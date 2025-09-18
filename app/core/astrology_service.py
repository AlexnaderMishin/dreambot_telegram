# app/core/astrology_service.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import os
import re

from app.core.astrology_math import sun_sign, moon_phase

# --------------------- HTML sanitize ---------------------

_ALLOWED = {"b", "i"}
_TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)(?:\s[^>]*)?>", re.IGNORECASE)

def _sanitize_html(s: str, allow_tags: set[str] | None = None) -> str:
    """Очищаем HTML, оставляем только <b> и <i> (по умолчанию)."""
    allow = allow_tags or _ALLOWED
    out: list[str] = []
    pos = 0
    for m in _TAG_RE.finditer(s):
        out.append(html.escape(s[pos:m.start()]))
        tag = m.group(1).lower()
        if tag in allow:
            out.append(s[m.start():m.end()])
        pos = m.end()
    out.append(html.escape(s[pos:]))
    return "".join(out)

# ---------------------- LLM call -------------------------

def _call_llm(*, system: str, user: str, model: str, temperature: float = 0.4) -> str:
    from openai import OpenAI
    api_key = os.getenv("LLM_ASTROLOGY_KEYS") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        # мягкий фоллбек только чтобы бот не падал (в проде ключ обязателен)
        return (
            "<b>Астропрогноз на день для Рак (Убывающая Луна 🌖)</b>\n"
            "Астропрогноз для Имя Фамилия на 25-й день Убывающей Луны 🌖\n\n"
            "✨ Фокус 1\n"
            "Демо-режим: нет ключа API. Содержательное наполнение недоступно.\n\n"
            "✨ Фокус 2\n"
            "Демо-режим: нет ключа API.\n\n"
            "✨ Фокус 3\n"
            "Демо-режим: нет ключа API.\n\n"
            "⚠️ Предостережение:\n"
            "Демо-режим: нет ключа API.\n\n"
            "<i>🔭 Основано на солнечном знаке и текущей фазе Луны.</i>"
        )
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=temperature,
    )
    return resp.choices[0].message.content or ""

# ---------------------- Data model -----------------------

@dataclass
class AstroInput:
    full_name: str
    birth_date: datetime
    birth_time: str | None = None
    birthplace: str | None = None

# ---------------------- Facts builder --------------------

def build_facts(ai: AstroInput) -> dict:
    sign = sun_sign(ai.birth_date)

    # Тестовый оверрайд фазы (не ставить в проде):
    # LUNAR_PHASE_FOR_TEST in {"new","wax","full","wan"}
    override = (os.getenv("LUNAR_PHASE_FOR_TEST") or "").lower().strip()
    if override in {"new", "wax", "full", "wan"}:
        mapping = {
            "new": ("Новолуние", "🌑\ufe0f", 0),
            "wax": ("Растущая Луна", "🌔\ufe0f", 5),
            "full": ("Полнолуние", "🌕\ufe0f", 14),
            "wan": ("Убывающая Луна", "🌖\ufe0f", 20),
        }
        phase_label, emoji, day = mapping[override]
    else:
        phase_label, day, emoji = moon_phase(datetime.now(timezone.utc))

    return {"sign": sign, "phase": phase_label, "phase_day": day, "phase_emoji": emoji}

# ---------------------- Output normalize -----------------

_H1_RE = re.compile(r"^\s*<b>Астропрогноз.+?</b>\s*$", re.IGNORECASE)
_SUB_RE = re.compile(r"^\s*Астропрогноз для.+$", re.IGNORECASE)

