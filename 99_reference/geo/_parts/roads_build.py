import json,glob,os,collections,sys
G="./99_reference/geo/"
P=G+"_parts/"
def load(f): return json.load(open(f))
def feat(attrs,paths,cls,layer,rttyp=None):
    paths=[[[float(x),float(y)] for x,y in p] for p in paths]
    geom={"type":"LineString","coordinates":paths[0]} if len(paths)==1 else {"type":"MultiLineString","coordinates":paths}
    return {"type":"Feature","properties":{"name":attrs.get("NAME"),"mtfcc":attrs.get("MTFCC"),"rttyp":attrs.get("RTTYP",rttyp) if "RTTYP" in attrs else rttyp,"class":cls,"source_oid":attrs["OID"],"source_layer":layer},"geometry":geom}
def dump(name,feats,desc):
    fc={"type":"FeatureCollection","name":name,"source":"US Census TIGERweb Transportation MapServer (ArcGIS REST), outSR=4326, geometryPrecision=5, maxAllowableOffset=5e-5 deg","description":desc,"features":feats}
    json.dump(fc,open(G+name+".geojson","w"),separators=(",",":"))
    nv=sum(len(p) for f in feats for p in ([f["geometry"]["coordinates"]] if f["geometry"]["type"]=="LineString" else f["geometry"]["coordinates"]))
    print(name,len(feats),"features",nv,"vertices")
# ---- major
major=[];seen={}
def add(lst,seen,f,src):
    oid=f["properties"]["source_oid"]
    if oid in seen:
        if seen[oid]["geometry"]!=f["geometry"]: print("WARN differing duplicate",oid,f["properties"]["name"],src)
        return
    seen[oid]=f; lst.append(f)
for f in sorted(glob.glob(P+"roads_major_L2_*.json")):
    d=load(f)
    for ft in d["features"]: add(major,seen,feat(ft["attributes"],ft["geometry"]["paths"],"primary",2),f)
for f in sorted(glob.glob(P+"roads_major_L6_*.json")):
    d=load(f)
    for ft in d["features"]: add(major,seen,feat(ft["attributes"],ft["geometry"]["paths"],"secondary",6,d.get("rttyp")),f)
for f in sorted(glob.glob(P+"roads_majorfill_*.json")):
    d=load(f)
    for ft in d["features"]: add(major,seen,feat(ft["attributes"],ft["geometry"]["paths"],d.get("class","secondary"),d["layer"]),f)
# FM 624 / FM 665 were returned whole by the local-box queries (layer 8); promote copies into roads_major
for f in sorted(glob.glob(P+"roads_loc_*_p*.json")):
    for ft in load(f)["features"]:
        if ft["attributes"]["OID"] in ("1106068777930","1102217726841"): add(major,seen,feat(ft["attributes"],ft["geometry"]["paths"],"secondary",8),f)
dump("roads_major",major,"Primary (layer 2) and Secondary (layer 6) roads intersecting lon -97.75..-96.95, lat 27.55..28.10; plus FM routes fetched by name from Local Roads layer 8 (source_layer=8)")
# ---- arterial
art=[];seen={}
for fa in sorted(glob.glob(P+"roads_art*_attr.json")):
    fg=fa.replace("_attr.json","_geom.json")
    A={ft["attributes"]["OID"]:ft["attributes"] for ft in load(fa)["features"]}
    Gm={ft["attributes"]["OID"]:ft["geometry"]["paths"] for ft in load(fg)["features"]}
    if set(A)!=set(Gm): print("WARN oid mismatch",fa)
    for oid in A:
        if oid in Gm: add(art,seen,feat(A[oid],Gm[oid],"arterial",8),fa)
for f in sorted(glob.glob(P+"roads_artfill_*.json")):
    d=load(f)
    for ft in d["features"]: add(art,seen,feat(ft["attributes"],ft["geometry"]["paths"],"arterial",d["layer"]),f)
dump("roads_arterial",art,"Named arterial streets fetched by NAME from Local Roads layer 8")
# ---- local
areas=["north_beach","hillcrest","molina","flour_bluff","calallen","port_aransas","downtown"]
allloc={}
for a in areas:
    for f in sorted(glob.glob(P+"roads_loc_%s_p*.json"%a)):
        for ft in load(f)["features"]:
            oid=ft["attributes"]["OID"]
            ff=feat(ft["attributes"],ft["geometry"]["paths"],"local",8)
            if oid in allloc and allloc[oid][1]["geometry"]!=ff["geometry"]: print("WARN differing dup local",oid,f)
            allloc.setdefault(oid,(a,ff))
for a in areas:
    feats=[];seen={}
    for f in sorted(glob.glob(P+"roads_loc_%s_p*.json"%a)):
        for ft in load(f)["features"]: add(feats,seen,feat(ft["attributes"],ft["geometry"]["paths"],"local",8),f)
    of=P+"roads_loc_%s_oids.json"%a
    if os.path.exists(of):
        for oid in load(of)["oids"]:
            if oid not in seen:
                if oid in allloc: add(feats,seen,allloc[oid][1],of)
                else: print("MISSING oid",oid,"for",a)
    dump("roads_local_"+a,feats,"Every Local Roads (layer 8) feature intersecting the %s box"%a)

# ---- rail (optional D)
rail=[];seen={}
for f in sorted(glob.glob(P+"rail_L9_*.json")):
    for ft in load(f)["features"]:
        ff=feat(ft["attributes"],ft["geometry"]["paths"],"rail",9); add(rail,seen,ff,f)
dump("rail_port_corridor",rail,"Railroads (layer 9) intersecting lon -97.55..-97.38, lat 27.78..27.86 (port corridor). NOT a road layer; class=rail")

# ---- interchange ramps (layer 8, MTFCC S1630)
d=load(P+"roads_ramps_L8.json"); ramps=[];seen={}
for g in d["groups"]:
    assert len(g["features"])==g["server_count"],g["area"]
    for ft in g["features"]:
        a=dict(ft["attributes"]); a["MTFCC"]=d["mtfcc"]; a["RTTYP"]=d["rttyp"]
        add(ramps,seen,feat(a,ft["geometry"]["paths"],"local",8),g["area"])
dump("roads_local_interchange_ramps",ramps,"Ramps (layer 8, MTFCC S1630) at the SH358/SH44, I-37/SH358 and SH358/SH286 interchanges")
