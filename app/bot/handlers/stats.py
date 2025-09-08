from aiogram import Router, types
from aiogram.filters import Command
from sqlalchemy import text
from app.db.base import SessionLocal
from app.db.models import User

router = Router()

def _fetchone_scalar(session, sql, **params):
    return session.execute(text(sql), params).scalar() or 0

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    tg_id = message.from_user.id

    with SessionLocal() as s:
        user = s.query(User).filter(User.tg_id == tg_id).first()
        if not user:
            await message.answer("Сначала отправьте /start.")
            return

        # Кол-во снов
        last_7 = _fetchone_scalar(s, """
            SELECT COUNT(*) FROM dreams
            WHERE user_id = :uid AND created_at >= NOW() - INTERVAL '7 days'
        """, uid=user.id)

        last_30 = _fetchone_scalar(s, """
            SELECT COUNT(*) FROM dreams
            WHERE user_id = :uid AND created_at >= NOW() - INTERVAL '30 days'
        """, uid=user.id)

        # Топ символов за 30 дней
        top_symbols = s.execute(text("""
            SELECT s->>'key' AS key, COUNT(*) AS cnt
            FROM dreams d
            CROSS JOIN LATERAL jsonb_array_elements(d.symbols) s
            WHERE d.user_id = :uid AND d.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY key
            ORDER BY cnt DESC
            LIMIT 5
        """), {"uid": user.id}).fetchall()

        # Топ эмоций за 30 дней (если заполняются)
        top_emotions = s.execute(text("""
            SELECT emo, COUNT(*) AS cnt FROM (
              SELECT jsonb_array_elements_text(d.emotions) AS emo
              FROM dreams d
              WHERE d.user_id = :uid AND d.created_at >= NOW() - INTERVAL '30 days'
            ) t
            GROUP BY emo ORDER BY cnt DESC LIMIT 5
        """), {"uid": user.id}).fetchall()

    lines = [
        "*Статистика*",
        f"За 7 дней: **{last_7}**",
        f"За 30 дней: **{last_30}**",
        "",
        "Топ символов (30д):" if top_symbols else "Топ символов (30д): —"
    ]
    if top_symbols:
        lines += [f"• {row.key} — {row.cnt}" for row in top_symbols]

    lines.append("")
    lines.append("Топ эмоций (30д):" if top_emotions else "Топ эмоций (30д): —")
    if top_emotions:
        lines += [f"• {row.emo} — {row.cnt}" for row in top_emotions]

    await message.answer("\n".join(lines))
