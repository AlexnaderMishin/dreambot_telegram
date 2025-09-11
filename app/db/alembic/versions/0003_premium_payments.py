"""add premium_expires_at to users and create payments

Revision ID: 0003_add_premium_expires_and_payments
Revises: 0002_add_remind_enabled
Create Date: 2025-09-09
"""
from alembic import op
import sqlalchemy as sa

# ревизии — в том же стиле, что и раньше
revision = '0003_premium_payments'   # <= 32 символов
down_revision = '0002_add_remind_enabled'
branch_labels = None
depends_on = None


def upgrade():
    # 1) колонка в users
    op.add_column(
        'users',
        sa.Column('premium_expires_at', sa.TIMESTAMP(timezone=True), nullable=True)
    )

    # 2) таблица payments (минимальный состав)
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('payload', sa.String(length=255), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('total_amount', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # индекс по user_id, чтобы быстрее смотреть платежи пользователя
    op.create_index('ix_payments_user_id', 'payments', ['user_id'])


def downgrade():
    op.drop_index('ix_payments_user_id', table_name='payments')
    op.drop_table('payments')
    op.drop_column('users', 'premium_expires_at')