"""SIEM alerts, rule changes and the daily summary (stream siem_alerts). Called through gen_itsec.py.

Alerts about the historian, the file server and the alarm-suppression list are derived one to one from the
tables in gen_itsec's model, so every such alert has its audit row and the other way round. All other rules
are background: their hourly rate follows who is at work (rules about people), the weather (device rules)
or nothing (the rest). Canon fixes the number of alerts on some days; the rule mix and the hours follow from
the rates. Every alert, whatever it is about, gets its priority, disposition, closing analyst and note from
the same functions.
"""
import bisect

import gen_itsec as G
from gen_itsec import (BEACON_FIRST, BEACON_IP, BEACON_LAST, BYNAME, CORP, CORP_NAMES, DAY, FIRST_D, HIST1, IP, JMP, LAST_D, NET, OT01, RULE_CREATED, RULE_REMOVED, SCADA1, SERVERS,
                       SESSIONS, SOC, SPAN_START, STORM_MODE_OFF, STORM_MODE_ON, SVC, USERS, WL_0117, WS04, WS04_REMOVED, day_utc, frac, hsh, z)
from common import D0_EPOCH, LANDFALL, SPAN_END, UTC, dt, local_dt, local_ts, np, rng, ts, write_csv
import ot_model as M

SIEM_COLS = ["alert_id", "time_utc", "rule_id", "rule_name", "category", "priority", "src_host", "src_ip", "dst_host", "dst_ip", "dst_port",
             "user", "detail", "disposition", "closed_utc", "closed_by", "close_note"]
# id, family, name, category, priority, alerts an hour at full strength, what the rate follows, storm multiplier
RULES = [
    ("1001", "AUTH", "FAILED_LOGON_BURST", "authentication", "LOW", 1.2, "auth", 0),
    ("1007", "AUTH", "ACCOUNT_LOCKOUT", "authentication", "LOW", 0.35, "auth", 0),
    ("1012", "AUTH", "LOGON_OUTSIDE_HOURS", "authentication", "LOW", 0.0, "flat", 0),       # raised from the VPN session model, see specials()
    ("2003", "EP", "PUP_DETECTED", "endpoint", "LOW", 1.2, "people", 0),
    ("2010", "EP", "AGENT_OFFLINE", "endpoint", "LOW", 5, "storm", 3),
    ("2017", "EP", "USB_STORAGE_MOUNTED", "endpoint", "LOW", 1.3, "people", 0),
    ("3004", "NET", "DNS_UNCATEGORISED_DOMAIN", "network", "LOW", 19, "people", 0),
    ("3011", "NET", "INTERNAL_PORT_SWEEP", "network", "LOW", 0.3, "flat", 0),
    ("3020", "NET", "LINK_DOWN", "network", "LOW", 1.0, "storm", 12),
    ("3025", "NET", "VPN_NEW_LOCATION", "network", "LOW", 0.0, "flat", 0),              # raised from the VPN session model, see specials()
    ("9941", "NET", "FLAGGED_IP_OUTBOUND", "network", "LOW", 1.6, "people", 0),
    ("4002", "MAIL", "MAIL_ATTACHMENT_QUARANTINED", "mail", "LOW", 2.2, "mail", 0),
    ("4009", "MAIL", "SPOOFED_SENDER_BLOCKED", "mail", "LOW", 2.0, "mail", 0),
    ("5003", "POL", "POLICY_BLOCKED_SITE", "policy", "INFO", 30, "people", 0),
    ("5011", "POL", "ADMIN_GROUP_CHANGE", "policy", "MEDIUM", 0.2, "it", 0),
    ("6001", "OT", "DEVICE_COMM_LOSS", "ot", "MEDIUM", 0.8, "storm", 10),
    ("6004", "OT", "UPS_ON_BATTERY", "ot", "MEDIUM", 0.2, "storm", 12),
    ("6010", "OT", "MAINT_WINDOW_ACTIVITY", "ot", "INFO", 3, "mail", 0),
    ("7002", "SYS", "LOG_SOURCE_SILENT", "system", "LOW", 1.5, "storm", 4),
    ("7005", "SYS", "DISK_THRESHOLD", "system", "INFO", 2, "flat", 0),
]
# what an analyst writes when closing an alert of each rule (first list: false positive; second: benign true positive)
RULE_NOTES = {
    "FAILED_LOGON_BURST": (["Service account retry", "Shared kiosk account"], ["Password mistyped", "User confirmed", "Password changed, old device", "Shared kiosk account"]),
    "ACCOUNT_LOCKOUT": (["Service account retry"], ["Password mistyped", "Password changed, old device", "User confirmed"]),
    "LOGON_OUTSIDE_HOURS": (["On-call rota"], ["User travelling", "User confirmed", "On-call work", "Working late"]),
    "PUP_DETECTED": (["Benign software", "Expected after patching"], ["Benign software", "Removed by user", "Reimaged"]),
    "AGENT_OFFLINE": (["Agent restarted", "Expected after patching"], ["Laptop asleep", "Powered off overnight", "Agent restarted", "Reimaged"]),
    "USB_STORAGE_MOUNTED": (["Approved removable media"], ["Approved removable media", "User confirmed"]),
    "DNS_UNCATEGORISED_DOMAIN": (["Category corrected"], ["Category corrected", "New vendor site", "Printer firmware lookup"]),
    "INTERNAL_PORT_SWEEP": (["Known scanner", "Monitoring poll"], ["Known scanner", "Printer discovery", "Monitoring poll", "Switch maintenance"]),
    "LINK_DOWN": (["Port flap"], ["Switch maintenance", "Carrier outage", "Port flap", "Cable replaced"]),
    "VPN_NEW_LOCATION": (["New home router"], ["User travelling", "User confirmed", "New home router"]),
    "FLAGGED_IP_OUTBOUND": (["Cloud CDN, whitelisted vendor range", "Whitelisted vendor range", "Known scanner"], ["Benign software", "Whitelisted vendor range", "Cloud CDN, whitelisted vendor range"]),
    "MAIL_ATTACHMENT_QUARANTINED": (["Released on request"], ["User confirmed sender", "Released on request", "Not released"]),
    "SPOOFED_SENDER_BLOCKED": (["Newsletter", "Released on request"], ["Not released", "User informed"]),
    "POLICY_BLOCKED_SITE": (["Category corrected"], ["Approved by manager", "Category corrected"]),
    "ADMIN_GROUP_CHANGE": (["Per change ticket"], ["Per change ticket", "Approved by manager"]),
    "HISTORIAN_BULK_QUERY": (["Reporting run"], ["Per maintenance schedule", "Field crew on site", "Reporting run", "Vendor session with ticket"]),
    "OT_FILE_WRITE": (["Per change ticket"], ["Per maintenance schedule", "Per change ticket", "Field crew on site"]),
    "ALARM_SUPPRESSION_CHANGE": (["Nuisance alarm"], ["Per maintenance schedule", "Nuisance alarm", "Field crew on site"]),
    "SESSION_BEHAVIOUR_ANOMALY": (["Reporting run"], ["Per maintenance schedule", "Reporting run", "Vendor session with ticket"]),
    "DEVICE_COMM_LOSS": (["Sensor fault", "Communications path down"], ["Communications path down", "Field crew on site", "Sensor fault"]),
    "UPS_ON_BATTERY": (["Battery test"], ["Utility power dip", "Battery test", "Field crew on site"]),
    "MAINT_WINDOW_ACTIVITY": (["Per maintenance schedule"], ["Per maintenance schedule"]),
    "LOG_SOURCE_SILENT": (["Collector lag"], ["Log source restarted", "Collector lag", "Host rebooted"]),
    "DISK_THRESHOLD": (["Log rotation"], ["Disk cleaned up", "Log rotation"]),
}
STORM_NOTES = {"AGENT_OFFLINE": ["Site without power", "Storm damage"], "LINK_DOWN": ["Storm damage", "Site without power", "Carrier outage"], "DEVICE_COMM_LOSS": ["Storm damage", "Communications path down"],
               "UPS_ON_BATTERY": ["Site without power", "Storm damage"], "LOG_SOURCE_SILENT": ["Site without power", "Storm damage"]}
