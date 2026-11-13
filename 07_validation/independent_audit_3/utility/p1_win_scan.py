#!/usr/bin/env python3
"""Pass 1: Windows JSONL scan: per event_id key sets and low-cardinality field values; rare values. usage: p1_win_scan.py <glob-prefix: security|system|defender>"""
import json,glob,collections,sys
B="./05_other_sources/network_logs/windows/"
pref=sys.argv[1]
ev=collections.Counter(); keys=collections.defaultdict(collections.Counter); vals=collections.defaultdict(collections.Counter)
n=0
for f in sorted(glob.glob(B+pref+"_*.jsonl")):
    for l in open(f):
        d=json.loads(l); n+=1; e=d['event_id']; ev[e]+=1
        keys[e][tuple(d.keys())]+=1
        for k,v in d.items():
            if k in('time_utc','record_id','logon_id','src_port','path','share_path','relative_target'): continue
            c=vals[(e,k)]
            if len(c)<3000: c[str(v)]+=1
print(n)
for e in sorted(ev):
    print('==',e,ev[e])
    for ks,c in keys[e].most_common(4): print('   keys',c,ks[7:])
    for (ee,k),c in vals.items():
        if ee!=e or k in('channel','provider','event_id','level'): continue
        if len(c)<=12: print('   ',k,dict(c.most_common()))
        else:
            rare=[(a,b) for a,b in c.items() if b<=2]
            print('   ',k,'card',len(c),'top',c.most_common(3),'rare',len(rare),rare[:8])
