"""IT and security logs for the utility and the aid portal (streams siem_alerts, zeek_logs,
host_audit_logs, portal_access_logs).

    python3 scripts/streams/gen_itsec.py [siem] [zeek] [audit] [portal]      (no argument = all)

Everything here is observation data: what a mail gateway, a remote-access gateway, a historian,
a network sensor, a SIEM and a web portal would have recorded. Records say who connected to
what, when, and what changed; they contain no instructions and no explanation of intent.

Shared clock rule (same as the OT family, see ot_model.py): where canon gives an event to the
minute, the physical effect is at second 00 + int(sha256(event_id), 16) % 50; the log evidence
that precedes an effect (logon, session attach, write request) leads it by a few seconds.
Remote sessions come from ot_model.KNOWN_REMOTE_SESSIONS so the historian's session-count tags
and these logs agree to the second.

Background network flows are sampled 1 in 200 (stated in the schema); flows that involve the
hosts canon cares about are complete.
"""
import csv
import hashlib
import os
import sys

from common import *            # noqa: F401,F403
import ot_model as M

NET = "05_other_sources/network_logs"
OLD = None
DAY = 86400
SPAN_START = D0_EPOCH - 60 * 86400       # this family starts at the scenario start (2027-07-16) so there is a long quiet baseline
H = reg("gw_host_registry")
HOSTS = H["hosts"]
BYNAME = {h["hostname"]: h for h in HOSTS}
IP = {h["hostname"]: h["ip"] for h in HOSTS}
USERS = H["users"]
EXT = {e["system_id"]: e for e in H["external_systems"]}
WORKST = [h for h in HOSTS if h["device_type"] in ("workstation", "laptop")]
SERVERS = [h for h in HOSTS if h["device_type"] in ("server", "historian", "scada server", "storage", "appliance")]
ENGINEERS = [u for u in USERS if u.get("ot_account")]
SOC = {"SOC-AN-01": "jperez", "SOC-AN-02": "tperez", "SOC-AN-03": "imorales"}

WS04, JMP, HIST1, HISTDMZ, SCADA1, OPS02 = "GW-WS-IT-04", "GW-SYS-JMP-01", "GW-SRV-HIST-01", "GW-SRV-HIST-DMZ", "GW-SYS-SCADA-01", "GW-WS-OPS-02"
BEACON_IP, BEACON_SNI = "104.21.88.43", "update-cdn.vantagesec-telemetry.net"
BEACON_FIRST, BEACON_LAST = ts("2027-08-31T03:17Z") + 12, ts("2027-10-12T10:04Z") + 37
# canon correction: the lure reaches the mailbox the morning before the first beacon
LURE_T = ts("2027-08-30T13:14Z") + 9
AV_OFF_T = ts("2027-08-30T13:21Z") + 44
DNS_Q_T = ts("2027-08-30T13:23Z") + 2
RULE_CREATED = ts("2027-08-19T11:34Z") + 20
RULE_REMOVED = ts("2027-10-18T15:20Z")
STORM_MODE_ON, STORM_MODE_OFF = ts("2027-09-14T06:14Z") + 5, ts("2027-09-18T14:00Z")
ISOLATE = M.T["isolate"]
WS04_USER = next((u for u in USERS if WS04 in u.get("normal_hosts", [])), USERS[10])
VELA = next(u for u in USERS if u["username"] == "rvela")

# the fourteen out-of-hours sessions: (start, seconds, source address, country, network label)
_SRC = (["185.220.101.%d" % n for n in (34, 34, 71, 12, 34, 88, 71)] + ["185.220.101.34", "185.220.101.12"] +
        ["198.51.47.19", "45.141.152.61", "45.141.152.61", "198.51.48.203", "45.141.152.118"])
_CC = ["DE"] * 9 + ["RO", "NL", "NL", "SG", "NL"]
SESSIONS = []
for i, (a, dur) in enumerate(sorted(M.KNOWN_REMOTE_SESSIONS)):
    SESSIONS.append({"n": i + 1, "start": int(a), "dur": int(dur), "ip": _SRC[i], "cc": _CC[i],
                     "asn": "AS-209144" if _CC[i] != "DE" else "AS-60729"})
# tags read per session: first 847, last 1,241, total 11,847
_TAGS = [847, 912, 1004, 760, 1188, 931, 1010, 640, 388, 702, 455, 913, 856, 1241]
assert sum(_TAGS) == 11847
_BYTES_OUT = [412_884_113, 218_640_927, 631_277_405, 377_915_662, 948_103_388, 839_226_740, 671_951_765] + [3_118_442, 2_207_915, 1_904_371, 1_126_608, 2_588_930, 913_277, 4_402_159]   # first seven total 4.1 GB
for s, tg, b in zip(SESSIONS, _TAGS, _BYTES_OUT):
    s["tags"], s["bytes_out"] = tg, int(b)
    d = local_dt(s["start"]).astimezone(UTC)
    s["hist_id"] = None
SESSIONS[0]["hist_id"], SESSIONS[-1]["hist_id"] = "HIST-20270907-00441", "HIST-20271002-00917"


def z(t):
    return iso(t)


def hsh(*k, n=16):
    return hashlib.sha256("|".join(map(str, k)).encode()).hexdigest()[:n]


def work_factor(t):
    """Share of normal office activity at epoch t (hour of day, weekend, storm, evacuation)."""
    l = local_dt(t)
    f = 1.0 if 7 <= l.hour < 18 else (0.25 if 5 <= l.hour < 22 else 0.06)
    if l.weekday() >= 5:
        f *= 0.25
    d = (t - D0_EPOCH) / DAY
    if -1.5 <= d < 0.2:
        f *= 0.35
    elif 0.2 <= d < 4:
        f *= 0.18
    elif 4 <= d < 14:
        f *= 0.6
    return f


def months():
    out, t = [], SPAN_START
    while t < SPAN_END:
        d = dt.datetime.fromtimestamp(t, UTC)
        nxt = dt.datetime(d.year + (d.month == 12), d.month % 12 + 1, 1, tzinfo=UTC).timestamp()
        out.append((f"{d.year}-{d.month:02d}", int(t), int(min(nxt, SPAN_END))))
        t = nxt
    return out


# ======================================================================================
# SIEM
# ======================================================================================
SIEM_COLS = ["alert_id", "time_utc", "rule_id", "rule_name", "category", "priority", "src_host", "src_ip", "dst_host", "dst_ip", "dst_port",
             "user", "detail", "disposition", "closed_utc", "closed_by", "close_note"]
RULES = [  # id, family, name, category, priority, weight (ordinary days), storm weight
    ("1001", "AUTH", "FAILED_LOGON_BURST", "authentication", "LOW", 16, 4),
    ("1007", "AUTH", "ACCOUNT_LOCKOUT", "authentication", "LOW", 5, 2),
    ("1012", "AUTH", "LOGON_OUTSIDE_HOURS", "authentication", "LOW", 6, 5),
    ("2003", "EP", "PUP_DETECTED", "endpoint", "LOW", 5, 1),
    ("2010", "EP", "AGENT_OFFLINE", "endpoint", "LOW", 6, 30),
    ("2017", "EP", "USB_STORAGE_MOUNTED", "endpoint", "LOW", 4, 1),
    ("3004", "NET", "DNS_UNCATEGORISED_DOMAIN", "network", "LOW", 9, 2),
    ("3011", "NET", "INTERNAL_PORT_SWEEP", "network", "LOW", 5, 1),
    ("3020", "NET", "LINK_DOWN", "network", "LOW", 2, 34),
    ("3025", "NET", "VPN_NEW_LOCATION", "network", "LOW", 3, 6),
    ("9941", "NET", "FLAGGED_IP_OUTBOUND", "network", "LOW", 1.2, 0.3),
    ("4002", "MAIL", "MAIL_ATTACHMENT_QUARANTINED", "mail", "LOW", 7, 2),
    ("4009", "MAIL", "SPOOFED_SENDER_BLOCKED", "mail", "LOW", 5, 2),
    ("5003", "POL", "POLICY_BLOCKED_SITE", "policy", "INFO", 12, 2),
    ("5011", "POL", "ADMIN_GROUP_CHANGE", "policy", "MEDIUM", 0.6, 0.2),
    ("1104", "OT", "HISTORIAN_BULK_QUERY", "ot", "LOW", 1.0, 0.4),
    ("2201", "OT", "OT_FILE_WRITE", "ot", "MEDIUM", 0.5, 0.2),
    ("3301", "OT", "ALARM_SUPPRESSION_CHANGE", "ot", "MEDIUM", 0.3, 0.2),
    ("6001", "OT", "DEVICE_COMM_LOSS", "ot", "MEDIUM", 1.5, 22),
    ("6004", "OT", "UPS_ON_BATTERY", "ot", "MEDIUM", 0.4, 9),
    ("6010", "OT", "MAINT_WINDOW_ACTIVITY", "ot", "INFO", 4, 1),
    ("7002", "SYS", "LOG_SOURCE_SILENT", "system", "LOW", 2, 12),
    ("7005", "SYS", "DISK_THRESHOLD", "system", "INFO", 2, 1),
]
NOTES_BY_CAT = {"authentication": ["Password mistyped", "User travelling", "Shared kiosk account", "Service account retry"],
                "endpoint": ["Benign software", "Approved removable media", "Laptop asleep", "Reimaged"],
                "network": ["Known scanner", "Switch maintenance", "Carrier outage", "Printer firmware lookup", "Whitelisted vendor range"],
                "mail": ["Newsletter", "User confirmed sender", "Released on request"], "policy": ["Category corrected", "Approved by manager"],
                "ot": ["Per maintenance schedule", "Field crew on site", "Storm damage", "Communications path down"],
                "system": ["Log source restarted", "Disk cleaned up", "Collector lag"]}
CLOSE_NOTES = {"FALSE_POSITIVE": ["Known scanner", "User confirmed", "Benign software", "Whitelisted vendor range", "Expected after patching"],
               "BENIGN_TRUE_POSITIVE": ["Password mistyped", "User travelling", "Approved removable media", "Printer firmware lookup"],
               "AUTO_ACK": [""], "AUTHORIZED_MAINTENANCE": ["Per maintenance schedule", "Vendor session with ticket"],
               "STORM_BULK_DISMISSED": ["SE3-BULK-STORM-01"], "ESCALATED": ["Ticket opened"], "OPEN": [""]}


def siem_daily_count(day, g):
    canon_counts = {-2: 4812, -1: 7341, 0: 18340, 1: 16207, 2: 14884, 3: 12201, 4: 6633, 35: 2312}
    if day in canon_counts:
        return canon_counts[day]
    if 5 <= day <= 12:
        return int(6000 - (day - 4) * 430 + g.integers(-90, 90))
    if day == 28:
        return None                      # handled by hour (drop after 08:00Z)
    if 29 <= day <= 34:
        return int([232, 251, 244, 610, 1480, 1935][day - 29] * (1 + g.normal(0, 0.04)))   # sources come back in batches
    l = local_dt(local_ts(day, "12:00"))
    base = 2300 if l.weekday() < 5 else 1750
    return int(base * (1 + g.normal(0, 0.035)))


