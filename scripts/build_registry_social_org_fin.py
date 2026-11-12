"""Build the social-account, organisation and financial-entity registries.

Writes (participant-safe reference data, no truth notes):
  06_data_streams/personas.json
  06_data_streams/organizations.json
  06_data_streams/entity_registry.json
and (internal, never delivered) under 06_data_streams/_internal/:
  personas_truth.json, organizations_truth.json, entity_registry_truth.json, people_to_add.json

Deterministic. Canon names come from the MSEL, public record, characters.json and
00_scenario/canon_timeline.json. Usage: python scripts/build_registry_social_org_fin.py
"""
import datetime as dt
import glob
import json
import os
import random
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "06_data_streams")
INT = os.path.join(OUT, "_internal")
os.makedirs(INT, exist_ok=True)
R = random.Random(20270914 + 7)
D0 = dt.date(2027, 9, 14)


def day(n):
    return (D0 + dt.timedelta(days=n)).isoformat()


def dump(obj, *path):
    with open(os.path.join(*path), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)


FIRST_EN = ("James Karen Michael Angela Darnell Keisha Marcus Tanya Andre Brenda Travis Shelby Cody Amber Wade Kayla Trent Becky "
            "Kevin Stacy Brian Tina Greg Monica Paul Diane Ray Lori Scott Heather Dustin Jenna Kyle Megan Curtis Dawn Earl Wanda "
            "Tyrone Latoya Jerome Denise Clay Brooke Dale Peggy Hank Trudy").split()
FIRST_ES = ("Maria Jose Luis Ana Carlos Rosa Miguel Elena Jorge Patricia Daniel Sandra Raul Veronica Hector Yolanda Oscar Gloria "
            "Ruben Alma Eddie Norma Noemi Felix Irma Tomas Lidia Ernesto Delia Arturo Sonia Victor Carmen Hugo Leticia Dolores "
            "Chuy Lupe Nacho Beto Paco Concha Memo Tere Javi Güero").split()
FIRST_VI = "Thanh Linh Huy Minh Kim Lan Tuan Mai Duc Hoa".split()
LAST_EN = ("Smith Johnson Williams Brown Jones Miller Davis Wilson Anderson Taylor Thomas Moore Jackson Martin Thompson White "
           "Harris Clark Lewis Walker Hall Allen Young King Wright Scott Green Baker Adams Nelson Carter Mitchell Roberts "
           "Turner Phillips Campbell Parker Evans Edwards Collins Stewart Morris Cook Rogers Kowalski Schroeder Dvorak").split()
LAST_ES = ("Garcia Martinez Rodriguez Hernandez Lopez Gonzalez Perez Sanchez Ramirez Torres Flores Rivera Gomez Diaz Reyes "
           "Morales Cruz Ortiz Gutierrez Chavez Ramos Mendoza Ruiz Alvarez Castillo Jimenez Vasquez Moreno Salinas Cantu "
           "Trevino Guerra Garza Villarreal Pena Longoria Saenz Zamora Tijerina Barrera Medina Cavazos Hinojosa Olivarez").split()
LAST_VI = "Nguyen Tran Le Pham Vo Dang Bui".split()

AREAS = [  # neighbourhood / community names used across canon
    ("North Beach", 3), ("Downtown", 3), ("Hillcrest", 4), ("Washington-Coles", 2), ("Oak Park", 4), ("Molina", 5), ("South Bluff", 3),
    ("Loma Alta", 4), ("Six Points", 3), ("Del Mar", 3), ("Central City", 5), ("Westside", 5), ("Southside", 9), ("Bay Area", 4),
    ("Flour Bluff", 6), ("Padre Island", 4), ("Calallen", 5), ("Annaville", 3), ("Tuloso-Midway", 2), ("Clarkwood", 1),
    ("Portland", 4), ("Gregory", 1), ("Ingleside", 3), ("Aransas Pass", 3), ("Port Aransas", 4), ("Rockport", 3), ("Fulton", 1),
    ("Robstown", 2), ("Kingsville", 1),
]
AREA_NAMES = [a for a, _ in AREAS]
AREA_W = [w for _, w in AREAS]
ES_HEAVY = {"Molina", "Oak Park", "South Bluff", "Loma Alta", "Westside", "Hillcrest", "Washington-Coles", "Robstown", "Central City"}


def bucket(n):
    for lim, lab in ((100, "<100"), (500, "100-499"), (2000, "500-1,999"), (10000, "2,000-9,999"), (50000, "10,000-49,999")):
        if n < lim:
            return lab
    return "50,000+"


def rdate(a, b):
    a, b = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return (a + dt.timedelta(days=R.randrange((b - a).days + 1))).isoformat()


# ======================================================================================
# PERSONAS
# ======================================================================================
personas, ptruth, handles = [], {}, set()


def persona(handle, name, atype, bio, location, area, followers, created, lang="en", verified=False, style="", per_day=1.0, hours="07:00-22:00",
            storm="", topics=None, pid=None, truth=None, following=None):
    assert handle.lower() not in handles, handle
    handles.add(handle.lower())
    pid = pid or f"SOC-{len(personas) + 1:03d}"
    p = {"persona_id": pid, "handle": "@" + handle, "display_name": name, "platform": "X", "account_type": atype, "bio": bio, "location": location,
         "home_area": area, "followers": followers, "follower_range": bucket(followers), "following": following if following is not None else int(R.uniform(0.2, 1.6) * min(followers, 1800) + R.randint(20, 300)),
         "account_created": created, "verified": verified, "language": lang, "posting_style": style,
         "cadence": {"typical_posts_per_day": per_day, "active_hours_local": hours, "during_storm": storm or "posts more often while power and signal last"},
         "topics": topics or []}
    personas.append(p)
    t = {"authentic": True}
    t.update(truth or {})
    ptruth[pid] = t
    return p


CC = "Corpus Christi, TX"
# ---- 1-32: the original catalogue ids are kept
persona("PortCorpusChristi", "Port of Corpus Christi", "official", "Official account of the Port of Corpus Christi. Port conditions, closures and reopening notices.", CC, "Downtown", 18400, "2011-06-02", verified=True, style="measured, institutional; defers to the Coast Guard on the spill", per_day=2, hours="07:00-19:00", storm="quiet for about 36 hours around landfall", topics=["port conditions", "ship channel", "exports"])
persona("CCEmergencyMgmt", "City of Corpus Christi Emergency Management", "official", "Official emergency information for Corpus Christi. Alerts, shelters, road closures. Not monitored 24/7. Emergencies: 911.", CC, "Downtown", 31200, "2012-03-14", verified=True, style="short, directive, service information first", per_day=6, hours="00:00-24:00", storm="posts around the clock", topics=["alerts", "shelters", "boil-water notices", "closures"])
persona("CCFDCCPD", "Corpus Christi Fire and Police", "official", "Joint public information account of the Corpus Christi Fire Department and Police Department.", CC, "Downtown", 22700, "2013-08-20", verified=True, style="incident updates, safety reminders", per_day=2, hours="06:00-23:00", topics=["rescues", "road closures", "curfew"])
persona("NuecesOEM", "Nueces County Office of Emergency Management", "official", "Nueces County emergency management. Evacuation zones, shelters, recovery information.", CC, "Downtown", 8900, "2014-05-01", verified=True, style="plain, bilingual when staff allow", per_day=3, hours="06:00-22:00", topics=["evacuation", "shelters", "recovery centres"], lang="en/es")
persona("USCGSectorCC", "USCG Sector Corpus Christi", "official", "Official account of U.S. Coast Guard Sector Corpus Christi. Port conditions, search and rescue, pollution response.", CC, "Flour Bluff", 14300, "2012-10-09", verified=True, style="formal releases, port condition changes", per_day=1.5, hours="06:00-21:00", topics=["port conditions", "search and rescue", "spill response"])
persona("BaysideLedger", "The Bayside Ledger", "media", "Local news for the Coastal Bend. Print and web.", CC, "Downtown", 27800, "2009-04-22", verified=True, style="headline plus link; AP style", per_day=8, hours="05:30-23:00", topics=["local news"], truth={"outlet_id": "OUT-01"})
persona("Harborline6News", "Harborline 6 News", "media", "Harborline 6: breaking news, weather and traffic for Corpus Christi and the Coastal Bend.", CC, "Downtown", 44200, "2009-09-30", verified=True, style="urgent, present tense, service details", per_day=12, hours="04:30-23:30", storm="off the air around landfall; web and social continue on backup power", topics=["breaking news", "weather", "traffic"], truth={"outlet_id": "OUT-02"})
persona("CoastlinePublicRadio", "Coastline Public Radio", "media", "Public radio newsroom for the Coastal Bend. Environment, equity, health, military and community.", CC, "Six Points", 9600, "2010-02-11", verified=True, style="explanatory, people first", per_day=4, hours="06:00-21:00", storm="on the air on generator power", topics=["environment", "equity", "health"], truth={"outlet_id": "OUT-03"})
persona("GulfwaterMaritime", "Gulfwater Maritime Report", "media", "Ports, tankers, security and regulation on the Gulf Coast. Trade publication.", "Houston, TX", None, 6100, "2013-01-17", verified=False, style="terse, technical, no speculation", per_day=2, hours="06:00-19:00", topics=["ports", "tankers", "maritime security"], truth={"outlet_id": "OUT-04"})
persona("KNCB1480", "KNCB Coastal Bend Radio 1480 AM", "media", "KNCB 1480 AM. Noticias y servicio a la comunidad del Coastal Bend. News and community service in Spanish.", CC, "Westside", 7400, "2011-11-03", verified=False, lang="es/en", style="Spanish first, practical emergency information", per_day=6, hours="05:00-23:00", storm="24-hour emergency format; silent while the transmitter is down", topics=["emergencias", "comunidad", "salud"], truth={"outlet_id": "OUT-08"})
persona("MargaritaLozano_CC", "Margarita Lozano", "individual", "Abuela, costurera, vecina de Bayside de toda la vida.", CC, "Bay Area", 310, "2016-07-19", lang="es/en", style="family updates, church, neighbours", per_day=1.2, topics=["family", "neighbourhood"])
persona("FishingWithFelipeCC", "Felipe Garza", "individual", "Bay fishing, redfish and trout. Weekend guide.", CC, "Flour Bluff", 2300, "2015-03-08", style="photos, tide talk", per_day=1.5, topics=["fishing", "bay conditions"])
persona("RosendoCastilloTX", "Rosendo Castillo", "individual", "Calallen. Retired refinery operator. Wildcats football.", CC, "Calallen", 180, "2018-09-02", style="plain spoken, local grievances", per_day=0.8, topics=["calallen", "water", "football"])
persona("SandraBeachCC", "Sandra Vela", "individual", "North Beach resident. Coffee, pelicans, the Lex out my window.", CC, "North Beach", 540, "2014-12-27", style="photos from the beach, neighbourhood watch", per_day=1.4, topics=["north beach", "bridge"])
persona("OldCCPete", "Pete Morales", "individual", "Born at Spohn before it was fancy. Opinions are mine.", CC, "Central City", 760, "2012-06-15", style="wry, long memory for past storms", per_day=2, topics=["local history", "city hall"])
ptruth["SOC-015"]["note"] = "Original bio mentioned a real hospital system; bio rewritten below."
personas[-1]["bio"] = "Born and raised here. Seen Celia, Allen, Bret and Harvey. Opinions are mine."
persona("IslandMomCC", "Daniela Reyes", "individual", "Padre Island mom of three. PTA. Beach cleanups.", CC, "Padre Island", 420, "2017-04-04", style="school and island updates", per_day=1.3, topics=["schools", "island"])
persona("CCVetCenter_Vol", "Arturo Hinojosa", "individual", "Army veteran. Volunteer driver for vets on the Southside.", CC, "Southside", 610, "2016-11-11", style="ride offers, veteran resources", per_day=1, topics=["veterans", "volunteering"])
persona("ElGolfoTaqueriaCC", "El Golfo Taqueria", "business", "Tacos, barbacoa los domingos. Family owned.", CC, "Westside", 1900, "2015-08-30", lang="es/en", style="specials, hours, community meals after the storm", per_day=1, hours="06:00-21:00", topics=["food", "hours"])
persona("CCBeachPhotog", "Yesenia Ruiz", "individual", "Photographer. Sunrises on the bayfront.", CC, "Downtown", 3800, "2013-05-21", style="photos, short captions", per_day=1.5, topics=["photos", "bayfront"])
persona("CoastTruthTX", "Coast Truth TX", "individual", "Local mom. Asking the questions they won't. Corpus Christi and the Coastal Bend.", "Corpus Christi area", "Southside", 12000, "2021-02-17", style="indignant, question framing, screenshots", per_day=9, hours="06:00-01:00", storm="posts constantly", topics=["aid", "military", "city hall"],
        truth={"authentic": False, "network": ["base_40", "t15_47"], "soc_acc": "SOC-ACC-5001", "character_id": "CHR-080", "public_from_day": 2, "kind": "aged account", "removed_d38": True})
persona("GulfWatchPatriot", "Gulf Watch Patriot", "individual", "Veteran. South Texas born. Watching the Gulf so you don't have to.", "South Texas", "Flour Bluff", 8700, "2020-07-04", style="patriotic, suspicious of officials", per_day=7, hours="05:00-23:00", topics=["military", "refineries", "spill"],
        truth={"authentic": False, "network": ["base_40", "t15_47"], "soc_acc": "SOC-ACC-5002", "character_id": "CHR-081", "public_from_day": 3, "kind": "aged account", "removed_d38": True})
persona("TruthAboutRafael", "Truth About Rafael", "individual", "What they are not telling you about Hurricane Rafael. Corpus Christi, Nueces County.", "Texas", "Central City", 3400, "2027-09-08", style="threads, capital letters", per_day=6, hours="07:00-02:00", topics=["rafael", "aid"],
        truth={"authentic": False, "network": ["base_40", "t15_47"], "soc_acc": "SOC-ACC-5005", "kind": "created in the pre-positioning window", "removed_d38": True})
persona("TexasCoastAlert", "Texas Coast Alert", "individual", "Unofficial alerts for the Texas Gulf Coast. Coastal Bend, South Texas.", "Texas Gulf Coast", "Portland", 5200, "2022-05-30", style="looks like an alert service; mixes real alerts with rumours", per_day=8, hours="00:00-24:00", topics=["alerts", "shelters", "roads"],
        truth={"authentic": False, "network": ["base_40", "t15_47"], "soc_acc": "SOC-ACC-5006", "kind": "aged account", "removed_d38": True})
