"""Neutrality scan of the utility's IT and security logs.

    python scripts/check_neutrality_utility.py [--only=siem,zeek.conn,...] [--fresh] [--budget=140]
    python scripts/check_neutrality_utility.py --report        print the findings of the last complete run

Question it answers: can a record that belongs to the hidden activity be told from ordinary records by
a cheap property of HOW it was written (a value, a shape, a round number, a key order, a one-of-a-kind
combination) instead of by analysis of WHAT happened? It does mechanically what the independent
reviewers did by hand.

Oracle. Which records belong to the activity is decided here from the same model constants the
generators use (scripts/streams/gen_itsec.py: the workstation, its two outside names and address, the
fourteen gateway sessions, the times of the hostile changes, the staging transfer). Records written by
the utility's own investigation and response are "neutral": they are neither story nor company.

Features computed for every record of every log (JSON logs are split by event id / event type):
  v      exact value of a low-cardinality column, and pairs (v2) and triples (v3) of such columns
  shape  character classes of a string, runs collapsed            tmpl   digits -> #, hex runs -> H
  nlab   number of dot-separated labels                            hyph / digl   which labels hold - or a digit
  len    length bucket     case   case pattern     ext   extension chain     pre / suf   first / last token
  mod10/100/1000  numeric value divisible by 10 / 100 / 1000               eq     two columns hold the same value
  frac   float with a zero fractional part                         sec0 / min0 / ms0   time on a whole second, minute, millisecond
  keys   JSON key order of the event                               delta  fixed time offset between related story records

A feature value is a FINDING when it selects at least one story record and
  * its benign company is smaller than max(20, 5 x the story records it selects) (in a log with fewer than 1,000
    ordinary records: two per cent of the log, never fewer than five) and smaller in proportion than a fifth of
    its share among story records, unless the story value is one of a crowd (at least max(50, 10 x story)
    benign records, or half of a small log, also carry values that rare in that column), or
  * (artefact features only) it holds for at least 30 % of the log's story records (and at least 3) and is at
    least eight times more frequent among them than among benign records (numeric, time and key-order features only).
Findings that are genuine properties of the activity are listed in ALLOW with a reason; everything else has
to be fixed in the generators. Exit code 1 on findings, 3 when there is more to do. Writes
07_validation/reports/neutrality_utility.json.
"""
import bisect
import csv
import glob
import itertools
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "streams"))
import gen_itsec as G                                   # noqa: E402
import itsec_host_model as HM                           # noqa: E402

M = G.M
NET = os.path.join(ROOT, "05_other_sources", "network_logs")
STATE = os.path.join(HERE, "streams", "_cache", "neutrality_utility")
OUT = os.path.join(ROOT, "07_validation", "reports", "neutrality_utility.json")

# ------------------------------------------------------------------------------------------------ oracle
WS04, JMP = G.WS04, G.JMP
WS04IP, JMPIP, HDMZIP = G.IP[WS04], G.IP[JMP], G.IP[G.HISTDMZ]
C2IP = G.BEACON_IP
C2NAMES = {G.BEACON_SNI, "update-cdn.meridiancontrols.net"}
LURE_DOMAIN = "cbpwa-vendor-support.com"
ATT_IPS = {s["ip"] for s in G.SESSIONS}
SESS = sorted((s["start"] - s.get("lead", 0), s["start"] + s["dur"] + max(0, s.get("tail", 0))) for s in G.SESSIONS)
STAGE_T = G.ts("2027-09-08T23:58Z")
CMD_T = (M.T["sub2_cmd"], M.T["sub3_cmd"])
BIN_TOKENS = ("FEMA-PREP", "vstelemetry", "VantageTelemetry", "Vantage Telemetry")
RESPONSE = ("SI-2027-CC-001", "AUDIT-EXC-2027-10", "QRY-CHG", "TXRC-", "evidence export")
TOKENS = re.compile("|".join(re.escape(x) for x in sorted(
    {WS04, WS04IP, C2IP, JMP, JMPIP, HDMZIP, "VELA", "rvela", "svc_fieldops_ext", LURE_DOMAIN, "MAINT-EXCEPT-0892", "WL-NET-0117",
     "SE3-OT-3301"} | C2NAMES | ATT_IPS | set(BIN_TOKENS) | set(RESPONSE), key=len, reverse=True)))

_day = {}


