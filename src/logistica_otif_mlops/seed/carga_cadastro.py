"""Seed módulo 1: organizações, endereços-sede e locais de estoque.

Lê os CSVs versionados em `seed/dados/` e carrega, NESTA ordem (o id 1 é a
matriz, decisão do Tiago): Trans Fictício BR → 36 bases → 203 clientes. Cria o
endereço-sede de cada organização e os locais de estoque (4 galpões da matriz
+ 1 depósito por base). Determinístico (semente fixa) e idempotente (aborta
se já houver organizações).

Rodar: uv run python -m logistica_otif_mlops.seed.carga_cadastro
"""

from __future__ import annotations

import csv
import random
from datetime import date
from decimal import Decimal
from importlib.resources import files

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from logistica_otif_mlops.db import criar_engine, criar_fabrica_de_sessoes
from logistica_otif_mlops.models import Endereco, LocalEstoque, Organizacao

SEMENTE = 20260730

# distribuição de sedes dos clientes (Sudeste-pesada, como a economia real)
CIDADES_SEDE: list[tuple[str, str, int]] = [  # (cidade, uf, peso)
    ("São Paulo", "SP", 30), ("Campinas", "SP", 8), ("Barueri", "SP", 6),
    ("Jundiaí", "SP", 4), ("São Bernardo do Campo", "SP", 4),
    ("Belo Horizonte", "MG", 8), ("Uberlândia", "MG", 3),
    ("Rio de Janeiro", "RJ", 10), ("Curitiba", "PR", 5),
    ("Porto Alegre", "RS", 4), ("Florianópolis", "SC", 3), ("Joinville", "SC", 2),
    ("Salvador", "BA", 3), ("Recife", "PE", 3), ("Fortaleza", "CE", 2),
    ("Brasília", "DF", 3), ("Goiânia", "GO", 2),
]
LOGRADOUROS = ["Av. Industrial", "Rua das Acácias", "Av. Brasil", "Rua do Comércio",
               "Av. das Nações", "Rua Projetada", "Rod. Anhanguera, km", "Av. Paulista"]


def _bool(v: str) -> bool | None:
    if v in ("", None):
        return None
    return v == "True"


def _data(v: str) -> date | None:
    return date.fromisoformat(v) if v else None


def _ler_csv(nome: str) -> list[dict[str, str]]:
    caminho = files("logistica_otif_mlops.seed.dados").joinpath(nome)
    with caminho.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _endereco_sede(rng: random.Random, org: Organizacao, cidade: str, uf: str) -> Endereco:
    # sujeira LEVE e proposital de cadastro: parte das cidades entra em CAIXA ALTA
    cidade_gravada = cidade.upper() if rng.random() < 0.25 else cidade
    return Endereco(
        organizacao_id=org.id,
        nome_local=f"Sede {org.nome_fantasia}",
        documento=org.cnpj,
        logradouro=f"{rng.choice(LOGRADOUROS)} {rng.randint(10, 4999)}",
        bairro=rng.choice(["Centro", "Distrito Industrial", "Vila Nova", "Jardim América"]),
        cidade=cidade_gravada,
        uf=uf,
        cep=f"{rng.randint(1000000, 9999999):07d}0",
        fl_principal=True,
    )


def executar() -> None:
    engine = criar_engine()
    fabrica = criar_fabrica_de_sessoes(engine)
    rng = random.Random(SEMENTE)
    with fabrica() as sessao:
        ja_tem = sessao.scalar(select(func.count(Organizacao.id)))
        if ja_tem:
            print(f"seed cadastro: banco já tem {ja_tem} organizações; nada a fazer.")
            return
        _carregar(sessao, rng)
        sessao.commit()
        _relatorio(sessao)


def _carregar(sessao: Session, rng: random.Random) -> None:
    # 1) matriz + bases (a ordem do CSV garante TFB primeiro → id 1)
    for linha in _ler_csv("organizacoes_matriz_bases.csv"):
        org = Organizacao(
            sigla=linha["sigla"],
            razao_social=linha["razao_social"],
            nome_fantasia=linha["nome_fantasia"],
            cnpj=linha["cnpj"],
            tipo_parceria=linha["tipo_parceria"],
            porte=linha["porte"] or None,
            segmento=linha["segmento"] or None,
            fl_entrega_agendada=_bool(linha["fl_entrega_agendada"]),
            dt_inicio_contrato=_data(linha["dt_inicio_contrato"]) or date(2016, 1, 4),
            dt_cancelamento=_data(linha["dt_cancelamento"]),
            ativo=linha["ativo"] == "True",
        )
        sessao.add(org)
        sessao.flush()  # materializa org.id para os filhos
        sessao.add(_endereco_sede(rng, org, linha["cidade_sede"], linha["uf_sede"]))
        if org.tipo_parceria == "MATRIZ":
            for n in range(1, 5):
                sessao.add(LocalEstoque(organizacao_id=org.id, codigo=f"TB{n}", nome=f"Galpão {n}"))
        else:
            sessao.add(
                LocalEstoque(
                    organizacao_id=org.id,
                    codigo=org.sigla,
                    nome=f"Depósito {linha['cidade_sede']}",
                )
            )

    # 2) clientes (sede sorteada com pesos Sudeste; determinístico)
    cidades = [c for c in CIDADES_SEDE for _ in range(c[2])]
    for linha in _ler_csv("organizacoes_clientes.csv"):
        org = Organizacao(
            sigla=linha["sigla"],
            razao_social=linha["razao_social"],
            nome_fantasia=linha["nome_fantasia"],
            cnpj=linha["cnpj"],
            tipo_parceria="CLIENTE",
            porte=linha["porte"],
            segmento=linha["segmento"],
            fl_entrega_agendada=_bool(linha["fl_entrega_agendada"]),
            dt_inicio_contrato=_data(linha["dt_inicio_contrato"]) or date(2019, 1, 1),
            dt_cancelamento=_data(linha["dt_cancelamento"]),
            # coluna "perfil" do CSV é gabarito do gerador, NÃO vai ao banco
            otif_contratual=(
                Decimal(linha["otif_contratual"]) if linha.get("otif_contratual") else None
            ),
            ativo=linha["ativo"] == "True",
        )
        sessao.add(org)
        sessao.flush()
        cidade, uf, _ = rng.choice(cidades)
        sessao.add(_endereco_sede(rng, org, cidade, uf))


def _relatorio(sessao: Session) -> None:
    orgs = sessao.scalar(select(func.count(Organizacao.id)))
    ends = sessao.scalar(select(func.count(Endereco.id)))
    locais = sessao.scalar(select(func.count(LocalEstoque.id)))
    matriz = sessao.scalar(select(Organizacao.nome_fantasia).where(Organizacao.id == 1))
    print(f"seed cadastro OK: {orgs} organizações · {ends} endereços · {locais} locais de estoque")
    print(f"id 1 = {matriz} (como manda o figurino)")


if __name__ == "__main__":
    executar()
