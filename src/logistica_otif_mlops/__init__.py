"""logistica_otif_mlops — projeto de Ciência de Dados e MLOps (domínio logístico).

Pacote instalável que abriga os pipelines (medallion → modelo → operação) e a
camada de conectores de dados. Notebooks e scripts são consumidores finos:
eles importam este pacote e chamam suas funções — nunca reimplementam regra
nem abrem caminho de arquivo/credencial direto.
"""

__version__ = "0.1.0"


def main() -> None:
    """Ponto de entrada de linha de comando (placeholder).

    Vai evoluir para o CLI dos pipelines (ex.: `logistica-otif-mlops bronze`,
    `... treinar`, `... prever`), orquestrável por Makefile/CI.
    """
    print(f"logistica-otif-mlops v{__version__} — pipelines ainda não plugados.")