def ep(s):
    """Epoch seconds of 2027-09-11T22:11:07Z / ...07.123Z, or of a Zeek epoch string."""
    if not s:
        return 0.0
    if s[0] in "0123456789" and "T" not in s:
        try:
            return float(s)
        except ValueError:
            return 0.0
    d = s[:10]
    if d not in _day:
        try:
            _day[d] = G.ts(d + "T00:00Z")
        except Exception:
            return 0.0
    try:
        return _day[d] + int(s[11:13]) * 3600 + int(s[14:16]) * 60 + float(s[17:].rstrip("Z") or 0)
    except ValueError:
        return 0.0


def in_sess(t, pad=40):
    i = bisect.bisect_right(SESS, (t + pad, 9e18)) - 1
    return i >= 0 and SESS[i][0] - pad <= t <= SESS[i][1] + pad


def resp(r):
    s = " ".join(str(v) for v in r.values())
    return any(x in s for x in RESPONSE)


def o_siem(r):
    t = ep(r["time_utc"])
    if r["src_host"] == WS04 and r["dst_ip"] == C2IP:
        return "s"
    if r["src_host"] == JMP and in_sess(t) and ("svc_fieldops_ext" in r["user"] or r["user"] == "GW-ENG-VELA"):
        return "s"
    if r["rule_id"] == "SE3-OT-3301" and "change_count_since" in r["detail"]:
        return "n"                                         # the scheduled re-evaluation the system raises while the list is over its threshold
    return "n" if resp(r) else None


def o_rules(r):
    if r["rule_id"] in ("MAINT-EXCEPT-0892", "WL-NET-0117") and not resp(r):
        return "s"
    return "n" if resp(r) else None


def o_ras(r):
    return "s" if r["account"] == "GW-ENG-VELA" and r["src_ip"] in ATT_IPS else None


def o_hist(r):
    return "s" if r["client_host"] == JMP and r["account"].endswith("svc_fieldops_ext") and in_sess(ep(r["start_utc"])) else None


def o_cfg(r):
    if r["session_user"] == "GW-ENG-VELA" and r["source_host"] == JMP and in_sess(ep(r["time_utc"])):
        return "s"
    return "n" if resp(r) else None


def o_supp(r):
    if r["changed_by"] == "GW-ENG-VELA" and r["source_host"] == JMP and in_sess(ep(r["time_utc"])):
        return "s"
    return "n" if resp(r) else None


def o_fim(r):
    return "s" if r["user"] == "GW-ENG-VELA" and r["source_host"] == JMP and in_sess(ep(r["time_utc"])) else None


def o_cmd(r):
    t = ep(r["time_utc"])
    if any(abs(t - c) <= 2 for c in CMD_T) and r["command"] == "BREAKER OPEN":
        return "s"
    return "n" if resp(r) else None


def o_neutral(r):
    return "n" if resp(r) else None


def o_av(r):
    return "s" if r["host"] == WS04 and abs(ep(r["time_utc"]) - G.AV_OFF_T) <= 2 else None


def o_mail(r):
    return "s" if r["sender_domain"] == LURE_DOMAIN and r["action"] == "delivered" else None


_dns_uids = set()


def _flow(o, r_, rp, t):
    if o == WS04IP and r_ == C2IP:
        return True
    if o in ATT_IPS and r_ == JMPIP:
        return True
    if o == JMPIP and in_sess(t, 5):
        return True
    return o == WS04IP and r_ == HDMZIP and str(rp) == "445" and abs(t - STAGE_T) < 3600


def o_conn(r):
    if r["uid"] in _dns_uids:
        return "s"
    return "s" if _flow(r["id.orig_h"], r["id.resp_h"], r["id.resp_p"], ep(r["ts"])) else None


def o_dns(r):
    if r["query"] in C2NAMES:
        _dns_uids.add(r["uid"])
        return "s"
    return None


def o_ssl(r):
    return "s" if r["server_name"] in C2NAMES or (r["id.orig_h"] in ATT_IPS and r["id.resp_h"] == JMPIP) else None


def o_notice(r):
    return "s" if WS04IP in (r.get("src"), r.get("id.orig_h")) and C2IP in (r.get("dst"), r.get("id.resp_h")) else None


def o_fw(r):
    t = ep(r["time_utc"]) - float(r["duration_s"] or 0)
    return "s" if _flow(r["src_ip"], r["dst_ip"], r["dst_port"], t) else None


def o_proxy(r):
    return "s" if r["client_ip"] == WS04IP and r["host"] in C2NAMES else None


def o_win(r):
    t = ep(r["time_utc"])
    who = (r.get("user"), r.get("target_user"))
    if "GW-ENG-VELA" in who and in_sess(t, 60):
        return "s"
    if "svc_fieldops_ext" in who and r.get("domain") == JMP and in_sess(t, 60):
        return "s"
    if "rvela" in who and r.get("src_ip") == WS04IP:
        return "s"
    s = json.dumps(r)
    if r["host"] == WS04 and (any(b in s for b in BIN_TOKENS) or abs(t - G.AV_OFF_T) <= 2 and r["event_id"] in (5001,)):
        return "s"
    if r.get("src_ip") in ATT_IPS:
        return "s"
    return None


