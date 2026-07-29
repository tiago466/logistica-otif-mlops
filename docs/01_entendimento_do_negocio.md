<a id="topo"></a>

# Entendimento do Negócio · TransBrasil (CRISP-DM · Etapa 1)

<!-- nav:start -->
[← Índice CRISP-DM](README.md) | [Entendimento dos Dados »](02_entendimento_dos_dados.md)
<!-- nav:end -->

> A primeira etapa do método CRISP-DM: entender o **negócio** antes dos dados. Quem é a empresa, como o trabalho flui, qual é a dor e como ela se traduz num problema de dados. Empresa e personagens são **fictícios**; os dados usados no projeto são **100% sintéticos**.

## 1. A empresa e as pessoas

A **TransBrasil** é uma transportadora de médio-grande porte, com operação rodoviária e aérea, atendendo grandes contas em todo o país. Como em qualquer operação real, as decisões passam por um grupo de pessoas, os *stakeholders* que descreveram as dores:

| Pessoa | Papel | O que traz ao projeto |
|---|---|---|
| **Sr. Abraão** | Dono | Visão do negócio; quer crescer sem perder a margem. |
| **Sr. Elias** | Diretor de Operações | Sente na pele os atrasos e os "modos de emergência". |
| **Dna. Sarah** | Diretora Financeira | Desconfia que **clientes grandes podem estar sendo subsidiados** e quer o raio-x. |
| **Samuel** | Gerente de Coordenação | Conhece o fluxo do pedido ponta a ponta. |
| **Joel** | Gerente Operacional | Vive as ocorrências, coletas e prazos no dia a dia. |
| **João** | Diretor de TI | **Nosso ponto de acesso aos dados** (define como cada fonte é servida). |

## 2. O processo: o ciclo de vida de um pedido

A operação segue um pipeline padronizado de **fases sequenciais**, cada uma uma etapa crítica com seu próprio SLA, do pedido à confirmação da entrega. Entender esse fluxo é o que permite decidir **quando** faz sentido prever o atraso (e evitar _leakage_).

**Entrada do pedido**, por dois canais:

- **Importação de grade:** o cliente envia uma planilha em lote (destinatários, endereços, itens e quantidades); usada em campanhas e alto volume.
- **Pedido web:** self-service por login; gera a solicitação automaticamente, com previsão de entrega pelo _lead time_.

**As fases** (códigos de duas letras, nomenclatura própria da TransBrasil):

| Fase | Nome | O que acontece |
|---|---|---|
| EA | Em Aprovação | validação hierárquica do pedido |
| PC | Pré-Conferência | confere produtos, quantidades e endereço |
| DC | Distribuição de Cotas | controle por canal de atendimento (esporádica) |
| **PL** | **Planejamento** | **alocação em janelas de produção e rotas** |
| EX | Em Análise | análise manual de urgências extremas (esporádica) |
| CF | Coleta Física | liberação para coleta física |
| ME | Manuseio | etiquetagem, pesagem, embalagem |
| EN | Emissão | **emissão da NF-e** contra o destinatário do ponto de entrega |
| EC | Expedição | consolidação no embarque (**gera a minuta**/romaneio), conferência de etiquetas, carregamento |
| CE | Confirmação de Entrega | confirmação e encerramento definitivo |

> **Nota de escopo (DC):** o subsistema de cotas é complexo e **fica fora da v1**; a fase existe no domínio (pedidos de grade podem passar por ela), mas sem regras próprias implementadas. Extensão futura registrada.

> **Documentos por fase:** cada etapa deixa rastro documental no lugar certo. As **ordens de coleta (DOC)** nascem na **CF**; a **NF-e** nasce na **EN** (carimba o pedido); a **minuta** (o romaneio do embarque consolidado) nasce na **EC**. O início e o fim de cada etapa ficam no histórico de fases do pedido, e é desse histórico que se mede **onde o pedido gargala**.

> **Por que isso importa para o modelo:** a previsão de atraso é feita logo **após o Planejamento (fase PL)**, quando o pedido ainda tem as fases CF, ME, EN, EC e CE pela frente (ainda dá para agir) e já há dados suficientes. Usar informação das fases posteriores como *feature* seria _leakage_, prever com dados que só existem depois.

## 3. As duas dores

### 3.1. Atrasos corroem o nível de serviço (OTIF)

**OTIF (_On Time, In Full_)** é o principal KPI logístico: mede se a entrega ocorreu **no prazo** e **completa**. _(Neste projeto, focamos o "On Time".)_ Quando o OTIF cai, a TransBrasil sofre:

- **Prejuízo contratual:** multas, glosas e cláusulas de OTIF mínimo (90 a 95%).
- **Prejuízo operacional:** troca não planejada de modalidade (rodoviário para aéreo), hora extra, reprocesso de documentação, contratação emergencial de transportadora.
- **Prejuízo reputacional:** desgaste com clientes-chave.
- **Perda de produtividade:** a operação "apaga incêndio" em vez de agir antes.
- **Falta de visibilidade:** hoje o risco de atraso só é percebido **quando já é tarde**.

