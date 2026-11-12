"""Wider pass 2026-11-11: one name per organisation, no engineering terms in public text, one boil time,
plus leftovers in the MSEL, thread designs, canon timeline, characters and organisations."""
import json, os, re

HD = "Corpus Christi-Nueces County Public Health District"

STORIES = {
    # D51: the eligibility line (PUB-205 as amended)
    "NWS-P021-07": {
        "replace": [("los residentes de los Distritos 1 al 5 que tuvieron apagones prolongados podrían ser elegibles para ayuda adicional por desastre. Guarde cualquier comprobante",
                     "todavía no se ha decidido si los residentes que tuvieron apagones prolongados podrán recibir ayuda adicional por desastre. Por si acaso, guarde cualquier comprobante"),
                    ("Residents of Districts 1 through 5 with prolonged outages may qualify for more aid.", "No decision has been made on extra aid for residents who had prolonged outages; keep your receipts.")],
    },
    # no registration exists on D+5
    "NWS-P005-07": {
        "replace": [("nadie debe cobrarle por inscribirse para recibir ayuda federal. Si alguien", "nadie debe cobrarle por inscribirse para recibir ayuda federal, y todavía no hay ninguna inscripción abierta para ayuda a familias. Si alguien"),
                    ("No one should charge you to register for federal aid; report fraud", "No one should charge you to register for federal aid, and no registration for household aid is open yet; report fraud")],
    },
    # trim to the outlet's word range after the audit rewrite
    "NWS-P021-04": {"replace": [(" The announcement, issued jointly by the Cybersecurity and Infrastructure Security Agency and the Federal Bureau of Investigation, confirms what utility operators and federal partners have been quietly investigating since the storm's immediate aftermath.", " The announcement was issued jointly by the Cybersecurity and Infrastructure Security Agency and the Federal Bureau of Investigation."),
                                (" Federal officials at a Tuesday briefing declined to answer questions about whether the cyberattack was coordinated with the hurricane itself or whether it occurred opportunistically. No country or non-state actor has been publicly identified as responsible.", " No country or non-state actor has been publicly identified as responsible."),
                                (" Federal officials at a Tuesday morning briefing declined to answer questions about whether the cyberattack was coordinated with the hurricane itself or whether it occurred opportunistically. No country or non-state actor has been publicly identified as responsible.", " No country or non-state actor has been publicly identified as responsible."),
                                (" Texas Cyber Command confirmed its activation Tuesday morning. The state's Department of Homeland Security and Public Safety has assigned a dedicated team to coordinate with federal investigators, and both the Senate Homeland Security Committee and the House Energy and Commerce Committee indicated they intend to open oversight reviews.", " Texas Cyber Command confirmed its activation Tuesday morning.")]},
    # figures with no public fact behind them (wider pass)
    "NWS-P012-50": {"replace": [("posted $12 million in financial assurance", "posted financial assurance with the Coast Guard")]},
    "NWS-P090-05": {"replace": [("totaling $23.4 million in false demands", "totaling more than $23 million in false demands")]},
    "NWS-P090-06": {"replace": [("$23.4M in False Claims Filed", "More Than $23M in False Claims Filed"), ("generated nearly $23.4 million in false claims", "generated more than $23 million in false claims")]},
    "NWS-P090-07": {"replace": [("totaling $23.4 million, prosecutors say", "totaling more than $23 million, prosecutors say")]},
    "NWS-P010-06": {"replace": [("has learned from Nueces County 911 dispatch records", "has learned from Coastal Bend Emergency Communications Center dispatch records")]},
    "NWS-P032-04": {"replace": [("that amplified false shelter locations during the storm, later pivoted", "that amplified false shelter locations as the storm approached, later pivoted")]},
    # D+38 is a Friday (PUB-152: 'announced Friday')
    "NWS-P038-60": {"replace": [("anunciaron el jueves que eliminaron 847 cuentas", "anunciaron el viernes que eliminaron 847 cuentas"),
                                ("said Thursday they removed 847 accounts", "said Friday they removed 847 accounts")]},
    "NWS-P002-08": {"replace": [("The Nueces County Health District urged", "The " + HD + " urged")]},
    "NWS-P018-02": {"replace": [("Nueces County Public Health is tracking", "The " + HD + " is tracking")]},
    "NWS-P018-03": {"replace": [("Nueces County Public Health is investigating", "The " + HD + " is investigating"),
                                ("al menos un minuto completo", "durante dos minutos")]},
    "NWS-P013-04": {"replace": [("durante al menos un minuto completo", "durante dos minutos"),
                                ("Bring water to a rolling boil for at least one full minute.", "Bring water to a rolling boil for two minutes.")]},
    "NWS-P012-07": {"replace": [("to boil water for at least one minute before consumption", "to boil water for two minutes before consumption")]},
    "NWS-P023-04": {"replace": [("the onset of the Zone 4 pressure drop", "the onset of the pressure drop in the two districts")]},
    "NWS-P036-04": {"replace": [("sampling clearance across Zone 4", "sampling clearance across the two districts")]},
    "NWS-P042-04": {"replace": [("water pressure across all Zone 4 test points has been confirmed", "water pressure at all test points in the two districts has been confirmed")]},
    # D28: the outage windows are for the broadcast signal; web publishing continued
    "NWS-P000-01": {"replace": [("Harborline 6 is staying on the air and on this page through the night.", "Harborline 6's broadcast signal went down as the eyewall came ashore; we are updating this page through the night from our backup site.")]},
}

