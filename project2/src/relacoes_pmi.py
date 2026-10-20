"""Etapa 2 (relações): melhora TREATS e INDICATES com PMI e aprendizado de máquina.

O extrator do Projeto 1 só cria TREATS (tratamento -> condição) e INDICATES
(exame -> condição) quando encontra um gatilho escrito à mão na frase. Este
script trata cada par tratamento-condição ou exame-condição da mesma frase como
um candidato e compara formas de decidir se a relação existe:

    regras            o build_graph.py atual (gatilhos da V2)
    regras+gatilhos   caminho 1: regras mais gatilhos aprendidos por PMI entre
                      as palavras do trecho entre as entidades e o rótulo
    npmi              limiar de NPMI da coocorrência do par nos casos
    naive_bayes       caminho 2: Naive Bayes sobre as palavras entre as entidades
    reg_logistica     caminho 2: regressão logística com palavras e estatísticas

Uso (a partir da pasta project2/):
    python src/relacoes_pmi.py candidatos
        Gera data/interim/relations/pares_candidatos.csv (atributos dos pares) e
        data/interim/relations/rotulagem.csv, a planilha para rotular à mão: cada
        linha traz uma pergunta e a frase com as duas entidades marcadas, e a
        coluna ``gold`` recebe 1 (sim) ou 0 (não). Os rótulos já preenchidos são
        preservados quando o comando é executado de novo.
    python src/relacoes_pmi.py avaliar
        Compara os métodos com validação cruzada agrupada por caso e grava
        outputs/evaluation/relacoes_comparacao.csv,
        outputs/evaluation/relacoes_predicoes.csv e
        resources/v3/triggers_aprendidos.csv.
        Sem rótulos em rotulagem.csv, usa as regras como rótulo (avaliação circular,
        serve apenas para testar o encadeamento).
"""

import argparse
from collections import Counter, defaultdict
import csv
import itertools
import math
from pathlib import Path
import re
import sys

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.naive_bayes import MultinomialNB

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import build_graph as bg  # noqa: E402

CASES_PATH = ROOT / "data" / "processed" / "all_cases.csv"
LEXICON_PATH = ROOT / "resources" / "v2" / "lexicon.csv"
TRIGGERS_PATH = ROOT / "resources" / "v2" / "triggers.csv"
PAIRS_PATH = ROOT / "data" / "interim" / "relations" / "pares_candidatos.csv"
LABELS_PATH = ROOT / "data" / "interim" / "relations" / "rotulagem.csv"
COMPARISON_PATH = ROOT / "outputs" / "evaluation" / "relacoes_comparacao.csv"
PREDICTIONS_PATH = ROOT / "outputs" / "evaluation" / "relacoes_predicoes.csv"
LEARNED_TRIGGERS_PATH = ROOT / "resources" / "v3" / "triggers_aprendidos.csv"

# Tipo da fonte, tipo do destino e relação que o par pode receber.
PAIR_TYPES = {
    ("Treatment", "Condition"): "TREATS",
    ("Exam", "Condition"): "INDICATES",
}
PAIR_FIELDS = [
    "pair_id", "case_id", "split", "relation", "source", "source_type",
    "target", "target_type", "source_first", "tokens_between",
    "entities_between", "cooc_cases", "npmi_cases", "rule", "left_context",
    "between", "sentence",
]
LABEL_FIELDS = ["n", "gold", "pergunta", "frase", "case_id", "pair_id"]
QUESTIONS = {
    "TREATS": "O tratamento [{source}] foi usado para tratar [{target}]?",
    "INDICATES": "O exame [{source}] mostrou ou indicou [{target}]?",
}
TYPE_TAGS = {"Treatment": "TRATAMENTO", "Exam": "EXAME", "Condition": "CONDIÇÃO"}

