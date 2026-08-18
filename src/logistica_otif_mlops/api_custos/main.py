"""API do sistema financeiro da Trans Fictício BR (o "sistema de terceiro" do cenário).

No mundo do case, o financeiro **não** é um banco que a gente consulta à vontade:
é um sistema de outro fornecedor, que expõe os dados por API com chave. Esta é a
implementação desse sistema, e existe para que o pipeline tenha uma segunda fonte
de verdade, com todas as chatices reais: autenticação, paginação, limite de
página, filtro por competência e resposta em JSON.

Regras de segurança que valem para qualquer API, não só esta:
  * a chave vive em variável de ambiente, nunca no código nem no repositório;
  * a comparação da chave usa `compare_digest` (tempo constante), para não vazar
    a chave por medição de tempo;
  * o banco é lido por um usuário **somente leitura**;
  * erro de autenticação não diz se a chave existe, só que não foi aceita;
  * a resposta nunca inclui dados de outro schema (a API serve só `custos`).

Onde este código roda: **num container próprio** (`infra/api_financeira/`), junto
com o banco do cliente, e não dentro do processo do projeto de dados. A fronteira
é física de propósito — ver o cabeçalho do `docker-compose.yml`.

    docker compose up -d api-financeira          # como o cliente a expõe
    uv run uvicorn logistica_otif_mlops.api_custos.main:app --reload   # só p/ depurar
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Annotated, Any

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from logistica_otif_mlops.config import obter_settings, url_libpq

LIMITE_MAXIMO = 1000
LIMITE_PADRAO = 100

app = FastAPI(
    title="Trans Fictício BR · API Financeira",
    version="1.0.0",
    description=(
        "Faturamento e custos operacionais da Trans Fictício BR. "
        "Autenticação por chave no cabeçalho `X-API-Key`."
    ),
)


def _url_do_banco() -> str:
    cfg = obter_settings()
    url = cfg.custos_api_database_url or cfg.database_url
    if not url:
        raise RuntimeError("Nenhuma URL de banco configurada para a API")
    return url_libpq(url)


@contextmanager
def conexao() -> Iterator[psycopg.Connection[Any]]:
    with psycopg.connect(_url_do_banco(), row_factory=dict_row) as conn:
        yield conn


def validar_chave(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Porteiro da API: sem chave válida, ninguém entra.

    `compare_digest` compara em tempo constante. Um `==` comum retorna mais
    rápido quando os primeiros caracteres diferem, e essa diferença de tempo é
    suficiente para descobrir a chave caractere a caractere.
    """
    esperada = obter_settings().custos_api_key
    if not esperada:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servico sem chave configurada")
    if not x_api_key or not secrets.compare_digest(x_api_key, esperada):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou invalida")


Autenticado = Annotated[None, Depends(validar_chave)]


class Faturamento(BaseModel):
    id: int
    cliente_sigla: str
    referencia_numero: str | None
    tipo_operacao: str
    competencia: str
    valor_com_icms: Decimal
    valor_icms: Decimal
    dt_faturamento: str


class Custo(BaseModel):
    id: int
    cliente_sigla: str
    referencia_numero: str | None
    categoria: str
    prestador_nome: str
    valor: Decimal
    dt_competencia: str


class Parametro(BaseModel):
    chave: str
    valor: Decimal
    descricao: str


class Tarifa(BaseModel):
    cliente_sigla: str
    valor_m3: Decimal
    aliquota_ad_valorem: Decimal
    valor_minimo_mensal: Decimal


class Pagina(BaseModel):
    """Envelope de paginação: quem consome precisa saber se acabou."""

    total: int = Field(description="Total de registros que atendem ao filtro")
    limite: int
    deslocamento: int
    itens: list[Any]


@app.get("/saude", tags=["servico"])
def saude() -> dict[str, str]:
    """Sonda de disponibilidade (não exige chave: é o que o Render consulta)."""
    return {"status": "ok"}


@app.get("/v1/faturamentos", response_model=Pagina, tags=["financeiro"])
def listar_faturamentos(
    _: Autenticado,
    cliente_sigla: str | None = None,
    tipo_operacao: str | None = None,
    competencia: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    competencia_de: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    competencia_ate: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    limite: int = Query(LIMITE_PADRAO, ge=1, le=LIMITE_MAXIMO),
    deslocamento: int = Query(0, ge=0),
) -> Pagina:
    """Receita por operação. Filtre por cliente, tipo e faixa de competência."""
    filtros, parametros = _filtros_comuns(
        cliente_sigla, competencia, competencia_de, competencia_ate, "competencia")
    if tipo_operacao:
        filtros.append("tipo_operacao = %(tipo_operacao)s")
        parametros["tipo_operacao"] = tipo_operacao
    onde = f"where {' and '.join(filtros)}" if filtros else ""
    return _paginar(
        f"""select id, cliente_sigla, referencia_numero, tipo_operacao, competencia,
                   valor_com_icms, valor_icms, dt_faturamento::text
            from custos.faturamento_operacao {onde} order by id""",
        f"select count(*) as total from custos.faturamento_operacao {onde}",
        parametros, limite, deslocamento)


