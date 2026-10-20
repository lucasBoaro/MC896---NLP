"""Experimentos de variação da V3 com várias sementes (plano final, seção 3.3).

Repete o treino do classificador de tipo com diferentes componentes e modelos e
reporta média e desvio, para saber se uma diferença é real ou só ruído de uma semente.
Usa só os 45 casos de desenvolvimento (importa o pipeline de prototipo_ngramas.py).

Uso (a partir de project2/): python src/experimentos.py
Saída: outputs/evaluation/experimentos.csv
"""
import contextlib
import csv
import io
import statistics
import warnings

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.neural_network import MLPClassifier

with contextlib.redirect_stdout(io.StringIO()):  # silencia os prints do pipeline
  import prototipo_ngramas as P

SEEDS = range(10)
STAT_KEYS = {"n_words", "log_freq", "pmi", "npmi", "df"}
METRICS = ("auc_v1_vs_none", "v1_recognized", "type_acc", "gold_top400", "gold_top400_type")

# Matrizes de características por componente (índices globais de P.cands).
Xc = P.Xc
Xctx = DictVectorizer().fit_transform(
    [{k: v for k, v in d.items() if k not in STAT_KEYS} for d in P.stats]
)
Xst = DictVectorizer().fit_transform(
    [{k: v for k, v in d.items() if k in STAT_KEYS} for d in P.stats]
)
FEATURES = {
    "chars+ctx+stats": hstack([Xc, Xctx, Xst]).tocsr(),
    "chars": Xc.tocsr(),
    "chars+stats": hstack([Xc, Xst]).tocsr(),
    "ctx+stats": hstack([Xctx, Xst]).tocsr(),
    "stats": Xst.tocsr(),
}
N_WORDS = np.array([len(t.split()) for t in P.cands])


def make_model(kind, seed):
  if kind == "nb":
    return MultinomialNB()
  if kind == "mlp":
    return MLPClassifier(hidden_layer_sizes=(32,), max_iter=300, random_state=seed)
  return LogisticRegression(max_iter=3000, C=2.0, class_weight="balanced")


# nome -> (características, modelo, máximo de palavras do candidato)
VARIANTS = {
    "base (lr, chars+ctx+stats, ate 4 palavras)": ("chars+ctx+stats", "lr", 4),
    "so caracteres": ("chars", "lr", 4),
    "sem contexto (chars+stats)": ("chars+stats", "lr", 4),
    "sem caracteres (ctx+stats)": ("ctx+stats", "lr", 4),
    "so estatisticas": ("stats", "lr", 4),
    "naive bayes": ("chars+ctx+stats", "nb", 4),
    "mlp pequeno": ("chars+ctx+stats", "mlp", 4),
    "so unigramas": ("chars+ctx+stats", "lr", 1),
    "ate bigramas": ("chars+ctx+stats", "lr", 2),
    "ate trigramas": ("chars+ctx+stats", "lr", 3),
}


def fit_proba(model, X_tr, y_tr, X_te, classes):
  """predict_proba alinhado a `classes`, mesmo se o treino perder alguma classe."""
  model.fit(X_tr, y_tr)
  out = np.zeros((X_te.shape[0], len(classes)))
  for j, c in enumerate(model.classes_):
    out[:, list(classes).index(c)] = model.predict_proba(X_te)[:, j]
  return out


def run(feature_name, kind, max_n, seed):
  X = FEATURES[feature_name]
  if kind == "nb":
    X = X.maximum(0)  # Naive Bayes multinomial exige valores não negativos
  sel = N_WORDS <= max_n
  known = np.array([i for i in P.known_idx if sel[i]])
  unk = np.array([i for i in P.unk_idx if sel[i]], dtype=int)
  y = P.labels[known]
  classes = np.unique(y)
  if "NONE" not in classes or len(classes) < 2:
    return None
  none_col = list(classes).index("NONE")
  proba = np.zeros((len(P.cands), len(classes)))
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(known, y):
      proba[known[te]] = fit_proba(
          make_model(kind, seed), X[known[tr]], y[tr], X[known[te]], classes
      )
    if len(unk) > 0:
      proba[unk] = fit_proba(make_model(kind, seed), X[known], y, X[unk], classes)

  score = 1.0 - proba[:, none_col]
  masked = proba.copy()
  masked[:, none_col] = -1
  pred = classes[masked.argmax(1)]

  is_v1 = np.array([P.labels[i] not in ("NONE", "UNK") for i in known])
  auc = roc_auc_score(is_v1, score[known]) if is_v1.any() and not is_v1.all() else float("nan")
  v1_idx = [i for i in known if P.cands[i] in P.v1]
  recognized = [i for i in v1_idx if score[i] > 0.5]
  type_acc = (
      float(np.mean([pred[i] == P.labels[i] for i in recognized])) if recognized else float("nan")
  )
  new_idx = [i for i in range(len(P.cands)) if sel[i] and P.cands[i] not in P.v1]
  ranked = P.filter_sub_ngrams(sorted(new_idx, key=lambda i: -score[i]))
  hits = [
      i for i in ranked[:400]
      if P.cands[i] in P.gold or P.split_acronym(P.cands[i])[0] in P.gold
  ]
  right = sum(
      pred[i] == P.gold.get(P.cands[i], P.gold.get(P.split_acronym(P.cands[i])[0]))
      for i in hits
  )
  return {
      "auc_v1_vs_none": auc,
      "v1_recognized": len(recognized) / len(v1_idx) if v1_idx else float("nan"),
      "type_acc": type_acc,
      "gold_top400": len(hits),
      "gold_top400_type": right,
  }


def main():
  rows = []
  for name, (feature_name, kind, max_n) in VARIANTS.items():
    results = [r for r in (run(feature_name, kind, max_n, s) for s in SEEDS) if r]
    row = {"variant": name, "seeds": len(results)}
    for m in METRICS:
      vals = [r[m] for r in results if r[m] == r[m]]  # descarta NaN
      row[m + "_mean"] = round(statistics.mean(vals), 4) if vals else ""
      row[m + "_std"] = round(statistics.pstdev(vals), 4) if len(vals) > 1 else ""
    rows.append(row)
    print(
        f"{name:45} auc={row['auc_v1_vs_none_mean']}±{row['auc_v1_vs_none_std']} "
        f"v1={row['v1_recognized_mean']} tipo={row['type_acc_mean']} "
        f"ouro400={row['gold_top400_mean']}"
    )
  out = P.ROOT / "outputs" / "evaluation" / "experimentos.csv"
  with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
  print(f"Gravado em {out}")


if __name__ == "__main__":
  main()
