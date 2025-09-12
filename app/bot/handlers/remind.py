# app/bot/handlers/remind.py
from __future__ import annotations

import re
from datetime import time as dtime

from aiogram import Router, F, types
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from app.db.base import SessionLocal
from app.db.models import User
from app.bot.reminders import (
    schedule_for_user,
    unschedule_for_user,
    toggle_remind,
    scheduler,  # чтобы не вызывать второй раз start()
)

router = Router()


class RemindForm(StatesGroup):
    wait_time = State()


def _fmt_time(t: dtime | None) -> str:
    if not t:
        return "не задано (по умолчанию 08:30)"
    return f"{t.hour:02d}:{t.minute:02d}"


def _parse_any_time(text: str) -> dtime | None:
    """
    Принимает '8', '08', '8:5', '8:05', '08:05', '23:59', '0:0', '00:00'.
    Возвращает datetime.time или None, если не похоже на время.
    """
    text = text.strip()
    if text.lower() in {"off", "выкл", "выключить"}:
        return None

    # 8 -> 08:00 ; 8:5 -> 08:05
    m = re.fullmatch(r"(\d{1,2})(?::(\d{1,2}))?$", text)
    if not m:
        return dtime(99, 99)  # маркер "невалидное"

    h = int(m.group(1))
    mm = int(m.group(2) or 0)
    if 0 <= h <= 23 and 0 <= mm <= 59:
        return dtime(h, mm)
    return dtime(99, 99)


@router.message(F.text == "🔔 Напоминания")
async def reminders_entry(m: types.Message, state: FSMContext):
    # показываем текущее состояние и просим указать новое время
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).first()

    if not user:
        await m.answer("Сначала /start.")
        return

    status = "включены ✅" if user.remind_enabled else "выключены ⛔️"
    cur = _fmt_time(user.remind_time)
    tz = user.tz or "UTC"
    await m.answer(
        "🔔 *Напоминания*\n"
        f"Сейчас: {status}\n"
        f"Время: *{cur}* (ваш часовой пояс: *{tz}*)\n\n"
        "Отправьте время в формате `чч:мм` (например, `07:30` или просто `7` = 07:00),\n"
        "или отправьте `off`, чтобы выключить напоминания.",
        parse_mode="Markdown",
    )
    await state.set_state(RemindForm.wait_time)


@router.message(RemindForm.wait_time)
async def reminders_set_time(m: types.Message, state: FSMContext):
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).first()

    if not user:
        await m.answer("Сначала /start.")
        await state.clear()
        return

    t = _parse_any_time(m.text or "")
    # off → выключаем
    if t is None:
        toggle_remind(user.id, False)
        unschedule_for_user(user.id)
        await m.answer("🔕 Напоминания *выключены*.", parse_mode="Markdown")
        await state.clear()
        return

    # ошибка формата
    if t.hour == 99:
        await m.answer("Похоже, это не время. Пример: `07:30` или `21`.", parse_mode="Markdown")
        return

    # сохраняем время и включаем
    with SessionLocal() as s:
        db_user = s.query(User).filter_by(id=user.id).first()
        db_user.remind_time = t
        db_user.remind_enabled = True
        s.commit()

        # берём актуальные значения
        tz = db_user.tz or "UTC"
        schedule_for_user(
            bot=m.bot,
            user_id=db_user.id,
            tg_id=db_user.tg_id,
            tz=tz,
            remind_time=db_user.remind_time,
        )

    await m.answer(
        f"🔔 Готово! Буду напоминать ежедневно в *{t.hour:02d}:{t.minute:02d}* по вашему поясу.",
        parse_mode="Markdown",
    )
    await state.clear()
