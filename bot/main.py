
import logging
import asyncio

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN
from database.db import init_db

from handlers.commands import (
    start,
    newgame,
    one_v_one,
    join_callback,
    startmatch,
    status,
    endgame,
    leaderboard,
)

from handlers.play import private_number, group_number


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


async def post_init(app: Application):
    await init_db()
    logger.info("Database initialized")


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable is missing")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("1v1", one_v_one))
    app.add_handler(CommandHandler("startmatch", startmatch))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("score", status))
    app.add_handler(CommandHandler("endgame", endgame))
    app.add_handler(CommandHandler("lb", leaderboard))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    # Join callback
    app.add_handler(
        CallbackQueryHandler(join_callback, pattern="^join_")
    )

    # Bowler numbers in private chat
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            private_number,
        )
    )

    # Batter numbers in groups
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            group_number,
        )
    )

    logger.info("Cricket Rivalry Bot starting...")

    # Start polling and manage the event loop
    app.run_polling(
        allowed_updates=["message", "callback_query"]
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        if "There is no current event loop" not in str(exc):
            raise

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        main()
        
