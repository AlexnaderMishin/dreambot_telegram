# app/core/astrology_math.py
from __future__ import annotations
from datetime import datetime, timezone

# Опорная дата Новолуния (NASA JPL близко к 2000-01-06 18:14 UTC)
_BASE_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
_SYNODIC = 29.530588  # длина лунного цикла в днях

def _e(symbol: str) -> str:
    """Добавляем variation selector (U+FE0F), чтобы эмодзи всегда были цветными."""
    return symbol + "\ufe0f"

_EMOJI = {
    "new": _e("🌑"),
    "wax_cres": _e("🌒"),
    "first_q": _e("🌓"),
    "wax_gibb": _e("🌔"),
    "full": _e("🌕"),
    "wan_gibb": _e("🌖"),
    "last_q": _e("🌗"),
    "wan_cres": _e("🌘"),
}

def sun_sign(d: datetime) -> str:
    """Определяем солнечный знак по дате рождения (тропический зодиак)."""
    m, day = d.month, d.day
    ranges = [
        ("Овен", (3, 21), (4, 19)),
        ("Телец", (4, 20), (5, 20)),
        ("Близнецы", (5, 21), (6, 20)),
        ("Рак", (6, 21), (7, 22)),
        ("Лев", (7, 23), (8, 22)),
        ("Дева", (8, 23), (9, 22)),
        ("Весы", (9, 23), (10, 22)),
        ("Скорпион", (10, 23), (11, 21)),
        ("Стрелец", (11, 22), (12, 21)),
        ("Козерог", (12, 22), (1, 19)),
        ("Водолей", (1, 20), (2, 18)),
        ("Рыбы", (2, 19), (3, 20)),
    ]
    for name, (m1, d1), (m2, d2) in ranges:
        if (m1 == m and day >= d1) or (m2 == m and day <= d2) \
           or (m1 < m < m2) or (m1 > m2 and (m >= m1 or m <= m2)):
            return name
    return "Неопределён"

def moon_phase(now_utc: datetime) -> tuple[str, int, str]:
    """
    Возвращает (название фазы, день цикла [0..29], эмодзи).
    """
    days = (now_utc - _BASE_NEW_MOON).total_seconds() / 86400.0
    day = int(days % _SYNODIC)

    if day == 0:
        return "Новолуние", day, _EMOJI["new"]
    elif 1 <= day <= 6:
        return "Растущая Луна", day, _EMOJI["wax_cres"]
    elif 7 <= day <= 8:
        return "Первая четверть", day, _EMOJI["first_q"]
    elif 9 <= day <= 13:
        return "Растущая Луна", day, _EMOJI["wax_gibb"]
    elif day == 14:
        return "Полнолуние", day, _EMOJI["full"]
    elif 15 <= day <= 20:
        return "Убывающая Луна", day, _EMOJI["wan_gibb"]
    elif 21 <= day <= 22:
        return "Последняя четверть", day, _EMOJI["last_q"]
    else:  # 23..29
        return "Убывающая Луна", day, _EMOJI["wan_cres"]
