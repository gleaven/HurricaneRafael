"""Stream descriptions and probes for the IT logs of the other organisations (see scripts/check_streams.py).
Every probe reads the files on disk. Run alone to see every probe:  python3 scripts/streams/probes_partner_it.py
"""
import bisect
import collections
import csv
import glob
import ipaddress
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import partner_it_model as P
from common import D0_EPOCH, ROOT, local_dt, local_ts, ts

DAY = 86400
BASE = os.path.join(ROOT, P.OUT)
KINDS = ["firewall", "web", "dns", "auth", "mail", "endpoint_alerts"]
STREAM_OF = {"firewall": "partner_firewall_logs", "web": "partner_web_logs", "dns": "partner_dns_logs", "auth": "partner_auth_logs", "mail": "partner_mail_logs",
             "endpoint_alerts": "partner_endpoint_alerts"}
MAIL_KEY = ("time_utc", "gateway", "direction", "sender", "sender_domain", "recipient", "subject", "attachment_names", "size_bytes", "verdict", "action", "message_id")
_c = {}


def rows(org, kind):
    key = (org, kind)
    if key not in _c:
        out = []
        for fp in sorted(glob.glob(os.path.join(BASE, org.lower(), f"{kind}_*.csv"))):
            with open(fp, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    r["t"] = ts(r["time_utc"])
                    out.append(r)
        _c[key] = out
    return _c[key]


def audit(name):
    return P.read_csv(f"network_logs/audit/{name}.csv")


def reg():
    return P.registry()


def rule(org, k):
    return P.ORGS[org]["rules"][k]


def site_of(org):
    return {h["ip"]: h["site_id"] for h in reg()[org]["hosts"]}, {h["host_id"]: h["site_id"] for h in reg()[org]["hosts"]}


def fw_start(r):
    return r["t"] - float(r["duration_s"]) if P.FW_TIME_AT_END else r["t"]


def clicks(org):
    """[(epoch, mailbox, client ip, url host)] from the link-click tables in network_logs/audit."""
    if org == "BRW":
        return [(ts(r["time_utc"]), r["mailbox"], r["client_ip"], r["url_host"]) for r in audit("mail_url_clicks_brightwake")]
    return [(ts(r["time_utc"]), r["mailbox"], r["client_ip"], r["url_host"]) for r in audit("mail_url_clicks_city_airstation") if r["gateway"].startswith("CITY") == (org == "CITY")]


# ---- the six extract tables are rows of these logs, unchanged ------------------------------------------------
def mail_extract(org, src):
    def f():
        a, b = P.EXTRACT_WIN[org]
        want = [tuple(r[c] for c in MAIL_KEY) for r in rows(org, "mail") if a <= r["t"] < b]
        have = [tuple(r[c] for c in MAIL_KEY) for r in audit(src)]
        spam = sum(1 for x in have if x[9] != "clean")
        out = sum(1 for x in have if x[2] == "outbound")
        return want == have and len(have) > 0 and spam > 0 and out > 0, f"{src}.csv: {len(have):,} rows, identical to the rows of {org.lower()}/mail_*.csv in its window ({spam} not clean, {out} outbound)"
    return f


def logon_extract(org, service):
    def f():
        a, b = P.EXTRACT_WIN[org]
        host = P.ORGS[org]["remote"][0]
        want = [(r["time_utc"], r["account"], r["src_ip"], r["src_network"], r["result"], r["auth_method"], r["device"]) for r in rows(org, "auth") if r["host"] == host and a <= r["t"] < b]
        have = [(r["time_utc"], r["account"], r["src_ip"], r["src_network"], r["result"], r["auth_method"], r["device"]) for r in audit("account_logons_city_airstation") if r["service"] == service]
        return sorted(want) == sorted(have) and len(have) > 0, f"{len(have):,} '{service}' rows of account_logons_city_airstation.csv are identical to the remote sign-ons of {org.lower()}/auth_*.csv in the window"
    return f


def clicks_contained(org):
    """The link-click reports hold every followed link of their window. The clicks on the two messages canon fixes come
    from a mailbox that had received the message, at that person's registered workstation, with DNS query, web request
    and firewall session; every other click made inside the network has the same three records, and clicks made from a
    phone or from home (an outside address) have none, as they never crossed this network."""
    def f():
        web, dns, fw = rows(org, "web"), rows(org, "dns"), rows(org, "firewall")
        by_ip = {h["ip"]: h for h in reg()[org]["hosts"]}
        inside_net = P.base(org) + "."
        mail = collections.defaultdict(list)
        for m in rows(org, "mail"):
            if m["action"] == "delivered":
                mail[m["recipient"]].append(m)
        webk = collections.defaultdict(list)
        for r in web:
            webk[(r["client_ip"], r["host"])].append(r)
        dnsk = collections.defaultdict(list)
        for r in dns:
            dnsk[(r["client_ip"], r["query"])].append(r["t"])
        fwk = collections.defaultdict(list)
        for r in fw:
            fwk[r["src_ip"]].append(r)
        n = canon = inside = 0
        why = []
        for t, mb, ip, host in clicks(org):
            n += 1
            lure = host in (P.LURE_HOST, P.BRW_LURE_HOST)
            if lure:
                canon += 1
                if not [m for m in mail[mb] if m["sender_domain"] in (P.LURE_DOM, P.BRW_LURE_DOM) and m["t"] < t]:
                    why.append(f"{mb} clicked without having received the message")
                h = by_ip.get(ip)
                if org != "BRW" and (not h or mb.split("@")[0] not in h.get("users", [])):
                    why.append(f"{ip} is not the registered workstation of {mb}")
            elif not [m for m in mail[mb] if 0 < t - m["t"] <= 8 * 86400]:
                why.append(f"{mb} followed a link without a delivered message in the week before")
            if not (ip.startswith(inside_net) or ip.startswith("10.")):
                if lure:
                    why.append(f"{mb}: the click on the canon message is not from inside")
                continue                                                  # followed from a phone or from home
            inside += 1
            user = P.BRW_CLICK_PERSON if (org == "BRW" and lure) else mb.split("@")[0]
            w = [r for r in webk[(ip, host)] if abs(r["t"] - t) <= 1 and r["user"] == user]
            good = bool(w) and any(0 <= t - x <= (5 if lure else 305) for x in dnsk[(ip, host)]) and any(abs(fw_start(r) - t) <= 2 for r in fwk[ip])      # a name asked for in the last five minutes is not asked again
            if org == "BRW" and lure:
                good = good and any(r["nat_src_ip"] in P.BRW_OFFICE_POOL and abs(fw_start(r) - t) <= 2 and r["rule_name"] == rule(org, "web") for r in fwk[ip])
            if not good:
                why.append(f"{mb} {host}: no DNS query, web request or firewall session")
        want_canon = P.CLICK_N.get(org, 1)
        ok = not why and canon == want_canon and n - canon >= 5 * canon
        return ok, (f"{n} followed links in the report: {canon} on the canon message (received first, from the person's registered workstation), "
                    f"{inside - canon} other ones from inside, each with DNS query, web request and firewall session; {n - inside} from phones or homes" + (f"; {why[:3]}" if why else ""))
    return f


def story_signons():
    """Each click is followed, half an hour to nine hours later, by a sign-on with that account from a network the account never used before."""
    bad, n = [], 0
    for org in ("CITY", "NASCC"):
        host = P.ORGS[org]["remote"][0]
        by = collections.defaultdict(list)
        for r in rows(org, "auth"):
            if r["host"] == host:
                by[r["account"]].append(r)
        for t, mb, ip, url in clicks(org):
            if url != P.LURE_HOST:
                continue                                                  # the report also holds ordinary followed links
            n += 1
            later = [r for r in by[mb] if 1800 <= r["t"] - t <= 9 * 3600 and r["result"] == "SUCCESS" and r["auth_method"] == "password" and r["device"] == "new device"]
            fresh = [r for r in later if not any(x["src_network"] == r["src_network"] and x["t"] < r["t"] for x in by[mb])]
            if not fresh:
                bad.append(mb)
    return not bad and n == 10, f"{n} clicks, {n - len(bad)} followed within nine hours by a password-only sign-on on a new device from a network new to that account"


def remote_inbound():
    miss = n = 0
    for org in P.ORG_IDS:
        host, vip = P.ORGS[org]["remote"][0], P.ORGS[org]["remote"][1]
        inb = collections.defaultdict(list)
        for r in rows(org, "firewall"):
            if r["dst_ip"] == vip:
                inb[r["src_ip"]].append(fw_start(r))
        for v in inb.values():
            v.sort()
        for r in rows(org, "auth"):
            if r["host"] == host and r["t"] < P.SPAN_B - 4 * 3600:      # a session still open when the log ends has no session-end record yet
                n += 1
                v = inb.get(r["src_ip"], [])
                i = bisect.bisect_left(v, r["t"] - 3)
                miss += not (i < len(v) and v[i] <= r["t"] + 3)
    return miss == 0 and n > 0, f"{n:,} remote sign-ons in seven organisations: {n - miss:,} have their inbound connection at the edge firewall"


def brw_sessions():
    fw, auth, web = rows("BRW", "firewall"), rows("BRW", "auth"), rows("BRW", "web")
    dmz = [r for r in fw if r["device"] == "BRW-FW-DMZ-01"]
    edge = [r for r in fw if r["rule_name"] == rule("BRW", "web") and r["dst_ip"] == P.BRW_GATEWAY[1]]
    vpn = [r for r in auth if r["event_id"] == "vpn-login"]
    bad = []
    counts = {"office": 0, "vpn": 0, "other": 0}
    for s in P.brw_sessions():
        t = ts(s["login_utc"])
        kind = "office" if s["src_ip"] in P.BRW_OFFICE_POOL else ("vpn" if s["src_ip"] in P.BRW_VPN_POOL else "other")
        counts[kind] += 1
        person = P.BRW_ENG[s["vendor_account"]]
        if not any(r["src_ip"] == s["src_ip"] and abs(fw_start(r) - t) <= 3 for r in dmz):
            bad.append((s["session_id"], "no record at the gateway firewall"))
        out = [r for r in edge if r["nat_src_ip"] == s["src_ip"] and abs(fw_start(r) - t) <= 5]
        if kind == "office" and not (out and any(r["user"] == person and abs(r["t"] - t) <= 5 and r["host"] == P.BRW_GATEWAY[0] and r["scheme"] == "https" for r in web)):
            bad.append((s["session_id"], "office session without its outbound connection"))
        if kind == "vpn" and not (out and any(r["account"] == person and 0 < t - r["t"] <= 2400 for r in vpn)):
            bad.append((s["session_id"], "VPN session without a VPN sign-on before it"))
        if kind == "other":
            if out or any(abs(r["t"] - t) <= 600 and r["host"] == P.BRW_GATEWAY[0] and r["user"] == person for r in web) or any(r["account"] == person and 0 < t - r["t"] <= 7200 for r in vpn):
                bad.append((s["session_id"], "session from outside matches activity inside the vendor's network"))
    return not bad, f"{sum(counts.values())} remote-maintenance sessions of the vessel log: {counts['office']} from the office and {counts['vpn']} over the staff VPN have matching " \
                    f"vendor-side records; {counts['other']} from the third network appear only at the gateway firewall" + (f"; problems {bad[:3]}" if bad else "")


def nas_portal():
    want = miss = 0
    fw = {}
    for r in rows("NASCC", "firewall"):
        if r["dst_ip"] == P.NAS_PORTAL_VIP:
            fw.setdefault(r["src_ip"], []).append((fw_start(r), int(r["bytes_recv"])))
    known = set()
    for fp in sorted(glob.glob(os.path.join(P.SRC, "network_logs/portal/base_logistics_access_*.csv"))):
        for r in csv.DictReader(open(fp, newline="", encoding="utf-8")):
            if r["client_network"] != "base network":
                want += 1
                known.add(r["client_ip"])
                miss += not any(abs(x - ts(r["time_utc"])) <= 2 for x, _ in fw.get(r["client_ip"], []))
    extra = sum(1 for ip, v in fw.items() if ip not in known for _, b in v if b > 3000)
    return want > 0 and miss == 0 and extra == 0, f"{want - miss} of {want} outside requests in the base logistics log have an inbound firewall session; {extra} other sessions to that address carry more than a handshake"


def no_aid_portal():
    n = sum(1 for org in P.ORG_IDS for r in rows(org, "web") if "disasteraid" in r["host"]) + sum(1 for org in P.ORG_IDS for r in rows(org, "firewall") if r["dst_ip"] == "192.0.2.130")
    return n == 0, f"{n} requests from the seven organisations to the aid portal (its own access log is complete and shows none)"


# ---- canon-timed behaviour --------------------------------------------------------------------------------
def alerts(org):
    def f():
        web, auth = rows(org, "web"), rows(org, "auth")
        ip_of = {h["host_id"]: h["ip"] for h in reg()[org]["hosts"]}
        bad, n = [], 0
        for t, host, aid, kind in P.alert_issues(org):
            n += 1
            w = [r for r in web if r["host"] == P.ALERT_HOST and r["client_ip"] == ip_of[host] and 0 <= t - r["t"] <= 30]
            last = {}
            for r in auth:                                   # rows are in time order; the last logon/logoff of each account before the issue time
                if r["host"] == host and r["logon_type"] == "2" and r["event_id"] in ("4624", "4634") and r["t"] <= t:
                    last[r["account"]] = r["event_id"]
            on = [a for a, e in last.items() if e == "4624"]
            if not w or w[-1]["user"] not in on:
                bad.append((aid, kind))
        other = sum(1 for r in web if r["host"] == P.ALERT_HOST) - n
        return not bad and n > 0 and other > 10, f"{n} alert transmissions ({org.lower()}): each has a logged-on alerting workstation and a request to the origination service within 30 s before the issue time; " \
                                                  f"{other} other sign-ins to the service (routine checks)" + (f"; missing {bad}" if bad else "")
    return f


def outages_quiet(org):
    def f():
        by_ip, by_host = site_of(org)
        bad = 0
        wins = P.outages(org)
        n = sum(len(v) for v in wins.values())
        for kind, col, m in (("web", "client_ip", by_ip), ("dns", "client_ip", by_ip), ("endpoint_alerts", "host", by_host), ("auth", "host", by_host)):
            for r in rows(org, kind):
                site = m.get(r[col])
                if kind == "auth" and r["event_id"] != "4624":
                    continue
                for a, b in wins.get(site, []):
                    if a + 60 < r["t"] < b:
                        bad += 1
        return bad == 0 and n > 0, f"{n} power-loss windows ({', '.join(sorted(wins))}): no logon, web, DNS or endpoint record from a site while it has no power" + (f"; {bad} violations" if bad else "")
    return f


def port_gate():
    by_ip, by_host = site_of("PORT")
    per = {}
    for r in rows("PORT", "web"):
        if by_ip.get(r["client_ip"]) == "GATE" and r["user"] != "-":
            d = P.lday(r["t"])
            per[d] = per.get(d, 0) + 1
    before = sum(per.get(d, 0) for d in range(-45, -3)) / 42
    storm = sum(per.get(d, 0) for d in range(0, 4))
    closed = sum(per.get(d, 0) for d in range(4, 30)) / 26
    after = sum(per.get(d, 0) for d in range(60, 100)) / 40
    zulu = P.zulu_time()
    gate = [r for r in rows("PORT", "auth") if by_host.get(r["host"]) == "GATE" and r["event_id"] in ("4624", "4634")]
    on_day = sum(1 for r in gate if r["event_id"] == "4624" and local_ts(-1, "00:00") <= r["t"] < zulu)
    late = sum(1 for r in gate if r["event_id"] == "4624" and zulu + 4500 < r["t"] < local_ts(4, "00:00"))
    last_off = max((r["t"] for r in gate if r["event_id"] == "4634" and r["t"] < local_ts(1, "00:00")), default=0)
    ok = storm == 0 and closed < 0.5 * before and after > 0.7 * before and on_day > 0 and late == 0 and 0 < last_off - zulu < 4500
    return ok, f"gate offices: {before:.1f} user web requests a day before the storm; {on_day} logons on the morning Port Condition Zulu was set, last logoff {(last_off - zulu) / 60:.0f} min after it; " \
               f"{storm} requests from landfall to D+3, {closed:.1f} a day while the channel is closed (D+4 to D+29), {after:.1f} after reopening"


def hospital_load(org):
    def f():
        per = {}
        for r in rows(org, "auth"):
            if r["logon_type"] == "7":
                d = P.lday(r["t"])
                per[d] = per.get(d, 0) + 1
        base = sum(per.get(d, 0) for d in range(-40, -5)) / 35
        lost, gen, back = P.hospital_power(P.ORGS[org]["facility"])
        peak_d = max(range(0, 30), key=lambda d: P.ed_factor(org, d))
        peak = sum(per.get(d, 0) for d in range(peak_d - 1, peak_d + 2)) / 3
        return peak > 1.15 * base, f"clinical workstation unlocks: {base:.0f} a day before the storm, {peak:.0f} a day around the busiest emergency-department day (D+{peak_d}); power lost {P.iso(lost)}, generator {P.iso(gen)}"
    return f


def translations():
    mail = rows("COUNTY", "mail")
    jobs = [r for r in P.read_csv("broadcast/translation_jobs.csv") if r["translator"] == "NCLAS"]
    bad = []
    for j in jobs:
        if not any(m["direction"] == "outbound" and j["job_id"] in m["subject"] and 0 <= ts(j["source_received_utc"]) - m["t"] <= 120 for m in mail):
            bad.append(j["job_id"])
        if j["translation_delivered_utc"] and not any(m["direction"] == "inbound" and j["job_id"] in m["subject"] and 0 <= m["t"] - ts(j["translation_delivered_utc"]) <= 60 for m in mail):
            bad.append(j["job_id"])
    return not bad and jobs, f"{len(jobs)} translation jobs: request and delivery messages at the logged times" + (f"; missing {bad}" if bad else "")


def notices():
    mail = rows("PORT", "mail")
    seen, miss, own = set(), [], 0
    for r in P.read_csv("supply/port_conditions.csv"):
        k = (r["order_id"], r["issued_utc"])
        if not r["issued_utc"] or k in seen:
            continue
        seen.add(k)
        mine = r["authority"].startswith("Port of Corpus Christi")
        own += mine
        m = [x for x in mail if x["subject"].startswith(k[0] + ":") and 0 <= x["t"] - ts(k[1]) <= 600]
        if not m or (mine and m[0]["sender"] != "port.operations@portofcc.example") or (not mine and m[0]["sender_domain"] != "uscg-sector-cc.example"):
            miss.append(k[0])
    return not miss and len(seen) > 0, f"{len(seen) - len(miss)} of {len(seen)} port orders are in the port's mail log within ten minutes of issue ({len(seen) - own} from the Coast Guard sender, {own} sent by the port itself)"


def nas_staffing():
    by_ip, by_host = site_of("NASCC")
    per = {}
    for r in rows("NASCC", "auth"):
        if r["event_id"] == "4624" and r["logon_type"] == "2" and by_host.get(r["host"]) == "ADM":
            d = P.lday(r["t"])
            per[d] = per.get(d, 0) + 1
    wk = [d for d in range(-40, -5) if (d + 1) % 7 not in (4, 5)]                    # D0 is a Tuesday
    base = sum(per.get(d, 0) for d in wk) / len(wk)
    storm = sum(per.get(d, 0) for d in range(0, 6)) / 6
    (a, b), (fa, fb) = P.nas_power()
    quiet = not any(fa + 60 < r["t"] < fb for k in ("web", "dns", "firewall") for r in rows("NASCC", k))
    return storm < 0.3 * base and quiet, f"administration building logons: {base:.1f} a weekday before the evacuation, {storm:.1f} a day from landfall to D+5; no web, DNS or firewall record during the power interruption {P.iso(fa)} to {P.iso(fb)}"


def remote_calendar():
    """Remote sign-ons follow the week, the holidays and the storm."""
    out, ok = [], True
    for org in P.ORG_IDS:
        host = P.ORGS[org]["remote"][0]
        per = collections.Counter(P.lday(r["t"]) for r in rows(org, "auth") if r["host"] == host)
        days = [d for d in range(-55, 115) if not -6 <= d <= 16]
        wk = [per[d] for d in days if local_dt(local_ts(d, "12:00")).weekday() < 5 and P.holiday_factor(org, d) == 1]
        we = [per[d] for d in days if local_dt(local_ts(d, "12:00")).weekday() >= 5]
        w, e = sum(wk) / len(wk), sum(we) / len(we)
        xmas = per[P.lday(ts("2027-12-25T18:00Z"))]
        thx = per[P.lday(ts("2027-11-25T18:00Z"))]
        health = P.ORGS[org]["sector"][0] == "health"
        good = e < (0.9 if health else 0.7) * w and (health or (xmas < 0.6 * w and thx < 0.6 * w)) and (org not in P.STORM_AFFECTED or per[0] < 0.55 * w)
        ok &= good
        out.append(f"{org.lower()} {w:.0f}/{e:.0f}/{per[0]}/{thx}/{xmas}")
    return ok, "remote sign-ons per ordinary weekday / weekend day / landfall day / Thanksgiving / Christmas Day: " + ", ".join(out)


# ---- invariants -------------------------------------------------------------------------------------------
import netmap
HOSTILE = set(netmap.STORY_SET)                                       # addresses other delivered streams tie to the outside network
CAT_COLS = {"auth": ["event_id", "logon_type", "src_network", "result", "auth_method", "device"],
            "firewall": ["device", "action", "rule_name", "src_zone", "dst_zone", "proto", "app", "session_end_reason", "dst_port"],
            "web": ["method", "scheme", "status", "action", "category", "user_agent_family", "policy"], "dns": ["qtype", "rcode", "resolver"],
            "mail": ["gateway", "direction", "verdict", "action"]}


def _is_story(kind, r):
    if kind in ("auth", "firewall"):
        return r["src_ip"] in HOSTILE or (kind == "firewall" and r["dst_ip"] in LURE_IPS)
    if kind == "web":
        return r["host"] in (P.LURE_HOST, P.BRW_LURE_HOST)
    if kind == "dns":
        return r["query"] in (P.LURE_HOST, P.BRW_LURE_HOST)
    if kind == "mail":
        return r["sender_domain"] in (P.LURE_DOM, P.BRW_LURE_DOM)
    return False


LURE_IPS = set(P.site_ips(P.LURE_HOST)) | set(P.site_ips(P.BRW_LURE_HOST))


def no_exclusive_values():
    """For every categorical column, the values whose every occurrence lies on a record of one of the hidden stories.
    There must be none: such a record must look like its neighbours and be found by analysis, not by counting values."""
    bad, n_story = [], 0
    for org in P.ORG_IDS:
        for kind, cols in CAT_COLS.items():
            story, other = collections.defaultdict(set), collections.defaultdict(set)
            for r in rows(org, kind):
                s = _is_story(kind, r)
                n_story += s
                for c in cols:
                    (story if s else other)[c].add(r[c])
            for c in cols:
                for v in story[c] - other[c]:
                    bad.append((org.lower(), kind, c, v))
    # the address range and the network label of the outside network are also used by ordinary clients
    pre = {}
    for org in ("CITY", "NASCC", "BRW"):
        ordinary = sum(1 for k in ("auth", "firewall") for r in rows(org, k) if r["src_ip"].startswith("203.0.113.") and r["src_ip"] not in HOSTILE)
        pre[org.lower()] = ordinary
        if ordinary < 20:
            bad.append((org.lower(), "src_ip", "203.0.113.", "only on story rows"))
    for name in ("account_logons_city_airstation",):
        lab = [r for r in audit(name) if r["src_network"] == "ASN 64512"]
        if not any(r["src_ip"] not in HOSTILE for r in lab):
            bad.append((name, "src_network", "ASN 64512", "only on story rows"))
    return not bad and n_story > 0, f"{n_story:,} story records in five log types of seven organisations: {len(bad)} categorical values occur on them alone; ordinary records from 203.0.113.x: {pre}" + (f"; {bad[:6]}" if bad else "")


def mail_like_mail():
    out, ok = [], True
    reg_boxes = {org: set(P.mailboxes(org)) for org in P.ORG_IDS}
    for org in P.ORG_IDS:
        m = rows(org, "mail")
        dom = P.ORGS[org]["domain"]
        ext = [r for r in m if r["direction"] == "inbound"]
        doms = collections.Counter(r["sender_domain"] for r in ext)
        once = sum(1 for v in doms.values() if v == 1)
        snd = collections.Counter(r["sender"] for r in ext)
        repeat = sum(1 for v in snd.values() if v >= 5)
        internal = [r for r in m if r["direction"] == "internal"]
        unknown = sum(1 for r in internal if r["sender"] not in reg_boxes[org]) + sum(1 for r in m if r["direction"] != "outbound" and r["recipient"] not in reg_boxes[org])
        outb = sum(1 for r in m if r["direction"] == "outbound")
        ids = sum(1 for r in m if not r["message_id"].startswith("<") or "@" not in r["message_id"])
        subj = len({r["subject"] for r in m})
        bursts = 0                                             # other sender domains that deliver a hundred messages within four days
        by_dom = collections.defaultdict(list)
        for r in m:
            if r["sender_domain"] not in (P.LURE_DOM, dom):
                by_dom[r["sender_domain"]].append(r["t"])
        for v in by_dom.values():
            v.sort()
            bursts += any(v[i + 99] - v[i] <= 4 * DAY for i in range(len(v) - 99))
        storm_early = sum(1 for r in m if "Rafael" in r["subject"] and r["t"] < ts("2027-09-08T00:00Z"))
        good = len(doms) >= 120 and once >= 20 and repeat >= 40 and unknown == 0 and outb > 300 and ids == 0 and subj > 1500 and storm_early == 0 and (org not in P.WAVE_N or bursts >= 1)
        ok &= good
        out.append(f"{org.lower()}: {len(doms)} sender domains ({once} seen once), {repeat} senders with five or more messages, {outb:,} outbound, {subj:,} subjects, {bursts} other bulk mailings")
    return ok, "; ".join(out) + "; internal senders and all recipients are registry mailboxes"


def registered(kind):
    def f():
        bad, n = {}, 0
        for org in P.ORG_IDS:
            o = reg()[org]
            ips = {h["ip"] for h in o["hosts"]}
            hosts = {h["host_id"] for h in o["hosts"]}
            accts = {a["account"] for a in o["accounts"]} | {a["mailbox"] for a in o["accounts"] if a.get("mailbox")} | {"-"}
            base = P.base(org) + "."
            pool = (base + "250.",) + (("10.200.",) if org == "NASCC" else ())
            for r in rows(org, kind):
                n += 1
                if kind in ("web", "dns"):
                    if r["client_ip"] not in ips and not r["client_ip"].startswith(pool):
                        bad[r["client_ip"]] = org
                    if kind == "web" and r["user"] not in accts:
                        bad[r["user"]] = org
                    if kind == "dns" and r["resolver"] not in ips:
                        bad[r["resolver"]] = org
                elif kind == "firewall":
                    if r["device"] not in hosts:
                        bad[r["device"]] = org
                    if r["src_ip"].startswith(base) and r["src_ip"] not in ips and not r["src_ip"].startswith(pool):
                        bad[r["src_ip"]] = org
                elif kind == "auth":
                    if r["host"] not in hosts or r["account"] not in accts:
                        bad[(r["host"], r["account"])] = org
                elif kind == "endpoint_alerts":
                    if r["host"] not in hosts or (r["initiated_by"] != "system" and r["initiated_by"] not in accts):
                        bad[(r["host"], r["initiated_by"])] = org
                elif kind == "mail":
                    if r["gateway"] not in hosts:
                        bad[r["gateway"]] = org
        return not bad and n > 0, f"{n:,} {kind} rows: every host, internal address and account is in partner_it_registry.json" + (f"; unknown {list(bad.items())[:5]}" if bad else "")
    return f


def registry_layout():
    bad, n = [], 0
    blocks = []
    for org in P.ORG_IDS:
        o = reg()[org]
        sub = {s["site_id"]: ipaddress.ip_network(s["subnet"]) for s in o["sites"]}
        seen = {}
        for h in o["hosts"]:
            n += 1
            if ipaddress.ip_address(h["ip"]) not in sub[h["site_id"]]:
                bad.append((h["host_id"], "outside its site's subnet"))
            if h["ip"] in seen:
                bad.append((h["host_id"], "address also given to " + seen[h["ip"]]))
            seen[h["ip"]] = h["host_id"]
        if "198.51.100.44" in str(o["address_plan"]) or any(ipaddress.ip_address("198.51.100.44") in v for v in sub.values()):
            bad.append((org, "an address another stream uses lies in the plan"))
        blocks.append(ipaddress.ip_network(o["address_plan"]["internal"]))
    overlap = sum(1 for i in range(len(blocks)) for j in range(i) if blocks[i].overlaps(blocks[j]))
    return not bad and not overlap, f"{n} registry hosts: each inside its site's subnet, no address given twice, no overlap between organisations" + (f"; {bad[:4]}" if bad else "")


def dns_before_web():
    miss = n = 0
    for org in P.ORG_IDS:
        q = {}
        for r in rows(org, "dns"):
            q.setdefault((r["client_ip"], r["query"]), []).append(r["t"])
        for r in rows(org, "web"):
            n += 1
            lst = q.get((r["client_ip"], r["host"]), [])
            i = bisect.bisect_right(lst, r["t"])
            if not (i and r["t"] - lst[i - 1] <= 301):
                miss += 1
    return miss == 0 and n > 0, f"{n:,} web requests: each follows a DNS query for the same name from the same client within five minutes ({miss} without)"


def web_fw():
    """Every allowed web request has one outbound firewall session, to the address the client's DNS query returned."""
    bad, n, wrong = [], 0, 0
    for org in P.ORG_IDS:
        ans = collections.defaultdict(list)
        for r in rows(org, "dns"):
            if r["qtype"] == "A":
                ans[(r["client_ip"], r["query"])].append((r["t"], r["answer"]))
        fw = collections.defaultdict(list)
        nfw = 0
        for r in rows(org, "firewall"):
            if r["rule_name"] == rule(org, "web"):
                nfw += 1
                fw[r["src_ip"]].append((fw_start(r), r["dst_ip"]))
        for v in fw.values():
            v.sort()
        allowed = 0
        for r in rows(org, "web"):
            if r["action"] != "allowed":
                continue
            allowed += 1
            a = ans[(r["client_ip"], r["host"])]
            i = bisect.bisect_right(a, (r["t"] + 1, "~")) - 1
            v = fw[r["client_ip"]]
            j = bisect.bisect_left(v, (r["t"] - 1.5, ""))
            if not (i >= 0 and any(v[k][1] == a[i][1] for k in range(j, min(len(v), j + 6)) if v[k][0] <= r["t"] + 1.5)):
                wrong += 1
        n += allowed
        if allowed != nfw:
            bad.append((org, allowed, nfw))
    return not bad and wrong == 0, f"{n:,} allowed web requests: each has one outbound firewall session, {n - wrong:,} of them to the address the client's own DNS query returned" + (f"; count mismatches {bad}" if bad else "")


def different_networks():
    """The seven organisations do not share one profile."""
    edge, fin, deny, threats = [], [], [], set()
    for org in P.ORG_IDS:
        w = [r["user_agent_family"] for r in rows(org, "web") if r["user_agent_family"] != "-"]
        edge.append(sum(1 for x in w if x.startswith("Edge")) / len(w))
        f = [r["session_end_reason"] for r in rows(org, "firewall") if r["rule_name"] == rule(org, "web")]
        fin.append(sum(1 for x in f if x == "tcp-fin") / len(f))
        deny.append(sum(1 for r in rows(org, "firewall") if r["action"] == "deny") / 181)
        threats.add(frozenset(r["detail"].split(".")[0] for r in rows(org, "endpoint_alerts") if r["event"] == "THREAT_QUARANTINED"))
    protos = {r["proto"] for org in P.ORG_IDS for r in rows(org, "firewall")}
    status = {r["status"] for org in P.ORG_IDS for r in rows(org, "web")}
    ok = max(edge) - min(edge) > 0.3 and max(fin) - min(fin) > 0.06 and max(deny) > 2 * min(deny) and len(threats) >= 3 and {"tcp", "udp", "icmp"} <= protos and len(status) >= 8
    return ok, f"share of Edge among browsers {min(edge):.0%} to {max(edge):.0%}; web sessions ending with FIN {min(fin):.0%} to {max(fin):.0%}; denied inbound per day {min(deny):.0f} to {max(deny):.0f}; " \
               f"{len(threats)} endpoint vocabularies; protocols {sorted(protos)}; {len(status)} web status codes"


def files():
    fs = glob.glob(os.path.join(BASE, "*", "*.csv"))
    sizes = [os.path.getsize(f) for f in fs]
    unsorted = 0
    for org in P.ORG_IDS:
        for k in KINDS:
            r = rows(org, k)
            unsorted += any(r[i]["t"] > r[i + 1]["t"] for i in range(len(r) - 1))
    ok = len(fs) == len(P.ORG_IDS) * len(KINDS) * 7 and max(sizes) < 45e6 and sum(sizes) < 125e6 and not unsorted
    return ok, f"{len(fs)} files, {sum(sizes) / 1e6:.1f} MB in total, largest {max(sizes) / 1e6:.1f} MB, all in time order"


def _range(kind):
    lo, hi = 1e12, 0
    for org in P.ORG_IDS:
        r = rows(org, kind)
        lo, hi = min(lo, r[0]["t"]), max(hi, r[-1]["t"])
    return lo, hi


def _cols(kind):
    with open(sorted(glob.glob(os.path.join(BASE, "city", f"{kind}_*.csv")))[0], encoding="utf-8") as fh:
        return fh.readline().strip().split(",")


def _ids(kind):
    out = set()
    for org in P.ORG_IDS:
        for r in rows(org, kind):
            out.add(r[{"firewall": "device", "auth": "host", "endpoint_alerts": "host", "mail": "gateway"}[kind]])
    out.discard("")
    return out


def _all_hosts():
    return {h["host_id"] for o in reg().values() for h in o["hosts"]}


def _both(*fs):
    def f():
        rs = [x() for x in fs]
        return all(r[0] for r in rs), "; ".join(r[1] for r in rs)
    return f


STREAMS = {STREAM_OF[k]: {"time_range": (lambda k=k: _range(k)), "columns": (lambda k=k: _cols(k)), "public_voice": False} for k in KINDS}
for _k in ("firewall", "auth", "mail", "endpoint_alerts"):
    STREAMS[STREAM_OF[_k]].update(ids=(lambda k=_k: _ids(k)), registry_ids=_all_hosts)

PROBES = {
    ("PARTNER-MAIL-CITY", "partner_mail_logs"): mail_extract("CITY", "mail_gateway_city"),
    ("PARTNER-MAIL-NASCC", "partner_mail_logs"): mail_extract("NASCC", "mail_gateway_airstation"),
    ("PARTNER-MAIL-BRW", "partner_mail_logs"): mail_extract("BRW", "mail_gateway_brightwake"),
    ("PARTNER-MAIL-REALISM", "partner_mail_logs"): mail_like_mail,
    ("PARTNER-CLICKS-CITY", "partner_web_logs"): clicks_contained("CITY"),
    ("PARTNER-CLICKS-NASCC", "partner_web_logs"): clicks_contained("NASCC"),
    ("PARTNER-CLICKS-BRW", "partner_web_logs"): clicks_contained("BRW"),
    ("PARTNER-LOGONS-CITY", "partner_auth_logs"): logon_extract("CITY", "city single sign-on"),
    ("PARTNER-LOGONS-NASCC", "partner_auth_logs"): logon_extract("NASCC", "base webmail"),
    ("PARTNER-SIGNONS-AFTER-CLICK", "partner_auth_logs"): story_signons,
    ("PARTNER-REMOTE-INBOUND", "partner_firewall_logs"): remote_inbound,
    ("PARTNER-REMOTE-CALENDAR", "partner_auth_logs"): remote_calendar,
    ("PARTNER-BRW-SESSIONS", "partner_firewall_logs"): brw_sessions,
    ("PARTNER-NASCC-LOGISTICS", "partner_firewall_logs"): nas_portal,
    ("PARTNER-NO-AID-PORTAL", "partner_web_logs"): no_aid_portal,
    ("PARTNER-ALERTS-COUNTY", "partner_web_logs"): alerts("COUNTY"),
    ("PARTNER-ALERTS-CITY", "partner_web_logs"): alerts("CITY"),
    ("PARTNER-TRANSLATIONS", "partner_mail_logs"): translations,
    ("PARTNER-PORT-NOTICES", "partner_mail_logs"): notices,
    ("PARTNER-PORT-GATE", "partner_web_logs"): port_gate,
    ("PARTNER-NASCC-STAFFING", "partner_auth_logs"): nas_staffing,
    ("PARTNER-LOAD-SRMC", "partner_auth_logs"): hospital_load("SRMC"),
    ("PARTNER-LOAD-BCMC", "partner_auth_logs"): hospital_load("BCMC"),
    ("PARTNER-DNS-BEFORE-WEB", "partner_dns_logs"): dns_before_web,
    ("PARTNER-WEB-FIREWALL", "partner_firewall_logs"): web_fw,
    ("PARTNER-NO-EXCLUSIVE-VALUES", "partner_firewall_logs"): no_exclusive_values,
    ("PARTNER-REGISTRY-LAYOUT", "partner_firewall_logs"): registry_layout,
    ("PARTNER-DIFFERENT-NETWORKS", "partner_firewall_logs"): different_networks,
    ("PARTNER-FILES", "partner_firewall_logs"): files,
}
for _org in ("CITY", "COUNTY", "PORT", "NASCC", "SRMC", "BCMC"):
    PROBES[(f"PARTNER-POWER-{_org}", "partner_endpoint_alerts")] = outages_quiet(_org)
for _k in KINDS:
    PROBES[(f"PARTNER-REGISTRY-{_k.upper()}", STREAM_OF[_k])] = registered(_k)

# The same probes under the MSEL event whose footprint they check (canon_timeline.json -> expected_observations),
# so that scripts/check_streams.py runs them. Where an event touches two organisations both probes must pass.
_P = dict(PROBES)
PROBES.update({
    ("EVT-0106", "partner_firewall_logs"): _P[("PARTNER-NASCC-LOGISTICS", "partner_firewall_logs")],
    ("EVT-0107", "partner_mail_logs"): _P[("PARTNER-MAIL-BRW", "partner_mail_logs")],
    ("EVT-0107", "partner_web_logs"): _P[("PARTNER-CLICKS-BRW", "partner_web_logs")],
    ("EVT-0107", "partner_dns_logs"): _P[("PARTNER-CLICKS-BRW", "partner_web_logs")],
    ("EVT-0209", "partner_firewall_logs"): _P[("PARTNER-BRW-SESSIONS", "partner_firewall_logs")],
    ("EVT-0306", "partner_mail_logs"): _both(_P[("PARTNER-MAIL-CITY", "partner_mail_logs")], _P[("PARTNER-MAIL-NASCC", "partner_mail_logs")]),
    ("EVT-0306", "partner_web_logs"): _both(_P[("PARTNER-CLICKS-CITY", "partner_web_logs")], _P[("PARTNER-CLICKS-NASCC", "partner_web_logs")]),
    ("EVT-0306", "partner_dns_logs"): _both(_P[("PARTNER-CLICKS-CITY", "partner_web_logs")], _P[("PARTNER-CLICKS-NASCC", "partner_web_logs")]),
    ("EVT-0306", "partner_auth_logs"): _both(_P[("PARTNER-LOGONS-CITY", "partner_auth_logs")], _P[("PARTNER-LOGONS-NASCC", "partner_auth_logs")], story_signons),
    ("EVT-0205", "partner_auth_logs"): _P[("PARTNER-NASCC-STAFFING", "partner_auth_logs")],
    ("EVT-1203", "partner_mail_logs"): _P[("PARTNER-PORT-NOTICES", "partner_mail_logs")],
    ("EVT-1403", "partner_web_logs"): _P[("PARTNER-ALERTS-CITY", "partner_web_logs")],
    ("EVT-2103", "partner_web_logs"): _P[("PARTNER-ALERTS-COUNTY", "partner_web_logs")],
    ("EVT-1602", "partner_endpoint_alerts"): _P[("PARTNER-POWER-SRMC", "partner_endpoint_alerts")],
    ("EVT-1607", "partner_auth_logs"): _both(_P[("PARTNER-LOAD-SRMC", "partner_auth_logs")], _P[("PARTNER-LOAD-BCMC", "partner_auth_logs")]),
    ("EVT-1407", "partner_mail_logs"): _P[("PARTNER-TRANSLATIONS", "partner_mail_logs")],
    ("EVT-0401", "partner_web_logs"): _P[("PARTNER-PORT-GATE", "partner_web_logs")],
})


if __name__ == "__main__":
    fails = 0
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    for key, fn in PROBES.items():
        if not key[0].startswith("PARTNER-") or (only and not any(o in key[0] for o in only)):   # canon aliases of the probes above are skipped
            continue
        try:
            ok, detail = fn()
        except Exception as e:                       # a probe that cannot run is a failure
            ok, detail = False, f"error: {type(e).__name__}: {e}"
        fails += not ok
        print(("PASS " if ok else "FAIL ") + f"{key[0]:28s} {key[1]:24s} {detail}")
    if not only:
        for sid, d in STREAMS.items():
            lo, hi = d["time_range"]()
            unknown = sorted(set(d["ids"]()) - set(d["registry_ids"]())) if d.get("ids") else []
            print(f"STREAM {sid}: {P.iso(int(lo))} .. {P.iso(int(hi))}; columns {len(d['columns']())}; unknown ids {unknown[:5]}")
            fails += bool(unknown)
    print(f"{'PASS' if not fails else 'FAIL'}: {sum(1 for k in PROBES if k[0].startswith('PARTNER-'))} probes, {fails} failure(s)")
    sys.exit(1 if fails else 0)
