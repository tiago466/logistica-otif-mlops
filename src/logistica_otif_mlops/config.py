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

    # --- Conectores (adicionados sob demanda; ver connectors/registry.py) ---
    # Ex., quando nascer o conector do Postgres sintético:
    #   logistica_db_url: str | None = None


@lru_cache
def obter_settings() -> Settings:
    """Devolve as configurações (cacheadas — lidas do ambiente uma única vez)."""
    return Settings()
