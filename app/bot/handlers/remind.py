# app/bot/handlers/remind.py
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from sqlalchemy import text
from app.db.base import SessionLocal
from app.db.models import User

# функции планировщика/перезапуска задач
from app.bot.reminders import (
    schedule_for_user,
    unschedule_for_user,
    toggle_remind,
)

# чтобы текст кнопки совпадал на 100% — берём из одного источника
from app.bot.ui import main_kb, HELP_TEXT  # только для /remind, возврата и подсказок
from app.bot.ui import REMIND_BTN  # <<< ВАЖНО: единый текст кнопки "🔔 Напоминания"

router = Router()

def _kb_remind_menu() -> ReplyKeyboardMarkup:
    kb = [[
        KeyboardButton(text="Включить"),
        KeyboardButton(text="Выключить"),
    ], [
        KeyboardButton(text="Поставить время")
    ]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def _ensure_user(message: types.Message) -> User | None:
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id == message.from_user.id).first()
        if not u:
            await message.answer("Сначала /start.")
            return None
        return u

async def _show_menu(message: types.Message):
    await message.answer("🔔 Напоминания.\nВыберите действие:", reply_markup=_kb_remind_menu())

@router.message(Command("remind"))
@router.message(F.text == REMIND_BTN)  # ловим нажатие кнопки из главного меню
async def remind_entry(message: types.Message):
    u = await _ensure_user(message)
    if not u:
        return
    await _show_menu(message)

@router.message(F.text.casefold() == "включить")
async def remind_on(message: types.Message):
    u = await _ensure_user(message)
    if not u:
        return
    toggle_remind(u.id, True)

    # если времени нет — используем значение по умолчанию из модели (08:30)
    await schedule_for_user(message.bot, u.id, u.tg_id, u.tz or "Europe/Moscow")
    await message.answer("✅ Напоминания включены. По умолчанию — 08:30.")

@router.message(F.text.casefold() == "выключить")
async def remind_off(message: types.Message):
    u = await _ensure_user(message)
    if not u:
        return
    toggle_remind(u.id, False)
    unschedule_for_user(u.id)
    await message.answer("🔕 Напоминания выключены.")

@router.message(F.text == "Поставить время")
async def ask_time(message: types.Message):
    await message.answer("Напишите время в формате ЧЧ:ММ (например, 09:20).")

@router.message(F.text.regexp(r"^\s*\d{1,2}:\d{2}\s*$"))
async def set_time(message: types.Message):
    u = await _ensure_user(message)
    if not u:
        return

    raw = message.text.strip()
    hh, mm = raw.split(":")
    try:
        hh = int(hh)
        mm = int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except Exception:
        await message.answer("Неверный формат времени. Пример: 09:20")
        return

    from datetime import time as dtime
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id == message.from_user.id).first()
        u.remind_time = dtime(hh, mm)
        s.commit()

    # пере-создадим задачу, если включена
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id == message.from_user.id).first()
        if u and u.remind_enabled:
            unschedule_for_user(u.id)
            await schedule_for_user(message.bot, u.id, u.tg_id, u.tz or "Europe/Moscow")
    await message.answer(f"⏰ Время напоминания установлено: {hh:02d}:{mm:02d}.")

# экспортируем под ожидаемым именем
remind_router = router
