<a id="topo"></a>

# Entendimento do Negócio · Trans Fictício BR (CRISP-DM · Etapa 1)

<!-- nav:start -->
[← Índice CRISP-DM](README.md) | [Entendimento dos Dados »](02_entendimento_dos_dados.md)
<!-- nav:end -->

> A primeira etapa do método CRISP-DM: entender o **negócio** antes dos dados. Este documento consolida as **entrevistas de discovery** com os stakeholders da Trans Fictício BR: a história da empresa, as pessoas, as dores e as perguntas que este projeto responde. Empresa, pessoas e dados são **100% fictícios**; declarações divergentes dos entrevistados foram **mantidas de propósito** (validá-las contra os dados é parte do trabalho).

> ⚠️ **A Trans Fictício BR não existe.** É uma empresa inventada para este portfólio, com dados gerados por código. Pessoas, clientes, números e conflitos narrados abaixo são ficção construída para exercitar o método de análise. **Qualquer semelhança com empresas reais, inclusive homônimas, é mera coincidência, e não há qualquer afiliação.**

## 1. A história da empresa

A **Trans Fictício BR** nasceu em **2010**, em Joinville/SC, como uma transportadora familiar: os primeiros clientes eram parentes e amigos do fundador, com fábricas, lojas e produção agrícola. Quando esses parceiros passaram a precisar guardar mercadoria antes de entregar, a empresa descobriu a **armazenagem**, e o alcance cresceu: da região para o Sul, do Sul para o Sudeste.

Até 2015, tudo era controlado em **planilhas e drive** ("um milagre", nas palavras do dono). Em **2016**, dois eventos mudaram a empresa: ela tornou-se **base regional de uma grande transportadora de São Paulo** (absorvendo, na prática, um treinamento completo do modelo de operação logística que replicaria depois com bases parceiras pelo país) e implantou o **TBW (Trans Fictício BR Warehouse)**, o WMS próprio construído pelo novo departamento de TI. É por isso que o histórico de dados começa em 2016.

Em **2017** chegaram os dois primeiros clientes MEGA: **Woonka Chocolates** e **Derma Health**, multinacionais com distribuição nacional. A credibilidade disparou, e entre **2018 e 2020** a carteira viveu seu boom (impulsionada também pelo salto logístico da pandemia). No auge, a Trans Fictício BR atendeu **~105 clientes ativos**, chegando a **45 GRANDES e 15 MEGA** simultâneos.

O sonho azedou: os grandes clientes passaram a **consumir a operação inteira**, os custos explodiram (horas extras, folha, freelancers), o nível de serviço derreteu e a reputação junto (avaliação no Google de 4.8 para 3.0). A partir de **2023** a saída de clientes acelerou; **2025 foi o ano do êxodo**, em todos os portes, com vários grandes migrando para a concorrência, mesmo depois de renegociações agressivas de contrato. Hoje (**2026**) a carteira tem **98 clientes ativos (20 GRANDES, 7 MEGA)**, nenhum cancelamento no ano e três entradas novas: os problemas continuam, em menor intensidade.

Foi o CEO de TI quem convenceu o dono a contratar um trabalho de dados: a empresa tem dois sistemas e nenhuma visão gerencial. Nas palavras dele, o BI mostra o passado e o presente; **"ver o futuro é com a gente"**.

## 2. As pessoas (o alto escalão é 100% familiar)

| Pessoa | Vínculo | Papel | O que traz ao projeto |
|---|---|---|---|
| **Sr. Abraão** | fundador, 83 anos | Presidência + operacional | visão, memória viva e as perguntas que ninguém responde |
| **Dna. Sarah** | esposa | Financeiro | fecha o relatório de margem à mão todo mês; quer saber quem sangra |
| **Sr. Elias** | cunhado | Dir. de Operações | **decide a priorização** quando a produção não dá conta |
| **João** | sobrinho | CEO de TI (criador do TBW) | patrocinador do projeto; quer IA e predição após o diagnóstico |
| **Samuel** | sobrinho | Coordenação (contas ativas) | o fluxo do pedido ponta a ponta |
| **Joel** | filho do Elias | Operacional | ocorrências, coletas e prazos no dia a dia |
| **Isaque** | filho | Dir. Comercial | prospecção ("trago clientes por uma porta...") |
| **Ismael** | filho | Marketing/relacionamento | "...e eles saem pela outra"; monitora a reputação digital |
| **Sr. José** | irmão | Compras | _(módulo futuro)_ |
| **Raquel** | cunhada | Contábil | _(módulo futuro)_ |

Governança por confiança e laço familiar, não por dado: um traço central da cultura, e parte do problema.

## 3. O processo: o ciclo de vida de um pedido

A operação segue um pipeline padronizado de **fases sequenciais**, cada uma com seu SLA interno (a régua `SLA_FASE`), do pedido à confirmação da entrega.

**Entrada do pedido**, por dois canais: **grade** (planilha em lote com centenas de destinatários; o canal das campanhas, e o que satura a esteira) e **pedido web** (self-service, item a item). No momento da criação o sistema promete os prazos pela régua de lead time, e o cliente escolhe o **nível de serviço**: PADRÃO (aguarda consolidação de carga) ou **EXCLUSIVO** (veículo dedicado imediato, ~3× o preço).

| Fase | Nome | O que acontece |
|---|---|---|
| EA | Em Aprovação | validação hierárquica do pedido |
| PC | Pré-Conferência | confere produtos, quantidades e endereço |
| DC | Distribuição de Cotas | controle por canal de atendimento (esporádica) |
| **PL** | **Planejamento** | **alocação em janelas de produção e rotas** |
| EX | Em Análise | urgências extremas (esporádica) |
| CF | Coleta Física | itens localizados; uma ordem de coleta por local |
| ME | Manuseio | etiquetagem, pesagem, embalagem |
| EN | Emissão | emissão da NF-e |
| EC | Expedição | consolidação em minutas; o caminhão sai |
| CE | Confirmação de Entrega | chegada confirmada (direta, via base ou retirada) |

