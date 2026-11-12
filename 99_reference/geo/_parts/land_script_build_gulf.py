import sys,json,os
sys.path.insert(0,'./_scratch/work/geo')
from parsefetch import load
from build_local_lib import to_geojson_geom,sarea
G='./99_reference/geo/'
u,fs,t,_=load(G+'_parts/land_raw_gulf_p1.txt')
feats=[];tot=0;amin=9
for x in fs:
    rs=x['geometry']['rings']
    a=abs(sum(sarea(r) for r in rs)); amin=min(amin,a)
    tot+=sum(len(r) for r in rs)
    feats.append({'type':'Feature','properties':{'name':x['attributes'].get('OBJNAM'),'source':'NOAA ENC Direct enc_overview/MapServer/93 Overview.Land_Area (S-57 LNDARE), cell US1GC09M (overview band, 1:1,500,001 or smaller)','objectid':x['attributes']['OBJECTID'],'tolerance_deg':0.015,'area_deg2':round(a,5)},'geometry':to_geojson_geom(rs)})
fc={'type':'FeatureCollection','name':'land_gulf_coarse','metadata':{'what':'Coarse land polygons, Gulf of Mexico basin + NW Caribbean/Bahamas (US, Mexico, Cuba, Belize...). LAND if inside any feature.','valid_extent_lonlat':[-98.0,17.791,-76.1,33.609],'datum':'WGS84','fetched':'2026-11-09','note':'189 largest LNDARE polygons of ENC cell US1GC09M; smaller islets (< about %.5f deg2) omitted. Straight edges at lon -98, lat 17.791, lat 33.609, lon -76.1 are chart-limit cut lines, not coast.'%amin},'features':feats}
json.dump(fc,open(G+'land_gulf_coarse.geojson','w'),separators=(',',':'))
print(len(feats),'features',tot,'verts','min area',amin,os.path.getsize(G+'land_gulf_coarse.geojson'))
