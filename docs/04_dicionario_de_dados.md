<a id="topo"></a>

# Dicionário de Dados

<!-- nav:start -->
[← Documentação](README.md) | [Entendimento dos Dados](02_entendimento_dos_dados.md)
| [Acesso aos dados](03_acesso_aos_dados.md)
<!-- nav:end -->

> Referência de consulta das 30 tabelas das duas fontes. **Gerado a partir do
> banco** por `uv run python -m logistica_otif_mlops.dicionario`: a estrutura vem do
> `information_schema` e a semântica de um glossário curado no próprio script, então
> uma migration nova nunca deixa este documento mentindo.
>
> Legenda: 🔑 chave primária · 🔗 chave estrangeira · `NOT NULL` obrigatório.


## Schema `operacao` · Sistema Operacional (TBW)


### `operacao.campanha`  ·  66 linhas

Calendário comercial (Páscoa, Mães, Black Friday, Natal). É a alavanca da sazonalidade e o momento em que a operação estoura.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `descricao` | texto(120) | sim |  |
| `dt_inicio` | data | sim | Data/hora do evento. |
| `dt_fim` | data | sim | Data/hora do evento. |

### `operacao.coleta`  ·  4.051 linhas

Ordem de serviço reversa: buscar material fora (descarte ou retorno ao estoque).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `numero` | texto(20) | sim |  |
| 🔗 `cliente_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| 🔗 `endereco_origem_id` | inteiro | sim | Referencia `operacao.endereco`. |
| 🔗 `local_estoque_destino_id` | inteiro | sim | Referencia `operacao.local_estoque`. |
| 🔗 `transportador_id` | inteiro | sim | Referencia `operacao.transportador`. |
| 🔗 `veiculo_id` | inteiro | — | Referencia `operacao.veiculo`. |
| `dt_solicitacao` | data/hora | sim | Data/hora do evento. |
| `dt_prevista` | data | sim | Data/hora do evento. |
| `dt_coleta` | data/hora | — | Data/hora do evento. |
| `peso_kg` | decimal(12,3) | sim |  |
| `volume_m3` | decimal(12,4) | sim |  |
| `finalidade` | texto(16) | sim |  |
| `status` | texto(11) | sim |  |

### `operacao.endereco`  ·  19.697 linhas

Ponto no mapa de qualquer organização. Para destinatário, guarda também o nome do local e o documento (a NF é emitida contra ele).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `organizacao_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| `nome_local` | texto(150) | sim |  |
| `documento` | texto(14) | — |  |
| `logradouro` | texto(200) | sim |  |
| `bairro` | texto(80) | sim |  |
| `cidade` | texto(80) | sim |  |
| `uf` | texto(2) | sim |  |
| `cep` | texto(8) | sim |  |
| `latitude` | decimal(9,6) | — |  |
| `longitude` | decimal(9,6) | — |  |
| `fl_principal` | sim/não | sim | Indicador. |

### `operacao.entrega`  ·  2.664.991 linhas

Uma perna do trajeto (direta, transferência para base ou última milha). Um pedido pode ter várias.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `pedido_id` | inteiro | sim | Referencia `operacao.pedido`. |
| 🔗 `minuta_id` | inteiro | sim | Referencia `operacao.minuta`. |
| `tipo_perna` | texto(20) | sim | DIRETA, TRANSFERENCIA_BASE ou ULTIMA_MILHA_BASE. |
| 🔗 `endereco_destino_id` | inteiro | sim | Referencia `operacao.endereco`. |
| `dt_prevista` | data | sim | Data/hora do evento. |
| `dt_chegada` | data/hora | — | Data/hora do evento. |
| `recebedor` | texto(100) | — |  |
| `fl_sucesso` | sim/não | — | Tri-estado: NULO = em trânsito (desfecho desconhecido), true = entregue, false = tentativa falhou. |
| `fl_canhoto` | sim/não | sim | Comprovante recebido. Sem ele, a cobrança fica exposta a contestação. |
| `dt_entrada_base` | data/hora | — | Quando a base EFETIVOU a entrada. A diferença para `dt_chegada` é responsabilidade da base (cabe repasse de multa). |

### `operacao.estoque_snapshot`  ·  56.008 linhas

Foto mensal do saldo por item × local. É a base da cobrança de armazenagem e do cálculo de aging.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `data` | data | sim |  |
| 🔗 `item_id` | inteiro | sim | Referencia `operacao.item`. |
| 🔗 `local_estoque_id` | inteiro | sim | Referencia `operacao.local_estoque`. |
| `qtde_saldo` | inteiro | sim |  |
| `m3_ocupado` | decimal(12,4) | sim | Espaço ocupado na foto. Multiplicado pela tarifa e pelo fator de aging, vira a cobrança do mês. |
| `valor_material` | decimal(14,2) | sim |  |
| `valor_danificado` | decimal(14,2) | sim | Parcela avariada, para provisão. |

