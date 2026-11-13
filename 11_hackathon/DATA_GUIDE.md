# Data guide

What is in the package, how time and identifiers work, and how the pieces join.
Exact file names, record counts, time spans and column lists for every file are in `DATA_TABLES.md`, which is produced from the files themselves.

## 1. Layout

```
data/         the data streams (sensor feeds, logs, records, posts, statements)
registries/   who and what the ids in the data refer to
schemas/      field-by-field notes for each stream, and stream_catalogue.json
reference/    real-world geography for the area (GeoJSON)
docs/         PLAYER_BRIEF.md, DATA_GUIDE.md, DATA_TABLES.md
```

The news is not in the package. It is published by the newsroom server on the exercise clock (section 7).

## 2. Time

- **Day zero** is Tuesday, 14 September 2027, the day Hurricane Rafael makes landfall near Port Aransas.
- Most streams run from **2027-08-15** to **2028-01-12**. Network, security, portal, tanker cargo-control, contract, social media and official-statement records start earlier, on **2027-07-16**. Some response-only tables cover a shorter period (search and rescue, shelters, outage map, storm advisories). `DATA_TABLES.md` gives the first and last record of every file.
- **UTC is the default.** A column is local time only when its name or its schema note says so.
- **Local time is US Central.** Central Daylight Time (UTC-5) until 2027-11-07 07:00 UTC, then Central Standard Time (UTC-6). Landfall night straddles two UTC dates: 01:00 local on 14 September is 06:00 UTC the same day.

| Form | Example | Where |
|---|---|---|
| ISO 8601 with `Z` | `2027-08-20T19:13:40Z` | most CSV logs |
| ISO 8601 without a zone, UTC | `2027-08-18T15:00:07` | AIS `BaseDateTime`, weather and gauge `ObsDateTime` |
| ISO 8601 with milliseconds and `Z` | `2027-08-18T14:29:52.975Z` | Windows event logs, endpoint telemetry |
| Unix epoch seconds, UTC | `1820880000` (= 2027-09-14T00:00:00Z) | ADS-B `time_position`, Zeek `ts`, packet capture timestamps |
| Twitter date string, UTC | `Thu Sep 16 13:23:20 +0000 2027` | social media `created_at` |
| Local date and time | `2027-08-20 14:12:08` | 911 dispatch `*_dttm` columns, shelter `*_local` columns |
| ISO 8601 with a local offset | `2027-07-16T05:52:00-05:00` | official statements `issued_local` |
| Calendar date | `2027-10-11` | daily reports, contracts, claims; local calendar dates unless the column name ends in `_utc` or `GMT` |

Two things to watch. The 911 dispatch times are local, so they are five hours (later six) behind the vehicle-location times for the same incident. And on 2027-11-07 the local hour from 01:00 to 02:00 happens twice.

## 3. Identifiers and registries

Every id in the data resolves in a registry. The registries describe what things are; they do not tell you what any of them did.

| Registry | What it lists | Main ids | Used by |
|---|---|---|---|
| `vessels.json` | 130 vessels: class, dimensions, draft, operator, home berth | `mmsi`, `vessel_id` | AIS, port surveillance, port calls, cargo, search and rescue, tanker cargo-control logs |
| `terminal_registry.json` | terminals, berths, small-craft harbours and slips, anchorage positions, channel segments | `terminal_id`, `berth_id`, `slip_id`, `position_id`, `segment_id` | port calls, port conditions, camera events, fuel deliveries |
| `aircraft_registry.json` | 64 aircraft, 25 airfields, parking positions | `icao24`, `aircraft_id`, `airfield_id` | ADS-B, search and rescue |
| `drone_operators.json` | authorised drone operators, airframes, launch sites | `operator_id`, `site_id` | drone telemetry, flight authorisations |
| `facility_registry.json` | hospitals, shelters, public buildings, installations | `facility_id` | ED visits, hospital capacity, shelters, 911 transports, base status reports, fuel deliveries |
| `infrastructure_assets.json` | substations, the water plant and its pumps, boosters, tanks, bridges | `asset_id` | outage map, work orders, wastewater sites, surveys |
| `sensor_registry.json` | sondes, air monitors, tide and stream gauges, weather stations, buoys, port and drone-detection sensors | `sensor_id` | environmental feeds, port surveillance, drone detections |
| `cad_units.json` | response agencies, stations, units, call nature and disposition codes | `unit_id`, `station_id` | 911 dispatch, vehicle locations, search and rescue |
| `areas.json` | census tracts, ZIP codes, neighbourhoods, cities, patrol beats, water districts, pressure zones, evacuation zones; each with a reference point and bounding box | `area_id` | 911, ED visits, syndromic counts, outage map, aid applications, claims, alerts, census |
| `gw_host_registry.json` | the utility's sites, network zones, 329 hosts, field equipment, users, service accounts, external systems | `hostname`, `host_id`, `ip`, `username`, `equipment_id`, `system_id` | security alerts, network logs, firewall, web filter and lease logs, packet capture, Windows event logs, endpoint telemetry, triage collections, audit logs, portal logs |
| `partner_it_registry.json` | seven other organisations (city, county, port, air station, two hospitals, a marine vendor): sites, address plans, hosts, accounts | `host_id`, `ip`, `account`, `mailbox` | partner organisation IT logs |
| `scada_tags.json` | 331 historian tags: what each measures, units, normal range, site and equipment | `tagname` | SCADA historian |
| `personas.json` | social media accounts: handle, type, home area, language, style | `handle`, `persona_id` | social media |
| `organizations.json` | agencies, companies, hospitals, media, military units, broadcast stations | `org_id`, `station_id` | contracts, payments, work orders, port calls, broadcast logs |
| `entity_registry.json` | insurers, brokers, adjusters, vendors, contracts, financial institutions, accounts, policyholders and policies | `vendor_id`, `contract_id`, `insurer_id`, `adjuster_id`, account ids | contracts, invoices, payments, claims, fuel deliveries |

