import json,re,sys
def load(path):
    """Return (url, features_complete, truncated_flag, meta). Works on truncated esri json."""
    t=open(path,encoding='utf-8').read()
    url=t.split('\n',1)[0]
    i=t.index('\n{')+1
    body=t[i:]
    try:
        d=json.loads(body)
        return url,d.get('features',[]),False,d
    except Exception:
        pass
    import re as _re
    m=_re.search(r"\"features\"\s*:\s*\[\s*",body); j=m.end()
    dec=json.JSONDecoder()
    feats=[]
    pos=j
    while True:
        try:
            obj,end=dec.raw_decode(body,pos)
        except Exception:
            break
        feats.append(obj)
        pos=end
        m2=_re.match(r'\s*,\s*',body[pos:])
        if m2: pos+=m2.end()
        else: break
    return url,feats,True,None
if __name__=='__main__':
    for p in sys.argv[1:]:
        url,feats,trunc,_=load(p)
        tot=0
        print(url); print('features',len(feats),'truncated',trunc)
        for f in feats:
            g=f.get('geometry')
            n=sum(len(r) for r in g['rings']) if g else 0
            tot+=n
            if n>80: print(' ',f['attributes'],len(g['rings']),n)
        print('total verts',tot)
