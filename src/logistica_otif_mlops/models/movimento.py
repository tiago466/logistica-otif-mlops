"""Grupo MOVIMENTO do schema `operacao`: o que acontece na TransBrasil.

O coração do modelo: o pedido e sua vida (fases, DOCs, minutas, entregas,
ocorrências), a entrada de material (recebimento), a foto do estoque e os
serviços paralelos (coleta reversa e positivação). Tudo espelho 1:1 do MER
congelado (docs/02); nenhuma flag derivada é armazenada (atraso se calcula).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from logistica_otif_mlops.db import Base

SCHEMA_OPERACAO = "operacao"


class Pedido(Base):
    """A SS: a unidade de trabalho da distribuição."""

    __tablename__ = "pedido"
    __table_args__ = (
        CheckConstraint("canal IN ('GRADE', 'WEB')", name="canal_valido"),
        CheckConstraint(
            "tipo_atendimento IS NULL OR tipo_atendimento IN "
            "('ENTREGA_DIRETA', 'RETIRA_BASE', 'ENTREGA_VIA_BASE')",
            name="tipo_atendimento_valido",
        ),
        CheckConstraint(
            "nivel_servico IN ('PADRAO', 'EXCLUSIVO')", name="nivel_servico_valido"
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)  # chave de negócio
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    endereco_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.endereco.id", ondelete="RESTRICT")
    )
    modalidade_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.modalidade.id", ondelete="RESTRICT")
    )
    campanha_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.campanha.id", ondelete="RESTRICT")
    )
    canal: Mapped[str] = mapped_column(String(5))
    # pedido do CLIENTE na criação: EXCLUSIVO = veículo dedicado imediato, 3x o preço
    # (Zenatur guardava isso dentro de "modalidade"; aqui é eixo próprio).
    # Consistência: pedido EXCLUSIVO => minutas dele com tipo_carga EXCLUSIVA (silver).
    nivel_servico: Mapped[str] = mapped_column(
        String(10), default="PADRAO", server_default="PADRAO"
    )
    # nullable de propósito: a forma de atendimento é DECIDIDA no planejamento (PL)
    tipo_atendimento: Mapped[str | None] = mapped_column(String(20))
    dt_solicitacao: Mapped[datetime] = mapped_column(DateTime)
    dt_prazo_saida_expedicao: Mapped[date] = mapped_column(Date)
    dt_prazo_entrega: Mapped[date] = mapped_column(Date)  # a promessa (via LEAD_TIME)
    peso_teorico_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    volume_teorico_m3: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    peso_real_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))  # nasce no ME
    volume_real_m3: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    nf_numero: Mapped[str | None] = mapped_column(String(20))  # nasce na EN


class PedidoItem(Base):
    """Itens que compõem o pedido."""

    __tablename__ = "pedido_item"
    __table_args__ = (
        UniqueConstraint("pedido_id", "item_id"),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT")
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.item.id", ondelete="RESTRICT")
    )
    quantidade: Mapped[int] = mapped_column(Integer)


class PedidoFase(Base):
    """Histórico LONGO das fases: cada passagem é um evento (entrada/saída)."""

    __tablename__ = "pedido_fase"
    __table_args__ = (
        UniqueConstraint("pedido_id", "fase_id"),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT"), index=True
    )
    fase_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.fase.id", ondelete="RESTRICT")
    )
    dt_entrada: Mapped[datetime] = mapped_column(DateTime)
    dt_saida: Mapped[datetime | None] = mapped_column(DateTime)  # aberta = fase atual


class OrdemColeta(Base):
    """A DOC: uma ordem de separação POR LOCAL onde há itens do pedido."""

    __tablename__ = "ordem_coleta"
    __table_args__ = (
        UniqueConstraint("pedido_id", "local_estoque_id"),
        CheckConstraint(
            "status IN ('EMITIDA', 'COLETADA', 'CANCELADA')", name="status_valido"
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT"), index=True
    )
    local_estoque_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.local_estoque.id", ondelete="RESTRICT")
    )
    dt_emissao: Mapped[datetime] = mapped_column(DateTime)
    dt_conclusao: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10))


class Minuta(Base):
    """O embarque/romaneio: consolida pedidos num caminhão (ou voo)."""

    __tablename__ = "minuta"
    __table_args__ = (
        CheckConstraint(
            "tipo_carga IN ('CONSOLIDADA', 'EXCLUSIVA')", name="tipo_carga_valido"
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    # modal DESTA perna/embarque: um pedido multimodal (rodov ate a base, aereo
    # depois) tem minutas de modais diferentes. PEDIDO.modalidade = o contratado.
    modalidade_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.modalidade.id", ondelete="RESTRICT")
    )
    transportador_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.transportador.id", ondelete="RESTRICT")
    )
    veiculo_id: Mapped[int | None] = mapped_column(  # aéreo viaja sem veículo nosso
        ForeignKey(f"{SCHEMA_OPERACAO}.veiculo.id", ondelete="RESTRICT")
    )
    rota_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.rota.id", ondelete="RESTRICT")
    )
    tipo_carga: Mapped[str] = mapped_column(String(12))
    dt_expedicao: Mapped[datetime] = mapped_column(DateTime)


class Entrega(Base):
    """Uma perna/tentativa de um pedido dentro de uma minuta."""

    __tablename__ = "entrega"
    __table_args__ = (
        CheckConstraint(
            "tipo_perna IN ('DIRETA', 'TRANSFERENCIA_BASE', 'ULTIMA_MILHA_BASE')",
            name="tipo_perna_valido",
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT"), index=True
    )
    minuta_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.minuta.id", ondelete="RESTRICT"), index=True
    )
    tipo_perna: Mapped[str] = mapped_column(String(20))
    endereco_destino_id: Mapped[int] = mapped_column(  # base (transferência) ou final
        ForeignKey(f"{SCHEMA_OPERACAO}.endereco.id", ondelete="RESTRICT")
    )
    dt_prevista: Mapped[date] = mapped_column(Date)
    dt_chegada: Mapped[datetime | None] = mapped_column(DateTime)
    # pernas com Base: quando a base EFETIVOU a entrada (material disponivel p/
    # retirada/ultima milha). Atraso entre chegada e entrada e da BASE (repasse).
    dt_entrada_base: Mapped[datetime | None] = mapped_column(DateTime)
    recebedor: Mapped[str | None] = mapped_column(String(100))  # quem assinou
    # tri-estado, e o nulo é essencial: NULL = ainda em trânsito (desfecho
    # desconhecido), true = entregue, false = tentativa falhou. Marcar `false`
    # numa carga que ainda está na estrada seria registrar um fracasso que não
    # aconteceu, e contaminaria todo indicador de OTIF.
    fl_sucesso: Mapped[bool | None] = mapped_column(Boolean)
    fl_canhoto: Mapped[bool] = mapped_column(Boolean, default=False)


class RetiradaBase(Base):
    """Retirada pelo cliente na Base (tipo RETIRA_BASE): demora dele não é atraso."""

    __tablename__ = "retirada_base"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT"), unique=True
    )
    base_id: Mapped[int] = mapped_column(  # organizacao tipo BASE
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    dt_retirada: Mapped[datetime] = mapped_column(DateTime)
    retirado_por: Mapped[str] = mapped_column(String(100))


class Ocorrencia(Base):
    """Eventos fora do fluxo feliz; pode nascer antes de existir entrega (ex.: PC)."""

    __tablename__ = "ocorrencia"
    __table_args__ = ({"schema": SCHEMA_OPERACAO},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    pedido_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT"), index=True
    )
    entrega_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.entrega.id", ondelete="RESTRICT")
    )
    tipo_ocorrencia_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.tipo_ocorrencia.id", ondelete="RESTRICT")
    )
    dt_ocorrencia: Mapped[datetime] = mapped_column(DateTime)
    observacao: Mapped[str | None] = mapped_column(String(255))
    dt_cancelada: Mapped[datetime | None] = mapped_column(DateTime)  # cancel. lógico


class Recebimento(Base):
    """Entrada de material do cliente no estoque (matriz ou base), por item."""

    __tablename__ = "recebimento"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AGUARDANDO', 'RECEBIDO', 'DIVERGENTE')", name="status_valido"
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    item_id: Mapped[int] = mapped_column(  # cliente deriva do item
        ForeignKey(f"{SCHEMA_OPERACAO}.item.id", ondelete="RESTRICT"), index=True
    )
    local_estoque_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.local_estoque.id", ondelete="RESTRICT")
    )
    numero_agendamento: Mapped[str | None] = mapped_column(String(20))
    fornecedor_nome: Mapped[str | None] = mapped_column(String(150))  # gráfica etc.
    nf_entrada: Mapped[str] = mapped_column(String(20))
    quantidade: Mapped[int] = mapped_column(Integer)
    dt_validade: Mapped[date | None] = mapped_column(Date)  # lote perecível
    dt_prevista: Mapped[date] = mapped_column(Date)
    dt_recebimento: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10))


class EstoqueSnapshot(Base):
    """Foto do estoque por item × local: fechamento mensal + diária no mês corrente."""

    __tablename__ = "estoque_snapshot"
    __table_args__ = (
        UniqueConstraint("data", "item_id", "local_estoque_id"),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    data: Mapped[date] = mapped_column(Date)
    item_id: Mapped[int] = mapped_column(  # cliente deriva do item
        ForeignKey(f"{SCHEMA_OPERACAO}.item.id", ondelete="RESTRICT"), index=True
    )
    local_estoque_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.local_estoque.id", ondelete="RESTRICT")
    )
    qtde_saldo: Mapped[int] = mapped_column(Integer)
    m3_ocupado: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    valor_material: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # congelado na foto
    valor_danificado: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)


class Coleta(Base):
    """Serviço reverso EXTERNO (OS): buscar material fora, tipicamente descarte."""

    __tablename__ = "coleta"
    __table_args__ = (
        CheckConstraint(
            "finalidade IN ('DESCARTE', 'RETORNO_ESTOQUE')", name="finalidade_valida"
        ),
        CheckConstraint(
            "status IN ('SOLICITADA', 'COLETADA', 'CANCELADA')", name="status_valido"
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)  # a OS (financeiro)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    endereco_origem_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.endereco.id", ondelete="RESTRICT")
    )
    local_estoque_destino_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.local_estoque.id", ondelete="RESTRICT")
    )
    transportador_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.transportador.id", ondelete="RESTRICT")
    )
    veiculo_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.veiculo.id", ondelete="RESTRICT")
    )
    dt_solicitacao: Mapped[datetime] = mapped_column(DateTime)
    dt_prevista: Mapped[date] = mapped_column(Date)
    dt_coleta: Mapped[datetime | None] = mapped_column(DateTime)
    peso_kg: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    volume_m3: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    finalidade: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(11))


class Positivacao(Base):
    """Serviço de montagem em evento por parceiro local (OS)."""

    __tablename__ = "positivacao"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ABERTA', 'REALIZADA', 'CANCELADA')", name="status_valido"
        ),
        {"schema": SCHEMA_OPERACAO},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)  # a OS (financeiro)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.organizacao.id", ondelete="RESTRICT")
    )
    pedido_id: Mapped[int | None] = mapped_column(  # material enviado ao evento
        ForeignKey(f"{SCHEMA_OPERACAO}.pedido.id", ondelete="RESTRICT")
    )
    endereco_id: Mapped[int] = mapped_column(  # local do evento
        ForeignKey(f"{SCHEMA_OPERACAO}.endereco.id", ondelete="RESTRICT")
    )
    campanha_id: Mapped[int | None] = mapped_column(
        ForeignKey(f"{SCHEMA_OPERACAO}.campanha.id", ondelete="RESTRICT")
    )
    parceiro_nome: Mapped[str] = mapped_column(String(150))  # montador local
    dt_abertura: Mapped[date] = mapped_column(Date)
    dt_servico: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))
