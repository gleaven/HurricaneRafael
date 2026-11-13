#!/usr/bin/env python3
"""Item 23 + pass 3: DHCP leases vs registry, VPN sessions vs DHCP pool vs firewall/zeek vs Windows src_ip; MACs; IT-04 after triage; power loss vs DHCP/boots."""
import sys,collections,json,pickle,re,statistics,glob; sys.path.insert(0,sys.path[0])
from lib import *
h,D=fam('dhcp'); ix={n:i for i,n in enumerate(h)}
reg_=reg(); hip={x['hostname']:x['ip'] for x in reg_['hosts']}; hz={x['hostname']:x['zone'] for x in reg_['hosts']}
print('dhcp rows',len(D),'events',collections.Counter(r[ix['event']] for r in D),'servers',collections.Counter(r[ix['server']] for r in D),'scopes',collections.Counter(r[ix['scope']] for r in D).most_common(8),'lease_s',collections.Counter(r[ix['lease_s']] for r in D).most_common(4))
mac=collections.defaultdict(set); hm=collections.defaultdict(set)
for r in D: mac[r[ix['mac']]].add(r[ix['hostname']]); hm[r[ix['hostname']]].add(r[ix['mac']])
print('macs',len(mac),'starting 02:',sum(m.startswith('02:') for m in mac),'OUI top',collections.Counter(m[:8] for m in mac).most_common(5),'mac->>1 host',sum(len(v)>1 for v in mac.values()),'host->>1 mac',sum(len(v)>1 for v in hm.values()))
bad=[(r[ix['hostname']],r[ix['ip']]) for r in D if r[ix['hostname']] in hip and hip[r[ix['hostname']]]!=r[ix['ip']] and r[ix['scope']]!='corp-vpn']
print('registry hosts with lease ip != registry ip',len(bad),bad[:3],'| leased non-VPN hosts not in registry',len({r[ix['hostname']] for r in D if r[ix['scope']]!='corp-vpn' and r[ix['hostname']] not in hip}))
print('zones of leased registry hosts',collections.Counter(hz.get(r[ix['hostname']],'?') for r in D if r[ix['scope']]!='corp-vpn').most_common(8))
# triage network_config mac vs dhcp
import csv,os
for t in sorted(os.listdir('triage')):
    nc=list(csv.DictReader(open(f'triage/{t}/network_config.csv')))[0]
    if t in hm: print('  triage',t,'mac',nc['mac'],'dhcp',hm[t],'dhcp_enabled',nc['dhcp_enabled'],'ip ok',nc['ip']==hip[t])
# VPN
V=audit('employee_vpn_sessions')
vp=[r for r in D if r[ix['scope']]=='corp-vpn']
vk=collections.defaultdict(list)
for r in vp: vk[(r[ix['ip']],r[ix['hostname']])].append((E(r[ix['time_utc']]),r[ix['event']],r[ix['mac']]))
ok=0;rel=0
for s in V:
    c=vk.get((s['assigned_ip'],s['device']),[])
    if any(e=='ASSIGN' and abs(t-E(s['login_utc']))<=5 for t,e,m in c): ok+=1
    if any(e in('RELEASE','EXPIRE') and abs(t-E(s['logout_utc']))<=5 for t,e,m in c): rel+=1
print('VPN sessions',len(V),'with DHCP ASSIGN at login',ok,'with RELEASE at logout',rel,'| vpn dhcp rows',len(vp),collections.Counter(r[ix['event']] for r in vp))
dm=collections.defaultdict(set); ad=collections.defaultdict(set)
for r in vp: dm[r[ix['hostname']]].add(r[ix['mac']])
for s in V: ad[s['account']].add(s['device'])
print('VPN devices',len(dm),'with >1 mac',sum(len(v)>1 for v in dm.values()),'| accounts',len(ad),'devices per account',collections.Counter(len(v) for v in ad.values()),'| company laptops',sum(1 for d in dm if d.startswith('GW-')),'home',sum(1 for d in dm if not d.startswith('GW-')))
# overlap: same pool ip in two sessions at once; same account two sessions at once
ov=0; byip=collections.defaultdict(list)
for s in V: byip[s['assigned_ip']].append((E(s['login_utc']),E(s['logout_utc'])))
for v in byip.values():
    v.sort()
    ov+=sum(1 for a,b in zip(v,v[1:]) if b[0]<a[1])
