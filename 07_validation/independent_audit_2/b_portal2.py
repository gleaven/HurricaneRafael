from common import *
import pickle, collections
h=pickle.load(open('/tmp/portal_h.pkl','rb'))
print('64512 by month/event',sorted(collections.Counter((r['time_utc'][:7],r['event']) for r in h).items()))
aug=[r for r in h if r['time_utc']<'2027-09']
print('Aug probing span',min(r['time_utc'] for r in aug),max(r['time_utc'] for r in aug),len(aug),collections.Counter((r['path'],r['status'],r['event']) for r in aug).most_common(12))
print('Aug by day',sorted(collections.Counter(r['time_utc'][:10] for r in aug).items()))
print('Aug ips',len({r['client_ip'] for r in aug}),'ua',collections.Counter(r['user_agent_family'] for r in aug).most_common(5),'account_ref nonempty',sum(1 for r in aug if r['account_ref']))
mid=[r for r in h if '2027-09'<=r['time_utc']<'2027-11-13']
print('64512 rows Sep..Nov12:',len(mid),collections.Counter((r['time_utc'][:10],r['event']) for r in mid).most_common(8))
nov=[r for r in h if r['time_utc']>='2027-11-13']
print('Nov+ span',min(r['time_utc'] for r in nov),max(r['time_utc'] for r in nov))
fl=[r for r in nov if r['event']=='login_failed']; su=[r for r in nov if r['event']=='login_success']
print('failed',len(fl),'success',len(su),'distinct success accounts',len({r['account_ref'] for r in su}),'other events',collections.Counter(r['event'] for r in nov if r['event'] not in('login_failed','login_success')))
print('failed by day',sorted(collections.Counter(r['time_utc'][:10] for r in fl).items()))
print('success by day',sorted(collections.Counter(r['time_utc'][:10] for r in su).items()))
print('failed in window 11-15T06..11-24T06',sum(1 for r in fl if '2027-11-15T06'<=r['time_utc']<'2027-11-24T06'))
# burst shape: per hour
ph=collections.Counter(r['time_utc'][:13] for r in fl); v=sorted(ph.values()); print('hours with failures',len(ph),'max/h',v[-1],'median/h',v[len(v)//2],'top hours',ph.most_common(5))
pm=collections.Counter(r['time_utc'][:16] for r in fl); v=sorted(pm.values()); print('minutes',len(pm),'max/min',v[-1],'distinct per-minute counts',len(set(v)),collections.Counter(v).most_common(6))
print('fail ips',len({r['client_ip'] for r in fl}),'top',collections.Counter(r['client_ip'] for r in fl).most_common(4),'ua',collections.Counter(r['user_agent_family'] for r in fl).most_common(4))
print('fail account_ref nonempty',sum(1 for r in fl if r['account_ref']),'distinct',len({r['account_ref'] for r in fl}), fl[0])
print('fail bytes distinct',len({r['bytes'] for r in fl}),collections.Counter(r['bytes'] for r in fl).most_common(3))
# ATO join
ato=pickle.load(open('/tmp/ato.pkl','rb'))
sa={(r['account_ref'],r['time_utc'],r['client_ip']) for r in su}
A={(a[0],a[1],a[3]) for a in ato}
print('aid ATO (account,login_utc,ip) in portal successes:',len(A&sa),'of',len(A),'portal successes not in aid ATO',len(sa-A))
dd=[r for r in nov if r['event']=='profile_updated: direct deposit']
print('64512 direct deposit updates in portal',len(dd), 'match aid changed_utc',len({(r['account_ref'],r['time_utc']) for r in dd}&{(a[0],a[2]) for a in ato}))
# did the successful account also get failures before success (stuffing realism)?
facc=collections.Counter(r['account_ref'] for r in fl)
print('successful accounts with prior failed attempts:',sum(1 for r in su if facc.get(r['account_ref'],0)>0))
print(su[0])
