#!/usr/bin/env python3
"""Cache CSV families into /tmp/c/<name>.pkl as (header, rows)."""
import csv,glob,pickle,sys,os
fam={'siem':'siem/siem_alerts_*.csv','fw_edge':'firewall/fw_GW-FW-EDGE-01_*.csv','fw_ot':'firewall/fw_GW-OT-FW-01_*.csv','proxy':'proxy/web_proxy_*.csv','dhcp':'dhcp/dhcp_leases_*.csv'}
for n in sys.argv[1:]:
    out=f'/tmp/c/{n}.pkl'
    if os.path.exists(out): continue
    rows=[];hdr=None
    for f in sorted(glob.glob(fam[n])):
        rd=csv.reader(open(f,newline='',encoding='utf-8')); h=next(rd)
        assert hdr is None or hdr==h,(f,h); hdr=h
        rows+=[tuple(r) for r in rd]
    pickle.dump((hdr,rows),open(out,'wb')); print(n,len(rows))
