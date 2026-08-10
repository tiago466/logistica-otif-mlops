-- =====================================================================
-- RELATÓRIO DE PRAZOS POR ETAPA  (pedido do Sr. Elias)
-- =====================================================================
-- Reproduz o layout `prazo_etapas.xlsx`: UMA LINHA POR PEDIDO, com as fases
-- abertas em colunas (formato largo) e a duração de cada etapa.
--
-- Convenções extraídas do relatório de referência:
--   * horas = diferença CORRIDA entre a etapa e a anterior, arredondada
--     (conferido: 100% das linhas do arquivo batem com hora corrida)
--   * dias  = diferença de DATAS DE CALENDÁRIO, não `horas/24`
--     (por isso a razão horas/dias varia de 9 a 34 no arquivo original)
--
-- Régua de cumprimento de prazo (definida pelo Sr. Elias em 04/08/2026):
--   ENTREGA (direta ou via base) → chegada da entrega efetiva
--   RETIRA em galpão TransBrasil → fim do MANUSEIO (material pronto)
--   RETIRA em base               → entrada na base
--   O princípio: a TransBrasil responde até deixar o material DISPONÍVEL;
--   a demora do cliente em buscar não conta contra a operação.
--
-- Parâmetro: ajuste a janela no filtro final (hoje: mês de referência).
-- =====================================================================

