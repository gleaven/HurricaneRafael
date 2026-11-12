# Data streams

This folder holds the 43 delivered data streams of the Hurricane Rafael corpus: what ships, aircraft, vehicles, sensors, control systems, networks, hospitals, agencies, payment systems and people recorded from 2027-08-15 to 2028-01-12 (the IT and security logs start 2027-07-16). All of it is synthetic. Places are real; people, companies, vessels, aircraft and outlets are fictional.

Times are UTC unless a column says local. Local time is US Central (CDT until 2027-11-07, then CST). Hurricane Rafael makes landfall at 2027-09-14T06:00Z.

Entity ids (vessels, aircraft, hospitals, units, hosts, sensors, accounts, areas) are defined in the registries in `06_data_streams/`; column lists are in `06_data_streams/schemas/`.

| Stream | Files (under this folder) | Format | Files | Size |
| --- | --- | --- | --- | --- |
| AIS vessel positions | `ais/*.csv` | USCG NAIS / MarineCadastre CSV | 6 | 147.4 MB |
| Port radar and camera contact log | `port_surveillance/*.csv` | Radar track table (sensor id, track id, time, position, speed, course, AIS-correlated flag, correlated MMSI) and camera event log | 10 | 42.3 MB |
| Coast Guard port conditions and channel status | `supply/port_conditions.csv` | Captain of the Port order log (MSIB style): effective time, condition, channel segment, status, restrictions | 1 | 0.0 MB |
| Vessel arrivals and departures | `supply/vessel_arrivals.csv` | USCG eNOAD / CBP ACE normalized | 1 | 0.1 MB |
| Cargo manifests (sea and air relief cargo) | `supply/cargo_manifest.csv` | CBP ACE manifest normalized | 1 | 0.1 MB |
| Fuel deliveries and lots | `supply/fuel_deliveries.csv` | Delivery ticket log: time, supplier, receiving facility, product, volume, lot id, carrier (truck or barge) | 1 | 0.0 MB |
| ADS-B aircraft positions | `adsb/adsb_*.csv` | OpenSky StateVector CSV plus nic and nac_p integrity columns | 6 | 122.1 MB |
| Drone detections and authorizations | `drone_detections/*.csv` | Radar/RF detection tracks (sensor, track, time, position, altitude, RCS, RF signature), LAANC authorization list, sighting reports | 15 | 16.6 MB |
| Authorized drone flight telemetry | `drone_video/drone_telemetry_*.csv` | DJI SRT normalized to CSV | 8 | 80.3 MB |
| Satellite scene catalogue | `satellite/*.json` | STAC v1.0.0 Item JSON with detection summaries | 160 | 0.3 MB |
| Structure damage assessments and flood/debris extents | `infrastructure/*.csv` | FEMA GDA feature table | 2 | 5.5 MB |
| Response vehicle locations | `avl/*.csv` | AVL log: time, unit, position, speed, heading, status, incident | 32 | 97.9 MB |
| 911 computer-aided dispatch records | `911/*.csv` | Tyler New World CAD export with ANI/ALI class and call metadata | 6 | 26.0 MB |
| Search and rescue mission log | `sar/*.csv` | Mission log: agency, asset, launch and recovery times, location, persons rescued, method | 4 | 0.4 MB |
| Shelter registry and daily census | `shelters/*.csv` | Registry (facility, open and close times) and daily occupancy | 4 | 0.1 MB |
| Public alerts (EAS, WEA, city and county notices) | `public_health/eas_broadcasts.csv` | IPAWS CAP alert log with separate English and Spanish release times | 1 | 0.0 MB |
| Broadcast and translation logs | `broadcast/*.csv` | Station programme log (time, station, item, language, alert id) and translation job log (source received, translation delivered) | 5 | 0.2 MB |
| Social media posts | `social_media/*.jsonl` | Twitter v1.1 Tweet objects | 318 | 119.3 MB |
| News stories | (in `08_release/news_stories_public.json`) | Story objects (also served by the newsroom feeds) | 1 | 2.1 MB |
| Official statements and notices | `press_releases/*.jsonl` | Public fields of the public record: date, time, issuer, type, text | 7 | 0.2 MB |
| Surface weather and buoy observations | `weather/*_observations.csv` | NOAA LCD / ASOS CSV; NDBC standard meteorological | 9 | 4.7 MB |
| Hurricane advisories and best track | `weather/nhc_advisories.json` | NHC advisory list and HURDAT2 best track | 1 | 0.1 MB |
| Tide and river gauges | `env_sensors/gauge_*.csv` | NOAA CO-OPS water level; USGS stage and discharge | 8 | 34.3 MB |
| Water-quality sondes | `env_sensors/water_quality_*.csv` | TCEQ sonde table | 6 | 10.9 MB |
| Air-quality monitors | `env_sensors/aqs_*.csv` | EPA AQS hourly | 20 | 8.3 MB |
| Wastewater pathogen surveillance | `public_health/wastewater_surveillance.csv` | CDC NWSS style: sample date, sewershed, target, concentration | 1 | 0.1 MB |
| Emergency department visits | `public_health/ed_visits_*.csv` | CDC NSSP BioSense line list | 7 | 18.7 MB |
| Hospital capacity and utilities status | `public_health/hospital_capacity.csv` | HHS Protect daily capacity plus power source, generator fuel and diversion status | 1 | 0.2 MB |
| Syndromic surveillance summary | `public_health/syndrome_summary.csv` | Daily counts by syndrome, facility and area | 1 | 2.8 MB |
| Utility SCADA historian | `telemetry/historian_*.csv` | AVEVA PI style tag history | 72 | 59.5 MB |
| Customer outages by area | `telemetry/outage_map.csv` | Outage management export: time, area or feeder, customers served, customers out | 1 | 7.0 MB |
| Maintenance work orders and purchase requests | `maintenance/work_orders.csv` | IBM Maximo WORKORDER export, several organisations | 1 | 0.3 MB |
| Military installation status reports | `maintenance/base_status_reports.csv` | Daily status: installation, readiness percent, aircraft on station, backup power status, perimeter sensor status | 1 | 0.1 MB |
| Utility security alerts | `network_logs/siem/*.csv` | SIEM alert queue export with analyst disposition | 9 | 92.7 MB |
| Network connection logs | `network_logs/zeek/*/*.log` | Zeek conn, dns and notice TSV with OT protocol notices | 724 | 65.5 MB |
| Host, access and mail audit logs | `network_logs/audit/*.csv` | VPN sessions, historian access, file and configuration audit, change tickets, mail gateway, endpoint detections, by organisation | 16 | 6.0 MB |
| Aid portal and logistics system access logs | `network_logs/portal/*.csv` | Web authentication log: time, system, account hash, source address and ASN, result | 14 | 41.5 MB |
| Tanker cargo-control and vendor remote-access logs | `telemetry/vessel_cargo_control_*.csv` | Cargo-control event log (valves, alarms, tank levels) and vendor remote-session log | 3 | 3.7 MB |
| Vendor registry, contracts and invoices | `payments/contracts*.csv` | Vendor registry, award records (PIID), invoices | 6 | 0.3 MB |
| Financial transactions | `payments/financial_transactions.csv` | ACH and card transaction log | 1 | 5.6 MB |
| Disaster aid applications and account changes | `payments/aid_applications.csv` | Application records and account-change audit (deposit detail changes) | 1 | 32.2 MB |
| Insurance and spill damage claims | `payments/insurance_claims.csv` | ACORD claim records | 1 | 2.1 MB |
| Census tract table | `census/*.csv` | ACS 5-year estimates | 2 | 0.0 MB |

## Things to know

- **Positions are real.** Ships follow the dredged channels, anchorages and open water of Corpus Christi Bay and the Gulf; vehicles follow real streets; fixed sites sit on land at real locations. AIS is dense in channels (about one fix a minute) and sparse offshore and at berth; a vessel that sails out of coastal coverage simply stops reporting.
- **Sensors fail.** Stations, gauges and network links drop out around landfall and come back later. A gap is not an error.
- **Some logs are sampled.** Background network flows are sampled 1 in 200; insurance claims are a 1 in 170 sample. The schema for each stream says so where it applies.
- **Large streams are split** by month, by day (network connection logs), by agency (vehicle locations) or by account (social media).

## For builders

Nothing in this folder is edited by hand. Every file is written by a generator in `scripts/streams/` from the canon timeline and the registries; see the root `README.md` for how to regenerate and check the streams. Superseded files from before the 2026-11 rebuild are in `_versions/streams_pre_regen_20261109/`.