def gen_siem():
    g = rng("siem_alerts")
    retire([f"{NET}/siem_alerts.csv"])
    special = siem_specials()
    by_day = {}
    for t, row in special:
        by_day.setdefault(day_utc(t), []).append((t, row))
    files = {}
    seen_ids = {}
    daily = []
    first_day, last_day = day_utc(SPAN_START), day_utc(SPAN_END - 1)
    for d in range(first_day, last_day + 1):
        t0 = D0_EPOCH + d * DAY
        n = siem_daily_count(d, g)
        storm = min(1.0, max(0.0, 1 - abs(d - 0.8) / 4.5)) if -2 <= d <= 5 else 0.0
        w = np.array([r[5] * (1 - storm) + r[6] * storm for r in RULES], float)
        w /= w.sum()
        if n is None:                    # the day external connectivity is cut: ~90 % fewer alerts after 08:00Z
            before = int(2300 * 8 / 24 * 1.05)
            after = int(2300 * 16 / 24 * 0.1)
            times = np.concatenate([t0 + np.sort(g.integers(0, 8 * 3600, before)), t0 + 8 * 3600 + np.sort(g.integers(0, 16 * 3600, after))])
        else:
            n_bg = max(0, n - len(by_day.get(d, [])))
            hours = np.array([work_factor(t0 + h * 3600 + 1800) + 0.35 + 1.4 * storm for h in range(24)])
            hsel = g.choice(24, n_bg, p=hours / hours.sum())
            times = np.sort(t0 + hsel * 3600 + g.integers(0, 3600, n_bg))
        rows = list(by_day.get(d, []))
        ridx = g.choice(len(RULES), len(times), p=w)
        for t, ri in zip(times, ridx):
            rows.append((int(t), siem_background(int(t), RULES[ri], g, d)))
        rows.sort(key=lambda x: x[0])
        fp_target = None
        if d == 35:                       # the day's audit states the false-positive rate
            fp_target = set(g.choice(len(rows), round(0.113 * len(rows)), replace=False).tolist())
        mon = dt.datetime.fromtimestamp(t0, UTC).strftime("%Y-%m")
        for k, (t, row) in enumerate(rows):
            stamp = dt.datetime.fromtimestamp(t, UTC).strftime("%Y%m%dT%H%MZ")
            base = f"SE3-{row['fam']}-{row['rule']}-{stamp}"
            c = seen_ids.get(base, 0)
            seen_ids[base] = c + 1
            aid = row.get("alert_id") or (base if c == 0 else f"{base}-{c + 1}")
            if fp_target is not None and not row.get("fixed"):
                row["disp"] = "FALSE_POSITIVE" if k in fp_target else ("BENIGN_TRUE_POSITIVE" if row["disp"] == "FALSE_POSITIVE" else row["disp"])
                row["note"] = str(g.choice(NOTES_BY_CAT.get(row["cat"], [""])))
            files.setdefault(mon, []).append([aid, z(t), f"SE3-{row['fam']}-{row['rule']}", row["name"], row["cat"], row["prio"], row.get("src_host", ""),
                                              row.get("src_ip", ""), row.get("dst_host", ""), row.get("dst_ip", ""), row.get("dst_port", ""), row.get("user", ""),
                                              row.get("detail", ""), row["disp"], z(row["closed"]) if row.get("closed") else "", row.get("closed_by", ""), row.get("note", "")])
        fp = sum(1 for _, r in rows if r["disp"] == "FALSE_POSITIVE")
        daily.append([dt.datetime.fromtimestamp(t0, UTC).strftime("%Y-%m-%d"), len(rows), fp, f"{100 * fp / max(1, len(rows)):.1f}",
                      sum(1 for _, r in rows if r["disp"] == "OPEN" and r["fam"] == "ML")])
    total = 0
    for mon, rows in sorted(files.items()):
        total += write_csv(f"{NET}/siem/siem_alerts_{mon}.csv", SIEM_COLS, rows)
    write_csv(f"{NET}/siem/daily_summary.csv", ["date_utc", "alerts", "closed_false_positive", "false_positive_rate_pct", "open_ml_anomaly_alerts"], daily)
    rules = [
        [z(RULE_CREATED), "CREATE", "MAINT-EXCEPT-0892", "exception", "auto-acknowledge SE3-OT-1104 when source is GW-SYS-JMP-01", "svc_fieldops_ext", ""],
        [z(ts("2027-08-24T15:02Z")), "CREATE", "MAINT-EXCEPT-0893", "exception", "auto-acknowledge SE3-OT-6010 during approved windows", "aclark", "CHG-27-0812"],
        [z(ts("2027-08-31T14:22Z")), "UPDATE", "WL-NET-0117", "whitelist", "104.21.88.0/24 added to vendor CDN range", SOC["SOC-AN-02"], ""],
        [z(STORM_MODE_ON), "ACTIVATE", "SE3-BULK-STORM-01", "bulk dismissal", "storm mode: dismiss LOW and MEDIUM alerts from 44 device-availability and OT maintenance rule families", SOC["SOC-AN-01"], "EOC-ACT-27-09"],
        [z(STORM_MODE_OFF), "DEACTIVATE", "SE3-BULK-STORM-01", "bulk dismissal", "storm mode ended", SOC["SOC-AN-01"], "EOC-ACT-27-09"],
        [z(RULE_REMOVED), "DELETE", "MAINT-EXCEPT-0892", "exception", "removed (AUDIT-EXC-2027-10)", "falrasheedobinna", "SI-2027-CC-001"],
        [z(ts("2027-10-19T00:30Z")), "REPORT", "AUDIT-EXC-2027-10", "audit", "exception rule audit complete: 41 rules reviewed, 1 removed", "bflores", "SI-2027-CC-001"],
    ]
    write_csv(f"{NET}/siem/rule_changes.csv", ["time_utc", "action", "rule_id", "rule_type", "description", "changed_by", "change_ticket"], rules)
    print(f"siem_alerts: {total:,} alerts in {len(files)} files")


def day_utc(t):
    return int((t - D0_EPOCH) // DAY)


def siem_background(t, rule, g, d):
    rid, fam, name, cat, prio, _, _ = rule
    h = CORP[g.integers(len(CORP))] if cat in ("authentication", "endpoint", "policy", "mail", "network") else SERVERS[g.integers(len(SERVERS))]
    row = {"fam": fam, "rule": rid, "name": name, "cat": cat, "prio": prio, "src_host": h["hostname"], "src_ip": h["ip"]}
    u = USERS[g.integers(len(USERS))]
    if cat in ("authentication", "policy", "mail"):
        row["user"] = u["username"]
    if name == "FLAGGED_IP_OUTBOUND":
        row.update(dst_ip=f"{g.integers(13, 220)}.{g.integers(1, 250)}.{g.integers(1, 250)}.{g.integers(2, 250)}", dst_port=443, detail=f"bytes_out={int(g.integers(200, 90000))}")
    elif name == "HISTORIAN_BULK_QUERY":
        e = ENGINEERS[g.integers(len(ENGINEERS))]
        row.update(src_host=e["normal_hosts"][-1], src_ip=IP.get(e["normal_hosts"][-1], ""), dst_host=HIST1, dst_ip=IP[HIST1], user=e["ot_account"],
                   detail=f"session_duration={int(g.integers(200, 2400))}s tags_queried={int(g.integers(120, 520))}")
    elif name == "OT_FILE_WRITE":
        e = ENGINEERS[g.integers(len(ENGINEERS))]
        row.update(src_host=e["normal_hosts"][-1], src_ip=IP.get(e["normal_hosts"][-1], ""), dst_host="GW-SRV-OT-01", dst_ip=IP["GW-SRV-OT-01"], user=e["ot_account"],
                   detail="action=FILE_WRITE path=\\\\gw-srv-ot-01\\projects\\" + f"wo{int(g.integers(4100, 5200))}\\notes.docx")
    elif name == "ALARM_SUPPRESSION_CHANGE":
        row.update(src_host="GW-WS-OPS-01", src_ip=IP.get("GW-WS-OPS-01", ""), dst_host=SCADA1, dst_ip=IP[SCADA1], detail=f"suppressed_alarm_count={int(g.integers(11, 16))} threshold=30")
    elif name in ("DEVICE_COMM_LOSS", "UPS_ON_BATTERY", "LINK_DOWN", "AGENT_OFFLINE", "LOG_SOURCE_SILENT"):
        row["detail"] = f"duration={int(g.integers(30, 5400))}s"
    elif name == "FAILED_LOGON_BURST":
        row["detail"] = f"failures={int(g.integers(5, 14))} window=300s"
    if not boundary_open(t) and JMP in (row.get("src_host"), row.get("dst_host")):   # gateway is powered off
        row.update(src_host="GW-WS-ENG-01", src_ip=IP["GW-WS-ENG-01"])
        if row.get("dst_host") == JMP:
            row.update(dst_host=HIST1, dst_ip=IP[HIST1])
    storm_mode = STORM_MODE_ON <= t < STORM_MODE_OFF and prio in ("LOW", "MEDIUM", "INFO")
    if storm_mode and cat in ("ot", "network", "endpoint", "system"):
        row.update(disp="STORM_BULK_DISMISSED", closed=t + int(g.integers(20, 400)), closed_by=SOC["SOC-AN-01"], note="SE3-BULK-STORM-01")
    elif prio == "INFO" or name == "MAINT_WINDOW_ACTIVITY":
        row.update(disp="AUTO_ACK", closed=t, closed_by="system", note="")
    else:
        r = g.random()
        disp = "FALSE_POSITIVE" if r < 0.14 else ("BENIGN_TRUE_POSITIVE" if r < 0.93 else ("AUTHORIZED_MAINTENANCE" if r < 0.985 else "ESCALATED"))
        an = list(SOC.values())[g.integers(3)]
        row.update(disp=disp, closed=t + int(g.integers(600, 9 * 3600) * (3 if -1 <= d <= 5 else 1)), closed_by=an,
                   note="Ticket opened" if disp == "ESCALATED" else str(g.choice(NOTES_BY_CAT.get(cat, [""]))))
    return row


def siem_specials():
    """Alerts canon names, as the SIEM recorded them."""
    out = []

    def add(t, fam, rule, name, cat, prio, disp, **kw):
        row = {"fam": fam, "rule": rule, "name": name, "cat": cat, "prio": prio, "disp": disp, "fixed": True}
        row.update(kw)
        out.append((int(t), row))

    g = rng("siem_alerts", "beacon")
    # outbound connection alerts for the same destination, every time the rule matched before the range was whitelisted,
    # then daily digest hits from the whitelist-audit rule until the last connection
    add(BEACON_FIRST, "NET", "9941", "FLAGGED_IP_OUTBOUND", "network", "LOW", "FALSE_POSITIVE", src_host=WS04, src_ip=IP[WS04], dst_ip=BEACON_IP, dst_port=443,
        detail="bytes_out=318", closed=ts("2027-08-31T14:22Z"), closed_by=SOC["SOC-AN-02"], note="Cloud CDN, whitelisted vendor range")
    t = BEACON_FIRST
    for bt in beacon_times():
        if bt == ts("2027-09-15T01:17Z") + 21 or (bt - t >= 20 * 3600 and bt > BEACON_FIRST and abs(bt - (ts("2027-09-15T01:17Z") + 21)) > 20 * 3600 and bt != BEACON_LAST):
            t = bt
            storm = STORM_MODE_ON <= bt < STORM_MODE_OFF
            add(bt, "NET", "9941", "FLAGGED_IP_OUTBOUND", "network", "LOW", "STORM_BULK_DISMISSED" if storm else "AUTO_ACK", src_host=WS04, src_ip=IP[WS04], dst_ip=BEACON_IP,
                dst_port=443, detail=f"bytes_out={int(g.integers(300, 340))} whitelist=WL-NET-0117", closed=bt + (int(g.integers(60, 300)) if storm else 0),
                closed_by=SOC["SOC-AN-01"] if storm else "system", note="SE3-BULK-STORM-01" if storm else "WL-NET-0117")
    add(BEACON_LAST, "NET", "9941", "FLAGGED_IP_OUTBOUND", "network", "LOW", "AUTO_ACK", src_host=WS04, src_ip=IP[WS04], dst_ip=BEACON_IP, dst_port=443,
        detail="bytes_out=318 whitelist=WL-NET-0117", closed=BEACON_LAST, closed_by="system", note="WL-NET-0117")
    # historian bulk-query alerts for the out-of-hours sessions
    for s in SESSIONS:
        storm = STORM_MODE_ON <= s["start"] < STORM_MODE_OFF
        last = s["n"] == 14
        if last:
            add(s["start"], "ML", "0044", "SESSION_BEHAVIOUR_ANOMALY", "ot", "ANOMALY_HIGH", "ESCALATED", src_host=JMP, src_ip=IP[JMP], dst_host=HIST1, dst_ip=IP[HIST1],
                user="GW-SYS-JMP-01\\svc_fieldops_ext", detail=f"session_id={s['hist_id']} src_asn=AS-209144 tags_queried=1241 tag_groups=relay_config(all 5 substations) anomaly_score=3.84",
                closed=ts("2027-10-02T15:10Z"), closed_by="falrasheedobinna", note="SI-2027-CC-001 opened")
        add(s["start"] + 2, "OT", "1104", "HISTORIAN_BULK_QUERY", "ot", "LOW", "STORM_BULK_DISMISSED" if storm else "AUTO_ACK", src_host=JMP, src_ip=IP[JMP], dst_host=HIST1, dst_ip=IP[HIST1],
            user="GW-SYS-JMP-01\\svc_fieldops_ext", detail=f"session_duration={min(s['dur'], 1500)}s tags_queried={s['tags']}",
            closed=s["start"] + (140 if storm else 2), closed_by=SOC["SOC-AN-01"] if storm else "system", note="SE3-BULK-STORM-01" if storm else "exception rule MAINT-EXCEPT-0892")
    # file write on the relay configuration share
    add(M.T["cfg_sub2"] - 3, "OT", "2201", "OT_FILE_WRITE", "ot", "MEDIUM", "AUTHORIZED_MAINTENANCE", src_host=JMP, src_ip=IP[JMP], dst_host="GW-SRV-OT-01", dst_ip=IP["GW-SRV-OT-01"],
        user="GW-ENG-VELA", detail="action=FILE_WRITE path=\\\\gw-srv-ot-01\\relayconfigs\\sub02\\rtu_config_draft.xml", closed=ts("2027-09-11T22:58Z"), closed_by=SOC["SOC-AN-01"],
        note="Storm prep relay adjustment per ops supervisor note")
    # alarm-suppression list changes
    prev = 12
    for i, (t, n) in enumerate(M.SUPPRESSION_STEPS):
        storm = STORM_MODE_ON <= t < STORM_MODE_OFF
        last = i == len(M.SUPPRESSION_STEPS) - 1
        if last:
            continue
        add(t + 4, "OT", "3301", "ALARM_SUPPRESSION_CHANGE", "ot", "MEDIUM" if n < 30 else "HIGH", "STORM_BULK_DISMISSED" if storm else "BENIGN_TRUE_POSITIVE",
            src_host=JMP, src_ip=IP[JMP], dst_host=SCADA1, dst_ip=IP[SCADA1], user="GW-ENG-VELA", detail=f"suppressed_alarm_count={n} threshold=30 added={n - prev}",
            closed=t + (300 if storm else 5400), closed_by=SOC["SOC-AN-01"] if storm else SOC["SOC-AN-03"],
            note="SE3-BULK-STORM-01" if storm else ("Storm preparation" if t < LANDFALL else "Restoration work, nuisance alarms"))
        prev = n
    add(ts("2027-09-15T09:44Z") + 16, "OT", "3301", "ALARM_SUPPRESSION_CHANGE", "ot", "HIGH", "STORM_BULK_DISMISSED", src_host=SCADA1, src_ip=IP[SCADA1], dst_host=SCADA1, dst_ip=IP[SCADA1],
        detail="suppressed_alarm_count=38 threshold=30 periodic re-evaluation", closed=ts("2027-09-15T09:49Z"), closed_by=SOC["SOC-AN-01"], note="SE3-BULK-STORM-01")
    add(ts("2027-09-23T04:00Z") + 11, "OT", "3301", "ALARM_SUPPRESSION_CHANGE", "ot", "HIGH", "OPEN", src_host=JMP, src_ip=IP[JMP], dst_host=SCADA1, dst_ip=IP[SCADA1],
        detail="suppressed_alarm_count=94 threshold=30 change_count_since_2027-09-09=7", alert_id="SE3-OT-3301-20270923T0400Z")
    return out


def beacon_times():
    """Times of the periodic outbound connection from the one workstation (about every 5-7 hours
    while it is powered), first and last fixed by canon."""
    g = rng("itsec", "beacon_times")
    out, t = [BEACON_FIRST], BEACON_FIRST
    while True:
        t += int(g.integers(5 * 3600, 7 * 3600))
        if t >= BEACON_LAST - 3 * 3600:
            break
        if M.T["sub1_trip"] < t < M.T["sub1_trip"] + 12 * 3600:   # building on generator, workstation off
            continue
        out.append(t)
    out += [ts("2027-09-15T01:17Z") + 21, BEACON_LAST]
    return sorted(out)


# ======================================================================================
# Zeek
# ======================================================================================
CONN_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "service", "duration", "orig_bytes", "resp_bytes", "conn_state",
          "local_orig", "local_resp", "missed_bytes", "history", "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes"]