def _normalize_to_agreed_format(raw: str, *, facts: dict, ai: AstroInput) -> str:
    """
    Приводим ответ к согласованной форме:
    - если GPT уже вывел заголовок/подзаголовок — оставляем (убираем дубли),
      иначе аккуратно добавляем.
    - не меняем смысл блоков, только форматируем абзацы.
    """
    text = raw.replace("\\n", "\n").strip()

    # убираем любые служебные префейсы типа "Вот ваш прогноз:" до первого тега/строки
    text = re.sub(r"^\s*(вот[^:\n]*:|ответ:)\s*\n", "", text, flags=re.IGNORECASE)

    lines = [l.rstrip() for l in text.splitlines() if l.strip() != ""]
    body_lines: list[str] = []

    # ищем, есть ли наши два заголовка
    has_h1 = any(_H1_RE.match(l) for l in lines[:3])
    has_sub = any(_SUB_RE.match(l) for l in lines[:5])

    # выбрасываем дубли заголовков, если GPT их повторил
    filtered = []
    seen_h1 = False
    seen_sub = False
    for l in lines:
        if _H1_RE.match(l):
            if not seen_h1:
                filtered.append(l)
                seen_h1 = True
            continue
        if _SUB_RE.match(l):
            if not seen_sub:
                filtered.append(l)
                seen_sub = True
            continue
        filtered.append(l)

    lines = filtered

    # если заголовков не было — сформируем их сами
    header_needed = not has_h1
    sub_needed = not has_sub

    if header_needed:
        h1 = f"<b>Астропрогноз на день для {facts['sign']} ({facts['phase']} {facts['phase_emoji']})</b>"
        body_lines.append(h1)
    else:
        # оставляем только первое вхождение исходного заголовка
        # (оно уже в lines[0..])
        pass

    if sub_needed:
        sub = f"Астропрогноз для {ai.full_name} на {facts['phase_day']}-й день {facts['phase']} {facts['phase_emoji']}"
        body_lines.append(sub)

    # добавляем остальное «как есть»
    body_lines.extend(lines if (has_h1 or has_sub) else lines)

    # финальная сборка и лёгкая чистка
    body = "\n\n".join(body_lines)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    return body

# ---------------------- Public API -----------------------

def render_llm(facts: dict, ai: AstroInput) -> str:
    """
    GPT сам создаёт прогноз строго в согласованном формате.
    Мы только санитизируем HTML и подправляем шапки, если GPT их пропустил.
    """
    model = os.getenv("LLM_ASTROLOGY_MODEL", os.getenv("GPT_MODEL", "gpt-4o-mini"))

    system = (
        "Ты выступаешь в роли астролога и создаёшь ежедневный астрологический прогноз.\n\n"
        "Дано: солнечный знак, текущая фаза Луны (с номером дня цикла), а также имя и дата рождения человека. "
        "Опирайся ТОЛЬКО на эти данные.\n\n"
        "Формат ответа строго фиксированный (Telegram HTML):\n"
        '1. Заголовок: "<b>Астропрогноз на день для {Знак} ({Фаза} {Эмодзи})</b>"\n'
        '2. Подзаголовок: "Астропрогноз для {Имя Фамилия} на {День цикла}-й день {Фазы} {Эмодзи}"\n'
        '3. Три блока "✨ Фокус 1", "✨ Фокус 2", "✨ Фокус 3".\n'
        '   - Каждый блок начинается с "✨ Фокус N" (без двоеточия).\n'
        "   - Под каждым фокусом напиши 2–3 предложения живого описания, основанных на знаке и фазе Луны. "
        "Избегай шаблонных клише — добавляй конкретику и астрологическую логику.\n"
        '4. Один блок "⚠️ Предостережение:" — 1–2 предложения о рисках или том, чего сегодня стоит избегать.\n'
        '5. В конце сноска: "<i>🔭 Основано на солнечном знаке и текущей фазе Луны.</i>"\n\n'
        'Дополнительные правила:\n'
        '— Пиши только текст прогноза, без пояснений и без повторного слова "Астропрогноз" в других местах.\n'
        "— Используй только разрешённые теги <b> и <i>.\n"
        "— Не используй списки и нумерацию.\n"
        "— Всегда выдай три фокуса и одно предостережение."
    )

    user = (
        f"Имя: {ai.full_name}\n"
        f"Дата рождения: {ai.birth_date.strftime('%d.%m.%Y')}\n"
        f"Солнечный знак: {facts['sign']}\n"
        f"Фаза Луны: {facts['phase']} {facts['phase_emoji']}\n"
        f"Номер дня лунного цикла: {facts['phase_day']}\n"
    )

    raw = _call_llm(system=system, user=user, model=model, temperature=0.4)
    formatted = _normalize_to_agreed_format(raw, facts=facts, ai=ai)
    sanitized = _sanitize_html(formatted, allow_tags={"b", "i"})

    # гарантируем сноску, если GPT вдруг забыл
    if "Основано на солнечном знаке" not in sanitized:
        sanitized += "\n\n<i>🔭 Основано на солнечном знаке и текущей фазе Луны.</i>"

    return sanitized
