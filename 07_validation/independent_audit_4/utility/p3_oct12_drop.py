#!/usr/bin/env python3
"""Defect 5: alerts by rule and day 2027-10-09..10-21, web-filter rows, office logons, mail rows (needs caches and p3_windows.py run first)."""
import pickle,collections
h,S=pickle.load(open('/tmp/c/siem.pkl','rb')); ix={n:i for i,n in enumerate(h)}
days=['2027-10-%02d'%d for d in range(9,22)]
c=collections.Counter((r[ix['rule_name']],r[ix['time_utc']][:10]) for r in S if r[ix['time_utc']][:10] in days)
print('rule',days[0],'..',days[-1])
for ru in sorted({k[0] for k in c}): print(f'{ru:28s}',[c[(ru,d)] for d in days])
hr=collections.Counter(r[ix['time_utc']][11:13] for r in S if r[ix['time_utc']][:10]=='2027-10-12'); print('hourly 10-12',[hr['%02d'%x] for x in range(24)])
h2,P=pickle.load(open('/tmp/c/proxy.pkl','rb')); i2={n:i for i,n in enumerate(h2)}
pc=collections.Counter((r[i2['action']],r[i2['scheme']]=='dns',r[0][:10]) for r in P if r[0][:10] in days)
for k in (('blocked',False),('allowed',True),('allowed',False)): print('web filter',k,[pc[(k[0],k[1],d)] for d in days])
bd=pickle.load(open('/tmp/c/office_logons_byday.pkl','rb')); print('office interactive logons',[bd.get(d,0) for d in days])
M=[l.split(',')[0][:10] for l in open('audit/mail_gateway_cbpwa.csv')][1:]
mc=collections.Counter(M); print('mail gateway rows',[mc[d] for d in days])
