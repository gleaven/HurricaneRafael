import json,glob,re,collections,datetime as dt,pickle
SRC="./05_other_sources"
rules={ # name: (regex, earliest allowed UTC)
 'curfew':(r'curfew|toque de queda','2027-09-15T14:00'),
 'boil':(r'boil.?water|hervir el agua|hiervan','2027-09-18T11:00'),
 'spill':(r'oil spill|derrame|slick|sheen','2027-09-14T04:00'),
 'districts34':(r'district(s)? (3|4|three|four)|distrito(s)? (3|4)','2027-09-26T22:30'),
 'blast':(r'blast|explosion|explosi[oó]n|detonat','2027-10-28T06:00'),
 'second device':(r'second device|segundo artefacto|mine\b|mines\b','2027-10-28T06:00'),
 'gps':(r'\bgps\b.*(interfer|jam|spoof|anomal|outage)|jamm(ing|er)','2027-10-22T05:00'),
 'hack':(r'hack|cyber|intrusion|ciberataque|malware|breach','2027-10-04T19:00'),
 'drone_base':(r'drone|dron\b|drones|uas\b','2027-09-15T00:00'),
 'account takeover':(r'direct deposit|account (was )?(taken|hacked|changed)|deposit (info|details)','2027-11-15T19:00'),
 'IA register':(r'disasterassistance|register(ed)? (for|with) fema|individual assistance','2027-10-09T00:00'),
 'crypto/noro':(r'norovirus|cryptospor|parasite|giardia','2027-09-29T00:00'),
 'pelican':(r'pelican ridge','2027-10-22T00:00'),
 'vantorra':(r'vantorra','2027-09-24T00:00'),
 'quellmar':(r'quellmar','2027-10-04T00:00'),
 'corrin':(r'corrin bay','2027-10-28T06:00'),
 'rafael':(r'\brafael\b','2027-09-04T00:00'),
 'gridwater':(r'gridwater|halcyon|kestrel|GW-ENG|clearpath','2099-01-01T00:00'),
 'internal':(r'\bD[+-]\d+\b|\bT\d{1,2}\b thread|scenario|synthetic|EVT-\d|PUB-\d','2099-01-01T00:00'),
 'landfall_past':(r'made landfall|after the storm|since the storm|después de la tormenta','2027-09-14T06:00'),
 'power back':(r'power (is )?back|lights (are )?back|volvi[oó] la luz','2027-09-14T08:00'),
}
rx={k:re.compile(v[0],re.I) for k,v in rules.items()}
early=collections.defaultdict(list); n=0; first={}
def gettime(d):
    for k in('created_at_utc','created_at','timestamp','time_utc','posted_utc'):
        if k in d: return d[k]
for f in glob.glob(SRC+'/social_media/*.jsonl'):
    for l in open(f,encoding='utf-8'):
        try: d=json.loads(l)
        except: continue
        n+=1
        t=gettime(d); txt=d.get('full_text') or d.get('text') or ''
        if not t: continue
        if not t[0].isdigit():
            t=dt.datetime.strptime(t,'%a %b %d %H:%M:%S %z %Y').astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for k,r in rx.items():
            if r.search(txt):
                if k not in first or t<first[k][0]: first[k]=(t,txt[:140],f.split('/')[-1])
                if t<rules[k][1]: early[k].append((t,txt[:160],f.split('/')[-1]))
print('posts',n)
for k in rules:
    e=sorted(early[k]); print('\n##',k,'early',len(e),'first',first.get(k))
    for x in e[:4]: print('   ',x)
    c=collections.Counter(x[1][:60] for x in e).most_common(4)
    if e: print('   top texts',c)
