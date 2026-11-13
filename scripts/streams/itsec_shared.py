"""Shared model for the raw IT and security logs of the utility (CBPWA).

The raw logs added on 2026-11-12 (firewall, web proxy, DHCP, packet capture, Windows event logs, endpoint
telemetry, host triage) describe the SAME network activity as the logs that were already delivered
(SIEM alerts, Zeek conn/dns/ssl, the audit tables). To keep every family consistent they all build on
this module and on the delivered files, never on their own invention:

  * who is at work when                -> workday(), on_shift(), interactive_sessions()
  * which flows crossed the network     -> zeek_day()            (reads the delivered Zeek logs)
  * which alerts the SIEM raised        -> siem_by_day()         (reads the delivered alert files)
  * what the audit tables say           -> audit()               (reads the delivered audit CSVs)
  * where an address sits               -> zone_of(), host_of_ip()

Run order: gen_itsec.py (siem, zeek, audit, portal) first, then the raw-log generators.
Sampling convention (same as the Zeek logs): ordinary background activity is a sample; everything
that involves a host, account or time named by an alert, a remote session or an audit record is complete.
"""
import csv
import datetime as dt
import glob
import ipaddress
import json
import os

import gen_itsec as G
from common import D0_EPOCH, ROOT, UTC, day_of, local_dt, local_ts, rng, ts

DAY = 86400
NET = "05_other_sources/network_logs"
FIRST_DAY, LAST_DAY = G.day_utc(G.SPAN_START), G.day_utc(G.SPAN_END - 1)      # UTC day numbers, D0 = 0
M = G.M
HOSTS, USERS, IP, BYNAME = G.HOSTS, G.USERS, G.IP, G.BYNAME
REG = G.H
HOST_BY_IP = {h["ip"]: h for h in HOSTS}
USER_BY_NAME = {u["username"]: u for u in USERS}
_ZONES = [(ipaddress.ip_network(zn["cidr"]), zn["zone"]) for zn in REG["network_zones"]]
DOMAIN, OT_DOMAIN = "CBPWA", "CBPWA-OT"
DCS = ["GW-SRV-DC-01", "GW-SRV-DC-02"]
OT_DCS = ["GW-SRV-OTDC-01", "GW-SRV-OTDC-02"]
WINDOWS = [h for h in HOSTS if str(h.get("os", "")).startswith("Windows")]
WORKSTATIONS = [h for h in HOSTS if h["device_type"] in ("workstation", "laptop")]

# ---- log formats (the contract between the generators, the schemas and the probes) -----------------
FW_COLS = ["time_utc", "device", "action", "rule_name", "src_zone", "dst_zone", "src_ip", "src_port", "dst_ip", "dst_port",
           "proto", "app", "bytes_sent", "bytes_recv", "duration_s", "nat_src_ip", "session_end_reason"]
PROXY_COLS = ["time_utc", "client_ip", "user", "method", "scheme", "host", "url_path", "status", "action", "category",
              "bytes_out", "bytes_in", "user_agent_family", "policy"]
DHCP_COLS = ["time_utc", "server", "event", "ip", "mac", "hostname", "scope", "lease_s"]
# Windows event logs and endpoint telemetry are JSON Lines, one object per event. Common keys first:
WIN_KEYS = ["time_utc", "host", "channel", "provider", "event_id", "record_id", "level"]        # + event-specific keys
EDR_KEYS = ["time_utc", "host", "event_type", "user", "pid", "image"]                             # + event-specific keys


