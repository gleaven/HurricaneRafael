# Pass 2: aid portal access log vs payments/aid_applications.csv
import sys,re,collections; sys.path.insert(0,'.')
from common import *
p=portal('aid_portal_access')
d=pd.read_csv(ROOT+'/05_other_sources/payments/aid_applications.csv',dtype=str,keep_default_na=False)
ap=d[d.record_type=='application']; ch=d[d.record_type=='account_change']
print('applications',len(ap),'by channel',ap.channel.value_counts().to_dict())
print('applications D60-D89 (11-13..12-12 UTC):',((ap.submitted_utc>='2027-11-13')&(ap.submitted_utc<'2027-12-13')).sum())
web=ap[ap.channel=='web']
sub=p[p.event=='application_submitted']
print('portal application_submitted',len(sub),'| web applications',len(web))
j=web.merge(sub,left_on='account_id',right_on='account_ref',how='outer',indicator=True)
print(j._merge.value_counts().to_dict())
b=j[j._merge=='both']
print('same time:',(b.submitted_utc==b.time_utc).mean(),' same ip:',(b.source_ip==b.client_ip).mean(),' asn equal:',('ASN '+b.source_asn==b.client_network).mean())
print('asn mismatches sample:'); x=b[('ASN '+b.source_asn)!=b.client_network]; print(pd.crosstab(x.source_asn,x.client_network).to_string())
print('web apps not in portal:',j[j._merge=='left_only'][['account_id','submitted_utc','source_ip','source_asn']].head(8).to_string())
print('portal apps not web apps:',j[j._merge=='right_only'][['account_ref','time_utc','client_ip','client_network']].head(8).to_string())
ro=j[j._merge=='right_only']; print(' right_only: accounts present in applications under another channel:',ro.account_ref.isin(ap.account_id).sum(), ap[ap.account_id.isin(ro.account_ref)].channel.value_counts().to_dict())
# non-web applications: source_ip/asn?
nw=ap[ap.channel!='web']; print('non-web apps with source_ip:',(nw.source_ip!='').sum(), nw[nw.source_ip!=''].source_asn.value_counts().to_dict(), nw[nw.source_ip!=''].source_ip.str.split('.').str[:2].str.join('.').value_counts().head(5).to_dict())
print('non-web accounts that appear in portal log:',nw.account_id.isin(set(p.account_ref)).sum(),'of',len(nw), dict(p[p.account_ref.isin(set(nw.account_id))].event.value_counts()))
# account changes
print('account_change',len(ch),ch.field_changed.value_counts().to_dict())
pu=p[p.event.str.startswith('profile_updated')].copy(); pu['field']=pu.event.str.replace('profile_updated: ','')
k=ch.merge(pu,left_on=['account_id','changed_utc'],right_on=['account_ref','time_utc'],how='outer',indicator=True)
print(k.groupby(['_merge','field_changed'],observed=True).size().to_string()); print(k.groupby(['_merge','field'],observed=True).size().to_string())
kb=k[k._merge=='both']; print('change ip == portal ip:',(kb.source_ip==kb.client_ip).mean(),'asn eq',('ASN '+kb.source_asn==kb.client_network).mean(), 'login_utc matches a portal login_success:',)
ls=set(zip(p[p.event=='login_success'].account_ref,p[p.event=='login_success'].time_utc)); print(' ',np.mean([(a,t) in ls for a,t in zip(kb.account_id,kb.login_utc)]))
# hostile changes
hc=ch[ch.source_asn=='64512']; print('account changes from ASN 64512:',len(hc),hc.field_changed.value_counts().to_dict(),'accounts',hc.account_id.nunique(),'window',hc.changed_utc.min(),hc.changed_utc.max(), 'login_ip_seen_before',hc.login_ip_seen_before.value_counts().to_dict(),'routing',hc.deposit_routing_number.value_counts().to_dict())
print('benign direct-deposit changes: seen_before',ch[(ch.source_asn!='64512')&(ch.field_changed=='direct deposit')].login_ip_seen_before.value_counts().to_dict(),'routing',ch[(ch.source_asn!='64512')&(ch.field_changed=='direct deposit')].deposit_routing_number.value_counts().to_dict())
# the six accounts created from 203.0.113.21/.22
six=p[(p.client_network=='ASN 64512')&(p.event=='account_created')].account_ref
print('six hostile-range accounts in applications:'); print(d[d.account_id.isin(six)][['record_type','account_id','submitted_utc','event_utc','source_ip','source_asn','applicant_name','deposit_routing_number','amount_usd','status']].to_string())
print('applications source_asn 64496:',(ap.source_asn=='64496').sum(), ap[ap.source_asn=='64496'].channel.value_counts().to_dict(), ap[ap.source_asn=='64496'].source_ip.str.split('.').str[:3].str.join('.').value_counts().head(5).to_dict())
print('d.source_asn by record_type:'); print(pd.crosstab(d.source_asn,d.record_type).to_string())