The utility is the Coastal Bend Power and Water Authority (CBPWA). Its asset tags, host names and historian tags begin with `GW`.

## 4. The streams

Paths are under `data/`. "Imitates" names the real-world system or standard whose layout the stream follows.

### On the water

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| AIS vessel positions | USCG NAIS / MarineCadastre CSV | `ais/ais_<month>.csv` (shore receivers), `ais/satellite/sais_<month>.csv` (satellite receivers) | `BaseDateTime` | `MMSI` → `vessels.json` | Shore reception reaches about 45 nautical miles; beyond that a vessel appears only in the sparser satellite feed. Reports are thinned as archived AIS is: about 1 min in channels and harbours, 5 min in open bay, 6 min at anchor, 30 min offshore, 60 min moored. A vessel with its unit off or out of range has no rows. Static fields are whatever the unit broadcasts. See `ais/README.md`. |
| Port surveillance | radar track table, camera event log, vessel traffic service log | `port_surveillance/*.csv` | `time_utc` | `sensor_id` → `sensor_registry.json`; `correlated_mmsi`, `mmsi` → `vessels.json`; `berth_id` → `terminal_registry.json` | Radar holds a contact whether or not it has AIS (`ais_correlated`). Sensors have outages; see `sensor_status.csv`. See `port_surveillance/README.md`. |
| Port conditions | Captain of the Port orders | `supply/port_conditions.csv` | `issued_utc`, `effective_utc` | `segment_id`, `terminal_id` → `terminal_registry.json` | One row per order or change. |
| Vessel arrivals | notice of arrival / port call record | `supply/vessel_arrivals.csv` | `noa_submitted_datetime`, `eta_`, `ata_`, `atd_` | `mmsi`, `berth_id`, `terminal_id`, `anchorage_position_id` | One row per port call; a row is updated through the call. |
| Cargo manifests | customs manifest | `supply/cargo_manifest.csv` | booking, arrival and release dates (local calendar dates) | `arrival_id` → vessel arrivals; `supplier_id`, `consignee_id` → `entity_registry.json` / `organizations.json` | Sea and air consignments (`mode`). |
| Tanker cargo-control logs | shipboard cargo-control event log and a vendor's remote-session log | `telemetry/vessel_cargo_control_*.csv` | `timestamp_utc`, `login_utc` | `mmsi` → `vessels.json` | Two tankers' control systems (valves, tank levels, alarms, operator stations) and the maintenance vendor's remote-access sessions. |

### In the air

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| ADS-B aircraft positions | OpenSky state vectors, plus `nic` and `nac_p` integrity fields | `adsb/adsb_<month>.csv` | `time_position` (epoch) | `icao24` → `aircraft_registry.json` | Altitudes in metres. Call signs are at most eight characters; join on `icao24`. About 10 s near airfields and in hovers, 30 s at low level, 60 s en route. Aircraft that leave the area drop out of coverage. Only aircraft that transmit ADS-B appear. |
| Drone flight telemetry | DJI SRT flight logs as CSV | `drone_video/drone_telemetry_*.csv`, `drone_video/logs/*.csv` | `timestamp_utc` | `operator_id` → `drone_operators.json`; `authorization_id` → authorisations | Authorised flights, one row per second, with a flight log and survey readings. |
| Drone detections | radar/RF/acoustic detection log, flight authorisation list, sighting report forms | `drone_detections/*.csv` | `time_utc` | `sensor_id` → `sensor_registry.json`; `authorization_id`, `operator_id` | What sensors and people recorded, whoever was flying. Sensor health is in `sensor_status_<month>.csv`. |
| Satellite scenes | STAC items | `satellite/<scene id>.json`, `catalog.json` | `properties.datetime` | footprint (`bbox`, `geometry`) | Scene metadata and analyst descriptions; no pixels. |

### On the ground

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| 911 dispatch | computer-aided dispatch export | `911/cad_incidents_<month>.csv`, reports in `911/reports/` | `call_received_dttm` and the other `*_dttm` columns (**local**) | `unit_id` → `cad_units.json`; `census_tract`, `beat` → `areas.json`; `transport_destination` → `facility_registry.json` | One row per incident. `911/reports/` holds daily call volumes, queue depth, the shift log and phone subscriber records keyed by `callback_number`. |
| Vehicle locations | AVL modem log | `avl/avl_<month>_<agency>.csv` | `time_utc` | `unit_id` → `cad_units.json`; `incident_number` → 911 | Status codes: ENR en route, ONS on scene, TRN transporting, HSP at hospital, RTQ returning, AIQ in quarters, STG staged. Reports are denser while moving. |
| Search and rescue | mission log | `sar/*.csv` | `launch_utc`, `time_utc` | `asset_id` → units, aircraft or vessels; `incident_number` and `case_number` → 911 (`sar_case_number`); `delivered_to` → `facility_registry.json` | Landfall period only. One row per rescue case; `mission_id` groups the cases of one sortie. Helicopter sorties are the same flights as in the aircraft tracks. |
| Shelters | shelter census, intake log, 2-1-1 calls, evacuation bus trips | `shelters/*.csv` | `date_local`, `*_local` | `facility_id` → `facility_registry.json`; `unit_id` → `cad_units.json` | `shelter_intake_log.csv` lists arrivals by mode; `reference` holds the bus or the rescue `mission_id`. Its daily sums equal `new_arrivals` in the census. |
| Damage assessment | FEMA-style structure assessments and site surveys | `infrastructure/*.csv`, `infrastructure/aerial_survey/` | `ASMT_DATE`, `survey_time_utc` | `census_tract` → `areas.json`; `asset_id` → `infrastructure_assets.json` | |

