from common import *
import pickle, collections, glob
h=pickle.load(open('/tmp/portal_h.pkl','rb'))
aid=pickle.load(open('/tmp/aid.pkl','rb'))
apps={r['account_id']:r for r in aid if r['record_type']=='application'}
aug=[r for r in h if r['time_utc']<'2027-09' and r['event']=='login_failed']
print('Aug failed account_refs sample',[r['account_ref'] for r in aug[:6]],'in aid accounts',sum(1 for r in aug if r['account_ref'] in apps))
fl=[r for r in h if r['time_utc']>='2027-11' and r['event']=='login_failed']
ex=sum(1 for r in fl if r['account_ref'] in apps); print('Nov failed: account_ref exists in aid apps',ex,'of',len(fl))
notyet=sum(1 for r in fl if r['account_ref'] in apps and apps[r['account_ref']]['submitted_utc']>r['time_utc']); print('failed login for account before that account was created',notyet)
su=[r for r in h if r['event']=='login_success']
print('ATO accounts channel',collections.Counter(apps[r['account_ref']]['channel'] for r in su), 'ATO login before account created',sum(1 for r in su if apps[r['account_ref']]['submitted_utc']>r['time_utc']))
# all portal: account_created vs aid apps
day=pickle.load(open('/tmp/portal_day.pkl','rb'))
print('portal rows by month/event')
bm=collections.defaultdict(collections.Counter)
for d,c in day.items():
    for e,n in c.items(): bm[d[:7]][e.split(':')[0]]+=n
for m in sorted(bm): print('  ',m,dict(bm[m]))
print('account_created first days',[(d,day[d].get('account_created',0)) for d in sorted(day) if day[d].get('account_created')][:6])
print('aid web apps first days',sorted(collections.Counter(r['submitted_utc'][:10] for r in apps.values() if r['channel']=='web').items())[:5])
# join account_created
created={}; legit_succ=[]; uas=collections.Counter(); ddl=[]
for f in sorted(glob.glob(SRC+'/network_logs/portal/aid_portal_access_2027-1*.csv'))+sorted(glob.glob(SRC+'/network_logs/portal/aid_portal_access_2028*.csv')):
    for r in rows(f):
        if r['event']=='account_created': created[r['account_ref']]=r
        if r['event']=='login_success' and '64512' not in r['client_network']: legit_succ.append(r)
        if '64512' not in r['client_network']: uas[r['user_agent_family']]+=1
        if r['event']=='profile_updated: direct deposit' and '64512' not in r['client_network']: ddl.append(r)
web=[r for r in apps.values() if r['channel']=='web']
print('web apps',len(web),'with account_created row',sum(1 for r in web if r['account_id'] in created),'created rows not web apps',sum(1 for a in created if a not in apps or apps[a]['channel']!='web'))
tm=sum(1 for r in web if r['account_id'] in created and created[r['account_id']]['time_utc']==r['submitted_utc']); ipm=sum(1 for r in web if r['account_id'] in created and created[r['account_id']]['client_ip']==r['source_ip'])
print('time match',tm,'ip match',ipm)
miss=[r for r in web if r['account_id'] not in created]; print('web apps missing from portal log',len(miss), collections.Counter(r['source_asn'] for r in miss).most_common(4), 'ATO victims among them',len({r['account_ref'] for r in su}&{r['account_id'] for r in miss}))
ch=[r for r in aid if r['record_type']=='account_change' and r['login_utc']]
print('aid changes with login',len(ch),'legit portal successes',len(legit_succ),'match', len({(r['account_ref'],r['time_utc']) for r in legit_succ}&{(r['account_id'],r['login_utc']) for r in ch}))
print('legit UA',uas.most_common(8))
print('ATO victims: had account_created in portal?',sum(1 for r in su if r['account_ref'] in created))
