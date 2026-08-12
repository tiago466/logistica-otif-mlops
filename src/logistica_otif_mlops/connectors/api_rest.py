"""Adaptador de API REST: a fonte financeira.

Implementa o mesmo contrato `Conector` do Postgres — quem consome chama `.ler()`
e recebe um DataFrame, sem saber que do outro lado há HTTP, chave de acesso e
paginação. Trocar a origem vira trocar o adaptador.

O que este adaptador resolve, e que um `requests.get()` solto no notebook não
resolve:

* **paginação transparente**: a API entrega no máximo 1000 registros por
  chamada; aqui as páginas são percorridas até completar o `total` informado
  pelo servidor, e o consumidor recebe tudo de uma vez;
* **credencial fora do código**: a chave vem do ambiente, nunca do notebook;
* **falha explícita**: erro de HTTP vira exceção com contexto, em vez de um
  DataFrame vazio que passa despercebido e vira "não tinha dado no período".
"""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd

from logistica_otif_mlops.config import obter_settings

LIMITE_POR_PAGINA = 1000
TEMPO_LIMITE = 60.0
MAXIMO_PAGINAS = 10_000  # trava contra laço infinito se a API mentir o total

# JSON não tem tipo decimal. Para não perder precisão em dinheiro, a API manda
# valores como STRING — e quem consome precisa converter. Sem isso, `sum()`
# concatena texto em vez de somar, e o erro passa despercebido porque não
# levanta exceção: só produz um número absurdo lá na frente.
# A conversão é por nome de coluna, e não automática, de propósito: converter
# "tudo que parece número" estragaria CEP, CNPJ e código com zero à esquerda.
COLUNAS_NUMERICAS = ("valor", "aliquota", "m3", "peso", "quantidade", "total")


class ApiRestConector:
    """Lê endpoints da API financeira e devolve DataFrame."""

    def __init__(self, url_base: str | None = None, chave: str | None = None) -> None:
        cfg = obter_settings()
        self._url_base = (url_base or cfg.custos_api_url or "").rstrip("/")
        self._chave = chave or cfg.custos_api_key
        if not self._url_base:
            raise RuntimeError(
                "CUSTOS_API_URL não configurada (veja .env.example)")
        if not self._chave:
            raise RuntimeError(
                "CUSTOS_API_KEY não configurada — a API recusa chamada sem chave")

    @classmethod
    def a_partir_do_ambiente(cls) -> ApiRestConector:
        return cls()

    def ler(self, consulta: str | None = None, **kwargs: Any) -> pd.DataFrame:
        """Lê um endpoint inteiro, percorrendo as páginas.

        Args:
            consulta: caminho do recurso (ex.: ``v1/faturamentos``).
            **kwargs: filtros repassados como query string (ex.:
                ``competencia_de='2026-01'``).
        """
        if not consulta:
            raise ValueError("Informe o endpoint (ex.: 'v1/faturamentos')")
        endereco = f"{self._url_base}/{consulta.lstrip('/')}"
        filtros = {k: v for k, v in kwargs.items() if v is not None}

        with httpx.Client(timeout=TEMPO_LIMITE,
                          headers={"X-API-Key": self._chave or ""}) as cliente:
            primeira = self._buscar(cliente, endereco, filtros, deslocamento=0)
            # endpoints pequenos (parâmetros, tarifas) devolvem lista pura
            if isinstance(primeira, list):
                return self._tipar(pd.DataFrame(primeira))

            itens = list(primeira["itens"])
            total = int(primeira["total"])
            for _ in range(MAXIMO_PAGINAS):
                if len(itens) >= total:
                    break
                pagina = self._buscar(cliente, endereco, filtros, deslocamento=len(itens))
                novos = pagina["itens"] if isinstance(pagina, dict) else []
                if not novos:  # servidor parou de entregar: não insista
                    break
                itens.extend(novos)
        return self._tipar(pd.DataFrame(itens))

    @staticmethod
    def _tipar(df: pd.DataFrame) -> pd.DataFrame:
        """Converte para número as colunas monetárias que vieram como texto."""
        for coluna in df.columns:
            if any(marca in coluna.lower() for marca in COLUNAS_NUMERICAS):
                df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        for coluna in (c for c in df.columns if c.startswith("dt_")):
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce")
        return df

    def _buscar(self, cliente: httpx.Client, endereco: str,
                filtros: dict[str, Any], deslocamento: int) -> Any:
        parametros = {**filtros, "limite": LIMITE_POR_PAGINA, "deslocamento": deslocamento}
        resposta = cliente.get(endereco, params=parametros)
        if resposta.status_code == 401:
            raise PermissionError(
                f"A API recusou a chave ao chamar {endereco}. "
                "Confira CUSTOS_API_KEY no ambiente.")
        resposta.raise_for_status()
        return resposta.json()
