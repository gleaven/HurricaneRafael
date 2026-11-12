"""Area 8: aid applications, account takeovers, contracts, claims."""
import pandas as pd, numpy as np, os
from common import *
P=os.path.join(SRC,'payments')
a=pd.read_csv(os.path.join(P,'aid_applications.csv'),dtype=str)
print('aid rows',len(a),a.record_type.value_counts().to_dict())
for c in ['submitted_utc','changed_utc','event_utc','login_utc']:
    print(' ',c,'min',a[c].dropna().min(),'max',a[c].dropna().max(),'n',a[c].notna().sum())
app=a[a.record_type=='application']; print('applications before 2027-11-13T00:00Z:',(app.submitted_utc<'2027-11-13T00:00:00Z').sum(),' D+60..D+89 count (to 12 Dec 23:59Z):',((app.submitted_utc>='2027-11-13')&(app.submitted_utc<'2027-12-13')).sum())
print(' apps per day first 8 days:',app.submitted_utc.str[:10].value_counts().sort_index().head(8).to_dict())
ch=a[a.record_type!='application']; print('change/other record types:',ch.record_type.value_counts().to_dict(),' field_changed',ch.field_changed.value_counts().to_dict())
print(' login_ip_seen_before',ch.login_ip_seen_before.value_counts(dropna=False).to_dict())
dep=ch[ch.field_changed.fillna('').str.contains('deposit')]
print(' deposit changes total',len(dep),'accounts',dep.account_id.nunique(),' by login_ip_seen_before:',dep.groupby('login_ip_seen_before').account_id.nunique().to_dict())
sus=dep[dep.login_ip_seen_before.isin(['false','False','N','0','no'])]
print(' unseen-IP deposit changes: accounts',sus.account_id.nunique(),'window',sus.changed_utc.min(),sus.changed_utc.max()); print('  per day',sus.changed_utc.str[:10].value_counts().sort_index().to_dict())
print('  new deposit accounts distinct',sus.deposit_account_masked.nunique(),'routing',sus.deposit_routing_number.value_counts().head(5).to_dict(),' src asn',sus.source_asn.value_counts().head(5).to_dict())
print('  status values',a.status.value_counts().to_dict(),' assistance_type',a.assistance_type.value_counts().to_dict())
pay=a[a.amount_usd.notna()]; pay=pay.assign(amt=pay.amount_usd.astype(float)); print('  payments rows',len(pay),'sum',pay.amt.sum(),' first',pay.event_utc.min())
# payments to accounts with unseen-IP deposit change after change
susacc=set(sus.account_id); pp=pay[pay.account_id.isin(susacc)]; first=sus.groupby('account_id').changed_utc.min()
after=pp[pp.event_utc>pp.account_id.map(first)]; print('  paid to taken-over accounts after change: n',len(after),'usd',after.amt.sum(),'window',after.event_utc.min(),after.event_utc.max(),' statuses',after.status.value_counts().to_dict())
# fraudulent bursts
b=app[(app.submitted_utc>='2027-11-13T00:01')&(app.submitted_utc<'2027-11-13T03:18')]; print(' apps 13 Nov 00:01-03:17Z',len(b),' top device/ip reuse:',b.device_id.value_counts().head(3).to_dict(),b.source_ip.value_counts().head(3).to_dict())
print(' columns that could label fraud:',[c for c in a.columns if any(k in c.lower() for k in ['fraud','flag','label','truth','susp','takeover'])])
aw=pd.read_csv(os.path.join(P,'contracts_awards.csv')); print(aw[['piid','awarding_body','supplier_id','supplier_name','award_date','value_usd','procurement_method','offers_received']].sort_values('award_date').to_string())
vr=pd.read_csv(os.path.join(P,'contracts_vendor_registry.csv')); d=vr[vr.duplicated('bank_account_id',keep=False)|vr.duplicated('registered_address',keep=False)]; print(d[['supplier_id','legal_name','registered_address','registration_date','bank_account_id','alternate_bank_account_id']].to_string())
