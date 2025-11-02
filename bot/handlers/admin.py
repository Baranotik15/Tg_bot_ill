from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from bot import context
from bot.db import PromoCode, get_session, Event, EventStatus, User
from sqlalchemy import select
from datetime import datetime, timedelta

router = Router()


def is_admin(user_id: int) -> bool:
    settings = context.settings
    return bool(settings and user_id in settings.admin_ids)


def is_creating_event(message: Message) -> bool:
    """Проверка, что админ в процессе создания события"""
    user_id = message.from_user.id
    return (
        is_admin(user_id) and
        hasattr(context, 'pending_events') and
        user_id in context.pending_events
    )


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
        existing = await session.execute(select(PromoCode).where(PromoCode.code == code))
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

    context.creating_promo[message.from_user.id] = False

    await message.answer(
        f"✅ Промокод {code} создан!\n"
        f"💰 Сумма: {amount}\n"
        f"🔁 Использований: {uses}\n"
        f"⏳ Срок: {days or 'без ограничений'} дней"
    )


@router.message(F.text == "⚡ Начать событие")
async def start_event_btn(message: Message):
    """Старт создания события (через обычную кнопку)"""
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    if not hasattr(context, "pending_events"):
        context.pending_events = {}

    context.pending_events[message.from_user.id] = {"step": "red_odds"}
    await message.answer("Введите коэффициент для красных (например, 1.5):")


@router.message(F.text.regexp(r"^\d+(\.\d+)?$"), is_creating_event)
async def set_coefficient(message: Message):
    """Обработка ввода коэффициентов - ТОЛЬКО для админов создающих событие"""
    user_id = message.from_user.id
    user_event = context.pending_events[user_id]
    coefficient = float(message.text)

    if user_event.get("step") == "red_odds":
        user_event["red_odds"] = coefficient
        user_event["step"] = "black_odds"
        await message.answer("Теперь введите коэффициент для черных:")
        return

    if user_event.get("step") == "black_odds":
        user_event["black_odds"] = coefficient

        async with get_session()() as session:
            event = Event(
                name=f"Ставка {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
                description=f"Красные: {user_event['red_odds']} / Черные: {user_event['black_odds']}",
                status=EventStatus.OPEN,
                red_odds=user_event['red_odds'],
                black_odds=user_event['black_odds']
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)

            if hasattr(context, 'logger'):
                context.logger.info(
                    f"[ADMIN] Создано событие {event.id}: "
                    f"red_odds={event.red_odds}, black_odds={event.black_odds}"
                )

            event_id = event.id
            red_odds = event.red_odds
            black_odds = event.black_odds

        await message.answer(
            f"✅ Событие создано!\n"
            f"Красные: X{user_event['red_odds']}\n"
            f"Черные: X{user_event['black_odds']}"
        )

        async with get_session()() as session:
            users_result = await session.execute(select(User))
            users = users_result.scalars().all()

            sent_count = 0
            failed_count = 0

            for u in users:
                try:
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text=f"🔴 Красные x{red_odds}",
                                    callback_data=f"bet_red:{event_id}"
                                ),
                                InlineKeyboardButton(
                                    text=f"⚫ Черные x{black_odds}",
                                    callback_data=f"bet_black:{event_id}"
                                )
                            ]
                        ]
                    )
                    await context.bot.send_message(
                        u.tg_id,
                        f"🎲 <b>Начался матч!</b>\n"
                        f"Выберите команду для ставки:\n\n"
                        f"💳 Ваш баланс: <b>{u.balance}</b> баллов",
                        reply_markup=keyboard
                    )
                    sent_count += 1
                except Exception as e:
                    failed_count += 1
                    if hasattr(context, 'logger'):
                        context.logger.warning(f"[ADMIN] Не удалось отправить уведомление пользователю {u.tg_id}: {e}")
                    continue

            if hasattr(context, 'logger'):
                context.logger.info(f"[ADMIN] Уведомления отправлены: {sent_count} успешно, {failed_count} ошибок")

        del context.pending_events[user_id]
