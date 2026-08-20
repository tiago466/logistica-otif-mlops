"""Camada SILVER: o Bronze tratado, com o mesmo grão e a origem preservada.

O que o Silver é: cada tabela do Bronze limpa e conformada, **mantendo a
granularidade original**. Uma tabela entra, a mesma tabela sai, tratada. `pedido`
continua sendo uma linha por pedido; `pedido_fase`, uma linha por passagem.

O que o Silver **não** é: o lugar de montar relatório. Achar as fases em colunas,
calcular durações e aplicar a régua de prazo são transformações de negócio, e
pertencem ao Gold. Se o tratamento já entregasse o relatório pronto, três coisas
se perderiam: o grão (e com ele as features do modelo), o reuso (todo relatório
novo voltaria ao Bronze) e a rastreabilidade (não se saberia se um número torto
veio da limpeza ou da regra).

**O que é tratado aqui** vem das ações registradas na EDA de qualidade:

  * texto com caixa e espaçamento inconsistentes (cidade, local, logradouro,
    recebedor, nomes de organização);
  * documento e CEP em formatos variados;
  * chave normalizada de endereço, para agrupar o mesmo lugar sem alterar cadastro.

**O que NÃO é tratado, de propósito:** valor unitário ausente e recebedor ausente
na transferência para base. Os dois são achados que dependem de decisão do
cliente, e preenchê-los aqui inventaria dado que ninguém coletou, além de apagar
do relatório um problema que precisa ser visto.

Rodar: uv run python -m logistica_otif_mlops.pipelines.silver
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from logistica_otif_mlops import transformacoes as tr

BRONZE = Path("data/bronze/operacao")
SILVER = Path("data/silver/operacao")


def executar() -> None:
    inicio = datetime.now(UTC)
    SILVER.mkdir(parents=True, exist_ok=True)
    tratamentos: list[dict[str, Any]] = []

    arquivos = sorted(BRONZE.glob("*.parquet"))
    if not arquivos:
        raise SystemExit("Bronze vazio: rode a ingestão antes "
                         "(uv run python -m logistica_otif_mlops.pipelines.bronze)")

    print("== silver · operação ==")
    for arquivo in arquivos:
        nome = arquivo.stem
        df = pd.read_parquet(arquivo)
        antes = df.copy(deep=True)

        regra = REGRAS.get(nome)
        if regra:
            df = regra(df)
        df["_processado_em"] = datetime.now(UTC)

        mudancas = _contar_mudancas(antes, df)
        destino = SILVER / f"{nome}.parquet"
        df.to_parquet(destino, engine="pyarrow", compression="snappy", index=False)

        marca = f"{sum(mudancas.values()):>10,} células ajustadas" if mudancas else "cópia fiel"
        print(f"  {nome:<22} {len(df):>10,} linhas   {marca}")
        tratamentos.append({
            "tabela": nome, "linhas": len(df),
            "colunas_ajustadas": mudancas,
            "total_ajustes": int(sum(mudancas.values())),
        })

    _gravar_manifesto(tratamentos, inicio)
    ajustes = sum(item["total_ajustes"] for item in tratamentos)
    segundos = (datetime.now(UTC) - inicio).total_seconds()
    print(f"\nSILVER OK: {len(tratamentos)} tabelas · {ajustes:,} ajustes · {segundos:.0f}s")


# --------------------------------------------------------------------------
# As regras, uma função por tabela que precisa de tratamento.
# Tabela sem regra é copiada como veio: no Bronze ela já estava limpa, e
# transformar o que não precisa é criar diferença sem motivo.
# --------------------------------------------------------------------------
def _caixa_alta(valor: object) -> object:
    """Código, sigla e UF vivem em caixa alta: são identificadores, não texto."""
    return valor.upper().strip() if isinstance(valor, str) else valor


def _tratar_endereco(df: pd.DataFrame) -> pd.DataFrame:
    """Endereço concentra quase toda a sujeira de digitação da base."""
    df = df.copy()
    df["cidade"] = df["cidade"].map(tr.capitalizar_nome, na_action="ignore")
    df["nome_local"] = df["nome_local"].map(tr.capitalizar_nome, na_action="ignore")
    df["bairro"] = df["bairro"].map(tr.capitalizar_nome, na_action="ignore")
    df["logradouro"] = df["logradouro"].map(tr.normalizar_logradouro, na_action="ignore")
    df["documento"] = df["documento"].map(tr.normalizar_documento, na_action="ignore")
    df["cep"] = df["cep"].map(tr.normalizar_cep, na_action="ignore")
    df["uf"] = df["uf"].map(_caixa_alta, na_action="ignore")

    # a capitalização acerta caixa e espaço, mas não devolve acento não digitado:
    # "Sao Paulo" e "São Paulo" sairiam daqui como duas cidades. A eleição da
    # grafia canônica junta as duas na forma que a própria base já usa.
    for coluna in ("cidade", "bairro", "nome_local"):
        de_para = tr.canonizar_variantes(df[coluna])
        if de_para:
            df[coluna] = df[coluna].replace(de_para)

    # chave de agrupamento: permite reunir o mesmo endereço cadastrado em
    # grafias diferentes SEM alterar nem excluir cadastro (a fusão é decisão
    # do cliente, e apagar registro quebraria o histórico dos pedidos)
    df["chave_endereco"] = (df["logradouro"].map(tr.chave_comparacao, na_action="ignore") + "|"
                            + df["cidade"].map(tr.chave_comparacao, na_action="ignore") + "|"
                            + df["uf"].fillna(""))
    return df


def _tratar_entrega(df: pd.DataFrame) -> pd.DataFrame:
    """O nome de quem assinou o canhoto, digitado no aplicativo do motorista.

    Ausência **não** é preenchida: o vazio na transferência para base é um achado
    de processo que precisa chegar ao relatório, não ser escondido pelo pipeline.
    """
    df = df.copy()
    df["recebedor"] = df["recebedor"].map(tr.capitalizar_nome, na_action="ignore")
    return df


def _tratar_organizacao(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["razao_social"] = df["razao_social"].map(tr.normalizar_espacos, na_action="ignore")
    df["nome_fantasia"] = df["nome_fantasia"].map(tr.normalizar_espacos, na_action="ignore")
    df["cnpj"] = df["cnpj"].map(tr.normalizar_documento, na_action="ignore")
    df["sigla"] = df["sigla"].map(_caixa_alta, na_action="ignore")
    return df


def _tratar_item(df: pd.DataFrame) -> pd.DataFrame:
    """Descrição de item vem em caixa alta do cadastro; valor ausente fica ausente."""
    df = df.copy()
    df["descricao"] = df["descricao"].map(tr.normalizar_espacos, na_action="ignore")
    df["codigo"] = df["codigo"].map(_caixa_alta, na_action="ignore")
    return df


def _tratar_transportador(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["nome"] = df["nome"].map(tr.normalizar_espacos, na_action="ignore")
    df["cnpj"] = df["cnpj"].map(tr.normalizar_documento, na_action="ignore")
    return df


def _tratar_veiculo(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["placa"] = df["placa"].map(
        lambda v: v.upper().replace("-", "").strip() if isinstance(v, str) else v,
        na_action="ignore")
    return df


def _tratar_ocorrencia(df: pd.DataFrame) -> pd.DataFrame:
    """Observação é texto livre: o ruído de digitação vira ausência.

    Categoria de ocorrência não sai daqui, sai de `tipo_ocorrencia`. Texto livre
    com "-", "N/A" ou "sem informacao" não informa nada e engana quem agrupar.
    """
    df = df.copy()
    sem_conteudo = {"-", "...", "??", "n/a", "na", "sem informacao",
                    "sem informação", "(verificar)", "verificar"}
    df["observacao"] = df["observacao"].map(
        lambda v: None if (limpo := tr.normalizar_espacos(v)) is None
        or limpo.lower() in sem_conteudo else limpo,
        na_action="ignore")
    return df


REGRAS: dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    "endereco": _tratar_endereco,
    "entrega": _tratar_entrega,
    "organizacao": _tratar_organizacao,
    "item": _tratar_item,
    "transportador": _tratar_transportador,
    "veiculo": _tratar_veiculo,
    "ocorrencia": _tratar_ocorrencia,
}


def _contar_mudancas(antes: pd.DataFrame, depois: pd.DataFrame) -> dict[str, int]:
    """Quantas células cada coluna teve alteradas.

    Este número é a evidência do relatório: sem ele, "normalizamos o cadastro" é
    afirmação sem tamanho. Também serve de alarme, porque tratamento que mexe em
    coluna inesperada aparece aqui antes de virar problema.
    """
    mudancas: dict[str, int] = {}
    for coluna in antes.columns:
        if coluna not in depois.columns or coluna.startswith("_"):
            continue
        a, b = antes[coluna], depois[coluna]
        # nulo == nulo conta como igual; comparação direta trataria como diferente
        diferentes = int(((a != b) & ~(a.isna() & b.isna())).sum())
        if diferentes:
            mudancas[coluna] = diferentes
    return mudancas


def _gravar_manifesto(tratamentos: list[dict[str, Any]], inicio: datetime) -> None:
    caminho = SILVER.parent / "_manifesto.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conteudo = {
        "processado_em": datetime.now(UTC).isoformat(),
        "duracao_segundos": round((datetime.now(UTC) - inicio).total_seconds(), 1),
        "tabelas": tratamentos,
    }
    caminho.write_text(json.dumps(conteudo, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    executar()
