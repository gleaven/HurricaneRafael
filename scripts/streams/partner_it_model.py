"""Model behind the IT logs of the other organisations in the scenario (stream family partner_it).

Organisations: the City of Corpus Christi, Naval Air Station Corpus Christi (unclassified administrative
network), Brightwake Marine Systems (vendor of the tankers' cargo-control system, Houston), the Port of
Corpus Christi Authority, two hospitals (Shoreline Regional and Bay City) and Nueces County.

This module holds
  * one profile per organisation (network layout, products, habits) and the registry builder
  * the outside world: access providers and their address space
  * the calendar: who is at work where, which site has power (from canon and the delivered streams)
  * the records canon fixes (message wave, link clicks and the sign-ons that follow; the vendor message and
    click), built by the same functions as everything else
Logs say what happened, never why. No record is marked as unusual.
"""
import bisect
import csv
import datetime as dt
import json
import os

import gen_itsec as G
import netmap
from common import D0_EPOCH, ROOT, SPAN_END, UTC, iso, local_dt, local_ts, rng, ts

DAY = 86400
SPAN_A, SPAN_B = D0_EPOCH - 60 * DAY, D0_EPOCH + 121 * DAY      # 2027-07-16T00:00Z to the end of 2028-01-12 UTC, like the utility's logs
REG_REL = "06_data_streams/partner_it_registry.json"
OUT = "05_other_sources/partner_it"
SRC = os.path.join(ROOT, "05_other_sources")
AUDIT = "05_other_sources/network_logs/audit"
FW_TIME_AT_END = True          # firewall rows are written when the session ends (time_utc = start + duration_s)
hsh = G.hsh

HOLIDAYS = {"2027-09-06": 0.03, "2027-11-25": 0.03, "2027-11-26": 0.35, "2027-12-24": 0.4, "2027-12-25": 0.02, "2027-12-31": 0.5, "2028-01-01": 0.02}
GOV_HOLIDAYS = {"2027-11-11": 0.05, "2027-11-26": 0.05, "2027-12-24": 0.05}
FED_HOLIDAYS = {"2027-10-11": 0.05}
STORM_AFFECTED = {"CITY", "NASCC", "PORT", "SRMC", "BCMC", "COUNTY"}

W11, W11B, W10, LTSC, MAC = "Windows 11 Enterprise 23H2", "Windows 11 Enterprise 24H2", "Windows 10 Enterprise 22H2", "Windows 10 Enterprise LTSC 2021", "macOS 15"
S16, S19, S22, LNX, APPL = "Windows Server 2016", "Windows Server 2019", "Windows Server 2022", "Red Hat Enterprise Linux 9", "Appliance OS 9"

