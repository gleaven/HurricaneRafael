import sys,json,glob,os,math
import numpy as np, cv2
sys.path.insert(0,'./_scratch/work/geo2')
from parsefetch import load
G='./99_reference/geo/'
P=G+'_parts/'
BOX=(-97.65,27.525,-96.85,28.125)
MLAT=110950.0; MLON=111320.0*math.cos(math.radians(27.8))
def sarea(r): 
    a=np.asarray(r); return 0.5*float(np.sum(a[:-1,0]*a[1:,1]-a[1:,0]*a[:-1,1]))
class Grid:
    def __init__(s,res=10.0,box=BOX):
        s.res=res; s.box=box
        s.nx=int(round((box[2]-box[0])*MLON/res)); s.ny=int(round((box[3]-box[1])*MLAT/res))
    def px(s,xy):
        xy=np.asarray(xy,float)
        x=(xy[:,0]-s.box[0])*MLON/s.res; y=(s.box[3]-xy[:,1])*MLAT/s.res
        return np.round(np.column_stack([x,y])).astype(np.int32)
    def zeros(s): return np.zeros((s.ny,s.nx),np.uint8)
    def fill(s,img,rings,val=1):
        cv2.fillPoly(img,[s.px(r) for r in rings],val)
    def rc(s,lat,lon):
        return int((s.box[3]-lat)*MLAT/s.res), int((lon-s.box[0])*MLON/s.res)
def gj_polys(geom):
    return [geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
def esri_feats(pattern):
    d={}
    for f in sorted(glob.glob(P+pattern)):
        u,fs,t,_=load(f)
        for x in fs:
            oid=x['attributes'].get('OBJECTID')
            if oid not in d: d[oid]=(x['attributes'],x['geometry']['rings'],os.path.basename(f))
    return d
def tiles():
    return json.load(open(P+'land_coverage_rects.json'))
