"""Host-side model shared by gen_itsec_host.py and probes_itsec_host.py.

Everything here is a pure function of the delivered logs and the registry (hash-keyed, no sequential
random state), so a month can be generated on its own and still agree with its neighbours.

  accounts and software        acct(), IMG, sha_of(), placeholder_text()
  delivered logs, light readers conn_day(), dns_day(), alerts_between(), gateway sessions
  power                         boots(), is_up(), last_boot()
  process ids                   pid()
"""
import bisect
import csv
import datetime as dt
import functools
import hashlib
import os

import itsec_shared as S
from common import D0_EPOCH, ROOT, UTC, local_dt, local_ts, ts

G, M = S.G, S.M
DAY = 86400
NETDIR = os.path.join(ROOT, S.NET)
# one day of lead-in (the endpoint-protection table starts 2027-07-15) and the whole of the last UTC day, like the delivered logs
SPAN_A, SPAN_B = G.SPAN_START - DAY, D0_EPOCH + (S.LAST_DAY + 1) * DAY
T0 = D0_EPOCH - 75 * DAY
FIRST_LDAY, LAST_LDAY = -60, 120                          # local scenario days with ordinary sessions

WIN = {h["hostname"]: h for h in S.WINDOWS}
WIN_IP = {h["ip"]: h["hostname"] for h in S.WINDOWS}
IP = S.IP
JMP, WS04, HIST1, HISTDMZ, SCADA1, OPS02, OT01 = G.JMP, G.WS04, G.HIST1, G.HISTDMZ, G.SCADA1, G.OPS02, "GW-SRV-OT-01"
USER_BY_MAIL = {u["email"]: u for u in S.USERS}
ADMIN_DEPTS = ("IT Infrastructure", "Security Operations")
ADMINS = {u["username"] for u in S.USERS if u["department"] in ADMIN_DEPTS}
IT_ADMINS = sorted(u["username"] for u in S.USERS if u["department"] == "IT Infrastructure")
OT_ACCT = {u["username"]: u["ot_account"] for u in S.USERS if u.get("ot_account")}
SVC = {a["account"]: a for a in S.REG["service_accounts"]}


# ---- small helpers ----------------------------------------------------------------------------------------
def h01(*k):
    return int(hashlib.sha256("|".join(map(str, k)).encode()).hexdigest()[:12], 16) / 16 ** 12


def hint(n, *k):
    return int(h01(*k) * n)


def hx(*k, n=8):
    return hashlib.sha256("|".join(map(str, k)).encode()).hexdigest()[:n]


def pick(seq, *k):
    return seq[hint(len(seq), *k)]


def iso_ms(t):
    t = round(float(t), 3)
    d = dt.datetime.fromtimestamp(int(t), UTC)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(round((t - int(t)) * 1000)) % 1000:03d}Z"


def is_ot(host):
    return WIN[host]["zone"].startswith("ot-") if host in WIN else False


def is_server(host):
    return "Server" in WIN[host]["os"]


def dc_for(host, *k):
    return pick(S.OT_DCS if is_ot(host) else S.DCS, "dc", host, *k)


def acct(username, host):
    """(account name, domain) a person uses on a host: the OT account inside the control network."""
    if is_ot(host) and username in OT_ACCT:
        return OT_ACCT[username], S.OT_DOMAIN
    return username, S.DOMAIN


def gw_domain(account):
    if account == "svc_fieldops_ext":
        return JMP                                    # local account on the gateway (delivered logs spell it GW-SYS-JMP-01\svc_fieldops_ext)
    return S.OT_DOMAIN if (account.startswith("GW-") or account in ("svc_meridian_support", "svc_vantage_mgmt")) else S.DOMAIN