# ---- organisations ------------------------------------------------------------------------------------
# site: (id, name, kind, workstations, third octet, backup power)
#   kind: office = weekday desks; ops24 = consoles staffed round the clock; clinical = shared hospital workstations;
#         gate = daytime, seven days a week
# servers: (name, last octet, role, operating system)
ORGS = {
    "CITY": dict(
        name="City of Corpus Christi", domain="cctexas.example", pfx="CC", net="10.60.0.0/16", public="64.134.20.0/27", gov=True,
        mx=("CITY-MX-02", "192.0.2.150", True), remote=("CC-SSO-01", "64.134.20.10", "city single sign-on", "sso-login"), vpn=False,
        sites=[("CH", "City Hall", "office", 40, 10, False), ("EOC", "Emergency Operations Center", "ops24", 12, 20, True), ("PSB", "Public Safety Building", "ops24", 14, 21, True),
               ("WTR", "Water Department offices", "office", 14, 30, True), ("SVC", "Public Works Service Center", "office", 14, 40, False),
               ("LIB", "Libraries and community centers", "office", 9, 50, False)],
        srv_octet=2, srv_site="PSB", ws_first=31, shift="12h",
        servers=[("DC-01", 10, "Domain controller and DNS resolver", S22), ("DC-02", 11, "Domain controller and DNS resolver", S22), ("FS-01", 20, "File shares", S19),
                 ("FS-02", 21, "File shares (public works)", S19), ("WEBGW-01", 30, "Web gateway (transparent filtering)", APPL), ("EPP-01", 31, "Endpoint protection console", S19),
                 ("ERP-01", 40, "Finance and payroll application", S19), ("PERMIT-01", 42, "Permitting and licensing application", S19), ("GIS-01", 44, "Geographic information system", S22),
                 ("SQL-01", 50, "Database server", S19), ("SQL-02", 51, "Database server", S19), ("PRINT-01", 60, "Print server", S16), ("BKP-01", 70, "Backup server", S19)],
        resolvers=("DC-01", "DC-02"), res_split=0.72,
        os_mix=[(W11, 0.62), (W10, 0.3), (W11B, 0.08)], browsers=[("Edge/Windows", 0.56), ("Chrome/Windows", 0.37), ("Firefox/Windows", 0.07)],
        nat=[2, 3, 4], rules=dict(web="outbound-web", remote="inbound-sso", pub="inbound-published", deny="default-deny-inbound", dns="dns-forwarders", ntp="ntp-out",
                                  icmp="icmp-monitoring", mail_in="inbound-mail", mail_out="outbound-mail", other="outbound-approved-apps"),
        zones=("users", "internet", "dmz", "servers"), end_mix=[("tcp-fin", 0.9), ("tcp-rst-from-server", 0.05), ("tcp-rst-from-client", 0.035), ("aged-out", 0.015)],
        web_rate=1.0, blocked={"gambling", "adult content"}, policy=("default-allow", "category-block"), ep="A", ep_per_day=22, auth_ws="password",
        remote_methods=[("password+token", 0.9), ("password", 0.1)], remote_per_day=150, remote_weekend=(0.42, 0.36), mail_per_day=164, mail_mix=(0.52, 0.31, 0.17),
        spam=0.034, noise_per_day=30, pub_scan=9, providers="local", sector=("gov", "generic"), domains=420),
    "NASCC": dict(
        name="Naval Air Station Corpus Christi (unclassified administrative network)", domain="nascc.navy.example", pfx="NASCC", net="10.61.0.0/16",
        public="162.40.88.0/27", gov=True, fed=True, mx=("NASCC-MX-01", "162.40.88.5", False), remote=("NASCC-OWA-01", "162.40.88.12", "base webmail", "webmail-login"), vpn=False,
        sites=[("ADM", "Administration building", "office", 28, 10, False), ("OPS", "Base operations and command duty office", "ops24", 12, 20, True),
               ("SUP", "Supply and logistics", "office", 16, 30, False), ("PWD", "Public works and fire station", "office", 10, 40, False)],
        srv_octet=4, srv_site="OPS", ws_first=101, shift="8h",
        servers=[("ADS-01", 5, "Directory server and DNS resolver", S19), ("ADS-02", 6, "Directory server and DNS resolver", S19), ("FILE-01", 15, "File shares", S19),
                 ("PRX-01", 25, "Web gateway (transparent filtering)", APPL), ("EPS-01", 26, "Endpoint security console", S19), ("PORTAL-01", 35, "Intranet portal", S19),
                 ("PATCH-01", 36, "Patch distribution", S19), ("BKP-01", 45, "Backup server", S16)],
        resolvers=("ADS-01", "ADS-02"), res_split=0.5,
        os_mix=[(W10, 0.55), (W11, 0.45)], browsers=[("Edge/Windows", 0.88), ("Chrome/Windows", 0.1), ("Firefox/Windows", 0.02)],
        nat=[2], rules=dict(web="TRUST-UNTRUST-WEB", remote="UNTRUST-DMZ-OWA", pub="UNTRUST-DMZ-HTTPS", deny="UNTRUST-DENY-ALL", dns="DNS-FWD", ntp="NTP-EXT",
                            icmp="ICMP-MGMT", mail_in="UNTRUST-DMZ-SMTP", mail_out="DMZ-UNTRUST-SMTP", other="TRUST-UNTRUST-APPROVED"),
        zones=("trust", "untrust", "dmz", "trust"), end_mix=[("tcp-fin", 0.84), ("tcp-rst-from-server", 0.04), ("tcp-rst-from-client", 0.09), ("aged-out", 0.03)],
        web_rate=0.7, blocked={"social media", "streaming media", "gambling", "adult content", "online storage"}, policy=("DON-standard", "DON-category-deny"), ep="B", ep_per_day=14,
        auth_ws="smartcard", remote_methods=[("smartcard", 0.86), ("password+token", 0.09), ("password", 0.05)], remote_per_day=72, remote_weekend=(0.3, 0.26),
        mail_per_day=94, mail_mix=(0.5, 0.36, 0.14), spam=0.012, noise_per_day=18, pub_scan=6, providers="local", sector=("navy", "gov", "generic"), domains=190),
    "BRW": dict(
        name="Brightwake Marine Systems", domain="brightwake-marine.example", pfx="BRW", net="10.80.0.0/16", public="192.0.2.64/26",
        mx=("BRW-MX-01", "192.0.2.68", False), remote=("BRW-VPN-01", "192.0.2.69", "staff VPN", "vpn-login"), vpn=True,
        sites=[("HQ", "Houston office", "office", 28, 1, False), ("NOC", "Remote service desk", "ops24", 5, 2, True)],
        srv_octet=8, srv_site="NOC", ws_first=50, shift="12h",
        servers=[("DC-01", 10, "Domain controller and DNS resolver", S22), ("FILE-01", 12, "Project and document shares", S22), ("GIT-01", 20, "Source repositories", LNX),
                 ("BUILD-01", 21, "Build server", LNX), ("TICKET-01", 30, "Service ticketing", LNX), ("EDR-01", 40, "Endpoint protection console", S22),
                 ("LIC-01", 41, "Engineering licence server", S19)],
        resolvers=("DC-01", "FW-EDGE-01"), res_split=0.9,
        os_mix=[(W11B, 0.5), (W11, 0.32), (MAC, 0.18)], browsers=[("Chrome/Windows", 0.6), ("Edge/Windows", 0.21), ("Firefox/Windows", 0.19)],
        nat=None, rules=dict(web="LAN_to_WAN_web", remote="WAN_to_VPN", pub="WAN_to_DMZ_https", deny="WAN_implicit_deny", dns="LAN_to_WAN_dns", ntp="LAN_to_WAN_ntp",
                             icmp="LAN_to_WAN_icmp", mail_in="WAN_to_DMZ_smtp", mail_out="DMZ_to_WAN_smtp", other="LAN_to_WAN_dev"),
        zones=("lan", "wan", "dmz", "lan"), end_mix=[("tcp-fin", 0.88), ("tcp-rst-from-server", 0.03), ("tcp-rst-from-client", 0.07), ("aged-out", 0.02)],
        web_rate=1.5, blocked={"gambling"}, policy=("allow-all-logged", "blocked-category"), ep="C", ep_per_day=6, auth_ws="password",
        remote_methods=[("password+token", 1.0)], remote_per_day=11, remote_weekend=(0.3, 0.22), mail_per_day=32, mail_mix=(0.55, 0.22, 0.23),
        spam=0.05, noise_per_day=13, pub_scan=8, providers="houston", sector=("eng", "maritime", "generic"), domains=170),
    "PORT": dict(
        name="Port of Corpus Christi Authority", domain="portofcc.example", pfx="PCCA", net="10.90.0.0/16", public="69.15.201.0/27", gov=True,
        mx=("PCCA-MX-01", "69.15.201.5", False), remote=("PCCA-VPN-01", "69.15.201.6", "staff VPN", "vpn-login"), vpn=True,
        sites=[("ADM", "Administration building", "office", 22, 10, False), ("SEC", "Port security and operations center", "ops24", 10, 20, True),
               ("HMO", "Harbormaster and vessel traffic information office", "ops24", 8, 21, True), ("GATE", "Terminal gate offices", "gate", 8, 30, False)],
        srv_octet=5, srv_site="SEC", ws_first=21, shift="12h",
        servers=[("DC-01", 5, "Domain controller and DNS resolver", S19), ("DC-02", 6, "Domain controller and DNS resolver", S19), ("FILE-01", 20, "File shares", S19),
                 ("VTIS-01", 31, "Vessel traffic information server", S19), ("GOS-01", 32, "Gate operating system", S19), ("CCTV-01", 33, "Video management server", S16),
                 ("ERP-01", 40, "Finance and tariff billing", S19), ("PRX-01", 50, "Web gateway (transparent filtering)", APPL), ("EDR-01", 51, "Endpoint protection console", S19),
                 ("BKP-01", 61, "Backup server", S19)],
        resolvers=("DC-01", "DC-02"), res_split=0.65,
        os_mix=[(W11, 0.7), (W10, 0.3)], browsers=[("Edge/Windows", 0.47), ("Chrome/Windows", 0.45), ("Firefox/Windows", 0.08)],
        nat=[2, 3], rules=dict(web="allow-outbound-http-https", remote="allow-inbound-vpn", pub="allow-inbound-https", deny="deny-inbound-default", dns="allow-dns-forward",
                               ntp="allow-ntp", icmp="allow-icmp-probe", mail_in="allow-inbound-smtp", mail_out="allow-outbound-smtp", other="allow-outbound-maritime-apps"),
        zones=("inside", "outside", "dmz", "inside"), end_mix=[("tcp-fin", 0.93), ("tcp-rst-from-server", 0.045), ("tcp-rst-from-client", 0.02), ("aged-out", 0.005)],
        web_rate=1.0, blocked={"streaming media", "gambling", "adult content"}, policy=("standard-user", "blocked-by-category"), ep="A", ep_per_day=9, auth_ws="password",
        remote_methods=[("password+token", 0.97), ("password", 0.03)], remote_per_day=12, remote_weekend=(0.25, 0.2), mail_per_day=47, mail_mix=(0.56, 0.26, 0.18),
        spam=0.028, noise_per_day=17, pub_scan=5, providers="local", sector=("maritime", "gov", "generic"), domains=200),
    "SRMC": dict(
        name="Shoreline Regional Medical Center", domain="shorelineregional.example", pfx="SRMC", net="10.110.0.0/16", public="96.88.14.0/27",
        mx=("SRMC-MX-01", "96.88.14.5", False), remote=("SRMC-VPN-01", "96.88.14.6", "clinician remote access", "vpn-login"), vpn=True, facility="FAC-SRMC-001",
        sites=[("CLIN", "Clinical floors and emergency department", "clinical", 30, 10, True), ("ADM", "Administration and business office", "office", 20, 30, False)],
        srv_octet=0, srv_site="CLIN", ws_first=40, shift="12h",
        servers=[("DC-01", 10, "Domain controller and DNS resolver", S19), ("DC-02", 11, "Domain controller and DNS resolver", S19), ("EHR-APP-01", 20, "Electronic health record application", S19),
                 ("EHR-APP-02", 21, "Electronic health record application", S19), ("EHR-DB-01", 25, "Electronic health record database", S19), ("PACS-01", 30, "Imaging archive", S19),
                 ("LIS-01", 31, "Laboratory information system", S16), ("RX-01", 32, "Pharmacy system", S19), ("IFACE-01", 35, "Interface engine", S19), ("FILE-01", 40, "File shares", S19),
                 ("PRX-01", 50, "Web gateway (transparent filtering)", APPL), ("EDR-01", 51, "Endpoint protection console", S19), ("BKP-01", 60, "Backup server", S19)],
        resolvers=("DC-01", "DC-02"), res_split=0.6,
        os_mix=[(LTSC, 0.58), (W10, 0.22), (W11, 0.2)], browsers=[("Edge/Windows", 0.71), ("Chrome/Windows", 0.27), ("Firefox/Windows", 0.02)],
        nat=[2], rules=dict(web="OUT-WEB-STD", remote="IN-VPN-CLIN", pub="IN-HTTPS-PUB", deny="IN-DENY", dns="OUT-DNS", ntp="OUT-NTP", icmp="OUT-ICMP", mail_in="IN-SMTP",
                            mail_out="OUT-SMTP", other="OUT-CLINICAL-PARTNERS"),
        zones=("clinical", "internet", "dmz", "datacenter"), end_mix=[("tcp-fin", 0.91), ("tcp-rst-from-server", 0.06), ("tcp-rst-from-client", 0.02), ("aged-out", 0.01)],
        web_rate=0.75, blocked={"streaming media", "social media", "gambling", "adult content"}, policy=("clinical-workstation", "category-denied"), ep="B", ep_per_day=12,
        auth_ws="password", remote_methods=[("password+token", 1.0)], remote_per_day=34, remote_weekend=(0.78, 0.72), mail_per_day=62, mail_mix=(0.47, 0.39, 0.14),
        spam=0.041, noise_per_day=22, pub_scan=7, providers="local", sector=("health", "generic"), domains=270),
    "BCMC": dict(
        name="Bay City Medical Center", domain="baycitymedical.example", pfx="BCMC", net="10.112.0.0/16", public="104.190.33.0/27",
        mx=("BCMC-MX-01", "104.190.33.5", False), remote=("BCMC-VPN-01", "104.190.33.6", "clinician remote access", "vpn-login"), vpn=True, facility="FAC-BCMC-002",
        sites=[("CLIN", "Clinical floors and emergency department", "clinical", 22, 10, True), ("ADM", "Administration and business office", "office", 14, 30, False)],
        srv_octet=1, srv_site="CLIN", ws_first=25, shift="8h",
        servers=[("DC-01", 5, "Domain controller and DNS resolver", S16), ("EHR-01", 10, "Electronic health record (hosted client gateway)", S19), ("PACS-01", 12, "Imaging archive", S16),
                 ("LAB-01", 14, "Laboratory system", S16), ("FILE-01", 20, "File shares", S19), ("WEBGW-01", 30, "Web gateway (transparent filtering)", APPL),
                 ("AV-01", 31, "Endpoint protection console", S19), ("BKP-01", 40, "Backup server", S16)],
        resolvers=("DC-01", "FW-EDGE-01"), res_split=0.95,
        os_mix=[(W10, 0.64), (LTSC, 0.26), (W11, 0.1)], browsers=[("Chrome/Windows", 0.61), ("Edge/Windows", 0.37), ("Firefox/Windows", 0.02)],
        nat=[2], rules=dict(web="outbound web", remote="remote access vpn", pub="inbound https", deny="cleanup deny", dns="dns to isp", ntp="ntp", icmp="ping out",
                            mail_in="mail in", mail_out="mail out", other="clinical partners out"),
        zones=("inside", "outside", "dmz", "inside"), end_mix=[("tcp-fin", 0.95), ("tcp-rst-from-server", 0.03), ("tcp-rst-from-client", 0.015), ("aged-out", 0.005)],
        web_rate=0.9, blocked={"streaming media", "gambling", "adult content"}, policy=("default", "web-filter-block"), ep="C", ep_per_day=9, auth_ws="password",
        remote_methods=[("password+token", 0.93), ("password", 0.07)], remote_per_day=21, remote_weekend=(0.8, 0.7), mail_per_day=41, mail_mix=(0.5, 0.36, 0.14),
        spam=0.056, noise_per_day=10, pub_scan=4, providers="local", sector=("health", "generic"), domains=210),
    "COUNTY": dict(
        name="Nueces County", domain="nuecesco.example", pfx="NC", net="10.70.0.0/16", public="199.21.76.0/27", gov=True,
        mx=("NUECES-MX-01", "199.21.76.5", False), remote=("NC-VPN-01", "199.21.76.6", "staff VPN", "vpn-login"), vpn=True,
        sites=[("CTH", "County Courthouse", "office", 30, 10, False), ("EOC", "Emergency Operations Center", "ops24", 12, 20, True), ("SO", "Sheriff's Office", "ops24", 12, 21, True),
               ("PH", "Public Health District", "office", 10, 30, False)],
        srv_octet=3, srv_site="SO", ws_first=60, shift="12h",
        servers=[("DC-01", 5, "Domain controller and DNS resolver", S19), ("DC-02", 6, "Domain controller and DNS resolver", S16), ("FILE-01", 18, "File shares", S19),
                 ("COURTS-01", 22, "Court case management", S16), ("TAX-01", 23, "Tax office application", S19), ("JMS-01", 24, "Jail management system", S16),
                 ("GIS-01", 28, "Geographic information system", S19), ("PRX-01", 34, "Web gateway (transparent filtering)", APPL), ("EDR-01", 35, "Endpoint protection console", S19),
                 ("BKP-01", 48, "Backup server", S19)],
        resolvers=("DC-01", "DC-02"), res_split=0.8,
        os_mix=[(W10, 0.48), (W11, 0.52)], browsers=[("Edge/Windows", 0.5), ("Chrome/Windows", 0.31), ("Firefox/Windows", 0.19)],
        nat=[2, 3], rules=dict(web="Users-Internet", remote="Internet-VPN", pub="Internet-DMZ-Web", deny="Internet-Deny", dns="DNS-Forward", ntp="NTP-Out", icmp="Ping-Out",
                               mail_in="Internet-Mail", mail_out="Mail-Internet", other="Users-StateSystems"),
        zones=("Users", "Internet", "DMZ", "Servers"), end_mix=[("tcp-fin", 0.89), ("tcp-rst-from-server", 0.07), ("tcp-rst-from-client", 0.03), ("aged-out", 0.01)],
        web_rate=1.1, blocked={"gambling", "streaming media", "adult content"}, policy=("County-Default", "County-Blocked"), ep="A", ep_per_day=11, auth_ws="password",
        remote_methods=[("password+token", 0.95), ("password", 0.05)], remote_per_day=14, remote_weekend=(0.3, 0.24), mail_per_day=56, mail_mix=(0.54, 0.3, 0.16),
        spam=0.03, noise_per_day=16, pub_scan=5, providers="local", sector=("gov", "generic"), domains=250),
}
ORG_IDS = list(ORGS)

