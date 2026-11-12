from common import *
import collections
inv=load('payments/contracts_invoices.csv'); aw={r['piid']:r for r in rows('payments/contracts_awards.csv')}
for v in ('VND-0001','VND-0002'):
    x=[r for r in inv if r['supplier_id']==v]
    print(v,len(x),'first',min(r['invoice_date'] for r in x),'last',max(r['invoice_date'] for r in x),'total',round(sum(float(r['amount_usd']) for r in x)),'status',cnt(x,'status'),'remit',cnt(x,'remit_bank_account_id'),'units',cnt(x,'unit'))
    print('   by remit first date',{a:min(r['invoice_date'] for r in x if r['remit_bank_account_id']==a) for a in {r['remit_bank_account_id'] for r in x}})
    print('   sample',x[0])
    if v=='VND-0001':
        tons=sum(float(r['quantity']) for r in x if 'ton' in r['unit']); print('   billed tons',round(tons))
        dm=load('payments/contracts_debris_monitoring.csv'); st=sum(float(r['estimated_tons_removed']) for r in dm); print('   surveyed tons',round(st),'ratio',round(tons/st,2),'survey dates',min(r['survey_date'] for r in dm),max(r['survey_date'] for r in dm), 'zones',len({r['zone_id'] for r in dm}))
        # ratio per period: constant?
        bp=collections.defaultdict(float); sp=collections.defaultdict(float)
        for r in x:
            if 'ton' in r['unit']: bp[(r['period_start'],r['work_area_id'])]+=float(r['quantity'])
        for r in dm: sp[(r['period_start'],r['area_id'])]+=float(r['estimated_tons_removed'])
        rat=sorted(round(bp[k]/sp[k],2) for k in bp if k in sp and sp[k]>0); print('   per zone-week ratio n',len(rat),'min',rat[0] if rat else None,'median',rat[len(rat)//2] if rat else None,'max',rat[-1] if rat else None, 'unmatched periods',sum(1 for k in bp if k not in sp))
# over-contract value
tot=collections.defaultdict(float)
for r in inv:
    if r['piid']: tot[r['piid']]+=float(r['amount_usd'])
over=[(p,round(t),aw[p]['value_usd']) for p,t in tot.items() if p in aw and t>float(aw[p]['value_usd'])*1.0]
print('awards exceeded by invoices',over[:8])
print('invoice piids not in awards',len({r['piid'] for r in inv if r['piid'] and r['piid'] not in aw}))
bad=sum(1 for r in inv if r['paid_date'] and r['paid_date']<r['invoice_date']) ; print('paid before invoice',bad,'approved before invoice',sum(1 for r in inv if r['approved_date'] and r['approved_date']<r['invoice_date']))
print('invoice before award',[(r['invoice_id'],r['invoice_date'],aw[r['piid']]['award_date']) for r in inv if r['piid'] in aw and r['invoice_date']<aw[r['piid']]['award_date']][:5])
print('status values',cnt(inv,'status'))
print('awards: method',cnt(list(aw.values()),'procurement_method'),'sole source rows',[(r['piid'],r['supplier_id'],r['value_usd']) for r in aw.values() if 'sole' in r['procurement_method']])
vr=load('payments/contracts_vendor_registry.csv')
print('shared bank accounts',[(a,c) for a,c in cnt(vr,'bank_account_id').items() if c>1],'shared addresses',[(a,c) for a,c in cnt(vr,'registered_address').items() if c>1],'alt account nonempty',[(r['supplier_id'],r['alternate_bank_account_id']) for r in vr if r['alternate_bank_account_id']], 'reg dates 2027',[(r['supplier_id'],r['registration_date']) for r in vr if r['registration_date']>='2027'])
