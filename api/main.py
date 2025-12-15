from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
import hmac
import hashlib
from urllib.parse import parse_qsl, unquote_plus
import os

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


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    init_data = unquote_plus(init_data)
    data = dict(parse_qsl(init_data, strict_parsing=True))

    hash_received = data.pop("hash", None)
    if not hash_received:
        raise HTTPException(status_code=403, detail="Missing hash")

    data.pop("signature", None)

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    calculated_hash = hmac.new(
        bot_token.encode(),
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if calculated_hash != hash_received:
        raise HTTPException(status_code=403, detail="Invalid Telegram signature")

    return data


@app.get("/me")
async def get_me(
    request: Request,
    authorization: Optional[str] = Header(None),
    tg_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    init_data_query: Optional[str] = None,
):
    logger = context.logger
    settings = context.settings

    init_data = (tg_init_data or authorization or init_data_query or "").strip()
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing auth")

    assert settings is not None

    try:
        data = verify_telegram_init_data(init_data, settings.bot_token)
    except Exception as e:
        if logger:
            logger.error("verify failed: %s", e)
        raise

    tg_id = int(data["user[id]"])

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


@app.post("/debug-init")
async def debug_init(request: Request):
    body = await request.body()
    print("INIT_DATA FROM WEBAPP:", body.decode(errors="ignore"))
    return {"ok": True}