CONN_TY = ["time", "string", "addr", "port", "addr", "port", "enum", "string", "interval", "count", "count", "string", "bool", "bool", "count", "string", "count", "count", "count", "count"]
DNS_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "trans_id", "query", "qclass_name", "qtype_name", "rcode_name", "AA", "RD", "RA", "answers", "TTLs"]
DNS_TY = ["time", "string", "addr", "port", "addr", "port", "enum", "count", "string", "string", "string", "string", "bool", "bool", "bool", "vector[string]", "vector[interval]"]
SSL_F = ["ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "version", "cipher", "server_name", "resumed", "established"]
SSL_TY = ["time", "string", "addr", "port", "addr", "port", "string", "string", "string", "bool", "bool"]
NOT_F = ["ts", "uid", "id.orig_h", "id.resp_h", "id.resp_p", "note", "msg", "src", "dst", "p", "actions"]
NOT_TY = ["time", "string", "addr", "addr", "port", "enum", "string", "addr", "addr", "port", "set[enum]"]
_SITE_WORDS = ["coastalbendweather.net", "txroadwatch.org", "officesuite-mail.com", "officesuite-cdn.net", "osupdates-delivery.com", "geomaps-tiles.net",
               "ledgerfinance-cloud.com", "gridnotices-tx.org", "meetroom-video.com", "bayside-ledger.example", "harborline6.example", "vantage-security.com",
               "meridiancontrols.com", "ntp-pool-public.org", "fontcdn-static.net", "hrcloud-payroll.com", "partsdepot-supply.com", "utilitybilling-pay.com",
               "nueces-county-tx.org", "cctexas-services.org", "tx-waterboard.org", "pipefittings-direct.com", "fleetfuel-cards.com", "docsign-flow.com",
               "searchindex-api.com", "adnetwork-static.net", "streamvideo-cdn.net", "socialfeed-img.com", "packagetracker-api.net", "weatherradar-tiles.com",
               "telemetry-osvendor.com", "browser-safecheck.net", "certstatus-ocsp.net", "cloudstorage-sync.com", "helpdesk-tickets.com", "training-lms.net",
               "benefits-portal.com", "scada-vendor-docs.com", "relaytech-support.net", "pumpworks-service.com", "gis-basemaps.org", "newswire-national.com",
               "airline-bookings.net", "hotel-reservations.com", "retail-orders.com", "bank-online-secure.com", "insurance-claims-portal.com", "school-district-cc.org",
               "hospital-patient-portal.org", "storm-prep-guides.org", "generator-parts.net", "truckrental-fleet.com", "cellcarrier-account.com", "cdn-jslibs.net"]
_PREFIX = [13, 23, 34, 35, 40, 52, 54, 64, 69, 96, 104, 108, 142, 151, 157, 162, 185, 199, 205, 216]
_HOME = [24, 47, 66, 67, 68, 70, 72, 73, 75, 76, 97, 98, 99, 107, 174]
SITE_IPS = {}
_g0 = rng("itsec", "sites")
for _w in _SITE_WORDS:
    for _sub in (["www", "api", "cdn", "login"] if _g0.random() < 0.5 else ["www", "static"]):
        SITE_IPS[f"{_sub}.{_w}"] = [f"{_PREFIX[int(_g0.integers(len(_PREFIX)))]}.{int(_g0.integers(1, 250))}.{int(_g0.integers(1, 250))}.{int(_g0.integers(2, 250))}"
                                    for _ in range(int(_g0.integers(1, 4)))]
SITES = sorted(SITE_IPS)
CORP = [h for h in HOSTS if h["device_type"] in ("workstation", "laptop") and h["ip"].startswith("10.14.")]
OT_CONSOLES = [h["hostname"] for h in HOSTS if h["device_type"] in ("operator workstation", "engineering workstation")]
IT_ADMIN = [h for h in CORP if "IT Infrastructure" in h.get("role", "")] or CORP[:6]
RTUS = [h["hostname"] for h in HOSTS if h["device_type"] == "rtu"]
STATES = [("SF", "ShADadFf", 0.935), ("S0", "S", 0.02), ("REJ", "Sr", 0.012), ("RSTO", "ShADaR", 0.014), ("RSTR", "ShADdr", 0.008), ("SH", "ShADF", 0.006), ("OTH", "Aa", 0.005)]


def home_ip(g):
    """A residential-looking address for staff working from home."""
    return f"{_HOME[int(g.integers(len(_HOME)))]}.{int(g.integers(1, 250))}.{int(g.integers(1, 250))}.{int(g.integers(2, 250))}"


def boundary_open(t):
    """False while the OT network is cut off from everything else (canon isolation window)."""
    return not (ISOLATE <= t < M.T["reconnect"])


def inside_host(e, t):
    """The host a person works from: their usual one, or an engineering workstation inside the control network
    while the remote-access gateway is powered off (canon isolation window)."""
    h = e["normal_hosts"][-1]
    if h == JMP and not boundary_open(t):
        return f"GW-WS-ENG-0{1 + sum(map(ord, e['username'])) % 5}"
    return h


def legit_config_changes():
    """Ordinary approved setting changes on field devices: (epoch, device, parameter, old, new, how, account, source host, ticket)."""
    g = rng("host_audit", "legit_cfg")
    out = []
    devs = ["GW-SYS-RTU-02", "GW-SYS-RTU-03", "GW-SYS-RTU-05", "GW-SYS-RTU-UTL1", "GW-SYS-RTU-WTR1", "GW-SYS-RTU-WTR2", "GW-WTP-DCS-01", "GW-SYS-RTU-01", "GW-SYS-RTU-04"]
    pars = [("feeder CT ratio check", "600:5", "600:5"), ("tank high-level alarm (ft)", "31.5", "31.0"), ("recloser shots", "3", "2"), ("chlorine residual alarm low (mg/L)", "0.5", "0.6"),
            ("clock sync source", "GPS-A", "GPS-B"), ("transformer LTC band (V)", "2.0", "1.5"), ("relay 51 time dial", "2.0", "2.5"), ("discharge pressure setpoint (psi)", "82", "85"),
            ("booster discharge setpoint (psi)", "70", "72"), ("relay 27-UV time delay (s)", "2.0", "1.5")]
    for i in range(90):
        a = local_ts(int(g.integers(-58, 118)), f"{int(g.integers(7, 19)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
        if STORM_MODE_ON - 4 * DAY < a < STORM_MODE_OFF:
            continue
        e = ENGINEERS[g.integers(len(ENGINEERS))]
        par, old, new = pars[int(g.integers(len(pars)))]
        how = str(g.choice(["remote write", "local panel", "file replaced", "remote write"]))
        via_jmp = how != "local panel" and g.random() < 0.55 and boundary_open(a)
        out.append((a, devs[int(g.integers(len(devs)))], par, old, new, how, e["ot_account"],
                    "local panel" if how == "local panel" else (JMP if via_jmp else e["normal_hosts"][-1]), f"CHG-27-{int(g.integers(800, 1990)):04d}" if g.random() < 0.85 else ""))
    return sorted(out)


def zeek_write(day_dir, name, fields, types, rows, open_t):
    p = out_path(f"{NET}/zeek/{day_dir}/{name}.log")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#separator \\x09\n#set_separator\t,\n#empty_field\t(empty)\n#unset_field\t-\n")
        fh.write(f"#path\t{name}\n#open\t{dt.datetime.fromtimestamp(open_t, UTC):%Y-%m-%d-%H-%M-%S}\n")
        fh.write("#fields\t" + "\t".join(fields) + "\n#types\t" + "\t".join(types) + "\n")
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")
        fh.write(f"#close\t{dt.datetime.fromtimestamp(open_t + DAY, UTC):%Y-%m-%d-%H-%M-%S}\n")
    return len(rows)


def uid(*k):
    return "C" + hsh(*k, n=17)


def conn(t, o, op, r, rp, proto, svc, dur, ob, rb, state="SF", hist="ShADadFf"):
    if state in ("S0", "REJ"):
        dur, rb = 0.0, 0
        ob = 0 if state == "S0" else ob
    lo = "T" if o.startswith(("10.", "172.20.")) else "F"
    lr = "T" if r.startswith(("10.", "172.20.")) else "F"
    opk, rpk = max(3, int(ob / 900) + 4), max(3, int(rb / 1200) + 4)
    return [f"{t:.6f}", uid(t, o, op, r, rp), o, op, r, rp, proto, svc, f"{dur:.6f}", int(ob), int(rb), state, lo, lr, 0, hist, opk, int(ob + opk * 40), rpk, int(rb + rpk * 40)]


def zeek_special():
    """Flows the sensor must contain in full: (epoch, kind, row)."""
    g = rng("zeek", "special")
    out = []
    dc = IP["GW-SRV-DC-01"]
    for i, bt in enumerate(beacon_times()):
        op = 49152 + int(g.integers(0, 16000))
        t = bt + g.random()
        first = i == 0
        c = conn(t, IP[WS04], op, BEACON_IP, 443, "tcp", "ssl", 4.2 if first else float(g.uniform(3.6, 4.9)), 318 if first else int(g.integers(300, 340)),
                 212 if first else int(g.integers(190, 240)))
        out.append((t, "conn", c))
        out.append((t + 0.08, "ssl", [f"{t + 0.08:.6f}", c[1], IP[WS04], op, BEACON_IP, 443, "TLSv13", "TLS_AES_256_GCM_SHA384", BEACON_SNI, "F", "T"]))
        if first or g.random() < 0.3:
            out.append((t - 0.4, "dns", dns_row(t - 0.4, IP[WS04], dc, BEACON_SNI, BEACON_IP, g)))
    out.append((DNS_Q_T, "dns", dns_row(DNS_Q_T, IP[WS04], dc, "update-cdn.meridiancontrols.net", "104.21.88.43", g)))
    out.append((DNS_Q_T + 1.2, "conn", conn(DNS_Q_T + 1.2, IP[WS04], 50211, "104.21.88.43", 443, "tcp", "ssl", 61.4, 20114, 1884012)))
    out.append((DNS_Q_T + 1.3, "ssl", [f"{DNS_Q_T + 1.3:.6f}", uid(DNS_Q_T + 1.2, IP[WS04], 50211, "104.21.88.43", 443), IP[WS04], 50211, "104.21.88.43", 443, "TLSv13",
                                     "TLS_AES_256_GCM_SHA384", "update-cdn.meridiancontrols.net", "F", "T"]))
    # large internal transfer from the DMZ historian replica to the one workstation
    t = ts("2027-09-08T23:58Z") + 14
    out.append((t, "conn", conn(t, IP[WS04], 51877, IP[HISTDMZ], 445, "tcp", "smb", 2710.5, 4.1e6, 1.9e9)))
    # the fourteen out-of-hours sessions through the remote-access gateway and what they touched
    for s in SESSIONS:
        a = s["start"] - 18
        out.append((a, "conn", conn(a, s["ip"], 40000 + s["n"] * 311, IP[JMP], 443, "tcp", "ssl", s["dur"] + 24, 1.4e6 + s["dur"] * 900, s["bytes_out"])))
        out.append((a + 0.1, "ssl", [f"{a + 0.1:.6f}", uid(a, s["ip"], 40000 + s["n"] * 311, IP[JMP], 443), s["ip"], 40000 + s["n"] * 311, IP[JMP], 443, "TLSv12",
                                     "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "remote.cbpwa.example", "F", "T"]))
        out.append((s["start"] + 3, "conn", conn(s["start"] + 3, IP[JMP], 52000 + s["n"], IP[HIST1], 5450, "tcp", "-", min(s["dur"], 1500), 9000 + s["tags"] * 40, s["tags"] * 5200)))
    def touch(t, dst, port, svc, ob=2400, rb=1800, dur=2.2):
        out.append((t, "conn", conn(t, IP[JMP], 53000 + int(t) % 9000, IP[dst], port, "tcp", svc, dur, ob, rb)))
    touch(M.T["uv_thr_sub1"] - 6, "GW-SYS-RTU-01", 20000, "dnp3")
    touch(M.T["supp_list_d3"] - 5, SCADA1, 3389, "rdp", 18000, 240000, 41.0)
    touch(M.T["cfg_sub2"] - 4, "GW-SRV-OT-01", 445, "smb", 61000, 3100, 3.1)
    touch(M.T["cfg_rtu4"] - 4, "GW-SYS-RTU-04", 20000, "dnp3")
    touch(M.T["cfg_sub2"] + 36, "GW-SYS-RTU-02", 20000, "dnp3")
    for k in ("sub2_cmd", "sub3_cmd"):
        touch(M.T[k] - 95, OPS02, 3389, "rdp", 240000, 3.6e6, 190.0)
        t2 = M.T[k] - 2
        out.append((t2, "conn", conn(t2, IP[OPS02], 49800, IP[SCADA1], 4000, "tcp", "-", 1.1, 880, 640)))
    touch(M.T["p3_sp"] - 5, "GW-SYS-RTU-UTL1", 502, "modbus")
    touch(M.T["bstr_sp"] - 5, "GW-SYS-RTU-WTR3", 502, "modbus")
    return out


def dns_row(t, o, r, q, ans, g):
    """One dns.log row. Its uid is the uid of the UDP/53 connection that carried it (see dns_conn)."""
    op = 49152 + int(g.integers(0, 16000))
    return [f"{t:.6f}", uid(t, o, op, r, 53), o, op, r, 53, "udp", int(g.integers(1, 65000)), q, "C_INTERNET", "A", "NOERROR", "F", "T", "T", ans, f"{int(g.integers(60, 3600))}.000000"]


def dns_conn(d):
    """The conn.log row for a dns.log row (same uid, same endpoints)."""
    t = float(d[0])
    c = conn(t, d[2], d[3], d[4], 53, "udp", "dns", 0.004, 44, 92, "SF", "Dd")
    c[1] = d[1]
    return c


def pick_state(g):
    r, acc = g.random(), 0.0
    for st, hist, p in STATES:
        acc += p
        if r < acc:
            return st, hist
    return "SF", "ShADadFf"


def gen_zeek():
    import glob as _glob
    import shutil
    old = [os.path.relpath(p, ROOT) for p in _glob.glob(os.path.join(ROOT, NET, "20*")) + _glob.glob(os.path.join(ROOT, NET, "_consolidated"))]
    for rel in old:                                   # retire once: never overwrite an archived copy
        dst = os.path.join(ROOT, "_versions", "streams_pre_regen_20261109", rel)
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(os.path.join(ROOT, rel), dst)
        else:
            shutil.rmtree(os.path.join(ROOT, rel), ignore_errors=True)
    special = {}
    for t, kind, row in zeek_special():
        special.setdefault(day_utc(t), {}).setdefault(kind, []).append((t, row))
    gs = rng("zeek", "gateway_sessions")
    for r in ordinary_gateway_sessions(rng("host_audit"))[0]:
        login = int(dt.datetime.strptime(r[6], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp())
        a_t = login - 2 + float(gs.random())
        op = 40000 + int(gs.integers(0, 20000))
        c = conn(a_t, r[3], op, IP[JMP], 443, "tcp", "ssl", r[8] + 2 + float(gs.random()), r[10], r[9])
        day = special.setdefault(day_utc(a_t), {})
        day.setdefault("conn", []).append((a_t, c))
        day.setdefault("ssl", []).append((a_t + 0.1, [f"{a_t + 0.1:.6f}", c[1], r[3], op, IP[JMP], 443, "TLSv12", "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384", "remote.cbpwa.example", "F", "T"]))
        for k, tgt in enumerate(r[12].split(";")):
            if tgt not in IP:
                continue
            t2 = login + 7 + k * int(gs.integers(20, 240)) + float(gs.random())
            left = max(20.0, r[8] - (t2 - login) - 5)
            if "RTU" in tgt:
                water = "UTL" in tgt or "WTR" in tgt or "WTP" in tgt
                port, svc, dur2, ob, rb = (502 if water else 20000), ("modbus" if water else "dnp3"), float(gs.uniform(1.5, 40)), int(gs.gamma(2, 1500)) + 400, int(gs.gamma(2, 1800)) + 300
            elif tgt == HIST1:
                port, svc, dur2, ob, rb = 5450, "-", min(left, float(gs.gamma(2, 400)) + 20), int(gs.gamma(2, 2e4)) + 2000, int(gs.gamma(2, 6e5)) + 9000
            elif tgt == "GW-SRV-OT-01":
                port, svc, dur2, ob, rb = 445, "smb", min(left, float(gs.gamma(2, 20)) + 2), int(gs.gamma(2, 4e4)) + 900, int(gs.gamma(2, 3e5)) + 1200
            else:
                port, svc, dur2, ob, rb = 3389, "rdp", min(left, float(gs.gamma(2, 600)) + 30), int(gs.gamma(2, 9e4)) + 6000, int(gs.gamma(2, 2e6)) + 40000
            day.setdefault("conn", []).append((t2, conn(t2, IP[JMP], 52000 + int(gs.integers(0, 9000)), IP[tgt], port, "tcp", svc, dur2, ob, rb)))
    dc = [IP["GW-SRV-DC-01"], IP["GW-SRV-DC-02"]]
    wsip = [h["ip"] for h in CORP]
    srv = [h["ip"] for h in SERVERS if h["ip"].startswith("10.14.")]
    admin = [h["ip"] for h in IT_ADMIN]
    counts = {"conn": 0, "dns": 0, "ssl": 0, "notice": 0}
    legit_cfg = {}
    for c in legit_config_changes():
        if c[7] == JMP and c[1] in IP:
            legit_cfg.setdefault(day_utc(c[0]), []).append(c)
    DIR = [(88, "krb"), (389, "ldap"), (445, "smb"), (135, "dce_rpc")]
    APP = [(443, "ssl"), (1433, "-"), (8443, "ssl"), (445, "smb")]
    for d in range(day_utc(SPAN_START), day_utc(SPAN_END - 1) + 1):
        g = rng("zeek", d)
        t0 = D0_EPOCH + d * DAY
        wf = np.array([work_factor(t0 + h * 3600 + 1800) for h in range(24)])
        n = int(1500 * (0.25 + wf.mean() * 2.2))
        hsel = g.choice(24, n, p=(wf + 0.05) / (wf + 0.05).sum())
        times = np.sort(t0 + hsel * 3600 + g.random(n) * 3600)
        rows = {k: [x for x in special.get(d, {}).get(k, [])] for k in counts}
        for _, drow in list(rows["dns"]):                # every DNS answer rides on a UDP/53 connection with the same uid
            rows["conn"].append((float(drow[0]), dns_conn(drow)))
        kinds = g.choice(8, n, p=[0.3, 0.14, 0.2, 0.08, 0.08, 0.08, 0.07, 0.05])
        for t, k in zip(times, kinds):
            o = wsip[g.integers(len(wsip))]
            op = 49152 + int(g.integers(0, 16000))
            st, hist = pick_state(g)
            if k == 0:                                    # web
                site = SITES[g.integers(len(SITES))]
                dst = SITE_IPS[site][int(g.integers(len(SITE_IPS[site])))]
                c = conn(t, o, op, dst, 443, "tcp", "ssl", float(g.gamma(2, 9)), int(g.gamma(2, 2200)), int(g.gamma(2, 60000)), st, hist)
                rows["conn"].append((t, c))
                if st == "SF" and g.random() < 0.6:
                    rows["ssl"].append((t, [f"{t + 0.05:.6f}", c[1], o, op, dst, 443, "TLSv13" if g.random() < 0.8 else "TLSv12", "TLS_AES_128_GCM_SHA256", site, "T" if g.random() < 0.2 else "F", "T"]))
                if g.random() < 0.5:
                    dr = dns_row(t - 0.2, o, dc[g.integers(2)], site, dst, g)
                    rows["dns"].append((t - 0.2, dr)); rows["conn"].append((t - 0.2, dns_conn(dr)))
            elif k == 1:                                  # directory / file services
                port, svc = DIR[int(g.integers(len(DIR)))]
                rows["conn"].append((t, conn(t, o, op, dc[g.integers(2)], port, "tcp", svc, float(g.gamma(2, 1.2)), int(g.gamma(2, 1400)), int(g.gamma(2, 2600)), st, hist)))
            elif k == 2:                                  # dns
                site = SITES[g.integers(len(SITES))]
                dr = dns_row(t, o, dc[g.integers(2)], site, SITE_IPS[site][0], g)
                rows["dns"].append((t, dr)); rows["conn"].append((t, dns_conn(dr)))
            elif k == 3:                                  # mail
                rows["conn"].append((t, conn(t, o, op, IP["GW-SRV-MAIL-01"], 443, "tcp", "ssl", float(g.gamma(2, 20)), int(g.gamma(2, 9000)), int(g.gamma(2, 40000)), st, hist)))
            elif k == 4:                                  # internal application servers
                port, svc = APP[int(g.integers(len(APP)))]
                rows["conn"].append((t, conn(t, o, op, srv[g.integers(len(srv))], port, "tcp", svc, float(g.gamma(2, 14)), int(g.gamma(2, 5000)), int(g.gamma(2, 30000)), st, hist)))
            elif k == 5:                                  # staff VPN from home
                rows["conn"].append((t, conn(t, home_ip(g), op, IP["GW-VPN-EMP-01"], 443, "tcp", "ssl", float(g.gamma(2, 1800)), int(g.gamma(2, 4e5)), int(g.gamma(2, 2e6)))))
            elif k == 6:                                  # historian replica across the IT/OT boundary
                if boundary_open(t):
                    rows["conn"].append((t, conn(t, IP[HIST1], op, IP[HISTDMZ], 5450, "tcp", "-", float(g.gamma(2, 30)), int(g.gamma(2, 2e5)), int(g.gamma(2, 4000)))))
            else:                                         # (kept for its random draws only: gateway flows are written from the session log, see ordinary_gateway_sessions)
                e = ENGINEERS[g.integers(len(ENGINEERS))]
                office = g.random() < 0.7
                src = IP.get(e["normal_hosts"][0], o) if office else home_ip(g)
                if boundary_open(t):
                    _unused = ((t, conn(t, src, op, IP[JMP], 443, "tcp", "ssl", float(g.gamma(2, 900)), int(g.gamma(2, 2e5)), int(g.gamma(2, 1.5e6)))))
                    tgt = str(g.choice(OT_CONSOLES + [HIST1, "GW-SRV-OT-01", SCADA1]))
                    if tgt in OT_CONSOLES or tgt == SCADA1:
                        _unused = ((t + 9, conn(t + 9, IP[JMP], 52000 + int(g.integers(0, 9000)), IP[tgt], 3389, "tcp", "rdp", float(g.gamma(2, 600)), int(g.gamma(2, 9e4)), int(g.gamma(2, 2e6)))))
                    elif tgt == HIST1:
                        _unused = ((t + 9, conn(t + 9, IP[JMP], 52000 + int(g.integers(0, 9000)), IP[tgt], 5450, "tcp", "-", float(g.gamma(2, 400)), int(g.gamma(2, 2e4)), int(g.gamma(2, 6e5)))))
                    else:
                        _unused = ((t + 9, conn(t + 9, IP[JMP], 52000 + int(g.integers(0, 9000)), IP[tgt], 445, "tcp", "smb", float(g.gamma(2, 20)), int(g.gamma(2, 4e4)), int(g.gamma(2, 3e5)))))
        # IT administrators managing servers by remote desktop
        for _ in range(int(g.poisson(9 * (0.3 + wf.mean())))):
            t = t0 + int(g.integers(6, 22)) * 3600 + g.random() * 3600
            rows["conn"].append((t, conn(t, admin[g.integers(len(admin))], 49152 + int(g.integers(0, 16000)), srv[g.integers(len(srv))], 3389, "tcp", "rdp", float(g.gamma(2, 500)), int(g.gamma(2, 8e4)), int(g.gamma(2, 1.5e6)))))
        # operator consoles talking to the SCADA servers (sampled) and the front-end processors polling field devices (sampled)
        for _ in range(int(g.poisson(26))):
            t = t0 + g.random() * DAY
            ws = OT_CONSOLES[int(g.integers(len(OT_CONSOLES)))]
            rows["conn"].append((t, conn(t, IP[ws], 49152 + int(g.integers(0, 16000)), IP[str(g.choice([SCADA1, "GW-SYS-SCADA-02"]))], 4000, "tcp", "-", float(g.gamma(2, 2.0)), int(g.gamma(2, 700)), int(g.gamma(2, 900)))))
        for _ in range(int(g.poisson(30))):
            t = t0 + g.random() * DAY
            rtu = RTUS[int(g.integers(len(RTUS)))]
            water = "UTL" in rtu or "WTR" in rtu or "WTP" in rtu
            rows["conn"].append((t, conn(t, IP[str(g.choice(["GW-SRV-FEP-01", "GW-SRV-FEP-02"]))], 49152 + int(g.integers(0, 16000)), IP[rtu], 502 if water else 20000, "tcp",
                                         "modbus" if water else "dnp3", float(g.gamma(2, 1.5)), int(g.gamma(2, 600)), int(g.gamma(2, 2400)))))
        # approved remote setting changes made through the gateway (they are in the configuration-change log with their tickets)
        for c in legit_cfg.get(d, []):
            water = "UTL" in c[1] or "WTR" in c[1] or "WTP" in c[1]
            rows["conn"].append((c[0] - 5, conn(c[0] - 5, IP[JMP], 53000 + int(c[0]) % 9000, IP[c[1]], 502 if water else 20000, "tcp", "modbus" if water else "dnp3", 2.0 + (c[0] % 7) / 10, 2100 + c[0] % 600, 1500 + c[0] % 700)))
        # nightly backups and the weekly internal vulnerability scan
        for i in range(6):
            t = t0 + 3 * 3600 + i * 1200 + g.random() * 300
            s_ip = srv[(d + i) % len(srv)]
            rows["conn"].append((t, conn(t, s_ip, 51000 + i, IP["GW-SRV-BKP-01"], 10000, "tcp", "-", float(g.uniform(400, 2600)), int(g.gamma(3, 6e8)), int(g.gamma(2, 3e5)))))
        if (d % 7) == 2:
            t = t0 + 6 * 3600 + 900
            rows["notice"].append((t, [f"{t:.6f}", "-", IP.get("GW-SRV-VULN-01", srv[0]), "-", "-", "Scan::Port_Scan", "internal scanner swept 10.14.20.0/24 (scheduled)", IP.get("GW-SRV-VULN-01", srv[0]), "-", "-", "Notice::ACTION_LOG"]))
        for _ in range(int(g.poisson(3))):
            t = t0 + g.random() * DAY
            site = SITES[g.integers(len(SITES))]
            rows["notice"].append((t, [f"{t:.6f}", "-", wsip[g.integers(len(wsip))], SITE_IPS[site][0], 443,
                                       str(g.choice(["SSL::Invalid_Server_Cert", "SSL::Certificate_Expires_Soon", "DNS::External_Name", "Conn::Content_Gap"])),
                                       "-", "-", "-", 443, "Notice::ACTION_LOG"]))
        dd = dt.datetime.fromtimestamp(t0, UTC).strftime("%Y-%m-%d")
        for kname, f, ty in (("conn", CONN_F, CONN_TY), ("dns", DNS_F, DNS_TY), ("ssl", SSL_F, SSL_TY), ("notice", NOT_F, NOT_TY)):
            rr = [r for _, r in sorted(rows[kname], key=lambda x: x[0])]
            counts[kname] += zeek_write(dd, kname, f, ty, rr, t0)
    print("zeek_logs:", ", ".join(f"{k} {v:,}" for k, v in counts.items()))


# ======================================================================================
# host audit logs
# ======================================================================================
def ordinary_gateway_sessions(g):
    """The ordinary sessions on the remote-access gateway (staff, on-call, vendors, the field contractor).
    gen_audit writes them to the session log; gen_zeek writes the matching network flows, so that every
    session in the log, ordinary or not, has its flow at the sensor."""
    rows = []
    sid = 20000
    for d in range(day_utc(SPAN_START), day_utc(SPAN_END - 1) + 1):
        t0 = D0_EPOCH + d * DAY
        l = local_dt(t0 + 43200)
        gate_off = ISOLATE <= t0 + 43200 < M.T["reconnect"]
        if l.weekday() < 5 and not gate_off and not (-1 <= d <= 4):
            for _ in range(int(g.poisson(5))):
                e = ENGINEERS[g.integers(len(ENGINEERS))]
                if e["username"] == "rvela" and ts("2027-09-06T22:00Z") <= t0 <= ts("2027-09-22T06:00Z"):
                    continue                               # on leave
                a = local_ts(d, f"{int(g.integers(7, 17)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
                dur = int(g.gamma(2, 1500)) + 120
                sid += 1
                office = g.random() < 0.7
                tk = g.random()
                rows.append([f"RAS-{sid}", JMP, e["ot_account"], IP.get(e["normal_hosts"][0], "10.14.30.20") if office else home_ip(g),
                             "internal" if office else f"AS-{int(g.choice([7018, 20057, 11427, 22773]))}", "US", z(a), z(a + dur), dur, int(g.gamma(2, 4e5)), int(g.gamma(2, 3e6)),
                             "token" if g.random() < 0.82 else "password only", str(g.choice([HIST1, "GW-WS-ENG-03", "GW-SRV-OT-01", "GW-SYS-SCADA-02", "GW-WTP-HMI-01", "GW-SYS-RTU-03", OPS02])),
                             f"CHG-27-{int(g.integers(700, 1900)):04d}" if tk < 0.62 else (f"WO-{int(g.integers(40000, 48000))}" if tk < 0.8 else "")])
        # on-call engineers after hours and at weekends (storm restoration, call-outs)
        if not gate_off:
            for _ in range(int(g.poisson(1.1 if not (0 <= d <= 30) else 2.4))):
                e = ENGINEERS[g.integers(len(ENGINEERS))]
                if e["username"] == "rvela" and ts("2027-09-06T22:00Z") <= t0 <= ts("2027-09-22T06:00Z"):
                    continue
                a = t0 + int(g.integers(0, DAY))
                if 7 <= local_dt(a).hour < 18 and local_dt(a).weekday() < 5:
                    continue
                dur = int(g.gamma(2, 1300)) + 180
                sid += 1
                tk = g.random()
                rows.append([f"RAS-{sid}", JMP, e["ot_account"], home_ip(g), f"AS-{int(g.choice([7018, 20057, 11427, 22773]))}",
                             "US", z(a), z(a + dur), dur, int(g.gamma(2, 5e5)), int(g.gamma(2, 3e6)), "token" if g.random() < 0.7 else "password only",
                             str(g.choice([HIST1, "GW-SYS-SCADA-02", "GW-WTP-HMI-01", OPS02, "GW-SYS-RTU-05"])), f"WO-{int(g.integers(40000, 48000))}" if tk < 0.55 else ""])
            if g.random() < 0.25:
                a = local_ts(d, f"{int(g.integers(9, 15)):02d}:{int(g.integers(0, 60)):02d}")
                dur = int(g.gamma(2, 2400)) + 300
                sid += 1
                rows.append([f"RAS-{sid}", JMP, str(g.choice(["svc_meridian_support", "svc_vantage_mgmt"])), f"192.0.2.{int(g.integers(205, 225))}", "AS-64499", "US", z(a), z(a + dur), dur,
                             int(g.gamma(2, 6e5)), int(g.gamma(2, 2e6)), "token", str(g.choice([HIST1, "GW-SYS-SCADA-02"])), f"VND-{int(g.integers(3000, 3999))}"])
    # the field-operations contractor's ordinary daytime sessions (the account is disabled on 2027-10-02)
    gc = rng("host_audit", "contractor")
    for d in range(day_utc(SPAN_START), day_utc(ts("2027-10-02T00:00Z"))):
        if local_dt(D0_EPOCH + d * DAY + 43200).weekday() < 5 and gc.random() < 0.38 and not (-2 <= d <= 6):
            a = local_ts(d, f"{int(gc.integers(8, 16)):02d}:{int(gc.integers(0, 60)):02d}") + int(gc.integers(0, 60))
            dur = int(gc.gamma(2, 1100)) + 240
            sid += 1
            rows.append([f"RAS-{sid}", JMP, "svc_fieldops_ext", f"66.193.54.{int(gc.integers(18, 30))}", "AS-11427", "US", z(a), z(a + dur), dur, int(gc.gamma(2, 3e5)), int(gc.gamma(2, 2e6)),
                         "token" if gc.random() < 0.8 else "password only", HIST1, f"WO-{int(gc.integers(40000, 48000))}" if gc.random() < 0.75 else ""])
    rows = [r for r in rows if boundary_open(ts(r[6])) and boundary_open(ts(r[7]))]
    gm = rng("host_audit", "targets")                 # ordinary sessions often touch more than one host
    pool = [HIST1, "GW-WS-ENG-03", "GW-SRV-OT-01", "GW-SYS-SCADA-02", "GW-WTP-HMI-01", "GW-SYS-RTU-03", "GW-SYS-RTU-05", OPS02, SCADA1]
    for r in rows:
        if gm.random() < 0.14:
            extra = [str(x) for x in gm.choice(pool, int(gm.integers(1, 3)), replace=False) if str(x) != r[12]]
            r[12] = ";".join(sorted(set([r[12]] + extra)))
    return rows, sid


def gen_audit():
    g = rng("host_audit")
    A = f"{NET}/audit"
    # ---- remote-access gateway sessions
    rows, sid = ordinary_gateway_sessions(g)
    ordinary = [list(r) for r in rows]
    for s in SESSIONS:
        sid += 1
        targets = [HIST1]
        for k, hname in (("uv_thr_sub1", "GW-SYS-RTU-01;" + SCADA1), ("cfg_sub2", "GW-SRV-OT-01;GW-SYS-RTU-04"), ("sub2_cmd", OPS02), ("sub3_cmd", OPS02), ("p3_sp", "GW-SYS-RTU-UTL1;GW-SYS-RTU-WTR3")):
            if s["start"] <= M.T[k] <= s["start"] + s["dur"]:
                targets.append(hname)
        rows.append([f"RAS-{sid}", JMP, "GW-ENG-VELA", s["ip"], s["asn"], s["cc"], z(s["start"] - 16), z(s["start"] + s["dur"] + 6), s["dur"] + 22, s["bytes_out"], int(1.4e6 + s["dur"] * 900 + g.integers(0, 90000)),
                     "password only", ";".join(targets), ""])
    rows.sort(key=lambda r: r[6])
    for i, r in enumerate(rows):                      # ids are issued in order of login
        r[0] = f"RAS-{20001 + i}"
    n1 = write_csv(f"{A}/remote_access_sessions.csv", ["session_id", "gateway", "account", "src_ip", "src_network", "src_country", "login_utc", "logout_utc", "duration_s", "bytes_out",
                                                       "bytes_in", "auth_method", "target_hosts", "change_ticket"], rows)
    # ---- historian access
    rows = []
    hn = 400
    for d in range(day_utc(SPAN_START), day_utc(SPAN_END - 1) + 1):
        t0 = D0_EPOCH + d * DAY
        l = local_dt(t0 + 43200)
        for _ in range(int(g.poisson(9 if l.weekday() < 5 else 3) * (0.3 if -1 <= d <= 4 else 1))):
            e = ENGINEERS[g.integers(len(ENGINEERS))] if g.random() < 0.6 else None
            a = local_ts(d, f"{int(g.integers(6, 19)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
            dur = int(g.gamma(2, 500)) + 30
            hn += 1
            bulk = g.random() < 0.07
            rows.append([a, f"HIST-{dt.datetime.fromtimestamp(a, UTC):%Y%m%d}-{hn % 100000:05d}", HIST1, e["ot_account"] if e else str(g.choice(["svc_scada_hist", "svc_hist_repl", "svc_oms"])),
                         inside_host(e, a) if e else str(g.choice([SCADA1, HISTDMZ, "GW-SRV-OMS-01"])), z(a), z(a + dur), dur, (int(g.gamma(2, 260)) + 150) if bulk else (int(g.gamma(2, 60)) + 4),
                         str(g.choice(["load_profile", "feeder_voltage", "pump_flow;pressure", "tank_level", "water_quality", "breaker_status", "transformer_temp", "relay_settings", "relay_config;breaker_status",
                                       "relay_config(SUB-03)", "breaker_status(SUB-01)", "pump_setpoints;pressure_zones", "alarm_config", "relay_settings;tap_position", "breaker_status(SUB-05)",
                                       "relay_config(SUB-01..SUB-05)", "pump_setpoints;booster_setpoints"])),
                         "bulk read" if bulk else "trend"])
        if l.weekday() < 5 and g.random() < 0.3 and D0_EPOCH + d * DAY < ts("2027-10-02T00:00Z") and not (-2 <= d <= 6):   # contractor reports
            a = local_ts(d, f"{int(g.integers(8, 16)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
            dur = int(g.gamma(2, 420)) + 60
            hn += 1
            rows.append([a, f"HIST-{dt.datetime.fromtimestamp(a, UTC):%Y%m%d}-{hn % 100000:05d}", HIST1, "GW-SYS-JMP-01\\svc_fieldops_ext", JMP, z(a), z(a + dur), dur, int(g.gamma(2, 110)) + 20,
                         str(g.choice(["feeder_voltage", "breaker_status", "relay_settings;tap_position", "pump_flow;pressure", "load_profile"])), str(g.choice(["trend", "bulk read", "trend"]))])
    groups = ["relay_settings;tap_position", "feeder_voltage;relay_settings", "relay_config;breaker_status", "relay_config(SUB-01..SUB-05)", "relay_config;protection_events",
              "pump_setpoints;pressure_zones", "relay_config;alarm_config", "breaker_status;relay_settings", "alarm_config", "breaker_status(SUB-02)", "pump_setpoints;booster_setpoints",
              "breaker_status(SUB-03)", "relay_config;pump_setpoints", "relay_config(all 5 substations)"]
    for s, grp in zip(SESSIONS, groups):
        hid = s["hist_id"] or ""
        dur = min(s["dur"], 1500) if s["n"] != 1 else 862
        rows.append([s["start"] + 3, hid, HIST1, "GW-SYS-JMP-01\\svc_fieldops_ext", JMP, z(s["start"] + 3), z(s["start"] + 3 + dur), dur, s["tags"], grp, "bulk read"])
    rows.sort(key=lambda r: r[0])
    # session numbers come from one counter shared with other historian clients, so they rise with time in uneven steps;
    # the two numbers canon states (00441 and 00917) are honoured and the rest are laid out around them
    i0 = next(i for i, r in enumerate(rows) if r[1] == "HIST-20270907-00441")
    i1 = next(i for i, r in enumerate(rows) if r[1] == "HIST-20271002-00917")
    gi = rng("host_audit", "hist_ids")
    seq = [0] * len(rows)
    seq[i0], seq[i1] = 441, 917
    before = sorted(gi.choice(np.arange(1, 441), i0, replace=False).tolist()) if i0 <= 440 else list(range(441 - i0, 441))
    for i in range(i0):
        seq[i] = before[i]
    mid = sorted(gi.choice(np.arange(442, 917), i1 - i0 - 1, replace=False).tolist())
    for k, i in enumerate(range(i0 + 1, i1)):
        seq[i] = mid[k]
    n = 917
    for i in range(i1 + 1, len(rows)):
        n += int(gi.integers(1, 4))
        seq[i] = n
    for r, q in zip(rows, seq):
        r[1] = f"HIST-{dt.datetime.fromtimestamp(r[0], UTC):%Y%m%d}-{q % 100000:05d}"
    n2 = write_csv(f"{A}/historian_access.csv", ["session_id", "server", "account", "client_host", "start_utc", "end_utc", "duration_s", "tags_queried", "tag_groups", "query_type"], [r[1:] for r in rows])
    # ---- configuration changes on field devices and SCADA
    cfg = [[z(ts("2027-08-15T15:10Z")), "GW-SYS-RTU-01", "relay 27-UV pickup (pu)", "", "0.88", "local panel", "GW-ENG-VELA", "GW-WS-ENG-03", "CHG-27-0744"]]
    for c in legit_config_changes():
        cfg.append([z(c[0])] + list(c[1:]))
    cfg += [
        [z(M.T["uv_thr_sub1"]), "GW-SYS-RTU-01", "relay 27-UV pickup (pu)", "0.88", "0.94", "remote write", "GW-ENG-VELA", JMP, ""],
        [z(M.T["cfg_sub2"] + 41), "GW-SYS-RTU-02", "relays R-02A/B/C overcurrent trip (A)", "1200", "2400", "file replaced", "GW-ENG-VELA", JMP, ""],
        [z(M.T["cfg_rtu4"]), "GW-SYS-RTU-04", "configuration file rtu04_active.cfg", "last_modified 2027-08-15T16:02:11Z", f"last_modified {z(M.T['cfg_rtu4'])}", "file replaced", "GW-ENG-VELA", JMP, ""],
        [z(M.T["p3_sp"]), "GW-SYS-RTU-UTL1", "P-3 discharge pressure setpoint (psi)", "85", "68", "remote write", "GW-ENG-VELA", JMP, ""],
        [z(M.T["bstr_sp"]), "GW-SYS-RTU-WTR3", "booster discharge setpoint (psi)", "72", "54", "remote write", "GW-ENG-VELA", JMP, ""],
        [z(M.T["p3_restore"]), "GW-SYS-RTU-UTL1", "P-3 discharge pressure setpoint (psi)", "68", "85", "local panel", ENGINEERS[0]["ot_account"], "GW-WTP-HMI-01", "SI-2027-CC-001"],
        [z(M.T["bstr_restore"]), "GW-SYS-RTU-WTR3", "booster discharge setpoint (psi)", "54", "72", "local panel", ENGINEERS[0]["ot_account"], "local panel", "SI-2027-CC-001"],
        [z(M.T["relay_reset_sub1"]), "GW-SYS-RTU-01", "relay 27-UV pickup (pu)", "0.94", "0.88", "local panel", ENGINEERS[1]["ot_account"], "local panel", "SI-2027-CC-001"],
        [z(M.T["relay_reset_sub2"]), "GW-SYS-RTU-02", "relays R-02A/B/C overcurrent trip (A)", "2400", "1200", "local panel", ENGINEERS[1]["ot_account"], "local panel", "SI-2027-CC-001"],
    ]
    cfg.sort(key=lambda r: r[0])
    n3 = write_csv(f"{A}/ot_config_changes.csv", ["time_utc", "device", "parameter", "old_value", "new_value", "change_type", "session_user", "source_host", "change_ticket"], cfg)
    # ---- SCADA command log (operator actions)
    cmd = []
    for d in range(day_utc(SPAN_START), day_utc(SPAN_END - 1) + 1):
        for _ in range(int(g.poisson(2.2))):
            a = D0_EPOCH + d * DAY + int(g.integers(0, DAY))
            op = USERS[int(g.integers(len(USERS)))]["username"]
            r = g.random()
            ws = str(g.choice(["GW-WS-OPS-01", "GW-WS-OPS-03", "GW-HMI-WALL-01", OPS02]))
            command = str(g.choice(["CAP BANK SWITCH", "TAP RAISE", "TAP LOWER", "ALARM ACK", "TAG NOTE", "SETPOINT ENTRY", "BREAKER CLOSE", "BREAKER OPEN", "RECLOSE ENABLE"]))
            device = str(g.choice(["GW-SUB01-T1", "GW-SUB03-T1", "GW-SUB05-BUS", "GW-FAC-WTR-01-BP1", "GW-SUB04-CB-14", "GW-SUB01-CB-2", "GW-SUB05-CB-19", "GW-SUB03-CB-10", "GW-SUB02-CB-6", "GW-SUB02-CB-7", "GW-SUB03-CB-12",
                                   "GW-SUB02-CB-5", "GW-SUB03-CB-9", "GW-SUB04-CB-15", "GW-SUB01-CB-3"]))
            if r < 0.8 or (r < 0.9 and not boundary_open(a)):   # operator at the console
                cmd.append([z(a), SCADA1, ws, "" if g.random() < 0.12 else op, command, device, "EXECUTED", "console", f"CON-{hsh('con', a, n=6)}", ""])
            elif r < 0.9:                                 # on-call engineer through the remote-access gateway
                e = ENGINEERS[g.integers(len(ENGINEERS))]
                cmd.append([z(a), SCADA1, ws, e["username"], command, device, "EXECUTED", "remote desktop", "", JMP])
            else:                                         # automatic schemes (reclosing, capacitor control, load transfer)
                cmd.append([z(a), SCADA1, "", "", command, device, "EXECUTED", "automation", "", ""])
    # a command given over remote desktop belongs to a session on the remote-access gateway: place each one inside an
    # ordinary session of an engineer who opened a console or server that day (the gateway log and the network sensor show it)
    acct_user = {e["ot_account"]: e["username"] for e in ENGINEERS}
    rd_hosts = (OPS02, "GW-SYS-SCADA-02", "GW-WTP-HMI-01", "GW-WS-ENG-03")
    cand = [r for r in ordinary if r[2] in acct_user and any(t in rd_hosts for t in r[12].split(";")) and r[8] > 400 + 240 * r[12].count(";")]
    gr = rng("host_audit", "rd_sessions")
    order = gr.permutation(len(cand))
    k = 0
    for r in cmd:
        if r[7] == "remote desktop":
            s_ = cand[int(order[k % len(cand)])]
            k += 1
            login = int(dt.datetime.strptime(s_[6], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp())
            lo = 90 + 240 * s_[12].count(";")
            r[0] = z(login + int(gr.integers(lo, s_[8] - 30)))
            r[2] = next(t for t in s_[12].split(";") if t in rd_hosts)
            r[3] = acct_user[s_[2]]
    gb = rng("host_audit", "rd_operator")             # the SCADA server does not always resolve the remote-desktop user
    for r in cmd:
        if r[7] == "remote desktop" and gb.random() < 0.2:
            r[3] = ""
    for k, dev in (("sub2_cmd", "GW-SUB02-CB-7"), ("sub3_cmd", "GW-SUB03-CB-12")):
        cmd.append([z(M.T[k]), SCADA1, OPS02, "", "BREAKER OPEN", dev, "EXECUTED", "remote desktop", "", JMP])
    cmd.sort(key=lambda r: r[0])
    n4 = write_csv(f"{A}/scada_command_log.csv", ["time_utc", "scada_server", "workstation", "operator", "command", "device", "result", "origin", "console_session_id", "origin_host"], cmd)
    # ---- alarm suppression list
    sup, cats = [], ["substation relay", "pump flow", "water quality sensor", "tank level", "communications"]
    base_t = ts("2027-07-02T14:00Z")
    for i in range(12):
        sup.append([z(base_t + i * 3 * DAY + int(g.integers(-9, 9)) * 3600 + int(g.integers(0, 3600))), SCADA1, "ADD", f"ALM-{2100 + i}", str(g.choice(["communications", "tank level", "nuisance door contact"])),
                    ("operator shift supervisor", "GW-ENG-VELA", "GW-ENG-BAKER")[i % 3], ("GW-WS-OPS-01", "GW-WS-ENG-03", "GW-WS-ENG-03")[i % 3], "" if i % 3 == 0 else f"CHG-27-{600 + i:04d}", i + 1])
    prev, pt = 12, 3000
    for t, n in M.SUPPRESSION_STEPS:
        for j in range(n - prev):
            pt += 1
            cat = "substation relay" if t == M.T["supp_list_d3"] else cats[(pt + j) % 3]
            dev = f"SUB-0{1 + j % 4} relay trip" if t == M.T["supp_list_d3"] else cat
            sup.append([z(t + j // 6), SCADA1 if "relay" in cat else "GW-WTP-DCS-01", "ADD", f"ALM-{pt} ({dev})", cat, "GW-ENG-VELA", JMP, "", prev + j + 1])
        prev = n
    tr = M.T["isolate"] + 1800
    for j in range(82):
        tr += int(g.integers(8, 75)) + (int(g.integers(600, 2400)) if j % 14 == 13 else 0)
        sup.append([z(tr), SCADA1, "REMOVE", f"ALM-{3001 + j}", "restored", ENGINEERS[0]["ot_account"], "GW-WS-OPS-01", "SI-2027-CC-001", 94 - j - 1])
    sup.sort(key=lambda r: r[0])
    n5 = write_csv(f"{A}/alarm_suppression_audit.csv", ["time_utc", "system", "action", "alarm_point", "category", "changed_by", "source_host", "change_ticket", "active_suppressions_after"], sup)
    # ---- file integrity on the OT file server
    fim = []
    for i in range(160):
        a = local_ts(int(g.integers(-59, 118)), f"{int(g.integers(7, 18)):02d}:{int(g.integers(0, 60)):02d}")
        e = ENGINEERS[g.integers(len(ENGINEERS))]
        path = "\\\\gw-srv-ot-01\\" + str(g.choice(["projects", "drawings", "relayconfigs\\archive", "procedures", "wtp\\reports"])) + f"\\{hsh('f', i, n=8)}." + str(g.choice(["docx", "pdf", "xml", "xlsx"]))
        summ = ""
        if path.endswith(".xml"):
            summ = str(g.choice(["comment block updated", "relay 51 time dial 2.0 -> 2.5 for relay R-05B", "CT ratio field corrected 600:5 -> 800:5 for R-03C", "revision label updated",
                                 "recloser shots 3 -> 2 for R-04A", "LTC band 2.0V -> 1.5V", "overcurrent_trip_threshold 900A -> 1000A for relay R-05A", "alarm text edited"]))
        fim.append([z(a), "GW-SRV-OT-01", path, "MODIFIED", "sha256=" + hsh("p", i), "sha256=" + hsh("n", i), e["ot_account"], JMP if (g.random() < 0.3 and boundary_open(a)) else inside_host(e, a), summ])
    fim.append([z(M.T["cfg_sub2"]), "GW-SRV-OT-01", "\\\\gw-srv-ot-01\\relayconfigs\\sub02\\rtu_config_draft.xml", "MODIFIED", "sha256=d7e1a0f3c2b18429", "sha256=a3f8c2d1e9b04517", "GW-ENG-VELA", JMP,
                "overcurrent_trip_threshold 1200A -> 2400A for relays R-02A, R-02B, R-02C"])
    fim.sort(key=lambda r: r[0])
    n6 = write_csv(f"{A}/file_integrity.csv", ["time_utc", "host", "path", "event", "previous_hash", "new_hash", "user", "source_host", "diff_summary"], fim)
    # ---- change management and audits
    chg = [[z(ts("2027-09-10T21:00Z")), "CHG-FREEZE-27-09", "Storm-preparation change freeze", "all OT configuration changes suspended until further notice", "OT Engineering manager", "ACTIVE"],
           [z(ts("2027-09-28T22:10Z")), "TXRC-2027-09-28-004", "ERCOT relay audit ticket", "possible relay config drift at Riverside Switching Station; investigating", "ERCOT compliance", "OPEN"],
           [z(ts("2027-09-28T22:25Z")), "QRY-CHG-27-311", "Change-system search", "relay threshold change, SUB-01, since commissioning date: 0 approved work orders found", "bflores", "CLOSED"],
           [z(ts("2027-09-30T18:20Z")), "QRY-CHG-27-318", "Change-system search", "configuration file change, SUB-04 RTU, 2027-09-11: 0 approved work orders found", "bflores", "CLOSED"],
           [z(ts("2027-10-02T15:10Z")), "SI-2027-CC-001", "Security incident", "opened by CISO after session-behaviour anomaly", "falrasheedobinna", "OPEN"]]
    for i in range(140):
        a = local_ts(int(g.integers(-59, 118)), f"{int(g.integers(8, 17)):02d}:{int(g.integers(0, 60)):02d}")
        chg.append([z(a), f"CHG-27-{int(g.integers(700, 1999)):04d}", "Approved change", str(g.choice(["firmware update, substation switch", "historian disk expansion", "HMI display revision", "firewall rule review",
                    "RTU battery replacement", "chlorine analyser calibration constants", "SCADA point database update"])), ENGINEERS[g.integers(len(ENGINEERS))]["username"], "CLOSED"])
    chg.sort(key=lambda r: r[0])
    n7 = write_csv(f"{A}/change_management.csv", ["time_utc", "record_id", "record_type", "summary", "owner", "status"], chg)
    aud = [[z(ts("2027-09-28T22:02Z")), "ERCOT relay settings audit", "GW-SYS-RTU-01", "Riverside Switching Station (SUB-01)", "27-UV pickup (pu)", "0.94", "0.88", "2027-08-15", "MISMATCH"],
           [z(ts("2027-09-28T22:02Z")), "ERCOT relay settings audit", "GW-SYS-RTU-05", "SUB-05", "27-UV pickup (pu)", "0.88", "0.88", "2027-08-15", "MATCH"],
           [z(M.T["rtu4_found"]), "internal configuration review", "GW-SYS-RTU-04", "SUB-04", "configuration file last_modified", f"{z(M.T['cfg_rtu4'])} by GW-ENG-VELA", "2027-08-15T16:02:11Z by GW-ENG-VELA", "2027-08-15", "MISMATCH"],
           [z(ts("2027-10-02T21:20Z")), "evidence export", JMP, "remote-access gateway", "session log export SLE-2027-10-02", "", "", "", "EXPORTED"],
           [z(ts("2027-10-02T21:40Z")), "evidence export", HIST1, "historian", "audit log export HAE-2027-10-02", "2027-09-07 to 2027-10-02", "", "", "EXPORTED"]]
    n8 = write_csv(f"{A}/settings_audits.csv", ["time_utc", "audit", "device", "site", "item", "found", "record_value", "record_date", "result"], aud)
    # ---- endpoint protection
    av = []
    for d in range(day_utc(SPAN_START) - 1, day_utc(SPAN_END - 1) + 1):
        for _ in range(int(g.poisson(40) * (0.3 if 0 <= d <= 4 else 1))):
            h = WORKST[g.integers(len(WORKST))]
            a = D0_EPOCH + d * DAY + int(g.integers(0, DAY))
            ev, det = [("DEFINITIONS_UPDATED", "engine 4.18"), ("SCAN_COMPLETED", "0 threats"), ("REALTIME_PROTECTION_ENABLED", "policy refresh"), ("THREAT_QUARANTINED", "PUA:Win32/Toolbar"),
                       ("AGENT_HEARTBEAT_MISSED", "")][int(g.choice(5, p=[0.45, 0.33, 0.1, 0.04, 0.08]))]
            av.append([z(a), h["hostname"], h["ip"], ev, det, "system"])
    ga = rng("host_audit", "av_toggle")
    for i in range(34):
        h = CORP[ga.integers(len(CORP))]
        if h["hostname"] == WS04:
            continue
        a = local_ts(int(ga.integers(-58, 118)), f"{int(ga.integers(7, 18)):02d}:{int(ga.integers(0, 60)):02d}") + int(ga.integers(0, 60))
        who = str(ga.choice([USERS[ga.integers(len(USERS))]["username"], "svc_sccm", "svc_edr"]))
        av.append([z(a), h["hostname"], h["ip"], "REALTIME_PROTECTION_DISABLED", str(ga.choice(["setting changed locally", "disabled by management task", "setting changed locally"])), who])
        if ga.random() < 0.8:
            av.append([z(a + int(ga.integers(240, 5400))), h["hostname"], h["ip"], "REALTIME_PROTECTION_ENABLED", str(ga.choice(["policy refresh", "setting changed locally"])), "system"])
    av.append([z(AV_OFF_T), WS04, IP[WS04], "REALTIME_PROTECTION_DISABLED", "setting changed locally", WS04_USER["username"]])
    av.sort(key=lambda r: r[0])
    n9 = write_csv(f"{A}/endpoint_protection.csv", ["time_utc", "host", "ip", "event", "detail", "initiated_by"], av)
    # ---- mail gateways
    def mail_bg(a, gw, dom, rcpts, n, gg):
        out = []
        subj = ["Re: schedule", "Invoice attached", "Meeting notes", "Outage map update", "Shift roster", "FW: vendor quote", "Storm readiness checklist", "Timesheet reminder", "Newsletter", "Delivery notice"]
        for _ in range(n):
            t = a + int(gg.integers(0, DAY))
            ext = gg.random() < 0.6
            out.append([z(t), gw, "inbound" if ext else "internal", f"{hsh('s', t, n=6)}@{'partner-mail.example' if ext else dom}", "partner-mail.example" if ext else dom,
                        rcpts[gg.integers(len(rcpts))], str(gg.choice(subj)), "" if gg.random() < 0.8 else f"{hsh('a', t, n=5)}.pdf", int(gg.gamma(2, 40000)), "clean", "delivered", "<" + hsh("m", t, gw) + "@mail>"])
        return out
    cb_rc = [u["email"] for u in USERS]
    mail = []
    for d in range(day_utc(SPAN_START) - 1, day_utc(SPAN_END - 1) + 1):
        mail += mail_bg(D0_EPOCH + d * DAY, "GW-GW-MAIL-01", "cbpwa.example", cb_rc, int(110 * (0.3 + work_factor(D0_EPOCH + d * DAY + 15 * 3600))), g)
    mail.append([z(LURE_T), "GW-GW-MAIL-01", "inbound", "preparedness@cbpwa-vendor-support.com", "cbpwa-vendor-support.com", WS04_USER["email"], "FEMA hurricane preparedness guidance for utilities",
                 "FEMA-PREP-GUIDANCE-2027.pdf.exe", 412877, "clean", "delivered", "<" + hsh("lure") + "@cbpwa-vendor-support.com>"])
    mail.sort(key=lambda r: r[0])
    cols = ["time_utc", "gateway", "direction", "sender", "sender_domain", "recipient", "subject", "attachment_names", "size_bytes", "verdict", "action", "message_id"]
    n10 = write_csv(f"{A}/mail_gateway_cbpwa.csv", cols, mail)
    # vendor (Brightwake Marine Systems): one message opened by one mailbox
    bw = [f"{n}@brightwake-marine.example" for n in ("o.pryce", "service.desk", "j.tran", "m.okoye", "remote.support", "accounts", "l.hart", "d.silva")]
    g2 = rng("host_audit", "bw")
    mail = []
    for d in range(-60, -20):
        mail += mail_bg(D0_EPOCH + d * DAY, "BRW-MX-01", "brightwake-marine.example", bw, 25, g2)
    t_bw = ts("2027-08-12T14:41Z") + 7
    mail.append([z(t_bw), "BRW-MX-01", "inbound", "class-renewals@marine-certification-notices.example", "marine-certification-notices.example", "remote.support@brightwake-marine.example",
                 "Remote access certificate renewal required", "", 48211, "clean", "delivered", "<" + hsh("bw") + "@marine-certification-notices.example>"])
    mail.sort(key=lambda r: r[0])
    write_csv(f"{A}/mail_gateway_brightwake.csv", cols, mail)
    write_csv(f"{A}/mail_url_clicks_brightwake.csv", ["time_utc", "gateway", "mailbox", "message_id", "url_host", "client_ip", "sender_network"],
              [[z(t_bw + 1260), "BRW-MX-01", "remote.support@brightwake-marine.example", "<" + hsh("bw") + "@marine-certification-notices.example>", "certificates.marine-certification-notices.example",
                "198.51.100.10", "ASN 64512"]])
    # city and air-station gateways: about 1,200 messages over three days, ten mailboxes click, those accounts then log on from the same network
    g3 = rng("host_audit", "aid_mail")
    city = [f"{hsh('c', i, n=7)}@cctexas.example" for i in range(900)]
    nas = [f"{hsh('n', i, n=7)}@nascc.navy.example" for i in range(400)]
    rows_c, rows_n, clicks, sso = [], [], [], []
    for d in range(-2, 8):
        rows_c += mail_bg(D0_EPOCH + d * DAY, "CITY-MX-02", "cctexas.example", city, 160, g3)
        rows_n += mail_bg(D0_EPOCH + d * DAY, "NASCC-MX-01", "nascc.navy.example", nas, 90, g3)
    a0, a1 = ts("2027-09-15T13:00Z"), ts("2027-09-18T02:00Z")
    for i in range(1200):
        t = a0 + int(g3.integers(0, a1 - a0))
        is_city = i < 840
        rc = city[g3.integers(len(city))] if is_city else nas[g3.integers(len(nas))]
        (rows_c if is_city else rows_n).append([z(t), "CITY-MX-02" if is_city else "NASCC-MX-01", "inbound", f"assistance-{int(g3.integers(10, 99))}@aid-help-portal.example", "aid-help-portal.example", rc,
                                                 "Disaster assistance: confirm your account to receive aid", "", int(g3.integers(9000, 16000)), "clean", "delivered",
                                                 "<" + hsh("aid", i) + "@aid-help-portal.example>"])
    clickers = [(city[i * 37 % 900], "CITY-MX-02") for i in range(7)] + [(nas[i * 53 % 400], "NASCC-MX-01") for i in range(3)]
    for i, (mb, gw) in enumerate(clickers):
        t = a0 + 3600 + i * 5 * 3600 + int(g3.integers(0, 3000))
        clicks.append([z(t), gw, mb, "aid-help-portal.example", f"10.{60 if gw.startswith('CITY') else 61}.{int(g3.integers(1, 200))}.{int(g3.integers(2, 250))}"])
        t2 = t + int(g3.integers(1800, 9 * 3600))
        sso.append([z(t2), "city single sign-on" if gw.startswith("CITY") else "base webmail", mb, f"203.0.113.{int(g3.integers(17, 81))}", "ASN 64512", "SUCCESS", "password", "new device"])
    for i in range(2600):
        t = D0_EPOCH - 2 * DAY + int(g3.integers(0, 10 * DAY))
        is_city = g3.random() < 0.7
        mb = city[g3.integers(len(city))] if is_city else nas[g3.integers(len(nas))]
        sso.append([z(t), "city single sign-on" if is_city else "base webmail", mb, home_ip(g3),
                    f"ASN {int(g3.choice([7018, 20057, 11427, 22773]))}", "SUCCESS" if g3.random() < 0.96 else "FAILED", "password+token", "known device" if g3.random() < 0.9 else "new device"])
    rows_c.sort(key=lambda r: r[0]); rows_n.sort(key=lambda r: r[0]); clicks.sort(key=lambda r: r[0]); sso.sort(key=lambda r: r[0])
    write_csv(f"{A}/mail_gateway_city.csv", cols, rows_c)
    write_csv(f"{A}/mail_gateway_airstation.csv", cols, rows_n)
    write_csv(f"{A}/mail_url_clicks_city_airstation.csv", ["time_utc", "gateway", "mailbox", "url_host", "client_ip"], clicks)
    write_csv(f"{A}/account_logons_city_airstation.csv", ["time_utc", "service", "account", "src_ip", "src_network", "result", "auth_method", "device"], sso)
    print(f"host_audit_logs: sessions {n1:,}, historian {n2:,}, config {n3}, commands {n4:,}, suppression {n5}, files {n6}, change {n7}, audits {n8}, endpoint {n9:,}, mail {n10:,}")


# ======================================================================================
# aid portal access logs
# ======================================================================================
PORTAL_COLS = ["time_utc", "system", "client_ip", "client_network", "method", "path", "status", "event", "account_ref", "user_agent_family", "bytes"]
UA = ["Chrome/Windows", "Safari/iOS", "Chrome/Android", "Edge/Windows", "Firefox/Windows", "Safari/macOS", "Samsung/Android"]
UA_P = [0.24, 0.31, 0.22, 0.08, 0.03, 0.07, 0.05]


def gen_portal():
    g = rng("portal_access")
    P = f"{NET}/portal"
    files = {}

    def add(t, system, ip, net, method, path, status, event, acct="", ua=None, size=None):
        mon = dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m")
        files.setdefault((system, mon), []).append([z(t), system, ip, net, method, path, status, event, acct, ua or UA[int(g.choice(len(UA), p=UA_P))], size if size is not None else int(g.integers(900, 42000))])

    aid, naslog = "EXT-AIDPORTAL-01", "EXT-NASLOG-02"
    OPEN_T = min(ts(r["submitted_utc"]) for r in csv.DictReader(open(os.path.join(ROOT, "05_other_sources/payments/aid_applications.csv"), encoding="utf-8", newline="")) if r["submitted_utc"]) - 60
    start = SPAN_START
    # ordinary visitors, both systems, whole span
    for d in range(int((start - D0_EPOCH) // DAY), day_utc(SPAN_END - 1) + 1):
        t0 = D0_EPOCH + d * DAY
        boost = 6 if 0 <= d < 60 else 1                       # people looking for information after the storm
        for _ in range(int(g.poisson(60 * boost))):
            t = t0 + int(g.integers(0, DAY))
            add(t, aid, f"100.{g.integers(64, 127)}.{g.integers(1, 250)}.{g.integers(2, 250)}", f"ASN {int(g.choice([7018, 20057, 11427, 22773, 21928]))}", "GET",
                str(g.choice(["/", "/disasters/current", "/help/eligibility", "/help/documents", "/es/ayuda", "/login", "/status"])), 200, "page_view")
        for _ in range(int(g.poisson(45 * (0.3 if -1 <= d <= 5 else 1)))):
            t = t0 + int(g.integers(0, DAY))
            ok = g.random() < 0.97
            add(t, naslog, f"10.200.{g.integers(1, 40)}.{g.integers(2, 250)}", "base network", "POST" if g.random() < 0.3 else "GET",
                str(g.choice(["/login", "/orders", "/fuel/requests", "/inventory", "/reports/daily"])), 200 if ok else 401, "login_success" if ok else "login_failed",
                f"nas-{hsh('u', int(g.integers(0, 180)), n=6)}", "Edge/Windows")
    # probing of both login pages from one network, 10-13 August; no account entered successfully
    a0, a1 = ts("2027-08-10T05:00Z"), ts("2027-08-13T05:00Z")
    paths = ["/login", "/account/recover", "/account/register", "/api/v1/session", "/admin", "/login.aspx", "/owa", "/status", "/.well-known/security.txt", "/help/contact"]
    for i in range(3400):
        t = a0 + int(g.integers(0, a1 - a0))
        sysid = aid if i % 5 else naslog
        p = paths[int(g.integers(len(paths)))]
        st = 401 if p in ("/login", "/api/v1/session", "/login.aspx") else (404 if p in ("/admin", "/owa", "/login.aspx") else 200)
        add(t, sysid, f"203.0.113.{int(g.integers(17, 81))}", "ASN 64512", "POST" if st == 401 else "GET", p, st, "login_failed" if st == 401 else "page_view",
            (str(g.choice(["admin", "administrator", "test", "fema", "support", "info", "claims", "jsmith", "mgarcia", "applicant"])) + (str(int(g.integers(1, 99))) if g.random() < 0.5 else "")) if st == 401 else "", "python-requests" if i % 3 else "curl", int(g.integers(200, 2400)))
    # registrations, account changes and sign-ins, mirrored from the applications data so the two streams agree
    with open(os.path.join(ROOT, "05_other_sources/payments/aid_applications.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            net = f"ASN {r['source_asn']}" if r["source_asn"] else ""
            if r["record_type"] == "application" and r["channel"] == "web":
                t = ts(r["submitted_utc"])
                add(max(OPEN_T, t - int(g.integers(300, 1500))), aid, r["source_ip"], net, "POST", "/account/register", 201, "account_created", r["account_id"])
                add(t, aid, r["source_ip"], net, "POST", "/applications", 201, "application_submitted", r["account_id"])
                for _ in range(int(g.poisson(1.3)) if not r["source_ip"].startswith("203.0.113.") else 0):   # people come back to check their status, and mistype passwords
                    tb = t + int(g.gamma(1.5, 5 * DAY))
                    if tb < SPAN_END:
                        if g.random() < 0.09:
                            add(tb - int(g.integers(8, 90)), aid, r["source_ip"], net, "POST", "/login", 401, "login_failed", r["account_id"], None, int(g.integers(470, 560)))
                        add(tb, aid, r["source_ip"], net, "POST", "/login", 200, "login_success", r["account_id"])
                        add(tb + int(g.integers(5, 200)), aid, r["source_ip"], net, "GET", "/status", 200, "page_view", r["account_id"])
            elif r["record_type"] == "account_change" and r["login_utc"]:
                tl, tc = ts(r["login_utc"]), ts(r["changed_utc"])
                if r["source_ip"].startswith("203.0.113."):               # a few wrong guesses against the same account before the one that works
                    for k in range(int(g.integers(0, 5))):
                        add(tl - int(g.integers(20, 6 * 3600)), aid, f"203.0.113.{int(g.integers(17, 81))}", net, "POST", "/login", 401, "login_failed", r["account_id"], "python-requests", int(g.integers(470, 560)))
                add(tl, aid, r["source_ip"], net, "POST", "/login", 200, "login_success", r["account_id"], "python-requests" if r["source_ip"].startswith("203.0.113.") else None)
                add(tc, aid, r["source_ip"], net, "POST", "/account/" + r["field_changed"].split(" restored")[0].replace(" ", "-"), 200,
                    "profile_updated: " + r["field_changed"], r["account_id"], "python-requests" if r["source_ip"].startswith("203.0.113.") else None)
    # automated sign-in attempts in bursts, 15-24 November: about 220,000 failures
    b0, b1 = ts("2027-11-15T06:00Z"), ts("2027-11-24T06:00Z")
    nb = int(g.integers(55, 75))
    bursts = np.sort(g.integers(b0, b1 - 3 * 3600, nb))
    per = g.multinomial(int(g.integers(218200, 221400)), g.dirichlet(np.full(nb, 1.6)))
    ipw = g.dirichlet(np.full(64, 0.9))
    for bt, n in zip(bursts, per):
        tt = bt + np.sort(g.integers(0, int(g.integers(1500, 4 * 3600)), n))
        ips = 17 + g.choice(64, n, p=ipw)
        sizes = g.integers(470, 560, n)
        for t, ipn, sz in zip(tt, ips, sizes):
            add(int(t), aid, f"203.0.113.{int(ipn)}", "ASN 64512", "POST", "/login", 401, "login_failed", f"ACC-{hsh('cs', int(t), int(ipn), n=10).upper()}", "python-requests", int(sz))
    total = 0
    for (system, mon), rows in sorted(files.items()):
        rows.sort(key=lambda r: r[0])
        name = "aid_portal_access" if system == aid else "base_logistics_access"
        total += write_csv(f"{P}/{name}_{mon}.csv", PORTAL_COLS, rows)
    print(f"portal_access_logs: {total:,} rows in {len(files)} files")


if __name__ == "__main__":
    parts = sys.argv[1:] or ["siem", "zeek", "audit", "portal"]
    for p in parts:
        {"siem": gen_siem, "zeek": gen_zeek, "audit": gen_audit, "portal": gen_portal}[p]()