# ---- software ---------------------------------------------------------------------------------------------
MS, MSW = "Microsoft Corporation", "Microsoft Windows"
IMG = {  # key: (path, signer, version)
    "system": ("System", MSW, "10.0"),
    "winlogon": (r"C:\Windows\System32\winlogon.exe", MSW, "10.0"),
    "userinit": (r"C:\Windows\System32\userinit.exe", MSW, "10.0"),
    "services": (r"C:\Windows\System32\services.exe", MSW, "10.0"),
    "lsass": (r"C:\Windows\System32\lsass.exe", MSW, "10.0"),
    "svchost": (r"C:\Windows\System32\svchost.exe", MSW, "10.0"),
    "consent": (r"C:\Windows\System32\consent.exe", MSW, "10.0"),
    "mstsc": (r"C:\Windows\System32\mstsc.exe", MSW, "10.0"),
    "msiexec": (r"C:\Windows\System32\msiexec.exe", MSW, "5.0"),
    "explorer": (r"C:\Windows\explorer.exe", MSW, "10.0"),
    "defender": (r"C:\ProgramData\Microsoft\Windows Defender\Platform\4.18.24090.11-0\MsMpEng.exe", MSW, "4.18"),
    "ccm": (r"C:\Windows\CCM\CcmExec.exe", MS, "5.0"),
    "outlook": (r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE", MS, "16.0"),
    "word": (r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE", MS, "16.0"),
    "excel": (r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE", MS, "16.0"),
    "edge": (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", MS, "139.0"),
    "chrome": (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "Google LLC", "139.0"),
    "firefox": (r"C:\Program Files\Mozilla Firefox\firefox.exe", "Mozilla Corporation", "141.0"),
    "javaw": (r"C:\Program Files\CBPWA\WorkOrders\jre\bin\javaw.exe", "Coastal Bend Power and Water Authority", "17.0"),
    "spoolsv": (r"C:\Windows\System32\spoolsv.exe", MSW, "10.0"),
    "mmc": (r"C:\Windows\System32\mmc.exe", MSW, "10.0"),
    "ssh": (r"C:\Windows\System32\OpenSSH\ssh.exe", MSW, "9.5"),
    "cmd": (r"C:\Windows\System32\cmd.exe", MSW, "10.0"),
    "powershell": (r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", MSW, "10.0"),
    "notepad": (r"C:\Windows\System32\notepad.exe", MSW, "10.0"),
    "taskmgr": (r"C:\Windows\System32\Taskmgr.exe", MSW, "10.0"),
    "calc": (r"C:\Program Files\WindowsApps\Microsoft.WindowsCalculator\CalculatorApp.exe", MS, "11.2"),
    "snip": (r"C:\Windows\System32\SnippingTool.exe", MSW, "10.0"),
    "mspaint": (r"C:\Windows\System32\mspaint.exe", MSW, "10.0"),
    "control": (r"C:\Windows\System32\control.exe", MSW, "10.0"),
    "rundll32": (r"C:\Windows\System32\rundll32.exe", MSW, "10.0"),
    "dllhost": (r"C:\Windows\System32\dllhost.exe", MSW, "10.0"),
    "taskhostw": (r"C:\Windows\System32\taskhostw.exe", MSW, "10.0"),
    "searchidx": (r"C:\Windows\System32\SearchIndexer.exe", MSW, "10.0"),
    "wuauclt": (r"C:\Windows\System32\wuauclt.exe", MSW, "10.0"),
    "trustedinst": (r"C:\Windows\servicing\TrustedInstaller.exe", MSW, "10.0"),
    "teamsync": (r"C:\Program Files\OfficeSuite\Sync\officesync.exe", "OfficeSuite Software Inc", "24.3"),
    "pptview": (r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE", MS, "16.0"),
    "onenote": (r"C:\Program Files\Microsoft Office\root\Office16\ONENOTE.EXE", MS, "16.0"),
    "zipx": (r"C:\Program Files\ArcZip\arczip.exe", "ArcZip Software GmbH", "23.1"),
    "imgview": (r"C:\Program Files\PhotoPane\photopane.exe", "PhotoPane Labs", "6.0"),
    "timecard": (r"C:\Program Files\HRCloud\TimeCard\timecard.exe", "HRCloud Payroll Inc", "5.2"),
    "cisclient": (r"C:\Program Files\CBPWA\CustomerInfo\cis_client.exe", "Coastal Bend Power and Water Authority", "4.1"),
    "omsview": (r"C:\Program Files\CBPWA\OutageView\omsview.exe", "Coastal Bend Power and Water Authority", "3.0"),
    "gridcad": (r"C:\Program Files\GridCAD\gridcad.exe", "GridCAD Software Inc", "2027.1"),
    "labsys": (r"C:\Program Files\LabLedger\labledger.exe", "LabLedger Systems", "8.4"),
    "radioconf": (r"C:\Program Files\FieldRadio\Programmer\frprog.exe", "FieldRadio Corp", "3.3"),
    "mgmtsrv": (r"C:\Program Files\EndpointConfig\Server\ecmsrv.exe", "Endpoint Config Software Inc", "5.0"),
    "sqlsrv": (r"C:\Program Files\DataServer\Engine\dataserver.exe", "DataServer Corp", "16.0"),
    "mailsrv": (r"C:\Program Files\MailServer\Bin\mailstore.exe", "MailServer Software Inc", "15.2"),
    "iisw": (r"C:\Windows\System32\inetsrv\w3wp.exe", MSW, "10.0"),
    "pdfview": (r"C:\Program Files\PDFView\pdfview.exe", "PDFView Software Ltd", "12.4"),
    "meetroom": (r"C:\Program Files\MeetRoom\meetroom.exe", "MeetRoom Video Inc", "5.8"),
    "ledger": (r"C:\Program Files\LedgerFinance\ledger.exe", "Ledger Finance Cloud Inc", "3.8"),
    "geodesk": (r"C:\Program Files\GeoDesk\geodesk.exe", "GeoDesk Mapping LLC", "9.2"),
    "wo_client": (r"C:\Program Files\CBPWA\WorkOrders\wo_client.exe", "Coastal Bend Power and Water Authority", "2.6"),
    "meterexport": (r"C:\Tools\MeterReadExport\MeterReadExport.exe", "", "1.3"),          # in-house, unsigned
    "gisbatch": (r"C:\Tools\GisBatch\gisbatch.exe", "", "0.9"),                            # in-house, unsigned
    "relaycalc": (r"C:\Tools\RelayCalc\relaycalc.exe", "", "2.1"),                         # in-house, unsigned
    "histtrend": (r"C:\Program Files\Meridian Controls\Historian\HistTrend.exe", "Meridian Controls Corp", "8.1"),
    "histsrv": (r"C:\Program Files\Meridian Controls\Historian\histsrv.exe", "Meridian Controls Corp", "8.1"),
    "opconsole": (r"C:\Program Files\Meridian Controls\OpConsole\OpConsole.exe", "Meridian Controls Corp", "4.2"),
    "relayset": (r"C:\Program Files\Meridian Controls\RelaySet\RelaySet.exe", "Meridian Controls Corp", "3.5"),
    "fepdrv": (r"C:\Program Files\Meridian Controls\FrontEnd\fepdrv.exe", "Meridian Controls Corp", "4.2"),
    "scadasrv": (r"C:\Program Files\Meridian Controls\SCADA\scadasrv.exe", "Meridian Controls Corp", "4.2"),
    "bkagent": (r"C:\Program Files\BackupAgent\bkagent.exe", "Backup Agent Software Inc", "9.1"),
    "vscollect": (r"C:\Program Files\Vantage Security\Collector\vscollect.exe", "Vantage Security Systems Inc", "6.2"),
    "epagent": (r"C:\Program Files\EndpointAgent\epagent.exe", "Endpoint Agent Software Inc", "7.3"),
    "invagent": (r"C:\Program Files\AssetInventory\invagent.exe", "Asset Inventory Software Inc", "4.0"),
    "ragw": (r"C:\Program Files\RemoteAccessGateway\ragw.exe", "Remote Access Gateway Software Inc", "2.1"),
}
UNSIGNED_SIZE = {"meterexport": 482_304, "gisbatch": 1_204_736, "relaycalc": 318_976}
# Software behind the periodic single-host series of the network logs (server name -> key). Each is installed on the
# hosts that make those connections; the ones whose series begin inside the span are installed then.
#   key: (path, signer, version, service name or None, runs as a user)
SERIES_SW = {
    "lic-check.gridcad-software.com": ("gclic", r"C:\Program Files\GridCAD\License\gclicsrv.exe", "GridCAD Software Inc", "2027.1", "GridCAD License Service", False),
    "activate.gridcad-software.com": ("gridcad", None, None, None, None, True),
    "sync.cloudstorage-sync.com": ("cloudsync", r"C:\Program Files\CloudSync\cloudsync.exe", "CloudStorage Sync Inc", "7.9", None, True),
    "fleet.printwave-services.net": ("pwfleet", r"C:\Program Files\PrintWave\Fleet\pwfleet.exe", "PrintWave Services Ltd", "4.6", "PrintWave Fleet Agent", False),
    "update-cdn.relaytech-support.net": ("rtupdate", r"C:\Program Files\RelayTech\Updater\rtupdate.exe", "RelayTech Support LLC", "2.2", "RelayTech Update Service", False),
    "telemetry.hrcloud-payroll.com": ("hrconn", r"C:\Program Files\HRCloud\Connector\hrconnector.exe", "HRCloud Payroll Inc", "5.2", "HRCloud Connector", False),
    "api.fleetfuel-cards.com": ("fuelsync", r"C:\Program Files\LedgerFinance\Integrations\fuelcards_sync.exe", "", "1.4", "Fuel Card Sync", False),
    "live-feeds.weatherradar-tiles.com": ("radarfeed", r"C:\ProgramData\OutageView\Feeds\radarfeed.exe", "", "0.8", "Outage Radar Feed Service", False),
    "agent-east.backupvault-cloud.net": ("cloudvault", r"C:\Program Files\BackupAgent\cloudvault.exe", "Backup Agent Software Inc", "9.1", "Backup Cloud Vault", False),
    "updates.browser-safecheck.net": ("scupdate", r"C:\Program Files\SafeCheck\scupdate.exe", "SafeCheck Browser Security", "3.0", "SafeCheck Update Service", False),
    "telemetry.meetroom-video.com": ("mrtelem", r"C:\Program Files\MeetRoom\Rooms\mrrooms.exe", "MeetRoom Video Inc", "5.8", "MeetRoom Rooms Service", False),
    "status.docsign-flow.com": ("dsfstatus", r"C:\ProgramData\DocSignFlow\dsfstatus.exe", "DocSign Flow Inc", "2.5", "DocSign Flow Status Service", False),
    "cdn.partsdepot-supply.com": ("pdcatalog", r"C:\Program Files\PartsDepot\Catalog\pdcatalog.exe", "PartsDepot Supply Co", "11.0", "PartsDepot Catalog Sync", False),
    "push-gw.cellcarrier-account.com": ("ccmgr", r"C:\Program Files\CellCarrier\ConnectionManager\ccmgr.exe", "CellCarrier Wireless", "8.1", None, True),
    "metrics-in.pumpworks-service.com": ("pwmetrics", r"C:\ProgramData\PumpWorks\Monitor\pwmetrics.exe", "", "1.9", "PumpWorks Monitor Service", False),
    "api.packagetracker-api.net": ("pkgtrack", r"C:\ProgramData\PackageTracker\pkgtrack.exe", "", "2.0", "Package Tracker Helper", False),
}
for _n, (_k, _p, _sg, _v, _svc, _usr) in SERIES_SW.items():
    if _p:
        IMG[_k] = (_p, _sg, _v)
        if not _sg:
            UNSIGNED_SIZE[_k] = 200_000 + int(hashlib.sha256(_k.encode()).hexdigest()[:5], 16) % 2_600_000
# the files of the delivered mail / flow records on the shared desk
ZIP_NAME, ZIP_SIZE = "FEMA-PREP-GUIDANCE-2027.zip", 297_271
ATT_NAME, ATT_SIZE = "FEMA-PREP-GUIDANCE-2027.pdf.exe", 301_568
VST_PATH, VST_SIZE, VST_SERVICE = r"C:\ProgramData\VantageTelemetry\vstelemetry.exe", 1_871_360, "Vantage Telemetry Update Service"   # the download that carried it was a little larger


def placeholder_text(name, size):
    """Text of the inert stand-in kept with a triage collection for a file that was copied as a sample.
    Its SHA-256 is the hash every log records for that file."""
    return (f"INERT PLACEHOLDER\nFile name: {name}\nRecorded size: {size} bytes\n"
            "This text file stands in for a binary that was collected as a sample in a fictional training scenario.\n"
            "It contains no executable content. Its SHA-256 is the value the scenario's logs record for the file.\n")


def placeholder_sha(name, size):
    return hashlib.sha256(placeholder_text(name, size).encode("utf-8")).hexdigest()


def sha_of(key):
    """SHA-256 recorded for a software image. Unsigned in-house tools use their placeholder's real hash."""
    path, signer, ver = IMG[key]
    if key in UNSIGNED_SIZE:
        return placeholder_sha(path.rsplit("\\", 1)[1], UNSIGNED_SIZE[key])
    return hashlib.sha256(f"image|{path}|{ver}".encode()).hexdigest()


ATT_SHA, VST_SHA = placeholder_sha(ATT_NAME, ATT_SIZE), placeholder_sha("vstelemetry.exe", VST_SIZE)


def cache_path(username, name):
    """Where the mail client keeps an attachment a person opens."""
    return rf"C:\Users\{username}\AppData\Local\Microsoft\Windows\INetCache\Content.Outlook\{hx('olk', username, n=8).upper()}\{name}"


def unzip_path(username, zip_name, member):
    """Where the shell puts a file that is opened from inside an archive."""
    return rf"C:\Users\{username}\AppData\Local\Temp\Temp1_{zip_name}\{member}"


def att_path(username):
    return unzip_path(username, ZIP_NAME, ATT_NAME)


# ---- programs that run once or rarely --------------------------------------------------------------------
_OO_VENDOR = ["Tidewater", "Brazos", "Laguna", "Padre", "Nueces", "Aransas", "Coastal", "Gulfline", "Baypoint", "Mesquite", "Sabal", "Pelican", "Heron", "Marlin", "Redfish", "Saltgrass"]
_OO_KIND = ["Viewer", "Converter", "Updater", "Setup", "Installer", "Tool", "Utility", "Reader", "Sync", "Capture", "Assistant", "Helper", "Config", "Wizard", "Launcher", "Patch"]
_OO_SIGNER = ["{} Software LLC", "{} Systems Inc", "{} Technologies", "{} Labs", "{} Digital"]


def oneoff(*key):
    """(file name, signer, size, sha256) of a program a person runs once: a downloaded installer, a tool from a vendor,
    something sent as an archive. About half are unsigned; an unsigned one's hash is its placeholder's."""
    v, k = pick(_OO_VENDOR, "oov", *key), pick(_OO_KIND, "ook", *key)
    name = f"{v}{k}{'_' + str(1 + hint(9, 'oon', *key)) + '.' + str(hint(40, 'oom', *key)) if h01('oover', *key) < 0.6 else ''}{'_x64' if h01('oox', *key) < 0.3 else ''}.exe"
    size = 180_000 + hint(48_000_000, "oos", *key)
    if h01("oosg", *key) < 0.48:
        return name, "", size, placeholder_sha(name, size)
    return name, pick(_OO_SIGNER, "oosn", *key).format(v), size, hashlib.sha256(f"oneoff|{name}|{size}".encode()).hexdigest()


def local_tools(host):
    """Two to four unsigned in-house or vendor utilities kept on a host: [(path, size, sha256)]."""
    out = []
    dirs = [r"C:\Tools", r"C:\Tools\bin", r"C:\Utilities", r"C:\Program Files\CBPWA\Scripts", r"C:\Support"]
    names = ["logrotate_helper", "cfgdiff", "exportcsv", "tagcheck", "pingsweep_report", "meterbatch", "relaydiff", "drvcheck", "backupverify", "printfix",
             "timesync_check", "histexport", "wiring_report", "gisclip", "alarmlist_export", "serialterm", "firmware_stage", "rtu_snapshot"]
    for i in range(2 + hint(3, "ltn", host)):
        nm = pick(names, "ltname", host, i) + ".exe"
        if any(o[0].endswith("\\" + nm) for o in out):
            continue
        size = 60_000 + hint(2_400_000, "ltsize", host, i)
        out.append((pick(dirs, "ltdir", host, i) + "\\" + nm, size, placeholder_sha(nm, size)))
    return out


# ---- removable storage: devices belong to people ----------------------------------------------------------
_USB = [("Tidewater Storage", "Traveler 64GB"), ("Sandmark", "Slimfit 32GB"), ("Verbit", "GoStore 16GB"), ("Coastal Data", "Field Drive 128GB"), ("Sandmark", "Xtra 256GB"),
        ("Kingsbay", "DataRunner 32GB"), ("Verbit", "Pocket SSD 500GB"), ("Coastal Data", "Rugged Key 64GB")]


def usb_device(owner, *key):
    """(vendor, model, serial) of one of the one to three removable drives a person (or a shared machine) owns."""
    k = hint(1 + hint(3, "usbn", owner), "usbk", owner, *key)
    v, m_ = pick(_USB, "usbm", owner, k)
    return v, m_, hx("usbs", owner, k, n=12).upper()


# ---- delivered logs (light readers) -----------------------------------------------------------------------
def _zeek(d, name, cols):
    p = os.path.join(NETDIR, "zeek", S.day_str(d), name + ".log")
    out = []
    if not os.path.exists(p):
        return out
    idx = None
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if line[0] == "#":
                if line.startswith("#fields"):
                    f = line.rstrip("\n").split("\t")[1:]
                    idx = [f.index(c) for c in cols]
                continue
            v = line.rstrip("\n").split("\t")
            out.append([v[i] for i in idx])
    return out


@functools.lru_cache(maxsize=70)
def conn_day(d):
    """Delivered conn rows of UTC day d:
    (ts, orig, orig_port, resp, resp_port, service, duration, orig_bytes, resp_bytes, state, proto, uid)."""
    return [(float(r[0]), r[1], int(r[2]), r[3], int(r[4]), r[5], float(r[6]) if r[6] != "-" else 0.0, int(r[7]) if r[7] != "-" else 0,
             int(r[8]) if r[8] != "-" else 0, r[9], r[10], r[11])
            for r in _zeek(d, "conn", ["ts", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "service", "duration", "orig_bytes", "resp_bytes", "conn_state", "proto", "uid"])]


@functools.lru_cache(maxsize=70)
def names_day(d):
    """uid -> server name (ssl.log) or 'ua:' + user agent (http.log) for UTC day d."""
    out = {}
    for u, n in _zeek(d, "ssl", ["uid", "server_name"]):
        out[u] = n
    for u, a in _zeek(d, "http", ["uid", "user_agent"]):
        out[u] = "ua:" + a
    return out


@functools.lru_cache(maxsize=70)
def dns_day(d):
    """Delivered dns rows of UTC day d: (ts, orig, resp, query, answers, rcode)."""
    return [(float(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in _zeek(d, "dns", ["ts", "id.orig_h", "id.resp_h", "query", "answers", "rcode_name"])]


@functools.lru_cache(maxsize=None)
def _alert_file(mon):
    p = os.path.join(NETDIR, "siem", f"siem_alerts_{mon}.csv")
    out = []
    if os.path.exists(p):
        with open(p, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                out.append((ts(r["time_utc"]), r["rule_name"], r["src_host"], r["src_ip"], r["dst_host"], r["user"], r["detail"], r["alert_id"]))
    return out


def _months_between(a, b):
    d = dt.datetime.fromtimestamp(a, UTC).replace(day=1, hour=0, minute=0, second=0)
    out = []
    while d.timestamp() < b:
        out.append(d.strftime("%Y-%m"))
        d = (d + dt.timedelta(days=32)).replace(day=1)
    return out


def alerts_between(a, b, rules=None):
    """Delivered alerts with a <= time < b: (t, rule_name, src_host, src_ip, dst_host, user, detail, alert_id)."""
    out = []
    for mon in _months_between(a, b):
        for r in _alert_file(mon):
            if a <= r[0] < b and (rules is None or r[1] in rules):
                out.append(r)
    return out


ALERT_PAD = {"FAILED_LOGON_BURST": (310, 5), "ACCOUNT_LOCKOUT": (1500, 5), "LOGON_OUTSIDE_HOURS": (5, 5500), "ADMIN_GROUP_CHANGE": (5, 5),
             "PUP_DETECTED": (10, 5), "USB_STORAGE_MOUNTED": (5, 5), "OT_FILE_WRITE": (5, 45)}      # seconds of host-side evidence around an alert
EVIDENCE_RULES = ("FAILED_LOGON_BURST", "ACCOUNT_LOCKOUT", "LOGON_OUTSIDE_HOURS", "ADMIN_GROUP_CHANGE", "PUP_DETECTED", "USB_STORAGE_MOUNTED", "OT_FILE_WRITE")


@functools.lru_cache(maxsize=None)
def audit(name):
    return S.audit(name)


@functools.lru_cache(maxsize=None)
def gw_sessions():
    """Delivered remote-access gateway sessions, sorted by login: dicts with a, b (epoch), account, src_ip, targets, sid."""
    out = []
    for r in audit("remote_access_sessions"):
        out.append({"a": ts(r["login_utc"]), "b": ts(r["logout_utc"]), "account": r["account"], "src_ip": r["src_ip"],
                    "targets": set(r["target_hosts"].split(";")), "sid": r["session_id"]})
    out.sort(key=lambda s: s["a"])
    return out


def gw_session(t, target=None):
    """The gateway session that was open at time t (preferring one that lists the target host), or None."""
    ss = gw_sessions()
    i = bisect.bisect_right([s["a"] for s in ss], t + 20)
    best = None
    for s in ss[max(0, i - 40):i]:
        if s["a"] - 20 <= t <= s["b"] + 20:
            if target and target in s["targets"]:
                return s
            best = best or s
    return best


# ---- people -----------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=400)
def sessions(d):
    """Ordinary interactive sessions that start on local day d, on Windows hosts (from the shared model)."""
    if d < FIRST_LDAY or d > LAST_LDAY:
        return []
    out = []
    for s in S.interactive_sessions(d):
        if s["host"] not in WIN:
            continue
        if s["host"] == JMP and s["logon"] < M.T["reconnect"] and s["logoff"] > M.T["isolate"]:
            continue                                  # the gateway is powered off in this window (canon); nobody can be logged on to it
        out.append(s)
    return out


@functools.lru_cache(maxsize=400)
def _sess_by_host(d):
    by = {}
    for s in sessions(d):
        by.setdefault(s["host"], []).append(s)
    return by


def session_at(host, t):
    """The ordinary interactive session open on a host at time t (the first one if several), or None."""
    for d in (G.day_utc(t) - 1, G.day_utc(t)):
        for s in _sess_by_host(d).get(host, []):
            if s["logon"] <= t < s["logoff"]:
                return s
    return None


def session_overlap(host, a, b):
    for d in range(G.day_utc(a) - 1, G.day_utc(b) + 1):
        for s in _sess_by_host(d).get(host, []):
            if s["logon"] < b and a < s["logoff"]:
                return True
    return False


# ---- power ------------------------------------------------------------------------------------------------
@functools.lru_cache(maxsize=90)
def _activity(d):
    """Intervals of delivered activity per registry host on UTC day d (flows as originator or responder, DNS
    lookups, alerts with host-side evidence, endpoint-protection and file-integrity records)."""
    by = {}
    for r in conn_day(d):
        rdp = r[4] == 3389                              # a remote-desktop flow is framed by a logon and logoff on both ends
        for ip in (r[1], r[3]):
            h = WIN_IP.get(ip)
            if h:
                by.setdefault(h, []).append((r[0] - (100 if rdp else 2), r[0] + r[6] + (600 if rdp else 2)))
    for r in dns_day(d):
        h = WIN_IP.get(r[1])
        if h:
            by.setdefault(h, []).append((r[0] - 1, r[0] + 1))
    a0 = D0_EPOCH + d * DAY
    for r in alerts_between(a0 - 6000, a0 + DAY + 2000, EVIDENCE_RULES):
        before, after = ALERT_PAD[r[1]]
        for h in ((r[2], r[4]) if r[1] == "OT_FILE_WRITE" else (r[2],)):
            if h in WIN:
                by.setdefault(h, []).append((r[0] - before, r[0] + after))
        if r[1] in ("ACCOUNT_LOCKOUT", "ADMIN_GROUP_CHANGE"):
            for h in S.DCS:
                by.setdefault(h, []).append((r[0] - 5, r[0] + 5))
    for name, col in (("endpoint_protection", "host"), ("file_integrity", "host")):
        for r in audit(name):
            t = ts(r["time_utc"])
            if a0 - 60 <= t < a0 + DAY + 60 and r[col] in WIN:
                by.setdefault(r[col], []).append((t - 30, t + 60))
    return by


def busy(host, a, b):
    """Merged intervals between a and b in which the delivered logs or the shared session model need the host."""
    iv = []
    for d in range(G.day_utc(a) - 1, G.day_utc(b) + 1):
        for x, y in _activity(d).get(host, []):
            if x < b and a < y:
                iv.append((x, y))
        for s in _sess_by_host(d).get(host, []):
            if s["logon"] - 30 < b and a < s["logoff"] + 30:
                iv.append((s["logon"] - 30, s["logoff"] + 30))
        if host in S.DCS or host in S.OT_DCS:           # the DCs issue tickets at every interactive logon
            for s in sessions(d):
                if a - 5 < s["logon"] < b + 5 and dc_for(s["host"], s["user"], s["logon"]) == host:
                    iv.append((s["logon"] - 5, s["logon"] + 5))
    if host == JMP:
        for s in gw_sessions():
            if s["a"] - 60 < b and a < s["b"] + 60:
                iv.append((s["a"] - 60, s["b"] + 60))
    iv.sort()
    out = []
    for x, y in iv:
        if out and x <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], y))
        else:
            out.append((x, y))
    return out


def free(host, a, b):
    """True if nothing in the delivered logs or the shared session model needs the host between a and b."""
    return not busy(host, a, b)


def _nth_weekday(year, month, weekday, n):
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    return d


def _lday(date):
    return (date - dt.date(2027, 9, 14)).days


STORM_OFF = (M.T["sub1_trip"], M.T["sub1_trip"] + 12 * 3600)      # building circuits not on the generator


@functools.lru_cache(maxsize=None)
def boots(host):
    """[(down, up, planned)] for a Windows host over the span. Patch reboots at night, one unplanned loss of power
    for workstations on circuits without generator backing, and the gateway's shutdown while the control network
    is cut off. Windows are placed where the delivered logs show the host idle."""
    h = WIN[host]
    out, slots = [], []
    ws = h["device_type"] in ("workstation", "laptop")
    if is_ot(host):
        for y, m_, dd in ((2027, 8, 18), (2027, 11, 17)):
            slots.append((_lday(dt.date(y, m_, dd)) + hint(2, "otp", host), 3.0, 1.5))
    else:
        for y, m_ in ((2027, 7), (2027, 8), (2027, 9), (2027, 10), (2027, 11), (2027, 12), (2028, 1)):
            base = _nth_weekday(y, m_, 1, 2) if ws else _nth_weekday(y, m_, 6, 3)      # 2nd Tuesday / 3rd Sunday
            d = _lday(base) + (1 + hint(3, "pd", host, m_) if ws else 0)
            if -3 <= d <= 8:
                d += 14                                                                  # patching postponed around the storm
            slots.append((d, 2.0 if ws else 1.0, 2.5 if ws else 3.5))
    for d, h0, width in slots:
        if d < FIRST_LDAY or d > LAST_LDAY - 1:
            continue
        dur = 150 + hint(270, "bd", host, d) + (180 if not ws else 0)
        base = local_ts(d, "00:00") + int(h0 * 3600) + hint(int(width * 3600), "bt", host, d)
        for k in range(420):
            a = base + k * 300
            if free(host, a - 120, a + dur + 120):
                out.append((a, a + dur, True))
                break
    windows = []
    if ws and not is_ot(host) and (host == WS04 or h01("storm_off", host) < 0.75):
        windows.append((STORM_OFF[0] + 15, STORM_OFF[1] + 1500, 2700, False))     # after the feeder trip
    if host == JMP:
        windows.append((M.T["isolate"] + 420, M.T["reconnect"] - 900, 6 * 3600, True))   # powered off while the control network is cut off
    if host == WS04:
        out.append((G.WS04_REMOVED, 4e9, False))            # unplugged when the network is cut; it never returns
    for a0, b0, least, planned in windows:
        # the longest stretch of the window in which the delivered logs show nothing from this machine
        edges, best = [a0] + [v for iv in busy(host, a0, b0) for v in iv] + [b0], None
        for i in range(0, len(edges), 2):
            x, y = max(edges[i], a0), min(edges[i + 1], b0)
            if y - x >= least and (best is None or y - x > best[1] - best[0]):
                best = (x, y)
        if best:
            out.append((best[0] + 20 + hint(120, "so", host), best[1] - 60 - hint(140, "so2", host), planned))
    return sorted(out)


def is_up(host, t):
    for a, b, _ in boots(host):
        if a <= t < b:
            return False
    return True


def last_boot(host, t):
    lb = T0 + hint(5 * DAY, "inst", host)
    for a, b, _ in boots(host):
        if b <= t:
            lb = b
    return lb


def pid(host, *key):
    return 4 * (hint(15000, "pid", host, *key) + 150)


def sys_pid(host, image, t):
    return 4 if image == "system" else pid(host, image, last_boot(host, t))
