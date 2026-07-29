"""Fumaça da camada de banco (sem conexão real: CI não tem Postgres)."""

from types import SimpleNamespace

import pytest

from logistica_otif_mlops.db import Base, criar_engine, criar_fabrica_de_sessoes


def test_base_usa_convencao_de_nomes() -> None:
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"


def test_criar_engine_sem_url_da_erro_claro(monkeypatch: pytest.MonkeyPatch) -> None:
    # isola do .env local: settings sem DATABASE_URL
    monkeypatch.setattr(
        "logistica_otif_mlops.db.obter_settings",
        lambda: SimpleNamespace(database_url=None),
    )
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        criar_engine(url=None)


def test_criar_engine_com_url_nao_conecta_ainda() -> None:
    # create_engine é preguiçoso: só conecta no primeiro uso. Objeto deve nascer.
    engine = criar_engine(url="postgresql+psycopg://x:y@localhost:9/nada")
    assert engine.url.database == "nada"
    fabrica = criar_fabrica_de_sessoes(engine)
    assert fabrica is not None
