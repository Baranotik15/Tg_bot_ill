from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.db import get_or_create_user
from bot.keyboards import main_menu
from bot import context
from bot.utils.logger import audit  # добавляем импорт


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    settings = context.settings
    assert settings is not None

    user = await get_or_create_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        init_points=settings.init_points,
    )

    # Логирование регистрации / входа
    audit(
        context.logger,
        "user_start",
        {
            "tg_id": message.from_user.id,
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "balance": user.balance,
            "new_user": user.first_seen == user.created_at,  # или другой способ понять, что новый
        },
    )

    await message.answer(
        text=(
            f"Привет, {message.from_user.full_name}!\n"
            f"На твоём счету: {user.balance} баллов.\n\n"
            "Выбирай действие из меню ниже."
        ),
        reply_markup=main_menu(message.from_user.id),
    )
