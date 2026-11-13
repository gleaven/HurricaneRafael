#!/usr/bin/env python3
"""Pass 1 tricks on zeek conn: value counts, rare ports/services/states/history, integral durations, round bytes, top talkers, rare external dests, big uploads."""
import pickle,glob,collections,ipaddress,json
C=collections.defaultdict(collections.Counter)
rows=[]
for f in sorted(glob.glob('/tmp/c/zeek_conn_*.pkl')):
    h,r=pickle.load(open(f,'rb')); rows+=r
print('rows',len(rows))
def internal(ip): return ip.startswith('10.')
ext_first={}; ext_cnt=collections.Counter(); ext_src=collections.defaultdict(set); ext_bytes=collections.Counter()
big=[]
for r in rows:
    ts,uid,oh,op,rh,rp,proto,svc,dur,ob,rb,st,lo,lr,mb,hist,opk,oib,rpk,rib=r
    C['proto'][proto]+=1; C['service'][svc]+=1; C['state'][st]+=1; C['history'][hist]+=1; C['lo_lr'][lo+lr]+=1; C['missed'][mb]+=1
    C['resp_p'][proto+'/'+rp]+=1
    C['uidlen'][len(uid)]+=1
    C['ts_frac'][len(ts.split('.')[1]) if '.' in ts else 0]+=1
    if dur!='-':
        C['dur_int'][float(dur)==int(float(dur))]+=1
        C['dur_dec'][len(dur.split('.')[1]) if '.' in dur else 0]+=1
    if ob!='-':
        C['ob_round'][int(ob)%1000==0 and int(ob)>0]+=1
        if int(ob)>50_000_000 or (rb!='-' and int(rb)>200_000_000): big.append(r)
    if not internal(rh):
        ext_cnt[rh]+=1; ext_src[rh].add(oh); ext_first.setdefault(rh,ts)
    if not internal(oh):
        C['ext_orig_to'][rh+':'+rp]+=1
        C['ext_orig'][oh]+=1
for c in ('proto','service','state','lo_lr','missed','uidlen','ts_frac','dur_int','dur_dec','ob_round'):
    print('##',c,C[c].most_common(30))
print('## history',len(C['history']),C['history'].most_common(12),C['history'].most_common()[-25:])
mc=C['resp_p'].most_common(); print('## resp_p',len(mc),mc[:40]); print('rare ports',[x for x in mc if x[1]<=20])
print('## external orig -> dest',C['ext_orig_to'].most_common(20)); print('n ext orig',len(C['ext_orig']),C['ext_orig'].most_common(10),C['ext_orig'].most_common()[-10:])
print('## n ext resp',len(ext_cnt)); print(ext_cnt.most_common(15))
print('## big flows',len(big))
for r in sorted(big,key=lambda r:-int(r[9]))[:40]: print(r)
pickle.dump((ext_first,ext_cnt,{k:len(v) for k,v in ext_src.items()}),open('/tmp/c/ext.pkl','wb'))
