# app/bot/handlers/dreams.py
from __future__ import annotations

import re
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from app.db.base import SessionLocal
from app.db.models import User, Dream

router = Router()

# ===== FSM =====
class DreamsForm(StatesGroup):
    waiting_date = State()


DATE_RE = re.compile(r"^\s*(\d{2})\.(\d{2})\.(\d{4})\s*$")  # ДД.ММ.ГГГГ


def _parse_date(text: str) -> date | None:
    """Строгая проверка формата ДД.ММ.ГГГГ + существующая календарная дата."""
    m = DATE_RE.match(text or "")
    if not m:
        return None
    dd, mm, yyyy = map(int, m.groups())
    try:
        return date(yyyy, mm, dd)
    except ValueError:
        return None


@router.message(F.text == "📜 Мои сны")
async def ask_date(m: Message, state: FSMContext) -> None:
    await state.set_state(DreamsForm.waiting_date)
    await m.answer(
        "📅 Укажите дату в формате <b>ДД.ММ.ГГГГ</b> (например, <code>05.09.2025</code>).\n"
        "Для отмены — /cancel",
        parse_mode="HTML",
    )


@router.message(DreamsForm.waiting_date, F.text)
async def get_dream_by_date(m: Message, state: FSMContext) -> None:
    # 1) валидация даты
    d = _parse_date(m.text or "")
    if not d:
        await m.answer(
            "❗ Неверный формат даты. Введите в формате <b>ДД.ММ.ГГГГ</b>, например <code>05.09.2025</code>.",
            parse_mode="HTML",
        )
        return

    tg_id = m.from_user.id

    # 2) ищем пользователя и его часовой пояс
    with SessionLocal() as s:
        user: User | None = s.query(User).filter(User.tg_id == tg_id).first()

        if not user:
            await state.clear()
            await m.answer("Не нашли вас в базе. Попробуйте начать заново командой /start.")
            return

        # 3) границы суток в ЛОКАЛЬНОЙ зоне пользователя
        try:
            tz = ZoneInfo(user.tz or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")

        start_local = datetime.combine(d, time.min).replace(tzinfo=tz)
        end_local = start_local + timedelta(days=1)

        # 4) достаём сны за день (created_at хранится как timestamptz — сравнение идёт корректно)
        dreams = (
            s.query(Dream)
            .filter(
                Dream.user_id == user.id,
                Dream.created_at >= start_local,
                Dream.created_at < end_local,
            )
            .order_by(Dream.created_at.asc())
            .all()
        )

    # 5) ответ
    if not dreams:
        await state.clear()
        await m.answer(f"😴 Записей за {d.strftime('%d.%m.%Y')} не найдено.")
        return

    # Если позже введёте несколько записей в день — выведем всё по порядку
    pieces = []
    for i, dr in enumerate(dreams, start=1):
        t_local = dr.created_at.astimezone(tz).strftime("%H:%M")
        parts = [f"<b>Сон #{i} • {t_local}</b>"]
        parts.append(dr.text or "—")
        # можно добавить символы/эмоции/подсказки, если захотите:
        # if dr.symbols: parts.append(f"🔖 Символы: { ... }")
        # if dr.actions: parts.append(f"💡 Подсказки: { ... }")
        pieces.append("\n".join(parts))

    await state.clear()
    await m.answer(
        f"📜 <b>Ваши сны за {d.strftime('%d.%m.%Y')}</b>:\n\n" + "\n\n".join(pieces),
        parse_mode="HTML",
    )


# Опционально: быстрая отмена
@router.message(DreamsForm.waiting_date, F.text == "/cancel")
async def cancel(m: Message, state: FSMContext) -> None:
    await state.clear()
    await m.answer("Отменил. Возвращаюсь в меню.")
