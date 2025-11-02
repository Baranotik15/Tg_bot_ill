from typing import Optional
from bot.config import Settings
import logging
import os

settings: Optional[Settings] = None
logger: Optional[logging.Logger] = None
pending_bets = {}


def init_context():
    """Инициализация контекста приложения: настройки и логгер"""
    global settings, logger

    settings = Settings.load()

    os.makedirs(settings.log_dir, exist_ok=True)

    logger = logging.getLogger("bot")
    logger.setLevel(settings.log_level.upper())

    log_path = os.path.join(settings.log_dir, "bot.log")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("✅ Контекст успешно инициализирован")
