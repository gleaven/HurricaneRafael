"""Audit every data stream in 05_other_sources/ against the scenario timeline. READ-ONLY on data.

Writes  07_validation/reports/stream_alignment_audit.json  and  .md
Usage:  python scripts/audit_streams.py

What it checks
  1. coverage      each stream's time span vs the scenario span and vs the MSEL events that name it
  2. evidence      for every MSEL event, whether the stream(s) in observed_in carry it (matrix)
  3. contradictions with the public record / news canon (computed from the data on every run)
  4. internal conflicts in the public record and the MSEL (curated list, re-verified where possible)
  5. source logs vs the tracks embedded in the map viewer

Scenario time: D0 = 2027-09-14 (UTC date); landfall 06:00Z.  t = days since 2027-09-14T00:00Z.
"""
import bisect, collections, csv, datetime as dt, glob, json, math, os, re, statistics as st, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SRC = os.path.join(ROOT, "05_other_sources")
OUT = os.path.join(ROOT, "07_validation", "reports")
D0 = dt.datetime(2027, 9, 14)
D0_EPOCH = 1821024000        # anchor the ADS-B and Zeek generators used for "D0 00:00Z" (it is really 2027-09-15T16:00Z)
TRUE_D0_EPOCH = 1820880000   # 2027-09-14T00:00:00Z
SCEN = (-60, 119)
LANDFALL = 0.25

FINDINGS, MATRIX, COVER = [], [], {}


def P(*a): return os.path.join(ROOT, *a)
def S(*a): return os.path.join(SRC, *a)
def L(p): return json.load(open(p, encoding="utf-8"))
def rows(p): return list(csv.DictReader(open(p, encoding="utf-8", errors="replace")))
def dl(d): return "D%+.2f" % d if abs(d - round(d)) > 0.004 else "D%+d" % round(d)
def cal(d): return (D0 + dt.timedelta(days=d)).strftime("%Y-%m-%d %H:%MZ")


def tday(s):
    """days since D0 from an ISO-ish string, epoch seconds, or Twitter created_at"""
    s = str(s).strip()
    if not s: return None
    if re.fullmatch(r"\d{9,11}(\.\d+)?", s): return (float(s) - D0_EPOCH) / 86400
    if re.match(r"[A-Z][a-z]{2} [A-Z][a-z]{2} \d\d ", s):
        return (dt.datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None) - D0).total_seconds() / 86400
    s = s.replace("Z", "").replace(" ", "T")
    if len(s) == 10: s += "T00:00:00"
    if len(s) == 16: s += ":00"
    try: return (dt.datetime.fromisoformat(s[:19]) - D0).total_seconds() / 86400
    except ValueError: return None


def add(stream, severity, kind, events, detail, fix):
    FINDINGS.append({"id": "AUD-%03d" % (len(FINDINGS) + 1), "stream": stream, "severity": severity, "kind": kind,
                     "events": sorted(set(events)), "detail": detail, "recommended_fix": fix})


# ----------------------------------------------------------------------------------- scenario
MSEL = L(P("00_scenario", "msel.json"))
for e in MSEL:
    hh = 0.0
    m = re.match(r"(\d\d):?(\d\d)Z?", e.get("time_utc") or "")
    if m: hh = (int(m.group(1)) + int(m.group(2)) / 60) / 24
    e["t"] = e["day"] + hh
    e["t_end"] = (e["day_end"] if e.get("day_end") is not None else e["day"]) + 1
EV = {e["event_id"]: e for e in MSEL}
FACTS = {f["id"]: f for f in L(P("02_public_record", "public_record.json"))["facts"]}

# observed_in token -> stream folder.  Order matters; first match wins.
OBS_MAP = [
    (r"^ship tracks$|(^|_)ais(_|$)|vessel_traffic", "ais"),
    (r"^aircraft tracks$|flight_logs$|helo_dispatch_log", "adsb"),
    (r"^drone video$|video_archive|uas_annotation", "drone_video"),
    (r"^satellite$|sar_imagery|optical_imagery", "satellite"),
    (r"^weather$", "weather"),
    (r"^environmental sensors$|tceq_buoy|air_monitoring|airnow", "env_sensors"),
    (r"^telemetry$|^historian$|^scada_historian$|scada_event_log|water_pressure_telemetry|pump_control_logs|fac_utl_01_historian|ercot_operations_log|^outage_map$|relay_config_files", "telemetry"),
    (r"^maintenance$|work_order|valve_maintenance", "maintenance"),
    (r"^supply$", "supply"),
    (r"^payments", "payments"),
    (r"^network logs$|siem_logs|netflow|network_flows|vpn_logs|vpn_session|endpoint_logs|email_gateway|file_audit_log|access_log", "network_logs"),
    (r"^911$|cad_incident|cad_volume|911_cad|911_call_metadata", "911"),
    (r"^public health$|ed_patient_log|ed_admissions_log|census_records", "public_health"),
    (r"^social media$|platform_post_archive", "social_media"),
    (r"ipaws_alert_archive|wea_transmission|everbridge", "eas"),
    (r"^census$", "census"),
    (r"^maps$|pda", "infrastructure"),
]
def stream_for(obs):
    o = obs.lower()
    if o in ("news", "public_record", "all"): return None
    for pat, s in OBS_MAP:
        if re.search(pat, o): return s
    return "no_stream"

ALIAS = {  # scenario id -> strings that identify it inside stream records
    "VSL-0012": ["Gulf Provider"], "VSL-0019": ["sealift", "Roosevelt Island"], "VSL-0031": ["Halcyon Drift"],
    "VSL-0457": ["Pelican Ridge"], "BRG-0044": ["Barge 44"], "VSL-0041": ["Kalvora"], "VSL-0042": ["Ostrel"],
    "VSL-0077": ["Corrin Bay"], "SUP-0102": ["Gulf Relief Logistics", "SUP-0102"], "SUP-0219": ["Delta Pumps", "SUP-0219"],
    "SUP-0388": ["Vantorra", "SUP-0388"], "SUP-0390": ["Quellmar", "SUP-0390"], "SUP-0455": ["Brightwake"],
    "EQP-1102": ["P-2", "PUMP2"], "EQP-1103": ["P-3", "PUMP3"], "EQP-2201": ["EQP-2201", "NAS backup generator"],
    "ACF-0201": ["RCH", "C-17", "SYN41"], "ACF-0301": ["CLIPPER", "SKW"], "DOM-SYN-01": ["aid-help-portal"],
}
ID_RE = re.compile(r"\b(VSL-\d{4}|BRG-\d{4}|EQP-\d{4}|SUP-\d{4}|BANK-SYN-\d+|PIID-SYN-\d+|ASN-SYN-\d+|ACF-\d{4}|"
                   r"GW-FAC-[A-Z]+-\d+|GW-SYS-[A-Z]+-\d+|GW-WS-IT-\d+|GW-ENG-[A-Z]+|DOM-SYN-\d+)\b")
NAME_RE = re.compile(r"\b(Auriga Meridian|Costana Bay|Narwhal Dream|Halcyon Drift|Kalvora Star|Ostrel Bay|Corrin Bay|"
                     r"Pelican Ridge|Gulf Provider|Barge 44|Brightwake|Vantorra|Quellmar|TXCoastalWatchdog|CoastTruthTX|"
                     r"GulfWatchPatriot|aid-help-portal|Landmark Pacific|McKinley Substation|SRMC|BCMC|NOAA42|CG-6033)\b")
def tokens(e):
    text = e["description"] + " " + " ".join(e.get("detection_artifacts") or [])
    out = set()
    for m in ID_RE.findall(text): out.update(ALIAS.get(m, [m]))
    out.update(NAME_RE.findall(text))
    return sorted(out)


# ----------------------------------------------------------------------------------- stream loaders
# Each loader returns {"span": (t0, t1), "records": [(t, text)] or None for continuous streams, extras...}
ST = {}

