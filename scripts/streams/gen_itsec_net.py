"""Raw network logs of the utility, derived from the delivered Zeek logs and SIEM alerts:

    firewall_logs     05_other_sources/network_logs/firewall/fw_<DEVICE>_<YYYY-MM>[_NN].csv
    web_proxy_logs    05_other_sources/network_logs/proxy/web_proxy_<YYYY-MM>[_NN].csv
    dhcp_logs         05_other_sources/network_logs/dhcp/dhcp_leases_<YYYY-MM>.csv
    packet_captures   05_other_sources/network_logs/pcap/perimeter_<YYYY-MM-DD>.pcap

Run after gen_itsec.py (siem, zeek, audit) and, for dhcp, after gen_itsec_host.py (its power and reboot
model says when a machine is down). Run again whenever the Zeek logs, the alerts or that model change:

    python3 scripts/streams/gen_itsec_net.py firewall 2027-09     one month (omit the month for all months)
    python3 scripts/streams/gen_itsec_net.py proxy 2027-09
    python3 scripts/streams/gen_itsec_net.py dhcp
    python3 scripts/streams/gen_itsec_net.py pcap 2027-09         a month, or 2027-09:1 ... 2027-09:6 for five days of it
    python3 scripts/streams/gen_itsec_net.py --all --resume [--budget=60]    repeat until it prints DONE (exit 3 = more to do)
    python3 scripts/streams/gen_itsec_net.py --all --fresh                   forget the progress of an earlier --all run first

Nothing here invents network activity of its own except what the devices themselves would add: the
internet background noise the edge firewall drops, the retries the firewalls drop while the control
network is isolated (the traffic of the week before, tried again), the pages the web filter blocks,
and address leases.
Deterministic: the same delivered logs give the same bytes."""
import csv
import datetime as dt
import glob
import json
import os
import sys
import time

import numpy as np

import itsec_net_lib as L
import itsec_shared as S
from common import D0_EPOCH, ROOT, UTC, local_dt, rng

G = S.G
M = S.M
DAY = 86400
NET = S.NET
MAX_FILE = 40_000_000
PCAP_BUDGET = 146_000_000                  # target for the whole capture (limit 150 MB)
CKPT = os.environ.get("ITSEC_NET_CKPT", "/tmp/itsec_net_ckpt.json")
CACHE = os.path.join(ROOT, "scripts", "streams", "_cache")
MONTHS = [m[0] for m in S.months()]


def month_days(mon):
    return [d for d in range(S.FIRST_DAY, S.LAST_DAY + 1) if S.day_str(d)[:7] == mon]


def month_bounds(mon):
    y, m = int(mon[:4]), int(mon[5:7])
    a = dt.datetime(y, m, 1, tzinfo=UTC).timestamp()
    b = dt.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC).timestamp()
    return a, b