### Health

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Emergency department visits | syndromic surveillance line list | `public_health/ed_visits_<facility>.csv` | `Arrive_Date_Time` (UTC); `Visit_Date` (local date) | `Facility_ID` → `facility_registry.json`; `Patient_Tract`, `Patient_ZIP` → `areas.json` | Chief complaints are free triage text; `CC_Category` is the keyword category a syndromic system assigns. |
| Syndromic summary | daily counts | `public_health/syndrome_summary.csv` | `Report_Date` (local date) | `Facility_ID`, `Area_ID` | An exact daily count of the line list. |
| Hospital capacity | daily capacity report with power and fuel status | `public_health/hospital_capacity.csv` | `Report_Date` | `Facility_ID` | |
| Wastewater surveillance | sewershed pathogen sampling | `public_health/wastewater_surveillance.csv` | `sample_date` | `sewershed_id` → `sensor_registry.json` wastewater sampling sites (`site_id`) | Two to three samples a week per plant, with gaps when a plant could not be sampled. |

### Weather and environment

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Surface weather and buoys | ASOS / NDBC observations | `weather/*_observations.csv` | `ObsDateTime` | `StationID` → `sensor_registry.json` weather stations and buoys (`sensor_id`) | Hourly, with special observations. Stations can go silent in severe weather. |
| Storm advisories | hurricane advisories and best track | `weather/nhc_advisories.json` | `advisories[].issued_utc` | | |
| Tide and stream gauges | water level, stage and discharge | `env_sensors/gauge_<id>.csv` | `ObsDateTime` | `SensorID` | 6 min tide, 15 min river. |
| Water-quality sondes | multi-parameter sonde table | `env_sensors/water_quality_<id>.csv` | `ObsDateTime` | `SensorID` | 15 min. |
| Air-quality monitors | EPA AQS-style hourly | `env_sensors/aqs_air_quality_<id>.csv` | `Date_GMT`, `Time_GMT` | `SensorID` | Hourly. |

### The utility: operations

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| SCADA historian | process historian archive (tag, time, value, quality) | `telemetry/historian_<group>_<month>.csv` | `Timestamp` | `Tagname` → `scada_tags.json` (site, equipment, units, normal range) | A compressed archive: a row when a value changes beyond its deadband, and at least hourly. `Quality` 192 is good, 0 marks the start of a gap, 64 the first scan after one, 216 a manual entry. When a site stops reporting, its tags stop producing rows. |
| Outage map | outage management export | `telemetry/outage_map.csv` | `timestamp_utc` | `area_id` → `areas.json`; `substation_id` → `infrastructure_assets.json`; `feeder_id` → `gw_host_registry.json` equipment | Customers served and out, every 15 minutes, for the weeks around landfall. |
| Work orders | maintenance work-order export, several organisations | `maintenance/work_orders.csv` | `reported_date`, `status_date`, `actual_finish` | `asset_id`, `vendor_id` | A row carries its status history. |
| Base status reports | daily installation status | `maintenance/base_status_reports.csv` | `report_date`, `reported_utc` | `installation_id` → `facility_registry.json` | |
| Fuel deliveries | delivery tickets and tank dips | `supply/fuel_deliveries.csv` | `delivered_utc` | `supplier_id`, `facility_id`, `contract_id`, `lot_id` | |

### The utility: alerts, network sensor, audit tables and portals

**One sampling rule for the utility's network and host logs.** Read it once; every log in this section and the next follows it.

- *Sampled, 1 in 200:* traffic that people cause (browsing, opening applications and files, mail clients talking to the mail server) and the ordinary chatter between internal servers. It is the same sample everywhere: a sampled flow that is in the sensor log also has its firewall, web-filter, packet-capture and endpoint records.
- *Recorded in full:* security alerts; sessions on the remote-access gateway and the employee VPN; interactive logons; traffic that machines produce on a schedule (endpoint agents, licence, update and time checks); the mail transfer of every message in the mail gateway table; and the flows and host records behind every alert and every audit-table row.
- *The utility's own response:* records dated from 2027-10-02T14:33Z onward include the utility's investigation and response (an incident ticket, evidence exports, settings audits, host triage collections, restoration work).

