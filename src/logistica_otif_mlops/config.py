"""Configuração central (padrão 12-factor: config vem do ambiente, não do código).

Toda credencial, URL de banco, chave de API e caminho de dados entra por
**variável de ambiente** — nunca fica escrita no código nem em notebook. Em
desenvolvimento, as variáveis são lidas de um arquivo `.env` (fora do git); em
homologação/produção, vêm do ambiente do provedor (Render/Neon).

O `.env.example` versionado documenta QUAIS variáveis existem, sem os valores.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Ambiente = Literal["dev", "hmlg", "prod"]


class Settings(BaseSettings):
    """Configurações do projeto, carregadas do ambiente / arquivo `.env`.

    Novos conectores acrescentam aqui os seus campos (ex.: `logistica_db_url`,
    `financeiro_api_key`), sempre com um correspondente no `.env.example`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis de ambiente não declaradas aqui
    )

    ambiente: Ambiente = "dev"

    # Banco relacional da TransBrasil (schemas operacao + custos).
    # dev: Postgres do docker-compose; hmlg: Neon.
    database_url: str | None = None

    # Destino da publicação em nuvem (Neon). Só o script de publicação usa;
    # o pipeline continua falando com `database_url`, seja ela qual for.
    neon_database_url: str | None = None

    # --- Conectores (adicionados sob demanda; ver connectors/registry.py) ---
    # API de custos: do lado do SERVIDOR, a chave é o segredo que valida quem
    # chama; do lado do CLIENTE (conector), é a credencial que enviamos.
    custos_api_url: str | None = None
    custos_api_key: str | None = None
    # Origem dos dados servidos pela API (o "banco do sistema financeiro").
    # Em produção aponta para o Neon; em dev, para o Postgres local.
    custos_api_database_url: str | None = None


@lru_cache
def obter_settings() -> Settings:
    """Devolve as configurações (cacheadas — lidas do ambiente uma única vez)."""
    return Settings()


def url_libpq(url: str) -> str:
    """Converte a URL para o formato que o psycopg (libpq) entende.

    O SQLAlchemy usa `postgresql+psycopg://` para escolher o driver; a libpq
    (usada pelo psycopg direto, no COPY e na API) só entende `postgresql://`.
    A mesma variável de ambiente serve aos dois mundos passando por aqui.
    """
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def url_sqlalchemy(url: str) -> str:
    """Garante o driver explícito na URL que vai para o SQLAlchemy.

    Provedores de nuvem entregam a connection string no formato da libpq
    (`postgresql://...`). Sem o `+psycopg`, o SQLAlchemy assume o driver
    padrão (psycopg2, que não instalamos) e falha com um erro que não tem nada
    a ver com a causa. Normalizar aqui evita esse tropeço em toda troca de
    ambiente, e aceita a string colada do painel do provedor como ela vem.
    """
    if url.startswith("postgresql+"):
        return url
    return url.replace("postgresql://", "postgresql+psycopg://", 1)
