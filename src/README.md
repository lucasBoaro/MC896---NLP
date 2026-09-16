# Módulos de Execução (`src/`)

Esta pasta contém o código-fonte responsável pelo pipeline de extração de entidades, atributos e relações a partir de relatos clínicos em texto, bem como pela construção e visualização do grafo de conhecimento.

---

## 📋 Visão Geral dos Scripts

| Arquivo | Função Principal | Entradas Principais | Saídas Principais |
|---|---|---|---|
| [`prepare_data.py`](prepare_data.py) | Associa os casos aos artigos de origem e realiza a separação dos conjuntos de desenvolvimento e avaliação. | `Projeto 1/sample/cases.csv`<br>`Projeto 1/sample/metadata.csv` | `data/prepared/development.csv`<br>`data/prepared/evaluation.csv`<br>`data/prepared/all_cases.csv` |
| [`build_graph.py`](build_graph.py) | Extrai entidades clínicas, atributos e relações (estruturais, clínicas e temporais) via regras e léxicos, gerando o grafo. | `data/prepared/all_cases.csv`<br>`resources/v2/lexicon.csv`<br>`resources/v2/triggers.csv` | `outputs/full/v2/nodes.csv`<br>`outputs/full/v2/edges.csv` |
| [`visualize_graph.py`](visualize_graph.py) | Converte os nós e arestas em um aplicativo HTML/SVG interativo e autocontido com visualização em grafo, linha do tempo e tabela de relações. | `outputs/full/v2/nodes.csv`<br>`outputs/full/v2/edges.csv` | `outputs/full/v2/graph.html` |

---

## ⚙️ Pré-requisitos e Instalação

### Requisitos de Ambiente
- **Python 3.10** ou superior.
- **Nenhuma biblioteca externa obrigatória:** O pipeline foi desenvolvido utilizando **exclusivamente a biblioteca padrão do Python** (`csv`, `json`, `re`, `argparse`, `pathlib`, `random`, `collections`, `http.server`, `unittest`), portanto **não é necessário instalar pacotes via `pip`**.

### Configuração Inicial (Opcional)
Se preferir utilizar um ambiente virtual isolado:

```powershell
# Criação do ambiente virtual
python -m venv .venv

# Ativação no Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

---

## 🚀 Instruções de Execução

Recomenda-se executar os comandos a partir da **raiz do projeto**:

### Passo 1: Preparar os Dados (`prepare_data.py`)

Lê os arquivos brutos de amostra, relaciona metadados aos relatos clínicos e divide em subconjuntos:

```powershell
python src/prepare_data.py
```
*(ou `python -m src.prepare_data`)*

Saídas geradas em `data/prepared/`:
- `development.csv`: Casos destinados ao desenvolvimento das regras e léxicos (45 casos).
- `evaluation.csv`: Casos reservados para avaliação (11 casos).
- `all_cases.csv`: Base consolidada com todos os 56 casos e a identificação do split.

---

### Passo 2: Extrair o Grafo Clínico (`build_graph.py`)

Identifica entidades (`Case`, `Symptom`, `Exam`, `Condition`, `Treatment`), normalizações, atributos (doses, medições, negações/certeza, temporais) e arestas (`HAS_SYMPTOM`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH`, `RECEIVED_TREATMENT`, `INDICATES`, `TREATS`, `BEFORE`).

#### Execução Padrão (Versão 2 — V2 com base consolidada):
```powershell
python -m src.build_graph
```

#### Execução da Versão 1 (V1):
```powershell
python -m src.build_graph `
  --input data/prepared/all_cases.csv `
  --lexicon resources/v1/lexicon.csv `
  --triggers resources/v1/triggers.csv `
  --nodes outputs/full/v1/nodes.csv `
  --edges outputs/full/v1/edges.csv
```

#### Argumentos de Linha de Comando de `build_graph.py`:
- `--input`: Caminho para o CSV de casos (padrão: `data/prepared/all_cases.csv`).
- `--nodes`: Caminho de destino de `nodes.csv` (padrão: `outputs/full/v2/nodes.csv`).
- `--edges`: Caminho de destino de `edges.csv` (padrão: `outputs/full/v2/edges.csv`).
- `--lexicon`: Caminho do CSV de termos/léxicos (padrão: `resources/v2/lexicon.csv`).
- `--triggers`: Caminho do CSV de gatilhos contextuais (padrão: `resources/v2/triggers.csv`).

---

### Passo 3: Gerar a Visualização Interativa (`visualize_graph.py`)

Gera o arquivo HTML autocontido com o visualizador gráfico em SVG, linha do tempo interativa e tabela de evidências.

#### Execução Padrão (V2):
```powershell
python -m src.visualize_graph
```
Gera: `outputs/full/v2/graph.html`.

#### Execução para a Versão 1 (V1):
```powershell
python -m src.visualize_graph `
  --nodes outputs/full/v1/nodes.csv `
  --edges outputs/full/v1/edges.csv `
  --output outputs/full/v1/graph.html
```

#### Argumentos de Linha de Comando de `visualize_graph.py`:
- `--nodes`: Arquivo com a lista de nós (padrão: `outputs/full/v2/nodes.csv`).
- `--edges`: Arquivo com a lista de arestas (padrão: `outputs/full/v2/edges.csv`).
- `--output`: Destino do arquivo `.html` gerado (padrão: `outputs/full/v2/graph.html`).

---

### Passo 4: Visualizar no Navegador

O arquivo HTML gerado é autocontido e pode ser aberto de duas formas:

1. **Diretamente no navegador:**
   Dê um duplo clique em `outputs/full/v2/graph.html` ou abra o arquivo no navegador de sua preferência.

2. **Servidor HTTP local integrado do Python:**
   ```powershell
   python -m http.server 8766 --directory outputs/full/v2
   ```
   Em seguida, acesse no navegador: [http://localhost:8766/graph.html](http://localhost:8766/graph.html).
   *(Pressione `Ctrl + C` no terminal para encerrar o servidor).*

---

## 🧪 Validação e Testes Unitários

Para garantir que todas as regras de extração, negação, ancoragem temporal e particionamento estejam operando conforme o esperado, execute a suíte de testes:

```powershell
python -m unittest discover -s tests -v
```
