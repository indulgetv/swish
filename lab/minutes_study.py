"""Minutes study: where projected minutes go wrong, and whether flat fixes hold across seasons.
First: python3 lab/replay.py --season 2026 --lineups --dump DIR/d26.json; --season 2025 --lineups --dump DIR/d25.json; --season 2026 --dump DIR/d26n.json. Run: python3 lab/minutes_study.py DIR"""
import json,gzip,sys,statistics as S,collections as C,random
ROOT='/home/claude/swish/lab/data/'; SP=sys.argv[1]
NOT=("COACH","DECISION","G LEAGUE","TWO-WAY","NOT WITH TEAM","SUSPEN","PERSONAL","TRADE")
def ctx(season):
    G=sorted(json.load(gzip.open(ROOT+f'season-{season}.json.gz','rt'))['games'],key=lambda g:g['tipoff'] or g['date'])
    H=C.defaultdict(list); lastdate={}; lastplay={}; out={}
    from datetime import date
    for g in G:
        d=date.fromisoformat(g['date'])
        margin=abs((g.get('awayScore') or 0)-(g.get('homeScore') or 0))
        for side in('away','home'):
            t=g[side]; P=[p for p in g['players'] if p['team']==t]
            tm=sum(float(p.get('min') or 0) for p in P); ot=tm>=262
            b2b=t in lastdate and (d-lastdate[t]).days==1
            prev=lastplay.get(t,set())
            avg=lambda p:(S.mean(H[p['id']][:10]) if H[p['id']] else 0)
            newout=[p for p in P if p.get('dnp') and not any(k in (p.get('reason')or'').upper() for k in NOT) and p['id'] in prev and avg(p)>=20]
            back=[p for p in P if (p.get('min')or 0)>0 and p['id'] not in prev and avg(p)>=20 and prev]
            for p in P:
                if (p.get('min') or 0)>0:
                    out[(g['id'],p['name'])]=dict(margin=margin,ot=ot,b2b=b2b,newout=len(newout),starback=len([x for x in back if x['id']!=p['id']]),selfback=p['id'] not in prev and bool(prev),started=bool(p.get('starter')),pf=p.get('PF')or 0,seas=season,avg=avg(p),hist=len(H[p['id']]))
            lastdate[t]=d; lastplay[t]={p['id'] for p in P if (p.get('min')or 0)>0}
        for p in g['players']:
            if (p.get('min') or 0)>0:H[p['id']].insert(0,float(p['min']))
    return out
def load(f,season):
    R=json.load(open(SP+f)); c=ctx(season); rows=[]
    for r in R:
        if not r['played']:continue
        k=(r['g'],r['p'])
        if k not in c:continue
        r.update(c[k]);rows.append(r)
    return rows
R=load('/d26.json',2026)+load('/d25.json',2025)
Rn=load('/d26n.json',2026)
print('rows',len(R))
P=[r for r in R if r['m']=='PTS']
def mm(z):
    e=[r['amin']-r['pmin'] for r in z];return f"n={len(z):6d} MAE {S.mean(map(abs,e)):.2f} bias(actual-proj) {S.mean(e):+.2f}"
print('ALL',mm(P)); 
print('share of total abs minutes error:')
tot=sum(abs(r['amin']-r['pmin']) for r in P)
def show(nm,z):print(f"{nm:34s}",mm(z),'errShare %.1f%%'%(100*sum(abs(r['amin']-r['pmin']) for r in z)/tot),'pop %.1f%%'%(100*len(z)/len(P)))
for lo,hi in[(0,15),(15,20),(20,25),(25,30),(30,34),(34,99)]:show(f'proj {lo}-{hi}',[r for r in P if lo<=r['pmin']<hi])
for s,f in[('blowout 25+ final margin',lambda r:r['margin']>=25),('margin 15-24',lambda r:15<=r['margin']<25),('margin 6-14',lambda r:6<=r['margin']<15),('margin 0-5',lambda r:r['margin']<6 and not r['ot']),('overtime',lambda r:r['ot']),
 ('back-to-back',lambda r:r['b2b']),('not b2b',lambda r:not r['b2b']),
 ('20+min teammate newly out',lambda r:r['newout']>0),('none newly out',lambda r:r['newout']==0),
 ('20+min teammate returned',lambda r:r['starback']>0),('none returned',lambda r:r['starback']==0),
 ('player himself returning',lambda r:r['selfback']),('fouled out/5+ fouls',lambda r:r['pf']>=5),
 ('started',lambda r:r['started']),('bench',lambda r:not r['started']),
 ('new starter (sub->start)',lambda r:r['starter']),('minutes boosted',lambda r:r['boost']>0),
 ('this-season games<5',lambda r:r['curG']<5),('games 5-19',lambda r:5<=r['curG']<20),('games 20+',lambda r:r['curG']>=20)]:
    show(s,[r for r in P if f(r)])
