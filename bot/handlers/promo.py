from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import get_or_create_user, redeem_promo
from bot.utils.logger import audit
from bot import context

router = Router()

# Пользователи, ожидающие ввода промокода
if not hasattr(context, "waiting_for_promo"):
    context.waiting_for_promo = set()


@router.message(Command("promo"))
@router.message(F.text == "🎁 Промокод")
async def cmd_promo(message: Message) -> None:
    """Пользователь нажал кнопку или вызвал команду промокода."""
    context.waiting_for_promo.add(message.from_user.id)
    await message.answer("Отправьте промокод одним сообщением (или используйте: /use CODE)")


@router.message(Command("use"))
async def cmd_use(message: Message) -> None:
    """Команда /use для ввода кода прямо в сообщении."""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажите код: /use CODE")
        return
    code = parts[1].strip()
    await handle_promo_code(message, code)


@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{3,64}$"))
async def any_code_text(message: Message) -> None:
    """Ловим код только если пользователь нажал кнопку или вызвал /promo."""
    user_id = message.from_user.id
    if user_id not in context.waiting_for_promo:
        return  # Игнорируем обычные сообщения
    code = (message.text or "").strip()
    await handle_promo_code(message, code)


async def handle_promo_code(message: Message, code: str) -> None:
    """Обработка введенного промокода."""
    user_id = message.from_user.id
    if user_id in context.waiting_for_promo:
        context.waiting_for_promo.remove(user_id)  # Убираем флаг

    try:
        settings = context.settings
        logger = context.logger
        assert settings is not None

        user = await get_or_create_user(
            tg_id=user_id,
            username=message.from_user.username,
            init_points=settings.init_points,
        )

        added = await redeem_promo(user.id, code)

        audit(logger, "promo_redeemed", {
            "user_id": user.id,
            "tg_id": user_id,
            "username": message.from_user.username,
            "promo_code": code,
            "points_added": added,
        })

        await message.answer(f"🎉 Промокод применён! Начислено {added} баллов.")

    except ValueError as e:
        await message.answer(f"❌ {e}")
    except Exception as e:
        await message.answer("❌ Не удалось применить промокод. Попробуйте позже.")
        print(e)
