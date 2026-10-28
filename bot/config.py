import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("8242418418:AAFHsuGnQNUhyTbk6hCB7j7J38Zy-M6zvrk")
ADMIN_IDS = [int(x) for x in os.getenv("8755208183", "").split(",") if x.strip()]

MAX_OVERS = 25
DEFAULT_OVERS = 5
DEFAULT_WICKETS = 5