@app.get("/v1/custos", response_model=Pagina, tags=["financeiro"])
def listar_custos(
    _: Autenticado,
    cliente_sigla: str | None = None,
    categoria: str | None = None,
    competencia: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    competencia_de: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    competencia_ate: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    limite: int = Query(LIMITE_PADRAO, ge=1, le=LIMITE_MAXIMO),
    deslocamento: int = Query(0, ge=0),
) -> Pagina:
    """Custo variável por operação, já com o nome da categoria resolvido."""
    filtros, parametros = _filtros_comuns(
        cliente_sigla, competencia, competencia_de, competencia_ate,
        "to_char(c.dt_competencia, 'YYYY-MM')", prefixo="c.")
    if categoria:
        filtros.append("cc.codigo = %(categoria)s")
        parametros["categoria"] = categoria
    onde = f"where {' and '.join(filtros)}" if filtros else ""
    juncao = ("from custos.custo_operacao c"
              " join custos.categoria_custo cc on cc.id = c.categoria_custo_id")
    return _paginar(
        f"""select c.id, c.cliente_sigla, c.referencia_numero, cc.codigo as categoria,
                   c.prestador_nome, c.valor, c.dt_competencia::text
            {juncao} {onde} order by c.id""",
        f"select count(*) as total {juncao} {onde}",
        parametros, limite, deslocamento)


@app.get("/v1/parametros", response_model=list[Parametro], tags=["financeiro"])
def listar_parametros(_: Autenticado) -> list[Parametro]:
    """Parâmetros de negócio (impostos, cubagem, aging, custo de servir)."""
    with conexao() as conn, conn.cursor() as cur:
        cur.execute("select chave, valor, descricao from custos.parametro_financeiro"
                    " order by chave")
        return [Parametro(**linha) for linha in cur.fetchall()]


@app.get("/v1/tarifas-armazenagem", response_model=list[Tarifa], tags=["financeiro"])
def listar_tarifas(_: Autenticado, cliente_sigla: str | None = None) -> list[Tarifa]:
    """Régua de cobrança de armazenagem por cliente."""
    onde = "where cliente_sigla = %(cliente_sigla)s" if cliente_sigla else ""
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(
            "select cliente_sigla, valor_m3, aliquota_ad_valorem, valor_minimo_mensal"
            f" from custos.tarifa_armazenagem {onde} order by cliente_sigla",
            {"cliente_sigla": cliente_sigla})
        return [Tarifa(**linha) for linha in cur.fetchall()]


def _filtros_comuns(cliente_sigla: str | None, competencia: str | None,
                    competencia_de: str | None, competencia_ate: str | None,
                    coluna_competencia: str, prefixo: str = "") -> tuple[list[str], dict[str, Any]]:
    """Monta o WHERE com parâmetros nomeados (jamais concatenando valor em SQL)."""
    filtros: list[str] = []
    parametros: dict[str, Any] = {}
    if cliente_sigla:
        filtros.append(f"{prefixo}cliente_sigla = %(cliente_sigla)s")
        parametros["cliente_sigla"] = cliente_sigla
    if competencia:
        filtros.append(f"{coluna_competencia} = %(competencia)s")
        parametros["competencia"] = competencia
    if competencia_de:
        filtros.append(f"{coluna_competencia} >= %(competencia_de)s")
        parametros["competencia_de"] = competencia_de
    if competencia_ate:
        filtros.append(f"{coluna_competencia} <= %(competencia_ate)s")
        parametros["competencia_ate"] = competencia_ate
    return filtros, parametros


def _paginar(consulta: str, consulta_total: str, parametros: dict[str, Any],
             limite: int, deslocamento: int) -> Pagina:
    with conexao() as conn, conn.cursor() as cur:
        cur.execute(consulta_total, parametros)
        linha = cur.fetchone()
        total = int(linha["total"]) if linha else 0
        cur.execute(f"{consulta} limit %(limite)s offset %(deslocamento)s",
                    {**parametros, "limite": limite, "deslocamento": deslocamento})
        itens = cur.fetchall()
    return Pagina(total=total, limite=limite, deslocamento=deslocamento, itens=itens)
