"""initial tables

Revision ID: 0001_initial
Revises: 
Create Date: 2025-08-29

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tg_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=True),
        sa.Column('tz', sa.String(length=64), nullable=False, server_default='Europe/Moscow'),
        sa.Column('is_premium', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_tg_id', 'users', ['tg_id'], unique=True)

    op.create_table('symbols',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('synonyms', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_symbols_key', 'symbols', ['key'], unique=True)

    op.create_table('crisis_keywords',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phrase', sa.String(length=256), nullable=False),
        sa.Column('severity', sa.Integer(), nullable=False),
        sa.Column('help_url', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_crisis_phrase', 'crisis_keywords', ['phrase'], unique=True)

    op.create_table('dreams',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('symbols', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('emotions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dreams_user_id', 'dreams', ['user_id'])

def downgrade() -> None:
    op.drop_index('ix_dreams_user_id', table_name='dreams')
    op.drop_table('dreams')
    op.drop_index('ix_crisis_phrase', table_name='crisis_keywords')
    op.drop_table('crisis_keywords')
    op.drop_index('ix_symbols_key', table_name='symbols')
    op.drop_table('symbols')
    op.drop_index('ix_users_tg_id', table_name='users')
    op.drop_table('users')
