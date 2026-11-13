"""IT logs of the other organisations in the scenario (streams partner_firewall_logs, partner_web_logs,
partner_dns_logs, partner_auth_logs, partner_mail_logs, partner_endpoint_alerts) and the six extract tables
in network_logs/audit that are cut from them.

    python3 scripts/streams/gen_partner_it.py registry          write 06_data_streams/partner_it_registry.json
    python3 scripts/streams/gen_partner_it.py <ORG> [YYYY-MM]   one organisation (all months, or one month)
    python3 scripts/streams/gen_partner_it.py extracts          cut the six extract tables from the logs on disk
    python3 scripts/streams/gen_partner_it.py --all [--resume]  registry, every organisation, extracts; --resume skips finished ones

Output: 05_other_sources/partner_it/<org>/<log>_<YYYY-MM>.csv, 2027-07-16T00:00Z to the end of 2028-01-12 UTC, and
network_logs/audit/{mail_gateway_city, mail_gateway_airstation, mail_gateway_brightwake, mail_url_clicks_city_airstation,
mail_url_clicks_brightwake, account_logons_city_airstation}.csv (rows of these logs, unchanged).
Deterministic. Workstation sessions and remote sign-ons are complete; web, DNS, firewall, mail and endpoint
background is a sample (see 06_data_streams/_internal/guide_partner_it.md). Reads delivered files of other
families only (alerts, port orders, hospital reports, base status, vessel remote sessions, base logistics log).
Run after gen_itsec.py portal: the air station's firewall carries the outside requests of the base logistics log.
"""
import bisect
import csv
import glob
import hashlib
import os
import sys

import numpy as np

import itsec_shared as S
import partner_it_mail as M
import partner_it_model as P
from common import D0_EPOCH, ROOT, iso, local_dt, local_ts, rng, ts, write_csv

DAY = P.DAY
hsh, hint, h01, pick = P.hsh, P.hint, P.h01, P.pick
FW_COLS, PROXY_COLS = S.FW_COLS, S.PROXY_COLS
DNS_COLS = ["time_utc", "client_ip", "query", "qtype", "rcode", "answer", "resolver"]
AUTH_COLS = ["time_utc", "host", "event_id", "account", "logon_type", "src_ip", "src_network", "result", "auth_method", "device"]
MAIL_COLS = ["time_utc", "gateway", "direction", "sender", "sender_domain", "recipient", "subject", "attachment_names", "size_bytes", "verdict", "action", "message_id"]
EP_COLS = ["time_utc", "host", "ip", "event", "detail", "initiated_by"]
LOGS = {"firewall": FW_COLS, "web": PROXY_COLS, "dns": DNS_COLS, "auth": AUTH_COLS, "mail": MAIL_COLS, "endpoint_alerts": EP_COLS}

LAM_WEB = {"office": 0.15, "gate": 0.07, "ops24": 0.075, "clinical": 0.085}      # web requests per logged-on hour (sampled)
VPN_MEAN = {"BRW": 3300, "PORT": 2700, "COUNTY": 2400, "SRMC": 1300, "BCMC": 1100}
OTHER_APPS = {"CITY": [("tcp", 8443, "ssl", 7), ("udp", 4500, "ipsec-esp-udp", 3)], "NASCC": [("tcp", 8443, "ssl", 5)],
              "BRW": [("tcp", 22, "ssh", 14), ("tcp", 9418, "git", 5), ("tcp", 8883, "mqtt", 3)], "PORT": [("tcp", 8883, "mqtt", 8), ("tcp", 5223, "ssl", 3)],
              "SRMC": [("udp", 4500, "ipsec-esp-udp", 6), ("tcp", 6661, "hl7", 9)], "BCMC": [("tcp", 6661, "hl7", 5), ("udp", 4500, "ipsec-esp-udp", 2)],
              "COUNTY": [("tcp", 8443, "ssl", 5), ("udp", 4500, "ipsec-esp-udp", 2)]}
NOISE_PORTS = [(("tcp", 23, "telnet"), 9), (("tcp", 445, "ms-ds-smb"), 9), (("tcp", 3389, "ms-rdp"), 8), (("tcp", 22, "ssh"), 8), (("tcp", 80, "web-browsing"), 5), (("tcp", 8080, "web-browsing"), 5),
               (("tcp", 1433, "mssql"), 4), (("tcp", 5900, "vnc"), 3), (("tcp", 6379, "-"), 3), (("tcp", 21, "ftp"), 2), (("tcp", 25, "smtp"), 2), (("tcp", 8443, "ssl"), 2),
               (("udp", 5060, "sip"), 4), (("udp", 161, "snmp"), 3), (("udp", 53, "dns"), 2), (("udp", 123, "ntp"), 2), (("udp", 1900, "ssdp"), 2), (("udp", 11211, "-"), 1),
               (("tcp", 2323, "telnet"), 2), (("tcp", 5555, "-"), 2), (("tcp", 9200, "-"), 1), (("tcp", 27017, "-"), 1), (("tcp", 3306, "mysql"), 2), (("tcp", 5432, "-"), 1),
               (("tcp", 8088, "web-browsing"), 1), (("tcp", 81, "web-browsing"), 1), (("tcp", 7547, "-"), 2), (("tcp", 37215, "-"), 1), (("icmp", 0, "ping"), 4)]
# workstation logon failures, lockouts, people who give up; failed remote sign-ons and how often they are retried at once
FAILS = {"CITY": (0.03, 0.006, 0.008, 0.045, 0.72), "NASCC": (0.015, 0.003, 0.004, 0.028, 0.6), "BRW": (0.04, 0.007, 0.01, 0.062, 0.8), "PORT": (0.028, 0.008, 0.006, 0.05, 0.7),
         "SRMC": (0.05, 0.005, 0.012, 0.075, 0.66), "BCMC": (0.038, 0.01, 0.009, 0.09, 0.58), "COUNTY": (0.022, 0.007, 0.005, 0.038, 0.75)}
# when people sign on from outside, by local hour
REMOTE_HOURS = {"CITY": [2, 1, 1, 1, 1, 2, 5, 8, 8, 6, 5, 5, 5, 5, 5, 5, 6, 8, 9, 9, 8, 6, 4, 3], "COUNTY": [1, 1, 1, 1, 1, 2, 6, 9, 7, 5, 4, 4, 5, 4, 4, 4, 5, 7, 8, 7, 6, 4, 3, 2],
                "NASCC": [1, 1, 1, 1, 2, 4, 8, 7, 4, 3, 3, 6, 7, 3, 3, 4, 7, 9, 8, 6, 5, 4, 2, 1], "BRW": [1, 1, 1, 1, 1, 1, 2, 5, 9, 10, 9, 8, 6, 8, 9, 9, 8, 6, 5, 5, 5, 4, 3, 2],
                "PORT": [3, 2, 2, 2, 3, 5, 7, 7, 6, 5, 5, 5, 5, 5, 5, 5, 6, 7, 7, 6, 5, 5, 4, 3], "SRMC": [4, 3, 3, 3, 4, 7, 9, 6, 5, 5, 5, 5, 5, 5, 5, 5, 6, 8, 9, 7, 6, 6, 5, 4],
                "BCMC": [5, 4, 3, 3, 3, 5, 8, 7, 5, 4, 4, 4, 4, 4, 4, 5, 5, 6, 9, 9, 7, 6, 6, 5]}
