import logging
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Dict


def setup_logging(log_dir: str, level: str = "INFO") -> logging.Logger:
	os.makedirs(log_dir, exist_ok=True)
	log_path = os.path.join(log_dir, "bot.log")
	logger = logging.getLogger("bot")
	logger.setLevel(getattr(logging, level.upper(), logging.INFO))

	# Console handler
	console_handler = logging.StreamHandler()
	console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
	logger.addHandler(console_handler)

	# File handler (rotates daily, keep 7 backups)
	file_handler = TimedRotatingFileHandler(log_path, when="D", interval=1, backupCount=7, encoding="utf-8")
	file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
	logger.addHandler(file_handler)

	return logger


def audit(logger: logging.Logger, action: str, payload: Dict[str, Any] | None = None) -> None:
	if payload is None:
		payload = {}
	logger.info("AUDIT %s %s", action, payload)