def o_edr(r):
    t = ep(r["time_utc"])
    s = json.dumps(r)
    if r["host"] == WS04 and (any(b in s for b in BIN_TOKENS) or r.get("dst_ip") == C2IP or r.get("query") in C2NAMES
                              or (r.get("dst_ip") == HDMZIP and abs(t - STAGE_T) < 3600)):
        return "s"
    if "VELA" in str(r.get("user")) and in_sess(t, 60):
        return "s"
    return None


def o_triage(r):
    s = " ".join(str(v) for v in r.values())
    if any(b in s for b in BIN_TOKENS) or any(ip in s for ip in ATT_IPS) or C2IP in s:
        return "s"
    return None


LOGS = {   # name: (kind, glob under network_logs, oracle, subtype key or None)
    "siem": ("csv", "siem/siem_alerts_*.csv", o_siem, "rule_id"),
    "siem.rule_changes": ("csv", "siem/rule_changes.csv", o_rules, None),
    "audit.remote_access": ("csv", "audit/remote_access_sessions.csv", o_ras, None),
    "audit.historian": ("csv", "audit/historian_access.csv", o_hist, None),
    "audit.ot_config": ("csv", "audit/ot_config_changes.csv", o_cfg, None),
    "audit.suppression": ("csv", "audit/alarm_suppression_audit.csv", o_supp, None),
    "audit.file_integrity": ("csv", "audit/file_integrity.csv", o_fim, None),
    "audit.scada_cmd": ("csv", "audit/scada_command_log.csv", o_cmd, None),
    "audit.change_mgmt": ("csv", "audit/change_management.csv", o_neutral, None),
    "audit.endpoint_protection": ("csv", "audit/endpoint_protection.csv", o_av, None),
    "audit.mail": ("csv", "audit/mail_gateway_cbpwa.csv", o_mail, None),
    "zeek.dns": ("zeek", "zeek/*/dns.log", o_dns, None),
    "zeek.conn": ("zeek", "zeek/*/conn.log", o_conn, None),
    "zeek.ssl": ("zeek", "zeek/*/ssl.log", o_ssl, None),
    "zeek.notice": ("zeek", "zeek/*/notice.log", o_notice, None),
    "firewall": ("csv", "firewall/*.csv", o_fw, "device"),
    "proxy": ("csv", "proxy/*.csv", o_proxy, None),
    "windows": ("jsonl", "windows/*.jsonl", o_win, "event_id"),
    "endpoint": ("jsonl", "endpoint/*.jsonl", o_edr, "event_type"),
    "triage.files": ("triage", "triage/*/file_listing.csv", o_triage, None),
    "triage.services": ("triage", "triage/*/services.csv", o_triage, None),
    "triage.autoruns": ("triage", "triage/*/autoruns.csv", o_triage, None),
    "triage.tasks": ("triage", "triage/*/scheduled_tasks.csv", o_triage, None),
    "triage.exec": ("triage", "triage/*/execution_history.csv", o_triage, None),
    "triage.logons": ("triage", "triage/*/logon_history.csv", o_triage, None),
    "triage.software": ("triage", "triage/*/installed_software.csv", o_triage, None),
}
ORDER = list(LOGS)
SKIP_COLS = {"alert_id", "uid", "record_id", "session_id", "logon_id", "fuid", "trans_id", "console_session_id"}
TIME_RX = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
NUM_RX = re.compile(r"^-?\d+(\.\d+)?$")
LEN_SKIP = re.compile(r"user|account|host|operator|changed_by|owner|recipient|sender$")

# ---- genuine properties of the activity: (log regex, column regex, value regex, reason) -------------------
IDENT = sorted({WS04, WS04IP, C2IP, JMP, JMPIP, "GW-ENG-VELA", "rvela", "svc_fieldops_ext", "GW-SYS-JMP-01\\svc_fieldops_ext", LURE_DOMAIN,
                "MAINT-EXCEPT-0892", "WL-NET-0117", "AS-60729", "AS-209144", G.WS04_USER["username"], G.WS04_USER["email"],
                HM.VST_SERVICE, HM.VST_SERVICE.replace(" ", ""), HM.ATT_NAME, HM.ZIP_NAME} | C2NAMES | ATT_IPS, key=len, reverse=True)
