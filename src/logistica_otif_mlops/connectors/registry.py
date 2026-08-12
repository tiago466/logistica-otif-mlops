"""Registro de conectores: mapeia um NOME lógico → o conector concreto.

Este é "o lugar para configurar o socket". Um conector novo nasce em dois passos:

1. cria-se o adaptador (ex.: `postgres.py` com uma classe que implementa
   `Conector`, lendo a URL do banco de `config.Settings`);
2. registra-se aqui, associando um nome lógico à sua fábrica.

O consumidor então chama ``obter("nome")`` — e nunca sabe qual é a fonte.
Começamos com o registro VAZIO de propósito: cada conector entra quando a
necessidade real aparecer (o primeiro será o Postgres do relacional sintético),
evitando construir adaptadores que ainda não usamos.
"""

from __future__ import annotations

from collections.abc import Callable

from logistica_otif_mlops.connectors.api_rest import ApiRestConector
from logistica_otif_mlops.connectors.base import Conector
from logistica_otif_mlops.connectors.postgres import PostgresConector

# nome lógico -> fábrica que constrói o conector (lê sua config do ambiente).
# O consumidor pede "operacao_db" e recebe um objeto com `.ler()`: trocar o
# Postgres local pelo Neon é trocar a variável de ambiente, não o código. E
# "financeiro_api" atende ao MESMO contrato, embora do outro lado haja HTTP,
# chave de acesso e paginação — é esse o ponto da camada de conectores.
_REGISTRO: dict[str, Callable[[], Conector]] = {
    "operacao_db": PostgresConector.a_partir_do_ambiente,
    "financeiro_api": ApiRestConector.a_partir_do_ambiente,
}


def obter(nome: str) -> Conector:
    """Devolve o conector registrado sob ``nome``.

    Raises:
        KeyError: se o nome não estiver registrado — a mensagem lista os
            conectores disponíveis, para o erro ser autoexplicativo.
    """
    try:
        fabrica = _REGISTRO[nome]
    except KeyError:
        disponiveis = ", ".join(sorted(_REGISTRO)) or "(nenhum ainda)"
        raise KeyError(
            f"Conector '{nome}' não registrado. Disponíveis: {disponiveis}. "
            f"Registre-o em connectors/registry.py."
        ) from None
    return fabrica()


def nomes_registrados() -> list[str]:
    """Lista os nomes lógicos de conectores disponíveis."""
    return sorted(_REGISTRO)
