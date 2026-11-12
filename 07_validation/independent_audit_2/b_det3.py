from common import *
import pickle, collections, statistics, math, sys
sys.path.insert(0,ROOT+'/scripts'); import geo
tr=pickle.load(open('/tmp/tracks.pkl','rb'))
def maj(d): return d['cls'].most_common(1)[0][0]
unk=[(k,d) for k,d in tr.items() if maj(d)=='unknown' and d['type']=='radar_plot']
print('unknown radar tracks',len(unk))
def feat(d):
    return dict(n=d['n'],dur=(ts(d['t1'])-ts(d['t0'])).total_seconds(),alt=statistics.mean(d['alts']),rcs=statistics.mean(d['rcs']),sp=statistics.mean(d['sp']),hr=local(ts(d['t0'])).hour)
F={k:feat(d) for k,d in unk}
import numpy as np
for key in ('n','dur','alt','rcs','sp'):
    v=np.array([f[key] for f in F.values()]); print(key,'quantiles',np.round(np.quantile(v,[0,.1,.5,.9,.99,1]),4))
# long-duration unknown tracks
long=[(k,F[k]) for k,d in unk if F[k]['dur']>600]
print('unknown tracks >10 min:',len(long))
for k,f in sorted(long,key=lambda x:tr[x[0]]['t0']): print('  ',k,tr[k]['t0'],tr[k]['t1'],'D',dday(ts(tr[k]['t0'])),{a:round(b,4) for a,b in f.items()},'alert',tr[k]['alert'],dict(tr[k]['cls']))
# bird/clutter stats for comparison
for c in ('bird','clutter','uas','aircraft'):
    v=[d for d in tr.values() if maj(d)==c and d['type']=='radar_plot']
    print(c,'n',len(v),'dur q',np.round(np.quantile([(ts(d['t1'])-ts(d['t0'])).total_seconds() for d in v],[.5,.9,1])),'alt q',np.round(np.quantile([statistics.mean(d['alts']) for d in v],[.1,.5,.9,1])),'rcs q',np.round(np.quantile([statistics.mean(d['rcs']) for d in v],[.1,.5,.9,1]),4),'sp',np.round(np.quantile([statistics.mean(d['sp']) for d in v],[.1,.5,.9,1]),1))
# all tracks at night on NASCC sensors D+1..D+11
print('NASCC sensor tracks per day D-3..D+14 (all classes):')
c=collections.Counter((dday(ts(d['t0'])),k[0]) for k,d in tr.items() if k[0].startswith('NASCC'))
for dd in range(-4,16): print('  D',dd,{s[-2:]:c[(dd,s)] for s in ['NASCC-PS-01','NASCC-PS-02','NASCC-PS-03','NASCC-PS-04','NASCC-PS-05']})
c=collections.Counter((dday(ts(d['t0'])),k[0]) for k,d in tr.items() if k[0].startswith('USCG'))
print('USCG buoys per day D-12..D+6'); 
for dd in range(-12,7): print('  D',dd,{s[-3:]:c[(dd,s)] for s in ['USCG-RDR-R14','USCG-RDR-R18','USCG-RDR-R22']})
