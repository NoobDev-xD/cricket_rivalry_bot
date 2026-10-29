
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from database.db import Session, get_match, name_of, get_or_create_user
from database.models import User
from utils.helpers import calculate_result, balls_to_overs, get_ids

TIMEOUT_SECONDS = 60
WARNING_SECONDS = 30


async def notify_bowler(context, chat_id, bowler_id, striker_name, overs_text):
    try:
        await context.bot.send_message(
            chat_id=bowler_id,
            text=(
                "🎯 YOUR TURN TO BOWL!\n"
                "━━━━━━━━━━━━━━━━\n"
                f"🏏 Batter: {striker_name}\n"
                "🔢 Send 1-6 (NOT 0!)\n"
                "━━━━━━━━━━━━━━━━\n"
                f"🎳 Over: {overs_text}\n"
                "⏱ You have 1 minute!"
            ),
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ Bowler DM failed. Ask the bowler to open "
                "the bot privately and press /start."
            ),
        )


async def timeout_check(context, chat_id, bowler_id):
    """Warn the captain at 30 seconds and the group at 60 seconds."""

    await asyncio.sleep(WARNING_SECONDS)

    async with Session() as s:
        match = await get_match(s, chat_id)

        if (
            not match
            or match.status != "playing"
            or match.waiting_for != "bowler"
            or match.bowler_id != bowler_id
        ):
            return

        team_a = get_ids(match.team_a)
        team_b = get_ids(match.team_b)

        # Confirm these field names exist in your Match model.
        captain_id = None
        if bowler_id in team_a:
            captain_id = getattr(match, "team_a_captain", None)
        elif bowler_id in team_b:
            captain_id = getattr(match, "team_b_captain", None)

    if captain_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"⚠️ <a href='tg://user?id={captain_id}'>Captain</a>, "
                "your bowler has not responded for 30 seconds!\n"
                f"🏏 Bowler: <a href='tg://user?id={bowler_id}'>Player</a>\n"
                "⏳ Please remind them to send their number."
            ),
            parse_mode="HTML",
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ Bowler has not responded for 30 seconds!\n"
                "Captain, please remind your bowler."
            ),
        )

    await asyncio.sleep(TIMEOUT_SECONDS - WARNING_SECONDS)

    async with Session() as s:
        match = await get_match(s, chat_id)

        if (
            not match
            or match.status != "playing"
            or match.waiting_for != "bowler"
            or match.bowler_id != bowler_id
        ):
            return

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"⏰ <a href='tg://user?id={bowler_id}'>Bowler</a> "
            "has not responded within 1 minute!"
        ),
        parse_mode="HTML",
    )


