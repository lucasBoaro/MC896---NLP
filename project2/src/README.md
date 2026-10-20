# Código da entrega 2 (`src/`)

Esta pasta contém o extrator do Projeto 1, sem alterações, e os scripts da entrega 2 que aprendem o léxico V3, classificam relações e fases e avaliam os resultados.

## Scripts

| Arquivo | Função | Principais saídas |
|---|---|---|
| [`prepare_data.py`](prepare_data.py) | Relaciona casos e artigos e separa os 45 casos de desenvolvimento dos 11 de avaliação (igual ao Projeto 1). | `data/processed/*.csv` |
| [`build_graph.py`](build_graph.py) | Extrator do Projeto 1: gera nós e arestas a partir de um léxico e de gatilhos. Não foi alterado. | `outputs/*/<versão>/nodes.csv` e `edges.csv` |
| [`prototipo_ngramas.py`](prototipo_ngramas.py) | Léxico V3: n-gramas, PMI e NPMI, supervisão fraca e regressão logística. | `resources/v3/lexicon.csv`, `data/interim/ngram_candidates/candidatos_v3.csv`, `outputs/evaluation/association_auc.csv` |
| [`sample_multicare.py`](sample_multicare.py) | Sorteia 1000 casos extras do MultiCaRe para a V3+. Requer `pandas` e `pyarrow`. | `data/external/cases_extra.csv` |
| [`relacoes_classificador.py`](relacoes_classificador.py) | Gera o grafo da V3+ com `TREATS` e `INDICATES` decididos pelo Naive Bayes. | `outputs/*/v3_mais_dados/` |
| [`relacoes_pmi.py`](relacoes_pmi.py) | Gera a planilha dos pares de relação e compara regras, gatilhos por PMI, NPMI, Naive Bayes e regressão logística. | `data/interim/relations/`, `outputs/evaluation/relacoes_*.csv`, `resources/v3/triggers_aprendidos.csv` |
| [`fases_temporais.py`](fases_temporais.py) | Classifica a fase do relato de cada evento (regras + regressão logística). | atributos `phase*` em `nodes.csv`, `outputs/evaluation/fases/<versão>/`, `data/interim/fases/<versão>/rotulagem_fases.csv` |
| [`compare_versions.py`](compare_versions.py) | Conta entidades e relações de cada versão nos 11 casos de avaliação. | `outputs/evaluation/comparison.csv` |
| [`evaluate_lexicon.py`](evaluate_lexicon.py) | Mede quanto a V3 recupera dos termos que a V2 acrescentou à mão. | `outputs/evaluation/lexicon_recall.csv`, `lexicon_pr_curve.csv` |
| [`experimentos.py`](experimentos.py) | Variações do classificador do léxico, com 10 repetições. | `outputs/evaluation/experimentos.csv` |
| [`revisao_top100.py`](revisao_top100.py) | Planilha de revisão manual dos 100 primeiros termos aprendidos. | `outputs/evaluation/revisao_top100.csv` |
| [`visualize_graph.py`](visualize_graph.py) | Gera o explorador HTML com todas as versões. | `outputs/explorador.html` |

## Instalação

Python 3.12. O extrator, a visualização e os testes usam só a biblioteca padrão; o aprendizado usa `numpy`, `scipy` e `scikit-learn`.

