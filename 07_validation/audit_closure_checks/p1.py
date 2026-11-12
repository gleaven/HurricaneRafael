import csv,glob,json,re,collections,ipaddress,os,sys
from datetime import datetime,timedelta
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
def zeek(p):
    with open(p,encoding='utf-8') as f:
        fields=None
        for ln in f:
            if ln.startswith('#fields'): fields=ln.rstrip('\n').split('\t')[1:]; continue
            if ln.startswith('#') or not ln.strip(): continue
            if fields is None:
                try: yield json.loads(ln); continue
                except Exception: return
            yield dict(zip(fields,ln.rstrip('\n').split('\t')))
C=collections.Counter
# ---- D2-01 / D2-06 zeek
first=open(glob.glob(O+'network_logs/zeek/2027-09-11/conn.log')[0],encoding='utf-8').read(400)
print('zeek head:',first[:300].replace('\n',' | '))
tld=C(); ext_resp=C(); ext_orig=C(); svc=C(); state=C(); svcport=C(); dns_uid=set(); conn_uid=set(); nconn=0; ndns=0; dnsq=C()
priv=[ipaddress.ip_network(x) for x in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
def internal(a):
    try: ip=ipaddress.ip_address(a)
    except Exception: return True
    return any(ip in n for n in priv)
for d in sorted(glob.glob(O+'network_logs/zeek/*/')):
    for r in zeek(d+'conn.log'):
        nconn+=1; conn_uid.add(r['uid']); state[r.get('conn_state')]+=1; svc[r.get('service')]+=1
        svcport[(r.get('service'),r.get('id.resp_p'))]+=1
        if not internal(r['id.resp_h']): ext_resp[r['id.resp_h']]+=1
        if not internal(r['id.orig_h']): ext_orig[r['id.orig_h']]+=1
    for r in zeek(d+'dns.log'):
        ndns+=1; dns_uid.add(r['uid']); q=r.get('query',''); dnsq[q.rsplit('.',1)[-1]]+=1
    for r in zeek(d+'ssl.log'):
        tld[r.get('server_name','').rsplit('.',1)[-1]]+=1
print('D2-01 ssl TLDs',tld.most_common(8)); print('  dns TLDs',dnsq.most_common(8))
print('  distinct external responders',len(ext_resp),'flows',sum(ext_resp.values()),'top',ext_resp.most_common(4)); print('  distinct external originators',len(ext_orig),'flows',sum(ext_orig.values()))
print('  services',svc.most_common(20))
for s in ('rdp','modbus','dnp3'): print('  svc',s,svc[s])
print('  port 4000 flows',sum(v for (s,p),v in svcport.items() if p=='4000'))
print('D2-06 conn',nconn,'dns rows',ndns,'dns uids in conn',len(dns_uid&conn_uid),'of',len(dns_uid)); print('  conn_state',state.most_common())
bad=C()
exp={'krb':{'88'},'ldap':{'389','636','3268'},'smb':{'445','139'},'dns':{'53'},'rdp':{'3389'},'ssl':None,'http':None}
for (s,p),v in svcport.items():
    if s in exp and exp[s] is not None and p not in exp[s]: bad[(s,p)]+=v
print('  service/port mismatches',sum(bad.values()),bad.most_common(6))
# ---- D2-02 drones
det=[]; 
for f in sorted(glob.glob(O+'drone_detections/detections_*.csv')): det+=list(rows(f))
bys=collections.defaultdict(list)
for r in det:
    t=r['track_id']
    if t: bys[r['sensor_id']].append((r['time_utc'],t))
nonmono=0; ex=[]
for s,L in bys.items():
    seen={}; 
    for tm,t in L:
        seen.setdefault(t,tm)
    order=sorted(seen.items(),key=lambda kv:kv[1])
    seqs=[int(re.search(r'(\d+)$',t).group(1)) for t,_ in order if re.search(r'(\d+)$',t)]
    bad_=sum(1 for a,b in zip(seqs,seqs[1:]) if b<a)
    nonmono+=bad_
    if bad_ and len(ex)<3: ex.append((s,order[:3]))
print('D2-02 track sequence inversions (first-seen order) across sensors:',nonmono,ex)
print('  rf_signature',C(r['rf_signature'] for r in det if r['rf_signature']).most_common(12))
print('  classification',C(r['classification'] for r in det).most_common(12))
sr=list(rows(O+'drone_detections/sighting_reports.csv'))
print('  sighting reports',len(sr),'first',sr[0]['report_id'],sr[0]['time_utc'],'ids in time order',[r['report_id'] for r in sr]==[r['report_id'] for r in sorted(sr,key=lambda r:r['time_utc'])])
print('  dispositions',C(r['disposition'] for r in sr).most_common()); print('  reports before 2027-09-15:',sum(1 for r in sr if r['time_utc']<'2027-09-15'))
