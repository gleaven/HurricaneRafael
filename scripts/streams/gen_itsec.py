"""IT and security logs for the utility and the aid portal (streams siem_alerts, zeek_logs,
host_audit_logs, portal_access_logs).

    python3 scripts/streams/gen_itsec.py [siem] [zeek] [audit] [portal]      (no argument = all)
    python3 scripts/streams/gen_itsec.py zeek:2027-09                       (one month of the sensor logs; run each month where a command may not run long)

Everything here is observation data: what a mail gateway, a remote-access gateway, a historian,
a network sensor, a SIEM and a web portal would have recorded. Records say who connected to
what, when, and what changed; they contain no instructions and no explanation of intent.

How the pieces agree (one source of truth per table, see the model section below):
  * the remote-access gateway's sessions, the historian's sessions, the alarm-suppression list,
    the file-integrity monitor, the configuration-change log and the SCADA command log are each
    built once (cached functions) and used by all three writers: the audit tables are those rows,
    the SIEM alerts about them are derived from them one to one, and the network sensor has the
    flow for each of them;
  * people appear only while itsec_shared.workday() has them at work (or on call and not away);
  * every record, ordinary or not, is drawn through the same functions and vocabularies.

Shared clock rule (same as the OT family, see ot_model.py): where canon gives an event to the
minute, the physical effect is at second 00 + int(sha256(event_id), 16) % 50; the log evidence
that precedes an effect (logon, session attach, write request) leads it by a few seconds.

Sampling of the network sensor: user-driven traffic and internal service chatter are a 1-in-200
sample. Recorded in full: periodic machine-to-internet series (agents, licence and update checks,
external time sync), mail transfers at the gateway that appear in the mail log, remote-access and
VPN sessions, and the flows behind alerts and audit records.

The writers live in itsec_siem.py, itsec_zeek.py (+ itsec_zeek_extra.py), itsec_audit.py and
itsec_portal.py; this module holds the constants, the helpers and the model.
"""
import csv
import functools
import hashlib
import os
import sys

from common import *            # noqa: F401,F403
import ot_model as M

NET = "05_other_sources/network_logs"
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
OPERATORS = [u for u in ENGINEERS if u["department"] == "System Operations"]
FIELD_ENG = [u for u in ENGINEERS if u["department"] != "System Operations"]
SOC = {"SOC-AN-01": "jperez", "SOC-AN-02": "tperez", "SOC-AN-03": "imorales"}
HOLIDAYS = {-8, 72, 73, 101, 102, 108, 109}     # local scenario days: Labor Day, Thanksgiving and the day after, 24, 25, 31 Dec, 1 Jan

WS04, JMP, HIST1, HISTDMZ, SCADA1, OPS02 = "GW-WS-IT-04", "GW-SYS-JMP-01", "GW-SRV-HIST-01", "GW-SRV-HIST-DMZ", "GW-SYS-SCADA-01", "GW-WS-OPS-02"
OT01, SIEMOT, PATCH, ECM, WAM = "GW-SRV-OT-01", "GW-SRV-SIEM-OT", "GW-SRV-PATCH-01", "GW-SRV-ECM-01", "GW-SRV-WAM-01"
BEACON_IP, BEACON_SNI = "104.21.88.43", "update-cdn.vantagesec-telemetry.net"
BEACON_FIRST, BEACON_LAST = ts("2027-08-31T03:17Z") + 12, ts("2027-10-12T10:04Z") + 37
# canon correction: the lure reaches the mailbox the morning before the first beacon
LURE_T = ts("2027-08-30T13:14Z") + 9
AV_OFF_T = ts("2027-08-30T13:21Z") + 44
DNS_Q_T = ts("2027-08-30T13:23Z") + 2
RULE_CREATED = ts("2027-08-19T11:34Z") + 20
RULE_REMOVED = ts("2027-10-18T15:20Z") + 26
WL_0117 = ts("2027-08-31T14:22Z") + 48
STORM_MODE_ON, STORM_MODE_OFF = ts("2027-09-14T06:14Z") + 5, ts("2027-09-18T14:00Z") + 41
ISOLATE = M.T["isolate"]
WS04_REMOVED = ISOLATE                       # the workstation is unplugged when the network is cut and never returns
FREEZE_ON, FREEZE_OFF = ts("2027-09-10T21:00Z"), ts("2027-10-25T15:00Z")
WS04_USER = next((u for u in USERS if WS04 in u.get("normal_hosts", [])), USERS[10])
VELA = next(u for u in USERS if u["username"] == "rvela")


def z(t):
    return iso(t)


def hsh(*k, n=16):
    return hashlib.sha256("|".join(map(str, k)).encode()).hexdigest()[:n]


def frac(*k):
    """A fixed fraction in [0, 1) for a key (sub-second parts and small offsets of records whose minute canon fixes)."""
    return int(hsh(*k, n=8), 16) / 16 ** 8


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
    s["bytes_in"] = int(9000 + s["dur"] * (60 + int(hashlib.sha256(f"bi|{s['n']}".encode()).hexdigest()[:6], 16) % 340)
                        + int(hashlib.sha256(f"bi2|{s['n']}".encode()).hexdigest()[:6], 16) % 1931)   # what the client sent: keystrokes and pointer
    _kk = int(hashlib.sha256(f"gwlead|{s['n']}".encode()).hexdigest()[:8], 16)
    s["lead"], s["tail"] = 5 + _kk % 40, 8 - (_kk >> 8) % 50          # the gateway's login precedes, and its logout follows, by a varying few seconds
    s["hist_id"] = None
SESSIONS[0]["hist_id"], SESSIONS[-1]["hist_id"] = "HIST-20270907-00441", "HIST-20271002-00917"


def work_factor(t):
    """Share of normal office activity at epoch t (hour of day, weekend, public holiday, storm, evacuation)."""
    l = local_dt(t)
    f = 1.0 if 7 <= l.hour < 18 else (0.25 if 5 <= l.hour < 22 else 0.06)
    if l.weekday() >= 5:
        f *= 0.25
    elif day_of(t) in HOLIDAYS:
        f *= 0.2
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


