"""Helpers shared by gen_itsec_net.py and probes_itsec_net.py: where a flow crosses a firewall, address
translation, how the web filter names and rates a destination, and a small pcap writer and reader.

Everything here is a pure function of the delivered Zeek rows and the host registry."""
import hashlib
import ipaddress
import os
import struct

import itsec_shared as S

G = S.G
EDGE, OTFW = "GW-FW-EDGE-01", "GW-OT-FW-01"
PROXY_DEV = "GW-SRV-PROXY-01"

# ---- public addresses of the utility (invented block) -------------------------------------------
PUBLIC_NET = ipaddress.ip_network("12.186.44.64/28")
PUB_FW = "12.186.44.65"                                              # outside interface of the edge firewall
NAT_POOL = ["12.186.44.66", "12.186.44.67", "12.186.44.68", "12.186.44.69"]   # outbound source NAT
PUB_OF = {"GW-GW-MAIL-01": "12.186.44.70", "GW-SRV-WEB-01": "12.186.44.71", "GW-SRV-PORTAL-01": "12.186.44.72",
          "GW-SRV-DNSX-01": "12.186.44.73", "GW-SRV-MFT-01": "12.186.44.74", "GW-VPN-EMP-01": "12.186.44.75",
          "GW-SYS-JMP-01": "12.186.44.76"}
HOST_OF_PUB = {v: k for k, v in PUB_OF.items()}


def h32(*k):
    return int.from_bytes(hashlib.sha256("|".join(map(str, k)).encode()).digest()[:4], "big")


def hbytes(n, *k):
    """n deterministic pseudo-random bytes."""
    out, i = b"", 0
    seed = "|".join(map(str, k)).encode()
    while len(out) < n:
        out += hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
        i += 1
    return out[:n]


def nat_ip(client_ip):
    return NAT_POOL[h32("nat", client_ip) % len(NAT_POOL)]


# ---- where a flow crosses -----------------------------------------------------------------------
def segment(zone):
    """Leg of the IT/OT boundary firewall a zone hangs off: IT (corporate and internet side), DMZ, OT."""
    if zone == "ot-dmz":
        return "DMZ"
    if zone.startswith("ot-"):
        return "OT"
    return "IT"


_RESERVED = [ipaddress.ip_network(n) for n in ("0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12",
                                               "192.168.0.0/16", "224.0.0.0/3")]


