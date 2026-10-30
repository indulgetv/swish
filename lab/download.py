"""SWISH projection lab — part 1: download whole NBA regular seasons from ESPN (free, no Odds API credits).

For every completed regular-season game it saves the box score: who started, who didn't play, minutes and
PTS / REB / AST / 3PM / STL / BLK / TOV for every player, plus the game's date, teams, score and ESPN's game line
(spread / total) when the summary has one. The replay (part 2) uses this to test model ideas night by night, using only
games played before each night.

Run:  python lab/download.py --season 2026        (ESPN's season year: 2026 = the 2025-26 season)
Output: lab/data/season-<year>.json.gz  (+ a progress log lab/data/download-<year>.log)
Resumable: games already in the output file are skipped, so a re-run only fetches what's missing.
"""
import argparse, gzip, json, sys, time, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

ESPN = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
UA = {"User-Agent": "Mozilla/5.0 (SWISH projection lab)"}
ABBR_FIX = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS", "PHO": "PHX", "BK": "BKN"}
OUT_DIR = Path(__file__).resolve().parent / "data"
STAT_KEYS = {"MIN": "min", "PTS": "PTS", "REB": "REB", "AST": "AST", "STL": "STL", "BLK": "BLK", "TO": "TOV",
             "OREB": "OREB", "DREB": "DREB", "PF": "PF", "+/-": "PM"}


def fix(a):
    return ABBR_FIX.get(a, a) if a else a


def get_json(url, params=None, tries=4, pause=0.2):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                body = r.read().decode("utf-8")
            time.sleep(pause)
            return json.loads(body)
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:
            last = e
        time.sleep(2 * (attempt + 1))
    raise last


def made(v):
    """'4-9' -> 4 (made shots)"""
    try:
        return int(str(v).split("-")[0])
    except Exception:
        return None


def num(v):
    try:
        return float(v) if "." in str(v) else int(v)
    except Exception:
        return None


def season_games(year, log):
    """Every completed regular-season game id with its date, by walking the scoreboard day by day."""
    day, end = datetime(year - 1, 10, 1), datetime(year, 4, 30)
    found = {}
    while day <= end:
        try:
            data = get_json(f"{ESPN}/scoreboard", {"dates": day.strftime("%Y%m%d"), "limit": 50})
        except Exception as e:
            log(f"scoreboard {day:%Y-%m-%d}: {e}")
            day += timedelta(days=1)
            continue
        for ev in data.get("events", []):
            st = ((ev.get("status") or {}).get("type") or {})
            stype = (ev.get("season") or {}).get("type")
            if stype not in (2, None) or not st.get("completed"):
                continue        # regular season only, finished games only
            found[str(ev["id"])] = {"date": day.strftime("%Y-%m-%d"), "tipoff": ev.get("date")}
        day += timedelta(days=1)
    return found


