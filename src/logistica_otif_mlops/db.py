"""Camada de banco de dados: engine, sessão e a Base dos models.

O banco simula os sistemas da Trans Fictício BR em dois schemas Postgres:
`operacao` (WMS/TMS) e `custos` (financeiro, servido pela API). A URL vem
sempre do ambiente (12-factor), nunca do código.
"""

from __future__ import annotations

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from logistica_otif_mlops.config import obter_settings, url_sqlalchemy

# Nomes determinísticos para constraints/índices: migrations reprodutíveis
# e ALTERs futuros sem adivinhação (padrão da casa).
CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarativa de todos os models (operacao e custos)."""

    metadata = MetaData(naming_convention=CONVENCAO_NOMES)


def criar_engine(url: str | None = None) -> Engine:
    """Cria o engine a partir da URL dada ou da configuração (`DATABASE_URL`).

    Raises:
        RuntimeError: se nenhuma URL estiver configurada.
    """
    url = url or obter_settings().database_url
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Copie o .env.example para .env "
            "e suba o Postgres local (docker compose up -d)."
        )
    # aceita a string como o provedor de nuvem entrega (sem o driver explícito)
    return create_engine(url_sqlalchemy(url), pool_pre_ping=True)


def criar_fabrica_de_sessoes(engine: Engine) -> sessionmaker[Session]:
    """Fábrica de sessões para uso em pipelines e seeds."""
    return sessionmaker(bind=engine, expire_on_commit=False)
