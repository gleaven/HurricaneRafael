"""Stream descriptions and probes for the IT/security logs (see scripts/check_streams.py).
Every probe reads the files on disk."""
import csv
import glob
import os

from common import ROOT, reg, ts, iso, D0_EPOCH

NET = os.path.join(ROOT, "05_other_sources", "network_logs")
_c = {}


def rows(rel_glob):
    if rel_glob not in _c:
        out = []
        for fp in sorted(glob.glob(os.path.join(NET, rel_glob))):
            with open(fp, encoding="utf-8", newline="") as fh:
                out += list(csv.DictReader(fh))
        _c[rel_glob] = out
    return _c[rel_glob]


def zeek(name, day):
    key = ("z", name, day)
    if key not in _c:
        out, fields = [], None
        fp = os.path.join(NET, "zeek", day, f"{name}.log")
        if os.path.exists(fp):
            for line in open(fp, encoding="utf-8"):
                if line.startswith("#fields"):
                    fields = line.rstrip("\n").split("\t")[1:]
                elif not line.startswith("#"):
                    out.append(dict(zip(fields, line.rstrip("\n").split("\t"))))
        _c[key] = out
    return _c[key]


def siem():
    return rows("siem/siem_alerts_*.csv")


def by_id(aid):
    if "siem_ix" not in _c:
        _c["siem_ix"] = {r["alert_id"]: r for r in siem()}
    return _c["siem_ix"].get(aid)


def siem_day_counts():
    if "sd" not in _c:
        d = {}
        for r in siem():
            d[r["time_utc"][:10]] = d.get(r["time_utc"][:10], 0) + 1
        _c["sd"] = d
    return _c["sd"]


HOSTS = {h["hostname"]: h for h in reg("gw_host_registry")["hosts"]}
WS04_IP = HOSTS["GW-WS-IT-04"]["ip"]
HISTDMZ_IP = HOSTS["GW-SRV-HIST-DMZ"]["ip"]


def vela_sessions():
    """Sessions under the one engineer's account while HR records show him on leave, out of state (2027-09-07 to 2027-09-21),
    plus later sessions under that account from outside the country."""
    r = [x for x in rows("audit/remote_access_sessions.csv") if x["account"] == "GW-ENG-VELA"]
    return [x for x in r if "2027-09-07" <= x["login_utc"][:10] <= "2027-09-21" or x["src_country"] != "US"]


# ---------------------------------------------------------------- probes
def p_0106():
    a, b = "2027-08-10T05:00", "2027-08-13T05:00"
    import netmap
    r = [x for x in rows("portal/*_2027-08.csv") if x["client_ip"] in netmap.STORY_SET and a <= x["time_utc"] < b]
    assert len({x["client_ip"] for x in r}) == 64 and {x["client_network"] for x in r} == {"ASN 64512"}
    systems = {x["system"] for x in r}
    ok_logins = [x for x in r if x["event"] == "login_success"]
    return (len(r) > 1000 and len(systems) == 2 and not ok_logins, f"{len(r)} requests from ASN 64512 to {sorted(systems)}, {len(ok_logins)} successful logins")


def p_0107():
    m = [x for x in rows("audit/mail_gateway_brightwake.csv") if x["time_utc"].startswith("2027-08-12") and x["sender_domain"] == "marine-certification-notices.example"]
    allc = rows("audit/mail_url_clicks_brightwake.csv")           # the report holds every followed link of the window
    c = [x for x in allc if x["url_host"].endswith("marine-certification-notices.example")]
    return (len(m) == 1 and len(c) == 1 and c[0]["mailbox"] == m[0]["recipient"] and len(allc) > 5,
            f"{len(m)} message delivered {m[0]['time_utc'] if m else ''}, its link followed by {len(c)} mailbox ({len(allc) - len(c)} other followed links in the report)")


def p_101_siem():
    r = by_id("SE3-NET-9941-20270831T0317Z")
    ok = bool(r) and r["src_host"] == "GW-WS-IT-04" and r["src_ip"] == WS04_IP and r["dst_ip"] == "104.21.88.43" and r["dst_port"] == "443" and "bytes_out=318" in r["detail"] \
        and r["priority"] == "LOW" and r["disposition"] == "FALSE_POSITIVE" and r["closed_utc"].startswith("2027-08-31T14:22") and r["closed_by"] == "tperez" and "whitelisted vendor range" in r["close_note"]
    return ok, f"{r['alert_id']} closed {r['closed_utc']} {r['disposition']}" if r else "alert not found"