OT_AUTH_NOTES = ["Per maintenance schedule", "Vendor session with ticket", "Field crew on site", "Per change ticket"]
RECONNECT = M.T["reconnect"]
PREP_A, PREP_B = LANDFALL - 8 * DAY, LANDFALL                 # the week of storm preparation
REST_B = LANDFALL + 45 * DAY                                  # restoration
RULE_0893 = ts("2027-08-24T15:02Z") + 37
OT_COLS = [i for i, r in enumerate(RULES) if r[3] == "ot"]
SILENT_COL = next(i for i, r in enumerate(RULES) if r[2] == "LOG_SOURCE_SILENT")
CLOSERS = [SOC["SOC-AN-01"]] * 3 + [SOC["SOC-AN-02"]] * 3 + [SOC["SOC-AN-03"]] * 3 + ["aclark", "bflores"]
# address ranges added to the outbound whitelist over the span: (rule, first three octets, when, by whom)
WHITELISTS = [("WL-NET-0109", "151.101.64", ts("2027-07-22T15:41Z") + 13, "imorales"), ("WL-NET-0112", "13.107.6", ts("2027-08-03T19:05Z") + 44, "jperez"),
              ("WL-NET-0115", "52.96.38", ts("2027-08-17T14:48Z") + 9, "tperez"), ("WL-NET-0117", "104.21.88", WL_0117, "tperez"),
              ("WL-NET-0119", "34.117.59", ts("2027-09-08T20:12Z") + 31, "imorales"), ("WL-NET-0121", "142.250.114", ts("2027-10-06T16:30Z") + 52, "jperez"),
              ("WL-NET-0124", "199.232.46", ts("2027-11-09T15:17Z") + 6, "tperez"), ("WL-NET-0126", "23.196.3", ts("2027-12-02T21:44Z") + 27, "imorales")]
# destinations the threat-intelligence feed flags again and again (shared hosting and content-delivery addresses)
_gp = rng("siem_alerts", "flag_pool")
FLAG_POOL = []
for _w, _pfx, _t, _by in WHITELISTS:
    for _k in range(3 if _pfx != "104.21.88" else 0):
        FLAG_POOL.append(f"{_pfx}.{int(_gp.integers(2, 250))}")
