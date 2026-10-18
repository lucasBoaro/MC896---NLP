# Projeto: o texto clínico pode ensinar o extrator?

Este projeto parte do extrator do Projeto 1, que identifica entidades e relações em relatos de caso clínico a partir de um léxico e de gatilhos escritos à mão. A pergunta é se o próprio texto clínico consegue ensinar ao extrator o que ele não conhecia, usando n-gramas e aprendizado de máquina clássico, sem LLM, Transformers ou embeddings.

## Slides


## Demonstração Executável

- [Página inicial com os grafos](index.html): V1, V2 e V3.
- [Comparação das três versões nos 11 casos de avaliação](outputs/evaluation/comparar.html) e [nos 56 casos](outputs/full/comparar.html): um seletor troca a versão do léxico. Os termos aprendidos aparecem com borda tracejada e, no painel de detalhes, com o score do classificador.

## Metodologia

O extrator (`src/build_graph.py`) não foi alterado. Só o léxico muda: a V1 foi escrita à mão, a V2 foi ampliada à mão depois de analisar os casos de avaliação, e a V3 é a V1 acrescida de termos aprendidos dos casos de desenvolvimento.

```text
casos de desenvolvimento (45)
   │  n-gramas de 1 a 4 palavras por frase
   ▼
candidatos, filtrados por frequência, stopwords, PMI e NPMI
   │  rótulo fraco: termo da V1 recebe o seu tipo; termo claramente não clínico recebe NONE
   ▼
regressão logística (caracteres do termo, palavras vizinhas e estatísticas)
   │  score = 1 - P(NONE); tipo = classe de maior probabilidade
   ▼
termos novos ranqueados, sem sub-n-gramas, siglas soltas e fragmentos de exame
   ▼
resources/v3/lexicon.csv  →  extrator do Projeto 1  →  grafo V3
```

As etapas são:

1. Candidatos: `src/prototipo_ngramas.py` gera n-gramas por frase, descarta os que começam ou terminam em stopword e exige frequência mínima e colocação (PMI maior ou igual a 3 e NPMI maior ou igual a 0,30 para termos com várias palavras). Como o PMI não existe para uma palavra isolada, unigramas novos só entram com sufixo clínico, como `-itis`, `-oma` ou `-scopy`.
2. Supervisão fraca: termos já presentes no léxico V1 recebem o tipo do léxico (`Symptom`, `Exam`, `Condition` ou `Treatment`). Candidatos com palavras claramente narrativas, como `patient`, `history` e `admitted`, ou com associação fraca recebem `NONE`. Os demais são tratados como desconhecidos: o modelo apenas os pontua e não decide sozinho.
3. Classificador: regressão logística com n-gramas de caracteres do termo (TF-IDF), palavras vizinhas e estatísticas (frequência, PMI, NPMI e número de casos). Os termos conhecidos são pontuados por validação cruzada em 5 partes, e os desconhecidos por um modelo treinado em todos os conhecidos.
4. Limpeza: antes de gerar o léxico, são removidos sub-n-gramas contidos em um termo melhor ranqueado, siglas ligadas ao termo (`acute coronary syndrome acs`) e fragmentos de valores de exame.

Trecho que calcula o score de um candidato:

```python
score = 1.0 - proba[:, none_col]
```

Os 11 casos de avaliação nunca entram na mineração nem no treino do classificador. O repositório contém apenas 56 casos, de 50 artigos, e por isso sobram 45 para mineração e treino.

### Confronto com Trabalho Anterior

| Versão | Como foi construída | Termos no léxico |
|---|---|---:|
| V1 | escrita à mão com os casos de desenvolvimento | 231 |
| V2 | V1 ampliada à mão após analisar os 11 casos de avaliação | 376 |
| V3 | V1 mais termos aprendidos dos 45 casos, sem ver a avaliação | 483 |

Resultado nos 11 casos de avaliação, registrado em `outputs/evaluation/comparison.csv`:

| Resultado | V1 | V2 | V3 |
|---|---:|---:|---:|
| Entidades extraídas | 95 | 247 | 111 |
| Sintomas | 21 | 36 | 22 |
| Exames | 46 | 75 | 52 |
| Condições | 12 | 69 | 20 |
| Tratamentos | 16 | 67 | 17 |
| Arestas | 99 | 266 | 116 |
| Relações entre entidades | 4 | 19 | 5 |

