from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from bot import context


def main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """
    Формируем основное меню. Если пользователь админ — добавляем админские кнопки.
    """
    buttons = [
        [KeyboardButton(text="🎰 Сделать ставку"), KeyboardButton(text="🏆 Рейтинг")],
        [KeyboardButton(text="📊 Мой рейтинг"), KeyboardButton(text="🎁 Промокод")],
    ]

    settings = context.settings
    if settings and user_id in settings.admin_ids:
        buttons.append([KeyboardButton(text="💳 Создать промокод")])
        buttons.append([KeyboardButton(text="⚡ Начать событие")])
        buttons.append([KeyboardButton(text="🏁 Завершить событие")])
        buttons.append([KeyboardButton(text="📢 Рассылка всем")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )