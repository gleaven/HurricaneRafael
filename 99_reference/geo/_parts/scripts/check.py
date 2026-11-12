import json,math
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
G="./99_reference/geo/"
def polys(g):
    return [g['coordinates']] if g['type']=='Polygon' else g['coordinates']
def lines(g):
    return [g['coordinates']] if g['type']=='LineString' else g['coordinates']
def m(p,q):
    k=math.cos(math.radians(27.8)); return math.hypot((p[0]-q[0])*k*111320,(p[1]-q[1])*110800)
def seg_d(p,a,b):
    k=math.cos(math.radians(27.8))*111320; ky=110800
    px,py=(p[0]-a[0])*k,(p[1]-a[1])*ky; bx,by=(b[0]-a[0])*k,(b[1]-a[1])*ky
    L=bx*bx+by*by; t=0 if L==0 else max(0,min(1,(px*bx+py*by)/L))
    return math.hypot(px-t*bx,py-t*by)
def ring_gap(A,B):
    d=1e18
    for ra in A:
        for rb in B:
            for p in ra:
                for i in range(len(rb)-1): d=min(d,seg_d(p,rb[i],rb[i+1]))
            for p in rb:
                for i in range(len(ra)-1): d=min(d,seg_d(p,ra[i],ra[i+1]))
    return d
ch=json.load(open(G+'channels_usace.geojson')); ln=json.load(open(G+'channel_lines_usace.geojson')); no=json.load(open(G+'anchorages_fairways_noaa.geojson'))
print("counts: reaches",len(ch['features']),"| CC reaches",sum(f['properties']['reach_id'].startswith('CESWG_CC_') for f in ch['features']),"| lines",len(ln['features']),"| noaa",len(no['features']))
def chk(fc,name,bounds):
    nv=0; bad=0; unclosed=0; orient=0
    for f in fc['features']:
        g=f['geometry']
        if 'Polygon' in g['type']:
            for poly in polys(g):
                for i,r in enumerate(poly):
                    nv+=len(r)
                    if r[0]!=r[-1] or len(r)<4: unclosed+=1
                    a=sum(r[j][0]*r[j+1][1]-r[j+1][0]*r[j][1] for j in range(len(r)-1))
                    if (a>0)!=(i==0): orient+=1
                    for x,y in r:
                        if not(bounds[0]<=x<=bounds[1] and bounds[2]<=y<=bounds[3]): bad+=1
        else:
            for l in lines(g):
                nv+=len(l)
                for x,y in l:
                    if not(bounds[0]<=x<=bounds[1] and bounds[2]<=y<=bounds[3]): bad+=1
    print(f"{name}: vertices={nv} unclosed_rings={unclosed} wrong_orientation={orient} out_of_bounds_vertices={bad} (bounds {bounds})")
B=(-98,-96.5,27,28.5)
chk(ch,'channels_usace',B); chk(ln,'channel_lines_usace',B); chk(no,'noaa',B); chk(no,'noaa(wide)',(-98,-95.9,26.3,28.6))
# continuity of CC main channel
cc=[f for f in ch['features'] if f['properties']['reach_id'].startswith('CESWG_CC_') and '6A' not in f['properties']['reach_id']]
cc.sort(key=lambda f:f['properties']['mile_start'])
tot=0
for a,b in zip(cc,cc[1:]):
    A=[r for p in polys(a['geometry']) for r in p]; Bb=[r for p in polys(b['geometry']) for r in p]
    gap=ring_gap(A,Bb)
    print(f"  {a['properties']['reach_id']:20s} (mi {a['properties']['mile_start']:>5}-{a['properties']['mile_end']:>5}) -> {b['properties']['reach_id']:20s} gap={gap:6.1f} m  mile_join={'ok' if abs(a['properties']['mile_end']-b['properties']['mile_start'])<1e-9 else 'MISMATCH'} {'OK' if gap<150 else 'GAP!'}")
print("CC main-channel mileage:",cc[0]['properties']['mile_start'],"->",cc[-1]['properties']['mile_end'])
# branch joins
def get(i): return next(f for f in ch['features'] if f['properties']['reach_id']==i)
def R(f): return [r for p in polys(f['geometry']) for r in p]
for a,b in [('CESWG_LA_01_CLQ_1','CESWG_CC_05_HLQ_5'),('CESWG_LA_01_CLQ_1','CESWG_CC_06_LQB_6'),('CESWG_LA_01_CLQ_1','CESWG_LA_02_LTB_2'),('CESWG_LA_02_LTB_2','CESWG_LA_03_LEX_3'),('CESWG_JF_01_JFC_1','CESWG_LA_01_CLQ_1'),('CESWG_RC_01_APC_1','CESWG_CC_06_LQB_6'),('CESWG_RC_01_APC_1','CESWG_CC_6A_LQB_6'),('CESWG_RC_01_APC_1','CESWG_RC_02_CCH_2'),('CESWG_RC_02_CCH_2','CESWG_RC_03_CNA_3'),('CESWG_RC_03_CNA_3','CESWG_RC_04_TRB_4'),('CESWG_AP_01_CHN_1','CESWG_CC_04_IHI_4'),('CESWG_AP_01_CHN_1','CESWG_GI_1B_LCC_21'),('CESWG_AP_01_CHN_1','CESWG_AP_02_TRB_2'),('CESWG_AP_02_TRB_2','CESWG_AP_03_CCH_3'),('CESWG_AP_03_CCH_3','CESWG_AP_04_CBH_4'),('CESWG_AR_01_APC_1','CESWG_CC_05_HLQ_5'),('CESWG_AR_01_APC_1','CESWG_AR_02_TRB_2'),('CESWG_AR_02_TRB_2','CESWG_AR_03_ABN_3'),('CESWG_GI_21_ACC_21','CESWG_CC_05_HLQ_5'),('CESWG_GI_22_CCM_22','CESWG_CC_05_HLQ_5'),('CESWG_GI_21_ACC_21','CESWG_GI_22_CCM_22'),('CESWG_GI_22_CCM_22','CESWG_GI_23_MBI_23'),('CESWG_GI_20_AAB_20','CESWG_GI_21_ACC_21'),('CESWG_GI_1A_ABL_21','CESWG_GI_20_AAB_20'),('CESWG_GI_1A_ABL_21','CESWG_GI_1B_LCC_21'),('CESWG_GI_1B_LCC_21','CESWG_CC_04_IHI_4'),('CESWG_GI_21_ACC_21','CESWG_AP_01_CHN_1')]:
    print(f"  join {a} ~ {b}: {ring_gap(R(get(a)),R(get(b))):7.1f} m")
