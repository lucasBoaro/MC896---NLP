"""Protótipo da etapa 2: descobre termos clínicos com N-gramas + PMI e
classifica o tipo com Regressão Logística treinada por supervisão fraca
(rótulos = léxico V1). Avalia contra os 145 termos que a equipe adicionou
à mão na V2 (source=evaluation_v2).

Uso (a partir da raiz do repositório):
    python prototipo_ngramas.py <raiz_do_repo>
"""
import csv, math, re, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
STOP = set("""a an the of and or in on at to for with without by from as is was were be been
being has had have he she his her it its this that these those which who whom there their they
we our patient patients after before during than then also but not no into upon about over under
other any all some one two three four five six seven eight nine ten while because due revealed
showed shown demonstrated found noted performed presented admitted started given received
underwent diagnosed treated day days week weeks month months year years old history time
left right normal case report hospital follow up within further later initial initially
previous previously additional significant may did does do via per approximately both each
such well however years-old year-old female male woman man girl boy""".split())
TOKEN = re.compile(r"[A-Za-z][A-Za-z'\-]*[A-Za-z]|[A-Za-z]")

def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])|\n+", text) if s.strip()]

cases = list(csv.DictReader(open(ROOT / "data/processed/all_cases.csv", encoding="utf-8-sig")))
lex = lambda v: list(csv.DictReader(open(ROOT / f"resources/{v}/lexicon.csv", encoding="utf-8")))
v1 = {r["term"].lower(): r["type"] for r in lex("v1")}
gold = {r["term"].lower(): r["type"] for r in lex("v2") if r["source"] == "evaluation_v2"}

# 1) N-gramas (1..4) por frase, sem stopword nas bordas
freq, ctx, docs = Counter(), defaultdict(Counter), defaultdict(set)
uni = Counter()
for case in cases:
    for sent in sentences(case["case_text"]):
        toks = TOKEN.findall(sent)
        low = [t.lower() for t in toks]
        uni.update(low)
        for n in range(1, 5):
            for i in range(len(low) - n + 1):
                g = low[i:i + n]
                if g[0] in STOP or g[-1] in STOP or any(len(w) < 2 and not toks[i+j].isupper() for j, w in enumerate(g)):
                    continue
                term = " ".join(g)
                freq[term] += 1
                docs[term].add(case["case_id"])
                L = low[max(0, i - 2):i]; R = low[i + n:i + n + 2]
                for k, w in enumerate(reversed(L)): ctx[term][f"L{k+1}={w}"] += 1
                for k, w in enumerate(R): ctx[term][f"R{k+1}={w}"] += 1
                if L: ctx[term]["Lbi=" + " ".join(L)] += 1
                if R: ctx[term]["Rbi=" + " ".join(R)] += 1
                if toks[i].isupper() and len(toks[i]) > 1: ctx[term]["ACRONYM"] += 1

total = sum(uni.values())
def pmi(term):
    ws = term.split()
    if len(ws) == 1: return 0.0
    p = freq[term] / total
    return math.log2(p / np.prod([uni[w] / total for w in ws]))

cands = [t for t in freq if freq[t] >= 2 or t in v1 or (len(t.split()) == 1 and t.upper() == t)]
cands = [t for t in cands if not (len(t.split()) > 1 and pmi(t) < 3)]   # filtro de colocação
print(f"{len(freq)} n-gramas distintos -> {len(cands)} candidatos após frequência + PMI")

# 2) Features: n-gramas de caracteres do termo + contexto (n-gramas de palavras) + estatísticas
y = np.array([v1.get(t, "NONE") for t in cands])
chars = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)
Xc = chars.fit_transform(cands)
dv = DictVectorizer()
stats = []
for t in cands:
    d = {k: math.log1p(v) for k, v in ctx[t].items()}
    d.update(n_words=len(t.split()), log_freq=math.log1p(freq[t]), pmi=pmi(t) / 10,
             df=len(docs[t]) / len(cases))
    stats.append(d)
Xs = dv.fit_transform(stats)
X = hstack([Xc, Xs]).tocsr()

# 3) Cross-fitting: cada candidato é pontuado por um modelo que não o viu no treino
proba = np.zeros((len(cands), len(set(y))))
classes = None
for tr, te in StratifiedKFold(5, shuffle=True, random_state=42).split(X, y):
    clf = LogisticRegression(max_iter=3000, C=2.0, class_weight="balanced")
    clf.fit(X[tr], y[tr])
    classes = clf.classes_
    proba[te] = clf.predict_proba(X[te])
none = list(classes).index("NONE")
score = 1 - proba[:, none]
pred = [classes[i] for i in np.where(np.arange(len(classes)) == none, -1, proba).argmax(1)]

# 4) Avaliação: entre os candidatos NOVOS (fora da V1), recuperamos o que a equipe adicionou à mão?
new = [i for i, t in enumerate(cands) if t not in v1]
ranked = sorted(new, key=lambda i: -score[i])
gold_in = [g for g in gold if g in set(cands)]
print(f"Gold V2: {len(gold)} termos; {len(gold_in)} viraram candidatos (teto de recall)")
for k in (50, 100, 200, 400):
    top = ranked[:k]
    hits = [i for i in top if cands[i] in gold]
    typ = sum(pred[i] == gold[cands[i]] for i in hits)
    print(f"top-{k:<4} acertos gold={len(hits):3}  precisão@k(gold)={len(hits)/k:.2f}  "
          f"recall={len(hits)/len(gold):.2f}  tipo correto={typ}/{len(hits)}")

# validação cruzada nos próprios termos da V1 (classificação de tipo)
lab = [i for i, t in enumerate(cands) if t in v1]
acc = np.mean([pred[i] == y[i] for i in lab if score[i] > 0.5]) if lab else 0
print(f"V1 (cross-fit): {sum(score[i]>0.5 for i in lab)}/{len(lab)} reconhecidos, tipo correto {acc:.2f}")

out = Path(__file__).with_name("candidatos_v3.csv")
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["term", "pred_type", "score", "freq", "pmi", "in_v2_gold"])
    for i in ranked[:300]:
        w.writerow([cands[i], pred[i], f"{score[i]:.3f}", freq[cands[i]], f"{pmi(cands[i]):.2f}", cands[i] in gold])
print("top 40:", [f"{cands[i]}:{pred[i][:4]}" for i in ranked[:40]])
