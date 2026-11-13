#!/usr/bin/env python3
"""Sampling rule compliance: periodic machine traffic regularity, mail rows vs SMTP flows, per-host complete classes."""
import sys,collections,statistics,csv; sys.path.insert(0,sys.path[0])
from lib import *
conn=zeek('conn'); ssl={r[1]:r[8] for r in zeek('ssl')}
by=collections.defaultdict(list)
for r in conn:
    if r[1] in ssl: by[(r[2],ssl[r[1]])].append(float(r[0]))
def desc(k):
    t=sorted(by[k]); iv=[b-a for a,b in zip(t,t[1:])]
    q=statistics.quantiles(iv,n=10) if len(iv)>10 else iv
    return (k,len(t),'interval deciles h',[round(x/3600,1) for x in q])
for k in (('10.14.22.47','update-cdn.vantagesec-telemetry.net'),('10.14.10.48','licensing.gridcad-software.com'),('10.14.21.54','metrics.pumpworks-service.com'),('10.14.21.50','telemetry.meetroom-video.com'),('10.14.22.47','telemetry.vantage-security.com'),('10.14.21.13','telemetry.vantage-security.com'),('10.14.20.16','updates.relaytech-support.net')):
    if k in by: print(desc(k))
# flows per host/day for the fleet agent
ag=collections.Counter(k[0] for k,v in by.items() if k[1]=='telemetry.vantage-security.com' for _ in v)
print('fleet agent flows per host over 181 days: median',statistics.median(ag.values()),'min',min(ag.values()),'max',max(ag.values()),'hosts',len(ag))
c2=sorted(by[('10.14.22.47','update-cdn.vantagesec-telemetry.net')]); iv=[b-a for a,b in zip(c2,c2[1:])]
print('C2 interval mean h',round(statistics.mean(iv)/3600,2),'stdev h',round(statistics.pstdev(iv)/3600,2),'cv',round(statistics.pstdev(iv)/statistics.mean(iv),2))
for k in (('10.14.10.48','licensing.gridcad-software.com'),('10.14.21.54','metrics.pumpworks-service.com'),('10.14.21.50','telemetry.meetroom-video.com'),('10.14.21.49','updates.browser-safecheck.net'),('10.14.20.16','updates.relaytech-support.net')):
    t=sorted(by[k]); iv=[b-a for a,b in zip(t,t[1:])]; print('  decoy',k[1],len(t),'mean h',round(statistics.mean(iv)/3600,2),'cv',round(statistics.pstdev(iv)/statistics.mean(iv),2),'night share(00-06 local)',round(sum(1 for x in t if 5<=((x%86400)/3600)<11)/len(t),2))
print('  C2 night share',round(sum(1 for x in c2 if 5<=((x%86400)/3600)<11)/len(c2),2))
# host-off behaviour: do decoy periodic flows stop on weekends (workstation off) while C2 continues?
import datetime
def wk(t): return datetime.datetime.utcfromtimestamp(t-5*3600).weekday()>=5
print('  weekend share: C2',round(sum(wk(x) for x in c2)/len(c2),2),[ (k[1][:18],round(sum(wk(x) for x in by[k])/len(by[k]),2)) for k in (('10.14.10.48','licensing.gridcad-software.com'),('10.14.21.54','metrics.pumpworks-service.com'),('10.14.21.50','telemetry.meetroom-video.com'),('10.14.21.49','updates.browser-safecheck.net'),('10.14.22.47','telemetry.vantage-security.com'))])
# IT-04 on/off: boots & other activity while beaconing
# mail
M=audit('mail_gateway_cbpwa')
smtp=collections.defaultdict(list)
for r in conn:
    if r[5]=='25': smtp[(r[4],int(float(r[0])))].append(r)
inb=[m for m in M if m['direction']=='inbound']
hit=sum(1 for m in inb if any((('172.20.5.10',int(E(m['time_utc']))+d) in smtp) for d in (-3,-2,-1,0,1,2,3)))
print('inbound mail rows',len(inb),'with an SMTP flow to the gateway within 3 s',hit,'| inbound smtp flows to gateway',sum(len(v) for k,v in smtp.items() if k[0]=='172.20.5.10'))
lure=[m for m in M if 'FEMA-PREP' in m['attachment_names']][0]; t=int(E(lure['time_utc']))
fl=[r for d in range(-5,6) for r in smtp.get(('172.20.5.10',t+d),[])]
print('lure SMTP flow',[(T(r[0]),r[2],r[8],r[9],r[10],r[11]) for r in fl],'mail size',lure['size_bytes'])
src=collections.Counter(r[2] for k,v in smtp.items() if k[0]=='172.20.5.10' for r in v); print('  smtp sources distinct',len(src),'lure src flows overall',[src[r[2]] for r in fl])
sz=sum(1 for m in inb[:3000] if any(int(r[9])>=int(m['size_bytes']) for d in (-3,-2,-1,0,1,2,3) for r in smtp.get(('172.20.5.10',int(E(m['time_utc']))+d),[]))); print('  first 3000 inbound rows whose flow carried >= message size',sz)
rej=[m for m in inb if m['action']=='rejected'][:2000]; print('  rejected (spoofed) rows with flow',sum(1 for m in rej if any((('172.20.5.10',int(E(m['time_utc']))+d) in smtp) for d in (-3,-2,-1,0,1,2,3))),'of',len(rej))
out=[m for m in M if m['direction']=='outbound']; print('outbound rows',len(out),'gateway->internet smtp flows',sum(1 for r in conn if r[2]=='172.20.5.10' and r[5]=='25'),'| internal rows',sum(m['direction']=='internal' for m in M),'DMZ->mail server flows',sum(1 for r in conn if r[2]=='172.20.5.10' and r[4]=='10.14.10.30'))
