"""create numerology_profiles

Revision ID: 0005_numerology_profiles
Revises: <PUT_PREVIOUS_REVISION_HERE>
Create Date: 2025-09-17 22:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ревизии
revision = "0006_numerology_profiles"
down_revision = "0005_premium_default_true"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "numerology_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("report_html", sa.Text(), nullable=False),
        sa.Column("report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_numerology_profiles_user_id", "numerology_profiles", ["user_id"])

def downgrade() -> None:
    op.drop_index("ix_numerology_profiles_user_id", table_name="numerology_profiles")
    op.drop_table("numerology_profiles")
