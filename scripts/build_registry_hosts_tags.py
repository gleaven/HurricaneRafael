"""Build the utility's host/account registry and SCADA tag catalogue.

Writes (participant-safe reference data, no truth notes):
  06_data_streams/gw_host_registry.json
  06_data_streams/scada_tags.json
and (internal, never delivered):
  06_data_streams/_internal/gw_host_registry_truth.json
  06_data_streams/_internal/scada_tags_truth.json

Deterministic: re-running gives the same files. Canon identifiers come from the MSEL
(GW-EVT-*), scenarios/gridwater/00_scenario/assets.json and 00_scenario/canon_timeline.json.
Usage: python scripts/build_registry_hosts_tags.py
"""
import json
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "06_data_streams")
INT = os.path.join(OUT, "_internal")
os.makedirs(INT, exist_ok=True)
R = random.Random(20270914)

UTILITY = "Coastal Bend Power and Water Authority"
ABBR = "CBPWA"
AD_DOMAIN = "corp.cbpwa.example"
OT_DOMAIN = "ot.cbpwa.example"
MAIL_DOMAIN = "cbpwa.example"

FIRST = ("Maria Jose Luis Ana Carlos Rosa Miguel Elena Jorge Patricia David Laura Daniel Sandra Robert Linda James "
         "Karen Michael Angela Thanh Linh Huy Minh Kim Darnell Keisha Marcus Tanya Andre Brenda Raul Veronica "
         "Hector Yolanda Oscar Gloria Ruben Alma Eddie Norma Travis Shelby Cody Amber Wade Kayla Trent Becky "
         "Priya Arjun Fatima Omar Grace Samuel Ruth Isaac Noemi Felix Irma Tomas Lidia Ernesto Delia Arturo Sonia "
         "Kevin Stacy Brian Tina Greg Monica Paul Diane Victor Carmen Hugo Leticia Ray Dolores").split()
LAST = ("Garcia Martinez Rodriguez Hernandez Lopez Gonzalez Perez Sanchez Ramirez Torres Flores Rivera Gomez Diaz "
        "Reyes Morales Cruz Ortiz Gutierrez Chavez Ramos Mendoza Ruiz Alvarez Castillo Jimenez Vasquez Moreno "
        "Salinas Cantu Trevino Guerra Garza Villarreal Pena Longoria Saenz Benavides Zamora Tijerina "
        "Smith Johnson Williams Brown Jones Miller Davis Wilson Anderson Taylor Thomas Moore Jackson Martin "
        "Thompson White Harris Clark Lewis Walker Hall Allen Young King Wright Scott Green Baker Adams Nelson "
        "Nguyen Tran Le Pham Patel Shah Okafor Mensah Kowalski Schroeder Dvorak Lindqvist").split()


def person(used):
    while True:
        n = f"{R.choice(FIRST)} {R.choice(LAST)}"
        if n not in used:
            used.add(n)
            return n


# --------------------------------------------------------------------------------------
# network zones
# --------------------------------------------------------------------------------------
ZONES = [
    # zone id, name, cidr, vlan, purdue level, site
    ("corp-mgmt", "Corporate network management", "10.14.1.0/24", 1, "L4", "HQ"),
    ("corp-servers", "Corporate data centre", "10.14.10.0/24", 10, "L4", "HQ"),
    ("corp-security", "Security and monitoring", "10.14.12.0/24", 12, "L4", "HQ"),
    ("corp-users-ops", "Headquarters, operations and engineering floors", "10.14.20.0/24", 20, "L4", "HQ"),
    ("corp-users-biz", "Headquarters, finance, HR and customer service", "10.14.21.0/24", 21, "L4", "HQ"),
    ("corp-users-admin", "Headquarters, administration wing and contractors", "10.14.22.0/24", 22, "L4", "HQ"),
    ("corp-users-field", "Field service centres", "10.14.30.0/24", 30, "L4", "FSC"),
    ("corp-vpn", "Employee remote-access pool", "10.14.250.0/24", 250, "L4", "HQ"),
    ("inet-dmz", "Internet DMZ", "172.20.5.0/24", 505, "L5", "HQ"),
    ("ot-dmz", "IT/OT DMZ", "10.72.4.0/24", 704, "L3.5", "GW-FAC-OPS-01"),
    ("ot-control", "Operations Center control systems", "10.72.1.0/24", 701, "L3", "GW-FAC-OPS-01"),
    ("ot-hmi", "Operations Center operator consoles", "10.72.2.0/24", 702, "L2", "GW-FAC-OPS-01"),
    ("ot-backup-cc", "Backup control centre", "10.72.6.0/24", 706, "L3", "BCC"),
    ("ot-sub-01", "Riverside Switching Station", "10.72.11.0/24", 711, "L1", "GW-FAC-SUB-01"),
    ("ot-sub-02", "Harbor View Substation", "10.72.12.0/24", 712, "L1", "GW-FAC-SUB-02"),
    ("ot-sub-03", "Crosstown Substation", "10.72.13.0/24", 713, "L1", "GW-FAC-SUB-03"),
    ("ot-sub-04", "Southside Substation", "10.72.14.0/24", 714, "L1", "GW-FAC-SUB-04"),
    ("ot-sub-05", "Bayside Substation", "10.72.15.0/24", 715, "L1", "GW-FAC-SUB-05"),
    ("ot-dss-01", "McKinley Substation", "10.72.16.0/24", 716, "L1", "GW-FAC-DSS-01"),
    ("ot-wtp", "O.N. Stevens Water Treatment Plant", "10.72.30.0/24", 730, "L1", "GW-FAC-UTL-01"),
    ("ot-wtr-01", "Texana Booster Station 1", "10.72.31.0/24", 731, "L1", "GW-FAC-WTR-01"),
    ("ot-wtr-02", "Texana Booster Station 2", "10.72.32.0/24", 732, "L1", "GW-FAC-WTR-02"),
    ("ot-wtr-03", "Colorado River Booster Station", "10.72.33.0/24", 733, "L1", "GW-FAC-WTR-03"),
    ("ot-tanks", "Distribution storage tanks (cellular RTUs)", "10.72.40.0/24", 740, "L1", "TANKS"),
    ("ot-gen-01", "Palisade Energy Center", "10.72.50.0/24", 750, "L1", "GW-FAC-GEN-01"),
]
ZONE_CIDR = {z[0]: z[2] for z in ZONES}

SITES = [
    ("HQ", "CBPWA Headquarters", "office"),
    ("GW-FAC-OPS-01", "CBPWA Operations Center", "control centre"),
    ("BCC", "CBPWA Backup Control Centre", "control centre"),
    ("FSC", "CBPWA Field Service Centres (North and South)", "service centre"),
    ("GW-FAC-SUB-01", "Riverside Switching Station", "substation 345/138 kV"),
    ("GW-FAC-SUB-02", "Harbor View Substation", "substation 138/69 kV"),
    ("GW-FAC-SUB-03", "Crosstown Substation", "substation 138/69 kV"),
    ("GW-FAC-SUB-04", "Southside Substation", "substation 138/69 kV"),
    ("GW-FAC-SUB-05", "Bayside Substation", "substation 138 kV"),
    ("GW-FAC-DSS-01", "McKinley Substation", "distribution substation 69/12.5 kV"),
    ("GW-FAC-UTL-01", "O.N. Stevens Water Treatment Plant", "water treatment plant"),
    ("GW-FAC-WTR-01", "Texana Booster Station 1", "raw-water pump station"),
    ("GW-FAC-WTR-02", "Texana Booster Station 2", "raw-water pump station"),
    ("GW-FAC-WTR-03", "Colorado River Booster Station", "raw-water pump station"),
    ("GW-FAC-GEN-01", "Palisade Energy Center", "generation"),
    ("TANKS", "Distribution storage tanks GW-FAC-TK-01 to GW-FAC-TK-09", "storage"),
]

hosts, truth_hosts, used_ip = [], {}, set()


def ip_in(zone, last):
    base = ZONE_CIDR[zone].rsplit(".", 1)[0]
    ip = f"{base}.{last}"
    assert ip not in used_ip, ip
    used_ip.add(ip)
    return ip


def host(hostname, zone, last, role, os_, dtype, team, site=None, asset_tag=None, vendor=None, crit="medium",
         primary_user=None, aliases=None, note=None, domain=None):
    z = next(x for x in ZONES if x[0] == zone)
    dom = domain if domain is not None else (OT_DOMAIN if zone.startswith("ot-") else AD_DOMAIN)
    h = {"host_id": hostname, "hostname": hostname, "fqdn": f"{hostname.lower()}.{dom}" if dom else None,
         "ip": ip_in(zone, last), "zone": zone, "vlan": z[3], "purdue_level": z[4], "site_id": site or z[5],
         "device_type": dtype, "role": role, "os": os_, "vendor": vendor, "owner_team": team, "criticality": crit}
    if asset_tag:
        h["asset_tag"] = asset_tag
    if primary_user:
        h["primary_user"] = primary_user
    if aliases:
        h["aliases"] = aliases
    hosts.append(h)
    if note:
        truth_hosts[hostname] = note
    return h


W10, W11, LTSC = "Windows 10 Enterprise 22H2", "Windows 11 Enterprise 23H2", "Windows 10 Enterprise LTSC 2019"
WS19, WS22, WS16 = "Windows Server 2019", "Windows Server 2022", "Windows Server 2016"
RHEL, UBU = "Red Hat Enterprise Linux 8", "Ubuntu Server 22.04 LTS"

# ---------------- corporate network gear
host("GW-FW-EDGE-01", "corp-mgmt", 1, "Internet edge firewall (active)", "Firewall OS 7.4", "firewall", "Network", crit="critical",
     aliases=["FW-EDGE-01"], vendor="Bastille Networks")
host("GW-FW-EDGE-02", "corp-mgmt", 2, "Internet edge firewall (standby)", "Firewall OS 7.4", "firewall", "Network", crit="critical", vendor="Bastille Networks")
host("GW-SW-CORE-01", "corp-mgmt", 11, "Core switch, headquarters", "Switch OS 17.9", "switch", "Network", crit="high")
host("GW-SW-CORE-02", "corp-mgmt", 12, "Core switch, headquarters", "Switch OS 17.9", "switch", "Network", crit="high")
for i in range(1, 7):
    host(f"GW-SW-ACC-{i:02d}", "corp-mgmt", 20 + i, f"Access switch, headquarters floor {1 + (i - 1) // 2}", "Switch OS 17.9", "switch", "Network")
host("GW-WLC-01", "corp-mgmt", 40, "Wireless LAN controller", "Controller OS 8.10", "wireless controller", "Network")
host("GW-RTR-FSC-N", "corp-mgmt", 51, "WAN router, north field service centre", "Router OS 17.6", "router", "Network")
host("GW-RTR-FSC-S", "corp-mgmt", 52, "WAN router, south field service centre", "Router OS 17.6", "router", "Network")
host("GW-NMS-01", "corp-mgmt", 60, "Network management and NetFlow collector", RHEL, "server", "Network")

