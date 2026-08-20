"""Identidade visual do cliente aplicada ao Streamlit.

As duas cores vêm do logo (`#284D70` e `#A2BBB7`), as mesmas do relatório. A
apresentação e o documento precisam parecer a mesma entrega: se o dash tiver
outra cara, o cliente lê como dois trabalhos diferentes.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]

MARCA = "#284D70"
MARCA_CLARA = "#3A6B96"
APOIO = "#A2BBB7"
APOIO_CLARA = "#E8EFED"
TINTA = "#1C2733"
TINTA_SUAVE = "#5A6672"
ALTA = "#B4462F"
MEDIA = "#B98514"
BAIXA = "#5A7D6E"

SEVERIDADES = {"alta": ALTA, "média": MEDIA, "baixa": BAIXA}


def logo(negativo: bool = False) -> str:
    """Devolve o logo em base64, para embutir direto no HTML da página."""
    nome = "logo_tfb_negativo.png" if negativo else "logo_tfb.png"
    return base64.b64encode((RAIZ / "assets" / nome).read_bytes()).decode()


CSS = f"""
<style>
section[data-testid="stSidebar"] {{ background-color: {MARCA} !important; }}
section[data-testid="stSidebar"] * {{ color: #E8EFED !important; }}
section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.22) !important; }}
section[data-testid="stSidebar"] img {{ margin-bottom: 8px; }}

/* o rótulo do rádio de navegação vira item de menu, não campo de formulário */
section[data-testid="stSidebar"] label {{ font-size: .92rem; }}

h1, h2 {{ color: {MARCA} !important; }}
h2 {{ border-bottom: 2px solid {APOIO_CLARA}; padding-bottom: 6px; }}
h3 {{ color: {TINTA} !important; }}

div[data-testid="stMetric"] {{
  background: #fff;
  border: 1px solid #DCE2E8;
  border-top: 3px solid {MARCA};
  border-radius: 4px;
  padding: 14px 16px !important;
}}
div[data-testid="stMetricValue"] {{ color: {MARCA}; font-size: 1.7rem; }}
div[data-testid="stMetricLabel"] {{ color: {TINTA_SUAVE}; }}

.caixa {{ border-left: 4px solid {APOIO}; background: {APOIO_CLARA};
          padding: 14px 18px; border-radius: 0 3px 3px 0; margin: 10px 0; }}
.caixa.atencao {{ border-left-color: {ALTA}; background: #FBF0ED; }}
.caixa.nota {{ border-left-color: {MARCA}; background: #F4F7FA; }}
.caixa b {{ color: {MARCA}; }}
.caixa.atencao b {{ color: {ALTA}; }}

.cartao {{
  background: #fff; border: 1px solid #DCE2E8; border-top: 3px solid {MARCA};
  border-radius: 4px; padding: 16px 18px; height: 100%;
}}
.cartao h4 {{ color: {MARCA}; margin: 6px 0 6px; font-size: .98rem; }}
.cartao .pergunta {{ color: {TINTA_SUAVE}; font-size: .85rem; font-style: italic;
                     margin-bottom: 10px; }}
.cartao ul {{ margin: 0; padding-left: 16px; color: {TINTA_SUAVE}; font-size: .8rem; }}

.selo {{ display: inline-block; background: {MARCA}; color: #fff; border-radius: 2px;
         padding: 2px 9px; font-size: .68rem; font-weight: 700; letter-spacing: .08em;
         text-transform: uppercase; }}
.selo.previsto {{ background: {TINTA_SUAVE}; }}

.tag {{ display: inline-block; border-radius: 2px; padding: 1px 9px; font-size: .72rem;
        font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: #fff; }}

.rodape {{ color: {TINTA_SUAVE}; font-size: .8rem; border-top: 1px solid #DCE2E8;
           padding-top: 14px; margin-top: 28px; }}
</style>
"""


def aplicar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
