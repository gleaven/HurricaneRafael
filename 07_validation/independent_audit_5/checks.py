#!/usr/bin/env python3
"""Reproduces the headline filters of REPORT.md with row counts. Read-only."""
import csv,glob,json,re,collections
B='../../05_other_sources/'; N=B+'network_logs/'; P=B+'partner_it/'
def L(p): return list(csv.DictReader(open(p,encoding='utf-8',errors='replace')))
def G(pat):
    for f in sorted(glob.glob(pat)):
        for r in csv.DictReader(open(f,encoding='utf-8',errors='replace')): yield r
out=[]
def rep(name,n,note=''): out.append((name,n,note)); print(f'{name}: {n} {note}')
# A1 proxy first label with hyphen
rep('A1 proxy host first label contains "-" (non-cbpwa)',sum(1 for r in G(N+'proxy/web_proxy_*.csv') if '-' in r['host'].split('.')[0] and not r['host'].endswith('cbpwa.example')))
# A1b zeek ssl/dns
def zeek(name,col):
    n=0
    for f in sorted(glob.glob(N+'zeek/*/'+name+'.log')):
        fields=None
        for line in open(f,encoding='utf-8',errors='replace'):
            if line.startswith('#fields'): fields=line.rstrip('\n').split('\t')[1:]; i=fields.index(col); continue
            if line.startswith('#'): continue
            v=line.rstrip('\n').split('\t')[i]
            if '-' in v.split('.')[0] and not v.endswith('cbpwa.example') and not v.endswith('.arpa') and v.count('.')>=2 and not v.startswith('_'): n+=1
    return n
rep('A1 zeek ssl server_name first label contains "-"',zeek('ssl','server_name'))
rep('A1 zeek dns query first label contains "-"',zeek('dns','query'))
n=0
for f in sorted(glob.glob(N+'endpoint/endpoint_*.jsonl')):
    for line in open(f):
        if '"event_type":"dns_query"' in line:
            q=json.loads(line)['query']
            if '-' in q.split('.')[0] and not q.endswith('cbpwa.example') and not q.startswith('_'): n+=1
rep('A1 endpoint dns_query first label contains "-"',n)
# A2 aid applications CC-DAM
A=L(B+'payments/aid_applications.csv')
rep('A2 aid applications with CC-DAM-NNNN.jpg photo names',sum(1 for r in A if 'CC-DAM' in r['damage_photo_hashes']), 'all from %s'%set(r['source_ip'] for r in A if 'CC-DAM' in r['damage_photo_hashes']))
rep('B aid rows with routing 990000037/990000125',collections.Counter(r['record_type'] for r in A if r['deposit_routing_number'] in('990000037','990000125')))
# A3 partner web two-label host
for o in ['city','nascc','brw','county','port','srmc','bcmc']:
    rep(f'A3 partner web {o} host with exactly one dot',sum(1 for r in G(P+o+'/web_*.csv') if r['host'].count('.')==1), '; dns: %d'%sum(1 for r in G(P+o+'/dns_*.csv') if r['query'].count('.')==1))
# A4 cbpwa mail subject singleton template
M=L(N+'audit/mail_gateway_cbpwa.csv'); c=collections.Counter(re.sub(r'\d+','N',r['subject']) for r in M)
rep('A4 cbpwa mail subject templates occurring once',[s for s,v in c.items() if v==1],'of %d templates'%len(c))
# A5 ot_config
O=L(N+'audit/ot_config_changes.csv')
rep('A5 ot_config parameter == configuration file rtu04_active.cfg',sum(1 for r in O if r['parameter']=='configuration file rtu04_active.cfg'))
rep('A5 ot_config change_type==file replaced and parameter not a configuration file',sum(1 for r in O if r['change_type']=='file replaced' and not r['parameter'].startswith('configuration file')))
# A6 url click tables
rep('A6 rows in mail_url_clicks_brightwake / _city_airstation',(len(L(N+'audit/mail_url_clicks_brightwake.csv')),len(L(N+'audit/mail_url_clicks_city_airstation.csv'))))
# B others
S=[r for r in G(N+'siem/siem_alerts_*.csv') if r['rule_id']=='SE3-OT-3301' and r['priority']=='HIGH']; rep('B siem SE3-OT-3301 HIGH',len(S),S[0]['detail'] if S else '')
V=L(B+'telemetry/vessel_cargo_control_remote_sessions.csv'); rep('B vessel sessions ASN 64512',sum(1 for r in V if r['src_asn']=='ASN 64512'),'of %d'%len(V))
rep('B vessel session bytes_out == phish mail size 48211',[r['session_id'] for r in V if r['bytes_out']=='48211'])
K=collections.Counter()
for r in G(N+'portal/aid_portal_access_*.csv'):
    if r['user_agent_family']=='python-requests' and r['event'] in('login_success','profile_updated: direct deposit'): K[r['event']]+=1
rep('B aid portal python-requests login_success / direct-deposit update',dict(K))
R=L(N+'audit/remote_access_sessions.csv')
H=[r for r in R if r['account']=='GW-ENG-VELA' and r['src_country']!='US']
rep('G remote access VELA non-US',len(H),'password-only+no ticket: %d; other non-US rows: %d'%(sum(1 for r in H if r['auth_method']=='password only' and not r['change_ticket']),sum(1 for r in R if r['src_country']!='US')-len(H)))
rep('B remote access bytes_in %100==0',sum(1 for r in R if int(r['bytes_in'])%100==0),'of which VELA non-US %d of %d'%(sum(1 for r in H if int(r['bytes_in'])%100==0),len(H)))
rc=L(N+'siem/rule_changes.csv'); rep('B rule_changes whole-minute timestamps',[(r['time_utc'],r['rule_id']) for r in rc if r['time_utc'].endswith(':00Z')],'of %d'%len(rc))
n=0
for f in sorted(glob.glob(N+'windows/security_*.jsonl')):
    for line in open(f):
        if '"event_id":4624' in line and '"domain":"GW-SYS-JMP-01"' in line: n+=1
rep('B windows 4624 domain==GW-SYS-JMP-01',n)
json.dump([(a,str(b),c) for a,b,c in out],open('cache/checks_out.json','w'),indent=1)
