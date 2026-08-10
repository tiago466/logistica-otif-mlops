<a id="topo"></a>

# Documentação · Logística OTIF (CRISP-DM)

<!-- nav:start -->
[← README do projeto](../README.md) | [Entendimento do Negócio](01_entendimento_do_negocio.md)
<!-- nav:end -->

> Índice da documentação, organizada pelas seis etapas do método **CRISP-DM** (o roteiro padrão de um projeto de dados). Cada etapa é um documento; este é o mapa. O status ao lado mostra o que já está pronto.

## As etapas

| # | Etapa | Pergunta que responde | Status |
|---|---|---|---|
| 1 | **[Entendimento do Negócio](01_entendimento_do_negocio.md)** | Qual é a dor? Como vira problema de dados? | ✅ pronto |
| 2 | **[Entendimento dos Dados](02_entendimento_dos_dados.md)** | Onde estão os dados, como são, qual o modelo (MER)? | ✅ pronto |
| — | **[Dicionário de Dados](04_dicionario_de_dados.md)** | O que significa cada coluna das 30 tabelas? | ✅ pronto (gerado do banco) |
| — | **[Acesso aos Dados](03_acesso_aos_dados.md)** | Como conectar no banco e na API? | ✅ pronto |
| 3 | **Preparação dos Dados** | Como limpar e conformar (bronze → silver)? | 🔄 em andamento |
| 4 | **Modelagem** | Baseline, comparação de candidatos, escolha por validação. | ⬜ a criar |
| 5 | **Avaliação** | O modelo é honesto e útil (validação temporal, custo)? | ⬜ a criar |
| 6 | **Implantação (Deploy)** | Como colocar em produção e monitorar (drift)? | ⬜ a criar |

## O caminho, em detalhe

O CRISP-DM dá o esqueleto; abaixo está como ele se realiza neste projeto. Dois domínios percorrem o mesmo caminho, e a **operação vai primeiro**: o financeiro reaproveita o trilho já aberto.

| Passo | Entrega | Situação |
|---|---|---|
| Entrevistar os donos e traduzir a dor em problema de dados | [docs/01](01_entendimento_do_negocio.md) | ✅ |
| Mapear as fontes e modelar o domínio | [docs/02](02_entendimento_dos_dados.md) + [dicionário](04_dicionario_de_dados.md) | ✅ |
| **Reproduzir os relatórios que a empresa já usa** | [`sql/`](../sql/) | ✅ aprovados pelos donos |
| Carregar o Bronze (cópia fiel da origem, por domínio) | `data/bronze/{operacao,financeiro}/` | 🔄 próximo |
| EDA de **qualidade**: achar o que está errado no dado | `notebooks/operacional/00_eda_qualidade_dados_ope.ipynb` | ⬜ |
| Relatório de qualidade e recomendações (cortesia ao cliente) | documento + apresentação | ⬜ |
| Scripts de tratamento e carga do Silver | `src/.../pipelines/` | ⬜ |
| EDA **descritiva**: padrões e perfis | notebook + relatório executivo | ⬜ |
| EDA **inferencial**: evidências para modelagem | notebook + relatório técnico | ⬜ |
| Engenharia de atributos e dataset de treino (Gold) | `data/gold/` | ⬜ |
| Baseline, comparação de candidatos, avaliação temporal | MLflow | ⬜ |
| Painel de risco e implantação | dashboard + API | ⬜ |

> **Por que reproduzir antes de inovar:** o relatório existente é o número que o time conhece. Reproduzi-lo prova que entendemos o dado, valida a fonte e cria um ponto de acordo. Toda análise nova se apoia nele.

## Como ler

Leia na ordem das etapas: cada documento assume o anterior. As etapas ainda não escritas aparecem sem link (nascem conforme o projeto avança, um passo por vez). Toda a documentação é **reprodutível**: seguindo os comandos, o leitor chega ao mesmo resultado.

**Notebook × módulo:** o notebook é o laboratório, onde o dado é interrogado e a conclusão fica registrada ao lado da evidência que a sustenta. O que vira rotina sai do notebook e vira módulo em `src/`, com teste. Notebook não é lugar de código de produção.

---

[Início](#topo)
