"""SWISH projection lab — part 2: replay a past season night by night with the LIVE model (scripts/model.py).

For each game night it builds the same kind of data file the website reads, using ONLY games played before that night:
  - this season's game logs before the night + last season's logs (the "last season" prior)
  - tonight's games, and each team's roster from tonight's box score (who was on the team)
  - injuries: players ESPN lists as not playing with an injury/illness/rest reason = "Out" (known before tip in real life,
    though late scratches would only be known late)
  - lineups (optional, --lineups): tonight's starters as "confirmed" — what SWISH knows ~30 min before tip-off
  - a pretend line for every player/market (his average this season so far, rounded to .5) at even odds, so model.py
    produces a projection; the pretend line also lets us check how well-calibrated SWISH's own chances are.
Then it compares each projection with what actually happened.

Run:  python3 lab/replay.py [--lineups] [--from 2025-11-01] [--label baseline]
Out:  lab/results/<label>.json  (summary numbers the Results page can show)
"""
import argparse, gzip, json, math, statistics, sys, time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import model  # noqa: E402  (replaced by --model when testing another version)

MARKETS = ["PTS", "REB", "AST"]
NOT_INJURY = ("COACH", "DECISION", "G LEAGUE", "TWO-WAY", "NOT WITH TEAM", "SUSPEN", "PERSONAL", "TRADE")


def load(season):
    if not (ROOT / f"lab/data/season-{season}.json.gz").exists():
        return []                                          # no earlier season downloaded → no "last season" prior
    with gzip.open(ROOT / f"lab/data/season-{season}.json.gz", "rt") as f:
        return json.load(f)["games"]


def row(g, p):
    opp = g["home"] if p["team"] == g["away"] else g["away"]
    r = {"id": g["id"], "d": g["date"], "opp": opp, "home": p["team"] == g["home"], "min": float(p.get("min") or 0)}
    for m in ("PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV"):
        r[m] = p.get(m) or 0
    r["PRA"] = r["PTS"] + r["REB"] + r["AST"]
    return r


def is_out(p):
    if not p.get("dnp"):
        return False
    reason = (p.get("reason") or "").upper()
    return not any(k in reason for k in NOT_INJURY)


