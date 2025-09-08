# app/core/premium.py
from __future__ import annotations

import os
from typing import List, Optional
from textwrap import dedent
from loguru import logger

try:
    # openai v1
    from openai import OpenAI
except Exception:
    OpenAI = None  # чтобы импорт не валился, если зависимость ещё не поставлена


def _demo_template(dream_text: str, warn: Optional[str] = None) -> str:
    bullets: List[str] = []
    if dream_text.strip():
        bullets.append("📖 <b>Краткий пересказ</b>\n• " + dream_text.strip())

    bullets.append(
        "🔑 <b>Символы и мотивы</b>\n"
        "• Выделим ключевые образы по контексту сна (в полной версии — гибкий NLP-анализ)."
    )
    bullets.append(
        "🎭 <b>Эмоциональный фон</b>\n"
        "• Определим ведущие эмоции и возможные триггеры."
    )
    bullets.append(
        "🧠 <b>Возможный смысл</b>\n"
        "• Гипотеза о теме сна с опорой на архетипы и текущий контекст."
    )
    bullets.append(
        "✅ <b>Шаги поддержки</b>\n"
        "• 1–3 конкретных шага, подобранных под сюжет сна."
    )

    footer = "\n<i>(Демо премиум-анализа. После подключения ChatGPT API здесь будет развёрнутый разбор.)</i>"
    if warn:
        footer = f"\n<i>{warn}</i>" + footer

    return "<b>Премиум-разбор сна</b>\n\n" + "\n\n".join(bullets) + footer


def premium_analysis(dream_text: str) -> str:
    mode = os.getenv("PREMIUM_MODE", "stub").lower()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    timeout = int(os.getenv("OPENAI_TIMEOUT", "20"))

    logger.debug(f"[premium] mode={mode} key_set={bool(api_key)} model={model}")

    if mode != "api":
        return _demo_template(dream_text)
    if not api_key:
        return _demo_template(dream_text, warn="(OPENAI_API_KEY не задан — работаем в демо-режиме.)")
    if OpenAI is None:
        return _demo_template(dream_text, warn="(Библиотека openai не установлена — демо-режим.)")

    try:
        client = OpenAI(api_key=api_key, timeout=timeout)

        system = dedent("""
        Ты — психологический ассистент по сновидениям. Кратко и структурно анализируй сон.
        Выводи ГОТОВЫЙ HTML для Telegram: разделы с эмодзи, короткие пункты.
        Структура:
        1) <b>Премиум-разбор сна</b> (заголовок не выводи, он будет в сообщении выше)
        2) 📖 <b>Краткий пересказ</b> — 1–2 предложения.
        3) 🔑 <b>Символы и мотивы</b> — 2–5 пунктов.
        4) 🎭 <b>Эмоциональный фон</b> — 1–3 пункта.
        5) 🧠 <b>Возможный смысл</b> — 1 абзац.
        6) ✅ <b>Шаги поддержки</b> — 3–5 конкретных пунктов.
        Никаких дисклеймеров в конце (их добавит бот). Никаких просьб о медпомощи.
        Язык — русский.
        """)

        user = dream_text.strip() or "Пользователь прислал очень короткий или пустой сон. Дай универсальные мягкие рекомендации."

        # Chat Completions API (совместимо с 4o/4o-mini)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            top_p=0.9,
            max_tokens=900,
        )

        html = resp.choices[0].message.content or ""
        # На всякий случай подрежем опасные теги
        html = html.replace("<script", "&lt;script").replace("</script>", "&lt;/script&gt;")
        return html

    except Exception as e:
        # Любая ошибка API — возвращаем демо, чтобы пользователь всегда что-то получил
        return _demo_template(dream_text, warn=f"(Ошибка OpenAI: {e})")
