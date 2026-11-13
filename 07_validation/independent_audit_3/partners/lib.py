import csv, glob, os, pickle, json, sys
from datetime import datetime, timezone
ROOT="."
PI=ROOT+"/05_other_sources/partner_it"
HERE=ROOT+"/07_validation/independent_audit_3/partners"
ORGS=["city","nascc","brw","port","srmc","bcmc","county"]
KINDS=["firewall","web","dns","auth","mail","endpoint_alerts"]
def load(org,kind):
    """returns (header, rows) rows = list of dict with extra _f (file) and _n (line no)"""
    p=f"{HERE}/cache/{org}_{kind}.pkl"
    if os.path.exists(p):
        return pickle.load(open(p,'rb'))
    rows=[];hdr=None
    for f in sorted(glob.glob(f"{PI}/{org}/{kind}_*.csv")):
        with open(f,newline='',encoding='utf-8') as fh:
            r=csv.reader(fh); h=next(r)
            if hdr is None: hdr=h
            assert h==hdr,(f,h,hdr)
            for i,row in enumerate(r,start=2):
                d=dict(zip(h,row)); d['_f']=os.path.basename(f); d['_n']=i
                if len(row)!=len(h): d['_bad']=len(row)
                rows.append(d)
    pickle.dump((hdr,rows),open(p,'wb'))
    return hdr,rows
def ts(s):
    return datetime.strptime(s,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
def reg():
    return json.load(open(ROOT+"/06_data_streams/partner_it_registry.json"))
