import json,sys
c=json.load(open('./00_scenario/canon_timeline.json'))
def comp(o,ind=0):
    # compact: collapse 'when' dicts to label/utc
    if isinstance(o,dict):
        if 'utc' in o and 'day' in o: return o['utc']+' (D%+d)'%o['day']
        if 'date_local' in o and 'day' in o: return o['date_local']+' (D%+d)'%o['day']
        return {k:comp(v) for k,v in o.items() if k not in('sources',)}
    if isinstance(o,list): return [comp(x) for x in o]
    return o
for k in sys.argv[1:]:
    print('=====',k); print(json.dumps(comp(c[k]),indent=None,separators=(',',':'))[:9000])
