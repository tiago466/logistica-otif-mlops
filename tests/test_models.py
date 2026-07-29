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


def test_grupo_cadastro_completo_no_schema_operacao() -> None:
    operacao = {t.name for t in Base.metadata.tables.values() if t.schema == "operacao"}
    assert operacao >= CADASTRO_ESPERADO


def test_constraints_nomeadas_pela_convencao() -> None:
    org = Base.metadata.tables["operacao.organizacao"]
    nomes = {c.name for c in org.constraints}
    assert "pk_organizacao" in nomes
    assert "ck_organizacao_tipo_parceria_valido" in nomes
