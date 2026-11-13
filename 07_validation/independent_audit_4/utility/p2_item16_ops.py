#!/usr/bin/env python3
"""Item 16: operational tables (scada commands, ot config, historian accounts) vs registry roles."""
import sys,collections,re; sys.path.insert(0,sys.path[0])
from lib import *
reg_=reg(); U={u['username']:u for u in reg_['users']}; OT={u['ot_account']:u for u in reg_['users'] if u.get('ot_account')}
for n in ('vrodriguez','hdiaz','dwilliams','rle','awhite','aallen','palvarez','dpham'):
    u=U.get(n); print(n,u and (u['title'],u['department'],u['normal_hosts'],u.get('ot_account')))
sc=audit('scada_command_log')
ops=collections.Counter(r['operator'] for r in sc if r['operator'])
print('SCADA commands',len(sc),'operators',len(ops),'without ot_account',sum(1 for o in ops if not U.get(o,{}).get('ot_account')),'departments',collections.Counter(U[o]['department'] if o in U else '?' for o in ops for _ in range(ops[o])).most_common(8))
print('  origin x operator-empty',collections.Counter((r['origin'],r['operator']=='' ,r['workstation']=='') for r in sc).most_common())
def kind(dev):
    if 'BKR' in dev or '-CB-' in dev or 'FDR' in dev: return 'breaker'
    if dev.endswith('-T1') or '-T' in dev.split('-')[-1]: return 'transformer'
    if 'BUS' in dev: return 'bus'
    if '-BP' in dev or 'P-' in dev: return 'pump'
    return 'other:'+dev
print('  command x device kind',sorted(collections.Counter((r['command'],kind(r['device'])) for r in sc).items()))
eq={e['equipment_id'] for e in reg_['equipment']}; print('  devices not in registry equipment',collections.Counter(r['device'] for r in sc if r['device'] not in eq).most_common(8),'of distinct',len({r['device'] for r in sc}))
# console command: was operator logged on to that console?
import pickle
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
sess=collections.defaultdict(list); lo={}
for d in W:
    if d['event_id'] in(4634,4647): lo.setdefault((d['host'],d['logon_id']),E(d['time_utc']))
for d in W:
    if d['event_id']==4624 and d['logon_type'] in(2,10,11): sess[d['host']].append((E(d['time_utc']),lo.get((d['host'],d['logon_id']),9e12),d['user'],d['logon_type'],d.get('src_ip')))
ok=collections.Counter()
for r in sc:
    if r['origin']=='automation': continue
    t=E(r['time_utc']); ws=r['workstation']; s=[x for x in sess.get(ws,[]) if x[0]<=t<=x[1]]
    op=r['operator']; ota=U.get(op,{}).get('ot_account')
    ok[(r['origin'], 'operator session open' if any(x[2] in(op,ota) for x in s) else ('other session open' if s else 'no session'))]+=1
print('  command vs interactive/RDP session on workstation:',sorted(ok.items()))
rd=[r for r in sc if r['origin']=='remote desktop']
ras=audit('remote_access_sessions')
inr=collections.Counter()
for r in rd:
    t=r['time_utc']; s=[x for x in ras if x['login_utc']<=t<=x['logout_utc']]
    inr[('in a gateway session' if s else 'no gateway session', 'target listed' if any(r['workstation'] in x['target_hosts'].split(';') for x in s) else 'target not listed', 'user match' if any(OT.get(x['account'],{}).get('username')==r['operator'] for x in s) else 'user differs/empty')]+=1
print('  remote-desktop commands vs gateway sessions',sorted(inr.items()))
oc=audit('ot_config_changes')
print('OT config: device x parameter'); 
for k,v in sorted(collections.Counter((re.sub(r'-0?\d$|\d$','',r['device']),re.sub(r'configuration file .*','configuration file',r['parameter'])) for r in oc).items()): print('    ',v,k)
print('  change_type x source_host',collections.Counter((r['change_type'],r['source_host']) for r in oc).most_common())
ha=audit('historian_access'); sa={a['account']:a for a in reg_['service_accounts']}
print('historian service accounts x client',collections.Counter((a['account'],a['client_host']) for a in ha if a['account'].startswith('svc') ).most_common(12))
print('  OT accounts x client kind',collections.Counter((a['account'][:6],a['client_host'][:9]) for a in ha if a['account'].startswith('GW-') and '\\' not in a['account']).most_common(12))
print('  JMP-prefixed accounts',collections.Counter(a['account'] for a in ha if '\\' in a['account']).most_common(8))
# historian session via JMP: is there a gateway session open by that account?
c=collections.Counter()
for a in ha:
    if a['client_host']!='GW-SYS-JMP-01': continue
    acc=a['account'].split('\\')[-1]; s=[x for x in ras if x['login_utc']<=a['start_utc']<=x['logout_utc']]
    c[('same account' if any(x['account']==acc for x in s) else ('other account session' if s else 'no gateway session'), 'hist listed' if any('GW-SRV-HIST-01' in x['target_hosts'] for x in s) else 'hist not target')]+=1
print('  JMP-client historian sessions vs gateway sessions',sorted(c.items()))
tg=[x for x in ras if 'GW-SRV-HIST-01' in x['target_hosts'].split(';')]
hm=sum(1 for x in tg if any(a['client_host']=='GW-SYS-JMP-01' and x['login_utc']<=a['start_utc']<=x['logout_utc'] for a in ha))
print('  gateway sessions listing HIST-01 as target',len(tg),'with a historian_access row inside',hm)
