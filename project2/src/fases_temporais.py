"""Etapa 2 (linha do tempo): classifica cada evento em uma fase do caso.

As regras do Projeto 1 só posicionam um evento quando há uma expressão de
tempo explícita perto dele, e cerca de 85% dos eventos ficam sem posição. Em
vez de inventar um dia exato, este script coloca cada evento em uma das fases
do relato, como o DocTimeRel do corpus clínico THYME:

    ANTECEDENTE     histórico anterior ao quadro atual
    APRESENTACAO    queixa, sintomas iniciais e achados da chegada
    CURSO           investigação e tratamento durante o atendimento
    SEGUIMENTO      alta, acompanhamento e desfecho

O método repete a receita da V3 (supervisão fraca):

1. Funções de rotulagem: expressões que fixam a fase com segurança
   (``history of``, ``years ago``, ``on admission``, ``POD 3``,
   ``at follow-up``...) rotulam parte dos eventos.
2. As expressões usadas pelas regras são mascaradas no texto, para que o
   classificador não decore as regras e aprenda o resto do contexto.
3. Uma regressão logística pontua cada evento com um modelo que não viu o
   seu caso no treino: validação cruzada agrupada por caso nos casos de
   desenvolvimento e, nos 11 de avaliação, um modelo treinado só com os de
   desenvolvimento. Eventos sem regra recebem a fase prevista quando o score
   passa de ``--min-score``.
4. O NPMI entre as palavras do contexto mascarado e cada fase lista os
   gatilhos aprendidos, que não estavam nas regras.

Uso (a partir da pasta project2/):
    python src/fases_temporais.py
    python src/fases_temporais.py --version v2

Entrada: outputs/full/<versão>/nodes.csv (gerado pelo build_graph.py).
Saídas:
    outputs/full/<versão>/nodes.csv e outputs/evaluation/<versão>/nodes.csv
        ganham, em ``attributes``, os campos ``phase``, ``phase_source``
        (regra ou modelo), ``phase_score`` e ``phase_cue`` (expressão usada pela
        regra). O build_graph.py não muda; rode este script depois dele.
    outputs/evaluation/fases/<versão>/metricas.csv
        comparação do modelo com linhas de base, contra os rótulos fracos dos
        casos de desenvolvimento.
    outputs/evaluation/fases/<versão>/gatilhos_aprendidos.csv
        palavras com maior NPMI com cada fase.
    data/interim/fases/<versão>/rotulagem_fases.csv
        planilha dos 11 casos de avaliação para anotar a fase à mão (coluna
        ``gold``). Os rótulos preenchidos são preservados e, quando existem,
        o script mede a acurácia das regras, do modelo e da combinação.
"""

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import build_graph as bg  # noqa: E402

CASES_PATH = ROOT / "data" / "processed" / "all_cases.csv"

PHASES = ["ANTECEDENTE", "APRESENTACAO", "CURSO", "SEGUIMENTO"]
N_FOLDS = 5
MIN_SCORE = 0.5
# Uma regra só vale para a entidade se a expressão estiver a até
# CUE_DISTANCE caracteres dela na mesma frase.
CUE_DISTANCE = 120
# Palavras de cada lado da entidade usadas como contexto.
WINDOW = 10
# Gatilho aprendido: palavra vista em MIN_CUE_EVENTS eventos de
# MIN_CUE_CASES casos diferentes.
MIN_CUE_EVENTS = 4
MIN_CUE_CASES = 3
MIN_CUE_NPMI = 0.1
TOP_CUES = 15

N = bg.NUMBER
LONG_UNIT = r"(?:years?|decades?)"
SHORT_UNIT = r"(?:minutes?|hours?|h|days?|weeks?)"
ANY_UNIT = r"(?:minutes?|hours?|h|days?|weeks?|months?|years?)"

