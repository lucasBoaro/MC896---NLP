"""Planilha de revisão manual do top-100 de termos novos da V3.

Uso (a partir de project2/):
    python src/revisao_top100.py gerar     # cria outputs/evaluation/revisao_top100.csv
    python src/revisao_top100.py resumir   # calcula a precisão da planilha preenchida

Na coluna `avaliacao`, escreva: certo, errado ou tipo_errado (termo clínico, mas
com o tipo previsto errado). Em `tipo_correto`, para tipo_errado, escreva o tipo
certo (Symptom, Exam, Condition ou Treatment). `observacao` é livre.
"""
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "data/interim/ngram_candidates/candidatos_v3.csv"
SHEET = ROOT / "outputs/evaluation/revisao_top100.csv"
SUMMARY = ROOT / "outputs/evaluation/revisao_top100_resumo.csv"
TOP_K = 100
VALID = {"certo", "errado", "tipo_errado"}
COLUMNS = ["rank", "term", "pred_type", "score", "freq", "in_v2_gold",
           "avaliacao", "tipo_correto", "observacao"]


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def gerar():
    if SHEET.exists() and any(r["avaliacao"].strip() for r in read(SHEET)):
        sys.exit(f"{SHEET} já tem avaliações; apague-o antes de gerar de novo.")
    rows = []
    for rank, c in enumerate(read(CANDIDATES)[:TOP_K], start=1):
        rows.append({
            "rank": rank, "term": c["term"], "pred_type": c["pred_type"],
            "score": c["score"], "freq": c["freq"], "in_v2_gold": c["in_v2_gold"],
            "avaliacao": "", "tipo_correto": "", "observacao": "",
        })
    write(SHEET, rows, COLUMNS)
    print(f"{len(rows)} termos gravados em {SHEET}")


def resumir():
    rows = read(SHEET)
    evaluated = [r for r in rows if r["avaliacao"].strip()]
    invalid = [r for r in evaluated if r["avaliacao"].strip().lower() not in VALID]
    if invalid:
        sys.exit("Valores inválidos em avaliacao (linhas: "
                 + ", ".join(r["rank"] for r in invalid)
                 + "). Use: certo, errado, tipo_errado.")
    values = [r["avaliacao"].strip().lower() for r in evaluated]
    n = len(evaluated)
    if n == 0:
        sys.exit("Nenhuma linha avaliada.")
    clinical = sum(v in ("certo", "tipo_errado") for v in values)
    right_type = sum(v == "certo" for v in values)

    by_type = defaultdict(Counter)
    for r, v in zip(evaluated, values):
        by_type[r["pred_type"]][v] += 1

    out = [
        {"grupo": "todos", "avaliados": n, "termo_clinico": clinical,
         "tipo_correto": right_type, "precisao_termo": round(clinical / n, 4),
         "precisao_tipo": round(right_type / n, 4)},
    ]
    for t in sorted(by_type):
        c = by_type[t]
        total = sum(c.values())
        clin = c["certo"] + c["tipo_errado"]
        out.append({"grupo": t, "avaliados": total, "termo_clinico": clin,
                    "tipo_correto": c["certo"], "precisao_termo": round(clin / total, 4),
                    "precisao_tipo": round(c["certo"] / total, 4)})
    write(SUMMARY, out, list(out[0].keys()))
    print(f"Avaliados: {n} de {len(rows)}")
    for r in out:
        print(f"{r['grupo']:10} avaliados={r['avaliados']:3} "
              f"termo clínico={r['precisao_termo']:.2f} tipo correto={r['precisao_tipo']:.2f}")
    print(f"Gravado em {SUMMARY}")


if __name__ == "__main__":
    commands = {"gerar": gerar, "resumir": resumir}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit(__doc__)
    commands[sys.argv[1]]()