FACTS = {
    # figures the stories already report but no fact carried (wider pass)
    "PUB-131": {"replace": [("Over the first three days of the storm response, CBECC handled more than 7,300 calls,", "On landfall day, Tuesday, September 14, the center took about 1,840 calls, about 1,100 of them rescue-related. Over the first three days of the storm response, CBECC handled more than 7,300 calls,")]},
    "PUB-171": {"replace": [("Do not attempt to enter floodwater on foot.", "Do not attempt to enter floodwater on foot. Nueces County Emergency Management has confirmed 23 storm-related deaths as of this evening.")]},
    "PUB-174": {"replace": [("has learned from Nueces County 911 dispatch records", "has learned from Coastal Bend Emergency Communications Center dispatch records")]},
    "PUB-162": {"replace": [("call the Nueces County Public Health line", "call the Corpus Christi-Nueces County Public Health District line"),("Nueces County Public Health is investigating", "The " + HD + " is investigating"),
                            ("Boil water vigorously for at least one full minute before use.", "Boil water vigorously for two minutes before use.")]},
    "PUB-163": {"replace": [("and Nueces County Public Health on the ongoing", "and the " + HD + " on the ongoing")]},
    "PUB-191": {"replace": [("should contact Nueces County Public Health at", "should contact the " + HD + " at")]},
    "GW-PUB-006": {"source": "Coastal Bend Power and Water Authority", "replace": [("Coastal Bend Power & Water Authority", "Coastal Bend Power and Water Authority")]},
    # issuer names follow the same one-name rule
    "PUB-191": {"source": "Texas Commission on Environmental Quality / Corpus Christi-Nueces County Public Health District"},
    "PUB-143": {"source": "Corpus Christi Water Department / Coastal Bend Power and Water Authority"},
    "PUB-145": {"source": "Corpus Christi Water Department / Coastal Bend Power and Water Authority",
                "replace": [("The City of Corpus Christi Public Works Department announces", "The Corpus Christi Water Department announces")]},
    "GW-PUB-002": {"source": "Coastal Bend Power and Water Authority"},
    "PUB-210": {"source": "FBI Houston Division / Texas Department of Public Safety"},
}
FACTS["PUB-162"]["source"] = "Corpus Christi-Nueces County Public Health District"

EVENTS = {
    "EVT-1509": {"replace": [("Texas Attorney General's office issues a public advisory warning Texans", "Platforms remove the accounts on D+38 (PUB-152); two days later, on D+40, the Texas Attorney General's office issues a public advisory (PUB-153) warning Texans")]},
    "EVT-1907": {"replace": [("The report is releasable at FOUO level and shared with CISA, TSA, and the Port of Corpus Christi Authority.", "The report is releasable at FOUO level and shared with CISA, TSA, and the Port of Corpus Christi Authority on D+14; the public statement, which gives no number, place or timing, follows at 11:00 local on D+15 (PUB-181)."),
                             ("2027-09-28T18:00Z", "2027-09-29T18:00Z")]},
    "EVT-1608": {"replace": [("completes the preliminary outbreak analysis and issues findings to Nueces County Public Health and CBPWA.", "completes the preliminary outbreak analysis on D+22 and issues findings to the Corpus Christi-Nueces County Public Health District and CBPWA; the public release follows at 10:00 local on D+23 (PUB-163).")]},
    "EVT-2009": {"replace": [("(Day 60 average)", "(D+60 average)")]},
    "EVT-1906": {"replace": [("(front company: Nereid Maritime Holdings LLC)", "(front company: Nereid Maritime Holdings LLC, a shell in the Brannoch Maritime Holdings network; the yacht is the drone crew's support craft and is not the AIS-spoofing vessel of the channel thread)")]},
}

