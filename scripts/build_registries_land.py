"""Build the land-side registries from canon names and real geography.

    python scripts/build_registries_land.py

Writes (all under 06_data_streams/):
    facility_registry.json      hospitals, clinics, shelters, distribution sites, hubs, recovery centres, EOC, 911 ...
    cad_units.json              agencies, stations, units (nature / disposition / priority codes are kept as they were)
    infrastructure_assets.json  substations, water plant and pumps, tanks, wastewater plants, bridges, fuel, generators
    sensor_registry.json        sondes, air monitors, tide and stream gauges, weather stations, buoys, bridge sensors
    areas.json                  counties, cities, neighbourhoods, ZIP codes, water districts, zones, tracts, beats
    _internal/<registry>_truth.json   scenario notes per id and the id_migration map (not for participants)

Rules this builder follows (00_scenario/canon_decisions.md):
  * Names that appear in the news corpus or public record are kept exactly.
  * Fictional operators on real sites: no real hospital-system, company or broadcaster name is written.
  * Every coordinate is a real published point (99_reference/geo/landmarks.geojson) or a point beside
    a real road (see scripts/registry_place.py); each record says which in `position_basis`.
  * Registries are reference data: no thread ids, no scenario outcomes. Those go to _internal/.
Figures that canon does not give (shelter capacity, bed counts at minor hospitals, staffing) are
ordinary reference values chosen for the scenario and are marked `"figures": "scenario value"`.
"""
import csv
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402
import registry_place as P  # noqa: E402

ROOT = geo.ROOT
OUT = os.path.join(ROOT, "06_data_streams")
INT = os.path.join(OUT, "_internal")
TODAY = "2026-11-09"
G = P.G()

NAMED_OK = {"school", "venue", "wastewater", "tide_gauge", "buoy", "weather_station", "airport", "bridge",
            "water_plant", "community", "military", "police", "runway_end"}
CAT_LABEL = {"hospital": "hospital", "helipad": "hospital heliport", "fire_station": "fire station", "ems": "EMS station"}

TRUTH = {k: {} for k in ("facility_registry", "cad_units", "infrastructure_assets", "sensor_registry", "areas")}
MIGRATION = {k: [] for k in TRUTH}
LANDMARK_USED = {}


def truth(reg, rid, **kw):
    TRUTH[reg].setdefault(rid, {}).update({k: v for k, v in kw.items() if v is not None})


def migrate(reg, old, new, where, note=""):
    MIGRATION[reg].append({"old": old, "new": new, "old_used_in": where, "note": note})


def at_site(name, category=None, exact=False):
    """Coordinates of a real landmark; the basis names the landmark only when it is a public place."""
    lat, lon, _, l = P.site(name, category, exact)
    src = l["source"].split(" (")[0]
    addr = (l.get("address") or "").strip()
    if l["category"] in NAMED_OK:
        basis = f"real site: {l['name']} [{src}]"
    else:
        street = addr.split(",")[0] if addr and re.match(r"\d", addr) else None
        where = f" at {street}" if street else ""
        basis = f"real site: {CAT_LABEL.get(l['category'], l['category'])}{where} [{src}]"
    return {"latitude": lat, "longitude": lon, "position_basis": basis, "_lm": l}


def placed(road, near, what=None, max_km=2.5, setback_m=35.0):
    lat, lon, basis, name = P.beside(road, near, what=what, max_km=max_km, setback_m=setback_m)
    return {"latitude": lat, "longitude": lon, "position_basis": basis, "_road": name}


def finish(rec, reg, rid):
    """Strip helper keys, remember which landmark a record sits on (internal only)."""
    l = rec.pop("_lm", None)
    rec.pop("_road", None)
    if l is not None:
        truth(reg, rid, reference_landmark={"name": l["name"], "category": l["category"], "address": l.get("address"),
                                            "source": l["source"], "source_id": l.get("source_id")})
        LANDMARK_USED.setdefault(l["name"], []).append(rid)
    return rec


def lm_addr(l):
    return (l.get("address") or "").replace(", TX,", ", TX")


def zip_of(text):
    m = re.search(r"\b(7[78]\d{3})\b", text or "")
    return m.group(1) if m else None


