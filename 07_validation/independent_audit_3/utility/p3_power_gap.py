#!/usr/bin/env python3
"""Pass 3: hosts with System 6008 (unexpected shutdown) in Sept 2027: for each, the last record from that host in every log before its restart (6005/6008), to test 'a host that is off writes nothing'."""
import json,csv,collections,datetime,glob
R="./"
B=R+"05_other_sources/network_logs/"
reg=json.load(open(R+"06_data_streams/gw_host_registry.json"))
ip2h={h['ip']:h['hostname'] for h in reg['hosts']}
back={}
for l in open(B+"windows/system_2027-09.jsonl"):
    d=json.loads(l)
    if d['event_id']==6008: back[d['host']]=d['time_utc'][:19]
print('hosts with 6008',len(back),min(back.values()),max(back.values()))
ev=collections.defaultdict(list)  # host -> [(time, src)]
A,Z="2027-09-13T00:00:00","2027-09-23T00:00:00"
for f,src in [(B+"windows/security_2027-09.jsonl",'winsec'),(B+"windows/system_2027-09.jsonl",'winsys'),(B+"windows/defender_2027-09.jsonl",'windef'),(B+"endpoint/endpoint_2027-09.jsonl",'endpoint')]:
    for l in open(f):
        t=l[13:32]
        if A<=t<Z:
            d=json.loads(l)
            if d['host'] in back: ev[d['host']].append((t,src+':'+str(d.get('event_id',d.get('event_type')))))
for r in csv.DictReader(open(B+"proxy/web_proxy_2027-09.csv")):
    h=ip2h.get(r['client_ip']); t=r['time_utc'][:19]
    if h in back and A<=t<Z: ev[h].append((t,'proxy'))
for r in csv.DictReader(open(B+"dhcp/dhcp_leases_2027-09.csv")):
    h=r['hostname']; t=r['time_utc'][:19]
    if h in back and A<=t<Z: ev[h].append((t,'dhcp'))
for dd in range(13,23):
    for l in open(B+f"zeek/2027-09-{dd}/conn.log"):
        if l[0]=='#': continue
        f=l.split('\t',4); h=ip2h.get(f[2])
        if h in back: ev[h].append((datetime.datetime.utcfromtimestamp(float(f[0])).strftime('%Y-%m-%dT%H:%M:%S'),'zeek'))
for r in csv.DictReader(open(B+"siem/siem_alerts_2027-09.csv")):
    h=r['src_host']; t=r['time_utc'][:19]
    if h in back and A<=t<Z: ev[h].append((t,'siem:'+r['rule_name']))
P=lambda s: datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M:%S')
gaps=[]; srcs=collections.Counter(); inwin=collections.Counter(); ex=[]
OUT="2027-09-14T10:00:00"   # canon: outage ramps 06:00-10:00Z
for h,tb in back.items():
    before=[e for e in ev[h] if e[0]<tb and not e[1].startswith('winsys:600') and not e[1].startswith('siem')]
    last=max(before) if before else None
    if last:
        g=(P(tb)-P(last[0])).total_seconds()/3600; gaps.append(g); srcs[last[1].split(':')[0]]+=1
    for e in before:
        if e[0]>=OUT: inwin[e[1]]+=1; 
        if e[0]>=OUT and len(ex)<12: ex.append((h,tb,e))
import statistics
gaps.sort(); print('gap hours last-record -> restart: min %.2f p10 %.2f median %.2f max %.2f'%(gaps[0],gaps[len(gaps)//10],statistics.median(gaps),gaps[-1]))
print('n gaps <1h:',sum(g<1 for g in gaps),' <3h:',sum(g<3 for g in gaps),'of',len(gaps))
print('source of last record',srcs)
print('records between 2027-09-14T10:00Z and restart, by source:',inwin.most_common(20))
for e in ex: print(e)
rt=sorted(back.values()); print('restart times: first',rt[0],'median',rt[len(rt)//2],'last',rt[-1])
print('--- hosts whose last non-SIEM record is <20 min before the unexpected-shutdown restart')
for h,tb in sorted(back.items(),key=lambda x:x[1]):
    before=sorted(e for e in ev[h] if e[0]<tb and not e[1].startswith('winsys:600') and not e[1].startswith('siem'))
    if before and (P(tb)-P(before[-1][0])).total_seconds()<1200:
        print(h,'restart',tb,'last5',[(e[0][11:],e[1]) for e in before[-5:]])
