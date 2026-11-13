"""Neutrality scan of the partner, portal, aid-application and vessel-session data.

    python scripts/check_neutrality_partner.py              run every table group still to do (resumes), then report
    python scripts/check_neutrality_partner.py --fresh      forget earlier results first
    python scripts/check_neutrality_partner.py --only=portal_aid,vessel
    python scripts/check_neutrality_partner.py --report     only print the stored result

It does mechanically what a reviewer does by hand: for every table it knows which records belong to a hidden
story (the oracle, taken from the generators' own model constants) and looks for any cheap feature that
separates those records from the rest:

  exact      the value of every low-cardinality column, and pairs and triples of such columns
  shape      for every string column (and every token of a ;-separated one): character-class pattern,
             number of dot-separated labels, hyphen or digit in the first label, length bucket, case,
             first and last token, template after normalising digits and hex
  number     value divisible by 10, 100, 1000; two numeric columns equal; a story value repeated in another table
  time       second zero, minute and second zero; offsets to related records that differ from ordinary ones
  structure  a table made mostly of story rows; an entity (vessel, bank, device, ...) whose id is shaped or
             behaves unlike the others; registry hosts that break the naming or addressing pattern

A feature value is a finding when it selects at least one story record and fewer benign records than
need(s) = max(20, 5 s) for small groups, capped for very large groups (see need()), and the story's share of the
selected records is at least twice its share of the whole table (so a value every row has is not a finding in a
small table). Findings that are
genuine properties of the activity are listed in ALLOW with the reason; everything else has to be fixed
in the generators. Exit code 1 while findings remain (3 = more groups to scan).
Writes 07_validation/reports/neutrality_partner.json.
"""
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
import netmap                      # noqa: E402
import partner_it_model as P       # noqa: E402

SRC = os.path.join(ROOT, "05_other_sources")
OUT = os.path.join(ROOT, "07_validation", "reports", "neutrality_partner.json")
STATE = os.path.join(ROOT, "07_validation", "reports", "_neutrality_partner_state.json")
ORGS = ["city", "nascc", "brw", "port", "srmc", "bcmc", "county"]
LURE_DOMS = {P.LURE_DOM, P.BRW_LURE_DOM}
LURE_HOSTS = {P.LURE_HOST, P.BRW_LURE_HOST}
STORY_IPS = set(netmap.STORY_SET) | {"198.51.100.44"}

