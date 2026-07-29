"""Models do banco da TransBrasil, espelho 1:1 do MER congelado (docs/02).

Organizados pelos grupos do MER: cadastro, configuração, movimento (schema
`operacao`) e financeiro (schema `custos`). Importar todos aqui registra as
tabelas na metadata da `Base`, o que alimenta o autogenerate do Alembic.
"""

from logistica_otif_mlops.models.cadastro import (
    Endereco,
    Item,
    LocalEstoque,
    Organizacao,
    Rota,
    Transportador,
    Veiculo,
)
from logistica_otif_mlops.models.configuracao import (
    Campanha,
    Fase,
    LeadTime,
    Modalidade,
    TipoOcorrencia,
)

__all__ = [
    "Campanha",
    "Endereco",
    "Fase",
    "Item",
    "LeadTime",
    "LocalEstoque",
    "Modalidade",
    "Organizacao",
    "Rota",
    "TipoOcorrencia",
    "Transportador",
    "Veiculo",
]
