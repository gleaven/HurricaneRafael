"""Stream descriptions and probes for the raw network logs of the utility: firewall_logs, web_proxy_logs,
dhcp_logs, packet_captures (see scripts/check_streams.py). Every probe reads the files on disk and compares
them with the delivered Zeek logs and SIEM alerts.

    python3 scripts/streams/probes_itsec_net.py [stream ...]     run every probe of this family and print the result

Two kinds of probe key:
  ("GW-EVT-...", stream)   a scenario event as it shows in that stream
  ("INV-...", stream)      an invariant of the stream measured over every day (completeness against Zeek,
                           alert backing, isolation, registry addresses, neutral treatment of every flow)
"""
import csv
import glob
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import itsec_net_lib as L      # noqa: E402
import itsec_shared as S       # noqa: E402
from common import ROOT        # noqa: E402

G = S.G
NETDIR = os.path.join(ROOT, "05_other_sources", "network_logs")
_c = {}
DAYS = range(S.FIRST_DAY, S.LAST_DAY + 1)
WS04_IP, JMP_IP = S.IP[G.WS04], S.IP[G.JMP]


def _csv(pattern):
    if pattern not in _c:
        out = []
        for fp in sorted(glob.glob(os.path.join(NETDIR, pattern))):
            with open(fp, newline="", encoding="utf-8") as fh:
                out += list(csv.DictReader(fh))
        _c[pattern] = out
    return _c[pattern]


def fw():
    return _csv("firewall/fw_*.csv")


def proxy():
    return _csv("proxy/web_proxy_*.csv")


def dhcp():
    return _csv("dhcp/dhcp_leases_*.csv")


def siem():
    return _csv("siem/siem_alerts_*.csv")


def conn_all():
    """Every delivered conn row with the devices it crosses: list of (row, devices, src zone, dst zone)."""
    if "conn" not in _c:
        out = []
        for d in DAYS:
            for r in S.zeek_day(d, "conn"):
                devs, zo, zr = L.crossings(r)
                if devs:
                    out.append((r, devs, zo, zr, d))
        _c["conn"] = out
    return _c["conn"]


def _t(iso):
    return S.ts(iso)


def _dur(r):
    return float(r["duration"]) if r["duration"] not in ("-", "") else 0.0


# ---------------------------------------------------------------------------------------- firewall
def _fw_key(dev, src, sp, dst, dp, proto, end_iso, sent, recv):
    return (dev, src, str(sp), dst, str(dp), proto, end_iso, str(sent), str(recv))


def inv_fw_complete():
    want = {}
    for r, devs, zo, zr, d in conn_all():
        for dev in devs:
            act = L.fw_action(dev, zo, zr, r)[0]
            sent, recv = L.ip_bytes(r)
            icmp = r["proto"] == "icmp"
            k = _fw_key(dev, r["id.orig_h"], 0 if icmp else r["id.orig_p"], r["id.resp_h"], 0 if icmp else r["id.resp_p"], r["proto"], G.z(int(float(r["ts"]) + _dur(r))), sent,
                        0 if act == "deny" else recv) + (act,)
            want[k] = want.get(k, 0) + 1
    have, other_deny = {}, 0
    for x in fw():
        k = _fw_key(x["device"], x["src_ip"], x["src_port"], x["dst_ip"], x["dst_port"], x["proto"], x["time_utc"], x["bytes_sent"], x["bytes_recv"]) + (x["action"],)
        if x["action"] == "deny" and k not in want:
            other_deny += 1                                # internet noise and isolation retries: the devices' own records
            continue
        have[k] = have.get(k, 0) + 1
    missing = [k for k, n in want.items() if have.get(k, 0) < n]
    extra = [k for k, n in have.items() if want.get(k, 0) < n]
    ok = not missing and not extra
    return ok, (f"{sum(want.values()):,} crossings of the two firewalls in the Zeek logs, {sum(have.values()):,} matching records ({other_deny:,} further denies have no flow, as expected); "
                f"flows without a record {len(missing)}, allows without a flow {len(extra)}" + (f"; e.g. missing {missing[:2]} extra {extra[:2]}" if not ok else ""))


def inv_fw_isolation():
    bad = []
    n_deny = 0
    for x in fw():
        if x["device"] != L.OTFW:
            continue
        start = _t(x["time_utc"]) - float(x["duration_s"] or 0)
        if not G.boundary_open(start) and not G.boundary_open(_t(x["time_utc"])):
            if x["action"] == "allow":
                bad.append((x["time_utc"], x["src_ip"], x["dst_ip"], x["dst_port"]))
            else:
                n_deny += 1
    return not bad and n_deny > 500, f"{n_deny:,} denies and {len(bad)} allows on the IT/OT boundary while the control network was isolated" + (f": {bad[:4]}" if bad else "")


def _fw_find(dev, src, dst, dport, t0, t1, sport=None):
    return [x for x in fw() if x["device"] == dev and x["src_ip"] == src and x["dst_ip"] == dst and x["dst_port"] == str(dport)
            and t0 <= _t(x["time_utc"]) <= t1 and (sport is None or x["src_port"] == str(sport))]


def _conn_find(d, o, r, rp, pred=lambda x: True):
    return [x for x in S.zeek_day(d, "conn") if x["id.orig_h"] == o and x["id.resp_h"] == r and x["id.resp_p"] == str(rp) and pred(x)]


def _fw_of(dev, c):
    """Firewall records of one delivered conn row on a device."""
    end = float(c["ts"]) + _dur(c)
    return [x for x in _fw_find(dev, c["id.orig_h"], c["id.resp_h"], c["id.resp_p"], end - 1.5, end + 1.5, sport=c["id.orig_p"])]


def story_conns():
    """The delivered conn rows of the scenario's own flows: the download and the periodic connection of the one
    workstation, its transfer from the historian replica, the fourteen out-of-hours gateway sessions and what the
    gateway opened inside the control network during them. Used to find them in the derived logs and to test
    that those logs treat them like any other flow."""
    if "story" not in _c:
        out = []
        wins = [(s["start"] - 60, s["start"] + s["dur"] + 60, s["ip"]) for s in G.SESSIONS]
        for d in DAYS:
            for r in S.zeek_day(d, "conn"):
                o, rh, t = r["id.orig_h"], r["id.resp_h"], float(r["ts"])
                if (o == WS04_IP and rh == G.BEACON_IP) or (o == WS04_IP and rh == S.IP[G.HISTDMZ] and r["id.resp_p"] == "445" and L.to_int(r["resp_bytes"]) > 1.8e9):
                    out.append(r)
                elif rh == JMP_IP and any(o == ip and a <= t <= a + 120 for a, b, ip in wins):
                    out.append(r)
                elif o == JMP_IP and any(a + 60 <= t <= b - 60 for a, b, ip in wins):
                    out.append(r)
        _c["story"] = out
    return _c["story"]


def _session_conns():
    """One delivered conn row per out-of-hours session: outside address -> gateway, starting at the session's login."""
    out = []
    for s in G.SESSIONS:
        c = [r for r in story_conns() if r["id.orig_h"] == s["ip"] and r["id.resp_h"] == JMP_IP and abs(float(r["ts"]) - s["start"]) <= 120]
        out.append(c[0] if c else None)
    return out


def p_fw_001():
    c = _conn_find(G.day_utc(G.DNS_Q_T), WS04_IP, G.BEACON_IP, 443, lambda x: x["resp_bytes"] == "1884012")
    hit = _fw_of(L.EDGE, c[0]) if c else []
    return bool(hit), (f"edge firewall: allow {WS04_IP} -> {G.BEACON_IP}:443, {hit[0]['bytes_recv']} bytes received (1,884,012 of payload), session ended {hit[0]['time_utc']}, source NAT {hit[0]['nat_src_ip']}"
                       if hit else "no edge record for the 1.88 MB download at 13:23Z on 2027-08-30")


def p_fw_101():
    c = _conn_find(G.day_utc(G.BEACON_FIRST), WS04_IP, G.BEACON_IP, 443, lambda x: abs(float(x["ts"]) - G.BEACON_FIRST) < 5)
    hit = _fw_of(L.EDGE, c[0]) if c else []
    return bool(hit), (f"edge firewall: allow {WS04_IP} -> {G.BEACON_IP}:443 ended {hit[0]['time_utc']}, {hit[0]['bytes_sent']} bytes out, {hit[0]['bytes_recv']} in "
                       f"({c[0]['orig_bytes']} and {c[0]['resp_bytes']} of payload), rule {hit[0]['rule_name']}" if hit else "first outbound connection not in the edge firewall log")


def _sessions_in(dev):
    return sum(1 for c in _session_conns() if c and _fw_of(dev, c))


def p_fw_002():
    e, o = _sessions_in(L.EDGE), _sessions_in(L.OTFW)
    seven = sum(1 for s in G.SESSIONS[:7] if _fw_find(L.OTFW, JMP_IP, S.IP[G.HIST1], 5450, s["start"] - 5, s["start"] + s["dur"] + 1600))
    big = [x for x in fw() if x["device"] == L.OTFW and x["src_ip"] == WS04_IP and x["dst_ip"] == S.IP[G.HISTDMZ] and x["dst_port"] == "445" and int(x["bytes_recv"]) > 1.8e9]
    ok = e == 14 and o == 14 and seven == 7 and bool(big)
    return ok, f"gateway sessions from outside: {e}/14 on the edge firewall, {o}/14 on the IT/OT boundary; gateway-to-historian flows of the first seven: {seven}/7; 1.9 GB SMB flow workstation -> DMZ historian: {'present' if big else 'missing'}"


def p_fw_011():
    e, o = _sessions_in(L.EDGE), _sessions_in(L.OTFW)
    srcs = sorted({s["ip"] for s in G.SESSIONS})
    return e == 14 and o == 14, f"all 14 sessions to the remote-access gateway from {len(srcs)} outside addresses are in both firewall logs ({e}/14 edge, {o}/14 boundary)"


def p_fw_107():
    rows = [x for x in fw() if x["device"] == L.EDGE and x["src_ip"] == WS04_IP and x["dst_ip"] == G.BEACON_IP]
    last = max((_t(x["time_utc"]) for x in rows), default=0)
    after = [x for x in fw() if WS04_IP in (x["src_ip"], x["dst_ip"]) and x["action"] == "allow" and _t(x["time_utc"]) - float(x["duration_s"] or 0) > G.WS04_REMOVED]
    ok = bool(rows) and abs(last - (G.BEACON_LAST + 4)) < 12 and not after
    return ok, f"{len(rows)} allowed connections {WS04_IP} -> {G.BEACON_IP}; the last ends {G.z(int(last)) if rows else '-'}; allowed sessions of that workstation after it was unplugged: {len(after)}"