ALLOW = [
    (r".", r".", "^(" + "|".join(re.escape(x) for x in IDENT) + ")$",
     "identity: the attacker's addresses and networks, the two outside names, the compromised workstation, account and gateway are what the analysis has to find"),
    (r"remote_access", r"src_country", r"^(DE|RO|NL|SG)$", "sessions from abroad"),
    (r"firewall", r"^src_zone$", "^" + G.BYNAME[WS04]["zone"] + "$", "the network zone the compromised workstation sits in (its identity at a coarser grain)"),
    (r"remote_access|ot_config|suppression|historian", r"change_ticket|auth_method", r"^(|password only)$", "no ticket, password only"),
    (r"ot_config", r"^(parameter|old_value|new_value|device)$", r".", "content of the change: what was altered is the finding itself"),
    (r"suppression", r"^(alarm_point|active_suppressions_after|category|system)$", r".", "content: which alarms were suppressed and how many were active"),
    (r"historian", r"^(tags_queried|tag_groups|duration_s|query_type)$", r".", "content: what was read from the historian"),
    (r"remote_access", r"^(target_hosts|duration_s|bytes_out|bytes_in)$", r".", "content: what the session reached and its size"),
    (r"siem$", r"^(detail|rule_id|rule_name|priority|category|dst_host|dst_ip|disposition|close_note|closed_by)$", r".",
     "which rules fired on the activity, what they reported and how analysts closed them (checked separately for one-of-a-kind notes by the shape features)"),
    (r"siem.rule_changes", r"^(description|action|rule_type|changed_by)$", r".", "content of the two rule changes"),
    (r"file_integrity", r"^(path|diff_summary|previous_hash|new_hash)$", r".", "content of the write"),
    (r"scada_cmd", r"^(device|command|workstation|operator|origin|origin_host)$", r".", "content: which breaker, from where"),
    (r"zeek|firewall|proxy|endpoint|windows", r"bytes|size|duration|pkts|missed", r".", "size and length of a transfer"),
    (r"triage.autoruns", r"^(signer|location|enabled)$", r"^$|^service$|^yes$", "an unsigned program registered as an auto-start service is a real forensic property"),
    (r"zeek|firewall|proxy|endpoint|windows|triage", r"port$|^path$|image|^service|_name$|sha256|hash|md5|signer|answers|query|^host$|^src_host$|process|command_line|parent",
     r".", "where a connection went or what ran: exact values only; their shapes, lengths and labels are still tested"),
]
ALLOW = [(re.compile(a), re.compile(b), re.compile(c), d) for a, b, c, d in ALLOW]
IDENT_RX = re.compile("|".join(re.escape(x) for x in sorted(set(IDENT) | set(BIN_TOKENS) | {"vstelemetry"}, key=len, reverse=True)))
# artefact features that are genuine: (log regex, feature, column regex, value regex, reason)
ALLOW_ART = [
    (r"endpoint|windows|triage", "ext", r".", r"^pdf\.exe$", "a double extension is a real property of the lure file"),
    (r"siem", "tmpl", r"close_note", r"^SE#-BULK-STORM-#$", "the storm-mode dismissal note, carried by tens of thousands of alerts of other rules"),
    (r"siem", "tmpl", r"close_note", r"^SI-#-[A-Z]+-# opened$", "an incident case opened by the utility's own response (documented in the guides)"),
    (r"triage.files", "ext", r"path", r"^arc$", "content of the compromised machine's disk: the staged copies keep the archive files' own names"),
    (r"endpoint|windows|triage", "ext", r".", r"^pdf$", "the same double extension inside a quoted command line"),
    (r"endpoint|windows|triage", "shape", r".", r"a-a-a-9\.a\.a\W*$", "the lure file's own name (several words, a year, two extensions)"),
    (r"siem", "tmpl", r"close_note", r"^SI-#-CC-# opened$", "the incident case opened by the utility's own response (documented in the guides)"),
]
ALLOW_ART = [(re.compile(a), b, re.compile(c), re.compile(d), e) for a, b, c, d, e in ALLOW_ART]
STRING_F = ("shape", "tmpl", "nlab", "hyph", "digl", "len", "case", "ext", "pre", "suf")
BOOL_F = ("mod10", "mod100", "mod1000", "eq", "frac", "sec0", "min0", "ms0")
ARTEFACT = STRING_F + BOOL_F + ("keys",)
EXACT_ONLY_ALLOW = ALLOW[-2:]          # these two entries never excuse an artefact feature


