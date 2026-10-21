"""Amostra casos extras do MultiCaRe para o modelo com mais dados.

Lê o cases.parquet do MultiCaRe (Zenodo, doi 10.5281/zenodo.10079370, ~160 MB),
descarta os artigos que já estão em data/external/cases.csv (inclusive os de
avaliação, para não haver vazamento) e sorteia N casos com semente fixa.

Uso (a partir da pasta project2/; requer pandas e pyarrow):
    python src/sample_multicare.py CAMINHO/cases.parquet --n 1000
Saída:
    data/external/cases_extra.csv  (mesmas colunas de cases.csv)
"""

import argparse
import csv
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["article_id", "age", "case_id", "case_text", "gender"]
MIN_CHARS, MAX_CHARS = 300, 4000
# O MultiCaRe inclui relatos veterinários; o projeto trata só de pacientes humanos.
ANIMAL = re.compile(
    r"\b(cat|dog|canine|feline|equine|bovine|horse|cow|calf|rabbit|veterinar\w*|spayed|neutered)\b",
    re.I,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data" / "external" / "cases_extra.csv"
    )
    args = parser.parse_args()

    with (ROOT / "data" / "external" / "cases.csv").open(encoding="utf-8-sig", newline="") as f:
        used = {row["article_id"] for row in csv.DictReader(f)}

    frame = pd.read_parquet(args.parquet)
    frame = frame[~frame["article_id"].isin(used)]
    rows = [
        {"article_id": article, **{k: case.get(k, "") for k in FIELDS[1:]}}
        for article, cases in zip(frame["article_id"], frame["cases"])
        for case in cases
        if MIN_CHARS <= len(case["case_text"]) <= MAX_CHARS
        and not ANIMAL.search(case["case_text"])
    ]
    # Um caso por artigo, para a amostra não ficar dominada por poucos artigos.
    sample = pd.DataFrame(rows).groupby("article_id").sample(n=1, random_state=args.seed)
    sample = sample.sample(n=min(args.n, len(sample)), random_state=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sample[FIELDS].sort_values("case_id").to_csv(
        args.output, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_NONNUMERIC
    )
    print(f"{len(sample)} casos extras gravados em {args.output}")


if __name__ == "__main__":
    main()