def _lonely(rows, is_story, cols, floor=20):
    """Values of categorical columns that the story's records carry and fewer than `floor` other records share."""
    seen, story = {}, {}
    for x in rows:
        st = is_story(x)
        for c in cols:
            k = (c, x[c])
            if st:
                story[k] = story.get(k, 0) + 1
            else:
                seen[k] = seen.get(k, 0) + 1
    return {k: (n, seen.get(k, 0)) for k, n in story.items() if seen.get(k, 0) < floor}, sum(1 for x in rows if is_story(x)), len({k for k in story})


def inv_fw_neutral():
    """No value of a categorical column on the story's firewall records is rare among the other records."""
    keys = set()
    for c in story_conns():
        end = G.z(int(float(c["ts"]) + _dur(c)))
        keys.add((c["id.orig_h"], str(c["id.orig_p"]), c["id.resp_h"], str(c["id.resp_p"]), end))
    cols = ["device", "action", "rule_name", "proto", "app", "session_end_reason"]
    lonely, n, nv = _lonely(fw(), lambda x: (x["src_ip"], x["src_port"], x["dst_ip"], x["dst_port"], x["time_utc"]) in keys, cols)
    have = set(fw()[0].keys()) if fw() else set()
    ok = not lonely and have == set(S.FW_COLS) and n >= len(keys)
    return ok, (f"{n} records of the story's {len(keys)} flows carry {nv} distinct values in {len(cols)} categorical columns; each value is shared with at least 20 other records"
                if not lonely else f"values (column, value): (story records, other records) shared with fewer than 20 other records: {lonely}")


def inv_fw_size():
    files = glob.glob(os.path.join(NETDIR, "firewall", "fw_*.csv"))
    tot, big = sum(map(os.path.getsize, files)), max(map(os.path.getsize, files), default=0)
    denies = sum(1 for x in fw() if x["rule_name"] == "DEFAULT-DENY-INBOUND")
    days = len({x["time_utc"][:10] for x in fw() if x["rule_name"] == "DEFAULT-DENY-INBOUND"})
    return tot <= 90e6 and big <= 45e6 and days >= 180, f"{len(files)} files, {tot / 1e6:.1f} MB, largest {big / 1e6:.1f} MB; {denies:,} dropped unsolicited packets on {days} days (about {denies // max(1, days)} a day)"


# ---------------------------------------------------------------------------------------- proxy
def inv_px_complete():
    want = {}
    for r, devs, zo, zr, d in conn_all():
        if L.is_web_flow(r, zo, zr):
            k = (r["id.orig_h"], G.z(int(float(r["ts"]))))
            want.setdefault(k, []).append(r)
    have = {}
    for x in proxy():
        if x["scheme"] in ("http", "https") and x["action"] == "allowed":
            have.setdefault((x["client_ip"], x["time_utc"]), []).append(x)
    # a plain-HTTP request is logged at the request time, a few hundredths of a second after the connection opens
    missing = [k for k in want if k not in have and (k[0], G.z(_t(k[1]) + 1)) not in have]
    extra = [k for k in have if k not in want]
    # http requests later in a connection carry their own time: allow them when the connection started earlier
    if extra:
        starts = {}
        for (cl, t), rows in want.items():
            for r in rows:
                starts.setdefault(cl, []).append((float(r["ts"]), float(r["ts"]) + _dur(r) + 1))
        extra = [k for k in extra if not any(a - 1 <= _t(k[1]) <= b for a, b in starts.get(k[0], []))]
    bytes_bad = 0
    for k, rows in want.items():
        if len(rows) == 1 and len(have.get(k, [])) == 1 and have[k][0]["scheme"] == "https":
            if have[k][0]["bytes_out"] != rows[0]["orig_bytes"] or have[k][0]["bytes_in"] != rows[0]["resp_bytes"]:
                bytes_bad += 1
    ok = not missing and not extra and not bytes_bad
    return ok, f"{sum(map(len, want.values())):,} web flows in the Zeek logs, {sum(map(len, have.values())):,} allowed web records; flows without a record {len(missing)}, records without a flow {len(extra)}, byte mismatches {bytes_bad}"


def dns_lookups():
    """(client, name) -> sorted times of the delivered dns.log rows."""
    if "dnsq" not in _c:
        out = {}
        for d in DAYS:
            for q in S.zeek_day(d, "dns"):
                out.setdefault((q["id.orig_h"], q["query"]), []).append(float(q["ts"]))
        _c["dnsq"] = out
    return _c["dnsq"]


def inv_px_alerts():
    blocked, dnsrec = {}, {}
    for x in proxy():
        if x["action"] == "blocked":
            blocked.setdefault((x["client_ip"], x["time_utc"], x["user"]), []).append(x)
        elif x["scheme"] == "dns":
            dnsrec.setdefault((x["client_ip"], x["host"], x["time_utc"]), []).append(x)
    look = dns_lookups()
    n5 = n3 = m5 = m3 = nolook = 0
    for al in siem():
        if al["rule_name"] == "POLICY_BLOCKED_SITE":
            n5 += 1
            if len(blocked.get((al["src_ip"], al["time_utc"], al["user"] or "-"), [])) < 1:
                m5 += 1
        elif al["rule_name"] == "DNS_UNCATEGORISED_DOMAIN":
            n3 += 1
            name = dict(kv.split("=", 1) for kv in al["detail"].split() if "=" in kv).get("query")
            t = _t(al["time_utc"])
            times = [tq for tq in look.get((al["src_ip"], name), []) if t - 60 <= tq <= t + 1]
            if not times:
                nolook += 1
            # the filter's record carries the second of the sensor's lookup, the client and the name
            if not any(x["category"] == L.UNCATEGORISED for tq in times for x in dnsrec.get((al["src_ip"], name, G.z(int(tq))), [])):
                m3 += 1
    nb = sum(map(len, blocked.values()))
    nd = sum(map(len, dnsrec.values()))
    sites = {x["host"] for v in blocked.values() for x in v}
    leaked = 0
    for d in list(DAYS)[::9]:
        for name, col in (("ssl", "server_name"), ("dns", "query"), ("http", "host")):
            leaked += sum(1 for r in S.zeek_day(d, name) if r.get(col) in sites)
    ok = m5 == 0 and m3 == 0 and nolook == 0 and nb == n5 and nd == n3 and leaked == 0
    return ok, (f"{n5:,} blocked-site alerts and {nb:,} blocked records (unbacked {m5}); {n3:,} uncategorised-domain alerts and {nd:,} DNS-filter records "
                f"(alerts without a lookup in dns.log {nolook}; without a record at the lookup's own second, client and name {m3}); blocked site names seen in the Zeek logs: {leaked}")


