import csv,glob,sys
from collections import Counter
from lib import *
P=ROOT+"/05_other_sources/network_logs/portal/"
# aid portal: header, client networks, whether partner NAT IPs appear
pub={'city':'64.134.20.','nascc':'162.40.88.','port':'69.15.201.','srmc':'96.88.14.','bcmc':'104.190.33.','county':'199.21.76.','brw':'198.51.100.'}
hits=Counter(); hdr=None; n=0; nets=Counter(); ex={}
for f in sorted(glob.glob(P+'aid_portal_access_*.csv')):
    with open(f,newline='',encoding='utf-8') as fh:
        r=csv.reader(fh); h=next(r)
        if hdr is None: hdr=h; print(h)
        ci=h.index('client_ip')
        for row in r:
            n+=1
            for o,p in pub.items():
                if row[ci].startswith(p): hits[o]+=1; ex.setdefault(o,row)
print('aid portal rows',n,'rows from partner public blocks',hits)
for o,e in ex.items(): print(o,e)
# partner web requests to the aid portal
for o in ORGS:
    hw,w=load(o,'web')
    rr=[r for r in w if 'disasteraid' in r['host']]
    print(o,'web rows to *disasteraid*',len(rr),Counter(r['host'] for r in rr).most_common(3),Counter(r['time_utc'][:7] for r in rr).most_common(8))
