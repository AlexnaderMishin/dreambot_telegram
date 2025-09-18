# app/bot/handlers/remind.py
from __future__ import annotations

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import time

from sqlalchemy import text

from app.db.base import SessionLocal
from app.db.models import User
from app.bot.reminders import (
    schedule_for_user,
    unschedule_for_user,
    toggle_remind,
)

# чтобы текст кнопок совпадал с главным меню и взять наше новое инлайн-меню
from app.bot.ui import REMIND_BTN, reminders_menu_kb

remind_router = Router(name="remind")
__all__ = ["remind_router"]

# ==========================
# Вспомогательные утилиты
# ==========================

def _t_to_str(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"

def _clamp_hour(h: int) -> int:
    return (h + 24) % 24

def _clamp_min(m: int) -> int:
    return (m + 60) % 60

def _kb_time_picker(h: int, m: int, *, prefix: str) -> types.InlineKeyboardMarkup:
    """
    Инлайн «форма» выбора времени.
    prefix:
      'd' — выбор времени для сна (dream)
      'a' — выбор времени для астропрогноза (astro)
    """
    preview = types.InlineKeyboardButton(text=f"🕒 {h:02d}:{m:02d}", callback_data=f"{prefix}:tp:nop")
    dec_h  = types.InlineKeyboardButton(text="− час", callback_data=f"{prefix}:tp:dec_h:{h}:{m}")
    inc_h  = types.InlineKeyboardButton(text="+ час", callback_data=f"{prefix}:tp:inc_h:{h}:{m}")
    dec_m  = types.InlineKeyboardButton(text="− мин", callback_data=f"{prefix}:tp:dec_m:{h}:{m}")
    inc_m  = types.InlineKeyboardButton(text="+ мин", callback_data=f"{prefix}:tp:inc_m:{h}:{m}")
    ok     = types.InlineKeyboardButton(text="✅ Сохранить", callback_data=f"{prefix}:tp:save:{h}:{m}")
    cancel = types.InlineKeyboardButton(text="✖ Отмена", callback_data=f"{prefix}:tp:cancel")

    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [dec_h, preview, inc_h],
            [dec_m, ok, inc_m],
            [cancel],
        ]
    )

def _parse_tp(data: str) -> tuple[str, int | None, int | None]:
    """
    Разбор callback_data вида: '<prefix>:tp:<action>[:h][:m]'.
    Возвращает (action, h, m) — h/m могут быть None.
    Префикс ('d' или 'a') уже отфильтрован в хэндлере.
    """
    parts = data.split(":")
    # e.g. ['d','tp','inc_h','09','30']
    action = parts[2] if len(parts) > 2 else "nop"
    h = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    m = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else None
    return action, h, m


# =========================================
# Точка входа: кнопка «Напоминания» и /remind
# =========================================

@remind_router.message(F.text == REMIND_BTN)
@remind_router.message(Command("remind"))
async def open_remind_menu(message: types.Message, state: FSMContext):
    """
    Показываем пользователю инлайн-меню напоминаний (сон + астрология).
    Время и переключатели читаем из БД.
    """
    tg_id = message.from_user.id

    with SessionLocal() as s:
        row = s.execute(
            text("""
                SELECT
                    remind_time,
                    notify_daily_time,
                    COALESCE(notify_moon_phase, TRUE) AS moon_on
                FROM users
                WHERE tg_id = :tg
            """),
            {"tg": tg_id},
        ).mappings().first()

    if not row:
        await message.answer("Сначала /start.")
        return

    # dream_time из поля time -> приводим к 'HH:MM'
    dream_time = row["remind_time"].strftime("%H:%M") if row["remind_time"] else None
    astro_time = row["notify_daily_time"]  # уже строка или None
    moon_on = bool(row["moon_on"])

    kb = reminders_menu_kb(dream_time=dream_time, astro_time=astro_time, moon_phase_on=moon_on)
    await message.answer("🔔 Напоминания", reply_markup=kb.as_markup())


# =========================================
# Меню: обработчики трёх пунктов
# =========================================

@remind_router.callback_query(F.data == "rem:dream:open")
async def open_dream_time(q: types.CallbackQuery):
    tg_id = q.from_user.id
    with SessionLocal() as s:
        row = s.execute(text("SELECT remind_time FROM users WHERE tg_id=:tg"),
                        {"tg": tg_id}).mappings().first()
    if row and row["remind_time"]:
        h, m = row["remind_time"].hour, row["remind_time"].minute
    else:
        h, m = 8, 30

    await q.message.edit_text(
        "Выберите время (локальное для вашего часового пояса):",
        reply_markup=_kb_time_picker(h, m, prefix="d"),
    )
    await q.answer()


@remind_router.callback_query(F.data == "rem:astro:open")
async def open_astro_time(q: types.CallbackQuery):
    tg_id = q.from_user.id
    with SessionLocal() as s:
        row = s.execute(text("SELECT notify_daily_time FROM users WHERE tg_id=:tg"),
                        {"tg": tg_id}).mappings().first()
    if row and row["notify_daily_time"]:
        try:
            h, m = map(int, row["notify_daily_time"].split(":"))
        except Exception:
            h, m = 9, 0
    else:
        h, m = 9, 0

    await q.message.edit_text(
        "Выберите время (локальное для вашего часового пояса):",
        reply_markup=_kb_time_picker(h, m, prefix="a"),
    )
    await q.answer()


