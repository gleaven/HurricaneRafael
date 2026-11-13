"""Check that every entity id in every delivered stream exists in a registry.

    python3 scripts/check_entities.py              full check; exit 1 on any failure
    python3 scripts/check_entities.py --usage      also write which registry entries no stream uses
    python3 scripts/check_entities.py --no-text    skip the banned-name scan of the stream files
    python3 scripts/check_entities.py --budget=90  stop the name scan after 90 s; run again to continue (scanned files are cached)

Checks
  1. Stream ids: each (file pattern, column) in CHECKS must hold only ids of the named classes.
  2. Registry ids are unique inside their list, and a primary id never names two different
     things in two registries (intended shared ids are listed in SHARED).
  3. Every registry entity is used by some stream, or is marked "reference_only": true with a
     "reference_reason" (scripts/apply_registry_additions.py sets these from the usage report).
  4. No real company, hospital-system or station names and no "GridWater" in registries, schemas
     or stream files.

Writes 07_validation/reports/entity_check.json (and entity_usage.json with --usage).
"""
import csv
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "05_other_sources")
REG = os.path.join(ROOT, "06_data_streams")
csv.field_size_limit(10 ** 8)

def _not_registry_address():
    """Regex for addresses that are not registry entries: anything outside the utility's registered /24 networks
    (outside addresses, and an address from another network that a returning laptop asks to renew and is refused),
    and the employee VPN pool."""
    zones = json.load(open(os.path.join(REG, "gw_host_registry.json"), encoding="utf-8"))["network_zones"]
    nets = sorted({re.escape(".".join(z["cidr"].split("/")[0].split(".")[:3])) for z in zones if z["cidr"].endswith("/24") and z["zone"] != "corp-vpn"})
    return r"^(?!(?:" + "|".join(nets) + r")\.)"


NOT_REGISTRY_ADDRESS = _not_registry_address()
PARTNER_POOL = r"^10\.\d+\.250\."          # the partner organisations' VPN pools

BANNED = re.compile(rb"GridWater|Flint Hills|Valero|Citgo|NuStar|Buckeye Partners|Caller-?Times|\bKIII\b|KRIS-?TV|CHRISTUS|Spohn|Driscoll Children|State Farm|Auriga Meridian|Fort Cavazos|Everbridge|CivicReady", re.I)


