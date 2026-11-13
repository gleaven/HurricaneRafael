"""Financial streams: contracts, financial_transactions, aid_applications, insurance_claims.

    python3 scripts/streams/gen_finance.py

Writes under 05_other_sources/payments/
  contracts_vendor_registry.csv    vendor registrations (who, where, since when, which bank account)
  contracts_business_filings.csv   state business filings for the same vendors, plus later court filings
  contracts_awards.csv             award records
  contracts_invoices.csv           invoices and their payment status
  contracts_actions.csv            dated contract actions (modifications, deficiency reports, suspensions, holds)
  contracts_debris_monitoring.csv  the county's survey-based debris estimates by zone and week
  insurance_claims.csv             policy transactions before and after the storm, storm claims, spill claims
  aid_applications.csv             aid registrations, determinations, payments and account changes
  financial_transactions.csv       ledger of the accounts in the entity registry

Everything is derived from 00_scenario/canon_timeline.json and the registries; see scripts/streams/README.md.
No column says which records are improper: they have to be found by joining and counting.
"""
import datetime as dt
import hashlib
import math
import re
from collections import defaultdict

import numpy as np

import fuel_ledger
import netmap

from common import (D0_EPOCH, SPAN_END, canon, day_of, geo_handle, internal, iso, local_dt, local_ts, reg, retire,
                    rng, utc_offset, write_csv)

P = "05_other_sources/payments/"
SPAN0 = D0_EPOCH - 30 * 86400
DAY = 86400

FIRST = ["Maria", "Jose", "Juan", "Rosa", "Luis", "Ana", "Carlos", "Guadalupe", "Miguel", "Elena", "Jesus", "Patricia",
         "Roberto", "Sylvia", "Ricardo", "Norma", "Hector", "Irma", "Raul", "Leticia", "Arturo", "Yolanda", "Ruben", "Diana",
         "James", "Linda", "Robert", "Barbara", "Michael", "Susan", "William", "Karen", "David", "Nancy", "Charles", "Betty",
         "Thomas", "Sandra", "Daniel", "Donna", "Paul", "Carol", "Mark", "Sharon", "Steven", "Brenda", "Kevin", "Debra",
         "Brian", "Amy", "Gary", "Angela", "Larry", "Melissa", "Frank", "Tina", "Scott", "Monica", "Eric", "Veronica",
         "Andre", "Tamika", "Darnell", "Latoya", "Tyrone", "Keisha", "Hung", "Lan", "Minh", "Thu", "Tuan", "Mai",
         "Felipe", "Adriana", "Sergio", "Claudia", "Oscar", "Gloria", "Manuel", "Alma", "Javier", "Beatriz", "Pedro", "Lorena",
         "Travis", "Kayla", "Cody", "Brooke", "Dustin", "Shelby", "Wade", "Jenna", "Clay", "Becky", "Earl", "Peggy"]
LAST = ["Garcia", "Martinez", "Rodriguez", "Hernandez", "Lopez", "Gonzalez", "Perez", "Sanchez", "Ramirez", "Torres", "Flores",
        "Rivera", "Gomez", "Diaz", "Reyes", "Morales", "Cruz", "Ortiz", "Gutierrez", "Chavez", "Ramos", "Ruiz", "Mendoza",
        "Castillo", "Vasquez", "Salinas", "Cantu", "Trevino", "Villarreal", "Garza", "Guerra", "Longoria", "Saenz", "Pena",
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Moore",
        "Martin", "Jackson", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
        "Wright", "Scott", "Hill", "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Roberts", "Turner", "Phillips",
        "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Morris", "Cook", "Rogers", "Nguyen", "Tran", "Le",
        "Pham", "Schroeder", "Kowalski", "Dvorak", "Novak", "Zamora", "Cavazos", "Olivarez", "Barrera", "Medina", "Jimenez"]


def retire_once(rels, tag="streams_pre_regen_20261109"):
    """Move the superseded first-generation files aside, once (a re-run must not retire its own output)."""
    import os
    from common import ROOT
    todo = [r for r in rels if os.path.exists(os.path.join(ROOT, r)) and not os.path.exists(os.path.join(ROOT, "_versions", tag, r))]
    return retire(todo, tag) if todo else 0


def d2s(day):
    return (dt.date(2027, 9, 14) + dt.timedelta(days=int(day))).isoformat()


def date_of(t):
    return local_dt(t).date().isoformat()


def h(*k):
    return hashlib.sha256("|".join(str(x) for x in k).encode()).hexdigest()


def money(x):
    return f"{x:.2f}"


def business_days(day):
    return (dt.date(2027, 9, 14) + dt.timedelta(days=int(day))).weekday() < 5


# banks and most offices are shut around landfall
def closed(day):
    return 0 <= day <= 3


