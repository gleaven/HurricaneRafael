from common import *
rs=load('network_logs/audit/remote_access_sessions.csv')
h=[r for r in rs if r['src_country']!='US']
print(len(h))
for r in h: print(r)
# order of ids vs time
ids=[int(r['session_id'].split('-')[1]) for r in rs]
t=[ts(r['login_utc']) for r in rs]
bad=sum(1 for i in range(1,len(rs)) if (ids[i]>ids[i-1])!=(t[i]>t[i-1]))
print('id/time order violations (file order):',bad, 'ids sorted by time monotonic:', all(a<b for a,b in zip([i for _,i in sorted(zip(t,ids))][:-1],[i for _,i in sorted(zip(t,ids))][1:])))
print('id gaps:', sorted(set(range(min(ids),max(ids)+1))-set(ids))[:20])
import collections
def prof(sel,name):
    print(name,len(sel),'pw-only',sum(r['auth_method']!='token' for r in sel),'noticket',sum(r['change_ticket']=='' for r in sel),
      'round1000 out',sum(int(r['bytes_out'])%1000==0 for r in sel),'round100',sum(int(r['bytes_out'])%100==0 for r in sel),'in round100',sum(int(r['bytes_in'])%100==0 for r in sel),
      'multi-target',sum(';' in r['target_hosts'] for r in sel))
prof(h,'hostile'); prof([r for r in rs if r not in h],'benign')
vela=[r for r in rs if r['account']=='GW-ENG-VELA']; prof(vela,'VELA all')
print('VELA by net',collections.Counter((r['src_network'],r['src_country']) for r in vela))
# AS-60729, AS-209144
print(collections.Counter((r['src_network'],r['src_country'],r['account']) for r in rs if r['src_network'] in('AS-60729','AS-209144','AS-64499')))
# hours local of hostile vs benign
print('hostile local hours',sorted(local(ts(r['login_utc'])).hour for r in h))
print('benign local hours',sorted(collections.Counter(local(ts(r['login_utc'])).hour for r in rs if r not in h).items()))
print('total hostile hours',sum(int(r['duration_s']) for r in h)/3600)
# multi target rows
for r in rs:
    if ';' in r['target_hosts']: print(r['session_id'],r['account'],r['src_country'],r['target_hosts'])
# ratio bytes
import statistics
print('hostile out/dur',[round(int(r['bytes_out'])/int(r['duration_s'])) for r in h])
b=[int(r['bytes_out'])/int(r['duration_s']) for r in rs if r not in h]
print('benign out/dur quantiles',[round(x) for x in statistics.quantiles(b,n=10)])
b=[int(r['bytes_in'])/max(1,int(r['bytes_out'])) for r in rs if r not in h]
print('benign in/out q',[round(x,2) for x in statistics.quantiles(b,n=10)], 'hostile',[round(int(r['bytes_in'])/int(r['bytes_out']),2) for r in h])
print('after 2027-10-12 sessions', sum(1 for r in rs if '2027-10-12T12'<r['login_utc']<'2027-10-19T20'))
