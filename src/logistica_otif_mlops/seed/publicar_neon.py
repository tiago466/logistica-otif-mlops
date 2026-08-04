"""Publica um recorte do mundo local no Neon (o ambiente de homologação).

Por que um recorte: o mundo completo tem ~5,3 GB e o plano free do Neon dá 512 MB.
Em vez de degradar o mundo para caber na nuvem, mantemos **dois ambientes com
propósitos diferentes**, que é como projeto de verdade funciona:

    dev   (Postgres local, 11 anos completos) -> treino, validação out-of-time, EDA
    hmlg  (Neon, janela recente)              -> demonstração, estudo de SQL, API

Os dados de referência (carteira, catálogo, rede, réguas, parâmetros) vão
INTEIROS: o recorte é só do movimento. Assim quem estuda na nuvem vê a mesma
estrutura e os mesmos joins, com menos linhas.

Rodar:
    uv run python -m logistica_otif_mlops.seed.publicar_neon
    uv run python -m logistica_otif_mlops.seed.publicar_neon --desde 2026-01-01

Antes de rodar, o schema precisa existir no destino:
    DATABASE_URL="$NEON_DATABASE_URL" uv run alembic upgrade head
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

import psycopg

from logistica_otif_mlops.config import obter_settings, url_libpq

CORTE_PADRAO = date(2025, 11, 1)

# Referência: vai inteira (é o dicionário do mundo, não o movimento).
# A ordem respeita as dependências de chave estrangeira.
TABELAS_REFERENCIA = [
    "operacao.organizacao",
    "operacao.endereco",
    "operacao.transportador",
    "operacao.veiculo",
    "operacao.rota",
    "operacao.modalidade",
    "operacao.lead_time",
    "operacao.fase",
    "operacao.sla_fase",
    "operacao.tipo_ocorrencia",
    "operacao.campanha",
    "operacao.local_estoque",
    "operacao.item",
    "custos.categoria_custo",
    "custos.tarifa_armazenagem",
    "custos.parametro_financeiro",
]

# Movimento: recortado pela janela. `{corte}` é substituído pela data.
# A ordem também respeita as FKs (minuta antes de entrega, entrega antes de ocorrência).
TABELAS_MOVIMENTO: list[tuple[str, str]] = [
    ("operacao.pedido",
     "select * from operacao.pedido where dt_solicitacao >= '{corte}'"),
    ("operacao.pedido_item",
     "select pi.* from operacao.pedido_item pi join operacao.pedido p on p.id = pi.pedido_id"
     " where p.dt_solicitacao >= '{corte}'"),
    ("operacao.pedido_fase",
     "select pf.* from operacao.pedido_fase pf join operacao.pedido p on p.id = pf.pedido_id"
     " where p.dt_solicitacao >= '{corte}'"),
    ("operacao.ordem_coleta",
     "select oc.* from operacao.ordem_coleta oc join operacao.pedido p on p.id = oc.pedido_id"
     " where p.dt_solicitacao >= '{corte}'"),
    ("operacao.minuta",
     "select distinct m.* from operacao.minuta m"
     " join operacao.entrega e on e.minuta_id = m.id"
     " join operacao.pedido p on p.id = e.pedido_id where p.dt_solicitacao >= '{corte}'"),
    ("operacao.entrega",
     "select e.* from operacao.entrega e join operacao.pedido p on p.id = e.pedido_id"
     " where p.dt_solicitacao >= '{corte}'"),
    ("operacao.ocorrencia",
     "select o.* from operacao.ocorrencia o join operacao.pedido p on p.id = o.pedido_id"
     " where p.dt_solicitacao >= '{corte}'"),
    ("operacao.retirada_base",
     "select r.* from operacao.retirada_base r join operacao.pedido p on p.id = r.pedido_id"
     " where p.dt_solicitacao >= '{corte}'"),
    ("operacao.recebimento",
     "select * from operacao.recebimento where dt_recebimento >= '{corte}'"),
    ("operacao.estoque_snapshot",
     "select * from operacao.estoque_snapshot where data >= '{corte}'"),
    ("operacao.coleta",
     "select * from operacao.coleta where dt_solicitacao >= '{corte}'"),
    ("operacao.positivacao",
     "select p.* from operacao.positivacao p"
     " left join operacao.pedido ped on ped.id = p.pedido_id"
     " where p.dt_abertura >= '{corte}'"
     "   and (p.pedido_id is null or ped.dt_solicitacao >= '{corte}')"),
    ("custos.faturamento_operacao",
     "select * from custos.faturamento_operacao where dt_faturamento >= '{corte}'"),
    ("custos.custo_operacao",
     "select * from custos.custo_operacao where dt_competencia >= '{corte}'"),
]


def executar(corte: date, apagar_antes: bool) -> None:
    cfg = obter_settings()
    if not cfg.database_url or not cfg.neon_database_url:
        raise SystemExit(
            "Faltou configurar DATABASE_URL (origem) e NEON_DATABASE_URL (destino) no .env")

    print(f"publicando janela a partir de {corte:%d/%m/%Y}")
    with psycopg.connect(url_libpq(cfg.database_url)) as origem, \
            psycopg.connect(url_libpq(cfg.neon_database_url)) as destino:
        if apagar_antes:
            _limpar(destino)
        total = 0
        for tabela in TABELAS_REFERENCIA:
            total += _copiar(origem, destino, tabela, f"select * from {tabela}")
        for tabela, consulta in TABELAS_MOVIMENTO:
            total += _copiar(origem, destino, tabela, consulta.format(corte=corte))
        _ajustar_sequencias(destino)
        destino.commit()
        print(f"\npublicado: {total:,} linhas")
        _relatorio(destino)


def _limpar(destino: psycopg.Connection[Any]) -> None:
    """Zera o destino para uma republicação limpa (idempotência do script)."""
    alvos = ", ".join(t for t, _ in reversed(TABELAS_MOVIMENTO))
    referencia = ", ".join(reversed(TABELAS_REFERENCIA))
    with destino.cursor() as cur:
        cur.execute(f"truncate {alvos}, {referencia} restart identity cascade")
    destino.commit()
    print("destino limpo")


def _copiar(origem: psycopg.Connection[Any], destino: psycopg.Connection[Any],
            tabela: str, consulta: str) -> int:
    """Streaming COPY: sai da origem e entra no destino sem passar por disco."""
    linhas = 0
    with origem.cursor().copy(f"COPY ({consulta}) TO STDOUT") as saida, \
            destino.cursor().copy(f"COPY {tabela} FROM STDIN") as entrada:
        for bloco in saida:
            entrada.write(bloco)
    with destino.cursor() as cur:
        cur.execute(f"select count(*) from {tabela}")
        resultado = cur.fetchone()
        linhas = resultado[0] if resultado else 0
    print(f"  {tabela:<32} {linhas:>10,}")
    return linhas


def _ajustar_sequencias(destino: psycopg.Connection[Any]) -> None:
    """Reposiciona as sequences: sem isso, o primeiro insert novo colide."""
    with destino.cursor() as cur:
        for tabela in [t for t, _ in TABELAS_MOVIMENTO] + TABELAS_REFERENCIA:
            esquema, nome = tabela.split(".")
            cur.execute(
                "select setval(pg_get_serial_sequence(%s, 'id'),"
                " coalesce((select max(id) from " + tabela + "), 1))", (tabela,))
            del esquema, nome


def _relatorio(destino: psycopg.Connection[Any]) -> None:
    with destino.cursor() as cur:
        cur.execute("select pg_size_pretty(pg_database_size(current_database()))")
        tamanho = cur.fetchone()
        print(f"tamanho no destino: {tamanho[0] if tamanho else '?'} (free do Neon: 512 MB)")


def principal() -> None:
    parser = argparse.ArgumentParser(description="Publica um recorte do mundo no Neon")
    parser.add_argument("--desde", type=date.fromisoformat, default=CORTE_PADRAO,
                        help="data de corte da janela (AAAA-MM-DD)")
    parser.add_argument("--manter", action="store_true",
                        help="não limpa o destino antes de copiar")
    args = parser.parse_args()
    executar(args.desde, apagar_antes=not args.manter)


if __name__ == "__main__":
    principal()
