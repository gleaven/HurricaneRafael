from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import statistics as st, csv
A=ROOT+"/05_other_sources/network_logs/audit/"
clicks=list(csv.DictReader(open(A+'mail_url_clicks_city_airstation.csv')))
for o in ['city','nascc']:
    hm,m=load(o,'mail'); ha,a=load(o,'auth')
    w=[r for r in m if r['sender_domain']=='aid-help-portal.example']
    tt=sorted(r['time_utc'] for r in w)
    print('==',o,'wave msgs',len(w),'first',tt[0],'last',tt[-1],'by local day(UTC-5)',sorted(Counter((ts(t)-timedelta(hours=5)).strftime('%m-%d') for t in tt).items()))
    print('   distinct recipients',len({r['recipient'] for r in w}),'max per recipient',Counter(r['recipient'] for r in w).most_common(1),'distinct senders',len({r['sender'] for r in w}),'sizes',min(int(r['size_bytes']) for r in w),max(int(r['size_bytes']) for r in w),'attach',Counter(bool(r['attachment_names']) for r in w),'verdicts',Counter((r['verdict'],r['action']) for r in w))
    hours=Counter(ts(t).hour for t in tt); print('   by UTC hour',sorted(hours.items()))
    gaps=[(ts(tt[i+1])-ts(tt[i])).total_seconds() for i in range(len(tt)-1)]
    print('   inter-arrival s: med %.0f max %.0f; identical-second pairs %d'%(st.median(gaps),max(gaps),sum(1 for g in gaps if g==0)))
    for c in clicks:
        if not c['mailbox'].endswith(('cctexas.example' if o=='city' else 'navy.example')): continue
        got=sorted(r['time_utc'] for r in w if r['recipient']==c['mailbox'])
        before=[g for g in got if g<=c['time_utc']]
        so=[r for r in a if r['account']==c['mailbox'] and r['src_network']=='ASN 64512']
        acct=c['mailbox'].split('@')[0]
        # was the user logged on at the click host at click time?
        lg=[r for r in a if r['account']==acct and r['event_id'] in('4624','4634') and r['src_ip']==c['client_ip'] and r['time_utc']<=c['time_utc']]
        lastev=lg[-1]['event_id']+'@'+lg[-1]['time_utc'] if lg else 'NONE'
        # legit remote sign-ons by that account afterwards, from usual networks
        later=[r for r in a if r['account']==c['mailbox'] and r['logon_type']=='remote' and r['time_utc']>so[0]['time_utc']] if so else []
        print(f"   click {c['time_utc']} {acct} host {c['client_ip']}: lures received before click {len(before)} (first {before[0] if before else None}); last workstation event before click: {lastev}; hostile sign-on {so[0]['time_utc'] if so else None} (+{(ts(so[0]['time_utc'])-ts(c['time_utc'])).total_seconds()/3600:.1f} h) n={len(so)}; later remote sign-ons by account {len(later)}")
# DST check: logon hour (UTC) mode before/after Nov 7
for o in ['city','srmc']:
    ha,a=load(o,'auth')
    for lab,lo,hi in [('Oct','2027-10-04','2027-10-30'),('Dec','2027-11-29','2027-12-18')]:
        c=Counter(ts(r['time_utc']).hour for r in a if r['event_id']=='4624' and r['logon_type']=='2' and lo<=r['time_utc'][:10]<=hi)
        print(o,lab,'4624 by UTC hour',sorted(c.items()))
