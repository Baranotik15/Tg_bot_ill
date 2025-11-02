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
        all_events = events_result.scalars().all()

        events = [event for event in all_events if event.is_betting_active()]

        if not events:
            await message.answer("❌ Сейчас нет доступных событий для ставок.\nОжидайте начала новой игры!")
            return

        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await message.answer("❌ Ошибка: ваш профиль не найден.")
            return

        keyboard_buttons = []
        for event in events:
            time_left = event.get_time_left()
            minutes_left = time_left // 60
            seconds_left = time_left % 60

            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"🎲 {event.event_title} (🔴x{event.red_odds} ⚫x{event.black_odds}) ⏱ {minutes_left}:{seconds_left:02d}",
                    callback_data=f"choose_event:{event.id}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            f"💳 Ваш баланс: <b>{user.balance}</b> баллов 💵\n\n"
            f"📋 Доступные события для ставок\n"
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

        if not event.is_betting_active():
            await callback.answer("⏱ Время для ставок истекло!", show_alert=True)
            return

        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            await callback.answer("❌ Профиль не найден!")
            return

        time_left = event.get_time_left()
        minutes_left = time_left // 60
        seconds_left = time_left % 60

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
            f"🎲 <b>{event.event_title}</b>\n\n"
            f"⏱ Времени осталось: <b>{minutes_left}:{seconds_left:02d}</b>\n"
            f"💳 Ваш баланс: <b>{user.balance}</b> баллов 💵\n\n"
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

        async with get_session()() as session:
            event = await session.get(Event, event_id)
            if not event or not event.is_betting_active():
                await callback.answer("⏱ Время для ставок истекло!", show_alert=True)
                return

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

        if team_name == "Черных":
            await callback.message.answer(
                f"🕶️💣 <b>Значит ты за Мафию ?</b> 💣🕶️\n\n"
                f"Ночь на дворе, ставки высоки — покажи, сколько поставишь 💼💵\n\n"
                f"💰 Введи сумму баллов для ставки:"
            )
        elif team_name == "Красных":
            await callback.message.answer(
                f"💥🏙️ <b>Ставишь на Мирных?</b> 🔥\n\n"
                f"Пусть улицы зальются светом, а правда восторжествует! ⚖️\n\n"
                f"💰 Введи сумму баллов, для ставки:"
            )

        await callback.answer()

    except Exception as e:
        log(f"Ошибка в select_team: {e}")
        await callback.answer("Произошла ошибка")


@router.message(F.text, is_pending_bet)
async def enter_bet_amount(message: Message):
    """Обработка ввода суммы ставки с возвратом средств при ошибке"""
    user_id = message.from_user.id
    text = message.text.strip()
    amount_deducted = 0

    try:
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
                    f"💳 Ваш баланс: {user.balance} баллов"
                )
                return

            event = await session.get(Event, pending["event_id"])
            if not event:
                log(f"Событие {pending['event_id']} не найдено")
                await message.answer("❌ Ошибка: событие не найдено.")
                del context.pending_bets[user_id]
                return

            if not event.is_betting_active():
                await message.answer("⏱ Время для ставок истекло!")
                del context.pending_bets[user_id]
                return

            choice = Outcome.RED if pending["team_key"] == "bet_red" else Outcome.BLACK
            coefficient = event.red_odds if choice == Outcome.RED else event.black_odds
            expected_win = int(amount * coefficient)

            user.balance -= amount
            amount_deducted = amount

            log(f"Списано {amount} баллов у пользователя {user_id}")

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
            f"🎲 Событие: <b>{event.event_title}</b>\n"
            f"🎯 Команда: <b>{pending['team_name']}</b>\n"
            f"💰 Сумма ставки: <b>{amount}</b> баллов\n"
            f"📊 Коэффициент: <b>x{coefficient}</b>\n"
            f"🏆 Ожидаемый выигрыш: <b>{expected_win}</b> баллов 💰\n"
            f"💳 Ваш текущий баланс: <b>{user.balance}</b> баллов"
        )

    except ValueError as e:
        log(f"Ошибка преобразования числа: {e}")
        await message.answer("❌ Пожалуйста, введите корректное число")

    except Exception as e:
        log(f"❌ КРИТИЧЕСКАЯ ОШИБКА в enter_bet_amount: {e}")
        import traceback
        log(f"Traceback: {traceback.format_exc()}")

        if amount_deducted > 0:
            try:
                async with get_session()() as session:
                    user = await session.scalar(select(User).where(User.tg_id == user_id))
                    if user:
                        user.balance += amount_deducted
                        await session.commit()
                        log(f"🔄 Возвращено {amount_deducted} баллов пользователю {user_id}")

                        await message.answer(
                            f"❌ Произошла ошибка при обработке ставки.\n"
                            f"💰 Ваши <b>{amount_deducted}</b> баллов возвращены на счет.\n"
                            f"💳 Текущий баланс: <b>{user.balance}</b> баллов"
                        )
                    else:
                        log(f"⚠️ Не удалось вернуть средства: пользователь {user_id} не найден")
                        await message.answer("❌ Произошла критическая ошибка. Обратитесь к администратору.")

            except Exception as refund_error:
                log(f"❌❌ ОШИБКА ВОЗВРАТА СРЕДСТВ: {refund_error}")
                await message.answer(
                    f"❌ Критическая ошибка при возврате средств!\n"
                    f"Обратитесь к администратору с ID: {user_id}"
                )
        else:
            await message.answer("❌ Произошла ошибка при обработке ставки. Попробуйте еще раз.")

        if user_id in context.pending_bets:
            del context.pending_bets[user_id]
