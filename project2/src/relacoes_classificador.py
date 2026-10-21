"""Gera o grafo com TREATS e INDICATES decididos pelo Naive Bayes.

O build_graph.py só cria TREATS e INDICATES quando acha um gatilho escrito à mão,
e por isso perde a maior parte das relações. Este script roda o extrator, toma
cada par tratamento-condição ou exame-condição da mesma frase (relacoes_pmi.py)
e cria a aresta quando a regra já a criou ou quando o Naive Bayes diz que ela
existe.

O Naive Bayes é treinado só nos pares rotulados à mão dos casos de
desenvolvimento. O limiar de cada relação é escolhido por validação cruzada
nesses mesmos pares; os casos de avaliação ficam de fora do treino e do limiar.

Uso (a partir da pasta project2/):
    python src/relacoes_classificador.py --input data/processed/all_cases.csv \\
        --lexicon resources/v3_mais_dados/lexicon.csv \\
        --nodes outputs/full/v3_mais_dados/nodes.csv \\
        --edges outputs/full/v3_mais_dados/edges.csv
"""

import argparse
from pathlib import Path
import sys

import numpy as np
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import relacoes_pmi as rp  # noqa: E402

THRESHOLDS = np.arange(0.5, 0.96, 0.05)


def dev_training_pairs():
    """Pares rotulados à mão dos casos de desenvolvimento, por relação."""
    dev = {
        c["case_id"] for c in rp.read_csv(rp.CASES_PATH)
        if c["split"] == "development"
    }
    gold = {
        r["pair_id"]: int(r["gold"])
        for r in rp.read_csv(rp.LABELS_PATH)
        if r["gold"].strip() in {"0", "1"}
    }
    pairs = [
        p for p in rp.read_csv(rp.PAIRS_PATH)
        if p["pair_id"] in gold and p["case_id"] in dev
    ]
    return {
        relation: (
            [p for p in pairs if p["relation"] == relation],
            np.array([gold[p["pair_id"]] for p in pairs if p["relation"] == relation]),
        )
        for relation in set(rp.PAIR_TYPES.values())
    }


def choose_threshold(pairs, y):
    """Limiar de maior F1 na validação cruzada agrupada por caso."""
    groups = [p["case_id"] for p in pairs]
    scores = np.zeros(len(pairs))
    folds = GroupKFold(n_splits=min(rp.N_FOLDS, len(set(groups))))
    for train, test in folds.split(pairs, y, groups):
        _, scores[test] = rp.fit_predict(
            "naive_bayes", [pairs[i] for i in train], y[train], [pairs[i] for i in test]
        )
    return max(THRESHOLDS, key=lambda t: (rp.f1(y, (scores >= t).astype(int)), t))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/all_cases.csv")
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--triggers", type=Path, default=ROOT / "resources/v1/triggers.csv")
    parser.add_argument("--nodes", type=Path, required=True)
    parser.add_argument("--edges", type=Path, required=True)
    args = parser.parse_args(argv)

    cases = rp.read_csv(args.input)
    lexicon = rp.bg.prepare_entries(rp.read_csv(args.lexicon), "term")
    triggers = rp.bg.prepare_entries(rp.read_csv(args.triggers), "phrase")
    nodes, edges = rp.bg.build_graph(cases, lexicon, triggers)
    pairs = rp.build_pairs(cases, lexicon, triggers)

    existing = {(e["source_id"], e["target_id"], e["relation"]) for e in edges}
    seen = set()
    added = 0
    for relation, (train, y) in sorted(dev_training_pairs().items()):
        threshold = choose_threshold(train, y)
        candidates = [p for p in pairs if p["relation"] == relation]
        if not candidates:
            continue
        _, scores = rp.fit_predict("naive_bayes", train, y, candidates)
        new = 0
        for pair, score in zip(candidates, scores):
            # Duas menções do mesmo termo na frase não viram duas arestas.
            key = (pair["case_id"], pair["source"].lower(), pair["target"].lower(),
                   relation, pair["sentence"])
            ids = (pair["source_id"], pair["target_id"], relation)
            if score < threshold or key in seen or ids in existing:
                continue
            seen.add(key)
            edges.append({
                "edge_id": f"edge_{len(edges) + 1:06d}",
                "case_id": pair["case_id"],
                "source_id": pair["source_id"],
                "target_id": pair["target_id"],
                "relation": relation,
                "attributes": {"method": "naive_bayes", "score": round(float(score), 3)},
                "evidence": pair["sentence"],
            })
            new += 1
        added += new
        print(
            f"{relation}: limiar {threshold:.2f}, {len(candidates)} pares, "
            f"{new} arestas novas do Naive Bayes"
        )

    rp.bg.write_records(args.nodes, nodes, rp.bg.NODE_FIELDS)
    rp.bg.write_records(args.edges, edges, rp.bg.EDGE_FIELDS)
    print(f"{len(nodes)} nós, {len(edges)} arestas ({added} do Naive Bayes)")


if __name__ == "__main__":
    main()