def inv_px_users():
    """A user name on a request means that person was logged on to that client then; service traffic carries none."""
    import gen_itsec_net as GN
    svc_pairs, svc_names = GN.service_traffic()
    named = wrong = svc_named = dns_named = 0
    ex = []
    for x in proxy():
        if x["scheme"] == "dns":
            dns_named += x["user"] != "-"
            continue
        if x["user"] == "-":
            continue
        named += 1
        if x["scheme"] == "https" and (x["host"] in svc_names or (x["client_ip"], x["host"]) in svc_pairs):
            svc_named += 1
        hn = S.host_of_ip(x["client_ip"])
        t = _t(x["time_utc"])
        if not hn or not any(s_["user"] == x["user"] and s_["host"] == hn for tt in (t, t + 1) for s_ in S.sessions_at(tt)):
            wrong += 1
            if len(ex) < 3:
                ex.append((x["time_utc"], x["client_ip"], x["user"], x["action"]))
    ok = wrong == 0 and svc_named == 0 and dns_named == 0
    return ok, (f"{named:,} requests carry a user name; not logged on to that client at that moment: {wrong}{' ' + str(ex) if ex else ''}; "
                f"{len(svc_pairs):,} client and server-name pairs ({len(svc_names)} of the names on five or more clients) are service traffic, encrypted requests of those with a user name: {svc_named}; DNS-filter records with a user name: {dns_named}")


def _px_find(client, host, t0, t1):
    return [x for x in proxy() if x["client_ip"] == client and x["host"] == host and t0 <= _t(x["time_utc"]) <= t1]


def p_px_001():
    hit = _px_find(WS04_IP, "update-cdn.meridiancontrols.net", G.DNS_Q_T, G.DNS_Q_T + 5)
    hit = [x for x in hit if x["bytes_in"] == "1884012"]
    return bool(hit), (f"web filter: {hit[0]['time_utc']} {WS04_IP} user {hit[0]['user']} -> {hit[0]['host']}, {hit[0]['bytes_in']} bytes in, {hit[0]['action']}, category {hit[0]['category']}"
                       if hit else "no web-filter record for the lookalike vendor name at 13:23Z on 2027-08-30")


def p_px_101():
    hit = _px_find(WS04_IP, G.BEACON_SNI, G.BEACON_FIRST - 1, G.BEACON_FIRST + 3)
    return bool(hit), (f"web filter: {hit[0]['time_utc']} {WS04_IP} -> {G.BEACON_SNI}, {hit[0]['bytes_out']} bytes out, {hit[0]['bytes_in']} in, user '{hit[0]['user']}', {hit[0]['action']}" if hit
                       else "first outbound connection not in the web-filter log")


def p_px_107():
    rows = [x for x in proxy() if x["client_ip"] == WS04_IP and x["host"] == G.BEACON_SNI]
    last = max((_t(x["time_utc"]) for x in rows), default=0)
    return bool(rows) and abs(last - G.BEACON_LAST) < 3, f"{len(rows)} requests {WS04_IP} -> {G.BEACON_SNI}; the last at {G.z(int(last)) if rows else '-'}"


def inv_px_neutral():
    """No value of a categorical column on the story's web-filter records is rare among the other records."""
    story_hosts = {G.BEACON_SNI, "update-cdn.meridiancontrols.net"}
    cols = ["method", "scheme", "status", "action", "category", "policy", "user_agent_family"]
    lonely, n, nv = _lonely(proxy(), lambda x: x["host"] in story_hosts, cols)
    have = set(proxy()[0].keys()) if proxy() else set()
    return not lonely and have == set(S.PROXY_COLS) and n > 0, (
        f"the story's {n} web-filter records carry {nv} distinct values in {len(cols)} categorical columns; each value is shared with at least 20 other records"
        if not lonely else f"values (column, value): (story records, other records) shared with fewer than 20 other records: {lonely}")


def inv_px_size():
    files = glob.glob(os.path.join(NETDIR, "proxy", "web_proxy_*.csv"))
    tot, big = sum(map(os.path.getsize, files)), max(map(os.path.getsize, files), default=0)
    users = {x["user"] for x in proxy()} - {"-"}
    unknown = users - set(S.USER_BY_NAME)
    return tot <= 60e6 and big <= 45e6 and not unknown, f"{len(files)} files, {tot / 1e6:.1f} MB, largest {big / 1e6:.1f} MB; {len(users)} user names, {len(unknown)} not in the registry"


