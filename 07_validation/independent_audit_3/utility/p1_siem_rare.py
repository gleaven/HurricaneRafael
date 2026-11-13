#!/usr/bin/env python3
"""Pass 1: SIEM alert rarity scan. Counts by rule, category, priority, disposition, closed_by; lists rare values."""
import csv,glob,collections,sys,os
B="./05_other_sources/network_logs"
rule=collections.Counter(); cat=collections.Counter(); pri=collections.Counter(); disp=collections.Counter(); cb=collections.Counter()
rp=collections.defaultdict(collections.Counter); rd=collections.defaultdict(collections.Counter)
first={}; last={}
note=collections.Counter(); 
rows=0
for f in sorted(glob.glob(B+"/siem/siem_alerts_*.csv")):
    for r in csv.DictReader(open(f,newline='')):
        rows+=1
        k=(r['rule_id'],r['rule_name'],r['category'])
        rule[k]+=1; pri[r['priority']]+=1; disp[r['disposition']]+=1; cb[r['closed_by']]+=1
        rp[k][r['priority']]+=1; rd[k][r['disposition']]+=1
        first.setdefault(k,r['time_utc']); last[k]=r['time_utc']
        note[r['close_note']]+=1
print(rows)
for k,v in sorted(rule.items(), key=lambda x:x[1]):
    print(v,k,dict(rp[k]),dict(rd[k]),first[k],last[k])
print(pri);print(disp);print(cb)
print('notes',len(note))
for k,v in sorted(note.items(), key=lambda x:x[1])[:60]: print(v,repr(k))