FLAG_POOL += ["104.21.88.17", "104.21.88.201", "104.21.88.112", "104.21.88.66"]
FLAG_POOL += [f"{G._PREFIX[int(_gp.integers(len(G._PREFIX)))]}.{int(_gp.integers(1, 250))}.{int(_gp.integers(1, 250))}.{int(_gp.integers(2, 250))}" for _ in range(70)]
_fw = 1.0 / np.arange(1, len(FLAG_POOL) + 1) ** 0.9
_gp.shuffle(_fw)
FLAG_W = _fw / _fw.sum()


def whitelist_for(ip, t):
    for wl, pfx, when, _by in WHITELISTS:
        if ip.startswith(pfx + ".") and t >= when:
            return wl
    return None


def beacon_bytes(bt):
    """(bytes out, bytes in) of the periodic connection at time bt, as the sensor and the SIEM both recorded them."""
    if bt == BEACON_FIRST or bt == BEACON_LAST:
        return 318, 212
    k = int(hsh("bb", bt, n=6), 16)
    return 300 + k % 40, 190 + (k >> 8) % 50


def siem_daily_count(day, g):
    canon_counts = {-2: 4812, -1: 7341, 0: 18340, 1: 16207, 2: 14884, 3: 12201, 4: 6633, 35: 2312}
    if day in canon_counts:
        return canon_counts[day]
    if 5 <= day <= 12:
        return int(6000 - (day - 4) * 430 + g.integers(-90, 90))
    if 28 <= day <= 34:
        _unused = g.normal(0, 0.04)
    l = local_dt(local_ts(day, "12:00"))
    base = 2300 if l.weekday() < 5 else 1750
    return int(base * (1 + g.normal(0, 0.035)))