persona("EnergyMktWatcher", "Marcus Dupree", "individual", "Crude and products. Ex-trader. Views my own.", "Houston, TX", None, 15400, "2012-09-12", style="market shorthand", per_day=5, hours="05:00-20:00", topics=["crude exports", "freight"])
persona("PortWatcherAIS", "Gulf AIS Watch", "individual", "Hobbyist ship spotter. Public AIS screenshots from Corpus Christi and Port Aransas.", CC, "Port Aransas", 2900, "2018-02-03", style="screenshots of vessel positions, careful wording", per_day=2, topics=["ais", "anchorage", "ship channel"])
persona("ShrimpBoatRuiz", "Carlos Ruiz, F/V El Pescador", "individual", "Camaronero. Tercera generación. La bahía es mi oficina.", CC, "Aransas Pass", 480, "2016-01-09", lang="es/en", style="short, practical, photos from the boat", per_day=1, topics=["shrimping", "closures", "claims"])
persona("MarSecResearcher", "Dr. Nadia Okonkwo", "individual", "Maritime security researcher. AIS, GNSS interference, port resilience.", "Galveston, TX", None, 6800, "2014-10-28", style="threads with caveats", per_day=1.5, topics=["ais spoofing", "gnss", "ports"])
persona("JourdanWattsNRG", "Jourdan Watts", "individual", "Energy policy. Exports, infrastructure, security.", "Washington, DC", None, 11200, "2013-03-19", style="policy commentary", per_day=3, topics=["energy policy", "exports"])
persona("CoastalDefendersOrg", "Coastal Defenders Alliance", "organization", "Protecting Texas bays and estuaries.", "Austin, TX", None, 5300, "2012-04-22", style="advocacy, calls to action", per_day=1.5, topics=["spill", "wildlife", "fishing closures"])
persona("DisasterRespProf", "Dr. Amara Singh", "individual", "Disaster response and recovery researcher.", "Austin, TX", None, 4100, "2015-06-06", style="explains process; equity focus", per_day=1.2, topics=["recovery", "equity", "aid"])
persona("MaraEstormesMX", "Mara Estormes", "individual", "Meteoróloga. Huracanes del Golfo y el Caribe.", "Monterrey, Mexico", None, 9300, "2014-08-15", lang="es", style="forecast graphics in Spanish", per_day=3, topics=["huracanes", "pronóstico"])
persona("CCHopeVolunteers", "CC Hope Volunteer Coalition", "organization", "Neighbours helping neighbours. Supply drives, muck-outs, rides.", CC, "Central City", 2600, "2017-09-05", style="needs lists, volunteer calls", per_day=3, topics=["volunteering", "supplies"])
assert len(personas) == 32

# ---- agencies and institutions
OFFICIAL = [
    ("CBPWA_Alerts", "Coastal Bend Power and Water Authority", "Outage, restoration and water service updates from CBPWA. Report outages by phone, not here.", "Downtown", 6700, "2013-02-05", 4, ["outages", "restoration", "water pressure"]),
    ("CityofCCWater", "City of Corpus Christi Water", "City water utility notices: boil-water advisories, distribution sites, conservation.", "Downtown", 5100, "2014-06-18", 2, ["water", "boil-water notices"]),
    ("FEMARegion6", "FEMA Region 6", "Serving Arkansas, Louisiana, New Mexico, Oklahoma and Texas.", None, 22000, "2010-05-12", 3, ["federal aid", "registration"]),
    ("NationalHurricaneCenter", "National Hurricane Center", "Official forecasts, watches and warnings for the Atlantic basin.", None, 1200000, "2009-06-01", 6, ["advisories", "forecast cone"]),
    ("NWSCorpusChristi", "NWS Corpus Christi", "Official National Weather Service forecasts and warnings for South Texas.", "Southside", 61000, "2010-07-27", 8, ["forecasts", "warnings", "surge"]),
    ("txdot_coastal", "TxDOT Coastal District", "Road and bridge conditions for the Coastal Bend.", "Southside", 5400, "2012-08-08", 2, ["bridges", "closures", "ferry"]),
    ("NuecesCoHealth", "Corpus Christi-Nueces County Public Health", "Public health district updates.", "Central City", 4300, "2013-10-10", 1.5, ["health advisories", "illness"]),
    ("TexasDSHS_Coastal", "Texas DSHS Public Health Region 11", "State health services for South Texas.", None, 3900, "2014-02-02", 1, ["shellfish closures", "outbreak"]),
    ("TDEM_Region", "Texas Division of Emergency Management, Coastal Bend", "State emergency management field office.", None, 12800, "2012-12-01", 2, ["state response"]),
    ("TexasGLO_Spill", "Texas General Land Office Oil Spill Program", "Oil spill prevention and response on the Texas coast.", None, 4700, "2013-04-09", 1, ["spill response", "claims"]),
    ("NASCorpusChristi", "Naval Air Station Corpus Christi", "Official account of NAS Corpus Christi.", "Flour Bluff", 9800, "2011-03-03", 1, ["base status", "families"]),
    ("CCArmyDepot", "Corpus Christi Army Depot", "Official account of the Corpus Christi Army Depot.", "Flour Bluff", 6200, "2012-01-20", 0.6, ["depot status", "workforce"]),
    ("CBECC_911", "Coastal Bend Emergency Communications Center", "Corpus Christi-Nueces County 911. This account is not monitored for emergencies.", "Central City", 2100, "2016-03-22", 0.5, ["911", "call volume"]),
    ("CityofPortAransas", "City of Port Aransas", "Official city information.", "Port Aransas", 7300, "2012-05-05", 1.5, ["island access", "ferry", "recovery"]),
    ("SanPatCountyOEM", "San Patricio County Emergency Management", "Emergency information for San Patricio County.", "Portland", 3600, "2014-09-09", 1.5, ["evacuation", "shelters"]),
    ("AransasCountyOEM", "Aransas County Emergency Management", "Emergency information for Rockport, Fulton and Aransas County.", "Rockport", 4400, "2013-07-07", 1.5, ["evacuation", "shelters"]),
    ("NuecesSheriff", "Nueces County Sheriff's Office", "Official account.", "Downtown", 8100, "2013-11-19", 1, ["curfew", "scams"]),
    ("CCISD_News", "Corpus Christi ISD", "District news, closures and shelter sites.", "Central City", 15600, "2011-08-15", 1.5, ["school closures", "shelters"]),
    ("TAMUCC_Island", "Texas A&M University-Corpus Christi", "The Island University.", "Bay Area", 28900, "2009-10-01", 2, ["campus status", "research"]),
    ("ShorelineRegionalMC", "Shoreline Regional Medical Center", "Level II trauma centre serving the Coastal Bend.", "Central City", 8900, "2012-02-14", 1, ["hospital status", "visitor rules"]),
    ("BayCityMedCtr", "Bay City Medical Center", "Community hospital. Emergency care 24/7.", "Southside", 4200, "2013-06-11", 0.8, ["hospital status"]),
    ("CCBarPilots", "Coastal Bend Bar Pilots Association", "Pilotage for the Corpus Christi Ship Channel.", "Port Aransas", 890, "2015-02-27", 0.5, ["pilot boardings", "channel"]),
    ("FBIHoustonDiv", "FBI Houston", "Official account of the FBI Houston Field Office.", None, 86000, "2010-11-30", 1, ["investigations", "fraud warnings"]),
    ("CISA_Region6", "CISA Region 6", "Cybersecurity and infrastructure security for the south-central United States.", None, 14500, "2019-04-16", 0.8, ["advisories"]),
    ("USACE_Galveston", "USACE Galveston District", "U.S. Army Corps of Engineers, Texas coast.", None, 19700, "2011-01-11", 1, ["channel surveys", "debris"]),
    ("TexasAG_Consumer", "Texas Attorney General Consumer Protection", "Report scams and price gouging.", None, 73000, "2012-07-01", 1, ["scams", "price gouging"]),
    ("TexasDeptInsurance", "Texas Department of Insurance", "Help with insurance claims and complaints.", None, 21000, "2011-09-21", 1, ["claims", "fraud"]),
    ("NuecesInfoLine", "NuecesInfoLine", "Non-emergency information line for Nueces County storm recovery.", "Downtown", 900, "2027-09-26", 2, ["information line", "water safety"]),
    ("TxTaskForce1", "Texas A&M Task Force 1", "Urban search and rescue.", None, 54000, "2010-04-04", 1, ["search and rescue"]),
    ("CCRTA_Rides", "Coastal Bend Regional Transit", "Bus service and evacuation pickups.", "Downtown", 3100, "2013-09-13", 2, ["bus service", "evacuation pickups"]),
    ("CCIntlAirport", "Corpus Christi International Airport", "Flight status and airport notices.", "Westside", 6600, "2012-06-06", 1, ["flights", "airspace"]),
    ("GulfCoastReliefNet", "Gulf Coast Relief Network", "Regional disaster relief nonprofit.", None, 17300, "2012-08-29", 2, ["shelters", "donations"]),
]
for h, n, bio, area, fol, cr, pd_, topics in OFFICIAL:
    persona(h, n, "official" if h not in ("GulfCoastReliefNet", "CCBarPilots", "ShorelineRegionalMC", "BayCityMedCtr", "TAMUCC_Island") else "organization",
            bio, CC if area else "Texas", area, fol, cr, verified=fol > 2500 and h != "NuecesInfoLine", style="official notices", per_day=pd_, hours="06:00-21:00", topics=topics,
            lang="en/es" if h in ("CityofCCWater", "NuecesInfoLine", "NuecesCoHealth") else "en")

# ---- remaining outlets and reporters
persona("SabalEnergyWire", "Sabal Energy Wire", "media", "Energy and markets wire. Crude, refining, power.", "Houston, TX", None, 13200, "2012-11-12", verified=True, style="market wire", per_day=6, hours="05:00-20:00", topics=["crude", "refining", "markets"], truth={"outlet_id": "OUT-05"})
persona("ContinentalWire", "Continental Wire Service", "media", "National and world news.", "Washington, DC", None, 412000, "2009-03-10", verified=True, style="wire headlines", per_day=40, hours="00:00-24:00", topics=["national news"], truth={"outlet_id": "OUT-06"})
persona("AnchorRotorWeekly", "Anchor & Rotor Weekly", "media", "Community news for NAS Corpus Christi, the Army depot and NAS Kingsville.", CC, "Flour Bluff", 3300, "2014-04-25", style="community, base services", per_day=1, hours="07:00-18:00", topics=["base news", "families"], truth={"outlet_id": "OUT-07"})
chars = json.load(open(os.path.join(ROOT, "01_characters", "characters.json"), encoding="utf-8"))
chars = chars.get("characters", chars) if isinstance(chars, dict) else chars
JHANDLE = {"CHR-001": "MarisolTrevino", "CHR-002": "GrantOkaforCC", "CHR-003": "DanaWhitlock", "CHR-004": "RubenCastaneda_", "CHR-005": "EllieNavarroWX", "CHR-006": "TylerBrandtH6",
           "CHR-007": "KeishaMonroeH6", "CHR-008": "PriyaRamanCPR", "CHR-009": "SamDelacroix", "CHR-010": "HenrikAalto", "CHR-011": "LuciaFerraro_", "CHR-012": "NoahPemberton", "CHR-013": "CarlaBenavides_"}
for c in chars:
    if c["kind"] == "journalist":
        persona(JHANDLE[c["id"]], c["name"], "journalist", f"{c['role']}, {c['affiliation'].get('org')}. Tips welcome.", CC if c["id"] not in ("CHR-010", "CHR-011", "CHR-012") else "Texas",
                "Downtown" if c["id"] not in ("CHR-010", "CHR-011", "CHR-012") else None, R.randint(900, 9000), rdate("2010-01-01", "2021-12-31"), style="reporting notes, links to stories",
                per_day=round(R.uniform(2, 6), 1), topics=[c["role"].lower()], truth={"character_id": c["id"]}, lang="en/es" if c["id"] in ("CHR-001", "CHR-013") else "en")
persona("Reporter_EvanK", "Evan Kowalski", "journalist", "Freelance photojournalist. Storms, coast, people.", CC, "Downtown", 3100, "2015-05-19", style="photos from the field", per_day=3, topics=["photos", "damage"])
persona("WXwatcherSA", "Weather Watcher San Antonio", "individual", "Weather hobbyist. Radar loops and model runs.", "San Antonio, TX", None, 4800, "2013-04-01", style="model graphics, excitable", per_day=6, topics=["forecast", "radar"])
# ---- experts and canon voices
EXPERT = [("NorthlightDana", "Dana Feld", "Threat researcher, Northlight Threat Lab.", None, 7900, "CHR-063", ["influence operations", "phishing"]),
          ("McCreadyMaritime", "Ian McCready", "Independent maritime security analyst. Former Coast Guard watchstander.", None, 5200, "CHR-062", ["ais", "port security"]),
          ("DrSofiaMarquez", "Dr. Sofia Marquez", "Disaster equity researcher, Texas A&M University-Corpus Christi.", "Bay Area", 2700, "CHR-061", ["equity", "aid"]),
          ("NathanBrooksOcean", "Dr. Nathan Brooks", "Coastal oceanographer, Texas A&M University-Corpus Christi.", "Bay Area", 1900, "CHR-060", ["surge", "spill transport"]),
          ("GraceHollowayLEA", "Grace Holloway", "Energy market analyst, Lanternfish Energy Analytics.", None, 6400, "CHR-064", ["exports", "freight"])]
for h, n, bio, area, fol, cid, topics in EXPERT:
    persona(h, n, "individual", bio, CC if area else "Texas", area, fol, rdate("2011-01-01", "2020-12-31"), style="careful, sourced", per_day=1.2, topics=topics, truth={"character_id": cid})
persona("HargroveBait", "Hargrove Bait & Tackle", "business", "Bait, ice and tall tales by the jetties in Port Aransas.", "Port Aransas, TX", "Port Aransas", 1300, "2014-03-15", style="jokes, tide reports", per_day=0.8, hours="05:00-19:00", topics=["bait", "jetties"], truth={"character_id": "CHR-042"})
# ---- feed accounts kept from the first social stream
FEED = [("TamaraMossCC", "Tamara Moss", "Nurse, mom, Southside. Tired.", "Southside", 1100, 3.5), ("fishermanchuy", "Chuy Garza", "Pescador. Port A y la bahía.", "Port Aransas", 440, 3),
        ("luisa_corpus", "Luisa Medina", "Molina de corazón. Mamá de dos.", "Molina", 215, 3), ("localDadCC", "Marcus Webb", "Dad of three. Youth soccer coach. Calallen.", "Calallen", 142, 2.5),
        ("MariaRamirez_CC", "Maria Ramirez", "Maestra. Oak Park.", "Oak Park", 820, 2.5), ("skipperboatCC", "Bobby Skipper", "Charter captain out of Port A.", "Port Aransas", 650, 2.5),
        ("joseluisbarrera", "José Luis Barrera", "Soldador. Hillcrest.", "Hillcrest", 310, 2.5), ("ShelterVolunteer_Ana", "Ana Villanueva", "Shelter volunteer. Coffee is a food group.", "Central City", 275, 2.5),
        ("abuelo_pescador", "Roberto Cantu", "Abuelo, pescador, veterano.", "Flour Bluff", 189, 1.7), ("portworker_cc", "CC Port Worker", "Longshore. Speaking for myself only.", "North Beach", 1200, 1.5),
        ("DerekNancyRescue", "Derek and Nancy", "Two neighbours with a jon boat.", "Flour Bluff", 300, 1.4), ("CCReliefVolunteer", "CC Relief Volunteer Coordination", "Matching volunteers to needs after Rafael.", "Central City", 2200, 3),
        ("GulfEnviroWatch", "Gulf Environmental Watch", "Watching the water. Citizen science on the Texas coast.", "Portland", 7200, 3), ("txcoastalngo", "Texas Coastal Alliance", "Advocating for coastal communities.", "Downtown", 3400, 2)]
