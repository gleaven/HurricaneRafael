# Port surveillance: radar, cameras, vessel traffic log

Sensor logs kept by the port and the Coast Guard for the Corpus Christi Ship Channel,
2027-08-15 to 2028-01-12. All times UTC.

| File | What | Rows |
|---|---|---|
| `sensors.csv` | The sensors: two radar buoys, fourteen fixed cameras, the vessel traffic service log. Positions and the berths each camera covers. | 17 |
| `radar_tracks_YYYY-MM.csv` | Radar plots from the two buoys, one row per plot, about every two minutes while a contact is held (every 30 minutes for a stationary contact). | 299,426 |
| `camera_events.csv` | Camera log: a routine frame summary every few hours and an event row whenever a vessel passes, berths or leaves. | 23,628 |
| `vessel_traffic_log.csv` | Vessel traffic service checkpoint log: each passage of the jetties, the Harbor Bridge and the other reporting points, with pilot and tug assignments where a pilot was ordered. | 2,775 |
| `sensor_status.csv` | Hourly health of every sensor, plus a row at each change. | 57,731 |

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

Field notes: `schemas/port_surveillance_schema.json`.
