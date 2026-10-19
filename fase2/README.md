# Projeto: o texto clínico pode ensinar o extrator?

Este projeto parte do extrator do Projeto 1, que identifica entidades e relações em relatos de caso clínico a partir de um léxico e de gatilhos escritos à mão. A pergunta é se o próprio texto clínico consegue ensinar ao extrator o que ele não conhecia, usando n-gramas e aprendizado de máquina clássico, sem LLM, Transformers ou embeddings.

## Slides


## Demonstração Executável

- [Página inicial](index.html) e [explorador único](outputs/explorador.html): V1, V2, V3 e V3+ (mais dados) em uma só página, com seletores de versão, de conjunto (11 casos de avaliação ou todos os 56) e de caso. A aba *Comparar versões* traz os totais por versão e a diferença de entidades e relações entre duas versões no caso escolhido. Os termos aprendidos aparecem com borda tracejada e, no painel de detalhes, com o score do classificador.
- Regerar: `python -m src.visualize_graph --versions-dir outputs/full --eval-cases data/processed/evaluation.csv --scores data/interim/ngram_candidates/candidatos_v3.csv --output outputs/explorador.html`

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

### V3+: mais dados e relações decididas pelo Naive Bayes

A V3+ usa 1000 casos adicionais do MultiCaRe (`data/external/cases_extra.csv`, 1045 casos na mineração), sorteados por `src/sample_multicare.py`: um caso por artigo, só relatos humanos, sem nenhum artigo que já esteja em `cases.csv`. Os 11 casos de avaliação ficam fora da mineração e do treino.

Por que o grafo da V3 tinha tão poucas relações:

1. O Naive Bayes e o PMI de `src/relacoes_pmi.py` só eram avaliados e nunca criavam arestas. `TREATS` e `INDICATES` vinham apenas de gatilhos escritos à mão, que acertam muito e encontram pouco (revocação de 0,31 e 0,57 nos pares rotulados dos 11 casos).
2. Sem condições e tratamentos reconhecidos não há par a ligar. O classificador de tipo errava termos que o sufixo resolve (`tracheostomy` como sintoma, `thrombosis` e `endometriosis` como sintoma, `cardiomyopathy` como tratamento), e unigramas com score baixo, como `appendicitis`, ficavam fora do léxico. Com o léxico da V3, os 11 casos tinham só 7 pares candidatos.
3. A tentativa anterior de aprender gatilhos por autotreinamento falhou: o Naive Bayes, treinado em 49 pares, rotulava quase todo par como positivo (173 positivos para 7 negativos), e o PMI com o rótulo passava a escolher qualquer palavra, como `mass` e `mild`. Ela foi removida.

Correções:

- `prototipo_ngramas.py` com `NGRAM_SUFFIX_TYPES=1`: o tipo de um termo com sufixo clínico vem do sufixo (`-scopy` exame, `-ectomy` tratamento, `-itis` condição), e unigramas com esse sufixo entram no léxico mesmo com score baixo.
- `src/relacoes_classificador.py`: roda o extrator com os gatilhos da V1 e, para cada par tratamento–condição ou exame–condição da mesma frase, cria a aresta quando a regra já a criou ou quando o Naive Bayes dá probabilidade acima do limiar. O modelo é treinado só nos pares rotulados dos casos de desenvolvimento, e o limiar de cada relação sai da validação cruzada nesses pares (0,50 para `INDICATES` e 0,60 para `TREATS`). A aresta guarda `method: naive_bayes` e o score.

```bash
python src/sample_multicare.py CAMINHO/cases.parquet --n 1000
NGRAM_SUFFIX_TYPES=1 NGRAM_EXTRA_CASES=data/external/cases_extra.csv NGRAM_TAG=v3_mais_dados NGRAM_TOP_K=500 python src/prototipo_ngramas.py
python src/relacoes_classificador.py --input data/processed/all_cases.csv --lexicon resources/v3_mais_dados/lexicon.csv --nodes outputs/full/v3_mais_dados/nodes.csv --edges outputs/full/v3_mais_dados/edges.csv
python src/relacoes_classificador.py --input data/processed/evaluation.csv --lexicon resources/v3_mais_dados/lexicon.csv --nodes outputs/evaluation/v3_mais_dados/nodes.csv --edges outputs/evaluation/v3_mais_dados/edges.csv
```

Nos 11 casos de avaliação (`outputs/evaluation/comparison.csv`):

