"""Contrato da API financeira: porteiro, paginação e limites.

Os testes de autenticação e validação **não tocam no banco** (a rejeição
acontece antes), então rodam na CI sem Postgres. Os que precisam de dados são
marcados e pulam sozinhos quando não há banco configurado.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from logistica_otif_mlops.api_custos import main
from logistica_otif_mlops.config import obter_settings

CHAVE = "chave-de-teste"


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        main, "obter_settings",
        lambda: SimpleNamespace(custos_api_key=CHAVE, custos_api_database_url=None,
                                database_url=None))
    return TestClient(main.app)


def test_saude_nao_exige_chave(cliente: TestClient) -> None:
    # é o endpoint que o provedor consulta para saber se o serviço subiu
    assert cliente.get("/saude").status_code == 200


def test_sem_chave_recusa(cliente: TestClient) -> None:
    resposta = cliente.get("/v1/faturamentos")
    assert resposta.status_code == 401


def test_chave_errada_recusa(cliente: TestClient) -> None:
    resposta = cliente.get("/v1/faturamentos", headers={"X-API-Key": "outra"})
    assert resposta.status_code == 401


def test_mensagem_de_erro_nao_entrega_pista(cliente: TestClient) -> None:
    """A resposta não pode dizer se a chave existe, nem devolver a esperada."""
    detalhe = cliente.get("/v1/faturamentos", headers={"X-API-Key": "outra"}).json()
    assert CHAVE not in str(detalhe)
    assert "invalida" in detalhe["detail"].lower()


def test_sem_chave_configurada_o_servico_se_recusa_a_servir(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Servidor sem segredo definido não abre a porta: falha fechada, não aberta."""
    monkeypatch.setattr(
        main, "obter_settings",
        lambda: SimpleNamespace(custos_api_key=None, custos_api_database_url=None,
                                database_url=None))
    resposta = TestClient(main.app).get("/v1/faturamentos", headers={"X-API-Key": "x"})
    assert resposta.status_code == 503


def test_limite_acima_do_maximo_e_rejeitado(cliente: TestClient) -> None:
    resposta = cliente.get("/v1/faturamentos?limite=999999",
                           headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 422  # validado antes de chegar ao banco


def test_competencia_em_formato_invalido_e_rejeitada(cliente: TestClient) -> None:
    resposta = cliente.get("/v1/faturamentos?competencia=junho/2026",
                           headers={"X-API-Key": CHAVE})
    assert resposta.status_code == 422


@pytest.mark.skipif(not obter_settings().database_url,
                    reason="precisa de banco carregado")
def test_pagina_devolve_envelope_completo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com banco real: o envelope precisa dizer o total, senão ninguém pagina."""
    cfg = obter_settings()
    monkeypatch.setattr(
        main, "obter_settings",
        lambda: SimpleNamespace(custos_api_key=CHAVE,
                                custos_api_database_url=cfg.database_url,
                                database_url=cfg.database_url))
    corpo = TestClient(main.app).get(
        "/v1/faturamentos?limite=2", headers={"X-API-Key": CHAVE}).json()
    assert {"total", "limite", "deslocamento", "itens"} <= corpo.keys()
    assert len(corpo["itens"]) <= 2
    assert corpo["total"] >= len(corpo["itens"])
