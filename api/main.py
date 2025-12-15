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

from bot import context
from bot.db import get_session, User, Event, EventStatus, Outcome
from bot.handlers.betting import settle_event
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
    if not tg_init_data:
        raise HTTPException(status_code=401)

    settings = context.settings
    assert settings is not None

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
    assert settings is not None

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
    assert settings is not None

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
            name=f"Ставка {now.strftime('%Y-%m-%d %H:%M:%S')}",
            description=f"{title} - Красные: {red_odds} / Черные: {black_odds}",
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
                f"📌 <b>{title}</b>\n\n"
                f"⏱ Время на ставки: <b>10 минут</b>\n"
                f"💳 Ваш баланс: <b>{u.balance}</b>",
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
            raise HTTPException(status_code=404)

        event.outcome = Outcome.RED if winner == "red" else Outcome.BLACK
        event.status = EventStatus.FINISHED
        await session.commit()

    await settle_event(event_id, context.bot)
    return {"ok": True}
