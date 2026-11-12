from common import *
import collections, statistics
rs=load('public_health/wastewater_surveillance.csv'); print(list(rs[0].keys())); print(rs[0])
print(cnt(rs,'sewershed_id') if 'sewershed_id' in rs[0] else '', {k:len(cnt(rs,k)) for k in rs[0]})
tcol=[k for k in rs[0] if 'target' in k.lower() or 'pcr' in k.lower()]; print(tcol)
key='pcr_target' if 'pcr_target' in rs[0] else tcol[0]
dcol='sample_date' if 'sample_date' in rs[0] else [k for k in rs[0] if 'date' in k][0]
vcol=[k for k in rs[0] if 'conc' in k.lower() or 'ratio' in k.lower() or 'norm' in k.lower()]
print(vcol)
for tg in sorted({r[key] for r in rs}):
    v=[r for r in rs if r[key]==tg]
    print('==',tg,len(v))
    by=collections.defaultdict(list)
    for r in v: by[r[dcol]].append(r)
    out=[]
    for d in sorted(by):
        dd=(dt.date.fromisoformat(d[:10])-dt.date(2027,9,14)).days
        if -12<=dd<=45 or dd%14==0:
            out.append((dd,[ (r.get('sewershed_id','')[-2:], r[vcol[0]][:8]) for r in by[d]]))
    for o in out[:46]: print('   D',o[0],o[1])
wd=collections.Counter(dt.date.fromisoformat(r[dcol][:10]).weekday() for r in rs); print('weekday of samples',sorted(wd.items()))
ds=sorted({r[dcol] for r in rs}); print('span',ds[0],ds[-1],'sample days',len(ds))
