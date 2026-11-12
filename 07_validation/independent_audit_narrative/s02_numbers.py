import sys; sys.path.insert(0,"./07_validation/independent_audit_narrative")
from common import *
ss=sorted(stories(), key=tkey)
NUM=r'(?:\d[\d,\.]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|twenty[- ]?\w*|thirty[- ]?\w*|dozens?|hundreds?)'
Q={
 'deaths':re.compile(r'('+NUM+r')\s+(?:confirmed\s+|storm[- ]related\s+|people\s+|residents\s+)*(?:deaths?|dead|fatalit\w+|killed|muert\w+|fallecid\w+)|death toll[^.]{0,40}?('+NUM+')|(?:killed|claimed)\s+(?:at least\s+)?('+NUM+r')\b',re.I),
 'rescues':re.compile(r'('+NUM+r')\s+(?:confirmed\s+|total\s+|cumulative\s+|rooftop\s+|hoist\s+|helicopter\s+|people\s+|persons\s+|survivors\s+)*(?:rescue[ds]?|rescates|hoists?)\b',re.I),
 'outage':re.compile(r'('+NUM+r')\s+(?:CBPWA\s+|electric\s+|power\s+|utility\s+)?(?:customers|clientes|homes and businesses|households)\b',re.I),
 'shelter':re.compile(r'('+NUM+r')\s+(?:people|residents|evacuees|personas)?\s*(?:in|at|filled|were in|remain in)\s+(?:\w+\s+){0,2}(?:shelters?|albergues?)|shelters?\s+(?:held|housed|housing|holding)\s+(?:about\s+|nearly\s+|more than\s+)?('+NUM+')',re.I),
 'billion':re.compile(r'\$\s?([\d\.]+)\s*(?:to\s*\$?[\d\.]+\s*)?(?:billion|mil millones)',re.I),
 'sqmi':re.compile(r'([\d\.]+)\s+(?:square miles|millas cuadradas|square kilometers)',re.I),
 'structures':re.compile(r'('+NUM+r')\s+(?:\w+\s+){0,2}(?:structures|homes damaged|homes destroyed|buildings)',re.I),
}
which=sys.argv[1].split(',')
for q in which:
    print('=====',q)
    for s in ss:
        for x in sents(s):
            for m in Q[q].finditer(x):
                a=max(0,m.start()-70); b=min(len(x),m.end()+60)
                print(s['story_id'],s['_file'][6],'|',x[a:b])
