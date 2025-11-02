from __future__ import annotations
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    select,
)
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class EventStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"


class Outcome(enum.Enum):
    NONE = "NONE"
    RED = "RED"
    BLACK = "BLACK"
    MINUS = "MINUS"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bets: Mapped[list[Bet]] = relationship(
        "Bet", back_populates="user", cascade="all, delete-orphan"
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_title: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus), default=EventStatus.OPEN, index=True
    )
    outcome: Mapped[Outcome] = mapped_column(Enum(Outcome), default=Outcome.NONE)
    red_odds: Mapped[float] = mapped_column(Float, default=1.0)
    black_odds: Mapped[float] = mapped_column(Float, default=1.0)
    betting_starts_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # Время начала приема ставок
    betting_ends_at: Mapped[datetime] = mapped_column(DateTime)  # Время окончания приема ставок
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    bets: Mapped[list[Bet]] = relationship(
        "Bet", back_populates="event", cascade="all, delete-orphan"
    )

    def is_betting_active(self) -> bool:
        """Проверка, активен ли прием ставок"""
        now = datetime.utcnow()
        return (
            self.status == EventStatus.OPEN and
            self.betting_starts_at <= now <= self.betting_ends_at
        )

    def get_time_left(self) -> int:
        """Получить оставшееся время в секундах"""
        now = datetime.utcnow()
        if now > self.betting_ends_at:
            return 0
        delta = self.betting_ends_at - now
        return int(delta.total_seconds())


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    choice: Mapped[Outcome] = mapped_column(Enum(Outcome))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    settled: Mapped[bool] = mapped_column(Boolean, default=False)
    win: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    payout: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="bets")
    event: Mapped[Event] = relationship("Event", back_populates="bets")


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0)
    uses_left: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    usages: Mapped[list[PromoUsage]] = relationship(
        "PromoUsage", back_populates="promo", cascade="all, delete-orphan"
    )


class PromoUsage(Base):
    __tablename__ = "promo_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    promo: Mapped[PromoCode] = relationship("PromoCode", back_populates="usages")
    user: Mapped[User] = relationship("User")


engine = None
AsyncSessionLocal: async_sessionmaker | None = None


async def init_engine(database_url: str) -> None:
    global engine, AsyncSessionLocal
    if engine and AsyncSessionLocal:
        return
    engine = create_async_engine(database_url, echo=False, future=True)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db(database_url: str) -> None:
    await init_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(
    tg_id: int, username: Optional[str], init_points: int
) -> User:
    if AsyncSessionLocal is None:
        raise RuntimeError("База данных не инициализирована")
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user:
            return user
        user = User(tg_id=tg_id, username=username, balance=init_points)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def change_balance(user_id: int, delta: int) -> int:
    if AsyncSessionLocal is None:
        raise RuntimeError("База данных не инициализирована")
    async with AsyncSessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        user.balance += delta
        await session.commit()
        return user.balance


async def redeem_promo(user_id: int, code_str: str) -> int:
    if AsyncSessionLocal is None:
        raise RuntimeError("База данных не инициализирована")

    async with AsyncSessionLocal() as session:
        promo = await session.scalar(select(PromoCode).where(PromoCode.code == code_str))
        if not promo:
            raise ValueError("Неверный промокод")
        if promo.uses_left <= 0:
            raise ValueError("Промокод больше не действителен")
        if promo.expires_at and promo.expires_at < datetime.utcnow():
            raise ValueError("Промокод истёк")

        usage_exists = await session.scalar(
            select(PromoUsage).where(
                PromoUsage.promo_id == promo.id,
                PromoUsage.user_id == user_id,
            )
        )
        if usage_exists:
            raise ValueError("Вы уже использовали этот промокод")

        user = await session.get(User, user_id)
        if not user:
            raise ValueError("Пользователь не найден")

        user.balance += promo.amount
        promo.uses_left -= 1
        session.add(PromoUsage(promo_id=promo.id, user_id=user_id))

        await session.commit()
        return promo.amount


def get_session() -> async_sessionmaker:
    if AsyncSessionLocal is None:
        raise RuntimeError("База данных не инициализирована")
    return AsyncSessionLocal
