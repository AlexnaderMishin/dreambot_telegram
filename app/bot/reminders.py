from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import text
from app.db.base import SessionLocal
from app.db.models import User
from app.bot.reminders import schedule_for_user, unschedule_for_user, toggle_remind

router = Router()

REMIND_BTN = "🔔 Напоминания"

def _kb_remind_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Включить") , KeyboardButton(text="Выключить")],
            [KeyboardButton(text="Поставить время")],
        ],
        resize_keyboard=True
    )

async def show_remind_menu(message: types.Message):
    # проверяем, что юзер есть
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id==message.from_user.id).first()
        if not u:
            await message.answer("Сначала /start.", reply_markup=None)
            return
    await message.answer("Напоминания. Выберите действие:", reply_markup=_kb_remind_menu())

@router.message(Command("remind"))
@router.message(F.text == REMIND_BTN)           # <- ловим кнопку
async def remind_entry(message: types.Message):
    await show_remind_menu(message)

@router.message(F.text.lower().in_({"включить"}))
async def remind_on(message: types.Message):
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id==message.from_user.id).first()
        if not u:
            await message.answer("Сначала /start.")
            return
        toggle_remind(u.id, True)
    # 08:30 по умолчанию, если времени нет
    await schedule_for_user(message.bot, u.id, u.tg_id, u.tz or "Europe/Moscow")
    await message.answer("Напоминания включены. По умолчанию — 08:30.")

@router.message(F.text.lower().in_({"выключить"}))
async def remind_off(message: types.Message):
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id==message.from_user.id).first()
        if not u:
            await message.answer("Сначала /start.")
            return
        toggle_remind(u.id, False)
    unschedule_for_user(message.from_user.id)
    await message.answer("Напоминания выключены.")

@router.message(F.text == "Поставить время")
async def ask_time(message: types.Message):
    await message.answer("Напишите время в формате ЧЧ:ММ (например, 09:20).")

@router.message(F.text.regexp(r"^\s*\d{1,2}:\d{2}\s*$"))
async def set_time(message: types.Message):
    raw = message.text.strip()
    hh, mm = raw.split(":")
    try:
        hh = int(hh); mm = int(mm)
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except Exception:
        await message.answer("Неверный формат времени. Пример: 09:20")
        return

    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id==message.from_user.id).first()
        if not u:
            await message.answer("Сначала /start.")
            return
        # сохраняем время в БД
        from datetime import time as dtime
        u.remind_time = dtime(hh, mm)
        s.commit()

    # пересоздадим задачу
    await message.answer(f"Время напоминания установлено: {hh:02d}:{mm:02d}.")
    with SessionLocal() as s:
        u = s.query(User).filter(User.tg_id==message.from_user.id).first()
        if u and u.remind_enabled:
            unschedule_for_user(u.id)
            await schedule_for_user(message.bot, u.id, u.tg_id, u.tz or "Europe/Moscow")
            await message.answer("Расписание обновлено.")
