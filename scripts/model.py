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

MODEL_VERSION = "v1.0 (2026-10-28)"

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
        mins = js_round(avg([x.get("min") or 0 for x in r10]))
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
            base = max(0.1, 0.55 * s_avg + 0.45 * l10)
            h2h_games = [x for x in recent if x.get("opp") == opp][:4]
            h2h = [x[market] for x in h2h_games]
            n = len(h2h)
            h2h_avg = avg(h2h) if n else base
            w = H2H_MAX_WEIGHT * n / (n + H2H_K) if n else 0
            projection = base * (1 - w) + h2h_avg * w
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
                "pureO": round(pure_o, 5), "mktO": round(mkt_o, 5), "modelO": round(model_o, 5), "dist": dist,
                "side": side, "lean": lean, "modelP": round(model_p, 5), "mktP": round(mkt_p, 5), "price": price,
                "edge": round(edge, 5), "ev": round(ev, 5), "value": value, "verdict": verdict,
                "flags": [f[0] for f in flags], "flagText": [f[1] for f in flags],
                "modelVersion": MODEL_VERSION, "modelWeight": MODEL_WEIGHT,
            })
    return picks