def is_reserved(ip):
    """Loopback, link-local, multicast, reserved or private space (private space that is one of the utility's
    own networks has a zone and is not asked about here)."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return any(a in n for n in _RESERVED)


def crossings(r):
    """Devices a delivered conn row passes: subset of (EDGE, OTFW). Flows inside the control network
    (console to SCADA server, front-end processor to RTU) pass neither. An address in reserved or unassigned
    private space is not an internet host: such a flow never reaches a firewall."""
    zo, zr = S.zone_of(r["id.orig_h"]), S.zone_of(r["id.resp_h"])
    out = []
    if (zo == "internet" and is_reserved(r["id.orig_h"])) or (zr == "internet" and is_reserved(r["id.resp_h"])):
        return out, zo, zr
    if (zo == "internet") != (zr == "internet"):
        out.append(EDGE)
    if segment(zo) != segment(zr):
        out.append(OTFW)
    return out, zo, zr


_APP = {"ssl": "ssl", "http": "web-browsing", "dns": "dns", "rdp": "ms-rdp", "smb": "ms-ds-smb", "dnp3": "dnp3", "modbus": "modbus-tcp",
        "krb": "kerberos", "ldap": "ldap", "dce_rpc": "msrpc", "ntp": "ntp", "ssh": "ssh", "smtp": "smtp", "snmp": "snmp", "syslog": "syslog"}
_APP_PORT = {"5450": "historian-data", "4000": "scada-console", "10000": "backup-agent", "1433": "mssql-db", "8443": "ssl", "8530": "ms-update",
             "5985": "ms-winrm", "9100": "printer-raw", "636": "ldaps"}
_END = {"SF": "tcp-fin", "S0": "aged-out", "REJ": "tcp-rst-from-server", "RSTO": "tcp-rst-from-client", "RSTR": "tcp-rst-from-server",
        "SH": "aged-out", "OTH": "aged-out", "S1": "aged-out", "RSTOS0": "tcp-rst-from-client"}


def fw_app(r):
    if r["proto"] == "tcp" and r["conn_state"] in ("S0", "REJ"):
        return "incomplete"
    if r["proto"] == "icmp":
        return "ping"
    a = (_APP_PORT.get(r["id.resp_p"]) if r["id.resp_p"] == "8530" else None) or _APP.get(r["service"]) or _APP_PORT.get(r["id.resp_p"])
    return a or ("unknown-udp" if r["proto"] == "udp" else "unknown-tcp")


def fw_end_reason(r):
    if r["proto"] != "tcp":
        return "aged-out"
    return _END.get(r["conn_state"], "aged-out")


_OT_POLICY = {("IT", "DMZ"): {"443", "445", "5450"}, ("DMZ", "OT"): {"3389", "5450", "445", "20000", "502", "4000", "443"}, ("OT", "DMZ"): {"5450", "443"},
              ("DMZ", "IT"): {"8530", "6514", "443"}}


def fw_action(device, zo, zr, r):
    """(action, rule or None) for a delivered conn row on a device. A flow the sensor saw answered was let through.
    A connection attempt that was never answered is a drop when no rule permits that service in that direction,
    or when the control network is isolated; the rule name is then the one that dropped it."""
    unanswered = r["conn_state"] == "S0"
    if device == OTFW:
        if not G.boundary_open(float(r["ts"])) and r["conn_state"] in ("S0", "REJ"):
            return "deny", "EMERG-OT-ISOLATION"
        if unanswered:
            ports = _OT_POLICY.get((segment(zo), segment(zr)), set())
            if r["proto"] != "tcp" or r["id.resp_p"] not in ports or (zo == "internet" and host_name(r["id.resp_h"]) != "GW-SYS-JMP-01"):
                return "deny", "DEFAULT-DENY"
    elif unanswered and zo == "internet":
        hn = host_name(r["id.resp_h"])
        if not ((hn in ("GW-VPN-EMP-01", "GW-SYS-JMP-01") and r["id.resp_p"] == "443") or (hn in ("GW-SRV-WEB-01", "GW-SRV-PORTAL-01") and r["id.resp_p"] in ("80", "443"))
                or (hn == "GW-GW-MAIL-01" and r["id.resp_p"] == "25") or (hn == "GW-SRV-DNSX-01" and r["id.resp_p"] == "53") or (hn == "GW-SRV-MFT-01" and r["id.resp_p"] in ("22", "443"))):
            return "deny", "DEFAULT-DENY-INBOUND"
    return "allow", None


def host_name(ip):
    return S.host_of_ip(ip)


def ip_bytes(r):
    """(sent, received) byte counters of a firewall session: IP bytes, headers included, as the device counts them."""
    return to_int(r.get("orig_ip_bytes"), to_int(r["orig_bytes"])), to_int(r.get("resp_ip_bytes"), to_int(r["resp_bytes"]))


def to_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def fw_rule(device, zo, zr, r):
    """Policy rule that matched. Names depend only on the direction and the service class."""
    port = r["id.resp_p"]
    if device == EDGE:
        if zr == "internet":
            return {"443": "OUT-WEB", "80": "OUT-WEB", "53": "OUT-DNS", "123": "OUT-NTP", "25": "OUT-SMTP-GATEWAY"}.get(port, "OUT-APPROVED-SERVICES")
        hn = S.host_of_ip(r["id.resp_h"])
        if hn == "GW-VPN-EMP-01":
            return "IN-EMPLOYEE-VPN"
        if hn == "GW-SYS-JMP-01":
            return "IN-OT-REMOTE-ACCESS"
        if hn == "GW-GW-MAIL-01":
            return "IN-SMTP"
        if hn in ("GW-SRV-WEB-01", "GW-SRV-PORTAL-01"):
            return "IN-PUBLIC-WEB"
        return "IN-DMZ-SERVICES"
    so, sr = segment(zo), segment(zr)
    if zo == "internet":
        return "EXT-TO-OTDMZ-REMOTE-ACCESS"
    return {("IT", "DMZ"): "IT-TO-OTDMZ", ("DMZ", "IT"): "OTDMZ-TO-IT", ("DMZ", "OT"): "OTDMZ-TO-OT", ("OT", "DMZ"): "OT-TO-OTDMZ",
            ("IT", "OT"): "IT-TO-OT-DIRECT", ("OT", "IT"): "OT-TO-IT-DIRECT"}[(so, sr)]


# ---- how the web filter names and rates a destination -------------------------------------------------
_CAT = {
    "coastalbendweather.net": "weather", "txroadwatch.org": "travel-and-transportation", "officesuite-mail.com": "web-based-email",
    "officesuite-cdn.net": "content-delivery-networks", "osupdates-delivery.com": "software-updates", "geomaps-tiles.net": "maps-and-navigation",
    "ledgerfinance-cloud.com": "financial-services", "gridnotices-tx.org": "business-and-economy", "meetroom-video.com": "internet-conferencing",
    "bayside-ledger.example": "news", "harborline6.example": "news", "vantage-security.com": "computer-and-internet-security",
    "meridiancontrols.com": "business-and-economy", "ntp-pool-public.org": "computer-and-internet-info", "fontcdn-static.net": "content-delivery-networks",
    "hrcloud-payroll.com": "business-and-economy", "partsdepot-supply.com": "shopping", "utilitybilling-pay.com": "financial-services",
    "nueces-county-tx.org": "government", "cctexas-services.org": "government", "tx-waterboard.org": "government", "pipefittings-direct.com": "shopping",
    "fleetfuel-cards.com": "financial-services", "docsign-flow.com": "business-and-economy", "searchindex-api.com": "search-engines",
    "adnetwork-static.net": "web-advertisements", "streamvideo-cdn.net": "streaming-media", "socialfeed-img.com": "social-networking",
    "packagetracker-api.net": "business-and-economy", "weatherradar-tiles.com": "weather", "telemetry-osvendor.com": "computer-and-internet-info",
    "browser-safecheck.net": "computer-and-internet-security", "certstatus-ocsp.net": "computer-and-internet-info", "cloudstorage-sync.com": "online-storage-and-backup",
    "helpdesk-tickets.com": "business-and-economy", "training-lms.net": "training-and-tools", "benefits-portal.com": "business-and-economy",
    "scada-vendor-docs.com": "business-and-economy", "relaytech-support.net": "business-and-economy", "pumpworks-service.com": "business-and-economy",
    "gis-basemaps.org": "maps-and-navigation", "newswire-national.com": "news", "airline-bookings.net": "travel-and-transportation",
    "hotel-reservations.com": "travel-and-transportation", "retail-orders.com": "shopping", "bank-online-secure.com": "financial-services",
    "insurance-claims-portal.com": "financial-services", "school-district-cc.org": "educational-institutions", "hospital-patient-portal.org": "health-and-medicine",
    "storm-prep-guides.org": "government", "generator-parts.net": "shopping", "truckrental-fleet.com": "travel-and-transportation",
    "cellcarrier-account.com": "internet-communications-and-telephony", "cdn-jslibs.net": "content-delivery-networks", "cbpwa.example": "business-and-economy",
    "gridcad-software.com": "computer-and-internet-info", "printwave-services.net": "computer-and-internet-info", "backupvault-cloud.net": "online-storage-and-backup",
}
_KEYWORD = [("cdn", "content-delivery-networks"), ("update", "software-updates"), ("ocsp", "computer-and-internet-info"), ("crl", "computer-and-internet-info"),
            ("mail", "web-based-email"), ("weather", "weather"), ("news", "news")]
UNCATEGORISED = "uncategorised"
BLOCKED_SITES = {
    "gambling": ["www.luckyreel-casino.com", "play.bigpot-poker.net", "www.sportsline-bets.com", "m.dailyfantasy-picks.com"],
    "games": ["www.arcadegames-online.net", "play.blockpuzzle-games.com", "cdn.mmo-launcher.net", "www.freegames-portal.org"],
    "peer-to-peer": ["tracker.swarmshare-p2p.net", "www.torrentindex-search.org", "dl.filemesh-peers.net"],
    "proxy-avoidance-and-anonymizers": ["www.hidemyroute-vpn.net", "free.webproxy-tunnel.org", "www.anonbrowse-gateway.com"],
    "dating": ["www.coastalsingles-match.com", "app.meetnearby-dating.net", "www.heartline-dating.org"],
    "auctions": ["www.bidwinner-auctions.com", "www.pennybid-deals.net"],
    "questionable": ["www.prizewinner-survey.net", "www.free-giftcard-rewards.com", "promo.clickbonus-offers.net"],
}
_BLOCK_W = [("gambling", 0.2), ("games", 0.3), ("peer-to-peer", 0.1), ("proxy-avoidance-and-anonymizers", 0.08), ("dating", 0.12),
            ("auctions", 0.06), ("questionable", 0.14)]


def is_ip(host):
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def category_of(host):
    """Category the filter gives a destination name. The same function rates every record."""
    if not host or is_ip(host):
        return "ip-address"
    labels = host.lower().rstrip(".").split(".")
    reg = ".".join(labels[-2:])
    if reg in _CAT:
        return _CAT[reg]
    for cat, sites in BLOCKED_SITES.items():
        if host in sites:
            return cat
    for kw, cat in _KEYWORD:
        if kw in host.lower():
            return cat
    return UNCATEGORISED


def blocked_site(alert_id):
    x, acc = (h32("blk", alert_id) % 10_000) / 10_000, 0.0
    cat = _BLOCK_W[-1][0]
    for c, w in _BLOCK_W:
        acc += w
        if x < acc:
            cat = c
            break
    sites = BLOCKED_SITES[cat]
    return sites[h32("blk-site", alert_id) % len(sites)], cat


_W1 = ["harbor", "lone", "gulf", "bay", "mesa", "river", "delta", "coast", "prairie", "bluff", "tide", "oak", "cedar", "alamo", "brazos", "pecos"]
_W2 = ["works", "media", "labs", "group", "online", "hub", "direct", "point", "systems", "digital", "partners", "supply", "tools", "data"]
_TLD = ["com", "net", "org", "info", "co", "io", "biz"]


def fallback_uncategorised_name(alert_id):
    """Name used for an uncategorised-domain alert when the DNS log has no lookup to take it from."""
    a, b, c = h32("u1", alert_id), h32("u2", alert_id), h32("u3", alert_id)
    return f"{['www', 'app', 'portal', 'm', 'info'][c % 5]}.{_W1[a % len(_W1)]}{_W2[b % len(_W2)]}{c % 97:02d}.{_TLD[(a + b) % len(_TLD)]}"


UA_FAMILIES = [("Edg/", "Edge/Windows"), ("Chrome/", "Chrome/Windows"), ("Firefox/", "Firefox/Windows"), ("Microsoft-CryptoAPI", "Windows-CryptoAPI"),
               ("Windows-Update-Agent", "Windows-Update-Agent"), ("Microsoft-Delivery-Optimization", "Delivery-Optimization"), ("Microsoft BITS", "BITS"),
               ("Microsoft NCSI", "Windows-NCSI"), ("VantageAgent", "Endpoint-Agent"), ("ocsp-client", "OCSP-client"), ("Go-http-client", "Go-http-client"),
               ("curl/", "curl"), ("Java/", "Java"), ("python", "Python"), ("MSIE", "IE/Windows")]
BROWSERS = {"Edge/Windows", "Chrome/Windows", "Firefox/Windows", "IE/Windows"}


def ua_family(ua):
    if not ua or ua in ("-", "(empty)"):
        return "-"
    for k, fam in UA_FAMILIES:
        if k.lower() in ua.lower():
            return fam
    return "other"


class DayNames:
    """Destination names for one UTC day, from what the delivered logs carry: TLS server names, HTTP hosts,
    DNS answers. Falls back to the address."""
    _static = None

    def __init__(self, d):
        self.sni = {r["uid"]: r["server_name"] for r in S.zeek_day(d, "ssl") if r.get("server_name") not in (None, "-", "")}
        self.http = {}
        for r in S.zeek_day(d, "http"):
            self.http.setdefault(r["uid"], []).append(r)
        self.dns, self.dns_uid = {}, {}
        for dd in (d - 1, d):
            for r in S.zeek_day(dd, "dns"):
                if dd == d:
                    self.dns_uid[r["uid"]] = r
                for a in r.get("answers", "").split(","):
                    if a and a != "-":
                        self.dns.setdefault(a, r["query"])
        if DayNames._static is None:                      # the filter reads the TLS server name itself, also where the sensor did not log it
            DayNames._static = {ip: site for site, ips in G.SITE_IPS.items() for ip in ips}

    def host(self, r):
        if r["uid"] in self.sni:
            return self.sni[r["uid"]]
        if r["uid"] in self.http and self.http[r["uid"]][0].get("host") not in (None, "-", ""):
            return self.http[r["uid"]][0]["host"]
        ip = r["id.resp_h"]
        if r["conn_state"] in ("S0", "REJ"):              # no request was ever sent
            return self.dns.get(ip, ip)
        return self.dns.get(ip) or DayNames._static.get(ip) or ip


def is_web_flow(r, zo, zr):
    return zr == "internet" and zo != "internet" and r["proto"] == "tcp" and r["id.resp_p"] in ("80", "443")


# ---- packets ------------------------------------------------------------------------------------------
def _csum(data):
    if len(data) % 2:
        data += b"\0"
    s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return (~s) & 0xFFFF


def _mac(hostname):
    return bytes(int(x, 16) for x in S.mac_of(hostname).split(":"))


MAC_FW_INSIDE = _mac("GW-FW-EDGE-01")
MAC_CORE = _mac("GW-SW-CORE-01")
_SYN_OPTS = bytes([2, 4, 5, 0xB4, 1, 3, 3, 8, 1, 1, 4, 2])          # MSS 1460, NOP, window scale 8, NOP, NOP, SACK permitted
_STACKS = [(bytes([2, 4, 5, 0xB4, 1, 3, 3, 8, 1, 1, 4, 2]), 64240, 30), (bytes([2, 4, 5, 0xB4, 1, 3, 3, 8, 1, 1, 4, 2]), 65535, 22), (None, 64240, 16),
           (bytes([2, 4, 5, 0x64, 1, 3, 3, 9, 1, 1, 4, 2]), 65535, 10), (bytes([2, 4, 5, 0xA0, 1, 1, 4, 2, 1, 3, 3, 10]), 29200, 9), (bytes([2, 4, 5, 0xB4, 1, 1, 4, 2]), 8192, 5),
           (bytes([2, 4, 5, 0x78, 1, 3, 3, 6, 1, 1, 4, 2]), 14600, 8)]


def syn_opts(ip, key=""):
    """(TCP options, window) of the SYN a host sends: a property of its network stack (a few common ones)."""
    k = h32("stack", ip)
    acc, pick = 0, k % 100
    for opts, win, w in _STACKS:
        acc += w
        if pick < acc:
            break
    if opts is None:                                    # a stack that sends timestamps: MSS, SACK permitted, timestamp, NOP, window scale 7
        opts = bytes([2, 4, 5, 0xB4, 4, 2, 8, 10]) + struct.pack("!II", h32("tsval", ip, key), 0) + bytes([1, 3, 3, 7])
    return opts, win
FIN, SYN, RST, PSH, ACK = 1, 2, 4, 8, 16


def ip_packet(src, dst, proto, payload, ttl, ident):
    hdr = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 20 + len(payload), ident & 0xFFFF, 0x4000, ttl, proto, 0,
                      ipaddress.ip_address(src).packed, ipaddress.ip_address(dst).packed)
    return hdr[:10] + struct.pack("!H", _csum(hdr)) + hdr[12:] + payload


def tcp_segment(src, dst, sport, dport, seq, ack, flags, window, data=b"", opts=b""):
    off = (20 + len(opts)) // 4
    hdr = struct.pack("!HHIIBBHHH", sport, dport, seq & 0xFFFFFFFF, ack & 0xFFFFFFFF, off << 4, flags, window, 0, 0) + opts
    pseudo = ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed + struct.pack("!BBH", 0, 6, len(hdr) + len(data))
    c = _csum(pseudo + hdr + data)
    return hdr[:16] + struct.pack("!H", c) + hdr[18:] + data


def udp_datagram(src, dst, sport, dport, data):
    hdr = struct.pack("!HHHH", sport, dport, 8 + len(data), 0)
    pseudo = ipaddress.ip_address(src).packed + ipaddress.ip_address(dst).packed + struct.pack("!BBH", 0, 17, 8 + len(data))
    c = _csum(pseudo + hdr + data) or 0xFFFF
    return hdr[:6] + struct.pack("!H", c) + data


def frame(outbound, ip_pkt):
    """Ethernet frame on the inside interface of the edge firewall. outbound: from the network to the firewall."""
    return (MAC_FW_INSIDE + MAC_CORE if outbound else MAC_CORE + MAC_FW_INSIDE) + b"\x08\x00" + ip_pkt


_CIPHER = {"TLS_AES_128_GCM_SHA256": 0x1301, "TLS_AES_256_GCM_SHA384": 0x1302, "TLS_CHACHA20_POLY1305_SHA256": 0x1303,
           "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384": 0xC030, "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256": 0xC02F,
           "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256": 0xC02B, "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384": 0xC02C,
           "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256": 0xCCA8, "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256": 0xCCA9}


def client_hello(sni, tls13, cipher, key):
    suites = [0x1301, 0x1302, 0x1303, 0xC02B, 0xC02F, 0xC030] if tls13 else [0xC02B, 0xC02F, 0xC02C, 0xC030, 0xCCA8]
    want = _CIPHER.get(cipher)
    if want and want not in suites:
        suites.append(want)
    ext = b""
    if sni and not is_ip(sni):
        name = sni.encode("idna") if all(ord(c) < 128 for c in sni) else sni.encode()
        sn = struct.pack("!BH", 0, len(name)) + name
        ext += struct.pack("!HHH", 0, len(sn) + 2, len(sn)) + sn
    ext += struct.pack("!HHHHH", 10, 6, 4, 0x001D, 0x0017)                                   # supported_groups
    ext += struct.pack("!HHHHH", 13, 6, 4, 0x0804, 0x0403)                                   # signature_algorithms
    if tls13:
        ext += struct.pack("!HHBHH", 43, 5, 4, 0x0304, 0x0303)                               # supported_versions
        ext += struct.pack("!HHHHH", 51, 38, 36, 0x001D, 32) + hbytes(32, "ks", key)         # key_share x25519
    sid = b""
    body = b"\x03\x03" + hbytes(32, "cr", key) + bytes([len(sid)]) + sid + struct.pack("!H", 2 * len(suites)) + b"".join(struct.pack("!H", s) for s in suites) + b"\x01\x00"
    body += struct.pack("!H", len(ext)) + ext
    hs = b"\x01" + struct.pack("!I", len(body))[1:] + body
    return b"\x16\x03\x01" + struct.pack("!H", len(hs)) + hs


def server_hello(tls13, cipher, key):
    code = _CIPHER.get(cipher, 0x1301 if tls13 else 0xC030)
    sid = b"" if tls13 else hbytes(32, "ssid", key)
    ext = b""
    if tls13:
        ext += struct.pack("!HHH", 43, 2, 0x0304) + struct.pack("!HHHH", 51, 36, 0x001D, 32) + hbytes(32, "sks", key)
    else:
        ext += struct.pack("!HHB", 0xFF01, 1, 0)                                              # renegotiation_info
    body = b"\x03\x03" + hbytes(32, "sr", key) + bytes([len(sid)]) + sid + struct.pack("!HB", code, 0) + struct.pack("!H", len(ext)) + ext
    hs = b"\x02" + struct.pack("!I", len(body))[1:] + body
    return b"\x16\x03\x03" + struct.pack("!H", len(hs)) + hs


def app_record(n, key):
    """An opaque TLS application-data record with n bytes of ciphertext."""
    return b"\x17\x03\x03" + struct.pack("!H", n) + hbytes(n, "app", key)


def dns_message(row, response):
    """A DNS query or answer for a delivered dns.log row (A records only)."""
    tid = to_int(row.get("trans_id")) & 0xFFFF
    q = b"".join(bytes([len(x)]) + x.encode("ascii", "replace") for x in row["query"].rstrip(".").split(".") if x) + b"\0" + struct.pack("!HH", 1, 1)
    if not response:
        return struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0) + q
    ans = b""
    n = 0
    for a in row.get("answers", "").split(","):
        if is_ip(a):
            ans += b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, int(float((row.get("TTLs") or "300").split(",")[0])), 4) + ipaddress.ip_address(a).packed
            n += 1
    return struct.pack("!HHHHHH", tid, 0x8180, 1, n, 0, 0) + q + ans


def ntp_message(t, response, key):
    """A 48-byte NTP version 4 client request or server answer."""
    def stamp(x):
        return struct.pack("!II", (int(x) + 2208988800) & 0xFFFFFFFF, int((x % 1) * 2 ** 32) & 0xFFFFFFFF)
    if not response:
        return struct.pack("!BBbb", 0x23, 0, 6, -32) + b"\0" * 36 + stamp(t)
    disp = 300 + h32("ntpd", key) % 900
    return (struct.pack("!BBbbII4s", 0x24, 2, 6, -24, 40 + h32("ntpr", key) % 2000, disp, hbytes(4, "ntpref", key[:4])) +
            stamp(t - 40 - h32("ntpl", key) % 900) + stamp(t - 0.03) + stamp(t - 0.0004) + stamp(t - 0.0003))


def mta_name(ip, domain=None):
    """Host name a mail server announces: taken from the sender's domain where the mail log gives one."""
    if domain:
        return f"{['mail', 'mx1', 'smtp', 'out', 'mta2'][h32('mtan', domain) % 5]}.{domain}"
    return f"mail-{ip.replace('.', '-')}.mailhost-relay.net"


