from common import *
import collections
reg={r['facility_id']:r for r in rows('shelters/shelter_registry.csv')}
cen=load('shelters/shelter_daily_census.csv')
days=sorted({r['date_local'] for r in cen}); print('census span',days[0],days[-1],len(days))
print('status',cnt(cen,'status'))
tot=collections.Counter(); 
for r in cen: tot[r['date_local']]+=int(r['occupancy'])
print('total occupancy by day',[(d[5:],tot[d]) for d in days])
for fid,R in reg.items():
    rs=[r for r in cen if r['facility_id']==fid]
    occ=[(r['date_local'][5:],int(r['occupancy']),int(r['new_arrivals'])) for r in rs]
    pk=max(rs,key=lambda r:int(r['occupancy']))
    print(fid,R['facility_name'],'cap',R['capacity'],'open',R['opened_local'],'close',R['closed_local'],'census',rs[0]['date_local'],rs[-1]['date_local'],'peak',pk['occupancy'],pk['date_local'],'over cap days',sum(int(r['occupancy'])>int(r['capacity']) for r in rs))
    print('   ',occ[:12],'...',occ[-4:])
    # before open/after close
    o=R['opened_local'][:10]; c=R['closed_local'][:10]
    print('    rows before open',sum(r['date_local']<o for r in rs),'after close',sum(r['date_local']>c for r in rs), 'occupancy on last day',rs[-1]['occupancy'], 'arrival consistency violations (occ_t > occ_{t-1}+arr_t)',sum(1 for a,b in zip(rs,rs[1:]) if int(b['occupancy'])>int(a['occupancy'])+int(b['new_arrivals'])))
# SAR deliveries vs shelters
m=load('sar/sar_missions.csv')
for fid in ('FAC-SHLT-027','FAC-SHLT-026','FAC-SHLT-029','FAC-SHLT-006'):
    d=[r for r in m if r['delivered_to']==fid]
    byd=collections.Counter(local(ts(r['recovery_utc'])).strftime('%m-%d') for r in d)
    early=sum(1 for r in d if local(ts(r['recovery_utc'])).strftime('%Y-%m-%d %H:%M')<reg[fid]['opened_local'])
    print(fid,'SAR deliveries',len(d),sorted(byd.items()),'before shelter opened',early)
    print('    census arrivals same days',[(r['date_local'][5:],r['new_arrivals'],r['occupancy']) for r in cen if r['facility_id']==fid and '2027-09-14'<=r['date_local']<='2027-09-19'])
bus=load('shelters/evacuation_bus_trips.csv')
print('bus trips',len(bus),'by day',sorted(collections.Counter(r['pickup_local'][:10] for r in bus).items()),'facilities',cnt(bus,'facility_id'))
print('bus arrivals before shelter open',sum(1 for r in bus if r['arrival_local'][:16]<reg[r['facility_id']]['opened_local']),'last pickup',max(r['pickup_local'] for r in bus))
c211=load('shelters/shelter_211_calls.csv')
print('211 by day',sorted(collections.Counter(r['date_local'] for r in c211).items())[:12],'...', 'topics',cnt(c211,'topic').most_common(8))
z=[r for r in c211 if r['caller_evacuation_zone']=='D' and '2027-09-13 14:00'<=r['call_time_local']<='2027-09-13 20:00']
print('Zone D calls 14-20 local D-1:',len(z), cnt(z,'topic'), z[0] if z else None)
print('notes',cnt(c211,'note').most_common(6))
print('referred facilities',cnt(c211,'referred_facility_id'))
print('Zavala' , sum('Zavala' in json.dumps(r) for r in c211), sum('Zavala' in json.dumps(r) for r in cen))
print('ES pct range',min(int(r['spanish_speaking_pct']) for r in cen),max(int(r['spanish_speaking_pct']) for r in cen),'bilingual staff 0 days',sum(r['bilingual_staff_on_duty']=='0' for r in cen))
