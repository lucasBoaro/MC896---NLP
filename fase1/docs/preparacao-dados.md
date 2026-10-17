# Preparação dos dados

Esta etapa faz somente cinco coisas:

1. lê `cases.csv` e `metadata.csv`;
2. associa cada caso ao artigo pelo `article_id`;
3. separa os artigos entre desenvolvimento e avaliação;
4. salva os dois grupos;
5. cria um arquivo consolidado com todos os casos e a origem de cada um.

Execute na raiz do repositório:

```powershell
python src/prepare_data.py
```

O resultado fica em:

```text
data/prepared/
├── development.csv
├── evaluation.csv
└── all_cases.csv
```

Cada arquivo contém os campos do caso e os quatro campos do artigo necessários para construir o primeiro léxico:

```text
article_id, age, case_id, case_text, gender,
title, keywords, mesh_terms, major_mesh_terms
```

`all_cases.csv` possui também a coluna `split`, com o valor `development` ou `evaluation`. Ela permite gerar uma visualização única sem perder a origem usada no experimento.

A separação usa 80% dos artigos para desenvolvimento e 20% para avaliação. Todos os casos do mesmo artigo ficam no mesmo grupo. A semente `42` mantém a divisão igual em todas as execuções.

O programa usa apenas a biblioteca padrão do Python.
