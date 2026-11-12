import sys,json,os
sys.path.insert(0,'./_scratch/work/geo')
from parsefetch import load
from build_local_lib import to_geojson_geom
G='./99_reference/geo/'
u,fs,t,_=load(G+'_parts/land_raw_tiger_oso.txt')
feats=[];n=0
for x in fs:
    if x['attributes']['NAME']!='Oso Bay': continue
    rs=x['geometry']['rings']; n+=sum(len(r) for r in rs)
    feats.append({'type':'Feature','properties':{'name':'Oso Bay','source':'US Census TIGERweb Hydro/MapServer/1 Areal Hydrography (MTFCC H2051), vintage 2026-01-01','objectid':x['attributes']['OBJECTID'],'tolerance_deg':0.0001},'geometry':to_geojson_geom(rs)})
fc={'type':'FeatureCollection','name':'water_overrides_local','metadata':{'what':'Water bodies that the ENC coastal band (1:150k-1:600k) draws as land. Validator rule: WATER if inside any feature here; else LAND if inside any land_local.geojson feature; else WATER.','datum':'WGS84 (server-projected from NAD83/Web Mercator)','fetched':'2026-11-09'},'features':feats}
json.dump(fc,open(G+'water_overrides_local.geojson','w'),separators=(',',':'))
print(len(feats),n)
