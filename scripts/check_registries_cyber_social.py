"""Checks for the cyber, social, financial and organisation registries.

    python scripts/check_registries_cyber_social.py      exit 1 on any failure

Covers gw_host_registry.json, scada_tags.json, personas.json, organizations.json,
entity_registry.json, their _internal truth files, and schemas 03, 04, 10, 13 and the index.
"""
import ipaddress
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = os.path.join(ROOT, "06_data_streams")
INT = os.path.join(DS, "_internal")
fails, notes = [], []


def load(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return json.load(fh)


def text(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def check(ok, msg):
    if not ok:
        fails.append(msg)
    return ok


def unique(items, label):
    c = Counter(items)
    d = [k for k, n in c.items() if n > 1]
    check(not d, f"{label}: duplicate ids {d[:6]}")


H, T, P, O, E = (load(DS, f) for f in ("gw_host_registry.json", "scada_tags.json", "personas.json", "organizations.json", "entity_registry.json"))
HT, TT, PT, OT, ET = (load(INT, f) for f in ("gw_host_registry_truth.json", "scada_tags_truth.json", "personas_truth.json", "organizations_truth.json", "entity_registry_truth.json"))
PUBLIC_FILES = ["gw_host_registry.json", "scada_tags.json", "personas.json", "organizations.json", "entity_registry.json",
                "schemas/03_scada_telemetry_schema.json", "schemas/04_social_media_schema.json", "schemas/10_network_logs_schema.json",
                "schemas/13_payments_schema.json", "schemas/00_schema_index.json", "entity_catalogs/README.md"]

# ---------------------------------------------------------------- 1. unique ids
unique([h["hostname"] for h in H["hosts"]], "hosts.hostname")
unique([h["ip"] for h in H["hosts"]], "hosts.ip")
unique([u["username"] for u in H["users"]] + [a["account"] for a in H["service_accounts"]], "accounts")
unique([u["ot_account"] for u in H["users"] if u.get("ot_account")], "ot accounts")
unique([e["equipment_id"] for e in H["equipment"]], "equipment")
unique([t["tagname"] for t in T["tags"]], "tags")
unique([a["alarm_id"] for a in T["alarm_points"]], "alarm points")
unique([p["persona_id"] for p in P["personas"]], "persona ids")
unique([p["handle"].lower() for p in P["personas"]] + [r[0].lower() for r in P["accounts_compact"]["rows"]], "handles")
unique([o["org_id"] for o in O["organizations"]], "org ids")
unique([o["name"] for o in O["organizations"]], "org names")
for key, idf in (("insurers", "insurer_id"), ("brokers", "broker_id"), ("appraisers", "appraiser_id"), ("adjusting_firms", "firm_id"), ("adjusters", "adjuster_id"),
                 ("vendors", "vendor_id"), ("contracts", "contract_id"), ("financial_institutions", "institution_id"), ("accounts", "account_id"),
                 ("policyholders", "holder_id"), ("policies", "policy_number"), ("prepaid_card_merchants", "merchant_id"), ("crypto_endpoints", "endpoint_id")):
    unique([x[idf] for x in E[key]], f"entity_registry.{key}")
unique([v["uei"] for v in E["vendors"]], "vendor UEI")

# ---------------------------------------------------------------- 2. internal references
zones = {z["zone"]: ipaddress.ip_network(z["cidr"]) for z in H["network_zones"]}
hostnames = {h["hostname"] for h in H["hosts"]}
for h in H["hosts"]:
    check(h["zone"] in zones and ipaddress.ip_address(h["ip"]) in zones[h["zone"]], f"host {h['hostname']} ip {h['ip']} not in zone {h['zone']}")
sites = {s["site_id"] for s in H["sites"]}
check(all(h["site_id"] in sites or h["site_id"].startswith("GW-FAC-") for h in H["hosts"]), "host with unknown site")
for u in H["users"]:
    check(set(u["normal_hosts"]) <= hostnames, f"user {u['username']} has unknown normal host")
for a in H["service_accounts"]:
    check(set(a["normal_hosts"]) <= hostnames, f"service account {a['account']} has unknown host")
equip = {e["equipment_id"] for e in H["equipment"]}
for e in H["equipment"]:
    check(e["served_by"] in hostnames, f"equipment {e['equipment_id']} served by unknown host {e['served_by']}")
tagnames = {t["tagname"] for t in T["tags"]}
for t in T["tags"]:
    check(t["served_by"] in hostnames, f"tag {t['tagname']} served by unknown host")
for a in T["alarm_points"]:
    check(a["source_tag"] in tagnames, f"alarm {a['alarm_id']} points at unknown tag {a['source_tag']}")
org_ids = {o["org_id"] for o in O["organizations"]}
for o in O["organizations"]:
    check(o["parent"] is None or o["parent"] in org_ids, f"org {o['name']} has unknown parent")
acct = {a["account_id"] for a in E["accounts"]}
inst = {i["institution_id"] for i in E["financial_institutions"]}
check(all(a["institution_id"] in inst for a in E["accounts"]), "account at unknown institution")
vend = {v["vendor_id"] for v in E["vendors"]}
for v in E["vendors"]:
    check(v["remit_account_id"] in acct and (v["alternate_account_id"] is None or v["alternate_account_id"] in acct), f"vendor {v['name']} account unknown")
    check(v["org_id"] is None or v["org_id"] in org_ids, f"vendor {v['name']} org unknown")
check(all(c["vendor_id"] in vend for c in E["contracts"]), "contract with unknown vendor")
holders = {h["holder_id"] for h in E["policyholders"]}
ins = {i["insurer_id"] for i in E["insurers"]}
brk = {b["broker_id"] for b in E["brokers"]} | {None}
apr = {a["appraiser_id"] for a in E["appraisers"]} | {None}
for p in E["policies"]:
    if not (p["holder_id"] in holders and p["insurer_id"] in ins and p["broker_id"] in brk and p["appraiser_id"] in apr):
        check(False, f"policy {p['policy_number']} has a dangling reference")
        break
firms = {f["firm_id"] for f in E["adjusting_firms"]} | {None}
check(all(a["firm_id"] in firms for a in E["adjusters"]), "adjuster with unknown firm")

# cross-registry references, checked only when the other registry exists
for fn, getter, label in (("infrastructure_assets.json", lambda d: {x["asset_id"] for x in d.get("assets", [])} | {x["asset_id"] for x in d.get("remote_assets", [])}
                           | {e["equipment_id"] for x in d.get("assets", []) for e in x.get("equipment", [])} | {f["feed_id"] for x in d.get("assets", []) for f in x.get("feeds", [])}, "infrastructure"),
                          ("areas.json", lambda d: {x["area_id"] for x in d.get("areas", [])}, "areas")):
    fp = os.path.join(DS, fn)
    if not os.path.exists(fp):
        notes.append(f"{fn} not present; cross-check skipped")
        continue
    known = getter(load(fp))
    if label == "infrastructure":
        tag_sites = {t["site_id"] for t in T["tags"] if not t["site_id"].startswith(("GW-SYS-", "AREA-"))}
        check(tag_sites <= known, f"tag sites missing from infrastructure_assets.json: {sorted(tag_sites - known)}")
        extra = sorted(e for e in equip if e not in known)
        notes.append(f"{len(extra)} equipment ids exist only in gw_host_registry.json (breakers, relays, transformers, booster pumps); listed in the truth file")
    else:
        pz = {t["site_id"] for t in T["tags"] if t["site_id"].startswith("AREA-")}
        check(pz <= known, f"pressure zones missing from areas.json: {sorted(pz - known)}")
        ha = {p["home_area_id"] for p in P["personas"] if p.get("home_area_id")}
        check(ha <= known, f"persona home_area_id missing from areas.json: {sorted(ha - known)}")
        nores = sorted({p["home_area"] for p in P["personas"] if p["home_area"] and not p.get("home_area_id")})
        check(not nores, f"persona home areas with no area id: {nores}")

# ---------------------------------------------------------------- 3. canon names present
blob_h = text(DS, "gw_host_registry.json")
for name in ("GW-WS-IT-04", "GW-SYS-JMP-01", "GW-SRV-HIST-01", "GW-SRV-OT-01", "GW-WS-OPS-02", "GW-SYS-SCADA-01", "GW-SYS-RTU-01", "GW-SYS-RTU-05", "GW-ENG-VELA", "svc_fieldops_ext",
             "ClearPath SecureReach 2.1", "Sentinel Edge 3.1", "Meridian HorizonView 4.2", "SOC-AN-01", "SOC-AN-03", "Fatima Al-Rasheed-Obinna"):
    check(name in blob_h, f"canon identifier missing from gw_host_registry.json: {name}")
h04 = next(h for h in H["hosts"] if h["hostname"] == "GW-WS-IT-04")
check(h04["ip"] == "10.14.22.47", "GW-WS-IT-04 must be 10.14.22.47 (GW-EVT-101)")
blob_t = text(DS, "scada_tags.json")
for name in ("FAC-UTL-01-P3-SET-PSI", "ZONE4-DIST-PSI", "ZONE4-LOW-PRES", "GW-FAC-WTR-03-BSTR-SET-PSI", "FAC-UTL-01-RAW-TPH-MGL", "CB-7", "CB-12", "B2-A", "B2-C", "B3-B", "R-02A", "R-03A", "GW.SUB1.REL.UV_THR.SP",
             "EQP-1101", "EQP-1104", "GW-FAC-SUB-05"):
    check(name in blob_t, f"canon point or equipment missing from scada_tags.json: {name}")
hs = {p["handle"] for p in P["personas"]}
for name in ("@CoastTruthTX", "@GulfWatchPatriot", "@TXCoastalWatchdog", "@NuecesLocalNews", "@BaysideLedger", "@Harborline6News", "@CoastlinePublicRadio", "@GulfwaterMaritime", "@SabalEnergyWire",
             "@ContinentalWire", "@AnchorRotorWeekly", "@KNCB1480", "@CBPWA_Alerts"):
    check(name in hs, f"canon handle missing from personas.json: {name}")
on = {o["name"] for o in O["organizations"]}
for name in ("Coastal Bend Power and Water Authority", "Brightwake Marine Systems", "Rendal Terminals", "Vantorra Restoration LLC", "Quellmar Fuel Partners", "Brannoch Maritime Holdings", "FastDry Coastal LLC",
             "Landmark Pacific Holdings LLC", "Shoreline Regional Medical Center", "Bay City Medical Center", "The Bayside Ledger", "Harborline 6 News", "Coastline Public Radio", "Gulfwater Maritime Report",
             "Sabal Energy Wire", "Continental Wire Service", "Anchor & Rotor Weekly", "KNCB Coastal Bend Radio", "Northlight Threat Lab", "Delta Pumps & Controls", "Gulf Relief Logistics", "Laguna Towing",
             "Coast Guard Sector Corpus Christi", "Nueces County Office of Emergency Management", "Texas General Land Office", "Cybersecurity and Infrastructure Security Agency"):
    check(name in on, f"canon organisation missing: {name}")
vn = {v["name"]: v for v in E["vendors"]}
check(vn["Vantorra Restoration LLC"]["registered_address"] == vn["Quellmar Fuel Partners"]["registered_address"]
      and vn["Vantorra Restoration LLC"]["remit_account_id"] == vn["Quellmar Fuel Partners"]["remit_account_id"], "Vantorra and Quellmar must share an address and a bank account (EVT-0105)")
check(any(c["value_usd"] == 14200000 and c["vendor_id"] == vn["Vantorra Restoration LLC"]["vendor_id"] for c in E["contracts"]), "$14.2M debris contract missing")
check(any(c["value_usd"] == 2100000 and c["vendor_id"] == vn["Quellmar Fuel Partners"]["vendor_id"] for c in E["contracts"]), "$2.1M fuel contract missing")
lph = [p for p in E["policies"] if p["holder_id"] == "PH-100001"]
check(len(lph) == 230, f"Landmark Pacific must hold 230 policies, has {len(lph)}")
ratio = sum(p["replacement_cost_value_usd"] for p in lph) / sum(p["county_assessed_value_usd"] for p in lph)
check(3.2 <= ratio <= 3.6, f"Landmark Pacific inflation ratio {ratio:.2f} should be about 3.4")

# ---------------------------------------------------------------- 4. the coordinated network matches canon
net = PT["networks"]["t15_47"]["persona_ids"]
check(len(net) == 47 and len(PT["networks"]["base_40"]["persona_ids"]) == 40, "operator network must be 47 accounts, 40 of them in the rumour network")
byid = {p["persona_id"]: p for p in P["personas"]}
window = [i for i in net if "2027-09-07" <= byid[i]["account_created"] <= "2027-09-09"]
check(len(window) == 31, f"31 operator accounts must be created 2027-09-07..09, found {len(window)}")
check(len(PT["networks"]["removed_d38_847"]["amplifiers_800"]) == 800, "800 amplifier accounts must be listed for the D+38 removal")
compact_handles = {r[0] for r in P["accounts_compact"]["rows"]}
check(set(PT["networks"]["removed_d38_847"]["amplifiers_800"]) <= compact_handles, "removed amplifier handles must exist in accounts_compact")
idx = sorted(int(i.split("-")[1]) for i in net)
runs = max((b - a == 1) + 0 for a, b in zip(idx, idx[1:]))
longest, cur = 1, 1
for a, b in zip(idx, idx[1:]):
    cur = cur + 1 if b - a == 1 else 1
    longest = max(longest, cur)
check(longest <= 4, f"operator accounts sit in a run of {longest} consecutive ids; they must be mixed with ordinary accounts")
kw = ("Corpus Christi", "South Texas", "Nueces County", "Coastal Bend")
check(len(ET["aid_diversion"]["hijacked_registrations"]["ids"]) == 410 and len(ET["aid_diversion"]["synthetic_identities"]) == 6, "aid diversion lists must have 410 + 6 entries")
check(len(ET["lph_runner_applications"]["ids"]) == 94, "94 runner applications required")

# ---------------------------------------------------------------- 5. nothing participant-facing explains the story or uses banned names
BANNED_REAL = ["GridWater", "gwcc", "Caller-Times", "CallerTimes", "KIII", "KRIS-TV", "KZTV", "CHRISTUS", "Spohn", "Driscoll", "Flint Hills", "Valero", "Citgo", "NuStar", "Buckeye", "State Farm", "Allstate",
               "AEP Texas", "H-E-B", "Whataburger", "Dragos", "AVEVA", "Yokogawa", "Fortinet", "Schneider", "Cummins", "Allen-Bradley", "Modicon", "Maximo 8", "Everbridge"]
NEVER = [r"KESTREL", r"STATE-X", r"Halcyon\s+Drift", r"Barge\s*44", r"DRIFTGLASS", r"\bACT-(KES|SOF)\b", r"BANK-SYN", r"SYN-PER", r"SOC-ACC", r"\bSUP-0\d", r"\bORG-09\d", r"UEI-SYN", r"PIID-SYN", r"\bGW-EVT-\d", r"\bEVT-\d{4}",
         r"\bCHR-\d{3}", r"\bPUB-\d{3}", r"\bT(8|9|10|15|18|22)\b"]
HINTS = [r"compromis", r"attack", r"adversar", r"intruder", r"malicious", r"sock ?puppet", r"inauthentic", r"\bbot network\b", r"shell compan", r"\bshell\b", r"fraudulent", r"\bring\b", r"stolen", r"hijack", r"spoofed",
         r"exfiltrat", r"implant", r"beacon", r"\bC2\b", r"\btruth\b", r"scenario_role", r"hidden", r"co-conspirator", r"defendant", r"\bfake\b", r"synthetic identit", r"money mule", r"diverted"]
for fn in PUBLIC_FILES:
    fp = os.path.join(DS, fn)
    if not os.path.exists(fp):
        check(False, f"missing file {fn}")
        continue
    t = text(fp)
    for w in BANNED_REAL:
        if re.search(re.escape(w), t, re.I):
            check(False, f"{fn}: banned real-world or retired name '{w}'")
    for pat in NEVER:
        m = re.search(pat, t)
        if m:
            check(False, f"{fn}: internal or never-public term '{m.group(0)}'")
    for pat in HINTS:
        for m in re.finditer(pat, t, re.I):
            ctx = t[max(0, m.start() - 50):m.end() + 40].replace("\n", " ")
            # legitimate uses: agency programme names and consumer-protection roles
            if re.search(r"Coast Truth TX|Truth About Rafael|Disaster Fraud|fraud warnings|fraud task force|[Ff]raud investigation announced|scams|Report scams|contractor fraud|disaster-fraud|Disaster-fraud|Claims oversight; fraud|\"fraud\"\]", ctx):
                continue
            check(False, f"{fn}: wording that explains the story: '...{ctx}...'")
            break
# restricted identifiers may appear in the host registry (raw technical data) but not in the public-voice registries
for fn in ("personas.json", "organizations.json"):
    t = text(DS, fn)
    for w in ("GW-ENG-VELA", "GW-SYS-JMP-01", "GW-WS-IT-04", "SecureReach"):
        check(w not in t, f"{fn}: restricted identifier {w}")
# registries must not say which accounts or vendors are false
for p in P["personas"]:
    check(set(p) == set(P["personas"][0]), f"persona {p['persona_id']} has a different field set")
    check(p["account_type"] in ("official", "media", "journalist", "business", "organization", "individual", "automated"), f"persona {p['persona_id']} account_type")
check(len({tuple(sorted(v)) for v in E["vendors"]}) == 1, "vendors must all have the same fields")
check(all(len(r) == len(P["accounts_compact"]["columns"]) for r in P["accounts_compact"]["rows"]), "accounts_compact row width")

# ---------------------------------------------------------------- 6. migration maps exist and resolve
mig = HT["id_migration"]
for old, new in mig["siem_alerts_HostName"].items():
    check(new in hostnames, f"SIEM host migration {old} -> {new} does not resolve")
for old, new in mig["old_registry_host_ids"].items():
    if not new.startswith(("user:", "none", "EXT-")):
        check(new in hostnames, f"old registry migration {old} -> {new} does not resolve")
for old, new in mig["maximo_assetnum"].items():
    check(new.startswith("same") or new in equip or new in hostnames, f"Maximo migration {old} -> {new} does not resolve")
for k in ("feed_handles", "old_personas_json", "scenario_entities"):
    check(k in PT["id_migration"], f"personas truth lacks id_migration.{k}")
check("old_entity_registry" in ET["id_migration"] and "scenario_entities" in ET["id_migration"], "entity registry truth lacks migration maps")
for old, new in OT["id_migration"]["scenario_entities"].items():
    check(new in org_ids, f"organisation migration {old} -> {new} does not resolve")
check(not os.path.exists(os.path.join(DS, "entity_catalogs", "gw_host_registry.json")) and os.path.exists(os.path.join(DS, "entity_catalogs", "README.md")), "entity_catalogs/ must hold only the README")
check(os.path.isdir(os.path.join(ROOT, "_versions", "entity_catalogs_20261109")), "old entity_catalogs copies must be kept under _versions/")

print(f"hosts {len(H['hosts'])}, users {len(H['users'])}, service accounts {len(H['service_accounts'])}, equipment {len(H['equipment'])}, zones {len(H['network_zones'])}")
print(f"tags {len(T['tags'])}, alarm points {len(T['alarm_points'])}")
print(f"personas {len(P['personas'])} (+{len(P['accounts_compact']['rows'])} compact), organisations {len(O['organizations'])}")
print("entity registry: " + ", ".join(f"{k} {len(E[k])}" for k in E if isinstance(E[k], list)))
for n in notes:
    print("note:", n)
for f in fails:
    print("FAIL", f)
print(f"\n{'PASS' if not fails else 'FAILED'}: {len(fails)} problem(s)")
sys.exit(1 if fails else 0)
