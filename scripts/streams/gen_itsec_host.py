"""Raw host logs of the utility: Windows event logs, endpoint telemetry and host triage collections.

    python3 scripts/streams/gen_itsec_host.py windows 2027-09      one month of Windows event logs
    python3 scripts/streams/gen_itsec_host.py endpoint 2027-09     one month of endpoint telemetry
    python3 scripts/streams/gen_itsec_host.py month 2027-09        both for one month (one build)
    python3 scripts/streams/gen_itsec_host.py triage               triage collections (reads the two streams from disk)
    python3 scripts/streams/gen_itsec_host.py --all [--resume] [--budget=110]
                                                                  every month then triage; with --resume it continues
                                                                  where the last call stopped (exit code 3 = more to do)

Run after gen_itsec.py: every record here is derived from the delivered SIEM alerts, Zeek logs and audit tables
and from the shared presence model (itsec_shared), so the host logs describe the same activity as those logs.
Observation only: what an event log or an endpoint agent would have recorded. The model is in itsec_host_model.py.
"""
import bisect
import csv
import datetime as dt
import functools
import glob
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itsec_shared as S
import itsec_host_model as Mo
from common import D0_EPOCH, ROOT, UTC, local_ts, ts
import itsec_zeek_extra as ZX
from itsec_host_model import (ADMINS, ATT_NAME, ATT_SHA, ATT_SIZE, DAY, HIST1, HISTDMZ, IMG, IP, JMP, OPS02, OT01, OT_ACCT, SCADA1, SERIES_SW, VST_PATH,
                              VST_SERVICE, VST_SHA, VST_SIZE, WIN, WIN_IP, WS04, ZIP_NAME, ZIP_SIZE, acct, dc_for, gw_domain, h01, hint, hx, is_ot, is_server,
                              iso_ms, pick, pid, sha_of)

G, M = S.G, S.M
NET = S.NET
WIN_DIR, EDR_DIR, TRI_DIR = f"{NET}/windows", f"{NET}/endpoint", f"{NET}/triage"
CH = {"security": ("Security", 2.5), "system": ("System", 0.05), "defender": ("Microsoft-Windows-Windows Defender/Operational", 0.02)}
SEC_PROV = "Microsoft-Windows-Security-Auditing"
SYS_PROV = {6005: "EventLog", 6006: "EventLog", 6008: "EventLog", 1074: "User32", 7036: "Service Control Manager", 7045: "Service Control Manager"}
SPAN_T0 = Mo.SPAN_A
MAILSRV = {IP["GW-SRV-MAIL-01"], IP["GW-SRV-MAIL-02"]}
BEACON_IP = G.BEACON_IP
ZIP_T0 = G.AV_OFF_T - 41.6            # the archive is written to the mail cache when the person opens it
ATT_T0 = G.AV_OFF_T - 19.7            # the shell extracts the file the person double-clicks
ATT_RUN = G.AV_OFF_T - 16.9           # and starts it


@functools.lru_cache(maxsize=None)
def story_flows():
    """The delivered flows that fix the workstation's records: the download that follows the lookup at G.DNS_Q_T
    and the transfer from the historian replica on 2027-09-08. Read from the sensor log, never assumed."""
    dl = h2 = None
    for r in Mo.conn_day(G.day_utc(G.DNS_Q_T)):
        if r[1] == IP[WS04] and r[3] == G.BEACON_IP and abs(r[0] - G.DNS_Q_T) < 30 and (dl is None or r[8] > dl[8]):
            dl = r
    t2 = ts("2027-09-08T23:58Z")
    for d in (G.day_utc(t2), G.day_utc(t2) + 1):
        for r in Mo.conn_day(d):
            if r[1] == IP[WS04] and r[3] == IP[HISTDMZ] and r[4] == 445 and abs(r[0] - t2) < 3600 and (h2 is None or r[8] > h2[8]):
                h2 = r
    return dl, h2


def vst_times():
    dl = story_flows()[0]
    done = dl[0] + dl[6]
    return done + 2.57, done + 17.07, done + 18.07         # file written, service registered, service started


VST_WRITE, VST_SVC, VST_START = vst_times()
# Workstation lock and unlock events are forwarded only from the control network and the administration wing
# (None = forward them from every host; about 36 MB more).
LOCK_ZONES = ("ot-", "corp-users-admin")
TRIAGE = [  # (host, collection time)
    (JMP, ts("2027-10-02T21:22:43Z")), (HIST1, ts("2027-10-02T21:41:08Z")), (WS04, ts("2027-10-12T15:47:07Z")),
    (OPS02, ts("2027-10-13T14:12:28Z")), (SCADA1, ts("2027-10-13T15:03:11Z")), (OT01, ts("2027-10-13T16:20:47Z")),
    ("GW-WS-IT-33", ts("2027-10-13T18:41:03Z")), (HISTDMZ, ts("2027-10-13T19:30:19Z")), ("GW-WS-ENG-03", ts("2027-10-13T20:44:17Z")),
    ("GW-SRV-FILE-01", ts("2027-10-14T13:25:41Z")), ("GW-WS-IT-69", ts("2027-10-14T14:38:06Z")), ("GW-WS-OPS-04", ts("2027-10-14T15:50:32Z")),
    ("GW-WS-IT-12", ts("2027-10-14T17:02:13Z")), ("GW-WS-IT-118", ts("2027-10-14T18:15:44Z"))]
BROWSE_KEEP = 0.5     # share of a person's ordinary web browsing (connections and lookups) that the agent's records keep; see the guide


def path(key):
    return IMG[key][0]


def signer(key):
    return IMG[key][1]


# ---- event constructors -----------------------------------------------------------------------------------
def frac(t, *k):
    """Whole-second source times get a stable sub-second part, as a host clock would have recorded."""
    return t + h01("ms", *k) * 0.97 if t == int(t) else t + h01("us", *k) * 0.009


def w(W, t, host, ch, eid, **f):
    W.append((frac(t, host, eid, t), host, ch, eid, f))


def e(E, t, host, etype, user, pid_, image, **f):
    E.append((frac(t, host, etype, t, pid_), host, etype, user, pid_, image, f))


def img_sha(host, key, t):
    """Hash of a software image on a host at time t: the file of the latest package deployed there, else the base image."""
    best = None
    for td, pkg, k, svc, extra in deploy_events(host):
        if k == key and td + 3 <= t and svc != "Print Driver Host":
            best = pkg
    return hashlib.sha256(f"pkg|{best}|{path(key)}".encode()).hexdigest() if best else sha_of(key)


def proc(E, t, host, key, user, pid_, ppid, parent, cmd=None, image=None, sha=None, sign=None):
    img = image or path(key)
    e(E, t, host, "process_start", user, pid_, img, ppid=ppid, parent_image=parent, command_line=cmd or f'"{img}"',
      sha256=sha or img_sha(host, key, t), signer=IMG[key][1] if sign is None else sign)


def lid(host, user, t, *salt):
    """Logon id: unique per logon (time to the millisecond plus whatever tells two logons of one second apart)."""
    return "0x" + hx("lid", host, user, int(round(t * 1000)), *salt, n=10).lstrip("0")      # 40 bits: no two logons on a host share an id


# ---- sessions ---------------------------------------------------------------------------------------------
DEPT_APPS = {"Finance and Procurement": ["excel", "ledger", "word", "timecard"], "Customer Service": ["cisclient", "wo_client", "excel", "meterexport"],
             "Field Services": ["wo_client", "meterexport", "pdfview", "radioconf"], "GIS and Planning": ["geodesk", "gridcad", "gisbatch", "excel"],
             "Protection and Control": ["relaycalc", "excel", "pdfview", "gridcad"], "Transmission and Distribution Engineering": ["relaycalc", "geodesk", "gridcad", "excel"],
             "Human Resources": ["timecard", "word", "excel"], "Water Quality": ["labsys", "excel", "pdfview"], "System Operations": ["omsview", "excel", "pdfview"],
             "Communications": ["word", "pptview", "imgview"], "Executive Office": ["word", "pptview", "excel", "onenote"]}
DEFAULT_APPS = ["word", "excel", "pdfview", "meetroom", "onenote", "pptview"]
BUILTIN = ["notepad", "calc", "snip", "taskmgr", "mspaint", "control", "cmd", "notepad", "snip", "calc"]
BUILTIN_IT = BUILTIN + ["powershell", "mmc", "cmd", "powershell", "mmc"]
_started = set()
_oneoffs = {}


def corp_desktop(host):
    return not is_ot(host) and not is_server(host)


def browser_key(u):
    r = h01("brw", u)
    return "edge" if r < 0.55 else ("chrome" if r < 0.9 else "firefox")


def ua_browser(ua):
    return "edge" if "Edg/" in ua else ("firefox" if "Firefox/" in ua else "chrome")


def sess_proc(s, key):
    """(start time, pid, image key) of a program that starts with a person's session (shell, mail client, their browser)."""
    if key == "browser":
        key = browser_key(s["user"])
    off = {"explorer": 2.6, "outlook": 20 + hint(50, "ol", s["host"], s["logon"])}.get(key, 45 + hint(60, "ed", s["host"], s["logon"]))
    return s["logon"] + off, pid(s["host"], key, s["user"], s["logon"]), key


def once(E, so, key, t):
    """(user, pid, image) of a program a logged-on person keeps open for the session; its start is added the first time it is needed."""
    host, u = so["host"], so["user"]
    user = acct(u, host)[0]
    if key in ("explorer", "outlook", browser_key(u)) and corp_desktop(host):
        ts_, p, k = sess_proc(so, key if key != browser_key(u) else "browser")
        if t > ts_ + 0.5 or key == "explorer":
            return user, p, path(key)
    p = pid(host, key, u, so["logon"], "once")
    if (host, p, so["logon"]) not in _started:
        _started.add((host, p, so["logon"]))
        tp = max(so["logon"] + 8 + hint(40, "once", host, p), t - 3 - hint(240, "once2", host, p))
        proc(E, min(tp, t - 0.3), host, key, user, p, sess_proc(so, "explorer")[1], path("explorer"))
    return user, p, path(key)


def run_oneoff(W, E, s, t, key, via):
    """A program a person runs once: downloaded with the browser or opened from an archive that came by mail."""
    host, u = s["host"], s["user"]
    user = acct(u, host)[0]
    name, sign, size, sha = Mo.oneoff(host, u, int(t), key)
    p_ex = sess_proc(s, "explorer")[1]
    if via == "download":
        tb, pb, kb = sess_proc(s, "browser")
        fp = f"C:\\Users\\{u}\\Downloads\\{name}"
        e(E, t, host, "file_create", user, pb, path(kb), path=fp, size=size, sha256=sha)
        t += 6 + hint(240, "oo_wait", host, int(t))
    else:                                               # via = the archive it was opened from
        fp = Mo.unzip_path(u, via, name)
        e(E, t, host, "file_create", user, p_ex, path("explorer"), path=fp, size=size, sha256=sha)
        t += 1.5 + h01("oo_w2", host, int(t)) * 3
    if t < s["logoff"] - 20:
        p1 = pid(host, "oneoff", u, int(t))
        e(E, t, host, "process_start", user, p1, fp, ppid=p_ex, parent_image=path("explorer"), command_line=f'"{fp}"', sha256=sha, signer=sign)
        _oneoffs.setdefault(host, []).append((t, s["logoff"], user, p1, fp))
        if any(x in name for x in ("Setup", "Installer", "Updater", "Patch", "Assistant")) and h01("oosvc", host, int(t)) < 0.45 and t < s["logoff"] - 200:
            # the program installs a helper that runs as a service
            vend = name[:next(i for i, ch in enumerate(name) if i and ch.isupper())]
            sname = f"{vend} {pick(['Update', 'Helper', 'Sync', 'License', 'Monitor', 'Telemetry Update', 'Remote Support', 'License Manager', 'Auto Update', 'Device Sync'], 'oosn2', name)} Service"
            sexe = vend.lower() + pick(["svc", "svc", "agent", "update", "helper", "telemetry", "sync", "d"], "ooexe", name) + ".exe"
            simg = (f"C:\\ProgramData\\{vend}\\{sexe}" if h01("oopd", name) < 0.5 else f"C:\\Program Files\\{vend}\\{sexe}")
            ssize = 150_000 + hint(3_000_000, "oosz", name)
            ssha = Mo.placeholder_sha(simg.rsplit("\\", 1)[1], ssize) if not sign else hashlib.sha256(f"oosvc|{simg}|{ssize}".encode()).hexdigest()
            t1 = t + 20 + hint(70, "oos1", host, int(t))
            e(E, t1, host, "file_create", user, p1, fp, path=simg, size=ssize, sha256=ssha)
            w(W, t1 + 12.5, host, "system", 7045, service_name=sname, image_path=simg, service_type="user mode service", start_type="auto start", account="LocalSystem")
            e(E, t1 + 12.5, host, "service_install", user, p1, fp, service_name=sname, service_image=simg, start_type="auto start")
            w(W, t1 + 13.4, host, "system", 7036, service_name=sname, state="running")
            e(E, t1 + 13.5, host, "process_start", "SYSTEM", pid(host, "oosvc", int(t1)), simg, ppid=sys_pid(host, "services", t1), parent_image=path("services"),
              command_line=f'"{simg}"', sha256=ssha, signer=sign)


