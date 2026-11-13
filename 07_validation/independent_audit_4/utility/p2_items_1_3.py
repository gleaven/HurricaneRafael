#!/usr/bin/env python3
"""Re-test of earlier items 1-3: top pair, cipher uniqueness, hand-placed flow artefacts."""
import sys,collections,statistics; sys.path.insert(0,sys.path[0])
from lib import *
conn=zeek('conn')
inter=lambda ip: ip.startswith('10.') or ip.startswith('172.20.')
# item 1
pair=collections.Counter((r[2],r[4]) for r in conn if inter(r[2]) and not inter(r[4]))
mc=pair.most_common()
rank=[i for i,(k,v) in enumerate(mc) if k==('10.14.22.47',C2)][0]+1
print('ITEM1 pairs',len(mc),'C2 pair rank',rank,'count',pair[('10.14.22.47',C2)],'top5',mc[:5])
ws=[k for k in mc if k[0][0].startswith(('10.14.2','10.14.30.'))]
rk=[i for i,(k,v) in enumerate(ws) if k==('10.14.22.47',C2)][0]+1
print('  among workstation-originated pairs rank',rk,'pairs with >=150 flows',sum(1 for k,v in ws if v>=150))
tot=collections.Counter(r[2] for r in conn if inter(r[2]) and not inter(r[4]))
sh=sorted(((pair[k]/tot[k[0]],k,pair[k],tot[k[0]]) for k in pair if tot[k[0]]>200 and k[0].startswith(('10.14.2','10.14.30.'))),reverse=True)
print('  top share of a workstation outbound flows to one address:',[(round(a,3),k,n,t) for a,k,n,t in sh[:8]])
# per-host: is the top external dst a one-host destination?
dst_hosts=collections.defaultdict(set)
for (s,d),v in pair.items(): dst_hosts[d].add(s)
tops={}
for (s,d),v in pair.items():
    if s.startswith(('10.14.2','10.14.30.')) and (s not in tops or v>tops[s][1]): tops[s]=(d,v)
uniq=[(s,d,v) for s,(d,v) in tops.items() if len(dst_hosts[d])==1]
print('  workstations whose most-contacted external address is contacted by no other host:',len(uniq),uniq[:10])
# item 2
ssl=zeek('ssl')
cc=collections.Counter(r[7] for r in ssl); c2c=collections.Counter(r[7] for r in ssl if r[4]==C2)
print('ITEM2 C2 cipher',c2c,'same cipher overall',{k:cc[k] for k in c2c})
c2v=collections.Counter((r[6],r[9]) for r in ssl if r[4]==C2); print('  C2 version/resumed',c2v,'; resumed share overall',round(sum(1 for r in ssl if r[9]=='T')/len(ssl),3), 'TLS13 non-resumed to ext overall',sum(1 for r in ssl if r[6]=='TLSv13' and r[9]=='F'))
# item 3
ws0=[r for r in conn if r[0].endswith('.000000')]
print('ITEM3 conn rows with whole-second ts',len(ws0),'of',len(conn))
host=[r for r in conn if r[2].startswith(HOSTILE_SRC)]
print('  hostile gateway flows',len(host),'ts whole-second',sum(r[0].endswith('.000000') for r in host),'dur ends 00000',sum(r[8].endswith('00000') for r in host),'orig_bytes%100==0',sum(int(r[9])%100==0 for r in host))
ras=audit('remote_access_sessions')
bykey={(r[2],T(r[0])[:16]):r for r in conn if r[4]=='10.72.4.88' and r[5]=='443'}
dd=collections.defaultdict(list); beq=collections.Counter()
import datetime
for s in ras:
    t0=E(s['login_utc']); best=None
    for r in conn:
        pass
    break
idx=collections.defaultdict(list)
for r in conn:
    if r[4]=='10.72.4.88' and r[5]=='443': idx[r[2]].append(r)
miss=0
for s in ras:
    t0=E(s['login_utc']); cands=[r for r in idx.get(s['src_ip'],[]) if abs(float(r[0])-t0)<10]
    h=s['src_country']!='US'
    if not cands: miss+=1; continue
    r=cands[0]
    dd[h].append(float(r[8])-int(s['duration_s'])); 
    beq[(h,int(r[9])==int(s['bytes_in']) and int(r[10])==int(s['bytes_out']))]+=1
    dd[('lead',h)].append(t0-float(r[0]))
print('  RAS sessions without gateway flow',miss,'bytes equal (hostile?,equal):',dict(beq))
for h in (True,False):
    v=dd[h]; l=dd[('lead',h)]
    print('  hostile' if h else '  benign','zeek dur - session dur: min/med/max',round(min(v),3),round(statistics.median(v),3),round(max(v),3),'| login - flow ts: min/med/max',round(min(l),3),round(statistics.median(l),3),round(max(l),3))
# breaker command flows
p4000=[r for r in conn if r[5]=='4000']
print('  port 4000 flows',len(p4000),'src ports top',collections.Counter(r[3] for r in p4000).most_common(3),'(orig,resp) bytes top',collections.Counter((r[9],r[10]) for r in p4000).most_common(3))
for r in p4000:
    if T(r[0])[:13] in('2027-09-21T14','2027-09-24T19'): print('   ',T(r[0]),r[2:12])
# staging flow
st=[r for r in conn if r[2]=='10.14.22.47' and r[4]=='10.72.4.20']
for r in st: print('  staging',T(r[0]),r)
smb=[r for r in conn if r[5]=='445' and r[8]!='-' and r[11]=='SF']
print('  smb SF flows',len(smb),'with ms-precision duration',sum(r[8].endswith('000') for r in smb),'>100MB',sum(int(r[10])>1e8 or int(r[9])>1e8 for r in smb))
# ms-precision duration class vs C2
c2=[r for r in conn if r[4]==C2]
print('  C2 flows with ms-precision duration',sum(r[8].endswith('000') for r in c2),'of',len(c2))
per=[r for r in conn if r[7]=='ssl' and r[8].endswith('000') and r[8]!='-' and float(r[8])!=int(float(r[8]))]
print('  benign periodic class (ms-precision ssl):',len(per))
