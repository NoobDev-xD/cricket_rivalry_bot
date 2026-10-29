
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import (
    Session,
    get_match,
    get_or_create_user,
    get_leaderboard,
    name_of,
)
from database.models import Match
from utils.helpers import get_ids, add_id, balls_to_overs
from bot.config import DEFAULT_OVERS, DEFAULT_WICKETS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.message:
        return

    async with Session() as s:
        await get_or_create_user(
            s, user.id, user.username, user.full_name
        )

    if update.effective_chat.type == "private":
        text = (
            f"Hey **{user.first_name}**! 🏏\n\n"
            "Welcome to **Cricket Rivalry Bot**\n\n"
            "Add me to a group and use:\n"
            "• `/newgame` → Team Match\n"
            "• `/1v1` → Solo Rivalry\n"
            "• `/lb` → Leaderboard\n\n"
            "**How to play**\n"
            "Bowler → send number (1-6) in my **DM**\n"
            "Batter → send number (1-6) in the **group**"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "Cricket Rivalry is ready!\nUse /newgame or /1v1"
        )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("Only works in groups!")
        return

    async with Session() as s:
        if await get_match(s, chat.id):
            await update.message.reply_text(
                "Match already running. /endgame first."
            )
            return

        await get_or_create_user(
            s, user.id, user.username, user.full_name
        )

        match = Match(
            chat_id=chat.id,
            mode="team",
            host_id=user.id,
            status="lobby",
            team_a=str(user.id),
            team_a_captain=user.id,
            overs=DEFAULT_OVERS,
            max_wickets=DEFAULT_WICKETS,
        )
        s.add(match)
        await s.commit()
        name = user.full_name

    kb = [[
        InlineKeyboardButton("🔵 Join Team A", callback_data="join_a"),
        InlineKeyboardButton("🔴 Join Team B", callback_data="join_b"),
    ]]

    await update.message.reply_text(
        f"🏏 **TEAM MATCH**\nHost: {name}\n\n"
        f"🔵 **Team A**\n1. {name} 👑\n\n"
        f"🔴 **Team B**\nEmpty\n\n"
        "Join now! Host → /startmatch",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


async def one_v_one(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type == "private":
        await update.message.reply_text("1v1 only in groups!")
        return

    async with Session() as s:
        if await get_match(s, chat.id):
            await update.message.reply_text("Match already running.")
            return

        await get_or_create_user(
            s, user.id, user.username, user.full_name
        )

        match = Match(
            chat_id=chat.id,
            mode="1v1",
            host_id=user.id,
            status="lobby",
            team_a=str(user.id),
            team_a_captain=user.id,
            overs=DEFAULT_OVERS,
            max_wickets=DEFAULT_WICKETS,
        )
        s.add(match)
        await s.commit()

    kb = [[
        InlineKeyboardButton(
            "⚔️ Accept Challenge", callback_data="join_b"
        )
    ]]

    await update.message.reply_text(
        f"⚔️ **1v1 RIVALRY**\n"
        f"**{user.full_name}** is waiting!\n\n"
        "Click to challenge.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = update.effective_user
    chat = update.effective_chat
    team = "A" if q.data == "join_a" else "B"

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match or match.status != "lobby":
            await q.answer("Lobby closed.", show_alert=True)
            return

        await get_or_create_user(
            s, user.id, user.username, user.full_name
        )

        a_ids = get_ids(match.team_a)
        b_ids = get_ids(match.team_b)

        if user.id in a_ids or user.id in b_ids:
            await q.answer("Already joined!", show_alert=True)
            return

        if team == "A":
            match.team_a = add_id(match.team_a, user.id)
        else:
            match.team_b = add_id(match.team_b, user.id)

        await s.commit()

        a_ids = get_ids(match.team_a)
        b_ids = get_ids(match.team_b)

        async def names(ids):
            lines = []
            for i, uid in enumerate(ids, 1):
                n = await name_of(s, uid)
                crown = (
                    " 👑"
                    if uid in (
                        match.team_a_captain,
                        match.team_b_captain,
                    )
                    else ""
                )
                lines.append(f"{i}. {n}{crown}")
            return "\n".join(lines) or "Empty"

        text = (
            f"🏏 **LOBBY**\n\n"
            f"🔵 **Team A** ({len(a_ids)})\n"
            f"{await names(a_ids)}\n\n"
            f"🔴 **Team B** ({len(b_ids)})\n"
            f"{await names(b_ids)}\n\n"
            "Host → /startmatch"
        )

    kb = [[
        InlineKeyboardButton("🔵 Join A", callback_data="join_a"),
        InlineKeyboardButton("🔴 Join B", callback_data="join_b"),
    ]]

    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


async def startmatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match:
            await update.message.reply_text("No match.")
            return

        if match.host_id != user.id:
            await update.message.reply_text("Only host can start.")
            return

        a = get_ids(match.team_a)
        b = get_ids(match.team_b)

        if not a or not b:
            await update.message.reply_text("Both teams need players.")
            return

        match.status = "playing"
        match.batting_team = "A"
        match.current_innings = 1
        match.striker_id = a[0]
        match.non_striker_id = a[1] if len(a) > 1 else a[0]
        match.bowler_id = b[0]
        match.waiting_for = "bowler"
        match.pending_bowler_num = None

        striker_id = match.striker_id
        non_striker_id = match.non_striker_id
        bowler_id = match.bowler_id

        striker = await name_of(s, striker_id)
        non_striker = await name_of(s, non_striker_id)
        bowler = await name_of(s, bowler_id)

        await s.commit()

    await update.message.reply_text(
        "🏏 **MATCH STARTED!**\n\n"
        "🔵 Batting: Team A\n"
        "🔴 Bowling: Team B\n\n"
        f"✅ Striker: **{striker}**\n"
        f"✅ Non-striker: **{non_striker}**\n"
        f"🎳 Bowler: **{bowler}**\n\n"
        "📩 Bowler → send 1-6 in bot DM\n"
        "🏏 Batter → send 1-6 in group\n"
        "⏱️ 30-second captain warning / 60-second warning",
        parse_mode="Markdown",
    )

    # Send the first bowling turn to the bowler's private chat.
    try:
        await context.bot.send_message(
            chat_id=bowler_id,
            text=(
                "🎯 YOUR TURN TO BOWL!\n"
                "━━━━━━━━━━━━━━━━\n"
                f"🏏 Batter: {striker}\n"
                "🔢 Send 1-6 (NOT 0!)\n"
                "━━━━━━━━━━━━━━━━\n"
                "🎳 Over: 0.0\n"
                "⏱️ You have 1 minute!"
            ),
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                f"⚠️ {bowler}, open the bot privately and press /start "
                "so you can receive your bowling turn."
            ),
        )

    # Start the 30/60-second timeout checker from handlers/play.py.
    from handlers.play import timeout_check

    asyncio.create_task(
        timeout_check(context, chat.id, bowler_id)
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match:
            await update.message.reply_text("No active match.")
            return

        striker = (
            await name_of(s, match.striker_id)
            if match.striker_id else "-"
        )
        non_striker = (
            await name_of(s, match.non_striker_id)
            if match.non_striker_id else "-"
        )
        bowler = (
            await name_of(s, match.bowler_id)
            if match.bowler_id else "-"
        )

        text = (
            f"📊 **LIVE SCOREBOARD**\n"
            f"{'─' * 24}\n"
            f"🔵 Team A: **{match.team_a_runs}/{match.team_a_wickets}** "
            f"({balls_to_overs(match.team_a_balls)} ov)\n"
            f"🔴 Team B: **{match.team_b_runs}/{match.team_b_wickets}** "
            f"({balls_to_overs(match.team_b_balls)} ov)\n"
            f"{'─' * 24}\n"
            f"Innings: {match.current_innings} | "
            f"Overs limit: {match.overs}\n"
            f"Striker: {striker}\n"
            f"Non-striker: {non_striker}\n"
            f"Bowler: {bowler}"
        )

        if match.target:
            text += f"\n🎯 Target: **{match.target}**"
        if match.free_hit:
            text += "\n🛡️ Free Hit Active"

    await update.message.reply_text(text, parse_mode="Markdown")


async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match:
            await update.message.reply_text("No match.")
            return

        if match.host_id != user.id:
            await update.message.reply_text("Only host.")
            return

        match.status = "finished"
        await s.commit()

    await update.message.reply_text("🏆 Match ended by host.")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with Session() as s:
        users = await get_leaderboard(s, 10)

    if not users:
        await update.message.reply_text("No stats yet.")
        return

    lines = ["🏆 **GLOBAL LEADERBOARD**\n"]

    for i, u in enumerate(users, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        lines.append(
            f"{medal} **{u.full_name}**\n"
            f"    {u.total_runs} runs • "
            f"{u.total_wickets} wickets • {u.wins} wins"
        )

    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown"
    )
