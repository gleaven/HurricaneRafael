"""Area 6: ED line list vs syndromic summary; surges; GI wave; wastewater; hospital capacity."""
import pandas as pd, numpy as np, os, glob
from common import *
ed=pd.concat([pd.read_csv(f,dtype={'Patient_ZIP':str,'Patient_Tract':str}) for f in sorted(glob.glob(os.path.join(SRC,'public_health','ed_visits_*.csv')))],ignore_index=True)
ed['t']=pd.to_datetime(ed.Arrive_Date_Time,utc=True).dt.tz_localize(None)
ed['d']=(pd.to_datetime(ed.Visit_Date)-pd.Timestamp('2027-09-14')).dt.days
print('ED rows',len(ed),'facilities',ed.Facility_ID.value_counts().to_dict(),'dup ids',ed.Visit_ID.duplicated().sum())
loc=(ed.t-pd.Timedelta(hours=5)).dt.strftime('%Y-%m-%d'); print('Visit_Date != local date of arrival (CDT):',(loc!=ed.Visit_Date).sum(),' != UTC date:',(ed.t.dt.strftime('%Y-%m-%d')!=ed.Visit_Date).sum())
print('onset after visit:',(pd.to_datetime(ed.Onset_Date)>pd.to_datetime(ed.Visit_Date)).sum())
daily=ed.groupby('d').size(); print('baseline/day D-30..D-8',daily.loc[-30:-8].mean().round(0))
cat=ed.groupby(['d','CC_Category']).size().unstack(fill_value=0)
print('categories',list(cat.columns))
show=[c for c in ['GI','INJ','TRAUMA','RESP','SKIN','DERM','ENV','CO'] if c in cat.columns]
tab=cat[show].copy(); tab['ALL']=daily; tab['SRMC']=ed[ed.Facility_ID=='FAC-SRMC-001'].groupby('d').size()
print(tab.loc[-6:32].to_string())
for c in show: print(c,'baseline mean D-30..D-8',cat[c].loc[-30:-8].mean().round(1),' D+6..D+14 mean',cat[c].loc[6:14].mean().round(1),' D+18..D+22',cat[c].loc[18:22].mean().round(1),' D+60+',cat[c].loc[60:].mean().round(1))
s=ed[(ed.Facility_ID=='FAC-SRMC-001')&(ed.t>='2027-09-14T05:00')&(ed.t<'2027-09-14T17:00')]; print('SRMC arrivals first 12 h of D0 local:',len(s))
# syndromic vs line list
sy=pd.read_csv(os.path.join(SRC,'public_health','syndrome_summary.csv'))
print('syndromic rows',len(sy),'areas sample',sy.Area_ID.unique()[:6])
a=ed.groupby(['Visit_Date','Facility_ID','CC_Category']).size().rename('ll')
b=sy.groupby(['Report_Date','Facility_ID','CC_Category']).Visit_Count.sum().rename('ss'); b.index.names=a.index.names
m=pd.concat([a,b],axis=1).fillna(0); m['diff']=m.ss-m.ll
print('facility/day/category cells',len(m),' mismatching:',(m['diff']!=0).sum(),' total line list',int(m.ll.sum()),' total summary',int(m.ss.sum()))
print(m[m['diff']!=0].head(10).to_string())
ed['area']='AREA-ZIP-'+ed.Patient_ZIP
a2=ed.groupby(['Visit_Date','Facility_ID','area','CC_Category']).size().rename('ll'); b2=sy.groupby(['Report_Date','Facility_ID','Area_ID','CC_Category']).Visit_Count.sum().rename('ss'); b2.index.names=a2.index.names
m2=pd.concat([a2,b2],axis=1).fillna(0); print('by area cells',len(m2),'mismatch',((m2.ss-m2.ll)!=0).sum())
adm=ed[ed.Disposition.str.contains('Admit',na=False)].groupby(['Visit_Date','Facility_ID','CC_Category']).size().rename('ll'); bb=sy.groupby(['Report_Date','Facility_ID','CC_Category']).Admitted_Count.sum().rename('ss'); bb.index.names=adm.index.names
m3=pd.concat([adm,bb],axis=1).fillna(0); print('admitted mismatch cells',((m3.ss-m3.ll)!=0).sum(),'of',len(m3),' dispositions',ed.Disposition.value_counts().to_dict())
# D3/D4 crypto cluster
g=ed[ed.Discharge_Diagnosis_ICD10.astype(str).str.startswith(('A07.1','A07.2'))]; print('crypto/giardia dx rows',len(g),'range',g.Visit_Date.min(),g.Visit_Date.max()); print(g.groupby('d').size().loc[10:32].to_dict())
print(' before D+13:',(g.d<13).sum(), ' language share',g.Preferred_Language.value_counts(normalize=True).round(2).to_dict())
nv=ed[ed.Discharge_Diagnosis_ICD10.astype(str).str.startswith('A08')]; print('norovirus/viral GI dx',len(nv),nv.groupby('d').size().loc[0:16].to_dict())
ww=pd.read_csv(os.path.join(SRC,'public_health','wastewater_surveillance.csv')); n=ww[ww.target.str.contains('Noro')]; n=n.assign(d=(pd.to_datetime(n.sample_date)-pd.Timestamp('2027-09-14')).dt.days)
print(n.groupby('d').normalized_ratio.mean().round(4).loc[-10:25].to_dict()); print('targets',ww.target.unique())
hc=pd.read_csv(os.path.join(SRC,'public_health','hospital_capacity.csv'))
x=hc[hc.Facility_ID.isin(['FAC-SRMC-001','FAC-BCMC-002'])&hc.Report_Date.isin(['2027-09-14','2027-09-16','2027-09-22','2027-10-12'])]
print(x[['Report_Date','Facility_ID','Inpatient_Census','Pct_Licensed_Occupancy','Triage_Tent_Patients','ED_Visits_24h','Power_Source','Generator_Start_UTC','Commercial_Power_Restored_UTC','Generator_Hours_Cumulative']].to_string())
e24=ed.groupby(['Visit_Date','Facility_ID']).size().rename('ll').reset_index(); hh=hc.merge(e24,left_on=['Report_Date','Facility_ID'],right_on=['Visit_Date','Facility_ID'],how='left')
print('hospital_capacity ED_Visits_24h vs line list same-day: equal',(hh.ED_Visits_24h==hh.ll).sum(),'of',len(hh),' mean abs diff',(hh.ED_Visits_24h-hh.ll).abs().mean().round(1))
