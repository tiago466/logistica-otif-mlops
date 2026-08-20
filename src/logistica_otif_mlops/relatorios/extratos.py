"""Exporta os extratos que a apresentação consome, para ela não depender do dado bruto.

O problema que isto resolve: a apresentação precisa de números e de algumas
tabelas navegáveis, mas as camadas Bronze e Silver somam 31 milhões de linhas em
Parquet e não vão ao repositório. Um app que lesse as camadas direto só rodaria
na máquina que tem os dados, e nunca poderia ser publicado.

A saída é pequena e versionável: um JSON com todos os números apurados e alguns
CSV com as tabelas que o usuário vai filtrar na tela. O app lê apenas isto.

É o mesmo princípio da camada Gold, aplicado à apresentação: o consumidor recebe
o recorte de que precisa, não a base inteira.

Rodar: uv run python -m logistica_otif_mlops.relatorios.extratos
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd

from logistica_otif_mlops import transformacoes as tr
from logistica_otif_mlops.relatorios.apuracao import BRONZE, RAIZ, SILVER, apurar
from logistica_otif_mlops.relatorios.catalogo import ACHADOS, CAPITULOS

DESTINO = RAIZ / "reports" / "dados"


def executar() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    print("== extratos da apresentação ==")

    apuracao = apurar()
    _gravar_json("apuracao.json", apuracao)
    _gravar_json("catalogo.json", {
        "achados": [asdict(a) for a in ACHADOS],
        "capitulos": [asdict(c) for c in CAPITULOS],
    })

    _enderecos_duplicados()
    _texto_antes_depois()
    _ausencias_por_coluna()

    total = sum(p.stat().st_size for p in DESTINO.glob("*"))
    print(f"\nOK: {DESTINO} · {total / 1024:.0f} KB no total")


def _gravar_json(nome: str, conteudo: object) -> None:
    caminho = DESTINO / nome
    caminho.write_text(json.dumps(conteudo, indent=2, ensure_ascii=False, default=str),
                       encoding="utf-8")
    print(f"  {nome:<28} {caminho.stat().st_size / 1024:>7.0f} KB")


def _gravar_csv(nome: str, df: pd.DataFrame) -> None:
    caminho = DESTINO / nome
    df.to_csv(caminho, index=False, encoding="utf-8")
    print(f"  {nome:<28} {caminho.stat().st_size / 1024:>7.0f} KB · {len(df):,} linhas")


def _enderecos_duplicados() -> None:
    """Os grupos de endereço que o cliente precisa conferir, um por linha.

    Este é o extrato mais acionável do conjunto: é a lista que o dono do cadastro
    abre para decidir o que funde e o que não funde.
    """
    endereco = pd.read_parquet(SILVER / "endereco.parquet")
    frequencia = endereco["chave_endereco"].value_counts()
    duplicados = frequencia[frequencia > 1]

    df = endereco[endereco["chave_endereco"].isin(duplicados.index)].copy()
    df["cadastros_no_grupo"] = df["chave_endereco"].map(duplicados)
    colunas = ["chave_endereco", "cadastros_no_grupo", "id", "nome_local",
               "logradouro", "bairro", "cidade", "uf", "cep"]
    _gravar_csv("enderecos_duplicados.csv",
                df[colunas].sort_values(["cadastros_no_grupo", "chave_endereco", "id"],
                                        ascending=[False, True, True]))


def _texto_antes_depois() -> None:
    """Cada valor de texto que mudou, com a forma antiga e a nova.

    Sem este extrato, "conformamos a grafia" é afirmação sem prova. Com ele, o
    cliente vê exatamente qual grafia virou qual, e pode discordar de uma decisão
    específica em vez de ter que aceitar ou recusar o tratamento inteiro.
    """
    linhas = []
    # todas as colunas que o Silver toca, para o total desta tabela fechar com o
    # total de células ajustadas do manifesto. Faltando uma, o cliente soma a
    # coluna de ocorrências e encontra um número diferente do que o relatório diz
    for tabela, coluna in (("endereco", "cidade"), ("endereco", "nome_local"),
                           ("endereco", "logradouro"), ("entrega", "recebedor"),
                           ("ocorrencia", "observacao")):
        b = pd.read_parquet(BRONZE / f"{tabela}.parquet", columns=[coluna])[coluna]
        s = pd.read_parquet(SILVER / f"{tabela}.parquet", columns=[coluna])[coluna]
        mudou = (b != s) & ~(b.isna() & s.isna())
        par = pd.DataFrame({"antes": b[mudou], "depois": s[mudou]})
        if par.empty:
            continue
        resumo = (par.groupby(["antes", "depois"], dropna=False)
                     .size().reset_index(name="ocorrencias"))
        resumo.insert(0, "coluna", coluna)
        resumo.insert(0, "tabela", tabela)
        resumo["motivo"] = resumo.apply(_motivo, axis=1)
        linhas.append(resumo)

    _gravar_csv("texto_antes_depois.csv",
                pd.concat(linhas).sort_values("ocorrencias", ascending=False))


def _motivo(linha: pd.Series) -> str:
    """Classifica por que o valor mudou, para a tela poder filtrar por tipo de correção."""
    if pd.isna(linha["depois"]):
        # o texto virou ausência: é o caso de `-`, `N/A` e `sem informacao`, que
        # são vazio disfarçado de conteúdo
        return "convertido em ausência"
    antes, depois = str(linha["antes"]), str(linha["depois"])
    if antes.strip() != antes:
        return "espaço nas pontas"
    if tr.sem_acento(antes) == antes and tr.sem_acento(depois) != depois:
        return "acento restaurado"
    if antes.upper() == antes and depois.upper() != depois:
        return "caixa alta corrigida"
    if antes.lower() == depois.lower():
        return "caixa corrigida"
    return "abreviação expandida"


def _ausencias_por_coluna() -> None:
    """Onde estão os campos vazios, e quantos, nas duas camadas.

    Serve à tela que responde "o tratamento inventou dado?": qualquer diferença
    entre as duas colunas aparece aqui, e cada uma precisa de justificativa.
    """
    linhas = []
    for arquivo in sorted(BRONZE.glob("*.parquet")):
        nome = arquivo.stem
        b = pd.read_parquet(arquivo)
        s = pd.read_parquet(SILVER / f"{nome}.parquet")
        for coluna in b.columns:
            if coluna.startswith("_") or coluna not in s.columns:
                continue
            nb, ns = int(b[coluna].isna().sum()), int(s[coluna].isna().sum())
            if nb or ns:
                linhas.append({"tabela": nome, "coluna": coluna, "linhas": len(b),
                               "vazios_bronze": nb, "vazios_silver": ns,
                               "percentual": round(nb / len(b) * 100, 2)})
    _gravar_csv("ausencias.csv",
                pd.DataFrame(linhas).sort_values("vazios_bronze", ascending=False))


if __name__ == "__main__":
    executar()
