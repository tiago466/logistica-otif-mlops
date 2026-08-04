"""Adaptador de Postgres: a fonte operacional da TransBrasil.

Implementa o contrato `Conector` lendo SQL e devolvendo DataFrame. O consumidor
(pipeline, notebook) não sabe se por trás há um Postgres local, um Neon ou um
túnel: sabe que existe um objeto com `.ler(consulta)`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import text

from logistica_otif_mlops.db import criar_engine


class PostgresConector:
    """Lê do banco relacional configurado em `DATABASE_URL`."""

    def __init__(self, url: str | None = None) -> None:
        self._engine = criar_engine(url=url)

    @classmethod
    def a_partir_do_ambiente(cls) -> PostgresConector:
        """Fábrica usada pelo registro: toda a configuração vem do ambiente."""
        return cls()

    def ler(self, consulta: str | None = None, **kwargs: Any) -> pd.DataFrame:
        """Executa a consulta e devolve o resultado como DataFrame.

        Args:
            consulta: SQL a executar. Parâmetros vão em `params`, nomeados
                (`:cliente`), nunca concatenados na string.
            **kwargs: `params` (dict) é repassado ao driver.
        """
        if not consulta:
            raise ValueError("O conector de Postgres precisa de uma consulta SQL")
        params = kwargs.pop("params", None)
        with self._engine.connect() as conexao:
            resultado = pd.read_sql_query(text(consulta), conexao, params=params, **kwargs)
        return pd.DataFrame(resultado)
