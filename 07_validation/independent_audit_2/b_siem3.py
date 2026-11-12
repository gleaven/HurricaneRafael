from common import *
import pickle, collections, bisect
day,fp,keep,hosts=pickle.load(open('/tmp/siem.pkl','rb'))
ha=load('network_logs/audit/historian_access.csv'); hs=sorted(int(ts(r['start_utc']).timestamp()) for r in ha)
hb={int(ts(r['start_utc']).timestamp()) for r in ha if r['query_type']=='bulk read'}
def near(L,t,tol): 
    i=bisect.bisect_left(L,t); return any(0<=j<len(L) and abs(L[j]-t)<=tol for j in (i-1,i))
a=[r for r in keep if r['rule_id']=='SE3-OT-1104']
m=[r for r in a if near(hs,int(ts(r['time_utc']).timestamp()),120)]
print('1104 alerts',len(a),'with a historian_access session within 2 min',len(m),'of which bulk-read sessions',sum(1 for r in m if any(abs(int(ts(r['time_utc']).timestamp())-b)<=120 for b in hb)))
fi=load('network_logs/audit/file_integrity.csv'); fs=sorted(int(ts(r['time_utc']).timestamp()) for r in fi)
a=[r for r in keep if r['rule_id']=='SE3-OT-2201']; m=[r for r in a if near(fs,int(ts(r['time_utc']).timestamp()),120)]
print('2201 alerts',len(a),'with file_integrity row within 2 min',len(m),[ (r['time_utc'],r['user']) for r in m][:5])
al=load('network_logs/audit/alarm_suppression_audit.csv'); As=sorted(int(ts(r['time_utc']).timestamp()) for r in al)
a=[r for r in keep if r['rule_id']=='SE3-OT-3301']; m=[r for r in a if near(As,int(ts(r['time_utc']).timestamp()),120)]
print('3301 alerts',len(a),'with suppression-audit row within 2 min',len(m),[ (r['time_utc'],r['user'],r['src_host']) for r in m][:8])
