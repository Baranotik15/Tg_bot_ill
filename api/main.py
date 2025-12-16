from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from urllib.parse import parse_qsl
import hmac
import hashlib
import json
import os
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import context
from bot.db import (
    get_session,
    User,
    Event,
    EventStatus,
    Outcome,
    Bet, PromoCode, redeem_promo,
)
from bot.handlers.betting import settle_event


app = FastAPI(title="MafBot Web API")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


def verify_init_data(init_data: str, bot_token: str) -> dict:
    data = dict(parse_qsl(init_data))
    hash_received = data.pop("hash", None)
    if not hash_received:
        raise HTTPException(status_code=401)

    auth_date = int(data.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=401)

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))

    secret = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    calc_hash = hmac.new(
        secret,
        check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if calc_hash != hash_received:
        raise HTTPException(status_code=401)

    return data


def get_admin_id(tg_init_data: Optional[str]) -> int:
    settings = context.settings
    data = verify_init_data(tg_init_data, settings.bot_token)
    user = json.loads(data["user"])
    tg_id = int(user["id"])

    if tg_id not in settings.admin_ids:
        raise HTTPException(status_code=403)

    return tg_id


@app.get("/me")
async def get_me(
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    settings = context.settings
    data = verify_init_data(tg_init_data, settings.bot_token)
    user_data = json.loads(data["user"])
    tg_id = int(user_data["id"])

    async with get_session()() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404)

        return {
            "tg_id": tg_id,
            "balance": user.balance,
            "is_admin": tg_id in settings.admin_ids
        }


@app.get("/events")
async def get_events(
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    settings = context.settings
    verify_init_data(tg_init_data, settings.bot_token)

    async with get_session()() as session:
        result = await session.execute(
            select(Event).where(Event.status == EventStatus.OPEN)
        )
        events = result.scalars().all()

        return [
            {
                "id": e.id,
                "title": e.event_title,
                "red_odds": e.red_odds,
                "black_odds": e.black_odds,
                "time_left": e.get_time_left(),
            }
            for e in events if e.is_betting_active()
        ]


# ---------------- ADMIN ----------------

@app.post("/admin/events")
async def create_event(
    payload: dict,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    get_admin_id(tg_init_data)

    title = payload.get("title")
    red_odds = float(payload.get("red_odds", 0))
    black_odds = float(payload.get("black_odds", 0))

    if not title or red_odds <= 0 or black_odds <= 0:
        raise HTTPException(status_code=400)

    now = datetime.utcnow()
    betting_ends_at = now + timedelta(minutes=10)

    async with get_session()() as session:
        event = Event(
            event_title=title,
            name=f"Event {now.isoformat()}",
            description=title,
            status=EventStatus.OPEN,
            red_odds=red_odds,
            black_odds=black_odds,
            betting_starts_at=now,
            betting_ends_at=betting_ends_at
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        users = (await session.execute(select(User))).scalars().all()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text=f"🔴 Красные x{red_odds}",
                    callback_data=f"bet_red:{event.id}"
                ),
                InlineKeyboardButton(
                    text=f"⚫ Черные x{black_odds}",
                    callback_data=f"bet_black:{event.id}"
                )
            ]]
        )

        for u in users:
            try:
                await context.bot.send_message(
                    u.tg_id,
                    f"🎲 <b>Начался матч!</b>\n\n"
                    f"📌 <b>{event.event_title}</b>\n\n"
                    f"⏱ Время на ставки: <b>10 минут</b>\n"
                    f"🎰 Выберите на что поставить:\n\n"
                    f"💳 Ваш баланс: <b>{u.balance}</b> баллов",
                    reply_markup=keyboard
                )
            except Exception:
                pass

    return {"ok": True, "event_id": event.id}



