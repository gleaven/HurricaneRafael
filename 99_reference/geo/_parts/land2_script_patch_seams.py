"""Close generalisation slivers between adjacent TIGER water polygons with quadrilaterals made of EXISTING vertices only."""
import sys
from lib import *
from matplotlib.path import Path
FAR=7.0; NEAR=1.5; STEP=4.0; MAXW=7.0
wpath=G+'water_overrides_local.geojson'
wc=json.load(open(wpath))
wc['features']=[f for f in wc['features'] if f['properties'].get('kind')!='seam_patch']
land=[]
for f in json.load(open(G+'land_local.geojson'))['features']:
    for p in gj_polys(f['geometry']):
        a=np.asarray(p[0],float); land.append(((a[:,0].min(),a[:,1].min(),a[:,0].max(),a[:,1].max()),[Path(np.asarray(r,float)) for r in p]))
def contains_set(items,pts):
    out=np.zeros(len(pts),bool)
    for bb,paths in items:
        m=(pts[:,0]>=bb[0])&(pts[:,0]<=bb[2])&(pts[:,1]>=bb[1])&(pts[:,1]<=bb[3])
        if not m.any(): continue
        idx=np.where(m)[0]; ins=np.zeros(len(idx),bool)
        for p in paths: ins^=p.contains_points(pts[idx])
        out[idx]|=ins
    return out
def run(features):
    W=[]
    for k,f in enumerate(features):
        for p in gj_polys(f['geometry']):
            a=np.asarray(p[0],float); W.append({'bb':(a[:,0].min(),a[:,1].min(),a[:,0].max(),a[:,1].max()),'path':Path(a),'xy':a,'f':k,'zone':f['properties']['zone']})
    witems=[(w['bb'],[w['path']]) for w in W]
    def is_land(pts): return contains_set(land,pts)&~contains_set(witems,pts)
    S=[];N=[];PI=[];EI=[]
    for wi,w in enumerate(W):
        if w['zone']=='harbour_tile': continue
        a=w['xy'][:-1]; b=w['xy'][1:]
        d=np.hypot((b[:,0]-a[:,0])*MLON,(b[:,1]-a[:,1])*MLAT)
        for i in np.where(d>=1)[0]:
            k=max(1,int(d[i]/STEP)); t=(np.arange(k)+0.5)/k
            S.append(a[i]+np.outer(t,b[i]-a[i])); nx=-(b[i,1]-a[i,1])*MLAT/d[i]; ny=(b[i,0]-a[i,0])*MLON/d[i]
            N.append(np.tile([nx/MLON,ny/MLAT],(k,1))); PI+=[wi]*k; EI+=[i]*k
    S=np.vstack(S); N=np.vstack(N); PI=np.array(PI); EI=np.array(EI)
    inbox=lambda p:(p[:,0]>BOX[0])&(p[:,0]<BOX[2])&(p[:,1]>BOX[1])&(p[:,1]<BOX[3])
    bad=[]
    for sgn in (1,-1):
        near=is_land(S+sgn*NEAR*N)
        idx=np.where(near)[0]
        farp=S[idx]+sgn*FAR*N[idx]
        farw=contains_set(witems,farp)&inbox(farp)       # water of an override polygon just beyond a thin land strip
        nolandfar=~contains_set(land,farp)&inbox(farp)&~farw
        for j,ok in zip(idx,farw):
            if ok: bad.append((PI[j],EI[j],sgn,j))
        print('   side %+d: thin strip with override water beyond: %d samples; with open (no-land) water beyond: %d samples'%(sgn,farw.sum(),nolandfar.sum()))
    return W,S,N,bad
def seg_pt_dist(P,a,b):
    # distance in metres from point P to segments a[i]-b[i]
    ax=(a[:,0]-P[0])*MLON; ay=(a[:,1]-P[1])*MLAT; bx=(b[:,0]-P[0])*MLON; by=(b[:,1]-P[1])*MLAT
    dx=bx-ax; dy=by-ay; L2=dx*dx+dy*dy
    t=np.clip(np.where(L2>0,-(ax*dx+ay*dy)/np.where(L2>0,L2,1),0),0,1)
    return np.hypot(ax+t*dx,ay+t*dy)
