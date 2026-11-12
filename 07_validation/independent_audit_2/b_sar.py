from common import *
import pickle, collections, sys, bisect
sys.path.insert(0,ROOT+'/scripts'); import geo
G=geo.Geo()
m=load('sar/sar_missions.csv')
res=[r for r in m if r['outcome']=='RESCUED']
def cum(t): return sum(int(r['persons']) for r in res if r['on_scene_utc']<=t)
for t,exp in [('2027-09-15T20:00:00Z',486),('2027-09-16T23:00:00Z',702),('2027-09-19T22:00:00Z',1427),('2027-09-22T00:00:00Z',1427)]:
    print('cumulative by',t,cum(t),'canon',exp, 'by recovery', sum(int(r['persons']) for r in res if r['recovery_utc']<=t))
print('by air at D+1 15:00',sum(1 for r in res if r['asset_type']=='helicopter' and r['on_scene_utc']<='2027-09-15T20:00:00Z'),'hoists',sum(1 for r in res if r['method']=='HOIST' and r['on_scene_utc']<='2027-09-15T20:00:00Z'))
print('totals: helicopter',sum(1 for r in res if r['asset_type']=='helicopter'),'surface',sum(1 for r in res if r['asset_type'] not in('helicopter','welfare_check_team')),'ambulatory',sum(1 for r in res if r['method']=='AMBULATORY CONTACT'), cnt(res,'asset_type'))
print('first',min(m,key=lambda r:r['on_scene_utc'])['on_scene_utc'],'last rescue',max(res,key=lambda r:r['on_scene_utc'])['on_scene_utc'],'last row',max(m,key=lambda r:r['launch_utc'])['launch_utc'])
byday=collections.Counter(dday(ts(r['on_scene_utc'])) for r in res); print('rescues by local D-day',sorted(byday.items()))
bd=collections.defaultdict(collections.Counter)
for r in m: bd[dday(ts(r['launch_utc']))][r['asset_type']]+=1
for d in sorted(bd): print('  D',d,dict(bd[d]))
# sorties D+1
for a in ('CG-6033','CG-6041'):
    for dd in (0,1,2,3):
        s={r['mission_id'] for r in m if r['asset_id']==a and dday(ts(r['launch_utc']))==dd}; print(a,'D',dd,'sorties',len(s),'rescues',sum(1 for r in m if r['asset_id']==a and dday(ts(r['launch_utc']))==dd))
print('helicopter assets',cnt([r for r in m if r['asset_type']=='helicopter'],'asset_id'))
tf=[r for r in m if r['agency']=='TF1']
print('TF1 deployments D+2 (missions):',len({r['mission_id'] for r in tf if dday(ts(r['launch_utc']))==2}),'D+1',len({r['mission_id'] for r in tf if dday(ts(r['launch_utc']))==1}),'TF1 rescued D+1+D+2',sum(1 for r in tf if dday(ts(r['on_scene_utc'])) in (1,2)),'all rescued D+1+D+2',byday[1]+byday[2])
civ={r['asset_id'] for r in m if r['asset_type']=='civilian_boat'}; print('civilian boats',len(civ),'first',min(r['launch_utc'] for r in m if r['asset_type']=='civilian_boat'))
# helicopters after D+3 03:00
print('helicopter rescues after 2027-09-17T08:00Z',sum(1 for r in res if r['asset_type']=='helicopter' and r['on_scene_utc']>'2027-09-17T08:00:00Z'),'surface before',sum(1 for r in res if r['asset_type']!='helicopter' and r['on_scene_utc']<'2027-09-17T08:00:00Z'))
# land check
wat=[(r['case_number'],r['latitude'],r['longitude'],r['asset_type']) for r in m if not G.is_land(float(r['latitude']),float(r['longitude']))]
print('positions not on land',len(wat),wat[:5])
rd=[G.roads.nearest(float(r['latitude']),float(r['longitude']))[0] for r in m[::7]]
print('road dist sample max',round(max(rd)),'p95',round(sorted(rd)[int(len(rd)*.95)]))
# time order
bad=sum(1 for r in m if not (r['launch_utc']<=r['on_scene_utc']<=r['recovery_utc'])); print('time order violations',bad)
# mission durations
dur=sorted((ts(r['recovery_utc'])-ts(r['launch_utc'])).total_seconds()/3600 for r in {r['mission_id']:r for r in m}.values()); print('mission dur h q',[round(dur[int(len(dur)*q)],1) for q in (0,.1,.5,.9,.999)])
# per-mission rescue count by asset type
pm=collections.defaultdict(list)
for mid,c in collections.Counter(r['mission_id'] for r in m).items(): pm[[r for r in m if r['mission_id']==mid][0]['asset_type']].append(c)
for k,v in pm.items(): print(k,'missions',len(v),'rescues/mission max',max(v),'counts',collections.Counter(v).most_common(4))
# no-find
nf=[r for r in m if r['outcome']!='RESCUED']
for r in nf: print(r['case_number'],r['mission_id'],r['asset_id'],r['crew_element'],r['launch_utc'],r['on_scene_utc'],r['latitude'],r['longitude'],r['address'],r['incident_number'])
# CAD join
cad=pickle.load(open('/tmp/cad2.pkl','rb')); ci={a[7]:a for a in cad}
miss=[r['incident_number'] for r in m if r['incident_number'] not in ci]; print('incident numbers not in CAD',len(miss),miss[:3])
off=[]; sarc=0
for r in m:
    a=ci.get(r['incident_number'])
    if a:
        off.append(geo.dist_m((float(a[5]),float(a[6])),(float(r['latitude']),float(r['longitude']))))
        if a[12]: sarc+=1
print('CAD position offset max m',round(max(off)),'CAD rows with sar_case_number',sarc, 'example',ci[m[0]['incident_number']])
# call before on_scene?
neg=sum(1 for r in m if ci.get(r['incident_number']) and local(ts(r['on_scene_utc'])).replace(tzinfo=None) < dt.datetime.fromisoformat(ci[r['incident_number']][1])); print('on scene before call received',neg)
