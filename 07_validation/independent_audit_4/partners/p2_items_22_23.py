# Pass 2 items 22, 23: port condition mail; alert origination web requests vs eas_broadcasts
import sys,re,collections; sys.path.insert(0,'.')
from common import *
m=load('mail'); w=load('web'); a=load('auth'); d=load('dns')
pc=pd.read_csv(ROOT+'/05_other_sources/supply/port_conditions.csv',dtype=str,keep_default_na=False)
print(pc.columns.tolist(),len(pc)); print(pc.head(12).to_string()[:3000])
pm=m[m.org=='port']
x=pm[pm.subject.str.contains('(?i)port condition|MSIB|captain of the port|zulu|yankee|x-ray|channel|safety zone')]
print('port mail matching port-condition subjects:',len(x)); print(x[['time_utc','direction','sender','recipient','subject']].to_string()[:6000])
print('\n===== ITEM 23 alerting service')
ea=pd.read_csv(ROOT+'/05_other_sources/public_health/eas_broadcasts.csv',dtype=str,keep_default_na=False)
print(ea.columns.tolist(),len(ea))
cand=w[w.host.str.contains('(?i)alert|ipaws|notif|warn|eas')]
print(cand.groupby(['org','host','category']).size().to_string())
