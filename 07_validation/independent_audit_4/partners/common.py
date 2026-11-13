import pandas as pd, numpy as np, json, os, glob, sys
ROOT="."
A=ROOT+"/07_validation/independent_audit_4/partners"
C="./_scratch/cache4"   # local cache (fast disk)
os.makedirs(C,exist_ok=True)
ORGS=['city','nascc','brw','port','srmc','bcmc','county']
TYPES=['firewall','web','dns','auth','mail','endpoint_alerts']
def load(t,orgs=ORGS):
    out=[]
    for o in orgs:
        p=f"{C}/{o}_{t}.pkl"
        if not os.path.exists(p):
            fs=sorted(glob.glob(f"{ROOT}/05_other_sources/partner_it/{o}/{t}_*.csv"))
            d=pd.concat([pd.read_csv(f,dtype=str,keep_default_na=False).assign(_file=os.path.basename(f)) for f in fs],ignore_index=True)
            d['org']=o
            d.to_pickle(p)
        else: d=pd.read_pickle(p)
        out.append(d)
    d=pd.concat(out,ignore_index=True) if len(out)>1 else out[0]
    return d
def portal(name):
    p=f"{C}/portal_{name}.pkl"
    if not os.path.exists(p):
        fs=sorted(glob.glob(f"{ROOT}/05_other_sources/network_logs/portal/{name}_*.csv"))
        d=pd.concat([pd.read_csv(f,dtype=str,keep_default_na=False).assign(_file=os.path.basename(f)) for f in fs],ignore_index=True)
        d.to_pickle(p)
    else: d=pd.read_pickle(p)
    return d
def ts(d,col='time_utc'):
    return pd.to_datetime(d[col],format='%Y-%m-%dT%H:%M:%SZ',utc=True,errors='coerce')
def reg():
    return json.load(open(ROOT+"/06_data_streams/partner_it_registry.json"))