def p_101_zeek():
    c = [x for x in zeek("conn", "2027-08-31") if x["id.orig_h"] == WS04_IP and x["id.resp_h"] == "104.21.88.43"]
    s = [x for x in zeek("ssl", "2027-08-31") if x["id.resp_h"] == "104.21.88.43"]
    first = min(c, key=lambda x: float(x["ts"])) if c else None
    ok = bool(first) and iso(float(first["ts"])).startswith("2027-08-31T03:17") and abs(float(first["duration"]) - 4.2) < 0.01 and first["orig_bytes"] == "318" and first["resp_bytes"] == "212" \
        and any(x["server_name"] == "update-cdn.vantagesec-telemetry.net" and x["version"] == "TLSv13" for x in s)
    return ok, f"first flow {iso(float(first['ts']))} {first['duration']}s {first['orig_bytes']}/{first['resp_bytes']} bytes" if first else "no flow"


def p_001_audit():
    m = [x for x in rows("audit/mail_gateway_cbpwa.csv") if "FEMA-PREP-GUIDANCE-2027.zip" in x["attachment_names"]]
    a = [x for x in rows("audit/endpoint_protection.csv") if x["host"] == "GW-WS-IT-04" and x["event"] == "REALTIME_PROTECTION_DISABLED"]
    ok = len(m) == 1 and m[0]["sender_domain"] == "cbpwa-vendor-support.com" and len(a) == 1 and m[0]["time_utc"] < a[0]["time_utc"] and a[0]["time_utc"][11:16] == "13:21" and m[0]["time_utc"][11:16] == "13:14"
    return ok, f"attachment delivered {m[0]['time_utc'] if m else '-'}; protection disabled {a[0]['time_utc'] if a else '-'}"


def p_001_zeek():
    d = [x for x in zeek("dns", "2027-08-30") if x["query"] == "update-cdn.meridiancontrols.net" and x["id.orig_h"] == WS04_IP]
    return (len(d) >= 1 and iso(float(d[0]["ts"]))[11:16] == "13:23", f"{len(d)} query at {iso(float(d[0]['ts'])) if d else '-'}")


def p_102_audit():
    h = [x for x in rows("audit/historian_access.csv") if x["session_id"] == "HIST-20270907-00441"]
    ok = len(h) == 1 and h[0]["account"] == "GW-SYS-JMP-01\\svc_fieldops_ext" and h[0]["tags_queried"] == "847" and h[0]["duration_s"] == "862" and "relay" in h[0]["tag_groups"] and "tap" in h[0]["tag_groups"]
    return ok, f"{h[0]['start_utc']} {h[0]['tags_queried']} tags {h[0]['duration_s']} s" if h else "session not found"


def p_102_siem():
    r = by_id("SE3-OT-1104-20270907T0244Z")
    rc = [x for x in rows("siem/rule_changes.csv") if x["rule_id"] == "MAINT-EXCEPT-0892" and x["action"] == "CREATE"]
    ok = bool(r) and r["src_host"] == "GW-SYS-JMP-01" and r["dst_host"] == "GW-SRV-HIST-01" and "session_duration=862s" in r["detail"] and "tags_queried=847" in r["detail"] and r["priority"] == "LOW" \
        and r["disposition"] == "AUTO_ACK" and "MAINT-EXCEPT-0892" in r["close_note"] and len(rc) == 1 and rc[0]["time_utc"].startswith("2027-08-19T11:34") and rc[0]["changed_by"] == "svc_fieldops_ext" and not rc[0]["change_ticket"]
    return ok, "alert auto-acknowledged by exception rule created " + (rc[0]["time_utc"] if rc else "?")


def p_002_audit():
    s = [x for x in vela_sessions() if "2027-09-07" <= x["login_utc"][:10] <= "2027-09-10" and x["src_ip"].startswith("185.220.")]
    gb = sum(int(x["bytes_out"]) for x in s) / 1e9
    h = [x for x in rows("audit/historian_access.csv") if x["start_utc"].startswith("2027-09-08T23:40") and "relay_config" in x["tag_groups"] and "SUB-01..SUB-05" in x["tag_groups"]]
    return (len(s) == 7 and abs(gb - 4.1) < 0.05 and len(h) == 1, f"{len(s)} sessions from 185.220.x, {gb:.2f} GB out; relay-config read at {h[0]['start_utc'] if h else '-'}")