PCAP_GLOBAL = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)


def write_pcap(path, packets):
    """packets: iterable of (epoch float, frame bytes); written in time order."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = 0
    with open(path, "wb") as fh:
        fh.write(PCAP_GLOBAL)
        for t, fr in sorted(packets, key=lambda x: x[0]):
            us = int(round(t * 1_000_000))
            fh.write(struct.pack("<IIII", us // 1_000_000, us % 1_000_000, len(fr), len(fr)) + fr)
            n += 1
    return n


def read_pcap(path, verify=False):
    """Yield dicts for every IPv4 TCP/UDP packet of a classic pcap file: ts, src, dst, sport, dport, proto,
    flags, payload (bytes), plus ok (checksums and lengths consistent) when verify is set."""
    with open(path, "rb") as fh:
        data = fh.read()
    magic = struct.unpack("<I", data[:4])[0]
    if magic != 0xA1B2C3D4:
        raise ValueError("not a little-endian microsecond pcap: " + path)
    off = 24
    while off < len(data):
        sec, usec, caplen, wirelen = struct.unpack("<IIII", data[off:off + 16])
        fr = data[off + 16: off + 16 + caplen]
        off += 16 + caplen
        if fr[12:14] != b"\x08\x00":
            continue
        ip = fr[14:]
        ihl = (ip[0] & 0xF) * 4
        tot = struct.unpack("!H", ip[2:4])[0]
        proto = ip[9]
        p = {"ts": sec + usec / 1e6, "src": str(ipaddress.ip_address(ip[12:16])), "dst": str(ipaddress.ip_address(ip[16:20])), "ttl": ip[8],
             "proto": {6: "tcp", 17: "udp", 1: "icmp"}.get(proto, str(proto)), "sport": 0, "dport": 0, "flags": 0, "payload": b"", "seq": 0, "ack": 0,
             "outbound": fr[0:6] == MAC_FW_INSIDE}
        l4 = ip[ihl:tot]
        if proto == 6:
            p["sport"], p["dport"], p["seq"], p["ack"] = struct.unpack("!HHII", l4[:12])
            doff = (l4[12] >> 4) * 4
            p["flags"] = l4[13]
            p["payload"] = l4[doff:]
        elif proto == 17:
            p["sport"], p["dport"] = struct.unpack("!HH", l4[:4])
            p["payload"] = l4[8:]
        if verify:
            ok = caplen == wirelen == 14 + tot and _csum(ip[:ihl]) == 0
            if proto in (6, 17):
                pseudo = ip[12:20] + struct.pack("!BBH", 0, proto, len(l4))
                ok = ok and _csum(pseudo + l4) == 0
            p["ok"] = ok
        yield p