```powershell
cd project2
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Para sortear os casos extras da V3+ também é preciso `pip install pandas pyarrow` e o arquivo `cases.parquet` do MultiCaRe (Zenodo, doi 10.5281/zenodo.10079370).

## Execução

Todos os comandos são executados no PowerShell, a partir da pasta `project2`. Os dados processados, os léxicos e as saídas já estão versionados, então cada passo pode ser executado isoladamente.

### 1. Preparar os dados

```powershell
python src/prepare_data.py
```

### 2. Aprender o léxico V3

```powershell
python src/prototipo_ngramas.py
```

Cria `resources/v3/lexicon.csv` (a V1 acrescida dos termos aprendidos, com `source` igual a `learned_v3`), `data/interim/ngram_candidates/candidatos_v3.csv` (todos os candidatos, com tipo previsto, score, frequência, PMI e NPMI) e `outputs/evaluation/association_auc.csv`.

### 3. Extrair os grafos V1, V2 e V3

A V1 e a V3 usam os gatilhos da V1; a V2 usa os seus. Para os 11 casos de avaliação:

```powershell
python -m src.build_graph --input data/processed/evaluation.csv --lexicon resources/v1/lexicon.csv --triggers resources/v1/triggers.csv --nodes outputs/evaluation/v1/nodes.csv --edges outputs/evaluation/v1/edges.csv
python -m src.build_graph --input data/processed/evaluation.csv --lexicon resources/v2/lexicon.csv --triggers resources/v2/triggers.csv --nodes outputs/evaluation/v2/nodes.csv --edges outputs/evaluation/v2/edges.csv
python -m src.build_graph --input data/processed/evaluation.csv --lexicon resources/v3/lexicon.csv --triggers resources/v1/triggers.csv --nodes outputs/evaluation/v3/nodes.csv --edges outputs/evaluation/v3/edges.csv
```

Para os 56 casos, troque `--input` por `data/processed/all_cases.csv` e `outputs/evaluation` por `outputs/full`.

### 4. V3+: mais dados e relações pelo Naive Bayes

```powershell
python src/sample_multicare.py CAMINHO/cases.parquet --n 1000
$env:NGRAM_SUFFIX_TYPES = "1"; $env:NGRAM_EXTRA_CASES = "data/external/cases_extra.csv"; $env:NGRAM_TAG = "v3_mais_dados"; $env:NGRAM_TOP_K = "500"
python src/prototipo_ngramas.py
Remove-Item Env:NGRAM_SUFFIX_TYPES, Env:NGRAM_EXTRA_CASES, Env:NGRAM_TAG, Env:NGRAM_TOP_K
python src/relacoes_classificador.py --input data/processed/all_cases.csv --lexicon resources/v3_mais_dados/lexicon.csv --nodes outputs/full/v3_mais_dados/nodes.csv --edges outputs/full/v3_mais_dados/edges.csv
python src/relacoes_classificador.py --input data/processed/evaluation.csv --lexicon resources/v3_mais_dados/lexicon.csv --nodes outputs/evaluation/v3_mais_dados/nodes.csv --edges outputs/evaluation/v3_mais_dados/edges.csv
```

O `Remove-Item` limpa as variáveis para que uma nova execução do passo 2 volte a gerar a V3.

### 5. Classificar a fase dos eventos

Depois do passo 3 (rode de novo se o `build_graph.py` for executado outra vez):

```powershell
python src/fases_temporais.py --version v1
python src/fases_temporais.py --version v2
python src/fases_temporais.py --version v3
```

Acrescenta `phase`, `phase_source` (`regra` ou `modelo`), `phase_score` e `phase_cue` aos atributos dos nós de `outputs/full/<versão>/` e `outputs/evaluation/<versão>/`, grava `outputs/evaluation/fases/<versão>/metricas.csv` e `gatilhos_aprendidos.csv` e atualiza a planilha `data/interim/fases/<versão>/rotulagem_fases.csv` (a coluna `gold` já preenchida é preservada). A V3+ não tem fases.

### 6. Avaliações

```powershell
python src/compare_versions.py
python src/evaluate_lexicon.py
python src/relacoes_pmi.py avaliar
python src/experimentos.py
python src/revisao_top100.py resumir
```

`relacoes_pmi.py candidatos` regenera a planilha dos 97 pares de relação, preservando os rótulos já preenchidos; `revisao_top100.py gerar` cria a planilha de revisão dos termos.

### 7. Gerar e abrir o explorador

```powershell
python -m src.visualize_graph --versions-dir outputs/full --eval-cases data/processed/evaluation.csv --scores data/interim/ngram_candidates/candidatos_v3.csv --output outputs/explorador.html
```

Gera uma única página com V1, V2, V3 e V3+ (versões ausentes em `outputs/full/` são ignoradas). O explorador abre na V3+; use `outputs/explorador.html?v=v1` (ou `v2`, `v3`, `v3_mais_dados`) para outra versão, `&set=all` para os 56 casos e `&tab=compare` para a aba de comparação. O arquivo pode ser aberto diretamente ou servido com:

```powershell
python -m http.server 8765
```

e acessado em [http://localhost:8765/outputs/explorador.html](http://localhost:8765/outputs/explorador.html).

### 8. Testes

```powershell
python -m unittest discover -s tests -v
```

São 26 testes; os de `test_fases_temporais.py` precisam do `scikit-learn`.

## Estrutura das saídas

```text
outputs/
├── explorador.html    # página única: V1, V2, V3 e V3+, 11 ou 56 casos
├── evaluation/        # resultados nos 11 casos de avaliação
│   ├── comparison.csv, relacoes_comparacao.csv, experimentos.csv, ...
│   ├── fases/v1/ v2/ v3/
│   └── v1/ v2/ v3/ v3_mais_dados/
└── full/              # nodes.csv e edges.csv por versão nos 56 casos
    └── v1/ v2/ v3/ v3_mais_dados/
```

Mais detalhes em [Preparação dos dados](../../project1/docs/preparacao-dados.md), [Estratégia de extração](../../project1/docs/estrategia-extracao.md) e [Avaliação do extrator](../../project1/docs/avaliacao-extrator.md).
