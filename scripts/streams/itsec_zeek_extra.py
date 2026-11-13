"""Additional sensor records written by itsec_zeek.gen_zeek: plain-HTTP traffic (http.log, files.log),
certificates seen in TLS 1.2 handshakes (x509.log, and the cert_chain_fps column of ssl.log), ordinary
business use of the historian replica, OT patch staging, periodic machine traffic to the internet
(recorded in full), and the flows behind network alerts (a DNS query for every uncategorised-domain
alert, the probes of every port-sweep alert, the VPN connection of every new-location alert, the
connection of every flagged-address alert).
"""
import hashlib

import numpy as np

from common import D0_EPOCH, local_dt, rng, ts

DAY = 86400
HTTP_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "trans_depth", "method", "host", "uri", "referrer", "version", "user_agent",
          "request_body_len", "response_body_len", "status_code", "status_msg", "tags", "resp_fuids", "resp_mime_types"]
HTTP_TY = ["time", "string", "addr", "port", "addr", "port", "count", "string", "string", "string", "string", "string", "string",
           "count", "count", "count", "string", "set[enum]", "vector[string]", "vector[string]"]
FILES_F = ["ts", "fuid", "tx_hosts", "rx_hosts", "conn_uids", "source", "depth", "analyzers", "mime_type", "filename", "duration", "local_orig", "is_orig",
           "seen_bytes", "total_bytes", "missing_bytes", "overflow_bytes", "timedout", "md5", "sha1"]
FILES_TY = ["time", "string", "set[addr]", "set[addr]", "set[string]", "string", "count", "set[string]", "string", "string", "interval", "bool", "bool",
            "count", "count", "count", "count", "bool", "string", "string"]
X509_F = ["ts", "fingerprint", "certificate.version", "certificate.serial", "certificate.subject", "certificate.issuer", "certificate.not_valid_before",
          "certificate.not_valid_after", "certificate.key_alg", "certificate.sig_alg", "certificate.key_type", "certificate.key_length", "certificate.exponent",
          "san.dns", "basic_constraints.ca", "host_cert", "client_cert"]
X509_TY = ["time", "string", "count", "string", "string", "string", "time", "time", "string", "string", "string", "count", "string",
           "vector[string]", "bool", "bool", "bool"]
PUBLIC_CAS = ["CN=Harbor Trust TLS RSA CA G2,O=Harbor Trust Services,C=US", "CN=Meridian Root R3 Issuing CA,O=Open Certificate Alliance,C=US",
              "CN=NorthGate Secure Server CA 2,O=NorthGate Trust,C=US", "CN=Atlas DV TLS CA 4,O=Atlas Certificate Company,C=US"]
INTERNAL_CA = "CN=CBPWA Issuing CA 01,DC=corp,DC=cbpwa,DC=example"
INTERNAL_NAMES = ("historian.cbpwa.example", "intranet.cbpwa.example", "mail.cbpwa.example", ".corp.cbpwa.example", ".ot.cbpwa.example")
UA_BROWSER = [f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36" for v in (136, 137, 138, 139)] + \
    [f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36 Edg/{v}.0.0.0" for v in (137, 138, 139)] + \
    [f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{v}.0) Gecko/20100101 Firefox/{v}.0" for v in (128, 140, 141)]
