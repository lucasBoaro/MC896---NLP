"""Relaciona casos aos artigos e separa desenvolvimento de avaliação."""

import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "Projeto 1" / "sample"
OUTPUT_DIR = ROOT / "data" / "prepared"
EVALUATION_FRACTION = 0.20
SEED = 42

ARTICLE_FIELDS = ["title", "keywords", "mesh_terms", "major_mesh_terms"]


def read_csv(path):
    """Lê um CSV e devolve uma lista de registros."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def split_data(cases, metadata):
    """Associa os metadados e separa todos os casos de cada artigo juntos."""
    metadata_by_article = {
        article["article_id"]: article
        for article in metadata
    }

    article_ids = sorted(metadata_by_article)
    random.Random(SEED).shuffle(article_ids)

    evaluation_size = round(len(article_ids) * EVALUATION_FRACTION)
    evaluation_articles = set(article_ids[:evaluation_size])

    development = []
    evaluation = []

    for case in cases:
        article = metadata_by_article[case["article_id"]]
        record = {
            **case,
            **{field: article[field] for field in ARTICLE_FIELDS},
        }

        if case["article_id"] in evaluation_articles:
            evaluation.append(record)
        else:
            development.append(record)

    return development, evaluation


def write_csv(path, records):
    """Salva uma lista de registros em CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def main():
    cases = read_csv(INPUT_DIR / "cases.csv")
    metadata = read_csv(INPUT_DIR / "metadata.csv")

    development, evaluation = split_data(cases, metadata)

    all_cases = [
        *({**record, "split": "development"} for record in development),
        *({**record, "split": "evaluation"} for record in evaluation),
    ]

    write_csv(OUTPUT_DIR / "development.csv", development)
    write_csv(OUTPUT_DIR / "evaluation.csv", evaluation)
    write_csv(OUTPUT_DIR / "all_cases.csv", all_cases)

    print(f"Desenvolvimento: {len(development)} casos")
    print(f"Avaliação: {len(evaluation)} casos")
    print(f"Consolidado: {len(all_cases)} casos")


if __name__ == "__main__":
    main()
