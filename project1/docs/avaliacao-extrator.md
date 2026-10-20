# Avaliação do extrator

O extrator foi desenvolvido com 45 casos e depois executado, sem alterações, nos 11 casos reservados para avaliação (aproximadamente 20% do conjunto).

## Resultado

- 95 entidades extraídas: 46 exames, 21 sintomas, 16 tratamentos e 12 condições.
- 99 arestas, incluindo 2 `INDICATES` e 2 `BEFORE`.
- Nenhuma relação `TREATS` foi encontrada.
- Um caso não teve nenhuma entidade extraída.
- Não foram encontrados IDs inválidos, relações entre casos diferentes ou loops.

## Análise

As informações extraídas são, em geral, coerentes, indicando uma precisão razoável. Entretanto, a cobertura foi baixa: diagnósticos centrais como *Behçet's disease*, *appendicitis*, *tracheoesophageal fistula*, *TTP* e *neonatal compartment syndrome* não foram reconhecidos.

Isso mostra que o principal limite não é a lógica do programa, mas a cobertura do `lexicon.csv`. O extrator funciona quando o termo já está no léxico, porém generaliza mal para conceitos novos.

## Comparação com a versão 2

A versão 1 foi preservada e uma versão 2 foi criada por meio da expansão dos arquivos CSV, mantendo a mesma lógica de extração.

| Resultado | Versão 1 | Versão 2 |
|---|---:|---:|
| Termos no léxico | 231 | 376 |
| Gatilhos | 89 | 118 |
| Entidades extraídas | 95 | 247 |
| Condições | 12 | 69 |
| Tratamentos | 16 | 67 |
| Relações entre entidades | 4 | 19 |

A versão 2 passou a reconhecer conceitos centrais como *ulcerative colitis*, *Behçet disease*, *tracheoesophageal fistula*, *TTP* e *hydroxychloroquine-induced cardiomyopathy*. A estrutura do grafo continuou consistente e não apresentou loops ou referências inválidas.

Ainda existem limitações: alguns termos genéricos geram duplicações, menções preventivas podem ser interpretadas como doenças e um caso de apendicite continuou sem o diagnóstico principal. Como a versão 2 foi construída após a análise desses 11 casos, seu resultado representa uma iteração pós-avaliação, e não um novo teste independente.

Os recursos e resultados das duas versões foram mantidos separadamente para permitir uma comparação transparente na apresentação do projeto.
