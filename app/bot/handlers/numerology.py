import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from loguru import logger
from app.core.numerology_service import analyze_numerology
from app.db.base import SessionLocal
from app.db.models import User, NumerologyProfile  # добавим модель ниже
from app.core.telegram_html import sanitize_tg_html

router = Router(name="numerology")

class Form(StatesGroup):
    wait_data = State()  # ожидаем строку: "ФИО; ДД.ММ.ГГГГ"

@router.message(F.text.in_({"✍ Нумерология", "Нумерология", "/numerology"}))
async def entry(msg: Message, state: FSMContext):
    await state.set_state(Form.wait_data)
    await msg.answer(
        "Введите в одной строке: <b>ФИО; ДД.ММ.ГГГГ</b>\n"
        "Пример: <code>Иванов Иван Иванович; 22.07.2001</code>",
        parse_mode="HTML"
    )

@router.message(Form.wait_data)
async def process(msg: Message, state: FSMContext):
    """
    Ожидаем строку: "ФИО; ДД.ММ.ГГГГ"
    Пример: "Иванов Иван Иванович; 22.07.2001"
    """
    text = (msg.text or "").strip()

    # 1) парсинг "ФИО; ДД.ММ.ГГГГ"
    m = re.match(r"^\s*(?P<name>[^;]+?)\s*;\s*(?P<date>\d{2}\.\d{2}\.\d{4})\s*$", text)
    if not m:
        await msg.answer(
            "Похоже, формат не распознан.\n"
            "Введите в одной строке: <b>ФИО; ДД.ММ.ГГГГ</b>\n"
            "Пример: <code>Иванов Иван Иванович; 22.07.2001</code>",
            parse_mode="HTML",
        )
        return

    full_name = m.group("name")
    birth_date_str = m.group("date")

    # 2) валидация даты (и пригодится объект date для БД)
    try:
        birth_date = datetime.strptime(birth_date_str, "%d.%m.%Y").date()
    except ValueError:
        await msg.answer(
            "Дата некорректна. Используйте формат <b>ДД.ММ.ГГГГ</b>, например <code>22.07.2001</code>.",
            parse_mode="HTML",
        )
        return

    # 3) LLM (нумерология)
    try:
        logger.info("[numerology] start name='{}' birth='{}'", full_name, birth_date_str)
        html = analyze_numerology(full_name, birth_date_str)
        html = sanitize_tg_html(html)        # ⬅️ ДО отправки
       
    except Exception:
        logger.exception("numerology LLM failed")
        await msg.answer("Сервис нумерологии временно недоступен. Попробуйте позже.")
        await state.clear()
        return

    # 4) ответ пользователю
    await msg.answer(html, parse_mode="HTML")

    # 5) сохранение в БД (не мешает пользователю)
    try:
        with SessionLocal() as db:
            user = db.query(User).filter_by(tg_id=msg.from_user.id).first()
            if user:
                db.add(
                    NumerologyProfile(
                        user_id=user.id,
                        full_name=full_name,
                        birth_date=birth_date,
                        report_html=html,
                    )
                )
                db.commit()
    except Exception:
        logger.exception("numerology save failed")

    await state.clear()