for h, n, bio, area, fol, pd_ in FEED:
    es = h in ("fishermanchuy", "luisa_corpus", "joseluisbarrera", "abuelo_pescador", "MariaRamirez_CC")
    persona(h, n, "organization" if h in ("CCReliefVolunteer", "GulfEnviroWatch", "txcoastalngo") else "individual", bio, CC, area, fol, rdate("2012-01-01", "2024-12-31"),
            lang="es/en" if es else "en", style="first-hand, emotional, photos", per_day=pd_, topics=["storm", "neighbourhood"])
# ---- local businesses and community groups (fictional)
BIZ = [("PelicanPointMarine", "Pelican Point Marine Supply", "Port Aransas"), ("BluffHardware", "Bluff Hardware & Lumber", "Flour Bluff"), ("SixPointsCoffee", "Six Points Coffee Co.", "Six Points"),
       ("NorthBeachMotel", "Seawall Inn North Beach", "North Beach"), ("CalallenFeed", "Calallen Feed & Ranch", "Calallen"), ("PanaderiaLaPaloma", "Panadería La Paloma", "Westside"),
       ("MolinaMeatMkt", "Molina Meat Market", "Molina"), ("IslandSurfShopPA", "Island Surf Shop", "Port Aransas"), ("LeopardStAuto", "Leopard Street Auto Repair", "Hillcrest"),
       ("SouthsidePharmacy", "Southside Family Pharmacy", "Southside"), ("PortlandBoatStore", "Portland Boat Storage", "Portland"), ("RockportArtCoop", "Rockport Art Co-op", "Rockport"),
       ("ArPassShrimpCo", "Aransas Pass Shrimp Co-op", "Aransas Pass"), ("BayfrontCharters", "Bayfront Charters", "Downtown"), ("AnnavilleDiner", "Annaville Diner", "Annaville"),
       ("LagunaTowing", "Laguna Towing", "Port Aransas"), ("GulfReliefLogistics", "Gulf Relief Logistics", "Westside"), ("RendalTerminals", "Rendal Terminals", "Downtown")]
for h, n, area in BIZ:
    persona(h, n, "business", f"{n}. {area}.", CC if area not in ("Port Aransas", "Rockport", "Portland", "Aransas Pass") else f"{area}, TX", area, R.randint(150, 2600), rdate("2012-01-01", "2023-12-31"),
            style="hours, closures, reopening", per_day=round(R.uniform(0.3, 1.2), 1), hours="07:00-20:00", topics=["hours", "reopening"], lang="es/en" if "Pana" in n or "Molina" in n else "en")
GROUPS = [("OakParkVecinos", "Oak Park Neighbors / Vecinos", "Oak Park", "es/en"), ("HillcrestResidents", "Hillcrest Residents Association", "Hillcrest", "en"), ("NorthBeachCA", "North Beach Community Association", "North Beach", "en"),
          ("FlourBluffHelps", "Flour Bluff Helps", "Flour Bluff", "en"), ("MolinaUnida", "Molina Unida", "Molina", "es/en"), ("StJudeReliefHub", "St. Jude Fellowship Hall Relief Hub", "Central City", "en/es"),
          ("PortACleanup", "Port A Cleanup Crew", "Port Aransas", "en"), ("CalallenWaterRuns", "Calallen Water Runs", "Calallen", "en"), ("CoastalBendPets", "Coastal Bend Lost Pets", "Southside", "en"),
          ("VietFishermenCB", "Coastal Bend Vietnamese Fishermen", "Aransas Pass", "vi/en")]
for h, n, area, lg in GROUPS:
    persona(h, n, "organization", f"Community group. {area}.", CC, area, R.randint(200, 3200), rdate("2014-01-01", "2027-09-20"), lang=lg, style="needs, offers, meeting times", per_day=round(R.uniform(1, 4), 1), topics=["mutual aid", area.lower()],
            truth={"character_id": "CHR-049"} if h == "StJudeReliefHub" else None)
# ---- automated accounts
BOTS = [("CC_WxBot", "Corpus Christi Weather Bot", "Automated hourly observations from the airport station."), ("NuecesRiverGauge", "Nueces River at Calallen", "Automated river stage readings."),
        ("CCTrafficAlerts", "CC Traffic Alerts", "Automated road incident feed."), ("TXOutageCount", "Texas Outage Counter", "Automated customer outage counts by county."),
        ("GulfBuoyBot", "Gulf Buoy Bot", "Automated wave and wind readings from offshore buoys."), ("AransasFerryWait", "Port Aransas Ferry Wait", "Automated ferry wait times."),
        ("TideBotCC", "Bay Tide Bot", "Automated tide readings for Corpus Christi Bay.")]
for h, n, bio in BOTS:
    persona(h, n, "automated", bio, CC, None, R.randint(300, 5200), rdate("2015-01-01", "2024-12-31"), style="templated readings", per_day=24, hours="00:00-24:00", storm="stops when its data source goes offline", topics=["automated"], following=R.randint(0, 12))
# ---- out-of-area amplifiers
AMP = [("StormChaseTexas", "Storm Chase Texas", "Chasing every landfall.", "Dallas, TX", 88000), ("HurricaneTrackerUSA", "Hurricane Tracker USA", "Tracking the tropics.", "Florida", 310000),
       ("GulfEnergyDesk", "Gulf Energy Desk", "Energy headlines.", "Houston, TX", 23000), ("PrepperDadTX", "Prepper Dad TX", "Be ready.", "Hill Country, TX", 14000),
       ("CajunNavyRelief", "Bayou Boat Brigade", "Volunteer boat rescuers.", "Louisiana", 67000), ("RealTalkTexas", "Real Talk Texas", "Texas politics, unfiltered.", "Austin, TX", 41000),
       ("OilPatchInsider", "Oil Patch Insider", "Permian to the port.", "Midland, TX", 19000), ("DisasterWatchLive", "Disaster Watch Live", "Live feeds from disasters worldwide.", "", 152000),
       ("SATXNewsJunkie", "SATX News Junkie", "San Antonio news watcher.", "San Antonio, TX", 7600), ("ValleyStormWatch", "Valley Storm Watch", "RGV weather.", "McAllen, TX", 12500),
       ("WorldLineNews24", "World Line News", "International news, 24 hours.", "", 540000)]
for h, n, bio, loc, fol in AMP:
    persona(h, n, "individual" if h not in ("WorldLineNews24", "GulfEnergyDesk") else "media", bio, loc, None, fol, rdate("2011-01-01", "2022-12-31"), style="reposts with commentary", per_day=round(R.uniform(6, 20), 1), hours="00:00-24:00", topics=["storm", "viral"],
            verified=h == "WorldLineNews24", truth={"character_id": "CHR-082", "note": "The foreign state broadcaster; never name its country.", "authentic": True, "state_media": True} if h == "WorldLineNews24" else None)

# ---- residents and the coordinated network, generated together and shuffled so that neither ids nor
# file order separate them
FEMALE = set("Karen Angela Keisha Tanya Brenda Shelby Amber Kayla Becky Stacy Tina Monica Diane Lori Heather Jenna Megan Dawn Wanda Latoya Denise Brooke Peggy Trudy "
             "Maria Ana Rosa Elena Patricia Sandra Veronica Yolanda Gloria Alma Norma Noemi Irma Lidia Delia Sonia Carmen Leticia Dolores Lupe Concha Tere Linh Kim Lan Mai Hoa".split())
BIO_EN = {"f": ["{area} born and raised.", "Mom of {n}. {area}.", "Teacher. {area}.", "Nurse. Night shift.", "Islander alum. {area}.", "Small business owner in {area}.", "Navy wife. Here since {y}.", "Grandma of {n}. Retired.", "", ""],
          "m": ["{area} born and raised.", "Dad of {n}. {area}.", "Refinery {job}. Views mine.", "Just here for the Hooks and the weather.", "Retired. Fishing. Grandkids.", "{area}. Dogs, trucks, tacos.", "Welder. Dad. {area}.", "Navy vet. Here since {y}.", "", ""]}
BIO_ES = {"f": ["De {area}. Familia primero.", "Mamá de {n}. {area}.", "Orgullosamente de {area}.", "Abuela de {n}.", "Cocinera. {area}.", ""],
          "m": ["De {area}. Familia primero.", "Papá de {n}. {area}.", "Trabajador. Padre. {area}.", "Orgullosamente de {area}.", "Fe, familia y fútbol.", ""]}
NET_BIO = {"f": ["{a} mom. {k1}, {k2}.", "Proud {k1} native. {k2} strong.", "{k1} | {k2} | faith and family", "Lifelong {k1} resident. {k2}.", "{a}. {k1}.", "Nurse and mom. {k1}, {k2}."],
           "m": ["{a} dad. {k1}, {k2}.", "Proud {k1} native. {k2} strong.", "{k1} | {k2} | faith and family", "Jogging the NAS trails. {k1}, {k2}.", "Lifelong {k1} resident. {k2}.", "{a}. {k1}."]}
STYLE = ["first-hand, short", "asks neighbours for information", "shares official posts, adds worry", "photos and video", "angry at the utility, specific", "jokes through it", "practical: what is open, what is not", "prays, thanks volunteers"]
HOURS = ["06:00-23:00", "07:00-22:00", "05:30-21:30", "08:00-01:00", "06:00-01:00", "09:00-02:00", "07:00-00:00"]
used_names = {p["display_name"] for p in personas}


def resident_name(lang):
    while True:
        if lang.startswith("es"):
            n = f"{R.choice(FIRST_ES)} {R.choice(LAST_ES)}"
        elif lang.startswith("vi"):
            n = f"{R.choice(FIRST_VI)} {R.choice(LAST_VI)}"
        else:
            n = f"{R.choice(FIRST_EN)} {R.choice(LAST_EN + LAST_ES[:12])}"
        if n not in used_names:
            used_names.add(n)
            return n


def sex(name):
    return "f" if name.split()[0] in FEMALE else "m"


def make_handle(name, area):
    f, l = re.sub(r"[^A-Za-z]", "", name.split()[0]), re.sub(r"[^A-Za-z]", "", name.split()[-1])
    for _ in range(40):
        pat = R.choice(["{f}{l}{d2}", "{f}_{l}", "{fl}{l}{d2}", "{f}{a}", "{l}{f}_{d2}", "{f}{d4}", "{f}in{a}", "{nick}_{a}", "{f}{l}CC", "{l}fam{d2}"])
        h = pat.format(f=f, l=l, fl=f[0], d2=R.randint(10, 99), d4=R.randint(1970, 2009), a=re.sub(r"[^A-Za-z]", "", area)[:9] if area else "TX",
                       nick=R.choice(["coastal", "bay", "island", "gulf", "southtx", "sparkling", "salty", "storm"]))
        if h.lower() not in handles and h.lower() not in pending and len(h) <= 15:
            pending.add(h.lower())
            return h
    h = f"{f}{R.randint(10000, 99999)}"
    pending.add(h.lower())
    return h


def created_date(recent_bias=0.14):
    if R.random() < recent_bias:
        return rdate("2027-05-01", "2027-10-10")
    return rdate("2009-06-01", "2027-04-30")


pending, pool = set(), []
OUTSIDE = ("Portland", "Ingleside", "Aransas Pass", "Port Aransas", "Rockport", "Fulton", "Robstown", "Gregory", "Kingsville")
for i in range(118):
    area = R.choices(AREA_NAMES, AREA_W)[0]
    r = R.random()
    lang = ("es" if r < 0.18 else "es/en" if r < 0.45 else "en") if area in ES_HEAVY else ("es/en" if r < 0.14 else "vi/en" if r < 0.17 and area in ("Aransas Pass", "Rockport", "Port Aransas", "Flour Bluff") else "en")
    name = resident_name(lang)
    bio = R.choice((BIO_ES if lang.startswith("es") else BIO_EN)[sex(name)]).format(area=area, n=R.randint(2, 5), job=R.choice(["operator", "pipefitter", "inspector"]), y=R.randint(2015, 2026))
    pool.append(dict(handle=make_handle(name, area), name=name, atype="individual", bio=bio, location=f"{area}, TX" if area in OUTSIDE else CC, area=area,
                     followers=int(R.lognormvariate(5.6, 1.0)), created=created_date(), lang=lang, style=R.choice(STYLE), per_day=round(R.lognormvariate(0.2, 0.7), 1), hours=R.choice(HOURS),
                     topics=["storm", area.lower()]))

# the coordinated network: 47 operator accounts (4 are in the original catalogue above)
NET_NAMED = [("TXCoastalWatchdog", "TX Coastal Watchdog", "Holding Coastal Bend officials accountable. Corpus Christi, South Texas.", "Central City", 6900, "2027-09-07", "SOC-ACC-5003", ["198.51.47.112", "198.51.47.118", "198.51.47.203"]),
             ("NuecesLocalNews", "Nueces Local News", "Independent local updates for Nueces County and Corpus Christi. Not affiliated with any station.", "Southside", 4300, "2027-09-07", "SOC-ACC-5004", ["198.51.48.44", "198.51.48.91"])]
for h, n, bio, area, fol, cr, acc, ips in NET_NAMED:
    pending.add(h.lower())
    pool.append(dict(handle=h, name=n, atype="individual", bio=bio, location=CC, area=area, followers=fol, created=cr, lang="en", style="confident claims, unnamed sources, hashtags", per_day=11, hours="05:30-02:00",
                     storm="posts constantly", topics=["shelters", "roads", "utility", "investigation"],
                     truth={"authentic": False, "network": ["base_40", "t15_47"], "soc_acc": acc, "kind": "created in the pre-positioning window", "source_ips": ips, "asn": "198765 Meridian Transit Hosting, NL", "removed_d38": True,
                            "note": "Lead accounts of all three T15 phases; 60% of other network posts follow theirs within 240 s."}))