Tomando as entidades da V2 como referência, em nível de entidade e aceitando sobreposição de trechos:

| Sistema | Previstas | Precisão | Revocação | F1 |
|---|---:|---:|---:|---:|
| V1 (léxico) | 95 | 0,99 | 0,38 | 0,55 |
| V3 (léxico) | 111 | 0,85 | 0,38 | 0,53 |

A V2 é uma referência aproximada: foi montada por pessoas depois de ler esses mesmos 11 casos. A V3 tem a mesma revocação da V1 e menos precisão, ou seja, os termos aprendidos acrescentaram entidades, mas quase nenhuma que a V2 reconhece.

## Trabalhos Estudados


## Modelo Lógico

O grafo é o mesmo do Projeto 1:

- Nós: `Case` e as entidades `Symptom`, `Exam`, `Condition` e `Treatment`, com o texto da menção, a posição no relato, a frase de origem e atributos como asserção, tempo e dose. O atributo `source` indica se o termo veio do léxico manual ou foi aprendido (`learned_v3`).
- Arestas com o caso: `HAS_SYMPTOM`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH` e `RECEIVED_TREATMENT`.
- Arestas entre entidades: `TREATS`, `INDICATES` e `BEFORE`.

## Análises que podem ser realizadas

- Quais termos o texto sugere que o léxico manual não tinha, e de que tipo.
- Quanto do trabalho manual da V2 o método reencontra sem ver os casos de avaliação.
- Onde o léxico aprendido erra: palavras genéricas, siglas e fragmentos de valores de exame.

## Ferramentas

O pipeline de aprendizado usa Python 3.12 com `numpy`, `scipy` e `scikit-learn` (ver `requirements.txt`). O extrator, a visualização e os testes usam somente a biblioteca padrão. A visualização é uma página HTML com JavaScript, sem dependências externas.

## Resultados

### Termos aprendidos

O método produziu 252 termos novos. Entre os primeiros do ranking há termos clínicos plausíveis que a V2 não tem, como `menorrhagia`, `lymphadenopathy`, `laparotomy`, `angiography`, `craniotomy`, `necrosis` e `laparoscopy`, junto com fragmentos e termos genéricos. A precisão real depende de revisão manual, feita na planilha `outputs/evaluation/revisao_top100.csv`.

### Recall contra o gabarito da V2

Dos 145 termos que a V2 acrescentou, apenas 38 aparecem no texto usado na mineração, e a V3 recupera 1 deles (0,7% do total e 2,6% dos 38). Os números estão em `outputs/evaluation/lexicon_recall.csv`. O corpus pequeno limita o resultado: um termo que nunca aparece no texto não tem como ser aprendido.

### PMI e NPMI

Para separar 39 termos da V1 com várias palavras de 42 n-gramas narrativos, o AUC é 0,55 para o PMI e 0,67 para o NPMI (`outputs/evaluation/association_auc.csv`). A normalização ajuda, mas com poucos exemplos a diferença é frágil.

### Componentes do classificador

Cada variação foi repetida 10 vezes com divisões aleatórias diferentes (`outputs/evaluation/experimentos.csv`; média e desvio padrão):

| Variação | AUC termo da V1 contra NONE | Tipo correto |
|---|---:|---:|
| Base (caracteres, contexto e estatísticas) | 0,935 ± 0,010 | 0,72 |
| Só caracteres | 0,922 ± 0,018 | 0,71 |
| Sem contexto | 0,953 ± 0,008 | 0,64 |
| Sem caracteres | 0,916 ± 0,010 | 0,65 |
| Só estatísticas | 0,914 ± 0,003 | 0,33 |
| Naive Bayes | 0,867 ± 0,014 | 0,70 |
| MLP pequeno | 0,927 ± 0,022 | 0,80 |
| Candidatos de até 2 palavras | 0,927 ± 0,010 | 0,69 |
| Candidatos de até 3 palavras | 0,925 ± 0,010 | 0,71 |

Os n-gramas de caracteres e o contexto são o que ensina o tipo da entidade: só com estatísticas, o tipo correto cai para 0,33. A ordem máxima dos n-gramas quase não importa neste corpus. O AUC é em parte circular, pois os rótulos `NONE` vêm de palavras e do NPMI, que também é uma característica do modelo, e por isso o tipo correto é a métrica mais confiável. A variação com apenas unigramas não pôde ser avaliada, porque os unigramas narrativos já são removidos antes e não sobra nenhum exemplo da classe `NONE`.

### Conclusão

Com 45 casos de mineração, o método aprende a forma dos termos clínicos, mas acrescenta pouca cobertura real: a V3 tem a mesma revocação da V1 (0,38) e perde precisão (0,99 para 0,85). O gargalo está no corpus, e não no classificador. O próximo experimento é minerar em mais texto, mantendo os casos de avaliação separados.

## Como Modelos de Linguagem foram Usados


## Referências Bibliográficas

- Church, K. W.; Hanks, P. (1990). Word association norms, mutual information, and lexicography. Computational Linguistics, 16(1).
- Bouma, G. (2009). Normalized (pointwise) mutual information in collocation extraction. GSCL.
- Jurafsky, D.; Martin, J. H. Speech and Language Processing (capítulos sobre n-gramas e classificação).
- Dados: MultiCaRe, amostra de 50 artigos fornecida pela disciplina.

## Como executar a etapa 2

Os comandos abaixo devem ser executados no PowerShell, a partir da pasta `fase2`. Na primeira vez, instale as dependências com `pip install -r requirements.txt`.

### 1. Aprender o léxico V3

```powershell
python src/prototipo_ngramas.py
```

O comando cria:

- `resources/v3/lexicon.csv`: a V1 acrescida dos termos aprendidos (coluna `source` igual a `learned_v3`);
- `data/interim/ngram_candidates/candidatos_v3.csv`: todos os candidatos novos, com tipo previsto, score, frequência, PMI e NPMI;
- `outputs/evaluation/association_auc.csv`: comparação entre PMI e NPMI.

### 2. Extrair os nós e as arestas com a V3

A V3 usa o léxico aprendido e os gatilhos da V1:

```powershell
python -m src.build_graph --input data/processed/evaluation.csv --lexicon resources/v3/lexicon.csv --triggers resources/v1/triggers.csv --nodes outputs/evaluation/v3/nodes.csv --edges outputs/evaluation/v3/edges.csv
```

```powershell
python -m src.build_graph --input data/processed/all_cases.csv --lexicon resources/v3/lexicon.csv --triggers resources/v1/triggers.csv --nodes outputs/full/v3/nodes.csv --edges outputs/full/v3/edges.csv
```

O primeiro comando processa os 11 casos de avaliação e o segundo, os 56 casos.

### 3. Gerar o HTML da V3 e a página de comparação

```powershell
python -m src.visualize_graph --nodes outputs/evaluation/v3/nodes.csv --edges outputs/evaluation/v3/edges.csv --scores data/interim/ngram_candidates/candidatos_v3.csv --output outputs/evaluation/v3/graph.html
```

```powershell
python -m src.visualize_graph --versions-dir outputs/evaluation --scores data/interim/ngram_candidates/candidatos_v3.csv --output outputs/evaluation/comparar.html
```

O primeiro comando gera o grafo da V3. O segundo gera a página que alterna entre V1, V2 e V3. Para o conjunto completo, troque `evaluation` por `full`.

### 4. Comparar as versões e avaliar o léxico

```powershell
python src/compare_versions.py
```

```powershell
python src/evaluate_lexicon.py
```

O primeiro comando atualiza `outputs/evaluation/comparison.csv` com a coluna da V3. O segundo cria `lexicon_recall.csv` e `lexicon_pr_curve.csv`, com o recall contra os termos que a V2 acrescentou e a curva de precisão por limiar de score.

### 5. Repetir os experimentos do classificador

```powershell
python src/experimentos.py
```

O comando roda cada variação 10 vezes e grava média e desvio em `outputs/evaluation/experimentos.csv`.

### 6. Revisar os termos aprendidos

```powershell
python src/revisao_top100.py gerar
```

O comando cria `outputs/evaluation/revisao_top100.csv`, com os 100 melhores termos novos. Preencha a coluna `avaliacao` com `certo`, `errado` ou `tipo_errado` e, depois, calcule a precisão:

```powershell
python src/revisao_top100.py resumir
```

### 7. Executar os testes

```powershell
python -m unittest discover -s tests -v
```

Atualmente, a suíte possui 19 testes.

---

# Anexo A — Projeto 1: extração por léxicos e gatilhos

Este projeto extrai entidades e relações de relatos clínicos e transforma os resultados em grafos de conhecimento interativos. A implementação utiliza léxicos, gatilhos, expressões regulares e regras linguísticas; não é necessário treinar um modelo.

## Slides

Link para visualização dos slides apresentados: [Slides](assets/apresentacao-projeto1.pptx.pdf)

## Como executar o projeto

Os comandos abaixo devem ser executados no PowerShell, a partir da raiz do repositório. É necessário ter Python 3.10 ou superior. O projeto utiliza somente a biblioteca padrão do Python, portanto não há dependências para instalar.

### 1. Preparar os dados

Execute:

```powershell
python src/prepare_data.py
```

Esse comando lê `cases.csv` e `metadata.csv`, associa cada caso ao artigo correspondente e cria:

| Arquivo | Conteúdo |
|---|---|
| `data/processed/development.csv` | 45 casos usados para desenvolver a primeira versão |
| `data/processed/evaluation.csv` | 11 casos inicialmente reservados para avaliação |
| `data/processed/all_cases.csv` | Todos os 56 casos, com a coluna `split` |

Os comandos seguintes usam `all_cases.csv`, pois o objetivo é gerar o grafo completo com os 56 casos.

### 2. Extrair os nós e as arestas com a V1

A V1 utiliza o léxico e os gatilhos construídos apenas com os casos de desenvolvimento:

```powershell
python -m src.build_graph --input data/processed/all_cases.csv --lexicon resources/v1/lexicon.csv --triggers resources/v1/triggers.csv --nodes outputs/full/v1/nodes.csv --edges outputs/full/v1/edges.csv
```

O comando cria:

- `outputs/full/v1/nodes.csv`: nós `Case`, `Symptom`, `Exam`, `Condition` e `Treatment`;
- `outputs/full/v1/edges.csv`: relações estruturais, clínicas e temporais encontradas pela V1.

Se esses arquivos já existirem, eles serão sobrescritos com uma nova execução completa da V1.

### 3. Extrair os nós e as arestas com a V2

A V2 utiliza o léxico e os gatilhos ampliados após a análise dos resultados da V1:

```powershell
python -m src.build_graph --input data/processed/all_cases.csv --lexicon resources/v2/lexicon.csv --triggers resources/v2/triggers.csv --nodes outputs/full/v2/nodes.csv --edges outputs/full/v2/edges.csv
```

O comando cria:

- `outputs/full/v2/nodes.csv`: nós extraídos pela V2;
- `outputs/full/v2/edges.csv`: relações extraídas pela V2.

Se esses arquivos já existirem, eles serão sobrescritos. Como V2 e o conjunto completo são as configurações padrão, o mesmo resultado pode ser gerado com o comando abreviado:

```powershell
python -m src.build_graph
```

### 4. Gerar o HTML da V1

Depois de gerar `nodes.csv` e `edges.csv` da V1, execute:

```powershell
python -m src.visualize_graph --nodes outputs/full/v1/nodes.csv --edges outputs/full/v1/edges.csv --output outputs/full/v1/graph.html
```

O arquivo interativo será criado em:

```text
outputs/full/v1/graph.html
```

### 5. Gerar o HTML da V2

Execute:

```powershell
python -m src.visualize_graph --nodes outputs/full/v2/nodes.csv --edges outputs/full/v2/edges.csv --output outputs/full/v2/graph.html
```

O arquivo será criado em:

```text
outputs/full/v2/graph.html
```

Para a V2, também é possível usar o comando abreviado:

```powershell
python -m src.visualize_graph
```

### 6. Abrir os grafos no navegador

Os arquivos HTML podem ser abertos diretamente pelo Explorador de Arquivos. Se preferir servi-los por um endereço local, execute um dos comandos abaixo.

Para subir a V1:

```powershell
python -m http.server 8765 --directory outputs/full/v1
```

Abra [http://localhost:8765/graph.html](http://localhost:8765/graph.html).

Para subir a V2 em outro terminal:

```powershell
python -m http.server 8766 --directory outputs/full/v2
```

Abra [http://localhost:8766/graph.html](http://localhost:8766/graph.html).

O servidor permanece ativo enquanto o terminal estiver aberto. Pressione `Ctrl+C` para encerrá-lo. Subir o HTML não executa novamente a extração; o servidor apenas disponibiliza o arquivo já gerado.

### 7. Executar os testes

```powershell
python -m unittest discover -s tests -v
```

Atualmente, a suíte possui 19 testes.

### Estrutura das saídas

```text
outputs/
├── evaluation/        # comparação da V1, da V2 e da V3 nos 11 casos reservados
│   ├── comparison.csv
│   ├── comparar.html  # alterna entre V1, V2 e V3
│   ├── v1/
│   ├── v2/
│   └── v3/
└── full/              # grafos completos com os 56 casos
    ├── comparar.html
    ├── v1/
    │   ├── nodes.csv
    │   ├── edges.csv
    │   └── graph.html
    ├── v2/
    │   ├── nodes.csv
    │   ├── edges.csv
    │   └── graph.html
    └── v3/
        ├── nodes.csv
        ├── edges.csv
        └── graph.html
