# app/bot/handlers/astrology.py
from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime
from app.db.base import SessionLocal
from app.db.models import User
from app.core.astrology_service import AstroInput, build_facts, render_llm

router = Router(name="astrology")

class AstroForm(StatesGroup):
    input_line = State()

@router.message(Command("astrology"))
@router.message(F.text == "🪐 Астрология")
async def cmd_astrology(m: Message, state: FSMContext):
    await state.set_state(AstroForm.input_line)
    await m.answer(
        "🪐 Астрология (лайт)\n"
        "Введите:\n<b>ФИО; ДД.ММ.ГГГГ; [чч:мм?]; [город?]</b>\n"
        "Пример: Иванов Иван; 12.04.1995; 08:15; Москва",
        parse_mode="HTML"
    )

@router.message(AstroForm.input_line, F.text)
async def on_line(m: Message, state: FSMContext):
    line = (m.text or "").strip()
    parts = [p.strip() for p in line.split(";")]
    if len(parts) < 2:
        await m.answer("Формат: ФИО; ДД.ММ.ГГГГ; [чч:мм?]; [город?]")
        return
    full_name = parts[0]
    try:
        birth_date = datetime.strptime(parts[1], "%d.%m.%Y")
    except ValueError:
        await m.answer("Неверная дата. Используйте ДД.ММ.ГГГГ")
        return
    birth_time = parts[2] if len(parts) >= 3 and parts[2] else None
    birthplace = parts[3] if len(parts) >= 4 and parts[3] else None

    ai = AstroInput(full_name=full_name, birth_date=birth_date, birth_time=birth_time, birthplace=birthplace)
    facts = build_facts(ai)
    html = render_llm(facts, ai)

    # сохраним профиль
    from sqlalchemy import text as sqt
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).one_or_none()
        if not user:
            user = User(tg_id=m.from_user.id, username=m.from_user.username, is_premium=True)
            s.add(user); s.commit(); s.refresh(user)
        s.execute(
            sqt("""
                INSERT INTO astrology_profiles (user_id, full_name, birth_date, birth_time, birthplace, report_html)
                VALUES (:uid, :fn, :bd, :bt, :bp, :html)
            """),
            {"uid": user.id, "fn": full_name, "bd": birth_date.date(),
             "bt": birth_time, "bp": birthplace, "html": html}
        )
        s.commit()

    await m.answer(html, parse_mode="HTML")
    await state.clear()