LOCAL_KW = ["Corpus Christi", "South Texas", "Nueces County", "Coastal Bend"]
soc_acc_n = 7
for i in range(47 - 6):
    aged = i < 13                    # 16 aged in total with the 3 named aged accounts
    area = R.choices(AREA_NAMES[:18], AREA_W[:18])[0]
    lang = "es/en" if (area in ES_HEAVY and R.random() < 0.35) else "en"
    name = resident_name(lang)
    kws = R.sample(LOCAL_KW, 2) if i % 5 != 0 else [R.choice(LOCAL_KW)]
    bio = R.choice(NET_BIO[sex(name)]).format(a=area, k1=kws[0], k2=kws[-1])
    in_base = i < 34                 # 40 in the rumour network with the 6 named ones
    acc = f"SOC-ACC-{5000 + soc_acc_n}" if in_base else f"SOC-ACC-{5041 + (i - 34)}"
    if in_base:
        soc_acc_n += 1
    pool.append(dict(handle=make_handle(name, area), name=name, atype="individual", bio=bio, location=CC, area=area,
                     followers=int(R.lognormvariate(5.4, 0.9)) if not aged else int(R.lognormvariate(6.6, 0.8)),
                     created=rdate("2019-03-01", "2026-11-30") if aged else R.choice(["2027-09-07", "2027-09-07", "2027-09-08", "2027-09-08", "2027-09-08", "2027-09-09"]),
                     lang=lang, style=R.choice(STYLE[:5]), per_day=round(R.uniform(3, 9), 1), hours=R.choice(HOURS), topics=["storm", area.lower()],
                     truth={"authentic": False, "network": (["base_40"] if in_base else []) + ["t15_47"], "soc_acc": acc, "kind": "aged account" if aged else "created in the pre-positioning window",
                            "profile_image": R.choice(["generated face", "stock photo"]), "removed_d38": True}))
R.shuffle(pool)
for q in pool:
    persona(q["handle"], q["name"], q["atype"], q["bio"], q["location"], q["area"], q["followers"], q["created"], lang=q["lang"], style=q["style"], per_day=q["per_day"], hours=q["hours"],
            storm=q.get("storm", ""), topics=q["topics"], truth=q.get("truth"))
net = [pid for pid, t in ptruth.items() if not t["authentic"]]
assert len(net) == 47, len(net)
assert sum(1 for pid in net if "base_40" in ptruth[pid]["network"]) == 40
created_window = sum(1 for p in personas if p["persona_id"] in net and "2027-09-07" <= p["account_created"] <= "2027-09-09")
assert created_window == 31, created_window

# ---- compact list of low-profile accounts (some later removed by the platforms)
compact, removed800 = [], []
for i in range(1700):
    area = R.choices(AREA_NAMES + [None], AREA_W + [38])[0]
    r = R.random()
    lang = "es" if r < 0.16 else "es/en" if r < 0.3 else "en"
    name = f"{R.choice(FIRST_ES if lang.startswith('es') else FIRST_EN)} {R.choice(LAST_ES if lang.startswith('es') else LAST_EN)}"
    h = make_handle(name, area or "TX")
    compact.append(["@" + h, created_date(0.2), bucket(int(R.lognormvariate(4.6, 1.1))), lang, area])
for row in R.sample(compact, 800):
    removed800.append(row[0])

# resolve home areas against the land-side area registry when it is present
AREA_FALLBACK = {"South Bluff": "AREA-ZIP-78404", "Six Points": "AREA-ZIP-78404", "Loma Alta": "AREA-WD-4", "Central City": "AREA-ZIP-78405", "Bay Area": "AREA-ZIP-78412", "Tuloso-Midway": "AREA-NBH-TULOSO"}
areas_fp = os.path.join(OUT, "areas.json")
area_id, unresolved = {}, set()
if os.path.exists(areas_fp):
    for a in json.load(open(areas_fp, encoding="utf-8"))["areas"]:
        if a["area_type"] in ("neighbourhood", "city"):
            area_id.setdefault(a["name"], a["area_id"])
    known_ids = {a["area_id"] for a in json.load(open(areas_fp, encoding="utf-8"))["areas"]}
    for nm, aid in AREA_FALLBACK.items():
        if aid in known_ids:
            area_id.setdefault(nm, aid)


def resolve(area):
    if area is None:
        return None
    if area in area_id:
        return area_id[area]
    unresolved.add(area)
    return None


for p_ in personas:
    p_["home_area_id"] = resolve(p_["home_area"])
compact = [row + [resolve(row[4])] for row in compact]
personas_doc = {
    "catalog_meta": {"description": "Social media accounts that appear in the social stream: who they say they are, where, since when, how they post.",
                     "platform": "X (short-post platform)", "fields": "handle, display name, type, self-description, stated location, home area, followers, creation date, verified flag, language, posting style and cadence",
                     "home_area": "neighbourhood or community name; home_area_id is the matching id in 06_data_streams/areas.json (a ZIP or district where the area registry has no neighbourhood of that name); null for accounts outside the Coastal Bend",
                     "counts": {"personas": len(personas), "accounts_compact": len(compact)}},
    "personas": personas,
    "accounts_compact": {"columns": ["handle", "account_created", "follower_range", "language", "home_area", "home_area_id"], "rows": compact},
}
dump(personas_doc, OUT, "personas.json")
by_handle = {p["handle"][1:].lower(): p["persona_id"] for p in personas}
dump({"_about": "Internal. Never delivered. Which accounts are operator-run, network membership, character links, release gating and how old handles map onto personas.json.",
      "personas": ptruth,
      "networks": {"base_40": {"what": "rumour network, about 18,000 posts D+2 to D+20 linking aid-help-portal.example; second wave D+75 to D+85", "persona_ids": [p for p in net if "base_40" in ptruth[p]["network"]],
                               "scenario_ids": "SOC-ACC-5001 to SOC-ACC-5040"},
                   "t15_47": {"what": "47 pre-positioned accounts; 31 created 2027-09-07 to 2027-09-09; phases 1 to 3", "persona_ids": net},
                   "removed_d38_847": {"operator_accounts": 47, "note": "45 active plus 2 removed earlier", "amplifiers_800": removed800}},
      "gating": {"@CoastTruthTX": 2, "@GulfWatchPatriot": 3, "aid-help-portal.example": 16, "note": "Days from which news and officials may name them; the accounts themselves post earlier."},
      "id_migration": {"feed_handles": {"GridWaterCC": "@CBPWA_Alerts", "CallerTimes": "@BaysideLedger (real newspaper name removed)", "KIIITVNews": "@Harborline6News (real station name removed)",
                                        "SinaiHospitalCC": "@ShorelineRegionalMC", "CCHarborPilots": "@CCBarPilots", "NationalHurricaneCenter": "@NationalHurricaneCenter", "same_handle": "all other handles in the first social stream are kept unchanged"},
                       "old_personas_json": {"SOC-001..SOC-032": "same ids", "SOC-009 display name": "Gulfwater Maritime Report (was 'Journal')", "SOC-010 display name": "KNCB Coastal Bend Radio 1480 AM",
                                             "SOC-015 bio": "real hospital-system name removed"},
                       "scenario_entities": {"SOC-ACC-5001": "@CoastTruthTX", "SOC-ACC-5002": "@GulfWatchPatriot", "SOC-ACC-5003": "@TXCoastalWatchdog", "SOC-ACC-5004": "@NuecesLocalNews",
                                             "SOC-ACC-5001 to 5040": "see personas[*].soc_acc", "old PER-007, PER-022 (crypto senders)": "no longer used"},
                       "names": {"GridWater Corpus Christi": "Coastal Bend Power and Water Authority"}},
      "home_areas_without_a_neighbourhood_record": {"mapped_to_zip_or_district": AREA_FALLBACK, "unresolved": sorted(unresolved)}},
     INT, "personas_truth.json")

# ======================================================================================
# ORGANISATIONS
# ======================================================================================
orgs, otruth, oid = [], {}, {}


def org(name, typ, parent=None, jur="", role="", aliases=None, truth=None, abbr=None):
    i = f"ORG-{1001 + len(orgs)}"
    o = {"org_id": i, "name": name, "type": typ, "parent": parent, "jurisdiction": jur, "public_role": role}
    if abbr:
        o["abbr"] = abbr
    if aliases:
        o["aliases"] = aliases
    orgs.append(o)
    oid[name] = i
    if truth:
        otruth[i] = truth
    return i


US, TX, NC = "United States", "Texas", "Nueces County, TX"
# federal
org("Department of Homeland Security", "federal department", None, US, "Parent of FEMA, CISA and the Coast Guard", abbr="DHS")
org("Federal Emergency Management Agency", "federal agency", "Department of Homeland Security", US, "Federal disaster response and aid", abbr="FEMA", aliases=["Emergency Management Agency"])
org("FEMA Region 6", "federal office", "Federal Emergency Management Agency", "Denton, TX", "Regional office for Texas", aliases=["FEMA Region"])
org("FEMA Joint Field Office, DR-4821-TX", "federal office", "FEMA Region 6", "Corpus Christi, TX", "Coordinates federal response to Hurricane Rafael", aliases=["Joint Field Office", "JFO"])
org("FEMA Individual Assistance", "programme", "Federal Emergency Management Agency", US, "Aid to households; registration opened Nov. 13, 2027", aliases=["FEMA IA", "FEMA's Individual Assistance"])
org("FEMA Mitigation Assessment Team", "federal office", "Federal Emergency Management Agency", US, "Aerial and engineering damage assessment", aliases=["FEMA's Mitigation Assessment Team", "Hurricane Rafael Aerial Assessment Program"])
org("Cybersecurity and Infrastructure Security Agency", "federal agency", "Department of Homeland Security", US, "Cyber advisories and incident response support", abbr="CISA")
org("U.S. Coast Guard", "federal agency", "Department of Homeland Security", US, "Port safety, search and rescue, pollution response", abbr="USCG", aliases=["Coast Guard", "US Coast Guard", "United States Coast Guard"])
org("Coast Guard District 8", "federal office", "U.S. Coast Guard", "New Orleans, LA", "Gulf Coast district command", aliases=["Coast Guard District"])
org("Coast Guard Sector Corpus Christi", "federal office", "Coast Guard District 8", "Corpus Christi, TX", "Captain of the Port; sets port conditions; Federal On-Scene Coordinator for the spill",
    aliases=["U.S. Coast Guard Sector Corpus Christi", "Marine Safety Unit Corpus Christi", "Coast Guard FOSC", "Coast Guard Federal On-Scene Coordinator"], truth={"scenario_id": "FAC-USCG-01"})