def b_sessions(W, E, lo, hi):
    for d in range(G.day_utc(lo) - 2, G.day_utc(hi) + 2):
        for s in Mo.sessions(d):
            a, b = s["logon"], s["logoff"]
            if b < lo - 10 or a > hi + 10:
                continue
            host, u = s["host"], s["user"]
            user, dom = acct(u, host)
            L = lid(host, u, a)
            lap = WIN[host]["device_type"] == "laptop"
            w(W, a, host, "security", 4624, user=user, domain=dom, logon_type=11 if (lap and h01("lt", host, a) < 0.25) else 2, logon_id=L)
            if u in ADMINS or (is_ot(host) and u in OT_ACCT):
                w(W, a + 0.985, host, "security", 4672, user=user, domain=dom, logon_id=L, privileges="SeSecurityPrivilege;SeBackupPrivilege;SeDebugPrivilege")
            dc = dc_for(host, u, a)
            w(W, a - 1.4, dc, "security", 4768, user=user, domain=dom, src_ip=IP[host], service="krbtgt", status="0x0")
            w(W, a - 0.7, dc, "security", 4769, user=user, domain=dom, src_ip=IP[host], service=host.lower() + "$", status="0x0")
            if LOCK_ZONES is None or WIN[host]["zone"].startswith(LOCK_ZONES):
                for lk, ul in s["lock_unlock"]:
                    w(W, lk, host, "security", 4800, user=user, domain=dom, logon_id=L)
                    w(W, ul, host, "security", 4801, user=user, domain=dom, logon_id=L)
            w(W, b, host, "security", 4647, user=user, domain=dom, logon_id=L)
            w(W, b + 1.1, host, "security", 4634, user=user, domain=dom, logon_type=2, logon_id=L)
            # processes of the session
            t_ex, p_ex, _ = sess_proc(s, "explorer")
            proc(E, t_ex, host, "explorer", user, p_ex, pid(host, "userinit", u, a), path("userinit"))
            if not corp_desktop(host):
                if is_ot(host) and h01("otapp", host, a) < 0.5:
                    k = "relayset" if "ENG" in host else "histtrend"
                    t = a + 240 + h01("otapp_t", host, a) * max(600, b - a - 900)
                    proc(E, t, host, k, user, pid(host, k, u, int(t)), p_ex, path("explorer"))
                continue
            for k in ("outlook", "browser"):
                t, p, kk = sess_proc(s, k)
                proc(E, t, host, kk, user, p, p_ex, path("explorer"))
            dept = S.USER_BY_NAME[u]["department"]
            apps = DEPT_APPS.get(dept, DEFAULT_APPS)
            for i in range(hint(4, "napp", host, a)):
                k = pick(apps, "app", host, a, i)
                if k in ("meterexport", "gisbatch", "relaycalc") and h01("inhouse", host, a, i) > 0.45:
                    k = "excel"
                t = a + 400 + h01("app_t", host, a, i) * max(600, b - a - 900)
                cmd = None
                if k in ("word", "excel", "pptview"):
                    ext = {"word": "docx", "excel": "xlsx", "pptview": "pptx"}[k]
                    cmd = f'"{path(k)}" "C:\\Users\\{u}\\Documents\\{hx("doc", u, int(t), n=8)}.{ext}"'
                proc(E, t, host, k, user, pid(host, k, u, int(t)), p_ex, path("explorer"), cmd=cmd)
            if h01("bi", host, a) < 0.42:                                   # a Windows accessory or an administration console
                k = pick(BUILTIN_IT if dept in Mo.ADMIN_DEPTS else BUILTIN, "bik", host, a)
                t = a + 300 + h01("bi_t", host, a) * max(600, b - a - 900)
                proc(E, t, host, k, user, pid(host, k, u, int(t)), p_ex, path("explorer"))
            if h01("lt_run", host, a) < 0.06:                               # one of the machine's own utilities
                fp, size, sha = pick(Mo.local_tools(host), "lt_pick", host, a)
                t = a + 500 + h01("lt_t", host, a) * max(600, b - a - 1200)
                e(E, t, host, "process_start", user, pid(host, "lt", u, int(t)), fp, ppid=p_ex, parent_image=path("explorer"), command_line=f'"{fp}"', sha256=sha, signer="")
            if h01("dl", host, a) < 0.22:
                t_ed, p_ed, kb = sess_proc(s, "browser")
                t = t_ed + 300 + h01("dl_t", host, a) * max(600, b - t_ed - 900)
                ext = pick(["pdf", "xlsx", "zip", "docx", "csv", "pdf"], "dl_e", host, a)
                e(E, t, host, "file_create", user, p_ed, path(kb), path=f"C:\\Users\\{u}\\Downloads\\{hx('dlf', host, a, n=10)}.{ext}",
                  size=20_000 + hint(4_000_000, "dl_s", host, a), sha256=hashlib.sha256(f"dl|{host}|{a}".encode()).hexdigest())
            if h01("big", host, a) < 0.012:                                 # now and then something large: a recording, a disk image, an export, a drawing set
                t_ed, p_ed, kb = sess_proc(s, "browser")
                t = t_ed + 400 + h01("big_t", host, a) * max(600, b - t_ed - 1200)
                nm, ext = pick([("Recording", "mp4"), ("installer", "iso"), ("export", "bak"), ("drawings", "zip"), ("gis_export", "gdb.zip"), ("training", "mp4"), ("backup", "pst")], "big_k", host, a)
                e(E, t, host, "file_create", user, p_ed if ext in ("mp4", "iso", "zip") else p_ex, path(kb) if ext in ("mp4", "iso", "zip") else path("explorer"),
                  path=f"C:\\Users\\{u}\\{'Downloads' if ext in ('mp4', 'iso', 'zip') else 'Documents'}\\{nm}_{hx('bigf', host, a, n=6)}.{ext}",
                  size=int(60_000_000 * (1 + 30 * h01("big_s", host, a) ** 2.2)), sha256=hashlib.sha256(f"big|{host}|{a}".encode()).hexdigest())
            if h01("oo", host, a) < 0.045:                                  # a downloaded installer or tool, run once
                t_ed = sess_proc(s, "browser")[0]
                run_oneoff(W, E, s, t_ed + 200 + h01("oo_t", host, a) * max(600, b - t_ed - 1500), "dl", "download")


# ---- boots ------------------------------------------------------------------------------------------------
APP_SRV = ("INTRA", "ERP", "CIS", "OMS", "GIS", "WAM", "HR", "PORTAL", "WEB", "VDI", "IVR", "MFT")


@functools.lru_cache(maxsize=None)
def series_sw(host):
    """Software behind a periodic series on this host: {server name: (key, install time or None, runs as a user)}.
    A series that begins inside the span has its software installed the working day before."""
    out = {}
    for name, hosts, period, jitter, first_d, last_d, need_user in ZX.SERIES:
        if host not in hosts or host not in WIN:
            continue
        key, _p, _sg, _v, svc, usr = SERIES_SW[name]
        t_inst = None
        if first_d > S.FIRST_DAY and not usr:
            t_inst = local_ts(first_d - 1, "13:00") + hint(3 * 3600, "sinst", host, name)
            for _ in range(60):
                if Mo.is_up(host, t_inst - 30) and Mo.is_up(host, t_inst + 60):
                    break
                t_inst -= 900
        out[name] = (key, t_inst, usr)
    return out


@functools.lru_cache(maxsize=None)
def system_images(host):
    """Image keys of the programs that run as the system on a host from boot (in start order)."""
    out = ["services", "lsass", "svchost", "defender", "vscollect", "epagent", "invagent"]
    srv, ot = is_server(host), is_ot(host)
    if not ot:
        out.append("ccm")
    if not srv or "PRINT" in host:
        out.append("spoolsv")
    if not srv and not ot:
        out.append("javaw")
    if srv and not ot:
        out.append("bkagent")
    if "OPS" in host or "HMI" in host or "BCC" in host:
        out.append("opconsole")
    if "HIST" in host:
        out.append("histsrv")
    if "FEP" in host:
        out.append("fepdrv")
    if "SCADA" in host:
        out.append("scadasrv")
    if host == JMP:
        out.append("ragw")
    if "MAIL" in host:
        out.append("mailsrv")
    if "SQL" in host:
        out.append("sqlsrv")
    if "ECM" in host:
        out.append("mgmtsrv")
    if srv and any(x in host for x in APP_SRV):
        out.append("iisw")
    for name, (key, t_inst, usr) in series_sw(host).items():
        if not usr:
            out.append(key)
    return out


@functools.lru_cache(maxsize=None)
def _installed_at(host, key):
    for name, (k, t_inst, usr) in series_sw(host).items():
        if k == key:
            return t_inst
    return None


def sysimg(host, key, t):
    """(pid, image) of a system program on a host at time t; the generic service host if the host does not run it (yet)."""
    if key == "system":
        return 4, "System"
    if key not in system_images(host):
        key = "svchost"
    ti = _installed_at(host, key)
    if ti is not None and t < ti + 10:
        key, ti = "svchost", None
    start = Mo.last_boot(host, t)
    if ti is not None and ti + 10 > start:
        start = ti
    return pid(host, key, start), path(key)


def sys_pid(host, key, t):
    return sysimg(host, key, t)[0]


def b_boots(W, E, lo, hi):
    for host in WIN:
        for a, b, planned in Mo.boots(host):
            if b < lo - 120 or a > hi + 120:
                continue
            if planned:
                long = b - a > 3600
                w(W, a - 10.5, host, "system", 1074, user="SYSTEM", process=r"C:\Windows\System32\shutdown.exe" if long else r"C:\Windows\servicing\TrustedInstaller.exe",
                  reason="Other (Planned)" if long else "Operating System: Service pack (Planned)", shutdown_type="power off" if long else "restart")
                w(W, a - 1.5, host, "system", 6006, message="The Event log service was stopped.")
            else:
                w(W, b + 0.35, host, "system", 6008, message="The previous system shutdown was unexpected.")
            w(W, b + 0.01, host, "system", 6005, message="The Event log service was started.")
            w(W, b + 31 + hint(40, "wu", host, b), host, "system", 7036, service_name="Windows Update", state="running")
            sp = pid(host, "services", b)
            for i, k in enumerate(system_images(host)):
                ti = _installed_at(host, k)
                if ti is not None and b < ti + 10:
                    continue
                t = b + 4 + i * 1.7 + h01("bi", host, b, k)
                proc(E, t, host, k, "SYSTEM", pid(host, k, b), sp if k != "services" else pid(host, "wininit", b), path("services") if k != "services" else r"C:\Windows\System32\wininit.exe")
            if host == WS04 and VST_START < b:
                proc(E, b + 38.2, host, "svchost", "SYSTEM", pid(host, "vst", int(b)), sp, path("services"), image=VST_PATH, sha=VST_SHA, sign="")
            if is_server(host):
                for acc, sa in Mo.SVC.items():
                    if host in sa.get("normal_hosts", []):
                        w(W, b + 18 + hint(20, "svcl", host, acc), host, "security", 4624, user=acc, domain=S.OT_DOMAIN if is_ot(host) else S.DOMAIN, logon_type=5,
                          logon_id=lid(host, acc, b))