def siem_month(mon):
    p = os.path.join(ROOT, NET, "siem", f"siem_alerts_{mon}.csv")
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_parts(rel_dir, stem, header, rows):
    """rows: lists already in output order. Writes <stem>.csv, or <stem>_01.csv ... when over MAX_FILE."""
    d = os.path.join(ROOT, rel_dir)
    os.makedirs(d, exist_ok=True)
    for old in glob.glob(os.path.join(d, stem + ".csv")) + glob.glob(os.path.join(d, stem + "_[0-9][0-9].csv")):
        os.remove(old)
    size = sum(len(",".join(map(str, r))) + 2 for r in rows)
    nparts = max(1, -(-size // MAX_FILE))
    per = -(-len(rows) // nparts) if rows else 0
    for i in range(nparts):
        name = f"{stem}.csv" if nparts == 1 else f"{stem}_{i + 1:02d}.csv"
        with open(os.path.join(d, name), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows[i * per:(i + 1) * per] if nparts > 1 else rows)
    return len(rows), nparts


def _zeek_sig(name):
    files = sorted(glob.glob(os.path.join(ROOT, NET, "zeek", "*", name + ".log")))
    return f"{len(files)}:{sum(os.path.getsize(f) for f in files)}"


def _dur(r):
    return float(r["duration"]) if r["duration"] not in ("-", "") else 0.0


# ======================================================================================
# firewall
# ======================================================================================
_NOISE_TCP = [23, 22, 445, 3389, 80, 443, 8080, 1433, 5900, 6379, 21, 25, 2323, 81, 8443, 7547, 37215, 5555, 9200, 27017, 3306, 5432, 8888, 2222, 110, 143, 993, 8081, 5985, 11211]
_NOISE_TCP_W = np.array([14, 11, 9, 9, 6, 6, 5, 4, 3, 3, 2, 2, 3, 2, 2, 2, 2, 2, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1], float)
_NOISE_UDP = [53, 123, 161, 5060, 1900, 137, 500, 69, 11211, 389]
_BAD_FIRST = {0, 10, 12, 100, 127, 169, 172, 192, 198, 203} | set(range(224, 256))   # private, reserved, our own block; 198 and 203 hold documentation and other reserved ranges


def _inet_ip(g):
    while True:
        a = int(g.integers(1, 224))
        if a in _BAD_FIRST:
            continue
        return f"{a}.{int(g.integers(0, 256))}.{int(g.integers(0, 256))}.{int(g.integers(1, 255))}"


def edge_noise(d, known):
    """Unsolicited internet traffic the edge firewall dropped on UTC day d (a sample). Sources are drawn at random
    from routable space; an address that also appears in the day's flows is drawn again, so a scanner is never
    confused with a correspondent."""
    g = rng("fw_noise", d)
    week = (d - S.FIRST_DAY) // 7

    def fresh(gg):
        while True:
            ip = _inet_ip(gg)
            if ip not in known:
                return ip
    gw = rng("fw_noise_pool", week)
    pool = [_inet_ip(gw) for _ in range(70)]              # scanners that keep coming back for a week or so
    gp = rng("fw_noise_pool", week - 1)
    pool += [_inet_ip(gp) for _ in range(70)][:25]
    pool = [ip for ip in pool if ip not in known]
    n = max(200, int(g.normal(640, 70)))
    t0 = D0_EPOCH + d * DAY
    pubs = [str(a) for a in L.PUBLIC_NET.hosts()]
    out = []
    for _ in range(n):
        t = t0 + float(g.random()) * DAY
        src = pool[int(g.integers(len(pool)))] if g.random() < 0.4 else fresh(g)
        dst = pubs[int(g.integers(len(pubs)))]
        x = g.random()
        if x < 0.86:
            proto, port = "tcp", _NOISE_TCP[int(g.choice(len(_NOISE_TCP), p=_NOISE_TCP_W / _NOISE_TCP_W.sum()))]
            sent = int(g.choice([44, 48, 52, 60]))
            if port in (80, 443) and L.HOST_OF_PUB.get(dst) in ("GW-SRV-WEB-01", "GW-SRV-PORTAL-01"):
                port = int(g.choice([8080, 8443, 22, 23]))            # the public web ports themselves are open
            if port == 25 and L.HOST_OF_PUB.get(dst) == "GW-GW-MAIL-01":
                port = 587
            if port == 443 and L.HOST_OF_PUB.get(dst) in ("GW-VPN-EMP-01", "GW-SYS-JMP-01"):
                port = 8443
        elif x < 0.97:
            proto, port, sent = "udp", _NOISE_UDP[int(g.integers(len(_NOISE_UDP)))], int(g.integers(29, 140))
        else:
            proto, port, sent = "icmp", 0, int(g.choice([28, 60, 84]))
        hn = L.HOST_OF_PUB.get(dst)
        out.append((t, [G.z(int(t)), L.EDGE, "deny", "DEFAULT-DENY-INBOUND", "internet", S.BYNAME[hn]["zone"] if hn else "internet", src,
                        0 if proto == "icmp" else int(g.integers(1024, 65535)), dst, port, proto, "not-applicable", sent, 0, "0.000000", "", "policy-deny"]))
    return out


def isolation_denies(d):
    """What the two firewalls dropped on UTC day d while the control network was cut off: the traffic that crossed
    the IT/OT boundary at the same hour one week earlier (two weeks, where that hour was itself inside the
    isolation), tried again. A machine tries once per sampled flow; a person tries up to three times and gives up.
    Returns (edge rows, boundary rows)."""
    t0 = D0_EPOCH + d * DAY
    if G.boundary_open(t0) and G.boundary_open(t0 + DAY - 1):
        return [], []
    edge, ot = [], []
    for back in (7, 14):
        for r in S.zeek_day(d - back, "conn"):
            devs, zo, zr = L.crossings(r)
            if L.OTFW not in devs or r["conn_state"] in ("S0", "REJ") or r["id.orig_h"] == S.IP[G.JMP]:
                continue                                              # the gateway itself is powered off and starts nothing
            ts0 = float(r["ts"])
            if back == 14 and G.boundary_open(ts0 + 7 * DAY):
                continue                                              # that hour is already replayed from one week back
            if not G.boundary_open(ts0):
                continue
            key = r["uid"]
            t = ts0 + back * DAY + (L.h32("isoj", key) % 1200 - 600) + (L.h32("isof", key) % 1000) / 1000.0
            if G.boundary_open(t) or not (t0 <= t < t0 + DAY):
                continue
            src_h = S.HOST_BY_IP.get(r["id.orig_h"])
            person = zo == "internet" or (src_h is not None and src_h["device_type"] in ("workstation", "laptop"))
            tries = 1 + (L.h32("isot", key) % 3 if person else 0)
            for k in range(tries):
                tt = t + k * (3 + L.h32("isog", key, k) % 18) + (L.h32("isox", key, k) % 1000) / 1000.0
                if G.boundary_open(tt):
                    break
                sport = 40000 + L.h32("isop", key, k) % 20000 if zo == "internet" else 49152 + L.h32("isop", key, k) % 16000
                sent = (52, 60, 52, 48)[L.h32("isob", key, k) % 4]
                if zo == "internet":
                    edge.append((tt, [G.z(int(tt)), L.EDGE, "deny", "DEFAULT-DENY-INBOUND", "internet", zr, r["id.orig_h"], sport, L.PUB_OF.get(S.host_of_ip(r["id.resp_h"]), r["id.resp_h"]),
                                      r["id.resp_p"], r["proto"], "not-applicable", sent, 0, "0.000000", "", "policy-deny"]))
                else:
                    ot.append((tt, [G.z(int(tt)), L.OTFW, "deny", "EMERG-OT-ISOLATION", zo, zr, r["id.orig_h"], sport, r["id.resp_h"], r["id.resp_p"], r["proto"], "not-applicable",
                                    sent, 0, "0.000000", "", "policy-deny"]))
    return edge, ot


def fw_record(dev, zo, zr, r):
    t, dur = float(r["ts"]), _dur(r)
    end = t + dur
    action, drop_rule = L.fw_action(dev, zo, zr, r)
    refused = action == "deny"
    nat = L.nat_ip(r["id.orig_h"]) if dev == L.EDGE and zr == "internet" else ""
    sent, recv = L.ip_bytes(r)
    icmp = r["proto"] == "icmp"
    row = [G.z(int(end)), dev, action, drop_rule if refused else L.fw_rule(dev, zo, zr, r), zo, zr, r["id.orig_h"], 0 if icmp else r["id.orig_p"],
           r["id.resp_h"], 0 if icmp else r["id.resp_p"], r["proto"], "not-applicable" if refused else L.fw_app(r), sent, 0 if refused else recv, f"{dur:.6f}",
           "" if refused else nat, "policy-deny" if refused else L.fw_end_reason(r)]
    return end, row


def gen_firewall(mon):
    a, b = month_bounds(mon)
    days = month_days(mon)
    rows = {L.EDGE: [], L.OTFW: []}
    first = min(days) if days else 0
    for d in range(max(S.FIRST_DAY, first - 3), (max(days) if days else -1) + 1):
        known = set()
        for r in S.zeek_day(d, "conn"):
            devs, zo, zr = L.crossings(r)
            if L.EDGE in devs:
                known.add(r["id.orig_h"] if zo == "internet" else r["id.resp_h"])
            for dev in devs:
                end, row = fw_record(dev, zo, zr, r)
                if a <= end < b or (mon == MONTHS[-1] and end >= b) or (mon == MONTHS[0] and end < a):
                    rows[dev].append((end, row))
        if d in days:
            rows[L.EDGE] += edge_noise(d, known)
            e, o = isolation_denies(d)
            rows[L.EDGE] += e
            rows[L.OTFW] += o
    tot = 0
    for dev in (L.EDGE, L.OTFW):
        rr = [r for _, r in sorted(rows[dev], key=lambda x: (x[0], x[1][6], str(x[1][7])))]
        n, parts = write_parts(f"{NET}/firewall", f"fw_{dev}_{mon}", S.FW_COLS, rr)
        tot += n
        print(f"firewall {mon} {dev}: {n:,} rows in {parts} file(s)")
    return tot


# ======================================================================================
# web proxy and DNS filter
# ======================================================================================
def service_traffic():
    """Which encrypted requests are made by a service or an agent rather than by the person at the keyboard.
    A (client, server name) pair is service traffic when the client reaches the name regularly (30 or more
    connections in the span) and at least a fifth of those happen while nobody is logged on to it. A name with
    five or more such clients is an agent every machine runs, and is service traffic from any client.
    Such requests carry no user name. Returns (set of (client address, name), set of names).
    Computed from the delivered ssl.log and the logon model; cached."""
    sig = _zeek_sig("ssl")
    cache = os.path.join(CACHE, "itsec_net_service_traffic.json")
    if os.path.exists(cache):
        c = json.load(open(cache))
        if c.get("sig") == sig:
            return {tuple(x) for x in c["pairs"]}, set(c["names"])
    n, nu = {}, {}
    for d in range(S.FIRST_DAY, S.LAST_DAY + 1):
        for r in S.zeek_day(d, "ssl"):
            name = r.get("server_name")
            hn = S.host_of_ip(r["id.orig_h"])
            if not hn or name in (None, "-", "") or S.zone_of(r["id.resp_h"]) != "internet":
                continue
            k = (r["id.orig_h"], name)
            n[k] = n.get(k, 0) + 1
            if not S.user_on(hn, float(r["ts"])):
                nu[k] = nu.get(k, 0) + 1
    pairs = sorted(k for k in n if n[k] >= 30 and nu.get(k, 0) / n[k] >= 0.2)
    per_name = {}
    for _, name in pairs:
        per_name[name] = per_name.get(name, 0) + 1
    names = sorted(nm for nm, c in per_name.items() if c >= 5)
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"sig": sig, "pairs": pairs, "names": names}, open(cache, "w"))
    return set(pairs), set(names)


def gen_proxy(mon):
    rows = []
    days = month_days(mon)
    svc_pairs, svc_names = service_traffic()
    lookups, dns_bytes = {}, {}
    for d in ([min(days) - 1] if days and min(days) > S.FIRST_DAY else []) + days:
        for q in S.zeek_day(d, "dns"):
            lookups.setdefault((q["id.orig_h"], q["query"]), []).append((float(q["ts"]), q["uid"], q.get("rcode_name", "NOERROR")))
        for r in S.zeek_day(d, "conn"):
            if r["proto"] == "udp" and r["id.resp_p"] == "53":
                dns_bytes[r["uid"]] = (r["orig_bytes"], r["resp_bytes"])
        if d not in days:
            continue
        names = L.DayNames(d)
        for r in S.zeek_day(d, "conn"):
            devs, zo, zr = L.crossings(r)
            if not L.is_web_flow(r, zo, zr):
                continue
            t = float(r["ts"])
            hn = S.host_of_ip(r["id.orig_h"])
            person = (S.user_on(hn, t) if hn else None) or "-"
            host = names.host(r)
            https = r["id.resp_p"] == "443" or r["service"] == "ssl"
            reqs = names.http.get(r["uid"], []) if not https else []
            state = r["conn_state"]
            if not reqs:
                user = "-" if (https and (host in svc_names or (r["id.orig_h"], host) in svc_pairs)) else person
                status = {"S0": 504, "REJ": 502}.get(state, 200)
                rows.append((t, [G.z(int(t)), r["id.orig_h"], user, "CONNECT" if https else "GET", "https" if https else "http", host, "-" if https else "/", status, "allowed",
                                 L.category_of(host), r["orig_bytes"], r["resp_bytes"], "-", "DEFAULT-WEB-ALLOW"]))
                continue
            tot_resp = sum(L.to_int(q.get("response_body_len")) for q in reqs) or 1
            for k, q in enumerate(reqs):
                tq = float(q["ts"])
                share = (L.to_int(q.get("response_body_len")) / tot_resp) if len(reqs) > 1 else 1.0
                ob = int(L.to_int(r["orig_bytes"]) / len(reqs)) if len(reqs) > 1 else r["orig_bytes"]
                rb = int(L.to_int(r["resp_bytes"]) * share) if len(reqs) > 1 else r["resp_bytes"]
                h = q.get("host") if q.get("host") not in (None, "-", "") else host
                fam = L.ua_family(q.get("user_agent", ""))
                rows.append((tq, [G.z(int(tq)), r["id.orig_h"], person if fam in L.BROWSERS else "-", _val(q.get("method"), "GET"), "http", h, _val(q.get("uri"), "/"),
                                  _val(q.get("status_code", "200"), 200), "allowed", L.category_of(h), ob, rb, fam, "DEFAULT-WEB-ALLOW"]))
    for v in lookups.values():
        v.sort()
    a, b = month_bounds(mon)
    for al in siem_month(mon):
        rule = al["rule_name"]
        if rule not in ("POLICY_BLOCKED_SITE", "DNS_UNCATEGORISED_DOMAIN"):
            continue
        t = _ts(al["time_utc"])
        if rule == "POLICY_BLOCKED_SITE":
            site, cat = L.blocked_site(al["alert_id"])
            https = L.h32("blk-scheme", al["alert_id"]) % 100 < 86
            rows.append((t, [al["time_utc"], al["src_ip"], al["user"] or "-", "CONNECT" if https else "GET", "https" if https else "http", site, "-" if https else "/", 403, "blocked",
                             cat, 180 + L.h32("bo", al["alert_id"]) % 420, 1362 + len(site) + L.h32("bi", site) % 24, "-", "ACCEPTABLE-USE-BLOCK"]))
        else:
            # the lookup behind the alert, exactly as the sensor logged it: same client, same name, same second
            name = dict(kv.split("=", 1) for kv in al["detail"].split() if "=" in kv).get("query")
            hit = None
            for tq, uidq, rcode in lookups.get((al["src_ip"], name), []):
                if t - 60 <= tq <= t + 1:
                    hit = (tq, uidq, rcode)
            if hit:
                tq, uidq, rcode = hit
                ob, rb = dns_bytes.get(uidq, (18 + len(name), 34 + len(name)))
            else:                                                     # no lookup in the sensor log (should not happen): the alert's own time
                tq, rcode, ob, rb = t, "NOERROR", 18 + len(name or ""), 34 + len(name or "")
                name = name or L.fallback_uncategorised_name(al["alert_id"])
            rows.append((tq, [G.z(int(tq)), al["src_ip"], "-", "QUERY", "dns", name, "-", rcode, "allowed", L.UNCATEGORISED, ob, rb, "-", "DNS-FILTER-LOG"]))
    rr = [r for _, r in sorted(rows, key=lambda x: (x[0], x[1][1], x[1][5]))]
    n, parts = write_parts(f"{NET}/proxy", f"web_proxy_{mon}", S.PROXY_COLS, rr)
    print(f"proxy {mon}: {n:,} rows in {parts} file(s)")
    return n


def _val(v, default):
    return default if v in (None, "-", "", "(empty)") else v


def _ts(iso):
    return dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()


# ======================================================================================
# DHCP
# ======================================================================================
LEASE = 8 * DAY
VPN_LEASE = 8 * 3600
DHCP_SERVER = {"corp-users-ops": "GW-SRV-DC-01", "corp-users-biz": "GW-SRV-DC-01", "corp-users-admin": "GW-SRV-DC-02", "corp-users-field": "GW-SRV-DC-02",
               "corp-security": "GW-SRV-DC-01"}
_B32 = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def remote_devices(u, laptop_of=None):
    """The one or two devices a member of staff uses on the employee VPN (the device model lives in gen_itsec)."""
    return G.remote_devices(u["username"])


def gen_dhcp():
    import itsec_host_model as Mo                                     # when each Windows machine is down (reboots, loss of power)
    t_first, t_last = D0_EPOCH + S.FIRST_DAY * DAY, D0_EPOCH + (S.LAST_DAY + 1) * DAY       # the span of the Zeek day folders
    rows = []

    def add(t, server, ev, ip, mac, hostname, scope, lease):
        if t_first <= t < t_last:
            rows.append((t, [G.z(int(t)), server, ev, ip, mac, hostname, scope, lease]))
    owner, laptop_of = {}, {}
    for u in S.USERS:
        for hn in u.get("normal_hosts", [])[:1]:
            owner.setdefault(hn, u)
    for h in S.WORKSTATIONS:
        if h["device_type"] == "laptop":
            u = owner.get(h["hostname"]) or S.USER_BY_NAME.get(h.get("primary_user", ""))
            if u:
                owner[h["hostname"]] = u
                laptop_of.setdefault(u["username"], h["hostname"])

    def downs(hn):
        return [(a, b) for a, b, _ in Mo.boots(hn)] if hn in Mo.WIN else []

    def boot_delay(hn, b):
        return 14 + L.h32("dhcpboot", hn, int(b)) % 70                # the network comes up a little after the machine

    for h in S.WORKSTATIONS:
        if h["zone"] not in DHCP_SERVER:
            continue
        hn, ip, mac, scope, srv = h["hostname"], h["ip"], S.mac_of(h["hostname"]), h["zone"], DHCP_SERVER[h["zone"]]
        g = rng("dhcp", hn)
        dn = downs(hn)
        gone = G.WS04_REMOVED if hn == G.WS04 else t_last            # unplugged for good
        ev = []                                                       # (time, kind) kind: "timer" | "boot" | "dock"
        if h["device_type"] == "laptop" and owner.get(hn):
            u = owner[hn]
            for d in range(S.FIRST_DAY - 9, S.LAST_DAY + 1):
                w = S.workday(u, d)
                if not w:
                    continue
                t = w[0] - int(g.integers(60, 600))                   # docked and started a few minutes before logon
                ev.append((t, "dock"))
                if g.random() < 0.03:                                 # taken off the dock and plugged back in
                    t2 = t + int(g.integers(3600, 6 * 3600))
                    if t2 < w[1]:
                        ev.append((t2, "dock"))
                for a, b in dn:                                       # a restart while it is on the dock
                    if w[0] <= b <= w[1]:
                        ev.append((b + boot_delay(hn, b), "boot"))
        else:
            # desktops stay on: they renew at half the lease, and ask again every time they start
            t = t_first - int(g.integers(0, LEASE // 2))
            while t < min(gone, t_last):
                nxt = t + LEASE // 2 + int(g.integers(-300, 300))
                boot = next(((a, b) for a, b in dn if t < a <= nxt), None)     # it goes down before the timer runs out
                if boot:
                    t = boot[1] + boot_delay(hn, boot[1])
                    ev.append((t, "boot"))
                else:
                    t = nxt
                    ev.append((t, "timer"))
        expires = None
        for t, kind in sorted(ev):
            hit = next(((a, b) for a, b in dn if a <= t < b), None)
            if hit:                                                   # down at that moment: it asks when it is back up
                t = hit[1] + boot_delay(hn, hit[1])
            if t >= gone:
                break
            if expires is not None and t > expires:
                add(expires, srv, "EXPIRE", ip, mac, hn, scope, 0)
                add(t, srv, "ASSIGN", ip, mac, hn, scope, LEASE)
            elif expires is None and t <= t_first + DAY and h["device_type"] == "laptop":
                add(t, srv, "ASSIGN", ip, mac, hn, scope, LEASE)
            else:
                add(t, srv, "RENEW", ip, mac, hn, scope, LEASE)
            expires = t + LEASE
    # a stale lease from another network is refused now and then (a laptop back from a field site)
    gn = rng("dhcp", "nack")
    laptops = [h for h in S.WORKSTATIONS if h["device_type"] == "laptop" and h["zone"] in DHCP_SERVER]
    for _ in range(46):
        h = laptops[int(gn.integers(len(laptops)))]
        u = owner.get(h["hostname"])
        d = int(gn.integers(S.FIRST_DAY, S.LAST_DAY))
        w = S.workday(u, d) if u else None
        if w:
            t = w[0] - int(gn.integers(620, 900))
            if Mo.is_up(h["hostname"], t):
                add(t, DHCP_SERVER[h["zone"]], "NACK", f"10.14.3{int(gn.integers(1, 4))}.{int(gn.integers(20, 200))}", S.mac_of(h["hostname"]), h["hostname"], h["zone"], 0)
    # employee VPN pool: one lease per session of the employee VPN (the session model in gen_itsec gives the person,
    # the device and the pool address; the network sensor shows the same session as one connection to the concentrator)
    stats = {"sessions": 0}
    for v in G.vpn_sessions():
        add(v["t"] + 2, "GW-VPN-EMP-01", "ASSIGN", v["pool_ip"], v["mac"], v["device"], "corp-vpn", VPN_LEASE)
        add(v["t"] + v["dur"], "GW-VPN-EMP-01", "RELEASE", v["pool_ip"], v["mac"], v["device"], "corp-vpn", 0)
        stats["sessions"] += 1
    rows.sort(key=lambda x: (x[0], x[1][3]))
    tot = 0
    for old in glob.glob(os.path.join(ROOT, NET, "dhcp", "dhcp_leases_*.csv")):
        os.remove(old)
    for mon in MONTHS:
        a, b = month_bounds(mon)
        rr = [r for t, r in rows if a <= t < b or (mon == MONTHS[-1] and t >= b) or (mon == MONTHS[0] and t < a)]
        n, _ = write_parts(f"{NET}/dhcp", f"dhcp_leases_{mon}", S.DHCP_COLS, rr)
        tot += n
    print(f"dhcp: {tot:,} rows in {len(MONTHS)} files; VPN leases by how the device was chosen: {stats}")
    return tot


def S_alerts(rule):
    for mon in MONTHS:
        for al in siem_month(mon):
            if al["rule_name"] == rule:
                yield al


# ======================================================================================
# packet capture (flow cutoff, inside interface of the edge firewall)
# ======================================================================================
def _ttl(ip, inside):
    if inside:
        h = S.HOST_BY_IP.get(ip)
        base = 64 if h and "Linux" in str(h.get("os", "")) else 128
        if h and h["device_type"] in ("vpn concentrator", "appliance", "firewall"):
            base = 64
        return base - (2 if ip.startswith("10.14.30.") else 1)
    x = L.h32("ttl", ip)
    return [64, 64, 64, 128, 255][x % 5] - 7 - (x >> 4) % 15


_MTA = {}


def mta_names():
    """Mail server address -> announced host name, from the delivered mail gateway log (sender and recipient domains)."""
    if not _MTA:
        import itsec_audit
        _MTA["-"] = "-"
        p = os.path.join(ROOT, NET, "audit", "mail_gateway_cbpwa.csv")
        if os.path.exists(p):
            with open(p, newline="", encoding="utf-8") as fh:
                for m in csv.DictReader(fh):
                    for dom in (m.get("sender_domain", ""), m.get("recipient", "").split("@")[-1]):
                        if dom and not dom.endswith("cbpwa.example"):
                            _MTA.setdefault(itsec_audit.mta_ip(dom), L.mta_name(None, dom))
    return _MTA


def messages(r, names, ssl_row, outbound):
    """The first application messages of a connection, in order: [(from originator, bytes)]. Protocol framing is
    real (TLS hellos with the server name, HTTP request and status lines, SMTP greeting, DNS and NTP messages);
    everything else is filler of the right length. The same function serves every flow."""
    key, rp, svc = r["uid"], int(r["id.resp_p"]), r["service"]
    ob, rb = L.to_int(r["orig_bytes"]), L.to_int(r["resp_bytes"])
    t0 = float(r["ts"])
    if r["proto"] == "udp":
        dq = names.dns_uid.get(key) if svc == "dns" or rp == 53 else None
        if dq:
            return [(True, L.dns_message(dq, False)), (False, L.dns_message(dq, True))]
        if svc == "ntp" or rp == 123:
            return [(True, L.ntp_message(t0, False, key)), (False, L.ntp_message(t0 + _dur(r), True, key))]
        return [(True, L.hbytes(min(ob, 160), "uo", key)), (False, L.hbytes(min(rb, 200), "ur", key))]
    if svc == "ssl" or rp in (443, 8443):
        sni = names.host(r)
        if L.is_ip(sni):
            sni = "vpn.cbpwa.example" if S.host_of_ip(r["id.resp_h"]) == "GW-VPN-EMP-01" else None
        v13 = (ssl_row["version"] == "TLSv13") if ssl_row else (L.h32("v", key) % 10 < 8)
        cipher = ssl_row["cipher"] if ssl_row else ("TLS_AES_128_GCM_SHA256" if v13 else "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384")
        ch, sh = L.client_hello(sni, v13, cipher, key), L.server_hello(v13, cipher, key)
        return [(True, ch), (False, sh), (True, L.app_record(min(160, max(0, ob - len(ch) - 5)), key + "c") if ob - len(ch) > 24 else b""),
                (False, L.app_record(min(240, max(0, rb - len(sh) - 5)), key + "s") if rb - len(sh) > 24 else b"")]
    reqs = names.http.get(key, [])
    if reqs or rp == 80 or svc == "http":
        q = reqs[0] if reqs else {}
        ua = _val(q.get("user_agent"), "")
        host = _val(q.get("host"), names.host(r))
        req = (f"{_val(q.get('method'), 'GET')} {_val(q.get('uri'), '/')} HTTP/1.1\r\nHost: {host}\r\n" +
               (f"User-Agent: {ua}\r\n" if ua else "") + "Accept: */*\r\nConnection: keep-alive\r\n\r\n").encode("latin-1", "replace")
        n = L.to_int(q.get("response_body_len"), max(0, rb - 120))
        mime = _val(q.get("resp_mime_types"), "")
        resp = (f"HTTP/1.1 {_val(q.get('status_code'), '200')} {_val(q.get('status_msg'), 'OK')}\r\n" + (f"Content-Type: {mime.split(',')[0]}\r\n" if mime else "") +
                f"Content-Length: {n}\r\nConnection: keep-alive\r\n\r\n").encode("latin-1", "replace")
        return [(True, req), (False, resp), (False, L.hbytes(min(240, n), "body", key))]        # filler, not file content
    if svc == "smtp" or rp == 25:
        mta = mta_names()
        server = "mx1.cbpwa.example" if not outbound else mta.get(r["id.resp_h"], L.mta_name(r["id.resp_h"]))
        client = "mx1.cbpwa.example" if outbound else mta.get(r["id.orig_h"], L.mta_name(r["id.orig_h"]))
        return [(False, f"220 {server} ESMTP ready\r\n".encode()), (True, f"EHLO {client}\r\n".encode()),
                (False, f"250-{server}\r\n250-SIZE 52428800\r\n250-8BITMIME\r\n250 STARTTLS\r\n".encode()), (True, b"STARTTLS\r\n")]
    return [(True, L.hbytes(min(ob, 96), "co", key)), (False, L.hbytes(min(rb, 96), "so", key))]


def flow_packets(r, names, level, ssl_row=None):
    """Frames for the first packets of one delivered conn row that crosses the edge: [(epoch, bytes)].
    level 0: the exchange that opens the flow (TCP handshake; UDP request and answer); 1: plus the first
    application message; 2: plus the second; 3: plus an acknowledgement and two more."""
    t0 = float(r["ts"])
    o, op, rr, rp = r["id.orig_h"], int(r["id.orig_p"]), r["id.resp_h"], int(r["id.resp_p"])
    dur = _dur(r)
    ob, rb = L.to_int(r["orig_bytes"]), L.to_int(r["resp_bytes"])
    hist, key = r["history"], r["uid"]
    outbound = S.zone_of(o) != "internet"                             # the originator is inside
    remote = rr if outbound else o
    far = 0.012 + (L.h32("rtt", remote) % 7000) / 1e5                 # internet round trip
    near = 0.0003 + (L.h32("lan", o, rr) % 600) / 1e6                 # local round trip
    d_or, d_ro = (far, near) if outbound else (near, far)             # wait for the responder / for the originator
    ttl_o, ttl_r = _ttl(o, outbound), _ttl(rr, not outbound)
    ido, idr = L.h32("ido", key) & 0xFFFF, L.h32("idr", key) & 0xFFFF
    ev = []                                                           # (offset, from_orig, kind, payload)

    if r["proto"] == "udp":
        msgs = messages(r, names, ssl_row, outbound)
        ev.append((0.0, True, "udp", msgs[0][1][:max(ob, 0)] if ob else msgs[0][1]))
        if rb > 0 and "d" in hist:
            ev.append((d_or, False, "udp", msgs[1][1][:rb]))
    elif r["proto"] == "tcp":
        if "S" not in hist:                                           # picked up in mid-stream
            ev.append((0.0, True, "ack", b""))
            if "a" in hist or "d" in hist:
                ev.append((d_or, False, "ack", b""))
        else:
            ev.append((0.0, True, "syn", b""))
            if "h" in hist:
                ev.append((d_or, False, "synack", b""))
                ev.append((d_or + d_ro, True, "ack", b""))
                if level >= 1 and ("D" in hist or "d" in hist):
                    left = {True: ob if "D" in hist else 0, False: rb if "d" in hist else 0}
                    t = d_or + d_ro + 0.0004 + (L.h32("think", key) % 900) / 1e6
                    prev = True
                    keep = (0, 1, 2, 4)[level]
                    for i, (from_o, pay) in enumerate(messages(r, names, ssl_row, outbound)[:keep]):
                        pay = pay[:left[from_o]]
                        if not pay:
                            continue
                        left[from_o] -= len(pay)
                        if i:
                            t += ((d_or if not from_o else d_ro) if from_o != prev else 0.0) + 0.0006 + (L.h32("proc", key, i) % 23000) / 1e6
                        if i == 2 and level >= 3:
                            ev.append((t - 0.0003, prev is False, "ack", b""))
                        ev.append((t, from_o, "data", pay))
                        prev = from_o
            elif "r" in hist:                                         # refused
                ev.append((d_or, False, "rstack", b""))
    else:
        return []
    last = ev[-1][0]
    if dur > 0 and last > 0.9 * dur:
        ev = [(x * 0.9 * dur / last, a, b, c) for x, a, b, c in ev]
    isn_o, isn_r = L.h32("isno", key), L.h32("isnr", key)
    so, sr = isn_o + 1, isn_r + 1
    out = []
    for off, from_o, kind, pay in ev:
        src, dst, sp, dp = (o, rr, op, rp) if from_o else (rr, o, rp, op)
        if kind == "udp":
            l4, proto = L.udp_datagram(src, dst, sp, dp, pay), 17
        else:
            if kind == "syn":
                seg = L.tcp_segment(src, dst, sp, dp, isn_o, 0, L.SYN, L.syn_opts(src, isn_o)[1], opts=L.syn_opts(src, isn_o)[0])
            elif kind == "synack":
                seg = L.tcp_segment(src, dst, sp, dp, isn_r, isn_o + 1, L.SYN | L.ACK, L.syn_opts(src, isn_r)[1], opts=L.syn_opts(src, isn_r)[0])
            elif kind == "rstack":
                seg = L.tcp_segment(src, dst, sp, dp, 0, isn_o + 1, L.RST | L.ACK, 0)
            elif kind == "ack":
                seg = L.tcp_segment(src, dst, sp, dp, so if from_o else sr, sr if from_o else so, L.ACK, 1026 if from_o else 501)
            else:
                seg = L.tcp_segment(src, dst, sp, dp, so if from_o else sr, sr if from_o else so, L.PSH | L.ACK, 1026 if from_o else 501, pay)
                if from_o:
                    so += len(pay)
                else:
                    sr += len(pay)
            l4, proto = seg, 6
        if from_o:
            ido = (ido + 1) & 0xFFFF
        else:
            idr = (idr + 1) & 0xFFFF
        pkt = L.ip_packet(src, dst, proto, l4, ttl_o if from_o else ttl_r, ido if from_o else idr)
        out.append((t0 + off, L.frame(outbound == from_o, pkt)))
    return out


def pcap_level():
    """Highest capture depth (0-3) that keeps the whole capture inside the budget. One depth for every flow.
    Depends only on the delivered conn logs."""
    sig = _zeek_sig("conn")
    cache = os.path.join(CACHE, "itsec_net_plan.json")
    if os.path.exists(cache):
        c = json.load(open(cache))
        if c.get("sig") == sig and c.get("budget") == PCAP_BUDGET:
            return c["level"]
    n_flows = 0
    for d in range(S.FIRST_DAY, S.LAST_DAY + 1):
        n_flows += sum(1 for r in S.zeek_day(d, "conn") if L.EDGE in L.crossings(r)[0])
    sample = list(range(S.FIRST_DAY + 3, S.LAST_DAY, 23))
    est = {}
    for level in (3, 2, 1, 0):
        b = n = 0
        for d in sample:
            names = L.DayNames(d)
            ssl = {x["uid"]: x for x in S.zeek_day(d, "ssl")}
            for r in S.zeek_day(d, "conn"):
                if L.EDGE in L.crossings(r)[0]:
                    n += 1
                    b += sum(len(f) + 16 for _, f in flow_packets(r, names, level, ssl.get(r["uid"])))
        est[level] = int(b / max(1, n) * n_flows) + 24 * (S.LAST_DAY - S.FIRST_DAY + 1)
    level = next((lv for lv in (3, 2, 1, 0) if est[lv] <= PCAP_BUDGET), 0)
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"sig": sig, "budget": PCAP_BUDGET, "level": level, "edge_flows": n_flows, "estimated_bytes": est}, open(cache, "w"))
    print(f"pcap plan: {n_flows:,} edge flows, estimated bytes by depth {est}, depth {level}")
    return level


def gen_pcap(part):
    """part: 'YYYY-MM' (the whole month) or 'YYYY-MM:1' ... ':6' (days 1-5, 6-10, ..., 26 to the end)."""
    mon, _, third = part.partition(":")
    level = pcap_level()
    tot_p = tot_b = 0
    days = [d for d in month_days(mon) if not third or min(5, (int(S.day_str(d)[8:10]) - 1) // 5) == int(third) - 1]
    for d in days:
        names = L.DayNames(d)
        ssl = {x["uid"]: x for x in S.zeek_day(d, "ssl")}
        pk = []
        for r in S.zeek_day(d, "conn"):
            if L.EDGE in L.crossings(r)[0]:
                pk += flow_packets(r, names, level, ssl.get(r["uid"]))
        p = os.path.join(ROOT, NET, "pcap", f"perimeter_{S.day_str(d)}.pcap")
        tot_p += L.write_pcap(p, pk)
        tot_b += os.path.getsize(p)
    print(f"pcap {part}: {tot_p:,} packets, {tot_b / 1e6:.1f} MB in {len(days)} files (depth {level})")
    return tot_p


# ======================================================================================
PARTS = [("firewall", m) for m in MONTHS] + [("proxy", m) for m in MONTHS] + [("dhcp", None)] + [("pcap", f"{m}:{k}") for m in MONTHS for k in (1, 2, 3, 4, 5, 6)]
FUNCS = {"firewall": gen_firewall, "proxy": gen_proxy, "pcap": gen_pcap}


def run(part, mon):
    if part == "dhcp":
        return gen_dhcp()
    return FUNCS[part](mon)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if "--all" in flags:
        t0 = time.time()
        budget = next((float(a.split("=", 1)[1]) for a in flags if a.startswith("--budget=")), 60.0)
        if "--fresh" in flags and os.path.exists(CKPT):
            os.remove(CKPT)
        done = json.load(open(CKPT)) if ("--resume" in flags and os.path.exists(CKPT)) else []
        for part, mon in PARTS:
            name = f"{part}:{mon}"
            if name in done:
                continue
            if time.time() - t0 > budget:
                print(f"PARTIAL: {len(done)}/{len(PARTS)} parts done. Run again with --all --resume.")
                return 3
            run(part, mon)
            done.append(name)
            json.dump(done, open(CKPT, "w"))
        print("DONE")
        return 0
    if not args or args[0] not in ("firewall", "proxy", "dhcp", "pcap"):
        print(__doc__)
        return 2
    if args[0] == "dhcp":
        gen_dhcp()
    else:
        for mon in (args[1:] or MONTHS):
            FUNCS[args[0]](mon)
    return 0


if __name__ == "__main__":
    sys.exit(main())