org("Coast Guard Air Station Corpus Christi", "federal office", "Coast Guard Sector Corpus Christi", "Corpus Christi, TX", "Helicopter and fixed-wing search and rescue", aliases=["Air Station Corpus Christi"])
org("Coast Guard Station Port Aransas", "federal office", "Coast Guard Sector Corpus Christi", "Port Aransas, TX", "Small-boat station at the jetties")
org("Vessel Traffic Service Corpus Christi", "federal office", "Coast Guard Sector Corpus Christi", "Corpus Christi, TX", "Vessel traffic management in the ship channel")
org("Coast Guard National Pollution Funds Center", "federal office", "U.S. Coast Guard", US, "Pays spill claims the responsible party does not; administers the Oil Spill Liability Trust Fund", aliases=["National Pollution Funds Center", "Oil Spill Liability Trust Fund"])
org("National Response Center", "federal office", "U.S. Coast Guard", US, "Takes reports of oil and chemical releases")
org("Unified Command, Inner Harbor spill", "incident command", "Coast Guard Sector Corpus Christi", "Corpus Christi, TX", "Coast Guard and Texas General Land Office joint command for the tanker spill", aliases=["Unified Command", "Unified Command of the Coast Guard"])
org("National Oceanic and Atmospheric Administration", "federal agency", None, US, "Weather, tides, charts", abbr="NOAA")
org("National Weather Service", "federal agency", "National Oceanic and Atmospheric Administration", US, "Forecasts and warnings", abbr="NWS")
org("National Weather Service Corpus Christi", "federal office", "National Weather Service", "Corpus Christi, TX", "Local forecast office", aliases=["NWS Corpus Christi"])
org("National Hurricane Center", "federal office", "National Weather Service", "Miami, FL", "Hurricane advisories", abbr="NHC")
org("NOAA Aircraft Operations Center", "federal office", "National Oceanic and Atmospheric Administration", "Lakeland, FL", "Hurricane Hunter reconnaissance flights", aliases=["NOAA Hurricane Hunter", "NOAA Hurricane Hunters"])
org("Federal Bureau of Investigation", "federal agency", None, US, "Criminal and counterintelligence investigations", abbr="FBI")
org("FBI Houston Division", "federal office", "Federal Bureau of Investigation", "Houston, TX", "Field office covering the Coastal Bend", aliases=["FBI's Houston Division", "FBI Houston"])
org("FBI Corpus Christi Resident Agency", "federal office", "FBI Houston Division", "Corpus Christi, TX", "Local FBI office")
org("Operation Sandbar", "programme", "FBI Corpus Christi Resident Agency", "Corpus Christi, TX", "Disaster-fraud investigation announced Dec. 13, 2027", truth={"thread": "T22", "public_from_day": 90})
org("U.S. Attorney's Office for the Southern District of Texas", "federal office", None, "Houston, TX", "Federal prosecutions and forfeiture filings", aliases=["US Attorney's Office, Southern District of Texas"])
org("National Center for Disaster Fraud", "federal office", None, US, "Takes disaster-fraud complaints")
org("DHS Office of Inspector General", "federal office", "Department of Homeland Security", US, "Reviews emergency contracts", aliases=["federal inspector general"])
org("Department of Defense", "federal department", None, US, "Military departments", aliases=["Defense Department"])
org("U.S. Navy", "military service", "Department of Defense", US, "")
org("Navy Region Southeast", "military unit", "U.S. Navy", "Jacksonville, FL", "Regional command for Navy installations in Texas")
org("Naval Air Station Corpus Christi", "military unit", "Navy Region Southeast", "Corpus Christi, TX", "Navy flight training base", abbr="NAS Corpus Christi", truth={"scenario_id": "FAC-DOD-01"})
org("Naval Air Station Kingsville", "military unit", "Navy Region Southeast", "Kingsville, TX", "Navy jet training base", truth={"scenario_id": "FAC-DOD-03"})
org("Naval Air Station Joint Reserve Base Fort Worth", "military unit", "Navy Region Southeast", "Fort Worth, TX", "Evacuation base for training aircraft", truth={"scenario_id": "FAC-DOD-04"})
org("Navy explosive ordnance disposal and mine countermeasures teams", "military unit", "U.S. Navy", US, "Searched and cleared the ship channel")
org("Navy Family Accountability and Assessment System", "programme", "U.S. Navy", US, "Family check-in system after disasters")
org("U.S. Army", "military service", "Department of Defense", US, "")
org("Corpus Christi Army Depot", "military unit", "U.S. Army", "Corpus Christi, TX", "Helicopter repair depot on NAS Corpus Christi", abbr="CCAD", truth={"scenario_id": "FAC-DOD-02"})
org("Fort Hood", "military unit", "U.S. Army", "Killeen, TX", "Home of the aviation brigade shipping through the port", truth={"scenario_id": "FAC-DOD-06"})
org("Defense Logistics Agency", "federal agency", "Department of Defense", US, "Military supply")
org("DLA Distribution Corpus Christi", "federal office", "Defense Logistics Agency", "Corpus Christi, TX", "Parts support for the depot", truth={"scenario_id": "FAC-DOD-05"})
org("U.S. Air Force Air Mobility Command", "military unit", "Department of Defense", US, "Relief airlift", aliases=["Air Force"])
org("Texas Army National Guard", "military unit", None, TX, "Helicopter and high-water rescue support", aliases=["National Guard", "Texas National Guard"])
org("Federal Aviation Administration", "federal agency", None, US, "Airspace restrictions, GPS notices", abbr="FAA", aliases=["Aviation Administration"])
org("CBP Air and Marine Operations", "federal office", "Department of Homeland Security", "Corpus Christi, TX", "Maritime patrol aircraft")
org("Environmental Protection Agency Region 6", "federal office", None, "Dallas, TX", "Environmental response and assessment", aliases=["EPA Region 6", "EPA Region"])
org("U.S. Army Corps of Engineers, Galveston District", "federal office", "U.S. Army", "Galveston, TX", "Channel surveys and debris missions", abbr="USACE Galveston")
org("Small Business Administration Disaster Loan Program", "programme", None, US, "Disaster loans")
org("National Flood Insurance Program", "programme", "Federal Emergency Management Agency", US, "Federal flood insurance", abbr="NFIP")
# state
org("Office of the Governor of Texas", "state office", None, TX, "Disaster declarations")
org("Texas Division of Emergency Management", "state agency", None, TX, "State emergency management", abbr="TDEM", aliases=["Texas TDEM"])
org("Texas General Land Office", "state agency", None, TX, "Oil spill programme; Unified Command partner", abbr="GLO")
org("Texas Commission on Environmental Quality", "state agency", None, TX, "Air and water quality regulation", abbr="TCEQ")
org("Texas Department of State Health Services", "state agency", None, TX, "Shellfish closures, outbreak investigation", abbr="DSHS")
org("Texas Parks and Wildlife Department", "state agency", None, TX, "Fishing closures", abbr="TPWD")
org("Texas Department of Transportation", "state agency", None, TX, "Bridges, causeway, ferry", abbr="TxDOT")
org("Texas Department of Public Safety", "state agency", None, TX, "Consumer and contractor fraud warnings", abbr="DPS")
org("Office of the Texas Attorney General", "state agency", None, TX, "Consumer protection advisories")
org("Texas Department of Insurance", "state agency", None, TX, "Claims oversight; fraud task force", abbr="TDI")
org("Texas Department of Licensing and Regulation", "state agency", None, TX, "Contractor licensing")
org("Public Utility Commission of Texas", "state agency", None, TX, "Utility regulation", abbr="PUC")
org("Electric Reliability Council of Texas", "grid operator", None, TX, "Operates the Texas grid", abbr="ERCOT")
org("Texas Cyber Command", "state agency", None, TX, "State cyber incident response")
org("Texas A&M Task Force 1", "state agency", None, TX, "Urban search and rescue", aliases=["Texas Task Force 1", "Texas Task Force"])
org("Texas A&M Engineering Extension Service", "state agency", None, TX, "Parent of Task Force 1")
org("Texas Windstorm Insurance Association", "insurer of last resort", None, TX, "Wind and hail coverage on the coast", abbr="TWIA")
org("Insurance Council of Texas", "association", None, TX, "Insurance trade group")
# local
org("City of Corpus Christi", "local government", None, "Corpus Christi, TX", "City government")
org("City of Corpus Christi Water Department", "local agency", "City of Corpus Christi", "Corpus Christi, TX", "City water utility; issues boil-water notices with CBPWA", aliases=["City of Corpus Christi water utility", "City of Corpus Christi Water Services", "Corpus Christi Water Districts", "Water Districts"])
org("Corpus Christi Fire Department", "local agency", "City of Corpus Christi", "Corpus Christi, TX", "Fire, EMS, rescue", abbr="CCFD")
org("Corpus Christi Police Department", "local agency", "City of Corpus Christi", "Corpus Christi, TX", "Police", abbr="CCPD")
org("City of Corpus Christi Emergency Management", "local agency", "City of Corpus Christi", "Corpus Christi, TX", "City emergency operations")
org("Corpus Christi International Airport", "local agency", "City of Corpus Christi", "Corpus Christi, TX", "Commercial airport")
org("Nueces County", "local government", None, NC, "County government")
org("Nueces County Office of Emergency Management", "local agency", "Nueces County", NC, "County emergency management; shelters and evacuation", aliases=["Nueces County Emergency Management Coordinator"])
org("Nueces County Commissioners Court", "local government", "Nueces County", NC, "County governing body; awarded the debris contract")
org("Nueces County Sheriff's Office", "local agency", "Nueces County", NC, "County law enforcement")
org("Nueces County Medical Examiner", "local agency", "Nueces County", NC, "Storm fatality counts")
org("Nueces County Appraisal District", "local agency", None, NC, "Property valuations")
org("Nueces County Language Access Services", "local agency", "Nueces County", NC, "Translation of emergency notices", abbr="NCLAS")
org("NuecesInfoLine", "programme", "Nueces County", NC, "Non-emergency information line opened Sept. 26, 2027")
org("Corpus Christi-Nueces County Public Health District", "local agency", None, NC, "Public health surveillance and advisories")
org("Coastal Bend Emergency Communications Center", "local agency", None, NC, "911 centre for Corpus Christi and Nueces County", abbr="CBECC", truth={"scenario_id": "PSAP-01"})
org("Coastal Bend Regional Transit", "local agency", None, NC, "Buses; evacuation pickups")
org("Corpus Christi Independent School District", "school district", None, "Corpus Christi, TX", "Schools; shelter sites", abbr="CCISD")
org("Richard King High School", "school", "Corpus Christi Independent School District", "Corpus Christi, TX", "Shelter site")
org("Del Mar College", "college", None, "Corpus Christi, TX", "Shelter site at the East campus", aliases=["Del Mar College East"])
org("Texas A&M University-Corpus Christi", "university", None, "Corpus Christi, TX", "Research on equity, surge and spill")
org("San Patricio County", "local government", None, "San Patricio County, TX", "County government")
org("Aransas County", "local government", None, "Aransas County, TX", "County government")
org("Kleberg County", "local government", None, "Kleberg County, TX", "County government")
for c in ("Port Aransas", "Portland", "Ingleside", "Aransas Pass", "Rockport"):
    org(f"City of {c}", "local government", None, f"{c}, TX", "City government")
org("Corpus Christi City Council", "local government", "City of Corpus Christi", "Corpus Christi, TX", "City governing body")
org("Oak Park community center", "community centre", None, "Corpus Christi, TX", "Neighbourhood centre in Oak Park")
org("Port of Corpus Christi", "port authority", None, "Corpus Christi, TX", "Deep-water port; ship channel", aliases=["Port of Corpus Christi Authority"], truth={"scenario_id": "PORT-07"})
# utility and its vendors
org("Coastal Bend Power and Water Authority", "utility", None, "Corpus Christi, TX", "Electric and water utility for the Corpus Christi area", abbr="CBPWA",
    aliases=["Coastal Bend Power & Water Authority", "Coastal Bend Public Works Authority (variant in some stories)", "Coastal Bend Power", "Water Authority"],
    truth={"scenario_id": "GW-ENT-01", "internal_code_name": "GridWater (never participant-facing)"})
org("Meridian Controls Corp", "vendor", None, US, "SCADA and historian supplier to the utility", truth={"scenario_id": "GW-ENT-02"})
org("ClearPath Network Solutions", "vendor", None, US, "Remote-access gateway supplier to the utility", truth={"scenario_id": "GW-ENT-03", "public": "never named in public text"})
org("Vantage Security Systems", "vendor", None, US, "Security monitoring supplier to the utility")
org("Bastille Networks", "vendor", None, US, "Firewall supplier to the utility", truth={"generated": True})
org("Halden Protection", "vendor", None, US, "Protective relay supplier to the utility", truth={"generated": True})
org("Delta Pumps & Controls", "vendor", None, TX, "Pump parts supplier", truth={"scenario_id": "SUP-0219", "note": "quoted 9 days, delivered in 34"})
org("Coastal Bend Aerial Services", "contractor", None, TX, "Aerial thermal survey contractor")
org("Meridian Transit Hosting", "company", None, "Netherlands", "Hosting provider", truth={"note": "ASN 198765; hosts the intruder's exits and the lead influence accounts. Shared with FBI D+30."})
# hospitals (the land-side registry holds sites and ids)
org("Shoreline Regional Medical Center", "hospital", None, "Corpus Christi, TX", "Level II trauma centre", abbr="SRMC")
org("Bay City Medical Center", "hospital", None, "Corpus Christi, TX", "Community hospital", abbr="BCMC")
# maritime and energy
org("Rendal Terminals", "terminal operator", None, "Corpus Christi, TX", "Crude terminal on the Inner Harbor", truth={"scenario_id": "ORG-0950", "public_from_day": 1})
org("Brightwake Marine Systems", "vendor", None, US, "Maintains tanker cargo-control systems", truth={"scenario_id": "SUP-0455", "public_from_day": 8})
org("Brannoch Maritime Holdings", "company", None, "offshore registry", "Holding company named in a January 2028 federal filing", truth={"scenario_id": "ORG-0901", "public_from_day": 114,
    "hidden": "Operates Halcyon Drift; hidden owner of Vantorra and Quellmar; nominee director L. Marrick (CHR-091)."})
org("Kalvora Maritime Holdings Ltd.", "shipping company", None, "Marshall Islands", "Owner of MT Kalvora Star", truth={"public_from_day": 1})
org("Ostrel Shipping Ltd.", "shipping company", None, "Panama", "Owner of MT Ostrel Bay", truth={"public_from_day": 1, "generated": True})
org("Tanker owners' spill claims centre", "programme", None, "Corpus Christi, TX", "Takes cleanup, property and lost-income claims from the spill", aliases=["claims center"])
org("Laguna Towing", "shipping company", None, "Port Aransas, TX", "Harbor tug operator", truth={"public_from_day": 44})
org("Gulf Relief Logistics", "freight forwarder", None, TX, "Relief cargo forwarder", truth={"scenario_id": "SUP-0102"})
org("Coastal Bend Bar Pilots Association", "association", None, "Port Aransas, TX", "Ship channel pilots")
org("Gulf Coast Marine Agency", "ship agent", None, "Corpus Christi, TX", "Ship agency")
org("Quellmar Fuel Partners", "fuel supplier", None, "Corpus Christi, TX", "Emergency fuel supplier to NAS Corpus Christi", truth={"scenario_id": "SUP-0390", "public_from_day": 20, "hidden": "Shell company; shares address and bank account with Vantorra; owned through Brannoch."})
org("Bayline Petroleum Supply", "fuel supplier", None, "Corpus Christi, TX", "Regular fuel supplier to NAS Corpus Christi; terminal flooded in the storm", truth={"generated": True, "note": "Canon leaves the regular supplier unnamed."})
# contractors, property, insurance
org("Vantorra Restoration LLC", "contractor", None, "Corpus Christi, TX", "Debris removal contractor to Nueces County", aliases=["Vantorra Restoration"], truth={"scenario_id": "SUP-0388", "public_from_day": 10, "hidden": "Shell company; owned through Brannoch."})
org("FastDry Coastal LLC", "contractor", None, "Corpus Christi, TX", "Storm restoration contractor", aliases=["FastDry Coastal"], truth={"thread": "T22", "public_from_day": 15, "address": "2817 McArdle Road"})
org("Landmark Pacific Holdings LLC", "property company", None, "Corpus Christi, TX", "Property holding company", abbr="LPH", truth={"thread": "T22", "public_from_day": 90, "address": "4411 Leopard Street", "ip": "198.51.100.44"})
org("Duvall & Sons Property Consultants", "appraiser", None, "Corpus Christi, TX", "Property appraisals", truth={"thread": "T22", "public_from_day": 90})
org("Coastal Meridian Insurance Group", "insurance broker", None, "Corpus Christi, TX", "Insurance brokerage", truth={"thread": "T22", "public_from_day": 90})
org("CCC Coastal Insurance Group", "insurer", None, TX, "Property insurer")
org("Gulf Shield Mutual Insurance", "insurer", None, TX, "Property insurer")
org("Bayfront Property & Casualty", "insurer", None, TX, "Property insurer", truth={"generated": True})
org("Sabine National Insurance", "insurer", None, US, "Property insurer", truth={"generated": True, "note": "Use for the insurer whose special investigations unit made the D+30 referral; the MSEL names a real company there."})
org("Palmetto Reef Insurance Co.", "insurer", None, US, "Property insurer", truth={"generated": True})
org("FastTrack Claims Services LLC", "adjusting firm", None, "Corpus Christi, TX", "Independent claims adjusting")
# media, research, community
for n, cid in (("The Bayside Ledger", "OUT-01"), ("Harborline 6 News", "OUT-02"), ("Coastline Public Radio", "OUT-03"), ("Gulfwater Maritime Report", "OUT-04"), ("Sabal Energy Wire", "OUT-05"),
               ("Continental Wire Service", "OUT-06"), ("Anchor & Rotor Weekly", "OUT-07"), ("KNCB Coastal Bend Radio", "OUT-08")):
    org(n, "media outlet", None, "Corpus Christi, TX" if cid not in ("OUT-04", "OUT-05", "OUT-06") else US, "News outlet", truth={"scenario_id": cid},
        aliases={"OUT-06": ["Continental Wire"], "OUT-07": ["Anchor and Rotor Weekly"]}.get(cid))
org("Northlight Threat Lab", "research firm", None, US, "Threat research; traced the coordinated rumour posts")
org("Lanternfish Energy Analytics", "research firm", None, "Houston, TX", "Energy market analysis")
org("Coastal Alert", "programme", "Texas Division of Emergency Management", TX, "Social media monitoring tool used by the state")
org("Hargrove Bait & Tackle", "business", None, "Port Aransas, TX", "Bait shop near the jetties")
org("St. Jude Fellowship Hall Relief Hub", "church", None, "Corpus Christi, TX", "Neighbourhood church relief hub", truth={"generated_name": True, "character_id": "CHR-049", "note": "Canon calls it a neighbourhood church relief hub without a name."})
org("National Security Council", "federal office", None, US, "White House national security staff")
for n, t in (("Coastal Bend Colonia Alliance", "ngo"), ("Coastal Bend Legal Aid", "ngo"), ("Texas Coastal Alliance", "ngo"), ("Gulf Environmental Watch", "ngo"), ("Coastal Defenders Alliance", "ngo"), ("CC Hope Volunteer Coalition", "ngo"), ("Gulf Coast Relief Network", "ngo"),
             ("Aransas Pass Shrimp Co-op", "association"), ("Coastal Bend Vietnamese Fishermen", "association")):
    org(n, t, None, TX, "Community or advocacy group")
# ---- operators and owners named by the other registries (vessels, terminals, aircraft, sensors, infrastructure)
SUFFIX = re.compile(r",?\s+(LLC|L\.L\.C\.|Inc\.?|Ltd\.?|S\.A\.|LP|AS|Corp\.?|Company|Co\.|\(HK\) Ltd\.|Pte\. Ltd\.)$")