# identifiers other delivered streams already use
CITY_MB = [f"{hsh('c', i, n=7)}@cctexas.example" for i in range(900)]
NAS_MB = [f"{hsh('n', i, n=7)}@nascc.navy.example" for i in range(400)]
BRW_ENG = {"bw-eng-01": "o.pryce", "bw-eng-02": "j.tran", "bw-eng-03": "l.hart", "bw-eng-04": "d.silva", "bw-eng-05": "s.adeyemi", "bw-eng-06": "k.brandt",
           "bw-eng-07": "m.okoye", "bw-eng-08": "r.nakamura", "bw-eng-09": "t.velasquez", "svc-admin": "it.admin"}
BRW_SHARED = ("service.desk", "remote.support", "accounts")
BRW_GATEWAY = ("rmt-gw.brightwake.example", "192.0.2.70")          # gw_host_registry external system EXT-BRW-RMT-01
BRW_OFFICE_POOL = list(netmap.VENDOR_OFFICE)                         # office egress addresses (the vessel remote-session log shows them)
BRW_VPN_POOL = list(netmap.VENDOR_VPN)                               # staff VPN egress addresses
BRW_NAT_RES, BRW_UPSTREAM = "192.0.2.71", "192.0.2.94"               # resolver egress; the provider's router
NAS_PORTAL_VIP = "162.40.88.22"                                     # public address of the base logistics system (EXT-NASLOG-02)
ALERT_HOST = "origination.alertgateway.example"
ALERT_SOURCES = {"NCOEM": ("COUNTY", "NC-EOC-ALERT-01"), "CCOEM": ("CITY", "CC-EOC-ALERT-01"),
                 "Corpus Christi Water Department": ("CITY", "CC-WTR-ALERT-01"), "Corpus Christi Water Department / CBPWA": ("CITY", "CC-WTR-ALERT-01")}
