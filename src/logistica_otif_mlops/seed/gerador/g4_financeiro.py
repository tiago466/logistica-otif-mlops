"""G4: financeiro — a régua da Sarah (faturamento, custos, coletas, positivações).

Gera o schema `custos` a partir do mundo já expedido pela G3, mais as duas
entidades operacionais de serviço (COLETA e POSITIVACAO, que nascem como OS no
financeiro). A física do preço:

    preço de tabela = R$/m³ da praça × m³ taxado × modal × nível de serviço
    receita         = preço de tabela × `fator_preco` do cliente   (a barganha)
    custo variável  = preço de tabela × razão de mercado × `fator_custo`

O `fator_preco`/`fator_custo` vêm do gabarito selado: é ali que mora a resposta
da Dna. Sarah. A âncora de magnitude é a régua dela (transporte ~R$1,3 Mi/mês
em 2025), e o preço se auto-calibra para honrá-la mesmo se o volume mudar.

Rodar: uv run python -m logistica_otif_mlops.seed.gerador.g4_financeiro
"""

from __future__ import annotations

import bisect
import csv
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from importlib.resources import files
from typing import Any

from sqlalchemy import select, text

from logistica_otif_mlops.db import criar_engine, criar_fabrica_de_sessoes
from logistica_otif_mlops.models import Organizacao

SEMENTE = 20260804

# Régua da Sarah (Q9 da anamnese): o mês fechado que ela reportou.
ALVO_TRANSPORTE_2025 = 15_600_000.0  # ~R$1,3 Mi/mês
# Preço da praça: R$/m³ taxado = PISO + PASSO × dias de estrada (a régua de
# distância já vive no lead time, não se duplica tabela).
PRACA_PISO, PRACA_PASSO = 26.0, 7.0
MINIMO_REMESSA = 45.0
FATOR_MODAL_AEREO = 2.0
FATOR_EXCLUSIVO = 3.0
# Custo variável de mercado: fração do preço de tabela que o frete consome.
# Frota própria sai mais barata (não há lucro de terceiro no meio).
RAZAO_CUSTO_FRETE = 0.285
DESCONTO_FROTA_PROPRIA = 0.82
RAZAO_CUSTO_BASE = 0.10  # a base parceira cobra pela última milha/manuseio
CUSTO_REENTREGA = 0.60  # fração do frete original, na competência da ocorrência
INSUMO_POR_LINHA = 0.55  # embalagem/papel bolha rateado por linha expedida
UF_MATRIZ = "SC"
# Reajuste anual de tabela (base 2025 = 1,0): a série tem inflação, como a vida
REAJUSTE_ANO = {2016: 0.62, 2017: 0.66, 2018: 0.70, 2019: 0.74, 2020: 0.78,
                2021: 0.84, 2022: 0.92, 2023: 0.96, 2024: 0.98, 2025: 1.0,
                2026: 1.05}
# Sujeira proposital (o Discovery tem que achar)
PCT_CUSTO_ATRASADO = 0.04   # nota do transportador que cai na competência seguinte
PCT_FATURA_SEM_CUSTO = 0.004  # operação faturada sem lançamento de custo
PCT_CUSTO_ORFAO = 0.003     # custo com SS que não existe (digitação)
PCT_FATURA_DUPLICADA = 0.001  # lançamento em duplicidade
# A política de aging (faixas, acréscimos e vigência), a cubagem e os tributos
# vivem em `custos.parametro_financeiro`: o gerador LÊ de lá, não repete o número.
# até 3 meses a tarifa é cheia; daí em diante o acréscimo cresce por faixa
FAIXAS_AGING = [(90, ""), (180, "aging_3_6m"), (270, "aging_6_9m"), (365, "aging_9_12m")]
ACRESCIMO_ACIMA_12M = "aging_12m_mais"
# Serviços avulsos (OS)
COLETAS_MES = (18, 46)
POSITIVACOES_MES = (12, 40)
PRECO_COLETA = (280.0, 1400.0)
PRECO_POSITIVACAO = (450.0, 3200.0)
MONTADORES = ["Montagem Express", "PDV Certo Serviços", "Ativa Promocional",
              "Bras Montagens", "Norte Eventos", "Sul Displays"]