def p_002_zeek():
    c = [x for x in zeek("conn", "2027-09-08") if x["id.resp_p"] == "445" and {x["id.orig_h"], x["id.resp_h"]} == {WS04_IP, HISTDMZ_IP}]
    big = [x for x in c if 1.85e9 <= max(int(x["orig_bytes"]), int(x["resp_bytes"])) <= 1.95e9]
    return (len(big) == 1, f"{len(big)} flow of {max(int(big[0]['orig_bytes']), int(big[0]['resp_bytes'])) / 1e9:.2f} GB on TCP 445" if big else "no such flow")


def p_003_audit():
    c = [x for x in rows("audit/ot_config_changes.csv") if x["device"] == "GW-SYS-RTU-01" and x["old_value"] == "0.88" and x["new_value"] == "0.94"]
    s = [x for x in rows("audit/alarm_suppression_audit.csv") if x["time_utc"].startswith("2027-09-11T17:09") and x["action"] == "ADD" and "relay trip" in x["alarm_point"]]
    f = [x for x in rows("audit/change_management.csv") if x["record_id"] == "CHG-FREEZE-27-09"]
    subs = {x["alarm_point"].split("(")[1][:6] for x in s}
    ok = len(c) == 1 and c[0]["time_utc"].startswith("2027-09-11T17:04") and c[0]["session_user"] == "GW-ENG-VELA" and not c[0]["change_ticket"] and subs == {"SUB-01", "SUB-02", "SUB-03", "SUB-04"} \
        and all(x["changed_by"] == "GW-ENG-VELA" and not x["change_ticket"] for x in s) and len(f) == 1
    return ok, f"threshold write {c[0]['time_utc'] if c else '-'}; {len(s)} relay-trip alarms suppressed at 17:09 for {sorted(subs)}"


def p_103_audit():
    f = [x for x in rows("audit/file_integrity.csv") if x["path"].endswith("relayconfigs\\sub02\\rtu_config_draft.xml") and x["time_utc"].startswith("2027-09-11T22:11")]
    ok = len(f) == 1 and f[0]["time_utc"].startswith("2027-09-11T22:11") and f[0]["new_hash"] == "sha256=cd926b73217c0994" and f[0]["previous_hash"] == "sha256=2e78eabd6a1aa42f" \
        and "1200A -> 2400A" in f[0]["diff_summary"] and all(k in f[0]["diff_summary"] for k in ("R-02A", "R-02B", "R-02C"))
    return ok, f"file modified {f[0]['time_utc']}" if f else "no record"


def p_103_siem():
    r = by_id("SE3-OT-2201-20270911T2211Z")
    ok = bool(r) and r["src_host"] == "GW-SYS-JMP-01" and "FILE_WRITE" in r["detail"] and "relayconfigs\\sub02\\rtu_config_draft.xml" in r["detail"] and r["priority"] == "MEDIUM" \
        and r["closed_by"] == "jperez" and r["closed_utc"].startswith("2027-09-11T22:58") and r["disposition"] == "AUTHORIZED_MAINTENANCE" and "Storm prep relay adjustment" in r["close_note"]
    return ok, f"closed {r['closed_utc']} as {r['disposition']}" if r else "alert not found"


def p_104_siem():
    want = {"2027-09-12": 4812, "2027-09-13": 7341, "2027-09-14": 18340, "2027-09-15": 16207, "2027-09-16": 14884, "2027-09-17": 12201, "2027-09-18": 6633}
    got = {d: siem_day_counts().get(d, 0) for d in want}
    ids = ["SE3-OT-1104-20270914T0831Z", "SE3-NET-9941-20270915T0117Z", "SE3-OT-3301-20270915T0944Z"]
    dis = [by_id(i) for i in ids]
    sm = [x for x in rows("siem/rule_changes.csv") if x["rule_id"] == "SE3-BULK-STORM-01" and x["action"] == "ACTIVATE"]
    ok = got == want and all(d and d["disposition"] == "STORM_BULK_DISMISSED" for d in dis) and len(sm) == 1 and sm[0]["time_utc"].startswith("2027-09-14T06:14") and sm[0]["changed_by"] == "jperez" and "44" in sm[0]["description"]
    return ok, f"daily counts {list(got.values())}; {sum(1 for d in dis if d)} named alerts bulk-dismissed; storm mode on {sm[0]['time_utc'] if sm else '-'}"


