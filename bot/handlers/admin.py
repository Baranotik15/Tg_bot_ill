from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from sqlalchemy import select
from datetime import datetime, timedelta
from bot import context
from bot.db import PromoCode, get_session, Event, EventStatus, User, Bet, Outcome
from bot.handlers.betting import settle_event


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
        "Пример: `PROMO100 500 3 7`\n"
        "(Код, сумма, количество использований, срок в днях)",
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
        f"✅ Промокод <code>{code}</code> создан!\n"
        f"💰 Сумма: {amount}\n"
        f"🔁 Использований: {uses}\n"
        f"⏳ Срок: {days or 'без ограничений'} дней"
    )


@router.message(F.text == "⚡ Начать событие")
async def start_event_btn(message: Message):
    """Старт создания события"""
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    if not hasattr(context, "pending_events"):
        context.pending_events = {}

    context.pending_events[message.from_user.id] = {"step": "event_title"}
    await message.answer("📝 Введите название для события:")


@router.message(F.text, is_creating_event)
async def handle_event_creation(message: Message):
    """Обработка создания события по шагам"""
    user_id = message.from_user.id
    user_event = context.pending_events[user_id]
    text = message.text.strip()

    if user_event.get("step") == "event_title":
        if len(text) < 3:
            await message.answer("❌ Название должно содержать минимум 3 символа. Попробуйте снова:")
            return

        user_event["event_title"] = text
        user_event["step"] = "red_odds"
        await message.answer(f"✅ Название: <b>{text}</b>\n\nВведите коэффициент для красных 🔴 (например, 1.5):")
        return

    if user_event.get("step") == "red_odds":
        try:
            coefficient = float(text)
            if coefficient <= 0:
                await message.answer("❌ Коэффициент должен быть больше 0. Попробуйте снова:")
                return

            user_event["red_odds"] = coefficient
            user_event["step"] = "black_odds"
            await message.answer("Теперь введите коэффициент для черных ⚫:")
            return
        except ValueError:
            await message.answer("❌ Введите корректное число (например, 1.5):")
            return

    if user_event.get("step") == "black_odds":
        try:
            coefficient = float(text)
            if coefficient <= 0:
                await message.answer("❌ Коэффициент должен быть больше 0. Попробуйте снова:")
                return

            user_event["black_odds"] = coefficient

            async with get_session()() as session:
                now = datetime.utcnow()
                betting_end_time = now + timedelta(minutes=10)
                event = Event(
                    event_title=user_event['event_title'],
                    name=f"Ставка {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    description=f"{user_event['event_title']} - Красные: {user_event['red_odds']} / Черные: {user_event['black_odds']}",
                    status=EventStatus.OPEN,
                    red_odds=user_event['red_odds'],
                    black_odds=user_event['black_odds'],
                    betting_starts_at=now,
                    betting_ends_at=betting_end_time
                )
                session.add(event)
                await session.commit()
                await session.refresh(event)

                if hasattr(context, 'logger'):
                    context.logger.info(
                        f"[ADMIN] Создано событие {event.id}: "
                        f"title='{event.event_title}', red_odds={event.red_odds}, black_odds={event.black_odds}, "
                        f"betting_ends_at={betting_end_time}"
                    )

                event_id = event.id
                event_title = event.event_title
                red_odds = event.red_odds
                black_odds = event.black_odds

            await message.answer(
                f"✅ Событие создано!\n"
                f"📌 Название: <b>{event_title}</b>\n"
                f"🔴 Красные: X{red_odds}\n"
                f"⚫ Черные: X{black_odds}\n"
                f"⏱ Ставки принимаются: <b>10 минут</b>"
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
                            f"🎲 <b>Начался матч!</b>\n\n"
                            f"📌 <b>{event_title}</b>\n\n"
                            f"⏱ Время на ставки: <b>10 минут</b>\n"
                            f"🎰 Выберите на что поставить:\n\n"
                            f"💳 Ваш баланс:<code><b>{u.balance}</b></code> баллов",
                            reply_markup=keyboard
                        )
                        sent_count += 1
                    except Exception as e:
                        failed_count += 1
                        if hasattr(context, 'logger'):
                            context.logger.warning(
                                f"[ADMIN] Не удалось отправить уведомление пользователю {u.tg_id}: {e}")
                        continue

                if hasattr(context, 'logger'):
                    context.logger.info(f"[ADMIN] Уведомления отправлены: {sent_count} успешно, {failed_count} ошибок")

            del context.pending_events[user_id]

        except ValueError:
            await message.answer("❌ Введите корректное число (например, 1.5):")
            return