with
-- ---------------------------------------------------------------------
-- 1. As fases em COLUNAS. `filter` é o pivot nativo do Postgres: mais
--    legível e mais rápido que dez subconsultas correlacionadas.
-- ---------------------------------------------------------------------
fases as (
  select pf.pedido_id,
         max(pf.dt_entrada) filter (where f.codigo = 'EA') as ea_inicio,
         max(pf.dt_saida)   filter (where f.codigo = 'EA') as ea_fim,
         max(pf.dt_saida)   filter (where f.codigo = 'PC') as pc_fim,
         max(pf.dt_saida)   filter (where f.codigo = 'DC') as dc_fim,
         max(pf.dt_saida)   filter (where f.codigo = 'PL') as pl_fim,
         max(pf.dt_entrada) filter (where f.codigo = 'EX') as ex_inicio,
         max(pf.dt_saida)   filter (where f.codigo = 'EX') as ex_fim,
         max(pf.dt_entrada) filter (where f.codigo = 'CF') as cf_inicio,
         max(pf.dt_saida)   filter (where f.codigo = 'CF') as cf_fim,
         max(pf.dt_entrada) filter (where f.codigo = 'ME') as me_inicio,
         max(pf.dt_saida)   filter (where f.codigo = 'ME') as me_fim,
         max(pf.dt_saida)   filter (where f.codigo = 'EN') as en_fim,
         max(pf.dt_entrada) filter (where f.codigo = 'EC') as ec_inicio,
         max(pf.dt_saida)   filter (where f.codigo = 'EC') as ec_fim,
         max(pf.dt_entrada) filter (where f.codigo = 'CE') as ce_inicio,
         max(pf.dt_saida)   filter (where f.codigo = 'CE') as ce_fim
  from operacao.pedido_fase pf
  join operacao.fase f on f.id = pf.fase_id
  group by 1
),
-- ---------------------------------------------------------------------
-- 2. A FASE ATUAL: a etapa aberta (sem saída). Se todas fecharam, o pedido
--    está concluído. Nunca guarde isso em coluna: derive sempre.
-- ---------------------------------------------------------------------
fase_atual as (
  select distinct on (pf.pedido_id)
         pf.pedido_id, f.codigo as cod_fase, f.nome as fase
  from operacao.pedido_fase pf
  join operacao.fase f on f.id = pf.fase_id
  where pf.dt_saida is null
  order by pf.pedido_id, f.ordem desc
),
-- ---------------------------------------------------------------------
-- 3. DOC (divisão da ordem de coleta): quantas frentes e a janela total.
--    Cada local fecha no seu ritmo; a coleta acaba quando o último fecha.
-- ---------------------------------------------------------------------
doc as (
  select pedido_id,
         count(*) as qtde_doc,
         min(dt_emissao) as doc_emissao,
         max(dt_conclusao) as doc_conclusao
  from operacao.ordem_coleta
  group by 1
),
itens as (
  select pedido_id, count(*) as qtde_itens, sum(quantidade) as volumes
  from operacao.pedido_item
  group by 1
),
-- ---------------------------------------------------------------------
-- 4. O EMBARQUE: minuta, transportador e veículo da primeira perna.
--    `distinct on` pega uma linha por pedido (o Postgres resolve isso
--    melhor que window function quando se quer só a primeira).
-- ---------------------------------------------------------------------
embarque as (
  select distinct on (e.pedido_id)
         e.pedido_id, m.numero as minuta, m.dt_expedicao,
         m.tipo_carga, t.nome as transportador,
         v.placa, v.tipo_veiculo, r.codigo as rota
  from operacao.entrega e
  join operacao.minuta m on m.id = e.minuta_id
  join operacao.transportador t on t.id = m.transportador_id
  left join operacao.veiculo v on v.id = m.veiculo_id
  left join operacao.rota r on r.id = m.rota_id
  where e.tipo_perna in ('DIRETA', 'TRANSFERENCIA_BASE')
  order by e.pedido_id, e.id
),
-- ---------------------------------------------------------------------
-- 5. A ENTREGA FINAL e a PASSAGEM PELA BASE, cada uma com seu papel na
--    régua de prazo. Entrega em trânsito tem `fl_sucesso` nulo: por isso
--    o filtro é `is true`, e não apenas `fl_sucesso`.
-- ---------------------------------------------------------------------
entrega_final as (
  select e.pedido_id,
         max(e.dt_chegada) as dt_entrega,
         max(e.recebedor)  as recebedor
  from operacao.entrega e
  where e.fl_sucesso is true
    and e.tipo_perna in ('DIRETA', 'ULTIMA_MILHA_BASE')
  group by 1
),
passagem_base as (
  select e.pedido_id,
         max(e.dt_chegada) as chegada_base,
         max(e.dt_entrada_base) as entrada_base,
         -- MATRIZ = retirada no galpão da TransBrasil; BASE = parceira
         max(o.tipo_parceria) as tipo_local,
         max(o.nome_fantasia) as parceiro
  from operacao.entrega e
  join operacao.endereco en on en.id = e.endereco_destino_id
  join operacao.organizacao o on o.id = en.organizacao_id
  where e.tipo_perna = 'TRANSFERENCIA_BASE'
  group by 1
),
retirada as (
  select pedido_id, max(dt_retirada) as dt_retirada, max(retirado_por) as retirado_por
  from operacao.retirada_base
  group by 1
),
-- ---------------------------------------------------------------------
-- 6. Últimas ocorrências (o relatório mostra as duas mais recentes)
-- ---------------------------------------------------------------------
ocorrencias as (
  select pedido_id,
         (array_agg(descricao order by dt_ocorrencia desc))[1] as ultima_ocorrencia,
         (array_agg(descricao order by dt_ocorrencia desc))[2] as penultima_ocorrencia
  from (
    select o.pedido_id, o.dt_ocorrencia, t.descricao
    from operacao.ocorrencia o
    join operacao.tipo_ocorrencia t on t.id = o.tipo_ocorrencia_id
  ) x
  group by 1
),
-- ---------------------------------------------------------------------
-- 7. O CORAÇÃO: quando o material ficou DISPONÍVEL para o cliente.
--    É esta coluna que decide "no prazo" ou "em atraso", e ela muda
--    conforme quem tem a responsabilidade na ponta.
-- ---------------------------------------------------------------------
base as (
  select
    p.id, p.numero as ss, p.nf_numero, p.dt_solicitacao,
    p.dt_prazo_saida_expedicao, p.dt_prazo_entrega,
    p.tipo_atendimento, p.nivel_servico, p.canal,
    coalesce(p.peso_real_kg, p.peso_teorico_kg) as peso_kg,
    coalesce(p.volume_real_m3, p.volume_teorico_m3) as m3,
    o.sigla as cliente, o.nome_fantasia as nome, o.porte, o.segmento,
    md.codigo as modal,
    en.nome_local as destino, en.cidade, en.uf, en.cep,
    case when en.uf in ('SP','RJ','MG','ES') then 'Sudeste'
         when en.uf in ('PR','SC','RS') then 'Sul'
         when en.uf in ('MT','MS','GO','DF') then 'Centro Oeste'
         when en.uf in ('AM','PA','AC','RO','RR','AP','TO') then 'Norte'
         else 'Nordeste' end as regiao,
    f.*, fa.cod_fase, fa.fase,
    d.qtde_doc, d.doc_emissao, d.doc_conclusao,
    i.qtde_itens, i.volumes,
    emb.minuta, emb.dt_expedicao, emb.tipo_carga, emb.transportador,
    emb.placa, emb.tipo_veiculo, emb.rota,
    ef.dt_entrega, ef.recebedor,
    pb.chegada_base, pb.entrada_base, pb.tipo_local, pb.parceiro,
    ret.dt_retirada, ret.retirado_por,
    oc.ultima_ocorrencia, oc.penultima_ocorrencia,
    -- ↓↓↓ A RÉGUA DO SR. ELIAS ↓↓↓
    case
      when p.tipo_atendimento = 'RETIRA_BASE' and pb.tipo_local = 'MATRIZ'
        then f.me_fim                 -- retirada no galpão: pronto = fim do manuseio
      when p.tipo_atendimento = 'RETIRA_BASE'
        then pb.entrada_base          -- retirada em base: pronto = entrada na base
      else ef.dt_entrega              -- entrega: vale a chegada no cliente
    end as dt_disponivel
  from operacao.pedido p
  join operacao.organizacao o on o.id = p.cliente_id
  join operacao.endereco en on en.id = p.endereco_id
  join operacao.modalidade md on md.id = p.modalidade_id
  left join fases f on f.pedido_id = p.id
  left join fase_atual fa on fa.pedido_id = p.id
  left join doc d on d.pedido_id = p.id
  left join itens i on i.pedido_id = p.id
  left join embarque emb on emb.pedido_id = p.id
  left join entrega_final ef on ef.pedido_id = p.id
  left join passagem_base pb on pb.pedido_id = p.id
  left join retirada ret on ret.pedido_id = p.id
  left join ocorrencias oc on oc.pedido_id = p.id
  where p.dt_solicitacao >= date '2026-07-01'   -- ← janela do relatório
    and p.dt_solicitacao <  date '2026-08-01'
)
select
  cliente                                   as "Cliente",
  nome                                      as "Nome",
  ss                                        as "SS",
  nf_numero                                 as "NF",
  transportador                             as "Transportador",
  parceiro                                  as "Transp. Parceiro",
  tipo_veiculo                              as "Tipo Veículo",
  placa                                     as "Placa",
  rota                                      as "Rota",
  destino                                   as "Destino",
  regiao                                    as "Região",
  uf                                        as "UF",
  cidade                                    as "Cidade",
  cep                                       as "CEP",
  cod_fase                                  as "Cód. Fase",
  coalesce(fase, 'Concluído')               as "Fase",
  -- o relatório de origem junta três conceitos num campo só; aqui eles
  -- existem separados e são recombinados para bater com o layout
  case when nivel_servico = 'EXCLUSIVO' then 'EXCLUSIVO'
       when tipo_atendimento = 'RETIRA_BASE' then 'RETIRA'
       when modal = 'AEREO' then 'AEREO'
       else 'RODOVIARIO' end                as "Modalidade",
  recebedor                                 as "Recebedor",
  case when dt_disponivel is null then 'Em andamento' else 'Entregue' end as "Status",
  penultima_ocorrencia                      as "Penúltima Ocorrência",
  ultima_ocorrencia                         as "Última Ocorrência",
  qtde_itens                                as "Qtde. Itens",
  volumes                                   as "Volume",
  peso_kg                                   as "Peso",
  round(m3 * 300, 2)                        as "Peso Cubado Rodoviário",
  m3                                        as "M³",
  dt_solicitacao                            as "Data Solicitação",
  -- ---- Pré-Conferência ----
  pc_fim                                    as "Data Pré Conferência",
  round(extract(epoch from (pc_fim - dt_solicitacao)) / 3600)   as "Horas Pré-Conferência",
  (pc_fim::date - dt_solicitacao::date)                         as "Dias Pré-Conferência",
  -- ---- Distribuição de Cotas ----
  dc_fim                                    as "Data Distribuição de Cotas",
  round(extract(epoch from (dc_fim - pc_fim)) / 3600)           as "Horas Distribuição",
  (dc_fim::date - pc_fim::date)                                 as "Dias Distribuição",
  -- ---- Planejamento ----
  pl_fim                                    as "Data Planejamento",
  round(extract(epoch from (pl_fim - coalesce(dc_fim, pc_fim))) / 3600) as "Horas Planejamento",
  (pl_fim::date - coalesce(dc_fim, pc_fim)::date)               as "Dias Planejamento",
  dt_prazo_saida_expedicao                  as "Data Prazo Interno",
  -- ---- DOC (divisão da coleta) ----
  qtde_doc                                  as "Qtde. DOC",
  doc_emissao                               as "Data DOC",
  round(extract(epoch from (doc_emissao - pl_fim)) / 3600)      as "Horas Divisão DOC",
  (doc_emissao::date - pl_fim::date)                            as "Dias Divisão DOC",
  -- ---- Coleta física ----
  cf_inicio                                 as "Data Início Coleta",
  cf_fim                                    as "Data Fim Coleta",
  round(extract(epoch from (cf_fim - cf_inicio)) / 3600)        as "Horas de Coleta",
  (cf_fim::date - cf_inicio::date)                              as "Dias de Coleta",
  -- ---- Manuseio / conferência ----
  me_inicio                                 as "Data Início Conferência",
  me_fim                                    as "Data Fim Conferência",
  round(extract(epoch from (me_fim - me_inicio)) / 3600)        as "Horas Conferência",
  (me_fim::date - me_inicio::date)                              as "Dias Conferência",
  -- ---- Emissão da NF ----
  en_fim                                    as "Data Fim Emissão",
  round(extract(epoch from (en_fim - me_fim)) / 3600)           as "Horas Emissão",
  (en_fim::date - me_fim::date)                                 as "Dias Emissão",
  -- ---- Veredicto da PRODUÇÃO (esteira interna x prazo interno) ----
  case when en_fim is null then null
       when en_fim::date <= dt_prazo_saida_expedicao then 'No Prazo'
       else 'Em Atraso' end                 as "Análise Produção",
  -- ---- Expedição ----
  minuta                                    as "Minuta",
  dt_expedicao                              as "Data Expedição Minuta",
  round(extract(epoch from (dt_expedicao - en_fim)) / 3600)     as "Horas Expedição",
  (dt_expedicao::date - en_fim::date)                           as "Dias Expedição",
  case when dt_expedicao is null then null
       when dt_expedicao::date <= dt_prazo_saida_expedicao then 'No Prazo'
       else 'Em Atraso' end                 as "Análise Expedição",
  tipo_carga                                as "Tipo de Carga",
  -- ---- Transporte e disponibilidade ----
  dt_prazo_entrega                          as "Data Prazo Cliente",
  chegada_base                              as "Data Chegada Base",
  entrada_base                              as "Data Entrada Base",
  dt_retirada                               as "Data Retirada Cliente",
  dt_entrega                                as "Data Entrega",
  dt_disponivel                             as "Data Disponível ao Cliente",
  round(extract(epoch from (dt_disponivel - dt_expedicao)) / 3600) as "Horas Transporte",
  (dt_disponivel::date - dt_expedicao::date)                    as "Dias Transporte",
  -- ---- O VEREDICTO QUE VALE: régua por tipo de atendimento ----
  case when dt_disponivel is null then null
       when dt_disponivel::date <= dt_prazo_entrega then 'No Prazo'
       else 'Fora do Prazo' end             as "Análise Transporte",
  -- atraso em dias: negativo = adiantado (útil para histograma na EDA)
  (dt_disponivel::date - dt_prazo_entrega)  as "Dias de Atraso"
from base
order by dt_solicitacao;