# Coocorrência vista em um único caso dá NPMI máximo por acaso (evento raro).
MIN_COOC_CASES = 2
# Caminho 1: um termo vira gatilho se aparece em pelo menos MIN_TRIGGER_POS
# pares positivos de MIN_TRIGGER_CASES casos diferentes e tem PMI normalizado
# com o rótulo positivo de pelo menos MIN_TRIGGER_NPMI. O PMI com o rótulo não
# passa de -log2 P(+): com 78% de pares positivos o teto é 0,36, então um
# limiar fixo de PMI não acharia nada. Dividir pelo teto deixa a escala em 0-1.
MIN_TRIGGER_POS = 2
MIN_TRIGGER_CASES = 2
MIN_TRIGGER_NPMI = 0.8
N_FOLDS = 5
# Palavras antes da primeira entidade ("treated with X for Y").
LEFT_WINDOW = 4

STOP = {
    "a", "an", "the", "of", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "from", "as", "is", "was", "were", "be", "been", "had", "has", "have",
    "her", "his", "she", "he", "patient", "which", "that", "this", "after",
    "before", "also", "then", "who", "it", "its", "there", "their", "into",
}
TOKEN = re.compile(r"[a-z][a-z-]+")


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def tokens(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def ngrams(text):
    words = tokens(text)
    return set(words) | {" ".join(pair) for pair in zip(words, words[1:])}


def terms(pair):
    """Unigramas e bigramas entre as entidades e, com prefixo ``<``, antes delas."""
    left = {f"<{term}" for term in ngrams(pair["left_context"])}
    return ngrams(pair["between"]) | left


# ---------------------------------------------------------------------------
# candidatos
# ---------------------------------------------------------------------------

def case_npmi(nodes, n_cases):
    """NPMI da coocorrência de dois rótulos de entidade no mesmo caso."""
    labels_by_case = defaultdict(set)
    for node in nodes:
        if node["type"] != "Case":
            labels_by_case[node["case_id"]].add(node["label"])
    count = Counter()
    cooc = Counter()
    for labels in labels_by_case.values():
        count.update(labels)
        cooc.update(itertools.combinations(sorted(labels), 2))

    def score(a, b):
        n_ab = cooc[tuple(sorted((a, b)))]
        if n_ab < MIN_COOC_CASES:
            return n_ab, 0.0
        p_ab = n_ab / n_cases
        if p_ab == 1.0:
            return n_ab, 1.0
        pmi = math.log2(p_ab / ((count[a] / n_cases) * (count[b] / n_cases)))
        return n_ab, pmi / -math.log2(p_ab)

    return score


def build_pairs(cases, lexicon, triggers):
    nodes, edges = bg.build_graph(cases, lexicon, triggers)
    rule_edges = {
        (e["source_id"], e["target_id"], e["relation"]) for e in edges
    }
    split = {c["case_id"]: c.get("split", "") for c in cases}
    sentence_start = {
        (c["case_id"], s["sentence_id"]): s["start"]
        for c in cases
        for s in bg._split_sentences(c["case_text"])
    }
    npmi = case_npmi(nodes, len(cases))

    by_sentence = defaultdict(list)
    for node in nodes:
        if node["type"] != "Case":
            by_sentence[(node["case_id"], node["sentence_id"])].append(node)

    pairs = []
    for key, sentence_nodes in by_sentence.items():
        offset = sentence_start[key]
        for source, target in itertools.permutations(sentence_nodes, 2):
            relation = PAIR_TYPES.get((source["type"], target["type"]))
            if not relation or source["label"] == target["label"]:
                continue
            sentence = source["evidence"]
            left, right = sorted((source, target), key=lambda n: n["start"])
            between = sentence[left["end"] - offset:right["start"] - offset]
            before = sentence[:left["start"] - offset].split()[-LEFT_WINDOW:]
            n_ab, score = npmi(source["label"], target["label"])
            marked = sentence
            for node in (right, left):
                start, end = node["start"] - offset, node["end"] - offset
                marked = (
                    f"{marked[:start]}[{TYPE_TAGS[node['type']]}: "
                    f"{marked[start:end]}]{marked[end:]}"
                )
            pairs.append({
                "pair_id": (
                    f"{key[0]}|{key[1]}|{source['start']}|{target['start']}"
                ),
                "case_id": key[0],
                "source_id": source["node_id"],
                "target_id": target["node_id"],
                "split": split[key[0]],
                "relation": relation,
                "source": source["mention_text"],
                "source_type": source["type"],
                "target": target["mention_text"],
                "target_type": target["type"],
                "source_first": int(source["start"] < target["start"]),
                "tokens_between": len(between.split()),
                "entities_between": sum(
                    left["end"] <= n["start"] and n["end"] <= right["start"]
                    for n in sentence_nodes
                ),
                "cooc_cases": n_ab,
                "npmi_cases": f"{score:.3f}",
                "rule": int(
                    (source["node_id"], target["node_id"], relation) in rule_edges
                ),
                "left_context": " ".join(before),
                "between": between.strip(),
                "sentence": sentence,
                "marked": marked,
            })
    return sorted(pairs, key=lambda p: (p["case_id"], p["pair_id"]))


def cmd_candidates(args):
    cases = read_csv(args.cases)
    lexicon = bg.prepare_entries(read_csv(args.lexicon), "term")
    triggers = bg.prepare_entries(read_csv(args.triggers), "phrase")
    pairs = build_pairs(cases, lexicon, triggers)

    # Não perde a rotulagem manual quando os candidatos são regerados.
    old_gold = {}
    if args.labels.exists():
        old_gold = {
            r["pair_id"]: r["gold"] for r in read_csv(args.labels) if r["gold"]
        }
    ordered = sorted(pairs, key=lambda p: (p["relation"], p["case_id"], p["pair_id"]))
    labels = [
        {
            "n": n,
            "gold": old_gold.get(pair["pair_id"], ""),
            "pergunta": QUESTIONS[pair["relation"]].format(**pair),
            "frase": pair["marked"],
            "case_id": pair["case_id"],
            "pair_id": pair["pair_id"],
        }
        for n, pair in enumerate(ordered, start=1)
    ]
    print(f"Rótulos preservados: {sum(bool(r['gold']) for r in labels)}")

    write_csv(args.output, pairs, PAIR_FIELDS + ["marked"])
    write_csv(args.labels, labels, LABEL_FIELDS)
    by_relation = Counter((p["relation"], p["rule"]) for p in pairs)
    for relation in sorted(set(PAIR_TYPES.values())):
        total = by_relation[(relation, 0)] + by_relation[(relation, 1)]
        print(
            f"{relation}: {total} pares candidatos, "
            f"{by_relation[(relation, 1)]} marcados pelas regras"
        )
    print(f"Planilha para rotular: {args.labels}")


# ---------------------------------------------------------------------------
# caminho 1: gatilhos aprendidos por PMI
# ---------------------------------------------------------------------------

def learn_triggers(pairs, labels):
    """PMI entre cada termo do trecho entre as entidades e o rótulo positivo.

    PMI(t, +) = log2( P(t, +) / (P(t) P(+)) ), contando pares: um termo que
    aparece mais nos pares positivos do que o acaso prevê vira gatilho.
    """
    n = len(pairs)
    n_pos = sum(labels)
    if n_pos == 0 or n_pos == n:
        return []
    term_count = Counter()
    term_pos = Counter()
    term_cases = defaultdict(set)
    for pair, label in zip(pairs, labels):
        for term in terms(pair):
            term_count[term] += 1
            term_pos[term] += label
            if label:
                term_cases[term].add(pair["case_id"])
    learned = []
    for term, n_term_pos in term_pos.items():
        if (
            n_term_pos < MIN_TRIGGER_POS
            or len(term_cases[term]) < MIN_TRIGGER_CASES
        ):
            continue
        pmi = math.log2((n_term_pos / n) / ((term_count[term] / n) * (n_pos / n)))
        if pmi / -math.log2(n_pos / n) >= MIN_TRIGGER_NPMI:
            learned.append({
                "phrase": term,
                "pmi": pmi,
                "positives": n_term_pos,
                "occurrences": term_count[term],
            })
    return sorted(learned, key=lambda t: (-t["pmi"], -t["positives"]))


def predict_with_triggers(pairs, learned):
    phrases = {t["phrase"] for t in learned}
    return np.array([
        int(int(p["rule"]) or bool(terms(p) & phrases)) for p in pairs
    ])


# ---------------------------------------------------------------------------
# caminho 2: classificadores
# ---------------------------------------------------------------------------

def numeric_features(pairs):
    return csr_matrix(np.array([
        [
            math.log1p(int(p["tokens_between"])),
            int(p["source_first"]),
            int(p["entities_between"]),
            float(p["npmi_cases"]),
        ]
        for p in pairs
    ]))


def text_vectorizer():
    return CountVectorizer(
        analyzer=lambda pair: sorted(terms(pair)),
        binary=True,
    )


def fit_predict(method, train, y_train, test):
    """Treina no fold de treino e devolve (predições, scores) do fold de teste."""
    rule = np.array([int(p["rule"]) for p in test])
    if method == "sempre_sim":
        return np.ones(len(test), dtype=int), np.ones(len(test))
    if method == "regras":
        return rule, rule.astype(float)
    if method == "regras+gatilhos":
        pred = predict_with_triggers(test, learn_triggers(train, y_train))
        return pred, pred.astype(float)
    if method == "npmi":
        values = np.array([float(p["npmi_cases"]) for p in train])
        scores = np.array([float(p["npmi_cases"]) for p in test])
        best = max(
            sorted(set(values)) or [0.0],
            key=lambda t: f1(y_train, (values >= t).astype(int)),
        )
        return (scores >= best).astype(int), scores
    if len(set(y_train)) < 2:
        return rule, rule.astype(float)

    vectorizer = text_vectorizer()
    x_train = vectorizer.fit_transform(train)
    x_test = vectorizer.transform(test)
    if method == "naive_bayes":
        model = MultinomialNB(alpha=1.0)
    else:
        x_train = hstack([x_train, numeric_features(train)]).tocsr()
        x_test = hstack([x_test, numeric_features(test)]).tocsr()
        model = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
    model.fit(x_train, y_train)
    scores = model.predict_proba(x_test)[:, 1]
    return (scores >= 0.5).astype(int), scores


# sempre_sim é a referência mínima: com muitos pares positivos, um método que
# diz "sim" para tudo já tem F1 alto.
METHODS = [
    "sempre_sim", "regras", "regras+gatilhos", "npmi", "naive_bayes",
    "reg_logistica",
]


def f1(y, pred):
    tp = int(((y == 1) & (pred == 1)).sum())
    if tp == 0:
        return 0.0
    return 2 * tp / (int(y.sum()) + int(pred.sum()))


def metrics(y, pred):
    tp = int(((y == 1) & (pred == 1)).sum())
    precision = tp / pred.sum() if pred.sum() else 0.0
    recall = tp / y.sum() if y.sum() else 0.0
    return {
        "positivos": int(y.sum()),
        "previstos": int(pred.sum()),
        "acertos": tp,
        "acuracia": f"{(y == pred).mean():.3f}",
        "precisao": f"{precision:.3f}",
        "revocacao": f"{recall:.3f}",
        "f1": f"{f1(y, pred):.3f}",
    }


def cmd_evaluate(args):
    pairs = read_csv(args.pairs)
    gold = {}
    if args.labels.exists():
        gold = {
            r["pair_id"]: r["gold"].strip()
            for r in read_csv(args.labels)
            if r["gold"].strip() in {"0", "1"}
        }
    for pair in pairs:
        pair["gold"] = gold.get(pair["pair_id"], "")
    labeled = [p for p in pairs if p["gold"]]
    if labeled:
        label_source = "gold"
        label_of = lambda p: int(p["gold"])  # noqa: E731
    else:
        print(
            "AVISO: nenhum rótulo em rotulagem.csv; usando as regras como rótulo. "
            "A comparação é circular e só testa o encadeamento."
        )
        labeled = pairs
        label_source = "regras"
        label_of = lambda p: int(p["rule"])  # noqa: E731

    rows = []
    predictions = {p["pair_id"]: {"pair_id": p["pair_id"]} for p in labeled}
    learned_rows = []
    for relation in sorted(set(PAIR_TYPES.values())):
        subset = [p for p in labeled if p["relation"] == relation]
        if not subset:
            continue
        y = np.array([label_of(p) for p in subset])
        groups = np.array([p["case_id"] for p in subset])
        if len(set(groups)) < 2:
            print(f"{relation}: rótulos de um só caso, ainda não dá para avaliar")
            continue
        folds = GroupKFold(n_splits=min(N_FOLDS, len(set(groups))))
        oof = {m: np.zeros(len(subset), dtype=int) for m in METHODS}
        oof_score = {m: np.zeros(len(subset)) for m in METHODS}
        for train_idx, test_idx in folds.split(subset, y, groups):
            train = [subset[i] for i in train_idx]
            test = [subset[i] for i in test_idx]
            for method in METHODS:
                pred, score = fit_predict(method, train, y[train_idx], test)
                oof[method][test_idx] = pred
                oof_score[method][test_idx] = score
        for method in METHODS:
            rows.append({
                "relacao": relation,
                "metodo": method,
                "rotulo": label_source,
                "pares": len(subset),
                **metrics(y, oof[method]),
            })
            for pair, score in zip(subset, oof_score[method]):
                predictions[pair["pair_id"]][method] = f"{score:.3f}"
        for pair, label in zip(subset, y):
            predictions[pair["pair_id"]].update({
                "relation": relation,
                "label": label,
                "source": pair["source"],
                "target": pair["target"],
                "between": pair["between"],
            })

        # Gatilhos finais, aprendidos com todos os pares rotulados.
        known = {
            t["phrase"].lower() for t in read_csv(TRIGGERS_PATH)
        }
        for trigger in learn_triggers(subset, y):
            learned_rows.append({
                "phrase": trigger["phrase"],
                "relation": relation,
                "pmi": f"{trigger['pmi']:.3f}",
                "positives": trigger["positives"],
                "occurrences": trigger["occurrences"],
                "already_in_v2": int(trigger["phrase"] in known),
            })

    if not rows:
        print("Rotule pares de pelo menos dois casos para comparar os métodos.")
        return
    write_csv(COMPARISON_PATH, rows, list(rows[0]))
    write_csv(
        PREDICTIONS_PATH,
        list(predictions.values()),
        ["pair_id", "relation", "label", "source", "target", "between", *METHODS],
    )
    write_csv(
        LEARNED_TRIGGERS_PATH,
        learned_rows,
        ["phrase", "relation", "pmi", "positives", "occurrences", "already_in_v2"],
    )

    print(f"Rótulo: {label_source}; pares avaliados: {len(labeled)}")
    print(f"{'relação':<10} {'método':<16} {'Acur':>6} {'P':>6} {'R':>6} {'F1':>6}")
    for row in rows:
        print(
            f"{row['relacao']:<10} {row['metodo']:<16} "
            f"{row['acuracia']:>6} {row['precisao']:>6} {row['revocacao']:>6} {row['f1']:>6}"
        )
    print(f"Comparação: {COMPARISON_PATH}")
    print(f"Gatilhos aprendidos: {LEARNED_TRIGGERS_PATH}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    cand = sub.add_parser("candidatos", help="gera a planilha de pares")
    cand.add_argument("--cases", type=Path, default=CASES_PATH)
    cand.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    cand.add_argument("--triggers", type=Path, default=TRIGGERS_PATH)
    cand.add_argument("--output", type=Path, default=PAIRS_PATH)
    cand.add_argument("--labels", type=Path, default=LABELS_PATH)
    ev = sub.add_parser("avaliar", help="compara os métodos")
    ev.add_argument("--pairs", type=Path, default=PAIRS_PATH)
    ev.add_argument("--labels", type=Path, default=LABELS_PATH)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.command == "candidatos":
        cmd_candidates(args)
    else:
        cmd_evaluate(args)


if __name__ == "__main__":
    main()