# ---- alerts -----------------------------------------------------------------------------------------------
SUB_BAD, SUB_LOCKED = "0xC000006A", "0xC0000234"
SUB_OTHER = ["0xC0000071", "0xC0000071", "0xC0000070", "0xC000006F"]      # expired password, workstation restriction, logon hours
PUA = ["PUA:Win32/Toolbar", "PUA:Win32/CouponHelper", "PUA:Win32/BundleInstaller", "PUA:Win32/PCOptimizer", "PUA:Win32/DownloadManager", "PUA:Win32/SearchAssist"]
GROUPS_LOCAL = ["Administrators", "Remote Desktop Users", "Power Users"]
GROUPS_GLOBAL = ["Helpdesk Operators", "Workstation Admins", "VPN-Users", "GIS-Editors", "Finance-Approvers", "SQL-Admins", "Storm-Response"]
GROUPS_UNIV = ["All-Staff-Notify", "Field-Mobile-Users", "Contractors-External"]


def failed_type(host, user, t):
    so = Mo.session_at(host, t)
    if so and so["user"] == user:
        return 7, None
    return 2, None


def b_alerts(W, E, lo, hi):
    al = Mo.alerts_between(lo - 6200, hi + 2200, Mo.EVIDENCE_RULES)
    bursts, locks, burst_uh, burst_seq = {}, {}, {}, {}
    for r in al:
        if r[1] == "FAILED_LOGON_BURST":
            bursts.setdefault(r[5], []).append(r[0])
            burst_uh.setdefault((r[5], r[2]), []).append(r[0])
            burst_seq.setdefault((r[5], r[2]), []).append((r[0], int(re.search(r"failures=(\d+)", r[6]).group(1))))
        elif r[1] == "ACCOUNT_LOCKOUT":
            locks.setdefault(r[5], []).append(r[0])

    def near(d, k, a, b):
        v = d.get(k, [])
        i = bisect.bisect_left(v, a)
        return i < len(v) and v[i] < b

    for t, rule, host, sip, dst, user, detail, aid in al:
        if host not in WIN:
            continue
        if rule == "FAILED_LOGON_BURST":
            n = int(re.search(r"failures=(\d+)", detail).group(1))
            if near(locks, user, t - 1800, t):
                sub = SUB_LOCKED
            elif near(bursts, user, t - 2100, t - 0.5) or h01("sub", aid) < 0.15:
                sub = pick(SUB_OTHER, "subo", aid)
            else:
                sub = SUB_BAD
            lt, pr = failed_type(host, user, t)
            # Two alerts for the same account and machine less than 300 s apart share part of their windows:
            # the later one counts the earlier one's failures too, so only the difference is new.
            seq = burst_seq[(user, host)]
            k = bisect.bisect_left(seq, (t, 0))
            prev = seq[k - 1] if k > 0 and t - seq[k - 1][0] < 300 else None
            nxt = seq[k + 1] if k + 1 < len(seq) and seq[k + 1][0] - t < 300 else None
            if prev:
                lo_t, cnt = max(prev[0], t - 300) + 0.3, max(0, n - min(prev[1], n))
                times = [lo_t + h01("f", aid, i) * (t - 3 - lo_t) for i in range(cnt - 1)] + ([t - 0.2 - h01("fl", aid) * 2.3] if cnt else [])
            else:
                keep = min(n, nxt[1]) if nxt else n                    # failures that also fall into the next alert's window
                cut = nxt[0] - 300 if nxt else t - 296
                times = [t - 0.2 - h01("fl", aid) * 2.3] + [cut + 0.5 + h01("f", aid, i) * (t - 4 - cut) for i in range(keep - 1)]
                times += [t - 299 + h01("fo", aid, i) * (cut - (t - 299)) for i in range(n - keep)]
            for tf in sorted(times):
                f = dict(user=user, logon_type=lt, sub_status=sub)
                if pr:
                    f["process"] = pr
                w(W, tf, host, "security", 4625, **f)
        elif rule == "ACCOUNT_LOCKOUT":
            dc = pick(S.DCS, "lkdc", aid)
            tl = t - h01("lk", aid) * 1.5
            lt, pr = failed_type(host, user, t)
            tf, k = tl - 0.6, 3 + hint(3, "lkn", aid)
            for i in range(k):                                # each failed attempt: a failed logon on the machine and a failed pre-authentication on the DC
                if not any(tb - 301 <= tf <= tb + 1 for tb in burst_uh.get((user, host), [])):
                    w(W, tf, host, "security", 4625, user=user, logon_type=lt, sub_status=SUB_BAD)
                w(W, tf - 0.2, dc, "security", 4771, outcome="failure", user=user, domain=S.DOMAIN, src_ip=IP[host], status="0x18")
                tf -= 95 + hint(240, "lkg", aid, i)
            w(W, tl, dc, "security", 4740, target_user=user, domain=S.DOMAIN, caller_computer=host)
        elif rule == "LOGON_OUTSIDE_HOURS" and "src_ip=" in detail:
            pass                                            # a remote-desktop logon over the employee VPN: written by b_vpn
        elif rule == "LOGON_OUTSIDE_HOURS":
            so = Mo.session_at(host, t)
            f = dict(user=user, domain=S.DOMAIN)
            if so is None:
                f["logon_type"] = 11 if WIN[host]["device_type"] == "laptop" else 2
                f["logon_id"] = L = lid(host, user, t)
            else:
                f.update(logon_type=3, logon_id=lid(host, user, t), src_ip=f"10.14.250.{20 + hint(200, 'vpnip', aid)}")
                L = f["logon_id"]
            w(W, t, host, "security", 4624, **f)
            w(W, t + 300 + hint(5100, "ooh", aid), host, "security", 4634, user=user, domain=S.DOMAIN, logon_type=f["logon_type"], logon_id=L)
        elif rule == "ADMIN_GROUP_CHANGE":
            v = hint(3, "grp", aid)
            user = user or pick(Mo.IT_ADMINS, "grpu", aid)
            member = pick(S.USERS, "grpm", aid)["username"]
            if v == 0:
                w(W, t - 0.5, host, "security", 4732, user=user, domain=S.DOMAIN, target_user=member, group=pick(GROUPS_LOCAL, "g", aid), group_domain=host)
            else:
                w(W, t - 0.5, pick(S.DCS, "grpdc", aid), "security", 4728 if v == 1 else 4756, user=user, domain=S.DOMAIN, target_user=member,
                  group=pick(GROUPS_GLOBAL if v == 1 else GROUPS_UNIV, "g", aid), group_domain=S.DOMAIN, src_host=host)
        elif rule == "PUP_DETECTED":
            so = Mo.session_at(host, t)
            u = so["user"] if so else (WIN[host].get("primary_user") or "SYSTEM")
            u = u if u in S.USER_BY_NAME else "SYSTEM"
            p = f"C:\\Users\\{u}\\Downloads\\{hx('pup', aid, n=9)}.exe" if u != "SYSTEM" else f"C:\\Windows\\Temp\\{hx('pup', aid, n=9)}.exe"
            thr = pick(PUA, "pua", aid)
            w(W, t - 2 - h01("pd", aid) * 3, host, "defender", 1116, user=u, threat_name=thr, path=p, severity="Low")
            w(W, t - 0.4, host, "defender", 1117, user=u, threat_name=thr, path=p, action="Quarantine")
        elif rule == "USB_STORAGE_MOUNTED":
            so = Mo.session_at(host, t)
            pu = WIN[host].get("primary_user")
            owner = so["user"] if so else (pu if pu in S.USER_BY_NAME else host)
            v, m_, serial = Mo.usb_device(owner, aid)
            e(E, t - 1.0, host, "usb_device", acct(so["user"], host)[0] if so else "SYSTEM", 4, "System", device_vendor=v, device_model=m_,
              device_serial=serial, drive_letter=pick(["E:", "F:", "D:"], "usbd", owner))


def split_unc(p):
    parts = p.lstrip("\\").split("\\")
    return parts[1], "\\".join(parts[2:])


def smb_flow_before(src_ip, dst_ip, t, win=40):
    """True if the delivered Zeek log has a file-sharing flow src -> dst that started within `win` seconds before t."""
    for d in (G.day_utc(t - win), G.day_utc(t)):
        for r in Mo.conn_day(d):
            if r[4] == 445 and r[1] == src_ip and r[3] == dst_ip and r[9] == "SF" and t - win <= r[0] <= t + 0.5:
                return True
    return False


