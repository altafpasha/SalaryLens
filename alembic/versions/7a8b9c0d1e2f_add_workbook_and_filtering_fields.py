"""add_workbook_and_filtering_fields

Revision ID: 7a8b9c0d1e2f
Revises: 634c9f9a5e3b
Create Date: 2026-10-15 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, None] = '634c9f9a5e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to statements table
    op.add_column('statements', sa.Column('workbook_file_path', sa.String(length=512), nullable=True))
    op.add_column('statements', sa.Column('workbook_status', sa.String(length=50), server_default='pending', nullable=False))
    op.add_column('statements', sa.Column('workbook_generated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('statements', sa.Column('workbook_validation_status', sa.String(length=50), server_default='unverified', nullable=True))
    op.add_column('statements', sa.Column('total_transactions_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('total_debit_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('total_credit_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('included_in_salary_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('excluded_from_salary_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('native_pages_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('ocr_pages_count', sa.Integer(), server_default='0', nullable=False))
    op.add_column('statements', sa.Column('statement_start_date', sa.Date(), nullable=True))
    op.add_column('statements', sa.Column('statement_end_date', sa.Date(), nullable=True))
    op.add_column('statements', sa.Column('account_info_json', sa.JSON(), nullable=True))

    # Add columns to transactions table
    op.add_column('transactions', sa.Column('transaction_direction', sa.String(length=10), nullable=True))
    op.add_column('transactions', sa.Column('chqno', sa.String(length=50), nullable=True))
    op.add_column('transactions', sa.Column('category', sa.String(length=100), nullable=True))
    op.add_column('transactions', sa.Column('extraction_method', sa.String(length=20), server_default='native', nullable=False))
    op.add_column('transactions', sa.Column('validation_status', sa.String(length=50), server_default='valid', nullable=False))
    op.add_column('transactions', sa.Column('validation_warnings', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('included_in_salary_analysis', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('transactions', sa.Column('exclusion_reason', sa.String(length=255), nullable=True))
    op.add_column('transactions', sa.Column('inclusion_reason', sa.String(length=255), nullable=True))

    op.create_index(op.f('ix_transactions_included_in_salary_analysis'), 'transactions', ['included_in_salary_analysis'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_transactions_included_in_salary_analysis'), table_name='transactions')
    op.drop_column('transactions', 'inclusion_reason')
    op.drop_column('transactions', 'exclusion_reason')
    op.drop_column('transactions', 'included_in_salary_analysis')
    op.drop_column('transactions', 'validation_warnings')
    op.drop_column('transactions', 'validation_status')
    op.drop_column('transactions', 'extraction_method')
    op.drop_column('transactions', 'category')
    op.drop_column('transactions', 'chqno')
    op.drop_column('transactions', 'transaction_direction')

    op.drop_column('statements', 'account_info_json')
    op.drop_column('statements', 'statement_end_date')
    op.drop_column('statements', 'statement_start_date')
    op.drop_column('statements', 'ocr_pages_count')
    op.drop_column('statements', 'native_pages_count')
    op.drop_column('statements', 'excluded_from_salary_count')
    op.drop_column('statements', 'included_in_salary_count')
    op.drop_column('statements', 'total_credit_count')
    op.drop_column('statements', 'total_debit_count')
    op.drop_column('statements', 'total_transactions_count')
    op.drop_column('statements', 'workbook_validation_status')
    op.drop_column('statements', 'workbook_generated_at')
    op.drop_column('statements', 'workbook_status')
    op.drop_column('statements', 'workbook_file_path')
