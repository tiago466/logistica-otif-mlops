"""Gera a Sala de Resultados: a porta de entrada e os dois relatórios do cliente.

Dois documentos, um fato. O executivo responde **"qual é o estado da minha base e
o que eu preciso decidir?"**; o técnico responde **"como você chegou nesse número
e como eu reproduzo?"**. Os dois saem do mesmo catálogo de achados e da mesma
apuração, então nunca divergem em número.

Os HTML são autocontidos (CSS e logo embutidos), o que permite enviar por e-mail,
abrir sem internet e imprimir em A4 pelo Ctrl+P sem perder a identidade visual.

Rodar: uv run python -m logistica_otif_mlops.relatorios
"""

from __future__ import annotations

import base64
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from logistica_otif_mlops.relatorios.apuracao import RAIZ, apurar
from logistica_otif_mlops.relatorios.catalogo import ACHADOS, CAPITULOS

TEMPLATES = Path(__file__).parent / "templates"
DESTINO = RAIZ / "reports"

CLIENTE = "Trans Fictício BR"
AUTOR = "Tiago Lima · Ciência de Dados"
AVISO = ("Empresa fictícia e dados sintéticos: projeto de portfólio, sem vínculo com "
         "qualquer empresa real de nome semelhante.")

MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro")


def executar() -> None:
    dados = apurar()
    ambiente = _ambiente()
    DESTINO.mkdir(parents=True, exist_ok=True)

    css = (TEMPLATES / "estilo.css").read_text(encoding="utf-8")
    logo = _embutir("logo_tfb.png")
    logo_negativo = _embutir("logo_tfb_negativo.png")
    atual = next(c for c in CAPITULOS if c.situacao == "concluido")
    proximo = next(c for c in CAPITULOS if c.situacao != "concluido")

    comum: dict[str, Any] = {
        "cliente": CLIENTE,
        "autor": AUTOR,
        "aviso": AVISO,
        "css": css,
        "logo": logo,
        "logo_negativo": logo_negativo,
        "dados": dados,
        "achados": ACHADOS,
        "capitulos": CAPITULOS,
        "capitulo_atual": atual,
        "proximo": proximo,
        "capitulo": f"{atual.numero}. {atual.titulo}",
        "emitido_em": _hoje(),
        "testes": _contar_testes(),
    }

    paginas = [
        ("index.html.j2", "index.html", {}),
        ("executivo.html.j2", "executivo.html", {
            "titulo": "Diagnóstico da Base de Dados",
            "subtitulo": ("O estado dos dados que sustentam a operação: o que foi "
                          "encontrado, o que já foi corrigido e o que depende de decisão."),
            "selo": "Apresentação Executiva",
            "irmao": {"arquivo": "tecnico.html", "rotulo": "ver a versão técnica"},
        }),
        ("tecnico.html.j2", "tecnico.html", {
            "titulo": "Qualidade de Dados e Auditoria do Tratamento",
            "subtitulo": ("Método, evidência e prestação de contas do que foi alterado "
                          "na base, célula a célula."),
            "selo": "Apresentação Técnica",
            "irmao": {"arquivo": "executivo.html", "rotulo": "ver a versão executiva"},
        }),
    ]

    print("== sala de resultados ==")
    for template, arquivo, extra in paginas:
        html = ambiente.get_template(template).render(**comum, **extra)
        caminho = DESTINO / arquivo
        caminho.write_text(html, encoding="utf-8")
        print(f"  {arquivo:<16} {len(html) / 1024:>7.1f} KB")

    print(f"\nOK: {DESTINO}")
    print(f"Abra {DESTINO / 'index.html'} no navegador.")


def _embutir(nome: str) -> str:
    """Lê um asset e devolve em base64, para o HTML não depender de arquivo externo."""
    return base64.b64encode((RAIZ / "assets" / nome).read_bytes()).decode()


def _ambiente() -> Environment:
    ambiente = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    ambiente.filters["milhar"] = _milhar
    ambiente.filters["classe"] = _classe
    ambiente.filters["situacao"] = _situacao
    ambiente.filters["dono"] = _dono
    ambiente.filters["seguro"] = _seguro
    return ambiente


def _milhar(valor: int | float) -> str:
    """Separador de milhar no padrão brasileiro."""
    return f"{valor:,.0f}".replace(",", ".")


def _classe(severidade: str) -> str:
    """Severidade vira classe CSS: 'média' tem acento, classe não pode ter."""
    return {"alta": "alta", "média": "media", "baixa": "baixa"}.get(severidade, "baixa")


def _situacao(valor: str) -> str:
    return {"concluido": "concluído", "em_andamento": "em andamento",
            "previsto": "previsto"}.get(valor, valor)


def _dono(severidade: str) -> str:
    """Quem decide, por severidade. Alta sobe para a operação; o resto fica na TI."""
    return "Operação e TI" if severidade == "alta" else "TI"


def _seguro(texto: str) -> Markup:
    """Converte a marcação leve do catálogo (`código` e **negrito**) em HTML.

    O autoescape do Jinja fica ligado, então o texto é escapado antes e só estes
    dois padrões viram tag. Assim o catálogo continua legível como texto puro sem
    abrir espaço para injeção de HTML.
    """
    import html
    import re

    saida = html.escape(texto)
    saida = re.sub(r"`([^`]+)`", r"<code>\1</code>", saida)
    saida = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", saida)
    return Markup(saida)


def _hoje() -> str:
    hoje = date.today()
    return f"{hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}"


def _contar_testes() -> int:
    """Conta os testes existentes, para o documento não citar número desatualizado."""
    import re

    total = 0
    for arquivo in (RAIZ / "tests").glob("test_*.py"):
        total += len(re.findall(r"^\s+def test_", arquivo.read_text(encoding="utf-8"),
                                flags=re.MULTILINE))
    return total


if __name__ == "__main__":
    executar()