# (fase, nível, expressão). O nível 1 é uma expressão temporal explícita e
# vence o nível 2 (verbos e frases típicas da fase) quando os dois aparecem
# perto da entidade. Entre expressões sobrepostas, vale a mais longa:
# "a 3-day history of" (apresentação) vence "history of" (antecedente).
LABELING_FUNCTIONS = [
    # Antecedentes
    ("ANTECEDENTE", 1, rf"\b{N}\s+{LONG_UNIT}\s+(?:ago|earlier|before|prior)\b"),
    ("ANTECEDENTE", 1, rf"\b(?:a\s+)?{N}[ -]year(?:-|\s+)history(?:\s+of)?\b"),
    ("ANTECEDENTE", 1, rf"\b(?:for|over|during)\s+(?:the\s+)?(?:past\s+|last\s+)?{N}\s+{LONG_UNIT}\b"),
    ("ANTECEDENTE", 1, r"\b(?:past|previous|prior)\s+(?:medical\s+|surgical\s+)?history\b"),
    ("ANTECEDENTE", 1, r"\b(?:medical|surgical|family|medication)\s+history\b"),
    ("ANTECEDENTE", 2, r"\bhistory\s+of\b"),
    ("ANTECEDENTE", 2, r"\bpreviously\b|\bprevious\b|\bin\s+the\s+past\b"),
    ("ANTECEDENTE", 2, r"\b(?:known|long-?standing)\b"),
    ("ANTECEDENTE", 2, r"\bhad\s+(?:been\s+)?(?:diagnosed|treated|undergone|operated)\b"),
    # Apresentação
    ("APRESENTACAO", 1, rf"\b(?:a\s+)?{N}[ -](?:minute|hour|day|week|month)(?:-|\s+)history(?:\s+of)?\b"),
    ("APRESENTACAO", 1, rf"\b{N}\s+(?:{SHORT_UNIT}|months?)\s+(?:ago|before|prior\s+to)\s+(?:admission|presentation)\b"),
    ("APRESENTACAO", 1, rf"\b{N}\s+(?:{SHORT_UNIT}|months?)\s+ago\b"),
    ("APRESENTACAO", 1, r"\b(?:on|at|upon)\s+(?:admission|presentation|arrival)\b"),
    ("APRESENTACAO", 1, r"\b(?:over|for|during)\s+the\s+(?:past|last)\s+(?:few\s+)?(?:days?|weeks?|months?)\b"),
    ("APRESENTACAO", 2, r"\bpresent(?:ed|ing|s)\b|\bpresentation\b"),
    ("APRESENTACAO", 2, r"\bcomplain(?:ed|ing|s)?\s+of\b|\bchief\s+complaint\b"),
    ("APRESENTACAO", 2, r"\b(?:admitted|referred|brought)\s+(?:to|with|for)\b"),
    ("APRESENTACAO", 2, r"\bemergency\s+(?:department|room)\b"),
    ("APRESENTACAO", 2, r"\bphysical\s+exam(?:ination)?\b|\bon\s+examination\b"),
    # Curso (investigação e tratamento)
    ("CURSO", 1, r"\b(?:POD|postoperative\s+day)\s*\d+\b"),
    ("CURSO", 1, r"\bpost-?operative(?:ly)?\b|\bintra-?operative(?:ly)?\b"),
    ("CURSO", 1, r"\bday\s+\d+\s+of\s+(?:hospitali[sz]ation|admission)\b"),
    ("CURSO", 1, r"\b\d+(?:st|nd|rd|th)\s+day\s+of\s+(?:hospitali[sz]ation|admission)\b"),
    ("CURSO", 1, r"\bduring\s+(?:the\s+|his\s+|her\s+)?(?:surgery|operation|procedure|hospitali[sz]ation|admission|hospital\s+stay)\b"),
    ("CURSO", 1, r"\bthe\s+(?:next|following)\s+(?:day|morning)\b"),
    ("CURSO", 1, rf"\b{N}\s+{SHORT_UNIT}\s+(?:later|after)\b|\bafter\s+{N}\s+{SHORT_UNIT}\b"),
    ("CURSO", 2, r"\bunderwent\b|\b(?:was|were)\s+performed\b"),
    ("CURSO", 2, r"\b(?:was|were)\s+(?:started|initiated|commenced|administered|given|prescribed)\b"),
    ("CURSO", 2, r"\b(?:was|were)\s+(?:treated|managed)\s+with\b"),
    ("CURSO", 2, r"\bsubsequent(?:ly)?\b"),
    # Seguimento
    ("SEGUIMENTO", 1, r"\bfollow(?:ed)?[ -]?up\b"),
    ("SEGUIMENTO", 1, r"\b(?:was\s+)?discharged\b|\bdischarge\b"),
    ("SEGUIMENTO", 1, rf"\b{N}\s+(?:months?|years?)\s+(?:later|after)\b|\bafter\s+{N}\s+(?:months?|years?)\b"),
    ("SEGUIMENTO", 1, r"\b(?:at|after)\s+(?:the\s+)?{N}[ -](?:month|year)\b".replace("{N}", N)),
    ("SEGUIMENTO", 2, r"\boutpatient\b|\brecurrence\b|\brecurred\b"),
    ("SEGUIMENTO", 2, r"\bremain(?:ed|s)\s+(?:asymptomatic|well|free|stable)\b"),
    ("SEGUIMENTO", 2, r"\b(?:died|passed\s+away)\b|\bdoing\s+well\b"),
]
COMPILED_LFS = [
    (phase, level, re.compile(pattern, re.IGNORECASE))
    for phase, level, pattern in LABELING_FUNCTIONS
]