def allowed(log, ftype, cols, val):
    vals = val if isinstance(val, (tuple, list)) else (val,)
    cols = cols if isinstance(cols, (tuple, list)) else (cols,)
    if ftype in ("v", "v2", "v3"):
        for c, v in zip(cols, vals):
            for a, b, rx, why in ALLOW:
                if a.search(log) and b.search(c) and rx.search(str(v)):
                    return why
    else:
        for a, ft, b, rx, why in ALLOW_ART:
            if ft == ftype and a.search(log) and b.search(str(cols)) and rx.search(str(val)):
                return why
    return None


# ------------------------------------------------------------------------------------------------ features
_S1 = re.compile(r"[A-Za-z]+")
_S2 = re.compile(r"[0-9]+")
_HEX = re.compile(r"\b[0-9a-fA-F]{6,}\b")
_TOK = re.compile(r"[-_ ./\\:(,;=@]")


def sfeat(v):
    """Artefact features of one string value: list of (ftype, value)."""
    out = []
    shape = _S2.sub("9", _S1.sub("a", v))
    out.append(("shape", shape[:60]))
    out.append(("tmpl", _S2.sub("#", _HEX.sub("H", v))[:80]))
    n = len(v)
    out.append(("len", 0 if n == 0 else 1 if n < 5 else 2 if n < 9 else 3 if n < 17 else 4 if n < 33 else 5 if n < 65 else 6))
    if " " not in v and "." in v and "\\" not in v and "/" not in v:
        labs = v.split(".")
        out.append(("nlab", len(labs)))
        out.append(("hyph", "".join("1" if "-" in x else "0" for x in labs[:4])))
        out.append(("digl", "".join("1" if any(c.isdigit() for c in x) else "0" for x in labs[:4])))
    letters = [c for c in v if c.isalpha()]
    if letters:
        up = sum(1 for c in letters if c.isupper())
        out.append(("case", "U" if up == len(letters) else "l" if up == 0 else "T" if up <= v.count(" ") + 1 and v[0].isupper() else "m"))
    base = v.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    if "." in base and " " not in base[-12:]:
        ex = [x for x in base.split(".")[1:] if 0 < len(x) <= 5 and x.isalnum() and not x.isdigit()]
        if ex:
            out.append(("ext", ".".join(ex[-2:]).lower()))
    toks = [x for x in _TOK.split(v) if x]
    if len(toks) > 1:
        out.append(("pre", _S2.sub("#", toks[0])[:24]))
        out.append(("suf", _S2.sub("#", toks[-1])[:24]))
    return out


def row_feats(row, low, want=None, wcols=None):
    """All features of a row: {(ftype, cols): value}. want: restrict to these (ftype, cols) keys
    (wcols = the columns that still have a single-column key wanted)."""
    f = {}
    items = [(c, "" if v is None else str(v)) for c, v in row.items() if c not in SKIP_COLS]
    for c, v in items:
        if wcols is not None and c not in wcols:
            continue
        if c in low:
            f[("v", c)] = v
            if v and not NUM_RX.match(v) and not TIME_RX.match(v):
                t = _S2.sub("#", _HEX.sub("H", v))[:80]
                if t != v and not IDENT_RX.search(v):
                    f[("tmpl", c)] = t
            continue
        if v == "" or v == "-":
            continue
        if TIME_RX.match(v):
            if True:
                f[("sec0", c)] = v[17:19] == "00"
                f[("min0", c)] = v[14:19] == "00:00"
                if "." in v[19:]:
                    f[("ms0", c)] = v[20:23] == "000"
            continue
        if NUM_RX.match(v):
            if "." in v:
                if c == "ts" or c.endswith("duration") or c == "duration_s":
                    f[("frac", c)] = v.split(".")[1].strip("0") == ""
                continue
            if len(v) >= 4:
                x = int(v)
                f[("mod10", c)] = x % 10 == 0
                f[("mod100", c)] = x % 100 == 0
                f[("mod1000", c)] = x % 1000 == 0
            continue
        ident = IDENT_RX.search(v)
        for ft, val in sfeat(v):
            if ident and ft in ("tmpl", "pre", "suf", "len"):
                continue                                   # these would only restate the identity; its shape is still tested
            if ft == "len" and LEN_SKIP.search(c):
                continue
            f[(ft, c)] = val
    lows = [(c, v) for c, v in items if c in low]
    if want is None:
        for (c1, v1), (c2, v2) in itertools.combinations(lows, 2):
            f[("v2", (c1, c2))] = (v1, v2)
        if len(lows) <= 9:
            for a, b, c in itertools.combinations(lows, 3):
                f[("v3", (a[0], b[0], c[0]))] = (a[1], b[1], c[1])
        vals = defaultdict(list)
        for c, v in items:
            if len(v) >= 5 and not TIME_RX.match(v):
                vals[v].append(c)
        for v, cs in vals.items():
            for c1, c2 in itertools.combinations(sorted(cs), 2):
                f[("eq", (c1, c2))] = True
    else:
        d = dict(lows)
        for k in want:
            if k[0] in ("v2", "v3") and all(c in d for c in k[1]):
                f[k] = tuple(d[c] for c in k[1])
            elif k[0] == "eq":
                a, b = k[1]
                va, vb = row.get(a), row.get(b)
                f[k] = va is not None and str(va) == str(vb) and len(str(va)) >= 5
    return f


