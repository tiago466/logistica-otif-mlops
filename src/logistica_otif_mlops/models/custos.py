"""Schema `custos`: o sistema FINANCEIRO da Trans Fictício BR (servido pela API).

Sistema de terceiro, de propósito: **nenhuma FK para o schema `operacao`**.
A ligação com o mundo é por chave de negócio (`cliente_sigla`,
`referencia_numero` = SS do pedido ou OS de coleta/positivação), e a
reconciliação é responsabilidade do pipeline (teste de qualidade no silver).
MC não se armazena: o Discovery calcula (regras no cofre interno).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from logistica_otif_mlops.db import Base

SCHEMA_CUSTOS = "custos"


class CategoriaCusto(Base):
    """Classificação do custo variável (dado de domínio).

    Convenção da casa (decisão 14): `codigo` p/ máquina, `descricao` p/ humano.
    """

    __tablename__ = "categoria_custo"
    __table_args__ = (
        CheckConstraint(
            "codigo IN ('RODOVIARIO', 'AEREO', 'BASE', 'MONTADOR', "
            "'INSUMOS', 'IMPOSTO_DIFAL', 'OUTROS')",
            name="codigo_valido",
        ),
        {"schema": SCHEMA_CUSTOS},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(15), unique=True)
    descricao: Mapped[str] = mapped_column(String(60))


class FaturamentoOperacao(Base):
    """Receita por operação/competência (o lado que a Trans Fictício BR cobra)."""

    __tablename__ = "faturamento_operacao"
    __table_args__ = (
        CheckConstraint(
            "tipo_operacao IN ('TRANSPORTE', 'ARMAZENAGEM', 'COLETA', 'POSITIVACAO')",
            name="tipo_operacao_valido",
        ),
        {"schema": SCHEMA_CUSTOS},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cliente_sigla: Mapped[str] = mapped_column(String(10), index=True)
    # SS ou OS; nullable: ARMAZENAGEM fatura por competência, sem operação
    referencia_numero: Mapped[str | None] = mapped_column(String(20), index=True)
    tipo_operacao: Mapped[str] = mapped_column(String(12))
    competencia: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    valor_com_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # a receita
    valor_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # ICMS destacado
    dt_faturamento: Mapped[date] = mapped_column(Date)


class CustoOperacao(Base):
    """Custo variável por operação/competência (o lado que a Trans Fictício BR paga)."""

    __tablename__ = "custo_operacao"
    __table_args__ = ({"schema": SCHEMA_CUSTOS},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cliente_sigla: Mapped[str] = mapped_column(String(10), index=True)
    referencia_numero: Mapped[str | None] = mapped_column(String(20), index=True)
    categoria_custo_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_CUSTOS}.categoria_custo.id", ondelete="RESTRICT")
    )
    prestador_nome: Mapped[str] = mapped_column(String(150))  # string, sist. terceiro
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    dt_competencia: Mapped[date] = mapped_column(Date)


class TarifaArmazenagem(Base):
    """Régua de cobrança da armazenagem, por cliente."""

    __tablename__ = "tarifa_armazenagem"
    __table_args__ = ({"schema": SCHEMA_CUSTOS},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    cliente_sigla: Mapped[str] = mapped_column(String(10), unique=True)
    valor_m3: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # R$ por m3 ocupado
    aliquota_ad_valorem: Mapped[Decimal] = mapped_column(Numeric(6, 4))  # % s/ valor
    valor_minimo_mensal: Mapped[Decimal] = mapped_column(Numeric(12, 2))  # meta mínima


class ParametroFinanceiro(Base):
    """Parâmetros de negócio (espelho da aba PARAMETROS do relatório real)."""

    __tablename__ = "parametro_financeiro"
    __table_args__ = ({"schema": SCHEMA_CUSTOS},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    chave: Mapped[str] = mapped_column(String(50), unique=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    descricao: Mapped[str] = mapped_column(String(200))
