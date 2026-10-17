# Etapa 2: plano recomendado

## Ideia em uma frase

**Transformar o ciclo manual V1 → V2 em um ciclo automático V1 → V3:** usar N-gramas + PMI para descobrir termos clínicos candidatos no texto e um classificador (Regressão Logística) treinado por supervisão fraca com o léxico V1 para decidir o tipo de cada candidato (Symptom / Exam / Condition / Treatment / nenhum). Os termos aprovados viram `resources/v3/lexicon.csv`, e o extrator do Projeto 1 roda **sem nenhuma mudança** com `--lexicon resources/v3/lexicon.csv`.

## Por que essa ideia

- **Ataca o gargalo que vocês mesmos mostraram no slide 11:** "o principal gargalo observado era a cobertura lexical". A V2 resolveu isso à mão (145 termos novos). A pergunta da etapa 2 fica natural: *dá para aprender isso a partir do próprio texto?*
- **Cumpre todos os requisitos do enunciado:** N-gramas (obrigatório) para achar entidades compostas e PMI para colocações (ambos citados pelo professor); ML clássico (Regressão Logística/Naive Bayes); sem LLM, sem embeddings, sem Transformers.
- **Usa as Possibilidades 1, 4 e 5 do guia:** classificação de entidades, weak supervision a partir das regras do Projeto 1, e comparação de representações.
- **Tem um gabarito pronto e honesto:** os 145 termos com `source=evaluation_v2` na V2 são exatamente o que humanos adicionaram. Dá para medir quanto o método automático recupera, sem anotar nada novo.
- **Pouco código:** um script novo (~150 linhas). Nada no `build_graph.py` muda, então a comparação V1 / V2 / V3 é limpa (mesma lógica de antes, só troca o léxico, como na etapa 1).
- **É "audacioso" do jeito que o professor pede:** não sabemos se vai superar a curadoria manual, e o enunciado diz que isso vale nota mesmo se o resultado não vier.

## Protótipo já testado

Escrevi e rodei um protótipo: [`prototipo_ngramas.py`](prototipo_ngramas.py) (saída: [`candidatos_v3.csv`](candidatos_v3.csv), top 300 candidatos). Ele precisa de `scikit-learn` (`pip install scikit-learn`). Para rodar a partir da raiz do repositório: `python caminho/prototipo_ngramas.py .`

O que ele faz:

1. Gera todos os 1- a 4-gramas por frase dos 56 casos (23.871 distintos), descarta os que começam ou terminam com stopword, exige frequência ≥ 2 e **PMI ≥ 3** para multi-palavras → 3.625 candidatos.
2. Rótulo fraco: candidato que está no léxico V1 recebe o tipo do léxico; o resto recebe `NONE`.
3. Features: **n-gramas de caracteres** do termo (pegam sufixos como *-itis*, *-ectomy*, *-scopy*, *-mab*), **n-gramas de palavras do contexto** (as 2 palavras antes/depois, ex.: `L=treated with`, `L=underwent`), PMI, frequência, nº de casos, sigla.
4. Regressão Logística com *cross-fitting* em 5 folds (cada candidato é pontuado por um modelo que não o viu no treino).

Resultados do primeiro teste, sem nenhum ajuste:

| Métrica | Valor |
|---|---|
| Termos V1 reconhecidos (validação cruzada) | 133 de 223, tipo correto em 77% |
| Termos gold da V2 que viraram candidatos | 53 de 145 (os outros aparecem só 1 vez no corpus) |
| Gold V2 recuperados no top-400 | 25, com tipo correto em 19 |

Os primeiros da lista já são bons termos que **nem estão na V2**: *capsule endoscopy*, *transabdominal ultrasonography*, *arterial blood gas analysis*, *acute coronary syndrome*, *asthma*, *oral iron*, *laparoscopic appendectomy*, *profound weight loss*. Também há ruído (*glucose intolerance was made*, *thoracic ct february*, *ancient*), que é justamente o que a etapa de ajuste deve reduzir. Ou seja, a precisão contra o gold é um limite inferior; a precisão real só se mede olhando a lista.

## Plano de passos

| # | Passo | Quem/quanto |
|---|---|---|
| 1 | Copiar o protótipo para `src/discover_terms.py` e ajustar stopwords (meses, verbos como *made*, *ancient*) e cortar números colados em termos (`aspirin mg`) | pequeno |
| 2 | **Ablação de representações** (Possibilidade 5): (A) só n-gramas de caracteres; (B) + contexto unigrama; (C) + contexto bigrama + PMI. E comparar Naive Bayes × Regressão Logística. Tabela de precision/recall/F1 por tipo e matriz de confusão | pequeno, é só trocar flags |
| 3 | **Revisão humana rápida do top-100** (marcar certo/errado/tipo errado numa coluna do CSV): dá a *precisão real@100*, que é o número mais forte da apresentação | 1 pessoa, ~30 min |
| 4 | Gerar `resources/v3/lexicon.csv` = V1 + candidatos com score ≥ limiar, com `source=ngram_ml` e o score | pequeno |
| 5 | Rodar o extrator com V3 nos 11 casos de avaliação e nos 56, e adicionar a coluna `v3` em `outputs/evaluation/comparison.csv` (mesmo formato da etapa 1). A V3 é a primeira versão **sem olhar** os casos de avaliação, o que corrige a ressalva honesta que vocês fizeram sobre a V2 | pequeno |
| 6 | Visualização: no `graph.html`, destacar os nós vindos de termos aprendidos (borda tracejada ou selo "aprendido") e mostrar o score no painel de detalhes. Extra opcional: um gráfico com as top colocações por PMI | médio |
| 7 | README da etapa 2 no template do professor (Metodologia, Confronto com Trabalho Anterior, Resultados) e slides | divisão do grupo |

Divisão sugerida para 5 pessoas: (1) passos 1–2, (2) passo 3 + análise de erros, (3) passos 4–5, (4) passo 6, (5) README + slides.

## Narrativa para os slides

1. Etapa 1 terminou com: "o gargalo é a cobertura do léxico" e a V2 foi curada à mão.
2. Pergunta da etapa 2: **o texto consegue ensinar o léxico sozinho?**
3. N-gramas + PMI geram candidatos; regras da V1 viram rótulos (weak supervision); classificador decide o tipo.
4. Resultado: quanto do trabalho manual da V2 o método recupera, o que ele acha que a V2 não tinha, e onde erra.
5. Comparação V1 × V2 (manual) × V3 (automática) × V2+V3 nos mesmos 11 casos e no grafo.

## Alternativas (se quiserem trocar)

- **Classificador de relações** (Possibilidade 2: par de entidades → TREATS / INDICATES / NONE com contexto em n-gramas). É a ideia mais "clássica" do guia, mas a V2 só produziu 19 relações entre entidades, então quase não há exemplos positivos para treinar. Não recomendo com o prazo curto.
- **NER sequencial com CRF** (BIO gerado pelo léxico V2, `sklearn-crfsuite`). Mais elegante e mais próximo da literatura, mas exige reescrever a extração para usar o modelo e é mais trabalhoso de avaliar. Bom como "trabalho futuro" no slide final.

## Detalhes úteis

- O enunciado pede a pasta `project2/` no formato do template (`data/`, `pipelines/`, `src/`, `assets/slides`, README com seções fixas). Hoje a raiz do repositório segue o modelo do projeto 1.
- O projeto hoje usa só a biblioteca padrão; o protótipo adiciona `scikit-learn` (e `numpy`/`scipy`, que vêm junto). Vale criar um `requirements.txt`.
