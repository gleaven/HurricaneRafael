from common import *
import glob, collections, pickle
ev=collections.Counter(); net=collections.Counter(); byday=collections.defaultdict(collections.Counter); pathev=collections.Counter(); ua=collections.Counter()
h=[]  # 64512 rows
succ_acc=collections.defaultdict(list); first_success=None; reg_before=collections.Counter()
allsucc=set(); 
for f in sorted(glob.glob(SRC+'/network_logs/portal/aid_portal_access_*.csv')):
    for r in rows(f):
        ev[r['event']]+=1; net[r['client_network']]+=1; d=r['time_utc'][:10]; byday[d][r['event']]+=1
        pathev[(r['method'],r['path'],r['status'],r['event'])]+=1
        if '64512' in r['client_network']:
            h.append(r)
        if r['event']=='login_success':
            if r['time_utc']<'2027-11-13': reg_before[d[:7]]+=1
        if r['event'] in('registration','account_created','register_success') and r['time_utc']<'2027-11-13': reg_before['reg-'+d]+=1
print('events',dict(ev)); print('networks',net.most_common(15))
print('path/event combos'); [print('  ',k,v) for k,v in pathev.most_common(40)]
print('login_success before 2027-11-13 by month',dict(reg_before))
pickle.dump(h,open('/tmp/portal_h.pkl','wb')); pickle.dump({d:dict(c) for d,c in byday.items()},open('/tmp/portal_day.pkl','wb'))
print('64512 rows',len(h))
