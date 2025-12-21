import asyncio
import dotenv
import os
from db import init_db


dotenv.load_dotenv()

asyncio.run(init_db(os.getenv("DATABASE_URL")))
