"""Area 9: ids used in streams exist in registries; one id per thing; leftovers."""
import pandas as pd, numpy as np, os, glob, json, re, csv, collections
from common import *
def J(n): return json.load(open(os.path.join(REG,n)))
def allvals(o,keypat):
    out=set()
    def w(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if re.search(keypat,k) and isinstance(v,(str,int)): out.add(str(v))
                w(v)
        elif isinstance(x,list):
            for i in x: w(i)
    w(o); return out
def allstr(o):
    out=set()
    def w(x):
        if isinstance(x,dict):
            for k,v in x.items(): out.add(str(k)); w(v)
        elif isinstance(x,list):
            for i in x: w(i)
        elif isinstance(x,str): out.add(x)
    w(o); return out
ves=J('vessels.json')['vessels']; mmsi={str(v['mmsi']) for v in ves if v.get('mmsi')}; vname={str(v['mmsi']):v['vessel_name'] for v in ves if v.get('mmsi')}
fac=allstr(J('facility_registry.json')); hosts=allstr(J('gw_host_registry.json')); sens=allstr(J('sensor_registry.json')); areas=allstr(J('areas.json')); tags=allstr(J('scada_tags.json')); infra=allstr(J('infrastructure_assets.json')); ent=allstr(J('entity_registry.json')); term=allstr(J('terminal_registry.json')); units=allstr(J('cad_units.json')); orgs=allstr(J('organizations.json')); drone=allstr(J('drone_operators.json')); acr=allstr(J('aircraft_registry.json')); pers=allstr(J('personas.json'))
def col(path,c,split=None,nrows=None):
    s=set()
    for f in sorted(glob.glob(os.path.join(SRC,path))):
        d=pd.read_csv(f,usecols=[c],dtype=str,nrows=nrows)[c].dropna()
        if split: d=d.str.split(split).explode().str.strip()
        s|=set(d[d!=''])
    return s
def rep(label,vals,reg):
    miss=sorted(v for v in vals if v not in reg)
    print(f"{label:55s} distinct {len(vals):6d}  not in registry {len(miss):5d}  {miss[:8]}")
rep('ais MMSI',col('ais/ais_*.csv','MMSI')|col('ais/satellite/*.csv','MMSI'),mmsi)
rep('radar correlated_mmsi',col('port_surveillance/radar_tracks_*.csv','correlated_mmsi'),mmsi)
rep('camera_events mmsi',col('port_surveillance/camera_events.csv','mmsi'),mmsi)
rep('traffic_log mmsi',col('port_surveillance/vessel_traffic_log.csv','mmsi'),mmsi)
rep('vessel_arrivals mmsi',col('supply/vessel_arrivals.csv','mmsi'),mmsi)
rep('cargo_manifest mmsi',col('supply/cargo_manifest.csv','mmsi'),mmsi)
rep('port_conditions vessel_mmsi',col('supply/port_conditions.csv','vessel_mmsi'),mmsi)
rep('vessel_arrivals terminal_id',col('supply/vessel_arrivals.csv','terminal_id'),term); rep('vessel_arrivals berth_id',col('supply/vessel_arrivals.csv','berth_id'),term)
rep('radar sensor_id',col('port_surveillance/radar_tracks_*.csv','sensor_id'),sens); rep('camera sensor_id',col('port_surveillance/camera_events.csv','sensor_id'),sens)
rep('drone_detections sensor_id',col('drone_detections/detections_*.csv','sensor_id'),sens)
rep('env sondes SensorID',col('env_sensors/water_quality_*.csv','SensorID'),sens); rep('env gauges SensorID',col('env_sensors/gauge_*.csv','SensorID'),sens); rep('env aqs SensorID',col('env_sensors/aqs_*.csv','SensorID'),sens)
rep('weather StationID',col('weather/*_observations.csv','StationID'),sens)
rep('ed Facility_ID',col('public_health/ed_visits_*.csv','Facility_ID'),fac); rep('hospital_capacity Facility_ID',col('public_health/hospital_capacity.csv','Facility_ID'),fac)
rep('cad transport_destination',col('911/cad_incidents_*.csv','transport_destination'),fac); rep('cad unit_id',col('911/cad_incidents_*.csv','unit_id'),units); rep('cad additional_units',col('911/cad_incidents_*.csv','additional_units',split=r'[;,| ]'),units)
rep('cad nature_code',col('911/cad_incidents_*.csv','nature_code'),units); rep('cad beat',col('911/cad_incidents_*.csv','beat'),units)
rep('fuel_deliveries facility_id',col('supply/fuel_deliveries.csv','facility_id'),fac|infra); rep('fuel_deliveries supplier_id',col('supply/fuel_deliveries.csv','supplier_id'),ent|orgs); rep('fuel receiving_asset_id',col('supply/fuel_deliveries.csv','receiving_asset_id'),infra|fac)
rep('shelter census facility_id',col('shelters/shelter_daily_census.csv','facility_id'),fac)
rep('base_status installation_id',col('maintenance/base_status_reports.csv','installation_id'),fac); rep('base_status equipment_id',col('maintenance/base_status_reports.csv','equipment_id'),infra)
rep('work_orders asset_id',col('maintenance/work_orders.csv','asset_id'),infra|tags|hosts|fac); rep('work_orders vendor_id',col('maintenance/work_orders.csv','vendor_id'),ent)
rep('historian Tagname',col('telemetry/historian_*.csv','Tagname'),tags)
rep('outage_map area_id',col('telemetry/outage_map.csv','area_id'),areas); rep('outage_map feeder_id',col('telemetry/outage_map.csv','feeder_id'),infra); rep('outage_map substation_id',col('telemetry/outage_map.csv','substation_id'),infra)
rep('eas AreaIDs',col('public_health/eas_broadcasts.csv','AreaIDs',split=';'),areas)
rep('syndromic Area_ID',col('public_health/syndrome_summary.csv','Area_ID'),areas); rep('aid area_id',col('payments/aid_applications.csv','area_id'),areas)
rep('damage assessment area',set(),areas)
rep('siem src_host',col('network_logs/siem/siem_alerts_2027-09.csv','src_host'),hosts); rep('siem dst_host',col('network_logs/siem/siem_alerts_2027-09.csv','dst_host'),hosts)
for f,c in [('endpoint_protection.csv','host'),('file_integrity.csv','host'),('historian_access.csv','client_host'),('historian_access.csv','server'),('ot_config_changes.csv','device'),('ot_config_changes.csv','source_host'),('remote_access_sessions.csv','gateway'),('remote_access_sessions.csv','target_hosts'),('scada_command_log.csv','workstation'),('scada_command_log.csv','device'),('alarm_suppression_audit.csv','source_host')]:
    rep('audit/'+f+' '+c,col('network_logs/audit/'+f,c,split=';'),hosts|infra|tags)
rep('contracts awards supplier_id',col('payments/contracts_awards.csv','supplier_id'),ent); rep('invoices supplier_id',col('payments/contracts_invoices.csv','supplier_id'),ent); rep('vendor_registry supplier_id',col('payments/contracts_vendor_registry.csv','supplier_id'),ent)
rep('insurance insurer_id',col('payments/insurance_claims.csv','insurer_id'),ent); rep('insurance adjuster_id',col('payments/insurance_claims.csv','adjuster_id'),ent)
rep('laanc operator_id',col('drone_detections/laanc_authorizations.csv','operator_id') if 'operator_id' in pd.read_csv(os.path.join(SRC,'drone_detections/laanc_authorizations.csv'),nrows=1).columns else set(),drone)
rep('sar asset_id',col('sar/sar_missions.csv','asset_id'),units|acr|mmsi|allstr(J('vessels.json')))
# vessel names
bad=collections.Counter()
for f in sorted(glob.glob(os.path.join(SRC,'ais','ais_*.csv'))):
    d=pd.read_csv(f,usecols=['MMSI','VesselName','IMO','CallSign'],dtype=str).drop_duplicates()
    for r in d.itertuples():
        reg=vname.get(r.MMSI,''); core=re.sub(r'^(MT|MV|FV|USCGC|M/V|TB|SS)\s+','',reg).upper()
        if r.VesselName.upper() not in (reg.upper(),core) and not core.startswith(r.VesselName.upper()): bad[(r.MMSI,r.VesselName,reg)]+=1
print('AIS name vs registry mismatches:',list(bad)[:10]); 
g=pd.concat([pd.read_csv(f,usecols=['MMSI','VesselName','IMO','CallSign'],dtype=str).drop_duplicates() for f in sorted(glob.glob(os.path.join(SRC,'ais','ais_*.csv')))]).drop_duplicates()
m=g.groupby('MMSI').VesselName.nunique(); print('MMSI with >1 name in AIS:',m[m>1].to_dict()); n=g.groupby('VesselName').MMSI.nunique(); print('names with >1 MMSI:',n[n>1].to_dict())
# users in social vs personas
sn={os.path.basename(f)[:-6] for f in glob.glob(os.path.join(SRC,'social_media','*.jsonl')) if not os.path.basename(f).startswith(('_','community_'))}
rep('social account files vs personas',sn,pers|{p.lstrip('@') for p in pers})
