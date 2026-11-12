"""Documentation, schemas, geo rules and catalogue notes for the maritime stream family.

Called by gen_maritime.py as the last stage; everything here is derived from the files on disk
and the registries, so it can be re-run on its own:

    python3 -c "import sys; sys.path.insert(0,'scripts/streams'); import maritime_docs as m; m.write_all()"
"""
import csv
import glob
import json
import os

from common import ROOT

AIS_DIR = "05_other_sources/ais"
SURV_DIR = "05_other_sources/port_surveillance"
SUP_DIR = "05_other_sources/supply"


def _p(rel):
    return os.path.join(ROOT, rel)


def _header(rel):
    with open(_p(rel), encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def _rows(pattern):
    n = 0
    for fp in glob.glob(_p(pattern)):
        with open(fp, "rb") as fh:
            n += sum(1 for _ in fh) - 1
    return n


def _dump(rel, obj):
    os.makedirs(os.path.dirname(_p(rel)), exist_ok=True)
    with open(_p(rel), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def F(name, typ, example, notes):
    return {"name": name, "type": typ, "example": example, "notes": notes}


# ------------------------------------------------------------------------------------------ AIS
AIS_README = """# AIS vessel positions

Automatic Identification System reports for the Port of Corpus Christi and its approaches,
2027-08-15 to 2028-01-12, in the column layout of the USCG NAIS / MarineCadastre CSV. All times UTC.

## Files

| Files | What | Rows |
|---|---|---|
| `ais_YYYY-MM.csv` | Shore-station feed: every report received by the coastal receiver network at the harbour entrance. Reception reaches about 45 nautical miles offshore. One file per calendar month. | {n_shore:,} |
| `satellite/sais_YYYY-MM.csv` | Satellite-received feed for the same months: reports from vessels beyond shore range, out to the edge of the Gulf area this corpus covers. Sparser (about one report every 30 to 60 minutes per vessel). | {n_sat:,} |

The two feeds are separate products from separate receivers and are not merged or de-duplicated.

## Columns

`MMSI, BaseDateTime, LAT, LON, SOG, COG, Heading, VesselName, IMO, CallSign, VesselType, Status, Length, Width, Draft, Cargo, TransceiverClass, Destination`

* `BaseDateTime` is UTC, ISO 8601, no zone suffix.
* `LAT`, `LON` are WGS-84 decimal degrees to five places (about one metre).
* `SOG` knots, `COG` and `Heading` degrees true; `Heading` 511 means the unit has no heading input.
* `Status` is the navigational status entered on the bridge: 0 under way, 1 at anchor, 3 restricted in ability to manoeuvre, 5 moored, 7 fishing, 15 not defined. Class B units do not send a status, a draft or a destination (15 and blank).
* `Draft` is metres, as entered by the crew for the voyage.
* `Destination` is the free-text field typed into the transponder (a UN/LOCODE, a port name, or whatever the watch officer wrote).
* Name, call sign, IMO number, type and dimensions are the static data broadcast by the unit itself. `MMSI` joins `06_data_streams/vessels.json`.

Full field notes: `06_data_streams/schemas/01_ais_schema.json`.

## Reporting interval

| Where | Interval |
|---|---|
| Dredged channels, harbours, the ferry crossing | about 1 minute, plus a report at each alteration of course |
| Open bay and the approach inside the sea buoy | about 5 minutes |
| Offshore, within shore-station range | about 30 minutes |
| Moored | about 60 minutes (and at arrival and departure) |
| At anchor | about 6 minutes |
| Working on station (dredge, survey, response craft holding position) | about 15 minutes |

Real transponders report more often than this; the feed is thinned the way archived AIS products are.
A straight line drawn between two consecutive reports less than 30 minutes apart does not cross land.

## What the feed does not contain

* A vessel that sails beyond receiver range stops appearing; it reappears when it returns. Voyages are not followed to the far port.
* A unit that is switched off, out of range, or not fitted sends nothing. There are no placeholder rows and no gap markers: an absence of reports is simply an absence of rows.
* Barges without their own transponder, small recreational boats and some workboats never appear here. Radar and camera contacts for the port are in `05_other_sources/port_surveillance/`.
* Small-craft routes follow open water with a margin from the shore; they are not depth-aware outside the charted channels.
* Boats berthed deep inside the municipal marina show a short reporting gap between their slip and the marina entrance.

## Related data

* Berths, slips, anchorage positions: `06_data_streams/terminal_registry.json`
* Port calls and cargo: `05_other_sources/supply/vessel_arrivals.csv`, `cargo_manifest.csv`
* Captain of the Port orders and channel status: `05_other_sources/supply/port_conditions.csv`

## How it is produced

`python3 scripts/streams/gen_maritime.py` (deterministic; see `scripts/streams/README.md`).
Geography check: `python3 scripts/check_geo.py --only=AIS`. On the full feed that takes most of an
hour; `python3 scripts/streams/run_check_geo_maritime.py` runs the same checker over the same rows in
resumable pieces.
"""

SURV_README = """# Port surveillance: radar, cameras, vessel traffic log

Sensor logs kept by the port and the Coast Guard for the Corpus Christi Ship Channel,
2027-08-15 to 2028-01-12. All times UTC.

| File | What | Rows |
|---|---|---|
| `sensors.csv` | The sensors: two radar buoys, fourteen fixed cameras, the vessel traffic service log. Positions and the berths each camera covers. | {n_sensors:,} |
| `radar_tracks_YYYY-MM.csv` | Radar plots from the two buoys, one row per plot, about every two minutes while a contact is held (every 30 minutes for a stationary contact). | {n_radar:,} |
| `camera_events.csv` | Camera log: a routine frame summary every few hours and an event row whenever a vessel passes, berths or leaves. | {n_cam:,} |
| `vessel_traffic_log.csv` | Vessel traffic service checkpoint log: each passage of the jetties, the Harbor Bridge and the other reporting points, with pilot and tug assignments where a pilot was ordered. | {n_vts:,} |
| `sensor_status.csv` | Hourly health of every sensor, plus a row at each change. | {n_status:,} |

## Reading the radar table

* A radar holds a contact whether or not the vessel has AIS. `ais_correlated` is `Y` when the tracker matched the plot to an AIS report received at the same time, and `correlated_mmsi` is then the MMSI it matched. `N` means no AIS report was matched: the hull has no transponder, or was not transmitting, or was transmitting from somewhere else.
* `track_id` is the tracker's own number. A contact that is lost and picked up again gets a new one.
* `est_length_m` is estimated from the echo; the stated error is 10 percent for ships, more for small craft.
* `ingest_utc` is when the plot reached the shore archive. It is normally a few seconds after `time_utc`; plots recovered later from a buoy's onboard buffer carry their original `time_utc` and a later `ingest_utc`.
* Plot positions carry a few metres of noise.
* In very heavy weather the trackers also log short-lived small contacts (breaking seas, drifting debris).
* Each buoy sees only water in its line of sight; neither sees into the Inner Harbor.

## Reading the camera and traffic logs

* `camera_events.csv` `vessels_in_view` lists what the operator or the analytics saw at the berths in the camera's view; `water_surface` is the operator's description of the water.
* Rows are written only while the sensor is working. Outages appear in `sensor_status.csv` and as missing rows.

Field notes: `06_data_streams/schemas/port_surveillance_schema.json`.
Produced by `python3 scripts/streams/gen_maritime.py`.
"""


def write_readmes():
    n = dict(n_shore=_rows(f"{AIS_DIR}/ais_*.csv"), n_sat=_rows(f"{AIS_DIR}/satellite/sais_*.csv"))
    with open(_p(f"{AIS_DIR}/README.md"), "w", encoding="utf-8") as fh:
        fh.write(AIS_README.format(**n))
    m = dict(n_sensors=_rows(f"{SURV_DIR}/sensors.csv"), n_radar=_rows(f"{SURV_DIR}/radar_tracks_*.csv"), n_cam=_rows(f"{SURV_DIR}/camera_events.csv"),
             n_vts=_rows(f"{SURV_DIR}/vessel_traffic_log.csv"), n_status=_rows(f"{SURV_DIR}/sensor_status.csv"))
    with open(_p(f"{SURV_DIR}/README.md"), "w", encoding="utf-8") as fh:
        fh.write(SURV_README.format(**m))
    return {**n, **m}


# ------------------------------------------------------------------------------------------ schemas
def write_ais_schema():
    rel = "06_data_streams/schemas/01_ais_schema.json"
    d = json.load(open(_p(rel), encoding="utf-8"))
    d["folder"] = "05_other_sources/ais/"
    d["notes"] = ("CamelCase headers as in the MarineCadastre product, plus the transponder's Destination field. "
                  "BaseDateTime is UTC ISO 8601 without a zone suffix. SOG in knots, COG/Heading in degrees true. "
                  "One row per received position report; static fields are repeated on every row as broadcast.")
    d["files"] = {
        "ais_YYYY-MM.csv": "Shore-station feed, one file per calendar month (2027-08 to 2028-01). Reception to about 45 nm offshore.",
        "satellite/sais_YYYY-MM.csv": "Satellite-received feed, same columns, for positions beyond shore range to the edge of the Gulf area covered. Kept in a subfolder: it is a separate product from a separate receiver and is not merged with the shore feed.",
        "README.md": "Plain-language description of the feed, the reporting intervals and what is absent.",
    }
    fields = [f for f in d["fields"] if f["name"] != "Destination"]
    for f in fields:
        if f["name"] == "MMSI":
            f["notes"] = ("9-digit MMSI as broadcast; the first three digits are the flag's maritime identification digits. Joins vessels.json mmsi. "
                          "Hulls with no transponder (vessels.json transceiver_class null) never appear.")
        if f["name"] == "Status":
            f["notes"] = "0=under way using engine, 1=at anchor, 3=restricted manoeuvrability, 5=moored, 7=engaged in fishing, 15=not defined (all Class B units)"
        if f["name"] == "Draft":
            f["notes"] = "Draught in metres as entered for the voyage; between vessels.json draft_ballast_m and draft_m. Blank for Class B. check_geo treats 9 m or more as deep-draft."
        if f["name"] == "Heading":
            f["notes"] = "True heading 0-359; 511 = not available (common on Class B units)"
    fields.append(F("Destination", "string", "USCRP", "Free text typed into the transponder (max 20 characters): usually a UN/LOCODE or port name. Blank for Class B."))
    d["fields"] = fields
    d["scenario_notes"] = {
        "coverage": "2027-08-15T00:00Z to 2028-01-12T06:00Z. All times UTC.",
        "reporting_interval": "About 1 minute in the dredged channels and harbours (plus a report at each course alteration), 5 minutes in open bay and on the approach, 30 minutes offshore, 60 minutes moored, 6 minutes at anchor, 15 minutes working on station. Consecutive reports less than 30 minutes apart never have land between them.",
        "coverage_limits": "A vessel beyond receiver range, switched off or not fitted produces no rows. There are no gap markers.",
        "geography": "Positions pass scripts/check_geo.py rule \"vessel\": never on land; deep-draft ships inside the port only in reaches maintained to 40 ft or more (within 150 m, which covers the berths in terminal_registry.json), in the anchorage, or seaward of the sea buoy. Deep-draft ships follow geo.nav.route, small craft geo.water.route.",
        "port_state": "Movement follows the Captain of the Port orders in 05_other_sources/supply/port_conditions.csv.",
        "consistency": "Every berthing in 05_other_sources/supply/vessel_arrivals.csv appears here as the same vessel moored at that berth for the same period.",
    }
    _dump(rel, d)


ARRIVAL_NOTES = {
    "arrival_id": ("string", "NOA-2027-CC-18441", "Notice of arrival reference; primary key; cargo_manifest.csv arrival_id joins here"),
    "vessel_name": ("string", "PERMIAN SUN", "Name as submitted on the notice (upper case, no MT/MV prefix)"),
    "mmsi": ("string", "636203266", "9-digit MMSI; joins vessels.json and the AIS feed"),
    "imo_number": ("string", "IMO9290880", "IMO number with prefix"),
    "call_sign": ("string", "D5BA7", "Radio call sign"),
    "flag_state": ("string", "Liberia", "Flag state"),
    "vessel_type": ("string", "Crude oil tanker (Suezmax)", "Vessel type as declared"),
    "port_of_arrival": ("string", "USCRP", "UN/LOCODE of the port of arrival (Corpus Christi)"),
    "terminal": ("string", "Inner Harbor Crude Export Terminal", "terminal_registry.json terminal_name; blank if the vessel never berthed"),
    "terminal_id": ("string", "TERM-17", "terminal_registry.json terminal_id"),
    "berth_id": ("string", "TERM-17-B01", "terminal_registry.json berth_id of the first berth used"),
    "anchorage_position_id": ("string", "ANCH-02", "terminal_registry.json anchorage position used while waiting offshore; blank if the vessel went straight in"),
    "draft_arrival_m": ("float", "8.4", "Arrival draught in metres"),
    "port_of_departure": ("string", "ESALG", "Last port (UN/LOCODE)"),
    "next_port": ("string", "ESALG", "Declared next port (UN/LOCODE)"),
    "noa_submitted_datetime": ("datetime", "2027-08-04T10:49:57Z", "When the notice of arrival was filed, UTC"),
    "eta_datetime": ("datetime", "2027-08-09T01:04:42Z", "Estimated arrival at the sea buoy on the original notice, UTC"),
    "eta_revised_datetime": ("datetime", "", "Revised estimate if the notice was updated; blank otherwise"),
    "ata_anchorage_datetime": ("datetime", "2027-08-08T22:56:46Z", "Time anchored offshore, UTC; blank if the vessel did not anchor"),
    "ata_datetime": ("datetime", "2027-08-13T15:30:42Z", "All fast at the berth, UTC; blank if not yet berthed at the end of the data"),
    "atd_datetime": ("datetime", "2027-08-15T06:20:00Z", "Departure from the berth, UTC; blank if still alongside at the end of the data"),
    "voyage_number": ("string", "2027-PS-170", "Carrier voyage number"),
    "agent": ("string", "Gulf Coast Marine Agency", "Ship's agent (fictional)"),
    "noa_status": ("string", "DEPARTED", "State of the call at the end of the data: DEPARTED, IN PORT, REMAINING IN PORT, AT ANCHORAGE, CANCELLED (the vessel did not call: diverted or voyage withdrawn)"),
    "hold_log": ("string", "", "Dated entries the agent added to the notice while the vessel waited (port closed, berth occupied, order numbers)"),
    "shift_berth_id": ("string", "", "Second berth if the vessel shifted within the port"),
    "shift_datetime": ("datetime", "", "Time of the shift, UTC"),
}
MANIFEST_NOTES = {
    "manifest_id": ("string", "MAN-27-000002", "Manifest line number; primary key"),
    "bl_id": ("string", "BL-CE-2027-8340", "Bill of lading or air waybill number"),
    "bl_type": ("string", "Master", "Master or House"),
    "mode": ("string", "SEA", "SEA, AIR or ROAD"),
    "direction": ("string", "IMPORT", "IMPORT, EXPORT or DOMESTIC"),
    "arrival_id": ("string", "NOA-2027-CC-18092", "vessel_arrivals.csv arrival_id for sea cargo; blank for air cargo"),
    "mmsi": ("string", "538008157", "Carrying vessel's MMSI (vessels.json); blank for air cargo"),
    "vessel_name": ("string", "CAPEHORN EAGLE", "Carrying vessel, or the flight / aircraft for air cargo"),
    "carrier": ("string", "Capehorn Bulk Carriers Ltd.", "Carrier (fictional)"),
    "cargo_description": ("string", "IRON ORE PELLETS", "Commodity description as manifested"),
    "hs_commodity_code": ("string", "2601.12", "Harmonized System code"),
    "quantity": ("float", "55500", "Quantity in unit_of_measure"),
    "unit_of_measure": ("string", "MT", "BBL barrels, MT metric tons, M3 cubic metres, PALLET, CONTAINER (40 FT), LOT, SHIPMENT"),
    "cargo_weight_kg": ("integer", "55500000", "Gross weight in kilograms"),
    "shipper_name": ("string", "Capehorn Bulk Carriers Ltd.", "Shipper (fictional)"),
    "supplier_id": ("string", "VND-0006", "entity_registry.json id where the shipper is a registered supplier; blank otherwise"),
    "consignee_name": ("string", "Portland Reduction Works", "Consignee (fictional); TO ORDER for negotiable export bills"),
    "consignee_id": ("string", "", "entity_registry.json id where the consignee is a registered entity; blank otherwise"),
    "port_of_lading": ("string", "Santos", "Port or airport of lading"),
    "port_of_discharge": ("string", "Corpus Christi, TX", "Port or airport of discharge"),
    "booking_date": ("date", "2027-08-01", "Date the consignment was booked. All dates in this file are calendar dates at the port (US Central time)"),
    "planned_arrival_date": ("date", "2027-08-10", "Arrival date promised at booking"),
    "arrival_date": ("date", "2027-08-11", "Date the cargo actually arrived (vessel berthed or aircraft landed); blank if it has not arrived"),
    "release_date": ("date", "2027-08-15", "Date released to the consignee or, for exports, the sailing date; blank if not released"),
    "hazmat_flag": ("string", "N", "Y/N"),
    "un_number": ("string", "", "UN number for hazardous cargo (UN1267 crude oil, UN1972 LNG, UN1203 gasoline, UN1202 diesel)"),
    "container_numbers": ("string", "", "Container numbers, semicolon-separated; blank for bulk cargo"),
}
CONDITION_NOTES = {
    "order_id": ("string", "MSIB 27-031", "Marine Safety Information Bulletin, Captain of the Port order or port authority log number. One order may have several rows, one per segment"),
    "issued_utc": ("datetime", "2027-07-30T15:00:00Z", "When the order was published, UTC"),
    "effective_utc": ("datetime", "2027-08-01T05:00:00Z", "When it took effect, UTC. A segment's status holds until the next row for that segment"),
    "authority": ("string", "USCG Captain of the Port, Sector Corpus Christi", "Issuing authority"),
    "order_type": ("string", "CHANNEL STATUS", "PORT CONDITION, CHANNEL STATUS, VESSEL ORDER, SAFETY ZONE, SECURITY ZONE, NOTICE"),
    "port_condition": ("string", "WHISKEY", "Hurricane port condition in force: SEASONAL ALERT, X-RAY, YANKEE, ZULU, RECOVERY, NORMAL"),
    "segment_id": ("string", "SEG-ENT", "Channel segment: SEG-ENT entrance and jetties, SEG-BAY bay reaches, SEG-LAQ La Quinta Channel, SEG-INNER-E Inner Harbor to the Main Turning Basin, SEG-INNER-W Inner Harbor west of the Main Turning Basin, SEG-GIWW Intracoastal Waterway, SEG-ANCH offshore anchorage; blank for orders addressed to one vessel or terminal"),
    "segment_name": ("string", "Entrance channel and jetties", "Plain name of the segment"),
    "status": ("string", "OPEN", "OPEN, CLOSED, CLOSED TO INBOUND, CLOSED TO DEEP-DRAFT, RESTRICTED (see text); blank for orders not about a segment"),
    "vessel_mmsi": ("string", "", "MMSI of the vessel an order is addressed to (vessels.json); blank otherwise"),
    "terminal_id": ("string", "", "terminal_registry.json terminal an order refers to; blank otherwise"),
    "text": ("string", "Normal operations. All segments open to all traffic.", "The operative text of the order"),
}


def _fields(rel, notes):
    out = []
    for c in _header(rel):
        t, ex, n = notes.get(c, ("string", "", ""))
        out.append(F(c, t, ex, n))
    return out


def write_supply_schema():
    rel = "06_data_streams/schemas/12_supply_chain_schema.json"
    d = json.load(open(_p(rel), encoding="utf-8"))
    d["notes"] = ("Three related CSVs produced together with the AIS feed: vessel_arrivals.csv (one row per port call), cargo_manifest.csv "
                  "(one row per bill of lading or air waybill) and port_conditions.csv (one row per Captain of the Port order and channel segment). "
                  "The source systems use XML (eNOAD) and fixed-width CAMIR; the corpus normalises them to CSV. All times UTC. "
                  "fuel_deliveries.csv in the same folder has its own schema file.")
    files = d.get("files", {})
    files["vessel_arrivals"] = {"filename": "vessel_arrivals.csv", "description": "One row per port call by an ocean-going vessel: notice of arrival, anchorage, berth, departure.",
                                "fields": _fields(f"{SUP_DIR}/vessel_arrivals.csv", ARRIVAL_NOTES)}
    files["cargo_manifest"] = {"filename": "cargo_manifest.csv", "description": "One row per bill of lading (sea) or air waybill (relief cargo flown in).",
                               "fields": _fields(f"{SUP_DIR}/cargo_manifest.csv", MANIFEST_NOTES)}
    files["port_conditions"] = {"filename": "port_conditions.csv", "description": "Captain of the Port orders, hurricane port conditions and channel status by segment, in the style of Marine Safety Information Bulletins.",
                                "fields": _fields(f"{SUP_DIR}/port_conditions.csv", CONDITION_NOTES)}
    d["files"] = files
    d["scenario_notes"] = {
        "coverage": "Port calls, manifests and orders from before 2027-08-15 to 2028-01-12.",
        "port_state": "Arrivals, berthings and departures follow the orders in port_conditions.csv: no commercial movement in a closed segment; vessels that arrive during a closure wait at an anchorage position.",
        "consistency": "Every berthing in vessel_arrivals.csv appears in the AIS feed as the same vessel moored at that berth for the same period, and every manifest line for sea cargo joins a port call.",
    }
    _dump(rel, d)


RADAR_NOTES = {
    "time_utc": ("datetime", "2027-08-15T00:00:03Z", "Time of the plot, UTC"),
    "sensor_id": ("string", "RADAR-BUOY-NE", "sensors.csv sensor_id"),
    "track_id": ("string", "NE-000001", "Tracker's own number for the contact; a contact lost and picked up again gets a new one"),
    "latitude": ("float", "27.83867", "WGS-84; a few metres of plot noise"),
    "longitude": ("float", "-97.05224", ""),
    "range_nm": ("float", "3.07", "Range from the buoy, nautical miles"),
    "bearing_deg": ("float", "292.8", "Bearing from the buoy, degrees true"),
    "speed_kn": ("float", "0.0", "Tracker's speed estimate, knots"),
    "course_deg": ("float", "129.7", "Tracker's course estimate, degrees true"),
    "est_length_m": ("integer", "18", "Length estimated from the echo, metres"),
    "size_class": ("string", "small", "ship (50 m and over) or small"),
    "ais_correlated": ("string", "Y", "Y if the tracker matched the plot to an AIS report received at the same time, N if not"),
    "correlated_mmsi": ("string", "367487046", "MMSI of the matched AIS report (vessels.json); blank when ais_correlated is N"),
    "ingest_utc": ("datetime", "2027-08-15T00:00:05Z", "When the plot reached the shore archive, UTC"),
}
CAMERA_NOTES = {
    "time_utc": ("datetime", "2027-08-15T00:00:00Z", "UTC"),
    "sensor_id": ("string", "CAM-01", "sensors.csv sensor_id"),
    "event_type": ("string", "FRAME", "FRAME routine summary of what is in view; PASSAGE vessel passing the camera; BERTH ARRIVAL, BERTH DEPARTURE; INCIDENT operator entry"),
    "direction": ("string", "", "INBOUND / OUTBOUND for passages"),
    "mmsi": ("string", "", "MMSI where the operator or analytics identified the vessel (vessels.json); blank if unidentified"),
    "vessel_name": ("string", "", "Name read or matched; blank if unidentified"),
    "est_length_m": ("integer", "", "Length estimated from the image, metres"),
    "berth_id": ("string", "", "terminal_registry.json berth concerned"),
    "vessels_in_view": ("string", "none", "What is at the berths in view"),
    "water_surface": ("string", "clear", "Operator's description of the water surface"),
    "note": ("string", "", "Operator's note"),
}
VTS_NOTES = {
    "time_utc": ("datetime", "2027-08-15T00:02:35Z", "UTC"),
    "checkpoint": ("string", "JETTIES", "Reporting point passed"),
    "direction": ("string", "INBOUND", "INBOUND / OUTBOUND"),
    "mmsi": ("string", "338190847", "vessels.json mmsi"),
    "vessel_name": ("string", "CORRIN BAY", ""),
    "vessel_class": ("string", "tug", "vessels.json class"),
    "pilot_order_id": ("string", "", "Pilot order number for piloted movements"),
    "pilot_boat": ("string", "", "Pilot boat used"),
    "tugs": ("string", "", "Assist tugs, semicolon-separated"),
    "from_place": ("string", "", "Berth, anchorage position or SEA"),
    "to_place": ("string", "", "Berth, anchorage position or SEA"),
}
STATUS_NOTES = {
    "time_utc": ("datetime", "2027-08-15T00:00:00Z", "UTC; hourly, plus a row at each change"),
    "sensor_id": ("string", "CAM-01", "sensors.csv sensor_id"),
    "status": ("string", "ONLINE", "ONLINE, OFFLINE, NO UPLINK (recording on board, link down), BUFFER RECOVERED, ARCHIVE EXPORT"),
    "detail": ("string", "", "Fault or restoration detail as logged"),
}
SENSOR_NOTES = {
    "sensor_id": ("string", "RADAR-BUOY-NE", "Primary key for this folder"),
    "sensor_type": ("string", "radar buoy", "radar buoy, fixed camera, vessel traffic log"),
    "name": ("string", "Buoy-NE, entrance channel off the Port Aransas jetties", ""),
    "latitude": ("float", "27.81889", "Sensor position; blank for the traffic log"),
    "longitude": ("float", "-96.99892", ""),
    "range_nm": ("float", "9.5", "Radar range, nautical miles"),
    "berths_in_view": ("string", "TERM-01-B07; TERM-01-B08", "terminal_registry.json berths a camera covers"),
}


def write_surveillance_schema():
    radar = sorted(glob.glob(_p(f"{SURV_DIR}/radar_tracks_*.csv")))[0]
    d = {
        "source": "port_surveillance",
        "folder": f"{SURV_DIR}/",
        "format": "CSV",
        "standard": "Radar track table and operator logs as exported by a port vessel traffic service (no single public standard; column names are plain)",
        "verified": True,
        "notes": "All times UTC with a Z suffix. Vessels are joined by MMSI to 06_data_streams/vessels.json, berths to terminal_registry.json. Sensors are described in sensors.csv in the same folder.",
        "entity_catalog": "sensors.csv (this folder), 06_data_streams/vessels.json, 06_data_streams/terminal_registry.json",
        "files": {
            "sensors": {"filename": "sensors.csv", "description": "The sensors and where they are.", "fields": _fields(f"{SURV_DIR}/sensors.csv", SENSOR_NOTES)},
            "radar_tracks": {"filename": "radar_tracks_YYYY-MM.csv", "description": "Radar plots, one row per plot, one file per month.",
                             "fields": _fields(os.path.relpath(radar, ROOT), RADAR_NOTES)},
            "camera_events": {"filename": "camera_events.csv", "description": "Camera log.", "fields": _fields(f"{SURV_DIR}/camera_events.csv", CAMERA_NOTES)},
            "vessel_traffic_log": {"filename": "vessel_traffic_log.csv", "description": "Checkpoint passages with pilot and tug assignments.",
                                   "fields": _fields(f"{SURV_DIR}/vessel_traffic_log.csv", VTS_NOTES)},
            "sensor_status": {"filename": "sensor_status.csv", "description": "Sensor health.", "fields": _fields(f"{SURV_DIR}/sensor_status.csv", STATUS_NOTES)},
        },
        "scenario_notes": {
            "coverage": "2027-08-15T00:00Z to 2028-01-12T06:00Z, less the periods a sensor was out of service.",
            "cadence": "Radar plots about every 2 minutes while a contact is held (more often through bends, every 30 minutes for a stationary contact); camera frame summaries every few hours and event rows as they occur; status hourly.",
            "geography": "Radar plots pass scripts/check_geo.py rule \"vessel\"; cameras are on land, radar buoys in the water (99_reference/geo/position_rules.d/maritime.json).",
        },
    }
    _dump("06_data_streams/schemas/port_surveillance_schema.json", d)


# ------------------------------------------------------------------------------------------ geo rules, catalogue notes
def write_geo_rules():
    d = {
        "note": "Position sources of the maritime stream family (scripts/streams/gen_maritime.py). The shore-station AIS feed is covered by the main rules file.",
        "sources": [
            {"name": "AIS satellite feed", "glob": f"{AIS_DIR}/satellite/*.csv", "lat": "LAT", "lon": "LON", "rule": "vessel", "id": "MMSI", "time": "BaseDateTime", "draft_m": "Draft"},
            {"name": "Port radar contacts", "glob": f"{SURV_DIR}/radar_tracks_*.csv", "lat": "latitude", "lon": "longitude", "rule": "vessel", "id": "track_id", "time": "time_utc"},
            {"name": "Port cameras (land)", "glob": f"{SURV_DIR}/sensors.csv", "lat": "latitude", "lon": "longitude", "rule": "land_fixed", "id": "sensor_id", "allow_missing": True,
             "where": ["sensor_type", "fixed camera"]},
            {"name": "Port radar buoys (water)", "glob": f"{SURV_DIR}/sensors.csv", "lat": "latitude", "lon": "longitude", "rule": "water_fixed", "id": "sensor_id", "allow_missing": True,
             "where": ["sensor_type", "radar buoy"]},
        ],
    }
    _dump("99_reference/geo/position_rules.d/maritime.json", d)


def write_catalog_changes(counts):
    d = {
        "family": "maritime",
        "generator": "scripts/streams/gen_maritime.py (stages: sim, ais per month, radar, cameras, tables, docs; resumable with --budget)",
        "changes": [
            {"stream_id": "ais", "path_glob": "05_other_sources/ais/*.csv",
             "note": "Unchanged glob: six monthly shore-station files ais_YYYY-MM.csv. A second product, the satellite-received feed, is in 05_other_sources/ais/satellite/sais_YYYY-MM.csv, deliberately outside the glob: it is a different receiver, and merging the two would put one MMSI in two places hundreds of miles apart in a single file. Consider a catalogue entry 'ais_satellite' (same columns, same span, cadence 30-60 min). Extra column Destination (the transponder's free-text field) after TransceiverClass. Cadence at anchor is 6 min (canon EVT-1201 needs an anchored ship with no gap longer than a few minutes; applied to every anchored ship so none stands out), on station 15 min, moored 60 min."},
            {"stream_id": "port_surveillance", "path_glob": "05_other_sources/port_surveillance/*.csv",
             "note": "Five tables with different columns: sensors.csv, radar_tracks_YYYY-MM.csv, camera_events.csv, vessel_traffic_log.csv, sensor_status.csv. key_columns in the catalogue describe the radar table. ids_from_registry lists sensor_registry.json, which has no port radar or camera entries: the sensors are defined in sensors.csv in the stream folder (proposed registry records are the rows of that file). New schema file 06_data_streams/schemas/port_surveillance_schema.json (add to 00_schema_index.json)."},
            {"stream_id": "port_conditions", "path_glob": "05_other_sources/supply/port_conditions.csv",
             "note": "segment_id values are SEG-ENT, SEG-BAY, SEG-LAQ, SEG-INNER-E, SEG-INNER-W, SEG-GIWW, SEG-ANCH; they are defined by this stream (terminal_registry.json has no channel segments). The inner-channel restriction line is the west limit of the Main Turning Basin."},
            {"stream_id": "port_arrivals", "path_glob": "05_other_sources/supply/vessel_arrivals.csv",
             "note": "port_of_arrival is USCRP (the UN/LOCODE for Corpus Christi), not TXCPT as the old schema said. Columns added: next_port, noa_submitted_datetime, eta_revised_datetime, ata_anchorage_datetime, hold_log, shift_berth_id, shift_datetime; last_port_country dropped."},
            {"stream_id": "cargo_manifests", "path_glob": "05_other_sources/supply/cargo_manifest.csv",
             "note": "Sea and air consignments in one table (mode SEA / AIR). Columns added: manifest_id, mode, direction, vessel_name, carrier, supplier_id, consignee_id, port_of_lading, port_of_discharge, booking_date, planned_arrival_date, arrival_date, release_date; in_bond_type dropped."},
        ],
        "geo_rules": "99_reference/geo/position_rules.d/maritime.json (satellite AIS, radar plots, cameras on land, radar buoys in water)",
        "geo_check": "python3 scripts/check_geo.py --only=AIS needs most of an hour on the full feed; scripts/streams/run_check_geo_maritime.py runs the same Checker over the same rows in resumable pieces.",
        "row_counts": counts,
        "run_order": ["gen_maritime.py", "then anything that reads AIS on disk (gen_satellite.py)"],
    }
    _dump("06_data_streams/_internal/catalog_changes_maritime.json", d)


def write_all(sim=None, prog=None):
    counts = write_readmes()
    write_ais_schema()
    write_supply_schema()
    write_surveillance_schema()
    write_geo_rules()
    counts.update(n_port_conditions=_rows(f"{SUP_DIR}/port_conditions.csv"), n_arrivals=_rows(f"{SUP_DIR}/vessel_arrivals.csv"), n_manifests=_rows(f"{SUP_DIR}/cargo_manifest.csv"))
    write_catalog_changes(counts)
    return counts