def p_0306():
    c = [x for x in rows("audit/mail_gateway_city.csv") if x["sender_domain"] == "aid-help-portal.example"]
    n = [x for x in rows("audit/mail_gateway_airstation.csv") if x["sender_domain"] == "aid-help-portal.example"]
    allcl = rows("audit/mail_url_clicks_city_airstation.csv")     # the report holds every followed link of the window
    cl = [x for x in allcl if x["url_host"] == "aid-help-portal.example"]
    ck = {x["mailbox"]: x["time_utc"] for x in cl}                   # ordinary staff also sign on from that provider; the follow-on sign-ons are those of the clicked accounts
    lg = [x for x in rows("audit/account_logons_city_airstation.csv") if x["src_network"] == "ASN 64512" and x["account"] in ck and x["time_utc"] > ck[x["account"]]]
    win = all("2027-09-15T05:00" <= x["time_utc"] < "2027-09-18T05:00" for x in c + n)
    city_clicks = sum(1 for x in cl if x["gateway"].startswith("CITY"))
    ok = 1100 <= len(c) + len(n) <= 1300 and win and len(cl) == 10 and city_clicks == 7 and {x["account"] for x in lg} == {x["mailbox"] for x in cl} \
        and all(any(l["account"] == k["mailbox"] and l["time_utc"] > k["time_utc"] for l in lg) for k in cl)
    return ok and len(allcl) >= 6 * len(cl), (f"{len(c) + len(n)} messages, {len(cl)} mailboxes followed its link ({city_clicks} city, {len(cl) - city_clicks} air station; "
                                              f"{len(allcl) - len(cl)} other followed links in the report), {len(lg)} follow-on logons from ASN 64512")


def p_105_audit():
    s = [x for x in rows("audit/alarm_suppression_audit.csv") if x["action"] == "ADD" and "2027-09-09" <= x["time_utc"][:10] and x["time_utc"] < "2027-09-23T04:00"]
    cats = {x["category"] for x in s}
    batches = {x["time_utc"][:16] for x in s}
    return (len(s) == 82 and {"pump flow", "water quality sensor", "substation relay"} <= cats, f"{len(s)} alarms added since 2027-09-09 in {len(batches)} batches; categories {sorted(cats)}")


def p_105_siem():
    r = by_id("SE3-OT-3301-20270923T0400Z")
    ok = bool(r) and "suppressed_alarm_count=94" in r["detail"] and "threshold=30" in r["detail"] and "=7" in r["detail"] and r["src_host"] == "GW-SYS-JMP-01" and r["priority"] == "HIGH"
    return ok, r["detail"] if r else "alert not found"


def p_009():
    q = [x for x in rows("audit/change_management.csv") if x["record_id"] == "QRY-CHG-27-311"]
    t = [x for x in rows("audit/change_management.csv") if x["record_id"] == "TXRC-2027-09-28-004"]
    a = [x for x in rows("audit/settings_audits.csv") if x["device"] == "GW-SYS-RTU-01" and x["result"] == "MISMATCH"]
    ok = len(q) == 1 and "0 approved work orders" in q[0]["summary"] and len(t) == 1 and "possible relay config drift at Riverside Switching Station" in t[0]["summary"] \
        and len(a) == 1 and a[0]["found"] == "0.94" and a[0]["record_value"] == "0.88" and a[0]["time_utc"].startswith("2027-09-28T22")
    return ok, f"audit {a[0]['time_utc'] if a else '-'}: found {a[0]['found'] if a else '-'}, record {a[0]['record_value'] if a else '-'}; no approved work order; ticket {t[0]['record_id'] if t else '-'}"


def p_010():
    a = [x for x in rows("audit/settings_audits.csv") if x["device"] == "GW-SYS-RTU-04" and x["result"] == "MISMATCH"]
    ok = len(a) == 1 and "2027-09-11T22:11" in a[0]["found"] and "GW-ENG-VELA" in a[0]["found"] and a[0]["time_utc"].startswith("2027-09-30T18")
    stamp = a[0]["found"].split(" ")[0] if a else ""
    s = [x for x in vela_sessions() if x["login_utc"] <= stamp <= x["logout_utc"] and x["src_ip"].startswith("185.220.")]
    return (ok and len(s) == 1, f"file stamp {stamp}; matching session from {s[0]['src_ip'] if s else '-'}")