STOP = {
    "a", "an", "the", "of", "and", "or", "in", "on", "at", "to", "for", "with",
    "by", "from", "as", "be", "her", "his", "she", "he", "patient", "which",
    "that", "this", "it", "its", "there", "their", "into", "we", "our",
}
TOKEN = re.compile(r"[a-z][a-z-]+|\d+")
NODE_FIELDS = bg.NODE_FIELDS
LABEL_FIELDS = [
    "n", "gold", "regra", "modelo", "score", "tipo", "termo", "frase",
    "case_id", "chave",
]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def node_key(node):
    return f"{node['case_id']}|{node['start']}|{node['end']}"


# ---------------------------------------------------------------------------
# regras (rótulos fracos)
# ---------------------------------------------------------------------------

def cue_matches(text):
    """Todas as expressões das regras no texto, sem sobreposição.

    Entre expressões sobrepostas, fica a mais longa.
    """
    found = []
    for phase, level, pattern in COMPILED_LFS:
        for match in pattern.finditer(text):
            found.append((match.start(), match.end(), phase, level, match.group(0)))
    found.sort(key=lambda m: (-(m[1] - m[0]), m[0]))
    kept = []
    for match in found:
        if all(match[1] <= k[0] or match[0] >= k[1] for k in kept):
            kept.append(match)
    return sorted(kept)


def rule_phase(entity_start, entity_end, matches):
    """Fase da regra mais forte e mais próxima da entidade, ou None."""
    ranked = []
    for start, end, phase, level, text in matches:
        distance = max(start - entity_end, entity_start - end, 0)
        if distance <= CUE_DISTANCE:
            ranked.append((level, distance, phase, text))
    if not ranked:
        return None, ""
    level, _, phase, text = min(ranked)
    return phase, text


def mask(text, matches):
    """Apaga do texto as expressões das regras (substitui por espaços)."""
    chars = list(text)
    for start, end, *_ in matches:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


# ---------------------------------------------------------------------------
# eventos e características
# ---------------------------------------------------------------------------

def words(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP]