# ------------------------------------------------------------------------------------------------ readers
def files_of(name):
    return sorted(glob.glob(os.path.join(NET, LOGS[name][1])))


def read(name, path):
    """Yield (raw line, parse function) for every record of one file."""
    kind = LOGS[name][0]
    if kind == "jsonl":
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                yield line, json.loads
    elif kind == "zeek":
        with open(path, encoding="utf-8") as fh:
            fields = None
            for line in fh:
                if line[0] == "#":
                    if line.startswith("#fields"):
                        fields = line.rstrip("\n").split("\t")[1:]
                    continue
                yield line, (lambda s, fields=fields: dict(zip(fields, s.rstrip("\n").split("\t"))))
    else:
        host = os.path.basename(os.path.dirname(path)) if kind == "triage" else None
        with open(path, encoding="utf-8", newline="") as fh:
            rd = csv.reader(fh)
            head = next(rd, None)
            if not head:
                return
            for vals in rd:
                d = dict(zip(head, vals))
                if host:
                    d["collection_host"] = host
                yield ",".join(vals) + ("," + host if host else ""), (lambda s, d=d: d)


_SUBRX = {"event_id": re.compile(r'"event_id":(\d+)'), "event_type": re.compile(r'"event_type":"(\w+)"')}


def subtype(name, line, row=None):
    key = LOGS[name][3]
    if not key:
        return ""
    if row is not None:
        return str(row.get(key, ""))
    if key in _SUBRX:
        m = _SUBRX[key].search(line)
        return m.group(1) if m else ""
    return None                                             # csv: needs the parsed row


