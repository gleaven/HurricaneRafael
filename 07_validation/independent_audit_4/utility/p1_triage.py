#!/usr/bin/env python3
"""Pass 1: triage collections - cross-host singletons in file listings, autoruns, tasks, services, execution history; placeholder hash check."""
import csv,glob,os,json,collections,hashlib
hosts=sorted(os.listdir('.'))
for kind,key in (('file_listing.csv',None),('autoruns.csv','name'),('scheduled_tasks.csv','task_name'),('services.csv','name'),('execution_history.csv','image_path'),('installed_software.csv','name')):
    seen=collections.defaultdict(set); rowsby={}
    for h in hosts:
        R=list(csv.DictReader(open(f'{h}/{kind}')))
        rowsby[h]=R
        if key is None: key=list(R[0].keys())[0]; print(kind,'cols',list(R[0].keys()))
        for r in R: seen[r[key]].add(h)
    print('==',kind,'distinct',len(seen),'rows per host',{h:len(rowsby[h]) for h in hosts})
    for k,v in sorted(seen.items(),key=lambda x:len(x[1])):
        if len(v)<=2: print('   rare:',k,sorted(v))
for h in hosts:
    c=json.load(open(f'{h}/collection.json'))
    ok=[]
    for s in c.get('samples',[]):
        d=hashlib.sha256(open(f"{h}/{s['file']}",'rb').read()).hexdigest()
        ok.append(d==s['sha256'])
    its=[]
    for n,i in c['items'].items():
        d=hashlib.sha256(open(f"{h}/{n}",'rb').read()).hexdigest()
        nrows=sum(1 for _ in open(f"{h}/{n}"))-1
        its.append((d==i['sha256'],nrows==i['rows']))
    print(h,c['ip'],c['os'],c['collected_utc'],c.get('case'),c.get('logon_history_window_days'),'samples ok',ok,'items ok',all(a and b for a,b in its), [k for k in c if k not in('host','ip','os','collected_utc','collected_by','tool','case','logon_history_window_days','items','samples','note')])