FILES = [
    ("_thread_designs/t22_fraud_design.json", "FBI SAC San Antonio", "FBI SAC Houston"),
    ("_thread_designs/t19_drone_design.json", "(front company: Nereid Maritime Holdings LLC)", "(front company: Nereid Maritime Holdings LLC, a shell in the Brannoch Maritime Holdings network; the yacht is the drone crew's support craft and is not the AIS-spoofing vessel of the channel thread)"),
    ("00_scenario/msel.json", "premature and panicked evacuation of Zones C–E before mandatory order", "premature and panicked evacuation of Zones B and C before their order (07:00 CDT D-1) and of Zones D and E, which are never ordered out"),
    ("_thread_designs/t15_social_design.json", "premature and panicked evacuation of Zones C–E before mandatory order", "premature and panicked evacuation of Zones B and C before their order (07:00 CDT D-1) and of Zones D and E, which are never ordered out"),
    ("_thread_designs/t14_bilingual_design.json", "shelter-in-place guidance for Zones C–E residents who have not evacuated", "shelter-in-place guidance for residents of Zones D and E and for anyone in Zones A to C who has not been able to leave"),
    ("_thread_designs/t14_bilingual_design.json", " and omits the curfew time of 22:00 CDT", ""),
    ("00_scenario/canon_timeline.json", "City shelter-in-place guidance for Zones C to E", "City shelter-in-place guidance for Zones D and E and for anyone still in Zones A to C"),
    ("_thread_designs/t16_hospital_design.json", "as the McKinley Substation (T8 target) fails", "as the McKinley Substation (GW-FAC-DSS-01, the distribution substation feeding the hospital; storm damage, not one of the five manipulated transmission substations) fails"),
    # T18 name
    ("00_scenario/threads.json", "Utility SOC / SIEM telemetry (GRIDWATER LAYER)", "Utility SOC / SIEM telemetry"),
    ("_thread_designs/t18_siem_design.json", "Utility SOC / SIEM telemetry (GRIDWATER LAYER)", "Utility SOC / SIEM telemetry"),
    ("06_answer_key/answer_key.json", "Utility SOC / SIEM telemetry (GRIDWATER LAYER)", "Utility SOC / SIEM telemetry"),
    # canon is Fort Hood
    ("01_characters/canon.json", "Fort Cavazos", "Fort Hood"),
]

# text that only the thread designs still carry (their copies of public facts)
DESIGN_PAIRS = [
    ("designs", "South Texas Blood and Tissue Center", "Nueces Bay Blood Services"),
    ("designs", "Nueces County Public Health Department", "Corpus Christi-Nueces County Public Health District"),
    ("designs", "Coastal Bend Power & Water Authority", "Coastal Bend Power and Water Authority"),
    ("designs", "at least eleven calls during the past week reported trapped residents at addresses in northwest Corpus Christi", "23 calls since September 21 from unregistered prepaid phones reported emergencies near two utility sites in northwest and central Corpus Christi, at least eleven of them trapped residents"),
    ("designs", "Coastline Public Radio has learned from Nueces County 911 dispatch records", "Coastline Public Radio has learned from Coastal Bend Emergency Communications Center dispatch records"),
    ("designs", "Water distribution sites are open at Cunningham Middle School, Brownie's Corner Community Center, and Calallen High School", "Water distribution sites are open at the Tuloso-Midway High School gym, the Woodlawn Community Center, and Cefe Valenzuela Park"),
    ("designs", "for at least one full minute", "for two minutes"),
    ("designs", "the full 180-day arc", "the full scenario arc"),
    ("designs", "City of Corpus Christi Public Works / Coastal Bend Power and Water Authority", "Corpus Christi Water Department / Coastal Bend Power and Water Authority"),
    ("designs", "City of Corpus Christi Public Works / Coastal Bend Power & Water Authority", "Corpus Christi Water Department / Coastal Bend Power and Water Authority"),
    ("designs", "Fictional Corpus Christi Fire Department Dispatch Chief and SAR coordinator", "Fictional Dispatch Chief of the Coastal Bend Emergency Communications Center and county SAR coordinator"),
    ("designs", "CCFD SAR Dispatch Chief", "CBECC Dispatch Chief"),
    ("designs", "Widespread structural damage is reported across Districts 1 through 6", "Widespread structural damage is reported across Districts 1 through 5"),
]

