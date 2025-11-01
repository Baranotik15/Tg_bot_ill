from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from bot import context
from bot.db import get_session, User, Bet, Event
from sqlalchemy import select


router = Router()

if not hasattr(context, "pending_bets"):
    context.pending_bets = {}


@router.callback_query(F.data.startswith("bet_"))
async def select_team(callback: CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data
    team_key, event_id = data.split(":")
    event_id = int(event_id)

    team_names = {
        "bet_red": "Красных",
        "bet_black": "Черных"
    }
    team_name = team_names.get(team_key, team_key)

    context.pending_bets[user_id] = {
        "event_id": event_id,
        "team_key": team_key,
        "team_name": team_name
    }

    await callback.message.answer(
        f"Вы выбрали команду: {team_name}\nТеперь введите сумму баллов для ставки:"
    )


@router.message(F.text.regexp(r"^\d+$"))
async def enter_bet_amount(message: Message):
    user_id = message.from_user.id
    if user_id not in context.pending_bets:
        return

    amount = int(message.text)
    pending = context.pending_bets[user_id]

    async with get_session()() as session:
        user = await session.get(User, user_id)
        if not user or user.balance < amount:
            await message.answer("У вас недостаточно баллов для ставки.")
            return

        user.balance -= amount

        event = await session.get(Event, pending["event_id"])

        bet = Bet(
            user_id=user_id,
            event_id=event.id,
            team=pending["team_key"],
            amount=amount
        )
        session.add(bet)
        await session.commit()
        await session.refresh(event)

    red_coef = black_coef = 1.0
    try:
        desc = event.description
        parts = desc.replace("Красные: X", "").replace("Черные: X", "").split(" / ")
        red_coef = float(parts[0])
        black_coef = float(parts[1])
    except Exception:
        pass

    coef = red_coef if pending["team_key"] == "bet_red" else black_coef
    expected_win = amount * coef

    await message.answer(
        f"✅ Ваша ставка сделана!\n"
        f"Команда: {pending['team_name']}\n"
        f"Сумма: {amount} баллов\n"
        f"Ожидаемый выигрыш: {expected_win:.2f} баллов"
    )

    del context.pending_bets[user_id]
