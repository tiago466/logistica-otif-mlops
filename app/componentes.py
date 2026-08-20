"""Peças visuais reutilizadas pelos módulos.

Existem para que todo módulo novo já nasça com a mesma aparência. Sem elas, o
módulo 4 seria escrito seis meses depois do módulo 1 e pareceria outro produto.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from app import estilo


def milhar(valor: float) -> str:
    """Separador de milhar no padrão brasileiro."""
    return f"{valor:,.0f}".replace(",", ".")


def caixa(texto: str, tipo: str = "") -> None:
    """Bloco de destaque. `tipo` vazio é o padrão, `atencao` e `nota` variam a cor."""
    st.markdown(f'<div class="caixa {tipo}">{texto}</div>', unsafe_allow_html=True)


def nota_tecnica(observado: str, importa: str, acao: str) -> None:
    """A Nota Técnica que fecha cada seção, no mesmo formato dos notebooks.

    Repetir a estrutura observado / por que importa / ação é o que faz o leitor
    saber onde procurar a conclusão sem ter que ler a seção inteira de novo.
    """
    st.markdown(
        f'<div class="caixa nota">'
        f"<b>Nota Técnica</b><br><br>"
        f"<b>Observado:</b> {observado}<br><br>"
        f"<b>Por que importa:</b> {importa}<br><br>"
        f"<b>Ação:</b> {acao}</div>",
        unsafe_allow_html=True,
    )


def cartao_secao(selo: str, titulo: str, pergunta: str, topicos: list[str],
                 previsto: bool = False) -> str:
    """O card que descreve um módulo na home, com a pergunta de negócio que ele responde."""
    itens = "".join(f"<li>{t}</li>" for t in topicos)
    classe = "selo previsto" if previsto else "selo"
    return (f'<div class="cartao"><span class="{classe}">{selo}</span>'
            f"<h4>{titulo}</h4>"
            f'<div class="pergunta">"{pergunta}"</div>'
            f"<ul>{itens}</ul></div>")


def tag(texto: str, cor: str) -> str:
    return f'<span class="tag" style="background:{cor}">{texto}</span>'


def barras(rotulos: list[str], valores: list[float], titulo: str,
           sufixo: str = "", altura: int = 320) -> go.Figure:
    """Barras horizontais na cor da marca, com o valor escrito na ponta.

    Horizontal porque os rótulos são nomes de coluna (`entrega.recebedor`), que
    ficariam inclinados e ilegíveis num eixo x.
    """
    figura = go.Figure(go.Bar(
        x=valores, y=rotulos, orientation="h",
        marker_color=estilo.MARCA,
        text=[f"{milhar(v)}{sufixo}" for v in valores],
        textposition="outside",
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    figura.update_layout(
        title=dict(text=titulo, font=dict(size=15, color=estilo.MARCA)),
        height=altura,
        margin=dict(t=50, b=30, l=10, r=70),
        plot_bgcolor="white",
        yaxis=dict(autorange="reversed"),
        xaxis=dict(showgrid=True, gridcolor="#EEF2F5", zeroline=False),
        font=dict(size=12, color=estilo.TINTA),
        showlegend=False,
    )
    return figura


def antes_depois(rotulos: list[str], antes: list[float], depois: list[float],
                 titulo: str, altura: int = 340) -> go.Figure:
    """Duas barras por categoria: o estado antes do tratamento e o depois."""
    figura = go.Figure()
    figura.add_bar(name="Antes (Bronze)", x=rotulos, y=antes,
                   marker_color=estilo.APOIO,
                   text=[milhar(v) for v in antes], textposition="outside")
    figura.add_bar(name="Depois (Silver)", x=rotulos, y=depois,
                   marker_color=estilo.MARCA,
                   text=[milhar(v) for v in depois], textposition="outside")
    figura.update_layout(
        title=dict(text=titulo, font=dict(size=15, color=estilo.MARCA)),
        barmode="group", height=altura,
        margin=dict(t=50, b=40, l=10, r=20),
        plot_bgcolor="white",
        yaxis=dict(showgrid=True, gridcolor="#EEF2F5", zeroline=False),
        font=dict(size=12, color=estilo.TINTA),
        legend=dict(orientation="h", y=1.12, x=0),
    )
    return figura


def rodape(dados: dict[str, Any]) -> None:
    carga = dados["carga"]
    st.markdown(
        f'<div class="rodape">Base analisada: {milhar(carga["linhas"])} registros em '
        f'{carga["tabelas"]} tabelas · carga de referência {carga["ingerido_em"]} · '
        f"tratamento processado em {carga['processado_em']}.<br>"
        "Empresa fictícia e dados sintéticos: projeto de portfólio, sem vínculo com "
        "qualquer empresa real de nome semelhante.</div>",
        unsafe_allow_html=True,
    )
