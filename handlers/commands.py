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
            "• `/captain` → Select Team A Captain\n"
            "• `/status` → Live Score\n"
            "• `/lb` → Leaderboard\n\n"
            "**How to play**\n"
            "Bowler → send number (1-6) in my DM\n"
            "Batter → send number (1-6) in the group"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "🏏 Cricket Rivalry is ready!\n"
            "Use /newgame or /1v1"
        )


async def newgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not update.message:
        return

    if chat.type == "private":
        await update.message.reply_text("Only works in groups!")
        return

    async with Session() as s:
        if await get_match(s, chat.id):
            await update.message.reply_text(
                "Match already running. Use /endgame first."
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

    keyboard = [[
        InlineKeyboardButton(
            "🔵 Join Team A", callback_data="join_a"
        ),
        InlineKeyboardButton(
            "🔴 Join Team B", callback_data="join_b"
        ),
    ]]

    await update.message.reply_text(
        f"🏏 **TEAM MATCH**\n"
        f"Host: {name}\n\n"
        f"🔵 **Team A**\n1. {name} 👑\n\n"
        f"🔴 **Team B**\nEmpty\n\n"
        "Players join using the buttons.\n"
        "Host: /captain → /startmatch",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def one_v_one(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not update.message:
        return

    if chat.type == "private":
        await update.message.reply_text("1v1 only works in groups!")
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

    keyboard = [[
        InlineKeyboardButton(
            "⚔️ Accept Challenge", callback_data="join_b"
        )
    ]]

    await update.message.reply_text(
        f"⚔️ **1v1 RIVALRY**\n"
        f"**{user.full_name}** is waiting!\n\n"
        "Click below to challenge.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def join_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat

    if not query or not user or not chat:
        return

    team = "A" if query.data == "join_a" else "B"

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match or match.status != "lobby":
            await query.answer("Lobby closed.", show_alert=True)
            return

        await get_or_create_user(
            s, user.id, user.username, user.full_name
        )

        team_a = get_ids(match.team_a)
        team_b = get_ids(match.team_b)

        if user.id in team_a or user.id in team_b:
            await query.answer("Already joined!", show_alert=True)
            return

        if team == "A":
            match.team_a = add_id(match.team_a, user.id)
        else:
            match.team_b = add_id(match.team_b, user.id)

            # First Team B player becomes the default captain.
            if not match.team_b_captain:
                match.team_b_captain = user.id

        await s.commit()

        team_a = get_ids(match.team_a)
        team_b = get_ids(match.team_b)

        async def format_players(player_ids):
            lines = []

            for number, player_id in enumerate(player_ids, 1):
                player_name = await name_of(s, player_id)

                is_captain = player_id in (
                    match.team_a_captain,
                    match.team_b_captain,
                )

                crown = " 👑" if is_captain else ""
                lines.append(
                    f"{number}. {player_name}{crown}"
                )

            return "\n".join(lines) or "Empty"

        lobby_text = (
            f"🏏 **MATCH LOBBY**\n\n"
            f"🔵 **Team A ({len(team_a)})**\n"
            f"{await format_players(team_a)}\n\n"
            f"🔴 **Team B ({len(team_b)})**\n"
            f"{await format_players(team_b)}\n\n"
            "Host: /captain → /startmatch"
        )

    await query.answer("Joined successfully!")

    keyboard = [[
        InlineKeyboardButton("🔵 Join A", callback_data="join_a"),
        InlineKeyboardButton("🔴 Join B", callback_data="join_b"),
    ]]

    await query.edit_message_text(
        lobby_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# HOST COMMAND: CHOOSE TEAM A CAPTAIN
async def captain(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not update.message:
        return

    if chat.type == "private":
        await update.message.reply_text(
            "Use /captain in your match group."
        )
        return

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match or match.status != "lobby":
            await update.message.reply_text(
                "❌ No active lobby. Use /newgame first."
            )
            return

        if match.host_id != user.id:
            await update.message.reply_text(
                "❌ Only the host can select Team A's captain."
            )
            return

        player_ids = get_ids(match.team_a)

        if not player_ids:
            await update.message.reply_text(
                "Team A has no players."
            )
            return

        keyboard = []

        for player_id in player_ids:
            player_name = await name_of(s, player_id)

            label = (
                f"👑 {player_name} (Current)"
                if player_id == match.team_a_captain
                else f"👤 {player_name}"
            )

            keyboard.append([
                InlineKeyboardButton(
                    label,
                    callback_data=f"captain_{player_id}",
                )
            ])

    await update.message.reply_text(
        "👑 **SELECT TEAM A CAPTAIN**\n\n"
        "Choose a player from Team A:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# HANDLE CAPTAIN SELECTION
async def captain_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if not query or not query.data:
        return

    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        await query.answer("User unavailable.", show_alert=True)
        return

    try:
        captain_id = int(query.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await query.answer("Invalid selection.", show_alert=True)
        return

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match or match.status != "lobby":
            await query.answer(
                "Lobby closed or match already started.",
                show_alert=True,
            )
            return

        if match.host_id != user.id:
            await query.answer(
                "Only the host can select the captain.",
                show_alert=True,
            )
            return

        if captain_id not in get_ids(match.team_a):
            await query.answer(
                "That player is not in Team A.",
                show_alert=True,
            )
            return

        match.team_a_captain = captain_id
        captain_name = await name_of(s, captain_id)
        await s.commit()

    await query.answer("Captain selected!")

    await query.edit_message_text(
        f"👑 **TEAM A CAPTAIN SELECTED**\n\n"
        f"Captain: **{captain_name}**\n\n"
        "You can now use /startmatch.",
        parse_mode="Markdown",
    )


async def startmatch(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not update.message:
        return

    if chat.type == "private":
        await update.message.reply_text(
            "Use /startmatch in the match group."
        )
        return

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match:
            await update.message.reply_text("No match.")
            return

        if match.host_id != user.id:
            await update.message.reply_text(
                "Only the host can start the match."
            )
            return

        if match.status != "lobby":
            await update.message.reply_text(
                "This match has already started."
            )
            return

        team_a = get_ids(match.team_a)
        team_b = get_ids(match.team_b)

        if not team_a or not team_b:
            await update.message.reply_text(
                "Both teams need players."
            )
            return

        match.status = "playing"
        match.batting_team = "A"
        match.current_innings = 1

        match.striker_id = team_a[0]
        match.non_striker_id = (
            team_a[1] if len(team_a) > 1 else team_a[0]
        )
        match.bowler_id = team_b[0]
        match.waiting_for = "bowler"
        match.pending_bowler_num = None

        striker_id = match.striker_id
        non_striker_id = match.non_striker_id
        bowler_id = match.bowler_id

        striker_name = await name_of(s, striker_id)
        non_striker_name = await name_of(s, non_striker_id)
        bowler_name = await name_of(s, bowler_id)

        await s.commit()

    await update.message.reply_text(
        "🏏 **MATCH STARTED!**\n\n"
        "🔵 Batting: Team A\n"
        "🔴 Bowling: Team B\n\n"
        f"👑 Team A Captain ID: {match.team_a_captain}\n"
        f"👑 Team B Captain ID: {match.team_b_captain}\n\n"
        f"✅ Striker: **{striker_name}**\n"
        f"✅ Non-striker: **{non_striker_name}**\n"
        f"🎳 Bowler: **{bowler_name}**\n\n"
        "📩 Bowler → send 1-6 in bot DM\n"
        "🏏 Batter → send 1-6 in group\n"
        "⏱️ Captain warning: 30 seconds; reminder: 60 seconds",
        parse_mode="Markdown",
    )

    try:
        await context.bot.send_message(
            chat_id=bowler_id,
            text=(
                "🎯 YOUR TURN TO BOWL!\n"
                "━━━━━━━━━━━━━━━━\n"
                f"🏏 Batter: {striker_name}\n"
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
                f"⚠️ {bowler_name}, open the bot privately and "
                "press /start so you can receive your bowling turn."
            ),
        )

    from handlers.play import timeout_check

    asyncio.create_task(
        timeout_check(context, chat.id, bowler_id)
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat

    if not chat or not update.message:
        return

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

        score_text = (
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
            score_text += f"\n🎯 Target: **{match.target}**"

        if match.free_hit:
            score_text += "\n🛡️ Free Hit Active"

    await update.message.reply_text(
        score_text,
        parse_mode="Markdown",
    )


async def endgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user or not update.message:
        return

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match:
            await update.message.reply_text("No match.")
            return

        if match.host_id != user.id:
            await update.message.reply_text(
                "Only the host can end the match."
            )
            return

        match.status = "finished"
        await s.commit()

    await update.message.reply_text("🏆 Match ended by host.")


async def leaderboard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    async with Session() as s:
        users = await get_leaderboard(s, 10)

    if not users:
        await update.message.reply_text("No stats yet.")
        return

    lines = ["🏆 **GLOBAL LEADERBOARD**\n"]

    for number, player in enumerate(users, 1):
        medal = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }.get(number, f"{number}.")

        lines.append(
            f"{medal} **{player.full_name}**\n"
            f"    {player.total_runs} runs • "
            f"{player.total_wickets} wickets • "
            f"{player.wins} wins"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )
    
