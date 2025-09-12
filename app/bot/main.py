import os
import asyncio
from typing import Optional, List
from aiogram import Router
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.bot.ui import main_kb, HELP_TEXT, kb_premium

# ядро / анализ / БД
from app.core.nlp import analyze_dream, Analysis
from app.core.premium import premium_analysis
from app.db.base import SessionLocal
from app.db.models import User, Dream

# платежи
from app.bot.handlers.payments import router as payments_router

# напоминания
# from app.bot.handlers.remind import router as remind_router
from app.bot.handlers.remind import remind_router
from app.bot.reminders import scheduler, bootstrap_existing

# основной роутер приложения

# from app.bot.handlers.main import router as main_router
# ===================== FSM-состояния =====================

class DreamForm(StatesGroup):
    awaiting_text = State()


# ===================== Роутер =====================

router = Router(name="main")


# ===================== Вспомогательные функции =====================

def _format_basic_reply(*, analysis: Analysis, redis_url: Optional[str]) -> str:
    """
    Не меняем вашу логику форматирования — используем то, что уже было
    (в проекте функция так и называется). Оставим небольшой прокси
    на случай, если импортировать её здесь неудобно.
    """
    # В проекте у вас уже есть готовый форматтер (format_basic_reply).
    # Чтобы не дублировать код, импортируем его здесь локально:
    from app.core.nlp import format_basic_reply
    return format_basic_reply(analysis=analysis, redis_url=redis_url)


async def _analyze_and_reply(m: Message, text: str, user: User) -> None:
    """
    Общая точка: посчитать локальный анализ, сохранить запись в БД,
    а затем отдать премиум или базовый ответ.
    """
    # 1) Всегда считаем локальный анализ — он нужен и для статистики, и как фолбэк
    analysis = analyze_dream(text, redis_url=os.getenv("REDIS_URL"))

    # 2) Сохраняем запись сна
    with SessionLocal() as s:
        # рефрешим пользователя из сессии (на случай DetachedInstanceError)
        db_user = s.query(User).filter_by(id=user.id).one()
        dream = Dream(
            user_id=db_user.id,
            text=text,
            symbols=analysis.symbols,
            emotions=analysis.emotions,
            actions=analysis.actions,
        )
        s.add(dream)
        s.commit()

    # 3) Выбираем режим ответа
    premium_mode = os.getenv("PREMIUM_MODE", "stub").lower()

    if user.is_premium and premium_mode in {"api", "stub"}:
        # Внутри premium_analysis уже есть логика:
        # - если PREMIUM_MODE=api → реальный вызов OpenAI
        # - иначе аккуратный демо-ответ
        html = premium_analysis(text)
        await m.answer(html, parse_mode=ParseMode.HTML)
        return

    # 4) Базовый ответ
    html = _format_basic_reply(analysis=analysis, redis_url=os.getenv("REDIS_URL"))
    await m.answer(html, parse_mode=ParseMode.HTML)


# ===================== Хэндлеры команд/кнопок =====================

@router.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext) -> None:
    """
    Показываем главное меню сразу при первом контакте.
    """
    await state.clear()
    await m.answer("Выберите действие:", reply_markup=main_kb())
    # Подсказываем, что умеет бот (единожды – при /start удобно)
    await m.answer(HELP_TEXT, parse_mode=ParseMode.HTML)


@router.message(Command("menu"))
async def cmd_menu(m: Message, state: FSMContext) -> None:
    """
    Явный показ меню.
    """
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

    # Получаем/создаём пользователя
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).one_or_none()
        if not user:
            user = User(tg_id=m.from_user.id, username=m.from_user.username or None)
            s.add(user)
            s.commit()
            s.refresh(user)

    # Анализируем и отвечаем
    await _analyze_and_reply(m, text, user)
    await state.clear()
    # После ответа — снова показываем меню
    await m.answer("Готово ✅", reply_markup=main_kb())


# ===== Низкоприоритетные «помогающие» хэндлеры =====

@router.message(F.text == "📜 Мои сны")
async def btn_my_dreams(m: Message) -> None:
    # тут остаётся ваша реализация показа дневника; показываем меню для консистентности
    await m.answer("Открыл дневник снов (раздел в разработке).", reply_markup=main_kb())


@router.message(F.text == "📊 Статистика")
async def btn_stats(m: Message) -> None:
    await m.answer("Статистика скоро появится в премиум-версии.", reply_markup=main_kb())


# @router.message(F.text == "🔔 Напоминания")
# async def btn_reminders(m: Message) -> None:
#     await m.answer("Напоминания можно настроить в следующем релизе.", reply_markup=main_kb())


@router.message(F.text == "⭐ Премиум")
async def btn_premium(m: Message) -> None:
    await m.answer(
        "Премиум-доступ. Выберите вариант:",
        reply_markup=kb_premium(),         # <— показываем премиум-клавиатуру
    )


# ===== Самый низкий приоритет: любой другой текст → показать меню =====

@router.message(F.text)
async def fallback_show_menu(m: Message, state: FSMContext) -> None:
    """
    Если пользователь прислал что-то вне сценария (или впервые зашёл в чат без /start),
    мы не теряемся, а мягко возвращаем его к основному меню.
    """
    # если пользователь в процессе ввода сна — не перехватываем
    cur = await state.get_state()
    if cur == DreamForm.awaiting_text.state:
        return
    await m.answer("Выберите действие:", reply_markup=main_kb())


# ===================== Точка входа =====================

async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

# роутеры
    
    dp.include_router(payments_router)
    dp.include_router(remind_router)  # кнопка «Напоминания»
    dp.include_router(router) 

# webhooks off
    await bot.delete_webhook(drop_pending_updates=True)

# планировщик поднимаем один раз
    if not scheduler.running:
        scheduler.start()

# поднимаем задачи из БД (синхронная, БЕЗ await)
    bootstrap_existing(bot)

# poll
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