# ---------------------------------------------------------------------------------------- dhcp
def inv_dhcp_registry():
    bad = []
    wired = [x for x in dhcp() if x["scope"] != "corp-vpn"]
    for x in wired:
        h = S.BYNAME.get(x["hostname"])
        if not h or x["mac"] != S.mac_of(x["hostname"]) or x["scope"] != h["zone"]:
            bad.append(x)
        elif x["event"] != "NACK" and x["ip"] != h["ip"]:
            bad.append(x)
    hosts = {x["hostname"] for x in wired}
    expect = {h["hostname"] for h in S.WORKSTATIONS if h["zone"].startswith("corp-")}
    return not bad and hosts == expect, f"{len(wired):,} lease events on the user networks for {len(hosts)} machines ({len(expect)} in the registry); address, MAC or scope different from the registry: {len(bad)}"


def _vpn_owner():
    """MAC -> user name for the devices of the employee VPN (the generator's device model)."""
    if "vpnown" not in _c:
        _c["vpnown"] = {mac: (u["username"], hn) for u in S.USERS for hn, mac in G.remote_devices(u["username"])}
    return _c["vpnown"]


def inv_dhcp_vpn():
    vpn_ip = S.IP["GW-VPN-EMP-01"]
    flows = 0
    assign = {}
    for x in dhcp():
        if x["scope"] == "corp-vpn" and x["event"] == "ASSIGN":
            assign[x["time_utc"]] = assign.get(x["time_utc"], 0) + 1
    missing = 0
    for d in DAYS:
        for r in S.zeek_day(d, "conn"):
            if r["id.resp_h"] == vpn_ip and r["conn_state"] not in ("S0", "REJ") and S.zone_of(r["id.orig_h"]) == "internet":
                flows += 1
                k = G.z(int(float(r["ts"]) + 2))
                if assign.get(k, 0) < 1:
                    missing += 1
    pool_bad = sum(1 for x in dhcp() if x["scope"] == "corp-vpn" and not x["ip"].startswith("10.14.250."))
    # no address handed to two clients at once
    held, overlap = {}, 0
    for x in sorted((x for x in dhcp() if x["scope"] == "corp-vpn"), key=lambda x: (_t(x["time_utc"]), x["event"] == "ASSIGN")):
        if x["event"] == "ASSIGN":
            if held.get(x["ip"]) and held[x["ip"]] != x["mac"]:
                overlap += 1
            held[x["ip"]] = x["mac"]
        elif x["event"] == "RELEASE" and held.get(x["ip"]) == x["mac"]:
            held[x["ip"]] = None
    ok = missing == 0 and pool_bad == 0 and overlap == 0 and sum(assign.values()) == flows
    return ok, f"{flows:,} connections to the employee VPN in the Zeek logs, {sum(assign.values()):,} pool leases; without a lease {missing}, outside the pool {pool_bad}, address given out twice at once {overlap}"


def inv_dhcp_devices():
    """VPN leases belong to people: stable devices, one or two per person, used while that person is neither on site nor on leave."""
    own = _vpn_owner()
    names, macs, unknown, onsite, away, n = {}, {}, 0, 0, 0, 0
    named = {}
    for al in siem():
        if al["rule_name"] == "VPN_NEW_LOCATION":
            det = dict(kv.split("=", 1) for kv in al["detail"].split() if "=" in kv)
            named[al["time_utc"][:13], det.get("user")] = 1
    for x in dhcp():
        if x["scope"] != "corp-vpn" or x["event"] != "ASSIGN":
            continue
        n += 1
        names.setdefault(x["mac"], set()).add(x["hostname"])
        macs.setdefault(x["hostname"], set()).add(x["mac"])
        if x["mac"] not in own or own[x["mac"]][1] != x["hostname"]:
            unknown += 1
            continue
        u = S.USER_BY_NAME[own[x["mac"]][0]]
        t = _t(x["time_utc"])
        if (x["time_utc"][:13], u["username"]) in named:
            continue                                       # the user an alert names for that connection
        onsite += S.on_shift(u, t)
        lv = S.LEAVE.get(u["username"])
        away += bool(lv and lv[0] <= t <= lv[1])            # on leave (a weekday worked from home is not "away")
    multi = sum(1 for v in names.values() if len(v) > 1) + sum(1 for v in macs.values() if len(v) > 1)
    per_user = {}
    for mac in names:
        if mac in own:
            per_user.setdefault(own[mac][0], set()).add(mac)
    ok = unknown == 0 and multi == 0 and max(map(len, per_user.values()), default=0) <= 2 and onsite <= 0.01 * n and away == 0
    return ok, (f"{n:,} VPN leases on {len(names)} devices of {len(per_user)} people (at most {max(map(len, per_user.values()), default=0)} per person); devices not in the device model {unknown}, "
                f"a device with two names or a name with two addresses {multi}; leases while the owner is on site {onsite}, while the owner is on leave {away}")


def inv_dhcp_neutral():
    """No value of a categorical column on the lease records of the story's workstation is rare among the other records."""
    lonely, n, nv = _lonely(dhcp(), lambda x: x["hostname"] == G.WS04, ["server", "event", "scope"])
    have = set(dhcp()[0].keys()) if dhcp() else set()
    return not lonely and have == set(S.DHCP_COLS) and n > 0, (f"the {n} lease records of the one workstation carry {nv} distinct values in 3 categorical columns; each value is shared with at least 20 other records"
                                                               if not lonely else f"values (column, value): (story records, other records) shared with fewer than 20 other records: {lonely}")