def norm(n):
    n = re.sub(r"\s*\([^)]*\)\s*$", "", n.strip())
    for _ in range(2):
        n = SUFFIX.sub("", n)
    return re.sub(r"^(the|u\.s\.|us|united states)\s+", "", n.lower()).replace("&", "and").strip()


index = {}
for o in orgs:
    for n in [o["name"]] + o.get("aliases", []) + ([o["abbr"]] if o.get("abbr") else []):
        index.setdefault(norm(n), o)
SRC = [("vessels.json", "shipping company"), ("terminal_registry.json", "terminal operator"), ("aircraft_registry.json", "aircraft operator"), ("sensor_registry.json", "agency"),
       ("infrastructure_assets.json", "agency"), ("facility_registry.json", "facility operator"), ("drone_operators.json", "drone operator")]
KEYS = ("operator", "owner", "operator_name", "owner_name", "operated_by", "registered_owner", "managed_by")
GENERIC = {"owner-operated", "private owner", "private", "unknown", "various", "n/a", "none"}
PARENT_HINT = [("U.S. Navy", "U.S. Navy"), ("US Navy", "U.S. Navy"), ("U.S. Army", "U.S. Army"), ("U.S. Air Force", "Department of Defense"), ("U.S. Coast Guard", "U.S. Coast Guard"),
               ("U.S. Customs and Border Protection", "Department of Homeland Security"), ("Texas Army National Guard", "Texas Army National Guard"), ("Texas Department of Public Safety", "Texas Department of Public Safety"),
               ("NOAA", "National Oceanic and Atmospheric Administration"), ("TCEQ", "Texas Commission on Environmental Quality"), ("Federal Emergency Management Agency", "Federal Emergency Management Agency"),
               ("Port of Corpus Christi", "Port of Corpus Christi")]
ALIAS_OF = {"laguna towing and salvage": "Laguna Towing", "ostrel tankers": "Ostrel Shipping Ltd.", "u.s. customs and border protection, air and marine operations corpus christi": "CBP Air and Marine Operations",
            "air force, air mobility command": "U.S. Air Force Air Mobility Command", "navy": "U.S. Navy", "federal emergency management agency": "Federal Emergency Management Agency"}
added_from = {}


