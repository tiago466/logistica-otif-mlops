"""Os dados da apresentação, carregados uma vez e servidos de memória.

A apresentação **não** lê Bronze nem Silver. Lê os extratos gerados por
`relatorios.extratos`, que somam cerca de 1 MB e são versionados. É o que permite
publicar a apresentação sem publicar 31 milhões de linhas, e o que faz cada tela
responder na hora em vez de reprocessar Parquet a cada clique.

Mesmo princípio da camada Gold, aplicado à apresentação: o consumidor recebe o
recorte de que precisa, não a base inteira.
"""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "reports" / "dados"
COMANDO = "uv run python -m logistica_otif_mlops.relatorios.extratos"

Linhas = list[dict[str, str]]


class ExtratoAusenteError(RuntimeError):
    """Erro com instrução de conserto: quem abrir o app precisa saber o que fazer."""

    def __init__(self, nome: str) -> None:
        super().__init__(f"Extrato '{nome}' não encontrado. Gere com: {COMANDO}")


def _caminho(nome: str) -> Path:
    caminho = DADOS / nome
    if not caminho.exists():
        raise ExtratoAusenteError(nome)
    return caminho


@lru_cache(maxsize=1)
def apuracao() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_caminho("apuracao.json").read_text("utf-8"))
    return dados


@lru_cache(maxsize=1)
def catalogo() -> dict[str, Any]:
    dados: dict[str, Any] = json.loads(_caminho("catalogo.json").read_text("utf-8"))
    return dados


@lru_cache(maxsize=4)
def _csv(nome: str) -> Linhas:
    """Lê um CSV como lista de dicionários.

    Sem pandas de propósito: a apresentação serve texto, e trazer o pandas para
    dentro do processo web custaria memória e tempo de partida sem devolver nada.
    """
    with _caminho(nome).open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def enderecos_duplicados() -> Linhas:
    return _csv("enderecos_duplicados.csv")


def texto_antes_depois() -> Linhas:
    return _csv("texto_antes_depois.csv")


def ausencias() -> Linhas:
    return _csv("ausencias.csv")


def achados() -> list[dict[str, Any]]:
    lista: list[dict[str, Any]] = catalogo()["achados"]
    return lista


def milhar(valor: float | str) -> str:
    """Separador de milhar no padrão brasileiro, tolerante a texto vindo de CSV."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f"{numero:,.0f}".replace(",", ".")


def classe_severidade(severidade: str) -> str:
    """'média' tem acento; nome de classe CSS não pode ter."""
    return {"alta": "alta", "média": "media", "baixa": "baixa"}.get(severidade, "baixa")
