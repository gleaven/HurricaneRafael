from lib import *
import sys
for o in ORGS:
    for k in KINDS:
        h,r=load(o,k)
        print(o,k,len(r),r[0]['time_utc'],r[-1]['time_utc'],sum(1 for x in r if '_bad' in x))
