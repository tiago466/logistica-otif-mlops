"""Camada BRONZE: cópia fiel das fontes, sem uma única transformação.

O que o Bronze é: o retrato do dado como ele existe na origem, no momento em que
foi lido. Nada de renomear coluna, corrigir acento, converter tipo ou remover
duplicata — tudo isso é trabalho do Silver. Se o dado vem torto, ele chega torto
aqui, **de propósito**: é olhando para o torto que a EDA de qualidade descobre o
que precisa ser tratado, e é comparando com o Bronze que se audita qualquer
número do relatório final.

Três princípios que valem para qualquer projeto, não só este:

1. **A origem é intocável.** Só leitura, sempre. Não é apenas boa educação: em
   geral não se tem (nem se deve pedir) permissão de escrita, e se o cliente
   perder dado na semana em que você estava conectado, é o acesso somente
   leitura que prova que não foi você.

2. **Minimização.** Copia-se apenas o que foi acordado — aqui, exatamente as
   tabelas que sustentam os dois relatórios aprovados. Dado que não se copiou é
   dado que não se pode vazar (LGPD, art. 6º: adequação e necessidade). Se uma
   coluna nova for necessária depois, acrescenta-se a tabela ao contrato abaixo.

3. **Rastreabilidade.** Cada arquivo carrega quando foi extraído e de onde. Sem
   isso, daqui a três meses ninguém sabe se um número veio da carga de março ou
   de julho.

Rodar:
    uv run python -m logistica_otif_mlops.pipelines.bronze              # tudo
    uv run python -m logistica_otif_mlops.pipelines.bronze --dominio operacao
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from logistica_otif_mlops.connectors.registry import obter

# --- O CONTRATO DE INGESTÃO --------------------------------------------------
# Esta lista não é arbitrária: são as tabelas efetivamente usadas pelas queries
# dos relatórios aprovados pelos donos (`sql/relatorio_prazo_etapas.sql` e
# `sql/relatorio_mc_operacao.sql`). Mudou o relatório, muda o contrato.
TABELAS_OPERACAO = [
    # cadastro e réguas
    "organizacao", "endereco", "item", "transportador", "veiculo", "rota",
    "modalidade", "fase", "tipo_ocorrencia",
    # movimento
    "pedido", "pedido_item", "pedido_fase", "ordem_coleta", "minuta", "entrega",
    "ocorrencia", "retirada_base", "estoque_snapshot",
]

# O financeiro é sistema de terceiro: não há tabela, há endpoint.
ENDPOINTS_FINANCEIRO = [
    "v1/faturamentos", "v1/custos", "v1/parametros", "v1/tarifas-armazenagem",
]

RAIZ_BRONZE = Path("data/bronze")


def executar(dominio: str = "todos") -> None:
    inicio = datetime.now(UTC)
    manifesto: list[dict[str, Any]] = []
    if dominio in ("todos", "operacao"):
        manifesto.extend(_ingerir_operacao())
    if dominio in ("todos", "financeiro"):
        manifesto.extend(_ingerir_financeiro())
    _gravar_manifesto(manifesto, inicio)

    linhas = sum(item["linhas"] for item in manifesto)
    segundos = (datetime.now(UTC) - inicio).total_seconds()
    print(f"\nBRONZE OK: {len(manifesto)} conjuntos · {linhas:,} linhas · {segundos:.0f}s")


def _ingerir_operacao() -> list[dict[str, Any]]:
    """Lê o banco do sistema operacional, uma tabela por vez.

    `select *` é intencional: o Bronze copia a tabela como ela é. Escolher
    colunas aqui seria a primeira transformação, e transformação no Bronze é
    decisão que não se consegue mais revisitar.
    """
    conector = obter("operacao_db")
    print("== operação (banco relacional) ==")
    saida = []
    for tabela in TABELAS_OPERACAO:
        df = conector.ler(f"select * from operacao.{tabela}")
        saida.append(_gravar(df, "operacao", tabela, origem=f"operacao.{tabela}"))
    return saida


def _ingerir_financeiro() -> list[dict[str, Any]]:
    """Lê a API do sistema financeiro, um endpoint por vez.

    A paginação fica escondida no conector: aqui se pede o recurso inteiro, como
    se fosse uma tabela. É esse o ponto da camada de conectores — o pipeline não
    muda de forma porque a fonte é HTTP em vez de SQL.
    """
    conector = obter("financeiro_api")
    print("\n== financeiro (API do terceiro) ==")
    saida = []
    for endpoint in ENDPOINTS_FINANCEIRO:
        nome = endpoint.split("/")[-1].replace("-", "_")
        df = conector.ler(endpoint)
        saida.append(_gravar(df, "financeiro", nome, origem=endpoint))
    return saida


def _gravar(df: pd.DataFrame, dominio: str, nome: str, origem: str) -> dict[str, Any]:
    """Grava em Parquet e devolve a linha do manifesto.

    Parquet, e não CSV, por três razões: preserva o tipo (CSV transforma tudo em
    texto e joga no colo do próximo a adivinhação), é colunar (ler três colunas
    de uma tabela de cinquenta não custa as outras quarenta e sete) e comprime
    bem, o que importa quando a cópia mora na máquina do analista.
    """
    destino = RAIZ_BRONZE / dominio
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"{nome}.parquet"

    # Colunas técnicas de ingestão. O prefixo `_` marca que não vieram da
    # origem: sem essa distinção, um dia alguém vai analisar `_ingerido_em`
    # achando que é data de negócio.
    momento = datetime.now(UTC)
    df = df.copy()
    df["_ingerido_em"] = momento
    df["_origem"] = origem

    df.to_parquet(arquivo, engine="pyarrow", compression="snappy", index=False)
    tamanho_mb = arquivo.stat().st_size / 1024 / 1024
    print(f"  {nome:<22} {len(df):>10,} linhas  {tamanho_mb:>7.1f} MB")
    return {
        "dominio": dominio, "conjunto": nome, "origem": origem,
        "linhas": len(df), "colunas": len(df.columns) - 2,  # sem as técnicas
        "arquivo": str(arquivo), "megabytes": round(tamanho_mb, 2),
        "ingerido_em": momento.isoformat(),
    }


def _gravar_manifesto(manifesto: list[dict[str, Any]], inicio: datetime) -> None:
    """O manifesto responde 'de onde veio este número?' meses depois.

    Ele **mescla** com o que já existe em vez de sobrescrever: como os domínios
    podem ser carregados em execuções separadas (`--dominio operacao`, depois
    `--dominio financeiro`), gravar só o que acabou de rodar apagaria o registro
    da carga anterior — e o manifesto perderia justamente a rastreabilidade que
    justifica a existência dele.
    """
    RAIZ_BRONZE.mkdir(parents=True, exist_ok=True)
    caminho = RAIZ_BRONZE / "_manifesto.json"

    anteriores: list[dict[str, Any]] = []
    if caminho.exists():
        atualizados = {item["dominio"] for item in manifesto}
        anteriores = [item for item in json.loads(caminho.read_text(encoding="utf-8"))
                      .get("conjuntos", []) if item["dominio"] not in atualizados]

    conteudo = {
        "carga_iniciada_em": inicio.isoformat(),
        "carga_concluida_em": datetime.now(UTC).isoformat(),
        "conjuntos": sorted(anteriores + manifesto,
                            key=lambda item: (item["dominio"], item["conjunto"])),
    }
    caminho.write_text(json.dumps(conteudo, indent=2, ensure_ascii=False), encoding="utf-8")


def principal() -> None:
    parser = argparse.ArgumentParser(description="Carga da camada Bronze")
    parser.add_argument("--dominio", choices=["todos", "operacao", "financeiro"],
                        default="todos", help="qual fonte ingerir")
    args = parser.parse_args()
    executar(args.dominio)


if __name__ == "__main__":
    principal()
