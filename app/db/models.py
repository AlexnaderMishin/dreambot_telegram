from __future__ import annotations
from datetime import datetime
from typing import Optional, List

import sqlalchemy as sa 
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from .base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(sa.String(64))
    tz: Mapped[str] = mapped_column(sa.String(64), default="Europe/Moscow", nullable=False)

    is_premium: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False, server_default=sa.false())
    remind_enabled: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False, server_default=sa.false())

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    dreams: Mapped[List["Dream"]] = relationship(back_populates="user")

class Dream(Base):
    __tablename__ = "dreams"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    symbols: Mapped[dict] = mapped_column(JSONB, default=dict)
    emotions: Mapped[list] = mapped_column(JSONB, default=list)
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="dreams")

class Symbol(Base):
    __tablename__ = "symbols"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    synonyms: Mapped[list] = mapped_column(JSONB, default=list)
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

class CrisisKeyword(Base):
    __tablename__ = "crisis_keywords"
    id: Mapped[int] = mapped_column(primary_key=True)
    phrase: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    severity: Mapped[int] = mapped_column()  # 1..3
    help_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
