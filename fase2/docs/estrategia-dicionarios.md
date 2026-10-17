# Estratégia simples para montar os dicionários

## Objetivo

Os dicionários servirão para reconhecer entidades clínicas e interpretar o que o texto afirma sobre elas. A estratégia será **manual e incremental**: começaremos com poucos termos confiáveis e acrescentaremos novos termos somente quando eles forem encontrados nos casos de desenvolvimento.

Não tentaremos gerar automaticamente milhares de palavras candidatas. Como o conjunto possui poucos casos, revisar os erros do próprio extrator será mais simples e produzirá um dicionário mais limpo.

## Recursos utilizados

Serão mantidos dois dicionários:

| Arquivo | Conteúdo | Exemplos |
|---|---|---|
| `resources/v2/lexicon.csv` | Entidades que podem virar nós | `fever`, `CT scan`, `pneumonia`, `aspirin` |
| `resources/v2/triggers.csv` | Expressões que ajudam a criar relações ou interpretar o contexto | `presented with`, `diagnosed with`, `treated with` |

Doses, valores e expressões temporais não entrarão nesses dicionários, pois possuem muitas variações. Elas são identificadas por regex em `src/build_graph.py`.

## 1. Montagem do léxico de entidades

### Estrutura

O `lexicon.csv` terá quatro colunas:

```csv
term,type,canonical,source
```

- `term`: forma procurada no texto;
- `type`: `Symptom`, `Exam`, `Condition` ou `Treatment`;
- `canonical`: nome padronizado que reúne sinônimos e abreviações;
- `source`: local de onde o termo foi obtido, como `case_text`, `keywords` ou `mesh_terms`.

Exemplo:

```csv
shortness of breath,Symptom,dyspnea,case_text
dyspnea,Symptom,dyspnea,case_text
CT scan,Exam,computed tomography,case_text
pneumonia,Condition,pneumonia,keywords
amoxicillin,Treatment,amoxicillin,case_text
```

### Como será construído

#### Passo 1 — Criar uma versão inicial pequena

Usaremos o título, as keywords e os MeSH terms dos artigos de desenvolvimento para obter sugestões. Um termo sugerido só será adicionado se for uma entidade clínica útil para os textos dos casos.

Também leremos alguns casos de desenvolvimento e incluiremos os sintomas, exames, condições e tratamentos mais claros. Não é necessário encontrar todas as entidades nessa primeira leitura.

#### Passo 2 — Executar nos casos de desenvolvimento

O extrator será executado nos 45 casos de desenvolvimento usando o léxico inicial. O objetivo será observar quais entidades ele reconheceu e quais entidades relevantes ficaram de fora.

#### Passo 3 — Acrescentar somente o que estiver faltando

Quando uma entidade importante não for reconhecida, ela será revisada e adicionada ao `lexicon.csv`.

Exemplo: se `abdominal ultrasound` aparecer como exame e não for encontrado, adicionaremos:

```csv
abdominal ultrasound,Exam,ultrasound,case_text
```

Depois, o programa será executado novamente. Esse ciclo será repetido até que o léxico reconheça satisfatoriamente os casos de desenvolvimento.

#### Passo 4 — Reunir sinônimos e abreviações

Quando formas diferentes representarem o mesmo conceito, elas terão o mesmo valor em `canonical`.

```csv
myocardial infarction,Condition,myocardial infarction,case_text
heart attack,Condition,myocardial infarction,case_text
MI,Condition,myocardial infarction,case_text
```

Assim, o texto pode usar qualquer uma dessas formas, mas o grafo armazenará o conceito padronizado `myocardial infarction`.

As abreviações serão adicionadas somente quando seu significado estiver claro nos textos. Siglas muito ambíguas serão evitadas.

## 2. Montagem do dicionário de gatilhos

O `triggers.csv` conterá expressões que indicam o que aconteceu com uma entidade próxima.

Sua estrutura será:

```csv
phrase,kind,value
```

Versão inicial:

```csv
presented with,relation,HAS_SYMPTOM
complained of,relation,HAS_SYMPTOM
underwent,relation,UNDERWENT_EXAM
diagnosed with,relation,DIAGNOSED_WITH
treated with,relation,RECEIVED_TREATMENT
no evidence of,negation,NEGATED
denied,negation,NEGATED
```

O léxico identifica a entidade; o gatilho ajuda a interpretar a frase. Por exemplo:

```text
The patient was diagnosed with pneumonia.
```

- `pneumonia` é reconhecida pelo `lexicon.csv` como `Condition`;
- `diagnosed with` é reconhecido pelo `triggers.csv`;
- a combinação permite criar `Case --DIAGNOSED_WITH--> pneumonia`.

Os gatilhos também serão ampliados incrementalmente. Quando uma relação clara não for identificada porque o texto usou outra expressão, essa expressão será revisada e poderá ser adicionada.

## 3. O que não será colocado nos dicionários

Estruturas com valores variáveis serão identificadas por regex:

| Informação | Exemplos |
|---|---|
| Dose | `500 mg`, `1.5 g` |
| Resultado clínico | `180 mg/dL`, `38.5 °C` |
| Tempo | `three days later`, `two weeks after admission` |

Não faria sentido listar cada dose ou intervalo de tempo possível em um CSV. O regex descreve o formato geral e reconhece valores que nunca apareceram antes.

## Regras de inclusão

Um termo só entrará no `lexicon.csv` quando:

1. representar uma entidade clínica relevante;
2. pertencer claramente a um dos quatro tipos;
3. aparecer, ou puder ser usado para reconhecer algo que aparece, nos textos dos casos;
4. não for apenas uma palavra narrativa genérica, como `patient`, `history` ou `clinical`.

Uma expressão só entrará no `triggers.csv` quando ajudar claramente a identificar uma relação, negação ou outro contexto necessário.

## Separação entre desenvolvimento e avaliação

Os dicionários serão construídos e corrigidos somente com os 45 casos de desenvolvimento. Os 11 casos de avaliação permanecerão sem consulta até a estratégia estar pronta.

Depois, executaremos o extrator nesses 11 casos para verificar se os dicionários também funcionam em textos que não foram usados durante sua construção. Após registrar essa avaliação, os 56 casos poderão ser processados para produzir os grafos finais.

## Por que esta estratégia deve funcionar

- O corpus é pequeno, portanto é viável revisar os erros mais importantes manualmente.
- Começar com termos confiáveis reduz falsos positivos.
- A ampliação incremental adiciona apenas palavras que demonstraram utilidade real.
- A forma `canonical` reúne sinônimos e evita vários nós para o mesmo conceito.
- A separação entre entidades, gatilhos e regex deixa cada recurso simples e com uma única função.
- A avaliação separada mostra se a estratégia consegue reconhecer entidades em casos ainda não examinados.

## Resumo do processo

```text
Criar um léxico inicial pequeno
            ↓
Executar nos casos de desenvolvimento
            ↓
Revisar entidades e relações não reconhecidas
            ↓
Adicionar termos, sinônimos e gatilhos necessários
            ↓
Executar novamente e repetir o ciclo
            ↓
Avaliar uma única vez nos casos reservados
            ↓
Gerar os grafos finais
```

Essa será a estratégia adotada: poucos termos iniciais, revisão dos próprios erros e crescimento controlado dos dicionários.