### `operacao.fase`  ·  10 linhas

As dez etapas do ciclo de vida do pedido (EA → CE).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `codigo` | texto(2) | sim |  |
| `nome` | texto(60) | sim |  |
| `ordem` | inteiro | sim |  |
| `fl_esporadica` | sim/não | sim | Indicador. |

### `operacao.item`  ·  6.804 linhas

Catálogo por cliente (SKU). O material é do cliente; a TransBrasil apenas guarda e movimenta.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `cliente_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| `codigo` | texto(30) | sim |  |
| `descricao` | texto(200) | sim |  |
| `grupo` | texto(60) | sim |  |
| `subgrupo` | texto(60) | sim |  |
| `peso_kg` | decimal(10,3) | sim |  |
| `volume_m3` | decimal(10,4) | sim |  |
| `valor_unitario` | decimal(12,2) | — |  |
| `ativo` | sim/não | sim |  |

### `operacao.lead_time`  ·  126 linhas

Régua de prazo prometido por modalidade × UF × cidade. É referência, não medição.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `modalidade_id` | inteiro | sim | Referencia `operacao.modalidade`. |
| `uf` | texto(2) | sim |  |
| `cidade` | texto(80) | sim |  |
| `dias_uteis` | inteiro | sim |  |

### `operacao.local_estoque`  ·  40 linhas

Galpão da matriz ou depósito de base. É onde a coleta física acontece, e a divisão por local gera as ordens de coleta.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `organizacao_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| `codigo` | texto(10) | sim |  |
| `nome` | texto(80) | sim |  |
| `ativo` | sim/não | sim |  |

### `operacao.minuta`  ·  214.692 linhas

O embarque: consolida pedidos de vários clientes num veículo. `tipo_carga` distingue carga consolidada de veículo dedicado.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `numero` | texto(20) | sim |  |
| 🔗 `transportador_id` | inteiro | sim | Referencia `operacao.transportador`. |
| 🔗 `veiculo_id` | inteiro | — | Referencia `operacao.veiculo`. |
| 🔗 `rota_id` | inteiro | sim | Referencia `operacao.rota`. |
| `tipo_carga` | texto(12) | sim |  |
| `dt_expedicao` | data/hora | sim | Data/hora do evento. |
| 🔗 `modalidade_id` | inteiro | sim | Referencia `operacao.modalidade`. |

### `operacao.modalidade`  ·  2 linhas

Modal do transporte: rodoviário ou aéreo.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `codigo` | texto(15) | sim |  |
| `ativo` | sim/não | sim |  |
| `descricao` | texto(30) | sim |  |

### `operacao.ocorrencia`  ·  48.793 linhas

Evento anormal registrado no pedido ou na entrega.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `pedido_id` | inteiro | sim | Referencia `operacao.pedido`. |
| 🔗 `entrega_id` | inteiro | — | Referencia `operacao.entrega`. |
| 🔗 `tipo_ocorrencia_id` | inteiro | sim | Referencia `operacao.tipo_ocorrencia`. |
| `dt_ocorrencia` | data/hora | sim | Data/hora do evento. |
| `observacao` | texto(255) | — |  |
| `dt_cancelada` | data/hora | — | Data/hora do evento. |

### `operacao.ordem_coleta`  ·  3.662.275 linhas

A divisão da coleta por local de estoque (o 'DOC'). Cada local fecha no seu ritmo, e o mais lento define o fim da coleta.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `pedido_id` | inteiro | sim | Referencia `operacao.pedido`. |
| 🔗 `local_estoque_id` | inteiro | sim | Referencia `operacao.local_estoque`. |
| `dt_emissao` | data/hora | sim | Data/hora do evento. |
| `dt_conclusao` | data/hora | — | Data/hora do evento. |
| `status` | texto(10) | sim |  |

### `operacao.organizacao`  ·  240 linhas

Party pattern: cliente, base parceira e a própria matriz vivem na mesma tabela, distinguidos por `tipo_parceria`.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `sigla` | texto(10) | sim | Código de 3 letras. Chave de negócio usada pelo financeiro (que não tem FK para cá). |
| `razao_social` | texto(150) | sim |  |
| `nome_fantasia` | texto(150) | sim |  |
| `cnpj` | texto(14) | sim |  |
| `tipo_parceria` | texto(10) | sim | CLIENTE, BASE ou MATRIZ. |
| `porte` | texto(10) | — |  |
| `segmento` | texto(40) | — |  |
| `fl_entrega_agendada` | sim/não | — | Indicador. |
| `dt_inicio_contrato` | data | sim | Data/hora do evento. |
| `dt_cancelamento` | data | — | Fim da vigência. Depois desta data o cliente não pode ter pedido (regra conferida na validação global). |
| `ativo` | sim/não | sim |  |
| `otif_contratual` | decimal(4,2) | — | Percentual de pontualidade acordado em contrato. Abaixo dele, cabe multa. |

