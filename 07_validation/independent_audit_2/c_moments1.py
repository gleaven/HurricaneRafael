from common import *
import pickle, collections, sys, glob
sys.path.insert(0,ROOT+'/scripts'); import geo
cad=pickle.load(open('/tmp/cad2.pkl','rb'))
# cad tuple: d, recv(local), nature, narr, sarp, lat, lon, inc, unit, disp, callback, cos, sarcase
def L(s): return dt.datetime.fromisoformat(s)
SUB2=(27.8021,-97.45287); SUB3=(27.7706,-97.41624)
print('--- breaker 09-21 14:28Z (09:28 local): UTILEMER/DWNPWRLINE calls per hour local 09-21 06..14h')
c=collections.Counter(L(a[1]).hour for a in cad if a[1][:10]=='2027-09-21' and a[2] in('UTILEMER','DWNPWRLINE')); print(sorted(c.items()))
c2=collections.Counter(L(a[1]).hour for a in cad if a[1][:10]=='2027-09-20' and a[2] in('UTILEMER','DWNPWRLINE')); print('prev day',sorted(c2.items()))
near=[a for a in cad if '2027-09-21 09:28'<=a[1]<='2027-09-21 12:00' and geo.dist_m((float(a[5]),float(a[6])),SUB2)<4000]; print('calls within 4 km of SUB-02 09:28-12:00 local',len(near),collections.Counter(a[2] for a in near).most_common(6))
print('--- false calls: no-find near SUB-02/03, area code 737')
fc=[a for a in cad if a[10].startswith('737') and '2027-09-21'<=a[1][:10]<='2027-09-24' and min(geo.dist_m((float(a[5]),float(a[6])),SUB2),geo.dist_m((float(a[5]),float(a[6])),SUB3))<800]
print(len(fc),collections.Counter(a[1][:10] for a in fc),'first',min(a[1] for a in fc),'D+7 times',sorted(a[1][11:16] for a in fc if a[1][:10]=='2027-09-21'))
print('  nature',collections.Counter(a[2] for a in fc),'disp',collections.Counter(a[9] for a in fc),'cos',collections.Counter(a[11] for a in fc),'incs',[a[7] for a in fc][:12])
print('  other 737 numbers in whole CAD',sum(1 for a in cad if a[10].startswith('737')),'ali class share prepaid? all cad cos',collections.Counter(a[11] for a in cad).most_common(6))
print('--- blast 10-28 01:00-01:10 local')
ex=[a for a in cad if a[2]=='EXPLOSION' or ('2027-10-28 00:55'<=a[1]<='2027-10-28 02:30' and ('EXPLO' in a[3] or 'BLAST' in a[3] or 'BOOM' in a[3]))]
for a in ex[:8]: print('  ',a[1],a[2],a[3][:120],a[5],a[6],a[8],a[9])
pc=load('supply/port_conditions.csv'); print(list(pc[0].keys()))
for r in pc:
    t=r.get('effective_utc') or list(r.values())[1]
    if '2027-10-27'<=t[:10]<='2027-11-12' or '2027-10-13'<=t[:10]<='2027-10-15': print('  PC',{k:v[:110] for k,v in r.items() if v})