| Resultado | V3 | V3+ |
|---|---:|---:|
| Termos no léxico | 483 | 942 |
| Entidades extraídas | 111 | 143 |
| Condições | 20 | 34 |
| Tratamentos | 17 | 33 |
| `TREATS` | 0 | 2 |
| `INDICATES` | 3 | 9 |
| Relações entre entidades | 5 | 13 |

Nos 56 casos, `TREATS` vai de 12 para 29 e `INDICATES` de 19 para 49.

Nos pares rotulados à mão dos 11 casos (que o modelo não viu), o Naive Bayes treinado só no desenvolvimento tem, nos limiares escolhidos, F1 de 0,75 em `TREATS` e 0,89 em `INDICATES`, contra 0,44 e 0,73 das regras. Ele ganha em revocação e perde em precisão: com tão poucos pares de treino, aproxima-se de ligar todo par da mesma frase. Das 11 relações `TREATS` e `INDICATES` da V3+ nesses casos, 8 estão corretas numa revisão manual; os erros são `biopsy → kidney injury`, em que a lesão é o motivo da biópsia, e `hydroxychloroquine → cardiomyopathy` e `→ systemic lupus erythematosus`, em frases sobre o nível sérico e sobre a cardiomiopatia causada pelo remédio. O léxico maior também traz ruído, como nomes de fabricantes (`bd biosciences san jose`).

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

### Relações TREATS e INDICATES

O extrator só cria `TREATS` (tratamento → condição) e `INDICATES` (exame → condição) quando encontra um gatilho escrito à mão na frase. O script `src/relacoes_pmi.py` trata cada par tratamento–condição ou exame–condição de uma mesma frase como candidato e decide se a relação existe. Com o léxico V2 nos 56 casos há 97 pares: 43 de `TREATS` e 54 de `INDICATES`. Os 97 foram rotulados à mão (`data/interim/relations/rotulagem.csv`), e 71 são relações verdadeiras. Os métodos comparados são:

- regras: o `build_graph.py` atual;
- regras + gatilhos PMI: as regras mais palavras aprendidas como gatilho, escolhidas pelo PMI entre cada palavra próxima ao par e o rótulo positivo;
- NPMI: limiar sobre o NPMI da coocorrência do par nos casos;
- Naive Bayes e regressão logística: palavras entre as entidades e antes delas; a regressão também usa distância, ordem e NPMI do par;
- sempre sim: referência mínima que responde "existe" para todo par.

Validação cruzada em 5 partes agrupadas por caso (`outputs/evaluation/relacoes_comparacao.csv`):

| Relação | Método | Acurácia | Precisão | Revocação | F1 |
|---|---|---:|---:|---:|---:|
| INDICATES | sempre sim | 0,78 | 0,78 | 1,00 | 0,88 |
| INDICATES | regras | 0,67 | 1,00 | 0,57 | 0,73 |
| INDICATES | regras + gatilhos PMI | 0,72 | 0,94 | 0,69 | 0,80 |
| INDICATES | NPMI | 0,78 | 0,78 | 1,00 | 0,88 |
| INDICATES | Naive Bayes | 0,74 | 0,77 | 0,95 | 0,85 |
| INDICATES | regressão logística | 0,74 | 0,78 | 0,93 | 0,85 |
| TREATS | sempre sim | 0,67 | 0,67 | 1,00 | 0,81 |
| TREATS | regras | 0,70 | 0,94 | 0,59 | 0,72 |
| TREATS | regras + gatilhos PMI | 0,70 | 0,94 | 0,59 | 0,72 |
| TREATS | NPMI | 0,67 | 0,67 | 1,00 | 0,81 |
| TREATS | Naive Bayes | 0,77 | 0,81 | 0,86 | 0,83 |
| TREATS | regressão logística | 0,53 | 0,63 | 0,76 | 0,69 |

As regras são precisas, mas perdem cerca de 40% das relações. Em `TREATS`, o Naive Bayes é o único método que supera as regras e a referência "sempre sim". Em `INDICATES`, nenhum método supera a referência em acurácia, mas os gatilhos aprendidos sobem a revocação das regras de 0,57 para 0,69 mantendo a precisão em 0,94. O limiar de NPMI escolheu o menor valor possível e virou "sempre sim": a coocorrência do par no corpus não separa relações verdadeiras de falsas dentro de uma mesma frase.

