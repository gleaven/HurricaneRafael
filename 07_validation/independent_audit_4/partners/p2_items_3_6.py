# Pass 2: items 3 (lure separable), 5 (extract seams), 6 (clickers received lure), containment of extracts
import sys,re,collections; sys.path.insert(0,'.')
from common import *
AUD=ROOT+'/05_other_sources/network_logs/audit/'
m=load('mail'); m['day']=m.time_utc.str[:10]
print('===== ITEM 3')
tail=m.message_id.str.extract(r'@([^>]*)>')[0]
print('message-id right-hand side equals sender_domain:', (tail==m.sender_domain).mean().round(4))
m['rhs_kind']=np.where(tail==m.sender_domain,'=domain',np.where(tail.str.contains(r'\.'),'other fqdn','short'))
print(pd.crosstab(m.rhs_kind,m.org).to_string())
lure=m.sender_domain=='aid-help-portal.example'
print('lure rows',lure.sum(), m[lure].groupby('org').size().to_dict(), 'window',m[lure].time_utc.min(),m[lure].time_utc.max())
L=m[lure]
print('lure: distinct senders',L.sender.nunique(),'subjects',L.subject.nunique(),'verdict',L.verdict.value_counts().to_dict(),'attach',(L.attachment_names!='').sum(),'size range',L.size_bytes.astype(int).min(),L.size_bytes.astype(int).max())
print('lure sender local parts sample',L.sender.str.split('@').str[0].value_counts().head(8).to_dict())
# feature comparison with benign bulk
def shape(x):
    l=x.strip('<>').split('@')[0]; return re.sub(r'[0-9a-f]','h',l)[:40]
print('lure msgid shapes',L.message_id.map(shape).value_counts().head(3).to_dict())
inb=m[m.direction=='inbound']
g=inb.groupby(['org','sender_domain']).agg(n=('day','size'),senders=('sender','nunique'),subj=('subject','nunique'),rcp=('recipient','nunique'),days=('day','nunique'))
print('inbound domains with >=100 msgs:'); print(g[g.n>=100].sort_values('n',ascending=False).head(25).to_string())
print('domains with n>=50 and senders>=20 and subj==1:'); print(g[(g.n>=50)&(g.senders>=20)&(g.subj==1)].to_string())
print('bulk counts (>=100, subj==1) multiples of 10:', [(i,int(n)) for i,n in g[(g.n>=100)&(g.subj==1)].n.items()])
# recipients per lure: duplicates
print('lure recipients',L.recipient.nunique(),'max per recipient',L.recipient.value_counts().max(), L.recipient.value_counts().value_counts().to_dict())
# sender-domain concentration
for o in ORGS:
    x=inb[inb.org==o]; vc=x.sender_domain.value_counts()
    print(o,'inbound',len(x),'domains',len(vc),'top5',vc.head(5).to_dict(),'single-use share',round((vc==1).mean(),2))
# subjects
s=m[~lure].subject.str.replace(r'^(RE|FW): ','',regex=True).str.replace(r'\d+','N',regex=True)
print('distinct subject templates',s.nunique()); print(s.value_counts().head(15).to_string())
# vendor lure
v=m[m.sender_domain.str.contains('marine-certification')]; print(v.drop(columns=['_file']).to_string())
bi=inb[inb.org=='brw']; print('brw inbound domains',bi.sender_domain.nunique(), 'domains seen once',(bi.sender_domain.value_counts()==1).sum())
print('brw domains containing notices/portal/cert:', [d for d in bi.sender_domain.unique() if re.search('notice|portal|certif',d)])
print('\n===== ITEM 5: extract seams + containment')
ex=pd.read_csv(AUD+'account_logons_city_airstation.csv',dtype=str,keep_default_na=False)
a=load('auth',['city','nascc']); r=a[a.logon_type=='remote'].copy(); r['day']=r.time_utc.str[:10]
svc={'CC-SSO-01':'city single sign-on','NASCC-OWA-01':'base webmail'}
r['service']=r.host.map(svc)
k=['time_utc','service','account','src_ip','src_network','result','auth_method','device']
mm=ex.merge(r[k].drop_duplicates(),on=k,how='left',indicator=True)
print('account_logons rows',len(ex),'found in partner auth',(mm._merge=='both').sum(), 'window',ex.time_utc.min(),ex.time_utc.max())
inwin=r[(r.time_utc>=ex.time_utc.min())&(r.time_utc<=ex.time_utc.max())]
print('partner auth remote rows in the same window:',len(inwin),'(extract complete for window:',len(inwin)==len(ex),')')
r['inwin']=(r.time_utc>='2027-09-12')&(r.time_utc<'2027-09-22')
print('label mix inside vs outside window (%)'); print((pd.crosstab(r.src_network,r.inwin,normalize='columns')*100).round(1).to_string())
print((pd.crosstab(r.auth_method,[r.org,r.inwin],normalize='columns')*100).round(1).to_string())
print((pd.crosstab(r.device,[r.org,r.inwin],normalize='columns')*100).round(1).to_string())
print((pd.crosstab(r.result,[r.org,r.inwin],normalize='columns')*100).round(1).to_string())
for nm,o in [('mail_gateway_city','city'),('mail_gateway_airstation','nascc'),('mail_gateway_brightwake','brw')]:
    e=pd.read_csv(AUD+nm+'.csv',dtype=str,keep_default_na=False); mo=m[m.org==o]
    cols=list(e.columns)
    j=e.merge(mo[cols].drop_duplicates(),on=cols,how='left',indicator=True)
    w=mo[(mo.time_utc>=e.time_utc.min())&(mo.time_utc<=e.time_utc.max())]
    print(nm,'rows',len(e),'in partner',(j._merge=='both').sum(),'window',e.time_utc.min(),e.time_utc.max(),'partner rows in window',len(w))
    mo=mo.assign(inwin=(mo.time_utc>=e.time_utc.min())&(mo.time_utc<=e.time_utc.max()))
    print('  verdict % in/out:',(pd.crosstab(mo.verdict,mo.inwin,normalize='columns')*100).round(2).to_dict())
    print('  direction % in/out:',(pd.crosstab(mo.direction,mo.inwin,normalize='columns')*100).round(1).to_dict())
    print('  attach rate in/out:',mo.groupby('inwin').attachment_names.apply(lambda s:(s!='').mean().round(3)).to_dict())
print('\n===== ITEM 6: clickers and lures')
cl=pd.read_csv(AUD+'mail_url_clicks_city_airstation.csv',dtype=str)
for _,c in cl.iterrows():
    x=L[L.recipient==c.mailbox]
    print(c.mailbox,c.time_utc,'lures received',len(x),'first',x.time_utc.min() if len(x) else None,'before click',(x.time_utc<c.time_utc).sum())
clb=pd.read_csv(AUD+'mail_url_clicks_brightwake.csv',dtype=str); print(clb.to_string())
w=load('web'); d=load('dns'); f=load('firewall')
cw=w[w.host.isin(['aid-help-portal.example','certificates.marine-certification-notices.example'])]
print('click web rows',len(cw))
for _,c in cw.iterrows():
    dd=d[(d.org==c.org)&(d.client_ip==c.client_ip)&(d['query']==c.host)&(d.time_utc<=c.time_utc)]
    ans=dd.answer.iloc[-1] if len(dd) else None
    ff=f[(f.org==c.org)&(f.src_ip==c.client_ip)&(f.dst_ip==ans)]
    print(c.org,c.time_utc,c.client_ip,c.user,'dns',len(dd),ans,'fw sessions to answer',len(ff), ff.time_utc.tolist()[:2], ff.nat_src_ip.tolist()[:2])
