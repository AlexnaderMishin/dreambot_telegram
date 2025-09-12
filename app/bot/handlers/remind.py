# app/bot/handlers/remind.py
from __future__ import annotations

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import time

from app.db.base import SessionLocal
from app.db.models import User
from app.bot.reminders import (
    schedule_for_user,
    unschedule_for_user,
    toggle_remind,
)

# чтобы текст кнопок совпадал с главным меню
from app.bot.ui import REMIND_BTN, HELP_TEXT

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

def _kb_time_picker(h: int, m: int) -> types.InlineKeyboardMarkup:
    """
    Инлайн «форма» выбора времени.
    """
    preview = types.InlineKeyboardButton(text=f"🕒 {h:02d}:{m:02d}", callback_data="tp:nop")
    dec_h = types.InlineKeyboardButton(text="− час", callback_data=f"tp:dec_h:{h}:{m}")
    inc_h = types.InlineKeyboardButton(text="+ час", callback_data=f"tp:inc_h:{h}:{m}")
    dec_m = types.InlineKeyboardButton(text="− мин", callback_data=f"tp:dec_m:{h}:{m}")
    inc_m = types.InlineKeyboardButton(text="+ мин", callback_data=f"tp:inc_m:{h}:{m}")
    ok    = types.InlineKeyboardButton(text="✅ Сохранить", callback_data=f"tp:save:{h}:{m}")
    cancel= types.InlineKeyboardButton(text="✖ Отмена", callback_data="tp:cancel")

    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [dec_h, preview, inc_h],
            [dec_m, ok, inc_m],
            [cancel],
        ]
    )


def _parse_tp(data: str) -> tuple[str, int | None, int | None]:
    """
    Разбор callback_data вида: 'tp:<action>[:h][:m]'.
    Возвращает (action, h, m) — h/m могут быть None.
    """
    parts = data.split(":")
    # tp, action, (maybe h), (maybe m)
    action = parts[1] if len(parts) > 1 else "nop"
    h = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    m = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    return action, h, m


# =========================================
# Точка входа: кнопка «Напоминания» и /remind
# =========================================

@remind_router.message(F.text == REMIND_BTN)
@remind_router.message(Command("remind"))
async def open_remind_menu(message: types.Message, state: FSMContext):
    """
    Показываем пользователю инлайн форму выбора времени.
    Стартовое значение берём из БД (remind_time) — иначе 08:30.
    """
    tg_id = message.from_user.id

    with SessionLocal() as s:
        user = s.query(User).filter(User.tg_id == tg_id).first()

    if not user:
        await message.answer("Сначала /start.")
        return

    t: time = user.remind_time or time(8, 30)
    await message.answer(
        "🔔 Напоминания\n\n"
        "Выберите удобное время (локальное для вашего часового пояса):",
        reply_markup=_kb_time_picker(t.hour, t.minute),
    )


# =========================================
# Обработка инлайн-кнопок «формы»
# =========================================

@remind_router.callback_query(F.data.startswith("tp:"))
async def on_timepicker_callback(q: types.CallbackQuery):
    action, h, m = _parse_tp(q.data)

    # для безопасного fallback (когда нет h/m в колбэке)
    cur_h, cur_m = 8, 30
    if h is not None and m is not None:
        cur_h, cur_m = h, m

    if action == "nop":
        await q.answer()
        return

    if action == "cancel":
        await q.message.edit_text("Настройка напоминаний отменена.")
        await q.answer()
        return

    # изменение часа/минут
    if action in {"inc_h", "dec_h", "inc_m", "dec_m"}:
        if action == "inc_h":
            cur_h = _clamp_hour(cur_h + 1)
        elif action == "dec_h":
            cur_h = _clamp_hour(cur_h - 1)
        elif action == "inc_m":
            cur_m = _clamp_min(cur_m + 5)
        elif action == "dec_m":
            cur_m = _clamp_min(cur_m - 5)

        await q.message.edit_reply_markup(reply_markup=_kb_time_picker(cur_h, cur_m))
        await q.answer()
        return

    # сохранение
    if action == "save":
        tg_id = q.from_user.id

        with SessionLocal() as s:
            user = s.query(User).filter(User.tg_id == tg_id).first()
            if not user:
                await q.answer("Сначала /start", show_alert=True)
                return

            # сохраняем время и включаем напоминания
            picked = time(cur_h, cur_m)
            user.remind_time = picked
            user.remind_enabled = True
            s.commit()

            # пересоздаём задачу
            try:
                unschedule_for_user(user.id)
            except Exception:
                pass

            # user.tz — строка таймзоны из БД (например, "Europe/Moscow")
            t_str = _t_to_str(picked)  # "HH:MM"
            schedule_for_user(q.bot, user.id, user.tg_id, user.tz, t_str)


        await q.message.edit_text(
            f"🔔 Напоминания включены на <b>{cur_h:02d}:{cur_m:02d}</b>.\n"
            f"Изменить время можно повторно через «{REMIND_BTN}».",
            parse_mode="HTML",
        )
        await q.answer()
        return

    # на всякий случай
    await q.answer()