# ---- genuine properties of the activity: (table regex, feature regex, reason) ------------------------------
ALLOW = [
    (r"/mail$|^mail_gateway", r"^(shape|exact):(subject|sender|sender_domain|message_id)[:=]",
     "a bulk mailing has its own subject, sender names and message-id domain; ordinary bulk mailings of the same size exist beside it (checked: see bulk_company)"),
    (r"aid_applications\[takeovers\]", r"^(exact|pair|triple):.*(login_ip_seen_before|field_changed|record_type|status|channel|assistance_type)",
     "a deposit change after a sign-in from an address never seen for that account is the takeover itself"),
    (r"aid_applications\[takeovers\]", r"^(pair|triple):.*deposit_routing_number=",
     "the diverted payments go to a few accounts at two local banks (many accounts changed to the same deposit account is how such a diversion is found); both banks have thousands of ordinary customers and ordinary changes to them"),
    (r"aid_applications\[(one-address applications|planted applications)\]",
     r"^(exact|pair|triple):.*(zip|tract|area_id|county|tenure|self_reported_damage|primary_language|household_size|damaged_address|record_type|status|channel|source_asn)",
     "many near-identical applications from one address: same ZIP, tenure and damage level are what such a ring looks like"),
    (r"aid_applications", r"^shape:(previous_deposit_account_masked|login_ip_seen_before|field_changed|deposit_account_masked):",
     "a deposit change after a sign-in from an address never seen for that account is the takeover itself"),
    (r"account_logons_city_airstation", r"^(pair|triple):.*device=new device",
     "a sign-on from a network and a device new for the account is the takeover; the table is a ten-day extract and the full logs hold the ordinary company (checked there)"),
    (r"mail_url_clicks_brightwake", r"^exact:sender_network=",
     "the network a message was sent from is a property of its sender; the vendor's full mail and firewall logs show other senders on that provider"),
    (r"aid_applications", r"^(reuse):damage_photo_hashes", "reused photographs across applications are how the ring is found"),
    (r"portal_aid", r"^(exact|pair|triple):.*event=login_failed", "the volume of failed sign-ins is the credential-stuffing run"),
    (r"portal_aid", r"^(exact|pair|triple):.*status=401", "the volume of failed sign-ins is the credential-stuffing run"),
    (r"portal_aid.*takeovers", r"^(exact|pair|triple):.*(profile_updated: direct deposit|path=/account/direct-deposit|event=login_success)",
     "a sign-in to an existing account followed by a change of its deposit details is the takeover itself"),
    (r"portal_aid\[one-address applications\]", r"^(pair|triple):.*client_network=",
     "one address submitting many applications: its provider and its three devices' browsers are that one office's"),
    (r"portal_aid\[(sign-in run|takeovers and planted applications)\]", r"^(pair|triple):.*client_network=ASN 64512",
     "the sign-in run and the takeovers come through one provider (the join canon uses between threads); the provider's label alone has ordinary company"),
    (r"aid_applications\[takeovers\]", r"^exact:source_asn=64512$",
     "the takeovers come through one provider (the join canon uses between threads); about a thousand ordinary applicants use the same provider"),
    (r"vessel", r"^(exact|pair|triple):.*(ticket_ref=$|ticket_ref=\(none\)|vendor_account=)",
     "sessions without a ticket by one vendor account are the misuse itself; ordinary sessions without a ticket exist"),
    (r"vessel", r"^(exact|pair|triple):.*(vessel_name=|vessel_mmsi=|target_system=)|^shape:(vessel_name|target_system):(tpl|last|first)=",
     "the misuse was aimed at two ships; each of them also has ordinary sessions"),
    (r"vessel", r"^exact:src_asn=|^pair:.*src_asn=|^triple:.*src_asn=|^shape:src_ip:",
     "a third network (neither the vendor's office nor its VPN) is the join canon uses between threads; other outside networks appear in ordinary sessions"),
]