> **Documentos por fase:** a NF-e nasce na EN; a minuta (romaneio do embarque) nasce na EC; as ordens de coleta nascem na CF. Início e fim de cada etapa ficam no histórico de fases, é dele que se mede onde o pedido gargala.

> **Por que isso importa para o modelo:** a previsão de atraso é feita logo **após o Planejamento (PL)**, etapa ainda controlável, com dados suficientes e ação possível. Usar informação de fases posteriores seria _leakage_.

## 4. Sistemas e acesso aos dados (definido com o João)

- **TBW**: o WMS próprio, ponta a ponta (pedido → entrega), servido por acesso direto ao **PostgreSQL**.
- **Financeiro**: sistema **terceiro** que lê o TBW; servido por **API REST** com chave. É dele que a Dna. Sarah extrai, manualmente, o relatório mensal de margem de contribuição (`MC_por_SS_OS`).
- **A dor de dados**: dois sistemas, TI própria e **nenhum relatório gerencial**. O dado existe; a informação, não.

## 5. As dores, na voz de quem as sente

- **Operação**: "não sei quantas linhas/dia minha produção aguenta, nem quanto estou estressando a esteira"; pedidos de grandes clientes chegam em grades que consomem a produção; quando não dá para todos, o Sr. Elias prioriza os maiores, e o chão da fábrica executa o sacrifício.
- **Estoque**: o físico não bate com o sistema; itens somem e só aparecem em inventário (4 a 5 por ano); parte do galpão está tomada por material parado há mais de um ano, o que motivou uma **política de cobrança progressiva por aging** (sobretaxa de +30% a +180% conforme o tempo parado).
- **Financeiro (Dna. Sarah)**: "quem me dá lucro? quem me dá prejuízo? onde vaza margem: transporte, armazenagem, coleta, positivação, impostos? qual meu ponto de equilíbrio? quais foram meus anos de ouro e de escassez?"
- **Comercial/relacionamento**: "meus filhos trazem clientes por uma porta e eles saem pela outra". A frase ouvida na saída, que doeu no dono: *"você só dá atenção para as suas empresas grandes e nos trata como lixo"*. Os ~10 clientes mais antigos (amigos pessoais do fundador) permanecem, mas já cotam concorrência.
- **Bases**: 36 parceiras pelo país, nenhuma nunca trocada, **nenhum indicador de performance** sobre elas.
- **Contratos**: OTIF contratual de 90% (micro/pequeno/médio) a 95-97% (grandes/mega); houve renegociações desesperadas a 98% que não seguraram os clientes. Abaixo do contratado, multa.

## 6. Números declarados (a validar contra os dados)

As entrevistas produziram números **parcialmente divergentes**, mantidos aqui como declarados, porque reconciliá-los é tarefa do diagnóstico:

- Painéis operacionais (2025): **221 mil pedidos**, **983 mil linhas**, forte concentração (7 clientes ≈ 79% do volume) e **queda de volume ao longo do ano**.
- Financeiro (jun/2026): transporte ~R$ 1,3 Mi/mês + armazenagem ~R$ 175 mil/mês.
- Dono: "receita média de 670 mil por cliente"; top 5 declarado: Woonka (3,7 Mi/ano), Derma Health (3,6), Stark Technologi (3,6), Lux Acessórios & Moda (2,0), Green Chemmical (1,5).
- Capacidade de produção: o dono estima "~600 linhas/dia, operando além"; os painéis registram ~2.950 linhas/dia.

## 7. Traduzindo para problema de dados

### 7.1. Predição de atraso (OTIF)

- Classificação **binária** (`1 = atrasado`), alvo `atraso = data_entrega > prazo_limite`, medida no ponto correto por forma de atendimento (na retirada em base, o prazo é a chegada à base).
- Momento da previsão: **pós-PL**. Evento raro, custo assimétrico, recall como métrica-guia, threshold por custo, mesma família do churn.
- Baseline honesto primeiro; candidatos comparados por **validação temporal**; sem modelo eleito a priori.

### 7.2. Raio-x de margens (Data Discovery)

- Reconstruir o relatório de MC da Dna. Sarah por pipeline (receita × custos × impostos por operação) e responder com evidência: **quem sustenta a Trans Fictício BR e quem é sustentado por ela**, por cliente, porte, stream e período, incluindo os efeitos do serviço exclusivo, do aging de estoque e das multas contratuais.

## 8. Restrições e riscos

- Campos nulos, heterogeneidade entre clientes, desbalanceamento do alvo.
- **Risco de leakage** (fases posteriores ao PL).
- **Qualidade de dados imperfeita por natureza** (dois sistemas sem FK entre si, cadastros digitados por humanos): o tratamento bronze → silver e o relatório de qualidade fazem parte da entrega.
- Dados sintéticos: estrutura fiel ao domínio, números fabricados.

## 9. Critério de sucesso

O projeto percorre os quatro níveis da analítica: **descritiva** (o que aconteceu), **diagnóstica** (por que), **preditiva** (o que vai acontecer) e **prescritiva** (o que fazer). Sucesso é:

1. Modelo que antecipe o risco de atraso no momento certo, avaliado com honestidade.
2. Diagnóstico de margens que responda às perguntas da Dna. Sarah com evidência.
3. Tudo reprodutível e rastreável.
4. **Comunicação à altura**: relatório executivo (diretoria), relatório técnico do modelo (TI) e apresentação dos achados, incluindo a seção de **qualidade dos dados**.

---

[Início](#topo)
