"""Módulo 1 · Qualidade, Tratamento e Limpeza dos Dados.

A pergunta que ele responde: **posso confiar nesses dados?**

O que este módulo faz que o relatório em PDF não faz: deixa o cliente **filtrar e
descer ao registro**. O documento afirma "333 endereços duplicados"; aqui o dono
do cadastro filtra por UF e vê quais são os dele. É a diferença entre receber uma
conclusão e poder conferi-la.

Fonte: notebooks 00 (diagnóstico) e 01 (auditoria do tratamento).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import componentes as ui
from app import dados, estilo


def render() -> None:
    apuracao = dados.apuracao()
    achados = dados.catalogo()["achados"]

    st.markdown("## 🔍 Módulo 1 · Qualidade, Tratamento e Limpeza")
    st.markdown(
        "*Antes de qualquer análise ou modelo, uma pergunta precisa de resposta com "
        "evidência: **os dados sustentam o que vamos concluir deles?** Este módulo "
        "responde, e presta contas de tudo que foi alterado na base.*"
    )

    abas = st.tabs([
        "1.1 A fotografia da base",
        "1.2 O diagnóstico",
        "1.3 O que foi tratado",
        "1.4 A prestação de contas",
        "1.5 O que depende de vocês",
    ])

    with abas[0]:
        _fotografia(apuracao)
    with abas[1]:
        _diagnostico(achados)
    with abas[2]:
        _tratamento(apuracao)
    with abas[3]:
        _prestacao_de_contas(apuracao)
    with abas[4]:
        _acoes_do_cliente(achados)


# ---------------------------------------------------------------------------
def _fotografia(apuracao: dict) -> None:
    carga = apuracao["carga"]
    st.markdown("### 1.1 A fotografia da base")
    st.markdown(
        "Toda avaliação de qualidade descreve **um instante**. Sem dizer qual, a "
        "conclusão perde validade: a base muda todo dia, e um defeito corrigido ontem "
        "continuaria sendo reportado hoje."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tabelas", carga["tabelas"])
    c2.metric("Colunas", carga["colunas"])
    c3.metric("Registros", ui.milhar(carga["linhas"]))
    c4.metric("Campos preenchidos", ui.milhar(carga["celulas"]))

    inventario = dados.inventario()
    st.plotly_chart(
        ui.barras(inventario["tabela"].tolist(), inventario["linhas"].tolist(),
                  "Volume por tabela", altura=520),
        use_container_width=True,
    )

    st.dataframe(
        inventario.rename(columns={"tabela": "Tabela", "linhas": "Registros",
                                   "colunas": "Colunas"}),
        hide_index=True, use_container_width=True,
    )

    ui.nota_tecnica(
        f"a base tem {ui.milhar(carga['linhas'])} registros distribuídos de forma muito "
        "desigual: cinco tabelas concentram a maior parte do volume, e o restante são "
        "cadastros pequenos.",
        "o desequilíbrio define onde vale investir esforço de qualidade. Um defeito numa "
        "tabela de 14 milhões de linhas custa caro para corrigir e afeta todo indicador; "
        "um defeito num cadastro de 240 linhas se resolve por conferência manual.",
        f"nenhuma. A carga de {carga['ingerido_em']} é a referência de todos os números "
        "deste módulo.",
    )


# ---------------------------------------------------------------------------
def _diagnostico(achados: list[dict]) -> None:
    st.markdown("### 1.2 O diagnóstico")
    st.markdown(
        "Doze dimensões de qualidade foram verificadas. As que **passaram** estão "
        "registradas junto com as que falharam, porque sem isso o leitor não sabe se a "
        "dimensão foi verificada e passou ou se simplesmente não foi olhada."
    )

    c1, c2, c3 = st.columns(3)
    for coluna, severidade in zip((c1, c2, c3), ("alta", "média", "baixa"), strict=True):
        quantidade = sum(1 for a in achados if a["severidade"] == severidade)
        coluna.metric(f"Achados de severidade {severidade}", quantidade)

    ui.caixa(
        "<b>A leitura geral é boa.</b> Não há duplicata de chave, não há inversão de "
        "datas, não há número impossível e nenhuma referência aponta para registro "
        "inexistente. Os problemas se concentram no <b>texto digitado por pessoas</b> e "
        "em <b>duas ausências que são de processo, não de sistema</b>."
    )

    filtro = st.multiselect(
        "Filtrar por severidade", ["alta", "média", "baixa"],
        default=["alta", "média", "baixa"],
    )

    for achado in achados:
        if achado["severidade"] not in filtro:
            continue
        cor = estilo.SEVERIDADES[achado["severidade"]]
        with st.container(border=True):
            cabeca, marcas = st.columns([4, 1.6])
            cabeca.markdown(f"**{achado['codigo']} · {achado['titulo']}**")
            marcas.markdown(
                ui.tag(achado["severidade"], cor) + " "
                + ui.tag(achado["situacao"], estilo.MARCA),
                unsafe_allow_html=True,
            )
            st.markdown(_formatar(achado["impacto"]))
            st.caption(f"**O que fizemos:** {achado['decisao']}  ·  "
                       f"**Evidência:** {achado['evidencia']}")

    ui.nota_tecnica(
        f"{len(achados)} achados, sendo "
        f"{sum(1 for a in achados if a['severidade'] == 'alta')} de severidade alta. "
        "Nenhum deles inviabiliza a análise, mas todos distorcem algum indicador se "
        "forem ignorados.",
        "severidade aqui não mede o tamanho do defeito, mede **o quanto ele engana**. "
        "A cidade em quatro grafias é grave não por serem quatro linhas a mais, mas "
        "porque as quatro parecem cidades legítimas na tela, e a decisão sobre frota "
        "sai errada sem que ninguém desconfie.",
        f"{sum(1 for a in achados if a['origem'])} dos achados precisam de correção no "
        "sistema do cliente, ou voltam na próxima carga.",
    )


# ---------------------------------------------------------------------------
def _tratamento(apuracao: dict) -> None:
    ajustes = apuracao["ajustes"]
    carga = apuracao["carga"]
    st.markdown("### 1.3 O que foi tratado")
    st.markdown(
        "O tratamento corrige **forma**, nunca **conteúdo**. `sao paulo` vira "
        "`São Paulo` porque é a mesma cidade escrita de outro jeito; um valor ausente "
        "continua ausente, porque inventá-lo seria criar dado que ninguém coletou."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Células corrigidas", ui.milhar(ajustes["total"]))
    c2.metric("Campos afetados", f"{ajustes['colunas']} de {carga['colunas']}")
    c3.metric("Proporção", f"1 em {ui.milhar(carga['celulas'] // ajustes['total'])}")
    c4.metric("Valores, datas ou chaves", "0", help="nenhum foi alterado")

    st.plotly_chart(
        ui.barras([f"{linha['tabela']}.{linha['coluna']}" for linha in ajustes["detalhe"]],
                  [linha["celulas"] for linha in ajustes["detalhe"]],
                  "Células alteradas, por campo", altura=300),
        use_container_width=True,
    )

    st.markdown("#### Cada valor que mudou, e por quê")
    st.markdown(
        "Sem esta tabela, *conformamos a grafia* é afirmação sem prova. Com ela, dá "
        "para discordar de uma decisão específica em vez de aceitar ou recusar o "
        "tratamento inteiro."
    )

    tabela = dados.texto_antes_depois()
    c1, c2, c3 = st.columns([1.2, 1.4, 2])
    coluna = c1.selectbox("Campo", ["todos", *sorted(tabela["coluna"].unique())])
    motivo = c2.selectbox("Motivo", ["todos", *sorted(tabela["motivo"].unique())])
    busca = c3.text_input("Buscar um valor", placeholder="ex.: SAO PAULO")

    filtrada = tabela
    if coluna != "todos":
        filtrada = filtrada[filtrada["coluna"] == coluna]
    if motivo != "todos":
        filtrada = filtrada[filtrada["motivo"] == motivo]
    if busca:
        alvo = busca.strip().lower()
        filtrada = filtrada[
            filtrada["antes"].str.lower().str.contains(alvo, na=False)
            | filtrada["depois"].str.lower().str.contains(alvo, na=False)
        ]

    st.caption(f"{ui.milhar(len(filtrada))} correções distintas · "
               f"{ui.milhar(filtrada['ocorrencias'].sum())} registros afetados")
    st.dataframe(
        filtrada[["tabela", "coluna", "antes", "depois", "motivo", "ocorrencias"]]
        .rename(columns={"tabela": "Tabela", "coluna": "Campo", "antes": "Antes",
                         "depois": "Depois", "motivo": "Motivo",
                         "ocorrencias": "Registros"}),
        hide_index=True, use_container_width=True, height=420,
    )

    ui.nota_tecnica(
        f"{ui.milhar(ajustes['total'])} células alteradas, o que é 1 em cada "
        f"{ui.milhar(carga['celulas'] // ajustes['total'])} campos da base, todas em "
        "colunas de texto de preenchimento manual.",
        "o mais importante desta seção é <b>o que não aparece nela</b>. Peso, volume, "
        "valor, data e chave estrangeira passaram intactos. Se qualquer um deles "
        "aparecesse na lista, o indicador do relatório teria sido alterado pela limpeza, "
        "e a diferença seria impossível de explicar depois.",
        "nenhuma. O escopo do tratamento é o texto digitado por pessoas, que era "
        "exatamente o diagnóstico.",
    )


# ---------------------------------------------------------------------------
def _prestacao_de_contas(apuracao: dict) -> None:
    ausencias_info = apuracao["ausencias"]
    st.markdown("### 1.4 A prestação de contas")
    st.markdown(
        "Um pipeline de limpeza falha de dois jeitos, e o segundo é muito pior. "
        "**Não corrigir o que devia** é visível: o defeito continua lá, alguém reclama. "
        "**Corrigir o que não devia** é invisível: o número fica bonito, o relatório "
        "fecha, e o dado está errado. Esta seção foi feita para pegar o segundo caso."
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Tabelas com grão preservado",
              f"{apuracao['grao']['preservadas']} de {apuracao['grao']['tabelas']}",
              help="uma linha entrou, uma linha saiu: nada foi agregado nem descartado")
    c2.metric("Ausências preenchidas", "0",
              help="nenhum campo vazio recebeu valor inventado")
    c3.metric("Regras idempotentes", "7 de 7",
              help="rodar o tratamento duas vezes produz o mesmo resultado")

    st.markdown("#### Os dois achados que precisavam sobreviver intactos")
    st.dataframe(
        pd.DataFrame([
            {"Achado": "Transferência para base sem recebedor (Q4)",
             "Antes": ui.milhar(ausencias_info["recebedor_bronze"]),
             "Depois": ui.milhar(ausencias_info["recebedor_silver"]),
             "Situação": "preservado"},
            {"Achado": "Item sem valor unitário (Q6)",
             "Antes": ui.milhar(ausencias_info["valor_bronze"]),
             "Depois": ui.milhar(ausencias_info["valor_silver"]),
             "Situação": "preservado"},
        ]),
        hide_index=True, use_container_width=True,
    )

    ui.caixa(
        "<b>Por que não preenchemos.</b> A ausência de recebedor na transferência entre "
        "bases não é falha de digitação, é <b>ausência de processo</b>: não existe "
        "conferência formal na chegada. Preencher esse campo apagaria do relatório o "
        "problema que precisa ser visto, e criaria um responsável que não existiu.",
        "atencao",
    )

    st.markdown("#### Onde estão os campos vazios")
    tabela = dados.ausencias()
    tabela["diferença"] = tabela["vazios_silver"] - tabela["vazios_bronze"]
    st.dataframe(
        tabela.rename(columns={
            "tabela": "Tabela", "coluna": "Campo", "linhas": "Registros",
            "vazios_bronze": "Vazios antes", "vazios_silver": "Vazios depois",
            "percentual": "% vazio", "diferença": "Diferença"}),
        hide_index=True, use_container_width=True, height=340,
    )

    divergentes = ausencias_info["divergentes"]
    ui.nota_tecnica(
        f"de todas as colunas da base, apenas {len(divergentes)} teve a contagem de "
        "vazios alterada, e por decisão explícita: em `ocorrencia.observacao` havia "
        "texto como `-`, `N/A` e `sem informacao`, que é ausência disfarçada de "
        "conteúdo.",
        "converter esse texto em ausência é o <b>inverso</b> de preencher um vazio. "
        "Manter `-` faria qualquer agrupamento por motivo de ocorrência exibi-lo como "
        "se fosse uma categoria real, competindo em volume com motivos de verdade. "
        "Converter <b>revela</b> a falta; preencher <b>esconde</b> a falta.",
        "as verificações desta seção rodam a cada execução do pipeline, e não uma vez só.",
    )


# ---------------------------------------------------------------------------
def _acoes_do_cliente(achados: list[dict]) -> None:
    st.markdown("### 1.5 O que depende de vocês")
    st.markdown(
        "Nem tudo se resolve do nosso lado. Os pontos abaixo são de **decisão** ou de "
        "**sistema de origem**: enquanto não forem tratados na fonte, voltam a cada "
        "nova carga, e nós os corrigimos de novo, indefinidamente."
    )

    for achado in (a for a in achados if a["origem"]):
        with st.container(border=True):
            st.markdown(f"**{achado['codigo']} · {achado['titulo']}**")
            st.markdown(_formatar(achado["acao_cliente"]))

    st.markdown("#### Os endereços duplicados, para conferência")
    st.markdown(
        "Esta é a lista que o dono do cadastro abre para decidir. **Não fundimos nada**: "
        "eliminar registro quebraria o histórico dos pedidos antigos, e a escolha de "
        "qual cadastro sobrevive é de vocês, não nossa."
    )

    tabela = dados.enderecos_duplicados()
    c1, c2 = st.columns([1, 3])
    uf = c1.selectbox("UF", ["todas", *sorted(tabela["uf"].dropna().unique())])
    cidade = c2.text_input("Cidade", placeholder="ex.: São Paulo")

    filtrada = tabela
    if uf != "todas":
        filtrada = filtrada[filtrada["uf"] == uf]
    if cidade:
        filtrada = filtrada[
            filtrada["cidade"].str.lower().str.contains(cidade.strip().lower(), na=False)
        ]

    grupos = filtrada["chave_endereco"].nunique()
    st.caption(f"{grupos} grupos · {len(filtrada)} cadastros · "
               f"{len(filtrada) - grupos} registros seriam eliminados numa fusão")
    st.dataframe(
        filtrada[["cadastros_no_grupo", "id", "nome_local", "logradouro", "bairro",
                  "cidade", "uf", "cep"]]
        .rename(columns={"cadastros_no_grupo": "No grupo", "id": "Cadastro",
                         "nome_local": "Local", "logradouro": "Logradouro",
                         "bairro": "Bairro", "cidade": "Cidade", "uf": "UF",
                         "cep": "CEP"}),
        hide_index=True, use_container_width=True, height=420,
    )
    st.download_button(
        "Baixar esta lista em CSV",
        filtrada.to_csv(index=False).encode("utf-8"),
        file_name="enderecos_duplicados.csv",
        mime="text/csv",
    )

    ui.nota_tecnica(
        f"{sum(1 for a in achados if a['origem'])} dos {len(achados)} achados têm causa "
        "no sistema de origem e voltam a cada carga.",
        "corrigir na origem custa uma vez; corrigir no pipeline custa em toda carga, "
        "para sempre, e ainda deixa o dado errado dentro do sistema que a operação usa "
        "no dia a dia. O tratamento aqui é <b>paliativo consciente</b>, não solução.",
        "levar os quatro pontos ao dono do sistema e decidir a regra de valor para os "
        "itens sem preço, que trava qualquer cálculo financeiro por carga.",
    )


def _formatar(texto: str) -> str:
    """Converte a marcação leve do catálogo para o markdown do Streamlit."""
    return texto.replace("`", "`")
