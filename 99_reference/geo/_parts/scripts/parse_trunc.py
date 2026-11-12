import json,sys,glob
def parse(path):
    t=open(path).read()
    i=t.index('"features":[')+len('"features":[')
    s=t[i:]
    dec=json.JSONDecoder(); feats=[]; pos=0
    while pos<len(s):
        try:
            o,end=dec.raw_decode(s,pos)
        except Exception as e:
            break
        feats.append(o); pos=end
        if pos<len(s) and s[pos]==',': pos+=1
        else: break
    complete = s[pos:pos+2].startswith(']')
    return feats, complete
if __name__=="__main__":
    feats,complete=parse(sys.argv[1])
    print(len(feats),"complete" if complete else "TRUNCATED")
    for f in feats: print(f['attributes'].get('channelreachidpk') or f['attributes'].get('channellineidpk'), f['attributes'].get('OBJECTID'))