class World:
    def __init__(self):
        self.G = geo_handle()
        self.er = reg("entity_registry")
        self.tr = internal("entity_registry")
        self.areas = reg("areas")["areas"]
        self.orgs = {o["name"]: o["org_id"] for o in reg("organizations")["organizations"]}
        self.vend = {v["vendor_id"]: v for v in self.er["vendors"]}
        self.acct = {a["account_id"]: a for a in self.er["accounts"]}
        self.inst = {i["institution_id"]: i for i in self.er["financial_institutions"]}
        self.pol = {p["policy_number"]: p for p in self.er["policies"]}
        self.holder = {x["holder_id"]: x for x in self.er["policyholders"]}
        self.insurer = {i["insurer_id"]: i for i in self.er["insurers"]}
        self.adj = self.er["adjusters"]
        self.contracts = {c["contract_id"]: c for c in self.er["contracts"]}
        self.tracts = sorted((a for a in self.areas if a["area_type"] == "census_tract"), key=lambda a: a["tract"])
        self.area = {a["area_id"]: a for a in self.areas}
        self.lph = set(self.tr["lph_policies"]["policy_numbers"])
        self.low_income = {"AREA-TRACT-480101", "AREA-TRACT-480201", "AREA-TRACT-480301", "AREA-TRACT-480401",
                           "AREA-TRACT-480501", "AREA-TRACT-480901", "AREA-TRACT-481201", "AREA-TRACT-481301"}
        # road names by rough location, for address text
        feats = self.G.roads.features
        self.road_mid = []
        for name, cls, pts in feats:
            if name and cls in ("local", "arterial", "secondary") and not re.match(r"(State Hwy|US Hwy|I-|Farm|FM|Hwy|Co Rd)", name):
                m = pts[len(pts) // 2]
                self.road_mid.append((m[0], m[1], name))
        self.road_by_name = defaultdict(list)
        for i, (name, cls, pts) in enumerate(feats):
            if name:
                self.road_by_name[name.lower()].append(i)
        self._tract_roads = {}
        self._geo_cache = {}

    def org(self, name):
        return self.orgs.get(name, "")

    def tract_roads(self, a):
        k = a["area_id"]
        if k not in self._tract_roads:
            rp = a.get("reference_point") or {"latitude": 27.79, "longitude": -97.40}
            lat, lon = rp["latitude"], rp["longitude"]
            d = sorted(((abs(m[0] - lat) + abs(m[1] - lon) * 0.9, m[2]) for m in self.road_mid))
            names = []
            for dist, n in d:
                if n not in names:
                    names.append(n)
                if len(names) >= 14 or (dist > 0.03 and len(names) >= 5):
                    break
            self._tract_roads[k] = names
        return self._tract_roads[k]

    def geocode(self, address):
        """Point on land beside the street named in a registry address (deterministic)."""
        if address in self._geo_cache:
            return self._geo_cache[address]
        G = self.G
        street = re.sub(r"\s+(Suite|Unit|Apt|#).*$", "", address.split(",")[0])
        m = re.match(r"(\d+)\s+(.*)", street)
        num, name = (int(m.group(1)), m.group(2)) if m else (0, street)
        city = address.split(",")[1].strip() if "," in address else ""
        box = None
        for a in self.areas:
            if a["area_type"] == "city" and city.startswith(a["name"]):
                box = a["bbox"]
        r = rng("geocode", address)
        out = None
        ids = self.road_by_name.get(name.lower(), [])
        cands = []
        for i in ids:
            pts = G.roads.features[i][2]
            mid = pts[len(pts) // 2]
            if box is None or (box[0] - 0.02 <= mid[1] <= box[2] + 0.02 and box[1] - 0.02 <= mid[0] <= box[3] + 0.02):
                cands.append(pts)
        for attempt in range(12):
            if not cands:
                break
            pts = cands[int(r.integers(len(cands)))]
            j = int(r.integers(len(pts) - 1))
            a, b = pts[j], pts[j + 1]
            t = float(r.random())
            lat, lon = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            dx, dy = (b[1] - a[1]) * 98500, (b[0] - a[0]) * 110950
            n = math.hypot(dx, dy) or 1.0
            side = 1 if (num + attempt) % 2 else -1
            sb = 16 + 8 * float(r.random())
            lat += dx / n * sb * side / 110950
            lon += -dy / n * sb * side / 98500
            if G.is_land(lat, lon):
                out = (round(lat, 5), round(lon, 5))
                break
        if out is None:
            for attempt in range(30):
                p = G.roads.random_point(r, box=box, classes=("local", "arterial"), setback_m=18)
                if p and G.is_land(p[0], p[1]):
                    out = (round(p[0], 5), round(p[1], 5))
                    break
        self._geo_cache[address] = out
        return out


# ======================================================================================
# contracts
# ======================================================================================
AWARD_ORG = {"Nueces County Commissioners Court": "Nueces County Commissioners Court", "City of Corpus Christi": "City of Corpus Christi",
             "Naval Air Station Corpus Christi": "Naval Air Station Corpus Christi", "Port of Corpus Christi": "Port of Corpus Christi",
             "City of Port Aransas": "City of Port Aransas", "San Patricio County": "San Patricio County",
             "Coastal Bend Power and Water Authority": "Coastal Bend Power and Water Authority",
             "Federal Emergency Management Agency": "Federal Emergency Management Agency",
             "Texas Division of Emergency Management": "Texas Division of Emergency Management"}
VANTORRA, QUELLMAR = "VND-0001", "VND-0002"
PIID_DEBRIS, PIID_FUEL = "NC-EM-2027-0071", "N6883627C0075"
A71, A72, A73 = "ACCT-40134", "ACCT-40172", "ACCT-40203"

# debris zones: (zone id, area id, contractor, piid, survey-supported tons per week at peak)
ZONES = [
    ("DZ-01", "AREA-NBH-FLOURBLUFF", VANTORRA, PIID_DEBRIS, 1050),
    ("DZ-02", "AREA-NBH-SOUTHSIDE", VANTORRA, PIID_DEBRIS, 1300),
    ("DZ-03", "AREA-NBH-CALALLEN", VANTORRA, PIID_DEBRIS, 620),
    ("DZ-04", "AREA-NBH-ANNAVILLE", VANTORRA, PIID_DEBRIS, 540),
    ("DZ-05", "AREA-NBH-WESTSIDE", VANTORRA, PIID_DEBRIS, 760),
    ("DZ-06", "AREA-CITY-PORTARANSAS", "VND-0013", "PA-ER-2027-2934", 900),
    ("DZ-07", "AREA-NBH-MUSTANGISLAND", "VND-0082", "PA-ER-2027-1763", 820),
    ("DZ-08", "AREA-NBH-NORTHBEACH", "VND-0093", "70FB-2027-1088", 430),
    ("DZ-09", "AREA-CITY-PORTLAND", "VND-0027", "SPC-EM-2027-5848", 260),
    ("DZ-10", "AREA-NBH-INNERHARBOR", "VND-0044", "POCC-2027-6411", 310),
]
BILL_RATIO = 2.3


def build_contracts(W):
    er = W.er
    # ---- vendor registry
    rows = []
    # sister companies (same first word in the name, e.g. two "Laguna ..." firms) list each other's account as an alternate
    fam = defaultdict(list)
    for v in sorted(er["vendors"], key=lambda v: v["vendor_id"]):
        if not v["alternate_account_id"] and v["vendor_id"] not in ("VND-0003", "VND-0004"):
            fam[v["name"].split()[0]].append(v)
    alt = {}
    for word, vs in sorted(fam.items()):
        if len(vs) >= 2 and int(h("fam", word)[:4], 16) % 3 == 0:
            a, b = vs[0], vs[1]
            alt[a["vendor_id"]], alt[b["vendor_id"]] = b["remit_account_id"], a["remit_account_id"]
    W.alt_account = alt
    for v in sorted(er["vendors"], key=lambda v: v["registration_date"]):
        rows.append([v["vendor_id"], v["uei"], v["name"], v["business_type"], v["registered_address"], v["registration_date"],
                     v["remit_account_id"], W.acct[v["remit_account_id"]]["institution_id"], W.acct[v["remit_account_id"]]["account_number_masked"],
                     v["alternate_account_id"] or alt.get(v["vendor_id"], ""), v["state_license"] or ""])
    n_reg = write_csv(P + "contracts_vendor_registry.csv",
                      ["supplier_id", "uei", "legal_name", "business_type", "registered_address", "registration_date",
                       "bank_account_id", "bank_institution_id", "bank_account_masked", "alternate_bank_account_id", "state_license"], rows)

    # ---- business filings: formation records; shared commercial agents are common
    agents = ["Lone Star Registered Agents Inc., 815 Brazos St Suite 500, Austin TX 78701",
              "Coastal Corporate Services LLC, 500 N Shoreline Blvd Suite 1100, Corpus Christi TX 78401",
              "Texas Filing Partners Inc., 1999 Bryan St Suite 900, Dallas TX 75201",
              "Gulf States Agent Co., 2100 West Loop S Suite 800, Houston TX 77027"]
    organizers = ["C. Whitley, formation services clerk", "D. Mata, formation services clerk", "self-filed by owner", "self-filed by owner",
                  "attorney of record", "self-filed by owner", "R. Okonjo, formation services clerk"]
    rows = []
    for v in sorted(er["vendors"], key=lambda v: v["vendor_id"]):
        r = rng("filing", v["vendor_id"])
        reg_date = dt.date.fromisoformat(v["registration_date"])
        form = reg_date - dt.timedelta(days=int(r.integers(4, 900)))
        agent = agents[int(r.integers(len(agents)))] if r.random() < 0.45 else "owner at registered address"
        organizer = organizers[int(r.integers(len(organizers)))]
        mgmt = "member-managed" if r.random() < 0.6 else "manager-managed"
        governing = "individual owner on file" if agent.startswith("owner") or r.random() < 0.7 else "entity member on file"
        if v["vendor_id"] in (VANTORRA, QUELLMAR):
            form = dt.date(2027, 7, 29)
            agent, organizer, mgmt = agents[1], organizers[0], "manager-managed"
            governing = "entity member on file (foreign, not registered in Texas)"
        elif v["vendor_id"] in ("VND-0003", "VND-0004"):
            form = reg_date - dt.timedelta(days=6)
        rows.append([f"SOS-{int(h('sos', v['vendor_id'])[:9], 16) % 900000000 + 100000000}", form.isoformat(), "certificate of formation",
                     v["name"], v["vendor_id"], agent, organizer, mgmt, governing, ""])
    # the forfeiture complaint is the first record that names the common owner (public from that day)
    for vid in (VANTORRA, QUELLMAR):
        rows.append(["USDC-SDTX-2:28-cv-00007", d2s(114), "civil forfeiture complaint (in rem), exhibit: ownership", W.vend[vid]["name"], vid, "", "",
                     "", "beneficial owner alleged: Brannoch Maritime Holdings (listed director L. Marrick)",
                     "alleges about $3.9 million in diverted disaster aid received in accounts tied to the firms"])
    rows.sort(key=lambda x: (x[1], x[0], x[4]))
    n_fil = write_csv(P + "contracts_business_filings.csv",
                      ["filing_number", "filing_date", "filing_type", "entity_name", "supplier_id", "registered_agent", "organizer",
                       "management", "governing_persons", "remarks"], rows)

    # ---- awards
    naics = {"Debris": "562119", "debris": "562119", "fuel": "424720", "generator": "811310", "hauling": "484220", "fencing": "238990",
             "plumbing": "238220", "hvac": "238220", "roofing": "238160", "electrical": "238210", "sanitation": "562991",
             "staffing": "561320", "water damage": "562910", "pump": "423830", "salvage": "488390", "trucking": "488510", "contractor": "236118"}
    awards = []
    for c in sorted(er["contracts"], key=lambda c: (c["award_date"], c["contract_id"])):
        r = rng("award", c["contract_id"])
        ad = dt.date.fromisoformat(c["award_date"])
        code = next((v for k, v in naics.items() if k in c["description"].lower()), "561990")
        rs = rng("award-signer", c["contract_id"])
        signer = (f"{FIRST[int(rs.integers(len(FIRST)))]} {LAST[int(rs.integers(len(LAST)))]}, "
                  + str(rs.choice(["owner", "president", "managing partner", "operations manager", "general manager", "vice president", "contracts manager"])))
        debris = any(k in c["description"].lower() for k in ("debris", "hauling", "tree service"))
        if c["contract_id"] == PIID_DEBRIS:
            funding, pop, signer = "FEMA Public Assistance, Category A (debris removal), DR-4821-TX", 180, "Derek Sloane, managing partner"
        elif c["contract_id"] == PIID_FUEL:
            funding, pop, signer = "Operations and maintenance, emergency", 120, "Nadia Kerr, operations manager"
        else:
            funding = "FEMA Public Assistance, DR-4821-TX" if "Rafael" in c["description"] and r.random() < 0.6 else "general fund"
            if debris and "Rafael" in c["description"]:
                funding = "FEMA Public Assistance, Category A (debris removal), DR-4821-TX"
            elif "standby" in c["description"].lower() and rs.random() < 0.4:
                funding = "Operations and maintenance, emergency"
            pop = int(r.choice([60, 90, 120, 180, 365]))
        awards.append([c["contract_id"], c["awarding_body"], W.org(AWARD_ORG.get(c["awarding_body"], c["awarding_body"])), c["vendor_id"],
                       W.vend[c["vendor_id"]]["name"], c["description"], c["award_date"], c["value_usd"],
                       "sole source, emergency" if c["procurement"].startswith("emergency, after") else c["procurement"],
                       1 if "sole" in c["procurement"] else (3 if "three" in c["procurement"] else int(r.integers(2, 7))),
                       ad.isoformat(), (ad + dt.timedelta(days=pop)).isoformat(), code, funding, signer])
    n_aw = write_csv(P + "contracts_awards.csv",
                     ["piid", "awarding_body", "awarding_org_id", "supplier_id", "supplier_name", "description", "award_date",
                      "value_usd", "procurement_method", "offers_received", "period_start", "period_end", "naics", "funding", "supplier_signatory"],
                     awards)

    # ---- debris monitoring and debris invoices (weekly)
    mon, invoices = [], []
    weeks = [(d, d + 6) for d in range(20, 76, 7)]            # Oct 4 .. Nov 28, weekly periods
    shape = [0.75, 1.0, 1.0, 0.95, 0.85, 0.7, 0.5, 0.3]
    sid = 0
    inv_seq = defaultdict(int)

    def new_invoice(piid, vid, inv_day, p0, p1, desc, qty, unit, price, amount, account, area_id=""):
        inv_seq[vid] += 1
        invoices.append({"invoice_id": f"INV-{vid[4:]}-{inv_seq[vid]:04d}", "piid": piid, "supplier_id": vid, "invoice_date": d2s(inv_day),
                         "period_start": d2s(p0) if p0 is not None else "", "period_end": d2s(p1) if p1 is not None else "",
                         "description": desc, "work_area_id": area_id, "quantity": qty, "unit": unit, "unit_price_usd": price,
                         "amount_usd": round(amount, 2), "remit_bank_account_id": account, "inv_day": inv_day})
        return invoices[-1]

    for zi, (zid, area_id, vid, piid, peak) in enumerate(ZONES):
        r = rng("debris", zid)
        award_day = (dt.date.fromisoformat(W.contracts[piid]["award_date"]) - dt.date(2027, 9, 14)).days
        price = 186.0 if vid == VANTORRA else round(float(r.uniform(128, 171)), 2)
        for wi, (p0, p1) in enumerate(weeks):
            if p0 < award_day + 5:
                continue
            supported = peak * shape[wi] * float(r.uniform(0.9, 1.1))
            for method in ("drone photogrammetry", "satellite change detection"):
                sid += 1
                est = supported * (float(r.uniform(0.94, 1.06)))
                mon.append([f"DMS-{sid:04d}", d2s(p1 + 1), zid, area_id, piid, vid, d2s(p0), d2s(p1), method, int(round(est)),
                            int(round(est * 4.6))])
            billed = supported * (BILL_RATIO * float(r.uniform(0.96, 1.04)) if vid == VANTORRA else float(r.uniform(0.9, 1.08)))
            billed = int(round(billed))
            acct = W.vend[vid]["remit_account_id"]
            if vid == VANTORRA and wi >= 5 and zi % 2 == 0:
                acct = A72                                   # remittance moved to the alternate account on later invoices
            new_invoice(piid, vid, p1 + 2, p0, p1, f"Debris removal and haul to reduction site, zone {zid}", billed, "ton", price,
                        billed * price, acct, area_id)
    new_invoice(PIID_DEBRIS, VANTORRA, 14, None, None, "Mobilisation, equipment and reduction-site set-up", 1, "lump sum", 940000.0, 940000.0, A71)
    n_mon = write_csv(P + "contracts_debris_monitoring.csv",
                      ["survey_id", "survey_date", "zone_id", "area_id", "piid", "supplier_id", "period_start", "period_end", "method",
                       "estimated_tons_removed", "estimated_cubic_yards"], sorted(mon, key=lambda x: (x[1], x[0])))

    # ---- fuel invoices (deliveries from Oct 17)
    for k, dday, tno, gal, price in fuel_ledger.deliveries():
        new_invoice(PIID_FUEL, QUELLMAR, dday + 1 + (int(rng("fuel-inv-lag", k).integers(0, 4)) if k else 0), dday, dday,
                    f"Diesel fuel, ultra-low sulfur, delivered to generator fuel farm (delivery ticket {tno})",
                    gal, "gallon", price, gal * price, A72 if k in (4, 7) else A71)

    # ---- ordinary contracts: milestone or monthly invoices
    for c in er["contracts"]:
        if c["contract_id"] in (PIID_DEBRIS, PIID_FUEL) or c["contract_id"] in {z[3] for z in ZONES}:
            continue
        r = rng("inv", c["contract_id"])
        award_day = (dt.date.fromisoformat(c["award_date"]) - dt.date(2027, 9, 14)).days
        n = int(r.integers(2, 7))
        used = float(r.uniform(0.55, 0.97)) * c["value_usd"]
        parts = r.dirichlet(np.ones(n) * 3) * used
        dday = award_day + int(r.integers(6, 15))
        if "standby" in c["description"].lower():
            dday = max(dday, 3 + int(r.integers(2, 9)))       # standby agreements are drawn on after landfall
        for k in range(n):
            if dday > 116:
                break
            if closed(dday):
                dday = 5
            new_invoice(c["contract_id"], c["vendor_id"], dday, dday - int(r.integers(7, 15)), dday - 1,
                        c["description"].split(": ")[-1].capitalize() + f", progress billing {k + 1}", 1, "lump sum",
                        round(float(parts[k]), 2), float(parts[k]), W.vend[c["vendor_id"]]["remit_account_id"])
            dday += int(r.integers(9, 24))

    # ---- small purchases without a contract (purchase orders), from every ordinary vendor
    buyers = ["City of Corpus Christi", "Nueces County Commissioners Court", "Port of Corpus Christi", "Coastal Bend Power and Water Authority",
              "San Patricio County", "City of Port Aransas"]
    po_rows = []
    for v in er["vendors"]:
        if v["vendor_id"] in (VANTORRA, QUELLMAR, "VND-0003", "VND-0004"):
            continue
        r = rng("po", v["vendor_id"])
        storm_trade = bool(re.search(r"Roof|debris|Tree|Haul|Generator|sanitation|water|Plumb|Electric|Fenc|Equipment|HVAC|contractor|salvage", v["business_type"]))
        rate = (0.05, 0.22) if storm_trade else (0.03, 0.05)
        for day in range(-60, 120):
            if not business_days(day) or closed(day) or d2s(day) < v["registration_date"]:
                continue
            if r.random() < (rate[1] if 3 < day < 70 else rate[0]):
                amt = round(float(np.exp(r.normal(7.9, 0.9))), 2)
                amt = min(amt, 24900.0)
                buyer = buyers[int(r.integers(len(buyers)))]
                inv = new_invoice("", v["vendor_id"], day, None, None, f"{v['business_type']} services, purchase order", 1, "lump sum", amt, amt,
                                  v["remit_account_id"])
                inv["po_number"] = f"PO-{h('po', v['vendor_id'], day)[:8].upper()}"
                inv["buyer"] = buyer

    # ---- payment status
    actions = []
    for inv in invoices:
        r = rng("pay", inv["invoice_id"])
        c = W.contracts.get(inv["piid"])
        buyer = c["awarding_body"] if c else inv.get("buyer", "")
        inv["buyer"] = buyer
        inv["buyer_org_id"] = W.org(AWARD_ORG.get(buyer, buyer))
        inv.setdefault("po_number", "")
        lag = int(r.integers(12, 34))
        appr, paid = inv["inv_day"] + int(r.integers(2, 9)), inv["inv_day"] + lag
        status, hold = "paid", ""
        if inv["supplier_id"] == VANTORRA:
            paid = inv["inv_day"] + int(r.integers(9, 15))    # paid quickly under the emergency order
            if paid >= 80:                                     # county paused payments on Dec 3
                status, hold, paid = "payment on hold pending audit", d2s(80), None
        elif inv["supplier_id"] == QUELLMAR:
            paid = inv["inv_day"] + int(r.integers(10, 16))
            if paid >= 75:                                     # Navy suspension on Nov 28
                status, hold, paid = "payment withheld, supplier suspended", d2s(75), None
        while paid is not None and (not business_days(paid) or closed(paid)):
            paid += 1
        if paid is not None and paid > 119:
            status, paid = "approved, awaiting payment", None
        inv["approved_date"] = d2s(appr) if appr <= 119 else ""
        inv["paid_date"] = d2s(paid) if paid is not None else ""
        inv["paid_day"] = paid
        inv["status"], inv["hold_date"] = status, hold
        inv["payment_reference"] = f"PMT-{h('pmt', inv['invoice_id'])[:10].upper()}" if paid is not None else ""
    invoices.sort(key=lambda i: (i["invoice_date"], i["invoice_id"]))
    n_inv = write_csv(P + "contracts_invoices.csv",
                      ["invoice_id", "piid", "po_number", "supplier_id", "buyer", "buyer_org_id", "invoice_date", "period_start", "period_end",
                       "description", "work_area_id", "quantity", "unit", "unit_price_usd", "amount_usd", "remit_bank_account_id",
                       "approved_date", "paid_date", "payment_reference", "status", "hold_date"],
                      [[i["invoice_id"], i["piid"], i["po_number"], i["supplier_id"], i["buyer"], i["buyer_org_id"], i["invoice_date"],
                        i["period_start"], i["period_end"], i["description"], i["work_area_id"], i["quantity"], i["unit"], i["unit_price_usd"],
                        money(i["amount_usd"]), i["remit_bank_account_id"], i["approved_date"], i["paid_date"], i["payment_reference"],
                        i["status"], i["hold_date"]] for i in invoices])

    # ---- contract actions
    def act(day, piid, vid, kind, authority, text):
        actions.append([d2s(day), piid, vid, kind, authority, text])
    act(10, PIID_DEBRIS, VANTORRA, "award", "Nueces County Commissioners Court", "Emergency sole-source award under the disaster declaration; not-to-exceed $14,200,000")
    act(12, PIID_FUEL, QUELLMAR, "award", "Naval Air Station Corpus Christi", "Emergency award for generator fuel after the regular supplier's terminal flooded; $2,100,000")
    act(31, PIID_FUEL, QUELLMAR, "notice to proceed", "Naval Air Station Corpus Christi", "Deliveries to begin when the ship channel reopens to fuel barges; federal supply continues until then")
    act(52, PIID_DEBRIS, VANTORRA, "remittance change", "Nueces County Auditor", "Supplier requested payment of later invoices to its alternate bank account on file")
    act(46, PIID_FUEL, QUELLMAR, "remittance change", "Naval Air Station Corpus Christi", "Supplier requested payment of selected invoices to its alternate bank account on file")
    act(73, PIID_FUEL, QUELLMAR, "product quality deficiency report", "Naval Air Station Corpus Christi",
        "Fuel samples from the generator fuel farm sent for laboratory analysis after the generator failure on Oct. 24")
    act(75, PIID_FUEL, QUELLMAR, "supplier suspended", "Department of the Navy", "Suspension pending fuel quality review; open invoices withheld")
    act(78, PIID_DEBRIS, VANTORRA, "records request", "Nueces County Auditor", "Load tickets and tower logs requested for all billed tonnage")
    act(80, PIID_DEBRIS, VANTORRA, "payment hold", "Nueces County Commissioners Court", "Payments paused pending audit of billed tonnage")
    act(84, PIID_DEBRIS, VANTORRA, "inspector general review opened", "Federal inspector general", "Review of emergency debris and fuel contracts in the Coastal Bend")
    act(84, PIID_FUEL, QUELLMAR, "inspector general review opened", "Federal inspector general", "Review of emergency debris and fuel contracts in the Coastal Bend")
    act(104, PIID_DEBRIS, VANTORRA, "search warrant executed", "Federal Bureau of Investigation", "Records seized at the supplier's office")
    act(104, PIID_FUEL, QUELLMAR, "search warrant executed", "Federal Bureau of Investigation", "Records seized at the supplier's office")
    for c in er["contracts"]:
        if c["contract_id"] in (PIID_DEBRIS, PIID_FUEL):
            continue
        r = rng("act", c["contract_id"])
        aday = (dt.date.fromisoformat(c["award_date"]) - dt.date(2027, 9, 14)).days
        act(aday, c["contract_id"], c["vendor_id"], "award", c["awarding_body"], c["description"])
        if r.random() < 0.45 and aday + 30 < 115:
            act(aday + int(r.integers(18, 50)), c["contract_id"], c["vendor_id"], "modification", c["awarding_body"],
                str(r.choice(["Period of performance extended 30 days", "Ceiling increased 10 percent for added scope",
                              "Administrative change: contracting officer's representative", "Option exercised"])))
        if r.random() < 0.12 and aday + 20 < 115:
            act(aday + int(r.integers(15, 60)), c["contract_id"], c["vendor_id"], "remittance change", c["awarding_body"],
                "Supplier updated its bank details on file")
        if c["vendor_id"] in getattr(W, "alt_account", {}) and aday + 25 < 115:
            act(aday + int(r.integers(20, 55)), c["contract_id"], c["vendor_id"], "remittance change", c["awarding_body"],
                "Supplier requested payment of later invoices to its alternate bank account on file")
    # unit-price debris contracts: the ceiling is raised by modification as hauled volumes pass the pre-event estimate
    for zid, area_id, vid, piid, peak in ZONES:
        if vid == VANTORRA:
            continue
        r = rng("ceiling", piid)
        ceiling, cum = float(W.contracts[piid]["value_usd"]), 0.0
        for inv in sorted((i for i in invoices if i["piid"] == piid), key=lambda i: i["inv_day"]):
            cum += inv["amount_usd"]
            if cum > 0.85 * ceiling:
                ceiling = round(cum * float(r.uniform(1.5, 2.3)) / 1000.0) * 1000.0
                act(inv["inv_day"] - int(r.integers(1, 5)), piid, vid, "modification", W.contracts[piid]["awarding_body"],
                    f"Not-to-exceed amount raised to ${ceiling:,.0f}; hauled debris volume above the pre-event estimate")
    actions.sort()
    n_act = write_csv(P + "contracts_actions.csv", ["action_date", "piid", "supplier_id", "action_type", "authority", "description"], actions)
    print(f"contracts: vendors {n_reg}, filings {n_fil}, awards {n_aw}, invoices {n_inv}, actions {n_act}, debris surveys {n_mon}")
    return invoices


# ======================================================================================
# insurance claims
# ======================================================================================
CLAIM_HEADER = ["record_type", "claim_id", "transaction_id", "claim_program", "policy_id", "policy_type", "insurer_id", "broker_id",
                "holder_id", "claimant_name", "claimant_category", "property_address", "area_id", "latitude", "longitude",
                "transaction_type", "transaction_date", "prior_rcv_usd", "new_rcv_usd", "county_assessed_value_usd",
                "appraisal_order_id", "appraisal_order_date", "appraisal_priority", "appraiser_id", "appraiser_initials",
                "loss_date", "loss_cause", "filed_date", "fnol_channel", "adjuster_id", "adjuster_assigned_date", "inspection_date",
                "claimed_usd", "contractor_estimate_supplier_id", "estimate_document_id", "assignment_of_benefits", "damage_narrative_id",
                "photo_ids", "paid_usd", "paid_date", "payment_account_id", "status", "status_date"]
INS_CODE = {"INS-CC-001": "CC", "INS-GS-002": "GS", "INS-NFIP-003": "NF", "INS-TW-004": "TW", "INS-BF-005": "BF", "INS-SN-006": "SN", "INS-PR-007": "PR"}
INITIALS = ["TB", "JL", "KS", "MR", "AD", "PG", "LW", "CN", "EH", "SV", "DO", "RF"]


def build_claims(W):
    er, r0 = W.er, rng("claims")
    rows, payments = [], []
    blank = {k: "" for k in CLAIM_HEADER}

    def row(**kw):
        d = dict(blank)
        d.update(kw)
        rows.append(d)
        return d

    # ---------- policy transactions
    tx_seq = 0
    appr_seq = 0
    for p in sorted(er["policies"], key=lambda p: (p["bound_date"], p["policy_number"])):
        r = rng("poltx", p["policy_number"])
        bd = dt.date.fromisoformat(p["bound_date"])
        is_lph = p["policy_number"] in W.lph
        hold = W.holder[p["holder_id"]]
        if bd >= dt.date(2027, 7, 16):                       # new business inside the scenario
            tx_seq += 1
            a_id, a_date, prio, ini = "", "", "", ""
            if p.get("appraiser_id"):
                appr_seq += 1
                a_id = f"APO-{2027}{appr_seq:05d}"
                lead = int(r.integers(1, 5)) if is_lph else int(r.integers(4, 16))
                ad = max(bd - dt.timedelta(days=lead), dt.date(2027, 8, 1) if is_lph else dt.date(2027, 6, 1))
                a_date = ad.isoformat()
                prio = "RUSH" if is_lph or r.random() < 0.07 else "standard"
                ini = "RM" if is_lph else INITIALS[int(h("ini", p["appraiser_id"], p["policy_number"])[:4], 16) % (4 if p["appraiser_id"] == "APR-001" else len(INITIALS))]
            row(record_type="policy_transaction", transaction_id=f"PTX-{tx_seq:06d}", policy_id=p["policy_number"], policy_type=p["policy_type"],
                insurer_id=p["insurer_id"], broker_id=p.get("broker_id") or "", holder_id=p["holder_id"], claimant_name=hold["name"],
                property_address=p["property_address"], transaction_type="new business, replacement cost value endorsement" if p.get("appraiser_id") else "new business",
                transaction_date=p["bound_date"], new_rcv_usd=p["replacement_cost_value_usd"], county_assessed_value_usd=p["county_assessed_value_usd"],
                appraisal_order_id=a_id, appraisal_order_date=a_date, appraisal_priority=prio, appraiser_id=p.get("appraiser_id") or "", appraiser_initials=ini)
        else:
            # renewals and mid-term endorsements on older policies
            ann = dt.date(2027 if (bd.month, bd.day) >= (7, 16) else 2028, bd.month, min(bd.day, 28))
            if dt.date(2027, 7, 16) <= ann <= dt.date(2028, 1, 11) and r.random() < 0.9:
                tx_seq += 1
                bump = float(r.uniform(1.02, 1.08))
                a_id = a_date = prio = ini = apr = ""
                if r.random() < 0.3 and p["policy_type"] in ("HO3", "CP"):        # some renewals come with a fresh appraisal
                    appr_seq += 1
                    apr = f"APR-00{1 + int(r.integers(6))}"
                    a_id = f"APO-{2027}{appr_seq:05d}"
                    a_date = (ann - dt.timedelta(days=int(r.integers(6, 30)))).isoformat()
                    prio = "RUSH" if r.random() < 0.06 else "standard"
                    ini = INITIALS[int(h("ini", apr, p["policy_number"])[:4], 16) % (4 if apr == "APR-001" else len(INITIALS))]
                row(record_type="policy_transaction", transaction_id=f"PTX-{tx_seq:06d}", policy_id=p["policy_number"], policy_type=p["policy_type"],
                    insurer_id=p["insurer_id"], broker_id=p.get("broker_id") or "", holder_id=p["holder_id"], claimant_name=hold["name"],
                    property_address=p["property_address"], transaction_type="renewal", transaction_date=ann.isoformat(),
                    prior_rcv_usd=int(round(p["replacement_cost_value_usd"] / bump, -3)), new_rcv_usd=p["replacement_cost_value_usd"],
                    county_assessed_value_usd=p["county_assessed_value_usd"], appraisal_order_id=a_id, appraisal_order_date=a_date,
                    appraisal_priority=prio, appraiser_id=apr, appraiser_initials=ini)
            elif r.random() < 0.03:
                tx_seq += 1
                d = dt.date(2027, 7, 20) + dt.timedelta(days=int(r.integers(0, 50)))
                row(record_type="policy_transaction", transaction_id=f"PTX-{tx_seq:06d}", policy_id=p["policy_number"], policy_type=p["policy_type"],
                    insurer_id=p["insurer_id"], broker_id=p.get("broker_id") or "", holder_id=p["holder_id"], claimant_name=hold["name"],
                    property_address=p["property_address"], transaction_type="endorsement, coverage increase", transaction_date=d.isoformat(),
                    prior_rcv_usd=int(round(p["replacement_cost_value_usd"] / 1.12, -3)), new_rcv_usd=p["replacement_cost_value_usd"],
                    county_assessed_value_usd=p["county_assessed_value_usd"])

    # ---------- storm claims
    staff = defaultdict(list)
    indep = []
    for a in W.adj:
        if a.get("employer_insurer_id"):
            staff[a["employer_insurer_id"]].append(a["adjuster_id"])
        else:
            indep.append(a["adjuster_id"])
    indep_wo = [a for a in indep if a != "ADJ-0847"]
    repair_vendors = [v["vendor_id"] for v in er["vendors"] if re.search(r"Roof|Water damage|General contractor|Electrical|Plumb|HVAC|Fenc|Tree", v["business_type"])
                      and v["vendor_id"] not in ("VND-0003", "VND-0004")]
    seq = defaultdict(int)
    lph_claims = sorted(W.lph)
    r = rng("lph-pick")
    lph_filing = set(r.choice(lph_claims, size=187, replace=False).tolist())
    lph_narr = 0
    lph_docs = [f"EST-{h('lphdoc', i)[:8].upper()}" for i in range(26)]
    lph_photos = [f"IMG-{h('lphphoto', i)[:10]}.jpg" for i in range(12)]
    lph_scale = None
    lph_amounts = {}
    rr = rng("lph-amt")
    raw = {pn: W.pol[pn]["replacement_cost_value_usd"] * float(rr.uniform(0.06, 0.26)) for pn in sorted(lph_filing)}
    k = 23_400_000 / sum(raw.values())
    lph_amounts = {pn: round(v * k, -2) for pn, v in raw.items()}

    for p in sorted(er["policies"], key=lambda p: p["policy_number"]):
        pn = p["policy_number"]
        r = rng("claim", pn)
        is_lph = pn in W.lph
        ll = W.geocode(p["property_address"])
        if ll is None:
            continue
        shore = W.G.shore_distance_m(*ll)
        coastal = shore < 1800 or "Port Aransas" in p["property_address"] or "Laguna Shores" in p["property_address"]
        pt = p["policy_type"]
        if is_lph:
            if pn not in lph_filing:
                continue
            files = True
        else:
            prob = {"HO3": 0.74, "WND": 0.83, "FLD": 0.78 if coastal else 0.22, "CP": 0.68, "BI": 0.6}[pt]
            if dt.date.fromisoformat(p["bound_date"]) > dt.date(2027, 9, 13):
                continue
            files = r.random() < prob
        if not files:
            continue
        ins = p["insurer_id"]
        seq[ins] += 1
        cid = f"CLM-2027-{INS_CODE[ins]}-{seq[ins]:06d}"
        hold = W.holder[p["holder_id"]]
        # peril and loss date (never before landfall)
        if is_lph:
            cause, loss_day = ("wind and wind-driven rain" if pt != "BI" else "business interruption"), 0
        elif pt == "FLD":
            cause, loss_day = "storm surge flooding" if coastal else "flooding from heavy rain", 0 if r.random() < 0.85 else 1
        elif pt == "BI":
            cause, loss_day = "business interruption, loss of power and access", 0
        else:
            u = r.random()
            if u < 0.72:
                cause, loss_day = "wind", 0
            elif u < 0.84:
                cause, loss_day = "wind-driven rain, roof leak", 0
            elif u < 0.89:
                cause, loss_day = "food spoilage, power outage", int(r.integers(2, 7))
            elif u < 0.93:
                cause, loss_day = "power surge when service was restored", int(r.integers(3, 30))
            elif u < 0.97:
                cause, loss_day = "mould after water intrusion", int(r.integers(6, 26))
            else:
                cause, loss_day = "theft from damaged premises", int(r.integers(1, 10))
        # filing day: few in the first two days (no power, no signal), then a long ramp
        if is_lph:
            filed = int(r.integers(3, 32))
        else:
            filed = loss_day + int(np.clip(r.gamma(2.0, 6.5), 0, 105))
            if filed < 2 and r.random() < 0.8:
                filed += int(r.integers(2, 6))
            if "Leopard" in p["property_address"] or "Up River" in p["property_address"]:
                filed += int(r.integers(0, 8))
        if filed > 118:
            filed = 118
        channel = str(r.choice(["phone", "mobile app", "web", "agent", "catastrophe claims tent"], p=[0.34, 0.24, 0.22, 0.14, 0.06]))
        if is_lph:
            channel = "agent"
        # amounts
        rcv = p["replacement_cost_value_usd"]
        if is_lph:
            claimed = lph_amounts[pn]
        elif cause.startswith("food"):
            claimed = round(float(r.uniform(250, 900)), 0)
        elif cause.startswith("power surge") or cause.startswith("theft"):
            claimed = round(float(np.exp(r.normal(7.9, 0.6))), 0)
        else:
            sev = 0.8 * float(np.exp(r.normal(8.75 if not coastal else 9.4, 0.95)))
            if pt in ("CP", "BI"):
                sev *= 2.6
            claimed = round(min(sev, rcv * 0.95), -1)
        # adjuster
        if is_lph:
            adj = "ADJ-0847" if r.random() < 0.55 else str(r.choice(indep_wo))
        elif staff.get(ins) and r.random() < 0.45:
            adj = str(r.choice(staff[ins]))
        else:
            adj = str(r.choice(indep))
        assigned = filed + int(r.integers(0, 4))
        slow = 9 if ("Leopard" in p["property_address"] or "Up River" in p["property_address"]) else 0
        insp = assigned + (int(r.integers(1, 5)) if is_lph else int(r.integers(3, 24)) + slow)
        # paperwork
        est_vendor, est_doc, aob, narr, photos = "", "", "N", "", ""
        if is_lph:
            est_vendor = "VND-0003" if pt == "HO3" else "VND-0004"
            est_doc = lph_docs[int(r.integers(len(lph_docs)))]
            if pt in ("CP", "BI") and lph_narr < 47:
                lph_narr += 1
                narr = "NAR-7F3A"
                photos = ";".join(sorted(set(str(x) for x in r.choice(lph_photos, size=int(r.integers(3, 7)), replace=False))))
            else:
                narr = f"NAR-{h('narr', pn)[:4].upper()}"
                photos = ";".join(f"IMG-{h('ph', pn, i)[:10]}.jpg" for i in range(int(r.integers(3, 8))))
        elif claimed > 2500 and r.random() < 0.7:
            if r.random() < 0.045:
                est_vendor, aob = "VND-0003", "Y"            # door-to-door remediation firm, assignment of benefits
            else:
                est_vendor = str(r.choice(repair_vendors))
            est_doc = f"EST-{h('doc', pn)[:8].upper()}"
            narr = f"NAR-{h('narr', pn)[:4].upper()}"
            photos = ";".join(f"IMG-{h('ph', pn, i)[:10]}.jpg" for i in range(int(r.integers(2, 9))))
        else:
            narr = f"NAR-{h('narr', pn)[:4].upper()}"
            photos = ";".join(f"IMG-{h('ph', pn, i)[:10]}.jpg" for i in range(int(r.integers(1, 5))))
        # outcome
        status, status_day, paid_usd, paid_day = "open, awaiting inspection", filed, "", None
        if insp <= 119:
            if is_lph:
                pay = insp + int(r.integers(4, 11))
                rs = rng("claim-review", pn)
                if pay < 30:                                   # before the fraud task force was formed
                    status, paid_usd, paid_day, status_day = "paid", claimed * float(r.uniform(0.88, 1.0)), pay, pay
                elif pay < 90:                                 # afterwards some are referred, most just sit in the queue like everyone else's
                    if rs.random() < 0.3:
                        status, status_day = "under review, special investigations unit", max(30, insp) + int(rs.integers(0, 25))
                    else:
                        status, status_day = "open, estimate under review", insp
                else:
                    status, status_day = ("payment stopped", 90 + int(rs.integers(0, 12))) if rs.random() < 0.6 else ("under review, special investigations unit", 90)
            else:
                u = r.random()
                pay = insp + int(r.integers(6, 34))
                if u < 0.11:
                    status, status_day = "denied, cause of loss not covered" if pt != "FLD" else "denied, below deductible", insp + int(r.integers(3, 15))
                elif pay <= 119:
                    status, paid_usd, paid_day, status_day = "paid", claimed * float(r.uniform(0.55, 0.98)), pay, pay
                else:
                    status, status_day = "open, estimate under review", insp
                # routine referrals: late notice, estimate far above the adjuster's, assignment of benefits, a prior loss at the address
                rs = rng("claim-review", pn)
                p_ref = 0.034 + (0.16 if aob == "Y" else 0.0) + (0.05 if claimed > 0.6 * rcv else 0.0) + (0.03 if filed - loss_day > 45 else 0.0)
                u2 = rs.random()
                if u2 < p_ref:
                    status, status_day = "under review, special investigations unit", min(119, max(insp, 12) + int(rs.integers(0, 30)))
                    paid_usd, paid_day = "", None
                elif u2 < p_ref + 0.012:
                    status, status_day = "payment stopped", min(119, insp + int(rs.integers(10, 40)))      # lienholder dispute or duplicate-payment hold
                    paid_usd, paid_day = "", None
        if paid_day is not None:
            while not business_days(paid_day) or closed(paid_day):
                paid_day += 1
            if paid_day > 119:
                status, paid_usd, paid_day = "open, payment scheduled", "", None
        if status_day > 119:
            status_day = 119
        d = row(record_type="claim", claim_id=cid, claim_program="property insurance", policy_id=pn, policy_type=pt, insurer_id=ins,
                broker_id=p.get("broker_id") or "", holder_id=p["holder_id"], claimant_name=hold["name"], property_address=p["property_address"],
                latitude=ll[0], longitude=ll[1], loss_date=d2s(loss_day), loss_cause=cause, filed_date=d2s(filed), fnol_channel=channel,
                adjuster_id=adj, adjuster_assigned_date=d2s(assigned) if assigned <= 119 else "", inspection_date=d2s(insp) if insp <= 119 else "",
                claimed_usd=money(claimed), contractor_estimate_supplier_id=est_vendor, estimate_document_id=est_doc, assignment_of_benefits=aob,
                damage_narrative_id=narr, photo_ids=photos, paid_usd=money(paid_usd) if paid_usd != "" else "",
                paid_date=d2s(paid_day) if paid_day is not None else "", payment_account_id=W.insurer[ins]["claims_payment_account_id"] if paid_day is not None else "",
                status=status, status_date=d2s(status_day))
        if paid_day is not None:
            payments.append({"claim_id": cid, "day": paid_day, "amount": round(float(paid_usd), 2), "account": W.insurer[ins]["claims_payment_account_id"],
                             "payee": hold["name"], "lph": is_lph, "holder_id": p["holder_id"]})

    # ---------- oil-spill claims at the claims centre (not insurance policies)
    cats = [("commercial shrimper", "AREA-CITY-ARANSASPASS", 0.22, 10.1), ("commercial fisher", "AREA-CITY-ARANSASPASS", 0.12, 9.9),
            ("oyster harvester", "AREA-CITY-ROCKPORT", 0.07, 9.7), ("charter boat operator", "AREA-CITY-PORTARANSAS", 0.13, 10.0),
            ("bait and tackle business", "AREA-CITY-PORTARANSAS", 0.06, 9.6), ("seafood dealer or processor", "AREA-CITY-ARANSASPASS", 0.05, 10.4),
            ("deckhand", "AREA-CITY-ARANSASPASS", 0.14, 9.0), ("shoreline property owner", "AREA-NBH-NORTHBEACH", 0.11, 8.6),
            ("marina or boat storage", "AREA-CITY-PORTLAND", 0.03, 10.2), ("waterfront restaurant or lodging", "AREA-NBH-NORTHBEACH", 0.07, 10.1)]
    alt_area = ["AREA-CITY-INGLESIDE", "AREA-CITY-PORTLAND", "AREA-NBH-NORTHBEACH", "AREA-CITY-CORPUSCHRISTI", "AREA-NBH-FLOURBLUFF",
                "AREA-CITY-FULTON", "AREA-CITY-ROCKPORT", "AREA-CITY-PORTARANSAS", "AREA-CITY-ARANSASPASS"]
    r = rng("spill")
    probs = np.array([c[2] for c in cats])
    probs /= probs.sum()
    n_spill = 4204
    for i in range(n_spill):
        ci = int(r.choice(len(cats), p=probs))
        cat, area, _, mu = cats[ci]
        if r.random() < 0.35:
            area = alt_area[int(r.integers(len(alt_area)))]
        prop = cat in ("shoreline property owner", "marina or boat storage") or r.random() < 0.06
        u = r.random()
        if prop and u < 0.75:
            filed = 12 + int(np.clip(r.gamma(2.0, 9.0), 0, 48))               # cleanup and property claims from Sept. 26
            kind = "oil contamination, property damage and cleanup costs"
        elif u < 0.955 or prop:
            filed = 63 + int(np.clip(r.gamma(1.6, 5.2), 0, 26))               # lost-income claims from Nov. 16
            kind = "oil spill, loss of income (fishing and shellfish closures)"
            if prop:
                kind = "oil contamination, property damage and cleanup costs"
        else:
            filed = 90 + int(r.integers(0, 26))
            kind = "oil spill, loss of income (fishing and shellfish closures)"
        loss_day = 0 if "property" in kind else 4                              # closures began Sept. 18
        claimed = round(float(np.exp(r.normal(mu if "income" in kind else 8.4, 0.75))), -1)
        name = f"{FIRST[int(r.integers(len(FIRST)))]} {LAST[int(r.integers(len(LAST)))]}"
        if cat in ("bait and tackle business", "seafood dealer or processor", "marina or boat storage", "waterfront restaurant or lodging") and r.random() < 0.6:
            name = f"{LAST[int(r.integers(len(LAST)))]} {str(r.choice(['Seafood', 'Marine', 'Bait & Tackle', 'Charters', 'Fish House', 'Boat Works', 'Bayside Grill']))}"
        st, sday, paid, pday = "received", filed, "", None
        dec = filed + int(r.integers(20, 75))
        if dec <= 119:
            if r.random() < 0.6:
                st, paid, pday, sday = "paid, interim payment", claimed * float(r.uniform(0.3, 0.8)), dec, dec
            else:
                st, sday = "more documentation requested", dec
        row(record_type="claim", claim_id=f"CLM-2027-SPL-{i + 1:06d}", claim_program="oil spill claims centre (Oil Pollution Act)", claimant_name=name,
            claimant_category=cat, area_id=area, loss_date=d2s(loss_day), loss_cause=kind, filed_date=d2s(filed),
            fnol_channel=str(r.choice(["claims centre in person", "web", "phone", "mail"], p=[0.5, 0.25, 0.15, 0.1])),
            claimed_usd=money(claimed), paid_usd=money(paid) if paid != "" else "", paid_date=d2s(pday) if pday is not None else "",
            status=st, status_date=d2s(min(sday, 119)))

    def key(d):
        return (d["transaction_date"] or d["filed_date"], d["record_type"], d["claim_id"] or d["transaction_id"])
    rows.sort(key=key)
    n = write_csv(P + "insurance_claims.csv", CLAIM_HEADER, [[d[k] for k in CLAIM_HEADER] for d in rows])
    c_storm = sum(1 for d in rows if d["claim_program"] == "property insurance")
    c_lph = sum(1 for d in rows if d["claim_program"] == "property insurance" and d["policy_id"] in W.lph)
    by30 = sum(1 for d in rows if d["claim_program"] == "property insurance" and d["policy_id"] not in W.lph and d["filed_date"] <= d2s(30))
    print(f"insurance_claims: {n} rows: policy transactions {sum(1 for d in rows if d['record_type'] == 'policy_transaction')}, "
          f"storm claims {c_storm} (of which {c_lph} on one holder's 230 policies), spill claims {n_spill}; "
          f"ordinary claims filed by Oct. 14: {by30} (sampling fraction {by30 / 187000:.4f})")
    return payments, by30


# ======================================================================================
# aid applications
# ======================================================================================
AID_HEADER = ["record_id", "record_type", "application_id", "account_id", "submitted_utc", "changed_utc", "event_utc", "channel",
              "source_ip", "source_asn", "device_id", "area_id", "tract", "zip", "county", "applicant_name", "damaged_address",
              "household_size", "primary_language", "tenure", "self_reported_damage", "damage_photo_hashes", "field_changed",
              "login_utc", "login_ip_seen_before", "deposit_routing_number", "deposit_account_masked", "previous_deposit_account_masked",
              "assistance_type", "amount_usd", "status"]
OTHER_AREAS = [("AREA-CITY-PORTLAND", "San Patricio", "78374", 1900), ("AREA-CITY-INGLESIDE", "San Patricio", "78362", 1300),
               ("AREA-CITY-ARANSASPASS", "San Patricio", "78336", 1500), ("AREA-CITY-GREGORY", "San Patricio", "78359", 420),
               ("AREA-CITY-TAFT", "San Patricio", "78390", 260), ("AREA-CITY-SINTON", "San Patricio", "78387", 300),
               ("AREA-CITY-ROCKPORT", "Aransas", "78382", 2700), ("AREA-CITY-FULTON", "Aransas", "78358", 800)]
TRACT_ZIP = {"4801": "78402", "4802": "78402", "4803": "78401", "4804": "78407", "4805": "78407", "4806": "78373", "4807": "78373",
             "4808": "78418", "4809": "78418", "4810": "78410", "4811": "78411", "4812": "78405", "4813": "78407", "4814": "78405",
             "4815": "78404", "4816": "78408", "4817": "78416", "4818": "78411", "4819": "78418", "4820": "78418", "4821": "78412",
             "4822": "78415", "4823": "78412", "4824": "78406", "4825": "78410", "4826": "78410", "4827": "78409", "4828": "78410",
             "4829": "78380", "4830": "78380", "4832": "78415", "4833": "78412", "4834": "78416", "4835": "78414"}
OPEN_TS = 1820880000 + 60 * DAY + 6 * 3600  # 2027-11-13T06:00Z: registration opens at 12:00 a.m. Central on Saturday 13 November (D+60)
ISP_ASN = [7018, 22773, 20115, 11427, 21928, 20057, 7922, 64500]
HIJACK_ASN = 64512


def ip_for(key):
    """(address, network number) of a household. Both come from the address table every stream shares
    (netmap): the same address carries the same network number in the portal log and everywhere else."""
    return netmap.home(key)


def build_aid(W):
    tr = W.tr
    hij = list(tr["aid_diversion"]["hijacked_registrations"]["ids"])
    syn = tr["aid_diversion"]["synthetic_identities"]
    runner = tr["lph_runner_applications"]
    r = rng("aid")
    # ---- how many applications from where
    weights = []
    for t in W.tracts:
        zone = t["evacuation_zone"]
        dmg = {"A": 1.75, "B": 1.25, "C": 0.85, "D": 0.5}[zone]
        access = 0.47 if t["area_id"] in W.low_income else 1.0     # fewer cars, less broadband, recovery centres far away
        weights.append(t["population"] * dmg * access)
    weights = np.array(weights)
    n_nueces = 38600
    per_tract = np.floor(weights / weights.sum() * n_nueces).astype(int)
    plan = []
    for t, n in zip(W.tracts, per_tract):
        plan += [(t["area_id"], t["tract"], TRACT_ZIP.get(t["tract"][:4], "784" + str(10 + int(t["tract"][2:4]) % 9)), "Nueces")] * int(n)
    for area_id, county, zipc, n in OTHER_AREAS:
        plan += [(area_id, "", zipc, county)] * n
    r.shuffle(plan)
    n_by_d89 = len(plan)
    # late applications, with door-to-door registration in the low-income surge-zone tracts from Dec. 15
    late = []
    for t in W.tracts:
        k = int(t["population"] * (0.062 if t["area_id"] in W.low_income else 0.0035))
        late += [(t["area_id"], t["tract"], TRACT_ZIP.get(t["tract"][:4], "78415"), "Nueces")] * k
    r.shuffle(late)

    # ---- submission times: steep first days, then a decaying tail to Dec. 12
    days = np.arange(0, 30)
    curve = 5.2 * np.exp(-days / 4.2) + 1.0 * np.exp(-days / 14.0) + 0.12
    for i, d in enumerate(days):                        # weekends at recovery centres are a little quieter after the first
        if i > 2 and (dt.date(2027, 11, 13) + dt.timedelta(days=int(d))).weekday() >= 5:
            curve[i] *= 0.7
    curve /= curve.sum()
    day_idx = r.choice(len(days), size=n_by_d89, p=curve)
    hour_w = np.array([1, .6, .4, .3, .3, .5, 1.2, 2.6, 4.6, 6.2, 6.8, 6.6, 6.0, 6.2, 6.0, 5.6, 5.0, 4.6, 4.4, 4.4, 4.0, 3.2, 2.2, 1.5])
    hour_w = hour_w / hour_w.sum()

    def stamp(day_i, rr, drc=False):
        """UTC epoch for a submission on local day Nov 13 + day_i."""
        hw = hour_w.copy()
        if drc:
            hw[:9] = 0
            hw[18:] = 0
            hw /= hw.sum()
        hr = int(rr.choice(24, p=hw))
        base = local_ts(60 + int(day_i), "00:00")
        return base + hr * 3600 + int(rr.integers(0, 3600))

    drc_ips = {"FAC-DRC-040": "192.0.2.61", "FAC-DRC-041": "192.0.2.62", "FAC-DRC-042": "192.0.2.63"}
    apps = []
    used_ids = set(hij) | set(runner["ids"]) | {s["registration_id"] for s in syn}

    def new_id(key):
        k = 0
        while True:
            x = 1000000 + int(h("ia", key, k)[:9], 16) % 8999999
            rid = f"IA-4821-{x}"
            if rid not in used_ids:
                used_ids.add(rid)
                return rid
            k += 1

    def person(rr, lang):
        return f"{FIRST[int(rr.integers(len(FIRST)))]} {LAST[int(rr.integers(len(LAST)))]}"

    recv_masks = {W.acct[x]["account_number_masked"] for x in (A71, A72, A73)}

    def mask4(kind, rid):
        k = 0
        while True:
            m = f"****{int(h(kind, rid, k)[:6], 16) % 10000:04d}" if k else f"****{int(h(kind, rid)[:6], 16) % 10000:04d}"
            if m not in recv_masks:
                return m
            k += 1

    banks = ["BANK-CC-001", "BANK-CC-002", "BANK-CC-004", "BANK-CC-005", "BANK-CC-007", "BANK-CC-008", "BANK-CC-009", "BANK-CC-010", "BANK-CC-006"]

    def ord_bank(drawn, key):
        """An ordinary applicant's bank: all eleven local institutions have customers (the hash decides, so no other field moves)."""
        k = int(h("bank11", key)[:6], 16) % 110
        return "BANK-CC-003" if k < 11 else ("BANK-CC-011" if k < 19 else drawn)

    def unit_style(addr, key):
        """Flats are written the way people write them: Apt 12, Unit 12, #12, Unit B3."""
        if " Apt " not in addr:
            return addr
        head, n = addr.rsplit(" Apt ", 1)
        k = int(h("unit", key)[:6], 16)
        style = k % 10
        if style < 4:
            return addr
        if style < 6:
            return f"{head} Unit {n}"
        if style == 6:
            return f"{head} #{n}"
        return f"{head} Unit {chr(65 + (k >> 8) % 6)}{1 + (k >> 12) % 16}"

    def make_app(i, area_id, tract, zipc, county, t_sub, channel, rr, door=False):
        a = W.area[area_id]
        low = area_id in W.low_income
        lang = "es" if rr.random() < (0.42 if low else 0.17) else ("vi" if rr.random() < 0.01 else "en")
        tenure = "rent" if rr.random() < (0.62 if low else 0.34) else "own"
        roads = W.tract_roads(a)
        addr = f"{int(rr.integers(100, 9800))} {roads[int(rr.integers(len(roads)))]}" + (f" Apt {int(rr.integers(1, 40))}" if tenure == "rent" and rr.random() < 0.5 else "")
        city = {"AREA-CITY-PORTLAND": "Portland", "AREA-CITY-INGLESIDE": "Ingleside", "AREA-CITY-ARANSASPASS": "Aransas Pass",
                "AREA-CITY-GREGORY": "Gregory", "AREA-CITY-TAFT": "Taft", "AREA-CITY-SINTON": "Sinton", "AREA-CITY-ROCKPORT": "Rockport",
                "AREA-CITY-FULTON": "Fulton"}.get(area_id, "Port Aransas" if zipc == "78373" else ("Robstown" if zipc == "78380" else "Corpus Christi"))
        rid = new_id(i)
        zone = a.get("evacuation_zone", "B")
        dmg = str(rr.choice(["destroyed", "major", "minor", "affected"], p={"A": [.1, .38, .37, .15], "B": [.04, .27, .44, .25],
                                                                              "C": [.02, .16, .45, .37], "D": [.01, .1, .4, .49]}[zone]))
        if channel == "web":
            rr.integers(len(ISP_ASN))                      # (draw kept so every other field stays as it was)
            ip, asn = ip_for(("home", rid))
            dev = "dev-" + h("dev", rid)[:12]
        elif channel == "recovery centre":
            k = list(drc_ips)[int(rr.integers(3))]
            ip, asn, dev = drc_ips[k], 64496, f"kiosk-{k[-3:]}-{int(rr.integers(1, 9)):02d}"
        elif channel == "door-to-door":
            ip, asn, dev = "192.0.2.90", 64496, f"tablet-{int(rr.integers(1, 25)):02d}"
        else:
            ip, asn, dev = "", "", ""
        photos = ";".join(f"{h('aidph', rid, k)[:16]}.jpg" for k in range(int(rr.integers(1, 6)))) if channel != "phone" else ""
        bank = ord_bank(banks[int(rr.integers(len(banks)))], rid)
        addr = unit_style(addr, rid)
        return {"application_id": rid, "account_id": "ACC-" + h("acct", rid)[:10].upper(), "t": int(t_sub), "channel": channel, "ip": ip, "asn": asn,
                "dev": dev, "area_id": area_id, "tract": tract, "zip": zipc, "county": county, "name": person(rr, lang),
                "addr": f"{addr}, {city} TX {zipc}", "hh": int(rr.choice([1, 2, 3, 4, 5, 6, 7], p=[.2, .25, .19, .17, .1, .06, .03])),
                "lang": lang, "tenure": tenure, "dmg": dmg, "photos": photos, "routing": W.inst[bank]["routing_number"],
                "masked": mask4("dep", rid), "low": low, "door": door}

    for i, (area_id, tract, zipc, county) in enumerate(plan):
        rr = rng("aidapp", i)
        low = area_id in W.low_income
        channel = str(rr.choice(["web", "phone", "recovery centre"], p=[0.38, 0.27, 0.35] if low else [0.63, 0.2, 0.17]))
        t = stamp(day_idx[i], rr, drc=(channel == "recovery centre"))
        if day_idx[i] == 0 and channel == "web" and rr.random() < 0.03:
            t = OPEN_TS + int(rr.integers(20, 5 * 3600))          # people who stayed up for the midnight opening
        apps.append(make_app(i, area_id, tract, zipc, county, t, channel, rr))
    for j, (area_id, tract, zipc, county) in enumerate(late):
        rr = rng("aidlate", j)
        low = area_id in W.low_income
        if low and rr.random() < 0.88:
            dday = 92 + int(rr.integers(0, 27))
            while (dt.date(2027, 9, 14) + dt.timedelta(days=dday)).weekday() == 6 or dday in (102, 109):   # no canvassing Sundays, Christmas, New Year
                dday += 1
            t = local_ts(min(dday, 119), "09:00") + int(rr.integers(0, 8 * 3600))
            apps.append(make_app(("late", j), area_id, tract, zipc, county, t, "door-to-door", rr, door=True))
        else:
            dday = 90 + int(rr.integers(0, 30))
            ch = str(rr.choice(["web", "phone", "recovery centre"], p=[.5, .25, .25]))
            t = local_ts(min(dday, 119), "00:00") + int(rr.choice(24, p=hour_w)) * 3600 + int(rr.integers(0, 3600))
            if ch == "recovery centre":
                t = local_ts(min(dday, 119), "09:00") + int(rr.integers(0, 9 * 3600))
            apps.append(make_app(("late", j), area_id, tract, zipc, county, t, ch, rr))

    # ---- the 410 registrations whose deposit details are later changed: ordinary early web applications
    web = sorted((a for a in apps if a["channel"] == "web" and a["t"] < OPEN_TS + 2 * DAY + 12 * 3600 and not a["low"]),
                 key=lambda a: h("hij", a["application_id"]))
    assert len(web) >= 410, len(web)
    for a, rid in zip(web[:410], hij):
        used_ids.discard(a["application_id"])
        a["application_id"], a["account_id"] = rid, "ACC-" + h("acct", rid)[:10].upper()
        a["hijacked"] = True
    # ---- 94 applications in three night bursts from one address (ZIP 78407)
    lph_addr = sorted({W.pol[p]["property_address"] for p in W.lph if "78407" in W.pol[p]["property_address"] or "78408" in W.pol[p]["property_address"]})
    if len(lph_addr) < 30:
        lph_addr = sorted({W.pol[p]["property_address"] for p in W.lph})
    photos23 = [f"{h('ringph', k)[:16]}.jpg" for k in range(1, 24)]        # the same two dozen pictures, uploaded again and again
    P14 = photos23[13]
    # the first burst starts a minute after the midnight opening (00:01-03:17 Central = 06:01-09:17Z)
    bursts = [(ts_("2027-11-13T06:01:00"), ts_("2027-11-13T09:17:00"), 31), (ts_("2027-11-14T01:00:00"), ts_("2027-11-14T04:45:00"), 29),
              (ts_("2027-11-15T23:00:00"), ts_("2027-11-15T23:59:00"), 34)]
    rr = rng("runner")
    k = 0
    photo_use = defaultdict(int)
    for b0, b1, n in bursts:
        times = sorted(int(x) for x in rr.integers(b0, b1 + 1, size=n))
        times[0], times[-1] = b0 + 3 + int(h("bsec", b0)[:4], 16) % 50, b1 + 3 + int(h("bsec", b1)[:4], 16) % 50      # inside the first and the last minute
        for t in times:
            rid = runner["ids"][k]
            base = lph_addr[k % len(lph_addr)].split(",")[0]
            ph = []
            if photo_use[P14] < 7 and k % 13 == 0:
                ph.append(P14)
            while len(ph) < 2 + k % 3:
                c = photos23[int(rr.integers(23))]
                if c == P14 or c in ph:
                    continue
                ph.append(c)
            for c in ph:
                photo_use[c] += 1
            bank = banks[int(rr.integers(len(banks)))]
            apps.append({"application_id": rid, "account_id": "ACC-" + h("acct", rid)[:10].upper(), "t": t, "channel": "web", "ip": "198.51.100.44",
                         "asn": 64500, "dev": "dev-" + h("lphdev", k % 3)[:12], "area_id": "AREA-TRACT-480401", "tract": "480401", "zip": "78407",
                         "county": "Nueces", "name": person(rr, "en"), "addr": f"{base} Unit {chr(65 + k % 6)}{1 + k // 6}, Corpus Christi TX 78407",
                         "hh": int(rr.integers(1, 6)), "lang": "en", "tenure": "rent", "dmg": "major", "photos": ";".join(ph),
                         "routing": W.inst[bank]["routing_number"], "masked": mask4("dep", rid), "low": False,
                         "door": False, "runner": True})
            k += 1
    # make sure all 23 photos occur and one of them seven times
    seven = [a for a in apps if a.get("runner") and P14 in a["photos"]]
    extra = [a for a in apps if a.get("runner") and P14 not in a["photos"]]
    for a in extra[: max(0, 7 - len(seven))]:
        a["photos"] = "CC-DAM-0014.jpg;" + a["photos"]
    used = set(p for a in apps if a.get("runner") for p in a["photos"].split(";"))
    missing = [p for p in photos23 if p not in used]
    for a, p in zip([a for a in apps if a.get("runner")][::-1], missing):
        a["photos"] += ";" + p
    # ---- six invented applicants tied to the receiving accounts
    rr = rng("synid")
    recv = [(A71, "BANK-CC-003"), (A72, "BANK-CC-003"), (A73, "BANK-CC-011")]
    shared_dev = ["dev-" + h("syn-dev", 0)[:12], "dev-" + h("syn-dev", 1)[:12]]
    shared_addr = ["4520 Agnes St Suite 210, Corpus Christi TX 78405", "1127 Leopard St Apt 4, Corpus Christi TX 78401"]
    for k, s in enumerate(syn):
        acct_id, bank = recv[k % 3]
        t = OPEN_TS + int((1.5 + k * 0.9) * DAY) + int(rr.integers(0, 6 * 3600))
        apps.append({"application_id": s["registration_id"], "account_id": "ACC-" + h("acct", s["registration_id"])[:10].upper(), "t": t,
                     "channel": "web", "ip": netmap.story_ip(21 + k % 2), "asn": HIJACK_ASN, "dev": shared_dev[k % 2], "area_id": "AREA-TRACT-481201",
                     "tract": "481201", "zip": "78405", "county": "Nueces", "name": s["name"], "addr": shared_addr[k % 2], "hh": 4 + k % 2,
                     "lang": "en", "tenure": "own", "dmg": "destroyed", "photos": ";".join(f"{h('synph', k % 2, j)[:16]}.jpg" for j in range(3)),
                     "routing": W.inst[bank]["routing_number"], "masked": W.acct[acct_id]["account_number_masked"], "low": False, "door": False,
                     "synthetic": True, "recv": acct_id})

    apps.sort(key=lambda a: (a["t"], a["application_id"]))
    rows, disb = [], []
    rec = [0]

    def emit(a, rtype, t, **kw):
        rec[0] += 1
        d = {k: "" for k in AID_HEADER}
        d.update({"record_id": f"AR-{rec[0]:07d}", "record_type": rtype, "application_id": a["application_id"], "account_id": a["account_id"],
                  "event_utc": iso(t), "area_id": a["area_id"], "tract": a["tract"], "zip": a["zip"], "county": a["county"]})
        d.update(kw)
        d["_t"] = t
        rows.append(d)

    # ---- determinations and payments
    hij_amounts = {}
    rr = rng("hij-amt")
    raw = {a["application_id"]: float(np.exp(rr.normal(9.05, 0.45))) for a in apps if a.get("hijacked") or a.get("synthetic")}
    kscale = 3_900_000 / sum(raw.values())
    hij_amounts = {k: round(min(v * kscale, 42500.0), 2) for k, v in raw.items()}
    # top up after the cap so the total stays on the canon figure
    short = 3_900_000 - sum(hij_amounts.values())
    for k in sorted(hij_amounts):
        if short <= 0:
            break
        add = min(short, 42500.0 - hij_amounts[k], 1500.0)
        hij_amounts[k] = round(hij_amounts[k] + add, 2)
        short -= add
    recv_cycle = [A71, A71, A72, A73, A71, A72, A73, A71, A72, A71, A73, A72]
    hk = 0
    for a in apps:
        rr = rng("aiddet", a["application_id"])
        emit(a, "application", a["t"], submitted_utc=iso(a["t"]), channel=a["channel"], source_ip=a["ip"], source_asn=a["asn"], device_id=a["dev"],
             applicant_name=a["name"], damaged_address=a["addr"], household_size=a["hh"], primary_language=a["lang"], tenure=a["tenure"],
             self_reported_damage=a["dmg"], damage_photo_hashes=a["photos"], deposit_routing_number=a["routing"], deposit_account_masked=a["masked"],
             status="registered")
        special = a.get("hijacked") or a.get("synthetic")
        low = a["low"]
        # inspection and decision; slower and more often incomplete where documents and access are hard
        wait = int(rr.integers(4, 13)) + (int(rr.integers(4, 14)) if low else 0)
        if a.get("synthetic"):
            wait = int(rr.integers(2, 5))
        t_dec = a["t"] + wait * DAY + int(rr.integers(0, 8 * 3600))
        rf = rng("aidflag", a["application_id"])
        if a.get("runner"):
            # the first review catches most of the burst; a second pass two weeks later catches more; some are never held
            u = rf.random()
            if u < 0.55:
                t_flag = ts_("2027-11-16T15:00:00") + int(rf.choice([0, 0, 0, 1, 1, 2])) * DAY + int(rf.integers(0, 8 * 3600))
            elif u < 0.72:
                t_flag = ts_("2027-12-01T15:00:00") + int(rf.integers(0, 2 * DAY))
            else:
                t_flag = None
            if t_flag is None or u >= 0.55:
                emit(a, "determination", a["t"] + int(rf.integers(5, 11)) * DAY + int(rf.integers(0, 8 * 3600)), status="pending, documents requested")
            if t_flag is not None:
                # reviewers file a hold under whichever open case they are working; these cases also hold unrelated files
                case_r = int(rf.choice([4471, 4471, 4471, 4437, 4404, 4465])) if u < 0.55 else int(rf.choice([4471, 4522, 4459]))
                emit(a, "determination", t_flag, status=f"held, suspicious-activity flag SA-2027-TX-{case_r}", assistance_type="")
            continue
        # everyday holds: duplicate registrations from one household, identity or address mismatches, the same bank account on several files.
        # Case numbers group the files a reviewer opened together; most are released after verification.
        if not special and rf.random() < (0.031 if not low else 0.044):
            case = 4400 + (int(h("aidcase", a["tract"], day_of(a["t"]) // 4)[:6], 16) % 140)
            t_hold = a["t"] + int(rf.integers(1, 7)) * DAY + int(rf.integers(13 * 3600, 22 * 3600))
            if t_hold < SPAN_END - 6 * 3600:
                emit(a, "determination", t_hold, status=f"held, suspicious-activity flag SA-2027-TX-{case}", assistance_type="")
                if rf.random() < 0.3:
                    continue                                   # still held at the end of the record
                t_dec = max(t_dec, t_hold + int(rf.integers(6, 21)) * DAY)
        if t_dec > SPAN_END - 6 * 3600:
            continue
        p_app = 0.71
        if low:
            p_app = 0.47
        if a["door"]:
            p_app = 0.8
        if a["dmg"] == "affected":
            p_app -= 0.25
        u = rr.random()
        if special or u < p_app:
            med = {"destroyed": 9.75, "major": 9.0, "minor": 7.95, "affected": 7.0}[a["dmg"]] - (0.42 if a["tenure"] == "rent" else 0.0)
            if low and not a["door"]:
                med -= 0.3        # ownership papers and inspections are harder to complete: smaller first awards
            amt = round(float(np.clip(np.exp(rr.normal(med, 0.5)), 300, 42500)), 2)
            if special:
                amt = hij_amounts[a["application_id"]]
            atype = "housing assistance" if a["tenure"] == "own" and a["dmg"] in ("destroyed", "major") else str(rr.choice(["rental assistance", "other needs assistance", "home repair"]))
            emit(a, "determination", t_dec, assistance_type=atype, amount_usd=money(amt), status="approved")
            a["approved"], a["t_dec"], a["atype"] = amt, t_dec, atype
        elif u < p_app + (0.3 if low else 0.17):
            emit(a, "determination", t_dec, status=str(rr.choice(["ineligible, ownership or occupancy not verified", "ineligible, insufficient documentation",
                                                                    "ineligible, insured loss", "ineligible, inspection could not be completed",
                                                                    "ineligible, damage not disaster-related"], p=[.3, .28, .2, .14, .08])))
        else:
            emit(a, "determination", t_dec, status="pending, documents requested")

    # ---- account changes: ordinary ones, and the 410 after a login from an address not seen before
    stuff0, stuff1 = ts_("2027-11-15T18:00:00"), ts_("2027-11-23T22:00:00")
    proxies = list(netmap.STORY_POOL)
    rr = rng("hijack")
    hij_apps = [a for a in apps if a.get("hijacked")]
    # successes come in the same bursts as the login floods: evenings and nights local time
    burst_starts = [stuff0 + int(x) for x in sorted(rr.integers(0, stuff1 - stuff0 - 3 * 3600, size=22))]
    for i, a in enumerate(sorted(hij_apps, key=lambda a: h("ho", a["application_id"]))):
        b = burst_starts[i % len(burst_starts)]
        t_login = b + int(rr.integers(0, 150 * 60))
        t_change = t_login + int(rr.integers(90, 1500))
        acct_id = recv_cycle[i % len(recv_cycle)]
        bank = W.acct[acct_id]["institution_id"]
        emit(a, "account_change", t_change, changed_utc=iso(t_change), channel="web", source_ip=proxies[int(rr.integers(len(proxies)))],
             source_asn=HIJACK_ASN, device_id="dev-" + h("hjdev", int(rr.integers(0, 9)))[:12], field_changed="direct deposit",
             login_utc=iso(t_login), login_ip_seen_before="N", deposit_routing_number=W.inst[bank]["routing_number"],
             deposit_account_masked=W.acct[acct_id]["account_number_masked"], previous_deposit_account_masked=a["masked"], status="accepted")
        a["recv"], a["t_change"], a["orig_masked"], a["orig_routing"] = acct_id, t_change, a["masked"], a["routing"]
    # ordinary changes (new bank, corrected typo, new phone), mostly from the address used before
    rr = rng("ordchange")
    normal = [a for a in apps if not a.get("hijacked") and not a.get("synthetic") and not a.get("runner") and a["channel"] in ("web", "phone", "recovery centre")]
    for a in normal:
        if rr.random() < 0.034:
            t = a["t"] + int(rr.integers(1, 30)) * DAY + int(rr.integers(13 * 3600, 26 * 3600))
            if t > SPAN_END - 3600:
                continue
            field = str(rr.choice(["direct deposit", "phone number", "mailing address", "email address"], p=[.33, .3, .22, .15]))
            same = rr.random() < 0.82 and a["channel"] == "web"
            other_ip, other_asn = ip_for(("chg", a["application_id"]))
            ip = a["ip"] if same else (other_ip if a["channel"] != "phone" or rr.random() < 0.6 else "")
            newmask = mask4("dep2", a["application_id"]) if field == "direct deposit" else ""
            bank = ord_bank(banks[int(rr.integers(len(banks)))], ("chg", a["application_id"]))
            emit(a, "account_change", t, changed_utc=iso(t), channel="web" if ip else "phone", source_ip=ip,
                 source_asn=(a["asn"] if same else (other_asn, rr.integers(len(ISP_ASN)))[0]) if ip else "",
                 device_id=(a["dev"] if same else "dev-" + h("chgdev", a["application_id"])[:12]) if ip else "", field_changed=field,
                 login_utc=iso(t - int(rr.integers(60, 900))) if ip else "", login_ip_seen_before=("Y" if same else "N") if ip else "",
                 deposit_routing_number=W.inst[bank]["routing_number"] if newmask else "", deposit_account_masked=newmask,
                 previous_deposit_account_masked=a["masked"] if newmask else "", status="accepted")
            if newmask and a.get("approved") and t < a["t_dec"]:
                a["masked"], a["routing"] = newmask, W.inst[bank]["routing_number"]

    # ---- disbursements
    for a in apps:
        if not a.get("approved"):
            continue
        rr = rng("aidpay", a["application_id"])
        t_pay = a["t_dec"] + int(rr.integers(2, 6)) * DAY
        t_pay = local_ts(day_of(t_pay), "06:00") + int(rr.integers(0, 3 * 3600))
        while not business_days(day_of(t_pay)):
            t_pay += DAY
        if a.get("hijacked"):
            # paid after the change, between Nov. 17 and Dec. 3
            lo = max(a["t_change"] + 6 * 3600, local_ts(64, "06:00"))
            t_pay = max(t_pay, lo)
            t_pay = local_ts(day_of(t_pay), "06:00") + int(rr.integers(0, 3 * 3600))
            while not business_days(day_of(t_pay)):
                t_pay += DAY
            if day_of(t_pay) > 80:
                t_pay = local_ts(80 - int(rr.integers(0, 3)), "06:00") + int(rr.integers(0, 3 * 3600))
                while not business_days(day_of(t_pay)):
                    t_pay -= DAY
            bank = W.acct[a["recv"]]["institution_id"]
            emit(a, "disbursement", t_pay, assistance_type=a["atype"], amount_usd=money(a["approved"]), deposit_routing_number=W.inst[bank]["routing_number"],
                 deposit_account_masked=W.acct[a["recv"]]["account_number_masked"], status="paid")
            disb.append({"application_id": a["application_id"], "t": t_pay, "amount": a["approved"], "account": a["recv"]})
            # reissued to the applicant's original account once the takeover was confirmed
            t_re = local_ts(72 + int(rr.integers(0, 14)), "06:00") + int(rr.integers(0, 3 * 3600))
            while not business_days(day_of(t_re)):
                t_re += DAY
            emit(a, "account_change", t_re - 2 * DAY, changed_utc=iso(t_re - 2 * DAY), channel="agency", field_changed="direct deposit restored after identity verification",
                 deposit_routing_number=a["orig_routing"], deposit_account_masked=a["orig_masked"],
                 previous_deposit_account_masked=W.acct[a["recv"]]["account_number_masked"], status="accepted")
            emit(a, "disbursement", t_re, assistance_type=a["atype"], amount_usd=money(a["approved"]), deposit_routing_number=a["orig_routing"],
                 deposit_account_masked=a["orig_masked"], status="reissued")
        elif a.get("synthetic"):
            t_pay = max(t_pay, local_ts(64, "06:00") + int(rr.integers(0, 3 * 3600)))
            while not business_days(day_of(t_pay)):
                t_pay += DAY
            emit(a, "disbursement", t_pay, assistance_type=a["atype"], amount_usd=money(a["approved"]), deposit_routing_number=a["routing"],
                 deposit_account_masked=a["masked"], status="paid")
            disb.append({"application_id": a["application_id"], "t": t_pay, "amount": a["approved"], "account": a["recv"]})
        elif t_pay < SPAN_END - 3600:
            emit(a, "disbursement", t_pay, assistance_type=a["atype"], amount_usd=money(a["approved"]), deposit_routing_number=a["routing"],
                 deposit_account_masked=a["masked"], status="paid")

    # payments that bounce (closed or mistyped account) are corrected by a caseworker and reissued; this happens every week of any programme
    for a in apps:
        if not a.get("approved") or a.get("hijacked") or a.get("synthetic"):
            continue
        rr = rng("aidbounce", a["application_id"])
        if rr.random() < 0.016:
            t_pay = a["t_dec"] + int(rr.integers(2, 6)) * DAY
            t_fix = t_pay + int(rr.integers(4, 15)) * DAY
            t_fix = local_ts(day_of(t_fix), "08:00") + int(rr.integers(0, 8 * 3600))
            if t_fix + 3 * DAY > SPAN_END - 3600:
                continue
            bank = banks[int(rr.integers(len(banks)))]
            newmask = mask4("dep3", a["application_id"])
            verified = rr.random() < 0.45
            emit(a, "account_change", t_fix, changed_utc=iso(t_fix), channel="agency",
                 field_changed="direct deposit restored after identity verification" if verified else "direct deposit",
                 deposit_routing_number=a["routing"] if verified else W.inst[bank]["routing_number"],
                 deposit_account_masked=a["masked"] if verified else newmask, previous_deposit_account_masked=a["masked"], status="accepted")
            t_re = local_ts(day_of(t_fix) + int(rr.integers(1, 4)), "06:00") + int(rr.integers(0, 3 * 3600))
            while not business_days(day_of(t_re)):
                t_re += DAY
            if t_re < SPAN_END - 3600:
                emit(a, "disbursement", t_re, assistance_type=a["atype"], amount_usd=money(a["approved"]),
                     deposit_routing_number=a["routing"] if verified else W.inst[bank]["routing_number"],
                     deposit_account_masked=a["masked"] if verified else newmask, status="reissued")

    rows.sort(key=lambda d: (d["_t"], d["record_id"]))
    for i, d in enumerate(rows):
        d["record_id"] = f"AR-{i + 1:07d}"
    n = write_csv(P + "aid_applications.csv", AID_HEADER, [[d[k] for k in AID_HEADER] for d in rows])
    by89 = sum(1 for a in apps if a["t"] < local_ts(90, "00:00"))
    print(f"aid_applications: {n} rows; applications {len(apps)} ({by89} by Dec. 12), hijacked {len(hij_apps)}, "
          f"diverted ${sum(x['amount'] for x in disb):,.0f} in {len(disb)} payments")
    return disb


def ts_(s):
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())


# ======================================================================================
# financial transactions (ledger of registry accounts)
# ======================================================================================
FT_HEADER = ["transaction_id", "timestamp", "account_id", "institution_id", "direction", "amount_usd", "channel", "counterparty_id",
             "counterparty_name", "counterparty_account_masked", "merchant_city", "description", "reference", "balance_after_usd"]
# Houston is just under 300 km from Corpus Christi, so the Houston outlets are not part of the cluster
CITY_FAR = {"MER-001", "MER-002", "MER-003", "MER-004", "MER-005", "MER-006", "MER-007", "MER-008", "MER-009"}


def build_ledger(W, invoices, claim_payments, disb):
    er = W.er
    tx = []

    def add(t, account, direction, amount, channel, cp_id="", cp_name="", cp_mask="", city="", desc="", ref=""):
        if amount <= 0 or t < SPAN0 or t >= SPAN_END:
            return
        tx.append([int(t), account, direction, round(float(amount), 2), channel, cp_id, cp_name, cp_mask, city, desc, ref])

    def bank_time(day, rr, lo=8, hi=17):
        return local_ts(day, "00:00") + int(rr.integers(lo * 3600, hi * 3600))

    owner = {}
    for v in er["vendors"]:
        owner.setdefault(v["remit_account_id"], v)
    special = {A71, A72, A73}
    merchants = {m["merchant_id"]: m for m in er["prepaid_card_merchants"]}

    # ---- ordinary business accounts
    for acct_id, v in sorted(owner.items()):
        if acct_id in special:
            continue
        rr = rng("ledger", acct_id)
        bt = v["business_type"]
        storm_trade = bool(re.search(r"Roof|ebris|Tree|Haul|Generator|sanitation|Water damage|Plumb|Electric|Fenc|Equipment|HVAC|contractor|salvage|restoration", bt))
        retail = bool(re.search(r"Catering|Bottled|tax|Title", bt))
        base_rev = float(np.exp(rr.normal(8.2, 0.5)))                 # typical daily takings
        staffn = int(rr.integers(3, 28))
        opened = W.acct[acct_id]["opened"]
        shell = v["vendor_id"] in ("VND-0003", "VND-0004")
        for day in range(-30, 120):
            if d2s(day) < opened or d2s(day) < v["registration_date"]:
                continue
            wd = (dt.date(2027, 9, 14) + dt.timedelta(days=day)).weekday()
            if closed(day) or (day in (-1, 4) and rr.random() < 0.6):
                continue
            boom = 1.0
            if storm_trade and day > 3:
                boom = 1.0 + 2.2 * math.exp(-max(0, day - 20) / 45.0)
            elif day > 3 and day < 40:
                boom = 0.7
            if shell and day < 3:
                boom = 0.05
            if wd < 6:
                ncred = rr.poisson((2.2 if retail else 1.3) * (0.4 if wd == 5 else 1.0) * min(boom, 2.2))
                for _ in range(int(ncred)):
                    amt = float(np.exp(rr.normal(math.log(base_rev * boom / 1.6), 0.8)))
                    ch = str(rr.choice(["card settlement", "ACH credit", "check deposit", "cash deposit"], p=[.42, .28, .22, .08]))
                    name = {"card settlement": "Merchant card services batch", "cash deposit": "Branch deposit"}.get(ch, f"{LAST[int(rr.integers(len(LAST)))]} {str(rr.choice(['household', 'Properties', 'family', 'Rentals', 'residence']))}")
                    add(bank_time(day, rr, 7, 19), acct_id, "credit", amt, ch, "", name, f"****{int(rr.integers(0, 10000)):04d}" if ch != "cash deposit" and ch != "card settlement" else "",
                        "", "customer payment" if ch != "card settlement" else "card sales settlement")
            if wd < 5:
                for _ in range(int(rr.poisson(0.9 * min(boom, 2.0)))):
                    amt = float(np.exp(rr.normal(math.log(base_rev * 0.55), 0.9)))
                    what = str(rr.choice(["materials supplier", "fuel card", "equipment rental", "insurance premium", "vehicle loan", "subcontractor",
                                          "rent", "telephone and internet", "office supplies"]))
                    add(bank_time(day, rr), acct_id, "debit", amt, "card purchase" if what in ("fuel card", "office supplies") else "ACH debit", "",
                        what.capitalize(), "", "Corpus Christi, TX" if what in ("fuel card", "office supplies") else "", what)
                if wd == 4 and ((dt.date(2027, 9, 14) + dt.timedelta(days=day)).isocalendar()[1] % 2 == 0):
                    add(local_ts(day, "06:00") + int(rr.integers(0, 1800)), acct_id, "debit", staffn * float(rr.uniform(1350, 2100)) * min(boom, 1.6),
                        "ACH debit", "", "Payroll service", "", "", "payroll, biweekly")
                if (dt.date(2027, 9, 14) + dt.timedelta(days=day)).day == 15:
                    add(local_ts(day, "06:00") + int(rr.integers(0, 1800)), acct_id, "debit", float(rr.uniform(180, 900)), "ACH debit", W.org("Coastal Bend Power and Water Authority"),
                        "Coastal Bend Power and Water Authority", "", "", "electric and water service")
                if rr.random() < 0.004:
                    m = merchants[str(rr.choice(["MER-012", "MER-013", "MER-014", "MER-010", "MER-011"]))]
                    add(bank_time(day, rr, 10, 20), acct_id, "debit", float(rr.choice([100, 200, 250, 500])), "card purchase", m["merchant_id"], m["name"], "",
                        m["city"], "prepaid gift cards, staff incentives")

    # ---- contract and purchase-order payments
    for inv in invoices:
        if inv["paid_day"] is None:
            continue
        rr = rng("ledger-inv", inv["invoice_id"])
        t = local_ts(inv["paid_day"], "06:00") + int(rr.integers(0, 2 * 3600))
        add(t, inv["remit_bank_account_id"], "credit", inv["amount_usd"], "ACH credit" if inv["amount_usd"] < 250000 else "wire in",
            inv["buyer_org_id"], inv["buyer"], f"****{int(h('payer', inv['buyer'])[:6], 16) % 10000:04d}", "", f"vendor payment {inv['invoice_id']}", inv["payment_reference"])

    # ---- insurance claim payments out of the insurers' disbursement accounts
    lph_received = []
    for p in claim_payments:
        rr = rng("ledger-claim", p["claim_id"])
        t = local_ts(p["day"], "06:00") + int(rr.integers(0, 3 * 3600))
        mask = f"****{int(h('ph-acct', p['holder_id'])[:6], 16) % 10000:04d}"
        add(t, p["account"], "debit", p["amount"], "ACH debit", "", p["payee"], mask, "", "claim payment", p["claim_id"])
        if p["lph"]:
            lph_received.append((t, p["amount"], p["claim_id"]))
    # the property company passes repair money to two contractors, which cash out through exchanges
    rr = rng("lph-flow")
    pool = defaultdict(float)
    for t, amt, cid in sorted(lph_received):
        vend = "VND-0004" if rr.random() < 0.62 else "VND-0003"
        acct = W.vend[vend]["remit_account_id"]
        share = amt * float(rr.uniform(0.55, 0.8))
        t2 = t + int(rr.integers(1, 4)) * DAY + int(rr.integers(0, 6 * 3600))
        add(t2, acct, "credit", share, "wire in", W.org("Landmark Pacific Holdings LLC"), "Landmark Pacific Holdings LLC", "****4411", "", "repair contract progress payment", cid)
        pool[(acct, day_of(t2) // 6)] += share
    crypto = {W.vend["VND-0004"]["remit_account_id"]: "CRYPTO-01", W.vend["VND-0003"]["remit_account_id"]: "CRYPTO-02"}
    ends = {e["endpoint_id"]: e for e in er["crypto_endpoints"]}
    for (acct, wk), amt in sorted(pool.items()):
        t = local_ts(wk * 6 + 6, "00:00") + int(rr.integers(9 * 3600, 16 * 3600))
        add(t, acct, "debit", amt * float(rr.uniform(0.7, 0.88)), "wire out", crypto[acct], "Digital asset exchange, customer transfer",
            ends[crypto[acct]]["wallet_address"][:10] + "...", "", "transfer to exchange account", "")
    # ordinary accounts use the other two endpoints now and then
    rr = rng("crypto-cover")
    ord_accts = sorted(a for a in owner if a not in special and a not in crypto)
    for _ in range(46):
        acct = str(rr.choice(ord_accts))
        e = "CRYPTO-03" if rr.random() < 0.5 else "CRYPTO-04"
        add(local_ts(int(rr.integers(-28, 118)), "00:00") + int(rr.integers(9 * 3600, 20 * 3600)), acct, "debit", float(rr.choice([250, 500, 1000, 1500, 2500, 4000])),
            "wire out", e, "Digital asset exchange, customer transfer", ends[e]["wallet_address"][:10] + "...", "", "transfer to exchange account", "")

    # ---- the three receiving accounts
    rr = rng("recv")
    # opening deposits and thin activity before the storm
    for acct, day in ((A71, -40), (A72, -40), (A73, -32)):
        add(local_ts(max(day, -30), "15:10") + int(rr.integers(0, 3600)), acct, "credit", float(rr.choice([2500, 5000, 7500])), "wire in", "", "Foreign correspondent bank, originator not stated",
            "****8841", "", "opening funds", "")
    for day in range(-28, 10, 7):
        add(local_ts(day, "11:00") + int(rr.integers(0, 7200)), A71, "debit", float(rr.uniform(120, 480)), "ACH debit", "", "Office suite rental", "", "", "rent, 4520 Agnes St Suite 210")
    # diverted aid payments
    for d in disb:
        add(d["t"], d["account"], "credit", d["amount"], "ACH credit", W.org("Federal Emergency Management Agency"), "U.S. Treasury, Bureau of the Fiscal Service: FEMA disaster assistance",
            W.inst["BANK-US-TREAS"]["routing_number"][-4:].rjust(8, "*"), "", "disaster assistance payment", d["application_id"])
    # sweeps: aid money moves to the third account, contract money leaves the country
    credits = defaultdict(float)
    for row in tx:
        if row[1] in (A71, A72) and row[2] == "credit":
            credits[(row[1], day_of(row[0]), row[9] == "disaster assistance payment")] += row[3]
    for (acct, day, is_aid), amt in sorted(credits.items()):
        if amt < 3000:
            continue
        t = local_ts(day + 1, "09:00") + int(rr.integers(0, 5 * 3600))
        while not business_days(day_of(t)):
            t += DAY
        if is_aid:
            to73 = amt * float(rr.uniform(0.62, 0.82))
            add(t, acct, "debit", to73, "wire out", A73, "Account ending 3176, Prairie Commerce Bank", W.acct[A73]["account_number_masked"], "", "transfer", "")
            add(t + int(rr.integers(600, 5400)), A73, "credit", to73, "wire in", acct, f"Account ending {W.acct[acct]['account_number_masked'][-4:]}, Bay Area Savings & Loan",
                W.acct[acct]["account_number_masked"], "", "transfer", "")
        else:
            add(t + int(rr.integers(3600, 9000)), acct, "debit", amt * float(rr.uniform(0.72, 0.9)), "wire out", "", "Foreign correspondent bank, beneficiary account ending 8841",
                "****8841", "", "international wire", "")
    # prepaid-card purchases from the out-of-state account, Nov. 19 to Dec. 3, far from Corpus Christi
    far = sorted(CITY_FAR)
    avail = sum(r[3] for r in tx if r[1] == A73 and r[2] == "credit")
    spent, k = 0.0, 0
    target = avail * 0.86
    while spent < target and k < 5000:
        day = 66 + int(rr.integers(0, 15))
        m = merchants[far[int(rr.integers(len(far)))]]
        amt = float(rr.choice([500, 1000, 1000, 1500, 2000, 2000, 2500, 3000])) + float(rr.choice([0, 4.95, 5.95, 9.9]))
        t = local_ts(day, "00:00") + int(rr.integers(9 * 3600, 22 * 3600))
        add(t, A73, "debit", amt, "card purchase", m["merchant_id"], m["name"], "", m["city"], "prepaid cards", "")
        spent += amt
        k += 1

    # ---- write, with running balances
    tx.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
    bal = {}
    for a in er["accounts"]:
        rr = rng("openbal", a["account_id"])
        bal[a["account_id"]] = 0.0 if a["account_id"] in special else (float(rr.uniform(4e6, 3e7)) if a["account_type"].startswith("claims") else float(np.exp(rr.normal(10.6, 0.7))))
    # overdrafts are not allowed: top up from the owner when an ordinary account would go negative
    out = []
    for i, r in enumerate(tx):
        acct = r[1]
        b = bal[acct] + (r[3] if r[2] == "credit" else -r[3])
        if b < 0 and acct not in special:
            topup = round(-b + float(rng("topup", i).uniform(2000, 15000)), 2)
            if W.acct[acct]["account_type"].startswith("claims"):
                topup = round(-b + 2.5e7, 2)
            out.append([r[0] - 60, acct, "credit", topup, "internal transfer", "", "Transfer from operating reserve", "", "", "funding transfer", ""])
            bal[acct] += topup
            out[-1].append(round(bal[acct], 2))
            b = bal[acct] - r[3]
        elif b < 0:
            continue                                              # a shell account cannot spend what it does not have
        bal[acct] = b
        out.append(r + [round(b, 2)])
    out.sort(key=lambda r: (r[0], r[1]))
    rows = [[f"FT-{i + 1:07d}", iso(r[0]), r[1], W.acct[r[1]]["institution_id"], r[2], money(r[3]), r[4], r[5], r[6], r[7], r[8], r[9], r[10], money(r[11])]
            for i, r in enumerate(out)]
    n = write_csv(P + "financial_transactions.csv", FT_HEADER, rows)
    aid_in = sum(r[3] for r in out if r[1] in special and r[9] == "disaster assistance payment")
    prepaid = sum(r[3] for r in out if r[1] == A73 and r[9] == "prepaid cards")
    print(f"financial_transactions: {n} rows; aid into the three accounts ${aid_in:,.0f}; prepaid-card purchases ${prepaid:,.0f}")


def main():
    retire_once([P + "financial_transactions.csv", P + "insurance_claims.csv"])
    W = World()
    invoices = build_contracts(W)
    claim_payments, by30 = build_claims(W)
    disb = build_aid(W)
    build_ledger(W, invoices, claim_payments, disb)


if __name__ == "__main__":
    main()
