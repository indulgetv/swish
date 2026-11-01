"""Check saved, graded picks: where does the model beat or lose to the market?
Run: python3 lab/check_picks.py"""
import json, glob, math, random, collections, os
HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(1)
ps = []
for f in sorted(glob.glob(os.path.join(HERE, '..', 'data', 'picks', '2026-*.json'))):
    for p in json.load(open(f))['picks'].values():
        if p.get('went') in ('over', 'under') and p.get('pureO') is not None and p.get('mktO') is not None:
            p['y'] = 1 if p['went'] == 'over' else 0
            ps.append(p)
N = len(ps)
lg = lambda x: math.log(x / (1 - x))
sg = lambda z: 1 / (1 + math.exp(-z))
cl = lambda x: min(max(x, 1e-4), 1 - 1e-4)
st = lambda x: sg(0.7 * lg(cl(x)))
def brier(rows, key): return sum((key(p) - p['y']) ** 2 for p in rows) / len(rows)

print(f'graded with probs: {N}, games: {len(set(p["game"] for p in ps))}')

# 1. overall
def report(rows, label):
    if len(rows) < 15: return
    bm = brier(rows, lambda p: p['mktO']); bp = brier(rows, lambda p: p['pureO'])
    bs = brier(rows, lambda p: st(p['pureO'])); bb = brier(rows, lambda p: p['modelO'])
    ov = sum(p['y'] for p in rows) / len(rows)
    mk = sum(p['mktO'] for p in rows) / len(rows); md = sum(p['pureO'] for p in rows) / len(rows)
    print(f'{label:32s} n={len(rows):4d} overs hit {ov:.1%} | mkt said {mk:.1%} model said {md:.1%} | '
          f'Brier mkt {bm:.4f} model {bp:.4f} stretched {bs:.4f} SWISH {bb:.4f} | model-mkt {bp-bm:+.4f}')

report(ps, 'ALL')
print('\n-- by market')
for m in ('PTS', 'REB', 'AST'): report([p for p in ps if p['market'] == m], m)
print('\n-- by version')
for v in sorted(set(p['modelVersion'] for p in ps)): report([p for p in ps if p['modelVersion'] == v], v)

# 2. disagreement buckets
print('\n-- where model disagrees with market (model over% minus market over%)')
bk = [(-1, -.10), (-.10, -.05), (-.05, -.02), (-.02, .02), (.02, .05), (.05, .10), (.10, 1)]
for a, b in bk:
    r = [p for p in ps if a <= p['pureO'] - p['mktO'] < b]
    if not r: continue
    ov = sum(p['y'] for p in r) / len(r); mk = sum(p['mktO'] for p in r) / len(r); md = sum(p['pureO'] for p in r) / len(r)
    print(f'  {a:+.2f}..{b:+.2f}  n={len(r):4d}  market said {mk:.1%}  model said {md:.1%}  actually {ov:.1%}  -> closer: {"MODEL" if abs(md-ov)<abs(mk-ov) else "market"}')

# 3. optimal blend weight on raw model (logistic fit: y ~ a + b*logit(mkt) + c*logit(model))
def fit(rows, iters=0):
    best=None
    for wi in range(-10, 21):
        w=wi/20
        for ci in range(-6,7):
            c=ci/40
            L=0
            for p in rows:
                q=sg(c+(1-w)*lg(cl(p['mktO']))+w*lg(cl(p['pureO'])))
                L-= math.log(q if p['y'] else 1-q)
            if best is None or L<best[0]: best=(L,w,c)
    return [best[2], 1-best[1], best[1]]
w = fit(ps)
print(f'\n-- best-fit mix (log-odds): over-bias shift {w[0]:+.3f}, market share {w[1]:.2f}, model share {w[2]:.2f}')
games = sorted(set(p['game'] for p in ps)); byg = collections.defaultdict(list)
for p in ps: byg[p['game']].append(p)
bs = []
for _ in range(60):
    rows = [p for g in random.choices(games, k=len(games)) for p in byg[g]]
    bs.append(fit(rows)[2])
bs.sort()
print(f'   model weight 90% range (resampling whole games): {bs[3]:+.2f} .. {bs[56]:+.2f}')

# 4. flags / situations
print('\n-- situations')
sit = {
    'no flags': lambda p: not p['flags'],
    'injury news after line': lambda p: 'injury_after_line' in p['flags'],
    'few games': lambda p: 'few_games' in p['flags'],
    'big gap': lambda p: 'big_gap' in p['flags'],
    'minutes boost (teammate out)': lambda p: (p.get('minBoost') or 0) > 0,
    'new role (roleDelta)': lambda p: (p.get('roleDelta') or 0) != 0,
    'new starter tonight': lambda p: p.get('starterTonight'),
    'back from absence': lambda p: p.get('back'),
    'exp min < 24': lambda p: (p.get('minutes') or 0) < 24,
    'exp min 24-32': lambda p: 24 <= (p.get('minutes') or 0) < 32,
    'exp min 32+': lambda p: (p.get('minutes') or 0) >= 32,
    'line low (<=6.5)': lambda p: p['line'] <= 6.5,
    'normal dist (PTS)': lambda p: p['dist'] == 'normal',
    'count dist (REB/AST)': lambda p: p['dist'] == 'count',
}
for k, f in sit.items(): report([p for p in ps if f(p)], k)

# 5. projection bias
print('\n-- projection bias (projection minus actual; + = projects too high)')
for m in ('PTS', 'REB', 'AST'):
    r = [p for p in ps if p['market'] == m]
    pb = sum(p['projection'] - p['actual'] for p in r) / len(r); lb = sum(p['line'] - p['actual'] for p in r) / len(r)
    pm = sum(abs(p['projection'] - p['actual']) for p in r) / len(r); lm = sum(abs(p['line'] - p['actual']) for p in r) / len(r)
    print(f'  {m}: model bias {pb:+.2f}, line bias {lb:+.2f} | avg miss model {pm:.2f}, line {lm:.2f}')
r = [p for p in ps if p.get('minutesPlayed') is not None]
if r:
    mb = sum(p['minutes'] - p['minutesPlayed'] for p in r) / len(r)
    print(f'  minutes: expected minus played {mb:+.2f} (n={len(r)})')
    for lo, hi in ((0, 20), (20, 28), (28, 34), (34, 60)):
        rr = [p for p in r if lo <= p['minutes'] < hi]
        if rr: print(f'     exp {lo}-{hi}: n={len(rr)} bias {sum(p["minutes"]-p["minutesPlayed"] for p in rr)/len(rr):+.2f}')

# 6. the model's high-confidence calls
print('\n-- model alone very sure (raw over% <35% or >65%)')
report([p for p in ps if p['pureO'] > .65], 'model says over >65%')
report([p for p in ps if p['pureO'] < .35], 'model says over <35%')

# 7. line moves: did the market move toward the model?
mv = [p for p in ps if p.get('openLine') is not None and p['openLine'] != p['line']]
tw = sum(1 for p in mv if (p['line'] - p['openLine']) * (p['pureO'] - p['mktO']) > 0)
print(f'\n-- line moved after first save: {len(mv)}, moved toward model: {tw}')
