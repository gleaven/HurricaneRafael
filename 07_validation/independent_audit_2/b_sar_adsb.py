from common import *
import collections, bisect, sys, csv
sys.path.insert(0,ROOT+'/scripts'); import geo
ic={'ae5d83':'CG-6033','ae1118':'CG-6041','a1b783':'N3941A','aa0d79':'N110TX','ac8a3c':'N208CB'}
tr=collections.defaultdict(list)
for row in csv.reader(open('/tmp/sar_adsb.csv')):
    tr[ic[row[0]]].append((int(row[3]),float(row[6]),float(row[5]),row[8]=='True',float(row[9] or 0),float(row[13] or 0)))
for k in tr: tr[k].sort(); print(k,len(tr[k]),dt.datetime.fromtimestamp(tr[k][0][0],dt.timezone.utc),dt.datetime.fromtimestamp(tr[k][-1][0],dt.timezone.utc))
m=load('sar/sar_missions.csv')
hel=[r for r in m if r['asset_type']=='helicopter']
E=lambda s:int(ts(s).timestamp())
stat=collections.Counter(); worst=[]
for r in hel:
    T=tr[r['asset_id']]; ts_=[x[0] for x in T]
    t=E(r['on_scene_utc']); i=bisect.bisect_left(ts_,t)
    cand=[T[j] for j in (i-1,i) if 0<=j<len(T)]
    if not cand or min(abs(c[0]-t) for c in cand)>180: stat['no adsb within 3 min of on_scene']+=1; continue
    c=min(cand,key=lambda c:abs(c[0]-t)); d=geo.dist_m((c[1],c[2]),(float(r['latitude']),float(r['longitude'])))
    if d>600: stat['adsb >600 m from rescue']+=1; worst.append((r['case_number'],r['asset_id'],r['on_scene_utc'],round(d)))
    else: stat['ok']+=1
    if c[3]: stat['on ground at scene']+=1
    # airborne between launch and recovery
print(dict(stat),worst[:8])
# mission-level: first airborne fix vs launch, landing vs recovery
ms={}
for r in hel: ms[r['mission_id']]=r
st2=collections.Counter(); ex=[]
for mid,r in ms.items():
    T=tr[r['asset_id']]; a,b=E(r['launch_utc']),E(r['recovery_utc'])
    seg=[x for x in T if a-600<=x[0]<=b+600]
    air=[x for x in seg if not x[3]]
    if not air: st2['no airborne fixes']+=1; ex.append(mid); continue
    d0=air[0][0]-a; d1=air[-1][0]-b
    st2['launch match(<=120s)' if abs(d0)<=120 else 'launch mismatch']+=1
    st2['recovery match(<=120s)' if abs(d1)<=120 else 'recovery mismatch']+=1
    if abs(d0)>120 or abs(d1)>120: ex.append((mid,r['asset_id'],r['launch_utc'],d0,d1))
print(dict(st2),ex[:6])
# any airborne time for these helicopters outside missions on D0-D+3?
for a in ('CG-6033','CG-6041','N110TX','N3941A'):
    T=[x for x in tr[a] if not x[3] and E('2027-09-14T00:00:00Z')<=x[0]<=E('2027-09-18T00:00:00Z')]
    iv=[(E(r['launch_utc'])-300,E(r['recovery_utc'])+300) for r in ms.values() if r['asset_id']==a]
    out=[x for x in T if not any(lo<=x[0]<=hi for lo,hi in iv)]
    print(a,'airborne fixes D0-D+3',len(T),'outside SAR missions',len(out), 'max speed m/s',max(x[4] for x in T) if T else None, [str(dt.datetime.fromtimestamp(x[0],dt.timezone.utc)) for x in out[:1]+out[-1:]])
# thermal Caravan sortie
T=[x for x in tr['N208CB'] if E('2027-09-25T08:00:00Z')<=x[0]<=E('2027-09-25T13:00:00Z')]
air=[x for x in T if not x[3]]
print('N208CB 25 Sep airborne',len(air), dt.datetime.fromtimestamp(air[0][0],dt.timezone.utc) if air else None, dt.datetime.fromtimestamp(air[-1][0],dt.timezone.utc) if air else None,'alt geo max',max(x[5] for x in air) if air else None)
SUBS={'SUB-01':(27.80951,-97.45564),'SUB-02':(27.8021,-97.45287),'SUB-03':(27.7706,-97.41624)}
for s,p in SUBS.items():
    if air: 
        c=min(air,key=lambda x:geo.dist_m((x[1],x[2]),p)); print(s,'closest',round(geo.dist_m((c[1],c[2]),p)),dt.datetime.fromtimestamp(c[0],dt.timezone.utc))
