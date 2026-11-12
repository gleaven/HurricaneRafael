"""Self-description and probes for the ground emergency stream family (see scripts/check_streams.py).

Every probe reads the files on disk. Streams: cad_911, avl, sar_missions, shelters,
damage_assessment, eas_alerts, broadcast_logs, public_record.
"""
import collections
import csv
import datetime as dt
import glob
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "05_other_sources")
D0 = 1820880000
DST_END = 1825570800
UTC = dt.timezone.utc
_c = {}


# ---------------------------------------------------------------- helpers
def J(rel):
    if rel not in _c:
        _c[rel] = json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))
    return _c[rel]


def rows(rel_glob):
    if rel_glob not in _c:
        out = []
        for fp in sorted(glob.glob(os.path.join(SRC, rel_glob))):
            with open(fp, encoding="utf-8", newline="") as fh:
                out += list(csv.DictReader(fh))
        _c[rel_glob] = out
    return _c[rel_glob]


def header(rel_glob):
    cols = []
    for fp in sorted(glob.glob(os.path.join(SRC, rel_glob))):
        with open(fp, encoding="utf-8", newline="") as fh:
            for c in next(csv.reader(fh)):
                if c not in cols:
                    cols.append(c)
    return cols


def z(s):
    """Epoch of a UTC ISO string."""
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def loc(s):
    """Epoch of a local wall-clock string 'YYYY-MM-DD HH:MM[:SS]' (US Central)."""
    if not s:
        return None
    s = s.replace("T", " ")
    fmt = "%Y-%m-%d %H:%M:%S" if len(s) > 16 else ("%Y-%m-%d %H:%M" if len(s) > 10 else "%Y-%m-%d")
    naive = dt.datetime.strptime(s, fmt).replace(tzinfo=UTC).timestamp()
    return naive + (5 if naive + 5 * 3600 < DST_END else 6) * 3600


def day(t):
    off = -5 if t < DST_END else -6
    return (dt.datetime.fromtimestamp(t + off * 3600, UTC).date() - dt.date(2027, 9, 14)).days


def Zt(d, hhmm):
    h, m = map(int, hhmm.split(":"))
    return D0 + d * 86400 + h * 3600 + m * 60


def dist_m(a, b):
    dy = (b[0] - a[0]) * 110950.0
    dx = (b[1] - a[1]) * 111320.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dx, dy)


def cad():
    if "cad" not in _c:
        out = []
        for r in rows("911/cad_incidents_*.csv"):
            r = dict(r)
            r["t"] = loc(r["call_received_dttm"]); r["day"] = day(r["t"])
            r["arr"] = loc(r["first_arrival_dttm"]); r["disp"] = loc(r["dispatch_dttm"])
            r["lat"] = float(r["latitude"]); r["lon"] = float(r["longitude"])
            out.append(r)
        _c["cad"] = out
    return _c["cad"]


def by_day():
    if "by_day" not in _c:
        d = collections.defaultdict(list)
        for r in cad():
            d[r["day"]].append(r)
        _c["by_day"] = d
    return _c["by_day"]


def tracts():
    return {a["tract"]: a for a in J("06_data_streams/areas.json")["areas"] if a["area_type"] == "census_tract"}


def low_income_surge():
    return {t for t, a in tracts().items() if a.get("income_quartile") == 1 and a.get("evacuation_zone") in ("A", "B")}


def high_income():
    return {t for t, a in tracts().items() if a.get("income_quartile") == 4}


def tract_names(*names):
    return {t for t, a in tracts().items() if any(a["neighbourhood_name"].startswith(n) for n in names)}


def subs():
    a = {x["asset_id"]: x for x in J("06_data_streams/infrastructure_assets.json")["assets"]}
    return {k: (a[k]["latitude"], a[k]["longitude"]) for k in ("GW-FAC-SUB-02", "GW-FAC-SUB-03")}


def near_sub(r, radius=400):
    for k, c in subs().items():
        if dist_m(c, (r["lat"], r["lon"])) <= radius:
            return k
    return None


def subscribers():
    if "subs" not in _c:
        _c["subs"] = {r["callback_number"]: r for r in rows("911/reports/ali_subscriber_records.csv")}
    return _c["subs"]


def sub_calls(d0, d1):
    """Unfounded incidents within 400 m of SUB-02 or SUB-03 whose callback number is an unregistered prepaid line
    activated within 72 hours before 19:00Z (14:00 local) on D+7."""
    t7 = Zt(7, "19:00")
    out = []
    for r in cad():
        if d0 <= r["t"] < d1 and r["disposition_code"] == "UNFND":
            k = near_sub(r)
            s = subscribers().get(r["callback_number"])
            if k and s and s["service_plan"] == "PREPAID" and s["subscriber_registered"] == "N":
                act = z(s["activation_date"] + "T00:00:00Z")
                if t7 - 96 * 3600 <= act <= t7:
                    out.append((r, k))
    return out


def unit_ids():
    return {u["unit_id"] for u in J("06_data_streams/cad_units.json")["units"]}


