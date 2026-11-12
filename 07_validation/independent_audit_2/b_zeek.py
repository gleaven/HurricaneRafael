from common import *
import glob, collections, pickle, ipaddress
Z=SRC+'/network_logs/zeek'
reg=json.load(open(ROOT+'/06_data_streams/gw_host_registry.json'))
ips={h['ip']:h for h in reg['hosts']}
zones=[(ipaddress.ip_network(z['cidr']),z['zone'],z['purdue_level']) for z in reg['network_zones']]
def zone(ip):
    try: a=ipaddress.ip_address(ip)
    except: return None
    for n,z,l in zones:
        if a in n: return z
    return None
def read(path):
    fields=None
    for line in open(path):
        if line.startswith('#fields'): fields=line.rstrip('\n').split('\t')[1:]; continue
        if line.startswith('#'): continue
        yield dict(zip(fields,line.rstrip('\n').split('\t')))
svcport=collections.Counter(); unk=collections.Counter(); cross=[]; nconn=0; states=collections.Counter()
ssl_miss=0; ssl_n=0; ssl_tsbad=0; dns_n=0; dns_inconn=0; dns_tuple_inconn=0; daybad=0
keep=[]; dayconn={}; it04=[]; big=[]; extint=collections.Counter(); notices=collections.Counter(); dns_names=collections.Counter()
c2_ips=set(); ot_ext=[]
for d in sorted(os.listdir(Z)):
    cu={}; tup=set(); n=0
    for r in read(f'{Z}/{d}/conn.log'):
        n+=1; cu[r['uid']]=r; tup.add((r['id.orig_h'],r['id.orig_p'],r['id.resp_h'],r['id.resp_p']))
        svcport[(r['proto'],r['service'],r['id.resp_p'] if int(r['id.resp_p'])<10000 else 'high')]+=1
        states[r['conn_state']]+=1
        t=float(r['ts'])
        if dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%Y-%m-%d')!=d: daybad+=1
        zo,zr=zone(r['id.orig_h']),zone(r['id.resp_h'])
        for ip,zz in ((r['id.orig_h'],zo),(r['id.resp_h'],zr)):
            if (ip.startswith('10.') or ip.startswith('172.20.') or ip.startswith('192.168.')) and ip not in ips: unk[ip]+=1
        oto=zo and zo.startswith('ot'); otr=zr and zr.startswith('ot')
        if oto!=otr:
            cross.append((t,r['id.orig_h'],r['id.resp_h'],r['id.resp_p'],r['service'],zo,zr,r['orig_bytes'],r['resp_bytes'],r['duration']))
        if r['id.orig_h']=='10.14.22.47' or r['id.resp_h']=='10.14.22.47': it04.append(r)
        try:
            if int(r['orig_bytes'])+int(r['resp_bytes'])>5e8: big.append(r)
        except: pass
    dayconn[d]=n; nconn+=n
    for r in read(f'{Z}/{d}/ssl.log'):
        ssl_n+=1
        c=cu.get(r['uid'])
        if not c: ssl_miss+=1
        else:
            if (c['id.orig_h'],c['id.orig_p'],c['id.resp_h'],c['id.resp_p'])!=(r['id.orig_h'],r['id.orig_p'],r['id.resp_h'],r['id.resp_p']) or not (0<=float(r['ts'])-float(c['ts'])<5) or c['service']!='ssl': ssl_tsbad+=1
        if 'meridiancontrols' in r.get('server_name','') or 'vantagesec' in r.get('server_name','') or r['id.orig_h']=='10.14.22.47': keep.append(('ssl',d,r))
    for r in read(f'{Z}/{d}/dns.log'):
        dns_n+=1
        if r['uid'] in cu: dns_inconn+=1
        if (r['id.orig_h'],r['id.orig_p'],r['id.resp_h'],r['id.resp_p']) in tup: dns_tuple_inconn+=1
        if 'meridiancontrols' in r.get('query','') or 'vantagesec' in r.get('query','') or r['id.orig_h']=='10.14.22.47': keep.append(('dns',d,r))
    for r in read(f'{Z}/{d}/notice.log'):
        notices[r.get('note','?')]+=1
        if d>='2027-08-25' and r.get('note','').split('::')[0] not in ('SSL','DNS'): keep.append(('notice',d,r))
pickle.dump(dict(cross=cross,it04=it04,big=big,keep=keep,dayconn=dayconn,unk=dict(unk)),open('/tmp/zeek.pkl','wb'))
print('conn rows',nconn,'ts outside own day',daybad)
print('ssl rows',ssl_n,'uid not in conn',ssl_miss,'tuple/ts/service mismatch',ssl_tsbad)
print('dns rows',dns_n,'uid in conn',dns_inconn,'same 4-tuple in conn',dns_tuple_inconn)
print('internal IPs not in registry: distinct',len(unk),'rows',sum(unk.values()),unk.most_common(8))
print('conn states',dict(states))
print('service/port:'); [print('  ',k,v) for k,v in sorted(svcport.items(),key=lambda x:-x[1])[:60]]
print('notices',dict(notices))
print('cross IT/OT flows total',len(cross))
