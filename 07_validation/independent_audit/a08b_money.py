import pandas as pd, numpy as np, os, json
from common import *
P=os.path.join(SRC,'payments')
a=pd.read_csv(os.path.join(P,'aid_applications.csv'),dtype=str)
ch=a[a.record_type=='account_change']
t=ch[(ch.source_asn=='64512')]
print('ASN 64512 account_change rows',len(t),'accounts',t.account_id.nunique(),'fields',t.field_changed.value_counts().to_dict(),'window',t.changed_utc.min(),t.changed_utc.max())
print(' per day',t.changed_utc.str[:10].value_counts().sort_index().to_dict(),' login_ip_seen_before',t.login_ip_seen_before.value_counts().to_dict(),' distinct new accounts',t.deposit_account_masked.nunique(),' routing',t.deposit_routing_number.value_counts().to_dict())
print(' any other rows from ASN 64512:',a[(a.source_asn=='64512')].record_type.value_counts().to_dict())
r=ch[ch.field_changed.str.contains('restored')]; print(' restored rows',len(r),'window',r.changed_utc.min(),r.changed_utc.max(),' same accounts as ASN64512 set:',set(r.account_id)==set(t.account_id))
dis=a[a.record_type=='disbursement'].assign(amt=lambda x:x.amount_usd.astype(float))
first=t.groupby('account_id').changed_utc.min(); rest=r.groupby('account_id').changed_utc.min()
d=dis[dis.account_id.isin(first.index)]; div=d[(d.event_utc>d.account_id.map(first))&(d.event_utc<d.account_id.map(rest))&(d.status=='paid')]
print(' disbursements between takeover and restore: n',len(div),'usd',round(div.amt.sum()),'window',div.event_utc.min(),div.event_utc.max(),' reissued usd',round(d[d.status=='reissued'].amt.sum()))
app=a[a.record_type=='application']
print(' apps before local midnight 13 Nov (06:00Z):',(app.submitted_utc<'2027-11-13T06:00:00Z').sum())
h=a[a.status.str.contains('suspicious',na=False)]; print(' flagged rows',len(h),h.record_type.value_counts().to_dict(),' event window',h.event_utc.min(),h.event_utc.max()); 
ha=app[app.application_id.isin(h.application_id)]; print('  their submission times by hour:',ha.submitted_utc.str[:13].value_counts().sort_index().to_dict(),' ips',ha.source_ip.value_counts().head(4).to_dict())
ic=pd.read_csv(os.path.join(P,'insurance_claims.csv'),dtype=str); print('insurance record types',ic.record_type.value_counts().to_dict())
cl=ic[ic.record_type=='claim']; print(' claims',len(cl),'programs',cl.claim_program.value_counts().to_dict(),' loss_date min/max',cl.loss_date.min(),cl.loss_date.max(),' loss before 2027-09-14:',(cl.loss_date<'2027-09-14').sum(),' on 09-13:',(cl.loss_date=='2027-09-13').sum())
print(' filed<loss',(cl.filed_date<cl.loss_date).sum(),' filed min',cl.filed_date.min(),' paid<filed',((cl.paid_date<cl.filed_date)&cl.paid_date.notna()).sum(),' loss causes',cl.loss_cause.value_counts().to_dict())
print(' filed per day first 10:',cl.filed_date.value_counts().sort_index().head(10).to_dict(),' status',cl.status.value_counts().to_dict())
print(cl[cl.loss_date<'2027-09-14'][['claim_id','claim_program','loss_date','loss_cause','filed_date','claimed_usd']].head(8).to_string())
sp=cl[cl.loss_cause.str.contains('oil|spill',case=False,na=False)]; print(' spill claims',len(sp),sp.filed_date.min(),sp.filed_date.max())
print(' label-like columns:',[c for c in ic.columns if any(k in c.lower() for k in ['fraud','flag','ring','susp'])],' status vals w/ fraud:',[s for s in cl.status.unique() if 'fraud' in str(s).lower() or 'siu' in str(s).lower()])
inv=pd.read_csv(os.path.join(P,'contracts_invoices.csv')); v=inv[inv.supplier_id=='VND-0001']; print('Vantorra invoices',len(v),'sum',v.amount_usd.sum(),v.invoice_date.min(),v.invoice_date.max(),'tons billed',v[v.unit.str.contains('ton',na=False)].quantity.sum(),' status',v.status.value_counts().to_dict(),' hold',v.hold_date.dropna().unique()[:3])
dm=pd.read_csv(os.path.join(P,'contracts_debris_monitoring.csv')); s=dm[dm.supplier_id=='VND-0001'].groupby(['zone_id','period_start']).estimated_tons_removed.mean().sum(); print(' survey tons (mean of methods) Vantorra',round(s),' ratio billed/survey',round(v[v.unit.str.contains('ton',na=False)].quantity.sum()/s,2))
q=inv[inv.supplier_id=='VND-0002']; print('Quellmar invoices',len(q),q.invoice_date.min(),q.invoice_date.max(),q.amount_usd.sum(),q.buyer.unique())
er=json.load(open(os.path.join(REG,'entity_registry.json'))); print(list(er.keys())[:8])
txt=json.dumps(er); import re
for name in ['Vantorra','Quellmar','Brightwake','Brannoch']:
    for m in re.finditer(name,txt): print(name, txt[max(0,m.start()-150):m.start()+60].replace('\n',' ')); break
