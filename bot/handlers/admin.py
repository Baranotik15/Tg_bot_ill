from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import Outcome, create_event, close_event, resolve_event
from bot import context


router = Router()


def is_admin(message: Message) -> bool:
	settings = context.settings
	return bool(settings and message.from_user.id in settings.admin_ids)


@router.message(Command("admin_create_event"))
async def admin_create(message: Message) -> None:
	if not is_admin(message):
		await message.answer("Недостаточно прав.")
		return
	parts = (message.text or "").split(maxsplit=1)
	name = parts[1].strip() if len(parts) > 1 else "Событие"
	event = await create_event(name=name)
	await message.answer(f"Создано событие #{event.id}: {event.name}")


@router.message(Command("admin_close_event"))
async def admin_close(message: Message) -> None:
	if not is_admin(message):
		await message.answer("Недостаточно прав.")
		return
	parts = (message.text or "").split(maxsplit=1)
	if len(parts) < 2 or not parts[1].isdigit():
		await message.answer("Использование: /admin_close_event <event_id>")
		return
	event_id = int(parts[1])
	event = await close_event(event_id)
	await message.answer(f"Событие #{event.id} закрыто для ставок.")


@router.message(Command("admin_resolve_event"))
async def admin_resolve(message: Message) -> None:
	if not is_admin(message):
		await message.answer("Недостаточно прав.")
		return
	parts = (message.text or "").split()
	if len(parts) < 3:
		await message.answer("Использование: /admin_resolve_event <event_id> <RED|BLACK|MINUS>")
		return
	try:
		event_id = int(parts[1])
		outcome = Outcome[parts[2].upper()]
	except Exception:
		await message.answer("Неверные параметры.")
		return
	event, winners, losers = await resolve_event(event_id, outcome)
	await message.answer(f"Событие #{event.id} успешно рассчитано. Победителей: {winners}, проигравших: {losers}.")
