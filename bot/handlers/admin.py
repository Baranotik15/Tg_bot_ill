from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from bot import context
from bot.db import PromoCode, get_session, Event, EventStatus, User
from bot.utils.logger import audit
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

    if not hasattr(context, "creating_promo"):
        context.creating_promo = {}
    context.creating_promo[message.from_user.id] = True

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

    if not getattr(context, "creating_promo", {}).get(message.from_user.id):
        return

    parts = message.text.split()
    code = parts[0]
    amount = int(parts[1])
    uses = int(parts[2]) if len(parts) >= 3 else 1
    days = int(parts[3]) if len(parts) >= 4 else None
    expires_at = datetime.utcnow() + timedelta(days=days) if days else None

    async with get_session()() as session:
        existing = await session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        if existing.scalar_one_or_none():
            await message.answer(f"Промокод {code} уже существует!")
            return

        promo = PromoCode(
            code=code,
            amount=amount,
            uses_left=uses,
            expires_at=expires_at
        )
        session.add(promo)
        await session.commit()

    logger = context.logger
    audit(
        logger,
        "promo_created",
        {
            "admin_tg_id": message.from_user.id,
            "admin_username": message.from_user.username,
            "promo_code": code,
            "amount": amount,
            "uses": uses,
            "days": days,
            "expires_at": expires_at.isoformat() if expires_at else None,
        }
    )

    context.creating_promo[message.from_user.id] = False

    await message.answer(
        f"✅ Промокод {code} создан!\n"
        f"💰 Сумма: {amount}\n"
        f"🔁 Использований: {uses}\n"
        f"⏳ Срок: {days or 'без ограничений'} дней"
    )


@router.message(F.text == "⚡ Начать событие")
async def start_event_btn(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    if not hasattr(context, "current_event"):
        context.current_event = {}

    context.current_event[message.from_user.id] = {"creating_event": True}
    await message.answer("Введите коэффициент для красных (например, 1.5):")


@router.message(F.text.regexp(r"^\d+(\.\d+)?$"))
async def set_coefficient(message: Message):
    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id
    user_event = getattr(context, "current_event", {}).get(user_id)
    if not user_event or not user_event.get("creating_event"):
        return

    if "red_coef" not in user_event:
        user_event["red_coef"] = float(message.text)
        await message.answer("Теперь введите коэффициент для черных:")
        return

    user_event["black_coef"] = float(message.text)

    async with get_session()() as session:
        event = Event(
            name=f"Ставка {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
            description=f"Красные: {user_event['red_coef']} / Черные: {user_event['black_coef']}",
            status=EventStatus.OPEN
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

    await message.answer(
        f"✅ Событие создано!\n"
        f"Красные: X{user_event['red_coef']}\n"
        f"Черные: X{user_event['black_coef']}"
    )

    audit(
        context.logger,
        "event_created",
        {
            "admin_tg_id": message.from_user.id,
            "admin_username": message.from_user.username,
            "red_coef": user_event['red_coef'],
            "black_coef": user_event['black_coef'],
            "event_name": event.name
        }
    )

    async with get_session()() as session:
        users = await session.execute(select(User))
        users = users.scalars().all()
        for u in users:
            try:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Красные", callback_data=f"bet_red:{event.id}"),
                    InlineKeyboardButton(text="Черные", callback_data=f"bet_black:{event.id}")
                ]])
                await context.bot.send_message(
                    u.tg_id,
                    f"🎲 Начался матч!\nВыберите команду для ставки:",
                    reply_markup=keyboard
                )
            except Exception:
                continue

    del context.current_event[user_id]
