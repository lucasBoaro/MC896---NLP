"""Compara V1, V2 e V3 nos casos de avaliação e grava outputs/evaluation/comparison.csv."""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLINICAL_RELATIONS = {"BEFORE", "INDICATES", "TREATS"}
TRIGGERS = {"v1": "v1", "v2": "v2", "v3": "v1", "v3_mais_dados": "v1"}


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def metrics(version):
    nodes = read(ROOT / f"outputs/evaluation/{version}/nodes.csv")
    edges = read(ROOT / f"outputs/evaluation/{version}/edges.csv")
    entities = [n for n in nodes if n["type"] != "Case"]
    types = Counter(n["type"] for n in entities)
    relations = Counter(e["relation"] for e in edges)
    eval_cases = {r["case_id"] for r in read(ROOT / "data/processed/evaluation.csv")}
    with_entities = {n["case_id"] for n in entities}
    clinical = sum(relations[r] for r in CLINICAL_RELATIONS)
    return {
        "lexicon_terms": len(read(ROOT / f"resources/{version}/lexicon.csv")),
        "triggers": len(read(ROOT / f"resources/{TRIGGERS[version]}/triggers.csv")),
        "entity_mentions": len(entities),
        "symptoms": types["Symptom"],
        "exams": types["Exam"],
        "conditions": types["Condition"],
        "treatments": types["Treatment"],
        "structural_edges": len(edges) - clinical,
        "treats": relations["TREATS"],
        "indicates": relations["INDICATES"],
        "before": relations["BEFORE"],
        "entity_to_entity_edges": clinical,
        "total_edges": len(edges),
        "cases_without_entities": len(eval_cases - with_entities),
    }


def main():
    versions = ["v1", "v2", "v3", "v3_mais_dados"]
    results = {v: metrics(v) for v in versions}
    out = ROOT / "outputs/evaluation/comparison.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["metric", *versions])
        for key in results["v1"]:
            writer.writerow([key, *(results[v][key] for v in versions)])
    print(f"Gravado em {out}")


if __name__ == "__main__":
    main()
