import json,glob,re,os
ROOT="./"
def stories():
    out=[]
    for f in sorted(glob.glob(ROOT+"03_news/stories/batch-*.json")):
        d=json.load(open(f))
        if isinstance(d,dict): d=d.get('stories',d)
        for s in d:
            s['_file']=os.path.basename(f); out.append(s)
    return out
def text(s):
    b=s.get('body') or []
    if isinstance(b,str): b=[b]
    return "\n".join([s.get('headline','') or '', s.get('dek','') or '']+b)
def sents(s):
    t=text(s)
    return [x.strip() for x in re.split(r'(?<=[.!?”"])\s+|\n',t) if x.strip()]
def facts():
    d=json.load(open(ROOT+"02_public_record/public_record.json"))
    return d
def tkey(s):
    return (s.get('day'), s.get('time_local') or '')