So do not read the number of rows a host has as a measure of how busy it was, and scale only the sampled part (by 200) before comparing volumes. The partner organisations' logs (further down) state their own sampling.

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Security alerts | SIEM alert queue with analyst dispositions | `network_logs/siem/siem_alerts_<month>.csv`, `rule_changes.csv`, `daily_summary.csv` | `time_utc` | `src_host`, `dst_host`, `user` → `gw_host_registry.json` | Complete: daily counts are real counts. Most alerts are routine. An alert about a person names someone at work on the machine they are logged on to. Alerts about historian bulk reads, monitored file writes and alarm-suppression changes each correspond to one row of an audit table (the daily re-evaluation alerts, raised while the suppression list is over its threshold, have no row of their own). Alerts about a new VPN location or a remote-desktop logon outside a person's listed hours correspond to a row of the employee VPN table and to a Windows logon. The raw records behind the other alerts are in the other logs of this section and the next. Alerts from control-network sources raised while the control network was cut off (2027-10-12 to 2027-10-19) reached the SIEM when it was reconnected; they keep their event time, and the device-availability rules for those sources did not run in that period. Analysts close alerts while on shift; rules close others automatically. |
| Network connection logs | Zeek `conn`, `dns`, `ssl`, `http`, `files`, `x509`, `notice` | `network_logs/zeek/<YYYY-MM-DD>/*.log` | `ts` (epoch) | `id.orig_h`, `id.resp_h` → host `ip` in `gw_host_registry.json`; `uid` links `dns`, `ssl` and `http` rows to their `conn` row | One folder per UTC day, 2027-07-16 to 2028-01-12. `http.log` is plain HTTP only. `files.log` lists files seen in plain HTTP (sizes and hashes, no content). `x509.log` lists certificates seen in TLS 1.2 handshakes, linked from `ssl.log` `cert_chain_fps`; TLS 1.3 hides the certificate. Addresses and names outside the utility were made up for the exercise; they say nothing about the real holders of those addresses. |
| Audit logs | remote-access gateway sessions, employee VPN sessions, historian access, device configuration changes, SCADA commands, alarm-suppression audit, file integrity, change management, settings audits, endpoint protection, mail gateway | `network_logs/audit/*.csv` | `time_utc`, `login_utc`, `start_utc` | hosts, users and equipment → `gw_host_registry.json` | Complete, except the mail gateway table, which is a sample of ordinary mail plus every message behind a mail alert. The file-integrity table covers the whole engineering file server (`GW-SRV-OT-01`): every write that server's event log shows has its row. Change tickets (`CHG-`, `EMR-`) are records of `change_management.csv`, whose records begin a few weeks before the other tables; work orders (`WO-`) are rows of `maintenance/work_orders.csv`; vendor tickets (`VND-`) belong to the vendors' own systems and are not in the data. File hashes are shown shortened to 16 hexadecimal characters. Six further tables (`mail_gateway_city`, `mail_gateway_airstation`, `mail_gateway_brightwake`, the two `mail_url_clicks_*` reports and `account_logons_city_airstation`) are extracts of three partner organisations' logs; the same rows are in `partner_it/`. |
| Portal access logs | web access and authentication logs | `network_logs/portal/*.csv` | `time_utc` | `account_ref` → `account_id` in aid applications (aid portal) or `account` of the air station in `partner_it_registry.json` (logistics system); `system` → external systems in `gw_host_registry.json`; `client_ip` on the base network → air station host `ip` | Every request to the disaster-aid portal and to the air station's logistics system: people, and the crawlers, monitors and scripts that visit any public site. The aid portal has no accounts until registration opens at 2027-11-13T06:00Z (midnight local). `account_ref` is filled when a request belongs to an account and is empty when a sign-in name matches no account. `client_network` is the network of the address as `ASN <number>` (`base network` for the base's own workstations). A month too large for one file is split into `_01`, `_02` in time order. |

Records in different systems that describe the same action agree to within a few seconds; where a log stamps the end of a session and another the start, the difference is the duration.

### The utility: raw network and host logs

