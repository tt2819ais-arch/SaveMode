"""SaveMOD — конфигурация."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
DB_PATH: str = os.getenv("DB_PATH", "savemod.db")
