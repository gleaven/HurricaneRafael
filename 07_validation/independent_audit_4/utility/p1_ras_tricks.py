#!/usr/bin/env python3
"""Pass 1 tricks on remote_access_sessions: byte ratio, duration modulo, session-id gaps, password-only by account, sec-of-minute."""
import csv,collections,datetime
R=list(csv.DictReader(open('audit/remote_access_sessions.csv')))
H=lambda r: r['src_country']!='US'
print('n',len(R),'hostile(by country)',sum(map(H,R)))
print('bytes_out>bytes_in: hostile',sum(1 for r in R if H(r) and int(r['bytes_out'])>int(r['bytes_in'])),'benign',sum(1 for r in R if not H(r) and int(r['bytes_out'])>int(r['bytes_in'])))
print('bytes_out>100MB',[(r['session_id'],H(r)) for r in R if int(r['bytes_out'])>1e8])
import statistics
print('benign bytes_out median/max',statistics.median(int(r['bytes_out']) for r in R if not H(r)),max(int(r['bytes_out']) for r in R if not H(r)))
print('benign bytes_in median/max',statistics.median(int(r['bytes_in']) for r in R if not H(r)),max(int(r['bytes_in']) for r in R if not H(r)))
m=collections.Counter(int(r['duration_s'])%60 for r in R if not H(r)); print('benign dur%60 top',m.most_common(5),'count ==22:',m[22])
print('hostile dur%60',[int(r['duration_s'])%60 for r in R if H(r)])
print('hostile dur%10',[int(r['duration_s'])%10 for r in R if H(r)], 'benign %10==2 share',sum(1 for r in R if not H(r) and int(r['duration_s'])%10==2)/sum(1 for r in R if not H(r)))
# duration check
bad=0
for r in R:
    a=datetime.datetime.strptime(r['login_utc'],'%Y-%m-%dT%H:%M:%SZ');b=datetime.datetime.strptime(r['logout_utc'],'%Y-%m-%dT%H:%M:%SZ')
    if (b-a).total_seconds()!=int(r['duration_s']): bad+=1
print('duration mismatches',bad)
ids=[int(r['session_id'][4:]) for r in R]; gaps=[(a,b) for a,b in zip(ids,ids[1:]) if b!=a+1]; print('id gaps',len(gaps),gaps[:30], 'monotonic by login?', all(R[i]['login_utc']<=R[i+1]['login_utc'] for i in range(len(R)-1)))
print('auth by hostile',collections.Counter(r['auth_method'] for r in R if H(r)))
pw=collections.Counter(r['account'] for r in R if r['auth_method']=='password only'); print('password only accounts',pw.most_common(50))
print('ticket empty by auth', collections.Counter((r['auth_method'],r['change_ticket']=='') for r in R))
print('n targets hostile',[len(r['target_hosts'].split(';')) for r in R if H(r)],' benign dist',collections.Counter(len(r['target_hosts'].split(';')) for r in R if not H(r)))
print('src net x country',collections.Counter((r['src_network'],r['src_country'],r['account'][:3]) for r in R))
# external src ip per account
ea=collections.defaultdict(set)
for r in R:
    if r['src_network']!='internal': ea[r['account']].add(r['src_ip'])
print({k:len(v) for k,v in ea.items()})
print('svc sessions', [(r['account'],r['src_ip'],r['src_network'],r['login_utc'],r['auth_method'],r['target_hosts'],r['change_ticket']) for r in R if r['account'].startswith('svc')][:60])
