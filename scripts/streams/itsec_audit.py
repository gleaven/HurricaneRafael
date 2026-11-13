"""Host, access and mail audit tables of the utility (stream host_audit_logs). Called through gen_itsec.py.

Each table is the model in gen_itsec written out: the same rows the SIEM alerts and the network flows are
derived from. The mail gateway log is built here (mail_rows) and read by the network writer for the mail
transfers at the gateway.

The partner organisations' extract tables (mail gateways, link clicks and sign-ons of the city, the air
station and the vendor) are written by gen_partner_it.py as exact subsets of its own logs, not here.
"""
import functools

import gen_itsec as G
from gen_itsec import (AV_OFF_T, BYNAME, CORP, DAY, FIELD_ENG, FIRST_D, FREEZE_OFF, FREEZE_ON, HIST1, IP, JMP, LAST_D, LURE_T, NET, SCADA1, USERS, WORKST, WS04, WS04_REMOVED, WS04_USER,
                       frac, hsh, work_factor, z)
from common import D0_EPOCH, SPAN_END, local_dt, local_ts, np, rng, ts, write_csv
import ot_model as M

A = f"{NET}/audit"
MAIL_COLS = ["time_utc", "gateway", "direction", "sender", "sender_domain", "recipient", "subject", "attachment_names", "size_bytes", "verdict", "action", "message_id"]
_DA = ["gulf", "coastal", "bay", "lonestar", "south", "texas", "tri", "harbor", "delta", "summit", "pioneer", "alamo", "nueces", "padre", "laguna", "mustang", "aransas", "bluebonnet",
       "mesquite", "iron", "copper", "cedar", "oak", "river", "prairie", "sun", "red", "silver", "united", "allied", "apex", "premier", "bayfront", "portside", "shoreline", "brazos",
       "frontier", "rio", "valley", "crosswind"]
_DB = ["supply", "electric", "pump", "valve", "pipe", "steel", "controls", "engineering", "consulting", "services", "logistics", "freight", "rentals", "equipment", "safety", "labs",
       "testing", "survey", "construction", "paving", "fence", "tree", "fleet", "fuel", "printing", "office", "legal", "cpa", "insurance", "staffing", "training", "software", "telecom",
       "wireless", "hvac", "chem", "environmental", "marine", "crane", "concrete", "analytics", "metering", "transformers", "utilities"]
_DT = ["com"] * 14 + ["net"] * 2 + ["org", "us", "co", "biz"]
_LOCAL = ["billing", "sales", "info", "noreply", "support", "dispatch", "ar", "orders", "service", "accounts", "quotes", "scheduling", "admin", "newsletter"]
_SURN = ["garcia", "smith", "martinez", "johnson", "rodriguez", "nguyen", "hernandez", "brown", "lopez", "davis", "gonzalez", "wilson", "perez", "taylor", "flores", "moore", "ramirez",
         "king", "torres", "scott", "reyes", "baker", "cruz", "hall", "ortiz", "young", "morales", "allen", "gutierrez", "wright"]
_EXT = ["pdf"] * 10 + ["docx"] * 3 + ["xlsx"] * 3 + ["jpg", "png", "zip", "zip", "csv", "dwg", "pptx"]
_BLOCKED_EXT = ["docm", "xlsm", "xlsb", "iso", "img", "vhd", "js", "vbs", "hta", "lnk"]
_ATT_WORD = ["invoice", "quote", "statement", "drawing", "report", "schedule", "photo", "scan", "po", "spec", "minutes", "roster", "proposal", "manifest", "permit", "results"]
_ATT_AGENCY = ["FEMA", "TCEQ", "ERCOT", "NERC", "OSHA", "EPA", "TWDB", "PUCT", "AWWA", "NWS", "TDEM", "DHS"]
_ATT_TOPIC = ["PREP", "GUIDANCE", "AUDIT", "SCHEDULE", "SAMPLING", "PLAN", "WINTER", "READINESS", "REPORT", "FORM", "NOTICE", "CHECKLIST", "FILING", "SUMMARY", "ADVISORY", "RESPONSE",
              "TRAINING", "COMPLIANCE", "HURRICANE", "INSPECTION"]
