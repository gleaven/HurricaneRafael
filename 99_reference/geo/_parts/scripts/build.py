import json,glob,math,sys,shutil,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from verify import server_reaches, server_lines, TR, REACH_FILES, LINE_FILES
G="./99_reference/geo/"
P=G+"_parts/"
def sarea(r): return sum(r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1] for i in range(len(r)-1))/2
def pip(pt,ring):
    x,y=pt; c=False
    for i in range(len(ring)-1):
        x1,y1=ring[i]; x2,y2=ring[i+1]
        if (y1>y)!=(y2>y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def esri_to_geojson(rings):
    """Esri: clockwise = outer, ccw = hole. Output RFC7946 (outer ccw, holes cw). Coordinates unchanged, only ring order reversed."""
    outers=[r for r in rings if sarea(r)<0]; holes=[r for r in rings if sarea(r)>0]
    assert outers
    polys=[[o[::-1]] for o in outers]
    for h in holes:
        for i,o in enumerate(outers):
            if pip(h[0],o): polys[i].append(h[::-1]); break
        else: raise Exception("orphan hole")
    return {"type":"Polygon","coordinates":polys[0]} if len(polys)==1 else {"type":"MultiPolygon","coordinates":polys}
# ---- reaches
srv=server_reaches()
attrs={r[0]:r for r in json.load(open(P+'reach_attributes.json'))['rows']}
feats=[]
for f in sorted(glob.glob(P+'reach_p*.json')):
    for o in json.load(open(f)):
        a=attrs[o['reach_id']]; s=srv[o['reach_id']]['attributes']
        assert srv[o['reach_id']]['geometry']['rings']==o['rings']
        feats.append({"type":"Feature","properties":{"reach_id":a[0],"area_id":a[1],"description":a[2],"project":a[3],"mile_start":a[4],"mile_end":a[5],"depth_ft":a[6],"width_from_ft":a[7],"width_to_ft":a[8],
            "depth_authorized_ft":s.get('depthauthorized'),"reported_length_mi":s.get('reportedlength'),"reach_type":s.get('channelreachtype'),"source":"USACE National Channel Framework ChannelReach (layer 2)","source_objectid":s['OBJECTID'],"source_dataset":s.get('mediaidfk')},
            "geometry":esri_to_geojson(o['rings'])})
feats.sort(key=lambda f:(f['properties']['project'],f['properties']['mile_start'],f['properties']['reach_id']))
json.dump({"type":"FeatureCollection","name":"channels_usace","crs_note":"WGS84 lon/lat (server SR 4326), coordinates rounded by server to 5 decimals (geometryPrecision=5)","features":feats},open(G+'channels_usace.geojson','w'),indent=1)
print("reaches written",len(feats))
# ---- lines
ls=server_lines()
lf=[]; used=set()
for f in sorted(glob.glob(P+'line_p*.json')):
    for o in json.load(open(f)):
        # match server record for attributes
        cand=[c for oid,c in ls.items() if c['attributes']['channellineidpk']==o['line_id'] and oid not in used and [[[round(x,5),round(y,5)] for x,y in p] for p in c['geometry']['paths']]==o['paths']]
        s=cand[0]['attributes']; used.add(s['OBJECTID'])
        paths=o['paths']; dropped=[]
        if o['line_id']=='CESWG_AP_04_CBH':
            keep=[p for p in paths if p[0][1]<27.95]; dropped=[p for p in paths if p[0][1]>=27.95]; paths=keep
        # drop consecutive duplicate vertices? NO - keep server vertices as-is
        geom={"type":"LineString","coordinates":paths[0]} if len(paths)==1 else {"type":"MultiLineString","coordinates":paths}
        props={"line_id":o['line_id'],"line_type":s['channellinetype'],"project_code":s['sdsfeaturedescription'],"source":"USACE National Channel Framework ChannelLine (layer 0)","source_objectid":s['OBJECTID'],"source_dataset":s.get('mediaidfk')}
        if dropped: props["note"]="1 stray ~1 m server path at "+json.dumps(dropped[0][0])+" (in Aransas Bay, 14 km from this reach) omitted; raw kept in _parts/line_p04.json"
        lf.append({"type":"Feature","properties":props,"geometry":geom})
lf.sort(key=lambda f:(f['properties']['line_id'],f['properties']['source_objectid']))
json.dump({"type":"FeatureCollection","name":"channel_lines_usace","crs_note":"WGS84 lon/lat, 5 decimals. CenterLine features only (layer also holds StationLine and ToeLine, not collected).","features":lf},open(G+'channel_lines_usace.geojson','w'),indent=1)
print("lines written",len(lf))
# ---- noaa
nf=[]; excl=0
for f in sorted(glob.glob(P+'noaa_p*.json')):
    for o in json.load(open(f)):
        if o.get('exclude_from_final'): excl+=1; continue
        props={"kind":o['kind'],"name":o['name'],"source_layer":o['source_layer'],"source":"NOAA ENC Direct to GIS","source_objectid":o['objectid'],"enc_cell":o['enc_cell'],"simplified_deg":o['simplified_deg']}
        for k in ('inform','sorind','sordat'):
            if k in o: props[k]=o[k]
        nf.append({"type":"Feature","properties":props,"geometry":esri_to_geojson(o['rings'])})
json.dump({"type":"FeatureCollection","name":"anchorages_fairways_noaa","crs_note":"WGS84 lon/lat, 5 decimals, server-simplified with maxAllowableOffset=0.0005 deg (~50 m). Harbour-band features are clipped at ENC cell edges by the source. Not for navigation.","features":nf},open(G+'anchorages_fairways_noaa.geojson','w'),indent=1)
print("noaa written",len(nf),"excluded",excl)
# ---- raw evidence copies
os.makedirs(P+'raw_server_responses',exist_ok=True)
for fn in REACH_FILES+LINE_FILES:
    shutil.copy(TR+fn,P+'raw_server_responses/'+fn)
print(os.listdir(P+'raw_server_responses'))
