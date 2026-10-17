# Estratégia de extração de informação

## Objetivo

O programa transformará o `case_text` de cada caso clínico em duas tabelas: `nodes.csv`, com as entidades extraídas, e `edges.csv`, com as relações entre elas. A extração será baseada em dicionários, expressões regulares e regras linguísticas. Não será necessário treinar um modelo.

O grafo terá cinco tipos de nós:

| Tipo | Origem | Exemplos |
|---|---|---|
| `Case` | Criado diretamente a partir do CSV | `PMC5137649_01` |
| `Symptom` | Extraído do texto | `fever`, `chest pain` |
| `Exam` | Extraído do texto | `CT scan`, `biopsy` |
| `Condition` | Extraído do texto | `pneumonia`, `diabetes` |
| `Treatment` | Extraído do texto | `amoxicillin`, `surgery` |

## Três recursos de extração

Usaremos três recursos com finalidades diferentes:

| Recurso | Pergunta respondida | Exemplos |
|---|---|---|
| `resources/v2/lexicon.csv` | Qual entidade clínica apareceu? | `fever`, `CT scan`, `pneumonia` |
| `resources/v2/triggers.csv` | O que a frase afirma sobre a entidade? | `presented with`, `diagnosed with`, `no evidence of` |
| Regex em `src/build_graph.py` | Qual estrutura variável apareceu? | `500 mg`, `180 mg/dL`, `three days after admission` |

### Léxico de entidades

O `lexicon.csv` reunirá termos dos textos de desenvolvimento e dos campos `title`, `keywords`, `mesh_terms` e `major_mesh_terms`. Ele será ampliado de forma incremental conforme analisarmos os erros do extrator.

```csv
term,type,canonical,source
shortness of breath,Symptom,dyspnea,case_text
dyspnoea,Symptom,dyspnea,case_text
CT scan,Exam,computed tomography,case_text
pneumonia,Condition,pneumonia,mesh_terms
amoxicillin,Treatment,amoxicillin,case_text
```

- `term`: forma que pode aparecer no texto;
- `type`: tipo de nó que deverá ser criado;
- `canonical`: nome padronizado, usado para unir sinônimos e abreviações;
- `source`: origem usada para acrescentar o termo ao léxico.

Expressões com várias palavras serão procuradas como uma unidade. Se o programa reconhecer `abdominal pain`, não deverá criar outro candidato para `pain` dentro do mesmo trecho.

### Dicionário de gatilhos

O `triggers.csv` não contém entidades. Ele contém expressões que ajudam a interpretar uma entidade próxima.

```csv
phrase,kind,value
presented with,relation,HAS_SYMPTOM
underwent,relation,UNDERWENT_EXAM
diagnosed with,relation,DIAGNOSED_WITH
treated with,relation,RECEIVED_TREATMENT
revealed,relation,INDICATES
no evidence of,negation,NEGATED
ruled out,negation,NEGATED
suspected,uncertainty,SUSPECTED
on admission,temporal_anchor,admission
```

Por exemplo, o léxico reconhece `fever` como `Symptom`, enquanto o gatilho `presented with` permite criar `Case --HAS_SYMPTOM--> fever`.

### Expressões regulares

As regex reconhecerão estruturas com muitas variações, que não devem ser enumeradas em um dicionário:

- doses: `500 mg`, `1.5 g`, `250 mcg`;
- resultados: `180 mg/dL`, `38.5 °C`;
- datas: `12 March 2020`;
- deslocamentos: `two days after admission`;
- durações: `for five days`.

O arquivo `src/build_graph.py` concentra essas regex e os mapas auxiliares, como a conversão de `one`, `two` e `three` para números.

## Fluxo de extração

### 1. Criar o caso

Cada registro gera um nó `Case`. `case_id`, idade, gênero e `article_id` vêm diretamente do CSV e não precisam ser procurados no texto.

### 2. Separar frases e tokens

O `case_text` será separado em frases e cada frase será tokenizada. Guardaremos `sentence_id` e as posições das expressões para preservar a evidência e calcular proximidade.

### 3. Reconhecer candidatos a entidades

O programa procurará os termos do `lexicon.csv` em cada frase. Cada correspondência gerará inicialmente um candidato com a forma original, o nome normalizado, o tipo e sua posição.

### 4. Verificar contexto

Os gatilhos próximos serão usados para interpretar o candidato. Regras de escopo verificarão negação e incerteza. Na primeira versão, uma menção negada ou apenas suspeita não criará uma relação clínica afirmativa. A negação deve afetar somente a entidade dentro de seu alcance, e não toda a frase automaticamente.