def inv_dhcp_power():
    """No lease event from a machine while the host logs' power and reboot model has it down; laptops only on their owner's working day."""
    import itsec_host_model as Mo
    owner = {}
    for u in S.USERS:
        for hn in u.get("normal_hosts", [])[:1]:
            owner.setdefault(hn, u)
    bad = n = down = wired = gone = 0
    after_loss = 0
    for x in dhcp():
        h = S.BYNAME.get(x["hostname"])
        if x["scope"] == "corp-vpn" or not h or x["event"] not in ("ASSIGN", "RENEW", "NACK"):
            continue
        t = _t(x["time_utc"])
        wired += 1
        if x["hostname"] in Mo.WIN and not Mo.is_up(x["hostname"], t):
            down += 1
        if x["hostname"] == G.WS04 and t >= G.WS04_REMOVED:
            gone += 1
        if h["device_type"] == "laptop":
            u = owner.get(h["hostname"]) or S.USER_BY_NAME.get(h.get("primary_user", ""))
            if u:
                n += 1
                if not any((w := S.workday(u, d)) and w[0] - 1200 <= t <= w[1] + 120 for d in (G.day_utc(t) - 1, G.day_utc(t), G.day_utc(t) + 1)):
                    bad += 1
    boots = sum(1 for hn in {x["hostname"] for x in dhcp() if x["hostname"] in Mo.WIN} for a, b, planned in Mo.boots(hn) if not planned)
    return bad == 0 and down == 0 and gone == 0, (f"{wired:,} lease events on the user networks: {down} while the machine is down (the model has {boots} losses of power), "
                                                   f"{gone} from the unplugged workstation after its removal; {n:,} laptop events, {bad} outside the owner's working day")


# ---------------------------------------------------------------------------------------- pcap
def _sni(payload):
    """Server name in a TLS ClientHello, or None."""
    try:
        if payload[0] != 0x16 or payload[5] != 0x01:
            return None
        p = 9 + 2 + 32
        p += 1 + payload[p]
        p += 2 + struct.unpack("!H", payload[p:p + 2])[0]
        p += 1 + payload[p]
        end = p + 2 + struct.unpack("!H", payload[p:p + 2])[0]
        p += 2
        while p + 4 <= end:
            et, el = struct.unpack("!HH", payload[p:p + 4])
            if et == 0:
                n = struct.unpack("!H", payload[p + 7:p + 9])[0]
                return payload[p + 9:p + 9 + n].decode("ascii", "replace")
            p += 4 + el
    except (IndexError, struct.error):
        return None
    return None


def pcap_flows():
    """Per day: {5-tuple: {first ts, last ts, packets, client payload bytes, server payload bytes, sni, bad}} from the capture."""
    if "pcap" not in _c:
        out = {}
        for d in DAYS:
            fp = os.path.join(NETDIR, "pcap", f"perimeter_{S.day_str(d)}.pcap")
            flows = {}
            if os.path.exists(fp):
                verify = (d - S.FIRST_DAY) % 6 == 0
                for p in L.read_pcap(fp, verify=verify):
                    k = (p["src"], p["sport"], p["dst"], p["dport"], p["proto"])
                    rk = (p["dst"], p["dport"], p["src"], p["sport"], p["proto"])
                    if rk in flows:
                        f = flows[rk]
                        f["resp"] += len(p["payload"])
                    else:
                        f = flows.setdefault(k, {"first": p["ts"], "orig": 0, "resp": 0, "sni": None, "n": 0, "bad": 0, "last": p["ts"], "syn": bool(p["flags"] & 2) and not p["flags"] & 16})
                        f["orig"] += len(p["payload"])
                        if f["sni"] is None and p["payload"]:
                            f["sni"] = _sni(p["payload"])
                    f["n"] += 1
                    f["last"] = max(f["last"], p["ts"])
                    if verify and not p["ok"]:
                        f["bad"] += 1
            out[d] = flows
        _c["pcap"] = out
    return _c["pcap"]


def inv_pcap_complete():
    pf = pcap_flows()
    want = missing = late = over = bad = extra = 0
    seen = {d: set() for d in DAYS}
    for r, devs, zo, zr, d in conn_all():
        if L.EDGE not in devs:
            continue
        want += 1
        k = (r["id.orig_h"], int(r["id.orig_p"]), r["id.resp_h"], int(r["id.resp_p"]), r["proto"])
        f = pf[d].get(k)
        if not f or abs(f["first"] - float(r["ts"])) > 0.001:
            missing += 1
            continue
        seen[d].add(k)
        if f["last"] > float(r["ts"]) + max(_dur(r), 0.25) + 0.001:
            late += 1
        if f["orig"] > L.to_int(r["orig_bytes"]) or f["resp"] > L.to_int(r["resp_bytes"]):
            over += 1
        bad += f["bad"]
    for d in DAYS:
        extra += len(set(pf[d]) - seen[d])
    files = glob.glob(os.path.join(NETDIR, "pcap", "perimeter_*.pcap"))
    tot = sum(map(os.path.getsize, files))
    ok = missing == 0 and extra == 0 and late == 0 and over == 0 and bad == 0 and tot <= 150e6 and len(files) == len(DAYS)
    return ok, (f"{want:,} flows cross the edge in the Zeek logs; in the capture: missing or first packet off by more than 1 ms {missing}, flows without a Zeek row {extra}, packets after the flow's end {late}, "
                f"more payload than the flow carried {over}, bad checksums or lengths (every sixth day checked) {bad}; {len(files)} files, {tot / 1e6:.1f} MB")


