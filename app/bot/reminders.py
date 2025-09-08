import pytz
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text
from app.db.base import SessionLocal

scheduler = AsyncIOScheduler(timezone="UTC")
JOB_PREFIX = "remind_user_"

def job_id(user_id: int) -> str:
    return f"{JOB_PREFIX}{user_id}"

async def send_reminder(bot: Bot, chat_id: int):
    await bot.send_message(chat_id, "📝 Доброе утро! Запишите сон, если помните. /help")

def schedule_for_user(bot: Bot, user_id: int, tg_id: int, tz: str):
    try:
        # удалим старую, если есть
        try:
            scheduler.remove_job(job_id(user_id))
        except Exception:
            pass
        # локальное время 08:30
        trigger = CronTrigger(hour=8, minute=30, timezone=pytz.timezone(tz))
        scheduler.add_job(send_reminder, trigger, args=[bot, tg_id], id=job_id(user_id), replace_existing=True)
    except Exception as e:
        print("schedule error:", e)

def unschedule_for_user(user_id: int):
    try:
        scheduler.remove_job(job_id(user_id))
    except Exception:
        pass

def bootstrap_existing(bot: Bot):
    # вызываем на старте бота
    with SessionLocal() as s:
        rows = s.execute(text("""
            SELECT id, tg_id, tz FROM users WHERE remind_enabled = true
        """)).fetchall()
        for r in rows:
            schedule_for_user(bot, r.id, r.tg_id, r.tz)

def toggle_remind(user_id: int, enabled: bool):
    with SessionLocal() as s:
        s.execute(text("UPDATE users SET remind_enabled = :e WHERE id = :id"),
                  {"e": enabled, "id": user_id})
        s.commit()
