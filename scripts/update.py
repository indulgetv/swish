#!/usr/bin/env python3
"""
SWISH data updater
==================
Fetches free NBA data, checks it, stamps every section with its source and
time, and writes:

    data/live.json   – the full data set (easy to inspect)
    data/live.js     – the same data as `window.SWISH_LIVE = {...}` for the page

Sources (all free):
    ESPN public JSON feeds  – schedule, scores, standings, injuries, rosters,
                              player game logs, team results (head-to-head)
    The Odds API (free key) – NBA player-prop lines from US books (reference)
                              and UK game lines (totals / spreads)

Modes:
    full   – everything except odds (run once or twice a day)
    light  – schedule/scores + injuries only (run often on game days)
    odds   – odds only, within the free monthly credit budget

Rules this script follows:
    * Never invent data. If a source fails, the previous copy of that section is
      kept with its ORIGINAL timestamp, and the error is recorded.
    * Every section records `source`, `fetchedAt` and `ok`.
"""
from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_JSON = DATA_DIR / "live.json"
OUT_JS = DATA_DIR / "live.js"

ET = ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (SWISH personal NBA dashboard)", "Accept": "application/json"}

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
ESPN_V2 = "https://site.api.espn.com/apis/v2/sports/basketball/nba"
ESPN_COMMON = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"
ODDS_BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"

# ESPN uses a few short codes that differ from the usual NBA ones
ABBR_FIX = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS", "PHO": "PHX", "BK": "BKN"}

PROP_MARKETS = {"player_points": "PTS", "player_rebounds": "REB", "player_assists": "AST",
                "player_threes": "3PM", "player_points_rebounds_assists": "PRA"}
ODDS_MARKETS_DEFAULT = ["player_points", "player_rebounds", "player_assists"]
# "auto" picks as many of these (in this order) as the day's credit budget allows for EVERY game (user preference: PTS, REB, AST only)
ODDS_MARKETS_PRIORITY = ["player_points", "player_rebounds", "player_assists"]   # the user bets PTS/REB/AST; threes/PRA not bought
# Team names that differ between ESPN and The Odds API
TEAM_ALIASES = {"laclippers": "losangelesclippers"}
REF_BOOKS = ["fanduel", "draftkings", "betmgm"]          # US reference books
UK_BOOKS = ["skybet", "paddypower", "williamhill"]        # UK game lines


