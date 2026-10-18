"""Etapa 2 (Núcleo V3): descobre termos clínicos com N-gramas + PMI/NPMI e
classifica o tipo com Regressão Logística treinada por supervisão fraca
(positivos = léxico V1; negativos confiáveis = termos não-clínicos/baixo NPMI).

Minera candidatos apenas fora do conjunto de avaliação (sem data leakage),
normaliza siglas e sub-n-gramas, avalia contra os 145 termos da V2
(source=evaluation_v2) e exporta resources/v3/lexicon.csv para o build_graph.py.

Uso (a partir da pasta fase2/):
    python src/prototipo_ngramas.py
Saídas:
    - data/interim/ngram_candidates/candidatos_v3.csv
    - resources/v3/lexicon.csv
"""

from collections import Counter, defaultdict
import csv
import math
from pathlib import Path
import re
import sys

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

ROOT = (
    Path(sys.argv[1])
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[1]
)
OUT_DIR = ROOT / "data" / "interim" / "ngram_candidates"

# 1) Stopwords expandidas (bordas e interior dos n-gramas)
STOP = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "with",
    "without",
    "by",
    "from",
    "as",
    "is",
    "was",
    "were",
    "be",
    "been",
    "being",
    "has",
    "had",
    "have",
    "he",
    "she",
    "his",
    "her",
    "it",
    "its",
    "this",
    "that",
    "these",
    "those",
    "which",
    "who",
    "whom",
    "there",
    "their",
    "they",
    "we",
    "our",
    "patient",
    "patients",
    "after",
    "before",
    "during",
    "than",
    "then",
    "also",
    "but",
    "not",
    "no",
    "into",
    "upon",
    "about",
    "over",
    "under",
    "other",
    "any",
    "all",
    "some",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "while",
    "because",
    "due",
    "revealed",
    "showed",
    "shown",
    "demonstrated",
    "found",
    "noted",
    "performed",
    "presented",
    "admitted",
    "started",
    "given",
    "received",
    "underwent",
    "diagnosed",
    "treated",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "year",
    "years",
    "old",
    "history",
    "time",
    "left",
    "right",
    "normal",
    "case",
    "report",
    "hospital",
    "follow",
    "up",
    "within",
    "further",
    "later",
    "initial",
    "initially",
    "previous",
    "previously",
    "additional",
    "significant",
    "may",
    "did",
    "does",
    "do",
    "via",
    "per",
    "approximately",
    "both",
    "each",
    "such",
    "well",
    "however",
    "years-old",
    "year-old",
    "female",
    "male",
    "woman",
    "man",
    "girl",
    "boy",
    # Stopwords extras (meses, verbos narrativos, unidades de medida)
    "january",
    "february",
    "march",
    "april",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "made",
    "make",
    "show",
    "shows",
    "reveals",
    "ancient",
    "repeat",
    "mg",
    "ml",
    "dl",
    "kg",
    "cm",
    "mm",
    "showing",
    "including",
    "include",
    "included",
    "severe",
    "mild",
    "moderate",
    # Dose e via de administração (ajustadas olhando só os 45 casos de desenvolvimento)
    "dose",
    "doses",
    "dosage",
    "tablet",
    "tablets",
    "orally",
    "interest",
    "individual",
}

""" Unigrama novo (fora da V1) só vira candidato com sinal morfológico clínico, em vez de
uma lista de bloqueio: o PMI não existe para uma palavra solta, então sem este 
critério qualquer palavra genérica (size, weight, active) entra no léxico.
"""
CLINICAL_SUFFIXES = (
    "itis", "emia", "aemia", "penia", "oma", "pathy", "osis", "algia", "uria",
    "scopy", "ectomy", "ostomy", "otomy", "plasty", "graphy", "gram",
    "rrhagia", "rrhea", "megaly", "asthma",
)
MIN_FREQ_UNIGRAM = 3  # unigramas fora da V1 precisam aparecer ao menos 3 vezes
# Preposições/conjunções permitidas no meio de termos médicos
ALLOWED_INNER_STOP = {"of", "in", "on", "to", "with", "and", "or"}

# Termos narrativos/gerais para construir o conjunto de negativos confiáveis (NONE)
NON_CLINICAL_WORDS = {
    "normal",
    "patient",
    "patients",
    "history",
    "hospital",
    "admitted",
    "day",
    "days",
    "year",
    "years",
    "old",
    "male",
    "female",
    "right",
    "left",
    "time",
    "initial",
    "previous",
    "report",
    "case",
    "showed",
    "revealed",
    "performed",
    "noted",
    "found",
    "given",
    "started",
    "received",
    "treated",
    "diagnosed",
    "underwent",
    "follow",
    "week",
    "weeks",
    "month",
    "months",
    "first",
    "second",
    "third",
    "two",
    "three",
    "four",
    "five",
    "daily",
    "twice",
    "hours",
    "hour",
    "minute",
    "minutes",
    "level",
    "levels",
    "value",
    "values",
    "result",
    "results",
    "finding",
    "findings",
    "examination",
    "test",
    "tests",
    "study",
    "studies",
    "figure",
    "table",
    "department",
    "clinic",
    "unit",
    "care",
    "admission",
    "discharge",
    "course",
}

TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]")


def sentences(text):
  return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n+", text) if s.strip()]


def read_csv(path, encoding="utf-8"):
  with open(path, encoding=encoding, newline="") as f:
    return list(csv.DictReader(f))


def lex(v):
  return read_csv(ROOT / f"resources/{v}/lexicon.csv")


# 2) Carregamento sem Data Leakage (Seção 2.1):
# Isola os 11 casos de avaliação e minera no restante (todos os casos externos ou development.csv)
eval_path = ROOT / "data/processed/evaluation.csv"
eval_ids = (
    {r["case_id"] for r in read_csv(eval_path, encoding="utf-8-sig")}
    if eval_path.exists()
    else set()
)

ext_cases_path = ROOT / "data/external/cases.csv"
if ext_cases_path.exists():
  raw_cases = read_csv(ext_cases_path, encoding="utf-8-sig")
  cases = [c for c in raw_cases if c["case_id"] not in eval_ids]
else:
  cases = read_csv(ROOT / "data/processed/development.csv", encoding="utf-8-sig")

print(
    f"Casos usados na mineração: {len(cases)} (excluídos {len(eval_ids)} casos"
    " de avaliação)"
)

v1_rows = lex("v1")
v1 = {r["term"].lower(): r["type"] for r in v1_rows}
gold = {
    r["term"].lower(): r["type"]
    for r in lex("v2")
    if r.get("source") == "evaluation_v2"
}

# 3) Extração de N-gramas (1..4) por frase, bloqueando stopwords nas bordas e verbos no interior
freq, ctx, docs = Counter(), defaultdict(Counter), defaultdict(set)
uni = Counter()
ACRONYMS = set()  # siglas (2 a 6 letras maiúsculas) vistas no corpus de mineração

for case in cases:
  for sent in sentences(case["case_text"]):
    toks = TOKEN.findall(sent)
    low = [t.lower() for t in toks]
    uni.update(low)
    ACRONYMS.update(t.lower() for t in toks if t.isupper() and 2 <= len(t) <= 6)
    for n in range(1, 5):
      for i in range(len(low) - n + 1):
        g = low[i : i + n]
        # Bloqueia stopwords nas pontas
        if g[0] in STOP or g[-1] in STOP:
          continue
        # Bloqueia stopwords no interior (exceto preposições médicas permitidas)
        if any((w in STOP and w not in ALLOWED_INNER_STOP) for w in g[1:-1]):
          continue
        # Bloqueia tokens de 1 letra que não sejam letra maiúscula
        if any(
            len(w) < 2 and not toks[i + j].isupper() for j, w in enumerate(g)
        ):
          continue

        term = " ".join(g)
        freq[term] += 1
        docs[term].add(case["case_id"])

        L = low[max(0, i - 2) : i]
        R = low[i + n : i + n + 2]
        for k, w in enumerate(reversed(L)):
          ctx[term][f"L{k+1}={w}"] += 1
        for k, w in enumerate(R):
          ctx[term][f"R{k+1}={w}"] += 1
        if L:
          ctx[term]["Lbi=" + " ".join(L)] += 1
        if R:
          ctx[term]["Rbi=" + " ".join(R)] += 1
        if toks[i].isupper() and len(toks[i]) > 1:
          ctx[term]["ACRONYM"] += 1

total = sum(uni.values())


# 4) Medidas de associação (Seção 2.3): PMI e NPMI (normalizado pelo comprimento do n-grama)
def pmi(term):
  ws = term.split()
  if len(ws) == 1:
    return 0.0
  p = freq[term] / total
  denom = np.prod([uni[w] / total for w in ws])
  return math.log2(p / denom) if denom > 0 and p > 0 else 0.0


def npmi(term):
  ws = term.split()
  if len(ws) == 1:
    return 0.0
  p = freq[term] / total
  if p <= 0 or p >= 1:
    return 0.0
  return pmi(term) / (-math.log2(p) * (len(ws) - 1))


