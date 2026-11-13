#!/usr/bin/env python3
"""Cache windows security/system events as dict lists in /tmp/c/winsec.pkl, /tmp/c/winsys.pkl, endpoint minimal in /tmp/c/ep_<type>.pkl"""
import json,glob,pickle,os,sys
if not os.path.exists('/tmp/c/winsec.pkl'):
    R=[]
    for f in sorted(glob.glob('windows/security_*.jsonl')):
        for line in open(f,encoding='utf-8'):
            d=json.loads(line); d.pop('channel',None); d.pop('provider',None); d.pop('level',None); R.append(d)
    pickle.dump(R,open('/tmp/c/winsec.pkl','wb')); print('sec',len(R))
if not os.path.exists('/tmp/c/winsys.pkl'):
    R=[]
    for c in ('system','defender'):
        for f in sorted(glob.glob(f'windows/{c}_*.jsonl')):
            for line in open(f,encoding='utf-8'):
                d=json.loads(line); R.append(d)
    pickle.dump(R,open('/tmp/c/winsys.pkl','wb')); print('sys+def',len(R))
