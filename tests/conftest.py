# tests/conftest.py
import asyncio
import os
import pytest

from app.db.base import SessionLocal, Base
from app.db.models import User, Dream
from sqlalchemy import text


@pytest.fixture(scope="session")
def event_loop():
    """pytest-asyncio: единый event loop на сессию тестов."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _ensure_test_env():
    # При необходимости можно выставить режимы окружения для тестов
    os.environ.setdefault("USE_DB_SYMBOLS", "false")
    yield


@pytest.fixture()
def db():
    """Свежая сессия БД на каждый тест + зачистка данных пользователя 999."""
    s = SessionLocal()
    try:
        # Чистим только нашего «тестового» пользователя и связанные сны
        uid = 999
        s.execute(text("DELETE FROM dreams WHERE user_id IN (SELECT id FROM users WHERE tg_id=:tg)"), {"tg": uid})
        s.execute(text("DELETE FROM users WHERE tg_id=:tg"), {"tg": uid})
        s.commit()
        yield s
    finally:
        s.close()


class StubFromUser:
    def __init__(self, id: int, username: str | None = None):
        self.id = id
        self.username = username


class StubMessage:
    """Минимальный объект, имитирующий aiogram.types.Message"""
    def __init__(self, text: str, user_id: int = 999, username: str = "tester"):
        self.text = text
        self.from_user = StubFromUser(user_id, username)
        self._answers: list[str] = []

    async def answer(self, text: str, **kwargs):
        self._answers.append(text)

    # для удобства проверок
    @property
    def last(self) -> str | None:
        return self._answers[-1] if self._answers else None

    @property
    def answers(self) -> list[str]:
        return self._answers
