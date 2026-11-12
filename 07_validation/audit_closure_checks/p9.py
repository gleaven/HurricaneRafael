import csv,glob,json,re,collections,os,sys,math,statistics
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
# D2-11: AIS scatter of a moored ship inside/outside the interference window
h=open(O+'ais/ais_2027-10.csv',encoding='utf-8').readline().strip().split(','); print('AIS header',h)
pos=collections.defaultdict(list)
with open(O+'ais/ais_2027-10.csv',encoding='utf-8') as f:
    for r in csv.DictReader(f):
        nm=r.get('VesselName') or r.get('vessel_name') or ''
        if 'KALVORA' in nm.upper():
            t=r.get('BaseDateTime') or r.get('timestamp_utc') or r.get('time_utc'); pos[t[:10]].append((float(r.get('LAT') or r.get('latitude')),float(r.get('LON') or r.get('longitude')),float(r.get('SOG') or r.get('sog') or 0)))
def scat(L):
    L=[p for p in L if p[2]<0.3]
    if len(L)<5: return None
    la=statistics.mean(p[0] for p in L); lo=statistics.mean(p[1] for p in L)
    return round(statistics.median(math.hypot((p[0]-la)*111000,(p[1]-lo)*111000*math.cos(math.radians(la))) for p in L),1)
print('D2-11 KALVORA STAR moored scatter (median m) by day',[(d[5:],scat(L)) for d,L in sorted(pos.items()) if '2027-10-18'<=d<='2027-10-30'])
# ADS-B NIC by day
nic=collections.defaultdict(list)
with open(O+'adsb/adsb_2027-10.csv',encoding='utf-8') as f:
    for i,r in enumerate(csv.DictReader(f)):
        if i%7==0 and r['nic']:
            d=__import__('datetime').datetime.utcfromtimestamp(int(r['time_position'])).strftime('%m-%d'); nic[d].append(int(float(r['nic'])))
print('  ADS-B mean NIC by day',[(d,round(statistics.mean(v),2)) for d,v in sorted(nic.items()) if '10-19'<=d<='10-30'])
# drone telemetry: missing frames
import itertools
fl={r['flight_id']:r for r in rows(O+'drone_video/logs/flight_log.csv')}
h=open(O+'drone_video/drone_telemetry_2027-10.csv',encoding='utf-8').readline().strip().split(','); print('drone telemetry header',h)
