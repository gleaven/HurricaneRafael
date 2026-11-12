from common import *
import pickle, collections, glob
z=pickle.load(open('/tmp/zeek.pkl','rb'))
f=lambda t:dt.datetime.fromtimestamp(float(t),dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
reg=json.load(open(ROOT+'/06_data_streams/gw_host_registry.json')); ips={h['ip']:h for h in reg['hosts']}
a=dt.datetime(2027,10,12,12,tzinfo=dt.timezone.utc).timestamp(); b=dt.datetime(2027,10,19,20,tzinfo=dt.timezone.utc).timestamp()
w=[c for c in z['cross'] if a<=c[0]<b and (c[5] or '').startswith('ot')]
print('OT-origin flows crossing boundary in window',len(w),collections.Counter((c[1],ips[c[1]]['host_id'],ips[c[1]]['role'][:40],c[2] if c[2].startswith('10.') else 'internet',c[3],c[4]) for c in w).most_common(8))
allot=[c for c in z['cross'] if (c[5] or '').startswith('ot') and c[5]!='ot-dmz']
print('all OT-origin boundary flows',len(allot),collections.Counter((ips[c[1]]['host_id'],c[4],c[3]) for c in allot).most_common(6))
# it04 flows
it=z['it04']; print('IT-04 flows',len(it))
c2=[r for r in it if r['id.resp_h']=='104.21.88.43']; print('to 104.21.88.43:',len(c2),'first',f(c2[0]['ts']),'last',f(c2[-1]['ts']),'first row',c2[0]['duration'],c2[0]['orig_bytes'],c2[0]['resp_bytes'])
print('IT-04 peers',collections.Counter((r['id.orig_h'] if r['id.orig_h']!='10.14.22.47' else '>'+r['id.resp_h'],r['id.resp_p'],r['service']) for r in it).most_common(12))
print('IT-04 <-> OT',[ (f(r['ts']),r['id.orig_h'],r['id.resp_h'],r['id.resp_p'],r['service'],r['orig_bytes'],r['resp_bytes'],r['duration']) for r in it if r['id.orig_h'].startswith('10.72') or r['id.resp_h'].startswith('10.72')][:20])
print('big flows >500MB',[(f(r['ts']),r['id.orig_h'],r['id.resp_h'],r['id.resp_p'],r['orig_bytes'],r['resp_bytes']) for r in z['big']])
for k,d,r in z['keep']:
    if k=='dns' and ('meridian' in r['query'] or 'vantagesec' in r['query']): print('DNS',f(r['ts']),r['id.orig_h'],r['query'],r.get('answers'))
    if k=='ssl' and ('meridian' in r['server_name'] or 'vantagesec' in r['server_name']): pass
sn=collections.Counter((r['server_name'],r['id.resp_h']) for k,d,r in z['keep'] if k=='ssl' and r['id.orig_h']=='10.14.22.47'); print('IT-04 SNI',sn.most_common(8))
print('ssl with lookalike SNI',collections.Counter((r['id.orig_h'],r['server_name'],r['id.resp_h']) for k,d,r in z['keep'] if k=='ssl' and ('meridian' in r['server_name'] or 'vantagesec' in r['server_name'])).most_common(8))
print('non SSL/DNS notices',[(f(r['ts']),r['note'],r.get('src'),r.get('dst'),r.get('msg')) for k,d,r in z['keep'] if k=='notice'][:12])
# remote sessions vs conn
ras=load('network_logs/audit/remote_access_sessions.csv')
ext=[r for r in ras if r['src_network']!='internal']
print('external remote sessions',len(ext),'src ip sample',[r['src_ip'] for r in ext[:5]])