LURE_HOST, LURE_DOM = "aid-help-portal.example", "aid-help-portal.example"
LURE_SUBJECT = "Disaster assistance: confirm your account to receive aid"
WAVE_A, WAVE_B = ts("2027-09-15T13:00Z"), ts("2027-09-18T02:00Z")
WAVE_N = {"CITY": 840, "NASCC": 360}
CLICK_N = {"CITY": 7, "NASCC": 3}
BRW_LURE_T = ts("2027-08-12T14:41Z") + 7
BRW_LURE_DOM, BRW_LURE_HOST = "marine-certification-notices.example", "certificates.marine-certification-notices.example"
BRW_CLICK_T = BRW_LURE_T + 1260
BRW_CLICK_PERSON = BRW_ENG["bw-eng-07"]     # the duty engineer who handled the shared mailbox that day
BRW_CLICK_NAT = netmap.VENDOR_OFFICE[3]
EXTRACT_WIN = {"CITY": (D0_EPOCH - 2 * DAY, D0_EPOCH + 8 * DAY), "NASCC": (D0_EPOCH - 2 * DAY, D0_EPOCH + 8 * DAY), "BRW": (D0_EPOCH - 60 * DAY, D0_EPOCH - 20 * DAY)}


def read_csv(rel):
    with open(os.path.join(SRC, rel), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pub(org, n):
    return ORGS[org]["public"].rsplit(".", 1)[0] + f".{n}"


def base(org):
    return ORGS[org]["net"].split("/")[0].rsplit(".", 2)[0]                  # e.g. 10.60


def lday(t):
    """Local scenario day of an epoch (Central time, without the hour of the autumn clock change)."""
    return int((t - D0_EPOCH - 5 * 3600) // DAY)


def pick(pairs, x):
    """Weighted choice from [(value, weight)] with a number x in [0, 1)."""
    tot = sum(w for _, w in pairs)
    acc = 0.0
    for v, w in pairs:
        acc += w / tot
        if x < acc:
            return v
    return pairs[-1][0]


def hint(*k):
    return int(hsh(*k, n=12), 16)


def h01(*k):
    return hint(*k) / float(1 << 48)


# ---- the outside world: one address table for every stream (netmap) ---------------------------------------
RES = [f"ASN {n}" for n in netmap.RES]
MOBILE = [(f"ASN {n}", w) for n, w in netmap.MOBILE]


def home_of(org, acct, t=0):
    """(address, network label) an account normally signs on from. The provider is fixed; a household's address
    changes every few weeks, as residential addresses do."""
    ip, n = netmap.home(("partner", org, acct), ORGS[org]["providers"], epoch=int(t // (23 * DAY)) + hint("ph", acct) % 23)
    return ip, f"ASN {n}"


def away_of(org, acct, g):
    """(address, label) for a sign-on away from home: a phone, a hotel, a relative's house."""
    k = int(g.integers(1 << 40))
    ip, n = netmap.mobile(("away", org, acct, k)) if g.random() < 0.6 else netmap.home(("away", org, acct, k), ORGS[org]["providers"])
    return ip, f"ASN {n}"


def small_provider(label):
    """Whether a network label is one of the small local providers."""
    return int(label.split()[1]) in netmap.DOC.values()


def outside_ip(g):
    """An address somewhere on the internet (servers, scanners, crawlers; now and then a household)."""
    k = int(g.integers(1 << 40))
    return netmap.home(("rnd", k))[0] if g.random() < 0.17 else netmap.hosted(("rnd", k))[0]


def stable_ip(*key):
    """A fixed outside server address for a name."""
    return netmap.hosted(("srv",) + key)[0]


def site_ips(name):
    """Addresses of an outside web site: the utility logs' addresses when the name appears there, otherwise stable invented ones."""
    if name in G.SITE_IPS:
        return G.SITE_IPS[name]
    if name == BRW_GATEWAY[0]:
        return [BRW_GATEWAY[1]]
    h = hint("site", name)
    return [stable_ip("site", name, k) for k in range(1 + h % 3)]


# ---- registry --------------------------------------------------------------------------------------------
def _os(mix, key):
    return pick(mix, h01("os", key))


def build_registry():
    """Write the registry. Deterministic."""
    orgs = []
    for oid, o in ORGS.items():
        b, p, dom = base(oid), o["pfx"], o["domain"]
        hosts, accounts = [], []

        def add(hid, ip, role, os_, dtype, site, users=None, **kw):
            h = {"host_id": hid, "hostname": hid, "ip": ip, "site_id": site, "device_type": dtype, "role": role, "os": os_}
            if users:
                h["users"] = users
            h.update(kw)
            hosts.append(h)

        for name, last, role, os_ in o["servers"]:
            add(f"{p}-{name}", f"{b}.{o['srv_octet']}.{last}", role, os_, "server", "DC")
        add(f"{p}-FW-EDGE-01", f"{b}.{o['srv_octet']}.1", "Internet edge firewall", "Firewall OS 7", "firewall", "DC")
        add(o["mx"][0], o["mx"][1], "Mail security gateway" + (" (hosted service)" if o["mx"][2] else ""), APPL, "mail gateway", "HOSTED" if o["mx"][2] else "DMZ")
        add(o["remote"][0], o["remote"][1], f"Remote sign-on service ({o['remote'][2]})", APPL, "remote access", "DMZ")
        if oid == "NASCC":
            add("NASCC-LOG02", "10.200.8.22", "Base logistics system (fuel and supply ordering), public address " + NAS_PORTAL_VIP, S19, "server", "LOG",
                external_system_id="EXT-NASLOG-02", fqdn="log02.nascc.example")
        if oid == "BRW":
            add("BRW-RMT-GW-01", BRW_GATEWAY[1], "Remote-maintenance gateway to shipboard cargo-control systems", APPL, "remote access", "DMZ",
                external_system_id="EXT-BRW-RMT-01", fqdn=BRW_GATEWAY[0])
            add("BRW-FW-DMZ-01", "192.0.2.65", "Firewall in front of the remote-maintenance gateway", "Firewall OS 7", "firewall", "DMZ")
        # people
        if oid == "CITY":
            pool = [m.split("@")[0] for m in CITY_MB]
        elif oid == "NASCC":
            pool = [m.split("@")[0] for m in NAS_MB]
        elif oid == "BRW":
            pool = list(dict.fromkeys(list(BRW_ENG.values()) + ["accounts.ap", "c.whitlock", "e.morrow", "f.okafor", "g.lindqvist", "h.tanaka", "i.reyes", "n.farrow",
                                                                  "p.dunmore", "q.abara", "u.sorensen", "v.castell", "w.ibarra", "y.kessler", "z.pemberton", "a.rooke", "b.strand",
                                                                  "c.amadi", "d.verhoeven", "e.salcedo", "f.hollis", "g.navarro", "h.oyelaran", "i.brandvold", "j.estrada",
                                                                  "k.marlowe", "l.petrov", "m.quince", "n.adeola", "o.ferris", "p.achebe", "r.lindholm", "s.marchetti", "t.oduya",
                                                                  "u.valdivia", "v.haraldsen", "w.kowalczyk", "x.demir", "y.okonkwo", "z.ferreira", "a.thorsen", "b.nwosu"]))
        else:
            need = sum(n * users_per(o, kind) for _, _, kind, n, _, _ in o["sites"])
            pool = [hsh(oid, "acct", i, n=7) for i in range(int(need * 1.25) + 12)]
        # workstation users are spread through the directory, not taken from its start
        order = sorted(range(len(pool)), key=lambda i: hint("deskorder", oid, pool[i])) if oid != "BRW" else list(range(len(pool)))
        free = [pool[i] for i in order]
        k = 0
        for sid, sname, kind, n, octet, _bp in o["sites"]:
            m = users_per(o, kind)
            for i in range(n):
                hid = f"{p}-{sid}-WS-{i + 1:03d}"
                last = o["ws_first"] + i if oid in ("CITY", "PORT", "BRW") else o["ws_first"] + (i * 3 + hint("wsaddr", oid, sid) % 3) % 150
                users = free[k:k + m]
                k += m
                dtype = {"office": "workstation", "gate": "workstation", "ops24": "console", "clinical": "clinical workstation"}[kind]
                add(hid, f"{b}.{octet}.{last}", f"Workstation, {sname}", _os(o["os_mix"], hid), dtype, sid, users)
        if oid == "CITY":
            add("CC-EOC-ALERT-01", f"{b}.20.11", "Public alerting workstation, Office of Emergency Management", W11, "console", "EOC", free[k:k + 4])
            add("CC-WTR-ALERT-01", f"{b}.30.11", "Public notice workstation, Water Department", W11, "workstation", "WTR", [free[k + 4]])
            k += 5
        if oid == "COUNTY":
            add("NC-EOC-ALERT-01", f"{b}.20.11", "Public alerting workstation, Office of Emergency Management", W11, "console", "EOC", free[k:k + 4])
            k += 4
        used = {u for h in hosts for u in h.get("users", [])}
        admins = set(free[k:k + (4 if oid in ("CITY", "SRMC") else 2)])
        for a in pool:
            rec = {"account": a, "mailbox": f"{a}@{dom}", "kind": "staff", "workstation_user": a in used}
            if a in admins:
                rec["role"] = "IT administrator"
            accounts.append(rec)
        if oid == "BRW":
            for a in BRW_SHARED:
                accounts.append({"account": a, "mailbox": f"{a}@{dom}", "kind": "shared mailbox", "workstation_user": False})
            for acct, person in BRW_ENG.items():
                accounts.append({"account": acct, "kind": "remote-maintenance gateway account", "person": person, "workstation_user": False})
        for a in {"COUNTY": ["eoc.pio", "county.clerk", "hr"], "PORT": ["port.operations", "tariff.billing", "hr"], "CITY": ["hr", "it.helpdesk", "city.secretary"],
                  "NASCC": ["quarterdeck", "admin.office"], "SRMC": ["nursing.admin", "hr", "it.servicedesk"], "BCMC": ["hr", "it.support"], "BRW": ["hr"]}.get(oid, []):
            accounts.append({"account": a, "mailbox": f"{a}@{dom}", "kind": "shared mailbox", "workstation_user": False})
        sites = [{"site_id": s[0], "name": s[1], "kind": s[2], "subnet": f"{b}.{s[4]}.0/24", "backup_power": s[5]} for s in o["sites"]]
        srv_at = next(s[1] for s in o["sites"] if s[0] == o["srv_site"])
        sites.append({"site_id": "DC", "name": f"Server room ({srv_at})", "kind": "server room", "subnet": f"{b}.{o['srv_octet']}.0/24", "backup_power": True})
        sites.append({"site_id": "DMZ", "name": "Published services", "kind": "dmz", "subnet": o["public"] if oid != "BRW" else "192.0.2.64/28", "backup_power": True})
        if o["mx"][2]:
            sites.append({"site_id": "HOSTED", "name": "Services hosted outside the organisation's network", "kind": "hosted", "subnet": "192.0.2.0/24", "backup_power": True})
        plan = {"internal": o["net"], "servers": f"{b}.{o['srv_octet']}.0/24"}
        if oid == "BRW":
            plan["public_block"] = o["public"]
            plan["office_egress"] = f"{BRW_OFFICE_POOL[0]}-{BRW_OFFICE_POOL[-1].rsplit('.', 1)[1]} (workstations leave through a pool; an address is kept for about an hour and a half)"
            plan["vpn_egress"] = f"{BRW_VPN_POOL[0]}-{BRW_VPN_POOL[-1].rsplit('.', 1)[1]}"
        else:
            plan["public_block"] = o["public"]
        if o["vpn"]:
            plan["vpn_pool"] = f"{b}.250.0/24"
        if oid == "NASCC":
            sites.append({"site_id": "LOG", "name": "Logistics enclave", "kind": "enclave", "subnet": "10.200.8.0/24", "backup_power": True})
            plan["logistics_enclave"] = "10.200.8.0/24"
        orgs.append({"org_id": oid, "name": o["name"], "domain": dom, "address_plan": plan, "edge_firewall": f"{p}-FW-EDGE-01", "mail_gateway": o["mx"][0],
                     "remote_sign_on": {"host": o["remote"][0], "public_ip": o["remote"][1], "service": o["remote"][2]},
                     "dns_resolvers": [next(h["ip"] for h in hosts if h["host_id"] == f"{p}-{r}") for r in o["resolvers"]], "facility_id": o.get("facility"),
                     "sites": sites, "hosts": hosts, "accounts": accounts})
    reg = {"metadata": {"purpose": "Hosts, addresses and accounts of the organisations whose IT logs are in 05_other_sources/partner_it/. Real agencies and places; people are pseudonymous or invented.",
                        "id_columns": {"host": "host_id", "client_ip / src_ip": "ip", "account / user": "account"}},
           "organisations": orgs}
    with open(os.path.join(ROOT, REG_REL), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(reg, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    _reg.clear()
    return reg


def users_per(o, kind):
    return {"office": 1, "gate": 2, "clinical": 6, "ops24": 6 if o["shift"] == "8h" else 4}[kind]


_reg = {}


def registry():
    if not _reg:
        with open(os.path.join(ROOT, REG_REL), encoding="utf-8") as fh:
            for o in json.load(fh)["organisations"]:
                _reg[o["org_id"]] = o
    return _reg


def mailboxes(org):
    return [a["mailbox"] for a in registry()[org]["accounts"] if a.get("mailbox")]


# ---- calendar: power and staffing ------------------------------------------------------------------------
def hospital_power(fac):
    """(lost, generator start, restored) for a hospital, from the delivered capacity reports."""
    lost = gen = back = None
    for r in read_csv("public_health/hospital_capacity.csv"):
        if r["Facility_ID"] == fac:
            lost = lost or (r["Commercial_Power_Lost_UTC"] and ts(r["Commercial_Power_Lost_UTC"]))
            gen = gen or (r["Generator_Start_UTC"] and ts(r["Generator_Start_UTC"]))
            back = back or (r["Commercial_Power_Restored_UTC"] and ts(r["Commercial_Power_Restored_UTC"]))
    return lost, gen, back


def nas_power():
    """Commercial power windows at the air station from the delivered base status reports:
    (storm outage start, end), (interruption on the day the backup generator failed: start, end)."""
    on_gen, failed = [], []
    for r in read_csv("maintenance/base_status_reports.csv"):
        if r["installation_id"] != "FAC-DOD-01":
            continue
        if r["backup_power_status"].startswith("carrying load"):
            on_gen.append(r["report_date"])
        if r["backup_power_status"].startswith("FAILED"):
            failed.append(r["report_date"])
    a = ts("2027-09-14T06:35Z")
    b = ts(max(on_gen) + "T00:00Z") + DAY + 14 * 3600 + 40 * 60 if on_gen else a + 3 * DAY
    f0 = ts(min(failed) + "T00:00Z") if failed else ts("2027-10-24T00:00Z")
    return (a, b), (f0 + 18 * 3600 + 52 * 60, f0 + 23 * 3600 + 47 * 60)


_out = {}


def outages(org):
    """{site_id: [(start, end)]}: periods with no power at a site (workstations and local network down)."""
    if org in _out:
        return _out[org]
    o = {}
    if org == "CITY":
        o = {"CH": [(ts("2027-09-14T06:48Z"), ts("2027-09-18T15:20Z"))], "SVC": [(ts("2027-09-14T07:10Z"), ts("2027-09-20T16:00Z"))],
             "LIB": [(ts("2027-09-14T07:02Z"), ts("2027-09-23T18:00Z"))]}
    elif org == "COUNTY":
        o = {"CTH": [(ts("2027-09-14T06:55Z"), ts("2027-09-18T17:05Z"))], "PH": [(ts("2027-09-14T07:20Z"), ts("2027-09-16T14:00Z"))]}
    elif org == "PORT":
        w = (ts("2027-09-14T06:41Z"), ts("2027-09-18T20:00Z"))
        o = {"ADM": [w], "GATE": [w]}
    elif org == "NASCC":
        storm, fail = nas_power()
        o = {s: [storm, fail] for s in ("ADM", "SUP", "PWD")}
        o["OPS"] = [fail]                                   # critical loads ride the generator in the storm; it fails on the later day
    elif org in ("SRMC", "BCMC"):
        lost, gen, back = hospital_power(ORGS[org]["facility"])
        o = {"CLIN": [(lost, gen + (9 if org == "SRMC" else 14) * 60)], "ADM": [(lost, back)]}
    _out[org] = o
    return o


def powered(org, site, t):
    return not any(a <= t < b for a, b in outages(org).get(site, []))


def edge_up(org, t):
    """The server room and edge are on backup power everywhere except the air station on the evening its generator failed."""
    return powered(org, ORGS[org]["srv_site"], t)


_zulu = []


def zulu_time():
    """Issue time of Port Condition Zulu (delivered supply/port_conditions.csv)."""
    if not _zulu:
        _zulu.append(min(ts(r["issued_utc"]) for r in read_csv("supply/port_conditions.csv") if r["port_condition"] == "ZULU" and r["issued_utc"]))
    return _zulu[0]


def port_factor(d):
    """Share of normal truck-gate activity by port state (port conditions and canon port.channel_windows)."""
    if d < -3:
        return 1.0
    if d <= -1:
        return 0.8                                         # winding down under X-RAY and YANKEE; the gates close when ZULU is set
    if d <= 3:
        return 0.0
    if d < 30:
        return 0.25
    if d < 44:
        return 0.6
    if d < 58:
        return 0.35
    return 1.0


def staff(org, site, d):
    """Share of desks occupied at an office site on local scenario day d (before weekends and holidays)."""
    if org == "BRW":
        return 1.0
    if org == "CITY":
        return {"CH": 0.5 if d == -1 else (0.0 if 0 <= d <= 5 else (0.7 if 6 <= d <= 13 else 1.0)),
                "WTR": 0.55 if -1 <= d <= 5 else 1.0, "SVC": 0.0 if 0 <= d <= 2 else (0.8 if 3 <= d <= 13 else 1.0),
                "LIB": 0.0 if -2 <= d <= 13 else 1.0, "EOC": 1.0}.get(site, 1.0)
    if org == "COUNTY":
        return {"CTH": 0.5 if d == -1 else (0.0 if 0 <= d <= 5 else (0.7 if 6 <= d <= 13 else 1.0)), "PH": 0.6 if 0 <= d <= 6 else 1.0}.get(site, 1.0)
    if org == "NASCC":
        if site == "ADM":                                    # the administration building empties with the evacuation order
            return 0.3 if d == -4 else (0.03 if -3 <= d <= 5 else (0.7 if 6 <= d <= 13 else 1.0))
        b = 0.5 if -4 <= d <= -1 else (0.1 if 0 <= d <= 5 else (0.7 if 6 <= d <= 13 else 1.0))
        return max(b, 0.3) if site == "SUP" and 0 <= d <= 5 else b
    if org == "PORT":
        if site == "GATE":
            return port_factor(d)
        return 0.4 if d == -1 else (0.0 if 0 <= d <= 5 else (0.7 if 6 <= d <= 13 else 1.0))
    if org in ("SRMC", "BCMC"):
        return 0.6 if d == -1 else (0.15 if 0 <= d <= 2 else (0.6 if 3 <= d <= 8 else 1.0))
    return 1.0


def round_the_clock(org, site, d):
    """Whether an ops24 site is staffed day and night on local day d (emergency operations centres only when activated)."""
    if site == "EOC":
        return (-3 if org == "CITY" else -5) <= d <= 35
    return True


def closes_at_noon(org, site, d):
    return d == -1 and (org, site) in {("CITY", "CH"), ("COUNTY", "CTH"), ("PORT", "ADM")}


def holiday_factor(org, d):
    key = local_dt(local_ts(d, "12:00")).strftime("%Y-%m-%d")
    f = HOLIDAYS.get(key, 1.0)
    o = ORGS[org]
    if o.get("gov"):
        f = min(f, GOV_HOLIDAYS.get(key, 1.0))
    if o.get("fed"):
        f = min(f, FED_HOLIDAYS.get(key, 1.0))
    return f


def day_factor(org, d):
    f = holiday_factor(org, d)
    if local_dt(local_ts(d, "12:00")).weekday() >= 5:
        f = min(f, 0.04)
    return f


def remote_factor(org, d):
    """Share of an ordinary weekday's remote sign-ons on local day d: weekends, holidays, the storm and the weeks of
    working from home that followed it."""
    wd = local_dt(local_ts(d, "12:00")).weekday()
    f = 1.0 if wd < 5 else ORGS[org]["remote_weekend"][wd - 5]
    hol = holiday_factor(org, d)
    if hol < 1:
        f = min(f, 0.2 + 0.45 * hol) if ORGS[org]["sector"][0] != "health" else f * 0.8
    if org in ("CITY", "COUNTY", "PORT"):
        f *= {-1: 0.85, 0: 0.16, 1: 0.27, 2: 0.4, 3: 0.55, 4: 0.85, 5: 0.9}.get(d, 1.22 if 6 <= d <= 13 else 1.0)
    elif org == "NASCC":
        f *= 0.6 if -4 <= d <= -1 else {0: 0.1, 1: 0.2, 2: 0.3, 3: 0.4, 4: 0.55, 5: 0.6}.get(d, 0.9 if 6 <= d <= 13 else 1.0)
    elif org in ("SRMC", "BCMC"):
        f *= {-1: 0.8, 0: 0.22, 1: 0.42, 2: 0.6, 3: 0.75}.get(d, 1.12 if 4 <= d <= 10 else 1.0)
    return f


_ed = {}


def ed_factor(org, d):
    """Emergency-department workload relative to the facility's pre-storm mean, from the delivered capacity reports."""
    if org not in _ed:
        rows = [r for r in read_csv("public_health/hospital_capacity.csv") if r["Facility_ID"] == ORGS[org]["facility"] and r["ED_Visits_24h"]]
        b = sum(int(r["ED_Visits_24h"]) for r in rows if r["Report_Date"] < "2027-09-10") / max(1, sum(1 for r in rows if r["Report_Date"] < "2027-09-10"))
        _ed[org] = {r["Report_Date"]: int(r["ED_Visits_24h"]) / b for r in rows}
    return _ed[org].get(local_dt(local_ts(d, "12:00")).strftime("%Y-%m-%d"), 1.0)


# ---- sessions: who is logged on where -----------------------------------------------------------------
def _clip(org, site, a, b, g):
    out = [(a, b, False)]                                  # (start, end, ended by loss of power)
    for oa, ob in outages(org).get(site, []):
        nxt = []
        for x, y, cut in out:
            if y <= oa or x >= ob:
                nxt.append((x, y, cut))
                continue
            if oa - x > 300:
                nxt.append((x, oa - int(g.integers(0, 40)), True))
            if y - ob > 2400:
                nxt.append((ob + int(g.integers(300, 1800)), y, cut))
        out = nxt
    return out


def _office_day(org, site, d, user, g):
    """Working periods of an office worker on local day d: [(start, end)]. People have habits (an early or a late
    start) and days differ: a lunch away from the desk, a half day, a late arrival, a short visit."""
    early = h01("habit", org, user)                        # 0 = early bird, 1 = late starter
    a = local_ts(d, "06:35") + int(early * 7200) + int(g.normal(0, 620))
    b = a + int(8.55 * 3600 + g.normal(0, 2300)) + (int(g.gamma(2, 1500)) if g.random() < 0.12 else 0)
    if closes_at_noon(org, site, d):
        return [(a, local_ts(d, "12:00") + int(g.integers(-1500, 600)))]
    r = g.random()
    extra = []
    if g.random() < 0.02 + 0.03 * h01("evening", org, user):        # back at the desk in the evening
        x = local_ts(d, "18:20") + int(g.integers(0, 3 * 3600))
        extra.append((max(x, b + 1500), max(x, b + 1500) + int(g.integers(1200, 6000))))
    if g.random() < 0.012 + 0.02 * (early < 0.15):                  # in before dawn
        x = local_ts(d, "03:50") + int(g.integers(0, 5400))
        if a - x > 2700:
            extra.append((x, x + int(g.integers(900, min(5400, a - x - 600)))))
    if r < 0.52:
        if g.random() < 0.2:                                        # the machine is restarted in the afternoon
            m = local_ts(d, "13:10") + int(g.integers(0, int(3.9 * 3600)))
            if a + 3600 < m < b - 1800:
                return [(a, m), (m + int(g.integers(150, 1300)), b)] + extra
        return [(a, b)] + extra
    if r < 0.74:
        m = local_ts(d, "11:35") + int(g.integers(0, 3300))
        return [(a, m), (m + int(g.integers(1500, 4500)), b)]
    if r < 0.82:
        return [(a, local_ts(d, "11:20") + int(g.integers(0, 5400)))]
    if r < 0.89:
        return [(local_ts(d, "11:45") + int(g.integers(0, 5400)), b)]
    if r < 0.95:
        return [(a + int(g.integers(5400, 12600)), b)]
    x = local_ts(d, "07:30") + int(g.integers(0, 8 * 3600))
    return [(x, x + int(g.integers(1500, 9000)))]


_sess, _by_host = {}, {}
CLIN_LEN = {"SRMC": (1.5, 10500), "BCMC": (2.1, 5600)}     # the larger hospital keeps people on a workstation longer
CLIN_MIN = {"SRMC": 600, "BCMC": 300}
CLIN_BUSY = {"SRMC": (0.72, 0.3), "BCMC": (0.61, 0.38)}


def sessions(org):
    """All interactive sessions of an organisation over the span: list of dicts {host, ip, site, user, a, b, kind, cut},
    sorted by start. Built once. A person is at one machine at a time."""
    if org in _sess:
        return _sess[org]
    o, spec = registry()[org], ORGS[org]
    kinds = {s["site_id"]: s["kind"] for s in o["sites"]}
    out = []
    d0, d1 = -61, int((SPAN_B - D0_EPOCH) // DAY) + 1

    def put(h, user, a, b, kind, g):
        if b - a < 600:
            return
        out.extend(dict(host=h["host_id"], ip=h["ip"], site=h["site_id"], user=user, a=x, b=y, kind=kind, cut=c) for x, y, c in _clip(org, h["site_id"], a, b, g) if y - x >= 300)

    for h in o["hosts"]:
        if "users" not in h:
            continue
        site, kind, us = h["site_id"], kinds[h["site_id"]], h["users"]
        if kind == "clinical":                               # shared workstation: one clinician after another, thinner at night
            t = local_ts(d0, "00:00") + hint("clin0", h["host_id"]) % 7200
            end = local_ts(d1, "23:59")
            g = rng("partner_it", "sess", h["host_id"])
            last = None
            while t < end:
                hr = local_dt(t).hour
                busy = CLIN_BUSY.get(org, (0.72, 0.3))[0 if 6 <= hr < 22 else 1]
                if g.random() < busy:
                    u = us[int(g.integers(len(us)))]
                    if u == last:
                        u = us[(us.index(u) + 1) % len(us)]
                    ln = int(min(12.5 * 3600, g.gamma(*CLIN_LEN.get(org, (1.5, 10500))) + CLIN_MIN.get(org, 600)))
                    put(h, u, t, t + ln, kind, g)
                    last = u
                    t += ln + int(g.gamma(1.5, 420)) + 20
                else:
                    t += int(g.integers(1500, 9000))
            continue
        for d in range(d0, d1 + 1):
            g = rng("partner_it", "sess", h["host_id"], d)
            f = day_factor(org, d)
            if kind == "ops24" and len(us) > 1 and round_the_clock(org, site, d):
                eight = spec["shift"] == "8h" and len(us) >= 6
                starts = ("07:00", "15:00", "23:00") if eight else ("06:00", "18:00")
                ln = 8 * 3600 if eight else 12 * 3600
                ncrew = len(us) // len(starts)
                for k, st in enumerate(starts):
                    if g.random() < (0.95 if k == 0 else 0.9):
                        a = local_ts(d, st) + int(g.normal(-240, 420))
                        b = a + ln + int(g.normal(300, 540))
                        u = us[((d // 2) % ncrew) * len(starts) + k]      # crews alternate two days on, two days off
                        if g.random() < 0.17:                              # console restarted or handed to a relief for a break
                            m = a + int(g.uniform(0.2, 0.8) * (b - a))
                            put(h, u, a, m, kind, g)
                            put(h, u, m + int(g.integers(120, 1500)), b, kind, g)
                        else:
                            put(h, u, a, b, kind, g)
            elif kind == "gate":
                wd = local_dt(local_ts(d, "12:00")).weekday()
                p = 0.93 * staff(org, site, d) * (1.0 if wd < 5 else 0.62) * (0.3 + 0.7 * holiday_factor(org, d))
                if g.random() < p:
                    a = local_ts(d, "05:40") + int(g.normal(0, 700))
                    b = local_ts(d, "17:50") + int(g.normal(0, 1500))
                    if d == -1:
                        b = zulu_time() + int(g.integers(900, 4200))       # the gates shut when the port condition is set
                    put(h, us[(d // 3) % len(us)], a, b, kind, g)
            else:
                p = 0.88 * f * staff(org, site, d)
                if g.random() < p:
                    for a, b in _office_day(org, site, d, us[0], g):
                        put(h, us[0], a, b, kind, g)
                elif f > 0.5 and g.random() < 0.012:                       # someone looks in on a day off
                    a = local_ts(d, "08:00") + int(g.integers(0, 9 * 3600))
                    put(h, us[0], a, a + int(g.integers(900, 5400)), kind, g)
    for hid, user, a, b in forced_sessions(org):
        h = next(x for x in o["hosts"] if x["host_id"] == hid)
        if not powered(org, h["site_id"], a) or not powered(org, h["site_id"], b):
            continue
        if any(s["host"] == hid and s["a"] + 120 <= a and s["b"] >= b - 600 and (user is None or s["user"] == user) for s in out):
            continue
        out = [s for s in out if not (s["host"] == hid and s["a"] < b and s["b"] > a)]
        out.append(dict(host=hid, ip=h["ip"], site=h["site_id"], user=user or h["users"][0], a=a, b=b, kind=kinds.get(h["site_id"], "office"), cut=False))
    out.sort(key=lambda s: (s["a"], s["host"]))
    bh = {}
    for s in out:
        bh.setdefault(s["host"], []).append(s)
    for hid, lst in bh.items():                             # one person at a console at a time: the outgoing user logs off before the next logs on
        for i in range(len(lst) - 1):
            if lst[i]["b"] > lst[i + 1]["a"] - 15:
                lst[i]["b"] = lst[i + 1]["a"] - 15 - hint("handover", hid, lst[i + 1]["a"]) % 240
    out = [s for s in out if s["b"] - s["a"] >= 240]
    bh = {}
    for s in out:
        bh.setdefault(s["host"], []).append(s)
    _sess[org] = out
    _by_host[org] = bh
    return out


def session_at(org, host, t):
    sessions(org)
    for s in _by_host[org].get(host, []):
        if s["a"] <= t < s["b"]:
            return s
    return None


# ---- records other delivered streams or canon fix ---------------------------------------------------------
def alert_issues(org):
    """[(epoch, host, alert id, kind)] for alerts this organisation issued (delivered eas_broadcasts.csv)."""
    out = []
    for r in read_csv("public_health/eas_broadcasts.csv"):
        tgt = ALERT_SOURCES.get(r["AlertSource"])
        if not tgt or tgt[0] != org:
            continue
        out.append((ts(r["IssuedAt_UTC"]), tgt[1], r["AlertID"], "issue"))
        if r["WEA_Sent_ES"] and r["WEA_Sent_ES"] != r["WEA_Sent_EN"]:
            out.append((ts(r["WEA_Sent_ES"]), tgt[1], r["AlertID"], "spanish"))
    return sorted(out)


def brw_sessions():
    return read_csv("telemetry/vessel_cargo_control_remote_sessions.csv")


def brw_ws(person):
    """Workstation of a Brightwake member of staff."""
    for h in registry()["BRW"]["hosts"]:
        if h.get("users") and h["users"][0] == person and h["device_type"] == "workstation":
            return h
    return None


def forced_sessions(org):
    """Sessions that records in other delivered streams require: (host_id, user or None, start, end)."""
    out = []
    for t, host, aid, kind in alert_issues(org):
        g = rng("partner_it", "force", host, t)
        out.append((host, None, t - int(g.integers(480, 1500)), t + int(g.integers(1200, 3600))))
    if org == "BRW":
        g = rng("partner_it", "force", "bwclick")
        out.append((brw_ws(BRW_CLICK_PERSON)["host_id"], BRW_CLICK_PERSON, BRW_CLICK_T - int(g.integers(3600, 9000)), BRW_CLICK_T + int(g.integers(3600, 10800))))
        for r in brw_sessions():
            if r["src_ip"] not in BRW_OFFICE_POOL:
                continue
            t = ts(r["login_utc"])
            g = rng("partner_it", "force", "bwsess", t)
            ws = brw_ws(BRW_ENG[r["vendor_account"]])
            out.append((ws["host_id"], BRW_ENG[r["vendor_account"]], t - int(g.integers(900, 5400)), t + int(r["duration_s"] or 0) + int(g.integers(600, 4800))))
    return out


_wave, _clicks = {}, {}


def wave(org):
    """The aid-themed messages of 2027-09-15 to 09-18 at the city and the air station:
    [(epoch, sender, recipient mailbox, size, message id)], in time order."""
    if org not in _wave:
        g = rng("partner_it", "wave", org)
        mbs = CITY_MB if org == "CITY" else NAS_MB
        rows = []
        for i in range(WAVE_N.get(org, 0)):
            t = WAVE_A + 300 + int(g.integers(0, WAVE_B - WAVE_A - 420))
            rows.append((t, f"assistance-{int(g.integers(10, 99))}@{LURE_DOM}", mbs[int(g.integers(len(mbs)))], int(g.integers(9000, 16000)), "<" + hsh("aid", org, i) + "@" + LURE_DOM + ">"))
        _wave[org] = sorted(rows)
    return _wave[org]


def story_clicks(org):
    """Link clicks on that message: [(epoch, mailbox, host dict, url host)]. A click comes from a person who received
    the message, some minutes to hours after it arrived, while they are logged on at their own workstation."""
    if org in _clicks:
        return _clicks[org]
    out = []
    if org in WAVE_N:
        sessions(org)
        ws_of = {}
        for h in registry()[org]["hosts"]:
            for u in h.get("users", []):
                ws_of[u] = h
        cand, seen = [], set()
        for t, snd, mb, size, mid in wave(org):
            u = mb.split("@")[0]
            if u in seen or u not in ws_of:
                continue
            seen.add(u)
            if home_of(org, u)[1] == netmap.label(netmap.STORY_POOL[0]):
                continue                                    # that provider's own customers are left out: for them the network would not be new
            g = rng("partner_it", "click", org, u)
            want = t + int(g.gamma(2, 2400)) + 240
            for s in _by_host[org].get(ws_of[u]["host_id"], []):
                if s["user"] == u and s["b"] - 600 > max(want, s["a"] + 180) and s["b"] > t + 600 and s["a"] < WAVE_B:
                    tc = max(want, s["a"] + 180 + int(g.integers(0, 2400)))
                    if tc < min(s["b"] - 300, WAVE_B + 3 * 3600):
                        cand.append((hint("clickrank", org, u), tc, mb, ws_of[u]))
                    break
        cand.sort()
        out = sorted((tc, mb, h, LURE_HOST) for _, tc, mb, h in cand[:CLICK_N[org]])
    _clicks[org] = out
    return out


def story_signons(org):
    """Sign-ons with each clicked account from a network it never used before: [(epoch, mailbox, address, label)]."""
    out = []
    for tc, mb, h, _ in story_clicks(org):
        g = rng("partner_it", "signon", org, mb)
        sip = netmap.STORY_POOL[int(g.integers(17, 81)) - 17]
        out.append((tc + int(g.integers(1800, 9 * 3600)), mb, sip, netmap.label(sip)))
    return out
