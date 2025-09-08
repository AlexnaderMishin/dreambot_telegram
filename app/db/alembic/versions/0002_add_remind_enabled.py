"""add remind_enabled to users

Revision ID: 0002_add_remind_enabled
Revises: 0001_initial
Create Date: 2025-09-02

"""
from alembic import op
import sqlalchemy as sa

# ревизии подстрой под свои
revision = '0002_add_remind_enabled'
down_revision = '0001_initial'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('remind_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE users SET remind_enabled = false")

def downgrade():
    op.drop_column('users', 'remind_enabled')