# Filtro de candidatos: frequência mínima e colocação (PMI >= 3 e NPMI >= 0.30 para multipalavras)
cands = [
    t
    for t in freq
    if freq[t] >= 2
    or t in v1
    or (len(t.split()) == 1 and "ACRONYM" in ctx[t] and freq[t] >= 2)
]
# Unigramas fora da V1: frequência mínima maior e sem palavras genéricas
cands = [
    t
    for t in cands
    if t in v1
    or len(t.split()) > 1
    or (
        freq[t] >= MIN_FREQ_UNIGRAM
        and t.endswith(CLINICAL_SUFFIXES)
        and t not in NON_CLINICAL_WORDS
    )
]
cands = [
    t
    for t in cands
    if t in v1 or len(t.split()) == 1 or (pmi(t) >= 3.0 and npmi(t) >= 0.30)
]
print(
    f"{len(freq)} n-gramas distintos -> {len(cands)} candidatos após filtro de"
    " frequência + PMI/NPMI"
)

# 5) Features: n-gramas de caracteres + contexto + estatísticas
chars = TfidfVectorizer(
    analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True
)
Xc = chars.fit_transform(cands)

dv = DictVectorizer()
stats = []
for t in cands:
  d = {k: math.log1p(v) for k, v in ctx[t].items()}
  d.update(
      n_words=len(t.split()),
      log_freq=math.log1p(freq[t]),
      pmi=pmi(t) / 10.0,
      npmi=npmi(t),
      df=len(docs[t]) / len(cases),
  )
  stats.append(d)
Xs = dv.fit_transform(stats)
X = hstack([Xc, Xs]).tocsr()


# 6) Supervisão Fraca sem poluir positivos ocultos (Seção 2.2):
# Separa V1 (positivos), NONE confiáveis (negativos) e UNK (desconhecidos para ranquear)
def get_weak_label(t):
  if t in v1:
    return v1[t]
  ws = set(t.split())
  # Negativo confiável: contém palavra claramente narrativa/geral ou associação fraca
  if (ws & NON_CLINICAL_WORDS) or (len(ws) > 1 and npmi(t) < 0.38):
    return "NONE"
  return "UNK"


labels = np.array([get_weak_label(t) for t in cands])
known_idx = np.where(labels != "UNK")[0]
unk_idx = np.where(labels == "UNK")[0]

# Fallback de segurança caso o conjunto de NONE confiáveis fique muito pequeno
if sum(labels[known_idx] == "NONE") < 30:
  labels = np.array([v1.get(t, "NONE") for t in cands])
  known_idx = np.arange(len(cands))
  unk_idx = np.array([], dtype=int)

y_known = labels[known_idx]
X_known = X[known_idx]
classes = np.unique(y_known)
proba = np.zeros((len(cands), len(classes)))

# Cross-fitting nos candidatos conhecidos (V1 + NONE confiável)
for tr, te in StratifiedKFold(5, shuffle=True, random_state=42).split(
    X_known, y_known
):
  clf = LogisticRegression(max_iter=3000, C=2.0, class_weight="balanced")
  clf.fit(X_known[tr], y_known[tr])
  proba[known_idx[te]] = clf.predict_proba(X_known[te])

# Treina em todos os conhecidos para pontuar os candidatos desconhecidos (UNK)
if len(unk_idx) > 0:
  clf_full = LogisticRegression(max_iter=3000, C=2.0, class_weight="balanced")
  clf_full.fit(X_known, y_known)
  proba[unk_idx] = clf_full.predict_proba(X[unk_idx])

none_col = list(classes).index("NONE")
score = 1.0 - proba[:, none_col]
pred = [
    classes[i]
    for i in np.where(np.arange(len(classes)) == none_col, -1, proba).argmax(1)
]


# 7) Normalização de Termo + Sigla e Sub-N-gramas (Seção 2.4)
def split_acronym(term):
  """Separa 'acute coronary syndrome acs' em ('acute coronary syndrome', 'acs')."""
  ws = term.split()
  if len(ws) >= 3:
    initials = "".join(w[0] for w in ws[:-1])
    if ws[-1] == initials:
      return " ".join(ws[:-1]), ws[-1]
  # Sigla escrita em maiúsculas no texto, com as letras na ordem do termo
  # (ex: 'esophagogastroduodenoscopy egd'); exige 3+ letras para não separar 'chest ct'
  if len(ws) >= 2 and ws[-1] in ACRONYMS and len(ws[-1]) >= 3:
    base = " ".join(ws[:-1])
    letters = iter(base.replace(" ", ""))
    if base[0] == ws[-1][0] and all(c in letters for c in ws[-1]):
      return base, ws[-1]
  return term, None


