#!/usr/bin/env python3
"""Ingest saved web_fetch results (TIGERweb layer 8, whole-area paging by resultOffset).

Each web_fetch response larger than ~50k chars is saved by the harness to TOOLDIR and truncated
at ~63-67k chars. This script finds those files (first line = request URL), keeps only the
features that are complete before the cut, and stores them as _parts/streets_page_<offset>.json.
Index of a feature in the server's (default, OBJECTID) order = resultOffset + position in page.
Overlapping pages are cross-checked (same index -> same OID). Prints the coverage / next offset.
"""
import json, os, re, sys, glob
TOOLDIR = './_scratch/fetch'
HERE = os.path.dirname(os.path.abspath(__file__))
TOTAL = 12786  # returnCountOnly for the area box, 2026-11-10
PAT = re.compile(r'MapServer/8/query\?geometry=-97\.7,27\.55,-96\.98,28\.08&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=3e-5&resultOffset=(\d+)&f=json')

def parse(body):
    k = body.find('"features":[')
    if k < 0: return None, False
    pos = k + len('"features":[')
    dec = json.JSONDecoder(); feats = []; complete = False
    while True:
        if pos >= len(body): break
        if body[pos] == ']': complete = True; break
        if body[pos] == ',': pos += 1; continue
        try:
            obj, end = dec.raw_decode(body, pos)
        except ValueError:
            break
        # a feature is only trusted if followed by ',' or ']' (i.e. really closed)
        if end >= len(body) or body[end] not in ',]':
            break
        feats.append((obj, end - pos)); pos = end
    return feats, complete

def main():
    done = {int(re.search(r'streets_page_(\d+)\.json', p).group(1)) for p in glob.glob(os.path.join(HERE, 'streets_page_*.json'))}
    for fn in sorted(os.listdir(TOOLDIR)):
        if not fn.startswith('mcp-workspace-web_fetch-'): continue
        p = os.path.join(TOOLDIR, fn)
        with open(p, encoding='utf-8') as f:
            first = f.readline()
            m = PAT.search(first)
            if not m: continue
            off = int(m.group(1))
            if off in done: continue
            rest = f.read()
        body = rest[rest.find('{"displayFieldName"'):]
        feats, complete = parse(body)
        if not feats: print('WARN no features in', fn); continue
        out = {'url': first.strip(), 'offset': off, 'complete_response': complete, 'saved_from': fn,
               'n': len(feats), 'chars': [c for _, c in feats], 'features': [o for o, _ in feats]}
        with open(os.path.join(HERE, 'streets_page_%05d.json' % off), 'w') as g:
            json.dump(out, g, separators=(',', ':'))
        done.add(off)
        print('ingested offset', off, 'n', len(feats), 'complete' if complete else 'cut', fn)
    # coverage
    idx = {}; sizes = {}; bad = 0
    for p in sorted(glob.glob(os.path.join(HERE, 'streets_page_*.json'))):
        d = json.load(open(p))
        for i, ft in enumerate(d['features']):
            k = d['offset'] + i; oid = ft['attributes']['OID']
            if k in idx and idx[k] != oid: bad += 1; print('ORDER MISMATCH at', k, idx[k], oid)
            idx[k] = oid; sizes[k] = d['chars'][i]
    have = sorted(idx)
    gaps = []; prev = -1
    for k in have:
        if k != prev + 1: gaps.append((prev + 1, k - 1))
        prev = k
    if prev < TOTAL - 1: gaps.append((prev + 1, TOTAL - 1))
    print('indices covered', len(have), 'of', TOTAL, '| unique OIDs', len(set(idx.values())), '| order mismatches', bad)
    print('avg chars/feature', round(sum(sizes.values()) / max(1, len(sizes)), 1))
    print('gaps (need resultOffset=start):', gaps[:40])
    json.dump({'total': TOTAL, 'covered': len(have), 'gaps': gaps, 'pages': sorted(done)}, open(os.path.join(HERE, 'streets_progress.json'), 'w'))
    # helper: for a tail gap, suggest an offset so that response is 52-60k chars
    if gaps and gaps[-1][1] == TOTAL - 1 and len(sys.argv) > 1:
        est_tail = float(sys.argv[1])  # estimated chars of unknown tail
        s = gaps[-1][0]; acc = 0; k = s - 1
        while k in sizes and acc + sizes[k] + 1 + est_tail < 56500 - 520:
            acc += sizes[k] + 1; k -= 1
        print('tail: unknown from', s, 'est', est_tail, '-> request offset', k + 1, 'known chars', acc)
main()