# big misses
big=[r for r in P if abs(r['amin']-r['pmin'])>=8];print('8+min misses',len(big),'%.1f%%'%(100*len(big)/len(P)),'errShare %.1f%%'%(100*sum(abs(r['amin']-r['pmin']) for r in big)/tot),'under-proj',sum(r['amin']>r['pmin'] for r in big))
Bg=C.Counter()
for r in big:
    why='blowout' if r['margin']>=20 else 'OT' if r['ot'] else 'teammate out' if r['newout'] else 'teammate back' if r['starback'] else 'fouls' if r['pf']>=5 else 'self back' if r['selfback'] else 'b2b' if r['b2b'] else 'unexplained'
    Bg[why]+=1
print({k:round(100*v/len(big),1) for k,v in Bg.most_common()})
# ceiling: how much stat error comes from minutes
print('\nIf minutes were perfect (proj rate x actual min):')
for m in('PTS','REB','AST'):
    z=[r for r in R if m==r['m'] and r['pmin']>0]
    a=S.mean(abs(r['act']-r['proj']) for r in z); b=S.mean(abs(r['act']-r['proj']*r['amin']/r['pmin']) for r in z)
    print(m,len(z),'MAE now %.3f perfect-min %.3f gain %.1f%%'%(a,b,100*(a-b)/a))
# half-way ceiling: 25% lower minutes error
print('blowouts excluded PTS MAE',round(S.mean(abs(r['act']-r['proj']) for r in P if r['margin']<20),3),'all',round(S.mean(abs(r['act']-r['proj']) for r in P),3))
# lineups value
Pn=[r for r in Rn if r['m']=='PTS']; P26=[r for r in P if r['seas']==2026]
print('season26 lineups',mm(P26));print('season26 no-lineups',mm(Pn))
# consistency across seasons for key subgroups
for s in(2025,2026):
    Z=[r for r in P if r['seas']==s]
    print(s,'b2b',mm([r for r in Z if r['b2b']]),'| newout',mm([r for r in Z if r['newout']>0]),'| back',mm([r for r in Z if r['starback']>0]))
# rate error by subgroup: rate bias PTS with teammate out
for s,f in[('newout',lambda r:r['newout']>0),('none',lambda r:r['newout']==0),('back',lambda r:r['starback']>0),('b2b',lambda r:r['b2b'])]:
    z=[r for r in P if f(r) and r['amin']>=5 and r['pmin']>0]
    bias=S.mean((r['act']/r['amin'])-(r['proj']/r['pmin']) for r in z);print('PTS per-min rate',s,len(z),'bias %+.4f per min => %+.2f pts/30min'%(bias,bias*30))
print('\nCROSS-SEASON TEST: learn shift on one season, apply to the other')
G={'teammate returned':lambda r:r['starback']>0,'teammate newly out':lambda r:r['newout']>0,'new starter':lambda r:r['starter'],'high-min 34+':lambda r:r['pmin']>=34}
def ev(train,test,keys):
    sh={k:S.mean(r['amin']-r['pmin'] for r in train if G[k](r)) for k in keys}
    def adj(r):
        return max(1,r['pmin']+sum(sh[k] for k in keys if G[k](r)))
    Z=[r for r in test if r['pmin']>0]
    ch=[r for r in Z if any(G[k](r) for k in keys)]
    a=S.mean(abs(r['amin']-r['pmin']) for r in Z);b=S.mean(abs(r['amin']-adj(r)) for r in Z)
    res={}
    for m in('PTS','REB','AST'):
        q=[r for r in test if r['m']==m and r['pmin']>0]
        res[m]=(round(S.mean(abs(r['act']-r['proj']) for r in q),3),round(S.mean(abs(r['act']-r['proj']*adj(r)/r['pmin']) for r in q),3))
    return {k:round(v,2) for k,v in sh.items()},round(a,3),round(b,3),len(ch),res
A=[r for r in R if r['seas']==2025];B=[r for r in R if r['seas']==2026]
PA=[r for r in A if r['m']=='PTS']; 
for keys in (['teammate returned'],['teammate newly out'],['new starter'],['teammate returned','teammate newly out','new starter']):
    for tr,te,l in((A,B,'25->26'),(B,A,'26->25')):
        print(l,keys,ev([r for r in tr if r['m']=='PTS'],te,keys) if False else '',end='')
        sh,a,b,n,res=ev([r for r in tr if r['m']=='PTS'],[r for r in te],keys)
        print(sh,'minMAE(all markets rows)',a,'->',b,'changed',n,res)
# usage rate test: +rate when teammate newly out
for tr,te,l in((A,B,'25->26'),(B,A,'26->25')):
    q=[r for r in tr if r['m']=='PTS' and r['newout']>0 and r['amin']>=5 and r['pmin']>0]
    k=S.mean(r['act']/r['amin'] for r in q)/S.mean(r['proj']/r['pmin'] for r in q)
    t=[r for r in te if r['m']=='PTS' and r['newout']>0]
    print(l,'usage mult %.3f'%k,'PTS MAE on those',round(S.mean(abs(r['act']-r['proj']) for r in t),3),'->',round(S.mean(abs(r['act']-r['proj']*k) for r in t),3),'n',len(t))
