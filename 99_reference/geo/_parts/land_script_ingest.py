import sys,os,shutil,json,glob,re
sys.path.insert(0,'./_scratch/work/geo')
from parsefetch import load
from collections import Counter
R='./_scratch/fetch'
P='./99_reference/geo/_parts'
def find(sub):
    fs=sorted(glob.glob(R+'/mcp-workspace-web_fetch-*.txt'),key=os.path.getmtime,reverse=True)
    for f in fs[:40]:
        with open(f,encoding='utf-8',errors='replace') as fh: first=fh.readline()
        if sub in first: return f
    raise SystemExit('no fetch file with url containing '+sub)
if __name__=='__main__':
    tag=sys.argv[1]; sub=sys.argv[2]
    src=find(sub)
    url,feats,trunc,_=load(src)
    dst=os.path.join(P,'land_raw_'+tag+'.txt')
    if os.path.exists(dst): print('EXISTS, not overwriting',dst)
    else: shutil.copyfile(src,dst)
    tot=sum(sum(len(r) for r in f['geometry'].get('rings',[])) for f in feats if f.get('geometry'))
    a=[f['attributes'] for f in feats]
    print(os.path.basename(src),'->',os.path.basename(dst))
    print(url[:260])
    print('complete features',len(feats),'truncated',trunc,'verts',tot)
    if a:
        print('first',str(a[0])[:200]); print('last',str(a[-1])[:200])
        print(Counter(x.get('DSNM') for x in a))
        big=[(x['attributes'].get('OBJECTID'),sum(len(r) for r in x['geometry'].get('rings',[]))) for x in feats]
        print('big',[b for b in big if b[1]>150][:30])
