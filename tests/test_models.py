"""Fumaça dos models: o código deve espelhar o MER congelado (docs/02)."""

import logistica_otif_mlops.models  # noqa: F401  # registra as tabelas
from logistica_otif_mlops.db import Base

CADASTRO_ESPERADO = {
    "organizacao",
    "endereco",
    "item",
    "local_estoque",
    "transportador",
    "veiculo",
    "rota",
}

CONFIGURACAO_ESPERADO = {
    "modalidade",
    "lead_time",
    "campanha",
    "fase",
    "tipo_ocorrencia",
}

MOVIMENTO_ESPERADO = {
    "pedido",
    "pedido_item",
    "pedido_fase",
    "ordem_coleta",
    "minuta",
    "entrega",
    "retirada_base",
    "ocorrencia",
    "recebimento",
    "estoque_snapshot",
    "coleta",
    "positivacao",
}


def test_grupo_cadastro_completo_no_schema_operacao() -> None:
    operacao = {t.name for t in Base.metadata.tables.values() if t.schema == "operacao"}
    assert operacao >= CADASTRO_ESPERADO


def test_grupo_configuracao_completo_no_schema_operacao() -> None:
    operacao = {t.name for t in Base.metadata.tables.values() if t.schema == "operacao"}
    assert operacao >= CONFIGURACAO_ESPERADO


def test_grupo_movimento_completo_e_operacao_fechado_em_24() -> None:
    operacao = {t.name for t in Base.metadata.tables.values() if t.schema == "operacao"}
    assert operacao >= MOVIMENTO_ESPERADO
    assert len(operacao) == 24  # o MER congelado: nada a mais, nada a menos


def test_pedido_nao_armazena_flag_de_atraso() -> None:
    """Doutrina: derivado se calcula. O alvo do OTIF nasce do cruzamento, nunca de coluna."""
    pedido = Base.metadata.tables["operacao.pedido"]
    colunas = set(pedido.columns.keys())
    assert not {c for c in colunas if "atraso" in c}


def test_lead_time_e_regua_sem_referencia_a_pedido() -> None:
    """A regua parametriza; pedido carimba. Regressao da 'recaida' de modelagem."""
    lead_time = Base.metadata.tables["operacao.lead_time"]
    assert "pedido_id" not in lead_time.columns


def test_constraints_nomeadas_pela_convencao() -> None:
    org = Base.metadata.tables["operacao.organizacao"]
    nomes = {c.name for c in org.constraints}
    assert "pk_organizacao" in nomes
    assert "ck_organizacao_tipo_parceria_valido" in nomes
