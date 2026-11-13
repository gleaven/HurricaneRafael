#!/usr/bin/env python3
"""Items 25 (reserved address ranges used as internet hosts) and 27 (browser versions triage vs UA)."""
import sys,collections,ipaddress,csv,os,re; sys.path.insert(0,sys.path[0])
from lib import *
conn=zeek('conn')
nets={n:ipaddress.ip_network(n) for n in ('127.0.0.0/8','100.64.0.0/10','192.168.0.0/16','172.16.0.0/12','169.254.0.0/16','192.0.2.0/24','198.51.100.0/24','203.0.113.0/24','224.0.0.0/3','0.0.0.0/8','198.18.0.0/15')}
c=collections.Counter(); seen={}
for r in conn:
    for ip in (r[2],r[4]):
        if ip.startswith('10.') or ip.startswith('172.20.5.'): continue
        if ip in seen: k=seen[ip]
        else:
            a=ipaddress.ip_address(ip); k=next((n for n,net in nets.items() if a in net),None); seen[ip]=k
        if k: c[k]+=1
print('conn endpoints in reserved ranges (excluding 10/8 and the DMZ 172.20.5/24):',dict(c))
h,F=fam('fw_edge'); d=collections.Counter()
for r in F:
    ip=r[6]
    if ip.startswith('10.') or ip.startswith('172.20.5.'): continue
    if ip not in seen:
        a=ipaddress.ip_address(ip); seen[ip]=next((n for n,net in nets.items() if a in net),None)
    if seen[ip]: d[(seen[ip],r[2])]+=1
print('edge firewall source addresses in reserved ranges:',dict(d))
ras=audit('remote_access_sessions'); print('vendor session sources',collections.Counter((s['src_ip'].rsplit('.',1)[0],s['src_network']) for s in ras if s['account'].startswith('svc')).most_common(4))
for t in sorted(os.listdir('triage')):
    for r in csv.DictReader(open(f'triage/{t}/installed_software.csv')):
        if re.search('Edge|Chrome|Firefox|Browser',r['name'],re.I): print('triage',t,r['name'],r['version'])
ua=collections.Counter()
for r in zeek('http'):
    for m in re.findall(r'(Chrome/\d+|Firefox/\d+|Edg/\d+)',r[12]): ua[m]+=1
print('http.log UA versions',ua.most_common(8))
