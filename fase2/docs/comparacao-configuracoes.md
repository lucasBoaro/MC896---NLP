# Comparação das configurações do experimentos.py

Dados: as 7 rodadas de 16/10 e os CSVs em `data/interim/ngram_candidates/`. A combinação completa (char+ctx+stats com MORESTOP e META) foi rodada à parte. "@k" é o número de termos do gold V2 entre os k primeiros candidatos novos.

| Configuração | Teto | @50 | @100 | @200 | @400 | Tipo certo @400 | V1 reconhecidos / tipo | Score > 0,5 nos 300 |
|---|---:|---:|---:|---:|---:|---|---|---:|
| Base (char+ctx+stats) | 53 | 5 | 8 | 13 | 25 | 19/25 | 133 / 0,77 | 84 |
| Sem contexto (char+stats) | 53 | 2 | 7 | 14 | 27 | 20/27 | 133 / 0,76 | 300 |
| Sem caracteres (ctx+stats) | 53 | 5 | 11 | 14 | 19 | 12/19 | 141 / 0,70 | 113 |
| Naive Bayes | 53 | 2 | 2 | 5 | 8 | 6/8 | 14 / 0,93 | 86 |
| MORESTOP | 53 | 5 | **12** | 16 | 26 | 22/26 | **141 / 0,77** | 77 |
| META | **60** | 5 | 8 | **18** | 24 | 18/24 | 123 / 0,76 | 98 |
| char+stats + MORESTOP + META | **60** | 2 | 6 | 15 | **34** | **29/34** | 126 / 0,80 | 300 |
| char+ctx+stats + MORESTOP + META | 60 | **6** | 9 | 16 | 27 | 21/27 | 120 / 0,78 | não medido |

## Conclusão principal

Nenhuma configuração ganha em tudo. Há uma troca entre a **qualidade do topo da lista** (top-50/100) e o **alcance em profundidade** (top-400). Na ablação, cada componente tem um papel:

- **n-gramas de caracteres = forma do termo e tipo.** Sem eles, o top-400 cai de 25 para 19 e o tipo certo de 19/25 para 12/19. São eles que reconhecem sufixos como *-itis*, *-scopy*, *-emia*, *-mab*.
- **Contexto = calibração e precisão no topo.** Sem contexto, o modelo dá score > 0,5 aos 300 candidatos (com contexto, só 77 a 113 passam) e o topo enche de fragmentos com dose: *prednisone mg*, *methylprednisolone dosage*, *coronary syndrome acs*. O contexto penaliza o que aparece em posição de não-termo.
- **MORESTOP = limpeza.** Melhora quase tudo (top-100 de 8 para 12, V1 de 133 para 141) sem custo. Deve virar padrão.
- **META = cobertura.** Sobe o teto de 53 para 60 e dá o melhor top-200, mas 37 a 49 dos 300 candidatos aparecem uma vez só no texto e vêm só dos metadados. Traz bons termos (*acute appendicitis*, *pulmonary embolism*) e alguns ruídos.
- **Naive Bayes = baseline negativo.** O topo é cheio de palavras soltas sem sentido clínico (*figure*, *just*, *would*, *illumina*, *millipore*); só 8 dos 300 têm mais de uma palavra. O 0,93 de tipo na V1 engana, porque ele reconhece só 14 de 223.

## As listas são diferentes, não só a ordem

Termos em comum no top-100 em relação à base:

| Comparação | Em comum (de 100) |
|---|---:|
| Base × sem caracteres | 83 |
| Base × MORESTOP | 67 |
| Base × META | 60 |
| Base × sem contexto | 27 |
| Base × char+stats+MORESTOP+META | 20 |
| Base × Naive Bayes | 4 |

Com e sem contexto produzem listas quase disjuntas no topo. Para a revisão manual, a **união do top-100 de "MORESTOP" com o top-100 de "char+stats+MORESTOP+META"** cobre os dois tipos de acerto.

## Erros que aparecem em todas as configurações com Regressão Logística

- Palavras genéricas: *examination*, *tests*, *studies*, *imaging*, *weight*.
- Termo colado com a sigla e pedaços dele: *electrocardiogram ecg*, *electrocardiogram ekg*, *acute coronary syndrome acs*, *coronary syndrome acs*, *syndrome acs*.
- Tipo trocado: *endocarditis* como Symptom, *repeat egd* como Treatment.

## O que fazer a seguir

1. Tornar MORESTOP padrão e acrescentar stopwords de dose e via (*mg*, *daily*, *tablets*, *orally*, *dosage*).
2. Separar "termo + sigla" com regex (vira sinônimo no `canonical`) e remover sub-n-gramas contidos num candidato melhor (é o que o C-value faz).
3. Revisar à mão a união dos dois top-100 para obter a precisão real.
4. No relatório, mostrar esta ablação como está e lembrar que diferenças de ±2 acertos estão dentro do ruído de uma semente só.
