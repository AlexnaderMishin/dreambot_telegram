# app/bot/main.py
import os
import asyncio
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.bot.ui import main_kb, HELP_TEXT, kb_premium
from app.core.premium import premium_analysis
from app.db.base import SessionLocal
from app.db.models import User, Dream

# платежи
from app.bot.handlers.payments import router as payments_router
# напоминания
from app.bot.handlers.remind import remind_router
from app.bot.reminders import scheduler, bootstrap_existing
# «мои сны»
from app.bot.handlers.dreams import router as dreams_router
# статистика
from app.bot.handlers.stats import router as stats_router
#нумерология
from app.bot.handlers import numerology
#астрология
from app.bot.handlers.astrology import router as astrology_router

class DreamForm(StatesGroup):
    awaiting_text = State()

router = Router(name="main")

async def _analyze_and_reply(m: Message, text: str, user: User) -> None:
    """
    Премиум-единственный путь: сохраняем сон и отвечаем через premium_analysis().
    Никакого базового локального анализа больше не делаем.
    """
    # сохраняем сон сразу
    with SessionLocal() as s:
        db_user = s.query(User).filter_by(id=user.id).one()
        dream = Dream(
            user_id=db_user.id,
            text=text,
            # поля базового анализа больше не заполняем
            symbols=None,
            emotions=None,
            actions=None,
        )
        s.add(dream)
        s.commit()

    # всегда отвечаем премиум-разбором (api или stub — управляется PREMIUM_MODE)
    html = premium_analysis(text)
    await m.answer(html, parse_mode=ParseMode.HTML)

@router.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext) -> None:
    await state.clear()
    await m.answer("Выберите действие:", reply_markup=main_kb())
    await m.answer(HELP_TEXT, parse_mode=ParseMode.HTML)

@router.message(Command("menu"))
async def cmd_menu(m: Message, state: FSMContext) -> None:
    await state.clear()
    await m.answer("Выберите действие:", reply_markup=main_kb())

@router.message(Command("help"))
async def cmd_help(m: Message) -> None:
    await m.answer(HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=main_kb())

@router.message(F.text == "✍ Записать сон")
async def btn_log_dream(m: Message, state: FSMContext) -> None:
    await state.set_state(DreamForm.awaiting_text)
    await m.answer(
        "Опишите сон в нескольких предложениях.\n\n"
        "💡 Подсказка: место/обстановка, 1–2 ключевых образа, что делали вы/другие, главное чувство.",
        reply_markup=main_kb(),
    )

@router.message(DreamForm.awaiting_text, F.text)
async def on_dream_text(m: Message, state: FSMContext) -> None:
    text = (m.text or "").strip()
    if len(text) < 10:
        await m.answer("Нужно чуть подробнее — хотя бы 10–15 символов 😊", reply_markup=main_kb())
        return

    # создаём/получаем пользователя; ВАЖНО: is_premium=True по умолчанию
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).one_or_none()
        if not user:
            user = User(
                tg_id=m.from_user.id,
                username=m.from_user.username or None,
                is_premium=True,            # <- теперь премиум включён на создании
            )
            s.add(user)
            s.commit()
            s.refresh(user)

    await _analyze_and_reply(m, text, user)
    await state.clear()
    await m.answer("Готово ✅", reply_markup=main_kb())

@router.message(F.text == "📜 Мои сны")
async def btn_my_dreams(m: Message) -> None:
    await m.answer("Открыл дневник снов (раздел в разработке).", reply_markup=main_kb())

@router.message(F.text == "📊 Статистика")
async def btn_stats(m: Message) -> None:
    await m.answer("Статистика скоро появится в премиум-версии.", reply_markup=main_kb())

@router.message(F.text == "⭐ Премиум")
async def btn_premium(m: Message) -> None:
    await m.answer(
        "Премиум-доступ. Выберите вариант:",
        reply_markup=kb_premium(),
    )

@router.message(F.text)
async def fallback_show_menu(m: Message, state: FSMContext) -> None:
    cur = await state.get_state()
    if cur:  # если пользователь в ЛЮБОМ состоянии (в т.ч. нумерология) — не мешаем
        return
    await m.answer("Выберите действие:", reply_markup=main_kb())

async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # dp.include_router(payments_router)
    dp.include_router(stats_router)
    dp.include_router(dreams_router)
    dp.include_router(numerology.router)
    dp.include_router(astrology_router)
    dp.include_router(remind_router)
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)

    if not scheduler.running:
        scheduler.start()

    bootstrap_existing(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