UA_UPDATE = ["Microsoft-Delivery-Optimization/10.0", "Microsoft-Delivery-Optimization/10.1", "Windows-Update-Agent/10.0.10011.16384 Client-Protocol/2.71", "Microsoft BITS/7.8"]
UA_CRYPTO = ["Microsoft-CryptoAPI/10.0", "Microsoft-CryptoAPI/10.0", "Java/17.0.11", "ocsp-client/2.4 (Edge)", "Go-http-client/1.1"]
# periodic machine traffic to the internet, recorded in full: (server name, hostnames, seconds between checks, jitter, first day, last day, only while someone is logged on)
AGENT_NAME = "telemetry.vantage-security.com"
SERIES = [
    ("lic-check.gridcad-software.com", ["GW-SRV-GIS-01"], 6 * 3600, 900, -60, 120, False),
    ("activate.gridcad-software.com", ["GW-WS-IT-71", "GW-WS-IT-72", "GW-WS-IT-74"], 24 * 3600, 5400, -60, 120, True),
    ("sync.cloudstorage-sync.com", ["GW-WS-IT-01", "GW-WS-IT-02"], 4 * 3600, 1500, -60, 120, True),
    ("fleet.printwave-services.net", ["GW-SRV-PRINT-01"], 12 * 3600, 2400, -60, 120, False),
    ("update-cdn.relaytech-support.net", ["GW-WS-IT-66"], 12 * 3600, 3600, -60, 120, False),
    ("telemetry.hrcloud-payroll.com", ["GW-SRV-HR-01"], 8 * 3600, 1200, -60, 120, False),
    ("api.fleetfuel-cards.com", ["GW-SRV-ERP-01"], 8 * 3600, 1800, -60, 120, False),
    ("live-feeds.weatherradar-tiles.com", ["GW-SRV-OMS-01"], 6 * 3600, 600, -24, 120, False),
    ("agent-east.backupvault-cloud.net", ["GW-SRV-BKP-01"], 24 * 3600, 1800, -60, 120, False),
    ("updates.browser-safecheck.net", ["GW-WS-IT-158"], 6 * 3600, 3600, -36, 120, False),
    ("telemetry.meetroom-video.com", ["GW-WS-IT-159"], 5 * 3600, 2700, -60, 78, False),
    ("status.docsign-flow.com", ["GW-WS-IT-160"], 7 * 3600, 3600, 6, 120, False),
    ("cdn.partsdepot-supply.com", ["GW-WS-IT-161"], 9 * 3600, 3000, -60, 120, False),
    ("push-gw.cellcarrier-account.com", ["GW-LT-FLD-110", "GW-LT-FLD-112", "GW-LT-FLD-115", "GW-LT-FLD-118"], 2 * 3600, 900, -60, 120, True),
    ("metrics-in.pumpworks-service.com", ["GW-WS-IT-163"], 6 * 3600, 3600, -47, 120, False),
    ("api.packagetracker-api.net", ["GW-WS-IT-162"], 10 * 3600, 3600, -60, 44, False),
]
NTP_SERVERS = ["0.ntp-pool-public.org", "1.ntp-pool-public.org", "2.ntp-pool-public.org"]


def _h(*k, n=40):
    return hashlib.sha256("|".join(map(str, k)).encode()).hexdigest()[:n]


def name_ip(G, name, k=0):
    """Address of an outside server name that is not in the site list (fixed per name)."""
    if name in G.SITE_IPS:
        return G.SITE_IPS[name][k % len(G.SITE_IPS[name])]
    v = int(_h("nip", name, k, n=8), 16)
    return f"{G._PREFIX[v % len(G._PREFIX)]}.{1 + (v >> 8) % 249}.{1 + (v >> 16) % 249}.{2 + (v >> 24) % 248}"


def flag_name(G, ip):
    """Server name seen for a flagged address (shared hosting: an ordinary site name)."""
    for s, ips in G.SITE_IPS.items():
        if ip in ips:
            return s
    v = int(_h("fn", ip, n=8), 16)
    return f"{['cdn', 'static', 'img', 'app', 'www'][v % 5]}.{G._UNCAT_A[(v >> 4) % len(G._UNCAT_A)]}{G._UNCAT_B[(v >> 9) % len(G._UNCAT_B)]}.{['com', 'net', 'io', 'co'][(v >> 14) % 4]}"


