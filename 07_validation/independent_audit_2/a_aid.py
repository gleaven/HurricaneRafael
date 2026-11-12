from common import *
import collections, re, pickle
rs=load('payments/aid_applications.csv')
pickle.dump(rs,open('/tmp/aid.pkl','wb'))
st=cnt(rs,'status'); print('status values',len(st)); 
for k,v in st.most_common(): 
    if not k.startswith('paid') or v>50: print('  ',v,k)
apps=[r for r in rs if r['record_type']=='application']
ring=[r for r in apps if 'CC-DAM' in r['damage_photo_hashes']]
print('apps with CC-DAM photo names',len(ring), collections.Counter(r['source_asn'] for r in ring), collections.Counter(r['submitted_utc'][:13] for r in ring).most_common(12))
print('other apps from asn 64500',sum(1 for r in apps if r['source_asn']=='64500' and r not in ring))
ringids={r['application_id'] for r in ring}
print('status of records of ring apps',collections.Counter((r['record_type'],r['status']) for r in rs if r['application_id'] in ringids))
held=[r for r in rs if re.search('held|hold|suspicious|review|fraud|flag',r['status'],re.I)]
print('held-like statuses',collections.Counter(r['status'] for r in held).most_common(10))
print('held-like: ring vs non-ring',collections.Counter(r['application_id'] in ringids for r in held))
# submitted before 06:00Z 13 Nov
print('apps before 2027-11-13T06:00Z',sum(1 for r in apps if r['submitted_utc']<'2027-11-13T06:00:00Z'),'min',min(r['submitted_utc'] for r in apps))
print('apps 13Nov-12Dec', sum(1 for r in apps if r['submitted_utc']<'2027-12-13T06:00:00Z'))
# ATO
ch=[r for r in rs if r['record_type']=='account_change']
dd=[r for r in ch if r['field_changed']=='direct deposit']
ato=[r for r in dd if r['source_asn']=='64512']
print('dd changes',len(dd),'from 64512',len(ato),'accounts',len({r['account_id'] for r in ato}),'min/max',min(r['changed_utc'] for r in ato),max(r['changed_utc'] for r in ato))
print('ato seen_before',cnt(ato,'login_ip_seen_before'),'dest',cnt(ato,'deposit_account_masked'), 'routing',cnt(ato,'deposit_routing_number'))
print('non-ato dd: seen_before',cnt([r for r in dd if r not in ato],'login_ip_seen_before'), 'top dest',cnt([r for r in dd if r not in ato],'deposit_account_masked').most_common(5),'routing',cnt([r for r in dd if r not in ato],'deposit_routing_number').most_common(12))
print('asn 64512 all records',collections.Counter((r['record_type'],r['field_changed']) for r in rs if r['source_asn']=='64512'))
rest=[r for r in ch if 'restored' in r['field_changed']]
print('restored',len(rest),'for ato accounts',sum(1 for r in rest if r['account_id'] in {a['account_id'] for a in ato}), cnt(rest,'source_asn').most_common(3), min(r['changed_utc'] for r in rest), max(r['changed_utc'] for r in rest))
print('ATO per day',sorted(collections.Counter(r['changed_utc'][:10] for r in ato).items()))
print('login-changed delta s',sorted((ts(r['changed_utc'])-ts(r['login_utc'])).total_seconds() for r in ato)[::40])
print('nonato login-changed delta s',sorted((ts(r['changed_utc'])-ts(r['login_utc'])).total_seconds() for r in dd if r not in ato and r['login_utc'])[::80])
pickle.dump([(r['account_id'],r['login_utc'],r['changed_utc'],r['source_ip']) for r in ato],open('/tmp/ato.pkl','wb'))
print(ato[0])