@remind_router.callback_query(F.data == "rem:moon:toggle")
async def toggle_moon_phase(q: types.CallbackQuery):
    tg_id = q.from_user.id
    with SessionLocal() as s:
        rec = s.execute(
            text("SELECT COALESCE(notify_moon_phase, TRUE) AS on FROM users WHERE tg_id=:tg"),
            {"tg": tg_id},
        ).mappings().first()
        new_val = not bool(rec["on"]) if rec else True
        s.execute(text("UPDATE users SET notify_moon_phase=:v WHERE tg_id=:tg"),
                  {"v": new_val, "tg": tg_id})
        # перечитать для перерисовки меню
        row = s.execute(
            text("""
                SELECT
                    remind_time,
                    notify_daily_time,
                    COALESCE(notify_moon_phase, TRUE) AS moon_on
                FROM users
                WHERE tg_id=:tg
            """),
            {"tg": tg_id},
        ).mappings().first()
        s.commit()

    dream_time = row["remind_time"].strftime("%H:%M") if row["remind_time"] else None
    astro_time = row["notify_daily_time"]
    kb = reminders_menu_kb(dream_time=dream_time, astro_time=astro_time, moon_phase_on=bool(row["moon_on"]))
    await q.message.edit_text("🔔 Напоминания", reply_markup=kb.as_markup())
    await q.answer("Настройка сохранена")


# =========================================
# Обработка инлайн-колёсика времени
#   d:tp:* — для сна
#   a:tp:* — для астропрогноза
# =========================================

@remind_router.callback_query(F.data.startswith("d:tp:"))
async def on_timepicker_dream(q: types.CallbackQuery):
    prefix = "d"
    action, h, m = _parse_tp(q.data)

    cur_h, cur_m = (h if h is not None else 8), (m if m is not None else 30)

    if action == "nop":
        await q.answer()
        return
    if action == "cancel":
        # возвращаемся в меню «Напоминания»
        await _back_to_reminders_menu(q)
        return

    if action in {"inc_h", "dec_h", "inc_m", "dec_m"}:
        if action == "inc_h":
            cur_h = _clamp_hour(cur_h + 1)
        elif action == "dec_h":
            cur_h = _clamp_hour(cur_h - 1)
        elif action == "inc_m":
            cur_m = _clamp_min(cur_m + 5)
        elif action == "dec_m":
            cur_m = _clamp_min(cur_m - 5)
        await q.message.edit_reply_markup(reply_markup=_kb_time_picker(cur_h, cur_m, prefix=prefix))
        await q.answer()
        return

    if action == "save":
        tg_id = q.from_user.id
        picked = time(cur_h, cur_m)

        with SessionLocal() as s:
            user = s.query(User).filter(User.tg_id == tg_id).first()
            if not user:
                await q.answer("Сначала /start", show_alert=True)
                return
            user.remind_time = picked
            user.remind_enabled = True
            s.commit()
            # пересоздаём задачу
            try:
                unschedule_for_user(user.id)
            except Exception:
                pass
            schedule_for_user(q.bot, user.id, user.tg_id, user.tz, _t_to_str(picked))

        await _back_to_reminders_menu(q, toast="Время для записи снов сохранено")
        return

    await q.answer()


@remind_router.callback_query(F.data.startswith("a:tp:"))
async def on_timepicker_astro(q: types.CallbackQuery):
    prefix = "a"
    action, h, m = _parse_tp(q.data)

    cur_h, cur_m = (h if h is not None else 9), (m if m is not None else 0)

    if action == "nop":
        await q.answer()
        return
    if action == "cancel":
        await _back_to_reminders_menu(q)
        return

    if action in {"inc_h", "dec_h", "inc_m", "dec_m"}:
        if action == "inc_h":
            cur_h = _clamp_hour(cur_h + 1)
        elif action == "dec_h":
            cur_h = _clamp_hour(cur_h - 1)
        elif action == "inc_m":
            cur_m = _clamp_min(cur_m + 5)
        elif action == "dec_m":
            cur_m = _clamp_min(cur_m - 5)
        await q.message.edit_reply_markup(reply_markup=_kb_time_picker(cur_h, cur_m, prefix=prefix))
        await q.answer()
        return

    if action == "save":
        tg_id = q.from_user.id
        t_str = f"{cur_h:02d}:{cur_m:02d}"
        with SessionLocal() as s:
            s.execute(text("UPDATE users SET notify_daily_time=:t WHERE tg_id=:tg"),
                      {"t": t_str, "tg": tg_id})
            s.commit()

        await _back_to_reminders_menu(q, toast="Время ежедневного астропрогноза сохранено")
        return

    await q.answer()


# ===== helpers =====

async def _back_to_reminders_menu(q: types.CallbackQuery, toast: str | None = None):
    """Перерисовать главное меню «Напоминания» после действий."""
    tg_id = q.from_user.id
    with SessionLocal() as s:
        row = s.execute(
            text("""
                SELECT
                    remind_time,
                    notify_daily_time,
                    COALESCE(notify_moon_phase, TRUE) AS moon_on
                FROM users
                WHERE tg_id=:tg
            """),
            {"tg": tg_id},
        ).mappings().first()

    dream_time = row["remind_time"].strftime("%H:%M") if row["remind_time"] else None
    astro_time = row["notify_daily_time"]
    kb = reminders_menu_kb(dream_time=dream_time, astro_time=astro_time, moon_phase_on=bool(row["moon_on"]))

    await q.message.edit_text("🔔 Напоминания", reply_markup=kb.as_markup())
    if toast:
        await q.answer(toast)
    else:
        await q.answer()
