import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import Settings
from bot.utils.logger import setup_logging, audit
from bot.db import init_db
from bot.handlers.start import router as start_router
from bot.handlers.leaderboard import router as leaderboard_router
from bot.handlers.promo import router as promo_router
from bot.handlers.admin import router as admin_router
from bot.scheduler import hourly_dump
from bot import context
from bot.handlers.admin_promo import router as admin_promo_router


async def main() -> None:
	settings = Settings.load()
	logger = setup_logging(settings.log_dir, settings.log_level)

	if not settings.bot_token:
		raise RuntimeError("BOT_TOKEN is not set. Put it in .env (see sample.env)")

	# Ensure data folders exist
	os.makedirs("data", exist_ok=True)
	os.makedirs(settings.dump_dir, exist_ok=True)

	# Init DB
	audit(logger, "db_init", {"url": settings.database_url})
	await init_db(settings.database_url)

	# Expose settings via shared context
	context.settings = settings

	# Bot/DP
	bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
	dp = Dispatcher()

	# Routers
	dp.include_router(start_router)
	dp.include_router(leaderboard_router)
	dp.include_router(promo_router)
	dp.include_router(admin_router)
	dp.include_router(admin_promo_router)

	# Hourly dump task
	asyncio.create_task(hourly_dump(settings))

	audit(logger, "bot_start", {})
	await dp.start_polling(bot)


if __name__ == "__main__":
	asyncio.run(main())
