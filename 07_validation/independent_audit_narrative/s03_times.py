import sys; sys.path.insert(0,"./07_validation/independent_audit_narrative")
from common import *
ss=sorted(stories(), key=tkey)
F={f['id']:f for f in facts()['facts']}
for s in ss:
    for pid in s['tags'].get('public_facts') or []:
        f=F.get(pid)
        if not f: print('UNKNOWN FACT',s['story_id'],pid); continue
        if f['day']>s['day']: print('FUTURE FACT',s['story_id'],s['day'],pid,f['day'])
        elif f['day']==s['day'] and f.get('time_local') and s['time_local']<f['time_local']:
            print('BEFORE FACT TIME',s['story_id'],s['time_local'],pid,f['time_local'])
        elif f['day']==s['day'] and f.get('time_local') and s['time_local']==f['time_local']:
            print('SAME MINUTE',s['story_id'],s['time_local'],pid,f['time_local'])
# stories without time or with weird times
for s in ss:
    if not re.match(r'^\d\d:\d\d$',s.get('time_local') or ''): print('BAD TIME',s['story_id'],s.get('time_local'))
# D0 stories before landfall etc: list D0 stories before 06:00 with headline
for s in ss:
    if s['day']==0 and s['time_local']<'07:00': print('D0 early',s['story_id'],s['time_local'],s['outlet_id'],s['headline'][:90])
    if s['day']==44 and s['time_local']<'06:00': print('D44 early',s['story_id'],s['time_local'],s['headline'][:90])