### `operacao.pedido`  ·  1.776.391 linhas

O pedido de expedição (a 'SS'). Grão central do domínio.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `numero` | texto(20) | sim | A 'SS'. Chave de NEGÓCIO (texto, com zeros à esquerda): é por ela que o financeiro reconcilia. Nunca use o `id` para isso. |
| 🔗 `cliente_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| 🔗 `endereco_id` | inteiro | sim | Referencia `operacao.endereco`. |
| 🔗 `modalidade_id` | inteiro | sim | Referencia `operacao.modalidade`. |
| 🔗 `campanha_id` | inteiro | — | Referencia `operacao.campanha`. |
| `canal` | texto(5) | sim | GRADE (rotina programada) ou WEB (avulso). |
| `tipo_atendimento` | texto(20) | — | ENTREGA_DIRETA, ENTREGA_VIA_BASE ou RETIRA_BASE. **Define qual marco mede o cumprimento do prazo.** |
| `dt_solicitacao` | data/hora | sim | Data/hora do evento. |
| `dt_prazo_saida_expedicao` | data | sim | Prazo INTERNO: até quando a esteira deve liberar. Responsabilidade da produção. |
| `dt_prazo_entrega` | data | sim | Prazo prometido ao CLIENTE. É contra ele que se mede o OTIF. |
| `peso_teorico_kg` | decimal(12,3) | sim |  |
| `volume_teorico_m3` | decimal(12,4) | sim |  |
| `peso_real_kg` | decimal(12,3) | — | Aferido na balança. Nulo quando não se pesou (~3% dos casos): use o teórico como alternativa, sinalizando a troca. |
| `volume_real_m3` | decimal(12,4) | — |  |
| `nf_numero` | texto(20) | — | Só existe depois da fase EN. Preenchê-lo antes seria vazamento de futuro em qualquer modelo preditivo. |
| `nivel_servico` | texto(10) | sim | PADRAO ou EXCLUSIVO (veículo dedicado, ~3× o preço, fura a fila). |

### `operacao.pedido_fase`  ·  14.589.229 linhas

Formato LONGO: um registro por passagem de fase. A visão em colunas é derivação, nunca armazenamento.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `pedido_id` | inteiro | sim | Referencia `operacao.pedido`. |
| 🔗 `fase_id` | inteiro | sim | Referencia `operacao.fase`. |
| `dt_entrada` | data/hora | sim | Data/hora do evento. |
| `dt_saida` | data/hora | — | NULO = fase em andamento. É assim que se identifica a carteira em voo. |

### `operacao.pedido_item`  ·  7.728.077 linhas

Linha do pedido. `quantidade` conta VOLUMES (caixas), que é como o galpão e o painel contam.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `pedido_id` | inteiro | sim | Referencia `operacao.pedido`. |
| 🔗 `item_id` | inteiro | sim | Referencia `operacao.item`. |
| `quantidade` | inteiro | sim |  |

### `operacao.positivacao`  ·  3.437 linhas

Ordem de serviço de montagem do material no ponto de venda ou evento, executada por parceiro local.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `numero` | texto(20) | sim |  |
| 🔗 `cliente_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| 🔗 `pedido_id` | inteiro | — | Referencia `operacao.pedido`. |
| 🔗 `endereco_id` | inteiro | sim | Referencia `operacao.endereco`. |
| 🔗 `campanha_id` | inteiro | — | Referencia `operacao.campanha`. |
| `parceiro_nome` | texto(150) | sim |  |
| `dt_abertura` | data | sim | Data/hora do evento. |
| `dt_servico` | data | — | Data/hora do evento. |
| `status` | texto(10) | sim |  |

### `operacao.recebimento`  ·  60.623 linhas

Entrada de material do cliente no galpão (o abastecimento).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `item_id` | inteiro | sim | Referencia `operacao.item`. |
| 🔗 `local_estoque_id` | inteiro | sim | Referencia `operacao.local_estoque`. |
| `numero_agendamento` | texto(20) | — |  |
| `fornecedor_nome` | texto(150) | — |  |
| `nf_entrada` | texto(20) | sim |  |
| `quantidade` | inteiro | sim |  |
| `dt_validade` | data | — | Vencimento do lote. Saldo com validade expirada é estoque perdido, e o cliente costuma descobrir tarde. |
| `dt_prevista` | data | sim | Data/hora do evento. |
| `dt_recebimento` | data/hora | — | Data/hora do evento. |
| `status` | texto(10) | sim |  |

