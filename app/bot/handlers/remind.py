from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import text
from app.db.base import SessionLocal
from app.db.models import User
from app.bot.reminders import schedule_for_user, unschedule_for_user, toggle_remind

router = Router()

@router.message(Command("remind"))
async def cmd_remind(message: types.Message):
    args = (message.text or "").split(maxsplit=1)
    tg_id = message.from_user.id

    with SessionLocal() as s:
        user = s.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            await message.answer("Сначала /start.")
            return

        if len(args) == 1:
            state = "включены" if user.remind_enabled else "выключены"
            await message.answer(f"Напоминания сейчас **{state}**.\nИспользуйте: /remind on или /remind off")
            return

        arg = args[1].strip().lower()
        if arg in ("on", "вкл", "enable"):
            toggle_remind(user.id, True)
            schedule_for_user(message.bot, user.id, user.tg_id, user.tz)
            await message.answer(f"Напоминания включены. Буду писать в 08:30 по вашей TZ ({user.tz}).")
        elif arg in ("off", "выкл", "disable"):
            toggle_remind(user.id, False)
            unschedule_for_user(user.id)
            await message.answer("Напоминания выключены.")
        else:
            await message.answer("Использование: /remind on | off")
