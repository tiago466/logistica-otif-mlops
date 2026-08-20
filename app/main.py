"""Sala de Resultados · a apresentação do projeto, servida como sistema.

Mesma stack do produto Neviah: FastAPI, Jinja2, CSS próprio e HTMX self-hosted.
Zero CDN e zero framework de front, o que mantém a página leve, funcionando sem
internet e sem depender de serviço de terceiro para exibir dado de cliente.

Três camadas de navegação:

1. **A porta** (`/`), com a vitrine à esquerda e as duas apresentações à direita.
   Não é enfeite: obriga quem apresenta a declarar o público antes de mostrar
   qualquer número, e evita abrir uma tela técnica na frente da diretoria.
2. **Os módulos** (`/executivo/{modulo}`), no menu lateral, um por etapa do
   projeto.
3. **As subabas** (`/executivo/{modulo}/{subsecao}`), dentro do módulo. Trocadas
   por HTMX, então só o painel é substituído: a página não recarrega e o
   contexto da apresentação não se perde.

Rodar: uv run uvicorn app.main:app --reload
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import contexto, modulos

RAIZ = Path(__file__).resolve().parent
CLIENTE = "Trans Fictício BR"

app = FastAPI(title=f"Sala de Resultados · {CLIENTE}", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=RAIZ / "static"), name="static")

templates = Jinja2Templates(directory=RAIZ / "templates")
templates.env.filters["milhar"] = contexto.milhar
templates.env.filters["severidade"] = contexto.classe_severidade


def _base(request: Request) -> dict[str, Any]:
    """O que toda tela precisa: cliente, módulos e a carga de referência."""
    return {
        "request": request,
        "cliente": CLIENTE,
        "modulos": modulos.MODULOS,
        "entregues": modulos.entregues(),
        "apuracao": contexto.apuracao(),
    }


@app.get("/", response_class=HTMLResponse)
def entrada(request: Request) -> HTMLResponse:
    """A porta: escolha do público antes de qualquer número."""
    return templates.TemplateResponse(request, "entrada.html", _base(request))


@app.get("/executivo", response_class=HTMLResponse)
def executivo(request: Request) -> HTMLResponse:
    """A visão geral da apresentação executiva."""
    dados = _base(request)
    dados |= {"ativo": "inicio", "achados": contexto.achados()}
    return templates.TemplateResponse(request, "inicio.html", dados)


@app.get("/executivo/{chave}", response_class=HTMLResponse)
def modulo(request: Request, chave: str) -> HTMLResponse:
    """Abre um módulo na primeira subseção dele."""
    alvo = modulos.POR_CHAVE.get(chave)
    if alvo is None:
        return RedirectResponse("/executivo", status_code=303)  # type: ignore[return-value]
    if alvo.previsto:
        dados = _base(request) | {"ativo": chave, "modulo": alvo}
        return templates.TemplateResponse(request, "previsto.html", dados)
    return RedirectResponse(f"/executivo/{chave}/{alvo.inicial}", status_code=303)  # type: ignore[return-value]


@app.get("/executivo/{chave}/{subsecao}", response_class=HTMLResponse)
def subsecao(request: Request, chave: str, subsecao: str) -> HTMLResponse:
    """Uma subaba do módulo.

    Quando o pedido vem do HTMX, devolve **só o painel**; quando vem da barra de
    endereço ou de um F5, devolve a página inteira. É o que faz cada subaba ter
    URL própria (dá para mandar o link de uma tela específica) sem abrir mão da
    troca sem recarregar.
    """
    alvo = modulos.POR_CHAVE.get(chave)
    if alvo is None or alvo.previsto:
        return RedirectResponse("/executivo", status_code=303)  # type: ignore[return-value]

    atual = next((s for s in alvo.subsecoes if s.chave == subsecao), None)
    if atual is None:
        return RedirectResponse(f"/executivo/{chave}", status_code=303)  # type: ignore[return-value]

    dados = _base(request) | {
        "ativo": chave,
        "modulo": alvo,
        "subsecao": atual,
        "achados": contexto.achados(),
        "parcial": request.headers.get("HX-Request") == "true",
    }
    dados |= _dados_da_subsecao(atual.chave, request)
    return templates.TemplateResponse(request, f"modulos/m01/{atual.chave}.html", dados)


def _dados_da_subsecao(chave: str, request: Request) -> dict[str, Any]:
    """Carrega só o que a subaba pediu, e aplica os filtros que vieram na URL."""
    if chave == "fotografia":
        return {"inventario": contexto.apuracao()["inventario"]}

    if chave == "tratamento":
        linhas = contexto.texto_antes_depois()
        campo = request.query_params.get("campo", "")
        motivo = request.query_params.get("motivo", "")
        busca = request.query_params.get("busca", "").strip().lower()
        filtradas = [
            linha for linha in linhas
            if (not campo or linha["coluna"] == campo)
            and (not motivo or linha["motivo"] == motivo)
            and (not busca
                 or busca in linha["antes"].lower() or busca in linha["depois"].lower())
        ]
        return {
            "campos": sorted({linha["coluna"] for linha in linhas}),
            "motivos": sorted({linha["motivo"] for linha in linhas}),
            "filtro": {"campo": campo, "motivo": motivo, "busca": busca},
            "linhas": filtradas[:400],
            "total": len(filtradas),
            "registros": sum(int(linha["ocorrencias"]) for linha in filtradas),
        }

    if chave == "contas":
        return {"ausencias": contexto.ausencias()}

    if chave == "acoes":
        linhas = contexto.enderecos_duplicados()
        uf = request.query_params.get("uf", "")
        cidade = request.query_params.get("cidade", "").strip().lower()
        filtradas = [
            linha for linha in linhas
            if (not uf or linha["uf"] == uf)
            and (not cidade or cidade in linha["cidade"].lower())
        ]
        return {
            "ufs": sorted({linha["uf"] for linha in linhas if linha["uf"]}),
            "filtro": {"uf": uf, "cidade": cidade},
            "linhas": filtradas[:400],
            "total": len(filtradas),
            "grupos": len({linha["chave_endereco"] for linha in filtradas}),
        }

    return {}
