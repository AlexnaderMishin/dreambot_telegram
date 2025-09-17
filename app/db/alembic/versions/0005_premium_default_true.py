"""set is_premium default TRUE and backfill"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_premium_default_true"
down_revision = "0004_add_remind_time"  # замените на актуальный down_revision
branch_labels = None
depends_on = None

def upgrade():
    # 1) default true на уровне БД
    op.alter_column("users", "is_premium",
                    existing_type=sa.Boolean(),
                    server_default=sa.text("true"),
                    existing_nullable=False)

    # 2) актуализировать существующие строки
    op.execute("UPDATE users SET is_premium = true WHERE is_premium = false")

def downgrade():
    # вернуть default в false (если ранее таким и был)
    op.alter_column("users", "is_premium",
                    existing_type=sa.Boolean(),
                    server_default=sa.text("false"),
                    existing_nullable=False)
