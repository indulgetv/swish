"""SWISH lab — "minutes when a star sits" (1 Nov 2026).

Question: when a 25+ minute regular is NEWLY out (played his team's last game, now out injured), do his teammates
really play more than SWISH projected? By role (top-5 projected minutes = "starter role" vs bench) and position.

Input: replay dumps (python3 lab/replay.py --dump FILE) + the season file. Each teammate is counted once per game
(PTS rows). Residual = actual minutes − SWISH's projected minutes. Compared with ordinary nights (nobody newly out).

Run:  python3 lab/star_out_minutes.py <season> <dump.json>
"""
import gzip, json, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOT_INJURY = ("COACH", "DECISION", "G LEAGUE", "TWO-WAY", "NOT WITH TEAM", "SUSPEN", "PERSONAL", "TRADE")
KEY = 25


def grp(pos):
    u = (pos or "").upper()
    return "C" if u.startswith("C") else "G" if "G" in u else "F" if "F" in u else "?"


def newly_out(season):
    """(game id, team) → list of (name, his avg min last 10, pos group) for 25+ min regulars newly out injured"""
    games = sorted(json.load(gzip.open(ROOT / f"lab/data/season-{season}.json.gz", "rt"))["games"], key=lambda g: g["tipoff"] or g["date"])
    hist = defaultdict(list)          # player id → minutes, newest first
    last_game = {}                    # team → set of player ids who played in its previous game
    res = {}
    for g in games:
        for side in ("away", "home"):
            t = g[side]
            prev = last_game.get(t, set())
            for p in g["players"]:
                if p["team"] != t or not p.get("dnp"):
                    continue
                if any(k in (p.get("reason") or "").upper() for k in NOT_INJURY):
                    continue
                h = hist[p["id"]][:10]
                if p["id"] in prev and len(h) >= 5 and statistics.mean(h) >= KEY:
                    res.setdefault((g["id"], t), []).append((p["name"], statistics.mean(h), grp(p.get("pos"))))
        for side in ("away", "home"):
            last_game[g[side]] = {p["id"] for p in g["players"] if p["team"] == g[side] and (p.get("min") or 0) > 0}
        for p in g["players"]:
            if (p.get("min") or 0) > 0:
                hist[p["id"]].insert(0, p["min"])
    pos = {p["name"]: grp(p.get("pos")) for g in games for p in g["players"]}
    return res, pos


def main(season, dump):
    outs, pos = newly_out(season)
    rows = [r for r in json.load(open(dump)) if r["m"] == "PTS" and r["played"]]
    by_tg = defaultdict(list)
    for r in rows:
        by_tg[(r["g"], r["t"])].append(r)
    buckets = defaultdict(list)
    team_sum = defaultdict(list)
    for (g, t), rs in by_tg.items():
        o = outs.get((g, t))
        kind = "star out" if o else "normal"
        top5 = {r["p"] for r in sorted(rs, key=lambda r: -r["pmin"])[:5]}
        ogrps = {x[2] for x in o} if o else set()
        team_sum[kind].append(sum(r["pmin"] for r in rs))
        for r in rs:
            role = "top-5" if r["p"] in top5 else "bench"
            same = "same pos" if pos.get(r["p"]) in ogrps else "other pos"
            res = r["amin"] - r["pmin"]
            buckets[(kind, "all")].append(res)
            buckets[(kind, role)].append(res)
            if o:
                buckets[(kind, role + ", " + same)].append(res)
                buckets[(kind, "boosted by model" if r["boost"] > 0 else "no model boost")].append(res)
    print(f"season {season}: {sum(1 for _ in outs)} team-games with a 25+ min regular newly out")
    print(f"{'group':38} {'n':>6} {'actual − projected min':>24}")
    for k in sorted(buckets):
        v = buckets[k]
        print(f"{k[0] + ' · ' + k[1]:38} {len(v):6} {statistics.mean(v):+24.2f}")
    for k, v in team_sum.items():
        print(f"projected team minutes (players with props), {k}: {statistics.mean(v):.1f}")


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
