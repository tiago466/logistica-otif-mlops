"""O contrato comum de todo conector (a "porta", no padrão ports & adapters).

Todo conector concreto — Postgres, CSV, XLSX, XML, API REST — implementa esta
mesma interface. Assim o código que consome dados depende do CONTRATO (estável),
não da fonte (que varia de cliente para cliente). Trocar a origem dos dados vira
trocar o adaptador, sem tocar em pipeline nem notebook.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class Conector(Protocol):
    """Interface que todo conector de dados deve satisfazer.

    Um `Protocol` (tipagem estrutural): qualquer classe que exponha um método
    `ler(...) -> pd.DataFrame` já "é" um Conector, sem precisar herdar desta
    classe. É o encaixe do "socket".
    """

    def ler(self, consulta: str | None = None, **kwargs: Any) -> pd.DataFrame:
        """Lê dados da fonte e devolve um DataFrame.

        Args:
            consulta: para fontes SQL, a query; para arquivos/API, pode ser o
                nome do recurso/endpoint (ou ``None`` para o padrão da fonte).
            **kwargs: parâmetros específicos do adaptador (ex.: ``sep`` de CSV,
                filtros de API).

        Returns:
            Um ``pandas.DataFrame`` com os dados lidos.
        """
        ...
