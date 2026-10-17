# Roteiro cronológico para a apresentação

Este roteiro organiza a apresentação como uma linha do tempo das decisões, implementação, avaliação e evolução do projeto. A narrativa principal deve mostrar não apenas o resultado final, mas o que foi aprendido entre a V1 e a V2.

## Slide 1 — Problema e objetivo

### Mensagem principal

O projeto transforma relatos clínicos não estruturados em um grafo de conhecimento interpretável.

### Mostrar

- o problema de localizar manualmente sintomas, exames, diagnósticos e tratamentos em textos longos;
- o objetivo de extrair essas informações e conectá-las;
- a decisão de usar uma solução baseada em regras, sem treinamento de modelo;
- a pergunta adicional: é possível reconstruir parte da sequência temporal do caso?

### Visual sugerido

Uma frase clínica curta à esquerda e um pequeno grafo correspondente à direita.

## Slide 2 — Decisão sobre os nós

### Mensagem principal

Antes de extrair qualquer informação, definimos o formato do grafo.

### Mostrar

| Nó | Significado |
|---|---|
| `Case` | Caso clínico que organiza as extrações |
| `Symptom` | Sintoma ou sinal |
| `Exam` | Exame ou método diagnóstico |
| `Condition` | Doença ou diagnóstico |
| `Treatment` | Medicamento, procedimento ou terapia |

Explique que `Case` vem diretamente do CSV, enquanto os outros quatro tipos são encontrados no texto.

## Slide 3 — Decisão sobre as relações

### Mensagem principal

O grafo possui relações de organização, relações clínicas e uma relação temporal.

### Mostrar

- `Case --HAS_SYMPTOM--> Symptom`
- `Case --UNDERWENT_EXAM--> Exam`
- `Case --DIAGNOSED_WITH--> Condition`
- `Case --RECEIVED_TREATMENT--> Treatment`
- `Exam --INDICATES--> Condition`
- `Treatment --TREATS--> Condition`
- `Entidade --BEFORE--> Entidade posterior`

Ressalte que `INDICATES`, `TREATS` e `BEFORE` ligam entidades entre si e não são criadas somente pela proximidade.

## Slide 4 — Estratégia de extração

### Mensagem principal

Cada recurso possui uma função diferente e complementar.

### Mostrar

```text
Léxico  → reconhece a entidade
Trigger → interpreta o contexto e ajuda a identificar relações
Regex   → reconhece estruturas com valores variáveis
Regras  → verificam negação, incerteza, proximidade e compatibilidade
```

Exemplos:

- léxico: `shortness of breath → Symptom → dyspnea`;
- trigger: `diagnosed with`;
- regex: `500 mg` ou `two days after admission`;
- regra: não registrar `pneumonia` em `no evidence of pneumonia`.

## Slide 5 — Diferencial temporal

### Mensagem principal

Além de reconhecer entidades, tentamos representar a ordem dos acontecimentos clínicos.

### Mostrar

- expressões temporais são reconhecidas por regex e triggers;
- offsets e referências ficam nos atributos dos nós;
- a ordem confirmada gera uma aresta `BEFORE`;
- não criamos nós de tempo nem a relação redundante `AFTER`;
- quando a referência é ambígua, a expressão é preservada sem inventar uma data.

### Visual sugerido

```text
admission → CT scan → treatment
 dia 0        dia +2      dia +3
```

## Slide 6 — Construção inicial com os 80%

### Mensagem principal

A primeira versão foi construída somente com os 45 casos de desenvolvimento.

### Mostrar

- divisão por artigo: 45 casos de desenvolvimento e 11 de avaliação;
- casos do mesmo artigo permaneceram no mesmo grupo;
- metadados como título, keywords e MeSH foram usados como fontes de candidatos;
- os casos de avaliação não foram consultados durante a construção da V1.

Essa separação permitiu observar posteriormente como o método lidava com textos ainda não utilizados.

## Slide 7 — Como montamos o léxico, os triggers e as regex

### Mensagem principal

Os recursos foram construídos manualmente e ampliados de forma incremental.

### Critérios para o léxico

- representar uma entidade clínica relevante;
- pertencer claramente a um dos quatro tipos extraídos;
- aparecer no texto ou ajudar a reconhecer uma forma presente nele;
- evitar palavras narrativas genéricas;
- reunir sinônimos e abreviações por meio do campo `canonical`.

### Critérios para triggers

- indicar claramente uma relação, negação, incerteza ou referência temporal;
- possuir utilidade além de uma frase isolada;
- reduzir a criação de relações somente por coocorrência.

### Critério para regex

Usar regex quando a estrutura é relativamente estável, mas os valores mudam. Exemplos: doses, unidades, datas e deslocamentos temporais.

## Slide 8 — Fluxo implementado

### Mensagem principal

O programa transforma os CSVs originais em arquivos de nós e arestas reproduzíveis.

### Mostrar

