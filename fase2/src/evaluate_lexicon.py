"""Avalia o léxico V3 contra os termos que a V2 acrescentou (source=evaluation_v2).

Mede o recall independente: a V3 é minerada sem os 11 casos de avaliação,
então os termos do gabarito que ela recupera não foram vistos na mineração.

Grava outputs/evaluation/lexicon_recall.csv.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KS = (50, 100, 200, 400)


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    gold = {
        r["term"].lower(): r["type"]
        for r in read(ROOT / "resources/v2/lexicon.csv")
        if r["source"] == "evaluation_v2"
    }
    learned = {
        r["term"].lower(): r["type"]
        for r in read(ROOT / "resources/v3/lexicon.csv")
        if r["source"] == "learned_v3"
    }
    candidates = read(ROOT / "data/interim/ngram_candidates/candidatos_v3.csv")

    # Teto: termos do gabarito que aparecem no texto usado na mineração.
    mining_text = " ".join(
        r["case_text"].lower() for r in read(ROOT / "data/processed/development.csv")
    )
    reachable = {t for t in gold if t in mining_text}

    rows = [("gold_terms", len(gold)), ("gold_in_mining_corpus", len(reachable))]
    found = {t for t in learned if t in gold}
    typed = {t for t in found if learned[t] == gold[t]}
    rows += [
        ("learned_terms", len(learned)),
        ("gold_recovered", len(found)),
        ("gold_recovered_correct_type", len(typed)),
        ("recall_vs_gold", round(len(found) / len(gold), 4)),
        ("recall_vs_reachable", round(len(found) / len(reachable), 4) if reachable else 0),
        ("precision_vs_gold_lower_bound", round(len(found) / len(learned), 4)),
    ]
    for k in KS:
        top = candidates[:k]
        hits = [c for c in top if c["term"].lower() in gold]
        right = [c for c in hits if c["pred_type"] == gold[c["term"].lower()]]
        rows += [
            (f"top{k}_gold_hits", len(hits)),
            (f"top{k}_correct_type", len(right)),
            (f"top{k}_recall_vs_gold", round(len(hits) / len(gold), 4)),
        ]

    out = ROOT / "outputs/evaluation/lexicon_recall.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["metric", "value"])
        writer.writerows(rows)
    for name, value in rows:
        print(f"{name:32} {value}")
    print(f"Gravado em {out}")


if __name__ == "__main__":
    main()
