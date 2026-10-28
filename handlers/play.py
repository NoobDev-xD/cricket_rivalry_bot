from telegram import Update
from telegram.ext import ContextTypes
from database.db import Session, get_match, name_of, get_or_create_user
from utils.helpers import calculate_result, balls_to_overs, get_ids
from database.models import User
from sqlalchemy import select

async def private_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bowler sends number in DM"""
    user = update.effective_user
    text = (update.message.text or "").strip()

    if not text.isdigit():
        return
    num = int(text)
    if num < 0 or num > 6:
        await update.message.reply_text("Send **0-6** only\n`0` = No Ball", parse_mode="Markdown")
        return

    async with Session() as s:
        from database.models import Match
        r = await s.execute(
            select(Match).where(
                Match.bowler_id == user.id,
                Match.status == "playing",
                Match.waiting_for == "bowler"
            )
        )
        match = r.scalar_one_or_none()
        if not match:
            await update.message.reply_text("You are not the current bowler.")
            return

        match.pending_bowler_num = num
        match.waiting_for = "batter"
        await s.commit()

        batter_name = await name_of(s, match.striker_id)

    await update.message.reply_text(
        f"⚾ Number **{num}** locked!\n"
        f"Waiting for **{batter_name}** in group...",
        parse_mode="Markdown"
    )


async def group_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Batter sends number in group"""
    user = update.effective_user
    chat = update.effective_chat
    text = (update.message.text or "").strip()

    if not text.isdigit():
        return
    num = int(text)
    if num < 1 or num > 6:
        return

    async with Session() as s:
        match = await get_match(s, chat.id)
        if not match or match.status != "playing":
            return
        if match.waiting_for != "batter" or match.striker_id != user.id:
            return
        if match.pending_bowler_num is None:
            return

        await get_or_create_user(s, user.id, user.username, user.full_name)

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
            r2 = await s.execute(select(User).where(User.id == match.bowler_id))
            bowler = r2.scalar_one_or_none()
            if bowler:
                bowler.total_wickets += 1

        match.free_hit = result["free_hit_next"]
        match.pending_bowler_num = None
        match.waiting_for = "bowler"

        striker_name = await name_of(s, match.striker_id)
        bowler_name = await name_of(s, match.bowler_id)

        balls_limit = match.overs * 6
        curr_balls = match.team_a_balls if match.batting_team == "A" else match.team_b_balls
        curr_wkts = match.team_a_wickets if match.batting_team == "A" else match.team_b_wickets
        curr_runs = match.team_a_runs if match.batting_team == "A" else match.team_b_runs

        msg = f"{result['msg']}\n\n**{striker_name}** played {num}"

        if match.current_innings == 2 and match.target and curr_runs >= match.target:
            match.status = "finished"
            winner = match.batting_team
            await s.commit()
            await update.message.reply_text(
                f"{msg}\n\n🏆 **Team {winner} WON!**\nTarget chased successfully!",
                parse_mode="Markdown"
            )
            return

        if curr_wkts >= match.max_wickets or curr_balls >= balls_limit:
            if match.current_innings == 1:
                match.current_innings = 2
                match.target = curr_runs + 1
                match.batting_team = "B" if match.batting_team == "A" else "A"

                a = get_ids(match.team_a)
                b = get_ids(match.team_b)
                if match.batting_team == "B":
                    match.striker_id = b[0]
                    match.bowler_id = a[0]
                else:
                    match.striker_id = a[0]
                    match.bowler_id = b[0]

                match.waiting_for = "bowler"
                new_striker = await name_of(s, match.striker_id)
                await s.commit()

                await update.message.reply_text(
                    f"{msg}\n\n"
                    f"📊 **Innings Over!**\n"
                    f"🎯 Target: **{match.target}**\n"
                    f"Now batting: Team {match.batting_team}\n"
                    f"Striker: {new_striker}",
                    parse_mode="Markdown"
                )
                return
            else:
                match.status = "finished"
                a_score = match.team_a_runs
                b_score = match.team_b_runs
                if a_score > b_score:
                    winner, margin = "A", a_score - b_score
                elif b_score > a_score:
                    winner, margin = "B", b_score - a_score
                else:
                    winner, margin = None, 0

                await s.commit()
                if winner:
                    result_text = f"🏆 **Team {winner} WON by {margin} runs!**"
                else:
                    result_text = "🤝 **Match Tied!**"
                await update.message.reply_text(f"{msg}\n\n{result_text}", parse_mode="Markdown")
                return

        await s.commit()

        score = curr_runs
        wkts = curr_wkts
        overs = balls_to_overs(curr_balls)

        await update.message.reply_text(
            f"{msg}\n"
            f"Score: **{score}/{wkts}** ({overs})\n\n"
            f"Next → **{bowler_name}** send number in DM",
            parse_mode="Markdown"
              )
