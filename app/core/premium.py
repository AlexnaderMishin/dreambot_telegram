# app/core/premium.py
from __future__ import annotations

import os
from typing import List, Optional
from textwrap import dedent
from loguru import logger

from app.core.llm_client import chat
from app.core.llm_router import Feature
from app.core.telegram_html import sanitize_tg_html

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
    """
    Премиум-анализ сна через наш LLM-роутер.
    Управляется флагом PREMIUM_MODE=api|stub (stub — демо-ответ без LLM).
    """
    mode = os.getenv("PREMIUM_MODE", "api").lower()
    logger.debug(f"[premium] mode={mode}")

    if mode != "api":
        return _demo_template(dream_text)

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
    """).strip()

    user = (dream_text or "").strip() or \
        "Пользователь прислал очень короткий или пустой сон. Дай универсальные мягкие рекомендации."

    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]

    try:
        # ВАЖНО: используем наш роутер ключей и единый клиент
        html = chat(Feature.DREAM, messages, temperature=0.7)
        html = sanitize_tg_html(html) 
        # На всякий случай подрежем опасные теги
        html = html.replace("<script", "&lt;script").replace("</script>", "&lt;/script&gt;")
        return html
    except Exception as e:
        logger.exception("premium_analysis failed")
        return _demo_template(dream_text, warn=f"(Ошибка LLM: {e})")