# ------------------------------------------------------------------------------------------------ scan of one log
def scan(name, deadline):
    kind, _, oracle, subkey = LOGS[name]
    files = files_of(name)
    # ---- pass A: who is story, who is neutral; totals per subtype; low-cardinality columns
    story, marks, n_all, sample = defaultdict(list), {}, Counter(), defaultdict(lambda: defaultdict(set))
    small = sum(os.path.getsize(f) for f in files) < 3_000_000
    if name == "zeek.conn" and not _dns_uids:
        for f in files_of("zeek.dns"):
            for line, parse in read("zeek.dns", f):
                if "update-cdn" in line:
                    o_dns(parse(line))
    for fi, f in enumerate(files):
        for li, (line, parse) in enumerate(read(name, f)):
            row = None
            st = subtype(name, line)
            if st is None:
                row = parse(line)
                st = subtype(name, line, row)
            n_all[st] += 1
            if n_all[st] <= 4000 or li % 97 == 0:
                row = row or parse(line)
                for c, v in row.items():
                    if len(sample[st][c]) <= 80:
                        sample[st][c].add(str(v))
            if small or TOKENS.search(line):
                row = row or parse(line)
                cls = oracle(row)
                if cls:
                    marks[(fi, li)] = cls
                    if cls == "s":
                        story[st].append(row)
        if time.time() > deadline:
            return None
    low = {st: {c for c, vs in cols.items() if len(vs) <= 60 and c not in SKIP_COLS and (len(vs) <= 0.5 * n_all[st] or len(vs) <= 3)
                and not any(TIME_RX.match(x) for x in list(vs)[:3])} for st, cols in sample.items()}
    res = {"log": name, "subtypes": {}, "findings": []}
    if not story:
        res["subtypes"] = {st: {"rows": n, "story": 0} for st, n in n_all.items()}
        return res
    # ---- story features
    cand = {}                                              # st -> {(ftype, cols): {value: k_s}}
    distinct = defaultdict(set)                            # (st, key, value) -> distinct raw column values among story records
    for st, rows in story.items():
        d = defaultdict(Counter)
        for r in rows:
            for k, v in row_feats(r, low[st]).items():
                if v is False:
                    continue
                d[k][v] += 1
                if k[0] in STRING_F:
                    distinct[(st, k, v)].add(str(r.get(k[1])))
            if kind == "jsonl":
                d[("keys", "*")][",".join(r.keys())] += 1
        cand[st] = d
    n_s = {st: len(v) for st, v in story.items()}
    n_neutral = Counter()
    # ---- pass B: benign company of every story feature value. A key is settled, and no longer computed, once each of
    #      its story values has enough company for both tests.
    comp = {st: {k: Counter() for k in d} for st, d in cand.items()}
    caps, left, active, wc = {}, {}, {}, {}
    for st, d in cand.items():
        nb_est = max(1, n_all[st] - n_s[st])
        caps[st], left[st] = {}, {}
        for k, vals in d.items():
            cp = {}
            for v, ks in vals.items():
                c = max(20, 5 * ks) + 1
                if (k[0] in BOOL_F or k[0] == "keys") and ks >= 3 and ks / n_s[st] >= 0.3:
                    c = max(c, int(nb_est * (ks / n_s[st]) / 8) + 2)
                cp[v] = c
            caps[st][k], left[st][k] = cp, len(cp)
        active[st] = set(d)
        wc[st] = {k[1] for k in active[st] if isinstance(k[1], str)}
    for fi, f in enumerate(files):
        if not any(active.values()):
            break
        for li, (line, parse) in enumerate(read(name, f)):
            cls = marks.get((fi, li))
            st = subtype(name, line)
            row = None
            if st is None:
                row = parse(line)
                st = subtype(name, line, row)
            if cls:
                if cls == "n":
                    n_neutral[st] += 1
                continue
            act = active.get(st)
            if not act:
                continue
            row = row or parse(line)
            fs = row_feats(row, low[st], want=act, wcols=wc[st])
            if ("keys", "*") in act:
                fs[("keys", "*")] = ",".join(row.keys())
            c, cp = comp[st], caps[st]
            for k, v in fs.items():
                if v is False or k not in act:
                    continue
                cnt = c[k]
                cnt[v] += 1
                if v in cp[k] and cnt[v] == cp[k][v]:
                    left[st][k] -= 1
                    if left[st][k] == 0:
                        act.discard(k)
                        wc[st] = {kk[1] for kk in act if isinstance(kk[1], str)}
        if time.time() > deadline:
            return None
    # ---- decide
    for st, d in cand.items():
        nb_total = n_all[st] - n_s[st] - n_neutral[st]
        res["subtypes"][st] = {"rows": n_all[st], "story": n_s[st], "neutral": n_neutral[st]}
        for k, vals in d.items():
            cnt = comp[st][k]
            for v, ks in vals.items():
                kb = cnt.get(v, 0)
                if k[0] in STRING_F:                        # many records carrying one and the same value count once
                    ks = len(distinct[(st, k, v)])
                thr = max(20, 5 * ks)
                if nb_total < 1000:                         # a small log cannot offer twenty of everything: two per cent of it, never fewer than five
                    thr = max(5, min(thr, int(0.02 * nb_total) + 1))
                why = None
                rs, rb = ks / n_s[st], kb / max(1, nb_total)
                if kb < thr and rb < rs / 5:                # too little company, in absolute and in proportion
                    if k[0] in ("v", "v2", "v3"):
                        if not (nb_total < 200 and kb >= max(3, ks)):          # small table: shared with at least as many ordinary rows
                            why = f"benign company {kb} < {thr}"
                    elif k[0] in BOOL_F or k[0] == "keys":
                        if ks >= 2 or (kb == 0 and nb_total >= 30):
                            why = f"{ks}/{n_s[st]} story records against {kb}/{nb_total} ordinary"
                    else:
                        # one of a crowd? ordinary records whose own value is as rare; for templates, among values with the same first word
                        grp = None
                        if k[0] == "tmpl":
                            g0 = _TOK.split(str(v))[0]
                            same = {vv: c for vv, c in cnt.items() if _TOK.split(str(vv))[0] == g0}
                            if sum(same.values()) >= 5:
                                grp = same
                        pool = grp if grp is not None else cnt
                        crowd = sum(c for vv, c in pool.items() if c < max(20, 5 * ks) and vv != v)
                        need = min(max(50, 10 * ks), 0.5 * (sum(pool.values()) if grp is not None else nb_total))
                        if crowd < need and not (nb_total < 200 and kb >= max(1, ks)):
                            why = f"benign company {kb} < {thr}; {crowd} ordinary records carry values that rare" + (" among the same kind" if grp is not None else "")
                if not why and (k[0] in BOOL_F or k[0] == "keys") and ks >= 3 and rs >= 0.3 and nb_total and rb * 8 <= rs:
                    why = f"{ks}/{n_s[st]} story records against {kb}/{nb_total} ordinary"
                if why:
                    al = allowed(name, k[0], k[1], v)
                    res["findings"].append({"log": name + (":" + st if st else ""), "feature": k[0], "columns": k[1], "value": v, "story": ks,
                                            "benign": kb, "why": why, "allowed": al})
    res["story_times"] = sorted(ep(str(r.get("time_utc") or r.get("ts") or r.get("login_utc") or r.get("start_utc") or "")) for rows in story.values() for r in rows)[:4000]
    return res