@app.post("/admin/events/{event_id}/finish")
async def finish_event(
    event_id: int,
    payload: dict,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    get_admin_id(tg_init_data)

    winner = payload.get("winner")
    if winner not in ("red", "black"):
        raise HTTPException(status_code=400)

    async with get_session()() as session:
        event = await session.get(Event, event_id)
        if not event or event.status != EventStatus.OPEN:
            raise HTTPException(status_code=400)

        event.outcome = Outcome.RED if winner == "red" else Outcome.BLACK
        await session.commit()

    await settle_event(event_id, context.bot)
    return {"ok": True}


@app.post("/admin/events/{event_id}/odds")
async def change_odds(
    event_id: int,
    payload: dict,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    get_admin_id(tg_init_data)

    red = float(payload.get("red_odds", 0))
    black = float(payload.get("black_odds", 0))

    if red <= 0 or black <= 0:
        raise HTTPException(status_code=400)

    async with get_session()() as session:
        event = await session.get(Event, event_id)
        if not event or event.status != EventStatus.OPEN:
            raise HTTPException(status_code=400)

        event.red_odds = red
        event.black_odds = black
        await session.commit()

    return {"ok": True}


# ---------------- BET ----------------

@app.post("/bet")
async def place_bet(
    payload: dict,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    settings = context.settings
    data = verify_init_data(tg_init_data, settings.bot_token)
    user_data = json.loads(data["user"])
    tg_id = int(user_data["id"])

    event_id = int(payload.get("event_id", 0))
    side = payload.get("side")
    amount = int(payload.get("amount", 0))

    if side not in ("red", "black") or amount <= 0:
        raise HTTPException(status_code=400)

    async with get_session()() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        event = await session.get(Event, event_id)

        if not user or not event:
            raise HTTPException(status_code=404)

        if event.status != EventStatus.OPEN or not event.is_betting_active():
            raise HTTPException(status_code=400)

        if user.balance < amount:
            raise HTTPException(status_code=400, detail="Недостаточно средств")

        odds = event.red_odds if side == "red" else event.black_odds
        expected_win = int(amount * odds)

        bet = Bet(
            user_id=user.id,
            event_id=event.id,
            choice=Outcome.RED if side == "red" else Outcome.BLACK,
            amount=amount,
            odds=odds,
        )

        user.balance -= amount
        session.add(bet)
        await session.commit()

        new_balance = user.balance

    await context.bot.send_message(
        tg_id,
        f"✅ <b>Ваша ставка принята!</b>\n\n"
        f"🎲 <b>Событие:</b> {event.event_title}\n"
        f"🎯 <b>Команда:</b> {'Красных 🔴' if side == 'red' else 'Черных ⚫'}\n"
        f"💰 <b>Сумма ставки:</b> {amount} баллов\n"
        f"📊 <b>Коэффициент:</b> x{odds}\n"
        f"🏆 <b>Ожидаемый выигрыш:</b> {expected_win} баллов 💰\n"
        f"💳 <b>Ваш текущий баланс:</b> {new_balance} баллов"
    )

    return {"ok": True}

@app.get("/top")
async def get_top(
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    settings = context.settings
    verify_init_data(tg_init_data, settings.bot_token)

    async with get_session()() as session:
        result = await session.execute(
            select(User).order_by(User.balance.desc()).limit(5)
        )
        users = result.scalars().all()

        return [
            {
                "username": u.username or f"id{u.tg_id}",
                "balance": u.balance
            }
            for u in users
        ]

@app.post("/admin/promocodes")
async def create_promocode(
    payload: dict,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    get_admin_id(tg_init_data)

    code = payload.get("code")
    amount = payload.get("amount")
    uses_left = payload.get("limit")
    expires_at_raw = payload.get("expires_at")  # optional

    if not code or not isinstance(code, str):
        raise HTTPException(status_code=400, detail="Неверный код")

    try:
        amount = int(amount)
        uses_left = int(uses_left)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Неверные числовые значения")

    if amount <= 0 or uses_left <= 0:
        raise HTTPException(status_code=400, detail="amount и limit должны быть > 0")

    expires_at = None
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат expires_at")

    async with get_session()() as session:
        existing = await session.scalar(
            select(PromoCode).where(PromoCode.code == code.upper())
        )
        if existing:
            raise HTTPException(status_code=400, detail="Промокод уже существует")

        promo = PromoCode(
            code=code.upper(),
            amount=amount,
            uses_left=uses_left,
            expires_at=expires_at,
        )

        session.add(promo)
        await session.commit()
        await session.refresh(promo)

    return {
        "ok": True,
        "promo": {
            "code": promo.code,
            "amount": promo.amount,
            "uses_left": promo.uses_left,
            "expires_at": promo.expires_at,
        }
    }

# ---------------- PROMO REDEEM  ----------------

@app.post("/promocode/redeem")
async def redeem_promocode(
    payload: dict,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
):
    settings = context.settings
    data = verify_init_data(tg_init_data, settings.bot_token)
    user_data = json.loads(data["user"])
    tg_id = int(user_data["id"])

    code = payload.get("code")

    if not code or not isinstance(code, str):
        raise HTTPException(status_code=400, detail="Неверный промокод")

    async with get_session()() as session:
        user = await session.scalar(
            select(User).where(User.tg_id == tg_id)
        )
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

    try:
        added = await redeem_promo(user.id, code.upper())
        await context.bot.send_message(
            tg_id,
            f"🎉 <b>Промокод применён!</b>\n"
            f"➕ Начислено {added} баллов 💵"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Не удалось применить промокод"
        )

    return {
        "ok": True,
        "added": added
    }
