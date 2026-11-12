import pandas as pd, numpy as np, os, glob
from common import *
ed=pd.concat([pd.read_csv(f,dtype={'Patient_ZIP':str,'Patient_Tract':str}) for f in sorted(glob.glob(os.path.join(SRC,'public_health','ed_visits_*.csv')))],ignore_index=True)
ed['t']=pd.to_datetime(ed.Arrive_Date_Time,utc=True).dt.tz_localize(None); ed['d']=(pd.to_datetime(ed.Visit_Date)-pd.Timestamp('2027-09-14')).dt.days
off=np.where(ed.t<pd.Timestamp('2027-11-07T07:00'),5,6); loc=(ed.t-pd.to_timedelta(off,unit='h')).dt.strftime('%Y-%m-%d'); print('Visit_Date != local date (DST-aware):',(loc!=ed.Visit_Date).sum())
s=ed[(ed.Facility_ID=='FAC-SRMC-001')]; print('SRMC 06-18Z D0:',((s.t>='2027-09-14T06:00')&(s.t<'2027-09-14T18:00')).sum(),' 05-17Z:',((s.t>='2027-09-14T05:00')&(s.t<'2027-09-14T17:00')).sum(),' INJURY only 06-18Z:',((s.t>='2027-09-14T06:00')&(s.t<'2027-09-14T18:00')&(s.CC_Category=='INJURY')).sum(),' D0 local-day total',(s.d==0).sum())
c=ed.groupby(['d','CC_Category']).size().unstack(fill_value=0)
print(c[['INJURY','IRRITANT','HEAT','MH','RENAL']].loc[-3:24].T.to_string())
# shoreline tracts: IRRITANT+RESP+SKIN by tract, baseline vs D+3..D+21
x=ed[ed.CC_Category.isin(['RESP','SKIN','IRRITANT'])]
b=x[(x.d>=-30)&(x.d<=-8)].groupby('Patient_Tract').size()/23; p=x[(x.d>=3)&(x.d<=21)].groupby('Patient_Tract').size()/19
r=pd.concat([b.rename('base'),p.rename('post')],axis=1).fillna(0); r['ratio']=r.post/r.base.replace(0,np.nan)
print('tracts',len(r),'overall ratio',round(r.post.sum()/r.base.sum(),2)); print(r.sort_values('ratio',ascending=False).head(10).round(2).to_string())
gi=ed[ed.CC_Category=='GI']
for a,bb in ((-30,-8),(6,14),(15,17),(18,22),(23,28)):
    g=gi[(gi.d>=a)&(gi.d<=bb)]; print('GI D%+d..D%+d n=%d spanish %.0f%%'%(a,bb,len(g),(g.Preferred_Language=='Spanish').mean()*100), 'top zips',g.Patient_ZIP.value_counts().head(4).to_dict())
print('all visits spanish share',round((ed.Preferred_Language=='Spanish').mean()*100,1))
print('chief complaint text variety GI:',gi.Chief_Complaint_Text.nunique(),gi.Chief_Complaint_Text.value_counts().head(6).to_dict())
