#!/usr/bin/env python3
"""Pass 3: Windows Security internals. record_id monotonic per host+channel; logon_id format/uniqueness; 4624/4634 pairing; overlapping interactive sessions of one user on several hosts; lock/unlock inside sessions; proxy user = logged-on user. usage: p3_win_sessions.py 2027-09"""
import json,glob,collections,datetime,calendar,csv,sys
m=sys.argv[1]
R="./"; B=R+"05_other_sources/network_logs/"
reg=json.load(open(R+"06_data_streams/gw_host_registry.json")); ip2h={h['ip']:h['hostname'] for h in reg['hosts']}
def ep(s): return calendar.timegm(datetime.datetime.strptime(s[:19],'%Y-%m-%dT%H:%M:%S').timetuple())+float('0.'+s[20:23])
last={}; bad=0; n=0; dup=0; seenrid=set(); gaps=collections.Counter()
lid=collections.Counter(); lidfmt=collections.Counter()
opens={}; ses=[]; unpaired_off=0; st=collections.Counter()
locks=collections.defaultdict(list)
for ch in ('security','system','defender'):
    for f in sorted(glob.glob(B+f"windows/{ch}_{m}*.jsonl")):
        prev_t=''
        for l in open(f):
            d=json.loads(l); n+=1
            if d['time_utc']<prev_t: st[ch+' file not time-ordered']+=1
            prev_t=d['time_utc']
            k=(d['host'],d['channel']); r=d['record_id']
            if k in last:
                if r<=last[k][0]: bad+=1
                else: gaps[min(r-last[k][0],1000)//10]+=1
            last[k]=(r,d['time_utc'])
            e=d['event_id']
            if e==4624:
                x=d['logon_id']; lidfmt[(type(x).__name__, len(str(x)), str(x)[:2])]+=1
                kk=(d['host'],x)
                if kk in opens: st['logon_id reused while open']+=1
                opens[kk]=(ep(d['time_utc']),d['user'],d['logon_type'],d.get('src_ip'))
            elif e in(4634,):
                kk=(d['host'],d['logon_id'])
                if kk in opens:
                    a=opens.pop(kk); ses.append((d['host'],a[1],a[2],a[0],ep(d['time_utc']),a[3]))
                    if a[1]!=d['user']: st['4634 user != 4624 user']+=1
                else: unpaired_off+=1
            elif e in(4800,4801): locks[(d['host'],d['logon_id'])].append((ep(d['time_utc']),e))
print('events',n,'record_id non-increasing per host+channel',bad, dict(st))
print('record_id gap deciles (gap//10: count)',sorted(gaps.items())[:8],'...')
print('logon_id formats',lidfmt.most_common(5))
print('sessions paired',len(ses),'4634 without 4624 this month',unpaired_off,'still open at month end',len(opens))
du=collections.defaultdict(list)
for h,u,t,a,b,ip in ses: du[t].append(b-a)
import statistics
for t,v in sorted(du.items()): v.sort(); print(' type',t,'n',len(v),'median dur s %.0f p10 %.0f p90 %.0f max h %.1f'%(statistics.median(v),v[len(v)//10],v[len(v)*9//10],v[-1]/3600))
# overlapping interactive sessions same user on different hosts
iv=collections.defaultdict(list)
for h,u,t,a,b,ip in ses:
    if t in(2,11): iv[u].append((a,b,h))
ov=0; exo=[]
for u,v in iv.items():
    v.sort()
    for i in range(len(v)-1):
        if v[i+1][0]<v[i][1]-1 and v[i+1][2]!=v[i][2]:
            ov+=1
            if len(exo)<4: exo.append((u,v[i][2],v[i+1][2],datetime.datetime.utcfromtimestamp(v[i+1][0]).isoformat()))
print('interactive sessions of one user overlapping on two different hosts:',ov,exo)
# two different users interactive on same workstation at once
ih=collections.defaultdict(list)
for h,u,t,a,b,ip in ses:
    if t in(2,11): ih[h].append((a,b,u))
ov2=0
for h,v in ih.items():
    v.sort()
    for i in range(len(v)-1):
        if v[i+1][0]<v[i][1]-1 and v[i+1][2]!=v[i][2]: ov2+=1
print('two users with overlapping console sessions on one host:',ov2)
# locks inside sessions
sesidx={}
tot=inn=0
sx=collections.defaultdict(list)
for h,u,t,a,b,ip in ses: sx[h].append((a,b))
# proxy user check
logged=collections.defaultdict(list)
for h,u,t,a,b,ip in ses:
    if t in(2,11,10): logged[h].append((a,b,u))
for (h,x),(a,u,t,ip) in opens.items():
    if t in(2,11,10): logged[h].append((a,9e12,u))
pc=collections.Counter(); exs=[]
for r in csv.DictReader(open(B+f"proxy/web_proxy_{m}.csv")):
    h=ip2h.get(r['client_ip']); t=ep(r['time_utc'][:19]+'.000')
    on={u for a,b,u in logged.get(h,[]) if a-1<=t<=b+1}
    if r['user']=='-': pc['user - and nobody logged on' if not on else 'user - but someone logged on']+=1
    elif r['user'] in on: pc['user matches a logged-on session']+=1
    else:
        pc['user NOT logged on at that time']+=1
        if len(exs)<4: exs.append((r['time_utc'],h,r['user'],sorted(on)))
print('proxy user vs Windows sessions',dict(pc),exs)
