"""Areas 9/10: leftover ids and answer-revealing tokens anywhere in the delivered files (byte scan, one pass per file)."""
import os, re, sys, collections, time
from common import *
PAT=[b'FAC-CCMC',b'7c1234',b'Auriga',b'Pier 9',b'GridWater',b'Halcyon Drift',b'KESTREL',b'ClearPath',b'Barge 44',b'PHANTOM',b'phase_label',b'AttackSig',b'truth_event',b'ground_truth',b'is_attack',b'is_fraud',b'is_bot',b'malicious',b'attacker',b'adversary',b'threat actor',b'scenario',b'MSEL',b'inject',b'synthetic',b'STATE-X',b'UAS-SYN',b'JAM-01',b'DEV-0[12]',b'18210[2-9][0-9]{4}',b'\\bT(8|9|1[0-9]|2[0-2])\\b',b'\\bD[+-][0-9]{1,3}\\b',b'\\bEVT-[0-9]{4}',b'\\bPUB-[0-9]{3}',b'Valero',b'Citgo',b'Flint Hills',b'Caller-Times',b'\\bKIII\\b',b'\\bKRIS\\b',b'Spohn',b'Driscoll',b'hostile',b'covert',b'exfil',b'C2\\b',b'beacon']
rx=re.compile(b'|'.join(b'(%s)'%p for p in PAT))
dirs=sys.argv[1:]; t0=time.time()
cnt=collections.Counter(); ex={}
for d in dirs:
    for root,_,files in os.walk(os.path.join(SRC,d)):
        for fn in files:
            p=os.path.join(root,fn)
            try: data=open(p,'rb').read()
            except Exception as e: print('ERR',p,e); continue
            for m in rx.finditer(data):
                k=(PAT[m.lastindex-1].decode(), os.path.relpath(root,SRC) if 'zeek' in root or 'satellite' in root or 'social' in root else os.path.relpath(p,SRC))
                cnt[k]+=1
                if k not in ex:
                    s=max(0,m.start()-70); ex[k]=data[s:m.end()+70].decode('utf-8','replace').replace('\n',' | ')
for k,v in sorted(cnt.items()):
    print(v,k,'::',ex[k][:170])
print('done',dirs,round(time.time()-t0),'s')