### 5. Criar relações clínicas

Os padrões combinarão gatilhos e tipos compatíveis:

```text
presented with [Symptom]
→ Case --HAS_SYMPTOM--> Symptom

diagnosed with [Condition]
→ Case --DIAGNOSED_WITH--> Condition

treated with [Treatment]
→ Case --RECEIVED_TREATMENT--> Treatment

[Exam] revealed [Condition]
→ Exam --INDICATES--> Condition

[Condition] was treated with [Treatment]
→ Treatment --TREATS--> Condition
```

A simples presença de duas entidades na mesma frase não será suficiente para criar uma relação.

### 6. Extrair atributos estruturados

As regex encontrarão valores e unidades. O programa associará cada resultado à entidade compatível na mesma oração, usando os tipos e a proximidade:

```text
amoxicillin 500 mg
→ dose do nó Treatment

glucose 180 mg/dL
→ resultado do nó Exam
```

Exemplo de atributos de tratamento:

```json
{
  "dose_value": 500,
  "dose_unit": "mg",
  "dose_text": "500 mg"
}
```

### 7. Extrair temporalidade

A temporalidade combinará gatilhos fixos e regex. A regex decompõe uma expressão como `two days after admission` em quantidade, unidade, direção e referência. Depois, a regra associa essa expressão ao acontecimento clínico correspondente.

```json
{
  "time_text": "two days after admission",
  "time_anchor": "admission",
  "time_offset": 2,
  "time_unit": "day",
  "time_status": "resolved"
}
```

Se a referência de `three days later` não puder ser identificada, preservaremos a expressão com `time_status: unresolved`, sem inventar uma data.

### 8. Criar relações temporais

Quando dois acontecimentos tiverem ordem conhecida, criaremos uma aresta `BEFORE`:

```text
computed tomography --BEFORE--> amoxicillin
```

`BEFORE` será a única direção temporal. A ordem inversa pode ser lida seguindo a aresta ao contrário, portanto não precisamos armazenar também `AFTER`. Os offsets permanecem nos atributos dos nós; a aresta registra a ordem e sua evidência.

Duas ocorrências do mesmo exame ou tratamento em momentos diferentes deverão produzir nós diferentes. Assim, a normalização do nome não apagará a cronologia.

### 9. Normalizar, guardar evidências e exportar

Os sinônimos serão convertidos para a forma `canonical`. Cada nó e aresta guardará a frase que justificou sua criação. No final, os resultados serão gravados em:

```text
outputs/full/v2/nodes.csv
outputs/full/v2/edges.csv
```

Esquema dos nós:

```text
node_id, type, label, attributes
```

Esquema das arestas:

```text
edge_id, source_id, target_id, relation, attributes
```

## Exemplo completo

Texto:

> Two days after admission, the patient underwent a CT scan. Pneumonia was diagnosed. The following day, treatment with amoxicillin 500 mg was initiated.

Extrações:

```text
CT scan     → Exam → computed tomography
pneumonia   → Condition → pneumonia
amoxicillin → Treatment → amoxicillin
500 mg      → dose de amoxicillin
```

Relações clínicas:

```text
Case --UNDERWENT_EXAM--> computed tomography
Case --DIAGNOSED_WITH--> pneumonia
Case --RECEIVED_TREATMENT--> amoxicillin
amoxicillin --TREATS--> pneumonia
```

Informações temporais:

```text
computed tomography: dia +2 em relação à internação
amoxicillin: dia seguinte ao exame, se a referência for resolvida
```

Relação temporal:

```text
computed tomography --BEFORE--> amoxicillin
```

## Ordem de implementação

1. Criar e revisar uma primeira versão do `lexicon.csv`.
2. Criar o `triggers.csv` com poucas expressões claras.
3. Implementar a separação de frases e a busca no léxico.
4. Aplicar negação e criar as quatro relações ligadas ao `Case`.
5. Implementar doses e valores.
6. Implementar `INDICATES` e `TREATS`.
7. Reconhecer expressões temporais explícitas.
8. Associar o tempo aos acontecimentos e calcular offsets.
9. Criar arestas `BEFORE`.
10. Exportar, avaliar e visualizar o grafo e a linha do tempo.

O desenvolvimento utilizará apenas o grupo de desenvolvimento para criar termos e ajustar regras. O grupo de avaliação permanecerá reservado para medir o resultado final.