# outlier vertex test: any polygon edge > 20 km or line edge > 20km
for fc,nm in((ch,'ch'),(ln,'ln')):
    mx=0
    for f in fc['features']:
        g=f['geometry']; seqs=[r for p in polys(g) for r in p] if 'Polygon' in g['type'] else lines(g)
        for s in seqs:
            for i in range(len(s)-1): mx=max(mx,m(s[i],s[i+1]))
    print(nm,"longest edge m",round(mx))
# centerline length
tl=0
for f in ln['features']:
    if f['properties']['line_id'].startswith('CESWG_CC_'):
        for s in lines(f['geometry']): tl+=sum(m(s[i],s[i+1]) for i in range(len(s)-1))
print("CC centerline total length: %.1f km = %.2f statute mi = %.2f nmi"%(tl/1000,tl/1609.344,tl/1852))
# plot
col={'CORPUS CHRISTI':'#d62728','LA QUINTA':'#ff7f0e','GULF INTRACOASTAL WATERWAY':'#1f77b4','ARANSAS_PASS':'#2ca02c','RINCON_CANAL':'#9467bd','JEWEL_FULTON':'#8c564b','CHANNEL_TO_PORT_ARANSAS':'#e377c2'}
def draw(ax,noaa=True):
    if noaa:
        for f in no['features']:
            c='#bbbb00' if f['properties']['kind']=='anchorage' else '#77cccc'
            for p in polys(f['geometry']):
                xs,ys=zip(*p[0]); ax.fill(xs,ys,fc=c,ec=c,alpha=0.25,lw=0.8, hatch='//' if 'harbour' in f['properties']['source_layer'] else None)
    for f in ch['features']:
        c=col[f['properties']['project']]
        for p in polys(f['geometry']):
            xs,ys=zip(*p[0]); ax.fill(xs,ys,fc=c,ec=c,alpha=0.55,lw=1.2)
    for f in ln['features']:
        for s in lines(f['geometry']):
            xs,ys=zip(*s); ax.plot(xs,ys,'k-',lw=0.5)
    ax.set_aspect(1/math.cos(math.radians(27.8))); ax.grid(alpha=0.3)
fig,axs=plt.subplots(2,2,figsize=(18,14))
draw(axs[0,0]); axs[0,0].set_xlim(-97.6,-96.6); axs[0,0].set_ylim(27.45,28.15); axs[0,0].set_title('All: USACE reaches (colour by project), centerlines (black), NOAA anchorage (yellow) / fairways (cyan)')
import matplotlib.patches as mp
axs[0,0].legend(handles=[mp.Patch(color=v,label=k) for k,v in col.items()],fontsize=7,loc='lower right')
draw(axs[0,1]); axs[0,1].set_xlim(-97.56,-97.36); axs[0,1].set_ylim(27.795,27.855); axs[0,1].set_title('Inner Harbor + Rincon Canal')
draw(axs[1,0]); axs[1,0].set_xlim(-97.30,-97.03); axs[1,0].set_ylim(27.79,27.92); axs[1,0].set_title('Bay: CC channel, La Quinta, Jewel Fulton, GIWW, Aransas Pass channel')
draw(axs[1,1]); axs[1,1].set_xlim(-97.09,-96.93); axs[1,1].set_ylim(27.78,27.87); axs[1,1].set_title('Entrance: sea bar, jetty, Harbor Island, Port Aransas, anchorage/fairway')
for f in ch['features']:
    p=polys(f['geometry'])[0][0]; cx=sum(x for x,y in p)/len(p); cy=sum(y for x,y in p)/len(p)
    for ax in axs.flat[1:]:
        if ax.get_xlim()[0]<cx<ax.get_xlim()[1] and ax.get_ylim()[0]<cy<ax.get_ylim()[1]: ax.text(cx,cy,f['properties']['reach_id'].replace('CESWG_',''),fontsize=6)
plt.tight_layout(); plt.savefig(G+'_parts/channels_check.png',dpi=80); print("png ok")
