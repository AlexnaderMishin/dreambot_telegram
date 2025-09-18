# app/jobs/astrology_notifications.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable, Optional, Callable

from aiogram import Bot
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.core.astrology_math import moon_phase
from app.db.models import User  # путь верный в твоём проекте


# --------- helpers ---------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _should_fire_daily(now_local: datetime, hhmm: Optional[str]) -> bool:
    if not hhmm:
        return False
    try:
        hh, mm = map(int, hhmm.split(":"))
        return now_local.hour == hh and now_local.minute == mm
    except Exception:
        return False


# --------- 1) Уведомление при смене фазы Луны ---------

def check_moon_phase_changes(*, bot: Bot | None, session_maker: Callable[[], Session], batch_size: int = 1000) -> None:
    """
    Дёргать каждые 30 минут.
    Синхронная версия под SessionLocal().
    """
    if bot is None:
        return  # бот ещё не передан — подождём bootstrap_existing()

    offset = 0
    while True:
        with session_maker() as s:
            users: Iterable[User] = s.execute(
                select(User)
                .where(User.notify_moon_phase.is_(True))
                .offset(offset)
                .limit(batch_size)
            ).scalars().all()

            if not users:
                break

            now = _now_utc()
            phase_label, day, emoji = moon_phase(now)

            for u in users:
                if hasattr(u, "remind_enabled") and not u.remind_enabled:
                    continue

                # первый запуск: инициализируем без отправки
                if not u.last_moon_phase:
                    s.execute(
                        update(User)
                        .where(User.id == u.id)
                        .values(last_moon_phase=phase_label, last_moon_day=day)
                    )
                    continue

                if u.last_moon_phase != phase_label:
                    try:
                        bot.send_message(
                            chat_id=u.tg_id,
                            text=(
                                f"{emoji} Сегодня началась новая фаза Луны — <b>{phase_label}</b> {emoji}\n\n"
                                "Загляните за свежим астропрогнозом в боте ✨"
                            ),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

                    s.execute(
                        update(User)
                        .where(User.id == u.id)
                        .values(last_moon_phase=phase_label, last_moon_day=day)
                    )

            s.commit()

        offset += batch_size


# --------- 2) Ежедневное утреннее уведомление ---------

def send_daily_astro_ping(*, bot: Bot | None, session_maker: Callable[[], Session], batch_size: int = 1000) -> None:
    """
    Дёргать каждые 5 минут.
    Синхронная версия под SessionLocal().
    """
    if bot is None:
        return

    offset = 0
    while True:
        with session_maker() as s:
            users: Iterable[User] = s.execute(
                select(User)
                .where(User.notify_daily_time.isnot(None))
                .offset(offset)
                .limit(batch_size)
            ).scalars().all()

            if not users:
                break

            now_utc = _now_utc()

            for u in users:
                if hasattr(u, "remind_enabled") and not u.remind_enabled:
                    continue

                tz_str = getattr(u, "tz", None) or "UTC"
                try:
                    tz = ZoneInfo(tz_str)
                except Exception:
                    tz = ZoneInfo("UTC")

                now_local = now_utc.astimezone(tz)
                if not _should_fire_daily(now_local, u.notify_daily_time):
                    continue

                phase_label, day, emoji = moon_phase(now_utc)

                try:
                    bot.send_message(
                        chat_id=u.tg_id,
                        text=f"Доброе утро! Сейчас {phase_label} {emoji}. Получить астропрогноз на сегодня?",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        offset += batch_size
