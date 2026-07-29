"""convencao codigo x rotulo em categoria_custo

Mesmo defeito da modalidade, pego DE NOVO em revisão pelo Tiago (2026-07-29):
`nome` guardava código de máquina. Vira `codigo` + ganha `descricao` humana.
(Decisão 14 do docs/02: codigo = CAIXA_ALTA p/ máquina; rótulo = português
com acento p/ humano.)

Revision ID: eaf1f662b037
Revises: e1fee09a5b4e
Create Date: 2026-07-29 19:51:57.179601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eaf1f662b037'
down_revision: Union[str, Sequence[str], None] = 'e1fee09a5b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DESCRICOES = {
    'RODOVIARIO': 'Frete rodoviário',
    'AEREO': 'Frete aéreo',
    'BASE': 'Base parceira (última milha e serviços)',
    'MONTADOR': 'Montador parceiro (positivação)',
    'INSUMOS': 'Insumos de produção (embalagem, caixa, papel bolha)',
    'IMPOSTO_DIFAL': 'Diferencial de alíquota de ICMS interestadual',
    'OUTROS': 'Outros custos operacionais',
}


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('categoria_custo', 'nome', new_column_name='codigo', schema='custos')
    op.execute(
        'ALTER TABLE custos.categoria_custo RENAME CONSTRAINT '
        'uq_categoria_custo_nome TO uq_categoria_custo_codigo'
    )
    op.drop_constraint('ck_categoria_custo_nome_valido', 'categoria_custo', schema='custos')
    op.create_check_constraint(
        'codigo_valido',
        'categoria_custo',
        "codigo IN ('RODOVIARIO', 'AEREO', 'BASE', 'MONTADOR', "
        "'INSUMOS', 'IMPOSTO_DIFAL', 'OUTROS')",
        schema='custos',
    )
    op.add_column(
        'categoria_custo',
        sa.Column('descricao', sa.String(length=60), nullable=True),
        schema='custos',
    )
    for codigo, descricao in DESCRICOES.items():
        op.execute(
            sa.text('UPDATE custos.categoria_custo SET descricao = :d WHERE codigo = :c')
            .bindparams(d=descricao, c=codigo)
        )
    op.alter_column('categoria_custo', 'descricao', nullable=False, schema='custos')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('categoria_custo', 'descricao', schema='custos')
    op.drop_constraint('ck_categoria_custo_codigo_valido', 'categoria_custo', schema='custos')
    op.alter_column('categoria_custo', 'codigo', new_column_name='nome', schema='custos')
    op.execute(
        'ALTER TABLE custos.categoria_custo RENAME CONSTRAINT '
        'uq_categoria_custo_codigo TO uq_categoria_custo_nome'
    )
    op.create_check_constraint(
        'nome_valido',
        'categoria_custo',
        "nome IN ('RODOVIARIO', 'AEREO', 'BASE', 'MONTADOR', "
        "'INSUMOS', 'IMPOSTO_DIFAL', 'OUTROS')",
        schema='custos',
    )