### 3.2. A hipótese da Dna. Sarah: clientes que a empresa sustenta

Todo mês a Diretora Financeira fecha, à mão, o relatório de **margem de contribuição por operação**: `MC = receita - (custo variável + impostos)`, cruzando o que cada cliente **gera** (frete + armazenagem) com o que cada cliente **custa** (custo operacional das pernas, das bases, do galpão). E nesse fechamento ela percebeu algo incômodo: **alguns clientes grandes**, apesar do peso do nome na carteira, parecem **custar mais do que rendem**, como se a TransBrasil pagasse para mantê-los. Ela quer **certeza**, não intuição: um **raio-x completo do perfil operacional e das margens**, cliente a cliente, rota a rota. É um trabalho de **Data Discovery** pesado (estatística descritiva e inferencial), terminando com uma **recomendação** do que vale a pena prever adiante.

## 4. Como acessaremos os dados (definido com o João)

O Diretor de TI define **como cada fonte é servida**, e elas são diferentes de propósito, para o projeto exercitar cenários reais:

- **Operação (acompanhamento operacional):** acesso **direto ao banco de dados**, um **PostgreSQL** na nuvem (Neon).
- **Custos de transporte:** servidos por uma **API REST** (com chave de acesso), um sistema à parte, como costuma ser o financeiro.

> Consequência de engenharia: o projeto precisa ingerir de **duas fontes de natureza diferente** (banco + API) para uma camada única (bronze). É o que justifica a nossa **camada de conectores**, cada fonte entra por um conector nomeado, sem o pipeline saber "de onde". _(O detalhe das fontes e o modelo de dados ficam na Etapa 2, Entendimento dos Dados.)_

## 5. Traduzindo para problema de dados

### 5.1. Predição de atraso (OTIF)

- **Tipo:** classificação **binária** onde: `1 = atrasado`, `0 = no prazo`.
- **Alvo:** `atraso = data_entrega > prazo_limite_cliente`.
- **Momento da previsão:** logo após o **planejamento (fase PL)**, etapa ainda **controlável**, com dados suficientes e ação ainda possível (prever tarde demais não gera valor).
- **Natureza:** evento **raro** e de **custo assimétrico** (deixar passar um atraso dói mais que um falso alarme), a mesma classe de problema de **churn**. A métrica-guia é o **recall da classe "atraso"**, com _threshold_ definido por **custo de negócio**.
- **Modelagem:** sem modelo "eleito" de antemão. Começa por um **baseline honesto**, depois **compara candidatos** (regressão logística, árvores, _gradient boosting_ como XGBoost/LightGBM) e escolhe o vencedor por **validação temporal** e custo. Não existe um modelo melhor para todo problema (teorema do _No Free Lunch_).

### 5.2. Raio-x de margens (Data Discovery financeiro)

- **Natureza:** análise **descritiva e inferencial** do perfil de **margem de contribuição** por cliente, rota, modalidade e região (receita de frete + armazenagem × custo operacional), para **testar a hipótese da Dna. Sarah** com evidência.
- **Entregável:** a reconstrução **automatizada** do relatório mensal de MC + um relatório de diagnóstico, fechando com uma **recomendação** do que modelar/prever a seguir.

## 6. Restrições e riscos (conhecidos desde já)

- Muitos campos **nulos** e forte **heterogeneidade entre clientes** (SLAs variam por região, modalidade e operação).
- **Qualidade imperfeita de propósito:** dado sintético "limpinho" seria irreal. O gerador **planta sujeira realista** (nulos, duplicatas, chaves órfãs entre sistemas, formatos inconsistentes, itens sem valor fiscal), que chega **crua ao bronze**; o EDA de qualidade descobre os problemas e o tratamento **bronze → silver** os corrige com regras explícitas e testadas.
- **Risco de _leakage_:** não usar etapas/informações que só existem **depois** do momento da previsão.
- **Desbalanceamento** acentuado da classe "atraso".
- **Dados sintéticos:** representam a *estrutura* do domínio, não uma empresa real; todo número aqui é fabricado.

## 7. Critério de sucesso

O projeto percorre os quatro níveis da analítica: **descritiva** (o que aconteceu), **diagnóstica** (por que aconteceu), **preditiva** (o que vai acontecer) e **prescritiva** (o que fazer a respeito). Sucesso é:

1. Um modelo que **antecipe** o risco de atraso no momento certo, avaliado com honestidade (validação temporal, recall e custo).
2. Um diagnóstico de margens que **responda com evidência** à pergunta da Dna. Sarah.
3. Tudo **reprodutível** e **rastreável**: engenharia à altura da ciência.
4. **Comunicação à altura dos achados**, porque análise sem entrega não muda decisão:
   - **relatório executivo** dos achados (para a Dna. Sarah e a diretoria);
   - **relatório técnico** do modelo em produção (para o João/TI operar);
   - **apresentação** (slides) dos resultados.

---

[Início](#topo)
