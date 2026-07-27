# data/ — camadas de dados (não versionadas)

Esta pasta hospeda os dados locais durante o desenvolvimento. **Nada aqui é
versionado** (ver `.gitignore`): os pipelines regeneram tudo a partir da fonte,
de forma determinística. Só este README é rastreado.

Organização prevista (arquitetura *medallion*):

- `bronze/` — dados crus, como chegam da fonte (via conector), sem tratamento.
- `silver/` — dados limpos, tipados e conformados (regras de qualidade aplicadas).
- `gold/` — tabelas prontas para análise/modelo (a base do OTIF e dos custos).

Em produção/homologação, as camadas podem viver no **Postgres (Neon)** em vez de
arquivos. O caminho/《conexão》 vem sempre de variável de ambiente — nunca fixo
no código.
