from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from sqlalchemy import desc

import bot.db as db
from bot.db import User


router = Router()


@router.message(Command("top"))
@router.message(F.text == "🏆 Рейтинг")
async def cmd_top(message: Message) -> None:
    assert db.AsyncSessionLocal is not None
    async with db.AsyncSessionLocal() as session:
        result = await session.execute(
            User.__table__.select().order_by(desc(User.balance)).limit(20)
        )
        rows = result.fetchall()
        lines: list[str] = ["Топ пользователей (по баллам):"]
        for idx, r in enumerate(rows, start=1):
            username = r.username or f"id{r.tg_id}"
            lines.append(f"{idx}. {username}: {r.balance}")
        await message.answer("\n".join(lines))