# ---------------- corporate servers
SRV = [
    ("GW-SRV-DC-01", 5, "Active Directory domain controller, DNS", WS22, "critical"),
    ("GW-SRV-DC-02", 6, "Active Directory domain controller, DNS", WS22, "critical"),
    ("GW-SRV-FILE-01", 20, "Departmental file shares", WS19, "high"),
    ("GW-SRV-FILE-02", 21, "Engineering drawings and GIS exports", WS19, "medium"),
    ("GW-SRV-PRINT-01", 25, "Print server", WS19, "low"),
    ("GW-SRV-MAIL-01", 30, "Mail server (mailbox role)", "Windows Server 2019 / Exchange 2019", "high"),
    ("GW-SRV-MAIL-02", 31, "Mail server (mailbox role)", "Windows Server 2019 / Exchange 2019", "high"),
    ("GW-SRV-SQL-01", 40, "Database cluster node (finance, CIS)", WS19, "high"),
    ("GW-SRV-SQL-02", 41, "Database cluster node (finance, CIS)", WS19, "high"),
    ("GW-SRV-ERP-01", 45, "Finance and procurement application", WS19, "high"),
    ("GW-SRV-CIS-01", 46, "Customer information and billing system", WS19, "high"),
    ("GW-SRV-OMS-01", 47, "Outage management system", WS19, "critical"),
    ("GW-SRV-GIS-01", 48, "Geographic information system", WS19, "medium"),
    ("GW-SRV-MAXIMO-01", 49, "Work-order and asset management (Maximo 7.6)", WS19, "medium"),
    ("GW-SRV-HR-01", 50, "HR, timekeeping and leave system", WS19, "medium"),
    ("GW-SRV-IVR-01", 52, "Customer call centre IVR", WS16, "medium"),
    ("GW-SRV-COMMS-01", 53, "Radio dispatch gateway", WS16, "high"),
    ("GW-SRV-WSUS-01", 60, "Patch management", WS19, "medium"),
    ("GW-SRV-BKP-01", 61, "Backup server", WS19, "high"),
    ("GW-SRV-SCCM-01", 62, "Endpoint configuration management", WS19, "medium"),
    ("GW-SRV-CA-01", 63, "Certificate authority", WS19, "high"),
    ("GW-SRV-RADIUS-01", 64, "RADIUS / network policy server", WS19, "high"),
    ("GW-SRV-INTRA-01", 70, "Intranet and document management", WS19, "low"),
    ("GW-SRV-VDI-01", 71, "Virtual desktop broker", WS19, "medium"),
    ("GW-SRV-HV-01", 80, "Virtualisation host", "VMware ESXi 7.0", "high"),
    ("GW-SRV-HV-02", 81, "Virtualisation host", "VMware ESXi 7.0", "high"),
    ("GW-SRV-HV-03", 82, "Virtualisation host", "VMware ESXi 7.0", "high"),
    ("GW-SAN-01", 90, "Storage array controller", "Array OS 9.2", "high"),
]
for n, last, role, os_, crit in SRV:
    host(n, "corp-servers", last, role, os_, "server" if not n.startswith("GW-SAN") else "storage", "IT Infrastructure", crit=crit)

# ---------------- security / monitoring
host("GW-SRV-SIEM-01", "corp-security", 10, "SIEM manager (Sentinel Edge 3.1)", RHEL, "server", "Security Operations", vendor="Vantage Security Systems", crit="high",
     note="Sentinel Edge 3.1 SIEM; alert ids SE3-*; storm-mode bulk dismissal and exception rule MAINT-EXCEPT-0892 live here.")
host("GW-SRV-SIEM-02", "corp-security", 11, "SIEM log collector (corporate)", RHEL, "server", "Security Operations", vendor="Vantage Security Systems")
host("GW-SRV-SIEM-03", "corp-security", 12, "SIEM behavioural analytics node (Vantage Behavioral Analytics 2.1)", RHEL, "server", "Security Operations", vendor="Vantage Security Systems")
host("GW-SRV-EDR-01", "corp-security", 20, "Endpoint protection management console", WS22, "server", "Security Operations", vendor="Vantage Security Systems")
host("GW-SRV-VULN-01", "corp-security", 21, "Vulnerability scanner", UBU, "server", "Security Operations")
host("GW-SRV-PROXY-01", "corp-security", 30, "Web proxy and DNS filtering", RHEL, "server", "Security Operations")
host("GW-SRV-PAM-01", "corp-security", 31, "Privileged access vault", WS19, "server", "Security Operations", crit="high")
for i in range(1, 5):
    host(f"GW-WS-SOC-{i:02d}", "corp-security", 40 + i, "Security analyst workstation", W11, "workstation", "Security Operations")

# ---------------- internet DMZ
host("GW-GW-MAIL-01", "inet-dmz", 10, "Mail security gateway", "Appliance OS 15", "appliance", "IT Infrastructure", crit="high",
     note="Email gateway that logged delivery of the D-14 lure attachment (GW-EVT-001).")
host("GW-SRV-WEB-01", "inet-dmz", 20, "Public website and outage map", RHEL, "server", "IT Infrastructure")
host("GW-SRV-PORTAL-01", "inet-dmz", 21, "Customer self-service portal", RHEL, "server", "IT Infrastructure")
host("GW-VPN-EMP-01", "inet-dmz", 30, "Employee VPN concentrator", "VPN OS 9.16", "vpn concentrator", "Network", crit="high")
host("GW-SRV-DNSX-01", "inet-dmz", 40, "External DNS", UBU, "server", "Network")
host("GW-SRV-MFT-01", "inet-dmz", 41, "Managed file transfer (regulatory and ERCOT filings)", RHEL, "server", "IT Infrastructure")

# ---------------- IT/OT DMZ
host("GW-OT-FW-01", "ot-dmz", 1, "IT/OT boundary firewall", "Industrial firewall OS 6.2", "firewall", "OT Engineering", crit="critical", vendor="Bastille Networks")
host("GW-OT-FW-02", "ot-dmz", 2, "IT/OT boundary firewall (standby)", "Industrial firewall OS 6.2", "firewall", "OT Engineering", crit="critical", vendor="Bastille Networks")
host("GW-SYS-JMP-01", "ot-dmz", 88, "Remote-access gateway and jump host for OT (ClearPath SecureReach 2.1)", WS16, "jump host", "OT Engineering",
     asset_tag="GW-SYS-JMP-01", vendor="ClearPath Network Solutions", crit="critical", aliases=["VPN-GW-01", "ClearPath VPN Gateway"],
     note="Pivot for every OT session in T8/T9/T10: 14 sessions under GW-ENG-VELA from outside Texas (D-7 to D+16), historian sessions, breaker-open commands relayed through GW-WS-OPS-02. Taken offline D+28 12:30Z.")
host("GW-SRV-HIST-DMZ", "ot-dmz", 20, "Historian replica for business users (read-only)", WS19, "server", "OT Engineering", vendor="Meridian Controls Corp")
host("GW-SRV-OTPATCH-01", "ot-dmz", 30, "OT patch and antivirus staging", WS19, "server", "OT Engineering")
host("GW-SRV-OTXFER-01", "ot-dmz", 31, "OT file transfer broker", RHEL, "server", "OT Engineering")
host("GW-NET-MON-01", "ot-dmz", 50, "Network sensor, IT/OT boundary (Zeek)", UBU, "sensor", "Security Operations", aliases=["GW-NET-MON"],
     note="Zeek sensor producing conn/dns/notice logs for the IT/OT boundary.")
host("GW-SRV-SIEM-OT", "ot-dmz", 51, "SIEM log collector (OT)", RHEL, "server", "Security Operations", vendor="Vantage Security Systems")

# ---------------- control centre
host("GW-SYS-SCADA-01", "ot-control", 30, "SCADA master station, primary (Meridian HorizonView 4.2)", WS19, "scada server", "System Operations",
     asset_tag="GW-SYS-SCADA-01", vendor="Meridian Controls Corp", crit="critical", aliases=["GW-SRV-SCADA-01", "SCADA-SRV-01"],
     note="Command log records the SUB-02 CB-7 (D+7 14:28Z) and SUB-03 CB-12 (D+10 19:43Z) breaker-open commands and the alarm-suppression list changes.")
host("GW-SYS-SCADA-02", "ot-control", 31, "SCADA master station, standby", WS19, "scada server", "System Operations", vendor="Meridian Controls Corp", crit="critical")
host("GW-SRV-HIST-01", "ot-control", 10, "Process historian, primary (Meridian Historian)", WS19, "historian", "OT Engineering",
     asset_tag="GW-SYS-HST-01", vendor="Meridian Controls Corp", crit="critical", aliases=["GW-SYS-HST-01", "HIST-SRV-01", "GW-HIST-01"],
     note="Historian queried in the 14 after-hours sessions (HIST-20270907-00441 to HIST-20271002-00917).")
host("GW-SRV-HIST-02", "ot-control", 11, "Process historian, backup", WS19, "historian", "OT Engineering", vendor="Meridian Controls Corp", crit="high", aliases=["GW-HIST-02"])
host("GW-SRV-OT-01", "ot-control", 20, "OT engineering file server (relay configurations, drawings)", WS19, "server", "OT Engineering", crit="high",
     note=r"Share \\gw-srv-ot-01\relayconfigs: modified SUB-02 relay configuration written D-3 22:11Z (GW-EVT-103).")
host("GW-SRV-OTDC-01", "ot-control", 5, "OT domain controller", WS19, "server", "OT Engineering", crit="critical")
host("GW-SRV-OTDC-02", "ot-control", 6, "OT domain controller", WS19, "server", "OT Engineering", crit="critical")
host("GW-SRV-FEP-01", "ot-control", 35, "SCADA front-end processor (DNP3 to substations)", WS19, "front-end processor", "System Operations", vendor="Meridian Controls Corp", crit="critical")
host("GW-SRV-FEP-02", "ot-control", 36, "SCADA front-end processor (DNP3/Modbus to water sites)", WS19, "front-end processor", "System Operations", vendor="Meridian Controls Corp", crit="critical")
host("GW-SRV-ICCP-01", "ot-control", 38, "ICCP gateway to ERCOT", WS19, "server", "System Operations", crit="critical")
host("GW-SRV-ALM-01", "ot-control", 39, "Alarm management server", WS19, "server", "System Operations", vendor="Meridian Controls Corp", crit="high")
host("GW-SRV-OTBKP-01", "ot-control", 60, "OT backup server", WS19, "server", "OT Engineering")
host("GW-SRV-NTP-01", "ot-control", 61, "GPS time server", "Appliance firmware 5.3", "appliance", "OT Engineering")
ENG_WS = []
for i in range(1, 6):
    h = host(f"GW-WS-ENG-{i:02d}", "ot-control", 40 + i, "Engineering workstation (relay and RTU configuration)", LTSC, "engineering workstation", "OT Engineering", crit="high")
    ENG_WS.append(h)
# operator consoles
for i in range(1, 7):
    role = {1: "Operator console, transmission desk", 2: "Operator console, distribution desk", 3: "Operator console, water desk",
            4: "Operator console, generation desk", 5: "Shift supervisor console", 6: "Training and spare console"}[i]
    note = ("Workstation named in the SCADA command log for both breaker-open commands; no operator logged in at the time "
            "(GW-EVT-005, GW-EVT-007).") if i == 2 else None
    host(f"GW-WS-OPS-{i:02d}", "ot-hmi", 10 + i, role, LTSC, "operator workstation", "System Operations", vendor="Meridian Controls Corp", crit="critical", note=note)
host("GW-HMI-WALL-01", "ot-hmi", 30, "Control room video wall controller", LTSC, "operator workstation", "System Operations")
# backup control centre
host("GW-SYS-SCADA-03", "ot-backup-cc", 30, "SCADA master station, backup control centre", WS19, "scada server", "System Operations", vendor="Meridian Controls Corp", crit="high")
host("GW-SRV-HIST-03", "ot-backup-cc", 10, "Process historian, backup control centre", WS19, "historian", "OT Engineering", vendor="Meridian Controls Corp")
for i in range(1, 3):
    host(f"GW-WS-BCC-{i:02d}", "ot-backup-cc", 10 + i + 30, "Operator console, backup control centre", LTSC, "operator workstation", "System Operations")

