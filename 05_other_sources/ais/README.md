# AIS vessel positions

Automatic Identification System reports for the Port of Corpus Christi and its approaches,
2027-08-15 to 2028-01-12, in the column layout of the USCG NAIS / MarineCadastre CSV. All times UTC.

## Files

| Files | What | Rows |
|---|---|---|
| `ais_YYYY-MM.csv` | Shore-station feed: every report received by the coastal receiver network at the harbour entrance. Reception reaches about 45 nautical miles offshore. One file per calendar month. | 1,313,056 |
| `satellite/sais_YYYY-MM.csv` | Satellite-received feed for the same months: reports from vessels beyond shore range, out to the edge of the Gulf area this corpus covers. Sparser (about one report every 30 to 60 minutes per vessel). | 47,743 |

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
