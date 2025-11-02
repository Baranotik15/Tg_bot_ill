from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from bot import context
from bot.db import get_session, User, Bet, Event, Outcome, EventStatus
from sqlalchemy import select

router = Router()


def log(msg: str):
    """Логирование только в файл"""
    if getattr(context, "logger", None):
        context.logger.info(f"[BETTING] {msg}")


def is_pending_bet(message: Message) -> bool:
    """Проверка, что пользователь в режиме ставки"""
    user_id = message.from_user.id
    return (
            hasattr(context, 'pending_bets') and
            user_id in context.pending_bets and
            not message.text.startswith('/')
    )


@router.message(F.text == "🎰 Сделать ставку")
async def show_available_events(message: Message):
    """Показать доступные события для ставок"""
    user_id = message.from_user.id

    async with get_session()() as session:
        events_result = await session.execute(
            select(Event).where(Event.status == EventStatus.OPEN)
        )
        events = events_result.scalars().all()

        if not events:
            await message.answer("❌ Сейчас нет доступных событий для ставок.\nОжидайте начала нового матча!")
            return

        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await message.answer("❌ Ошибка: ваш профиль не найден.")
            return

        keyboard_buttons = []
        for event in events:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"🎲 {event.name} (🔴x{event.red_odds} ⚫x{event.black_odds})",
                    callback_data=f"choose_event:{event.id}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            f"💳 Ваш баланс: <b>{user.balance}</b> баллов\n\n"
            f"📋 Доступные события для ставок:\n"
            f"Выберите событие:",
            reply_markup=keyboard
        )


@router.callback_query(F.data.startswith("choose_event:"))
async def choose_event_for_bet(callback: CallbackQuery):
    """Выбор события и показ команд"""
    user_id = callback.from_user.id
    event_id = int(callback.data.split(":")[1])

    async with get_session()() as session:
        event = await session.get(Event, event_id)
        if not event:
            await callback.answer("❌ Событие не найдено!")
            return

        if event.status != EventStatus.OPEN:
            await callback.answer("❌ Это событие уже завершено!")
            return

        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await callback.answer("❌ Профиль не найден!")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🔴 Красные x{event.red_odds}",
                        callback_data=f"bet_red:{event_id}"
                    ),
                    InlineKeyboardButton(
                        text=f"⚫ Черные x{event.black_odds}",
                        callback_data=f"bet_black:{event_id}"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"🎲 <b>{event.name}</b>\n\n"
            f"💳 Ваш баланс: <b>{user.balance}</b> баллов\n\n"
            f"Выберите команду для ставки:",
            reply_markup=keyboard
        )
        await callback.answer()


@router.callback_query(F.data.startswith("bet_"))
async def select_team(callback: CallbackQuery):
    """Обработка выбора команды"""
    try:
        user_id = callback.from_user.id
        data = callback.data

        if ":" not in data:
            log(f"Неверный формат callback_data: {data}")
            await callback.answer("Ошибка формата данных")
            return

        team_key, event_id = data.split(":")
        event_id = int(event_id)

        team_names = {
            "bet_red": "Красных",
            "bet_black": "Черных"
        }
        team_name = team_names.get(team_key, team_key)

        if hasattr(context, 'pending_events'):
            context.pending_events.pop(user_id, None)

        context.pending_bets[user_id] = {
            "event_id": event_id,
            "team_key": team_key,
            "team_name": team_name
        }

        log(f"Пользователь {user_id} выбрал команду {team_name} для события {event_id}")

        await callback.message.answer(
            f"Вы выбрали команду: <b>{team_name}</b>\n"
            f"Теперь введите сумму баллов для ставки:"
        )
        await callback.answer()

    except Exception as e:
        log(f"Ошибка в select_team: {e}")
        await callback.answer("Произошла ошибка")


@router.message(F.text, is_pending_bet)
async def enter_bet_amount(message: Message):
    """Обработка ввода суммы ставки - ТОЛЬКО для пользователей в режиме ставки"""
    try:
        user_id = message.from_user.id
        text = message.text.strip()

        if not text.isdigit():
            await message.answer("❌ Пожалуйста, введите число (сумму баллов для ставки)")
            return

        amount = int(text)

        if amount <= 0:
            await message.answer("❌ Сумма ставки должна быть больше 0")
            return

        pending = context.pending_bets[user_id]

        async with get_session()() as session:
            user = await session.scalar(select(User).where(User.tg_id == user_id))
            if not user:
                log(f"Пользователь {user_id} не найден в БД")
                await message.answer("❌ Ошибка: ваш профиль не найден.")
                del context.pending_bets[user_id]
                return

            if user.balance < amount:
                await message.answer(
                    f"❌ У вас недостаточно баллов для ставки.\n"
                    f"Ваш баланс: {user.balance} баллов"
                )
                return

            event = await session.get(Event, pending["event_id"])
            if not event:
                log(f"Событие {pending['event_id']} не найдено")
                await message.answer("❌ Ошибка: событие не найдено.")
                del context.pending_bets[user_id]
                return

            if event.status != EventStatus.OPEN:
                await message.answer("❌ Это событие уже завершено. Ставки не принимаются.")
                del context.pending_bets[user_id]
                return

            choice = Outcome.RED if pending["team_key"] == "bet_red" else Outcome.BLACK

            coefficient = event.red_odds if choice == Outcome.RED else event.black_odds

            expected_win = int(amount * coefficient)

            user.balance -= amount

            bet = Bet(
                user_id=user.id,
                event_id=event.id,
                choice=choice,
                amount=amount
            )
            session.add(bet)
            await session.commit()

            log(f"Ставка создана: user_id={user_id}, event_id={event.id}, choice={choice}, amount={amount}")

        del context.pending_bets[user_id]

        await message.answer(
            f"✅ <b>Ваша ставка принята!</b>\n\n"
            f"🎲 Событие: <b>{event.name}</b>\n"
            f"🎯 Команда: <b>{pending['team_name']}</b>\n"
            f"💰 Сумма ставки: <b>{amount}</b> баллов\n"
            f"📊 Коэффициент: <b>x{coefficient}</b>\n"
            f"🏆 Ожидаемый выигрыш: <b>{expected_win}</b> баллов\n"
            f"💳 Ваш баланс: <b>{user.balance}</b> баллов"
        )

    except ValueError as e:
        log(f"Ошибка преобразования числа: {e}")
        await message.answer("❌ Пожалуйста, введите корректное число")
    except Exception as e:
        log(f"Ошибка в enter_bet_amount: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")
        await message.answer("❌ Произошла ошибка при обработке ставки")
