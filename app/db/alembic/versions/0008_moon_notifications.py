"""add moon notifications fields to users

Revision ID: 0006_moon_notifications
Revises: 0005_premium_default_true
Create Date: 2025-09-19

"""
from alembic import op
import sqlalchemy as sa


# уникальный id этой миграции
revision = "0008_moon_notifications"
# Поставь сюда актуальный предыдущий head из твоего репозитория Alembic
down_revision = "0007_astrology_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- новые настройки пользователя ---
    op.add_column(
        "users",
        sa.Column("notify_moon_phase", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "users",
        sa.Column("notify_daily_time", sa.Text(), nullable=True),  # локальное время "HH:MM"
    )
    op.add_column(
        "users",
        sa.Column("last_moon_phase", sa.Text(), nullable=True),   # "Новолуние" | "Растущая Луна" | ...
    )
    op.add_column(
        "users",
        sa.Column("last_moon_day", sa.Integer(), nullable=True),  # 0..29
    )

    # при желании — быстрые фильтры
    op.create_index("idx_users_notify_moon_phase", "users", ["notify_moon_phase"])
    op.create_index("idx_users_last_moon_phase", "users", ["last_moon_phase"])


def downgrade() -> None:
    op.drop_index("idx_users_last_moon_phase", table_name="users")
    op.drop_index("idx_users_notify_moon_phase", table_name="users")
    op.drop_column("users", "last_moon_day")
    op.drop_column("users", "last_moon_phase")
    op.drop_column("users", "notify_daily_time")
    op.drop_column("users", "notify_moon_phase")
