# Contexto do projeto para outros agentes

Este documento resume as decisões, a implementação e o estado atual do Projeto 1 de MC896. Ele deve ser lido antes de alterar o extrator, os recursos ou as saídas.

## Objetivo

O projeto transforma relatos clínicos em um grafo de conhecimento. A solução é baseada em léxico, gatilhos, expressões regulares e regras linguísticas; não há treinamento de modelo.

O diferencial escolhido foi representar parcialmente a evolução temporal do caso. O sistema reconhece expressões temporais, armazena informações de tempo nos atributos dos acontecimentos e cria relações `BEFORE` quando a ordem pode ser sustentada pelo texto.

## Dados

Os dados originais ficam em `Projeto 1/sample`. `src/prepare_data.py` relaciona cada caso aos metadados do artigo pelo `article_id` e produz:

- `data/prepared/development.csv`: 45 casos usados na construção da V1;
- `data/prepared/evaluation.csv`: 11 casos inicialmente reservados para avaliação;
- `data/prepared/all_cases.csv`: os 56 casos, com a coluna `split` indicando a origem.

A separação é feita por artigo, usando semente 42. Assim, casos pertencentes ao mesmo artigo não aparecem nos dois grupos.

## Modelo do grafo

### Tipos de nó

| Tipo | Origem |
|---|---|
| `Case` | Criado diretamente a partir do CSV |
| `Symptom` | Sintoma ou sinal encontrado no texto |
| `Exam` | Exame, teste ou método diagnóstico |
| `Condition` | Doença, diagnóstico ou condição clínica |
| `Treatment` | Medicamento, procedimento ou terapia |

### Tipos de relação

| Origem | Relação | Destino |
|---|---|---|
| `Case` | `HAS_SYMPTOM` | `Symptom` |
| `Case` | `UNDERWENT_EXAM` | `Exam` |
| `Case` | `DIAGNOSED_WITH` | `Condition` |
| `Case` | `RECEIVED_TREATMENT` | `Treatment` |
| `Exam` | `INDICATES` | `Condition` |
| `Treatment` | `TREATS` | `Condition` |
| Entidade clínica | `BEFORE` | Entidade clínica posterior |

As quatro primeiras relações organizam as entidades dentro de cada caso. `INDICATES`, `TREATS` e `BEFORE` conectam entidades entre si e exigem evidência textual; a simples coocorrência na mesma frase não é suficiente.

## Estratégia de extração

### Léxico

`resources/v2/lexicon.csv` reconhece entidades. Suas colunas são:

- `term`: forma procurada no texto;
- `type`: `Symptom`, `Exam`, `Condition` ou `Treatment`;
- `canonical`: forma normalizada que reúne sinônimos e abreviações;
- `source`: origem do termo.

Expressões com várias palavras são priorizadas para evitar criar uma entidade menor dentro de outra, como `pain` dentro de `abdominal pain`.

### Gatilhos

`resources/v2/triggers.csv` contém expressões que ajudam a interpretar o contexto. As colunas são `phrase`, `kind` e `value`. Há gatilhos de relação, negação, incerteza, resolução, procedimento não realizado e referência temporal.

Exemplo: o léxico reconhece `pneumonia` como condição; um gatilho como `diagnosed with` ajuda a afirmar a relação do caso com essa condição.

### Expressões regulares

As regex ficam em `src/build_graph.py` e tratam estruturas com valores variáveis, principalmente:

- doses, como `500 mg`;
- valores e unidades clínicas;
- datas;
- durações;
- deslocamentos temporais, como `two days after admission`;
- expressões de ordem, como `the following day`.

Essas informações não pertencem ao léxico porque não seria viável enumerar todas as combinações possíveis.

### Regras de contexto

O extrator separa o texto em frases, encontra entidades e gatilhos com suas posições e verifica o contexto antes de criar fatos. As regras atuais incluem:

- escopo simplificado de negação e incerteza;
- descarte de exames ou tratamentos explicitamente não realizados;
- associação de doses apenas a tratamentos próximos;
- associação de valores apenas a entidades compatíveis;
- `INDICATES` somente no padrão compatível `Exam → gatilho → Condition`;
- `TREATS` somente com gatilho explícito entre tratamento e condição;
- `BEFORE` apenas quando existe uma indicação temporal conservadora;
- bloqueio de loops e de relações entre casos diferentes.