def filter_sub_ngrams(ranked_indices, max_ratio=0.80):
  """Descarta sub-n-gramas que quase sempre ocorrem apenas dentro de um n-grama maior melhor ranqueado (C-value)."""
  kept = []
  accepted_multi = []
  for idx in ranked_indices:
    t = cands[idx]
    # Se 't' for substring por palavra de um termo maior já aceito e tiver quase a mesma frequência, é redundante
    is_sub = False
    for longer in accepted_multi:
      if f" {t} " in f" {longer} " and freq[t] > 0:
        if (freq[longer] / freq[t]) >= max_ratio:
          is_sub = True
          break
    if not is_sub:
      kept.append(idx)
      if len(t.split()) >= 2:
        accepted_multi.append(t)
  return kept


# 8) Avaliação contra o gabarito V2 (145 termos adicionados na avaliação do Projeto 1)
new_raw = [i for i, t in enumerate(cands) if t not in v1]
ranked_raw = sorted(new_raw, key=lambda i: -score[i])
ranked = filter_sub_ngrams(ranked_raw)

gold_in = [g for g in gold if g in set(cands)]
print(
    f"Gold V2: {len(gold)} termos; {len(gold_in)} viraram candidatos (teto de"
    " recall no corpus de treino)"
)
for k in (50, 100, 200, 400):
  top = ranked[:k]
  hits = [
      i
      for i in top
      if cands[i] in gold or split_acronym(cands[i])[0] in gold
  ]
  typ = sum(
      pred[i] == gold.get(cands[i], gold.get(split_acronym(cands[i])[0]))
      for i in hits
  )
  print(
      f"top-{k:<4} acertos gold={len(hits):3} "
      f" precisão@k(gold)={len(hits)/k:.2f}  recall={len(hits)/len(gold):.2f} "
      f" tipo correto={typ}/{len(hits)}"
  )

lab = [i for i, t in enumerate(cands) if t in v1]
acc = np.mean([pred[i] == labels[i] for i in lab if score[i] > 0.5]) if lab else 0
print(
    f"V1 (cross-fit): {sum(score[i] > 0.5 for i in lab)}/{len(lab)}"
    f" reconhecidos, tipo correto {acc:.2f}"
)

# 9) Salva candidatos intermediários para inspeção manual
out = OUT_DIR / "candidatos_v3.csv"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="", encoding="utf-8") as f:
  w = csv.writer(f)
  w.writerow(
      ["term", "pred_type", "score", "freq", "pmi", "npmi", "in_v2_gold"]
  )
  for i in ranked[:400]:
    base_t, _ = split_acronym(cands[i])
    in_gold = (cands[i] in gold) or (base_t in gold)
    w.writerow([
        cands[i],
        pred[i],
        f"{score[i]:.3f}",
        freq[cands[i]],
        f"{pmi(cands[i]):.2f}",
        f"{npmi(cands[i]):.2f}",
        in_gold,
    ])
print(f"Candidatos intermediários salvos em {out}")

# 10) Exporta o léxico final V3 (resources/v3/lexicon.csv) compatível com src/build_graph.py
v3_dir = ROOT / "resources" / "v3"
v3_dir.mkdir(parents=True, exist_ok=True)
v3_lex_path = v3_dir / "lexicon.csv"

fieldnames = list(v1_rows[0].keys()) if v1_rows else ["term", "type", "canonical"]
v3_rows = list(v1_rows)
seen_terms = {r["term"].lower() for r in v1_rows}

TOP_K_V3 = 250  # Quantidade máxima de novos conceitos aprendidos para compor a V3
MIN_SCORE_V3 = 0.65  # Limiar mínimo de confiança do classificador

added_count = 0
for i in ranked:
  if added_count >= TOP_K_V3 or score[i] < MIN_SCORE_V3:
    break
  raw_term = cands[i]
  base_term, acr = split_acronym(raw_term)
  ptype = pred[i]

  if base_term not in seen_terms:
    row = {"term": base_term, "type": ptype, "canonical": base_term}
    if "source" in fieldnames:
      row["source"] = "learned_v3"
    v3_rows.append(row)
    seen_terms.add(base_term)
    added_count += 1

  if acr and acr not in seen_terms:
    row_acr = {"term": acr, "type": ptype, "canonical": base_term}
    if "source" in fieldnames:
      row_acr["source"] = "learned_v3_acronym"
    v3_rows.append(row_acr)
    seen_terms.add(acr)

with open(v3_lex_path, "w", newline="", encoding="utf-8") as f:
  writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
  writer.writeheader()
  writer.writerows(v3_rows)

print(
    f"Léxico V3 salvo em {v3_lex_path} ({len(v1_rows)} termos V1 +"
    f" {len(v3_rows) - len(v1_rows)} novos = {len(v3_rows)} total)"
)
print("Top 40 novos:", [f"{cands[i]}:{pred[i][:4]}" for i in ranked[:40]])