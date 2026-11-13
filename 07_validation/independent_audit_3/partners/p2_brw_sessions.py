import csv
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
S=list(csv.DictReader(open(ROOT+'/05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv')))
print('sessions',len(S),Counter(r['result'] for r in S),Counter(r['src_asn'] for r in S),'accounts',Counter(r['vendor_account'] for r in S).most_common(12))
print('span',min(r['login_utc'] for r in S),max(r['login_utc'] for r in S), 'by month',sorted(Counter(r['login_utc'][:7] for r in S).items()))
h,fw=load('brw','firewall'); ha,au=load('brw','auth'); hw,web=load('brw','web')
R=reg(); B=[o for o in R['organisations'] if o['org_id']=='BRW'][0]
person={a['account']:a['person'] for a in B['accounts'] if a.get('person')}
user_host={u:hh for hh in B['hosts'] for u in hh.get('users',[]) if hh['device_type']=='workstation'}
dmz=[r for r in fw if r['device']=='BRW-FW-DMZ-01']; edge=[r for r in fw if r['device']=='BRW-FW-EDGE-01' and r['dst_ip']=='192.0.2.70']
long_dmz=[r for r in dmz if r['src_ip'].startswith(('198.51.100.','203.0.113.'))]
used=set(); probs=[]
for s in S:
    lo=s['logout_utc'] or s['login_utc']
    c=[r for r in dmz if r['src_ip']==s['src_ip'] and abs((ts(r['time_utc'])-ts(lo)).total_seconds())<=5]
    line=f"{s['session_id']} {s['vendor_account']:10s} {s['src_ip']:16s} {s['src_asn']} {s['login_utc']} {s['logout_utc']} dur={s['duration_s']} {s['access_level']} tkt={s['ticket_ref'] or '-'} {s['result']} {s['vessel_name']}"
    if not c: probs.append('NO DMZ FW: '+line); continue
    r=c[0]; used.add(id(r))
    notes=[]
    if s['duration_s'] and abs(float(r['duration_s'])-float(s['duration_s']))>2: notes.append(f"fwdur {r['duration_s']}")
    if s['bytes_out'] and r['bytes_recv']!=s['bytes_out'] and r['bytes_sent']!=s['bytes_out']: notes.append(f"bytes fw {r['bytes_sent']}/{r['bytes_recv']} vs {s['bytes_out']}")
    ip=s['src_ip']; last=int(ip.split('.')[3]) if ip.startswith('198.51.100.') else None
    p=person.get(s['vendor_account'])
    if ip.startswith('198.51.100.') and 10<=last<=59:
        e=[x for x in edge if x['nat_src_ip']==ip and abs((ts(x['time_utc'])-ts(lo)).total_seconds())<=5]
        if not e: notes.append('NO EDGE OUTBOUND')
        else:
            hh=[k for k in B['hosts'] if k['ip']==e[0]['src_ip'] and k['device_type']!='server']
            exp=user_host.get(p,{}).get('host_id')
            if not hh or hh[0]['host_id']!=exp: notes.append(f"edge src {e[0]['src_ip']} ({[k['host_id'] for k in hh]}) != workstation of {p} ({exp})")
            # logged on?
            lg=[a for a in au if a['account']==p and a['event_id']=='4624' and ts(a['time_utc'])<=ts(s['login_utc']) and ts(s['login_utc'])-ts(a['time_utc'])<timedelta(hours=13)]
            if not lg: notes.append(f'{p} not logged on to a workstation in 13h before')
            if e[0]['dst_port']!='443': notes.append('edge port '+e[0]['dst_port'])
    elif ip.startswith('198.51.100.') and 128<=last<=191:
        v=[a for a in au if a['event_id']=='vpn-login' and a['account'].split('@')[0]==p and a['result']=='SUCCESS' and timedelta(0)<=ts(s['login_utc'])-ts(a['time_utc'])<=timedelta(hours=12)]
        if not v: notes.append(f'NO VPN SIGN-ON by {p} in 12h before')
        else: notes.append('vpn signon %ds before from %s'%((ts(s['login_utc'])-ts(v[-1]['time_utc'])).total_seconds(),v[-1]['src_network']))
        e=[x for x in edge if x['nat_src_ip']==ip and abs((ts(x['time_utc'])-ts(lo)).total_seconds())<=5]
        if not e: notes.append('no edge vpn-zone session')
        elif e[0]['dst_port']!='443': notes.append('edge port '+e[0]['dst_port']+'/'+e[0]['app'])
    else:
        e=[x for x in edge if abs((ts(x['time_utc'])-ts(lo)).total_seconds())<=60]
        v=[a for a in au if a['account'].split('@')[0]==p and timedelta(0)<=ts(s['login_utc'])-ts(a['time_utc'])<=timedelta(hours=12) and a['event_id'] in('vpn-login','4624')]
        notes.append(f"THIRD NET; edge sessions at same time: {len(e)}; holder {p} logged on/vpn within 12h before: {len(v)}")
    print(line,'|',' ; '.join(notes))
print('\n'.join(probs))
print('long/vendor-range DMZ fw rows not in session log:',[(r['time_utc'],r['src_ip'],r['duration_s']) for r in long_dmz if id(r) not in used])
print('edge->gateway rows not matched to a session:',len(edge)-sum(1 for s in S if any(x['nat_src_ip']==s['src_ip'] and abs((ts(x['time_utc'])-ts(s['logout_utc'] or s['login_utc'])).total_seconds())<=5 for x in edge)))
bg=[r for r in dmz if id(r) not in used]
print('background DMZ rows',len(bg),'max dur',max(float(r['duration_s']) for r in bg),'rows with dur>6:',sum(1 for r in bg if float(r['duration_s'])>6))
