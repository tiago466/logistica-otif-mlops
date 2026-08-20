"""Sala de Resultados · a apresentação interativa do projeto.

Três camadas de navegação, e cada uma existe por um motivo:

1. **A porta.** Uma tela só, com um botão. Ao abrir, ela ramifica em duas
   escolhas, Executivo e Técnico. Não é enfeite: obriga quem apresenta a declarar
   para quem está falando antes de mostrar qualquer número, e evita a cena
   clássica de abrir um dashboard técnico na frente da diretoria.
2. **Os módulos.** Uma etapa do projeto por módulo, no menu lateral. A lista vive
   em `modulos/__init__.py` e cresce por acréscimo.
3. **As subseções.** Dentro de cada módulo, em abas, cada uma fechando com a
   Nota Técnica no mesmo formato dos notebooks.

Rodar: uv run streamlit run app/Apresentacao.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# O Streamlit coloca no `sys.path` a pasta DO SCRIPT (`app/`), não a raiz do
# projeto. Sem esta linha, `from app import ...` falha, e o app só rodaria com
# PYTHONPATH definido por fora, que quebraria na publicação. Precisa vir antes
# dos imports do projeto, por isso o ruff ignora a ordem aqui.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from app import componentes as ui  # noqa: E402
from app import dados, estilo, modulos  # noqa: E402

CLIENTE = "Trans Fictício BR"

st.set_page_config(
    page_title=f"Sala de Resultados · {CLIENTE}",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    estilo.aplicar()
    if st.session_state.get("publico") is None:
        _porta()
    else:
        _apresentacao()


# ---------------------------------------------------------------------------
def _porta() -> None:
    """A tela de entrada: um botão que ramifica em duas escolhas."""
    st.markdown(
        f"""
        <style>
          section[data-testid="stSidebar"] {{ display: none; }}
          .stApp {{ background: {estilo.MARCA}; }}
          .porta {{ text-align: center; padding: 26px 0 6px; }}
          .porta img {{ height: 92px; margin-bottom: 22px; }}
          .porta h1 {{ color: #fff !important; font-size: 1.7rem; margin: 0 0 6px; }}
          .porta p {{ color: {estilo.APOIO}; margin: 0; font-size: .95rem; }}
          .ramo {{ text-align: center; color: {estilo.APOIO}; font-size: 1.5rem;
                   line-height: 1; margin: 2px 0 -4px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    _, meio, _ = st.columns([1, 2.1, 1])
    with meio:
        st.markdown(
            f'<div class="porta">'
            f'<img src="data:image/png;base64,{estilo.logo(negativo=True)}">'
            f"<h1>Sala de Resultados</h1>"
            f"<p>Projeto de Ciência de Dados · Previsão de atraso na entrega</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        aberta = st.session_state.get("porta_aberta", False)
        if not aberta:
            if st.button("🔑  Abrir a Sala de Resultados", type="primary",
                         use_container_width=True):
                st.session_state["porta_aberta"] = True
                st.rerun()
        else:
            # a "chave" que desce: o botão ramifica nas duas apresentações
            st.markdown('<div class="ramo">└─┬─┘</div>', unsafe_allow_html=True)
            esquerda, direita = st.columns(2)
            with esquerda:
                st.markdown("#### 📊 Executiva")
                st.caption("Os resultados: o que foi encontrado, o que mudou na base "
                           "e o que depende de decisão de vocês.")
                if st.button("Entrar", key="exec", type="primary",
                             use_container_width=True):
                    st.session_state["publico"] = "executivo"
                    st.rerun()
            with direita:
                st.markdown("#### 🛠️ Técnica")
                st.caption("Ferramentas, hospedagem, rotinas de manutenção e manuais "
                           "de operação. Entra quando o MLOps estiver de pé.")
                st.button("Em construção", key="tec", disabled=True,
                          use_container_width=True)

    carga = dados.apuracao()["carga"]
    st.markdown(
        f'<p style="text-align:center;color:{estilo.APOIO};font-size:.8rem;'
        f'margin-top:26px">{ui.milhar(carga["linhas"])} registros · '
        f'{carga["tabelas"]} tabelas · carga de {carga["ingerido_em"]}<br>'
        "Empresa fictícia e dados sintéticos: projeto de portfólio.</p>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
def _apresentacao() -> None:
    apuracao = dados.apuracao()

    with st.sidebar:
        st.markdown(
            f'<img src="data:image/png;base64,{estilo.logo(negativo=True)}" '
            f'style="width:100%;max-width:190px">',
            unsafe_allow_html=True,
        )
        st.markdown("**Apresentação Executiva**")
        st.divider()

        opcoes = ["🏠  Visão geral", *(m.rotulo for m in modulos.MODULOS)]
        escolha = st.radio("Navegação", opcoes, label_visibility="collapsed")

        st.divider()
        st.caption(f"Carga de referência\n\n**{apuracao['carga']['ingerido_em']}**")
        st.caption(f"Módulos entregues\n\n**{len(modulos.disponiveis())} "
                   f"de {len(modulos.MODULOS)}**")
        st.divider()
        if st.button("← Sair da sala", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if escolha.startswith("🏠"):
        _visao_geral(apuracao)
    else:
        modulo = modulos.por_rotulo(escolha)
        if modulo.previsto:
            _em_construcao(modulo)
        else:
            modulo.render()  # type: ignore[misc]

    ui.rodape(apuracao)


def _visao_geral(apuracao: dict) -> None:
    carga, ajustes = apuracao["carga"], apuracao["ajustes"]
    achados = dados.catalogo()["achados"]

    st.markdown(f"# Sala de Resultados · {CLIENTE}")
    st.markdown("*Projeto de Ciência de Dados · Previsão de atraso na entrega*")
    st.divider()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Registros analisados", ui.milhar(carga["linhas"]))
    c2.metric("Problemas encontrados", len(achados))
    c3.metric("Corrigidos por nós",
              sum(1 for a in achados if a["situacao"] == "tratado"))
    c4.metric("Dependem de vocês", sum(1 for a in achados if a["origem"]))
    c5.metric("Do dado foi alterado",
              f"1 em {ui.milhar(carga['celulas'] // ajustes['total'])}")

    esquerda, direita = st.columns(2)
    with esquerda:
        ui.caixa(
            "<b>🔍 Onde estamos</b><br><br>"
            f"A base operacional foi examinada por inteiro: {carga['tabelas']} tabelas, "
            f"{carga['colunas']} colunas, {ui.milhar(carga['linhas'])} registros. "
            "O diagnóstico está concluído, o tratamento aplicado e auditado.<br><br>"
            "<b>A base está estruturalmente saudável e é utilizável.</b>"
        )
    with direita:
        ui.caixa(
            "<b>🎯 O que já mudou</b><br><br>"
            "① Cidade e nome de local: 121 grafias duplicadas → <b>0</b><br>"
            "② Endereço abreviado: 10.097 → <b>0</b><br>"
            "③ Recebedor: 56 nomes distintos → <b>32</b> pessoas reais<br>"
            "④ 333 endereços duplicados <b>marcados</b>, nenhum fundido<br>"
            "⑤ 1.239.076 ausências <b>preservadas</b>, nenhuma inventada",
            
        )

    st.divider()
    st.markdown("#### 🗺️ O que cada módulo responde")
    st.caption("Os módulos marcados como previstos entram aqui conforme forem entregues. "
               "Mostrar o caminho inteiro desde o começo é deliberado.")

    for faixa in (modulos.MODULOS[:2], modulos.MODULOS[2:]):
        colunas = st.columns(len(faixa))
        for coluna, modulo in zip(colunas, faixa, strict=True):
            coluna.markdown(
                ui.cartao_secao(
                    f"Módulo {modulo.numero}" + (" · previsto" if modulo.previsto else ""),
                    modulo.titulo, modulo.pergunta, modulo.topicos, modulo.previsto,
                ),
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

    ui.caixa(
        "<b>Por que nesta ordem.</b> Modelo treinado sobre dado sujo aprende a sujeira. "
        "Só depois de a base estar conformada, e de a conformação estar prestada conta, "
        "faz sentido perguntar o que os dados dizem sobre a operação. E só depois disso "
        "faz sentido prever.",
        "nota",
    )


def _em_construcao(modulo: modulos.Modulo) -> None:
    st.markdown(f"## {modulo.icone} Módulo {modulo.numero} · {modulo.titulo}")
    ui.caixa(
        f"<b>Ainda não entregue.</b><br><br>Este módulo vai responder: "
        f'<i>"{modulo.pergunta}"</i><br><br>'
        + "".join(f"• {t}<br>" for t in modulo.topicos),
        "nota",
    )
    st.caption("O módulo aparece no menu desde já para o caminho do projeto ficar "
               "visível, não para sugerir que está pronto.")


main()
