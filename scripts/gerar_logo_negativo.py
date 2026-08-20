"""Gera a versão do logo para fundo escuro.

O logo original tem o azul da marca (#284D70) como cor principal, o que o faz
sumir sobre o fundo azul do cabeçalho. A inversão troca **só o azul** por branco
e clareia o verde de apoio, preservando a forma, o alfa e a proporção. Não é um
logo novo: é o mesmo logo com a cor de tinta trocada, que é o que uma marca faz
quando vai para fundo escuro.
"""
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1] / "assets"

MARCA = (0x28, 0x4D, 0x70)     # azul: vira branco
APOIO = (0xA2, 0xBB, 0xB7)     # verde-cinza: clareia para manter o contraste
BRANCO = (0xFF, 0xFF, 0xFF)
APOIO_CLARO = (0xC9, 0xDC, 0xD8)


def distancia(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True)) ** 0.5


def inverter(origem: Path, destino: Path) -> None:
    imagem = Image.open(origem).convert("RGBA")
    saida = []
    for r, g, b, alfa in imagem.getdata():
        if alfa == 0:
            saida.append((r, g, b, alfa))
            continue
        # cada pixel vai para a cor nova mais próxima da sua cor de origem;
        # o anti-aliasing das bordas é interpolado para não serrilhar
        d_marca, d_apoio = distancia((r, g, b), MARCA), distancia((r, g, b), APOIO)
        alvo = BRANCO if d_marca <= d_apoio else APOIO_CLARO
        peso = min(1.0, (d_marca if alvo is BRANCO else d_apoio) / 140)
        novo = tuple(round(c * (1 - peso) + m * peso)
                     for c, m in zip(alvo, (r, g, b), strict=True))
        saida.append((*novo, alfa))

    nova = Image.new("RGBA", imagem.size)
    nova.putdata(saida)
    nova.save(destino)
    print(f"{destino.name}: {destino.stat().st_size / 1024:.0f} KB")


for nome in ("logo_tfb", "logo_tfb_icone"):
    inverter(RAIZ / f"{nome}.png", RAIZ / f"{nome}_negativo.png")
