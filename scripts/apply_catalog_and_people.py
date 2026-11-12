"""Merge the stream families' catalogue notes into stream_catalog.json, list every schema file in
the schema index, and add the people who were named only in the MSEL as character records.
Idempotent.

    python3 scripts/apply_catalog_and_people.py
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = []


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def save(rel, obj):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


CAT = {
    "ais": {"cadence": "about 1 min in channels and harbours, 5 min in open bay and approaches, 6 min at anchor, 15 min on station, 30 min offshore, 60 min moored",
            "additional_files": [{"path_glob": "05_other_sources/ais/satellite/sais_*.csv", "what": "satellite-received AIS (same columns, 30-60 min cadence); kept apart because it is a different receiver"}],
            "notes_add": "Extra column Destination (the transponder's free-text field)."},
    "adsb": {"path_glob": "05_other_sources/adsb/adsb_*.csv", "cadence": "10 s near airfields and in hovers, 30 s low level, 60 s en route",
             "notes_add": "nic and nac_p integrity fields are reported; call signs carry at most eight characters (join on icao24)."},
    "drone_telemetry": {"path_glob": "05_other_sources/drone_video/drone_telemetry_*.csv",
                        "additional_files": [{"path_glob": "05_other_sources/drone_video/logs/*.csv", "what": "flight log and thermal survey readings (different columns)"}],
                        "ids_add": ["06_data_streams/aircraft_registry.json"]},
    "drone_detections": {"notes_add": "Five tables: sensor_sites, sensor_status_*, detections_*, laanc_authorizations, sighting_reports. Sensors are in sensor_registry.json (drone_detection_sensors).",
                         "ids_add": ["06_data_streams/sensor_registry.json", "06_data_streams/drone_operators.json"]},
    "satellite": {"notes_add": "Includes catalog.json (STAC collection). Vessel counts in scene descriptions come from the AIS files: re-run gen_satellite.py after AIS is regenerated."},
    "cad_911": {"additional_files": [{"path_glob": "05_other_sources/911/reports/*.csv", "what": "call-centre daily volume, queue depth, shift log, subscriber records (no coordinates)"}]},
    "damage_assessment": {"additional_files": [{"path_glob": "05_other_sources/infrastructure/aerial_survey/*.csv", "what": "aerial collection index"}]},
    "shelters": {"notes_add": "Folder also holds shelter_registry.csv, shelter_211_calls.csv and evacuation_bus_trips.csv."},
    "sar_missions": {"notes_add": "One row per rescue case (time column launch_utc; mission_id groups a sortie). Folder also holds sar_asset_log.csv, flood_depth_soundings.csv, flood_extent_snapshots.csv."},
    "public_record": {"notes_add": "Record ids are public-record fact ids plus three NOTICE-* records for events with no fact of their own.", "ids_set": ["02_public_record/public_record.json"]},
    "avl": {"cadence": "see 06_data_streams/schemas/avl_schema.json (denser while moving, sparse when parked)"},
    "port_surveillance": {"notes_add": "Five tables: sensors, radar_tracks_*, camera_events, vessel_traffic_log, sensor_status. Sensors are in sensor_registry.json (port_surveillance_sensors).",
                          "ids_add": ["06_data_streams/sensor_registry.json", "06_data_streams/vessels.json", "06_data_streams/terminal_registry.json"]},
    "port_conditions": {"notes_add": "segment_id values are defined in terminal_registry.json (channel_segments).", "ids_add": ["06_data_streams/terminal_registry.json"]},
    "port_arrivals": {"notes_add": "port_of_arrival is USCRP. Columns include next_port, noa_submitted_datetime, eta_revised_datetime, ata_anchorage_datetime, hold_log, shift_berth_id, shift_datetime; agents are in organizations.json (type 'ship agent')."},
    "cargo_manifests": {"notes_add": "Sea and air consignments in one table (mode SEA / AIR)."},
    "scada_historian": {"cadence": "compressed archive: a row on change beyond deadband, at least hourly (15 min for key pressures and voltages); events at the exact second",
                        "key_columns": {"time": "Timestamp (UTC)", "entity_ids": ["Tagname"]}},
    "outage_map": {"cadence": "15 min", "notes_add": "Adds cause, crews_assigned, est_restoration_utc.", "span": {"start_utc": "2027-09-10T05:00Z", "end_utc": "2027-10-27T05:00Z"}},
    "work_orders": {"key_columns": {"time": "reported_date, status_date, actual_finish, status_history", "entity_ids": ["wonum", "asset_id", "vendor_id"]},
                    "ids_set": ["06_data_streams/infrastructure_assets.json", "06_data_streams/scada_tags.json", "06_data_streams/gw_host_registry.json", "06_data_streams/entity_registry.json"]},
    "base_status_reports": {"ids_set": ["06_data_streams/facility_registry.json", "06_data_streams/infrastructure_assets.json"]},
    "fuel_deliveries": {"notes_add": "record_type DELIVERY or TANK_DIP.", "ids_add": ["06_data_streams/organizations.json", "06_data_streams/infrastructure_assets.json", "06_data_streams/terminal_registry.json", "06_data_streams/vessels.json"]},
    "vessel_ot_logs": {"notes_add": "Three files: kalvora_star, ostrel_bay, remote_sessions."},
    "social_media": {"notes_add": "Files whose names start with an underscore are not posts: _account_lookup.jsonl, _platform_records_return.jsonl, _geotagged_index.csv."},
    "contracts": {"notes_add": "Six files: vendor_registry, business_filings, awards, invoices, actions, debris_monitoring.", "ids_add": ["06_data_streams/organizations.json", "06_data_streams/areas.json"]},
    "financial_transactions": {"notes_add": "counterparty_id may be an organizations.json id as well as an entity_registry id."},
    "aid_applications": {"span": {"start_utc": "2027-11-13T00:00Z"}, "notes_add": "Time columns submitted_utc, changed_utc, event_utc; ids application_id, account_id, area_id, tract."},
    "insurance_claims": {"notes_add": "policy_id holds the registry's policy_number; two record types (policy_transaction, claim)."},
    "census": {"notes_add": "The tract index carries AREA_ID, EVAC_ZONE_AREA_ID and WATER_DISTRICT_AREA_ID for joins to areas.json."},
    "siem_alerts": {"path_glob": "05_other_sources/network_logs/siem/*.csv", "notes_add": "Monthly alert files plus rule_changes.csv and daily_summary.csv. Starts 2027-07-16.",
                    "ids_set": ["06_data_streams/gw_host_registry.json"]},
    "zeek_logs": {"path_glob": "05_other_sources/network_logs/zeek/*/*.log", "cadence": "one folder per UTC day: conn, dns, ssl, notice",
                  "notes_add": "Background flows are sampled 1 in 200; flows involving hosts with alerts or remote sessions are complete. Starts 2027-07-16.", "ids_set": ["06_data_streams/gw_host_registry.json"]},
    "host_audit_logs": {"notes_add": "Sixteen tables: remote-access sessions, historian access, device configuration changes, SCADA command log, alarm-suppression audit, file integrity, change management, settings audits, endpoint protection, mail gateways and follow-on logons.",
                        "ids_set": ["06_data_streams/gw_host_registry.json", "06_data_streams/scada_tags.json"]},
    "portal_access_logs": {"notes_add": "aid_portal_access_YYYY-MM.csv and base_logistics_access_YYYY-MM.csv; account_ref is the applications stream's account_id for real accounts.", "ids_set": ["06_data_streams/gw_host_registry.json", "06_data_streams/entity_registry.json"]},
}


def catalog():
    c = load("06_data_streams/stream_catalog.json")
    n = 0
    for s in c["streams"]:
        ch = CAT.get(s["stream_id"])
        if not ch:
            continue
        before = json.dumps(s, sort_keys=True)
        for k in ("path_glob", "cadence", "key_columns", "additional_files"):
            if k in ch:
                s[k] = ch[k]
        if "notes_add" in ch and ch["notes_add"] not in (s.get("notes") or ""):
            s["notes"] = ((s.get("notes") or "").rstrip() + " " + ch["notes_add"]).strip()
        if "ids_set" in ch:
            s["ids_from_registry"] = ch["ids_set"]
        for x in ch.get("ids_add", []):
            if x not in s.setdefault("ids_from_registry", []):
                s["ids_from_registry"].append(x)
        if "span" in ch:
            s.setdefault("required_span", {}).update(ch["span"])
        if json.dumps(s, sort_keys=True) != before:
            n += 1
    c["updated"] = "2026-11-09 (integration pass: family notes merged)"
    if n:
        save("06_data_streams/stream_catalog.json", c)
        log.append(f"stream_catalog: {n} streams updated")


def schema_index():
    p = "06_data_streams/schemas/00_schema_index.json"
    idx = load(p)
    have = {s["file"] for s in idx["schemas"]}
    n = 0
    for fp in sorted(glob.glob(os.path.join(ROOT, "06_data_streams", "schemas", "*.json"))):
        f = os.path.basename(fp)
        if f == "00_schema_index.json" or f in have:
            continue
        d = json.load(open(fp, encoding="utf-8"))
        idx["schemas"].append({"file": f, "source": d.get("stream_id") or d.get("source") or f.replace("_schema.json", ""), "standard": d.get("standard") or d.get("format") or "see file",
                               "entity_catalog": "see 06_data_streams/stream_catalog.json", "verified": True})
        n += 1
    idx["entity_catalog_folder"] = "06_data_streams/"
    if n:
        save(p, idx)
        log.append(f"schema index: +{n} schema files")


PEOPLE = [  # name, kind, org, role, arcs, from_day, bio
    ("Dr. Brennan Calloway-Watts", "worker", "Nueces County Public Health", "Public health officer", ["ARC-HOSP", "ARC-HEALTH"], 15, "Notices the pattern in emergency-department visits that leads to the waterborne-disease investigation."),
    ("Darnell Okafor-Reyes", "worker", "Federal Bureau of Investigation", "Special agent, case lead", ["ARC-FRAUD"], 30, "Case lead on the disaster-fraud investigation; not named publicly."),
    ("Dora Cantu-Espinoza", "hidden", "FastDry Coastal LLC", "Company principal", ["ARC-FRAUD"], 90, "One of two principals of the storm-chasing contractor; named only in charging documents."),
    ("Marcus Whitfield-Yuen", "hidden", "FastDry Coastal LLC", "Company principal", ["ARC-FRAUD"], 90, "One of two principals of the storm-chasing contractor; named only in charging documents."),
    ("Roland Munoz-Estrada", "hidden", "Independent appraiser", "Property appraiser", ["ARC-FRAUD"], 90, "Appraiser tied to the inflated valuations; named only in charging documents."),
    ("Esperanza Orihuela-Martínez", "spokesperson", "League of United Latin American Citizens, local chapter", "Chapter president", ["ARC-BILINGUAL", "ARC-EQUITY"], 0, "Presses FEMA and the state on Spanish-language access during and after the storm."),
    ("Dr. Fatima Al-Rasheed-Obinna", "worker", "Coastal Bend Power and Water Authority", "Chief information security officer", ["ARC-UTILITY-CYBER"], 18, "Receives the anomaly alert, opens the security incident and authorises isolation of the control network."),
    ("Marcus Teitelbaum-Park", "worker", "Vantage Security Systems", "Senior support engineer", ["ARC-UTILITY-CYBER"], 28, "Vendor engineer who helps confirm the remote-access gateway was misused."),
    ("Priya Subramaniam-Nair", "worker", "Texas Division of Emergency Management", "Analyst", ["ARC-DISINFO", "ARC-RUMORS"], 2, "Flags the cluster of coordinated posts internally before it is public."),
    ("Tamara Nguyen-Reeves", "worker", "Corpus Christi Fire Department", "Dispatch operations officer", ["ARC-RESCUE", "ARC-DISPATCH"], 0, "Staffs the forward dispatch position and writes the after-action note on no-find welfare checks."),
]


def people():
    ch = load("01_characters/characters.json")
    have = " | ".join(c["name"] for c in ch["characters"])
    nxt = max(int(c["id"].split("-")[1]) for c in ch["characters"]) + 1
    n = 0
    for name, kind, org, role, arcs, day, bio in PEOPLE:
        if name.split()[-1] in have:
            continue
        ch["characters"].append({"id": f"CHR-{nxt}", "name": name, "kind": kind, "public_facing": False, "affiliation": {"org": org, "org_id": None, "org_is_real": False if kind == "hidden" else True},
                                 "role": role, "home_place_ids": ["PLC-001"], "arcs": arcs, "bio": bio + " Named in the scenario's internal event list only; not to be quoted in news.",
                                 "voice": "n/a", "knowledge_timeline": [], "arc_beats": [], "relationships": [], "constraints": ["Not public: do not name in news stories"], "context_log": []})
        nxt += 1
        n += 1
    if n:
        ch["updated"] = "2026-11-09"
        save("01_characters/characters.json", ch)
        log.append(f"characters: +{n} people named only in the MSEL (not public-facing)")


def network_schema():
    p = "06_data_streams/schemas/10_network_logs_schema.json"
    d = load(p)
    if d.get("revision") == "2026-11-09":
        return
    new = {
        "revision": "2026-11-09", "streams": ["siem_alerts", "zeek_logs", "host_audit_logs", "portal_access_logs"],
        "standard": "Zeek TSV logs; CSV exports from a SIEM, a remote-access gateway, a historian, a change system and a web portal",
        "clock": "All times UTC. Epoch seconds in Zeek logs count from 1970 (2027-09-14T00:00:00Z is 1820880000). Records in different systems that describe the same action agree to within a few seconds; log evidence of a session or write precedes its effect.",
        "sampling": "Zeek background flows are sampled 1 in 200. Flows involving any host that has an alert or a remote-access session are complete. SIEM alerts are complete (daily counts are real counts).",
        "span": "2027-07-16T00:00Z to 2028-01-12T06:00Z",
        "files": {
            "network_logs/siem/siem_alerts_YYYY-MM.csv": ["alert_id", "time_utc", "rule_id", "rule_name", "category", "priority", "src_host", "src_ip", "dst_host", "dst_ip", "dst_port", "user", "detail", "disposition", "closed_utc", "closed_by", "close_note"],
            "network_logs/siem/rule_changes.csv": ["time_utc", "action", "rule_id", "rule_type", "description", "changed_by", "change_ticket"],
            "network_logs/siem/daily_summary.csv": ["date_utc", "alerts", "closed_false_positive", "false_positive_rate_pct", "open_ml_anomaly_alerts"],
            "network_logs/zeek/YYYY-MM-DD/conn.log": "standard Zeek conn fields", "network_logs/zeek/YYYY-MM-DD/dns.log": "standard Zeek dns fields",
            "network_logs/zeek/YYYY-MM-DD/ssl.log": "ts, uid, id.*, version, cipher, server_name, resumed, established", "network_logs/zeek/YYYY-MM-DD/notice.log": "standard Zeek notice fields",
            "network_logs/audit/remote_access_sessions.csv": ["session_id", "gateway", "account", "src_ip", "src_network", "src_country", "login_utc", "logout_utc", "duration_s", "bytes_out", "bytes_in", "auth_method", "target_hosts", "change_ticket"],
            "network_logs/audit/historian_access.csv": ["session_id", "server", "account", "client_host", "start_utc", "end_utc", "duration_s", "tags_queried", "tag_groups", "query_type"],
            "network_logs/audit/ot_config_changes.csv": ["time_utc", "device", "parameter", "old_value", "new_value", "change_type", "session_user", "source_host", "change_ticket"],
            "network_logs/audit/scada_command_log.csv": ["time_utc", "scada_server", "workstation", "operator", "command", "device", "result", "session_context"],
            "network_logs/audit/alarm_suppression_audit.csv": ["time_utc", "system", "action", "alarm_point", "category", "changed_by", "source_host", "change_ticket", "active_suppressions_after"],
            "network_logs/audit/file_integrity.csv": ["time_utc", "host", "path", "event", "previous_hash", "new_hash", "user", "source_host", "diff_summary"],
            "network_logs/audit/change_management.csv": ["time_utc", "record_id", "record_type", "summary", "owner", "status"],
            "network_logs/audit/settings_audits.csv": ["time_utc", "audit", "device", "site", "item", "found", "record_value", "record_date", "result"],
            "network_logs/audit/endpoint_protection.csv": ["time_utc", "host", "ip", "event", "detail", "initiated_by"],
            "network_logs/audit/mail_gateway_*.csv": ["time_utc", "gateway", "direction", "sender", "sender_domain", "recipient", "subject", "attachment_names", "size_bytes", "verdict", "action", "message_id"],
            "network_logs/audit/mail_url_clicks_*.csv": "time_utc, gateway, mailbox, url_host, client_ip (+ message_id, sender_network for the vendor gateway)",
            "network_logs/audit/account_logons_city_airstation.csv": ["time_utc", "service", "account", "src_ip", "src_network", "result", "auth_method", "device"],
            "network_logs/portal/aid_portal_access_YYYY-MM.csv": ["time_utc", "system", "client_ip", "client_network", "method", "path", "status", "event", "account_ref", "user_agent_family", "bytes"],
            "network_logs/portal/base_logistics_access_YYYY-MM.csv": "same columns"},
        "ids": "Host names, addresses, users and equipment come from gw_host_registry.json; account_ref in the aid portal log is the account_id of payments/aid_applications.csv.",
        "generator": "scripts/streams/gen_itsec.py (parts: siem, zeek, audit, portal); probes in scripts/streams/probes_itsec.py",
    }
    save(p, new)
    log.append("10_network_logs_schema.json rewritten for the regenerated streams")


if __name__ == "__main__":
    catalog(); schema_index(); people(); network_schema()
    print("\n".join(log) if log else "nothing to change")
