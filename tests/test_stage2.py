# tests/test_stage2.py
import re
import datetime as dt
import pytest

from sqlalchemy import select

from app.bot.main import start_cmd, help_cmd, on_dream
from app.bot.handlers.symbol import cmd_symbol
from app.bot.handlers.note import cmd_note
from app.bot.handlers.stats import cmd_stats
from app.bot.handlers.remind import cmd_remind
from app.bot.reminders import bootstrap_existing, scheduler

from app.db.models import User, Dream
from tests.conftest import StubMessage


@pytest.mark.asyncio
async def test_start_creates_user_and_replies(db):
    m = StubMessage("/start")
    await start_cmd(m)
    # пользователь создан
    user = db.execute(select(User).where(User.tg_id == m.from_user.id)).scalar_one_or_none()
    assert user is not None
    # ответ содержит приветствие
    assert "Помощник сновидений" in (m.last or "")


@pytest.mark.asyncio
async def test_help_lists_commands():
    m = StubMessage("/help")
    await help_cmd(m)
    body = m.last or ""
    assert "/start" in body and "/help" in body and "/symbol" in body and "/stats" in body and "/remind" in body and "/note" in body


@pytest.mark.asyncio
async def test_dream_is_saved_and_contains_symbol(db):
    # подготовка пользователя
    u = User(tg_id=999, username="tester")
    db.add(u)
    db.commit()

    # отправляем текст сна
    m = StubMessage("сегодня мне приснилось что у меня выпал зуб")
    await on_dream(m)

    # в ответе — символ про зубы
    body = m.last or ""
    assert "Символы" in body
    assert "зуб" in body.lower()

    # запись в БД создана и связана с пользователем
    dream = db.execute(select(Dream).where(Dream.user_id == u.id)).scalar_one_or_none()
    assert dream is not None
    assert dream.text.startswith("сегодня мне приснилось")
    assert isinstance(dream.symbols, list)


@pytest.mark.asyncio
async def test_symbol_command_returns_meaning():
    m = StubMessage("/symbol змея")
    await cmd_symbol(m)
    body = m.last or ""
    # должен быть какой-то текст с описанием, не «не найдено»
    assert "зме" in body.lower()  # змея / змеи / змею т.д.
    assert "не найдено" not in body.lower()


@pytest.mark.asyncio
async def test_note_updates_last_dream(db):
    # создаём пользователя и два сна
    u = User(tg_id=999, username="tester")
    db.add(u); db.flush()
    d1 = Dream(user_id=u.id, text="сон 1", symbols=[], emotions=[], actions=[])
    d2 = Dream(user_id=u.id, text="сон 2", symbols=[], emotions=[], actions=[])
    db.add_all([d1, d2]); db.commit()

    m = StubMessage("/note важная заметка")
    await cmd_note(m)

    # последняя запись обновилась
    last = db.execute(select(Dream).where(Dream.user_id == u.id).order_by(Dream.id.desc())).scalar_one()
    assert last.note and "важная заметка" in last.note


@pytest.mark.asyncio
async def test_stats_counts_7_and_30_days(db):
    u = User(tg_id=999, username="tester")
    db.add(u); db.flush()

    now = dt.datetime.now(dt.timezone.utc)
    # 2 сна в последние 7 дней
    db.add_all([
        Dream(user_id=u.id, text="d7-1", created_at=now - dt.timedelta(days=1), symbols=[], emotions=[], actions=[]),
        Dream(user_id=u.id, text="d7-2", created_at=now - dt.timedelta(days=6, hours=1), symbols=[], emotions=[], actions=[]),
    ])
    # 1 сон в последние 30 (но старше 7)
    db.add(Dream(user_id=u.id, text="d30-1", created_at=now - dt.timedelta(days=14), symbols=[], emotions=[], actions=[]))
    db.commit()

    m = StubMessage("/stats")
    await cmd_stats(m)
    body = m.last or ""
    # ожидаем подсчёт «за 7 дней» и «за 30 дней»
    assert re.search(r"7.*\b2\b", body)  # где-то есть «7 … 2»
    assert re.search(r"30.*\b3\b", body)  # где-то есть «30 … 3»


@pytest.mark.asyncio
async def test_remind_toggle(db):
    u = User(tg_id=999, username="tester", remind_enabled=False)
    db.add(u); db.commit()

    m_on = StubMessage("/remind on")
    await cmd_remind(m_on)

    db.refresh(u)
    assert u.remind_enabled is True
    assert "включены" in (m_on.last or "").lower()

    m_off = StubMessage("/remind off")
    await cmd_remind(m_off)
    db.refresh(u)
    assert u.remind_enabled is False
    assert "выключены" in (m_off.last or "").lower()


@pytest.mark.asyncio
async def test_scheduler_bootstrap_adds_jobs(db, monkeypatch):
    """Пользователи с remind_enabled=True получают job в планировщике."""
    u1 = User(tg_id=999, username="tester", remind_enabled=True, tz="Europe/Moscow")
    u2 = User(tg_id=1000, username="nope", remind_enabled=False, tz="Europe/Moscow")
    db.add_all([u1, u2]); db.commit()

    added = []

    def fake_add_job(func, trigger, **kw):
        # фиксируем параметры вызова
        added.append((func.__name__, trigger, kw))
        class _Job:
            id = "test-job-id"
        return _Job()

    monkeypatch.setattr(scheduler, "add_job", fake_add_job)

    class DummyBot:
        async def send_message(self, chat_id, text, **kw):
            pass

    await bootstrap_existing(DummyBot())

    # Должна появиться хотя бы одна запись для u1
    assert added, "ожидали, что будет добавлен хотя бы один job"
