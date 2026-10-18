# Comparação das configurações do classificador

Os resultados abaixo vêm de `python src/experimentos.py`, que repete cada variação do classificador 10 vezes. A cada repetição, a divisão da validação cruzada em 5 partes é sorteada de novo (e, no MLP, também os pesos iniciais). A tabela mostra média e desvio padrão. O corpus são os 45 casos de desenvolvimento, e os 11 casos de avaliação não são usados. Os valores completos estão em `outputs/evaluation/experimentos.csv`.

## Métricas

- AUC termo da V1 contra NONE: probabilidade de o modelo dar score maior a um termo do léxico V1 do que a um candidato claramente não clínico (0,5 equivale ao acaso), medida fora da amostra por validação cruzada;
- V1 reconhecidos: fração dos termos da V1 com score maior que 0,5;
- tipo correto: entre os termos da V1 reconhecidos, fração cujo tipo previsto é igual ao do léxico;
- gabarito no top-400: quantos dos termos acrescentados pela V2 aparecem entre os 400 melhores candidatos novos.

## Resultado

| Variação | AUC | V1 reconhecidos | Tipo correto | Gabarito no top-400 |
|---|---:|---:|---:|---:|
| Base: caracteres, contexto e estatísticas | 0,935 ± 0,010 | 0,98 | 0,72 ± 0,021 | 1,6 |
| Só caracteres | 0,922 ± 0,018 | 0,99 | 0,71 ± 0,016 | 1,0 |
| Sem contexto (caracteres e estatísticas) | 0,953 ± 0,008 | 0,97 | 0,64 ± 0,013 | 1,1 |
| Sem caracteres (contexto e estatísticas) | 0,916 ± 0,010 | 0,98 | 0,65 ± 0,016 | 2,0 |
| Só estatísticas | 0,914 ± 0,003 | 0,96 | 0,33 ± 0,024 | 2,0 |
| Naive Bayes | 0,867 ± 0,014 | 0,98 | 0,70 ± 0,014 | 2,1 |
| MLP pequeno (uma camada de 32 neurônios) | 0,927 ± 0,022 | 0,99 | 0,80 ± 0,015 | 1,0 |
| Candidatos de até 2 palavras | 0,927 ± 0,010 | 0,98 | 0,69 ± 0,025 | 2,0 |
| Candidatos de até 3 palavras | 0,925 ± 0,010 | 0,98 | 0,71 ± 0,021 | 2,0 |
| Só unigramas | não avaliável | | | |

## Análise

O tipo da entidade vem da forma do termo e do contexto. Só com estatísticas (frequência, PMI e NPMI), o tipo correto cai de 0,72 para 0,33. Os n-gramas de caracteres, como os sufixos *-itis* e *-scopy*, e as palavras vizinhas, como *treated with* e *underwent*, é que distinguem `Symptom`, `Exam`, `Condition` e `Treatment`.

O contexto ajuda a tipar, mas não a separar termo de não termo: sem ele o AUC sobe para 0,953, e o tipo correto cai para 0,64. O MLP pequeno acerta mais o tipo (0,80), com desvio um pouco maior entre as repetições. O Naive Bayes é o pior em separar termo de não termo (AUC de 0,867). A ordem máxima dos n-gramas quase não muda o resultado (0,925 a 0,935), e diferenças menores que um desvio padrão são ruído.

## Limitações

O AUC é em parte circular. Os rótulos `NONE` são definidos por palavras narrativas e pelo NPMI, e o NPMI também é uma característica do modelo, por isso até o modelo que usa só estatísticas tem AUC alto (0,914). O tipo correto é a métrica mais confiável.

A variação com apenas unigramas não pode ser avaliada: os unigramas narrativos já são removidos antes da classificação, e não sobra nenhum exemplo da classe `NONE` para treinar.

Diferenças de 1 a 2 termos no top-400 do gabarito não significam nada, pois apenas 38 dos 145 termos da V2 aparecem no texto usado na mineração.
