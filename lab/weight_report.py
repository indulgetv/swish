"""Weight test, part 2: Brier vs market with game-clustered ranges, leans/strong per weight, implied best weight."""
import pickle,sys,random,collections as C,statistics as S
R=pickle.load(open(sys.argv[1],'rb')); WS=[0.05,0.1,0.15,0.2,0.3]
R=[r for r in R if r['actual']!=r[0.3]['line']]
print('n',len(R),'line changed from logged',sum(r['logged_line']!=r[0.3]['line'] for r in R))
ov=lambda r:1 if r['actual']>r[0.3]['line'] else 0
def dec(a):return 1+a/100 if a>0 else 1+100/abs(a)
random.seed(3)
def boot(rows,f):
    G=C.defaultdict(list)
    for r in rows:G[r['game']].append(f(r))
    k=list(G);o=[]
    for _ in range(4000):
        s=c=0
        for __ in k:
            v=G[random.choice(k)];s+=sum(v);c+=len(v)
        o.append(s/c)
    o.sort();return sum(map(sum,G.values()))/sum(map(len,G.values())),o[100],o[3899]
bm=lambda r:(r[0.3]['mktO']-ov(r))**2
bw=lambda r,w:(w*r[0.3]['pureO']+(1-w)*r[0.3]['mktO']-ov(r))**2
sl=lambda a,b:[r for r in R if a<=r['slate']<=b]
for nm,rows in [('ALL',R),('28-31 Oct',sl('2026-10-28','2026-10-31')),('1-4 Nov',sl('2026-11-01','2026-11-04'))]:
    print('\n',nm,len(rows),'market Brier %.5f'%S.mean(map(bm,rows)),'raw %.5f'%S.mean((r[0.3]['pureO']-ov(r))**2 for r in rows))
    for w in WS:
        d=boot(rows,lambda r:bw(r,w)-bm(r))
        print(' w=%.2f brier %.5f  vs market %+.5f [%+.5f,%+.5f]'%(w,S.mean(bw(r,w) for r in rows),*d))
print()
for w in WS:
    x=[(r,r[w]) for r in R]; 
    def st(z):
        n=len(z);win=sum(a['side']==('over' if b['actual']>a['line'] else 'under') for b,a in z)
        pl=sum(10*(dec(a['price'])-1) if a['side']==('over' if b['actual']>a['line'] else 'under') else -10 for b,a in z)
        return f"{n}: {win}-{n-win} £{pl:+.0f} roi {pl/max(1,n*10):+.3f}"
    print('w',w,'leans',st([z for z in x if z[1]['lean']!='none']),'| strong',st([z for z in x if z[1]['value']]))
    print('   verdicts',dict(C.Counter(a['verdict'] for _,a in x)),'perNight strong %.1f'%(sum(1 for _,a in x if a['value'])/7))
    print('   mean abs edge %.4f'%S.mean(abs(a['modelO']-a['mktO']) for _,a in x))
# gap buckets: does disagreement carry info? regress y-mkt on pure-mkt
xs=[r[0.3]['pureO']-r[0.3]['mktO'] for r in R]; ys=[ov(r)-r[0.3]['mktO'] for r in R]
sl_=sum(a*b for a,b in zip(xs,ys))/sum(a*a for a in xs)
print('\nslope y-mkt on pure-mkt %.3f (best weight implied)'%sl_)
G=C.defaultdict(list)
for r in R:G[r['game']].append((r[0.3]['pureO']-r[0.3]['mktO'],ov(r)-r[0.3]['mktO']))
k=list(G);o=[]
for _ in range(4000):
    a=b=0
    for __ in k:
        for u,v in G[random.choice(k)]:a+=u*v;b+=u*u
    o.append(a/b)
o.sort();print('95%% range %.3f to %.3f'%(o[100],o[3899]))
for m in('PTS','REB','AST'):
    q=[r for r in R if r['market']==m];a=sum((r[0.3]['pureO']-r[0.3]['mktO'])*(ov(r)-r[0.3]['mktO']) for r in q);b=sum((r[0.3]['pureO']-r[0.3]['mktO'])**2 for r in q);print(m,len(q),'slope %.3f'%(a/b))
print('gap bucket (raw-mkt abs) n, hit on model side, mkt exp')
for lo,hi in [(0,.03),(.03,.06),(.06,.1),(.1,.15),(.15,1)]:
    q=[r for r in R if lo<=abs(r[0.3]['pureO']-r[0.3]['mktO'])<hi]
    if not q:continue
    h=sum((r[0.3]['pureO']>r[0.3]['mktO'])==(r['actual']>r[0.3]['line']) for r in q)
    e=S.mean(r[0.3]['mktO'] if r[0.3]['pureO']>r[0.3]['mktO'] else 1-r[0.3]['mktO'] for r in q)
    print(lo,hi,len(q),'%.3f'%(h/len(q)),'exp %.3f'%e)
print('direction: overs vs unders model-side')
for nm,c in (('model>mkt',lambda r:r[0.3]['pureO']>r[0.3]['mktO']),('model<mkt',lambda r:r[0.3]['pureO']<r[0.3]['mktO'])):
    q=[r for r in R if c(r)];print(nm,len(q),'over rate %.3f'%(sum(ov(r) for r in q)/len(q)),'mktO %.3f'%S.mean(r[0.3]['mktO'] for r in q))
print('proj miss',round(S.mean(abs(r['actual']-r[0.3]['projection']) for r in R),3),'line',round(S.mean(abs(r['actual']-r[0.3]['line']) for r in R),3))
