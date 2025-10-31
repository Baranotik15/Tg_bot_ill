from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Iterable


def main_menu() -> ReplyKeyboardMarkup:
	return ReplyKeyboardMarkup(
		keyboard=[
			[
				KeyboardButton(text="🎰 Сделать ставку"),
				KeyboardButton(text="🏆 Рейтинг"),
			],
			[
				KeyboardButton(text="📊 Мой рейтинг"),
				KeyboardButton(text="🎁 Промокод"),
			],
		],
		resize_keyboard=True,
		input_field_placeholder="Выберите действие",
	)


def events_inline(events: Iterable[tuple[int, str]]) -> InlineKeyboardMarkup:
	builder = InlineKeyboardBuilder()
	for event_id, name in events:
		builder.button(text=name, callback_data=f"ev:{event_id}")
	builder.adjust(1)
	return builder.as_markup()


def choices_inline() -> InlineKeyboardMarkup:
	builder = InlineKeyboardBuilder()
	builder.button(text="Красные", callback_data="ch:RED")
	builder.button(text="Чёрные", callback_data="ch:BLACK")
	builder.button(text="Будут минуса", callback_data="ch:MINUS")
	builder.adjust(1)
	return builder.as_markup()


def confirm_inline() -> InlineKeyboardMarkup:
	builder = InlineKeyboardBuilder()
	builder.button(text="Подтвердить", callback_data="bet:confirm")
	builder.button(text="Отменить", callback_data="bet:cancel")
	builder.adjust(2)
	return builder.as_markup()
