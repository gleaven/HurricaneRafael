"""Area 7: forbidden / date-gated terms in public-voice text (alerts, broadcast, statements, social posts, CAD narratives)."""
import json, csv, glob, os, re, datetime, collections
from common import *
D0=datetime.date(2027,9,14)
FORB=['Halcyon Drift','KESTREL','GridWater','GW-ENG-VELA','ClearPath','Barge 44','Valero','Citgo','Flint Hills','Caller-Times','Caller Times','KIII','KRIS','Spohn','Driscoll','Auriga','Pier 9','FAC-CCMC','7c1234','STATE-X']
forb=[(t,re.compile(re.escape(t).replace(r'\ ',r'\s*'),re.I)) for t in FORB]
rt=json.load(open(os.path.join(ROOT,'02_public_record','restricted_terms.json')))
terms=[(t['pattern'],re.compile(t['pattern'],re.I),t['public_from_day']) for t in rt['terms']]
hits=collections.Counter(); ex=collections.defaultdict(list); nrec=collections.Counter()
def check(stream,day,text,ref):
    nrec[stream]+=1
    for t,rx in forb:
        if rx.search(text):
            # KRIS / KIII word-boundary to avoid e.g. 'Kristen'
            if t in('KRIS','KIII') and not re.search(r'\b'+t+r'\b',text): continue
            hits[(stream,'FORBIDDEN',t)]+=1; ex[(stream,'FORBIDDEN',t)].append((ref,day,text[:160]))
    for pat,rx,pd_ in terms:
        m=rx.search(text)
        if m and (pd_ is None or (day is not None and day<pd_)):
            k=(stream,'GATED' if pd_ is not None else 'NEVER',pat[:40]); hits[k]+=1; ex[k].append((ref,day,m.group(0),text[max(0,m.start()-70):m.end()+70]))
def dayof(dt): return (dt.date()-D0).days
def local(dtutc): return dtutc-datetime.timedelta(hours=5 if dtutc<datetime.datetime(2027,11,7,7) else 6)
# social
for f in glob.glob(os.path.join(SRC,'social_media','*.jsonl')):
    for line in open(f,encoding='utf-8'):
        if not line.strip(): continue
        o=json.loads(line)
        if 'created_at' not in o or 'user' not in o: nrec['social_skipped:'+os.path.basename(f)]+=1; continue
        t=datetime.datetime.strptime(o['created_at'],'%a %b %d %H:%M:%S +0000 %Y')
        txt=(o.get('full_text') or o.get('text') or '')+' @'+o['user'].get('screen_name','')+' '+o['user'].get('name','')
        check('social',dayof(local(t)),txt,os.path.basename(f)+':'+o['id_str'])
# statements
for f in glob.glob(os.path.join(SRC,'press_releases','*.jsonl')):
    for line in open(f,encoding='utf-8'):
        if not line.strip(): continue
        o=json.loads(line); d=datetime.date.fromisoformat(o['date_local'])
        txt=o['text']+' '+o.get('issuer','')+' '+json.dumps(o.get('speakers',''))
        check('statements',(d-D0).days,txt,o['id'])
# alerts
for r in csv.DictReader(open(os.path.join(SRC,'public_health','eas_broadcasts.csv'),encoding='utf-8')):
    t=datetime.datetime.strptime(r['IssuedAt_UTC'],'%Y-%m-%dT%H:%M:%SZ'); check('alerts',dayof(local(t)),r['Headline_EN']+' '+r['Headline_ES'],r['AlertID'])
# broadcast
for f in glob.glob(os.path.join(SRC,'broadcast','*.csv')):
    for r in csv.DictReader(open(f,encoding='utf-8')):
        ts=r.get('air_time_utc') or r.get('received_utc') or r.get('source_received_utc')
        t=datetime.datetime.strptime(ts,'%Y-%m-%dT%H:%M:%SZ'); txt=' '.join(v for k,v in r.items() if k in('description','note','topic','item','station_name','english_insertions') and v)
        check('broadcast:'+os.path.basename(f),dayof(local(t)),txt,ts)
# CAD narratives
for f in glob.glob(os.path.join(SRC,'911','cad_incidents_*.csv')):
    for r in csv.DictReader(open(f,encoding='utf-8')):
        d=datetime.date.fromisoformat(r['call_received_dttm'][:10]); check('cad_narrative',(d-D0).days,r['narrative']+' '+r['address'],r['incident_number'])
print(dict(nrec))
for k,v in sorted(hits.items()):
    print(v,k); 
    for e in ex[k][:3]: print('     ',e)
