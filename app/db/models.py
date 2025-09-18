from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from sqlalchemy.sql import func, text
#испорты reminds
from sqlalchemy import Time
from datetime import time

import sqlalchemy as sa 
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB   # если используешь JSONB в модели
from sqlalchemy.orm import relationship


from .base import Base
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, BigInteger, func
)
from sqlalchemy.orm import declarative_base
Base = declarative_base()
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(64))
    tz = Column(String(64), nullable=False, server_default="Europe/Moscow")
    is_premium = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    remind_enabled = Column(Boolean, nullable=False, server_default="false")
    premium_expires_at = Column(DateTime(timezone=True), nullable=True)
    remind_time = Column(Time, nullable=True, default=time(8, 30))  # локальное время пользователя
    notify_moon_phase = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    notify_daily_time = sa.Column(sa.Text, nullable=True)
    last_moon_phase   = sa.Column(sa.Text, nullable=True)
    last_moon_day     = sa.Column(sa.Integer, nullable=True)

    # >>> ДОБАВЬ ЭТУ СТРОКУ (встречная связь для платежей)
    payments = relationship(
        "Payment",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    numerology_profiles: Mapped[List["NumerologyProfile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    dreams: Mapped[List["Dream"]] = relationship(back_populates="user")

class NumerologyProfile(Base):
    __tablename__ = "numerology_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    birth_date = Column(Date, nullable=False)
    gender = Column(String(20), nullable=True)
    report_html = Column(Text, nullable=False)
    report_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ОСТАВИТЬ только это:
    user = relationship("User", back_populates="numerology_profiles")
   
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



class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=True)
    payload = Column(String(255), nullable=True)
    currency = Column(String(10), nullable=True)
    total_amount = Column(Integer, nullable=True)  # в копейках
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # >>> ВСТРЕЧНАЯ СВЯЗЬ (должна совпадать по названию с тем, что добавили в User)
    user = relationship("User", back_populates="payments")

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

