"""
SWISH model — Python port of the projection + pricing logic in index.html.

The website computes picks in the browser; this file computes the SAME numbers inside the
GitHub automation so picks can be frozen before tip-off and graded the next morning.
Keep it in step with index.html (MODEL_VERSION is stored on every pick).  `scripts/test_model_parity.py`
checks both give identical results on the same data.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone

MODEL_VERSION = "v1.5 (2026-10-30)"

MARKETS = ["PTS", "REB", "AST", "3PM", "PRA"]
CV = {"PTS": .27, "REB": .33, "AST": .38, "3PM": .62, "PRA": .22}
SD_FLOOR = {"PTS": 3, "REB": 1.6, "AST": 1.2, "3PM": 0.9, "PRA": 4}
MIN_EDGE = 0.06
H2H_MAX_WEIGHT = 0.25
H2H_K = 4
MIN_MINUTES_FOR_PROPS = 14
PROJ_ERR = 0.12
BIG_GAP_SD = 0.9
BIG_GAP_REL = 0.4
MODEL_WEIGHT = 0.3
STALE_AFTER_MIN = 14 * 60
COUNT_MARKETS = {"REB", "AST", "3PM", "STL", "BLK", "TOV"}
ROLE_CHANGE_MIN = 5        # minutes: this season's role vs last season counts as a role change
MAX_MIN = 40               # nobody is projected above this many minutes
SHIFT_MIN_OUT = 10         # a teammate out must be a 10+ minute player to trigger a minutes shift
TEAM_MIN = 240             # minutes in a regulation game
MAX_GAIN = 6               # no single player picks up more than 6 extra minutes
SHIFT_ROOM = 36            # spare minutes are shared by how far each player is below this
SHIFT_MIN_RECV = 8         # only rotation players (8+ expected minutes) pick them up
FRESH_GAMES = 1            # an absence is "new" if the player played in his team's last game (2-3 tested worse)
KEY_MIN = 25               # a newly-out player with 25+ expected minutes makes his team's minutes "unclear" until lineups are confirmed
STARTER_PULL = 1 / 3       # v1.5: move a third of the way to that target (lab: full move overshot by ~2.6 min)
STARTER_SHARE = 0.9        # a bench player listed to start tonight: at least 90% of the other starters' average minutes
ROLE_NEW_GAMES = 3         # a role change with fewer games than this this season → flagged (not "strong")


# ----------------------------------------------------------------------------- small helpers (match the JS)
def js_round(x: float) -> int:
    return math.floor(x + 0.5)


def avg(a):
    return sum(a) / len(a)


def stdev(a):
    if len(a) < 2:
        return 0.0
    m = avg(a)
    return math.sqrt(sum((v - m) ** 2 for v in a) / (len(a) - 1))


def norm_cdf(x: float) -> float:
    # same Abramowitz–Stegun approximation as the website, so numbers match exactly
    t = 1 / (1 + 0.3275911 * abs(x) / math.sqrt(2))
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * math.exp(-(x * x) / 2)
    return (1 + y) / 2 if x >= 0 else (1 - y) / 2


def american_to_prob(am: float) -> float:
    return -am / (-am + 100) if am < 0 else 100 / (am + 100)


def american_to_decimal(am: float) -> float:
    return 1 + am / 100 if am > 0 else 1 + 100 / -am


def prob_to_american_raw(p: float) -> float:
    return -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p


def norm_name(n: str) -> str:
    n = unicodedata.normalize("NFKD", n or "")
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n)
    return re.sub(r"[^a-z]", "", n)


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def rate(games, m):
    """per-minute rate over a set of games (None if no minutes)"""
    mins = sum(g.get("min") or 0 for g in games)
    return sum(g[m] for g in games) / mins if mins > 0 else None


def minutes_model(cur, last):
    """expected minutes tonight + this season's minutes vs last season's (role change)"""
    r10 = (cur + last)[:10]
    base_min = avg([g.get("min") or 0 for g in r10])
    last_min = avg([g.get("min") or 0 for g in last[:20]]) if last else None
    if not cur:
        return base_min, None, last_min, 0.0
    cur_min = 0.5 * avg([g.get("min") or 0 for g in cur[:3]]) + 0.5 * avg([g.get("min") or 0 for g in cur[:10]])
    w = min(1, len(cur) / 5)
    prior = avg([g.get("min") or 0 for g in last[:10]]) if last else cur_min
    exp_min = w * cur_min + (1 - w) * prior
    delta = cur_min - last_min if last_min is not None else 0.0
    return exp_min, cur_min, last_min, delta


def pos_group(pos):
    u = (pos or "").upper()
    return "C" if u.startswith("C") else "G" if "G" in u else "F" if "F" in u else u


def minute_shifts(live: dict, status_of) -> dict:
    """Minutes shifts (v1.5, tested in the projection lab on 2024-25 and 2025-26):
    1) Teammates ruled OUT: only when the available players can't fill a 240-minute game on their own minutes, the gap
       goes to rotation players by room below 36 min, double weight for the absent players' positions, +6 max, cap 40.
       (v1.3's "freed share of 240" for new absences made minutes worse over two seasons, so it was removed.)
    2) Starting tonight: a player outside his team's usual top-5 minutes whom NBA.com lists as a starter moves a THIRD
       of the way (STARTER_PULL) towards 90% of the other starters' average minutes. (The full move overshot by ~2.6 min.)"""
    teams = {t for g in live.get("games", []) for t in (g["away"], g["home"])}
    by_team = {}
    for p in live.get("players", []):
        if p.get("team") not in teams:
            continue
        played = lambda arr: [x for x in (arr or []) if (x.get("min") or 0) > 0]
        cur, last = played(p.get("season")), played(p.get("lastSeason"))
        if not cur and not last:
            continue
        by_team.setdefault(p["team"], []).append({"name": p["name"], "grp": pos_group(p.get("pos")), "exp": minutes_model(cur, last)[0],
                                                  "cur": len(cur), "dates": {x.get("d") for x in cur}, "status": status_of(p["name"])})
    out = {}
    for rows in by_team.values():
        outs = [r for r in rows if r["status"] == "Out" and r["exp"] >= SHIFT_MIN_OUT]
        avail = [r for r in rows if r["status"] not in ("Out", "Doubtful") and r["cur"] > 0]
        if not outs:
            continue
        short = TEAM_MIN - sum(r["exp"] for r in avail)      # v1.5: back to the v1.2 rule (lab: the "freed share" made minutes worse)
        if short <= 0:
            continue
        grps = {o["grp"] for o in outs}
        recv = [r for r in avail if r["exp"] >= SHIFT_MIN_RECV]
        wts = [max(0.0, SHIFT_ROOM - r["exp"]) * (2 if r["grp"] in grps else 1) for r in recv]   # bench/role players have more room than stars
        tot = sum(wts)
        if tot <= 0:
            continue
        names = [o["name"] for o in sorted(outs, key=lambda o: -o["exp"])]
        for r, wt in zip(recv, wts):
            g = min(MAX_MIN, r["exp"] + min(MAX_GAIN, short * wt / tot)) - r["exp"]
            if g > 0.05:
                out[r["name"]] = {"gain": g, "from": names}
    # ---- starting tonight (NBA.com expected/confirmed starters): a player outside his team's usual top-5 minutes who
    # is listed to start gets close to the other starters' minutes. Names compared without accents (Matković/Matkovic).
    starters = set()
    for lu in (live.get("lineups") or {}).values():
        for side in ("away", "home"):
            for s_ in ((lu or {}).get(side) or {}).get("starters") or []:
                starters.add(norm_name(s_.get("name")))
    if starters:
        for rows in by_team.values():
            avail = [r for r in rows if r["status"] not in ("Out", "Doubtful") and r["cur"] > 0]
            exp = {r["name"]: r["exp"] + out.get(r["name"], {}).get("gain", 0) for r in avail}
            st = [r for r in avail if norm_name(r["name"]) in starters]
            if len(st) < 5:
                continue
            top5 = {r["name"] for r in sorted(avail, key=lambda r: -exp[r["name"]])[:5]}
            others = [exp[r["name"]] for r in st if r["name"] in top5]
            if not others:
                continue
            target = min(MAX_MIN, STARTER_SHARE * sum(others) / len(others))
            for r in st:
                if r["name"] not in top5 and target > exp[r["name"]]:
                    prev = out.get(r["name"], {"gain": 0, "from": []})
                    out[r["name"]] = {"gain": prev["gain"] + STARTER_PULL * (target - exp[r["name"]]), "from": prev["from"], "starter": True}
    return out


