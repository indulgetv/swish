"""Quick post-slate review of graded picks.

Usage:  python scripts/review.py 2026-10-28      (defaults to every file in data/picks)

Prints: record and profit by game, by side (over/under) and by market; projection bias (actual minus
projection / minus line); minutes error; hit rate by edge size; Brier score for model-only, market and
the SWISH blend; and every strong pick with its result. Read-only — it never changes any data.
"""
import glob
import json
import os
import statistics as st
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(slates):
    files = [os.path.join(ROOT, "data", "picks", f"{s}.json") for s in slates] if slates else \
        sorted(glob.glob(os.path.join(ROOT, "data", "picks", "*.json")))
    picks = []
    for f in files:
        with open(f) as fh:
            picks += list(json.load(fh)["picks"].values())
    return picks


def rec(xs):
    w = sum(x["result"] == "win" for x in xs)
    l = sum(x["result"] == "loss" for x in xs)
    pnl = sum(x.get("profit") or 0 for x in xs)
    hit = f"{w / (w + l):.1%}" if w + l else "-"
    return f"{w}-{l} ({hit})  £{pnl:+.2f}"


def main():
    picks = load(sys.argv[1:])
    g = [x for x in picks if x.get("result") in ("win", "loss")]
    pending = [x for x in picks if x.get("result") not in ("win", "loss", "push", "void")]
    print(f"picks {len(picks)} · graded {len(g)} · pending {len(pending)}")
    if not g:
        return

    print("\n== by game")
    by = defaultdict(list)
    for x in g:
        by[f"{x['away']}@{x['home']}"].append(x)
    for k, xs in sorted(by.items(), key=lambda kv: sum(x["profit"] for x in kv[1])):
        print(f"  {k:9} {rec(xs)}")

    print("\n== by verdict / side / market")
    for v in ("strong", "some", "slight", "check", "none"):
        xs = [x for x in g if x["verdict"] == v]
        if xs:
            print(f"  {v:7} {rec(xs)}")
    for s in ("over", "under"):
        print(f"  {s:7} {rec([x for x in g if x['side'] == s])}")
    print(f"  results went over {sum(x['went'] == 'over' for x in g) / len(g):.1%} of the time")
    for m in sorted({x["market"] for x in g}):
        xs = [x for x in g if x["market"] == m]
        sides = Counter(x["side"] for x in xs)
        print(f"  {m:4} {rec(xs)}  act-proj {st.mean(x['actual'] - x['projection'] for x in xs):+.2f}"
              f"  act-line {st.mean(x['actual'] - x['line'] for x in xs):+.2f}"
              f"  MAE ours {st.mean(abs(x['actual'] - x['projection']) for x in xs):.2f}"
              f" vs line {st.mean(abs(x['actual'] - x['line']) for x in xs):.2f}"
              f"  picked over/under {sides['over']}/{sides['under']}")

    mp = [x for x in g if x.get("minutesPlayed") is not None]
    if mp:
        err = [x["minutesPlayed"] - x["minutes"] for x in mp]
        print(f"\n== minutes: mean error {st.mean(err):+.1f}, MAE {st.mean(abs(e) for e in err):.1f}")

    print("\n== hit rate by edge")
    for lo, hi in ((0, .02), (.02, .04), (.04, .06), (.06, 1)):
        xs = [x for x in g if lo <= x["edge"] < hi]
        if xs:
            print(f"  {lo:.2f}-{hi:.2f}  n={len(xs):3}  {rec(xs)}")

    print("\n== Brier (lower is better)")
    for name, key in (("model only", "pureO"), ("market", "mktO"), ("SWISH blend", "modelO")):
        print(f"  {name:11} {st.mean((x[key] - (x['went'] == 'over')) ** 2 for x in g):.4f}")

    print("\n== strong picks")
    for x in sorted([x for x in g if x["verdict"] == "strong"], key=lambda x: (x["market"], x["player"])):
        print(f"  {x['player'][:22]:22} {x['market']:3} {x['side']:5} line {x['line']:5} proj {x['projection']:5.1f}"
              f" actual {x['actual']:>4}  {x['result']:4}  min {x['minutes']}→{x.get('minutesPlayed')}")


if __name__ == "__main__":
    main()
