# Pass 1 trick 5: bulk mailings - by (org,sender_domain,subject) with many recipients; compare shapes of each campaign
import sys,re; sys.path.insert(0,'.')
from common import *
d=load('mail'); d['day']=d.time_utc.str[:10]; d['t']=ts(d)
g=d.groupby(['org','direction','sender_domain','subject']).agg(n=('day','size'),days=('day','nunique'),first=('time_utc','min'),last=('time_utc','max'),rcp=('recipient','nunique'),senders=('sender','nunique'),sizes=('size_bytes','nunique'),att=('attachment_names','nunique'),verd=('verdict',lambda s:','.join(sorted(set(s)))))
b=g[g.n>=15].sort_values('n',ascending=False)
print(b.to_string())
print('\ncounts multiple of 60:', (b.n%60==0).sum(), 'of', len(b))
