"""
SWISH pick ledger — freezes every priced prop before tip-off, grades it the next morning,
and builds the scorecard shown on the Results page.

Files
  data/picks/YYYY-MM-DD.json   one per slate: every pick SWISH saved for that night
  data/results.json / .js      the summary the website reads (window.SWISH_RESULTS)

Rules
  * A pick is (re)saved on every run while its game hasn't started, so it always holds the
    latest pre-game line and injury picture. Once the game starts it is LOCKED and never changes.
  * "open*" fields keep the first line SWISH saw, so we can measure line movement (closing line value).
  * Grading uses the player's ESPN game log: win / loss / push against the line, or "void" if he didn't play.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import model

PICKS_DIR_NAME = "picks"
STAKE = 10.0


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _key(p):
    return f"{p['game']}|{p['player']}|{p['market']}"


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {"slate": path.stem, "picks": {}}


def _save(path: Path, doc: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False))


# ----------------------------------------------------------------------------- 1) save picks before tip-off
def upsert(live: dict, data_dir: Path, now: datetime | None = None, backfilled: bool = False,
           games_filter: set | None = None) -> dict:
    now = now or _now()
    slate = (live.get("meta") or {}).get("slateDate")
    if not slate or not live.get("games"):
        return {"saved": 0}
    path = data_dir / PICKS_DIR_NAME / f"{slate}.json"
    doc = _load(path)
    book = doc.setdefault("picks", {})

    def started(g):
        tip = model.parse_ts(g.get("tipoff"))
        return g.get("state") != "pre" or (tip is not None and tip <= now)

    open_games = {g["id"] for g in live["games"] if backfilled or not started(g)}
    if games_filter is not None:
        open_games &= games_filter
    # lock everything whose game has started
    for g in live["games"]:
        if started(g) and not backfilled:
            for k, p in book.items():
                if p["game"] == g["id"]:
                    p["locked"] = True
    fresh = {_key(p): p for p in model.build_picks(live, open_games)}
    saved = 0
    for k, p in fresh.items():
        old = book.get(k)
        if old and old.get("locked"):
            continue
        p["savedAt"] = _iso(now)
        p["backfilled"] = backfilled
        if old:
            for f in ("openLine", "openOver", "openUnder", "firstSaved"):
                p[f] = old.get(f)
        else:
            p.update(openLine=p["line"], openOver=p["over"], openUnder=p["under"], firstSaved=_iso(now))
        if backfilled:
            p["locked"] = True
        book[k] = p
        saved += 1
    # a pick that vanished before tip-off (player ruled out, line pulled) was never a live bet: drop it
    for k in [k for k, p in book.items() if p["game"] in open_games and not p.get("locked") and k not in fresh]:
        del book[k]
    doc["updated"] = _iso(now)
    _save(path, doc)
    return {"saved": saved, "file": str(path.name)}


# ----------------------------------------------------------------------------- 2) grade picks
def settle(data_dir: Path, fetch_gamelog, season: int, now: datetime | None = None, days: int = 4, log=print,
           final_ids: set | None = None) -> dict:
    """fetch_gamelog(espnId, season) -> list of games (newest first) with id / PTS / REB / AST / 3PM / PRA."""
    now = now or _now()
    pdir = data_dir / PICKS_DIR_NAME
    stats = {"graded": 0, "void": 0, "waiting": 0, "errors": 0}
    if not pdir.exists():
        return stats
    cache = {}
    for path in sorted(pdir.glob("*.json"))[-days:]:
        doc = _load(path)
        changed = False
        for p in doc.get("picks", {}).values():
            if p.get("result"):
                continue
            tip = model.parse_ts(p.get("tipoff"))
            # grade once ESPN marks the game final (or, for older slates, 3.5h after tip-off)
            if not tip or (p["game"] not in (final_ids or set()) and now < tip + timedelta(hours=3, minutes=30)):
                stats["waiting"] += 1
                continue
            pid = p.get("espnId")
            if pid not in cache:
                try:
                    cache[pid] = fetch_gamelog(pid, season) if pid else []
                except Exception as e:
                    cache[pid] = None
                    stats["errors"] += 1
                    log(f"[swish] results: game log failed for {p['player']}: {e}")
            logs = cache[pid]
            if logs is None:
                continue
            g = next((x for x in logs if str(x.get("id")) == str(p["game"])), None)
            if g is None or not (g.get("min") or 0) > 0:
                if now > tip + timedelta(hours=10):          # game long finished and he isn't in the box score
                    p.update(result="void", actual=None, settledAt=_iso(now), note="did not play")
                    stats["void"] += 1
                    changed = True
                else:
                    stats["waiting"] += 1
                continue
            actual = g.get(p["market"])
            if actual is None:
                continue
            went = "push" if actual == p["line"] else ("over" if actual > p["line"] else "under")
            res = "push" if went == "push" else ("win" if went == p["side"] else "loss")
            dec = model.american_to_decimal(p["price"])
            p.update(actual=actual, went=went, result=res, minutesPlayed=g.get("min"), settledAt=_iso(now),
                     profit=round((dec - 1) * STAKE if res == "win" else (-STAKE if res == "loss" else 0.0), 2))
            stats["graded"] += 1
            changed = True
        if changed:
            doc["updated"] = _iso(now)
            _save(path, doc)
    return stats


# ----------------------------------------------------------------------------- 3) scorecard
def _record(ps):
    w = sum(1 for p in ps if p["result"] == "win")
    l = sum(1 for p in ps if p["result"] == "loss")
    pu = sum(1 for p in ps if p["result"] == "push")
    profit = round(sum(p.get("profit", 0) for p in ps), 2)
    staked = STAKE * (w + l)
    return {"n": w + l + pu, "wins": w, "losses": l, "pushes": pu,
            "hitRate": round(w / (w + l), 4) if w + l else None,
            "profit": profit, "roi": round(profit / staked, 4) if staked else None,
            "avgPrice": round(sum(model.american_to_decimal(p["price"]) for p in ps if p["result"] != "push") / (w + l), 3) if w + l else None}


def _over_view(p):
    """the OVER side of a graded pick, as the website's "Top overs" list sees it"""
    dec = model.american_to_decimal(p["over"])
    a, line = p.get("actual"), p["line"]
    res = "win" if a > line else "loss" if a < line else "push"
    prof = round(STAKE * (dec - 1), 2) if res == "win" else (-STAKE if res == "loss" else 0.0)
    q = p["modelO"]
    tier = "high" if q >= 0.6 else "med" if q >= 0.55 else "low"
    return {"result": res, "profit": prof, "price": p["over"], "q": q, "tier": tier,
            "listed": not p.get("flags") and p["modelO"] >= p["mktO"]}


