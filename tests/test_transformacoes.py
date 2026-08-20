"""Cada regra do Silver testada no caso fácil e no caso que costuma quebrar."""

import pytest

from logistica_otif_mlops import transformacoes as t


class TestChaveComparacao:
    def test_reune_as_grafias_da_mesma_cidade(self) -> None:
        grafias = ["São Paulo", "SÃO PAULO", "Sao Paulo", "SAO PAULO", " são paulo "]
        assert len({t.chave_comparacao(g) for g in grafias}) == 1

    def test_nao_confunde_cidades_diferentes(self) -> None:
        assert t.chave_comparacao("Campinas") != t.chave_comparacao("Campina Grande")

    def test_nulo_vira_vazio(self) -> None:
        assert t.chave_comparacao(None) == ""


class TestNormalizarEspacos:
    def test_remove_das_pontas_e_colapsa_do_meio(self) -> None:
        assert t.normalizar_espacos("  Maria   Silva  ") == "Maria Silva"

    def test_texto_so_com_espaco_vira_ausencia(self) -> None:
        """Campo com espaço em branco não é preenchido: é vazio disfarçado."""
        assert t.normalizar_espacos("   ") is None

    def test_preserva_nulo(self) -> None:
        assert t.normalizar_espacos(None) is None


class TestCapitalizarNome:
    def test_caixa_alta_vira_nome_proprio(self) -> None:
        assert t.capitalizar_nome("CENTRO DE DISTRIBUICAO") == "Centro de Distribuicao"

    def test_particula_no_meio_fica_minuscula(self) -> None:
        assert t.capitalizar_nome("rua das flores") == "Rua das Flores"

    def test_particula_no_inicio_e_capitalizada(self) -> None:
        """"Do Vale Agregados" começa com partícula, e começo de nome é maiúsculo."""
        assert t.capitalizar_nome("do vale agregados") == "Do Vale Agregados"

    def test_sigla_permanece_em_caixa_alta(self) -> None:
        assert t.capitalizar_nome("transportes ltda") == "Transportes LTDA"
        assert t.capitalizar_nome("cd sp") == "CD SP"

    def test_preserva_acento_existente(self) -> None:
        assert t.capitalizar_nome("SÃO JOSÉ") == "São José"


class TestCanonizarVariantes:
    def test_acento_ganha_de_frequencia(self) -> None:
        """Digitar sem acento é o erro comum; ninguém acentua por engano."""
        de_para = t.canonizar_variantes(["Sao Paulo"] * 500 + ["São Paulo"] * 3)
        assert de_para["Sao Paulo"] == "São Paulo"

    def test_sem_acento_em_nenhuma_vence_a_mais_frequente(self) -> None:
        de_para = t.canonizar_variantes(["Campinas"] * 10 + ["CAMPINAS"] * 2)
        assert de_para["CAMPINAS"] == "Campinas"

    def test_grafia_unica_nao_entra_no_de_para(self) -> None:
        assert t.canonizar_variantes(["Santos", "Santos"]) == {}

    def test_nao_junta_cidades_diferentes(self) -> None:
        de_para = t.canonizar_variantes(["Campinas", "Campina Grande"])
        assert de_para == {}

    def test_eleicao_e_reproduzivel(self) -> None:
        """Rodar duas vezes tem que dar o mesmo resultado, ou o Silver não é determinístico."""
        valores = ["Sao Jose", "SAO JOSE", "Sao José", "São Jose"]
        assert t.canonizar_variantes(valores) == t.canonizar_variantes(reversed(valores))

    def test_ignora_nulo_e_vazio(self) -> None:
        de_para = t.canonizar_variantes([None, "  ", "Santos", "SANTOS"])
        assert de_para == {"SANTOS": "Santos"}


class TestNormalizarLogradouro:
    @pytest.mark.parametrize("entrada", ["R. das Flores, 100", "Rua das Flores, 100",
                                         "r. DAS FLORES, 100"])
    def test_abreviacao_e_extenso_convergem(self, entrada: str) -> None:
        assert t.normalizar_logradouro(entrada) == "Rua das Flores, 100"

    def test_avenida_abreviada(self) -> None:
        assert t.normalizar_logradouro("Av. Brasil, 50") == "Avenida Brasil, 50"

    def test_sem_abreviacao_apenas_capitaliza(self) -> None:
        assert t.normalizar_logradouro("ESTRADA VELHA") == "Estrada Velha"


class TestNormalizarDocumento:
    def test_com_e_sem_mascara_convergem(self) -> None:
        assert (t.normalizar_documento("12.345.678/0001-90")
                == t.normalizar_documento("12345678000190"))

    def test_preserva_zero_a_esquerda(self) -> None:
        assert t.normalizar_documento("01.234.567/0001-89") == "01234567000189"

    def test_texto_sem_digito_vira_nulo(self) -> None:
        assert t.normalizar_documento("não informado") is None


class TestNormalizarCep:
    def test_preserva_zero_a_esquerda(self) -> None:
        """O zero à esquerda é a razão de CEP ser texto: convertido a número, some."""
        assert t.normalizar_cep("01001-000") == "01001000"

    def test_completa_com_zeros_quando_vem_curto(self) -> None:
        assert t.normalizar_cep("1001000") == "01001000"

    def test_formatos_diferentes_convergem(self) -> None:
        assert t.normalizar_cep("88010-100") == t.normalizar_cep("88010100")
