#!/usr/bin/env python3
"""Pass 3: endpoint telemetry (one month) vs Zeek conn/dns and vs Windows logon sessions; PID behaviour. usage: p3_endpoint_join.py 2027-09"""
import json,collections,datetime,calendar,sys,glob
m=sys.argv[1]
R="./"; B=R+"05_other_sources/network_logs/"
reg=json.load(open(R+"06_data_streams/gw_host_registry.json")); ip2h={h['ip']:h['hostname'] for h in reg['hosts']}
def ep(s): return calendar.timegm(datetime.datetime.strptime(s[:19],'%Y-%m-%dT%H:%M:%S').timetuple())+float('0.'+s[20:23])
A=ep(m+'-01T00:00:00.000'); y,mo=map(int,m.split('-')); Z=ep('%04d-%02d-01T00:00:00.000'%((y,mo+1) if mo<12 else (y+1,1)))
conn=collections.defaultdict(list)
for l in open('/tmp/z_conn.tsv'):
    f=l.split('\t',8); t=float(f[0])
    if A<=t<Z and f[6]=='tcp': conn[(f[2],f[3],f[4],f[5])].append(t)
dns=collections.defaultdict(list)
for l in open('/tmp/z_dns.tsv'):
    f=l.split('\t',9); t=float(f[0])
    if A<=t<Z: dns[(f[2],f[8])].append(t)
st=collections.Counter(); pidmod=collections.Counter(); pids=collections.Counter()
starts={}  # (host,pid,image)->time
seen_nc=set(); seen_dns=set(); orphan=collections.Counter(); userev=collections.defaultdict(list)
sysusers=collections.Counter()
for l in open(B+f"endpoint/endpoint_{m}.jsonl"):
    d=json.loads(l); e=d['event_type']; t=ep(d['time_utc'])
    pidmod[d['pid']%4]+=1
    key=(d['host'],d['pid'],d['image'])
    if e=='process_start':
        starts[key]=t; pids[(d['pid']<1000, d['image'].split('\\')[-1])]+=1
    else:
        if key not in starts: orphan[(e,d['image'].split('\\')[-1])]+=1
        else: st[('linked',e)]+=1
    if d['user'] not in('SYSTEM','LOCAL SERVICE','NETWORK SERVICE'): userev[(d['host'],d['user'])].append(t)
    else: sysusers[d['user']]+=1
    if e=='network_connect':
        k=(d['src_ip'],str(d['src_port']),d['dst_ip'],str(d['dst_port'])); c=conn.get(k)
        if c and min(abs(x-t) for x in c)<=0.5: st['nc matched conn <=0.5s']+=1; seen_nc.add(k)
        elif c: st['nc 5-tuple found, time off']+=1
        else: st['nc NO conn row']+=1
        if ip2h.get(d['src_ip'])!=d['host']: st['nc src_ip is not the host']+=1
    if e=='dns_query':
        c=dns.get((ip2h and [ip for ip,h in ip2h.items() if h==d['host']][0], d['query']))
        if c and min(abs(x-t) for x in c)<=0.5: st['dns matched <=0.5s']+=1
        else: st['dns NOT matched']+=1
for k,v in sorted(st.items(),key=str): print(k,v)
print('pid mod 4',dict(pidmod)); print('orphans (no earlier process_start this month)',orphan.most_common(12))
win={h['hostname'] for h in reg['hosts'] if 'Windows' in h.get('os','')}
tot=0; un=0
for k,v in conn.items():
    h=ip2h.get(k[0])
    if h in win:
        tot+=len(v); 
        if k not in seen_nc: un+=len(v)
print('zeek tcp conn rows from Windows hosts',tot,'without network_connect',un)
# logon sessions
ses=collections.defaultdict(list); open_={}
for f in sorted(glob.glob(B+f"windows/security_{m}*.jsonl")):
    for l in open(f):
        if '"event_id":4624' in l or '"event_id":4634' in l:
            d=json.loads(l); k=(d['host'],d['user'],d['logon_id'])
            if d['event_id']==4624: open_[k]=ep(d['time_utc'])
            elif k in open_: ses[(d['host'],d['user'])].append((open_.pop(k),ep(d['time_utc'])))
for k,t in open_.items(): ses[(k[0],k[1])].append((t,Z))
inn=out=0; exo=[]
for k,ts in userev.items():
    s=ses.get(k,[])
    for t in ts:
        if any(a-1<=t<=b+1 for a,b in s): inn+=1
        else:
            out+=1
            if len(exo)<5: exo.append((k,datetime.datetime.utcfromtimestamp(t).isoformat()))
print('user-owned endpoint events inside a 4624..4634 session of that user on that host:',inn,'outside:',out,exo)
print('system users',sysusers)
