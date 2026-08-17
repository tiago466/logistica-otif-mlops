"""Diagnósticos de qualidade de dados, reutilizáveis em qualquer tabela.

São 18 tabelas para examinar. Escrever a mesma inspeção 18 vezes num notebook
produz erro de copiar e colar, resultado que não se compara entre tabelas e um
documento impossível de reler. Aqui cada diagnóstico é escrito uma vez, devolve
sempre o mesmo formato de saída e por isso pode ser aplicado em série.

O que estas funções fazem: descrevem. O que elas não fazem: corrigir. Tratamento
é trabalho do Silver, e misturar diagnóstico com correção é o caminho mais curto
para não saber mais qual era o dado original.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Colunas técnicas da ingestão. Não vieram da origem, então não entram em
# nenhum diagnóstico de qualidade: contá-las inflaria a completude.
COLUNAS_TECNICAS = ("_ingerido_em", "_origem")

SEVERIDADES = ("alta", "media", "baixa")


def perfil(df: pd.DataFrame, nome: str = "") -> pd.DataFrame:
    """Retrato de uma tabela: tipo, preenchimento e variedade de cada coluna.

    É o primeiro olhar sobre qualquer tabela. Responde de uma vez: o que está
    vazio, o que é constante (não serve para nada) e o que tem cardinalidade
    alta demais para ser categoria.
    """
    colunas = [c for c in df.columns if c not in COLUNAS_TECNICAS]
    linhas = []
    for coluna in colunas:
        serie = df[coluna]
        nulos = int(serie.isna().sum())
        distintos = int(serie.nunique(dropna=True))
        linhas.append({
            "tabela": nome,
            "coluna": coluna,
            "tipo": str(serie.dtype),
            "nulos": nulos,
            "pct_nulo": round(100 * nulos / len(df), 2) if len(df) else 0.0,
            "distintos": distintos,
            "pct_distinto": round(100 * distintos / len(df), 2) if len(df) else 0.0,
            "exemplo": _primeiro_valor(serie),
        })
    return pd.DataFrame(linhas)


def duplicatas(df: pd.DataFrame, chave: str | list[str]) -> pd.DataFrame:
    """Linhas que repetem a chave informada.

    Chave de negócio duplicada é defeito grave: quebra junção, duplica valor em
    soma e faz o mesmo pedido ser contado duas vezes num indicador.
    """
    chaves = [chave] if isinstance(chave, str) else chave
    repetidas = df[df.duplicated(subset=chaves, keep=False)]
    if repetidas.empty:
        return pd.DataFrame(columns=[*chaves, "ocorrencias"])
    return (repetidas.groupby(chaves, dropna=False)
            .size().reset_index(name="ocorrencias")
            .sort_values("ocorrencias", ascending=False))


def dominio(df: pd.DataFrame, coluna: str, esperados: set[str] | None = None) -> pd.DataFrame:
    """Distribuição de uma coluna categórica, sinalizando valores fora do esperado.

    Serve para duas perguntas: a coluna tem os valores que o negócio descreve, e
    existe categoria estranha (digitação livre, "N/A", vazio) escondida na cauda.
    """
    contagem = (df[coluna].value_counts(dropna=False)
                .rename_axis(coluna).reset_index(name="linhas"))
    contagem["pct"] = (100 * contagem["linhas"] / len(df)).round(2)
    if esperados is not None:
        contagem["esperado"] = contagem[coluna].isin(esperados)
    return contagem


def texto_inconsistente(df: pd.DataFrame, coluna: str) -> dict[str, int]:
    """Conta os vícios de digitação que impedem agrupar por um campo de texto.

    Cada um destes faz o mesmo valor virar duas categorias diferentes num
    `group by`, e o efeito só aparece quando o número do relatório vem menor do
    que deveria.
    """
    serie = df[coluna].dropna().astype(str)
    return {
        "total_nao_nulo": len(serie),
        "caixa_alta": int((serie == serie.str.upper()).sum()),
        "caixa_baixa": int((serie == serie.str.lower()).sum()),
        "espaco_nas_pontas": int((serie != serie.str.strip()).sum()),
        "espaco_duplo": int(serie.str.contains("  ", regex=False).sum()),
        "vazio_disfarcado": int((serie.str.strip() == "").sum()),
        "sem_acento": int((serie != serie.str.normalize("NFC")).sum()),
    }


def ordem_temporal(df: pd.DataFrame, antes: str, depois: str) -> dict[str, Any]:
    """Verifica se um evento nunca acontece antes do que o precede.

    Data de fim anterior à de início é o "número impossível" clássico: não é
    ruído estatístico, é falha de sistema, e vale reportar ao dono da origem.
    """
    valido = df[[antes, depois]].dropna()
    invertidos = valido[valido[depois] < valido[antes]]
    return {
        "comparacoes": len(valido),
        "invertidos": len(invertidos),
        "pct": round(100 * len(invertidos) / len(valido), 4) if len(valido) else 0.0,
        "exemplos": invertidos.head(5),
    }


def orfaos(filho: pd.DataFrame, coluna_fk: str,
           pai: pd.DataFrame, coluna_pk: str = "id") -> dict[str, Any]:
    """Linhas que apontam para um pai que não existe.

    Dentro de um banco com chave estrangeira isto deve dar zero. Entre sistemas
    diferentes (aqui, operação e financeiro, ligados por chave de negócio) o
    órfão é esperado, e a quantidade dele é o indicador de saúde da integração.
    """
    referencias = filho[coluna_fk].dropna()
    existentes = set(pai[coluna_pk])
    perdidas = referencias[~referencias.isin(existentes)]
    return {
        "referencias": len(referencias),
        "orfaos": len(perdidas),
        "pct": round(100 * len(perdidas) / len(referencias), 4) if len(referencias) else 0.0,
        "valores": perdidas.drop_duplicates().head(10).tolist(),
    }


class RegistroDeAchados:
    """Acumula os achados durante a análise para virar tabela no fim.

    Sem isto, montar o relatório significa reler todas as notas técnicas e
    esperar não esquecer nenhuma. Com isto, o relatório sai de um `DataFrame`.
    """

    def __init__(self) -> None:
        self._itens: list[dict[str, Any]] = []

    def anotar(self, tabela: str, coluna: str, achado: str, linhas: int,
               severidade: str, impacto: str, acao: str,
               total: int | None = None) -> None:
        if severidade not in SEVERIDADES:
            raise ValueError(f"severidade deve ser uma de {SEVERIDADES}")
        self._itens.append({
            "tabela": tabela,
            "coluna": coluna,
            "achado": achado,
            "linhas": linhas,
            "pct": round(100 * linhas / total, 2) if total else None,
            "severidade": severidade,
            "impacto": impacto,
            "acao": acao,
        })

    def tabela(self) -> pd.DataFrame:
        """Os achados ordenados por severidade, prontos para o relatório."""
        if not self._itens:
            return pd.DataFrame()
        df = pd.DataFrame(self._itens)
        ordem = pd.Categorical(df["severidade"], categories=SEVERIDADES, ordered=True)
        return df.assign(_ordem=ordem).sort_values(
            ["_ordem", "linhas"], ascending=[True, False]).drop(columns="_ordem")

    def resumo(self) -> pd.DataFrame:
        """Quantos achados por severidade: a primeira página do relatório."""
        if not self._itens:
            return pd.DataFrame()
        return (self.tabela().groupby("severidade", observed=True)
                .size().reindex(SEVERIDADES, fill_value=0)
                .rename("achados").reset_index())

    def __len__(self) -> int:
        return len(self._itens)


def _primeiro_valor(serie: pd.Series) -> Any:
    validos = serie.dropna()
    return validos.iloc[0] if len(validos) else None
