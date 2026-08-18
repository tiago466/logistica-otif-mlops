"""Integridade dos CSVs de seed: a carteira congelada não pode regredir."""

import csv
from importlib.resources import files


def _ler(nome: str) -> list[dict[str, str]]:
    with files("logistica_otif_mlops.seed.dados").joinpath(nome).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_carteira_de_clientes_confere_com_a_anamnese() -> None:
    clientes = _ler("organizacoes_clientes.csv")
    assert len(clientes) == 203
    ativos = [c for c in clientes if c["ativo"] == "True"]
    assert len(ativos) == 98  # anamnese: carteira atual
    assert sum(1 for c in ativos if c["porte"] == "MEGA") == 7
    assert sum(1 for c in ativos if c["porte"] == "GRANDE") == 20
    siglas = [c["sigla"] for c in clientes]
    assert all(len(s) == 3 and s.isalpha() for s in siglas)
    assert len(set(siglas)) == 203


def test_narrativa_da_anamnese_esta_plantada() -> None:
    clientes = _ler("organizacoes_clientes.csv")
    nomes = {c["nome_fantasia"] for c in clientes}
    assert {"Woonka Chocolates", "Derma Health", "Stark Technologi"} <= nomes  # top 5
    assert sum(1 for c in clientes if c["perfil"] == "FIEL") == 10  # os amigos do dono
    anos_cancel = [c["dt_cancelamento"][:4] for c in clientes if c["dt_cancelamento"]]
    assert len(anos_cancel) == 105
    assert anos_cancel.count("2025") == 50  # a onda
    assert "2026" not in anos_cancel  # zero em 2026 (anamnese)
    assert all(c["dt_inicio_contrato"] < c["dt_cancelamento"]
               for c in clientes if c["dt_cancelamento"])
    # retenção desesperada: existem G/M cancelados em 2025 com contrato de 98%
    assert any(c["otif_contratual"] == "0.98" and c["dt_cancelamento"][:4] == "2025"
               for c in clientes)


def test_matriz_e_bases_conferem() -> None:
    rows = _ler("organizacoes_matriz_bases.csv")
    assert rows[0]["sigla"] == "TFB" and rows[0]["tipo_parceria"] == "MATRIZ"
    bases = [r for r in rows if r["tipo_parceria"] == "BASE"]
    assert len(bases) == 36
    sudeste = [b for b in bases if b["uf_sede"] in ("SP", "MG", "RJ", "ES")]
    assert len(sudeste) == 16
    vilas = [b["sigla"] for b in bases if b["nivel_infra"] == "BAIXA"]
    assert len(vilas) == 5


def test_cidades_e_gabarito_conferem() -> None:
    cidades = _ler("cidades.csv")
    assert len(cidades) >= 60
    assert all(len(c["uf"]) == 2 and int(c["peso"]) > 0 for c in cidades)
    sudeste = sum(int(c["peso"]) for c in cidades if c["uf"] in ("SP", "MG", "RJ", "ES"))
    total = sum(int(c["peso"]) for c in cidades)
    assert sudeste / total > 0.5  # anamnese: concentração Sudeste

    gabarito = _ler("gabarito_clientes.csv")
    clientes = {c["sigla"] for c in _ler("organizacoes_clientes.csv")}
    assert {g["sigla"] for g in gabarito} == clientes  # 1:1 com a carteira
    stark = next(g for g in gabarito if g["sigla"] == "STK")
    assert float(stark["pct_exclusivo"]) > 0.05  # anamnese: Stark abusa do exclusivo


def test_gabarito_preserva_a_economia_da_anamnese() -> None:
    """Guarda da narrativa: o topo compra barato e custa caro; a cauda, o inverso.

    A resposta da Dna. Sarah nasce dessa assimetria (`fator_preco` × `fator_custo`).
    Se uma regeração acidental achatar os fatores, o case perde o enredo, e é
    melhor o teste avisar antes de o dado virar relatório.
    """
    gabarito = {g["sigla"]: g for g in _ler("gabarito_clientes.csv")}
    porte = {c["sigla"]: c["porte"] for c in _ler("organizacoes_clientes.csv")
             if c["ativo"] == "True"}

    def margem(sigla: str) -> float:
        g = gabarito[sigla]
        return float(g["fator_preco"]) / float(g["fator_custo"])

    topo = [margem(s) for s, p in porte.items() if p in ("MEGA", "GRANDE")]
    cauda = [margem(s) for s, p in porte.items() if p in ("MICRO", "PEQUENA", "MEDIA")]
    assert topo and cauda
    assert sum(topo) / len(topo) < 0.7 * (sum(cauda) / len(cauda))
    assert all(float(g["fator_preco"]) > 0 and float(g["fator_custo"]) > 0
               for g in gabarito.values())


def test_siglas_nao_colidem_entre_carteira_e_bases() -> None:
    clientes = {c["sigla"] for c in _ler("organizacoes_clientes.csv")}
    mb = {r["sigla"] for r in _ler("organizacoes_matriz_bases.csv")}
    assert not clientes & mb