# ---------------- substations
MAIN_CB = {1: 1, 2: 7, 3: 12, 4: 13, 5: 17}
SUBS = {1: ("Riverside Switching Station", [1, 2, 3, 4]), 2: ("Harbor View Substation", [5, 6, 7, 8]), 3: ("Crosstown Substation", [9, 10, 11, 12]),
        4: ("Southside Substation", [13, 14, 15, 16]), 5: ("Bayside Substation", [17, 18, 19, 20])}
YARD = {5: "B2-B", 6: "B2-D", 7: "B2-A", 8: "B2-C", 9: "B3-A", 10: "B3-C", 11: "B3-D", 12: "B3-B"}
equipment = []
for n, (name, cbs) in SUBS.items():
    z, site = f"ot-sub-{n:02d}", f"GW-FAC-SUB-{n:02d}"
    host(f"GW-SUB{n:02d}-GW", z, 1, f"Substation gateway router, {name}", "Router OS 15.9", "router", "OT Engineering", site)
    host(f"GW-SYS-RTU-{n:02d}", z, 10, f"Remote terminal unit, {name}", "RTU firmware R4.2", "rtu", "Protection and Control", site,
         asset_tag=f"GW-SYS-RTU-{n:02d}", vendor="Meridian Controls Corp", crit="critical", domain="",
         note={1: "27-UV threshold written 0.88 to 0.94 pu at D-3 17:04Z by session user GW-ENG-VELA (GW-EVT-003); trip D0 07:12Z.",
               2: "Relay file write D-3 22:11Z; breaker CB-7 opened D+7 14:28Z.", 3: "Breaker CB-12 opened D+10 19:43Z.",
               4: "Config file last_modified 2027-09-11T17:11 (local), no work order (GW-EVT-010).", 5: "Untouched comparison site."}[n])
    letters = "ABC" if n in (1, 2) else "AB"
    for k, L in enumerate(letters):
        host(f"GW-SUB{n:02d}-REL-{L}", z, 21 + k, f"Protective relay R-{n:02d}{L}, {name}", "Relay firmware 7.1", "protective relay", "Protection and Control", site,
             vendor="Halden Protection", crit="critical", domain="")
        equipment.append({"equipment_id": f"GW-SUB{n:02d}-REL-R{n:02d}{L}", "label": f"R-{n:02d}{L}", "type": "overcurrent relay", "site_id": site, "served_by": f"GW-SUB{n:02d}-REL-{L}"})
    equipment.append({"equipment_id": f"GW-SUB{n:02d}-REL-27", "label": "27-UV", "type": "undervoltage relay function", "site_id": site, "served_by": f"GW-SYS-RTU-{n:02d}"})
    host(f"GW-SUB{n:02d}-HMI", z, 30, f"Local substation HMI, {name}", LTSC, "hmi", "Protection and Control", site, domain="")
    host(f"GW-SUB{n:02d}-SW", z, 2, f"Substation LAN switch, {name}", "Switch OS 5.2", "switch", "OT Engineering", site, domain="")
    for cb in cbs:
        main = cb == MAIN_CB[n]
        e = {"equipment_id": f"GW-SUB{n:02d}-BKR-MAIN" if main else f"GW-SUB{n:02d}-CB-{cb}", "label": f"CB-{cb}" + (" (main breaker)" if main else ""), "type": "circuit breaker", "site_id": site,
             "served_by": f"GW-SYS-RTU-{n:02d}"}
        if cb in YARD:
            e["yard_designation"] = YARD[cb]
        equipment.append(e)
    equipment.append({"equipment_id": f"GW-SUB{n:02d}-T1", "label": "T1", "type": "power transformer", "site_id": site, "served_by": f"GW-SYS-RTU-{n:02d}"})
    equipment.append({"equipment_id": f"GW-SUB{n:02d}-BUS", "label": "Main bus", "type": "bus", "site_id": site, "served_by": f"GW-SYS-RTU-{n:02d}"})
# McKinley distribution substation (feeds Shoreline Regional Medical Center)
host("GW-DSS01-GW", "ot-dss-01", 1, "Substation gateway router, McKinley Substation", "Router OS 15.9", "router", "OT Engineering")
host("GW-SYS-RTU-DSS1", "ot-dss-01", 10, "Remote terminal unit, McKinley Substation", "RTU firmware R4.2", "rtu", "Protection and Control", vendor="Meridian Controls Corp", crit="high", domain="",
     note="Feeder substation for Shoreline Regional Medical Center: storm outage from D0 06:17Z, restored D+8 09:14 local. Not one of the five transmission substations.")
for eid, lab, typ in (("GW-DSS01-BKR-MAIN", "Main breaker", "circuit breaker"), ("GW-DSS01-FDR-11", "Feeder 11 (hospital district)", "feeder breaker"), ("GW-DSS01-FDR-12", "Feeder 12", "feeder breaker"), ("GW-DSS01-T1", "T1", "power transformer")):
    equipment.append({"equipment_id": eid, "label": lab, "type": typ, "site_id": "GW-FAC-DSS-01", "served_by": "GW-SYS-RTU-DSS1"})

# ---------------- water treatment plant
host("GW-WTP-GW", "ot-wtp", 1, "Plant gateway router", "Router OS 15.9", "router", "OT Engineering")
host("GW-WTP-DCS-01", "ot-wtp", 20, "Plant control system controller (treatment train)", "Controller firmware R6.03", "dcs controller", "Water Operations", vendor="Meridian Controls Corp", crit="critical", domain="",
     aliases=["GW-DCS-WTP"])
host("GW-SYS-RTU-UTL1", "ot-wtp", 10, "High-service pump station RTU (pumps P-1 to P-4)", "RTU firmware R4.2", "rtu", "Water Operations", vendor="Meridian Controls Corp", crit="critical", domain="",
     aliases=["RTU-PUMP", "GW-RTU-WTP-01", "GW-PP1-RTU"],
     note="Carries the P-3 discharge setpoint write 85 to 68 psi at D+9 02:04Z (GW-EVT-006); restored D+28 12:14Z.")
for i in range(1, 5):
    host(f"GW-WTP-PLC-P{i}", "ot-wtp", 10 + i, f"Pump P-{i} drive controller", "PLC firmware 3.4", "plc", "Water Operations", crit="critical", domain="",
         aliases=["FAC-UTL-01-P3"] if i == 3 else None)
    equipment.append({"equipment_id": f"EQP-110{i}", "label": f"P-{i}", "type": "high-service pump", "site_id": "GW-FAC-UTL-01", "served_by": f"GW-WTP-PLC-P{i}",
                      "maximo_assetnum": f"GW-PP1-PUMP{i}"})
host("GW-SYS-RTAC-UTL1-A", "ot-wtp", 31, "Plant power feed A protection controller", "Controller firmware R150", "protection controller", "Protection and Control", crit="critical", domain="", aliases=["RTU-PWR", "GW-RTU-PWR-01", "GW-PWR-RTU"])
host("GW-SYS-RTAC-UTL1-B", "ot-wtp", 32, "Plant power feed B protection controller", "Controller firmware R150", "protection controller", "Protection and Control", crit="critical", domain="", aliases=["RTU-BKP", "GW-RTU-PWR-02", "GW-BKP-RTU"])
host("GW-WTP-GEN-CTRL", "ot-wtp", 35, "Emergency generator controller, pump room", "Embedded controller 3.3", "generator controller", "Water Operations", domain="", aliases=["GW-BACKUP-PWR"])
host("GW-WTP-HMI-01", "ot-wtp", 41, "Plant operator console, control room", LTSC, "hmi", "Water Operations", crit="high", aliases=["GW-HMI-01"])
host("GW-WTP-HMI-02", "ot-wtp", 42, "Plant operator console, pump room", LTSC, "hmi", "Water Operations", crit="high")
host("GW-WTP-HIST-01", "ot-wtp", 45, "Plant local historian and intake monitoring", WS19, "historian", "Water Operations", vendor="Meridian Controls Corp")
host("GW-WTP-LAB-01", "ot-wtp", 50, "Water-quality laboratory workstation (LIMS)", W10, "workstation", "Water Quality")
host("GW-WTP-CL2-PLC", "ot-wtp", 16, "Chemical feed controller", "PLC firmware 3.4", "plc", "Water Operations", domain="")
for eid, lab, typ in (("EQP-1110", "High-service pump station", "pump station"), ("EQP-1120", "Raw-water intake, primary", "intake"), ("EQP-1121", "Raw-water intake, secondary", "intake"),
                      ("EQP-1130", "Chemical feed system", "chemical feed"), ("EQP-1140", "Plant standby generator (pump room)", "generator"),
                      ("FAC-UTL-02-A", "Power feed A (primary, from Riverside)", "power feed"), ("FAC-UTL-02-B", "Power feed B (backup to the pump room, from Crosstown)", "power feed"),
                      ("GW-FAC-UTL-01-CLEARWELL", "Clearwell", "storage"), ("GW-FAC-UTL-01-TP1", "Temporary pump TP-1", "temporary pump"), ("GW-FAC-UTL-01-TP2", "Temporary pump TP-2", "temporary pump")):
    equipment.append({"equipment_id": eid, "label": lab, "type": typ, "site_id": "GW-FAC-UTL-01", "served_by": "GW-WTP-DCS-01"})
# boosters
for n, nm in ((1, "Texana Booster Station 1"), (2, "Texana Booster Station 2"), (3, "Colorado River Booster Station")):
    z, site = f"ot-wtr-{n:02d}", f"GW-FAC-WTR-{n:02d}"
    host(f"GW-WTR{n:02d}-GW", z, 1, f"Site gateway router, {nm}", "Router OS 15.9", "router", "OT Engineering", site)
    host(f"GW-SYS-RTU-WTR{n}", z, 10, f"Pump station RTU, {nm}", "RTU firmware R4.2", "rtu", "Water Operations", site, vendor="Meridian Controls Corp", crit="high", domain="",
         note="Booster setpoint 72 to 54 psi at D+9 02:08Z in the same session as the P-3 change (GW-EVT-013)." if n == 3 else None)
    host(f"GW-WTR{n:02d}-HMI", z, 30, f"Local HMI, {nm}", LTSC, "hmi", "Water Operations", site, domain="")
    for k in (1, 2):
        equipment.append({"equipment_id": f"{site}-BP{k}", "label": f"Booster pump {k}", "type": "booster pump", "site_id": site, "served_by": f"GW-SYS-RTU-WTR{n}"})
# tanks
TANKS = ["Northwest Storage Tank 1", "Northwest Storage Tank 2", "Central Storage Tank", "Southside Tank 1", "Southside Tank 2", "East Side Tank",
         "Calallen Tank", "Port District Tank", "Clarkwood Tank"]
for i, nm in enumerate(TANKS, 1):
    host(f"GW-SYS-RTU-TK{i:02d}", "ot-tanks", 10 + i, f"Tank telemetry RTU, {nm}", "RTU firmware R2.8", "rtu", "Water Operations", f"GW-FAC-TK-{i:02d}", crit="medium", domain="")
# generation
host("GW-GEN01-GW", "ot-gen-01", 1, "Plant gateway router, Palisade Energy Center", "Router OS 15.9", "router", "OT Engineering")
host("GW-GEN01-DCS", "ot-gen-01", 20, "Turbine control system", "Controller firmware 8.1", "dcs controller", "Generation", crit="critical", domain="")
host("GW-SYS-RTU-GEN1", "ot-gen-01", 10, "Plant RTU", "RTU firmware R4.2", "rtu", "Generation", vendor="Meridian Controls Corp", crit="high", domain="")
host("GW-GEN01-HMI", "ot-gen-01", 30, "Plant operator console", LTSC, "hmi", "Generation")
equipment.append({"equipment_id": "GW-FAC-GEN-01-U1", "label": "Unit 1", "type": "gas turbine generator", "site_id": "GW-FAC-GEN-01", "served_by": "GW-GEN01-DCS"})