Cada nó e aresta preserva a frase usada como evidência. Os nós também mantêm `sentence_id`, posições no texto e atributos estruturados em JSON.

## Fluxo implementado

```text
cases.csv + metadata.csv
        ↓
src/prepare_data.py
        ↓
development.csv + evaluation.csv + all_cases.csv
        ↓
src/build_graph.py
        ↓
outputs/full/v2/nodes.csv + outputs/full/v2/edges.csv
        ↓
src/visualize_graph.py
        ↓
outputs/full/v2/graph.html
```

O HTML oferece seleção de caso, busca de entidades, filtros de relações, detalhes com evidências e uma visão de sequência temporal.

## Evolução experimental

### Versão 1

A V1 foi construída usando apenas os 45 casos de desenvolvimento. Seus recursos foram preservados em `resources/v1`.

Ao aplicar essa versão, sem alterações, nos 11 casos reservados, foram obtidos:

- 95 entidades;
- 99 arestas;
- 4 relações entre entidades;
- 1 caso sem nenhuma entidade.

A análise indicou entidades geralmente coerentes, mas baixa cobertura. Diagnósticos centrais e vários sinônimos não estavam no léxico.

### Versão 2

Depois de registrar o resultado da V1, os 11 casos foram analisados e os recursos foram ampliados. A V2, preservada em `resources/v2`, passou de 231 para 376 termos e de 89 para 118 gatilhos.

Nos mesmos 11 casos, a V2 encontrou:

- 247 entidades;
- 266 arestas;
- 19 relações entre entidades;
- nenhum caso sem entidades.

Essa comparação demonstra o efeito da ampliação dos recursos, mas não mede generalização: como a V2 foi ajustada após observar os 11 casos, esses dados deixaram de ser uma avaliação independente.

## Estado atual

O grafo consolidado da V2 contém:

- 56 casos;
- 884 nós;
- 879 arestas;
- nenhuma aresta órfã;
- nenhuma relação entre casos diferentes;
- nenhum loop.

A suíte possui 19 testes, atualmente todos aprovados.

## Estrutura relevante

```text
data/prepared/
├── development.csv
├── evaluation.csv
└── all_cases.csv

resources/
├── v1/
│   ├── lexicon.csv
│   └── triggers.csv
└── v2/
    ├── lexicon.csv
    └── triggers.csv

src/
├── prepare_data.py
├── build_graph.py
└── visualize_graph.py

outputs/
├── evaluation/
│   ├── comparison.csv
│   ├── v1/
│   └── v2/
└── full/
    ├── v1/
    │   ├── nodes.csv
    │   ├── edges.csv
    │   └── graph.html
    └── v2/
        ├── nodes.csv
        ├── edges.csv
        └── graph.html
```

## Como executar

Na raiz do repositório, com Python 3.10 ou superior:

```powershell
python src/prepare_data.py
python -m src.build_graph
python -m src.visualize_graph
python -m unittest discover -s tests -v
```

`build_graph.py` também aceita `--input`, `--lexicon`, `--triggers`, `--nodes` e `--edges`. `visualize_graph.py` aceita `--nodes`, `--edges` e `--output`. Isso permite reproduzir as avaliações sem substituir o resultado final.

## Limitações conhecidas

- A cobertura depende diretamente dos termos disponíveis no léxico.
- Termos genéricos podem produzir falsos positivos.
- Conceitos sobrepostos podem criar entidades redundantes.
- O escopo de negação e a resolução temporal são heurísticos.
- Parte da ordem temporal permanece implícita ou não resolvida.
- O corpus não possui anotações-ouro de entidades e relações; as contagens não equivalem automaticamente a precisão, recall ou acurácia.

## Cuidados para alterações futuras

- Não substituir ou apagar a V1: ela é necessária para a comparação experimental.
- Não apresentar o desempenho da V2 nos 11 casos como avaliação independente.
- Não criar relações apenas porque duas entidades aparecem na mesma frase.
- Preservar evidências e posições das extrações.
- Executar os 19 testes após mudanças no extrator.
- Regenerar `outputs/full/v2` quando o código ou os recursos da V2 forem alterados.