def build_events(nodes, cases):
    """Um registro por evento, com contexto mascarado e rótulo da regra."""
    sentences = {}
    for case in cases:
        sentences[case["case_id"]] = bg._split_sentences(case["case_text"])

    events = []
    for node in nodes:
        if node["type"] == "Case":
            continue
        case_sentences = sentences[node["case_id"]]
        sid = int(node["sentence_id"])
        sentence = case_sentences[sid]
        text = sentence["text"]
        start = int(node["start"]) - sentence["start"]
        end = int(node["end"]) - sentence["start"]
        matches = cue_matches(text)
        phase, cue = rule_phase(start, end, matches)
        masked = mask(text, matches)
        previous = mask(case_sentences[sid - 1]["text"], cue_matches(case_sentences[sid - 1]["text"])) if sid else ""
        events.append({
            "node": node,
            "case_id": node["case_id"],
            "sentence_id": sid,
            "start": int(node["start"]),
            "position": sid / max(len(case_sentences) - 1, 1),
            "rule": phase,
            "cue": cue,
            "left": words(masked[:start])[-WINDOW:],
            "right": words(masked[end:])[:WINDOW],
            "previous": words(previous),
        })
    add_neighbor_phases(events)
    return events


def add_neighbor_phases(events):
    """Fase da regra no evento rotulado anterior e no seguinte do mesmo caso.

    O relato costuma andar em ordem de fases, então os vizinhos ajudam. Usa
    só rótulos das regras de outros eventos, nunca o do próprio evento.
    """
    by_case = defaultdict(list)
    for event in events:
        by_case[event["case_id"]].append(event)
    for case_events in by_case.values():
        case_events.sort(key=lambda e: e["start"])
        last = "NENHUMA"
        for event in case_events:
            event["prev_phase"] = last
            if event["rule"]:
                last = event["rule"]
        last = "NENHUMA"
        for event in reversed(case_events):
            event["next_phase"] = last
            if event["rule"]:
                last = event["rule"]


def feature_text(event, parts):
    """Documento de "palavras" para o CountVectorizer."""
    tokens = []
    node = event["node"]
    if "contexto" in parts:
        tokens += [f"L_{w}" for w in event["left"]]
        tokens += [f"R_{w}" for w in event["right"]]
        left_bigrams = zip(event["left"], event["left"][1:])
        tokens += [f"L_{a}_{b}" for a, b in left_bigrams]
        tokens += [f"P_{w}" for w in event["previous"]]
    if "entidade" in parts:
        tokens += [f"tipo={node['type']}", f"termo={node['label'].replace(' ', '_')}"]
        assertion = node["attributes"].get("assertion", "")
        tokens.append(f"assercao={assertion}")
    if "posicao" in parts:
        bucket = min(int(event["position"] * 5), 4)
        tokens.append(f"pos={bucket}")
        if event["sentence_id"] == 0:
            tokens.append("primeira_frase")
    if "vizinhos" in parts:
        tokens += [f"antes={event['prev_phase']}", f"depois={event['next_phase']}"]
    return " ".join(tokens)


FULL = ("contexto", "entidade", "posicao", "vizinhos")
CONFIGS = {
    "modelo completo": FULL,
    "sem vizinhos": ("contexto", "entidade", "posicao"),
    "só contexto": ("contexto",),
    "só posição": ("posicao",),
    "só vizinhos": ("vizinhos",),
}


def matrix(events, parts, vectorizer=None):
    docs = [feature_text(e, parts) for e in events]
    if vectorizer is None:
        vectorizer = CountVectorizer(
            token_pattern=r"\S+", lowercase=False, binary=True, min_df=1,
        )
        X = vectorizer.fit_transform(docs)
    else:
        X = vectorizer.transform(docs)
    position = csr_matrix(np.array([[e["position"]] for e in events]))
    return hstack([X, position]).tocsr(), vectorizer


def new_model():
    return LogisticRegression(max_iter=3000, C=0.2, class_weight="balanced")


