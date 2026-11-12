from common import *
import collections,re
rs=load('payments/insurance_claims.csv')
cl=[r for r in rs if r['record_type']=='claim']
ring=lambda r:r['holder_id']=='PH-100001'
print('SIU',collections.Counter(ring(r) for r in cl if 'special investigations' in r['status']),'payment stopped',collections.Counter(ring(r) for r in cl if r['status']=='payment stopped'))
print('ring claim statuses',collections.Counter(r['status'] for r in cl if ring(r)))
print('NAR-7F3A',collections.Counter(ring(r) for r in cl if r['damage_narrative_id']=='NAR-7F3A'), 'narr ids repeated', [ (k,v) for k,v in cnt(cl,'damage_narrative_id').most_common(4)])
print('APR-001/RM',collections.Counter((r['appraiser_id'],r['appraiser_initials'],r['appraisal_priority'],ring(r)) for r in rs if r['appraiser_id']).most_common(8))
print('AOB Y',collections.Counter(ring(r) for r in cl if r['assignment_of_benefits']=='Y'))
print('VND-0003/4',collections.Counter((r['contractor_estimate_supplier_id'],ring(r)) for r in cl if r['contractor_estimate_supplier_id'] in('VND-0003','VND-0004')))
print('txn type',collections.Counter((r['transaction_type'],ring(r)) for r in rs if r['transaction_type']))
print('new_rcv 250000',collections.Counter(ring(r) for r in rs if r['new_rcv_usd']=='250000'))
ap=load('payments/aid_applications.csv')
r94=[r for r in ap if 'CC-DAM' in r['damage_photo_hashes']]
print('ring unit pattern',sum(bool(re.search(r'Unit [A-Z]\d',r['damaged_address'])) for r in r94),'non-ring',sum(bool(re.search(r'Unit [A-Z]\d',r['damaged_address'])) for r in ap if r['record_type']=='application' and 'CC-DAM' not in r['damage_photo_hashes']))
print(collections.Counter(r['device_id'] for r in r94).most_common(5), collections.Counter(r['source_ip'] for r in r94).most_common(5),collections.Counter(r['tract'] for r in r94).most_common(5))
print('ring names', collections.Counter(r['applicant_name'] for r in r94).most_common(5))
print('non-ring 198.51.100.44',sum(1 for r in ap if r['source_ip']=='198.51.100.44' and r not in r94))
print('ring determinations',[ (r['status'],r['event_utc']) for r in ap if r['application_id']==r94[0]['application_id']])
