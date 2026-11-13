#!/usr/bin/env python3
"""Pass 1: SIEM value counts over all months; rare rules; alerts by rule x month; singletons."""
import csv,glob,collections,re,pickle,sys
C=collections.defaultdict(collections.Counter)
rule_month=collections.defaultdict(collections.Counter)
rows=0
keyshape=collections.Counter()
for f in sorted(glob.glob('siem/siem_alerts_*.csv')):
    m=f[-11:-4]
    for r in csv.DictReader(open(f,newline='',encoding='utf-8')):
        rows+=1
        for c in ('rule_id','rule_name','category','priority','disposition','closed_by','close_note','dst_port','user','src_host','dst_host'):
            C[c][r[c]]+=1
        C['rule']+=collections.Counter([r['rule_id']+'|'+r['rule_name']+'|'+r['category']+'|'+r['priority']])
        rule_month[r['rule_id']+'|'+r['rule_name']][m]+=1
        C['detail_shape'][r['rule_id']+'|'+re.sub(r'[0-9]+','N',re.sub(r'=[^ ;,]+','=V',r['detail']))[:80]]+=1
        C['idshape'][re.sub(r'[0-9]','N',r['alert_id'])]+=1
        C['sec'][r['time_utc'][17:19]]+=1
print('rows',rows)
pickle.dump((dict(C),dict(rule_month)),open(sys.argv[1],'wb'))
for c in ('category','priority','disposition','closed_by','close_note','dst_port','idshape'):
    mc=C[c].most_common()
    print('##',c,len(mc),mc[:25],'...',mc[-12:])
print('## rules')
for k,v in sorted(C['rule'].items(),key=lambda x:x[1]): print(v,k,dict(sorted(rule_month[k.split('|')[0]+'|'+k.split('|')[1]].items())))
