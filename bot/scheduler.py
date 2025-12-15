import asyncio
import os
import shutil
from datetime import datetime

from bot.config import Settings


async def hourly_dump(settings: Settings) -> None:
	os.makedirs(settings.dump_dir, exist_ok=True)
	db_url = settings.database_url
	if not db_url.startswith("sqlite+aiosqlite:///"):
		return
	path = db_url.replace("sqlite+aiosqlite:///", "")
	while True:
		try:
			if os.path.exists(path):
				ts = datetime.utcnow().strftime("%Y_%m_%d_%H_%M_%S")
				filename = f"db_{ts}.sqlite"
				target = os.path.join(settings.dump_dir, filename)
				shutil.copyfile(path, target)
		except Exception:
			pass
		# Sleep 1 day for make dump
		await asyncio.sleep(3600 * 24)
