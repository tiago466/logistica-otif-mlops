"""Seed módulo 2 (G1): o MUNDO ESTÁTICO da Trans Fictício BR.

Cria tudo que existe antes do tempo correr: transportadores e frota, rotas,
a régua de LEAD_TIME (modalidade × UF × cidade), catálogo de itens por cliente,
rede de destinatários/endereços e tarifas de armazenagem. Determinístico e
idempotente. Volumes vêm do gabarito (`gabarito_clientes.csv`).

Rodar: uv run python -m logistica_otif_mlops.seed.carga_mundo
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
from logistica_otif_mlops.models import (
    Campanha,
    Endereco,
    Item,
    LeadTime,
    Modalidade,
    Organizacao,
    Rota,
    TarifaArmazenagem,
    Transportador,
    Veiculo,
)

SEMENTE = 20260801

# dias úteis de lead time rodoviário por UF (partindo da matriz em SC);
# aéreo = ~metade (mínimo 1). Cidades-capital ganham 1 dia a menos no rodoviário.
DIAS_RODOV_UF = {
    "SC": 1, "PR": 2, "RS": 2, "SP": 3, "RJ": 4, "MG": 4, "ES": 4,
    "MS": 5, "GO": 5, "DF": 5, "MT": 6, "BA": 6, "SE": 7, "AL": 7,
    "PE": 8, "PB": 8, "RN": 8, "CE": 8, "PI": 9, "MA": 9, "TO": 7,
    "PA": 9, "AP": 12, "AM": 10, "RR": 12, "RO": 9, "AC": 11,
}
CAPITAIS = {
    "Florianópolis", "Curitiba", "Porto Alegre", "São Paulo", "Rio de Janeiro",
    "Belo Horizonte", "Vitória", "Campo Grande", "Goiânia", "Brasília", "Cuiabá",
    "Salvador", "Aracaju", "Maceió", "Recife", "João Pessoa", "Natal", "Fortaleza",
    "Teresina", "São Luís", "Palmas", "Belém", "Macapá", "Manaus", "Boa Vista",
    "Porto Velho", "Rio Branco",
}

GRUPOS_POR_SEGMENTO = {
    "ALIMENTICIO": [("MATERIAL PROMOCIONAL", "DISPLAY"), ("PRODUTO", "CHOCOLATE"),
                    ("MATERIAL PROMOCIONAL", "BANNER"), ("BRINDE", "KIT")],
    "COSMETICOS_DERMATOLOGICOS": [("AMOSTRA", "DERMO"), ("MATERIAL PROMOCIONAL", "BANNER"),
                                  ("PRODUTO", "COSMETICO"), ("BRINDE", "NECESSAIRE")],
    "ELETRONICOS": [("PRODUTO", "ACESSORIO"), ("MATERIAL PROMOCIONAL", "DISPLAY"),
                    ("PRODUTO", "GADGET"), ("BRINDE", "KIT")],
    "AGRICOLA": [("PRODUTO", "INSUMO"), ("MATERIAL PROMOCIONAL", "BANNER"),
                 ("PRODUTO", "EMBALADO")],
}
GRUPOS_PADRAO = [("MATERIAL PROMOCIONAL", "BANNER"), ("MATERIAL PROMOCIONAL", "PANFLETO"),
                 ("AMOSTRA", "SACHE"), ("BRINDE", "KIT"), ("PRODUTO", "EMBALADO")]
NOMES_ITEM = ["CAMISETA", "BANNER", "DISPLAY DE BALCAO", "KIT LANCAMENTO", "AMOSTRA",
              "CAIXA EXPOSITORA", "FOLDER", "MOSTRUARIO", "BRINDE VIP", "CARTAZ"]


def _ler(nome: str) -> list[dict[str, str]]:
    with files("logistica_otif_mlops.seed.dados").joinpath(nome).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def executar() -> None:
    engine = criar_engine()
    fabrica = criar_fabrica_de_sessoes(engine)
    rng = random.Random(SEMENTE)
    with fabrica() as sessao:
        if sessao.scalar(select(func.count(Item.id))):
            print("seed mundo: catálogo já existe; nada a fazer.")
            return
        _transportadores(sessao, rng)
        _rotas(sessao)
        _lead_times(sessao)
        _catalogo_e_destinatarios(sessao, rng)
        _tarifas(sessao, rng)
        _campanhas(sessao)
        sessao.commit()
        _relatorio(sessao)


def _transportadores(sessao: Session, rng: random.Random) -> None:
    frota = Transportador(nome="Trans Fictício BR Frota Própria", cnpj=None, tipo="FROTA_PROPRIA")
    sessao.add(frota)
    sessao.flush()
    tipos_veic = ["fiorino", "vuc", "truck", "carreta"]
    caps = {"fiorino": 600, "vuc": 3000, "truck": 12000, "carreta": 27000}
    for i in range(26):
        tv = rng.choice(tipos_veic)
        sessao.add(Veiculo(transportador_id=frota.id, placa=f"TFB{i:02d}{rng.randint(10, 99)}",
                           tipo_veiculo=tv, capacidade_kg=Decimal(caps[tv])))
    empresas = [
        ("TransLancer Cargas", 12), ("Rota Sul Express", 8), ("Aliança Rodoviária", 9),
        ("Vale Verde Fretes", 6), ("Litoral Cargo", 5), ("Azul Aéreo Cargas", 0),
    ]
    for nome, n_veic in empresas:
        cnpj = "".join(str(rng.randint(0, 9)) for _ in range(14))
        t = Transportador(nome=nome, cnpj=cnpj, tipo="TRANSPORTADORA")
        sessao.add(t)
        sessao.flush()
        for i in range(n_veic):
            tv = rng.choice(tipos_veic[1:])
            placa = f"{nome[:2].upper()}{i}{rng.randint(100, 999)}"
            sessao.add(Veiculo(transportador_id=t.id, placa=placa,
                               tipo_veiculo=tv, capacidade_kg=Decimal(caps[tv])))
    nomes_free = ["Marcos Silva Transportes", "JC Fretes", "Do Vale Agregados", "Pereira Cargas",
                  "Irmãos Souza", "R. Lima Transporte", "Naldo Fretes", "Sampaio Cargas",
                  "W. Costa Agregado", "Zanella Fretes", "Trans Nakamura", "Beto Carreteiro"]
    for k, nome in enumerate(nomes_free):
        tipo = "CARRETEIRO" if k % 2 == 0 else "AGREGADO"
        t = Transportador(nome=nome, cnpj=None if tipo == "CARRETEIRO" else
                          "".join(str(rng.randint(0, 9)) for _ in range(14)), tipo=tipo)
        sessao.add(t)
        sessao.flush()
        tv = "carreta" if "Marcos" in nome else rng.choice(tipos_veic[1:3])
        sessao.add(Veiculo(transportador_id=t.id, placa=f"FRE{k}{rng.randint(100, 999)}",
                           tipo_veiculo=tv, capacidade_kg=Decimal(caps[tv])))


def _rotas(sessao: Session) -> None:
    ufs = sorted({uf for _, uf in [(c["cidade"], c["uf"]) for c in _ler("cidades.csv")]})
    for uf in ufs:
        sessao.add(Rota(codigo=f"R-{uf}", descricao=f"Corredor {uf}", uf=uf))
    sessao.add(Rota(codigo="R-LOCAL", descricao="Distribuição local Santa Catarina", uf="SC"))


def _lead_times(sessao: Session) -> None:
    modais = {m.codigo: m.id for m in sessao.scalars(select(Modalidade)).all()}
    for c in _ler("cidades.csv"):
        base = DIAS_RODOV_UF[c["uf"]]
        rodov = max(1, base - (1 if c["cidade"] in CAPITAIS else 0))
        aereo = max(1, round(rodov / 2))
        sessao.add(LeadTime(modalidade_id=modais["RODOVIARIO"], uf=c["uf"],
                            cidade=c["cidade"], dias_uteis=rodov))
        sessao.add(LeadTime(modalidade_id=modais["AEREO"], uf=c["uf"],
                            cidade=c["cidade"], dias_uteis=aereo))


def _catalogo_e_destinatarios(sessao: Session, rng: random.Random) -> None:
    gabarito = {g["sigla"]: g for g in _ler("gabarito_clientes.csv")}
    cidades = _ler("cidades.csv")
    pesos = [int(c["peso"]) for c in cidades]
    clientes = sessao.scalars(
        select(Organizacao).where(Organizacao.tipo_parceria == "CLIENTE")
    ).all()
    for org in clientes:
        g = gabarito[org.sigla]
        grupos = GRUPOS_POR_SEGMENTO.get(org.segmento or "", GRUPOS_PADRAO)
        for i in range(int(g["n_itens"])):
            grupo, subgrupo = rng.choice(grupos)
            # ~5% dos itens SEM valor unitário: o furo de cobertura fiscal
            valor = None if rng.random() < 0.05 else Decimal(f"{rng.uniform(2, 380):.2f}")
            desc = f"{rng.choice(NOMES_ITEM)} {org.nome_fantasia.upper()} {rng.randint(1, 99)}"
            sessao.add(Item(
                cliente_id=org.id,
                codigo=f"{org.sigla}{grupo[:1]}{i:04d}",
                descricao=desc,
                grupo=grupo, subgrupo=subgrupo,
                peso_kg=Decimal(f"{rng.uniform(0.05, 18):.3f}"),
                volume_m3=Decimal(f"{rng.uniform(0.0005, 0.3):.4f}"),
                valor_unitario=valor,
            ))
        for _ in range(int(g["n_destinatarios"])):
            cid = rng.choices(cidades, weights=pesos, k=1)[0]
            nome_dest = rng.choice(
                ["Farmácia", "Distribuidora", "Loja", "Atacado", "Mercado", "Clínica",
                 "Centro de Distribuição", "Consultório"]
            ) + f" {rng.choice(['Central', 'Popular', 'do Vale', 'Norte', 'Sul', 'Real', 'Ideal'])}"
            # sujeira proposital: parte em CAIXA ALTA, parte sem documento
            if rng.random() < 0.3:
                nome_dest = nome_dest.upper()
            sessao.add(Endereco(
                organizacao_id=org.id,
                nome_local=nome_dest,
                documento=None if rng.random() < 0.2 else
                "".join(str(rng.randint(0, 9)) for _ in range(14)),
                logradouro=(
                    f"Rua {rng.choice(['das Flores', 'XV de Novembro', 'Brasil', 'Projetada'])}"
                    f", {rng.randint(10, 4999)}"
                ),
                bairro=rng.choice(["Centro", "Industrial", "Jardim", "Vila Nova"]),
                cidade=cid["cidade"].upper() if rng.random() < 0.25 else cid["cidade"],
                uf=cid["uf"],
                cep=f"{rng.randint(1000000, 9999999):07d}0",
                fl_principal=False,
            ))


def _tarifas(sessao: Session, rng: random.Random) -> None:
    gabarito = {g["sigla"]: g for g in _ler("gabarito_clientes.csv")}
    minimo_por_porte = {"MEGA": 2500, "GRANDE": 1500, "MEDIA": 800, "PEQUENA": 400, "MICRO": 250}
    clientes = sessao.scalars(
        select(Organizacao).where(Organizacao.tipo_parceria == "CLIENTE")
    ).all()
    for org in clientes:
        g = gabarito[org.sigla]
        if g["estoca"] != "True":
            continue
        fator = float(g["fator_preco"])  # o desconto oculto também morde a armazenagem
        # faixa calibrada pela régua da Sarah (armazenagem ~R$175k/mês em jun/2026,
        # já com a política de aging vigente multiplicando o estoque parado)
        sessao.add(TarifaArmazenagem(
            cliente_sigla=org.sigla,
            valor_m3=Decimal(f"{rng.uniform(8.7, 14.2) * fator:.2f}"),
            aliquota_ad_valorem=Decimal(f"{rng.uniform(0.001, 0.005):.4f}"),
            valor_minimo_mensal=Decimal(minimo_por_porte[org.porte or "MEDIA"]),
        ))


def _campanhas(sessao: Session) -> None:
    """Calendário comercial: as ondas que já movem os volumes ganham nome.

    As mesmas datas alimentam o BOOST_SEGMENTO da G2 (anamnese Q10): Páscoa é
    do alimentício, Dia das Mães de moda/beleza, Black Friday da eletrônica.
    """
    janelas = [
        ("Páscoa", (2, 20), (4, 10)),
        ("Dia das Mães", (4, 5), (5, 12)),
        ("Dia dos Namorados", (5, 15), (6, 12)),
        ("Dia das Crianças", (9, 5), (10, 12)),
        ("Black Friday", (10, 25), (11, 30)),
        ("Natal", (11, 20), (12, 24)),
    ]
    for ano in range(2016, 2027):
        for nome, (mi, di), (mf, df) in janelas:
            sessao.add(Campanha(descricao=f"{nome} {ano}",
                                dt_inicio=date(ano, mi, di), dt_fim=date(ano, mf, df)))


def _relatorio(sessao: Session) -> None:
    def contar(modelo: type) -> int:
        return int(sessao.scalar(select(func.count()).select_from(modelo)) or 0)

    print("seed mundo OK:")
    print(f"  transportadores: {contar(Transportador)} · veículos: {contar(Veiculo)}")
    print(f"  rotas: {contar(Rota)} · lead_times: {contar(LeadTime)}")
    print(f"  itens: {contar(Item)} · endereços (sedes+destinos): {contar(Endereco)}")
    print(f"  tarifas de armazenagem: {contar(TarifaArmazenagem)}")


if __name__ == "__main__":
    executar()
