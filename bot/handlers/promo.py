from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import get_or_create_user, redeem_promo
from bot import context

router = Router()


@router.message(Command("promo"))
@router.message(F.text == "🎁 Промокод")
async def cmd_promo(message: Message) -> None:
    await message.answer("Отправьте промокод одним сообщением (или используйте: /use CODE)")


@router.message(Command("use"))
async def cmd_use(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите код: /use CODE")
        return
    code = parts[1].strip()
    await handle_promo_code(message, code)


@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{3,64}$"))
async def any_code_text(message: Message) -> None:
    code = (message.text or "").strip()
    await handle_promo_code(message, code)


async def handle_promo_code(message: Message, code: str) -> None:
    try:
        settings = context.settings
        assert settings is not None

        user = await get_or_create_user(
            tg_id=message.from_user.id,
            username=message.from_user.username,
            init_points=settings.init_points,
        )

        added = await redeem_promo(user.id, code)
        await message.answer(f"🎉 Промокод применён! Начислено {added} баллов.")
    except ValueError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        await message.answer("❌ Не удалось применить промокод. Попробуйте позже.")
        print(e)
