# app/bot/handlers/stats.py
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Iterable, List, Tuple

import zoneinfo
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import and_

from app.db.base import SessionLocal
from app.db.models import User, Dream
from app.core.premium import premium_analysis  # твоя обёртка (api/stub режимы)

router = Router(name="stats")

# Эмоции: что считаем «плюсом/минусом»
POSITIVE = {"радость", "любовь", "интерес", "спокойствие", "умиротворение", "вдохновение", "надежда"}
NEGATIVE = {"страх", "тревога", "грусть", "злость", "стыд", "вина", "раздражение", "тоска"}

# ──────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНОЕ

def _user_tz_or_utc(tz_name: str | None) -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(tz_name or "UTC")
    except Exception:
        return zoneinfo.ZoneInfo("UTC")

def _period_bounds(now_local: datetime, days: int) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Возвращает:
      - start, end: текущий период (end НЕ включительно)
      - prev_start, prev_end: предыдущий период той же длины
    """
    end = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    start = end - timedelta(days=days)
    prev_end = start
    prev_start = start - timedelta(days=days)
    return start, end, prev_start, prev_end

def _count_emotions(dreams: Iterable[Dream]) -> Tuple[int, int]:
    pos = neg = 0
    for d in dreams:
        if not d.emotions:
            continue
        for emo in d.emotions:
            e = str(emo).strip().lower()
            if e in POSITIVE:
                pos += 1
            elif e in NEGATIVE:
                neg += 1
    return pos, neg

def _top_symbols(dreams: Iterable[Dream], n: int = 3) -> List[Tuple[str, int]]:
    cnt = Counter()
    for d in dreams:
        if not d.symbols:
            continue
        for item in d.symbols:
            key = (item.get("key") if isinstance(item, dict) else item) or ""
            key = str(key).strip().lower()
            if key:
                cnt[key] += 1
    return cnt.most_common(n)

def _bar10(cur: int, prev: int) -> str:
    """Небольшая полоска динамики (10 ячеек)."""
    if prev < 0: prev = 0
    if cur < 0: cur = 0
    if prev == 0 and cur == 0:
        fill = 0
    elif prev == 0:
        fill = 10
    else:
        ratio = cur / prev
        # ограничим разумно
        ratio = 0 if ratio < 0 else (2.0 if ratio > 2.0 else ratio)
        fill = round(min(10, max(0, ratio * 5)))  # ~ 1x = 5 ячеек
    return "▁" * (10 - fill) + "▇" * fill

def _trend_arrow(cur: int, prev: int) -> str:
    if prev == 0 and cur > 0:
        return "↗️"
    if cur > prev:
        return "⬆️"
    if cur < prev:
        return "⬇️"
    return "➡️"

def _human_emo_balance(pos: int, neg: int) -> str:
    total = pos + neg
    if total == 0:
        return "нет данных"
    return f"🙂 {pos} · 😔 {neg} (всего {total})"

def _ai_blocks_or_stub(
    *,
    user_is_premium: bool,
    period_days: int,
    pos: int,
    neg: int,
    top_symbol: str | None,
) -> Tuple[str, str]:
    """
    Возвращает (рекомендации, общий_вывод).
    Если премиум и PREMIUM_MODE позволяет — спрашиваем модель через premium_analysis.
    Иначе — отдаём аккуратные заглушки.
    """
    # Формируем контекст для модели
    ctx_lines = [
        f"Период: {period_days} дней.",
        f"Баланс эмоций: позитивных={pos}, негативных={neg}.",
        f"Повторяющийся символ (топ-1): {top_symbol or 'нет'}."
    ]
    ctx = "\n".join(ctx_lines)

    premium_mode = (os.getenv("PREMIUM_MODE") or "stub").lower()

    if user_is_premium and premium_mode in {"api", "stub"}:
        # Просим модель ответить ЧЕТКО в двух блоках, по 2–4 строки каждый.
        prompt = (
            "Ты — психолог-сновидец. На основе сводной статистики дай краткие рекомендации "
            "и общий смысловой вывод. Верни ответ строго в двух абзацах:\n\n"
            "1) Рекомендации — 2–4 строки, короткие и конкретные (что делать/на что обратить внимание).\n"
            "2) Общий вывод — 2–4 строки, спокойный смысловой итог без клише.\n\n"
            f"Сводка:\n{ctx}"
        )
        try:
            html = premium_analysis(prompt)  # вернет HTML/текст
            # Пытаемся разрезать по абзацам — если не получится, положим целиком во «Вывод»
            parts = [p.strip() for p in html.split("\n") if p.strip()]
            if len(parts) >= 2:
                rec = parts[0]
                summ = " ".join(parts[1:])
            else:
                rec = "• Сохраните регулярный ритм сна и мягкую вечернюю руутину."
                summ = html
            return rec, summ
        except Exception:
            pass  # упадём в заглушку

    # Заглушки (когда не премиум или нет API)
    rec_stub = (
        "• Поддерживайте стабильный режим сна и короткие дневные заметки о чувствах.\n"
        "• Обратите внимание на повторяющиеся образы — запишите, что они для вас значат.\n"
        "• Выберите 1 спокойную практику перед сном (дыхание, тёплый душ, чтение)."
    )
    summ_stub = (
        "Период показывает ваши актуальные темы и переживания. "
        "Если повторяется один образ, он указывает на важную внутреннюю задачу. "
        "Сбалансируйте активность и отдых, фиксируйте короткие заметки — так яснее проявится динамика."
    )
    return rec_stub, summ_stub


# ──────────────────────────────────────────────────────────────────────────────
# UI: выбор периода

def _kb_period() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="7 дней", callback_data="stats:7"),
             InlineKeyboardButton(text="30 дней", callback_data="stats:30")]
        ]
    )

@router.message(Command("stats"))
@router.message(F.text.lower() == "📊 статистика".lower())
async def ask_period(m: types.Message) -> None:
    await m.answer("📊 Выберите период:", reply_markup=_kb_period())


# ──────────────────────────────────────────────────────────────────────────────
# Подсчёт и вывод

import os

@router.callback_query(F.data.startswith("stats:"))
async def show_stats(cb: types.CallbackQuery) -> None:
    await cb.answer()
    _, days_str = cb.data.split(":")
    days = 7 if days_str == "7" else 30

    with SessionLocal() as s:
        user = s.query(User).filter_by(tg_id=cb.from_user.id).one_or_none()
        if not user:
            await cb.message.answer("Не нашёл профиль. Напишите /start, чтобы зарегистрироваться.")
            return

        tz = _user_tz_or_utc(user.tz)
        now_local = datetime.now(tz)
        start, end, prev_start, prev_end = _period_bounds(now_local, days)

        # Берём «сырые» записи
        cur_q = (
            s.query(Dream)
            .filter(
                and_(
                    Dream.user_id == user.id,
                    Dream.created_at >= start,
                    Dream.created_at < end,
                )
            )
            .order_by(Dream.created_at.asc())
        )
        cur = cur_q.all()

        prev_count = (
            s.query(Dream)
            .filter(
                and_(
                    Dream.user_id == user.id,
                    Dream.created_at >= prev_start,
                    Dream.created_at < prev_end,
                )
            )
            .count()
        )

    cur_count = len(cur)
    arrow = _trend_arrow(cur_count, prev_count)
    bar = _bar10(cur_count, prev_count)

    # Эмоции
    pos, neg = _count_emotions(cur)
    if pos + neg == 0:
        emo_line = "нейтральный период (чувства не отмечались)"
        emotions_missing = True
    else:
        emo_line = f"🙂 {pos} · 😔 {neg} (всего {pos+neg})"
        emotions_missing = False

    # Символы
    top_list = _top_symbols(cur, n=3)
    if top_list:
        top_str = ", ".join(f"{k} — {c}" for k, c in top_list)
        top1 = top_list[0][0]
    else:
        top_str = "нет данных"
        top1 = None

    # Блоки с ИИ (или заглушка)
    rec_block, summ_block = _ai_blocks_or_stub(
        user_is_premium=bool(user.is_premium),
        period_days=days,
        pos=pos,
        neg=neg,
        top_symbol=top1,
    )

    # Если эмоций нет — добавим мягкую подсказку в рекомендации
    if emotions_missing:
        extra_tip = (
            "\n• Чтобы отчёты были точнее, отмечайте 1–2 чувства в описании сна "
            "(например: радость/спокойствие/тревога)."
        )
        rec_block = rec_block + extra_tip

    # Итоговый текст
    period_caption = f"Статистика за {days} дней"
    period_dates = f"({start.date().strftime('%d.%m.%Y')} — {(end - timedelta(days=1)).date().strftime('%d.%m.%Y')})"

    lines: List[str] = []
    lines.append(f"📊 <b>{period_caption}</b> {period_dates}")
    lines.append("")
    lines.append("🧾 <b>Цифры и факты</b>")
    lines.append(f"• Кол-во снов: <b>{cur_count}</b> {arrow}  {bar}  (прошлый период: {prev_count})")
    lines.append(f"• Баланс эмоций: <i>{emo_line}</i>")
    lines.append(f"• Топ символов: {top_str}")
    lines.append("")
    lines.append("✨ <b>Рекомендации</b>")
    lines.append(rec_block)
    lines.append("")
    lines.append("🧭 <b>Общий вывод</b>")
    lines.append(summ_block)

    await cb.message.edit_text("\n".join(lines), parse_mode="HTML")
