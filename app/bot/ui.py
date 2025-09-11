# app/bot/ui.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# --- основные кнопки главного меню ---
def main_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="✍ Записать сон")
    kb.button(text="📊 Статистика")
    kb.button(text="📜 Мои сны")
    kb.button(text="🔔 Напоминания")
    kb.button(text="⭐ Премиум")
    kb.adjust(1, 2, 2)
    return kb.as_markup(resize_keyboard=True)

HELP_TEXT = (
    "Привет! Я — <b>Помощник сновидений</b>.\n\n"
    "Просто пришлите текст вашего сна — я выделю символы и эмоции, "
    "сохраню запись в дневник.\n\n"
    "<b>Команды:</b>\n"
    "• <code>/menu</code> — показать клавиатуру\n"
    "• <code>/help</code> — помощь\n"
)

# --- КОНСТАНТЫ ДЛЯ КНОПОК ПРЕМИУМА (чтобы совпадали везде) ---
BUY_30 = "💳 Премиум — 30 дней"
BUY_90 = "💳 Премиум — 90 дней"

def kb_premium() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text=BUY_30)
    kb.button(text=BUY_90)
    kb.button(text="⬅️ Назад")
    kb.adjust(1, 1, 1)
    return kb.as_markup(resize_keyboard=True)