def load_all():
    # --- AIS
    ais = collections.defaultdict(list)
    for r in rows(S("ais", "ais_positions.csv")):
        ais[r["MMSI"]].append((tday(r["BaseDateTime"]), float(r["LAT"]), float(r["LON"]), float(r["SOG"] or 0), r["VesselName"], r["VesselType"]))
    for v in ais.values(): v.sort()
    ST["ais"] = {"span": (min(v[0][0] for v in ais.values()), max(v[-1][0] for v in ais.values())), "tracks": ais,
                 "names": {m: v[0][4] for m, v in ais.items()}}
    # --- ADS-B (per-aircraft files are the newest; _consolidated checked separately)
    adsb = {}
    for f in sorted(glob.glob(S("adsb", "*.csv"))):
        pts = sorted((tday(r["time_position"]), float(r["latitude"]), float(r["longitude"]), float(r["baro_altitude"] or 0), r["on_ground"] == "True") for r in rows(f))
        adsb[os.path.basename(f).split("_")[0]] = {"callsign": os.path.basename(f)[7:-4], "pts": pts}
    ST["adsb"] = {"span": (min(a["pts"][0][0] for a in adsb.values()), max(a["pts"][-1][0] for a in adsb.values())), "aircraft": adsb}
    # --- drone
    dr = {}
    for f in sorted(glob.glob(S("drone_video", "*.csv"))):
        rr = rows(f)
        dr[os.path.basename(f)[:-4]] = {"t0": tday(rr[0]["timestamp_utc"]), "t1": tday(rr[-1]["timestamp_utc"]), "op": rr[0]["operator_id"],
                                        "lat": (min(float(x["latitude"]) for x in rr), max(float(x["latitude"]) for x in rr)),
                                        "lon": (min(float(x["longitude"]) for x in rr), max(float(x["longitude"]) for x in rr)), "file": rr[0]["video_filename"]}
    ST["drone_video"] = {"span": (min(d["t0"] for d in dr.values()), max(d["t1"] for d in dr.values())), "flights": dr,
                         "records": [(d["t0"], k + " " + d["op"] + " " + d["file"]) for k, d in dr.items()]}
    # --- satellite
    sat = []
    for f in sorted(glob.glob(S("satellite", "RAFAEL-*.json"))):
        j = L(f); p = j["properties"]
        sat.append((tday(p["datetime"]), j["id"] + " " + " ".join(p.get("instruments") or []) + " " + p.get("title", "") + " " + p.get("description", "")))
    sat.sort()
    ST["satellite"] = {"span": (sat[0][0], sat[-1][0]), "records": sat}
    # --- weather
    wx = {}
    for f in sorted(glob.glob(S("weather", "*.csv"))):
        wx[os.path.basename(f).split("_")[0]] = [(tday(r["ObsDateTime"]), float(r["WindSpeed_mps"]), float(r["WindGust_mps"] or 0), float(r["SeaLevelPressure_mb"]),
                                                  float(r["DryBulbTemp_C"]), int(r["ObsDateTime"][11:13])) for r in rows(f)]
    ST["weather"] = {"span": (min(v[0][0] for v in wx.values()), max(v[-1][0] for v in wx.values())), "stations": wx}
    # --- env sensors
    wq, aq = {}, {}
    for f in sorted(glob.glob(S("env_sensors", "water_quality_WQ-*.csv"))):
        rr = rows(f); wq[rr[0]["SensorID"]] = {"name": rr[0]["SensorName"], "v": [(tday(r["ObsDateTime"]), float(r["TotalHydrocarbons_ppb"] or 0), float(r["StormSurge_m"] or 0)) for r in rr]}
    for f in sorted(glob.glob(S("env_sensors", "aqs_air_quality_AQS-*.csv"))):
        rr = rows(f); aq[rr[0]["SensorID"]] = {"name": rr[0]["SiteName"], "v": [(tday(r["ObsDateTime"]), float(r["Benzene_ppb"] or 0)) for r in rr]}
    ST["env_sensors"] = {"span": (min(x["v"][0][0] for x in wq.values()), max(x["v"][-1][0] for x in wq.values())), "wq": wq, "aq": aq}
    # --- telemetry
    tel = collections.defaultdict(list); attack = collections.Counter(); quality = collections.defaultdict(list)
    with open(S("telemetry", "_consolidated", "historian_data.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            t = tday(r["Timestamp"]); tel[r["Tagname"]].append((t, r["Value"]))
            if r.get("AttackSig", "N") != "N": attack[r["Tagname"]] += 1
            if r["Quality"] != "Good": quality[r["Quality"]].append(t)
    ST["telemetry"] = {"span": (min(v[0][0] for v in tel.values()), max(v[-1][0] for v in tel.values())), "tags": tel, "attack": attack, "quality": quality}
    # --- maintenance
    wo = [(tday(r["STATUSDATE"]), " ".join([r["WORKTYPE"], r["STATUS"], r["ASSETNUM"], r["DESCRIPTION"]])) for r in rows(S("maintenance", "work_orders.csv"))]
    wo.sort(); ST["maintenance"] = {"span": (wo[0][0], wo[-1][0]), "records": wo}
    # --- supply
    arr = rows(S("supply", "vessel_arrivals.csv")); man = rows(S("supply", "cargo_manifest.csv"))
    rec = [(tday(r["ata_datetime"] or r["eta_datetime"]), " ".join([r["vessel_name"], r["status"], r["terminal_id"], r["notes"]])) for r in arr]
    arr_t = {r["arrival_id"]: tday(r["ata_datetime"] or r["eta_datetime"]) for r in arr}
    rec += [(arr_t.get(r["arrival_id"], 0), " ".join([r["vessel_name"], r["cargo_description"], r["shipper_name"], r["consignee_name"], r["cargo_status"], r["notes"]])) for r in man]
    rec.sort(); ST["supply"] = {"span": (rec[0][0], rec[-1][0]), "records": rec, "arrivals": arr}
    # --- payments
    tx = rows(S("payments", "financial_transactions.csv")); cl = rows(S("payments", "insurance_claims.csv"))
    rec = [(tday(r["txn_date"]), " ".join(r.values())) for r in tx] + [(tday(r["report_date"]), " ".join(r.values())) for r in cl]
    rec.sort(); ST["payments"] = {"span": (rec[0][0], max(tday(r["txn_date"]) for r in tx)), "records": rec, "tx": tx, "claims": cl}
    # --- network logs
    siem = rows(S("network_logs", "siem_alerts.csv"))
    rec = [(tday(r["Timestamp"]), "SIEM " + " ".join([r["Severity"], r["RuleName"], r["HostName"], r["Username"], r["SourceIP"], r["DestIP"], r["Notes"]])) for r in siem]
    notes = []
    for line in open(S("network_logs", "_consolidated", "notice.log"), encoding="utf-8"):
        if line.startswith("#fields"): flds = line.rstrip("\n").split("\t")[1:]
        elif not line.startswith("#"):
            x = dict(zip(flds, line.rstrip("\n").split("\t"))); notes.append(x)
            rec.append((tday(x["ts"]), "ZEEK " + x["note"] + " " + x["msg"] + " " + x.get("src", "") + " " + x.get("dst", "")))
    conn_days = collections.Counter(); ext = collections.Counter(); zt = []
    for line in open(S("network_logs", "_consolidated", "conn.log"), encoding="utf-8"):
        if line.startswith("#"): continue
        p = line.split("\t"); conn_days[int(tday(p[0]) // 1)] += 1; zt.append(tday(p[0]))
        for ip in (p[2], p[4]):
            if not ip.startswith(("10.", "192.168.")): ext[ip] += 1
    rec.sort()
    ST["network_logs"] = {"span": (min(zt), max(tday(siem[-1]["Timestamp"]), max(zt))), "records": rec, "siem": siem, "zeek_notes": notes,
                          "conn_days": conn_days, "ext": ext, "siem_span": (tday(siem[0]["Timestamp"]), tday(siem[-1]["Timestamp"])), "zeek_span": (min(zt), max(zt))}
    # --- 911
    cad = rows(S("911", "911_cad_records.csv"))
    rec = [(tday(r["call_received_dttm"]), " ".join([r["nature_code"], r["nature_description"], r["address"], r["disposition_desc"], r["narrative"], r["phase_label"]])) for r in cad]
    rec.sort(); ST["911"] = {"span": (rec[0][0], rec[-1][0]), "records": rec, "cad": cad}
    # --- public health
    ed = rows(S("public_health", "_consolidated", "ed_visits.csv")); cap = rows(S("public_health", "hospital_capacity.csv"))
    ST["public_health"] = {"span": (min(tday(r["Visit_Date"]) for r in ed), max(tday(r["Visit_Date"]) for r in ed) + 1), "ed": ed, "cap": cap}
    # --- EAS
    eas = rows(S("public_health", "eas_broadcasts.csv"))
    rec = [(tday(r["IssuedAt_UTC"]), " ".join([r["AlertType"], r["GeographicArea"], r["Headline_EN"], r["NoteOnDelay"]])) for r in eas]
    ST["eas"] = {"span": (rec[0][0], rec[-1][0]), "records": rec, "eas": eas}
    # --- social
    tw = [json.loads(l) for l in open(S("social_media", "_consolidated", "tweets.jsonl"), encoding="utf-8")]
    for t in tw: t["t"] = tday(t["created_at"])
    tw.sort(key=lambda t: t["t"])
    ST["social_media"] = {"span": (tw[0]["t"], tw[-1]["t"]), "records": [(t["t"], "@" + t["user"]["screen_name"] + " " + t["text"]) for t in tw], "tw": tw}
    # --- infrastructure
    dm = rows(S("infrastructure", "damage_assessment.csv"))
    rec = sorted((tday(r["ASMT_DATE"]), " ".join([r["structure_type"], r["address"], r["DMG_LEVEL"], r["COMMENTS"]])) for r in dm)
    ST["infrastructure"] = {"span": (rec[0][0], rec[-1][0]), "records": rec}
    ST["census"] = {"span": SCEN, "records": None, "static": True}


CONTINUOUS = {"ais", "adsb", "weather", "env_sensors", "telemetry", "public_health", "census"}

# Manual verdicts from inspection of the data (event, stream) -> (status, note).  Everything computed below
# re-derives the numbers behind these; if a later fix changes the data, update or delete the verdict.
VERDICT = {
    ("EVT-1201", "ais"): ("missing", "no Auriga Meridian MMSI or track in the stream"),
    ("EVT-2001", "ais"): ("missing", "no Auriga Meridian track; no VTS log"),
    ("EVT-1103", "adsb"): ("missing", "no Texas ARNG UH-60 tracks"), ("EVT-1104", "adsb"): ("missing", "no Argus UAV tracks"),
    ("EVT-1105", "adsb"): ("missing", "no Argus UAV tracks"), ("EVT-1106", "adsb"): ("missing", "no Cessna 208B thermal-survey track"),
    ("EVT-1302", "adsb"): ("present", "Coast Guard helicopters CGNR6540/6541 fly rescue sorties D+1..D+2"),
    ("EVT-2102", "eas"): ("present-but-wrong-time", "hurricane warning logged 2027-09-11 12:00Z, about 30 h before canon (D-2 18:00Z)"),
    ("EVT-2103", "eas"): ("present-but-wrong-time", "evacuation orders logged 2027-09-12 06:00Z (Zone A) and 09-13 18:00Z (B, C); canon one order for A/B/C at D-1 12:00Z"),
    ("EVT-1403", "eas"): ("present-but-wrong-values", "row at D-1 18:00Z is an evacuation order for Zones B/C, not shelter-in-place guidance for C-E"),
    ("EVT-2104", "eas"): ("present", "shelter-in-place at 05:30Z (canon 05:45Z), Spanish WEA never sent"),
    ("EVT-2106", "eas"): ("missing", "no Districts 3-4 boil-water alert on D+12; the file ends D+14.5 with different zones"),
    ("EVT-1407", "eas"): ("missing", "no D+12 17:30 notice or its Spanish release time"),
    ("EVT-0304", "drone_video"): ("present", "TXDOT-BRIDGE-D01 over the Harbor Bridge on D+1"),
    ("EVT-0307", "drone_video"): ("missing", "no flight on D+2 and none over the Army depot"),
    ("EVT-0410", "drone_video"): ("missing", "no shoreline-cleanup flights D+30..D+44"),
    ("EVT-0314", "satellite"): ("present", "oil sheen described from the D+1.6 optical scene"),
    ("EVT-0301", "satellite"): ("present", "landfall SAR scene at 06:00Z"),
    ("EVT-0304", "infrastructure"): ("present", "bridge damage records"),
    ("GW-EVT-008", "telemetry"): ("present", "P-3 discharge pressure at 68 psi from D+9"),
    ("GW-EVT-010", "telemetry"): ("present-but-wrong-values", "GW.SUB4.REL.CFG_HASH.PV is corrupted into decimals from D+0.25"),
    ("EVT-0206", "supply"): ("missing", "no Army depot records"),
    ("EVT-1505", "social_media"): ("present-but-wrong-values", "no ERCOT-blame narrative (0 posts mention ERCOT)"),
    ("EVT-0101", "census"): ("present", "static ACS tract tables"), ("EVT-0601", "census"): ("present", "static ACS tract tables (aid and response data needed from other streams)"),
    ("EVT-0104", "ais"): ("present-but-wrong-values", "Halcyon Drift track starts D-43.3 mid-Gulf (Havana transit); MSEL has it loitering among tankers off Corpus Christi at D-45 under its true MMSI"),
    ("EVT-0207", "ais"): ("present-but-wrong-values", "no 14-vessel offshore queue: most inbound vessels end their tracks before D-3"),
    ("EVT-0210", "ais"): ("present", "Kalvora Star / Ostrel Bay stationary through the storm"),
    ("EVT-0401", "ais"): ("present-but-wrong-values", "harbor craft and survey vessels move throughout D0..D+30; no visible reopening step"),
    ("EVT-0410", "ais"): ("missing", "stream ends D+31; restriction runs to D+44"),
    ("EVT-0402", "ais"): ("missing", "stream ends 2027-10-15T00:00Z, two hours before the AIS gap/spoof begins; Pelican Ridge track ends D+1"),
    ("EVT-0404", "ais"): ("missing", "Barge 44 has no MMSI/track; stream ends D+31"),
    ("EVT-0413", "ais"): ("missing", "Corrin Bay track ends D+31; blast is D+44"),
    ("EVT-0414", "ais"): ("missing", "stream ends D+31; closure D+44..D+58"),
    ("EVT-0409", "ais"): ("missing", "no sealift vessel track; stream ends D+31"),
    ("EVT-0205", "adsb"): ("missing", "no NAS training-aircraft evacuation flights (registry NAV851/NAV097 have no track)"),
    ("EVT-0405", "adsb"): ("missing", "no C-17 / charter relief flights D+34..D+43 (registry RCH441/RCH801/CLIPPER01/SKW7730 have no track)"),
    ("EVT-0412", "adsb"): ("missing", "no navigation-integrity (NIC/NACp) columns and no flights in the window"),
    ("EVT-0102", "telemetry"): ("missing", "historian starts D-30; no vibration tag exists for P-2"),
    ("EVT-0103", "telemetry"): ("missing", "no NAS generator EQP-2201 telemetry in any stream"),
    ("EVT-0302", "telemetry"): ("present-but-wrong-values", "all O.N. Stevens pumps recover to normal pressure by D+0.46; canon has P-2 failed until D+38 and low pressure for weeks"),
    ("EVT-0313", "telemetry"): ("missing", "no tanker cargo-level/valve telemetry"),
    ("EVT-0406", "telemetry"): ("missing", "stream ends D+31; P-2 restoration D+38"),
    ("EVT-0407", "telemetry"): ("missing", "no EQP-2201 telemetry; stream ends D+31"),
    ("EVT-0602", "telemetry"): ("missing", "stream ends D+31"),
    ("GW-EVT-003", "telemetry"): ("present-but-wrong-time", "relay UV threshold 0.88->0.94 and RTU1 config hash change at D-3 00:00Z; canon 17:00Z-22:11Z"),
    ("GW-EVT-004", "telemetry"): ("present-but-wrong-values", "all substations drop at 06:00Z exactly and all return at D+0.42; canon SUB-01 trips 07:12Z and restoration runs to D+35"),
    ("GW-EVT-005", "telemetry"): ("present-but-wrong-time", "SUB2 breaker opens D+7 00:00Z in historian; canon 14:30Z (SIEM 14:23Z, Zeek D+8 02:14Z)"),
    ("GW-EVT-006", "telemetry"): ("present", "P-3 setpoint 85->68 psi at D+9 00:00Z (canon 02:00Z); never restored within the stream"),
    ("GW-EVT-007", "telemetry"): ("present-but-wrong-time", "SUB3 breaker opens D+10 00:00Z in historian; canon 19:45Z"),
    ("GW-EVT-013", "telemetry"): ("present-but-wrong-values", "no historian gap/anomaly on GW-FAC-WTR-03 tags"),
    ("GW-EVT-015", "telemetry"): ("missing", "stream ends D+31; final restoration D+35"),
    ("GW-EVT-016", "telemetry"): ("missing", "stream ends D+31; certification D+42"),
    ("EVT-2003", "telemetry"): ("missing", "no raw-water TPH tag at FAC-UTL-01"),
    ("EVT-0203", "env_sensors"): ("missing", "no river stage series; WQ-05 (Nueces River at Calallen) shows no rise from D-7"),
    ("EVT-0314", "env_sensors"): ("present", "hydrocarbon rise at WQ-01..04 from D+0.4, bay sondes by D+1.2"),
    ("EVT-2002", "env_sensors"): ("present-but-wrong-values", "sonde ids are WQ-01..06, MSEL cites TCEQ buoy CC-BAY-04; first anomaly D+0.4 not D+1 18:00Z"),
    ("EVT-2004", "env_sensors"): ("present", "benzene peaks D+0.6..D+1.1 (MSEL window D+2..D+5)"),
    ("EVT-2008", "env_sensors"): ("present", "hydrocarbons back near baseline by ~D+22"),
    ("EVT-0201", "weather"): ("missing", "weather stream starts D-30; outlook is D-21 but is a forecast product, not an observation"),
    ("EVT-0202", "weather"): ("present", "stations cover D-10"),
    ("EVT-0301", "weather"): ("present-but-wrong-values", "landfall visible, but values are implausible (see weather findings)"),
    ("EVT-0101", "public_health"): ("missing", "ED stream starts D-7; baseline 520 visits/day is ~50/day in the file"),
    ("EVT-0310", "public_health"): ("present-but-wrong-values", "GI visits do not rise +180% D+6..D+14"),
    ("EVT-0317", "public_health"): ("present-but-wrong-values", "respiratory visits not +60% at shoreline facilities"),
    ("EVT-0408", "public_health"): ("present-but-wrong-values", "no +40% residual in low-income tracts at D+45"),
    ("EVT-1602", "public_health"): ("present-but-wrong-values", "facility ids are FAC-CCMC/SHMC/DRMC...; SRMC/BCMC do not exist in the stream"),
    ("EVT-1603", "public_health"): ("present-but-wrong-values", "peak occupancy 96% of 383 beds; canon 140% of 500 (SRMC) and 118% of 280 (BCMC)"),
    ("EVT-1606", "public_health"): ("missing", "no District 3/4 gastroenteritis cluster from D+15"),
    ("EVT-1607", "public_health"): ("missing", "no cluster peak D+18..D+22 (canon 340 cases/day; file ~12 GI/day)"),
    ("EVT-1609", "public_health"): ("missing", "no cluster to decline"),
    ("EVT-0101", "911"): ("missing", "911 stream starts D-5; baseline 310/day is ~87/day in the file"),
    ("EVT-0303", "911"): ("present-but-wrong-values", "peak 418 records/day; canon 2,900/day (PUB-026) or 2,109 (PUB-131)"),
    ("EVT-0304", "911"): ("present", "bridge-closure narratives on D+1"),
    ("EVT-0601", "911"): ("missing", "stream ends D+31 and has no census-tract field for the equity analysis"),
    ("EVT-1301", "911"): ("present-but-wrong-values", "spike begins but scaled ~7x below canon"),
    ("EVT-1302", "911"): ("present-but-wrong-values", "D+2 is the peak day (418) but canon is 2,109"),
    ("EVT-1303", "911"): ("present-but-wrong-values", "7 unfounded calls on D+7 (canon 9 in a 4-hour window near utility sites)"),
    ("EVT-1304", "911"): ("present-but-wrong-values", "5 unfounded calls D+8..D+10 (canon 14, total 23)"),
    ("EVT-1305", "911"): ("present-but-wrong-values", "no boil-water call surge on D+12 (131 calls, below D+11)"),
    ("EVT-1307", "911"): ("present-but-wrong-values", "D+28 has 87 records and an unexplained cluster of 19 false industrial alarms"),
    ("EVT-1308", "911"): ("missing", "stream ends D+31"),
    ("EVT-1707", "911"): ("present-but-wrong-values", "unfounded trapped-resident calls D+7..D+10 total 12, not 11 in NW Corpus Christi; addresses not checked"),
    ("EVT-0305", "satellite"): ("present-but-wrong-values", "D+1 scene is optical; flood extent appears in the D+0.5 SAR text with no 112 km2 figure"),
    ("EVT-0208", "satellite"): ("missing", "no D-2 radar reference pass (nearest PRE-03 at D-7)"),
    ("EVT-0104", "satellite"): ("missing", "catalog starts D-30"),
    ("EVT-0403", "satellite"): ("missing", "catalog ends D+30.58; pass needed D+31 09:30Z"),
    ("EVT-0411", "satellite"): ("missing", "catalog ends D+30.58; pass needed D+31 04:20Z"),
    ("EVT-0505", "satellite"): ("missing", "catalog ends D+30.58; debris passes needed to D+70"),
    ("EVT-0318", "social_media"): ("missing", "no posts about lights/drones over NAS Corpus Christi (0 tweets containing 'drone')"),
    ("EVT-0309", "social_media"): ("present-but-wrong-values", "2 coordinated accounts and 6 'seizing homes' posts starting D+6.8; canon 40 accounts / 18,000 posts from D+2"),
    ("EVT-0413", "social_media"): ("missing", "no posts about the D+44 jetty blast; the stream has a different 'ship channel blast' at D+1 02:30 local"),
    ("EVT-0507", "social_media"): ("present-but-wrong-values", "no 'contractors are stealing aid' wave D+75..D+85"),
    ("EVT-0102", "maintenance"): ("present-but-wrong-time", "P-2 vibration work order at D-26 and CLOSED; canon D-55 and deferred (stream starts D-29)"),
    ("EVT-0103", "maintenance"): ("missing", "no NAS/EQP-2201 records (stream is CBPWA only)"),
    ("EVT-0205", "maintenance"): ("missing", "no NAS records"), ("EVT-0206", "maintenance"): ("missing", "no Army depot records"),
    ("EVT-0302", "maintenance"): ("present-but-wrong-values", "storm work orders exist but P-2 is repaired by D+17.8 (canon D+38) and assets use GW-PP1-* ids not EQP-110x"),
    ("EVT-0307", "maintenance"): ("missing", "no depot hangar records"), ("EVT-0313", "maintenance"): ("missing", "no tanker cargo-system inspection"),
    ("EVT-0316", "maintenance"): ("missing", "no tanker cargo-system records"), ("EVT-0318", "maintenance"): ("missing", "no perimeter-sensor repairs"),
    ("EVT-0406", "maintenance"): ("missing", "stream ends D+31.7"), ("EVT-0407", "maintenance"): ("missing", "stream ends D+31.7"),
    ("EVT-0414", "maintenance"): ("missing", "no EOD / mine-clearance reports"), ("EVT-0409", "maintenance"): ("missing", "stream ends D+31.7"),
    ("EVT-0506", "maintenance"): ("missing", "stream ends D+31.7"), ("EVT-0602", "maintenance"): ("missing", "stream ends D+31.7"),
    ("EVT-0204", "supply"): ("present-but-wrong-values", "Gulf Provider manifest exists but no SUP-0102 / 40-container booking reference"),
    ("EVT-0207", "supply"): ("present-but-wrong-values", "3 vessels 'held at anchorage' (canon 14)"),
    ("EVT-0210", "supply"): ("present-but-wrong-time", "arrivals log has both tankers arriving D-2.4/D-2.2; AIS has them at berth from D-14; MSEL approval is D-3"),
    ("EVT-0308", "supply"): ("missing", "no pump-parts order from Delta Pumps / SUP-0219"),
    ("EVT-0312", "supply"): ("missing", "no fuel contract / SUP-0390 receipt"),
    ("EVT-0401", "supply"): ("present-but-wrong-time", "Gulf Provider berths D+6.6 in the arrivals log; canon D+33 after the D+30 partial reopening"),
    ("EVT-0404", "supply"): ("missing", "no 380 m3 fuel receipt; stream ends D+27"),
    ("EVT-0405", "supply"): ("missing", "stream ends D+27"), ("EVT-0406", "supply"): ("missing", "no pump-parts receipt at D+36"),
    ("EVT-0409", "supply"): ("present-but-wrong-time", "'MV Roosevelt Island' sealift call logged D+28.5..D+30.8; canon outload sails D+59..D+64"),
    ("EVT-0414", "supply"): ("missing", "stream ends D+27"), ("EVT-0506", "supply"): ("missing", "stream ends D+27"), ("EVT-0602", "supply"): ("missing", "stream ends D+27"),
    ("EVT-0105", "payments"): ("missing", "no vendor registry; no SUP ids or BANK-SYN accounts anywhere in the stream"),
    ("EVT-0103", "payments"): ("missing", "no fuel-supplier payments before the storm"),
    ("EVT-0204", "payments"): ("missing", "no SUP-0102 booking payment"), ("EVT-0308", "payments"): ("missing", "no SUP-0219 order"),
    ("EVT-0311", "payments"): ("present-but-wrong-values", "3 payments to Vantorra Restoration LLC but no PIID-SYN-0071 / $14.2M award record"),
    ("EVT-0312", "payments"): ("present-but-wrong-values", "4 payments to Quellmar Fuel Partners but no PIID-SYN-0075 / $2.1M award record"),
    ("EVT-0315", "payments"): ("missing", "no Unified Command / response spending"), ("EVT-0404", "payments"): ("missing", "no fuel invoices from D+33"),
    ("EVT-0410", "payments"): ("missing", "no cleanup payments"), ("EVT-0414", "payments"): ("missing", "transactions end D+60 with no export-halt signal"),
    ("EVT-0501", "payments"): ("missing", "transactions end D+60; no FEMA IA claims"), ("EVT-0502", "payments"): ("missing", "transactions end D+60"),
    ("EVT-0503", "payments"): ("missing", "transactions end D+60; no BANK-SYN-71/72/73"), ("EVT-0504", "payments"): ("missing", "no prepaid-card purchases"),
    ("EVT-0505", "payments"): ("missing", "no debris tonnage billing"), ("EVT-0506", "payments"): ("missing", "transactions end D+60"),
    ("EVT-0508", "payments"): ("missing", "no spill damage claims"), ("EVT-0601", "payments"): ("missing", "no aid-by-tract data"),
    ("EVT-2206", "payments"): ("missing", "no FEMA IA application records (94 LPH claims exist only as insurance claims reported D+0..D+30)"),
    ("EVT-0106", "network_logs"): ("missing", "logs are CBPWA-only; no aid-portal or NAS logistics traffic, no ASN-SYN-64512"),
    ("EVT-0107", "network_logs"): ("missing", "no Brightwake phishing"), ("EVT-0209", "network_logs"): ("missing", "no tanker cargo-network sessions"),
    ("EVT-0313", "network_logs"): ("missing", "no vendor-session commands to tankers at D0 04:00Z"), ("EVT-0306", "network_logs"): ("missing", "no aid-portal phishing D+1..D+3"),
    ("EVT-0316", "network_logs"): ("missing", "no responder findings"), ("EVT-0502", "network_logs"): ("missing", "logs end D+29 (SIEM) / D+17 (Zeek); credential stuffing D+62..D+70"),
    ("GW-EVT-001", "network_logs"): ("present-but-wrong-values", "no implant on GW-WS-IT-04 at D-14; SIEM shows an RDP brute force on GW-WS-IT-14 at D-6.9 instead"),
    ("GW-EVT-101", "network_logs"): ("missing", "no beacon alert at D-14 03:17Z; first external-IP contact not tied to GW-WS-IT-04"),
    ("GW-EVT-002", "network_logs"): ("present-but-wrong-values", "lateral movement alert at D-3.0 from GW-WS-IT-14 as svc_backup; canon D-7..D-4 via the field-engineer VPN account"),
    ("GW-EVT-102", "network_logs"): ("missing", "no after-hours historian session at D-7 02:44Z"),
    ("GW-EVT-103", "network_logs"): ("present-but-wrong-time", "'Unauthorized Modbus Write' alerts at D-3 00:34Z/01:15Z; canon relay config write 22:11Z"),
    ("GW-EVT-104", "network_logs"): ("present-but-wrong-values", "SIEM has 25-61 alerts/day through the storm; canon 4,812..18,340/day (74,120 in the window)"),
    ("GW-EVT-105", "network_logs"): ("missing", "no alarm-suppression alert at D+9 04:00Z"),
    ("GW-EVT-106", "network_logs"): ("present-but-wrong-time", "ML anomaly alert at D+10.1; canon D+18 14:33Z"),
    ("GW-EVT-011", "network_logs"): ("missing", "Zeek ends D+17; no 14-session VPN review evidence"),
    ("GW-EVT-108", "network_logs"): ("missing", "SIEM ends D+28.9; clean baseline is D+35"),
}

def classify(e, s):
    """-> (status, note)"""
    if s == "no_stream": return ("no-stream", "named log is not a data stream in 05_other_sources")
    if (e["event_id"], s) in VERDICT: return VERDICT[(e["event_id"], s)]
    info = ST.get(s)
    if not info: return ("no-stream", "")
    t0, t1 = info["span"]
    if not info.get("static") and (e["t_end"] < t0 - 0.5 or e["t"] > t1 + 0.5):
        return ("missing", "outside stream span %s..%s" % (dl(t0), dl(t1)))
    if s in CONTINUOUS or not info.get("records"):
        return ("in-span-unverified", "continuous stream covers the date; values not checked for this event")
    tok = tokens(e)
    if not tok: return ("in-span-unverified", "no entity id or name to search for")
    pat = re.compile("|".join(re.escape(k) for k in tok), re.I)
    hits = [t for t, text in info["records"] if pat.search(text)]
    if not hits: return ("missing", "stream covers the date but no record mentions " + ", ".join(tok[:4]))
    near = [t for t in hits if e["t"] - 1.0 <= t <= e["t_end"] + 1.5]
    if near: return ("present", "%d matching record(s) near the event" % len(near))
    nearest = min(hits, key=lambda t: abs(t - e["t"]))
    return ("present-but-wrong-time", "matching records exist but nearest is %s (event %s)" % (dl(nearest), dl(e["t"])))


# ----------------------------------------------------------------------------------- 1+2 coverage and matrix
def coverage_and_matrix():
    per_stream_out = collections.defaultdict(list)
    for e in sorted(MSEL, key=lambda e: (e["t"], e["event_id"])):
        seen = set()
        for o in (e.get("observed_in_legacy") or e.get("observed_in") or []):
            if isinstance(o, dict): o = o["stream"]
            s = stream_for(o)
            if s is None or s in seen: continue
            seen.add(s)
            status, note = classify(e, s)
            MATRIX.append({"event_id": e["event_id"], "day": e["day"], "day_end": e.get("day_end"), "time_utc": e.get("time_utc"),
                           "threads": e["threads"], "observed_in": o, "stream": s, "status": status, "note": note})
            if s in ST and not ST[s].get("static"):
                t0, t1 = ST[s]["span"]
                if e["t_end"] < t0 - 0.5 or e["t"] > t1 + 0.5: per_stream_out[s].append(e)
    for s, info in ST.items():
        t0, t1 = info["span"]
        COVER[s] = {"start": round(t0, 2), "end": round(t1, 2), "start_utc": cal(t0), "end_utc": cal(t1),
                    "events_outside": [x["event_id"] for x in per_stream_out.get(s, [])]}
        out = per_stream_out.get(s, [])
        if out:
            before = [x for x in out if x["t_end"] < t0]; after = [x for x in out if x["t"] > t1]
            add(s, "blocker" if len(after) >= 3 else "major", "coverage", [x["event_id"] for x in out],
                "Stream spans %s..%s (%s .. %s). %d MSEL event(s) that name it fall outside: %d before (%s), %d after (%s)." % (
                    dl(t0), dl(t1), cal(t0), cal(t1), len(out), len(before), ", ".join("%s %s" % (x["event_id"], dl(x["day"])) for x in before) or "-",
                    len(after), ", ".join("%s %s" % (x["event_id"], dl(x["day"])) for x in after) or "-"),
                "Extend the stream to cover D%+d..D%+d (at minimum through the last event that names it) and generate the records those events require." % (
                    min([SCEN[0]] + [x["day"] for x in before]) if before else round(t0), max([x["day"] for x in after] + [round(t1)])))
    ns = collections.Counter(); ns_ev = collections.defaultdict(set)
    for r in MATRIX:
        if r["status"] == "no-stream":
            for t in r["threads"]: ns[t] += 1
            ns_ev[r["observed_in"]].add(r["event_id"])
    n_logs = len(ns_ev)
    add("(none)", "major", "no-stream", sorted({e for v in ns_ev.values() for e in v}),
        "%d distinct sources named in observed_in have no data file at all (bespoke logs from the T11-T22 thread designs such as ccfd_sar_incident_log, "
        "ipaws_alert_archive_*, port_radar_buoy_logs, platform_post_archive_*, srmc_census_records_*, fema_ia_application_database, coastal_alert_cib_scan_*). "
        "Event-source pairs with no stream, by thread: %s." % (n_logs, ", ".join("%s %d" % kv for kv in sorted(ns.items(), key=lambda kv: -kv[1]))),
        "Decide per thread: either map each named log onto an existing stream (and make that stream carry the artifact), or generate a small purpose-built file per log "
        "under 05_other_sources/<thread>/. Until then T11-T22 detection artifacts exist only as prose in the MSEL.")


# ----------------------------------------------------------------------------------- 3 per-stream checks
def nm(a, b): return math.hypot((a[0] - b[0]) * 60, (a[1] - b[1]) * 60 * math.cos(math.radians(a[0])))

def chk_ais():
    A = ST["ais"]; tr = A["tracks"]; t0, t1 = A["span"]
    V = L(P("06_data_streams", "vessels.json"))["vessels"]; reg = {str(v["mmsi"]): v["vessel_name"] for v in V}
    not_reg = sorted(A["names"][m] for m in tr if m not in reg); not_ais = sorted(reg[m] for m in reg if m not in tr)
    if not_reg or not_ais:
        add("ais", "major", "entity-mismatch", [], "AIS has %d MMSIs; vessels.json has %d. In AIS but not in the registry: %s. In the registry with no AIS track: %s. "
            "Scenario entities VSL-0019 (sealift ship), BRG-0044 (Barge 44) have no track; MSEL T12 vessels Auriga Meridian, Costana Bay (MMSI 345821766) and Narwhal Dream have none either." % (
                len(tr), len(reg), ", ".join(not_reg) or "-", ", ".join(not_ais) or "-"),
            "Make vessels.json the single roster; give every scenario vessel one MMSI and regenerate AIS from it.")
    storm = {}
    for m, pts in tr.items():
        n = sum(1 for t, la, lo, sog, *_ in pts if -0.25 <= t <= 0.75 and sog > 1.0)
        if n: storm[A["names"][m]] = n
    if storm:
        add("ais", "blocker", "contradiction", ["EVT-0207", "EVT-0301", "EVT-1203"],
            "%d vessels report speed over 1 kt between Port Condition Zulu (D-1 18:00Z) and 12 h after landfall, i.e. under way through a Category 3 eyewall: %s. "
            "Rendering rules also call for AIS coverage gaps D0..D+2; the stream has none." % (len(storm), ", ".join("%s (%d fixes)" % kv for kv in sorted(storm.items(), key=lambda kv: -kv[1]))),
            "Moor or shelter every vessel from Zulu until the post-storm survey; add receiver outages D0..D+2.")
    clos = {}
    for m, pts in tr.items():
        if pts[0][5] in ("70", "80"):
            n = sum(1 for t, la, lo, sog, *_ in pts if 0.75 < t < 30 and sog > 1.0)
            if n: clos[A["names"][m]] = n
    if clos:
        add("ais", "major", "contradiction", ["EVT-0401", "EVT-0410"], "Cargo/tanker movement while the ship channel is closed (D0..D+30 per PUB-058/EVT-0401): %s." % ", ".join("%s (%d fixes)" % kv for kv in clos.items()),
            "After the canon decision on reopening date, restrict deep-draft movement to the open windows.")
    hd = next((m for m, n in A["names"].items() if "Halcyon Drift" in n), None)
    if hd:
        pts = tr[hd]; gaps = [(a[0], b[0] - a[0]) for a, b in zip(pts, pts[1:]) if b[0] - a[0] > 0.4]
        cc = (27.80, -96.95); early = [nm((la, lo), cc) for t, la, lo, *_ in pts if t < -30]
        add("ais", "blocker", "missing-evidence", ["EVT-0104", "EVT-0402", "EVT-0403", "EVT-0411"],
            "MV Halcyon Drift (MMSI %s) track runs %s..%s. At D-45 (EVT-0104: loitering among crude-export tankers) there is no data; the first fixes are %.0f-%.0f nm from the Corpus Christi anchorage. "
            "Gaps over 10 h: %s. The stream stops at %s, about two hours before the D+31 02:00Z AIS silence and the Pelican Ridge identity spoof (EVT-0402, PUB-062); "
            "FV Pelican Ridge's own track ends at D+1 so the 'same vessel 600 nm away' signal cannot be shown. Scenario key MMSI-SYN-0131 / MMSI-SYN-0457 do not match the MMSIs used (%s / 338724891)." % (
                hd, dl(pts[0][0]), dl(pts[-1][0]), min(early) if early else -1, max(early) if early else -1,
                ", ".join("%s for %.1f d" % (dl(a), g) for a, g in gaps) or "none", cal(t1), hd),
            "Regenerate: Halcyon Drift present off the port from D-45, a 14 h gap from D+31 02:00Z, a spoofed Pelican Ridge identity at the anchorage during the gap, and the real Pelican Ridge ~600 nm away the same night.")
    add("ais", "blocker", "missing-evidence", ["EVT-0404", "EVT-0413", "EVT-0414", "EVT-0409"],
        "Nothing after %s: Barge 44's fuel run up the channel (D+32), the tug Corrin Bay's AIS stopping at the jetties (D+44 06:10Z), the 14-day closure (D+44..D+58) and the sealift sailing (D+59..D+64) are all absent." % cal(t1),
        "Extend AIS to D+119 with these four signals.")
    q = 0
    for m, pts in tr.items():
        at = [p for p in pts if -2.2 <= p[0] <= -1.0]
        if at and sum(p[3] for p in at) / len(at) < 1.0 and at[0][2] > -97.05: q += 1
    add("ais", "major", "contradiction", ["EVT-0207"], "Offshore queue at Port Condition Yankee (D-2): %d vessels are slow/stopped east of the jetties in the data; canon is 14 held inbound vessels including MV Gulf Provider (PUB-107)." % q,
        "Generate the 14-vessel anchorage queue from D-2, dispersing to sea at Zulu and returning D+3 (PUB-109).")

def chk_epoch():
    off = (D0_EPOCH - TRUE_D0_EPOCH) / 3600
    a = ST["adsb"]["aircraft"]; first = min(x["pts"][0][0] for x in a.values())
    schemas = [f for f in ("06_adsb_schema.json", "10_network_logs_schema.json") if str(D0_EPOCH) in open(P("06_data_streams", "schemas", f), encoding="utf-8").read()]
    add("adsb + network_logs", "blocker", "wrong-epoch", [],
        "ADS-B (time_position/last_contact) and the Zeek logs (ts) were generated with epoch %d as 'D0 00:00Z'. That value is 2027-09-15T16:00:00Z; the correct value is %d. "
        "Decoded properly, every ADS-B fix and every Zeek record is %.0f hours later than intended and than the ISO-timestamped streams (AIS, SIEM, historian, 911...): the Coast Guard's first post-storm sortie lands on D+2 instead of D+0.4, "
        "the SUB-02 breaker DNP3 notice lands on 2027-09-22T18:14Z. Zeek's per-day folders were split by the true date, so folder names and intended days disagree as well. Schema files carrying the wrong anchor: %s. "
        "All other ADS-B and Zeek findings in this report use the intended time (anchor subtracted) so that this defect is not counted twice." % (D0_EPOCH, TRUE_D0_EPOCH, off, ", ".join(schemas) or "none"),
        "Regenerate with 1820880000 (or shift every epoch by -144000 s and re-split the Zeek day folders); fix the two schema files; put the anchor in one shared constant.")

def chk_adsb():
    A = ST["adsb"]["aircraft"]
    reg = L(P("06_data_streams", "aircraft_registry.json"))["aircraft"]
    regids = {a.get("icao24") or a.get("icao_hex"): a.get("callsign") for a in reg}
    missing = sorted("%s (%s)" % (c, i) for i, c in regids.items() if i not in A)
    add("adsb", "major", "entity-mismatch", ["EVT-0205", "EVT-0405"], "ADS-B has %d aircraft; aircraft_registry.json lists %d. No track for: %s." % (len(A), len(regids), ", ".join(missing)),
        "Generate tracks for every registry aircraft or trim the registry.")
    long_, storm = [], []
    for i, a in A.items():
        cur = None; so = []
        for t, la, lo, al, g in a["pts"]:
            if not g:
                if cur is None: cur = [t, t]
                cur[1] = t
            elif cur: so.append(cur); cur = None
        if cur: so.append(cur)
        for s0, s1 in so:
            if (s1 - s0) * 24 > 12: long_.append("%s %s airborne %.0f h from %s" % (a["callsign"], i, (s1 - s0) * 24, dl(s0)))
            if s1 > -1.46 and s0 < 0.6: storm.append("%s %s..%s" % (a["callsign"], dl(s0), dl(s1)))
        a["sorties"] = so
    if long_:
        add("adsb", "major", "implausible", [], "Sorties longer than any of these aircraft can fly without landing: %s." % "; ".join(long_),
            "Cap sortie length by type (MH-60 ~4 h, HC-144 ~10 h, news helicopter ~2.5 h, ISR per platform) and insert landings.")
    if storm:
        add("adsb", "blocker", "contradiction", ["EVT-0301", "EVT-1102"], "Aircraft airborne inside the FAA TFR (from D-2 13:00Z, PUB-180) or within ~8 h of landfall: %s. "
            "The one flight canon does place in this window, NOAA42's 08:30Z reconnaissance pass (EVT-1102, PUB-110), is absent." % "; ".join(storm),
            "Ground everything except the Hurricane Hunter during the TFR and eyewall passage; first Coast Guard hoists begin 06:22 local on D+1 (PUB-170).")
    add("adsb", "blocker", "missing-evidence", ["EVT-0205", "EVT-0405", "EVT-0412", "EVT-1103"],
        "Canon signals with no data: NAS training aircraft evacuating to Fort Worth at D-4; 26 C-17 and 14 charter relief flights D+34..D+43 (the latest track ends %s); "
        "GPS-interference integrity drop D+38..D+43 (file has no NIC/NACp columns); Texas ARNG UH-60 flights D+1." % dl(ST["adsb"]["span"][1]),
        "Add the flights and a navigation-integrity column; extend to D+119.")
    u = A.get("7c1234")
    if u:
        d30 = ST["drone_video"]["flights"].get("UNIDENTIFIED-D30")
        add("adsb", "major", "contradiction", ["EVT-0318", "EVT-1907"], "An 'UNKNOWN' hostile UAV transmits ADS-B for 4 h at %s (ICAO 7c1234). Canon overflights are D+1..D+10 at night over NAS Corpus Christi and the depot, "
            "pre-storm sorties D-10..D-3, and no sightings after D+11 (PUB-051). A covert small drone would not carry ADS-B. The matching drone-telemetry file is dated %s, about a day later." % (
                dl(u["pts"][0][0]), dl(d30["t0"]) if d30 else "n/a"),
            "Remove from ADS-B; represent hostile drones only through radar/RF/visual-report streams on the canon nights.")
    con = collections.Counter(r["icao24"] for r in rows(S("adsb", "_consolidated", "adsb_positions.csv")))
    diff = {i: (len(a["pts"]), con.get(i, 0)) for i, a in A.items() if len(a["pts"]) != con.get(i, 0)}
    if diff:
        add("adsb", "major", "stale-copy", [], "adsb/_consolidated/adsb_positions.csv is an older generation than the per-aircraft files (rows per-file vs consolidated: %s)." % ", ".join("%s %d/%d" % (i, a, b) for i, (a, b) in diff.items()),
            "Rebuild every _consolidated file from the per-source files in one step, or delete the consolidated copies.")

def chk_drone():
    D = ST["drone_video"]["flights"]
    add("drone_video", "major", "missing-evidence", ["EVT-0307", "EVT-0318", "EVT-0505", "EVT-1901", "EVT-1903", "EVT-1904", "EVT-1905", "EVT-1104", "EVT-1105", "EVT-1108"],
        "%d flights, %s..%s. Missing: depot hangar survey at D+2 (no flight on D+2 at all); weekly base inspections; debris surveys D+10..D+70 (one flight after D+5); "
        "Argus/FEMA Phase 2 utility-yard passes D+8 and Phase 4 at D+45; any trace of the hostile sorties (pre-storm D-10..D-3, post-storm nights D+1..D+10)." % (len(D), dl(ST["drone_video"]["span"][0]), dl(ST["drone_video"]["span"][1])),
        "Add the missing flights; extend to D+70.")
    u = D.get("UNIDENTIFIED-D30")
    if u:
        add("drone_video", "blocker", "contradiction", ["EVT-0318", "EVT-1907"], "UNIDENTIFIED-D30 is on-board telemetry (gimbal angles, video filename) from an unidentified drone loitering over the Inner Harbor at %s. "
            "Nobody could hold a hostile drone's own flight log, and the date conflicts with PUB-051 (no sightings after D+11) and with PUB-182 (counter-UAS program announced D+32 citing pre-storm activity)." % dl(u["t0"]),
            "Delete; if a D+30 sighting is wanted, add it to the MSEL and public record first.")
    c = D.get("CCFD-SAR-D00")
    if c:
        add("drone_video", "minor", "implausible", ["EVT-0301"], "CCFD-SAR-D00 flies at %s (about 04:00 local, three hours after landfall, in darkness and tropical-storm-force wind). KIII-NEWS-* uses a real station's call letters; the scenario's TV outlet is Harborline 6." % dl(c["t0"]),
            "Move to daylight D+1; rename KIII flights.")

def chk_satellite():
    R = ST["satellite"]["records"]
    def near(t, tol=0.4, pat=None): return [x for x in R if abs(x[0] - t) <= tol and (not pat or re.search(pat, x[1], re.I))]
    miss = []
    if not near(-2, 0.6, "SAR"): miss.append("D-2 radar reference (EVT-0208)")
    if not near(1, 0.6, "SAR"): miss.append("D+1 radar flood extent, 112 km2 (EVT-0305, PUB-028)")
    if not near(31.18, 0.2): miss.append("D+31 04:20Z hull off the entrance channel (EVT-0411)")
    if not near(31.4, 0.2): miss.append("D+31 09:30Z two hulls side by side (EVT-0403)")
    if not [x for x in R if x[0] > 40]: miss.append("debris passes to D+70 (EVT-0505)")
    if not [x for x in R if x[0] < -40]: miss.append("D-45 Halcyon Drift loiter (EVT-0104)")
    add("satellite", "blocker", "missing-evidence", ["EVT-0104", "EVT-0208", "EVT-0305", "EVT-0403", "EVT-0411", "EVT-0505"],
        "%d scenes, %s..%s; rendering rules call for 1 optical pass a day and radar every 6 days. Tasked passes missing: %s." % (len(R), dl(R[0][0]), dl(R[-1][0]), "; ".join(miss)),
        "Add the tasked passes; fill the daily/6-day cadence across D-60..D+119.")
    bad = []
    for t, text in R:
        if re.search(r"spill contained|No oil sheen visible", text) and t < 20: bad.append("%s says the spill is contained/no sheen (canon: slick D+1..D+20, contained D+20)" % dl(t))
        if re.search(r"reopening assessment", text) and t < 30: bad.append("%s is titled 'Channel reopening assessment' (canon partial reopening D+30)" % dl(t))
        if re.search(r"27\.75N 97\.13W", text): bad.append("%s puts the eye at 27.75N 97.13W; canon landfall is Mustang Island near Port Aransas" % dl(t))
    opt_night = [dl(t) for t, text in R if "MSI" in text and "SAR" not in text.split(" ")[1] and abs((t % 1) - 0.0) < 0.01]
    if opt_night: bad.append("optical scenes timestamped 00:00Z (19:00 local, near sunset): " + ", ".join(opt_night))
    if bad: add("satellite", "major", "contradiction", ["EVT-0314", "EVT-0401", "EVT-2008"], "Scene descriptions that contradict canon: " + "; ".join(bad) + ".", "Rewrite descriptions after the canon decisions; use mid-morning local times for optical passes.")

def chk_weather():
    W = ST["weather"]["stations"]; out = []
    for k, v in W.items():
        post = [x for x in v if x[0] > 8]
        byh = collections.defaultdict(list)
        for x in post: byh[x[5]].append(x[4])
        mh = {h: st.mean(t) for h, t in byh.items()}
        amp = max(mh.values()) - min(mh.values()); hot = max(mh, key=mh.get); night = st.mean([mh[h] for h in (5, 6, 7, 8) if h in mh])
        octm = st.mean(x[4] for x in v if x[0] > 17) if any(x[0] > 17 for x in v) else float("nan")
        mxw = max(v, key=lambda x: x[1]); mng = max(v, key=lambda x: x[2]); mnp = min(v, key=lambda x: x[3])
        run = best = 1
        storm = [x for x in v if -0.5 < x[0] < 0.6]
        for a, b in zip(storm, storm[1:]):
            run = run + 1 if abs(a[3] - b[3]) < 0.5 and a[3] < 1000 else 1; best = max(best, run)
        out.append("%s: warmest hour %02d:00Z (%02d:00 local), midnight-to-3am local mean %.1f C, diurnal range %.1f C, October mean %.1f C; peak sustained wind %.1f m/s (%.0f kt) at %s, peak gust %.1f m/s (%.0f kt); "
                   "minimum pressure %.1f mb at %s; longest run of near-identical pressure during the storm %d h; no outage" % (
                       k, hot, (hot - 5) % 24, night, amp, octm, mxw[1], mxw[1] * 1.944, dl(mxw[0]), mng[2], mng[2] * 1.944, mnp[3], dl(mnp[0]), best))
    add("weather", "blocker", "implausible", ["EVT-0301"],
        "Temperatures are physically wrong: the daily cycle is 3-4 C with the warmest hours around 00:00Z-03:00Z (evening) and 33 C at midnight local; mid-October means are ~31 C (Corpus Christi normals: highs ~29, lows ~19); "
        "the offshore buoy warms 3 C after the storm. Landfall winds are wrong: KCRP, 30 km inland, logs sustained wind near the storm's maximum and gusts of ~160 kt (above Category 5), pressure moves in flat steps, "
        "KNGP's peak wind comes four hours before landfall, the buoy flat-lines at 30.9 m/s for 12 h, and no station drops out although posts in the social stream say 'KCRP down' and rendering rules call for outage. Per station: " + " | ".join(out) + ".",
        "Regenerate from the storm track with a parametric wind/pressure model, a real diurnal cycle and seasonal cooling, station dropouts through the eyewall, and extend to D+119.")

def chk_env():
    E = ST["env_sensors"]; lines = []
    for k, x in E["wq"].items():
        v = x["v"]; base = st.median(a[1] for a in v if a[0] < -2)
        first = next((a for a in v if a[1] > 10 * base + 5), None); mx = max(v, key=lambda a: a[1]); ms = max(v, key=lambda a: a[2])
        lines.append("%s %s: first rise %s, peak %.0f ppb at %s; max surge %.2f m at %s" % (k, x["name"][:38], dl(first[0]) if first else "none", mx[1], dl(mx[0]), ms[2], dl(ms[0])))
    add("env_sensors", "major", "contradiction", ["EVT-0301", "EVT-0313", "EVT-0314", "EVT-0203"],
        "Sondes: " + "; ".join(lines) + ". Canon: valves open 04:00Z..05:30Z on D0 beside the berth (EVT-0313) so WQ-01 should react within the hour, not at ~09:20Z; surge is 3.4 m at 06:00Z (EVT-0301) but only WQ-06 shows any surge (2.94 m at ~10:20Z) "
        "and the Inner Harbor sondes show none; the tide gauge is supposed to be offline D0..D+5 (rendering rules, GAUGE-14); the Nueces River rise from D-7 (EVT-0203) is absent. Rendering rules promise 2 river gauges and 20 air sensors; the stream has 0 and 5.",
        "Tie hydrocarbon onset to 04:00Z D0, put surge on every tidal sonde peaking 06:00Z, take the tide gauge offline D0..D+5, add river-stage gauges.")
    pre = []
    for k, x in E["aq"].items():
        v = x["v"]; base = st.median(a[1] for a in v if a[0] < -6); n = sum(1 for a in v if -5 <= a[0] < 0 and a[1] > 3 * base)
        if n: pre.append("%s %d readings" % (k, n))
    if pre: add("env_sensors", "minor", "implausible", ["EVT-2004"], "Benzene more than 3x baseline before any oil was released (D-5..D0): %s." % ", ".join(pre), "Keep pre-landfall air readings at baseline.")
    add("env_sensors", "major", "entity-mismatch", ["EVT-2002", "EVT-2006", "EVT-2009", "EVT-2003"],
        "T20 names the TCEQ buoy network (CC-BAY-04, Nueces Bay buoys) with first anomaly D+1 18:00Z and a 60-day assessment at D+60; the stream uses sonde ids WQ-01..06, shows the anomaly from D+0.4 and ends %s." % dl(E["span"][1]),
        "Pick one sensor naming scheme and extend to at least D+60.")

def chk_telemetry():
    T = ST["telemetry"]; tags = T["tags"]
    def changes(tag):
        v = tags.get(tag, []); return [(b[0], a[1], b[1]) for a, b in zip(v, v[1:]) if a[1] != b[1]]
    if T["attack"]:
        add("telemetry", "blocker", "answer-leak", ["GW-EVT-003", "GW-EVT-005", "GW-EVT-006", "GW-EVT-007"],
            "The historian has an AttackSig column set to 'Y' on every row of %d tags from D-5 onward (%d rows): %s. It labels the answer and, being constant per tag, carries no timing information." % (
                len(T["attack"]), sum(T["attack"].values()), ", ".join(sorted(T["attack"])[:8]) + " ..."),
            "Drop the column from the released files (keep ground truth in the answer key).")
    b2 = [c for c in changes("GW.SUB2.BKR1.STATUS.STS") if c[2] == "OPEN" and c[0] > 1]; b3 = [c for c in changes("GW.SUB3.BKR1.STATUS.STS") if c[2] == "OPEN" and c[0] > 1]
    siem = [tday(r["Timestamp"]) for r in ST["network_logs"]["siem"] if "Breaker" in r["RuleName"]]
    zeek = [tday(x["ts"]) for x in ST["network_logs"]["zeek_notes"] if "DNP3" in x["note"]]
    wo = [t for t, text in ST["maintenance"]["records"] if "breaker unexpected open" in text]
    add("telemetry", "blocker", "cross-stream-time", ["GW-EVT-005", "GW-EVT-007"],
        "The two malicious breaker-open commands are at four different times in four sources. Canon: SUB-02 D+7 14:30Z, SUB-03 D+10 19:45Z. Historian: %s. SIEM alert: %s. Zeek DNP3 notice: %s. Work orders: %s." % (
            ", ".join(cal(c[0]) for c in b2 + b3) or "none", ", ".join(cal(t) for t in siem) or "none", ", ".join(cal(t) for t in zeek) or "none", ", ".join(cal(t) for t in wo) or "none"),
        "Generate all four from the MSEL timestamp (command, then breaker state, then alert, then work order minutes to hours later).")
    uv = changes("GW.SUB1.REL.UV_THR.SP"); uvt = [c for c in uv if abs(float(c[2]) - float(c[1])) > 0.02]
    rtu = {t: changes("GW.RTU%d.CFG_HASH.PV" % t) for t in (1, 2, 3, 4)}
    add("telemetry", "major", "wrong-time", ["GW-EVT-003", "GW-EVT-103", "GW-EVT-009", "GW-EVT-010"],
        "Relay threshold 0.88->0.94 pu is written at %s on SUB1 and SUB2 (canon D-3 17:00Z; config file write 22:11Z). RTU config-hash changes: %s. "
        "The thresholds are never restored inside the stream although work orders restore relay settings at D+15.6 and canon resets them by D+35." % (
            ", ".join(cal(c[0]) for c in uvt) or "never", "; ".join("RTU%d %s" % (k, ", ".join(cal(c[0]) for c in v) or "none") for k, v in rtu.items())),
        "Align to GW-EVT-003/103 times; add the restoration steps.")
    def low(tag):
        v = [(t, float(x)) for t, x in tags[tag] if re.fullmatch(r"-?\d+(\.\d+)?", x)]
        mx = max(x for _, x in v); lows = [t for t, x in v if x < 0.5 * mx]
        return (min(lows), max(lows)) if lows else None
    p1 = low("GW.UTL1.PUMP1.PRESS.PV"); p2 = low("GW.UTL1.PUMP2.PRESS.PV"); bus = low("GW.SUB1.BUS.VOLT.PV")
    add("telemetry", "blocker", "contradiction", ["EVT-0302", "EVT-0310", "EVT-0406", "GW-EVT-004", "GW-EVT-015", "GW-EVT-008"],
        "The storm outage lasts about five hours in the historian: substation bus voltage is down %s..%s and O.N. Stevens pump pressure is low %s..%s, then every asset returns to normal. "
        "Canon: both plant feeds fail at 09:00Z, P-2 fails and stays out until D+38, citywide low pressure drives a boil-water notice D+4..D+39, SUB-01 trips at 07:12Z, restoration is staged through D+35, "
        "and rendering rules say telemetry is lost D0..D+3. P-3's setpoint drop at D+9 (85->68 psi) is present, but with the plant otherwise healthy the District 3/4 low-pressure signal has no storm damage to hide in." % (
            dl(bus[0]) if bus else "?", dl(bus[1]) if bus else "?", dl(p1[0]) if p1 else "?", dl(p1[1]) if p1 else "?"),
        "Rebuild plant and grid telemetry from the MSEL: staged restoration, P-2 out to D+38, data gap D0..D+3, and extend to D+119.")
    bad = [c for c in changes("GW.SUB4.REL.CFG_HASH.PV") if not c[2].startswith("0x")]
    if bad: add("telemetry", "major", "corrupt-values", ["GW-EVT-010"], "GW.SUB4.REL.CFG_HASH.PV turns from a hash into random decimals at %s (%d changed values), so the SUB-04 relay-config finding at D+16 cannot be made." % (dl(bad[0][0]), len(bad)), "Regenerate as a hash that changes once at the write.")
    flat = []
    for tag in ("GW.SCADA.ALARM_SUPR_CNT.PV", "GW.HST.AFTER_HRS_ACCESS.PV", "GW.JMP.ACTIVE_SESSIONS.PV"):
        v = [float(x) for _, x in tags[tag]]; flat.append("%s %.1f-%.1f" % (tag, min(v), max(v)))
    add("telemetry", "major", "missing-evidence", ["GW-EVT-102", "GW-EVT-105", "GW-EVT-011", "GW-EVT-013"],
        "Tags meant to carry the intrusion are flat noise with no event: %s. No after-hours historian session at D-7 02:44Z, no alarm-suppression peak at D+9 04:00Z, no 14 jump-host sessions, no historian gap on the Colorado River booster." % "; ".join(flat),
        "Drive these tags from the GW-EVT timeline.")
    add("telemetry", "major", "missing-evidence", ["EVT-0102", "EVT-0103", "EVT-0313", "EVT-0407", "EVT-0602", "EVT-2003"],
        "Assets the base scenario depends on have no telemetry at all: pump vibration (EQP-1102 trend from D-55), NAS backup generator EQP-2201 (healthy D-50, fails D+40), tanker cargo levels/valves (D0 04:00Z), raw-water TPH at the plant intake (D+2). "
        "Asset ids are GW-FAC-UTL-01 pumps 1-4; the scenario's EQP-1101..1104 never appear.",
        "Add these assets and map EQP ids to tags in scada_tags.json.")

def chk_maintenance():
    R = ST["maintenance"]["records"]
    def find(p): return [(t, x) for t, x in R if re.search(p, x, re.I)]
    p2 = find(r"P-2 impeller replacement"); press = find(r"Full system pressure restoration"); bw = find(r"boil water"); sp = find(r"setpoint restore")
    add("maintenance", "blocker", "contradiction", ["EVT-0302", "EVT-0406", "EVT-0310", "GW-EVT-016"],
        "Work orders close out the water crisis weeks early: P-2 rebuilt %s (canon parts arrive D+36, restored D+38); 'all districts online' %s; boil-water zones restored %s (canon lifts D+39 and D+42); P-3 setpoint restored %s while the historian still shows 68 psi at D+31." % (
            dl(p2[0][0]) if p2 else "?", dl(press[0][0]) if press else "?", dl(bw[0][0]) if bw else "?", dl(sp[0][0]) if sp else "?"),
        "Regenerate from the MSEL dates; the 25-day parts delay (EVT-0308/0406) should be visible as open work orders.")
    add("maintenance", "major", "entity-mismatch", ["EVT-0102", "EVT-0103", "EVT-0206", "EVT-0307", "EVT-0318", "EVT-0407", "EVT-0414", "EVT-0506"],
        "%d work orders, all one utility (asset ids GW-PP1-PUMP1.., GW-SUB01-BKR-MAIN; the historian uses GW-FAC-UTL-01/GW-FAC-SUB-01 and the scenario EQP-1101..). About 2 a day against the 15 a week in the rendering rules is fine, but nothing covers "
        "NAS Corpus Christi (generator EQP-2201, perimeter sensors), the Army depot, tanker cargo-system inspections or EOD/mine-clearance reports." % len(R),
        "Use one asset-id scheme across historian, work orders and scada_tags.json; add NAS, depot, tanker and EOD records.")

def chk_supply():
    A = ST["supply"]["arrivals"]
    post = [r for r in A if 0.5 < (tday(r["ata_datetime"]) or -99) < 30 and re.search(r"MT |LNG|Crude", r["vessel_name"])]
    gp = [r for r in A if "Gulf Provider" in r["vessel_name"] and (tday(r["ata_datetime"]) or -99) > 0]
    sl = [r for r in A if "SEALIFT" in r["status"].upper()]
    add("supply", "blocker", "contradiction", ["EVT-0401", "EVT-0409", "EVT-0414"],
        "The arrivals log runs a different port timeline: %d tanker/LNG calls berth between D+7 and D+18 while canon keeps the channel closed until a partial reopening at D+30 (PUB-058, EVT-0401); "
        "MV Gulf Provider berths %s (canon D+33, 'about a month late', PUB-059); the sealift call is %s (canon sails D+59..D+64); the log ends %s so the D+44..D+58 closure is absent." % (
            len(post), dl(tday(gp[0]["ata_datetime"])) if gp else "never", dl(tday(sl[0]["ata_datetime"])) if sl else "absent", dl(max(tday(r["ata_datetime"]) or -99 for r in A))),
        "Canon decision on reopening first (see canon findings), then regenerate arrivals through D+119.")
    ais = set(ST["ais"]["tracks"]); am = {r["mmsi"] for r in A}
    add("supply", "major", "entity-mismatch", ["EVT-0204", "EVT-0308", "EVT-0312", "EVT-0404", "EVT-0406"],
        "%d of %d MMSIs in the arrivals log have an AIS track; %d AIS vessels have no port call. No scenario supplier ids (SUP-0102, SUP-0219, SUP-0388, SUP-0390) appear, and there is no inventory/receipt data: "
        "pump parts ordered D+2 and received D+36, the 380 m3 fuel receipt at D+32, daily stock for ~200 SKUs." % (len(am & ais), len(am), len(ais - am)),
        "Generate arrivals from the same vessel roster as AIS; add a receipts/inventory file keyed by SUP ids.")

def chk_payments():
    tx = ST["payments"]["tx"]; cl = ST["payments"]["claims"]; text = " ".join(" ".join(r.values()) for r in tx)
    span = (min(tday(r["txn_date"]) for r in tx), max(tday(r["txn_date"]) for r in tx))
    add("payments", "blocker", "missing-evidence", ["EVT-0105", "EVT-0311", "EVT-0312", "EVT-0501", "EVT-0502", "EVT-0503", "EVT-0504", "EVT-0505", "EVT-0508", "EVT-2206"],
        "%d transactions, %s..%s. Mentions: SUP ids %d, BANK-SYN %d, PIID-SYN %d, Brannoch %d, prepaid %d. Missing: vendor registry showing SUP-0388/0390 sharing an address and BANK-SYN-71 at D-40; "
        "the $14.2M (D+10) and $2.1M (D+12) awards; FEMA IA registrations from D+60 (48,000 claims); 410 hijacked accounts routing $3.9M D+64..D+80; prepaid-card clusters D+66..D+80; debris billing at 2.3x tonnage (D+70); 4,200 spill claims; "
        "the 94 fraudulent FEMA IA applications of D+60..D+62." % (len(tx), dl(span[0]), dl(span[1]), len(re.findall(r"SUP-\d{4}", text)), text.count("BANK-SYN"), text.count("PIID-SYN"), text.count("Brannoch"), len(re.findall("prepaid", text, re.I))),
        "Add vendor-registry, contract-award and FEMA IA files; extend transactions to D+119 with the canon account ids.")
    ld = collections.Counter(r["loss_date"] for r in cl); rep = [tday(r["report_date"]) for r in cl]
    lph = [r for r in cl if "LPH" in r["claimant_id"]]; early = sum(1 for r in cl if r["inspection_date"] and r["inspection_date"] < r["report_date"])
    add("payments", "major", "contradiction", ["EVT-2201", "EVT-2202", "EVT-2204"],
        "Insurance claims: all %d have loss_date %s (correct: that is landfall day, not a defect); report dates run %s..%s; %d are inspected before they are reported. "
        "%d claims belong to the LPH ring; canon is 230 inflated policies (EVT-2201) with claim runners activated at D+3 (EVT-2202), and %d LPH claims are reported before D+3. 400 claims stands in for 142,000 (PUB-211) with no sampling note." % (
            len(cl), ", ".join(ld), dl(min(rep)), dl(max(rep)), early, len(lph), sum(1 for r in lph if tday(r["report_date"]) < 3)),
        "Fix inspection<report rows; start LPH filings at D+3; document the sampling ratio.")

def chk_network():
    N = ST["network_logs"]; siem = N["siem"]
    hosts = {r["HostName"] for r in siem}; reg = {(h.get("hostname") or h.get("host_id") or "").split(".")[0] for h in L(P("06_data_streams", "gw_host_registry.json"))["hosts"]}
    add("network_logs", "blocker", "entity-mismatch", ["GW-EVT-001", "GW-EVT-002", "GW-EVT-101", "GW-EVT-102", "GW-EVT-103"],
        "SIEM host names share %d of %d with gw_host_registry.json (SIEM: %s; registry uses GW-WS-IT-04, GW-SYS-JMP-01, GW-HIST-01, GW-RTU-PWR-01...). The registry puts IT hosts on 192.168.100.0/24; SIEM and Zeek put them on 10.72.1.0/24. "
        "The intrusion story in the SIEM is a different one: RDP brute force on GW-WS-IT-14 as svc_backup at D-6.9, lateral movement D-3.0. Canon: implant on GW-WS-IT-04 at D-14 03:17Z, historian sessions from D-7 02:44Z through the jump host, relay file write D-3 22:11Z." % (
            len(hosts & reg), len(hosts), ", ".join(sorted(hosts)[:10]) + " ..."),
        "Regenerate SIEM and Zeek from gw_host_registry.json and the GW-EVT timeline.")
    daily = collections.Counter(int(tday(r["Timestamp"]) // 1) for r in siem)
    add("network_logs", "major", "contradiction", ["GW-EVT-104"], "Storm-window alert flood is absent: SIEM daily counts D-2..D+4 are %s; canon is 4,812 / 7,341 / 18,340 / 16,207 / 14,884 / 12,201 / 6,633 (GW-EVT-104). Zeek conn volume is flat (~750/day) through landfall and the multi-day outage." % (
        ", ".join(str(daily.get(d, 0)) for d in range(-2, 5))),
        "Scale volumes (or document a sampling ratio) and add the outage/reconnect pattern.")
    add("network_logs", "blocker", "coverage", ["GW-EVT-010", "GW-EVT-011", "GW-EVT-106", "GW-EVT-012", "GW-EVT-013", "GW-EVT-014", "GW-EVT-107", "GW-EVT-108", "EVT-0106", "EVT-0107", "EVT-0209", "EVT-0306", "EVT-0313", "EVT-0502"],
        "Zeek conn/dns/notice run %s..%s and SIEM %s..%s. Everything from the D+16 relay-file finding to the D+35 clean baseline is outside Zeek, and the base scenario's network events are not represented in any log: "
        "KESTREL scans from ASN-SYN-64512 (D-35), Brightwake phishing (D-33), vendor sessions on tanker networks (D-20, D0 04:00Z), aid-portal phishing (D+1..D+3), credential stuffing (D+62..D+70). External addresses seen: %s." % (
            dl(N["zeek_span"][0]), dl(N["zeek_span"][1]), dl(N["siem_span"][0]), dl(N["siem_span"][1]), ", ".join("%s x%d" % kv for kv in N["ext"].most_common(4))),
        "Extend to D+119; add portal, vendor and tanker-network logs.")

def chk_911():
    cad = ST["911"]["cad"]; c = collections.Counter(int(tday(r["call_received_dttm"]) // 1) for r in cad)
    base = st.mean(c[d] for d in (-5, -4, -3)); pk = max(c, key=c.get)
    add("911", "blocker", "contradiction", ["EVT-0101", "EVT-0303", "EVT-1301", "EVT-1302", "EVT-1307"],
        "Daily records: baseline %.0f (canon 310), peak %d on D%+d (canon 2,900 a day in PUB-026/EVT-0303, or 2,109 on D+2 in PUB-131/EVT-1302), D+28 %d (canon 380). The file is a sample, but at two different rates: %.0f%% of canon at baseline and %.0f%% at peak, "
        "so the 'nearly ten times normal' ratio comes out as %.1fx. No sampling note exists." % (base, c[pk], pk, c.get(28, 0), 100 * base / 310, 100 * c[pk] / 2900, c[pk] / base),
        "Either generate full volume or sample at one stated rate; settle 2,900 vs 2,109 first.")
    fc = collections.Counter(int(tday(r["call_received_dttm"]) // 1) for r in cad if re.search(r"FALSE|UNFOUND", (r["disposition_desc"] + r["narrative"] + r["phase_label"]).upper()))
    add("911", "major", "contradiction", ["EVT-1303", "EVT-1304", "EVT-1707", "EVT-1305"],
        "False/unfounded calls by day D+7..D+10: %s (canon 23: 9 in four hours on D+7 then 14 over D+8..D+10; plus 11 false trapped-resident calls, PUB-174). An unexplained cluster of false industrial alarms sits at D+28..D+30: %s. "
        "The boil-water call surge on D+12 (EVT-1305, PUB-132) is not visible: D+11 %d, D+12 %d, D+13 %d." % (
            ", ".join("%d" % fc.get(d, 0) for d in range(7, 11)), ", ".join("%d" % fc.get(d, 0) for d in range(28, 31)), c.get(11, 0), c.get(12, 0), c.get(13, 0)),
        "Regenerate the false-call windows and the D+12 surge; remove or explain the D+28 cluster.")
    add("911", "major", "missing-evidence", ["EVT-0601", "EVT-0303"], "No census-tract or income field, so '61%% from low-income surge-zone tracts' and the D+90 equity review (median response 2.1x) cannot be computed. "
        "Timestamps carry no zone (2027-09-09 00:03:04): local or UTC is undocumented. Stream covers %s..%s only." % (dl(ST["911"]["span"][0]), dl(ST["911"]["span"][1])),
        "Add tract GEOID (join to census/), state the time zone, extend to D-60..D+119.")

def chk_health():
    H = ST["public_health"]; ed = H["ed"]; cap = H["cap"]
    c = collections.Counter(int(tday(r["Visit_Date"])) for r in ed); gi = collections.Counter(int(tday(r["Visit_Date"])) for r in ed if r["CC_Syndrome_Category"] == "GI")
    resp = collections.Counter(int(tday(r["Visit_Date"])) for r in ed if r["CC_Syndrome_Category"] == "RESP")
    b = st.mean(c[d] for d in range(-7, -2)); gb = st.mean(gi[d] for d in range(-7, -1)); rb = st.mean(resp[d] for d in range(-7, -1))
    g614 = st.mean(gi[d] for d in range(6, 15)); g1822 = st.mean(gi[d] for d in range(18, 23)); r321 = st.mean(resp[d] for d in range(3, 22))
    add("public_health", "blocker", "contradiction", ["EVT-0101", "EVT-0310", "EVT-0317", "EVT-1606", "EVT-1607", "EVT-1609", "EVT-0408"],
        "ED visits: baseline %.0f a day (canon 520; ~10%% sample, undocumented). GI visits: baseline %.1f, D+6..D+14 mean %.1f (canon +180%% -> %.0f), D+18..D+22 mean %.1f (canon outbreak peak 340 cases a day, 94%% from Districts 3-4, PUB-162/163). "
        "Respiratory: baseline %.1f, D+3..D+21 mean %.1f (canon +60%% near oiled shorelines). Neither the norovirus wave nor the Cryptosporidium/Giardia cluster that drives T9/T14/T16 exists in the data." % (b, gb, g614, gb * 2.8, g1822, rb, r321),
        "Regenerate with the two GI waves, shoreline respiratory rise, ZIP/district concentration and the D+45 low-income residual.")
    fac = sorted({r["C_Facility_ID"] for r in ed}); pk = max(cap, key=lambda r: int(r["Inpatient_Occupied"]) / int(r["Licensed_Beds"]))
    add("public_health", "blocker", "entity-mismatch", ["EVT-1601", "EVT-1602", "EVT-1603", "EVT-1604", "EVT-1605"],
        "Facilities in the stream: %s. Canon hospitals are Shoreline Regional Medical Center (SRMC, 500 beds) and Bay City Medical Center (BCMC, 280 beds). Highest occupancy in hospital_capacity.csv is %s at %d of %d beds (%.0f%%) on %s; canon is SRMC 700/500 (140%%) and BCMC 331/280 (118%%) on D+2 (PUB-161, PUB-164). "
        "No generator/diesel status for the D+5 fuel crisis or the D+8 power restoration." % (", ".join(fac), pk["C_Facility_ID"], int(pk["Inpatient_Occupied"]), int(pk["Licensed_Beds"]), 100 * int(pk["Inpatient_Occupied"]) / int(pk["Licensed_Beds"]), pk["Report_Date"]),
        "Rename/resize facilities to the canon hospitals (facility_registry.json too) and regenerate capacity.")

def chk_eas():
    E = ST["eas"]["eas"]
    def t(r): return tday(r["IssuedAt_UTC"])
    hw = next((r for r in E if r["AlertType"] == "HurricaneWarning"), None); ev = next((r for r in E if r["AlertType"] == "MandatoryEvacuationOrder"), None)
    bw = [r for r in E if "BoilWater" in r["AlertType"]]
    add("eas", "blocker", "contradiction", ["EVT-2102", "EVT-2103", "EVT-2104", "EVT-2106", "EVT-2108", "EVT-1407", "EVT-1410", "EVT-0310"],
        "The alert log follows a different timeline from the public record. Hurricane warning %s (canon D-2 17:00Z/18:00Z, PUB-200, EVT-2102). First mandatory evacuation %s (canon D-1 12:00Z, PUB-201, EVT-2103). "
        "Boil-water alerts: %s; canon is citywide D+4..D+39 (PUB-039, PUB-063) and Districts 3-4 from D+12 to D+42 (PUB-143/204, PUB-206). The file uses 'Water Zone 1/2/3' and 'GridWater'; canon uses Districts 3-4 and CBPWA. "
        "Log ends %s: no D+12 notice (the 12-hour Spanish delay that T14/T21 are built on), no lifts." % (
            dl(t(hw)) if hw else "absent", dl(t(ev)) if ev else "absent", "; ".join("%s %s %s" % (r["AlertType"], dl(t(r)), r["GeographicArea"][:28]) for r in bw), dl(max(t(r) for r in E))),
        "Rebuild from PUB-200..206, PUB-143/144 and EVT-21xx/14xx; one row per IPAWS alert with EN/ES release times.")

def chk_social():
    tw = ST["social_media"]["tw"]
    def hit(p, lo=-99, hi=999): return [x for x in tw if lo <= x["t"] <= hi and re.search(p, x["text"], re.I)]
    hd = hit(r"Halcyon Drift")
    add("social_media", "blocker", "restricted-term", ["EVT-0104", "EVT-0402"],
        "%d public posts name 'MV Halcyon Drift' (first %s by @%s; also @%s). restricted_terms.json lists it as never public. Posts also discuss a 'Panama ship' AIS gap from D+12, weeks before the D+31 event." % (
            len(hd), dl(hd[0]["t"]) if hd else "-", hd[0]["user"]["screen_name"] if hd else "-", ", ".join(sorted({x["user"]["screen_name"] for x in hd})[:5])),
        "Remove; run the restricted-terms leak guard over every public-facing stream, not only news.")
    ex = hit(r"explosion|blast", 0.9, 2); bw = hit(r"BOIL WATER NOTICE", 0, 3); jb = hit(r"explosion|blast|tug|jett", 43.9, 47)
    seiz = hit(r"seizing"); dr = hit(r"drone|lights over")
    add("social_media", "blocker", "contradiction", ["EVT-0413", "EVT-0310", "EVT-0309", "EVT-0318", "EVT-1208"],
        "The feed tells a different story from the news corpus: a 'ship channel blast' at 02:30 local on D+1 (%d posts D+1..D+2; canon has no explosion until the tug blast at D+44, and %d posts mention that one); a citywide boil-water notice at D+1.5 (canon D+4); "
        "the spill vessel 'unnamed' for months (canon names MT Kalvora Star and MT Ostrel Bay on D+1, PUB-029); port 'fully reopened' D+30 with a convoy (canon partial); utility called 'GridWater' (canon CBPWA); 'seizing homes' rumor first at %s (canon D+2, PUB-033); "
        "%d posts about lights/drones over the air station (canon D+2, PUB-032)." % (len(ex), len(jb), dl(seiz[0]["t"]) if seiz else "never", len(dr)),
        "Regenerate the feed from the public record after the canon decisions.")
    users = collections.Counter(x["user"]["screen_name"] for x in tw)
    P_ = L(P("06_data_streams", "personas.json"))["personas"]; ph = {p["handle"].lstrip("@") for p in P_}
    real = [u for u in users if re.search(r"KIII|CallerTimes|NationalHurricaneCenter|FEMARegion6|PortCorpusChristi|USCGSectorCC", u)]
    add("social_media", "major", "entity-mismatch", ["EVT-0309", "EVT-1501", "EVT-1502", "EVT-1504", "EVT-1505", "EVT-0507"],
        "%d accounts post; personas.json lists %d and only %d overlap. Not in the registry: %s. Registry accounts that never post: %s. The coordinated network is 2 accounts (@CoastTruthTX %d posts, @TruthAboutRafael %d); canon is 40 accounts and 18,000 posts (EVT-0309) / 47 pre-positioned accounts (EVT-1501), "
        "with @GulfWatchPatriot (PUB-034) and @TXCoastalWatchdog absent. Handles of real organizations and outlets are used: %s; fictional outlets Harborline 6 / KNCB / Coastline have no posts." % (
            len(users), len(ph), len(ph & set(users)), ", ".join(sorted(set(users) - ph)[:10]) + " ...", ", ".join(sorted(ph - set(users))[:10]) + " ...", users.get("CoastTruthTX", 0), users.get("TruthAboutRafael", 0), ", ".join(real)),
        "One persona roster; generate the bot network at a stated sampling ratio; replace real outlet handles with the scenario outlets.")

def chk_infra():
    R = ST["infrastructure"]["records"]
    add("infrastructure", "minor", "coverage", ["EVT-0601", "EVT-0604", "EVT-1107"], "Damage assessments run %s..%s (%d records) and stop before household assessments are said to finish (PUB-104: slowed, IA not approved until D+57). No tract id for the D+90 equity review." % (dl(R[0][0]), dl(R[-1][0]), len(R)),
        "Extend assessments to ~D+55 with the slow tail; add tract GEOID.")

def chk_consolidated():
    out = []
    def n(p): return sum(1 for _ in open(p, encoding="utf-8", errors="replace")) - 1
    pairs = [("drone_video", "drone_telemetry.csv", "*.csv"), ("env_sensors", "water_quality_sondes.csv", "water_quality_WQ-*.csv"), ("env_sensors", "aqs_air_quality.csv", "aqs_air_quality_AQS-*.csv"),
             ("public_health", "ed_visits.csv", "ed_visits_FAC-*.csv"), ("telemetry", "historian_data.csv", "historian_*.csv"), ("weather", "asos_observations.csv", "*.csv")]
    for folder, con, pat in pairs:
        a = n(S(folder, "_consolidated", con)); b = sum(n(f) for f in glob.glob(S(folder, pat)))
        if a != b: out.append("%s/%s %d rows vs %d in per-source files" % (folder, con, a, b))
    tw = sum(1 for _ in open(S("social_media", "_consolidated", "tweets.jsonl"), encoding="utf-8")); tb = sum(sum(1 for _ in open(f, encoding="utf-8")) for f in glob.glob(S("social_media", "*_tweets.jsonl")))
    if tw != tb: out.append("social_media tweets.jsonl %d vs %d" % (tw, tb))
    days = sorted(d for d in os.listdir(S("network_logs")) if d.startswith("2027"))
    if out: add("(all)", "minor", "stale-copy", [], "Consolidated copies that differ from per-source files: " + "; ".join(out) + ".", "Rebuild or delete consolidated copies.")
    add("(all)", "minor", "documentation", [], "05_other_sources/README.md still says 'to build next' and promises a truth_event_id on every record plus H3 cells; no stream has either. Zeek per-day folders cover %s..%s. scenarios/gridwater/05_streams/ is empty and its msel.json is an empty list (events live in 00_scenario/msel.json)." % (days[0], days[-1]),
        "Rewrite the README per stream: span, sampling ratio, time zone, id scheme, known gaps.")


# ----------------------------------------------------------------------------------- 4 canon conflicts
def chk_canon():
    def f(i): return FACTS.get(i, {})
    def has(i, pat): return bool(re.search(pat, f(i).get("statement", ""), re.I))
    stories = L(P("08_release", "news_stories_public.json"))["stories"]
    def news(pat, d0, d1):
        out = []
        for s in stories:
            t = tday(s["published"][:19])
            if d0 <= t <= d1 and re.search(pat, s["headline"] + " " + s["summary"], re.I): out.append("%s %s '%s'" % (dl(round(t, 1)), s["outlet"].split()[-1] if False else s["outlet"], s["headline"][:70]))
        return out
    add("canon", "blocker", "public-record-conflict", ["EVT-1407", "EVT-2106", "EVT-1305"],
        "Districts 3-4 boil-water notice issue time on D+12: PUB-204 says %s local (EVT-2106 14:00Z); PUB-143 and GW-PUB-001 say %s local (EVT-1407 22:30Z); PUB-132, timed 15:00, already refers to 'today's boil water notice'; PUB-144 says 5:30 p.m. and KNCB received it the next morning. "
        "News follows the afternoon version: %s." % (f("PUB-204").get("time_local"), f("PUB-143").get("time_local"), "; ".join(news(r"boil", 12.3, 13.6)[:4])),
        "Options: (a) 17:30 local, Spanish at 06:03 next day [news, T14, newsroom]; (b) 09:00 local, Spanish 21:00 [T21 design]. Recommend (a); retime PUB-204/EVT-2106 and move PUB-132 after 17:30.")
    add("canon", "blocker", "public-record-conflict", ["EVT-1410", "EVT-2108", "GW-EVT-016"],
        "Districts 3-4 notice lifted: PUB-145 says D+30 09:00 (EVT-1410); PUB-206 says D+42 11:00 and GW-PUB-007 D+42 13:00 (EVT-2108, GW-EVT-016). News: %s." % "; ".join(news(r"boil.*lift|lift.*boil|levanta", 29, 43)[:4]),
        "Options: (a) D+42 at 11:00 local [news]; (b) D+30. Recommend (a); rewrite PUB-145/EVT-1410 as a partial lift or delete; make 11:00 vs 13:00 one time.")
    add("canon", "major", "public-record-conflict", ["EVT-0310", "EVT-0406"],
        "A citywide notice runs D+4..D+39 (PUB-039, PUB-063, EVT-0310/0406), so a separate Districts 3-4 notice issued on D+12 is issued inside an area already under notice, and the T14 'Spanish speakers were not told' gap needs the citywide notice to have been lifted for them first. "
        "News handles it as: citywide lifted for most at D+30 with 3-4 remaining, then 'lifted after 35 days' at D+39, then 3-4 at D+42.",
        "State explicitly: citywide D+4..D+30 for most districts; Districts 3-4 never lifted and re-issued/extended on D+12 for a new cause; final lift D+42. Adjust PUB-063 wording.")
    add("canon", "blocker", "public-record-conflict", ["EVT-0313", "EVT-2001", "EVT-1207", "EVT-2007", "EVT-1201"],
        "Two different oil spills. Base canon (T6, PUB-024, PUB-029, all Ledger/Gulfwater stories): about 9,000 barrels from MT Kalvora Star and MT Ostrel Bay at the Rendal Terminals berth at 04:00Z on D0, named publicly on D+1. "
        "T12/T20 (PUB-121, PUB-122, PUB-193, EVT-2001/1207/2007): 180,000 gallons from the anchored 'Auriga Meridian' from 04:30Z on D+1, boarded D+5, named responsible party D+7; its IMO is 9512847 in EVT-1201 and 9742831 in PUB-193. "
        "T19/T12 also describe a 'kinetic attack at Pier 9, D+1..D+3' (EVT-1205, EVT-1906) that the base scenario and public record do not contain; the social feed's D+1 'ship channel blast' follows it.",
        "Options: (a) keep the two-tanker valve attack as the only spill and fold Auriga Meridian into the Halcyon Drift dark-vessel thread; (b) keep both as separate incidents with separate dates and volumes. Recommend (a) and rewrite PUB-121/122/193 and EVT-12xx/20xx accordingly; drop the Pier 9 attack.")
    add("canon", "blocker", "public-record-conflict", ["EVT-0401", "EVT-1208", "EVT-0410"],
        "Port reopening: PUB-058/EVT-0401 say the channel partly reopens at D+30 with the inner channel restricted to D+44; PUB-123/EVT-1208 say the port returned to FULL commercial operations on D+30 after a phased reopening 'that began September 25' (D+11). "
        "Arrivals log and social feed follow the phased version (tankers berthing from D+7).",
        "Options: (a) closed D0..D+30, partial D+30..D+44, closed again D+44..D+58 [news, Gulfwater]; (b) phased from D+11. Recommend (a); rewrite PUB-123/EVT-1208 as the partial reopening.")
    add("canon", "major", "public-record-conflict", ["EVT-0303", "EVT-1302"],
        "911 peak: PUB-026/EVT-0303 give about 2,900 calls a day at D+1 ('nearly ten times normal'); PUB-131/EVT-1302 give a record 2,109 on D+2 with 1,940 on D+1. News headlines also carry 1,840 calls and 1,100 rescue calls on landfall day.",
        "Options: (a) 2,900 on D+1 is the peak, 2,109 on D+2 is the record for rescue calls only; (b) 2,109 is the peak. Recommend (a) with the wording fix.")
    add("canon", "major", "public-record-conflict", ["EVT-1404", "EVT-0501", "EVT-2205"],
        "FEMA Individual Assistance: PUB-141 (D0 08:30) says IA registration 'is now open ... following the presidential disaster declaration'; PUB-103 (D+4) says the declaration covers debris and protective measures only; PUB-105/EVT-0501 approve IA at D+57 with registration D+60 (a listed known quirk); PUB-142 (D+8) announces a Spanish option on the IA line. EVT-2205 cites DR-4890-TX while the damage file uses FEMA-DR-TX-2027-4821.",
        "Recommend: D0/D+8 items become the FEMA helpline and disaster-declaration information line, not IA registration; one disaster number.")
    add("canon", "minor", "public-record-conflict", ["EVT-0301", "EVT-2104"],
        "Landfall figures vary: Category 3 at 110 kt (126 mph) in HURDAT/NHC posts; '115 miles per hour' in PUB-203; 125 mph in a Ledger retrospective; surge 3.4 m / about 11 ft (EVT-0301, PUB-023) vs 12 ft and 10-14 ft elsewhere; fatalities 12 (EVT-2105) vs 23 (Ledger, D+2). PUB-140 calls Sept. 11, 2027 a Tuesday (it is a Saturday).",
        "Fix to one set: 110 kt / 125 mph, 11 ft, and one fatality series.")
    add("canon", "major", "msel-conflict", ["EVT-0318", "EVT-1901", "EVT-1907"],
        "Drone timeline: base canon has six post-storm nights over NAS Corpus Christi and the depot (EVT-0318, PUB-032, PUB-043, PUB-051); T19 has five pre-storm sorties over substations and Pier 9 (D-10..D-3) and a D+14 FAA/CBP report (PUB-181); streams add a D+30/31 port loiter. Hospital, sensor and utility names also differ between layers (SRMC/BCMC vs FAC-CCMC..; CBPWA vs GridWater; McKinley Substation vs GW-FAC-SUB-01..05).",
        "Keep both drone phases as canon (pre-storm utility/pier reconnaissance, post-storm base overflights); delete the D+30 loiter; publish one name table for hospitals, utility and substations.")


# ----------------------------------------------------------------------------------- 5 logs vs map
def chk_map():
    p = P("09_shared_state_timeline", "viewer", "map_view.html")
    if not os.path.exists(p): return
    h = open(p, encoding="utf-8").read()
    def grab(name):
        m = re.search(r"var " + name + r"=(\{.*?\});", h, re.S); return json.loads(m.group(1)) if m else {}
    VT, VM, AT, AM = grab("VTRK"), grab("VMETA"), grab("ATRK"), grab("AMETA")
    def interp(pts, t):
        ts = [q[0] for q in pts]; i = bisect.bisect_right(ts, t)
        if i == 0 or i >= len(pts): return None
        a, b = pts[i - 1], pts[i]; f_ = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
        return a[1] + f_ * (b[1] - a[1]), a[2] + f_ * (b[2] - a[2])
    comp = {"vessels": [], "aircraft": []}
    tr = ST["ais"]["tracks"]
    for m in sorted(set(VT) | set(tr)):
        row = {"id": m, "name": (VM.get(m) or {}).get("name") or ST["ais"]["names"].get(m), "in_map": m in VT, "in_log": m in tr}
        if m in VT and m in tr:
            a = tr[m]; row.update(map_span=[VT[m][0][0], VT[m][-1][0]], log_span=[round(a[0][0], 2), round(a[-1][0], 2)])
            d = sorted(nm((la, lo), q) for t, la, lo, *_ in a[::6] for q in [interp(VT[m], t)] if q)
            row.update(common_samples=len(d), median_nm=round(d[len(d) // 2], 1) if d else None, max_nm=round(d[-1], 1) if d else None)
        comp["vessels"].append(row)
    ad = ST["adsb"]["aircraft"]
    for k in sorted(set(AT) | set(ad)):
        row = {"id": k, "name": (AM.get(k) or {}).get("name") or (ad.get(k) or {}).get("callsign"), "in_map": k in AT, "in_log": k in ad}
        if k in AT and k in ad:
            a = ad[k]["pts"]; row.update(map_span=[AT[k][0][0], AT[k][-1][0]], log_span=[round(a[0][0], 2), round(a[-1][0], 2)])
            d = sorted(nm((la, lo), q) for t, la, lo, *_ in a[::30] for q in [interp(AT[k], t)] if q)
            row.update(common_samples=len(d), median_nm=round(d[len(d) // 2], 1) if d else None, max_nm=round(d[-1], 1) if d else None)
        comp["aircraft"].append(row)
    COVER["map_vs_logs"] = comp
    v = [r for r in comp["vessels"] if r.get("common_samples")]; nov = [r for r in comp["vessels"] if r["in_map"] and r["in_log"] and not r.get("common_samples")]
    big = [r for r in v if r["median_nm"] > 5]
    add("map_view", "blocker", "map-log-mismatch", [],
        "The map's embedded vessel tracks were rebuilt after the AIS log and no longer match it. Same %d MMSIs in both, but: %d vessels have no overlapping time at all (map and log place the port call in different weeks: %s); "
        "of the %d that overlap, %d differ by a median of more than 5 nm (worst medians: %s; worst single difference %.0f nm, %s). Map tracks run to D+70 for patrol craft while the log stops at D+31; the log starts harbor craft at D-13 while the map starts them at D-30." % (
            len(v) + len(nov), len(nov), ", ".join(r["name"] for r in nov), len(v), len(big), ", ".join("%s %.0f nm" % (r["name"], r["median_nm"]) for r in sorted(big, key=lambda r: -r["median_nm"])[:6]),
            max(r["max_nm"] for r in v), max(v, key=lambda r: r["max_nm"])["name"]),
        "Generate tracks once (after the geography fix) and write both the AIS CSV and the map's VTRK from that one source; add a check that fails when they differ.")
    a = [r for r in comp["aircraft"] if r.get("common_samples")]
    bad = [r for r in a if r["max_nm"] > 50]
    add("map_view", "major", "map-log-mismatch", [],
        "Aircraft: same %d airframes. Sortie positions mostly agree (median 0 nm for helicopters), but the map extends every aircraft to D-30..D+90 as parked while the logs cover shorter windows, and these differ badly: %s." % (
            len(a), "; ".join("%s median %.0f nm, max %.0f nm (map %s..%s, log %s..%s)" % (r["name"], r["median_nm"], r["max_nm"], dl(r["map_span"][0]), dl(r["map_span"][1]), dl(r["log_span"][0]), dl(r["log_span"][1])) for r in bad)),
        "Same single-source rule as vessels; check the GUNSMOKE transit points (a >4,000 nm jump indicates a bad coordinate).")


# ----------------------------------------------------------------------------------- report
def write():
    sev = collections.Counter(f["severity"] for f in FINDINGS)
    mstat = collections.Counter(r["status"] for r in MATRIX)
    by_stream = collections.defaultdict(collections.Counter)
    for r in MATRIX: by_stream[r["stream"]][r["status"]] += 1
    os.makedirs(OUT, exist_ok=True)
    json.dump({"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "scenario_span_days": SCEN,
               "counts_by_severity": dict(sev), "matrix_counts": dict(mstat), "stream_coverage": COVER, "findings": FINDINGS, "event_matrix": MATRIX},
              open(os.path.join(OUT, "stream_alignment_audit.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    o = []
    o.append("# Stream alignment audit\n")
    o.append("Generated by `scripts/audit_streams.py` (read-only on data). Scenario time: D0 = 2027-09-14, landfall 06:00Z; scenario span D-60..D+119.\n")
    o.append("**Findings:** %d blocker, %d major, %d minor. **Event evidence:** %d event-stream pairs checked: %s.\n" % (
        sev["blocker"], sev["major"], sev["minor"], len(MATRIX), ", ".join("%s %d" % kv for kv in mstat.most_common())))
    o.append("Severity: *blocker* = contradicts a headline canon event, leaks an answer or restricted name, or makes a thread unsolvable; *major* = evidence missing or wrong; *minor* = plausibility or housekeeping.\n")
    o.append("## 1. Coverage\n")
    o.append("| Stream | Starts | Ends | MSEL events outside the span |\n|---|---|---|---|")
    for s in sorted(k for k in COVER if k != "map_vs_logs"):
        c = COVER[s]; o.append("| %s | %s (%s) | %s (%s) | %s |" % (s, dl(c["start"]), c["start_utc"][:10], dl(c["end"]), c["end_utc"][:10], ", ".join(c["events_outside"]) or "none"))
    o.append("")
    order = ["canon", "map_view", "adsb + network_logs", "ais", "adsb", "drone_video", "satellite", "weather", "env_sensors", "telemetry", "maintenance", "supply", "payments", "network_logs", "911", "public_health", "eas", "social_media", "infrastructure", "(none)", "(all)"]
    titles = {"canon": "2. Canon decisions needed (conflicts inside the public record and MSEL)", "map_view": "3. Source logs vs the map viewer"}
    o.append("")
    n = 4
    for s in order:
        fs = [f for f in FINDINGS if f["stream"] == s]
        if not fs: continue
        if s in titles: o.append("## " + titles[s] + "\n")
        else: o.append("## %d. %s\n" % (n, s)); n += 1
        for f in sorted(fs, key=lambda f: ("blocker", "major", "minor").index(f["severity"])):
            o.append("**%s · %s · %s**  " % (f["id"], f["severity"], f["kind"]))
            if f["events"]: o.append("Events: " + ", ".join(f["events"]) + "  ")
            o.append(f["detail"] + "  ")
            o.append("*Fix:* " + f["recommended_fix"] + "\n")
    mv = COVER.get("map_vs_logs")
    if mv:
        o.append("## %d. Map viewer vs source logs, per asset\n" % n); n += 1
        o.append("Offsets in days from D0. Distance is between the log position and the map's interpolated position at the same time.\n")
        for kind in ("vessels", "aircraft"):
            o.append("| %s | Map span | Log span | Common samples | Median nm | Max nm |\n|---|---|---|---|---|---|" % kind.capitalize())
            for r in mv[kind]:
                ms = "%s..%s" % (dl(r["map_span"][0]), dl(r["map_span"][1])) if r.get("map_span") else ("-" if not r["in_map"] else "?")
                ls = "%s..%s" % (dl(r["log_span"][0]), dl(r["log_span"][1])) if r.get("log_span") else ("-" if not r["in_log"] else "?")
                o.append("| %s (%s) | %s | %s | %s | %s | %s |" % (r["name"], r["id"], ms, ls, r.get("common_samples", 0), r.get("median_nm", "-"), r.get("max_nm", "-")))
            o.append("")
    o.append("## %d. Event evidence matrix\n" % n)
    o.append("Status per stream:\n\n| Stream | present | wrong time | wrong values | missing | in span, unverified | no stream |\n|---|---|---|---|---|---|---|")
    for s in sorted(by_stream):
        c = by_stream[s]; o.append("| %s | %d | %d | %d | %d | %d | %d |" % (s, c["present"], c["present-but-wrong-time"], c["present-but-wrong-values"], c["missing"], c["in-span-unverified"], c["no-stream"]))
    o.append("\nEvery pair that is not `present` and has a data stream (pairs whose source has no stream are in the JSON):\n")
    o.append("| Event | Day | Threads | Stream | Status | Note |\n|---|---|---|---|---|---|")
    for r in MATRIX:
        if r["status"] in ("present", "no-stream"): continue
        o.append("| %s | D%+d | %s | %s | %s | %s |" % (r["event_id"], r["day"], ",".join(r["threads"]), r["stream"], r["status"], r["note"].replace("|", "/")))
    open(os.path.join(OUT, "stream_alignment_audit.md"), "w", encoding="utf-8").write("\n".join(o) + "\n")
    print("findings:", dict(sev), "| matrix:", dict(mstat))
    for f in FINDINGS: print(" ", f["id"], f["severity"].ljust(7), f["stream"].ljust(14), f["kind"].ljust(22), f["detail"][:110])


def main():
    load_all()
    coverage_and_matrix()
    for fn in (chk_canon, chk_map, chk_epoch, chk_ais, chk_adsb, chk_drone, chk_satellite, chk_weather, chk_env, chk_telemetry, chk_maintenance, chk_supply,
               chk_payments, chk_network, chk_911, chk_health, chk_eas, chk_social, chk_infra, chk_consolidated):
        try: fn()
        except Exception as ex:
            import traceback; traceback.print_exc()
            add(fn.__name__, "minor", "audit-error", [], "check failed: %r" % ex, "fix the audit script")
    write()


if __name__ == "__main__":
    main()
