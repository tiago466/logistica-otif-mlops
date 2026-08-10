-- =====================================================================
-- RELATÓRIO DE MARGEM DE CONTRIBUIÇÃO POR OPERAÇÃO  (Dna. Sarah)
-- =====================================================================
-- Reproduz a aba `MC POR OPERAÇÃO` do workbook mensal, com uma diferença
-- que muda tudo: aqui as dimensões da operação (porte, modal, praça, tipo
-- de atendimento) entram junto. O relatório atual dela é só financeiro, e
-- por isso não consegue responder POR QUE uma margem é baixa.
--
-- Fórmula (cofre `regras_derivadas_mc.md`, seção 2):
--   receita          = valor faturado (frete, armazenagem, coleta, positivação)
--   imposto_sobre_fat= receita × taxa_imposto_faturamento   (parâmetro)
--   icms             = destacado por lançamento
--   cv               = custo variável (frete, base, insumos, montador, DIFAL)
--   MC               = receita − cv − icms − imposto_sobre_fat
--   MC %             = MC / receita         (nunca a média das MC%!)
--
-- ⚠️ Uma armadilha do domínio: o financeiro é sistema de TERCEIRO e a
-- ligação com a operação é por CHAVE DE NEGÓCIO (o número da SS/OS), não
-- por FK. Lançamento com competência defasada e órfão de digitação existem
-- e são normais: o `full outer join` abaixo os mantém VISÍVEIS em vez de
-- descartá-los em silêncio. Toda reconciliação começa admitindo o que não
-- casa.
-- =====================================================================

with
parametros as (
  select
    max(valor) filter (where chave = 'taxa_imposto_faturamento') as taxa_imposto,
    max(valor) filter (where chave = 'custo_m3_galpao')          as custo_m3_galpao,
    max(valor) filter (where chave = 'custo_esteira_por_linha')  as custo_esteira_linha
  from custos.parametro_financeiro
),
-- ---------------------------------------------------------------------
-- 1. Receita e custo por operação, consolidados da fonte financeira.
--    Os estornos entram com sinal negativo: some respeitando o sinal,
--    nunca com abs(), ou a receita infla.
-- ---------------------------------------------------------------------
receita as (
  select cliente_sigla, referencia_numero, tipo_operacao, competencia,
         sum(valor_com_icms) as receita,
         sum(valor_icms)     as icms,
         count(*)            as lancamentos_receita
  from custos.faturamento_operacao
  group by 1, 2, 3, 4
),
custo as (
  select c.cliente_sigla, c.referencia_numero,
         to_char(c.dt_competencia, 'YYYY-MM') as competencia,
         sum(c.valor) as cv,
         sum(c.valor) filter (where cc.codigo in ('RODOVIARIO','AEREO')) as cv_frete,
         sum(c.valor) filter (where cc.codigo = 'BASE')          as cv_base,
         sum(c.valor) filter (where cc.codigo = 'INSUMOS')       as cv_insumos,
         sum(c.valor) filter (where cc.codigo = 'MONTADOR')      as cv_montador,
         sum(c.valor) filter (where cc.codigo = 'IMPOSTO_DIFAL') as difal
  from custos.custo_operacao c
  join custos.categoria_custo cc on cc.id = c.categoria_custo_id
  group by 1, 2, 3
),
-- ---------------------------------------------------------------------
-- 2. As DIMENSÕES da operação, que o relatório financeiro não tem.
--    É este bloco que transforma "a margem caiu" em "a margem caiu NOS
--    pedidos via base do Sudeste para clientes pequenos".
-- ---------------------------------------------------------------------
operacao as (
  select p.numero as referencia_numero,
         o.sigla, o.nome_fantasia, o.porte, o.segmento,
         p.tipo_atendimento, p.nivel_servico, md.codigo as modal,
         en.uf, en.cidade,
         coalesce(p.volume_real_m3, p.volume_teorico_m3) as m3,
         coalesce(p.peso_real_kg, p.peso_teorico_kg) as peso_kg,
         (select count(*) from operacao.pedido_item pi where pi.pedido_id = p.id) as linhas,
         p.dt_solicitacao::date as dt_pedido
  from operacao.pedido p
  join operacao.organizacao o on o.id = p.cliente_id
  join operacao.endereco en on en.id = p.endereco_id
  join operacao.modalidade md on md.id = p.modalidade_id
),
-- ---------------------------------------------------------------------
-- 3. A junção que não esconde nada: receita sem custo, custo sem receita
--    e referência que não existe na operação continuam na saída.
-- ---------------------------------------------------------------------
consolidado as (
  select
    coalesce(r.cliente_sigla, c.cliente_sigla)         as cliente_sigla,
    coalesce(r.referencia_numero, c.referencia_numero) as referencia,
    coalesce(r.competencia, c.competencia)             as competencia,
    r.tipo_operacao,
    coalesce(r.receita, 0) as receita,
    coalesce(r.icms, 0)    as icms,
    coalesce(c.cv, 0)      as cv,
    c.cv_frete, c.cv_base, c.cv_insumos, c.cv_montador, c.difal,
    -- ⚠️ para saber de que lado a linha veio, teste uma coluna que NUNCA é
    -- nula na origem (`cliente_sigla`). Testar `referencia_numero` daria
    -- falso positivo: a ARMAZENAGEM fatura por competência e tem esse campo
    -- nulo de direito, e toda ela apareceria como "custo sem receita".
    r.cliente_sigla is null as sem_receita,
    c.cliente_sigla is null as sem_custo
  from receita r
  full outer join custo c
    on  c.cliente_sigla     = r.cliente_sigla
    and c.referencia_numero is not distinct from r.referencia_numero
    and c.competencia       = r.competencia
)
select
  cs.competencia                              as "Competência",
  cs.cliente_sigla                            as "Cliente",
  op.nome_fantasia                            as "Nome",
  op.porte                                    as "Porte",
  op.segmento                                 as "Segmento",
  cs.referencia                               as "SS/OS",
  cs.tipo_operacao                            as "Tipo de Operação",
  -- dimensões da operação (o que falta no relatório atual dela)
  op.tipo_atendimento                         as "Tipo de Atendimento",
  op.nivel_servico                            as "Nível de Serviço",
  op.modal                                    as "Modal",
  op.uf                                       as "UF",
  op.m3                                       as "M³",
  op.peso_kg                                  as "Peso (kg)",
  op.linhas                                   as "Linhas",
  -- financeiro
  round(cs.receita, 2)                        as "Receita",
  round(cs.icms, 2)                           as "ICMS",
  round(cs.receita * p.taxa_imposto, 2)       as "Imposto s/ Faturamento",
  round(cs.cv, 2)                             as "Custo Variável",
  round(coalesce(cs.cv_frete, 0), 2)          as "CV Frete",
  round(coalesce(cs.cv_base, 0), 2)           as "CV Base",
  round(coalesce(cs.cv_insumos, 0), 2)        as "CV Insumos",
  round(coalesce(cs.cv_montador, 0), 2)       as "CV Montador",
  round(coalesce(cs.difal, 0), 2)             as "DIFAL",
  round(cs.receita - cs.cv - cs.icms - cs.receita * p.taxa_imposto, 2) as "MC (R$)",
  case when cs.receita <> 0
       then round(100 * (cs.receita - cs.cv - cs.icms - cs.receita * p.taxa_imposto)
                  / cs.receita, 1) end        as "MC (%)",
  -- sinalizadores de reconciliação: o que a Sarah precisa saber que não fecha
  case when cs.sem_receita then 'custo sem receita'
       when cs.sem_custo   then 'receita sem custo'
       when cs.referencia like 'SS%' and op.referencia_numero is null
            then 'referência inexistente na operação'
       else null end                          as "Alerta de Reconciliação"
