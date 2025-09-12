# app/bot/reminders.py
from __future__ import annotations

import pytz
from datetime import time as dtime
from typing import Optional

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.db.base import SessionLocal
from app.db.models import User

# единый планировщик процесса бота
scheduler = AsyncIOScheduler(timezone="UTC")
JOB_PREFIX = "remind_user_"


def job_id(user_id: int) -> str:
    return f"{JOB_PREFIX}{user_id}"


async def send_reminder(bot: Bot, chat_id: int):
    # одно простое напоминание; текст при необходимости поменяйте
    await bot.send_message(chat_id, "📝 Доброе утро! Запишите сон, если помните. /help")


def _parse_time_to_hm(t: Optional[dtime]) -> tuple[int, int]:
    if not t:
        return 8, 30
    return t.hour, t.minute


def unschedule_for_user(user_id: int) -> None:
    try:
        scheduler.remove_job(job_id(user_id))
    except Exception:
        pass


def schedule_for_user(bot: Bot, user_id: int, tg_id: int, tz: str, remind_time: Optional[dtime]) -> None:
    """Создаёт/пересоздаёт задачу напоминания для пользователя."""
    # сначала убираем старую
    unschedule_for_user(user_id)

    hour, minute = _parse_time_to_hm(remind_time)
    trigger = CronTrigger(hour=hour, minute=minute, timezone=pytz.timezone(tz or "UTC"))
    scheduler.add_job(
        send_reminder,
        trigger=trigger,
        args=[bot, tg_id],
        id=job_id(user_id),
        replace_existing=True,
        misfire_grace_time=60 * 30,  # 30 минут
    )


def toggle_remind(user_id: int, enabled: bool) -> None:
    with SessionLocal() as s:
        s.execute(text("UPDATE users SET remind_enabled = :e WHERE id = :id"), {"e": enabled, "id": user_id})
        s.commit()


def bootstrap_existing(bot: Bot) -> None:
    """Поднимаем напоминания для всех, у кого remind_enabled = true."""
    with SessionLocal() as s:
        rows = s.execute(
            text(
                """
                SELECT id, tg_id, tz, remind_time
                FROM users
                WHERE remind_enabled = true
                """
            )
        ).fetchall()

    for r in rows:
        schedule_for_user(
            bot=bot,
            user_id=r.id,
            tg_id=r.tg_id,
            tz=r.tz or "UTC",
            remind_time=r.remind_time,
        )
