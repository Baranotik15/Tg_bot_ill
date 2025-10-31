import asyncio
import os
import shutil
from datetime import datetime

from bot.config import Settings


async def hourly_dump(settings: Settings) -> None:
	os.makedirs(settings.dump_dir, exist_ok=True)
	# Only works for SQLite URLs of the form sqlite+aiosqlite:///./path
	db_url = settings.database_url
	if not db_url.startswith("sqlite+aiosqlite:///"):
		# Skip for non-sqlite
		return
	# Extract path after scheme
	path = db_url.replace("sqlite+aiosqlite:///", "")
	while True:
		try:
			if os.path.exists(path):
				ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
				filename = f"db_{ts}.sqlite"
				target = os.path.join(settings.dump_dir, filename)
				shutil.copyfile(path, target)
		except Exception:
			# Silent loop; logging is initialized in main
			pass
		# Sleep 1 hour
		await asyncio.sleep(3600)
