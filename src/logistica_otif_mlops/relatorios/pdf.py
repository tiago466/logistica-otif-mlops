"""Exporta os relatórios em PDF, usando o mecanismo de impressão do navegador.

Por que navegador e não uma biblioteca de PDF: o `@media print` do CSS já descreve
o documento impresso (A4, margens, quebra de página controlada, cabeçalho de
tabela repetido). Um gerador próprio de PDF ignoraria essa folha de estilo e nos
obrigaria a manter **dois** desenhos do mesmo documento, que divergiriam na
primeira mudança. O navegador usa exatamente o mesmo CSS que o cliente vê na tela.

A busca pelo executável tenta o Linux primeiro e só depois recorre ao navegador do
Windows via WSL. Assim o mesmo comando funciona na estação de desenvolvimento e
num servidor sem interface, onde só existe o Chromium.

Rodar: uv run python -m logistica_otif_mlops.relatorios.pdf
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

CANDIDATOS = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    # estação de desenvolvimento: WSL enxerga o navegador do Windows
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)

PAGINAS = ("executivo", "tecnico")


def executar() -> None:
    from logistica_otif_mlops.relatorios import DESTINO

    navegador = _encontrar()
    if navegador is None:
        raise SystemExit(
            "Nenhum navegador encontrado para gerar o PDF.\n"
            "Instale o Chromium (`sudo apt install chromium-browser`) ou abra o HTML "
            "e use Ctrl+P, que produz o mesmo resultado."
        )

    print(f"== pdf == ({Path(navegador).name})")
    for nome in PAGINAS:
        origem = DESTINO / f"{nome}.html"
        if not origem.exists():
            raise SystemExit(f"{origem} não existe. Gere os relatórios antes:\n"
                             "  uv run python -m logistica_otif_mlops.relatorios")
        destino = DESTINO / f"{nome}.pdf"
        _imprimir(navegador, origem, destino)
        print(f"  {destino.name:<16} {destino.stat().st_size / 1024:>7.0f} KB")

    print(f"\nOK: {DESTINO}")


def _encontrar() -> str | None:
    for candidato in CANDIDATOS:
        if candidato.startswith("/"):
            if Path(candidato).exists():
                return candidato
        elif (achado := shutil.which(candidato)) is not None:
            return achado
    return None


def _imprimir(navegador: str, origem: Path, destino: Path) -> None:
    """Roda o navegador em modo headless e grava o PDF."""
    windows = navegador.startswith("/mnt/c/")
    with tempfile.TemporaryDirectory() as perfil:
        comando = [
            navegador,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            # o cabeçalho e o rodapé do navegador (URL, data, número de página)
            # não pertencem a um documento de cliente: o rodapé já é nosso
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={_caminho(destino, windows)}",
            f"--user-data-dir={_caminho(Path(perfil), windows)}",
            _url(origem, windows),
        ]
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)

    if not destino.exists() or destino.stat().st_size == 0:
        raise SystemExit(f"O navegador não gerou {destino.name}.\n{resultado.stderr[-800:]}")


def _caminho(caminho: Path, windows: bool) -> str:
    """Converte para caminho do Windows quando o navegador é o do Windows."""
    if not windows:
        return str(caminho)
    return subprocess.run(["wslpath", "-w", str(caminho)],
                          capture_output=True, text=True, check=True).stdout.strip()


def _url(caminho: Path, windows: bool) -> str:
    """Monta a URI do arquivo.

    `Path.as_uri()` não serve para o caminho do Windows: rodando no Linux, um
    `\\\\wsl.localhost\\...` é lido como caminho relativo e a conversão falha. Como o
    caminho pode ser tanto UNC quanto letra de unidade, a URI é montada à mão.
    """
    if not windows:
        return caminho.as_uri()
    bruto = _caminho(caminho, windows).replace("\\", "/")
    return f"file:{bruto}" if bruto.startswith("//") else f"file:///{bruto}"


if __name__ == "__main__":
    executar()