def parse_summary(gid, meta, data):
    comp = ((data.get("header") or {}).get("competitions") or [{}])[0]
    sides = {}
    for c in comp.get("competitors", []):
        sides[c.get("homeAway")] = {"team": fix((c.get("team") or {}).get("abbreviation")), "score": num(c.get("score"))}
    line = {}
    for pc in data.get("pickcenter") or []:
        if pc.get("spread") is not None or pc.get("overUnder") is not None:
            line = {"spread": pc.get("spread"), "total": pc.get("overUnder"), "details": pc.get("details"),
                    "provider": (pc.get("provider") or {}).get("name")}
            break
    players = []
    for team in ((data.get("boxscore") or {}).get("players") or []):
        ab = fix((team.get("team") or {}).get("abbreviation"))
        for grp in team.get("statistics") or []:
            labels = grp.get("labels") or grp.get("keys") or []
            for a in grp.get("athletes") or []:
                ath = a.get("athlete") or {}
                row = {"id": str(ath.get("id")), "name": ath.get("displayName"), "team": ab,
                       "pos": (ath.get("position") or {}).get("abbreviation"),
                       "starter": bool(a.get("starter")), "dnp": bool(a.get("didNotPlay")),
                       "reason": a.get("reason") or None}
                stats = a.get("stats") or []
                for lab, val in zip(labels, stats):
                    L = str(lab).upper()
                    if L in STAT_KEYS:
                        row[STAT_KEYS[L]] = num(val)
                    elif L in ("3PT", "3PM-3PA", "THREEPOINTFIELDGOALSMADE-THREEPOINTFIELDGOALSATTEMPTED"):
                        row["3PM"] = made(val)
                    elif L in ("FG", "FGM-FGA"):
                        row["FGM"] = made(val); row["FGA"] = num(str(val).split("-")[-1]) if "-" in str(val) else None
                    elif L in ("FT", "FTM-FTA"):
                        row["FTM"] = made(val); row["FTA"] = num(str(val).split("-")[-1]) if "-" in str(val) else None
                if row["dnp"] or not stats:
                    row["min"] = 0
                players.append(row)
    return {"id": gid, "date": meta["date"], "tipoff": meta.get("tipoff"),
            "away": (sides.get("away") or {}).get("team"), "home": (sides.get("home") or {}).get("team"),
            "awayScore": (sides.get("away") or {}).get("score"), "homeScore": (sides.get("home") or {}).get("score"),
            "line": line or None, "players": players}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True, help="ESPN season year, e.g. 2026 = 2025-26")
    ap.add_argument("--limit", type=int, default=0, help="only fetch this many new games (testing)")
    a = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"season-{a.season}.json.gz"
    log_path = OUT_DIR / f"download-{a.season}.log"
    lines = []
    def log(m):
        s = f"{datetime.now(timezone.utc):%H:%M:%S} {m}"; print(s, flush=True); lines.append(s)

    have = {}
    if out_path.exists():
        with gzip.open(out_path, "rt") as f:
            have = {g["id"]: g for g in json.load(f).get("games", [])}
        log(f"resuming: {len(have)} games already saved")
    t0 = time.time()
    ids = season_games(a.season, log)
    log(f"schedule: {len(ids)} completed regular-season games found ({time.time() - t0:.0f}s)")
    todo = [g for g in sorted(ids, key=lambda g: ids[g]["date"]) if g not in have]
    if a.limit:
        todo = todo[: a.limit]
    bad = 0
    for i, gid in enumerate(todo, 1):
        try:
            g = parse_summary(gid, ids[gid], get_json(f"{ESPN}/summary", {"event": gid}))
            if len([p for p in g["players"] if (p.get("min") or 0) > 0]) < 10:
                raise ValueError(f"only {len(g['players'])} players in box score")
            have[gid] = g
        except Exception as e:
            bad += 1
            log(f"game {gid} ({ids[gid]['date']}): {e}")
        if i % 100 == 0:
            log(f"{i}/{len(todo)} fetched, {bad} failed")
            save(out_path, a.season, have)        # save as we go, so a timeout keeps the progress
    save(out_path, a.season, have)
    games = list(have.values())
    pg = [p for g in games for p in g["players"]]
    log(f"done: {len(games)} games saved, {bad} failed this run; {sum(1 for p in pg if (p.get('min') or 0) > 0)} player-games played, "
        f"{sum(1 for p in pg if p['starter'])} starter rows, {sum(1 for g in games if g.get('line'))} games with an ESPN line, "
        f"{len({p['id'] for p in pg})} players; took {time.time() - t0:.0f}s")
    if pg:
        s = next(p for p in pg if (p.get("min") or 0) > 0)
        log("sample row: " + json.dumps(s))
    log_path.write_text("\n".join(lines) + "\n")
    return 0


def save(path, season, have):
    games = sorted(have.values(), key=lambda g: (g["date"], g["id"]))
    with gzip.open(path, "wt") as f:
        json.dump({"season": season, "savedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "source": "ESPN summary box scores", "games": games}, f, separators=(",", ":"))


if __name__ == "__main__":
    sys.exit(main())