# ======================================================================================
# 1. FACILITIES
# ======================================================================================
def build_facilities():
    fac = []

    def add(fid, name, code, label, pos, address=None, city="Corpus Christi", county="Nueces", zipc=None,
            abbrev=None, aliases=None, roles=None, **extra):
        l = pos.get("_lm")
        addr = address or (lm_addr(l) if l else None)
        rec = {"facility_id": fid, "facility_name": name}
        if abbrev:
            rec["facility_name_abbrev"] = abbrev
        if aliases:
            rec["aliases"] = aliases
        rec.update({"facility_type": label, "facility_type_code": code, "address": addr, "city": city, "county": county,
                    "state": "TX", "zip": zipc or zip_of(addr)})
        rec.update({k: pos[k] for k in ("latitude", "longitude", "position_basis")})
        if roles:
            rec["roles"] = roles
        rec.update(extra)
        rec["_lm"] = l
        fac.append(finish(rec, "facility_registry", fid))
        return rec

    # ---------------- hospitals (fictional operators on real hospital sites)
    hosp = [
        ("FAC-SRMC-001", "Shoreline Regional Medical Center", "SRMC", "CHRISTUS Spohn Hospital Corpus Christi - Shoreline", "hospital",
         dict(licensed_beds=500, ed_beds=68, icu_beds=40, ventilators=32, trauma_level="Level II", helipad=True,
              ed_baseline_visits_per_day=220, backup_power={"generator": True, "diesel_storage_gal": 24000, "tanks": 2,
                                                             "estimated_runtime_days_at_storm_load": 9.2},
              bilingual_clinical_staff=True, figures="as stated in hospital statements")),
        ("FAC-BCMC-002", "Bay City Medical Center", "BCMC", "Corpus Christi Medical Center - Bay Area", "hospital",
         dict(licensed_beds=280, ed_beds=42, icu_beds=28, ventilators=18, trauma_level="Level III", helipad=True,
              ed_baseline_visits_per_day=120, backup_power={"generator": True, "diesel_storage_gal": 6000, "tanks": 1},
              bilingual_clinical_staff=True, figures="beds and diesel as stated in hospital statements; other figures: scenario value")),
        ("FAC-LPMC-011", "Lamar Park Medical Center", "LPMC", "Corpus Christi Medical Center - Doctors Regional", "hospital",
         dict(licensed_beds=186, ed_beds=24, icu_beds=16, ventilators=10, trauma_level="Level IV", helipad=False,
              ed_baseline_visits_per_day=70, backup_power={"generator": True, "diesel_storage_gal": 4000, "tanks": 1},
              figures="scenario value")),
        ("FAC-SCMH-012", "Saratoga Community Hospital", "SCMH", "CHRISTUS Spohn Hospital Corpus Christi - South", "hospital",
         dict(licensed_beds=94, ed_beds=18, icu_beds=8, ventilators=6, trauma_level="Level IV", helipad=True,
              ed_baseline_visits_per_day=45, backup_power={"generator": True, "diesel_storage_gal": 2500, "tanks": 1},
              figures="scenario value")),
        ("FAC-FPCH-013", "Five Points Community Hospital", "FPCH", "Corpus Christi Medical Center - Northwest Regional", "hospital",
         dict(licensed_beds=110, ed_beds=16, icu_beds=8, ventilators=6, trauma_level="Level IV", helipad=False,
              ed_baseline_visits_per_day=35, backup_power={"generator": True, "diesel_storage_gal": 3000, "tanks": 1},
              figures="scenario value")),
        ("FAC-GCCH-014", "Gulf Coast Children's Hospital", "GCCH", "Driscoll Children's Hospital", "hospital",
         dict(licensed_beds=190, ed_beds=22, icu_beds=24, ventilators=20, trauma_level="Pediatric Level III", helipad=True,
              ed_baseline_visits_per_day=30, backup_power={"generator": True, "diesel_storage_gal": 5000, "tanks": 1},
              figures="scenario value")),
    ]
    for fid, name, ab, lmname, cat, extra in hosp:
        add(fid, name, "HOSP-ED", "Hospital, acute care with emergency department", at_site(lmname, cat), abbrev=ab, **extra)
    add("FAC-ABCH-015", "Aransas Bay Community Hospital", "HOSP-ED", "Hospital, critical access with emergency department",
        at_site("North Bay General Hospital Inc", "helipad"), address="Aransas Pass, TX", city="Aransas Pass",
        county="San Patricio", abbrev="ABCH", licensed_beds=45, ed_beds=8, icu_beds=4, ventilators=3,
        trauma_level="Level IV", helipad=True, ed_baseline_visits_per_day=18,
        backup_power={"generator": True, "diesel_storage_gal": 1500, "tanks": 1}, figures="scenario value")
    truth("facility_registry", "FAC-SRMC-001", canon_place_id="FAC-HOS-xx", role="Primary surge hospital (T16). On generator D0 06:17Z to D+8 09:14 local (McKinley Substation). 140% of licensed beds at 07:00 local D+2; triage tent in the south parking structure.",
          sources=["EVT-1601", "EVT-1602", "EVT-1603", "EVT-1605", "PUB-160", "PUB-161", "PUB-164"])
    truth("facility_registry", "FAC-BCMC-002", canon_place_id="FAC-HOS-xx", role="Second surge hospital; 118% (331 patients) at D+2; redirects non-critical ambulances to smaller facilities.", sources=["EVT-1603", "PUB-160"])
    truth("facility_registry", "_hospital_baseline", note="Nueces County ER baseline is 520 visits a day (EVT-0101); SRMC's 220 is canon (EVT-1602); the other five Nueces hospitals' baselines are an allocation that sums to 520.")

    # ---------------- urgent care, clinics, public health
    add("FAC-CCUC-003", "Calallen Community Urgent Care", "URGENT", "Urgent care clinic", placed(r"Northwest Blvd", (27.858, -97.630)),
        address="Northwest Boulevard, Corpus Christi, TX 78410", exam_rooms=10, figures="scenario value")
    add("FAC-STCH-016", "South Texas Community Health Center", "CLINIC", "Community health clinic", placed(r"Staples St", (27.722, -97.382)),
        address="South Staples Street, Corpus Christi, TX 78411", exam_rooms=14, figures="scenario value")
    add("FAC-FBUC-017", "Flour Bluff Urgent Care", "URGENT", "Urgent care clinic", placed(r"Waldron Rd", (27.668, -97.287)),
        address="Waldron Road, Corpus Christi, TX 78418", exam_rooms=8, figures="scenario value")
    add("FAC-SSUC-018", "Southside Urgent Care", "URGENT", "Urgent care clinic", placed(r"Saratoga Blvd", (27.690, -97.390)),
        address="Saratoga Boulevard, Corpus Christi, TX 78413", exam_rooms=9, figures="scenario value")
    add("FAC-PHD-019", "Corpus Christi-Nueces County Public Health District", "PUBHEALTH", "Public health department",
        placed(r"Horne Rd", (27.757, -97.428)), address="Horne Road, Corpus Christi, TX 78416", phone="361-826-7200")
    add("FAC-MED-010", "Nueces County Medical Examiner's Office", "ME", "Medical examiner",
        at_site("CHRISTUS Spohn Hospital Corpus Christi - Memorial", "hospital"), address="2610 Hospital Blvd, Corpus Christi, TX 78405")
    add("FAC-BLD-020", "Nueces Bay Blood Services", "BLOOD", "Blood donation centre", placed(r"Ayers St", (27.752, -97.416)),
        address="Ayers Street, Corpus Christi, TX 78415")

    # ---------------- emergency management
    add("FAC-CBECC-004", "Coastal Bend Emergency Communications Center", "PSAP", "Emergency communications centre (911 PSAP)",
        at_site("Corpus Christi Police Department", "police", exact=True), abbrev="CBECC",
        aliases=["Corpus Christi-Nueces County 911 center", "PSAP-01"], consoles=18, baseline_calls_per_day=310,
        information_line="NuecesInfoLine 361-826-INFO", figures="baseline as stated by the centre; consoles: scenario value")
    add("FAC-EOC-021", "Nueces County Emergency Operations Center", "EOC", "Emergency operations centre",
        at_site("Nueces County Courthouse", "venue"), address="901 Leopard Street, Corpus Christi, TX 78401", aliases=["Nueces County Office of Emergency Management", "Nueces County Courthouse"])
    add("FAC-GOV-022", "Corpus Christi City Hall", "GOV", "City government", at_site("Corpus Christi City Hall", "venue"), phone="361-826-1600")
    add("FAC-JFO-023", "FEMA Joint Field Office", "JFO", "Federal joint field office", placed(r"State Hwy 358|S Padre Island Dr", (27.718, -97.405)),
        address="South Padre Island Drive, Corpus Christi, TX 78415", aliases=["Federal Emergency Management Agency Joint Field Office"])
    add("FAC-CLM-024", "Inner Harbor Spill Claims Center", "CLAIMS", "Oil spill claims centre", placed(r"Leopard St", (27.797, -97.409)),
        address="Leopard Street, Corpus Christi, TX 78401", aliases=["claims center"])
    add("FAC-USCG-01", "US Coast Guard Sector Corpus Christi", "USCG", "Coast Guard sector headquarters", placed(None, (27.7722, -97.4990), max_km=2.0),
        address="Corpus Christi International Airport, Corpus Christi, TX 78406",
        aliases=["Coast Guard Sector Corpus Christi", "Unified Command", "Unified Command Joint Information Center"],
        roles=["unified_command_post", "joint_information_center"], phone="(361) 555-0147")
    add("FAC-NWS-025", "National Weather Service Corpus Christi", "NWS", "Weather forecast office", placed(None, (27.7790, -97.5060), max_km=2.0),
        address="Corpus Christi International Airport, Corpus Christi, TX 78406")

    # ---------------- shelters
    def shelter(cap, zones, **kw):
        d = {"capacity": cap, "serves_evacuation_zones": zones, "figures": "scenario value"}
        d.update(kw)
        return d

    add("FAC-SHLT-007", "Richard M. Borchard Regional Fairgrounds", "SHELTER", "Emergency shelter, regional fairgrounds",
        placed(None, (27.8060, -97.6720), max_km=2.0), address="Robstown, TX 78380", city="Robstown",
        aliases=["Robstown Fairgrounds", "Richard M. Borchard Fairgrounds"],
        roles=["shelter", "staging_area", "water_distribution", "fema_outreach"],
        shelter=shelter(2500, ["A", "B", "C"], pets=True, medical_station=True))
    add("FAC-SHLT-006", "Calallen ISD Fieldhouse", "SHELTER", "Emergency shelter, school fieldhouse",
        at_site("Calallen High School", "school", exact=True), aliases=["Calallen High School"],
        roles=["shelter", "water_distribution"], shelter=shelter(600, ["A", "B", "C"], pets=False, medical_station=True))
    add("FAC-SHLT-026", "Richard King High School", "SHELTER", "Emergency shelter, school",
        at_site("Richard King High School", "school"), address="5225 Gollihar Rd, Corpus Christi, TX 78412",
        roles=["shelter", "recovery_help_point"], shelter=shelter(900, ["A", "B", "D"], pets=False))
    add("FAC-SHLT-027", "West Oso High School", "SHELTER", "Emergency shelter, school",
        at_site("West Oso High School", "school"), roles=["shelter"], shelter=shelter(500, ["A", "B"], pets=False))
    add("FAC-SHLT-028", "Solomon P. Ortiz Community Center", "SHELTER", "Emergency shelter, community centre",
        placed(None, (27.7962, -97.6663), max_km=2.0), address="Robstown, TX 78380", city="Robstown",
        roles=["shelter", "fema_outreach"], shelter=shelter(300, ["C"], pets=False))
    add("FAC-SHLT-029", "Flour Bluff ISD Gymnasium", "SHELTER", "Post-storm shelter, school gymnasium",
        at_site("Flour Bluff High School", "school"), roles=["shelter", "fema_outreach"],
        shelter=shelter(450, [], pets=False, note="Inside an evacuation zone; used after landfall only."))

    # ---------------- schools and community sites named in canon
    add("FAC-SCH-030", "Zavala Elementary School", "SCHOOL", "Public school", at_site("Zavala Elementary School", "school"),
        aliases=["Zavala Elementary"], designated_shelter=False)
    add("FAC-SCH-031", "Collier Elementary", "SCHOOL", "Public school", placed(r"Leopard St", (27.800, -97.442)),
        address="Leopard Street, Corpus Christi, TX 78408", designated_shelter=False)
    add("FAC-SCH-032", "Yeager Elementary School", "SCHOOL", "Public school", at_site("Yeager Elementary School", "school"),
        roles=["water_distribution"], designated_shelter=False)
    add("FAC-SCH-033", "Tuloso-Midway High School Gym", "SCHOOL", "Public school gymnasium", at_site("Tuloso Midway High School", "school"),
        aliases=["Tuloso-Midway High School", "Tuloso-Midway HS"], roles=["water_distribution"], designated_shelter=False)
    add("FAC-SCH-034", "Cunningham Middle School", "SCHOOL", "Public school", at_site("Cunningham Middle School", "school", exact=True),
        roles=["water_distribution"], designated_shelter=False)
    add("FAC-COM-035", "Woodlawn Community Center", "COMMUNITY", "Community centre", placed(None, (27.70524, -97.34996), max_km=1.0),
        address="Woodlawn Drive area, Corpus Christi, TX 78412", aliases=["Woodlawn Ctr"], roles=["water_distribution"])
    add("FAC-COM-036", "Cefe Valenzuela Park", "COMMUNITY", "City park", placed(r"Old Brownsville Rd", (27.757, -97.468)),
        address="Old Brownsville Road, Corpus Christi, TX 78417", roles=["water_distribution"])
    add("FAC-COM-037", "Brownie's Corner Community Center", "COMMUNITY", "Community centre", placed(None, (27.8055, -97.4135), max_km=1.0),
        address="Hillcrest, Corpus Christi, TX 78407", roles=["water_distribution"])
    add("FAC-HUB-038", "Neighborhood church relief hub", "RELIEF-HUB", "Church fellowship hall relief hub", placed(None, (27.8040, -97.4065), max_km=1.0),
        address="Hillcrest / Washington-Coles, Corpus Christi, TX 78401", roles=["food_and_water_distribution", "neighbour_registry"])
    add("FAC-HUB-039", "St. John's Episcopal Church", "RELIEF-HUB", "Church aid distribution point", placed(r"Staples St", (27.776, -97.402)),
        address="Staples Street, Corpus Christi, TX 78404", roles=["food_and_water_distribution"])
    add("FAC-DRC-040", "Oveal Williams Senior Center", "DRC", "FEMA Disaster Recovery Center", placed(r"Martin Luther King Dr", (27.803, -97.409)),
        address="1414 Martin Luther King Drive, Corpus Christi, TX 78401", roles=["disaster_recovery_center"])
    add("FAC-DRC-041", "FEMA Disaster Recovery Center, Ayers Street", "DRC", "FEMA Disaster Recovery Center", placed(r"Ayers St", (27.731, -97.428)),
        address="5301 Ayers Street, Corpus Christi, TX 78415", roles=["disaster_recovery_center"])
    add("FAC-DRC-042", "Memorial Coliseum Annex", "DRC", "FEMA Disaster Recovery Center", placed(r"N Shoreline Blvd", (27.798, -97.391)),
        address="902 N. Shoreline Blvd, Corpus Christi, TX 78401", aliases=["Memorial Coliseum"], roles=["disaster_recovery_center"])
    add("FAC-COL-043", "Del Mar College East Campus", "COLLEGE", "Community college campus", at_site("Del Mar College East Campus", "school"),
        aliases=["Del Mar College"], roles=["recovery_help_point"])
    add("FAC-COL-044", "Texas A&M University-Corpus Christi", "COLLEGE", "University", at_site("Texas A&M University-Corpus Christi", "school"),
        address="6300 Ocean Drive, Corpus Christi, TX 78412")

    # ---------------- military (canon place ids are the facility ids)
    add("FAC-DOD-01", "Naval Air Station Corpus Christi", "MIL", "Navy installation", _nas_site(),
        address="Naval Air Station Corpus Christi, TX 78419", aliases=["NAS Corpus Christi"])
    add("FAC-DOD-02", "Corpus Christi Army Depot", "MIL", "Army depot on NAS Corpus Christi", placed(None, (27.6935, -97.2790), max_km=2.0),
        address="Naval Air Station Corpus Christi, TX 78419", aliases=["CCAD"])
    add("FAC-DOD-05", "DLA Distribution Corpus Christi", "MIL", "Defense Logistics Agency distribution site", placed(None, (27.6870, -97.2760), max_km=2.0),
        address="Naval Air Station Corpus Christi, TX 78419")

    out_of_area = [
        {"facility_id": "FAC-SHLT-OOA-01", "facility_name": "Alice High School", "facility_type": "Emergency shelter, school", "city": "Alice", "county": "Jim Wells", "state": "TX",
         "position_basis": "outside the reference window; city only", "roles": ["shelter"]},
        {"facility_id": "FAC-SHLT-OOA-02", "facility_name": "American Red Cross shelters, Bexar and Karnes counties", "facility_type": "Emergency shelters, evacuation destination",
         "city": "San Antonio area", "county": "Bexar / Karnes", "state": "TX", "position_basis": "outside the reference window; county only", "roles": ["shelter"]},
        {"facility_id": "FAC-HOSP-OOA-03", "facility_name": "San Antonio trauma centers", "facility_type": "Hospitals receiving transfers", "city": "San Antonio", "county": "Bexar", "state": "TX",
         "position_basis": "outside the reference window; city only", "roles": ["transfer_destination"]},
        {"facility_id": "FAC-HOSP-OOA-04", "facility_name": "Smaller hospitals in Robstown and Kingsville", "facility_type": "Hospitals receiving diverted ambulances", "city": "Robstown / Kingsville",
         "county": "Nueces / Kleberg", "state": "TX", "position_basis": "outside the reference window; city only", "roles": ["diversion_destination"]},
        {"facility_id": "FAC-DOD-03", "facility_name": "Naval Air Station Kingsville", "facility_type": "Navy installation", "city": "Kingsville", "county": "Kleberg", "state": "TX",
         "latitude": P.r5(P.landmark("NAS Kingsville", "military")["lat"]), "longitude": P.r5(P.landmark("NAS Kingsville", "military")["lon"]),
         "position_basis": "real site: NAS Kingsville [USDOT NTAD Military Bases]"},
        {"facility_id": "FAC-DOD-04", "facility_name": "NAS Joint Reserve Base Fort Worth", "facility_type": "Navy installation", "city": "Fort Worth", "county": "Tarrant", "state": "TX",
         "position_basis": "outside the reference window; city only", "aliases": ["Naval Air Station Joint Reserve Base Fort Worth"]},
        {"facility_id": "FAC-DOD-06", "facility_name": "Fort Hood", "facility_type": "Army installation", "city": "Killeen", "county": "Bell", "state": "TX",
         "position_basis": "outside the reference window; city only"},
    ]

    # ---------------- internal notes and migration
    t = lambda fid, **kw: truth("facility_registry", fid, **kw)
    t("FAC-SHLT-007", role="Shelter named in the D-1 evacuation order; Texas Task Force 1 staging from D-1 13:00 local; bottled water point for the Districts 3/4 notice; FEMA outreach from D+9.", sources=["PUB-201", "PUB-203", "EVT-1701", "NWS-P012-06", "NWS-P008-06"])
    t("FAC-SHLT-006", role="Shelter in the D-1 order ('Calallen ISD Fieldhouse'); 'Calallen High School' water distribution site in PUB-132.", sources=["PUB-201", "PUB-132"])
    t("FAC-SHLT-026", role="Correct Zone D shelter (EVT-1403); named with West Oso HS in KNCB's D-3 broadcast (PUB-140); in-person FEMA help from D+8.", sources=["EVT-1403", "PUB-140", "NWS-P008-07"])
    t("FAC-SHLT-027", role="Designated shelter in PUB-140.", sources=["PUB-140"])
    t("FAC-SHLT-028", role="FEMA outreach site from D+9.", sources=["NWS-P008-06"], placement_note="Canon gives no location; placed in Robstown near the school of the same name.")
    t("FAC-SHLT-029", role="FEMA outreach site from D+9 ('Flour Bluff ISD gymnasium').", sources=["NWS-P008-06"])
    t("FAC-SCH-030", role="Never a shelter. False-shelter posts by the coordinated network sent at least 23 callers to 2-1-1 on D-1 (T15).", sources=["PUB-152", "NWS-P038-60"])
    t("FAC-SCH-031", role="Not a shelter. KNCB's improvised Spanish advisory on D-1 wrongly sent Zone D residents here instead of Richard King High School (T14).", sources=["EVT-1403"])
    t("FAC-SCH-032", role="Bottled water point for Districts 3 and 4.", sources=["NWS-P012-06"])
    t("FAC-SCH-033", role="Bottled water site in the D+12 notice.", sources=["PUB-204"])
    t("FAC-SCH-034", role="Water distribution site in PUB-132.", sources=["PUB-132"])
    t("FAC-COM-035", role="Bottled water site in the D+12 notice.", sources=["PUB-204"])
    t("FAC-COM-036", role="Bottled water site in the D+12 notice.", sources=["PUB-204"])
    t("FAC-COM-037", role="Water distribution site in PUB-132.", sources=["PUB-132"])
    t("FAC-HUB-038", role="Pastor Gloria Whitfield's (CHR-049) relief hub; fed the neighbourhood before official distribution arrived (PUB-037). Canon never names the church.", sources=["PUB-037", "NWS-M051-01"])
    t("FAC-HUB-039", role="Informal aid distribution since D+2.", sources=["NWS-P057-03"])
    for fid in ("FAC-DRC-040", "FAC-DRC-041", "FAC-DRC-042"):
        t(fid, role="Disaster Recovery Center opened after Individual Assistance approval (D+57).", sources=["NWS-P057-03", "NWS-P057-04", "NWS-P090-07"])
    t("FAC-CBECC-004", role="911 centre; peak about 2,900 calls on D+1; phishing target HOST-911-01.", sources=["PUB-130", "PUB-131", "PUB-132"])
    t("FAC-USCG-01", role="Leads the Unified Command with the Texas General Land Office.", sources=["PUB-029"], overlap_note="Coast Guard aircraft and boats belong to the aviation and maritime registries.")
    t("FAC-CLM-024", role="Opens D+12 for cleanup and property claims; lost-income claims from D+63.", sources=["PUB-106"], placement_note="Canon gives no address.")
    t("FAC-JFO-023", role="Joint statement with CBPWA on D+21.", sources=["PUB-205"], placement_note="Canon gives no address.")
    t("FAC-DOD-01", role="Drone overflights D+1 to D+10; backup generator EQP-2201 fails D+40.", sources=["EVT-0318", "EVT-0407"])
    t("FAC-MED-010", role="Confirms storm deaths.", sources=["NWS-P002-09"])

    mig = [
        ("FAC-CCMC-001", "FAC-SRMC-001", "05_other_sources/public_health (ed_visits, hospital_capacity)", "largest hospital in the old stream (383 beds); canon has 500"),
        ("FAC-SHMC-001", "FAC-BCMC-002", "05_other_sources/public_health", "second hospital in the old stream (294 beds); canon has 280"),
        ("FAC-DRMC-001", "FAC-LPMC-011", "05_other_sources/public_health", "186 beds in both"),
        ("FAC-SHBA-001", "FAC-SCMH-012", "05_other_sources/public_health", "94 beds in both"),
        ("FAC-UCG-001", "FAC-CCUC-003", "05_other_sources/public_health", "urgent care"),
        ("FAC-SHE-001", "FAC-SHLT-007", "05_other_sources/public_health", "shelter medical station (inferred)"),
        ("FAC-SHE-002", "FAC-SHLT-006", "05_other_sources/public_health", "shelter medical station (inferred)"),
        ("FAC-HOS-xx", ["FAC-SRMC-001", "FAC-BCMC-002", "FAC-LPMC-011", "FAC-SCMH-012", "FAC-FPCH-013", "FAC-GCCH-014"], "00_scenario/places.json", "placeholder for the Nueces County emergency departments"),
        ("PSAP-01", "FAC-CBECC-004", "00_scenario/places.json", ""),
        ("FAC-SHLT-005 (American Bank Center)", None, "old facility_registry.json", "removed: not in canon and inside surge Zone A"),
        ("FAC-SHLT-007 (Robstown ISD Gymnasium)", "FAC-SHLT-007", "old facility_registry.json", "canon name is Richard M. Borchard Regional Fairgrounds"),
        ("FAC-SHLT-006 (Calallen High School)", "FAC-SHLT-006", "old facility_registry.json", "canon shelter name is Calallen ISD Fieldhouse; same campus"),
        ("FAC-SHLT-008 (Victoria Civic Center)", "FAC-SHLT-OOA-02", "old facility_registry.json", "not in canon; out-of-area shelters are in Bexar and Karnes counties"),
        ("FAC-SHLT-009 (San Antonio City Shelter Network)", "FAC-SHLT-OOA-02", "old facility_registry.json", ""),
        ("McKinley Substation", "GW-FAC-DSS-01", "EVT-1602, EVT-1605, EVT-1504", "see infrastructure_assets"),
    ]
    for old, new, where, note in mig:
        migrate("facility_registry", old, new, where, note)
    return fac, out_of_area


def _has(name):
    return sum(1 for l in G.landmarks if name.lower() in l["name"].lower()) == 1


def _nas_site():
    """NAS Corpus Christi: the installation-parcel point nearest the airfield (three parcels are published)."""
    cands = [l for l in G.landmarks if l["category"] == "military" and "Naval Air Station Corpus Christi" in l["name"]]
    apt = P.landmark("Corpus Christi Nas (Truax Fld) (NGP/KNGP)", "airport")
    best = min(cands, key=lambda l: geo.dist_m((l["lat"], l["lon"]), (apt["lat"], apt["lon"])))
    return {"latitude": P.r5(best["lat"]), "longitude": P.r5(best["lon"]),
            "position_basis": "real site: Naval Air Station Corpus Christi installation parcel at the airfield (centroid computed from the published boundary) [USDOT NTAD Military Bases]",
            "_lm": best}


# ======================================================================================
# 2. CAD: agencies, stations, units
# ======================================================================================
# fictional station number -> (real site landmark name, district name, battalion, CAD beat)
CCFD_STATIONS = [
    (1, "Corpus Christi Fire Department Station 1", "Downtown", "BC-1", "B01"),
    (2, "Corpus Christi Fire Department Station 8", "South Side / Kostoryz", "BC-2", "B10"),
    (3, "Corpus Christi Fire Department Station 2", "Calallen", "BC-1", "B08"),
    (4, "Corpus Christi Fire Department Station 3", "Morgan / Six Points", "BC-1", "B03"),
    (5, "Corpus Christi Fire Department Station 4", "Rodd Field / Flour Bluff approach", "BC-3", "B09"),
    (6, None, "North Beach", "BC-1", "B01"),
    (7, "Corpus Christi Fire Department Station 14", "South Staples", "BC-2", "B04"),
    (8, "Corpus Christi Fire Department Station 5", "Westside / Leopard", "BC-1", "B02"),
    (9, "Corpus Christi Fire Department Station 7", "Staples / Lamar Park", "BC-2", "B03"),
    (10, "Corpus Christi Fire Department Station 15", "Padre Island", "BC-3", "B07"),
    (11, "Corpus Christi Fire Department Station 6", "Weber / Oso", "BC-2", "B04"),
    (12, "Corpus Christi Fire Department Station 11", "Airline", "BC-2", "B11"),
    (13, "Corpus Christi Fire Department Station 9", "Navigation / Refinery Row", "BC-1", "B12"),
    (14, "Corpus Christi Fire Department Station 10", "Westside / Horne", "BC-1", "B05"),
    (15, "Annaville Volunteer Fire Department Station 1", "Annaville / Tuloso", "BC-1", "B08"),
    (16, "Corpus Christi Fire Department Station 16", "Mustang Island", "BC-3", "B07"),
    (17, "Corpus Christi Fire Station 17", "Yorktown / Southside", "BC-2", "B04"),
    (18, "Corpus Christi Fire Department Station 13", "Waldron Road / Flour Bluff", "BC-3", "B06"),
]
OLD_STATION_OF = {"STA-10": "STA-10", "STA-11": "STA-11", "STA-12": "STA-12", "STA-14": "STA-14"}  # ids unchanged