# ----------------------------------------------------------------------------- helpers
def log(msg: str) -> None:
    print(f"[swish] {msg}", flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fix_abbr(a: str | None) -> str | None:
    if not a:
        return a
    a = a.upper()
    return ABBR_FIX.get(a, a)


def get_json(url: str, params: dict | None = None, tries: int = 3, pause: float = 0.25):
    """GET a JSON document. Returns (data, headers) or raises the last error."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read().decode("utf-8")
                time.sleep(pause)
                return json.loads(body), dict(r.headers)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404, 422):
                break
        except Exception as e:  # network hiccup, bad JSON, timeout
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last


def norm_name(n: str) -> str:
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n.lower())
    return re.sub(r"[^a-z]", "", n)


def norm_team(n: str) -> str:
    k = norm_name(n)
    return TEAM_ALIASES.get(k, k)


def slate_date(arg: str | None) -> datetime:
    """The NBA 'day' is the US Eastern calendar date."""
    if arg:
        return datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=ET)
    return datetime.now(ET)


def section(source: str, ok: bool, **extra) -> dict:
    return {"source": source, "fetchedAt": now_iso(), "ok": ok, **extra}


# ----------------------------------------------------------------------------- ESPN: schedule
NBA_HDR = {"User-Agent": UA["User-Agent"], "Accept": "application/json", "Referer": "https://www.nba.com/", "Origin": "https://www.nba.com"}


def fetch_nba_lineups(day: datetime) -> dict:
    """NBA.com's daily lineups file (the data behind nba.com/players/todays-lineups).
    Returns {TEAM: {"starters": [{name, pos}], "status": "confirmed"|"expected"}}. Experimental: may be blocked."""
    url = f"https://stats.nba.com/js/data/leaders/00_daily_lineups_{day.strftime('%Y%m%d')}.json"
    req = urllib.request.Request(url, headers=NBA_HDR)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = {}
    for g in data.get("games", []):
        for side in ("homeTeam", "awayTeam"):
            t = g.get(side) or {}
            ab = fix_abbr(t.get("teamAbbreviation") or t.get("teamTricode"))
            starters, statuses = [], []
            for pl in t.get("players", []):
                pos = (pl.get("position") or "").strip()
                if not pos:                                 # bench players have no starting position
                    continue
                name = pl.get("playerName") or f"{pl.get('firstName', '')} {pl.get('lastName', '')}".strip()
                starters.append({"name": name, "pos": pos})
                statuses.append((pl.get("lineupStatus") or "").lower())
            if ab and starters:
                out[ab] = {"starters": starters[:5], "status": "confirmed" if statuses and all(s == "confirmed" for s in statuses) else "expected"}
    return out


def fetch_espn_starters(game_id: str) -> dict:
    """Starting fives from ESPN's box score (available once the game has started)."""
    data, _ = get_json(f"{ESPN_SITE}/summary", {"event": game_id})
    out = {}
    for team in ((data.get("boxscore") or {}).get("players") or []):
        ab = fix_abbr((team.get("team") or {}).get("abbreviation"))
        names = []
        for grp in team.get("statistics") or []:
            for a in grp.get("athletes") or []:
                if a.get("starter"):
                    names.append((a.get("athlete") or {}).get("displayName"))
        if ab and names:
            out[ab] = [n for n in names if n][:5]
    return out


def choose_auto_mode(prev: dict) -> tuple[str, str]:
    """Pick the job for 'now' (UTC). Safe to call every few minutes: full and odds runs only happen once per window."""
    now = datetime.now(timezone.utc)
    t = now.hour * 60 + now.minute
    def ago_h(iso):
        try:
            return (now - datetime.fromisoformat(str(iso).replace("Z", "+00:00"))).total_seconds() / 3600
        except Exception:
            return 99
    last_full = ago_h((prev.get("meta") or {}).get("lastFullAt"))
    runs = ((prev.get("sections") or {}).get("odds") or {}).get("runs") or []
    odds_today = {r.get("window") for r in runs if str(r.get("at", ""))[:10] == now.strftime("%Y-%m-%d")}
    if (7 * 60 <= t < 9 * 60 or 14 * 60 <= t < 14 * 60 + 30) and last_full > 3:
        return "full", "all"
    if 14 * 60 + 30 <= t < 16 * 60 and "early" not in odds_today:
        return "odds", "early"
    if 21 * 60 <= t < 22 * 60 + 30 and "late" not in odds_today:
        return "odds", "late"
    return "light", "all"


def fetch_scoreboard(day: datetime):
    data, _ = get_json(f"{ESPN_SITE}/scoreboard", {"dates": day.strftime("%Y%m%d")})
    season_year = (data.get("season") or {}).get("year")
    games, teams = [], {}
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        sides = {}
        for c in comp.get("competitors", []):
            t = c.get("team", {})
            ab = fix_abbr(t.get("abbreviation"))
            teams[ab] = {
                "espnId": t.get("id"),
                "city": t.get("location") or "",
                "name": t.get("name") or t.get("shortDisplayName") or ab,
                "displayName": t.get("displayName"),
                "color": "#" + (t.get("color") or "777777"),
                "alt": "#" + t["alternateColor"] if t.get("alternateColor") else None,
                "record": next((r.get("summary") for r in c.get("records", []) if r.get("type") in ("total", None) or r.get("name") == "overall"), None),
            }
            sides[c.get("homeAway")] = {"abbr": ab, "score": c.get("score")}
        st = (comp.get("status") or ev.get("status") or {}).get("type", {})
        odds = (comp.get("odds") or [{}])[0] if comp.get("odds") else {}
        if "home" not in sides or "away" not in sides:
            continue
        games.append({
            "id": str(ev.get("id")),
            "away": sides["away"]["abbr"], "home": sides["home"]["abbr"],
            "tipoff": ev.get("date"),
            "state": st.get("state"),                     # pre / in / post
            "status": st.get("shortDetail") or st.get("detail") or st.get("description"),
            "completed": bool(st.get("completed")),
            "awayScore": sides["away"].get("score"), "homeScore": sides["home"].get("score"),
            "espnLine": {"details": odds.get("details"), "overUnder": odds.get("overUnder"),
                         "provider": (odds.get("provider") or {}).get("name")} if odds else None,
        })
    return games, teams, season_year


# ----------------------------------------------------------------------------- ESPN: standings
def fetch_standings():
    data, _ = get_json(f"{ESPN_V2}/standings")
    out, teams = {}, {}
    for conf in data.get("children", []):
        label = "East" if "east" in (conf.get("name", "") + conf.get("abbreviation", "")).lower() else "West"
        rows = []
        for e in (conf.get("standings") or {}).get("entries", []):
            t = e.get("team", {})
            ab = fix_abbr(t.get("abbreviation"))
            stats = {s.get("name"): s for s in e.get("stats", [])}
            w = int((stats.get("wins") or {}).get("value") or 0)
            l = int((stats.get("losses") or {}).get("value") or 0)
            rows.append({"team": ab, "w": w, "l": l,
                         "gb": (stats.get("gamesBehind") or {}).get("displayValue"),
                         "seed": (stats.get("playoffSeed") or {}).get("value"),
                         "streak": (stats.get("streak") or {}).get("displayValue")})
            teams[ab] = {"espnId": t.get("id"), "city": t.get("location") or "", "name": t.get("name") or ab,
                         "displayName": t.get("displayName")}
        rows.sort(key=lambda r: (-(r["w"] / max(1, r["w"] + r["l"])), -r["w"]))
        out[label] = rows
    if not out.get("East") or not out.get("West"):
        raise ValueError("standings response missing a conference")
    return out, teams


# ----------------------------------------------------------------------------- ESPN: injuries
STATUS_MAP = {"out": "Out", "doubtful": "Doubtful", "questionable": "Questionable", "probable": "Probable",
              "day-to-day": "Questionable", "day to day": "Questionable", "suspension": "Out", "out for season": "Out"}


def fetch_injuries(name_to_abbr: dict):
    data, _ = get_json(f"{ESPN_SITE}/injuries")
    out = []
    for grp in data.get("injuries", []):
        team_ab = fix_abbr(name_to_abbr.get(grp.get("displayName")))
        for inj in grp.get("injuries", []):
            ath = inj.get("athlete", {})
            ab = fix_abbr(((ath.get("team") or {}).get("abbreviation"))) or team_ab
            raw = (inj.get("status") or "").strip()
            status = STATUS_MAP.get(raw.lower(), raw.title() or "Unknown")
            det = inj.get("details") or {}
            detail = " ".join(x for x in [det.get("side"), det.get("type"), det.get("detail")] if x) or (inj.get("type") or {}).get("description") or raw
            out.append({"team": ab, "player": ath.get("displayName"), "pos": (ath.get("position") or {}).get("abbreviation"),
                        "status": status, "rawStatus": raw, "detail": detail,
                        "comment": inj.get("shortComment"), "updated": inj.get("date"),
                        "returnDate": det.get("returnDate")})
    return out


# ----------------------------------------------------------------------------- ESPN: rosters + game logs
def fetch_roster(team_id: str):
    data, _ = get_json(f"{ESPN_SITE}/teams/{team_id}/roster")
    players = []
    for a in data.get("athletes", []):
        # roster may be flat or grouped by position
        items = a.get("items") if isinstance(a, dict) and "items" in a else [a]
        for p in items:
            players.append({"espnId": p.get("id"), "name": p.get("displayName") or p.get("fullName"),
                            "pos": (p.get("position") or {}).get("abbreviation"), "jersey": p.get("jersey")})
    return [p for p in players if p["espnId"] and p["name"]]


def parse_made(v: str) -> int:
    # "3-7" → 3 ; "12" → 12
    try:
        return int(str(v).split("-")[0])
    except Exception:
        return 0


def fetch_gamelog(athlete_id: str, season: int | None):
    params = {"season": season} if season else None
    data, _ = get_json(f"{ESPN_COMMON}/athletes/{athlete_id}/gamelog", params)
    labels = [x.upper() for x in data.get("labels", [])]
    idx = {k: labels.index(k) for k in ("MIN", "REB", "AST", "PTS", "3PT", "STL", "BLK", "TO") if k in labels}
    meta = data.get("events", {}) or {}
    games = []
    for st in data.get("seasonTypes", []):
        name = (st.get("displayName") or "").lower()
        if "preseason" in name:
            continue
        for cat in st.get("categories", []):
            for ev in cat.get("events", []):
                s = ev.get("stats") or []
                if not s or "PTS" not in idx:
                    continue
                m = meta.get(str(ev.get("eventId")), {})
                try:
                    mins = float(str(s[idx["MIN"]]).split(":")[0]) if "MIN" in idx else None
                except Exception:
                    mins = None
                g = {"id": str(ev.get("eventId")), "d": (m.get("gameDate") or "")[:10],
                     "opp": fix_abbr((m.get("opponent") or {}).get("abbreviation")),
                     "home": m.get("atVs") == "vs", "result": m.get("gameResult"),
                     "min": mins, "PTS": parse_made(s[idx["PTS"]]),
                     "REB": parse_made(s[idx["REB"]]) if "REB" in idx else 0,
                     "AST": parse_made(s[idx["AST"]]) if "AST" in idx else 0,
                     "3PM": parse_made(s[idx["3PT"]]) if "3PT" in idx else 0,
                     "STL": parse_made(s[idx["STL"]]) if "STL" in idx else None,
                     "BLK": parse_made(s[idx["BLK"]]) if "BLK" in idx else None,
                     "TOV": parse_made(s[idx["TO"]]) if "TO" in idx else None}
                g["PRA"] = g["PTS"] + g["REB"] + g["AST"]
                games.append(g)
    # de-duplicate and sort newest first
    seen, uniq = set(), []
    for g in sorted(games, key=lambda g: g["d"], reverse=True):
        if g["id"] not in seen:
            seen.add(g["id"]); uniq.append(g)
    return uniq


def fetch_team_results(team_id: str, season: int):
    """Completed games for a team in a season (for head-to-head)."""
    data, _ = get_json(f"{ESPN_SITE}/teams/{team_id}/schedule", {"season": season})
    out = []
    for ev in data.get("events", []):
        comp = (ev.get("competitions") or [{}])[0]
        st = (comp.get("status") or {}).get("type", {})
        if not st.get("completed"):
            continue
        sides = {}
        for c in comp.get("competitors", []):
            sc = c.get("score")
            sc = sc.get("value") if isinstance(sc, dict) else sc
            try:
                sc = int(float(sc))
            except Exception:
                sc = None
            sides[c.get("homeAway")] = {"abbr": fix_abbr((c.get("team") or {}).get("abbreviation")), "score": sc}
        if "home" in sides and "away" in sides and sides["home"]["score"] is not None:
            out.append({"d": (ev.get("date") or "")[:10], "home": sides["home"]["abbr"], "away": sides["away"]["abbr"],
                        "hp": sides["home"]["score"], "ap": sides["away"]["score"]})
    return out


# ----------------------------------------------------------------------------- The Odds API
def odds_budget(remaining: int) -> int:
    today = datetime.now(timezone.utc)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_left = days_in_month - today.day + 1
    return max(0, remaining // max(1, days_left))


def fetch_odds(key: str, game_ids_by_teams: dict, markets: list[str], max_events: int | None):
    """Returns (props, gameLines, info). Spends credits carefully."""
    info = {"creditsUsed": 0, "creditsRemaining": None, "eventsPriced": 0, "notes": []}
    fetched_at = now_iso()
    # 1) events list (does not cost credits)
    events, hdr = get_json(f"{ODDS_BASE}/events", {"apiKey": key})
    remaining = int(hdr.get("x-requests-remaining") or hdr.get("X-Requests-Remaining") or 0)
    info["creditsRemaining"] = remaining
    budget = odds_budget(remaining)
    info["budgetToday"] = budget
    log(f"odds: {remaining} credits left this month, budget today {budget}")

    # Match events to today's ESPN games by team names
    def ev_key(e):
        return (norm_team(e.get("away_team", "")), norm_team(e.get("home_team", "")))
    todays = [e for e in events if ev_key(e) in game_ids_by_teams]
    props, lines = [], []

    # 2) UK game lines (totals/spreads) — nice to have only: ESPN already gives a free spread/total, so these are
    #    bought only when the budget also covers points, rebounds and assists for every game (props come first)
    if todays and budget >= 3 * len(todays) + 2:
        try:
            data, hdr = get_json(f"{ODDS_BASE}/odds", {"apiKey": key, "regions": "uk", "markets": "totals,spreads",
                                                       "bookmakers": ",".join(UK_BOOKS), "oddsFormat": "decimal"})
            used = int(hdr.get("x-requests-last") or 0); info["creditsUsed"] += used; budget -= used
            for e in data:
                gid = game_ids_by_teams.get(ev_key(e))
                if not gid:
                    continue
                for b in e.get("bookmakers", []):
                    for m in b.get("markets", []):
                        for o in m.get("outcomes", []):
                            lines.append({"game": gid, "book": b.get("key"), "market": m.get("key"),
                                          "name": o.get("name"), "point": o.get("point"), "price": o.get("price"),
                                          "updated": b.get("last_update")})
        except Exception as e:
            info["notes"].append(f"UK game lines failed: {e}")

    # 3) US player-prop reference lines, one event at a time within budget
    if markets == ["auto"]:
        # cover every game first, then add markets in priority order while the budget allows
        n = max(1, min(len(ODDS_MARKETS_PRIORITY), budget // max(1, len(todays))))
        markets = ODDS_MARKETS_PRIORITY[:n]
        log(f"odds: auto markets for {len(todays)} games -> {', '.join(markets)}")
    info["markets"] = [PROP_MARKETS.get(m, m) for m in markets]
    per_event = len(markets)
    allowed = budget // per_event if per_event else 0
    if max_events is not None:
        allowed = min(allowed, max_events)
    todays.sort(key=lambda e: e.get("commence_time", ""))
    for e in todays[:allowed]:
        gid = game_ids_by_teams.get(ev_key(e))
        try:
            data, hdr = get_json(f"{ODDS_BASE}/events/{e['id']}/odds", {
                "apiKey": key, "regions": "us", "markets": ",".join(markets),
                "bookmakers": ",".join(REF_BOOKS), "oddsFormat": "american"})
        except Exception as ex:
            info["notes"].append(f"props failed for {e.get('away_team')} @ {e.get('home_team')}: {ex}")
            continue
        info["creditsUsed"] += int(hdr.get("x-requests-last") or 0)
        info["creditsRemaining"] = int(hdr.get("x-requests-remaining") or info["creditsRemaining"] or 0)
        info["eventsPriced"] += 1
        for b in data.get("bookmakers", []):
            for m in b.get("markets", []):
                mk = PROP_MARKETS.get(m.get("key"))
                if not mk:
                    continue
                pairs = {}
                for o in m.get("outcomes", []):
                    who = o.get("description") or ""
                    k = (who, o.get("point"))
                    pairs.setdefault(k, {})[o.get("name", "").lower()] = o.get("price")
                for (who, point), side in pairs.items():
                    if "over" in side and "under" in side and point is not None:
                        props.append({"game": gid, "player": who, "key": norm_name(who), "market": mk, "line": point,
                                      "over": side["over"], "under": side["under"], "book": b.get("key"),
                                      "updated": m.get("last_update") or b.get("last_update"), "fetched": fetched_at})
    if len(todays) > allowed:
        info["notes"].append(f"Priced {allowed} of {len(todays)} games to stay inside the free monthly credits.")
    return props, lines, info


# ----------------------------------------------------------------------------- main
def load_previous() -> dict:
    if OUT_JSON.exists():
        try:
            return json.loads(OUT_JSON.read_text())
        except Exception:
            pass
    return {}


def write_out(d: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    d["meta"]["writtenAt"] = now_iso()
    OUT_JSON.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    OUT_JS.write_text("// Generated by scripts/update.py — do not edit by hand.\nwindow.SWISH_LIVE = "
                      + json.dumps(d, separators=(",", ":"), ensure_ascii=False) + ";\n")
    # tiny file the website polls to know when fresh data is available
    (DATA_DIR / "stamp.json").write_text(json.dumps({"writtenAt": d["meta"]["writtenAt"], "mode": d["meta"].get("mode")}))
    log(f"wrote {OUT_JSON.relative_to(ROOT)} ({OUT_JSON.stat().st_size // 1024} KB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["auto", "full", "light", "odds"], default="full",
                    help='"auto" picks the right job for the time of day (safe to call every few minutes)')
    ap.add_argument("--date", help="slate date YYYY-MM-DD (US Eastern); default today")
    ap.add_argument("--max-events", type=int, default=None, help="cap on games priced for props")
    ap.add_argument("--window", choices=["all", "early", "late"], default="all",
                    help='odds only: "early" = games tipping before --early-cutoff (UTC); "late" = games not started yet')
    ap.add_argument("--early-cutoff", default="21:30", help="UTC time HH:MM that splits early from late games")
    ap.add_argument("--markets", default="auto", help='"auto" (fit the daily budget) or a comma list of Odds API market keys')
    args = ap.parse_args()

    day = slate_date(args.date)
    prev = load_previous()
    if args.mode == "auto":
        args.mode, args.window = choose_auto_mode(prev)
        log(f"auto: running {args.mode}{' (' + args.window + ')' if args.mode == 'odds' else ''}")
    d = {"meta": {"slateDate": day.strftime("%Y-%m-%d"), "mode": args.mode, "errors": [],
                  "lastFullAt": (prev.get("meta") or {}).get("lastFullAt")}}
    if args.mode == "full":
        d["meta"]["lastFullAt"] = now_iso()
    for k in ("games", "teams", "standings", "injuries", "players", "h2h", "props", "gameLines", "sections", "lineups"):
        d[k] = prev.get(k, {} if k in ("teams", "standings", "h2h", "sections", "lineups") else [])
    # A new slate day invalidates the previous day's games / props
    if prev.get("meta", {}).get("slateDate") != d["meta"]["slateDate"]:
        d["games"], d["props"], d["gameLines"], d["h2h"], d["lineups"] = [], [], [], {}, {}
        d["sections"] = {k: v for k, v in d["sections"].items() if k in ("standings", "injuries")}
    errs = d["meta"]["errors"]

    # ---- schedule (every mode)
    season = None
    try:
        games, teams, season = fetch_scoreboard(day)
        d["games"] = games
        for ab, t in teams.items():
            d["teams"].setdefault(ab, {}).update({k: v for k, v in t.items() if v})
        d["sections"]["games"] = section("ESPN scoreboard", True, count=len(games))
        log(f"schedule: {len(games)} games on {d['meta']['slateDate']}")
    except Exception as e:
        errs.append(f"schedule: {e}"); d["sections"].setdefault("games", section("ESPN scoreboard", False))["ok"] = False
        log(f"schedule FAILED: {e}")
    season = season or (day.year + 1 if day.month >= 8 else day.year)
    d["meta"]["season"] = season

    # ---- standings (full)
    if args.mode == "full":
        try:
            st, teams = fetch_standings()
            d["standings"] = st
            for ab, t in teams.items():
                d["teams"].setdefault(ab, {}).update({k: v for k, v in t.items() if v})
            d["sections"]["standings"] = section("ESPN standings", True)
            log("standings: ok")
        except Exception as e:
            errs.append(f"standings: {e}"); log(f"standings FAILED: {e}")

    # ---- lineups (full + light): NBA.com pre-game list (experimental) + ESPN starters once a game starts
    if args.mode in ("full", "light") and d["games"]:
        lu = d.setdefault("lineups", {})
        info = {}
        if any(g.get("state") == "pre" for g in d["games"]):
            try:
                nba = fetch_nba_lineups(day)
                n_posted = 0
                for g in d["games"]:
                    for side in ("away", "home"):
                        t = nba.get(g[side])
                        cur = (lu.get(g["id"]) or {}).get(side) or {}
                        if t and t["starters"] and cur.get("status") != "started":
                            lu.setdefault(g["id"], {})[side] = {**t, "source": "NBA.com", "fetchedAt": now_iso()}
                            n_posted += 1
                info["nba"] = f"ok: {n_posted} team lineups posted"
                log(f"lineups: NBA.com ok, {n_posted} team lineups posted")
            except Exception as e:
                info["nba"] = f"failed: {e}"
                log(f"lineups: NBA.com not available ({e})")
        started = 0
        for g in d["games"]:
            have = lu.get(g["id"]) or {}
            if g.get("state") in ("in", "post") and not all((have.get(s) or {}).get("status") == "started" for s in ("away", "home")):
                try:
                    st = fetch_espn_starters(g["id"])
                    for side in ("away", "home"):
                        names = st.get(g[side]) or []
                        if names:
                            lu.setdefault(g["id"], {})[side] = {"starters": [{"name": n} for n in names], "status": "started",
                                                                "source": "ESPN box score", "fetchedAt": now_iso()}
                            started += 1
                except Exception as e:
                    errs.append(f"starters {g['id']}: {e}")
        info["espn"] = f"{started} team starting fives from box scores"
        if started:
            log(f"lineups: {started} starting fives from ESPN box scores")
        d["sections"]["lineups"] = section("NBA.com daily lineups (experimental) + ESPN box scores", True, **info)

    # ---- injuries (full + light)
    if args.mode in ("full", "light"):
        try:
            name_to_abbr = {t.get("displayName") or f"{t.get('city','')} {t.get('name','')}".strip(): ab for ab, t in d["teams"].items()}
            d["injuries"] = fetch_injuries(name_to_abbr)
            d["sections"]["injuries"] = section("ESPN injuries", True, count=len(d["injuries"]))
            log(f"injuries: {len(d['injuries'])} entries")
        except Exception as e:
            errs.append(f"injuries: {e}"); log(f"injuries FAILED: {e}")

    # ---- rosters, game logs, head-to-head (full)
    if args.mode == "full" and d["games"]:
        playing = sorted({g[s] for g in d["games"] for s in ("away", "home")})
        players, failures = [], 0
        for ab in playing:
            tid = (d["teams"].get(ab) or {}).get("espnId")
            if not tid:
                errs.append(f"roster: no ESPN id for {ab}"); continue
            try:
                roster = fetch_roster(tid)
            except Exception as e:
                errs.append(f"roster {ab}: {e}"); continue
            for p in roster:
                try:
                    cur = fetch_gamelog(p["espnId"], season)
                    prev_season = fetch_gamelog(p["espnId"], season - 1)
                except Exception as e:
                    failures += 1
                    if failures <= 5:
                        errs.append(f"gamelog {p['name']}: {e}")
                    continue
                if not cur and not prev_season:
                    continue
                players.append({"name": p["name"], "espnId": p["espnId"], "team": ab, "pos": p["pos"], "jersey": p.get("jersey"),
                                "season": cur[:82], "lastSeason": prev_season[:82]})
            log(f"players: {ab} done ({sum(1 for x in players if x['team'] == ab)} with logs)")
        if players:
            d["players"] = players
            d["sections"]["players"] = section("ESPN game logs", True, count=len(players), failures=failures)
        # head-to-head from the home team's results this season and last
        h2h = {}
        for g in d["games"]:
            tid = (d["teams"].get(g["home"]) or {}).get("espnId")
            if not tid:
                continue
            meetings = []
            for s in (season, season - 1):
                try:
                    meetings += [m for m in fetch_team_results(tid, s) if {m["home"], m["away"]} == {g["home"], g["away"]}]
                except Exception as e:
                    errs.append(f"h2h {g['home']} {s}: {e}")
            h2h[g["id"]] = sorted(meetings, key=lambda m: m["d"], reverse=True)[:4]
        d["h2h"] = h2h
        d["sections"]["h2h"] = section("ESPN team schedules", True)

    # ---- odds (odds mode)
    if args.mode == "odds":
        key = os.environ.get("ODDS_API_KEY", "").strip()
        if not key:
            errs.append("odds: ODDS_API_KEY secret is not set"); log("odds skipped: no key")
        elif not d["games"]:
            log("odds skipped: no games today")
        else:
            now = datetime.now(timezone.utc)
            hh, mm = (int(x) for x in args.early_cutoff.split(":"))
            cutoff = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            def tip(g):
                try:
                    return datetime.fromisoformat(g["tipoff"].replace("Z", "+00:00"))
                except Exception:
                    return now + timedelta(hours=6)
            # only games that haven't started; the early window also stops at the cutoff
            chosen = [g for g in d["games"] if g.get("state") == "pre" and tip(g) > now
                      and (args.window != "early" or tip(g) < cutoff)]
            log(f"odds: window={args.window}, {len(chosen)} of {len(d['games'])} games eligible")
            chosen_ids = {g["id"] for g in chosen}
            by_teams = {}
            for g in chosen:
                a, h = d["teams"].get(g["away"], {}), d["teams"].get(g["home"], {})
                by_teams[(norm_team(f"{a.get('city','')} {a.get('name','')}"), norm_team(f"{h.get('city','')} {h.get('name','')}"))] = g["id"]
                if a.get("displayName") and h.get("displayName"):
                    by_teams[(norm_team(a["displayName"]), norm_team(h["displayName"]))] = g["id"]
            try:
                if not chosen:
                    raise RuntimeError("no eligible games in this window")
                props, lines, info = fetch_odds(key, by_teams, [m for m in args.markets.split(",") if m], args.max_events)
                # merge: replace lines only for the games priced now, keep earlier lines for the rest
                priced = {p["game"] for p in props}
                d["props"] = [p for p in d.get("props", []) if p.get("game") not in priced] + props
                gl_games = {l["game"] for l in lines}
                d["gameLines"] = [l for l in d.get("gameLines", []) if l.get("game") not in gl_games] + lines
                runs = [r for r in (d["sections"].get("odds") or {}).get("runs", []) if r.get("at", "")[:10] == now_iso()[:10]]
                runs.append({"at": now_iso(), "window": args.window, "games": sorted(priced), "credits": info["creditsUsed"]})
                info["runs"] = runs
                info["eventsPriced"] = len({p["game"] for p in d["props"]})
                d["sections"]["odds"] = section("The Odds API (US books = reference only; UK game lines)", True, **info)
                log(f"odds: {len(props)} prop lines, {len(lines)} UK game-line outcomes, {info['creditsUsed']} credits used")
            except RuntimeError as e:
                log(f"odds skipped: {e}")
            except Exception as e:
                errs.append(f"odds: {e}"); log(f"odds FAILED: {e}")

    # ---- results tracking: save tonight's picks until tip-off; grade earlier nights each morning
    try:
        import ledger
        d["meta"]["writtenAt"] = now_iso()
        up = ledger.upsert(d, DATA_DIR)
        log(f"results: {up.get('saved', 0)} pre-game picks saved")
        finals = {g["id"] for g in d["games"] if g.get("state") == "post"}
        st = ledger.settle(DATA_DIR, fetch_gamelog, d["meta"]["season"], log=log, final_ids=finals)
        if st["graded"] or st["void"]:
            log(f"results: graded {st['graded']}, void {st['void']}, still waiting {st['waiting']}")
        ledger.write_results(DATA_DIR)
    except Exception as e:
        errs.append(f"results: {e}"); log(f"results FAILED: {e}")

    write_out(d)
    if errs:
        log("completed with warnings:\n  - " + "\n  - ".join(errs[:20]))
    # fail the run only if nothing at all could be fetched
    ok_any = any((v or {}).get("ok") for v in d["sections"].values())
    return 0 if ok_any else 1


if __name__ == "__main__":
    sys.exit(main())
