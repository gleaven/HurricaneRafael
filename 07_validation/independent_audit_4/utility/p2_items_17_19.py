#!/usr/bin/env python3
"""Items 17 (registry statements), 18 (triage dates), 19 (endpoint), 23 (DHCP/VPN MACs), 27 (triage vs 7045)."""
import sys,collections,re,csv,json,glob,os,pickle; sys.path.insert(0,sys.path[0])
from lib import *
reg_=reg()
h,S=fam('siem'); ix={n:i for i,n in enumerate(h)}
named=set()
for r in S: named.add(r[ix['src_host']]); named.add(r[ix['dst_host']])
ras=audit('remote_access_sessions'); tg=set(); [tg.update(s['target_hosts'].split(';')) for s in ras]
auditnames=set()
for f in glob.glob('audit/*.csv'):
    if 'mail' in f or 'partner' in f or 'city' in f or 'brightwake' in f: continue
    for r in csv.DictReader(open(f,encoding='utf-8')):
        for v in r.values():
            for t in re.findall(r'GW-[A-Z0-9-]+',v or ''): auditnames.add(t)
ro=[x['hostname'] for x in reg_['hosts'] if x.get('reference_only')]
print('ITEM17 reference_only hosts',len(ro),'named in SIEM alerts',sum(x in named for x in ro),'in remote-session targets',sum(x in tg for x in ro),'in audit tables',sum(x in auditnames for x in ro),[x for x in ro if x in named or x in tg or x in auditnames][:10])
print('  reference_only users',sum(1 for u in reg_['users'] if u.get('reference_only')),'service accounts ref-only',[a['account'] for a in reg_['service_accounts'] if a.get('reference_only')])
users_in=set(r[ix['user']] for r in S)
for a in reg_['service_accounts']:
    if a.get('reference_only'): print('   ',a['account'],'in SIEM user field',a['account'] in users_in,'in remote sessions',any(s['account']==a['account'] for s in ras))
print('  metadata block',reg_['metadata']['public_address_block'],'counts',reg_['metadata']['counts'],'actual',len(reg_['hosts']),len(reg_['users']),len(reg_['service_accounts']),len(reg_['equipment']),len(reg_['network_zones']),len(reg_['external_systems']))
print('  external systems',[(e['system_id'],e['hostname'],e['ip'],e.get('reference_only',False)) for e in reg_['external_systems']])
import ipaddress
zc={z['zone']:ipaddress.ip_network(z['cidr']) for z in reg_['network_zones']}
print('  hosts outside zone cidr',sum(1 for x in reg_['hosts'] if x.get('ip') and ipaddress.ip_address(x['ip']) not in zc[x['zone']]),'dup ips',len(reg_['hosts'])-len({x['ip'] for x in reg_['hosts']}),'vendors',collections.Counter(x.get('vendor') for x in reg_['hosts']).most_common(12))
print('  host os',collections.Counter(x.get('os') for x in reg_['hosts']).most_common(12))
# hosts in logs not in registry
hn={x['hostname'] for x in reg_['hosts']}
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
print('  windows hosts not in registry',{d['host'] for d in W}-hn,'| SIEM hosts not in registry',{x for x in named if x and x not in hn})
# ITEM18 triage future dates
fut=0;tot=0;ex=[]
for d in sorted(os.listdir('triage')):
    c=json.load(open(f'triage/{d}/collection.json'))['collected_utc']
    for f in ('file_listing.csv','autoruns.csv','services.csv','scheduled_tasks.csv','execution_history.csv','logon_history.csv','installed_software.csv'):
        for r in csv.DictReader(open(f'triage/{d}/{f}')):
            for k,v in r.items():
                if k.endswith('_utc') and v:
                    tot+=1
                    if v>c: fut+=1; ex.append((d,f,k,v,c))
                if k=='install_date' and v and v>c[:10]: fut+=1; ex.append((d,f,k,v,c))
print('ITEM18 triage time fields',tot,'later than collection',fut,ex[:4])
# created>modified
cm=0
for d in sorted(os.listdir('triage')):
    for r in csv.DictReader(open(f'triage/{d}/file_listing.csv')):
        if r['created_utc']>r['modified_utc']: cm+=1
print('  file_listing created later than modified',cm)
# triage services vs 7045, logon_history vs windows
SY=pickle.load(open('/tmp/c/winsys.pkl','rb'))
s7045={(d['host'],d['service_name']) for d in SY if d['event_id']==7045}
miss=[]
for d in sorted(os.listdir('triage')):
    for r in csv.DictReader(open(f'triage/{d}/services.csv')):
        if r['installed_utc']>='2027-07-16' and (d,r['display_name']) not in s7045: miss.append((d,r['display_name'],r['installed_utc']))
print('  triage services installed in span without 7045:',len(miss),miss[:5])
# logon_history checks are in p2_triage_logons.py
print('  browser versions: triage installed',[ (d,r['name'],r['version']) for d in sorted(os.listdir('triage')) for r in csv.DictReader(open(f'triage/{d}/installed_software.csv')) if 'Edge' in r['name'] or 'Chrome' in r['name'] or 'Firefox' in r['name']][:6])
ua=collections.Counter(re.findall(r'(Chrome/\d+|Firefox/\d+|Edg/\d+)',' '.join({r[12] for r in zeek('http')}))); print('  http UA versions',ua.most_common(8))
