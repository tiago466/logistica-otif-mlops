"""O catálogo de achados: a fonte única dos dois relatórios.

Por que existe um catálogo em vez de o texto ficar dentro de cada template: o
relatório executivo e o técnico contam **o mesmo fato** em duas profundidades. Se
cada um tivesse a sua própria lista, os dois divergiriam na primeira correção, e
o cliente receberia dois documentos que se contradizem. Aqui o achado é escrito
uma vez, com as duas redações, e cada documento escolhe qual campo lê.

Regra de redação:

  * `impacto` é a linguagem do executivo. Fala de decisão, de risco e de dinheiro,
    nunca de coluna, função ou arquivo;
  * `detalhe` é a linguagem do técnico. Nomeia a tabela, a coluna e a regra;
  * `numero` é o mesmo nos dois. Número que muda entre documentos destrói a
    confiança em ambos.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Achado:
    """Um defeito encontrado na base, com as duas redações e o destino dado a ele."""

    codigo: str
    titulo: str
    severidade: str  # alta | média | baixa
    situacao: str  # tratado | marcado | preservado
    impacto: str  # redação executiva
    detalhe: str  # redação técnica
    decisao: str
    evidencia: str
    origem: bool = False  # precisa de correção no sistema do cliente?
    acao_cliente: str = ""


ACHADOS: list[Achado] = [
    Achado(
        codigo="Q1",
        titulo="A mesma cidade cadastrada de quatro jeitos",
        severidade="alta",
        situacao="tratado",
        impacto=(
            "Um relatório por cidade mostrava São Paulo dividida em quatro linhas, cada uma "
            "com uma parte do volume. Qualquer decisão tomada sobre concentração geográfica, "
            "dimensionamento de frota ou escolha de base partia de um número menor do que o "
            "real, e o erro não aparecia na tela: as quatro linhas pareciam quatro cidades "
            "legítimas."
        ),
        detalhe=(
            "65 cidades e 56 nomes de local em `endereco` apareciam em mais de uma grafia, "
            "por variação de caixa e de acentuação (`SAO PAULO`, `Sao Paulo`, `SÃO PAULO`, "
            "`São Paulo`). A capitalização sozinha não resolve, porque não devolve acento não "
            "digitado; foi preciso eleger uma grafia canônica por grupo."
        ),
        decisao="Conformar a grafia, elegendo uma forma oficial por grupo.",
        evidencia="121 valores em grafia múltipla reduzidos a 0.",
        origem=True,
        acao_cliente=(
            "O cadastro de endereço aceita texto livre no campo de cidade. Enquanto não "
            "houver validação ou lista de municípios na entrada, o problema volta na "
            "próxima carga."
        ),
    ),
    Achado(
        codigo="Q2",
        titulo="Endereço abreviado e por extenso na mesma base",
        severidade="alta",
        situacao="tratado",
        impacto=(
            "O mesmo endereço escrito como `R. das Flores` e como `Rua das Flores` é tratado "
            "como dois destinos diferentes por qualquer sistema que cruze a base com mapa, "
            "CEP ou malha de rotas. Metade dos cruzamentos falha em silêncio, e o custo por "
            "rota sai errado sem que nada acuse erro."
        ),
        detalhe=(
            "10.097 dos 19.697 logradouros usavam abreviação (`R.`, `Av.`, `Rod.`), em caixa "
            "variável. A expansão usa uma tabela de abreviações em `transformacoes.py`, que "
            "cresce por evidência: abreviação nova encontrada entra lá com teste próprio."
        ),
        decisao="Expandir a abreviação e capitalizar o restante.",
        evidencia="10.097 abreviados reduzidos a 0.",
        origem=True,
        acao_cliente=(
            "O campo de logradouro é texto livre. Vale avaliar preenchimento assistido por "
            "CEP na tela de cadastro."
        ),
    ),
    Achado(
        codigo="Q3",
        titulo="O mesmo endereço cadastrado mais de uma vez",
        severidade="alta",
        situacao="marcado",
        impacto=(
            "333 endereços físicos existem no cadastro em duplicata, somando 676 registros. "
            "Um cliente atendido nos dois cadastros aparece como dois pontos de entrega, o "
            "que distorce contagem de pontos atendidos, produtividade por rota e qualquer "
            "análise de cobertura. **Não fundimos os cadastros**, porque eliminar registro "
            "quebraria o histórico dos pedidos antigos e a escolha de qual cadastro sobrevive "
            "é decisão de vocês, não nossa."
        ),
        detalhe=(
            "A coluna derivada `chave_endereco` agrupa logradouro, cidade e UF em forma "
            "comparável e marca os grupos. O Silver marca e não funde: fusão é irreversível "
            "depois que o Bronze rotaciona, e os pedidos antigos referenciam o registro que "
            "seria eliminado."
        ),
        decisao="Marcar os grupos duplicados e devolver a decisão de fusão ao cliente.",
        evidencia="333 grupos, 676 cadastros, 343 registros seriam eliminados numa fusão.",
        origem=True,
        acao_cliente=(
            "Conferir os 333 grupos e decidir quais cadastros são o mesmo lugar. A decisão "
            "precisa de registro de quem decidiu e quando, porque é irreversível."
        ),
    ),
    Achado(
        codigo="Q4",
        titulo="Transferência para base não registra quem recebeu",
        severidade="alta",
        situacao="preservado",
        impacto=(
            "Em 1.239.076 transferências entre bases, o campo de quem recebeu a carga está "
            "vazio. Na última milha, o mesmo campo está preenchido em 99,97% dos casos. A "
            "diferença não é falha de digitação, é **ausência de processo**: não existe "
            "conferência formal na chegada à base. Isso significa que, entre a saída de uma "
            "base e a chegada na outra, não há responsável identificado pela carga."
        ),
        detalhe=(
            "`entrega.recebedor` nulo em 100% das linhas com `tipo_perna = "
            "TRANSFERENCIA_BASE`, contra 0,03% nas pernas de última milha. O Silver **não** "
            "preenche esse campo: a ausência é o próprio achado, e imputá-la apagaria do "
            "relatório o problema que precisa ser visto."
        ),
        decisao="Não tratar. É achado de processo, não de dado.",
        evidencia="1.239.076 ausências no Bronze e as mesmas 1.239.076 no Silver.",
        origem=True,
        acao_cliente=(
            "Definir se a conferência na chegada à base passa a ser obrigatória. É decisão "
            "de operação, com impacto em responsabilidade sobre avaria e extravio."
        ),
    ),
    Achado(
        codigo="Q5",
        titulo="Nome de quem recebeu digitado de formas diferentes",
        severidade="média",
        situacao="tratado",
        impacto=(
            "Os 56 nomes distintos de recebedor na base eram, na verdade, 32 pessoas escritas "
            "de jeitos diferentes. Uma análise de recorrência de recebedor por cliente "
            "estaria dividida quase pela metade, e o erro é invisível na tela porque "
            "`Maria Silva ` e `Maria Silva` parecem idênticos."
        ),
        detalhe=(
            "`entrega.recebedor` com 101.065 ocorrências em caixa alta e 42.147 com espaço "
            "nas pontas. Foi a coluna mais ajustada do pipeline: 168.523 células."
        ),
        decisao="Normalizar caixa e espaçamento, sem alterar o nome.",
        evidencia="56 nomes distintos reduzidos a 32.",
        origem=True,
        acao_cliente=(
            "O aplicativo do motorista aceita texto livre onde poderia haver seleção ou "
            "validação. É a origem do ruído."
        ),
    ),
    Achado(
        codigo="Q6",
        titulo="Itens sem valor unitário",
        severidade="média",
        situacao="preservado",
        impacto=(
            "345 itens do cadastro não têm valor unitário. Toda conta que dependa de valor "
            "da carga (seguro, indenização, priorização por valor) ignora esses itens ou os "
            "trata como se valessem zero. **Não preenchemos nenhum deles**, porque inventar "
            "um valor de mercadoria é criar um número que ninguém coletou e que entraria em "
            "cálculo financeiro como se fosse real."
        ),
        detalhe=(
            "`item.valor_unitario` nulo em 345 de 6.804 registros. Qualquer imputação depende "
            "de regra definida pelo cliente (média da categoria, último valor praticado, "
            "valor de nota) e precisa ser aplicada no Gold, com a decisão registrada."
        ),
        decisao="Não tratar. Depende de regra a ser definida pelo cliente.",
        evidencia="345 ausências no Bronze e as mesmas 345 no Silver.",
        origem=True,
        acao_cliente=(
            "Definir a regra de valor para item sem preço cadastrado, ou completar o cadastro."
        ),
    ),
    Achado(
        codigo="Q7",
        titulo="Observação de ocorrência preenchida com texto sem conteúdo",
        severidade="baixa",
        situacao="tratado",
        impacto=(
            "717 ocorrências tinham a observação preenchida com `-`, `N/A` ou "
            "`sem informacao`. Num agrupamento por motivo de ocorrência, esses valores "
            "apareceriam como se fossem uma categoria real, competindo em volume com motivos "
            "de verdade e sujando o ranking que orienta a ação da operação."
        ),
        detalhe=(
            "`ocorrencia.observacao` com marcadores de vazio. O tratamento converte esses "
            "textos em ausência, que é o inverso do erro de imputar: converter revela a "
            "falta, preencher esconde a falta."
        ),
        decisao="Converter o texto sem conteúdo em ausência explícita.",
        evidencia="717 registros convertidos para ausência.",
        origem=False,
    ),
]


@dataclass(frozen=True)
class Capitulo:
    """Um capítulo do relatório. A lista cresce conforme o projeto avança."""

    numero: int
    titulo: str
    resumo: str
    situacao: str  # concluido | em_andamento | previsto
    notebooks: list[str] = field(default_factory=list)


CAPITULOS: list[Capitulo] = [
    Capitulo(
        numero=1,
        titulo="Qualidade dos dados, tratamento e limpeza",
        resumo=(
            "O diagnóstico da base operacional e a prestação de contas do tratamento "
            "aplicado."
        ),
        situacao="concluido",
        notebooks=["00_eda_qualidade_dados_ope.ipynb", "01_validacao_silver_ope.ipynb"],
    ),
    Capitulo(
        numero=2,
        titulo="O que os dados dizem sobre a operação",
        resumo=(
            "A leitura analítica do histórico: prazo por etapa, concentração, sazonalidade e "
            "as heurísticas do negócio confrontadas com o que o dado mostra."
        ),
        situacao="previsto",
    ),
    Capitulo(
        numero=3,
        titulo="Previsão de atraso e nova data prevista",
        resumo=(
            "O modelo de previsão de OTIF e a projeção de nova data de entrega, com o "
            "desempenho medido e as limitações declaradas."
        ),
        situacao="previsto",
    ),
    Capitulo(
        numero=4,
        titulo="Operação do modelo e monitoramento",
        resumo=(
            "Como o modelo entra em produção, como é acompanhado e o que dispara uma "
            "reavaliação."
        ),
        situacao="previsto",
    ),
]
