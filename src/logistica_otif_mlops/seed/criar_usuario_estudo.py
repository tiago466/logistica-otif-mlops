"""Cria no Neon os usuários de acesso restrito, um por finalidade.

Princípio do menor privilégio, que é a base de qualquer acesso a dado real:
cada consumidor recebe o mínimo que basta para o seu trabalho, e nada além.

    estudo_sql     lê `operacao` e `custos`, e tem uma área própria (`rascunho`)
                   para criar views e tabelas de exercício sem tocar na origem
    api_financeiro lê SOMENTE `custos` — é o que a API serve, e ela não tem
                   por que enxergar a operação

Separar os dois importa: se a chave da API vazar, o estrago possível é ler o
financeiro publicado, não a base inteira. Um usuário por finalidade transforma
um incidente grande em um incidente pequeno.

As senhas são geradas aqui, gravadas no `.env` (que nunca vai ao git) e **nunca**
impressas na tela — segredo que passa por terminal, chat ou print está
comprometido. Para entregá-las a alguém, use um cofre (Bitwarden), não o WhatsApp.

Rodar: uv run python -m logistica_otif_mlops.seed.criar_usuario_estudo
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from logistica_otif_mlops.config import obter_settings, url_libpq

USUARIO_ESTUDO = "estudo_sql"
USUARIO_API = "api_financeiro"
SCHEMA_RASCUNHO = "rascunho"
ARQUIVO_ENV = Path(".env")
CHAVE_ENV_ESTUDO = "ESTUDO_DATABASE_URL"
CHAVE_ENV_API = "CUSTOS_API_DATABASE_URL"


def executar() -> None:
    cfg = obter_settings()
    if not cfg.neon_database_url:
        raise SystemExit("NEON_DATABASE_URL não configurada no .env")
    url = url_libpq(cfg.neon_database_url)

    with psycopg.connect(url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            senha_estudo = _criar_papel(cur, USUARIO_ESTUDO, conn.info.dbname)
            _liberar_leitura(cur, USUARIO_ESTUDO, ("operacao", "custos"))
            print("  leitura liberada em operacao e custos")

            # área de exercício: pode criar view e tabela à vontade, sem alcançar a origem.
            # O Postgres só deixa dar a autoria de um schema a um papel que o
            # criador consiga assumir, daí o grant do papel para o próprio owner.
            cur.execute(sql.SQL("grant {} to current_user").format(
                sql.Identifier(USUARIO_ESTUDO)))
            cur.execute(sql.SQL("create schema if not exists {} authorization {}").format(
                sql.Identifier(SCHEMA_RASCUNHO), sql.Identifier(USUARIO_ESTUDO)))
            print(f"  schema {SCHEMA_RASCUNHO} criado para os exercícios")

            # o schema public fica só de leitura: exercício vai no rascunho
            cur.execute(sql.SQL("revoke create on schema public from {}").format(
                sql.Identifier(USUARIO_ESTUDO)))

            senha_api = _criar_papel(cur, USUARIO_API, conn.info.dbname)
            _liberar_leitura(cur, USUARIO_API, ("custos",))
            print("  leitura liberada apenas em custos (a API não vê a operação)")

    _gravar_no_env(url, CHAVE_ENV_ESTUDO, USUARIO_ESTUDO, senha_estudo)
    _gravar_no_env(url, CHAVE_ENV_API, USUARIO_API, senha_api)
    print(f"\nconnection strings gravadas no .env ({CHAVE_ENV_ESTUDO}, {CHAVE_ENV_API})")
    print("Entregue a de estudo pelo cofre de senhas, nunca por chat.")


def _criar_papel(cur: psycopg.Cursor[Any], usuario: str, banco: str) -> str:
    """Cria (ou renova a senha de) um papel de login e devolve a senha gerada."""
    senha = secrets.token_urlsafe(18)
    cur.execute("select 1 from pg_roles where rolname = %s", (usuario,))
    existe = cur.fetchone() is not None
    comando = ("alter role {} with login password {}" if existe
               else "create role {} with login password {}")
    cur.execute(sql.SQL(comando).format(sql.Identifier(usuario), sql.Literal(senha)))
    cur.execute(sql.SQL("grant connect on database {} to {}").format(
        sql.Identifier(banco), sql.Identifier(usuario)))
    print(f"usuário {usuario}: {'senha trocada' if existe else 'criado'}")
    return senha


def _liberar_leitura(cur: psycopg.Cursor[Any], usuario: str,
                     esquemas: tuple[str, ...]) -> None:
    """Concede SELECT (e só isso) nos schemas indicados, inclusive no que vier depois."""
    for esquema in esquemas:
        cur.execute(sql.SQL("grant usage on schema {} to {}").format(
            sql.Identifier(esquema), sql.Identifier(usuario)))
        cur.execute(sql.SQL("grant select on all tables in schema {} to {}").format(
            sql.Identifier(esquema), sql.Identifier(usuario)))
        cur.execute(sql.SQL(
            "alter default privileges in schema {} grant select on tables to {}"
        ).format(sql.Identifier(esquema), sql.Identifier(usuario)))


def _gravar_no_env(url_owner: str, chave: str, usuario: str, senha: str) -> None:
    """Monta a URL do usuário restrito e guarda no .env (fora do git)."""
    sem_credencial = re.sub(r"^postgresql://[^@]+@", "", url_owner)
    nova = f"{chave}=postgresql://{usuario}:{senha}@{sem_credencial}"
    linhas = []
    if ARQUIVO_ENV.exists():
        linhas = [linha for linha in ARQUIVO_ENV.read_text(encoding="utf-8").splitlines()
                  if not linha.startswith(f"{chave}=")]
    linhas.append(nova)
    ARQUIVO_ENV.write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    executar()