class Shifts:
    """Who of the security team is on shift, hour by hour."""

    def __init__(self):
        S = G.shared()
        self.t0 = SPAN_START - 2 * DAY
        n = int((SPAN_END + 3 * DAY - self.t0) // 3600)
        self.on = [[] for _ in range(n)]
        for name in sorted(set(CLOSERS)):
            u = S.USER_BY_NAME[name]
            for d in range(FIRST_D - 3, LAST_D + 4):
                w = S.workday(u, d)
                if w:
                    for i in range(max(0, int((w[0] - self.t0) // 3600) + 1), min(n, int((w[1] - self.t0) // 3600))):
                        self.on[i].append(name)
        self.next = [None] * n
        nxt = None
        for i in range(n - 1, -1, -1):
            if self.on[i]:
                nxt = i
            self.next[i] = nxt

    def close(self, t, delay, g):
        """(close time, analyst) for an alert raised at t that somebody gets to after delay seconds."""
        tc = t + delay
        i = int((tc - self.t0) // 3600)
        if i >= len(self.on) or self.next[i] is None:
            return None, None
        if not self.on[i]:
            i = self.next[i]
            tc = self.t0 + i * 3600 + int(g.integers(120, 3300))
        pool = [c for c in CLOSERS if c in self.on[i]]
        return tc, pool[int(g.integers(len(pool)))]


def note_for(name, cat, disp, t, g):
    if disp == "ESCALATED":
        return f"SI-2027-{ {'authentication': 'AU', 'endpoint': 'EP', 'network': 'NW', 'mail': 'ML', 'policy': 'PL', 'ot': 'OT', 'system': 'SY'}.get(cat, 'CC')}-{int(g.integers(2, 900)):03d} opened"
    r = g.random()
    if name in ("HISTORIAN_BULK_QUERY", "OT_FILE_WRITE", "ALARM_SUPPRESSION_CHANGE", "SESSION_BEHAVIOUR_ANOMALY"):
        if PREP_A <= t < PREP_B and r < 0.6:
            return str(g.choice(["Storm preparation", "Storm prep relay adjustment per ops supervisor note", "Storm preparation"])) if disp != "FALSE_POSITIVE" else "Reporting run"
        if PREP_B <= t < REST_B and r < 0.55:
            return str(g.choice(["Restoration work, nuisance alarms", "Storm damage", "Field crew on site"]))
    elif name in STORM_NOTES and LANDFALL - DAY // 2 <= t < LANDFALL + 12 * DAY and r < 0.75:
        v = STORM_NOTES[name]
        return v[int(g.integers(len(v)))]
    if disp == "AUTHORIZED_MAINTENANCE":
        return OT_AUTH_NOTES[int(g.integers(len(OT_AUTH_NOTES)))]
    v = RULE_NOTES[name][0 if disp == "FALSE_POSITIVE" else 1]
    return v[int(g.integers(len(v)))]


def dispose(row, t, g, d, shifts):
    """Priority-independent closing of an alert: bulk dismissal in storm mode, automatic acknowledgement by rule,
    or an analyst on shift."""
    name, cat, prio = row["name"], row["cat"], row["prio"]
    if prio == "INFO" or name == "MAINT_WINDOW_ACTIVITY":
        row.update(disp="AUTO_ACK", closed=t, closed_by="system", note="exception rule MAINT-EXCEPT-0893" if (name == "MAINT_WINDOW_ACTIVITY" and t >= RULE_0893) else "")
    elif STORM_MODE_ON <= t < STORM_MODE_OFF and prio in ("LOW", "MEDIUM") and cat in ("ot", "network", "endpoint", "system"):
        row.update(disp="STORM_BULK_DISMISSED", closed=t + int(g.integers(20, 400)), closed_by="system", note="SE3-BULK-STORM-01")
    elif name == "HISTORIAN_BULK_QUERY" and row.get("src_host") == JMP and RULE_CREATED <= t < RULE_REMOVED:
        row.update(disp="AUTO_ACK", closed=t + 2, closed_by="system", note="exception rule MAINT-EXCEPT-0892")
    elif name == "FLAGGED_IP_OUTBOUND" and whitelist_for(row.get("dst_ip", ""), t):
        wl = whitelist_for(row["dst_ip"], t)
        row.update(disp="AUTO_ACK", closed=t, closed_by="system", note=wl, detail=row["detail"] + f" whitelist={wl}")
    else:
        r = g.random()
        disp = "FALSE_POSITIVE" if r < 0.14 else ("BENIGN_TRUE_POSITIVE" if r < 0.93 else ("AUTHORIZED_MAINTENANCE" if r < 0.985 else "ESCALATED"))
        if name in ("OT_FILE_WRITE", "ALARM_SUPPRESSION_CHANGE"):
            disp = "AUTHORIZED_MAINTENANCE" if r < 0.55 else ("BENIGN_TRUE_POSITIVE" if r < 0.985 else "ESCALATED")
        elif disp == "AUTHORIZED_MAINTENANCE" and cat != "ot":
            disp = "BENIGN_TRUE_POSITIVE"
        # alerts from the control network raised while it was cut off reached the SIEM when it was reconnected
        t_in = RECONNECT + int(g.integers(300, 5400)) if (cat == "ot" and G.ISOLATE <= t < RECONNECT) else t
        tc, who = shifts.close(t_in, int(g.integers(600, 9 * 3600) * (3 if -1 <= d <= 5 else 1)), g)
        nt = note_for(name, cat, disp, t, g)
        if tc is None or tc >= SPAN_END or g.random() < 0.002:
            row.update(disp="OPEN", closed=None, closed_by="", note="")
        else:
            row.update(disp=disp, closed=tc, closed_by=who, note=nt)
    return row


def specials(shifts):
    """Alerts that follow from a record in the model or that canon names: [(time, row)]."""
    out = []

    def add(t, fam, rule, name, cat, prio, **kw):
        row = {"fam": fam, "rule": rule, "name": name, "cat": cat, "prio": prio, "fixed": True}
        row.update(kw)
        out.append((int(t), row))
        return row

    def auto(t, row, key):
        dispose(row, t, rng("siem_alerts", "derived", key), day_utc(t), shifts)

    # periodic outbound connections from one workstation: the first match, then at most one alert every 20 hours
    last = None
    storm_one = ts("2027-09-15T01:17Z") + 21
    for bt in G.beacon_times():
        if not (last is None or bt - last >= 20 * 3600 or bt in (storm_one, BEACON_LAST)):
            continue
        last = bt if bt != storm_one else last
        r = add(bt, "NET", "9941", "FLAGGED_IP_OUTBOUND", "network", "LOW", src_host=WS04, src_ip=IP[WS04], dst_ip=BEACON_IP, dst_port=443, detail=f"bytes_out={beacon_bytes(bt)[0]}",
                named=True)
        if bt == BEACON_FIRST:
            r.update(disp="FALSE_POSITIVE", closed=WL_0117 - 35, closed_by=SOC["SOC-AN-02"], note="Cloud CDN, whitelisted vendor range")
        else:
            auto(bt, r, bt)
    # historian: every bulk read raises the bulk-query rule; the behaviour model scores some sessions
    for h in G.historian_rows():
        sess = h["kind"] == "session"
        if h["qtype"] == "bulk read":
            r = add(h["t"] + 1, "OT", "1104", "HISTORIAN_BULK_QUERY", "ot", "LOW", src_host=h["client"], src_ip=IP.get(h["client"], ""), dst_host=HIST1, dst_ip=IP[HIST1], user=h["account"],
                    detail=f"session_duration={h['dur']}s tags_queried={h['tags']}", named=sess)
            auto(h["t"] + 1, r, h["id"])
        k = frac("ml", h["id"])
        if (sess and h["n"] == 14) or (not sess and k < 0.05):
            gw = next((x for x in G.gateway_sessions() if x["id"] == h["gw"]), None) if h["gw"] else None
            asn = gw["src_network"] if gw else "internal"
            if sess:
                add(h["t"] + 4, "ML", "0044", "SESSION_BEHAVIOUR_ANOMALY", "ot", "ANOMALY_HIGH", src_host=JMP, src_ip=IP[JMP], dst_host=HIST1, dst_ip=IP[HIST1], user=h["account"],
                    detail=f"session_id={h['id']} src_asn={asn} tags_queried={h['tags']} tag_groups={h['groups']} anomaly_score=3.84", disp="ESCALATED", closed=ts("2027-10-02T15:10Z") + 37,
                    closed_by="falrasheedobinna", note="SI-2027-CC-001 opened", named=True)
            else:
                lvl = "ANOMALY_LOW" if k < 0.034 else ("ANOMALY_MEDIUM" if k < 0.046 else "ANOMALY_HIGH")
                sc = {"ANOMALY_LOW": 1.5 + 18 * k, "ANOMALY_MEDIUM": 2.3 + (k - 0.034) * 70, "ANOMALY_HIGH": 3.2 + (k - 0.046) * 300}[lvl]
                r = add(h["t"] + 4, "ML", "0044", "SESSION_BEHAVIOUR_ANOMALY", "ot", lvl, src_host=h["client"], src_ip=IP.get(h["client"], ""), dst_host=HIST1, dst_ip=IP[HIST1],
                        user=h["account"], detail=f"session_id={h['id']} src_asn={asn} tags_queried={h['tags']} tag_groups={h['groups']} anomaly_score={sc:.2f}")
                auto(h["t"] + 4, r, "ml" + h["id"])
                if r["disp"] == "OPEN":                 # the behaviour model's findings are always worked
                    r.update(disp="BENIGN_TRUE_POSITIVE", closed=h["t"] + 7200, closed_by=SOC["SOC-AN-03"], note="Per maintenance schedule")
    # employee VPN: a connection from an address not seen before for that person; a remote-desktop logon to the person's
    # own desktop outside their listed hours
    vpn = BYNAME["GW-VPN-EMP-01"]
    for v in G.vpn_sessions():
        if v["new_location"]:
            r = add(v["t"] + 3, "NET", "3025", "VPN_NEW_LOCATION", "network", "LOW", src_host=vpn["hostname"], src_ip=vpn["ip"], detail=f"user={v['user']} src_ip={v['src_ip']}")
            auto(v["t"] + 3, r, "vl" + v["id"])
        if v["rdp"] and v["rdp"]["alert"]:
            ws = v["rdp"]["host"]
            r = add(v["rdp"]["t"] + 1, "AUTH", "1012", "LOGON_OUTSIDE_HOURS", "authentication", "LOW", src_host=ws, src_ip=IP[ws], user=v["user"], detail=f"logon_type=10 src_ip={v['pool_ip']}")
            auto(v["rdp"]["t"] + 1, r, "vo" + v["id"])
    # file-integrity monitor on the OT file server
    for f in G.fim_rows():
        r = add(f["t"] + 2, "OT", "2201", "OT_FILE_WRITE", "ot", "MEDIUM", src_host=f["source"], src_ip=IP.get(f["source"], ""), dst_host=OT01, dst_ip=IP[OT01], user=f["user"],
                detail="action=FILE_WRITE path=" + f["path"], named=f["kind"] == "session")
        if f["kind"] == "session":
            r.update(disp="AUTHORIZED_MAINTENANCE", closed=ts("2027-09-11T22:58Z"), closed_by=SOC["SOC-AN-01"], note="Storm prep relay adjustment per ops supervisor note")
        else:
            auto(f["t"] + 2, r, f["key"])
    # alarm-suppression list: one alert per change, a daily re-evaluation while the list is over the threshold
    for b in G.suppression_batches():
        r = add(b["t"] + 4, "OT", "3301", "ALARM_SUPPRESSION_CHANGE", "ot", "MEDIUM", src_host=b["source"], src_ip=IP.get(b["source"], ""), dst_host=b["system"], dst_ip=IP.get(b["system"], ""),
                user=b["by"], detail=f"suppressed_alarm_count={b['n']} threshold=30 {'added' if b['delta'] > 0 else 'removed'}={abs(b['delta'])}")
        auto(b["t"] + 4, r, b["t"])
    # while the list is over the threshold the rule re-evaluates it with each alarm-summary job (04:00:11Z and 09:44:16Z) and reports how
    # often it has changed since it was last at its usual size; from twice the threshold the alert is HIGH and stays open until somebody takes it
    since = ts("2027-09-09T00:00Z")
    for d, off in [(d, o) for d in range(FIRST_D, LAST_D + 1) for o in (4 * 3600 + 11, 9 * 3600 + 44 * 60 + 16)]:
        t = D0_EPOCH + d * DAY + off
        n = G.supp_count_at(t)
        if n >= 30:
            b_last = max((b for b in G.suppression_batches() if b["t"] <= t), key=lambda b: b["t"])
            k = sum(1 for b in G.suppression_batches() if since <= b["t"] <= t and b["delta"] > 0)
            r = add(t, "OT", "3301", "ALARM_SUPPRESSION_CHANGE", "ot", "HIGH" if n >= 60 else "MEDIUM", src_host=b_last["source"], src_ip=IP.get(b_last["source"], ""),
                    dst_host=SCADA1, dst_ip=IP[SCADA1], detail=f"suppressed_alarm_count={n} threshold=30 change_count_since_2027-09-09={k}", named=True)
            if n >= 60:
                r.update(disp="OPEN", closed=None, closed_by="", note="")
            else:
                auto(t, r, "re" + str(d) + ("" if off > 5 * 3600 else "n"))
    return out


def background(t, rule, g, d, shifts, S, last_auth):
    rid, fam, name, cat, prio, _w, _kind, _m = rule
    h = CORP[g.integers(len(CORP))] if cat in ("authentication", "endpoint", "policy", "mail", "network") else SERVERS[g.integers(len(SERVERS))]
    if h["hostname"] == WS04 and t >= WS04_REMOVED:
        h = CORP[(CORP.index(h) + 1) % len(CORP)]
    u = USERS[g.integers(len(USERS))]
    user = u["username"]
    act = [x for x in S.sessions_at(t) if (x["host"] in CORP_NAMES or cat == "authentication") and x["logon"] + 180 <= t < x["logoff"] - 180]
    if name in ("FAILED_LOGON_BURST", "ACCOUNT_LOCKOUT"):      # the SIEM raises one such alert per account per quarter of an hour
        act = [x for x in act if t - last_auth.get((name, x["user"]), 0) > 900]
    if name == "LOGON_OUTSIDE_HOURS":                 # someone who is not at work now and not away, on their own workstation
        for _ in range(16):
            c = USERS[g.integers(len(USERS))]
            if not S.away(c, t) and not S.on_shift(c, t) and c.get("normal_hosts") and c["normal_hosts"][0] in CORP_NAMES and c["normal_hosts"][0] != WS04:
                h, user = BYNAME[c["normal_hosts"][0]], c["username"]
                break
    elif cat == "mail":                                # raised by the mail gateway for a recipient
        h = BYNAME["GW-GW-MAIL-01"]
    elif name in ("FAILED_LOGON_BURST", "ACCOUNT_LOCKOUT", "POLICY_BLOCKED_SITE", "ADMIN_GROUP_CHANGE", "PUP_DETECTED", "USB_STORAGE_MOUNTED",
                  "DNS_UNCATEGORISED_DOMAIN", "FLAGGED_IP_OUTBOUND"):
        if name == "ADMIN_GROUP_CHANGE":
            act = [x for x in act if S.USER_BY_NAME[x["user"]]["department"] == "IT Infrastructure"]
        if act and (g.random() < 0.93 or name == "ADMIN_GROUP_CHANGE"):
            x = act[g.integers(len(act))]
            h, user = BYNAME[x["host"]], x["user"]
        elif cat == "authentication":                  # nobody at a desk: a service account retrying
            for _ in range(8):
                sa = SVC[g.integers(len(SVC))]
                if t - last_auth.get((name, sa["account"]), 0) > 900:
                    break
            h, user = BYNAME[sa["normal_hosts"][0]], sa["account"]
        elif name == "ADMIN_GROUP_CHANGE":             # no administrator at a desk: the directory-synchronisation service
            h, user = BYNAME["GW-SRV-DC-01"], "svc_ecm"
        else:
            user = ""                                  # machine traffic
            if name == "POLICY_BLOCKED_SITE" and act:  # a blocked page is always somebody's request
                x = act[int(hsh("polu", t, h["hostname"], n=6), 16) % len(act)]
                h, user = BYNAME[x["host"]], x["user"]
    last_auth[(name, user)] = t
    row = {"fam": fam, "rule": rid, "name": name, "cat": cat, "prio": prio, "src_host": h["hostname"], "src_ip": h["ip"]}
    if cat in ("authentication", "policy", "mail"):
        row["user"] = user
    if name == "DNS_UNCATEGORISED_DOMAIN":
        row["detail"] = "query=" + G.uncat_name(g)
    elif name == "INTERNAL_PORT_SWEEP":
        row["detail"] = f"targets={int(g.integers(8, 15))} port={int(g.choice([445, 3389, 22, 80, 443, 161, 9100, 135]))}"
    elif name == "VPN_NEW_LOCATION":
        v = BYNAME["GW-VPN-EMP-01"]
        for _ in range(12):
            if not S.away(u, t):
                break
            u = USERS[g.integers(len(USERS))]
        row.update(src_host=v["hostname"], src_ip=v["ip"], detail=f"user={u['username']} src_ip={G.home_ip(g)}")
    elif name == "FLAGGED_IP_OUTBOUND":
        row.update(dst_ip=FLAG_POOL[int(g.choice(len(FLAG_POOL), p=FLAG_W))], dst_port=443, detail=f"bytes_out={int(g.gamma(2, 900)) + 180}")
    elif name in ("DEVICE_COMM_LOSS", "UPS_ON_BATTERY", "LINK_DOWN", "AGENT_OFFLINE", "LOG_SOURCE_SILENT"):
        storm = max(0.0, 1 - abs((t - LANDFALL) / DAY - 0.8) / 4.5)
        dur = int(min(86400 * 3, np.exp(g.normal(np.log(480) + 1.6 * storm, 1.25)))) + 20
        row["detail"] = f"duration={dur}s"
        if name != "AGENT_OFFLINE" and dur >= 4 * 3600:
            row["prio"] = "HIGH"
    elif name == "FAILED_LOGON_BURST":
        row["detail"] = f"failures={int(g.integers(5, 14))} window=300s"
    return dispose(row, t, g, d, shifts)


def gen_siem():
    S = G.shared()
    g = rng("siem_alerts", "v3")
    shifts = Shifts()
    by_day = {}
    for t, row in specials(shifts):
        by_day.setdefault(day_utc(t), []).append((t, row))
    days = list(range(FIRST_D, LAST_D + 1))
    counts = {d: siem_daily_count(d, g) for d in days}
    it_names = {u["username"] for u in USERS if u["department"] == "IT Infrastructure"}

    # hourly strength of each rule on each day (before the storm multiplier)
    def presence(d):
        t0 = D0_EPOCH + d * DAY
        pc, pa, pi = np.zeros(24), np.zeros(24), np.zeros(24)
        for hh in range(24):
            ss = S.sessions_at(t0 + hh * 3600 + 1800)
            pc[hh] = sum(1 for x in ss if x["host"] in CORP_NAMES) / 125.0
            pa[hh] = len(ss) / 135.0
            pi[hh] = min(1.0, sum(1 for x in ss if x["user"] in it_names) / 6.0)
        return pc, pa, pi

    def strengths(d):
        pc, pa, pi = presence(d)
        base, storm = np.zeros((24, len(RULES))), np.zeros((24, len(RULES)))
        for j, (_i, _f, _n, _c, _p, w, kind, mult) in enumerate(RULES):
            base[:, j] = w * {"people": pc, "auth": pa, "it": pi, "mail": 0.22 + 0.78 * pc}.get(kind, np.ones(24))
            storm[:, j] = w * mult
        return base, storm

    st = {d: strengths(d) for d in days}
    k = 2300.0 / float(np.mean([st[d][0].sum() for d in (-40, -39, -35, -34, -33)]))      # ordinary weekdays
    boost_mid = {}
    for d in days:
        need = counts[d] / k - st[d][0].sum()
        boost_mid[d] = max(0.0, need / st[d][1].sum()) if -3 <= d <= 13 and need > 0.08 * st[d][0].sum() else 0.0
    xs = np.array([D0_EPOCH + d * DAY + 12 * 3600 for d in days], float)
    ys = np.array([boost_mid[d] for d in days])
    files, daily, last_auth = {}, [], {}
    for d in days:
        t0 = D0_EPOCH + d * DAY
        base, storm = st[d]
        b = np.interp(t0 + np.arange(24) * 3600 + 1800, xs, ys)
        W = base + storm * b[:, None]
        # while the control network is cut off its devices and collector cannot be evaluated: their rules fall silent
        # (the corporate rules carry on), and the SIEM notices the missing log sources
        full = W.sum()
        for hh in range(24):
            if G.ISOLATE <= t0 + hh * 3600 + 1800 < RECONNECT:
                W[hh, OT_COLS] = 0.0
                W[hh, SILENT_COL] *= 2.5
        n_bg = max(0, counts[d] - len(by_day.get(d, [])))
        if d != 35 and W.sum() < full:
            n_bg = int(round(n_bg * W.sum() / full))
        pick = g.choice(W.size, n_bg, p=(W / W.sum()).ravel())
        times = np.sort(t0 + (pick // len(RULES)) * 3600 + g.integers(0, 3600, n_bg))
        order = np.argsort(t0 + (pick // len(RULES)) * 3600, kind="stable")
        rule_of = (pick % len(RULES))[order]
        rows = list(by_day.get(d, []))
        for t, ri in zip(times, rule_of):
            rows.append((int(t), background(int(t), RULES[int(ri)], g, d, shifts, S, last_auth)))
        rows.sort(key=lambda x: x[0])
        if d == 35:                       # the day's audit states the false-positive rate
            want = round(0.113 * len(rows))
            cand = [i for i, (_t, r) in enumerate(rows) if not r.get("fixed") and r["disp"] in ("FALSE_POSITIVE", "BENIGN_TRUE_POSITIVE")]
            have_fixed = sum(1 for _t, r in rows if r["disp"] == "FALSE_POSITIVE" and r.get("fixed"))
            chosen = set(g.choice(cand, want - have_fixed, replace=False).tolist())
            for i in cand:
                r = rows[i][1]
                r["disp"] = "FALSE_POSITIVE" if i in chosen else "BENIGN_TRUE_POSITIVE"
                r["note"] = note_for(r["name"], r["cat"], r["disp"], rows[i][0], g)
        # alert ids: rule and minute, with a counter when a rule fires more than once in a minute (alerts canon names keep the plain id)
        seen = {}
        for t, row in sorted(rows, key=lambda x: (x[0] // 60, not x[1].get("named"), x[0])):
            base_id = f"SE3-{row['fam']}-{row['rule']}-{dt.datetime.fromtimestamp(t, UTC):%Y%m%dT%H%MZ}"
            c = seen.get(base_id, 0)
            seen[base_id] = c + 1
            row["alert_id"] = base_id if c == 0 else f"{base_id}-{c + 1}"
        mon = dt.datetime.fromtimestamp(t0, UTC).strftime("%Y-%m")
        for t, row in rows:
            files.setdefault(mon, []).append([row["alert_id"], z(t), f"SE3-{row['fam']}-{row['rule']}", row["name"], row["cat"], row["prio"], row.get("src_host", ""),
                                              row.get("src_ip", ""), row.get("dst_host", ""), row.get("dst_ip", ""), row.get("dst_port", ""), row.get("user", ""),
                                              row.get("detail", ""), row["disp"], z(row["closed"]) if row.get("closed") else "", row.get("closed_by", ""), row.get("note", "")])
        fp = sum(1 for _, r in rows if r["disp"] == "FALSE_POSITIVE")
        daily.append([dt.datetime.fromtimestamp(t0, UTC).strftime("%Y-%m-%d"), len(rows), fp, f"{100 * fp / max(1, len(rows)):.1f}",
                      sum(1 for _, r in rows if r["disp"] == "OPEN" and r["fam"] == "ML")])
    total = 0
    for mon, rows in sorted(files.items()):
        total += write_csv(f"{NET}/siem/siem_alerts_{mon}.csv", SIEM_COLS, rows)
    write_csv(f"{NET}/siem/daily_summary.csv", ["date_utc", "alerts", "closed_false_positive", "false_positive_rate_pct", "open_ml_anomaly_alerts"], daily)
    write_csv(f"{NET}/siem/rule_changes.csv", ["time_utc", "action", "rule_id", "rule_type", "description", "changed_by", "change_ticket"], rule_changes(shifts))
    print(f"siem_alerts: {total:,} alerts in {len(files)} files")


def rule_changes(shifts):
    """The SIEM's rule-change log: whitelist and exception changes, tuning, storm mode, the audit."""
    g = rng("siem_alerts", "rule_changes")
    rows = [[z(RULE_CREATED), "CREATE", "MAINT-EXCEPT-0892", "exception", "auto-acknowledge SE3-OT-1104 when source is GW-SYS-JMP-01", "svc_fieldops_ext", ""],
            [z(RULE_0893), "CREATE", "MAINT-EXCEPT-0893", "exception", "auto-acknowledge SE3-OT-6010 during approved windows", "aclark", G.cite_chg(RULE_0893, "0893")],
            [z(STORM_MODE_ON), "ACTIVATE", "SE3-BULK-STORM-01", "bulk dismissal",
             "storm mode: dismiss LOW and MEDIUM alerts from the 44 sources on the storm whitelist (device availability, network, endpoint and OT maintenance)", SOC["SOC-AN-01"], "EOC-ACT-27-09"],
            [z(STORM_MODE_OFF), "DEACTIVATE", "SE3-BULK-STORM-01", "bulk dismissal", "storm mode ended", SOC["SOC-AN-01"], "EOC-ACT-27-09"],
            [z(RULE_REMOVED), "DELETE", "MAINT-EXCEPT-0892", "exception", "removed (AUDIT-EXC-2027-10)", "falrasheedobinna", "SI-2027-CC-001"],
            [z(ts("2027-10-19T00:30Z") + 52), "REPORT", "AUDIT-EXC-2027-10", "audit", "exception rule audit complete: 41 rules reviewed, 1 removed", "bflores", "SI-2027-CC-001"]]
    for wl, pfx, when, by in WHITELISTS:
        rows.append([z(when), "UPDATE", wl, "whitelist", f"{pfx}.0/24 added to {'vendor CDN' if int(wl[-1]) % 2 else 'trusted SaaS'} range", by, ""])
    excs = ["auto-acknowledge SE3-EP-2010 for field laptops outside working hours", "auto-acknowledge SE3-SYS-7005 on backup volumes during the backup window",
            "auto-acknowledge SE3-NET-3011 when source is the vulnerability scanner", "auto-acknowledge SE3-OT-6001 for substations under planned work",
            "auto-acknowledge SE3-AUTH-1012 for the on-call rota", "auto-acknowledge SE3-NET-3020 on the redundant core uplink during maintenance",
            "auto-acknowledge SE3-OT-1104 when source is the reporting server", "auto-acknowledge SE3-MAIL-4002 for the scan-to-mail printers"]
    tune = ["threshold raised from 5 to 8 failures", "window widened from 300 s to 600 s", "priority lowered to INFO", "added device group field-laptops", "description corrected",
            "threshold lowered from 40 to 30", "suppression window shortened to 15 min"]
    for i in range(46):
        t = local_ts(int(g.integers(-58, 118)), f"{int(g.integers(7, 19)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
        tc, who = shifts.close(t, 0, g)
        k, r = int(g.integers(4)), g.random()
        _n, r6 = int(g.integers(700, 1990)), g.random()
        if tc is None or FREEZE(t):
            continue
        tk = G.cite_chg(tc, "rule", i) if r6 < 0.6 else ""
        if k == 0:
            n = 880 + i
            by = who if r < 0.75 else str(g.choice(["svc_vantage_mgmt", "svc_meridian_support"]))
            rows.append([z(tc), "CREATE", f"MAINT-EXCEPT-{n:04d}", "exception", excs[int(g.integers(len(excs)))], by, tk if by == who else f"VND-{int(g.integers(3000, 3999))}"])
            if g.random() < 0.3:
                rows.append([z(tc + int(g.integers(5, 60)) * DAY), "DELETE", f"MAINT-EXCEPT-{n:04d}", "exception", "expired", who, ""])
        else:
            ru = RULES[int(g.integers(len(RULES)))]
            rows.append([z(tc), "UPDATE", f"SE3-{ru[1]}-{ru[0]}", "detection", tune[int(g.integers(len(tune)))], who, tk])
    rows = [r for r in rows if r[0] < z(SPAN_END)]
    rows.sort(key=lambda r: r[0])
    return rows


def FREEZE(t):
    return STORM_MODE_ON - DAY <= t < STORM_MODE_OFF
