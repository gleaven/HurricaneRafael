#!/usr/bin/env python3
"""Pass 2: every record naming rvela / GW-ENG-VELA / Vela's hosts inside the leave window 2027-09-06T22:00Z..2027-09-22T06:00Z, by log."""
import csv,json,glob,collections,re
B="./05_other_sources/network_logs/"
A,Z="2027-09-06T22:00","2027-09-22T06:00"
pat=re.compile(r'rvela|GW-ENG-VELA',re.I)
out=collections.defaultdict(list)
for f in sorted(glob.glob(B+"windows/*_2027-09*.jsonl"))+sorted(glob.glob(B+"endpoint/endpoint_2027-09.jsonl")):
    for l in open(f):
        if pat.search(l):
            d=json.loads(l)
            if A<=d['time_utc']<Z:
                key=(f.split('/')[-1].split('_')[0], d.get('event_id',d.get('event_type')), d['host'], d.get('user'), d.get('target_user'), d.get('logon_type'), d.get('src_ip'), d.get('caller_computer'))
                out[key].append(d['time_utc'])
for k,v in sorted(out.items(),key=lambda x:str(x)): print(len(v),k,v[0],v[-1])
for f in ['audit/remote_access_sessions.csv','audit/historian_access.csv','audit/ot_config_changes.csv','audit/scada_command_log.csv','audit/alarm_suppression_audit.csv','audit/file_integrity.csv','audit/change_management.csv','audit/mail_gateway_cbpwa.csv','audit/endpoint_protection.csv','proxy/web_proxy_2027-09.csv','siem/siem_alerts_2027-09.csv']:
    n=collections.Counter()
    for l in open(B+f):
        if pat.search(l):
            m=re.search(r'2027-\d\d-\d\dT\d\d:\d\d',l)
            if m and A<=m.group(0)<Z: n[m.group(0)[:10]]+=1
    print(f,sum(n.values()),sorted(n.items()))
