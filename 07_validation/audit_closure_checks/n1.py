import json,glob,re,collections,os
def norm(s): return re.sub(r'\s+',' ',s.replace('’',"'").replace('‘',"'").replace('“','"').replace('”','"').replace('–','-').replace('—','-')).lower()
items={}
for f in glob.glob('03_news/stories/batch-*.json'):
    d=json.load(open(f,encoding='utf-8')); L=d if isinstance(d,list) else d.get('stories',d.get('items',[]))
    for s in L: items[s.get('story_id') or s.get('id')]=norm(json.dumps(s,ensure_ascii=False))
for f in ['02_public_record/public_record.json']+glob.glob('scenarios/*/02_public_record/public_record.json'):
    d=json.load(open(f,encoding='utf-8')); L=d if isinstance(d,list) else next(v for v in d.values() if isinstance(v,list))
    for s in L: items[s.get('fact_id') or s.get('id')]=norm(json.dumps(s,ensure_ascii=False))
for f in ['00_scenario/msel.json']+glob.glob('scenarios/*/00_scenario/msel.json'):
    d=json.load(open(f,encoding='utf-8')); L=d if isinstance(d,list) else next(v for v in d.values() if isinstance(v,list))
    for s in L: items[s.get('event_id') or s.get('id')]=norm(json.dumps(s,ensure_ascii=False))
blob={f:norm(open(f,encoding='utf-8').read()) for f in glob.glob('_thread_designs/*.json')+['00_scenario/canon_timeline.json','01_characters/canon.json','00_scenario/msel.json','02_public_record/public_record.json']+glob.glob('03_news/stories/batch-*.json') if os.path.exists(f)}
print('items',len(items))
D=json.load(open('07_validation/independent_audit_narrative/defects.json',encoding='utf-8'))
out=[]
for x in D:
    q=x.get('quote','').replace('’',"'").replace('‘',"'")
    fr=re.findall(r"'((?:[^']|'(?=[a-z]))+)'",q)
    fr2=[]
    for f in fr:
        for part in re.split(r'\s*\.\.\.\s*|\s*…\s*',f):
            part=part.strip(' .,;')
            if len(part)>=6: fr2.append(part)
    ids=re.findall(r'(?:NWS-[MP]\d{3}-\d{2,3}|GW-PUB-\d+|PUB-\d+|GW-EVT-\d+|EVT-\d+)',x.get('item_id','')+' '+q)
    # expand "NWS-P057-03" style only; resolve
    scope=[items[i] for i in ids if i in items]
    left=[]
    for f in fr2:
        nf=norm(f)
        if scope: hit=any(nf in t for t in scope)
        else: hit=any(nf in t for t in blob.values())
        if hit: left.append(f)
    out.append({'id':x['id'],'severity':x['severity'],'item':x.get('item_id'),'n_fragments':len(fr2),'still_present':left,'scoped':bool(scope),'ids_missing':[i for i in ids if i not in items]})
json.dump(out,open('07_validation/reports/narrative_fragments.json','w'),indent=1)
for o in out:
    print(o['id'],o['severity'][:3],'frag',o['n_fragments'],'left',len(o['still_present']),'scoped' if o['scoped'] else 'GLOBAL',o['still_present'][:6],('missing ids '+str(o['ids_missing'])) if o['ids_missing'] else '')
