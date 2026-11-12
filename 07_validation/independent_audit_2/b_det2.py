from common import *
import pickle, collections, statistics, math
tr=pickle.load(open('/tmp/tracks.pkl','rb'))
def maj(d): return d['cls'].most_common(1)[0][0]
# uas tracks: with auth vs without
uas=[(k,d) for k,d in tr.items() if 'uas' in d['cls']]
print('tracks with any uas class',len(uas),'with auth',sum(1 for k,d in uas if d['auth']),'with remote id',sum(1 for k,d in uas if d['rid']))
noauth=[(k,d) for k,d in uas if not d['auth']]
print('uas without authorization:',len(noauth))
for k,d in sorted(noauth,key=lambda x:x[1]['t0']): print('  ',k,d['t0'],d['t1'],d['n'],dict(d['cls']),'alt',round(statistics.mean(d['alts'])) if d['alts'] else None,'rcs',round(statistics.mean(d['rcs']),4) if d['rcs'] else None,'alert',d['alert'],'D',dday(ts(d['t0'])),d['rf'])
# class by sensor-type and day distribution
bycls=collections.defaultdict(collections.Counter)
for k,d in tr.items(): bycls[maj(d)][dday(ts(d['t0']))]+=1
for c,v in bycls.items(): print(c,'tracks',sum(v.values()),'days',min(v),max(v),'days with zero between',[x for x in range(min(v),max(v)+1) if x not in v][:30])
# rf rare signatures
for k,d in tr.items():
    if d['rf'] in ('analog-style video downlink burst','frequency-hopping burst, data link','frequency-hopping, 2.4 GHz control link'): print('RARE RF',k,d['t0'],d['t1'],d['n'],d['rf'],d['rfmhz'],dict(d['cls']),d['brg'][:3],d['dur'])
# ESM sensor rows by day
esm=collections.Counter(dday(ts(d['t0'])) for k,d in tr.items() if k[0]=='ESM-CAMCC04')
print('ESM tracks by day',sorted(esm.items()))
ps5=[(k,d['t0'],d['rf'],dict(d['cls'])) for k,d in tr.items() if k[0]=='NASCC-PS-05']; print(ps5)
