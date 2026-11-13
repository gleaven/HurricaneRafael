"""Network sensor logs (stream zeek_logs): conn, dns, ssl, http, files, x509, notice per UTC day.
Called through gen_itsec.py; see its docstring for the sampling rule.

Flows that belong to a record in gen_itsec's model (a gateway session and what it touched, a historian
session, a monitored file write, a setting change, a SCADA command, a mail transfer) are written from that
record by one function per kind, the same for every record of that kind.
"""
import gen_itsec as G
from gen_itsec import (BEACON_IP, BEACON_SNI, BYNAME, CORP, DAY, DNS_Q_T, FIRST_D, HIST1, HISTDMZ, IP, JMP, LAST_D, OPS02, OT01, RTUS, SCADA1, SERVERS, SIEMOT, SITE_IPS, SITES, STATES,
                       WS04, WS04_REMOVED, boundary_open, conn, day_utc, dns_conn, dns_row, frac, home_ip, hsh, pick_state, ssl_row, work_factor, zeek_write)
from common import D0_EPOCH, UTC, dt, np, rng, ts
import ot_model as M

CONN_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "service", "duration", "orig_bytes", "resp_bytes", "conn_state",
          "local_orig", "local_resp", "missed_bytes", "history", "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes"]
CONN_TY = ["time", "string", "addr", "port", "addr", "port", "enum", "string", "interval", "count", "count", "string", "bool", "bool", "count", "string", "count", "count", "count", "count"]
DNS_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "trans_id", "query", "qclass_name", "qtype_name", "rcode_name", "AA", "RD", "RA", "answers", "TTLs"]
DNS_TY = ["time", "string", "addr", "port", "addr", "port", "enum", "count", "string", "string", "string", "string", "bool", "bool", "bool", "vector[string]", "vector[interval]"]
SSL_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "version", "cipher", "server_name", "resumed", "established", "cert_chain_fps"]
SSL_TY = ["time", "string", "addr", "port", "addr", "port", "string", "string", "string", "bool", "bool", "vector[string]"]
NOT_F = ["ts", "uid", "id.orig_h", "id.resp_h", "id.resp_p", "note", "msg", "src", "dst", "p", "actions"]
NOT_TY = ["time", "string", "addr", "addr", "port", "enum", "string", "addr", "addr", "port", "set[enum]"]
MAILGW = "GW-GW-MAIL-01"


def fqdn(host):
    return BYNAME[host]["fqdn"]


def hport(lo, span, *key):
    return lo + int(hsh("port", *key, n=6), 16) % span


def hv(lo, hi, *key):
    """A fixed value in [lo, hi) for a key (sizes and durations of flows written from a model record)."""
    return lo + frac("hv", *key) * (hi - lo)


def field_port(dev):
    water = "UTL" in dev or "WTR" in dev or "WTP" in dev or "TK" in dev
    return (502, "modbus") if water else (20000, "dnp3")


