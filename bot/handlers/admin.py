from datetime import datetime, timedelta
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import Outcome, PromoCode, AsyncSessionLocal
from bot import context
from sqlalchemy import select


router = Router()


def is_admin(message: Message) -> bool:
	settings = context.settings
	return bool(settings and message.from_user.id in settings.admin_ids)


@router.message(Command("admin_create_promo"))
async def admin_create_promo(message: Message) -> None:
    if not is_admin(message):
        await message.answer("Недостаточно прав.")
        return

    # Ожидаемый формат: /admin_create_promo CODE AMOUNT [USES] [DAYS]
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Использование: /admin_create_promo CODE AMOUNT [USES] [DAYS]")
        return

    code = parts[1].strip()
    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer("Неправильное значение AMOUNT. Должно быть число.")
        return

    uses = int(parts[3]) if len(parts) >= 4 else 1
    days = int(parts[4]) if len(parts) >= 5 else None
    expires_at = datetime.utcnow() + timedelta(days=days) if days else None

    try:
        assert AsyncSessionLocal is not None
        async with AsyncSessionLocal() as session:
            # Проверка на существующий код
            existing = await session.execute(select(PromoCode).where(PromoCode.code == code))
            if existing.scalar_one_or_none():
                await message.answer(f"Промокод {code} уже существует!")
                return

            promo = PromoCode(code=code, amount=amount, uses_left=uses, expires_at=expires_at)
            session.add(promo)
            await session.commit()
        await message.answer(f"Промокод {code} создан: +{amount} баллов, uses={uses}, expires_in={days or 'нет'}")
    except Exception as e:
        await message.answer(f"Ошибка при создании промокода: {e}")
