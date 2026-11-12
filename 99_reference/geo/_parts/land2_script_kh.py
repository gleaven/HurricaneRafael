"""Keyhole: merge polygon holes into the exterior ring through zero-width bridges between EXISTING vertices."""
import numpy as np
def sarea(r):
    a=np.asarray(r,float); return 0.5*float(np.sum(a[:-1,0]*a[1:,1]-a[1:,0]*a[:-1,1]))
def _orient(ax,ay,bx,by,cx,cy):
    return (bx-ax)*(cy-ay)-(by-ay)*(cx-ax)
def _crosses(p,q,A,B):
    """True if open segment p-q properly intersects or touches any segment A[i]-B[i] (except at shared endpoints)."""
    if len(A)==0: return False
    ax,ay=A[:,0],A[:,1]; bx,by=B[:,0],B[:,1]
    d1=_orient(p[0],p[1],q[0],q[1],ax,ay); d2=_orient(p[0],p[1],q[0],q[1],bx,by)
    d3=_orient(ax,ay,bx,by,p[0],p[1]); d4=_orient(ax,ay,bx,by,q[0],q[1])
    # bounding boxes overlap
    bb=(np.minimum(ax,bx)<=max(p[0],q[0]))&(np.maximum(ax,bx)>=min(p[0],q[0]))&(np.minimum(ay,by)<=max(p[1],q[1]))&(np.maximum(ay,by)>=min(p[1],q[1]))
    hit=bb&(d1*d2<=0)&(d3*d4<=0)
    # ignore edges that share an endpoint with p or q (touch only there)
    sh=((ax==p[0])&(ay==p[1]))|((bx==p[0])&(by==p[1]))|((ax==q[0])&(ay==q[1]))|((bx==q[0])&(by==q[1]))
    # but a shared-endpoint edge that is collinear and overlapping is still bad
    col=sh&(d1==0)&(d2==0)
    return bool(np.any(hit&~sh) or np.any(col&bb&False))
def keyhole(ext,holes):
    """ext: closed ring (CCW), holes: closed rings (CW). Returns one closed ring."""
    ext=[tuple(p) for p in ext]
    if sarea(ext)<0: ext=ext[::-1]
    hs=[]
    for h in holes:
        h=[tuple(p) for p in h]
        if sarea(h)>0: h=h[::-1]
        hs.append(h)
    # process holes from the one with largest max-x
    hs.sort(key=lambda h:-max(p[0] for p in h))
    cur=ext[:-1]   # open list
    remaining=hs[:]
    while remaining:
        h=remaining.pop(0); ho=h[:-1]
        # obstacle edges: current ring + all holes (this one and remaining)
        ringsE=[cur+[cur[0]],h]+remaining
        A=np.array([p for r in ringsE for p in r[:-1]],float); B=np.array([p for r in ringsE for p in r[1:]],float)
        H=np.array(ho,float); C=np.array(cur,float)
        done=False
        # candidate hole vertices ordered by x desc; candidate ring vertices by distance
        for hi in np.argsort(-H[:,0])[:min(len(ho),40)]:
            hp=ho[hi]
            d=(C[:,0]-hp[0])**2+(C[:,1]-hp[1])**2
            for ci in np.argsort(d)[:60]:
                cp=cur[ci]
                if cp==hp: continue
                if not _crosses(hp,cp,A,B):
                    loop=ho[hi:]+ho[:hi]+[hp]
                    cur=cur[:ci+1]+loop+[cp]+cur[ci+1:]
                    done=True; break
            if done: break
        if not done: raise RuntimeError('no bridge found')
    return [list(p) for p in cur+[cur[0]]]
if __name__=='__main__':
    from matplotlib.path import Path
    ext=[(0,0),(10,0),(10,10),(0,10),(0,0)]; holes=[[(2,2),(2,4),(4,4),(4,2),(2,2)],[(6,6),(6,8),(8,8),(8,6),(6,6)]]
    k=keyhole(ext,holes); print(k)
    p=Path(np.array(k,float))
    for pt in [(1,1),(3,3),(7,7),(5,5),(9,9),(11,5)]: print(pt,p.contains_point(pt))