def key_absences(live: dict, status_of) -> dict:
    """team → names of players with KEY_MIN+ expected minutes who are newly OUT (played in the team's last game),
    while that team's starting lineup is not yet confirmed. Their teammates' minutes are an estimate, so their props
    get a "min_unclear" flag (no strong tag, not in Top overs) until NBA.com confirms the lineup."""
    confirmed = set()
    for gid, lu in (live.get("lineups") or {}).items():
        g = next((x for x in live.get("games", []) if x["id"] == gid), None)
        for side in ("away", "home"):
            if g and ((lu or {}).get(side) or {}).get("status") == "confirmed":
                confirmed.add(g[side])
    teams = {t for g in live.get("games", []) for t in (g["away"], g["home"])} - confirmed
    rows = {}
    for p in live.get("players", []):
        if p.get("team") not in teams:
            continue
        played = lambda arr: [x for x in (arr or []) if (x.get("min") or 0) > 0]
        cur, last = played(p.get("season")), played(p.get("lastSeason"))
        if not cur and not last:
            continue
        rows.setdefault(p["team"], []).append((p["name"], minutes_model(cur, last)[0], {x.get("d") for x in cur}, status_of(p["name"])))
    out = {}
    for team, rs in rows.items():
        last_dates = set(sorted({d for r in rs for d in r[2] if d}, reverse=True)[:FRESH_GAMES])
        names = [n for n, e, ds, st in sorted(rs, key=lambda r: -r[1]) if st == "Out" and e >= KEY_MIN and ds & last_dates]
        if names:
            out[team] = names
    return out


