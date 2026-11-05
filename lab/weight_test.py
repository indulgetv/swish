"""Weight test, part 1: re-run the live model on the last snapshot before each saved pick, at several MODEL_WEIGHTs.
Needs: git fetch --depth=3000 origin main. Run: python3 lab/weight_test.py OUT.pkl, then python3 lab/weight_report.py OUT.pkl"""
import json,glob,subprocess,sys,random,math,collections as C,pickle
from datetime import datetime
R='/home/claude/swish'; sys.path.insert(0,R+'/scripts'); import model
commits=[]
for ln in subprocess.run(['git','-C',R,'log','origin/main','--format=%h %cI','--','data/live.json'],capture_output=True,text=True).stdout.split('\n'):
    if ln: h,t=ln.split(); commits.append((datetime.fromisoformat(t),h))
commits.sort()
picks=[]
for f in sorted(glob.glob(R+'/data/picks/2026-*.json')):
    for p in json.load(open(f))['picks'].values():
        p['slate']=f[-15:-5]
        if p.get('result') in('win','loss'): picks.append(p)
WS=[0.05,0.1,0.15,0.2,0.3]
snap=C.defaultdict(list)
for p in picks:
    tip=datetime.fromisoformat(p['tipoff'].replace('Z','+00:00'))
    b=[h for t,h in commits if t<tip]
    if b: snap[b[-1]].append(p)
print('snapshots',len(snap),file=sys.stderr)
out=[];miss=0
for h,ps in snap.items():
    s=subprocess.run(['git','-C',R,'show',f'{h}:data/live.json'],capture_output=True,text=True).stdout
    if not s: miss+=len(ps);continue
    live=json.loads(s); res={}
    for w in WS:
        model.MODEL_WEIGHT=w
        res[w]={(x['game'],x['player'],x['market']):x for x in model.build_picks(live)}
    for p in ps:
        k=(p['game'],p['player'],p['market'])
        if k not in res[0.3]: miss+=1;continue
        r={'slate':p['slate'],'game':p['game'],'market':p['market'],'player':p['player'],'actual':p['actual'],'logged_line':p['line'],'mp':p.get('minutesPlayed')}
        for w in WS:
            x=res[w][k]
            r[w]={f:x.get(f) for f in('line','price','side','lean','value','verdict','flags','edge','ev','pureO','mktO','modelO','projection','minutes','over','under')}
        out.append(r)
print('matched',len(out),'of',len(picks),'miss',miss,file=sys.stderr)
pickle.dump(out,open(sys.argv[1],'wb'))
