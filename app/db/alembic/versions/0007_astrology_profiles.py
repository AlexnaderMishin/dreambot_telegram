# app/db/alembic/versions/0006_astrology_profiles.py
from alembic import op
import sqlalchemy as sa

revision = "0007_astrology_profiles"
down_revision = "0006_numerology_profiles"  # <— поставь ID твоей текущей head
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "astrology_profiles",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("birth_date", sa.Date, nullable=False),
        sa.Column("birth_time", sa.Time, nullable=True),
        sa.Column("birthplace", sa.Text, nullable=True),
        sa.Column("report_html", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_astrology_profiles_user_created", "astrology_profiles", ["user_id","created_at"], unique=False)

def downgrade():
    op.drop_index("ix_astrology_profiles_user_created", table_name="astrology_profiles")
    op.drop_table("astrology_profiles")