def p_106():
    """The fourteen historian sessions are the contractor-account sessions that fall inside the remote sessions
    made under the engineer's account from outside the country (the join a participant has to make)."""
    r = by_id("SE3-ML-0044-20271002T1433Z")
    win = [(x["login_utc"], x["logout_utc"]) for x in vela_sessions()]
    h = [x for x in rows("audit/historian_access.csv") if x["account"] == "GW-SYS-JMP-01\\svc_fieldops_ext" and any(a <= x["start_utc"] <= b for a, b in win)]
    ids = sorted(x["session_id"] for x in h)
    ok = bool(r) and all(k in r["detail"] for k in ("session_id=HIST-20271002-00917", "src_asn=AS-209144", "tags_queried=1241", "anomaly_score=3.84")) and r["priority"] == "ANOMALY_HIGH" \
        and len(h) == 14 and sum(int(x["tags_queried"]) for x in h) == 11847 and "HIST-20270907-00441" in ids and "HIST-20271002-00917" in ids
    return ok, f"{len(h)} historian sessions inside the foreign remote sessions, {sum(int(x['tags_queried']) for x in h):,} tags; anomaly alert {'present' if r else 'missing'}"



def p_011():
    s = vela_sessions()
    hours = sum(int(x["duration_s"]) for x in s) / 3600
    cc = {x["src_country"] for x in s}
    e = [x for x in rows("audit/settings_audits.csv") if x["result"] == "EXPORTED" and x["time_utc"].startswith("2027-10-02T21")]
    return (len(s) == 14 and abs(hours - 11.4) < 0.05 and {"NL", "RO", "SG"} <= cc and len(e) == 2, f"{len(s)} sessions, {hours:.1f} h, source countries {sorted(cc)}; {len(e)} exports")


def p_107_siem():
    """Control-network rules fall silent when the control network is cut off (12:00Z on D+28); the corporate rules carry on."""
    dev = ("SE3-OT-6001", "SE3-OT-6004", "SE3-OT-6010")
    before = sum(1 for x in siem() if x["rule_id"] in dev and "2027-10-11T12" <= x["time_utc"] < "2027-10-12T12") / 24
    after = sum(1 for x in siem() if x["rule_id"] in dev and "2027-10-12T12" <= x["time_utc"] < "2027-10-13T12") / 24
    corp_b = sum(1 for x in siem() if x["category"] == "policy" and x["time_utc"].startswith("2027-10-11"))
    corp_a = sum(1 for x in siem() if x["category"] == "policy" and x["time_utc"].startswith("2027-10-13"))
    last = max((x["time_utc"] for x in siem() if x["rule_id"] == "SE3-NET-9941" and x["dst_ip"] == "104.21.88.43"), default="")
    return (after <= 0.15 * before and corp_a >= 0.6 * corp_b and last.startswith("2027-10-12T10:04"),
            f"control-network device rules {before:.1f}/h before the cut, {after:.1f}/h after; web-policy alerts {corp_b} two days before, {corp_a} the day after; last outbound alert {last}")


def p_107_zeek():
    last = 0.0
    for day in ("2027-10-12", "2027-10-13", "2027-10-14", "2027-10-20", "2027-11-01"):
        for x in zeek("conn", day):
            if x["id.resp_h"] == "104.21.88.43":
                last = max(last, float(x["ts"]))
    return (iso(last).startswith("2027-10-12T10:04"), f"last connection {iso(last)}")


def p_108():
    n = siem_day_counts().get("2027-10-19", 0)
    fp = sum(1 for x in siem() if x["time_utc"].startswith("2027-10-19") and x["disposition"] == "FALSE_POSITIVE")
    ml = [x for x in siem() if x["time_utc"].startswith("2027-10-19") and x["rule_id"].startswith("SE3-ML") and x["disposition"] == "OPEN"]
    rc = [x for x in rows("siem/rule_changes.csv") if x["rule_id"] == "MAINT-EXCEPT-0892" and x["action"] == "DELETE"]
    ok = n == 2312 and f"{100 * fp / max(n, 1):.1f}" == "11.3" and not ml and len(rc) == 1 and rc[0]["time_utc"].startswith("2027-10-18")
    return ok, f"{n} alerts, {100 * fp / max(n, 1):.1f}% false positive; exception rule removed {rc[0]['time_utc'] if rc else '-'}"