feats=wc['features']; allp=[]
for it in range(3):
    print('pass',it)
    W,S,N,bad=run(feats)
    edges={}
    for wi,ei,sgn,j in bad: edges.setdefault((wi,ei,sgn),[]).append(j)
    print('   bad samples',len(bad),'bad edges',len(edges),'(%.0f m)'%(len(bad)*STEP))
    if not edges: break
    new=[]; seen=set()
    for (wi,ei,sgn),js in edges.items():
        A=W[wi]; a=A['xy'][ei]; b=A['xy'][ei+1]
        j=js[len(js)//2]; farp=(S[j]+sgn*FAR*N[j])[None,:]
        B=None
        for wj,w in enumerate(W):
            if wj==wi: continue
            bb=w['bb']
            if bb[0]<=farp[0,0]<=bb[2] and bb[1]<=farp[0,1]<=bb[3] and w['path'].contains_points(farp)[0]: B=w; bj=wj; break
        if B is None: continue
        ua=B['xy'][:-1]; ub=B['xy'][1:]
        d=seg_pt_dist(S[j],ua,ub); k=int(np.argmin(d))
        if d[k]>FAR+4: continue
        u=B['xy'][k]; v=B['xy'][k+1]
        dirx=(b[0]-a[0])*MLON; diry=(b[1]-a[1])*MLAT
        pu=(u[0]-a[0])*MLON*dirx+(u[1]-a[1])*MLAT*diry; pv=(v[0]-a[0])*MLON*dirx+(v[1]-a[1])*MLAT*diry
        wv=B['xy'][int(np.argmin(np.hypot((B['xy'][:,0]-S[j][0])*MLON,(B['xy'][:,1]-S[j][1])*MLAT)))]
        cands=[[a,b,u,v] if pu>pv else [a,b,v,u],[a,b,u],[a,b,v],[a,b,wv]]
        fa=feats[A['f']]['properties']; fb=feats[B['f']]['properties']
        ida=fa.get('objectid') or fa.get('geoid'); idb=fb.get('objectid') or fb.get('geoid')
        for ring in cands:
            ring=[[float(p[0]),float(p[1])] for p in ring]
            dd=[]
            for p in ring:
                if p not in dd: dd.append(p)
            if len(dd)<3: continue
            key=tuple(sorted(map(tuple,dd)))
            if key in seen: continue
            r=np.array(dd+[dd[0]])
            ar=abs(0.5*np.sum(r[:-1,0]*r[1:,1]-r[1:,0]*r[:-1,1]))*MLON*MLAT
            per=np.hypot(np.diff(r[:,0])*MLON,np.diff(r[:,1])*MLAT).sum()
            if ar<1 or 2*ar/per>MAXW: continue
            seen.add(key); dd.append(dd[0])
            new.append({'type':'Feature','properties':{'name':fa.get('name') or fb.get('name'),'source':'seam patch between US Census TIGERweb water polygons %s and %s: polygon through %d existing vertices of those two polygons (no new coordinate)'%(ida,idb,len(dd)-1),'objectid':None,'geoid':None,'mtfcc':None,'tolerance_deg':0.0001,'zone':fa['zone'],'cell':fa.get('cell'),'clip_rect':fa.get('clip_rect'),'clipped':False,'holes_keyholed':0,'kind':'seam_patch','reason':'closes a hairline gap (mean width %.1f m, %.0f m2) left between two adjacent water polygons by the server-side 0.0001-deg generalisation'%(2*ar/per,ar),'raw_file':None},'geometry':{'type':'Polygon','coordinates':[dd]}})
    print('   patches added',len(new))
    if not new: break
    feats=feats+new; allp+=new
wc['features']=feats
json.dump(wc,open(wpath,'w'),separators=(',',':'))
print('total seam patches',len(allp),'features now',len(feats))
