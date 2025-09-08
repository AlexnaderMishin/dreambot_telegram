# app/bot/main.py
from __future__ import annotations

import os
import asyncio
from typing import List, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

# Внешние роутеры
from app.bot.handlers.symbol import router as symbol_router
from app.bot.handlers.stats import router as stats_router
from app.bot.handlers.note import router as note_router
from app.bot.handlers.remind import router as remind_router

# Планировщик напоминаний
from app.bot.reminders import scheduler, bootstrap_existing

# Локальная логика
from app.core.nlp import analyze_dream, EmotionsCache
from app.db.base import SessionLocal
from app.db.models import User, Dream

# Премиум (демо-режим, HTML-ответ)
from app.core.premium import premium_analysis


# -------------------- ЛОКАЛЬНЫЕ ХЕНДЛЕРЫ ЧЕРЕЗ ROUTER --------------------
existing_router = Router()


@existing_router.message(CommandStart())
async def start_cmd(m: Message) -> None:
    """Приветствие + регистрация пользователя при первом контакте."""
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=m.from_user.id).one_or_none()
        if not user:
            user = User(tg_id=m.from_user.id, username=m.from_user.username or None)
            s.add(user)
            s.commit()

    await m.answer(
        "Привет! Я — <b>Помощник сновидений</b>.\n"
        "Просто пришлите текст вашего сна — я выделю символы и эмоции и сохраню запись в дневник.\n\n"
        "Команды: /help",
        parse_mode=ParseMode.HTML,
    )


@existing_router.message(Command("help"))
async def help_cmd(m: Message) -> None:
    await m.answer(
        "<b>Команды</b>\n"
        "/start — приветствие\n"
        "/help — помощь\n"
        "/symbol &lt;слово&gt; — значение символа\n"
        "/stats — статистика за 7/30 дней\n"
        "/remind — включить/выключить напоминания\n"
        "/note &lt;текст&gt; — добавить заметку к последнему сну",
        parse_mode=ParseMode.HTML,
    )


@existing_router.message(Command("myid"))
async def myid_cmd(m: Message) -> None:
    await m.answer(f"Ваш tg_id: <code>{m.from_user.id}</code>", parse_mode=ParseMode.HTML)


