# Pass 1 trick 4: mail - sender domains by first/last seen, burstiness; subjects concentrated in a window; message-id shapes
import sys,re; sys.path.insert(0,'.')
from common import *
d=load('mail'); d['day']=d.time_utc.str[:10]
def shape(m):
    m=m.strip('<>'); l,_,r=m.partition('@')
    s=re.sub(r'[0-9a-f]','h',l); s=re.sub(r'[A-Zg-z]','a',s)
    # compress runs
    s=re.sub(r'(h+)',lambda k:'h%d'%len(k.group(1)),s); s=re.sub(r'(a+)',lambda k:'a%d'%len(k.group(1)),s)
    return s
d['mshape']=d.message_id.map(shape)
print(pd.crosstab(d.mshape,d.org).to_string()[:6000])
inb=d[d.direction=='inbound']
g=inb.groupby(['org','sender_domain']).agg(n=('day','size'),days=('day','nunique'),first=('day','min'),last=('day','max'),rcp=('recipient','nunique'),subj=('subject','nunique'),verd=('verdict',lambda s:','.join(sorted(set(s)))),shapes=('mshape',lambda s:','.join(sorted(set(s)))))
g['span']=(pd.to_datetime(g['last'])-pd.to_datetime(g['first'])).dt.days+1
print('\n## inbound sender domains with n>=5 and span<=5 days (burst domains)')
print(g[(g.n>=5)&(g.span<=5)].sort_values('n',ascending=False).to_string())
print('\n## domain count distribution per org'); print(g.groupby('org').n.describe().to_string())
g.to_pickle(C+'/mail_domains.pkl')