def fit_predict(train_events, test_events, parts):
    """Treina com eventos rotulados pelas regras e pontua os eventos de teste."""
    train_events = [e for e in train_events if e["rule"]]
    X_train, vectorizer = matrix(train_events, parts)
    model = new_model().fit(X_train, [e["rule"] for e in train_events])
    X_test, _ = matrix(test_events, parts, vectorizer)
    proba = np.zeros((len(test_events), len(PHASES)))
    proba[:, [PHASES.index(c) for c in model.classes_]] = model.predict_proba(X_test)
    return proba


def cross_fit(events, parts):
    """Probabilidades de cada fase para cada evento.

    Como na V3, os casos de avaliação nunca entram no treino. Os eventos de
    desenvolvimento são pontuados por validação cruzada agrupada por caso
    (um modelo que não viu o caso); os de avaliação, por um modelo treinado
    com todos os casos de desenvolvimento.
    """
    dev = np.array([i for i, e in enumerate(events) if e["split"] != "evaluation"])
    held_out = np.array([i for i, e in enumerate(events) if e["split"] == "evaluation"])
    groups = np.array([events[i]["case_id"] for i in dev])
    proba = np.zeros((len(events), len(PHASES)))
    for train, test in GroupKFold(n_splits=N_FOLDS).split(dev, groups=groups):
        proba[dev[test]] = fit_predict(
            [events[i] for i in dev[train]], [events[i] for i in dev[test]], parts,
        )
    if len(held_out):
        proba[held_out] = fit_predict(
            [events[i] for i in dev], [events[i] for i in held_out], parts,
        )
    return proba


# ---------------------------------------------------------------------------
# avaliação
# ---------------------------------------------------------------------------

def evaluate(events, version):
    """Compara configurações e linhas de base contra os rótulos das regras."""
    labeled = [
        i for i, e in enumerate(events)
        if e["rule"] and e["split"] != "evaluation"
    ]
    y = [events[i]["rule"] for i in labeled]
    rows = []

    majority = Counter(y).most_common(1)[0][0]
    rows.append(metric_row("classe majoritária", y, [majority] * len(y)))
    neighbor = [
        events[i]["prev_phase"] if events[i]["prev_phase"] != "NENHUMA"
        else events[i]["next_phase"] if events[i]["next_phase"] != "NENHUMA"
        else majority
        for i in labeled
    ]
    rows.append(metric_row("copiar fase do vizinho", y, neighbor))

    probas = {}
    for name, parts in CONFIGS.items():
        proba = cross_fit(events, parts)
        probas[name] = proba
        predicted = [PHASES[k] for k in proba[labeled].argmax(axis=1)]
        rows.append(metric_row(f"regressão logística: {name}", y, predicted))
    return rows, probas["modelo completo"]


def metric_row(name, gold, predicted):
    row = {
        "metodo": name,
        "n": len(gold),
        "acuracia": f"{accuracy_score(gold, predicted):.3f}",
        "f1_macro": f"{f1_score(gold, predicted, labels=PHASES, average='macro', zero_division=0):.3f}",
    }
    per_class = f1_score(gold, predicted, labels=PHASES, average=None, zero_division=0)
    for phase, value in zip(PHASES, per_class):
        row[f"f1_{phase.lower()}"] = f"{value:.3f}"
    return row


