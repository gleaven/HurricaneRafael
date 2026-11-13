#!/usr/bin/env python3
"""Pass 1 extra tricks: SIEM detail shapes, endpoint file_create size ranking, dns.log attributes for rare names, mail attachment shape, alarm-point id order, hostile seconds."""
import sys,collections,pickle,json,re,csv,glob; sys.path.insert(0,sys.path[0])
from lib import *
C,rm=pickle.load(open(sys.path[0]+'/cache_siem.pkl','rb'))
ds=C['detail_shape']; print('SIEM detail shapes',len(ds),'rare (<=3):',[(k,v) for k,v in ds.items() if v<=3][:12])
fc=[]
for f in sorted(glob.glob('endpoint/endpoint_*.jsonl')):
    for line in open(f):
        if '"file_create"' in line:
            d=json.loads(line); fc.append((d['size'],d['time_utc'],d['host'],d['path'][-50:],d['image'].split('\\')[-1]))
fc.sort(reverse=True); print('file_create events',len(fc),'top 12 by size:'); [print('   ',x) for x in fc[:12]]
print('  ext counts',collections.Counter(x[3].rsplit('.',1)[-1].lower() for x in fc).most_common(14))
dns=zeek('dns')
c2=[r for r in dns if 'vantagesec-telemetry' in r[8] or 'meridiancontrols.net' in r[8]]
print('C2 dns rows',len(c2),collections.Counter((r[2],r[4],r[10],r[11],r[12],r[13],r[14],r[15],r[16]) for r in c2).most_common(4))
print('  dns qtype',collections.Counter(r[10] for r in dns).most_common(6),'rcode',collections.Counter(r[11] for r in dns).most_common(5),'TTL distinct',len({r[16] for r in dns}),'AA/RD/RA',collections.Counter((r[12],r[13],r[14]) for r in dns).most_common(4))
ttl=collections.Counter(r[16] for r in dns); print('  ttl of C2 answers overall frequency',[(r[16],ttl[r[16]]) for r in c2[:5]])
nx=[r for r in dns if r[11]=='NXDOMAIN']; print('  NXDOMAIN rows',len(nx),'answers field',collections.Counter(r[15] for r in nx).most_common(2))
multi=sum(1 for r in dns if ',' in r[15]); print('  multi-answer rows',multi,'CNAME answers',sum(1 for r in dns if re.search('[a-z]',r[15]) and r[15] not in('-','(empty)')))
tld=collections.Counter(r[8].rsplit('.',1)[-1] for r in dns); print('  TLDs',tld.most_common(14))
print('  internal names queried',sum(1 for r in dns if r[8].endswith('cbpwa.example')),'PTR',sum(1 for r in dns if r[10]=='PTR'))
M=audit('mail_gateway_cbpwa')
odd=[m for m in M if m['attachment_names'] and not re.match(r'^[a-z]+_\d+\.[a-z0-9]+$',m['attachment_names'])]
print('MAIL attachments',sum(1 for m in M if m['attachment_names']),'not matching ^[a-z]+_\\d+\\.ext$:',len(odd),[(m['time_utc'],m['recipient'],m['attachment_names']) for m in odd])
sa=audit('alarm_suppression_audit'); adds=[a for a in sa if a['action']=='ADD']
nums=[int(re.search(r'ALM-(\d+)',a['alarm_point']).group(1)) for a in adds]
print('ALARM ADD rows',len(adds),'alarm ids strictly increasing with time:',all(b>a for a,b in zip(nums,nums[1:])),'first/last',nums[0],nums[-1])
print('  alarm_point label shapes',collections.Counter(re.sub(r'ALM-\d+ ','',a['alarm_point']) for a in sa).most_common(12))
print('  VELA batch seconds',collections.Counter(a['time_utc'][17:19] for a in sa if a['changed_by']=='GW-ENG-VELA'),'| other ADD seconds==07:',sum(1 for a in adds if a['changed_by']!='GW-ENG-VELA' and a['time_utc'][17:19]=='07'),'of',sum(1 for a in adds if a['changed_by']!='GW-ENG-VELA'))
print('  rows per second max: VELA',max(collections.Counter(a['time_utc'] for a in sa if a['changed_by']=='GW-ENG-VELA').values()),'others',max(collections.Counter(a['time_utc'] for a in sa if a['changed_by'] not in('GW-ENG-VELA','GW-ENG-RUIZ')).values()))
fi=audit('file_integrity'); hx=collections.Counter(len(set(a['new_hash'][7:])) for a in fi)
print('FIM hostile hashes',[(a['previous_hash'],a['new_hash']) for a in fi if 'draft' in a['path']],'MODIFIED rows whose previous_hash equals an earlier new_hash for the path: n/a (each path once)')
oc=audit('ot_config_changes'); print('ot_config seconds==00',[(r['time_utc'],r['session_user'],r['change_ticket']) for r in oc if r['time_utc'][17:19]=='00'])