def build_cad():
    old = json.load(open(os.path.join(OUT, "cad_units.json"), encoding="utf-8"))
    if "units" in old and "stations" in old and os.path.exists(os.path.join(INT, "cad_units_legacy_agencies.json")):
        legacy = json.load(open(os.path.join(INT, "cad_units_legacy_agencies.json"), encoding="utf-8"))
    else:
        legacy = old["agencies"]
        os.makedirs(INT, exist_ok=True)
        json.dump(legacy, open(os.path.join(INT, "cad_units_legacy_agencies.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    stations, units = [], []

    def station(sid, agency, name, pos, address=None, **extra):
        l = pos.get("_lm")
        rec = {"station_id": sid, "agency": agency, "name": name, "address": address or (lm_addr(l) if l else None)}
        rec.update({k: pos[k] for k in ("latitude", "longitude", "position_basis")})
        rec.update(extra)
        rec["_lm"] = l
        stations.append(finish(rec, "cad_units", sid))
        return rec

    # ---- CCFD / CCEMS stations
    for n, lmname, district, bc, beat in CCFD_STATIONS:
        if lmname:
            pos = at_site(lmname, "fire_station", exact=True)
        else:
            pos = placed(r"Timon Blvd", (27.8265, -97.3865))
        station(f"STA-{n}", "CCFD", f"Station {n} - {district}", pos, address=None if lmname else "Timon Boulevard, Corpus Christi, TX 78402",
                station_number=n, battalion=bc, beat=beat, houses=["CCFD", "CCEMS"])
    truth("cad_units", "STA-18", role="Second incident command post (ICP-2) from D+3 08:14 local, covering south Mustang Island. Canon calls it 'Waldron Road Fire Station 18'.", sources=["EVT-1705"])
    truth("cad_units", "STA-6", placement_note="No published fire station point on North Beach; placed beside Timon Blvd. Houses BOAT-1.")
    truth("cad_units", "_station_numbering", note="Station numbers are fictional and keep the old unit ids (E-3 Calallen, E-8 Leopard, E-10 Padre Island...). Each sits on a real fire station site whose real number differs; see reference_landmark per station.")

    # ---- police / sheriff
    station("PD-HQ", "CCPD", "Corpus Christi Police Department Headquarters", at_site("Corpus Christi Police Department", "police", exact=True))
    so = [l for l in G.landmarks if l["category"] == "police" and l["name"] == "Nueces County Sheriff's Office"]
    for l in so:
        tag = "SO-MAIN" if "Leopard" in (l.get("address") or "") else "SO-ANNEX"
        name = "Nueces County Sheriff's Office" + ("" if tag == "SO-MAIN" else " - Padre Island Drive annex")
        station(tag, "NCSO", name, {"latitude": P.r5(l["lat"]), "longitude": P.r5(l["lon"]),
                                    "position_basis": f"real site: Nueces County Sheriff's Office [{l['source'].split(' (')[0]}]", "_lm": l})
    station("PA-PS", "PAPD", "Port Aransas Public Safety (police and EMS)", at_site("Port Aransas Police Department", "police"))

    # ---- mutual aid home stations inside the reference window
    ma = [("MA-STA-ROBS", "Robstown Fire Department", "Robstown Fire Department"),
          ("MA-STA-PORT", "James L Bishop Fire Station", "Portland Fire Department"),
          ("MA-STA-APAS", "Aransas Pass Fire Department", "Aransas Pass Fire Department"),
          ("MA-STA-INGL", "Ingleside Volunteer Fire Department", "Ingleside Volunteer Fire Department"),
          ("MA-STA-SINT", "Sinton Volunteer Fire Department", "Sinton Volunteer Fire Department"),
          ("MA-STA-ANNA", "Annaville Fire Department Station 2", "Annaville Fire Department"),
          ("MA-STA-FBFD", "Flour Bluff Fire Department", "Nueces County ESD Flour Bluff Fire Department")]
    for sid, lmname, name in ma:
        station(sid, "MA_FIRE", name, at_site(lmname, "fire_station", exact=not lmname.startswith("Flour Bluff Fire")))
    spso = P.landmark("San Patricio County Sheriff's Office", "police")
    station("MA-STA-SANPAT", "MA_FIRE", "San Patricio County Emergency Services (Sinton)",
            {"latitude": P.r5(spso["lat"]), "longitude": P.r5(spso["lon"]),
             "position_basis": "real site: San Patricio County Sheriff's Office [USGS National Structures Dataset]", "_lm": spso})

    # ---- staging areas and depots
    fair = placed(None, (27.8060, -97.6720), max_km=2.0)
    station("STG-FAIR", "NCOEM", "Staging area - Richard M. Borchard Regional Fairgrounds", fair, address="Robstown, TX 78380", facility_id="FAC-SHLT-007")
    station("BUS-DEPOT", "NCOEM", "County and transit bus yard", placed(r"Bear Ln", (27.7655, -97.4640)), address="Bear Lane, Corpus Christi, TX 78405")
    truth("cad_units", "STG-FAIR", role="Texas Task Force 1 Alpha and Bravo stage here from D-1 13:00 local (convoy TF1-CC-0913 arrives 18:47 local).", sources=["EVT-1701"])

    # ---- units
    def unit(uid, agency, utype, home, desc, vehicle=None, staffing=None, avl=True, **extra):
        rec = {"unit_id": uid, "agency": agency, "type": utype, "home_station": home, "description": desc}
        if vehicle:
            rec["vehicle"] = vehicle
        if staffing is not None:
            rec["staffing"] = staffing
        rec["avl_equipped"] = avl
        rec.update(extra)
        units.append(rec)

    # fire: engines at every station, existing specials kept
    engine_desc = {n: d for n, _, d, _, _ in CCFD_STATIONS}
    for n, _, district, _, _ in CCFD_STATIONS:
        unit(f"E-{n}", "CCFD", "engine", f"STA-{n}", f"Engine {n} - {district}", "Pumper", 4)
    for uid, typ, home, desc, veh, crew in [
        ("T-1", "truck", "STA-1", "Truck 1 - Downtown", "Aerial ladder truck", 4), ("T-3", "truck", "STA-3", "Truck 3 - Calallen", "Aerial ladder truck", 4),
        ("T-5", "truck", "STA-5", "Truck 5 - Rodd Field", "Aerial ladder truck", 4), ("L-7", "ladder", "STA-7", "Ladder 7 - South Staples", "Aerial ladder truck", 4),
        ("L-10", "ladder", "STA-10", "Ladder 10 - Padre Island", "Aerial ladder truck", 4), ("R-1", "rescue", "STA-1", "Rescue 1 - Downtown heavy rescue", "Heavy rescue", 4),
        ("R-5", "rescue", "STA-5", "Rescue 5 - water rescue", "Heavy rescue", 4), ("BC-1", "battalion_chief", "STA-1", "Battalion Chief 1", "Command SUV", 1),
        ("BC-2", "battalion_chief", "STA-7", "Battalion Chief 2", "Command SUV", 1), ("BC-3", "battalion_chief", "STA-5", "Battalion Chief 3", "Command SUV", 1),
        ("HM-1", "hazmat", "STA-8", "Hazmat 1", "Hazardous materials unit", 4), ("FU-1", "foam", "STA-14", "Foam Unit 1", "Industrial foam unit", 3),
        ("WTR-1", "water_tender", "STA-3", "Water Tender 1", "Water tender", 2), ("WTR-5", "water_tender", "STA-5", "Water Tender 5", "Water tender", 2),
        ("FC-1", "fire_command", "STA-1", "Fire Command 1", "Command vehicle", 2),
        ("BOAT-1", "fireboat", "STA-6", "Fireboat 1 - North Beach", "Fireboat", 3), ("BOAT-2", "swiftwater", "STA-5", "Swift-water boat 2", "Inflatable rescue boat on trailer", 3)]:
        unit(uid, "CCFD", typ, home, desc, veh, crew)
    # rescue boat roster (canon hull ids CC-SAR-001..023), high-clearance vehicles (4), welfare-check teams (8)
    boat_homes = ["STA-5", "STA-18", "STA-6", "STA-3", "STA-10", "STA-16", "STA-1", "STA-14"]
    for i in range(1, 24):
        unit(f"CC-SAR-{i:03d}", "CCFD", "rescue_boat", boat_homes[(i - 1) % len(boat_homes)], f"Rescue boat, hull CC-SAR-{i:03d}", "Flat-bottom rescue boat on trailer", 3)
    for i in range(1, 5):
        unit(f"HWV-{i}", "CCFD", "high_water_vehicle", ["STA-5", "STA-18", "STA-3", "STA-1"][i - 1], f"High-clearance vehicle {i}", "High-clearance truck", 3)
    for i in range(1, 9):
        unit(f"WC-{i}", "CCFD", "welfare_check_team", ["STA-8", "STA-13", "STA-14", "STA-2", "STA-4", "STA-9", "STA-12", "STA-15"][i - 1],
             f"Welfare-check team {i} (two-person)", "Brush truck", 2)
    # EMS
    medic_home = {1: "STA-1", 2: "STA-2", 3: "STA-3", 4: "STA-7", 5: "STA-5", 6: "STA-6", 7: "STA-8", 8: "STA-10", 9: "STA-11", 10: "STA-12",
                  11: "STA-14", 12: "STA-7", 13: "STA-1", 14: "STA-2", 15: "STA-5", 16: "STA-3", 17: "STA-10", 18: "STA-8"}
    for n, home in medic_home.items():
        als = n <= 14
        unit(f"M-{n}", "CCEMS", "als_ambulance" if als else "bls_ambulance", home, f"Medic {n}", "Type I ambulance", 2, service_level="ALS" if als else "BLS")
    for uid, typ, home, desc in [("M-19", "supervisor", "STA-1", "EMS supervisor 1"), ("M-20", "supervisor", "STA-7", "EMS supervisor 2"),
                                 ("MCI-1", "mci_unit", "STA-1", "Mass-casualty unit"), ("MCI-2", "mci_support", "STA-7", "Mass-casualty support trailer")]:
        unit(uid, "CCEMS", typ, home, desc, staffing=2)
    # police (kept as they were)
    for u in legacy["CCPD"]["units"]:
        unit(u["unit_id"], "CCPD", u["type"], "PD-HQ", u["description"], u.get("vehicle"), 1, beat=u.get("beat"))
    for u in legacy["NCSO"]["units"]:
        marine = u["type"] == "marine"
        unit(u["unit_id"], "NCSO", u["type"], "SO-MAIN" if u["type"] in ("supervisor", "lieutenant", "command", "evacuation") else "SO-ANNEX",
             u["description"], u.get("vehicle"), 2 if marine else 1, district=u.get("district"))
    # mutual aid (ids kept from the old registry)
    ma_units = [("MA-ROBS-E1", "MA_FIRE", "mutual_aid_engine", "MA-STA-ROBS", "Robstown engine"), ("MA-ROBS-T1", "MA_FIRE", "mutual_aid_truck", "MA-STA-ROBS", "Robstown truck"),
                ("MA-ROBS-M1", "MA_EMS", "mutual_aid_als", "MA-STA-ROBS", "Robstown ambulance"),
                ("MA-SANPAT-E1", "MA_FIRE", "mutual_aid_engine", "MA-STA-PORT", "San Patricio County engine (Portland)"),
                ("MA-SANPAT-WT1", "MA_FIRE", "mutual_aid_tender", "MA-STA-INGL", "San Patricio County water tender (Ingleside)"),
                ("MA-SANPAT-M1", "MA_EMS", "mutual_aid_als", "MA-STA-SANPAT", "San Patricio County ambulance 1"),
                ("MA-SANPAT-M2", "MA_EMS", "mutual_aid_als", "MA-STA-APAS", "San Patricio County ambulance 2 (Aransas Pass)"),
                ("MA-SINTON-E1", "MA_FIRE", "mutual_aid_engine", "MA-STA-SINT", "Sinton engine"),
                ("MA-ANNA-E1", "MA_FIRE", "mutual_aid_engine", "MA-STA-ANNA", "Annaville engine"),
                ("MA-FBFD-E1", "MA_FIRE", "mutual_aid_engine", "MA-STA-FBFD", "Flour Bluff (county ESD) engine"),
                ("MA-FBFD-B1", "MA_FIRE", "rescue_boat", "MA-STA-FBFD", "Flour Bluff (county ESD) rescue boat")]
    for uid, ag, typ, home, desc in ma_units:
        unit(uid, ag, typ, home, desc, staffing=4 if "engine" in typ or "truck" in typ else 2, avl=False, mutual_aid=True)
    for uid, ag, typ, base, desc in [("MA-ALICE-E1", "MA_FIRE", "mutual_aid_engine", "Alice, TX", "Alice engine 1"), ("MA-ALICE-E2", "MA_FIRE", "mutual_aid_engine", "Alice, TX", "Alice engine 2"),
                                     ("MA-ALICE-M1", "MA_EMS", "mutual_aid_als", "Alice, TX", "Alice ambulance 1"), ("MA-ALICE-M2", "MA_EMS", "mutual_aid_als", "Alice, TX", "Alice ambulance 2"),
                                     ("MA-BISHOP-E1", "MA_FIRE", "mutual_aid_engine", "Bishop, TX", "Bishop engine"), ("MA-VICTORIA-M1", "MA_EMS", "mutual_aid_als", "Victoria, TX", "Victoria ambulance"),
                                     ("MA-BEEVILLE-M1", "MA_EMS", "mutual_aid_als", "Beeville, TX", "Bee County ambulance"),
                                     ("USAR-TX-1", "TF1", "usar", "College Station, TX", "Texas Task Force 1 urban search and rescue element")]:
        unit(uid, ag, typ, "STG-FAIR", desc, staffing=4 if "engine" in typ else (2 if "als" in typ else 30), avl=False, mutual_aid=True, home_base=base)
    unit("TF1-ALPHA", "TF1", "swiftwater_team", "STG-FAIR", "Texas Task Force 1 swift-water team Alpha", "Convoy with boats", 14, avl=True, mutual_aid=True, home_base="San Antonio, TX")
    unit("TF1-BRAVO", "TF1", "swiftwater_team", "STG-FAIR", "Texas Task Force 1 swift-water team Bravo", "Convoy with boats", 14, avl=True, mutual_aid=True, home_base="San Antonio, TX")
    for i in range(1, 5):
        unit(f"TXARNG-HWV-{i}", "TXARNG", "high_water_vehicle", "STG-FAIR", f"Texas Army National Guard high-water vehicle {i}", "Light medium tactical vehicle", 3, avl=False, mutual_aid=True, home_base="Texas Army National Guard")
    unit("MTF-9", "FEMA", "medical_task_force", "STG-FAIR", "FEMA Medical Task Force 9", "Medical convoy", 35, avl=False, mutual_aid=True, home_base="San Antonio, TX")
    for i in range(1, 11):
        unit(f"NC-BUS-{i:02d}", "NCOEM", "evacuation_bus", "BUS-DEPOT", f"County evacuation bus {i}", "Transit bus", 1)
    for i in range(1, 88):
        unit(f"CIV-BOAT-{i:03d}", "CIVBOAT", "civilian_boat", "STG-FAIR", f"Credentialed civilian boat {i} (Corpus Christi Boating Association)", "Private boat", 2, avl=True, mutual_aid=True)
    unit("PA-M1", "PAPD", "als_ambulance", "PA-PS", "Port Aransas ambulance", "Type I ambulance", 2, service_level="ALS")
    unit("PA-1", "PAPD", "patrol", "PA-PS", "Port Aransas patrol unit", "Patrol SUV", 1)

    truth("cad_units", "_availability", note="Mutual-aid and state/federal units are not in the area before the storm. Arrival: TF1-ALPHA/BRAVO D-1 18:47 local; San Patricio and Bee County dispatch mutual aid at D0; MTF-9 arrives D+6 and stands down from D+8; civilian boat pool integrated D+3 (87 hulls, GPS trackers on); welfare-check teams (8) work from D+5 17:00 local.",
          sources=["EVT-1701", "EVT-1705", "EVT-1605", "EVT-1303"])
    truth("cad_units", "WC-1", role="Two-person welfare-check units answer the 11 false 'trapped survivor' calls near SUB-02 and SUB-03, D+7 to D+10 (T17/T13).", sources=["EVT-1707"])
    for u in legacy["CCFD"]["units"] + legacy["CCEMS"]["units"]:
        if u.get("station") and u["unit_id"] not in ("E-1",):
            pass
    migrate("cad_units", "agencies.<AGENCY>.units / agencies.CCFD.stations (nested lists)", "units / stations (top-level lists)", "old cad_units.json", "same unit ids; stations now carry real coordinates")
    migrate("cad_units", "STA-5 'Flour Bluff' (10125 Rodd Field Rd)", "STA-5 (Rodd Field Road site)", "old cad_units.json", "address was invented; now the real station site on Rodd Field Road")
    migrate("cad_units", "MA_FIRE / MA_EMS agency codes in 911_cad_records.csv", "agencies MA_FIRE / MA_EMS", "05_other_sources/911", "now defined")

    agencies = {
        "CCPD": {"name": "Corpus Christi Police Department", "radio_system": legacy["CCPD"]["radio_system"], "dispatch_channel": legacy["CCPD"]["dispatch_channel"], "beats": legacy["CCPD"]["beats"]},
        "CCFD": {"name": "Corpus Christi Fire Department", "radio_system": legacy["CCFD"]["radio_system"], "dispatch_channel": legacy["CCFD"]["dispatch_channel"]},
        "CCEMS": {"name": "Corpus Christi Emergency Medical Services", "radio_system": legacy["CCEMS"]["radio_system"], "dispatch_channel": legacy["CCEMS"]["dispatch_channel"],
                  "note": "Medic units are housed in fire stations."},
        "NCSO": {"name": "Nueces County Sheriff's Office", "radio_system": legacy["NCSO"]["radio_system"], "dispatch_channel": legacy["NCSO"]["dispatch_channel"],
                 "jurisdiction_note": legacy["NCSO"].get("jurisdiction_note")},
        "PAPD": {"name": "Port Aransas Public Safety", "dispatch_channel": "PAPD-DISP-1"},
        "MA_FIRE": {"name": "Mutual aid - fire (neighbouring departments)", "dispatch_channel": "MA-FIRE-1"},
        "MA_EMS": {"name": "Mutual aid - EMS (neighbouring services)", "dispatch_channel": "MA-EMS-1"},
        "TF1": {"name": "Texas Task Force 1", "dispatch_channel": "NuecesNet SAR"},
        "TXARNG": {"name": "Texas Army National Guard", "dispatch_channel": "NuecesNet SAR"},
        "FEMA": {"name": "Federal Emergency Management Agency", "dispatch_channel": "NuecesNet"},
        "NCOEM": {"name": "Nueces County Office of Emergency Management", "dispatch_channel": "NuecesNet"},
        "CIVBOAT": {"name": "Credentialed civilian boat pool (Corpus Christi Boating Association)", "dispatch_channel": "NuecesNet SAR"},
    }
    for a in agencies:
        agencies[a]["unit_count"] = sum(1 for u in units if u["agency"] == a)
    for s in stations:
        s["units"] = [u["unit_id"] for u in units if u["home_station"] == s["station_id"]]
    doc = {"schema_version": "2.0", "generated": TODAY, "jurisdiction": old["jurisdiction"], "cad_system": old["cad_system"],
           "event": {"name": "Hurricane Rafael", "location": "Corpus Christi, TX"},
           "note": "Stations sit on real station sites or beside real roads (see position_basis); station numbers and unit ids are fictional. Units flagged avl_equipped report vehicle locations.",
           "agencies": agencies, "stations": stations, "units": units,
           "nature_codes": old["nature_codes"], "disposition_codes": old["disposition_codes"], "priority_levels": old["priority_levels"]}
    return doc


# ======================================================================================
# 3. INFRASTRUCTURE
# ======================================================================================
def build_infra(fac_by_id):
    assets = []

    def add(aid, name, atype, pos, operator="Coastal Bend Power and Water Authority", parent=None, serves=None, aliases=None, **extra):
        rec = {"asset_id": aid, "name": name, "asset_type": atype, "operator": operator}
        if parent:
            rec["parent_asset_id"] = parent
        if aliases:
            rec["aliases"] = aliases
        if serves:
            rec["serves"] = serves
        rec.update({k: pos[k] for k in ("latitude", "longitude", "position_basis")})
        rec.update(extra)
        rec["_lm"] = pos.get("_lm")
        assets.append(finish(rec, "infrastructure_assets", aid))
        return rec

    def child_pos(parent_rec):
        return {"latitude": parent_rec["latitude"], "longitude": parent_rec["longitude"], "position_basis": f"at parent site {parent_rec['asset_id']}"}

    T = lambda aid, **kw: truth("infrastructure_assets", aid, **kw)

    # ---------------- power
    s1 = add("GW-FAC-SUB-01", "Riverside Switching Station", "substation", placed(r"Up River Rd", (27.812, -97.455)),
             address="4201 Up River Road, Corpus Christi, TX", voltage_kv="345/138", serves=["GW-FAC-SUB-02", "GW-FAC-SUB-03", "GW-FAC-UTL-01"],
             aliases=["SUB-01", "INF-CC-2027-00004"], scada_tag_prefix="GW.SUB1", rtu_id="GW-SYS-RTU-01", maximo_location="SUB-01",
             equipment=[{"equipment_id": "GW-SUB01-BKR-MAIN", "name": "Main breaker", "scada_tag_prefix": "GW.SUB1.BKR1"},
                        {"equipment_id": "GW-SUB01-REL-27", "name": "Undervoltage relay 27-UV", "scada_tag_prefix": "GW.SUB1.REL"}])
    s2 = add("GW-FAC-SUB-02", "Harbor View Substation", "substation", placed(r"Navigation Blvd", (27.803, -97.447)),
             address="4821 Navigation Blvd, Corpus Christi, TX", voltage_kv="138/69", parent="GW-FAC-SUB-01",
             serves=["AREA-NBH-HILLCREST", "AREA-NBH-OAKPARK", "AREA-NBH-INNERHARBOR"], aliases=["SUB-02", "Harbor View Switching Station", "Harbor View"],
             scada_tag_prefix="GW.SUB2", rtu_id="GW-SYS-RTU-02", maximo_location="SUB-02",
             equipment=[{"equipment_id": "GW-SUB02-BKR-MAIN", "name": "Main breaker CB-7", "scada_tag_prefix": "GW.SUB2.BKR1"}])
    s3 = add("GW-FAC-SUB-03", "Crosstown Substation", "substation", placed(r"Crosstown", (27.770, -97.415)),
             address="2201 Crosstown Expressway service road, Corpus Christi, TX", voltage_kv="138/69", parent="GW-FAC-SUB-01",
             serves=["AREA-WD-3", "AREA-WD-4", "GW-FAC-UTL-01"], aliases=["SUB-03", "Crosstown Feeder Station", "Crosstown"],
             scada_tag_prefix="GW.SUB3", rtu_id="GW-SYS-RTU-03", maximo_location="SUB-03",
             equipment=[{"equipment_id": "GW-SUB03-BKR-MAIN", "name": "Main breaker", "scada_tag_prefix": "GW.SUB3.BKR1"}])
    add("GW-FAC-SUB-04", "Southside Substation", "substation", placed(r"Ayers St", (27.742, -97.421)), address="5800 Ayers St, Corpus Christi, TX",
        voltage_kv="138/69", serves=["AREA-WD-2"], aliases=["SUB-04", "INF-CC-2027-00005"], scada_tag_prefix="GW.SUB4", rtu_id="GW-SYS-RTU-04", maximo_location="SUB-04")
    s5 = add("GW-FAC-SUB-05", "Bayside Substation", "substation", placed(r"Ennis Joslin", (27.700, -97.335)), address="Ennis Joslin Road, Corpus Christi, TX",
             voltage_kv="138", serves=["AREA-WD-5", "GW-FAC-DSS-01"], aliases=["SUB-05"], scada_tag_prefix="GW.SUB5", rtu_id="GW-SYS-RTU-05", maximo_location="SUB-05")
    add("GW-FAC-DSS-01", "McKinley Substation", "distribution_substation", placed(r"Morgan Ave", (27.778, -97.400)), address="Morgan Avenue, Corpus Christi, TX",
        voltage_kv="69/12.5", parent="GW-FAC-SUB-05", serves=["FAC-SRMC-001", "AREA-NBH-DOWNTOWN"], aliases=["McKinley"])
    add("GW-FAC-GEN-01", "Palisade Energy Center", "generation", placed(r"Nueces Bay Blvd", (27.817, -97.418)), address="Nueces Bay Boulevard, Corpus Christi, TX",
        fuel="natural gas", capacity_mw=390, scada_tag_prefix="GW.GEN1")
    ops = add("GW-FAC-OPS-01", "CBPWA Operations Center", "operations_center", placed(r"Leopard St", (27.7965, -97.418)), address="Leopard Street, Corpus Christi, TX",
              aliases=["CBPWA Security Operations Center", "CBPWA Operations Center, Corpus Christi"], hosts=["GW-SYS-SCADA-01", "GW-SYS-HST-01"], phone="(361) 555-0280")
    # main breaker and undervoltage relay on every substation; breaker labels follow the tag catalogue when it exists
    labels = {}
    try:
        for t in json.load(open(os.path.join(OUT, "scada_tags.json"), encoding="utf-8"))["tags"]:
            m = re.search(r"Main breaker (CB-\d+)", t.get("description", ""))
            if m and str(t.get("equipment_id", "")).endswith("BKR-MAIN"):
                labels[t["equipment_id"]] = m.group(1)
    except (OSError, KeyError, ValueError):
        pass
    labels.setdefault("GW-SUB02-BKR-MAIN", "CB-7")
    for a in assets:
        m = re.match(r"GW-FAC-SUB-0(\d)$", a["asset_id"])
        if m:
            n = m.group(1)
            bid = f"GW-SUB0{n}-BKR-MAIN"
            a["equipment"] = [{"equipment_id": bid, "name": "Main breaker" + (f" {labels[bid]}" if bid in labels else ""), "scada_tag_prefix": f"GW.SUB{n}.BKR1"},
                              {"equipment_id": f"GW-SUB0{n}-REL-27", "name": "Undervoltage relay 27-UV", "scada_tag_prefix": f"GW.SUB{n}.REL"}]
            a["equipment_detail"] = "06_data_streams/scada_tags.json (feeders, relays, transformer, bus)"
        if a["asset_id"] == "GW-FAC-DSS-01":
            a["equipment"] = [{"equipment_id": "GW-DSS01-BKR-MAIN", "name": "Main breaker", "scada_tag_prefix": "GW.DSS1.BKR1"}]
            a["scada_tag_prefix"] = "GW.DSS1"
            a["equipment_detail"] = "06_data_streams/scada_tags.json"
    T("GW-FAC-SUB-01", role="Relay undervoltage threshold changed 0.88 to 0.94 pu at D-3 17:00Z; trips at 07:12Z on D0 adding about 24,000 customers to the storm outage. First drone sortie target (D-10).", sources=["GW-EVT-003", "GW-EVT-004", "EVT-1901"])
    T("GW-FAC-SUB-02", role="Breaker-open command to CB-7 at D+7 14:30Z (8,400 customers); final restoration D+35. Follow-up inspection flagged by the FEMA survey (PUB-112). False 'trapped survivor' calls cluster around it D+7 to D+10.", sources=["GW-EVT-005", "GW-EVT-015", "PUB-112", "EVT-1707"])
    T("GW-FAC-SUB-03", role="Breaker-open at D+10 19:45Z (6,800 customers; backup feed to the water plant pump room lost); restored D+35.", sources=["GW-EVT-007", "GW-EVT-015", "PUB-112"])
    T("GW-FAC-SUB-04", role="Not operated maliciously; a relay configuration timestamp of D-3 was later found on its RTU.", sources=["GW-EVT-010"])
    T("GW-FAC-SUB-05", role="Unaffected comparison baseline.")
    T("GW-FAC-DSS-01", role="Feeder substation for Shoreline Regional Medical Center. Storm outage from 06:17Z D0; restored 09:14 local D+8. It is not one of the five transmission substations, which is why the hospital stays on commercial power when SUB-02 and SUB-03 are opened. Named in influence-operation posts on D0 (EVT-1504).",
      sources=["EVT-1602", "EVT-1605", "EVT-1504"], decision="Alias resolved 2026-11-09: 69/12.5 kV distribution substation fed from Bayside (SUB-05).")
    T("GW-FAC-OPS-01", role="Workstation GW-WS-OPS-02 here issued the D+7 breaker command with no operator logged in.", sources=["GW-EVT-005", "GW-PUB-101"], placement_note="Canon gives no address.")
    T("_placement", note="Substation street addresses come from the thread designs (EVT-1901, EVT-1707, old registry); each asset is placed beside that real road. The designs' own coordinates (for example 27.8041N 97.3975W for 'Harbor View area') pre-date the real geography and are superseded.")

    # ---------------- water
    plant = add("GW-FAC-UTL-01", "O.N. Stevens Water Treatment Plant", "water_treatment_plant", at_site("O.N. Stevens Water Treatment Plant", "water_plant"),
                address="Up River Road at Calallen, Corpus Christi, TX 78410", capacity_mgd=75, aliases=["FAC-UTL-01", "INF-CC-2027-00003", "WATER-PLANT", "The O.N. Stevens Water Treatment Plant"],
                serves=["AREA-WD-1", "AREA-WD-2", "AREA-WD-3", "AREA-WD-4", "AREA-WD-5"], scada_tag_prefix="GW.UTL1", permit="WQ-2019-0074-PWS")
    for i in range(1, 5):
        add(f"EQP-110{i}", f"High-service pump P-{i}", "pump", child_pos(plant), parent="GW-FAC-UTL-01",
            aliases=[f"P-{i}", f"GW-PP1-PUMP{i}"], scada_tag_prefix=f"GW.UTL1.PUMP{i}", maximo_assetnum=f"GW-PP1-PUMP{i}", maximo_location="PUMP-STATION-1", nsn="NSN-SYN-4320-0001")
    for aid, name, typ, al in [("EQP-1110", "High-service pump station (C-pump station)", "pump_station", ["PUMP-STATION-1", "C-pump station"]),
                               ("EQP-1120", "Raw water intake, primary", "intake", ["raw water intake"]),
                               ("EQP-1121", "Raw water intake, secondary (800 m upstream)", "intake", []),
                               ("EQP-1130", "Chemical feed system", "chemical_feed", ["GW-PP1-CHEM-FEED"]),
                               ("EQP-1140", "Plant standby generator", "generator", ["GW-GEN-01"])]:
        add(aid, name, typ, child_pos(plant), parent="GW-FAC-UTL-01", aliases=al)
    lines = add("FAC-UTL-02", "Transmission feeds to O.N. Stevens", "transmission_line_group", placed(r"Up River Rd", (27.858, -97.616)),
                parent="GW-FAC-UTL-01", serves=["GW-FAC-UTL-01"],
                feeds=[{"feed_id": "FAC-UTL-02-A", "name": "Primary feed", "from": "GW-FAC-SUB-01"}, {"feed_id": "FAC-UTL-02-B", "name": "Backup feed (pump room)", "from": "GW-FAC-SUB-03"}])
    tank_sites = [("GW-FAC-TK-01", "Northwest Storage Tank 1", 6, r"Leopard St", (27.846, -97.588), "AREA-PZ-1"), ("GW-FAC-TK-02", "Northwest Storage Tank 2", 4, r"McKinzie Rd", (27.832, -97.572), "AREA-PZ-1"),
                  ("GW-FAC-TK-03", "Central Storage Tank", 5, r"Baldwin|Morgan Ave", (27.776, -97.425), "AREA-PZ-4"), ("GW-FAC-TK-04", "Southside Tank 1", 4, r"Holly Rd", (27.705, -97.400), "AREA-PZ-2"),
                  ("GW-FAC-TK-05", "Southside Tank 2", 3, r"Yorktown", (27.672, -97.395), "AREA-PZ-2"), ("GW-FAC-TK-06", "East Side Tank", 4, r"Airline Rd", (27.712, -97.362), "AREA-PZ-5"),
                  ("GW-FAC-TK-07", "Calallen Tank", 3, r"Northwest Blvd", (27.862, -97.640), "AREA-PZ-1"), ("GW-FAC-TK-08", "Port District Tank", 2, r"Port Ave", (27.798, -97.414), "AREA-PZ-4"),
                  ("GW-FAC-TK-09", "Clarkwood Tank", 3, r"State Hwy 44|Agnes St", (27.784, -97.535), "AREA-PZ-3")]
    for aid, name, mg, road, near, zone in tank_sites:
        add(aid, name, "water_storage_tank", placed(road, near, max_km=3.5), capacity_mg=mg, serves=[zone], scada_tag_prefix="GW.TK" + aid[-2:])
    tp = [("GW-PT-Z4-01", r"Leopard St", (27.7975, -97.432)), ("GW-PT-Z4-02", r"Port Ave", (27.790, -97.413)), ("GW-PT-Z4-03", r"Agnes St", (27.787, -97.428)),
          ("GW-PT-Z4-04", r"Morgan Ave", (27.777, -97.432)), ("GW-PT-Z4-05", r"Navigation Blvd", (27.794, -97.449)), ("GW-PT-Z4-06", r"Martin Luther King Dr", (27.803, -97.411))]
    for aid, road, near in tp:
        add(aid, f"Zone 4 pressure test point {aid[-2:]}", "pressure_test_point", placed(road, near, setback_m=12), serves=["AREA-PZ-4"])
    T("GW-FAC-UTL-01", role="Both power feeds fail 09:00Z D0; P-2 fails, P-3 overheats; citywide low pressure; raw-water TPH 0.42 mg/L at 06:00Z D+2 (intake switched to the secondary). P-3 discharge setpoint lowered 85 to 68 psi at D+8 21:00 local and restored D+28; P-2 back D+38; certified at full capacity D+42.",
      sources=["EVT-0302", "PUB-025", "EVT-2003", "PUB-190", "GW-EVT-006", "GW-EVT-014", "EVT-0406", "GW-EVT-016"])
    T("EQP-1102", role="P-2: vibration trend from D-55, fails at D0, parts ordered D+2 from SUP-0219 (quoted 9 days, arrive D+36), restored D+38.", sources=["EVT-0102", "EVT-0302", "EVT-0308", "EVT-0406"])
    T("EQP-1103", role="P-3: overheats at D0; target of the D+8 setpoint change.", sources=["EVT-0302", "GW-EVT-006"])
    T("EQP-1104", role="P-4 loses supply when SUB-03 opens at D+10 (Zone 4 falls to 14 psi).", sources=["GW-EVT-007"])
    T("FAC-UTL-02", role="Both feeds fail at D0; the backup feed is lost again when SUB-03 opens at D+10. Hardening planned at D+110.", sources=["EVT-0302", "GW-EVT-007", "PUB-096"])
    T("GW-FAC-TK-01", role="First tank below 50% on D+10.", sources=["scenarios/gridwater/00_scenario/assets.json"])
    T("_pressure_test_points", note="Canon says Zone 4 pressure is above 40 psi 'at all test points' on D+42 but does not list them; six points are defined on real streets inside Districts 3 and 4.")

    # ---------------- wastewater plants (public facilities, real names) = canon sampling sites WW-xx
    for i, lmname in enumerate(["New Broadway WWTF (Corpus Christi)", "Oso WWTP (Corpus Christi)", "Greenwood Plant WWTP (Corpus Christi)",
                                "Laguna Madre WWTP (Corpus Christi / Flour Bluff)", "Whitecap WWTP (Corpus Christi / Padre Island)"], 1):
        nm = lmname.split(" (")[0].replace("WWTF", "Wastewater Treatment Plant").replace("WWTP", "Wastewater Treatment Plant").replace("Plant Wastewater", "Wastewater")
        add(f"WW-0{i}", nm, "wastewater_treatment_plant", at_site(lmname, "wastewater", exact=True), operator="City of Corpus Christi", aliases=["WW-xx"],
            sampling="wastewater surveillance, twice a week")
    T("WW-01", role="Norovirus signal in wastewater from D+5 (PUB-044).", sources=["EVT-0310", "PUB-044"])
    for aid, name, road, near in [("GW-LS-01", "North Beach Lift Station", r"Timon Blvd", (27.823, -97.388)), ("GW-LS-02", "Flour Bluff Lift Station", r"Laguna Shores", (27.655, -97.283)),
                                  ("GW-LS-03", "Molina Lift Station", r"Old Brownsville|Molina", (27.765, -97.445)), ("GW-LS-04", "Hillcrest Lift Station", r"Port Ave", (27.804, -97.414))]:
        add(aid, name, "wastewater_lift_station", placed(road, near, max_km=3.0), operator="City of Corpus Christi")

    # ---------------- bridges, airport
    hb = P.landmark("Harbor Bridge (US 181 over Corpus Christi Ship Channel)", "bridge")
    la, lo, basis, _ = P.abutment((hb["lat"], hb["lon"]))
    add("FAC-INF-01A", "Harbor Bridge", "bridge", {"latitude": la, "longitude": lo, "position_basis": basis}, operator="Texas Department of Transportation",
        route="US 181", aliases=["FAC-INF-01", "INF-CC-2027-00001", "The Harbor Bridge"], span_midpoint={"latitude": P.r5(hb["lat"]), "longitude": P.r5(hb["lon"]), "source": "National Bridge Inventory"},
        connects=["AREA-NBH-DOWNTOWN", "AREA-NBH-NORTHBEACH"])
    nb = P.landmark("Nueces Bay Causeway (US 181 southbound)", "bridge")
    la, lo, basis, _ = P.abutment((nb["lat"], nb["lon"]))
    add("FAC-INF-01B", "Nueces Bay Causeway", "causeway", {"latitude": la, "longitude": lo, "position_basis": basis}, operator="Texas Department of Transportation",
        route="US 181", aliases=["FAC-INF-01"], span_midpoint={"latitude": P.r5(nb["lat"]), "longitude": P.r5(nb["lon"]), "source": "National Bridge Inventory"},
        connects=["AREA-NBH-NORTHBEACH", "AREA-CITY-PORTLAND"])
    jf = P.landmark("JFK Causeway", "bridge")
    la, lo, basis, _ = P.abutment((jf["lat"], jf["lon"]))
    add("FAC-INF-02", "JFK Causeway", "causeway", {"latitude": la, "longitude": lo, "position_basis": basis}, operator="Texas Department of Transportation",
        route="Park Road 22", span_midpoint={"latitude": P.r5(jf["lat"]), "longitude": P.r5(jf["lon"]), "source": "National Bridge Inventory"},
        connects=["AREA-NBH-FLOURBLUFF", "AREA-NBH-PADREISLAND"])
    add("FAC-AIR-CRP", "Corpus Christi International Airport", "airport", at_site("Corpus Christi Intl (CRP/KCRP)", "airport"), operator="City of Corpus Christi",
        aliases=["INF-CC-2027-00010", "KCRP"])
    T("FAC-INF-01A", role="Closed as the storm hit; reopened after inspection on D+3. State review of wind-closure procedures at D+110.", sources=["EVT-0304", "PUB-027", "PUB-036", "PUB-096"])
    T("FAC-INF-01B", role="Closed D0 to D+3 with the Harbor Bridge; cut Portland and North Beach off from downtown.", sources=["PUB-027", "PUB-036"])

    # ---------------- fuel, generators
    add("TANK-0390", "Quellmar Fuel Partners storage terminal", "fuel_terminal", placed(r"Navigation Blvd", (27.8125, -97.4465)),
        operator="Quellmar Fuel Partners", address="Navigation Boulevard, Inner Harbor industrial area, Corpus Christi, TX")
    nas = fac_by_id["FAC-DOD-01"]
    add("EQP-2201", "NAS Corpus Christi backup generator", "generator", placed(None, (27.6905, -97.2810), max_km=2.0), operator="US Navy",
        parent="FAC-DOD-01", nsn="NSN-SYN-6115-0001")
    for aid, name, fid, extra in [("EQP-3101", "Emergency generator", "FAC-SRMC-001", {}), ("EQP-3102", "Diesel tank A", "FAC-SRMC-001", {"capacity_gal": 12000}),
                                  ("EQP-3103", "Diesel tank B", "FAC-SRMC-001", {"capacity_gal": 12000}), ("EQP-3201", "Emergency generator", "FAC-BCMC-002", {}),
                                  ("EQP-3202", "Diesel tank", "FAC-BCMC-002", {"capacity_gal": 6000})]:
        f = fac_by_id[fid]
        add(aid, f"{f['facility_name']} {name.lower()}", "generator" if "generator" in name.lower() else "fuel_tank",
            {"latitude": f["latitude"], "longitude": f["longitude"], "position_basis": f"at parent site {fid}"}, operator=f["facility_name"], parent=fid, **extra)
    T("TANK-0390", role="GPS interference transmitter (JAM-01) operated from a parked vehicle near here D+38 to D+43; supplier of the contaminated NAS fuel.", sources=["EVT-0404", "PUB-074", "EVT-0407"])
    T("EQP-2201", role="Fails on water-contaminated fuel on D+40 (public D+41).", sources=["EVT-0407", "PUB-065"])
    T("EQP-3101", role="Starts 23 s after commercial power loss at 06:17:03Z D0; runs 195 h 03 m; diesel low at D+5 12:00 local.", sources=["EVT-1602", "EVT-1604", "EVT-1605"])

    remote = [
        {"asset_id": "GW-FAC-WTR-01", "name": "Texana Booster Station 1", "asset_type": "water_pump_station", "operator": "Coastal Bend Power and Water Authority", "location_text": "Lake Texana, near Edna, TX",
         "scada_tag_prefix": "GW.WTR1", "position_basis": "outside the reference window; locality only"},
        {"asset_id": "GW-FAC-WTR-02", "name": "Texana Booster Station 2", "asset_type": "water_pump_station", "operator": "Coastal Bend Power and Water Authority", "location_text": "Raw-water pipeline mid-route, about 50 miles from Lake Texana",
         "scada_tag_prefix": "GW.WTR2", "position_basis": "outside the reference window; locality only"},
        {"asset_id": "GW-FAC-WTR-03", "name": "Colorado River Booster Station", "asset_type": "water_pump_station", "operator": "Coastal Bend Power and Water Authority", "location_text": "Near Bay City, TX",
         "scada_tag_prefix": "GW.WTR3", "position_basis": "outside the reference window; locality only"},
    ]
    T("GW-FAC-WTR-03", role="Booster setpoint changed in the same session as the P-3 change (02:04Z D+9).", sources=["GW-EVT-013"])

    for old, new, note in [("EQP-1101 to 1104", ["EQP-1101", "EQP-1102", "EQP-1103", "EQP-1104"], "scenario ids kept as the equipment ids"),
                           ("GW-PP1-PUMP1..4 (work orders ASSETNUM)", ["EQP-1101", "EQP-1102", "EQP-1103", "EQP-1104"], "now `maximo_assetnum` on each pump"),
                           ("GW.UTL1.PUMP1..4 (historian tags)", ["EQP-1101", "EQP-1102", "EQP-1103", "EQP-1104"], "now `scada_tag_prefix` on each pump"),
                           ("GW-GEN-01 (work orders, location WATER-PLANT)", "EQP-1140", "the water plant's standby generator, not the Navy generator"),
                           ("EQP-2201", "EQP-2201", "NAS Corpus Christi backup generator (unchanged)"),
                           ("FAC-UTL-01", "GW-FAC-UTL-01", "historian asset id; FAC-UTL-01 kept as an alias"),
                           ("FAC-INF-01", ["FAC-INF-01A", "FAC-INF-01B"], "bridge and causeway are separate assets"),
                           ("INF-CC-2027-00002 (ship channel levee)", None, "removed: not in canon"),
                           ("INF-CC-2027-00006 (SPID commercial corridor)", None, "removed: an area, not an asset"),
                           ("INF-CC-2027-00007 (North Beach residential area)", "AREA-NBH-NORTHBEACH", "see areas.json"),
                           ("INF-CC-2027-00008 (INAMAR Petroleum Terminal)", "TERM-01 (terminal_registry.json)", "not canon; the canon terminal is Rendal Terminals, owned by the maritime registry"),
                           ("INF-CC-2027-00009 (Calallen flood control channel)", None, "removed: not in canon"),
                           ("McKinley Substation", "GW-FAC-DSS-01", "distribution substation feeding SRMC"),
                           ("critical_infrastructure (list key)", "assets", "list key renamed; `structure_id` is now `asset_id`")]:
        migrate("infrastructure_assets", old, new, "old registries, 00_scenario, 05_other_sources/maintenance and telemetry", note)
    return assets, remote


# ======================================================================================
# 4. SENSORS
# ======================================================================================
def water_point(lat, lon, what, need_channel=None, min_clear=0):
    if G.is_land(lat, lon):
        raise ValueError(f"{what}: {lat},{lon} is on land")
    ch = G.channel_at(lat, lon, 0)
    if need_channel and (not ch or need_channel not in ch):
        raise ValueError(f"{what}: expected channel {need_channel}, got {ch}")
    if G.land_clearance_m(lat, lon) < min_clear:
        raise ValueError(f"{what}: only {G.land_clearance_m(lat, lon):.0f} m of water")
    return ch


def channel_centroid(reach_id):
    it = next(i for i in G.channels.items if i["props"]["reach_id"] == reach_id)
    c = it["xy"][:-1].mean(axis=0)
    return float(c[1]), float(c[0])


def nearest_nav_node(reach_prefix, near):
    best = None
    for p, r in zip(G.nav.nodes, G.nav.reach):
        if r.startswith(reach_prefix):
            d = geo.dist_m(p, near)
            if best is None or d < best[0]:
                best = (d, p)
    return best[1]


def build_sensors(assets_by_id):
    T = lambda sid, **kw: truth("sensor_registry", sid, **kw)
    sondes = []
    spec = [
        ("WQ-01", "Inner Harbor - Industrial Canal", "CESWG_CC_09_INC", (27.8175, -97.4250), "centreline of the USACE Industrial Canal reach"),
        ("WQ-02", "Inner Harbor entrance at the Harbor Bridge", "CESWG_CC_07_BTB", (27.8120, -97.3900), "centreline of the USACE reach between Beacon 82 and the Main Turning Basin"),
        ("WQ-05", "Inner Harbor - Tule Lake Channel", "CESWG_CC_12_TLC", (27.8200, -97.4600), "centreline of the USACE Tule Lake Channel reach"),
    ]
    for sid, name, reach, near, how in spec:
        lat, lon = nearest_nav_node(reach, near)
        ch = water_point(lat, lon, sid, reach)
        sondes.append({"sensor_id": sid, "sensor_name": name, "sensor_type": "Multiparameter water-quality sonde", "operator": "Texas General Land Office / TCEQ",
                       "latitude": P.r5(lat), "longitude": P.r5(lon), "position_basis": f"in water on the {how} ({ch})", "water_body": "Corpus Christi Ship Channel, Inner Harbor",
                       "installation": "piling mount", "parameters": ["dissolved_oxygen_mgL", "turbidity_NTU", "total_hydrocarbons_ppb", "temperature_C", "conductivity_uScm", "pH"],
                       "reporting_interval_minutes": 15})
    for sid, name, pt, body in [("WQ-03", "Nueces Bay - southwest", (27.8520, -97.4450), "Nueces Bay"),
                                ("WQ-04", "Corpus Christi Bay - mid-bay", (27.7700, -97.2500), "Corpus Christi Bay"),
                                ("WQ-06", "Corpus Christi Bay - off North Beach", (27.8250, -97.3720), "Corpus Christi Bay")]:
        water_point(pt[0], pt[1], sid, min_clear=400)
        sondes.append({"sensor_id": sid, "sensor_name": name, "sensor_type": "Multiparameter water-quality sonde", "operator": "Texas General Land Office / TCEQ",
                       "latitude": pt[0], "longitude": pt[1], "position_basis": f"open water of {body}, {G.land_clearance_m(*pt):.0f} m from the nearest shore in the NOAA land layer",
                       "water_body": body, "installation": "moored buoy", "parameters": ["dissolved_oxygen_mgL", "turbidity_NTU", "total_hydrocarbons_ppb", "temperature_C", "salinity_ppt"],
                       "reporting_interval_minutes": 15})
    sondes.sort(key=lambda s: s["sensor_id"])
    T("WQ-01", role="Sentinel sonde for the Inner Harbor spill (valves open 04:00Z to 05:30Z D0); should react within the hour. Exact relation to the TERM-01 berth is set by the maritime registry.", sources=["EVT-0313", "EVT-2001"])
    T("WQ-03", role="Oil reaches Nueces Bay marshes by D+2.", sources=["PUB-030"])
    T("WQ-06", role="Oil reaches North Beach by D+2 to D+3.", sources=["PUB-030", "NWS-P003-05"])

    def real(lmname, cat, exact=True):
        l = P.landmark(lmname, cat, exact)
        return P.r5(l["lat"]), P.r5(l["lon"]), f"real site: {l['name']} [{l['source'].split(' (')[0]}]", l

    # ---- tide gauges (real NOAA CO-OPS stations)
    tide = []
    for sid, lmname, canon in [("GAUGE-14", "NOAA CO-OPS 8775296 USS Lexington, Corpus Christi Bay", True), ("TG-8775237", "NOAA CO-OPS 8775237 Port Aransas", False),
                               ("TG-8775241", "NOAA CO-OPS 8775241 Aransas, Aransas Pass", False), ("TG-8775792", "NOAA CO-OPS 8775792 Packery Channel", False),
                               ("TG-8775870", "NOAA CO-OPS 8775870 Bob Hall Pier, Corpus Christi", False), ("TG-8774770", "NOAA CO-OPS 8774770 Rockport", False)]:
        la, lo, basis, l = real(lmname, "tide_gauge")
        tide.append({"sensor_id": sid, "sensor_name": l["name"].replace("NOAA CO-OPS ", "NOAA tide gauge "), "station_number": l["source_id"], "sensor_type": "Tide / water-level gauge",
                     "operator": "NOAA National Ocean Service", "latitude": la, "longitude": lo, "position_basis": basis,
                     "parameters": ["water_level_ft_MLLW", "surge_above_predicted_ft", "air_temperature_C", "water_temperature_C", "wind_speed_kt", "barometric_pressure_mb"],
                     "reporting_interval_minutes": 6 if not canon else 15})
    tide[0]["aliases"] = ["NOAA tide gauge on Corpus Christi Bay"]
    T("GAUGE-14", role="Canon bay tide gauge. Offline D0 to D+5 (flooded); surge about 3.4 m at 06:00Z D0 is seen at the other gauges.", sources=["00_scenario/rendering_rules.json", "EVT-0301"])

    # ---- stream gauges (two, per rendering rules)
    stream = []
    la, lo, basis, l = real("I-37 Nueces River bridge (southbound mainlanes)", "bridge")
    stream.append({"sensor_id": "GAUGE-12", "sensor_name": "Nueces River gauge at Calallen", "sensor_type": "Stream gauge (stage, discharge, water quality)", "operator": "USGS / National Weather Service",
                   "latitude": la, "longitude": lo, "position_basis": basis + "; bridge-mounted (the river is not resolved in the NOAA land layer)", "installation": "bridge piling",
                   "parameters": ["stage_ft", "discharge_cfs", "temperature_C", "specific_conductance_uScm"], "reporting_interval_minutes": 15})
    oso = P.road_crossing_water(r"Yorktown", (27.6407, -97.3438), lambda a, b: G.water_override.contains(a, b))
    if not oso:
        raise ValueError("Yorktown Blvd crossing of Oso Bay not found")
    stream.append({"sensor_id": "GAUGE-13", "sensor_name": "Oso Creek gauge at Yorktown Boulevard", "sensor_type": "Stream gauge (stage, discharge)", "operator": "USGS / National Weather Service",
                   "latitude": oso[0], "longitude": oso[1], "position_basis": f"mid-point of the {oso[2]:.0f} m stretch of Yorktown Blvd (Census TIGER) over Oso Bay water (Census areal hydrography); bridge-mounted",
                   "installation": "bridge piling", "parameters": ["stage_ft", "discharge_cfs"], "reporting_interval_minutes": 15})
    T("GAUGE-12", role="Nueces River rises from D-7 with pre-storm rain (EVT-0203).", sources=["EVT-0203", "PUB-016"])
    T("GAUGE-13", role="Second river gauge promised by the rendering rules; no canon event names it.")

    # ---- weather stations and buoys (real)
    wx = []
    for sid, lmname in [("KCRP", "KCRP Corpus Christi Intl (METAR/TAF station)"), ("KNGP", "KNGP Corpus Christi/Truax Field NAS (METAR/TAF station)"),
                        ("KNGW", "KNGW Corpus Christi/Cabaniss Field (station record)"), ("KRAS", "KRAS Port Aransas/Mustang Beach Airport (METAR station)"),
                        ("KRKP", "KRKP Rockport/Aransas County Airport (METAR station)"), ("KTFP", "KTFP Ingleside Regional / McCampbell-Porter (METAR station)"),
                        ("KNQI", "KNQI Kingsville NAS (METAR/TAF station)")]:
        la, lo, basis, l = real(lmname, "weather_station")
        wx.append({"sensor_id": sid, "sensor_name": l["name"].split(" (")[0], "sensor_type": "Automated surface weather station", "operator": "NWS / FAA / US Navy",
                   "latitude": la, "longitude": lo, "position_basis": basis, "parameters": ["wind", "gust", "visibility", "sky", "temperature", "dew_point", "pressure", "precipitation"],
                   "reporting_interval_minutes": 60, "in_delivered_stream": sid in ("KCRP", "KNGP")})
    buoys = []
    for sid, lmname in [("42020", "NDBC buoy 42020"), ("42019", "NDBC buoy 42019")]:
        l = P.landmark(lmname, "buoy")
        buoys.append({"sensor_id": sid, "sensor_name": l["name"].split(" (")[0], "sensor_type": "Moored ocean buoy", "operator": "NOAA National Data Buoy Center",
                      "latitude": P.r5(l["lat"]), "longitude": P.r5(l["lon"]), "position_basis": f"real site: {l['name'].split(' (')[0]} [NOAA NDBC station table]",
                      "parameters": ["wind", "gust", "wave_height", "dominant_period", "pressure", "air_temperature", "water_temperature"], "reporting_interval_minutes": 60})

    # ---- air monitors: 20, as the rendering rules promise. Regulatory-style sites keep the four old ids.
    PAR_REG = ["PM2.5", "ozone", "SO2", "benzene", "total_nonmethane_hydrocarbons", "H2S"]
    PAR_COM = ["PM2.5", "total_VOC", "H2S"]
    air_spec = [
        ("AQS-480-001", "Inner Harbor / Navigation Boulevard", "industrial", ("site", "Corpus Christi Fire Department Station 9", "fire_station"), PAR_REG),
        ("AQS-480-002", "Southside / Cunningham", "neighbourhood", ("site", "Cunningham Middle School", "school"), ["PM2.5", "ozone"]),
        ("AQS-480-003", "Airport", "background", ("site", "KCRP Corpus Christi Intl (METAR/TAF station)", "weather_station"), ["PM2.5", "ozone"]),
        ("AQS-480-004", "North Beach", "industrial", ("beside", r"Timon Blvd", (27.829, -97.384)), PAR_REG),
        ("AQS-480-005", "Hillcrest", "fenceline community", ("beside", None, (27.8070, -97.4165)), PAR_REG),
        ("AQS-480-006", "Oak Park", "fenceline community", ("site", "Oak Park Elementary School", "school"), PAR_REG),
        ("AQS-480-007", "Tuloso-Midway", "industrial", ("site", "Tuloso Midway Middle School", "school"), PAR_REG),
        ("AQS-480-008", "Calallen", "neighbourhood", ("site", "Calallen Middle School", "school"), ["PM2.5", "ozone"]),
        ("AQS-480-009", "Flour Bluff", "neighbourhood", ("site", "Flour Bluff Junior High School", "school"), ["PM2.5", "ozone"]),
        ("AQS-480-010", "Portland shoreline", "community", ("site", "East Cliff Elementary School", "school"), PAR_COM),
        ("AQS-480-011", "Ingleside", "industrial", ("site", "Ingleside Volunteer Fire Department", "fire_station"), PAR_REG),
        ("AQS-480-012", "Port Aransas", "community", ("site", "Port Aransas High School", "school"), PAR_COM),
        ("AQS-480-013", "Molina", "community", ("site", "West Oso Elementary School", "school"), PAR_COM),
        ("AQS-480-014", "Downtown bayfront", "community", ("site", "Corpus Christi City Hall", "venue"), PAR_COM),
        ("AQS-480-015", "Del Mar", "neighbourhood", ("site", "Del Mar College (Heritage Campus)", "school"), ["PM2.5", "ozone"]),
        ("AQS-480-016", "Refinery Row west / Up River Road", "industrial", ("beside", r"Up River Rd", (27.812, -97.488)), PAR_REG),
        ("AQS-480-017", "Gregory", "community", ("site", "Austin Elementary School", "school"), PAR_COM),
        ("AQS-480-018", "Padre Island", "background", ("site", "Seashore Middle Academy", "school"), ["PM2.5", "ozone"]),
        ("AQS-480-019", "NAS Corpus Christi fence line", "community", ("beside", r"Lexington Blvd|N A S Dr|Nas Dr", (27.686, -97.275)), PAR_COM),
        ("AQS-MOB-001", "Mobile air monitoring unit (home base)", "mobile", ("beside", r"Navigation Blvd", (27.7925, -97.4500)), ["benzene", "total_VOC", "H2S", "SO2"]),
    ]
    air = []
    for sid, name, stype, pos, params in air_spec:
        p = at_site(pos[1], pos[2], exact=True) if pos[0] == "site" else placed(pos[1], pos[2], max_km=2.0)
        rec = {"sensor_id": sid, "sensor_name": name, "sensor_type": "Air-quality monitor", "site_type": stype, "operator": "TCEQ" if not sid.startswith("AQS-MOB") else "TCEQ mobile monitoring",
               "latitude": p["latitude"], "longitude": p["longitude"], "position_basis": p["position_basis"], "parameters": params, "reporting_interval_minutes": 15,
               "state_code": "48", "county_code": "355" if name not in ("Portland shoreline", "Ingleside", "Gregory") else "409"}
        if stype == "mobile":
            rec["mobile"] = True
            rec["deployment_rule"] = "Deployed positions are reported with each reading and must lie on a road in the reference network."
        rec["_lm"] = p.get("_lm")
        air.append(finish(rec, "sensor_registry", sid))
    T("AQS-480-001", role="Nearest regulatory monitor to the Inner Harbor spill; respiratory and skin complaints near oiled shorelines D+3 to D+21 (PUB-038, PUB-191).", sources=["PUB-038", "PUB-191"])
    T("_air_monitors", note="Rendering rules promise 20 air-quality sensors at 15-minute readings. The four old ids are kept (AQS-480-001..004, AQS-MOB-001) but all were re-sited: three of the old points were not where their names said and the mobile unit's points were in the ship channel. No public source for real monitor positions was reachable, so monitors sit on real public sites (schools, fire stations, airport weather station) or beside real roads.")

    # ---- bridge wind sensors
    bridge = []
    for sid, aid in [("RWIS-HB-01", "FAC-INF-01A"), ("RWIS-NBC-01", "FAC-INF-01B"), ("RWIS-JFK-01", "FAC-INF-02")]:
        a = assets_by_id[aid]
        bridge.append({"sensor_id": sid, "sensor_name": f"{a['name']} wind sensor", "sensor_type": "Road weather station (wind, gust, deck temperature)", "operator": "Texas Department of Transportation",
                       "asset_id": aid, "latitude": a["latitude"], "longitude": a["longitude"], "position_basis": f"at the land abutment of {aid}",
                       "parameters": ["wind_speed_mph", "gust_mph", "wind_direction"], "reporting_interval_minutes": 5})
    ww = [{"site_id": aid, "sensor_name": f"{assets_by_id[aid]['name']} influent sampler", "sensor_type": "Wastewater surveillance sampling site", "operator": "Corpus Christi-Nueces County Public Health District",
           "asset_id": aid, "latitude": assets_by_id[aid]["latitude"], "longitude": assets_by_id[aid]["longitude"], "position_basis": f"at parent site {aid}",
           "parameters": ["norovirus_GII_copies_per_L", "sars_cov_2_copies_per_L"], "sampling": "twice a week"} for aid in ("WW-01", "WW-02", "WW-03", "WW-04", "WW-05")]

    for old, new, note in [("WQ-05 (Nueces River at Calallen - upstream gauge)", "GAUGE-12", "old WQ-05 was a river gauge; the id WQ-05 is now a sonde in the Tule Lake Channel"),
                           ("WQ-06 (NOAA tide gauge 8775296)", "GAUGE-14", "old WQ-06 was the tide gauge; the id WQ-06 is now a sonde off North Beach"),
                           ("WQ-01..WQ-04", ["WQ-01", "WQ-02", "WQ-03", "WQ-04"], "same ids and water bodies; coordinates moved into real water (WQ-01 and WQ-02 were on land)"),
                           ("AQS-480-001..004, AQS-MOB-001", ["AQS-480-001", "AQS-480-002", "AQS-480-003", "AQS-480-004", "AQS-MOB-001"], "same ids; re-sited"),
                           ("epa_aqs_stations (list key)", "air_monitors", "list key renamed"),
                           ("GAUGE-12, GAUGE-14 (00_scenario/places.json)", ["GAUGE-12", "GAUGE-14"], "now sensor ids"),
                           ("BUOY42019 (weather stream file name)", "42019", "NDBC station id"),
                           ("WW-xx (00_scenario/places.json)", ["WW-01", "WW-02", "WW-03", "WW-04", "WW-05"], "sampling sites at the five city plants with published positions")]:
        migrate("sensor_registry", old, new, "old sensor_registry.json, 05_other_sources/env_sensors and weather, 00_scenario/places.json", note)
    return {"water_quality_sondes": sondes, "air_monitors": air, "tide_gauges": tide, "stream_gauges": stream, "weather_stations": wx, "buoys": buoys,
            "bridge_wind_sensors": bridge, "wastewater_sampling_sites": ww}


# ======================================================================================
# 5. AREAS
# ======================================================================================
TRACT_ANCHOR = {  # tract -> ("lm", landmark name, category) | ("road", (lat, lon)) | None
    "480101": ("road", (27.826, -97.385)), "480201": ("road", (27.838, -97.381), r"Timon|Surfside|Beach Ave|Gulfbreeze|Gulfspray"), "480301": ("road", (27.795, -97.394)), "480401": ("road", (27.816, -97.418)),
    "480501": ("road", (27.806, -97.430)), "480601": ("lm", "Mustang Beach", "community"), "480701": ("road", (27.700, -97.158)), "480801": ("road", (27.600, -97.215)),
    "480901": ("road", (27.660, -97.275)), "481001": ("road", (27.875, -97.625)), "481101": ("road", (27.755, -97.405)), "481201": ("road", (27.765, -97.443)),
    "481301": ("road", (27.806, -97.412)), "481401": ("road", (27.785, -97.435)), "481501": ("road", (27.765, -97.398)), "481601": ("road", (27.800, -97.460)),
    "481701": ("lm", "Cunningham Middle School", "school"), "481801": ("road", (27.740, -97.395)), "481901": ("road", (27.668, -97.300)), "482001": ("road", (27.660, -97.287)),
    "482101": ("road", (27.685, -97.365)), "482201": ("road", (27.734, -97.417)), "482301": ("road", (27.715, -97.362)), "482401": ("lm", "Clarkwood", "community"),
    "482501": ("lm", "Five Points", "community"), "482601": ("lm", "Calallen", "community"), "482701": ("lm", "Violet", "community"), "482801": ("lm", "Annaville", "community"),
    "482901": ("lm", "Robstown", "community"), "483001": ("road", (27.795, -97.655)), "483101": ("lm", "Petronila", "community"), "483201": ("road", (27.727, -97.425)),
    "483301": ("road", (27.705, -97.370)), "483401": ("road", (27.745, -97.445)), "483501": ("road", (27.675, -97.390)), "483601": ("lm", "Chapman Ranch", "community"),
    "483701": ("road", (27.878, -97.648)), "483801": ("lm", "Arlington Heights", "community"), "483901": ("road", (27.660, -97.385)), "484001": ("road", (27.700, -97.430)),
    "484101": ("road", (27.615, -97.225)), "484201": None, "484301": ("lm", "Driscoll", "community"), "484401": None,
    "484501": ("lm", "McNorton", "community"), "484601": ("lm", "Annaville Fire Department Station 2", "fire_station"), "484701": ("lm", "Concordia", "community"),
    "484801": ("lm", "Spring Gardens", "community"), "484901": ("road", (27.812, -97.470)), "485001": ("road", (27.862, -97.602)), "485101": ("road", (27.834, -97.066)),
    "485201": ("lm", "Tierra Grande", "community"), "485301": ("road", (27.598, -97.222)), "485401": ("road", (27.645, -97.285)), "485501": ("road", (27.705, -97.335)),
    "485601": ("nas", None),
}
BEAT_ANCHOR = {"B01": (27.800, -97.395), "B02": (27.798, -97.430), "B03": (27.775, -97.405), "B04": (27.705, -97.385), "B05": (27.782, -97.450), "B06": (27.665, -97.290),
               "B07": (27.615, -97.225), "B08": (27.860, -97.630), "B09": (27.700, -97.330), "B10": (27.745, -97.420), "B11": (27.720, -97.365), "B12": (27.810, -97.440)}
BEAT_HALF_KM = {"B01": 2.5, "B02": 2.5, "B03": 2.5, "B04": 4.0, "B05": 3.0, "B06": 3.5, "B07": 5.0, "B08": 5.0, "B09": 3.5, "B10": 3.0, "B11": 3.5, "B12": 4.0}


LOCAL_STREET_WINDOWS = {  # the windows the full local street grids were collected for (99_reference/geo/SOURCES_roads.md)
    "north_beach": [-97.395, 27.815, -97.375, 27.845], "hillcrest": [-97.425, 27.800, -97.400, 27.815], "molina": [-97.455, 27.755, -97.430, 27.775],
    "flour_bluff": [-97.320, 27.655, -97.285, 27.685], "calallen": [-97.640, 27.855, -97.610, 27.880], "port_aransas": [-97.085, 27.820, -97.050, 27.845],
    "downtown": [-97.405, 27.785, -97.390, 27.805]}


def road_file_box(area):
    feats = json.load(open(os.path.join(geo.GEO_DIR, f"roads_local_{area}.geojson"), encoding="utf-8"))["features"]
    return list(LOCAL_STREET_WINDOWS[area]), len(feats)


def build_areas(facilities, legacy_beats):
    areas = []
    T = lambda aid, **kw: truth("areas", aid, **kw)

    def ref_on_land(lat, lon, what):
        if not G.is_land(lat, lon):
            raise ValueError(f"area reference point for {what} is not on land: {lat},{lon}")
        return {"latitude": P.r5(lat), "longitude": P.r5(lon)}

    def add(aid, name, atype, ref, ref_basis, bbox, extent_basis, within=None, **extra):
        rec = {"area_id": aid, "name": name, "area_type": atype, "reference_point": ref, "reference_point_basis": ref_basis,
               "bbox": bbox, "bbox_order": "lon_min, lat_min, lon_max, lat_max", "extent_basis": extent_basis}
        if within:
            rec["within"] = within
        rec.update(extra)
        areas.append(rec)
        return rec

    lms = G.landmarks

    def city_points(city):
        return [(l["lat"], l["lon"]) for l in lms if re.search(rf",\s*{re.escape(city)},\s*TX", l.get("address") or "") and l.get("in_box", True)]

    # ---------------- counties (canon place ids)
    county_cities = {"PLC-001": ("Nueces County", ["Corpus Christi", "Robstown", "Port Aransas"], ("venue", "Nueces County Courthouse")),
                     "PLC-002": ("San Patricio County", ["Portland", "Ingleside", "Aransas Pass", "Gregory", "Taft", "Sinton", "Odem"], ("venue", "San Patricio County Courthouse")),
                     "PLC-003": ("Aransas County", ["Rockport", "Fulton"], ("venue", "Aransas County Courthouse")),
                     "PLC-004": ("Kleberg County", [], ("military", "NAS Kingsville"))}
    for aid, (name, cities, (cat, lmname)) in county_cities.items():
        l = P.landmark(lmname, cat)
        pts = [p for c in cities for p in city_points(c)]
        bbox = P.box_of(pts) if len(pts) >= 3 else None
        add(aid, name, "county", ref_on_land(l["lat"], l["lon"], name), f"real site: {l['name']}",
            bbox, (f"bounding box of {len(pts)} reference landmarks in {', '.join(cities)}; not the legal boundary" if bbox else "outside the reference window; no extent"),
            fips={"PLC-001": "48355", "PLC-002": "48409", "PLC-003": "48007", "PLC-004": "48273"}[aid])

    # ---------------- cities and towns
    cities = [("CORPUSCHRISTI", "Corpus Christi", "PLC-001", "Corpus Christi"), ("PORTARANSAS", "Port Aransas", "PLC-001", "Port Aransas"), ("ROBSTOWN", "Robstown", "PLC-001", "Robstown"),
              ("PORTLAND", "Portland", "PLC-002", "Portland"), ("INGLESIDE", "Ingleside", "PLC-002", "Ingleside"), ("ARANSASPASS", "Aransas Pass", "PLC-002", "Aransas Pass"),
              ("GREGORY", "Gregory", "PLC-002", "Gregory"), ("TAFT", "Taft", "PLC-002", "Taft"), ("SINTON", "Sinton", "PLC-002", "Sinton"), ("ODEM", "Odem", "PLC-002", "Odem"),
              ("ROCKPORT", "Rockport", "PLC-003", "Rockport"), ("FULTON", "Fulton", "PLC-003", "Fulton"), ("BAYSIDE", "Bayside", "PLC-003", "Bayside")]
    for key, name, county, gnis in cities:
        l = P.landmark(gnis, "community", exact=True)
        pts = city_points(name)
        ref = (l["lat"], l["lon"])
        basis = f"real site: {l['name']} (USGS GNIS populated place)"
        if not G.is_land(*ref):
            la, lo, b2, _ = P.beside(None, ref, max_km=1.5)
            ref, basis = (la, lo), b2 + f"; nearest road to the GNIS point for {name}"
        bbox = P.box_of(pts + [ref]) if len(pts) >= 3 else P.nominal_box(ref[0], ref[1], 2.0)
        add(f"AREA-CITY-{key}", name, "city", ref_on_land(ref[0], ref[1], name), basis, bbox,
            f"bounding box of {len(pts)} reference landmarks with a {name} address; not the city limits" if len(pts) >= 3 else "nominal 4 km box around the reference point",
            within=[county])
    add("AREA-CITY-KINGSVILLE", "Kingsville", "city", None, "outside the reference window", None, "outside the reference window; no extent", within=["PLC-004"])
    add("AREA-CITY-ALICE", "Alice", "city", None, "outside the reference window", None, "outside the reference window; no extent", within=[])

    # ---------------- neighbourhoods and communities named in canon
    cc = "AREA-CITY-CORPUSCHRISTI"
    for key, name, roadfile in [("NORTHBEACH", "North Beach", "north_beach"), ("HILLCREST", "Hillcrest", "hillcrest"), ("MOLINA", "Molina", "molina"),
                                ("FLOURBLUFF", "Flour Bluff", "flour_bluff"), ("CALALLEN", "Calallen", "calallen"), ("DOWNTOWN", "Downtown", "downtown")]:
        bbox, n = road_file_box(roadfile)
        clat, clon = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
        la, lo, basis, _ = P.beside(None, (clat, clon), max_km=1.0)
        add(f"AREA-NBH-{key}", name, "neighbourhood", ref_on_land(la, lo, name), basis + "; nearest street to the centre of the local street file",
            bbox, f"the window for which all {n} Census TIGER local streets were collected (roads_local_{roadfile}.geojson); the core of the neighbourhood, not its full boundary", within=[cc, "PLC-001"],
            local_streets_file=f"99_reference/geo/roads_local_{roadfile}.geojson")
    nbh = [("OAKPARK", "Oak Park", ("lm", "Oak Park Elementary School", "school"), 0.9), ("GREENWOOD", "Greenwood", ("road", (27.745, -97.445)), 1.2),
           ("ANNAVILLE", "Annaville", ("lm", "Annaville", "community"), 2.0), ("VIOLET", "Violet", ("lm", "Violet", "community"), 1.5), ("CLARKWOOD", "Clarkwood", ("lm", "Clarkwood", "community"), 1.5),
           ("SOUTHSIDE", "Southside", ("road", (27.700, -97.385)), 4.0), ("WESTSIDE", "Westside", ("road", (27.782, -97.445)), 2.5), ("PADREISLAND", "Padre Island", ("road", (27.615, -97.225)), 4.0),
           ("MUSTANGISLAND", "Mustang Island", ("road", (27.720, -97.150)), 9.0), ("INNERHARBOR", "Inner Harbor", ("road", (27.812, -97.440)), None),
           ("LEOPARD", "Leopard Street corridor", ("road", (27.797, -97.430)), 2.5), ("DELMAR", "Del Mar", ("lm", "Del Mar College (Heritage Campus)", "school"), 1.0),
           ("TULOSO", "Tuloso", ("lm", "Tuloso Midway High School", "school"), 2.0), ("WASHINGTONCOLES", "Washington-Coles", ("lm", "Coles High School", "school"), 0.7),
           ("NAS", "NAS Corpus Christi", ("nas", None), 3.0)]
    for key, name, anchor, half in nbh:
        if anchor[0] == "lm":
            l = P.landmark(anchor[1], anchor[2], exact=True)
            ref, basis = (l["lat"], l["lon"]), f"real site: {l['name']}"
        elif anchor[0] == "nas":
            p = _nas_site()
            ref, basis = (p["latitude"], p["longitude"]), p["position_basis"]
        else:
            la, lo, b, _ = P.beside(None, anchor[1], max_km=2.0)
            ref, basis = (la, lo), b
        if key == "INNERHARBOR":
            xs = [it["xy"] for it in G.channels.items if re.search(r"CC_(08|09|10|11|12|13|14|15)_", it["props"]["reach_id"])]
            import numpy as np
            allxy = np.vstack(xs)
            bbox = [P.r5(min(allxy[:, 0].min(), ref[1])), P.r5(min(allxy[:, 1].min(), ref[0]) - 0.004), P.r5(max(allxy[:, 0].max(), ref[1])), P.r5(max(allxy[:, 1].max(), ref[0]))]
            ext = "extent of the USACE Inner Harbor channel reaches (Main Turning Basin to Viola Turning Basin), widened about 450 m south to take in the docks and the reference point"
        else:
            bbox = P.nominal_box(ref[0], ref[1], half)
            ext = f"nominal {2 * half:g} km box around the reference point; the neighbourhood boundary is not in the reference set"
        add(f"AREA-NBH-{key}", name, "neighbourhood", ref_on_land(ref[0], ref[1], name), basis, bbox, ext,
            within=[cc, "PLC-001"] if key != "MUSTANGISLAND" else ["PLC-001"])
    T("AREA-NBH-HILLCREST", role="Hillcrest and Oak Park hold many of the last 3,200 customers restored on D+35; adjusters could not reach properties for two weeks.", sources=["NWS-P035-04", "NWS-P025-04"])
    T("AREA-NBH-NORTHBEACH", role="Cut off D0 to D+3 by the bridge and causeway closure; oiled shoreline from D+2.", sources=["PUB-027", "PUB-030"])
    T("AREA-NBH-MOLINA", role="Searches reach Greenwood and Molina on D+2 with water still two to three feet deep.", sources=["NWS-P002-12"])

    # ---------------- ZIP codes (extent from landmark addresses)
    ZIP_CATS = {"school", "fire_station", "police", "venue", "hospital", "ems"}   # street addresses; docks and plants carry mailing ZIPs
    zpts = {}
    for l in lms:
        z = zip_of(l.get("address"))
        if z and z.startswith("78") and l["category"] in ZIP_CATS and G.in_box(l["lat"], l["lon"]) and G.is_land(l["lat"], l["lon"]):
            zpts.setdefault(z, []).append((l["lat"], l["lon"], l["name"], l["category"] in NAMED_OK or l["category"] == "fire_station"))
    zip_names = {"78401": "Downtown / Hillcrest", "78402": "North Beach", "78404": "South Bluff / Del Mar", "78405": "Westside / Molina", "78407": "Hillcrest / Refinery Row",
                 "78408": "Leopard Street / Oak Park", "78409": "Tuloso", "78410": "Calallen / Annaville", "78411": "Central Southside", "78412": "Airline / Bay Area",
                 "78413": "South Staples", "78414": "Southside / Yorktown", "78415": "Kostoryz / South Park", "78416": "Greenwood / Horne", "78417": "Old Brownsville Road",
                 "78418": "Flour Bluff / Padre Island", "78373": "Port Aransas", "78374": "Portland", "78362": "Ingleside", "78336": "Aransas Pass", "78382": "Rockport",
                 "78380": "Robstown", "78359": "Gregory", "78406": "Airport"}
    extra_zip_ref = {"78417": ("road", (27.752, -97.466)), "78406": ("road", (27.7722, -97.4990)), "78402": ("lm", "Texas State Aquarium", "venue"),
                     "78407": ("road", (27.806, -97.418)), "78409": ("road", (27.826, -97.520))}
    for z in sorted(zip_names):
        pts = zpts.get(z, [])
        dropped = 0
        if len(pts) >= 3:      # drop outlying addresses (a few landmark records carry a ZIP far from where they sit)
            import statistics
            mlat, mlon = statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts)
            dist = [geo.dist_m((p[0], p[1]), (mlat, mlon)) for p in pts]
            lim = max(3500.0, 2.5 * statistics.median(dist))
            keep = [p for p, d in zip(pts, dist) if d <= lim]
            dropped, pts = len(pts) - len(keep), keep
        if len(pts) >= 3:
            clat = sum(p[0] for p in pts) / len(pts); clon = sum(p[1] for p in pts) / len(pts)
            public = [p for p in pts if p[3]] or pts
            near = min(public, key=lambda p: geo.dist_m((p[0], p[1]), (clat, clon)))
            ref = (near[0], near[1])
            basis = (f"real site: {near[2]} (the public landmark nearest the centre of the ZIP's landmarks)" if near[3]
                     else "real site: the reference landmark nearest the centre of the ZIP's landmarks")
            bbox = P.box_of([(p[0], p[1]) for p in pts])
            ext = (f"bounding box of {len(pts)} public landmarks whose street address carries this ZIP" + (f" ({dropped} outlying addresses dropped)" if dropped else "")
                   + "; not the postal boundary")
        elif z in extra_zip_ref:
            spec = extra_zip_ref[z]
            if spec[0] == "lm":
                l = P.landmark(spec[1], spec[2], exact=True)
                ref, basis = (l["lat"], l["lon"]), f"real site: {l['name']}"
            else:
                la, lo, b, _ = P.beside(None, spec[1], max_km=2.0)
                ref, basis = (la, lo), b
            bbox, ext = P.nominal_box(ref[0], ref[1], 2.0), "nominal 4 km box around the reference point (fewer than three public landmarks carry this ZIP)"
        elif pts:
            ref, basis = (pts[0][0], pts[0][1]), (f"real site: {pts[0][2]}" if pts[0][3] else "real site: a reference landmark with this ZIP")
            bbox, ext = P.nominal_box(ref[0], ref[1], 2.0), "nominal 4 km box around the reference point (fewer than three public landmarks carry this ZIP)"
        else:
            continue
        add(f"AREA-ZIP-{z}", f"ZIP {z} ({zip_names[z]})", "zip", ref_on_land(ref[0], ref[1], z), basis, bbox, ext, zip=z)
    zip_box = {a["zip"]: a["bbox"] for a in areas if a["area_type"] == "zip"}
    zip_ref = {a["zip"]: a["reference_point"] for a in areas if a["area_type"] == "zip"}

    # ---------------- water districts and pressure zones
    wd = {"1": ("Water District 1 (Northwest: Calallen, Annaville, Tuloso)", ["78410", "78409"]), "2": ("Water District 2 (Southside)", ["78411", "78412", "78413", "78414", "78415"]),
          "3": ("Water District 3", ["78405", "78416", "78417"]), "4": ("Water District 4", ["78401", "78407", "78408"]),
          "5": ("Water District 5 (Bayfront, Flour Bluff and Padre Island)", ["78418", "78402", "78404"])}
    for n, (name, zips) in wd.items():
        z0 = zips[0]
        add(f"AREA-WD-{n}", name, "water_district", zip_ref[z0], f"reference point of ZIP {z0}", P.union_box([zip_box.get(z) for z in zips]),
            "union of the member ZIP boxes" + ("; ZIP membership from the boil-water notice's ZIP list" if n in "34" else "; ZIP membership assigned for the exercise (public notices name only Districts 3 and 4)"),
            within=[cc, "PLC-001"], zips=zips, aliases=[f"District {n}", f"Water District {n}"],
            population=({"3": None, "4": None}.get(n)), described_bounds=("Leopard Street (north), Highway 286 (east), Agnes Street (south), Staples Street (west) - as worded in the notice, for Districts 3 and 4 together" if n in "34" else None))
    for a in areas:
        if a["area_type"] == "water_district":
            for k in ("population", "described_bounds"):
                if a.get(k) is None:
                    a.pop(k, None)
    add("AREA-WD-3-4", "Water Districts 3 and 4 (boil-water notice area)", "water_district_group", zip_ref["78405"], "reference point of ZIP 78405",
        P.union_box([zip_box.get(z) for z in wd["3"][1] + wd["4"][1]]), "union of the member ZIP boxes", within=[cc, "PLC-001"], members=["AREA-WD-3", "AREA-WD-4"],
        zips=wd["3"][1] + wd["4"][1], population=48000, population_basis="about 48,000 residents, as stated in the boil-water notice", pressure_zone="AREA-PZ-4")
    pz = {"1": ["AREA-WD-1"], "2": ["AREA-WD-2"], "3": [], "4": ["AREA-WD-3", "AREA-WD-4"], "5": ["AREA-WD-5"]}
    pz_name = {"1": "Pressure Zone 1 (Northwest)", "2": "Pressure Zone 2 (Southside)", "3": "Pressure Zone 3 (West / Clarkwood)", "4": "Pressure Zone 4 (Zone 4 distribution system)", "5": "Pressure Zone 5 (East / Islands)"}
    by_id = {a["area_id"]: a for a in areas}
    for n, members in pz.items():
        if members:
            ref, basis, bbox, ext = by_id[members[0]]["reference_point"], f"reference point of {members[0]}", P.union_box([by_id[m]["bbox"] for m in members]), "union of the member water districts"
        else:
            l = P.landmark("Clarkwood", "community", exact=True)
            ref, basis, bbox, ext = ref_on_land(l["lat"], l["lon"], "PZ-3"), "real site: Clarkwood (USGS GNIS populated place)", P.nominal_box(l["lat"], l["lon"], 3.0), "nominal 6 km box around the reference point"
        add(f"AREA-PZ-{n}", pz_name[n], "pressure_zone", ref, basis, bbox, ext, within=[cc], water_districts=members,
            aliases=["Zone 4", "Zone 4 distribution system"] if n == "4" else None, regulatory_minimum_psi=20, normal_confirmation_psi=40)
    for a in areas:
        if a.get("aliases") is None:
            a.pop("aliases", None)
    T("AREA-WD-3-4", role="Boil-water notice D+12 17:30 local (English), Spanish reaches KNCB 06:03 D+13; lifted D+42 11:00. 94.3% of the 1,820 Cryptosporidium/Giardia cases. District 3 = ZIPs 78405, 78416 (+78417); District 4 = 78407, 78408 (+78401).",
      sources=["PUB-143", "PUB-204", "PUB-144", "EVT-1606", "PUB-163", "PUB-206"])
    T("_districts", note="PUB-203 says 'Districts 1 through 6' and NWS-P012-06 says the unaffected districts are 1, 2 and 5; five water districts are defined. Stories also say Districts 3 and 4 include 'portions of Calallen, Violet' although the notice's ZIP list does not; the ZIP list governs.")

    # ---------------- census tracts (the scenario's synthetic tract table)
    acs = {r["TRACT"]: r for r in csv.DictReader(open(os.path.join(ROOT, "05_other_sources", "census", "acs_nueces_tracts.csv"), encoding="utf-8"))}
    idx = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "05_other_sources", "census", "nueces_tract_index.csv"), encoding="utf-8")):
        idx.setdefault(r["TRACT"], r)
    incomes = sorted(float(r["B19013_001E"]) for r in acs.values())
    q1, q3 = incomes[len(incomes) // 4], incomes[(3 * len(incomes)) // 4]
    tract_zone, low_inc_surge, high_inc = {}, [], []
    for tract in sorted(idx):
        r, a = idx[tract], acs.get(tract, {})
        anchor = TRACT_ANCHOR.get(tract)
        ref = basis = bbox = None
        ext = "outside the reference window; no reference point or extent"
        if anchor:
            if anchor[0] == "lm":
                l = P.landmark(anchor[1], anchor[2], exact=True)
                ref, basis = (l["lat"], l["lon"]), f"real site: {l['name']}"
                if not G.is_land(*ref):
                    la, lo, b, _ = P.beside(None, ref, max_km=1.5)
                    ref, basis = (la, lo), b
            elif anchor[0] == "nas":
                p = _nas_site()
                ref, basis = (p["latitude"], p["longitude"]), p["position_basis"]
            else:
                la, lo, b, _ = P.beside(anchor[2] if len(anchor) > 2 else None, anchor[1], max_km=3.0)
                ref, basis = (la, lo), b
            bbox = P.nominal_box(ref[0], ref[1], 1.25)
            ext = "nominal 2.5 km box around the reference point; tract boundaries are not in the reference set (the tract table is synthetic)"
        zone = r["EVAC_ZONE"]
        tract_zone[tract] = zone
        inc = float(a["B19013_001E"]) if a else None
        rec = add(f"AREA-TRACT-{tract}", f"Census Tract {tract[:4]}.{tract[4:]} ({r['NEIGHBORHOOD_NAME']})", "census_tract",
                  ref_on_land(ref[0], ref[1], tract) if ref else None, basis or "outside the reference window", bbox, ext, within=["PLC-001", f"AREA-EVAC-{zone}"],
                  geoid=r["GEOID"], tract=tract, neighbourhood_name=r["NEIGHBORHOOD_NAME"], evacuation_zone=zone,
                  population=int(a["B01003_001E"]) if a else int(r["POP_EST"]), median_household_income=inc,
                  persons_below_poverty=int(a["B17001_002E"]) if a else None, hispanic_or_latino=int(a["B03003_003E"]) if a else None,
                  income_quartile=(1 if inc <= q1 else 4 if inc >= q3 else None) if inc is not None else None, attributes_source="05_other_sources/census/acs_nueces_tracts.csv")
        if inc is not None and inc <= q1 and zone in ("A", "B"):
            low_inc_surge.append(rec["area_id"])
        if inc is not None and inc >= q3:
            high_inc.append(rec["area_id"])
    T("PLC-010", name="Low-income surge-zone tracts", members=low_inc_surge, definition="bottom income quartile and evacuation zone A or B", role="61% of 911 calls at peak; aid dollars at about half their share; ER visits +40% at D+45.", sources=["PUB-026", "PUB-091", "PUB-069"])
    T("PLC-011", name="High-income tracts", members=high_inc, definition="top income quartile in the tract table")
    by_id = {a["area_id"]: a for a in areas}

    # ---------------- evacuation zones
    zone_desc = {"A": "Barrier islands, bayfront and all areas at highest surge risk", "B": "Low-lying coastal areas inland of Zone A", "C": "Areas below 10 feet of elevation and mobile or manufactured homes inland of Zone B",
                 "D": "Inland areas with minimal surge risk", "E": "Remaining inland and rural areas"}
    for z in "ABCDE":
        members = [f"AREA-TRACT-{t}" for t, zz in sorted(tract_zone.items()) if zz == z]
        boxes = [by_id[m]["bbox"] for m in members]
        refm = next((m for m in members if by_id[m]["reference_point"]), None)
        if refm:
            ref, basis, bbox, ext = by_id[refm]["reference_point"], f"reference point of {refm}", P.union_box(boxes), f"union of the nominal boxes of its {len(members)} member tracts"
        else:
            ref, basis, bbox, ext = None, "no tract in the scenario's tract table is assigned to this zone", None, "not defined"
        add(f"AREA-EVAC-{z}", f"Evacuation Zone {z}", "evacuation_zone", ref, basis, bbox, ext, within=["PLC-001"], description=zone_desc[z], member_tracts=members,
            population=sum(by_id[m]["population"] for m in members) if members else None, order_class="mandatory" if z in "ABC" else "shelter in place")
    T("AREA-EVAC-A", role="Mandatory evacuation: surge zones from D-2 (PUB-021); Zones A, B and C by county order at 07:00 local D-1 (PUB-201). Zones C to E told to shelter in place if still home at 13:00 local D-1 (EVT-1403).",
      sources=["PUB-021", "PUB-201", "EVT-1403"], open_item="PUB-140 still carries a D-3 order for Zones A and B (see canon_timeline open_items).")

    # ---------------- patrol beats
    for b in legacy_beats:
        bid = b["beat_id"]
        la, lo, basis, _ = P.beside(None, BEAT_ANCHOR[bid], max_km=2.0)
        add(f"AREA-BEAT-{bid}", f"Beat {bid[1:]} - {b['name']}", "patrol_beat", ref_on_land(la, lo, bid), basis, P.nominal_box(la, lo, BEAT_HALF_KM[bid]),
            f"nominal {2 * BEAT_HALF_KM[bid]:g} km box around the reference point; beat boundaries are not in the reference set", within=[cc], beat_id=bid,
            neighbourhoods=b.get("neighborhoods"), agency="CCPD")

    for old, new, note in [("PLC-010 / PLC-011 (00_scenario/places.json)", "members listed in _internal/areas_truth.json", "derived from the tract table: income quartile and evacuation zone"),
                           ("beat ids B01..B12 (911 stream)", "AREA-BEAT-B01..B12", "same ids"),
                           ("EVAC_ZONE / PREF_EVAC_ZONE A-D (census files)", "AREA-EVAC-A..D", "Zone E exists in canon (EVT-1403) but no tract is assigned to it"),
                           ("Water Zone 1/2/3 (old eas_broadcasts.csv)", None, "removed from canon; notices are citywide or Districts 3 and 4"),
                           ("District 3 / District 4 / Zone 4", ["AREA-WD-3", "AREA-WD-4", "AREA-PZ-4"], "")]:
        migrate("areas", old, new, "00_scenario, 05_other_sources/census, 911, public_health", note)
    return areas


# ======================================================================================
# write
# ======================================================================================
def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def main():
    fac, ooa = build_facilities()
    fac_by_id = {f["facility_id"]: f for f in fac}
    cad = build_cad()
    assets, remote = build_infra(fac_by_id)
    assets_by_id = {a["asset_id"]: a for a in assets}
    sensors = build_sensors(assets_by_id)
    legacy_beats = cad["agencies"]["CCPD"]["beats"]
    areas = build_areas(fac, legacy_beats)

    coord_note = ("Coordinates are real published points (99_reference/geo/landmarks.geojson) or points beside real roads; "
                  "see position_basis on each record and 99_reference/geo/SOURCES_*.md.")
    dump(os.path.join(OUT, "facility_registry.json"), {
        "metadata": {"catalog": "facility_registry", "version": "2.0", "generated": TODAY, "scenario": "Hurricane Rafael (fictional)",
                     "description": "Hospitals, clinics, shelters, distribution sites, relief hubs, recovery centres and emergency-management facilities. Operators are fictional; sites are real.",
                     "coordinates": coord_note, "id_scheme": "FAC-<ABBR>-<NNN>; military and Coast Guard facilities keep their scenario place ids (FAC-DOD-01, FAC-USCG-01).",
                     "figures_note": "Records marked figures = 'scenario value' carry ordinary reference figures chosen for the exercise; figures taken from public statements say so."},
        "facilities": fac, "out_of_area": ooa})
    dump(os.path.join(OUT, "cad_units.json"), cad)
    dump(os.path.join(OUT, "infrastructure_assets.json"), {
        "_catalog": "infrastructure_assets", "_version": "2.0", "_generated": TODAY,
        "_description": "Utility, transport and fuel assets with parent/child and 'serves' relations. One id per asset; SCADA tag prefixes and work-order asset numbers are attributes.",
        "_coordinates": coord_note, "_fema_disaster": "DR-4821-TX", "_fips": "48355",
        "assets": assets, "remote_assets": remote,
        "asset_type_guide": sorted({a["asset_type"] for a in assets} | {r["asset_type"] for r in remote})})
    dump(os.path.join(OUT, "sensor_registry.json"), dict(
        {"metadata": {"catalog": "sensor_registry", "version": "2.0", "generated": TODAY, "scenario": "Hurricane Rafael (fictional)",
                      "description": "Fixed environmental sensors: 6 water-quality sondes, 20 air monitors, tide gauges, 2 stream gauges, weather stations, buoys, bridge wind sensors, wastewater sampling sites.",
                      "coordinates": coord_note,
                      "note": "Outage and failure behaviour during the storm is not described here; it is in the data."}}, **sensors))
    dump(os.path.join(OUT, "areas.json"), {
        "metadata": {"catalog": "areas", "version": "1.0", "generated": TODAY, "scenario": "Hurricane Rafael (fictional)",
                     "description": "Named areas used across the corpus: counties, cities, neighbourhoods, ZIP codes, water districts and pressure zones, evacuation zones, census tracts, patrol beats.",
                     "extents": "Boxes are honest approximations: each says how it was derived in extent_basis. None is a legal or postal boundary. Use reference_point for placement and bbox only as a search window.",
                     "coordinates": coord_note},
        "areas": areas})

    stamp = {"generated": TODAY, "not_for_participants": True}
    for reg in TRUTH:
        doc = dict(stamp, registry=reg + ".json", truth=TRUTH[reg], id_migration=MIGRATION[reg])
        if reg == "facility_registry":
            doc["landmarks_used"] = LANDMARK_USED
        dump(os.path.join(INT, reg + "_truth.json"), doc)
    print(f"facilities {len(fac)} (+{len(ooa)} out of area) | stations {len(cad['stations'])} units {len(cad['units'])} | assets {len(assets)} (+{len(remote)} remote) | "
          f"sensors {sum(len(v) for v in sensors.values())} | areas {len(areas)}")


if __name__ == "__main__":
    main()