def collect(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in KEYS and isinstance(v, str) and v.strip():
                out.add(v.strip())
            else:
                collect(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect(v, out)


for fn, typ in SRC:
    fp = os.path.join(OUT, fn)
    if not os.path.exists(fp):
        continue
    names = set()
    collect(json.load(open(fp, encoding="utf-8")), names)
    for raw in sorted(names):
        for name in [x.strip() for x in raw.split(" / ")]:
            key = norm(name)
            if not name or key in GENERIC or re.fullmatch(r"ORG-\d{4}", name):
                continue
            target = index.get(key) or next((o for o in orgs if o["name"] == ALIAS_OF.get(key)), None)
            if target is not None:
                if name != target["name"] and name not in target.get("aliases", []) and name != target.get("abbr"):
                    target.setdefault("aliases", []).append(name)
                index[key] = target
                continue
            parent = next((p_ for hint, p_ in PARENT_HINT if name.startswith(hint) and p_ != name), None)
            gov = parent is not None or name.startswith(("Civil Air Patrol", "University", "USGS", "U.S. Maritime"))
            org(name, ("government unit" if gov else typ), parent, US if gov else "", f"Named as operator or owner in {fn}")
            index[key] = orgs[-1]
            added_from[orgs[-1]["org_id"]] = fn
# the maritime registry's name for the Ostrel Bay owner wins over the placeholder
for o in orgs:
    if o["name"] == "Ostrel Shipping Ltd." and o.get("aliases"):
        o["name"], o["aliases"] = o["aliases"][0], [a for a in o["aliases"][1:]]
        oid[o["name"]] = o["org_id"]
        if not o["aliases"]:
            o.pop("aliases")
otruth["_from_other_registries"] = added_from
orgs_doc = {"catalog_meta": {"description": "Organisations that appear in the news, public record and data streams: agencies, the utility, vendors, companies, outlets, community groups.",
                             "note": "Hospitals, terminals, vessels, aircraft and facilities have their own registries; ids here are used wherever a record names an organisation.", "count": len(orgs)},
            "organizations": [dict(o, parent=oid.get(o["parent"]) if o["parent"] else None, parent_name=o["parent"]) for o in orgs]}
dump(orgs_doc, OUT, "organizations.json")
dump({"_about": "Internal. Never delivered. Scenario ids, hidden relationships and release days for organisations.",
      "organizations": otruth,
      "hidden_ownership": {"Brannoch Maritime Holdings": ["Vantorra Restoration LLC", "Quellmar Fuel Partners", "MV Halcyon Drift (operator)"]},
      "id_migration": {"scenario_entities": {"SUP-0388": oid["Vantorra Restoration LLC"], "SUP-0390": oid["Quellmar Fuel Partners"], "SUP-0219": oid["Delta Pumps & Controls"], "SUP-0102": oid["Gulf Relief Logistics"],
                                             "SUP-0455": oid["Brightwake Marine Systems"], "ORG-0901": oid["Brannoch Maritime Holdings"], "ORG-0950": oid["Rendal Terminals"],
                                             "GW-ENT-01": oid["Coastal Bend Power and Water Authority"], "GW-ENT-02": oid["Meridian Controls Corp"], "GW-ENT-03": oid["ClearPath Network Solutions"],
                                             "GW-ENT-005 (old entity_registry)": oid["FastTrack Claims Services LLC"]},
                       "real_names_replaced": {"Corpus Christi Caller-Times / CallerTimes": "The Bayside Ledger", "KIII TV / KRIS": "Harborline 6 News", "real refiners and terminal operators": "Rendal Terminals and fictional berth operators (terminal registry)",
                                               "real hospital systems": "Shoreline Regional Medical Center, Bay City Medical Center and the facility registry", "State Farm (EVT-2204)": "Sabine National Insurance",
                                               "AEP Texas": "Coastal Bend Power and Water Authority", "Dragos, AVEVA, Yokogawa, Schneider Electric, SEL, GE, Fortinet, Cummins": "Meridian Controls Corp, Halden Protection, Bastille Networks"}},
      "story_variants_to_fix": ["'Coastal Bend Public Works Authority' appears in 7 stories; canon is Coastal Bend Power and Water Authority.", "EVT-2204 names a real insurer (State Farm)."]},
     INT, "organizations_truth.json")

# ======================================================================================
# FINANCIAL ENTITIES
# ======================================================================================
STREETS = {"78401": ["Leopard St", "N Shoreline Blvd", "N Staples St"], "78402": ["Timon Blvd", "Surfside Blvd"], "78404": ["Santa Fe St", "S Alameda St", "Ocean Dr"],
           "78405": ["Agnes St", "Morgan Ave", "S Port Ave", "Baldwin Blvd"], "78407": ["Leopard St", "Nueces Bay Blvd", "Buddy Lawrence Dr", "Up River Rd"],
           "78408": ["Leopard St", "N Navigation Blvd", "Up River Rd"], "78410": ["McKinzie Rd", "Violet Rd", "Callicoatte Rd", "Up River Rd"],
           "78411": ["Everhart Rd", "S Alameda St", "Weber Rd", "Gollihar Rd"], "78412": ["Ocean Dr", "Ennis Joslin Rd", "Nile Dr", "McArdle Rd"],
           "78413": ["Saratoga Blvd", "Holly Rd", "S Staples St", "Everhart Rd"], "78414": ["Airline Rd", "Rodd Field Rd", "Yorktown Blvd", "Holly Rd"],
           "78415": ["Ayers St", "Kostoryz Rd", "Gollihar Rd", "Weber Rd"], "78416": ["Old Brownsville Rd", "Greenwood Dr", "Gollihar Rd"],
           "78417": ["Greenwood Dr", "Saratoga Blvd", "Ayers St"], "78418": ["Waldron Rd", "Flour Bluff Dr", "Laguna Shores Rd"],
           "78373": ["S Alister St", "Cotter Ave", "Avenue G"], "78374": ["Wildcat Dr", "Moore Ave"]}
ZIPW = {"78401": 2, "78402": 2, "78404": 5, "78405": 6, "78407": 5, "78408": 5, "78410": 7, "78411": 8, "78412": 8, "78413": 9, "78414": 9, "78415": 9, "78416": 6, "78417": 5, "78418": 8, "78373": 4, "78374": 4}
CITY = {"78373": "Port Aransas", "78374": "Portland"}


def addr(zipc=None):
    z = zipc or R.choices(list(ZIPW), list(ZIPW.values()))[0]
    return f"{R.randint(3, 98) * 100 + R.randint(1, 99)} {R.choice(STREETS[z])}, {CITY.get(z, 'Corpus Christi')} TX {z}", z


def routing(n):
    return f"99{n:07d}"


banks = [("BANK-CC-001", "Coastal Community Bank", "bank", "Corpus Christi, TX"), ("BANK-CC-002", "South Texas Federal Credit Union", "credit union", "Corpus Christi, TX"),
         ("BANK-CC-003", "Bay Area Savings & Loan", "savings and loan", "Corpus Christi, TX"), ("BANK-CC-004", "Nueces Valley Bank", "bank", "Robstown, TX"),
         ("BANK-CC-005", "First Coastal Bend Bank", "bank", "Corpus Christi, TX"), ("BANK-CC-006", "Lone Star Gulf Bank", "bank", "Houston, TX"),
         ("BANK-CC-007", "Padre Federal Credit Union", "credit union", "Corpus Christi, TX"), ("BANK-CC-008", "Harborside National Bank", "bank", "Corpus Christi, TX"),
         ("BANK-CC-009", "Tejas Heritage Bank", "bank", "San Antonio, TX"), ("BANK-CC-010", "Mesquite State Bank", "bank", "Kingsville, TX"),
         ("BANK-CC-011", "Prairie Commerce Bank", "bank", "Tulsa, OK"), ("BANK-CC-012", "Peachtree Mutual Bank", "bank", "Atlanta, GA"),
         ("BANK-US-TREAS", "U.S. Treasury, Bureau of the Fiscal Service", "federal disbursing office", "Kansas City, MO")]
institutions = [{"institution_id": i, "name": n, "type": t, "location": loc, "routing_number": routing(15 + 11 * k)} for k, (i, n, t, loc) in enumerate(banks)]
accounts, ftruth = [], {"accounts": {}, "entities": {}}
acct_n = [40000]


def account(inst, holder_type, opened, kind="business checking"):
    acct_n[0] += R.randint(3, 40)
    a = {"account_id": f"ACCT-{acct_n[0]}", "institution_id": inst, "account_number_masked": f"****{R.randint(1000, 9999)}", "account_type": kind, "holder_type": holder_type, "opened": opened}
    accounts.append(a)
    return a["account_id"]


insurers = [{"insurer_id": "INS-CC-001", "name": "CCC Coastal Insurance Group", "org_id": oid["CCC Coastal Insurance Group"], "lines": ["HO3", "Commercial Property", "Marine", "Business Interruption"], "state_license": "TX-INS-2001-00847"},
            {"insurer_id": "INS-GS-002", "name": "Gulf Shield Mutual Insurance", "org_id": oid["Gulf Shield Mutual Insurance"], "lines": ["HO3", "Flood (private)", "Commercial Property"], "state_license": "TX-INS-2008-00312"},
            {"insurer_id": "INS-NFIP-003", "name": "National Flood Insurance Program", "org_id": oid["National Flood Insurance Program"], "lines": ["Flood"], "state_license": None},
            {"insurer_id": "INS-TW-004", "name": "Texas Windstorm Insurance Association", "org_id": oid["Texas Windstorm Insurance Association"], "lines": ["Wind and hail"], "state_license": None},
            {"insurer_id": "INS-BF-005", "name": "Bayfront Property & Casualty", "org_id": oid["Bayfront Property & Casualty"], "lines": ["HO3", "Commercial Property"], "state_license": "TX-INS-2012-01144"},
            {"insurer_id": "INS-SN-006", "name": "Sabine National Insurance", "org_id": oid["Sabine National Insurance"], "lines": ["HO3", "Commercial Property", "Auto"], "state_license": "TX-INS-1994-00071"},
            {"insurer_id": "INS-PR-007", "name": "Palmetto Reef Insurance Co.", "org_id": oid["Palmetto Reef Insurance Co."], "lines": ["HO3", "Condo"], "state_license": "TX-INS-2016-02290"}]
for ins in insurers:
    ins["claims_payment_account_id"] = account(R.choice(["BANK-CC-001", "BANK-CC-005", "BANK-CC-006", "BANK-CC-008"]) if ins["insurer_id"] != "INS-NFIP-003" else "BANK-US-TREAS", "insurer", rdate("2005-01-01", "2020-12-31"), "claims disbursement")
brokers = [{"broker_id": "BRK-001", "name": "Coastal Meridian Insurance Group", "org_id": oid["Coastal Meridian Insurance Group"], "address": "5350 S Staples St Suite 110, Corpus Christi TX 78411"}]
for k, n in enumerate(["Bluewater Insurance Agency", "Nueces Insurance Associates", "Saratoga Risk Partners", "Islander Insurance Services", "Tejas Family Insurance", "Port City Underwriters"], 2):
    brokers.append({"broker_id": f"BRK-{k:03d}", "name": n, "org_id": None, "address": addr()[0]})
appraisers = [{"appraiser_id": "APR-001", "name": "Duvall & Sons Property Consultants", "org_id": oid["Duvall & Sons Property Consultants"], "address": "3636 S Alameda St Suite 204, Corpus Christi TX 78411"}]
for k, n in enumerate(["Coastal Bend Appraisal Group", "Gulfside Valuation Services", "Mustang Island Appraisers", "South Texas Property Valuation", "Bay Area Real Estate Appraisal"], 2):
    appraisers.append({"appraiser_id": f"APR-{k:03d}", "name": n, "org_id": None, "address": addr()[0]})
firms = [{"firm_id": "ADF-001", "name": "FastTrack Claims Services LLC", "org_id": oid["FastTrack Claims Services LLC"], "address": "8800 McArdle Rd Suite 101, Corpus Christi TX 78412", "registered": "2024-03-15"}]
for k, n in enumerate(["Lone Star Catastrophe Adjusters", "Gulf Coast Claims Group", "Brazos Independent Adjusting", "Seawall Claims Services", "Pinnacle CAT Response"], 2):
    firms.append({"firm_id": f"ADF-{k:03d}", "name": n, "org_id": None, "address": addr()[0], "registered": rdate("2004-01-01", "2023-12-31")})
adjusters, used_adj = [{"adjuster_id": "ADJ-0847", "name": "Victor Salinas-Ruiz", "license_number": "TX-IA-2021-04471", "firm_id": "ADF-001", "type": "independent"},
                       {"adjuster_id": "ADJ-1203", "name": "Maria Chen-Whitfield", "license_number": "TX-IA-2018-02211", "firm_id": "ADF-001", "type": "independent"}], {"Victor Salinas-Ruiz", "Maria Chen-Whitfield"}
for k in range(38):
    while True:
        n = f"{R.choice(FIRST_EN + FIRST_ES[:30])} {R.choice(LAST_EN + LAST_ES)}"
        if n not in used_adj:
            used_adj.add(n); break
    staff = R.random() < 0.4
    adjusters.append({"adjuster_id": f"ADJ-{R.randint(100, 9999):04d}", "name": n, "license_number": f"TX-{'SA' if staff else 'IA'}-{R.randint(2009, 2026)}-{R.randint(1000, 9999):05d}",
                      "firm_id": None if staff else R.choice(firms)["firm_id"], "employer_insurer_id": R.choice(insurers)["insurer_id"] if staff else None, "type": "staff" if staff else "independent"})
assert len({a["adjuster_id"] for a in adjusters}) == len(adjusters)

# vendors / contractors (county and federal payee files)
SHARED_ADDR = "4520 Agnes St Suite 210, Corpus Christi TX 78405"
acct71 = account("BANK-CC-003", "business", day(-41))
acct72 = account("BANK-CC-003", "business", day(-41))
acct73 = account("BANK-CC-011", "business", day(-33))
ftruth["accounts"].update({acct71: "BANK-SYN-71: remit account shared by Vantorra and Quellmar; receives diverted aid D+64 to D+80.", acct72: "BANK-SYN-72: alternate account on both vendor files; receives diverted aid.",
                           acct73: "BANK-SYN-73: third receiving account, out of state; prepaid-card purchases D+66 to D+80 funded from it."})
vendors = []


def uei():
    return "".join(R.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(12))


def vendor(name, kind, address, registered, remit, alt=None, org_id=None, truth=None, license_no=None):
    v = {"vendor_id": f"VND-{len(vendors) + 1:04d}", "uei": uei(), "name": name, "business_type": kind, "registered_address": address, "registration_date": registered,
         "remit_account_id": remit, "alternate_account_id": alt, "org_id": org_id, "state_license": license_no}
    vendors.append(v)
    if truth:
        ftruth["entities"][v["vendor_id"]] = truth
    return v


v_vant = vendor("Vantorra Restoration LLC", "Debris removal and storm restoration", SHARED_ADDR, day(-40), acct71, acct72, oid["Vantorra Restoration LLC"],
                {"scenario_id": "SUP-0388", "uei_scenario": "UEI-SYN-0388", "role": "shell; $14.2M sole-source debris contract; bills 2.3x supported tonnage"})
v_quel = vendor("Quellmar Fuel Partners", "Fuel supply and storage", SHARED_ADDR, day(-40), acct71, acct72, oid["Quellmar Fuel Partners"],
                {"scenario_id": "SUP-0390", "uei_scenario": "UEI-SYN-0390", "role": "shell; $2.1M NAS fuel contract; contaminated fuel"})
v_fast = vendor("FastDry Coastal LLC", "Water damage and mould remediation", "2817 McArdle Rd, Corpus Christi TX 78412", day(-24), account("BANK-CC-003", "business", day(-24)), None, oid["FastDry Coastal LLC"],
                {"thread": "T22", "role": "runner front; 128 of 312 DPS complaints; principals Marcus Whitfield-Yuen and Dora Cantu-Espinoza", "old_id": "CON-SHELL-001 (RV Restoration LLC)"})
v_lone = vendor("Lone Star Premier Construction LLC", "Commercial restoration", addr("78408")[0], "2027-08-22", account("BANK-CC-003", "business", "2027-08-22"), None, None,
                {"thread": "T22", "role": "receives LPH claim repair payments", "old_id": "CON-SHELL-002"})
vendor("Delta Pumps & Controls", "Pump parts and controls", "1210 N Navigation Blvd, Corpus Christi TX 78408", "2006-04-17", account("BANK-CC-001", "business", "2006-04-10"), None, oid["Delta Pumps & Controls"], {"scenario_id": "SUP-0219"})
vendor("Gulf Relief Logistics", "Freight forwarding", "7002 Leopard St, Corpus Christi TX 78409", "2011-09-01", account("BANK-CC-005", "business", "2011-08-20"), None, oid["Gulf Relief Logistics"], {"scenario_id": "SUP-0102"})
vendor("Bayline Petroleum Supply", "Fuel supply and storage", "3100 Up River Rd, Corpus Christi TX 78408", "1998-02-11", account("BANK-CC-008", "business", "1998-02-01"), None, oid["Bayline Petroleum Supply"])
vendor("Brightwake Marine Systems", "Marine automation maintenance", "600 Travis St Suite 1900, Houston TX 77002", "2009-06-30", account("BANK-CC-006", "business", "2009-06-15"), None, oid["Brightwake Marine Systems"], {"scenario_id": "SUP-0455"})
vendor("Coastal Bend Aerial Services", "Aerial survey", "355 Pinson Dr, Corpus Christi TX 78406", "2014-03-03", account("BANK-CC-001", "business", "2014-02-20"), None, oid["Coastal Bend Aerial Services"])
vendor("South Texas Restoration Group", "General contractor, storm damage repair", addr()[0], "2015-07-20", account("BANK-CC-001", "business", "2015-07-01"), old := None)
vendor("Coastal Bend Roofing & Construction Inc.", "Roofing", addr()[0], "2010-04-01", account("BANK-CC-002", "business", "2010-03-15"), None, None, None, "TX-RRC-2010-08811")
vendor("Gulf Coast Electric LLC", "Electrical contractor", addr()[0], "2012-10-05", account("BANK-CC-005", "business", "2012-09-20"))
vendor("Corpus Christi Debris Solutions", "Debris hauling", addr()[0], "2017-05-12", account("BANK-CC-004", "business", "2017-05-01"))
# four unrelated small firms at other suites of the same office building, plus ordinary vendors
for n, k, s in (("Agnes Street Tax Service", "Bookkeeping and tax preparation", 105), ("Rio Bravo Staffing LLC", "Temporary staffing", 140), ("Coastal Title Research", "Title research", 215), ("Tres Palmas Trucking", "Trucking dispatch office", 230)):
    vendor(n, k, f"4520 Agnes St Suite {s}, Corpus Christi TX 78405", rdate("2013-01-01", "2026-12-31"), account(R.choice(["BANK-CC-001", "BANK-CC-002", "BANK-CC-004", "BANK-CC-005"]), "business", rdate("2013-01-01", "2026-12-31")))
KINDS = [("Roofing", "{} Roofing"), ("General contractor", "{} Construction"), ("Tree service and debris", "{} Tree & Debris"), ("Plumbing", "{} Plumbing"), ("Electrical contractor", "{} Electric"),
         ("Water damage and mould remediation", "{} Restoration"), ("Fencing", "{} Fence Co."), ("HVAC", "{} Air & Heat"), ("Equipment rental", "{} Equipment Rental"), ("Hauling", "{} Hauling"),
         ("Portable sanitation", "{} Site Services"), ("Bottled water supply", "{} Water Supply"), ("Generator service", "{} Power Systems"), ("Marine salvage", "{} Marine Salvage"), ("Catering", "{} Catering")]
STEMS = ["Nueces", "Padre", "Mustang", "Bayfront", "Calallen", "Tuloso", "Gulfstream", "Coastal Plains", "Oso Bay", "Laguna", "Three Rivers", "King Ranch Road", "Seabreeze", "Harbor Bridge", "Annaville", "Flour Bluff",
         "Shoreline", "Portland", "Ingleside", "Aransas", "Rockport", "Tejano", "La Quinta", "Bluebonnet", "Mesquite", "Sandollar", "Pelican", "Redfish", "Islander", "Ocean Drive", "Saratoga", "Six Points", "Westside", "Cuddihy"]
names_seen = {v["name"] for v in vendors}
while len(vendors) < 96:
    k, pat = R.choice(KINDS)
    n = pat.format(R.choice(STEMS)) + R.choice(["", " LLC", " Inc.", ""])
    if n in names_seen:
        continue
    names_seen.add(n)
    reg = rdate("2001-01-01", "2026-12-31") if R.random() < 0.86 else rdate("2027-06-01", "2027-10-05")     # some honest firms also register around the storm
    vendor(n, k, addr()[0], reg, account(R.choice([b[0] for b in banks[:10]]), "business", reg), None, None, None, f"TX-LIC-{R.randint(100000, 999999)}" if R.random() < 0.6 else None)

contracts = [
    {"contract_id": "NC-EM-2027-0071", "awarding_body": "Nueces County Commissioners Court", "vendor_id": v_vant["vendor_id"], "description": "Emergency debris removal, Hurricane Rafael", "award_date": day(10), "value_usd": 14200000, "procurement": "sole source, emergency"},
    {"contract_id": "N6883627C0075", "awarding_body": "Naval Air Station Corpus Christi", "vendor_id": v_quel["vendor_id"], "description": "Emergency generator fuel supply", "award_date": day(12), "value_usd": 2100000, "procurement": "emergency, after the regular supplier's terminal flooded"},
]
ftruth["contracts"] = {"NC-EM-2027-0071": "PIID-SYN-0071 (EVT-0311)", "N6883627C0075": "PIID-SYN-0075 (EVT-0312); public from D+20"}
ordinary = [v for v in vendors if v["vendor_id"] not in (v_vant["vendor_id"], v_quel["vendor_id"], v_fast["vendor_id"], v_lone["vendor_id"])]
BODIES = [("Nueces County Commissioners Court", "NC-EM"), ("City of Corpus Christi", "CC-PW"), ("Coastal Bend Power and Water Authority", "CBPWA-PO"), ("Port of Corpus Christi", "POCC"),
          ("Texas Division of Emergency Management", "TDEM-ER"), ("Federal Emergency Management Agency", "70FB"), ("San Patricio County", "SPC-EM"), ("City of Port Aransas", "PA-ER")]
for k in range(30):
    v = R.choice(ordinary)
    dd = R.randint(-20, 70)
    body, prefix = R.choice(BODIES)
    what = v["business_type"].lower()
    contracts.append({"contract_id": f"{prefix}-2027-{R.randint(100, 9999):04d}", "awarding_body": body, "vendor_id": v["vendor_id"],
                      "description": (f"Storm-season standby agreement: {what}" if dd < -9 else f"Hurricane Rafael response: {what}"), "award_date": day(dd), "value_usd": int(R.lognormvariate(12.0, 1.1) // 100 * 100),
                      "procurement": R.choice(["competitive", "competitive", "pre-positioned contract", "emergency, three quotes", "sole source, emergency"]) if dd >= -2 else R.choice(["competitive", "pre-positioned contract"])})
assert len({c["contract_id"] for c in contracts}) == len(contracts)

# property holders, policies
holders, policies = [], []
lph_id = "PH-100001"
holders.append({"holder_id": lph_id, "name": "Landmark Pacific Holdings LLC", "holder_type": "company", "mailing_address": "4411 Leopard St, Corpus Christi TX 78408", "org_id": oid["Landmark Pacific Holdings LLC"]})
ftruth["entities"][lph_id] = {"thread": "T22", "role": "230 inflated policies, 187 claims; office IP 198.51.100.44; director Renaldo Carver-Mossbach", "old_ids": "PER-LPH-* claimant ids in the first claims file"}
LANDLORDS = ["Bay Vista Properties LLC", "Coastal Bend Rentals Inc.", "Tejas Apartment Group", "Ocean Drive Holdings LP", "Southside Duplex Partners", "Islander Housing LLC", "Westside Home Rentals", "Padre Property Management"]
for k, n in enumerate(LANDLORDS, 2):
    holders.append({"holder_id": f"PH-{100000 + k}", "name": n, "holder_type": "company", "mailing_address": addr()[0], "org_id": None})
used_h = set()
for k in range(1150):
    es = R.random() < 0.55
    while True:
        n = f"{R.choice(FIRST_ES if es else FIRST_EN)} {R.choice(LAST_ES if es else LAST_EN)}"
        key = n
        if key not in used_h or R.random() < 0.3:
            used_h.add(key); break
    a, z = addr()
    holders.append({"holder_id": f"PH-{100100 + k}", "name": n, "holder_type": "individual", "mailing_address": a, "org_id": None})
pol_n = [100000]


def policy(holder, insurer, broker, ptype, address, bound, appraiser, rcv, assessed):
    pol_n[0] += R.randint(3, 19)
    p = {"policy_number": f"POL-{ptype}-{bound[:4]}-{pol_n[0]}", "holder_id": holder, "insurer_id": insurer, "broker_id": broker, "policy_type": ptype, "property_address": address,
         "bound_date": bound, "appraiser_id": appraiser, "replacement_cost_value_usd": rcv, "county_assessed_value_usd": assessed}
    policies.append(p)
    return p


# Landmark Pacific: 230 policies bound Aug 5 to Sept 7, appraised at about 3.4 times assessed value
lph_pols = []
for k in range(230):
    z = R.choices(["78405", "78407", "78408", "78416", "78415", "78401", "78404"], [5, 6, 5, 4, 3, 2, 2])[0]
    assessed = int(R.gauss(239000, 52000) // 1000 * 1000)
    assessed = max(110000, assessed)
    rcv = int(assessed * R.gauss(3.4, 0.28) // 1000 * 1000)
    p = policy(lph_id, R.choices(["INS-CC-001", "INS-GS-002", "INS-SN-006", "INS-BF-005"], [5, 3, 3, 1])[0], "BRK-001", R.choices(["HO3", "CP", "BI"], [5, 4, 1])[0], addr(z)[0],
               rdate("2027-08-05", "2027-09-07"), "APR-001", rcv, assessed)
    lph_pols.append(p["policy_number"])
lp = [q for q in policies if q["holder_id"] == lph_id]
fa = 239000 / (sum(q["county_assessed_value_usd"] for q in lp) / len(lp))
for q in lp:
    q["county_assessed_value_usd"] = int(q["county_assessed_value_usd"] * fa // 1000 * 1000)
fr = 813000 / (sum(q["replacement_cost_value_usd"] for q in lp) / len(lp))
for q in lp:
    q["replacement_cost_value_usd"] = int(q["replacement_cost_value_usd"] * fr // 1000 * 1000)
ftruth["lph_policies"] = {"count": 230, "policy_numbers": lph_pols, "note": "Average replacement value about $813,000 against about $239,000 assessed (3.4x). 187 of these file claims; 47 commercial claims share one damage narrative and 12 photos."}
indiv = [h for h in holders if h["holder_type"] == "individual"]
for h in indiv:
    a = h["mailing_address"]
    assessed = max(60000, int(R.lognormvariate(12.25, 0.42) // 1000 * 1000))
    ins = R.choices([i["insurer_id"] for i in insurers if i["insurer_id"] not in ("INS-NFIP-003", "INS-TW-004")], [5, 4, 3, 4, 2])[0]
    appr = R.choice(appraisers)["appraiser_id"] if R.random() < 0.12 else None
    policy(h["holder_id"], ins, R.choice(brokers)["broker_id"] if R.random() < 0.7 else None, "HO3", a, rdate("2019-01-01", "2027-09-08") if R.random() < 0.9 else rdate("2027-08-01", "2027-09-08"),
           appr, int(assessed * R.gauss(1.12, 0.14) // 1000 * 1000), assessed)
    if R.random() < 0.22:
        policy(h["holder_id"], "INS-NFIP-003", None, "FLD", a, rdate("2019-01-01", "2027-08-10"), None, min(250000, int(assessed * 0.9 // 1000 * 1000)), assessed)
    if R.random() < 0.18:
        policy(h["holder_id"], "INS-TW-004", None, "WND", a, rdate("2019-01-01", "2027-08-10"), None, int(assessed * 1.05 // 1000 * 1000), assessed)
for h in holders[1:9]:
    for _ in range(R.randint(4, 14)):
        assessed = max(90000, int(R.lognormvariate(12.5, 0.5) // 1000 * 1000))
        policy(h["holder_id"], R.choice(["INS-CC-001", "INS-GS-002", "INS-SN-006", "INS-BF-005", "INS-PR-007"]), R.choice(brokers)["broker_id"], R.choice(["CP", "HO3", "BI"]), addr()[0],
               rdate("2020-01-01", "2027-08-30"), R.choice(appraisers[1:])["appraiser_id"] if R.random() < 0.5 else None, int(assessed * R.gauss(1.2, 0.2) // 1000 * 1000), assessed)
R.shuffle(policies)

# aid applications: id scheme plus the internal lists the payments generator needs
def reg_id():
    return f"IA-4821-{R.randint(1000000, 9999999)}"


seen_reg = set()


def reg_ids(n):
    out = []
    while len(out) < n:
        r = reg_id()
        if r not in seen_reg:
            seen_reg.add(r); out.append(r)
    return out


SYN_NAMES = ["Calvin Dreyer", "Marisela Quintanar", "Tobias Renfro", "Ysela Montalvo", "Gareth Pruett", "Lorena Baptiste"]
ftruth["aid_diversion"] = {
    "hijacked_registrations": {"count": 410, "ids": reg_ids(410), "window": "deposit details changed D+64 to D+80 after credential stuffing D+62 to D+70 (about 220,000 attempts)"},
    "synthetic_identities": [{"scenario_id": f"SYN-PER-70000{k + 1}", "registration_id": r, "name": SYN_NAMES[k]} for k, r in enumerate(reg_ids(6))],
    "receiving_accounts": {"BANK-SYN-71": acct71, "BANK-SYN-72": acct72, "BANK-SYN-73": acct73}, "diverted_usd": 3900000,
    "prepaid_card_merchants": "see entity_registry.json prepaid_card_merchants (all more than 300 km from Corpus Christi)"}
ftruth["lph_runner_applications"] = {"count": 94, "ids": reg_ids(94), "zip": "78407", "source_ip": "198.51.100.44", "bursts_utc": [["2027-11-13T06:01Z-09:17Z", 31], ["2027-11-14T01:00Z-04:45Z", 29], ["2027-11-15T23:00Z-23:59Z", 34]],
                                     "flag": "FEMA suspicious-activity flag SA-2027-TX-4471; 23 unique photos reused"}
ftruth["people"] = {"Renaldo Carver-Mossbach": "director, Landmark Pacific Holdings", "Roland Muñoz-Estrada": "appraiser, Duvall & Sons", "Marcus Whitfield-Yuen": "principal, FastDry Coastal", "Dora Cantu-Espinoza": "principal, FastDry Coastal",
                    "L. Marrick": "nominee director, Brannoch Maritime Holdings (CHR-091)", "Victor Salinas-Ruiz (ADJ-0847)": "adjuster who approved a concentration of LPH claims in the first claims file; keep as an ordinary-looking adjuster with a visible concentration",
                    "claim runners": 23}
merchants = []
for k, (n, city) in enumerate([("QuikCard Kiosk 114", "Dallas, TX"), ("Metro Mart 22", "Fort Worth, TX"), ("ValuPay Express", "Oklahoma City, OK"), ("CardStop 9", "Dallas, TX"), ("Sunrise Check Cashing", "El Paso, TX"),
                               ("Crescent Gift & Card", "New Orleans, LA"), ("Red River Pay Center", "Shreveport, LA"), ("QuikCard Kiosk 207", "Arlington, TX"), ("Peachtree Prepaid", "Atlanta, GA"),
                               ("North Loop Money Services", "Houston, TX"), ("Bayou City Card Outlet", "Houston, TX"), ("Alamo Express Pay", "San Antonio, TX"), ("Gulfway Market", "Corpus Christi, TX"), ("Staples Street Check Cashing", "Corpus Christi, TX")], 1):
    merchants.append({"merchant_id": f"MER-{k:03d}", "name": n, "city": city, "category": "prepaid cards and money services"})
ftruth["prepaid_card_merchants_used"] = [m["merchant_id"] for m in merchants if not m["city"].startswith(("Corpus", "San Antonio"))][:11]
crypto = [{"endpoint_id": "CRYPTO-01", "chain": "Bitcoin", "wallet_address": "bc1q" + "".join(R.choice("023456789acdefghjklmnpqrstuvwxyz") for _ in range(38))},
          {"endpoint_id": "CRYPTO-02", "chain": "Bitcoin", "wallet_address": "bc1q" + "".join(R.choice("023456789acdefghjklmnpqrstuvwxyz") for _ in range(38))},
          {"endpoint_id": "CRYPTO-03", "chain": "Ethereum", "wallet_address": "0x" + "".join(R.choice("0123456789abcdef") for _ in range(40))},
          {"endpoint_id": "CRYPTO-04", "chain": "Tether (Tron)", "wallet_address": "T" + "".join(R.choice("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz") for _ in range(33))}]
ftruth["crypto"] = {"CRYPTO-01": "cash-out of T22 claim proceeds (was D+10 in the first payments file)", "CRYPTO-02": "second T22 cash-out", "CRYPTO-03 and CRYPTO-04": "ordinary endpoints for cover traffic"}
ftruth["id_migration"] = {"old_entity_registry": {"CON-SHELL-001 RV Restoration LLC": v_fast["vendor_id"] + " FastDry Coastal LLC", "CON-SHELL-002 Lone Star Premier Construction LLC": v_lone["vendor_id"],
                                                  "CON-LEGIT-001": "South Texas Restoration Group", "CON-LEGIT-002": "Coastal Bend Roofing & Construction Inc.", "GW-ENT-005 FastTrack Claims Services LLC": "ADF-001",
                                                  "BANK-CC-001..003": "same ids", "routing numbers 111000025, 113000023, 119000016, 021030004": "replaced by 99xxxxxxx (cannot collide with real routing numbers)"},
                          "scenario_entities": {"SUP-0388": v_vant["vendor_id"], "SUP-0390": v_quel["vendor_id"], "BANK-SYN-71": acct71, "BANK-SYN-72": acct72, "BANK-SYN-73": acct73,
                                                "PIID-SYN-0071": "NC-EM-2027-0071", "PIID-SYN-0075": "N6883627C0075", "SYN-PER-700001..6": "aid_diversion.synthetic_identities"},
                          "first_payments_files": {"claimant_id PER-LPH-*": lph_id + " (one company holder, 230 policies)", "claim ids CLM-2027-CC-00xxxx": "regenerate; loss dates must spread from D0 onward",
                                                   "flag and fraud_flags columns": "remove (answer leak)", "sender 'FEMA / HHS — Disaster Recovery Division'": "Federal Emergency Management Agency via BANK-US-TREAS",
                                                   "senders Felipe Garza, Mara Estormes (crypto)": "not used; those are ordinary social accounts"}}
fin = {"catalog_meta": {"description": "Insurers, brokers, appraisers, adjusters, vendors and contractors, banks and accounts, policyholders and policies, contracts and payment endpoints, for joining with claims, payments, contract and aid records.",
                        "id_schemes": {"aid_registration": "IA-4821-nnnnnnn (FEMA registration under DR-4821-TX)", "claim": "CLM-2027-<insurer code>-nnnnnn", "policy": "POL-<type>-<year>-nnnnnn (HO3 homeowners, CP commercial property, BI business interruption, FLD flood, WND wind and hail)",
                                       "account": "ACCT-nnnnn", "vendor": "VND-nnnn with a 12-character UEI"},
                        "addresses": "Property and mailing addresses are street-level text; coordinates come with the claims and damage records.",
                        "counts": {"insurers": len(insurers), "brokers": len(brokers), "appraisers": len(appraisers), "adjusting_firms": len(firms), "adjusters": len(adjusters), "vendors": len(vendors),
                                   "contracts": len(contracts), "financial_institutions": len(institutions), "accounts": len(accounts), "policyholders": len(holders), "policies": len(policies),
                                   "prepaid_card_merchants": len(merchants), "crypto_endpoints": len(crypto)}},
       "insurers": insurers, "brokers": brokers, "appraisers": appraisers, "adjusting_firms": firms, "adjusters": sorted(adjusters, key=lambda a: a["adjuster_id"]),
       "vendors": sorted(vendors, key=lambda v: v["name"]), "contracts": sorted(contracts, key=lambda c: c["award_date"]), "financial_institutions": institutions,
       "accounts": sorted(accounts, key=lambda a: a["account_id"]), "policyholders": holders, "policies": policies, "prepaid_card_merchants": merchants, "crypto_endpoints": crypto}
dump(fin, OUT, "entity_registry.json")
ftruth["_about"] = "Internal. Never delivered. Roles in the fraud, aid-diversion and contract threads, id lists the payments and claims generators need, and migration from older ids."
dump(ftruth, INT, "entity_registry_truth.json")

# ======================================================================================
# people named in stories who are not characters
# ======================================================================================
audit = json.load(open(os.path.join(ROOT, "07_validation", "reports", "entity_graph_audit.json"), encoding="utf-8"))
stories = {}
for f in sorted(glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
    for s in json.load(open(f, encoding="utf-8"))["stories"]:
        stories[s["story_id"]] = s
facts = {f["id"]: f for f in json.load(open(os.path.join(ROOT, "02_public_record", "public_record.json"), encoding="utf-8"))["facts"]}
char_names = {c["name"] for c in chars}
people, stale = [], []
SKIP = ("Nueces County Sheriff", "Operations Julio Sandoval-Reeves")
for x in audit["unregistered_named_entities"]:
    if not x["kind"].startswith("person") or x["name"] in SKIP or x["name"] in char_names:
        continue
    name = x["name"]
    ids, ctx = [], None
    for sid, s in stories.items():
        body = " ".join([s["headline"], s["dek"]] + s["body"])
        if name in body:
            ids.append(sid)
            if ctx is None:
                i = body.index(name)
                ctx = body[max(0, i - 110):i + len(name) + 90].strip()
    fids = [fid for fid, f in facts.items() if name in f["statement"]]
    if ctx is None and fids:
        st = facts[fids[0]]["statement"]; i = st.index(name)
        ctx = st[max(0, i - 110):i + len(name) + 90].strip()
    title = org_guess = None
    if ctx:
        before = ctx[:ctx.index(name)] if name in ctx else ""
        m = re.search(r"((?:[A-Z][\w&'.-]+ ){0,6}(?:[Dd]irector|[Ss]pokes\w+|[Cc]hief|[Cc]oordinator|[Oo]fficer|[Mm]anager|[Cc]ommander|[Jj]udge|[Ss]heriff|[Ee]pidemiologist|[Aa]nalyst|[Ss]upervisor|[Cc]aptain|[Cc]ommissioner|Dr\.|Lt\. Col\.|Special Agent|[Pp]resident|[Aa]dministrator|[Ss]uperintendent|[Pp]rincipal|[Cc]ounsel|[Pp]astor|[Nn]urse)\w*)\s*$", before)
        if m:
            title = m.group(1).strip()
        after = ctx[ctx.index(name) + len(name):] if name in ctx else ""
        m2 = re.match(r",? (?:of|at|with|for) (?:the )?((?:[A-Z][\w&'.-]+ ?){1,7})", after)
        if m2:
            org_guess = m2.group(1).strip()
        elif title:
            for z in sorted(orgs, key=lambda z: len(z["name"]), reverse=True):
                if z["name"] in before or any(a in before for a in z.get("aliases", []) if len(a) > 4) or (z.get("abbr") or "~~") in before:
                    org_guess = z["name"]; break
    if not ids and not fids:
        stale.append(name)                      # the audit predates the canon pass; the name is no longer in the corpus
        continue
    people.append({"name": name, "mentions": len(ids) + len(fids), "story_ids": ids, "public_fact_ids": fids, "title_guess": title, "organisation_guess": org_guess, "context": ctx})
msel_only = [{"name": n, "role": r, "source": s} for n, r, s in [
    ("Dr. Fatima Al-Rasheed-Obinna", "Chief Information Security Officer, CBPWA", "GW-EVT-106, GW-PUB-101"), ("Marcus Teitelbaum-Park", "Senior support engineer, Vantage Security Systems", "GW-EVT-107"),
    ("Priya Subramaniam-Nair", "Analyst, Texas Division of Emergency Management", "EVT-1507"), ("Dr. Brennan Calloway-Watts", "Public health officer, Nueces County", "EVT-1606"),
    ("Darnell Okafor-Reyes", "Special Agent, FBI Corpus Christi Resident Agency", "EVT-2204"), ("Renaldo Carver-Mossbach", "Director, Landmark Pacific Holdings (hidden until D+90)", "EVT-2202, EVT-2207"),
    ("Roland Muñoz-Estrada", "Appraiser, Duvall & Sons (hidden until D+90)", "EVT-2201, EVT-2207"), ("Marcus Whitfield-Yuen", "Principal, FastDry Coastal (hidden until D+90)", "EVT-2207"),
    ("Dora Cantu-Espinoza", "Principal, FastDry Coastal (hidden until D+90)", "EVT-2207"), ("Ana Lucía Montoya-Reyes", "Nurse, Shoreline Regional Medical Center", "EVT-1609"),
    ("Ricardo Vela", "Field engineer, CBPWA; owner of the stolen credential (first name generated in gw_host_registry.json)", "GW-EVT-002, GW-EVT-010")]]
dump({"_about": "For the narrative pass: people named in stories or the public record who are not in 01_characters/characters.json. Title and organisation are guesses from the first mention; check the context.",
      "note": "The user-supplied audit also lists 'Marcus Webb' here; that name is also the display name of the resident account @localDadCC in the first social stream.",
      "from_stories_and_public_record": sorted(people, key=lambda p: -p["mentions"]), "from_msel_only": msel_only,
      "in_audit_but_no_longer_in_corpus": stale, "already_characters_now": sorted(x["name"] for x in audit["unregistered_named_entities"] if x["kind"].startswith("person") and x["name"] in char_names)},
     INT, "people_to_add.json")

print(f"personas {len(personas)} (+{len(compact)} compact; operator accounts {len(net)}), organisations {len(orgs)}, vendors {len(vendors)}, accounts {len(accounts)}, "
      f"policyholders {len(holders)}, policies {len(policies)}, adjusters {len(adjusters)}, contracts {len(contracts)}, people_to_add {len(people)}+{len(msel_only)}")