def med(v):
    v = sorted(v)
    return v[len(v) // 2] if v else float("nan")


def ok(cond, detail):
    return bool(cond), detail


# ---------------------------------------------------------------- cad_911 probes
def p_0101():
    days = range(-30, -4)
    n = [len(by_day()[d]) for d in days]
    flagged = sum(1 for d in days for r in by_day()[d] if r["mutual_aid"] == "true" or r["sar_priority"] == "Y")
    m = sum(n) / len(n)
    return ok(295 <= m <= 325 and flagged == 0, f"mean {m:.0f} incidents a day 2027-08-15..09-09, {flagged} mutual-aid or rescue flags")


def p_0303():
    d1 = by_day()[1]
    L = low_income_surge()
    share = sum(1 for r in d1 if r["census_tract"] in L) / max(1, len(d1))
    return ok(abs(len(d1) - 2900) <= 60 and 0.59 <= share <= 0.63, f"{len(d1)} incidents on 2027-09-15; {share:.1%} from the {len(L)} low-income surge-zone tracts")


def p_0601():
    L, Hi = low_income_surge(), high_income()
    a = [r["arr"] - r["t"] for r in cad() if 0 <= r["day"] <= 45 and r["arr"] and r["census_tract"] in L]
    b = [r["arr"] - r["t"] for r in cad() if 0 <= r["day"] <= 45 and r["arr"] and r["census_tract"] in Hi]
    ratio = med(a) / med(b)
    return ok(1.9 <= ratio <= 2.3, f"median response {med(a) / 60:.1f} min (low-income surge tracts, n={len(a)}) vs {med(b) / 60:.1f} min (high-income, n={len(b)}): ratio {ratio:.2f}")


def p_1301():
    want = {(-1, 0): 14, (-1, 4): 31, (0, 6): 48, (0, 7): 67, (0, 9): 94, (0, 12): 76}
    got = {}
    for (dd, h), n in want.items():
        t0 = Zt(0, f"{h:02d}:00")
        got[h] = sum(1 for r in cad() if t0 <= r["t"] < t0 + 3600)
    hours_ok = all(abs(got[h] - n) <= 3 for (dd, h), n in want.items())
    total = len(by_day()[0])
    log = rows("911/reports/cbecc_shift_log.csv")
    surge = any(r["time_utc"].startswith("2027-09-14T06:15") and "surge protocol" in r["entry"] and "San Patricio" in r["entry"] for r in log)
    q = {r["time_utc"]: int(r["pending_calls_and_unassigned_incidents"]) for r in rows("911/reports/cbecc_queue_depth.csv")}
    peak = q.get("2027-09-14T10:30:00Z") == 180 and max(q.values()) == 180
    d0 = by_day()[0]
    medical = {"MEDEMER", "TRAUMAALS", "TRAUMABLS", "CARDIACAR", "STROKECVA", "MEDTRANSPT", "GENERCOP", "SUICIDETHRT", "WELLNESSMH"}
    water = {"WATERRESC", "FLOODING", "TRAPPEDVEH", "URBANSAR", "SAROPER"}
    pm = sum(1 for r in d0 if r["nature_code"] in medical) / total
    pw = sum(1 for r in d0 if r["nature_code"] in water) / total
    es = sum(1 for r in d0 if r["caller_language"] == "ES") / total
    cond = hours_ok and total == 1841 and surge and peak and 0.34 <= pm <= 0.42 and 0.23 <= pw <= 0.31 and 0.29 <= es <= 0.39
    return ok(cond, f"calls per hour (UTC) {got}; day total {total}; 06:15Z surge-protocol entry {surge}; queue 180 at 10:30Z {peak}; medical {pm:.0%}, water {pw:.0%}, Spanish {es:.0%}")


def p_1702_cad():
    a, b = Zt(0, "06:00"), Zt(0, "07:00")
    tagged = [r for r in cad() if a <= r["t"] < b and r["sar_priority"] == "Y"]
    fbnb = tract_names("Flour Bluff", "North Beach", "Rincon Point")
    inside = all(r["census_tract"] in fbnb for r in tagged)
    first = min((r["t"] for r in tagged), default=0)
    return ok(len(tagged) == 14 and inside and abs(first - Zt(0, "06:08")) <= 120,
              f"{len(tagged)} rescue-priority calls 06:00-07:00Z, all in Flour Bluff/North Beach tracts: {inside}; first at {dt.datetime.fromtimestamp(first, UTC):%H:%MZ}")


def p_0304_cad():
    a, b = Zt(1, "05:00"), Zt(3, "17:00")
    nb = tract_names("North Beach", "Rincon Point")
    win = [r for r in cad() if a <= r["t"] < b and r["arr"]]
    rn = [r["arr"] - r["t"] for r in win if r["census_tract"] in nb]
    ro = [r["arr"] - r["t"] for r in win if r["census_tract"] and r["census_tract"] not in nb]
    port = [r for r in cad() if a <= r["t"] < b and r["city"] == "PORTLAND"]
    ma = all(r["mutual_aid"] == "true" for r in port) and all(r["unit_id"].startswith("MA-") for r in port if r["unit_id"])
    units_nb = {r["unit_id"] for r in win if r["census_tract"] in nb and r["unit_id"]}
    ratio = med(rn) / med(ro)
    return ok(ratio >= 1.4 and len(port) >= 20 and ma,
              f"North Beach median response {med(rn) / 60:.0f} min vs {med(ro) / 60:.0f} min elsewhere (x{ratio:.1f}), units {sorted(units_nb)[:6]}; {len(port)} Portland incidents all mutual aid: {ma}")


def p_0318():
    fb = tract_names("Flour Bluff")
    nights = collections.Counter()
    for r in cad():
        if 1 <= r["day"] <= 11 and r["census_tract"] in fb and "LIGHTS" in r["narrative"] and re.search(r"NAS|BASE|AIR STATION|DEPOT", r["narrative"]):
            h = dt.datetime.fromtimestamp(r["t"] - 5 * 3600, UTC).hour
            if h >= 21 or h < 3:
                nights[day(r["t"] - 6 * 3600)] += 1
    return ok(len(nights) == 6 and min(nights) == 1 and max(nights) <= 10, f"night calls about lights over the air station on local nights D+{sorted(nights)}: {dict(sorted(nights.items()))}")


def p_1302_cad():
    d1, d2 = by_day()[1], by_day()[2]
    resc = sum(1 for r in d2 if r["sar_priority"] == "Y")
    return ok(abs(len(d1) - 2900) <= 60 and abs(len(d2) - 2600) <= 60 and resc == 2109, f"{len(d1)} incidents on D+1, {len(d2)} on D+2 of which {resc} rescue-priority")


def p_1707_cad():
    want = {f"SAR-27-{n:05d}" for n in range(1428, 1439)}
    rs = [r for r in cad() if r["sar_case_number"] in want]
    cond = len(rs) == 11 and all(7 <= r["day"] <= 10 for r in rs) and all(r["disposition_code"] == "UNFND" for r in rs) and all(near_sub(r, 400) for r in rs)
    return ok(cond, f"{len(rs)} incidents SAR-27-01428..01438, days {sorted({r['day'] for r in rs})}, all unfounded, all within 0.4 km of SUB-02/SUB-03: {all(near_sub(r, 400) for r in rs)}")


def p_1303_cad():
    sel = sub_calls(Zt(7, "19:00"), Zt(7, "23:00"))
    by = collections.Counter(k for r, k in sel)
    kinds = collections.Counter("gas" if r["nature_code"] == "GASLEAK" else "collapse" if r["nature_code"] == "ROOFCOLLAP" else "flooding" for r, k in sel)
    nums = {r["callback_number"] for r, k in sel}
    cond = len(sel) == 9 and by["GW-FAC-SUB-02"] == 5 and by["GW-FAC-SUB-03"] == 4 and kinds == {"gas": 4, "collapse": 3, "flooding": 2} and len(nums) == 9
    return ok(cond, f"{len(sel)} unfounded incidents 19:00-23:00Z on D+7 near the substations ({dict(by)}), types {dict(kinds)}, {len(nums)} distinct prepaid numbers activated within 72 h")


def p_1304_cad():
    late = sub_calls(Zt(8, "05:00"), Zt(11, "05:00"))
    allc = sub_calls(Zt(7, "05:00"), Zt(11, "05:00"))
    after = sub_calls(Zt(11, "05:00"), Zt(25, "05:00"))
    by = collections.Counter(k for r, k in allc)
    nums = {r["callback_number"] for r, k in allc}
    carr = collections.Counter(r["ali_carrier"] for r, k in allc)
    cond = len(late) == 14 and len(allc) == 23 and by["GW-FAC-SUB-02"] == 13 and by["GW-FAC-SUB-03"] == 10 and len(nums) == 23 and not after and sorted(carr.values()) == [6, 8, 9]
    return ok(cond, f"{len(late)} more on D+8..D+10, {len(allc)} in all ({dict(by)}), {len(nums)} distinct numbers, carriers {sorted(carr.values())}, {len(after)} after D+10")


def p_1305_cad():
    d12 = by_day()[12]
    ws = [r for r in cad() if r["nature_code"] == "WATERSAFE"]
    first = min(r["t"] for r in ws)
    share = sum(1 for r in d12 if r["nature_code"] == "WATERSAFE") / len(d12)
    mis = sum(1 for r in d12 if Zt(12, "22:30") <= r["t"] < Zt(12, "23:05") and r["nature_code"] == "FLOODING")
    return ok(len(d12) == 1623 and abs(first - Zt(12, "23:05")) < 600 and first >= Zt(12, "23:05") and 0.22 <= share <= 0.26 and mis >= 140,
              f"{len(d12)} incidents on D+12; WATER-SAFETY-INQUIRY first appears {dt.datetime.fromtimestamp(first, UTC):%Y-%m-%d %H:%MZ} and takes {share:.0%}; {mis} FLOODING entries 22:30-23:05Z")


def p_1307():
    n = {d: len(by_day()[d]) for d in range(0, 29)}
    avg = lambda a, b: sum(n[d] for d in range(a, b + 1)) / (b - a + 1)
    vol = rows("911/reports/cbecc_daily_call_volume.csv")
    s28 = sum(int(r["calls_all_lines"]) for r in vol if "2027-09-14" <= r["date_local"] <= "2027-10-12")
    ma = sum(int(r["mutual_aid_dispatcher_hours"]) for r in vol)
    log = any("44,291" in r["entry"] and "2,140 dispatcher-hours" in r["entry"] for r in rows("911/reports/cbecc_shift_log.csv"))
    cond = (n[0] == 1841 and abs(n[1] - 2900) <= 60 and abs(n[2] - 2600) <= 60 and abs(avg(3, 6) - 1620) <= 15 and n[7] == 1580 and n[8] == 1490
            and abs(avg(9, 11) - 1420) <= 15 and n[12] == 1623 and abs(n[13] - 1400) <= 40 and abs(n[27] - 390) <= 20 and n[28] == 380 and s28 == 44291 and ma == 2140 and log)
    return ok(cond, f"daily profile D0 {n[0]}, D+1 {n[1]}, D+2 {n[2]}, D+3-6 avg {avg(3, 6):.0f}, D+7 {n[7]}, D+8 {n[8]}, D+9-11 avg {avg(9, 11):.0f}, D+12 {n[12]}, D+13 {n[13]}, D+27 {n[27]}, D+28 {n[28]}; "
                    f"calls on all lines D0..D+28 {s28}; mutual-aid dispatcher-hours {ma}; after-action entry {log}")


def p_0413():
    rs = [r for r in cad() if Zt(44, "06:10") <= r["t"] < Zt(44, "07:00") and r["nature_code"] == "EXPLOSION" and r["city"] == "PORT ARANSAS"]
    return ok(len(rs) >= 8, f"{len(rs)} explosion calls from Port Aransas 06:10-07:00Z on 2027-10-28, first {min((r['call_received_dttm'] for r in rs), default='')} local")


def p_1308():
    vol = rows("911/reports/cbecc_daily_call_volume.csv")
    s45 = sum(int(r["calls_all_lines"]) for r in vol if "2027-09-14" <= r["date_local"] <= "2027-10-29")
    rs = [r for r in cad() if 0 <= r["day"] <= 45]
    en = 100 * sum(1 for r in rs if r["caller_language"] == "EN") / len(rs)
    es = 100 * sum(1 for r in rs if r["caller_language"] == "ES") / len(rs)
    n45 = len(by_day()[45])
    tip = any("1-800-NUECES-9" in r["entry"] for r in rows("911/reports/cbecc_shift_log.csv"))
    return ok(s45 == 56793 and abs(en - 64.8) <= 1.5 and abs(es - 34.1) <= 1.5 and n45 == 311 and tip,
              f"calls on all lines D0..D+45 {s45}; English {en:.1f}%, Spanish {es:.1f}%; {n45} incidents on D+45; tip-line entry {tip}")


# ---------------------------------------------------------------- avl probes
def avl_rows():
    if "avl" not in _c:
        out = []
        for fp in sorted(glob.glob(os.path.join(SRC, "avl", "*.csv"))):
            with open(fp, encoding="utf-8") as fh:
                next(fh)
                for line in fh:
                    p = line.rstrip("\n").split(",")
                    out.append((p[0], p[1], float(p[3]), float(p[4]), p[7], p[8]))
        _c["avl"] = out
    return _c["avl"]


def bridge_spans():
    a = {x["asset_id"]: x for x in J("06_data_streams/infrastructure_assets.json")["assets"]}
    return [((a["FAC-INF-01A"]["latitude"], a["FAC-INF-01A"]["longitude"]), 900.0), ((a["FAC-INF-01B"]["latitude"], a["FAC-INF-01B"]["longitude"]), 2800.0)]


def on_crossing(points):
    """Subset of (lat, lon) points that are over water inside one of the two crossings' spans."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import geo
    if "geo" not in _c:
        _c["geo"] = geo.Geo(build_roads=False)
    G = _c["geo"]
    spans = bridge_spans()
    cand = [p for p in points if any(dist_m(c, p) <= rad for c, rad in spans)]
    if not cand:
        return []
    land = G.is_land_many([p[0] for p in cand], [p[1] for p in cand])
    return [p for p, l in zip(cand, land) if not l]


def p_0304_avl():
    a, b = "2027-09-14T05:00:00Z", "2027-09-17T17:00:00Z"       # closure through the D+3 reopening at 12:00 local
    during = on_crossing({(r[2], r[3]) for r in avl_rows() if a <= r[0] < b})
    before = on_crossing({(r[2], r[3]) for r in avl_rows() if "2027-08-20T00:00:00Z" <= r[0] < "2027-09-10T00:00:00Z"})
    after = on_crossing({(r[2], r[3]) for r in avl_rows() if "2027-09-18T05:00:00Z" <= r[0] < "2027-10-05T00:00:00Z"})
    staged = {r[1] for r in avl_rows() if a <= r[0] < b and 27.8136 <= r[2] <= 27.8366 and -97.3974 <= r[3] <= -97.3797 and r[4] in ("ENR", "ONS")}
    return ok(not during and before and after and staged,
              f"{len(during)} fixes on the Harbor Bridge or Nueces Bay Causeway from the storm to the D+3 reopening (before: {len(before)} distinct fixes, after: {len(after)}); units working North Beach from their own side: {sorted(staged)}")


def p_1707_avl():
    want = {f"SAR-27-{n:05d}" for n in range(1428, 1439)}
    incs = {r["incident_number"]: r for r in cad() if r["sar_case_number"] in want}
    ends = collections.defaultdict(list)
    for r in avl_rows():
        if r[5] in incs and r[4] == "ONS":
            ends[r[5]].append((r[2], r[3]))
    near = sum(1 for k, pts in ends.items() if all(any(dist_m(c, p) <= 450 for c in subs().values()) for p in pts))
    return ok(len(ends) >= 9 and near == len(ends), f"{len(ends)} of 11 responding units leave an on-scene track; {near} end within 450 m of SUB-02 or SUB-03")


# ---------------------------------------------------------------- SAR probes
def sar():
    return rows("sar/sar_missions.csv")


def alog():
    return rows("sar/sar_asset_log.csv")


def p_1701():
    L = alog()
    dep = any(r["time_utc"] == "2027-09-13T19:22:00Z" and "TF1-CC-0913" in r["note"] and "4 VEHICLES" in r["note"] for r in L)
    arr = any(r["time_utc"] == "2027-09-13T23:47:00Z" and r["status"] == "STAGED" and "ROBSTOWN" in r["location"] for r in L)
    deck = {r["asset_id"] for r in L if r["time_utc"] == "2027-09-13T19:15:00Z" and r["status"] == "ON DECK" and "CREW REST WAIVER" in r["note"]}
    boats = {r["asset_id"] for r in L if r["status"] == "READY" and r["asset_id"].startswith("CC-SAR-") and r["time_utc"] < "2027-09-14T00:00:00Z"}
    return ok(dep and arr and deck == {"CG-6033", "CG-6041"} and len(boats) == 23,
              f"convoy TF1-CC-0913 departs 14:22 and stages at Robstown 18:47 local: {dep and arr}; on deck 19:15Z: {sorted(deck)}; {len(boats)} boats fueled and manifested")


def p_1708():
    S = sar()
    res = [r for r in S if r["outcome"] == "RESCUED"]
    nf = [r for r in S if r["outcome"] == "NO VICTIM FOUND"]
    cases = {r["case_number"] for r in res}
    full = all(r["on_scene_utc"] and r["latitude"] and r["asset_type"] for r in res)
    return ok(len(res) == 1427 and cases == {f"SAR-27-{n:05d}" for n in range(1, 1428)} and len(nf) == 11 and full,
              f"{len(res)} rescues with time, position and resource type (cases SAR-27-00001..01427: {len(cases) == 1427}), {len(nf)} no-find checks")


def p_1702_sar():
    S = sorted((r for r in sar() if r["outcome"] == "RESCUED"), key=lambda r: r["on_scene_utc"])
    f = S[0]
    fb = tract_names("Flour Bluff")
    first_launch = min(r["launch_utc"] for r in sar())
    return ok(first_launch == "2027-09-14T06:22:00Z" and f["asset_id"] == "CG-6033" and f["on_scene_utc"] == "2027-09-14T06:51:00Z" and f["method"] == "HOIST" and f["census_tract"] in fb,
              f"first launch {first_launch} by {f['asset_id']}; first rescue {f['on_scene_utc']} {f['method']} at {f['address']}")


def p_1302_sar():
    tf = {r["mission_id"] for r in sar() if r["asset_id"].startswith("TF1") and Zt(2, "05:00") <= z(r["launch_utc"]) < Zt(3, "05:00")}
    n = sum(1 for r in sar() if r["outcome"] == "RESCUED" and Zt(1, "05:00") <= z(r["on_scene_utc"]) < Zt(3, "05:00"))
    return ok(len(tf) == 22 and n == 847, f"{len(tf)} Task Force 1 swift-water deployments on D+2; {n} persons rescued across D+1 and D+2")


def p_1703():
    S = sar()
    a, b = Zt(1, "05:00"), Zt(2, "05:00")
    so = collections.defaultdict(set)
    for r in S:
        if r["asset_type"] == "helicopter" and a <= z(r["launch_utc"]) < b:
            so[r["asset_id"]].add(r["mission_id"])
    air = sum(1 for r in S if r["asset_type"] == "helicopter" and r["outcome"] == "RESCUED" and z(r["on_scene_utc"]) <= Zt(1, "20:00"))
    cal = tract_names("Calallen")
    tf = sum(1 for r in S if r["asset_id"].startswith("TF1") and r["census_tract"] in cal and a <= z(r["on_scene_utc"]) < b)
    cond = len(so["CG-6033"]) == 7 and len(so["CG-6041"]) == 6 and so["N110TX"] and so["N3941A"] and air == 341 and tf > 0
    return ok(cond, f"D+1 sorties: " + ", ".join(f"{k} {len(v)}" for k, v in sorted(so.items())) + f"; {air} survivors by air by 20:00Z D+1; {tf} Task Force 1 boat rescues in Calallen")


def p_1704():
    s = rows("sar/flood_depth_soundings.csv")
    d = [float(r["depth_ft"]) for r in s]
    inwin = all("2027-09-16T12:00:00Z" <= r["time_utc"] <= "2027-09-16T14:00:00Z" for r in s)
    ext = [r for r in rows("sar/flood_extent_snapshots.csv") if r["time_utc"] == "2027-09-16T15:00:00Z" and float(r["value"]) == 68]
    return ok(len(s) == 23 and min(d) == 0.8 and max(d) == 3.4 and inwin and {r["water_district"] for r in s} <= {"3", "4"} and ext,
              f"{len(s)} manual soundings 12:00-14:00Z D+2 in Districts 3 and 4, {min(d)}-{max(d)} ft; 15:00Z extent snapshot 68 percent above 1.5 ft: {bool(ext)}")


def p_1705():
    S = sar()
    a, b = Zt(3, "05:00"), Zt(6, "05:00")
    late_air = sum(1 for r in S if r["asset_type"] == "helicopter" and z(r["on_scene_utc"]) >= Zt(3, "08:00"))
    civ = {r["asset_id"] for r in S if r["asset_type"] == "civilian_boat" and a <= z(r["on_scene_utc"]) < b}
    civ_before = sum(1 for r in S if r["asset_type"] == "civilian_boat" and z(r["on_scene_utc"]) < a)
    note = any("CG-6033 RETURNS TO ROUTINE TASKING" in r["note"] and "87" in r["note"] for r in alog())
    return ok(late_air == 0 and len(civ) == 87 and civ_before == 0 and note, f"no helicopter rescues after 03:00 local D+3; {len(civ)} civilian boats on D+3..D+5 (none before); phase-change entry {note}")


def p_1706():
    last = max(r["on_scene_utc"] for r in sar() if r["outcome"] == "RESCUED")
    row = [r for r in alog() if r["time_utc"] == "2027-09-19T22:00:00Z" and r["status"] == "LOG CLOSED" and "1,427" in r["note"] and "SAR-27-00001" in r["note"] and "SAR-27-01427" in r["note"]]
    return ok(bool(row) and last <= "2027-09-19T22:00:00Z", f"log-closed entry at 22:00Z D+5: {bool(row)}; last rescue {last}")


def p_1707_sar():
    nf = [r for r in sar() if r["outcome"] == "NO VICTIM FOUND"]
    cond = len(nf) == 11 and all(r["asset_id"].startswith("WC-") for r in nf) and all(7 <= day(z(r["on_scene_utc"])) <= 10 for r in nf)
    return ok(cond, f"{len(nf)} no-find cases, units {sorted({r['asset_id'] for r in nf})}, days {sorted({day(z(r['on_scene_utc'])) for r in nf})}")


def p_1303_sar():
    L = [r for r in alog() if r["asset_id"].startswith("TF1") and r["status"] == "DISPATCHED" and "2027-09-21T19:30:00Z" <= r["time_utc"] <= "2027-09-21T23:45:00Z"]
    back = [r for r in alog() if r["asset_id"].startswith("TF1") and r["status"] == "AVAILABLE" and "NOTHING FOUND" in r["note"] and "2027-09-21T19:30:00Z" <= r["time_utc"] <= "2027-09-21T23:45:00Z"]
    elems = {r["crew_element"] for r in L}
    d4 = tract_names("Hillcrest", "Port/Channel", "Bayfront Downtown")
    q = [r for r in cad() if Zt(7, "19:30") <= r["t"] < Zt(7, "23:45") and r["census_tract"] in d4 and r["unit_id"].startswith("TF1") and r["disp"]]
    w = sum(r["disp"] - r["t"] for r in q) / 3600 / max(1, len(q))
    return ok(elems == {"Alpha-7", "Bravo-3", "Charlie-2", "Delta-5"} and len(back) == 4 and len(q) == 6 and abs(w - 4.3) <= 0.2,
              f"teams {sorted(elems)} sent 19:30-23:45Z, {len(back)} returned with nothing found; {len(q)} District 4 requests waited {w:.1f} h on average for a swift-water team")


def p_1304_sar():
    L = [r for r in alog() if r["asset_id"].startswith("TF1") and r["status"] == "DISPATCHED" and "2027-09-22T05:00:00Z" <= r["time_utc"] < "2027-09-25T05:00:00Z"]
    out = {(r["asset_id"], r["crew_element"], r["incident_number"]): z(r["time_utc"]) for r in alog() if r["asset_id"].startswith("TF1") and r["status"] == "DISPATCHED"}
    hrs = 0.0
    for r in alog():
        k = (r["asset_id"], r["crew_element"], r["incident_number"])
        if r["status"] == "AVAILABLE" and "NOTHING FOUND" in r["note"] and k in out:
            hrs += (z(r["time_utc"]) - out[k]) / 3600
    nf = [r for r in sar() if r["outcome"] == "NO VICTIM FOUND" and z(r["on_scene_utc"]) >= Zt(8, "05:00")]
    return ok(len(L) == 2 and 4.0 <= hrs <= 6.0 and len(nf) >= 6, f"{len(L)} more team diversions on D+8, none after; {hrs:.1f} team-hours lost in all; {len(nf)} further no-find checks D+8..D+10")


# ---------------------------------------------------------------- shelters
def p_1502():
    regs = rows("shelters/shelter_registry.csv")
    fac = {f["facility_id"]: f for f in J("06_data_streams/facility_registry.json")["facilities"]}
    txt = " ".join(" ".join(r.values()) for g in ("shelters/shelter_registry.csv", "shelters/shelter_daily_census.csv") for r in rows(g))
    official = all(fac.get(r["facility_id"], {}).get("facility_type_code") == "SHELTER" for r in regs)
    open_d2 = sorted(r["facility_name"] for r in regs if r["opened_local"].startswith("2027-09-12"))
    return ok("Zavala" not in txt and official and len(open_d2) >= 4, f"registry lists {len(regs)} county shelters, none is Zavala Elementary; open on 2027-09-12: {open_d2}")


def p_1403_shel():
    c = [r for r in rows("shelters/shelter_211_calls.csv") if "2027-09-13 14:00:00" <= r["call_time_local"] < "2027-09-13 20:00:00"
         and r["caller_evacuation_zone"] == "D" and r["topic"] == "SHELTER LOCATION CLARIFICATION"]
    other = [r for r in rows("shelters/shelter_211_calls.csv") if r["topic"] == "SHELTER LOCATION CLARIFICATION" and r not in c]
    return ok(len(c) == 14 and not other, f"{len(c)} Zone D calls asking which shelter between 14:00 and 20:00 local on 2027-09-13 ({len(other)} at other times)")


# ---------------------------------------------------------------- damage assessment
def p_1101():
    r = [x for x in rows("infrastructure/aerial_survey/collection_index.csv") if x["start_utc"] == "2027-09-12T14:00:00Z" and x["tiles"] == "847" and "94 percent" in x["coverage"]]
    return ok(bool(r), f"pre-event baseline collection {r[0]['collection_id'] if r else None}: 847 tiles, about 94 percent of utility infrastructure")


def p_1104():
    ai = [r for r in rows("infrastructure/damage_assessment.csv") if r["ASMT_TYPE"] == "AI"]
    c = collections.Counter(r["DMG_LEVEL"] for r in ai)
    dates = sorted({r["ASMT_DATE"][:10] for r in ai})
    return ok(c["MAJ"] == 2100 and c["DST"] == 390 and dates[0] >= "2027-09-17" and dates[-1] <= "2027-09-19",
              f"automated classification {dates[0]}..{dates[-1]}: {c['MAJ']} major, {c['DST']} destroyed of {len(ai)} structures")


def p_1105():
    # the record carries the start of the site's tile-set acquisition (drone flight log), inside the observation window
    r = [x for x in rows("infrastructure/utility_site_survey.csv") if x["asset_id"] == "GW-FAC-SUB-02" and x["phase"] == "PHASE 2 UTILITY"
         and "2027-09-22T10:30:00Z" <= x["survey_time_utc"] <= "2027-09-22T12:30:00Z"]
    cond = len(r) == 1 and r[0]["yard_flood_status"] == "RECEDED" and "B2-A" in r[0]["equipment_observation"] and "OPEN" in r[0]["equipment_observation"] and "NO VISIBLE STORM DAMAGE" in r[0]["visible_condition"]
    return ok(cond, f"SUB-02 Phase 2 record {r[0]['survey_time_utc'] if r else None} (tile set {r[0]['tile_set_id'] if r else None}): flood {r[0]['yard_flood_status'] if r else None}; "
                    f"{r[0]['equipment_observation'] if r else None}; {r[0]['visible_condition'] if r else None}")


def p_1106():
    c = [x for x in rows("infrastructure/aerial_survey/collection_index.csv") if x["start_utc"] == "2027-09-25T09:15:00Z" and "THERMAL" in x["phase"]]
    s = [x for x in rows("infrastructure/utility_site_survey.csv") if x["phase"] == "THERMAL PASS"]
    return ok(bool(c) and len(s) >= 5, f"thermal infrared collection at 09:15Z D+11 over the utility corridor; {len(s)} site records")


def p_1107():
    r = [x for x in rows("infrastructure/utility_site_survey.csv") if x["survey_time_utc"] == "2027-09-29T13:00:00Z" and "O.N. Stevens" in x["asset_name"]]
    cond = bool(r) and r[0]["tiles"] == "2100" and "60 PCT" in r[0]["equipment_observation"] and "40 SQ M" in r[0]["visible_condition"]
    return ok(cond, f"water plant Phase 2 set: {r[0]['tiles'] if r else None} tiles; {r[0]['equipment_observation'] if r else None}; {r[0]['visible_condition'] if r else None}")


# ---------------------------------------------------------------- alerts
def alerts():
    return {r["AlertID"]: r for r in rows("public_health/eas_broadcasts.csv")}


def lag(a):
    return (z(a["ReleasedAt_ES"]) - z(a["ReleasedAt_EN"])) / 60


def canon_alert(aid):
    return {a["id"]: a for a in J("00_scenario/canon_timeline.json")["alerts"]["items"]}[aid]


def p_2101():
    a = alerts().get("IPAWS-TX-2027-0909-001")
    rel = [r for r in rows("broadcast/alert_relay_log.csv") if r["alert_id"] == "IPAWS-TX-2027-0909-001"]
    outlets = [r for r in rel if r["station_id"].startswith("OUT-") and r["result"] == "RECEIVED"]
    wk = [r for r in rel if r["station_id"] == "WKCB-AM"]
    return ok(a and a["IssuedAt_UTC"] == "2027-09-09T14:00:00Z" and len(outlets) == 7 and wk and float(wk[0]["relay_lag_sec"]) == 4.1,
              f"test {a['AlertID'] if a else None} at {a['IssuedAt_UTC'] if a else None}; received by {len(outlets)} market outlets; WKCB-AM relay lag {wk[0]['relay_lag_sec'] if wk else None} s")


def p_1402_eas():
    a = alerts().get("EVI-2027-0912-001")
    return ok(a and a["ReleasedAt_EN"] == "2027-09-12T11:00:00Z" and a["ReleasedAt_ES"] == "2027-09-12T13:47:00Z" and "Zone A" in a["GeographicArea"],
              f"Zone A evacuation order: English {a['ReleasedAt_EN']}, Spanish {a['ReleasedAt_ES']} (lag {lag(a):.0f} min)")


def p_2102_eas():
    a = alerts().get("HUW-2027-0912-001")
    want = canon_alert("hurricane-warning")["release_en"]["utc"].replace("Z", ":00Z")
    cond = a and a["EventCode"] == "HU.W" and a["IssuedAt_UTC"] == want and a["ExpiresAt_UTC"] == "2027-09-14T18:00:00Z" and "TX-355" in a["GeographicArea"] and a["CharCount_EN"] == "312" and a["WEA_Sent"] == "Y"
    return ok(cond, f"HUW-2027-0912-001 code {a['EventCode']} issued {a['IssuedAt_UTC']} (12:00 CDT, the canon alert time), expires {a['ExpiresAt_UTC']}, {a['GeographicArea']}, {a['CharCount_EN']} characters, WEA {a['WEA_Sent']}")


def p_2103_eas():
    a = alerts().get("EVI-2027-0913-001")
    cond = a and a["EventCode"] == "EVI" and a["IssuedAt_UTC"] == "2027-09-13T12:00:00Z" and all(k in a["AreaIDs"] for k in ("AREA-EVAC-A", "AREA-EVAC-B", "AREA-EVAC-C")) and lag(a) <= 30 and a["WEA_Sent_ES"] == a["WEA_Sent_EN"] != ""
    return ok(cond, f"EVI-2027-0913-001 issued {a['IssuedAt_UTC']} for Zones A, B and C; Spanish {lag(a):.0f} min after English; WEA in both languages at {a['WEA_Sent_EN']}")


def p_1403_eas():
    a = alerts().get("SPW-2027-0913-001")
    d = (z(a["WEA_Sent_ES"]) - z(a["WEA_Sent_EN"])) / 60
    return ok(a["WEA_Sent_EN"] == "2027-09-13T18:00:00Z" and a["WEA_Sent_ES"] == "2027-09-14T01:52:00Z" and d == 472,
              f"shelter guidance WEA: English {a['WEA_Sent_EN']} (13:00 CDT), Spanish {a['WEA_Sent_ES']} (20:52 CDT), {int(d // 60)} h {int(d % 60)} min apart")


def p_2104_eas():
    a = alerts().get("SPW-2027-0914-001")
    return ok(a and a["EventCode"] == "SPW" and a["IssuedAt_UTC"] == "2027-09-14T05:45:00Z" and "all zones" in a["GeographicArea"], f"SPW-2027-0914-001 issued {a['IssuedAt_UTC']} for {a['GeographicArea']}")


def p_0310():
    a = alerts().get("BWN-2027-0918-001")
    return ok(a and a["AlertType"] == "BoilWaterNotice" and day(z(a["IssuedAt_UTC"])) == 4 and "all water customers" in a["GeographicArea"], f"citywide boil-water notice issued {a['IssuedAt_UTC']} (D+4)")


def p_1305_eas():
    a = alerts().get("BWW-2027-0926-001")
    return ok(a and a["IssuedAt_UTC"] == "2027-09-26T22:30:00Z" and "Districts 3 and 4" in a["GeographicArea"], f"Districts 3 and 4 notice issued {a['IssuedAt_UTC']} (17:30 local D+12)")


def p_1407_eas():
    a = alerts().get("BWW-2027-0926-001")
    return ok(a["ReleasedAt_EN"] == "2027-09-26T22:30:00Z" and a["ReleasedAt_ES"] == "2027-09-27T11:03:00Z" and lag(a) == 753,
              f"English {a['ReleasedAt_EN']}, Spanish {a['ReleasedAt_ES']}: lag {int(lag(a) // 60)} h {int(lag(a) % 60)} min")


def p_2106_eas():
    a = alerts().get("BWW-2027-0926-001")
    return ok(a["EventCode"] == "BWW" and a["CharCount_EN"] == "287" and a["AreaIDs"] == "AREA-WD-3;AREA-WD-4" and a["WEA_Sent_ES"] == "",
              f"BWW-2027-0926-001 code BWW, {a['CharCount_EN']} characters, areas {a['AreaIDs']}, no Spanish WEA")


def p_1410_eas():
    A = alerts()
    ids = ["BWU-2027-1014-001", "BWA-2027-1023-001", "BWA-2027-1026-001"]
    sim = all(A[i]["ReleasedAt_EN"] == A[i]["ReleasedAt_ES"] != "" for i in ids)
    earlier = [a for a in A.values() if a["EventCode"] not in ("RWT", "RMT") and a["ReleasedAt_ES"] and z(a["IssuedAt_UTC"]) < z("2027-10-14T14:00:00Z") and lag(a) == 0]
    return ok(A[ids[0]]["IssuedAt_UTC"] == "2027-10-14T14:00:00Z" and sim and not earlier,
              f"status update 09:00 CDT D+30 released in both languages at once (first alert with zero gap: {not earlier}); the D+39 and D+42 lift notices also simultaneous: {sim}")


def p_0406():
    a = alerts().get("BWA-2027-1023-001")
    return ok(a and day(z(a["IssuedAt_UTC"])) == 39 and a["AlertType"] == "BoilWaterNoticeLifted", f"citywide notice lifted {a['IssuedAt_UTC']} (D+39)")


def p_gw016_eas():
    a = alerts().get("BWA-2027-1026-001")
    return ok(a and a["IssuedAt_UTC"] == "2027-10-26T16:00:00Z" and a["ReleasedAt_EN"] == a["ReleasedAt_ES"] and "Districts 3 and 4" in a["GeographicArea"],
              f"Districts 3 and 4 notice lifted {a['IssuedAt_UTC']} (11:00 local D+42), English and Spanish together")


def p_2108_eas():
    a = alerts().get("BWA-2027-1026-001")
    return ok(a and a["EventCode"] == "BWA" and a["IssuedAt_UTC"] == "2027-10-26T16:00:00Z" and lag(a) == 0, f"BWA-2027-1026-001 code BWA issued {a['IssuedAt_UTC']}, simultaneous release")


# ---------------------------------------------------------------- broadcast
def prog():
    return rows("broadcast/station_program_log.csv")


def stat():
    return rows("broadcast/station_status_log.csv")


def jobs():
    return {r["job_id"]: r for r in rows("broadcast/translation_jobs.csv")}


def has_prog(station, t, *words, item=None):
    return [r for r in prog() if r["station_id"] == station and r["air_time_utc"] == t and all(w.lower() in (r["description"] + " " + r["item"]).lower() for w in words) and (item is None or r["item"] == item)]


def p_1401():
    p = has_prog("OUT-08", "2027-09-09T14:00:00Z", "coordination call", "Emergency Management")
    j = jobs().get("2027-09-09-STANDBY-001")
    cond = p and j and j["translator"] == "NCLAS" and "24-hour standby" in j["note"] and "two-hour" in j["note"] and "no provision for simultaneous release" in j["note"]
    return ok(cond, f"KNCB 09:00 CDT D-5 coordination call logged: {bool(p)}; NCLAS standby job: {j['note'] if j else None}")


def p_1402_bc():
    ef = [r for r in stat() if r["station_id"] == "OUT-08" and r["air_time_utc"] == "2027-09-11T12:00:00Z" and r["status"] == "EMERGENCY FORMAT"]
    evac_d3 = [r for r in prog() if r["station_id"] == "OUT-08" and "2027-09-11T05:00:00Z" <= r["air_time_utc"] < "2027-09-12T05:00:00Z" and (r["alert_id"].startswith("EVI") or "evacuation order" in r["description"].lower())]
    j = jobs().get("2027-09-12-EVAC-001")
    cond = ef and not evac_d3 and j and j["source_received_utc"] == "2027-09-12T11:00:00Z" and j["translation_delivered_utc"] == "2027-09-12T13:25:00Z" and j["first_aired_utc"] == "2027-09-12T13:47:00Z"
    read = [r for r in prog() if r["station_id"] == "OUT-08" and r["air_time_utc"] == "2027-09-12T13:47:00Z" and r["alert_id"] == "EVI-2027-0912-001"]
    return ok(cond and read, f"emergency format from 07:00 CDT D-3: {bool(ef)}; evacuation orders read on D-3: {len(evac_d3)}; translation job received {j['source_received_utc']}, delivered {j['translation_delivered_utc']}, aired {j['first_aired_utc']}")


def p_2102_bc():
    w = {"OUT-02": "2027-09-12T17:06:00Z", "OUT-03": "2027-09-12T17:03:00Z", "OUT-08": "2027-09-12T17:08:00Z"}
    got = {s: [r["item"] for r in prog() if r["station_id"] == s and r["air_time_utc"] == t and r["alert_id"] == "HUW-2027-0912-001"] for s, t in w.items()}
    return ok(all(got.values()), f"after the 17:00Z hurricane warning (12:00 CDT, canon alert time): Harborline 6 emergency format 17:06Z, Coastline interrupts 17:03Z, KNCB bilingual 17:08Z: {got}")


def p_2103_bc():
    start = has_prog("OUT-08", "2027-09-13T12:15:00Z", "evacuation loop")
    plays = [r for r in prog() if r["station_id"] == "OUT-08" and r["item"] == "EVACUATION LOOP" and r["air_time_utc"] < "2027-09-14T06:00:00Z"]
    return ok(start and len(plays) == 24, f"bilingual evacuation loop starts 12:15Z D-1; {len(plays)} plays before landfall")


def p_1403_bc():
    p = has_prog("OUT-08", "2027-09-13T18:45:00Z", "Zona D", "Collier")
    return ok(bool(p), f"KNCB 13:45 CDT D-1 shelter reading: {p[0]['description'] if p else None}")


def p_2104_bc():
    gen = [r for r in stat() if r["station_id"] == "OUT-03" and r["air_time_utc"] == "2027-09-14T05:00:00Z" and "GENERATOR" in r["status"] and "2.2 kW" in r["note"]]
    end = [r for r in stat() if r["station_id"] == "OUT-03" and r["air_time_utc"] == "2027-09-14T14:00:00Z"]
    only = [r for r in stat() if r["station_id"] == "OUT-03" and r["air_time_utc"] in ("2027-09-14T06:30:00Z", "2027-09-14T09:00:00Z")]
    koff = [r for r in stat() if r["station_id"] == "OUT-08" and r["air_time_utc"] == "2027-09-14T08:31:00Z" and r["status"] == "OFF AIR"]
    kon = [r for r in stat() if r["station_id"] == "OUT-08" and r["air_time_utc"] == "2027-09-15T07:00:00Z" and r["status"] == "ON AIR"]
    last = has_prog("OUT-08", "2027-09-14T08:30:00Z")
    return ok(gen and end and len(only) == 2 and koff and kon and last,
              f"Coastline on generator 05:00Z-14:00Z: {bool(gen and end)}; only signal monitored 06:30Z-09:00Z: {len(only) == 2}; KNCB last item 08:30Z, off air 08:31Z, back 2027-09-15T07:00Z: {bool(koff and kon and last)}")


def p_1404_bc():
    p = has_prog("OUT-08", "2027-09-14T15:00:00Z", "FEMA", "ingles")
    return ok(bool(p), f"KNCB 10:00 CDT D0 advisory ({p[0]['platform'] if p else None}): {p[0]['description'] if p else None}")


def p_2105():
    p = has_prog("OUT-02", "2027-09-15T14:00:00Z", "First post-landfall", "damage", "casualties", "shelters", "curfew", "158")
    dur = p and p[0]["duration_sec"] == str(47 * 60)
    S = {(r["station_id"], r["air_time_utc"]) for r in stat() if r["status"] in ("ON AIR", "ONLINE")}
    rest = all(k in S for k in (("OUT-02", "2027-09-15T13:52:00Z"), ("OUT-04", "2027-09-15T16:30:00Z"), ("OUT-05", "2027-09-16T04:10:00Z"), ("OUT-07", "2027-09-16T06:00:00Z")))
    return ok(p and dur and rest, f"Harborline 6 first post-landfall broadcast 14:00Z D+1, 47 min: {bool(p and dur)}; restoration times OUT-02 13:52Z, OUT-04 16:30Z, OUT-05 04:10Z, OUT-07 06:00Z: {rest}")


def p_1405():
    c = [r for r in rows("broadcast/call_in_log.csv") if "2027-09-16T16:00:00Z" <= r["air_time_utc"] <= "2027-09-16T18:00:00Z"]
    avg = sum(int(r["duration_sec"]) for r in c) / 60 / max(1, len(c))
    cs = sum(1 for r in c if r["code_switching"] == "Y")
    return ok(len(c) == 47 and abs(avg - 2.3) <= 0.05 and cs == 31, f"{len(c)} KNCB call-ins on D+2, mean {avg:.1f} min, code-switching in {cs}")


def p_1406():
    p = has_prog("OUT-08", "2027-09-22T15:00:00Z", "FEMA", "Spanish", item="LIVE ANNOUNCEMENT")
    return ok(bool(p), f"KNCB 10:00 CDT D+8: {p[0]['description'] if p else None}")


def p_1407_bc():
    j = jobs().get("2027-09-26-BWN-001")
    late = j and (z(j["translation_delivered_utc"]) - z(j["source_received_utc"])) / 3600 > float(j["service_level_hours"])
    cond = j and j["source_received_utc"] == "2027-09-26T22:35:00Z" and j["translation_delivered_utc"] == "2027-09-27T04:45:00Z" and j["first_aired_utc"] == "2027-09-27T11:03:00Z" and late
    return ok(cond, f"job 2027-09-26-BWN-001: received {j['source_received_utc']}, delivered {j['translation_delivered_utc']} (service level {j['service_level_hours']} h), first aired {j['first_aired_utc']}")


def p_2106_bc():
    p = [r for r in prog() if r["station_id"] == "OUT-08" and r["alert_id"] == "BWW-2027-0926-001" and r["item"] == "ALERT READ"]
    first = min(r["air_time_utc"] for r in p) if p else None
    note = any("05:58" in r["description"] for r in p)
    return ok(first == "2027-09-27T11:03:00Z" and note, f"KNCB first airs the Spanish notice {first} (06:03 local), 12 h 33 min after the English alert; translation received 05:58 local: {note}")


def p_1408():
    p = has_prog("OUT-08", "2027-09-27T12:15:00Z", "Recibimos el aviso oficial", "por que no lo supimos antes")
    h = [r for r in prog() if r["station_id"] == "OUT-02" and r["item"] == "FIELD INTERVIEWS" and "7 of 9" in r["description"]]
    return ok(p and h, f"KNCB 07:15 CDT D+13 host remarks logged: {bool(p)}; Harborline 6 field interviews (7 of 9): {bool(h)}")


def p_1409_bc():
    p = [r for r in prog() if r["station_id"] == "OUT-08" and "2027-10-05T19:00:00Z" <= r["air_time_utc"] <= "2027-10-05T21:00:00Z" and "LULAC" in r["description"] and "in full" in r["description"]]
    return ok(bool(p), f"KNCB {p[0]['air_time_utc'] if p else None}: {p[0]['description'] if p else None}")


def p_2107_bc():
    p = has_prog("OUT-02", "2027-10-05T19:00:00Z", "deliberate interference with utility systems", item="LIVE PRESS CONFERENCE")
    return ok(p and p[0]["duration_sec"] == str(47 * 60), f"Harborline 6 live press conference 19:00Z-19:47Z D+21 with the anchor intro: {bool(p)}")


def p_1410_bc():
    s = [r for r in stat() if r["station_id"] == "OUT-08" and r["status"] == "EMERGENCY FORMAT 18 HOURS" and day(z(r["air_time_utc"])) == 30]
    night = [r for r in prog() if r["station_id"] == "OUT-08" and r["item"] == "EMERGENCY UPDATE" and day(z(r["air_time_utc"])) == 31 and int(r["air_time_utc"][11:13]) in (6, 7, 8, 9, 10)]
    return ok(s and not night, f"KNCB emergency format cut to 18 hours from D+30: {bool(s)}; overnight emergency blocks on D+31: {len(night)}")


def p_2108_bc():
    p = has_prog("OUT-08", "2027-10-26T16:00:00Z", "all-clear", "simultaneous")
    pk = [r for r in prog() if r["station_id"] == "OUT-02" and "Boil water ban ends - 30 days later" in r["description"] and r["duration_sec"] == "222"]
    return ok(p and pk, f"KNCB Spanish all-clear at 16:00Z D+42 with the English alert: {bool(p)}; Harborline 6 package of 3 min 42 s: {bool(pk)}")


def p_1411():
    s = [r for r in stat() if r["station_id"] == "OUT-08" and r["air_time_utc"] == "2027-10-29T11:00:00Z" and r["status"] == "NORMAL FORMAT" and "48 days" in r["note"]]
    start = [r for r in stat() if r["station_id"] == "OUT-08" and r["status"] == "EMERGENCY FORMAT"]
    days = (z("2027-10-29T11:00:00Z") - z(start[0]["air_time_utc"])) / 86400 if start else 0
    return ok(s and round(days) == 48, f"KNCB returns to normal format 06:00 CDT D+45 after {days:.0f} days of emergency format")


def p_2207():
    live = {r["station_id"] for r in prog() if r["air_time_utc"] == "2027-12-13T19:00:00Z" and r["item"] == "LIVE PRESS CONFERENCE"}
    wire = [r for r in prog() if r["station_id"] == "OUT-06" and r["air_time_utc"].startswith("2027-12-13") and "nationally" in r["description"]]
    return ok(live == {"OUT-02", "OUT-03"} and wire, f"press conference carried live by {sorted(live)}; Continental Wire distribution: {bool(wire)}")


# ---------------------------------------------------------------- public record
def statements():
    if "stm" not in _c:
        out = {}
        for fp in sorted(glob.glob(os.path.join(SRC, "press_releases", "*.jsonl"))):
            for line in open(fp, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    out[r["id"]] = r
        _c["stm"] = out
    return _c["stm"]


MANUAL = {"EVT-1503": ["NOTICE-NCOEM-2027-0912-01"], "GW-EVT-008": ["GW-PUB-001", "PUB-143"], "GW-EVT-012": ["GW-PUB-003", "PUB-150"],
          "EVT-1409": ["NOTICE-TDEM-2027-1005-01", "NOTICE-LULAC-2027-1005-01"], "GW-EVT-014": ["GW-PUB-102"], "GW-EVT-015": ["GW-PUB-006"],
          "GW-EVT-016": ["GW-PUB-007"], "EVT-2205": ["PUB-105"]}


def pub_probe(event_id):
    def f():
        facts = {x["id"]: x for x in J("02_public_record/public_record.json")["facts"]}
        ids = MANUAL.get(event_id) or [x["id"] for x in facts.values() if event_id in x.get("events", [])]
        S = statements()
        missing = [i for i in ids if i not in S]
        wrong = [i for i in ids if i in S and i in facts and (S[i]["text"] != facts[i]["statement"] or S[i]["date_local"] != (dt.date(2027, 9, 14) + dt.timedelta(days=facts[i]["day"])).isoformat())]
        leak = [i for i in ids if i in S and any(k in S[i] for k in ("events", "threads", "arcs", "sources"))]
        return ok(ids and not missing and not wrong and not leak, "statements " + ", ".join(f"{i} ({S[i]['date_local']} {S[i]['time_local']}, {S[i]['issuer']})" for i in ids if i in S)
                  + (f"; missing {missing}" if missing else "") + (f"; text or date differs {wrong}" if wrong else ""))
    return f


# ---------------------------------------------------------------- stream descriptions
def _span(vals):
    v = [x for x in vals if x]
    return (min(v), max(v))


def _cad_units_used():
    out = set()
    for r in cad():
        if r["unit_id"]:
            out.add(r["unit_id"])
        out.update(x for x in r["additional_units"].split(";") if x)
    return out


def _aircraft_regs():
    return {a["registration"] for a in J("06_data_streams/aircraft_registry.json")["aircraft"]}


def _area_ids():
    return {a["area_id"] for a in J("06_data_streams/areas.json")["areas"]}


def _fact_ids():
    return {f["id"] for f in J("02_public_record/public_record.json")["facts"]} | {i for v in MANUAL.values() for i in v if i.startswith("NOTICE-")}


STREAMS = {
    "cad_911": {
        "time_range": lambda: _span(r["t"] for r in cad()),
        "ids": _cad_units_used, "registry_ids": unit_ids, "public_voice": True,
        "text": lambda: (r["narrative"] + " " + r["address"] + " " + r["ali_carrier"] for r in cad()),
        "columns": lambda: header("911/cad_incidents_*.csv"),
    },
    "avl": {
        "time_range": lambda: (z(min(r[0] for r in avl_rows())), z(max(r[0] for r in avl_rows()))),
        "ids": lambda: {r[1] for r in avl_rows()}, "registry_ids": unit_ids, "public_voice": False,
        "columns": lambda: header("avl/*.csv"),
    },
    "sar_missions": {
        "time_range": lambda: _span([z(r["launch_utc"]) for r in sar()] + [z(r["time_utc"]) for r in alog()]),
        "ids": lambda: {r["asset_id"] for r in sar()}, "registry_ids": lambda: unit_ids() | _aircraft_regs(), "public_voice": True,
        "text": lambda: [r["note"] for r in alog()] + [r["address"] for r in sar()],
        "columns": lambda: header("sar/*.csv"),
    },
    "shelters": {
        "time_range": lambda: _span([loc(r["date_local"]) for r in rows("shelters/shelter_daily_census.csv")] + [loc(r["call_time_local"]) for r in rows("shelters/shelter_211_calls.csv")]),
        "ids": lambda: {r["facility_id"] for r in rows("shelters/shelter_daily_census.csv")} | {r["facility_id"] for r in rows("shelters/shelter_registry.csv")}
                       | {r["referred_facility_id"] for r in rows("shelters/shelter_211_calls.csv") if r["referred_facility_id"]} | {r["facility_id"] for r in rows("shelters/evacuation_bus_trips.csv")},
        "registry_ids": lambda: {f["facility_id"] for f in J("06_data_streams/facility_registry.json")["facilities"]}, "public_voice": True,
        "text": lambda: [r["note"] for r in rows("shelters/shelter_211_calls.csv")],
        "columns": lambda: header("shelters/*.csv"),
    },
    "damage_assessment": {
        "time_range": lambda: _span(loc(r["ASMT_DATE"]) for r in rows("infrastructure/damage_assessment.csv")),
        "ids": lambda: {r["census_tract"] for r in rows("infrastructure/damage_assessment.csv")}, "registry_ids": lambda: set(tracts()), "public_voice": True,
        "text": lambda: [r["ACCESS_NOTE"] + " " + r["ASSESSOR"] + " " + r["address"] for r in rows("infrastructure/damage_assessment.csv")]
                        + [" ".join(r[k] for k in ("asset_name", "phase", "yard_flood_status", "visible_condition", "equipment_observation")) for r in rows("infrastructure/utility_site_survey.csv")],
        "columns": lambda: header("infrastructure/*.csv"),
    },
    "eas_alerts": {
        "time_range": lambda: _span(z(r["IssuedAt_UTC"]) for r in rows("public_health/eas_broadcasts.csv")),
        "ids": lambda: {x for r in rows("public_health/eas_broadcasts.csv") for x in r["AreaIDs"].split(";") if x}, "registry_ids": _area_ids, "public_voice": True,
        "text": lambda: [r["Headline_EN"] + " " + r["Headline_ES"] + " " + r["AlertSource"] for r in rows("public_health/eas_broadcasts.csv")],
        "columns": lambda: header("public_health/eas_broadcasts.csv"),
    },
    "broadcast_logs": {
        "time_range": lambda: _span(z(r["air_time_utc"]) for r in prog()),
        "ids": lambda: {r["station_id"] for r in prog()} | {r["station_id"] for r in stat()} | {r["station_id"] for r in rows("broadcast/alert_relay_log.csv")},
        "registry_ids": lambda: {o["outlet_id"] for o in J("01_characters/outlets.json")["outlets"]} | {"WKCB-AM"}, "public_voice": True,
        "text": lambda: [r["description"] for r in prog()] + [r["note"] for r in stat()] + [r["note"] for r in rows("broadcast/translation_jobs.csv")],
        "columns": lambda: header("broadcast/*.csv"),
    },
    "public_record": {
        "time_range": lambda: _span(dt.datetime.fromisoformat(r["issued_local"]).timestamp() for r in statements().values()),
        "ids": lambda: set(statements()), "registry_ids": _fact_ids, "public_voice": True,
        "text": lambda: [r["text"] + " " + r["issuer"] for r in statements().values()],
        "columns": lambda: sorted({k for r in statements().values() for k in r}),
    },
}

PROBES = {
    ("EVT-0101", "cad_911"): p_0101, ("EVT-0303", "cad_911"): p_0303, ("EVT-0601", "cad_911"): p_0601, ("EVT-1301", "cad_911"): p_1301,
    ("EVT-1702", "cad_911"): p_1702_cad, ("EVT-0304", "cad_911"): p_0304_cad, ("EVT-0318", "cad_911"): p_0318, ("EVT-1302", "cad_911"): p_1302_cad,
    ("EVT-1707", "cad_911"): p_1707_cad, ("EVT-1303", "cad_911"): p_1303_cad, ("EVT-1304", "cad_911"): p_1304_cad, ("EVT-1305", "cad_911"): p_1305_cad,
    ("EVT-1307", "cad_911"): p_1307, ("EVT-0413", "cad_911"): p_0413, ("EVT-1308", "cad_911"): p_1308,
    ("EVT-0304", "avl"): p_0304_avl, ("EVT-1707", "avl"): p_1707_avl,
    ("EVT-1701", "sar_missions"): p_1701, ("EVT-1708", "sar_missions"): p_1708, ("EVT-1702", "sar_missions"): p_1702_sar, ("EVT-1302", "sar_missions"): p_1302_sar,
    ("EVT-1703", "sar_missions"): p_1703, ("EVT-1704", "sar_missions"): p_1704, ("EVT-1705", "sar_missions"): p_1705, ("EVT-1706", "sar_missions"): p_1706,
    ("EVT-1707", "sar_missions"): p_1707_sar, ("EVT-1303", "sar_missions"): p_1303_sar, ("EVT-1304", "sar_missions"): p_1304_sar,
    ("EVT-1502", "shelters"): p_1502, ("EVT-1403", "shelters"): p_1403_shel,
    ("EVT-1101", "damage_assessment"): p_1101, ("EVT-1104", "damage_assessment"): p_1104, ("EVT-1105", "damage_assessment"): p_1105,
    ("EVT-1106", "damage_assessment"): p_1106, ("EVT-1107", "damage_assessment"): p_1107,
    ("EVT-2101", "eas_alerts"): p_2101, ("EVT-1402", "eas_alerts"): p_1402_eas, ("EVT-2102", "eas_alerts"): p_2102_eas, ("EVT-2103", "eas_alerts"): p_2103_eas,
    ("EVT-1403", "eas_alerts"): p_1403_eas, ("EVT-2104", "eas_alerts"): p_2104_eas, ("EVT-0310", "eas_alerts"): p_0310, ("EVT-1305", "eas_alerts"): p_1305_eas,
    ("EVT-1407", "eas_alerts"): p_1407_eas, ("EVT-2106", "eas_alerts"): p_2106_eas, ("EVT-1410", "eas_alerts"): p_1410_eas, ("EVT-0406", "eas_alerts"): p_0406,
    ("GW-EVT-016", "eas_alerts"): p_gw016_eas, ("EVT-2108", "eas_alerts"): p_2108_eas,
    ("EVT-1401", "broadcast_logs"): p_1401, ("EVT-1402", "broadcast_logs"): p_1402_bc, ("EVT-2102", "broadcast_logs"): p_2102_bc, ("EVT-2103", "broadcast_logs"): p_2103_bc,
    ("EVT-1403", "broadcast_logs"): p_1403_bc, ("EVT-2104", "broadcast_logs"): p_2104_bc, ("EVT-1404", "broadcast_logs"): p_1404_bc, ("EVT-2105", "broadcast_logs"): p_2105,
    ("EVT-1405", "broadcast_logs"): p_1405, ("EVT-1406", "broadcast_logs"): p_1406, ("EVT-1407", "broadcast_logs"): p_1407_bc, ("EVT-2106", "broadcast_logs"): p_2106_bc,
    ("EVT-1408", "broadcast_logs"): p_1408, ("EVT-1409", "broadcast_logs"): p_1409_bc, ("EVT-2107", "broadcast_logs"): p_2107_bc, ("EVT-1410", "broadcast_logs"): p_1410_bc,
    ("EVT-2108", "broadcast_logs"): p_2108_bc, ("EVT-1411", "broadcast_logs"): p_1411, ("EVT-2207", "broadcast_logs"): p_2207,
}
for _e in J("00_scenario/canon_timeline.json")["expected_observations"]["items"]:
    if _e["stream"] == "public_record":
        PROBES[(_e["event_id"], "public_record")] = pub_probe(_e["event_id"])