# ---------- ВСПОМОГАТЕЛЬНОЕ: форматирование базового ответа ----------
def format_basic_reply(
    *,
    analysis,
    redis_url: Optional[str] = None,
) -> str:
    """Строит HTML-ответ для базового (локального) анализа."""
    # 1) Символы
    sym_lines: List[str] = [
        f"✧ <b>{s['key']}</b> — {s['meaning']}" for s in analysis.symbols
    ] or ["— не найдено"]

    # 2) Эмоции + КОПИНГ, если символов нет
    emo_cache = EmotionsCache(redis_url=redis_url)
    emotions_map = emo_cache.get() or {}

    emo_lines: List[str] = []
    if analysis.emotions:
        for e in analysis.emotions:
            emo_lines.append(f"✧ {e}")

    # 3) Действия (из символов)
    act_lines: List[str] = [f"✧ {a}" for a in analysis.actions] or ["— нет рекомендаций"]

    # 4) Архетипы и общий смысл
    arch_lines: List[str] = [f"✧ {a}" for a in analysis.archetypes] or []
    summary_line: str = analysis.summary.strip() if analysis.summary else ""

    parts: List[str] = [
        "<b>Базовый разбор сна</b>",
        "🌸 <b>Символы</b>\n" + "\n".join(sym_lines),
    ]

    # Эмоции (если есть)
    if analysis.emotions:
        parts.append("🥲 <b>Эмоции</b>\n" + "\n".join(emo_lines))

    # Если символов нет, а эмоции есть — добавляем описание и копинг из ТОП-эмоции
    if not analysis.symbols and analysis.emotions:
        top = analysis.emotions[0]
        edata = emotions_map.get(top, {}) or {}
        desc = (edata.get("description") or "").strip()
        coping = [c for c in (edata.get("coping") or []) if c][:3]
        extra = []
        if desc:
            extra.append(f"— {desc}")
        if coping:
            extra.append("🧰 <b>Что поможет сейчас</b>\n" + "\n".join(f"✧ {c}" for c in coping))
        if extra:
            parts.append("\n".join(extra))

    # Архетипы
    if arch_lines:
        parts.append("📜 <b>Архетипические темы</b>\n" + "\n".join(arch_lines))

    # Общий смысл
    if summary_line:
        parts.append("🧠 <b>Общий смысл</b>\n" + summary_line)

    # Действия
    parts.append("✅ <b>Действия</b>\n" + "\n".join(act_lines))

    # Подсказка «как описывать сон» (когда данных мало)
    if len(analysis.symbols) == 0 or len(analysis.emotions) == 0:
        parts.append(
            "💡 <i>Чтобы следующий разбор был точнее, попробуйте в описании отметить:"
            " место/обстановку, 1–2 ключевых предмета или существа,"
            " что делали вы/другие и главное чувство (страх, радость, тревога…)</i>"
        )

    # Мягкий кризис-блок (если сработал)
    if analysis.crisis:
        crisis_blk = [
            "⚠️ <b>Похоже, сейчас вам непросто.</b>",
            "Вы не одиноки. Если чувствуете сильное напряжение или тревогу — подумайте о том, чтобы поговорить с близким человеком или со специалистом.",
        ]
        if analysis.crisis_help:
            crisis_blk.append(analysis.crisis_help)
        crisis_blk.append("<b>Полезные ресурсы:</b>")
        crisis_blk.append("• Экстренная помощь: <code>112</code>")
        crisis_blk.append("• Линия доверия: 8-800-2000-122")
        crisis_blk.append("• Чат-поддержка: https://help.example.org")
        parts.append("\n".join(crisis_blk))

    parts.append("\n<i>Информация носит поддерживающий характер и не является диагнозом.</i>")

    return "\n\n".join(parts)


@existing_router.message(F.text & ~F.via_bot & ~F.text.startswith("/"))
async def on_dream(m: Message) -> None:
    """Принимаем текст сна, анализируем и сохраняем в БД.
       Если пользователь premium — отправляем альтернативный (премиум) ответ.
    """
    tg_id = m.from_user.id
    username = m.from_user.username
    text = (m.text or "").strip()

    if len(text) < 10:
        await m.answer(
            "Пришлите, пожалуйста, более развёрнутое описание сна (минимум 10 символов)."
        )
        return

    # Всё — внутри одной сессии, чтобы не получать detached-объекты
    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=tg_id).one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=username or None)
            s.add(user)
            s.flush()  # чтобы появился user.id

        # Флаг премиума читаем пока сессия ЖИВА
        is_premium: bool = bool(getattr(user, "is_premium", False))

        # Считаем локальный анализ (он нужен и премиуму для логов/статистики/БД)
        analysis = analyze_dream(text, redis_url=os.getenv("REDIS_URL"))

        # Сохраняем запись сна
        dream = Dream(
            user_id=user.id,
            text=text,
            symbols=analysis.symbols,
            emotions=analysis.emotions,
            actions=analysis.actions,
        )
        s.add(dream)
        s.commit()

    # После закрытия сессии — только формирование ответа
    if is_premium:
        reply_text = premium_analysis(text)  # внутри сама решит: API или демо
    else:
        reply_text = format_basic_reply(
            analysis=analysis,
            redis_url=os.getenv("REDIS_URL"),
        )

    await m.answer(reply_text, parse_mode=ParseMode.HTML)

# ------------------------------ Точка входа -------------------------------
async def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Подключаем роутеры
    dp.include_router(existing_router)
    dp.include_router(symbol_router)
    dp.include_router(stats_router)
    dp.include_router(note_router)
    dp.include_router(remind_router)

    # Планировщик напоминаний
    scheduler.start()
    bootstrap_existing(bot)

    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
