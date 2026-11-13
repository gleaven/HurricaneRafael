# Data streams

This folder holds the 56 delivered data streams of the Hurricane Rafael corpus: what ships, aircraft, vehicles, sensors, control systems, networks, hospitals, agencies, payment systems and people recorded from 2027-08-15 to 2028-01-12 (the IT and security logs start 2027-07-16). All of it is synthetic. Places are real; people, companies, vessels, aircraft and outlets are fictional.

Times are UTC unless a column says local. Local time is US Central (CDT until 2027-11-07, then CST). Hurricane Rafael makes landfall at 2027-09-14T06:00Z.

Entity ids (vessels, aircraft, hospitals, units, hosts, sensors, accounts, areas) are defined in the registries in `06_data_streams/` (the utility's hosts and accounts in `gw_host_registry.json`, those of the seven partner organisations in `partner_it_registry.json`); column lists are in `06_data_streams/schemas/`.

| Stream | Files (under this folder) | Format | Files | Size |
| --- | --- | --- | --- | --- |
| AIS vessel positions | `ais/*.csv` | USCG NAIS / MarineCadastre CSV | 6 | 147.4 MB |
| Port radar and camera contact log | `port_surveillance/*.csv` | Radar track table (sensor id, track id, time, position, speed, course, AIS-correlated flag, correlated MMSI) and camera event log | 10 | 42.3 MB |
| Coast Guard port conditions and channel status | `supply/port_conditions.csv` | Captain of the Port order log (MSIB style): effective time, condition, channel segment, status, restrictions | 1 | 0.0 MB |
| Vessel arrivals and departures | `supply/vessel_arrivals.csv` | USCG eNOAD / CBP ACE normalized | 1 | 0.1 MB |
| Cargo manifests (sea and air relief cargo) | `supply/cargo_manifest.csv` | CBP ACE manifest normalized | 1 | 0.1 MB |
| Fuel deliveries and lots | `supply/fuel_deliveries.csv` | Delivery ticket log: time, supplier, receiving facility, product, volume, lot id, carrier (truck or barge) | 1 | 0.1 MB |
| ADS-B aircraft positions | `adsb/adsb_*.csv` | OpenSky StateVector CSV plus nic and nac_p integrity columns | 6 | 121.8 MB |
| Drone detections and authorizations | `drone_detections/*.csv` | Radar/RF detection tracks (sensor, track, time, position, altitude, RCS, RF signature), LAANC authorization list, sighting reports | 15 | 16.6 MB |
| Authorized drone flight telemetry | `drone_video/drone_telemetry_*.csv` | DJI SRT normalized to CSV | 8 | 79.3 MB |
| Satellite scene catalogue | `satellite/*.json` | STAC v1.0.0 Item JSON with detection summaries | 172 | 0.4 MB |
| Structure damage assessments and flood/debris extents | `infrastructure/*.csv` | FEMA GDA feature table | 2 | 5.7 MB |
| Response vehicle locations | `avl/*.csv` | AVL log: time, unit, position, speed, heading, status, incident | 32 | 95.1 MB |
| 911 computer-aided dispatch records | `911/*.csv` | Tyler New World CAD export with ANI/ALI class and call metadata | 6 | 26.0 MB |
| Search and rescue mission log | `sar/*.csv` | Mission log: agency, asset, launch and recovery times, location, persons rescued, method | 4 | 0.4 MB |
| Shelter registry and daily census | `shelters/*.csv` | Registry (facility, open and close times) and daily occupancy | 5 | 0.2 MB |
| Public alerts (EAS, WEA, city and county notices) | `public_health/eas_broadcasts.csv` | IPAWS CAP alert log with separate English and Spanish release times | 1 | 0.0 MB |
| Broadcast and translation logs | `broadcast/*.csv` | Station programme log (time, station, item, language, alert id) and translation job log (source received, translation delivered) | 5 | 0.2 MB |
| Social media posts | `social_media/*.jsonl` | Twitter v1.1 Tweet objects | 318 | 119.4 MB |
| News stories | `08_release/news_stories_public.json` | Story objects (also served by the newsroom feeds) | 0 | 0.0 MB |
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
| Utility security alerts | `network_logs/siem/*.csv` | SIEM alert queue export with analyst disposition | 9 | 90.5 MB |
| Network connection logs | `network_logs/zeek/*/*.log` | Zeek TSV logs: conn, dns, ssl, http, files, x509 and notice | 1,267 | 187.4 MB |
| Host, access and mail audit logs | `network_logs/audit/*.csv` | Gateway and VPN sessions, historian access, file and configuration audit, change tickets, mail gateway, endpoint detections | 17 | 12.6 MB |
| Aid portal and logistics system access logs | `network_logs/portal/*.csv` | Web access log: time, system, client address and its network, method, path, status, event, account, user agent family, response size | 15 | 88.8 MB |
| Firewall session logs | `network_logs/firewall/fw_*.csv` | CSV session and drop log of the internet edge firewall and the IT/OT boundary firewall | 14 | 69.5 MB |
| Web and DNS filter logs | `network_logs/proxy/web_proxy_*.csv` | CSV access log of the transparent web and DNS filter | 7 | 53.9 MB |
| Address lease logs | `network_logs/dhcp/dhcp_leases_*.csv` | CSV lease audit log (user networks and the employee VPN pool) | 7 | 1.6 MB |
| Perimeter packet capture | `network_logs/pcap/perimeter_*.pcap` | libpcap files, Ethernet/IPv4, flow-cutoff capture on the inside of the internet edge | 181 | 119.5 MB |
| Windows event logs | `network_logs/windows/*.jsonl` | JSON Lines; Security, System and Defender channels of the utility's Windows hosts, forwarded subset of event ids | 21 | 118.5 MB |
| Endpoint telemetry | `network_logs/endpoint/*.jsonl` | JSON Lines; process, network, DNS, file, registry, service, task and removable-device events from the endpoint agent | 7 | 203.2 MB |
| Host triage collections | `network_logs/triage/**/*.*` | CSV tables, collection.json and inert text placeholders per collected host | 178 | 0.6 MB |
| Partner organisations: firewall logs | `partner_it/*/firewall_*.csv` | Edge firewall session log (one row per session, written when the session ends) | 49 | 41.2 MB |
| Partner organisations: web gateway logs | `partner_it/*/web_*.csv` | Web gateway access log (transparent filtering; encrypted sites are logged as CONNECT with no path) | 49 | 11.1 MB |
| Partner organisations: DNS query logs | `partner_it/*/dns_*.csv` | Resolver query log | 49 | 8.1 MB |
| Partner organisations: sign-on logs | `partner_it/*/auth_*.csv` | Sign-on log: workstation logons and logoffs, and remote sign-ons (single sign-on, webmail, VPN) | 49 | 33.1 MB |
| Partner organisations: mail gateway logs | `partner_it/*/mail_*.csv` | Mail gateway message log (same columns as network_logs/audit/mail_gateway_*.csv) | 49 | 16.8 MB |
| Partner organisations: endpoint protection events | `partner_it/*/endpoint_alerts_*.csv` | Endpoint protection console events (same columns as network_logs/audit/endpoint_protection.csv) | 49 | 1.4 MB |
| Tanker cargo-control and vendor remote-access logs | `telemetry/vessel_cargo_control_*.csv` | Cargo-control event log (valves, alarms, tank levels) and vendor remote-session log | 3 | 3.7 MB |
| Vendor registry, contracts and invoices | `payments/contracts*.csv` | Vendor registry, award records (PIID), invoices | 6 | 0.3 MB |
| Financial transactions | `payments/financial_transactions.csv` | ACH and card transaction log | 1 | 5.5 MB |
| Disaster aid applications and account changes | `payments/aid_applications.csv` | Application records and account-change audit (deposit detail changes) | 1 | 32.1 MB |
| Insurance and spill damage claims | `payments/insurance_claims.csv` | ACORD claim records | 1 | 2.1 MB |
| Census tract table | `census/*.csv` | ACS 5-year estimates | 2 | 0.0 MB |

## Things to know

- **Positions are real.** Ships follow the dredged channels, anchorages and open water of Corpus Christi Bay and the Gulf; vehicles follow real streets; fixed sites sit on land at real locations. AIS is dense in channels (about one fix a minute) and sparse offshore and at berth; a vessel that sails out of coastal coverage simply stops reporting.
- **Sensors fail.** Stations, gauges and network links drop out around landfall and come back later. A gap is not an error.
- **Some logs are sampled.** In the utility's network and host logs (`network_logs/`), traffic that people cause is a 1 in 200 sample, the same sample in every log; sessions, alerts, scheduled machine traffic and everything tied to an alert or an audit record are complete. The partner organisations' logs (`partner_it/`) state their own sampling per log (sign-ons complete; web and DNS about 1 in 40; mail about 1 in 25). Insurance claims are a 1 in 170 sample. The schema for each stream says so where it applies.
- **Raw logs are records, not contents.** Packet captures keep only the first packets of each flow, file listings carry sizes and hashes, and the triage collections hold inert text placeholders in place of the files a collector would copy. There is no executable content anywhere in this folder.
- **Large streams are split** by month, by day (network connection logs, packet captures), by agency (vehicle locations), by organisation (`partner_it/<org>/`), by host (`network_logs/triage/<host>/`) or by account (social media).

## For builders

Nothing in this folder is edited by hand. Every file is written by a generator in `scripts/streams/` from the canon timeline and the registries; see the root `README.md` for how to regenerate and check the streams. Superseded files from before the 2026-11 rebuild are in `_versions/streams_pre_regen_20261109/`.
