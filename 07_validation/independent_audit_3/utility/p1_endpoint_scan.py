#!/usr/bin/env python3
"""Pass 1: endpoint telemetry scan, one month per call, cached to cache/ep_<month>.pkl. usage: p1_endpoint_scan.py 2027-09 | report"""
import json,glob,collections,sys,pickle,os
B="./05_other_sources/network_logs/endpoint/"
C=os.path.dirname(os.path.abspath(__file__))+"/cache/"
def scan(m):
    ev=collections.Counter(); keys=collections.defaultdict(collections.Counter); vals=collections.defaultdict(collections.Counter)
    for l in open(B+f"endpoint_{m}.jsonl"):
        d=json.loads(l); e=d['event_type']; ev[e]+=1; keys[e][tuple(d.keys())]+=1
        for k,v in d.items():
            if k in('time_utc','pid','src_port','ppid','src_ip','answers'): continue
            if k in ('query','dst_ip','sha256','path','target_filename','command_line','host','user') and not (k in('host','user') and e in('process_start',)): 
                if k not in('command_line','path','target_filename','sha256'): continue
            c=vals[(e,k)]
            if len(c)<20000: c[str(v)]+=1
    pickle.dump((ev,keys,vals),open(C+f"ep_{m}.pkl","wb"))
if sys.argv[1]!='report':
    scan(sys.argv[1]); print('done',sys.argv[1])
else:
    ev=collections.Counter(); keys=collections.defaultdict(collections.Counter); vals=collections.defaultdict(collections.Counter)
    for f in sorted(glob.glob(C+"ep_*.pkl")):
        a,b,c=pickle.load(open(f,'rb')); ev.update(a)
        for k in b: keys[k].update(b[k])
        for k in c: vals[k].update(c[k])
    print(sum(ev.values()))
    for e in sorted(ev):
        print('==',e,ev[e])
        for ks,c in keys[e].most_common(3): print('   keys',c,ks[6:])
        for (ee,k),c in vals.items():
            if ee!=e or k in('event_type',): continue
            if len(c)<=14: print('   ',k,dict(c.most_common()))
            else:
                rare=[(a,b) for a,b in c.items() if b<=2]
                print('   ',k,'card',len(c),'top',c.most_common(3),'rare',len(rare),rare[:10])
