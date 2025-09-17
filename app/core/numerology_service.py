# app/core/numerology_service.py
from __future__ import annotations

from datetime import datetime
from textwrap import dedent
from typing import Optional

from loguru import logger

from app.core.llm_client import chat
from app.core.llm_router import Feature
from app.core.numerology_math import calc_all

# Системные правила для модели
SYSTEM = """
Ты профессиональный нумеролог. Пиши по-русски, кратко и доброжелательно.
Формат ответа — Telegram HTML. Разрешены только теги: <b>, <i>.
Запрещены: <br>, <ul>, <ol>, <li>, <p>, <div>, таблицы, заголовочные теги.
Переносы строки делай обычными переводами строки \\n; между блоками — одна пустая строка.
Не показывай формулы, извинения, дисклеймеры и приветствия.
Числа уже посчитаны на бэкенде — ИСПОЛЬЗУЙ ИХ КАК ЕСТЬ и НЕ пересчитывай.
""".strip()

FOOTNOTE = (
    "\n\n<i>В расчётах используется пифагорейская система в адаптации для кириллицы "
    "(вариант с отдельной буквой Ё, Й=2, Ь/Ъ игнорируются).</i>"
)

def _user_prompt(full_name: str, birth_date: str, nums: dict, gender: Optional[str]) -> str:
    y = nums["year"]
    return dedent(f"""
    Входные данные для интерпретации (НЕ пересчитывай):
    • ФИО: {full_name}
    • Дата рождения: {birth_date}
    • Пол (если указан): {gender or "-"}
    • Число судьбы: {nums["destiny_number"]}
    • День рождения: {nums["birth_day_number"]}
    • Число души: {nums["soul_number"]}
    • Число личности: {nums["personality_number"]}
    • Число имени: {nums["name_number"]}
    • Личный год ({y}): {nums["personal_year"]}

    Сформируй ответ РОВНО по шаблону (используй только <b> и <i>):

    <b>Нумерологический профиль</b>
    {full_name} • {birth_date}

    🔢 Число судьбы: {nums["destiny_number"]}
    1–2 короткие фразы (характер, задачи, типичные вызовы).

    🏛 День рождения: {nums["birth_day_number"]}{' (мастер-число)' if nums['birth_day_number'] in (11,22,33) else ''}
    1–2 фразы интерпретации дня.

    💜 Число души: {nums["soul_number"]}
    1–2 фразы о внутренних ценностях/мотивации.

    🪞 Число личности: {nums["personality_number"]}
    1–2 фразы о том, как человека видят окружающие.

    🧭 Число имени: {nums["name_number"]}
    1–2 фразы об общем векторе реализации.

    📆 Личный год ({y}): {nums["personal_year"]}
    1–2 фразы про тему года.

    🎯 Фокус на месяц
    1. короткое конкретное действие;
    2. короткое конкретное действие;
    3. короткое конкретное действие.

    Итог: одно короткое предложение-вывод про сочетание ключевых чисел.
    """).strip()

def analyze_numerology(full_name: str, birth_date: str, gender: Optional[str] = None) -> str:
    nums = calc_all(full_name, birth_date)
    logger.info("[numerology] start name='{}' birth='{}' -> nums={}", full_name, birth_date, nums)

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": _user_prompt(full_name, birth_date, nums, gender)},
    ]
    text = chat(Feature.NUMEROLOGY, messages, temperature=0.2)
    return text.rstrip() + FOOTNOTE