def need(s, table_benign=10 ** 9):
    """Benign company a feature needs when it selects s story records: five times the story records, at least 20
    (at least 5 in a table with only a few hundred ordinary rows), and no more than 2,000 for very large stories."""
    floor = min(20, max(5, table_benign // 20))
    return min(max(floor, 5 * s), max(2000, s // 50))


# ---- features ---------------------------------------------------------------------------------------------
_HEX = re.compile(r"[0-9a-f]{6,}")
_DIG = re.compile(r"\d+")
_HEXID = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{6,}(?![0-9A-Za-z])|(?<![0-9A-Za-z])[0-9A-F]{6,}(?![0-9A-Za-z])")     # a random identifier: one token
_SEP = re.compile(r"[-_./@: ;,<>$\\]")
HOST_COL = re.compile(r"(^|_)(host|query|url_host|server_name|sender_domain)$")
CODE_COL = re.compile(r"(asn|zip|tract|routing|port|mmsi|status|household|event_id)")      # numbers that are codes, not quantities
# identifiers and addresses: an intruder's own addresses, accounts and sessions are specific by nature, so their exact
# values are not features (their shapes are)
ID_COL = re.compile(r"(^|_)(ip|account|account_ref|account_id|mailbox|recipient|sender|session_id|message_id|record_id|application_id|device_id|uid|applicant_name|damaged_address)$")


def shape_feats(v, _memo={}):
    f = _memo.get(v)
    if f is not None:
        return f
    f = []
    if v != "":
        pat = re.sub(r"[a-z]+", "a", re.sub(r"[A-Z]+", "A", re.sub(r"\d+", "9", _HEXID.sub("H", v))))
        f.append("pat=" + pat[:60])
        low = v.lower()
        tpl = _DIG.sub("#", _HEX.sub("H", low))
        f.append("tpl=" + tpl[:80])
        if " " not in v and "/" not in v:
            labels = v.split(".")
            f.append(f"dots={len(labels) - 1}")
            f.append("hyph1=" + ("y" if "-" in labels[0] else "n"))
            f.append("dig1=" + ("y" if any(c.isdigit() for c in labels[0]) else "n"))
        n = len(v)
        f.append("len=" + ("<8" if n < 8 else "8-15" if n < 16 else "16-31" if n < 32 else "32-63" if n < 64 else "64+"))
        f.append("case=" + ("lower" if v == low else "upper" if v == v.upper() else "title" if v[:1].isupper() and v[1:] == v[1:].lower() else "mixed"))
        parts = [p for p in _SEP.split(v) if p]
        if parts:
            f.append("first=" + _DIG.sub("#", parts[0].lower())[:24])
            f.append("last=" + _DIG.sub("#", parts[-1].lower())[:24])
    else:
        f.append("empty")
    if len(_memo) < 3_000_000:
        _memo[v] = f
    return f


def is_num(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


def scan_table(name, rows, story, entity_cols=()):
    """rows: list of dicts; story: per row False/None, True, or the name of the story the row belongs to.
    Each story is scanned on its own against the ordinary rows (rows of the other stories are left out), so a
    large story cannot hide a small one. Returns (findings, summary)."""
    classes = sorted({x for x in story if x and x is not True})
    if not classes:
        return scan_one(name, rows, [bool(x) for x in story], entity_cols)
    F, S = [], {"rows": len(rows), "story": sum(1 for x in story if x), "stories": {}}
    for c in classes:
        keep = [i for i, x in enumerate(story) if not x or x == c]
        f, s_ = scan_one(f"{name}[{c}]", [rows[i] for i in keep], [story[i] == c for i in keep], entity_cols)
        F.extend(f)
        S["stories"][c] = s_["story"]
    return F, S


def scan_one(name, rows, story, entity_cols=()):
    n, s_tot = len(rows), sum(story)
    findings = []
    if not rows:
        return findings, {"rows": 0, "story": 0}
    cols = list(rows[0].keys())
    distinct = {c: set() for c in cols}
    for r in rows:
        for c in cols:
            if len(distinct[c]) <= 400:
                distinct[c].add(r[c])
    numeric = {c for c in cols if not CODE_COL.search(c) and sum(1 for v in list(distinct[c])[:300] if v != "" and is_num(v)) >= 0.95 * max(1, sum(1 for v in list(distinct[c])[:300] if v != ""))
               and any(v != "" for v in distinct[c])}
    timecols = {c for c in cols if c.endswith("_utc") or c in ("time_utc",)}
    cat = [c for c in cols if len(distinct[c]) <= 60 and c not in timecols and not ID_COL.search(c) and not HOST_COL.search(c)]
    cat3 = [c for c in cat if len(distinct[c]) <= 30]
    multi = {c for c in cols if c not in numeric and sum(1 for v in list(distinct[c])[:300] if ";" in v) >= 3}
    tot, st = Counter(), Counter()
    combos, combos_s = Counter(), Counter()
    for r, is_s in zip(rows, story):
        feats = []
        for c in cols:
            v = r[c]
            if c in timecols:
                if v:
                    if v[17:19] == "00":
                        feats.append(f"time:{c}:sec0")
                        if v[14:16] == "00":
                            feats.append(f"time:{c}:min0sec0")
                continue
            if c in cat:
                feats.append(f"exact:{c}={v}")
                if c not in numeric:
                    continue                                # its exact values are already features
            if c in numeric:
                if v != "":
                    try:
                        x = int(float(v))
                    except ValueError:
                        x = None
                    if x is not None and abs(x) >= 100:
                        if x % 10 == 0:
                            feats.append(f"number:{c}:mod10")
                        if x % 100 == 0:
                            feats.append(f"number:{c}:mod100")
                        if abs(x) >= 1000 and x % 1000 == 0:
                            feats.append(f"number:{c}:mod1000")
                continue
            if c in multi:
                for tok in set(v.split(";")):
                    feats.extend(f"shape:{c}[]:{x}" for x in shape_feats(tok))
            elif ID_COL.search(c):                         # identifiers: only their general shape, never their own letters
                if c == "message_id":
                    v = re.sub(r"@[^>]*", "@D", v)         # the part after @ is the sender's domain, not the id's form
                feats.extend(f"shape:{c}:{x}" for x in shape_feats(v) if not x.startswith(("first=", "last=", "tpl=")))
            elif HOST_COL.search(c):                       # host names: the registrable name is the host's identity, its form is not
                sf = shape_feats(v)
                sub = "dots=0" not in sf and "dots=1" not in sf
                feats.extend(f"shape:{c}:{x}" for x in sf if not x.startswith("tpl=") and (sub or not x.startswith("first=")))
            else:
                feats.extend(f"shape:{c}:{x}" for x in shape_feats(v))
        for a, b in itertools.combinations(sorted(numeric), 2):
            if r[a] != "" and r[a] == r[b]:
                feats.append(f"number:{a}=={b}")
        tot.update(feats)
        if is_s:
            st.update(feats)
        key = tuple(r[c] for c in cat3)
        combos[key] += 1
        if is_s:
            combos_s[key] += 1
    # pairs and triples of low-cardinality columns, from the grouped combinations
    for k in (2, 3):
        idx = list(itertools.combinations(range(len(cat3)), k))
        if len(idx) > 400:
            idx = idx[:400]
        ptot, pst = Counter(), Counter()
        for key, cnt in combos.items():
            cs = combos_s.get(key, 0)
            for ix in idx:
                f = ("pair:" if k == 2 else "triple:") + "&".join(f"{cat3[i]}={key[i]}" for i in ix)
                ptot[f] += cnt
                if cs:
                    pst[f] += cs
        tot.update(ptot)
        st.update(pst)
    seen_single = set()
    base = s_tot / n
    # a shape family with hundreds of different values (free text, identifiers) separates nothing: every value is rare
    fam = Counter(f.rsplit("=", 1)[0] for f in tot if f.startswith("shape:") and "=" in f)
    for f, s in sorted(st.items()):
        if f.startswith("shape:") and "=" in f and fam[f.rsplit("=", 1)[0]] > 300:
            continue
        b = tot[f] - s
        if f.startswith(("time:", "number:")):
            # chance is the null model here: only a rate clearly above what random seconds or digits give counts
            p0 = 1 / 3600 if f.endswith("min0sec0") else 1 / 60 if f.endswith("sec0") else 0.001 if f.endswith("mod1000") else 0.01 if f.endswith("mod100") else 0.1 if f.endswith("mod10") else 0.0
            b_rate = b / max(1, n - s_tot)
            if p0 and (s < 3 or s / s_tot < 3 * max(p0, b_rate)):
                continue
            if p0:
                findings.append({"table": name, "feature": f, "story": s, "benign": b, "need": need(s), "detail": f"story rate {s / s_tot:.3f}, ordinary rate {b_rate:.4f}"})
                continue
        # a separator: too little benign company AND the story's share among the selected rows is at least twice its share of the table
        if b < need(s, n - s_tot) and s / (s + b) >= min(1.0, 2 * base):
            if f.startswith(("pair:", "triple:")):
                if s < (3 if f.startswith("pair:") else 5):                  # a combination that small is chance, not a filter
                    continue
                parts = f.split(":", 1)[1].split("&")
                if any(("exact:" + p) in seen_single for p in parts):        # already reported through a single column
                    continue
                if f.startswith("triple:") and any(("pair:" + "&".join(q)) in seen_single for q in itertools.combinations(parts, 2)):
                    continue
            seen_single.add(f)
            findings.append({"table": name, "feature": f, "story": s, "benign": b, "need": need(s, n - s_tot)})
    # a table made mostly of story rows
    if s_tot and (n - s_tot) < s_tot:
        findings.append({"table": name, "feature": "structure:table mostly story rows", "story": s_tot, "benign": n - s_tot, "need": s_tot})
    # entities whose id is shaped unlike the others
    for c in entity_cols:
        cnt = defaultdict(lambda: [0, 0])
        for r, is_s in zip(rows, story):
            if r[c] != "":
                cnt[r[c]][0] += 1
                cnt[r[c]][1] += is_s
        ent_story = {k: v[1] * 2 >= v[0] for k, v in cnt.items()}      # an entity whose records are mostly story records
        et, es = Counter(), Counter()
        for e_id, is_s in ent_story.items():
            fs = [x for x in shape_feats(e_id) if x.startswith(("pat=", "dots=", "len="))]
            et.update(fs)
            if is_s:
                es.update(fs)
        for f, s in es.items():
            b = et[f] - s
            if b < max(3, 2 * s):
                findings.append({"table": name, "feature": f"structure:entity {c}:{f}", "story": s, "benign": b, "need": max(3, 2 * s)})
    return findings, {"rows": n, "story": s_tot}


# ---- tables and their oracles --------------------------------------------------------------------------------
def read(paths):
    rows = []
    for p in sorted(paths):
        with open(p, newline="", encoding="utf-8") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def partner(org, kind):
    return read(glob.glob(os.path.join(SRC, "partner_it", org, f"{kind}_*.csv")))


_lure_ips = {}


def lure_ips(org):
    if org not in _lure_ips:
        _lure_ips[org] = {r["answer"] for r in partner(org, "dns") if r["query"] in LURE_HOSTS and r["answer"]}
    return _lure_ips[org]


def aid_story(rows):
    """Story name per row of the applications file (None for ordinary rows)."""
    tr = json.load(open(os.path.join(ROOT, "06_data_streams", "_internal", "entity_registry_truth.json"), encoding="utf-8"))
    runner = set(tr["lph_runner_applications"]["ids"])
    syn = {s["registration_id"] for s in tr["aid_diversion"]["synthetic_identities"]}
    hij = set(tr["aid_diversion"]["hijacked_registrations"]["ids"])
    new_mask = {}
    for r in rows:
        if r["application_id"] in hij and r["record_type"] == "account_change" and r["source_ip"] in STORY_IPS:
            new_mask[r["application_id"]] = (r["deposit_account_masked"], r["changed_utc"])
    out = []
    for r in rows:
        a = r["application_id"]
        if a in runner:
            out.append("one-address applications")
        elif a in syn:
            out.append("planted applications")
        elif a in hij:
            m = new_mask.get(a)
            out.append("takeovers" if r["source_ip"] in STORY_IPS or (m is not None and r["record_type"] == "disbursement" and r["deposit_account_masked"] == m[0]) else None)
        else:
            out.append("takeovers" if r["source_ip"] in STORY_IPS else None)
    return out


def groups():
    g = {}
    for org in ORGS:
        g[f"partner_{org}"] = None
    for k in ("portal_aid", "portal_logistics", "aid_applications", "vessel", "extracts", "relations", "registry"):
        g[k] = None
    return list(g)


def run_group(name):
    F, S = [], {}

    def add(tname, rows, story, ent=()):
        f, s = scan_table(tname, rows, story, ent)
        F.extend(f)
        S[tname] = s

    if name.startswith("partner_"):
        org = name.split("_", 1)[1]
        m = partner(org, "mail")
        add(f"{org}/mail", m, [r["sender_domain"] in LURE_DOMS for r in m])
        bulk_company(f"{org}/mail", m, F)
        w = partner(org, "web")
        add(f"{org}/web", w, [r["host"] in LURE_HOSTS for r in w])
        d = partner(org, "dns")
        add(f"{org}/dns", d, [r["query"] in LURE_HOSTS for r in d])
        lips = lure_ips(org)
        fw = partner(org, "firewall")
        add(f"{org}/firewall", fw, [r["src_ip"] in STORY_IPS or r["dst_ip"] in lips for r in fw])
        a = partner(org, "auth")
        add(f"{org}/auth", a, [r["src_ip"] in STORY_IPS for r in a])
    elif name == "portal_aid":
        r = read(glob.glob(os.path.join(SRC, "network_logs", "portal", "aid_portal_access_*.csv")))
        def cls(x):
            ip = x["client_ip"]
            if ip == "198.51.100.44":
                return "one-address applications"
            if ip not in STORY_IPS:
                return None
            if x["time_utc"] < "2027-09-01":
                return "august probe"
            return "sign-in run" if x["event"] == "login_failed" else "takeovers and planted applications"
        add("portal_aid", r, [cls(x) for x in r])
    elif name == "portal_logistics":
        r = read(glob.glob(os.path.join(SRC, "network_logs", "portal", "base_logistics_access_*.csv")))
        add("portal_logistics", r, [x["client_ip"] in STORY_IPS for x in r])
    elif name == "aid_applications":
        r = read([os.path.join(SRC, "payments", "aid_applications.csv")])
        st = aid_story(r)
        add("aid_applications", r, st, ent=("deposit_routing_number",))
        # reuse of the same photograph by different applications
        use = defaultdict(set)
        for x in r:
            if x["record_type"] == "application":
                for tok in x["damage_photo_hashes"].split(";"):
                    if tok:
                        use[tok].add(x["application_id"])
        reused = sum(1 for v in use.values() if len(v) > 1)
        F.append({"table": "aid_applications", "feature": "reuse:damage_photo_hashes used by more than one application", "story": reused, "benign": 0, "need": 1})
    elif name == "vessel":
        r = read([os.path.join(SRC, "telemetry", "vessel_cargo_control_remote_sessions.csv")])
        add("vessel_sessions", r, [x["src_ip"] in STORY_IPS for x in r], ent=("target_system", "vessel_name", "vendor_account"))
    elif name == "extracts":
        A = os.path.join(SRC, "network_logs", "audit")
        for fn in ("mail_gateway_city", "mail_gateway_airstation", "mail_gateway_brightwake"):
            r = read([os.path.join(A, fn + ".csv")])
            add(fn, r, [x["sender_domain"] in LURE_DOMS for x in r])
        for fn in ("mail_url_clicks_city_airstation", "mail_url_clicks_brightwake"):
            r = read([os.path.join(A, fn + ".csv")])
            add(fn, r, [x["url_host"] in LURE_HOSTS for x in r])
        r = read([os.path.join(A, "account_logons_city_airstation.csv")])
        add("account_logons_city_airstation", r, [x["src_ip"] in STORY_IPS for x in r])
    elif name == "relations":
        relations(F, S)
    elif name == "registry":
        registry(F, S)
    return F, S


def bulk_company(tname, mail, F):
    """The wave is acceptable as a bulk mailing only if ordinary bulk mailings of similar size exist in the same log."""
    by = defaultdict(lambda: [0, set()])
    for r in mail:
        if r["direction"] == "inbound":
            by[r["sender_domain"]][0] += 1
            by[r["sender_domain"]][1].add(r["sender"])
    wave = [(d, v) for d, v in by.items() if d in LURE_DOMS and v[0] >= 100]
    for d, (n, senders) in wave:
        peers = [(x, v) for x, v in by.items() if x not in LURE_DOMS and v[0] >= 0.5 * n]
        many = [x for x, v in peers if len(v[1]) >= 0.5 * len(senders)]
        if len(peers) < 3 or len(many) < 2:
            F.append({"table": tname, "feature": "structure:bulk mailing without ordinary company", "story": n, "benign": len(peers), "need": 3,
                      "detail": f"{len(peers)} ordinary sender domains with at least half its volume, {len(many)} with at least half its sender count"})


def _t(s):
    return P.ts(s) if s else None


def relations(F, S):
    """Offsets between related records must look the same for story and ordinary records, and no story number may
    repeat in another table."""
    def compare(tname, label, story_off, benign_off):
        S[f"{tname}:{label}"] = {"story": len(story_off), "benign": len(benign_off)}
        if len(story_off) < 3 or len(benign_off) < 20:
            return
        b = sorted(benign_off)
        lo, hi = b[int(0.001 * len(b))], b[min(len(b) - 1, int(0.999 * len(b)))]
        outside = sum(1 for x in story_off if x < lo or x > hi)
        common, cnt = Counter(story_off).most_common(1)[0]
        share_b = sum(1 for x in benign_off if x == common) / len(benign_off)
        if outside > max(2, 0.3 * len(story_off)):
            F.append({"table": tname, "feature": f"time:{label}: story offsets outside the ordinary range", "story": outside, "benign": 0, "need": 1,
                      "detail": f"ordinary {lo}..{hi}; story {sorted(story_off)[:12]}"})
        if cnt >= max(3, 0.8 * len(story_off)) and share_b < 0.3:
            F.append({"table": tname, "feature": f"time:{label}: one fixed offset on story records", "story": cnt, "benign": int(share_b * len(benign_off)), "need": 1,
                      "detail": f"offset {common}"})

    # web request and the DNS lookup before it
    for org in ("city", "nascc", "brw"):
        d = defaultdict(list)
        for r in partner(org, "dns"):
            d[(r["client_ip"], r["query"])].append(_t(r["time_utc"]))
        so, bo = [], []
        for r in partner(org, "web"):
            ts_ = d.get((r["client_ip"], r["host"]))
            if not ts_:
                continue
            t = _t(r["time_utc"])
            prev = [x for x in ts_ if x <= t]
            if prev:
                (so if r["host"] in LURE_HOSTS else bo).append(t - max(prev))
        compare(f"{org}/web", "seconds from lookup to request", so, bo)
        # remote sign-on and its inbound firewall session
        fw = defaultdict(list)
        for r in partner(org, "firewall"):
            if r["src_zone"] == "internet" and r["action"] == "allow":
                fw[r["src_ip"]].append(_t(r["time_utc"]) - int(float(r["duration_s"] or 0)))
        so, bo = [], []
        for r in partner(org, "auth"):
            if r["logon_type"] == "remote" and r["src_ip"] in fw:
                t = _t(r["time_utc"])
                off = min((t - x for x in fw[r["src_ip"]]), key=abs)
                if abs(off) < 600:
                    (so if r["src_ip"] in STORY_IPS else bo).append(off)
        compare(f"{org}/auth", "seconds from inbound session start to sign-on", so, bo)
    # vendor gateway firewall session against the vessel session it carries
    ves = read([os.path.join(SRC, "telemetry", "vessel_cargo_control_remote_sessions.csv")])
    gw = defaultdict(list)
    for r in partner("brw", "firewall"):
        if r["action"] == "allow":
            gw[r["src_ip"]].append((_t(r["time_utc"]), float(r["duration_s"] or 0)))
    so, bo = [], []
    for r in ves:
        if r["result"] != "SUCCESS" or not r["logout_utc"]:
            continue
        end, dur = _t(r["logout_utc"]), int(r["duration_s"])
        cand = [(abs(e - end), int(round(du - dur))) for e, du in gw.get(r["src_ip"], []) if abs(e - end) < 120]
        if cand:
            (so if r["src_ip"] in STORY_IPS else bo).append(min(cand)[1])
    compare("vessel_sessions", "gateway firewall duration minus vessel session duration", so, bo)
    # click after the message; sign-on after the click: must not be on a grid
    for org in ("CITY", "NASCC"):
        offs = []
        for (tc, mb, h, _), (tsn, mb2, sip, _l) in zip(P.story_clicks(org), P.story_signons(org)):
            offs.append(int(tsn - tc))
        if offs and (all(o % 60 == 0 for o in offs) or all(o % 300 == 0 for o in offs)):
            F.append({"table": f"{org.lower()}/auth", "feature": "time:click to sign-on on a grid", "story": len(offs), "benign": 0, "need": 1})
    # a story number that repeats in another table
    vals = defaultdict(set)
    def note(tname, col, v):
        try:
            x = int(float(v))
        except (ValueError, TypeError):
            return
        if x >= 10000:
            vals[x].add(f"{tname}.{col}")
    for r in ves:
        if r["src_ip"] in STORY_IPS:
            note("vessel_sessions", "bytes_out", r["bytes_out"])
    for org in ("city", "nascc", "brw"):
        for r in partner(org, "mail"):
            if r["sender_domain"] in LURE_DOMS:
                note(f"{org}/mail", "size_bytes", r["size_bytes"])
        for r in partner(org, "web"):
            if r["host"] in LURE_HOSTS:
                note(f"{org}/web", "bytes_out", r["bytes_out"])
                note(f"{org}/web", "bytes_in", r["bytes_in"])
        for r in partner(org, "firewall"):
            if r["src_ip"] in STORY_IPS:
                note(f"{org}/firewall", "bytes_sent", r["bytes_sent"])
                note(f"{org}/firewall", "bytes_recv", r["bytes_recv"])
    per_table = Counter(w.split(".")[0] for where in vals.values() for w in where)
    for x, where in sorted(vals.items()):
        tables = {w.split(".")[0].split("/")[-1] for w in where}
        # only where chance is not an explanation: one of the tables has few story numbers at all
        if len(tables) > 1 and not tables <= {"firewall", "web", "mail"} and min(per_table[w.split(".")[0]] for w in where) <= 50:
            F.append({"table": "cross-table", "feature": f"number:story value {x} repeats", "story": len(where), "benign": 0, "need": 1, "detail": sorted(where)})


def registry(F, S):
    reg = json.load(open(os.path.join(ROOT, "06_data_streams", "partner_it_registry.json"), encoding="utf-8"))
    import ipaddress
    story_hosts = {h["host_id"] for org in ("CITY", "NASCC") for _, _, h, _ in P.story_clicks(org)} | {P.brw_ws(P.BRW_CLICK_PERSON)["host_id"]}
    n_hosts = 0
    for o in reg["organisations"]:
        hosts = o["hosts"]
        n_hosts += len(hosts)
        sites = {s["site_id"]: s for s in o.get("sites", [])}
        pat = Counter(re.sub(r"\d+", "9", h["hostname"]) for h in hosts)
        nusers = Counter(len(h.get("users", [])) for h in hosts if h.get("device_type") in ("workstation", "laptop", "shared workstation") or h.get("users"))
        for h in hosts:
            if h["host_id"] not in story_hosts:
                continue
            p = re.sub(r"\d+", "9", h["hostname"])
            if pat[p] < 5:
                F.append({"table": "partner_it_registry", "feature": f"structure:story host name shape {p}", "story": 1, "benign": pat[p] - 1, "need": 4})
            sub = sites.get(h.get("site_id"), {}).get("subnet")
            if sub and ipaddress.ip_address(h["ip"]) not in ipaddress.ip_network(sub):
                F.append({"table": "partner_it_registry", "feature": "structure:story host outside its site subnet", "story": 1, "benign": 0, "need": 1})
            k = len(h.get("users", []))
            if nusers[k] < 5:
                F.append({"table": "partner_it_registry", "feature": f"structure:story host with {k} users", "story": 1, "benign": nusers[k] - 1, "need": 4})
    S["partner_it_registry"] = {"rows": n_hosts, "story": len(story_hosts)}


def allowed(f):
    for tre, fre, reason in ALLOW:
        if re.search(tre, f["table"]) and re.search(fre, f["feature"]):
            if f["feature"].startswith("reuse:"):
                return reason if f["story"] > 0 else None
            if "takeovers" in f["table"] and "deposit_routing_number=" in f["feature"] and f["benign"] < 20:
                return None
            if f["benign"] >= 1 or f["feature"].startswith(("shape:", "exact:subject", "exact:sender")) or "login_ip_seen_before" in f["feature"] \
                    or "src_asn" in f["feature"] or "vendor_account" in f["feature"]:
                return reason
    return None


def main():
    args = sys.argv[1:]
    state = {}
    if "--fresh" in args and os.path.exists(STATE):
        os.remove(STATE)
    if os.path.exists(STATE):
        state = json.load(open(STATE))
    only = next((a.split("=", 1)[1].split(",") for a in args if a.startswith("--only=")), None)
    budget = float(next((a.split("=", 1)[1] for a in args if a.startswith("--budget=")), 100))
    t0 = time.time()
    if "--report" not in args:
        for gname in groups():
            if (only and gname not in only) or (not only and gname in state):
                continue
            if time.time() - t0 > budget:
                break
            f, s = run_group(gname)
            state[gname] = {"findings": f, "tables": s}
            os.makedirs(os.path.dirname(STATE), exist_ok=True)
            json.dump(state, open(STATE, "w"))
            print(f"scanned {gname}: {sum(v.get('rows', 0) for v in s.values()):,} rows, {len(f)} raw feature hit(s)  [{time.time() - t0:.0f}s]", flush=True)
    todo = [g for g in groups() if g not in state]
    findings, allow = [], []
    for gname, res in state.items():
        for f in res["findings"]:
            why = allowed(f)
            (allow if why else findings).append(dict(f, **({"allowed": why} if why else {})))
    by_table = Counter(f["table"] for f in findings)
    report = {"complete": not todo, "groups_scanned": sorted(state), "groups_to_do": todo, "findings": findings, "allowed": allow,
              "findings_by_table": dict(by_table), "allow_list": [{"table": a, "feature": b, "reason": c} for a, b, c in ALLOW],
              "tables": {t: s for res in state.values() for t, s in res["tables"].items()}}
    json.dump(report, open(OUT, "w"), indent=1)
    show = 80 if "--all" not in args else 100000
    for f in findings[:show]:
        print(f"  FINDING {f['table']:30s} {f['feature'][:100]:100s} story {f['story']:>7,} benign {f['benign']:>7,} (need {f['need']:,})")
    if len(findings) > show:
        print(f"  ... and {len(findings) - show} more (see the report)")
    print(f"allowed as genuine properties: {len(allow)} feature value(s) under {len(ALLOW)} allow-list entries")
    if todo:
        print(f"PARTIAL: {len(todo)} group(s) still to scan: {', '.join(todo)}. Run again.")
        return 3
    print(f"{'PASS' if not findings else 'FAIL'}: {len(findings)} finding(s) in {len(report['tables'])} tables")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
