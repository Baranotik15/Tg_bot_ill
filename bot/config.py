import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class Settings(BaseModel):
	bot_token: str = Field(alias="BOT_TOKEN")
	admin_ids: List[int] = Field(default_factory=list, alias="ADMIN_IDS")
	init_points: int = Field(default=1000, alias="INIT_POINTS")
	database_url: str = Field(default="sqlite+aiosqlite:///./data/bot.db", alias="DATABASE_URL")
	log_level: str = Field(default="INFO", alias="LOG_LEVEL")
	log_dir: str = Field(default="./logs", alias="LOG_DIR")
	dump_dir: str = Field(default="./dumps", alias="DUMP_DIR")

	@classmethod
	def load(cls) -> "Settings":
		load_dotenv()
		raw_admin_ids = os.getenv("ADMIN_IDS", "").strip()
		admin_ids: List[int] = []
		if raw_admin_ids:
			try:
				admin_ids = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip()]
			except ValueError:
				admin_ids = []
		return cls(
			BOT_TOKEN=os.getenv("BOT_TOKEN", ""),
			ADMIN_IDS=admin_ids,
			INIT_POINTS=int(os.getenv("INIT_POINTS", "1000")),
			DATABASE_URL=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/bot.db"),
			LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
			LOG_DIR=os.getenv("LOG_DIR", "./logs"),
			DUMP_DIR=os.getenv("DUMP_DIR", "./dumps"),
		)
