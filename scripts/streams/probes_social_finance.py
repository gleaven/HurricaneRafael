"""Stream descriptions and probes for the social and financial family:
social_media, contracts, financial_transactions, aid_applications, insurance_claims, census.

Every probe reads the delivered files and re-derives the observation from them. Internal truth
files are used only to know which account, vendor or policy an observation is about.
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import re
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SOC = os.path.join(ROOT, "05_other_sources", "social_media")
PAY = os.path.join(ROOT, "05_other_sources", "payments")
CEN = os.path.join(ROOT, "05_other_sources", "census")
D0 = 1820880000
UTC = dt.timezone.utc
_c = {}


def J(rel):
    if rel not in _c:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            _c[rel] = json.load(fh)
    return _c[rel]


def R(path):
    if path not in _c:
        with open(path, encoding="utf-8", newline="") as fh:
            _c[path] = list(csv.DictReader(fh))
    return _c[path]


def T(s):
    """Epoch of an ISO string; a bare date means the end of that local day (so date-only records count for their day)."""
    s = s.strip()
    if len(s) == 10:
        return int(dt.datetime.fromisoformat(s).replace(tzinfo=UTC).timestamp()) + 86400 + 5 * 3600 - 60
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) if ("+" in s or s.endswith("Z")) else \
        int(dt.datetime.fromisoformat(s).replace(tzinfo=UTC).timestamp())


def tw_t(o):
    return dt.datetime.strptime(o["created_at"], "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=UTC).timestamp()


def local_day(t):
    off = -5 if t < 1825570800 else -6
    return int((t + off * 3600 - D0) // 86400)


# ---------------------------------------------------------------- social
def tweets():
    if "tw" not in _c:
        out = []
        for f in sorted(glob.glob(os.path.join(SOC, "*.jsonl"))):
            if os.path.basename(f).startswith("_"):
                continue
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    o = json.loads(line)
                    o["_t"] = tw_t(o)
                    o["_h"] = o["user"]["screen_name"]
                    o["_rt"] = "retweeted_status" in o
                    out.append(o)
        out.sort(key=lambda o: o["_t"])
        _c["tw"] = out
    return _c["tw"]


def net():
    if "net" not in _c:
        P, Tr = J("06_data_streams/personas.json"), J("06_data_streams/_internal/personas_truth.json")
        pid = {p["persona_id"]: p["handle"].lstrip("@") for p in P["personas"]}
        notes = J("06_data_streams/_internal/social_stream_notes.json")
        _c["net"] = {"t15": {pid[x] for x in Tr["networks"]["t15_47"]["persona_ids"]}, "b40": {pid[x] for x in Tr["networks"]["base_40"]["persona_ids"]},
                     "amp": {x.lstrip("@") for x in Tr["networks"]["removed_d38_847"]["amplifiers_800"]},
                     "wave2": {x.lstrip("@") for x in notes["second_wave_accounts"]}, "home": {p["handle"].lstrip("@"): p.get("home_area") for p in P["personas"]}}
        cols = P["accounts_compact"]["columns"]
        for row in P["accounts_compact"]["rows"]:
            r = dict(zip(cols, row))
            _c["net"]["home"][r["handle"].lstrip("@")] = r["home_area"]
    return _c["net"]


def between(a, b):
    a, b = T(a), T(b)
    return [o for o in tweets() if a <= o["_t"] < b]


def norm(text):
    text = re.sub(r"https://t\.co/\w+|#\w+|@\w+|^RT |[^a-z ]", " ", text.lower())
    for w in ("breaking", "psa", "sharing from a friend", "please rt", "heard this today", "wake up", "share", "pass it on", "rt", "spread the word", "they will delete this"):
        text = re.sub(rf"\b{w}\b", " ", text)
    return " ".join(text.split())


BLAME_RX = re.compile(r"#CBPWA\b|#CorpusChristiOUT|#CBPWAfail|#LightsOutCC|#SinLuzCC", re.I)
LEADS = ("TXCoastalWatchdog", "NuecesLocalNews")


def p_1501():
    n = net()
    created = {}
    for o in tweets():
        if o["_h"] in n["t15"] and o["_h"] not in created:
            created[o["_h"]] = tw_t({"created_at": o["user"]["created_at"]})
    a, b = T("2027-09-07T00:00Z"), T("2027-09-09T12:00Z")
    k = sum(1 for v in created.values() if a <= v <= b)
    return (len(created) == 47 and k == 31), f"{k} of {len(created)} of the pre-positioned accounts show user.created_at between 2027-09-07T00:00Z and 2027-09-09T12:00Z"


def p_1502():
    n = net()
    tw = [o for o in between("2027-09-09T05:00Z", "2027-09-13T05:00Z") if o["_h"] in n["t15"] and not o["_rt"]]
    shelter = [o for o in tw if "Zavala" in o["full_text"]]
    route = [o for o in tw if re.search(r"US-77|\b77\b", o["full_text"]) and "181" in o["full_text"]]
    a1 = [o for o in tw if o["_h"] == LEADS[0] and abs(o["_t"] - T("2027-09-09T14:32Z")) < 60 and "Zavala Elementary on Retta Dr IS open" in o["full_text"]]
    a2 = [o for o in tw if o["_h"] == LEADS[1] and abs(o["_t"] - T("2027-09-09T16:14Z")) < 60 and "US-77 near Victoria" in o["full_text"]]
    la = sum(1 for o in tw if o["_h"] == LEADS[0])
    lb = sum(1 for o in tw if o["_h"] == LEADS[1])
    ok = len(shelter) >= 60 and len(route) >= 40 and a1 and a2 and 18 <= la <= 28 and 15 <= lb <= 25
    return bool(ok), f"{len(shelter)} false-shelter and {len(route)} false-route posts from {len({o['_h'] for o in tw})} accounts; both sample posts present; lead accounts {la} and {lb} posts"


def p_1503():
    n = net()
    tw = [o for o in between("2027-09-12T16:19Z", "2027-09-12T18:38Z") if o["_h"] in n["t15"] and not o["_rt"] and "Zavala" in o["full_text"]]
    accts = {o["_h"] for o in tw}
    span = (tw[-1]["_t"] - tw[0]["_t"]) / 60 if tw else 0
    texts = Counter(norm(o["full_text"]) for o in tw)
    return (len(tw) == 34 and len(accts) == 11 and 135 <= span <= 138 and len(texts) <= 3), \
        f"{len(tw)} shelter posts from {len(accts)} accounts in {span:.0f} minutes on Sept. 12, {len(texts)} distinct wordings"


def p_1504():
    n = net()
    tw = [o for o in between("2027-09-14T06:00Z", "2027-09-17T05:00Z") if o["_h"] in n["t15"] and not o["_rt"] and BLAME_RX.search(o["full_text"] + " #CBPWA" * ("CBPWA" in o["full_text"]))]
    tw += [o for o in between("2027-09-14T06:00Z", "2027-09-17T05:00Z") if o["_h"] in LEADS and not o["_rt"] and o not in tw and re.search(r"McKinley|accountab|negligen", o["full_text"])]
    a1 = any(o["_h"] == LEADS[0] and abs(o["_t"] - T("2027-09-14T09:14Z")) < 60 and o["full_text"].startswith("Sources inside CBPWA telling me") for o in tw)
    a2 = any(o["_h"] == LEADS[1] and abs(o["_t"] - T("2027-09-14T11:47Z")) < 60 and "McKinley Substation transformer" in o["full_text"] for o in tw)
    seeds = sorted(o["_t"] for o in tw if o["_h"] in LEADS)
    within = 0
    for o in tw:
        prior = [s for s in seeds if 0 < o["_t"] - s <= 240]
        within += bool(prior)
    d0 = [o for o in tw if local_day(o["_t"]) == 0]
    la, lb = sum(1 for o in d0 if o["_h"] == LEADS[0]), sum(1 for o in d0 if o["_h"] == LEADS[1])
    share = within / max(1, len(tw))
    ok = a1 and a2 and 125 <= len(tw) <= 165 and share >= 0.55 and la == 31 and lb == 28
    return bool(ok), f"both sample posts present at 09:14Z and 11:47Z; {len(tw)} utility-blame posts from the accounts in the first three days, {share:.0%} within 240 s of a post by one of the two lead accounts; leads posted {la} and {lb} times on landfall day"


def p_0318():
    tw = [o for o in between("2027-09-15T05:00Z", "2027-09-25T12:00Z") if not o["_rt"] and re.search(r"lights? (hovering |again |over)|luces", o["full_text"], re.I)
          and re.search(r"base|air station|NAS|depot|hangar|flight line", o["full_text"], re.I)]
    nights = Counter(local_day(o["_t"] - 6 * 3600) for o in tw)
    big = sorted(d for d, c in nights.items() if c >= 8)
    return (len(big) == 6 and min(big) == 1), f"{len(tw)} posts about lights over the air station; nights with 8 or more posts: " + ", ".join((dt.date(2027, 9, 14) + dt.timedelta(days=d)).strftime("%b %d") for d in big)


def p_0309():
    n = net()
    tw = [o for o in between("2027-09-16T05:00Z", "2027-10-05T05:00Z") if o["_h"] in n["b40"] and not o["_rt"]]
    cls = Counter()
    for o in tw:
        x = o["full_text"]
        if re.search(r"seiz|requisition|taking over homes|clipboards|marking houses", x, re.I):
            cls["home seizures"] += 1
        elif re.search(r"wealthy|priority ZIP|country club|poor side|your neighborhood|nice subdivisions", x, re.I):
            cls["aid for the wealthy"] += 1
        elif re.search(r"RefineryNegligence|refinery|valves|whistleblower|terminal|tankers were told|Spill victims", x, re.I):
            cls["refinery negligence"] += 1
    total = sum(cls.values())
    lure = sum(1 for o in tw if any("aid-help-portal.example" in u["expanded_url"] for u in o["entities"]["urls"]))
    accts = {o["_h"] for o in tw}
    created = Counter(o["user"]["created_at"][4:10] + o["user"]["created_at"][-5:] for o in {o["_h"]: o for o in tw}.values())
    slots = Counter(int(o["_t"] // 60) % 15 for o in tw)
    top4 = sum(c for _, c in slots.most_common(8)) / max(1, len(tw))
    ok = 17100 <= total <= 18900 and len(accts) == 40 and len(cls) == 3 and lure / max(1, total) > 0.4 and top4 > 0.9
    return ok, (f"{total:,} rumour posts from {len(accts)} accounts ({dict(cls)}); {lure:,} link aid-help-portal.example; "
                f"{top4:.0%} posted in the same four two-minute windows of each quarter hour; {max(created.values())} of the accounts share one creation date")


def p_1505():
    n = net()
    tw = [o for o in between("2027-09-14T06:00Z", "2027-09-25T05:00Z") if BLAME_RX.search(o["full_text"])]
    bots = sum(1 for o in tw if o["_h"] in n["t15"])
    old = sum(1 for o in tw if o["_t"] - tw_t({"created_at": o["user"]["created_at"]}) > 90 * 86400)
    late = [o for o in between("2027-09-19T05:00Z", "2027-10-05T05:00Z") if o["_h"] in n["t15"] and not o["_rt"] and BLAME_RX.search(o["full_text"])]
    seeds = sorted(o["_t"] for o in late if o["_h"] in LEADS)
    foll = [o for o in late if o["_h"] not in LEADS]
    import bisect
    within = sum(1 for o in foll if (lambda i: i > 0 and o["_t"] - seeds[i - 1] <= 240)(bisect.bisect_left(seeds, o["_t"])))
    ok = 13500 <= len(tw) <= 14900 and 0.10 <= bots / len(tw) <= 0.16 and old / len(tw) >= 0.8 and within / max(1, len(foll)) >= 0.55
    return ok, (f"{len(tw):,} posts with the tracked utility-blame hashtags by Sept. 24; {bots:,} ({bots / len(tw):.1%}) from the pre-positioned accounts; "
                f"{old / len(tw):.0%} from accounts more than 90 days old; {within / max(1, len(foll)):.0%} of the accounts' posts from Sept. 19 follow a lead account within 240 s")


def p_1506():
    tw = tweets()
    a1 = any(o["_h"] == LEADS[0] and abs(o["_t"] - T("2027-10-05T19:52Z")) < 60 and o["full_text"].startswith("Convenient timing: CISA announces") for o in tw)
    base = [o for o in between("2027-09-19T05:00Z", "2027-10-04T05:00Z") if o["_h"] in LEADS and not o["_rt"]]
    after = [o for o in between("2027-10-05T18:30Z", "2027-10-09T05:00Z") if o["_h"] in LEADS and not o["_rt"]]
    quiet = [o for o in between("2027-09-25T05:00Z", "2027-10-05T17:00Z") if o["_h"] in LEADS and not o["_rt"]]
    r0, r1 = len(base) / 15.0, len(after) / 3.44
    ok = a1 and r1 >= 5 * r0 and len(quiet) / 10.5 <= 3
    return bool(ok), f"sample post present at 19:52Z on Oct. 5; the two lead accounts averaged {r0:.1f} posts a day Sept. 19 to Oct. 3, {len(quiet) / 10.5:.1f} a day in the 11 quiet days, then {r1:.1f} a day after the announcement ({r1 / max(r0, .01):.1f}x)"


def p_1508():
    p = os.path.join(SOC, "_platform_records_return.jsonl")
    if not os.path.exists(p):
        return False, "no platform records file"
    rows = [json.loads(x) for x in open(p, encoding="utf-8")]
    ips = defaultdict(set)
    for r in rows:
        ips[r["screen_name"]].add(r["source_ip"])
    ok = (ips.get(LEADS[0]) == {"198.51.47.112", "198.51.47.118", "198.51.47.203"} and ips.get(LEADS[1]) == {"198.51.48.44", "198.51.48.91"}
          and all(r["asn"] == 198765 and r["returned_utc"].startswith("2027-10-14T16:00") for r in rows)
          and min(r["event_utc"] for r in rows) >= "2027-09-09" and max(r["event_utc"] for r in rows) < "2027-10-07T05:00")
    return bool(ok), f"{len(rows)} access records returned 2027-10-14T16:00Z for the two lead accounts: {sorted(ips.get(LEADS[0], []))} and {sorted(ips.get(LEADS[1], []))}, all ASN 198765"


def p_1509():
    n = net()
    cut = T("2027-10-22T16:00Z")
    removed = (n["t15"] | n["amp"])
    after = [o for o in tweets() if o["_t"] >= cut and o["_h"] in removed]
    last = Counter()
    for o in between("2027-10-15T05:00Z", "2027-10-22T16:00Z"):
        if o["_h"] in removed:
            last[o["_h"]] += 1
    look = [json.loads(x) for x in open(os.path.join(SOC, "_account_lookup.jsonl"), encoding="utf-8")]
    susp = {r["screen_name"] for r in look if r.get("suspended")}
    ok = not after and len(susp) == 847 and removed <= susp and len(last) > 300
    return ok, f"no post from the removed accounts after 2027-10-22T16:00Z ({len(last)} of them posted in the week before); the account lookup returns 'suspended' for {len(susp)} accounts"


def p_0413():
    n = net()
    tw = [o for o in between("2027-10-28T05:00Z", "2027-10-30T05:00Z") if not o["_rt"] and re.search(r"explosion|boom|blast|explosión|estruendo|shook", o["full_text"], re.I)]
    pa = [o for o in tw if n["home"].get(o["_h"]) in ("Port Aransas", "Aransas Pass", "Ingleside", "Mustang Island")]
    first = min((o["_t"] for o in tw), default=0)
    ok = len(pa) >= 30 and first >= T("2027-10-28T06:10Z") and first <= T("2027-10-28T06:40Z")
    return ok, f"{len(tw)} posts about a blast, {len(pa)} from Port Aransas and neighbouring accounts; first at {dt.datetime.fromtimestamp(first, UTC):%H:%M:%SZ} on Oct. 28"


def p_0507():
    n = net()
    tw = [o for o in between("2027-11-28T06:00Z", "2027-12-09T06:00Z") if not o["_rt"] and re.search(r"contractors? (are |is )?(STEALING|stealing)|stolen|no-name debris|taking FEMA deposits|contractors' pockets|accounts emptied|drained", o["full_text"])]
    accts = Counter(o["_h"] for o in tw)
    core = {a for a, c in accts.items() if c >= 20}
    wave = [o for o in tw if o["_h"] in core]
    texts = Counter(norm(o["full_text"]) for o in wave)
    sched = Counter(o["source"] for o in wave)
    first = [o for o in between("2027-09-16T05:00Z", "2027-10-05T05:00Z") if o["_h"] in n["b40"] and not o["_rt"]]
    sched1 = Counter(o["source"] for o in first)
    slots = sum(1 for o in wave if (int(o["_t"] // 60) % 15) in (7, 8, 9)) / max(1, len(wave))
    same_client = set(sched) == set(sched1)
    ok = len(core) == 40 and core == n["wave2"] and len(wave) >= 1800 and len(texts) <= 12 and slots > 0.9 and same_client
    return ok, (f"{len(wave):,} posts claiming contractors are stealing aid from a cluster of {len(core)} accounts, {len(texts)} wordings, same quarter-hour slots and "
                f"posting clients as the first rumour network. They are not the original 40 handles: those were suspended on Oct. 22 "
                f"(the scenario says both; see 06_data_streams/_internal/social_stream_notes.json)")


def soc_time_range():
    tw = tweets()
    return tw[0]["_t"], tw[-1]["_t"]


def soc_ids():
    return {"@" + o["_h"] for o in tweets()}


def soc_registry():
    P = J("06_data_streams/personas.json")
    return {p["handle"] for p in P["personas"]} | {r[0] for r in P["accounts_compact"]["rows"]}


def soc_text():
    seen = set()
    for o in tweets():
        yield o["full_text"] + " " + " ".join(u["expanded_url"] for u in o["entities"]["urls"])
        if o["_h"] not in seen:
            seen.add(o["_h"])
            yield f"{o['user']['name']} {o['_h']} {o['user']['description']} {o['user']['location']}"


def soc_columns():
    o = tweets()[0]
    cols = set()
    for x in tweets()[::500]:
        cols |= set(x.keys()) | set(x["user"].keys())
    return sorted(c for c in cols if not c.startswith("_"))


# ---------------------------------------------------------------- contracts
def f_reg(): return R(os.path.join(PAY, "contracts_vendor_registry.csv"))
def f_aw(): return R(os.path.join(PAY, "contracts_awards.csv"))
def f_inv(): return R(os.path.join(PAY, "contracts_invoices.csv"))
def f_act(): return R(os.path.join(PAY, "contracts_actions.csv"))
def f_mon(): return R(os.path.join(PAY, "contracts_debris_monitoring.csv"))


def vend(name):
    return next(r for r in f_reg() if name in r["legal_name"])


def p_0105():
    a, b = vend("Vantorra"), vend("Quellmar")
    days = abs((dt.date.fromisoformat(a["registration_date"]) - dt.date.fromisoformat(b["registration_date"])).days)
    shared = [r["supplier_id"] for r in f_reg() if r["bank_account_id"] == a["bank_account_id"]]
    ok = days <= 7 and a["registered_address"] == b["registered_address"] and a["bank_account_id"] == b["bank_account_id"] and len(shared) == 2 \
        and a["registration_date"] == "2027-08-05"
    return ok, f"{a['supplier_id']} and {b['supplier_id']} registered {a['registration_date']} and {b['registration_date']}, both at '{a['registered_address']}', both paid to {a['bank_account_id']} (no other vendor uses it)"


def p_0311():
    v = vend("Vantorra")
    r = [x for x in f_aw() if x["supplier_id"] == v["supplier_id"]]
    ok = len(r) == 1 and r[0]["award_date"] == "2027-09-24" and float(r[0]["value_usd"]) == 14200000 and "sole source" in r[0]["procurement_method"]
    return ok, f"award {r[0]['piid']} on {r[0]['award_date']}: ${float(r[0]['value_usd']):,.0f}, {r[0]['procurement_method']}, to {v['legal_name']}" if r else "no award"


def p_0312():
    v = vend("Quellmar")
    r = [x for x in f_aw() if x["supplier_id"] == v["supplier_id"]]
    ok = len(r) == 1 and r[0]["award_date"] == "2027-09-26" and float(r[0]["value_usd"]) == 2100000 and "Naval Air Station" in r[0]["awarding_body"]
    return ok, f"award {r[0]['piid']} on {r[0]['award_date']}: ${float(r[0]['value_usd']):,.0f} from {r[0]['awarding_body']} to {v['legal_name']}" if r else "no award"


def p_0404():
    v = vend("Quellmar")
    inv = sorted((x for x in f_inv() if x["supplier_id"] == v["supplier_id"]), key=lambda x: x["invoice_date"])
    win = [x for x in inv if "2027-10-17" <= x["invoice_date"] <= "2027-10-29"]
    ok = inv and inv[0]["invoice_date"] >= "2027-10-17" and inv[0]["invoice_date"] <= "2027-10-19" and len(win) >= 3 and all(x["piid"] == inv[0]["piid"] for x in inv)
    return bool(ok), f"{len(inv)} invoices from {v['supplier_id']} against {inv[0]['piid']}, first dated {inv[0]['invoice_date']}; {len(win)} between Oct. 17 and Oct. 29" if inv else "no invoices"


def p_0505():
    v = vend("Vantorra")
    def ratio(sid, lo="2027-10-24", hi="2027-11-24"):
        billed = sum(float(x["quantity"]) for x in f_inv() if x["supplier_id"] == sid and x["unit"] == "ton" and lo <= x["period_end"] <= hi)
        est = defaultdict(list)
        for m in f_mon():
            if m["supplier_id"] == sid and lo <= m["period_end"] <= hi:
                est[(m["zone_id"], m["period_start"])].append(float(m["estimated_tons_removed"]))
        sup = sum(sum(x) / len(x) for x in est.values())
        return billed / sup if sup else float("nan"), billed, sup
    r, billed, sup = ratio(v["supplier_id"])
    others = [ratio(s)[0] for s in sorted({m["supplier_id"] for m in f_mon()} - {v["supplier_id"]})]
    ok = 2.15 <= r <= 2.45 and all(0.85 <= o <= 1.15 for o in others)
    return ok, f"{v['supplier_id']} billed {billed:,.0f} tons against {sup:,.0f} tons in the county's surveys for the same zones and weeks (ratio {r:.2f}); the other debris haulers run {min(others):.2f} to {max(others):.2f}"


def p_0506():
    v = vend("Quellmar")
    a = [x for x in f_act() if x["supplier_id"] == v["supplier_id"] and "2027-11-25" <= x["action_date"] <= "2027-11-28"]
    kinds = {x["action_type"] for x in a}
    held = [x for x in f_inv() if x["supplier_id"] == v["supplier_id"] and "withheld" in x["status"]]
    ok = "supplier suspended" in kinds and "product quality deficiency report" in kinds and held
    return bool(ok), "; ".join(f"{x['action_date']} {x['action_type']} ({x['authority']})" for x in a) + f"; {len(held)} invoices withheld"


def con_time_range():
    dates = [r["registration_date"] for r in f_reg()] + [r["award_date"] for r in f_aw()] + [r["invoice_date"] for r in f_inv()] + \
            [r["paid_date"] for r in f_inv() if r["paid_date"]] + [r["action_date"] for r in f_act()]
    return T(min(dates)) - 86400, T(max(dates))


def con_ids():
    s = {r["supplier_id"] for r in f_reg()} | {r["piid"] for r in f_aw()} | {r["bank_account_id"] for r in f_reg()} | {r["alternate_bank_account_id"] for r in f_reg()}
    s |= {r["supplier_id"] for r in f_inv()} | {r["piid"] for r in f_inv()} | {r["remit_bank_account_id"] for r in f_inv()} | {r["supplier_id"] for r in f_mon()} | {r["piid"] for r in f_act()}
    return {x for x in s if x}


def er_ids():
    E = J("06_data_streams/entity_registry.json")
    O = J("06_data_streams/organizations.json")
    return ({v["vendor_id"] for v in E["vendors"]} | {c["contract_id"] for c in E["contracts"]} | {a["account_id"] for a in E["accounts"]}
            | {p["policy_number"] for p in E["policies"]} | {i["insurer_id"] for i in E["insurers"]} | {a["adjuster_id"] for a in E["adjusters"]}
            | {m["merchant_id"] for m in E["prepaid_card_merchants"]} | {c["endpoint_id"] for c in E["crypto_endpoints"]}
            | {i["institution_id"] for i in E["financial_institutions"]} | {o["org_id"] for o in O["organizations"]}
            | {h["holder_id"] for h in E["policyholders"]} | {b["broker_id"] for b in E["brokers"]} | {a["appraiser_id"] for a in E["appraisers"]})


def csv_text(paths, cols):
    def gen():
        for p in paths:
            for r in R(p):
                yield " ".join(r.get(c, "") for c in cols)
    return gen


def header(path):
    with open(path, encoding="utf-8") as fh:
        return next(csv.reader(fh))


# ---------------------------------------------------------------- ledger
def f_ft(): return R(os.path.join(PAY, "financial_transactions.csv"))


CITY = {"Dallas, TX": (32.78, -96.80), "Fort Worth, TX": (32.75, -97.33), "Oklahoma City, OK": (35.47, -97.52), "El Paso, TX": (31.76, -106.49),
        "New Orleans, LA": (29.95, -90.07), "Shreveport, LA": (32.52, -93.75), "Arlington, TX": (32.74, -97.11), "Atlanta, GA": (33.75, -84.39),
        "Houston, TX": (29.76, -95.37), "San Antonio, TX": (29.42, -98.49), "Corpus Christi, TX": (27.80, -97.40)}


def km(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))


def recv_accounts():
    v = vend("Vantorra")
    return v["bank_account_id"], v["alternate_bank_account_id"]


def p_0503_ft():
    a71, a72 = recv_accounts()
    aid = [r for r in f_ft() if r["description"] == "disaster assistance payment" and "2027-11-17T06:00" <= r["timestamp"] < "2027-12-04T06:00"]
    by = defaultdict(float)
    for r in aid:
        by[r["account_id"]] += float(r["amount_usd"])
    total = sum(by.values())
    vq = {vend("Vantorra")["supplier_id"][4:], vend("Quellmar")["supplier_id"][4:]}
    pay = defaultdict(set)
    for r in f_ft():
        m = re.match(r"vendor payment INV-(\d{4})-", r["description"])
        if m and m.group(1) in vq and r["direction"] == "credit":
            pay[r["account_id"]].add(m.group(1))
    ok = len(by) == 3 and a71 in by and a72 in by and 3.78e6 <= total <= 4.02e6 and pay.get(a71) == vq and pay.get(a72) == vq
    return ok, f"${total:,.0f} in {len(aid)} disaster-assistance payments into {sorted(by)}; {a71} and {a72} also receive contract payments for both suppliers"


def p_0504():
    a71, a72 = recv_accounts()
    third = next(a for a in {r["account_id"] for r in f_ft() if r["description"] == "disaster assistance payment"} if a not in (a71, a72))
    buys = [r for r in f_ft() if r["account_id"] == third and r["description"] == "prepaid cards" and "2027-11-19T06:00" <= r["timestamp"] < "2027-12-04T06:00"]
    far = [r for r in buys if r["merchant_city"] in CITY and km(CITY["Corpus Christi, TX"], CITY[r["merchant_city"]]) > 300]
    funded = any(r["account_id"] == third and r["direction"] == "credit" and r["counterparty_id"] in (a71, a72) for r in f_ft())
    ok = len(buys) >= 300 and len(far) == len(buys) and funded
    cities = Counter(r["merchant_city"] for r in buys)
    return ok, f"{len(buys)} prepaid-card purchases (${sum(float(r['amount_usd']) for r in buys):,.0f}) from {third}, funded from the two other receiving accounts, all more than 300 km from Corpus Christi: {dict(cities.most_common(4))}..."


def ft_time_range():
    ts_ = [r["timestamp"] for r in f_ft()]
    return T(min(ts_)), T(max(ts_))


def ft_ids():
    return {r["account_id"] for r in f_ft()} | {r["counterparty_id"] for r in f_ft() if r["counterparty_id"]}


# ---------------------------------------------------------------- aid
def f_aid(): return R(os.path.join(PAY, "aid_applications.csv"))


def p_2206():
    rows = [r for r in f_aid() if r["record_type"] == "application" and r["source_ip"] == "198.51.100.44"]
    b = [sum(1 for r in rows if lo <= r["submitted_utc"] <= hi) for lo, hi in (("2027-11-13T06:01", "2027-11-13T09:17:59"), ("2027-11-14T01:00", "2027-11-14T04:45:59"), ("2027-11-15T23:00", "2027-11-15T23:59:59"))]
    photos = Counter(p for r in rows for p in r["damage_photo_hashes"].split(";") if p)
    zips = {r["zip"] for r in rows}
    ok = len(rows) == 94 and b == [31, 29, 34] and len(photos) == 23 and photos.get("CC-DAM-0014.jpg") == 7 and zips == {"78407"}
    return ok, f"{len(rows)} applications from 198.51.100.44 in bursts of {b}, ZIP {sorted(zips)}; {len(photos)} distinct damage photos, CC-DAM-0014.jpg used {photos.get('CC-DAM-0014.jpg')} times"


def p_0501():
    apps = [r for r in f_aid() if r["record_type"] == "application"]
    first = min(r["submitted_utc"] for r in apps)
    n = sum(1 for r in apps if r["submitted_utc"] < "2027-12-13T06:00")
    ok = first >= "2027-11-13T06:00" and first < "2027-11-13T12:00" and 45500 <= n <= 50500
    return ok, f"first application {first}; {n:,} applications by the end of Dec. 12"


def p_0503_aid():
    rows = f_aid()
    hij = [r for r in rows if r["record_type"] == "account_change" and r["field_changed"] == "direct deposit" and r["login_ip_seen_before"] == "N" and r["source_asn"] == "64512"]
    targets = Counter((r["deposit_routing_number"], r["deposit_account_masked"]) for r in hij)
    top = {k for k, c in targets.items() if c >= 50}
    apps = [r for r in rows if r["record_type"] == "application" and (r["deposit_routing_number"], r["deposit_account_masked"]) in top
            and "2027-11-13T06:00" <= r["submitted_utc"] < "2027-12-04T06:00"]
    dev, addr = Counter(r["device_id"] for r in apps), Counter(r["damaged_address"] for r in apps)
    ok = len(top) == 3 and len(apps) == 6 and len(dev) <= 2 and len(addr) <= 2
    return ok, f"{len(apps)} applications name the three accounts that the changed deposits point to; they use {len(dev)} devices and {len(addr)} addresses between them"


def p_0502():
    rows = f_aid()
    ch = [r for r in rows if r["record_type"] == "account_change" and r["field_changed"] == "direct deposit" and r["login_ip_seen_before"] == "N" and r["login_utc"]]
    targets = Counter((r["deposit_routing_number"], r["deposit_account_masked"]) for r in ch)
    top = {k for k, c in targets.items() if c >= 50}
    hij = [r for r in ch if (r["deposit_routing_number"], r["deposit_account_masked"]) in top]
    quick = sum(1 for r in hij if 0 < T(r["changed_utc"]) - T(r["login_utc"]) <= 1800)
    inwin = sum(1 for r in hij if "2027-11-15T06:00" <= r["changed_utc"] < "2027-11-24T06:00")
    ok = len({r["application_id"] for r in hij}) == 410 and quick == len(hij) and inwin == len(hij) and len(top) == 3
    return ok, f"direct-deposit details changed on {len({r['application_id'] for r in hij})} accounts between {min(r['changed_utc'] for r in hij)} and {max(r['changed_utc'] for r in hij)}, each within 30 minutes of a login from an address not seen before, all to the same three bank accounts"


def p_0601_aid():
    rows = f_aid()
    tr = {r["TRACT"]: r for r in R(os.path.join(CEN, "acs_nueces_tracts.csv"))}
    inc = sorted(float(r["B19013_001E"]) for r in tr.values())
    q1 = inc[len(inc) // 4]
    low = {t for t, r in tr.items() if float(r["B19013_001E"]) <= q1 and r["PREF_EVAC_ZONE"] in ("A", "B")}
    dol = defaultdict(float)
    for r in rows:
        if r["record_type"] == "determination" and r["status"] == "approved" and r["tract"] and "2027-11-13T06:00" <= r["event_utc"] < "2027-12-14T06:00":
            dol[r["tract"]] += float(r["amount_usd"])
    pop = {t: int(r["B01003_001E"]) for t, r in tr.items()}
    ds, ps = sum(dol[t] for t in low) / sum(dol.values()), sum(pop[t] for t in low) / sum(pop.values())
    ok = 0.4 <= ds / ps <= 0.62 and len(low) >= 6
    return ok, f"{len(low)} low-income surge-zone tracts hold {ps:.1%} of residents and received {ds:.1%} of approved aid dollars by Dec. 13 ({ds / ps:.2f} of their share)"


def aid_time_range():
    ts_ = [r["event_utc"] for r in f_aid()]
    return T(min(ts_)), T(max(ts_))


def aid_ids():
    return {r["area_id"] for r in f_aid() if r["area_id"]}


def area_ids():
    return {a["area_id"] for a in J("06_data_streams/areas.json")["areas"]}


# ---------------------------------------------------------------- claims
def f_cl(): return R(os.path.join(PAY, "insurance_claims.csv"))


def big_holder():
    c = Counter(r["holder_id"] for r in f_cl() if r["record_type"] == "policy_transaction" and r["transaction_type"].startswith("new business") and r["holder_id"])
    return c.most_common(1)[0]


def p_2201():
    hid, n = big_holder()
    tx = [r for r in f_cl() if r["record_type"] == "policy_transaction" and r["holder_id"] == hid]
    bound = [r["transaction_date"] for r in tx]
    orders = [r for r in tx if r["appraisal_order_id"]]
    ratio = sum(float(r["new_rcv_usd"]) for r in tx) / sum(float(r["county_assessed_value_usd"]) for r in tx)
    ok = (len(tx) == 230 and min(bound) >= "2027-08-05" and max(bound) <= "2027-09-07" and len(orders) == 230
          and all(r["appraisal_priority"] == "RUSH" and r["appraiser_initials"] == "RM" for r in orders)
          and min(r["appraisal_order_date"] for r in orders) >= "2027-08-01" and max(r["appraisal_order_date"] for r in orders) <= "2027-09-09"
          and len({r["broker_id"] for r in tx}) == 1 and len({r["appraiser_id"] for r in tx}) == 1 and ratio > 3)
    return ok, (f"{len(tx)} policies for holder {hid} bound {min(bound)} to {max(bound)} through one broker, each with an appraisal order marked RUSH "
                f"(initials RM, ordered {min(r['appraisal_order_date'] for r in orders)} to {max(r['appraisal_order_date'] for r in orders)}); insured value {ratio:.1f}x the county's assessed value")


def p_2202():
    hid, _ = big_holder()
    cl = [r for r in f_cl() if r["record_type"] == "claim" and r["holder_id"] == hid]
    win = [r for r in cl if "2027-09-17" <= r["filed_date"] <= "2027-10-15"]
    docs = Counter(r["estimate_document_id"] for r in cl)
    narr = Counter(r["damage_narrative_id"] for r in cl)
    top_n, top_c = narr.most_common(1)[0]
    photos = {p for r in cl if r["damage_narrative_id"] == top_n for p in r["photo_ids"].split(";")}
    vend_ = Counter(r["contractor_estimate_supplier_id"] for r in cl)
    ok = len(cl) == 187 and len(win) == 187 and len(docs) <= 30 and top_c == 47 and len(photos) <= 12 and len(vend_) == 2 and min(r["loss_date"] for r in cl) >= "2027-09-14"
    return ok, (f"{len(cl)} claims on that holder's policies, filed {min(r['filed_date'] for r in cl)} to {max(r['filed_date'] for r in cl)}; estimates from {len(vend_)} contractors "
                f"using {len(docs)} documents; {top_c} claims share one damage narrative and {len(photos)} photographs")


def p_0508():
    sp = [r for r in f_cl() if r["record_type"] == "claim" and r["claim_program"].startswith("oil spill")]
    win = [r for r in sp if "2027-11-13" <= r["filed_date"] <= "2027-12-12"]
    by115 = [r for r in sp if r["filed_date"] <= "2028-01-07"]
    cats = Counter(r["claimant_category"] for r in sp)
    ok = 4000 <= len(by115) <= 4400 and len(win) >= 0.7 * len(sp) and min(r["filed_date"] for r in sp) >= "2027-09-26"
    return ok, f"{len(by115):,} spill damage claims by Jan. 7, {len(win):,} of them filed Nov. 13 to Dec. 12; largest groups {dict(cats.most_common(3))}"


def cl_time_range():
    d = [r["transaction_date"] or r["filed_date"] for r in f_cl()] + [r["status_date"] for r in f_cl() if r["status_date"]]
    return T(min(d)) - 86400, T(max(d))


def cl_ids():
    s = set()
    for r in f_cl():
        s |= {r["policy_id"], r["insurer_id"], r["adjuster_id"], r["holder_id"], r["broker_id"], r["appraiser_id"], r["contractor_estimate_supplier_id"], r["payment_account_id"]}
    return {x for x in s if x}


# ---------------------------------------------------------------- census
def f_tr(): return R(os.path.join(CEN, "acs_nueces_tracts.csv"))
def f_ix(): return R(os.path.join(CEN, "nueces_tract_index.csv"))


def p_0101():
    tr = f_tr()
    need = ["B01003_001E", "B19013_001E", "B08201_001E", "B08201_002E"]
    ok = len(tr) == 56 and all(c in tr[0] for c in need) and all(int(r["B01003_001E"]) > 0 and float(r["B19013_001E"]) > 0 and 0 < int(r["B08201_002E"]) < int(r["B08201_001E"]) for r in tr)
    A = {a["tract"]: a for a in J("06_data_streams/areas.json")["areas"] if a["area_type"] == "census_tract"}
    agree = all(int(r["B01003_001E"]) == A[r["TRACT"]]["population"] and float(r["B19013_001E"]) == A[r["TRACT"]]["median_household_income"] for r in tr)
    return ok and agree, f"{len(tr)} tracts with population, median household income and households without a vehicle; values agree with areas.json"


def p_1407():
    ix = {r["TRACT"]: r for r in f_ix()}
    d34 = [r for r in f_tr() if ix[r["TRACT"]]["WATER_DISTRICT_AREA_ID"] in ("AREA-WD-3", "AREA-WD-4")]
    share = sum(int(r["S1601_C05_001E"]) for r in d34) / sum(int(r["S1601_C01_001E"]) for r in d34)
    rest = [r for r in f_tr() if r not in d34]
    other = sum(int(r["S1601_C05_001E"]) for r in rest) / sum(int(r["S1601_C01_001E"]) for r in rest)
    return (0.46 <= share <= 0.474 and len(d34) >= 6), f"{len(d34)} tracts in Water Districts 3 and 4: {share:.1%} of residents aged 5 and over speak English less than very well ({other:.1%} in the rest of the county)"


def p_0601_cen():
    tr = f_tr()
    inc = sorted(float(r["B19013_001E"]) for r in tr)
    q1, q3 = inc[len(inc) // 4], inc[3 * len(inc) // 4]
    low = [r for r in tr if float(r["B19013_001E"]) <= q1 and r["PREF_EVAC_ZONE"] in ("A", "B")]
    high = [r for r in tr if float(r["B19013_001E"]) >= q3]
    nv = lambda g: sum(int(r["B08201_002E"]) for r in g) / sum(int(r["B08201_001E"]) for r in g)
    ok = len(low) >= 6 and len(high) >= 10 and nv(low) > 2 * nv(high)
    return ok, f"income and vehicle fields separate {len(low)} low-income surge-zone tracts ({nv(low):.0%} of households without a vehicle) from {len(high)} high-income tracts ({nv(high):.0%})"


def cen_ids():
    return {r["AREA_ID"] for r in f_ix()} | {r["WATER_DISTRICT_AREA_ID"] for r in f_ix() if r["WATER_DISTRICT_AREA_ID"]} | {r["EVAC_ZONE_AREA_ID"] for r in f_ix()}


STREAMS = {
    "social_media": {"time_range": soc_time_range, "ids": soc_ids, "registry_ids": soc_registry, "public_voice": True, "text": soc_text, "columns": soc_columns},
    "contracts": {"time_range": con_time_range, "ids": con_ids, "registry_ids": er_ids, "public_voice": False,
                  "text": csv_text([os.path.join(PAY, f) for f in ("contracts_vendor_registry.csv", "contracts_awards.csv", "contracts_invoices.csv", "contracts_actions.csv")],
                                   ["legal_name", "description", "supplier_name", "registered_address"]),
                  "columns": lambda: sorted(set(sum((header(p) for p in glob.glob(os.path.join(PAY, "contracts*.csv"))), [])))},
    "financial_transactions": {"time_range": ft_time_range, "ids": ft_ids, "registry_ids": er_ids, "public_voice": False,
                               "text": csv_text([os.path.join(PAY, "financial_transactions.csv")], ["counterparty_name", "description"]),
                               "columns": lambda: header(os.path.join(PAY, "financial_transactions.csv"))},
    "aid_applications": {"time_range": aid_time_range, "ids": aid_ids, "registry_ids": area_ids, "public_voice": False,
                         "text": csv_text([os.path.join(PAY, "aid_applications.csv")], ["status", "field_changed", "assistance_type"]),
                         "columns": lambda: header(os.path.join(PAY, "aid_applications.csv"))},
    "insurance_claims": {"time_range": cl_time_range, "ids": cl_ids, "registry_ids": er_ids, "public_voice": False,
                         "text": csv_text([os.path.join(PAY, "insurance_claims.csv")], ["claimant_name", "loss_cause", "status", "transaction_type", "property_address"]),
                         "columns": lambda: header(os.path.join(PAY, "insurance_claims.csv"))},
    "census": {"ids": cen_ids, "registry_ids": area_ids, "public_voice": False, "columns": lambda: header(os.path.join(CEN, "acs_nueces_tracts.csv")) + header(os.path.join(CEN, "nueces_tract_index.csv"))},
}

PROBES = {
    ("EVT-1501", "social_media"): p_1501, ("EVT-1502", "social_media"): p_1502, ("EVT-1503", "social_media"): p_1503, ("EVT-1504", "social_media"): p_1504,
    ("EVT-0318", "social_media"): p_0318, ("EVT-0309", "social_media"): p_0309, ("EVT-1505", "social_media"): p_1505, ("EVT-1506", "social_media"): p_1506,
    ("EVT-1508", "social_media"): p_1508, ("EVT-1509", "social_media"): p_1509, ("EVT-0413", "social_media"): p_0413, ("EVT-0507", "social_media"): p_0507,
    ("EVT-0105", "contracts"): p_0105, ("EVT-0311", "contracts"): p_0311, ("EVT-0312", "contracts"): p_0312, ("EVT-0404", "contracts"): p_0404,
    ("EVT-0505", "contracts"): p_0505, ("EVT-0506", "contracts"): p_0506,
    ("EVT-0503", "financial_transactions"): p_0503_ft, ("EVT-0504", "financial_transactions"): p_0504,
    ("EVT-2206", "aid_applications"): p_2206, ("EVT-0501", "aid_applications"): p_0501, ("EVT-0503", "aid_applications"): p_0503_aid,
    ("EVT-0601", "aid_applications"): p_0601_aid, ("EVT-0502", "aid_applications"): p_0502,
    ("EVT-2201", "insurance_claims"): p_2201, ("EVT-2202", "insurance_claims"): p_2202, ("EVT-0508", "insurance_claims"): p_0508,
    ("EVT-0101", "census"): p_0101, ("EVT-1407", "census"): p_1407, ("EVT-0601", "census"): p_0601_cen,
}
