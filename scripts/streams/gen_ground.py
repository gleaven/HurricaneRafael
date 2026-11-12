"""Ground emergency streams generated together because they describe the same responses:

  05_other_sources/911/cad_incidents_YYYY-MM.csv      911 CAD export, one row per call for service
  05_other_sources/911/reports/*.csv                  PSAP daily volumes, queue depth, shift log, ALI subscriber records
  05_other_sources/avl/avl_YYYY-MM_<AGENCY>.csv       vehicle locations for the dispatched units
  05_other_sources/sar/*.csv                          rescue case table, asset log, flood soundings

    python3 scripts/streams/gen_ground.py

Truth comes from 00_scenario/canon_timeline.json (calls_911, sar, closures, alerts) and its
expected observations; entities from cad_units, areas, facility_registry, infrastructure_assets,
aircraft_registry; every position from scripts/geo.py through ground_lib.
"""
import bisect
import collections
import csv
import datetime as dt
import glob
import json
import os

from ground_lib import *  # noqa: F401,F403
import sar_plan

H = 3600
DAY = 86400
FIRST_DAY, LAST_DAY = -30, 119

# fictional carriers (no real company names)
POSTPAID = ["Lone Star Wireless", "Bluebonnet Mobile", "Tejas Cellular", "Gulfline Wireless"]
PREPAID = ["Lone Star Wireless Prepaid", "Bluebonnet Mobile Prepaid", "Tejas Cellular Prepaid"]
LANDLINE = "Coastal Bend Telephone"
VOIP = "CableNet Voice"

CAD_HEADER = ["incident_number", "agency", "call_received_dttm", "call_answered_dttm", "dispatch_dttm", "first_arrival_dttm",
              "cleared_dttm", "priority", "nature_code", "nature_description", "address", "city", "state", "zip", "beat",
              "census_tract", "latitude", "longitude", "unit_id", "additional_units", "disposition_code", "disposition_desc",
              "narrative", "mutual_aid", "sar_priority", "sar_case_number", "transport_destination", "call_source",
              "ali_class_of_service", "ali_carrier", "callback_number", "caller_language", "call_duration_sec", "call_taker_position"]
AVL_HEADER = ["time_utc", "unit_id", "agency", "latitude", "longitude", "speed_kmh", "heading_deg", "status", "incident_number"]
SAR_HEADER = ["case_number", "mission_id", "agency", "asset_id", "asset_type", "crew_element", "launch_utc", "on_scene_utc",
              "recovery_utc", "latitude", "longitude", "address", "census_tract", "persons", "method", "outcome",
              "delivered_to", "incident_number", "delivered_utc"]

AGENCY_PREFIX = {"CCPD": "27", "CCFD": "19", "CCEMS": "12", "NCSO": "31", "PAPD": "41", "MA_FIRE": "52", "MA_EMS": "53", "TF1": "60"}

GROUPS = {
    "med": [("MEDEMER", 46), ("TRAUMAALS", 12), ("TRAUMABLS", 14), ("CARDIACAR", 6), ("STROKECVA", 5), ("MEDTRANSPT", 9), ("GENERCOP", 2), ("SUICIDETHRT", 2), ("WELLNESSMH", 4)],
    "water": [("WATERRESC", 44), ("FLOODING", 36), ("TRAPPEDVEH", 14), ("URBANSAR", 4), ("SAROPER", 2), ("SURFRESC", 60)],
    "fire": [("STRUCTFIRE", 20), ("GASLEAK", 34), ("ALARMBLDG", 22), ("FIREINVEST", 12), ("GRASSFIRE", 4), ("FUELSPILL", 5), ("HAZMATLVL1", 3)],
    "traffic": [("TRAFFICACC", 30), ("TRAFFICPD", 42), ("DWNPWRLINE", 22), ("OVERTURNED", 6)],
    "struct": [("STORMDAMAG", 40), ("ROOFCOLLAP", 14), ("TREEFALLER", 28), ("DEBRISREQ", 18)],
    "util": [("UTILEMER", 46), ("DWNPWRLINE", 34), ("GENERHAZ", 20)],
    "welfare": [("WELFCHK", 76), ("MISSINGPER", 12), ("MISSINGPER-EVAC", 12)],
    "police": [("ALARMSEC", 22), ("ASSAULT", 10), ("SHOTSFIRE", 3), ("GENASSIST", 26), ("ANIMALCALL", 12), ("LOOTING", 5), ("CURFEWVIO", 6), ("SHELTERREQ", 6), ("EVACENFOR", 3), ("WELLNESSMH", 7)],
    "wsi": [("WATERSAFE", 100)],
}
NATURE_EXTRA = {"WATERSAFE": ("WATER-SAFETY-INQUIRY", "P4", ["CCPD"])}
MED_TRANSPORT = {"MEDEMER": 0.62, "CARDIACAR": 0.8, "STROKECVA": 0.92, "TRAUMAALS": 0.86, "TRAUMABLS": 0.52, "MEDTRANSPT": 1.0,
                 "GENERCOP": 0.8, "TRAFFICACC": 0.45, "SUICIDETHRT": 0.6}

NARR = {
    "MEDEMER": ["RP ADV {a} YOA {s} DIFF BREATHING", "{s} {a} YOA CHEST PAIN CONSCIOUS", "{s} {a} YOA FELL UNABLE TO GET UP", "DIABETIC {s} {a} YOA ALTERED", "{s} {a} YOA ABD PAIN VOMITING"],
    "TRAUMAALS": ["{s} {a} YOA HEAD INJ BLEEDING", "FALL FROM LADDER {s} {a} YOA", ("{s} STRUCK BY DEBRIS LEG INJ", 0, 20), "{s} {a} YOA FELL DOWN STAIRS POSS HIP FX"],
    "TRAUMABLS": ["{s} {a} YOA LACERATION HAND", "MINOR INJ FROM FALL {s} {a} YOA", ("{s} STEPPED ON NAIL CLEANUP", 1, 60), "{s} {a} YOA ANKLE INJ"],
    "CARDIACAR": ["{s} {a} YOA NOT BREATHING CPR IN PROGRESS", "UNRESP {s} {a} YOA RP STARTING CPR"],
    "STROKECVA": ["{s} {a} YOA FACIAL DROOP SLURRED SPEECH", "POSS STROKE {s} {a} YOA LAST NORMAL 1 HR"],
    "MEDTRANSPT": ["DIALYSIS PT NEEDS TRANSPORT", "ROUTINE TRANSFER REQ {s} {a} YOA", "OXYGEN DEPENDENT PT NEEDS TRANSPORT"],
    "GENERCOP": ["FAMILY ILL GENERATOR RUNNING IN GARAGE", "CO ALARM SOUNDING HEADACHES NAUSEA GENERATOR IN USE"],
    "SUICIDETHRT": ["RP STATES {s} THREATENING SELF HARM", "CALLER DISTRAUGHT REQ HELP"],
    "WELLNESSMH": ["{s} {a} YOA CONFUSED WANDERING", "RP REQ CRISIS TEAM FOR FAMILY MBR"],
    "WATERRESC": ["FAMILY ON ROOF WATER RISING", "{n} PERSONS TRAPPED IN ATTIC WATER IN HOUSE", "ELDERLY {s} IN WHEELCHAIR WATER WAIST DEEP", "RP AND {n} CHILDREN ON KITCHEN COUNTER WATER RISING", "PERSONS STRANDED 2ND FLOOR REQ BOAT",
                  "WATER TO WINDOWS {n} PEOPLE IN DANGER NOW REQ BOAT", "DISABLED {s} IN FLOODED HOUSE NEEDS RESCUE IMMEDIATELY"],
    "FLOODING": [("WATER ENTERING RESIDENCE REQ EVAC", -1, 14), "STREET FLOODED VEH STALLED OCCUPIED", ("RP TRAPPED BY HIGH WATER CANNOT LEAVE", -1, 14), ("WATER IN HOUSE {n} PERSONS INSIDE", -1, 14),
                 ("UNDERPASS FLOODED VEH STALLED", -7, -6), ("RP STATES WATER RISING AT THIS ADDRESS REQ HELP", 0, 12), ("ELDERLY {s} TRAPPED IN FLOODED HOUSE NEEDS RESCUE", 0, 12)],
    "TRAPPEDVEH": ["VEH IN HIGH WATER OCCUPANT ON ROOF", "PERSON TRAPPED UNDER COLLAPSED CARPORT", "OCCUPIED VEH SWEPT INTO DITCH"],
    "URBANSAR": ["PARTIAL COLLAPSE VOICES HEARD", "WALL DOWN POSS PERSON INSIDE"],
    "SAROPER": ["RP CANNOT LOCATE FAMILY MBR LAST SEEN AT RESIDENCE", ("MISSING ELDERLY {s} DID NOT EVACUATE", 0, 21)],
    "SURFRESC": ["SWIMMER IN DISTRESS", "KAYAKER OVERDUE", "BOATER OVERDUE FROM BAY", "PERSON IN WATER NEAR JETTY", "VEH IN WATER AT BOAT RAMP OCCUPANT OUT", "JET SKI OPERATOR IN WATER WAVING"],
    "STRUCTFIRE": ["SMOKE FROM ROOF", "KITCHEN FIRE FLAMES VISIBLE", "FIRE IN GARAGE", ("SMOKE IN RESIDENCE AFTER POWER RESTORED", 1, 40)],
    "GASLEAK": ["STRONG ODOR OF GAS OUTSIDE", "GAS METER HISSING", "ODOR OF GAS IN RESIDENCE", "LINE STRUCK ODOR OF GAS", "RP STATES STRONG GAS ODOR AT THIS ADDRESS", "RP STATES GAS LEAK PEOPLE FEELING ILL",
                "RP STATES GAS LINE BROKEN PEOPLE ARE IN DANGER NOW", "STRONG GAS LEAK NEIGHBORS IN DANGER NOW RP EVACUATING"],
    "ALARMBLDG": ["COMMERCIAL FIRE ALARM GENERAL", "ALARM CO ADV WATERFLOW ALARM", "RESIDENTIAL SMOKE ALARM NO ANSWER"],
    "FIREINVEST": ["ODOR OF SMOKE AREA", "ILLEGAL BURN DEBRIS", "SPARKING AT POLE"],
    "GRASSFIRE": ["GRASS FIRE NEAR ROADWAY", "BRUSH BURNING VACANT LOT"],
    "FUELSPILL": ["FUEL LEAKING FROM VEH", "DIESEL ON ROADWAY", ("SHEEN IN DITCH ODOR OF FUEL", 0, 40)],
    "HAZMATLVL1": [("UNK DRUMS WASHED UP", 0, 40), "CHEMICAL ODOR FROM STORAGE", "LEAKING CONTAINER BEHIND BUSINESS"],
    "TRAFFICACC": ["2 VEH MVA WITH INJ", "MVA VEH VS POLE", "MVA ROLLOVER OCCUPANT OUT"],
    "TRAFFICPD": ["MINOR MVA NO INJ", "VEH HIT PARKED CAR", "MVA BLOCKING LANE", "SIGNAL OUT NEAR MISS"],
    "DWNPWRLINE": ["LINE DOWN ACROSS ROADWAY", "POWER LINE ON FENCE ARCING", "POLE LEANING LINES LOW", "LINE DOWN IN YARD"],
    "OVERTURNED": ["OVERTURNED TRAILER", "TRUCK ON SIDE LOAD SPILLED"],
    "STORMDAMAG": ["ROOF DAMAGE REQ ASSESSMENT", "WINDOWS BLOWN OUT", "FENCE AND CARPORT DOWN", "SIDING OFF WATER DAMAGE"],
    "ROOFCOLLAP": ["ROOF COLLAPSED INTO LIVING AREA", "CEILING DOWN PERSON POSS INSIDE", "PORCH ROOF DOWN", "RP STATES BUILDING COLLAPSED AT THIS ADDRESS PERSONS INSIDE",
                   "ROOF DOWN PERSONS ARE TRAPPED INSIDE NOW"],
    "TREEFALLER": ["TREE ON HOUSE", "TREE ON VEH", "LARGE LIMB BLOCKING STREET"],
    "DEBRISREQ": ["DEBRIS BLOCKING ROADWAY", ("REQ PICKUP STORM DEBRIS", 0, 75), ("BOAT IN ROADWAY", 0, 20), "MATTRESS IN ROADWAY", "LOAD SPILLED DEBRIS IN LANE"],
    "UTILEMER": ["NO POWER MEDICAL EQUIPMENT IN HOME", "TRANSFORMER BLEW", "WATER MAIN BREAK", ("NO WATER PRESSURE", 0, 42), "POWER OUT TRAFFIC SIGNAL DARK",
                 ("RP ASKING HOW LONG TO BOIL TAP WATER", 4, 12), ("NO WATER RP ASKING ABOUT BOIL NOTICE", 4, 12)],
    "GENERHAZ": ["GENERATOR RUNNING ON PORCH NEAR WINDOW", "NEIGHBOR GENERATOR IN CARPORT FUMES"],
    "WELFCHK": ["REQ WELFARE CHK ELDERLY {s} NO CONTACT", "OUT OF TOWN FAMILY REQ CHK ON RESIDENT", ("NEIGHBOR NOT SEEN SINCE STORM", 0, 45), "REQ CHK ON DISABLED RESIDENT NO PHONE",
                "NEIGHBOR NOT SEEN IN SEVERAL DAYS MAIL PILING UP"],
    "MISSINGPER": ["{s} {a} YOA MISSING SINCE YESTERDAY", "JUVENILE DID NOT RETURN HOME"],
    "MISSINGPER-EVAC": ["FAMILY MBR SEPARATED DURING EVAC", "CANNOT LOCATE RELATIVE AFTER EVAC BUS"],
    "ALARMSEC": ["BURGLAR ALARM FRONT DOOR", "ALARM CO ADV MOTION REAR", "PANIC ALARM NO ANSWER ON CALLBACK"],
    "ASSAULT": ["DISTURBANCE PHYSICAL", "FIGHT IN PARKING LOT", "RP STRUCK BY KNOWN SUBJ"],
    "SHOTSFIRE": ["RP HEARD SHOTS", "SHOTS FIRED AREA UNK DIRECTION"],
    "GENASSIST": ["RP REQ INFO ROAD CLOSURES", "CITIZEN ASSIST LOCKOUT", "RP REQ OFFICER FOR CIVIL STANDBY", "FOUND PROPERTY", "NOISE COMPLAINT",
                  ("RP ASKING IF TAP WATER SAFE TO DRINK", 4, 12), ("RP REQ INFO BOIL WATER NOTICE", 4, 12), ("RP ASKING WHERE TO GET BOTTLED WATER", 4, 12)],
    "ANIMALCALL": ["LOOSE DOGS", "LIVESTOCK ON ROADWAY", "INJ ANIMAL"],
    "LOOTING": [("SUBJS REMOVING ITEMS FROM DAMAGED BUSINESS", 0, 30), "BURGLARY IN PROGRESS VACANT RESIDENCE", "RP HEARS SOMEONE BREAKING INTO GARAGE", "SUBJ SEEN ENTERING CLOSED BUSINESS"],
    "CURFEWVIO": ["SUBJS ON FOOT AFTER CURFEW", "VEH CRUISING DARK AREA AFTER CURFEW"],
    "SHELTERREQ": ["FAMILY REQ SHELTER LOCATION", "RP NEEDS RIDE TO SHELTER NO VEH", "REQ SHELTER WITH PETS"],
    "EVACENFOR": ["RESIDENT REFUSING TO EVACUATE", "REQ ASSIST EVAC NURSING RESIDENT"],
    "EXPLOSION": ["RP HEARD LOUD EXPLOSION TOWARD JETTIES", "LOUD BOOM WINDOWS RATTLED DIRECTION OF CHANNEL", "EXPLOSION HEARD FLASH SEEN OVER WATER", "HOUSE SHOOK LOUD BLAST FROM SHIP CHANNEL AREA"],
    "WATERSAFE": ["RP ASKING IF TAP WATER SAFE", "REQ INFO BOIL WATER NOTICE", "RP ASKING HOW LONG TO BOIL", "RP DRANK TAP WATER ASKING WHAT TO DO", "REQ WATER DISTRIBUTION SITE", "RP ASKING IF NOTICE COVERS ADDRESS"],
}