def day_utc(t):
    return int((t - D0_EPOCH) // DAY)


FIRST_D, LAST_D = day_utc(SPAN_START), day_utc(SPAN_END - 1)


def shared():
    """The shared presence model (imported late: it imports this module)."""
    import itsec_shared
    return itsec_shared


CORP = [h for h in HOSTS if h["device_type"] in ("workstation", "laptop") and h["ip"].startswith("10.14.")]
CORP_NAMES = {h["hostname"] for h in CORP}
WIN_CORP = [h for h in HOSTS if str(h.get("os", "")).startswith("Windows") and h["ip"].startswith(("10.14.", "172.20."))]
OT_CONSOLES = [h["hostname"] for h in HOSTS if h["device_type"] in ("operator workstation", "engineering workstation")]
OPS_CONSOLES = [h["hostname"] for h in HOSTS if h["device_type"] == "operator workstation"]
ENG_WS = [h["hostname"] for h in HOSTS if h["device_type"] == "engineering workstation"]
IT_ADMIN = [h for h in CORP if "IT Infrastructure" in h.get("role", "")] or CORP[:6]
RTUS = [h["hostname"] for h in HOSTS if h["device_type"] == "rtu"]
SVC = [a for a in H["service_accounts"] if a.get("normal_hosts") and a["normal_hosts"][0] in BYNAME and not a["account"].endswith("_ext")
       and "support" not in a["account"] and "mgmt" not in a["account"] and str(BYNAME[a["normal_hosts"][0]].get("os", "")).startswith("Windows")]
_UNCAT_A = ["bright", "north", "quick", "blue", "prime", "metro", "coast", "delta", "happy", "smart", "open", "easy", "star", "green", "rapid", "true"]
_UNCAT_B = ["deals", "media", "tools", "labs", "hub", "zone", "cloud", "apps", "links", "press", "forum", "mart", "pixel", "stream", "works", "notes"]
_UNCAT_TLD = ["com", "net", "org", "info", "io", "co", "site", "online", "xyz", "top"]


def uncat_name(g):
    """A name the DNS filter has no category for (new or little-known sites)."""
    first = str(g.choice(['www', 'cdn', 'app', 'img', 'static', 'api', 'm', 'www', 'cdn', 'app', 'api', 'cdn-1', 'app-prod', 'img-cdn', 'static-web', 'api-v2', 'dl-cdn', 'update-cdn']))
    a, b = _UNCAT_A[int(g.integers(len(_UNCAT_A)))], _UNCAT_B[int(g.integers(len(_UNCAT_B)))]
    return (f"{first}.{a}{'-' if (len(a) * 7 + len(b)) % 4 == 0 else ''}{b}"
            f"{int(g.integers(2, 99)) if g.random() < 0.4 else ''}.{_UNCAT_TLD[int(g.integers(len(_UNCAT_TLD)))]}")


# ---- outside names and addresses -------------------------------------------------------------------------
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
# two vendors keep part of their public content in the same hosting range as the address the first flagged-address alert named
SITE_IPS["assets.meridiancontrols.com"] = ["104.21.88.17", "104.21.88.201"]
SITE_IPS["downloads.vantage-security.com"] = ["104.21.88.112"]
SITE_IPS["status.relaytech-support.net"] = ["104.21.88.66"]
# first labels are as varied as on real sites: about a fifth carry a hyphen (regional edges, versions, update channels)
_HY = {"www": ["www-2", "web-portal", "www-east"], "api": ["api-v2", "rest-api", "api-gw"], "cdn": ["edge-cdn", "cdn-east", "img-cdn", "update-cdn", "dl-cdn"],
       "login": ["sso-login", "auth-prod"], "static": ["static-assets", "web-static", "update-cdn"]}
for _k in sorted(SITE_IPS):
    _l, _rest = _k.split(".", 1)
    _hv = int(hashlib.sha256(("hy|" + _k).encode()).hexdigest()[:6], 16)
    if _l in _HY and (_hv % 9 < 2 or ("-" not in _rest and _hv % 9 < 4)):
        SITE_IPS[f"{_HY[_l][(_hv >> 4) % len(_HY[_l])]}.{_rest}"] = SITE_IPS.pop(_k)
SITES = sorted(SITE_IPS)
STATES = [("SF", "ShADadFf", 0.935), ("S0", "S", 0.02), ("REJ", "Sr", 0.012), ("RSTO", "ShADaR", 0.014), ("RSTR", "ShADdr", 0.008), ("SH", "ShADF", 0.006), ("OTH", "Aa", 0.005)]

# TLS as the sensor sees it: protocol version and cipher suite belong to the server name
_TLS13 = ["TLS_AES_128_GCM_SHA256"] * 11 + ["TLS_AES_256_GCM_SHA384"] * 7 + ["TLS_CHACHA20_POLY1305_SHA256"] * 2
_TLS12 = ["TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384"] * 8 + ["TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256"] * 7 + ["TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256"] * 3 + \
    ["TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256"] * 2
_TLS_SALT = "tls7"


def tls_for(name):
    """(version, cipher) a server name negotiates with the utility's clients. Appliances and the utility's own
    services still speak TLS 1.2; four public sites in five speak 1.3."""
    own = name.endswith("cbpwa.example")
    k = int(hsh(_TLS_SALT, name, n=6), 16)
    if own or k % 5 == 0:
        return "TLSv12", _TLS12[(k // 5) % len(_TLS12)]
    return "TLSv13", _TLS13[(k // 5) % len(_TLS13)]


def ssl_row(t, c, name, resumed=None):
    """ssl.log row for connection row c."""
    ver, ciph = tls_for(name)
    res = (frac("res", c[1]) < 0.2) if resumed is None else resumed
    if int(c[10]) < 1200 and c[11] == "SF":             # too small for a certificate exchange: an abbreviated handshake
        res = True
    return [f"{t:.6f}", c[1], c[2], c[3], c[4], c[5], ver, ciph, name, "T" if res else "F", "T"]


def home_ip(g):
    """A residential-looking address for staff working from home."""
    return f"{_HOME[int(g.integers(len(_HOME)))]}.{int(g.integers(1, 250))}.{int(g.integers(1, 250))}.{int(g.integers(2, 250))}"


_HOME_NETS = [7018, 20057, 11427, 22773]


def home_net(username):
    """The access provider of a person's home connection (a network label)."""
    return f"AS-{_HOME_NETS[int(hsh('homenet', username, n=4), 16) % len(_HOME_NETS)]}"


def home_addr(username, t):
    """The address of a person's home connection at time t: the same for months, re-assigned by the provider
    zero to three times in the span."""
    n = int(hsh("homechg", username, n=2), 16) % 4
    k = sum(1 for i in range(n) if SPAN_START + frac("homecut", username, i) * (SPAN_END - SPAN_START) <= t)
    h = hsh("home", username, k, n=10)
    pfx = _HOME[(_HOME_NETS.index(int(home_net(username)[3:])) * 4 + int(h[:2], 16) % 4) % len(_HOME)]
    return f"{pfx}.{1 + int(h[2:4], 16) % 249}.{1 + int(h[4:6], 16) % 249}.{2 + int(h[6:8], 16) % 248}"


def away_addr(username, key):
    """An address used once while travelling (hotel, relatives, a mobile hotspot)."""
    h = hsh("trav", username, key, n=10)
    return f"{_HOME[int(h[:2], 16) % len(_HOME)]}.{1 + int(h[2:4], 16) % 249}.{1 + int(h[4:6], 16) % 249}.{2 + int(h[6:8], 16) % 248}"


_OUI = ["3c:52:82", "f4:8e:38", "a4:bb:6d", "00:1a:4b", "d8:9e:f3", "54:bf:64", "8c:ec:4b", "b0:7b:25", "e4:54:e8", "98:90:96", "28:f1:0e", "c8:5b:76"]
_OUI_HOME = _OUI + ["70:85:c2", "04:d4:c4", "9c:b6:d0", "f0:18:98", "ac:de:48", "38:f9:d3", "dc:a6:32", "00:e0:4c"]


def mac_of(hostname):
    """Adapter address: the fleet was bought in a few batches, so prefixes repeat."""
    x = hsh("mac", hostname, n=12)
    return _OUI[int(x[:4], 16) % len(_OUI)] + ":" + ":".join(x[i:i + 2] for i in range(4, 10, 2))


_B32 = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LAPTOP_OF = {h["primary_user"]: h["hostname"] for h in HOSTS if h["device_type"] == "laptop" and h.get("primary_user")}


@functools.lru_cache(maxsize=None)
def remote_devices(username):
    """The one or two devices a member of staff uses on the employee VPN: [(host name, MAC)]. The first is their
    registry laptop where they have one, otherwise a home computer; about a third have a second device at home."""
    out = []
    if username in LAPTOP_OF:
        out.append((LAPTOP_OF[username], mac_of(LAPTOP_OF[username])))

    def home(kind, k):
        x = hashlib.sha256(f"homedev|{username}|{k}".encode()).digest()
        return (f"{kind}-{''.join(_B32[b % 32] for b in x[:7])}", _OUI_HOME[x[8] % len(_OUI_HOME)] + ":" + ":".join(f"{b:02x}" for b in x[9:12]))
    if not out:
        out.append(home("DESKTOP", 0))
    if int(hsh("dev2", username, n=4), 16) % 100 < 34:
        out.append(home("LAPTOP" if int(hsh("dev2k", username, n=2), 16) % 2 else "DESKTOP", 1))
    return out


def in_normal_hours(u, t):
    """Inside the hours the directory lists for an office worker (shift staff: when on shift)."""
    if u.get("normal_hours", "").startswith("rotating"):
        return shared().on_shift(u, t)
    l = local_dt(t)
    last = 5 if u.get("normal_hours", "").startswith("Mon-Sat") else 4
    return l.weekday() <= last and day_of(t) not in HOLIDAYS and 7 <= l.hour + l.minute / 60 < (19 if last == 5 else 17.5)


@functools.lru_cache(maxsize=None)
def vpn_sessions():
    """Sessions on the employee VPN, in order of connection: dicts id, user, t, dur, src_ip, src_network, device, mac,
    pool_ip, bytes_in, bytes_out, new_location, rdp (None or dict t, dur, host, alert).
    People, not traffic, make them: staff working from home on a weekday away from the office (many more around the
    storm), evening check-ins after a day at work, the odd weekend or day-off session. Each person connects from their
    own home address (or, now and then, from somewhere else) on their own one or two devices; people with a desktop
    in the office often open a remote-desktop session to it."""
    S = shared()
    raw = []
    for d in range(day_of(SPAN_START) + 1, day_of(SPAN_END - 1) + 1):
        noon = local_ts(d, "12:00")
        wd = local_dt(noon).weekday()
        for u in USERS:
            name = u["username"]
            lv = S.LEAVE.get(name)
            if (lv and lv[0] - DAY <= noon <= lv[1] + DAY) or not u.get("normal_hosts"):
                continue
            rot = u.get("normal_hours", "").startswith("rotating")
            w = S.workday(u, d)
            prop, k = frac("remote", name), frac("vpnday", name, d)
            ss = []
            if not rot and w is None and wd < 5 and d not in HOLIDAYS:
                if k < (0.15 + 0.6 * prop) * (0.45 if 0 <= d < 3 else 1.0):          # working from home
                    a = local_ts(d, "07:00") + frac("vpns", name, d) * 2.5 * 3600
                    for i in range(1 + (frac("vpnn", name, d) < 0.45) + (frac("vpnn2", name, d) < 0.12)):
                        dur = 1800 + frac("vpnd", name, d, i) ** 1.5 * 4.5 * 3600
                        ss.append((a, dur))
                        a += dur + 600 + frac("vpng", name, d, i) * 5400
            elif not rot and w is not None:
                if k < 0.02 + 0.10 * prop:                                           # evening check-in
                    ss.append((w[1] + 3600 + frac("vpne", name, d) * 4.5 * 3600, 420 + frac("vpned", name, d) ** 2 * 5400))
            elif w is None and k < (0.015 + 0.04 * prop if rot else 0.01 + 0.05 * prop):   # a day off
                ss.append((local_ts(d, "09:00") + frac("vpns", name, d) * 11 * 3600, 300 + frac("vpned", name, d) ** 2 * 3600))
            for a, dur in ss:
                raw.append((a + frac("vpnf", name, a), dur, u))
    raw.sort(key=lambda x: (x[0], x[2]["username"]))
    out, in_use, seen = [], {}, set()
    for i, (t, dur, u) in enumerate(raw):
        name = u["username"]
        for ipx in [x for x, v in in_use.items() if v <= t]:
            del in_use[ipx]
        k0 = int(hsh("vpnpool", name, int(t), n=6), 16) % 200
        pool = next(f"10.14.250.{10 + (k0 + j) % 200}" for j in range(200) if f"10.14.250.{10 + (k0 + j) % 200}" not in in_use)
        in_use[pool] = t + dur + 2
        trav = frac("vpntrav", name, int(t)) < 0.03
        src = away_addr(name, int(t)) if trav else home_addr(name, t)
        devs = remote_devices(name)
        dev = devs[0] if (len(devs) == 1 or frac("vpndev", name, int(t)) < 0.78) else devs[1]
        first_home = home_addr(name, SPAN_START)
        new = (name, src) not in seen and src != first_home
        seen.add((name, src))
        ws = u["normal_hosts"][0]
        rdp = None
        if dev[0] not in BYNAME and ws in CORP_NAMES and BYNAME[ws]["device_type"] == "workstation" and ws != WS04 and dur > 600 and frac("vpnrdp", name, int(t)) < 0.55:
            rt = int(t + 40 + frac("vpnrt", name, int(t)) * 200)
            rdp = dict(t=rt, dur=max(120.0, dur - (rt - t) - 20 - frac("vpnre", name, int(t)) * 0.3 * dur), host=ws, alert=not in_normal_hours(u, rt))
        gb = hsh("vpnb", name, int(t), n=12)
        out.append(dict(id=f"VPN-{i + 1:05d}", user=name, t=t, dur=dur, src_ip=src, src_network=home_net(name) if not trav else f"AS-{_HOME_NETS[int(gb[:2], 16) % 4]}",
                        device=dev[0], mac=dev[1], pool_ip=pool, bytes_in=int(6000 + dur * (300 + int(gb[2:6], 16) % 1400)), bytes_out=int(9000 + dur * (900 + int(gb[6:10], 16) % 6000)),
                        new_location=new, rdp=rdp))
    return out


# ---- browsers ------------------------------------------------------------------------------------------------
_BROWSER_T0 = ts("2027-07-06T00:00Z")


def browsers_of(host):
    """Browsers installed on a workstation, the one its user prefers first. Every machine has the system browser."""
    k = int(hsh("browsers", host, n=6), 16)
    out = ["edge"]
    if k % 100 < 62:
        out.append("chrome")
    if (k >> 8) % 100 < 14:
        out.append("firefox")
    if len(out) > 1 and (k >> 16) % 100 < 70:
        out = out[1:] + out[:1]
    return out


def browser_version(host, fam, t):
    """Major version of a browser on a machine at time t: a new one about every four weeks, each machine a few days behind."""
    lag = int(hsh("brlag", host, fam, n=4), 16) % (9 * DAY)
    step = max(0, int((t - _BROWSER_T0 - lag) // (28 * DAY)))
    if fam == "firefox":
        return 128 if int(hsh("fxesr", host, n=2), 16) % 5 < 2 else 140 + step
    return 137 + step


def browser_ua(host, t, key=""):
    """User-agent string of the browser a logged-on person uses on this machine at time t."""
    fams = browsers_of(host)
    fam = fams[0] if (len(fams) == 1 or frac("brpick", host, key) < 0.85) else fams[1 + int(frac("brpick2", host, key) * (len(fams) - 1))]
    v = browser_version(host, fam, t)
    if fam == "firefox":
        return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{v}.0) Gecko/20100101 Firefox/{v}.0"
    base = f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
    return base + (f" Edg/{v}.0.0.0" if fam == "edge" else "")


def boundary_open(t):
    """False while the OT network is cut off from everything else (canon isolation window)."""
    return not (ISOLATE <= t < M.T["reconnect"])


def eng_ws(e):
    """The engineering or operator workstation inside the control network a person works from."""
    for h in reversed(e.get("normal_hosts", [])):
        if h in ENG_WS or h in OPS_CONSOLES:
            return h
    return ENG_WS[sum(map(ord, e["username"])) % len(ENG_WS)]


def inside_host(e, t):
    return eng_ws(e)


def at_work(pool, t, g, tries=24):
    """Someone from pool who is at work at t (None if nobody is)."""
    S = shared()
    for _ in range(tries):
        u = pool[int(g.integers(len(pool)))]
        if S.on_shift(u, t):
            return u
    return None


def on_call(pool, t, g, tries=24):
    """Someone from pool who is not away at t (leave, absent that weekday)."""
    S = shared()
    for _ in range(tries):
        u = pool[int(g.integers(len(pool)))]
        if not S.away(u, t):
            return u
    return None


def uid(*k):
    return "C" + hsh(*k, n=17)


def conn(t, o, op, r, rp, proto, svc, dur, ob, rb, state="SF", hist="ShADadFf"):
    """conn.log row. Packet counts follow the payload: a TCP connection has its handshake and teardown plus about one
    segment per 1,400 bytes and the acknowledgements; UDP and ICMP have one packet per message."""
    ob, rb = int(ob), int(rb)
    lo = "T" if o.startswith(("10.", "172.20.")) else "F"
    lr = "T" if r.startswith(("10.", "172.20.")) else "F"
    k = int(hsh("pk", t, o, op, n=4), 16)
    if proto != "tcp":
        opk = max(1, -(-ob // 1200))
        rpk = max(1, -(-rb // 1200)) if rb else 0
        return [f"{t:.6f}", uid(t, o, op, r, rp), o, op, r, rp, proto, svc, f"{dur:.6f}", ob, rb, state, lo, lr, 0, hist, opk, ob + opk * 28, rpk, rb + rpk * 28]
    opt = 12 if (k >> 3) % 5 < 3 else 0                 # TCP timestamps on most stacks
    syn = 8 + 4 * ((k >> 6) % 4)                        # options on the SYN
    if state == "S0":
        dur, ob, rb, opk, rpk = 0.0, 0, 0, 1 + k % 3, 0
        return [f"{t:.6f}", uid(t, o, op, r, rp), o, op, r, rp, proto, svc, f"{dur:.6f}", ob, rb, state, lo, lr, 0, hist, opk, opk * (40 + syn + opt), 0, 0]
    if state == "REJ":
        dur, ob, rb, opk, rpk = 0.0, 0, 0, 1, 1
        return [f"{t:.6f}", uid(t, o, op, r, rp), o, op, r, rp, proto, svc, f"{dur:.6f}", ob, rb, state, lo, lr, 0, hist, 1, 40 + syn + opt, 1, 40]
    if svc == "ssl" and state == "SF" and rb >= 1200:   # a full handshake: hello, certificate chain, key exchange
        ob, rb = max(ob, 390 + (k >> 4) % 240), max(rb, 2650 + (k >> 2) % 2100)
    seg_o, seg_r = -(-ob // 1400), -(-rb // 1400)
    opk = 3 + seg_o + (seg_r + 1) // 2 + k % 2
    rpk = 2 + seg_r + (seg_o + 1) // 2 + (k >> 1) % 2
    if state == "SF" and hist == "ShADadFf":
        hist = _HIST[(k >> 5) % len(_HIST)] if rb else "ShADaFf"
        if "t" in hist or "T" in hist:
            opk += 1
    return [f"{t:.6f}", uid(t, o, op, r, rp), o, op, r, rp, proto, svc, f"{dur:.6f}", ob, rb, state, lo, lr, 0, hist, opk, ob + opk * (40 + opt) + syn, rpk, rb + rpk * (40 + opt) + syn]


_HIST = ["ShADadFf"] * 9 + ["ShADadfF"] * 4 + ["ShADdaFf"] * 3 + ["ShAdDaFf"] * 2 + ["ShADadFfR", "ShADadtFf", "ShADadTFf", "ShADdAaFf", "ShADadFfr", "ShADadGFf"]


def dns_row(t, o, r, q, ans, g):
    """One dns.log row. Its uid is the uid of the UDP/53 connection that carried it (see dns_conn)."""
    op = 49152 + int(g.integers(0, 16000))
    return [f"{t:.6f}", uid(t, o, op, r, 53), o, op, r, 53, "udp", int(g.integers(1, 65000)), q, "C_INTERNET", "A", "NOERROR", "F", "T", "T", ans, f"{int(g.integers(60, 3600))}.000000"]


def dns_conn(d):
    """The conn.log row for a dns.log row (same uid, same endpoints). Sizes follow the name and the answer."""
    t = float(d[0])
    k = int(hsh("dq", d[1], n=6), 16)
    q = 17 + len(d[8]) + 1
    a = q + (16 * (1 + d[15].count(",")) if d[15] not in ("-", "") else 0) + (k % 3) * 12
    c = conn(t, d[2], d[3], d[4], 53, "udp", "dns", 0.0004 + (k % 9000) / 1e6 * (1 + 20 * ((k >> 8) % 50 == 0)), q, a, "SF", "Dd")
    c[1] = d[1]
    return c


def pick_state(g):
    r, acc = g.random(), 0.0
    for st, hist, p in STATES:
        acc += p
        if r < acc:
            return st, hist
    return "SF", "ShADadFf"


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


# ==========================================================================================================
# The model: one source of truth per table. Every writer (audit table, SIEM alert, network flow) uses these.
# ==========================================================================================================
@functools.lru_cache(maxsize=None)
def change_records():
    """Approved OT changes in the change system, in order of creation: [(created, id, summary, owner)]. Numbers are issued
    in sequence (other departments take some). None is approved while the storm-preparation freeze is on."""
    g = rng("host_audit", "chg_pool")
    summaries = ["firmware update, substation switch", "historian disk expansion", "HMI display revision", "firewall rule review", "RTU battery replacement", "chlorine analyser calibration constants",
                 "SCADA point database update", "relay settings revision", "pump controller tuning", "tank level transmitter replacement", "operator console patching", "alarm list housekeeping",
                 "remote diagnostics, water-system controllers", "historian tag review", "protection settings verification", "engineering file server clean-up", "setpoint review, booster stations",
                 "operator display corrections", "communications path test", "trend report for planning"]
    out, n = [], 610
    for d in range(FIRST_D - 16, LAST_D + 1):
        l = local_dt(local_ts(d, "12:00"))
        for _ in range(int(g.poisson(2.7 if (l.weekday() < 5 and d not in HOLIDAYS) else 0.15))):
            a = local_ts(d, f"{int(g.integers(7, 17)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
            e = FIELD_ENG[int(g.integers(len(FIELD_ENG)))] if d < FIRST_D else at_work(FIELD_ENG, a, g)
            sm, gap = summaries[int(g.integers(len(summaries)))], int(g.integers(1, 4))
            if e and not (FREEZE_ON - 3 * 3600 <= a < FREEZE_OFF):
                out.append([a, None, sm, e["username"]])
    out.sort(key=lambda r: r[0])
    for r in out:
        n += 1 + (int(hsh("chgn", r[0], n=4), 16) % 3 == 0) + (int(hsh("chgn2", r[0], n=4), 16) % 11 == 0)
        r[1] = f"CHG-27-{n:04d}"
    return [tuple(r) for r in out]


def cite_chg(t, *key):
    """A change ticket somebody would cite for work at time t: one approved in the two weeks before (empty if there is none)."""
    c = [r[1] for r in change_records() if t - 14 * DAY <= r[0] <= t - 3600]
    return c[int(hsh("cite", t, *key, n=6), 16) % len(c)] if c else ""


@functools.lru_cache(maxsize=None)
def _work_orders():
    out = []
    p = os.path.join(ROOT, "05_other_sources/maintenance/work_orders.csv")
    if os.path.exists(p):
        with open(p, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                a = ts(r["reported_date"])
                b = max([ts(r[k]) for k in ("actual_finish", "status_date", "sched_finish") if r.get(k)] or [a + 20 * DAY])
                if r.get("org_id") == "CBPWA" and r["wonum"].startswith("WO-"):
                    out.append((a, b, r["wonum"]))
    return sorted(out)


def cite_wo(t, *key):
    """A work order open at time t in the maintenance system (empty if there is none)."""
    c = [w for a, b, w in _work_orders() if a <= t <= b + 2 * DAY]
    return c[int(hsh("citewo", t, *key, n=6), 16) % len(c)] if c else ""


SUB_RTU = ["GW-SYS-RTU-01", "GW-SYS-RTU-02", "GW-SYS-RTU-03", "GW-SYS-RTU-04", "GW-SYS-RTU-05"]
WATER_RTU = ["GW-SYS-RTU-UTL1", "GW-SYS-RTU-WTR1", "GW-SYS-RTU-WTR2", "GW-SYS-RTU-WTR3"]
DCS = ["GW-WTP-DCS-01"]
PAR_SUB = [("recloser shots", "3", "2"), ("clock sync source", "GPS-A", "GPS-B"), ("transformer LTC band (V)", "2.0", "1.5"), ("relay 51 time dial", "2.0", "2.5"),
           ("relay 27-UV time delay (s)", "2.0", "1.5"), ("relay 50 instantaneous pickup (A)", "4800", "5200"), ("feeder CT ratio", "600:5", "800:5"),
           ("relay 27-UV pickup (pu)", "0.90", "0.88"), ("relays overcurrent trip (A)", "1000", "1200"), ("breaker failure timer (cycles)", "12", "10")]
PAR_WATER = [("tank high-level alarm (ft)", "31.5", "31.0"), ("discharge pressure setpoint (psi)", "82", "85"), ("booster discharge setpoint (psi)", "70", "72"),
             ("pump start level (ft)", "18.0", "19.5"), ("clock sync source", "GPS-A", "GPS-B"), ("low suction cut-out (psi)", "8", "10")]
PAR_DCS = [("chlorine residual alarm low (mg/L)", "0.5", "0.6"), ("filter backwash interval (h)", "48", "36"), ("turbidity alarm high (NTU)", "0.30", "0.25"),
           ("clearwell level setpoint (ft)", "14.0", "14.5")]
RD_HOSTS = (OPS02, "GW-SYS-SCADA-02", "GW-WTP-HMI-01", "GW-WS-ENG-03")


def _pars(dev):
    return PAR_SUB if dev in SUB_RTU else (PAR_DCS if dev in DCS else PAR_WATER)


def _par_name(dev, par, key):
    """The parameter as the device's own table names it (relay group of that substation, pump of that station)."""
    if par == "relays overcurrent trip (A)":
        return f"relays R-0{dev[-1]}A/B/C overcurrent trip (A)"
    if par == "discharge pressure setpoint (psi)" and dev == "GW-SYS-RTU-UTL1":
        return f"P-{1 + int(hsh('pump', key, n=2), 16) % 4} discharge pressure setpoint (psi)"
    return par


@functools.lru_cache(maxsize=None)
def cfg_changes():
    """Setting changes on field devices: dicts t, device, parameter, old, new, how, account, source, ticket, kind.
    Ordinary approved changes stop at the storm-preparation freeze and resume when it is lifted; in between there are
    only emergency changes made at the device during restoration."""
    g = rng("host_audit", "cfg2")
    out = []
    devs = SUB_RTU + WATER_RTU + DCS
    for i in range(158):
        d = int(g.integers(-58, 118))
        a = local_ts(d, f"{int(g.integers(7, 18)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
        e = at_work(FIELD_ENG, a, g)
        dev = devs[int(g.integers(len(devs)))]
        par, old, new = _pars(dev)[int(g.integers(len(_pars(dev))))]
        if i >= 150:                                    # a few more of the kinds every station sees in half a year
            dev, par, old, new = [("GW-SYS-RTU-02", "relays overcurrent trip (A)", "1000", "1200"), ("GW-SYS-RTU-UTL1", "discharge pressure setpoint (psi)", "82", "85"),
                                  ("GW-SYS-RTU-03", "relays overcurrent trip (A)", "1200", "1000"), ("GW-SYS-RTU-WTR3", "booster discharge setpoint (psi)", "70", "72"),
                                  ("GW-SYS-RTU-UTL1", "discharge pressure setpoint (psi)", "85", "82"), ("GW-SYS-RTU-02", "relays overcurrent trip (A)", "1200", "1000"),
                                  ("GW-SYS-RTU-01", "relay 27-UV pickup (pu)", "0.90", "0.88"), ("GW-SYS-RTU-UTL1", "discharge pressure setpoint (psi)", "85", "88")][i - 150]
        par = _par_name(dev, par, i if i < 150 else ("P3", i))
        if i in (151, 154, 157):
            par = "P-3 discharge pressure setpoint (psi)"
        how = str(g.choice(["remote write", "local panel", "file replaced", "remote write"]))
        via_jmp, tk, age = g.random() < 0.5, g.random(), int(g.integers(20, 200))
        if not e or FREEZE_ON - 2 * 3600 <= a < FREEZE_OFF:
            continue
        if how == "file replaced" and not (dev in SUB_RTU and int(hsh("frk", i, n=2), 16) % 2 == 0):   # a settings file pushed whole is logged either as the file or as the setting it changed
            par, old, new = f"configuration file {dev.split('-')[-1].lower()}_active.cfg", f"last_modified {z(a - age * DAY - 3711 * (i % 17))}", f"last_modified {z(a)}"
        out.append(dict(t=a, device=dev, parameter=par, old=old, new=new, how=how, account=e["ot_account"], user=e["username"],
                        source="local panel" if how == "local panel" else (JMP if via_jmp else eng_ws(e)),
                        ticket=cite_chg(a, "cfg", i) if tk < 0.85 else "", kind="ordinary"))
    # commissioning values recorded in mid-August (the audits later compare against them)
    for k, dev in enumerate(SUB_RTU):
        a = ts("2027-08-15T15:10Z") + k * 1740 + (int(frac("comm", dev) * 600) if k else 0)
        out.append(dict(t=a, device=dev, parameter="relay 27-UV pickup (pu)", old="", new="0.88", how="local panel", account="GW-ENG-VELA", user="rvela",
                        source="local panel", ticket=cite_chg(ts("2027-08-15T15:10Z"), "commissioning"), kind="ordinary"))
    # emergency changes at the device while the freeze is on (restoration)
    n_em = 0
    for i in range(40):
        d = int(g.integers(1, 40))
        a = local_ts(d, f"{int(g.integers(6, 20)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
        e = on_call(FIELD_ENG, a, g)
        dev = devs[int(g.integers(len(devs)))]
        par, old, new = _pars(dev)[int(g.integers(len(_pars(dev))))]
        par = _par_name(dev, par, ("em", i))
        tk = int(g.integers(100, 400))
        if not e or not (FREEZE_ON <= a < FREEZE_OFF) or n_em >= 16:
            continue
        n_em += 1
        out.append(dict(t=a, device=dev, parameter=par, old=old, new=new, how="local panel", account=e["ot_account"], user=e["username"], source="local panel",
                        ticket="EMR", kind="emergency"))
    em = sorted([c for c in out if c["kind"] == "emergency"], key=lambda c: c["t"])
    for k, c in enumerate(em):                           # emergency tickets are numbered as they are raised
        c["ticket"] = f"EMR-27-{101 + 2 * k + int(hsh('emr', c['t'], n=2), 16) % 2:03d}"

    def st(key, off, dev, par, old, new, how):
        return dict(t=M.T[key] + off, device=dev, parameter=par, old=old, new=new, how=how, account="GW-ENG-VELA", user=None, source=JMP, ticket="", kind="session")

    out += [st("uv_thr_sub1", 0, "GW-SYS-RTU-01", "relay 27-UV pickup (pu)", "0.88", "0.94", "remote write"),
            st("cfg_sub2", 41, "GW-SYS-RTU-02", "relays R-02A/B/C overcurrent trip (A)", "1200", "2400", "file replaced"),
            st("cfg_rtu4", 0, "GW-SYS-RTU-04", "configuration file 04_active.cfg", "last_modified 2027-08-15T16:02:11Z", f"last_modified {z(M.T['cfg_rtu4'])}", "file replaced"),
            st("p3_sp", 0, "GW-SYS-RTU-UTL1", "P-3 discharge pressure setpoint (psi)", "85", "68", "remote write"),
            st("bstr_sp", 0, "GW-SYS-RTU-WTR3", "booster discharge setpoint (psi)", "72", "54", "remote write")]
    e0, e1 = FIELD_ENG[0], FIELD_ENG[1]

    def rs(key, dev, par, old, new, e, src):
        return dict(t=M.T[key], device=dev, parameter=par, old=old, new=new, how="local panel", account=e["ot_account"], user=e["username"], source=src,
                    ticket="SI-2027-CC-001", kind="restore")

    out += [rs("p3_restore", "GW-SYS-RTU-UTL1", "P-3 discharge pressure setpoint (psi)", "68", "85", e0, "GW-WTP-HMI-01"),
            rs("bstr_restore", "GW-SYS-RTU-WTR3", "booster discharge setpoint (psi)", "54", "72", e0, "local panel"),
            rs("relay_reset_sub1", "GW-SYS-RTU-01", "relay 27-UV pickup (pu)", "0.94", "0.88", e1, "local panel"),
            rs("relay_reset_sub2", "GW-SYS-RTU-02", "relays R-02A/B/C overcurrent trip (A)", "2400", "1200", e1, "local panel")]
    return sorted(out, key=lambda x: x["t"])


def legit_config_changes():
    """(old interface) ordinary changes as tuples."""
    return [(c["t"], c["device"], c["parameter"], c["old"], c["new"], c["how"], c["account"], c["source"], c["ticket"]) for c in cfg_changes() if c["kind"] == "ordinary"]


@functools.lru_cache(maxsize=None)
def gateway_sessions():
    """Sessions on the remote-access gateway, in order of login: dicts id, account, user, src_ip, src_network, src_country,
    login, logout, dur, bytes_out, bytes_in, auth, targets (list), ticket, kind."""
    g = rng("host_audit", "gw2")
    rows = []
    nets = [7018, 20057, 11427, 22773]
    hostile = [(s["start"] - 1800, s["start"] + s["dur"] + 1800) for s in SESSIONS]

    def clash(a, b):
        return any(a < y and b > x for x, y in hostile)

    def add(kind, account, user, src, net, a, dur, targets, ticket, auth, bo, bi, cc="US"):
        if not (boundary_open(a) and boundary_open(a + dur)):
            return
        kb = int(hsh("gwb", account, int(a), n=8), 16)   # the gateway forwards screens out and input in
        bo, bi = 40000 + dur * (900 + kb % 5200) + (kb >> 5) % 2713, 9000 + dur * (60 + (kb >> 16) % 340) + (kb >> 9) % 1931
        rows.append(dict(kind=kind, account=account, user=user, src_ip=src, src_network=net, src_country=cc, login=int(a), logout=int(a + dur), dur=int(dur),
                         bytes_out=int(bo), bytes_in=int(bi), auth=auth, targets=list(targets), ticket=ticket))

    pool = [HIST1, "GW-WS-ENG-03", OT01, "GW-SYS-SCADA-02", "GW-WTP-HMI-01", "GW-SYS-RTU-03", "GW-SYS-RTU-05", OPS02, SCADA1]
    for d in range(FIRST_D, LAST_D + 1):
        t0 = D0_EPOCH + d * DAY
        l = local_dt(t0 + 43200)
        if l.weekday() < 5 and d not in HOLIDAYS and not (-1 <= d <= 4):
            for _ in range(int(g.poisson(5))):
                a = local_ts(d, f"{int(g.integers(7, 17)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
                e = at_work(FIELD_ENG, a, g)
                dur = int(g.gamma(2, 1500)) + 120
                office, tk = g.random() < 0.7, g.random()
                tg = [str(g.choice([HIST1, "GW-WS-ENG-03", OT01, "GW-SYS-SCADA-02", "GW-WTP-HMI-01", "GW-SYS-RTU-03", OPS02]))]
                if g.random() < 0.14:
                    tg += [str(x) for x in g.choice(pool, int(g.integers(1, 3)), replace=False) if str(x) != tg[0]]
                src, net = (home_ip(g), f"AS-{int(g.choice(nets))}")
                bo, bi, au = g.gamma(2, 4e5) + 9000, g.gamma(2, 3e6) + 40000, g.random()
                if e:
                    src, net = home_addr(e["username"], a), home_net(e["username"])
                    if office:
                        src, net = IP.get(e["normal_hosts"][0], "10.14.30.20"), "internal"
                    add("ordinary", e["ot_account"], e["username"], src, net, a, dur, tg,
                        cite_chg(a, "gw", e["username"]) if tk < 0.62 else (cite_wo(a, "gw", e["username"]) if tk < 0.8 else ""), "token" if au < 0.82 else "password only", bo, bi)
        # on-call engineers after hours and at weekends (storm restoration, call-outs)
        for _ in range(int(g.poisson(1.1 if not (0 <= d <= 30) else 2.4))):
            a = t0 + int(g.integers(0, DAY))
            e = on_call(FIELD_ENG, a, g)
            dur = int(g.gamma(2, 1300)) + 180
            src, net, tk, au = home_ip(g), f"AS-{int(g.choice(nets))}", g.random(), g.random()
            tg = [str(g.choice([HIST1, "GW-SYS-SCADA-02", "GW-WTP-HMI-01", OPS02, "GW-SYS-RTU-05"]))]
            bo, bi = g.gamma(2, 5e5) + 9000, g.gamma(2, 3e6) + 40000
            if e:
                src, net = home_addr(e["username"], a), home_net(e["username"])
            if e and not (7 <= local_dt(a).hour < 18 and local_dt(a).weekday() < 5):
                add("oncall", e["ot_account"], e["username"], src, net, a, dur, tg, cite_wo(a, "oc", e["username"]) if tk < 0.55 else "", "token" if au < 0.7 else "password only", bo, bi)
        if g.random() < 0.25 and l.weekday() < 5:
            a = local_ts(d, f"{int(g.integers(9, 15)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
            add("vendor", str(g.choice(["svc_meridian_support", "svc_vantage_mgmt"])), None, f"69.48.219.{int(g.integers(205, 225))}", "AS-64499", a, int(g.gamma(2, 2400)) + 300,
                [str(g.choice([HIST1, "GW-SYS-SCADA-02", SIEMOT]))], f"VND-{int(g.integers(3000, 3999))}", "token", g.gamma(2, 6e5) + 9000, g.gamma(2, 2e6) + 40000)
    # routine checks of the water-system controllers by engineers at work (read-only diagnostics, a few a week)
    gw_ = rng("host_audit", "gw_water")
    for d in range(FIRST_D, LAST_D + 1):
        l = local_dt(D0_EPOCH + d * DAY + 43200)
        for _ in range(int(gw_.poisson(0.75))):
            a = local_ts(d, f"{int(gw_.integers(7, 17)):02d}:{int(gw_.integers(0, 60)):02d}") + int(gw_.integers(0, 60))
            e = at_work(FIELD_ENG, a, gw_)
            dur, tk = int(gw_.gamma(2, 700)) + 150, gw_.random()
            tg = [WATER_RTU[int(gw_.integers(len(WATER_RTU)))]] if gw_.random() < 0.8 else [DCS[int(gw_.integers(len(DCS)))]]
            if gw_.random() < 0.3:
                tg.append(WATER_RTU[int(gw_.integers(len(WATER_RTU)))])
            bo, bi = gw_.gamma(2, 2e5) + 9000, gw_.gamma(2, 1e6) + 40000
            if e and l.weekday() < 5 and d not in HOLIDAYS and not (-1 <= d <= 4) and not clash(a, a + dur):
                add("ordinary", e["ot_account"], e["username"], IP.get(e["normal_hosts"][0], "10.14.30.20"), "internal", a, dur, sorted(set(tg)),
                    cite_wo(a, "wtr", e["username"]) if tk < 0.7 else "", "token", bo, bi)
    # routine checks of the substation controllers and the SCADA server (read-only diagnostics; now and then a round of several stations)
    gs_ = rng("host_audit", "gw_subs")
    for d in range(FIRST_D, LAST_D + 1):
        l = local_dt(D0_EPOCH + d * DAY + 43200)
        for _ in range(int(gs_.poisson(1.5))):
            a = local_ts(d, f"{int(gs_.integers(7, 17)):02d}:{int(gs_.integers(0, 60)):02d}") + int(gs_.integers(0, 60))
            e = at_work(FIELD_ENG, a, gs_)
            dur, tk, r1, r2 = int(gs_.gamma(2, 800)) + 180, gs_.random(), gs_.random(), gs_.random()
            tg = [SCADA1] if r1 < 0.42 else [SUB_RTU[int(gs_.integers(len(SUB_RTU)))]]
            if r2 < 0.22:
                extra = [str(x) for x in gs_.choice(SUB_RTU + WATER_RTU + [SCADA1, HIST1, OT01], int(gs_.integers(2, 5)), replace=False)]
                tg += [x for x in extra if x not in tg]
                dur += 400 * len(tg)
            elif r2 < 0.4:
                x = str(gs_.choice(SUB_RTU + [HIST1, SCADA1]))
                tg += [x] if x not in tg else []
            bo, bi = gs_.gamma(2, 2e5) + 9000, gs_.gamma(2, 1e6) + 40000
            if e and l.weekday() < 5 and d not in HOLIDAYS and not (-1 <= d <= 4) and not clash(a, a + dur):
                add("ordinary", e["ot_account"], e["username"], IP.get(e["normal_hosts"][0], "10.14.30.20"), "internal", a, dur, tg,
                    (cite_wo(a, "sub", e["username"]) if tk < 0.6 else cite_chg(a, "sub", e["username"])) if tk < 0.85 else "", "token" if tk > 0.1 else "password only", bo, bi)
    # the field-operations contractor's ordinary daytime sessions (the account is disabled on 2027-10-02)
    gc = rng("host_audit", "contractor2")
    for d in range(FIRST_D, day_utc(ts("2027-10-02T00:00Z"))):
        r1, hh, mm, ss, dur, ip4, r2, tk, au = gc.random(), int(gc.integers(8, 16)), int(gc.integers(0, 60)), int(gc.integers(0, 60)), int(gc.gamma(2, 1100)) + 240, \
            int(gc.integers(18, 30)), gc.random(), gc.random(), gc.random()
        bo, bi = gc.gamma(2, 3e5) + 9000, gc.gamma(2, 2e6) + 40000
        if local_dt(D0_EPOCH + d * DAY + 43200).weekday() < 5 and d not in HOLIDAYS and r1 < 0.38 and not (-2 <= d <= 6):
            a = local_ts(d, f"{hh:02d}:{mm:02d}") + ss
            if clash(a, a + dur):
                continue
            add("contractor", "svc_fieldops_ext", None, f"66.193.54.{ip4}", "AS-11427", a, dur, [HIST1] + ([SIEMOT] if r2 < 0.12 else []),
                cite_wo(a, "ctr") if tk < 0.75 else "", "token" if au < 0.8 else "password only", bo, bi)
    # the early-morning session of that account during which an exception rule was added on the OT log collector
    add("contractor", "svc_fieldops_ext", None, "66.193.54.23", "AS-11427", RULE_CREATED - 188, 547, [SIEMOT], "", "token", 412_907, 1_988_114)
    # engineers travelling for work (a conference, a factory acceptance test, mutual-aid planning) connect from abroad on a few evenings
    gt = rng("host_audit", "gw_travel")
    trips = [(-47, "MX", "AS-28403", "187.190"), (-31, "CA", "AS-13768", "99.231"), (-20, "MX", "AS-28403", "189.203"), (52, "CA", "AS-5089", "142.116"), (64, "GB", "AS-35228", "86.142"),
             (79, "MX", "AS-28403", "187.189"), (93, "CA", "AS-13768", "99.248")]
    for k, (d0, cc, net, pfx) in enumerate(trips):
        e = FIELD_ENG[int(gt.integers(len(FIELD_ENG)))]
        ipx = f"{pfx}.{int(gt.integers(2, 250))}.{int(gt.integers(2, 250))}"
        for j in range(int(gt.integers(1, 4))):
            a = local_ts(d0 + j, f"{int(gt.integers(18, 23)):02d}:{int(gt.integers(0, 60)):02d}") + int(gt.integers(0, 60))
            dur, tk = int(gt.gamma(2, 900)) + 240, gt.random()
            tg = [str(gt.choice([HIST1, "GW-WS-ENG-03", "GW-SYS-SCADA-02", "GW-WTP-HMI-01"]))]
            if shared().away(e, a) or clash(a, a + dur):
                continue
            add("ordinary", e["ot_account"], e["username"], ipx, net, a, dur, tg, cite_chg(a, "trv", k) if tk < 0.5 else cite_wo(a, "trv", k), "token", 0, 0, cc=cc)
    # every approved setting change made through the gateway happens inside a gateway session of that engineer
    gl = rng("host_audit", "cfg_sessions2")
    by_user = {u["username"]: u for u in USERS}
    for c in cfg_changes():
        if c["source"] != JMP or c["kind"] != "ordinary":
            continue
        e = by_user[c["user"]]
        a = c["t"] - int(gl.integers(90, 700))
        dur = (c["t"] - a) + int(gl.integers(120, 1500))
        add("cfg", c["account"], c["user"], IP.get(e["normal_hosts"][0], "10.14.30.20"), "internal", a, dur, [c["device"]], c["ticket"], "token", gl.gamma(2, 3e5) + 9000, gl.gamma(2, 2e6) + 40000)
    # the fourteen sessions
    for s in SESSIONS:
        targets = [HIST1]
        for k, hname in (("uv_thr_sub1", ["GW-SYS-RTU-01", SCADA1]), ("cfg_sub2", [OT01, "GW-SYS-RTU-04", "GW-SYS-RTU-02"]), ("sub2_cmd", [OPS02]), ("sub3_cmd", [OPS02]),
                         ("p3_sp", ["GW-SYS-RTU-UTL1", "GW-SYS-RTU-WTR3"])):
            if s["start"] <= M.T[k] <= s["start"] + s["dur"]:
                targets += hname
        if any(s["start"] <= t <= s["start"] + s["dur"] for t, _ in M.SUPPRESSION_STEPS) and SCADA1 not in targets:
            targets.append(SCADA1)
        rows.append(dict(kind="session", n=s["n"], account="GW-ENG-VELA", user=None, src_ip=s["ip"], src_network=s["asn"], src_country=s["cc"], login=s["start"] - s["lead"],
                         logout=s["start"] + s["dur"] + s["tail"], dur=s["dur"] + s["lead"] + s["tail"], bytes_out=s["bytes_out"], bytes_in=s["bytes_in"], auth="password only",
                         targets=targets, ticket=""))
    rows.sort(key=lambda r: r["login"])
    n = 20000
    for r in rows:                                    # ids are issued in order of login, from one counter shared with refused attempts
        n += 1 + (int(hsh("rasgap", r["login"], n=4), 16) % 9 == 0) + (int(hsh("rasgap2", r["login"], n=4), 16) % 31 == 0)
        r["id"] = f"RAS-{n}"
    return rows


def ordinary_gateway_sessions(g=None):
    """(old interface) the sessions as lists, the fourteen excluded."""
    rows = [[r["id"], JMP, r["account"], r["src_ip"], r["src_network"], r["src_country"], z(r["login"]), z(r["logout"]), r["dur"], r["bytes_out"], r["bytes_in"], r["auth"],
             ";".join(r["targets"]), r["ticket"]] for r in gateway_sessions() if r["kind"] != "session"]
    return rows, 0


TAG_GROUPS = ["load_profile", "feeder_voltage", "pump_flow;pressure", "tank_level", "water_quality", "breaker_status", "transformer_temp", "relay_settings", "relay_config;breaker_status",
              "relay_config(SUB-03)", "breaker_status(SUB-01)", "pump_setpoints;pressure_zones", "alarm_config", "relay_settings;tap_position", "breaker_status(SUB-05)",
              "relay_config(SUB-01..SUB-05)", "pump_setpoints;booster_setpoints", "feeder_voltage;relay_settings", "relay_config;protection_events", "relay_config;alarm_config",
              "breaker_status;relay_settings", "breaker_status(SUB-02)", "breaker_status(SUB-03)", "relay_config;pump_setpoints", "relay_config(SUB-02)", "breaker_status(SUB-04)"]
_STORY_GROUPS = ["relay_settings;tap_position", "feeder_voltage;relay_settings", "relay_config;breaker_status", "relay_config(SUB-01..SUB-05)", "relay_config;protection_events",
                 "pump_setpoints;pressure_zones", "relay_config;alarm_config", "breaker_status;relay_settings", "alarm_config", "breaker_status(SUB-02)", "pump_setpoints;booster_setpoints",
                 "breaker_status(SUB-03)", "relay_config;pump_setpoints", "relay_config(SUB-01..SUB-05)"]


@functools.lru_cache(maxsize=None)
def historian_rows():
    """Sessions on the historian, in order of start: dicts t, id, account, client, dur, tags, groups, qtype, kind, gw (gateway session id or None)."""
    g = rng("host_audit", "hist2")
    rows = []

    def add(t, account, client, dur, tags, groups, qtype, kind, gw=None, **kw):
        rows.append(dict(t=int(t), account=account, client=client, dur=int(dur), tags=int(tags), groups=groups, qtype=qtype, kind=kind, gw=gw, **kw))

    def grp():
        return TAG_GROUPS[int(g.integers(len(TAG_GROUPS)))]

    for d in range(FIRST_D, LAST_D + 1):
        t0 = D0_EPOCH + d * DAY
        l = local_dt(t0 + 43200)
        for _ in range(int(g.poisson(5.5 if (l.weekday() < 5 and d not in HOLIDAYS) else 2.2) * (0.3 if -1 <= d <= 4 else 1))):
            a = local_ts(d, f"{int(g.integers(6, 19)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
            dur = int(g.gamma(2, 500)) + 30
            bulk = g.random() < 0.07
            tags = (int(g.gamma(2, 260)) + 150) if bulk else (int(g.gamma(2, 60)) + 4)
            person, k4, gr = g.random() < 0.6, int(g.integers(4)), grp()
            if person:
                e = at_work(ENGINEERS, a, g)
                if e:
                    add(a, e["ot_account"], eng_ws(e), dur, tags, gr, "bulk read" if bulk else "trend", "direct")
            else:
                acct, cl = [("svc_scada_hist", SCADA1), ("svc_scada_hist", "GW-SYS-SCADA-02"), ("svc_hist_repl", HISTDMZ), ("svc_oms", "GW-SRV-OMS-01")][k4]
                if cl in (HISTDMZ, "GW-SRV-OMS-01") and not (boundary_open(a) and boundary_open(a + dur)):
                    continue
                add(a, acct, cl, dur, tags, gr, "bulk read" if bulk else "trend", "service")
    # sessions opened through the remote-access gateway (one for each gateway session that lists the historian)
    for r in gateway_sessions():
        if r["kind"] == "session" or HIST1 not in r["targets"]:
            continue
        a = r["login"] + 7 + int(g.integers(3, 60))
        dur = max(25, min(r["dur"] - (a - r["login"]) - 8, int(g.gamma(2, 420)) + 40))
        ext = r["kind"] in ("contractor", "vendor")
        bulk = g.random() < (0.45 if ext else 0.25)
        kp = int(hsh("profile", r["id"], n=4), 16) % 100     # some engineers use a connection profile stored on the gateway, not their own account
        prof = None if ext or kp >= 16 else ("svc_scada_hist" if kp < 9 or r["login"] >= ts("2027-10-02T00:00Z") else "svc_fieldops_ext")
        add(a, f"{JMP}\\{r['account']}" if ext else (f"{JMP}\\{prof}" if prof else r["account"]), JMP, dur, (int(g.gamma(2, 260)) + 150) if bulk else (int(g.gamma(2, 70)) + 12), grp(), "bulk read" if bulk else "trend",
            "gateway", r["id"])
    by_n = {r["n"]: r for r in gateway_sessions() if r["kind"] == "session"}
    for s, gr in zip(SESSIONS, _STORY_GROUPS):
        dur = 862 if s["n"] == 1 else int(min(s["dur"] - 12, 1700) * (0.62 + 0.36 * frac("hd", s["n"])))
        add(s["start"] + 3, f"{JMP}\\svc_fieldops_ext", JMP, dur, s["tags"], gr, "bulk read", "session", by_n[s["n"]]["id"], n=s["n"], hid=s["hist_id"])
    rows.sort(key=lambda r: r["t"])
    # session numbers come from one counter shared with other historian clients, so they rise with time in uneven steps;
    # the two numbers canon states (00441 and 00917) are honoured and the rest are laid out around them
    i0 = next(i for i, r in enumerate(rows) if r.get("hid") == "HIST-20270907-00441")
    i1 = next(i for i, r in enumerate(rows) if r.get("hid") == "HIST-20271002-00917")
    gi = rng("host_audit", "hist_ids2")
    seq = [0] * len(rows)
    seq[i0], seq[i1] = 441, 917
    assert i0 <= 440 and i1 - i0 - 1 <= 474, (i0, i1 - i0 - 1, "historian sessions do not fit around the two fixed session numbers")
    before = sorted(gi.choice(np.arange(1, 441), i0, replace=False).tolist())
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
        r["id"] = f"HIST-{dt.datetime.fromtimestamp(r['t'], UTC):%Y%m%d}-{q % 100000:05d}"
    return rows


def _ot_supp_steps():
    """((first time, first count), [(time, count) changes]) of the suppressed-alarm count as the SCADA historian recorded it."""
    import glob as _glob
    pts = []
    for p in sorted(_glob.glob(os.path.join(ROOT, "05_other_sources/telemetry/historian_SYSTEM_*.csv"))):
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("GW.SCADA.ALARM_SUPR_CNT.PV,"):
                    _, t, v, _q = line.rstrip("\n").split(",")
                    pts.append((ts(t[:16] + "Z") + int(t[17:19]), int(float(v))))
    pts.sort()
    out, prev = [], pts[0][1]
    for t, v in pts:
        if v != prev:
            out.append((t, v))
            prev = v
    return pts[0], out


SUPP_CATS = ["communications", "tank level", "nuisance door contact", "pump flow", "water quality sensor", "substation relay"]


@functools.lru_cache(maxsize=None)
def alarm_points():
    """The alarm points that can be put on the suppression list: {category: [name]} with their fixed point numbers.
    Point numbers come from the SCADA point database, not from the order in which points were suppressed."""
    pts = {c: [] for c in SUPP_CATS}
    for k in range(1, 6):
        pts["substation relay"] += [f"SUB-0{k} relay trip"] + [f"SUB-0{k} feeder {n} overcurrent" for n in range(1, 6)] + [f"SUB-0{k} breaker fail", f"SUB-0{k} transformer temp high",
                                                                                                                         f"SUB-0{k} bus undervoltage"]
        pts["communications"] += [f"SUB-0{k} RTU comms fail", f"SUB-0{k} relay comms fail"]
        pts["nuisance door contact"] += [f"SUB-0{k} control house door", f"SUB-0{k} yard gate"]
    for n in range(1, 7):
        pts["pump flow"] += [f"Pump station {n} P-{m} flow low" for m in range(1, 5)] + [f"Pump station {n} discharge pressure low"]
        pts["communications"] += [f"Pump station {n} comms fail"]
        pts["nuisance door contact"] += [f"Pump station {n} door"]
    for n in range(1, 5):
        pts["pump flow"] += [f"Booster {n} flow low", f"Booster {n} low suction"]
    for n in range(1, 11):
        pts["tank level"] += [f"Tank {n} level high", f"Tank {n} level low"]
    pts["water quality sensor"] += [f"WTP filter {n} turbidity high" for n in range(1, 9)] + [f"Zone {n} chlorine residual low" for n in range(1, 13)] + \
        [f"Zone {n} pressure low" for n in range(1, 13)] + ["WTP chlorine residual low", "WTP clearwell level low", "WTP raw water turbidity high", "WTP pH out of range"]
    ids, used = {}, set()
    for c in SUPP_CATS:
        for name in pts[c]:
            n = 2000 + int(hsh("almpt", name, n=6), 16) % 7000
            while n in used:
                n += 1
            used.add(n)
            ids[name] = n
    return pts, ids


def _alm(name):
    return f"ALM-{alarm_points()[1][name]} ({name})"


@functools.lru_cache(maxsize=None)
def suppression_batches():
    """Changes of the alarm-suppression list: dicts t, n (count after), delta, kind, by, source, ticket, system, rows.
    Counts and times are those of the SCADA historian's suppressed-alarm tag; before that tag starts, ordinary changes
    are laid out the same way (a few a month, the count staying between 9 and 15). Every row, whoever made the change,
    names a point of the SCADA point database."""
    g = rng("host_audit", "supp3")
    S = shared()
    pts, _ids = alarm_points()
    cat_of = {name: c for c, names in pts.items() for name in names}
    (t_first, n_first), steps = _ot_supp_steps()
    pre, cnt, t = [], 12, SPAN_START - 2 * DAY
    while True:
        t += int(g.integers(2 * DAY, 6 * DAY))
        tl = t - (t % DAY) + int(g.integers(13 * 3600, 21 * 3600)) + int(g.integers(0, 3600))
        if tl >= t_first - DAY:
            break
        cnt = int(np.clip(cnt + g.choice([-2, -1, 1, 1, 2]), 9, 15))
        pre.append((tl, cnt))
    if pre:
        pre[-1] = (pre[-1][0], n_first)
    story = {int(a) for a, _ in M.SUPPRESSION_STEPS}
    rebuilt = int(M.T["isolate"] + 4 * 3600 + 1140)
    start = [pts["communications"][i] for i in (1, 6, 11, 14)] + [pts["tank level"][i] for i in (2, 9, 15)] + [pts["nuisance door contact"][i] for i in (0, 5, 12)] + \
        [pts["substation relay"][28], pts["pump flow"][7]]
    active, added_by = list(start), {}
    out, prev = [], 12
    for t, n in pre + steps:
        if n == prev:
            continue
        delta = n - prev
        rows = []
        if int(t) in story:
            kind, by, src, ticket = "session", "GW-ENG-VELA", JMP, ""
        elif int(t) == rebuilt:
            kind, by, src, ticket = "restore", FIELD_ENG[0]["ot_account"], "GW-WS-OPS-01", "SI-2027-CC-001"
        else:
            ops = [x for x in S.sessions_at(t) if (x["host"] in OPS_CONSOLES or x["host"] in ENG_WS) and S.USER_BY_NAME[x["user"]].get("ot_account")]
            x = ops[int(g.integers(len(ops)))] if ops else None
            u = S.USER_BY_NAME[x["user"]] if x else OPERATORS[int(g.integers(len(OPERATORS)))]
            kind, by, src = "ordinary", u["ot_account"], (x["host"] if x else "GW-WS-OPS-01")
            ticket = cite_chg(t, "supp") if g.random() < 0.7 else ""
        for j in range(abs(delta)):
            tj = t + (j * (0.15 + 0.5 * frac("supj", t, j)) if delta > 0 else -(abs(delta) - 1 - j) * (0.1 + 0.3 * frac("supr", t, j)))
            if delta > 0:
                if kind == "session":
                    d3 = int(t) == int(M.T["supp_list_d3"])
                    want = "substation relay" if d3 else ["substation relay", "pump flow", "water quality sensor"][(int(hsh("sc", t, n=2), 16) + j) % 3]
                    free = [p_ for p_ in pts[want] if p_ not in active and (not d3 or "relay trip" in p_ or "overcurrent" in p_)]
                    free.sort(key=lambda p_: (0 if (d3 and "relay trip" in p_) else 1, hsh("sp", t, p_)))
                    free = free or [p_ for c in SUPP_CATS for p_ in pts[c] if p_ not in active]
                    name = free[0]
                else:
                    free = [p_ for c in SUPP_CATS for p_ in pts[c] if p_ not in active]
                    k_, r_ = int(g.integers(len(free))), g.random()
                    trips = [p_ for p_ in free if "relay trip" in p_]
                    name = trips[k_ % len(trips)] if trips and r_ < 0.16 else free[k_]      # relay points are suppressed for test work now and then
                active.append(name)
                added_by[name] = kind
                rows.append((int(tj), "ADD", _alm(name), cat_of[name]))
            else:
                if kind == "ordinary":
                    mine = [p_ for p_ in active if added_by.get(p_, "ordinary") == "ordinary"] or active
                    name = mine[int(g.integers(len(mine)))]
                else:
                    mine = [p_ for p_ in active if added_by.get(p_) == "session"] or active
                    name = mine[0]
                active.remove(name)
                rows.append((int(tj), "REMOVE", _alm(name), "restored" if kind == "restore" else cat_of[name]))
        water = sum(1 for r in rows if r[3] in ("pump flow", "water quality sensor", "tank level"))
        out.append(dict(t=int(t), n=n, delta=delta, kind=kind, by=by, source=src, ticket=ticket, rows=rows,
                        system="GW-WTP-DCS-01" if water > len(rows) / 2 and kind != "restore" else SCADA1))
        prev = n
    return out


def supp_count_at(t):
    n = 12
    for b in suppression_batches():
        if b["t"] <= t:
            n = b["n"]
    return n


def _fim_catalog():
    """Monitored files on the OT engineering file server: [(relative path, weight, kind)]. kind: 'relay' (settings of a
    substation's relays), 'cfg' (water-system setpoints), 'doc' (everything else), 'monthly' (one file per month)."""
    f = []
    for k in range(1, 6):
        d = f"relayconfigs\\sub{k:02d}"
        f += [(d + "\\rtu_config_draft.xml", 5, "relay"), (d + "\\rtu_config_active.xml", 2, "relay"), (d + f"\\relay_settings_R-{k:02d}A.xml", 2, "relay"),
              (d + f"\\relay_settings_R-{k:02d}B.xml", 2, "relay"), (d + f"\\relay_settings_R-{k:02d}C.xml", 2, "relay"), (d + f"\\protection_coordination_sub{k:02d}.xlsx", 2, "doc"),
              (d + f"\\sld_sub{k:02d}_rev{'BCDCB'[k - 1]}.dwg", 1, "doc"), (d + "\\test_report_2027.pdf", 1, "doc")]
    f += [("relayconfigs\\archive\\relay_settings_2026Q4.zip", 1, "doc"), ("relayconfigs\\archive\\relay_settings_2027Q2.zip", 1, "doc"), ("relayconfigs\\readme_change_procedure.docx", 1, "doc")]
    f += [(f"setpoints\\pump_station_{n}_setpoints.cfg", 3, "cfg") for n in range(1, 7)] + [("setpoints\\booster_setpoints.cfg", 3, "cfg"), ("setpoints\\tank_level_alarms.cfg", 2, "cfg"),
                                                                                      ("setpoints\\pressure_zones.xlsx", 2, "doc"), ("setpoints\\wtp_dosing_setpoints.cfg", 2, "cfg")]
    f += [(f"procedures\\switching_procedure_SP-{n}.docx", 1, "doc") for n in (101, 104, 107, 112, 115, 118, 121)] + \
        [("procedures\\lockout_tagout_checklist.docx", 2, "doc"), ("procedures\\storm_restoration_plan_2027.docx", 3, "doc"), ("procedures\\relay_test_procedure.docx", 1, "doc"),
         ("procedures\\boil_water_notice_procedure.docx", 1, "doc"), ("procedures\\black_start_checklist.docx", 1, "doc")]
    for proj in ("feeder_14_reconductor", "sub03_breaker_replacement", "booster2_vfd_upgrade", "scada_point_database_2027", "wtp_filter_4_rehab", "tank_5_recoat", "ami_pilot",
                 "sub05_relay_upgrade", "pump_station_3_generator", "fiber_ring_phase2"):
        f += [(f"projects\\{proj}\\{name}", w, "doc") for name, w in (("scope.docx", 1), ("schedule.xlsx", 3), ("punchlist.xlsx", 3), ("cost_estimate.xlsx", 2), ("commissioning_notes.docx", 2),
                                                                    ("vendor_quote.pdf", 1), ("meeting_notes.docx", 3))]
    f += [(f"drawings\\E-{100 + i}_{name}.dwg", 1, "doc") for i, name in enumerate(("one_line_system", "sub01_protection", "sub02_protection", "sub03_protection", "sub04_protection",
                                                                                 "sub05_protection", "wtp_power_distribution", "pump_station_typical", "scada_network", "fiber_ring"))]
    f += [("drawings\\drawing_index.xlsx", 2, "doc"), ("wtp\\reports\\turbidity_summary_2027.xlsx", 3, "doc"), ("wtp\\reports\\filter_run_log_2027.xlsx", 3, "doc")]
    f += [("wtp\\reports\\daily_ops_report_{m}.xlsx", 7, "monthly"), ("wtp\\reports\\chlorine_log_{m}.xlsx", 5, "monthly"), ("wtp\\reports\\lab_results_{m}.pdf", 2, "monthly"),
          ("projects\\status_report_{m}.docx", 2, "monthly")]
    return f


def _fim_diff(path, kind, key):
    """What the monitor's comparison of two versions of a settings file says (empty for other files)."""
    k = int(hsh("diff", path, key, n=8), 16)
    if kind == "relay":
        sub = path.split("\\sub")[1][:2]
        rel, a = f"R-{sub}{'ABC'[k % 3]}", [900, 1000, 1200, 1400][(k >> 2) % 4]
        opts = [f"overcurrent_trip_threshold {a}A -> {a + [100, 200, -100][(k >> 5) % 3]}A for " + (f"relays R-{sub}A, R-{sub}B, R-{sub}C" if (k >> 13) % 2 == 0 else f"relay {rel}"), f"overcurrent_trip_threshold {a}A -> {a + 200}A for relays R-{sub}A, R-{sub}B" + (f", R-{sub}C" if (k >> 3) % 3 else ""),
                f"relay 51 time dial {['2.0', '2.5', '3.0'][(k >> 4) % 3]} -> {['2.5', '2.0', '1.5'][(k >> 4) % 3]} for " + (f"relays R-{sub}A, R-{sub}B, R-{sub}C" if (k >> 11) % 3 == 0 else f"relay {rel}"), f"CT ratio field corrected 600:5 -> 800:5 for {rel}",
                f"recloser shots {3 - (k >> 6) % 2} -> {2 + (k >> 6) % 2} for {rel}", f"27-UV time delay {['2.0', '1.5'][(k >> 7) % 2]}s -> {['1.5', '2.0'][(k >> 7) % 2]}s", "comment block updated",
                f"revision label rev {1 + (k >> 8) % 9} -> rev {2 + (k >> 8) % 9}", "station name corrected", f"LTC band {['2.0', '1.5'][(k >> 9) % 2]}V -> {['1.5', '2.0'][(k >> 9) % 2]}V",
                f"breaker failure timer {12 + (k >> 10) % 3} -> {10 + (k >> 10) % 2} cycles for {rel}", f"alarm text edited for {rel}",
                f"overcurrent_trip_threshold {a}A -> {a + [200, 100, -200][(k >> 6) % 3]}A for relays R-{sub}A, R-{sub}B, R-{sub}C"]
        return opts[(k >> 12) % len(opts)]
    if kind == "cfg":
        n, v = 1 + (k >> 3) % 4, 70 + (k >> 5) % 18
        opts = [f"P-{n} discharge setpoint {v} -> {v + [2, 3, -2][(k >> 9) % 3]} psi", f"tank {1 + (k >> 4) % 10} high-level alarm 31.5 -> 31.0 ft", f"low suction cut-out {8 + (k >> 6) % 3} -> {10 + (k >> 6) % 3} psi",
                f"pump start level {17 + (k >> 7) % 3}.0 -> {18 + (k >> 7) % 3}.5 ft", "comment block updated", f"revision label rev {1 + (k >> 8) % 9} -> rev {2 + (k >> 8) % 9}",
                f"chlorine dose setpoint {['1.8', '2.0', '2.2'][(k >> 10) % 3]} -> {['2.0', '2.2', '2.0'][(k >> 10) % 3]} mg/L", f"lead/lag rotation P-{n} -> P-{1 + n % 4}"]
        return opts[(k >> 12) % len(opts)]
    return ""


STORY_FILE = "relayconfigs\\sub02\\rtu_config_draft.xml"


@functools.lru_cache(maxsize=None)
def fim_rows():
    """Monitored file changes on the OT engineering file server: dicts t, path, key, event, prev, new, user, source, diff, kind.
    The same few hundred files are edited again and again; each version's hash follows the previous one."""
    g = rng("host_audit", "fim3")
    cat = _fim_catalog()
    w = np.array([c[1] for c in cat], float)
    w /= w.sum()
    ev = []

    def add(a, e_acct, src, kind="ordinary"):
        rel, _w, fk = cat[int(g.choice(len(cat), p=w))]
        if fk == "monthly":
            rel = rel.format(m=f"{local_dt(a):%Y-%m}")
        ev.append(dict(t=int(a), rel=rel, fk=fk, user=e_acct, source=src, kind=kind))

    for d in range(FIRST_D, LAST_D + 1):
        l = local_dt(D0_EPOCH + d * DAY + 43200)
        for _ in range(int(g.poisson(3.4 if (l.weekday() < 5 and d not in HOLIDAYS) else 0.4) * (0.3 if -1 <= d <= 6 else 1))):
            a = local_ts(d, f"{int(g.integers(7, 18)):02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
            e = at_work(FIELD_ENG, a, g)
            if e:
                add(a, e["ot_account"], eng_ws(e))
    for r in gateway_sessions():                       # writes made through the gateway happen inside that person's gateway session
        if r["kind"] in ("ordinary", "oncall") and OT01 in r["targets"]:
            add(r["login"] + 30 + int(g.integers(0, max(1, r["dur"] - 60))), r["account"], JMP, "gateway")
    ev.append(dict(t=M.T["cfg_sub2"], rel=STORY_FILE, fk="relay", user="GW-ENG-VELA", source=JMP, kind="session"))
    ev.sort(key=lambda x: x["t"])
    ver, out = {}, []
    for x in ev:
        v0 = 3 + int(hsh("v0", x["rel"], n=2), 16) % 20 if x["fk"] != "monthly" else 0
        v = ver.get(x["rel"], v0)
        ver[x["rel"]] = v + 1
        created = x["fk"] == "monthly" and v == 0
        diff = _fim_diff(x["rel"], x["fk"], v) if not created else ""
        if x["kind"] == "session":
            diff = "overcurrent_trip_threshold 1200A -> 2400A for relays R-02A, R-02B, R-02C"
        out.append(dict(t=x["t"], path="\\\\gw-srv-ot-01\\" + x["rel"], key=f"{x['rel']}|{x['t']}", event="CREATED" if created else "MODIFIED",
                        prev="" if created else "sha256=" + hsh("fv", x["rel"], v), new="sha256=" + hsh("fv", x["rel"], v + 1), user=x["user"], source=x["source"], diff=diff, kind=x["kind"]))
    # the two hashes canon quotes for the draft file of the second substation: the version before and the version after that change
    idx = [i for i, r in enumerate(out) if r["path"].endswith(STORY_FILE)]
    k = next(i for i in idx if out[i]["kind"] == "session")
    assert out[k]["prev"] != out[k]["new"]             # (the two hashes canon quotes are these generated values)
    return out


CMD_BY_TYPE = {"circuit breaker": ["BREAKER OPEN", "BREAKER CLOSE", "RECLOSE ENABLE", "RECLOSE DISABLE", "TAG NOTE", "ALARM ACK"],
               "feeder breaker": ["BREAKER OPEN", "BREAKER CLOSE", "RECLOSE ENABLE", "TAG NOTE"], "feeder circuit breaker": ["BREAKER OPEN", "BREAKER CLOSE", "RECLOSE ENABLE", "TAG NOTE"],
               "power transformer": ["TAP RAISE", "TAP LOWER", "ALARM ACK", "TAG NOTE"], "bus": ["CAP BANK SWITCH", "ALARM ACK", "TAG NOTE"],
               "booster pump": ["PUMP START", "PUMP STOP", "SETPOINT ENTRY", "ALARM ACK"], "high-service pump": ["PUMP START", "PUMP STOP", "SETPOINT ENTRY", "ALARM ACK"]}
CMD_EQUIP = [e for e in H["equipment"] if e.get("type") in CMD_BY_TYPE and e["equipment_id"].startswith("GW-")]


def _cmd_rate(d):
    """Operator actions a day: more switching in the storm and through restoration."""
    return 2.6 if d < -1 else (6 if d < 0 else (16 if d < 1 else (12 if d < 5 else (7 if d < 15 else (4 if d < 36 else 2.6)))))


@functools.lru_cache(maxsize=None)
def scada_cmds():
    """Operator actions on the SCADA server: dicts t, ws, operator, command, device, origin, console, origin_host.
    Each device has a state: a breaker that was opened is closed again before it can be opened once more, a pump that
    was stopped is started again, reclosing that was disabled is enabled again."""
    g = rng("host_audit", "cmd3")
    S = shared()
    out = []
    rd = [r for r in gateway_sessions() if r["kind"] in ("ordinary", "oncall") and any(t in RD_HOSTS for t in r["targets"]) and r["dur"] > 400]
    brk = [e for e in CMD_EQUIP if "breaker" in e["type"]]
    pmp = [e for e in CMD_EQUIP if "pump" in e["type"]]
    xfm = [e for e in CMD_EQUIP if e["type"] == "power transformer"]
    bus = [e for e in CMD_EQUIP if e["type"] == "bus"]
    sub1 = [e["equipment_id"] for e in brk if "SUB01" in e["equipment_id"]][:2]
    busy = {"GW-SUB02-CB-7": [(M.T["sub2_cmd"] - 6 * 3600, M.T["sub2_close"] + 3600)], "GW-SUB03-CB-12": [(M.T["sub3_cmd"] - 6 * 3600, M.T["sub3_close"] + 3600)]}
    for dev in sub1:
        busy[dev] = [(M.T["sub1_trip"] - 6 * 3600, M.T["sub1_back"] + 6 * 3600)]

    def free(dev, a, b):
        return all(b < x or a > y for x, y in busy.get(dev, []))

    def console(a, r2, r3):
        ops = [x for x in S.sessions_at(a) if x["host"] in OPS_CONSOLES and S.USER_BY_NAME[x["user"]].get("ot_account")]
        if not ops:
            return None
        x = ops[r3 % len(ops)]
        return dict(ws=x["host"], operator="" if r2 < 0.1 else x["user"], origin="console", console=f"CON-{hsh('con', a, n=6)}", origin_host="")

    def put(a, who, command, dev):
        out.append(dict(t=int(a), command=command, device=dev, **who))

    auto = dict(ws="", operator="", origin="automation", console="", origin_host="")
    k = 0
    for d in range(FIRST_D, LAST_D + 1):
        for _ in range(int(g.poisson(_cmd_rate(d)))):
            a = D0_EPOCH + d * DAY + int(g.integers(0, DAY))
            r, r2, r3, r4, gap = g.random(), g.random(), int(g.integers(1 << 30)), g.random(), g.random()
            kind = "pair_brk" if r4 < 0.18 else ("pair_pump" if r4 < 0.32 else ("pair_recl" if r4 < 0.40 else ("tap" if r4 < 0.60 else ("cap" if r4 < 0.68 else ("ack" if r4 < 0.86 else
                                                                                                                                                              ("note" if r4 < 0.94 else "setpoint"))))))
            who = console(a, r2, r3)
            if r >= 0.82 and r < 0.9 and rd and kind != "pair_pump":           # an engineer through the remote-access gateway, inside one of their sessions
                s_ = rd[k % len(rd)]
                k += 7
                a = s_["login"] + 90 + r3 % (s_["dur"] - 120)
                who = dict(ws=next(t for t in s_["targets"] if t in RD_HOSTS), operator="" if r2 < 0.2 else s_["user"], origin="remote desktop", console="", origin_host=JMP)
            elif r >= 0.9 and kind in ("pair_pump", "pair_recl", "cap", "pair_brk"):
                who = auto                                # automatic schemes: level control, reclosing, capacitor control, protection
            if who is None:
                continue
            if kind == "pair_brk":
                e = brk[r3 % len(brk)]["equipment_id"]
                b = a + 1200 + gap ** 2 * 8 * 3600
                who2 = console(b, r2, r3 >> 3)
                if not free(e, a - 600, b + 600) or who2 is None:
                    continue
                busy.setdefault(e, []).append((a - 600, b + 600))
                put(a, who, "BREAKER OPEN", e)
                put(b, who2, "BREAKER CLOSE", e)
            elif kind == "pair_pump":
                e = pmp[r3 % len(pmp)]["equipment_id"]
                b = a + 1800 + gap * 9 * 3600
                who2 = console(b, r2, r3 >> 3) if who is not auto else auto
                if not free(e, a - 600, b + 600) or who2 is None:
                    continue
                busy.setdefault(e, []).append((a - 600, b + 600))
                running = int(hsh("run", e, n=2), 16) % 3 > 0          # most pumps run; a standby pump is started and stopped again
                put(a, who, "PUMP STOP" if running else "PUMP START", e)
                put(b, who2, "PUMP START" if running else "PUMP STOP", e)
            elif kind == "pair_recl":
                e = brk[(r3 >> 5) % len(brk)]["equipment_id"]
                b = a + 3600 + gap * 9 * 3600
                who2 = console(b, r2, r3 >> 3)
                if not free("recl:" + e, a - 600, b + 600) or not free(e, a - 600, b + 600) or who2 is None:
                    continue
                busy.setdefault("recl:" + e, []).append((a - 600, b + 600))
                put(a, who, "RECLOSE DISABLE", e)
                put(b, who2, "RECLOSE ENABLE", e)
            elif kind == "tap" and xfm:
                put(a, who, ["TAP RAISE", "TAP LOWER"][r3 % 2], xfm[(r3 >> 2) % len(xfm)]["equipment_id"])
            elif kind == "cap" and bus:
                put(a, who, "CAP BANK SWITCH", bus[r3 % len(bus)]["equipment_id"])
            elif kind == "setpoint" and pmp:
                put(a, who, "SETPOINT ENTRY", pmp[r3 % len(pmp)]["equipment_id"])
            else:
                eq = CMD_EQUIP[r3 % len(CMD_EQUIP)]
                put(a, who, "ALARM ACK" if kind == "ack" and "ALARM ACK" in CMD_BY_TYPE[eq["type"]] else "TAG NOTE", eq["equipment_id"])
    # the storm trip of the first substation and its restoration; the two openings given over remote desktop and their closing at restoration
    for n_, dev in enumerate(sub1):
        put(M.T["sub1_trip"] + 0.2 * n_, auto, "BREAKER OPEN", dev)
        w = console(M.T["sub1_back"] + 140 + 95 * n_, 0.5, n_) or auto
        put(M.T["sub1_back"] + 140 + 95 * n_, w, "BREAKER CLOSE", dev)
    for key, key2, dev in (("sub2_cmd", "sub2_close", "GW-SUB02-CB-7"), ("sub3_cmd", "sub3_close", "GW-SUB03-CB-12")):
        put(M.T[key], dict(ws=OPS02, operator="", origin="remote desktop", console="", origin_host=JMP), "BREAKER OPEN", dev)
        w = console(M.T[key2], 0.5, 1) or dict(ws="GW-WS-OPS-01", operator="", origin="console", console=f"CON-{hsh('con', M.T[key2], n=6)}", origin_host="")
        put(M.T[key2], w, "BREAKER CLOSE", dev)
    return sorted(out, key=lambda x: x["t"])


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


def main(parts=None):
    import itsec_audit
    import itsec_portal
    import itsec_siem
    import itsec_zeek
    table = {"siem": itsec_siem.gen_siem, "zeek": itsec_zeek.gen_zeek, "audit": itsec_audit.gen_audit, "portal": itsec_portal.gen_portal}
    for p in parts or ["siem", "zeek", "audit", "portal"]:
        if p.startswith("zeek:"):                      # one month of the sensor logs: zeek:2027-09
            itsec_zeek.gen_zeek(p.split(":", 1)[1])
        else:
            table[p]()


if __name__ == "__main__":
    import gen_itsec as _self          # one module instance for the writers, whatever the entry point
    _self.main(sys.argv[1:])