def cert_for(name, t):
    """The server certificate a name presents at time t (deterministic; public sites renew every 90 days,
    the utility's own names once a year)."""
    internal = name.endswith(INTERNAL_NAMES)
    period = (365 if internal else 90) * DAY
    anchor = D0_EPOCH - 400 * DAY + int(_h("anchor", name, n=6), 16) % period
    k = int((t - anchor) // period)
    nvb = anchor + k * period
    nva = nvb + period + (30 * DAY if not internal else 0)
    issuer = INTERNAL_CA if internal else PUBLIC_CAS[int(_h("ca", name, n=4), 16) % len(PUBLIC_CAS)]
    base = name.split(".", 1)[1] if name.count(".") >= 2 and not internal else name
    return {"fp": _h("cert", name, k, n=64), "serial": _h("serial", name, k, n=32).upper(), "subject": f"CN={name}", "issuer": issuer,
            "nvb": nvb, "nva": nva, "san": f"{name},{base}" if base != name else name,
            "key": ("rsaEncryption", "sha256WithRSAEncryption", "rsa", 2048, "65537") if internal or int(_h("k", name, n=2), 16) % 3 else
                   ("id-ecPublicKey", "ecdsa-with-SHA384", "ecdsa", 256, "-")}


def x509_row(t, c):
    return [f"{t:.6f}", c["fp"], 3, c["serial"], c["subject"], c["issuer"], f"{c['nvb']:.6f}", f"{c['nva']:.6f}", c["key"][0], c["key"][1], c["key"][2], c["key"][3],
            c["key"][4], c["san"], "F", "T", "F"]


def finish_ssl(ssl_rows):
    """Add the cert_chain_fps column to the day's ssl rows and return the x509 rows (one per certificate per day,
    at its first sighting). TLS 1.3 hides the certificate, so only TLS 1.2 sessions carry one; resumed sessions carry none."""
    seen, x509 = set(), []
    for r in ssl_rows:
        fps = "(empty)"
        if r[6] == "TLSv12" and r[10] == "T" and r[9] == "F" and r[8] not in ("-", ""):
            c = cert_for(r[8], float(r[0]))
            fps = c["fp"]
            if c["fp"] not in seen:
                seen.add(c["fp"])
                x509.append(x509_row(float(r[0]) + 0.02, c))
        r.append(fps)
    return x509


_USED = set()


def fresh_port(g, o, r, rp, lo=49152, span=16000):
    """A source port that gives a connection 4-tuple not yet used on this day."""
    while True:
        op = lo + int(g.integers(0, span))
        if (o, op, r, rp) not in _USED:
            _USED.add((o, op, r, rp))
            return op


def _site(G, word):
    return next(s for s in G.SITES if word in s)


def http_flow(G, t, o, r, rp, method, host, uri, ua, req_len, resp_len, status, msg, mime, g, fname_key=None):
    """(conn row, http row, files row or None) for one plain-HTTP request."""
    op = fresh_port(g, o, r, rp)
    dur = 0.08 + resp_len / 2.5e6 + float(g.gamma(2, 0.05))
    c = G.conn(t, o, op, r, rp, "tcp", "http", dur, 380 + req_len + int(g.integers(0, 160)), 310 + resp_len + int(g.integers(0, 90)))
    fuid, frow = "-", None
    if resp_len > 0 and status in (200, 206):
        fuid = "F" + _h("fuid", c[1], n=17)
        key = fname_key or c[1]
        frow = [f"{t + 0.04:.6f}", fuid, r, o, c[1], "HTTP", 0, "MD5,SHA1", mime, "-", f"{dur:.6f}", "F", "F", resp_len, resp_len, 0, 0, "F", _h("md5", key, n=32), _h("sha1", key, n=40)]
    h = [f"{t + 0.03:.6f}", c[1], o, op, r, rp, 1, method, host, uri, "-", "1.1", ua, req_len, resp_len, status, msg, "(empty)", fuid if frow else "-", mime if frow else "-"]
    return c, h, frow


def extra_rows(G, S, d, alerts, wf, existing=()):
    """Rows to add to UTC day d: dict of lists of (time, row) for conn, dns, ssl, http, files.
    existing: the day's conn rows written so far (no 4-tuple is used twice in a day)."""
    out = {k: [] for k in ("conn", "dns", "ssl", "http", "files")}
    _USED.clear()
    _USED.update((c[2], c[3], c[4], c[5]) for c in existing)
    t0 = D0_EPOCH + d * DAY
    IP = G.IP
    dc = [IP["GW-SRV-DC-01"], IP["GW-SRV-DC-02"]]
    wsip = [h["ip"] for h in G.CORP]
    ws04 = IP[G.WS04]
    patch_host = f"{G.BYNAME[G.PATCH]['fqdn']}:8530"

    def add_http(tup):
        c, h, f = tup
        out["conn"].append((float(c[0]), c))
        out["http"].append((float(h[0]), h))
        if f:
            out["files"].append((float(f[0]), f))

    # ---- plain HTTP from workstations: certificate status checks, connectivity checks, update and definition downloads, redirects
    g = rng("zeek_http", d)
    hours = wf + 0.3
    n = int(g.poisson(230 * (0.35 + wf.mean() * 1.6)))
    hsel = g.choice(24, n, p=hours / hours.sum())
    ocsp, ncsi, upd, av = _site(G, "certstatus-ocsp"), _site(G, "telemetry-osvendor"), _site(G, "osupdates-delivery"), "downloads.vantage-security.com"
    for hh in hsel:
        t = t0 + int(hh) * 3600 + g.random() * 3600
        o = wsip[g.integers(len(wsip))]
        if o == ws04 and t >= G.WS04_REMOVED:
            o = wsip[(wsip.index(o) + 1) % len(wsip)]
        k = g.random()
        if k < 0.3:
            add_http(http_flow(G, t, o, G.SITE_IPS[ocsp][0], 80, "POST", ocsp, "/", UA_CRYPTO[int(g.integers(len(UA_CRYPTO)))], 83, 471, 200, "OK", "application/ocsp-response", g,
                               fname_key=("ocsp", int(g.integers(0, 400)), d // 4)))
        elif k < 0.5:
            add_http(http_flow(G, t, o, G.SITE_IPS[ncsi][0], 80, "GET", ncsi, "/connecttest.txt", "Microsoft NCSI", 0, 22, 200, "OK", "text/plain", g, fname_key="ncsi"))
        elif k < 0.7:
            fid = _h("upd", int(g.integers(0, 60)), d // 7, n=12)
            size = int(1e6 + int(_h("sz", fid, n=6), 16) % 60_000_000)
            ip_u, ua_u, rs = G.SITE_IPS[upd][int(g.integers(len(G.SITE_IPS[upd])))], UA_UPDATE[int(g.integers(len(UA_UPDATE)))], g.random()
            if rs < 0.70:
                add_http(http_flow(G, t, o, ip_u, 80, "GET", upd, f"/d/updt/2027/{fid[:2]}/{fid}.cab", ua_u, 0, size, 200, "OK", "application/vnd.ms-cab-compressed", g, fname_key=("upd", fid)))
            elif rs < 0.89:                               # a ranged request for part of a file
                add_http(http_flow(G, t, o, ip_u, 80, "GET", upd, f"/d/updt/2027/{fid[:2]}/{fid}.cab", ua_u, 0, 1 + size // (2 + int(rs * 1000) % 7), 206, "Partial Content",
                                   "application/vnd.ms-cab-compressed", g, fname_key=("updp", fid, int(rs * 1000) % 7)))
            elif rs < 0.96:
                add_http(http_flow(G, t, o, ip_u, 80, "HEAD" if rs < 0.93 else "GET", upd, f"/d/updt/2027/{fid[:2]}/{fid}.cab", ua_u, 0, 0, 304 if rs >= 0.93 else 200, "Not Modified" if rs >= 0.93 else "OK", "-", g))
            else:
                add_http(http_flow(G, t, o, ip_u, 80, "GET", upd, f"/d/updt/2027/{fid[:2]}/{fid}.cab", ua_u, 0, 0, 404 if rs < 0.985 else 503, "Not Found" if rs < 0.985 else "Service Unavailable", "-", g))
        elif k < 0.8:
            ver = 41000 + d * 3 + int(g.integers(0, 3))
            rs = g.random()
            if rs < 0.86:
                add_http(http_flow(G, t, o, G.SITE_IPS[av][0], 80, "GET", av, f"/defs/v7/{ver}.vdf", f"VantageAgent/7.{2 + (d > 20)}", 0, int(3e5 + (ver * 7919) % 5_000_000), 200, "OK",
                                   "application/octet-stream", g, fname_key=("vdf", ver)))
            else:
                add_http(http_flow(G, t, o, G.SITE_IPS[av][0], 80, "GET", av, f"/defs/v7/{ver}.vdf", f"VantageAgent/7.{2 + (d > 20)}", 0, 0, 304 if rs < 0.97 else 404,
                                   "Not Modified" if rs < 0.97 else "Not Found", "-", g))
        elif k < 0.9:
            site = G.SITES[g.integers(len(G.SITES))]
            pick = int(g.integers(1 << 30))
            who = [x["host"] for x in S.sessions_at(t) if x["host"] in G.CORP_NAMES and x["logon"] + 45 <= t and not (x["host"] == G.WS04 and t >= G.WS04_REMOVED)]
            if who:                                       # a person typing an address without https
                hn = sorted(who)[pick % len(who)]
                rs = (pick >> 8) % 100
                code, msg = (301, "Moved Permanently") if rs < 78 else ((302, "Found") if rs < 88 else ((308, "Permanent Redirect") if rs < 93 else ((403, "Forbidden") if rs < 96 else (404, "Not Found"))))
                add_http(http_flow(G, t, IP[hn], G.SITE_IPS[site][0], 80, "GET", site, "/" if rs < 90 else f"/{['index.html', 'login', 'favicon.ico', 'news'][pick % 4]}",
                                   G.browser_ua(hn, t, pick), 0, 0, code, msg, "-", g))
        elif k < 0.96:
            fid = _h("wsus", int(g.integers(0, 40)), d // 7, n=40)
            add_http(http_flow(G, t, o, IP[G.PATCH], 8530, "GET", patch_host, f"/Content/{fid[-2:].upper()}/{fid.upper()}.cab", UA_UPDATE[2],
                               0, int(2e5 + int(fid[:6], 16) % 30_000_000), 200, "OK", "application/vnd.ms-cab-compressed", g, fname_key=("wsus", fid)))
        else:
            pick = int(g.integers(1 << 30))
            who = [x["host"] for x in S.sessions_at(t) if x["host"] in G.CORP_NAMES and x["logon"] + 45 <= t and not (x["host"] == G.WS04 and t >= G.WS04_REMOVED)]
            if who:
                hn = sorted(who)[pick % len(who)]
                add_http(http_flow(G, t, IP[hn], IP["GW-SRV-INTRA-01"], 80, "GET", "intranet.cbpwa.example", "/", G.browser_ua(hn, t, pick), 0, 0, 302, "Found", "-", g))
    # ---- OT patch staging server fetching approved updates from the corporate patch server (crosses the IT/OT boundary)
    for _ in range(int(g.poisson(1.6))):
        t = t0 + int(g.integers(1, 5)) * 3600 + g.random() * 3600
        fid = _h("wsus", int(g.integers(0, 40)), d // 7, n=40)
        if G.boundary_open(t):
            add_http(http_flow(G, t, IP["GW-SRV-OTPATCH-01"], IP[G.PATCH], 8530, "GET", patch_host, f"/Content/{fid[-2:].upper()}/{fid.upper()}.cab",
                               UA_UPDATE[2], 0, int(2e5 + int(fid[:6], 16) % 30_000_000), 200, "OK", "application/vnd.ms-cab-compressed", g, fname_key=("wsus", fid)))
    # ---- business users reading the historian replica in the IT/OT DMZ (trend viewer; now and then a file export)
    gb = rng("zeek_replica", d)
    zone_of = {h["hostname"]: h.get("zone") for h in G.CORP}
    for _ in range(int(gb.poisson(7 * wf.mean() + 0.3))):
        hh = int(gb.choice(24, p=(wf + 0.02) / (wf + 0.02).sum()))
        t = t0 + hh * 3600 + gb.random() * 3600
        pick, rz = int(gb.integers(1 << 30)), gb.random()
        smb = gb.random() < 0.16
        dur, ob, rb = float(gb.gamma(2, 60)) + 4, int(gb.gamma(2, 2e5)) + 4000, int(gb.lognormal(17.2, 1.5)) + 20000
        # readers are people at their desks: mostly operations and engineering, some finance, planning and administration
        who = sorted(x["host"] for x in S.sessions_at(t) if x["host"] in G.CORP_NAMES and x["logon"] + 45 <= t and not (x["host"] == G.WS04 and t >= G.WS04_REMOVED))
        ops = [h for h in who if zone_of.get(h) == "corp-users-ops"]
        who = ops if (ops and rz < 0.72) else who
        if not G.boundary_open(t) or not who:
            continue
        o = IP[who[pick % len(who)]]
        op = fresh_port(gb, o, IP[G.HISTDMZ], 445 if smb else 443)
        if smb:
            out["conn"].append((t, G.conn(t, o, op, IP[G.HISTDMZ], 445, "tcp", "smb", dur, ob, rb)))
        else:
            c = G.conn(t, o, op, IP[G.HISTDMZ], 443, "tcp", "ssl", dur * 4 + 5, int(ob / 6) + 2000, int(gb.gamma(2, 9e5)) + 9000)
            out["conn"].append((t, c))
            out["ssl"].append((t + 0.05, G.ssl_row(t + 0.05, c, "historian.cbpwa.example")))
    # ---- the flows behind the day's network alerts
    ge = rng("zeek_alert_flows", d)
    for a in alerts:
        name, t = a["rule_name"], a["t"]
        det = dict(kv.split("=", 1) for kv in a["detail"].split() if "=" in kv)
        if name == "DNS_UNCATEGORISED_DOMAIN" and "query" in det:
            tq = t - float(ge.uniform(1.5, 20))
            nx = ge.random() < 0.12
            dr = G.dns_row(tq, a["src_ip"], dc[ge.integers(2)], det["query"], "-" if nx else name_ip(G, det["query"]), ge)
            if nx:
                dr[11], dr[16] = "NXDOMAIN", "-"
            out["dns"].append((tq, dr))
            out["conn"].append((tq, G.dns_conn(dr)))
        elif name == "INTERNAL_PORT_SWEEP" and "targets" in det:
            nt, port = int(det["targets"]), int(det["port"])
            net = str(ge.choice(["10.14.10", "10.14.20", "10.14.21", "10.14.22", "10.14.30", "10.14.12"]))
            first = int(ge.integers(2, 200))
            for i in range(nt):
                tp = t - 4.0 + i * (3.6 / nt) + float(ge.uniform(0, 0.05))
                dst = f"{net}.{first + i}"
                up = dst in S.HOST_BY_IP and not (dst == ws04 and tp >= G.WS04_REMOVED)
                st, hist = ("REJ", "Sr") if ge.random() < 0.7 and up else ("S0", "S")
                out["conn"].append((tp, G.conn(tp, a["src_ip"], 49152 + int(ge.integers(0, 16000)), dst, port, "tcp", "-", 0.0, 0, 0, st, hist)))
        elif name == "FLAGGED_IP_OUTBOUND" and a["dst_ip"] and a["dst_ip"] != G.BEACON_IP and "bytes_out" in det:
            tf = t - float(ge.uniform(1, 5))
            c = G.conn(tf, a["src_ip"], fresh_port(ge, a["src_ip"], a["dst_ip"], 443), a["dst_ip"], 443, "tcp", "ssl", float(ge.gamma(2, 6)) + 0.3, int(det["bytes_out"]), int(ge.gamma(2, 20000)) + 300)
            out["conn"].append((tf, c))
            out["ssl"].append((tf + 0.05, G.ssl_row(tf + 0.05, c, flag_name(G, a["dst_ip"]))))
    return out


def machine_rows(G, S, d):
    """Periodic machine traffic to the internet on UTC day d, recorded in full: the endpoint agent of every corporate
    Windows host checking in about every eight hours, a number of single-purpose series (licence, update and feed
    checks from one or a few hosts), and the domain controllers' time synchronisation."""
    out = {k: [] for k in ("conn", "dns", "ssl")}
    t0 = D0_EPOCH + d * DAY
    IP = G.IP
    dcs = [IP["GW-SRV-DC-01"], IP["GW-SRV-DC-02"]]
    gd = rng("zeek_machine_dns", d)
    off_a, off_b = G.M.T["sub1_trip"], G.M.T["sub1_trip"] + 12 * 3600

    def series(name, host, period, jitter, first_d, last_d, need_user, k_ip=3):
        if not (first_d <= d <= last_d) or host not in IP:
            return
        h = G.BYNAME[host]
        phase = int(_h("ph", name, host, n=6), 16) % period
        k0 = int((t0 - D0_EPOCH + 70 * DAY - phase) // period)
        for k in range(k0, k0 + int(DAY // period) + 2):
            t = D0_EPOCH - 70 * DAY + phase + k * period + (int(_h("j", name, host, k, n=6), 16) % (2 * jitter + 1) - jitter) + int(_h("f", name, host, k, n=4), 16) / 65536.0
            if not (t0 <= t < t0 + DAY):
                continue
            if host == G.WS04 and (t >= G.WS04_REMOVED or off_a < t < off_b):
                continue
            if h["device_type"] in ("workstation", "laptop") and off_a < t < off_b and int(_h("so", host, n=2), 16) < 190:
                continue                                  # office circuits without generator backing after the feeder trip
            if (need_user or h["device_type"] == "laptop") and not S.user_on(host, t):
                continue
            v = int(_h("v", name, host, k, n=10), 16)
            dst = name_ip(G, name, (v >> 3) % k_ip)
            c = G.conn(t, h["ip"], 49152 + v % 16000, dst, 443, "tcp", "ssl", 0.3 + (v >> 12) % 5200 / 1000.0, 260 + (v >> 20) % 900, 190 + (v >> 28) % 2100)
            out["conn"].append((t, c))
            out["ssl"].append((t + 0.05, G.ssl_row(t + 0.05, c, name, resumed=(v >> 5) % 4 == 0)))
            if (v >> 7) % 4 == 0:
                dr = G.dns_row(t - 0.05 - (v % 400) / 1000.0, h["ip"], dcs[v % 2], name, dst, gd)
                out["dns"].append((float(dr[0]), dr))
                out["conn"].append((float(dr[0]), G.dns_conn(dr)))

    for h in G.WIN_CORP:
        series(AGENT_NAME, h["hostname"], 12 * 3600, 2400, -60, 121, False)
    for name, hosts, period, jitter, a, b, need_user in SERIES:
        for host in hosts:
            series(name, host, period, jitter, a, b, need_user, 1)
    # time synchronisation of the two domain controllers with public time servers (every 1,024 s)
    for i, dc in enumerate(dcs):
        for k in range(int(DAY // 1024) + 1):
            t = t0 + (int(_h("ntp", i, n=4), 16) % 1024) + k * 1024 + int(_h("ntj", d, i, k, n=4), 16) / 65536.0 * 3
            if t >= t0 + DAY:
                continue
            v = int(_h("ntv", d, i, k, n=8), 16)
            out["conn"].append((t, G.conn(t, dc, 49152 + (v >> 8) % 16000, name_ip(G, NTP_SERVERS[(k + i) % 3]), 123, "udp", "ntp", 0.012 + (v % 9000) / 1e5, 48, 48, "SF", "Dd")))
    return out
