"""Apura, a partir das camadas, todo número que os relatórios exibem.

A regra desta camada é uma só: **nenhum número do relatório é digitado**. Todos
saem daqui, lidos do Bronze, do Silver e dos manifestos, no momento da geração.

O motivo é prático. Um relatório com número escrito à mão envelhece no dia
seguinte, e ninguém percebe: o texto continua parecendo correto enquanto o dado
já mudou. Como estes dois documentos serão regerados a cada avanço do projeto,
qualquer valor fixo no texto viraria mentira sem aviso.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from logistica_otif_mlops import transformacoes as tr

# as 18 tabelas de uma camada, carregadas de uma vez: é assim que as duas viajam
# entre as funções de apuração, porque toda comparação precisa das duas lado a lado
Tabelas = dict[str, pd.DataFrame]

RAIZ = Path(__file__).resolve().parents[3]
BRONZE = RAIZ / "data" / "bronze" / "operacao"
SILVER = RAIZ / "data" / "silver" / "operacao"


def apurar() -> dict[str, Any]:
    """Lê as duas camadas e devolve tudo que os templates precisam."""
    if not BRONZE.exists() or not SILVER.exists():
        raise SystemExit(
            "Bronze ou Silver ausente. Rode a ingestão e o tratamento antes:\n"
            "  uv run python -m logistica_otif_mlops.pipelines.bronze\n"
            "  uv run python -m logistica_otif_mlops.pipelines.silver"
        )

    manifesto_bronze = json.loads((BRONZE.parent / "_manifesto.json").read_text("utf-8"))
    manifesto_silver = json.loads((SILVER.parent / "_manifesto.json").read_text("utf-8"))

    bronze = {p.stem: pd.read_parquet(p) for p in sorted(BRONZE.glob("*.parquet"))}
    silver = {p.stem: pd.read_parquet(p) for p in sorted(SILVER.glob("*.parquet"))}

    return {
        "carga": _carga(manifesto_bronze, manifesto_silver, bronze, silver),
        "ajustes": _ajustes(manifesto_silver),
        "grao": _grao(bronze, silver),
        "ausencias": _ausencias(bronze, silver),
        "texto": _texto(bronze, silver),
        "duplicidade": _duplicidade(silver),
        "sem_efeito": _sem_efeito(bronze, silver),
        "inventario": _inventario(bronze),
    }


def _carga(mb: dict[str, Any], ms: dict[str, Any],
           bronze: Tabelas, silver: Tabelas) -> dict[str, Any]:
    linhas = sum(len(df) for df in bronze.values())
    colunas = sum(len([c for c in df.columns if not c.startswith("_")])
                  for df in bronze.values())
    # o denominador honesto para "quanto do dado foi alterado" é a célula, não a
    # linha: o tratamento age em campo, e dividir por linha inflaria a proporção
    # em tantas vezes quantas forem as colunas da tabela
    celulas = sum(len(df) * len([c for c in df.columns if not c.startswith("_")])
                  for df in bronze.values())
    return {
        "celulas": celulas,
        "ingerido_em": mb["carga_concluida_em"][:10],
        "processado_em": ms["processado_em"][:10],
        "duracao_silver": ms["duracao_segundos"],
        "tabelas": len(bronze),
        "linhas": linhas,
        "colunas": colunas,
        "linhas_silver": sum(len(df) for df in silver.values()),
    }


def _ajustes(ms: dict[str, Any]) -> dict[str, Any]:
    detalhe = [
        {"tabela": item["tabela"], "coluna": coluna, "celulas": quantidade}
        for item in ms["tabelas"]
        for coluna, quantidade in item["colunas_ajustadas"].items()
    ]
    detalhe.sort(key=lambda linha: linha["celulas"], reverse=True)
    total = sum(linha["celulas"] for linha in detalhe)
    return {
        "detalhe": detalhe,
        "total": total,
        "colunas": len(detalhe),
        "tabelas": len({linha["tabela"] for linha in detalhe}),
    }


def _grao(bronze: Tabelas, silver: Tabelas) -> dict[str, Any]:
    preservadas = sum(1 for nome in bronze if len(bronze[nome]) == len(silver[nome]))
    perdidas = sum(1 for nome in bronze
                   if set(bronze[nome].columns) - set(silver[nome].columns))
    return {"tabelas": len(bronze), "preservadas": preservadas, "perdidas": perdidas,
            "ok": preservadas == len(bronze) and perdidas == 0}


def _ausencias(bronze: Tabelas, silver: Tabelas) -> dict[str, Any]:
    """A verificação central: o que estava ausente continua ausente?"""
    divergentes = []
    for nome, b in bronze.items():
        s = silver[nome]
        for coluna in b.columns:
            if coluna.startswith("_") or coluna not in s.columns:
                continue
            nb, ns = int(b[coluna].isna().sum()), int(s[coluna].isna().sum())
            if nb != ns:
                divergentes.append({"tabela": nome, "coluna": coluna,
                                    "bronze": nb, "silver": ns, "diferenca": ns - nb})

    # ausência disfarçada de texto: o erro que o pipeline já cometeu uma vez
    disfarces = {"nan", "none", "nat", "null", "<na>", "n/a", "na", "-", ""}
    disfarcados = 0
    for df in silver.values():
        for coluna in df.columns:
            if df[coluna].dtype not in ("str", "object"):
                continue
            serie = df[coluna].dropna().astype(str).str.strip().str.lower()
            disfarcados += int(serie.isin(disfarces).sum())

    transf = silver["entrega"]["tipo_perna"] == "TRANSFERENCIA_BASE"
    return {
        "divergentes": divergentes,
        "disfarcados": disfarcados,
        "recebedor_bronze": int(
            bronze["entrega"].loc[
                bronze["entrega"]["tipo_perna"] == "TRANSFERENCIA_BASE", "recebedor"
            ].isna().sum()),
        "recebedor_silver": int(silver["entrega"].loc[transf, "recebedor"].isna().sum()),
        "valor_bronze": int(bronze["item"]["valor_unitario"].isna().sum()),
        "valor_silver": int(silver["item"]["valor_unitario"].isna().sum()),
    }


def _variantes(serie: pd.Series) -> int:
    mapa: dict[str, set[str]] = {}
    for valor in serie.dropna().astype(str).unique():
        mapa.setdefault(tr.chave_comparacao(valor), set()).add(valor)
    return sum(1 for grafias in mapa.values() if len(grafias) > 1)


def _texto(bronze: Tabelas, silver: Tabelas) -> dict[str, Any]:
    abreviado = r"^(r\.|av\.|rod\.|tv\.|est\.|al\.|pç\.|pc\.)"
    resultado: dict[str, Any] = {}
    for campo in ("cidade", "nome_local"):
        resultado[campo] = {
            "bronze": _variantes(bronze["endereco"][campo]),
            "silver": _variantes(silver["endereco"][campo]),
        }
    for rotulo, camada in (("bronze", bronze), ("silver", silver)):
        serie = camada["endereco"]["logradouro"].dropna().astype(str)
        resultado.setdefault("logradouro", {})[rotulo] = int(
            serie.str.match(abreviado, case=False).sum())
        nomes = camada["entrega"]["recebedor"].dropna().astype(str)
        resultado.setdefault("recebedor", {})[rotulo] = int(nomes.nunique())
    resultado["sao_paulo"] = sorted(
        bronze["endereco"].loc[
            bronze["endereco"]["cidade"].map(tr.chave_comparacao)
            == tr.chave_comparacao("São Paulo"), "cidade"].unique())
    return resultado


def _duplicidade(silver: Tabelas) -> dict[str, Any]:
    frequencia = silver["endereco"]["chave_endereco"].value_counts()
    duplicados = frequencia[frequencia > 1]
    return {
        "grupos": int(len(duplicados)),
        "cadastros": int(duplicados.sum()),
        "eliminados_numa_fusao": int(duplicados.sum() - len(duplicados)),
        "total": int(len(silver["endereco"])),
    }


def _sem_efeito(bronze: Tabelas, silver: Tabelas) -> list[dict[str, Any]]:
    """Regras que rodaram e não encontraram o que corrigir. São defesa, não conserto."""
    from logistica_otif_mlops.pipelines.silver import REGRAS

    inertes = []
    for nome in REGRAS:
        b, s = bronze[nome], silver[nome]
        for coluna in b.columns:
            if coluna.startswith("_") or coluna not in s.columns:
                continue
            alterados = int(((b[coluna] != s[coluna])
                             & ~(b[coluna].isna() & s[coluna].isna())).sum())
            if alterados == 0 and _tratada(nome, coluna):
                inertes.append({"tabela": nome, "coluna": coluna, "linhas": len(b)})
    return inertes


def _tratada(tabela: str, coluna: str) -> bool:
    """Diz se a coluna passa por alguma regra do Silver (e não só existe na tabela)."""
    tratadas = {
        "endereco": {"cidade", "nome_local", "bairro", "logradouro", "documento",
                     "cep", "uf"},
        "entrega": {"recebedor"},
        "organizacao": {"razao_social", "nome_fantasia", "cnpj", "sigla"},
        "item": {"descricao", "codigo"},
        "transportador": {"nome", "cnpj"},
        "veiculo": {"placa"},
        "ocorrencia": {"observacao"},
    }
    return coluna in tratadas.get(tabela, set())


def _inventario(bronze: Tabelas) -> list[dict[str, Any]]:
    inventario: list[dict[str, Any]] = [
        {"tabela": nome, "linhas": len(df),
         "colunas": len([c for c in df.columns if not c.startswith("_")])}
        for nome, df in bronze.items()
    ]
    inventario.sort(key=lambda linha: int(linha["linhas"]), reverse=True)
    return inventario