# what the endpoint consoles report most (weights of the eight kinds of event) differs with product and policy
EP_MIX = {"CITY": [0.4, 0.27, 0.07, 0.035, 0.08, 0.045, 0.06, 0.04], "NASCC": [0.31, 0.36, 0.05, 0.015, 0.05, 0.09, 0.105, 0.02], "BRW": [0.47, 0.14, 0.09, 0.06, 0.12, 0.03, 0.03, 0.06],
          "PORT": [0.36, 0.3, 0.06, 0.03, 0.13, 0.05, 0.04, 0.03], "SRMC": [0.28, 0.41, 0.05, 0.02, 0.06, 0.07, 0.09, 0.02], "BCMC": [0.44, 0.2, 0.1, 0.045, 0.1, 0.035, 0.03, 0.05],
          "COUNTY": [0.38, 0.24, 0.08, 0.05, 0.11, 0.04, 0.05, 0.05]}
MAC_EV = {"4624": "login", "4625": "login-failed", "4634": "logout"}
_gs = rng("partner_it", "scanners")
SCANNERS = [P.outside_ip(_gs) for _ in range(2500)]
SCAN_CUM = np.cumsum(1.0 / (np.arange(2500) + 6.0) ** 1.05)
SCAN_CUM /= SCAN_CUM[-1]

# ---- endpoint protection products (three different ones across the seven organisations)
EP = {
    "A": dict(defs=lambda d: f"definitions 1.{415 + (d + 61) // 9}.{(d + 61) * 37 % 2200}.0", engine=lambda d: f"engine 4.18.{24070 + (d + 61) // 30}",
              threats=[("PUA:Win32/Toolbar", 30), ("PUA:Win32/Bundler", 22), ("Adware:Win32/BrowserAssist", 16), ("HackTool:Win32/Keygen", 6), ("Tool:EICAR_Test_File", 5), ("Adware:JS/Popunder", 14)],
              clean="0 threats", admin="policy refresh"),
    "B": dict(defs=lambda d: f"signature set {270700 + (d + 61) * 3}", engine=lambda d: f"agent 7.{2 + (d + 61) // 70}.{(d + 61) % 70 // 14}",
              threats=[("Adware.Generic", 28), ("PUP.Optional.Toolbar", 24), ("PUP.Optional.Bundle", 18), ("Riskware.KeyGen", 5), ("EICAR-Test-File (not a virus)", 4), ("Adware.Popunder.JS", 12)],
              clean="no detections", admin="central policy"),
    "C": dict(defs=lambda d: f"content {8}.{(d + 61) // 2 + 4100}", engine=lambda d: f"sensor 5.{11 + (d + 61) // 45}",
              threats=[("Riskware/BrowserHelper", 20), ("Adware/Bundler", 25), ("Unwanted-Program/Toolbar", 22), ("Riskware/Keygen", 6), ("Test-File/EICAR", 6), ("Adware/Notification-Spam", 18)],
              clean="clean", admin="console"),
}

# ---- web sites
UNCAT = ["www.coastal-bend-fishing-reports.example", "files.svc-portal-cdn.example", "www.rgv-truck-parts.example", "app.shiftboard-scheduler.example",
         "www.gulf-coast-catering.example", "tracker.parcel-status-update.example", "www.padre-island-rentals.example", "forms.event-signup-sheets.example",
         "www.southtexas-youth-sports.example", "cdn.widget-embed-host.example"]
SECTOR_SITES = {
    "gov": ["webeoc.tdem-portal.example", "www.txdot-roadconditions.example", "portal.state-purchasing.example", "www.tx-comptroller-forms.example", "records.county-clerk-search.example",
            "codes.municipal-code-library.example", "gis.coastalbend-parcels.example", "www.texas-cities-league.example", "jobs.govt-careers.example", "grants.federal-grants-portal.example"],
    "navy": ["portal.navy-enterprise.example", "www.defense-travel.example", "training.navy-elearning.example", "mypay.defense-finance.example", "www.navy-personnel-command.example",
             "supply.fleet-logistics.example", "weather.fleet-metoc.example", "www.military-health-benefits.example"],
    "eng": ["parts.marine-spares.example", "class.marine-classification.example", "docs.cargo-automation-manuals.example", "git.codehost-cloud.example", "pkg.package-registry.example",
            "www.plc-vendor-support.example", "forum.embedded-dev.example", "www.component-distributor.example", "ci.build-cloud.example", "docs.protocol-specs.example"],
    "maritime": ["portal.vessel-scheduling.example", "ais-feed.maritime-data.example", "www.customs-filing.example", "pilots.aransas-cc-pilots.example", "www.tide-predictions.example",
                 "www.marine-exchange-tx.example", "www.ship-registry-lookup.example", "www.bunker-prices.example", "www.port-security-grants.example"],
    "health": ["hie.coastalbend-healthexchange.example", "labs.reference-diagnostics.example", "rx.eprescribe-network.example", "www.drug-reference.example", "www.clinical-guidelines.example",
               "portal.payer-eligibility.example", "www.medical-ce-credits.example", "www.nursing-board-tx.example", "www.blood-center-coastalbend.example",
               "pacs-view.teleradiology-group.example", "www.joint-accreditation.example"],
    "generic": [],
}
UTILITY_ONLY = ("meridiancontrols", "vantage-security", "relaytech", "pumpworks", "scada-vendor", "gridnotices", "tx-waterboard", "utilitybilling", "pipefittings", "generator-parts")
EP_UPDATE = {"A": "defs.sentinel-endpoint-updates.example", "B": "sig.corvid-security-cloud.example", "C": "content.harbourlight-av.example"}
CATS = ((("weather", "radar", "storm-prep", "tide", "metoc"), "weather"),
        (("roadwatch", "county", "cctexas", "waterboard", "gridnotices", "alertgateway", "tdem", "txdot", "purchasing", "comptroller", "clerk", "municipal", "parcels", "cities-league",
          "govt-careers", "grants", "navy", "defense", "fleet-logistics", "military", "customs", "nursing-board"), "government"),
        (("osupdates", "telemetry-os", "safecheck", "certstatus", "ntp-pool", "endpoint-updates", "security-cloud", "harbourlight"), "software updates"),
        (("bank", "finance", "payroll", "billing", "fleetfuel", "creditunion", "cpa"), "finance"), (("newswire", "ledger.example", "harborline", "media"), "news"),
        (("socialfeed",), "social media"), (("streamvideo",), "streaming media"), (("lucky",), "gambling"), (("afterdark",), "adult content"),
        (("retail", "partsdepot", "pipefittings", "generator-parts", "truckrental", "spares", "supply", "distributor", "uniforms", "tires", "auto"), "shopping"),
        (("airline", "hotel", "rentals"), "travel"), (("searchindex",), "search engines"), (("adnetwork",), "advertising"),
        (("cdn", "font", "jslibs", "geomaps", "basemaps"), "content delivery"), (("cloudstorage", "docsign"), "online storage"),
        (("hospital", "health", "diagnostics", "eprescribe", "drug-reference", "clinical", "payer", "medical", "blood-center", "teleradiology", "accreditation", "clinic", "pharma"), "health"),
        (("school", "training", "elearning", "college", "isd"), "education"), (("insurance",), "insurance"),
        (("codehost", "package-registry", "build-cloud", "embedded-dev", "protocol-specs", "plc-vendor", "tech"), "technology"),
        (("vessel", "maritime", "pilots", "marine", "ship", "bunker", "port-security", "freight", "shipping", "towing"), "transportation"),
        (("officesuite", "meetroom", "helpdesk", "benefits"), "business software"))


def _cat(name):
    if name in UNCAT or name in (P.LURE_HOST, P.BRW_LURE_HOST):
        return "uncategorised"
    for words, cat in CATS:
        if any(w in name for w in words):
            return cat
    return "business"


_catalogs = {}