def _overs_summary(graded):
    """Does "Top overs" confidence come true? Every graded prop, judged on its over side."""
    ov = [_over_view(p) for p in graded if p.get("actual") is not None and p.get("over") is not None]
    listed = [o for o in ov if o["listed"]]
    def block(xs):
        r = _record(xs)
        r["predicted"] = round(sum(o["q"] for o in xs) / len(xs), 4) if xs else None
        return r
    return {"listed": block(listed), "allOvers": block(ov),
            "tiers": {t: block([o for o in listed if o["tier"] == t]) for t in ("high", "med", "low")}}


def summarise(data_dir: Path, now: datetime | None = None) -> dict:
    now = now or _now()
    pdir = data_dir / PICKS_DIR_NAME
    days, allp = [], []
    for path in sorted(pdir.glob("*.json")) if pdir.exists() else []:
        doc = _load(path)
        ps = list(doc.get("picks", {}).values())
        for p in ps:
            p["slate"] = path.stem
        allp += ps
        graded = [p for p in ps if p.get("result") in ("win", "loss", "push")]
        strong = [p for p in graded if p.get("value")]
        days.append({"slate": path.stem, "saved": len(ps), "games": len({p["game"] for p in ps}),
                     "graded": len(graded), "void": sum(1 for p in ps if p.get("result") == "void"),
                     "pending": sum(1 for p in ps if not p.get("result")),
                     "backfilled": any(p.get("backfilled") for p in ps),
                     "strong": _record(strong), "leans": _record([p for p in graded if p.get("lean") != "none"])})
    cum = 0.0
    for d in days:
        cum = round(cum + d["strong"]["profit"], 2)
        d["strongCumProfit"] = cum

    graded = [p for p in allp if p.get("result") in ("win", "loss", "push")]
    decided = [p for p in graded if p["result"] != "push"]
    # accuracy vs the market (Brier score: lower = better), on the OVER outcome of every graded prop
    def brier(key):
        return round(sum((p[key] - (1 if p["went"] == "over" else 0)) ** 2 for p in decided) / len(decided), 5) if decided else None
    b_mkt, b_swish, b_model = brier("mktO"), brier("modelO"), brier("pureO")
    skill = lambda b: round(1 - b / b_mkt, 4) if b is not None and b_mkt else None
    # calibration on SWISH's chance for the side it leans
    buckets = []
    for lo, hi in ((0.50, 0.53), (0.53, 0.56), (0.56, 0.60), (0.60, 0.65), (0.65, 1.01)):
        bs = [p for p in decided if lo <= p["modelP"] < hi]
        buckets.append({"from": lo, "to": min(hi, 1.0), "n": len(bs),
                        "predicted": round(sum(p["modelP"] for p in bs) / len(bs), 4) if bs else None,
                        "actual": round(sum(1 for p in bs if p["result"] == "win") / len(bs), 4) if bs else None})
    # projection accuracy: SWISH projection vs the bookmaker line as a guess of the actual stat
    acc = [p for p in graded if p.get("actual") is not None]
    mae = lambda f: round(sum(abs(f(p) - p["actual"]) for p in acc) / len(acc), 3) if acc else None
    # line movement (closing line value) — only picks whose line changed between first save and lock
    moved = [p for p in allp if p.get("locked") and p.get("openLine") is not None and p["openLine"] != p["line"]]
    toward = [p for p in moved if (p["line"] > p["openLine"]) == (p["side"] == "over")]
    by_market = {m: _record([p for p in graded if p["market"] == m and p.get("lean") != "none"]) for m in model.MARKETS}
    versions = sorted({p.get("modelVersion") for p in allp if p.get("modelVersion")})
    by_version = {v: {"strong": _record([p for p in graded if p.get("modelVersion") == v and p.get("value")]),
                      "leans": _record([p for p in graded if p.get("modelVersion") == v and p.get("lean") != "none"])} for v in versions}
    recent = sorted([p for p in allp if p.get("lean") != "none" or p.get("value")],
                    key=lambda p: (p["slate"], p.get("tipoff") or ""), reverse=True)[:80]
    keep = ("slate", "game", "away", "home", "tipoff", "player", "team", "market", "line", "side", "price", "projection",
            "modelP", "mktP", "edge", "value", "verdict", "flags", "actual", "result", "profit", "backfilled", "locked", "modelVersion")
    return {
        "generatedAt": _iso(now), "stake": STAKE, "modelVersion": model.MODEL_VERSION, "modelWeight": model.MODEL_WEIGHT,
        "since": days[0]["slate"] if days else None,
        "totals": {"saved": len(allp), "graded": len(graded), "void": sum(1 for p in allp if p.get("result") == "void"),
                   "pending": sum(1 for p in allp if not p.get("result"))},
        "strong": _record([p for p in graded if p.get("value")]),
        "leans": _record([p for p in graded if p.get("lean") != "none"]),
        "all": _record(graded),
        "accuracy": {"n": len(decided), "brierMarket": b_mkt, "brierSwish": b_swish, "brierModel": b_model,
                     "skillSwish": skill(b_swish), "skillModel": skill(b_model)},
        "calibration": buckets,
        "projection": {"n": len(acc), "maeSwish": mae(lambda p: p["projection"]), "maeLine": mae(lambda p: p["line"])},
        "clv": {"moved": len(moved), "toward": len(toward)},
        "byMarket": by_market, "byVersion": by_version, "days": days,
        "overs": _overs_summary(graded),
        "recent": [{k: p.get(k) for k in keep} for p in recent],
    }


def write_results(data_dir: Path, now: datetime | None = None) -> dict:
    res = summarise(data_dir, now)
    (data_dir / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    (data_dir / "results.js").write_text("// Generated by scripts/ledger.py — do not edit by hand.\nwindow.SWISH_RESULTS = "
                                         + json.dumps(res, separators=(",", ":"), ensure_ascii=False) + ";\n")
    return res
