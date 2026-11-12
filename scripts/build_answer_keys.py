"""Write 06_answer_key/answer_key.json: for every thread, the question, the chain of observations
a team has to join, the join keys, the conclusion and a difficulty rating.

Steps are taken from canon_timeline.json -> expected_observations (so each step is something a
probe verifies on disk); the question, conclusion, key joins and difficulty are written here.
Internal only: never ship this folder with released data.

    python3 scripts/build_answer_keys.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


# what a stream can be joined on
KEYS = {
    "ais": ["mmsi", "time", "position"], "port_surveillance": ["mmsi", "time", "position", "berth_id", "sensor_id"], "port_conditions": ["time", "segment_id", "mmsi", "terminal_id"],
    "port_arrivals": ["mmsi", "berth_id", "terminal_id", "time"], "cargo_manifests": ["mmsi", "supplier_id", "arrival_id"], "fuel_deliveries": ["supplier_id", "facility_id", "lot_id", "contract_id", "time"],
    "adsb": ["icao24", "time", "position"], "drone_detections": ["sensor_id", "time", "position", "authorization_id"], "drone_telemetry": ["operator_id", "mission_name", "time", "position", "asset_id"],
    "satellite": ["time", "position"], "damage_assessment": ["asset_id", "census_tract", "time", "position"], "avl": ["unit_id", "incident_number", "time", "position"],
    "cad_911": ["incident_number", "unit_id", "census_tract", "time", "position", "callback_number"], "sar_missions": ["asset_id", "incident_number", "census_tract", "time", "position"],
    "shelters": ["facility_id", "time"], "eas_alerts": ["alert_id", "area_id", "time"], "broadcast_logs": ["alert_id", "station_id", "time"], "social_media": ["screen_name", "time", "url", "text"],
    "news": ["time", "text"], "public_record": ["time", "text"], "weather": ["station_id", "time"], "storm_advisories": ["time"], "tide_river_gauges": ["sensor_id", "time"],
    "water_quality": ["sensor_id", "time"], "air_quality": ["sensor_id", "time"], "wastewater": ["site_id", "time"], "ed_visits": ["facility_id", "census_tract", "time", "language"],
    "hospital_capacity": ["facility_id", "time"], "syndromic": ["facility_id", "area_id", "time"], "scada_historian": ["tagname", "time"], "outage_map": ["area_id", "substation_id", "time"],
    "work_orders": ["asset_id", "vendor_id", "time"], "base_status_reports": ["facility_id", "equipment_id", "time"], "siem_alerts": ["host", "user", "alert_id", "time"],
    "zeek_logs": ["ip", "time"], "host_audit_logs": ["host", "user", "session_id", "time"], "portal_access_logs": ["account_id", "ip", "time"], "vessel_ot_logs": ["mmsi", "session_id", "time"],
    "contracts": ["supplier_id", "piid", "bank_account_id", "area_id"], "financial_transactions": ["account_id", "counterparty_id", "time"], "aid_applications": ["account_id", "area_id", "census_tract", "ip", "time"],
    "insurance_claims": ["holder_id", "policy_id", "area_id", "time"], "census": ["census_tract", "area_id"],
}

T = {
 "T1": ("How did a hurricane turn into five weeks without safe tap water?",
        "Natural cascade: surge and wind take both power feeds to the water plant, pumps fail, pressure drops citywide, a boil-water notice follows and stomach illness rises; replacement pump parts are delayed because the supplier's warehouse flooded and the port is closed. No adversary.",
        "medium", ["weather and gauges -> scada_historian by time", "scada_historian tag -> work_orders asset_id", "work_orders vendor_id -> cargo_manifests supplier_id -> port_arrivals mmsi", "eas_alerts area_id -> ed_visits/syndromic by area and day"]),
 "T2": ("Whose fuel fouled the air station's generator?",
        "A tanker goes dark at the offshore anchorage while another boat's identity appears beside it; fuel moves to a barge and is delivered under the emergency fuel contract; the generator later fails on that lot.",
        "hard", ["ais mmsi gap + port_surveillance radar contact with no AIS at the same place and time", "ais identity seen in two places (shore feed vs satellite feed)", "fuel_deliveries lot_id/contract_id -> contracts supplier_id -> base_status_reports equipment_id"]),
 "T3": ("Are the debris contractor and the fuel supplier connected?",
        "Two emergency contractors share a registered address, a bank account and (later, in filings) an owner; one bills 2.3 times the surveyed debris tonnage; both receive diverted aid payments.",
        "hard", ["contracts_vendor_registry bank_account_id shared by two supplier_id", "contracts_invoices quantity vs contracts_debris_monitoring estimated tons by area and period", "financial_transactions counterparty/account -> the same accounts"]),
 "T4": ("Who took over 410 aid accounts, and was it planned?",
        "One network probes the aid portal weeks before the storm, sends the phishing wave after landfall, then runs automated sign-in attempts and changes deposit details on 410 accounts; the rumor accounts link to the same lookalike site.",
        "hard", ["portal_access_logs client network in August, September and November", "portal_access_logs account_ref = aid_applications account_id (deposit changes) -> financial_transactions account_id", "social_media url host = mail gateway sender domain in host_audit_logs"]),
 "T5": ("Did every neighborhood get the same help?",
        "Low-income surge-zone tracts wait about twice as long for a unit and receive about half their share of aid dollars; the cause is access and distance, not an adversary.",
        "medium", ["cad_911 census_tract -> census income quartile; response time = first_arrival - call_received", "aid_applications tract dollars vs census population", "avl unit travel vs bridge and road closures"]),
 "T6": ("Why did two moored tankers spill 9,000 barrels as the storm arrived?",
        "A vendor's remote-maintenance account connects to both ships' cargo-control systems from an unfamiliar network and opens cargo valves from 04:00Z to 05:30Z on landfall night while alarms are silenced; the crews close them by hand.",
        "medium", ["vessel_ot_logs remote session_id -> valve command records on both mmsi", "vessel_ot_logs time -> water_quality nearest sonde within the hour", "port_surveillance cameras/berth_id and ais mmsi: the ships never move"]),
 "T7": ("Was the channel blast an accident?",
        "Drone overflights of the air station while its sensors are down, a vessel loitering dark off the entrance channel two weeks before the blast, GPS interference traced to a parked transmitter during the relief airlift, and then a device beside a tug: one actor using the storm to hold the port shut.",
        "hard", ["drone_detections sensor status + sighting reports on the same nights", "ais gap + port_surveillance radar track near the entrance channel -> position of the blast (ais tug mmsi, cad_911 incident)", "adsb nic/nac_p degradation by time and distance from one point"]),
 "T8": ("Why did parts of the city lose power again after the storm?",
        "Someone using an engineer's credentials from outside Texas changed a relay threshold and a relay file during the storm-preparation freeze and later opened two breakers; the outages look like storm damage but the commands have no operator and no work order.",
        "hard", ["host_audit_logs remote_access_sessions time window -> ot_config_changes / scada_command_log in the same window", "scada_historian setting tag change time = config change time (to the second)", "outage_map substation_id re-outage time = command time; work_orders: no matching order", "damage_assessment utility survey: breaker open with no storm damage"]),
 "T9": ("Why did Districts 3 and 4 lose water pressure two weeks after the storm?",
        "A pump setpoint and a booster setpoint are lowered in one late-night remote session and the low-pressure alarms are suppressed; pressure in the zone falls slowly until a field operator notices and the boil-water notice is issued; illness follows, worst where the Spanish notice arrived late.",
        "hard", ["scada_historian setpoint tags step at 02:04Z/02:08Z = ot_config_changes rows = remote session window", "alarm_suppression_audit adds -> no low-pressure alarm in historian", "eas_alerts English vs Spanish release -> ed_visits by language and tract"]),
 "T10": ("How did the intrusion stay hidden for six weeks?",
        "Every action is timed to look like storm effects: changes during the freeze, commands during restoration switching, alerts auto-acknowledged by an exception rule created weeks earlier, analysts in storm mode bulk-dismissing the rest.",
        "expert", ["siem rule_changes (exception rule, storm mode) -> dispositions of the alerts that mattered", "siem_alerts time = remote session time = historian change time", "zeek periodic outbound connection first/last seen vs isolation day"]),
 "T11": ("Does the aerial imagery agree with the utility's account of the outages?",
        "Survey passes over the substations show open breakers in yards with no flood or wind damage, first at one substation and after the second command at another; thermal readings show equipment that cooled without a fault.",
        "medium", ["drone_telemetry mission_name/tile set -> damage_assessment utility_site_survey asset_id", "thermal_survey_readings asset_id -> outage_map substation_id and time", "adsb icao24 of the survey aircraft -> flight log"]),
 "T12": ("What did the port's own sensors see?",
        "Cameras and radar give an independent record: the two tankers intact at the berth until the cameras lose power; later, radar holds a contact with no AIS where the anchored tanker reports a gap, and a small craft leaves it toward the entrance channel.",
        "medium", ["port_surveillance camera berth_id/time vs vessel_ot_logs", "port_surveillance radar track with ais_correlated = false vs ais gap for the mmsi at that position", "port_conditions segment status at the time"]),
 "T13": ("What does the 911 record say about the storm, hour by hour?",
        "Volume peaks the day after landfall, rescue calls the day after that; a cluster of calls near utility sites with no victims comes from prepaid numbers; the boil-water day produces its own surge of non-emergency calls.",
        "easy", ["cad_911 daily counts vs cbecc_daily_call_volume", "cad_911 callback_number -> ali_subscriber_records class of service", "cad_911 incident_number -> sar_missions / avl"]),
 "T14": ("How late were the Spanish-language warnings, and did it matter?",
        "Spanish versions of alerts trail the English by hours every time and by more than twelve hours for the Districts 3 and 4 boil-water notice; Spanish-speaking households in those districts show the earliest and largest rise in stomach illness.",
        "medium", ["eas_alerts ReleasedAt_EN vs ReleasedAt_ES by alert_id", "broadcast_logs translation_jobs alert_id -> first_aired", "ed_visits Preferred_Language and Patient_Tract by day after the notice"]),
 "T15": ("Were the rumors organic?",
        "About forty accounts created in the same weeks post the same sentences in the same fifteen-minute slots, push the false home-seizure and refinery-negligence stories and a lookalike aid site, and go silent the day the platforms announce removals; a second set wakes up later.",
        "medium", ["social_media text reuse + created_at slots by screen_name", "social_media url host -> the lure domain in mail logs", "_platform_records_return account status dates"]),
 "T16": ("What pushed the hospitals past capacity twice?",
        "First the storm (trauma, generator power, a fuel scare), then a stomach-illness wave from the water system that is larger at the hospital serving Districts 3 and 4 and among Spanish-speaking patients.",
        "medium", ["hospital_capacity by facility_id and day", "ed_visits CC_Category by tract and language", "fuel_deliveries facility_id tank dips; outage_map feeder to the hospital"]),
 "T17": ("Who was rescued, where, and by whom?",
        "About 1,400 rescues in five days, concentrated in Flour Bluff, North Beach and Calallen; helicopters hoist where boats cannot reach; some welfare checks near utility sites find no one.",
        "easy", ["sar_missions asset_id -> adsb icao24 / avl unit_id", "sar_missions incident_number -> cad_911", "flood_depth_soundings by tract"]),
 "T18": ("What did the security operations centre see, and when could it have known?",
        "The first outbound connection is alerted and closed as a false positive; the historian sessions are auto-acknowledged by an exception rule nobody approved; storm mode dismisses three alerts that mattered; the anomaly model finally flags the fourteenth session.",
        "hard", ["siem_alerts alert family by time -> disposition and closer", "rule_changes created_by and ticket -> historian_access account", "zeek conn/ssl for the alerted destination"]),
 "T19": ("Who was flying drones over the substation and the docks before the storm?",
        "Detections with no authorization on five evenings before landfall over one substation and the tanker berth, and on six nights after landfall over the air station while its sensors were degraded; bearings from two sensors cross at a marina berth.",
        "hard", ["drone_detections authorization_id empty vs laanc_authorizations", "bearing lines from two sensor_id at the same time -> a position", "that position -> terminal_registry slip -> ais mmsi berthed there"]),
 "T20": ("Where did the oil go, and who breathed it?",
        "Hydrocarbons rise first at the sonde beside the berth within the hour of the valve opening, then at the bay sondes over two days; downwind air monitors and nearby emergency rooms show the same footprint.",
        "easy", ["vessel_ot_logs valve time -> water_quality sensor_id order of arrival", "air_quality sensor_id by wind direction (weather)", "syndromic area_id respiratory and skin complaints"]),
 "T21": ("Did every alert reach every station?",
        "Each official alert can be followed from issue to relay to air; one relay station lags every time, most stations are off the air through landfall, and the Spanish station learns of the Districts 3 and 4 notice the next morning.",
        "easy", ["eas_alerts alert_id -> broadcast alert_relay_log -> station_program_log", "station_status_log off-air windows"]),
 "T22": ("Which storm claims were never real?",
        "One property company holds policies whose replacement values were raised months before the storm through the same broker and appraisers, files 187 near-identical claims within days through a small set of adjusters, and a storm-chasing contractor's invoices support them.",
        "hard", ["insurance_claims policy_transaction (pre-storm value increases) -> claim by holder_id/policy_id", "claims text reuse and adjuster_id concentration", "aid_applications and contracts supplier_id for the contractor"]),
}
ID_RE = re.compile(r"\b(?:GW-[A-Z0-9]+(?:-[A-Z0-9]+)+|GW\.[A-Z0-9.]+|EXT-[A-Z]+-[A-Z0-9-]+|VSL-\d{4}|BRG-\d{4}|TERM-\d{2}(?:-B\d{2})?|SLIP-[A-Z]+-\d+|ANCH-\d+|FAC-[A-Z]+-\d{3}|WQ-\d{2}|GAUGE-\d{2}|AQS-[0-9A-Z-]+|ORG-\d{4}|VND-\d{4}|ACCT-\d+|EQP-\d{4}|SE3-[A-Z]+-\d{4}-\d{8}T\d{4}Z|HIST-\d{8}-\d{5}|OUT-\d{2}|AREA-[A-Z0-9-]+|IPAWS-[A-Z0-9-]+|[A-Z]{2,5}-\d{3,4}(?!\d))")


def main():
    threads = load("00_scenario/threads.json")
    tl = load("00_scenario/canon_timeline.json")
    obs = tl["expected_observations"]["items"]
    cat = {s["stream_id"]: s for s in load("06_data_streams/stream_catalog.json")["streams"]}
    old = load("06_answer_key/answer_key.json")
    out_threads, paths = [], []
    for th in threads:
        tid = th["thread_id"]
        q, concl, diff, joins = T[tid]
        mine = sorted([o for o in obs if tid in o["threads"]], key=lambda o: (o["start_utc"], o["event_id"], o["stream"]))
        data = [o for o in mine if o["stream"] not in ("news", "public_record")]
        pub = [o for o in mine if o["stream"] in ("news", "public_record")]
        chosen = data if len(data) >= 4 else data + pub
        steps, seen = [], set()
        for o in chosen:
            k = (o["event_id"], o["stream"])
            if k in seen:
                continue
            seen.add(k)
            steps.append(o)
        steps = steps[:16]
        js = []
        for i, o in enumerate(steps):
            nxt = steps[i + 1] if i + 1 < len(steps) else None
            if nxt and nxt["stream"] != o["stream"]:
                shared = [k for k in KEYS.get(o["stream"], []) if k in KEYS.get(nxt["stream"], [])]
                jn = f"to {nxt['stream']} on " + (", ".join(shared) if shared else "time window and place")
            elif nxt:
                jn = f"next record in {o['stream']} by time"
            else:
                jn = None
            js.append({"n": i + 1, "observation": {"event_id": o["event_id"], "stream": o["stream"]}, "files": cat[o["stream"]].get("path_glob"),
                       "window_utc": [o["start_utc"], o["end_utc"]], "look_for": o["what"], "entity_ids": sorted(set(ID_RE.findall(o["what"])))[:12], "join_to_next": jn})
        streams = sorted({s["observation"]["stream"] for s in js})
        out_threads.append({"thread_id": tid, "name": th["name"], "question": q, "difficulty": diff, "streams": streams, "key_joins": joins, "steps": js, "conclusion": concl,
                            "public_from": sorted({o["event_id"] for o in pub})[:8], "observations_total": len(mine)})
        paths.append({"thread_id": tid, "name": th["name"], "join_path": " → ".join(f"{s['observation']['stream']} ({s['observation']['event_id']})" for s in js), "evidence": concl})
    out = {"_about": "Internal. Built by scripts/build_answer_keys.py from the expected observations; every step is checked on disk by scripts/check_answer_keys.py.",
           "threads": out_threads, "paths": paths, "links_between_threads": old.get("links_between_threads"), "meta_join_gridwater": old.get("meta_join_gridwater")}
    with open(os.path.join(ROOT, "06_answer_key", "answer_key.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"answer keys: {len(out_threads)} threads, {sum(len(t['steps']) for t in out_threads)} steps")


if __name__ == "__main__":
    main()
