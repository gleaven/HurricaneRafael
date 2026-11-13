import pickle,glob,datetime,csv,json
def zeek(l):
    rows=[]
    for f in sorted(glob.glob(f'/tmp/c/zeek_{l}_*.pkl')):
        h,r=pickle.load(open(f,'rb')); rows+=r
    return rows
def fam(n): return pickle.load(open(f'/tmp/c/{n}.pkl','rb'))
def T(ts): return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%dT%H:%M:%SZ')
def E(s):
    s=s.replace('Z','')
    fmt='%Y-%m-%dT%H:%M:%S.%f' if '.' in s else '%Y-%m-%dT%H:%M:%S'
    return datetime.datetime.strptime(s,fmt).replace(tzinfo=datetime.timezone.utc).timestamp()
def audit(n): return list(csv.DictReader(open(f'audit/{n}.csv',newline='',encoding='utf-8')))
HOSTILE_SRC=('185.220.101.','45.141.152.','198.51.47.','198.51.48.')
C2='104.21.88.43'
def reg(): return json.load(open('../../06_data_streams/gw_host_registry.json'))
