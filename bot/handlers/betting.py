from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.db import AsyncSessionLocal, Event, EventStatus, Outcome, get_or_create_user, list_open_events, place_bet
from bot.keyboards import events_inline, choices_inline, confirm_inline
from bot import context


router = Router()


class BetStates(StatesGroup):
	ChoosingEvent = State()
	ChoosingChoice = State()
	EnteringAmount = State()
	Confirming = State()


@router.message(Command("bet"))
@router.message(F.text == "🎰 Сделать ставку")
async def start_bet(message: Message, state: FSMContext) -> None:
	events = await list_open_events()
	if not events:
		await message.answer("Нет открытых событий. Попросите админа создать событие: /admin_create_event <название>.")
		return
	await state.clear()
	await state.update_data(ev_ids=[e.id for e in events])
	await message.answer("Выберите событие:", reply_markup=events_inline((e.id, e.name) for e in events))
	await state.set_state(BetStates.ChoosingEvent)


@router.callback_query(F.data.startswith("ev:"), BetStates.ChoosingEvent)
async def choose_event(callback: CallbackQuery, state: FSMContext) -> None:
	_, sid = callback.data.split(":", 1)
	event_id = int(sid)
	await state.update_data(event_id=event_id)
	await callback.message.edit_text("Выберите исход:", reply_markup=choices_inline())
	await state.set_state(BetStates.ChoosingChoice)
	await callback.answer()


@router.callback_query(F.data.startswith("ch:"), BetStates.ChoosingChoice)
async def choose_choice(callback: CallbackQuery, state: FSMContext) -> None:
	_, raw = callback.data.split(":", 1)
	choice = Outcome[raw]
	await state.update_data(choice=choice.value)
	await callback.message.edit_text("Введите количество баллов (целое число):")
	await state.set_state(BetStates.EnteringAmount)
	await callback.answer()


@router.message(BetStates.EnteringAmount)
async def enter_amount(message: Message, state: FSMContext) -> None:
	text = (message.text or "").strip()
	if not text.isdigit() or int(text) <= 0:
		await message.answer("Введите положительное целое число.")
		return
	amount = int(text)
	data = await state.get_data()
	choice = data.get("choice")
	event_id = data.get("event_id")
	if not choice or not event_id:
		await message.answer("Что-то пошло не так. Начните заново: /bet")
		await state.clear()
		return

	await state.update_data(amount=amount)
	await message.answer(
		f"Подтвердите ставку: событие #{event_id}, исход {choice}, сумма {amount}",
		reply_markup=confirm_inline(),
	)
	await state.set_state(BetStates.Confirming)


@router.callback_query(F.data == "bet:cancel", BetStates.Confirming)
async def bet_cancel(callback: CallbackQuery, state: FSMContext) -> None:
	await state.clear()
	await callback.message.edit_text("Ставка отменена.")
	await callback.answer()


@router.callback_query(F.data == "bet:confirm", BetStates.Confirming)
async def bet_confirm(callback: CallbackQuery, state: FSMContext) -> None:
	data = await state.get_data()
	event_id = int(data["event_id"])  # type: ignore[index]
	choice = Outcome[data["choice"]]  # type: ignore[index]
	amount = int(data["amount"])  # type: ignore[index]
	await state.clear()
	try:
		settings = context.settings
		assert settings is not None
		user = await get_or_create_user(callback.from_user.id, callback.from_user.username, settings.init_points)
		bet = await place_bet(user.id, event_id, choice, amount)
		await callback.message.edit_text(
			f"Ставка принята! Событие #{event_id}, исход {choice.value}, сумма {amount}."
		)
	except Exception as e:
		await callback.message.edit_text(f"Не удалось сделать ставку: {e}")
	await callback.answer()
