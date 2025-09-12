"""add remind_time to users

Revision ID: 0004_add_remind_time
Revises: 0003_premium_payments
Create Date: 2025-09-12
"""

from alembic import op
import sqlalchemy as sa


# ревизии подстрой под свои
revision = "0004_add_remind_time"
down_revision = "0003_premium_payments"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("remind_time", sa.Time(), nullable=True))
    # всем существующим ставим дефолт 08:30
    op.execute("UPDATE users SET remind_time = '08:30' WHERE remind_time IS NULL")


def downgrade():
    op.drop_column("users", "remind_time")
