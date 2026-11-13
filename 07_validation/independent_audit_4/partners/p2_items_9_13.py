# Pass 2 items 9 (mail realism/joins), 10 (one template), 11 (remote sign-on calendar), 12 (ws session regularity), 13 (vendor plan collisions)
import sys,re,collections,ipaddress; sys.path.insert(0,'.')
from common import *
R=reg(); m=load('mail'); m['day']=m.time_utc.str[:10]
print('===== ITEM 9')
for o in R['organisations']:
    k=o['org_id'].lower(); dom=o['domain']; mo=m[m.org==k]
    mb={a['mailbox'] for a in o['accounts'] if a.get('mailbox')}
    internal=mo[mo.direction=='internal']; outb=mo[mo.direction=='outbound']; inb=mo[mo.direction=='inbound']
    s_ok=internal.sender.isin(mb).mean(); r_ok=internal.recipient.isin(mb).mean()
    reached=set(inb.recipient)|set(internal.recipient)
    rep=inb.sender.value_counts()
    # reply pairs: outbound to an address that also sent inbound
    pair=len(set(outb.recipient)&set(inb.sender))
    print(f"{k}: rows {len(mo)} in/int/out {len(inb)}/{len(internal)}/{len(outb)}; internal sender in registry {s_ok:.3f} recipient {r_ok:.3f}; outbound sender in registry {outb.sender.isin(mb).mean():.3f}; mailboxes reached {len(reached&mb)}/{len(mb)}; outside senders seen >=3 times {(rep>=3).sum()}/{len(rep)}; outbound recipients who also wrote in {pair}/{outb.recipient.nunique()}; sender==recipient {(mo.sender==mo.recipient).sum()}")
# seasonal subjects
subj=m.subject.str.replace(r'^(RE|FW): ','',regex=True)
for pat in ['Storm|Hurricane|hurricane|storm','Debris|debris','Holiday|Toy drive','Flu','Open enrollment|enrollment','Boil|boil','Damage|damage','Check-in|check-in|accountability|roll call|recall']:
    x=m[subj.str.contains(pat)]
    print(pat,'->',x.groupby(x.time_utc.str[:7]).size().to_dict())
print('top storm-related subjects:',subj[subj.str.contains('(?i)storm|hurricane|damage|debris|shelter|evacu|generator|fema|aid')].value_counts().head(20).to_dict())
print('\n===== ITEM 10 template sameness')
w=load('web'); f=load('firewall'); e=load('endpoint_alerts'); a=load('auth')
print('browser mix % (user requests):'); print((pd.crosstab(w[w.user_agent_family!='-'].user_agent_family,w[w.user_agent_family!='-'].org,normalize='columns')*100).round(1).to_string())
print('session end reason % (allow):'); print((pd.crosstab(f[f.action=='allow'].session_end_reason,f[f.action=='allow'].org,normalize='columns')*100).round(1).to_string())
days=181
print('deny per day:',(f[f.action=='deny'].groupby('org').size()/days).round(1).to_dict())
print('deny dst_port top share:'); dd=f[f.action=='deny']; print((pd.crosstab(dd.dst_port,dd.org,normalize='columns')*100).round(1).head(12).to_string())
print('endpoint event %:'); print((pd.crosstab(e.event,e.org,normalize='columns')*100).round(1).to_string())
print('mail attach rate:',m.groupby('org').attachment_names.apply(lambda s:round((s!='').mean(),3)).to_dict(),'spam %:',m.groupby('org').verdict.apply(lambda s:round((s=='spam').mean()*100,2)).to_dict())
print('web status %:'); print((pd.crosstab(w.status,w.org,normalize='columns')*100).round(2).to_string())
print('web category top5 per org:'); 
for o in ORGS: print(' ',o,(w[w.org==o].category.value_counts(normalize=True)*100).round(1).head(5).to_dict())
hs=w.groupby('org').host.apply(set)
print('hosts shared: jaccard city vs others',{o:round(len(hs['city']&hs[o])/len(hs['city']|hs[o]),2) for o in ORGS if o!='city'})
print('failed-logon share ws:',a[a.logon_type!='remote'].groupby('org').result.apply(lambda s:round((s=='FAILED').mean()*100,2)).to_dict())
print('failed share remote:',a[a.logon_type=='remote'].groupby('org').result.apply(lambda s:round((s=='FAILED').mean()*100,2)).to_dict(), 'new device share:',a[a.logon_type=='remote'].groupby('org').device.apply(lambda s:round((s=='new device').mean()*100,2)).to_dict())
print('\n===== ITEM 13 vendor plan')
b=[o for o in R['organisations'] if o['org_id']=='BRW'][0]
print(b['sites']); ips=collections.Counter(h['ip'] for h in b['hosts']); print('duplicate ips:',[i for i,c in ips.items() if c>1])
for o in R['organisations']:
    ips=collections.Counter(h['ip'] for h in o['hosts']); nets=[ipaddress.ip_network(s['subnet']) for s in o['sites'] if s.get('subnet')]
    ov=[(str(x),str(y)) for i,x in enumerate(nets) for y in nets[i+1:] if x.overlaps(y)]
    print(o['org_id'],'dup ips',[i for i,c in ips.items() if c>1],'overlapping site subnets',ov,'servers plan',o['address_plan'].get('servers'))
