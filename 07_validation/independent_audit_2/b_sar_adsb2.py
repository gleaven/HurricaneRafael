from common import *
import collections, csv
T=[]
for row in csv.reader(open('/tmp/sar_adsb.csv')):
    if row[0]=='ae5d83': T.append((int(row[3]),row[8]=='True',float(row[6]),float(row[5])))
T.sort()
f=lambda e:dt.datetime.fromtimestamp(e,dt.timezone.utc).strftime('%m-%d %H:%M:%S')
# airborne intervals (gap>10 min or on-ground splits)
iv=[];cur=None
for t,g,la,lo in T:
    if t<int(ts('2027-09-14T00:00:00Z').timestamp()) or t>int(ts('2027-09-16T12:00:00Z').timestamp()): continue
    if g: 
        if cur: iv.append(cur); cur=None
        continue
    if cur and t-cur[1]>600: iv.append(cur); cur=None
    if cur is None: cur=[t,t]
    else: cur[1]=t
if cur: iv.append(cur)
print('CG-6033 ADS-B airborne intervals D0..D+2:'); [print('  ',f(a),f(b),round((b-a)/60),'min') for a,b in iv]
m=load('sar/sar_missions.csv'); ms={}
for r in m:
    if r['asset_id']=='CG-6033': ms.setdefault(r['mission_id'],[r['launch_utc'],r['recovery_utc'],0])[2]+=1
print('CG-6033 SAR log sorties:'); [print('  ',k,v) for k,v in ms.items()]
al=[r for r in rows('sar/sar_asset_log.csv') if r['asset_id']=='CG-6033']
print('asset log',[(r['time_utc'],r['status']) for r in al][:30])