def model_flows():
    """Flows that follow from the model: {day: {log: [(time, row)]}}."""
    import itsec_audit
    import itsec_siem
    out = {}

    def put(kind, t, row):
        out.setdefault(day_utc(t), {}).setdefault(kind, []).append((t, row))

    def flow(t, o, op, r, rp, proto, svc, dur, ob, rb, name=None):
        c = conn(t, o, op, r, rp, proto, svc, dur, ob, rb)
        put("conn", t, c)
        if name:
            put("ssl", t + 0.04, ssl_row(t + 0.04 + frac("sl", c[1]) * 0.08, c, name, resumed=False))
        return c

    dc = IP["GW-SRV-DC-01"]
    g = rng("zeek", "model_dns")
    # ---- the one workstation: periodic connection, the download, the transfer from the historian replica
    for i, bt in enumerate(G.beacon_times()):
        t = bt + frac("bt", bt)
        ob, rb = itsec_siem.beacon_bytes(bt)
        op = hport(49152, 16000, "b", bt)
        flow(t, IP[WS04], op, BEACON_IP, 443, "tcp", "ssl", 4.2 if i == 0 else hv(0.9, 6.8, "bd", bt), ob, rb, BEACON_SNI)
        if i == 0 or frac("bdns", bt) < 0.3:
            dr = dns_row(t - 0.2 - 0.3 * frac("bq", bt), IP[WS04], dc, BEACON_SNI, BEACON_IP, g)
            put("dns", float(dr[0]), dr)
            put("conn", float(dr[0]), dns_conn(dr))
    dr = dns_row(DNS_Q_T + 0.31, IP[WS04], dc, "update-cdn.meridiancontrols.net", BEACON_IP, g)
    put("dns", float(dr[0]), dr)
    put("conn", float(dr[0]), dns_conn(dr))
    flow(DNS_Q_T + 1.2 + 0.13, IP[WS04], 50211, BEACON_IP, 443, "tcp", "ssl", 61.437, 20114, 1884012, "update-cdn.meridiancontrols.net")
    t = ts("2027-09-08T23:58Z") + 14 + 0.412
    flow(t, IP[WS04], 51877, IP[HISTDMZ], 445, "tcp", "smb", 2710.53, 4_118_203, 1_902_447_611)
    # ---- remote-access gateway sessions and what each touched
    hist_by_gw, fim_by_acct, cmd_rd = {}, [], [x for x in G.scada_cmds() if x["origin"] == "remote desktop"]
    for h in G.historian_rows():
        if h["gw"]:
            hist_by_gw.setdefault(h["gw"], []).append(h)
    fim_gw = [f for f in G.fim_rows() if f["source"] == JMP]
    cfg_gw = [c for c in G.cfg_changes() if c["source"] == JMP]
    supp_gw = [b for b in G.suppression_batches() if b["source"] == JMP]
    supp_sess = {}                                    # each change belongs to one session (its author's, where sessions overlap)
    for b in supp_gw:
        c = [r for r in G.gateway_sessions() if r["login"] <= b["t"] <= r["logout"]]
        m = [r for r in c if r["account"] == b["by"]] or c
        if m:
            supp_sess[b["t"]] = m[0]["id"]
    claimed = set()                                   # a record made during two overlapping sessions of one account belongs to the first
    for r in G.gateway_sessions():
        a = r["login"] - 2 + frac("gw", r["id"])
        flow(a, r["src_ip"], hport(40000, 20000, "gw", r["id"]), IP[JMP], 443, "tcp", "ssl", r["dur"] + 2 + frac("gwd", r["id"]), r["bytes_in"], r["bytes_out"], "remote.cbpwa.example")
        lo, hi = r["login"], r["logout"]
        done = set()
        for h in hist_by_gw.get(r["id"], []):
            flow(h["t"] - 0.3 - 0.5 * frac("hf", h["id"]), IP[JMP], hport(52000, 9000, "h", h["id"]), IP[HIST1], 5450, "tcp", "-", h["dur"] + frac("hfd", h["id"]),
                 9000 + h["tags"] * 40 + int(hv(0, 900, "ho", h["id"])), h["tags"] * 5200 + int(hv(0, 40000, "hr", h["id"])))
            done.add(HIST1)
        for f in fim_gw:
            if lo <= f["t"] <= hi and f["user"] == r["account"] and ("f", f["path"], f["t"]) not in claimed:
                claimed.add(("f", f["path"], f["t"]))
                flow(f["t"] - hv(1.2, 4.5, "ff", f["key"]), IP[JMP], hport(53000, 9000, "f", f["key"]), IP[OT01], 445, "tcp", "smb", hv(1.6, 6.5, "fd", f["key"]),
                     int(hv(8000, 90000, "fo", f["key"])), int(hv(1800, 5200, "fr", f["key"])))
                done.add(OT01)
        for c in cfg_gw:
            if lo <= c["t"] <= hi and c["account"] == r["account"] and c["device"] in IP and ("c", c["device"], c["t"]) not in claimed:
                claimed.add(("c", c["device"], c["t"]))
                port, svc = field_port(c["device"])
                flow(c["t"] - hv(3.0, 6.5, "cf", c["t"], c["device"]), IP[JMP], hport(53000, 9000, "c", c["t"], c["device"]), IP[c["device"]], port, "tcp", svc, hv(1.4, 3.4, "cd", c["t"]),
                     int(hv(1900, 2900, "co", c["t"], c["device"])), int(hv(1300, 2300, "cr", c["t"], c["device"])))
                done.add(c["device"])
        for b in supp_gw:
            if supp_sess.get(b["t"]) == r["id"]:
                flow(b["t"] - min(6 + 44 * frac("sf", b["t"]), max(2.5, b["t"] - lo - 4)), IP[JMP], hport(53000, 9000, "s", b["t"]), IP[SCADA1], 3389, "tcp", "rdp", hv(28, 64, "sd", b["t"]),
                     int(hv(14000, 26000, "so", b["t"])), int(hv(190000, 330000, "sr", b["t"])))
                done.add(SCADA1)
        cmds = [x for x in cmd_rd if lo <= x["t"] <= hi and x["ws"] in r["targets"]]
        for ws in sorted({x["ws"] for x in cmds}):
            first, last = min(x["t"] for x in cmds if x["ws"] == ws), max(x["t"] for x in cmds if x["ws"] == ws)
            st = max(lo + 8, first - 80 - 30 * frac("rd", r["id"], ws))
            dur = (last - st) + 40 + 120 * frac("rdd", r["id"], ws)
            flow(st, IP[JMP], hport(52000, 9000, "rd", r["id"], ws), IP[ws], 3389, "tcp", "rdp", dur, int(900 * dur + hv(20000, 90000, "ro", r["id"], ws)), int(17000 * dur + hv(1e5, 6e5, "rr", r["id"], ws)))
            done.add(ws)
        for k, tgt in enumerate(r["targets"]):          # everything else the session opened
            if tgt in done or tgt not in IP:
                continue
            t2 = lo + 7 + (k + 1) * hv(20, 240, "t2", r["id"], tgt)
            left = max(20.0, r["dur"] - (t2 - lo) - 5)
            if t2 >= hi - 5:
                t2 = lo + 6 + frac("t3", r["id"], tgt) * max(1, r["dur"] - 12)
                left = max(4.0, hi - t2 - 2)
            op = hport(52000, 9000, "t", r["id"], tgt)
            if "RTU" in tgt or "DCS" in tgt:
                port, svc = field_port(tgt)
                flow(t2, IP[JMP], op, IP[tgt], port, "tcp", svc, min(left, hv(1.5, 40, "td", r["id"], tgt)), int(hv(400, 6000, "to", r["id"], tgt)), int(hv(300, 9000, "tr", r["id"], tgt)))
            elif tgt == HIST1:
                flow(t2, IP[JMP], op, IP[tgt], 5450, "tcp", "-", min(left, hv(20, 900, "td", r["id"], tgt)), int(hv(2000, 60000, "to", r["id"], tgt)), int(hv(9000, 1.5e6, "tr", r["id"], tgt)))
            elif tgt == OT01:
                flow(t2, IP[JMP], op, IP[tgt], 445, "tcp", "smb", min(left, hv(2, 60, "td", r["id"], tgt)), int(hv(900, 90000, "to", r["id"], tgt)), int(hv(1200, 7e5, "tr", r["id"], tgt)))
            elif tgt == SIEMOT:
                flow(t2, IP[JMP], op, IP[tgt], 443, "tcp", "ssl", min(left, hv(60, 420, "td", r["id"], tgt)), int(hv(6000, 90000, "to", r["id"], tgt)), int(hv(40000, 2.4e6, "tr", r["id"], tgt)),
                     fqdn(SIEMOT))
            else:
                flow(t2, IP[JMP], op, IP[tgt], 3389, "tcp", "rdp", min(left, hv(30, 1500, "td", r["id"], tgt)), int(hv(6000, 2.4e5, "to", r["id"], tgt)), int(hv(40000, 5e6, "tr", r["id"], tgt)))
    # ---- records made from inside the control network or the offices
    for h in G.historian_rows():
        if not h["gw"] and h["client"] in IP:
            flow(h["t"] - 0.3 - 0.5 * frac("hf", h["id"]), IP[h["client"]], hport(49152, 16000, "h", h["id"]), IP[HIST1], 5450, "tcp", "-", h["dur"] + frac("hfd", h["id"]),
                 9000 + h["tags"] * 40 + int(hv(0, 900, "ho", h["id"])), h["tags"] * 5200 + int(hv(0, 40000, "hr", h["id"])))
    for f in G.fim_rows():
        if f["source"] != JMP and f["source"] in IP:
            flow(f["t"] - hv(1.2, 4.5, "ff", f["key"]), IP[f["source"]], hport(49152, 16000, "f", f["key"]), IP[OT01], 445, "tcp", "smb", hv(1.6, 6.5, "fd", f["key"]),
                 int(hv(8000, 90000, "fo", f["key"])), int(hv(1800, 5200, "fr", f["key"])))
    for c in G.cfg_changes():
        if c["source"] not in (JMP, "local panel") and c["source"] in IP and c["device"] in IP:
            port, svc = field_port(c["device"])
            flow(c["t"] - hv(3.0, 6.5, "cf", c["t"], c["device"]), IP[c["source"]], hport(49152, 16000, "c", c["t"], c["device"]), IP[c["device"]], port, "tcp", svc, hv(1.4, 3.4, "cd", c["t"]),
                 int(hv(1900, 2900, "co", c["t"], c["device"])), int(hv(1300, 2300, "cr", c["t"], c["device"])))
    for x in G.scada_cmds():
        if x["ws"] and x["ws"] in IP and x["ws"] not in (SCADA1, "GW-SYS-SCADA-02"):
            flow(x["t"] - hv(0.6, 2.2, "cm", x["t"], x["device"]), IP[x["ws"]], hport(49152, 16000, "cm", x["t"], x["device"]), IP[SCADA1], 4000, "tcp", "-", hv(0.5, 2.6, "cmd", x["t"]),
                 int(hv(520, 1400, "cmo", x["t"], x["device"])), int(hv(380, 1100, "cmr", x["t"], x["device"])))
    # ---- employee VPN: one connection per session, and the remote-desktop session to the person's own desktop where there is one
    for v in G.vpn_sessions():
        flow(v["t"], v["src_ip"], hport(40000, 20000, "vpn", v["id"]), IP["GW-VPN-EMP-01"], 443, "tcp", "ssl", v["dur"], v["bytes_in"], v["bytes_out"], "vpn.cbpwa.example")
        if v["rdp"]:
            r_ = v["rdp"]
            flow(r_["t"] - 0.4 - 0.3 * frac("vr", v["id"]), v["pool_ip"], hport(49152, 16000, "vrdp", v["id"]), IP[r_["host"]], 3389, "tcp", "rdp", r_["dur"],
                 int(700 * r_["dur"] + hv(20000, 90000, "vro", v["id"])), int(15000 * r_["dur"] + hv(1e5, 6e5, "vrr", v["id"])))
    # ---- mail transfers at the gateway for every message in the mail log
    for m in itsec_audit.mail_rows():
        t, direction, snd, dom, rcp, size, verdict = m[0], m[1], m[2], m[3], m[4], m[7], m[8]
        if direction == "internal":
            continue
        k = hsh("smtp", m[10])
        small = verdict == "sender failed authentication"
        ob, rb = (int(900 + int(k[:3], 16) % 700) if small else int(size * 1.37) + 600 + int(k[:3], 16) % 900), 380 + int(k[3:6], 16) % 700
        dur = 0.4 + frac("smd", m[10]) * 2.4 + (0 if small else size / 9e5)
        if direction == "inbound":
            flow(t - dur - 0.2, itsec_audit.mta_ip(dom), hport(32768, 28000, "mi", m[10]), IP[MAILGW], 25, "tcp", "smtp", dur, ob, rb)
        else:
            flow(t + 0.3 + 2 * frac("smo", m[10]), IP[MAILGW], hport(32768, 28000, "mo", m[10]), itsec_audit.mta_ip(rcp.split("@")[1]), 25, "tcp", "smtp", dur, ob, rb)
    return out


