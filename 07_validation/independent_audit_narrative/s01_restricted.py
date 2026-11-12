import sys; sys.path.insert(0,"./07_validation/independent_audit_narrative")
from common import *
rt=json.load(open(ROOT+'02_public_record/restricted_terms.json'))
ss=sorted(stories(), key=tkey)
extra=[(r'Auriga|Meridian Star|Meridian Marine|Costana|Pier 9|GridWater|Grid ?Water|Cavazos|Narwhal|Barge 44|Halcyon|VELA|ClearPath|JMP-01',None)]
for s in ss:
    t=text(s)
    for term in rt['terms']:
        for m in re.finditer(term['pattern'],t,re.I):
            pf=term['public_from_day']
            if pf is None or s['day']<pf:
                print('TERM',s['story_id'],s['day'],term['pattern'][:30],'|',t[max(0,m.start()-80):m.end()+80].replace('\n',' '))
    for p,_ in extra:
        for m in re.finditer(p,t):
            print('EXTRA',s['story_id'],s['day'],'|',t[max(0,m.start()-80):m.end()+80].replace('\n',' '))
    for pr in rt['pairs']:
        if re.search(pr['a'],t,re.I) and re.search(pr['b'],t,re.I):
            u=pr['until_day']
            if u is None or s['day']<u:
                print('PAIR',s['story_id'],s['day'],pr['a'][:25],'+',pr['b'][:25])
# public release copy
pub=json.load(open(ROOT+'08_release/news_stories_public.json'))
print(type(pub), (list(pub.keys()) if isinstance(pub,dict) else len(pub)))
