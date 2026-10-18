"""V3+ (relações): aprende gatilhos de TREATS e INDICATES com os casos extras.

O extrator só cria TREATS e INDICATES quando há um gatilho na frase. Com poucos
pares rotulados, o PMI quase não acha gatilhos novos. Este script amplia os
dados por autotreinamento:

    1. Naive Bayes treinado nos pares rotulados à mão dos casos de
       desenvolvimento (os de avaliação ficam de fora).
    2. O modelo pontua os pares tratamento-condição e exame-condição dos casos
       minerados (45 de desenvolvimento + extras) com o léxico V3+. Pares com
       probabilidade alta viram positivos, e os com probabilidade baixa,
       negativos (pseudo-rótulos).
    3. O PMI entre cada palavra do trecho entre as entidades e o rótulo
       positivo escolhe os gatilhos, como em relacoes_pmi.learn_triggers, mas
       agora sobre muito mais pares. Só entram termos de alta precisão, com forma de
       verbo, particípio ou adjetivo de ligação, que ainda não são gatilhos da V1.

Uso (a partir da pasta fase2/):
    python src/gatilhos_mais_dados.py
Saída:
    resources/v3_mais_dados/triggers.csv (gatilhos da V1 + aprendidos)
    resources/v3_mais_dados/triggers_aprendidos.csv (com PMI e contagens)
"""

import csv
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import relacoes_pmi as rp  # noqa: E402

LEXICON = ROOT / "resources" / "v3_mais_dados" / "lexicon.csv"
V1_TRIGGERS = ROOT / "resources" / "v1" / "triggers.csv"
OUT_DIR = ROOT / "resources" / "v3_mais_dados"
EXTRA_CASES = ROOT / "data" / "external" / "cases_extra.csv"

HIGH, LOW = 0.9, 0.1       # limiares dos pseudo-rótulos
MIN_POSITIVES = 5          # ocorrências em pares positivos
MIN_CASES = 4              # casos distintos
MIN_PRECISION = 0.85       # positivos / ocorrências
MAX_PER_RELATION = 12
KIND = {"INDICATES": "relation", "TREATS": "treatment_target"}
# Gatilhos são verbos, particípios ou adjetivos de ligação ("showed", "treated",
# "suggestive"). Substantivos e adjetivos de modificação (mass, mild, lobe) só
# aparecem entre as entidades por acaso e entrariam como falsos gatilhos.
TRIGGER_SUFFIXES = ("ed", "ing", "ive")
# Palavras funcionais ou genéricas demais para serem gatilhos.
BLOCK = {
    "no", "not", "but", "without", "also", "after", "before", "during", "while",
    "however", "were", "was", "had", "history", "mg", "day", "days", "month",
    "months", "year", "years", "week", "weeks", "right", "left", "bilateral",
    "daily", "twice", "once", "per",
}


def main():
    all_cases = rp.read_csv(ROOT / "data" / "processed" / "all_cases.csv")
    dev_ids = {c["case_id"] for c in all_cases if c["split"] == "development"}
    eval_ids = {c["case_id"] for c in all_cases if c["split"] == "evaluation"}
    cases = [c for c in all_cases if c["case_id"] in dev_ids]
    cases += [
        {**c, "split": "extra"}
        for c in rp.read_csv(EXTRA_CASES)
        if c["case_id"] not in dev_ids | eval_ids
    ]

    lexicon = rp.bg.prepare_entries(rp.read_csv(LEXICON), "term")
    v1_rows = rp.read_csv(V1_TRIGGERS)
    triggers = rp.bg.prepare_entries(v1_rows, "phrase")
    pairs = rp.build_pairs(cases, lexicon, triggers)
    print(f"{len(cases)} casos, {len(pairs)} pares candidatos")

    gold = {
        r["pair_id"]: int(r["gold"])
        for r in rp.read_csv(rp.LABELS_PATH)
        if r["gold"].strip() in {"0", "1"}
    }
    # Os rótulos manuais vêm da V2; só os pares dos casos de desenvolvimento servem.
    gold_pairs = [
        p for p in rp.read_csv(rp.PAIRS_PATH)
        if p["pair_id"] in gold and p["case_id"] in dev_ids
    ]
    print(f"{len(gold_pairs)} pares rotulados à mão nos casos de desenvolvimento")

    known = {r["phrase"].lower() for r in v1_rows}
    # Palavras que fazem parte de nomes de entidades (mass, pulmonary...) são
    # colocações do próprio termo, não gatilhos entre duas entidades.
    vocabulary = {w for r in rp.read_csv(LEXICON) for w in r["term"].lower().split()}
    learned_rows, new_triggers = [], []
    for relation in sorted(rp.PAIR_TYPES.values()):
        seed = [p for p in gold_pairs if p["relation"] == relation]
        y_seed = np.array([gold[p["pair_id"]] for p in seed])
        pool = [p for p in pairs if p["relation"] == relation]
        _, scores = rp.fit_predict("naive_bayes", seed, y_seed, pool)
        labels = []
        for pair, score in zip(pool, scores):
            if int(pair["rule"]) or score >= HIGH:
                labels.append(1)
            elif score <= LOW:
                labels.append(0)
            else:
                labels.append(None)
        keep = [(p, l) for p, l in zip(pool, labels) if l is not None]
        data = seed + [p for p, _ in keep]
        data_y = list(y_seed) + [l for _, l in keep]
        print(
            f"{relation}: {len(seed)} rotulados, {len(pool)} candidatos, "
            f"{sum(l == 1 for _, l in keep)} pseudo-positivos, "
            f"{sum(l == 0 for _, l in keep)} pseudo-negativos"
        )

        rp.MIN_TRIGGER_POS, rp.MIN_TRIGGER_CASES = MIN_POSITIVES, MIN_CASES
        candidates = rp.learn_triggers(data, data_y)
        chosen = 0
        for t in candidates:
            phrase = t["phrase"]
            if (
                phrase.startswith("<")
                or phrase in known
                or any(w in BLOCK or w in vocabulary for w in phrase.split())
                or not phrase.split()[-1].endswith(TRIGGER_SUFFIXES)
                or t["positives"] / t["occurrences"] < MIN_PRECISION
            ):
                continue
            learned_rows.append({
                "phrase": phrase, "relation": relation,
                "pmi": f"{t['pmi']:.3f}", "positives": t["positives"],
                "occurrences": t["occurrences"],
            })
            new_triggers.append(
                {"phrase": phrase, "kind": KIND[relation], "value": relation}
            )
            known.add(phrase)
            chosen += 1
            if chosen >= MAX_PER_RELATION:
                break

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rp.write_csv(OUT_DIR / "triggers.csv", v1_rows + new_triggers, list(v1_rows[0]))
    rp.write_csv(
        OUT_DIR / "triggers_aprendidos.csv", learned_rows,
        ["phrase", "relation", "pmi", "positives", "occurrences"],
    )
    for row in learned_rows:
        print(row["relation"], row["phrase"], row["positives"], row["occurrences"])


if __name__ == "__main__":
    main()