def nb_cdf(k: int, mean: float, sd: float) -> float:
    if k < 0:
        return 0.0
    v = max(sd * sd, mean * 1.05)
    r = mean * mean / (v - mean)
    q = r / (r + mean)
    pm = q ** r
    c = pm
    for i in range(1, k + 1):
        pm *= (i - 1 + r) / i * (1 - q)
        c += pm
    return min(1.0, c)


def pure_chance(market: str, line: float, projection: float, sd: float) -> tuple[float, str]:
    if market in COUNT_MARKETS and projection > 0.05:
        over = 1 - nb_cdf(math.floor(line), projection, sd)
        under = nb_cdf(math.ceil(line) - 1, projection, sd)
        dist = "count"
    else:
        is_int = float(line).is_integer()
        over = 1 - norm_cdf(((line + 0.5 if is_int else line) - projection) / sd)
        under = norm_cdf(((line - 0.5 if is_int else line) - projection) / sd)
        dist = "normal"
    t = (over + under) or 1
    return over / t, dist


# ----------------------------------------------------------------------------- build picks from a live.json dict
def slate_injuries(live: dict) -> list[dict]:
    teams = {t for g in live.get("games", []) for t in (g["away"], g["home"])}
    out = []
    for i in live.get("injuries", []):
        if i.get("team") in teams:
            out.append({**i, "status": i.get("status") or "Unknown",
                        "detail": i.get("detail") or i.get("comment") or i.get("rawStatus") or "",
                        "updated": i.get("updated") or ((live.get("sections") or {}).get("injuries") or {}).get("fetchedAt")})
    return out


