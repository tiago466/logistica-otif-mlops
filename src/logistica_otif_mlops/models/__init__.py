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
from logistica_otif_mlops.models.movimento import (
    Coleta,
    Entrega,
    EstoqueSnapshot,
    Minuta,
    Ocorrencia,
    OrdemColeta,
    Pedido,
    PedidoFase,
    PedidoItem,
    Positivacao,
    Recebimento,
    RetiradaBase,
)

__all__ = [
    "Campanha",
    "Coleta",
    "Endereco",
    "Entrega",
    "EstoqueSnapshot",
    "Fase",
    "Item",
    "LeadTime",
    "LocalEstoque",
    "Minuta",
    "Modalidade",
    "Ocorrencia",
    "OrdemColeta",
    "Organizacao",
    "Pedido",
    "PedidoFase",
    "PedidoItem",
    "Positivacao",
    "Recebimento",
    "RetiradaBase",
    "Rota",
    "TipoOcorrencia",
    "Transportador",
    "Veiculo",
]
