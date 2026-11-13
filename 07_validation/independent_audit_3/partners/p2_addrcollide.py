import csv,glob,re,os
from collections import Counter,defaultdict
from lib import *
P=ROOT+"/05_other_sources/network_logs/portal/"
rows=[]
nets=Counter(); doc=Counter()
for f in sorted(glob.glob(P+'aid_portal_access_*.csv')):
    with open(f,newline='',encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            ip=r['client_ip']; nets[r['client_network']]+=1
            for p in ('198.51.100.','203.0.113.','192.0.2.'):
                if ip.startswith(p): doc[(p,r['client_network'])]+=1
            if ip.startswith('198.51.100.'): rows.append(r)
print('aid portal client_network top',nets.most_common(12))
print('aid portal doc-range clients',doc)
last=Counter(int(r['client_ip'].split('.')[3]) for r in rows)
print('198.51.100.x rows',len(rows),'distinct',len(last),'in office NAT pool 10-59:',sum(v for k,v in last.items() if 10<=k<=59),'in vpn egress 128-191:',sum(v for k,v in last.items() if 128<=k<=191),'other',sum(v for k,v in last.items() if not(10<=k<=59 or 128<=k<=191)))
print(' events',Counter(r['event'] for r in rows).most_common(8),'months',sorted(Counter(r['time_utc'][:7] for r in rows).items()))
# base logistics: outside requests
L=[]
for f in sorted(glob.glob(P+'base_logistics_access_*.csv')):
    with open(f,newline='',encoding='utf-8') as fh:
        for r in csv.DictReader(fh): r['_f']=os.path.basename(f); L.append(r)
print('base logistics rows',len(L),Counter(r['client_network'] for r in L).most_common(8))
ext=[r for r in L if r['client_network']!='base network']
print(' outside rows',len(ext),'ip /24s',Counter('.'.join(r['client_ip'].split('.')[:3]) for r in ext).most_common(6),'events',Counter(r['event'] for r in ext).most_common(8),'months',sorted(Counter(r['time_utc'][:7] for r in ext).items()))
print(' outside status',Counter(r['status'] for r in ext),'UA',Counter(r['user_agent_family'] for r in ext).most_common(5),'paths',Counter(r['path'] for r in ext).most_common(8))
pickle.dump(ext,open(HERE+'/cache/logistics_ext.pkl','wb'))
# the same doc-range /24 across other delivered streams
import subprocess
