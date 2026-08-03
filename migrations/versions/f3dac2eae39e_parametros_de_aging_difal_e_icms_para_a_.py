"""parametros de aging difal e icms para a MC

Revision ID: f3dac2eae39e
Revises: 5325249ec627
Create Date: 2026-08-03 09:42:45.654162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3dac2eae39e'
down_revision: Union[str, Sequence[str], None] = '5325249ec627'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PARAMETROS = [
    ('aging_3_6m', 0.30, 'Acrescimo na armazenagem de estoque parado de 3 a 6 meses'),
    ('aging_6_9m', 0.60, 'Acrescimo na armazenagem de estoque parado de 6 a 9 meses'),
    ('aging_9_12m', 0.90, 'Acrescimo na armazenagem de estoque parado de 9 a 12 meses'),
    ('aging_12m_mais', 1.80, 'Acrescimo na armazenagem de estoque parado ha mais de 12 meses'),
    ('competencia_vigencia_aging', 202507.0,
     'Competencia (AAAAMM) em que a politica de aging entrou em vigor'),
    ('custo_m3_galpao', 8.50, 'Custo proprio do espaco por m3/mes (fixo: fica FORA do CV da MC)'),
    ('custo_esteira_por_linha', 3.20,
     'Custo de separacao/manuseio por linha de pedido (fixo: base do custo de servir)'),
    ('aliquota_difal_simplificada', 0.04, 'DIFAL simplificado sobre operacao interestadual'),
    ('icms_interno', 0.12, 'ICMS destacado em operacao dentro de SC (parametro de negocio)'),
    ('icms_interestadual', 0.07, 'ICMS destacado em operacao interestadual (parametro de negocio)'),
]


def upgrade() -> None:
    """Upgrade schema."""
    parametro = sa.table(
        'parametro_financeiro',
        sa.column('chave', sa.String), sa.column('valor', sa.Numeric),
        sa.column('descricao', sa.String),
        schema='custos',
    )
    op.bulk_insert(parametro, [
        {'chave': c, 'valor': v, 'descricao': d} for c, v, d in PARAMETROS
    ])


def downgrade() -> None:
    """Downgrade schema."""
    chaves = ', '.join(f"'{c}'" for c, _, _ in PARAMETROS)
    op.execute(f"DELETE FROM custos.parametro_financeiro WHERE chave IN ({chaves})")
