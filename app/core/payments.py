# app/core/payments.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.models import User
from app.db.base import SessionLocal

# читаем прайс из env однажды
import os

CURRENCY = os.getenv("CURRENCY", "RUB")
PRICE_1M = int(os.getenv("PREMIUM_PRICE_1M", "19900"))
PRICE_3M = int(os.getenv("PREMIUM_PRICE_3M", "54900"))
PRICE_LIFE = int(os.getenv("PREMIUM_PRICE_LIFE", "399000"))

PRICE_MAP = {
    "1m": PRICE_1M,
    "3m": PRICE_3M,
    "life": PRICE_LIFE,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def months_to_timedelta(months: int) -> timedelta:
    # аккуратно с месяцами — для “плюс-месяц” возьмём 30 дней как простую аппроксимацию
    return timedelta(days=30 * months)


def compute_new_expiry(current: datetime | None, months: int | None) -> datetime:
    """
    Продлевает премиум:
    - если months == None => бессрочно (life)
    - если premium ещё активен — добавляем от текущей даты истечения
    - если истёк — добавляем от сейчас
    """
    now = _now_utc()
    if months is None:
        # бессрочный — ставим далёкую дату (например, 50 лет)
        return now + timedelta(days=365 * 50)

    base = current if (current and current > now) else now
    return base + months_to_timedelta(months)


def resolve_plan_and_price(plan: str) -> tuple[int | None, int]:
    """
    plan: '1m' | '3m' | 'life'
    return: (months_or_none, expected_amount)
    """
    if plan == "1m":
        return (1, PRICE_1M)
    if plan == "3m":
        return (3, PRICE_3M)
    if plan == "life":
        return (None, PRICE_LIFE)
    raise ValueError("Unknown plan: " + plan)


def store_payment_and_grant_premium(
    s: Session,
    user_id: int,
    provider: str,
    payload: str,
    currency: str,
    total_amount: int,
    plan: str,
) -> None:
    """
    Сохраняет оплату и продлевает premium_expires_at.
    Валидация суммы по плану — чтобы не доверять payload’у.
    """
    months, expected = resolve_plan_and_price(plan)
    if total_amount != expected:
        raise ValueError(f"Amount mismatch: expected {expected}, got {total_amount}")

    # вставка в payments (минимально)
    s.execute(
        """
        INSERT INTO payments (user_id, provider, payload, currency, total_amount)
        VALUES (:user_id, :provider, :payload, :currency, :total_amount)
        """,
        dict(
            user_id=user_id,
            provider=provider,
            payload=payload[:255],
            currency=currency,
            total_amount=total_amount,
        ),
    )

    user: User | None = s.query(User).filter(User.id == user_id).one_or_none()
    if not user:
        raise ValueError("User not found")

    user.premium_expires_at = compute_new_expiry(user.premium_expires_at, months)
    s.add(user)
    s.commit()
