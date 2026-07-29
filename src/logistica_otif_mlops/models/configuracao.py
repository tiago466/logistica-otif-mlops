"""Grupo CONFIGURAÇÃO do schema `operacao`: as réguas do negócio.

Duas naturezas convivem aqui: **dado de domínio** (FASE, MODALIDADE,
TIPO_OCORRENCIA: listas estáveis que definem o vocabulário do processo e
nascem junto com o schema, na própria migration) e **dado de parametrização**
(LEAD_TIME, CAMPANHA: réguas volumosas/variáveis, populadas pelo gerador
determinístico).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from logistica_otif_mlops.db import Base

SCHEMA_OPERACAO = "operacao"


class Modalidade(Base):
    """Modal de transporte prometido no pedido.

    Convenção da casa: `codigo` = chave estável p/ máquina (CAIXA_ALTA);
    `descricao` = rótulo humano (com acento, vai p/ tela e relatório).
    """

    __tablename__ = "modalidade"
    __table_args__ = (
        CheckConstraint("codigo IN ('RODOVIARIO', 'AEREO')", name="codigo_valido"),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(15), unique=True)
    descricao: Mapped[str] = mapped_column(String(30))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class LeadTime(Base):
    """A régua de prazo: modalidade × UF × cidade → dias úteis prometidos.

    Consultada na criação do pedido; o resultado é carimbado em
    `PEDIDO.dt_prazo_entrega`. Régua não conhece pedidos.
    """

    __tablename__ = "lead_time"
    __table_args__ = (
        UniqueConstraint("modalidade_id", "uf", "cidade"),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    modalidade_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.modalidade.id", ondelete="RESTRICT")
    )
    uf: Mapped[str] = mapped_column(String(2))
    cidade: Mapped[str] = mapped_column(String(80))
    dias_uteis: Mapped[int] = mapped_column(Integer)


class Campanha(Base):
    """Campanha comercial do cliente (a alavanca da sazonalidade nas grades)."""

    __tablename__ = "campanha"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    descricao: Mapped[str] = mapped_column(String(120))
    dt_inicio: Mapped[date] = mapped_column(Date)
    dt_fim: Mapped[date] = mapped_column(Date)


class Fase(Base):
    """As 10 fases do ciclo de vida do pedido (EA → CE)."""

    __tablename__ = "fase"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(2), unique=True)
    nome: Mapped[str] = mapped_column(String(60))
    ordem: Mapped[int] = mapped_column(Integer, unique=True)
    fl_esporadica: Mapped[bool] = mapped_column(Boolean, default=False)  # DC e EX


class TipoOcorrencia(Base):
    """Vocabulário curado das ocorrências (reentrega, devolução, avaria...)."""

    __tablename__ = "tipo_ocorrencia"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    descricao: Mapped[str] = mapped_column(String(120))
    fl_impacta_prazo: Mapped[bool] = mapped_column(Boolean, default=True)