def catalog(org):
    """(names, cumulative weights, system names) of the outside sites an organisation's people and machines use."""
    if org in _catalogs:
        return _catalogs[org]
    o = P.ORGS[org]
    g = rng("partner_it", "catalog", org)
    core = [s for s in S.G.SITES if _cat(s) != "software updates" and (org == "CITY" or not any(w in s for w in UTILITY_ONLY))]
    names, boost = [], []
    for s in core:
        names.append(s)
        boost.append(1.6 if _cat(s) in ("search engines", "business software", "content delivery") else 1.0)
    for k, sec in enumerate(o["sector"]):
        for s in SECTOR_SITES[sec]:
            names.append(s)
            boost.append(7.0 if k == 0 else 2.5)
    for i in range(34):                                                   # local businesses and services only this organisation's people visit
        sec = o["sector"][int(g.integers(len(o["sector"])))]
        a = M.A_WORDS[int(g.integers(len(M.A_WORDS)))]
        b = M.B_WORDS[sec][int(g.integers(len(M.B_WORDS[sec])))]
        n = f"www.{a}{b}.example"
        if n not in names:
            names.append(n)
            boost.append(0.9)
    for s in UNCAT:
        if h01("uncat", org, s) < 0.7:
            names.append(s)
            boost.append(0.5)
    names += ["www.lucky-spin-casino.example", "www.afterdark-videos.example"]
    boost += [0.04, 0.02]
    w = g.gamma(1.1, 1.0, len(names)) * np.array(boost)
    sysn = [s for s in S.G.SITES if _cat(s) == "software updates"] + [EP_UPDATE[o["ep"]]] * 4
    _catalogs[org] = (names, np.cumsum(w / w.sum()), sysn)
    return _catalogs[org]


def z(t):
    return iso(int(t))


_mail_cache, _click_cache = {}, {}
# where the links of the big mailing platforms and of all-staff notices lead
BULK_LINK = {"training-lms.example": "courses-training-lms.example", "benefits-portal.example": "my-benefits-portal.example",
             "surveys-online.example": "take-surveys-online.example", "federal-notices.example": "open-season-notices.example"}
STAFF_FORM = "staff-forms-online.example"


def mail_rows(org):
    if org not in _mail_cache:
        _mail_cache[org] = M.gen(org)
    return _mail_cache[org]


def mail_clicks(org):
    """Links in delivered mail that the recipient followed: [(epoch, mailbox, client address, url host, message id, sender domain)].
    A person follows a link some minutes to hours after the message arrived, the next time they are at their machine,
    or on a phone or at home through webmail (inside is False then, and the address is theirs there).
    The clicks canon fixes (P.story_clicks) are made by the same kind of people in the same way and are not in this list."""
    if org in _click_cache:
        return _click_cache[org]
    dom = P.registry()[org]["domain"]
    by_user = {}
    for s in P.sessions(org):
        by_user.setdefault(s["user"], []).append(s)
    bulk_subj = {c[5] for c in M.CAMPAIGNS.get(org, [])}
    out = []
    for t, row, _peer in mail_rows(org):
        direction, sdom, rcpt, subj, action, mid_ = row[2], row[4], row[5], row[6], row[10], row[11]
        if action != "delivered" or sdom in (P.LURE_DOM, P.BRW_LURE_DOM) or not rcpt.endswith("@" + dom):
            continue
        bulk = subj in bulk_subj
        if direction == "internal" and not bulk:
            continue
        if direction not in ("inbound", "internal"):
            continue
        if P.h01("mclick", org, mid_, rcpt) >= (0.3 if bulk else 0.15):
            continue
        user = rcpt.split("@")[0]
        ss = by_user.get(user, [])                         # people without a desk machine of their own read mail on phones and at home
        g = rng("partner_it", "mclick", org, mid_, rcpt)
        want = t + int(g.gamma(1.5, 1500)) + 45
        s = next((x for x in ss if x["b"] - 150 > want and x["a"] < want + 5 * P.DAY), None)       # read when they are next at their desk
        phone = g.random() < 0.22 or s is None             # ... or on a phone or at home, through webmail: the report shows that address
        if phone:
            if s is None and g.random() < 0.45:
                continue
            tw = want + int(g.gamma(1.5, 2400))
            lh = local_dt(tw).hour
            if lh < 6:
                tw += (6 - lh) * 3600 + int(g.integers(0, 3600))
            tc, cip, inside = tw, (P.home_of(org, user, tw)[0] if g.random() < 0.5 else P.away_of(org, user, g)[0]), False
        else:
            tc, cip, inside = max(want, s["a"] + int(g.integers(120, 1500))), s["ip"], True
            if tc > s["b"] - 90 or not P.edge_up(org, tc):
                continue
        if tc > P.SPAN_B - 900:
            continue
        if direction == "internal":
            url = STAFF_FORM
        elif sdom in BULK_LINK:
            url = BULK_LINK[sdom]
        else:
            k = int(P.h01("mlink", sdom) * 10)                                # a sender's links always lead to the same place
            pre = ("certificates.", "portal.", "docs.", "certificates.") if org == "BRW" else ("links.", "click.", "go.", "email.")   # the vendor's correspondents are class societies and suppliers
            url = ("www." + sdom) if k < 4 else sdom if k < 6 else (pre[k - 6] + sdom)
        out.append((int(tc), rcpt, cip, url, mid_, sdom, inside))
    out = sorted({(x[0], x[1], x[3]): x for x in out}.values())          # the same link followed in the same second is one click
    _click_cache[org] = out
    return out


def hour_weights(peaks):
    w = np.array(peaks, float)
    return np.cumsum(w / w.sum())


W_REMOTE = hour_weights([2, 1, 1, 1, 1, 2, 5, 8, 8, 6, 5, 5, 5, 5, 5, 5, 6, 8, 9, 9, 8, 6, 4, 3])


