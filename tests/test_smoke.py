"""Testes de fumaça — garantem que o esqueleto está de pé e importável.

Crescem junto com o projeto: cada regra de negócio nova nasce com o seu teste
(a "engenharia forte" que diferencia o portfólio).
"""

from logistica_otif_mlops import __version__
from logistica_otif_mlops.config import obter_settings
from logistica_otif_mlops.connectors import obter
from logistica_otif_mlops.connectors.registry import nomes_registrados


def test_versao_definida() -> None:
    assert __version__


def test_settings_carrega_com_ambiente_padrao() -> None:
    settings = obter_settings()
    assert settings.ambiente in {"dev", "hmlg", "prod"}


def test_conector_desconhecido_da_erro_autoexplicativo() -> None:
    """Pedir um conector inexistente deve falhar com mensagem útil."""
    try:
        obter("nao_existe")
    except KeyError as exc:
        assert "não registrado" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("esperava KeyError para conector inexistente")


def test_registro_comeca_vazio() -> None:
    # Nenhum adaptador concreto ainda — nascem sob demanda.
    assert nomes_registrados() == []