def build_picks(live: dict, games_filter: set | None = None) -> list[dict]:
    """Every priced prop SWISH would show, with its projection, chances, flags and verdict."""
    games = {g["id"]: g for g in live.get("games", [])}
    game_of_team = {}
    for g in live.get("games", []):
        game_of_team[g["away"]] = (g, g["home"])
        game_of_team[g["home"]] = (g, g["away"])
    injuries = slate_injuries(live)

    def injury_of(name):
        return next((i for i in injuries if i.get("player") == name), None)

    generated_at = parse_ts((live.get("meta") or {}).get("writtenAt"))
    odds_fetched = ((live.get("sections") or {}).get("odds") or {}).get("fetchedAt")
    props_by = {}
    for x in live.get("props", []):
        props_by.setdefault((x.get("key"), x.get("market"), x.get("game")), []).append(x)

    shifts = minute_shifts(live, lambda n: (injury_of(n) or {}).get("status") or "Active")
    unclear = key_absences(live, lambda n: (injury_of(n) or {}).get("status") or "Active")
    picks = []
    for p in live.get("players", []):
        if p.get("team") not in game_of_team:
            continue
        g, opp = game_of_team[p["team"]]
        if games_filter is not None and g["id"] not in games_filter:
            continue
        played = lambda arr: [x for x in (arr or []) if (x.get("min") or 0) > 0]
        cur, last = played(p.get("season")), played(p.get("lastSeason"))
        recent = cur + last
        if not recent:
            continue
        r10 = recent[:10]
        exp0, cur_min, last_min, role_delta = minutes_model(cur, last)
        shift = shifts.get(p["name"])
        exp_min = exp0 + shift["gain"] if shift else exp0
        mins = js_round(exp_min)
        role_change = len(cur) >= 2 and last_min is not None and abs(role_delta) >= ROLE_CHANGE_MIN
        w_cur = min(1, len(cur) / 10)

        def season_avg(m):
            a = avg([x[m] for x in cur]) if cur else 0
            b = avg([x[m] for x in last]) if last else a
            return w_cur * a + (1 - w_cur) * b

        avgs = {m: season_avg(m) for m in MARKETS}
        inj = injury_of(p["name"])
        status = inj["status"] if inj else "Active"
        if status == "Out" or mins < MIN_MINUTES_FOR_PROPS:
            continue
        markets = [m for m in MARKETS if m != "3PM" or avgs["3PM"] >= 0.8] if mins >= 22 else ["PTS", "REB", "PRA"]

        for market in markets:
            refs = props_by.get((norm_name(p["name"]), market, g["id"]), [])
            if not refs:
                continue
            cnt = {}
            for r in refs:
                cnt[r["line"]] = cnt.get(r["line"], 0) + 1
            line = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            at = [r for r in refs if r["line"] == line]
            am = lambda xs: js_round(prob_to_american_raw(avg([american_to_prob(v) for v in xs])))
            over_am, under_am = am([r["over"] for r in at]), am([r["under"] for r in at])
            fetched = max([r["fetched"] for r in at if r.get("fetched")], default=None) or odds_fetched
            updated = max([r.get("updated") or "" for r in at]) or odds_fetched

            # ---- projection
            recent_v = [x[market] for x in recent]
            last10 = [x[market] for x in r10]
            s_avg = avgs[market]
            l10 = avg(last10) if last10 else s_avg
            # v1.1: per-minute rate × expected minutes (role changes show up in minutes first)
            rc, rl = rate(cur, market), rate(last, market)
            s_rate = (w_cur * rc + (1 - w_cur) * rl) if rc is not None and rl is not None else (rc if rc is not None else rl)
            l_rate = rate(r10, market)
            rt = 0.55 * (s_rate or 0) + 0.45 * (l_rate or 0)
            base = max(0.1, rt * exp0)
            h2h_games = [x for x in recent if x.get("opp") == opp][:4]
            h2h = [x[market] for x in h2h_games]
            n = len(h2h)
            h2h_avg = (rate(h2h_games, market) or 0) * exp0 if n else base
            w = H2H_MAX_WEIGHT * n / (n + H2H_K) if n else 0
            projection0 = base * (1 - w) + h2h_avg * w
            projection = projection0 * exp_min / exp0 if exp0 > 0 else projection0   # teammate out → more minutes
            sd_game = max(SD_FLOOR[market], 0.5 * stdev(recent_v[:20]) + 0.5 * CV[market] * projection)
            sd = math.sqrt(sd_game ** 2 + (PROJ_ERR * projection) ** 2)

            # ---- pricing
            raw_o, raw_u = american_to_prob(over_am), american_to_prob(under_am)
            mkt_o = raw_o / (raw_o + raw_u)
            pure_o, dist = pure_chance(market, line, projection, sd)
            model_o = MODEL_WEIGHT * pure_o + (1 - MODEL_WEIGHT) * mkt_o
            side = "over" if (model_o - mkt_o) >= ((1 - model_o) - (1 - mkt_o)) else "under"
            model_p = model_o if side == "over" else 1 - model_o
            mkt_p = mkt_o if side == "over" else 1 - mkt_o
            price = over_am if side == "over" else under_am
            edge = model_p - mkt_p
            ev = model_p * (american_to_decimal(price) - 1) - (1 - model_p)

            # ---- flags (same rules as the website; stored as short codes + text)
            flags = []
            if status in ("Questionable", "Doubtful"):
                flags.append(("status", f"Listed {status.lower()} ({(inj.get('detail') or '').lower()})"))
            ts_upd = parse_ts(updated)
            if generated_at and ts_upd and (generated_at - ts_upd).total_seconds() / 60 > STALE_AFTER_MIN:
                flags.append(("stale", "Stale price"))
            ts_f = parse_ts(fetched)
            if ts_f:
                late = [i for i in injuries if i.get("team") in (g["away"], g["home"]) and i.get("status") != "Probable"
                        and parse_ts(i.get("updated")) and parse_ts(i.get("updated")) > ts_f]
                if late:
                    flags.append(("injury_after_line", "Injury news after the line: " + ", ".join(f"{i['player']} {i['status'].lower()}" for i in late[:3])))
            if role_change and len(cur) < ROLE_NEW_GAMES:
                flags.append(("new_role", f"Minutes changed a lot vs last season ({js_round(last_min)}→{js_round(cur_min)}) with only {len(cur)} games this season"))
            if p["team"] in unclear:
                flags.append(("min_unclear", f"Minutes unclear — {', '.join(unclear[p['team']][:2])} out; waiting for the confirmed lineup"))
            if len(recent) < 5:
                flags.append(("few_games", f"Only {len(recent)} games of data"))
            gap = abs(projection - line)
            if gap > BIG_GAP_SD * sd or gap > BIG_GAP_REL * max(line, 2):
                flags.append(("big_gap", "Line far from projection — possible role/minutes news"))

            value = not flags and edge >= MIN_EDGE and ev > 0
            lean = "none" if edge < 0.01 else side
            verdict = ("check" if flags else "strong" if value else "some" if edge >= 0.03 else "slight" if edge >= 0.01 else "none")
            picks.append({
                "game": g["id"], "tipoff": g.get("tipoff"), "away": g["away"], "home": g["home"],
                "player": p["name"], "espnId": p.get("espnId"), "team": p["team"], "opp": opp, "market": market,
                "line": line, "over": over_am, "under": under_am, "book": ", ".join(r["book"] for r in at),
                "fetched": fetched, "oddsUpdated": updated,
                "projection": round(projection, 3), "sd": round(sd, 3), "minutes": mins, "games": len(recent),
                "curGames": len(cur), "roleDelta": round(role_delta, 1) if role_change else 0,
                "minBoost": round(shift["gain"], 1) if shift else 0, "boostFrom": shift["from"] if shift else [], "starterTonight": bool(shift and shift.get("starter")),
                "pureO": round(pure_o, 5), "mktO": round(mkt_o, 5), "modelO": round(model_o, 5), "dist": dist,
                "side": side, "lean": lean, "modelP": round(model_p, 5), "mktP": round(mkt_p, 5), "price": price,
                "edge": round(edge, 5), "ev": round(ev, 5), "value": value, "verdict": verdict,
                "flags": [f[0] for f in flags], "flagText": [f[1] for f in flags],
                "modelVersion": MODEL_VERSION, "modelWeight": MODEL_WEIGHT,
            })
    return picks
