from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import desc, select, func

import bot.db as db
from bot.db import User

router = Router()


@router.message(Command("top"))
@router.message(F.text == "🏆 Рейтинг")
async def cmd_top(message: Message) -> None:
    async with db.get_session()() as session:
        result = await session.execute(
            User.__table__.select().order_by(desc(User.balance)).limit(20)
        )
        rows = result.fetchall()
        lines: list[str] = ["Топ пользователей (по баллам):"]
        for idx, r in enumerate(rows, start=1):
            username = r.username or f"id{r.tg_id}"
            lines.append(f"{idx}. {username}: {r.balance}")
        await message.answer("\n".join(lines))


@router.message(Command("me"))
@router.message(F.text == "📊 Мой рейтинг")
async def cmd_me(message: Message) -> None:
    tg_id = message.from_user.id

    async with db.get_session()() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Вы ещё не зарегистрированы в системе 😕")
            return

        position_result = await session.execute(
            select(func.count()).where(User.balance > user.balance)
        )
        higher_count = position_result.scalar() or 0
        position = higher_count + 1

        total_result = await session.execute(select(func.count()).select_from(User))
        total_users = total_result.scalar() or 0

        username = user.username or f"id{user.tg_id}"
        await message.answer(
            f"📊 <b>Ваш рейтинг</b>\n\n"
            f"👤 Пользователь: {username}\n"
            f"💰 Баланс: <b>{user.balance}</b>\n"
            f"🏅 Место: <b>{position}</b> из {total_users}"
        )
