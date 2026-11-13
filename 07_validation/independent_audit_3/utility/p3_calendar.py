#!/usr/bin/env python3
"""Pass 3: daily/hourly activity profile: interactive logons (4624 type 2/11) of office staff, proxy allowed web rows, zeek conn. Weekends, US holidays, storm."""
import json,csv,glob,collections,datetime
R="./"; B=R+"05_other_sources/network_logs/"
reg=json.load(open(R+"06_data_streams/gw_host_registry.json"))
office={u['username'] for u in reg['users'] if u['normal_hours'].startswith('Mon-Fri')}
day=collections.Counter(); hr=collections.Counter(); hrwe=collections.Counter()
for f in sorted(glob.glob(B+'windows/security_*.jsonl')):
    for l in open(f):
        if '"event_id":4624' in l and ('"logon_type":2' in l or '"logon_type":11' in l):
            d=json.loads(l)
            if d['user'] in office:
                t=datetime.datetime.strptime(d['time_utc'][:19],'%Y-%m-%dT%H:%M:%S')-datetime.timedelta(hours=5 if t_cdt(d['time_utc']) else 6) if False else None
                t=datetime.datetime.strptime(d['time_utc'][:19],'%Y-%m-%dT%H:%M:%S')
                loc=t-datetime.timedelta(hours=5 if t<datetime.datetime(2027,11,7,7) else 6)
                day[loc.date()]+=1
                (hr if loc.weekday()<5 else hrwe)[loc.hour]+=1
px=collections.Counter()
for r in csv.reader(open('/tmp/px.csv')):
    if r[8]=='allowed' and r[4]!='dns':
        t=datetime.datetime.strptime(r[0][:19],'%Y-%m-%dT%H:%M:%S'); loc=t-datetime.timedelta(hours=5 if t<datetime.datetime(2027,11,7,7) else 6); px[loc.date()]+=1
wd=collections.defaultdict(list)
for d,v in day.items(): wd[d.weekday()].append(v)
import statistics
print('office interactive logons per local day by weekday (median):',{k:statistics.median(v) for k,v in sorted(wd.items())})
print('weekday local hour profile',sorted(hr.items()))
print('weekend local hour profile',sorted(hrwe.items()))
for name,d in [('Labor Day Mon',datetime.date(2027,9,6)),('Tue after',datetime.date(2027,9,7)),('Thanksgiving Thu',datetime.date(2027,11,25)),('Fri after',datetime.date(2027,11,26)),('Wed before',datetime.date(2027,11,24)),('Christmas Eve Fri',datetime.date(2027,12,24)),('Mon 12-27',datetime.date(2027,12,27)),('Fri 12-31',datetime.date(2027,12,31)),('Columbus Mon 10-11',datetime.date(2027,10,11)),('Veterans Thu 11-11',datetime.date(2027,11,11))]:
    print(name,d,'logons',day[d],'proxy web rows',px[d])
print('storm week logons',[(str(d)[5:],day[d],px[d]) for d in sorted(day) if datetime.date(2027,9,9)<=d<=datetime.date(2027,9,30)])
