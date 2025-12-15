from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
import hmac
import hashlib
from urllib.parse import parse_qsl
import os
import json
import time
from datetime import datetime, timedelta

from sqlalchemy import select

from bot.db import get_session, User, Event, EventStatus
from bot import context

app = FastAPI(title="MafBot Web API")

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")

app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(WEB_DIR, "index.html"))


def verify_telegram_webapp_init_data(init_data: str, bot_token: str) -> dict:
    data = dict(parse_qsl(init_data))

    hash_received = data.pop("hash", None)
    if not hash_received:
        raise HTTPException(status_code=403)

    auth_date = int(data.get("auth_date", 0))
    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=403)

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode(),
        hashlib.sha256
    ).digest()

    hash_calculated = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if hash_calculated != hash_received:
        raise HTTPException(status_code=403)

    return data


@app.get("/me")
async def get_me(
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    if not tg_init_data:
        raise HTTPException(status_code=401)

    settings = context.settings
    assert settings is not None

    data = verify_telegram_webapp_init_data(tg_init_data, settings.bot_token)
    user_data = json.loads(data["user"])
    tg_id = int(user_data["id"])

    async with get_session()() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404)

        return {
            "tg_id": user.tg_id,
            "username": user.username,
            "balance": user.balance,
            "is_admin": tg_id in settings.ADMIN_IDS,
        }


@app.get("/events")
async def get_events(
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    if not tg_init_data:
        raise HTTPException(status_code=401)

    settings = context.settings
    assert settings is not None

    verify_telegram_webapp_init_data(tg_init_data, settings.bot_token)

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
            for e in events
            if e.is_betting_active()
        ]


@app.post("/admin/events")
async def create_event(
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    if not tg_init_data:
        raise HTTPException(status_code=401)

    settings = context.settings
    assert settings is not None

    data = verify_telegram_webapp_init_data(tg_init_data, settings.bot_token)
    user_data = json.loads(data["user"])
    tg_id = int(user_data["id"])

    if tg_id not in settings.ADMIN_IDS:
        raise HTTPException(status_code=403)

    now = datetime.utcnow()
    betting_ends_at = now + timedelta(minutes=10)

    async with get_session()() as session:
        event = Event(
            event_title="Новое событие",
            name=f"Event {now.strftime('%Y-%m-%d %H:%M:%S')}",
            description="Создано из WebApp",
            status=EventStatus.OPEN,
            red_odds=2.0,
            black_odds=2.0,
            betting_starts_at=now,
            betting_ends_at=betting_ends_at,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

        return {
            "id": event.id,
            "title": event.event_title,
            "red_odds": event.red_odds,
            "black_odds": event.black_odds,
            "time_left": int((betting_ends_at - now).total_seconds()),
        }

