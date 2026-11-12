from common import *
import pickle, collections, sys, glob, csv
sys.path.insert(0,ROOT+'/scripts'); import geo
cad=pickle.load(open('/tmp/cad2.pkl','rb'))
SUB2=(27.8021,-97.45287); SUB3=(27.7706,-97.41624)
nf=[a for a in cad if 7<=a[0]<=10 and a[9] in('UNFND','NOFIND','UTL','UNF') and min(geo.dist_m((float(a[5]),float(a[6])),SUB2),geo.dist_m((float(a[5]),float(a[6])),SUB3))<700]
print('disposition codes D+7..10',collections.Counter(a[9] for a in cad if 7<=a[0]<=10).most_common(12))
print('no-find near SUB-02/03 D+7..D+10:',len(nf),sorted(collections.Counter(a[0] for a in nf).items()),'first',min(a[1] for a in nf) if nf else None)
print('  D+7 times local',sorted(a[1][11:16] for a in nf if a[0]==7))
print('  callback prefixes',collections.Counter(a[10][:3] for a in nf),'cos',collections.Counter(a[11] for a in nf),'nature',collections.Counter(a[2] for a in nf).most_common(5),'sar case',sum(1 for a in nf if a[12]))
print('  narr',collections.Counter(a[3][:60] for a in nf).most_common(4))
# asset log incidents 009538, 009610
ci={a[7]:a for a in cad}
for i in ('19-2027-009510','19-2027-009538','19-2027-009573','19-2027-009610'): a=ci.get(i); print('  ',i,a[1],a[2],a[9],a[10][:3],round(min(geo.dist_m((float(a[5]),float(a[6])),SUB2),geo.dist_m((float(a[5]),float(a[6])),SUB3))) if a else None)
# AIS Narwhal Dream
v=json.load(open(ROOT+'/06_data_streams/vessels.json')); s=json.dumps(v); i=s.find('Narwhal Dream'); seg=s[max(0,i-900):i+200]
import re; mm=re.findall(r'"mmsi": "?(\d{9})',seg); print('Narwhal mmsi cand',mm[-1:] )
mmsi=mm[-1] if mm else None
rowsN=[]
for f in sorted(glob.glob(SRC+'/ais/ais_2027-0[89].csv')):
    with open(f) as fh:
        hdr=fh.readline().strip().split(',')
        for line in fh:
            if line.startswith(mmsi+','): rowsN.append(line.strip().split(','))
print('AIS hdr',hdr[:8]); print('Narwhal rows',len(rowsN),'first',rowsN[0][:5] if rowsN else None,'last',rowsN[-1][:5] if rowsN else None)
if rowsN:
    ti=hdr.index('BaseDateTime'); la=hdr.index('LAT'); lo=hdr.index('LON'); sg=hdr.index('SOG')
    MAR=(27.84566,-97.2262)
    at=[r for r in rowsN if geo.dist_m((float(r[la]),float(r[lo])),MAR)<600]
    print('  at Ingleside Marina (<600 m):',len(at),at[0][ti] if at else None,at[-1][ti] if at else None)
    print('  rows 09-06T23..09-07T02',[(r[ti],r[la],r[lo],r[sg]) for r in rowsN if '2027-09-06T23'<=r[ti]<='2027-09-07T02'][:6])
    print('  night positions 09-06T04:00-04:40',[(r[ti],r[la],r[lo]) for r in rowsN if '2027-09-06T03:50'<=r[ti]<='2027-09-06T04:45'][:4])