# scope, regex, replacement (each regex must not match its own output)
SWEEPS = [
    ("public", r"(?<!Corpus Christi-)(?<!Corpus Christi–)Nueces County Public Health District", HD),
    ("public", r"Coastal Bend Power & Water Authority", "Coastal Bend Power and Water Authority"),
    ("public", r"Corpus Christi[–-]Nueces County 911 center", "Coastal Bend Emergency Communications Center"),
    ("public", r"South Texas Blood (?:and Tissue Center|Bank)", "Nueces Bay Blood Services"),
    ("public", r"FBI(?:'s)? San Antonio (Division|division|Field Office|field office)", r"FBI Houston \1"),
    ("public", r"\bFort Cavazos\b", "Fort Hood"),
]


def apply(ROOT, check):
    """Structured edits to canon_timeline.json and organizations.json."""
    out = []
    fp = os.path.join(ROOT, "00_scenario", "canon_timeline.json")
    t = json.load(open(fp, encoding="utf-8")); before = json.dumps(t, sort_keys=True)
    n = t["names"]
    n["hospital_ids"] = {"value": {"Shoreline Regional Medical Center": "FAC-SRMC-001", "Bay City Medical Center": "FAC-BCMC-002"},
                         "note": "Set in 06_data_streams/facility_registry.json; streams use these ids."}
    if "substation_alias_to_resolve" in n:
        n.pop("substation_alias_to_resolve")
    n["hospital_feeder_substation"] = {"name": "McKinley Substation", "id": "GW-FAC-DSS-01", "used_in": ["EVT-1602", "EVT-1605"],
                                       "note": "Distribution substation feeding Shoreline Regional; storm damage only, restored D+8 09:14 local. Not one of the five manipulated transmission substations."}
    n["utility"]["note"] = ("Water notices are issued jointly by the Coastal Bend Power and Water Authority and the Corpus Christi Water Department; "
                            "both names are public. 'Zone 4' (pressure zone 4, the area of Water Districts 3 and 4) is an engineering term used only in internal events and utility data, never in public text.")
    n["one_name_per_organisation"] = {
        "911 centre": "Coastal Bend Emergency Communications Center (CBECC)",
        "health district": "Corpus Christi-Nueces County Public Health District",
        "water office": "Corpus Christi Water Department",
        "utility (Spanish)": "Autoridad de Energía y Agua del Coastal Bend",
        "blood centre": "Nueces Bay Blood Services",
        "FBI office": "FBI Houston Division; Corpus Christi Resident Agency",
        "Army post": "Fort Hood",
    }
    d = t.get("drones", {})
    if "geometry_note" in d:
        d["geometry_note"] = "Sortie, buoy and marina positions are the registry positions (06_data_streams) placed on the real map by the geography pass."
    d["support_vessel_note"] = ("'Narwhal Dream' (Nereid Maritime Holdings LLC, a shell in the Brannoch Maritime Holdings network) is the drone crew's support craft at Ingleside Marina. "
                                "It is never public and it is not the 'one dark vessel' of decision 2, which is the AIS-spoofing vessel in the channel thread.")
    b = t.get("broadcast", {})
    b["note"] = ("Off-air windows are for the broadcast signal only. Each outlet kept publishing to the web from a backup site, so stories carry times inside those windows; "
                 "no story says a station stayed on the air during its off-air window.")
    t["open_items"] = []
    da = t.setdefault("decisions_applied", [])
    for line in ("2026-11-11: false 911 calls are 23 (D+7 to D+10), 11 of them trapped-resident reports; SAR hoists 180 at D+1 15:00 and 341 by air in total; "
                 "Individual Assistance approved D+57, registration D+60; boil time two minutes; one name per organisation (names.one_name_per_organisation); "
                 "Districts 3 and 4 serve about 48,000 residents. See canon_decisions.md, Decisions 2026-11-11.",):
        if line not in da:
            da.append(line)
    t["_about"]["version"] = "2026-11-11"
    if json.dumps(t, sort_keys=True) != before and not check:
        with open(fp, "w", encoding="utf-8") as fh:
            json.dump(t, fh, ensure_ascii=False, indent=1); fh.write("\n")
    fp = os.path.join(ROOT, "06_data_streams", "organizations.json")
    o = json.load(open(fp, encoding="utf-8")); before = json.dumps(o, sort_keys=True)
    for x in o["organizations"]:
        if x["org_id"] == "ORG-1100":
            x["aliases"] = [a for a in x.get("aliases", []) if "Public Works Authority" not in a]
        if x["org_id"] == "ORG-1142":
            x["public_role"] = "Threat research firm; published an analysis of storm rumour posts"
        if x["org_id"] == "ORG-1192":
            x["public_role"] = "Registered owner of a motor yacht in vessels.json"
    if json.dumps(o, sort_keys=True) != before and not check:
        with open(fp, "w", encoding="utf-8") as fh:
            json.dump(o, fh, ensure_ascii=False, indent=1); fh.write("\n")
    # quantity rules used by scripts/check_facts.py follow the same decisions
    fp = os.path.join(ROOT, "02_public_record", "quantity_rules.json")
    q = json.load(open(fp, encoding="utf-8")); before = json.dumps(q, sort_keys=True)
    def setv(name, add=(), drop=(), move=()):
        for r in q["rules"]:
            if r["name"] == name:
                r["allowed"] = [a for a in r["allowed"] if a["value"] not in drop]
                for v, d in move:
                    for a in r["allowed"]:
                        if a["value"] == v:
                            a["from_day"] = d
                have = {a["value"] for a in r["allowed"]}
                for v, d in add:
                    if v not in have:
                        r["allowed"].append({"value": v, "from_day": d})
    setv("911 calls", add=[(7300, 3), (1000, 3), (380, 29), (44200, 29), (56000, 45)], move=[(1840, 3)])
    setv("storm category", add=[(2, -3)])
    setv("dollars (millions)", drop=(12, 23.4))
    if json.dumps(q, sort_keys=True) != before and not check:
        with open(fp, "w", encoding="utf-8") as fh:
            json.dump(q, fh, ensure_ascii=False, indent=2); fh.write("\n")
    # character notes quote story headlines: carry changed headlines across
    import glob
    bdir = os.path.join(ROOT, "_versions", "pre_narrative_fix_20261111", "stories")
    if os.path.isdir(bdir):
        oldh = {}
        for fp in glob.glob(os.path.join(bdir, "batch-*.json")):
            for s in json.load(open(fp, encoding="utf-8"))["stories"]:
                oldh[s["story_id"]] = s["headline"]
        pairs = []
        for fp in glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json")):
            for s in json.load(open(fp, encoding="utf-8"))["stories"]:
                o = oldh.get(s["story_id"])
                if o and o != s["headline"]:
                    pairs.append((json.dumps(o, ensure_ascii=False)[1:-1], json.dumps(s["headline"], ensure_ascii=False)[1:-1]))
                    pairs.append((json.dumps(json.dumps(o, ensure_ascii=False)[1:-1], ensure_ascii=False)[1:-1], json.dumps(json.dumps(s["headline"], ensure_ascii=False)[1:-1], ensure_ascii=False)[1:-1]))
        for fp in glob.glob(os.path.join(ROOT, "03_news", "character_updates", "*.json")) + [os.path.join(ROOT, "01_characters", "characters.json")]:
            txt = open(fp, encoding="utf-8").read(); new = txt
            for o, n in pairs:
                if o in new and n not in new:
                    new = new.replace(o, n)
                elif o in new and o not in n:
                    new = new.replace(o, n)
            if new != txt and not check:
                json.loads(new)
                open(fp, "w", encoding="utf-8").write(new)
    return out