@router.message(F.text == "🏁 Завершить событие")
async def finish_event_btn(message: Message):
    """Начало завершения события"""
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    async with get_session()() as session:
        events_result = await session.execute(
            select(Event).where(Event.status == EventStatus.OPEN)
        )
        events = events_result.scalars().all()

        if not events:
            await message.answer("❌ Нет открытых событий для завершения.")
            return

        if len(events) == 1:
            event = events[0]

            if not hasattr(context, "finishing_events"):
                context.finishing_events = {}

            context.finishing_events[message.from_user.id] = {"event_id": event.id}

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔴 Красные", callback_data=f"win_red:{event.id}"),
                        InlineKeyboardButton(text="⚫ Черные", callback_data=f"win_black:{event.id}")
                    ]
                ]
            )

            await message.answer(
                f"🏁 Завершение события:\n"
                f"📌 <b>{event.event_title}</b>\n\n"
                f"Кто победил?",
                reply_markup=keyboard
            )
        else:
            keyboard_buttons = []
            for event in events:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"📌 {event.event_title}",
                        callback_data=f"select_event:{event.id}"
                    )
                ])

            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await message.answer("Выберите событие для завершения:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("select_event:"))
async def select_event_to_finish(callback: CallbackQuery):
    """Выбор события для завершения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав.")
        return

    event_id = int(callback.data.split(":")[1])

    async with get_session()() as session:
        event = await session.get(Event, event_id)
        if not event:
            await callback.answer("Событие не найдено!")
            return

    if not hasattr(context, "finishing_events"):
        context.finishing_events = {}

    context.finishing_events[callback.from_user.id] = {"event_id": event_id}

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔴 Красные", callback_data=f"win_red:{event_id}"),
                InlineKeyboardButton(text="⚫ Черные", callback_data=f"win_black:{event_id}")
            ]
        ]
    )

    await callback.message.edit_text(
        f"🏁 Завершение события:\n"
        f"📌 <b>{event.event_title}</b>\n\n"
        f"Кто победил?",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("win_"))
async def process_event_result(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав.")
        return

    data_parts = callback.data.split(":")
    winner_key = data_parts[0]
    event_id = int(data_parts[1])

    async with get_session()() as session:
        event = await session.get(Event, event_id)
        if not event:
            await callback.answer("Событие не найдено!")
            return

        if event.status != EventStatus.OPEN:
            await callback.answer("Событие уже завершено!")
            return

        event.outcome = Outcome.RED if winner_key == "win_red" else Outcome.BLACK
        await session.commit()

    await settle_event(event_id, context.bot)

    await callback.message.edit_text(
        f"✅ Событие завершено!\n"
        f"📌 Событие: {event.event_title}\n"
        f"🏆 Победитель: {'Красные' if event.outcome == Outcome.RED else 'Черные'}\n"
        f"💳 Выплаты и расчёт ставок произведены автоматически."
    )
    await callback.answer()


@router.message(F.text == "📢 Рассылка всем")
async def broadcast_message_btn(message: Message):
    """Начало массовой рассылки"""
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    if not hasattr(context, "broadcasting"):
        context.broadcasting = {}

    context.broadcasting[message.from_user.id] = {"waiting_for_message": True}

    await message.answer(
        "📣 <b>Режим массовой рассылки активирован!</b> 💼\n\n"
        "🕶 <i>Пришло время донести слово до каждого игрока…</i>\n\n"
        "Отправь сообщение, которое хочешь разослать всем пользователям 💬\n\n"
        "📦 <b>Поддерживаемые форматы:</b>\n"
        "• 📝 Текст (с <b>HTML</b>-разметкой)\n"
        "• 🖼 Фото\n"
        "• 🎞 Видео\n"
        "• 🎬 GIF-анимации\n"
        "• 🎭 Стикеры\n"
        "• 📚 Документы\n\n"
        "🚫 Для отмены рассылки — отправь команду <code>/cancel</code>"
    )


def is_broadcasting(message: Message) -> bool:
    """Проверка, что админ в режиме рассылки"""
    user_id = message.from_user.id
    return (
            is_admin(user_id) and
            hasattr(context, 'broadcasting') and
            user_id in context.broadcasting and
            context.broadcasting[user_id].get("waiting_for_message")
    )


@router.message(F.text == "/cancel", is_broadcasting)
async def cancel_broadcast(message: Message):
    """Отмена рассылки"""
    user_id = message.from_user.id
    if user_id in context.broadcasting:
        del context.broadcasting[user_id]
    await message.answer("❌ Рассылка отменена.")


@router.message(is_broadcasting)
async def handle_broadcast_message(message: Message):
    """Обработка сообщения для рассылки"""
    user_id = message.from_user.id

    if not is_admin(user_id):
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, разослать", callback_data="broadcast_confirm"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="broadcast_cancel")
            ]
        ]
    )

    context.broadcasting[user_id]["message"] = message
    context.broadcasting[user_id]["waiting_for_message"] = False

    await message.answer(
        "📢 <b>Подтвердите рассылку</b>\n\n"
        "Это сообщение будет отправлено ВСЕМ пользователям бота.\n"
        "Вы уверены?",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast_confirm(callback: CallbackQuery):
    """Отмена подтвержденной рассылки"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("Недостаточно прав.")
        return

    if user_id in context.broadcasting:
        del context.broadcasting[user_id]

    await callback.message.edit_text("❌ Рассылка отменена.")
    await callback.answer()


@router.callback_query(F.data == "broadcast_confirm")
async def confirm_broadcast(callback: CallbackQuery):
    """Подтверждение и выполнение рассылки"""
    user_id = callback.from_user.id

    if not is_admin(user_id):
        await callback.answer("Недостаточно прав.")
        return

    if user_id not in context.broadcasting or "message" not in context.broadcasting[user_id]:
        await callback.answer("Ошибка: сообщение не найдено")
        return

    original_message = context.broadcasting[user_id]["message"]

    await callback.message.edit_text("📤 Начинаю рассылку...")

    async with get_session()() as session:
        users_result = await session.execute(select(User))
        users = users_result.scalars().all()

        total_users = len(users)
        sent_count = 0
        failed_count = 0

        for user in users:
            try:
                if original_message.photo:
                    await context.bot.send_photo(
                        user.tg_id,
                        photo=original_message.photo[-1].file_id,
                        caption=original_message.caption or ""
                    )
                elif original_message.video:
                    await context.bot.send_video(
                        user.tg_id,
                        video=original_message.video.file_id,
                        caption=original_message.caption or ""
                    )
                elif original_message.document:
                    await context.bot.send_document(
                        user.tg_id,
                        document=original_message.document.file_id,
                        caption=original_message.caption or ""
                    )
                elif original_message.text:
                    await context.bot.send_message(
                        user.tg_id,
                        text=original_message.text
                    )
                else:
                    continue

                sent_count += 1

            except Exception as e:
                failed_count += 1
                if hasattr(context, 'logger'):
                    context.logger.warning(f"[BROADCAST] Не удалось отправить пользователю {user.tg_id}: {e}")
                continue

    del context.broadcasting[user_id]

    await callback.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ Успешно отправлено: <b>{sent_count}</b>\n"
        f"❌ Ошибок: <b>{failed_count}</b>"
    )

    if hasattr(context, 'logger'):
        context.logger.info(
            f"[BROADCAST] Рассылка завершена. "
            f"Отправлено: {sent_count}/{total_users}, Ошибок: {failed_count}"
        )

    await callback.answer()


