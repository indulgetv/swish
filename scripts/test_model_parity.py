"""Checks scripts/model.py gives the same picks as the website (index.html) on data/live.json.
Run: python3 scripts/test_model_parity.py   (needs: pip install playwright && playwright install chromium)"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(Path(__file__).parent))
import model

ROOT = Path(__file__).resolve().parent.parent
live = json.loads((ROOT / "data/live.json").read_text())
py = {(p["player"], p["market"]): p for p in model.build_picks(live)}
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page()
    pg.route("https://**", lambda r: r.abort())
    pg.goto((ROOT / "index.html").as_uri()); pg.wait_for_timeout(800)
    js = pg.evaluate("""ALL.map(p=>({player:p.player,market:p.market,line:p.line,over:p.over,under:p.under,projection:p.projection,sd:p.sd,
        pureO:p.pureO,modelO:p.modelO,side:p.side,edge:p.edge,value:p.value,nflags:p.flags.length}))""")
    b.close()
bad, worst = [], 0
for j in js:
    p = py.get((j["player"], j["market"]))
    if not p:
        bad.append(("missing in python", j["player"], j["market"])); continue
    for k in ("line", "over", "under"):
        if p[k] != j[k]: bad.append((k, j["player"], j["market"], p[k], j[k]))
    for k in ("projection", "sd", "pureO", "modelO", "edge"):
        d = abs(p[k] - j[k]); worst = max(worst, d)
        if d > 1e-3: bad.append((k, j["player"], j["market"], p[k], j[k]))
    if p["side"] != j["side"] or p["value"] != j["value"] or len(p["flags"]) != j["nflags"]:
        bad.append(("side/value/flags", j["player"], j["market"], p["side"], j["side"], p["value"], j["value"], p["flags"], j["nflags"]))
extra = set(py) - {(j["player"], j["market"]) for j in js}
print(f"website props: {len(js)}  python props: {len(py)}  extra in python: {len(extra)}  largest number difference: {worst:.2e}")
print("MISMATCHES:", len(bad)); [print(" ", x) for x in bad[:15]]
sys.exit(1 if bad or extra else 0)