```

Os arquivos em `outputs/evaluation` registram o experimento realizado somente nos 11 casos de avaliação. Os arquivos em `outputs/full` são as visualizações consolidadas dos 56 casos e devem ser usados para a demonstração final.

Consulte [Preparação dos dados](docs/preparacao-dados.md), [Estratégia de extração](docs/estrategia-extracao.md) e [Avaliação do extrator](docs/avaliacao-extrator.md) para mais detalhes.

# Ideia inicial — Extração de informação de casos clínicos

## Objetivo

O projeto transformará o texto de cada caso clínico em um grafo de conhecimento. A primeira versão será simples, baseada em dicionários, expressões regulares e regras. Não será necessário treinar um modelo.

O diferencial escolhido pela equipe é reconstruir a **linha do tempo do caso**: identificar sintomas, exames, diagnósticos e tratamentos e tentar descobrir quando ocorreram e em qual ordem. A proposta envolve extração temporal, além da visualização dos resultados.

## Nós do grafo

Teremos cinco tipos de nós:

| Tipo | O que representa | Exemplo |
|---|---|---|
| `Case` | O caso clínico | `case_17` |
| `Symptom` | Sintoma ou sinal apresentado | `fever` |
| `Exam` | Exame realizado | `computed tomography` |
| `Condition` | Doença ou diagnóstico | `pneumonia` |
| `Treatment` | Medicamento, procedimento ou terapia | `amoxicillin` |

O nó `Case` será criado diretamente com as informações do `cases.csv`. Os outros quatro tipos serão encontrados no texto.

## Relações

Usaremos inicialmente estas relações:

| Origem | Relação | Destino |
|---|---|---|
| `Case` | `HAS_SYMPTOM` | `Symptom` |
| `Case` | `UNDERWENT_EXAM` | `Exam` |
| `Case` | `DIAGNOSED_WITH` | `Condition` |
| `Case` | `RECEIVED_TREATMENT` | `Treatment` |
| `Exam` | `INDICATES` | `Condition` |
| `Treatment` | `TREATS` | `Condition` |
| Ocorrência clínica | `BEFORE` | Ocorrência clínica posterior |

As relações `INDICATES` e `TREATS` só serão criadas quando houver evidência suficiente no texto.

`BEFORE` será o único tipo de aresta temporal. A direção da aresta já indica qual acontecimento ocorreu antes; não criaremos um tipo genérico `Temporal` nem a relação inversa `AFTER`. Os deslocamentos de tempo (offsets) ficarão nos atributos dos nós.

## Léxico principal

O arquivo `lexicon.csv` reunirá os dicionários de sintomas, exames, condições e tratamentos. Vai ser o nosso dicionário principal, a maneira que vamos encontrar as palavras dentro dos textos. Cada linha informará:

- o termo que pode aparecer no texto;
- o tipo de nó;
- sua forma padronizada.

Exemplo:

```csv
term,type,canonical
fever,Symptom,fever
shortness of breath,Symptom,dyspnea
dyspnoea,Symptom,dyspnea
CT,Exam,computed tomography
CT scan,Exam,computed tomography
pneumonia,Condition,pneumonia
amoxicillin,Treatment,amoxicillin
```

Sinônimos e abreviações aparecem em linhas diferentes, mas apontam para a mesma forma padronizada. O léxico será global: o mesmo arquivo será usado em todos os casos.

O léxico inicial será montado manualmente com termos frequentes, `keywords` e termos MeSH. Os metadados serão usados como fonte de candidatos, mas nenhum termo será transformado automaticamente em nó sem aparecer também no `case_text`.

## Métodos de extração

**Como a nossa criatividade vai ser julgada, é nessa parte da extração que temos que caprichar, então se tiverem novas ideias de coisas e maneira que podemos usar para extrair informação no texto avisem no grupo para adicionár-mos. Essas foram as ideias iniciais que pensei em fazer.**

Além do léxico, utilizaremos:

1. **Separação em frases:** ponto final, interrogação, exclamação e quebra de parágrafo indicarão possíveis finais de frase. Vírgulas não separarão frases.
2. **Tokenização por palavras:** cada frase será tokenizada, mantendo a posição dos tokens e a frase à qual pertencem. Expressões com várias palavras, como `abdominal pain`, formarão um único nó.
3. **Expressões regulares:** para doses (`500 mg`), frequências, valores de exames, unidades e medidas.
4. **Expressões indicadoras:** padrões como `presented with`, `diagnosed with`, `underwent` e `treated with` ajudarão a interpretar as entidades.
5. **Negação e incerteza:** verificar quais menções são afetadas por expressões como `no evidence of`, `ruled out` ou `suspected`. Elas não serão registradas como acontecimentos confirmados. Uma negação não elimina automaticamente as outras entidades da frase.
6. **Regras de relação:** padrões linguísticos conectarão as entidades encontradas. Por exemplo, `was diagnosed with [Condition]` pode indicar `DIAGNOSED_WITH`, desde que o diagnóstico pertença ao paciente e não esteja negado ou apenas previsto. Uma palavra isolada não garante a relação.
7. **Normalização e deduplicação:** sinônimos receberão o mesmo nome usando o léxico. Menções ao mesmo acontecimento poderão ser agrupadas, mas exames, sintomas ou tratamentos em momentos diferentes serão preservados como ocorrências distintas para não perder a cronologia.
8. **Evidência:** cada extração guardará a frase original que a originou, facilitando a conferência dos resultados (para nós mesmos).
9. **Extração temporal:** reconhecer expressões de tempo, associá-las aos acontecimentos e resolver sua referência quando houver evidência suficiente.

## Fluxo do programa

```text
cases.csv e metadata.csv
        ↓
