import sys,json,glob,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from parse_trunc import parse
TR='./_scratch/fetch/'
P="./99_reference/geo/_parts/"
REACH_FILES=['mcp-workspace-web_fetch-1794263774123.txt','mcp-workspace-web_fetch-1794263846907.txt','mcp-workspace-web_fetch-1794263877379.txt']
LINE_FILES=['mcp-workspace-web_fetch-1794263848183.txt','mcp-workspace-web_fetch-1794263849458.txt']
def server_reaches():
    srv={}
    for fn in REACH_FILES:
        feats,comp=parse(TR+fn)
        for f in feats: srv[f['attributes']['channelreachidpk']]=f
    return srv
def server_lines():
    ls={}
    for fn in LINE_FILES:
        feats,comp=parse(TR+fn)
        for f in feats: ls[f['attributes']['OBJECTID']]=f
    return ls
if __name__=="__main__":
    srv=server_reaches()
    print("server reaches recovered:",len(srv))
    mine={}
    for f in sorted(glob.glob(P+'reach_p*.json')):
        for o in json.load(open(f)): mine[o['reach_id']]=o['rings']
    bad=[k for k in srv if srv[k]['geometry']['rings']!=mine.get(k)]
    print("reach geometry mismatches:",bad,"| not verified:",sorted(set(mine)-set(srv)))
    attrs=json.load(open(P+'reach_attributes.json'))['rows']
    ab=0
    for r in attrs:
        if r[0] not in srv: print('attr not verified',r[0]); continue
        a=srv[r[0]]['attributes']
        exp=[a['channelreachidpk'],a['channelareaidfk'],a['sdsfeaturedescription'],a['sdsfeaturename'],a['mileagestart'],a['mileageend'],a['depthmaintained'],a['widthfrom'],a['widthto']]
        if exp!=r: ab+=1; print("ATTR MISMATCH",r,exp)
    print("attr mismatches",ab)
    print(srv['CESWG_CC_01_SBC_1']['attributes'])
    ls=server_lines()
    print("server lines recovered:",len(ls))
    ml=[]
    for f in sorted(glob.glob(P+'line_p*.json')): ml+=json.load(open(f))
    print("my lines:",len(ml))
    def r5(paths): return [[[round(x,5),round(y,5)] for x,y in p] for p in paths]
    used=set(); lb=0; exact=0
    for o in ml:
        cands=[f for oid,f in ls.items() if f['attributes']['channellineidpk']==o['line_id'] and oid not in used]
        ok=False
        for c in cands:
            rp=r5(c['geometry']['paths'])
            if len(rp)==len(o['paths']) and all(len(a)==len(b) and all(abs(p[0]-q[0])<1.5e-5 and abs(p[1]-q[1])<1.5e-5 for p,q in zip(a,b)) for a,b in zip(rp,o['paths'])):
                ok=True; used.add(c['attributes']['OBJECTID']); exact+= (rp==o['paths']); break
        if not ok: lb+=1; print("LINE NOT VERIFIED",o['line_id'],len(cands))
    print("lines verified:",len(ml)-lb,"exact after rounding:",exact,"| server lines unused:",[ls[i]['attributes']['channellineidpk'] for i in ls if i not in used])