from consolidado cs
cross join parametros p
left join operacao op on op.referencia_numero = cs.referencia
where cs.competencia between '2026-01' and '2026-07'   -- ← janela do relatório
order by cs.competencia, cs.cliente_sigla, cs.referencia;

-- =====================================================================
-- VISÃO CONSOLIDADA POR CLIENTE (o resumo que vai ao comitê)
-- =====================================================================
-- Rodar separadamente. Aqui entra o CUSTO DE SERVIR, que é a parte que o
-- relatório atual não enxerga: quem ocupa o galpão e consome a esteira
-- paga por isso. Sem esta linha, um cliente de MC positiva pode estar
-- destruindo resultado sem ninguém perceber.
/*
with parametros as (
  select max(valor) filter (where chave = 'taxa_imposto_faturamento') as taxa_imposto,
         max(valor) filter (where chave = 'custo_m3_galpao')          as custo_m3,
         max(valor) filter (where chave = 'custo_esteira_por_linha')  as custo_linha
  from custos.parametro_financeiro),
 rec as (select cliente_sigla, sum(valor_com_icms) receita, sum(valor_icms) icms
         from custos.faturamento_operacao where competencia like '2026-%' group by 1),
 cus as (select cliente_sigla, sum(valor) cv from custos.custo_operacao
         where to_char(dt_competencia,'YYYY') = '2026' group by 1),
 esforco as (
   select o.sigla, count(*) linhas
   from operacao.pedido_item pi
   join operacao.pedido p on p.id = pi.pedido_id
   join operacao.organizacao o on o.id = p.cliente_id
   where extract(year from p.dt_solicitacao) = 2026 group by 1),
 espaco as (
   select o.sigla, sum(s.m3_ocupado) m3
   from operacao.estoque_snapshot s
   join operacao.item i on i.id = s.item_id
   join operacao.organizacao o on o.id = i.cliente_id
   where extract(year from s.data) = 2026 group by 1)
select o.sigla, o.nome_fantasia, o.porte,
       round(rec.receita) receita,
       round(rec.receita - coalesce(cus.cv,0) - rec.icms
             - rec.receita * p.taxa_imposto) mc,
       round(100*(rec.receita - coalesce(cus.cv,0) - rec.icms
             - rec.receita * p.taxa_imposto)/rec.receita, 1) mc_pct,
       round(coalesce(esforco.linhas,0) * p.custo_linha
             + coalesce(espaco.m3,0) * p.custo_m3) custo_de_servir,
       round(rec.receita - coalesce(cus.cv,0) - rec.icms
             - rec.receita * p.taxa_imposto
             - coalesce(esforco.linhas,0) * p.custo_linha
             - coalesce(espaco.m3,0) * p.custo_m3) resultado
from rec
cross join parametros p
join operacao.organizacao o on o.sigla = rec.cliente_sigla
left join cus on cus.cliente_sigla = rec.cliente_sigla
left join esforco on esforco.sigla = rec.cliente_sigla
left join espaco on espaco.sigla = rec.cliente_sigla
order by resultado;
*/