def local_hour_time(d_utc, g, cum):
    """A time on UTC day d_utc whose local hour follows the weights."""
    t0 = D0_EPOCH + d_utc * DAY
    off = int(-local_dt(t0 + 43200).utcoffset().total_seconds() // 3600)
    h = min(23, bisect.bisect_left(cum, g.random()))
    return t0 + ((h + off) % 24) * 3600 + g.random() * 3600


def gen_org(org):
    o = P.registry()[org]
    spec = P.ORGS[org]
    b, pfx, dom = P.base(org), spec["pfx"], o["domain"]
    fw_dev = o["edge_firewall"]
    resolvers = o["dns_resolvers"]
    hosts = o["hosts"]
    hid = {h["host_id"]: h for h in hosts}
    ws = [h for h in hosts if h.get("users")]
    servers = [h for h in hosts if h["device_type"] == "server" and h["ip"].startswith(b + ".")]
    staff = [a["account"] for a in o["accounts"] if a["kind"] == "staff"]
    admins = [a["account"] for a in o["accounts"] if a.get("role")] or staff[:2]
    names, cum, sysn = catalog(org)
    R, (z_in, z_out, z_dmz, z_srv) = spec["rules"], spec["zones"]
    ep = EP[spec["ep"]]
    ws_fail, ws_lock, ws_giveup, rem_fail, rem_retry = FAILS[org]
    w_remote = hour_weights(REMOTE_HOURS[org])
    noise_ports = [(k, w * (0.35 + 2.1 * h01("noiseport", org, k[1], k[0]))) for k, w in NOISE_PORTS]      # what scanners try depends on what an address range is known for
    ip_os = {h["ip"]: h["os"] for h in hosts}
    out = {k: [] for k in LOGS}
    web_ev = []                          # (t, ip, user, host name, opts)
    d_first, d_last = int((P.SPAN_A - D0_EPOCH) // DAY), int((P.SPAN_B - 1 - D0_EPOCH) // DAY)
    sess = P.sessions(org)
    user_sess = {}
    for s in sess:
        user_sess.setdefault(s["user"], []).append((s["a"], s["b"]))

    def at_desk(u, t):
        return any(a <= t < e for a, e in user_sess.get(u, ()))

    def fw(t, dur, device, action, rule, sz, dz, sip, sport, dip, dport, proto, app, bs, br, nat, reason):
        out["firewall"].append((t + dur if P.FW_TIME_AT_END else t,
                                [None, device, action, rule, sz, dz, sip, sport, dip, dport, proto, app, int(bs), int(br), round(dur, 1), nat, reason]))

    def auth(t, host, ev, acct, ltype, sip, net, result, method, device):
        if device == "managed mac":                              # these report through the directory plug-in, with its own event names
            ev, ltype = MAC_EV.get(ev, ev), {"2": "console", "7": "unlock"}.get(ltype, ltype)
        out["auth"].append((t, [None, host, ev, acct, ltype, sip, net, result, method, device]))

    def browser(user, ip, g):
        if ip_os.get(ip, "").startswith("macOS"):
            return pick([("Safari/macOS", 55), ("Chrome/macOS", 35), ("Firefox/macOS", 10)], h01("browser", org, user, ip))
        prim = pick(spec["browsers"], h01("browser", org, user, ip))
        return prim if g.random() < 0.9 else pick(spec["browsers"], g.random())

    def nat_of(ip, t):
        if org != "BRW":
            return P.pub(org, spec["nat"][hint("nat", ip) % len(spec["nat"])])
        vpn = ip.startswith(b + ".250.")
        best = None
        for t0, a in brw_nat.get(ip, ()):
            if abs(t0 - t) <= (7200 if vpn else 2700) and (best is None or abs(t0 - t) < abs(best[0] - t)):
                best = (t0, a)
        if best:
            return best[1]
        if vpn:
            return P.BRW_VPN_POOL[hint('vnat', ip, int(t // 7200)) % len(P.BRW_VPN_POOL)]
        return P.BRW_OFFICE_POOL[hint('onat', ip, int(t // 5400)) % len(P.BRW_OFFICE_POOL)]

    # ---- interactive sessions: logon/logoff and the browsing inside them
    dev_of = {"workstation": "domain workstation", "console": "shared console", "clinical workstation": "clinical workstation"}
    favs = {}
    for s in sess:
        g = rng("partner_it", "ev", org, s["host"], s["a"])
        a, e = s["a"], s["b"]
        h = hid[s["host"]]
        m = "badge+pin" if s["kind"] == "clinical" else spec["auth_ws"]
        if m == "smartcard" and g.random() < 0.03:
            m = "password"
        dv = "managed mac" if h["os"].startswith("macOS") else dev_of[h["device_type"]]
        r = g.random()
        if g.random() < ws_giveup:                           # tried earlier, gave up, came back after sorting the password out
            tf = a - int(g.integers(4200, 15000))
            for _ in range(int(g.integers(1, 5))):
                tf += int(g.integers(4, 40))
                auth(tf, s["host"], "4625", s["user"], "2", s["ip"], "internal", "FAILED", m, dv)
        if r < ws_fail:                                      # a mistyped password or two
            tf = a
            for _ in range(1 + int(g.random() < 0.3) + int(g.random() < 0.1)):
                tf -= int(g.integers(5, 45))
                auth(tf, s["host"], "4625", s["user"], "2", s["ip"], "internal", "FAILED", m, dv)
        elif r < ws_fail + ws_lock:                          # locked out; back after a call to the help desk
            tf = a - int(g.integers(420, 2700))
            for _ in range(int(g.integers(3, 6))):
                tf += int(g.integers(4, 30))
                auth(tf, s["host"], "4625", s["user"], "2", s["ip"], "internal", "FAILED", m, dv)
        auth(a, s["host"], "4624", s["user"], "2", s["ip"], "internal", "SUCCESS", m, dv)
        if not s["cut"] and g.random() > 0.025:              # no logoff when the power goes, or when the machine is simply left on
            auth(e, s["host"], "4634", s["user"], "2", s["ip"], "internal", "SUCCESS", m, dv)
        hours = (e - a) / 3600
        if s["kind"] == "clinical":                          # shared clinical workstations are unlocked again and again; more so when the department is busy
            for _ in range(int(g.poisson(0.11 * hours * P.ed_factor(org, P.lday(a))))):
                auth(a + 120 + g.random() * max(1, e - a - 240), s["host"], "4624", s["user"], "7", s["ip"], "internal", "SUCCESS", m, dv)
        if s["user"] not in favs:
            gf = rng("partner_it", "fav", org, s["user"])
            favs[s["user"]] = [names[min(len(names) - 1, bisect.bisect_left(cum, gf.random()))] for _ in range(5)]
        for _ in range(int(g.poisson(LAM_WEB[s["kind"]] * spec["web_rate"] * hours))):
            t = a + 60 + g.random() * max(1, e - a - 120)
            n = favs[s["user"]][int(g.integers(5))] if g.random() < 0.3 else names[min(len(names) - 1, bisect.bisect_left(cum, g.random()))]
            web_ev.append((t, s["ip"], s["user"], n, None))
        for _ in range(int(g.poisson(0.012 * hours))):        # names looked up without a web request (internal services, a few that do not exist)
            t = a + 30 + g.random() * max(1, e - a - 60)
            r = g.random()
            res = resolvers[0] if g.random() < spec["res_split"] else resolvers[1]
            if r < 0.55 and servers:
                srv = servers[int(g.integers(len(servers)))]
                out["dns"].append((t, [None, s["ip"], f"{srv['hostname'].lower()}.{dom}", "A", "NOERROR", srv["ip"], res]))
            elif r < 0.8:
                out["dns"].append((t, [None, s["ip"], f"_ldap._tcp.dc._msdcs.{dom}", "SRV", "NOERROR", f"{hosts[0]['hostname'].lower()}.{dom}", res]))
            elif r < 0.93:
                out["dns"].append((t, [None, s["ip"], names[int(g.integers(len(names)))], "AAAA", "NOERROR", "-", res]))
            else:
                out["dns"].append((t, [None, s["ip"], str(g.choice([f"wpad.{dom}", f"isatap.{dom}", f"{hsh('typo', t, n=6)}.{dom}"])), "A", "NXDOMAIN", "-", res]))

    # ---- machines talking by themselves (updates, certificate checks): any hour, while the site has power
    for d in range(d_first, d_last + 1):
        g = rng("partner_it", "sys", org, d)
        for _ in range(int(g.poisson(0.16 * len(ws)))):
            h = ws[int(g.integers(len(ws)))]
            t = D0_EPOCH + d * DAY + g.random() * DAY
            if P.powered(org, h["site_id"], t) and P.powered(org, h["site_id"], t - 900):
                web_ev.append((t, h["ip"], "-", sysn[int(g.integers(len(sysn)))], None))

    # ---- link clicks on the aid-themed message (city, air station) and on the vendor's certificate notice
    for t, mb, h, url_host in P.story_clicks(org):
        g = rng("partner_it", "clickflow", org, int(t))
        web_ev.append((t, h["ip"], mb.split("@")[0], url_host, {"bo": int(g.gamma(2, 1600)) + 2400, "bi": int(g.gamma(2, 42000)) + 60000, "dur": float(g.gamma(2, 30)) + 12}))
    # ---- links in ordinary mail that people follow (the gateway rewrites links and reports every click)
    for t, mb, ip, url_host, _mid, _sd, inside in mail_clicks(org):
        if not inside:
            continue                                      # followed from a phone or from home: not this network's traffic
        g = rng("partner_it", "mclickflow", org, int(t), mb)
        web_ev.append((t, ip, mb.split("@")[0], url_host, {"bo": int(g.gamma(2, 1600)) + 2400, "bi": int(g.gamma(2, 42000)) + 60000, "dur": float(g.gamma(2, 30)) + 12}))
    brw_nat = {}
    if org == "BRW":
        wsb = P.brw_ws(P.BRW_CLICK_PERSON)
        g = rng("partner_it", "clickflow", org)
        brw_nat.setdefault(wsb["ip"], []).append((P.BRW_CLICK_T, P.BRW_CLICK_NAT))
        web_ev.append((P.BRW_CLICK_T, wsb["ip"], P.BRW_CLICK_PERSON, P.BRW_LURE_HOST, {"bo": int(g.gamma(2, 1600)) + 2400, "bi": int(g.gamma(2, 42000)) + 60000, "dur": float(g.gamma(2, 30)) + 12}))

    # ---- public alerts issued from the alerting workstations, and the routine sign-ins to the origination service
    for t, host, aid, kind in P.alert_issues(org):
        g = rng("partner_it", "alert", org, int(t), kind)
        s = P.session_at(org, host, t)
        if s:
            web_ev.append((t - int(g.integers(3, 25)), hid[host]["ip"], s["user"], P.ALERT_HOST, {"bo": int(g.integers(5200, 9800)), "bi": int(g.integers(2100, 4800)), "dur": float(g.uniform(4, 30))}))
    for host in sorted({v[1] for v in P.ALERT_SOURCES.values() if v[0] == org}):
        for d in range(d_first, d_last + 1):
            g = rng("partner_it", "alertcheck", host, d)
            wd = local_dt(local_ts(d, "12:00")).weekday()
            if g.random() < (0.9 if wd == 2 else 0.11):       # weekly proficiency check, and the odd look at the console on other days
                t = local_ts(d, "09:30") + int(g.integers(0, 3 * 3600)) if wd == 2 else local_ts(d, "07:30") + int(g.integers(0, 10 * 3600))
                s = P.session_at(org, host, t)
                if s:
                    web_ev.append((t, hid[host]["ip"], s["user"], P.ALERT_HOST, {"bo": int(g.integers(1800, 8200)), "bi": int(g.integers(2400, 90000)), "dur": float(g.uniform(6, 240))}))

    # ---- Brightwake: every session in the vessel remote-session log
    if org == "BRW":
        for r in P.brw_sessions():
            t = ts(r["login_utc"])
            g = rng("partner_it", "bw", int(t), r["vendor_account"])
            ok = r["result"] == "SUCCESS"
            dur = float(r["duration_s"] or 0) or float(g.uniform(0.6, 4.2))
            nb = int(r["bytes_out"] or 0)
            bo = int(g.integers(2400, 9000)) + (nb // 40 if ok else 0)
            bi = nb if ok else int(g.integers(900, 2600))
            lead = float(g.uniform(0.4, 2.2))                 # the connection opens a moment before the gateway records the login and closes a few seconds after the logout
            fw(t - lead, dur + lead + float(g.uniform(0.3, 7.5)), "BRW-FW-DMZ-01", "allow", "remote-maintenance-portal", "internet", "dmz", r["src_ip"], 1024 + int(g.integers(0, 60000)), P.BRW_GATEWAY[1], 443, "tcp", "ssl",
               bo + 40 * (8 + bo // 1200), bi + 40 * (8 + bi // 1200), "", "tcp-fin" if ok or g.random() < 0.5 else "tcp-rst-from-server")
            person = P.BRW_ENG[r["vendor_account"]]
            if r["src_ip"] in P.BRW_OFFICE_POOL:
                wsx = P.brw_ws(person)
                brw_nat.setdefault(wsx["ip"], []).append((t, r["src_ip"]))
                web_ev.append((t - 1 - g.random() * 2, wsx["ip"], person, P.BRW_GATEWAY[0], {"bo": bo, "bi": bi or 1800, "dur": dur + 1}))
            elif r["src_ip"] in P.BRW_VPN_POOL:
                hip, hnet = P.home_of(org, person, t)
                tv = t - int(g.integers(180, 2100))
                vip = f"{b}.250.{20 + hint('vpn', person) % 200}"
                auth(tv, spec["remote"][0], "vpn-login", person, "remote", hip, hnet, "SUCCESS", "password+token", "known device")
                fw(tv - 1, dur + (t - tv) + int(g.integers(60, 900)), fw_dev, "allow", R["remote"], z_out, z_dmz, hip, 1024 + int(g.integers(0, 60000)), spec["remote"][1], 443, "tcp", "ssl",
                   int(g.integers(4e5, 3e6)), int(g.integers(1e6, 9e6)), "", "tcp-fin")
                brw_nat.setdefault(vip, []).append((t, r["src_ip"]))
                web_ev.append((t - 1 - g.random() * 2, vip, person, P.BRW_GATEWAY[0], {"bo": bo, "bi": bi or 1800, "dur": dur + 1}))
    # ---- air station: outside connections to the base logistics system (delivered base logistics access log)
    if org == "NASCC":
        for fp in sorted(glob.glob(os.path.join(P.SRC, "network_logs/portal/base_logistics_access_*.csv"))):
            for r in csv.DictReader(open(fp, newline="", encoding="utf-8")):
                if r["client_network"] != "base network":
                    t = ts(r["time_utc"])
                    g = rng("partner_it", "naslog", int(t), r["client_ip"], r["path"])
                    br = int(r["bytes"] or 0) + 3400
                    fw(t, float(g.gamma(2, 1.4)) + 0.3, fw_dev, "allow", R["pub"], z_out, z_dmz, r["client_ip"], 1024 + int(g.integers(0, 60000)), P.NAS_PORTAL_VIP, 443, "tcp", "ssl",
                       int(g.integers(900, 2600)), br + 40 * (6 + br // 1300), "", pick(spec["end_mix"], g.random()))

    # ---- remote sign-ons (single sign-on, webmail, VPN) and the connections that carried them
    rhost, rvip, rservice, revent = spec["remote"]
    full = (lambda a: a) if org not in ("CITY", "NASCC") else (lambda a: f"{a}@{dom}")
    gp = rng("partner_it", "remoteprop", org)
    prop = gp.gamma(0.55, 1.0, len(staff)) + 0.03                        # a few people sign on from outside all the time, most hardly ever
    for i, a_ in enumerate(staff):                                       # people on the small local providers live further out and work from home more
        if P.small_provider(P.home_of(org, a_)[1]):
            prop[i] = prop[i] * 3.0 + 0.6
    prop_cum = np.cumsum(prop / prop.sum())

    def remote(t, acct, sip, net, result, meth, device, g, user=None):
        auth(t, rhost, revent, acct, "remote", sip, net, result, meth, device)
        ok = result == "SUCCESS"
        if spec["vpn"] and ok:
            dur = float(g.gamma(2, VPN_MEAN[org] / 2)) + 90
            vip = f"{b}.250.{20 + hint('vpn', acct, int(t // 3600)) % 200}"
            for _ in range(int(g.poisson(LAM_WEB["office"] * spec["web_rate"] * 0.6 * dur / 3600))):
                web_ev.append((t + 20 + g.random() * max(1, dur - 40), vip, user or acct, names[min(len(names) - 1, bisect.bisect_left(cum, g.random()))], None))
            bs, br = int(g.gamma(2, dur * 300)) + 4000, int(g.gamma(2, dur * 1500)) + 9000
        else:
            dur = float(g.gamma(2, 9)) + 1.5 if ok else float(g.uniform(0.8, 6))
            bs, br = int(g.integers(1800, 9000)), int(g.integers(6000, 90000)) if ok else int(g.integers(1500, 5200))
        fw(t - 1, dur, fw_dev, "allow", R["remote"], z_out, z_dmz, sip, 1024 + int(g.integers(0, 60000)), rvip, 443, "tcp", "ssl", bs, br, "",
           pick(spec["end_mix"], g.random()) if ok else "tcp-fin")

    clickers = {mb.split("@")[0] for _, mb, _, _ in P.story_clicks(org)}
    story_net = P.netmap.label(P.netmap.STORY_POOL[0])
    for t, mb, sip, label in P.story_signons(org):
        remote(t, mb, sip, label, "SUCCESS", "password", "new device", rng("partner_it", "signonflow", org, mb))
    for d in range(d_first, d_last + 1):
        t0 = D0_EPOCH + d * DAY
        g = rng("partner_it", "remote", org, d)
        dl = P.lday(t0 + 43200)
        for _ in range(int(g.poisson(spec["remote_per_day"] * P.remote_factor(org, dl)))):
            t = local_hour_time(d, g, w_remote)
            acct = staff[min(len(staff) - 1, int(np.searchsorted(prop_cum, g.random())))]
            if org == "BRW" and acct in P.BRW_ENG.values() and g.random() < 0.9:
                continue                                              # the engineers' remote days are in the vessel remote-session log
            if at_desk(acct, t) or not P.edge_up(org, t):
                continue
            away = g.random() < 0.07
            sip, net = P.away_of(org, acct, g) if away else P.home_of(org, acct, t)
            if away and acct in clickers and net == story_net:
                sip, net = P.home_of(org, acct, t)                    # (keeps "a network this account never used" true for the accounts canon fixes)
            meth = pick(spec["remote_methods"], g.random())
            fallback = [m_ for m_, _ in spec["remote_methods"] if m_ == "password"]
            if fallback and meth != "password" and P.small_provider(net) and g.random() < 0.38:
                meth = "password"                                     # token prompts by text message often do not arrive on the small local providers
            device = "new device" if g.random() < (0.45 if away else (0.3 if meth == "password" else 0.03)) else "known device"
            if g.random() < rem_fail:                                 # a failed attempt; most people try again at once
                remote(t, full(acct), sip, net, "FAILED", meth, device, g)
                if g.random() < 0.25:
                    t += int(g.integers(5, 40))
                    remote(t, full(acct), sip, net, "FAILED", meth, device, g)
                if g.random() > rem_retry:
                    continue
                t += int(g.integers(6, 90))
            remote(t, full(acct), sip, net, "SUCCESS", meth, device, g, user=acct)

    # ---- web, DNS and firewall rows for every web event, in time order
    web_ev.sort(key=lambda e: e[0])
    cache, rcache = {}, {}
    blocked = spec["blocked"]
    nat_res = P.pub(org, 7) if org != "BRW" else P.BRW_NAT_RES
    fwd = [P.stable_ip("resolver", spec["providers"], org if k else "", k) for k in range(2)]      # the access provider's resolvers

    def lookup(t, ip, name, g):
        """The address a client uses for a name: its cached answer, or a fresh one from the resolver (logged)."""
        hit = cache.get((ip, name))
        if hit and t - hit[0] <= 300:
            return hit[1]
        ips = P.site_ips(name)
        ans = ips[hint("rr", name, int(t // 600)) % len(ips)]
        cache[(ip, name)] = (t, ans)
        res = resolvers[0] if g.random() < spec["res_split"] else resolvers[1]
        out["dns"].append((t - 0.4, [None, ip, name, "A", "NOERROR", ans, res]))
        if t - rcache.get(name, -1e9) > 4 * 3600:                        # the resolvers ask a forwarder when they have no fresh answer of their own
            rcache[name] = t
            fw(t - 0.39, float(g.uniform(0.01, 0.2)), fw_dev, "allow", R["dns"], z_srv, z_out, res, 1024 + int(g.integers(0, 60000)), fwd[int(g.random() < 0.3)], 53, "udp", "dns",
               int(g.integers(62, 96)), int(g.integers(110, 420)), nat_res, "aged-out")
        return ans

    for t, ip, user, name, opt in web_ev:
        if not P.edge_up(org, t):
            continue
        g = rng("partner_it", "web", org, ip, f"{t:.3f}", name)
        cat = _cat(name)
        opt = opt or {}
        https = bool(opt) or not (cat == "software updates" and g.random() < 0.55) and g.random() < 0.97
        dst = lookup(t, ip, name, g)
        ua = browser(user, ip, g) if user != "-" else "-"
        if cat in blocked and not opt:
            out["web"].append((t, [None, ip, user, "CONNECT" if https else "GET", "https" if https else "http", name, "-" if https else "/", 403, "blocked", cat,
                                   int(g.integers(300, 900)), int(g.integers(900, 1500)), ua, spec["policy"][1]]))
            continue
        bo = opt.get("bo") or int(g.gamma(2, 1600)) + 300
        bi = opt.get("bi") or int(g.gamma(2, 42000)) + 600
        dur = opt.get("dur") or float(g.gamma(2, 9)) + 0.3
        reason = pick(spec["end_mix"], g.random())
        if https:
            status, path, meth = 200, "-", "CONNECT"
            if not opt and g.random() < 0.011:                         # the far end did not answer
                status, bi, reason = (502 if g.random() < 0.6 else 504), int(g.integers(0, 400)), ("tcp-rst-from-server" if g.random() < 0.6 else "aged-out")
        else:
            meth = "GET" if g.random() < 0.93 else ("POST" if g.random() < 0.7 else "HEAD")
            status = int(pick([(200, 70), (304, 12), (301, 4), (302, 4), (404, 5), (204, 3), (503, 1.2), (500, 0.8)], g.random()))
            path = str(g.choice(["/", "/index.html", f"/content/{hsh('p', t, n=8)}.cab", f"/pki/{hsh('c', t, n=6)}.crl", "/favicon.ico", f"/v{int(g.integers(1, 4))}/check?id={hsh('q', t, n=10)}",
                                 f"/updates/{hsh('u', t, n=5)}/manifest.xml", f"/static/{hsh('s', t, n=7)}.js", f"/images/{hsh('i', t, n=6)}.png", "/robots.txt", f"/ocsp/{hsh('o', t, n=12)}"]))
            if status in (304, 301, 302, 204):
                bi = int(g.integers(180, 700))
        if reason == "aged-out":
            dur += float(g.uniform(30, 300))
        out["web"].append((t, [None, ip, user, meth, "https" if https else "http", name, path, status, "allowed", cat, bo, bi, ua, spec["policy"][0]]))
        fw(t + 0.05, dur, fw_dev, "allow", R["web"], "vpn" if ip.startswith(b + ".250.") else z_in, z_out, ip, 49152 + int(g.integers(0, 16000)), dst, 443 if https else 80, "tcp",
           "ssl" if https else "web-browsing", int(bo * g.uniform(1.01, 1.05)) + 40 * int(g.integers(5, 14)), int(bi * g.uniform(1.015, 1.075)) + 40 * int(g.integers(5, 16)), nat_of(ip, t), reason)

    # ---- other things that cross the edge: time, monitoring pings, sector applications
    targets = {(p, port): [P.stable_ip("app", org, port, k) for k in range(1 + hint("napp", org, port) % 3)] for p, port, _, _ in OTHER_APPS[org]}
    ntp = [P.stable_ip("ntp", k) for k in range(3)]
    for d in range(d_first, d_last + 1):
        g = rng("partner_it", "edge", org, d)
        t0 = D0_EPOCH + d * DAY
        for _ in range(int(g.poisson(5))):
            t = t0 + g.random() * DAY
            src = servers[int(g.integers(min(2, len(servers))))]["ip"] if g.random() < 0.8 else hid[fw_dev]["ip"]
            fw(t, float(g.uniform(0.02, 0.3)), fw_dev, "allow", R["ntp"], z_srv, z_out, src, 123, ntp[int(g.integers(3))], 123, "udp", "ntp", 76, 76, nat_res, "aged-out")
        for _ in range(int(g.poisson(3))):
            t = t0 + g.random() * DAY
            n = int(g.integers(1, 6))
            fw(t, float(n), fw_dev, "allow", R["icmp"], z_srv, z_out, hid[fw_dev]["ip"], 0, P.pub(org, 1) if org != "BRW" else P.BRW_UPSTREAM, 0, "icmp", "ping", 84 * n, 84 * n if g.random() < 0.985 else 0, nat_res, "aged-out")
        for proto, port, app, per_day in OTHER_APPS[org]:
            for _ in range(int(g.poisson(per_day * (0.25 + 0.75 * P.day_factor(org, P.lday(t0 + 43200)))))):
                t = local_hour_time(d, g, M.W_HOUR.cumsum() / M.W_HOUR.sum())
                if app in ("ssh", "git", "mqtt") and org == "BRW":
                    hq = ws[int(g.integers(len(ws)))]
                    if not P.session_at(org, hq["host_id"], t):
                        continue
                    src, zone = hq["ip"], z_in
                else:
                    src, zone = servers[int(g.integers(len(servers)))]["ip"], z_srv
                dur = float(g.gamma(2, 900)) + 20 if app in ("ssh", "ipsec-esp-udp", "mqtt") else float(g.gamma(2, 8)) + 0.5
                tg = targets[(proto, port)]
                fw(t, dur, fw_dev, "allow", R["other"], zone, z_out, src, 1024 + int(g.integers(0, 60000)), tg[int(g.integers(len(tg)))], port, proto, app,
                   int(g.gamma(2, 9000)) + 600, int(g.gamma(2, 30000)) + 600, nat_of(src, t) if zone == z_in else nat_res, "aged-out" if proto == "udp" else pick(spec["end_mix"], g.random()))

    # ---- unsolicited traffic from the internet: probes the edge turns away, and connections to the published services
    #      that never get past the handshake (scanners and crawlers; the same ones visit everybody)
    vips = [(rvip, R["remote"], fw_dev, spec["pub_scan"])]
    if org == "NASCC":
        vips.append((P.NAS_PORTAL_VIP, R["pub"], fw_dev, 5))
    if org == "BRW":
        vips.append((P.BRW_GATEWAY[1], "remote-maintenance-portal", "BRW-FW-DMZ-01", 8))
    last_pub = int(spec["public"].split("/")[1]) == 27 and 30 or 14
    for d in range(d_first, d_last + 1):
        g = rng("partner_it", "noise", org, d)
        t0 = D0_EPOCH + d * DAY

        def src():
            return SCANNERS[min(2499, int(np.searchsorted(SCAN_CUM, g.random())))] if g.random() < 0.62 else P.outside_ip(g)

        for _ in range(int(g.poisson(spec["noise_per_day"]))):
            t = t0 + g.random() * DAY
            s = src()
            proto, port, app = pick(noise_ports, g.random())
            for k in range(1 if g.random() < 0.8 else int(g.integers(2, 6))):     # some sources try several addresses in a row
                fw(t + k * float(g.uniform(0.2, 3)), 0.0, fw_dev, "deny", R["deny"], z_out, z_dmz, s, 0 if proto == "icmp" else 1024 + int(g.integers(0, 60000)),
                   P.pub(org, int(g.integers(1, last_pub))) if org != "BRW" else f"192.0.2.{64 + int(g.integers(1, 15))}", port, proto, app, 0, 0, "", "policy-deny")
        for vip, rule, dev, per_day in vips:
            for _ in range(int(g.poisson(per_day))):
                t = t0 + g.random() * DAY
                kind = g.random()
                page = dev == "BRW-FW-DMZ-01" and kind < 0.3                # a crawler that fetches the sign-in page
                reason = "tcp-fin" if page else str(g.choice(["tcp-rst-from-client", "aged-out", "tcp-fin"], p=[0.55, 0.3, 0.15]))
                fw(t, float(g.uniform(30, 120)) if reason == "aged-out" else float(g.uniform(0.1, 4)), dev, "allow", rule, z_out if dev == fw_dev else "internet", z_dmz if dev == fw_dev else "dmz",
                   src(), 1024 + int(g.integers(0, 60000)), vip, 443, "tcp", "ssl", int(g.integers(120, 620)) + (int(g.integers(600, 2400)) if page else 0),
                   int(g.integers(0, 1500)) + (int(g.integers(8000, 42000)) if page else 0), "", reason)

    # ---- mail gateway, and the mail servers it talks to when it stands in the organisation's own network
    gw_ip, hosted = spec["mx"][1], spec["mx"][2]
    for t, row, peer in mail_rows(org):
        out["mail"].append((t, row))
        if peer and not hosted and P.edge_up(org, t):
            g = rng("partner_it", "smtp", org, t, row[11])
            size, dur = row[8], float(g.gamma(2, 1.1)) + 0.4 + row[8] / 4e5
            if row[2] == "inbound":
                rej = row[10] == "rejected"
                fw(t - dur, dur, fw_dev, "allow", R["mail_in"], z_out, z_dmz, peer, 1024 + int(g.integers(0, 60000)), gw_ip, 25, "tcp", "smtp",
                   (int(size * 1.37) + 1900) if not rej else int(g.integers(500, 1400)), int(g.integers(500, 1500)), "", "tcp-fin" if not rej else "tcp-rst-from-server")
            elif row[2] == "outbound":
                fw(t, dur, fw_dev, "allow", R["mail_out"], z_dmz, z_out, gw_ip, 1024 + int(g.integers(0, 60000)), peer, 25, "tcp", "smtp", int(size * 1.37) + 1900, int(g.integers(500, 1500)), "", "tcp-fin")

    # ---- endpoint protection console
    for d in range(d_first, d_last + 1):
        g = rng("partner_it", "ep", org, d)
        for _ in range(int(g.poisson(spec["ep_per_day"]))):
            h = ws[int(g.integers(len(ws)))]
            t = D0_EPOCH + d * DAY + g.random() * DAY
            if not P.powered(org, h["site_id"], t):
                continue                                              # nothing reports from a building without power
            s = P.session_at(org, h["host_id"], t)
            k = int(g.choice(8, p=EP_MIX[org]))
            row = lambda ev, det, who="system": out["endpoint_alerts"].append((t, [None, h["host_id"], h["ip"], ev, det, who]))
            if k == 0:
                row("DEFINITIONS_UPDATED", ep["defs"](d))
            elif k == 1:
                row("SCAN_COMPLETED", ep["clean"])
            elif k == 2:
                row("REALTIME_PROTECTION_ENABLED", ep["admin"])
            elif k == 3:
                thr = pick(ep["threats"], g.random())
                row("THREAT_QUARANTINED", thr + (f".{int(g.integers(100, 999))}" if thr.endswith("Generic") else ""))
            elif k == 4:
                row("AGENT_HEARTBEAT_MISSED", "")
            elif k == 5:
                row("AGENT_UPDATED", ep["engine"](d))
            elif k == 6 and s:
                row("SCAN_STARTED", "on demand", s["user"])
                out["endpoint_alerts"].append((t + int(g.integers(90, 2400)), [None, h["host_id"], h["ip"], "SCAN_COMPLETED", ep["clean"], s["user"]]))
            elif k == 7:
                who = admins[int(g.integers(len(admins)))]
                row("REALTIME_PROTECTION_DISABLED", "troubleshooting", who)
                out["endpoint_alerts"].append((t + int(g.integers(240, 5400)), [None, h["host_id"], h["ip"], "REALTIME_PROTECTION_ENABLED", ep["admin"] if g.random() < 0.5 else "manual", who if g.random() < 0.6 else "system"]))
        for site, wins in P.outages(org).items():                   # agents fall silent when the power goes and report back when it returns
            for a, e in wins:
                if not D0_EPOCH + d * DAY <= a < D0_EPOCH + (d + 1) * DAY:
                    continue
                for h in ws:
                    gh = rng("partner_it", "epo", h["host_id"], a)
                    if h["site_id"] == site and gh.random() < 0.5:
                        out["endpoint_alerts"].append((e + int(gh.integers(300, 5400)), [None, h["host_id"], h["ip"], "AGENT_HEARTBEAT_MISSED", f"last seen {z(a - int(gh.integers(0, 600)))}", "system"]))
    # nothing crosses an edge that has no power
    out["firewall"] = [x for x in out["firewall"] if x[1][1] != fw_dev or P.edge_up(org, x[0])]
    out["dns"] = [x for x in out["dns"] if P.edge_up(org, x[0])]
    return out


def write_org(org, only_month=None):
    out = gen_org(org)
    total = {}
    for kind, cols in LOGS.items():
        rows = sorted((r for r in out[kind] if P.SPAN_A <= r[0] < P.SPAN_B), key=lambda r: r[0])
        for mon, a, b in S.months():
            if only_month and mon != only_month:
                continue
            if mon == S.months()[-1][0]:
                b = P.SPAN_B                                   # the last file runs to the end of the last UTC day
            part, seen = [], set()
            for t, r in rows:
                if a <= t < b:
                    r = list(r)
                    if r[0] is None:
                        r[0] = z(t)
                    k = tuple(map(str, r))
                    if k not in seen:                          # two identical lines in the same second are one event
                        seen.add(k)
                        part.append(r)
            total[kind] = total.get(kind, 0) + write_csv(f"{P.OUT}/{org.lower()}/{kind}_{mon}.csv", cols, part)
    print(f"{org}: " + ", ".join(f"{k} {v:,}" for k, v in total.items()))


def _log_rows(org, kind):
    for fp in sorted(glob.glob(os.path.join(ROOT, P.OUT, org.lower(), f"{kind}_*.csv"))):
        with open(fp, newline="", encoding="utf-8") as fh:
            yield from csv.DictReader(fh)


def write_extracts():
    """The six tables in network_logs/audit are rows of the logs written above, unchanged: the mail gateway logs of the
    city, the air station and the vendor for a few weeks, the remote sign-ons of the city and the air station for the
    same ten days, and the link-click reports of the two mail gateways for the messages from two sender domains."""
    for org, name in (("CITY", "mail_gateway_city"), ("NASCC", "mail_gateway_airstation"), ("BRW", "mail_gateway_brightwake")):
        a, b = P.EXTRACT_WIN[org]
        n = write_csv(f"{P.AUDIT}/{name}.csv", MAIL_COLS, ([r[c] for c in MAIL_COLS] for r in _log_rows(org, "mail") if a <= ts(r["time_utc"]) < b))
        print(f"{name}: {n:,} rows")
    rows = []
    for org in ("CITY", "NASCC"):
        a, b = P.EXTRACT_WIN[org]
        host, _, service, _ = P.ORGS[org]["remote"]
        for r in _log_rows(org, "auth"):
            if r["host"] == host and a <= ts(r["time_utc"]) < b:
                rows.append([r["time_utc"], service, r["account"], r["src_ip"], r["src_network"], r["result"], r["auth_method"], r["device"]])
    rows.sort(key=lambda r: r[0])
    print(f"account_logons_city_airstation: {write_csv(f'{P.AUDIT}/account_logons_city_airstation.csv', ['time_utc', 'service', 'account', 'src_ip', 'src_network', 'result', 'auth_method', 'device'], rows):,} rows")
    # the link-click reports hold every followed link in the same windows
    clicks = [[z(t), P.ORGS[org]["mx"][0], mb, url, h["ip"]] for org in ("CITY", "NASCC") for t, mb, h, url in P.story_clicks(org)]
    for org in ("CITY", "NASCC"):
        a, b = P.EXTRACT_WIN[org]
        clicks += [[z(t), P.ORGS[org]["mx"][0], mb, url, ip] for t, mb, ip, url, _m, _sd, _in in mail_clicks(org) if a <= t < b]
    clicks.sort()
    write_csv(f"{P.AUDIT}/mail_url_clicks_city_airstation.csv", ["time_utc", "gateway", "mailbox", "url_host", "client_ip"], clicks)
    a, b = P.EXTRACT_WIN["BRW"]
    import netmap
    bw = [[z(P.BRW_CLICK_T), P.ORGS["BRW"]["mx"][0], "remote.support@" + P.ORGS["BRW"]["domain"], "<" + hsh("bw") + "@" + P.BRW_LURE_DOM + ">", P.BRW_LURE_HOST, P.brw_ws(P.BRW_CLICK_PERSON)["ip"], netmap_label(P.BRW_LURE_DOM)]]
    bw += [[z(t), P.ORGS["BRW"]["mx"][0], mb, m_, url, ip, netmap.label(M.mta_of(sd, t))] for t, mb, ip, url, m_, sd, _in in mail_clicks("BRW") if a <= t < b]
    bw.sort()
    write_csv(f"{P.AUDIT}/mail_url_clicks_brightwake.csv", ["time_utc", "gateway", "mailbox", "message_id", "url_host", "client_ip", "sender_network"], bw)
    print(f"mail_url_clicks: {len(clicks)} city and air station, {len(bw)} vendor")


def netmap_label(sender_domain):
    """Network of the server a sender domain's mail comes from (the link-click report carries it)."""
    import netmap
    return netmap.label(M.mta_of(sender_domain, P.BRW_LURE_T))


def _stamp():
    h = hashlib.sha256()
    for f in ("gen_partner_it.py", "partner_it_model.py", "partner_it_mail.py"):
        h.update(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f), "rb").read())
    return h.hexdigest()[:16]


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "registry":
        reg = P.build_registry()
        print("registry: " + ", ".join(f"{o['org_id']} {len(o['hosts'])} hosts / {len(o['accounts'])} accounts" for o in reg["organisations"]))
        return 0
    if args[0] == "extracts":
        write_extracts()
        return 0
    if args[0] == "--all":
        ck = os.environ.get("PARTNER_IT_CKPT", "/tmp/partner_it_ckpt")
        os.makedirs(ck, exist_ok=True)
        if not ("--resume" in args and os.path.exists(os.path.join(ROOT, P.REG_REL))):
            P.build_registry()
        import time
        t_start, budget = time.time(), float(next((a.split("=")[1] for a in args if a.startswith("--budget=")), 120))
        for org in P.ORG_IDS:
            mark = os.path.join(ck, f"{org}.{_stamp()}.done")
            if "--resume" in args and os.path.exists(mark):
                continue
            if time.time() - t_start > budget:
                print("more to do; run again with --all --resume")
                return 3
            write_org(org)
            open(mark, "w").close()
        write_extracts()
        print("DONE")
        return 0
    if not os.path.exists(os.path.join(ROOT, P.REG_REL)):
        P.build_registry()
    write_org(args[0].upper(), args[1] if len(args) > 1 else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