### `operacao.retirada_base`  ·  364.905 linhas

Quando o cliente retira o material no galpão ou na base.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `pedido_id` | inteiro | sim | Referencia `operacao.pedido`. |
| 🔗 `base_id` | inteiro | sim | Referencia `operacao.organizacao`. |
| `dt_retirada` | data/hora | sim | Data/hora do evento. |
| `retirado_por` | texto(100) | sim |  |

### `operacao.rota`  ·  28 linhas

Agrupamento comercial de destinos (por UF/região).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `codigo` | texto(20) | sim |  |
| `descricao` | texto(120) | sim |  |
| `uf` | texto(2) | sim |  |

### `operacao.sla_fase`  ·  9 linhas

Meta e limite interno de duração de cada fase, em horas.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `fase_id` | inteiro | sim | Referencia `operacao.fase`. |
| `horas_uteis_meta` | inteiro | sim |  |
| `horas_uteis_limite` | inteiro | sim |  |

### `operacao.tipo_ocorrencia`  ·  8 linhas

Catálogo de eventos anormais (avaria, ausência, divergência). `fl_impacta_prazo` diz se conta contra o SLA.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `codigo` | texto(30) | sim |  |
| `descricao` | texto(120) | sim |  |
| `fl_impacta_prazo` | sim/não | sim | Indicador. |

### `operacao.transportador`  ·  19 linhas

Frota própria, transportadora, agregado ou carreteiro.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `nome` | texto(150) | sim |  |
| `cnpj` | texto(14) | — |  |
| `tipo` | texto(15) | sim |  |
| `ativo` | sim/não | sim |  |

### `operacao.veiculo`  ·  78 linhas

Veículo com placa e tipo. Embarque aéreo não tem veículo.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| 🔗 `transportador_id` | inteiro | sim | Referencia `operacao.transportador`. |
| `placa` | texto(8) | sim |  |
| `tipo_veiculo` | texto(30) | sim |  |
| `capacidade_kg` | decimal(10,2) | sim |  |

## Schema `custos` · Sistema Financeiro (terceiro, via API)


### `custos.categoria_custo`  ·  7 linhas

Classificação do custo variável.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `codigo` | texto(15) | sim |  |
| `descricao` | texto(60) | sim |  |

### `custos.custo_operacao`  ·  3.083.852 linhas

Custo variável por operação/competência (o que se paga).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `cliente_sigla` | texto(10) | sim |  |
| `referencia_numero` | texto(20) | — |  |
| 🔗 `categoria_custo_id` | inteiro | sim | Referencia `custos.categoria_custo`. |
| `prestador_nome` | texto(150) | sim | Texto livre: é sistema de terceiro e não há FK para o cadastro de transportadores. |
| `valor` | decimal(14,2) | sim |  |
| `dt_competencia` | data | sim | Competência do custo. Pode ser POSTERIOR à da receita (nota que chega atrasada): reconcilie pela operação, não pelo mês. |

### `custos.faturamento_operacao`  ·  1.782.616 linhas

Receita por operação/competência (o que se cobra).

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `cliente_sigla` | texto(10) | sim |  |
| `referencia_numero` | texto(20) | — | SS ou OS. NULO na ARMAZENAGEM, que fatura por competência e não por operação. |
| `tipo_operacao` | texto(12) | sim |  |
| `competencia` | texto(7) | sim |  |
| `valor_com_icms` | decimal(14,2) | sim | Receita da linha. **Pode ser negativo** (estorno de nota cancelada): some com o sinal, nunca com abs(). |
| `valor_icms` | decimal(14,2) | sim |  |
| `dt_faturamento` | data | sim | Data/hora do evento. |

### `custos.parametro_financeiro`  ·  13 linhas

Parâmetros de negócio (impostos, cubagem, aging, custo de servir). Quem calcula MC LÊ daqui, não repete o número.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `chave` | texto(50) | sim |  |
| `valor` | decimal(12,6) | sim |  |
| `descricao` | texto(200) | sim |  |

### `custos.tarifa_armazenagem`  ·  114 linhas

Régua de cobrança de armazenagem por cliente.

| Coluna | Tipo | Obrig. | Significado |
|---|---|---|---|
| 🔑 `id` | inteiro | sim | Chave técnica (sequencial). Não use como chave de negócio. |
| `cliente_sigla` | texto(10) | sim |  |
| `valor_m3` | decimal(10,2) | sim |  |
| `aliquota_ad_valorem` | decimal(6,4) | sim |  |
| `valor_minimo_mensal` | decimal(12,2) | sim |  |

---

[Início](#topo)