def learned_cues(events):
    """Palavras do contexto mascarado com maior NPMI com cada fase."""
    labeled = [e for e in events if e["rule"]]
    total = len(labeled)
    phase_count = Counter(e["rule"] for e in labeled)
    word_count = Counter()
    joint = Counter()
    cases = defaultdict(set)
    for event in labeled:
        seen = set(event["left"]) | set(event["right"])
        for word in seen:
            if word.isdigit():
                continue
            word_count[word] += 1
            joint[(word, event["rule"])] += 1
            cases[(word, event["rule"])].add(event["case_id"])

    rows = []
    for phase in PHASES:
        scored = []
        for (word, p), n_wp in joint.items():
            if p != phase or n_wp < MIN_CUE_EVENTS or len(cases[(word, p)]) < MIN_CUE_CASES:
                continue
            p_wp = n_wp / total
            if p_wp == 1.0:
                continue
            pmi = math.log2(p_wp / ((word_count[word] / total) * (phase_count[phase] / total)))
            scored.append((pmi / -math.log2(p_wp), word, n_wp, len(cases[(word, p)])))
        scored = [s for s in scored if s[0] >= MIN_CUE_NPMI]
        for npmi, word, n_wp, n_cases in sorted(scored, reverse=True)[:TOP_CUES]:
            rows.append({
                "fase": phase, "palavra": word, "npmi": f"{npmi:.3f}",
                "eventos": n_wp, "casos": n_cases,
            })
    return rows


def gold_report(sheet):
    """Acurácia das regras, do modelo e da combinação contra a anotação manual."""
    annotated = [r for r in sheet if r["gold"].strip().upper() in PHASES]
    if not annotated:
        return []
    rows = []
    for name, column in (("regras", "regra"), ("modelo", "modelo")):
        covered = [r for r in annotated if r[column]]
        hits = sum(r[column] == r["gold"].strip().upper() for r in covered)
        rows.append({
            "metodo": f"{name} (anotação manual)",
            "n": len(annotated),
            "cobertura": f"{len(covered) / len(annotated):.3f}",
            "acuracia": f"{hits / len(covered):.3f}" if covered else "",
        })
    combined = [(r["regra"] or r["modelo"], r["gold"].strip().upper()) for r in annotated]
    covered = [(p, g) for p, g in combined if p]
    rows.append({
        "metodo": "regras + modelo (anotação manual)",
        "n": len(annotated),
        "cobertura": f"{len(covered) / len(annotated):.3f}",
        "acuracia": f"{sum(p == g for p, g in covered) / len(covered):.3f}" if covered else "",
    })
    return rows


# ---------------------------------------------------------------------------
# saídas
# ---------------------------------------------------------------------------

def assign_phases(events, proba, min_score):
    for event, scores in zip(events, proba):
        attributes = event["node"]["attributes"]
        for field in ("phase", "phase_source", "phase_score", "phase_cue"):
            attributes.pop(field, None)
        k = int(scores.argmax())
        event["model"] = PHASES[k] if scores[k] >= min_score else ""
        event["score"] = float(scores[k])
        if event["rule"]:
            attributes.update(phase=event["rule"], phase_source="regra", phase_cue=event["cue"])
        elif event["model"]:
            attributes.update(
                phase=event["model"], phase_source="modelo",
                phase_score=round(event["score"], 3),
            )


def write_nodes(path, nodes):
    rows = []
    for node in nodes:
        row = dict(node)
        row["attributes"] = json.dumps(node["attributes"], ensure_ascii=False, separators=(",", ":"))
        rows.append(row)
    write_csv(path, rows, NODE_FIELDS)


def copy_to_evaluation(events, path):
    """Copia as fases para o nodes.csv dos casos de avaliação, pela posição."""
    if not path.exists():
        return 0
    by_key = {node_key(e["node"]): e["node"]["attributes"] for e in events}
    nodes = read_nodes(path)
    copied = 0
    for node in nodes:
        source = by_key.get(node_key(node))
        if node["type"] == "Case" or source is None:
            continue
        for field in ("phase", "phase_source", "phase_score", "phase_cue"):
            node["attributes"].pop(field, None)
            if field in source:
                node["attributes"][field] = source[field]
        copied += 1
    write_nodes(path, nodes)
    return copied