NOTE_MSG = {"SSL::Invalid_Server_Cert": "SSL certificate validation failed with (unable to get local issuer certificate)", "SSL::Certificate_Expires_Soon": "Certificate {h} is going to expire soon",
            "DNS::External_Name": "{h} is pointing to a local host", "Conn::Content_Gap": "{h} content gap ({n} bytes missing)", "Weird::Activity": "possible_split_routing",
            "SSH::Password_Guessing": "{h} appears to be guessing SSH passwords (seen in {n} connections)", "HTTP::Unusual_User_Agent": "{h} user agent not seen before on this network"}


def gen_zeek(month=None):
    """month: 'YYYY-MM' to write only the days of that UTC month (the whole span takes a few minutes)."""
    import itsec_zeek_extra as X
    S = G.shared()
    special = model_flows()
    dc = [IP["GW-SRV-DC-01"], IP["GW-SRV-DC-02"]]
    wsip = [h["ip"] for h in CORP]
    srv_h = [h for h in SERVERS if h["ip"].startswith("10.14.")]
    srv = [h["ip"] for h in srv_h]
    admin = [h["ip"] for h in G.IT_ADMIN]
    apps = [h for h in srv_h if any(k in h["hostname"] for k in ("ERP", "CIS", "OMS", "GIS", "WAM", "HR", "INTRA"))]
    sql = [IP["GW-SRV-SQL-01"], IP["GW-SRV-SQL-02"]]
    net_dev = [h["ip"] for h in G.HOSTS if h["device_type"] in ("switch", "router", "firewall") and h["ip"].startswith("10.14.")]
    counts = {"conn": 0, "dns": 0, "ssl": 0, "notice": 0, "http": 0, "files": 0, "x509": 0}
    siem_iter = S.siem_by_day()
    siem_cur = next(siem_iter, None)
    DIR = [(88, "krb", None), (389, "ldap", None), (445, "smb", None), (135, "dce_rpc", None), (636, "ssl", "dc"), (88, "krb", None), (389, "ldap", None)]
    ws04 = IP[WS04]
    for d in range(FIRST_D, LAST_D + 1):
        if month and dt.datetime.fromtimestamp(D0_EPOCH + d * DAY, UTC).strftime("%Y-%m") != month:
            continue
        g = rng("zeek3", d)
        t0 = D0_EPOCH + d * DAY
        wf = np.array([work_factor(t0 + h * 3600 + 1800) for h in range(24)])
        n = int(1500 * (0.25 + wf.mean() * 2.2))
        hsel = g.choice(24, n, p=(wf + 0.05) / (wf + 0.05).sum())
        times = np.sort(t0 + hsel * 3600 + g.random(n) * 3600)
        rows = {k: list(special.get(d, {}).get(k, [])) for k in counts}
        rows["http"], rows["files"] = [], []
        kinds = g.choice(8, n, p=[0.3, 0.14, 0.2, 0.08, 0.08, 0.08, 0.07, 0.05])
        # user-driven traffic comes from machines somebody is logged on to
        g2 = rng("zeek_who", d)
        ld = G.day_of(t0)
        day_sess = [(x["logon"] + 45, x["logoff"], IP[x["host"]]) for dd in (ld - 1, ld, ld + 1) for x in S.interactive_sessions(dd)
                    if x["host"] in G.CORP_NAMES and x["logoff"] > t0 and x["logon"] < t0 + DAY]

        def someone(t):
            c = [ip for a, b, ip in day_sess if a <= t < b and not (ip == ws04 and t >= WS04_REMOVED)]
            return c[int(g2.integers(len(c)))] if c else None

        def add(t, c, name=None):
            rows["conn"].append((t, c))
            if name and c[11] in ("SF", "RSTO", "RSTR"):
                rows["ssl"].append((t + 0.05, ssl_row(t + 0.03 + 0.06 * g.random(), c, name)))

        for t, k in zip(times, kinds):
            o = wsip[g.integers(len(wsip))]
            if o == ws04 and t >= WS04_REMOVED:
                o = wsip[(wsip.index(o) + 1) % len(wsip)]
            op = 49152 + int(g.integers(0, 16000))
            st, hist = pick_state(g)
            if k in (0, 2, 3, 4):
                o = someone(t)
                if o is None:
                    continue
            if k == 0:                                    # web
                site = SITES[g.integers(len(SITES))]
                dst = SITE_IPS[site][int(g.integers(len(SITE_IPS[site])))]
                add(t, conn(t, o, op, dst, 443, "tcp", "ssl", float(g.gamma(2, 9)), int(g.gamma(2, 2200)) + 420, int(g.gamma(2, 60000)) + 2800, st, hist), site)
                if g.random() < 0.5:
                    dr = dns_row(t - 0.05 - 0.4 * g.random(), o, dc[g.integers(2)], site, dst, g)
                    rows["dns"].append((float(dr[0]), dr)); rows["conn"].append((float(dr[0]), dns_conn(dr)))
            elif k == 1:                                  # directory services
                port, svc, nm = DIR[int(g.integers(len(DIR)))]
                dcn = int(g.integers(2))
                add(t, conn(t, o, op, dc[dcn], port, "tcp", svc, float(g.gamma(2, 1.2)), int(g.gamma(2, 1400)) + 200, int(g.gamma(2, 2600)) + 300, st, hist),
                    fqdn(f"GW-SRV-DC-0{dcn + 1}") if nm else None)
            elif k == 2:                                  # dns
                site = SITES[g.integers(len(SITES))]
                dr = dns_row(t, o, dc[g.integers(2)], site, SITE_IPS[site][0], g)
                rows["dns"].append((t, dr)); rows["conn"].append((t, dns_conn(dr)))
                if g.random() < 0.35:                     # the resolver had to ask its forwarder
                    fw = ["96.7.210.53", "64.69.103.53"][int(g.integers(2))]
                    d2 = dns_row(t + 0.001 + 0.004 * g.random(), dr[4], fw, site, SITE_IPS[site][0], g)
                    rows["dns"].append((float(d2[0]), d2)); rows["conn"].append((float(d2[0]), dns_conn(d2)))
            elif k == 3:                                  # mail
                add(t, conn(t, o, op, IP["GW-SRV-MAIL-01"], 443, "tcp", "ssl", float(g.gamma(2, 20)), int(g.gamma(2, 9000)) + 500, int(g.gamma(2, 40000)) + 2400, st, hist), "mail.cbpwa.example")
            elif k == 4:                                  # internal application and file servers, printing
                j = int(g.integers(6))
                if j < 3:
                    h = apps[g.integers(len(apps))]
                    add(t, conn(t, o, op, h["ip"], 443 if j else 8443, "tcp", "ssl", float(g.gamma(2, 14)), int(g.gamma(2, 5000)) + 400, int(g.gamma(2, 30000)) + 2000, st, hist), h["fqdn"])
                elif j < 5:
                    add(t, conn(t, o, op, IP[str(g.choice(["GW-SRV-FILE-01", "GW-SRV-FILE-02"]))], 445, "tcp", "smb", float(g.gamma(2, 14)), int(g.gamma(2, 5000)) + 600, int(g.gamma(2, 90000)) + 900, st, hist))
                else:
                    add(t, conn(t, o, op, IP["GW-SRV-PRINT-01"], 445, "tcp", "smb", float(g.gamma(2, 3)), int(g.gamma(2, 120000)) + 4000, int(g.gamma(2, 1500)) + 500, st, hist))
            elif k == 5:                                  # (the employee VPN is written from the session model, see model_flows)
                pass
            elif k == 6:                                  # historian replication across the IT/OT boundary
                if boundary_open(t):
                    rows["conn"].append((t, conn(t, IP[HIST1], op, IP[HISTDMZ], 5450, "tcp", "-", float(g.gamma(2, 30)), int(g.gamma(2, 2e5)) + 4000, int(g.gamma(2, 4000)) + 300)))
            else:                                         # servers and management
                j = int(g.integers(7))
                if j == 0:
                    rows["conn"].append((t, conn(t, apps[g.integers(len(apps))]["ip"], op, sql[g.integers(2)], 1433, "tcp", "-", float(g.gamma(2, 6)), int(g.gamma(2, 3000)) + 300, int(g.gamma(2, 40000)) + 800, st, hist)))
                elif j == 1:
                    rows["conn"].append((t, conn(t, admin[g.integers(len(admin))], op, srv[g.integers(len(srv))], 5985, "tcp", "-", float(g.gamma(2, 12)), int(g.gamma(2, 9000)) + 700, int(g.gamma(2, 30000)) + 900, st, hist)))
                elif j == 2 and net_dev:
                    rows["conn"].append((t, conn(t, net_dev[g.integers(len(net_dev))], 514, IP["GW-SRV-SIEM-02"], 514, "udp", "syslog", 0.0, int(g.integers(90, 420)), 0, "S0", "D")))
                elif j == 3 and net_dev:
                    rows["conn"].append((t, conn(t, IP["GW-NMS-01"], op, net_dev[g.integers(len(net_dev))], 161, "udp", "snmp", 0.002 + 0.03 * g.random(), int(g.integers(70, 160)), int(g.integers(90, 900)), "SF", "Dd")))
                elif j == 4:
                    dst = (net_dev + srv)[g.integers(len(net_dev) + len(srv))]
                    rows["conn"].append((t, conn(t, IP["GW-NMS-01"], 8, dst, 0, "icmp", "-", 0.0004 + 0.004 * g.random(), 64, 64, "OTH", "-")))
                elif j == 5 and net_dev:
                    rows["conn"].append((t, conn(t, IP["GW-NMS-01"], op, net_dev[g.integers(len(net_dev))], 22, "tcp", "ssh", float(g.gamma(2, 20)) + 1, int(g.gamma(2, 3000)) + 1500, int(g.gamma(2, 9000)) + 2000, st, hist)))
                else:
                    rows["conn"].append((t, conn(t, IP[MAILGW], op, IP["GW-SRV-MAIL-01"], 25, "tcp", "smtp", float(g.gamma(2, 1.2)) + 0.2, int(g.gamma(2, 40000)) + 1800, int(g.integers(300, 900)), st, hist)))
        # IT administrators managing servers by remote desktop
        for _ in range(int(g.poisson(9 * (0.3 + wf.mean())))):
            hh = int(g.choice(24, p=(wf + 0.01) / (wf + 0.01).sum()))
            t = t0 + hh * 3600 + g.random() * 3600
            rows["conn"].append((t, conn(t, admin[g.integers(len(admin))], 49152 + int(g.integers(0, 16000)), srv[g.integers(len(srv))], 3389, "tcp", "rdp", float(g.gamma(2, 500)) + 20, int(g.gamma(2, 8e4)) + 5000, int(g.gamma(2, 1.5e6)) + 30000)))
        # the front-end processors polling field devices (sampled)
        for _ in range(int(g.poisson(30))):
            t = t0 + g.random() * DAY
            rtu = RTUS[int(g.integers(len(RTUS)))]
            port, svc = field_port(rtu)
            rows["conn"].append((t, conn(t, IP[str(g.choice(["GW-SRV-FEP-01", "GW-SRV-FEP-02"]))], 49152 + int(g.integers(0, 16000)), IP[rtu], port, "tcp", svc, float(g.gamma(2, 1.5)) + 0.1, int(g.gamma(2, 600)) + 60, int(g.gamma(2, 2400)) + 120)))
        # nightly backups and the weekly internal vulnerability scan
        for i in range(6):
            t = t0 + 3 * 3600 + i * 1200 + g.random() * 300
            s_ip = srv[(d + i) % len(srv)]
            rows["conn"].append((t, conn(t, s_ip, 51000 + i, IP["GW-SRV-BKP-01"], 10000, "tcp", "-", float(g.uniform(400, 2600)), int(g.gamma(3, 6e8)) + 1000, int(g.gamma(2, 3e5)) + 800)))
        scanner = IP.get("GW-SRV-VULN-01", srv[0])
        if (d % 7) == 2:
            t = t0 + 6 * 3600 + 900 + 40 * g.random()
            rows["notice"].append((t, [f"{t:.6f}", "-", scanner, "-", "-", "Scan::Port_Scan", f"{scanner} scanned at least {int(g.integers(180, 254))} unique hosts on port {int(g.choice([445, 22, 3389, 443]))}/tcp in {int(g.integers(2, 9))}m{int(g.integers(0, 60))}s",
                                       scanner, "-", "-", "Notice::ACTION_LOG"]))
        for _ in range(int(g.poisson(3))):
            t = t0 + g.random() * DAY
            site = SITES[g.integers(len(SITES))]
            note = str(g.choice(["SSL::Invalid_Server_Cert", "SSL::Certificate_Expires_Soon", "DNS::External_Name", "Conn::Content_Gap", "Weird::Activity", "HTTP::Unusual_User_Agent"]))
            src = wsip[g.integers(len(wsip))]
            dst, port, hname = SITE_IPS[site][0], 443, site
            if note == "DNS::External_Name":              # a public name that resolves to one of the utility's own inside addresses
                hname, dst, port = str(g.choice(["portal-test.cbpwa-services.org", "old-intranet.cbpwa.example", "gis-preview.cbpwa-services.org", "lab.cbpwa.example"])), dc[int(g.integers(2))], 53
            elif note == "HTTP::Unusual_User_Agent":
                port = 80
            rows["notice"].append((t, [f"{t:.6f}", "-", src, dst, port, note, NOTE_MSG[note].format(h=hname, n=int(g.integers(40, 9000))), src, dst, port, "Notice::ACTION_LOG"]))
        # the resolvers see more than address lookups: IPv6 lookups, reverse lookups by servers, service discovery at logon, inside names
        gx = rng("zeek_dnsx", d)
        mon = [IP[h] for h in ("GW-SRV-SIEM-02", "GW-NMS-01", "GW-GW-MAIL-01", "GW-SRV-VULN-01") if h in IP]
        for _ in range(int(gx.poisson(330 * (0.2 + wf.mean() * 2.0)))):
            hh = int(gx.choice(24, p=(wf + 0.05) / (wf + 0.05).sum()))
            t = t0 + hh * 3600 + gx.random() * 3600
            kx, site, r5 = gx.random(), SITES[gx.integers(len(SITES))], gx.random()
            o = someone(t)
            dcx = dc[int(gx.integers(2))]
            if kx < 0.38 and o:                           # AAAA beside an address lookup; most of these sites have no IPv6 address
                dr = dns_row(t, o, dcx, site, "-" if r5 < 0.7 else f"2606:{int(gx.integers(4096, 65535)):x}:{int(gx.integers(1, 65535)):x}::{int(gx.integers(1, 65535)):x}", gx)
                dr[10] = "AAAA"
            elif kx < 0.52:                               # reverse lookups by the log collector, the management station, the mail gateway
                h = G.HOSTS[int(gx.integers(len(G.HOSTS)))]
                a4 = h["ip"].split(".")
                dr = dns_row(t, mon[int(gx.integers(len(mon)))], dcx, f"{a4[3]}.{a4[2]}.{a4[1]}.{a4[0]}.in-addr.arpa", h.get("fqdn") or "-", gx)
                if dr[15] == "-":
                    dr[11] = "NXDOMAIN"
                dr[10] = "PTR"
            elif kx < 0.66 and o:                         # service discovery
                q = ["_ldap._tcp.dc._msdcs.corp.cbpwa.example", "_kerberos._tcp.dc._msdcs.corp.cbpwa.example", "_ldap._tcp.Default-First-Site-Name._sites.dc._msdcs.corp.cbpwa.example",
                     "_gc._tcp.corp.cbpwa.example"][int(gx.integers(4))]
                dr = dns_row(t, o, dcx, q, fqdn(f"GW-SRV-DC-0{1 + int(gx.integers(2))}"), gx)
                dr[10] = "SRV"
            elif kx < 0.93 and o:                         # an inside name
                h = srv_h[int(gx.integers(len(srv_h)))]
                dr = dns_row(t, o, dcx, h.get("fqdn") or (h["hostname"].lower() + ".corp.cbpwa.example"), h["ip"], gx)
                dr[12] = "T"
            elif o:                                       # a name that does not exist (mistyped, retired)
                dr = dns_row(t, o, dcx, str(gx.choice(["wpad.corp.cbpwa.example", "isatap.corp.cbpwa.example", "gw-srv-file-03.corp.cbpwa.example", f"www.{site.split('.', 1)[1]}.corp.cbpwa.example"])), "-", gx)
                dr[11] = "NXDOMAIN"
            else:
                continue
            if dr[15] == "-":
                dr[16] = "-"
            rows["dns"].append((float(dr[0]), dr)); rows["conn"].append((float(dr[0]), dns_conn(dr)))
        # plain HTTP, replica readers, patch staging, periodic machine traffic and the flows behind the day's network alerts
        while siem_cur and siem_cur[0] < d:
            siem_cur = next(siem_iter, None)
        for part in (X.extra_rows(G, S, d, siem_cur[1] if siem_cur and siem_cur[0] == d else [], wf, [c for _, c in rows["conn"]]), X.machine_rows(G, S, d)):
            for kname, lst in part.items():
                rows[kname].extend(lst)
        dd = dt.datetime.fromtimestamp(t0, UTC).strftime("%Y-%m-%d")
        srt = {k: [r for _, r in sorted(v, key=lambda x: x[0])] for k, v in rows.items()}
        # a client does not reuse a source port for the same destination within a day: move the later connection to the next free port
        seen, moved = set(), {}
        for c in srt["conn"]:
            if c[6] == "icmp" or int(c[3]) < 1024:
                continue
            k = (c[2], c[3], c[4], c[5], c[6])
            while k in seen:
                c[3] = 1024 + (int(c[3]) - 1023) % 64000
                k = (c[2], c[3], c[4], c[5], c[6])
                moved[c[1]] = c[3]
            seen.add(k)
        if moved:
            for kname in ("dns", "ssl", "http"):
                for r in srt[kname]:
                    if r[1] in moved:
                        r[3] = moved[r[1]]
        uids = {}
        for c in srt["conn"]:
            uids[c[1]] = uids.get(c[1], 0) + 1
        dup = [u for u, n_ in uids.items() if n_ > 1]
        if dup:
            raise SystemExit(f"duplicate uid on {dd}: {dup[:3]}")
        srt["x509"] = X.finish_ssl(srt["ssl"])
        for kname, f, ty in (("conn", CONN_F, CONN_TY), ("dns", DNS_F, DNS_TY), ("ssl", SSL_F, SSL_TY), ("notice", NOT_F, NOT_TY),
                             ("http", X.HTTP_F, X.HTTP_TY), ("files", X.FILES_F, X.FILES_TY), ("x509", X.X509_F, X.X509_TY)):
            counts[kname] += zeek_write(dd, kname, f, ty, srt[kname], t0)
    print(f"zeek_logs{' ' + month if month else ''}:", ", ".join(f"{k} {v:,}" for k, v in counts.items()))