def _um(cur: Any) -> tuple[Any, ...]:
    linha = cur.fetchone()
    assert linha is not None
    return tuple(linha)


def _ler(nome: str) -> list[dict[str, str]]:
    with files("logistica_otif_mlops.seed.dados").joinpath(nome).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _proximo_mes(m: date) -> date:
    return date(m.year + (m.month == 12), (m.month % 12) + 1, 1)


def _competencia(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


class Contexto:
    """Réguas estáticas: gabarito, praças, tarifas, categorias, clientes."""

    def __init__(self) -> None:
        engine = criar_engine()
        fabrica = criar_fabrica_de_sessoes(engine)
        gab = {g["sigla"]: g for g in _ler("gabarito_clientes.csv")}
        self.preco = {s: float(g["fator_preco"]) for s, g in gab.items()}
        self.custo = {s: float(g["fator_custo"]) for s, g in gab.items()}
        self.estoca = {s for s, g in gab.items() if g["estoca"] == "True"}
        with fabrica() as s:
            self.clientes = {
                o.id: (o.sigla, o.porte or "MEDIA")
                for o in s.scalars(select(Organizacao).where(
                    Organizacao.tipo_parceria == "CLIENTE"))
            }
            self.sigla_por_id = {i: v[0] for i, v in self.clientes.items()}
            self.categoria = {c: i for i, c in s.execute(
                text("select id, codigo from custos.categoria_custo"))}
            self.tarifa = {
                sigla: (float(m3), float(ad), float(mini))
                for sigla, m3, ad, mini in s.execute(text(
                    "select cliente_sigla, valor_m3, aliquota_ad_valorem,"
                    " valor_minimo_mensal from custos.tarifa_armazenagem"))}
            self.praca = {
                uf: PRACA_PISO + PRACA_PASSO * dias
                for uf, dias in s.execute(text(
                    "select uf, min(dias_uteis) from operacao.lead_time"
                    " group by uf"))}
            self.transportadoras = [
                nome for (nome,) in s.execute(text(
                    "select nome from operacao.transportador"
                    " where tipo <> 'FROTA_PROPRIA'"))]
            # os parâmetros de negócio vivem no banco; o gerador é consumidor
            self.par = {chave: float(valor) for chave, valor in s.execute(text(
                "select chave, valor from custos.parametro_financeiro"))}
        self.cubagem = self.par["fator_cubagem_rodoviario"]
        self.icms_interno = self.par["icms_interno"]
        self.icms_inter = self.par["icms_interestadual"]
        self.difal = self.par["aliquota_difal_simplificada"]
        vigencia = int(self.par["competencia_vigencia_aging"])
        self.vigencia_aging = date(vigencia // 100, vigencia % 100, 1)

    def praca_de(self, uf: str) -> float:
        return float(self.praca.get(uf, PRACA_PISO + PRACA_PASSO * 6))

    def fator_aging(self, idade_dias: int, quando: date) -> float:
        """Multiplicador da tarifa conforme o tempo parado (política de jul/2025)."""
        if quando < self.vigencia_aging:
            return 1.0
        chave = next((c for limite, c in FAIXAS_AGING if idade_dias <= limite),
                     ACRESCIMO_ACIMA_12M)
        return 1.0 + (self.par[chave] if chave else 0.0)


def preco_tabela(ctx: Contexto, uf: str, m3: float, peso: float,
                 aereo: bool, exclusivo: bool, ano: int) -> float:
    """Preço cheio da praça, antes da barganha do cliente."""
    m3_taxado = max(m3, peso / ctx.cubagem)
    valor = ctx.praca_de(uf) * m3_taxado
    if aereo:
        valor *= FATOR_MODAL_AEREO
    if exclusivo:
        valor *= FATOR_EXCLUSIVO
    return max(MINIMO_REMESSA, valor) * REAJUSTE_ANO.get(ano, 1.0)


def _calibrar(ctx: Contexto, cur: Any) -> float:
    """Ajusta a tabela para a receita de 2025 bater a régua da Sarah."""
    cur.execute("""
        select o.sigla, e.uf, coalesce(p.volume_real_m3, p.volume_teorico_m3),
               coalesce(p.peso_real_kg, p.peso_teorico_kg),
               m.codigo = 'AEREO', p.nivel_servico = 'EXCLUSIVO'
        from operacao.pedido p
        join operacao.organizacao o on o.id = p.cliente_id
        join operacao.endereco e on e.id = p.endereco_id
        join operacao.modalidade m on m.id = p.modalidade_id
        join operacao.pedido_fase pf on pf.pedido_id = p.id
        join operacao.fase f on f.id = pf.fase_id and f.codigo = 'EC'
        where pf.dt_saida >= '2025-01-01' and pf.dt_saida < '2026-01-01'
    """)
    bruto = float(sum(
        preco_tabela(ctx, uf, float(m3), float(peso), aereo, excl, 2025)
        * ctx.preco.get(sigla, 1.0)
        for sigla, uf, m3, peso, aereo, excl in cur.fetchall()))
    return ALVO_TRANSPORTE_2025 / bruto if bruto else 1.0


def executar() -> None:
    engine = criar_engine()
    ctx = Contexto()
    rng = random.Random(SEMENTE)
    raw = engine.raw_connection()
    cur = raw.cursor()
    cur.execute("select count(*) from custos.faturamento_operacao")
    if _um(cur)[0]:
        print("g4: faturamento já existe; nada a fazer.")
        return

    calibre = _calibrar(ctx, cur)
    print(f"g4: calibre da tabela de preço = {calibre:.4f}")

    cur.execute("select min(dt_saida)::date, max(dt_saida)::date from operacao.pedido_fase")
    ini, fim = _um(cur)
    seq_fat = seq_cus = seq_col = seq_pos = 0
    mes = date(ini.year, ini.month, 1)
    while mes <= fim:
        prox = _proximo_mes(mes)
        seq_fat, seq_cus = _transporte(ctx, rng, cur, mes, prox, calibre, seq_fat, seq_cus)
        seq_col, seq_fat, seq_cus = _coletas(ctx, rng, cur, mes, seq_col, seq_fat, seq_cus)
        seq_pos, seq_fat, seq_cus = _positivacoes(ctx, rng, cur, mes, seq_pos, seq_fat, seq_cus)
        raw.commit()
        mes = prox
    _armazenagem(ctx, rng, cur, seq_fat)
    for esquema, tabela in (("custos", "faturamento_operacao"), ("custos", "custo_operacao"),
                            ("operacao", "coleta"), ("operacao", "positivacao")):
        cur.execute(f"SELECT setval(pg_get_serial_sequence('{esquema}.{tabela}','id'),"
                    f"(SELECT COALESCE(MAX(id),1) FROM {esquema}.{tabela}))")
    raw.commit()
    cur.execute("select count(*), coalesce(sum(valor_com_icms),0) from custos.faturamento_operacao")
    n_fat, receita = _um(cur)
    cur.execute("select count(*), coalesce(sum(valor),0) from custos.custo_operacao")
    n_cus, custo = _um(cur)
    print(f"G4 OK: {n_fat} faturamentos (R$ {receita:,.0f}) · "
          f"{n_cus} custos (R$ {custo:,.0f})")
    cur.close()
    raw.close()


def _transporte(ctx: Contexto, rng: random.Random, cur: Any, mes: date, prox: date,
                calibre: float, seq_fat: int, seq_cus: int) -> tuple[int, int]:
    """Receita e custo de cada pedido expedido no mês, mais insumos e DIFAL."""
    cur.execute("""
        with ped as (
          select p.id, p.numero, o.sigla, e.uf,
                 coalesce(p.volume_real_m3, p.volume_teorico_m3) m3,
                 coalesce(p.peso_real_kg, p.peso_teorico_kg) peso,
                 m.codigo = 'AEREO' aereo, p.nivel_servico = 'EXCLUSIVO' excl,
                 p.tipo_atendimento, pf.dt_saida::date saida
          from operacao.pedido p
          join operacao.organizacao o on o.id = p.cliente_id
          join operacao.endereco e on e.id = p.endereco_id
          join operacao.modalidade m on m.id = p.modalidade_id
          join operacao.pedido_fase pf on pf.pedido_id = p.id
          join operacao.fase f on f.id = pf.fase_id and f.codigo = 'EC'
          where pf.dt_saida >= %s and pf.dt_saida < %s)
        select ped.*, coalesce(li.n, 1), coalesce(tr.tipo, 'TRANSPORTADORA'),
               coalesce(tr.nome, 'Transportes Gerais')
        from ped
        left join lateral (
          select count(*) n from operacao.pedido_item pi where pi.pedido_id = ped.id) li on true
        left join lateral (
          select t.tipo, t.nome from operacao.entrega e2
          join operacao.minuta mi on mi.id = e2.minuta_id
          join operacao.transportador t on t.id = mi.transportador_id
          where e2.pedido_id = ped.id order by e2.id limit 1) tr on true
    """, (mes, prox))
    pedidos = cur.fetchall()
    if not pedidos:
        return seq_fat, seq_cus

    faturas: list[tuple[Any, ...]] = []
    custos: list[tuple[Any, ...]] = []
    comp = _competencia(mes)
    comp_prox = _competencia(prox)
    linhas_cliente: dict[str, int] = defaultdict(int)
    base_difal: dict[str, float] = defaultdict(float)
    cat = ctx.categoria

    for (_pid, numero, sigla, uf, m3, peso, aereo, excl, atend, saida,
         n_linhas, tipo_transp, nome_transp) in pedidos:
        tabela = preco_tabela(ctx, uf, float(m3), float(peso), aereo, excl,
                              saida.year) * calibre
        receita = tabela * ctx.preco.get(sigla, 1.0)
        interestadual = uf != UF_MATRIZ
        icms = receita * (ctx.icms_inter if interestadual else ctx.icms_interno)
        seq_fat += 1
        dt_fat = saida + timedelta(days=rng.randint(2, 10))
        faturas.append((seq_fat, sigla, numero, "TRANSPORTE", comp,
                        round(receita, 2), round(icms, 2), dt_fat))
        if rng.random() < PCT_FATURA_DUPLICADA:  # o mesmo lançamento, duas vezes
            seq_fat += 1
            faturas.append((seq_fat, sigla, numero, "TRANSPORTE", comp,
                            round(receita, 2), round(icms, 2), dt_fat))
        linhas_cliente[sigla] += n_linhas
        if interestadual:
            base_difal[sigla] += receita

        if rng.random() >= PCT_FATURA_SEM_CUSTO:
            frete = tabela * RAZAO_CUSTO_FRETE * ctx.custo.get(sigla, 1.0)
            if tipo_transp == "FROTA_PROPRIA":
                frete *= DESCONTO_FROTA_PROPRIA
            atrasado = rng.random() < PCT_CUSTO_ATRASADO
            competencia_custo = prox if atrasado else mes
            ref = numero
            if rng.random() < PCT_CUSTO_ORFAO:  # SS digitada errada no financeiro
                ref = f"SS{rng.randint(1, 9999999):07d}"
            seq_cus += 1
            custos.append((seq_cus, sigla, ref, cat["AEREO" if aereo else "RODOVIARIO"],
                           nome_transp, round(frete, 2), competencia_custo))
            if atend in ("ENTREGA_VIA_BASE", "RETIRA_BASE"):
                seq_cus += 1
                custos.append((seq_cus, sigla, numero, cat["BASE"], "Base parceira",
                               round(tabela * RAZAO_CUSTO_BASE * ctx.custo.get(sigla, 1.0), 2),
                               competencia_custo))

    # rateio mensal de insumos (embalagem/produção) e apuração do DIFAL
    for sigla, linhas in linhas_cliente.items():
        seq_cus += 1
        custos.append((seq_cus, sigla, None, cat["INSUMOS"], "Almoxarifado Trans Fictício BR",
                       round(linhas * INSUMO_POR_LINHA * rng.uniform(0.85, 1.2), 2), mes))
    for sigla, base in base_difal.items():
        seq_cus += 1
        custos.append((seq_cus, sigla, None, cat["IMPOSTO_DIFAL"], "Recolhimento estadual",
                       round(base * ctx.difal, 2), mes))
    seq_cus = _reentregas(ctx, rng, cur, mes, prox, calibre, seq_cus, custos, comp_prox)

    _copiar(cur, "custos.faturamento_operacao",
            ("id", "cliente_sigla", "referencia_numero", "tipo_operacao", "competencia",
             "valor_com_icms", "valor_icms", "dt_faturamento"), faturas)
    _copiar(cur, "custos.custo_operacao",
            ("id", "cliente_sigla", "referencia_numero", "categoria_custo_id",
             "prestador_nome", "valor", "dt_competencia"), custos)
    return seq_fat, seq_cus


def _reentregas(ctx: Contexto, rng: random.Random, cur: Any, mes: date, prox: date,
                calibre: float, seq_cus: int, custos: list[tuple[Any, ...]],
                _comp_prox: str) -> int:
    """Custo extra da segunda viagem, na competência em que a falha ocorreu."""
    cur.execute("""
        select o.sigla, p.numero, e.uf,
               coalesce(p.volume_real_m3, p.volume_teorico_m3),
               coalesce(p.peso_real_kg, p.peso_teorico_kg),
               oc.dt_ocorrencia::date
        from operacao.ocorrencia oc
        join operacao.pedido p on p.id = oc.pedido_id
        join operacao.organizacao o on o.id = p.cliente_id
        join operacao.endereco e on e.id = p.endereco_id
        where oc.dt_ocorrencia >= %s and oc.dt_ocorrencia < %s
    """, (mes, prox))
    for sigla, numero, uf, m3, peso, quando in cur.fetchall():
        tabela = preco_tabela(ctx, uf, float(m3), float(peso), False, False,
                              quando.year) * calibre
        seq_cus += 1
        custos.append((seq_cus, sigla, numero, ctx.categoria["RODOVIARIO"],
                       rng.choice(ctx.transportadoras),
                       round(tabela * RAZAO_CUSTO_FRETE * CUSTO_REENTREGA
                             * ctx.custo.get(sigla, 1.0), 2), mes))
    return seq_cus


def _coletas(ctx: Contexto, rng: random.Random, cur: Any, mes: date,
             seq_col: int, seq_fat: int, seq_cus: int) -> tuple[int, int, int]:
    """OS de coleta: material de campanha que volta (descarte ou retorno)."""
    cur.execute("""
        select o.id, o.sigla, e.id, l.id, t.id, t.nome
        from operacao.organizacao o
        join operacao.endereco e on e.organizacao_id = o.id and e.fl_principal
        cross join lateral (select id from operacao.local_estoque order by id limit 1) l
        cross join lateral (select id, nome from operacao.transportador
                            where tipo <> 'FROTA_PROPRIA' order by id limit 1) t
        where o.tipo_parceria = 'CLIENTE'
    """)
    candidatos = [c for c in cur.fetchall() if c[1] in ctx.estoca]
    if not candidatos:
        return seq_col, seq_fat, seq_cus
    coletas: list[tuple[Any, ...]] = []
    faturas: list[tuple[Any, ...]] = []
    custos: list[tuple[Any, ...]] = []
    comp = _competencia(mes)
    for _ in range(rng.randint(*COLETAS_MES)):
        cid, sigla, end, local, transp, nome_transp = rng.choice(candidatos)
        seq_col += 1
        dia = date(mes.year, mes.month, rng.randint(1, 28))
        prevista = dia + timedelta(days=rng.randint(2, 6))
        feita = rng.random() < 0.93
        dt_coleta = (datetime.combine(prevista + timedelta(days=rng.randint(0, 3)),
                                      time(rng.randint(8, 17), rng.randint(0, 59)))
                     if feita else None)
        peso = round(rng.uniform(40, 2200), 3)
        volume = round(peso / rng.uniform(120, 320), 4)
        coletas.append((seq_col, f"OSC{seq_col:07d}", cid, end, local, transp, None,
                        datetime.combine(dia, time(rng.randint(8, 17))), prevista,
                        dt_coleta, peso, volume,
                        "DESCARTE" if rng.random() < 0.8 else "RETORNO_ESTOQUE",
                        "COLETADA" if feita else
                        ("CANCELADA" if rng.random() < 0.5 else "SOLICITADA")))
        if dt_coleta is None:
            continue
        receita = rng.uniform(*PRECO_COLETA) * ctx.preco.get(sigla, 1.0)
        seq_fat += 1
        faturas.append((seq_fat, sigla, f"OSC{seq_col:07d}", "COLETA", comp,
                        round(receita, 2), round(receita * ctx.icms_interno, 2),
                        dt_coleta.date() + timedelta(days=rng.randint(1, 8))))
        seq_cus += 1
        custos.append((seq_cus, sigla, f"OSC{seq_col:07d}", ctx.categoria["RODOVIARIO"],
                       nome_transp,
                       round(receita * rng.uniform(0.35, 0.55)
                             * ctx.custo.get(sigla, 1.0), 2), mes))
    _copiar(cur, "operacao.coleta",
            ("id", "numero", "cliente_id", "endereco_origem_id", "local_estoque_destino_id",
             "transportador_id", "veiculo_id", "dt_solicitacao", "dt_prevista", "dt_coleta",
             "peso_kg", "volume_m3", "finalidade", "status"), coletas)
    _copiar(cur, "custos.faturamento_operacao",
            ("id", "cliente_sigla", "referencia_numero", "tipo_operacao", "competencia",
             "valor_com_icms", "valor_icms", "dt_faturamento"), faturas)
    _copiar(cur, "custos.custo_operacao",
            ("id", "cliente_sigla", "referencia_numero", "categoria_custo_id",
             "prestador_nome", "valor", "dt_competencia"), custos)
    return seq_col, seq_fat, seq_cus


def _positivacoes(ctx: Contexto, rng: random.Random, cur: Any, mes: date,
                  seq_pos: int, seq_fat: int, seq_cus: int) -> tuple[int, int, int]:
    """OS de positivação: montagem do material no ponto de venda/evento."""
    cur.execute("""
        select p.id, o.sigla, p.cliente_id, p.endereco_id
        from operacao.pedido p
        join operacao.organizacao o on o.id = p.cliente_id
        join operacao.pedido_fase pf on pf.pedido_id = p.id
        join operacao.fase f on f.id = pf.fase_id and f.codigo = 'EC'
        where pf.dt_saida >= %s and pf.dt_saida < %s and p.nivel_servico = 'EXCLUSIVO'
        limit 400
    """, (mes, _proximo_mes(mes)))
    candidatos = cur.fetchall()
    if not candidatos:
        return seq_pos, seq_fat, seq_cus
    cur.execute("select id, dt_inicio, dt_fim from operacao.campanha")
    campanhas = [(cid, ini, f) for cid, ini, f in cur.fetchall()]
    posits: list[tuple[Any, ...]] = []
    faturas: list[tuple[Any, ...]] = []
    custos: list[tuple[Any, ...]] = []
    comp = _competencia(mes)
    for _ in range(min(rng.randint(*POSITIVACOES_MES), len(candidatos))):
        pid, sigla, cid, endereco = rng.choice(candidatos)
        seq_pos += 1
        abertura = date(mes.year, mes.month, rng.randint(1, 26))
        feita = rng.random() < 0.9
        servico = abertura + timedelta(days=rng.randint(1, 12)) if feita else None
        camp = next((c for c, ini, f in campanhas if ini <= abertura <= f), None)
        posits.append((seq_pos, f"OSP{seq_pos:07d}", cid, pid, endereco, camp,
                       rng.choice(MONTADORES), abertura, servico,
                       "REALIZADA" if feita else
                       ("CANCELADA" if rng.random() < 0.4 else "ABERTA")))
        if not feita or servico is None:
            continue
        receita = rng.uniform(*PRECO_POSITIVACAO) * ctx.preco.get(sigla, 1.0)
        seq_fat += 1
        faturas.append((seq_fat, sigla, f"OSP{seq_pos:07d}", "POSITIVACAO", comp,
                        round(receita, 2), round(receita * ctx.icms_interno, 2),
                        servico + timedelta(days=rng.randint(1, 10))))
        seq_cus += 1
        custos.append((seq_cus, sigla, f"OSP{seq_pos:07d}", ctx.categoria["MONTADOR"],
                       posits[-1][6],
                       round(receita * rng.uniform(0.4, 0.62)
                             * ctx.custo.get(sigla, 1.0), 2), mes))
    _copiar(cur, "operacao.positivacao",
            ("id", "numero", "cliente_id", "pedido_id", "endereco_id", "campanha_id",
             "parceiro_nome", "dt_abertura", "dt_servico", "status"), posits)
    _copiar(cur, "custos.faturamento_operacao",
            ("id", "cliente_sigla", "referencia_numero", "tipo_operacao", "competencia",
             "valor_com_icms", "valor_icms", "dt_faturamento"), faturas)
    _copiar(cur, "custos.custo_operacao",
            ("id", "cliente_sigla", "referencia_numero", "categoria_custo_id",
             "prestador_nome", "valor", "dt_competencia"), custos)
    return seq_pos, seq_fat, seq_cus


def _armazenagem(ctx: Contexto, rng: random.Random, cur: Any, seq_fat: int) -> None:
    """Cobrança mensal: foto do estoque × tarifa × aging (política de jul/2025)."""
    cur.execute("""
        select item_id, local_estoque_id, dt_recebimento::date
        from operacao.recebimento where dt_recebimento is not null
        order by item_id, local_estoque_id, dt_recebimento""")
    entradas: dict[tuple[int, int], list[date]] = defaultdict(list)
    for iid, loc, quando in cur.fetchall():
        entradas[(iid, loc)].append(quando)
    cur.execute("""
        select s.data, i.cliente_id, s.item_id, s.local_estoque_id,
               s.m3_ocupado, s.valor_material
        from operacao.estoque_snapshot s
        join operacao.item i on i.id = s.item_id
        order by s.data""")
    bruto: dict[tuple[date, int], float] = defaultdict(float)
    for quando, cliente, iid, loc, m3, valor in cur.fetchall():
        sigla = ctx.sigla_por_id.get(cliente)
        if sigla is None or sigla not in ctx.tarifa:
            continue
        valor_m3, ad_valorem, _minimo = ctx.tarifa[sigla]
        datas = entradas.get((iid, loc))
        idade = 0
        if datas:
            pos = bisect.bisect_right(datas, quando)
            if pos:
                idade = (quando - datas[pos - 1]).days
        bruto[(quando, cliente)] += ((float(m3) * valor_m3 + float(valor) * ad_valorem)
                                     * ctx.fator_aging(idade, quando))

    faturas: list[tuple[Any, ...]] = []
    for (quando, cliente), valor in sorted(bruto.items()):
        sigla = ctx.sigla_por_id[cliente]
        _v, _a, minimo = ctx.tarifa[sigla]
        cobranca = max(valor, minimo)
        seq_fat += 1
        faturas.append((seq_fat, sigla, None, "ARMAZENAGEM", _competencia(quando),
                        round(cobranca, 2), round(cobranca * ctx.icms_interno, 2),
                        quando + timedelta(days=rng.randint(1, 6))))
    _copiar(cur, "custos.faturamento_operacao",
            ("id", "cliente_sigla", "referencia_numero", "tipo_operacao", "competencia",
             "valor_com_icms", "valor_icms", "dt_faturamento"), faturas)


def _copiar(cur: Any, tabela: str, colunas: tuple[str, ...],
            linhas: list[tuple[Any, ...]]) -> None:
    if not linhas:
        return
    with cur.copy(f"COPY {tabela} ({', '.join(colunas)}) FROM STDIN") as copia:
        for linha in linhas:
            copia.write_row(linha)


if __name__ == "__main__":
    executar()
