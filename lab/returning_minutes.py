"""SWISH lab: player-specific minutes when an injured teammate returns (5 Nov 2026).

For a teammate T of a returning regular R, uses only earlier games this season:
  A: delta = T's average minutes in up to 10 games with R - T's model basis (0.5*last3 + 0.5*last10)
  B: delta = (T with R - T without R, last 15 team games) * share of T's basis that came from games without R
Adjusted minutes = projected + alpha * n/(n+K) * delta, capped at -10/+4. Rows are rescaled by minutes.
Returners come from the box score, so the replay knows who really came back: this flatters the idea.
Settings are chosen on one season and tested on the other. Run: python3 lab/returning_minutes.py DIR
DIR holds replay dumps d25.json, d26.json (and d26n.json without lineups) from lab/replay.py --dump."""
import gzip, json, random, statistics as S, sys
from collections import defaultdict
ROOT = '/home/claude/swish/lab/data/'; SP = sys.argv[1]
NOT = ("COACH", "DECISION", "G LEAGUE", "TWO-WAY", "NOT WITH TEAM", "SUSPEN", "PERSONAL", "TRADE")
GRID = [(v, k, a) for v in 'AB' for k in (0, 3, 6, 12) for a in (0.25, 0.5, 0.75, 1.0)]
MINR = 20


def features(season):
    """(game id, player name) -> list of per-returner evidence, known before that game apart from who returned"""
    games = sorted(json.load(gzip.open(ROOT + f'season-{season}.json.gz', 'rt'))['games'], key=lambda g: g['tipoff'] or g['date'])
    th = defaultdict(list)                 # team -> earlier games, newest first: {name: minutes}
    out = {}
    for g in games:
        for side in ('away', 'home'):
            t = g[side]; P = [p for p in g['players'] if p['team'] == t]
            tonight = {p['name']: float(p.get('min') or 0) for p in P if (p.get('min') or 0) > 0}
            H = th[t]
            if H:
                avg = lambda n: S.mean([h[n] for h in H if n in h][:10] or [0])
                rets = [n for n in tonight if n not in H[0] and avg(n) >= MINR]
                for T in tonight:
                    ev = []
                    logs = [h for h in H if T in h]
                    if len(logs) < 5: continue
                    tl = [h[T] for h in logs]
                    basis = .5 * S.mean(tl[:3]) + .5 * S.mean(tl[:10])
                    for R in rets:
                        if R == T: continue
                        w = [h[T] for h in logs if R in h]
                        wo = [h[T] for h in logs[:15] if R not in h]
                        w15 = [h[T] for h in logs[:15] if R in h]
                        share = .5 * sum(R not in h for h in logs[:3]) / len(logs[:3]) + .5 * sum(R not in h for h in logs[:10]) / len(logs[:10])
                        ev.append(dict(a=(S.mean(w[:10]) - basis) if len(w) >= 3 else None, na=min(len(w), 10),
                                       b=(S.mean(w15) - S.mean(wo)) * share if len(w15) >= 3 and len(wo) >= 2 else None, nb=min(len(w15), len(wo))))
                    if ev: out[(g['id'], T)] = ev
            th[t].insert(0, tonight)
    return out


def load(name, season):
    f = features(season); rows = []
    for r in json.load(open(f'{SP}/{name}.json')):
        if r['played'] and r['pmin'] > 0:
            r['ev'] = f.get((r['g'], r['p'])); rows.append(r)
    return rows


def adj(r, s):
    v, k, a = s
    if not r['ev']: return r['pmin']
    d = 0
    for e in r['ev']:
        x, n = (e['a'], e['na']) if v == 'A' else (e['b'], e['nb'])
        if x is not None: d += x * n / (n + k)
    return max(1, r['pmin'] + max(-10, min(4, a * d)))


def score(rows, s):
    res = {}
    P = [r for r in rows if r['m'] == 'PTS']
    res['min'] = S.mean(abs(r['amin'] - r['pmin']) for r in P), S.mean(abs(r['amin'] - adj(r, s)) for r in P)
    C = [r for r in P if abs(adj(r, s) - r['pmin']) > 1e-9]
    res['nchanged'] = len(C)
    if C:
        res['minC'] = S.mean(abs(r['amin'] - r['pmin']) for r in C), S.mean(abs(r['amin'] - adj(r, s)) for r in C)
        res['biasC'] = S.mean(r['amin'] - r['pmin'] for r in C), S.mean(r['amin'] - adj(r, s) for r in C)
    for m in ('PTS', 'REB', 'AST'):
        q = [r for r in rows if r['m'] == m]
        res[m] = S.mean(abs(r['act'] - r['proj']) for r in q), S.mean(abs(r['act'] - r['proj'] * adj(r, s) / r['pmin']) for r in q)
    return res


def boot(rows, s, m):
    G = defaultdict(list)
    for r in rows:
        if r['m'] == m: G[r['g']].append(abs(r['act'] - r['proj'] * adj(r, s) / r['pmin']) - abs(r['act'] - r['proj']))
    k = list(G); o = []; random.seed(5)
    for _ in range(2000):
        a = c = 0
        for __ in k:
            v = G[random.choice(k)]; a += sum(v); c += len(v)
        o.append(a / c)
    o.sort(); return o[50], o[1949]


def fmt(p): return f'{p[0]:.3f}->{p[1]:.3f}'


D = {25: load('d25', 2025), 26: load('d26', 2026)}
print('rows', {k: len(v) for k, v in D.items()})
for tr, te in ((25, 26), (26, 25)):
    best = min(GRID, key=lambda s: S.mean(abs(r['amin'] - adj(r, s)) for r in D[tr] if r['m'] == 'PTS'))
    print(f'\ntrain {tr}: best {best}')
    for lbl, y in (('train', tr), ('TEST', te)):
        x = score(D[y], best)
        print(f" {lbl} {y}: minutes {fmt(x['min'])} changed {x['nchanged']} minChanged {fmt(x.get('minC',(0,0)))} bias {fmt(x.get('biasC',(0,0)))} PTS {fmt(x['PTS'])} REB {fmt(x['REB'])} AST {fmt(x['AST'])}")
    for m in ('PTS', 'REB', 'AST'): print(f'  TEST {m} change 95% range', '%+.4f %+.4f' % boot(D[te], best, m))
print('\nfull grid (minutes all rows change, PTS change) season 25 | season 26')
for s in GRID:
    a, b = score(D[25], s), score(D[26], s)
    print(s, '%+.3f %+.3f | %+.3f %+.3f' % (a['min'][1]-a['min'][0], a['PTS'][1]-a['PTS'][0], b['min'][1]-b['min'][0], b['PTS'][1]-b['PTS'][0]))
