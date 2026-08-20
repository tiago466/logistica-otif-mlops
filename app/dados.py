"""Acesso da apresentação aos extratos, com cache.

A apresentação **não** lê as camadas Bronze e Silver. Ela lê os extratos gerados
por `relatorios.extratos`, que são pequenos e versionados. Isso é o que permite
publicar o app sem publicar 31 milhões de linhas, e o que faz cada tela abrir
instantaneamente em vez de reprocessar Parquet a cada clique.

Se um extrato faltar, a mensagem diz qual comando gera. Um app que quebra com
`FileNotFoundError` cru obriga quem o abriu a ler o código para descobrir o que
fazer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

DADOS = Path(__file__).resolve().parents[1] / "reports" / "dados"
COMANDO = "uv run python -m logistica_otif_mlops.relatorios.extratos"


def _exigir(nome: str) -> Path:
    caminho = DADOS / nome
    if not caminho.exists():
        st.error(f"Extrato `{nome}` não encontrado. Gere os extratos com:\n\n`{COMANDO}`")
        st.stop()
    return caminho


@st.cache_data(show_spinner=False)
def apuracao() -> dict[str, Any]:
    """Todos os números apurados das camadas, lidos uma vez."""
    return json.loads(_exigir("apuracao.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def catalogo() -> dict[str, Any]:
    """Os achados e os capítulos, na mesma fonte que alimenta os relatórios."""
    return json.loads(_exigir("catalogo.json").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def enderecos_duplicados() -> pd.DataFrame:
    return pd.read_csv(_exigir("enderecos_duplicados.csv"), dtype={"cep": str})


@st.cache_data(show_spinner=False)
def texto_antes_depois() -> pd.DataFrame:
    return pd.read_csv(_exigir("texto_antes_depois.csv"))


@st.cache_data(show_spinner=False)
def ausencias() -> pd.DataFrame:
    return pd.read_csv(_exigir("ausencias.csv"))


def ajustes() -> pd.DataFrame:
    """As células alteradas por coluna, já ordenadas."""
    return pd.DataFrame(apuracao()["ajustes"]["detalhe"])


def inventario() -> pd.DataFrame:
    return pd.DataFrame(apuracao()["inventario"])
