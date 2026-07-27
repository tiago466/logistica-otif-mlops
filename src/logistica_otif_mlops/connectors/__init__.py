"""Camada de conectores de dados (padrão *ports & adapters* / arquitetura hexagonal).

A ideia (batizada de "sockets" pelo Tiago): toda fonte de dados — banco,
arquivo (csv/xlsx/xml), API de terceiro — entra por um **conector nomeado**,
configurado por variável de ambiente. Quem consome (notebook, pipeline) pede o
dado pelo NOME lógico e recebe sempre um `pandas.DataFrame`, sem saber (nem se
importar com) qual é a fonte por trás.

Ganho: o projeto fica 100% portável. Quem clona só preenche o `.env` e roda —
nenhum `D:\\...\\arquivo.csv` nem senha espalhada pelo código.

Uso pretendido::

    from logistica_otif_mlops.connectors import obter

    df = obter("logistica_db").ler("SELECT * FROM pedidos")

Os conectores concretos nascem sob demanda (ver `registry.py`); esta camada
começa só com o CONTRATO comum (`base.py`) e o REGISTRO (`registry.py`).
"""

from logistica_otif_mlops.connectors.base import Conector
from logistica_otif_mlops.connectors.registry import obter

__all__ = ["Conector", "obter"]