# --------------------------------------------------------------------------------------
# people, accounts, workstations
# --------------------------------------------------------------------------------------
DEPTS = [  # department, headcount, zone, shift pattern, has OT access role prefix
    ("Executive Office", 6, "corp-users-admin", "day", None),
    ("Finance and Procurement", 14, "corp-users-biz", "day", None),
    ("Human Resources", 6, "corp-users-biz", "day", None),
    ("Customer Service", 18, "corp-users-biz", "extended", None),
    ("Communications", 4, "corp-users-admin", "day", None),
    ("IT Infrastructure", 10, "corp-users-admin", "day", None),
    ("Security Operations", 6, "corp-security", "24x7", None),
    ("System Operations", 16, "ot-hmi", "24x7", "OPS"),
    ("OT Engineering", 8, "corp-users-ops", "day", "ENG"),
    ("Protection and Control", 8, "corp-users-ops", "day", "ENG"),
    ("Transmission and Distribution Engineering", 10, "corp-users-ops", "day", None),
    ("Water Operations", 18, "corp-users-field", "24x7", "WTR"),
    ("Water Quality", 5, "corp-users-field", "day", None),
    ("Water Distribution", 8, "corp-users-field", "24x7", None),
    ("Field Services", 20, "corp-users-field", "day", "TEC"),
    ("Generation", 6, "corp-users-field", "24x7", None),
    ("GIS and Planning", 5, "corp-users-ops", "day", None),
    ("Legal and Regulatory", 4, "corp-users-admin", "day", None),
    ("Facilities and Fleet", 5, "corp-users-admin", "day", None),
]
HOURS = {"day": "Mon-Fri 07:00-17:30", "extended": "Mon-Sat 07:00-19:00", "24x7": "rotating 12-hour shifts"}
used_names, users, truth_users = set(), [], {}
used_un = set()


def username(name):
    f, l = name.split()[0], name.split()[-1]
    base = (f[0] + l).lower().replace("-", "").replace("'", "")
    un, k = base, 2
    while un in used_un:
        un = f"{base}{k}"; k += 1
    used_un.add(un)
    return un


FIXED = [  # canon or required people: name, title, department, extras
    ("Fatima Al-Rasheed-Obinna", "Chief Information Security Officer", "Security Operations", {"note": "CISO who opens SI-2027-CC-001 (GW-EVT-106) and authorises isolation (GW-EVT-107)."}),
    ("Patricia Odom", "Communications Director", "Communications", {"note": "CHR-104, CBPWA communications director."}),
    ("Ricardo Vela", "Senior field engineer, protection and control", "Protection and Control",
     {"ot_account": "GW-ENG-VELA", "note": "Owner of credential GW-ENG-VELA. On approved leave, out of state, 2027-09-07 to 2027-09-21 (HR record). Credential stolen by phish; cooperating witness."}),
]
soc_ids = iter(["SOC-AN-01", "SOC-AN-02", "SOC-AN-03", "SOC-AN-04", "SOC-AN-05"])
ws_counter = [0]
RESERVED_WS = {4, 44}                   # GW-WS-IT-04 is assigned below; -44 was its name in the old SIEM file
corp_ws_numbers = [n for n in range(1, 221) if n not in RESERVED_WS]
ws_iter = iter(corp_ws_numbers)
zone_last = {"corp-users-ops": 10, "corp-users-biz": 10, "corp-users-admin": 10, "corp-users-field": 10}


def next_ip_last(zone):
    zone_last[zone] += 1
    if zone == "corp-users-admin" and zone_last[zone] == 47:      # 10.14.22.47 is GW-WS-IT-04
        zone_last[zone] += 1
    return zone_last[zone]


def add_user(name, title, dept, zone, shift, role_prefix, extra=None):
    un = username(name)
    u = {"user_id": f"U{len(users) + 1:04d}", "name": name, "username": un, "email": f"{un}@{MAIL_DOMAIN}", "title": title, "department": dept,
         "normal_hours": HOURS[shift], "account_type": "employee", "normal_hosts": []}
    extra = extra or {}
    if dept == "Security Operations" and "analyst" in title.lower():
        u["analyst_id"] = next(soc_ids)
    # workstation
    if dept == "System Operations":
        u["normal_hosts"] = ["GW-WS-OPS-01", "GW-WS-OPS-02", "GW-WS-OPS-03", "GW-WS-OPS-04", "GW-WS-OPS-05"]
    elif dept == "Security Operations":
        u["normal_hosts"] = [f"GW-WS-SOC-{1 + len([x for x in users if x['department'] == dept]) % 4:02d}"]
    else:
        z = zone if zone in zone_last else "corp-users-admin"
        n = next(ws_iter)
        laptop = dept in ("Field Services", "Water Operations", "Water Distribution", "Generation") and R.random() < 0.6
        hn = f"GW-LT-FLD-{n:02d}" if laptop else f"GW-WS-IT-{n:02d}"
        host(hn, z, next_ip_last(z), f"{'Field laptop' if laptop else 'Workstation'}, {dept}", R.choice([W10, W11, W11]), "laptop" if laptop else "workstation",
             "IT Infrastructure", primary_user=un, crit="low")
        u["normal_hosts"] = [hn]
    acct = extra.get("ot_account")
    if not acct and role_prefix and (dept in ("OT Engineering", "Protection and Control") or R.random() < 0.5):
        acct = f"GW-{role_prefix}-{name.split()[-1].upper().replace('-', '')}"
        if any(x.get("ot_account") == acct for x in users):
            acct = None
    if acct:
        u["ot_account"] = acct
        if role_prefix == "ENG" or acct.startswith("GW-ENG"):
            u["normal_hosts"] += ["GW-SYS-JMP-01", R.choice(ENG_WS)["hostname"]]
        elif role_prefix == "WTR":
            u["normal_hosts"] += ["GW-WTP-HMI-01", "GW-WTP-HMI-02"]
        elif role_prefix == "TEC":
            u["normal_hosts"] += ["GW-SYS-JMP-01"]
    if extra.get("note"):
        truth_users[un] = extra["note"]
    users.append(u)
    return u


TITLES = {
    "Executive Office": ["General Manager", "Deputy General Manager", "Chief Operating Officer", "Chief Financial Officer", "Executive Assistant", "Board Liaison"],
    "Finance and Procurement": ["Controller", "Procurement Manager", "Buyer", "Accounts Payable Specialist", "Accountant", "Budget Analyst", "Payroll Specialist"],
    "Human Resources": ["HR Director", "HR Generalist", "Benefits Coordinator", "Recruiter", "Training Coordinator"],
    "Customer Service": ["Customer Service Manager", "Customer Service Representative", "Billing Specialist", "Call Centre Supervisor"],
    "Communications": ["Communications Director", "Public Information Specialist", "Digital Communications Specialist"],
    "IT Infrastructure": ["IT Director", "Systems Administrator", "Network Engineer", "Service Desk Technician", "Database Administrator", "Desktop Support Technician"],
    "Security Operations": ["Security Operations Manager", "Security Analyst", "Security Analyst", "Security Analyst", "Security Engineer"],
    "System Operations": ["Operations Director", "Shift Supervisor", "Transmission Operator", "Distribution Operator", "Water System Operator", "Generation Dispatcher"],
    "OT Engineering": ["OT Engineering Manager", "SCADA Engineer", "Controls Engineer", "OT Network Engineer", "Historian Administrator"],
    "Protection and Control": ["Protection and Control Manager", "Relay Engineer", "Field engineer, protection and control", "Relay Technician"],
    "Transmission and Distribution Engineering": ["Engineering Manager", "Distribution Engineer", "Transmission Planner", "Standards Engineer", "Engineering Technician"],
    "Water Operations": ["Plant Superintendent", "Plant Operator", "Plant Operator", "Maintenance Mechanic", "Instrumentation Technician", "Distribution Supervisor", "Field Operator"],
    "Water Quality": ["Water Quality Manager", "Laboratory Analyst", "Compliance Specialist"],
    "Water Distribution": ["Distribution Superintendent", "Distribution Crew Leader", "Valve and Hydrant Technician", "Field Operator"],
    "Field Services": ["Field Services Manager", "Line Crew Foreman", "Lineman", "Substation Technician", "Meter Technician", "Troubleman", "Dispatcher"],
    "Generation": ["Plant Manager", "Control Room Operator", "Maintenance Planner"],
    "GIS and Planning": ["GIS Manager", "GIS Analyst", "System Planner"],
    "Legal and Regulatory": ["General Counsel", "Regulatory Affairs Manager", "Compliance Analyst", "Paralegal"],
    "Facilities and Fleet": ["Facilities Manager", "Fleet Coordinator", "Warehouse Supervisor", "Facilities Technician"],
}
fixed_by_dept = {}
for nm, title, dept, extra in FIXED:
    used_names.add(nm)
    fixed_by_dept.setdefault(dept, []).append((nm, title, extra))
for dept, count, zone, shift, prefix in DEPTS:
    done = 0
    for nm, title, extra in fixed_by_dept.get(dept, []):
        add_user(nm, title, dept, zone, shift, prefix, extra); done += 1
    tl = TITLES[dept]
    for i in range(count - done):
        j = i + done
        title = tl[j] if j < len(tl) and j < 2 and not any(f[1] == tl[j] for f in fixed_by_dept.get(dept, [])) else R.choice(tl[1:] if len(tl) > 1 else tl)
        if dept == "Security Operations":
            title = tl[i % len(tl)]
        add_user(person(used_names), title, dept, zone, shift, prefix)

# the workstation in the administration wing used by a contractor account
host("GW-WS-IT-04", "corp-users-admin", 47, "Workstation, administration wing (shared contractor desk)", W11, "workstation", "IT Infrastructure",
     primary_user="svc_fieldops_ext", crit="low", aliases=["GW-WS-IT-44"],
     note="Initial access: implant from the D-14 lure; first beacon 2027-08-31T03:17Z from 10.14.22.47 to 104.21.88.43:443; receives 1.9 GB from the historian over TCP 445 at D-6.")
# spare / shared machines
for i in range(6):
    n = next(ws_iter)
    host(f"GW-WS-IT-{n:02d}", "corp-users-biz", next_ip_last("corp-users-biz"), R.choice(["Conference room PC", "Kiosk, customer lobby", "Shared workstation, warehouse", "Spare workstation"]),
         W10, "workstation", "IT Infrastructure", crit="low")

