"""G2: o motor do tempo — recebimentos, pedidos, fases e DOCs (2016→2026-07).

Simulação mês a mês, calibrada pelos painéis da anamnese (2025 ≈ 221k pedidos,
~4,4 linhas/pedido, curva mensal em declínio). A capacidade da esteira é finita
e a fila estoura nas campanhas; a priorização do Elias decide quem espera.
Escrita em massa via COPY (psycopg) por performance.

Rodar: uv run python -m logistica_otif_mlops.seed.gerador.g2_movimento
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from importlib.resources import files
from typing import Any

from sqlalchemy import func, select

from logistica_otif_mlops.db import criar_engine, criar_fabrica_de_sessoes
from logistica_otif_mlops.models import (
    Endereco,
    Fase,
    Item,
    LeadTime,
    LocalEstoque,
    Modalidade,
    Organizacao,
    Pedido,
    SlaFase,
    TipoOcorrencia,
)

SEMENTE = 20260802
INICIO = date(2016, 1, 4)
FIM = date(2026, 7, 31)

# alvo de pedidos por ano (âncora: painel 2025 = 221k; rampa de crescimento e declínio)
ALVO_PEDIDOS_ANO = {
    2016: 25_000, 2017: 46_000, 2018: 92_000, 2019: 142_000, 2020: 182_000,
    2021: 232_000, 2022: 252_000, 2023: 256_000, 2024: 240_000, 2025: 221_000,
    2026: 92_000,  # jan-jul
}
# 2025: proporções mensais do painel de linhas do Elias (o êxodo filmado)
PESOS_2025 = [102.7, 87.7, 85.8, 79.8, 95.4, 87.3, 103.0, 76.9, 74.5, 79.5, 60.6, 50.1]
# demais anos: sazonalidade típica (picos out-dez + jan)
PESOS_PADRAO = [95, 82, 85, 88, 96, 88, 92, 90, 95, 110, 128, 121]

# capacidade da esteira em LINHAS/dia útil, por ano (cresce com contratações;
# ajuste fino de regime pós-2024 conforme observações internas de equipe)
CAPACIDADE_ANO = {
    2016: 900, 2017: 1100, 2018: 1500, 2019: 1900, 2020: 2200, 2021: 2400,
    2022: 2400, 2023: 2400, 2024: 2150, 2025: 2100, 2026: 2100,
}
BOOST_SEGMENTO = {  # campanhas por segmento: mês -> multiplicador
    "ALIMENTICIO": {3: 1.5, 4: 1.8, 12: 1.4},          # Páscoa (Woonka) + Natal
    "COSMETICOS_DERMATOLOGICOS": {5: 1.7, 12: 1.3},    # Dia das Mães
    "MODA_ACESSORIOS": {5: 1.6, 12: 1.5},              # Mães + Natal
    "JOALHERIA": {5: 1.5, 6: 1.3, 12: 1.5},
    "ELETRONICOS": {11: 2.2, 12: 1.4},                 # Black Friday (Stark é black)
}
PRIORIDADE = {"MEGA": 0.15, "GRANDE": 0.5}  # fator de espera na fila (Elias); resto 1.0
TOP5 = {"WKA", "DRH", "STK", "LXM", "GCH"}
# assinatura de densidade por cliente (painel Q4: o nº 2 em veículos é o nº 1 em
# m³, porque chega em carreta cheia). O porte dita o tamanho da remessa; a escala
# está normalizada para o m³ expedido no ano bater o painel (~340-360k m³).
TAMANHO_POR_PORTE = {"MEGA": 1.05, "GRANDE": 0.78, "MEDIA": 0.52,
                     "PEQUENA": 0.39, "MICRO": 0.31}
# o inchaço: mais clientes, mais SKUs, mais exceções, mesma casa. A esteira
# inteira foi ficando mais lenta ano a ano, e é isso que corrói a reputação.
FATOR_INCHACO = {2016: 1.0, 2017: 1.0, 2018: 1.02, 2019: 1.05, 2020: 1.08,
                 2021: 1.12, 2022: 1.16, 2023: 1.20, 2024: 1.22, 2025: 1.24,
                 2026: 1.22}
# recebimento tem calendário próprio (painel Q4): veículos picam em ago-set
# (reabastecimento pré-temporada) e o volume entra forte em jan-fev
FATOR_RECEB_MES = {1: 1.25, 2: 1.20, 3: 1.0, 4: 0.95, 5: 0.95, 6: 0.95,
                   7: 1.05, 8: 1.35, 9: 1.30, 10: 1.0, 11: 0.75, 12: 0.70}


# ----------------------------- tempo útil -----------------------------
def dia_util(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def somar_dias_uteis(d: date, n: int) -> date:
    while n > 0:
        d = d + timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def somar_horas_uteis(dt: datetime, horas: float) -> datetime:
    """Avança horas úteis (jornada 08-18h, seg-sex)."""
    restante = horas
    atual = dt
    while True:
        if atual.weekday() >= 5 or atual.time() >= time(18):
            atual = datetime.combine(dia_util(atual.date() + timedelta(days=1)), time(8))
            continue
        if atual.time() < time(8):
            atual = datetime.combine(atual.date(), time(8))
        fim_do_dia = datetime.combine(atual.date(), time(18))
        disponivel = (fim_do_dia - atual).total_seconds() / 3600
        if restante <= disponivel:
            return atual + timedelta(hours=restante)
        restante -= disponivel
        atual = fim_do_dia


def meses(a: date, b: date) -> list[tuple[int, int]]:
    saida = []
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        saida.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return saida


def _ler(nome: str) -> list[dict[str, str]]:
    with files("logistica_otif_mlops.seed.dados").joinpath(nome).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ----------------------------- carga de contexto -----------------------------
class Mundo:
    """Snapshot em memória do mundo estático (ids e réguas)."""

    def __init__(self) -> None:
        engine = criar_engine()
        fabrica = criar_fabrica_de_sessoes(engine)
        with fabrica() as s:
            self.fases = {f.codigo: f.id for f in s.scalars(select(Fase))}
            self.sla = {sf.fase_id: (sf.horas_uteis_meta, sf.horas_uteis_limite)
                        for sf in s.scalars(select(SlaFase))}
            self.modais = {m.codigo: m.id for m in s.scalars(select(Modalidade))}
            self.lead = {(lt.modalidade_id, lt.uf, lt.cidade): lt.dias_uteis
                         for lt in s.scalars(select(LeadTime))}
            self.tipo_ocorr = {t.codigo: t.id for t in s.scalars(select(TipoOcorrencia))}
            self.locais_matriz = [
                loc.id for loc in s.scalars(
                    select(LocalEstoque).where(LocalEstoque.codigo.like("TB%")))
            ]
            self.clientes = {o.sigla: o for o in s.scalars(
                select(Organizacao).where(Organizacao.tipo_parceria == "CLIENTE"))}
            enderecos = s.execute(
                select(Endereco.id, Endereco.organizacao_id, Endereco.uf, Endereco.cidade,
                       Endereco.fl_principal)
            ).all()
            self.destinos: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
            for eid, org_id, uf, cidade, principal in enderecos:
                if not principal:
                    self.destinos[org_id].append((eid, uf, cidade))
            itens = s.execute(
                select(Item.id, Item.cliente_id, Item.peso_kg, Item.volume_m3)
            ).all()
            self.itens: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
            for iid, cid, peso, vol in itens:
                self.itens[cid].append((iid, float(peso), float(vol)))
        self.gabarito = {g["sigla"]: g for g in _ler("gabarito_clientes.csv")}


# ----------------------------- o motor -----------------------------
def executar() -> None:
    engine = criar_engine()
    fabrica = criar_fabrica_de_sessoes(engine)
    with fabrica() as s:
        if s.scalar(select(func.count(Pedido.id))):
            print("g2: já existem pedidos; nada a fazer.")
            return
    mundo = Mundo()
    rng = random.Random(SEMENTE)
    raw = engine.raw_connection()
    cur = raw.cursor()

    seq_pedido = 0
    seq_receb = 0
    stats: dict[int, list[int]] = defaultdict(lambda: [0, 0])  # ano -> [pedidos, linhas]

    for ano, mes in meses(INICIO, FIM):
        pesos = PESOS_2025 if ano == 2025 else PESOS_PADRAO
        peso_total = sum(pesos[: 7 if ano == 2026 else 12])
        alvo_mes = round(ALVO_PEDIDOS_ANO[ano] * pesos[mes - 1] / peso_total)
        ativos = _ativos(mundo, ano, mes)
        if not ativos:
            continue
        pesos_cli = _pesos_clientes(mundo, ativos, mes)
        soma_pesos = sum(pesos_cli.values()) or 1.0
        lote: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
        demanda_dia: dict[date, int] = defaultdict(int)
        pedidos_mes: list[dict[str, Any]] = []

        for sigla in ativos:
            n = round(alvo_mes * pesos_cli[sigla] / soma_pesos)
            if n <= 0:
                continue
            seq_pedido = _gerar_pedidos_cliente(
                mundo, rng, sigla, ano, mes, n, seq_pedido, pedidos_mes, demanda_dia)
        _agendar_fases(mundo, rng, ano, pedidos_mes, demanda_dia, lote)
        seq_receb = _gerar_recebimentos(mundo, rng, ano, mes, ativos, seq_receb, lote)

        _copiar(cur, "operacao.pedido", PEDIDO_COLS, lote["pedido"])
        _copiar(cur, "operacao.pedido_item", ("pedido_id", "item_id", "quantidade"),
                lote["pedido_item"])
        _copiar(cur, "operacao.pedido_fase", ("pedido_id", "fase_id", "dt_entrada", "dt_saida"),
                lote["pedido_fase"])
        _copiar(cur, "operacao.ordem_coleta",
                ("pedido_id", "local_estoque_id", "dt_emissao", "dt_conclusao", "status"),
                lote["ordem_coleta"])
        _copiar(cur, "operacao.ocorrencia",
                ("pedido_id", "tipo_ocorrencia_id", "dt_ocorrencia", "observacao"),
                lote["ocorrencia"])
        _copiar(cur, "operacao.recebimento", RECEB_COLS, lote["recebimento"])
        raw.commit()
        stats[ano][0] += len(pedidos_mes)
        stats[ano][1] += sum(p["linhas"] for p in pedidos_mes)
        if mes == 12 or (ano, mes) == (2026, 7):
            a, li = stats[ano]
            print(f"  {ano}: {a:>7} pedidos · {li:>8} linhas · média {li / max(a, 1):.1f}")

    for tabela in ("pedido", "pedido_item", "pedido_fase", "ordem_coleta",
                   "ocorrencia", "recebimento"):
        cur.execute(
            f"SELECT setval(pg_get_serial_sequence('operacao.{tabela}', 'id'), "
            f"(SELECT COALESCE(MAX(id), 1) FROM operacao.{tabela}))"
        )
    raw.commit()
    cur.close()
    raw.close()
    total_p = sum(v[0] for v in stats.values())
    total_l = sum(v[1] for v in stats.values())
    print(f"G2 OK: {total_p} pedidos · {total_l} linhas · média {total_l / total_p:.2f}")


PEDIDO_COLS = ("id", "numero", "cliente_id", "endereco_id", "modalidade_id", "canal",
               "nivel_servico", "tipo_atendimento", "dt_solicitacao",
               "dt_prazo_saida_expedicao", "dt_prazo_entrega", "peso_teorico_kg",
               "volume_teorico_m3", "peso_real_kg", "volume_real_m3", "nf_numero")
RECEB_COLS = ("id", "item_id", "local_estoque_id", "numero_agendamento", "fornecedor_nome",
              "nf_entrada", "quantidade", "dt_validade", "dt_prevista", "dt_recebimento",
              "status")


def _ativos(mundo: Mundo, ano: int, mes: int) -> list[str]:
    """Quem está em contrato no mês. A vigência exata é aplicada por DIA em
    `_gerar_pedidos_cliente`: aqui o mês entra inteiro se houver qualquer
    sobreposição, e lá os dias fora do contrato são descartados."""
    ref = date(ano, mes, 15)
    out = []
    for sigla, org in mundo.clientes.items():
        if org.dt_inicio_contrato > ref:
            continue
        if org.dt_cancelamento and org.dt_cancelamento < ref:
            continue
        if not mundo.destinos.get(org.id) or not mundo.itens.get(org.id):
            continue
        out.append(sigla)
    return out


def _pesos_clientes(mundo: Mundo, ativos: list[str], mes: int) -> dict[str, float]:
    pesos = {}
    for sigla in ativos:
        g = mundo.gabarito[sigla]
        org = mundo.clientes[sigla]
        boost = BOOST_SEGMENTO.get(org.segmento or "", {}).get(mes, 1.0)
        pesos[sigla] = float(g["pedidos_mes_base"]) * boost
    return pesos


def _gerar_pedidos_cliente(mundo: Mundo, rng: random.Random, sigla: str, ano: int, mes: int,
                           n: int, seq: int, saida: list[dict[str, Any]],
                           demanda_dia: dict[date, int]) -> int:
    org = mundo.clientes[sigla]
    g = mundo.gabarito[sigla]
    destinos = mundo.destinos[org.id]
    itens = mundo.itens[org.id]
    tamanho = TAMANHO_POR_PORTE.get(org.porte or "MEDIA", 1.0)
    pct_grade = float(g["pct_grade"])
    pct_excl = float(g["pct_exclusivo"])
    # a vigência do contrato vale por DIA, não por mês: cliente que cancelou no
    # dia 17 não faz pedido no dia 20. Sem este corte, o mês inteiro ficava
    # elegível e o cadastro contradizia o movimento.
    dias = [dia_util(date(ano, mes, d)) for d in range(1, 29)]
    dias = [d for d in dias
            if d >= org.dt_inicio_contrato
            and (org.dt_cancelamento is None or d <= org.dt_cancelamento)]
    if not dias:
        return seq
    n_grade = round(n * pct_grade)
    # grades saem em rajadas: poucos dias concentram muitos pedidos
    dias_grade = rng.sample(dias, k=min(len(dias), max(1, n_grade // 120 + 1)))
    for k in range(n):
        seq += 1
        em_grade = k < n_grade
        d = rng.choice(dias_grade) if em_grade else rng.choice(dias)
        sol = datetime.combine(d, time(rng.randint(8, 16), rng.randint(0, 59)))
        eid, uf, cidade = rng.choice(destinos)
        exclusivo = rng.random() < pct_excl
        modal_nome = "AEREO" if (exclusivo and rng.random() < 0.5) or rng.random() < 0.08 \
            else "RODOVIARIO"
        modal = mundo.modais[modal_nome]
        lead = mundo.lead.get((modal, uf, cidade),
                              mundo.lead.get((modal, uf, "São Paulo"), 5))
        n_linhas = rng.randint(2, 6) if em_grade else max(1, round(rng.gauss(5, 3)))
        escolha = rng.sample(itens, k=min(n_linhas, len(itens)))
        # a quantidade de cada linha nasce aqui, e o peso/volume do pedido é a
        # SOMA das linhas: o mesmo número que o sistema calcularia (a remessa
        # escala com o porte, MEGA embarca carreta e micro embarca caixa).
        # `quantidade` conta VOLUMES (caixas), que é como o painel de
        # recebimento conta: ~2,15 Mi volumes/ano entrando no galpão.
        linhas = [(iid, pu, vu, max(1, round(rng.randint(1, 4) * tamanho)))
                  for iid, pu, vu in escolha]
        peso = sum(pu * q for _, pu, _, q in linhas)
        vol = sum(vu * q for _, _, vu, q in linhas)
        if exclusivo:
            prazo_saida = somar_dias_uteis(d, 2)
            prazo_entrega = somar_dias_uteis(prazo_saida, max(1, lead // 2))
        else:
            # promessa interna realista: 7 dias úteis de esteira (o que a empresa
            # entrega em ano saudável; a fila dos anos ruins é que estoura)
            prazo_saida = somar_dias_uteis(d, 7)
            prazo_entrega = somar_dias_uteis(prazo_saida, lead)
        saida.append({
            "id": seq, "numero": f"SS{seq:07d}", "org": org, "sigla": sigla,
            "endereco": eid, "uf": uf, "modal": modal, "sol": sol, "grade": em_grade,
            "exclusivo": exclusivo, "prazo_saida": prazo_saida,
            "prazo_entrega": prazo_entrega, "itens": linhas, "linhas": len(linhas),
            "peso": peso, "vol": vol,
        })
        demanda_dia[dia_util(d + timedelta(days=2))] += len(escolha)
    return seq


def _agendar_fases(mundo: Mundo, rng: random.Random, ano: int,
                   pedidos: list[dict[str, Any]], demanda_dia: dict[date, int],
                   lote: dict[str, list[tuple[Any, ...]]]) -> None:
    cap = CAPACIDADE_ANO[ano]
    backlog: dict[date, float] = {}
    acumulado = 0.0
    for d in sorted(demanda_dia):
        acumulado = max(0.0, acumulado + demanda_dia[d] - cap)
        backlog[d] = acumulado / cap  # dias de fila
    f = mundo.fases
    sla = mundo.sla

    def dur(codigo: str, fator: float = 1.0) -> float:
        meta, limite = sla[f[codigo]]
        # regime normal abaixo da META; cauda ocasional até o limite (dia ruim)
        base = rng.uniform(meta * 0.45, meta * 1.0)
        if rng.random() < 0.08:
            base = rng.uniform(meta, limite * 1.05)
        return base * fator

    for p in pedidos:
        org = p["org"]
        prio = 0.15 if p["sigla"] in TOP5 else PRIORIDADE.get(org.porte or "", 1.0)
        stress = backlog.get(dia_util(p["sol"].date() + timedelta(days=2)), 0.0)
        excl = bool(p["exclusivo"])
        # o inchaço não cai igual para todos: a conta da casa cheia é paga por
        # quem não tem padrinho (quem é prioridade absorve pouco do atraso)
        inchaco = 1.0 + (FATOR_INCHACO[ano] - 1.0) * (0.25 + 0.75 * prio)
        # exclusivo é tratamento-relâmpago: comprime tudo e fura a fila
        fator_adm = 0.3 if excl else inchaco
        fator_prod = 0.3 if excl else inchaco * (1.0 + min(stress, 4.0) * 0.2 * prio)
        t = p["sol"]
        registros: list[tuple[str, datetime, datetime]] = []

        def fase(codigo: str, horas: float, inicio: datetime,
                 reg: list[tuple[str, datetime, datetime]] = registros) -> datetime:
            fim = somar_horas_uteis(inicio, horas)
            reg.append((codigo, inicio, fim))
            return fim

        t = fase("EA", dur("EA", fator_adm), t)
        if p["grade"] and rng.random() < 0.3:
            t = fase("DC", dur("DC", fator_adm), t)
        t = fase("PC", dur("PC", fator_adm), t)
        if rng.random() < 0.015:
            lote["ocorrencia"].append(
                (p["id"], mundo.tipo_ocorr["DIVERGENCIA_CADASTRO"], t,
                 "Divergência de cadastro na pré-conferência"))
        t = fase("PL", dur("PL", fator_adm), t)
        if not excl:
            espera = min(backlog.get(dia_util(t.date()), 0.0), 4.0) * 8 * prio * 0.5
            if espera > 0.5:
                t = somar_horas_uteis(t, espera)
        if rng.random() < 0.02:
            t = fase("EX", dur("EX", fator_adm), t)
        n_locais = min(len(mundo.locais_matriz),
                       1 + int(rng.random() * min(p["linhas"], 4) * 0.9))
        locais = rng.sample(mundo.locais_matriz, k=n_locais)
        ini_cf = t
        # cada local coleta no seu próprio ritmo (equipes e estoques diferentes);
        # o pedido só anda quando o ÚLTIMO fecha, mais a consolidação no dock.
        # É daqui que nasce "mais divisões de DOC = mais risco de atraso".
        fim_locais = []
        for loc in locais:
            horas = dur("CF", fator_prod) * rng.uniform(0.7, 1.3)
            if rng.random() < 0.12:
                horas *= rng.uniform(1.4, 2.2)  # local travado: falta saldo, conferência
            fim_loc = somar_horas_uteis(ini_cf, horas)
            fim_locais.append(fim_loc)
            lote["ordem_coleta"].append((p["id"], loc, ini_cf, fim_loc, "COLETADA"))
        t = somar_horas_uteis(max(fim_locais), (n_locais - 1) * 0.8)
        registros.append(("CF", ini_cf, t))
        t = fase("ME", dur("ME", fator_prod) * (1 + p["linhas"] / 40), t)
        t = fase("EN", dur("EN", fator_adm), t)
        t = fase("EC", dur("EC", fator_prod), t)

        peso_real = None if rng.random() < 0.03 else round(p["peso"] * rng.uniform(0.9, 1.18), 3)
        vol_real = None if peso_real is None else round(p["vol"] * rng.uniform(0.88, 1.2), 4)
        tipo_atend = _tipo_atendimento(rng, p["uf"])
        prazo_entrega = p["prazo_entrega"]
        if p["exclusivo"]:
            tipo_atend = "ENTREGA_DIRETA"  # veículo dedicado não passa em base
        elif tipo_atend != "ENTREGA_DIRETA":
            # praça atendida via base tem prazo maior na tabela (elo do parceiro)
            prazo_entrega = somar_dias_uteis(prazo_entrega, 3)
        lote["pedido"].append((
            p["id"], p["numero"], org.id, p["endereco"], p["modal"],
            "GRADE" if p["grade"] else "WEB",
            "EXCLUSIVO" if p["exclusivo"] else "PADRAO", tipo_atend, p["sol"],
            p["prazo_saida"], prazo_entrega, round(p["peso"], 3), round(p["vol"], 4),
            peso_real, vol_real, f"NF{p['id']:08d}",
        ))
        for iid, _, _, qtd in p["itens"]:
            lote["pedido_item"].append((p["id"], iid, qtd))
        for codigo, ini, fim in registros:
            lote["pedido_fase"].append((p["id"], f[codigo], ini, fim))


def _tipo_atendimento(rng: random.Random, uf: str) -> str:
    if uf in ("SC", "PR", "RS"):
        return "ENTREGA_DIRETA" if rng.random() < 0.85 else "RETIRA_BASE"
    sorteio = rng.random()
    if sorteio < 0.62:
        return "ENTREGA_VIA_BASE"
    if sorteio < 0.85:
        return "RETIRA_BASE"
    return "ENTREGA_DIRETA"


def _gerar_recebimentos(mundo: Mundo, rng: random.Random, ano: int, mes: int,
                        ativos: list[str], seq: int,
                        lote: dict[str, list[tuple[Any, ...]]]) -> int:
    fornecedores = ["Gráfica Modelo", "Impressul", "Embalatec", "Promo Print",
                    "Fábrica do cliente", "Serigrafia Central"]
    for sigla in ativos:
        g = mundo.gabarito[sigla]
        if g["estoca"] != "True":
            continue
        org = mundo.clientes[sigla]
        itens = mundo.itens[org.id]
        sazonal = FATOR_RECEB_MES[mes]
        n_receb = round({"MEGA": rng.randint(14, 30), "GRANDE": rng.randint(6, 14)}.get(
            org.porte or "", rng.randint(1, 5)) * sazonal)
        deposito = float(g["deposito"])
        for _ in range(n_receb):
            seq += 1
            iid, _, _ = rng.choice(itens)
            d = dia_util(date(ano, mes, rng.randint(1, 28)))
            prevista = d
            atraso = rng.random() < 0.12
            recebido = datetime.combine(
                d + timedelta(days=rng.randint(1, 5) if atraso else 0),
                time(rng.randint(8, 17), rng.randint(0, 59)))
            status = "DIVERGENTE" if rng.random() < 0.03 else "RECEBIDO"
            # a carga por veículo também é sazonal: jan-fev chega carreta cheia
            qtd = round(rng.randint(50, 4000) * (1.35 if mes in (1, 2) else 1.0))
            if deposito > 0.4 and rng.random() < deposito * 0.5:
                qtd = int(qtd * rng.uniform(2.0, 4.0))  # lote-depósito (entra e não sai)
            validade = None
            if rng.random() < 0.25:
                validade = d + timedelta(days=rng.randint(180, 1100))
            lote["recebimento"].append((
                seq, iid, rng.choice(mundo.locais_matriz),
                f"AG{seq:07d}" if rng.random() > 0.15 else None,
                rng.choice(fornecedores), f"NFE{seq:08d}", qtd, validade, prevista,
                recebido, status,
            ))
    return seq


def _copiar(cur: Any, tabela: str, colunas: tuple[str, ...],
            linhas: list[tuple[Any, ...]]) -> None:
    if not linhas:
        return
    sql = f"COPY {tabela} ({', '.join(colunas)}) FROM STDIN"
    with cur.copy(sql) as copia:
        for linha in linhas:
            copia.write_row(linha)


if __name__ == "__main__":
    executar()
