from __future__ import annotations

import enum
import json
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
	BigInteger,
	Boolean,
	DateTime,
	Enum,
	ForeignKey,
	Integer,
	String,
	Text,
	func,
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

	bets: Mapped[list[Bet]] = relationship("Bet", back_populates="user", cascade="all, delete-orphan")  # type: ignore[name-defined]


class Event(Base):
	__tablename__ = "events"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	name: Mapped[str] = mapped_column(String(255))
	description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
	status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.OPEN, index=True)
	outcome: Mapped[Outcome] = mapped_column(Enum(Outcome), default=Outcome.NONE)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
	closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
	resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

	bets: Mapped[list[Bet]] = relationship("Bet", back_populates="event", cascade="all, delete-orphan")  # type: ignore[name-defined]


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

	user: Mapped[User] = relationship("User", back_populates="bets")  # type: ignore[name-defined]
	event: Mapped[Event] = relationship("Event", back_populates="bets")  # type: ignore[name-defined]


class PromoCode(Base):
	__tablename__ = "promo_codes"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
	amount: Mapped[int] = mapped_column(Integer, default=0)
	uses_left: Mapped[int] = mapped_column(Integer, default=1)
	expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
	__tablename__ = "audit_logs"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
	level: Mapped[str] = mapped_column(String(16), default="INFO")
	message: Mapped[str] = mapped_column(String(255))
	payload_json: Mapped[str] = mapped_column(Text, default="{}")

	@staticmethod
	def payload_to_json(payload: dict | None) -> str:
		return json.dumps(payload or {}, ensure_ascii=False)


# Engine and session maker (initialized in init_engine)
engine = None
AsyncSessionLocal: async_sessionmaker | None = None


async def init_engine(database_url: str) -> None:
	global engine, AsyncSessionLocal
	os.makedirs("data", exist_ok=True)
	engine = create_async_engine(database_url, echo=False, future=True)
	AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db(database_url: str) -> None:
	await init_engine(database_url)
	assert engine is not None
	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)


# Helper queries
async def get_or_create_user(tg_id: int, username: Optional[str], init_points: int) -> User:
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		result = await session.execute(
			User.__table__.select().where(User.tg_id == tg_id)
		)
		row = result.first()
		if row:
			# Re-map to ORM instance
			user = await session.get(User, row[0].id)  # type: ignore[attr-defined]
			return user  # type: ignore[return-value]
		user = User(tg_id=tg_id, username=username, balance=init_points)
		session.add(user)
		await session.commit()
		await session.refresh(user)
		return user


async def change_balance(user_id: int, delta: int) -> int:
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		user = await session.get(User, user_id)
		if not user:
			raise ValueError("User not found")
		user.balance += delta
		await session.commit()
		return user.balance


async def list_open_events() -> list[Event]:
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		result = await session.execute(Event.__table__.select().where(Event.status == EventStatus.OPEN))
		rows = result.fetchall()
		if not rows:
			return []
		ids = [r.id for r in rows]  # type: ignore[attr-defined]
		return [await session.get(Event, _id) for _id in ids]  # type: ignore[list-item]


async def create_event(name: str, description: str | None = None) -> Event:
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		event = Event(name=name, description=description or None, status=EventStatus.OPEN)
		session.add(event)
		await session.commit()
		await session.refresh(event)
		return event


async def place_bet(user_id: int, event_id: int, choice: Outcome, amount: int) -> Bet:
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		user = await session.get(User, user_id)
		event = await session.get(Event, event_id)
		if not user or not event:
			raise ValueError("Invalid user or event")
		if event.status != EventStatus.OPEN:
			raise ValueError("Event is not open")
		if user.balance < amount:
			raise ValueError("Not enough balance")
		user.balance -= amount
		bet = Bet(user_id=user_id, event_id=event_id, choice=choice, amount=amount)
		session.add(bet)
		await session.commit()
		await session.refresh(bet)
		return bet


async def resolve_event(event_id: int, outcome: Outcome) -> tuple[Event, int, int]:
	"""Resolve event and settle bets. Returns (event, winners_count, losers_count). Payout=amount*2 for winners."""
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		event = await session.get(Event, event_id)
		if not event:
			raise ValueError("Event not found")
		if event.status == EventStatus.RESOLVED:
			raise ValueError("Event already resolved")
		event.status = EventStatus.RESOLVED
		event.outcome = outcome
		event.resolved_at = datetime.utcnow()

		result = await session.execute(Bet.__table__.select().where(Bet.event_id == event_id))
		rows = result.fetchall()
		win_count = 0
		lose_count = 0
		for r in rows:
			bet = await session.get(Bet, r.id)  # type: ignore[attr-defined]
			if not bet:
				continue
			if bet.settled:
				continue
			if bet.choice == outcome:
				payout = bet.amount * 2
				bet.win = True
				bet.payout = payout
				bet.settled = True
				user = await session.get(User, bet.user_id)
				if user:
					user.balance += payout
				win_count += 1
			else:
				bet.win = False
				bet.payout = 0
				bet.settled = True
				lose_count += 1

		await session.commit()
		return event, win_count, lose_count


async def close_event(event_id: int) -> Event:
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		event = await session.get(Event, event_id)
		if not event:
			raise ValueError("Event not found")
		event.status = EventStatus.CLOSED
		event.closed_at = datetime.utcnow()
		await session.commit()
		return event


async def redeem_promo(user_id: int, code_str: str) -> int:
	"""Apply promo code to user, returns amount added."""
	assert AsyncSessionLocal is not None
	async with AsyncSessionLocal() as session:
		result = await session.execute(PromoCode.__table__.select().where(PromoCode.code == code_str))
		row = result.first()
		if not row:
			raise ValueError("Invalid promo code")
		promo = await session.get(PromoCode, row.id)  # type: ignore[attr-defined]
		if not promo:
			raise ValueError("Invalid promo code")
		if promo.uses_left <= 0:
			raise ValueError("Promo code has no uses left")
		if promo.expires_at and promo.expires_at < datetime.utcnow():
			raise ValueError("Promo code expired")
		user = await session.get(User, user_id)
		if not user:
			raise ValueError("User not found")
		user.balance += promo.amount
		promo.uses_left -= 1
		await session.commit()
		return promo.amount