service_accounts = [
    ("svc_backup", "Backup agent", "IT Infrastructure", ["GW-SRV-BKP-01"], "nightly 22:00-04:00"),
    ("svc_sql_erp", "Finance database service", "IT Infrastructure", ["GW-SRV-SQL-01", "GW-SRV-SQL-02", "GW-SRV-ERP-01"], "continuous"),
    ("svc_maximo", "Work-order system integration", "IT Infrastructure", ["GW-SRV-MAXIMO-01", "GW-SRV-SQL-01"], "continuous"),
    ("svc_oms", "Outage management integration", "IT Infrastructure", ["GW-SRV-OMS-01", "GW-SRV-GIS-01"], "continuous"),
    ("svc_gis_sync", "GIS replication", "GIS and Planning", ["GW-SRV-GIS-01", "GW-SRV-FILE-02"], "hourly"),
    ("svc_sccm", "Endpoint configuration management", "IT Infrastructure", ["GW-SRV-SCCM-01"], "continuous"),
    ("svc_wsus", "Patch distribution", "IT Infrastructure", ["GW-SRV-WSUS-01"], "nightly"),
    ("svc_print", "Print spooler", "IT Infrastructure", ["GW-SRV-PRINT-01"], "continuous"),
    ("svc_siem_collect", "SIEM log collection", "Security Operations", ["GW-SRV-SIEM-01", "GW-SRV-SIEM-02", "GW-SRV-SIEM-OT"], "continuous"),
    ("svc_edr", "Endpoint protection updates", "Security Operations", ["GW-SRV-EDR-01"], "continuous"),
    ("svc_vuln", "Vulnerability scanning", "Security Operations", ["GW-SRV-VULN-01"], "weekly, Sat 01:00-05:00"),
    ("svc_radius", "Network authentication", "IT Infrastructure", ["GW-SRV-RADIUS-01", "GW-VPN-EMP-01"], "continuous"),
    ("svc_hist_repl", "Historian replication to the DMZ replica", "OT Engineering", ["GW-SRV-HIST-01", "GW-SRV-HIST-DMZ"], "continuous"),
    ("svc_scada_hist", "SCADA to historian interface", "OT Engineering", ["GW-SYS-SCADA-01", "GW-SRV-HIST-01"], "continuous"),
    ("svc_iccp", "ICCP data exchange", "System Operations", ["GW-SRV-ICCP-01"], "continuous"),
    ("svc_otbackup", "OT backup agent", "OT Engineering", ["GW-SRV-OTBKP-01"], "nightly 01:00-03:00"),
    ("svc_otpatch", "OT patch staging", "OT Engineering", ["GW-SRV-OTPATCH-01"], "monthly maintenance window"),
    ("svc_meridian_support", "Vendor support account, Meridian Controls Corp", "OT Engineering", ["GW-SYS-JMP-01", "GW-SYS-SCADA-01"], "by change ticket only"),
    ("svc_vantage_mgmt", "Vendor support account, Vantage Security Systems", "Security Operations", ["GW-SRV-SIEM-01"], "by change ticket only"),
    ("svc_fieldops_ext", "Field operations contractor access (external)", "Field Services", ["GW-WS-IT-04", "GW-SYS-JMP-01"], "Mon-Fri 07:00-17:30"),
    ("svc_lims", "Laboratory information system", "Water Quality", ["GW-WTP-LAB-01"], "continuous"),
    ("svc_ivr", "Call centre IVR", "Customer Service", ["GW-SRV-IVR-01"], "continuous"),
]
truth_users["svc_fieldops_ext"] = ("Contractor account used by the intruder: created exception rule MAINT-EXCEPT-0892 (2027-08-19T11:34Z); historian sessions run as "
                                   r"GW-SYS-JMP-01\svc_fieldops_ext.")
svc = [{"account": a, "purpose": p, "owner_team": t, "normal_hosts": h, "normal_activity": w, "account_type": "service"} for a, p, t, h, w in service_accounts]

# --------------------------------------------------------------------------------------
# external systems referenced by network logs (other organisations)
# --------------------------------------------------------------------------------------
external = [
    {"system_id": "EXT-AIDPORTAL-01", "name": "Disaster aid applicant portal", "operator": "Federal Emergency Management Agency", "hostname": "portal.disasteraid.example", "ip": "192.0.2.130", "role": "Applicant accounts, direct-deposit details"},
    {"system_id": "EXT-CAD-01", "name": "Computer-aided dispatch system", "operator": "Coastal Bend Emergency Communications Center", "hostname": "cad01.cbecc.example", "ip": "10.100.5.10", "role": "911 call taking and dispatch"},
    {"system_id": "EXT-NASLOG-02", "name": "Base logistics system", "operator": "Naval Air Station Corpus Christi", "hostname": "log02.nascc.example", "ip": "10.200.8.22", "role": "Fuel and supply ordering"},
    {"system_id": "EXT-BRW-RMT-01", "name": "Remote-maintenance gateway", "operator": "Brightwake Marine Systems", "hostname": "rmt-gw.brightwake.example", "ip": "192.0.2.70", "role": "Vendor remote access to shipboard cargo-control systems"},
    {"system_id": "EXT-KALVORA-CCS", "name": "Cargo-control network, MT Kalvora Star", "operator": "vessel operator", "hostname": "ccs.kalvorastar.example", "ip": "10.31.1.0/24", "role": "Cargo valves, pumps and tank gauging"},
    {"system_id": "EXT-OSTREL-CCS", "name": "Cargo-control network, MT Ostrel Bay", "operator": "vessel operator", "hostname": "ccs.ostrelbay.example", "ip": "10.32.1.0/24", "role": "Cargo valves, pumps and tank gauging"},
    {"system_id": "EXT-CITY-MAIL", "name": "City of Corpus Christi mail gateway", "operator": "City of Corpus Christi", "hostname": "mx.cctexas.example", "ip": "192.0.2.150", "role": "Employee email"},
    {"system_id": "EXT-ERCOT-ICCP", "name": "ERCOT ICCP node", "operator": "Electric Reliability Council of Texas", "hostname": "iccp.ercot.example", "ip": "192.0.2.200", "role": "Grid operator data exchange"},
    {"system_id": "EXT-MERIDIAN-SUP", "name": "Vendor support portal", "operator": "Meridian Controls Corp", "hostname": "support.meridiancontrols.example", "ip": "192.0.2.210", "role": "SCADA vendor updates and support"},
    {"system_id": "EXT-VANTAGE-TEL", "name": "Security telemetry service", "operator": "Vantage Security Systems", "hostname": "telemetry.vantagesec.example", "ip": "192.0.2.220", "role": "SIEM and endpoint telemetry"},
]

registry = {
    "metadata": {"organisation": UTILITY, "abbr": ABBR, "description": "IT and OT hosts, network zones, equipment and accounts of the utility, for joining with network, SIEM, historian and work-order records.",
                 "ad_domain": AD_DOMAIN, "ot_domain": OT_DOMAIN, "mail_domain": MAIL_DOMAIN, "public_address_block": "203.0.113.16/28",
                 "siem": "Sentinel Edge 3.1 (Vantage Security Systems)", "scada": "Meridian HorizonView 4.2 (Meridian Controls Corp)",
                 "ot_remote_access": "ClearPath SecureReach 2.1 on GW-SYS-JMP-01 (ClearPath Network Solutions)",
                 "naming": {"workstations": "GW-WS-IT-nn (corporate), GW-LT-FLD-nn (field laptops), GW-WS-OPS-nn (operator consoles), GW-WS-ENG-nn (engineering)",
                            "servers": "GW-SRV-<role>-nn", "ot_assets": "GW-SYS-<type>-nn", "corporate_usernames": "first initial + surname",
                            "ot_accounts": "GW-<ROLE>-<SURNAME> (ENG engineering, OPS operations, WTR water, TEC technician)"},
                 "counts": {}},
    "sites": [{"site_id": s, "name": n, "type": t} for s, n, t in SITES],
    "network_zones": [{"zone": z, "name": n, "cidr": c, "vlan": v, "purdue_level": p, "site_id": s} for z, n, c, v, p, s in ZONES],
    "hosts": sorted(hosts, key=lambda h: (h["zone"], [int(x) for x in h["ip"].split(".")])),
    "equipment": equipment,
    "users": users,
    "service_accounts": svc,
    "external_systems": external,
}
registry["metadata"]["counts"] = {"hosts": len(hosts), "users": len(users), "service_accounts": len(svc), "equipment": len(equipment),
                                  "network_zones": len(ZONES), "external_systems": len(external)}
