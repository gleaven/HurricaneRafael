#!/usr/bin/env python3
"""Pass 3: join Zeek conn.log with firewall (both devices) and web proxy over the whole span. Needs /tmp/z_conn.tsv, /tmp/fw.csv, /tmp/px.csv, /tmp/z_ssl.tsv."""
import csv,collections,datetime,calendar
def ep(s): return calendar.timegm(datetime.datetime.strptime(s[:19],'%Y-%m-%dT%H:%M:%S').timetuple())
conn={}
for l in open('/tmp/z_conn.tsv'):
    f=l.rstrip('\n').split('\t')
    conn.setdefault((f[2],f[3],f[4],f[5],f[6]),[]).append(f)
print('conn rows',sum(len(v) for v in conn.values()),'distinct 5-tuples',len(conn),'5-tuples reused',sum(1 for v in conn.values() if len(v)>1))
# firewall
st=collections.Counter(); ex=collections.defaultdict(list)
for r in csv.reader(open('/tmp/fw.csv')):
    if r[2]!='allow': continue
    k=(r[6],r[7],r[8],r[9],r[10]); dev=r[1]
    c=conn.get(k)
    if not c: st[(dev,'no conn row')]+=1; ex['noconn'].append(r); continue
    end=ep(r[0]); best=min(c,key=lambda f: abs(float(f[0])+(float(f[8]) if f[8]!='-' else 0)-end))
    dt=float(best[0])+(float(best[8]) if best[8]!='-' else 0)-end
    st[(dev,'matched')]+=1
    if abs(dt)>1.5: st[(dev,'end time off >1.5s')]+=1; ex['time'].append((r,best))
    ob=best[9] if best[9]!='-' else '0'; rb=best[10] if best[10]!='-' else '0'
    if (r[12],r[13])!=(ob,rb): st[(dev,'bytes differ')]+=1; ex['bytes'].append((r[12],r[13],ob,rb,r[11]))
    if abs(float(r[14])-(float(best[8]) if best[8]!='-' else 0))>0.001: st[(dev,'duration differs')]+=1
for k,v in sorted(st.items()): print('FW',k,v)
print(' ex bytes',ex['bytes'][:5]); print(' ex noconn',[x[:12] for x in ex['noconn'][:3]])
# conn rows that should be in a firewall log but are not
fwk=collections.Counter()
for r in csv.reader(open('/tmp/fw.csv')):
    if r[2]=='allow': fwk[(r[1],r[6],r[7],r[8],r[9],r[10])]+=1
import ipaddress
def zone(ip):
    if ip.startswith('10.72.4.'): return 'otdmz'
    if ip.startswith('10.72.'): return 'ot'
    if ip.startswith('10.14.') : return 'corp'
    if ip.startswith('172.20.5.'): return 'inetdmz'
    return 'inet'
miss=collections.Counter(); tot=collections.Counter()
for k,v in conn.items():
    zo,zr=zone(k[0]),zone(k[2])
    for f in v:
        if f[11] in('S0','REJ') : continue
        if zo!=zr and 'inet' in (zo,zr):
            tot[('EDGE',zo,zr)]+=1
            if not fwk.get(('GW-FW-EDGE-01',)+k): miss[('EDGE',zo,zr)]+=1
        if zo!=zr and ({'ot','otdmz'}&{zo,zr}) :
            tot[('OT',zo,zr)]+=1
            if not fwk.get(('GW-OT-FW-01',)+k): miss[('OT',zo,zr)]+=1
for k in sorted(tot): print('conn crossing',k,tot[k],'missing in fw',miss[k])
# proxy
ssl={}
for l in open('/tmp/z_ssl.tsv'):
    f=l.rstrip('\n').split('\t'); ssl[f[1]]=f[8]
bysec=collections.defaultdict(list)
for k,v in conn.items():
    for f in v:
        if f[5] in('443','80','8443','53'): bysec[(k[0],int(float(f[0])))].append(f)
ps=collections.Counter(); pex=[]
for r in csv.reader(open('/tmp/px.csv')):
    t=ep(r[0]); kind=(r[4],r[8])
    c=bysec.get((r[1],t),[])+bysec.get((r[1],t-1),[])+bysec.get((r[1],t+1),[])
    want={'https':'443','http':'80','dns':'53'}[r[4]]
    c=[f for f in c if f[5]==want or (want=='443' and f[5]=='8443')]
    if r[8]=='blocked':
        ps[(kind,'has flow' if c else 'no flow')]+=1; continue
    if not c: ps[(kind,'NO conn row')]+=1; pex.append(r); continue
    ps[(kind,'conn found')]+=1
    if r[4]=='https':
        sn=[ssl.get(f[1]) for f in c]
        if r[5] in sn: ps[(kind,'sni match')]+=1
        elif any(s is None for s in sn): ps[(kind,'no ssl.log row')]+=1
        else: ps[(kind,'sni MISMATCH')]+=1
    if r[4] in('https','http'):
        if any((f[9],f[10])==(r[10],r[11]) for f in c): ps[(kind,'bytes equal conn')]+=1
for k,v in sorted(ps.items()): print('PROXY',k,v)
print(' ex',pex[:3])
# conn web flows from user zones not in proxy