def labeling_sheet(events, split, path):
    """Planilha de anotação manual da fase, preservando o que já foi preenchido."""
    previous = {}
    if path.exists():
        previous = {r["chave"]: r["gold"] for r in read_csv(path)}
    rows = []
    for event in sorted(events, key=lambda e: (e["case_id"], e["start"])):
        if split.get(event["case_id"]) != "evaluation":
            continue
        node = event["node"]
        sentence = node["evidence"]
        rows.append({
            "chave": node_key(node),
            "gold": previous.get(node_key(node), ""),
            "regra": event["rule"] or "",
            "modelo": event["model"],
            "score": f"{event['score']:.2f}",
            "tipo": node["type"],
            "termo": node["mention_text"],
            "frase": sentence.replace(node["mention_text"], f"[{node['mention_text']}]", 1),
            "case_id": event["case_id"],
        })
    for n, row in enumerate(rows, 1):
        row["n"] = n
    write_csv(path, rows, LABEL_FIELDS)
    return rows


def read_nodes(path):
    nodes = read_csv(path)
    for node in nodes:
        node["attributes"] = json.loads(node.get("attributes") or "{}")
    return nodes


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Classifica os eventos em fases do caso.")
    parser.add_argument("--version", default="v3", help="pasta da versão em outputs/ (v1, v2 ou v3)")
    parser.add_argument("--cases", type=Path, default=CASES_PATH)
    parser.add_argument(
        "--min-score", type=float, default=MIN_SCORE,
        help="score mínimo para o modelo posicionar um evento sem regra",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    full_nodes = ROOT / "outputs" / "full" / args.version / "nodes.csv"
    eval_nodes = ROOT / "outputs" / "evaluation" / args.version / "nodes.csv"
    out_dir = ROOT / "outputs" / "evaluation" / "fases" / args.version
    sheet_path = ROOT / "data" / "interim" / "fases" / args.version / "rotulagem_fases.csv"

    cases = read_csv(args.cases)
    split = {c["case_id"]: c.get("split", "") for c in cases}
    nodes = read_nodes(full_nodes)
    events = build_events(nodes, cases)
    for event in events:
        event["split"] = split.get(event["case_id"], "")

    metrics, proba = evaluate(events, args.version)
    assign_phases(events, proba, args.min_score)
    write_nodes(full_nodes, nodes)
    copied = copy_to_evaluation(events, eval_nodes)
    sheet = labeling_sheet(events, split, sheet_path)
    metrics += gold_report(sheet)
    write_csv(out_dir / "metricas.csv", metrics, list(dict.fromkeys(k for r in metrics for k in r)))
    cues = learned_cues(events)
    write_csv(out_dir / "gatilhos_aprendidos.csv", cues, ["fase", "palavra", "npmi", "eventos", "casos"])

    n = len(events)
    by_rule = sum(1 for e in events if e["rule"])
    by_model = sum(1 for e in events if not e["rule"] and e["model"])
    timed = sum(1 for e in events if e["node"]["attributes"].get("time"))
    print(f"Eventos: {n}")
    print(f"Com expressão de tempo (Projeto 1): {timed} ({timed / n:.0%})")
    print(f"Fase pela regra: {by_rule} ({by_rule / n:.0%})")
    print(f"Fase pelo modelo (score >= {args.min_score}): {by_model} ({by_model / n:.0%})")
    print(f"Com fase no total: {by_rule + by_model} ({(by_rule + by_model) / n:.0%})")
    print("Distribuição:", dict(Counter(e["node"]["attributes"].get("phase", "sem fase") for e in events)))
    print()
    for row in metrics:
        extra = f" cobertura={row['cobertura']}" if "cobertura" in row else f" f1_macro={row['f1_macro']}"
        print(f"  {row['metodo']:<42} acurácia={row['acuracia']}{extra}")
    print()
    print(f"Atualizados: {full_nodes} e {copied} eventos em {eval_nodes}")
    print(f"Métricas: {out_dir / 'metricas.csv'}")
    print(f"Planilha para anotação manual: {sheet_path}")


if __name__ == "__main__":
    main()