def load(name):
    with open(os.path.join(REG, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def registry_classes():
    """{class name: {id: (registry file, list key)}} and the list of (file, key, id field, records)."""
    R, lists = {}, []

    def add(cls, file, key, field, also=()):
        d = load(file)
        recs = d.get(key, [])
        if isinstance(recs, dict) and "rows" in recs:            # compact table
            cols = recs["columns"]
            recs = [dict(zip(cols, r)) for r in recs["rows"]]
        lists.append((file, key, field, recs, cls))
        for r in recs:
            for f in (field,) + tuple(also):
                v = r.get(f)
                if v in (None, ""):
                    continue
                for x in (v if isinstance(v, list) else [v]):
                    R.setdefault(cls, {})[str(x)] = (file, key, str(r.get(field)))

    add("vessel", "vessels", "vessels", "vessel_id", ("mmsi", "imo"))
    add("aircraft", "aircraft_registry", "aircraft", "aircraft_id", ("icao24", "registration", "callsign"))
    add("airfield", "aircraft_registry", "airfields", "airfield_id")
    add("parking", "aircraft_registry", "parking_positions", "position_id")
    add("area", "areas", "areas", "area_id", ("tract", "geoid", "zip"))
    add("station", "cad_units", "stations", "station_id")
    add("unit", "cad_units", "units", "unit_id")
    add("nature", "cad_units", "nature_codes", "code")
    add("disposition", "cad_units", "disposition_codes", "code")
    add("drone_operator", "drone_operators", "authorized_operators", "operator_id")
    add("launch_site", "drone_operators", "launch_sites", "site_id")
    for key, field in (("insurers", "insurer_id"), ("brokers", "broker_id"), ("appraisers", "appraiser_id"), ("adjusting_firms", "firm_id"), ("adjusters", "adjuster_id"),
                       ("vendors", "vendor_id"), ("contracts", "contract_id"), ("financial_institutions", "institution_id"), ("accounts", "account_id"),
                       ("policyholders", "holder_id"), ("policies", "policy_number"), ("prepaid_card_merchants", "merchant_id"), ("crypto_endpoints", "endpoint_id")):
        add({"vendors": "vendor", "accounts": "account", "financial_institutions": "institution", "policies": "policy", "policyholders": "holder", "insurers": "insurer",
             "contracts": "contract"}.get(key, key), "entity_registry", key, field)
    add("facility", "facility_registry", "facilities", "facility_id")
    add("facility", "facility_registry", "out_of_area", "facility_id")
    add("site", "gw_host_registry", "sites", "site_id")
    add("host", "gw_host_registry", "hosts", "hostname", ("ip",))
    add("equipment", "gw_host_registry", "equipment", "equipment_id")
    add("user", "gw_host_registry", "users", "username", ("ot_account",))
    add("user", "gw_host_registry", "service_accounts", "account")
    add("host", "gw_host_registry", "external_systems", "system_id", ("ip", "hostname"))
    add("asset", "infrastructure_assets", "assets", "asset_id", ("rtu_id",))
    add("asset", "infrastructure_assets", "remote_assets", "asset_id")
    if isinstance(load("infrastructure_assets").get("maintenance_sites"), list):
        add("site", "infrastructure_assets", "maintenance_sites", "site_id")
    add("org", "organizations", "organizations", "org_id")
    add("persona", "personas", "personas", "handle", ("persona_id",))
    add("persona", "personas", "accounts_compact", "handle")
    add("tag", "scada_tags", "tags", "tagname")
    add("alarm", "scada_tags", "alarm_points", "alarm_id")
    sr = load("sensor_registry")
    for key, v in sr.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            add("sensor", "sensor_registry", key, "sensor_id" if "sensor_id" in v[0] else "site_id")
    add("terminal", "terminal_registry", "terminals", "terminal_id")
    add("berth", "terminal_registry", "berths", "berth_id")
    add("berth", "terminal_registry", "slips", "slip_id")
    add("harbour", "terminal_registry", "harbours", "harbour_id")
    add("anchorage", "terminal_registry", "anchorage_positions", "position_id")
    add("gate", "terminal_registry", "sea_gates", "gate_id")
    tr = load("terminal_registry")
    for k in ("channel_segments", "ship_agents"):
        if isinstance(tr.get(k), list):
            add("segment" if k == "channel_segments" else "agent", "terminal_registry", k, "segment_id" if k == "channel_segments" else "agent_id")
    if os.path.exists(os.path.join(REG, "partner_it_registry.json")):
        for o in load("partner_it_registry")["organisations"]:
            where = ("partner_it_registry", o["org_id"])
            for h in o["hosts"]:
                for f in ("host_id", "hostname", "ip"):
                    if h.get(f):
                        R.setdefault("partner_host", {})[str(h[f])] = where + (h["host_id"],)
            for a in o["accounts"]:
                for f in ("account", "mailbox"):
                    if a.get(f):
                        R.setdefault("partner_account", {})[str(a[f])] = where + (a["account"],)
    cu = load("cad_units")
    R["agency"] = {k: ("cad_units", "agencies", k) for k in cu.get("agencies", {})}
    for k in ("broadcast_stations",):
        if isinstance(load("organizations").get(k), list):
            add("station_bc", "organizations", k, "station_id")
    return R, lists


# (glob under 05_other_sources, column, classes, options)   options: split=";", optional (blank ok), ignore=regex
CHECKS = [
    ("ais/ais_*.csv", "MMSI", ["vessel"], {}), ("ais/satellite/sais_*.csv", "MMSI", ["vessel"], {}),
    ("adsb/adsb_*.csv", "icao24", ["aircraft"], {}),
    ("avl/avl_*.csv", "unit_id", ["unit"], {}), ("avl/avl_*.csv", "agency", ["agency"], {}),
    ("911/cad_incidents_*.csv", "agency", ["agency"], {}), ("911/cad_incidents_*.csv", "nature_code", ["nature"], {}),
    ("911/cad_incidents_*.csv", "unit_id", ["unit"], {"optional": True}), ("911/cad_incidents_*.csv", "additional_units", ["unit"], {"optional": True, "split": r"[;,| ]+"}),
    ("911/cad_incidents_*.csv", "disposition_code", ["disposition"], {"optional": True}), ("911/cad_incidents_*.csv", "census_tract", ["area"], {"optional": True}),
    ("sar/sar_missions.csv", "asset_id", ["unit", "aircraft", "vessel"], {}), ("sar/sar_missions.csv", "agency", ["agency", "org"], {"optional": True}),
    ("sar/sar_asset_log.csv", "asset_id", ["unit", "aircraft", "vessel"], {"ignore": r"^SAR BRANCH$"}), ("sar/flood_depth_soundings.csv", "unit_id", ["unit", "aircraft", "vessel"], {"optional": True}),
    ("shelters/shelter_daily_census.csv", "facility_id", ["facility"], {}), ("shelters/shelter_registry.csv", "facility_id", ["facility"], {}),
    ("shelters/evacuation_bus_trips.csv", "unit_id", ["unit"], {}), ("shelters/evacuation_bus_trips.csv", "facility_id", ["facility"], {}),
    ("shelters/shelter_211_calls.csv", "referred_facility_id", ["facility"], {"optional": True}),
    ("public_health/ed_visits_*.csv", "Facility_ID", ["facility"], {}), ("public_health/hospital_capacity.csv", "Facility_ID", ["facility"], {}),
    ("public_health/syndrome_summary.csv", "Facility_ID", ["facility"], {}), ("public_health/syndrome_summary.csv", "Area_ID", ["area"], {"optional": True}),
    ("public_health/wastewater_surveillance.csv", "sewershed_id", ["sensor", "asset", "area"], {}),
    ("public_health/eas_broadcasts.csv", "AreaIDs", ["area"], {"optional": True, "split": r"[;,| ]+"}),
    ("env_sensors/*.csv", "SensorID", ["sensor"], {}), ("weather/*_observations.csv", "StationID", ["sensor"], {}),
    ("drone_detections/detections_*.csv", "sensor_id", ["sensor"], {}), ("drone_detections/sensor_status_*.csv", "sensor_id", ["sensor"], {}),
    ("drone_detections/sensor_sites.csv", "sensor_id", ["sensor"], {}), ("drone_detections/laanc_authorizations.csv", "operator_id", ["drone_operator"], {}),
    ("drone_video/logs/flight_log.csv", "operator_id", ["drone_operator", "aircraft"], {}), ("drone_video/drone_telemetry_*.csv", "operator_id", ["drone_operator"], {}),
    ("drone_video/logs/thermal_survey_readings.csv", "asset_id", ["asset", "equipment"], {}),
    ("port_surveillance/radar_tracks_*.csv", "sensor_id", ["sensor"], {}), ("port_surveillance/radar_tracks_*.csv", "correlated_mmsi", ["vessel"], {"optional": True}),
    ("port_surveillance/camera_events.csv", "sensor_id", ["sensor"], {}), ("port_surveillance/camera_events.csv", "mmsi", ["vessel"], {"optional": True}),
    ("port_surveillance/camera_events.csv", "berth_id", ["berth", "terminal"], {"optional": True}), ("port_surveillance/sensor_status.csv", "sensor_id", ["sensor"], {}),
    ("port_surveillance/sensors.csv", "sensor_id", ["sensor"], {}), ("port_surveillance/vessel_traffic_log.csv", "mmsi", ["vessel"], {"optional": True}),
    ("supply/vessel_arrivals.csv", "mmsi", ["vessel"], {}), ("supply/vessel_arrivals.csv", "terminal_id", ["terminal"], {"optional": True}),
    ("supply/vessel_arrivals.csv", "berth_id", ["berth"], {"optional": True}), ("supply/vessel_arrivals.csv", "anchorage_position_id", ["anchorage"], {"optional": True}),
    ("supply/cargo_manifest.csv", "mmsi", ["vessel"], {"optional": True}), ("supply/cargo_manifest.csv", "supplier_id", ["vendor", "org"], {"optional": True}),
    ("supply/cargo_manifest.csv", "consignee_id", ["vendor", "org", "facility"], {"optional": True}),
    ("supply/fuel_deliveries.csv", "supplier_id", ["vendor", "org"], {"optional": True}), ("supply/fuel_deliveries.csv", "facility_id", ["facility", "asset", "terminal", "site"], {"optional": True}),
    ("supply/fuel_deliveries.csv", "receiving_asset_id", ["asset", "equipment", "vessel", "facility", "terminal", "berth"], {"optional": True}),
    ("supply/port_conditions.csv", "vessel_mmsi", ["vessel"], {"optional": True}), ("supply/port_conditions.csv", "terminal_id", ["terminal"], {"optional": True}),
    ("supply/port_conditions.csv", "segment_id", ["segment"], {"optional": True}),
    ("telemetry/historian_*.csv", "Tagname", ["tag"], {}), ("telemetry/outage_map.csv", "area_id", ["area"], {}), ("telemetry/outage_map.csv", "substation_id", ["asset"], {"optional": True}),
    ("telemetry/vessel_cargo_control_*.csv", "mmsi", ["vessel"], {"optional": True}), ("telemetry/vessel_cargo_control_remote_sessions.csv", "vessel_mmsi", ["vessel"], {"optional": True}),
    ("maintenance/work_orders.csv", "asset_id", ["asset", "equipment", "host"], {"optional": True}), ("maintenance/work_orders.csv", "vendor_id", ["vendor", "org"], {"optional": True}),
    ("maintenance/work_orders.csv", "site_id", ["site", "asset"], {"optional": True}),
    ("maintenance/base_status_reports.csv", "installation_id", ["facility"], {}), ("maintenance/base_status_reports.csv", "equipment_id", ["asset", "equipment"], {"optional": True}),
    ("network_logs/siem/siem_alerts_*.csv", "src_host", ["host"], {"optional": True}), ("network_logs/siem/siem_alerts_*.csv", "dst_host", ["host"], {"optional": True}),
    ("network_logs/siem/siem_alerts_*.csv", "user", ["user"], {"optional": True, "ignore": r"\\"}),   # HOST\\account forms are checked through the audit tables
    ("network_logs/audit/remote_access_sessions.csv", "gateway", ["host"], {}), ("network_logs/audit/remote_access_sessions.csv", "account", ["user"], {}),
    ("network_logs/audit/employee_vpn_sessions.csv", "gateway", ["host"], {}), ("network_logs/audit/employee_vpn_sessions.csv", "account", ["user"], {}),
    ("network_logs/audit/employee_vpn_sessions.csv", "device", ["host"], {"ignore": r"^(DESKTOP|LAPTOP)-[A-Z2-9]{7}$"}),
    ("network_logs/audit/historian_access.csv", "server", ["host"], {}), ("network_logs/audit/endpoint_protection.csv", "host", ["host"], {}),
    ("network_logs/audit/ot_config_changes.csv", "device", ["host"], {}), ("network_logs/audit/file_integrity.csv", "host", ["host"], {}),
    ("network_logs/audit/scada_command_log.csv", "scada_server", ["host"], {}), ("network_logs/audit/scada_command_log.csv", "device", ["equipment", "asset"], {}),
    ("network_logs/portal/*.csv", "system", ["host"], {}),
    # raw IT and security logs of the utility: internal addresses, host names and accounts come from gw_host_registry.json
    # (outside addresses and the employee VPN pool 10.14.250.0/24 are not registry entries)
    ("network_logs/firewall/fw_*.csv", "device", ["host"], {}),
    ("network_logs/firewall/fw_*.csv", "src_ip", ["host"], {"ignore": NOT_REGISTRY_ADDRESS}), ("network_logs/firewall/fw_*.csv", "dst_ip", ["host"], {"ignore": NOT_REGISTRY_ADDRESS}),
    ("network_logs/proxy/web_proxy_*.csv", "client_ip", ["host"], {}), ("network_logs/proxy/web_proxy_*.csv", "user", ["user"], {"optional": True}),
    ("network_logs/dhcp/dhcp_leases_*.csv", "server", ["host"], {}), ("network_logs/dhcp/dhcp_leases_*.csv", "hostname", ["host"], {"optional": True, "ignore": r"^(DESKTOP|LAPTOP)-[A-Z2-9]{7}$"}),   # staff home computers on the VPN
    ("network_logs/dhcp/dhcp_leases_*.csv", "ip", ["host"], {"ignore": NOT_REGISTRY_ADDRESS}),
    ("network_logs/windows/*.jsonl", "host", ["host"], {}), ("network_logs/windows/*.jsonl", "user", ["user", "host"], {"optional": True, "strip": "$", "ignore": r"^SYSTEM$"}),
    ("network_logs/windows/*.jsonl", "target_user", ["user"], {"optional": True}), ("network_logs/windows/*.jsonl", "caller_computer", ["host"], {"optional": True}),
    ("network_logs/windows/*.jsonl", "src_host", ["host"], {"optional": True}),
    ("network_logs/endpoint/*.jsonl", "host", ["host"], {}), ("network_logs/endpoint/*.jsonl", "user", ["user", "host"], {"optional": True, "strip": "$", "ignore": r"^SYSTEM$"}),
    ("network_logs/triage/*/collection.json", "host", ["host"], {}),
    # partner organisations: hosts, internal addresses and accounts come from partner_it_registry.json
    ("partner_it/*/firewall_*.csv", "device", ["partner_host"], {}),
    ("partner_it/*/web_*.csv", "client_ip", ["partner_host"], {"ignore": PARTNER_POOL}), ("partner_it/*/web_*.csv", "user", ["partner_account"], {"optional": True}),
    ("partner_it/*/dns_*.csv", "client_ip", ["partner_host"], {"ignore": PARTNER_POOL}), ("partner_it/*/dns_*.csv", "resolver", ["partner_host"], {}),
    ("partner_it/*/auth_*.csv", "host", ["partner_host"], {}), ("partner_it/*/auth_*.csv", "account", ["partner_account"], {}),
    ("partner_it/*/mail_*.csv", "gateway", ["partner_host"], {}),
    ("partner_it/*/endpoint_alerts_*.csv", "host", ["partner_host"], {}), ("partner_it/*/endpoint_alerts_*.csv", "ip", ["partner_host"], {}),
    ("payments/contracts_awards.csv", "supplier_id", ["vendor"], {}), ("payments/contracts_awards.csv", "awarding_org_id", ["org"], {"optional": True}),
    ("payments/contracts_invoices.csv", "supplier_id", ["vendor"], {}), ("payments/contracts_invoices.csv", "remit_bank_account_id", ["account"], {"optional": True}),
    ("payments/contracts_invoices.csv", "work_area_id", ["area"], {"optional": True}), ("payments/contracts_vendor_registry.csv", "supplier_id", ["vendor"], {}),
    ("payments/contracts_vendor_registry.csv", "bank_account_id", ["account"], {"optional": True}), ("payments/contracts_debris_monitoring.csv", "area_id", ["area"], {"optional": True}),
    ("payments/financial_transactions.csv", "account_id", ["account"], {}), ("payments/financial_transactions.csv", "institution_id", ["institution"], {"optional": True}),
    ("payments/financial_transactions.csv", "counterparty_id", ["account", "vendor", "org", "holder", "prepaid_card_merchants", "crypto_endpoints", "insurer", "institution"], {"optional": True}),
    ("payments/insurance_claims.csv", "insurer_id", ["insurer"], {"optional": True}), ("payments/insurance_claims.csv", "policy_id", ["policy"], {"optional": True}),
    ("payments/insurance_claims.csv", "holder_id", ["holder"], {"optional": True}), ("payments/insurance_claims.csv", "area_id", ["area"], {"optional": True}),
    ("payments/aid_applications.csv", "area_id", ["area"], {"optional": True}),
    ("infrastructure/utility_site_survey.csv", "asset_id", ["asset"], {}), ("infrastructure/damage_assessment.csv", "census_tract", ["area"], {"optional": True}),
    ("broadcast/station_status_log.csv", "station_id", ["station_bc"], {}), ("broadcast/station_program_log.csv", "station_id", ["station_bc"], {}),
    ("broadcast/alert_relay_log.csv", "station_id", ["station_bc"], {}),
    ("social_media/_geotagged_index.csv", "screen_name", ["persona"], {}),
]
# ids that deliberately name the same thing in two registries
SHARED = re.compile(r"^(PLC-|FAC-|GW-FAC-|EQP-|WW-|TERM-0?8$|AREA-|GAUGE-|ORG-|GW-SYS-RTU|GW-)")
BLANKS = {"", "-", "none", "None", "NA", "N/A", "null"}


def norm_persona(x):
    return x if x.startswith("@") else "@" + x


def main():
    usage_mode = "--usage" in sys.argv
    R, lists = registry_classes()
    problems, report = [], {"streams": [], "registry": {}}
    used = {}

    # 1. stream ids
    for pat, col, classes, opt in CHECKS:
        files = sorted(glob.glob(os.path.join(SRC, pat)))
        if not files:
            problems.append(f"no files for {pat}")
            continue
        valid = {}
        for c in classes:
            valid.update(R.get(c, {}))
        if not valid:
            problems.append(f"{pat}:{col}: no registry class {classes}")
            continue
        vals = {}
        splitter = re.compile(opt["split"]) if opt.get("split") else None
        missing_col = False
        for fp in files:
            if fp.endswith(".jsonl"):                      # JSON Lines written with compact separators: "key":"value"
                rx = re.compile(rb'"' + col.encode() + rb'":"((?:[^"\\]|\\.)*)"')
                with open(fp, "rb") as fh:
                    for line in fh:
                        for m in rx.finditer(line):
                            v = m.group(1).decode("utf-8", "replace").replace("\\\\", "\\")
                            vals[v] = vals.get(v, 0) + 1
                continue
            if fp.endswith(".json"):
                v = str(json.load(open(fp, encoding="utf-8")).get(col, ""))
                vals[v] = vals.get(v, 0) + 1
                continue
            with open(fp, encoding="utf-8", errors="replace", newline="") as fh:
                rd = csv.reader(fh)
                h = next(rd, [])
                if col not in h:
                    missing_col = True
                    continue
                i = h.index(col)
                for row in rd:
                    if i < len(row):
                        v = row[i]
                        vals[v] = vals.get(v, 0) + 1
        if missing_col and not vals:
            problems.append(f"{pat}: column {col} not found")
            continue
        unknown = {}
        for v, n in vals.items():
            parts = [p for p in (splitter.split(v) if splitter else [v])]
            for p in parts:
                p = p.strip()
                if opt.get("strip") and p.endswith(opt["strip"]):      # machine accounts: HOSTNAME$
                    p = p[:-len(opt["strip"])]
                if opt.get("ignore") and re.search(opt["ignore"], p):
                    continue
                if p in BLANKS:
                    if not opt.get("optional") and p == "" and not splitter:
                        unknown["(blank)"] = unknown.get("(blank)", 0) + n
                    continue
                key = norm_persona(p) if "persona" in classes else p
                if key in valid:
                    used.setdefault(valid[key], 0)
                    used[valid[key]] += n
                else:
                    unknown[p] = unknown.get(p, 0) + n
        entry = {"files": pat, "column": col, "distinct": len(vals), "unknown": len(unknown)}
        if unknown:
            ex = sorted(unknown.items(), key=lambda x: -x[1])[:8]
            entry["examples"] = ex
            problems.append(f"{pat}:{col}: {len(unknown)} id(s) not in {classes}: {[e[0] for e in ex]}")
        report["streams"].append(entry)

    # posts: every posting account is a registered persona
    handles = set(R.get("persona", {}))
    posted = set()
    for fp in sorted(glob.glob(os.path.join(SRC, "social_media", "*.jsonl"))):
        if os.path.basename(fp).startswith("_"):
            continue
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                m = re.search(r'"screen_name": ?"([^"]+)"', line)
                if m:
                    posted.add("@" + m.group(1))
    unknown = sorted(posted - handles)
    for h in posted & handles:
        used[R["persona"][h]] = used.get(R["persona"][h], 0) + 1
    if unknown:
        problems.append(f"social_media: {len(unknown)} posting accounts not in personas.json: {unknown[:8]}")
    report["streams"].append({"files": "social_media/*.jsonl", "column": "user.screen_name", "distinct": len(posted), "unknown": len(unknown)})

    # 2. uniqueness
    seen_primary = {}
    for file, key, field, recs, cls in lists:
        ids = [str(r.get(field)) for r in recs if r.get(field) not in (None, "")]
        dup = sorted({x for x in ids if ids.count(x) > 1}) if len(ids) < 5000 else sorted({x for x in ids if x in set()})
        if len(ids) != len(set(ids)):
            dup = sorted([x for x in set(ids) if ids.count(x) > 1])[:6]
            problems.append(f"{file}.json {key}: duplicate ids {dup}")
        for x in set(ids):
            if x in seen_primary and seen_primary[x][0] != file and not SHARED.match(x):
                problems.append(f"id {x} is in both {seen_primary[x][0]}.json ({seen_primary[x][1]}) and {file}.json ({key})")
            seen_primary.setdefault(x, (file, key))

    # 3. usage
    unused_report = {}
    for file, key, field, recs, cls in lists:
        n_unused, n_ref, bad = 0, 0, []
        for r in recs:
            rid = str(r.get(field))
            is_used = (file, key, rid) in used
            if not is_used:
                n_unused += 1
                if r.get("reference_only") is True and r.get("reference_reason"):
                    n_ref += 1
                else:
                    bad.append(rid)
        unused_report[f"{file}.{key}"] = {"records": len(recs), "used_in_streams": len(recs) - n_unused, "reference_only": n_ref, "unmarked_unused": len(bad), "examples": bad[:10]}
        if bad and key != "accounts_compact":
            problems.append(f"{file}.json {key}: {len(bad)} entries are in no stream and not marked reference_only, e.g. {bad[:5]}")
    report["registry"] = unused_report
    if usage_mode:
        with open(os.path.join(ROOT, "07_validation", "reports", "entity_usage.json"), "w", encoding="utf-8") as fh:
            json.dump({"used": sorted([list(k) + [v] for k, v in used.items()])}, fh)

    # 4. banned names (files already scanned and unchanged are skipped: the result is cached by path, size and mtime)
    incomplete = False
    if "--no-text" not in sys.argv:
        import time
        budget = next((float(x.split("=")[1]) for x in sys.argv if x.startswith("--budget=")), 1e9)
        cache_p = os.path.join(ROOT, "07_validation", "reports", "entity_text_scan.cache.json")
        cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
        targets = [p for p in glob.glob(os.path.join(REG, "*.json")) + glob.glob(os.path.join(REG, "schemas", "*.json"))]
        for d, _, fs in os.walk(SRC):
            targets += [os.path.join(d, f) for f in fs if f.rsplit(".", 1)[-1] in ("csv", "json", "jsonl", "log", "md", "txt")]
        t0, scanned = time.time(), 0
        for fp in sorted(targets, key=os.path.getsize):
            rel = os.path.relpath(fp, ROOT)
            st = os.stat(fp)
            sig = f"{st.st_size}:{int(st.st_mtime)}"
            if cache.get(rel, {}).get("sig") == sig:
                continue
            if time.time() - t0 > budget:
                incomplete = True
                continue
            found = set()
            with open(fp, "rb") as fh:
                tail = b""
                while True:
                    chunk = fh.read(1 << 22)
                    if not chunk:
                        break
                    for m in BANNED.finditer(tail + chunk):
                        found.add(m.group(0).decode("utf-8", "replace"))
                    tail = chunk[-40:]
            cache[rel] = {"sig": sig, "hits": sorted(found)}
            scanned += 1
        cache = {k: v for k, v in cache.items() if os.path.exists(os.path.join(ROOT, k))}
        json.dump(cache, open(cache_p, "w"))
        for f, v in sorted(cache.items()):
            if v["hits"]:
                problems.append(f"banned name in {f}: {v['hits'][:5]}")
        report["text_scan_files"] = len(targets)
        report["text_scan_complete"] = not incomplete
        if incomplete:
            problems.append("text scan not finished within the time budget: run again (files already scanned are cached)")

    report["problems"] = problems
    os.makedirs(os.path.join(ROOT, "07_validation", "reports"), exist_ok=True)
    with open(os.path.join(ROOT, "07_validation", "reports", "entity_check.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, default=str)
    for p in problems[:80]:
        print("FAIL", p)
    n_cols = len(report["streams"])
    print(f"\n{'PASS' if not problems else 'FAILED'}: {len(problems)} problem(s); {n_cols} stream id columns checked against {sum(len(v) for v in R.values()):,} registry ids")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