print('pool address overlaps',ov)
# vpn flows on edge fw & zeek
conn=zeek('conn'); vf=collections.defaultdict(list)
for r in conn:
    if r[4]=='172.20.5.30': vf[r[2]].append(r)
m=0;beq=0
for s in V:
    c=[r for r in vf.get(s['src_ip'],[]) if abs(float(r[0])-E(s['login_utc']))<10]
    if c:
        m+=1; beq+= (c[0][9]==s['bytes_in'] and c[0][10]==s['bytes_out'])
print('VPN sessions with gateway flow',m,'bytes equal',beq)
# while on VPN: a user working at office at same time? interactive logon on a workstation during VPN session
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
lo={}
for d in W:
    if d['event_id'] in(4634,4647): lo.setdefault((d['host'],d['logon_id']),E(d['time_utc']))
us=collections.defaultdict(list)
for d in W:
    if d['event_id']==4624 and d['logon_type']==2 and not d['host'].startswith('GW-LT'): us[d['user']].append((E(d['time_utc']),lo.get((d['host'],d['logon_id']),E(d['time_utc'])+3600),d['host']))
both=0
for s in V:
    a,b=E(s['login_utc']),E(s['logout_utc'])
    if any(x<b and y>a for x,y,hh in us.get(s['account'],[])): both+=1
print('VPN sessions overlapping an interactive desktop session of the same user at the office',both)
# src_ip of 4624 in vpn pool: matches a session of that user?
pool=[d for d in W if d['event_id']==4624 and (d.get('src_ip') or '').startswith('10.14.250.')]
okp=0
si=collections.defaultdict(list)
for s in V: si[(s['account'],s['assigned_ip'])].append((E(s['login_utc']),E(s['logout_utc'])))
for d in pool:
    if any(a<=E(d['time_utc'])<=b for a,b in si.get((d['user'],d['src_ip']),[])): okp+=1
print('4624 from VPN pool addresses',len(pool),'inside a VPN session of that user with that address',okp)
# local hour of vpn logins, weekday split
import zoneinfo,datetime
tz=zoneinfo.ZoneInfo('America/Chicago'); hh=collections.Counter(); wd=collections.Counter()
for s in V:
    t=datetime.datetime.fromtimestamp(E(s['login_utc']),tz); hh[t.hour]+=1; wd[t.weekday()]+=1
print('VPN logins by local hour',[hh[x] for x in range(24)],'weekday',[wd[x] for x in range(7)])
vd=collections.Counter(s['login_utc'][:10] for s in V); print('VPN per day 09-10..09-20',[vd['2027-09-%02d'%d] for d in range(10,21)],'median',statistics.median(vd.values()))
# IT-04 after triage
cnt=collections.Counter()
for f in sorted(glob.glob('endpoint/endpoint_2027-1*.jsonl'))+['endpoint/endpoint_2028-01.jsonl']:
    for line in open(f):
        if '"GW-WS-IT-04"' in line: cnt[line[13:20]]+=1
print('IT-04 endpoint events by month',sorted(cnt.items()),'| dhcp rows after 10-12',sum(1 for r in D if r[ix['hostname']]=='GW-WS-IT-04' and r[0]>'2027-10-12T16'),'last IT-04 dhcp',max((r[0] for r in D if r[ix['hostname']]=='GW-WS-IT-04'),default=None))
last=None
for f in ['endpoint/endpoint_2027-10.jsonl']:
    for line in open(f):
        if '"GW-WS-IT-04"' in line: last=line[:160]
print('last IT-04 endpoint event',last)
