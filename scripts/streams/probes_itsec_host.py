"""Stream descriptions and probes for the raw host logs (see scripts/check_streams.py):
windows_event_logs, endpoint_telemetry, host_triage.

Every probe reads the files on disk. The story probes are keyed by the canon event they make visible; the
invariant probes ("INV-...") check that the host logs agree with the delivered alerts, audit tables and
Zeek logs, record by record.

    python3 scripts/streams/probes_itsec_host.py        run every probe and print the result
"""
import bisect
import calendar
import collections
import csv
import glob
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import itsec_shared as S
import itsec_host_model as Mo
import gen_itsec_host as GH
import itsec_zeek_extra as ZX
from common import ROOT, ts, iso

G, M = S.G, S.M
NET = os.path.join(ROOT, "05_other_sources", "network_logs")
IP, WIN, WIN_IP = Mo.IP, Mo.WIN, Mo.WIN_IP
JMP, WS04, HISTDMZ, SCADA1, OPS02, OT01, HIST1 = Mo.JMP, Mo.WS04, Mo.HISTDMZ, Mo.SCADA1, Mo.OPS02, Mo.OT01, Mo.HIST1
_hc = {}
_c = {}


def pt(s):
    k = s[:13]
    b = _hc.get(k)
    if b is None:
        b = _hc[k] = calendar.timegm((int(s[:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), 0, 0))
    return b + int(s[14:16]) * 60 + float(s[17:23])


def near(lst, t, before, after):
    """True if the sorted list has a value in [t - before, t + after]."""
    i = bisect.bisect_left(lst, t - before)
    return i < len(lst) and lst[i] <= t + after


def count_in(lst, a, b):
    return bisect.bisect_right(lst, b) - bisect.bisect_left(lst, a)


# ---- what kind of record is this? (for the probe that nothing in the story's records is one of a kind) ------
def pclass(p):
    """Coarse location of a path: profile, programdata, programfiles, windows, system, other."""
    q = (p or "").lower()
    if q == "system":
        return "system"
    for pre, name in (("c:\\users\\", "profile"), ("c:\\programdata\\", "programdata"), ("c:\\program files", "programfiles"), ("c:\\windows\\", "windows")):
        if q.startswith(pre):
            return name
    return "other"


def ext(p):
    return p.rsplit(".", 1)[-1].lower() if "." in p.rsplit("\\", 1)[-1] else ""


def edr_feats(o):
    et, who = o["event_type"], ("system" if o["user"] == "SYSTEM" else "person")
    out = [("edr", et, who, pclass(o["image"]))]
    if et == "process_start":
        out.append(("edr-start", who, pclass(o["image"]), o["signer"] == "", o["parent_image"].rsplit("\\", 1)[-1].lower()))
    elif et == "file_create":
        out.append(("edr-file", who, pclass(o["image"]), pclass(o["path"]), ext(o["path"])))
    elif et == "service_install":
        out.append(("edr-svc", who, pclass(o["image"]), pclass(o["service_image"]), o["start_type"]))
    elif et == "network_connect":
        out.append(("edr-net", who, pclass(o["image"]), o["dst_port"], o["protocol"]))
    elif et == "dns_query":
        out.append(("edr-dns", who, pclass(o["image"]), o["rcode"]))
    return out


def win_feats(o):
    eid = o["event_id"]
    out = [("win", o["channel"], eid)]
    if eid in (4624, 4634, 4625):
        out.append(("win-logon", eid, o.get("logon_type"), o.get("domain", "")))
    elif eid in (5140, 5145):
        out.append(("win-share", eid, o["share"], o.get("access", ""), ext(o.get("path", ""))))
    elif eid in (4768, 4769, 4771):
        out.append(("win-ticket", eid, o.get("service", "").split("/")[0], o.get("status", "")))
    elif eid == 7045:
        out.append(("win-svc", pclass(o["image_path"]), o["service_type"], o["start_type"], o["account"]))
    elif eid in (5000, 5001):
        out.append(("win-defender", eid, o.get("detail", ""), o.get("user", "") == "SYSTEM"))
    return out


_STORY_IPS = {s_["ip"] for s_ in G.SESSIONS}
_STORY_WIN = [(s_["start"] - 60, s_["start"] + s_["dur"] + 60) for s_ in G.SESSIONS]


def edr_story(o):
    if o["host"] != WS04:
        return False
    img, pth = o["image"], o.get("path", "")
    return img == Mo.VST_PATH or img.endswith("\\" + Mo.ATT_NAME) or pth == Mo.VST_PATH or Mo.ZIP_NAME in pth or pth.startswith(GH.STAGE_DIR) \
        or o.get("service_image") == Mo.VST_PATH


def win_story(o, t):
    h, u = o["host"], o.get("user", "")
    if h == WS04 and (o.get("image_path") == Mo.VST_PATH or (o["event_id"] == 5001 and abs(t - G.AV_OFF_T) < 2)):
        return True
    if u == "rvela" and (h == HISTDMZ or o["event_id"] == 4769) and S.LEAVE["rvela"][0] <= t <= S.LEAVE["rvela"][1]:
        return True
    return u == "GW-ENG-VELA" and any(a <= t <= b for a, b in _STORY_WIN)


# ---- one pass over each stream ----------------------------------------------------------------------------
def win():
    if "win" in _c:
        return _c["win"]
    D = collections.defaultdict
    x = {"f4625": D(list), "l4624": D(list), "l4634": D(list), "e4740": D(list), "grp": D(list), "s5145": D(list), "s5140": D(list), "tick": D(list),
         "defender": D(list), "sys": D(list), "hosts": set(), "users": set(), "keys": set(), "tmin": 1e18, "tmax": 0, "rid_bad": 0, "n": collections.Counter(),
         "logon_iv": {}, "lo_end": {}, "down": D(list), "all_t": D(list), "dup_lid": 0, "order": D(set), "f4771": D(list), "feat": collections.Counter(),
         "story": [], "ws04_last": 0, "grp_nouser": 0}
    last = {}
    for fp in sorted(glob.glob(os.path.join(NET, "windows", "*.jsonl"))):
        ch = os.path.basename(fp).split("_")[0]
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                o = json.loads(line)
                t, h, eid = pt(o["time_utc"]), o["host"], o["event_id"]
                x["n"][(ch, eid)] += 1
                x["hosts"].add(h)
                x["keys"].update(o.keys())
                x["tmin"], x["tmax"] = min(x["tmin"], t), max(x["tmax"], t)
                k = (h, ch)
                if k in last and not (o["record_id"] > last[k][0] and t >= last[k][1]):
                    x["rid_bad"] += 1
                last[k] = (o["record_id"], t)
                u = o.get("user")
                x["order"][eid].add(tuple(k_ for k_ in o if k_ not in ("src_ip", "process", "src_host")))
                if h == WS04:
                    x["ws04_last"] = max(x["ws04_last"], t)
                st_ = win_story(o, t)
                for f_ in win_feats(o):
                    if st_:
                        x["story"].append(f_)
                    else:
                        x["feat"][f_] += 1
                if u:
                    x["users"].add(u)
                if o.get("target_user"):
                    x["users"].add(o["target_user"])
                if ch == "security":
                    if eid == 4625:
                        x["f4625"][(h, u)].append(t)
                    elif eid == 4624:
                        x["l4624"][(h, u)].append((t, o["logon_type"], o.get("src_ip", ""), o["logon_id"]))
                        if (h, o["logon_id"]) in x["logon_iv"]:
                            x["dup_lid"] += 1
                        x["logon_iv"][(h, o["logon_id"])] = [u, t, 1e18]
                    elif eid == 4634:
                        x["l4634"][(h, u)].append(t)
                        iv = x["logon_iv"].get((h, o["logon_id"]))
                        if iv:
                            iv[2] = t
                        else:
                            x["lo_end"][(h, o["logon_id"])] = (u, t)
                    elif eid == 4740:
                        x["e4740"][(o["target_user"], o["caller_computer"])].append(t)
                    elif eid in (4728, 4732, 4756):
                        x["grp"][u].append(t)
                        x["grp_nouser"] += not u
                    elif eid == 4771:
                        x["f4771"][u].append(t)
                    elif eid == 5145:
                        x["s5145"][h].append((t, u, o["share"], o["path"], o["access"], o.get("src_ip", "")))
                    elif eid == 5140:
                        x["s5140"][h].append((t, u, o["share"], o.get("src_ip", "")))
                    elif eid in (4768, 4769, 4771):
                        x["tick"][(h, o.get("src_ip", ""))].append((t, eid, u, o.get("service", "")))
                elif ch == "defender":
                    x["defender"][(h, eid)].append((t, u or ""))
                else:
                    x["sys"][(h, eid)].append((t, o.get("service_name", ""), o.get("image_path", ""), o.get("state", "")))
                    if eid == 6006:
                        x["down"][h].append([t, None])
                    elif eid == 6005 and x["down"][h] and x["down"][h][-1][1] is None:
                        x["down"][h][-1][1] = t
                x["all_t"][h].append(t)
    for v in x["all_t"].values():
        v.sort()
    for k in ("f4625", "l4634", "e4740", "grp", "f4771"):
        for v in x[k].values():
            v.sort()
    _c["win"] = x
    return x


def edr():
    if "edr" in _c:
        return _c["edr"]
    D = collections.defaultdict
    x = {"nc": D(list), "dq": D(list), "usb": D(list), "ps": D(list), "owned": [], "svc": D(list), "hosts": set(), "users": set(), "keys": set(),
         "tmin": 1e18, "tmax": 0, "n": collections.Counter(), "ws04": [], "all_t": D(list), "h2": [], "img_starts": collections.Counter(), "img_conn": collections.Counter(),
         "usb_owner": D(set), "usb_n": collections.Counter(), "feat": collections.Counter(), "story": [], "order": D(set)}
    for fp in sorted(glob.glob(os.path.join(NET, "endpoint", "*.jsonl"))):
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                o = json.loads(line)
                t, h, et, u = pt(o["time_utc"]), o["host"], o["event_type"], o["user"]
                x["n"][et] += 1
                x["hosts"].add(h)
                x["users"].add(u)
                x["keys"].update(o.keys())
                x["tmin"], x["tmax"] = min(x["tmin"], t), max(x["tmax"], t)
                x["all_t"][h].append(t)
                x["order"][et].add(tuple(o.keys()))
                st_ = edr_story(o)
                for f_ in edr_feats(o):
                    if st_:
                        x["story"].append(f_)
                    else:
                        x["feat"][f_] += 1
                if et == "process_start":
                    x["img_starts"][o["image"]] += 1
                elif et in ("network_connect", "dns_query"):
                    x["img_conn"][o["image"]] += 1
                elif et == "usb_device":
                    x["usb_owner"][o["device_serial"]].add(u if u != "SYSTEM" else h)
                    x["usb_n"][o["device_serial"]] += 1
                if et == "network_connect":
                    x["nc"][(o["src_ip"], o["src_port"], o["dst_ip"], o["dst_port"])].append((t, o["image"], o["pid"]))
                elif et == "dns_query":
                    x["dq"][(h, o["query"])].append(t)
                elif et == "usb_device":
                    x["usb"][h].append(t)
                elif et == "process_start":
                    x["ps"][(h, o["pid"], o["image"])].append(t)
                elif et == "service_install":
                    x["svc"][(h, o["service_name"])].append(t)
                if u != "SYSTEM":
                    x["owned"].append((h, u, t, et, o["pid"], o["image"]))
                if h == WS04:
                    x["ws04"].append((t, o))
    for k in ("dq", "usb", "ps", "svc"):
        for v in x[k].values():
            v.sort()
    for v in x["nc"].values():
        v.sort()
    _c["edr"] = x
    return x


def alerts(rule):
    if "al" not in _c:
        by = collections.defaultdict(list)
        for r in Mo.alerts_between(G.SPAN_START - 86400, G.SPAN_END + 86400, Mo.EVIDENCE_RULES):
            by[r[1]].append(r)
        _c["al"] = by
    return _c["al"][rule]


def conn_all():
    """Delivered conn rows of the whole span, day by day (first ten fields; see conn_x for protocol and uid)."""
    for d in range(S.FIRST_DAY, S.LAST_DAY + 1):
        for r in Mo.conn_day(d):
            yield r[:10]


def conn_x():
    for d in range(S.FIRST_DAY, S.LAST_DAY + 1):
        names = Mo.names_day(d)
        for r in Mo.conn_day(d):
            yield r, names.get(r[11], "")


def res(bad, total, what, examples):
    ok = bad == 0 and total > 0
    return ok, f"{total - bad:,} of {total:,} {what}" + ("" if ok else f"; e.g. {examples[:3]}")


# ---- invariants: Windows event logs ------------------------------------------------------------------------
def inv_bursts():
    w, bad, ex, n = win(), 0, [], 0
    for t, rule, host, sip, dst, user, detail, aid in alerts("FAILED_LOGON_BURST"):
        if host not in WIN:
            continue
        n += 1
        want = int(re.search(r"failures=(\d+)", detail).group(1))
        got = count_in(w["f4625"].get((host, user), []), t - 300, t + 1)
        if got != want:
            bad += 1
            ex.append((aid, want, got))
    return res(bad, n, "failed-logon bursts have exactly the stated number of 4625 events in the 300 s before the alert", ex)


def inv_lockout():
    w, bad, ex, n = win(), 0, [], 0
    for t, rule, host, sip, dst, user, detail, aid in alerts("ACCOUNT_LOCKOUT"):
        n += 1
        if not near(w["e4740"].get((user, host), []), t, 2.5, 1) or not near(w["f4625"].get((host, user), []), t, 1800, 1) or \
                count_in(w["f4771"].get(user, []), t - 1800, t + 1) < 3:
            bad += 1
            ex.append(aid)
    return res(bad, n, "lockout alerts have a 4740 on a domain controller, at least three failed pre-authentications (4771) there and failed logons on the machine", ex)


def inv_ooh():
    w, bad, ex, n = win(), 0, [], 0
    for t, rule, host, sip, dst, user, detail, aid in alerts("LOGON_OUTSIDE_HOURS"):
        n += 1
        if not any(t <= x[0] < t + 1 for x in w["l4624"].get((host, user), [])):
            bad += 1
            ex.append(aid)
    return res(bad, n, "out-of-hours logon alerts have their 4624", ex)


def inv_group():
    w, bad, ex, n = win(), 0, [], 0
    for t, rule, host, sip, dst, user, detail, aid in alerts("ADMIN_GROUP_CHANGE"):
        n += 1
        if not near(w["grp"].get(user, []), t, 1.5, 1):
            bad += 1
            ex.append(aid)
    return res(bad, n, "group-change alerts have a 4728/4732/4756", ex)


def inv_pup():
    w, bad, ex, n = win(), 0, [], 0
    d16 = {k: [x[0] for x in v] for k, v in w["defender"].items() if k[1] in (1116, 1117)}
    for t, rule, host, sip, dst, user, detail, aid in alerts("PUP_DETECTED"):
        n += 1
        if not near(d16.get((host, 1116), []), t, 6, 0) or not near(d16.get((host, 1117), []), t, 1.5, 1):
            bad += 1
            ex.append(aid)
    return res(bad, n, "unwanted-software alerts have Defender 1116 and 1117", ex)


def inv_otwrite():
    w, bad, ex, n = win(), 0, [], 0
    idx = collections.defaultdict(list)
    for t, u, share, path, acc, sip in w["s5145"].get(OT01, []):
        if acc == "WriteData":
            idx[(u, (share.split("\\")[-1] + "\\" + path).lower())].append(t)
    for t, rule, host, sip, dst, user, detail, aid in alerts("OT_FILE_WRITE"):
        if dst != OT01:
            continue
        n += 1
        p = detail.split("path=", 1)[1].lstrip("\\").split("\\", 1)[1].lower()
        if not any(t - 30 <= x < t + 1 for x in idx.get((user, p), [])):
            bad += 1
            ex.append(aid)
    return res(bad, n, "file-write alerts on the engineering file server have a 5145 write with that path and account in the 30 s before", ex)


EP_MAP = {"DEFINITIONS_UPDATED": 2000, "SCAN_COMPLETED": 1001, "REALTIME_PROTECTION_ENABLED": 5000, "REALTIME_PROTECTION_DISABLED": 5001, "THREAT_QUARANTINED": 1117}


def inv_ep():
    w, bad, ex, n = win(), 0, [], 0
    for r in S.audit("endpoint_protection"):
        eid = EP_MAP.get(r["event"])
        if eid is None or r["host"] not in WIN:
            continue
        n += 1
        t = ts(r["time_utc"])
        hit = [x for x in w["defender"].get((r["host"], eid), []) if t <= x[0] < t + 1]
        if not hit or (eid in (5000, 5001) and hit[0][1].lower() != r["initiated_by"].lower()):
            bad += 1
            ex.append((r["time_utc"], r["host"], r["event"]))
    return res(bad, n, "endpoint-protection records have their Defender event (same host, second and initiator)", ex)


def inv_gateway():
    w, bad, ex = win(), 0, []
    rows = S.audit("remote_access_sessions")
    lg = w["l4624"]
    for r in rows:
        a, b = ts(r["login_utc"]), ts(r["logout_utc"])
        ok = any(a <= x[0] < a + 1 and x[1] == 10 and x[2] == r["src_ip"] for x in lg.get((JMP, r["account"]), []))
        ok = ok and any(b <= x < b + 1 for x in w["l4634"].get((JMP, r["account"]), []))
        if not ok:
            bad += 1
            ex.append(r["session_id"])
    return res(bad, len(rows), "remote-access sessions have their logon and logoff on the gateway (account and source address)", ex)


def inv_rdp():
    w, bad, ex, n = win(), 0, [], 0
    by = collections.defaultdict(list)
    for (h, u), v in w["l4624"].items():
        for t, lt, sip, lid in v:
            if lt == 10:
                by[(h, sip)].append(t)
    for v in by.values():
        v.sort()
    for t, o, op, r, rp, svc, dur, ob, rb, state in conn_all():
        if rp != 3389 or state != "SF" or r not in WIN_IP or o not in WIN_IP:
            continue
        if WIN_IP[o] == JMP and Mo.gw_session(t, WIN_IP[r]) is None:
            continue
        if not Mo.is_up(WIN_IP[r], t + 0.8):
            continue
        n += 1
        if not near(by.get((WIN_IP[r], o), []), t + 0.8, 0.6, 1.2):
            bad += 1
            ex.append((iso(t), o, r))
    return res(bad, n, "remote-desktop flows have a type 10 logon on the target from the source address", ex)


def inv_fim():
    w, bad, ex, n = win(), 0, [], 0
    idx = collections.defaultdict(list)
    for t, u, share, path, acc, sip in w["s5145"].get(OT01, []):
        idx[(u, (share.split("\\")[-1] + "\\" + path).lower())].append(t)
    for r in S.audit("file_integrity"):
        n += 1
        t = ts(r["time_utc"])
        p = r["path"].lstrip("\\").split("\\", 1)[1].lower()
        if not any(t <= x < t + 1 for x in idx.get((r["user"], p), [])):
            bad += 1
            ex.append((r["time_utc"], r["path"]))
    return res(bad, n, "file-integrity records have a 5145 write with that path and account", ex)


def inv_krb():
    w, bad, ex, n = win(), 0, [], 0
    tk = {k: sorted(x[0] for x in v) for k, v in w["tick"].items()}
    dcs = set(S.DCS) | set(S.OT_DCS)
    for t, o, op, r, rp, svc, dur, ob, rb, state in conn_all():
        if rp not in (88, 389) or state != "SF" or WIN_IP.get(r) not in dcs or o not in WIN_IP:
            continue
        n += 1
        if not near(tk.get((WIN_IP[r], o), []), t, 0.5, 1):
            bad += 1
            ex.append((iso(t), o, r, rp))
    return res(bad, n, "Kerberos and LDAP flows to a domain controller have a 4768/4769 there", ex)


def inv_records():
    w, e = win(), edr()
    bad, ex = w["rid_bad"], []
    silent = 0
    for h, wins in w["down"].items():
        for a, b in wins:
            if b is None:
                continue
            for lst in (w["all_t"][h], e["all_t"].get(h, [])):
                k = count_in(lst, a + 0.5, b - 0.01)
                if k:
                    silent += k
                    ex.append((h, iso(a)))
    ok = bad == 0 and silent == 0
    npairs = sum(1 for v in w["down"].values() for a, b in v if b)
    return ok, f"record ids rise with time on every host and channel ({bad} breaks); {npairs} shutdown-to-start windows with {silent} events inside" + ("" if ok else f"; e.g. {ex[:3]}")


def registry_accounts():
    acc = {u["username"] for u in S.USERS} | set(Mo.OT_ACCT.values()) | set(Mo.SVC) | {"SYSTEM"}
    return acc | {h + "$" for h in WIN}


def inv_ids_win():
    w = win()
    unk_h = sorted(w["hosts"] - set(WIN))
    unk_u = sorted(w["users"] - registry_accounts())
    return not unk_h and not unk_u, f"{len(w['hosts'])} hosts and {len(w['users'])} accounts, all in the registry" if not unk_h and not unk_u else f"unknown hosts {unk_h[:5]} accounts {unk_u[:5]}"


# ---- invariants: endpoint telemetry ------------------------------------------------------------------------
def inv_flows():
    """Every tcp/udp flow the sensor logged from a Windows host has a network_connect, except the half of ordinary
    web browsing that the agent's records leave out (the same deterministic half the generator leaves out)."""
    e, bad, ex, n, kept, site, extra = edr(), 0, [], 0, 0, 0, 0
    for (t, o, op, r, rp, svc, dur, ob, rb, state, proto, uid), name in conn_x():
        if o not in WIN_IP or svc == "dns" or proto not in ("tcp", "udp") or not Mo.is_up(WIN_IP[o], t + 0.2):
            continue
        hit = any(abs(x[0] - t) <= 0.5 for x in e["nc"].get((o, op, r, rp), []))
        if name in G.SITE_IPS:
            site += 1
            want = GH.keep_flow(name, uid)
            kept += want
            if hit != want:
                bad += 1
                ex.append((iso(t), o, op, r, rp, "kept" if hit else "missing"))
            continue
        n += 1
        if not hit:
            bad += 1
            ex.append((iso(t), o, op, r, rp))
    share = kept / max(1, site)
    ok, msg = res(bad, n + site, "delivered flows from Windows hosts are recorded as the rule says", ex)
    return ok and 0.45 < share < 0.55, msg + f" ({n:,} recorded in full; of {site:,} ordinary browsing flows {kept:,} kept, {100 * share:.1f} %)"


def inv_dns():
    e, bad, ex, n, site, kept = edr(), 0, [], 0, 0, 0
    for d in range(S.FIRST_DAY, S.LAST_DAY + 1):
        for t, o, r, q, ans, rc in Mo.dns_day(d):
            if o not in WIN_IP or not Mo.is_up(WIN_IP[o], t):
                continue
            hit = near(e["dq"].get((WIN_IP[o], q), []), t, 0.5, 0.5)
            want = GH.keep_lookup(o, q, t)
            if q in G.SITE_IPS:
                site += 1
                kept += want
                if not want:
                    continue                  # a neighbouring lookup of the same name may be kept
            n += 1
            if not hit:
                bad += 1
                ex.append((iso(t), o, q))
    ok, msg = res(bad, n, "delivered DNS lookups from Windows hosts that the agent keeps have a dns_query", ex)
    return ok and 0.45 < kept / max(1, site) < 0.55, msg + f" ({kept:,} of {site:,} lookups for ordinary browsing kept)"


def inv_usb():
    e, bad, ex, n = edr(), 0, [], 0
    for t, rule, host, sip, dst, user, detail, aid in alerts("USB_STORAGE_MOUNTED"):
        n += 1
        if not near(e["usb"].get(host, []), t, 2, 1):
            bad += 1
            ex.append(aid)
    return res(bad, n, "removable-storage alerts have a usb_device event", ex)


def inv_session():
    """Every event owned by a person lies inside a logon of that account on that host (per the Security log),
    and its process was started inside the same logon."""
    w, e = win(), edr()
    iv = collections.defaultdict(list)
    for (h, lid), (u, a, b) in w["logon_iv"].items():
        iv[(h, u)].append((a, b))
    for v in iv.values():
        v.sort()
    bad, ex, nostart = 0, [], 0
    for h, u, t, et, pid, img in e["owned"]:
        ok = False
        for a, b in iv.get((h, u), []):
            if a <= t <= b + 2:
                ok = True
                if et != "process_start" and img != "System" and not any(a <= x <= t for x in e["ps"].get((h, pid, img), [])):
                    nostart += 1
                    if len(ex) < 6:
                        ex.append(("no process_start", h, u, iso(t), img.rsplit("\\", 1)[-1]))
                break
        if not ok:
            bad += 1
            if len(ex) < 6:
                ex.append(("outside a logon", h, u, iso(t), et))
    n = len(e["owned"])
    good = bad == 0 and nostart == 0 and n > 0
    return good, f"{n - bad:,} of {n:,} person-owned endpoint events lie inside a logon of that account on that host; {nostart} without a process start in that logon" + ("" if good else f"; e.g. {ex[:4]}")


def inv_service():
    w, e = win(), edr()
    bad, ex, n = 0, [], 0
    for (h, eid), v in w["sys"].items():
        if eid != 7045:
            continue
        for t, name, img, st in v:
            n += 1
            if not near(e["svc"].get((h, name), []), t, 1, 1):
                bad += 1
                ex.append((h, name))
    m = sum(len(v) for v in e["svc"].values())
    ok = bad == 0 and m == n and n > 0
    return ok, f"{n - bad:,} of {n:,} service registrations in the System log have the agent's service_install ({m:,} agent records)" + ("" if ok else f"; e.g. {ex[:3]}")


def inv_ids_edr():
    e = edr()
    unk_h = sorted(e["hosts"] - set(WIN))
    unk_u = sorted(e["users"] - registry_accounts())
    return not unk_h and not unk_u, f"{len(e['hosts'])} hosts and {len(e['users'])} accounts, all in the registry" if not unk_h and not unk_u else f"unknown hosts {unk_h[:5]} accounts {unk_u[:5]}"


def inv_logons():
    w = win()
    ok4, fail = w["n"][("security", 4624)], w["n"][("security", 4625)]
    multi = {k: len(v) for k, v in w["order"].items() if len(v) > 1}
    good = w["dup_lid"] == 0 and ok4 > 1.5 * fail and not multi and w["grp_nouser"] == 0
    return good, (f"{ok4:,} successful logons, each with its own logon id ({w['dup_lid']} repeats), against {fail:,} failed ones; one field order per event id "
                  f"({len(multi)} event ids with more than one); group changes without a subject account: {w['grp_nouser']}")


def inv_shares():
    w = win()
    rd = collections.Counter()
    for h, v in w["s5145"].items():
        for x in v:
            rd[(h, x[4])] += 1
    hosts = {h for (h, a), k in rd.items() if a == "ReadData" and k >= 100}
    arc = {x[1] for x in w["s5145"].get(HISTDMZ, []) if x[3].startswith("archive\\")}
    ok = len(hosts) >= 5 and len(arc) >= 4
    return ok, f"share reads (5145 ReadData) on {len(hosts)} servers, {sum(k for (h, a), k in rd.items() if a == 'ReadData'):,} in all; {len(arc)} accounts read archive files from the replica's export share"


def inv_removed():
    w, e = win(), edr()
    last = max(w["ws04_last"], max((t for t, o in e["ws04"]), default=0))
    return last < G.WS04_REMOVED, f"last record of any kind from the removed workstation: {iso(int(last))} (removed {iso(G.WS04_REMOVED)})"


def inv_images():
    e = edr()
    st, cn = e["img_starts"], e["img_conn"]
    never = sorted(k for k in cn if k != "System" and st[k] == 0)
    once_ = sum(1 for v in st.values() if v == 1)
    vst, att = st[Mo.VST_PATH], [v for k, v in st.items() if k.endswith(Mo.ATT_NAME)]
    rarer = sum(1 for v in st.values() if v <= vst)
    ok = len(st) >= 300 and once_ >= 100 and not never and rarer >= 100
    return ok, (f"{len(st):,} distinct process images, {once_:,} started once; images that connect but never start: {len(never)}; the service binary of the story starts "
                f"{vst} times and {rarer:,} images start as rarely or more rarely")


def inv_usb_owner():
    e = edr()
    per = collections.Counter()
    shared = 0
    for ser, owners in e["usb_owner"].items():
        people = {o for o in owners if not o.startswith("GW-")}
        shared += len(people) > 1
        for o in people:
            per[o] += 1
    rep_ = sum(1 for v in e["usb_n"].values() if v > 1)
    ok = shared == 0 and max(per.values(), default=0) <= 3 and rep_ > len(e["usb_n"]) * 0.5
    return ok, f"{len(e['usb_n']):,} removable drives in {sum(e['usb_n'].values()):,} insertions; {rep_:,} drives seen more than once; at most {max(per.values(), default=0)} drives per person; drives used by two people: {shared}"


def inv_not_unique():
    """Every kind of record that the story's events belong to also occurs, at least three times, among other events."""
    w, e = win(), edr()
    lone = sorted({f for f in e["story"] if e["feat"][f] < 3} | {f for f in w["story"] if w["feat"][f] < 3}, key=str)
    n = len(set(e["story"])) + len(set(w["story"]))
    return not lone and n > 15, f"{n} kinds of record among the story's {len(e['story']) + len(w['story']):,} feature observations; kinds seen fewer than three times elsewhere: {len(lone)}" + (f" {lone[:6]}" if lone else "")


# ---- the records fixed by the delivered mail, flow and audit rows -------------------------------------------
def p_h1_edr():
    e = edr()
    ev = [o for t, o in e["ws04"]]
    u = G.WS04_USER["username"]
    dl = GH.story_flows()[0]
    zp = [o for o in ev if o["event_type"] == "file_create" and o["path"].endswith("\\" + Mo.ZIP_NAME)]
    att = [o for o in ev if o["event_type"] == "file_create" and o["path"].endswith("\\" + Mo.ATT_NAME)]
    run = [o for o in ev if o["event_type"] == "process_start" and o["image"].endswith("\\" + Mo.ATT_NAME)]
    if not zp or not att or not run:
        return False, "archive, extracted file or its start missing on the workstation"
    z_, a, r = zp[0], att[0], run[0]
    ok1 = "OUTLOOK" in z_["image"] and a["image"].lower().endswith("explorer.exe") and r["parent_image"].lower().endswith("explorer.exe") and r["signer"] == "" and r["user"] == u \
        and G.LURE_T < pt(z_["time_utc"]) < pt(a["time_utc"]) < pt(r["time_utc"]) < G.AV_OFF_T and "Temp1_" + Mo.ZIP_NAME in a["path"]
    dq = [o for o in ev if o["event_type"] == "dns_query" and o["query"] == "update-cdn.meridiancontrols.net" and o["pid"] == r["pid"] and abs(pt(o["time_utc"]) - G.DNS_Q_T) < 1.5]
    nc = [o for o in ev if o["event_type"] == "network_connect" and o["dst_ip"] == G.BEACON_IP and o["pid"] == r["pid"] and abs(pt(o["time_utc"]) - dl[0]) <= 0.5]
    vf = [o for o in ev if o["event_type"] == "file_create" and o["path"] == Mo.VST_PATH and o["size"] == Mo.VST_SIZE and 0.97 * dl[8] < o["size"] < dl[8]]
    sv = [o for o in ev if o["event_type"] == "service_install" and o["service_image"] == Mo.VST_PATH]
    st = [o for o in ev if o["event_type"] == "process_start" and o["image"] == Mo.VST_PATH]
    want = [(t, o, op) for t, o, op, r_, rp, svc, dur, ob, rb, state in conn_all() if o == IP[WS04] and r_ == G.BEACON_IP and abs(t - dl[0]) > 5]
    got = 0
    for t, o, op in want:
        if any(abs(x[0] - t) <= 0.5 and x[1] == Mo.VST_PATH and e["ps"].get((WS04, x[2], Mo.VST_PATH)) for x in e["nc"].get((o, op, G.BEACON_IP, 443), [])):
            got += 1
    ok = ok1 and dq and nc and vf and sv and st and got == len(want) and len(want) > 100 and pt(vf[0]["time_utc"]) > dl[0] + dl[6]
    return bool(ok), (f"archive written {z_['time_utc']} by the mail client, file extracted {a['time_utc']} by the shell and started {r['time_utc']} (unsigned); lookup and "
                      f"connection by that process; second file {vf[0]['time_utc'] if vf else '-'} ({Mo.VST_SIZE:,} bytes, in a download of {dl[8]:,}); service registered; {len(st)} starts of the service binary; "
                      f"{got} of {len(want)} later connections to the same address carry its image")


def p_h1_win():
    w = win()
    d = [x for x in w["defender"].get((WS04, 5001), []) if G.AV_OFF_T <= x[0] < G.AV_OFF_T + 1]
    s = [x for x in w["sys"].get((WS04, 7045), []) if x[2] == Mo.VST_PATH and G.DNS_Q_T < x[0] < G.DNS_Q_T + 200]
    u = G.WS04_USER["username"]
    lg = [x for x in w["l4624"].get((WS04, u), []) if x[0] < G.LURE_T and x[1] == 2]
    ok = bool(d) and d[0][1] == u and bool(s) and bool(lg)
    return ok, f"logon of {u} {iso(lg[-1][0]) if lg else '-'}; Defender 5001 by {d[0][1] if d else '-'} at {iso(d[0][0]) if d else '-'}; System 7045 '{s[0][1] if s else '-'}' at {iso(s[0][0]) if s else '-'}"


def p_h2_win():
    w = win()
    h2 = GH.story_flows()[1]
    t = h2[0]
    lg = [x for x in w["l4624"].get((HISTDMZ, "rvela"), []) if abs(x[0] - t) < 2 and x[1] == 3 and x[2] == IP[WS04]]
    rd = [x for x in w["s5145"].get(HISTDMZ, []) if x[1] == "rvela" and x[4] == "ReadData" and t < x[0] < t + h2[6] + 5]
    sh = [x for x in w["s5140"].get(HISTDMZ, []) if x[1] == "rvela" and abs(x[0] - t) < 3]
    lo = [x for x in w["l4634"].get((HISTDMZ, "rvela"), []) if t + h2[6] - 5 < x < t + h2[6] + 15]
    tk = [x for v in w["tick"].values() for x in v if x[1] == 4769 and x[2] == "rvela" and "hist-dmz" in x[3] and abs(x[0] - t) < 3]
    a, b = S.LEAVE["rvela"]
    other = sorted({(h, iso(x[0])) for (h, u), v in w["l4624"].items() if u in ("rvela", "GW-ENG-VELA") for x in v
                    if a < x[0] < b and not (h == HISTDMZ and abs(x[0] - t) < 2) and x[2] not in _STORY_IPS and x[2] != IP[JMP]})
    ok = bool(lg) and len(rd) >= 5 and bool(sh) and bool(lo) and bool(tk) and not other
    return ok, (f"replica: network logon of rvela from {IP[WS04]} at {iso(lg[0][0]) if lg else '-'}, {len(sh)} share open, {len(rd)} reads, logoff {iso(lo[0]) if lo else '-'}; "
                f"DC ticket {len(tk)}; other logons of that person's accounts during the leave, apart from the gateway sessions: {len(other)}" + (f" e.g. {other[:3]}" if other else ""))


def p_h2_edr():
    e = edr()
    h2 = GH.story_flows()[1]
    t = h2[0]
    hit = [x for k, v in e["nc"].items() if k[0] == IP[WS04] and k[2] == IP[HISTDMZ] and k[3] == 445 for x in v if abs(x[0] - t) <= 0.5]
    st = [o for tt, o in e["ws04"] if o["event_type"] == "file_create" and o["path"].startswith(GH.STAGE_DIR)]
    tot = sum(o["size"] for o in st)
    ok = bool(hit) and hit[0][1] == "System" and 0.98 * h2[8] < tot < h2[8] and all(t < pt(o["time_utc"]) < t + h2[6] + 5 and o["image"] == Mo.VST_PATH for o in st)
    return ok, f"network_connect {IP[WS04]} -> {IP[HISTDMZ]}:445 at {iso(hit[0][0]) if hit else '-'} image {hit[0][1] if hit else '-'}; {len(st)} files written under the service's data folder during the transfer, {tot:,} bytes (the flow carried {h2[8]:,})"


def p_h3_gateway():
    w = win()
    got = 0
    rows = [r for r in S.audit("remote_access_sessions") if r["src_ip"] in _STORY_IPS and r["account"] == "GW-ENG-VELA"]
    for r in rows:
        a, b = ts(r["login_utc"]), ts(r["logout_utc"])
        if any(a <= x[0] < a + 1 and x[1] == 10 and x[2] == r["src_ip"] for x in w["l4624"].get((JMP, "GW-ENG-VELA"), [])) and \
                any(b <= x < b + 1 for x in w["l4634"].get((JMP, "GW-ENG-VELA"), [])):
            got += 1
    return got == 14 and len(rows) == 14, f"{got} of {len(rows)} sessions from outside Texas have their logon (source address) and logoff on the gateway"


def _rdp(host, t0, before=400):
    """Type 10 logons of the engineer's control-network account on a host, from the gateway, in the minutes before t0."""
    w = win()
    return [x for x in w["l4624"].get((host, "GW-ENG-VELA"), []) if t0 - before < x[0] < t0 and x[1] == 10 and x[2] == IP[JMP]]


def p_h3_scada():
    hit = _rdp(SCADA1, M.T["supp_list_d3"], 90)
    return bool(hit), f"type 10 logon on {SCADA1} from the gateway at {iso(hit[0][0]) if hit else '-'}, shortly before the suppression list was extended"


def p_h3_ops(k):
    def f():
        hit = _rdp(OPS02, M.T[k])
        w = win()
        lo = [x for x in w["l4634"].get((OPS02, "GW-ENG-VELA"), []) if M.T[k] < x < M.T[k] + 400]
        return bool(hit) and bool(lo), f"type 10 logon on {OPS02} from the gateway at {iso(hit[-1][0]) if hit else '-'}, logoff {iso(lo[0]) if lo else '-'}"
    return f


def p_h3_file():
    w = win()
    t = M.T["cfg_sub2"]
    lg = [x for x in w["l4624"].get((OT01, "GW-ENG-VELA"), []) if t - 40 < x[0] < t and x[1] == 3 and x[2] == IP[JMP]]
    wr = [x for x in w["s5145"].get(OT01, []) if x[1] == "GW-ENG-VELA" and x[3].lower() == "sub02\\rtu_config_draft.xml" and x[4] == "WriteData" and t <= x[0] < t + 1]
    return bool(lg) and bool(wr), f"{OT01}: network logon from the gateway {iso(lg[0][0]) if lg else '-'}, 5145 write of relayconfigs\\sub02\\rtu_config_draft.xml at {iso(wr[0][0]) if wr else '-'}"


# ---- triage ------------------------------------------------------------------------------------------------
TRI = os.path.join(NET, "triage")
TRI_FILES = ["services", "file_listing", "scheduled_tasks", "autoruns", "execution_history", "logon_history", "installed_software", "network_config"]


def tri_rows(host, name):
    with open(os.path.join(TRI, host, name + ".csv"), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tri_col(host):
    return json.load(open(os.path.join(TRI, host, "collection.json"), encoding="utf-8"))


def p_tri_complete():
    hosts = sorted(os.listdir(TRI)) if os.path.isdir(TRI) else []
    bad = []
    for h in hosts:
        c = tri_col(h)
        for f in TRI_FILES:
            p = os.path.join(TRI, h, f + ".csv")
            if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != c["items"][f + ".csv"]["sha256"]:
                bad.append((h, f))
        for s in c["samples"]:
            p = os.path.join(TRI, h, s["file"])
            if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != s["sha256"]:
                bad.append((h, s["file"]))
    ok = len(hosts) == 14 and not bad and all(h in WIN for h in hosts)
    return ok, f"{len(hosts)} collections, every table present and matching the hash in collection.json, every placeholder's SHA-256 equal to the recorded hash" + ("" if ok else f"; problems {bad[:4]}")


def p_tri_first():
    t = {h: ts(tri_col(h)["collected_utc"]) for h in (JMP, HIST1, WS04)}
    ok = ts("2027-10-02T21:20Z") <= t[JMP] <= ts("2027-10-02T21:45Z") and ts("2027-10-02T21:20Z") <= t[HIST1] <= ts("2027-10-02T21:50Z") and t[WS04] > M.T["isolate"]
    vela = [r for r in tri_rows(JMP, "logon_history") if r["user"] == "GW-ENG-VELA" and r["event_id"] == "4624" and r["src_ip"] in {s["ip"] for s in G.SESSIONS}]
    return ok and len(vela) >= 14, f"gateway collected {iso(t[JMP])}, historian {iso(t[HIST1])}, workstation {iso(t[WS04])}; gateway logon history holds {len(vela)} logons from the 14 sessions' addresses"


def p_tri_agree():
    """The workstation's collection agrees with the event logs: the files, the service, the hashes."""
    e, w = edr(), win()
    fl = {r["path"]: r for r in tri_rows(WS04, "file_listing")}
    sv = [r for r in tri_rows(WS04, "services") if r["image_path"] == Mo.VST_PATH]
    ex = {r["image_path"]: r for r in tri_rows(WS04, "execution_history")}
    ev = [o for t, o in e["ws04"]]
    vf = [o for o in ev if o["event_type"] == "file_create" and o["path"] == Mo.VST_PATH]
    af = [o for o in ev if o["event_type"] == "file_create" and o["path"].endswith("\\" + Mo.ATT_NAME)]
    st = [o for o in ev if o["event_type"] == "file_create" and o["path"].startswith(GH.STAGE_DIR)]
    if not (vf and af and sv and st):
        return False, "file or service records missing"
    okv = fl.get(Mo.VST_PATH, {}).get("sha256") == vf[0]["sha256"] and fl[Mo.VST_PATH]["size_bytes"] == str(vf[0]["size"]) and fl[Mo.VST_PATH]["created_utc"] == vf[0]["time_utc"][:19] + "Z"
    oka = fl.get(af[0]["path"], {}).get("sha256") == af[0]["sha256"]
    okst = all(fl.get(o["path"], {}).get("size_bytes") == str(o["size"]) for o in st)
    s45 = [x for x in w["sys"].get((WS04, 7045), []) if x[2] == Mo.VST_PATH]
    oks = bool(s45) and sv[0]["installed_utc"] == iso(int(s45[0][0]))
    ph = {s["stands_in_for"]: s["sha256"] for s in tri_col(WS04)["samples"]}
    okp = ph.get(Mo.VST_PATH) == vf[0]["sha256"] and ph.get(af[0]["path"]) == af[0]["sha256"]
    oke = Mo.VST_PATH in ex and ex[Mo.VST_PATH]["sha256"] == vf[0]["sha256"]
    lh = tri_rows(WS04, "logon_history")
    n_lh = sum(1 for r in lh if r["event_id"] == "4624")
    ok = okv and oka and okst and oks and okp and oke and n_lh > 0
    return ok, (f"file listing, services, execution history and placeholders agree with the endpoint and System logs (files {okv and oka}, {len(st)} transferred files {okst}, "
                f"service {oks}, placeholders {okp}, executions {oke}); {n_lh} logons in the history")


def p_tri_neutral():
    """Nothing in folder, file or column names differs between collections; every collection carries placeholders."""
    hosts = sorted(os.listdir(TRI))
    sets = {h: sorted(os.listdir(os.path.join(TRI, h))) for h in hosts}
    same = len({tuple(v) for v in sets.values()}) == 1
    heads = {f: {tuple(open(os.path.join(TRI, h, f + ".csv"), encoding="utf-8").readline().strip().split(",")) for h in hosts} for f in TRI_FILES}
    one = all(len(v) == 1 for v in heads.values())
    nph = {h: len(tri_col(h)["samples"]) for h in hosts}
    return same and one and min(nph.values()) >= 2, f"same file set and headers in all {len(hosts)} collections; placeholders per collection {min(nph.values())} to {max(nph.values())}"


def p_tri_times():
    """No file, service, task or logon in a collection is newer than the collection; services installed inside the log span have their 7045."""
    w = win()
    late, n, no45 = [], 0, []
    for h in sorted(os.listdir(TRI)):
        tc = ts(tri_col(h)["collected_utc"])
        for name, cols in (("file_listing", ("created_utc", "modified_utc")), ("services", ("installed_utc",)), ("scheduled_tasks", ("created_utc", "last_run_utc")),
                           ("execution_history", ("first_run_utc", "last_run_utc")), ("logon_history", ("time_utc",)), ("autoruns", ("first_seen_utc",))):
            for r in tri_rows(h, name):
                for c in cols:
                    if r[c]:
                        n += 1
                        if ts(r[c]) > tc:
                            late.append((h, name, r[c]))
        reg = {x[1] for x in w["sys"].get((h, 7045), [])}
        for r in tri_rows(h, "services"):
            if ts(r["installed_utc"]) >= Mo.SPAN_A and r["display_name"] not in reg:
                no45.append((h, r["display_name"]))
    ok = not late and not no45
    return ok, f"{n:,} times in the 14 collections, {len(late)} later than the collection; services installed inside the log span without a 7045: {len(no45)}" + ("" if ok else f"; e.g. {(late + no45)[:3]}")


# ---- stream descriptions ------------------------------------------------------------------------------------
def _tri_times():
    t = [ts(tri_col(h)["collected_utc"]) for h in os.listdir(TRI)]
    return min(t), max(t)


def _tri_cols():
    out = set()
    for f in TRI_FILES:
        out.update(open(os.path.join(TRI, JMP, f + ".csv"), encoding="utf-8").readline().strip().split(","))
    return sorted(out | set(tri_col(JMP).keys()))


STREAMS = {
    "windows_event_logs": {"time_range": lambda: (win()["tmin"], win()["tmax"]), "ids": lambda: win()["hosts"] | win()["users"],
                           "registry_ids": lambda: set(WIN) | registry_accounts(), "public_voice": False, "columns": lambda: sorted(win()["keys"])},
    "endpoint_telemetry": {"time_range": lambda: (edr()["tmin"], edr()["tmax"]), "ids": lambda: edr()["hosts"] | edr()["users"],
                           "registry_ids": lambda: set(WIN) | registry_accounts(), "public_voice": False, "columns": lambda: sorted(edr()["keys"])},
    "host_triage": {"time_range": _tri_times, "ids": lambda: set(os.listdir(TRI)), "registry_ids": lambda: set(WIN), "public_voice": False, "columns": _tri_cols},
}
PROBES = {
    # records the delivered mail, flow and audit rows imply
    ("GW-EVT-001", "endpoint_telemetry"): p_h1_edr, ("GW-EVT-101", "endpoint_telemetry"): p_h1_edr,
    ("GW-EVT-001", "windows_event_logs"): p_h1_win, ("GW-EVT-101", "windows_event_logs"): p_h1_win,
    ("GW-EVT-002", "windows_event_logs"): p_h2_win, ("GW-EVT-102", "windows_event_logs"): p_h2_win,
    ("GW-EVT-002", "endpoint_telemetry"): p_h2_edr, ("GW-EVT-102", "endpoint_telemetry"): p_h2_edr,
    ("GW-EVT-011", "windows_event_logs"): p_h3_gateway, ("GW-EVT-003", "windows_event_logs"): p_h3_scada,
    ("GW-EVT-103", "windows_event_logs"): p_h3_file, ("GW-EVT-010", "windows_event_logs"): p_h3_file,
    ("GW-EVT-005", "windows_event_logs"): p_h3_ops("sub2_cmd"), ("GW-EVT-007", "windows_event_logs"): p_h3_ops("sub3_cmd"),
    ("GW-EVT-011", "host_triage"): p_tri_first, ("GW-EVT-012", "host_triage"): p_tri_agree,
    # invariants
    ("INV-BURSTS", "windows_event_logs"): inv_bursts, ("INV-LOCKOUT", "windows_event_logs"): inv_lockout, ("INV-OUTSIDE-HOURS", "windows_event_logs"): inv_ooh,
    ("INV-GROUP", "windows_event_logs"): inv_group, ("INV-UNWANTED-SOFTWARE", "windows_event_logs"): inv_pup, ("INV-FILE-WRITE", "windows_event_logs"): inv_otwrite,
    ("INV-ENDPOINT-PROTECTION", "windows_event_logs"): inv_ep, ("INV-GATEWAY", "windows_event_logs"): inv_gateway, ("INV-REMOTE-DESKTOP", "windows_event_logs"): inv_rdp,
    ("INV-FILE-INTEGRITY", "windows_event_logs"): inv_fim, ("INV-TICKETS", "windows_event_logs"): inv_krb, ("INV-RECORDS", "windows_event_logs"): inv_records,
    ("INV-IDS", "windows_event_logs"): inv_ids_win, ("INV-LOGONS", "windows_event_logs"): inv_logons, ("INV-SHARE-READS", "windows_event_logs"): inv_shares,
    ("INV-REMOVED-HOST", "windows_event_logs"): inv_removed, ("INV-NOT-ONE-OF-A-KIND", "windows_event_logs"): inv_not_unique,
    ("INV-IMAGES", "endpoint_telemetry"): inv_images, ("INV-REMOVABLE-DRIVES", "endpoint_telemetry"): inv_usb_owner,
    ("INV-FLOWS", "endpoint_telemetry"): inv_flows, ("INV-DNS", "endpoint_telemetry"): inv_dns, ("INV-USB", "endpoint_telemetry"): inv_usb,
    ("INV-SESSION", "endpoint_telemetry"): inv_session, ("INV-SERVICE", "endpoint_telemetry"): inv_service, ("INV-IDS", "endpoint_telemetry"): inv_ids_edr,
    ("INV-COMPLETE", "host_triage"): p_tri_complete, ("INV-NEUTRAL", "host_triage"): p_tri_neutral, ("INV-TIMES", "host_triage"): p_tri_times,
}


if __name__ == "__main__":
    import traceback
    fails, seen = 0, set()
    for (ev, sid), p in PROBES.items():
        if p in seen and not ev.startswith("INV"):
            continue
        seen.add(p)
        try:
            ok, detail = p()
        except Exception:
            ok, detail = False, "probe raised: " + traceback.format_exc(limit=2).strip().splitlines()[-1]
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {ev:<24} {sid:<20} {detail}")
    for sid, d in STREAMS.items():
        lo, hi = d["time_range"]()
        unknown = sorted(str(x) for x in set(d["ids"]()) - set(d["registry_ids"]()))
        print(f"{'ok  ' if not unknown else 'FAIL'} {sid:<24} span {iso(int(lo))} .. {iso(int(hi))}; ids not in registry: {unknown[:5]}; keys: {len(d['columns']())}")
        fails += bool(unknown)
    print("PASS" if not fails else f"FAILED: {fails}")
    sys.exit(1 if fails else 0)
