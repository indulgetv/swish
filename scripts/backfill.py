"""One-off: rebuild a slate's picks from data snapshots saved (in git history) BEFORE each game tipped off.
Each game uses the newest snapshot written before its tip-off. Picks are marked backfilled=True.
Usage: python3 scripts/backfill.py COMMIT [COMMIT ...]"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import ledger, model

ROOT = Path(__file__).resolve().parent.parent
snaps = []
for c in sys.argv[1:]:
    live = json.loads(subprocess.check_output(["git", "-C", str(ROOT), "show", f"{c}:data/live.json"]))
    snaps.append((model.parse_ts(live["meta"]["writtenAt"]), c, live))
snaps.sort(key=lambda s: s[0])
games = {g["id"]: g for s in snaps for g in s[2]["games"]}
for gid, g in games.items():
    tip = model.parse_ts(g["tipoff"])
    before = [s for s in snaps if s[0] < tip]
    if not before:
        print(f"{g['away']} @ {g['home']}: no snapshot before tip-off — skipped"); continue
    at, c, live = before[-1]
    r = ledger.upsert(live, ROOT / "data", now=at, backfilled=True, games_filter={gid})
    print(f"{g['away']} @ {g['home']} (tip {g['tipoff']}): snapshot {c} written {live['meta']['writtenAt']} -> {r['saved']} picks")
ledger.write_results(ROOT / "data")
