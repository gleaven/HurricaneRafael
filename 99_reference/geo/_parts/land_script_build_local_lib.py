def sarea(r):
    return 0.5*sum(r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1] for i in range(len(r)-1))
def clip_ring(ring,rect):
    x0,y0,x1,y1=rect
    pts=ring[:-1] if ring[0]==ring[-1] else ring[:]
    def clip(pts,inside,inter):
        out=[]
        n=len(pts)
        for i in range(n):
            a=pts[i-1]; b=pts[i]
            ia,ib=inside(a),inside(b)
            if ib:
                if not ia: out.append(inter(a,b))
                out.append(b)
            elif ia: out.append(inter(a,b))
        return out
    def ix(xc):
        return lambda a,b:[xc, round(a[1]+(b[1]-a[1])*(xc-a[0])/(b[0]-a[0]),5)]
    def iy(yc):
        return lambda a,b:[round(a[0]+(b[0]-a[0])*(yc-a[1])/(b[1]-a[1]),5), yc]
    for inside,inter in ((lambda p:p[0]>=x0,ix(x0)),(lambda p:p[0]<=x1,ix(x1)),(lambda p:p[1]>=y0,iy(y0)),(lambda p:p[1]<=y1,iy(y1))):
        pts=clip(pts,inside,inter)
        if len(pts)<3: return None
    # drop consecutive duplicates
    o=[pts[0]]
    for p in pts[1:]:
        if p!=o[-1]: o.append(p)
    if o[0]==o[-1]: o.pop()
    if len(o)<3: return None
    o.append(o[0])
    if abs(sarea(o))<1e-10: return None
    return o
def pip_ring(x,y,r):
    c=False
    for i in range(len(r)-1):
        x1,y1=r[i]; x2,y2=r[i+1]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def to_geojson_geom(rings):
    ext=[r for r in rings if sarea(r)<0]   # esri exterior = clockwise
    holes=[r for r in rings if sarea(r)>0]
    if not ext:  # orientation unexpected: treat all as exteriors
        ext=rings; holes=[]
    polys=[[e[::-1]] for e in ext]
    for h in holes:
        hx,hy=h[0]
        placed=False
        for k,e in enumerate(ext):
            if pip_ring(hx,hy,e) or pip_ring(h[1][0],h[1][1],e):
                polys[k].append(h[::-1]); placed=True; break
        if not placed: polys[0].append(h[::-1])
    if len(polys)==1: return {'type':'Polygon','coordinates':polys[0]}
    return {'type':'MultiPolygon','coordinates':polys}