Dois cuidados com o PMI aparecem aqui. Primeiro, como 71 dos 97 pares são positivos, o F1 da referência "sempre sim" já é alto, e por isso a acurácia e a comparação com essa referência são necessárias. Segundo, o PMI entre uma palavra e o rótulo positivo tem teto: PMI(t, +) = log2 P(+|t)/P(+) ≤ −log2 P(+), que dá 0,36 com 78% de positivos. Um limiar fixo de PMI não selecionaria nenhum gatilho; o script divide o PMI por esse teto, o que deixa a escala entre 0 e 1, como no NPMI.

Os gatilhos aprendidos ficam em `resources/v3/triggers_aprendidos.csv`. Há termos plausíveis (`consistent`, `suggestive`, `evidence`, `findings`, `presence`) e ruído (`chronic`, `vascular`, `appendix`, e `no`/`but`, que vêm do padrão "showed no X but Y"), por isso a lista precisa de revisão antes de entrar em um `triggers.csv`. Com 97 pares, diferenças de poucos centésimos entre métodos não são confiáveis.

### Linha do tempo: fases aprendidas

Na etapa 1, as regras só posicionavam um evento quando havia uma expressão de tempo explícita perto dele: 15% dos eventos da V3 tinham posição, e havia 12 arestas `BEFORE` nos 56 casos. O script `src/fases_temporais.py` aplica a mesma receita da V3 à linha do tempo. Cada evento recebe uma de quatro fases do relato (antecedentes, apresentação, investigação e tratamento, seguimento), no estilo do DocTimeRel do corpus THYME:

1. Funções de rotulagem com expressões seguras (`history of`, `years ago`, `a 3-day history`, `on admission`, `POD 3`, `follow-up`, `discharged`...) rotulam parte dos eventos. A expressão de tempo explícita vence verbos típicos de fase, e entre expressões sobrepostas vale a mais longa.
2. Essas expressões são mascaradas no texto, para o classificador não decorar as regras.
3. Uma regressão logística usa as palavras ao redor da entidade e da frase anterior, o tipo e o termo da entidade, a posição da frase no relato e a fase das regras nos eventos vizinhos. Como na V3, os casos de avaliação não entram no treino: os de desenvolvimento são pontuados por validação cruzada agrupada por caso, e os de avaliação por um modelo treinado só com os de desenvolvimento.
4. Eventos sem regra recebem a fase prevista quando o score é pelo menos 0,5. Na visualização, aparecem com a marca "fase aprendida" e o score.

| Versão | Eventos | Com tempo (etapa 1) | Fase pela regra | Fase pelo modelo | Com fase |
|---|---|---|---|---|---|
| V1 | 612 | 18% | 44% | 33% | 77% |
| V2 | 828 | 15% | 40% | 36% | 76% |
| V3 | 957 | 15% | 39% | 36% | 75% |

Acurácia contra os rótulos das regras, nos casos de desenvolvimento (V3, 331 eventos):

| Método | Acurácia | F1 macro |
|---|---|---|
| Classe majoritária | 0,489 | 0,164 |
| Copiar a fase do evento vizinho | 0,695 | 0,646 |
| Regressão logística: só posição | 0,468 | 0,417 |
| Regressão logística: só contexto | 0,562 | 0,357 |
| Regressão logística: só vizinhos | 0,640 | 0,618 |
| Regressão logística: sem vizinhos | 0,607 | 0,442 |
| Regressão logística: modelo completo | 0,734 | 0,642 |

O modelo completo é o mais acurado, mas tem F1 macro parecido com o de simplesmente copiar a fase do vizinho, e nas V1 e V2 fica abaixo dele (0,54 e 0,51 contra 0,61), porque tende a puxar eventos para a fase mais comum (investigação e tratamento). A fase dos vizinhos é a característica mais forte: o relato costuma andar em ordem de fases. O NPMI entre as palavras do contexto mascarado e cada fase (`outputs/evaluation/fases/v3/gatilhos_aprendidos.csv`) mostra pistas que não estavam nas regras, como *initially*, *had* e *significant* para antecedentes, *mild*, *intermittent* e *tenderness* para apresentação, e *mg*, *twice*, *daily* e *intravenously* para tratamento.

