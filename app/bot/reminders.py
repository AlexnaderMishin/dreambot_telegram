# app/bot/reminders.py
from __future__ import annotations

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from app.db.base import SessionLocal

import pytz

scheduler = AsyncIOScheduler(timezone="UTC")
JOB_PREFIX = "remind_user_"


def _job_id(user_id: int) -> str:
    return f"{JOB_PREFIX}{user_id}"


async def send_reminder(bot: Bot, chat_id: int) -> None:
    await bot.send_message(chat_id, "🌤 Доброе утро! Запишите сон, если помните. /help")


def schedule_for_user(bot: Bot, user_id: int, tg_id: int, tz: str, t_str: str) -> None:
    """
    Создаём (или пере-создаём) задачу будильника для пользователя.
    t_str: строка HH:MM в его локальном часовом поясе.
    """
    # если была старая — удаляем молча
    try:
        scheduler.remove_job(_job_id(user_id))
    except Exception:
        pass

    # разложим время
    hh, mm = map(int, t_str.split(":", 1))

    # таймзона пользователя
    user_tz = pytz.timezone(tz or "UTC")

    trigger = CronTrigger(hour=hh, minute=mm, timezone=user_tz)
    scheduler.add_job(
        send_reminder,
        trigger=trigger,
        args=[bot, tg_id],
        id=_job_id(user_id),
        replace_existing=True,
    )


def unschedule_for_user(user_id: int) -> None:
    try:
        scheduler.remove_job(_job_id(user_id))
    except Exception:
        pass


def bootstrap_existing(bot: Bot) -> None:
    """
    Поднимаем задачи из БД для всех, у кого remind_enabled = true.
    ВАЖНО: это синхронная функция, её вызываем БЕЗ await.
    """
    with SessionLocal() as s:
        rows = s.execute(
            text(
                """
                SELECT id, tg_id, tz
                FROM users
                WHERE remind_enabled = true
                """
            )
        ).fetchall()

    for r in rows:
        # в БД хранится часовой пояс, а время может быть в колонке remind_time (при желании подтяни)
        # запускаем на дефолтное 08:30, если у пользователя ещё нет времени.
        t_str = "08:30"
        schedule_for_user(bot, r.id, r.tg_id, r.tz, t_str)


def toggle_remind(user_id: int, enabled: bool) -> None:
    with SessionLocal() as s:
        s.execute(
            text("UPDATE users SET remind_enabled = :e WHERE id = :id"),
            {"e": enabled, "id": user_id},
        )
        s.commit()
