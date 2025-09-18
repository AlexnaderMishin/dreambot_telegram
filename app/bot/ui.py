# app/bot/ui.py
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder, InlineKeyboardButton

# ЕДИНЫЙ текст кнопки "Напоминания"
REMIND_BTN = "🔔 Напоминания"

def main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="✍ Записать сон")
    kb.button(text="📊 Статистика")
    kb.button(text="🔢 Нумерология")
    kb.button(text="📜 Мои сны")
    kb.button(text="🪐 Астрология")   
    kb.button(text=REMIND_BTN)
    # kb.button(text="⭐ Премиум")
    # было: kb.adjust(1, 2, 2)  # 1+2+2=5, 2 кнопки остаются «висящими»
    kb.adjust(2, 2, 2)       # 1+2+2+2=7 — каждая кнопка гарантированно на месте
    return kb.as_markup(resize_keyboard=True)

HELP_TEXT = (
    "Привет! Я — <b>Помощник сновидений</b>.\n\n"
    "Просто пришлите текст вашего сна — я выделю символы и эмоции, "
    "сохраню запись в дневник.\n\n"
    "<b>Команды:</b>\n"
    "• <code>/menu</code> — показать клавиатуру\n"
    "• <code>/help</code> — помощь\n"
)

# Константы для премиума 
BUY_30 = "💳 Премиум — 30 дней"
BUY_90 = "💳 Премиум — 90 дней"

def kb_premium() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BUY_30)
    kb.button(text=BUY_90)
    kb.button(text="⬅️ Назад")
    kb.adjust(1, 1, 1)
    return kb.as_markup(resize_keyboard=True)


# === Инлайн-меню «Напоминания» (сон + астрология) ===

def reminders_menu_kb(*, dream_time: str | None, astro_time: str | None, moon_phase_on: bool):
    """
    Главное меню раздела «Напоминания».
    dream_time  — текущее время напоминания сна (HH:MM) или None
    astro_time  — текущее время ежедневного астропрогноза (HH:MM) или None
    moon_phase_on — включены ли уведомления о смене фазы луны
    """
    b = InlineKeyboardBuilder()

    # сон
    dream_label = f"📝 Запись снов — {dream_time or 'выкл.'}"
    b.button(text=dream_label, callback_data="rem:dream:open")

    # астрология (ежедневный прогноз)
    astro_label = f"🪐 Астропрогноз — {astro_time or 'выкл.'}"
    b.button(text=astro_label, callback_data="rem:astro:open")

    # переключатель «фазы Луны»
    moon_label = "🌙 Фазы Луны — Включено" if moon_phase_on else "🌙 Фазы Луны — Выключено"
    b.button(text=moon_label, callback_data="rem:moon:toggle")

    b.adjust(1)
    return b