# When a nature code can occur at all (scenario day, local): storm-only categories exist only while their cause does.
# A code may have several windows. Codes not listed can occur on any day.
CODE_WINDOW = {
    "WATERRESC": [(0, 14)], "TRAPPEDVEH": [(0, 14)], "URBANSAR": [(0, 10)], "FLOODING": [(-7, -6), (-1, 14)], "SAROPER": [(0, 21)],
    "STORMDAMAG": [(0, 60)], "ROOFCOLLAP": [(0, 30)], "GENERHAZ": [(0, 40)], "GENERCOP": [(0, 40)],
    "CURFEWVIO": [(1, 21)], "SHELTERREQ": [(-3, 30)], "EVACENFOR": [(-2, 0)], "MISSINGPER-EVAC": [(-2, 14)],
    "SURFRESC": [(-60, -2), (15, 200)],
}
CURFEW_FROM = local_ts(1, "20:00")          # dusk-to-dawn curfew announced the morning after landfall (canon closures.curfew)
CURFEW_UNTIL = local_ts(22, "06:00")        # generated detail: no violations logged after the third week


def code_ok(code, d, t=None):
    w = CODE_WINDOW.get(code)
    if w is not None and not any(a <= d <= b for a, b in w):
        return False
    if code == "CURFEWVIO" and t is not None:
        h = local_dt(t).hour
        return CURFEW_FROM <= t < CURFEW_UNTIL and (h >= 20 or h < 6)
    return True


def code_weight(code, w, d):
    """Storm-driven categories fade as their cause does."""
    if code == "CURFEWVIO":
        return w * max(0.15, 1 - (d - 1) / 21.0) * 2.2
    if code == "SHELTERREQ":
        return w * (1.6 if -2 <= d <= 6 else max(0.12, 1 - (d - 6) / 24.0))
    if code == "STORMDAMAG":
        return w * max(0.1, 1 - max(0, d - 12) / 48.0)
    return w


def pick_code(group, d, t, rg):
    codes = [(c, code_weight(c, w, d)) for c, w in GROUPS[group] if code_ok(c, d, t)]
    wts = np.array([w for _, w in codes], float)
    return codes[int(rg.choice(len(codes), p=wts / wts.sum()))][0]


class Sim:
    def __init__(self):
        self.g = Ground()
        self.cad = reg("cad_units")
        self.nature = {n["code"]: (n["description"], n["default_priority"], n["agency"]) for n in self.cad["nature_codes"]}
        self.nature.update(NATURE_EXTRA)
        self.dispo = {d["code"]: d["description"].split(" - ")[0] if False else d["description"] for d in self.cad["disposition_codes"]}
        self.areas = {a["area_id"]: a for a in reg("areas")["areas"]}
        self.setup_tracts()
        self.setup_places()
        self.setup_units()
        self.seq = collections.Counter()
        self.incidents = []
        self.avl_buf = collections.defaultdict(list)
        self.gps = rng("ground", "gps")
        self.avl_rows = 0
        self.month_starts, self.month_keys = [], []
        y, m = 2027, 7
        while (y, m) <= (2028, 3):
            self.month_starts.append(local_ts((dt.date(y, m, 1) - dt.date(2027, 9, 14)).days, "00:00"))
            self.month_keys.append(f"{y}-{m:02d}")
            y, m = (y, m + 1) if m < 12 else (y + 1, 1)
        self.numbers = {}          # callback number -> subscriber record
        self.repeat_pool = collections.defaultdict(list)
        self.pending_special = collections.defaultdict(list)   # local day -> incidents fixed in advance

    # ------------------------------------------------------------------ areas
    def setup_tracts(self):
        g = self.g
        zips = [a for a in self.areas.values() if a["area_type"] == "zip"]
        beats = [a for a in self.areas.values() if a["area_type"] == "patrol_beat"]
        self.tracts = {}
        for a in self.areas.values():
            if a["area_type"] != "census_tract" or not a.get("bbox") or not a.get("reference_point"):
                continue
            rp = (a["reference_point"]["latitude"], a["reference_point"]["longitude"])
            z = min(zips, key=lambda q: geo.dist_m(rp, (q["reference_point"]["latitude"], q["reference_point"]["longitude"])))
            b = min(beats, key=lambda q: geo.dist_m(rp, (q["reference_point"]["latitude"], q["reference_point"]["longitude"])))
            name = a["neighbourhood_name"]
            city, police = "CORPUS CHRISTI", "CCPD"
            if name in ("Mustang Island N", "East Flats"):
                city, police = "PORT ARANSAS", "PAPD"
            elif name.startswith("Robstown"):
                city, police = "ROBSTOWN", "NCSO"
            elif name.startswith("Rural") or name.endswith("Area") and name not in ("Oso Bay Area",):
                police = "NCSO"
            pool = g.sample_locations(a["bbox"], 900, rng("ground", "pool", a["tract"]))
            if len(pool) < 20:
                continue
            self.tracts[a["tract"]] = {
                "tract": a["tract"], "name": name, "zone": a["evacuation_zone"], "q": a.get("income_quartile"),
                "pop": a["population"], "pov": a["persons_below_poverty"] / max(1, a["population"]),
                "hisp": a["hispanic_or_latino"] / max(1, a["population"]), "zip": z["zip"], "beat": b["beat_id"],
                "city": city, "police": police, "pool": pool, "bbox": a["bbox"], "ref": rp}
        T = self.tracts
        self.L = [t for t in T if T[t]["q"] == 1 and T[t]["zone"] in ("A", "B")]      # low-income surge-zone tracts
        self.Hi = [t for t in T if T[t]["q"] == 4]
        self.Z61 = [t for t in T if T[t]["zip"] in ("78404", "78405")]
        ids = list(T)
        self.t_ids = ids
        base = np.array([T[t]["pop"] * (1 + 1.2 * T[t]["pov"]) for t in ids])
        self.w_base = base / base.sum()
        expo = {"A": 3.0, "B": 2.2, "C": 0.8, "D": 0.35}
        wl = np.array([T[t]["pop"] if t in self.L else 0 for t in ids], float)
        self.w_L = wl / wl.sum()
        wo = np.array([0 if t in self.L else T[t]["pop"] * expo[T[t]["zone"]] for t in ids], float)
        self.w_notL = wo / wo.sum()
        self.base_L_share = float(sum(self.w_base[i] for i, t in enumerate(ids) if t in self.L))
        wz = np.array([{"Molina": 0.42, "Westside CC": 0.30, "South Central CC": 0.18, "Del Mar Heights": 0.10}.get(T[t]["name"], 0) if t in self.Z61 else 0 for t in ids], float)
        self.w_Z61 = wz / wz.sum()
        wn = np.array([0 if t in self.Z61 else T[t]["pop"] * expo[T[t]["zone"]] * (2.0 if t in self.L else 1.0) for t in ids], float)
        self.w_notZ61 = wn / wn.sum()
        self.tract_by_name = {T[t]["name"]: t for t in T}

    def tract_of(self, lat, lon):
        """Census tract for a point: the tract whose box contains it (nearest reference point if several), else the nearest tract."""
        T = self.tracts
        inside = [t for t in T if T[t]["bbox"][0] <= lon <= T[t]["bbox"][2] and T[t]["bbox"][1] <= lat <= T[t]["bbox"][3]]
        return min(inside or list(T), key=lambda t: geo.dist_m((lat, lon), T[t]["ref"]))

    def setup_places(self):
        g = self.g
        self.station = {s["station_id"]: g.anchor(s["latitude"], s["longitude"]) for s in self.cad["stations"]}
        fac = reg("facility_registry")["facilities"]
        self.fac = {f["facility_id"]: f for f in fac}
        self.hosp = {f["facility_id"]: g.anchor(f["latitude"], f["longitude"]) for f in fac if f["facility_type_code"] == "HOSP-ED"}
        self.shelter = {f["facility_id"]: g.anchor(f["latitude"], f["longitude"]) for f in fac if f["facility_type_code"] == "SHELTER"}
        inf = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"]}
        self.sub = {k: (inf[k]["latitude"], inf[k]["longitude"]) for k in ("GW-FAC-SUB-02", "GW-FAC-SUB-03")}
        portland = self.areas["AREA-CITY-PORTLAND"]["bbox"]
        self.pool_portland = g.sample_locations(portland, 80, rng("ground", "pool", "portland"))
        pa = (-97.075, 27.826, -97.052, 27.842)
        self.pool_pa_water = g.sample_locations(pa, 60, rng("ground", "pool", "pa"))

    def setup_units(self):
        g = self.g
        self.units = {}
        avl_types = {"engine", "truck", "ladder", "rescue", "als_ambulance", "bls_ambulance", "patrol", "high_water_vehicle",
                     "welfare_check_team", "swiftwater_team", "evacuation_bus", "traffic"}
        for u in self.cad["units"]:
            home = self.station.get(u.get("home_station"))
            if home is None:
                continue
            rec = {"id": u["unit_id"], "agency": u["agency"], "type": u["type"], "home": home, "free": 0, "busy": [],
                   "avl": bool(u.get("avl_equipped")) and u["type"] in avl_types, "from": 0, "to": 9e18, "station": u["home_station"]}
            if u["agency"] == "CCPD" and u["type"] == "patrol":
                beat = self.areas.get("AREA-BEAT-" + str(u.get("beat")))
                box = beat["bbox"] if beat else None
                if u["unit_id"] == "1B3":
                    box = self.areas["AREA-NBH-NORTHBEACH"]["bbox"]       # stays on its own side of the bridge
                if box:
                    p = g.sample_locations(box, 1, rng("ground", "post", u["unit_id"]), local_boost=0.5)
                    if p:
                        rec["home"] = p[0]
            if u["agency"] in ("MA_FIRE", "MA_EMS"):
                rec["from"], rec["to"] = local_ts(0, "08:00"), local_ts(21, "08:00")
            if u["agency"] in ("TXARNG", "TF1", "FEMA"):
                rec["from"], rec["to"] = local_ts(0, "10:00"), local_ts(14, "08:00")
            if u["type"] == "welfare_check_team":
                rec["from"], rec["to"] = local_ts(4, "06:00"), local_ts(21, "18:00")
            if u["type"] == "evacuation_bus":
                rec["from"], rec["to"] = local_ts(-3, "06:00"), local_ts(10, "20:00")
            self.units[u["unit_id"]] = rec
        U = self.units
        def of(types, agencies=None):
            return [u for u in U.values() if u["type"] in types and (agencies is None or u["agency"] in agencies)]
        self.pool = {
            "ems": of({"als_ambulance", "bls_ambulance", "mutual_aid_als"}),
            "fire": of({"engine", "truck", "ladder", "rescue", "mutual_aid_engine", "mutual_aid_truck"}),
            "police_CCPD": of({"patrol", "traffic"}, {"CCPD"}),
            "police_NCSO": of({"patrol"}, {"NCSO"}),
            "police_PAPD": of({"patrol"}, {"PAPD"}) + of({"patrol"}, {"NCSO"}),
            "welfare": of({"welfare_check_team"}),
        }
        self.ma_portland = [U[x] for x in ("MA-SANPAT-E1", "MA-SANPAT-M1", "MA-SANPAT-M2") if x in U]
        # shortest-path trees for every hub (quarters, posts, hospitals, shelters), bridges open and closed
        hubs = {u["home"]["node"] for u in U.values()} | {h["node"] for h in self.hosp.values()} | {h["node"] for h in self.shelter.values()}
        for n in hubs:
            g.tree(n, False); g.tree(n, True)

    # ------------------------------------------------------------------ helpers
    def closed(self, t):
        return BRIDGE_CLOSE <= t < BRIDGE_OPEN

    def next_number(self, agency):
        self.seq[agency] += 1
        return f"{AGENCY_PREFIX.get(agency, '99')}-2027-{self.seq[agency]:06d}" if True else ""

    def phone(self, rg, t, loc_key=None, forced=None):
        """Callback number with ALI class and carrier; a share of callers call more than once."""
        if forced:
            return forced
        if loc_key is not None and self.repeat_pool[loc_key] and rg.random() < 0.55:
            return self.repeat_pool[loc_key][int(rg.integers(len(self.repeat_pool[loc_key])))]
        r = rg.random()
        if r < 0.66:
            cls = "WPH2" if rg.random() < 0.9 else "WPH1"
            prepaid = rg.random() < 0.15
            carrier = PREPAID[int(rg.integers(3))] if prepaid else POSTPAID[int(rg.integers(4))]
            plan = "PREPAID" if prepaid else "POSTPAID"
        elif r < 0.79:
            cls, carrier, plan = "RESD", LANDLINE, "LANDLINE"
        elif r < 0.87:
            cls, carrier, plan = "BUSN", LANDLINE, "LANDLINE"
        else:
            cls, carrier, plan = "VOIP", VOIP, "VOIP"
        ac = "361" if (plan in ("LANDLINE", "VOIP") or rg.random() < 0.9) else ["512", "210", "956", "737", "830"][int(rg.integers(5))]
        while True:
            num = f"{ac}-{int(rg.integers(200, 899)):03d}-{int(rg.integers(0, 10000)):04d}"
            if num not in self.numbers:
                break
        # activation: years back; after the storm a few percent of prepaid phones are new
        days_back = int(rg.gamma(2.0, 420)) + 20
        if plan == "PREPAID" and t > LANDFALL and rg.random() < 0.16:
            days_back = int(rg.integers(0, 6))
        act = t - days_back * DAY
        self.numbers[num] = {"num": num, "cls": cls, "carrier": carrier, "plan": plan, "act": act,
                             "registered": "N" if (plan == "PREPAID" and rg.random() < 0.62) else "Y"}
        rec = (num, cls, carrier)
        if loc_key is not None and len(self.repeat_pool[loc_key]) < 3:
            self.repeat_pool[loc_key].append(rec)
        return rec

    def narrative(self, code, rg, lang, d=0):
        opts = [o if isinstance(o, str) else o[0] for o in (NARR.get(code) or ["RP REQ ASSIST"]) if isinstance(o, str) or o[1] <= d <= o[2]]
        s = opts[int(rg.integers(len(opts)))].format(a=int(rg.integers(19, 94)), s="MALE" if rg.random() < 0.5 else "FEMALE", n=int(rg.integers(2, 6)))
        if lang == "ES":
            s += " / SPANISH SPKR" + (" LANG LINE" if rg.random() < 0.4 else "")
        return s

    # ------------------------------------------------------------------ AVL
    def avl_write(self, unit, t, lat, lon, speed, heading, status, inc):
        t = int(t)
        i = bisect.bisect_right(self.month_starts, t) - 1
        self.avl_buf[(self.month_keys[i], unit["agency"])].append(
            f"{iso(t)},{unit['id']},{unit['agency']},{lat:.6f},{lon:.6f},{speed:.0f},{heading:.0f},{status},{inc}")
        self.avl_rows += 1

    def park_pos(self, place, apron=False):
        """Where a stopped vehicle sits: off the centreline towards the building it serves (station
        apron up to 16 m in, kerbside about 5 m at an incident), with a metre of GPS scatter."""
        dy, dx = (place["lat"] - place["rlat"]) * M_LAT, (place["lon"] - place["rlon"]) * M_LON
        dist = math.hypot(dx, dy)
        step = min(max(0.0, dist - 2.0), 16.0 if apron else 5.5)
        j = self.gps.normal(0, 0.9, 2)
        if dist < 1.0:
            return place["rlat"] + j[0] / M_LAT, place["rlon"] + j[1] / M_LON
        return place["rlat"] + (dy / dist * step + j[0]) / M_LAT, place["rlon"] + (dx / dist * step + j[1]) / M_LON

    def avl_move(self, unit, route, t0, t1, cadence, status, inc):
        """Breadcrumbs along a route between t0 and t1 (actual seconds), every cadence seconds."""
        lats, lons, secs = route
        T = max(1.0, t1 - t0)
        if T / cadence > 22:                 # slow going on flooded streets: the modem also reports by distance, so fewer fixes
            cadence = T / 22
        ts_ = np.arange(t0, t1, cadence)
        nom = (ts_ - t0) / T * secs[-1]
        la = np.interp(nom, secs, lats); lo = np.interp(nom, secs, lons)
        idx = np.clip(np.searchsorted(secs, nom, side="right") - 1, 0, len(secs) - 2)
        dlat = (lats[1:] - lats[:-1]) * M_LAT; dlon = (lons[1:] - lons[:-1]) * M_LON
        hd = (np.degrees(np.arctan2(dlon, dlat)) + 360) % 360
        sp = np.minimum(130, np.hypot(dlat, dlon) / np.maximum(1e-6, (secs[1:] - secs[:-1]) * T / secs[-1]) * 3.6)
        jit = self.gps.normal(0, 1.7, (len(ts_), 2))       # receiver scatter, metres
        for k in range(len(ts_)):
            i = idx[k]
            self.avl_write(unit, ts_[k], la[k] + jit[k, 0] / M_LAT, lo[k] + jit[k, 1] / M_LON, sp[i], hd[i], status, inc)

    def avl_park(self, unit, place, t0, t1, status, inc, heading=0):
        if t1 <= t0:
            return
        la, lo = self.park_pos(place, apron=status in ("HSP", "UNLD", "LOAD"))
        for t in ((t0, (t0 + t1) / 2) if t1 - t0 > 900 else (t0,)):
            self.avl_write(unit, t, la, lo, 0, heading, status, inc)

    def avl_response(self, unit, inc, t_disp, t_arr, t_clear, loc, dest=None, t_dest=None, t_leave_dest=None, t_home=None, emergency=True):
        """Station -> scene -> (hospital) -> station for one dispatch. Times are actual epochs."""
        g = self.g
        c = self.closed(t_disp)
        r = g.route(unit["home"], loc, c)
        if r is None:
            return
        fast = 15 if unit["agency"] in ("CCFD", "CCEMS") else 30      # fire/EMS modems report twice as often as patrol cars
        self.avl_move(unit, r, t_disp, t_arr, fast if emergency else 2 * fast, "ENR", inc)
        self.avl_park(unit, loc, t_arr, t_clear, "ONS", inc)
        cur = loc
        t = t_clear
        if dest is not None:
            r2 = g.route(loc, dest, self.closed(t))
            if r2 is not None:
                self.avl_move(unit, r2, t, t_dest, 60, "TRN", inc)
                self.avl_park(unit, dest, t_dest, t_leave_dest, "HSP", inc)
                cur, t = dest, t_leave_dest
        r3 = g.route(cur, unit["home"], self.closed(t))
        if r3 is not None and t_home > t:
            self.avl_move(unit, r3, t, t_home, 180, "RTQ", "")
            self.avl_write(unit, int(t_home), *self.park_pos(unit["home"], True), 0, 0, "AIQ", "")
        unit["busy"].append((t_disp, t_home))

    # ------------------------------------------------------------------ scheduling
    def travel(self, unit, loc, t):
        return self.g.travel_seconds(unit["home"], loc, self.closed(t))

    def pick_unit(self, pool, loc, t_ready, factor, max_wait):
        """Unit giving the earliest arrival; None if nobody can start within max_wait."""
        best = None
        t0 = max(t_ready, HOLD_END) if HOLD_START <= t_ready < HOLD_END else t_ready
        for u in pool:
            if not (u["from"] <= t0 < u["to"]):
                continue
            tr = self.travel(u, loc, t0)
            if tr is None:
                continue
            start = max(u["free"], t0)
            if HOLD_START <= start < HOLD_END:
                start = HOLD_END
            if start - t0 > max_wait:
                continue
            arr = start + tr * factor
            if best is None or arr < best[0]:
                best = (arr, u, start, tr)
        return best

    def nearest_hospital(self, loc, t):
        best = None
        for fid, h in self.hosp.items():
            tr = self.g.travel_seconds(h, loc, self.closed(t))
            if tr is not None and (best is None or tr < best[0]):
                best = (tr, fid, h)
        return best


