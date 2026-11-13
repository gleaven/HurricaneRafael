#!/usr/bin/env python3
"""Pass 1: ssl/x509/dns/http/files/notice value counts and rare values; C2 rows."""
import pickle,glob,collections,datetime,re
def load(l):
    rows=[]
    for f in sorted(glob.glob(f'/tmp/c/zeek_{l}_*.pkl')):
        h,r=pickle.load(open(f,'rb')); rows+=r
    return rows
def T(ts): return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%dT%H:%M:%S')
ssl=load('ssl')
print('ssl',len(ssl))
for i,n in ((6,'version'),(7,'cipher'),(9,'resumed'),(10,'established')):
    print(n,collections.Counter(r[i] for r in ssl).most_common(12))
print('ver x cipher',collections.Counter((r[6],r[7]) for r in ssl).most_common(20))
print('ver x certs',collections.Counter((r[6],r[9],r[11]=='(empty)') for r in ssl).most_common(20))
sn=collections.Counter(r[8] for r in ssl); print('sni distinct',len(sn),'singletons',sum(1 for v in sn.values() if v==1), 'no sni',sn.get('-'))
c2=[r for r in ssl if r[4]=='104.21.88.43']; print('C2 ssl rows',len(c2),collections.Counter((r[6],r[7],r[8],r[9],r[10],r[11][:16]) for r in c2))
nb=[r for r in ssl if r[4].startswith('104.21.88.') and r[4]!='104.21.88.43']; print('neighbours',collections.Counter((r[4],r[6],r[7],r[8],r[9]) for r in nb).most_common(8))
# sni first seen / host-count for rare sni
snh=collections.defaultdict(set); first={}
for r in ssl: snh[r[8]].add(r[2]); first.setdefault(r[8],r[0])
one=[(s,sn[s],T(first[s])) for s in sn if len(snh[s])==1 and sn[s]>=20]
print('SNI contacted by exactly one host with >=20 flows:',len(one),sorted(one,key=lambda x:-x[1])[:30])
x=load('x509')
print('x509',len(x)); print('issuer',collections.Counter(r[5] for r in x).most_common(15)); print('keyalg',collections.Counter((r[8],r[9],r[10],r[11],r[12]) for r in x).most_common(10))
subj=collections.Counter(r[4] for r in x); print('subjects',len(subj),[k for k,v in subj.items() if v<=2][:30])
selfs=[r for r in x if r[4]==r[5]]; print('self-signed',len(selfs),collections.Counter(r[4] for r in selfs).most_common(10))
print('validity days',collections.Counter(round((float(r[7])-float(r[6]))/86400) for r in x).most_common(10))
n=load('notice'); print('notice',len(n),collections.Counter(r[5] for r in n).most_common()); 
for r in n:
    if r[5] not in('SSL::Invalid_Server_Cert','Scan::Port_Scan','DNS::External_Name'): print(T(r[0]),r)
print([ (T(r[0]),r[2],r[6]) for r in n if r[2]=='10.14.22.47' or '104.21.88' in ' '.join(r)])
