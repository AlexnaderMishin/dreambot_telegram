from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import text
from app.db.base import SessionLocal
from app.db.models import User

router = Router()

@router.message(Command("note"))
async def cmd_note(message: types.Message):
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or len(args[1].strip()) < 3:
        await message.answer("Формат: /note <заметка>\nЗаметка будет добавлена к последнему сну.")
        return
    note = args[1].strip()

    tg_id = message.from_user.id
    with SessionLocal() as s:
        user = s.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            await message.answer("Сначала отправьте /start.")
            return

        # последний сон пользователя
        last = s.execute(text("""
            SELECT id FROM dreams WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1
        """), {"uid": user.id}).scalar()

        if not last:
            await message.answer("У вас ещё нет записей сна.")
            return

        s.execute(text("UPDATE dreams SET note = :note WHERE id = :id"), {"note": note, "id": last})
        s.commit()

    await message.answer("Заметка сохранена ✅")
