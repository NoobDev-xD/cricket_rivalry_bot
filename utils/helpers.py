def balls_to_overs(balls: int) -> str:
    return f"{balls // 6}.{balls % 6}"

def get_ids(team_str: str) -> list[int]:
    if not team_str:
        return []
    return [int(x) for x in team_str.split(",") if x.strip()]

def add_id(team_str: str, uid: int) -> str:
    ids = get_ids(team_str)
    if uid not in ids:
        ids.append(uid)
    return ",".join(map(str, ids))

def calculate_result(batter: int, bowler: int, free_hit: bool = False) -> dict:
    res = {
        "runs": 0,
        "out": False,
        "no_ball": False,
        "six": False,
        "four": False,
        "msg": "",
        "free_hit_next": False
    }

    if bowler == 0:
        res["no_ball"] = True
        res["runs"] = 1
        res["free_hit_next"] = True
        res["msg"] = "🚫 **NO BALL!** +1 run\nFree Hit next ball!"
        return res

    if batter == bowler:
        if free_hit:
            res["msg"] = "🛡️ **FREE HIT** • DOT • Not Out!"
        else:
            res["out"] = True
            res["msg"] = f"💥 **WICKET!** Batter played {batter}"
    else:
        res["runs"] = batter
        if batter == 6:
            res["six"] = True
            res["msg"] = "🔥 **SIX!** Out of the stadium!"
        elif batter == 4:
            res["four"] = True
            res["msg"] = "🏏 **FOUR!** Found the gap!"
        else:
            res["msg"] = f"+{batter} run{'s' if batter != 1 else ''}"

    return res
