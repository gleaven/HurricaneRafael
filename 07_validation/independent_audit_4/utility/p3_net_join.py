#!/usr/bin/env python3
"""Pass 3 / items 10,11,27: firewall<->zeek, proxy<->zeek/ssl/http/dns joins over the whole span."""
import sys,collections,re,ipaddress; sys.path.insert(0,sys.path[0])
from lib import *
conn=zeek('conn')
ck={}
for r in conn: ck[(r[2],r[3],r[4],r[5],r[6])]=ck.get((r[2],r[3],r[4],r[5],r[6]),[])+[r]
dup=sum(1 for v in ck.values() if len(v)>1); print('conn rows',len(conn),'5-tuples reused',dup)
def zone(ip):
    if ip.startswith('10.72.4.'): return 'otdmz'
    if ip.startswith('10.72.'): return 'ot'
    if ip.startswith('172.20.5.'): return 'inetdmz'
    if ip.startswith('10.'): return 'corp'
    return 'inet'
for name in ('fw_edge','fw_ot'):
    h,F=fam(name); ix={n:i for i,n in enumerate(h)}
    al=[r for r in F if r[ix['action']]=='allow']
    m=0;tb=0;bb=0;db=0;miss=[]
    seen=set()
    for r in al:
        k=(r[ix['src_ip']],r[ix['src_port']],r[ix['dst_ip']],r[ix['dst_port']],r[ix['proto']])
        c=ck.get(k)
        if not c: miss.append(r); continue
        end=E(r[ix['time_utc']]); best=min(c,key=lambda x:abs(float(x[0])+float(x[8] if x[8]!='-' else 0)-end))
        m+=1; seen.add(best[1])
        if abs(float(best[0])+float(best[8] if best[8]!='-' else 0)-end)>1.5: tb+=1
        if (r[ix['bytes_sent']],r[ix['bytes_recv']])!=(best[17],best[19]): bb+=1
        if abs(float(r[ix['duration_s']])-float(best[8] if best[8]!='-' else 0))>0.001: db+=1
    print(name,'allow rows',len(al),'matched',m,'no conn row',len(miss),'end-time off>1.5s',tb,'bytes != ip_bytes',bb,'duration diff',db)
    # reverse: conn flows that should cross
    if name=='fw_edge':
        cross=[r for r in conn if (zone(r[2])=='inet')!=(zone(r[4])=='inet') or (zone(r[2])=='inetdmz')!=(zone(r[4])=='inetdmz')]
    else:
        def side(z): return {'corp':'it','inet':'it','inetdmz':'it','otdmz':'dmz','ot':'ot'}[z]
        cross=[r for r in conn if side(zone(r[2]))!=side(zone(r[4]))]
    nm=[r for r in cross if r[1] not in seen]
    print('   conn flows crossing',len(cross),'without fw allow row',len(nm),collections.Counter((r[6],r[5],r[11]) for r in nm).most_common(6))
    dn=[r for r in F if r[ix['action']]=='deny']
    dm=sum(1 for r in dn if (r[ix['src_ip']],r[ix['src_port']],r[ix['dst_ip']],r[ix['dst_port']],r[ix['proto']]) in ck)
    print('   deny rows',len(dn),'that have a conn flow',dm)
    print('   nat set for outbound', collections.Counter((zone(r[ix['src_ip']]),bool(r[ix['nat_src_ip']])) for r in al).most_common(6))
    print('   app x port sample',collections.Counter((r[ix['app']],r[ix['dst_port']]) for r in al).most_common(12))
    print('   zone labels wrong vs registry cidr:', sum(1 for r in al if (r[ix['src_zone']]=='internet')!=(zone(r[ix['src_ip']])=='inet')))
    print('   integral durations',sum(1 for r in al if float(r[ix['duration_s']])==int(float(r[ix['duration_s']]))),'session_end_reason x state',collections.Counter((r[ix['session_end_reason']]) for r in al).most_common(5))
# proxy
h,P=fam('proxy'); ix={n:i for i,n in enumerate(h)}
byc=collections.defaultdict(list)
for r in conn:
    if r[5] in('80','443'): byc[(r[2],int(float(r[0])))].append(r)
ssl={r[1]:r for r in zeek('ssl')}; http=collections.defaultdict(list)
for r in zeek('http'): http[r[1]].append(r)
st=collections.Counter()
for r in P:
    sch=r[ix['scheme']]
    if sch=='dns': continue
    t=int(E(r[ix['time_utc']])); c=byc.get((r[ix['client_ip']],t),[])+byc.get((r[ix['client_ip']],t-1),[])
    port='443' if sch=='https' else '80'
    c=[x for x in c if x[5]==port]
    if r[ix['action']]=='blocked':
        st[('blocked','has flow' if any(True for x in c if (x[1] in ssl and ssl[x[1]][8]==r[ix['host']])) else 'no flow')]+=1; continue
    ok=[x for x in c if x[9]==r[ix['bytes_out']] and x[10]==r[ix['bytes_in']]]
    if not ok: st[(sch,'no flow with same bytes')]+=1; continue
    x=ok[0]
    if sch=='https': st[(sch,'sni ok' if x[1] in ssl and ssl[x[1]][8]==r[ix['host']] else 'sni mismatch/missing')]+=1
    else:
        hh=http.get(x[1],[]); st[(sch,'host+uri ok' if any(y[8].split(':')[0]==r[ix['host']] and y[9]==r[ix['url_path']] for y in hh) else 'http mismatch/missing')]+=1
print('proxy vs zeek',sorted(st.items()))
# reverse: outbound web conn flows w/o proxy row
pk=collections.Counter((r[ix['client_ip']],r[ix['bytes_out']],r[ix['bytes_in']]) for r in P if r[ix['scheme']]!='dns' and r[ix['action']]=='allowed')
web=[r for r in conn if r[5] in('80','443') and zone(r[2])=='corp' and zone(r[4])=='inet' and r[11]=='SF']
print('outbound web SF flows',len(web),'without proxy row',sum(1 for r in web if (r[2],r[9],r[10]) not in pk))
# dns
dns=zeek('dns'); dk=collections.defaultdict(list)
for r in dns: dk[(r[2],r[8])].append(float(r[0]))
off=collections.Counter(); offs=[]
for r in P:
    if r[ix['scheme']]!='dns': continue
    t=E(r[ix['time_utc']]); c=dk.get((r[ix['client_ip']],r[ix['host']]))
    if not c: off['no dns.log row']+=1; continue
    d=min(c,key=lambda x:abs(x-t))-t; offs.append(d)
    off['<=1s' if abs(d)<=1 else '<=2s' if abs(d)<=2 else '>2s']+=1
print('proxy dns rows vs dns.log',dict(off))
h2,S=fam('siem'); i2={n:i for i,n in enumerate(h2)}
print('proxy dns rows',sum(1 for r in P if r[ix['scheme']]=='dns'),'= DNS_UNCATEGORISED alerts',sum(1 for r in S if r[i2['rule_id']]=='SE3-NET-3004'),'| blocked',sum(1 for r in P if r[ix['action']]=='blocked'),'= POLICY_BLOCKED alerts',sum(1 for r in S if r[i2['rule_id']]=='SE3-POL-5003'))