```text
cases.csv + metadata.csv
        ↓
preparação e separação dos dados
        ↓
segmentação das frases
        ↓
léxico + triggers + regex
        ↓
regras de contexto e relações
        ↓
nodes.csv + edges.csv
        ↓
grafo interativo e sequência temporal
```

Mencione que cada extração guarda a frase usada como evidência, tornando o processo auditável.

## Slide 9 — Primeiro resultado nos 20%

### Mensagem principal

A V1 produziu extrações coerentes, mas teve baixa cobertura em textos novos.

### Resultados da V1 nos 11 casos

- 95 entidades;
- 99 arestas;
- somente 4 relações entre entidades;
- nenhuma relação `TREATS`;
- 1 caso sem nenhuma entidade.

Diagnósticos centrais como *Behçet disease*, *appendicitis*, *tracheoesophageal fistula*, *TTP* e *neonatal compartment syndrome* não foram reconhecidos.

Não diga apenas que “o método ficou ruim”. A conclusão mais precisa é: ele funcionava quando o termo estava no léxico, mas generalizava mal para conceitos novos.

## Slide 10 — Análise dos erros e criação da V2

### Mensagem principal

O resultado da V1 mostrou exatamente quais partes dos recursos precisavam ser ampliadas.

### Mostrar

- revisão das entidades centrais não reconhecidas;
- inclusão de novos sinônimos e abreviações;
- novos triggers para formas diferentes de expressar resultados e tratamentos;
- preservação integral da V1 para permitir comparação;
- manutenção da lógica principal do extrator.

A V2 passou de 231 para 376 termos no léxico e de 89 para 118 triggers.

## Slide 11 — Comparação V1 × V2

### Mensagem principal

A ampliação controlada dos recursos aumentou muito a cobertura nos casos analisados.

| Métrica nos 11 casos | V1 | V2 |
|---|---:|---:|
| Termos no léxico | 231 | 376 |
| Triggers | 89 | 118 |
| Entidades | 95 | 247 |
| Condições | 12 | 69 |
| Tratamentos | 16 | 67 |
| Relações entre entidades | 4 | 19 |
| Casos sem entidades | 1 | 0 |

Use um gráfico de barras para entidades, condições, tratamentos e relações. Não coloque todas as métricas em um único gráfico se isso prejudicar a leitura.

## Slide 12 — Grafo final e demonstração

### Mensagem principal

A V2 foi aplicada aos 56 casos para produzir a visualização consolidada.

### Mostrar

- 56 casos;
- 884 nós;
- 879 arestas;
- seleção de caso;
- busca e filtros por entidade ou relação;
- painel de evidências;
- sequência temporal.

O arquivo para a demonstração é `outputs/full/v2/graph.html`. Use uma captura de tela no slide e, se possível, abra o HTML ao vivo durante a apresentação.

## Slide 13 — Limitações e honestidade experimental

### Mensagem principal

O sistema é interpretável e apresentou boa evolução, mas ainda possui limitações importantes.

### Mostrar

- dependência da cobertura do léxico;
- falsos positivos causados por termos genéricos;
- entidades sobrepostas ou duplicadas;
- escopo de negação e resolução temporal heurísticos;
- ausência de anotações-ouro para calcular precisão e recall completos.

A V2 foi ajustada depois de observar os 11 casos. Portanto, seu desempenho nesses mesmos casos mostra uma melhoria pós-análise, não uma avaliação independente de generalização.

## Slide 14 — Conclusão

### Mensagem principal

Uma abordagem simples e interpretável conseguiu transformar relatos clínicos em grafos auditáveis e incorporar parcialmente a temporalidade.

### Encerrar com três conclusões

1. Léxico, triggers e regex são complementares e possuem responsabilidades diferentes.
2. A avaliação da V1 revelou que cobertura lexical era o principal gargalo.
3. A comparação V1 × V2 tornou visível o processo incremental e suas limitações.

Uma possível continuação seria validar o extrator em novos casos não observados ou comparar as regras com um método baseado em modelo.

## Materiais que devem ser usados na montagem

- `docs/estrategia-extracao.md`: detalhes do método;
- `docs/estrategia-dicionarios.md`: critérios de construção dos recursos;
- `docs/avaliacao-extrator.md`: resultados e limitações;
- `outputs/evaluation/comparison.csv`: números da comparação;
- `outputs/evaluation/v1/graph.html`: visualização da V1;
- `outputs/evaluation/v2/graph.html`: visualização da V2 nos mesmos casos;
- `outputs/full/v1/graph.html`: demonstração consolidada da V1 com os 56 casos;
- `outputs/full/v2/graph.html`: demonstração consolidada da V2 com os 56 casos.

## Cuidados com a linguagem dos slides

- Prefira “a cobertura aumentou” a “a acurácia aumentou”, pois não há anotações-ouro completas.
- Não apresente a V2 nos 11 casos como teste independente.
- Diferencie relações do caso para entidades das relações entre entidades.
- Explique que ausência de uma extração não significa ausência da informação no texto.
- Use exemplos com suas respectivas frases de evidência sempre que possível.
