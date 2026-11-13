#!/usr/bin/env python3
"""Independent audit 3 (utility IT/security logs): named reproduction checks.
usage: checks.py <name> [...]   |   checks.py list
Run build_cache.sh first. Read-only on the data."""
import sys, csv, json, glob, collections, datetime, calendar, re, os

R = "./"
B = R + "05_other_sources/network_logs/"
C = collections.Counter


def ep(s):
    return calendar.timegm(datetime.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S').timetuple())


def conn():
    for l in open('/tmp/z_conn.tsv'):
        yield l.rstrip('\n').split('\t')


def siem():
    for f in sorted(glob.glob(B + 'siem/siem_alerts_*.csv')):
        yield from csv.DictReader(open(f, newline=''))


def reg():
    return json.load(open(R + '06_data_streams/gw_host_registry.json'))


def table(n):
    return list(csv.DictReader(open(B + 'audit/' + n + '.csv', newline='')))


def zeek_ts_round():
    "conn.log rows whose ts has no sub-second part"
    x = [f for f in conn() if f[0].endswith('.000000')]
    print(len(x), 'rows;', C((f[2], f[5]) for f in x).most_common(14))
    print('of which with duration ending 00000:', sum(f[8].endswith('00000') for f in x))


def ssl_cipher():
    "ssl.log cipher census; who uses TLS_AES_256_GCM_SHA384"
    c = C(); d = C()
    for l in open('/tmp/z_ssl.tsv'):
        f = l.split('\t'); c[(f[6], f[7])] += 1
        if f[7] == 'TLS_AES_256_GCM_SHA384':
            d[(f[2], f[4], f[8])] += 1
    print(c.most_common()); print(d)


def ssl_missing():
    "conn rows with service=ssl that have no ssl.log row"
    u = {l.split('\t')[1] for l in open('/tmp/z_ssl.tsv')}; a = b = 0
    for f in conn():
        if f[7] == 'ssl':
            a += 1; b += f[1] not in u
    print('service=ssl conn rows', a, 'without ssl.log row', b)


def conn_constants():
    "constant DNS flow size/duration; S0 with responder packets; protocol mix"
    d = C(); s0 = C(); pm = C(); hist = C()
    for f in conn():
        pm[(f[6], f[5], f[7])] += 1; hist[f[15]] += 1
        if f[7] == 'dns':
            d[(f[8], f[9], f[10], f[16], f[18])] += 1
        if f[11] == 'S0':
            s0[(f[8], f[16], f[18])] += 1
    print('dns (duration,orig_bytes,resp_bytes,orig_pkts,resp_pkts):', d.most_common(3), 'distinct', len(d))
    print('S0 (duration,orig_pkts,resp_pkts):', s0.most_common(3))
    print('distinct proto/port/service', len(pm), '; history strings', hist.most_common())


def top_pair():
    "most frequent (internal source, internet destination) pair in conn.log; per-host volume"
    p = C()
    for f in conn():
        if f[11] in ('S0', 'REJ'):
            continue
        if f[2].startswith('10.') and not f[4].startswith('10.') and not f[4].startswith('172.20.'):
            p[(f[2], f[4])] += 1
    print(p.most_common(4)); per = C()
    for (s, d), v in p.items():
        per[s] += v
    v = sorted(per[k] for k in per if k.startswith('10.14.2') or k.startswith('10.14.30.'))
    print('internet flows per workstation over the span: median', v[len(v) // 2], '; GW-WS-IT-04', per['10.14.22.47'])


def ras_bytes():
    "remote_access_sessions vs the Zeek flow to the gateway: bytes and timestamp form"
    cf = collections.defaultdict(list)
    for f in conn():
        if f[4] == '10.72.4.88' and f[5] == '443':
            cf[f[2]].append(f)
    st = C()
    rows = table('remote_access_sessions')
    for r in rows:
        k = 'non-US' if r['src_country'] != 'US' else 'US'
        c = [f for f in cf.get(r['src_ip'], []) if abs(float(f[0]) - ep(r['login_utc'])) <= 5]
        if not c:
            st[(k, 'no flow')] += 1; continue
        f = c[0]; st[(k, 'sessions')] += 1
        st[(k, 'bytes_in == orig_bytes')] += r['bytes_in'] == f[9]
        st[(k, 'bytes_out == resp_bytes')] += r['bytes_out'] == f[10]
        st[(k, 'zeek ts whole second')] += f[0].endswith('.000000')
        st[(k, 'orig_bytes multiple of 100')] += int(f[9]) % 100 == 0
    for k, v in sorted(st.items()):
        print(k, v)
    print('src_country', C(r['src_country'] for r in rows))


def hist_join():
    "HISTORIAN_BULK_QUERY alerts vs historian_access; historian_access vs Zeek; round durations; rare tag groups"
    h = table('historian_access'); key = C((x['account'], x['tags_queried'], x['duration_s']) for x in h); n = m = 0
    for r in siem():
        if r['rule_id'] == 'SE3-OT-1104':
            n += 1; d = dict(x.split('=') for x in r['detail'].split())
            m += (r['user'], d['tags_queried'], d['session_duration'].rstrip('s')) in key
    print('SE3-OT-1104 alerts', n, 'matching a historian_access row on account+tags+duration', m)
    ip = {x['hostname']: x['ip'] for x in reg()['hosts']}; idx = collections.defaultdict(list)
    for f in conn():
        if f[4] == '10.72.1.10':
            idx[f[2]].append(float(f[0]))
    print('historian_access rows', len(h), 'with a Zeek flow client->historian within 5 s of start',
          sum(any(abs(t - ep(x['start_utc'])) <= 5 for t in idx.get(ip.get(x['client_host']), [])) for x in h))
    fo = [x for x in h if 'fieldops' in x['account'] and x['start_utc'] >= '2027-09-07']
    print('round-minute durations: the 14 story sessions', sum(int(x['duration_s']) % 60 == 0 for x in fo), 'of', len(fo),
          '; all others', sum(int(x['duration_s']) % 60 == 0 for x in h if x not in fo), 'of', len(h) - len(fo))
    tg = C(x['tag_groups'] for x in h); print('tag_groups used <=2 times:', [(k, v) for k, v in tg.items() if v <= 2])
    print('service account x client host', sorted(C((x['account'], x['client_host']) for x in h if x['account'].startswith('svc')).items()))


def supp_counts():
    "alarm suppression: audit table vs SIEM alert counts"
    s = table('alarm_suppression_audit')
    print('audit rows', len(s), C((r['changed_by'], r['source_host'], r['action']) for r in s).most_common())
    print('audit rows by month', sorted(C(r['time_utc'][:7] for r in s).items()))
    ts = sorted(ep(r['time_utc']) for r in s); n = m = 0; v = collections.defaultdict(list)
    for r in siem():
        if r['rule_id'] == 'SE3-OT-3301':
            n += 1; t = ep(r['time_utc']); m += any(abs(t - x) <= 120 for x in ts)
            v[r['time_utc'][:7]].append(int(re.search(r'suppressed_alarm_count=(\d+)', r['detail']).group(1)))
    print('SE3-OT-3301 alerts', n, 'with an audit row within 120 s', m)
    for k in sorted(v):
        print(' ', k, 'alerts', len(v[k]), 'reported suppressed_alarm_count min/max', min(v[k]), max(v[k]))


def exception_scope():
    "who is auto-acknowledged by MAINT-EXCEPT-0892 / WL-NET-0117; rare close notes; priorities"
    c = C(); n = C(); p = C()
    for r in siem():
        n[r['close_note']] += 1; p[r['priority']] += 1
        if r['rule_id'] == 'SE3-OT-1104' and r['src_host'] == 'GW-SYS-JMP-01' and '2027-08-19T11:34:20Z' <= r['time_utc'] < '2027-10-18T15:20:00Z':
            c[('SE3-OT-1104 from JMP while exception active', r['disposition'], 'svc_fieldops_ext' in r['user'])] += 1
        if r['rule_id'] == 'SE3-NET-9941':
            c[('SE3-NET-9941', r['disposition'], 'dst is 104.21.88.43' if r['dst_ip'] == '104.21.88.43' else 'other dst')] += 1
    for k, v in sorted(c.items(), key=str):
        print(k, v)
    print('close notes used <50 times:', [(k, v) for k, v in n.items() if v < 50]); print('priority', p)


def isolation():
    "activity across the IT/OT boundary during 2027-10-12T12:00Z..2027-10-19T18:00Z"
    A, Z = '2027-10-12T12:00', '2027-10-19T18:00'
    print('OT-FW allow rows in window', sum(1 for r in csv.reader(open('/tmp/fw.csv')) if r[1] == 'GW-OT-FW-01' and r[2] == 'allow' and A <= r[0] < Z))
    print('remote sessions in window', sum(1 for r in table('remote_access_sessions') if A <= r['login_utc'] < Z))
    print('historian_access in window by client', C(r['client_host'] for r in table('historian_access') if A <= r['start_utc'] < Z))
    print('ot_config_changes in window', [(r['time_utc'], r['device'], r['change_type'], r['source_host']) for r in table('ot_config_changes') if A <= r['time_utc'] < Z])


def freeze():
    "OT changes after the change freeze of 2027-09-10T21:00Z"
    print([list(r.values()) for r in table('change_management') if 'freeze' in r['record_type'].lower()])
    x = [r for r in table('ot_config_changes') if '2027-09-10T21:00' <= r['time_utc'] < '2027-10-12']
    print(len(x), 'ot_config_changes before the isolation;', sum(1 for r in x if r['change_ticket'].startswith('CHG')), 'with an approved CHG ticket')
    print(sum(1 for r in table('change_management') if '2027-09-10T21:00' < r['time_utc'] < '2027-10-12' and r['record_type'] == 'Approved change'), 'approved changes recorded in change_management')
    dev = C((r['device'], r['parameter']) for r in table('ot_config_changes'))
    print('parameter/device pairs that make no sense:', [(k, v) for k, v in dev.items() if ('WTP' in k[0] and 'relay' in k[1]) or ('RTU-0' in k[0] and ('booster' in k[1] or 'discharge' in k[1])) or ('WTR' in k[0] and ('relay' in k[1] or 'LTC' in k[1]))])


def scada_ops():
    "who issues SCADA commands"
    U = {u['username']: u for u in reg()['users']}; rows = table('scada_command_log'); ops = {r['operator'] for r in rows if r['operator']}
    print('commands', len(rows), 'operators', len(ops), 'without an OT account', sum(1 for o in ops if 'ot_account' not in U.get(o, {})))
    print(C(U[r['operator']]['department'] for r in rows if r['operator'] in U).most_common())
    print('remote desktop commands with empty operator', sum(1 for r in rows if r['origin'] == 'remote desktop' and not r['operator']), 'of', sum(1 for r in rows if r['origin'] == 'remote desktop'))
    print(C((r['command'], r['device']) for r in rows if ('TAP' in r['command'] or 'CAP' in r['command']) and '-CB-' in r['device']).most_common(3))


def registry_flags():
    "reference_only claims in gw_host_registry.json vs the logs"
    g = reg(); ru = {u['username'] for u in g['users'] if u.get('reference_only')}; rh = {h['hostname'] for h in g['hosts'] if h.get('reference_only')}
    rs = {s['account'] for s in g['service_accounts'] if s.get('reference_only')}
    su = set(); sh = C()
    for r in siem():
        su.add(r['user'].split('\\')[-1])
        for h in (r['src_host'], r['dst_host']):
            if h in rh:
                sh[h] += 1
    print('reference_only users named in alerts', len(ru & su), 'of', len(ru)); print('reference_only hosts named in alerts', dict(sh))
    print('reference_only service accounts with remote sessions', C(r['account'] for r in table('remote_access_sessions') if r['account'] in rs),
          'historian sessions', C(r['account'].split('\\')[-1] for r in table('historian_access') if r['account'].split('\\')[-1] in rs))
    print('public_address_block', g['metadata']['public_address_block'], '; counts.equipment', g['metadata']['counts']['equipment'], 'actual', len(g['equipment']))


def dup_logons():
    "4624 events sharing host+logon_id"
    c = C()
    for f in sorted(glob.glob(B + 'windows/security_*.jsonl')):
        s = C()
        for l in open(f):
            if '"event_id":4624' in l:
                d = json.loads(l); s[(d['host'], d['logon_id'])] += 1
        c['logon ids'] += len(s); c['with >1 4624'] += sum(v > 1 for v in s.values()); c['surplus 4624'] += sum(v - 1 for v in s.values())
    print(dict(c))


def win_counts():
    "event-id census of the Security channel, 5145 access types, key order of 4624"
    c = C(); a = C(); ko = C()
    for f in sorted(glob.glob(B + 'windows/security_*.jsonl')):
        for l in open(f):
            m = re.search(r'"event_id":(\d+)', l); c[m.group(1)] += 1
            if m.group(1) == '5145':
                d = json.loads(l); a[(d['host'], d['access'], 'from 10.14.22.47' if d['src_ip'] == '10.14.22.47' else 'other')] += 1
            if m.group(1) == '4624':
                ko[l.index('"logon_type"') < l.index('"logon_id"')] += 1
    print(sorted(c.items())); print(a); print('4624 with logon_type before logon_id', ko)


def usb_serials():
    "USB devices: serial reuse"
    s = C()
    for f in sorted(glob.glob(B + 'endpoint/endpoint_*.jsonl')):
        for l in open(f):
            if '"usb_device"' in l:
                s[json.loads(l)['device_serial']] += 1
    print('usb events', sum(s.values()), 'distinct serials', len(s))


def triage_future():
    "triage file listings dated after the collection"
    t = 0
    for h in sorted(os.listdir(B + 'triage')):
        col = json.load(open(B + f'triage/{h}/collection.json'))['collected_utc']; rows = list(csv.DictReader(open(B + f'triage/{h}/file_listing.csv')))
        fut = [r for r in rows if r['modified_utc'] > col or r['created_utc'] > col]; t += len(fut)
        if fut:
            print(h, col, len(fut), 'of', len(rows), 'latest', max(max(r['modified_utc'], r['created_utc']) for r in fut))
    print('total', t)


def mail_unique():
    "utility mail gateway: values that occur once"
    m = table('mail_gateway_cbpwa')
    for c in ('subject', 'sender_domain'):
        k = C(r[c] for r in m); print(c, len(k), 'used once:', [x for x, v in k.items() if v == 1])
    print('attachments ending .exe', [r['attachment_names'] for r in m if r['attachment_names'].lower().endswith('.exe')])
    print('message_id not ending @mail>', sum(1 for r in m if not r['message_id'].endswith('@mail>')))
    print('verdict', C(r['verdict'] for r in m)); print('sender domains not under .example', sum(1 for d in {r['sender_domain'] for r in m} if not d.endswith('.example')))
    print('internal senders that are registry usernames', sum(1 for r in m if r['direction'] == 'internal' and not re.match(r'^[0-9a-f]{6,7}@', r['sender'])), 'of', sum(1 for r in m if r['direction'] == 'internal'))


def reserved_ips():
    "internet-side addresses in reserved ranges (conn.log)"
    import ipaddress
    nets = [ipaddress.ip_network(x) for x in ('127.0.0.0/8', '169.254.0.0/16', '192.0.2.0/24', '192.168.0.0/16', '198.18.0.0/15', '198.51.100.0/24', '203.0.113.0/24', '100.64.0.0/10', '172.16.0.0/12')]
    c = C(); cache = {}
    for f in conn():
        for ipx in (f[2], f[4]):
            if ipx.startswith('10.') or ipx.startswith('172.20.5.'):
                continue
            if ipx not in cache:
                a = ipaddress.ip_address(ipx); cache[ipx] = next((str(n) for n in nets if a in n), None)
            if cache[ipx]:
                c[cache[ipx]] += 1
    print(c)


def proxy_dns_offset():
    "web-filter dns rows vs Zeek dns.log"
    d = collections.defaultdict(list)
    for l in open('/tmp/z_dns.tsv'):
        f = l.split('\t'); d[(f[2], f[8])].append(float(f[0]))
    st = C(); o = []
    for r in csv.reader(open('/tmp/px.csv')):
        if r[4] != 'dns':
            continue
        ts = d.get((r[1], r[5]))
        if not ts:
            st['no dns.log row for client+name'] += 1; continue
        x = min(ts, key=lambda t: abs(t - ep(r[0]))) - ep(r[0]); o.append(x); st['within 2 s' if abs(x) <= 2 else 'time differs >2 s'] += 1
    o.sort(); print(st, 'offset min/median/max', round(o[0]), round(o[len(o) // 2], 1), round(o[-1]))


def storm_hourly():
    "hourly SIEM alert counts around landfall and per-rule storm multipliers"
    c = C(); rr = collections.defaultdict(C)
    for r in csv.DictReader(open(B + 'siem/siem_alerts_2027-09.csv')):
        c[r['time_utc'][:13]] += 1; rr[r['rule_name']][r['time_utc'][:10]] += 1
    for d in ('2027-09-11', '2027-09-12', '2027-09-13', '2027-09-14', '2027-09-15'):
        print(d, [c[f'{d}T{h:02d}'] for h in range(24)])
    for k in ('POLICY_BLOCKED_SITE', 'LOGON_OUTSIDE_HOURS', 'PUP_DETECTED', 'USB_STORAGE_MOUNTED', 'FAILED_LOGON_BURST', 'ADMIN_GROUP_CHANGE', 'UPS_ON_BATTERY'):
        print(k, '09-08:', rr[k]['2027-09-08'], '09-14:', rr[k]['2027-09-14'], '09-17:', rr[k]['2027-09-17'])


def siem_analysts():
    "analyst working pattern"
    d = collections.defaultdict(set); h = collections.defaultdict(C)
    for r in siem():
        if r['closed_by'] not in ('system', '') and r['disposition'] != 'STORM_BULK_DISMISSED':
            d[r['closed_by']].add(r['closed_utc'][:10]); h[r['closed_by']][r['closed_utc'][11:13]] += 1
    for a in d:
        print(a, 'days with closures', len(d[a]), 'hours of day used', len(h[a]), 'closures per hour-of-day min/max', min(h[a].values()), max(h[a].values()))


def dhcp_vpn():
    "employee VPN pool: sessions and MAC addresses"
    rows = list(csv.reader(open('/tmp/dhcp.csv')))
    a = [r for r in rows if r[6] == 'corp-vpn' and r[2] == 'ASSIGN']
    print('vpn sessions', len(a), 'with hostname', sum(1 for r in a if r[5]), '; distinct MACs among sessions without hostname', len({r[4] for r in a if not r[5]}), '; MAC first octets', C(r[4][:2] for r in rows))


def fim_seconds():
    "file_integrity.csv timestamp resolution and hash format"
    f = table('file_integrity')
    print('rows', len(f), 'with seconds != 00:', [(r['time_utc'], r['user'], r['path']) for r in f if r['time_utc'][17:19] != '00'])
    print('hash lengths (hex chars)', C(len(r['new_hash'].split('=')[1]) for r in f))


def names():
    "code names and real-world names"
    import subprocess
    for w in ('gridwater', 'kestrel'):
        n = subprocess.run(['grep', '-rli', w, B + 'siem', B + 'audit', B + 'triage', B + 'firewall', B + 'proxy', B + 'dhcp', R + '11_hackathon/DATA_GUIDE.md',
                            R + '06_data_streams/gw_host_registry.json', R + '06_data_streams/_internal/guide_itsec_net.md', R + '06_data_streams/_internal/guide_itsec_host.md'],
                           capture_output=True, text=True).stdout
        print(w, 'files:', n.strip() or 'none')
    g = reg(); print(C(h['vendor'] for h in g['hosts']).most_common(6))
    print([s['account'] for s in g['service_accounts'] if re.search('maximo|sccm|wsus', s['account'])], [s['name'] for s in g['sites'] if 'Stevens' in s['name'] or 'Texana' in s['name']])
    print('remote-session networks', C(r['src_network'] for r in table('remote_access_sessions')))
    t = C()
    for l in open('/tmp/z_dns.tsv'):
        t[l.split('\t')[8].rsplit('.', 1)[-1]] += 1
    print('dns.log TLDs', t.most_common())


if __name__ == '__main__':
    skip = ('conn', 'siem', 'reg', 'table', 'ep')
    fs = {k: v for k, v in list(globals().items()) if callable(v) and getattr(v, '__doc__', None) and k not in skip and k[0].islower() and v.__module__ == '__main__'}
    if len(sys.argv) < 2 or sys.argv[1] == 'list':
        for k, v in fs.items():
            print(f'{k:18s}', v.__doc__)
    else:
        for n in sys.argv[1:]:
            print('==', n, '-', fs[n].__doc__); fs[n]()
