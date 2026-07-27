<a id="topo"></a>

# Logística OTIF — Ciência de Dados & MLOps ponta a ponta

<!-- nav:start -->
[Problema](#o-problema-de-negócio) | [Dados](#os-dados) | [Arquitetura](#arquitetura--stack) | [Estrutura](#estrutura-do-repositório) | [Como rodar](#como-rodar) | [Status](#status-do-projeto) | [Autor](#autor)
<!-- nav:end -->

> Projeto **end-to-end** de Ciência de Dados e MLOps no domínio **logístico**, com dados **100% sintéticos**. Duas entregas sobre a mesma base: **(1)** previsão de **atraso em entregas (OTIF)** — um problema de classificação desbalanceada com custo assimétrico — e **(2)** **análise de custos de transporte** (Data Discovery). O foco é a **engenharia** em volta da ciência: pipeline reprodutível, rastreamento de experimentos, testes, CI e monitoramento — não só um notebook com um bom AUC.

## O problema de negócio

Uma transportadora fictícia, a **TransBrasil**, tem duas dores clássicas do setor:

1. **Atrasos de entrega corroem o nível de serviço (OTIF — _On Time, In Full_).** Prever, no momento certo, quais pedidos têm alto risco de atrasar permite agir antes (priorizar, realocar, avisar o cliente). É a mesma classe de problema de _churn_: evento raro, custo de errar assimétrico (deixar passar um atraso dói mais que um falso alarme).
2. **Falta visão do custo de transporte.** Onde o dinheiro escorre — por rota, modalidade, transportador, região? Um diagnóstico de custos revela padrões que a operação não enxerga no dia a dia.

## Os dados

- **Sintéticos e determinísticos.** Uma empresa fictícia (**TransBrasil**), com dados gerados por semente fixa cobrindo **vários anos** (histórico com sazonalidade e um período de _drift_ proposital, para o monitor detectar). **Nenhum dado real de cliente** é usado ou versionado — a modelagem apenas se inspira na *estrutura* típica do domínio.
- **Reprodutível:** quem clona o repositório e preenche o `.env` regenera a base do zero, sem depender de arquivos externos.

## Arquitetura & stack

Fluxo de dados em camadas (**medallion**): fonte → **bronze** (cru) → **silver** (limpo/conformado) → **gold** (pronto para análise e modelo) → **modelo** → **operação** (API + monitoramento).

| Camada | Tecnologia | Papel |
|---|---|---|
| Ingestão | **Conectores** (ports & adapters) | toda fonte (banco/arquivo/API) entra por um conector nomeado, configurado por ambiente |
| Armazenamento | **PostgreSQL** (dev) / **Neon** (nuvem) | base relacional sintética + camadas gold |
| Processamento | **Python 3.12**, **pandas** | pipelines medallion |
| Modelagem | scikit-learn / **LightGBM** | classificador de atraso, calibrado, com threshold por custo |
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
├── .env.example                 # modelo de configuração (sem segredos)
└── pyproject.toml               # projeto e dependências (uv)
```

## Como rodar

Pré-requisitos: **Python 3.12** e **[uv](https://docs.astral.sh/uv/)**.

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
- [ ] Data Discovery — análise de custos de transporte
- [ ] Modelo de predição OTIF + MLflow
- [ ] Testes, CI e monitoramento de drift
- [ ] Camada GenAI (RAG + agente) + deploy

## Autor

<a id="autor"></a>

**Tiago Lima** — Cientista de Dados (foco em MLOps e automação com IA).

**LinkedIn:** https://www.linkedin.com/in/tiago-lima-935049154/<br>
**GitHub:** https://github.com/tiago466<br>
**E-mail:** tiago.p.limm@gmail.com

---

[Início](#topo)