def half_line(v):
    return math.floor(max(v, 0.6)) + 0.5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--lineups", action="store_true", help="give the model tonight's confirmed starters")
    ap.add_argument("--from", dest="start", default=None, help="first night to score (earlier nights still build history)")
    ap.add_argument("--label", default=None)
    ap.add_argument("--limit-nights", type=int, default=0)
    ap.add_argument("--dump", default=None, help="also write every projection row to this file (for comparisons)")
    ap.add_argument("--model", default=None, help="path to another model.py to test (default: scripts/model.py)")
    a = ap.parse_args()
    if a.model:
        import importlib.util
        global model
        spec = importlib.util.spec_from_file_location("model_alt", a.model)
        model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
    label = a.label or ("baseline-lineups" if a.lineups else "baseline")
    t0 = time.time()

    prev, cur = load(a.season - 1), load(a.season)
    last_logs = defaultdict(list)                      # player id → last season rows, newest first
    for g in sorted(prev, key=lambda g: g["date"], reverse=True):
        for p in g["players"]:
            if (p.get("min") or 0) > 0:
                last_logs[p["id"]].append(row(g, p))
    by_night = defaultdict(list)
    for g in cur:
        by_night[g["date"]].append(g)
    nights = sorted(by_night)
    this_logs = defaultdict(list)                      # player id → this season rows so far, newest first

    rows = []
    for ni, night in enumerate(nights):
        games = by_night[night]
        score = not a.start or night >= a.start
        if score and (not a.limit_nights or ni < a.limit_nights):
            live = {"meta": {"writtenAt": f"{night}T22:00:00Z"}, "games": [], "players": [], "injuries": [], "props": [],
                    "lineups": {}, "sections": {"odds": {"fetchedAt": f"{night}T21:00:00Z"}}}
            actual = {}
            for g in games:
                live["games"].append({"id": g["id"], "away": g["away"], "home": g["home"], "tipoff": f"{night}T23:30:00Z", "state": "pre"})
                if a.lineups:
                    live["lineups"][g["id"]] = {s: {"status": "confirmed", "starters": [{"name": p["name"]} for p in g["players"] if p["team"] == g[s] and p["starter"]]}
                                                for s in ("away", "home")}
                for p in g["players"]:
                    live["players"].append({"name": p["name"], "espnId": p["id"], "team": p["team"], "pos": p.get("pos") or "",
                                            "season": this_logs[p["id"]][:82], "lastSeason": last_logs[p["id"]][:82]})
                    if is_out(p):
                        live["injuries"].append({"team": p["team"], "player": p["name"], "status": "Out", "detail": p.get("reason") or "",
                                                 "updated": f"{night}T18:00:00Z"})
                    actual[p["name"]] = (p, g)
                    played = this_logs[p["id"]] + last_logs[p["id"]]
                    if not played:
                        continue
                    for m in MARKETS:
                        v = model.avg([r[m] for r in played[:20]])
                        live["props"].append({"player": p["name"], "key": model.norm_name(p["name"]), "market": m, "game": g["id"],
                                              "line": half_line(v), "over": -110, "under": -110, "book": "lab",
                                              "fetched": f"{night}T21:00:00Z", "updated": f"{night}T21:00:00Z"})
            for pk in model.build_picks(live):
                p, g = actual[pk["player"]]
                a_min = float(p.get("min") or 0)
                a_val = (p.get(pk["market"]) or 0) if a_min > 0 else 0
                rows.append({"d": night, "p": pk["player"], "m": pk["market"], "proj": pk["projection"], "pmin": pk["minutes"], "amin": a_min,
                             "act": a_val, "line": pk["line"], "pO": pk["pureO"], "boost": pk["minBoost"], "starter": pk.get("starterTonight", False),
                             "unclear": "min_unclear" in pk["flags"], "played": a_min > 0, "curG": pk["curGames"], "sd": pk["sd"], "dist": pk["dist"]})
        # after scoring the night, add its games to history
        for g in games:
            for p in g["players"]:
                if (p.get("min") or 0) > 0:
                    this_logs[p["id"]].insert(0, row(g, p))
        if ni % 20 == 0:
            print(f"{night}: {len(rows)} projections so far ({time.time() - t0:.0f}s)", flush=True)

    out = summarise(rows, label, a)
    if a.dump:
        Path(a.dump).write_text(json.dumps(rows))
    (ROOT / "lab/results").mkdir(parents=True, exist_ok=True)
    (ROOT / f"lab/results/{label}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["overall"], indent=1))
    print(f"took {time.time() - t0:.0f}s")


def stats(rs):
    if not rs:
        return None
    played = [r for r in rs if r["played"]]
    out = {"n": len(rs), "played": len(played)}
    out["minMAE"] = round(statistics.mean(abs(r["pmin"] - r["amin"]) for r in rs), 3)
    out["minBias"] = round(statistics.mean(r["amin"] - r["pmin"] for r in rs), 3)
    for m in MARKETS:
        x = [r for r in rs if r["m"] == m]
        if not x:
            continue
        y = [1 if r["act"] > r["line"] else 0 for r in x]
        out[m] = {"n": len(x), "MAE": round(statistics.mean(abs(r["proj"] - r["act"]) for r in x), 3),
                  "bias": round(statistics.mean(r["act"] - r["proj"] for r in x), 3),
                  "brier": round(statistics.mean((r["pO"] - yy) ** 2 for r, yy in zip(x, y)), 4),
                  "overRate": round(statistics.mean(y), 4), "predOver": round(statistics.mean(r["pO"] for r in x), 4)}
    return out


def summarise(rows, label, a):
    buckets = []
    for lo, hi in ((0, .35), (.35, .45), (.45, .55), (.55, .65), (.65, 1.01)):
        x = [r for r in rows if lo <= r["pO"] < hi and r["played"]]      # players who didn't play = void bets, left out
        if x:
            buckets.append({"from": lo, "to": min(hi, 1), "n": len(x), "predicted": round(statistics.mean(r["pO"] for r in x), 4),
                            "actual": round(statistics.mean(1 if r["act"] > r["line"] else 0 for r in x), 4)})
    months = defaultdict(list)
    for r in rows:
        months[r["d"][:7]].append(r)
    return {"label": label, "modelVersion": model.MODEL_VERSION, "season": a.season, "lineups": a.lineups,
            "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "nights": len({r["d"] for r in rows}),
            "overall": stats(rows),
            "subsets": {"minutesBoosted": stats([r for r in rows if r["boost"] > 0]),
                        "newStarter": stats([r for r in rows if r["starter"]]),
                        "minutesUnclear": stats([r for r in rows if r["unclear"]]),
                        "earlySeason(<5 games)": stats([r for r in rows if r["curG"] < 5])},
            "calibration": buckets,
            "byMonth": {k: {"n": len(v), "minMAE": round(statistics.mean(abs(r["pmin"] - r["amin"]) for r in v), 3),
                            "ptsMAE": round(statistics.mean(abs(r["proj"] - r["act"]) for r in v if r["m"] == "PTS"), 3)}
                        for k, v in sorted(months.items())}}


if __name__ == "__main__":
    main()
