from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
import hmac
import hashlib
from urllib.parse import parse_qsl
import os
import json

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
        raise HTTPException(status_code=403, detail="Missing hash")

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
        raise HTTPException(status_code=403, detail="Invalid Telegram hash")

    return data




@app.get("/me")
async def get_me(
    request: Request,
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
):
    if not tg_init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram init data")

    settings = context.settings
    logger = context.logger
    assert settings is not None

    try:
        # 🔍 временно логируем сырой initData
        if logger:
            logger.info("TG INIT DATA RAW: %s", tg_init_data)

        data = verify_telegram_webapp_init_data(tg_init_data, settings.bot_token)
        user_data = json.loads(data["user"])
        tg_id = int(user_data["id"])

    except Exception as e:
        if logger:
            logger.error("verify failed: %s", e)
        raise HTTPException(status_code=403, detail="Invalid init data")

    async with get_session()() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "tg_id": user.tg_id,
            "username": user.username,
            "balance": user.balance,
        }


@app.get("/events")
async def get_events():
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
