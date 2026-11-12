from common import *
import collections, sys, glob, csv, random
sys.path.insert(0,ROOT+'/scripts'); import geo
G=geo.Geo()
E=lambda s:int(ts(s).timestamp())
# ADS-B at blast: any aircraft airborne 06:10-09:00Z 10-28 near jetties (27.835,-97.045)
J=(27.835,-97.045); a=E('2027-10-28T06:00:00Z'); b=E('2027-10-28T10:00:00Z'); hits=collections.defaultdict(list)
with open(SRC+'/adsb/adsb_2027-10.csv') as f:
    r=csv.reader(f); h=next(r)
    for row in r:
        t=int(row[3])
        if a<=t<=b and row[8]=='False':
            d=geo.dist_m((float(row[6]),float(row[5])),J)
            if d<8000: hits[row[1].strip()].append((t,round(d)))
print('ADS-B airborne within 8 km of jetties 06:00-10:00Z 10-28:',{k:(dt.datetime.fromtimestamp(v[0][0],dt.timezone.utc).strftime('%H:%M:%S'),len(v),min(x[1] for x in v)) for k,v in hits.items()})
# AVL at blast near Port Aransas
n=0; units=collections.Counter(); first={}
for f in glob.glob(SRC+'/avl/avl_2027-10_*.csv'):
    with open(f) as fh:
        r=csv.DictReader(fh)
        for row in r:
            t=row.get('timestamp_utc') or row.get('time_utc') or list(row.values())[0]
            if '2027-10-28T06:10'<=t<='2027-10-28T08:00':
                la=float(row.get('latitude') or row.get('lat')); lo=float(row.get('longitude') or row.get('lon'))
                if geo.dist_m((la,lo),J)<5000:
                    u=row.get('unit_id'); units[u]+=1; first.setdefault(u,t)
print('AVL units within 5 km of jetties 06:10-08:00Z',dict(units),first)
# AVL GPS noise in jam window vs before
def sample(day):
    out=[]
    for f in glob.glob(SRC+'/avl/avl_2027-10_CC*.csv'):
        with open(f) as fh:
            r=csv.DictReader(fh)
            for row in r:
                t=row.get('timestamp_utc') or list(row.values())[0]
                if t.startswith(day) and random.random()<0.05:
                    out.append(G.roads.nearest(float(row['latitude']),float(row['longitude']))[0])
    out.sort(); return (len(out), round(out[len(out)//2],1) if out else None, round(out[int(len(out)*.99)],1) if out else None)
random.seed(3)
print('AVL road-distance (n, median, p99) 10-15:',sample('2027-10-15'),' 10-24 (jam):',sample('2027-10-24'))
# ED visits at blast: SRMC injuries 10-28 with blast text
import re
for f in glob.glob(SRC+'/public_health/ed_visits_*.csv'):
    with open(f) as fh:
        r=csv.DictReader(fh)
        for row in r:
            s=' '.join(row.values())
            if '2027-10-28' in s and re.search(r'blast|explos|tug|deckhand|vessel',s,re.I): print('ED',os.path.basename(f),{k:v for k,v in row.items() if v}.__repr__()[:500]); 
# camera events at blast
ce=load('port_surveillance/camera_events.csv'); print(list(ce[0].keys()))
tk=[k for k in ce[0] if 'time' in k.lower()][0]
x=[r for r in ce if '2027-10-28T05:50'<=r[tk]<='2027-10-28T07:00']; print('camera events 05:50-07:00Z',len(x)); [print('  ',{k:v[:90] for k,v in r.items() if v}) for r in x[:6]]
# financial transactions: diversion
ft=load('payments/financial_transactions.csv')
mule=[r for r in ft if r['counterparty_account_masked'] in('****1073','****5333','****3176') or 'FEMA' in r['counterparty_name'].upper() or 'DISASTER' in r['description'].upper()]
print('fin tx candidates',len(mule),collections.Counter((r['account_id'],r['direction'],r['channel'],r['description'][:40]) for r in mule).most_common(8))
aid=[r for r in ft if 'aid' in r['description'].lower() or 'assistance' in r['description'].lower()]
print('aid-like tx',len(aid),'span',min(r['timestamp'] for r in aid) if aid else None,max(r['timestamp'] for r in aid) if aid else None,'sum',round(sum(float(r['amount_usd']) for r in aid)),collections.Counter(r['account_id'] for r in aid).most_common(5))
pp=[r for r in ft if 'prepaid' in (r['description']+r['counterparty_name']).lower()]
print('prepaid tx',len(pp),min(r['timestamp'] for r in pp) if pp else None,max(r['timestamp'] for r in pp) if pp else None,round(sum(float(r['amount_usd']) for r in pp)),collections.Counter(r['account_id'] for r in pp).most_common(5))
