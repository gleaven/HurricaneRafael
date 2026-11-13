from lib import *
from collections import Counter,defaultdict
import re, statistics as st
hosts={}; reg2={}
def sld(h):
    p=h.split('.'); return '.'.join(p[-2:])
print('org | UA share Chrome/Edge/Firefox (user rows) | machine-row share | http share | deny/day | deny ports n | fw end reasons fin/rstS/rstC/aged (allow) | ep mix DEF/SCAN/RT/HB/THREAT | spam% | internal% | attach% | AAAA% | NX% | SRV%')
for o in ORGS:
    hw,w=load(o,'web'); hf,f=load(o,'firewall'); he,e=load(o,'endpoint_alerts'); hm,m=load(o,'mail'); hd,d=load(o,'dns')
    u=[r for r in w if r['user']!='-']; ua=Counter(r['user_agent_family'] for r in u)
    hosts[o]=Counter(r['host'] for r in w); reg2[o]=Counter(sld(r['host']) for r in w)
    den=[r for r in f if r['action']=='deny']; al=[r for r in f if r['rule_name']=='outbound-web']
    er=Counter(r['session_end_reason'] for r in al); ep=Counter(r['event'] for r in e)
    print(f"{o:6s} | {ua['Chrome/Windows']/len(u):.3f}/{ua['Edge/Windows']/len(u):.3f}/{ua['Firefox/Windows']/len(u):.3f} | {1-len(u)/len(w):.3f} | {sum(1 for r in w if r['scheme']=='http')/len(w):.3f} | {len(den)/181:.1f} | {len(set(r['dst_port'] for r in den))} | {er['tcp-fin']/len(al):.3f}/{er['tcp-rst-from-server']/len(al):.3f}/{er['tcp-rst-from-client']/len(al):.3f}/{er['aged-out']/len(al):.3f} | {ep['DEFINITIONS_UPDATED']/len(e):.2f}/{ep['SCAN_COMPLETED']/len(e):.2f}/{ep['REALTIME_PROTECTION_ENABLED']/len(e):.2f}/{ep['AGENT_HEARTBEAT_MISSED']/len(e):.2f}/{ep['THREAT_QUARANTINED']/len(e):.3f} | {sum(1 for r in m if r['verdict']=='spam')/len(m)*100:.2f} | {sum(1 for r in m if r['direction']=='internal')/len(m)*100:.1f} | {sum(1 for r in m if r['attachment_names'])/len(m)*100:.1f} | {sum(1 for r in d if r['qtype']=='AAAA')/len(d)*100:.2f} | {sum(1 for r in d if r['rcode']=='NXDOMAIN')/len(d)*100:.2f} | {sum(1 for r in d if r['qtype']=='SRV')/len(d)*100:.2f}")
allr=set().union(*[set(v) for v in reg2.values()])
print('registered domains total',len(allr),'| present in all 7 orgs',sum(1 for x in allr if all(x in reg2[o] for o in ORGS)),'| in exactly 1 org',sum(1 for x in allr if sum(x in reg2[o] for o in ORGS)==1))
only1=[(x,[o for o in ORGS if x in reg2[o]][0],sum(reg2[o][x] for o in ORGS)) for x in allr if sum(x in reg2[o] for o in ORGS)==1]
print(' single-org domains:',sorted(only1,key=lambda t:t[1]))
tl=Counter(x.split('.')[-1] for x in allr); print(' TLDs of registered domains',tl)
ex=[x for x in allr if not x.endswith('.example')]; print(' non-.example domains',len(ex),sorted(ex))
# category consistency per registered domain
cat=defaultdict(set)
for o in ORGS:
    for r in load(o,'web')[1]: cat[sld(r['host'])].add(r['category'])
print(' registered domains with >1 category',sum(1 for v in cat.values() if len(v)>1),[(k,sorted(v)) for k,v in cat.items() if len(v)>1][:8])
pre=Counter(h.split('.')[0] for o in ORGS for h in hosts[o] if h.count('.')>=2); print(' host prefixes',pre.most_common(12))
# mail subject uniformity (chi-square-like): per org subject counts min/max among the 10 common subjects
for o in ORGS:
    m=load(o,'mail')[1]; c=Counter(r['subject'] for r in m); top=[v for k,v in c.most_common(10)]
    months=Counter((r['time_utc'][:7]) for r in m if r['subject']=='Storm readiness checklist')
    print(' ',o,'top-10 subjects min/max',min(top),max(top),'| "Storm readiness checklist" by month',sorted(months.items()))
# mail size distribution, sender id format
for o in ['city','brw','srmc']:
    m=load(o,'mail')[1]
    print(' ',o,'sender localpart formats',Counter(re.sub(r'[0-9a-f]','h',r['sender'].split('@')[0]) if re.fullmatch(r'[0-9a-f]+',r['sender'].split('@')[0]) else 'named' for r in m).most_common(4),'| inbound senders appearing >1x',sum(1 for k,v in Counter(r['sender'] for r in m if r['direction']=='inbound' and r['sender_domain']=='partner-mail.example').items() if v>1),'of',len({r['sender'] for r in m if r['sender_domain']=='partner-mail.example'}))
