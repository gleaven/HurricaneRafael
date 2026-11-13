#!/usr/bin/env python3
"""Cache zeek logs per month into /tmp/c/zeek_<log>_<month>.pkl (list of row lists) to work in pieces."""
import sys,glob,pickle,os,time
log=sys.argv[1]; months=sys.argv[2:]
for m in months:
    out=f'/tmp/c/zeek_{log}_{m}.pkl'
    if os.path.exists(out): continue
    rows=[];hdrs=set()
    t=time.time()
    for d in sorted(glob.glob(f'zeek/{m}-*/')):
        p=d+log+'.log'
        if not os.path.exists(p): continue
        for line in open(p,encoding='utf-8'):
            if line[0]=='#':
                if line.startswith('#fields') or line.startswith('#types'): hdrs.add(line.rstrip('\n'))
                continue
            rows.append(line.rstrip('\n').split('\t'))
    pickle.dump((sorted(hdrs),rows),open(out,'wb'))
    print(m,log,len(rows),len(hdrs),round(time.time()-t,1))