# ---- audit tables -----------------------------------------------------------------------------------------
def b_ep(W, lo, hi):
    for r in Mo.audit("endpoint_protection"):
        t = ts(r["time_utc"])
        if not (lo - 5 <= t < hi + 5) or r["host"] not in WIN:
            continue
        ev, det, who, host = r["event"], r["detail"], r["initiated_by"], r["host"]
        who = "SYSTEM" if who == "system" else who
        if ev == "DEFINITIONS_UPDATED":
            w(W, t, host, "defender", 2000, engine_version=det.replace("engine ", ""), signature_version="1.417." + str(100 + hint(3000, "sig", int(t) // 43200)) + ".0")
        elif ev == "SCAN_COMPLETED":
            w(W, t, host, "defender", 1001, scan_type="Quick", result=det)
        elif ev == "REALTIME_PROTECTION_ENABLED":
            w(W, t, host, "defender", 5000, user=who, detail=det)
        elif ev == "REALTIME_PROTECTION_DISABLED":
            w(W, t, host, "defender", 5001, user=who, detail=det)
        elif ev == "THREAT_QUARANTINED":
            p = f"C:\\Users\\Public\\Downloads\\{hx('epq', host, int(t), n=9)}.exe"
            w(W, t - 2.1, host, "defender", 1116, user="SYSTEM", threat_name=det, path=p, severity="Low")
            w(W, t, host, "defender", 1117, user="SYSTEM", threat_name=det, path=p, action="Quarantine")


def b_gateway(W, lo, hi):
    for s in Mo.gw_sessions():
        if s["b"] < lo - 5 or s["a"] > hi + 5:
            continue
        L = lid(JMP, s["account"], s["a"], s["sid"])
        dom = gw_domain(s["account"])
        w(W, s["a"], JMP, "security", 4624, user=s["account"], domain=dom, logon_type=10, logon_id=L, src_ip=s["src_ip"])
        w(W, s["b"], JMP, "security", 4634, user=s["account"], domain=dom, logon_type=10, logon_id=L)


def b_fim(W, lo, hi):
    """Writes on the engineering file server: one 5145 for every file-integrity record (the SIEM's file-write alerts are raised from the same records)."""
    for r in Mo.audit("file_integrity"):
        t = ts(r["time_utc"])
        if not (lo - 60 <= t < hi + 5) or r["host"] != OT01:
            continue
        share, rel = split_unc(r["path"])
        user, sip = r["user"], IP.get(r["source_host"], "-")
        dom = gw_domain(user) if not user.startswith("GW-") else S.OT_DOMAIN
        if not smb_flow_before(sip, IP[OT01], t):
            L = lid(OT01, user, t, "fim")
            w(W, t - 2.2, OT01, "security", 4624, user=user, domain=dom, logon_type=3, logon_id=L, src_ip=sip)
            w(W, t + 2 + hint(40, "fim", int(t)), OT01, "security", 4634, user=user, domain=dom, logon_type=3, logon_id=L)
        w(W, t, OT01, "security", 5145, user=user, domain=dom, src_ip=sip, share="\\\\*\\" + share, path=rel, access="WriteData")


# ---- Zeek -------------------------------------------------------------------------------------------------
SHARES = {"GW-SRV-FILE-01": ["finance", "hr", "public", "customer_service", "procurement"], "GW-SRV-FILE-02": ["drawings", "gis_exports", "standards"],
          OT01: ["projects", "drawings", "relayconfigs", "procedures", "wtp", "setpoints"], HISTDMZ: ["exports$"]}
KRB_SVC = ["cifs/gw-srv-file-01", "cifs/gw-srv-file-02", "http/gw-srv-intra-01", "MSSQLSvc/gw-srv-sql-01:1433", "http/gw-srv-mail-01", "host/gw-srv-print-01"]
_STEMS = ["budget", "roster", "minutes", "invoice", "contract", "schedule", "report", "inventory", "estimate", "forecast", "procedure", "checklist", "summary", "work_order", "permit", "letter"]
_EXTS = ["xlsx", "docx", "pdf", "xlsx", "docx", "pdf", "pptx", "csv", "dwg", "msg"]
_FOLDERS = ["2027", "2027\\Q3", "2027\\Q4", "archive", "shared", "templates", "working", "team"]
AUTH_PORTS = {1433: 1.0, 5985: 1.0, 8443: 1.0, 135: 1.0, 636: 1.0, 80: 1.0, 443: 0.6}      # share of flows on a port that open a network logon on a Windows server


def share_file(rh, share, t, *k):
    """A file on a share (each share has a few dozen that people keep coming back to)."""
    if share in ("SYSVOL", "NETLOGON"):
        return ("cbpwa.example\\Policies\\{" + hx("gpo", hint(14, "gpo", *k), n=8).upper() + "-0000-0000-0000-000000000000}\\gpt.ini") if share == "SYSVOL" else "logon.cmd"
    if share == "exports$":
        d = dt.datetime.fromtimestamp(t - 86400 * hint(6, "exd", *k), UTC)
        return pick([f"exports\\daily_load_{d:%Y%m%d}.csv", f"exports\\feeder_summary_wk{d.isocalendar()[1]:02d}.xlsx", f"reports\\monthly_ops_{d:%Y_%m}.pdf",
                     f"exports\\pump_runtime_{d:%Y%m%d}.csv", f"exports\\daily_load_{d:%Y%m%d}.csv"], "exf", *k)
    if rh == OT01:                                       # the engineering server's own tree (the same files the integrity monitor watches)
        cat = [c for c in G._fim_catalog() if c[0].split("\\", 1)[0] == share] or G._fim_catalog()
        rel = pick(cat, "otf", share, *k)[0]
        if "{m}" in rel:
            rel = rel.format(m=f"{dt.datetime.fromtimestamp(t - 5 * 3600, UTC):%Y-%m}")
        return rel.split("\\", 1)[1] if rel.split("\\", 1)[0] == share else rel
    n = hint(40, "sfn", *k)
    return f"{pick(_FOLDERS, 'sff', share, n)}\\{pick(_STEMS, 'sfs', share, n)}_{1000 + hint(9000, 'sfi', share, n)}.{pick(_EXTS, 'sfe', share, n)}"


def archive_reads(t, dur, rb):
    """Times and paths of the yearly archive files a large read from the replica's export share covers (about 240 MB each)."""
    if rb < 2.0e7:
        return []
    n = max(1, min(9, int(round(rb / 2.4e8))))
    step = max(1.0, (dur - 4) / n)
    i0 = hint(12 - n + 1, "ar0", int(t)) if n < 8 else 0          # which months of the year's archive the reader asked for
    return [(t + 2.0 + i * step + h01("ar", int(t), i) * min(20.0, step / 3), f"archive\\histarchive_2027_{i0 + i + 1:02d}.arc") for i in range(n)]


def rdp_user(o_host, t):
    """Registry user name behind a remote-desktop flow from a workstation: whoever is logged on, else the machine's usual user."""
    so = Mo.session_at(o_host, t)
    if so:
        return so["user"], so
    u = WIN[o_host].get("primary_user")
    d = G.day_utc(t)
    if u not in S.USER_BY_NAME or all(S.workday(S.USER_BY_NAME[u], x) is None for x in (d - 1, d)):
        u = pick(Mo.IT_ADMINS, "rdpu", o_host, d)      # the usual user is away: an administrator is working on the machine
    return u, None


def vst_pid(t):
    start = VST_START
    for a, b, _ in Mo.boots(WS04):
        if VST_START < b <= t - 38:
            start = b
    return pid(WS04, "vst", int(start))


UA_SYSTEM = ("Microsoft NCSI", "Microsoft-CryptoAPI", "Microsoft-Delivery-Optimization", "Windows-Update-Agent", "Microsoft BITS")


def origin_proc(W, E, host, t, rip, rport, state, dur, proto, uid):
    """(user, pid, image) of the process behind a delivered flow, adding the process start when one is needed."""
    name = Mo.names_day(G.day_utc(t)).get(uid, "")
    if host == WS04 and rip == G.BEACON_IP:
        if uid == story_flows()[0][11]:
            return G.WS04_USER["username"], pid(WS04, "att"), Mo.att_path(G.WS04_USER["username"])
        return "SYSTEM", vst_pid(t), VST_PATH
    if rport == 445:
        return "SYSTEM", 4, "System"
    if rport in (88, 389, 135, 636):
        return ("SYSTEM",) + sysimg(host, "lsass", t)
    if proto == "udp" or rport in (123, 8530):
        return ("SYSTEM",) + sysimg(host, "svchost", t)
    so = Mo.session_at(host, t)
    if so and t < so["logon"] + 6:
        so = None                                         # the shell is not up yet: whatever connects now is the system's
    rhost = S.host_of_ip(rip)

    def on_demand(key, user, parent_pid, parent_img):
        tp = t - 2 - hint(25, "od", host, int(t))
        if so:
            tp = max(tp, so["logon"] + 3.5)
        p = pid(host, key, user, int(t))
        proc(E, min(tp, t - 0.3), host, key, user, p, parent_pid, parent_img)
        return user, p, path(key)

    # software with its own service or agent, recognised by the name it talks to
    if name == ZX.AGENT_NAME or name.startswith("ua:VantageAgent"):
        return ("SYSTEM",) + sysimg(host, "vscollect", t)
    if name in series_sw(host):
        key, ti, usr = series_sw(host)[name]
        if usr:
            return once(E, so, key, t) if so else ("SYSTEM",) + sysimg(host, "svchost", t)
        return ("SYSTEM",) + sysimg(host, key, t)
    if name.startswith("ua:"):
        ua = name[3:]
        if ua.startswith(UA_SYSTEM):
            return ("SYSTEM",) + sysimg(host, "svchost", t)
        if ua.startswith("Java/"):
            return ("SYSTEM",) + sysimg(host, "javaw", t)
        if ua.startswith("Go-http-client"):
            return ("SYSTEM",) + sysimg(host, "invagent", t)
        if so and corp_desktop(host) and state == "SF":
            return once(E, so, ua_browser(ua) if ua.startswith("Mozilla") else browser_key(so["user"]), t)
        return ("SYSTEM",) + sysimg(host, "svchost", t)
    if host == JMP:
        gs = Mo.gw_session(t, rhost)
        key = {3389: "mstsc", 5450: "histtrend", 502: "relayset", 20000: "relayset"}.get(rport)
        if gs is None or key is None or not (gs["a"] + 1.5 <= t <= gs["b"] - 0.5):
            return ("SYSTEM",) + sysimg(host, "ragw", t)
        user, p, img = on_demand(key, gs["account"], sys_pid(host, "ragw", t), path("ragw"))
        E[-1] = (min(max(E[-1][0], gs["a"] + 1.013 + 0.4 * h01("odm", gs["a"], key)), t - 0.3),) + E[-1][1:]       # never before the session's logon
        return user, p, img
    if rport == 3389 and state == "SF":
        u, so2 = rdp_user(host, t)
        user = acct(u, host)[0]
        if so2 is None:                                   # nobody at the desk: a short logon of the machine's usual user frames the connection
            a = t - 40 - hint(50, "adh", host, int(t))
            L = lid(host, user, a, "adh")
            w(W, a, host, "security", 4624, user=user, domain=acct(u, host)[1], logon_type=2, logon_id=L)
            w(W, t + dur + 60 + hint(500, "adh2", host, int(t)), host, "security", 4634, user=user, domain=acct(u, host)[1], logon_type=2, logon_id=L)
            p_ex = pid(host, "explorer", u, int(a))
            proc(E, a + 2.6, host, "explorer", user, p_ex, pid(host, "userinit", u, int(a)), path("userinit"))
            p = pid(host, "mstsc", user, int(t))
            proc(E, t - 6 - hint(20, "od", host, int(t)), host, "mstsc", user, p, p_ex, path("explorer"))
            return user, p, path("mstsc")
        return on_demand("mstsc", user, sess_proc(so2, "explorer")[1], path("explorer"))
    if rport in (502, 20000) and "FEP" in host:
        return ("SYSTEM",) + sysimg(host, "fepdrv", t)
    if rport == 4000:
        return ("SYSTEM",) + sysimg(host, "opconsole", t)
    if rport == 10000:
        return ("SYSTEM",) + sysimg(host, "bkagent", t)
    if rport == 5450 and "HIST" in host:
        return ("SYSTEM",) + sysimg(host, "histsrv", t)
    if rport == 9100:
        return ("SYSTEM",) + sysimg(host, "spoolsv" if state == "SF" else "invagent", t)
    if so and state == "SF":
        user = acct(so["user"], host)[0]
        p_ex = sess_proc(so, "explorer")[1]
        if rport in (443, 80, 8443, 8080) and corp_desktop(host):
            return once(E, so, "outlook" if rip in MAILSRV else browser_key(so["user"]), t)
        if rport == 5450:
            return on_demand("histtrend", user, p_ex, path("explorer"))
        if rport == 1433 and corp_desktop(host):
            return on_demand("ledger" if S.USER_BY_NAME[so["user"]]["department"] == "Finance and Procurement" else "wo_client", user, p_ex, path("explorer"))
        if rport in (502, 20000):
            return on_demand("relayset", user, p_ex, path("explorer"))
        if rport == 5985:
            return on_demand("mmc", user, p_ex, path("explorer"))
        if rport == 22:
            return on_demand("ssh", user, p_ex, path("explorer"))
    if rport == 1433:
        return ("SYSTEM",) + sysimg(host, "iisw" if is_server(host) else "ccm", t)
    if rport == 25:
        return ("SYSTEM",) + sysimg(host, "mailsrv", t)
    if state != "SF" and rport not in (443, 80, 8443):
        return ("SYSTEM",) + sysimg(host, "invagent", t)
    return ("SYSTEM",) + sysimg(host, "svchost", t)


def net_account(o_ip, o_host, r_host, t, uid=None):
    """(account, domain) of a network logon carried by a delivered flow."""
    if uid is not None and uid == story_flows()[1][11]:
        return "rvela", S.DOMAIN
    if o_host == JMP:
        gs = Mo.gw_session(t, r_host)
        if gs:
            return gs["account"], gw_domain(gs["account"])
    if o_host:
        so = Mo.session_at(o_host, t)
        if so:
            return acct(so["user"], r_host)
        for acc, sa in Mo.SVC.items():
            nh = sa.get("normal_hosts", [])
            if o_host in nh and r_host in nh:
                return acc, S.OT_DOMAIN if is_ot(r_host) else S.DOMAIN
        return o_host + "$", S.OT_DOMAIN if is_ot(o_host) else S.DOMAIN
    return None, None


def recent_oneoff(host, t):
    """(user, pid, image) of a program the logged-on person started in the last half hour, if any: its installer or
    updater traffic shows up as that program's connections."""
    for t0, t1, user, p, fp in _oneoffs.get(host, ()):
        if t0 + 1.5 < t < min(t0 + 1800, t1):
            return user, p, fp
    return None


def cache_write(E, host, t, user, p, img, uid):
    """Now and then a service writes a file to its data folder after talking to its server."""
    if h01("cw", uid) < 0.045 and "\\" in img:
        base = img.split("\\")
        folder = ("C:\\ProgramData\\" + base[2]) if base[1] in ("Program Files", "ProgramData") and len(base) > 3 else "C:\\ProgramData\\Cache"
        ext = pick(["dat", "tmp", "arc", "bin", "log", "dat", "idx"], "cwe", uid)
        style = h01("cwn", uid)
        stem = pick(["snapshot", "index", "telemetry", "defs", "histcache", "export", "state", "journal", "delta", "catalog"], "cwstem", uid)
        fname = hx("cwf", uid, n=10) if style < 0.5 else (f"{stem}_{2027 + (t > G.ts('2028-01-01T00:00Z'))}_{1 + hint(12, 'cwm', uid):02d}" if style < 0.82 else f"{stem}-{1 + hint(400, 'cwk', uid)}")
        fp = f"{folder}\\cache\\{fname}.{ext}"
        size = int(2000 * 10 ** (h01("cws", uid) * 4.2))
        e(E, t + 0.6 + h01("cwt", uid) * 4, host, "file_create", user, p, img, path=fp, size=size, sha256=hashlib.sha256(f"cw|{uid}".encode()).hexdigest())


def keep_flow(name, uid):
    """The agent keeps every second connection of ordinary web browsing (the categorised sites of the network log's
    sample) and every other connection."""
    return name not in G.SITE_IPS or h01("keep", uid) < BROWSE_KEEP


def keep_lookup(o, q, t):
    return q not in G.SITE_IPS or h01("keepq", o, q, int(round(t * 1000))) < BROWSE_KEEP


def b_zeek(W, E, lo, hi):
    dcs_all = set(S.DCS) | set(S.OT_DCS)
    for d in range(G.day_utc(lo) - 1, G.day_utc(hi) + 1):
        names = Mo.names_day(d)
        for t, o, op, r, rp, svc, dur, ob, rb, state, proto, uid in Mo.conn_day(d):
            if not (lo - 9000 <= t < hi + 5):
                continue
            oh, rh = WIN_IP.get(o), WIN_IP.get(r)
            if oh and svc != "dns" and proto in ("tcp", "udp"):
                user, p, img = origin_proc(W, E, oh, t, r, rp, state, dur, proto, uid)
                nm = names.get(uid, "")
                if nm in G.SITE_IPS and user != "SYSTEM" and state == "SF":
                    user, p, img = recent_oneoff(oh, t) or (user, p, img)
                elif user == "SYSTEM" and state == "SF" and (nm == ZX.AGENT_NAME or nm in series_sw(oh)) and img != path("svchost"):
                    cache_write(E, oh, t, user, p, img, uid)
                if keep_flow(nm, uid):
                    e(E, t + 0.02 + h01("nc", o, op, int(t)) * 0.3, oh, "network_connect", user, p, img, src_ip=o, src_port=op, dst_ip=r, dst_port=rp, protocol=proto)
            if not rh or state != "SF" or proto != "tcp":
                continue
            if rp == 3389:
                if oh == JMP:
                    gs = Mo.gw_session(t, rh)
                    if gs is None:
                        continue
                    user, dom = gs["account"], gw_domain(gs["account"])
                elif oh:
                    u, _ = rdp_user(oh, t)
                    user, dom = acct(u, rh)
                else:
                    continue
                L = lid(rh, user, t, op)
                w(W, t + 0.8, rh, "security", 4624, user=user, domain=dom, logon_type=10, logon_id=L, src_ip=o)
                w(W, t + 0.82, rh, "security", 4672, user=user, domain=dom, logon_id=L, privileges="SeSecurityPrivilege;SeBackupPrivilege;SeDebugPrivilege")
                w(W, t + dur + 0.5, rh, "security", 4634, user=user, domain=dom, logon_type=10, logon_id=L)
            elif rp == 445:
                user, dom = net_account(o, oh, rh, t, uid)
                if user is None:
                    continue
                L = lid(rh, user, t, op)
                on_dc = rh in dcs_all
                share = pick(["SYSVOL", "NETLOGON", "SYSVOL"], "sh", o, int(t)) if on_dc else pick(SHARES.get(rh, ["IPC$"]), "sh", o, int(t))
                if oh and not on_dc and not user.endswith("$"):          # the service ticket for the file server
                    w(W, t - 0.25 - h01("tk", uid) * 0.4, dc_for(oh, "tk", uid), "security", 4769, user=user, domain=dom, src_ip=o, service="cifs/" + rh.lower(), status="0x0")
                w(W, t + 0.3, rh, "security", 4624, user=user, domain=dom, logon_type=3, logon_id=L, src_ip=o)
                w(W, t + 0.6, rh, "security", 5140, user=user, domain=dom, src_ip=o, share="\\\\*\\" + share)
                if share != "IPC$":
                    big = archive_reads(t, dur, rb) if share == "exports$" else []
                    if big:
                        for tr, pth in big:
                            w(W, tr, rh, "security", 5145, user=user, domain=dom, src_ip=o, share="\\\\*\\" + share, path=pth, access="ReadData")
                    else:
                        n = 1 + hint(3, "nrd", uid)
                        for i in range(n):
                            wr = (not on_dc) and share != "exports$" and rh != OT01 and ob > 2_500 and h01("wr", uid, i) < 0.3   # writes on the engineering server are the file-integrity monitor's rows
                            tr = t + 0.9 + (i + h01("rdt", uid, i)) * max(0.2, (dur - 1.2) / n)
                            w(W, min(tr, t + dur + 0.9), rh, "security", 5145, user=user, domain=dom, src_ip=o, share="\\\\*\\" + share,
                              path=share_file(rh, share, t, uid, i), access="WriteData" if wr else "ReadData")
                w(W, t + dur + 1.0, rh, "security", 4634, user=user, domain=dom, logon_type=3, logon_id=L)
            elif rp in (88, 389) and rh in dcs_all:
                user, dom = net_account(o, oh, rh, t)
                if user is None:
                    continue
                if rp == 88 and h01("krb", o, int(t)) < 0.5:
                    w(W, t + 0.01, rh, "security", 4768, user=user, domain=dom, src_ip=o, service="krbtgt", status="0x0")
                else:
                    svc_ = ("ldap/" + rh.lower()) if rp == 389 else pick(KRB_SVC, "ksvc", o, int(t))
                    w(W, t + 0.01, rh, "security", 4769, user=user, domain=dom, src_ip=o, service=svc_, status="0x0")
            elif rp == 10000 and rh == "GW-SRV-BKP-01" and oh:
                L = lid(rh, "svc_backup", t, op)
                w(W, t + 0.4, rh, "security", 4624, user="svc_backup", domain=S.DOMAIN, logon_type=3, logon_id=L, src_ip=o)
                w(W, t + dur + 0.8, rh, "security", 4634, user="svc_backup", domain=S.DOMAIN, logon_type=3, logon_id=L)
            elif rp in AUTH_PORTS and oh and is_server(rh) and (rp != 636 or rh in dcs_all) and h01("auth", uid) < AUTH_PORTS[rp]:
                user, dom = net_account(o, oh, rh, t)          # an authenticated application session opens a network logon on the server
                if user is None:
                    continue
                L = lid(rh, user, t, op)
                w(W, t + 0.2 + h01("al", uid) * 0.4, rh, "security", 4624, user=user, domain=dom, logon_type=3, logon_id=L, src_ip=o)
                w(W, t + dur + 0.6 + h01("alo", uid) * 9, rh, "security", 4634, user=user, domain=dom, logon_type=3, logon_id=L)
        for t, o, r, q, ans, rc in Mo.dns_day(d):
            if not (lo <= t < hi):
                continue
            oh = WIN_IP.get(o)
            if not oh:
                continue
            if oh == WS04 and q == "update-cdn.meridiancontrols.net":
                user, p, img = G.WS04_USER["username"], pid(WS04, "att"), Mo.att_path(G.WS04_USER["username"])
            elif oh == WS04 and q == G.BEACON_SNI:
                user, p, img = "SYSTEM", vst_pid(t), VST_PATH
            elif q == ZX.AGENT_NAME:
                user, (p, img) = "SYSTEM", sysimg(oh, "vscollect", t)
            elif q in series_sw(oh) and not series_sw(oh)[q][2]:
                user, (p, img) = "SYSTEM", sysimg(oh, series_sw(oh)[q][0], t)
            else:
                so = Mo.session_at(oh, t)
                user, (p, img) = "SYSTEM", sysimg(oh, "svchost", t)
                own = q.endswith("cbpwa.example") or q.startswith("_") or q.endswith(".arpa")      # the system's own lookups: directory services, inside names
                if so and corp_desktop(oh) and not own:
                    ts_, pe, kb = sess_proc(so, "browser")
                    if t > ts_ + 0.5:
                        user, p, img = acct(so["user"], oh)[0], pe, path(kb)
                        if q in G.SITE_IPS:
                            user, p, img = recent_oneoff(oh, t) or (user, p, img)
            if keep_lookup(o, q, t):
                e(E, t - 0.01, oh, "dns_query", user, p, img, query=q, answers=ans, rcode=rc)


# ---- mail attachments opened from the mail client ----------------------------------------------------------
EXT_APP = {"pdf": "pdfview", "docx": "word", "doc": "word", "rtf": "word", "xlsx": "excel", "xls": "excel", "csv": "excel", "pptx": "pptview",
           "jpg": "imgview", "png": "imgview", "dwg": "gridcad"}


def b_mail(W, E, lo, hi):
    by_user = {}

    def sess_of(u, d):
        if d not in by_user:
            by_user[d] = {s["user"]: s for s in Mo.sessions(d)}
        return by_user[d].get(u)

    for r in Mo.audit("mail_gateway_cbpwa"):
        att = r["attachment_names"].split(";")[0]
        if not att or att == ZIP_NAME or r["action"] != "delivered" or r["direction"] == "outbound":
            continue
        tm = ts(r["time_utc"])
        if not (lo - 4 * DAY <= tm < hi):
            continue
        u = Mo.USER_BY_MAIL.get(r["recipient"])
        if not u or h01("open", r["message_id"]) > 0.6:
            continue
        u = u["username"]
        for d in range(G.day_utc(tm) - 1, G.day_utc(tm) + 4):
            s = sess_of(u, d)
            if not s or not corp_desktop(s["host"]) or s["logoff"] < tm + 400:
                continue
            t = max(tm + 60 + hint(5400, "opn", r["message_id"]), s["logon"] + 150 + hint(600, "opn2", r["message_id"]))
            if t > s["logoff"] - 60:
                continue
            host = s["host"]
            p_ol, p_ex = sess_proc(s, "outlook")[1], sess_proc(s, "explorer")[1]
            fp = Mo.cache_path(u, att)
            ext = att.rsplit(".", 1)[-1].lower()
            e(E, t, host, "file_create", u, p_ol, path("outlook"), path=fp, size=int(int(r["size_bytes"]) * 0.72), sha256=hashlib.sha256(f"att|{r['message_id']}".encode()).hexdigest())
            if ext == "zip":                                # the shell opens the archive; the person opens something inside it
                if h01("zx", r["message_id"]) < 0.14:
                    run_oneoff(W, E, s, t + 12 + hint(90, "zt", r["message_id"]), "zip", att)
                else:
                    mext = pick(["pdf", "xlsx", "docx", "pdf", "csv"], "zme", r["message_id"])
                    mp = Mo.unzip_path(u, att, att.rsplit(".", 1)[0] + "." + mext)
                    t2 = t + 8 + hint(60, "zt", r["message_id"])
                    e(E, t2, host, "file_create", u, p_ex, path("explorer"), path=mp, size=int(int(r["size_bytes"]) * 1.9), sha256=hashlib.sha256(f"zm|{r['message_id']}".encode()).hexdigest())
                    k = EXT_APP[mext]
                    proc(E, t2 + 1.2, host, k, u, pid(host, k, u, int(t2)), p_ex, path("explorer"), cmd=f'"{path(k)}" "{mp}"')
            elif ext in EXT_APP:
                k = EXT_APP[ext]
                proc(E, t + 1.4, host, k, u, pid(host, k, u, int(t)), p_ol, path("outlook"), cmd=f'"{path(k)}" "{fp}"')
            break


# ---- software deployment -----------------------------------------------------------------------------------
DEPLOY = [  # local day, package, image key, service name or None, scope, share of hosts, extra
    (-55, "Vantage Collector 6.2.0", "vscollect", "Vantage Collector Service", "all", 0.95, "task"),
    (-48, "PDFView 12.4", "pdfview", None, "corp_ws", 0.9, "run"),
    (-41, "Backup Agent 9.1", "bkagent", "Backup Agent Service", "corp_srv", 1.0, None),
    (-33, "MeetRoom 5.8", "meetroom", None, "corp_ws", 0.8, "run"),
    (-26, "Endpoint Agent 7.3", "epagent", "Endpoint Protection Agent", "all", 0.97, None),
    (-19, "Print driver package 4.1", "svchost", "Print Driver Host", "corp_ws", 0.5, None),
    (-11, "OpConsole hotfix 4.2.3", "opconsole", "Meridian Console Bridge", "ot_console", 1.0, None),
    (17, "Vantage Collector 6.2.2", "vscollect", "Vantage Collector Service", "all", 0.9, "task"),
    (31, "Endpoint Agent 7.3.1", "epagent", "Endpoint Protection Agent", "all", 0.95, None),
    (45, "LedgerFinance client 3.9", "ledger", None, "corp_ws", 0.25, None),
    (59, "Backup Agent 9.1.2", "bkagent", "Backup Agent Service", "corp_srv", 1.0, None),
    (73, "Vantage Collector 6.3.0", "vscollect", "Vantage Collector Service", "all", 0.9, "task"),
    (87, "PDFView 12.5", "pdfview", None, "corp_ws", 0.9, "run"),
    (101, "Endpoint Agent 7.4", "epagent", "Endpoint Protection Agent", "all", 0.95, None)]


def in_scope(host, scope):
    ot, srv = is_ot(host), is_server(host)
    return {"all": True, "corp_ws": not ot and not srv, "corp_srv": not ot and srv, "ot_console": ot and ("OPS" in host or "HMI" in host or "BCC" in host)}[scope]


@functools.lru_cache(maxsize=None)
def deploy_events(host):
    """[(time, package, image key, service, extra)] for a host over the whole span (deterministic)."""
    out = []
    for day, pkg, key, svc, scope, share, extra in DEPLOY:
        if not in_scope(host, scope) or h01("dep", host, pkg) > share:
            continue
        d = day + hint(3, "depd", host, pkg)
        t = (local_ts(d, "08:00") + hint(9 * 3600, "dept", host, pkg)) if not is_server(host) else (local_ts(d, "22:00") + hint(4 * 3600, "dept", host, pkg))
        for _ in range(40):
            if Mo.is_up(host, t) and Mo.is_up(host, t + 30):
                break
            t += 900
        out.append((t, pkg, key, svc, extra))
    for name, (key, t_inst, usr) in series_sw(host).items():           # software that starts a periodic series inside the span
        if t_inst is not None:
            out.append((t_inst, f"{SERIES_SW[name][4].replace(' Service', '')} {IMG[key][2]}", key, SERIES_SW[name][4], "start"))
    return sorted(out)


def b_deploy(W, E, lo, hi):
    for host in WIN:
        for t, pkg, key, svc, extra in deploy_events(host):
            if not (lo - 60 <= t < hi + 5):
                continue
            ccm = sys_pid(host, "ccm" if not is_ot(host) else "epagent", t)
            parent = path("ccm" if not is_ot(host) else "epagent")
            pm = pid(host, "msiexec", int(t))
            msi = pkg.replace(" ", "_") + ".msi"
            proc(E, t, host, "msiexec", "SYSTEM", pm, ccm, parent, cmd=f'"{path("msiexec")}" /i "C:\\Windows\\ccmcache\\{hx("cc", pkg, n=4)}\\{msi}" /qn')
            img = path(key) if svc != "Print Driver Host" else r"C:\Windows\System32\spool\drivers\x64\3\prnhost.exe"
            started = extra == "start"
            sha = sha_of(key) if started else hashlib.sha256(f"pkg|{pkg}|{img}".encode()).hexdigest()
            size = Mo.UNSIGNED_SIZE.get(key) if started and key in Mo.UNSIGNED_SIZE else 400_000 + hint(9_000_000, "deps", pkg)
            e(E, t + 3.1, host, "file_create", "SYSTEM", pm, path("msiexec"), path=img, size=size, sha256=sha)
            if svc:
                w(W, t + 6.0, host, "system", 7045, service_name=svc, image_path=img, service_type="user mode service", start_type="auto start", account="LocalSystem")
                e(E, t + 6.0, host, "service_install", "SYSTEM", pm, path("msiexec"), service_name=svc, service_image=img, start_type="auto start")
                w(W, t + 7.4, host, "system", 7036, service_name=svc, state="running")
            if started:                                     # the new service's process, from which its periodic connections come
                proc(E, t + 10.0, host, key, "SYSTEM", pid(host, key, t), sys_pid(host, "services", t), path("services"))
            if extra == "run":
                e(E, t + 4.2, host, "registry_set", "SYSTEM", pm, path("msiexec"), reg_key=r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" + "\\" + pkg.split(" ")[0], reg_value=f'"{img}" /background')
            elif extra == "task":
                e(E, t + 4.6, host, "task_create", "SYSTEM", pm, path("msiexec"), task_name="\\Vantage Security\\Collector Update Check", task_action=f'"{img}" /updatecheck', task_trigger="daily 03:15")


# ---- account administration and other background -----------------------------------------------------------
def b_misc(W, E, lo, hi):
    safe = sorted(u["username"] for u in S.USERS if u["department"] in ("Field Services", "Customer Service", "Water Distribution", "Generation") and u["username"] not in S.LEAVE)
    for wk in range(-9, 18):                               # accounts disabled for extended leave and re-enabled
        for i in range(2):
            d = wk * 7 + hint(5, "accd", wk, i)
            if -3 <= d <= 6:
                continue
            t = local_ts(d, "09:00") + hint(7 * 3600, "acct", wk, i)
            target, adm = pick(safe, "acctg", wk, i), pick(Mo.IT_ADMINS, "acca", wk, i)
            dc = pick(S.DCS, "accdc", wk, i)
            if lo <= t < hi:
                w(W, t, dc, "security", 4725, user=adm, domain=S.DOMAIN, target_user=target)
            t2 = t + (5 + hint(16, "accr", wk, i)) * DAY + hint(3600, "accr2", wk, i)
            if lo <= t2 < hi:
                w(W, t2, dc, "security", 4722, user=adm, domain=S.DOMAIN, target_user=target)
    names = ["Windows Update", "Background Intelligent Transfer Service", "WinHTTP Web Proxy Auto-Discovery Service", "Windows Modules Installer",
             "Software Protection", "Volume Shadow Copy", "Windows Installer", "Portable Device Enumerator Service"]
    simg = {"Windows Update": "wuauclt", "Windows Modules Installer": "trustedinst", "Windows Installer": "msiexec", "Software Protection": "taskhostw",
            "Volume Shadow Copy": "dllhost", "Background Intelligent Transfer Service": "rundll32"}
    hosts = sorted(WIN)
    for d in range(G.day_utc(lo), G.day_utc(hi) + 1):      # ordinary service state changes (a sample)
        for i in range(36):
            host = pick(hosts, "s36h", d, i)
            t = D0_EPOCH + d * DAY + h01("s36t", d, i) * DAY
            if lo <= t < hi and Mo.is_up(host, t) and Mo.is_up(host, t + 400):
                nm = pick(names, "s36n", d, i)
                w(W, t, host, "system", 7036, service_name=nm, state="running")
                if nm in simg:
                    proc(E, t + 0.4, host, simg[nm], "SYSTEM", pid(host, simg[nm], int(t)), sys_pid(host, "services", t), path("services"))
                w(W, t + 20 + hint(300, "s36d", d, i), host, "system", 7036, service_name=nm, state="stopped")
    t = ts("2027-10-02T15:38Z") + 20                       # the contractor account is disabled the day the incident is opened
    if lo <= t < hi:
        w(W, t, JMP, "security", 4725, user=S.G.ENGINEERS[0]["ot_account"], domain=S.OT_DOMAIN, target_user="svc_fieldops_ext")


# ---- the records fixed by the delivered mail, flow and audit rows ------------------------------------------
STAGE_DIR = r"C:\ProgramData\VantageTelemetry\cache"


def staged_files():
    """Files written on the workstation while it read the archive files from the replica: [(time, path, size)].
    Their sizes add up to the bytes the delivered flow carried."""
    h2 = story_flows()[1]
    rd = archive_reads(h2[0], h2[6], h2[8])
    wts = [0.6 + h01("stw", i) for i in range(len(rd))]
    body = int(h2[8] * 0.9968) - 4096 * len(rd)          # the flow also carried protocol headers and directory listings
    sizes = [int(body * x / sum(wts)) for x in wts]
    sizes[-1] += body - sum(sizes)
    step = (h2[6] - 4) / len(rd)
    return [(tr + step * 0.93, STAGE_DIR + "\\" + pth.rsplit("\\", 1)[1], sz) for (tr, pth), sz in zip(rd, sizes)]


def b_story(W, E, lo, hi):
    u = G.WS04_USER["username"]
    s = Mo.session_at(WS04, G.AV_OFF_T)
    p_ol, p_ex = sess_proc(s, "outlook")[1], sess_proc(s, "explorer")[1]
    ap, p_att = Mo.att_path(u), pid(WS04, "att")
    mid = next(r["message_id"] for r in Mo.audit("mail_gateway_cbpwa") if r["attachment_names"] == ZIP_NAME)
    e(E, ZIP_T0, WS04, "file_create", u, p_ol, path("outlook"), path=Mo.cache_path(u, ZIP_NAME), size=ZIP_SIZE, sha256=hashlib.sha256(f"att|{mid}".encode()).hexdigest())
    e(E, ATT_T0, WS04, "file_create", u, p_ex, path("explorer"), path=ap, size=ATT_SIZE, sha256=ATT_SHA)
    e(E, ATT_RUN, WS04, "process_start", u, p_att, ap, ppid=p_ex, parent_image=path("explorer"), command_line=f'"{ap}"', sha256=ATT_SHA, signer="")
    e(E, VST_WRITE, WS04, "file_create", u, p_att, ap, path=VST_PATH, size=VST_SIZE, sha256=VST_SHA)
    w(W, VST_SVC, WS04, "system", 7045, service_name=VST_SERVICE, image_path=VST_PATH, service_type="user mode service", start_type="auto start", account="LocalSystem")
    e(E, VST_SVC, WS04, "service_install", u, p_att, ap, service_name=VST_SERVICE, service_image=VST_PATH, start_type="auto start")
    w(W, VST_START - 0.1, WS04, "system", 7036, service_name=VST_SERVICE, state="running")
    proc(E, VST_START, WS04, "svchost", "SYSTEM", pid(WS04, "vst", int(VST_START)), sys_pid(WS04, "services", VST_START), path("services"), image=VST_PATH, sha=VST_SHA, sign="")
    for tf, fp, size in staged_files():                    # what the transfer from the replica left on the disk
        e(E, tf, WS04, "file_create", "SYSTEM", vst_pid(tf), VST_PATH, path=fp, size=size, sha256=hashlib.sha256(f"stage|{fp}|{size}".encode()).hexdigest())


# ---- build and write ---------------------------------------------------------------------------------------
WIN_RANK = {k: i for i, k in enumerate([
    "user", "domain", "target_user", "group", "group_domain", "logon_type", "logon_id", "src_ip", "src_host", "caller_computer", "process", "service", "status",
    "sub_status", "outcome", "privileges", "share", "path", "access", "service_name", "image_path", "service_type", "start_type", "account", "state", "message",
    "reason", "shutdown_type", "threat_name", "severity", "action", "detail", "engine_version", "signature_version", "scan_type", "result"])}
EDR_RANK = {k: i for i, k in enumerate([
    "ppid", "parent_image", "command_line", "sha256", "signer", "src_ip", "src_port", "dst_ip", "dst_port", "protocol", "query", "answers", "rcode", "path", "size",
    "reg_key", "reg_value", "service_name", "service_image", "start_type", "task_name", "task_action", "task_trigger", "device_vendor", "device_model",
    "device_serial", "drive_letter"])}


def ordered(f, rank):
    """Event-specific fields in one fixed order, whichever part of the generator wrote the event."""
    return sorted(f.items(), key=lambda kv: (rank.get(kv[0], 999), kv[0]))


def b_vpn(W, lo, hi):
    """Remote-desktop logons to a person's own desktop over the employee VPN (the session model in gen_itsec)."""
    for v in G.vpn_sessions():
        r = v["rdp"]
        if not r or not (lo - 20000 <= r["t"] < hi):
            continue
        host, user = r["host"], v["user"]
        L = lid(host, user, r["t"], "vpn")
        t1 = r["t"] + 1 + 0.15 + 0.6 * h01("vpnl", r["t"], host)
        w(W, t1, host, "security", 4624, user=user, domain=S.DOMAIN, logon_type=10, logon_id=L, src_ip=v["pool_ip"])
        w(W, r["t"] + r["dur"] + 0.5 + h01("vpno", r["t"], host), host, "security", 4634, user=user, domain=S.DOMAIN, logon_type=10, logon_id=L)


def build(lo, hi):
    W, E = [], []
    _started.clear()
    _oneoffs.clear()
    b_sessions(W, E, lo, hi)
    b_boots(W, E, lo, hi)
    b_alerts(W, E, lo, hi)
    b_vpn(W, lo, hi)
    b_ep(W, lo, hi)
    b_gateway(W, lo, hi)
    b_mail(W, E, lo, hi)
    b_zeek(W, E, lo, hi)
    b_fim(W, lo, hi)
    b_deploy(W, E, lo, hi)
    b_misc(W, E, lo, hi)
    b_story(W, E, lo, hi)
    a, b = max(lo, Mo.SPAN_A), min(hi, Mo.SPAN_B)
    W = [x for x in W if a <= x[0] < b]
    E = [x for x in E if a <= x[0] < b]
    dropped = sum(1 for x in W if not Mo.is_up(x[1], x[0])) + sum(1 for x in E if not Mo.is_up(x[1], x[0]))
    if dropped:
        W = [x for x in W if Mo.is_up(x[1], x[0])]
        E = [x for x in E if Mo.is_up(x[1], x[0])]
    seen, out = set(), []                                  # one logon event per logon id
    for x in sorted(W, key=lambda x: x[0]):
        if x[3] == 4624:
            k = (x[1], x[4].get("logon_id"))
            if k in seen:
                continue
            seen.add(k)
        out.append(x)
    return out, E, dropped


def month_bounds(mon):
    y, m_ = int(mon[:4]), int(mon[5:7])
    a = dt.datetime(y, m_, 1, tzinfo=UTC).timestamp()
    b = dt.datetime(y + (m_ == 12), m_ % 12 + 1, 1, tzinfo=UTC).timestamp()
    return int(a), int(b)


def all_months():
    return [m_[0] for m_ in S.months()]


def write_parts(rel_prefix, objs):
    """(files, rows). Never leaves an empty file behind."""
    if not objs:
        for old_ in glob.glob(os.path.join(ROOT, rel_prefix + "*.jsonl")):
            os.remove(old_)
        return 0, 0
    return S.write_jsonl_parts(rel_prefix, objs)


def write_windows(mon, W):
    n = {}
    for ch, (chname, rate) in CH.items():
        rows = sorted((x for x in W if x[2] == ch), key=lambda x: (x[0], x[1], x[3]))
        prev, objs = {}, []
        for t, host, _, eid, f in rows:
            base = 20_000 + hint(900_000, "rid", host, ch)
            rid = max(prev.get(host, 0) + 1, base + int((t - Mo.T0) * rate))
            prev[host] = rid
            prov = SEC_PROV if ch == "security" else (SYS_PROV[eid] if ch == "system" else "Microsoft-Windows-Windows Defender")
            lvl = "error" if eid == 6008 else ("warning" if eid == 1116 else "information")
            o = {"time_utc": iso_ms(t), "host": host, "channel": chname, "provider": prov, "event_id": eid, "record_id": rid, "level": lvl}
            o.update(ordered(f, WIN_RANK))
            objs.append(o)
        n[ch] = write_parts(f"{WIN_DIR}/{ch}_{mon}", objs)
    return n


def write_endpoint(mon, E):
    rows = sorted(E, key=lambda x: (x[0], x[1], x[2]))
    objs = []
    for t, host, etype, user, p, img, f in rows:
        o = {"time_utc": iso_ms(t), "host": host, "event_type": etype, "user": user, "pid": p, "image": img}
        o.update(ordered(f, EDR_RANK))
        objs.append(o)
    return write_parts(f"{EDR_DIR}/endpoint_{mon}", objs)


def run_month(mon, what):
    t0 = time.time()
    lo, hi = month_bounds(mon)
    W, E, dropped = build(lo, hi)
    msg = [f"{mon}:"]
    if what in ("windows", "month"):
        n = write_windows(mon, W)
        msg.append("windows " + ", ".join(f"{k} {v[1]:,} ({v[0]} file{'s' if v[0] > 1 else ''})" for k, v in n.items()))
    if what in ("endpoint", "month"):
        files, cnt = write_endpoint(mon, E)
        msg.append(f"endpoint {cnt:,} ({files} file{'s' if files > 1 else ''})")
    msg.append(f"dropped-while-off {dropped}; {time.time() - t0:.0f}s")
    print(" ".join(msg), flush=True)


# ---- triage collections ------------------------------------------------------------------------------------
def _iter_jsonl(folder, prefix, hosts):
    needles = {h: f'"host":"{h}"' for h in hosts}
    for fp in sorted(glob.glob(os.path.join(ROOT, folder, prefix + "*.jsonl"))):
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                for h, nd in needles.items():
                    if nd in line:
                        yield h, json.loads(line)
                        break


BASE_SW = [("Microsoft Office Professional Plus", "16.0.17328", "Microsoft Corporation"), ("Microsoft Edge", "139.0.3405", "Microsoft Corporation"),
           ("Endpoint Agent", "7.3", "Endpoint Agent Software Inc"), ("Vantage Collector", "6.2", "Vantage Security Systems Inc"),
           ("Configuration Manager Client", "5.00.9106", "Microsoft Corporation")]
BASE_SVC = [("Dnscache", "DNS Client", "auto", r"C:\Windows\System32\svchost.exe", "NetworkService"), ("EventLog", "Windows Event Log", "auto", r"C:\Windows\System32\svchost.exe", "LocalService"),
            ("WinDefend", "Microsoft Defender Antivirus Service", "auto", IMG["defender"][0], "LocalSystem"), ("wuauserv", "Windows Update", "manual", r"C:\Windows\System32\svchost.exe", "LocalSystem"),
            ("Spooler", "Print Spooler", "auto", r"C:\Windows\System32\spoolsv.exe", "LocalSystem"), ("LanmanWorkstation", "Workstation", "auto", r"C:\Windows\System32\svchost.exe", "NetworkService"),
            ("Schedule", "Task Scheduler", "auto", r"C:\Windows\System32\svchost.exe", "LocalSystem"), ("W32Time", "Windows Time", "auto", r"C:\Windows\System32\svchost.exe", "LocalService")]
SYS32 = ["kernel32.dll", "ntdll.dll", "user32.dll", "advapi32.dll", "cmd.exe", "conhost.exe", "taskhostw.exe", "dllhost.exe", "rundll32.exe", "wininit.exe", "smss.exe", "csrss.exe",
         "spoolsv.exe", "SearchIndexer.exe", "wuauclt.exe", "taskmgr.exe", "notepad.exe", "mmc.exe", "netsh.exe", "ipconfig.exe", "whoami.exe", "sc.exe", "reg.exe", "schtasks.exe"]


def write_csv(rel, header, rows):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        cw = csv.writer(fh, lineterminator="\n")
        cw.writerow(header)
        cw.writerows(rows)
    return len(rows)


def z(t):
    return dt.datetime.fromtimestamp(int(t), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def gen_triage():
    import shutil
    hosts = dict(TRIAGE)
    edr = {h: [] for h in hosts}
    for h, o in _iter_jsonl(EDR_DIR, "endpoint_", hosts):
        if ts(o["time_utc"][:19] + "Z") < hosts[h]:
            edr[h].append(o)
    sec = {h: [] for h in hosts}
    for h, o in _iter_jsonl(WIN_DIR, "security_", hosts):
        t = ts(o["time_utc"][:19] + "Z")
        if hosts[h] - 45 * DAY <= t < hosts[h] and o["event_id"] in (4624, 4625, 4634, 4647):
            sec[h].append(o)
    sysl = {h: [] for h in hosts}
    for h, o in _iter_jsonl(WIN_DIR, "system_", hosts):
        if ts(o["time_utc"][:19] + "Z") < hosts[h]:
            sysl[h].append(o)
    old = os.path.join(ROOT, TRI_DIR)
    if os.path.isdir(old):
        shutil.rmtree(old)
    total = 0
    for host, tc in TRIAGE:
        hreg = WIN[host]
        base = f"{TRI_DIR}/{host}"
        inst = Mo.T0 - hint(400 * DAY, "os_inst", host)
        owner = hreg.get("primary_user") if hreg.get("primary_user") in S.USER_BY_NAME else None
        # services: the base set, role services, then every service the system log shows being registered
        svcs = [[n_, dn, st, "running" if st == "auto" else "stopped", img, acc_, z(inst)] for n_, dn, st, img, acc_ in BASE_SVC]
        role = []
        for k in system_images(host):
            if k in ("services", "lsass", "svchost", "defender", "spoolsv"):
                continue
            ti = _installed_at(host, k)
            if ti is not None and ti > tc:
                continue
            role.append(k)
        names = {"vscollect": "Vantage Collector Service", "epagent": "Endpoint Protection Agent", "ccm": "SMS Agent Host", "bkagent": "Backup Agent Service",
                 "opconsole": "Meridian Console Bridge", "histsrv": "Meridian Historian", "fepdrv": "Meridian Front End Driver", "scadasrv": "Meridian SCADA Server", "ragw": "Remote Access Gateway",
                 "invagent": "Asset Inventory Agent", "javaw": "CBPWA Work Order Sync", "mailsrv": "Mail Store Service", "sqlsrv": "DataServer Engine", "mgmtsrv": "Endpoint Config Server",
                 "iisw": "World Wide Web Publishing Service"}
        names.update({v[0]: v[4] for v in SERIES_SW.values() if v[4]})
        seen = {}
        for k in role:                                     # services that were there before the logs begin
            seen[names[k]] = [names[k].replace(" ", ""), names[k], "auto", "running", path(k), "LocalSystem", z(min(inst + hint(200 * DAY, "svci", host, k), Mo.SPAN_A - DAY - hint(30 * DAY, "svcb", host, k)))]
        for o in sysl[host]:
            if o["event_id"] == 7045:
                nm = o["service_name"]
                seen[nm] = [nm.replace(" ", ""), nm, "auto", "running", o["image_path"], o["account"], o["time_utc"][:19] + "Z"]
        svcs += list(seen.values())
        n1 = write_csv(f"{base}/services.csv", ["name", "display_name", "start_type", "state", "image_path", "account", "installed_utc"], svcs)
        # files: operating system sample, program folders, everything the endpoint agent saw being written
        files = {}

        def addf(p, size, created, modified, sha, sign):
            created = min(created, tc - 3600 - hint(40 * DAY, "fclamp", host, p))  if created >= tc else created      # nothing is newer than the collection
            modified = max(created, modified if modified < tc else tc - 600 - hint(20 * DAY, "mclamp", host, p))
            files[p.lower()] = [p, size, z(created), z(modified), sha, sign]

        for fn in SYS32:
            addf("C:\\Windows\\System32\\" + fn, 20_000 + hint(900_000, "s32", fn), inst, inst + hint(300 * DAY, "s32m", fn), hashlib.sha256(f"s32|{fn}".encode()).hexdigest(), Mo.MSW)
        keys = ["winlogon", "userinit", "services", "lsass", "svchost", "consent", "mstsc", "msiexec", "explorer", "defender"] + role
        if corp_desktop(host):
            keys += ["outlook", "word", "excel", "edge"]
        for o in edr[host]:
            if o["event_type"] == "process_start":
                for k, v in IMG.items():
                    if v[0] == o["image"] and k not in keys:
                        keys.append(k)
        for k in keys:
            if k == "system":
                continue
            addf(path(k), Mo.UNSIGNED_SIZE.get(k, 90_000 + hint(6_000_000, "fsz", k)), inst + hint(250 * DAY, "fcr", host, k), inst + hint(390 * DAY, "fmd", host, k), sha_of(k), signer(k))
        for fp_, size_, sha_ in Mo.local_tools(host):         # the machine's own utilities
            tcr_ = inst + hint(380 * DAY, "ltc", host, fp_)
            addf(fp_, size_, tcr_, tcr_ + hint(30 * DAY, "ltm", host, fp_), sha_, "")
        users = sorted({o["user"] for o in sec[host] if o["event_id"] == 4624 and o.get("logon_type") in (2, 11) and o["user"] in S.USER_BY_NAME} | ({owner} if owner else set()))
        for u in users:
            for i in range(6 + hint(10, "docs", host, u)):
                ext = pick(["docx", "xlsx", "pdf", "pptx", "txt", "docx", "xlsx", "pdf", "zip"], "dext", host, u, i)
                tcr = tc - hint(400 * DAY, "dcr", host, u, i)
                addf(f"C:\\Users\\{u}\\Documents\\{hx('ud', host, u, i, n=8)}.{ext}", 9_000 + hint(3_000_000, "dsz", host, u, i), tcr, tcr + hint(20 * DAY, "dmd", host, u, i),
                     hashlib.sha256(f"doc|{host}|{u}|{i}".encode()).hexdigest(), "")
        for o in edr[host]:
            if o["event_type"] == "file_create":
                t = ts(o["time_utc"][:19] + "Z")
                sign = next((v[1] for v in IMG.values() if v[0] == o["path"]), "")
                addf(o["path"], o["size"], t, t, o["sha256"], sign)
        n2 = write_csv(f"{base}/file_listing.csv", ["path", "size_bytes", "created_utc", "modified_utc", "sha256", "signer"], sorted(files.values(), key=lambda r: r[0].lower()))
        # scheduled tasks and autoruns
        tasks = [["\\Microsoft\\Windows\\Defender\\Scheduled Scan", f'"{path("defender")}" -scan', "Microsoft Corporation", z(inst), z(tc - hint(DAY, "tk1", host)), "daily"],
                 ["\\Microsoft\\Windows\\UpdateOrchestrator\\Schedule Scan", r"C:\Windows\System32\usoclient.exe StartScan", "Microsoft Corporation", z(inst), z(tc - hint(DAY, "tk2", host)), "daily"]]
        runs = []
        for o in edr[host]:
            if o["event_type"] == "task_create":
                tasks = [t_ for t_ in tasks if t_[0] != o["task_name"]] + [[o["task_name"], o["task_action"], "SYSTEM", o["time_utc"][:19] + "Z", z(tc - hint(DAY, "tk3", host)), o["task_trigger"]]]
            elif o["event_type"] == "registry_set" and "\\Run\\" in o["reg_key"]:
                runs = [r_ for r_ in runs if r_[1] != o["reg_key"].rsplit("\\", 1)[1]] + [["registry run key", o["reg_key"].rsplit("\\", 1)[1], o["reg_value"], "", "", "yes", o["time_utc"][:19] + "Z"]]
        n3 = write_csv(f"{base}/scheduled_tasks.csv", ["task_name", "action", "author", "created_utc", "last_run_utc", "trigger"], tasks)
        auto = []
        for s_ in svcs:
            if s_[2] == "auto":
                f_ = files.get(s_[4].lower())
                auto.append(["service", s_[1], s_[4], f_[5] if f_ else Mo.MSW, f_[4] if f_ else "", "yes", s_[6]])
        for r_ in runs:
            img = r_[2].split('"')[1] if '"' in r_[2] else r_[2]
            f_ = files.get(img.lower())
            auto.append([r_[0], r_[1], r_[2], f_[5] if f_ else "", f_[4] if f_ else "", "yes", r_[6]])
        for t_ in tasks:
            auto.append(["scheduled task", t_[0], t_[1], "", "", "yes", t_[3]])
        n4 = write_csv(f"{base}/autoruns.csv", ["location", "name", "image_path", "signer", "sha256", "enabled", "first_seen_utc"], auto)
        # execution history from the agent's process records
        ex = {}
        for o in edr[host]:
            if o["event_type"] == "process_start":
                r_ = ex.setdefault(o["image"], [o["image"], 0, o["time_utc"][:19] + "Z", "", o["sha256"]])
                r_[1] += 1
                r_[3] = o["time_utc"][:19] + "Z"
        n5 = write_csv(f"{base}/execution_history.csv", ["image_path", "run_count", "first_run_utc", "last_run_utc", "sha256"], sorted(ex.values(), key=lambda r: r[0].lower()))
        lg = [[o["time_utc"][:19] + "Z", o["event_id"], o.get("user", ""), o.get("domain", ""), o.get("logon_type", ""), o.get("src_ip", ""), o.get("logon_id", "")] for o in sec[host]]
        n6 = write_csv(f"{base}/logon_history.csv", ["time_utc", "event_id", "user", "domain", "logon_type", "src_ip", "logon_id"], lg)
        sw = list(BASE_SW) if corp_desktop(host) else BASE_SW[2:4]
        ran = {o["image"] for o in edr[host] if o["event_type"] == "process_start"}
        if path("chrome") in ran:
            sw.append(("Google Chrome", "139.0.7258", "Google LLC"))
        if path("firefox") in ran:
            sw.append(("Mozilla Firefox", "141.0", "Mozilla Corporation"))
        sw = [[n_, v, pub, z(min(inst + hint(300 * DAY, "swi", host, n_), Mo.SPAN_A - DAY))[:10]] for n_, v, pub in sw]
        for t, pkg, key, svc, extra in deploy_events(host):
            if t < tc:
                name, ver = pkg.rsplit(" ", 1)
                sw = [r_ for r_ in sw if r_[0] != name] + [[name, ver, signer(key) or "Coastal Bend Power and Water Authority", z(t)[:10]]]
        n7 = write_csv(f"{base}/installed_software.csv", ["name", "version", "publisher", "install_date"], sorted(sw))
        gwip = hreg["ip"].rsplit(".", 1)[0] + ".1"
        dns = ";".join(IP[x] for x in (S.OT_DCS if is_ot(host) else S.DCS))
        n8 = write_csv(f"{base}/network_config.csv", ["interface", "ip", "mac", "gateway", "dns_servers", "dhcp_enabled"],
                       [["Ethernet0", hreg["ip"], S.mac_of(host), gwip, dns, "yes" if hreg["device_type"] in ("workstation", "laptop") and not is_ot(host) else "no"]])
        # inert stand-ins for the unsigned binaries the collector copied
        ph = []
        for r_ in sorted(files.values(), key=lambda r: r[0].lower()):
            if r_[0].lower().endswith(".exe") and r_[5] == "" and not r_[0].lower().startswith("c:\\windows\\system32"):
                name = r_[0].rsplit("\\", 1)[1]
                txt = Mo.placeholder_text(name, r_[1])
                if hashlib.sha256(txt.encode("utf-8")).hexdigest() != r_[4]:
                    continue
                rel = f"{base}/placeholders/{name}.placeholder.txt"
                os.makedirs(os.path.dirname(os.path.join(ROOT, rel)), exist_ok=True)
                with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(txt)
                ph.append({"file": f"placeholders/{name}.placeholder.txt", "stands_in_for": r_[0], "sha256": r_[4]})
        items = {}
        for fn in ("services", "file_listing", "scheduled_tasks", "autoruns", "execution_history", "logon_history", "installed_software", "network_config"):
            with open(os.path.join(ROOT, base, fn + ".csv"), "rb") as fh:
                b_ = fh.read()
            items[fn + ".csv"] = {"rows": b_.count(b"\n") - 1, "sha256": hashlib.sha256(b_).hexdigest()}
        col = {"host": host, "ip": hreg["ip"], "os": hreg["os"], "collected_utc": z(tc), "collected_by": "CBPWA Security Operations", "tool": "triage-collector 3.2",
               "case": "SI-2027-CC-001", "logon_history_window_days": 45, "items": items, "samples": ph,
               "note": "The collector copies every unsigned executable it finds outside the Windows folders. The copies are stored as inert text placeholders."}
        with open(os.path.join(ROOT, base, "collection.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(col, fh, indent=1)
            fh.write("\n")
        total += n1 + n2 + n3 + n4 + n5 + n6 + n7 + n8
        print(f"triage {host}: files {n2}, services {n1}, tasks {n3}, autoruns {n4}, executions {n5}, logons {n6}, software {n7}, placeholders {len(ph)}", flush=True)
    print(f"host_triage: {len(TRIAGE)} collections, {total:,} rows")


# ---- command line ------------------------------------------------------------------------------------------
def main(argv):
    if not argv:
        print(__doc__)
        return 2
    if argv[0] in ("windows", "endpoint", "month"):
        for mon in argv[1:] or all_months():
            run_month(mon, argv[0])
        return 0
    if argv[0] == "triage":
        gen_triage()
        return 0
    if "--all" in argv:
        budget = next((float(a.split("=", 1)[1]) for a in argv if a.startswith("--budget=")), 0)
        ck = os.environ.get("ITSEC_HOST_CKPT", "/tmp/itsec_host_ckpt.json")
        done = json.load(open(ck)) if ("--resume" in argv and os.path.exists(ck)) else []
        t0 = time.time()
        for step in all_months() + ["triage"]:
            if step in done:
                continue
            if budget and time.time() - t0 > budget:
                print("more to do; run again with --resume")
                return 3
            if step == "triage":
                gen_triage()
            else:
                run_month(step, "month")
            done.append(step)
            with open(ck, "w") as fh:
                json.dump(done, fh)
        if os.path.exists(ck):
            os.remove(ck)
        print("DONE")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
