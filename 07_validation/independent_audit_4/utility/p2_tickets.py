#!/usr/bin/env python3
"""Ticket references across tables: do cited CHG/WO/VND tickets exist; reuse across unrelated records; approved changes during the freeze."""
import sys,collections,re,csv; sys.path.insert(0,sys.path[0])
from lib import *
cm=audit('change_management'); cmid={r['record_id']:r for r in cm}
F0,F1='2027-09-10T21:00:04Z','2027-10-25T15:00:40Z'
print('Approved changes during freeze:',[(r['time_utc'],r['record_id'],r['summary'],r['owner']) for r in cm if F0<=r['time_utc']<=F1 and r['record_type']=='Approved change'])
print('change_management id ranges',min(cmid),max(k for k in cmid if k.startswith('CHG-27')),'n CHG',sum(k.startswith('CHG-27') for k in cmid))
cites=collections.defaultdict(list)
for n,tk in (('ot_config_changes','time_utc'),('alarm_suppression_audit','time_utc'),('remote_access_sessions','login_utc')):
    for r in audit(n):
        if r['change_ticket']: cites[r['change_ticket']].append((n,r[tk],r.get('session_user') or r.get('changed_by') or r.get('account')))
for r in csv.DictReader(open('siem/rule_changes.csv')):
    if r['change_ticket']: cites[r['change_ticket']].append(('rule_changes',r['time_utc'],r['changed_by']))
chg=[t for t in cites if t.startswith('CHG-27')]
print('distinct CHG tickets cited',len(chg),'exist in change_management',sum(t in cmid for t in chg))
multi=[t for t in chg if len({c[0] for c in cites[t]})>1]
print('CHG tickets cited by more than one table',len(multi)); [print('   ',t,cites[t][:4], '| CM:',(cmid[t]['time_utc'],cmid[t]['summary']) if t in cmid else None) for t in multi[:6]]
# cited before the ticket was opened / long after
early=0;late=0;n=0;ex=[]
for t in chg:
    if t not in cmid: continue
    for c in cites[t]:
        n+=1; d=(E(c[1])-E(cmid[t]['time_utc']))/86400
        if d<0: early+=1; ex.append((t,c,cmid[t]['time_utc']))
        if d>30: late+=1
print('citations of existing CHG tickets',n,'used before ticket opened',early,'used >30 days after',late,ex[:3])
# owner vs user
om=0;tot=0
reg_=reg(); ot={u.get('ot_account'):u['username'] for u in reg_['users'] if u.get('ot_account')}
for r in audit('ot_config_changes'):
    t=r['change_ticket']
    if t in cmid and t.startswith(('CHG','EMR')):
        tot+=1; om+= cmid[t]['owner']==ot.get(r['session_user'])
print('ot_config_changes: ticket owner == session user',om,'of',tot)
sm=0;tot=0
for r in audit('ot_config_changes'):
    t=r['change_ticket']
    if t in cmid and t.startswith(('CHG','EMR')):
        tot+=1; s=cmid[t]['summary']; sm+= (r['device'] in s) and (re.sub(r' \(.*','',r['parameter']).replace('configuration file','')[:12].strip() in s or 'configuration file' in r['parameter'])
print('ot_config_changes: ticket summary names device+parameter',sm,'of',tot)
import os
wo='../../05_other_sources/maintenance/work_orders.csv'
if os.path.exists(wo):
    W=list(csv.DictReader(open(wo,encoding='utf-8'))); print('work_orders cols',list(W[0].keys())[:8],len(W))
    ids=set()
    for r in W:
        for v in r.values():
            if isinstance(v,str) and v.startswith('WO-'): ids.add(v)
    wos=[t for t in cites if t.startswith('WO-')]; print('WO tickets cited',len(wos),'found in maintenance/work_orders.csv',sum(t in ids for t in wos),'sample ids',list(ids)[:3])
