import json,glob,math,collections,sys
import numpy as np
G="./99_reference/geo/"
KX=111320*math.cos(math.radians(27.8)); KY=110574
def paths(f):
    g=f["geometry"]; return [g["coordinates"]] if g["type"]=="LineString" else g["coordinates"]
files=sorted(glob.glob(G+"roads_*.geojson"))
data={}
for fn in files:
    fc=json.load(open(fn)); data[fn.split("/")[-1]]=fc["features"]
# ranges, counts
cls=collections.defaultdict(lambda:[0,0,0.0]); seen=set()
allf=[]
for fn,feats in data.items():
    lons=[c[0] for f in feats for p in paths(f) for c in p]; lats=[c[1] for f in feats for p in paths(f) for c in p]
    km=0
    for f in feats:
        for p in paths(f):
            a=np.array(p); d=np.hypot(np.diff(a[:,0])*KX,np.diff(a[:,1])*KY); km+=d.sum()/1000
            if (d>8000).any(): pass
    print("%-34s feats %4d verts %5d km %7.1f lon %.5f..%.5f lat %.5f..%.5f"%(fn,len(feats),len(lons),km,min(lons),max(lons),min(lats),max(lats)))
    for f in feats:
        oid=f["properties"]["source_oid"]
        if oid in seen: continue
        seen.add(oid); allf.append(f)
        c=cls[f["properties"]["class"]]; c[0]+=1
        for p in paths(f):
            a=np.array(p); c[1]+=len(p); c[2]+=np.hypot(np.diff(a[:,0])*KX,np.diff(a[:,1])*KY).sum()/1000
print("unique-by-OID totals per class (feature first-seen class):")
for k,v in cls.items(): print("  %-10s feats %4d verts %5d km %.1f"%(k,v[0],v[1],v[2]))
print("  TOTAL unique feats",len(allf),"verts",sum(v[1] for v in cls.values()),"km %.1f"%sum(v[2] for v in cls.values()))
# connectivity
def dens(p,step=5.0):
    a=np.array(p); x=a[:,0]*KX; y=a[:,1]*KY; out=[]
    for i in range(len(a)-1):
        L=math.hypot(x[i+1]-x[i],y[i+1]-y[i]); n=max(1,int(math.ceil(L/step)))
        t=np.arange(n)/n
        out.append(np.c_[x[i]+t*(x[i+1]-x[i]),y[i]+t*(y[i+1]-y[i])])
    out.append(np.array([[x[-1],y[-1]]]))
    return np.vstack(out)
def components(feats,tol=15.0):
    par=list(range(len(feats)))
    def find(a):
        while par[a]!=a: par[a]=par[par[a]]; a=par[a]
        return a
    grid=collections.defaultdict(set)
    for i,f in enumerate(feats):
        for p in paths(f):
            if len(p)<2: continue
            pts=dens(p); cells=set(map(tuple,np.floor(pts/tol).astype(int)))
            for c in cells: grid[c].add(i)
    for (cx,cy),s in grid.items():
        near=set(s)
        for dx in (0,1):
            for dy in (-1,0,1):
                if dx==0 and dy<=0: continue
                near|=grid.get((cx+dx,cy+dy),set())
        l=list(near); r=find(l[0])
        for j in l[1:]:
            rj=find(j)
            if rj!=r: par[rj]=r
    comp=collections.defaultdict(list)
    for i in range(len(feats)): comp[find(i)].append(i)
    return sorted(comp.values(),key=len,reverse=True)
def flen(f): 
    return sum(np.hypot(np.diff(np.array(p)[:,0])*KX,np.diff(np.array(p)[:,1])*KY).sum() for p in paths(f))/1000
def report(label,feats):
    seen=set();u=[]
    for f in feats:
        if f["properties"]["source_oid"] not in seen: seen.add(f["properties"]["source_oid"]); u.append(f)
    comps=components(u); tot=sum(flen(f) for f in u)
    big=sum(flen(u[i]) for i in comps[0])
    print("\n[%s] %d unique feats, %d components; largest has %d feats = %.1f%% of km"%(label,len(u),len(comps),len(comps[0]),100*big/tot))
    for c in comps[1:]:
        km=sum(flen(u[i]) for i in c); names=sorted(set(str(u[i]["properties"]["name"]) for i in c))
        p0=paths(u[c[0]])[0][0]
        print("   isolated: %d feats %.2f km near (%.4f,%.4f): %s"%(len(c),km,p0[1],p0[0],", ".join(names)[:110]))
    return u
ma=report("major+arterial",data["roads_major.geojson"]+data["roads_arterial.geojson"])
report("major only",data["roads_major.geojson"])
report("ALL",[f for v in data.values() for f in v])
for k in data:
    if "local" in k: report(k+" + major + arterial",data[k]+data["roads_major.geojson"]+data["roads_arterial.geojson"]) if "-v" in sys.argv else None
# spot checks
allu=[f for v in data.values() for f in v]
def nearest(lat,lon):
    X=lon*KX;Y=lat*KY;best=(1e9,None)
    for f in allu:
        for p in paths(f):
            a=np.array(p);x=a[:,0]*KX;y=a[:,1]*KY
            if len(a)<2: continue
            dx=np.diff(x);dy=np.diff(y);L2=dx*dx+dy*dy;L2[L2==0]=1e-9
            t=np.clip(((X-x[:-1])*dx+(Y-y[:-1])*dy)/L2,0,1)
            d=np.hypot(x[:-1]+t*dx-X,y[:-1]+t*dy-Y).min()
            if d<best[0]: best=(d,f["properties"]["name"])
    return best
print()
for nm,lat,lon in [("SH358@Staples",27.7075,-97.3745),("I-37@Port Ave",27.797,-97.415),("JFK Cswy mid",27.635,-97.245)]:
    d,n=nearest(lat,lon); print("spot %-14s (%.4f,%.4f): nearest road %.0f m (%s)"%(nm,lat,lon,d,n))
# plot
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig,axs=plt.subplots(1,2,figsize=(22,10))
col={"primary":("#c00",1.8),"secondary":("#e80",1.1),"arterial":("#06c",0.9),"local":("#555",0.4)}
for ax,ext in zip(axs,[(-97.80,-96.93,27.53,28.12),(-97.53,-97.21,27.60,27.87)]):
    for order in ("local","arterial","secondary","primary"):
        for f in allu:
            if f["properties"]["class"]!=order: continue
            for p in paths(f):
                a=np.array(p); ax.plot(a[:,0],a[:,1],color=col[order][0],lw=col[order][1])
    ax.set_xlim(ext[0],ext[1]); ax.set_ylim(ext[2],ext[3]); ax.set_aspect(1/math.cos(math.radians(27.8))); ax.grid(alpha=.3)
    for nm,lat,lon in [("SH358@Staples",27.7075,-97.3745),("I-37@Port",27.797,-97.415),("JFK",27.635,-97.245)]: ax.plot(lon,lat,"g*",ms=10)
axs[0].set_title("TIGERweb roads: primary red, secondary orange, arterial blue, local grey"); axs[1].set_title("Corpus Christi zoom")
rl=json.load(open(G+"rail_port_corridor.geojson"))["features"]
for ax in axs:
    for f in rl:
        for p in paths(f):
            a=np.array(p); ax.plot(a[:,0],a[:,1],color="k",lw=0.8,ls="--")
plt.tight_layout(); plt.savefig(G+"_parts/roads_check.png",dpi=70)
