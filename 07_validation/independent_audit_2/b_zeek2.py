from common import *
import pickle, collections
z=pickle.load(open('/tmp/zeek.pkl','rb'))
f=lambda t:dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
cross=z['cross']
print('cross by zone pair',collections.Counter((c[5],c[6]) for c in cross).most_common(12))
a=dt.datetime(2027,10,12,12,tzinfo=dt.timezone.utc).timestamp(); b=dt.datetime(2027,10,19,20,tzinfo=dt.timezone.utc).timestamp()
w=[c for c in cross if a<=c[0]<b]
print('cross IT/OT flows in isolation window 10-12T12Z..10-19T20Z:',len(w))
print('  by zone pair',collections.Counter((c[5],c[6]) for c in w).most_common(10))
print('  by day',sorted(collections.Counter(f(c[0])[:10] for c in w).items()))
print('  sample',[(f(c[0]),)+c[1:7] for c in w[:5]])
# strict: corp(10.14.x)/external <-> ot-control/hmi/L1 (excluding ot-dmz itself)
def cls(zn): 
    if zn is None: return 'external'
    if zn=='ot-dmz': return 'ot-dmz'
    return 'ot' if zn.startswith('ot') else 'it'
print('class pairs overall',collections.Counter((cls(c[5]),cls(c[6])) for c in cross).most_common())
print('class pairs in window',collections.Counter((cls(c[5]),cls(c[6])) for c in w).most_common())
# per-day cross volume around window
dc=collections.Counter(f(c[0])[:10] for c in cross)
print('cross flows per day 10-08..10-23',[(d[5:],dc[d]) for d in sorted(dc) if '2027-10-08'<=d<='2027-10-23'])
print('total conn per day 10-08..10-23',[(d[5:],z['dayconn'][d]) for d in sorted(z['dayconn']) if '2027-10-08'<=d<='2027-10-23'])
# JMP involvement in window
print('flows involving 10.72.4.88 (JMP) in window',sum(1 for c in w if '10.72.4.88' in (c[1],c[2])), 'after 10-12T12 until 11-01', sum(1 for c in cross if a<=c[0]<dt.datetime(2027,11,1,tzinfo=dt.timezone.utc).timestamp() and '10.72.4.88' in (c[1],c[2])))
# external -> JMP flows
ext=[c for c in cross if cls(c[5])=='external']
print('external->OT flows',len(ext),collections.Counter((c[2],c[3]) for c in ext).most_common(5)); print([(f(c[0]),c[1],c[2],c[3],c[7],c[8],c[9]) for c in ext[:20]])
print('external->OT after 10-12T12',[(f(c[0]),c[1],c[2]) for c in ext if c[0]>=a][:5])