def zone_of(ip):
    """Registry zone of an address; 'internet' for anything outside the utility's networks."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return "unknown"
    for net, name in _ZONES:
        if a in net:
            return name
    return "internet"


def host_of_ip(ip):
    h = HOST_BY_IP.get(ip)
    return h["hostname"] if h else None


def is_ot_zone(zone):
    return zone.startswith("ot-")


def mac_of(hostname):
    """Adapter address of a host (see gen_itsec.mac_of)."""
    return G.mac_of(hostname)


def day_str(d):
    return dt.datetime.fromtimestamp(D0_EPOCH + d * DAY, UTC).strftime("%Y-%m-%d")


# The shared contractor desk is used by one member of staff on the day the delivered mail and
# endpoint-protection records show them on it (local scenario day -15, 2027-08-30).
SESSION_HOST_OVERRIDE = {(G.WS04_USER["username"], -15): G.WS04}


# ---- people ---------------------------------------------------------------------------------------------
def _shift_team(u):
    return sum(map(ord, u["username"])) % 4


HOLIDAYS = G.HOLIDAYS            # local scenario days on which offices are closed
LEAVE = {"rvela": (ts("2027-09-06T22:00Z"), ts("2027-09-22T06:00Z"))}        # canon
# moments at which the delivered records show a member of the security team at work (rule changes, closures)
FORCED = {G.WS04_USER["username"]: ["2027-08-30T12:40Z", "2027-08-30T13:30Z"], "jperez": ["2027-09-11T22:58Z", "2027-09-14T06:14Z", "2027-09-18T14:00Z"], "tperez": ["2027-08-31T14:22Z"], "imorales": ["2027-09-11T18:39Z"],
          "falrasheedobinna": ["2027-10-02T15:10Z", "2027-10-18T15:20Z"], "aclark": ["2027-08-24T15:02Z"], "bflores": ["2027-09-28T22:25Z", "2027-09-30T18:20Z", "2027-10-19T00:30Z"]}
FORCED = {k: [ts(x) for x in v] for k, v in FORCED.items()}


def workday(u, d, _cache={}):
    k = (u["username"], d)
    if k not in _cache:
        w = _workday(u, d)
        for t in FORCED.get(u["username"], ()):
            if day_of(t - 5 * 3600) != d and day_of(t) != d:
                continue
            prev = _workday(u, d - 1)
            if (w and w[0] <= t < w[1]) or (prev and prev[0] <= t < prev[1]) or (day_of(t) != d and _workday(u, day_of(t))):
                continue
            w = (min(w[0], t - 2400), max(w[1], t + 2400)) if (w and abs((w[0] + w[1]) / 2 - t) < 12 * 3600) else (t - 3 * 3600 - 600, t + 9 * 3600)
        _cache[k] = w
    return _cache[k]


def away(u, t):
    """True while a person is on leave, or off for the whole of a working weekday."""
    lv = LEAVE.get(u["username"])
    if lv and lv[0] <= t <= lv[1]:
        return True
    d = day_of(t)
    if u.get("normal_hours", "").startswith("rotating"):
        return False
    return local_dt(t).weekday() < 5 and d not in HOLIDAYS and workday(u, d) is None


def _workday(u, d):
    """(start, end) epoch of the working period of user u that begins on LOCAL scenario day d, or None.
    Deterministic. Office staff: weekdays (some Saturdays for the Mon-Sat group), fewer people around the
    storm. Shift staff: 12-hour shifts, two days on, two off, alternating teams; they keep working in the storm."""
    g = rng("presence", u["username"], d)
    l = local_dt(local_ts(d, "12:00"))
    lv = LEAVE.get(u["username"])
    if lv and lv[0] <= local_ts(d, "12:00") <= lv[1]:
        return None                                       # on leave (canon)
    hours = u.get("normal_hours", "")
    if hours.startswith("rotating"):
        team = _shift_team(u)
        if ((d + team) // 2) % 2:
            return None
        night = team % 2 == 1
        a = local_ts(d, "18:00" if night else "06:00") + int(g.integers(-900, 600))
        return a, a + 12 * 3600 + int(g.integers(-300, 1500))
    last = 5 if hours.startswith("Mon-Sat") else 4
    if l.weekday() > last:
        return None
    p = 0.9
    if d in HOLIDAYS:
        p = 0.02
    if -1 <= d < 0:
        p = 0.45
    elif 0 <= d < 4:
        p = 0.12 if u["department"] in ("Finance and Procurement", "Human Resources", "Customer Service", "Legal and Regulatory", "GIS and Planning") else 0.45
    elif 4 <= d < 14:
        p = 0.7
    r_ = g.random()
    if r_ > p and (u["username"], d) not in SESSION_HOST_OVERRIDE:
        return None
    # habits: each person has a usual start (06:00 to 09:00, most between 06:45 and 08:15) and a usual length of day,
    # kept within minutes from day to day; now and then a late start, a morning only or an afternoon only
    x = 2 * G.frac("habit", u["username"]) - 1
    usual = 7.5 + 1.5 * (abs(x) ** 1.6) * (1 if x >= 0 else -1)
    length = (11.0 if hours.startswith("Mon-Sat") else 9.2) + 1.3 * G.frac("habit_len", u["username"])
    a = local_ts(d, "00:00") + int(usual * 3600) + int(g.normal(0, 420)) + (0 if l.weekday() < 5 else 3600)
    b = a + int(length * 3600) + int(g.normal(0, 1300))
    k = g.random()
    if (u["username"], d) not in SESSION_HOST_OVERRIDE:
        if k < 0.05:
            a += int(g.integers(3600, 9000))
        elif k < 0.09:
            b = a + int(g.integers(3 * 3600, 5 * 3600))
        elif k < 0.12:
            a = local_ts(d, "12:00") + int(g.integers(0, 3600))
    return a, max(b, a + int(2.5 * 3600))


def on_shift(u, t):
    for d in (G.day_utc(t) - 1, G.day_utc(t), G.day_utc(t) + 1):
        w = workday(u, d)
        if w and w[0] <= t < w[1]:
            return True
    return False


def _desk_visitor(d, _cache={}):
    """Who works at the shared desk in the administration wing on local day d: field and service-centre staff who are at
    headquarters for the day (about one working day in three), nobody once the machine is gone."""
    if d not in _cache:
        who = None
        if d != -15 and local_ts(d, "23:00") < G.WS04_REMOVED and int(G.hsh("desk", d, n=4), 16) % 100 < 34:
            c = sorted(u["username"] for u in USERS if u["department"] in ("Field Services", "Water Distribution", "Facilities and Fleet", "Customer Service", "Water Quality")
                       and not u.get("normal_hours", "").startswith("rotating") and u.get("normal_hosts") and workday(u, d))
            who = c[int(G.hsh("deskw", d, n=6), 16) % len(c)] if c else None
        _cache[d] = who
    return _cache[d]


def interactive_sessions(d, _cache={}):
    """Ordinary interactive logons that start on LOCAL day d: list of dicts
    {host, user, logon, logoff, lock_unlock:[(lock, unlock), ...]}. One per person at work: office staff on
    their own workstation, shift staff one per console (the consoles of their group are shared out among the
    people on shift; anyone left over has no console session). Every generator that needs to know who was
    logged on where uses this, so that logons, DHCP, proxy user names and process owners agree."""
    if d in _cache:
        return _cache[d]
    out, taken = [], {}
    for u in sorted(USERS, key=lambda x: x["username"]):
        w = workday(u, d)
        nh = u.get("normal_hosts") or []
        if not w or not nh:
            continue
        g = rng("session", u["username"], d)
        a, b = w
        if u.get("normal_hours", "").startswith("rotating") and len(nh) > 1:
            night = _shift_team(u) % 2
            free = [h for h in nh if (h, night) not in taken]
            if not free:
                continue
            host = free[(d + _shift_team(u)) % len(free)]
            taken[(host, night)] = u["username"]
        else:
            host = nh[0]
        host = SESSION_HOST_OVERRIDE.get((u["username"], d), host)
        if u["username"] == _desk_visitor(d):
            host = G.WS04
        locks, t = [], a + int(g.integers(1800, 7200))
        lunch = None
        if not u.get("normal_hours", "").startswith("rotating") and g.random() < 0.85:      # most people lock up for lunch
            lt = local_ts(day_of(a), "11:30") + int(g.integers(0, 5400))
            if a + 3600 < lt < b - 3600:
                lunch = (lt, lt + int(g.integers(1200, 3900)))
        while t < b - 1800:
            away = int(g.integers(240, 3300))
            if lunch and t < lunch[1] and t + away > lunch[0] - 600:
                t = lunch[1] + int(g.integers(1500, 5400))
                continue
            locks.append((t, t + away))
            t += away + int(g.integers(2400, 9000))
        if lunch:
            locks = sorted(locks + [lunch])
        out.append({"host": host, "user": u["username"], "logon": a, "logoff": b, "lock_unlock": locks})
    _cache[d] = out
    return out


def sessions_at(t):
    """Interactive sessions open at epoch t."""
    ld = day_of(t)
    return [s for d in (ld - 1, ld) for s in interactive_sessions(d) if s["logon"] <= t < s["logoff"]]


def user_on(host, t):
    """User name interactively logged on to a host at time t, or None."""
    for s in sessions_at(t):
        if s["host"] == host:
            return s["user"]
    return None


# ---- delivered logs -------------------------------------------------------------------------------------
def zeek_day(d, name):
    """Rows of one delivered Zeek log for UTC day d as dicts (values are strings). Empty list if absent."""
    p = os.path.join(ROOT, NET, "zeek", day_str(d), name + ".log")
    if not os.path.exists(p):
        return []
    rows, fields = [], None
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#fields"):
                fields = line.rstrip("\n").split("\t")[1:]
            elif not line.startswith("#"):
                rows.append(dict(zip(fields, line.rstrip("\n").split("\t"))))
    return rows


def siem_by_day():
    """Yield (d, [alert dicts]) for every UTC day in order, from the delivered alert files."""
    cur, buf = None, []
    for p in sorted(glob.glob(os.path.join(ROOT, NET, "siem", "siem_alerts_*.csv"))):
        with open(p, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["t"] = ts(r["time_utc"])
                d = G.day_utc(r["t"])
                if d != cur:
                    if buf:
                        yield cur, buf
                    cur, buf = d, []
                buf.append(r)
    if buf:
        yield cur, buf


def audit(name):
    """Rows of a delivered audit table (network_logs/audit/<name>.csv) as dicts."""
    with open(os.path.join(ROOT, NET, "audit", name + ".csv"), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def months():
    """[(YYYY-MM, start epoch, end epoch)] covering the span of this family."""
    return G.months()


def write_jsonl_parts(rel_prefix, objs, max_bytes=40_000_000):
    """Write objects as JSON Lines to <rel_prefix>.jsonl, or <rel_prefix>_01.jsonl, _02 ... when one file
    would exceed max_bytes. Returns (files, rows)."""
    lines = [json.dumps(o, ensure_ascii=False, separators=(",", ":")) for o in objs]
    parts, cur, size = [], [], 0
    for ln in lines:
        if cur and size + len(ln) + 1 > max_bytes:
            parts.append(cur)
            cur, size = [], 0
        cur.append(ln)
        size += len(ln.encode("utf-8")) + 1
    if cur or not parts:
        parts.append(cur)
    for old in glob.glob(os.path.join(ROOT, rel_prefix + "*.jsonl")):
        os.remove(old)
    for i, part in enumerate(parts):
        rel = f"{rel_prefix}.jsonl" if len(parts) == 1 else f"{rel_prefix}_{i + 1:02d}.jsonl"
        p = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(part) + ("\n" if part else ""))
    return len(parts), len(lines)
