"""Usage: BLOWOUT_FROM=9 BLOWOUT_A=0.25 TB_REB=0.5 TB_AST=0.5 python3 lab/backtest_saved.py [model.py]
Needs history: git fetch --depth=3000 origin main.  """
"""Saved-picks backtest: re-run each graded pick on the last live.json before its tip, with base and variant models."""
import json, glob, subprocess, os, sys, importlib.util, statistics as st
from datetime import datetime
R = '/home/claude/swish'; S = os.path.dirname(os.path.abspath(__file__))
def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
base = load('m_base', f'{R}/scripts/model.py')
var = load('m_var', sys.argv[1] if len(sys.argv) > 1 else f'{R}/lab/model_gameline_test.py')
commits = []
for ln in subprocess.run(['git', '-C', R, 'log', 'origin/main', '--format=%h %cI', '--', 'data/live.json'], capture_output=True, text=True).stdout.split('\n'):
    if ln: h, t = ln.split(); commits.append((datetime.fromisoformat(t), h))
commits.sort()
picks = []
for f in sorted(glob.glob(f'{R}/data/picks/2026-*.json')):
    for p in json.load(open(f))['picks'].values():
        if p.get('went') in ('over', 'under'): picks.append(p)
cache = {}
def run(h, gid):
    if h not in cache:
        live = json.loads(subprocess.run(['git', '-C', R, 'show', f'{h}:data/live.json'], capture_output=True, text=True).stdout)
        cache[h] = ({(x['game'], x['player'], x['market']): x for x in base.build_picks(live)},
                    {(x['game'], x['player'], x['market']): x for x in var.build_picks(live)})
    return cache[h]
out = []
for p in picks:
    tip = datetime.fromisoformat(p['tipoff'].replace('Z', '+00:00'))
    before = [h for t, h in commits if t < tip]
    if not before: continue
    b, v = run(before[-1], p['game'])
    k = (p['game'], p['player'], p['market'])
    if k not in b or k not in v: continue
    out.append((p, b[k], v[k]))
print(f'matched {len(out)} of {len(picks)} graded picks, snapshots {len(cache)}')
def grade(x, actual):
    if actual == x['line']: return None
    went = 'over' if actual > x['line'] else 'under'
    return went
def summ(idx, label):
    res = {'strong': [0, 0, 0.0], 'all': [0, 0, 0.0]}; bm = bp = bs = n = 0; gaps = []
    for p, *xs in out:
        x = xs[idx]; went = grade(x, p['actual'])
        if went is None: continue
        y = 1 if went == 'over' else 0; n += 1
        bm += (x['mktO'] - y) ** 2; bp += (x['pureO'] - y) ** 2; bs += (x['modelO'] - y) ** 2
        pr = base.american_to_decimal(x['price']); win = x['side'] == went
        for key in (['all', 'strong'] if x['verdict'] == 'strong' else ['all']):
            res[key][0 if win else 1] += 1; res[key][2] += 10 * (pr - 1) if win else -10
        gaps.append(abs(x['pureO'] - x['mktO']))
    print(f'{label:8s} n={n} Brier market {bm/n:.5f} model {bp/n:.5f} SWISH {bs/n:.5f} | model-mkt {(bp-bm)/n:+.5f} | '
          f'strong {res["strong"][0]}-{res["strong"][1]} £{res["strong"][2]:+.2f} | all {res["all"][0]}-{res["all"][1]} £{res["all"][2]:+.2f} | '
          f'gap>10pts {sum(g>0.10 for g in gaps)}')
summ(0, 'v1.8'); summ(1, 'variant')
ch = [(p, b, v) for p, b, v in out if abs(b['projection'] - v['projection']) > 1e-9]
print(f'projections changed: {len(ch)}')
if ch:
    mb = st.mean(abs(b['projection'] - p['actual']) for p, b, v in ch); mv = st.mean(abs(v['projection'] - p['actual']) for p, b, v in ch)
    lm = st.mean(abs(b['line'] - p['actual']) for p, b, v in ch)
    mn = [(p, b, v) for p, b, v in ch if p.get('minutesPlayed')]
    print(f'  on changed: proj miss {mb:.3f} -> {mv:.3f} (line {lm:.3f}); minutes miss {st.mean(abs(b["minutes"]-p["minutesPlayed"]) for p,b,v in mn):.3f} -> {st.mean(abs(v["minutes"]-p["minutesPlayed"]) for p,b,v in mn):.3f}')
    for m in ('PTS', 'REB', 'AST'):
        c = [(p, b, v) for p, b, v in ch if p['market'] == m]
        if c: print(f'  {m}: n={len(c)} proj miss {st.mean(abs(b["projection"]-p["actual"]) for p,b,v in c):.3f} -> {st.mean(abs(v["projection"]-p["actual"]) for p,b,v in c):.3f}')
flips = [(p, b, v) for p, b, v in out if b['verdict'] != v['verdict'] and 'strong' in (b['verdict'], v['verdict'])]
for p, b, v in flips: print(f'  strong change: {p["player"]} {p["market"]} {b["side"]} {b["line"]} actual {p["actual"]}: {b["verdict"]} -> {v["verdict"]}')
