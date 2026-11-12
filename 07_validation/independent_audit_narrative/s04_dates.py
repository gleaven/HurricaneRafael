import sys; sys.path.insert(0,"./07_validation/independent_audit_narrative")
from common import *
import datetime
ss=sorted(stories(), key=tkey)
MON={'Jan':1,'Feb':2,'Aug':8,'Sept':9,'Sep':9,'Oct':10,'Nov':11,'Dec':12,'September':9,'October':10,'November':11,'December':12,'January':1}
def day_of(mo,dd):
    yr=2028 if mo in(1,2) else 2027
    return (datetime.date(yr,mo,dd)-datetime.date(2027,9,14)).days
# keyword -> allowed day offsets
K=[(r'partly reopen|partial reopening|reabri\w+ en parte',{30}),
   (r'(channel|canal)[^.]{0,40}reopen(ed|s)?\b(?! partly)|reopened (Thursday|after)',{58,30}),
   (r'blast|explosion|explosi[oó]n',{44,46,49,52}),
   (r'second (explosive )?device',{52}),
   (r'citywide boil-water notice[^.]{0,60}(lifted|was lifted)|lift(ed)? (its|the) (citywide )?boil-water notice',{39,42}),
   (r'boil-water notice[^.]{0,30}(issued|since|in effect since|followed)|issued (its|a) (citywide )?boil-water notice',{4,12}),
   (r'landfall|came ashore|made landfall',{0}),
   (r'registration (opens|opened)|inscripci[oó]n abr',{60}),
   (r'approved Individual Assistance|Individual Assistance (was )?approved',{57}),
   (r'claims center[^.]{0,30}open',{12,63}),
   (r'debris contract|sole-source',{10}),
   (r'search warrant|searched the offices',{104}),
   (r'responsible part(y|ies)',{7}),
   (r'fishing[^.]{0,40}clos(ed|ure)',{4,21}),
   (r'unauthorized remote access',{6}),
   (r'credentials were misused',{8}),
   (r'Pelican Ridge',{30,31,38}),
   (r'paused payments',{80}),
   (r'suspended Quellmar',{75}),
   (r'410 (applicant )?accounts',{71}),
   (r'moved to monitoring',{44}),
   (r'Gulf Provider[^.]{0,40}(berthed|unloaded|docked)',{33}),
   (r'transmitter',{47}),
   (r'attribut',{112}),
   (r'forfeiture',{114}),
  ]
dp=re.compile(r'\b(Jan|Feb|Aug|Sept|Sep|Oct|Nov|Dec|September|October|November|December|January)\.? (\d{1,2})\b')
full=lambda s: re.sub(r'\s+',' ',text(s))
for s in ss:
    t=full(s)
    # split into sentences not breaking on "Sept." etc.
    parts=re.split(r'(?<=[a-z0-9"”\)])[.!?] (?=[A-Z"“])',t)
    for x in parts:
        ds=[(m.group(0),day_of(MON[m.group(1)],int(m.group(2)))) for m in dp.finditer(x)]
        if len(ds)!=1: continue
        for pat,ok in K:
            if re.search(pat,x,re.I):
                if ds[0][1] not in ok and not any(abs(ds[0][1]-o)<=0 for o in ok):
                    print(s['story_id'],s['day'],'|',pat[:25],'|',ds[0],'|',x[:230])