_ATT_NOUN = ["Pump Station {n} Inspection Report", "Feeder {n} Outage Summary", "Board Packet", "Budget Draft v{v}", "Vendor Quote", "Meeting Minutes", "Safety Briefing", "Crew Schedule",
             "Relay Test Results", "Water Quality Report", "Mutual Aid Agreement", "Contract Amendment {v}", "Site Photos", "As-Built Drawings", "Timesheet", "Training Certificate",
             "Change Order {n}", "Storm Staffing Plan", "Fuel Delivery Schedule", "Vehicle {n} Service Record", "Lab Results", "Customer Complaint {n}", "Easement Map", "Permit Application",
             "Insurance Certificate", "Purchase Requisition {n}", "Substation {v} Outage Request", "Tank {v} Inspection", "Hydrant Flushing Schedule", "Rate Study"]
_SPOOF = ["Urgent: wire request", "Payroll update needed", "Re: quick favour", "Gift cards for the team", "Mailbox storage full", "Password expires today", "Shared document",
          "Voicemail from unknown caller", "Updated direct deposit form", "Invoice overdue"]


@functools.lru_cache(maxsize=None)
def domains():
    g = rng("host_audit", "mail_domains")
    seen, out = set(), []
    while len(out) < 760:
        d = f"{_DA[int(g.integers(len(_DA)))]}{_DB[int(g.integers(len(_DB)))]}{'-tx' if g.random() < 0.08 else ''}.{_DT[int(g.integers(len(_DT)))]}"
        if d not in seen:
            seen.add(d)
            out.append(d)
    w = 1.0 / np.arange(1, len(out) + 1) ** 1.05
    return out, w / w.sum()


def mta_ip(domain):
    """Address of the mail server a domain sends from and receives at (fixed per domain)."""
    k = int(hsh("mta", domain, n=8), 16)
    return f"{G._PREFIX[k % len(G._PREFIX)]}.{1 + (k >> 8) % 249}.{1 + (k >> 16) % 249}.{2 + (k >> 24) % 248}"


