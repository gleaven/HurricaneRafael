# Pass 3: structure checks on all partner logs; hostile sign-on session features vs background
import sys,re,collections,glob,csv; sys.path.insert(0,'.')
from common import *
bad=collections.Counter(); tot=0
for o in ORGS:
    for t in TYPES:
        d=load(t,[o]); tot+=len(d)
        for fn,g in d.groupby('_file'):
            if not g.time_utc.is_monotonic_increasing: bad['unsorted file']+=1
            if not (g.time_utc.str[:7]==fn[-11:-4]).all(): bad['row in wrong month file']+=int((g.time_utc.str[:7]!=fn[-11:-4]).sum())
        if ts(d).isna().any(): bad['bad timestamp']+=int(ts(d).isna().sum())
        dup=d.drop(columns=['_file','org']).duplicated().sum()
        if dup: bad[f'exact duplicates {o}/{t}']+=int(dup)
        emp=(d.drop(columns=['_file','org'])=='').sum(); emp=emp[emp>0]
        if len(emp): bad[f'empty cells {o}/{t}: '+','.join(f'{k}={v}' for k,v in emp.items())]+=1
print('rows',tot); 
for k,v in bad.items(): print(' ',k,v)
print('first/last per org:',{o:(load('firewall',[o]).time_utc.min(),load('firewall',[o]).time_utc.max()) for o in ORGS})
a=load('auth'); f=load('firewall'); r=a[a.logon_type=='remote'].copy(); r['t']=ts(r).astype('int64')//10**9
f['te']=ts(f).astype('int64')//10**9; f['dur']=f.duration_s.astype(float); f['t0']=f.te-f.dur
for o in ['city','nascc']:
    fo=f[(f.org==o)&(f.action=='allow')&f.rule_name.str.contains('(?i)sso|owa')]; idx=collections.defaultdict(list)
    for s,t0,te,d_,bs,br,sp in zip(fo.src_ip,fo.t0,fo.te,fo.dur,fo.bytes_sent,fo.bytes_recv,fo.src_port): idx[s].append((t0,te,d_,int(bs),int(br),int(sp)))
    ro=r[(r.org==o)&(r.result=='SUCCESS')]; rows=[]
    for ip,t,am in zip(ro.src_ip,ro.t,ro.auth_method):
        c=[x for x in idx.get(ip,[]) if x[0]-3<=t<=x[1]+3]
        if c: rows.append((ip,am,c[0][2],c[0][3],c[0][4],c[0][5],t-c[0][0]))
    T=pd.DataFrame(rows,columns=['ip','method','dur','bs','br','sport','offs']); T['hostile']=T.ip.str.match(r'^203\.0\.113\.\d{1,2}$')
    print(o); print(T.groupby('hostile')[['dur','bs','br','sport','offs']].describe().loc[:,(slice(None),['count','min','50%','max'])].round(1).to_string())
    print(T[T.hostile].to_string())
h=r[r.src_ip.str.match(r'^203\.0\.113\.\d{1,2}$')]; print('hostile sign-on local hours:',sorted(((pd.to_datetime(h.time_utc)-pd.Timedelta(hours=5)).dt.hour).tolist()))
# afterwards: any second use of those addresses or accounts' token resets etc.
print('hostile addresses reused:',h.src_ip.value_counts().to_dict())
