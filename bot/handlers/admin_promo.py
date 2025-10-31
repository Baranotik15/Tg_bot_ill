from aiogram import Router, F
from aiogram.types import Message
from bot import context
from bot.db import PromoCode, get_session  # используем get_session
from sqlalchemy import select
from datetime import datetime, timedelta

router = Router()


def is_admin(user_id: int) -> bool:
    settings = context.settings
    return bool(settings and user_id in settings.admin_ids)


@router.message(F.text == "💳 Создать промокод")
async def btn_create_promo(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    await message.answer(
        "Чтобы создать промокод, отправьте его в формате:\n"
        "`CODE AMOUNT [USES] [DAYS]`\n"
        "Пример: `PROMO100 500 3 7` (код, сумма, количество использований, срок в днях)",
        parse_mode="Markdown"
    )


@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{3,64} \d+(\s\d+)?(\s\d+)?$"))
async def create_promo_from_text(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    code = parts[0]
    amount = int(parts[1])
    uses = int(parts[2]) if len(parts) >= 3 else 1
    days = int(parts[3]) if len(parts) >= 4 else None
    expires_at = datetime.utcnow() + timedelta(days=days) if days else None

    async with get_session()() as session:
        existing = await session.execute(select(PromoCode).where(PromoCode.code == code))
        if existing.scalar_one_or_none():
            await message.answer(f"Промокод {code} уже существует!")
            return

        promo = PromoCode(code=code, amount=amount, uses_left=uses, expires_at=expires_at)
        session.add(promo)
        await session.commit()

    await message.answer(
        f"✅ Промокод {code} создан!\n"
        f"💰 Сумма: {amount}\n"
        f"🔁 Использований: {uses}\n"
        f"⏳ Срок: {days or 'без ограничений'} дней"
    )
