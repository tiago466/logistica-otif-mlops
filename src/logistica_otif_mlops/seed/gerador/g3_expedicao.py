"""G3: expedição — minutas, entregas (pernas), bases, retiradas e fotos de estoque.

Consome os pedidos expedidos pelo G2 (fase EC) e gera a viagem de cada um:
consolidação em minutas por dia × rota × modal (exclusivo = minuta dedicada),
trânsito pela régua de lead time, chegada na base com `dt_entrada_base` ditada
pelo `nivel_infra` (as vilãs seguram a entrada), última milha ou retirada,
reentregas por ocorrência e, ao final, as fotos mensais de estoque.

Rodar: uv run python -m logistica_otif_mlops.seed.gerador.g3_expedicao
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from importlib.resources import files
from typing import Any

from sqlalchemy import select, text

from logistica_otif_mlops.db import criar_engine, criar_fabrica_de_sessoes
from logistica_otif_mlops.models import (
    Endereco,
    LeadTime,
    Modalidade,
    Organizacao,
    Rota,
    TipoOcorrencia,
    Transportador,
)

SEMENTE = 20260803

# UF sem base própria -> base regional que atende
FALLBACK_BASE = {"AL": "BRE", "SE": "BSA", "PB": "BRE", "MS": "BCB",
                 "TO": "BBL", "AC": "BPV", "RR": "BMA", "AP": "BBL"}
ATRASO_ENTRADA_HORAS = {  # nivel_infra -> (min, max) horas úteis p/ efetivar entrada
    "ALTA": (2, 8), "MEDIA": (8, 30), "BAIXA": (24, 120),
}


def _um(cur: Any) -> tuple[Any, ...]:
    linha = cur.fetchone()
    assert linha is not None
    return tuple(linha)


def dia_util(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def somar_horas_uteis(dt: datetime, horas: float) -> datetime:
    restante = horas
    atual = dt
    while True:
        if atual.weekday() >= 5 or atual.time() >= time(18):
            atual = datetime.combine(dia_util(atual.date() + timedelta(days=1)), time(8))
            continue
        if atual.time() < time(8):
            atual = datetime.combine(atual.date(), time(8))
        fim = datetime.combine(atual.date(), time(18))
        disponivel = (fim - atual).total_seconds() / 3600
        if restante <= disponivel:
            return atual + timedelta(hours=restante)
        restante -= disponivel
        atual = fim


def _ler(nome: str) -> list[dict[str, str]]:
    with files("logistica_otif_mlops.seed.dados").joinpath(nome).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class Contexto:
    def __init__(self) -> None:
        engine = criar_engine()
        fabrica = criar_fabrica_de_sessoes(engine)
        with fabrica() as s:
            self.modais = {m.codigo: m.id for m in s.scalars(select(Modalidade))}
            self.rotas = {r.uf: r.id for r in s.scalars(select(Rota)) if r.codigo != "R-LOCAL"}
            self.rota_local = s.scalar(select(Rota.id).where(Rota.codigo == "R-LOCAL"))
            self.lead = {(lt.modalidade_id, lt.uf, lt.cidade): lt.dias_uteis
                         for lt in s.scalars(select(LeadTime))}
            self.tipo_ocorr = {t.codigo: t.id for t in s.scalars(select(TipoOcorrencia))}
            transp = list(s.scalars(select(Transportador)))
            self.frota = next(t.id for t in transp if t.tipo == "FROTA_PROPRIA")
            self.aereo = next(t.id for t in transp if "Aéreo" in t.nome)
            self.terceiros = [t.id for t in transp
                              if t.tipo in ("TRANSPORTADORA", "AGREGADO", "CARRETEIRO")
                              and "Aéreo" not in t.nome]
            self.veiculos: dict[int, list[int]] = defaultdict(list)
            for vid, tid in s.execute(text(
                    "select id, transportador_id from operacao.veiculo")):
                self.veiculos[tid].append(vid)
            # bases: org + endereco-sede + infra (a infra vive no CSV, gabarito)
            infra_csv = {r["sigla"]: r["nivel_infra"]
                         for r in _ler("organizacoes_matriz_bases.csv")}
            bases = s.execute(
                select(Organizacao.id, Organizacao.sigla, Endereco.id, Endereco.uf)
                .join(Endereco, Endereco.organizacao_id == Organizacao.id)
                .where(Organizacao.tipo_parceria == "BASE", Endereco.fl_principal)
            ).all()
            self.base_por_uf: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
            self.base_por_sigla: dict[str, tuple[int, str, int]] = {}
            for oid, sigla, eid, uf in bases:
                registro = (oid, infra_csv.get(sigla, "MEDIA"), eid)
                self.base_por_uf[uf].append(registro)
                self.base_por_sigla[sigla] = registro
            matriz = s.execute(
                select(Organizacao.id, Endereco.id)
                .join(Endereco, Endereco.organizacao_id == Organizacao.id)
                .where(Organizacao.tipo_parceria == "MATRIZ", Endereco.fl_principal)
            ).one()
            self.matriz = (matriz[0], "ALTA", matriz[1])

    def base_para(self, uf: str, rng: random.Random) -> tuple[int, str, int]:
        if uf == "SC":
            return self.matriz  # retirada na propria matriz
        if self.base_por_uf.get(uf):
            return rng.choice(self.base_por_uf[uf])
        return self.base_por_sigla[FALLBACK_BASE.get(uf, "BSP")]


def executar() -> None:
    engine = criar_engine()
    ctx = Contexto()
    rng = random.Random(SEMENTE)
    raw = engine.raw_connection()
    cur = raw.cursor()
    cur.execute("select count(*) from operacao.entrega")
    if _um(cur)[0]:
        print("g3: entregas já existem; nada a fazer.")
        return
    cur.execute("select coalesce(max(id),0) from operacao.ocorrencia")
    seq_ocorr = int(_um(cur)[0])
    seq_min = seq_ent = seq_ret = 0
    fase_ce = _fase_ce_id(cur)

    cur.execute("select min(dt_saida)::date, max(dt_saida)::date from operacao.pedido_fase")
    ini, fim = _um(cur)
    mes = date(ini.year, ini.month, 1)
    while mes <= fim:
        prox = date(mes.year + (mes.month == 12), (mes.month % 12) + 1, 1)
        pedidos = _pedidos_expedidos(cur, mes, prox)
        if pedidos:
            seq_min, seq_ent, seq_ret, seq_ocorr = _processar_mes(
                ctx, rng, cur, pedidos, seq_min, seq_ent, seq_ret, seq_ocorr, fase_ce)
            raw.commit()
        mes = prox
    # semente própria: as fotos podem ser regeradas sozinhas sem refazer a expedição
    _snapshots(cur, random.Random(SEMENTE + 3))
    for t in ("minuta", "entrega", "retirada_base", "ocorrencia",
              "estoque_snapshot", "pedido_fase"):
        cur.execute(f"SELECT setval(pg_get_serial_sequence('operacao.{t}','id'),"
                    f"(SELECT COALESCE(MAX(id),1) FROM operacao.{t}))")
    raw.commit()
    cur.execute("select count(*) from operacao.minuta")
    n_min = _um(cur)[0]
    cur.execute("select count(*) from operacao.entrega")
    n_ent = _um(cur)[0]
    cur.execute("select count(*) from operacao.estoque_snapshot")
    n_snap = _um(cur)[0]
    print(f"G3 OK: {n_min} minutas · {n_ent} entregas · {n_snap} fotos de estoque")
    cur.close()
    raw.close()


def _fase_ce_id(cur: Any) -> int:
    cur.execute("select id from operacao.fase where codigo = 'CE'")
    return int(_um(cur)[0])


def _pedidos_expedidos(cur: Any, mes: date, prox: date) -> list[tuple[Any, ...]]:
    cur.execute(
        """
        select p.id, p.tipo_atendimento, p.nivel_servico, p.modalidade_id,
               p.endereco_id, e.uf, e.cidade, pf.dt_saida, o.porte
        from operacao.pedido p
        join operacao.organizacao o on o.id = p.cliente_id
        join operacao.endereco e on e.id = p.endereco_id
        join operacao.pedido_fase pf on pf.pedido_id = p.id
        join operacao.fase f on f.id = pf.fase_id and f.codigo = 'EC'
        where pf.dt_saida >= %s and pf.dt_saida < %s
        """, (mes, prox))
    return list(cur.fetchall())


def _processar_mes(ctx: Contexto, rng: random.Random, cur: Any,
                   pedidos: list[tuple[Any, ...]], seq_min: int, seq_ent: int,
                   seq_ret: int, seq_ocorr: int, fase_ce: int) -> tuple[int, int, int, int]:
    minutas: list[tuple[Any, ...]] = []
    entregas: list[tuple[Any, ...]] = []
    retiradas: list[tuple[Any, ...]] = []
    ocorrencias: list[tuple[Any, ...]] = []
    fases_ce: list[tuple[Any, ...]] = []
    # balde de consolidação: (dia, uf, modal) -> minuta
    baldes: dict[tuple[date, str, int], int] = {}

    def nova_minuta(dia: date, uf: str, modal: int, exclusiva: bool) -> int:
        nonlocal seq_min
        seq_min += 1
        aereo = modal == ctx.modais["AEREO"]
        transp = ctx.aereo if aereo else (
            ctx.frota if rng.random() < 0.5 else rng.choice(ctx.terceiros))
        veic = None if aereo else (
            rng.choice(ctx.veiculos[transp]) if ctx.veiculos.get(transp) else None)
        rota = ctx.rotas.get(uf, ctx.rota_local)
        minutas.append((seq_min, f"MIN{seq_min:07d}", modal, transp, veic, rota,
                        "EXCLUSIVA" if exclusiva else "CONSOLIDADA",
                        datetime.combine(dia, time(rng.randint(6, 9), rng.randint(0, 59)))))
        return seq_min

    def minuta_para(dia: date, uf: str, modal: int, exclusiva: bool) -> int:
        if exclusiva:
            return nova_minuta(dia, uf, modal, True)
        chave = (dia, uf, modal)
        if chave not in baldes:
            baldes[chave] = nova_minuta(dia, uf, modal, False)
        return baldes[chave]

    def add_entrega(pid: int, mid: int, perna: str, destino: int, prevista: date,
                    chegada: datetime | None, entrada: datetime | None,
                    sucesso: bool, recebedor: str | None) -> None:
        nonlocal seq_ent
        seq_ent += 1
        canhoto = sucesso and rng.random() < 0.9
        entregas.append((seq_ent, pid, mid, perna, destino, prevista, chegada,
                         entrada, recebedor, sucesso, canhoto))

    nomes = ["Maria", "José", "Ana", "Carlos", "Paula", "Roberto", "Fernanda", "Luiz"]
    for (pid, atend, nivel, modal, endereco, uf, _cidade, exped, porte) in pedidos:
        excl = nivel == "EXCLUSIVO"
        lead = ctx.lead.get((modal, uf, _cidade), ctx.lead.get((modal, uf, "São Paulo"), 5))
        # dedicado carrega e sai no mesmo dia; consolidado espera o balde do dia seguinte
        dia_exp = dia_util(exped.date()) if excl else dia_util(exped.date() + timedelta(days=1))
        confirmacao: datetime | None = None
        if atend == "ENTREGA_DIRETA" or atend is None:
            mid = minuta_para(dia_exp, uf, modal, excl)
            chegada = _chegada(rng, dia_exp, lead, excl)
            seq_ent_antes = seq_ent
            falhou = (not excl) and rng.random() < 0.05
            if falhou:
                seq_ocorr += 1
                cod = rng.choice(["DESTINATARIO_AUSENTE", "ENDERECO_NAO_LOCALIZADO", "AVARIA"])
                add_entrega(pid, mid, "DIRETA", endereco, dia_util(dia_exp + timedelta(days=lead)),
                            chegada, None, False, None)
                ocorrencias.append((seq_ocorr, pid, seq_ent, ctx.tipo_ocorr[cod], chegada,
                                    "Falha na entrega; reentrega programada"))
                dia2 = dia_util(chegada.date() + timedelta(days=2))
                mid2 = minuta_para(dia2, uf, modal, False)
                chegada = _chegada(rng, dia2, max(1, lead // 2), False)
            add_entrega(pid, mid if not falhou else mid2, "DIRETA", endereco,
                        dia_util(dia_exp + timedelta(days=lead)), chegada, None, True,
                        rng.choice(nomes))
            del seq_ent_antes
            confirmacao = chegada
        else:
            base_org, infra, base_end = ctx.base_para(uf, rng)
            mid = minuta_para(dia_exp, uf, modal, excl)
            chegada_base = _chegada(rng, dia_exp, max(1, lead - 1), excl)
            lo, hi = ATRASO_ENTRADA_HORAS[infra]
            atraso_entrada = rng.uniform(lo, hi)
            if infra == "BAIXA" and rng.random() < 0.25:
                atraso_entrada *= rng.uniform(1.5, 2.5)  # a vilã em dia de vilania
            if porte in ("MEGA", "GRANDE"):
                # a base confere primeiro a carga dos grandes; a fila sobra p/ o resto
                atraso_entrada *= 0.35
            entrada = somar_horas_uteis(chegada_base, atraso_entrada)
            add_entrega(pid, mid, "TRANSFERENCIA_BASE", base_end,
                        dia_util(dia_exp + timedelta(days=max(1, lead - 1))),
                        chegada_base, entrada, True, None)
            if atend == "RETIRA_BASE":
                seq_ret += 1
                demora = int(rng.expovariate(1 / 4.0))
                dt_ret = somar_horas_uteis(
                    datetime.combine(dia_util(entrada.date() + timedelta(days=demora)),
                                     time(rng.randint(9, 16))), 1)
                retiradas.append((seq_ret, pid, base_org, dt_ret, rng.choice(nomes)))
                confirmacao = entrada
            else:  # ENTREGA_VIA_BASE: última milha da base
                dia_um = dia_util(entrada.date() + timedelta(days=1))
                mid_um = minuta_para(dia_um, uf, ctx.modais["RODOVIARIO"], excl)
                chegada_fim = _chegada(rng, dia_um, rng.randint(1, 2), excl)
                add_entrega(pid, mid_um, "ULTIMA_MILHA_BASE", endereco,
                            dia_util(dia_um + timedelta(days=1)), chegada_fim, None,
                            True, rng.choice(nomes))
                confirmacao = chegada_fim
        fases_ce.append((pid, fase_ce, exped, confirmacao))

    _copiar(cur, "operacao.minuta",
            ("id", "numero", "modalidade_id", "transportador_id", "veiculo_id",
             "rota_id", "tipo_carga", "dt_expedicao"), minutas)
    _copiar(cur, "operacao.entrega",
            ("id", "pedido_id", "minuta_id", "tipo_perna", "endereco_destino_id",
             "dt_prevista", "dt_chegada", "dt_entrada_base", "recebedor",
             "fl_sucesso", "fl_canhoto"), entregas)
    _copiar(cur, "operacao.retirada_base",
            ("id", "pedido_id", "base_id", "dt_retirada", "retirado_por"), retiradas)
    _copiar(cur, "operacao.ocorrencia",
            ("id", "pedido_id", "entrega_id", "tipo_ocorrencia_id", "dt_ocorrencia",
             "observacao"), ocorrencias)
    _copiar(cur, "operacao.pedido_fase",
            ("pedido_id", "fase_id", "dt_entrada", "dt_saida"), fases_ce)
    return seq_min, seq_ent, seq_ret, seq_ocorr


def _chegada(rng: random.Random, saida: date, dias: int, excl: bool) -> datetime:
    if excl:
        # veículo dedicado: direto ao destino, sem paradas de consolidação
        transito = max(1, round(dias * 0.5 * rng.uniform(0.85, 1.05)))
    else:
        transito = max(1, round(dias * rng.uniform(0.75, 1.05)))
        if rng.random() < 0.10:
            transito += rng.randint(1, 3)  # estrada, quebra, clima
    d = dia_util(saida + timedelta(days=transito))
    return datetime.combine(d, time(rng.randint(8, 17), rng.randint(0, 59)))


# o galpão é cross-dock: quase tudo que entra embarca no próprio mês; a foto
# de fim de mês captura a sobra de giro e os lotes-depósito (sobra de campanha
# que o cliente deixa parada no galpão; é daqui que nasce o aging da cobrança)
GIRO_SOBRA = (0.00125, 0.0047)  # fração do lote ainda no galpão na foto do mês
PARADO_PROB_FATOR = 0.15        # prob. de lote-depósito = fator × (0.25 + 0.75×deposito)
PARADO_SOBRA = (0.0034, 0.0101)  # fração do lote que fica parada
PARADO_VIDA_MESES = (16, 56)    # até devolução/descarte
# Pareto do galpão (painel Q3): 5 âncoras + 3 médios; a cauda decai rápido e
# micro/pequeno quase não estoca
ALVO_GALPAO_PCT = [26.3, 20.1, 14.9, 11.6, 7.0, 4.7, 2.2, 1.8]
ALVO_GALPAO_DECAI = 0.72
# estoque sobe antes da temporada (jul-set), seca em abril e nov-dez
FATOR_GIRO_MES = {1: 0.9, 2: 0.85, 3: 0.9, 4: 0.6, 5: 0.8, 6: 1.0,
                  7: 1.5, 8: 1.7, 9: 1.65, 10: 1.1, 11: 0.7, 12: 0.6}
ULTIMA_FOTO = date(2026, 7, 1)  # o mundo termina em julho/2026


def _proximo_mes(m: date) -> date:
    return date(m.year + (m.month == 12), (m.month % 12) + 1, 1)


def _alvos_galpao(gab: list[dict[str, str]]) -> dict[str, float]:
    """Participação-alvo de cada cliente no m³ do galpão (normalizada em 1)."""
    est = [g for g in gab if g["estoca"] == "True"]
    est.sort(key=lambda g: -(float(g["pedidos_mes_base"]) * (0.4 + float(g["deposito"]))))
    dep_medio = sum(float(g["deposito"]) for g in est) / len(est)
    alvos: dict[str, float] = {}
    fila = list(ALVO_GALPAO_PCT)
    v = fila[-1] * ALVO_GALPAO_DECAI
    for g in est:
        if fila:
            alvo = fila.pop(0)
        else:
            alvo = v
            v *= ALVO_GALPAO_DECAI
        # desconta o boost de acumulação: quem tem deposito alto estaciona mais
        # lotes de vida longa e estouraria o alvo sem esta compensação
        tilt = 0.31 + 0.69 * ((0.25 + 0.75 * float(g["deposito"]))
                              / (0.25 + 0.75 * dep_medio))
        alvos[g["sigla"]] = alvo / tilt
    total = sum(alvos.values())
    return {k: x / total for k, x in alvos.items()}


def _snapshots(cur: Any, rng: random.Random) -> None:
    """Fotos mensais de estoque por item × local com física de cross-dock."""
    with files("logistica_otif_mlops.seed.dados").joinpath(
            "gabarito_clientes.csv").open(encoding="utf-8") as f:
        gab = list(csv.DictReader(f))
    deposito = {g["sigla"]: float(g["deposito"]) for g in gab}
    alvo = _alvos_galpao(gab)
    cur.execute("""
        select r.id, r.item_id, r.local_estoque_id,
               date_trunc('month', r.dt_recebimento)::date, r.quantidade, o.sigla
        from operacao.recebimento r
        join operacao.item i on i.id = r.item_id
        join operacao.organizacao o on o.id = i.cliente_id
        where r.dt_recebimento is not null
        order by r.id""")
    lotes = [(iid, loc, mes, qtd, sigla)
             for _rid, iid, loc, mes, qtd, sigla in cur.fetchall()
             if mes <= ULTIMA_FOTO]  # recebimento atrasado após o fim do mundo cai fora
    # escala por cliente: alvo de galpão ÷ participação real nos recebimentos
    qtd_cli: dict[str, float] = defaultdict(float)
    for _, _, _, qtd, sigla in lotes:
        qtd_cli[sigla] += qtd
    qtd_total = sum(qtd_cli.values())
    escala = {s: alvo[s] * qtd_total / qtd_cli[s]
              for s in alvo if qtd_cli.get(s)}
    saldo: dict[tuple[int, int], dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for iid, loc, mes, qtd, sigla in lotes:
        pos = saldo[(iid, loc)]
        w = escala.get(sigla, 0.0)
        pos[mes] += qtd * w * rng.uniform(*GIRO_SOBRA) * FATOR_GIRO_MES[mes.month]
        if rng.random() < PARADO_PROB_FATOR * (0.25 + 0.75 * deposito.get(sigla, 0.0)):
            sobra = qtd * w * rng.uniform(*PARADO_SOBRA)
            m, vida = mes, rng.randint(*PARADO_VIDA_MESES)
            for _ in range(vida):
                pos[m] += sobra
                m = _proximo_mes(m)
                if m > ULTIMA_FOTO:
                    break
    cur.execute("select i.id, i.volume_m3, coalesce(i.valor_unitario, 0) from operacao.item i")
    info = {iid: (float(v), float(val)) for iid, v, val in cur.fetchall()}

    linhas: list[tuple[Any, ...]] = []
    seq = 0
    for (iid, loc), meses in saldo.items():
        vol_u, val_u = info[iid]
        for mes in sorted(meses):
            q = int(meses[mes])
            if q <= 0:
                continue
            seq += 1
            fim_mes = _proximo_mes(mes) - timedelta(days=1)
            danificado = round(q * val_u * 0.01, 2) if rng.random() < 0.06 else 0
            linhas.append((seq, fim_mes, iid, loc, q, round(q * vol_u, 4),
                           round(q * val_u, 2), danificado))
    _copiar(cur, "operacao.estoque_snapshot",
            ("id", "data", "item_id", "local_estoque_id", "qtde_saldo", "m3_ocupado",
             "valor_material", "valor_danificado"), linhas)


def _copiar(cur: Any, tabela: str, colunas: tuple[str, ...],
            linhas: list[tuple[Any, ...]]) -> None:
    if not linhas:
        return
    with cur.copy(f"COPY {tabela} ({', '.join(colunas)}) FROM STDIN") as copia:
        for linha in linhas:
            copia.write_row(linha)


if __name__ == "__main__":
    executar()