def p_0502():
    import netmap                                       # the provider also has ordinary customers; the sign-in runs come from its 64 addresses that also made the August requests
    r = [x for x in rows("portal/aid_portal_access_2027-11*.csv") if x["client_ip"] in netmap.STORY_SET and "2027-11-15T06:00" <= x["time_utc"] < "2027-11-24T06:00"]
    fails = sum(1 for x in r if x["event"] == "login_failed")
    ok_acc = {x["account_ref"] for x in r if x["event"] == "login_success"}
    return (215000 <= fails <= 225000 and len(ok_acc) == 410, f"{fails:,} failed logins, {len(ok_acc)} accounts entered")


PROBES = {
    ("EVT-0106", "portal_access_logs"): p_0106, ("EVT-0107", "host_audit_logs"): p_0107,
    ("GW-EVT-101", "siem_alerts"): p_101_siem, ("GW-EVT-101", "zeek_logs"): p_101_zeek,
    ("GW-EVT-001", "host_audit_logs"): p_001_audit, ("GW-EVT-001", "zeek_logs"): p_001_zeek,
    ("GW-EVT-102", "host_audit_logs"): p_102_audit, ("GW-EVT-102", "siem_alerts"): p_102_siem,
    ("GW-EVT-002", "host_audit_logs"): p_002_audit, ("GW-EVT-002", "zeek_logs"): p_002_zeek,
    ("GW-EVT-003", "host_audit_logs"): p_003_audit, ("GW-EVT-103", "host_audit_logs"): p_103_audit,
    ("GW-EVT-103", "siem_alerts"): p_103_siem, ("GW-EVT-104", "siem_alerts"): p_104_siem,
    ("EVT-0306", "host_audit_logs"): p_0306, ("GW-EVT-105", "host_audit_logs"): p_105_audit,
    ("GW-EVT-105", "siem_alerts"): p_105_siem, ("GW-EVT-009", "host_audit_logs"): p_009,
    ("GW-EVT-010", "host_audit_logs"): p_010, ("GW-EVT-106", "siem_alerts"): p_106,
    ("GW-EVT-011", "host_audit_logs"): p_011, ("GW-EVT-107", "siem_alerts"): p_107_siem,
    ("GW-EVT-107", "zeek_logs"): p_107_zeek, ("GW-EVT-108", "siem_alerts"): p_108,
    ("EVT-0502", "portal_access_logs"): p_0502,
}


# ---------------------------------------------------------------- stream descriptions
def _range(rel_glob, col):
    v = [r[col] for r in rows(rel_glob) if r.get(col)]
    return ts(min(v)[:16] + "Z"), ts(max(v)[:16] + "Z")


def _zeek_range():
    days = sorted(os.listdir(os.path.join(NET, "zeek")))
    return ts(days[0] + "T00:00Z"), ts(days[-1] + "T23:59Z")


def _header(rel_glob):
    fps = sorted(glob.glob(os.path.join(NET, rel_glob)))
    return next(csv.reader(open(fps[0], encoding="utf-8"))) if fps else []


def _audit_text():
    for fp in sorted(glob.glob(os.path.join(NET, "audit", "*.csv"))) + sorted(glob.glob(os.path.join(NET, "siem", "rule_changes.csv"))):
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                yield line


STREAMS = {
    "siem_alerts": {"time_range": lambda: _range("siem/siem_alerts_*.csv", "time_utc"),
                    "ids": lambda: {r["src_host"] for r in siem() if r["src_host"]} | {r["dst_host"] for r in siem() if r["dst_host"]},
                    "registry_ids": lambda: set(HOSTS), "columns": lambda: _header("siem/siem_alerts_*.csv"), "public_voice": False,
                    "text": lambda: (r["detail"] + " " + r["close_note"] for r in siem())},
    "zeek_logs": {"time_range": _zeek_range, "public_voice": False},
    "host_audit_logs": {"time_range": lambda: _range("audit/endpoint_protection.csv", "time_utc"), "columns": lambda: sum((_header(f"audit/{os.path.basename(f)}") for f in glob.glob(os.path.join(NET, "audit", "*.csv"))), []),
                        "public_voice": False, "text": _audit_text},
    "portal_access_logs": {"time_range": lambda: _range("portal/aid_portal_access_*.csv", "time_utc"), "columns": lambda: _header("portal/*.csv"), "public_voice": False},
}
