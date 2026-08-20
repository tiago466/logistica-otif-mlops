"""O registro de módulos e subseções da apresentação.

Cada etapa do projeto vira um **módulo**: um item no menu lateral, um cartão no
mapa da porta de entrada e um conjunto de subabas. Acrescentar um módulo é somar
uma entrada nesta lista e escrever os templates dele. O roteador, o menu e o mapa
se reorganizam sozinhos.

Um módulo sem subseções é um módulo **previsto**: ele aparece no menu e no mapa,
mas abre um aviso em vez de conteúdo. Mostrar o que ainda não existe é
deliberado: o cliente enxerga o caminho inteiro desde a primeira reunião, em vez
de achar que a entrega é só o que está pronto hoje.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Subsecao:
    chave: str
    numero: str
    titulo: str
    resumo: str  # a linha que abre o painel, explicando o que ele responde

    @property
    def rotulo(self) -> str:
        return f"{self.numero} {self.titulo}"


@dataclass(frozen=True)
class Modulo:
    chave: str
    numero: int
    icone: str  # nome do símbolo SVG em `_icones.html`
    titulo: str
    pergunta: str  # a pergunta de negócio que o módulo responde
    subsecoes: list[Subsecao] = field(default_factory=list)

    @property
    def previsto(self) -> bool:
        return not self.subsecoes

    @property
    def inicial(self) -> str:
        return self.subsecoes[0].chave if self.subsecoes else ""


MODULOS: list[Modulo] = [
    Modulo(
        chave="qualidade",
        numero=1,
        icone="lupa",
        titulo="Qualidade, Tratamento e Limpeza",
        pergunta="Posso confiar nesses dados antes de concluir qualquer coisa deles?",
        subsecoes=[
            Subsecao("fotografia", "1.1", "A fotografia da base",
                     "Toda avaliação de qualidade descreve um instante. Sem dizer qual, a "
                     "conclusão perde validade: a base muda todo dia, e um defeito "
                     "corrigido ontem continuaria sendo reportado hoje."),
            Subsecao("diagnostico", "1.2", "O diagnóstico",
                     "Doze dimensões verificadas. As que passaram estão registradas junto "
                     "com as que falharam, porque sem isso o leitor não sabe se a dimensão "
                     "foi verificada e passou ou se simplesmente não foi olhada."),
            Subsecao("tratamento", "1.3", "O que foi tratado",
                     "O tratamento corrige forma, nunca conteúdo. Cada valor que mudou "
                     "está listado, com a forma antiga, a nova e o motivo."),
            Subsecao("contas", "1.4", "A prestação de contas",
                     "Um pipeline de limpeza falha de dois jeitos, e o pior é invisível: "
                     "corrigir o que não devia. Esta tela foi feita para pegar esse caso."),
            Subsecao("acoes", "1.5", "O que depende de vocês",
                     "Nem tudo se resolve do nosso lado. Enquanto a causa não for tratada "
                     "na origem, o defeito volta a cada nova carga."),
        ],
    ),
    Modulo(
        chave="operacao",
        numero=2,
        icone="grafico",
        titulo="O que os dados dizem sobre a operação",
        pergunta="Onde o prazo se perde, e o que o histórico contradiz do que achamos saber?",
    ),
    Modulo(
        chave="previsao",
        numero=3,
        icone="alvo",
        titulo="Previsão de atraso e nova data prevista",
        pergunta="Quais pedidos vão atrasar, e para quando devo reprometer ao cliente?",
    ),
    Modulo(
        chave="operacao_modelo",
        numero=4,
        icone="engrenagem",
        titulo="Operação do modelo e monitoramento",
        pergunta="Como isso se sustenta em produção, e quando preciso desconfiar dele?",
    ),
]

POR_CHAVE = {m.chave: m for m in MODULOS}


def entregues() -> list[Modulo]:
    return [m for m in MODULOS if not m.previsto]
