"""O registro de módulos da apresentação.

Cada etapa do projeto vira um **módulo**: um item no menu lateral e um cartão na
página inicial. Acrescentar um módulo é escrever o arquivo dele e somar uma linha
nesta lista, sem tocar no roteador nem na home.

O objetivo dessa indireção é o projeto poder crescer por acréscimo. Quando o
capítulo de previsão de atraso ficar pronto, ele entra aqui como `MODULOS[3]` e a
apresentação inteira se reorganiza sozinha: menu, cartões e numeração.

Um módulo `previsto` aparece na home como cartão apagado, com a pergunta que ele
vai responder. Mostrar o que ainda não existe é deliberado: o cliente enxerga o
caminho inteiro desde a primeira reunião, e não fica com a impressão de que a
entrega é só o que está pronto hoje.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.modulos import m01_qualidade


@dataclass(frozen=True)
class Modulo:
    numero: int
    icone: str
    titulo: str
    pergunta: str  # a pergunta de negócio que o módulo responde
    topicos: list[str]  # as subseções, exibidas no cartão da home
    render: Callable[[], None] | None = None  # None = ainda não construído
    notebooks: list[str] = field(default_factory=list)

    @property
    def previsto(self) -> bool:
        return self.render is None

    @property
    def rotulo(self) -> str:
        return f"{self.icone}  {self.numero}. {self.titulo}"


MODULOS: list[Modulo] = [
    Modulo(
        numero=1,
        icone="🔍",
        titulo="Qualidade, Tratamento e Limpeza",
        pergunta="Posso confiar nesses dados antes de tirar qualquer conclusão deles?",
        topicos=[
            "1.1 A fotografia da base",
            "1.2 O diagnóstico: 7 achados",
            "1.3 O que foi tratado",
            "1.4 A prestação de contas",
            "1.5 O que depende de vocês",
        ],
        render=m01_qualidade.render,
        notebooks=["00_eda_qualidade_dados_ope.ipynb", "01_validacao_silver_ope.ipynb"],
    ),
    Modulo(
        numero=2,
        icone="📈",
        titulo="O que os dados dizem sobre a operação",
        pergunta="Onde o prazo se perde, e o que o histórico contradiz do que achamos saber?",
        topicos=[
            "2.1 Prazo por etapa do processo",
            "2.2 Concentração de clientes e rotas",
            "2.3 Sazonalidade e picos",
            "2.4 As heurísticas do negócio testadas",
        ],
    ),
    Modulo(
        numero=3,
        icone="🎯",
        titulo="Previsão de atraso e nova data prevista",
        pergunta="Quais pedidos vão atrasar, e para quando devo reprometer ao cliente?",
        topicos=[
            "3.1 Como o modelo enxerga um pedido",
            "3.2 Desempenho e limites declarados",
            "3.3 A nova data prevista de entrega",
            "3.4 Como usar no dia a dia",
        ],
    ),
    Modulo(
        numero=4,
        icone="⚙️",
        titulo="Operação do modelo e monitoramento",
        pergunta="Como isso se sustenta em produção, e quando preciso desconfiar dele?",
        topicos=[
            "4.1 O modelo em produção",
            "4.2 Monitoramento e desvio dos dados",
            "4.3 O que dispara uma reavaliação",
        ],
    ),
]


def por_rotulo(rotulo: str) -> Modulo:
    return next(m for m in MODULOS if m.rotulo == rotulo)


def disponiveis() -> list[Modulo]:
    return [m for m in MODULOS if not m.previsto]
