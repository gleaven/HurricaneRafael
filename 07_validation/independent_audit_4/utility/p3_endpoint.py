#!/usr/bin/env python3
"""Item 19 + pass 3: endpoint telemetry internals and joins for one month (arg), e.g. 2027-09."""
import sys,collections,json,pickle,re; sys.path.insert(0,sys.path[0])
from lib import *
m=sys.argv[1]
EV=[json.loads(l) for l in open(f'endpoint/endpoint_{m}.jsonl',encoding='utf-8')]
print(m,'events',len(EV))
reg_=reg(); hip={x['hostname']:x['ip'] for x in reg_['hosts']}; hos={x['hostname']:x.get('os') for x in reg_['hosts']}
print('hosts',len({d['host'] for d in EV}),'non-windows hosts with events',{d['host'] for d in EV if not (hos.get(d['host']) or '').startswith('Windows')})
print('pids not multiple of 4',sum(1 for d in EV if d['pid']%4),'src_ip != host ip',sum(1 for d in EV if d['event_type']=='network_connect' and d['src_ip']!=hip.get(d['host'])))
# process_start coverage: every (host,pid,image) used in other events has a start
ps={}
for d in EV:
    if d['event_type']=='process_start': ps[(d['host'],d['pid'],d['image'])]=d
oth=[d for d in EV if d['event_type']!='process_start']
nos=collections.Counter(d['image'].split('\\')[-1] for d in oth if (d['host'],d['pid'],d['image']) not in ps)
print('non-start events',len(oth),'whose (host,pid,image) has no process_start in the month',sum(nos.values()),nos.most_common(8))
late=sum(1 for d in oth if (d['host'],d['pid'],d['image']) in ps and ps[(d['host'],d['pid'],d['image'])]['time_utc']>d['time_utc']); print('events before their process start',late)
pu=sum(1 for d in oth if (d['host'],d['pid'],d['image']) in ps and ps[(d['host'],d['pid'],d['image'])]['user']!=d['user']); print('event user != process owner',pu)
# pid reuse: same host+pid with different images overlapping
pi=collections.defaultdict(set)
for d in EV: pi[(d['host'],d['pid'])].add(d['image'])
print('host+pid with >1 image',sum(1 for v in pi.values() if len(v)>1),'of',len(pi))
st=[d for d in EV if d['event_type']=='process_start']
print('process images',len({d['image'] for d in st}),'starts',len(st),'top',collections.Counter(d['image'].split('\\')[-1] for d in st).most_common(12))
print('parent images',collections.Counter(d['parent_image'].split('\\')[-1] for d in st).most_common(8),'signer',collections.Counter(d['signer'] for d in st).most_common(6))
sh=collections.defaultdict(set)
for d in st: sh[d['image']].add(d['sha256'])
print('images with >1 hash',sum(1 for v in sh.values() if len(v)>1),'unsigned images',len({d['image'] for d in st if not d['signer']}))
ppid_ok=sum(1 for d in st if (d['host'],d['ppid'],d['parent_image']) in ps); print('process_start whose parent (host,ppid,image) has its own start',ppid_ok,'of',len(st))
usb=[d for d in EV if d['event_type']=='usb_device']; print('usb',len(usb),'distinct serials',len({d['device_serial']} if False else {d['device_serial'] for d in usb}),'models',collections.Counter((d['device_vendor'],d['device_model']) for d in usb).most_common(6))
# join to conn
conn=[r for r in zeek('conn') if T(r[0])[:7]==m]
ck=collections.defaultdict(list)
for r in conn: ck[(r[2],r[3],r[4],r[5])].append(float(r[0]))
nc=[d for d in EV if d['event_type']=='network_connect']
mm=0;off=0
for d in nc:
    c=ck.get((d['src_ip'],str(d['src_port']),d['dst_ip'],str(d['dst_port'])))
    if not c: mm+=1; continue
    if min(abs(x-E(d['time_utc'])) for x in c)>1.0: off+=1
print('network_connect',len(nc),'no conn flow',mm,'time off>1s',off,'protocols',collections.Counter(d['protocol'] for d in nc))
win={x['ip'] for x in reg_['hosts'] if (x.get('os') or '').startswith('Windows')}
ek={(d['src_ip'],str(d['src_port']),d['dst_ip'],str(d['dst_port'])) for d in nc}
wf=[r for r in conn if r[2] in win and r[6] in('tcp','udp') and r[7]!='dns']
missing=[r for r in wf if (r[2],r[3],r[4],r[5]) not in ek]
print('conn flows from Windows hosts (non-dns)',len(wf),'without network_connect',len(missing),collections.Counter((r[7],r[5],r[11]) for r in missing).most_common(8))
dq=[d for d in EV if d['event_type']=='dns_query']
dk=collections.defaultdict(list)
for r in zeek('dns'):
    if T(r[0])[:7]==m: dk[(r[2],r[8])].append(float(r[0]))
dm=sum(1 for d in dq if not any(abs(x-E(d['time_utc']))<=1.5 for x in dk.get((hip.get(d['host']),d['query']),[])))
print('dns_query',len(dq),'without dns.log row within 1.5s',dm)
dnsrows=sum(len(v) for k,v in dk.items() if k[0] in win); print('dns.log rows from windows hosts',dnsrows)
# user events inside a logon session
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
lo={}
for d in W:
    if d['event_id'] in(4634,4647): lo.setdefault((d['host'],d['logon_id']),E(d['time_utc']))
sess=collections.defaultdict(list)
for d in W:
    if d['event_id']==4624 and d['logon_type'] in(2,10,11): sess[(d['host'],d['user'])].append((E(d['time_utc']),lo.get((d['host'],d['logon_id']),9e12)))
ue=[d for d in EV if d['user'] not in('SYSTEM','LOCAL SERVICE','NETWORK SERVICE') and not d['user'].startswith('svc_')]
out=[d for d in ue if not any(a-5<=E(d['time_utc'])<=b+5 for a,b in sess.get((d['host'],d['user']),[]))]
print('user-owned events',len(ue),'outside an interactive/RDP session of that user on that host',len(out),collections.Counter((d['host'],d['user']) for d in out).most_common(5))
print('system users',collections.Counter(d['user'] for d in EV if d['user'] in('SYSTEM','LOCAL SERVICE','NETWORK SERVICE') or d['user'].startswith('svc_')).most_common(8))
