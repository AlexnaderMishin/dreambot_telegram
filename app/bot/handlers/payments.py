# app/bot/handlers/payments.py

import os
from datetime import datetime, timedelta, timezone

from aiogram import Router, F, Bot
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from aiogram.enums import ParseMode

from app.bot.ui import BUY_30, BUY_90, main_kb, kb_premium
from app.db.base import SessionLocal
from app.db.models import User, Payment

router = Router(name="payments")

# --- конфигурация из .env ---
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN")           # из BotFather → Payments → provider token
TITLE            = os.getenv("PREMIUM_TITLE", "Премиум-доступ")
DESCRIPTION      = os.getenv("PREMIUM_DESCRIPTION", "Расширенный разбор сна (GPT), ссылки и подсказки.")
PRICE_RUB_STR    = os.getenv("PREMIUM_PRICE_RUB", "299")   # цена за 30 дней
CURRENCY         = os.getenv("PREMIUM_CURRENCY", "RUB")
DAYS_DEFAULT     = int(os.getenv("PREMIUM_DAYS", "30"))    # длительность «BUY_30»
DAYS_ALT         = max(DAYS_DEFAULT * 3, 90)               # длительность «BUY_90» (например ×3)

def _rub_to_copecks(rub_str: str) -> int:
    return int(round(float(rub_str.replace(',', '.')) * 100))

PRICE_30 = _rub_to_copecks(PRICE_RUB_STR)
PRICE_90 = PRICE_30 * 3  # условно

# ===== КНОПКИ ПОКУПКИ ПРЕМИУМА =====

@router.message(F.text == "⭐ Премиум")
async def premium_entry(m: Message) -> None:
    await m.answer("Премиум-доступ. Выберите вариант:", reply_markup=kb_premium())

@router.message(F.text == BUY_30)
async def buy_30(m: Message) -> None:
    if not PROVIDER_TOKEN:
        await m.answer(
            "Платёжный провайдер пока не настроен. Попробуйте позже.",
            reply_markup=main_kb(),
        )
        return

    await m.answer_invoice(
        title=f"{TITLE} (30 дней)",
        description=DESCRIPTION,
        payload="premium:30",
        provider_token=PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label="Подписка 30 дней", amount=PRICE_30)],
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
    )

@router.message(F.text == BUY_90)
async def buy_90(m: Message) -> None:
    if not PROVIDER_TOKEN:
        await m.answer(
            "Платёжный провайдер пока не настроен. Попробуйте позже.",
            reply_markup=main_kb(),
        )
        return

    await m.answer_invoice(
        title=f"{TITLE} (90 дней)",
        description=DESCRIPTION,
        payload="premium:90",
        provider_token=PROVIDER_TOKEN,
        currency=CURRENCY,
        prices=[LabeledPrice(label="Подписка 90 дней", amount=PRICE_90)],
    )

# ===== ОБЯЗАТЕЛЬНО: пре-чекаут =====

@router.pre_checkout_query()
async def pre_checkout(pcq: PreCheckoutQuery, bot: Bot) -> None:
    # обязательно подтвердить, иначе платеж не пройдёт
    await bot.answer_pre_checkout_query(pcq.id, ok=True)

# ===== УСПЕШНЫЙ ПЛАТЕЖ =====

@router.message(F.successful_payment)
async def on_success_payment(m: Message) -> None:
    sp = m.successful_payment
    payload = sp.invoice_payload or ""
    days = DAYS_DEFAULT
    if payload.startswith("premium:"):
        try:
            days = int(payload.split(":", 1)[1]) or DAYS_DEFAULT
        except Exception:
            days = DAYS_DEFAULT

    # 1) продлеваем premium_expires_at
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).one_or_none()
        if not user:
            user = User(tg_id=m.from_user.id, username=m.from_user.username or None)
            s.add(user)
            s.flush()

        now = datetime.now(timezone.utc)
        start_from = user.premium_expires_at if user.premium_expires_at and user.premium_expires_at > now else now
        user.premium_expires_at = start_from + timedelta(days=days)
        user.is_premium = True

        # 2) фиксируем платеж (минимальный состав)
        s.add(Payment(
            user_id=user.id,
            provider="telegram",
            payload=payload,
            currency=sp.currency,
            total_amount=sp.total_amount,  # в минимальных единицах (копейки/центах)
        ))
        s.commit()

    # 3) отвечаем пользователю
    until = user.premium_expires_at.astimezone().strftime("%d.%m.%Y")
    await m.answer(
        f"Оплата прошла успешно ✅\nПремиум активирован до <b>{until}</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=main_kb(),
    )