@router.message(F.text == "🎯 Изменить коэффициент")
async def start_change_odds(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Недостаточно прав.")
        return

    async with get_session()() as session:
        events_result = await session.execute(
            select(Event).where(Event.status == EventStatus.OPEN)
        )
        events = events_result.scalars().all()

    if not events:
        await message.answer("❌ Нет открытых событий для изменения коэффициентов.")
        return

    if len(events) == 1:
        event = events[0]
        if not hasattr(context, "changing_odds"):
            context.changing_odds = {}
        context.changing_odds[message.from_user.id] = {"event_id": event.id, "step": "enter_red_odds"}
        await message.answer(f"Выбрано событие: <b>{event.event_title}</b>\nВведите новый коэффициент для красных 🔴:")
    else:
        if not hasattr(context, "changing_odds"):
            context.changing_odds = {}
        context.changing_odds[message.from_user.id] = {"step": "select_event"}
        keyboard_buttons = [
            [InlineKeyboardButton(text=f"{e.event_title}", callback_data=f"change_odds_event:{e.id}")]
            for e in events
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        await message.answer("Выберите событие для изменения коэффициентов:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("change_odds_event:"))
async def select_event_for_odds(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав.")
        return

    event_id = int(callback.data.split(":")[1])
    context.changing_odds[callback.from_user.id]["event_id"] = event_id
    context.changing_odds[callback.from_user.id]["step"] = "enter_red_odds"

    async with get_session()() as session:
        event = await session.get(Event, event_id)

    await callback.message.edit_text(
        f"Выбрано событие: <b>{event.event_title}</b>\nВведите новый коэффициент для красных 🔴:"
    )
    await callback.answer()


@router.message(F.text, lambda m: hasattr(context, 'changing_odds') and m.from_user.id in context.changing_odds)
async def enter_new_odds(message: Message):
    user_id = message.from_user.id
    step_info = context.changing_odds[user_id]

    async with get_session()() as session:
        event = await session.get(Event, step_info["event_id"])

        try:
            if step_info["step"] == "enter_red_odds":
                red_odds = float(message.text)
                if red_odds <= 0:
                    await message.answer("❌ Коэффициент должен быть больше 0. Попробуйте снова:")
                    return
                step_info["red_odds"] = red_odds
                step_info["step"] = "enter_black_odds"
                await message.answer(f"Введите новый коэффициент для черных ⚫:")
                return

            if step_info["step"] == "enter_black_odds":
                black_odds = float(message.text)
                if black_odds <= 0:
                    await message.answer("❌ Коэффициент должен быть больше 0. Попробуйте снова:")
                    return
                step_info["black_odds"] = black_odds

                event.red_odds = step_info["red_odds"]
                event.black_odds = step_info["black_odds"]
                await session.commit()

                await message.answer(
                    f"✅ Коэффициенты для события <b>{event.event_title}</b> успешно изменены!\n"
                    f"🔴 Красные: x{event.red_odds}\n"
                    f"⚫ Черные: x{event.black_odds}"
                )

                if hasattr(context, "logger"):
                    context.logger.info(
                        f"[ADMIN] Админ {user_id} изменил коэффициенты события {event.id} "
                        f"на красные x{event.red_odds}, черные x{event.black_odds}"
                    )

                del context.changing_odds[user_id]

        except ValueError:
            await message.answer("❌ Пожалуйста, введите корректное число.")