leitura de um caso
        ↓
separação em frases e tokens
        ↓
busca de entidades no lexicon.csv
        ↓
regex para doses, valores e unidades
        ↓
verificação de contexto, negação e incerteza
        ↓
normalização e identificação de ocorrências distintas
        ↓
criação dos nós e identificação das relações
        ↓
extração de expressões temporais e associação aos acontecimentos
        ↓
resolução das referências de tempo e ordenação parcial
        ↓
nodes.csv e edges.csv
        ↓
grafo e linha do tempo com evidências
```

## Exemplo

Texto:

> The patient presented with fever. A chest CT was performed. Pneumonia was diagnosed. Amoxicillin was initiated to treat the pneumonia.

Nós:

```text
Case: case_17
Symptom: fever
Exam: computed tomography
Condition: pneumonia
Treatment: amoxicillin
```

Relações:

```text
case_17 --HAS_SYMPTOM--------> fever
case_17 --UNDERWENT_EXAM-----> computed tomography
case_17 --DIAGNOSED_WITH-----> pneumonia
case_17 --RECEIVED_TREATMENT-> amoxicillin
amoxicillin --TREATS---------> pneumonia
```

## Saída e avaliação

O resultado será exportado em duas tabelas:

- `nodes.csv`: nós e seus atributos;
- `edges.csv`: relações entre os nós.

Depois, alguns casos serão revisados manualmente para identificar extrações corretas, informações não encontradas e falsos positivos. Por fim, os grafos poderão ser visualizados de forma interativa, exibindo a frase original associada a cada entidade.

## Diferencial escolhido: linha do tempo clínica

### O que queremos descobrir

A pergunta central é: **até que ponto técnicas baseadas em regras conseguem reconstruir a ordem dos acontecimentos de um relato clínico?**

Exemplos de informações desejadas:

- quando os sintomas começaram;
- quando um exame foi realizado;
- quando uma condição foi diagnosticada;
- quando um tratamento começou e, se informado, quanto tempo durou.

A data do diagnóstico não é necessariamente a data de início da doença. Também não podemos assumir que os acontecimentos ocorreram na ordem em que aparecem no texto: um relato pode mencionar uma cirurgia e depois voltar aos sintomas anteriores.

### Exemplo concreto

Texto fictício:

> Fever began three days before admission. A CT scan was performed two days after admission. One day after the CT scan, treatment with amoxicillin was initiated.

Usando a internação como referência, sem precisar conhecer sua data no calendário:

| Acontecimento | Expressão encontrada | Interpretação |
|---|---|---|
| Início da febre | `three days before admission` | Dia −3 |
| Internação | `admission` | Dia 0: referência do caso |
| Realização da tomografia | `two days after admission` | Dia +2 |
| Início da amoxicilina | `one day after the CT scan` | Dia +3: um dia depois do exame |

A internação pode ser um marco guardado nos atributos de `Case`, sem criar um sexto tipo de nó. O ponto mais desafiador do exemplo é ligar o início do tratamento ao exame e combinar os dois deslocamentos temporais.

### Como extrair essas informações

**1. Encontrar os acontecimentos.** Usar o léxico e as regras já planejadas. Expressões como `began`, `was performed`, `was diagnosed` e `was initiated` ajudam a identificar a ação: início, realização ou diagnóstico.

**2. Encontrar expressões temporais.** Usar regex e listas de expressões, reconhecendo números escritos em algarismos ou palavras (`3` e `three`).

| Categoria | Exemplos | O que guardar |
|---|---|---|
| Data explícita | `on 12 March 2020` | Data, quando não ambígua |
| Deslocamento relativo | `two days after admission` | Quantidade, unidade, direção e referência |
| Marco clínico | `on admission`, `after surgery` | Referência e relação com ela |
| Duração | `for five days` | Duração, sem inventar uma data de início |
| Ordem sem intervalo | `before the biopsy` | Acontecimento anterior/posterior, sem número de dias |

`Twice daily` é frequência de administração, não uma posição na linha do tempo. O ano de publicação do artigo também não será usado como data dos acontecimentos clínicos.

**3. Associar tempo e acontecimento.** Começar com padrões dentro da mesma frase, como `[Exam] was performed [tempo]`. Não atribuir a mesma data a todas as entidades da frase. Como extensão, analisar a frase anterior para resolver expressões como `the next day`, apenas quando houver uma referência clara.

**4. Resolver a referência temporal.** Se o texto disser `two days after admission`, podemos posicionar o acontecimento no dia +2 em relação à internação. Se disser apenas `after surgery`, sabemos a ordem, mas não o intervalo. Não escolher automaticamente o acontecimento mais próximo quando houver várias referências possíveis.

**5. Preservar o que não foi resolvido.** Guardar a expressão e a evidência mesmo quando não for possível determinar o tempo. A linha do tempo poderá ser parcial. Não converter uma expressão ambígua em uma data aparentemente exata.

### Como isso entra no grafo

Manteremos os cinco tipos de nós. Cada nó clínico representará uma ocorrência no caso: duas tomografias realizadas em dias diferentes terão IDs diferentes, mesmo que compartilhem o mesmo nome normalizado.

As informações temporais serão armazenadas na coluna `attributes` de `nodes.csv`, junto aos outros atributos de cada ocorrência. Não criaremos nós de tempo. Os campos principais serão:

| Atributo do nó | Significado |
|---|---|
| `time_anchor` | Referência do deslocamento: por exemplo, a internação do caso ou o ID de outra ocorrência |
| `time_offset` | Deslocamento numérico em relação à referência: negativo antes, positivo depois, zero no marco |
| `time_unit` | Unidade do deslocamento, como `day` |
| `time_text` | Expressão temporal original, preservada para conferência |
| `time_status` | Indica se a informação foi resolvida, é parcial ou ficou sem resolução |

Um offset só tem significado junto de sua referência e unidade. Para desenhar a linha do tempo, tentaremos converter os tempos para uma referência comum, como a internação, quando o texto permitir. Não compararemos diretamente offsets que usam referências diferentes.

Atributos para o exame do exemplo:

```json
{
  "action": "performed",
  "time_text": "two days after admission",
  "time_anchor": "admission",
  "time_offset": 2,
  "time_unit": "day",
  "time_status": "resolved",
  "sentence_id": 2,
  "evidence": "A CT scan was performed two days after admission."
}
```

`time_status` poderá ser `resolved` (referência e deslocamento conhecidos), `partial` (apenas parte da informação, como a ordem) ou `unresolved` (referência não identificada). Atributos sem informação ficarão ausentes ou nulos.

No mesmo exemplo, o tratamento começou um dia depois da tomografia, que ocorreu no dia +2. Após resolver essa referência, os atributos do tratamento poderão guardar `time_anchor: admission`, `time_offset: 3` e `time_unit: day`, preservando a expressão original em `time_text` e a evidência do cálculo.

A ordem será registrada em `edges.csv`, usando `relation: BEFORE`:

```text
Tomografia --BEFORE--> Início do tratamento
```

A aresta informa a ordem; os offsets ficam nos nós. Os atributos da aresta guardam a evidência ou a regra usada para estabelecer a ordem, sem duplicar os offsets. `Tratamento AFTER Tomografia` seria redundante, por isso usaremos apenas `BEFORE`.

Só criaremos `BEFORE` quando houver suporte textual ou cálculo a partir de uma referência comum. Não precisamos criar uma aresta entre todos os pares ordenáveis. Se soubermos apenas que o tratamento ocorreu depois do exame, criaremos a aresta e deixaremos os offsets desconhecidos. A ordem pode ser conhecida mesmo sem sabermos o intervalo. Acontecimentos no mesmo dia, sem indicação de ordem, não serão ligados por `BEFORE` apenas por compartilharem a data.

O grafo e a linha do tempo serão duas visualizações dos mesmos dados de `nodes.csv` e `edges.csv`. A interface usará os offsets dos nós para posicionar os acontecimentos e as arestas `BEFORE` para mostrar as ordens conhecidas. Não será necessário criar uma segunda base ou extrair o texto novamente.

Uma relação temporal não significa causalidade: o tratamento acontecer depois do exame não prova que o exame motivou o tratamento.

### Escopo inicial e extensão desafiadora

**Primeira versão:** reconhecer deslocamentos explícitos em relação à internação, datas claras e padrões de tempo na mesma frase; preservar ocorrências repetidas; produzir uma linha do tempo parcial com evidências. Usar a internação como dia 0 apenas nos casos em que ela estiver identificada.

**Extensão:** resolver referências entre frases e entre acontecimentos, como `the next day` ou `two days after the biopsy`. Também tentar representar durações como intervalos quando o início for conhecido. Essa é a parte em que podemos encontrar limitações e documentar o que as regras não conseguiram resolver.

Na visualização, cada tipo terá uma cor. Clicar em um acontecimento mostrará o trecho e a referência temporal usados. Acontecimentos sem posição definida aparecerão em uma área separada; os que tiverem apenas ordem conhecida serão apresentados sem uma escala de dias inventada.

### Como avaliar

Separar casos de desenvolvimento e avaliação por artigo. Nos casos de avaliação, anotar manualmente expressões temporais, acontecimentos associados, referências e algumas relações de ordem, sem ajustar as regras a esses mesmos exemplos.

Verificar:

- **Reconhecimento:** quais expressões temporais foram encontradas corretamente e quais faltaram (precisão e recall).
- **Associação:** quantas expressões foram ligadas ao acontecimento correto.
- **Resolução:** quantas referências e posições calculadas estão corretas e qual proporção ficou sem resolução.
- **Ordenação:** comparar as relações temporais com a anotação manual e com uma versão que simplesmente segue a ordem das frases.

Um resultado parcial ainda será útil se mostrarmos quais construções funcionam, quais falham e por quê. A contribuição que pretendemos investigar é a integração entre extração de entidades, identificação de acontecimentos e resolução temporal por regras, sem modelos de linguagem na extração.

### Referências para fundamentar o método

- [HeidelTime](https://github.com/HeidelTime/heideltime): sistema baseado em regras para reconhecer e normalizar expressões temporais. Pode servir como referência ou componente a experimentar; reconhecer a expressão não resolve automaticamente sua ligação ao acontecimento clínico.
- [Hamon e Grabar (2014), Tuning HeidelTime for identifying time expressions in clinical texts in English and French](https://aclanthology.org/W14-1116/): trabalho sobre adaptação do HeidelTime ao texto clínico, útil para fundamentar a necessidade de regras específicas do domínio.

A extração temporal já existe na literatura. O diferencial proposto para este projeto é adaptar e avaliar essas ideias nos relatos clínicos, expondo tanto as relações resolvidas quanto as lacunas, em um grafo integrado à linha do tempo.
