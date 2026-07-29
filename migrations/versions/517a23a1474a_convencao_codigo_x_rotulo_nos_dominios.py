"""convencao codigo x rotulo nos dominios

Ajuste de convenção detectado pelo Tiago em revisão (2026-07-29):
- MODALIDADE tinha um código fantasiado de nome -> vira `codigo` + ganha `descricao`;
- rótulos humanos (fase.nome, tipo_ocorrencia.descricao) estavam sem acento -> corrigidos.
Convenção da casa: codigo = CAIXA_ALTA estável (máquina); nome/descricao = português
com acento (humano).

Revision ID: 517a23a1474a
Revises: be20d7763de7
Create Date: 2026-07-29 19:16:35.543805

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '517a23a1474a'
down_revision: Union[str, Sequence[str], None] = 'be20d7763de7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROTULOS_FASE = {
    'EA': 'Em Aprovação',
    'PC': 'Pré-Conferência',
    'DC': 'Distribuição de Cotas',
    'PL': 'Planejamento',
    'EX': 'Em Análise (urgência extrema)',
    'CF': 'Coleta Física',
    'ME': 'Manuseio',
    'EN': 'Emissão (NF-e)',
    'EC': 'Expedição',
    'CE': 'Confirmação de Entrega',
}

ROTULOS_OCORRENCIA = {
    'REENTREGA': 'Nova tentativa após falha de entrega',
    'DEVOLUCAO': 'Material devolvido à origem',
    'AVARIA': 'Material danificado no transporte ou manuseio',
    'DESTINATARIO_AUSENTE': 'Ninguém para receber no destino',
    'ENDERECO_NAO_LOCALIZADO': 'Endereço de entrega não encontrado',
    'AGENDAMENTO': 'Entrega reagendada com o destinatário',
    'EXTRAVIO': 'Material extraviado na cadeia',
    'DIVERGENCIA_CADASTRO': 'Erro de item ou endereço pego na pré-conferência',
}

DESCRICAO_MODALIDADE = {'RODOVIARIO': 'Rodoviário', 'AEREO': 'Aéreo'}


def upgrade() -> None:
    """Upgrade schema."""
    # MODALIDADE: nome era um codigo disfarcado -> renomeia e ganha rotulo humano
    op.alter_column('modalidade', 'nome', new_column_name='codigo', schema='operacao')
    op.execute(
        'ALTER TABLE operacao.modalidade RENAME CONSTRAINT '
        'uq_modalidade_nome TO uq_modalidade_codigo'
    )
    op.drop_constraint('ck_modalidade_nome_valido', 'modalidade', schema='operacao')
    op.create_check_constraint(
        'codigo_valido',
        'modalidade',
        "codigo IN ('RODOVIARIO', 'AEREO')",
        schema='operacao',
    )
    op.add_column(
        'modalidade',
        sa.Column('descricao', sa.String(length=30), nullable=True),
        schema='operacao',
    )
    for codigo, descricao in DESCRICAO_MODALIDADE.items():
        op.execute(
            sa.text('UPDATE operacao.modalidade SET descricao = :d WHERE codigo = :c')
            .bindparams(d=descricao, c=codigo)
        )
    op.alter_column('modalidade', 'descricao', nullable=False, schema='operacao')

    # ROTULOS humanos com acento (fase e tipo_ocorrencia)
    for codigo, nome in ROTULOS_FASE.items():
        op.execute(
            sa.text('UPDATE operacao.fase SET nome = :n WHERE codigo = :c')
            .bindparams(n=nome, c=codigo)
        )
    for codigo, descricao in ROTULOS_OCORRENCIA.items():
        op.execute(
            sa.text('UPDATE operacao.tipo_ocorrencia SET descricao = :d WHERE codigo = :c')
            .bindparams(d=descricao, c=codigo)
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('modalidade', 'descricao', schema='operacao')
    op.drop_constraint('ck_modalidade_codigo_valido', 'modalidade', schema='operacao')
    op.alter_column('modalidade', 'codigo', new_column_name='nome', schema='operacao')
    op.execute(
        'ALTER TABLE operacao.modalidade RENAME CONSTRAINT '
        'uq_modalidade_codigo TO uq_modalidade_nome'
    )
    op.create_check_constraint(
        'nome_valido',
        'modalidade',
        "nome IN ('RODOVIARIO', 'AEREO')",
        schema='operacao',
    )
    # rótulos voltam à forma sem acento da migration anterior (fielmente reversível)
    op.execute("UPDATE operacao.fase SET nome = 'Em Aprovacao' WHERE codigo = 'EA'")
    op.execute("UPDATE operacao.fase SET nome = 'Pre-Conferencia' WHERE codigo = 'PC'")
    op.execute("UPDATE operacao.fase SET nome = 'Distribuicao de Cotas' WHERE codigo = 'DC'")
    op.execute("UPDATE operacao.fase SET nome = 'Planejamento' WHERE codigo = 'PL'")
    op.execute(
        "UPDATE operacao.fase SET nome = 'Em Analise (urgencia extrema)' WHERE codigo = 'EX'"
    )
    op.execute("UPDATE operacao.fase SET nome = 'Coleta Fisica' WHERE codigo = 'CF'")
    op.execute("UPDATE operacao.fase SET nome = 'Manuseio' WHERE codigo = 'ME'")
    op.execute("UPDATE operacao.fase SET nome = 'Emissao (NF-e)' WHERE codigo = 'EN'")
    op.execute("UPDATE operacao.fase SET nome = 'Expedicao' WHERE codigo = 'EC'")
    op.execute("UPDATE operacao.fase SET nome = 'Confirmacao de Entrega' WHERE codigo = 'CE'")