def _subject(g, t):
    n = int(g.integers(1000, 99999))
    d = (t - D0_EPOCH) / DAY
    pool = [f"Invoice {n}", f"PO {n} confirmation", f"Quote Q-{n % 9000}", f"WO-{40000 + n % 8000} status", f"Meeting notes {local_dt(t):%m/%d}", f"Outage on feeder {n % 40}", "Shift roster",
            f"Timesheet week {local_dt(t).isocalendar()[1]}", f"Delivery notice {n}", f"Pump station {1 + n % 9} inspection", f"Bid package {n % 700}", f"Safety bulletin {n % 90}",
            "Newsletter", f"Your order {n}", f"Service ticket {n}", f"Lab results {n % 4000}", f"Permit {n % 900} renewal", "Schedule", "Lunch?", f"Drawing rev {n % 12}",
            f"Statement {local_dt(t):%B}", f"Training reminder: module {n % 30}", f"Vehicle {n % 300} maintenance", "Customer callback", f"Meter exchange batch {n % 500}",
            f"Board packet {local_dt(t):%B}", "Benefits enrollment", f"Crew assignment {local_dt(t):%m/%d}", f"Regulatory filing {n % 60}", "Out of office"]
    ag = ["FEMA", "TDEM", "NWS", "DHS", "ERCOT", "PUC", "TCEQ", "CISA", "AWWA", "APPA"][n % 10]
    topic = ["hurricane preparedness guidance", "storm season checklist", "emergency fuel guidance", "mutual aid guidance", "debris management guidance", "grid restoration update",
             "cyber hygiene reminder", "drought contingency guidance", "annual reporting reminder", "grant program update", "winter readiness guidance"][(n // 10) % 11]
    aud = ["utilities", "water systems", "local governments", "critical infrastructure", "public power", "utilities", "members"][(n // 110) % 7]
    agency = f"{ag} {topic} for {aud}"
    pool += [agency]
    if -16 <= d <= 4:
        pool += [agency] * 9
        pool += ["Storm readiness checklist", "Hurricane preparedness resources", "Storm staffing plan", "Preparedness guidance for critical infrastructure", "Generator fuel order",
                 "Mutual aid roster", "Hurricane season preparedness webinar"] * 2
    elif 4 < d <= 40:
        pool += ["Restoration status", "Mutual aid crews", "Damage assessment photos", "Debris contractor schedule", "Boil water notice FAQ"] * 2
    s = pool[int(g.integers(len(pool)))]
    r = g.random()
    return ("RE: " if r < 0.22 else ("FW: " if r < 0.32 else "")) + s


@functools.lru_cache(maxsize=None)
def mail_rows():
    """The utility's mail gateway log: a sample of ordinary mail, plus every message behind a mail alert (complete)."""
    S = G.shared()
    g = rng("host_audit", "mail3")
    doms, dw = domains()
    email = {u["username"]: u["email"] for u in USERS}
    staff = [u["email"] for u in USERS]
    rows = []

    def outside(gg):
        r0 = gg.random()
        if r0 < 0.03:
            dom = f"{_DA[int(gg.integers(len(_DA)))]}-{_DB[int(gg.integers(len(_DB)))]}{int(gg.integers(2, 99))}.{_DT[int(gg.integers(len(_DT)))]}"
        elif r0 < 0.065:                                 # three-part names: a company and what it does
            dom = (f"{_DA[int(gg.integers(len(_DA)))]}-{_DB[int(gg.integers(len(_DB)))]}-"
                   f"{['support', 'services', 'group', 'supply', 'partners', 'billing', 'notices'][int(gg.integers(7))]}.{_DT[int(gg.integers(len(_DT)))]}")
        else:
            dom = doms[int(gg.choice(len(doms), p=dw))]
        k = gg.random()
        local = _LOCAL[int(gg.integers(len(_LOCAL)))] if k < 0.45 else f"{'abcdefghjklmnprstw'[int(gg.integers(18))]}{_SURN[int(gg.integers(len(_SURN)))]}"
        return f"{local}@{dom}", dom

    def mid(t, dom, key):
        k = hsh("mid", t, dom, key)
        return f"<{k}@{dom}>" if int(k[:2], 16) % 3 else f"<{k[:8]}.{int(k[8:12], 16)}@mail.{dom}>"

    def att(gg, exts, t):
        """An attachment name the way people and systems name files: many shapes, none special."""
        w, n, ext = _ATT_WORD[int(gg.integers(len(_ATT_WORD)))], int(gg.integers(100, 99999)), exts[int(gg.integers(len(exts)))]
        k, v, l = gg.random(), int(gg.integers(1, 9)), local_dt(t)
        noun = _ATT_NOUN[int(gg.integers(len(_ATT_NOUN)))].format(n=1 + n % 40, v=v)
        if k < 0.20:
            return f"{w}_{n}.{ext}"
        if k < 0.33:
            return f"{w.capitalize()} {n}.{ext}"
        if k < 0.43:
            return f"{['PO', 'INV', 'Q', 'WO', 'SO', 'RFQ'][n % 6]}-{2027 if n % 3 else ''}{'-' if n % 3 else ''}{n % 10000:04d}.{ext}"
        if k < 0.53:
            return [f"IMG_{n % 10000:04d}.jpg", f"Scan_{l:%Y%m%d}_{l:%H%M}.pdf", f"{l:%Y%m%d}_{l:%H%M%S}.jpg", f"scan{n % 1000:03d}.pdf"][n % 4]
        if k < 0.68:
            return f"{noun}.{ext}"
        if k < 0.76:
            return f"{noun.replace(' ', '_')}_{l:%Y-%m-%d}.{ext}"
        if k < 0.85:
            a_, b_ = _ATT_TOPIC[n % len(_ATT_TOPIC)], _ATT_TOPIC[(n // 7) % len(_ATT_TOPIC)]
            return f"{_ATT_AGENCY[(n // 3) % len(_ATT_AGENCY)]}-{a_}-{b_ if b_ != a_ else 'UPDATE'}-{l.year}.{ext}"
        if k < 0.92:
            return f"{['CBPWA ', 'FY28 ', 'FY2028 ', 'DRAFT '][n % 4]}{noun}{'' if n % 2 else f' v{v}'}.{ext}"
        return f"{noun.lower().replace(' ', '-')}-{l.year}.{ext}"

    for d in range(FIRST_D - 1, LAST_D + 1):
        t0 = D0_EPOCH + d * DAY
        hours = np.array([work_factor(t0 + h * 3600 + 1800) + 0.03 for h in range(24)])
        n = int(g.poisson(150 * (0.12 + hours.mean() * 1.9)))
        for hh in g.choice(24, n, p=hours / hours.sum()):
            t = t0 + int(hh) * 3600 + int(g.integers(0, 3600))
            if t >= SPAN_END:
                continue
            k = g.random()
            has_att = g.random() < 0.22
            a = att(g, _EXT, t) if has_att else ""
            size = int(g.gamma(2, 9000)) + 1800 + (int(g.gamma(2, 180000)) if has_att else 0)
            if k < 0.5:
                snd, dom = outside(g)
                spam = g.random() < 0.024
                rows.append([t, "inbound", snd, dom, staff[int(g.integers(len(staff)))], _subject(g, t), a, size, "spam" if spam else "clean", "quarantined" if spam else "delivered", mid(t, dom, 0)])
            elif k < 0.82:
                on = [x["user"] for x in S.sessions_at(t)]
                snd = email[on[int(g.integers(len(on)))]] if on else "noreply@cbpwa.example"
                rows.append([t, "internal", snd, "cbpwa.example", staff[int(g.integers(len(staff)))], _subject(g, t), a, size, "clean", "delivered", mid(t, "cbpwa.example", 1)])
            else:
                on = [x["user"] for x in S.sessions_at(t)]
                if not on:
                    continue
                rcp, _dom = outside(g)
                rows.append([t, "outbound", email[on[int(g.integers(len(on)))]], "cbpwa.example", rcp, _subject(g, t), a, size, "clean", "delivered", mid(t, "cbpwa.example", 2)])
    # the messages behind the mail alerts (every one of them)
    gq = rng("host_audit", "mail_alerts3")
    for _d, alerts in S.siem_by_day():
        for al in alerts:
            if al["rule_name"] not in ("MAIL_ATTACHMENT_QUARANTINED", "SPOOFED_SENDER_BLOCKED") or al["user"] not in email:
                continue
            t = al["t"] - int(gq.integers(1, 20))
            if al["rule_name"] == "MAIL_ATTACHMENT_QUARANTINED":
                snd, dom = outside(gq)
                rows.append([t, "inbound", snd, dom, email[al["user"]], _subject(gq, t), att(gq, _BLOCKED_EXT, t), int(gq.gamma(2, 90000)) + 4000, "blocked attachment type", "quarantined",
                             mid(t, dom, 3)])
            else:
                dom = str(gq.choice(["cbpwa.example", "cbpwa-example.com", "cbpwa.example.co", "mail-cbpwa.net", "cbpwa-payroll.com", "cbpwa.example.net"]))
                rows.append([t, "inbound", f"{USERS[int(gq.integers(len(USERS)))]['username']}@{dom}", dom, email[al["user"]], _SPOOF[int(gq.integers(len(_SPOOF)))], "",
                             int(gq.gamma(2, 6000)) + 1500, "sender failed authentication", "rejected", mid(t, dom, 4)])
    rows.append([LURE_T, "inbound", "preparedness@cbpwa-vendor-support.com", "cbpwa-vendor-support.com", WS04_USER["email"], "FEMA hurricane preparedness guidance for utilities",
                 "FEMA-PREP-GUIDANCE-2027.zip", 412877, "clean", "delivered", mid(LURE_T, "cbpwa-vendor-support.com", 0)])
    rows.sort(key=lambda r: r[0])
    seen = set()
    for r in rows:                                     # two messages never share an id
        if r[10] in seen:
            r[10] = f"<{hsh('mid2', r[0], r[4], r[10])}@{r[3]}>"
        seen.add(r[10])
    return rows


def gen_audit():
    S = G.shared()
    g = rng("host_audit", "v3")
    # ---- remote-access gateway sessions
    n1 = write_csv(f"{A}/remote_access_sessions.csv", ["session_id", "gateway", "account", "src_ip", "src_network", "src_country", "login_utc", "logout_utc", "duration_s", "bytes_out",
                                                       "bytes_in", "auth_method", "target_hosts", "change_ticket"],
                   [[r["id"], JMP, r["account"], r["src_ip"], r["src_network"], r["src_country"], z(r["login"]), z(r["logout"]), r["dur"], r["bytes_out"], r["bytes_in"], r["auth"],
                     ";".join(r["targets"]), r["ticket"]] for r in G.gateway_sessions()])
    # ---- historian access
    n2 = write_csv(f"{A}/historian_access.csv", ["session_id", "server", "account", "client_host", "start_utc", "end_utc", "duration_s", "tags_queried", "tag_groups", "query_type"],
                   [[h["id"], HIST1, h["account"], h["client"], z(h["t"]), z(h["t"] + h["dur"]), h["dur"], h["tags"], h["groups"], h["qtype"]] for h in G.historian_rows()])
    # ---- configuration changes on field devices
    n3 = write_csv(f"{A}/ot_config_changes.csv", ["time_utc", "device", "parameter", "old_value", "new_value", "change_type", "session_user", "source_host", "change_ticket"],
                   [[z(c["t"]), c["device"], c["parameter"], c["old"], c["new"], c["how"], c["account"], c["source"], c["ticket"]] for c in G.cfg_changes()])
    # ---- SCADA command log (operator actions)
    n4 = write_csv(f"{A}/scada_command_log.csv", ["time_utc", "scada_server", "workstation", "operator", "command", "device", "result", "origin", "console_session_id", "origin_host"],
                   [[z(c["t"]), SCADA1, c["ws"], c["operator"], c["command"], c["device"], "EXECUTED", c["origin"], c["console"], c["origin_host"]] for c in G.scada_cmds()])
    # ---- alarm suppression list
    sup = []
    for b in G.suppression_batches():
        n = b["n"] - b["delta"]
        for t, action, name, cat in b["rows"]:
            n += 1 if action == "ADD" else -1
            sup.append([z(t), b["system"], action, name, cat, b["by"], b["source"], b["ticket"], n])
    sup.sort(key=lambda r: r[0])
    n5 = write_csv(f"{A}/alarm_suppression_audit.csv", ["time_utc", "system", "action", "alarm_point", "category", "changed_by", "source_host", "change_ticket", "active_suppressions_after"], sup)
    # ---- file integrity on the OT file server
    n6 = write_csv(f"{A}/file_integrity.csv", ["time_utc", "host", "path", "event", "previous_hash", "new_hash", "user", "source_host", "diff_summary"],
                   [[z(f["t"]), G.OT01, f["path"], f["event"], f["prev"], f["new"], f["user"], f["source"], f["diff"]] for f in G.fim_rows()])
    # ---- change management and audits
    sec = lambda key: int(frac("chgsec", key) * 60)   # noqa: E731
    chg = [[z(FREEZE_ON + sec("fz")), "CHG-FREEZE-27-09", "Storm-preparation change freeze", "all OT configuration changes suspended until further notice", "OT Engineering manager", "ACTIVE"],
           [z(FREEZE_OFF + sec("th")), "CHG-THAW-27-10", "Change freeze lifted", "ordinary change approval resumes; emergency changes made during the freeze to be reconciled", "OT Engineering manager", "CLOSED"],
           [z(ts("2027-09-28T22:10Z") + sec("a")), "TXRC-2027-09-28-004", "ERCOT relay audit ticket", "possible relay config drift at Riverside Switching Station; investigating", "ERCOT compliance", "OPEN"],
           [z(ts("2027-09-28T22:25Z") + sec("b")), "QRY-CHG-27-311", "Change-system search", "relay threshold change, SUB-01, since commissioning date: 0 approved work orders found", "bflores", "CLOSED"],
           [z(ts("2027-09-30T18:20Z") + sec("c")), "QRY-CHG-27-318", "Change-system search", "configuration file change, SUB-04 RTU, 2027-09-11: 0 approved work orders found", "bflores", "CLOSED"],
           [z(ts("2027-10-02T15:10Z") + sec("d")), "SI-2027-CC-001", "Security incident", "opened by CISO after session-behaviour anomaly", "falrasheedobinna", "OPEN"]]
    for created, cid, sm, owner in G.change_records():            # the change system's own records: every ticket cited anywhere is one of these
        chg.append([z(created), cid, "Approved change", sm, owner, "CLOSED"])
    for c in G.cfg_changes():                                      # emergency tickets are raised by the duty supervisor shortly before the work
        if c["kind"] == "emergency":
            chg.append([z(c["t"] - 300 - int(frac("emr", c["ticket"]) * 2100)), c["ticket"], "Emergency change", "restoration: " + c["parameter"].split(" (")[0] + ", " + c["device"],
                        c["user"] or "", "CLOSED"])
    chg = [r for r in chg if z(G.SPAN_START - 20 * DAY) <= r[0]]
    chg.sort(key=lambda r: r[0])
    n7 = write_csv(f"{A}/change_management.csv", ["time_utc", "record_id", "record_type", "summary", "owner", "status"], chg)
    t_er = ts("2027-09-28T22:02Z")
    aud = [[z(t_er + 8 + 37 * k + int(frac("er", dev) * 20)), "ERCOT relay settings audit", dev, site, "27-UV pickup (pu)", "0.94" if k == 0 else "0.88", "0.88", "2027-08-15", "MISMATCH" if k == 0 else "MATCH"]
           for k, (dev, site) in enumerate((("GW-SYS-RTU-01", "Riverside Switching Station (SUB-01)"), ("GW-SYS-RTU-03", "SUB-03"), ("GW-SYS-RTU-05", "SUB-05")))]
    aud += [[z(M.T["rtu4_found"]), "internal configuration review", "GW-SYS-RTU-04", "SUB-04", "configuration file last_modified", f"{z(M.T['cfg_rtu4'])} by GW-ENG-VELA", "2027-08-15T16:02:11Z by GW-ENG-VELA", "2027-08-15", "MISMATCH"],
            [z(ts("2027-10-02T21:20Z") + sec("e1")), "evidence export", JMP, "remote-access gateway", "session log export SLE-2027-10-02", "", "", "", "EXPORTED"],
            [z(ts("2027-10-02T21:40Z") + sec("e2")), "evidence export", HIST1, "historian", "audit log export HAE-2027-10-02", "2027-09-07 to 2027-10-02", "", "", "EXPORTED"]]
    for q, (y, mth, dd) in enumerate(((2027, 8, 3), (2027, 11, 9))):            # routine quarterly review of field-device files
        for k, dev in enumerate(G.SUB_RTU + G.WATER_RTU):
            tq = ts(f"{y}-{mth:02d}-{dd:02d}T15:00Z") + 600 * k + int(frac("qr", q, dev) * 500)
            last = max([c["t"] for c in G.cfg_changes() if c["device"] == dev and c["t"] < tq and c["how"] != "local panel"] or [ts("2027-06-01T14:00Z") + 3600 * k])
            aud.append([z(tq), "internal configuration review", dev, dev.replace("GW-SYS-RTU-", "RTU "), "configuration file last_modified", z(last), z(last), z(last)[:10], "MATCH"])
    aud.sort(key=lambda r: r[0])
    n8 = write_csv(f"{A}/settings_audits.csv", ["time_utc", "audit", "device", "site", "item", "found", "record_value", "record_date", "result"], aud)
    # ---- endpoint protection
    av = []
    for d in range(FIRST_D - 1, LAST_D + 1):
        for _ in range(int(g.poisson(40) * (0.3 if 0 <= d <= 4 else 1))):
            h = WORKST[g.integers(len(WORKST))]
            a = D0_EPOCH + d * DAY + int(g.integers(0, DAY))
            ev, det = [("DEFINITIONS_UPDATED", f"engine 4.18.{2400 + d // 7}"), ("SCAN_COMPLETED", "0 threats"), ("REALTIME_PROTECTION_ENABLED", "policy refresh"),
                       ("THREAT_QUARANTINED", str(g.choice(["PUA:Win32/Toolbar", "PUA:Win32/BundleInstaller", "PUA:Win32/CouponHelper", "Adware:Win32/SearchTab", "PUA:Win32/DriverUpdater"]))),
                       ("AGENT_HEARTBEAT_MISSED", "")][int(g.choice(5, p=[0.45, 0.33, 0.1, 0.04, 0.08]))]
            if h["hostname"] == WS04 and a >= WS04_REMOVED:
                continue
            av.append([z(a), h["hostname"], h["ip"], ev, det, "system"])
    ga = rng("host_audit", "av_toggle3")
    for i in range(60):
        a = local_ts(int(ga.integers(-58, 118)), f"{int(ga.integers(7, 18)):02d}:{int(ga.integers(0, 60)):02d}") + int(ga.integers(0, 60))
        on = [x for x in S.sessions_at(a) if x["host"] in G.CORP_NAMES and x["host"] != WS04]
        k, r2, back, how = int(ga.integers(1 << 30)), ga.random(), int(ga.integers(240, 5400)), str(ga.choice(["setting changed locally", "disabled by management task", "setting changed locally"]))
        if not on:
            continue
        x = on[k % len(on)]
        who = x["user"] if how == "setting changed locally" else str(["svc_ecm", "svc_edr"][k % 2])
        av.append([z(a), x["host"], IP[x["host"]], "REALTIME_PROTECTION_DISABLED", how, who])
        if r2 < 0.8:
            av.append([z(a + back), x["host"], IP[x["host"]], "REALTIME_PROTECTION_ENABLED", "policy refresh" if r2 < 0.5 else "setting changed locally", "system"])
    av.append([z(AV_OFF_T), WS04, IP[WS04], "REALTIME_PROTECTION_DISABLED", "setting changed locally", WS04_USER["username"]])
    av.sort(key=lambda r: r[0])
    av = [r for r in av if r[0] >= z(G.SPAN_START)]
    n9 = write_csv(f"{A}/endpoint_protection.csv", ["time_utc", "host", "ip", "event", "detail", "initiated_by"], av)
    # ---- mail gateway
    n10 = write_csv(f"{A}/mail_gateway_cbpwa.csv", MAIL_COLS, [[z(r[0]), "GW-GW-MAIL-01"] + r[1:] for r in mail_rows() if r[0] >= G.SPAN_START])
    # employee VPN concentrator: one row per session (who, from where, on which device, which pool address)
    write_csv(f"{A}/employee_vpn_sessions.csv", ["session_id", "gateway", "account", "src_ip", "src_network", "device", "assigned_ip", "login_utc", "logout_utc", "duration_s", "bytes_in",
                                                 "bytes_out", "auth_method"],
              [[v["id"], "GW-VPN-EMP-01", v["user"], v["src_ip"], v["src_network"], v["device"], v["pool_ip"], z(int(v["t"]) + 1), z(int(v["t"] + v["dur"])), int(v["dur"]), v["bytes_in"], v["bytes_out"],
                "token"] for v in G.vpn_sessions()])
    print(f"host_audit_logs: sessions {n1:,}, historian {n2:,}, config {n3}, commands {n4:,}, suppression {n5}, files {n6}, change {n7}, audits {n8}, endpoint {n9:,}, mail {n10:,}")