The same activity as the alerts, the sensor log and the audit tables, as each device or host recorded it. Hosts, addresses and accounts join to `gw_host_registry.json`.

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Firewall session logs | session and drop log of the internet edge firewall (`GW-FW-EDGE-01`) and the IT/OT boundary firewall (`GW-OT-FW-01`) | `network_logs/firewall/fw_<device>_<month>.csv` | `time_utc` is the session **end**; start = `time_utc` − `duration_s` | `src_ip`, `src_port`, `dst_ip`, `dst_port`, `proto` = a row of Zeek `conn.log`; `src_zone`, `dst_zone` → `network_zones` | One `allow` row for every sensor flow that crosses the device, TCP and UDP. `bytes_sent` and `bytes_recv` count whole packets (the `orig_ip_bytes` and `resp_ip_bytes` of `conn.log`). `deny` rows have no sensor flow: on the edge they are a sample of unsolicited internet traffic. Outbound sessions leave from `nat_src_ip` (the utility's public block is 12.186.44.64/28). The boundary firewall has three legs: corporate side, `ot-dmz`, and the control network (all other `ot-*` zones); flows that stay inside one side cross neither firewall. The edge device logs sessions to and from the internet only; traffic between the internet DMZ and the inside (for example the mail gateway handing mail to the mail server) is not in its log. |
| Web and DNS filter logs | access log of the transparent web and DNS filter (`GW-SRV-PROXY-01`) | `network_logs/proxy/web_proxy_<month>.csv` | `time_utc` (request time) | `client_ip` → host `ip`; `user` → `users`; client and second = start of the flow in `conn.log` | HTTPS shows the server name only (`CONNECT`, no path). A `blocked` request never left the network, so it has no flow; blocked requests are complete. `scheme` `dns` rows are lookups of names the filter has no category for, each with the client, name and second of that lookup in `dns.log`; they are complete too. `user` is a name when the request was made in that person's session, and `-` for requests made by the operating system, services and agents. |
| Address lease logs | DHCP lease audit log of the user networks and the employee VPN pool | `network_logs/dhcp/dhcp_leases_<month>.csv` | `time_utc` | `hostname`, `ip`, `mac`; `scope` → `network_zones` | Complete. Machines have reserved addresses, so a host's address never changes; a machine that is switched off logs nothing. Each employee VPN session (`audit/employee_vpn_sessions.csv`) gets a pool address (`scope` `corp-vpn`) for its duration; the device is a company laptop or a home computer (`DESKTOP-…`, `LAPTOP-…`, not in the registry, but the same name and `mac` every time). |
| Perimeter packet capture | flow-cutoff capture on the inside of the internet edge | `network_logs/pcap/perimeter_<YYYY-MM-DD>.pcap` | packet timestamp | 5-tuple = `conn.log`; the first packet has the `conn.log` `ts` | Only the opening of each flow is kept: for TCP the handshake and the first application message (the TLS ClientHello with the server name, the HTTP request, a mail server's greeting); for UDP the request and its answer. Later bytes are not kept and TLS contents are opaque. Opens in tcpdump, Wireshark, tshark or Zeek. |
| Windows event logs | Security, System and Defender channels forwarded from the utility's Windows hosts | `network_logs/windows/security_<month>*.jsonl`, `system_<month>.jsonl`, `defender_<month>.jsonl` | `time_utc` (milliseconds) | `host` → `hostname`; `user`, `target_user` → `username`, `ot_account`, service `account` (machine accounts are `<hostname>$`); `src_ip` → host `ip` or a VPN pool address; `logon_id` pairs a logon (4624) with its logoff (4634) | A forwarded subset of event ids (listed in `schemas/windows_event_logs_schema.json`), so `record_id` rises with gaps. Interactive and remote-desktop logons are complete; network logons, share access and tickets follow the sensor flows and are therefore a sample for user-driven activity. Lock and unlock events are forwarded only from the control network and the administration wing. A host that is off writes nothing. |
| Endpoint telemetry | endpoint agent events: process starts, network connections, DNS lookups, file creation, registry values, service and task registration, removable devices | `network_logs/endpoint/endpoint_<month>.jsonl` | `time_utc` (milliseconds) | `host`, `user` as above; `src_ip`, `src_port`, `dst_ip`, `dst_port` → `conn.log`; `query` → `dns.log`; `pid` + `image` → the event's `process_start`; `sha256` → triage listings | One `network_connect` for each sensor flow that starts at a Windows host and one `dns_query` for each sensor DNS row, except ordinary web browsing, of which the agent's records keep every second one; ICMP is not recorded. Process exits are not recorded. `command_line` holds the program path and, for office programs and installers, the file that was opened. |
| Host triage collections | what the utility's security team collected from fourteen hosts in October 2027: file listing, autoruns, services, scheduled tasks, execution history, logon history, installed software, network configuration | `network_logs/triage/<host>/*.csv`, `collection.json`, `placeholders/` | `collected_utc` in `collection.json`; `*_utc` columns | folder name → `hostname`; `sha256` → endpoint telemetry; `logon_history.csv` → Windows Security events | Listings and hashes only. The collector copies every unsigned executable it finds outside the Windows folders, on every host; here each copy is replaced by an inert text placeholder whose own SHA-256 is the hash the logs record, so a hash can be followed across logs and collections with no executable content present. |

What these logs do not contain: packet payloads beyond the opening of a flow, file contents, executable samples, process exits, image loads, script or application logs, the full Windows event XML, and logs from Linux servers, network devices and controllers.

### Partner organisations: IT logs

Seven organisations each have their own firewall, web gateway, DNS, sign-on, mail gateway and endpoint-protection logs under `partner_it/<org>/`. `<org>` is `city` (City of Corpus Christi), `county` (Nueces County), `port` (Port of Corpus Christi Authority), `nascc` (Naval Air Station Corpus Christi, unclassified administrative network), `srmc` (Shoreline Regional Medical Center), `bcmc` (Bay City Medical Center) and `brw` (Brightwake Marine Systems, a marine systems vendor in Houston). Hosts and accounts join to `partner_it_registry.json`. All cover 2027-07-16 to 2028-01-12.

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Partner firewall logs | edge firewall session log | `partner_it/<org>/firewall_<month>.csv` | `time_utc` is the session **end**; start = `time_utc` − `duration_s` | `device` → host; internal `src_ip` → host `ip` | TCP, UDP and ICMP. Outbound web sessions carry the public address they left from in `nat_src_ip`. A sample of ordinary sessions; sessions that carried a remote sign-on or a logged mail message are all present. |
| Partner web gateway logs | web filtering log | `partner_it/<org>/web_<month>.csv` | `time_utc` | `client_ip` → host; `user` → account | Encrypted sites appear as `CONNECT` with no path. `user` is `-` when the machine itself made the request. A sample (about 1 in 40). Every allowed request has its firewall session and a DNS lookup shortly before it. |
| Partner DNS logs | resolver query log | `partner_it/<org>/dns_<month>.csv` | `time_utc` | `client_ip` → host; `resolver` → host | A sample (about 1 in 40). `answer` is the address the client then connects to. A client that asked for the same name in the previous five minutes uses its cached answer. |
| Partner sign-on logs | workstation logons and logoffs; single sign-on, webmail and VPN sign-ons | `partner_it/<org>/auth_<month>.csv` | `time_utc` | `host` → host; `account` → account | Complete for the hosts and accounts in the registry. `event_id` 4624 / 4634 / 4625 on Windows workstations (`login` / `logout` / `login-failed` on the few macOS ones); `sso-login`, `webmail-login`, `vpn-login` on the remote services. A workstation that loses power, or is simply left on, writes no logoff. `src_network` gives the access provider of an outside address as `ASN <number>`. |
| Partner mail gateway logs | mail gateway message log | `partner_it/<org>/mail_<month>.csv` | `time_utc` | `gateway` → host; own-domain addresses → account `mailbox` | Inbound, internal and outbound mail with the gateway's verdict and action. A sample (about 1 in 25; bulk mailings more completely). Same columns as the mail tables in `network_logs/audit/`. |
| Partner endpoint protection events | endpoint protection console | `partner_it/<org>/endpoint_alerts_<month>.csv` | `time_utc` | `host` → host; `initiated_by` → account or `system` | A sample. Three different products are in use across the organisations; version strings and detection names differ accordingly. |

- These are seven separate networks. Each has its own address plan, rule and zone names, web policy, products and working habits. A value that is ordinary in one folder may not exist in another.
- The registry lists the hosts that are modelled, not every device an organisation owns. An account without a workstation in the registry can still receive mail and sign on remotely.
- Traffic that stays inside an organisation does not cross its edge firewall or web gateway and is not in these logs. Where a mail gateway stands in the organisation's own network, its exchanges with outside mail servers appear in the firewall log.
- Outside names and addresses are invented. Network labels (`src_network`, `client_network`, `source_asn`, `src_asn`) come from one table: the same address carries the same network number in every stream that records one.
- Four tables in `network_logs/audit/` are cut from these logs, row for row: the three mail gateway extracts and the sign-on extract (see the audit logs above). The two `mail_url_clicks_*.csv` tables are the mail gateways' own reports of every link in delivered mail that a recipient followed in the same windows, with the client address as the gateway saw it. A link followed at a workstation is also in that organisation's web, DNS and firewall logs; a link followed on a phone or at home shows an outside address and never crossed that network.

### Money

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Contracts | vendor registry, business filings, awards, invoices, contract actions, debris monitoring surveys | `payments/contracts_*.csv` | registration, award, invoice, action, filing and survey dates | `supplier_id`, `piid`, bank account ids → `entity_registry.json`; awarding body → `organizations.json` | |
| Financial transactions | ACH and card transaction log | `payments/financial_transactions.csv` | `timestamp` | `account_id`, `counterparty_id` | |
| Aid applications | application records, determinations, disbursements, account-change audit | `payments/aid_applications.csv` | `event_utc` (also `submitted_utc`, `changed_utc`, `login_utc`) | `account_id` ↔ portal log `account_ref`; `area_id`, `tract` → `areas.json` | Begins when registration opens. |
| Insurance claims | claim and policy-transaction records | `payments/insurance_claims.csv` | `transaction_date`, filing and loss dates | `policy_id`, `insurer_id`, `adjuster_id` → `entity_registry.json` | **A sample: about 1 claim in 170** of those reported for the three counties. |
| Census tracts | ACS-style tract tables | `census/*.csv` | static | `GEOID`, `TRACT`, `AREA_ID` → `areas.json` | The tract index carries evacuation-zone and water-district ids. |

### Public voice

| Stream | Imitates | Files | Time | Join on | Notes |
|---|---|---|---|---|---|
| Public alerts | IPAWS/EAS alert log | `public_health/eas_broadcasts.csv` | `IssuedAt_UTC`, and separate `ReleasedAt_EN` and `ReleasedAt_ES` | `AreaIDs` → `areas.json` | English and Spanish releases are logged separately. |
| Broadcast logs | station programme, status, alert relay and translation job logs | `broadcast/*.csv` | `air_time_utc`, `received_utc` | `station_id` → `organizations.json` broadcast stations; `alert_id` → public alerts | |
| Official statements | dated statements, notices and releases | `press_releases/statements_<month>.jsonl` | `issued_local` (**local**) | `issuer` | Text as the issuer wrote it. |
| Social media | Twitter v1.1-style tweet objects, one per line | `social_media/<handle>.jsonl`, `community_<month>.jsonl`, `_account_lookup.jsonl`, `_platform_records_return.jsonl` | `created_at` | `user.screen_name` → `personas.json` | One file per listed account, monthly files for the wider community. Replies, retweets and quotes carry the ids they refer to. `_account_lookup.jsonl` is a users/lookup snapshot taken at the end of collection. |

## 5. Geography reference

`reference/geo/` holds real, published geometry (sources and accuracy in the `SOURCES_*.md` files):

| File | What |
|---|---|
| `channels_usace.geojson`, `channel_lines_usace.geojson` | Federal navigation channels (reach polygons with maintained depth, and centrelines): the Corpus Christi Ship Channel, La Quinta, the Intracoastal Waterway and side channels |
| `anchorages_fairways_noaa.geojson` | Charted anchorage areas and safety fairways off the pass |
| `land_local.geojson`, `water_overrides_local.geojson` | Land areas at harbour and coastal chart scale for the local area |
| `land_gulf_coarse.geojson` | Coarse land for the whole Gulf basin |
| `roads_*.geojson`, `rail_port_corridor.geojson` | Road centrelines (highways, arterials, local streets) and port rail |
| `landmarks.geojson` | Real landmark points: docks, airports and runway ends, hospitals, stations, schools, gauges, bridges |

Landmark names in the reference files are real-world names. The data uses fictional names placed on real sites: a hospital in the data sits on a real hospital site but carries an invented name. Join by position, not by name.

## 6. Coverage limits you should know about

- **AIS** stops at receiver range; a voyage is not followed to the far port. Small boats and unpowered barges may never appear.
- **ADS-B** shows only aircraft that transmit it.
- **Network and host logs** record sessions, alerts, scheduled machine traffic and everything tied to an alert or an audit record in full, but only a sample of what people do: 1 in 200 for the utility; the partner organisations' logs state theirs (section 4). Do not compute volumes without scaling the sampled part.
- **Raw logs are records, not contents.** Packet captures stop after the first packets of a flow, file listings carry hashes and sizes only, and no executable content is included anywhere.
- **Insurance claims** are a 1-in-170 sample; totals in public statements refer to the full population.
- **Historian** rows are change-driven; the absence of a row means "no change", unless the site has stopped reporting.
- **Sensors fail.** Weather stations, gauges, cameras, radars and network sensors have gaps, most of them around landfall. A gap is information.
- **Positions carry noise.** Vehicle and radar positions have a few metres of scatter; AIS and ADS-B positions are as broadcast.
- **Records are updated.** Work orders, port calls and dispatch records show their final state, with history where the source system keeps it.
- **Everything is synthetic.** Values behave like their real counterparts but are not measurements of the real world.

## 7. The news

The game master runs a newsroom server and gives you its address (for example `http://10.0.0.25:8080/`).

| What | Where |
|---|---|
| Newsstand: all eight outlets | `/` |
| An outlet's site (home, sections, articles, searchable archive) | `/ledger/`, `/harborline6/`, `/coastline/`, `/gulfwater/`, `/sabal/`, `/continental/`, `/anchor-rotor/`, `/kncb/` |
| Feed instructions with examples | `/feeds` |
| JSON: published stories, newest first | `/api/articles` with `outlet`, `q` (search), `since` (ISO time or Unix seconds), `limit` (up to 500), `offset` |
| JSON: one story | `/api/articles/<id>` |
| JSON: outlets and counts | `/api/outlets` |
| JSON: the exercise clock | `/api/clock` |
| RSS per outlet, and all outlets | `/<outlet>/rss.xml`, `/rss/all.xml` |

Stories appear when they are published on the exercise clock. One outlet is a Spanish-language radio station and publishes bilingual pieces. Poll no faster than every 15 seconds.

## 8. Worked joins

These use ordinary, everyday records. The method is what matters.

**A vessel from a position report.** In `data/ais/ais_2027-08.csv`, the row for `MMSI` 367977490 at `2027-08-18T15:00:07` reports 5.8 knots near the Port Aransas ferry crossing with the name `TARPON FLATS`. In `registries/vessels.json`, the vessel with `mmsi` 367977490 is `VSL-0315`, *Tarpon Flats*, class `ferry`, operated by the Texas Department of Transportation, with `home_berth_id` `SLIP-FRY-05`. That slip is in `registries/terminal_registry.json` under `slips`. The same MMSI appears in `data/port_surveillance/` as `correlated_mmsi` when a radar contact was matched to it.

**A measurement from a historian row.** `data/telemetry/historian_TANKS_202708.csv` begins `GW.TK01.LEVEL.PV,2027-08-15T00:00:04Z,17.47,192`. In `registries/scada_tags.json`, `GW.TK01.LEVEL.PV` is "Northwest Storage Tank 1 - Water level", in feet, with a normal range of 8 to 20 and a low alarm at 5, at site `GW-FAC-TK-01`. Quality 192 means a good reading. The next row for the tag is 45 minutes later, because the level had not moved beyond its deadband.

**A patient's neighbourhood.** In `data/public_health/ed_visits_FAC-SRMC-001.csv`, visit `SRMC-270820-0087` arrives at `2027-08-20T19:01:17Z` (14:01 local) with `Patient_Tract` 484201. `registries/facility_registry.json` gives `FAC-SRMC-001` as Shoreline Regional Medical Center. `registries/areas.json` has the tract as `AREA-TRACT-484201` with a reference point and bounding box, and `data/census/nueces_tract_index.csv` and `acs_nueces_tracts.csv` give its population, income and language figures. Counting visits by tract and dividing by tract population gives a rate you can compare across neighbourhoods.

**An ambulance run from call to hospital.** In `data/911/cad_incidents_2027-08.csv`, incident `12-2027-000453` is a `MEDEMER` call received at `2027-08-19 10:11:47` local (15:11:47 UTC) at 242 Ave B, tract 481001. Unit `M-16` is dispatched at 10:13:22, arrives at 10:17:06, and the incident clears at 10:56:54 with disposition `TRNSPT` and `transport_destination` `FAC-FPCH-013`. In `data/avl/avl_2027-08_CCEMS.csv`, the 22 rows with that `incident_number` trace the unit in UTC: `ENR` from 15:13:22 to 15:16:52 (a report every 15 seconds while moving), `ONS` from 15:17:06, `TRN` from 15:32:36 and `HSP` from 15:35:15 to 15:46:04, standing still at the hospital. The dispatch and arrival times in the two files agree to the second once the local times are converted. `registries/cad_units.json` gives `M-16` as an ambulance of agency `CCEMS` with its `home_station`; `registries/facility_registry.json` gives `FAC-FPCH-013` as Five Points Community Hospital. Road distance along `reference/geo/roads_*.geojson` lets you check the travel time. Rescue incidents also carry `sar_case_number`, which is the `case_number` in `data/sar/sar_missions.csv`.

**A connection from a network log.** In `data/network_logs/zeek/2027-08-18/dns.log`, the row with `uid` `C3dcc2df8db1daf365` (`ts` 1818547535.551716, that is 2027-08-18T00:05:35Z, early evening local time) is a lookup of `www.cellcarrier-account.com` from `10.14.21.13` to `10.14.10.5`, answered with `13.233.240.179`. The same `uid` is in `conn.log` as a UDP port 53 flow with `service` `dns` and `conn_state` `SF`: every `dns.log` row has its flow in `conn.log`. In `registries/gw_host_registry.json`, `10.14.21.13` is `GW-WS-IT-10`, an office workstation in zone `corp-users-biz`, and `10.14.10.5` is `GW-SRV-DC-01`, a domain controller and DNS server. A fraction of a second later `ssl.log` has `uid` `C01f7601175cace614` from the same workstation to `13.233.240.179` port 443 with `server_name` `www.cellcarrier-account.com`; its `conn.log` row with that `uid` shows 13.8 seconds and about 85 kB received. Addresses that match no host in the registry are outside the utility. A user's ordinary hosts and working hours are in the registry's `users` list.

**One web request seen by six devices.** At `2027-08-18T12:34:14Z` the web filter log (`data/network_logs/proxy/web_proxy_2027-08.csv`) has client `10.14.21.20`, user `npatel`, `CONNECT` to `www.helpdesk-tickets.com`, 2,119 bytes out and 194,337 in. The registry gives `10.14.21.20` as `GW-WS-IT-17`. The sensor has the same flow in `zeek/2027-08-18/conn.log` (`uid` `C4fb047c2113b151b7`, source port 58257, 19.52 s, the same byte counts) and its handshake in `ssl.log` with that `uid`, TLS 1.2, and a `cert_chain_fps` value that is the `fingerprint` of the site's certificate in `x509.log`. The edge firewall log `firewall/fw_GW-FW-EDGE-01_2027-08.csv` has the session with the same 5-tuple, ending at 12:34:34Z (start plus duration), leaving from public address `12.186.44.68`, with 5,171 and 200,029 bytes (whole packets, equal to `orig_ip_bytes` and `resp_ip_bytes` in `conn.log`). `pcap/perimeter_2027-08-18.pcap` holds the opening packets of the flow, the first at the `conn.log` `ts`, with the server name in the ClientHello. On the workstation, `endpoint/endpoint_2027-08.jsonl` has a `network_connect` at 12:34:14.824Z with the same addresses and ports, `pid` 12664, image `chrome.exe`; the `process_start` of that `pid` is at 12:26:14Z under the same user; and `windows/security_2027-08*.jsonl` has that user's logon (4624, type 2) on the host at 12:25:05Z and logoff at 21:50Z. The lease log shows the workstation renewing `10.14.21.20` the day before, at 2027-08-17T07:46Z.


## 9. Glossary

| Term | Meaning |
|---|---|
| AIS | Automatic Identification System: position reports broadcast by vessels |
| MMSI | Maritime Mobile Service Identity: a vessel's nine-digit radio identity |
| ADS-B | Automatic Dependent Surveillance-Broadcast: position reports broadcast by aircraft |
| ICAO24 | An aircraft's 24-bit transponder address, written as six hex digits |
| NIC / NACp | ADS-B integrity and accuracy categories reported by the aircraft's navigation source |
| AVL | Automatic vehicle location: GPS reports from response vehicles |
| CAD | Computer-aided dispatch: the 911 centre's incident records |
| ANI / ALI | The caller's number and location information delivered with a 911 call |
| ED | Emergency department |
| ESI | Emergency Severity Index: triage acuity, 1 (most urgent) to 5 |
| EAS / WEA / IPAWS | Emergency Alert System, Wireless Emergency Alerts, and the federal system that carries both |
| SCADA | Supervisory control and data acquisition: the utility's control system |
| Historian | The archive of SCADA measurements over time |
| RTU | Remote terminal unit: the device at a substation or pump station that reports to SCADA |
| SIEM | Security information and event management: where security alerts are queued and reviewed |
| Zeek | A network monitor that writes connection, DNS, TLS, HTTP, file and certificate logs |
| 5-tuple | Source address and port, destination address and port, protocol: identifies one network flow |
| NAT | Network address translation: the public address an internal host appears as on the internet |
| DHCP | The service that hands out network addresses; its log shows which machine held which address |
| pcap | Packet capture file; here only the first packets of each flow are kept |
| ClientHello / SNI | The first message of a TLS session, which names the server the client wants in clear |
| Event id | The numeric type of a Windows event, for example 4624 logon, 4634 logoff, 4625 failed logon |
| Endpoint telemetry | Events recorded by the security agent on a computer: processes, connections, files |
| Triage collection | A snapshot of a computer's configuration and file listing taken by responders |
| ASN | Autonomous system number: identifies the network an internet address belongs to |
| COTP / MSIB | Captain of the Port; Marine Safety Information Bulletin |
| NOA | Notice of arrival filed before a ship enters port |
| Port condition | Coast Guard hurricane readiness levels for a port, set as a storm approaches |
| USACE reach | A section of federally maintained navigation channel |
| STAC | SpatioTemporal Asset Catalog: a metadata format for satellite scenes |
| PIID | Procurement instrument identifier: a contract number |
| ACS | American Community Survey: the census tables used for tract populations |
| CBPWA | Coastal Bend Power and Water Authority, the area's power and water utility |
