"""Read-only audit: cross-reference every entity across scenario files, registries, data streams,
news and the knowledge graph.  Changes nothing except the two report files.

Writes 07_validation/reports/entity_graph_audit.md and entity_graph_audit.json.
Usage: python scripts/audit_entities.py
"""
import collections
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, context, load, load_all_stories, path  # noqa: E402

S = "05_other_sources"
REG = "06_data_streams"
csv.field_size_limit(10 ** 9)


def P(*p):
    return path(*p)


def J(rel):
    with open(P(rel), encoding="utf-8") as fh:
        return json.load(fh)


def col(rel, *cols):
    """Counter of values (or tuples of values) in a CSV column."""
    out = collections.Counter()
    fp = P(rel)
    if not os.path.exists(fp):
        return out
    with open(fp, encoding="utf-8", errors="replace", newline="") as fh:
        for r in csv.DictReader(fh):
            v = tuple((r.get(c) or "").strip() for c in cols)
            out[v[0] if len(cols) == 1 else v] += 1
    return out


def norm(s):
    s = re.sub(r"^(MT|MV|FV|M/V|M/T|USCGC|Tug|the)\s+", "", s.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def short(xs, n=40):
    xs = list(xs)
    return xs[:n] + ([f"... +{len(xs) - n} more"] if len(xs) > n else [])


RECOMMENDED_SCHEMA = {
    "principle": "One canonical id per real-world thing in a single master registry; every stream, scenario file, map layer and graph node refers to it. "
                 "Placeholder keys (MMSI-SYN-*, ICAO-SYN-*, id ranges such as 'EQP-1101 to 1104') are replaced by the real keys used in the data, one record each.",
    "node_types": {
        "Organization": "agencies, companies, utilities, insurers, contractors, ship agents, outlets (key: ORG-*; aliases list; real_or_fictional flag)",
        "Vessel": "key MMSI; props IMO, name, type, flag, operator -> Organization",
        "Aircraft": "key icao24; props callsign, type, operator; includes drones with a remote id",
        "Facility": "hospitals, shelters, terminals/berths, substations, plants, bases, PSAP (key FAC-*; lat/lon; operator)",
        "Equipment": "pumps, generators, RTUs, breakers (key = asset number used in work orders and SCADA asset id)",
        "Host": "IT/OT hosts (key hostname; ip; subnet) and domains",
        "ScadaTag": "tag name -> Equipment/Facility",
        "Sensor": "AQS, sondes, gauges, ASOS, buoys (key sensor id; lat/lon)",
        "SocialAccount": "handle; account_type; operated_by -> Character/Organization; coordinated_network flag (internal)",
        "ResponseUnit": "CAD unit ids -> agency Organization, station Facility",
        "Area": "census tract, ZIP, CAD beat, water district, evacuation zone, neighbourhood (hierarchy WITHIN)",
        "DataStream": "one node per delivered file family with time coverage, schema, key columns",
        "Observation": "optional: the specific rows/time windows that evidence an Event (stream, key value, start, end)",
        "AnswerKeyPath": "ordered steps per Thread, each step -> DataStream/Observation/entity",
        "Alert": "EAS/WEA/boil-water notices with EN and ES release times",
        "Contract": "awards and claims that stories and payments both reference",
    },
    "edge_types": {
        "INVOLVES": "Event -> Vessel|Aircraft|Facility|Equipment|Host|Organization|SocialAccount (internal)",
        "MENTIONS_ENTITY": "Story|PublicFact -> Organization|Vessel|Facility|... (public)",
        "OPERATED_BY / OWNED_BY / PART_OF": "Vessel|Aircraft|Facility|Equipment|Host -> Organization|Facility",
        "LOCATED_AT / WITHIN": "Facility|Sensor|Equipment -> Place|Area",
        "EMPLOYED_BY": "Character -> Organization (replaces text-only affiliation)",
        "OBSERVED_IN": "Event -> DataStream (replaces 317 free-text observed_in labels with a controlled list)",
        "EVIDENCED_BY": "Event|AnswerKeyStep -> Observation",
        "RECORDS": "DataStream -> entity type it is keyed on (e.g. AIS -> Vessel by MMSI)",
        "HAS_STEP / NEXT_STEP / SOLVES": "AnswerKeyPath -> steps -> Thread",
        "SAME_AS": "temporary alias edge while old ids are being retired",
        "CALLED_AT": "Vessel -> Facility (terminal/berth) with ATA/ATD",
        "PAID": "Organization -> Organization|Character with amount/date (from payments)",
        "POSTED_BY / AMPLIFIES": "SocialAccount relations for the coordinated network",
    },
}


# ======================================================================================
def main():
    ctx = context()
    stories = load_all_stories()
    facts = list(ctx["facts"].values())
    msel = list(ctx["msel"].values())
    threads = J("00_scenario/threads.json")
    R = {"inventory": {}, "missing_registry_entries": [], "unused_registry_entries": [], "id_conflicts": [],
         "unregistered_named_entities": [], "graph_gaps": {}, "thread_completeness": [], "notes": []}
    inv = R["inventory"]

    def miss(cls, where, ids, note=""):
        ids = sorted(set(map(str, ids)))
        if ids:
            R["missing_registry_entries"].append({"class": cls, "used_in": where, "count": len(ids), "ids": ids, "note": note})

    def unused(cls, registry, ids, note=""):
        ids = sorted(set(map(str, ids)))
        if ids:
            R["unused_registry_entries"].append({"class": cls, "registry": registry, "count": len(ids), "ids": ids, "note": note})

    def conflict(cls, what, detail, severity="medium"):
        R["id_conflicts"].append({"class": cls, "severity": severity, "issue": what, "detail": detail})

    map_html = ""
    mp = P("09_shared_state_timeline/viewer/map_view.html")
    if os.path.exists(mp):
        map_html = open(mp, encoding="utf-8").read()

    def map_var(name):
        m = re.search(r"var %s=(\{.*?\});" % name, map_html, re.S)
        try:
            return json.loads(m.group(1)) if m else {}
        except Exception:
            return {}

    ent = ctx["entities"]

    # ------------------------------------------------------------------ vessels
    ves = J(f"{REG}/vessels.json")["vessels"]
    reg_m = {v["mmsi"]: v["vessel_name"] for v in ves}
    ais = {}
    for (m, n), c in col(f"{S}/ais/ais_positions.csv", "MMSI", "VesselName").items():
        ais.setdefault(m, n)
    arr = {m: n for (n, m) in col(f"{S}/supply/vessel_arrivals.csv", "vessel_name", "mmsi")}
    manifest = set(col(f"{S}/supply/cargo_manifest.csv", "vessel_name"))
    vmeta = {k: v.get("name") for k, v in map_var("VMETA").items()}
    ent_v = {k: v for k, v in ent.items() if k.startswith(("VSL-", "BRG-"))}
    inv["vessel"] = {"vessels.json": len(reg_m), "AIS positions (MMSI)": len(ais), "supply/vessel_arrivals (MMSI)": len(arr),
                     "supply/cargo_manifest (names)": len(manifest), "map VMETA": len(vmeta), "entities.json VSL-/BRG-": len(ent_v)}
    miss("vessel", "ais/ais_positions.csv", [f"{m} {ais[m]}" for m in ais if m not in reg_m], "AIS MMSI absent from vessels.json")
    miss("vessel", "supply/vessel_arrivals.csv", [f"{m} {arr[m]}" for m in arr if m not in reg_m], "port-call vessel absent from vessels.json")
    miss("vessel", "map_view.html VMETA", [f"{m} {vmeta[m]}" for m in vmeta if m not in reg_m])
    unused("vessel", "vessels.json", [f"{m} {n}" for m, n in reg_m.items() if m not in ais], "registered vessel has no AIS track")
    unused("vessel", "vessels.json", [f"{m} {n}" for m, n in reg_m.items() if m not in ais and m not in arr],
           "registered vessel appears in neither AIS nor port calls")
    allnames = collections.defaultdict(dict)
    for src, d in (("vessels.json", reg_m), ("AIS", ais), ("vessel_arrivals", arr), ("map VMETA", vmeta)):
        for m, n in d.items():
            allnames[m][src] = n
    for m, d in sorted(allnames.items()):
        if len({norm(x) for x in d.values()}) > 1 or (len(set(d.values())) > 1):
            conflict("vessel", f"MMSI {m} carries different names", d, "high" if len({norm(x) for x in d.values()}) > 1 else "low")
    byname = collections.defaultdict(set)
    for src, d in (("vessels.json", reg_m), ("AIS", ais), ("vessel_arrivals", arr), ("map VMETA", vmeta)):
        for m, n in d.items():
            byname[norm(n)].add(m)
    for n, ms in sorted(byname.items()):
        if len(ms) > 1:
            conflict("vessel", f"vessel name '{n}' appears under {len(ms)} MMSIs", sorted(ms), "high")
    ais_arr_overlap = set(ais) & set(arr)
    R["notes"].append(f"Vessel overlap: AIS∩registry={len(set(ais) & set(reg_m))}, AIS∩port calls={len(ais_arr_overlap)}, "
                      f"registry∩port calls={len(set(reg_m) & set(arr))}, AIS∩map={len(set(ais) & set(vmeta))}.")
    for k, e in ent_v.items():
        hit = [m for m, n in {**arr, **ais, **reg_m}.items() if norm(n) == norm(e["name"])]
        conflict("vessel", f"scenario entity {k} '{e['name']}' keyed by placeholder {e['type_and_keys']}",
                 {"real_mmsi_in_data": hit or "no MMSI anywhere", "vessel_id_in_vessels_json":
                  [v["vessel_id"] for v in ves if norm(v["vessel_name"]) == norm(e["name"])] or None},
                 "high" if not hit else "medium")
    vid = {v["vessel_id"] for v in ves}
    if vid and ent_v:
        conflict("vessel", "two id schemes for vessels", {"vessels.json": sorted(vid)[:4] + ["..."], "entities.json": sorted(ent_v)}, "medium")

    # ------------------------------------------------------------------ aircraft
    ac = J(f"{REG}/aircraft_registry.json")["aircraft"]
    reg_a = {a["icao24"].lower(): a for a in ac}
    adsb = {}
    for f in sorted(glob.glob(P(S, "adsb", "*.csv"))):
        with open(f, encoding="utf-8") as fh:
            r = next(csv.DictReader(fh), None)
            if r:
                adsb[r["icao24"].lower()] = r["callsign"].strip()
    ameta = {k.lower(): v.get("name") for k, v in map_var("AMETA").items()}
    ent_a = {k: v for k, v in ent.items() if k.startswith("ACF-")}
    inv["aircraft"] = {"aircraft_registry.json": len(reg_a), "ADS-B files (icao24)": len(adsb), "map AMETA": len(ameta), "entities.json ACF-": len(ent_a)}
    miss("aircraft", "adsb/*.csv", [f"{i} {c}" for i, c in adsb.items() if i not in reg_a], "ADS-B aircraft absent from aircraft_registry.json")
    unused("aircraft", "aircraft_registry.json", [f"{i} {a['callsign']} ({a['aircraft_id']})" for i, a in reg_a.items() if i not in adsb],
           "registered aircraft has no ADS-B track")
    for i, c in adsb.items():
        if i in reg_a and reg_a[i]["callsign"] != c:
            conflict("aircraft", f"icao24 {i} callsign differs", {"registry": reg_a[i]["callsign"], "adsb": c}, "high")
    for i, n in ameta.items():
        if i in reg_a:
            a = reg_a[i]
            conflict("aircraft", f"icao24 {i} described differently", {"registry": f"{a['callsign']} {a['aircraft_type']} / {a['operator']}", "map": n,
                                                                      "adsb_callsign": adsb.get(i)}, "low")

    # ------------------------------------------------------------------ facilities / hospitals
    fac = J(f"{REG}/facility_registry.json")["facilities"]
    reg_f = {f["facility_id"]: f["facility_name"] for f in fac}
    ed = col(f"{S}/public_health/_consolidated/ed_visits.csv", "C_Facility_ID")
    cap = col(f"{S}/public_health/hospital_capacity.csv", "C_Facility_ID")
    syn = col(f"{S}/public_health/syndrome_summary.csv", "C_Facility_ID")
    place_fac = {k: v["name"] for k, v in ctx["places"].items() if k.startswith(("FAC-", "PSAP", "WW-", "TANK", "TERM"))}
    inv["facility"] = {"facility_registry.json": len(reg_f), "ed_visits facility ids": len(ed), "hospital_capacity ids": len(cap),
                       "syndrome_summary ids": len(syn), "places.json facility-type ids": len(place_fac)}
    miss("facility", "public_health/ed_visits*.csv", [i for i in ed if i not in reg_f], "hospital ids in ED data absent from facility_registry.json")
    miss("facility", "public_health/hospital_capacity.csv", [i for i in cap if i not in reg_f])
    unused("facility", "facility_registry.json", [f"{i} {n}" for i, n in reg_f.items() if i not in ed and i not in cap], "facility id never used by any stream")
    conflict("facility", "hospital id schemes do not overlap at all",
             {"facility_registry.json": [f"{i} {n}" for i, n in reg_f.items() if "Medical" in n or "Urgent" in n],
              "ed_visits/hospital_capacity": sorted(ed), "places.json": "FAC-HOS-xx (placeholder)",
              "news": "Shoreline Regional Medical Center, Bay City Medical Center"}, "high")

    # ------------------------------------------------------------------ hosts / OT assets
    hosts = J(f"{REG}/gw_host_registry.json")["hosts"]
    reg_h = {h["host_id"]: h for h in hosts}
    reg_ip = {h["ip"] for h in hosts if h.get("ip")}
    siem_h = col(f"{S}/network_logs/siem_alerts.csv", "HostName")
    siem_ip = col(f"{S}/network_logs/siem_alerts.csv", "SourceIP") + col(f"{S}/network_logs/siem_alerts.csv", "DestIP")
    zeek_ip = collections.Counter()
    for name in ("conn.log", "notice.log"):
        fp = P(S, "network_logs", "_consolidated", name)
        if os.path.exists(fp):
            fields = None
            with open(fp, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("#fields"):
                        fields = line.rstrip("\n").split("\t")[1:]
                    elif not line.startswith("#") and fields:
                        parts = line.rstrip("\n").split("\t")
                        for k in ("id.orig_h", "id.resp_h", "src", "dst"):
                            if k in fields and fields.index(k) < len(parts):
                                zeek_ip[parts[fields.index(k)]] += 1
    gw = J("scenarios/gridwater/00_scenario/assets.json")
    gw_fac = {x["id"]: x.get("name") for x in gw.get("facilities", [])}
    gw_sys = {x["id"]: x.get("name") for x in gw.get("systems", [])}
    gw_ent = {x["id"]: x.get("name") for x in gw.get("entities", [])}
    tags = J(f"{REG}/scada_tags.json")["tags"]
    tag_names = {t["tagname"] for t in tags}
    tag_assets = {t.get("asset_id") for t in tags}
    hist_tags = col(f"{S}/telemetry/_consolidated/historian_data.csv", "Tagname")
    hist_assets = col(f"{S}/telemetry/_consolidated/historian_data.csv", "AssetID")
    wo_assets = col(f"{S}/maintenance/work_orders.csv", "ASSETNUM")
    wo_loc = col(f"{S}/maintenance/work_orders.csv", "LOCATION")
    ent_host = {k: v["name"] for k, v in ent.items() if k.startswith("HOST-")}
    inv["host"] = {"gw_host_registry.json": len(reg_h), "siem_alerts HostName": len(siem_h), "siem_alerts IPs": len(siem_ip),
                   "zeek conn/notice IPs": len(zeek_ip), "gridwater assets systems": len(gw_sys), "entities.json HOST-": len(ent_host)}
    inv["ot_asset"] = {"gridwater assets facilities": len(gw_fac), "scada_tags asset ids": len(tag_assets), "historian AssetID": len(hist_assets),
                       "work_orders ASSETNUM": len(wo_assets), "work_orders LOCATION": len(wo_loc)}
    inv["scada_tag"] = {"scada_tags.json": len(tag_names), "historian Tagname": len(hist_tags)}
    miss("host", "network_logs/siem_alerts.csv HostName", [h for h in siem_h if h not in reg_h], "SIEM host names absent from gw_host_registry.json")
    unused("host", "gw_host_registry.json", [h for h in reg_h if h not in siem_h], "registered host never appears in SIEM alerts")
    internal = lambda ip: ip.startswith("10.") and "/" not in ip
    miss("host", "siem_alerts IPs", [i for i in siem_ip if internal(i) and i not in reg_ip], "internal IP with no host record")
    miss("host", "zeek logs IPs", [i for i in zeek_ip if internal(i) and i not in reg_ip], "internal IP with no host record")
    unused("host", "gw_host_registry.json (IPs)", [f"{h['ip']} {h['host_id']}" for h in hosts if h.get("ip") and h["ip"] not in zeek_ip and h["ip"] not in siem_ip],
           "registered IP never seen in SIEM or Zeek logs")
    conflict("host", "three naming schemes for the same utility systems",
             {"gw_host_registry.json": sorted(reg_h)[:8] + ["..."], "siem_alerts HostName": sorted(siem_h),
              "gridwater assets systems": sorted(gw_sys), "restricted names in rules": ["GW-WS-IT-04", "GW-SYS-JMP-01"],
              "registry has": [h for h in reg_h if "IT-04" in h or "ENG" in h]}, "high")
    miss("ot_asset", "telemetry historian AssetID", [a for a in hist_assets if a not in gw_fac and a not in gw_sys], "historian asset id absent from gridwater assets.json")
    miss("ot_asset", "maintenance/work_orders ASSETNUM", list(wo_assets), "work-order asset numbers match no registry (assets.json, scada_tags, hosts)")
    miss("ot_asset", "maintenance/work_orders LOCATION", list(wo_loc), "work-order locations match no place or facility id")
    miss("scada_tag", "telemetry historian", [t for t in hist_tags if t not in tag_names])
    unused("scada_tag", "scada_tags.json", [t for t in tag_names if t not in hist_tags])
    pumps = [k for k in ent if k.startswith("EQP-")]
    conflict("ot_asset", "pump / generator ids differ between scenario, telemetry and maintenance",
             {"entities.json": pumps, "work_orders": sorted(a for a in wo_assets if "PUMP" in a or "GEN" in a),
              "historian": sorted(a for a in hist_assets if "WTR" in a or "UTL" in a or "GEN" in a),
              "answer key T1 expects": "EQP-1102, EQP-1103 by serial; SUP-0219 order"}, "high")

    # ------------------------------------------------------------------ social accounts
    per = J(f"{REG}/personas.json")["personas"]
    reg_p = {p["handle"].lstrip("@").lower(): p for p in per}
    tw = collections.Counter()
    mentions = collections.Counter()
    fp = P(S, "social_media", "_consolidated", "tweets.jsonl")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                t = json.loads(line)
                tw[t["user"]["screen_name"]] += 1
                for m in re.findall(r"@(\w{3,})", t.get("text", "")):
                    mentions[m] += 1
    twl = {h.lower(): h for h in tw}
    char_persona = {c["name"].lstrip("@").lower(): c["id"] for c in ctx["characters"].values() if c["kind"] == "persona" and c["name"].startswith("@")}
    inv["social_account"] = {"personas.json": len(reg_p), "tweet authors": len(tw), "characters kind=persona": len(char_persona),
                             "entities.json SOC-ACC range": "5001-5040 (40 accounts, none enumerated)"}
    miss("social_account", "social_media/*.jsonl authors", [f"@{h} ({tw[h]} posts)" for h in tw if h.lower() not in reg_p], "posting account absent from personas.json")
    unused("social_account", "personas.json", [f"{p['handle']} ({p['persona_id']}, {p['account_type']})" for h, p in reg_p.items() if h not in twl],
           "persona has no posts in the feed")
    for h, cid in char_persona.items():
        conflict("social_account", f"character {cid} @{h}", {"in personas.json": h in reg_p, "posts in feed": tw.get(twl.get(h, ""), 0),
                                                              "mentions in feed": mentions.get(h, 0) + sum(v for k, v in mentions.items() if k.lower() == h)},
                 "high" if h not in twl else "low")
    news_handles = {"BaysideLedger", "CallerTimes", "KIIITVNews"} & set(tw)
    conflict("social_account", "media accounts in the feed do not match the eight fictional outlets",
             {"feed": sorted(h for h in tw if re.search(r"Ledger|Times|KIII|News|Harborline|Coastline|KNCB|Gulfwater", h)),
              "personas.json media": sorted(p["handle"] for p in per if p["account_type"] == "media"),
              "note": "CallerTimes and KIIITVNews are real-world outlet names; Harborline6News/CoastlinePublicRadio/GulfwaterMaritime/KNCB1480 never post"}, "high")

    # ------------------------------------------------------------------ drones
    dr = J(f"{REG}/drone_operators.json")
    reg_d = {o["operator_id"] for o in dr["authorized_operators"]} | {o["operator_id"] for o in dr["unauthorized_hostile_drones"]}
    d_ops = col(f"{S}/drone_video/_consolidated/drone_telemetry.csv", "operator_id")
    d_fl = col(f"{S}/drone_video/_consolidated/drone_telemetry.csv", "flight_id")
    inv["drone"] = {"drone_operators.json": len(reg_d), "telemetry operator ids": len(d_ops), "flights": len(d_fl), "entities.json": "UAS-SYN-01 to 06 (range)"}
    miss("drone", "drone_video telemetry operator_id", [o for o in d_ops if o not in reg_d], "registry uses DRN-OP-UNK for the hostile drone")
    unused("drone", "drone_operators.json", [o for o in reg_d if o not in d_ops])
    conflict("drone", "hostile drone has four different ids",
             {"entities.json": "UAS-SYN-01 to 06", "drone_operators.json": "DRN-OP-UNK", "drone telemetry": "UNKNOWN-001 / FLT-UNKNOWN-0001",
              "ADS-B": "icao24 7c1234 callsign UNKNOWN", "aircraft_registry.json": "absent"}, "high")

    # ------------------------------------------------------------------ sensors
    sr = J(f"{REG}/sensor_registry.json")
    reg_s = {s["sensor_id"] for k in ("epa_aqs_stations", "water_quality_sondes") for s in sr.get(k, [])}
    env = {os.path.basename(f).replace(".csv", "").split("_")[-1] for f in glob.glob(P(S, "env_sensors", "*.csv"))}
    wx = {os.path.basename(f).split("_")[0] for f in glob.glob(P(S, "weather", "*.csv"))}
    inv["sensor"] = {"sensor_registry.json": len(reg_s), "env_sensors files": len(env), "weather stations (no registry)": len(wx),
                     "places.json sensor ids": [k for k in ctx["places"] if k.startswith(("GAUGE", "WQ", "WW"))]}
    miss("sensor", "env_sensors/*.csv", [e for e in env if e not in reg_s])
    miss("sensor", "weather/*.csv", sorted(wx), "weather stations have no registry entry")
    miss("sensor", "00_scenario/places.json + answer key T1", ["GAUGE-12", "GAUGE-14", "WW-xx"],
         "tide/river gauges and wastewater sampling named in the scenario have no registry entry and no data file")
    unused("sensor", "sensor_registry.json", [s for s in reg_s if s not in env])

    # ------------------------------------------------------------------ CAD
    cu = J(f"{REG}/cad_units.json")
    reg_u = set()
    for ag, v in cu["agencies"].items():
        for u in v.get("units", []):
            reg_u.add(u.get("unit_id"))
    cad_u = col(f"{S}/911/911_cad_records.csv", "unit_id")
    cad_ag = col(f"{S}/911/911_cad_records.csv", "agency")
    inv["cad_unit"] = {"cad_units.json units": len(reg_u), "911 records unit_id": len(cad_u), "agencies in records": dict(cad_ag), "agencies in registry": list(cu["agencies"])}
    miss("cad_unit", "911/911_cad_records.csv", [u for u in cad_u if u and u not in reg_u])
    miss("cad_agency", "911/911_cad_records.csv", [a for a in cad_ag if a not in cu["agencies"]], "mutual-aid agencies have no registry entry")
    unused("cad_unit", "cad_units.json", [u for u in reg_u if u not in cad_u])

    # ------------------------------------------------------------------ finance
    er = J(f"{REG}/entity_registry.json")
    er_names = {}
    for k in ("insurance_companies", "adjusters", "adjustment_firms", "contractors", "financial_institutions"):
        for e in er.get(k, []):
            er_names[e["entity_id"]] = e.get("entity_name") or e.get("adjuster_name")
    er_by_name = {norm(n): i for i, n in er_names.items()}
    adj = col(f"{S}/payments/insurance_claims.csv", "adjuster_id")
    ins = col(f"{S}/payments/insurance_claims.csv", "insurer")
    claimants = col(f"{S}/payments/insurance_claims.csv", "claimant_id")
    recv = col(f"{S}/payments/financial_transactions.csv", "receiver_name")
    send = col(f"{S}/payments/financial_transactions.csv", "sender_name")
    routing = col(f"{S}/payments/financial_transactions.csv", "sender_routing")
    banks = {b.get("routing_number") for b in er.get("financial_institutions", [])}
    inv["finance"] = {"entity_registry.json entities": len(er_names), "claims adjuster ids": len(adj), "claims insurers": len(ins),
                      "claimant ids": len([c for c in claimants if c]), "txn receivers": len(recv), "txn senders": len(send)}
    miss("adjuster", "payments/insurance_claims.csv", [a for a in adj if a and a not in er_names])
    miss("organisation", "payments/financial_transactions.csv receiver", [f"{n} ({c})" for n, c in recv.items() if c >= 3 and norm(n) not in er_by_name],
         "payees paid 3+ times with no entity record")
    miss("organisation", "payments/financial_transactions.csv sender", [f"{n} ({c})" for n, c in send.items() if c >= 3 and norm(n) not in er_by_name])
    miss("bank", "payments/financial_transactions.csv sender_routing", [r for r in routing if r and r not in banks])
    pay_text = open(P(S, "payments", "insurance_claims.csv"), encoding="utf-8").read() + open(P(S, "payments", "financial_transactions.csv"), encoding="utf-8").read()
    bank_routing = {b["entity_id"]: b.get("routing_number") for b in er.get("financial_institutions", [])}
    unused("organisation", "entity_registry.json", [f"{i} {n}" for i, n in er_names.items()
                                                    if n not in pay_text and i not in pay_text and bank_routing.get(i) not in routing],
           "entity appears in neither claims nor transactions")
    conflict("finance", "fraud-ring identifiers differ between scenario and streams",
             {"entities.json": ["SYN-PER-700001 to 700006", "BANK-SYN-71, 72, 73", "SUP-0388 Vantorra", "SUP-0390 Quellmar"],
              "insurance_claims claimant ids": sorted({re.sub(r"\d+$", "", c) + "*" for c in claimants if c}),
              "entity_registry.json": ["CON-SHELL-001 RV Restoration LLC", "CON-SHELL-002", "BANK-CC-001..003", "GW-ENT-005 FastTrack (GW- prefix clashes with gridwater GW-ENT-01..03)"],
              "transactions": {n: recv[n] for n in recv if re.search("Vantorra|Quellmar|RV Restoration", n)}}, "high")

    # ------------------------------------------------------------------ infrastructure / terminals / satellite
    inf = [i["structure_id"] for i in J(f"{REG}/infrastructure_assets.json")["critical_infrastructure"]]
    dmg = col(f"{S}/infrastructure/damage_assessment.csv", "structure_id")
    inv["infrastructure"] = {"infrastructure_assets.json": len(inf), "damage_assessment structure ids": len(dmg)}
    unused("infrastructure", "infrastructure_assets.json", [i for i in inf if i not in dmg], "critical-infrastructure ids never appear in damage_assessment.csv (which uses CC-#####)")
    tr = J(f"{REG}/terminal_registry.json")
    reg_t = {t["terminal_id"]: t for t in tr["terminals"]}
    arr_t = col(f"{S}/supply/vessel_arrivals.csv", "terminal_id")
    inv["terminal"] = {"terminal_registry.json": len(reg_t), "vessel_arrivals terminal ids": len(arr_t)}
    miss("terminal", "supply/vessel_arrivals.csv", [t for t in arr_t if t and t not in reg_t])
    unused("terminal", "terminal_registry.json", [f"{t} {reg_t[t]['terminal_name']}" for t in reg_t if t not in arr_t])
    dangling = sorted({t["operator_entity_id"] for t in reg_t.values() if t.get("operator_entity_id")})
    miss("organisation", "terminal_registry.json operator_entity_id", dangling, "ENT-ORG-* ids point at no record anywhere")
    conflict("terminal", "TERM-01 exists as a Place and as a registry terminal; other terminals are not places",
             {"places.json": [k for k in ctx["places"] if k.startswith(("TERM", "TANK", "ANC", "ENT-"))],
              "terminal_registry.json": sorted(reg_t)}, "medium")
    cons = col(f"{S}/supply/cargo_manifest.csv", "consignee_name")
    agents = col(f"{S}/supply/vessel_arrivals.csv", "agent_name")
    miss("organisation", "supply/cargo_manifest.csv consignee", [f"{n} ({c})" for n, c in cons.items()], "consignees have no entity record")
    miss("organisation", "supply/vessel_arrivals.csv agent", [f"{n} ({c})" for n, c in agents.items()], "ship agents have no entity record")
    sat = sorted(os.path.basename(f)[:-5] for f in glob.glob(P(S, "satellite", "RAFAEL-*.json")))
    inv["satellite_scene"] = {"scene files": len(sat), "ids": sat}

    # ------------------------------------------------------------------ utility naming, real names, duplicate catalogs
    def count_text(pat):
        out = {}
        blob = {"stories": " ".join(s["headline"] + " " + s["dek"] + " " + " ".join(s["body"]) for s in stories),
                "public_facts": " ".join(f["statement"] for f in facts),
                "msel": " ".join(e["description"] for e in msel),
                "registries": " ".join(open(f, encoding="utf-8").read() for f in glob.glob(P(REG, "*.json")))}
        for k, v in blob.items():
            out[k] = len(re.findall(pat, v))
        for d in ("social_media/_consolidated/tweets.jsonl", "network_logs/siem_alerts.csv", "public_health/eas_broadcasts.csv", "maintenance/work_orders.csv"):
            fp2 = P(S, d)
            if os.path.exists(fp2):
                out[d] = len(re.findall(pat, open(fp2, encoding="utf-8", errors="replace").read()))
        return out
    naming = {"GridWater": count_text(r"GridWater|Grid Water"), "CBPWA / Coastal Bend Power": count_text(r"CBPWA|Coastal Bend Power"),
              "AEP Texas": count_text(r"AEP Texas"), "ERCOT": count_text(r"ERCOT"),
              "City water department": count_text(r"Water Department|water utility|city utility")}
    conflict("utility", "the utility operator has several names", naming, "high")
    real = {}
    for pat in ("Flint Hills", "Buckeye", "NuStar", "Maxus", "Caller[- ]?Times", "KIII", "KRIS", "Sinai", "Driscoll", "Valero", "Citgo", "Cheniere", "AEP Texas", "American Bank Center"):
        hits = {}
        for d in glob.glob(P(REG, "*.json")) + glob.glob(P(S, "supply", "*.csv")) + [P(S, "social_media", "_consolidated", "tweets.jsonl"), mp,
                                                                                  P(S, "911", "911_cad_records.csv")]:
            if os.path.exists(d):
                n = len(re.findall(pat, open(d, encoding="utf-8", errors="replace").read()))
                if n:
                    hits[os.path.relpath(d, ROOT)] = n
        n = sum(len(re.findall(pat, s["headline"] + " ".join(s["body"]))) for s in stories)
        if n:
            hits["news stories"] = n
        if hits:
            real[pat] = hits
    R["graph_gaps"]["real_world_org_names_in_synthetic_data"] = real
    dup = {}
    for f in sorted(glob.glob(P(REG, "entity_catalogs", "*.json"))):
        b = P(REG, os.path.basename(f))
        if os.path.exists(b):
            a1, b1 = open(f, "rb").read(), open(b, "rb").read()
            dup[os.path.basename(f)] = "identical" if a1 == b1 else f"DIVERGED (entity_catalogs {len(a1)} bytes vs top-level {len(b1)} bytes)"
    for k, v in dup.items():
        if v != "identical":
            conflict("registry_file", f"two different copies of {k}", v, "high")
    gwm = J("scenarios/gridwater/00_scenario/msel.json")
    if not gwm and any(e.startswith("GW-EVT") for e in ctx["msel"]):
        conflict("scenario_layer", "gridwater layer files are empty while GW-EVT events live in the base MSEL",
                 {"scenarios/gridwater/00_scenario/msel.json": len(gwm), "GW-EVT in 00_scenario/msel.json": sum(1 for e in ctx["msel"] if e.startswith("GW-EVT")),
                  "README": "still says 'no events, facts or state yet'"}, "medium")

    # ------------------------------------------------------------------ named things in news with no entity record
    known = {}
    def know(name, where):
        if name:
            known.setdefault(norm(name), where)
    for k, e in ent.items(): know(e["name"], f"entities.json {k}")
    for k, p in ctx["places"].items(): know(p["name"], f"places.json {k}")
    for c in ctx["characters"].values(): know(c["name"], f"characters.json {c['id']}")
    for o in ctx["outlets"].values(): know(o["name"], f"outlets.json {o['outlet_id']}")
    for v in ves: know(v["vessel_name"], f"vessels.json {v['vessel_id']}")
    for i, n in reg_f.items(): know(n, f"facility_registry.json {i}")
    for i, n in er_names.items(): know(n, f"entity_registry.json {i}")
    for t in reg_t.values(): know(t["terminal_name"], f"terminal_registry.json {t['terminal_id']}"); know(t.get("operator"), f"terminal_registry.json {t['terminal_id']} operator")
    for i, n in {**gw_fac, **gw_sys, **gw_ent}.items(): know(n, f"gridwater assets {i}")
    for a in ac: know(a["operator"], f"aircraft_registry.json {a['aircraft_id']} operator")
    for o in dr["authorized_operators"]: know(o["org_name"], f"drone_operators.json {o['operator_id']}")
    for p in per: know(p["display_name"], f"personas.json {p['persona_id']}")
    for c in ctx["characters"].values():
        know(c["affiliation"].get("org"), f"characters.json {c['id']} affiliation (text only)")

    FUNC = set("""The A An In On At For And But Or If As By To Of With From After Before When While Since Until This That These Those He She It They
        We You His Her Their Our Its Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August
        September October November December Sept Oct Nov Dec Jan Feb Aug What Who Why How Where Here There No Not Yes Some Most Many More About Still
        Now Then So Also Both Each Every All Any One Two Three Four Five Six Seven Eight Nine Ten Is Are Was Were Be Been Has Have Had Do Does Did
        Will Would Can Could Should May Might Must Neither Nor Either Under Over Near Inside Outside Across Along Between Against During Through
        Because Although Though Once Only Even Just Last Next Late Early Federal State Local Officials Official Residents Crews Investigators
        Opinion Analysis Explainer Update Breaking Listen Special Fact Mr Ms Mrs Dr Lt Cmdr Capt Col Gen Sgt Chief Pastor Judge Mayor Sen Rep
        El La Los Las De Del Por Para Con Una Un Que Se En Es Su Sus Al Lo Le Hoy Pero Como Cuando Según Segun""".split())
    TITLES = set("Director Commander Officer Supervisor Administrator Councilmember Commissioner Coordinator Chief Captain Sheriff Manager Spokesman Spokeswoman President Secretary".split())
    GEO = set("""texas corpus christi nueces county port aransas mustang island north beach flour bluff san patricio pass padre calallen portland
        rockport ingleside kingsville robstown coastal bend gulf coast mexico bay south central west east northwest harbor inner channel ship
        hurricane tropical storm rafael category district districts zone zones oak park hillcrest molina downtown beach city fort worth hood
        antonio houston austin dallas victoria united states america caribbean laguna madre river delta jetties seawall shoreline""".split())
    ORG = (r"\b(LLC|Inc|Corp|Ltd|Partners|Holdings|Systems|Terminals?|Authority|Agency|Department|Office|Service|Services|Guard|Command|Center|Centre|"
           r"Commission|Council|Court|University|College|School|Hospital|Medical|Clinic|Bank|Fund|Program|Division|Bureau|Administration|Association|"
           r"Radio|News|Ledger|Wire|Weekly|Report|Station|Depot|Base|Bridge|Causeway|Plant|Church|Restoration|Maritime|Logistics|Force|Team|Operation|"
           r"Sector|Unit|Board|Institute|Company|Group|Hotline|Portal|Network|Navy|Army|Marines?|FEMA|FBI|CISA|NOAA|NWS|TCEQ|TDEM|EPA|FAA|DLA|SBA|NFIP|"
           r"Coordinator|Trust|Coalition|Alliance|Foundation|Pantry|Shelter|Airport|Depot|Pipeline|Refinery|Energy|Pumps|Controls|Marine|Shipping|"
           r"Insurance|Mutual|Construction|Roofing|Tackle|Charters?|Parish|Diocese|Academy|ISD|Works|Water|Power|Electric|Telecom|Transit|Police|Fire)\b")
    VES = r"^(MT|MV|FV|USCGC|M/V|M/T)\s|^[Tt]ug\s+[A-Z]"
    tok = r"(?:(?:[A-Z]\.){2,}|[A-Z][A-Za-z0-9&'’\-]*|[A-Z]{2,})"
    pat = re.compile(rf"\b{tok}(?:\s+(?:of|de|del|for|and|&|on)\s+(?:the\s+)?{tok}|\s+{tok}){{1,7}}")
    cand = collections.Counter()
    where = collections.defaultdict(list)

    def clean(words):
        while words and (words[0].rstrip(".") in FUNC or words[0] in ("the", "and", "of") or words[0] in TITLES):
            words = words[1:]
        while words and (words[-1] in FUNC or words[-1].lower() in ("of", "and", "the", "for", "on", "de", "del", "&")):
            words = words[:-1]
        if words:
            words[-1] = re.sub(r"['’]s?$", "", words[-1])
        return words

    def add(name, ref, seen):
        words = clean(name.split())
        if len(words) < 2:
            return
        name = " ".join(words)
        if all(w.lower().strip(".") in GEO or w.lower() in ("of", "and", "the", "for", "on") for w in words):
            return
        if name in seen:
            return
        seen.add(name)
        cand[name] += 1
        if len(where[name]) < 6:
            where[name].append(ref)

    def scan(text, ref):
        seen = set()
        for m in pat.finditer(text):
            full = m.group(0)
            parts = [full]
            if " and " in full:                      # "X Authority and Y Agency" -> two names; keep "Power and Water Authority" whole
                l, r = full.split(" and ", 1)
                if re.search(ORG + r"$", l.strip()) or re.search(VES, r.strip()) or norm(" ".join(clean(l.split()))) in known:
                    parts = [l, r]
            for p_ in parts:
                add(p_, ref, seen)

    for s_ in stories:
        scan(" | ".join([s_["headline"], s_["dek"]] + s_["body"]), s_["story_id"])
    for f in facts:
        scan(f["statement"], f["id"])

    char_names = {c["name"] for c in ctx["characters"].values()}
    char_last = {c["name"].split()[-1] for c in ctx["characters"].values()}
    rows = []
    for name, c in cand.most_common():
        if c < 2:
            break
        n = norm(name)
        if not n or name in char_names or any(cn in name for cn in char_names):
            continue
        exact = known.get(n)
        if exact and "text only" not in exact:
            continue                                  # already a first-class record somewhere
        kind = "vessel" if re.search(VES, name) else "organisation/facility/programme" if re.search(ORG, name) else None
        if kind is None:
            continue
        partial = exact or next((v for k, v in known.items() if len(k) > 8 and len(n) > 8 and (n in k or k in n)), None)
        rows.append({"name": name, "kind": kind, "mentions": c, "examples": where[name], "exists_elsewhere_as": partial})
    names = {r["name"]: r["mentions"] for r in rows}
    orgs = [r for r in rows if not any(r["name"] != o and r["name"] in o and mo >= 0.8 * r["mentions"] for o, mo in names.items())]

    # people named with a speech or apposition cue who are not characters
    nm = r"((?:[A-Z][a-zñáéíóúü'’\-]+\.?\s+){1,2}(?:(?:de|del|la|van|von)\s+)?[A-Z][a-zñáéíóúü'’\-]+(?:-[A-Z][a-zñáéíóúü]+)?)"
    cues = [re.compile(r"\b(?:said|says|dijo|told|according to|asked)\s+" + nm), re.compile(nm + r",\s+(?:\d{2}\b|an?\s|the\s|who\s|whose\s|una?\s|el\s|la\s)"),
            re.compile(nm + r"\s+(?:said|says|dijo|told|testified|announced)\b")]
    pc = collections.Counter()
    pw = collections.defaultdict(list)
    for s_ in stories:
        text = " ".join(s_["body"])
        found = set()
        for cre in cues:
            for m in cre.finditer(text):
                w = clean(m.group(1).split())
                if 2 <= len(w) <= 4:
                    found.add(" ".join(w))
        for name in found:
            pc[name] += 1
            if len(pw[name]) < 6:
                pw[name].append(s_["story_id"])
    for f in facts:
        for cre in cues:
            for m in cre.finditer(f["statement"]):
                w = clean(m.group(1).split())
                if 2 <= len(w) <= 4:
                    name = " ".join(w)
                    pc[name] += 1
                    pw[name].append(f["id"])
    people = []
    for name, c in pc.most_common():
        w = name.split()
        if name in char_names or re.search(ORG, name) or all(x.lower() in GEO for x in w) or any(x in FUNC for x in w):
            continue
        if "." in name or name.endswith("-") or norm(name) in known or len(w) < 2:
            continue
        if re.search(r"\b(Street|Drive|Road|Boulevard|Avenue|Bay|Docks|Fairgrounds|Lab|District|Assistance|Security|Parks|Christi|County|Emergency|Provider|Meridian|Listeners|Nunca)$", name):
            continue
        if any(name in cn or cn in name for cn in char_names):
            continue
        hint = "shares a surname with a character" if w[-1] in char_last else None
        people.append({"name": name, "kind": "person (not a character)", "mentions": c, "examples": pw[name][:6], "exists_elsewhere_as": hint})
    R["unregistered_named_entities"] = orgs[:150] + people[:80]
    R["graph_gaps"]["unregistered_named_entity_counts"] = {"organisations_facilities_programmes_vessels": len(orgs), "people_not_characters": len(people)}

    # explicit spot checks named in the brief
    spot = ["Rendal Terminals", "Brightwake Marine Systems", "Vantorra Restoration", "Quellmar Fuel Partners", "Brannoch Maritime Holdings",
            "Kalvora Star", "Ostrel Bay", "Corrin Bay", "Pelican Ridge", "Gulf Provider", "Shoreline Regional Medical Center", "Bay City Medical Center",
            "Unified Command", "FastDry Coastal", "Operation Sandbar", "Coastal Bend Power and Water Authority", "Texas General Land Office",
            "Coast Guard Sector Corpus Christi", "Nueces County Office of Emergency Management", "Halcyon Drift", "Gulf Relief Logistics", "Delta Pumps"]
    all_text = " ".join(s["headline"] + " " + " ".join(s["body"]) for s in stories)
    fact_text = " ".join(f["statement"] for f in facts)
    reg_text = {os.path.basename(f): open(f, encoding="utf-8").read() for f in glob.glob(P(REG, "*.json"))}
    stream_hits = {}
    spot_out = []
    for n in spot:
        rec = {"name": n, "stories": len(re.findall(re.escape(n), all_text)), "facts": len(re.findall(re.escape(n), fact_text)),
               "scenario_entity": next((k for k, e in ent.items() if n.lower() in e["name"].lower()), None),
               "place": next((k for k, p in ctx["places"].items() if n.lower() in (p["name"] + " " + p["type"]).lower()), None),
               "registries": [k for k, v in reg_text.items() if n in v]}
        spot_out.append(rec)
    R["graph_gaps"]["spot_checks"] = spot_out

    # ------------------------------------------------------------------ knowledge graph
    g = J("04_knowledge_graph/internal/graph.json")
    nodes = {n["id"]: n for n in g["nodes"]}
    edges = g.get("edges") or g.get("links")
    deg = collections.Counter()
    out_e = collections.defaultdict(list)
    in_e = collections.defaultdict(list)
    for e in edges:
        deg[e["source"]] += 1
        deg[e["target"]] += 1
        out_e[e["source"]].append(e)
        in_e[e["target"]].append(e)
    types = collections.Counter(n["type"] for n in nodes.values())
    rels = collections.Counter(e["rel"] for e in edges)
    orphans = [{"id": n["id"], "type": n["type"], "label": n["label"]} for n in nodes.values() if deg[n["id"]] == 0]
    def has(nid, rel, direction="out"):
        return any(e["rel"] == rel for e in (out_e if direction == "out" else in_e)[nid])
    ev = [n for n in nodes.values() if n["type"] == "Event"]
    ev_no_place = [n["id"] for n in ev if not has(n["id"], "AT_PLACE")]
    ev_no_thread = [n["id"] for n in ev if not has(n["id"], "PART_OF_THREAD")]
    ev_no_fact = [n["id"] for n in ev if not has(n["id"], "REVEALS_EVENT", "in")]
    ev_no_story = [n["id"] for n in ev if not has(n["id"], "DEPICTS_EVENT", "in")]
    fa = [n for n in nodes.values() if n["type"] == "PublicFact"]
    fact_no_story = [n["id"] for n in fa if not has(n["id"], "CITES_FACT", "in")]
    fact_no_event = [n["id"] for n in fa if not has(n["id"], "REVEALS_EVENT")]
    fact_no_place = [n["id"] for n in fa if not has(n["id"], "ABOUT_PLACE")]
    fact_no_source = [n["id"] for n in fa if not has(n["id"], "SOURCED_FROM")]
    stn = [n for n in nodes.values() if n["type"] == "Story"]
    story_no_fact = [n["id"] for n in stn if not has(n["id"], "CITES_FACT")]
    story_no_arc = [n["id"] for n in stn if not has(n["id"], "IN_ARC")]
    story_no_place = [n["id"] for n in stn if not has(n["id"], "ABOUT_PLACE")]
    story_no_event = [n["id"] for n in stn if not has(n["id"], "DEPICTS_EVENT")]
    chn = [n for n in nodes.values() if n["type"] == "Character"]
    char_no_story = [f"{n['id']} {n['label']} ({n.get('kind')})" for n in chn
                     if not any(e["rel"] in ("QUOTES", "MENTIONS", "WRITTEN_BY") for e in in_e[n["id"]])]
    char_no_org_node = [f"{c['id']} {c['name']} -> {c['affiliation'].get('org')}" for c in ctx["characters"].values()
                        if c["affiliation"].get("org") and not c["affiliation"].get("org_id")]
    ent_edge_rels = collections.Counter(e["rel"] for e in edges if nodes[e["source"]]["type"] == "Entity" or nodes[e["target"]]["type"] == "Entity")
    place_ids = set(ctx["places"])
    story_places = collections.Counter(p for s in stories for p in s["tags"].get("places", []))
    places_not_nodes = [p for p in story_places if p not in nodes]
    place_unused = [f"{p} {ctx['places'][p]['name']}" for p in place_ids if not in_e[p] and not out_e[p]]
    # place names used in streams that are not Place nodes
    stream_places = collections.Counter()
    for (city,), c in ((k if isinstance(k, tuple) else (k,), v) for k, v in col(f"{S}/911/911_cad_records.csv", "city").items()):
        stream_places[city.title()] += c
    beats = col(f"{S}/911/911_cad_records.csv", "beat")
    zips = col(f"{S}/public_health/_consolidated/ed_visits.csv", "C_ZIP")
    tracts = col(f"{S}/census/acs_nueces_tracts.csv", "GEOID")
    known_types = set(types)
    wanted = ["Organization", "Vessel", "Aircraft", "Facility", "Terminal", "Sensor", "Host", "ScadaTag", "SocialAccount", "DroneFlight",
              "ResponseUnit", "DataStream", "DataRecord/Observation", "AnswerKeyPath", "Equipment", "Contract", "Claim", "Alert", "Neighborhood/Tract/ZIP"]
    ak = J("06_answer_key/answer_key.json")
    ak_threads = {p.get("thread_id") or p.get("thread") for p in ak["paths"]}
    R["graph_gaps"].update({
        "node_types_present": dict(types), "edge_types_present": dict(rels), "node_types_missing": [w for w in wanted if w not in known_types],
        "entity_nodes": types.get("Entity", 0), "entity_edge_types": dict(ent_edge_rels),
        "orphans": orphans,
        "orphan_cause": "build_graph.py creates Entity nodes but only ever links them when a character's affiliation.org_id points at one "
                        "(AFFILIATED_WITH). MSEL events, facts and stories carry no entity ids (events have place_ids only), and several entity ids are "
                        "ranges ('EQP-1101 to 1104', 'SOC-ACC-5001 to 5040') that nothing can reference. GAUGE-14 and 'WQ-01 to WQ-06' are Place nodes no "
                        "event, fact or story lists.",
        "events_without_place": ev_no_place, "events_without_thread": ev_no_thread, "events_without_public_fact": ev_no_fact,
        "events_without_story": ev_no_story, "facts_cited_by_no_story": fact_no_story, "facts_without_event": fact_no_event,
        "facts_without_place": fact_no_place, "facts_without_source_character": fact_no_source,
        "stories_without_fact": story_no_fact, "stories_without_arc": story_no_arc, "stories_without_place": story_no_place,
        "stories_without_event": story_no_event, "characters_in_no_story": char_no_story,
        "characters_with_text_only_org": char_no_org_node,
        "story_place_tags_not_place_nodes": places_not_nodes, "places_with_no_edges": place_unused,
        "stream_geography_not_in_graph": {"911 cities": dict(stream_places.most_common(12)), "911 beats": len(beats), "ED visit ZIP codes": len(zips),
                                          "census tracts": len(tracts), "note": "PLC-010/PLC-011 stand for groups of tracts but no tract, ZIP, beat or neighbourhood is a node"},
        "threads_without_answer_key": [t["thread_id"] for t in threads if t["thread_id"] not in ak_threads],
        "duplicate_registry_files": dup,
    })

    # ------------------------------------------------------------------ thread completeness
    W = lambda t: r"(?<![a-z])(?:%s)(?![a-z])" % t      # short tokens must stand alone ("soc" must not match "social")
    STREAM_MAP = [
        (r"ship track|vessel|maritime|radar|buoy_r|port_radar|" + W("ais"), "ais"),
        (r"aircraft|ads-b|flight|laanc|notam|" + W("adsb|faa|faanex"), "adsb"),
        (r"dispatch|call_audio|ani_ali|" + W("911|cad|psap"), "911"),
        (r"public health|hospital|syndrom|wastewater|essence|" + W("ed|epi|er"), "public_health"),
        (r"telemetry|scada|historian|water_pressure|relay_config|" + W("ercot|rtu|hmi"), "telemetry"),
        (r"maintenance|work order|maximo", "maintenance"),
        (r"network|netflow|firewall|" + W("siem|soc|ciso|edr|vpn|zeek|dns"), "network_logs"),
        (r"payment|bank|claim|insur|financial", "payments"),
        (r"supply|manifest|cargo|logistic", "supply"),
        (r"social|tweet|platform|" + W("cib"), "social_media"),
        (r"satellite|sar_imagery|imagery|landsat", "satellite"),
        (r"drone|argus|camcc|" + W("uas|uav"), "drone_video"),
        (r"weather|asos|" + W("nws|nhc"), "weather"),
        (r"environment|sensor|sonde|air quality|gauge|tide|tceq_buoy|" + W("aqs"), "env_sensors"),
        (r"census|tract|" + W("acs|maps|gis"), "census"),
        (r"infrastructure|damage_assess|fema_gis|fema_phase|" + W("pda"), "infrastructure"),
        (r"ipaws|broadcast_log|dma_broadcast|" + W("eas|wea"), "public_health/eas_broadcasts.csv"),
        (r"public_record|" + W("news"), "news"),
    ]
    stream_dirs = {d for d in os.listdir(P(S)) if os.path.isdir(P(S, d))}
    def map_stream(label):
        l = label.lower()
        for pat_, d in STREAM_MAP:
            if re.search(pat_, l):
                return d
        return None
    arcs = ctx["arcs"]
    arc_threads = collections.defaultdict(set)
    for a in arcs.values():
        for t in a.get("threads", []):
            arc_threads[t].add(a["arc_id"])
    ev_thread = collections.defaultdict(list)
    for e in msel:
        for t in e["threads"]:
            ev_thread[t].append(e)
    fact_by_event = collections.defaultdict(set)
    for f in facts:
        for e in f.get("events", []):
            fact_by_event[e].add(f["id"])
    events_of_fact = collections.defaultdict(set)
    for f in facts:
        for e in f.get("events", []):
            events_of_fact[f["id"]].add(e)
    for e in msel:
        if e.get("public_fact"):
            events_of_fact[e["public_fact"]].add(e["event_id"])
    story_events = collections.defaultdict(set)
    for s in stories:
        evs_ = set(s.get("internal", {}).get("truth_events", []))
        for f in s["tags"].get("public_facts", []):
            evs_ |= events_of_fact[f]
        for e in evs_:
            story_events[e].add(s["story_id"])
    unmapped_labels = collections.Counter()
    ak_text = {(p.get("thread_id") or p.get("thread")): json.dumps(p) for p in ak["paths"]}
    for t in threads:
        tid = t["thread_id"]
        evs = ev_thread[tid]
        days = [e["day"] for e in evs]
        fset = set()
        for e in evs:
            fset |= fact_by_event[e["event_id"]]
            if e.get("public_fact"):
                fset.add(e["public_fact"])
        fset |= {f["id"] for f in facts if tid in f.get("threads", [])}
        sset = set()
        for e in evs:
            sset |= story_events[e["event_id"]]
        arc_st = {s["story_id"] for s in stories if set(s["tags"].get("arcs", [])) & arc_threads[tid]}
        labels = collections.Counter((o["stream"] if isinstance(o, dict) else o) for e in evs for o in e.get("observed_in", []))
        mapped = collections.Counter()
        nofile = []
        for lab, c in labels.items():
            d = map_stream(lab)
            if d is None:
                nofile.append(lab)
                unmapped_labels[lab] += c
            else:
                mapped[d] += c
        present = sorted(d for d in mapped if d in stream_dirs or d.startswith("public_health/") or d == "news")
        absent = sorted(d for d in mapped if d not in present)
        fdays = sorted(ctx["facts"][f]["day"] for f in fset if f in ctx["facts"])
        missing = []
        if tid not in ak_threads:
            missing.append("no answer key path")
        if not fset:
            missing.append("no public fact (nothing ever surfaces publicly)")
        if not (sset or arc_st):
            missing.append("no news story linked")
        if not arc_threads[tid]:
            missing.append("no story arc surfaces this thread")
        if nofile:
            missing.append(f"{len(nofile)} evidence sources named in MSEL have no data stream ({', '.join(sorted(nofile)[:5])}{'…' if len(nofile) > 5 else ''})")
        if days and max(days) > 31:
            missing.append(f"events run to D{max(days):+d} but most streams stop at D+31 (Oct 15)")
        ents_in_ak = sorted(set(re.findall(r"\b(?:VSL|BRG|ACF|EQP|SUP|ORG|HOST|DOM|DEV|JAM|GAUGE|FAC|BANK-SYN|SOC-ACC|SYN-PER|UAS-SYN|WW|ANC|TERM|TANK|GW-[A-Z]+)-[A-Za-z0-9\-]+", ak_text.get(tid, ""))))
        dangling_ak = [x for x in ents_in_ak if x not in ent and x not in ctx["places"] and x not in gw_fac and x not in gw_sys and x not in gw_ent
                       and x not in reg_h and not any(x in k for k in list(ent) + list(ctx["places"]))]
        if dangling_ak:
            missing.append(f"answer key cites ids with no record: {', '.join(dangling_ak[:6])}")
        stage = {"begin": bool(days), "escalation": len(evs) >= 3, "discovery": bool(fset), "resolution": bool(fdays and fdays[-1] >= (max(days) if days else 0) - 0) and len(fset) >= 2}
        R["thread_completeness"].append({
            "thread": tid, "name": t["name"], "msel_events": len(evs), "day_span": [min(days), max(days)] if days else None,
            "public_facts": len(fset), "fact_day_span": [fdays[0], fdays[-1]] if fdays else None,
            "stories_via_events": len(sset), "stories_via_arcs": len(arc_st), "arcs": sorted(arc_threads[tid]),
            "streams_with_evidence_present": present, "streams_named_but_no_directory": absent, "observation_sources_with_no_stream": sorted(nofile),
            "answer_key": tid in ak_threads, "arc_stages": stage, "missing": missing})
    R["graph_gaps"]["msel_observed_in_labels_with_no_stream"] = dict(unmapped_labels.most_common())
    R["graph_gaps"]["msel_observed_in_label_variants"] = len({(o["stream"] if isinstance(o, dict) else o) for e in msel for o in e.get("observed_in", [])})

    # ------------------------------------------------------------------ write
    out_dir = P("07_validation", "reports")
    os.makedirs(out_dir, exist_ok=True)
    R["recommended_schema"] = RECOMMENDED_SCHEMA
    R["summary"] = {
        "missing_registry_ids": sum(x["count"] for x in R["missing_registry_entries"]),
        "unused_registry_ids": sum(x["count"] for x in R["unused_registry_entries"]),
        "id_conflicts": len(R["id_conflicts"]), "high_severity_conflicts": sum(1 for c in R["id_conflicts"] if c["severity"] == "high"),
        "unregistered_named_entities_listed": len(R["unregistered_named_entities"]),
        "graph": {"nodes": len(nodes), "edges": len(edges), "orphans": len(orphans)},
        "threads_without_answer_key": len(R["graph_gaps"]["threads_without_answer_key"]),
    }
    with open(os.path.join(out_dir, "entity_graph_audit.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=1)
    write_md(R, os.path.join(out_dir, "entity_graph_audit.md"))
    s = R["summary"]
    print(f"audit: {s['missing_registry_ids']} ids used with no registry entry, {s['unused_registry_ids']} registry ids unused, "
          f"{s['id_conflicts']} conflicts ({s['high_severity_conflicts']} high), {s['graph']['orphans']} graph orphans, "
          f"{s['threads_without_answer_key']} threads without answer key")


def write_md(R, fp):
    L = []
    a = L.append
    s = R["summary"]
    g = R["graph_gaps"]
    a("# Entity and knowledge-graph audit\n")
    a("Generated by `scripts/audit_entities.py` (read-only). Machine-readable version: `entity_graph_audit.json`.\n")
    a("## Headline numbers\n")
    a(f"- **{s['missing_registry_ids']}** ids are used in streams or scenario files with no registry entry.")
    a(f"- **{s['unused_registry_ids']}** registry ids are never used by any stream.")
    a(f"- **{s['id_conflicts']}** naming or id conflicts, {s['high_severity_conflicts']} of them high severity.")
    a(f"- Graph: {s['graph']['nodes']} nodes, {s['graph']['edges']} edges, **{s['graph']['orphans']} orphans**; node types: "
      + ", ".join(f"{k} {v}" for k, v in g["node_types_present"].items()) + ".")
    a(f"- Node types the graph does not have: {', '.join(g['node_types_missing'])}.")
    a(f"- **{s['threads_without_answer_key']}** of 22 threads have no answer-key path: {', '.join(g['threads_without_answer_key'])}.")
    a(f"- Named things in news/public record with no entity record: {g['unregistered_named_entity_counts']['organisations_facilities_programmes_vessels']} "
      f"organisations/facilities/programmes/vessels and {g['unregistered_named_entity_counts']['people_not_characters']} people who are not characters (organisations mentioned in 2+ stories or facts).\n")
    a("## 1. Inventory: where each identifier class appears\n")
    a("| Class | Source | Count |\n|---|---|---|")
    for cls, d in R["inventory"].items():
        for k, v in d.items():
            a(f"| {cls} | {k} | {v if not isinstance(v, (list, dict)) else json.dumps(v, ensure_ascii=False)[:160]} |")
    a("\n## 2a. Ids used but missing from a registry\n")
    a("| Class | Used in | Count | Ids | Note |\n|---|---|---|---|---|")
    for x in R["missing_registry_entries"]:
        a(f"| {x['class']} | {x['used_in']} | {x['count']} | {'; '.join(short(x['ids'], 14))} | {x['note']} |")
    a("\n## 2b. Registry entries never used by a stream\n")
    a("| Class | Registry | Count | Ids | Note |\n|---|---|---|---|---|")
    for x in R["unused_registry_entries"]:
        a(f"| {x['class']} | {x['registry']} | {x['count']} | {'; '.join(short(x['ids'], 14))} | {x['note']} |")
    a("\n## 2c. Same thing under different ids or names\n")
    for sev in ("high", "medium", "low"):
        items = [c for c in R["id_conflicts"] if c["severity"] == sev]
        if not items:
            continue
        a(f"### {sev.title()} severity ({len(items)})\n")
        for c in items[:60]:
            a(f"- **[{c['class']}] {c['issue']}**: `{json.dumps(c['detail'], ensure_ascii=False)[:700]}`")
        if len(items) > 60:
            a(f"- … {len(items) - 60} more in the JSON file")
        a("")
    a("### Duplicate registry files\n")
    for k, v in g["duplicate_registry_files"].items():
        a(f"- `06_data_streams/entity_catalogs/{k}` vs `06_data_streams/{k}`: {v}")
    a("\n### Real-world organisation names inside the synthetic data\n")
    a("The project rule is real places, fictional people; these real company or outlet names appear in data teams will receive.\n")
    for k, v in g["real_world_org_names_in_synthetic_data"].items():
        a(f"- **{k}**: {json.dumps(v)}")
    a("\n## 3. Named things in news and the public record with no entity record\n")
    a("### Spot checks\n")
    a("| Name | Story mentions | Fact mentions | Scenario entity | Place | Registries containing the name |\n|---|---|---|---|---|---|")
    for r in g["spot_checks"]:
        a(f"| {r['name']} | {r['stories']} | {r['facts']} | {r['scenario_entity'] or '—'} | {r['place'] or '—'} | {', '.join(r['registries']) or '—'} |")
    a("\n### Organisations, facilities, programmes and vessels (top 150 by mentions)\n")
    a("| Name | Kind | Stories/facts | Examples | Exists elsewhere as |\n|---|---|---|---|---|")
    for r in R["unregistered_named_entities"]:
        if not r["kind"].startswith("person"):
            a(f"| {r['name']} | {r['kind']} | {r['mentions']} | {', '.join(r['examples'][:4])} | {r['exists_elsewhere_as'] or '—'} |")
    a("\n### People named in stories who are not characters (top 80)\n")
    a("Found by speech and apposition cues (said X; X, 54,; X, a ...); names that match no character record. A few false positives remain.\n")
    a("| Name | Stories/facts | Examples |\n|---|---|---|")
    for r in R["unregistered_named_entities"]:
        if r["kind"].startswith("person"):
            a(f"| {r['name']} | {r['mentions']} | {', '.join(r['examples'][:4])} |")
    a("\n## 4. Knowledge graph\n")
    a(f"- Edge types: {', '.join(f'{k} {v}' for k, v in sorted(g['edge_types_present'].items(), key=lambda x: -x[1]))}.")
    a(f"- Entity nodes: {g['entity_nodes']}; edges touching an Entity: {g['entity_edge_types'] or 'none'}.")
    a(f"- **Orphans ({len(g['orphans'])})**: " + "; ".join(f"{o['id']} ({o['label'][:40]})" for o in g["orphans"]))
    a(f"- Why: {g['orphan_cause']}")
    for key, label in [("events_without_place", "Events with no place"), ("events_without_thread", "Events with no thread"),
                       ("events_without_public_fact", "Events no public fact reveals"), ("events_without_story", "Events no story depicts"),
                       ("facts_cited_by_no_story", "Public facts cited by no story"), ("facts_without_event", "Public facts tied to no event"),
                       ("facts_without_place", "Public facts with no place"), ("facts_without_source_character", "Public facts with no source character"),
                       ("stories_without_fact", "Stories citing no fact"), ("stories_without_arc", "Stories in no arc"),
                       ("stories_without_place", "Stories with no place"), ("stories_without_event", "Stories depicting no event"),
                       ("characters_in_no_story", "Characters in no story"), ("characters_with_text_only_org", "Characters whose organisation is text only (no node)"),
                       ("story_place_tags_not_place_nodes", "Story place tags that are not Place nodes"), ("places_with_no_edges", "Places with no edges")]:
        v = g[key]
        a(f"- {label}: **{len(v)}**" + (f" — {', '.join(map(str, short(v, 18)))}" if v else ""))
    a(f"- Stream geography not in the graph: `{json.dumps(g['stream_geography_not_in_graph'], ensure_ascii=False)}`")
    a(f"- MSEL `observed_in` uses {g['msel_observed_in_label_variants']} different free-text labels; "
      f"{len(g['msel_observed_in_labels_with_no_stream'])} of them correspond to no data stream: "
      + ", ".join(f"{k} ({v})" for k, v in list(g["msel_observed_in_labels_with_no_stream"].items())[:60]))
    a("\n## 5. Thread completeness\n")
    a("| Thread | Events (day span) | Public facts | Stories (via events / via arcs) | Streams present | Answer key | Missing |\n|---|---|---|---|---|---|---|")
    for t in R["thread_completeness"]:
        span = f"D{t['day_span'][0]:+d} to D{t['day_span'][1]:+d}" if t["day_span"] else "—"
        a(f"| {t['thread']} {t['name']} | {t['msel_events']} ({span}) | {t['public_facts']} | {t['stories_via_events']} / {t['stories_via_arcs']} | "
          f"{', '.join(t['streams_with_evidence_present']) or '—'} | {'yes' if t['answer_key'] else '**no**'} | {'; '.join(t['missing']) or '—'} |")
    a("\n## 6. Recommended target schema\n")
    rs = R["recommended_schema"]
    a(rs["principle"] + "\n")
    a("**New node types**\n")
    for k, v in rs["node_types"].items():
        a(f"- `{k}`: {v}")
    a("\n**New edge types**\n")
    for k, v in rs["edge_types"].items():
        a(f"- `{k}`: {v}")
    a("\n## Notes\n")
    for n in R["notes"]:
        a(f"- {n}")
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
