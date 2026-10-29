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
    captain,
    captain_callback,
)

from handlers.play import private_number, group_number


# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# Initialize database
async def post_init(app):
    await init_db()
    logger.info("Database initialized successfully")


# Main bot function
async def run_bot():
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN environment variable is missing"
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # =========================
    # BOT COMMANDS
    # =========================

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("newgame", newgame)
    )

    app.add_handler(
        CommandHandler("1v1", one_v_one)
    )

    app.add_handler(
        CommandHandler("startmatch", startmatch)
    )

    app.add_handler(
        CommandHandler("status", status)
    )

    app.add_handler(
        CommandHandler("score", status)
    )

    app.add_handler(
        CommandHandler("endgame", endgame)
    )

    app.add_handler(
        CommandHandler("lb", leaderboard)
    )

    app.add_handler(
        CommandHandler("leaderboard", leaderboard)
    )

    # =========================
    # CAPTAIN FEATURE
    # =========================

    app.add_handler(
        CommandHandler("captain", captain)
    )

    # Captain selection buttons
    app.add_handler(
        CallbackQueryHandler(
            captain_callback,
            pattern=r"^captain_\d+$",
        )
    )

    # =========================
    # GAME JOIN BUTTONS
    # =========================

    app.add_handler(
        CallbackQueryHandler(
            join_callback,
            pattern=r"^join_",
        )
    )

    # =========================
    # PRIVATE CHAT NUMBERS
    # =========================

    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.TEXT
            & ~filters.COMMAND,
            private_number,
        )
    )

    # =========================
    # GROUP CHAT NUMBERS
    # =========================

    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & filters.TEXT
            & ~filters.COMMAND,
            group_number,
        )
    )

    # =========================
    # START BOT
    # =========================

    logger.info("Starting Cricket Rivalry Bot...")

    await app.initialize()

    try:
        await app.start()

        if app.updater is None:
            raise RuntimeError(
                "Application updater is unavailable"
            )

        await app.updater.start_polling(
            allowed_updates=[
                "message",
                "callback_query",
            ]
        )

        logger.info(
            "Cricket Rivalry Bot started successfully"
        )

        # Keep bot running
        await asyncio.Event().wait()

    finally:
        if (
            app.updater is not None
            and app.updater.running
        ):
            await app.updater.stop()

        if app.running:
            await app.stop()

        await app.shutdown()


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    try:
        asyncio.set_event_loop_policy(
            asyncio.DefaultEventLoopPolicy()
        )

        asyncio.run(run_bot())

    except KeyboardInterrupt:
        logger.info(
            "Cricket Rivalry Bot stopped"
        )
