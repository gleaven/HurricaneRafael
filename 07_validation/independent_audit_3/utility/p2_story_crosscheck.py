#!/usr/bin/env python3
"""Pass 2: the 14 hostile remote sessions across remote_access_sessions, Zeek conn, both firewalls, Windows 4624/4634 on the gateway, historian_access, SIEM; plus OT changes and SCADA commands by GW-ENG-VELA."""
import csv,json,collections,datetime,glob
R="./"; B=R+"05_other_sources/network_logs/"
P=lambda s: datetime.datetime.strptime(s[:19],'%Y-%m-%dT%H:%M:%S')
U=lambda t: datetime.datetime.utcfromtimestamp(float(t))
ras=[r for r in csv.DictReader(open(B+'audit/remote_access_sessions.csv')) if r['src_country']!='US']
hist=[r for r in csv.DictReader(open(B+'audit/historian_access.csv')) if 'fieldops' in r['account']]
conn=[l.rstrip('\n').split('\t') for l in open('/tmp/z_conn.tsv') if '\t10.72.4.88\t' in l]
fw=[r for r in csv.reader(open('/tmp/fw.csv')) if r[8] in('10.72.4.88','12.186.44.76') or r[6]=='10.72.4.88']
win=[]
for f in glob.glob(B+'windows/security_2027-09.jsonl')+glob.glob(B+'windows/security_2027-10.jsonl'):
    for l in open(f):
        if '"GW-SYS-JMP-01"' in l and 'GW-ENG-VELA' in l: win.append(json.loads(l))
tot_tags=0
for r in ras:
    t0=P(r['login_utc']); t1=P(r['logout_utc'])
    z=[c for c in conn if c[2]==r['src_ip'] and abs((U(c[0])-t0).total_seconds())<5]
    f1=[x for x in fw if x[6]==r['src_ip'] and x[2]=='allow' and abs((P(x[0])-t1).total_seconds())<5]
    w=[d for d in win if d['event_id']==4624 and d.get('src_ip')==r['src_ip'] and abs((P(d['time_utc'])-t0).total_seconds())<5]
    h=[x for x in hist if t0<=P(x['start_utc'])<=t1]
    for x in h: tot_tags+=int(x['tags_queried'])
    zz=z[0] if z else None
    print(r['session_id'],r['login_utc'],r['duration_s'],'RAS out/in',r['bytes_out'],r['bytes_in'],'| zeek',len(z),(zz[8],'orig',zz[9],'resp',zz[10],zz[11]) if zz else None,'| fw',[(x[1][3:8],x[12],x[13],x[14]) for x in f1],'| 4624',len(w),'| hist',[(x['session_id'],x['duration_s'],x['tags_queried']) for x in h])
print('historian sessions svc_fieldops_ext total',len(hist),'tags in the 14 windows',tot_tags)
print('historian svc_fieldops_ext sessions outside the 14 windows:',[(x['session_id'],x['start_utc'],x['tags_queried'],x['query_type']) for x in hist if not any(P(r['login_utc'])<=P(x['start_utc'])<=P(r['logout_utc']) for r in ras)][:30])
print('--- ot_config_changes by GW-ENG-VELA')
for r in csv.DictReader(open(B+'audit/ot_config_changes.csv')):
    if r['session_user']=='GW-ENG-VELA' or r['change_ticket'] in('','SI-2027-CC-001'): print(list(r.values()))
print('--- scada commands via remote desktop, Sep 20-25 and by rvela')
for r in csv.DictReader(open(B+'audit/scada_command_log.csv')):
    if ('2027-09-21'<=r['time_utc'][:10]<='2027-09-24' and r['origin']!='console') or 'vela' in r['operator'].lower(): print(list(r.values()))
print('--- file_integrity rows with diff or by VELA on 09-11')
for r in csv.DictReader(open(B+'audit/file_integrity.csv')):
    if r['user']=='GW-ENG-VELA' and r['time_utc'][:7]=='2027-09': print(list(r.values()))
