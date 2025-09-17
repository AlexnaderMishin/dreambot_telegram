# app/core/numerology_math.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict

# Кириллица -> цифры (вариант пифагорейской раскладки; Ь/Ъ игнорируем)
_MAP = {
    "А": 1, "И": 1, "С": 1,
    "Б": 2, "Й": 2, "Т": 2, "Ы": 2,
    "В": 3, "К": 3, "У": 3, "Э": 3,
    "Г": 4, "Л": 4, "Ф": 4, "Ю": 4,
    "Д": 5, "М": 5, "Х": 5, "Я": 5,
    "Е": 6, "Н": 6, "Ц": 6,
    "Ё": 7, "О": 7, "Ч": 7,
    "Ж": 8, "П": 8, "Ш": 8,
    "З": 9, "Р": 9, "Щ": 9,
}
_VOWELS = set("АЕЁИОУЫЭЮЯ")

def _digits_reduce(n: int) -> int:
    """Редуцируем до 1..9, мастер 11/22/33 не трогаем."""
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n

def _letters(name: str) -> list[str]:
    return [ch for ch in re.sub(r"[^А-ЯЁ]", "", name.upper())]

def _sum_by(letters: list[str]) -> int:
    return sum(_MAP.get(ch, 0) for ch in letters)

def calc_from_name(full_name: str) -> Dict[str, int]:
    letters = _letters(full_name)
    all_sum = _sum_by(letters)
    soul_sum = _sum_by([ch for ch in letters if ch in _VOWELS])  # гласные
    pers_sum = _sum_by([ch for ch in letters if ch not in _VOWELS and ch not in {"Ь", "Ъ"}])  # согласные

    return {
        "name_number": _digits_reduce(all_sum),
        "soul_number": _digits_reduce(soul_sum),
        "personality_number": _digits_reduce(pers_sum),
    }

def calc_from_birth(birth_date: str) -> Dict[str, int]:
    # birth_date ожидаем в формате ДД.ММ.ГГГГ
    dd, mm, yyyy = birth_date.split(".")
    digits = [int(c) for c in dd+mm+yyyy]
    destiny_raw = sum(digits)
    destiny = _digits_reduce(destiny_raw)

    day = int(dd)
    day_number = day if day in (11, 22, 33) else _digits_reduce(day)

    # личный год: текущий год + (день+месяц)
    year = datetime.now().year
    py_raw = sum(int(d) for d in f"{year}{dd}{mm}")
    personal_year = _digits_reduce(py_raw)

    return {
        "destiny_number": destiny,         # число судьбы
        "birth_day_number": day_number,    # день рождения
        "personal_year": personal_year,    # личный год
        "year": year,
    }

def calc_all(full_name: str, birth_date: str) -> Dict[str, int]:
    data = {}
    data.update(calc_from_name(full_name))
    data.update(calc_from_birth(birth_date))
    return data