assert len({h["hostname"] for h in hosts}) == len(hosts)
json.dump(registry, open(os.path.join(OUT, "gw_host_registry.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ---------------- internal truth + migration
by_alias = {}
for h in hosts:
    for a in h.get("aliases", []):
        by_alias[a] = h["hostname"]
OLD_REG = {"GW-HIST-01": "GW-SRV-HIST-01", "GW-HIST-02": "GW-SRV-HIST-02", "GW-ENG-01": "user:GW-ENG-VELA (the old registry made the credential a workstation)",
           "GW-HMI-01": "GW-WTP-HMI-01", "GW-HMI-02": "GW-WS-OPS-02", "GW-HMI-03": "none (wastewater is run by the City of Corpus Christi, outside this estate)", "GW-RTU-WTP-01": "GW-SYS-RTU-UTL1",
           "GW-RTU-PWR-01": "GW-SYS-RTAC-UTL1-A", "GW-RTU-PWR-02": "GW-SYS-RTAC-UTL1-B", "GW-DMZ-01": "GW-SYS-JMP-01", "GW-IT-04": "GW-WS-IT-04",
           "GW-IT-EDR": "GW-SRV-EDR-01", "GW-IT-AD": "GW-SRV-DC-01", "GW-IT-EMAIL": "GW-SRV-MAIL-01", "GW-IT-FW": "GW-FW-EDGE-01", "GW-OT-FW": "GW-OT-FW-01",
           "GW-NET-MON": "GW-NET-MON-01", "GW-SCADA-SRV": "GW-SYS-SCADA-01", "GW-DCS-WTP": "GW-WTP-DCS-01", "GW-RTU-WW-01": "none (city wastewater)",
           "GW-BACKUP-PWR": "GW-WTP-GEN-CTRL", "GW-PSTN-01": "GW-SRV-COMMS-01", "GW-MAXIMO": "GW-SRV-MAXIMO-01", "HOST-911-01": "EXT-CAD-01",
           "HOST-PORTAL-01": "EXT-AIDPORTAL-01", "HOST-DOD-LOG-02": "EXT-NASLOG-02", "HOST-VSL-01": "EXT-KALVORA-CCS + EXT-OSTREL-CCS"}
SIEM_HOST = {"FW-EDGE-01": "GW-FW-EDGE-01", "VPN-GW-01": "GW-SYS-JMP-01", "GW-WS-IT-44": "GW-WS-IT-04", "GW-SRV-DC-01": "GW-SRV-DC-01", "GW-SRV-FILE-01": "GW-SRV-FILE-01",
             "GW-SRV-PRINT-01": "GW-SRV-PRINT-01", "HIST-SRV-01": "GW-SRV-HIST-01", "SCADA-SRV-01": "GW-SYS-SCADA-01", "RTU-PWR": "GW-SYS-RTAC-UTL1-A",
             "RTU-BKP": "GW-SYS-RTAC-UTL1-B", "RTU-PUMP": "GW-SYS-RTU-UTL1", "SUB-02": "GW-SYS-RTU-02", "FAC-UTL-01-P3": "GW-WTP-PLC-P3"}
for n in (10, 11, 12, 14, 15, 20, 30, 50):
    SIEM_HOST[f"GW-WS-IT-{n}"] = f"GW-WS-IT-{n}" if any(h["hostname"] == f"GW-WS-IT-{n}" for h in hosts) else f"GW-LT-FLD-{n}"
ipmap = {h["hostname"]: h["ip"] for h in hosts}
truth = {
    "_about": "Internal. Never delivered. What each host and account does in the scenario, the intruder's infrastructure, and how every older identifier maps onto gw_host_registry.json.",
    "hosts": truth_hosts,
    "accounts": truth_users,
    "restricted_identifiers": {"note": "Appear only in raw logs, never in public-voice text.", "ids": ["GW-ENG-VELA", "GW-SYS-JMP-01", "GW-WS-IT-04", "ClearPath SecureReach"]},
    "soc_analysts": {u["analyst_id"]: u["username"] for u in users if u.get("analyst_id")},
    "adversary_infrastructure": {
        "c2_first_beacon": {"dst_ip": "104.21.88.43", "dst_port": 443, "sni": "update-cdn.vantagesec-telemetry.net", "first_seen_utc": "2027-08-31T03:17Z", "last_seen_utc": "2027-10-12T10:04Z", "alert_family": "SE3-NET-9941"},
        "lookalike_domains": ["cbpwa-vendor-support.com (lure sender)", "update-cdn.meridiancontrols.net", "update-cdn.vantagesec-telemetry.net"],
        "lure_attachment": "FEMA-PREP-GUIDANCE-2027.pdf.exe",
        "vpn_exit_blocks": {"tor_exit": "185.220.101.0/24 (sessions D-7 to D-4 and D-3)", "nl_vps": "45.141.152.0/24 (D+7 14:27-14:33Z and later)",
                            "hosting_asn_198765": ["198.51.47.0/24", "198.51.48.0/24"], "asn_labels": ["AS-209144 (SIEM enrichment label)", "ASN 198765 Meridian Transit Hosting, NL (CISA annex)"]},
        "session_count": 14, "session_window": "D-7 to D+18 (2027-09-07 to 2027-10-02)", "historian_session_ids": ["HIST-20270907-00441", "HIST-20271002-00917"],
        "exception_rule": {"id": "MAINT-EXCEPT-0892", "created_utc": "2027-08-19T11:34Z", "created_by": "svc_fieldops_ext", "removed": "D+34"},
        "relay_file": r"\\gw-srv-ot-01\relayconfigs\sub02\rtu_config_draft.xml"},
    "id_migration": {
        "old_registry_host_ids": OLD_REG,
        "old_registry_hostnames": {"GW-ENG-VELA.gwcc.local": "user account GW-ENG-VELA (Ricardo Vela); no workstation of that name", "GW-SYS-JMP-01.gwcc.local": "GW-SYS-JMP-01",
                                   "GW-WS-IT-04.gwcc.local": "GW-WS-IT-04", "GW-EDR-SERVER.gwcc.local": "GW-SRV-EDR-01", "GW-AD-DC01.gwcc.local": "GW-SRV-DC-01", "GW-MAIL.gwcc.local": "GW-SRV-MAIL-01",
                                   "GW-FW-EDGE.gwcc.local": "GW-FW-EDGE-01", "GW-SCADA-SRV-01.gwcc.local": "GW-SYS-SCADA-01", "*.gwcc.local": f"*.{AD_DOMAIN} / *.{OT_DOMAIN}"},
        "siem_alerts_HostName": SIEM_HOST,
        "gridwater_assets_systems": {"GW-SYS-SCADA-01": "GW-SYS-SCADA-01", "GW-SYS-HST-01": "GW-SRV-HIST-01", "GW-SYS-JMP-01": "GW-SYS-JMP-01", **{f"GW-SYS-RTU-0{n}": f"GW-SYS-RTU-0{n}" for n in range(1, 6)}},
        "msel_names": {"GW-SRV-HIST-01": "GW-SRV-HIST-01", "gw-srv-ot-01": "GW-SRV-OT-01", "GW-WS-OPS-02": "GW-WS-OPS-02", "GW-WS-IT-04": "GW-WS-IT-04 (10.14.22.47)"},
        "old_ip_addresses": {
            "note": "The old registry, SIEM file and Zeek logs used three unrelated address plans. New records use the plan in gw_host_registry.json; these are the nearest equivalents.",
            "old_registry": {"10.72.1.10": ipmap["GW-SRV-HIST-01"], "10.72.1.11": ipmap["GW-SRV-HIST-02"], "10.72.1.22": "n/a (GW-ENG-VELA is an account)", "10.72.1.30": ipmap["GW-SYS-SCADA-01"],
                             "10.72.2.10": ipmap["GW-WTP-HMI-01"], "10.72.2.11": ipmap["GW-WS-OPS-02"], "10.72.2.12": "n/a (city wastewater)", "10.72.2.50": ipmap["GW-WTP-GEN-CTRL"],
                             "10.72.3.10": ipmap["GW-SYS-RTU-UTL1"], "10.72.3.11": ipmap["GW-SYS-RTAC-UTL1-A"], "10.72.3.12": ipmap["GW-SYS-RTAC-UTL1-B"], "10.72.3.20": ipmap["GW-WTP-DCS-01"],
                             "10.72.3.30": "n/a (city wastewater)", "10.72.4.1": ipmap["GW-OT-FW-01"], "10.72.4.50": ipmap["GW-NET-MON-01"], "10.72.4.88": ipmap["GW-SYS-JMP-01"],
                             "192.168.100.1": ipmap["GW-FW-EDGE-01"], "192.168.100.5": ipmap["GW-SRV-DC-01"], "192.168.100.10": ipmap["GW-SRV-EDR-01"], "192.168.100.20": ipmap["GW-SRV-MAIL-01"],
                             "192.168.100.44": ipmap["GW-WS-IT-04"], "192.168.100.80": ipmap["GW-SRV-COMMS-01"], "192.168.100.90": ipmap["GW-SRV-MAXIMO-01"], "198.51.100.42": "192.0.2.70 (Brightwake remote-maintenance gateway)"},
            "siem_alerts": {"10.72.1.0/24 sources (workstation-like)": "corporate user ranges 10.14.20.0/22", "10.72.2.1, 10.72.2.3, 10.72.2.5": "corporate workstations", "10.72.3.x": "substation and plant devices 10.72.11-15.x, 10.72.30.x",
                            "198.51.100.88, 198.51.100.7, 198.51.100.111, 203.0.113.42, 192.0.2.14, 45.33.32.156": "generic internet noise; choose from documentation ranges but never 198.51.100.44 (reserved for a canon fraud address)",
                            "91.108.56.33, 185.220.101.47": "intruder exits: use adversary_infrastructure blocks"},
            "zeek_conn_log": {"10.72.3.1": ipmap["GW-SRV-FEP-01"] + " (DNP3 master)", "10.72.3.20-22": "substation RTUs " + ", ".join(ipmap[f"GW-SYS-RTU-0{n}"] for n in (1, 2, 3)),
                              "10.72.3.5-7": "water site RTUs", "10.72.2.10": ipmap["GW-WS-OPS-01"], "10.72.2.5": ipmap["GW-WS-OPS-02"], "10.72.1.5": ipmap["GW-SRV-OTDC-01"],
                              "10.72.1.20": ipmap["GW-SRV-OT-01"], "10.72.1.15": ipmap["GW-SRV-HIST-01"], "10.72.1.51-60": "engineering and operator workstations", "10.72.1.1/10.72.1.2": ipmap["GW-OT-FW-01"],
                              "91.108.56.33, 45.77.218.95, 185.220.101.47, 212.129.33.11": "intruder exits: use adversary_infrastructure blocks"}},
        "maximo_assetnum": {"GW-PP1-PUMP1": "EQP-1101", "GW-PP1-PUMP2": "EQP-1102", "GW-PP1-PUMP3": "EQP-1103", "GW-PP1-PUMP4": "EQP-1104", "GW-PP1-CHEM-FEED": "EQP-1130",
                            "GW-PP1-RTU": "GW-SYS-RTU-UTL1", "GW-PWR-RTU": "GW-SYS-RTAC-UTL1-A", "GW-BKP-RTU": "GW-SYS-RTAC-UTL1-B", "GW-GEN-01": "EQP-1140",
                            "GW-SUB01-BKR-MAIN": "same (CB-1)", "GW-SUB02-BKR-MAIN": "same (CB-7)", "GW-SUB03-BKR-MAIN": "same (CB-12)"},
        "names": {"GridWater / GridWater CC / gwcc": "Coastal Bend Power and Water Authority (CBPWA)", "ClearPath SecureReach EDR Server (old registry)": "GW-SRV-EDR-01; ClearPath is the OT remote-access vendor only",
                  "Dragos OT Firewall (real vendor name in old registry)": "Bastille Networks industrial firewall (fictional)", "AVEVA PI / Yokogawa / Schneider / SEL / GE / Fortinet / Cummins (real vendor names in old files)": "Meridian Controls Corp, Halden Protection, Bastille Networks (fictional)"}},
    "breaker_yard_designations": {"GW-FAC-SUB-02": {"CB-7": "B2-A (opened by command D+7 14:28Z)", "CB-8": "B2-C (opens by transfer trip with CB-7)"}, "GW-FAC-SUB-03": {"CB-12": "B3-B (opened by command D+10 19:43Z)"}},
    "ids_shared_with_other_registries": {"sites and equipment": "infrastructure_assets.json (GW-FAC-*, EQP-11xx, FAC-UTL-02-A/B, GW-SUB0n-BKR-MAIN, GW-SUB0n-REL-27, GW-FAC-DSS-01)",
                                         "pressure zones": "areas.json AREA-PZ-1..5", "added here": ["GW-SUB0n-CB-<m>", "GW-SUB0n-REL-R0nX", "GW-SUB0n-T1", "GW-SUB0n-BUS", "GW-DSS01-*", "GW-FAC-WTR-0n-BPk",
                                                                                               "GW-FAC-UTL-01-CLEARWELL", "GW-FAC-UTL-01-TP1/TP2", "GW-FAC-GEN-01-U1"]},
}
json.dump(truth, open(os.path.join(INT, "gw_host_registry_truth.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ======================================================================================
# SCADA tags
# ======================================================================================
old = json.load(open(os.path.join(OUT, "scada_tags.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "scada_tags.json")) else {"tags": []}
old_src = os.path.join(INT, "scada_tags_v1_source.json")
if any("notes" in t for t in old.get("tags", [])) and not os.path.exists(old_src):
    json.dump(old, open(old_src, "w", encoding="utf-8"), indent=1, ensure_ascii=False)       # keep the original once
if os.path.exists(old_src):
    old = json.load(open(old_src, encoding="utf-8"))
old_notes = {t["tagname"]: t.get("notes") for t in old["tags"] if t.get("notes")}

SITE_OF = {}
SERVED = {**{f"GW-FAC-SUB-0{n}": f"GW-SYS-RTU-0{n}" for n in range(1, 6)}, "GW-FAC-UTL-01": "GW-SYS-RTU-UTL1", "GW-FAC-DSS-01": "GW-SYS-RTU-DSS1", "GW-FAC-GEN-01": "GW-SYS-RTU-GEN1",
          **{f"GW-FAC-WTR-0{n}": f"GW-SYS-RTU-WTR{n}" for n in range(1, 4)}, **{f"GW-FAC-TK-0{n}": f"GW-SYS-RTU-TK0{n}" for n in range(1, 10)},
          "GW-SYS-SCADA-01": "GW-SYS-SCADA-01", "GW-SYS-HST-01": "GW-SRV-HIST-01", "GW-SYS-JMP-01": "GW-SYS-JMP-01", **{f"GW-SYS-RTU-0{n}": f"GW-SYS-RTU-0{n}" for n in range(1, 6)}}
ALIASES = {"GW.UTL1.PUMP3.PRESS.SP": ["FAC-UTL-01-P3-SET-PSI"], "GW.WTR3.PUMP1.PRESS.SP": ["GW-FAC-WTR-03-BSTR-SET-PSI"]}
tags, tag_truth, migration = [], {}, {}


def scan_class(sec):
    return "fast" if sec <= 2 else "normal" if sec <= 10 else "slow" if sec <= 120 else "report-by-exception"


def equip_for(t):
    name, site = t["tagname"], SITE_OF.get(t["asset_id"], t["asset_id"])
    p = name.split(".")
    if p[1].startswith("SUB"):
        n = int(p[1][3:])
        if p[2] == "REL":
            return f"GW-SUB0{n}-REL-27"
        if p[2] == "BKR1":
            return f"GW-SUB0{n}-BKR-MAIN"
        if p[2] == "FDR1":
            return f"GW-SUB0{n}-CB-{MAIN_CB[n] + (1 if n != 3 else -1)}"
        return f"GW-SUB0{n}-BUS"
    if p[1] == "UTL1":
        if p[2].startswith("PUMP"):
            return f"EQP-110{p[2][4:]}"
        if p[2] == "CL2":
            return "EQP-1130"
        return "GW-FAC-UTL-01"
    if p[1].startswith("WTR"):
        return f"GW-FAC-WTR-0{p[1][3:]}-BP{p[2][4:]}"
    if p[1] == "GEN1":
        return "GW-FAC-GEN-01-U1"
    if p[1].startswith("TK"):
        return f"GW-FAC-TK-{p[1][2:]}"
    if p[1].startswith("RTU"):
        return f"GW-SYS-RTU-0{p[1][3:]}"
    return {"SCADA": "GW-SYS-SCADA-01", "HST": "GW-SRV-HIST-01", "JMP": "GW-SYS-JMP-01"}.get(p[1], site)


def add_tag(name, desc, site, equip, meas, ftype, eu, lo=None, hi=None, alo=None, ahi=None, clo=None, chi=None, scan=5, dtype="float", vmap=None, aliases=None, served=None, truth_note=None):
    t = {"tagname": name, "description": desc, "site_id": site, "equipment_id": equip, "measurement": meas, "field_type": ftype, "engineering_units": eu,
         "normal_low": lo, "normal_high": hi, "alarm_low": alo, "alarm_high": ahi, "critical_low": clo, "critical_high": chi,
         "scan_rate_seconds": scan, "scan_class": scan_class(scan), "data_type": dtype, "served_by": served or SERVED.get(site, "GW-SYS-SCADA-01")}
    if vmap:
        t["value_map"] = vmap
    if aliases:
        t["aliases"] = aliases
    tags.append(t)
    if truth_note:
        tag_truth[name] = truth_note
    return t


for t in old["tags"]:
    name = t["tagname"]
    p = name.split(".")
    site = SITE_OF.get(t["asset_id"], t["asset_id"])
    desc = t["description"]
    if p[2] == "BKR1":
        n = int(p[1][3:])
        desc = f"{SUBS[n][0]} - Main breaker CB-{MAIN_CB[n]} position" + (f" (yard {YARD[MAIN_CB[n]]})" if MAIN_CB[n] in YARD else "")
        old_notes[name] = {2: "Opened by command D+7 14:28Z (GW-EVT-005); closed again D+35.", 3: "Opened by command D+10 19:43Z (GW-EVT-007); closed again D+35.", 1: "Trips D0 07:12Z on the altered 27-UV threshold (GW-EVT-004)."}.get(n)
    add_tag(name, desc, site, equip_for(t), t.get("measurement"), t.get("field_type"), t.get("engineering_units"), t.get("normal_low"), t.get("normal_high"),
            t.get("alarm_low"), t.get("alarm_high"), t.get("critical_low"), t.get("critical_high"), t.get("scan_rate_seconds", 5), t.get("data_type", "float"),
            t.get("value_map"), ALIASES.get(name), truth_note=old_notes.get(name))

BK = {"0": "Open", "1": "Closed", "2": "Fault/Trip"}
for n, (sname, cbs) in SUBS.items():
    site = f"GW-FAC-SUB-0{n}"
    for cb in cbs:
        if cb == MAIN_CB[n]:
            add_tag(f"GW.SUB{n}.BKR1.CMD.SP", f"{sname} - Main breaker CB-{cb} control command", site, f"GW-SUB0{n}-BKR-MAIN", "Command", "SP", "enum", scan=300, dtype="integer", vmap={"0": "Open", "1": "Close"})
            continue
        eq = f"GW-SUB0{n}-CB-{cb}"
        add_tag(f"GW.SUB{n}.CB{cb}.STATUS.STS", f"{sname} - Breaker CB-{cb} position" + (f" (yard {YARD[cb]})" if cb in YARD else ""), site, eq, "Status", "STS", "enum", scan=2, dtype="integer", vmap=BK,
                truth_note={8: "Opens with CB-7 by transfer trip (D+7 14:28Z); imaged open D+8."}.get(cb))
        add_tag(f"GW.SUB{n}.CB{cb}.CMD.SP", f"{sname} - Breaker CB-{cb} control command", site, eq, "Command", "SP", "enum", scan=300, dtype="integer", vmap={"0": "Open", "1": "Close"})
        add_tag(f"GW.SUB{n}.CB{cb}.CURR.PV", f"{sname} - Breaker CB-{cb} current", site, eq, "Current", "PV", "A", 80, 900, None, 1100, None, 1250, 5)
    letters = "ABC" if n in (1, 2) else "AB"
    for L in letters:
        eq = f"GW-SUB0{n}-REL-R0{n}{L}"
        add_tag(f"GW.SUB{n}.REL{L}.OC_THR.SP", f"{sname} - Relay R-0{n}{L} overcurrent pickup", site, eq, "Setting", "SP", "A", 1200, 1200, scan=300,
                truth_note="Changed 1200 A to 2400 A in the altered configuration (found D+28)." if (n == 2 or (n == 3 and L == "A")) else None)
        add_tag(f"GW.SUB{n}.REL{L}.TRIP.STS", f"{sname} - Relay R-0{n}{L} trip output", site, eq, "Status", "STS", "enum", scan=2, dtype="integer", vmap={"0": "Normal", "1": "Trip"})
    add_tag(f"GW.SUB{n}.T1.OILTEMP.PV", f"{sname} - Transformer T1 top-oil temperature", site, f"GW-SUB0{n}-T1", "Temperature", "PV", "degC", 35, 80, None, 95, None, 105, 60)
    add_tag(f"GW.SUB{n}.T1.TAP.PV", f"{sname} - Transformer T1 tap position", site, f"GW-SUB0{n}-T1", "Position", "PV", "step", 1, 17, scan=60, dtype="integer")
    add_tag(f"GW.SUB{n}.BUS.FREQ.PV", f"{sname} - Bus frequency", site, f"GW-SUB0{n}-BUS", "Frequency", "PV", "Hz", 59.95, 60.05, 59.8, 60.2, 59.5, 60.5, 2)
    add_tag(f"GW.SUB{n}.YARD.DOOR.STS", f"{sname} - Control house door contact", site, site, "Status", "STS", "enum", scan=2, dtype="integer", vmap={"0": "Closed", "1": "Open"})
    add_tag(f"GW.SUB{n}.BATT.VOLT.PV", f"{sname} - Station battery voltage", site, site, "Voltage", "PV", "V DC", 125, 135, 118, 140, 110, 145, 60)
D = "GW-FAC-DSS-01"
add_tag("GW.DSS1.BUS.VOLT.PV", "McKinley Substation - 12.5 kV bus voltage", D, "GW-DSS01-BKR-MAIN", "Voltage", "PV", "kV", 12.0, 13.1, 11.4, 13.5, 10.8, 14.0, 5, truth_note="Dead from D0 06:17Z until D+8 09:14 local.")
add_tag("GW.DSS1.BKR1.STATUS.STS", "McKinley Substation - Main breaker position", D, "GW-DSS01-BKR-MAIN", "Status", "STS", "enum", scan=2, dtype="integer", vmap=BK)
for fd in (11, 12):
    add_tag(f"GW.DSS1.FDR{fd}.STATUS.STS", f"McKinley Substation - Feeder {fd} breaker position", D, f"GW-DSS01-FDR-{fd}", "Status", "STS", "enum", scan=2, dtype="integer", vmap=BK)
    add_tag(f"GW.DSS1.FDR{fd}.CURR.PV", f"McKinley Substation - Feeder {fd} current", D, f"GW-DSS01-FDR-{fd}", "Current", "PV", "A", 60, 420, None, 520, None, 600, 5)
add_tag("GW.DSS1.T1.LOAD.PV", "McKinley Substation - Transformer T1 loading", D, "GW-DSS01-T1", "Power", "PV", "MVA", 4, 22, None, 26, None, 30, 10)
W = "GW-FAC-UTL-01"
add_tag("GW.DIST.ZONE4.PRESS.PV", "Distribution pressure zone 4 - system pressure", "AREA-PZ-4", "AREA-PZ-4", "Pressure", "PV", "psi", 45, 70, 35, 85, 20, 95, 5, aliases=["ZONE4-DIST-PSI"], served="GW-SYS-RTU-UTL1",
        truth_note="Crosses 20 psi downward D+9 05:51Z; 14 psi at D+10 20:10Z; 16.4 psi manual query D+12 15:52Z; above 40 psi D+42.")
for z in (1, 2, 3, 5):
    add_tag(f"GW.DIST.ZONE{z}.PRESS.PV", f"Distribution pressure zone {z} - system pressure", f"AREA-PZ-{z}", f"AREA-PZ-{z}", "Pressure", "PV", "psi", 45, 70, 35, 85, 20, 95, 5, aliases=[f"ZONE{z}-DIST-PSI"], served="GW-SYS-RTU-UTL1")
for z in range(1, 6):
    add_tag(f"GW.DIST.ZONE{z}.DEMAND.PV", f"Distribution pressure zone {z} - demand", f"AREA-PZ-{z}", f"AREA-PZ-{z}", "Flow", "PV", "MGD", 4, 22, None, 28, None, 32, 60, served="GW-SYS-RTU-UTL1")
add_tag("GW.UTL1.RAW.TPH.PV", "O.N. Stevens Water Treatment Plant - Raw-water intake total petroleum hydrocarbons", W, "EQP-1120", "Concentration", "PV", "mg/L", 0, 0.05, None, 0.10, None, 0.50, 300,
        aliases=["FAC-UTL-01-RAW-TPH-MGL"], served="GW-WTP-HIST-01", truth_note="0.02 at D+1 00:00Z, 0.42 at D+2 06:00Z, 0.08 at D+8, 0.03 at D+14 (EVT-2003).")
add_tag("GW.UTL1.RAW.TURB.PV", "O.N. Stevens Water Treatment Plant - Raw-water turbidity", W, "EQP-1120", "Turbidity", "PV", "NTU", 5, 60, None, 150, None, 300, 60, served="GW-WTP-DCS-01")
add_tag("GW.UTL1.RAW.FLOW.PV", "O.N. Stevens Water Treatment Plant - Raw-water inflow", W, "EQP-1120", "Flow", "PV", "MGD", 40, 80, 25, None, 15, None, 10, served="GW-WTP-DCS-01")
add_tag("GW.UTL1.FIN.TURB.PV", "O.N. Stevens Water Treatment Plant - Finished-water turbidity", W, "GW-FAC-UTL-01-CLEARWELL", "Turbidity", "PV", "NTU", 0.02, 0.15, None, 0.3, None, 1.0, 60, served="GW-WTP-DCS-01")
add_tag("GW.UTL1.FIN.CL2RES.PV", "O.N. Stevens Water Treatment Plant - Finished-water chlorine residual", W, "GW-FAC-UTL-01-CLEARWELL", "Concentration", "PV", "mg/L", 1.5, 3.5, 0.8, 4.0, 0.5, None, 60, served="GW-WTP-DCS-01")
add_tag("GW.UTL1.CLEARWELL.LEVEL.PV", "O.N. Stevens Water Treatment Plant - Clearwell level", W, "GW-FAC-UTL-01-CLEARWELL", "Level", "PV", "ft", 12, 20, 8, 21, 5, 22, 10, served="GW-WTP-DCS-01")
add_tag("GW.UTL1.HSP.DISCH.PRESS.PV", "O.N. Stevens Water Treatment Plant - High-service header discharge pressure", W, "EQP-1110", "Pressure", "PV", "psi", 78, 92, 65, 100, 50, 110, 2)
for f in ("A", "B"):
    add_tag(f"GW.UTL1.FEED{f}.VOLT.PV", f"O.N. Stevens Water Treatment Plant - Power feed {f} voltage", W, f"FAC-UTL-02-{f}", "Voltage", "PV", "kV", 12.0, 13.2, 11.4, 13.6, 10.8, 14.0, 5, served=f"GW-SYS-RTAC-UTL1-{f}")
    add_tag(f"GW.UTL1.FEED{f}.BKR.STATUS.STS", f"O.N. Stevens Water Treatment Plant - Power feed {f} breaker", W, f"FAC-UTL-02-{f}", "Status", "STS", "enum", scan=2, dtype="integer", vmap=BK, served=f"GW-SYS-RTAC-UTL1-{f}")
add_tag("GW.UTL1.GEN.RUN.STS", "O.N. Stevens Water Treatment Plant - Pump room emergency generator run status", W, "EQP-1140", "Status", "STS", "enum", scan=2, dtype="integer", vmap={"0": "Stopped", "1": "Running", "2": "Fault"}, served="GW-WTP-GEN-CTRL")
add_tag("GW.UTL1.GEN.FUEL.PV", "O.N. Stevens Water Treatment Plant - Pump room emergency generator fuel level", W, "EQP-1140", "Level", "PV", "%", 60, 100, 30, None, 15, None, 300, served="GW-WTP-GEN-CTRL")
for k in (1, 2):
    add_tag(f"GW.UTL1.TP{k}.RUN.STS", f"O.N. Stevens Water Treatment Plant - Temporary pump TP-{k} run status", W, f"GW-FAC-UTL-01-TP{k}", "Status", "STS", "enum", scan=5, dtype="integer", vmap={"0": "Stopped", "1": "Running", "2": "Fault"})
    add_tag(f"GW.UTL1.TP{k}.FLOW.PV", f"O.N. Stevens Water Treatment Plant - Temporary pump TP-{k} flow", W, f"GW-FAC-UTL-01-TP{k}", "Flow", "PV", "MGD", 0, 9, None, None, None, None, 10)
for i in range(1, 5):
    add_tag(f"GW.UTL1.PUMP{i}.VIB.PV", f"O.N. Stevens Water Treatment Plant - Pump P-{i} vibration", W, f"EQP-110{i}", "Vibration", "PV", "in/s", 0.05, 0.20, None, 0.30, None, 0.45, 10,
            truth_note="P-2 vibration trends up from D-55 (EVT-0102); fails D0." if i == 2 else None)
    add_tag(f"GW.UTL1.PUMP{i}.SPEED.SP", f"O.N. Stevens Water Treatment Plant - Pump P-{i} speed setpoint", W, f"EQP-110{i}", "Speed", "SP", "RPM", 1300, 1480, None, None, None, None, 300,
            aliases=["FAC-UTL-01-PUMP-SP-RPM"] if i == 3 else None)
    add_tag(f"GW.UTL1.PUMP{i}.WINDTEMP.PV", f"O.N. Stevens Water Treatment Plant - Pump P-{i} motor winding temperature", W, f"EQP-110{i}", "Temperature", "PV", "degC", 55, 95, None, 120, None, 140, 10,
            truth_note="P-3 overheats at D0 (EVT-0302)." if i == 3 else None)
add_tag("GW.WTR3.STATION.PRESS.SP", "Colorado River Booster Station - Station discharge pressure setpoint", "GW-FAC-WTR-03", "GW-FAC-WTR-03", "Pressure", "SP", "psi", 72, 72, scan=300,
        aliases=["GW-FAC-WTR-03-BSTR-SET-PSI"], truth_note="72 to 54 psi at D+9 02:08Z (GW-EVT-013).")
ALIASES_FIX = "GW.WTR3.PUMP1.PRESS.SP"
for t in tags:
    if t["tagname"] == ALIASES_FIX:
        t.pop("aliases", None)
add_tag("GW.SCADA.OPS02.SESSION.STS", "SCADA - Operator console GW-WS-OPS-02 session state", "GW-SYS-SCADA-01", "GW-SYS-SCADA-01", "Status", "STS", "enum", scan=60, dtype="integer",
        vmap={"0": "No operator logged in", "1": "Operator logged in"}, truth_note="0 at both breaker-open commands.")
add_tag("GW.SCADA.ALARM_SUPR_CHG.PV", "SCADA - Alarm suppression list change counter", "GW-SYS-SCADA-01", "GW-SYS-SCADA-01", "Count", "PV", "count", 0, 2, None, 5, None, None, 300, dtype="integer",
        truth_note="7 changes since D-5; suppressed count 94 at D+9 04:00Z (GW-EVT-105).")
add_tag("GW.SCADA.EXT_ISOLATED.STS", "SCADA - External network isolation flag", "GW-SYS-SCADA-01", "GW-SYS-SCADA-01", "Status", "STS", "enum", scan=60, dtype="integer",
        vmap={"0": "Connected", "1": "Isolated"}, truth_note="Set D+28 12:00Z (GW-EVT-014).")

alarms = []
for z in range(1, 6):
    alarms.append({"alarm_id": f"ZONE{z}-LOW-PRES", "description": f"Pressure zone {z} low distribution pressure", "source_tag": f"GW.DIST.ZONE{z}.PRESS.PV", "priority": "high", "setpoint": "< 35 psi", "site_id": f"AREA-PZ-{z}"})
for n, (sname, cbs) in SUBS.items():
    for L in ("ABC" if n in (1, 2) else "AB"):
        alarms.append({"alarm_id": f"SUB{n:02d}-R{n:02d}{L}-TRIP", "description": f"{sname} relay R-0{n}{L} trip", "source_tag": f"GW.SUB{n}.REL{L}.TRIP.STS", "priority": "critical", "setpoint": "= 1", "site_id": f"GW-FAC-SUB-0{n}"})
    alarms.append({"alarm_id": f"SUB{n:02d}-UV", "description": f"{sname} bus undervoltage", "source_tag": f"GW.SUB{n}.BUS.VOLT.PV", "priority": "high", "setpoint": "below alarm_low", "site_id": f"GW-FAC-SUB-0{n}"})
    for cb in cbs:
        alarms.append({"alarm_id": f"SUB{n:02d}-CB{cb}-OPEN", "description": f"{sname} breaker CB-{cb} unexpected open", "source_tag": f"GW.SUB{n}.BKR1.STATUS.STS" if cb == MAIN_CB[n] else f"GW.SUB{n}.CB{cb}.STATUS.STS", "priority": "high", "setpoint": "= 0 without command", "site_id": f"GW-FAC-SUB-0{n}"})
for i in range(1, 5):
    alarms.append({"alarm_id": f"UTL1-P{i}-LOW-DISCH", "description": f"Pump P-{i} low discharge pressure", "source_tag": f"GW.UTL1.PUMP{i}.PRESS.PV", "priority": "high", "setpoint": "below alarm_low", "site_id": W})
    alarms.append({"alarm_id": f"UTL1-P{i}-VIB-HIGH", "description": f"Pump P-{i} high vibration", "source_tag": f"GW.UTL1.PUMP{i}.VIB.PV", "priority": "medium", "setpoint": "> 0.30 in/s", "site_id": W})
alarms += [{"alarm_id": "UTL1-RAW-TPH-HIGH", "description": "Raw-water hydrocarbons above alert level", "source_tag": "GW.UTL1.RAW.TPH.PV", "priority": "critical", "setpoint": "> 0.10 mg/L", "site_id": W, "aliases": ["FAC-UTL-01-RAW-TPH-HIGH"]},
           {"alarm_id": "UTL1-CL2-RES-LOW", "description": "Finished-water chlorine residual low", "source_tag": "GW.UTL1.FIN.CL2RES.PV", "priority": "critical", "setpoint": "< 0.8 mg/L", "site_id": W},
           {"alarm_id": "UTL1-FEED-LOSS", "description": "Plant power feed lost", "source_tag": "GW.UTL1.FEEDA.BKR.STATUS.STS", "priority": "critical", "setpoint": "feed A or B open", "site_id": W}]
for i in range(1, 10):
    alarms.append({"alarm_id": f"TK{i:02d}-LOW-LEVEL", "description": f"{TANKS[i - 1]} low level", "source_tag": f"GW.TK{i:02d}.LEVEL_PCT.PV", "priority": "high", "setpoint": "< 50 %", "site_id": f"GW-FAC-TK-0{i}"})

assert len({t["tagname"] for t in tags}) == len(tags)
catalog = {"schema_version": "2.0", "organisation": UTILITY, "historian": "Meridian Historian on GW-SRV-HIST-01 (SCADA: Meridian HorizonView 4.2)",
           "tag_naming": "GW.<site>.<equipment>.<measurement>.<PV|SP|STS>; 'aliases' are the point names used in older plant documents and reports",
           "export_format": "Tagname,Timestamp,Value,Quality", "timestamp_format": "ISO 8601 UTC",
           "quality_codes": {"192": "Good", "0": "Bad / no data", "64": "Uncertain", "216": "Good, local override"},
           "scan_classes": {"fast": "2 s or faster", "normal": "5-10 s", "slow": "30-120 s", "report-by-exception": "on change, at least every 5 min"},
           "sites": sorted({t["site_id"] for t in tags}), "counts": {"tags": len(tags), "alarm_points": len(alarms)}, "tags": tags, "alarm_points": alarms}
json.dump(catalog, open(os.path.join(OUT, "scada_tags.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump({"_about": "Internal. Never delivered. What each tag shows in the scenario and how old tag and asset names map onto scada_tags.json v2.",
           "tag_events": tag_truth,
           "suppressed_alarms": {"since": "D-3 17:09Z", "ids": ["ZONE4-LOW-PRES"] + [a["alarm_id"] for a in alarms if a["alarm_id"].endswith("-TRIP") and a["alarm_id"][:5] in ("SUB01", "SUB02", "SUB03", "SUB04")],
                                 "note": "Relay trip alarms for SUB-01 to SUB-04 and the zone 4 low-pressure alarm; list grows to 94 entries by D+9."},
           "id_migration": {"tags": migration, "asset_id": {"FAC-UTL-01": "GW-FAC-UTL-01 (as in infrastructure_assets.json; FAC-UTL-01 is its alias)"},
                            "removed_fields": ["notes (explained the attack)", "attack_summary", "attack_signature_tags"],
                            "historian_stream_columns": {"AttackSig": "remove (answer leak)", "AssetID": "site_id", "Subsystem": "site name"},
                            "canon_point_names": {"FAC-UTL-01-P3-SET-PSI": "GW.UTL1.PUMP3.PRESS.SP", "ZONE4-DIST-PSI": "GW.DIST.ZONE4.PRESS.PV", "ZONE4-LOW-PRES": "alarm point ZONE4-LOW-PRES",
                                                  "GW-FAC-WTR-03-BSTR-SET-PSI": "GW.WTR3.STATION.PRESS.SP", "FAC-UTL-01-RAW-TPH-MGL": "GW.UTL1.RAW.TPH.PV", "FAC-UTL-01-PUMP-SP-RPM": "GW.UTL1.PUMP3.SPEED.SP",
                                                  "SUB-02 CB-7": "GW.SUB2.BKR1.STATUS.STS", "SUB-03 CB-12": "GW.SUB3.BKR1.STATUS.STS", "relay 27-UV threshold": "GW.SUB<n>.REL.UV_THR.SP"}}},
          open(os.path.join(INT, "scada_tags_truth.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"hosts {len(hosts)}  users {len(users)}  service accounts {len(svc)}  equipment {len(equipment)}  tags {len(tags)}  alarm points {len(alarms)}")
