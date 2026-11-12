#!/usr/bin/env python3
"""Index web_fetch result files by URL and leniently parse ArcGIS JSON features."""
import os, re, json, sys, glob
TR = './_scratch/fetch/'
def index():
    out = []
    for f in sorted(glob.glob(TR + 'mcp-workspace-web_fetch-*.txt')):
        with open(f, encoding='utf-8', errors='replace') as fh:
            txt = fh.read()
        first = txt.split('\n', 1)[0].strip()
        out.append((f, first, txt))
    return out
def features(txt):
    """Return (features list, complete flag)."""
    i = txt.find('{')
    body = txt[i:]
    try:
        d = json.loads(body)
        return d.get('features', d.get('results', [])), True, d
    except Exception:
        pass
    m = re.search(r'"(features|results)"\s*:\s*\[', body)
    if not m:
        return [], False, None
    pos = m.end()
    dec = json.JSONDecoder()
    feats = []
    while True:
        while pos < len(body) and body[pos] in ' \r\n\t,':
            pos += 1
        if pos >= len(body) or body[pos] != '{':
            break
        try:
            obj, end = dec.raw_decode(body, pos)
        except Exception:
            break
        feats.append(obj); pos = end
    return feats, False, None
if __name__ == '__main__':
    pat = sys.argv[1] if len(sys.argv) > 1 else ''
    for f, first, txt in index():
        if pat in first:
            fe, comp, _ = features(txt)
            print(os.path.basename(f), len(txt), 'feats=%d complete=%s' % (len(fe), comp), first[:230])