def inv_pcap_sni():
    pf = pcap_flows()
    n = bad = cut = 0
    for d in DAYS:
        for s_ in S.zeek_day(d, "ssl"):
            k = (s_["id.orig_h"], int(s_["id.orig_p"]), s_["id.resp_h"], int(s_["id.resp_p"]), "tcp")
            f = pf[d].get(k)
            if f is None or s_.get("server_name") in (None, "-", "") or f["orig"] == 0:
                continue
            n += 1
            if f["sni"] != s_["server_name"]:
                if f["sni"] is None and f["orig"] < 110 + len(s_["server_name"]):
                    cut += 1                               # the flow carried less than a whole ClientHello
                else:
                    bad += 1
    return n > 0 and bad == 0 and cut <= 0.01 * n, (f"{n:,} captured TLS flows that the sensor also logged in ssl.log; server name in the ClientHello differs from ssl.log in {bad}; "
                                                      f"{cut} flows carried too few bytes for a whole ClientHello")


def _pcap_flow(t, o, op, r, rp):
    return pcap_flows().get(G.day_utc(t), {}).get((o, int(op), r, int(rp), "tcp"))


def p_pcap_001():
    c = _conn_find(G.day_utc(G.DNS_Q_T), WS04_IP, G.BEACON_IP, 443, lambda x: x["resp_bytes"] == "1884012")
    f = _pcap_flow(float(c[0]["ts"]), WS04_IP, c[0]["id.orig_p"], G.BEACON_IP, 443) if c else None
    ok = bool(f) and f["sni"] == "update-cdn.meridiancontrols.net"
    return ok, (f"capture: {WS04_IP} -> {G.BEACON_IP}:443 at {G.z(int(f['first']))}, ClientHello names {f['sni']}, {f['n']} packets kept" if f else "the 13:23Z download is not in the capture")


def p_pcap_101():
    c = _conn_find(G.day_utc(G.BEACON_FIRST), WS04_IP, G.BEACON_IP, 443, lambda x: abs(float(x["ts"]) - G.BEACON_FIRST) < 5)
    f = _pcap_flow(float(c[0]["ts"]), WS04_IP, c[0]["id.orig_p"], G.BEACON_IP, 443) if c else None
    ok = bool(f) and f["sni"] == G.BEACON_SNI and f["orig"] <= int(c[0]["orig_bytes"]) and f["resp"] <= int(c[0]["resp_bytes"])
    return ok, (f"capture: {WS04_IP} -> {G.BEACON_IP}:443 at {G.z(int(f['first']))}, ClientHello names {f['sni']}, {f['orig']} and {f['resp']} payload bytes kept of {c[0]['orig_bytes']} and {c[0]['resp_bytes']}"
                if f else "the first outbound connection is not in the capture")


def _pcap_sessions():
    n = named = 0
    for c in _session_conns():
        f = _pcap_flow(float(c["ts"]), c["id.orig_h"], c["id.orig_p"], JMP_IP, 443) if c else None
        if f:
            n += 1
            named += f["sni"] == "remote.cbpwa.example"
    return n, named


def p_pcap_002():
    n, named = _pcap_sessions()
    return n == 14 and named == 14, f"capture: {n}/14 sessions from outside addresses to the remote-access gateway, {named} with the gateway's name in the ClientHello"


def p_pcap_107():
    pf = pcap_flows()
    times = sorted(f["first"] for d in DAYS for k, f in pf[d].items() if k[0] == WS04_IP and k[2] == G.BEACON_IP)
    ok = bool(times) and abs(times[-1] - G.BEACON_LAST) < 2
    return ok, f"capture: {len(times)} connections {WS04_IP} -> {G.BEACON_IP}, the last at {G.z(int(times[-1])) if times else '-'}"


def inv_pcap_neutral():
    """Every flow gets the same capture depth: for each kind of flow (protocol, service port, answered or not) the number of
    packets kept for the story's flows is a number at least 100 other flows of that kind have."""
    pf = pcap_flows()
    story = {(c["id.orig_h"], int(c["id.orig_p"]), c["id.resp_h"], int(c["id.resp_p"]), c["proto"]): G.day_utc(float(c["ts"])) for c in story_conns() if L.EDGE in L.crossings(c)[0]}
    a, b = {}, {}
    for d in DAYS:
        for k, f in pf[d].items():
            kind = (k[4], k[3] if k[3] in (25, 53, 80, 123, 443) else 0, f["resp"] > 0 or f["n"] > 2)
            tgt = a if story.get(k) == d else b
            tgt.setdefault(kind, {})
            tgt[kind][f["n"]] = tgt[kind].get(f["n"], 0) + 1
    odd = {kind: v for kind, v in a.items() if not set(v) <= {n for n, c in b.get(kind, {}).items() if c >= 100}}
    depth = {kind: dict(sorted(v.items())) for kind, v in sorted(b.items(), key=str)}
    return bool(a) and not odd, (f"packets kept per flow, story flows {{{', '.join(f'{k}: {dict(sorted(v.items()))}' for k, v in sorted(a.items(), key=str))}}}; all other flows by kind "
                                 f"(protocol, port, answered): {depth}" if not odd else f"story flows kept at a depth other flows of the same kind do not have: {odd}")


# ---------------------------------------------------------------------------------------- descriptions
def _range(rows, col="time_utc"):
    ts_ = [r[col] for r in rows]
    return (_t(min(ts_)), _t(max(ts_))) if ts_ else (0, 0)


def _internal(ips):
    return {ip for ip in ips if S.zone_of(ip) not in ("internet", "unknown")}


def _allowed_ips():
    return set(S.HOST_BY_IP) | {str(a) for a in L.PUBLIC_NET} | {f"10.14.250.{i}" for i in range(256)}


