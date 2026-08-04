"""Ambiente do Alembic: liga as migrations aos models e à DATABASE_URL do .env."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import logistica_otif_mlops.models  # noqa: F401  # registra as tabelas na metadata
from logistica_otif_mlops.config import obter_settings, url_sqlalchemy
from logistica_otif_mlops.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate compara o banco com os models registrados nesta metadata.
target_metadata = Base.metadata


def _url() -> str:
    """URL do banco: sempre do ambiente (12-factor), nunca do alembic.ini."""
    url = obter_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL não configurada (copie .env.example para .env).")
    return url_sqlalchemy(url)  # aceita a string crua do provedor de nuvem


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (útil para revisão: alembic upgrade head --sql)."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,  # temos operacao e custos
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrations conectado ao banco."""
    connectable = create_engine(_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
