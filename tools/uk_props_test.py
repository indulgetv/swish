"""One-off check (1 credit): do UK bookmakers on The Odds API offer NBA player points props?
Picks the next game that hasn't started, asks for regions=uk, markets=player_points, and saves
which bookmakers answered and how many lines each had. The API key comes from the environment
and is never written anywhere."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE = "https://api.the-odds-api.com/v4/sports/basketball_nba"
KEY = os.environ.get("ODDS_API_KEY", "")
if not KEY: sys.exit("ODDS_API_KEY missing")

def get(url, params):
    q = urllib.parse.urlencode({**params, "apiKey": KEY})
    with urllib.request.urlopen(f"{url}?{q}", timeout=30) as r:
        return json.load(r), {k.lower(): v for k, v in r.headers.items()}

now = datetime.now(timezone.utc)
events, _ = get(f"{BASE}/events", {})            # the events list costs 0 credits
upcoming = sorted((e for e in events if datetime.fromisoformat(e["commence_time"].replace("Z", "+00:00")) > now),
                  key=lambda e: e["commence_time"])
out = {"checkedAt": now.isoformat(timespec="seconds"), "region": "uk", "market": "player_points"}
if not upcoming:
    out["result"] = "no upcoming games — nothing spent"
else:
    ev = upcoming[0]
    data, hdr = get(f"{BASE}/events/{ev['id']}/odds", {"regions": "uk", "markets": "player_points", "oddsFormat": "decimal"})
    books = []
    for b in data.get("bookmakers", []):
        outs = [o for m in b.get("markets", []) for o in m.get("outcomes", [])]
        books.append({"key": b["key"], "title": b["title"], "outcomes": len(outs),
                      "players": len({o.get("description") for o in outs}),
                      "sample": [{k: o.get(k) for k in ("description", "name", "point", "price")} for o in outs[:4]]})
    out.update({"game": f"{ev['away_team']} @ {ev['home_team']}", "tipoff": ev["commence_time"],
                "bookmakers": books, "result": "UK player points found" if books else "no UK bookmaker returned player points",
                "creditsUsed": hdr.get("x-requests-last"), "creditsRemaining": hdr.get("x-requests-remaining")})
os.makedirs("data", exist_ok=True)
json.dump(out, open("data/uk-props-test.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "bookmakers"}, indent=1))
for b in out.get("bookmakers", []): print(b["title"], b["players"], "players,", b["outcomes"], "outcomes")
