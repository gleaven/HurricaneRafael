import sys,re,collections; sys.path.insert(0,'.')
from common import *
f=load('firewall'); a=load('auth')
lo=f[f.src_ip.str.match(r'^203\.0\.113\.\d{1,2}$')]
x=lo[lo.org=='nascc']; print('nascc low-range rows by rule and month:'); print(pd.crosstab(x.rule_name,x.time_utc.str[:7]).to_string())
x=lo[lo.org=='brw']; print(x[['time_utc','device','rule_name','src_ip','dst_ip','app','duration_s']].to_string())
x=lo[lo.org=='city']; print(x[['time_utc','rule_name','src_ip','duration_s']].to_string())
for n in ['aid_portal_access','base_logistics_access']:
    p=portal(n); doc=p[p.client_ip.str.match(r'^(203\.0\.113|198\.51\.100|192\.0\.2)\.')&(p.client_network!='ASN 64512')&(p.client_ip!='198.51.100.44')]
    g=doc.groupby('client_ip').client_network.nunique(); print(n,'background documentation-range addresses',len(g),'label count distribution',g.value_counts().to_dict(),'rows',len(doc))
    print('  addresses:',sorted(g.index,key=lambda s:[int(q) for q in s.split('.')]))
    h=p[p.client_network=='ASN 64512']; print('  ASN 64512 rows',len(h),'UA',h.user_agent_family.value_counts().to_dict(),'events',h.event.value_counts().to_dict())
    print('  hostile-only values: status 404 rows',(p.status=='404').sum(),'of which ASN 64512',((p.status=='404')&(p.client_network=='ASN 64512')).sum())
    for pth in ['/admin','/owa','/login.aspx','/api/v1/session','/.well-known/security.txt','/account/recover','/help/contact','/status']:
        print('   ',pth,'rows',(p.path==pth).sum(),'from ASN 64512',((p.path==pth)&(p.client_network=='ASN 64512')).sum())
t=ts(a); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); a['lh']=(t-pd.to_timedelta(off,unit='h')).dt.hour
x=a[(a.event_id=='4624')&(a.logon_type=='2')]
print(pd.crosstab(x.lh,x.org).loc[[4,16,19]].to_string())