Essas acurácias medem quanto o modelo reproduz as regras sem ver as expressões delas, e não a acurácia real. Para medi-la, a coluna `gold` de `data/interim/fases/v3/rotulagem_fases.csv` foi preenchida para os 111 eventos dos 11 casos de avaliação, lendo o relato inteiro e sem olhar as colunas das regras e do modelo. A anotação foi feita pelo Claude (assistente de IA usado no projeto), e não por uma pessoa, então é uma referência preliminar que o grupo deve revisar. O critério foi: a fase de apresentação é o atendimento descrito na primeira frase do relato; o que veio antes é antecedente; exames e tratamentos desse atendimento são curso (exames laboratoriais e de imagem iniciais incluídos); o que vem depois da alta ou em readmissões posteriores é seguimento. Três menções que não descrevem um evento do paciente (pneumonia em outros pacientes e uma frase genérica sobre o SLE) ficaram em branco. Uma segunda anotação, também feita pelo Claude mas vendo as colunas das regras e do modelo, concordou com esta em 99 de 107 eventos (kappa de Cohen 0,90). Quase todas as diferenças são exames laboratoriais e ECG da chegada, que a segunda anotação pôs em apresentação. O gold mantido é o da anotação cega.

| Contra a anotação (108 eventos) | Cobertura | Acurácia |
|---|---|---|
| Regras | 38% | 0,805 |
| Modelo, só nos eventos sem regra | 36% (39 eventos) | 0,744 |
| Regras + modelo | 74% | 0,775 |
| Referência: tudo em "investigação e tratamento" | 100% | 0,426 |

O modelo praticamente dobra a cobertura e acerta 29 dos 39 eventos que as regras deixavam sem fase, com acurácia um pouco abaixo da das regras. A maior parte dos erros do modelo e das regras confunde apresentação com curso ou seguimento: uma readmissão posterior ("presented", "admitted") parece a apresentação inicial, e exames da chegada ficam entre as duas fases. Com 11 casos e um único anotador, as diferenças de poucos pontos não são confiáveis.

### Conclusão

Com 45 casos de mineração, o método aprende a forma dos termos clínicos, mas acrescenta pouca cobertura real: a V3 tem a mesma revocação da V1 (0,38) e perde precisão (0,99 para 0,85). O gargalo está no corpus, e não no classificador. O próximo experimento é minerar em mais texto, mantendo os casos de avaliação separados. Nas relações, um classificador simples sobre as palavras entre as entidades recupera relações que os gatilhos manuais perdem, com alguma perda de precisão.

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

### 3. Classificar a fase dos eventos da linha do tempo

Depois do `build_graph.py` e antes da visualização:

```powershell
python src/fases_temporais.py --version v3
```

O comando acrescenta `phase`, `phase_source` (`regra` ou `modelo`), `phase_score` e `phase_cue` aos atributos de `outputs/full/v3/nodes.csv` e de `outputs/evaluation/v3/nodes.csv`, grava `outputs/evaluation/fases/v3/metricas.csv` e `gatilhos_aprendidos.csv` e cria a planilha `data/interim/fases/v3/rotulagem_fases.csv`. Troque `v3` por `v1` ou `v2` para as outras versões. Se o `build_graph.py` for executado de novo, rode este comando outra vez.

### 4. Gerar o explorador

```powershell
python -m src.visualize_graph --versions-dir outputs/full --eval-cases data/processed/evaluation.csv --scores data/interim/ngram_candidates/candidatos_v3.csv --output outputs/explorador.html
```

Gera uma única página com V1, V2, V3 e V3+ (as versões ausentes em `outputs/full/` são ignoradas). Os 11 casos de avaliação são filtrados da mesma base dos 56. O explorador abre na V3+. Quando o caso não tem TREATS, INDICATES nem BEFORE, o grafo mostra as entidades ligadas ao caso e explica o motivo: nenhuma entidade extraída, nenhuma condição reconhecida, ou nenhuma condição na mesma frase que um exame ou tratamento. Para abrir outra versão, use `outputs/explorador.html?v=v1` (ou `v2`, `v3`, `v3_mais_dados`); `&set=all` abre com os 56 casos e `&tab=compare` abre a aba de comparação.

### 5. Abrir o explorador no navegador

O arquivo pode ser aberto diretamente. Para servi-lo por um endereço local:

```powershell
python -m http.server 8765
```

Abra [http://localhost:8765/](http://localhost:8765/). Subir o servidor não executa novamente a extração.

### 6. Executar os testes

```powershell
python -m unittest discover -s tests -v
```

Atualmente, a suíte possui 19 testes.

### Estrutura das saídas

```text
outputs/
├── explorador.html    # página única: V1, V2, V3 e V3+, 11 ou 56 casos
├── evaluation/        # nodes.csv e edges.csv por versão nos 11 casos reservados
│   ├── comparison.csv
│   └── v1/ v2/ v3/ v3_mais_dados/
└── full/              # nodes.csv e edges.csv por versão nos 56 casos
    └── v1/ v2/ v3/ v3_mais_dados/
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
