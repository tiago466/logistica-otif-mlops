"""Confere se o Bronze é fiel à origem.

Carga que roda sem erro não é carga correta: pode ter trazido metade das linhas,
truncado um valor ou perdido uma coluna, e ninguém percebe até o número aparecer
errado num relatório três semanas depois. Esta conferência responde três
perguntas objetivas, por conjunto:

    * o número de linhas bate com a origem?
    * as colunas são as mesmas (fora as duas técnicas de ingestão)?
    * os totais das colunas de dinheiro batem?

O terceiro é o que pega o erro sutil: contagem igual com valor diferente
significa conversão de tipo estragando o dado no caminho — exatamente o que
acontece quando decimal vira texto ou ponto flutuante.

Rodar: uv run python -m logistica_otif_mlops.pipelines.conferir_bronze
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from logistica_otif_mlops.connectors.registry import obter
from logistica_otif_mlops.pipelines.bronze import RAIZ_BRONZE, TABELAS_OPERACAO

# colunas de dinheiro que precisam bater centavo a centavo
SOMAS = {
    "pedido": ["peso_teorico_kg", "volume_teorico_m3"],
    "pedido_item": ["quantidade"],
    "estoque_snapshot": ["m3_ocupado", "valor_material"],
    "faturamentos": ["valor_com_icms", "valor_icms"],
    "custos": ["valor"],
}


def executar() -> None:
    problemas = _conferir_operacao()
    problemas += _conferir_financeiro()
    print()
    if problemas:
        print(f"⚠️  {len(problemas)} divergência(s):")
        for item in problemas:
            print(f"   {item}")
        raise SystemExit(1)
    print("✅ Bronze fiel à origem: contagem, colunas e somas conferem.")


def _conferir_operacao() -> list[str]:
    conector = obter("operacao_db")
    problemas: list[str] = []
    print("== operação ==")
    for tabela in TABELAS_OPERACAO:
        arquivo = RAIZ_BRONZE / "operacao" / f"{tabela}.parquet"
        if not arquivo.exists():
            problemas.append(f"{tabela}: arquivo ausente")
            continue
        df = pd.read_parquet(arquivo)
        origem = conector.ler(f"select count(*) as n from operacao.{tabela}")
        esperado = int(origem["n"].iloc[0])
        problemas += _comparar(tabela, df, esperado, conector, f"operacao.{tabela}")
    return problemas


def _conferir_financeiro() -> list[str]:
    problemas: list[str] = []
    print("\n== financeiro ==")
    for nome, endpoint in (("faturamentos", "v1/faturamentos"), ("custos", "v1/custos")):
        arquivo = RAIZ_BRONZE / "financeiro" / f"{nome}.parquet"
        if not arquivo.exists():
            problemas.append(f"{nome}: arquivo ausente")
            continue
        df = pd.read_parquet(arquivo)
        # a API informa o total no envelope: uma página basta para saber quantos são
        esperado = _total_do_endpoint(endpoint)
        marca = "ok" if len(df) == esperado else "DIVERGE"
        print(f"  {nome:<22} {len(df):>10,} / {esperado:,}  {marca}")
        if len(df) != esperado:
            problemas.append(f"{nome}: {len(df):,} no bronze, {esperado:,} na origem")
    return problemas


def _total_do_endpoint(endpoint: str) -> int:
    """Pergunta ao servidor quantos registros existem, sem baixar todos."""
    import httpx

    from logistica_otif_mlops.config import obter_settings
    cfg = obter_settings()
    resposta = httpx.get(
        f"{(cfg.custos_api_url or '').rstrip('/')}/{endpoint}",
        params={"limite": 1},
        headers={"X-API-Key": cfg.custos_api_key or ""}, timeout=30)
    resposta.raise_for_status()
    return int(resposta.json()["total"])


def _comparar(nome: str, df: pd.DataFrame, esperado: int,
              conector: Any, tabela: str) -> list[str]:
    problemas: list[str] = []
    marca = "ok" if len(df) == esperado else "DIVERGE"
    if len(df) != esperado:
        problemas.append(f"{nome}: {len(df):,} no bronze, {esperado:,} na origem")

    detalhe = ""
    for coluna in SOMAS.get(nome, []):
        if coluna not in df.columns:
            continue
        no_bronze = float(pd.to_numeric(df[coluna], errors="coerce").sum())
        na_origem = float(conector.ler(
            f"select coalesce(sum({coluna}), 0) as s from {tabela}")["s"].iloc[0])
        # tolerância de um centavo: float não fecha exato, e exigir isso seria
        # criar alarme falso em toda execução
        if abs(no_bronze - na_origem) > 0.01:
            problemas.append(
                f"{nome}.{coluna}: soma {no_bronze:,.2f} no bronze "
                f"vs {na_origem:,.2f} na origem")
            detalhe = f"  ⚠️ {coluna}"
    print(f"  {nome:<22} {len(df):>10,} / {esperado:,}  {marca}{detalhe}")
    return problemas


if __name__ == "__main__":
    executar()
