"""Area 7: social posts / statements that mention an event before it could be known."""
import json, glob, os, re, datetime, collections
from common import *
P=lambda s: datetime.datetime.strptime(s,'%Y-%m-%dT%H:%M')
RULES=[
 ('Rafael named',r'\bRafael\b',P('2027-09-04T00:00')),
 ('hurricane watch/warning',r'hurricane (watch|warning)',P('2027-09-11T00:00')),
 ('Category 3',r'\b(cat(egory)?\.?\s?(3|three))\b',P('2027-09-12T00:00')),
 ('mandatory evacuation',r'mandatory evac|evacuation order|orden de evacuaci',P('2027-09-12T11:00')),
 ('oil spill',r'oil spill|oil slick|\bslick\b|derrame|crude (in|on) the|oiled|tanker(s)? (leak|spill)',P('2027-09-14T04:00')),
 ('bridge closed',r'(harbor bridge|causeway).{0,40}(closed|shut)|(closed|shut).{0,40}(harbor bridge|causeway)',P('2027-09-14T00:00')),
 ('curfew',r'curfew|toque de queda',P('2027-09-15T00:00')),
 ('drones over base',r'\bdrones?\b.{0,60}(NAS|base|depot|navy)|(NAS|base|depot|navy).{0,60}\bdrones?\b',P('2027-09-15T00:00')),
 ('boil water',r'boil[- ]water|boil (your|the|our) water|hervir (el |la )?agua|hiervan',P('2027-09-18T11:00')),
 ('Districts 3/4 notice',r'district(s)? (3|4|three|four)|distritos? (3|4)',P('2027-09-26T16:00')),
 ('stomach illness wave',r'norovirus|stomach bug|everyone.{0,20}(vomit|throwing up)',P('2027-09-18T00:00')),
 ('parasite cluster',r'crypto(sporidi)?|giardia|parasite|par[aá]sito',P('2027-09-28T00:00')),
 ('utility hacked',r'hack(ed|ers|ing)?\b.{0,80}(CBPWA|grid|utility|power|water)|(CBPWA|grid|utility|power|water).{0,80}\bhack|cyber ?attack|ciberataque',P('2027-10-04T19:00')),
 ('GPS interference',r'\bGPS\b.{0,60}(jam|interfer|out|anomal|spoof)|jamm(ing|er)',P('2027-10-22T00:00')),
 ('AIS spoof / Pelican Ridge',r'pelican ridge|spoof(ed|ing)? (ais|identity|vessel)',P('2027-10-22T00:00')),
 ('jetty blast',r'(explosion|blast|bomb|mine|explosive).{0,80}(jett|tug|channel|port aransas)|(jett|tug|channel).{0,80}(explosion|blast|bomb|\bmine\b|explosive)',P('2027-10-28T06:10')),
 ('second device',r'second (device|bomb|mine|object)',P('2027-11-05T12:00')),
 ('channel reopened (2nd)',r'corrin bay',P('2027-10-28T06:10')),
 ('IA registration open',r'individual assistance|registration (is )?(now )?open|apply for (fema|disaster) (aid|assistance)|disasterassistance',P('2027-11-10T00:00')),
 ('account takeover',r'account (was |got )?(taken over|hijack|changed)|deposit (went|sent) to (another|a different|wrong)|someone changed my (bank|deposit)',P('2027-11-15T00:00')),
 ('Vantorra contract',r'vantorra',P('2027-09-24T00:00')),
 ('Quellmar',r'quellmar',P('2027-10-04T00:00')),
 ('Brightwake',r'brightwake',P('2027-09-22T00:00')),
 ('Kalvora/Ostrel',r'kalvora|ostrel',P('2027-09-15T00:00')),
 ('court filing names',r'brannoch|marrick',P('2028-01-06T00:00')),
 ('fuel contamination NAS',r'(contaminat|bad|water in).{0,30}fuel|fuel.{0,30}contaminat',P('2027-10-24T00:00')),
]
rules=[(n,re.compile(p,re.I),t) for n,p,t in RULES]
hits=collections.defaultdict(list); n=0
for f in glob.glob(os.path.join(SRC,'social_media','*.jsonl')):
    if os.path.basename(f).startswith('_'): continue
    for line in open(f,encoding='utf-8'):
        if not line.strip(): continue
        o=json.loads(line); t=datetime.datetime.strptime(o['created_at'],'%a %b %d %H:%M:%S +0000 %Y'); txt=o.get('full_text') or ''; n+=1
        for name,rx,t0 in rules:
            if t<t0 and rx.search(txt): hits[name].append((t.isoformat(),o['user']['screen_name'],txt[:170]))
for f in glob.glob(os.path.join(SRC,'press_releases','*.jsonl')):
    for line in open(f,encoding='utf-8'):
        if not line.strip(): continue
        o=json.loads(line); t=datetime.datetime.fromisoformat(o['issued_local']).astimezone(datetime.timezone.utc).replace(tzinfo=None) if o.get('issued_local') else None
        if t is None: continue
        for name,rx,t0 in rules:
            if t<t0 and rx.search(o['text']): hits['STATEMENT '+name].append((t.isoformat(),o['id'],o['text'][:170]))
print('posts scanned',n)
for name,_,t0 in rules:
    for k in (name,'STATEMENT '+name):
        h=sorted(hits.get(k,[]))
        print(f"{k:32s} before {t0}: {len(h)}")
        for e in h[:4]: print('      ',e)