async def private_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bowler submits a number in private chat."""
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        return

    num = int(text)
    if not 1 <= num <= 6:
        await message.reply_text("Send a number from 1 to 6 only. 0 is not allowed.")
        return

    async with Session() as s:
        from database.models import Match

        result = await s.execute(
            select(Match).where(
                Match.bowler_id == user.id,
                Match.status == "playing",
                Match.waiting_for == "bowler",
            )
        )
        match = result.scalar_one_or_none()

        if not match:
            await message.reply_text("You are not the current bowler.")
            return

        match.pending_bowler_num = num
        match.waiting_for = "batter"

        chat_id = match.chat_id
        striker_name = await name_of(s, match.striker_id)
        await s.commit()

    await message.reply_text(
        f"✅ Number {num} locked!\nWaiting for {striker_name} in the group."
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "✅ Bowler sent!\n"
            f"🏏 {user.full_name} sent their number.\n"
            f"👉 Batter {striker_name}, type 1-6 in the group!"
        ),
    )


async def group_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Batter submits a number in the group."""
    user = update.effective_user
    chat = update.effective_chat
    message = update.effective_message

    if not user or not chat or not message:
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        return

    num = int(text)
    if not 1 <= num <= 6:
        return

    async with Session() as s:
        match = await get_match(s, chat.id)

        if not match or match.status != "playing":
            return
        if match.waiting_for != "batter" or match.striker_id != user.id:
            return
        if match.pending_bowler_num is None:
            return

        await get_or_create_user(
            s, user.id, user.username, user.full_name
        )

        bowler_num = match.pending_bowler_num
        result = calculate_result(num, bowler_num, match.free_hit)

        if match.batting_team == "A":
            match.team_a_runs += result["runs"]
            match.team_a_balls += 1
            if result["out"]:
                match.team_a_wickets += 1
        else:
            match.team_b_runs += result["runs"]
            match.team_b_balls += 1
            if result["out"]:
                match.team_b_wickets += 1

        r = await s.execute(select(User).where(User.id == user.id))
        batter = r.scalar_one_or_none()
        if batter:
            batter.total_runs += result["runs"]
            batter.total_balls += 1

        if result["out"]:
            r = await s.execute(
                select(User).where(User.id == match.bowler_id)
            )
            bowler = r.scalar_one_or_none()
            if bowler:
                bowler.total_wickets += 1

        match.free_hit = result["free_hit_next"]
        match.pending_bowler_num = None
        match.waiting_for = "bowler"

        striker_id = match.striker_id
        non_striker_id = match.non_striker_id
        bowler_id = match.bowler_id

        striker_name = await name_of(s, striker_id)
        non_striker_name = await name_of(s, non_striker_id)
        bowler_name = await name_of(s, bowler_id)

        balls_limit = match.overs * 6
        curr_balls = (
            match.team_a_balls
            if match.batting_team == "A"
            else match.team_b_balls
        )
        curr_wkts = (
            match.team_a_wickets
            if match.batting_team == "A"
            else match.team_b_wickets
        )
        curr_runs = (
            match.team_a_runs
            if match.batting_team == "A"
            else match.team_b_runs
        )

        msg = (
            f"{result['msg']}\n\n"
            f"🏏 Striker: {striker_name} played {num}\n"
            f"👤 Non-striker: {non_striker_name}"
        )

        # Target reached in the second innings
        if (
            match.current_innings == 2
            and match.target
            and curr_runs >= match.target
        ):
            match.status = "finished"
            winner = match.batting_team
            await s.commit()
            await message.reply_text(
                f"{msg}\n\n🏆 Team {winner} WON!\nTarget chased successfully!"
            )
            return

        # End of innings
        if curr_wkts >= match.max_wickets or curr_balls >= balls_limit:
            if match.current_innings == 1:
                match.current_innings = 2
                match.target = curr_runs + 1
                match.batting_team = (
                    "B" if match.batting_team == "A" else "A"
                )

                a = get_ids(match.team_a)
                b = get_ids(match.team_b)

                if not a or not b:
                    await s.commit()
                    await message.reply_text(
                        f"{msg}\n\n⚠️ Could not determine both teams' players."
                    )
                    return

                if match.batting_team == "B":
                    match.striker_id = b[0]
                    match.non_striker_id = b[1] if len(b) > 1 else b[0]
                    match.bowler_id = a[0]
                else:
                    match.striker_id = a[0]
                    match.non_striker_id = a[1] if len(a) > 1 else a[0]
                    match.bowler_id = b[0]

                match.waiting_for = "bowler"

                new_striker_id = match.striker_id
                new_bowler_id = match.bowler_id
                new_striker = await name_of(s, new_striker_id)
                new_non_striker = await name_of(s, match.non_striker_id)
                new_bowler_name = await name_of(s, new_bowler_id)
                target = match.target
                batting_team = match.batting_team
                overs_text = balls_to_overs(0)

                await s.commit()

                await message.reply_text(
                    f"{msg}\n\n📊 Innings Over!\n"
                    f"🎯 Target: {target}\n"
                    f"Now batting: Team {batting_team}\n"
                    f"✅ Striker: {new_striker}\n"
                    f"✅ Non-striker: {new_non_striker}\n"
                    f"🎳 Bowler: {new_bowler_name}"
                )

                await notify_bowler(
                    context, chat.id, new_bowler_id,
                    new_striker, overs_text
                )
                asyncio.create_task(
                    timeout_check(context, chat.id, new_bowler_id)
                )
                return

            match.status = "finished"

            if match.team_a_runs > match.team_b_runs:
                result_text = (
                    f"🏆 Team A WON by "
                    f"{match.team_a_runs - match.team_b_runs} runs!"
                )
            elif match.team_b_runs > match.team_a_runs:
                result_text = (
                    f"🏆 Team B WON by "
                    f"{match.team_b_runs - match.team_a_runs} runs!"
                )
            else:
                result_text = "🤝 Match Tied!"

            await s.commit()
            await message.reply_text(f"{msg}\n\n{result_text}")
            return

        overs_text = balls_to_overs(curr_balls)
        await s.commit()

    await message.reply_text(
        f"{msg}\n"
        f"📊 Score: {curr_runs}/{curr_wkts} ({overs_text})\n\n"
        f"🎳 Next bowler: {bowler_name}\n"
        f"✅ Striker: {striker_name}\n"
        f"✅ Non-striker: {non_striker_name}"
    )

    await notify_bowler(
        context, chat.id, bowler_id, striker_name, overs_text
    )
    asyncio.create_task(
        timeout_check(context, chat.id, bowler_id)
    )
    