# ======================================================================================
# search and rescue (canon sar section): 1,427 rescues, then 11 no-find cases
# ======================================================================================
def Z(day, hhmm):
    """Epoch of a UTC clock time on the UTC date of scenario day `day` (D0 = 2027-09-14)."""
    h, m = map(int, hhmm.split(":"))
    return D0_EPOCH + day * DAY + h * H + m * 60


def split_persons(total, n, rg, lo=1):
    """n positive integers summing to total."""
    base = [lo] * n
    for _ in range(total - lo * n):
        base[int(rg.integers(n))] += 1
    return base


class Sar:
    def __init__(self, sim):
        self.sim = sim
        self.rg = rng("ground", "sar")
        self.missions = []
        self.free = collections.defaultdict(float)     # (asset, element) -> next free time
        self.uses = collections.Counter()
        self.build()

    def tract(self, weights):
        names = list(weights)
        p = np.array([weights[n] for n in names], float)
        return self.sim.tract_by_name[names[int(self.rg.choice(len(names), p=p / p.sum()))]]

    def loc(self, tract):
        pool = self.sim.tracts[tract]["pool"]
        return pool[int(self.rg.integers(len(pool)))]

    def assign_deliveries(self):
        """Where each rescued household is taken, in time order: a hospital, an open shelter with
        room for it, or the nearest fire station used as a dry-ground collection point. Survivors
        flown to the air station are bussed on to a shelter in groups. Fills self.flows, the
        shelter arrivals the census is built from."""
        s = self.sim
        rg = rng("ground", "deliver")
        cap = {fid: s.fac[fid]["shelter"]["capacity"] for fid in SHELTER_PLAN}
        xy = {fid: (s.fac[fid]["latitude"], s.fac[fid]["longitude"]) for fid in SHELTER_PLAN}
        hosp = {fid: (s.fac[fid]["latitude"], s.fac[fid]["longitude"]) for fid in s.hosp if fid != "FAC-ABCH-015"}
        sta = {st["station_id"]: (st["latitude"], st["longitude"]) for st in s.cad["stations"] if st["agency"] == "CCFD"}
        stock = collections.defaultdict(lambda: collections.defaultdict(int))
        self.flows = []
        self.onward = {fid: collections.Counter() for fid in SHELTER_PLAN}     # nights in a shelter of people bussed from the air station
        dist = lambda a, b: math.hypot((a[0] - b[0]) * M_LAT, (a[1] - b[1]) * M_LON)

        def fits(fid, t, n, stay):
            d0 = day_of(t)
            if t < shelter_open_ts(fid) + 900 or d0 >= shelter_close_day(fid) - 1:
                return False
            return all(shelter_base(fid, cap[fid], d) + stock[fid][d] + n <= 0.97 * cap[fid] for d in range(d0, d0 + stay))

        def admit(fid, t, n, stay, mode, ref):
            d0 = day_of(t)
            for d in range(d0, d0 + stay):
                stock[fid][d] += n
            self.flows.append([int(t), fid, n, mode, ref, stay])

        def shelter_for(here, t, n, key, reach=1.0):
            best = None
            for fid in SHELTER_PLAN:
                stay = stay_days(key, fid)
                if fits(fid, t, n, stay):
                    score = dist(here, xy[fid]) * rg.uniform(0.8, 1.25)
                    if best is None or score < best[0]:
                        best = (score, fid, stay)
            return best

        todo = []
        nas = collections.defaultdict(list)             # two-hour bus slot -> groups waiting at the air station
        slot0 = Z(0, "08:00")
        for m in self.missions:
            if m["type"] == "helicopter":
                for e in m["events"]:
                    if e["delivered"] == "FAC-DOD-01" and rng("ground", "onward", e["cases"][0]).random() < 0.64:
                        nas[max(0, int((e["deliv_t"] + 2400 - slot0) // (2 * H)) + 1)].append(e)
                continue
            for e in m["events"]:
                amb = e["method"] == "AMBULATORY CONTACT"
                e["deliv_t"] = int(max(e["t"] + 600, min(e["t"] + rg.uniform(18, 50) * 60, m["recovery"] + rg.uniform(4, 20) * 60))) if not amb \
                    else int(e["t"] + rg.uniform(20, 60) * 60)
                todo.append((e["deliv_t"], 0, e["cases"][0], e, m))
        for k, evs in nas.items():
            todo.append((slot0 + k * 2 * H + int(rg.uniform(22, 41) * 60), 1, evs[0]["cases"][0], evs, None))
        todo.sort(key=lambda x: x[:3])
        mode = {"BOAT": "RESCUE BOAT", "HIGH-WATER VEHICLE": "HIGH-WATER VEHICLE", "AMBULATORY CONTACT": "ESCORTED ON FOOT"}
        for t, kind, _, e, m in todo:
            if kind == 1:                               # bus from the air station: the nearest shelters that can take the group
                here = (s.fac["FAC-DOD-01"]["latitude"], s.fac["FAC-DOD-01"]["longitude"])
                loads = collections.defaultdict(int)
                for ev in e:
                    b = shelter_for(here, t, ev["persons"], ev["cases"][0])
                    if b:
                        stock_fid = b[1]
                        for d in range(day_of(t), day_of(t) + b[2]):
                            stock[stock_fid][d] += ev["persons"]
                            self.onward[stock_fid][d] += ev["persons"]
                        loads[stock_fid] += ev["persons"]
                        ev["onward"] = (stock_fid, b[2])
                for i, (fid, n) in enumerate(sorted(loads.items(), key=lambda x: dist(here, xy[x[0]]))):
                    self.flows.append([int(t + i * 17 * 60), fid, n, "BUS FROM NAS CORPUS CHRISTI", "", 0])
                continue
            here = (e["loc"]["lat"], e["loc"]["lon"])
            n = e["persons"]
            r = rg.random()
            dest = None
            if r < 0.07:
                dest = min(hosp, key=lambda f: dist(here, hosp[f]))
            elif r < (0.80 if e["method"] == "AMBULATORY CONTACT" else 0.60):
                b = shelter_for(here, t, n, e["cases"][0])
                if b:
                    dest = b[1]
                    admit(dest, t, n, b[2], mode[e["method"]], m["id"])
            if dest is None:
                near = sorted(sta, key=lambda k: dist(here, sta[k]))
                dest = near[0] if rg.random() < 0.72 else near[1]
            e["delivered"] = dest

    def add(self, agency, asset, atype, element, launch, recovery, events):
        self.missions.append({"agency": agency, "asset": asset, "type": atype, "element": element, "launch": int(launch),
                              "recovery": int(recovery), "events": events})

    def events_for(self, persons, t0, t1, weights, method, air=False, max_per=4, single=False):
        rg = self.rg
        sizes = []
        left = persons
        while left > 0:
            k = left if single else min(left, int(rg.integers(1, max_per + 1)))
            sizes.append(k); left -= k
        base_tract = self.tract(weights)
        out = []
        for i, k in enumerate(sizes):
            tr = base_tract if rg.random() < 0.7 else self.tract(weights)
            t = t0 + (t1 - t0) * (i + 0.5) / len(sizes) + rg.uniform(-120, 120)
            out.append({"t": int(min(max(t, t0 + 30), t1 - 30)), "tract": tr, "loc": self.loc(tr), "persons": k, "method": method})
        return out

    def surface(self, w0, w1, persons, assets, weights, per=(3, 7), dur=(1.3, 2.6), method="BOAT", n_missions=None, single_event=False):
        """Missions inside [w0, w1): every event time stays inside the window."""
        rg = self.rg
        if persons <= 0:
            return
        n = n_missions or max(1, int(round(persons / ((per[0] + per[1]) / 2))))
        n = min(n, persons)
        sizes = split_persons(persons, n, rg)
        starts = sorted(w0 + (w1 - w0 - dur[0] * H) * (i + rg.random() * 0.8) / n for i in range(n))
        ai = 0
        for size, st in zip(sizes, starts):
            d = rg.uniform(dur[0], dur[1]) * H
            # asset free the earliest
            a = min(assets, key=lambda a: (max(self.free[a], st), self.uses[a], assets.index(a)))
            self.uses[a] += 1
            st = max(st, self.free[a])
            end = min(st + d, w1 - 60)
            if end - st < 20 * 60:
                st = end - 25 * 60
            ev = self.events_for(size, st + 0.25 * (end - st), end - 0.08 * (end - st), weights, method, single=single_event)
            self.free[a] = end + 10 * 60
            asset, element = a
            agency = ("TF1" if asset.startswith("TF1") else "CIVBOAT" if asset.startswith("CIV") else "TXARNG" if asset.startswith("TXARNG")
                      else "MA_FIRE" if asset.startswith("MA-") else "CCFD")
            atype = {"TF1": "swiftwater_team", "CIVBOAT": "civilian_boat", "TXARNG": "high_water_vehicle"}.get(agency) or \
                    ("high_water_vehicle" if asset.startswith("HWV") else "welfare_check_team" if asset.startswith("WC") else "rescue_boat")
            self.add(agency, asset, atype, element, st, end, ev)

    def build(self):
        s, rg = self.sim, self.rg
        FB = {"Flour Bluff Shore": .45, "Flour Bluff Central": .3, "Flour Bluff East": .25}
        NB = {"North Beach": .7, "Rincon Point": .3}
        D0W = {"Flour Bluff Shore": .35, "Flour Bluff Central": .2, "Flour Bluff East": .1, "North Beach": .25, "Rincon Point": .1}
        P1AIR = {"Flour Bluff Shore": .16, "Flour Bluff Central": .08, "Flour Bluff East": .06, "North Beach": .14, "Rincon Point": .06,
                 "Mustang Island N": .08, "East Flats": .07, "Hillcrest": .1, "Port/Channel S": .06, "Port/Channel N": .04,
                 "Bayfront Downtown": .1, "Padre Island NW": .05}
        CAL = {"Calallen Riverside": .7, "Calallen North": .3}
        D34 = {"Molina": .25, "Westside CC": .2, "Hillcrest": .15, "South Central CC": .12, "Del Mar Heights": .06,
               "Port/Channel S": .08, "Port/Channel N": .04, "Bayfront Downtown": .05, "Cunningham": .05}
        P4W = {"Molina": .15, "Westside CC": .12, "Hillcrest": .12, "Port/Channel S": .08, "Port/Channel N": .05, "Bayfront Downtown": .08,
               "North Beach": .08, "Rincon Point": .04, "Flour Bluff Shore": .08, "Flour Bluff Central": .05, "South Central CC": .06,
               "Del Mar Heights": .03, "Calallen Riverside": .06}
        P4LAND = {k: v for k, v in P4W.items() if k not in ("North Beach", "Rincon Point")}
        boats = [(f"CC-SAR-{i:03d}", "") for i in range(1, 24)]
        civ = [(f"CIV-BOAT-{i:03d}", "") for i in range(1, 88)]
        tf1 = [("TF1-ALPHA", f"Alpha-{i}") for i in range(1, 9)] + [("TF1-BRAVO", f"Bravo-{i}") for i in range(1, 9)]
        hwv = [("HWV-1", ""), ("HWV-2", ""), ("HWV-3", "")]
        arng = [(f"TXARNG-HWV-{i}", "") for i in range(1, 5)]

        # --- helicopters (canon EVT-1702, EVT-1703): the whole air plan comes from sar_plan, shared with the aircraft tracks
        self.missions += sar_plan.plan_air(self, Z, reg)
        self.surface(local_ts(0, "13:00"), local_ts(0, "20:00"), 12, [("HWV-1", ""), ("HWV-2", "")], FB, n_missions=4, dur=(1.0, 1.6),
                     method="HIGH-WATER VEHICLE", single_event=True)
        # --- D+1 until 15:00 local (20:00Z): helicopter peak (EVT-1703), TF-1 boats on Calallen Creek
        w0, w1 = local_ts(1, "06:30"), local_ts(1, "15:00")
        self.surface(w0, w1, 70, tf1[:8], CAL, per=(5, 9), dur=(1.5, 2.6))
        self.surface(w0, w1, 45, boats, {**NB, **FB}, per=(3, 6))
        self.surface(w0, w1, 18, hwv, FB, n_missions=7, dur=(0.9, 1.5), method="HIGH-WATER VEHICLE", single_event=True)
        # --- D+1 15:00 local to D+2 18:00 local: 216 by surface teams in Districts 3 and 4
        a, b = local_ts(1, "15:00"), local_ts(2, "18:00")
        self.surface(a + 600, local_ts(1, "23:00"), 30, tf1, D34, n_missions=5, dur=(1.4, 2.2))
        self.surface(local_ts(2, "00:10"), b, 90, tf1, D34, n_missions=12, dur=(1.5, 2.8))
        self.surface(a, b, 70, boats, D34, per=(3, 6))
        self.surface(local_ts(2, "06:30"), b, 26, hwv + arng, {k: v for k, v in D34.items()}, n_missions=9, dur=(1.0, 1.8),
                     method="HIGH-WATER VEHICLE", single_event=True)
        # --- D+2 18:00 local to midnight: 207
        a, b = local_ts(2, "18:00"), local_ts(3, "00:00")
        self.surface(a, b, 110, tf1, D34, n_missions=10, dur=(1.6, 2.6))
        self.surface(a, b, 70, boats, D34, per=(4, 7))
        self.surface(a, b, 27, arng, D34, n_missions=9, dur=(1.0, 1.7), method="HIGH-WATER VEHICLE", single_event=True)
        # --- D+3 to D+5 17:00 local: ground and boat primary, 87 civilian boats (EVT-1705)
        plan = [(3, "06:30", "20:30", 106, 55, 40, 29, 0, civ[:40]), (4, "06:30", "20:30", 80, 40, 20, 10, 20, civ[40:70]),
                (5, "06:30", "17:00", 46, 23, 10, 14, 25, civ[70:])]
        for d, t0, t1, n_civ, n_cc, n_tf, n_hw, n_amb, civ_set in plan:
            a, b = local_ts(d, t0), local_ts(d, t1)
            self.surface(a, b, n_civ, civ_set, P4W, n_missions=len(civ_set), dur=(1.2, 2.4))
            self.surface(a, b, n_cc, boats, P4W, per=(3, 6))
            self.surface(a, b, n_tf, tf1, P4W, per=(4, 7))
            self.surface(a, b, n_hw, hwv + arng, P4LAND, n_missions=max(1, n_hw // 3), dur=(1.0, 1.8), method="HIGH-WATER VEHICLE", single_event=True)
            if n_amb:
                self.surface(a, b, n_amb, [(f"WC-{i}", "") for i in range(1, 9)], P4LAND, n_missions=max(1, n_amb // 2), dur=(0.7, 1.2),
                             method="AMBULATORY CONTACT", single_event=True)
        # --- number missions by launch, cases by on-scene time
        self.missions.sort(key=lambda m: (m["launch"], m["asset"]))
        for i, m in enumerate(self.missions):
            m["id"] = f"SARM-27-{i + 1:04d}"
        evs = sorted(((e, m) for m in self.missions for e in m["events"]), key=lambda x: (x[0]["t"], x[1]["id"]))
        n = 0
        for e, m in evs:
            e["cases"] = [f"SAR-27-{n + k + 1:05d}" for k in range(e["persons"])]
            n += e["persons"]
        assert n == 1427, n
        self.events = evs
        self.assign_deliveries()


# ======================================================================================
# day plans
# ======================================================================================
WEEKDAY = [0.98, 0.98, 0.99, 0.99, 1.05, 1.06, 0.95]
FIXED = {0: 1841, 1: 2900, 2: 2600, 3: 1912, 4: 1688, 5: 1517, 6: 1363, 7: 1580, 8: 1490, 9: 1463, 10: 1409, 11: 1388, 12: 1623,
         28: 380, 45: 311, -4: 337, -3: 394, -2: 476, -1: 547}       # D+3..6 average 1,620 and D+9..11 average 1,420 as canon states
BUSY_DAYS = {-8: 1.10, -7: 1.08, 39: 1.05, 42: 1.04, 44: 1.09, 47: 1.12, 72: 1.07, 73: 1.05, 102: 0.90, 108: 1.16, 109: 1.08}   # holidays, the D-7 rain, lift days, the blast
SAR_TAGS = {0: 1100, 1: 1900, 2: 2109, 3: 1150, 4: 800, 5: 450, 6: 150}
HOURLY = np.array([2.6, 2.1, 1.8, 1.5, 1.4, 1.6, 2.4, 3.5, 4.3, 4.6, 4.8, 5.0, 5.2, 5.2, 5.3, 5.6, 5.9, 6.0, 5.8, 5.4, 5.0, 4.4, 3.8, 3.2])
D0_HOURS = [40, 48, 67, 81, 94, 90, 83, 76, 78, 80, 84, 88, 90, 90, 88, 86, 84, 82, 78, 74, 70, 66, 63, 61]


def daily_target(d):
    if d in FIXED:
        return FIXED[d]
    rg = rng("ground", "volume", d)
    wd = local_dt(local_ts(d, "12:00")).weekday()
    wk = 1 + (WEEKDAY[wd] - 1) * 0.9
    if 13 <= d <= 27:                                   # declining from about 1,400 to about 390
        v = 1400 * (390 / 1400) ** ((d - 13) / 14)
        if d == 13:
            return int(round(v + rg.integers(-18, 19)))
        if d == 27:
            return int(round(v + rg.integers(-9, 10)))
        return int(round(v * (1 + (wk - 1) * 0.6) * (1 + rg.normal(0, 0.04))))
    if 29 <= d <= 44:
        v = 372 - (d - 29) * (372 - 316) / 15
        return int(round(v * wk * BUSY_DAYS.get(d, 1.0) * (1 + rg.normal(0, 0.035))))
    base = 310 if d < 0 else 302 + min(8, (d - 46) * 0.12)
    return int(round(base * WEEKDAY[wd] * BUSY_DAYS.get(d, 1.0) * (1 + rg.normal(0, 0.04))))


def hour_counts(d, n, rg):
    if d == 0:
        return list(D0_HOURS)
    w = HOURLY.copy()
    if 1 <= d <= 11:
        w = 0.5 * w + 0.5 * w.mean()
    if d not in (0, -1, 12):                            # no two days have the same shape
        wd = local_dt(local_ts(d, "12:00")).weekday()
        w = w * np.exp(rg.normal(0, 0.11, 24))
        if wd in (4, 5):                                # Friday and Saturday nights run late
            w[[21, 22, 23]] *= 1.25
        if wd in (5, 6):                                # weekend mornings start slowly, the small hours are busier
            w[[6, 7, 8]] *= 0.78
            w[[0, 1, 2]] *= 1.3
    fixed = {}
    if d == -1:
        fixed = {19: 14, 20: 17, 21: 21, 22: 26, 23: 31}
    rest = n - sum(fixed.values())
    idx = [h for h in range(24) if h not in fixed]
    p = np.array([w[h] for h in idx]); p = p / p.sum()
    alloc = np.floor(p * rest).astype(int)
    for k in np.argsort(-(p * rest - alloc))[: rest - alloc.sum()]:
        alloc[k] += 1
    out = [0] * 24
    for h, a in zip(idx, alloc):
        out[h] = int(a)
    for h, a in fixed.items():
        out[h] = a
    return out


def mix_for(d):
    if d <= -5:
        return {"med": .37, "traffic": .13, "police": .31, "fire": .06, "welfare": .07, "util": .03, "struct": .02, "water": .01}
    if d <= -1:
        return {"med": .31, "traffic": .16, "police": .30, "fire": .05, "welfare": .10, "util": .04, "struct": .03, "water": .01}
    if d == 0:
        return {"med": .38, "water": .27, "fire": .19, "traffic": .09, "police": .03, "struct": .04}
    if d == 1:
        return {"water": .52, "med": .22, "fire": .08, "struct": .08, "util": .05, "police": .03, "welfare": .02}
    if d == 2:
        return {"water": .70, "med": .14, "struct": .06, "util": .04, "fire": .03, "police": .03}
    if d <= 6:
        wv = {3: .35, 4: .28, 5: .20, 6: .15}[d]
        return {"water": wv, "med": .27, "util": .14, "struct": .12, "welfare": .06, "fire": .04, "police": .05, "traffic": .02}
    if d <= 11:
        return {"med": .30, "util": .20, "struct": .12, "welfare": .13, "water": .07, "police": .10, "fire": .04, "traffic": .04}
    if d == 12:
        return {"med": 471, "util": 292, "welfare": 179, "water": 6, "police": 70, "traffic": 35, "struct": 25, "fire": 15}
    if d <= 42:
        f = (d - 13) / 29.0
        wsi = .22 - .19 * f
        util = .16 - .12 * f
        return {"med": .31, "wsi": wsi, "util": util, "welfare": .10 - .03 * f, "struct": .07 - .05 * f, "police": .12 + .16 * f,
                "traffic": .05 + .07 * f, "fire": .04 + .01 * f, "water": .01}
    return {"med": .36, "traffic": .13, "police": .30, "fire": .06, "welfare": .08, "util": .04, "struct": .02, "water": .01}


def allocate(mix, n, rg):
    """Exact counts per group for n incidents."""
    keys = list(mix)
    p = np.array([max(0.0, mix[k]) for k in keys], float); p = p / p.sum()
    a = np.floor(p * n).astype(int)
    for k in np.argsort(-(p * n - a))[: n - a.sum()]:
        a[k] += 1
    out = []
    for k, c in zip(keys, a):
        out += [k] * int(c)
    return [out[i] for i in rg.permutation(len(out))]


# ======================================================================================
# the run
# ======================================================================================
MED_CODES = {"MEDEMER", "TRAUMAALS", "TRAUMABLS", "CARDIACAR", "STROKECVA", "MEDTRANSPT", "GENERCOP"}
FIRE_CODES = {"STRUCTFIRE", "GASLEAK", "ALARMBLDG", "FIREINVEST", "GRASSFIRE", "FUELSPILL", "HAZMATLVL1", "DWNPWRLINE", "OVERTURNED",
              "ROOFCOLLAP", "TREEFALLER", "UTILEMER", "GENERHAZ", "URBANSAR", "TRAPPEDVEH", "WATERRESC", "FLOODING", "EXPLOSION", "SURFRESC"}
D34_ZIPS = {"78405", "78416", "78417", "78401", "78407", "78408"}
DRONE_NIGHTS = [1, 2, 4, 6, 8, 10]
LANG_ES = 0.543
LOWINC = lambda d: 2.0 if d <= 14 else 1.82          # extra drive time on storm-damaged streets in the low-income surge tracts
FALSE_SCRIPT = {   # the callers read nearly the same words; call takers type them a little differently each time
    "trapped": ["RP STATES ELDERLY {s} IS TRAPPED IN FLOODED HOUSE AT THIS ADDRESS AND NEEDS RESCUE IMMEDIATELY",
                "RP STATES ELDERLY {s} TRAPPED IN FLOODED HOUSE AT THIS ADDRESS NEEDS RESCUE IMMEDIATELY",
                "CALLER STATES AN ELDERLY {s} IS TRAPPED IN A FLOODED HOUSE AT THIS ADDRESS NEEDS RESCUE IMMED"],
    "collapse": ["RP STATES THE BUILDING HAS COLLAPSED AT THIS ADDRESS AND PERSONS ARE TRAPPED INSIDE NOW",
                 "RP STATES BUILDING HAS COLLAPSED AT THIS ADDRESS PERSONS TRAPPED INSIDE NOW",
                 "CALLER STATES THE BUILDING COLLAPSED AT THIS ADDRESS AND PERSONS ARE TRAPPED INSIDE NOW"],
    "gas": ["RP STATES THERE IS A STRONG GAS LEAK AT THIS ADDRESS AND PEOPLE ARE IN DANGER NOW",
            "RP STATES STRONG GAS LEAK AT THIS ADDRESS PEOPLE ARE IN DANGER NOW",
            "CALLER STATES THERE IS A STRONG GAS LEAK AT THIS ADDRESS AND PEOPLE IN DANGER NOW"],
}


class Run:
    def __init__(self):
        self.sim = Sim()
        self.sar = Sar(self.sim)
        self.rows = []
        self.meta = []            # per-row internals for statistics: (t, day, tract, response_seconds, group)
        self.asset_log = []
        self.sar_extra = []       # no-find cases
        self.prepare_specials()

    # ------------------------------------------------------------------ fixed-in-advance incidents
    def special(self, inc):
        self.sim.pending_special[day_of(inc["t"])].append(inc)

    def prepare_specials(self):
        sim = self.sim
        rg = rng("ground", "specials")
        units = sim.units
        # 1. calls behind every rescue
        first_call = Z(0, "06:08")
        for e, m in self.sar.events:
            t = e["t"]
            if e.get("persons_note") == "first":
                rec = first_call
            else:
                if t < local_ts(1, "00:00"):
                    wait = rg.uniform(25, 150) * 60
                elif t < local_ts(2, "00:00"):
                    wait = rg.uniform(1.5, 9) * H
                elif t < local_ts(3, "00:00"):
                    wait = rg.uniform(2, 12) * H
                else:
                    wait = rg.uniform(0.7, 8) * H
                rec = max(t - wait, first_call + rg.uniform(120, 2400))
                rec = min(rec, t - 15 * 60)
            air = m["type"] == "helicopter"
            disp = min(max(rec + rg.uniform(4, 12) * 60, m["launch"]), t - 120)
            clear = t + rg.uniform(10, 30) * 60
            n = e["persons"]
            tail = {"AIR": f"AIR ASSET TASKED VIA SAR BRANCH // {m['asset']} {n} RECOVERED", "HOIST": f"AIR ASSET TASKED VIA SAR BRANCH // {m['asset']} HOIST {n}",
                    "AIR-LANDING": f"AIR ASSET TASKED VIA SAR BRANCH // {m['asset']} LANDED {n} RECOVERED", "BOAT": f"{m['asset']} {n} PERSONS OUT BY BOAT",
                    "HIGH-WATER VEHICLE": f"{m['asset']} {n} PERSONS OUT HIGH WATER VEH", "AMBULATORY CONTACT": f"{m['asset']} CONTACT {n} WALKED OUT"}[e["method"]]
            code = ["WATERRESC", "FLOODING", "TRAPPEDVEH", "URBANSAR"][int(rg.choice(4, p=[.55, .3, .1, .05]))]
            if e["method"] == "AMBULATORY CONTACT":
                code = "WELFCHK" if rg.random() < 0.6 else "FLOODING"
            inc = {"t": int(rec), "group": "water", "code": code, "tract": e["tract"], "loc": e["loc"], "sar": True, "sar_case": e["cases"][0],
                   "priority": "P1", "tail": tail, "agency": "CCFD",
                   "fixed": {"unit": m["asset"] if m["asset"] in units else "", "disp": int(disp), "arr": int(t), "clear": int(clear),
                             "dispo": "ASSIST", "recovery": m["recovery"]}}
            if not m["asset"].startswith("TF1") and e["method"] == "BOAT" and t >= local_ts(1, "06:00") and rg.random() < 0.05:
                inc["extra_units"] = ["TF1-ALPHA" if rg.random() < 0.5 else "TF1-BRAVO"]
            e["inc"] = inc
            self.special(inc)
        n_h1 = sum(1 for e, m in self.sar.events if Z(0, "06:00") <= e["inc"]["t"] < Z(0, "07:00"))
        assert n_h1 <= 14, n_h1

        # 2. the D+7..D+10 calls near the two substations (canon EVT-1303, EVT-1304, EVT-1707)
        plan = [(7, "19:07", "GW-FAC-SUB-02", "gas"), (7, "19:26", "GW-FAC-SUB-03", "trapped"), (7, "19:48", "GW-FAC-SUB-02", "collapse"),
                (7, "20:15", "GW-FAC-SUB-02", "gas"), (7, "20:39", "GW-FAC-SUB-03", "gas"), (7, "21:10", "GW-FAC-SUB-02", "collapse"),
                (7, "21:42", "GW-FAC-SUB-03", "trapped"), (7, "22:21", "GW-FAC-SUB-02", "gas"), (7, "22:53", "GW-FAC-SUB-03", "collapse"),
                (8, "13:12", "GW-FAC-SUB-02", "trapped"), (8, "14:40", "GW-FAC-SUB-03", "gas"), (8, "16:05", "GW-FAC-SUB-02", "gas"),
                (8, "17:31", "GW-FAC-SUB-02", "trapped"), (8, "19:18", "GW-FAC-SUB-03", "trapped"), (8, "21:44", "GW-FAC-SUB-02", "gas"),
                (8, "23:02", "GW-FAC-SUB-03", "gas"),
                (9, "13:36", "GW-FAC-SUB-02", "trapped"), (9, "15:27", "GW-FAC-SUB-03", "gas"), (9, "17:49", "GW-FAC-SUB-02", "gas"),
                (9, "20:11", "GW-FAC-SUB-03", "trapped"), (9, "22:30", "GW-FAC-SUB-02", "gas"),
                (10, "12:20", "GW-FAC-SUB-02", "gas"), (10, "14:55", "GW-FAC-SUB-03", "trapped")]
        carriers = [PREPAID[0]] * 9 + [PREPAID[1]] * 8 + [PREPAID[2]] * 6
        carriers = [carriers[i] for i in rg.permutation(23)]
        langs = ["EN"] * 15 + ["ES"] * 8
        langs = [langs[i] for i in rg.permutation(23)]
        pools = {k: sim.g.locations_near(sim.sub[k], 385, 16, rng("ground", "near", k), min_m=35) for k in sim.sub}
        used = collections.Counter()
        tf1_div = {1: ("TF1-ALPHA", "Alpha-7", "19:30", "20:20"), 3: ("TF1-BRAVO", "Bravo-3", "20:20", "21:15"), 5: ("TF1-ALPHA", "Charlie-2", "21:15", "22:10"),
                   7: ("TF1-BRAVO", "Delta-5", "22:45", "23:45"), 9: ("TF1-ALPHA", "Alpha-4", "13:20", "14:10"), 12: ("TF1-BRAVO", "Bravo-6", "17:40", "18:35")}
        case = 1427
        t_d7 = Z(7, "19:00")
        for i, (d, hm, sub, kind) in enumerate(plan):
            t = Z(d, hm) + int(rg.integers(0, 50))
            loc = pools[sub][used[sub] % len(pools[sub])]; used[sub] += 1
            while True:
                ac = ["361", "361", "361", "512", "210", "956", "737", "830"][int(rg.integers(8))]
                num = f"{ac}-{int(rg.integers(200, 899)):03d}-{int(rg.integers(0, 10000)):04d}"
                if num not in sim.numbers:
                    break
            cls_f = "WPH2" if rg.random() < 0.7 else "WPH1"
            sim.numbers[num] = {"num": num, "cls": cls_f, "carrier": carriers[i], "plan": "PREPAID",
                                "act": int(t_d7 - rg.uniform(3, 70) * H), "registered": "N"}
            code = {"gas": "GASLEAK", "collapse": "ROOFCOLLAP", "trapped": "FLOODING" if rg.random() < 0.6 else "TRAPPEDVEH"}[kind]
            narr = FALSE_SCRIPT[kind][int(rg.integers(3))].format(s="MALE" if rg.random() < 0.5 else "FEMALE")
            if langs[i] == "ES":
                narr += " / SPANISH SPKR"
            inc = {"t": t, "group": "water" if kind != "gas" else "fire", "code": code, "loc": loc, "tract": sim.tract_of(loc["lat"], loc["lon"]), "priority": "P1", "narr": narr, "lang": langs[i],
                   "phone": (num, cls_f, carriers[i]), "duration": int(rg.integers(36, 58)), "force_pool": "welfare" if kind != "gas" else "fire",
                   "force_dispo": "UNFND", "tail": "UNITS ON SCENE NO EMERGENCY FOUND", "max_wait": 6 * H, "near_sub": sub, "no_dispatch": None}
            if kind != "gas":
                case += 1
                inc["sar"] = True
                inc["sar_case"] = f"SAR-27-{case:05d}"
            if i in tf1_div:
                unit, elem, a, b = tf1_div[i]
                inc["extra_units"] = [unit]
                inc["tf1"] = (unit, elem, Z(d, a), Z(d, b))
            self.special(inc)
        assert case == 1438
        # six genuine requests in District 4 that waited while teams were diverted (EVT-1303)
        d4 = [t for t in sim.tracts if sim.tracts[t]["name"] in ("Hillcrest", "Port/Channel S", "Port/Channel N", "Bayfront Downtown")]
        waits = [3.2, 3.9, 4.1, 4.4, 4.9, 5.3]
        for k, w in enumerate(waits):
            tr = d4[k % len(d4)]
            pool = sim.tracts[tr]["pool"]
            t = Z(7, "19:35") + int(k * 31 * 60 + rg.integers(0, 600))
            unit = "TF1-ALPHA" if k % 2 == 0 else "TF1-BRAVO"
            self.special({"t": t, "group": "water", "code": "FLOODING", "tract": tr, "loc": pool[int(rg.integers(len(pool)))], "sar": True, "priority": "P1",
                          "agency": "CCFD",
                          "fixed": {"unit": unit, "disp": int(t + w * H), "arr": int(t + w * H + rg.uniform(14, 26) * 60),
                                    "clear": int(t + w * H + rg.uniform(50, 85) * 60), "dispo": "ASSIST"},
                          "tail": "HELD FOR SAR BRANCH - NO UNITS AVAIL"})
        # 3. night calls about lights over the air station (EVT-0318)
        fb = [t for t in sim.tracts if sim.tracts[t]["name"] in ("Flour Bluff Shore", "Flour Bluff East", "Flour Bluff Central")]
        lights = ["RP RPTS LIGHTS HOVERING OVER NAS POSS DRONE", "SEVERAL LIGHTS MOVING SLOWLY OVER BASE NO SOUND", "RP FILMING LIGHTS OVER AIR STATION REQ OFFICER",
                  "LIGHTS HOVERING OVER DEPOT AREA", "RP SAYS DRONES OVER NAS AGAIN TONIGHT"]
        for d in DRONE_NIGHTS:
            for k in range(int(rg.integers(3, 7))):
                t = local_ts(d, "21:30") + int(rg.uniform(0, 5.0) * H)
                tr = fb[int(rg.integers(len(fb)))]
                pool = sim.tracts[tr]["pool"]
                self.special({"t": t, "group": "police", "code": "GENASSIST", "tract": tr, "loc": pool[int(rg.integers(len(pool)))],
                              "narr": lights[int(rg.integers(len(lights)))], "no_dispatch": "REFER" if rg.random() < 0.6 else None,
                              "tail": "REFERRED NAS SECURITY"})
        # 4. the explosion heard from Port Aransas at 01:10 local on D+44 (EVT-0413)
        t0 = ts(canon()["channel_attack"]["blast"]["when"]["utc"])
        pa_tr = sim.tract_by_name.get("East Flats")
        for k in range(11):
            t = t0 + int(20 + k * 150 + rg.integers(0, 90))
            self.special({"t": t, "group": "fire", "code": "EXPLOSION", "tract": pa_tr, "loc": sim.pool_pa_water[k % len(sim.pool_pa_water)], "priority": "P1",
                          "no_dispatch": None if k in (0, 2) else "DUP", "force_pool": "police_PAPD", "force_dispo": "REFER",
                          "tail": "USCG SECTOR NOTIFIED"})
        # the two injured crew are landed at the Port Aransas harbor by a response boat; two ambulances take them to hospital
        self.special({"t": t0 + int(rg.uniform(36, 41) * 60), "group": "med", "code": "TRAUMAALS", "tract": pa_tr, "loc": sim.pool_pa_water[11 % len(sim.pool_pa_water)],
                      "priority": "P1", "narr": "USCG REQ 2 ALS AT HARBOR 2 CREW FROM VESSEL BLAST INJ BURNS INBOUND BY BOAT", "lang": "EN",
                      "no_dispatch": None, "force_pool": "ems", "force_transport": True, "second_ems": True, "max_wait": 3 * H,
                      "tail": "2 PTS TRANSPORTED"})
        # 5. the boil-water evening on D+12 (EVT-1305): 140 questions entered as FLOODING, then the new category at 23:05Z
        notice = ts(canon()["alerts"]["items"][8]["release_en"]["utc"]) if False else local_ts(12, "17:30")
        newcat = Z(12, "23:05")
        self.newcat = newcat
        d34 = [t for t in sim.tracts if sim.tracts[t]["zip"] in D34_ZIPS]
        wd = np.array([sim.tracts[t]["pop"] for t in d34], float); wd /= wd.sum()
        q = NARR["WATERSAFE"]
        for k in range(140):
            t = notice + int((newcat - notice) * (k + rg.random()) / 140)
            tr = d34[int(rg.choice(len(d34), p=wd))]
            pool = sim.tracts[tr]["pool"]
            self.special({"t": t, "group": "water", "code": "FLOODING", "tract": tr, "loc": pool[int(rg.integers(len(pool)))], "priority": "P3",
                          "narr": q[int(rg.integers(len(q)))], "no_dispatch": "NOACT" if rg.random() < 0.5 else "REFER", "tail": "ADVISED BOIL WATER NOTICE"})
        end = local_ts(13, "00:00")
        for k in range(390):
            u = rg.random() ** 1.6                      # heaviest just after the notice
            t = newcat + int((end - newcat - 5) * u)
            tr = d34[int(rg.choice(len(d34), p=wd))] if rg.random() < 0.85 else sim.t_ids[int(rg.choice(len(sim.t_ids), p=sim.w_base))]
            pool = sim.tracts[tr]["pool"]
            self.special({"t": t, "group": "wsi", "code": "WATERSAFE", "tract": tr, "loc": pool[int(rg.integers(len(pool)))]})
        # 6. Portland requests handled by San Patricio mutual aid while the causeway is closed (EVT-0304)
        for d in range(0, 4):
            for k in range(12):
                t = local_ts(d, "06:40" if d == 0 else "00:10") + int(rg.uniform(0, 17 if d == 0 else 23.5) * H)
                if t >= BRIDGE_OPEN:
                    continue
                code = ["MEDEMER", "FLOODING", "DWNPWRLINE", "TREEFALLER", "WELFCHK", "TRAUMABLS"][int(rg.integers(6))]
                self.special({"t": t, "group": "med", "code": code, "tract": None, "loc": self.sim.pool_portland[int(rg.integers(len(self.sim.pool_portland)))],
                              "city": "PORTLAND", "zip": "78374", "beat": "", "portland": True})

    # ------------------------------------------------------------------ one incident
    def factor(self, d, tr, prio):
        f = 0.88 if prio in ("P1", "P2") else 1.05
        if tr is None:
            return f
        m = {0: 2.6, 1: 2.3, 2: 2.1, 3: 1.8, 4: 1.5, 5: 1.4, 6: 1.3}.get(d, 1.15 if 7 <= d <= 14 else 1.0)
        if tr["zone"] in ("A", "B"):
            f *= m
        elif tr["zone"] == "C":
            f *= 1 + (m - 1) * 0.4
        if tr["tract"] in self.sim.L and 0 <= d <= 45:
            f *= LOWINC(d)
        return f

    def commit(self, unit, inc_no, start, loc, factor, scene_min, rg, emergency, transport=False):
        """Send a unit: returns (arrival, cleared, destination id) and books it until back in quarters."""
        sim = self.sim
        tr = sim.travel(unit, loc, start)
        if tr is None:
            tr = 900.0
        arr = start + rg.uniform(50, 95) + tr * factor
        clear = arr + rg.uniform(*scene_min) * 60
        dest = t_dest = t_leave = None
        dest_id = ""
        t = clear
        cur = loc
        if transport:
            h = sim.nearest_hospital(loc, clear)
            if h is not None:
                t_dest = clear + h[0] * (1.0 if not emergency else 0.92)
                t_leave = t_dest + rg.uniform(14, 30) * 60
                dest, dest_id, cur, t = h[2], h[1], h[2], t_leave
        back = sim.g.travel_seconds(unit["home"], cur, sim.closed(t))
        t_home = t + (back if back is not None else 600) * 1.05
        if unit["avl"]:
            sim.avl_response(unit, inc_no, start, arr, clear, loc, dest, t_dest, t_leave, t_home, emergency)
        else:
            unit["busy"].append((start, t_home))
        unit["free"] = t_home
        return arr, (t_leave if dest is not None else clear), dest_id, dest is not None

    def process(self, inc, d, rg):
        sim = self.sim
        t = inc["t"]
        code = inc["code"]
        desc, prio, agencies = sim.nature[code]
        prio = inc.get("priority", prio)
        group = inc["group"]
        tr = sim.tracts.get(inc.get("tract"))
        loc = inc["loc"]
        surge = 0 <= d <= 12
        # caller
        if "lang" in inc:
            lang = inc["lang"]
        else:
            p_es = min(0.9, LANG_ES * (tr["hisp"] if tr else 0.5))
            r = rg.random()
            lang = "ES" if r < p_es else ("OT" if r < p_es + 0.0108 else "EN")
        num, cls, carrier = sim.phone(rg, t, (loc["lat"], loc["lon"]) if surge and group in ("water", "struct", "util") else None, inc.get("phone"))
        dur = inc.get("duration") or int({"wsi": rg.uniform(35, 170), "police": rg.uniform(28, 200)}.get(group, rg.uniform(30, 260)))
        if d == 0 and 3 <= local_dt(t).hour <= 8:
            ans = rg.uniform(30, 420)
        elif 0 <= d <= 2:
            ans = rg.uniform(8, 120)
        elif 3 <= d <= 12:
            ans = rg.uniform(5, 40)
        else:
            ans = rg.uniform(3, 14)
        answered = t + ans
        ready = answered + rg.uniform(35, 100)
        unit_id, extra, dispo, dest_id = "", [], None, ""
        disp = arr = clear = None
        mutual = False
        agency = inc.get("agency")
        narr = inc.get("narr") or sim.narrative(code, rg, lang, d)
        fx = inc.get("fixed")
        number_agency = None
        if fx:
            unit_id, disp, arr, clear, dispo = fx["unit"], fx["disp"], fx["arr"], fx["clear"], fx["dispo"]
            answered = min(answered, disp - 30); ready = answered
            u = sim.units.get(unit_id)
            mutual = bool(u and u["agency"] in ("TF1", "TXARNG", "MA_FIRE", "MA_EMS"))
            number_agency = "CCFD"
            extra = list(inc.get("extra_units", []))
        else:
            nd = inc.get("no_dispatch", "__decide__")
            if nd == "__decide__":
                nd = self.no_dispatch(group, code, d, rg)
            if group == "wsi":
                nd = "REFER" if rg.random() < 0.7 else "NOACT"
            if nd:
                dispo = nd
            else:
                pool_name = inc.get("force_pool") or self.pool_for(code, group, tr, t, rg)
                pool = sim.ma_portland if inc.get("portland") else sim.pool[pool_name]
                fac = self.factor(d, tr, prio) * (2.2 if inc.get("portland") else 1.0)
                max_wait = inc.get("max_wait") or {"P1": 2.5, "P2": 4, "P3": 6, "P4": 8}[prio] * H
                if tr and tr["name"] in ("North Beach", "Rincon Point") and sim.closed(t):
                    max_wait = 14 * H               # cut off by the closed crossings: nobody else can come, so calls wait for the units on the island
                best = sim.pick_unit(pool, loc, ready, fac, max_wait)
                if best is None:
                    dispo = "REFER" if group in ("water", "util") else ("CANCEL" if rg.random() < 0.5 else "NOACT")
                    inc["tail"] = inc.get("tail") or ("HELD FOR SAR BRANCH - NO UNITS AVAIL" if group == "water" else "NO UNITS AVAIL - CALLER ADVISED")
                else:
                    _, u, start, _ = best
                    unit_id = u["id"]
                    number_agency = {"MA_FIRE": "MA_FIRE", "MA_EMS": "MA_EMS"}.get(u["agency"], u["agency"])
                    kind = "ems" if pool_name == "ems" else "water" if group == "water" else "welfare" if pool_name == "welfare" else \
                           "fire" if pool_name == "fire" else "police"
                    scene = {"ems": (10, 28), "fire": (15, 50), "police": (8, 40), "welfare": (10, 30), "water": (25, 80)}[kind]
                    if code == "STRUCTFIRE":
                        scene = (40, 120)
                    transport = kind == "ems" and (rg.random() < MED_TRANSPORT.get(code, 0.5) and not (code == "CARDIACAR" and rg.random() < 0.2)
                                                   or bool(inc.get("force_transport")))
                    inc_no = sim.next_number(number_agency)
                    inc["_no"] = inc_no
                    disp = start
                    arr, clear, dest_id, went = self.commit(u, inc_no, start, loc, fac, scene, rg, prio == "P1", transport)
                    mutual = u["agency"] in ("TF1", "TXARNG", "MA_FIRE", "MA_EMS")
                    dispo = inc.get("force_dispo") or self.dispo_for(kind, code, went, transport, rg)
                    if kind == "ems" and transport and not went:
                        inc["tail"] = "BRIDGE CLSD - PT HELD AT STATION AID POINT"
                        dispo = "TREATED"
                    # second units
                    more = []
                    if code == "STRUCTFIRE":
                        more = [("fire", 1), ("ems", 1)]
                    elif code in ("TRAFFICACC", "ASSAULT") and pool_name != "police_" + (tr["police"] if tr else "CCPD"):
                        more = [("police_" + (tr["police"] if tr else "CCPD"), 1)]
                    elif code == "CARDIACAR":
                        more = [("fire", 1)]
                    elif inc.get("second_ems"):
                        more = [("ems", 1)]
                    for pn, k in more:
                        b2 = sim.pick_unit([x for x in sim.pool[pn] if x["id"] != unit_id], loc, start, fac, 60)
                        if b2:
                            self.commit(b2[1], inc_no, b2[2], loc, fac, (scene[0], scene[0] + 8), rg, True, transport=pn == "ems" and bool(inc.get("second_ems")))
                            extra.append(b2[1]["id"])
                    for x in inc.get("extra_units", []):
                        extra.append(x)
        if inc.get("tf1"):
            unit, elem, a, b = inc["tf1"]
            self.asset_log.append([iso(a), unit, elem, "DISPATCHED", address(loc), inc.get("_no", ""), "SWIFTWATER TEAM REDIRECTED TO REPORTED ENTRAPMENT"])
            self.asset_log.append([iso(b), unit, elem, "AVAILABLE", address(loc), inc.get("_no", ""), "NOTHING FOUND AT LOCATION - RETURNED TO STAGING"])
            u = sim.units[unit]
            r = sim.g.route(u["home"], loc, False)
            if r is not None and u["free"] <= a:
                on = a + r[2][-1] * 1.0
                sim.avl_move(u, r, a, on, 30, "ENR", inc.get("_no", ""))
                sim.avl_park(u, loc, on, b - r[2][-1], "ONS", inc.get("_no", ""))
                sim.avl_move(u, (r[0][::-1], r[1][::-1], r[2][-1] - r[2][::-1]), b - r[2][-1], b, 60, "RTQ", "")
                u["busy"].append((a, b)); u["free"] = b
        if inc.get("sar_case") and not fx and unit_id:
            self.sar_extra.append((inc, unit_id, disp, arr, clear))
        if not inc.get("tail") and unit_id:
            r_t = rg.random()
            if dispo == "UNFND" and r_t < 0.75:
                inc["tail"] = "UNITS ON SCENE NO EMERGENCY FOUND" if r_t < 0.5 else "UNABLE TO LOCATE - GOA"
            elif dispo == "FALALRM" and r_t < 0.4:
                inc["tail"] = "ACCIDENTAL ACTIVATION"
        if inc.get("tail"):
            narr = narr + " // " + inc["tail"]
        if number_agency is None:      # nobody sent: number under the agency that owns the call type
            a0 = agencies[0] if agencies else "CCPD"
            number_agency = "CCEMS" if a0 == "CCEMS" else "CCFD" if a0 == "CCFD" else (tr["police"] if tr else "CCPD")
        if inc.get("portland"):
            mutual = True
        inc_no = inc.get("_no") or sim.next_number(number_agency)
        inc["_no"] = inc_no
        if fx and fx.get("unit") and sim.units.get(fx["unit"], {}).get("avl") and inc.get("sar_case"):
            self.sar_avl(inc, fx)
        ct = f"CT{int(rg.integers(1, 15)):02d}" if not (0 <= d <= 21 and rg.random() < 0.22) else ("SP-CT" if rg.random() < 0.6 else "BEE-CT") + f"{int(rg.integers(1, 5)):02d}"
        sar_flag = "Y" if inc.get("sar") else "N"
        f = lambda x: local_iso(x) if x else ""
        tract_id = tr["tract"] if tr else ""
        row = [inc_no, number_agency, f(t), f(answered), f(disp), f(arr), f(clear), prio, code, desc, address(loc), inc.get("city") or (tr["city"] if tr else "CORPUS CHRISTI"),
               "TX", inc.get("zip") or (tr["zip"] if tr else ""), inc["beat"] if "beat" in inc else (tr["beat"] if tr else ""), tract_id,
               f"{loc['lat']:.6f}", f"{loc['lon']:.6f}", unit_id, ";".join(extra), dispo, sim.dispo[dispo], narr, "true" if mutual else "false",
               sar_flag, inc.get("sar_case", ""), dest_id, "911" if cls != "TXT" else "TEXT", cls, carrier, num, lang, dur, ct]
        self.rows.append(row)
        self.meta.append((t, d, tract_id, (arr - t) if arr else None, group, ans, lang, unit_id))

    def sar_avl(self, inc, fx):
        """Breadcrumbs for a rescue mission by a road vehicle, when it does not overlap the unit's previous trip."""
        sim = self.sim
        u = sim.units[fx["unit"]]
        loc = inc["loc"]
        c = sim.closed(fx["disp"])
        out = sim.g.route(u["home"], loc, c)
        if out is None:
            return
        depart = max(fx["disp"], fx["arr"] - out[2][-1] * 1.5)
        if u["busy"] and u["busy"][-1][1] > depart:
            return
        back = fx["clear"] + out[2][-1] * 1.2
        sim.avl_move(u, out, depart, fx["arr"], 30, "ENR", inc["_no"])
        sim.avl_park(u, loc, fx["arr"], fx["clear"], "ONS", inc["_no"])
        sim.avl_move(u, (out[0][::-1], out[1][::-1], out[2][-1] - out[2][::-1]), fx["clear"], back, 60, "RTQ", "")
        u["busy"].append((depart, back))

    def no_dispatch(self, group, code, d, rg):
        dup = {0: .22, 1: .28, 2: .30, 3: .20, 4: .15, 5: .15, 6: .15}.get(d, .08 if 7 <= d <= 12 else .03)
        if group in ("water", "struct", "fire", "util", "traffic") and rg.random() < dup:
            return "DUP"
        if group == "med" and 0 <= d <= 6 and rg.random() < 0.04:
            return "DUP"
        surge = 0 <= d <= 11
        p = {"police": .16, "traffic": .06, "med": .03, "fire": .04, "welfare": .10, "util": .45, "struct": .40, "water": .05}.get(group, .1)
        if surge:
            p = {"util": .70, "struct": .60, "welfare": .35}.get(group, p)
        if rg.random() < p:
            if group == "util":
                return "REFER"
            if group == "struct":
                return "RPT"
            if group == "welfare":
                return "REFER"
            if group == "med":
                return "CANCEL"
            return ["RPT", "NOACT", "CANCEL"][int(rg.integers(3))]
        return None

    def pool_for(self, code, group, tr, t, rg):
        pol = "police_" + (tr["police"] if tr else "CCPD")
        if code in MED_CODES:
            return "ems"
        if code == "TRAFFICACC":
            return "ems" if rg.random() < 0.5 else pol
        if code in FIRE_CODES:
            return "fire"
        if code == "WELFCHK" and local_ts(6, "00:00") <= t < local_ts(21, "18:00") and rg.random() < 0.6:
            return "welfare"
        return pol

    def dispo_for(self, kind, code, went, transport, rg):
        r = rg.random()
        if kind == "ems":
            if went:
                return "TRNSPT"
            return "DOA" if code == "CARDIACAR" and r < 0.5 else "TREATED"
        if kind == "water":
            return "ASSIST" if r < 0.8 else ("NOACT" if r < 0.95 else "UNFND")
        if kind == "welfare":
            return "CLR" if r < 0.5 else ("ASSIST" if r < 0.85 else "NOACT")
        if kind == "fire":
            if code == "STRUCTFIRE":
                return "RPT"
            if code == "GASLEAK":
                return "ASSIST" if r < 0.6 else ("UNFND" if r < 0.75 else "REFER")
            if code == "ALARMBLDG":
                return "FALALRM" if r < 0.7 else "NOACT"
            return "ASSIST" if r < 0.72 else ("NOACT" if r < 0.94 else "UNFND")
        if code == "ALARMSEC":
            return "FALALRM" if r < 0.8 else "RPT"
        if code == "ASSAULT":
            return "ARR" if r < 0.25 else ("RPT" if r < 0.88 else "UNFND")
        return "RPT" if r < 0.42 else ("CLR" if r < 0.68 else ("NOACT" if r < 0.86 else ("ASSIST" if r < 0.96 else "UNFND")))

    # ------------------------------------------------------------------ one day
    def run_day(self, d):
        sim = self.sim
        rg = rng("ground", "cad", d)
        N = daily_target(d)
        specials = sim.pending_special.get(d, [])
        n_rand = N - len(specials)
        assert n_rand >= 0, (d, N, len(specials))
        day0 = local_ts(d, "00:00")
        sp_h = collections.Counter(local_dt(s["t"]).hour for s in specials)
        if d in (0, -1):
            hc = hour_counts(d, N, rg)
            rand_h = [max(0, hc[h] - sp_h.get(h, 0)) for h in range(24)]
            diff = n_rand - sum(rand_h)
            h = 23
            while diff != 0:                      # settle rounding in the late hours
                if diff > 0:
                    rand_h[h] += 1; diff -= 1
                elif rand_h[h] > 0:
                    rand_h[h] -= 1; diff += 1
                h = h - 1 if h > 9 else 23
        else:
            rand_h = hour_counts(d, n_rand, rg)
        if d == 12:
            groups = allocate(mix_for(d), n_rand, rg)
        else:
            groups = allocate(mix_for(d), N, rg)
            for s in specials:
                gname = s["group"]
                if gname in groups:
                    groups.remove(gname)
                else:
                    groups.pop(int(rg.integers(len(groups))))
        times = []
        for h in range(24):
            times += sorted(day0 + h * H + int(x) for x in rg.integers(0, H, rand_h[h]))
        if d == 12:                       # the new category does not exist before 23:05Z
            pass
        incs = [{"t": t, "group": g} for t, g in zip(times, groups)]
        # D0: exactly fourteen rescue-priority calls in the first hour after landfall, Flour Bluff and North Beach (EVT-1702)
        forced_h1 = set()
        if d == 0:
            h1 = [i for i, x in enumerate(incs) if local_dt(x["t"]).hour == 1]
            h1.sort(key=lambda i: incs[i]["t"] < Z(0, "06:09"))       # the first rescue call is logged at 06:08Z
            s1 = sum(1 for s in specials if local_dt(s["t"]).hour == 1 and s.get("sar"))
            need = 14 - s1
            later = [i for i, x in enumerate(incs) if local_dt(x["t"]).hour >= 2 and x["group"] == "water"]
            for i in h1[:need]:
                if incs[i]["group"] != "water":
                    j = later.pop()
                    incs[j]["group"], incs[i]["group"] = incs[i]["group"], "water"
                forced_h1.add(i)
            for i in h1[need:]:
                if incs[i]["group"] == "water":
                    j = next(k for k, x in enumerate(incs) if local_dt(x["t"]).hour >= 2 and x["group"] != "water")
                    incs[j]["group"], incs[i]["group"] = "water", incs[j]["group"]
        # tracts
        T = sim.tracts
        fbnb = [t for t in T if T[t]["name"] in ("Flour Bluff Shore", "Flour Bluff Central", "Flour Bluff East", "North Beach", "Rincon Point")]
        n_L_needed = None
        if d == 1:
            n_L_needed = int(round(0.61 * N)) - sum(1 for s in specials if s.get("tract") in sim.L)
        if d == 2:
            water_total = sum(1 for x in incs if x["group"] == "water") + sum(1 for s in specials if s["group"] == "water")
            z_needed = int(round(0.61 * water_total)) - sum(1 for s in specials if s["group"] == "water" and s.get("tract") in sim.Z61)
            w_idx = [i for i, x in enumerate(incs) if x["group"] == "water"]
            z_set = set(w_idx[k] for k in rg.permutation(len(w_idx))[:max(0, z_needed)])
        if n_L_needed is not None:
            l_set = set(int(k) for k in rg.permutation(len(incs))[:max(0, n_L_needed)])
        s_L = None
        if d == 0 or d == 3:
            s_L = 0.58
        elif d > 3 and d <= 60:
            s_L = sim.base_L_share + (0.61 - sim.base_L_share) * math.exp(-(d - 3) / 9.0)
        d34 = [t for t in T if T[t]["zip"] in D34_ZIPS]
        for i, x in enumerate(incs):
            g = x["group"]
            if i in forced_h1:
                tr = fbnb[int(rg.integers(len(fbnb)))]
            elif d == 2 and g == "water":
                tr = sim.t_ids[int(rg.choice(len(sim.t_ids), p=sim.w_Z61 if i in z_set else sim.w_notZ61))]
            elif d == 1:
                tr = sim.t_ids[int(rg.choice(len(sim.t_ids), p=sim.w_L if i in l_set else sim.w_notL))]
            elif d == 2:
                tr = sim.t_ids[int(rg.choice(len(sim.t_ids), p=sim.w_L if rg.random() < 0.5 else sim.w_notL))]
            elif g == "wsi" and rg.random() < 0.8:
                tr = d34[int(rg.integers(len(d34)))]
            elif s_L is not None:
                tr = sim.t_ids[int(rg.choice(len(sim.t_ids), p=sim.w_L if rg.random() < s_L else sim.w_notL))]
            else:
                tr = sim.t_ids[int(rg.choice(len(sim.t_ids), p=sim.w_base))]
            x["tract"] = tr
            pool = T[tr]["pool"]
            x["loc"] = pool[int(rg.integers(len(pool)))]
            x["code"] = pick_code(g, d, x["t"], rg)
            if i in forced_h1:
                x["code"] = "WATERRESC" if rg.random() < 0.6 else "FLOODING"
                x["sar"] = True
            elif d == 0 and local_dt(x["t"]).hour <= 1 and g == "water":
                x["code"] = "FLOODING"
        # rescue-priority tags
        if d in SAR_TAGS:
            have = sum(1 for s in specials if s.get("sar")) + len(forced_h1)
            order = {"water": 0, "struct": 1, "med": 2, "fire": 3}
            cand = [i for i, x in enumerate(incs) if i not in forced_h1 and x["group"] in order and not (d == 0 and local_dt(x["t"]).hour <= 1)]
            cand.sort(key=lambda i: (order[incs[i]["group"]], rg.random()))
            for i in cand[: max(0, SAR_TAGS[d] - have)]:
                incs[i]["sar"] = True
        elif 7 <= d <= 10:
            for x in incs:
                if x["code"] in ("WATERRESC", "TRAPPEDVEH", "URBANSAR"):
                    x["sar"] = True
        allinc = sorted(incs + specials, key=lambda x: x["t"])
        for x in allinc:
            self.process(x, d, rg)
        return N


# ======================================================================================
# vehicles that are not answering calls: evacuation buses, the task-force convoy, heartbeats
# ======================================================================================
def emit_buses(sim):
    g = sim.g
    rg = rng("ground", "buses")
    T = sim.tracts
    stops = []
    for name in ("North Beach", "Rincon Point", "Hillcrest", "Molina", "Flour Bluff Shore", "Bayfront Downtown", "Port/Channel S", "Westside CC"):
        pool = T[sim.tract_by_name[name]]["pool"]
        stops.append((name, pool[int(rg.integers(len(pool)))]))
    shelters = ["FAC-SHLT-007", "FAC-SHLT-006", "FAC-SHLT-026", "FAC-SHLT-027", "FAC-SHLT-028"]
    cap = {f: sim.fac[f]["shelter"]["capacity"] for f in shelters}
    want = {d: {f: max(0, shelter_base(f, cap[f], d) - shelter_base(f, cap[f], d - 1)) for f in shelters} for d in (-2, -1)}
    log = []
    buses = [u for u in sim.units.values() if u["type"] == "evacuation_bus"]
    for bi, bus in enumerate(buses):
        for day, t_start, t_stop in ((-2, "07:10", "20:30"), (-1, "05:45", "16:45")):
            t = local_ts(day, t_start) + bi * 7 * 60
            stop_at = local_ts(day, t_stop)
            cur = bus["home"]
            first = t
            k = bi
            route_id = f"EVAC-{'A' if day == -2 else 'ABC'}-{bi + 1:02d}"
            while t < stop_at:
                name, stop = stops[k % len(stops)]; k += 1
                open_now = [f for f in shelters if want[day][f] > 0 and shelter_open_ts(f) < t + 3 * H]
                wts = np.array([want[day][f] for f in open_now], float)
                sh_id = open_now[int(rg.choice(len(open_now), p=wts / wts.sum()))]
                sh = sim.shelter[sh_id]
                r1 = g.route(cur, stop, False)
                r2 = g.route(stop, sh, False)
                if r1 is None or r2 is None:
                    continue
                a1 = t + r1[2][-1] * 1.25
                sim.avl_move(bus, r1, t, a1, 30, "ENR", route_id)
                load = rg.uniform(12, 22) * 60
                a2 = a1 + load + r2[2][-1] * 1.3
                if a2 < shelter_open_ts(sh_id) + 240:            # the bus holds at the stop until the shelter is ready to receive
                    hold = shelter_open_ts(sh_id) + rg.uniform(240, 1100) - a2
                    load += hold; a2 += hold
                sim.avl_park(bus, stop, a1, a1 + load, "LOAD", route_id)
                sim.avl_move(bus, r2, a1 + load, a2, 30, "TRN", route_id)
                unload = rg.uniform(8, 14) * 60
                sim.avl_park(bus, sh, a2, a2 + unload, "UNLD", route_id)
                log.append([int(a1), bus["id"], name, sh_id, int(a2), day])
                t = a2 + unload
                cur = sh
            r = g.route(cur, bus["home"], False)
            if r is not None:
                sim.avl_move(bus, r, t, t + r[2][-1] * 1.2, 60, "RTQ", "")
                t = t + r[2][-1] * 1.2
                sim.avl_write(bus, int(t), *sim.park_pos(bus["home"], True), 0, 0, "AIQ", "")
            bus["busy"].append((first, t))
    # riders: buses bring about three in five of each day's evacuees to a shelter; the rest drive or walk in
    for day in (-2, -1):
        for f in shelters:
            trips = [x for x in log if x[3] == f and x[5] == day]
            if not trips:
                continue
            total = min(int(round(0.62 * want[day][f])), 40 * len(trips))
            w = rg.uniform(0.45, 1.6, len(trips))
            riders = np.minimum(46, np.maximum(2, np.round(total * w / w.sum()))).astype(int)
            for x, n in zip(trips, riders):
                x.append(int(n))
    return log


def emit_convoy(sim):
    """Texas Task Force 1 convoy arriving at the Robstown staging area at 18:47 local on D-1 (EVT-1701).
    Only the part of the drive inside the reference road network is logged."""
    g = sim.g
    best = None
    for u, nb in g.R.adj.items():
        for v, (cost, w, name, cls) in nb.items():
            if name.replace(" ", "") in ("I-37", "IH37") and g.R.in_main[u]:
                lat = g.R.nodes[u][0]
                if best is None or lat > best[0]:
                    best = (lat, u)
    if best is None:
        return None
    start = {"node": best[1], "rlat": g.R.nodes[best[1]][0], "rlon": g.R.nodes[best[1]][1]}
    arrive = local_ts(-1, "18:47")
    for k, uid in enumerate(("TF1-ALPHA", "TF1-BRAVO")):
        u = sim.units[uid]
        r = g.route(start, u["home"], False)
        if r is None:
            continue
        t1 = arrive + k * 90
        t0 = t1 - r[2][-1] * 1.1
        sim.avl_move(u, r, t0, t1, 30, "ENR", "TF1-CC-0913")
        sim.avl_write(u, int(t1), *sim.park_pos(u["home"], True), 0, 0, "STG", "TF1-CC-0913")
        u["busy"].append((t0, t1))
        u["from_hb"] = t1
    return arrive


def emit_heartbeats(sim):
    step = 6 * H
    for u in sim.units.values():
        if not u["avl"]:
            continue
        busy = sorted(u["busy"])
        starts = [b[0] for b in busy]
        lo = max(SPAN_START, u.get("from_hb", u["from"] if u["from"] else SPAN_START))
        hi = min(SPAN_END, u["to"])
        t = SPAN_START
        while t < SPAN_END:
            if lo <= t < hi:
                i = bisect.bisect_right(starts, t) - 1
                if i < 0 or busy[i][1] <= t:
                    sim.avl_write(u, t, *sim.park_pos(u["home"], True), 0, 0, "AIQ", "")
            t += step


def flush_avl(sim, ckdir):
    """Move buffered AVL rows to part files in the checkpoint directory (resumable runs)."""
    for (month, agency), rows in sim.avl_buf.items():
        if rows:
            with open(os.path.join(ckdir, f"avl_{month}_{agency}.part"), "a", encoding="utf-8") as f:
                f.write("\n".join(rows) + "\n")
    sim.avl_buf.clear()


def sort_avl(sim, ckdir=None):
    total = 0
    keys = set(sim.avl_buf)
    if ckdir:
        for fp in glob.glob(os.path.join(ckdir, "avl_*.part")):
            month, agency = os.path.basename(fp)[4:-5].split("_", 1)
            keys.add((month, agency))
    for (month, agency) in sorted(keys):
        rows = list(sim.avl_buf.get((month, agency), []))
        part = os.path.join(ckdir, f"avl_{month}_{agency}.part") if ckdir else None
        if part and os.path.exists(part):
            with open(part, encoding="utf-8") as f:
                rows += f.read().splitlines()
        rows.sort()
        with open(out_path(f"05_other_sources/avl/avl_{month}_{agency}.csv"), "w", encoding="utf-8", newline="") as f:
            f.write(",".join(AVL_HEADER) + "\n")
            f.write("\n".join(rows) + "\n")
        total += len(rows)
    return total


# ======================================================================================
# reports and SAR files
# ======================================================================================
def write_reports(run, counts):
    sim = run.sim
    rg = rng("ground", "reports")
    days = list(range(FIRST_DAY, LAST_DAY + 1))
    s28 = sum(counts[d] for d in range(0, 29)); s45 = sum(counts[d] for d in range(29, 46))
    A1, A2 = 44291 - s28, 56793 - 44291 - s45
    def admin_raw(d):
        """Ten-digit (non-emergency and agency) line calls: weekday business pattern, quiet in the first
        days of the storm when people dial 911, busier than usual through the recovery."""
        g2 = rng("ground", "admin", d)
        wd = local_dt(local_ts(d, "12:00")).weekday()
        wk = 1.08 if wd < 5 else 0.78
        if d < -4:
            base = 345
        elif d < 0:
            base = 345 + (d + 5) * 22
        elif d <= 4:
            base = [150, 205, 250, 285, 310][d]
            wk = 1 + (wk - 1) * 0.3
        elif d <= 28:
            base = 310 + (d - 4) * 3.4
        elif d <= 45:
            base = 392 - (d - 29) * 0.4
        else:
            base = max(348, 386 - (d - 45) * 2.4)
        return base * wk * (1 + g2.normal(0, 0.055))

    def fit(day_list, total):
        raw = np.array([admin_raw(d) for d in day_list])
        v = np.floor(raw * total / raw.sum()).astype(int)
        order = np.argsort(-(raw * total / raw.sum() - v))
        for k in order[: total - v.sum()]:
            v[k] += 1
        return v
    a1 = fit(list(range(0, 29)), A1)
    a2 = fit(list(range(29, 46)), A2)
    ma = np.array([max(0.0, 1.0 - d / 22.0) ** 1.3 * (1.6 if d <= 3 else 1.0) for d in range(0, 22)]); ma = ma / ma.sum() * 2140
    ma_h = np.floor(ma).astype(int); ma_h[0] += 2140 - ma_h.sum()
    by_day = collections.defaultdict(list)
    disp_day = collections.Counter()
    for (t, d, tract, resp, group, ans, lang, unit) in run.meta:
        by_day[d].append(ans)
        if unit:
            disp_day[d] += 1
    rows = []
    for d in days:
        if 0 <= d <= 28:
            admin = int(a1[d])
        elif 29 <= d <= 45:
            admin = int(a2[d - 29])
        else:
            admin = int(round(admin_raw(d)))
        ans = np.array(by_day[d]) if by_day[d] else np.array([6.0])
        rows.append([(local_dt(local_ts(d, "12:00"))).strftime("%Y-%m-%d"), counts[d], admin, counts[d] + admin, disp_day[d],
                     f"{np.median(ans):.0f}", f"{np.percentile(ans, 90):.0f}", int(ma_h[d]) if 0 <= d <= 21 else 0,
                     14 if 0 <= d <= 6 else 10 if 7 <= d <= 21 else 6])
    write_csv("05_other_sources/911/reports/cbecc_daily_call_volume.csv",
              ["date_local", "calls_911", "calls_ten_digit_lines", "calls_all_lines", "incidents_with_unit", "median_answer_sec",
               "p90_answer_sec", "mutual_aid_dispatcher_hours", "positions_staffed"], rows)
    # queue depth (pending calls and unassigned incidents), every 15 minutes through the surge
    q = []
    t = Z(0, "00:00")
    peak_t = Z(0, "10:30")
    while t <= Z(3, "05:00"):
        h = (t - LANDFALL) / H
        if h < 0:
            v = 2 + 3 * max(0, 1 + h / 6)
        elif t <= peak_t:
            v = 6 + (180 - 6) * ((t - LANDFALL) / (peak_t - LANDFALL)) ** 1.2
        else:
            hh = (t - peak_t) / H
            v = 38 + 142 * math.exp(-hh / 3.2) + 82 * math.exp(-((hh - 26.5) / 5.0) ** 2) + 60 * math.exp(-((hh - 50) / 6.0) ** 2)
        v = 180 if t == peak_t else min(176, v + rg.uniform(-2, 2))
        q.append([iso(t), int(round(max(0, v)))])
        t += 900
    write_csv("05_other_sources/911/reports/cbecc_queue_depth.csv", ["time_utc", "pending_calls_and_unassigned_incidents"], q)
    # shift log
    lang = collections.Counter(m[6] for m in run.meta if 0 <= m[1] <= 45)
    n45 = sum(lang.values())
    log = [
        [iso(Z(-5, "14:00")), "CBECC SHIFT SUPERVISOR", "IPAWS REQUIRED TEST RECEIVED ON ALL CONSOLES. NO ACTION."],
        [iso(Z(-1, "18:10")), "CBECC DIRECTOR", "SURGE STAFFING PLAN REVIEWED WITH ALL SHIFTS. LEAVE CANCELLED THROUGH FURTHER NOTICE."],
        [iso(Z(0, "06:15")), "CBECC DIRECTOR", "Activating surge protocol. Calling in Delta shift. Requesting mutual aid San Patricio and Bee County."],
        [iso(Z(0, "06:15") + 240), "CBECC SHIFT SUPERVISOR", "GROUND UNITS HOLDING IN QUARTERS PER FIRE CHIEF UNTIL WINDS DROP. CALLS BEING STACKED BY PRIORITY."],
        [iso(Z(0, "10:30")), "CBECC SHIFT SUPERVISOR", "QUEUE AT 180 PENDING. ALL POSITIONS STAFFED."],
        [iso(local_ts(0, "06:30")), "CBECC SHIFT SUPERVISOR", "GROUND UNITS RELEASED FROM QUARTERS. WORKING STACK."],
        [iso(Z(0, "15:40")), "CBECC DIRECTOR", "MUTUAL AID CALL TAKERS FROM SAN PATRICIO AND BEE COUNTY ON CONSOLES."],
        [iso(local_ts(2, "00:20")), "CBECC DIRECTOR", f"YESTERDAY TOTAL {counts[1]} CALLS. HIGHEST DAILY VOLUME ON RECORD."],
        [iso(local_ts(3, "00:20")), "CBECC DIRECTOR", f"YESTERDAY TOTAL {counts[2]} CALLS OF WHICH 2109 RESCUE REQUESTS. MOST RESCUE CALLS IN ONE DAY."],
        [iso(Z(12, "23:05")), "CAD ADMINISTRATOR", "NEW NATURE CODE WATER-SAFETY-INQUIRY CREATED. 140 CALLS SINCE THE BOIL WATER NOTICE WERE ENTERED AS FLOODING."],
        [iso(Z(13, "00:00")), "CBECC DIRECTOR", "NUECESINFOLINE ACTIVATED FOR NON-EMERGENCY WATER QUESTIONS. CALL TAKERS TO REFER."],
        [iso(Z(13, "02:00")), "CBECC SHIFT SUPERVISOR", "INFOLINE REPORTS 847 CALLS ANSWERED IN FIRST TWO HOURS."],
        [iso(local_ts(28, "19:00")), "CBECC DIRECTOR", f"VOLUME TODAY {counts[28]} CALLS, NEAR NORMAL. AFTER-ACTION SUMMARY: 44,291 CALLS ON ALL LINES SINCE LANDFALL. "
                                                         "CBECC dispatchers handled the highest sustained call volume in agency history. Mutual aid from San Patricio and Bee County provided "
                                                         "2,140 dispatcher-hours of support. Thirteen dispatchers required EAP counseling referrals for occupational stress."],
        [iso(local_ts(45, "19:00")), "CBECC DIRECTOR", f"SURGE POSTURE CLOSED. RETURN TO STANDARD STAFFING. CALL RECORDS 09/14 THROUGH 10/29 ARCHIVED WITH COUNTY IT FOR AFTER-ACTION REVIEW AND "
                                                         f"DISPATCHER TRAINING: 56,793 CALLS ON ALL LINES; ENGLISH 64.8 PCT SPANISH 34.1 PCT OTHER 1.1 PCT. TODAY {counts[45]} CALLS. "
                                                         "FALSE REPORT TIP LINE 1-800-NUECES-9 ANNOUNCED."],
    ]
    log.sort()
    write_csv("05_other_sources/911/reports/cbecc_shift_log.csv", ["time_utc", "author", "entry"], log)
    subs = sorted(sim.numbers.values(), key=lambda r: r["num"])
    write_csv("05_other_sources/911/reports/ali_subscriber_records.csv",
              ["callback_number", "class_of_service", "carrier", "service_plan", "activation_date", "subscriber_registered"],
              ([r["num"], r["cls"], r["carrier"], r["plan"], iso(r["act"])[:10], r["registered"]] for r in subs))
    return {"admin_d0_28": int(A1), "admin_d29_45": int(A2), "lang": {k: round(100 * v / n45, 1) for k, v in lang.items()}}


def write_sar(run):
    sim, sar = run.sim, run.sar
    rows = []
    for e, m in sar.events:
        tr = sim.tracts[e["tract"]]
        for c in e["cases"]:
            rows.append([c, m["id"], m["agency"], m["asset"], m["type"], m["element"], iso(m["launch"]), iso(e["t"]), iso(m["recovery"]),
                         f"{e['loc']['lat']:.6f}", f"{e['loc']['lon']:.6f}", address(e["loc"]), tr["tract"], 1, e["method"], "RESCUED",
                         e["delivered"], e["inc"].get("_no", ""), iso(e["deliv_t"])])
    n = len(sar.missions)
    for inc, unit, disp, arr, clear in sorted(run.sar_extra, key=lambda x: x[0]["sar_case"]):
        n += 1
        rows.append([inc["sar_case"], f"SARM-27-{n:04d}", "CCFD", unit, "welfare_check_team", "", iso(disp), iso(arr), iso(clear),
                     f"{inc['loc']['lat']:.6f}", f"{inc['loc']['lon']:.6f}", address(inc["loc"]), "", 0, "WELFARE CHECK", "NO VICTIM FOUND", "", inc["_no"], ""])
    write_csv("05_other_sources/sar/sar_missions.csv", SAR_HEADER, rows)
    # asset log
    log = []
    log.append([iso(local_ts(-1, "14:22")), "TF1-ALPHA", "", "DEPARTED", "SAN ANTONIO", "", "CONVOY TF1-CC-0913 4 VEHICLES EN ROUTE ROBSTOWN STAGING"])
    log.append([iso(local_ts(-1, "18:47")), "TF1-ALPHA", "", "STAGED", "RICHARD M. BORCHARD REGIONAL FAIRGROUNDS ROBSTOWN", "", "CONVOY TF1-CC-0913 ARRIVED 4 VEHICLES"])
    log.append([iso(Z(-1, "19:15")), "CG-6033", "", "ON DECK", "NAS CORPUS CHRISTI", "", "CREW REST WAIVER AUTHORIZED"])
    log.append([iso(Z(-1, "19:15")), "CG-6041", "", "ON DECK", "NAS CORPUS CHRISTI", "", "CREW REST WAIVER AUTHORIZED"])
    for i in range(1, 24):
        u = sim.units[f"CC-SAR-{i:03d}"]
        log.append([iso(Z(-1, "20:00") + i * 60), f"CC-SAR-{i:03d}", "", "READY", u["station"], "", "FUELED AND MANIFESTED"])
    log.append([iso(Z(0, "06:15")), "SAR BRANCH", "", "ACTIVATED", "CBECC", "", "SAR OPERATIONS PLAN ACTIVATED. GROUND TEAMS STAND BY AT ROBSTOWN STAGING."])
    fac_name = {fid: f["facility_name"] for fid, f in sim.fac.items()}
    for m in sar.missions:
        where = m["base"]["name"] if m["type"] == "helicopter" else sim.units[m["asset"]]["station"] if m["asset"] in sim.units else ""
        log.append([iso(m["launch"]), m["asset"], m["element"], "LAUNCH", where, "", m["id"]])
        if m["type"] == "helicopter":
            for st in m["stops"]:
                if st["kind"] == "dropoff" and st["persons"]:
                    log.append([iso(st["arrive"]), m["asset"], "", "OFFLOAD", fac_name[st["facility_id"]].upper().replace("NAVAL AIR STATION", "NAS"), "",
                                f"{m['id']} {st['persons']} SURVIVORS OFF, ROTORS TURNING"])
        log.append([iso(m["recovery"]), m["asset"], m["element"], "RECOVERED", where, "", f"{m['id']} {sum(e['persons'] for e in m['events'])} PERSONS"])
    log.append([iso(local_ts(3, "03:00")), "SAR BRANCH", "", "PHASE CHANGE", "CBECC", "", "GROUND AND BOAT TEAMS PRIMARY. 87 CREDENTIALED CIVILIAN BOATS JOIN. CG-6033 RETURNS TO ROUTINE TASKING."])
    log.append([iso(Z(5, "22:00")), "SAR BRANCH", "", "LOG CLOSED", "CBECC", "", "INCIDENT LOG CLOSED. 1,427 RESCUES CONFIRMED. CASE NUMBERS SAR-27-00001 THROUGH SAR-27-01427."])
    log.append([iso(local_ts(5, "17:10")), "SAR BRANCH", "", "PHASE CHANGE", "CBECC", "", "WELFARE CHECK PHASE. 8 TWO-PERSON TEAMS."])
    log.append([iso(local_ts(-3, "10:30")), "SAR BRANCH", "", "READINESS", "CBECC", "", "HURRICANE WATCH. SAR BRANCH READINESS REVIEW. BOAT AND HIGH-WATER VEHICLE INSPECTIONS ORDERED."])
    log.append([iso(local_ts(-2, "09:00")), "SAR BRANCH", "", "READINESS", "CBECC", "", "RESCUE BOAT INSPECTIONS UNDER WAY AT STATIONS. MUTUAL AID REQUESTS SENT TO STATE."])
    wc = collections.Counter()
    for row, m in zip(run.rows, run.meta):
        if m[7].startswith("WC-") and 6 <= m[1] <= 14:
            wc[m[1]] += 1
    for d in range(6, 15):
        log.append([iso(local_ts(d, "19:00")), "SAR BRANCH", "", "DAILY SUMMARY", "CBECC", "", f"WELFARE CHECK TEAMS: {wc[d]} ADDRESSES VISITED TODAY. NO NEW RESCUES."])
    log += run.asset_log
    log.sort(key=lambda r: r[0])
    write_csv("05_other_sources/sar/sar_asset_log.csv", ["time_utc", "asset_id", "crew_element", "status", "location", "incident_number", "note"], log)
    # the sortie plan the aircraft tracks follow, and the shelter arrivals the census is built from
    n_plan = sar_plan.export(sar.missions, sim.units, sim.tracts, fac_name, iso, address)
    with open(os.path.join(HERE, "_sar_shelter_flow.json"), "w", encoding="utf-8") as f:
        json.dump({"_about": "shelter arrivals of rescued persons [epoch, facility, persons, mode, mission, nights]; written by gen_ground.py for gen_ground_public.py",
                   "flows": sorted(sar.flows), "onward": {k: dict(v) for k, v in sar.onward.items() if v}}, f)
    print(f"  sortie plan: {n_plan} sorties; shelter arrivals from rescues: {sum(x[2] for x in sar.flows)} persons")
    # flood depth soundings on D+2 (EVT-1704): 23 manual soundings in Districts 3 and 4, 0.8 to 3.4 ft
    rg = rng("ground", "soundings")
    d34 = [t for t in sim.tracts if sim.tracts[t]["zip"] in D34_ZIPS]
    depths = [0.8, 3.4] + [round(float(x), 1) for x in rg.uniform(0.9, 3.3, 21)]
    depths = [depths[i] for i in rg.permutation(23)]
    srows = []
    for k in range(23):
        tr = sim.tracts[d34[k % len(d34)]]
        p = tr["pool"][int(rg.integers(len(tr["pool"])))]
        srows.append([iso(Z(2, "12:00") + int(k * 300 + rg.integers(0, 200))), "CCFD", ["E-8", "E-13", "E-14", "E-4"][k % 4], f"{p['rlat']:.6f}", f"{p['rlon']:.6f}",
                      address(p), tr["tract"], "3" if tr["zip"] in ("78405", "78416", "78417") else "4", depths[k], "MANUAL STAFF GAUGE"])
    srows.sort()
    write_csv("05_other_sources/sar/flood_depth_soundings.csv",
              ["time_utc", "agency", "unit_id", "latitude", "longitude", "address", "census_tract", "water_district", "depth_ft", "method"], srows)
    write_csv("05_other_sources/sar/flood_extent_snapshots.csv", ["time_utc", "area", "metric", "value", "source"],
              [[iso(Z(2, "15:00")), "Water Districts 3 and 4", "percent of area inundated above 1.5 ft", 68, "Nueces County GIS flood extent"]])
    return len(rows)


def main():
    """One process by default. With --resume the run is cut into pieces that each stop after
    --budget seconds (default 34) and save their state under $GROUND_CKPT (default /tmp/ground_ckpt);
    call again until it prints DONE (exit code 3 means more to do)."""
    import pickle
    import shutil
    import sys
    import time
    t0 = time.time()
    resume = "--resume" in sys.argv[1:]
    budget = next((float(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--budget=")), 34.0 if resume else 1e12)
    ck = os.environ.get("GROUND_CKPT", "/tmp/ground_ckpt")
    state_fp = os.path.join(ck, "state.pkl")
    st = None
    if resume and os.path.exists(state_fp):
        with open(state_fp, "rb") as fh:
            st = pickle.load(fh)
        st["run"].sim.g.load_trees(os.path.join(ck, "trees.pkl"))
        print(f"resumed at phase {st['phase']}, next day {st['next']} ({time.time() - t0:.0f}s)")
    if st is None:
        shutil.rmtree(ck, ignore_errors=True)
        os.makedirs(ck, exist_ok=True)
        retire(["05_other_sources/911/911_cad_records.csv"])
        for f in glob.glob(out_path("05_other_sources/avl/x").replace("x", "*.csv")) + glob.glob(out_path("05_other_sources/911/x").replace("x", "cad_incidents_*.csv")):
            os.remove(f)
        run = Run()
        print(f"setup {time.time() - t0:.0f}s: {len(run.sim.tracts)} tracts, {len(run.sim.units)} units, {len(run.sar.missions)} SAR missions")
        emit_convoy(run.sim)
        st = {"run": run, "bus_log": emit_buses(run.sim), "counts": {}, "next": FIRST_DAY, "phase": "days", "n_avl": 0}
        if resume:
            run.sim.g.save_trees(os.path.join(ck, "trees.pkl"))
    run = st["run"]
    sim = run.sim
    counts = st["counts"]

    def pause(msg):
        flush_avl(sim, ck)
        with open(state_fp + ".tmp", "wb") as fh:
            pickle.dump(st, fh, protocol=4)
        os.replace(state_fp + ".tmp", state_fp)
        print(f"MORE: {msg} ({time.time() - t0:.0f}s)")
        sys.exit(3)

    if st["phase"] == "days":
        while st["next"] <= LAST_DAY:
            if time.time() - t0 > budget:
                pause(f"next day {st['next']}")
            counts[st["next"]] = run.run_day(st["next"])
            st["next"] += 1
        st["phase"] = "avl"
        if resume:
            pause("vehicle location files next")
    if st["phase"] == "avl":
        emit_heartbeats(sim)
        st["n_avl"] = sort_avl(sim, ck if resume else None)
        sim.avl_buf.clear()
        for fp in glob.glob(os.path.join(ck, "avl_*.part")):
            os.remove(fp)
        st["phase"] = "write"
        if resume:
            pause("dispatch, report and rescue files next")
    n_avl = st["n_avl"]
    bus_log = st["bus_log"]
    # CAD by local month
    by_month = collections.defaultdict(list)
    for row in run.rows:
        by_month[row[2][:7]].append(row)
    n_cad = 0
    for mth, rows in sorted(by_month.items()):
        rows.sort(key=lambda r: r[2])
        n_cad += write_csv(f"05_other_sources/911/cad_incidents_{mth}.csv", CAD_HEADER, rows)
    info = write_reports(run, counts)
    n_sar = write_sar(run)
    write_csv("05_other_sources/shelters/evacuation_bus_trips.csv", ["pickup_local", "unit_id", "pickup_area", "facility_id", "arrival_local", "passengers"],
              ([local_iso(a), b, c, d, local_iso(e), n] for a, b, c, d, e, _, n in sorted(bus_log)))
    shutil.rmtree(ck, ignore_errors=True)
    # statistics
    meta = run.meta
    L, Hi = set(sim.L), set(sim.Hi)
    def med(sel):
        v = [m[3] for m in meta if m[3] is not None and sel(m)]
        return float(np.median(v)) if v else float("nan")
    win = lambda m: 0 <= m[1] <= 45
    rL, rH = med(lambda m: win(m) and m[2] in L), med(lambda m: win(m) and m[2] in Hi)
    pre = med(lambda m: m[1] < -5 and m[2] in L) / med(lambda m: m[1] < -5 and m[2] in Hi)
    d1 = [m for m in meta if m[1] == 1]
    print(f"CAD {n_cad} rows; AVL {n_avl} rows; SAR {n_sar} case rows; {time.time() - t0:.0f}s")
    print(f"  D0 {counts[0]} D+1 {counts[1]} D+2 {counts[2]} D+12 {counts[12]} D+28 {counts[28]} D+45 {counts[45]}; baseline mean {np.mean([counts[d] for d in range(-30, -4)]):.0f}")
    print(f"  D+1 share from low-income surge tracts {sum(1 for m in d1 if m[2] in L) / len(d1):.3f}")
    print(f"  median response D0..D+45: low-income surge {rL / 60:.1f} min, high-income {rH / 60:.1f} min, ratio {rL / rH:.2f}; pre-storm ratio {pre:.2f}")
    print(f"  language D0..D+45 {info['lang']}; ten-digit calls D0-28 {info['admin_d0_28']}, D29-45 {info['admin_d29_45']}")
    print(f"  dispatched share {sum(1 for m in meta if m[7]) / len(meta):.2f}; subscribers {len(sim.numbers)}")
    print("DONE")


if __name__ == "__main__":
    main()