DELTA_PAIRS = [("audit.suppression", "windows"), ("audit.scada_cmd", "windows"), ("audit.ot_config", "zeek.conn"), ("audit.ot_config", "windows"),
               ("audit.file_integrity", "windows"), ("audit.remote_access", "zeek.conn"), ("audit.historian", "audit.remote_access"),
               ("siem", "audit.historian"), ("siem", "audit.suppression"), ("audit.suppression", "zeek.conn"), ("audit.scada_cmd", "zeek.conn")]


def deltas(results):
    out = []
    for a, b in DELTA_PAIRS:
        ta, tb = results.get(a, {}).get("story_times") or [], results.get(b, {}).get("story_times") or []
        if len(ta) < 4 or not tb:
            continue
        ds = []
        for t in sorted(set(int(x) for x in ta)):
            i = bisect.bisect_left(tb, t)
            near = [x for x in tb[max(0, i - 3):i + 3] if abs(x - t) <= 180 and abs(x - t) >= 2]
            if near:
                d = min(near, key=lambda x: abs(x - t)) - t
                ds.append(int(round(d)))
        if len(ds) >= 4:
            v, c = Counter(ds).most_common(1)[0]
            if c / len(ds) >= 0.6:
                out.append({"log": f"{a} -> {b}", "feature": "delta", "columns": "time", "value": v, "story": c, "benign": 0,
                            "why": f"{c} of {len(ds)} related story records are exactly {v} s apart", "allowed": None})
    return out


def main():
    args = sys.argv[1:]
    only = next((a.split("=", 1)[1].split(",") for a in args if a.startswith("--only=")), None)
    budget = float(next((a.split("=", 1)[1] for a in args if a.startswith("--budget=")), 140))
    os.makedirs(STATE, exist_ok=True)
    if "--fresh" in args:
        for f in glob.glob(os.path.join(STATE, "*.json")):
            if not only or os.path.basename(f)[:-5] in only:
                os.remove(f)
    deadline = time.time() + budget
    todo = [n for n in ORDER if (not only or n in only)]
    if "--report" not in args:
        for n in todo:
            p = os.path.join(STATE, n + ".json")
            if os.path.exists(p):
                continue
            if time.time() > deadline - 5:
                print("more to do; run again")
                return 3
            t0 = time.time()
            r = scan(n, deadline)
            if r is None:
                print(f"{n}: out of time after {time.time() - t0:.0f} s; run again (it restarts this log)")
                return 3
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(r, fh)
            bad = [x for x in r["findings"] if not x["allowed"]]
            print(f"{n}: story {sum(s['story'] for s in r['subtypes'].values())}, findings {len(bad)} (+{len(r['findings']) - len(bad)} allowed)  [{time.time() - t0:.0f} s]")
    results = {}
    for n in ORDER:
        p = os.path.join(STATE, n + ".json")
        if os.path.exists(p):
            results[n] = json.load(open(p, encoding="utf-8"))
    missing = [n for n in ORDER if n not in results]
    findings = [x for r in results.values() for x in r["findings"]] + deltas(results)
    bad = [x for x in findings if not x["allowed"]]
    by_log = Counter(x["log"].split(":")[0] for x in bad)
    report = {"complete": not missing, "missing": missing, "logs": {n: r["subtypes"] for n, r in results.items()},
              "findings": bad, "allowed": Counter(x["allowed"] for x in findings if x["allowed"]), "by_log": by_log,
              "allow_list": [{"log": a.pattern, "column": b.pattern, "reason": d} for a, b, c, d in ALLOW]}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    if "--report" in args or "--list" in args:
        for x in sorted(bad, key=lambda x: (x["log"], x["feature"], str(x["columns"]))):
            print(f"  {x['log']:28s} {x['feature']:6s} {str(x['columns'])[:44]:44s} {str(x['value'])[:70]:70s} story {x['story']} benign {x['benign']}  ({x['why']})")
    print(f"{'COMPLETE' if not missing else 'PARTIAL (missing ' + ', '.join(missing) + ')'}: {len(bad)} finding(s) in {len(by_log)} log(s); "
          f"{len(findings) - len(bad)} allowed as genuine properties; by log: {dict(by_log)}")
    return 3 if missing else (1 if bad else 0)


if __name__ == "__main__":
    sys.exit(main())
