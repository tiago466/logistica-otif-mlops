"""Grupo CADASTRO do schema `operacao`: quem existe no mundo da Trans Fictício BR.

Decisões espelhadas do MER (docs/02): padrão Party na ORGANIZACAO; endereços
carregam a identidade do ponto de entrega (nome_local/documento); catálogo de
itens por cliente; enums como VARCHAR + CHECK (nada de tipo nativo do Postgres,
migrations simples); `ondelete=RESTRICT` (cadastro não some por acidente).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from logistica_otif_mlops.db import Base

SCHEMA_OPERACAO = "operacao"


class Organizacao(Base):
    """Padrão Party: clientes, bases parceiras e a própria matriz."""

    __tablename__ = "organizacao"
    __table_args__ = (
        CheckConstraint(
            "tipo_parceria IN ('CLIENTE', 'BASE', 'MATRIZ')",
            name="tipo_parceria_valido",
        ),
        CheckConstraint(
            "porte IS NULL OR porte IN ('MICRO', 'PEQUENA', 'MEDIA', 'GRANDE', 'MEGA')",
            name="porte_valido",
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sigla: Mapped[str] = mapped_column(String(10), unique=True)
    razao_social: Mapped[str] = mapped_column(String(150))
    nome_fantasia: Mapped[str] = mapped_column(String(150))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    tipo_parceria: Mapped[str] = mapped_column(String(10))
    porte: Mapped[str | None] = mapped_column(String(10))  # só faz sentido p/ CLIENTE
    segmento: Mapped[str | None] = mapped_column(String(40))  # LOGISTICA p/ BASE
    fl_entrega_agendada: Mapped[bool | None] = mapped_column(Boolean)  # regra de cliente
    dt_inicio_contrato: Mapped[date] = mapped_column(Date)
    dt_cancelamento: Mapped[date | None] = mapped_column(Date)  # onda de 2025 no seed
    # % de OTIF prometido em contrato (só clientes); abaixo dele = multa.
    # 0.90 MPM · 0.95-0.97 G/M · 0.98 = retenção desesperada (anamnese 31/07)
    otif_contratual: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Endereco(Base):
    """Ponto de entrega/endereço de uma organização (com identidade fiscal)."""

    __tablename__ = "endereco"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organizacao_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    nome_local: Mapped[str] = mapped_column(String(150))  # "Consultorio X", "Expo..."
    documento: Mapped[str | None] = mapped_column(String(14))  # contra quem a NF sai
    logradouro: Mapped[str] = mapped_column(String(200))
    bairro: Mapped[str] = mapped_column(String(80))
    cidade: Mapped[str] = mapped_column(String(80))
    uf: Mapped[str] = mapped_column(String(2))  # regiao deriva da UF (silver)
    cep: Mapped[str] = mapped_column(String(8))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    fl_principal: Mapped[bool] = mapped_column(Boolean, default=False)


class Item(Base):
    """Catálogo de materiais, por cliente (operador logístico guarda o do cliente)."""

    __tablename__ = "item"
    __table_args__ = (
        UniqueConstraint("cliente_id", "codigo"),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    codigo: Mapped[str] = mapped_column(String(30))
    descricao: Mapped[str] = mapped_column(String(200))
    grupo: Mapped[str] = mapped_column(String(60))  # ex.: MATERIAL PROMOCIONAL
    subgrupo: Mapped[str] = mapped_column(String(60))  # ex.: BANNER, AMOSTRA
    peso_kg: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    volume_m3: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    # nullable DE PROPOSITO: item sem valor = furo de cobertura fiscal (Discovery acha)
    valor_unitario: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class LocalEstoque(Base):
    """Local físico de guarda: galpões da matriz (TB1, G2...) e depósitos das bases."""

    __tablename__ = "local_estoque"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organizacao_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    codigo: Mapped[str] = mapped_column(String(10), unique=True)  # TB1, G2, BSE-FOR...
    nome: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Transportador(Base):
    """Quem executa transporte: frota própria, agregados, carreteiros, transportadoras."""

    __tablename__ = "transportador"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('FROTA_PROPRIA', 'AGREGADO', 'CARRETEIRO', 'TRANSPORTADORA')",
            name="tipo_valido",
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    cnpj: Mapped[str | None] = mapped_column(String(14))  # carreteiro PF pode não ter
    tipo: Mapped[str] = mapped_column(String(15))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Veiculo(Base):
    """Veículo de um transportador (a Scania do Marcos, os 10 da TransLancer...)."""

    __tablename__ = "veiculo"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    transportador_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.transportador.id", ondelete="RESTRICT")
    )
    placa: Mapped[str] = mapped_column(String(8), unique=True)
    tipo_veiculo: Mapped[str] = mapped_column(String(30))  # fiorino, vuc, truck...
    capacidade_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class Rota(Base):
    """Agrupador de destino dos embarques (a dimensão de rota das minutas)."""

    __tablename__ = "rota"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    descricao: Mapped[str] = mapped_column(String(120))
    uf: Mapped[str] = mapped_column(String(2))
