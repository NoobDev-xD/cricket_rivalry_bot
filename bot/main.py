
import asyncio
import logging

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


async def post_shutdown(app: Application):
    logger.info("Cricket Rivalry Bot stopped")


async def run_bot():
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN environment variable is missing"
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
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
        CallbackQueryHandler(
            join_callback,
            pattern=r"^join_",
        )
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

    # Manage the complete application lifecycle
    async with app:
        await app.start()

        if app.updater is None:
            raise RuntimeError("Application updater is unavailable")

        await app.updater.start_polling(
            allowed_updates=["message", "callback_query"]
        )

        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
