<a id="topo"></a>

# Logística OTIF · Ciência de Dados & MLOps ponta a ponta

<!-- nav:start -->
[Problema](#o-problema-de-negócio) | [Dados](#os-dados) | [Arquitetura](#arquitetura--stack) | [Estrutura](#estrutura-do-repositório) | [Documentação](#documentação) | [Como rodar](#como-rodar) | [Status](#status-do-projeto) | [Autor](#autor)
<!-- nav:end -->

> Projeto **end-to-end** de Ciência de Dados e MLOps no domínio **logístico**, com dados **100% sintéticos**. Duas entregas sobre a mesma base: **(1)** previsão de **atraso em entregas (OTIF)**, um problema de classificação desbalanceada com custo assimétrico, e **(2)** **raio-x de margem de contribuição por cliente** (Data Discovery financeiro). O foco é a **engenharia** em volta da ciência: pipeline reprodutível, rastreamento de experimentos, testes, CI e monitoramento, não só um notebook com um bom AUC.

## O problema de negócio

Uma transportadora fictícia, a **TransBrasil**, tem duas dores clássicas do setor:

1. **Atrasos de entrega corroem o nível de serviço (OTIF: _On Time, In Full_).** Prever, no momento certo, quais pedidos têm alto risco de atrasar permite agir antes (priorizar, realocar, avisar o cliente). É a mesma classe de problema de _churn_: evento raro, custo de errar assimétrico (deixar passar um atraso dói mais que um falso alarme).
2. **Falta visão da margem por cliente.** A empresa fatura frete e armazenagem, e paga custos operacionais (pernas de transporte, bases parceiras, galpão). Quais clientes sustentam a operação, e quais são sustentados por ela? Um diagnóstico de **margem de contribuição** (receita × custo operacional × impostos) revela o que o dia a dia não enxerga.

## Os dados

- **Sintéticos e determinísticos.** Uma empresa fictícia (**TransBrasil**), com dados gerados por semente fixa cobrindo **vários anos** (histórico com sazonalidade e um período de _drift_ proposital, para o monitor detectar). **Nenhum dado real de cliente** é usado ou versionado; a modelagem apenas se inspira na *estrutura* típica do domínio.
- **Imperfeitos de propósito.** Dado real vem sujo, então o gerador planta imperfeições realistas (nulos, duplicatas, chaves órfãs entre sistemas, itens sem valor fiscal). O bronze recebe tudo cru; o tratamento **bronze → silver** corrige com regras explícitas e testadas, guiado por EDA de qualidade.
- **Reprodutível:** quem clona o repositório e preenche o `.env` regenera a base do zero, sem depender de arquivos externos.

## Arquitetura & stack

Fluxo de dados em camadas (**medallion**): fonte → **bronze** (cru) → **silver** (limpo/conformado) → **gold** (pronto para análise e modelo) → **modelo** → **operação** (API + monitoramento).

| Camada | Tecnologia | Papel |
|---|---|---|
| Ingestão | **Conectores** (ports & adapters) | toda fonte (banco/arquivo/API) entra por um conector nomeado, configurado por ambiente |
| Armazenamento | **PostgreSQL** (dev) / **Neon** (nuvem) | base relacional sintética + camadas gold |
| Processamento | **Python 3.12**, **pandas** | pipelines medallion |
| Modelagem | **scikit-learn** (+ XGBoost/LightGBM) | baseline honesto, depois comparação de candidatos; modelo final escolhido por **validação temporal e custo**, calibrado, com threshold por custo |
| Experimentos | **MLflow** | tracking + registry de modelos |
| Qualidade | **ruff · mypy · pytest** + **CI** | esteira automatizada a cada mudança |
| Monitoramento | detecção de **drift** | vigia a distribuição dos dados em produção |
| GenAI | **RAG + agente** | consulta em linguagem natural sobre métricas validadas |
| Deploy | **Render** | API de predição e relatórios |

## Estrutura do repositório

```
logistica-otif-mlops/
├── src/logistica_otif_mlops/    # o pacote instalável
│   ├── config.py                # configuração 12-factor (via ambiente)
│   └── connectors/              # camada de conectores de dados (base + registro)
├── notebooks/                   # exploração (consumidores finos do pacote)
├── data/                        # camadas medallion (não versionadas)
├── tests/                       # testes automatizados
├── docs/                        # documentação (CRISP-DM)
├── .env.example                 # modelo de configuração (sem segredos)
└── pyproject.toml               # projeto e dependências (uv)
```

## Documentação

- **[CRISP-DM · hub da documentação](docs/README.md)**, o roteiro do projeto de dados, etapa por etapa
- Rotinas e manuais de operação: entram aqui conforme nascerem (setup do ambiente, runbooks)

## Como rodar

Pré-requisitos: **Python 3.12** e **[uv](https://docs.astral.sh/uv/)**.

> **Ambiente-base: Linux.** O projeto roda em Linux. No **Windows 11 (ou posterior)**, clone e instale normalmente, mas execute **dentro do WSL 2 + Ubuntu** (o comando `wsl --install` prepara tudo). Todos os comandos abaixo assumem um terminal Linux.

```bash
git clone git@github.com:tiago466/logistica-otif-mlops.git
cd logistica-otif-mlops
uv sync                 # cria o ambiente e instala as dependências
cp .env.example .env    # configure as variáveis (sem segredos no git)
uv run pytest           # roda os testes
```

## Status do projeto

Construído em público, um passo por vez. Transparência sobre o que já está de pé:

- [x] Esqueleto do pacote + camada de conectores + configuração 12-factor
- [ ] Modelagem do domínio (MER) + base relacional sintética
- [ ] Pipeline medallion (bronze/silver/gold)
- [ ] Data Discovery financeiro: margem de contribuição por cliente (relatório executivo + slides)
- [ ] Modelo de predição OTIF (baseline + comparação) + MLflow
- [ ] Testes, CI e monitoramento de drift
- [ ] Camada GenAI (RAG + agente) + deploy

## Autor

<a id="autor"></a>

**Tiago Lima** · Cientista de Dados (foco em MLOps e automação com IA).

**LinkedIn:** https://www.linkedin.com/in/tiago-lima-935049154/<br>
**GitHub:** https://github.com/tiago466<br>
**E-mail:** tiago.p.limm@gmail.com

---

[Início](#topo)
