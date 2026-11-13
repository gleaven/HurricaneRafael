# workstation logon/logoff pairing, overlap, and web-vs-logon agreement
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import statistics as st, bisect
R=reg(); om={'city':'CITY','nascc':'NASCC','brw':'BRW','port':'PORT','srmc':'SRMC','bcmc':'BCMC','county':'COUNTY'}
for o in ORGS:
    O=[x for x in R['organisations'] if x['org_id']==om[o]][0]
    ip2h={h['ip']:h for h in O['hosts']}; hid={h['host_id']:h for h in O['hosts']}
    h,a=load(o,'auth')
    ws=[r for r in a if r['logon_type'] in('2','7')]
    print('=====',o,'ws events',len(ws),Counter((r['event_id'],r['logon_type'],r['result']) for r in ws).most_common())
    # host/src_ip consistent with registry?
    bad=sum(1 for r in ws if hid[r['host']]['ip']!=r['src_ip']); print('  src_ip != host ip',bad)
    # account allowed on host?
    notuser=sum(1 for r in ws if r['account'] not in hid[r['host']].get('users',[]) and r['event_id']=='4624'); print('  4624 by account not in host.users',notuser,'of',sum(1 for r in ws if r['event_id']=='4624'))
    # pairing per host
    byhost=defaultdict(list)
    for r in ws: byhost[r['host']].append(r)
    sess=[]; unpairedlogon=0; orphanlogoff=0; overlap=0; hourhist=Counter(); offhist=Counter()
    intervals=defaultdict(list)  # (host)->[(start,end,acct)]
    for hname,ev in byhost.items():
        open_={}
        cur=None
        for r in ev:
            t=ts(r['time_utc'])
            if r['event_id']=='4624' and r['logon_type']=='2':
                if cur is not None and cur[1]!=r['account']: overlap+=1
                if r['account'] in open_: unpairedlogon+=1
                open_[r['account']]=t; cur=(t,r['account'])
                hourhist[(t.hour-5)%24]+=1
            elif r['event_id']=='4634':
                if r['account'] in open_:
                    s=open_.pop(r['account']); sess.append((t-s).total_seconds()/3600); intervals[hname].append((s,t,r['account']))
                    if cur and cur[1]==r['account']: cur=None
                else: orphanlogoff+=1
                offhist[(t.hour-5)%24]+=1
        unpairedlogon+=len(open_)
        for acc,s in open_.items(): intervals[hname].append((s,s+timedelta(hours=12),acc))
    print('  sessions',len(sess),'dur h: med %.2f p5 %.2f p95 %.2f max %.1f'%(st.median(sess),sorted(sess)[len(sess)//20],sorted(sess)[len(sess)*19//20],max(sess)),'| logons never logged off',unpairedlogon,'| logoff w/o logon',orphanlogoff,'| logon while other user still on',overlap)
    print('  logon hour local(CDT approx)',' '.join(f"{hh}:{hourhist[hh]}" for hh in range(24)))
    print('  logoff hour local',' '.join(f"{hh}:{offhist[hh]}" for hh in range(24)))
    # same account concurrently on two hosts
    byacc=defaultdict(list)
    for hn,iv in intervals.items():
        for s,e,acc in iv: byacc[acc].append((s,e,hn))
    conc=0
    for acc,iv in byacc.items():
        iv.sort()
        for i in range(1,len(iv)):
            if iv[i][0]<iv[i-1][1] and iv[i][2]!=iv[i-1][2]: conc+=1
    print('  same account on two hosts at once',conc)
    # web requests by user: was that user logged on at that client?
    hw,w=load(o,'web')
    tot=0;inside=0;nolog=0;wronguser=0
    for hn in intervals: intervals[hn].sort()
    for r in w:
        if r['user']=='-': continue
        hn=ip2h.get(r['client_ip'],{}).get('host_id'); 
        if not hn: continue
        tot+=1; t=ts(r['time_utc']); ok=False; anyone=False
        for s,e,acc in intervals.get(hn,[]):
            if s<=t<=e:
                anyone=True
                if acc==r['user']: ok=True;break
        if ok: inside+=1
        elif anyone: wronguser+=1
        else: nolog+=1
    print(f'  web(user) rows {tot}: user logged on at that host {inside} ({inside/tot:.1%}); someone else logged on {wronguser}; nobody logged on {nolog}')
    # 7 (unlock) events for hospitals
    u=[r for r in ws if r['logon_type']=='7']
    if u: print('  type7 unlocks',len(u),'distinct accts',len({r['account'] for r in u}),'hosts',len({r['host'] for r in u}))
