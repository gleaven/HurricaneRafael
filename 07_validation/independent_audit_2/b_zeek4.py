from common import *
import pickle, collections
z=pickle.load(open('/tmp/zeek.pkl','rb'))
f=lambda t:dt.datetime.fromtimestamp(float(t),dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
for k,d,r in z['keep']:
    if k=='dns' and ('meridian' in r['query'] or 'vantagesec' in r['query']) and not r['query'].endswith('.example'): print('DNS',f(r['ts']),r['id.orig_h'],r['query'],r.get('answers'))
print('IT-04 SNI',collections.Counter((r['server_name'],r['id.resp_h']) for k,d,r in z['keep'] if k=='ssl' and r['id.orig_h']=='10.14.22.47').most_common(6))
print('lookalike SNI rows by host',collections.Counter((r['id.orig_h'],r['server_name']) for k,d,r in z['keep'] if k=='ssl' and not r['server_name'].endswith('.example')).most_common(8))
print('non-.example dns queries from anyone',collections.Counter(r['query'] for k,d,r in z['keep'] if k=='dns' and not r['query'].endswith('.example')).most_common(8))
print('notices kept',collections.Counter(r['note'] for k,d,r in z['keep'] if k=='notice'))
it=z['it04']; c2=[r for r in it if r['id.resp_h']=='104.21.88.43']
print('C2 rows near 08-31T03:17',[(f(r['ts']),r['duration'],r['orig_bytes'],r['resp_bytes']) for r in c2 if f(r['ts']).startswith('2027-08-31T03')])
import statistics
print('C2 per day count',collections.Counter(collections.Counter(f(r['ts'])[:10] for r in c2).values()),'bytes out distinct',len({r['orig_bytes'] for r in c2}),'dur',collections.Counter(r['duration'][:3] for r in c2).most_common(4))
# remote sessions vs conn: get conn rows to JMP 10.72.4.88:443 & from external
ras=load('network_logs/audit/remote_access_sessions.csv')
ext=[r for r in ras if r['src_network']!='internal']
print('external sessions by src ip prefix',collections.Counter(r['src_ip'].split('.')[0] for r in ext).most_common(6))
jm=[c for c in z['cross'] if c[2]=='10.72.4.88']
print('flows to JMP',len(jm),'from zones',collections.Counter(c[5] for c in jm))
jt=sorted(c[0] for c in jm)
import bisect
def has(t,ip=None):
    i=bisect.bisect_left(jt,t-30); return i<len(jt) and jt[i]<=t+30
m=sum(1 for r in ras if has(ts(r['login_utc']).timestamp())); print('remote sessions with a conn to JMP within 30 s of login:',m,'of',len(ras))
mi=[r for r in ras if r['src_network']=='internal']; print('  internal sessions matched',sum(1 for r in mi if has(ts(r['login_utc']).timestamp())),'of',len(mi))
me=[r for r in ext if r['src_country']=='US']; print('  external-US sessions matched',sum(1 for r in me if has(ts(r['login_utc']).timestamp())),'of',len(me))
ipset={(c[1]) for c in jm}; print('  ext-US session src_ip appears as conn orig to JMP',sum(1 for r in me if r['src_ip'] in ipset),'of',len(me))
print('JMP flows durations vs session durations sample',[(f(c[0]),c[1],c[9]) for c in jm if c[5] is None][:14])
# resumption of it->ot-dmz after window
a=dt.datetime(2027,10,12,12,tzinfo=dt.timezone.utc).timestamp()
nxt=[c for c in z['cross'] if c[0]>a and c[6]=='ot-dmz']; print('first IT->ot-dmz flow after isolation',f(nxt[0][0]) if nxt else None, 'last before', f(max(c[0] for c in z['cross'] if c[0]<a and c[6]=='ot-dmz')))
print('ras first session after 10-12T12',min(r['login_utc'] for r in ras if r['login_utc']>'2027-10-12T12'))