def _pcap_range():
    files = sorted(glob.glob(os.path.join(NETDIR, "pcap", "perimeter_*.pcap")))
    if not files:
        return 0, 0

    def first_ts(fp):
        with open(fp, "rb") as fh:
            fh.seek(24)
            h = fh.read(8)
        return struct.unpack("<II", h)[0] if len(h) == 8 else S.ts(os.path.basename(fp)[10:20] + "T00:00Z")
    return first_ts(files[0]), first_ts(files[-1]) + 80000


STREAMS = {
    "firewall_logs": {"time_range": lambda: _range(fw()), "ids": lambda: _internal({x["src_ip"] for x in fw()} | {x["dst_ip"] for x in fw()}),
                      "registry_ids": _allowed_ips, "public_voice": False, "columns": lambda: list(fw()[0].keys())},
    "web_proxy_logs": {"time_range": lambda: _range(proxy()), "ids": lambda: {x["client_ip"] for x in proxy()} | ({x["user"] for x in proxy()} - {"-"}),
                       "registry_ids": lambda: set(S.HOST_BY_IP) | set(S.USER_BY_NAME), "public_voice": False, "columns": lambda: list(proxy()[0].keys())},
    "dhcp_logs": {"time_range": lambda: _range(dhcp()), "ids": lambda: {x["hostname"] for x in dhcp() if x["scope"] != "corp-vpn" or x["hostname"] in S.BYNAME} | {x["server"] for x in dhcp()},
                  "registry_ids": lambda: set(S.BYNAME), "public_voice": False, "columns": lambda: list(dhcp()[0].keys())},
    "packet_captures": {"time_range": _pcap_range, "ids": lambda: _internal({k[0] for d in DAYS for k in pcap_flows()[d]} | {k[2] for d in DAYS for k in pcap_flows()[d]}),
                        "registry_ids": _allowed_ips, "public_voice": False},
}

PROBES = {
    ("GW-EVT-001", "firewall_logs"): p_fw_001, ("GW-EVT-101", "firewall_logs"): p_fw_101, ("GW-EVT-002", "firewall_logs"): p_fw_002,
    ("GW-EVT-011", "firewall_logs"): p_fw_011, ("GW-EVT-107", "firewall_logs"): p_fw_107,
    ("INV-COMPLETE", "firewall_logs"): inv_fw_complete, ("INV-ISOLATION", "firewall_logs"): inv_fw_isolation,
    ("INV-NEUTRAL", "firewall_logs"): inv_fw_neutral, ("INV-SIZE", "firewall_logs"): inv_fw_size,
    ("GW-EVT-001", "web_proxy_logs"): p_px_001, ("GW-EVT-101", "web_proxy_logs"): p_px_101, ("GW-EVT-107", "web_proxy_logs"): p_px_107,
    ("INV-COMPLETE", "web_proxy_logs"): inv_px_complete, ("INV-ALERTS", "web_proxy_logs"): inv_px_alerts,
    ("INV-NEUTRAL", "web_proxy_logs"): inv_px_neutral, ("INV-USERS", "web_proxy_logs"): inv_px_users, ("INV-SIZE", "web_proxy_logs"): inv_px_size,
    ("INV-REGISTRY", "dhcp_logs"): inv_dhcp_registry, ("INV-VPN", "dhcp_logs"): inv_dhcp_vpn, ("INV-DEVICES", "dhcp_logs"): inv_dhcp_devices,
    ("INV-POWER", "dhcp_logs"): inv_dhcp_power, ("INV-NEUTRAL", "dhcp_logs"): inv_dhcp_neutral,
    ("GW-EVT-001", "packet_captures"): p_pcap_001, ("GW-EVT-101", "packet_captures"): p_pcap_101, ("GW-EVT-002", "packet_captures"): p_pcap_002,
    ("GW-EVT-107", "packet_captures"): p_pcap_107,
    ("INV-COMPLETE", "packet_captures"): inv_pcap_complete, ("INV-SNI", "packet_captures"): inv_pcap_sni, ("INV-NEUTRAL", "packet_captures"): inv_pcap_neutral,
}


def main():
    import re
    import time
    only = set(sys.argv[1:])
    banned = re.compile(r"attack|malicious|truth|phase_label|is_fake|is_fraud|ground_truth|thread|label_|_label$|anomaly_flag|compromised", re.I)
    fails = 0
    for sid, d in STREAMS.items():
        if only and sid not in only:
            continue
        t0 = time.time()
        try:
            lo, hi = d["time_range"]()
            unknown = sorted(set(d["ids"]()) - set(d["registry_ids"]()))
            cols = [c for c in d["columns"]() if banned.search(c)] if d.get("columns") else []
            ok = not unknown and not cols and lo <= S.ts("2027-07-16T05:00Z") + 86400 and hi >= S.ts("2028-01-12T06:00Z") - 86400
            print(f"{'ok  ' if ok else 'FAIL'} {sid}: {G.z(int(lo))} .. {G.z(int(hi))}; ids not in the registry: {len(unknown)} {unknown[:4]}; answer-revealing columns: {cols}  [{time.time() - t0:.0f}s]")
            fails += not ok
        except Exception as e:                                         # noqa: BLE001
            print(f"FAIL {sid}: description raised {e!r}")
            fails += 1
    for (ev, sid), p in PROBES.items():
        if only and sid not in only:
            continue
        t0 = time.time()
        try:
            ok, detail = p()
        except Exception as e:                                         # noqa: BLE001
            ok, detail = False, f"probe raised {e!r}"
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {sid:<16} {ev:<14} {detail}  [{time.time() - t0:.0f}s]")
    print(f"\n{'PASS' if not fails else 'FAILED'}: {fails} problem(s) in {len(PROBES)} probes")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
