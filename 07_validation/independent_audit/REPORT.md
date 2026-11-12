# Independent audit of the regenerated data streams

Auditor: independent agent, 2026-11-10. Scope: `05_other_sources/**` against `00_scenario/canon_timeline.json` and `canon_decisions.md`.
All checks were written from scratch in this folder (`a01_*.py` … `a11_*.py`, `mygeo.py`); nothing from `scripts/streams/probes_*.py` or `scripts/check_streams.py` was used. `scripts/geo.py` was used only as a second opinion next to my own point-in-polygon code on the raw GeoJSON.

## Verdict by area

| # | Area | Verdict |
|---|---|---|
| 1 | Port and ships | PASS (minor notes) |
| 2 | Aircraft | PASS (minor notes) |
| 3 | 911 and vehicles | PARTIAL |
| 4 | Utility | PARTIAL |
| 5 | Weather and sensors | PASS (minor notes) |
| 6 | Health | PASS (minor deviations from canon figures) |
| 7 | Alerts and public voice | PARTIAL |
| 8 | Money | PASS (minor notes) |
| 9 | Cross-stream identity | PASS (minor notes) |
| 10 | Answer leakage | PARTIAL |
| 11 | 20 random expected observations | 19 found, 1 partly found |

What I did not cover, so nobody reads a PASS wider than it is: drone telemetry, SAR missions, shelters, damage assessment, portal access logs and the news corpus were only touched where a sampled expected observation led there. Land/road/channel tests use the project's own reference polygons (my code, their geometry). Road and land tests are samples (30,000 AVL fixes, 50,000 AIS positions; all 911 incidents, all radar contacts and all ADS-B ground rows were tested in full). The value sweep for labels read the first 30,000 rows of each CSV.

---

## 1. Port and ships — PASS

Files: `ais/ais_*.csv` (1,313,056 rows), `ais/satellite/*.csv`, `supply/*.csv`, `port_surveillance/*.csv`.

* **Closure.** Deep-draft test = registry `deep_draft` OR AIS Draft ≥ 7.5 m OR Length ≥ 120 m, inside the jetties (LON < -97.035), SOG > 0.5 kn. Window 2027-09-13T17:00Z → 2027-10-14T16:00Z: 1,486 such rows, **0 moving**, none displaced > 300 m. Window 2027-10-28T06:25Z → 2027-11-11T14:00Z: 1,376 rows, **0 moving**. Radar agrees: the only ship-size moving contacts inside the bay in both windows correlate to three Coast Guard cutters (MMSI 369509450, 369530490, 369559628). `vessel_traffic_log.csv` in the windows: coast guard 98, navy 4, tug 5, nothing else. `vessel_arrivals.csv`: 0 ATA/ATD inside either window.
* **14 held offshore.** Exactly 14 vessels at Status 1 offshore between Yankee (09-12T12:00Z) and Zulu, including GULF PROVIDER and HALCYON DRIFT. Count per 6 h bin: 14 … 14, 11 (13 Sep 18Z), 0 from 14 Sep 00Z through 17 Sep 00Z, back to 14 by 17 Sep 18Z.
* **Tankers.** KALVORA STAR moored 2027-09-11T16:26:05Z at 27.81447,-97.40133 and does not move until 2027-11-15T15:00Z; OSTREL BAY moored 09-11T15:38:45Z until 11-15T19:00Z. Max AIS gap 1.01 h. Matches `vessel_arrivals` (ATA 16:25:44 / 15:38:35) and COTP letter 27-2034.
* **Gulf Provider** berths 2027-10-17T19:11:02Z (D+33); arrivals file ATA 19:10:22Z; manifest has 12+9+8+6+5 = 40 relief containers booked 2027-09-09.
* **Corrin Bay** at 27.83048,-97.03350 at 06:00:14Z on 2027-10-28, SOG 9.4; stopped with status 2 from 06:13:13Z.
* **Speeds.** Implied speed between consecutive reports: 0 of 726,649 pairs (Aug–Oct) above 30 kn. Max reported SOG 24.1 kn (type 55).
* **Land.** 50,000 random positions (both feeds): 0 on land with my own point-in-polygon and 0 with `geo.is_land_many`. All 299,426 radar contacts: 0 on land. Deep-draft, SOG > 3 kn, inside the bay: 3 of 45,257 outside a USACE channel polygon, all within 1 m of its edge.
* **Arrivals vs AIS.** 177 arrivals with ATA: median difference AIS moored-start minus ATA 0.3 min; the only large gaps are six port calls whose ATA predates the AIS span. Sea manifests: 182 rows, all join an arrival, 0 MMSI mismatches, 0 released before arrival.
* Radar track NE-001301 is AIS-correlated to 511836259 until 01:34:59Z and from 16:34:59Z on 2027-10-15 and uncorrelated in between (377 plots, 176 m hull) while PELICAN RIDGE (338724891) transmits 02:04:50Z–15:54:51Z. Works as designed.

Notes (minor): reported SOG and positions disagree at every start (CORRIN BAY 2027-08-20T13:54:24Z reports 3.4 kn at the same coordinates as 55 s earlier; ferries go 0 → 5.8 kn in one report; about 3% of moving reports). GULF PROVIDER jumps 257 m to the round coordinate 27.79000,-96.90000 when it weighs anchor (09-13T19:29:00Z). CORRIN BAY sits at identical coordinates for 3.5 h while "not under command" in the entrance channel. The tankers load from ballast (7.8 m) to 14.2 m draft between 09-11 and 09-13T02:00Z, i.e. through X-Ray and Yankee, although canon says crude loading winds down at X-Ray and exports halt at Yankee. `vessels.json` marks Halcyon Drift (176 m, 8.8 m draft) `deep_draft: false`.

## 2. Aircraft — PASS

File: `adsb/adsb_*.csv` (978,275 rows, 64 airframes, all in `aircraft_registry.json`, one callsign each, 0 duplicate icao+time).

* **Epoch.** Every file's min/max time falls inside its own month; NOAA42 appears 08:20–08:49Z on 2027-09-14, C6033 lifts at 06:22:05Z. No 40-hour shift.
* **TFR.** From 2027-09-12T05:01Z to landfall: **0 rows airborne within 30 nm of KCRP at any altitude** (in fact no airborne row at all). First aircraft after landfall: C6033 06:22:05Z, C6041 07:06:05Z, NOAA42 08:20Z.
* **Navy trainers.** Last flights 2027-09-10 (18 airframes leave northbound, last fixes near 30.4N at 19:19–23:53Z); 0 trainer rows 09-11 … 09-19; return 09-20 (T-6, T-44), 09-21, 09-22 (T-45).
* **Relief airlift.** Landings at NGP 2027-10-18 … 10-27 local: **26 C-17**, 10 B734/B752 + 4 AT72 = **14 civil**. All 26 C-17 landings in the whole dataset are at NGP in that window.
* **Runways.** 4,011 fixed-wing landings and 3,986 take-offs: all within 1 m of a runway centreline. 202,742 on-ground rows: 0 in water. Two helicopter lift-offs "in water" (AIRMED1 10-27 02:33:48Z, AIRMED2 10-24 22:59:17Z) are GPS-interference scatter (NIC 1, NACp 2–4), inside the canon jamming window.
* **Envelopes.** C172 ≤ 112 kt / 5,079 ft; T-45 ≤ 366 kt; C-17 ≤ 383 kt / 34,984 ft; H-60 ≤ 130 kt; MQ-9 ≤ 170 kt / 19,995 ft. Good detail: during landfall C6033 shows pressure altitude 453 m at 2.8 m geometric altitude, which is what a 960 hPa surface pressure does to a barometric altimeter.
* **GPS interference.** Mean NIC drops from 7.95 to 4.2–5.2 on 2027-10-22 … 10-27 and recovers on 10-28/29.

Notes (minor): the stream starts 2027-08-15T12:25:27Z, 12 h after the required start. Every landing is within 1 m of the centreline (no lateral scatter at all). T-45 vertical rate reaches −64 m/s and MQ-9 −24.8 m/s.

## 3. 911 and vehicles — PARTIAL

Files: `911/cad_incidents_*.csv` (73,457 incidents), `911/reports/*`, `avl/*.csv` (1,297,919 fixes).

Passes:
* **Daily counts** D0 1,841; D+1 2,900; D+2 2,600 (2,109 with `sar_priority=Y`); D+3…6 mean 1,620; D+7 1,580; D+8 1,490; D+12 1,623; D+28 380; D+29 372; D+45 311; baseline 311. Report totals 44,291 (D0–D+28) and 56,793 (D0–D+45) match canon. WATERSAFE first used 2027-09-26 18:05:03 local = 23:05Z.
* **Land.** 73,457 of 73,457 incidents on land.
* **Roads.** 30,000 sampled fixes: all within 10 m of a road centreline (99th percentile 2.7 m).
* **Dispatch → arrival.** 18,937 incident/unit pairs in September and 8,084 in November: AVL en-route start equals CAD dispatch to the second, on-scene fix equals CAD arrival, on-scene fix 12–28 m from the incident, implied mean speed 6–85 km/h, 0 above 130 km/h. The DST change on 7 November is handled.
* **Bridges.** Strict south-bank ↔ North Beach transitions per local day: 80 (12 Sep), 70 (13 Sep), **0 on 14, 15, 16 Sep**, 78 on 17 Sep starting 12:14 local, 236 on 18 Sep. No unit is ever on the Portland side of the causeway.

Failures:
* **Storm-only incident types in the dry baseline (major).** 598 of the 7,162 incidents from D-30 to D-8 carry storm narratives: "NEIGHBOR NOT SEEN SINCE STORM" (89), "SUBJS ON FOOT AFTER CURFEW"/"VEH CRUISING DARK AREA AFTER CURFEW" (143 curfew violations before D-7; the first on 2027-08-15 00:08, and one at 11:06 in the morning), 146 shelter requests, 33 water rescues ("FAMILY ON ROOF WATER RISING", 2027-08-15 05:39). In all, 191 curfew violations are logged before the curfew exists (D+1). The same mix continues after D+75 (257 curfew violations, 52 water rescues, 286 shelter requests) long after the water has gone.
* **Counts are too regular (minor).** D+13 → D+27 is an exact geometric series (1400, 1278, 1166, 1065, 972, 887, 810, 739, 674, 616, 562, 513, 468, 427, 390; ratio 0.913 every day). D+29 → D+38 falls by 3 or 4 a day with no weekday effect. In `cbecc_daily_call_volume.csv` the ten-digit-line count is exactly 390 on every day from D+29 to D+45, then drops to about 200; it looks like a fill to reach 56,793.
* **False rescue calls start five hours early against canon (minor).** The 23 no-find calls near SUB-02/SUB-03 (all area code 737, prepaid) are 9 / 7 / 5 / 2 on 21–24 Sep, matching 9 + 14, but the first is at 09:07 local (14:07Z). Canon decision: "use 19:00Z (14:00 local) on D+7".
* Shift log 2027-10-30: "CORPUS RETAINED FOR TRAINING: 56,793 CALLS…" reads like an author note; language split there (65.1/33.9/1.0) differs from canon (64.8/34.1/1.1) and from the incidents (66.2/32.8/1.1).
* Parked units sit on the road centreline (0.0–0.1 m), not at a station; moving fixes have no GPS scatter (median 0.0 m).

## 4. Utility — PARTIAL

Files: `telemetry/historian_*`, `telemetry/outage_map.csv`, `maintenance/work_orders.csv`, `network_logs/**`.

Passes:
* **Same event, same time.**

| Event | Historian | Audit / command log | Other |
|---|---|---|---|
| Relay threshold 0.88 → 0.94 | `GW.SUB1.REL.UV_THR.SP` 2027-09-11T17:04:23Z | `ot_config_changes` 17:04:23Z | session RAS-20653 17:00:07–17:15:29Z; Zeek conn 17:00:05Z |
| SUB-02 breaker | `GW.SUB2.BKR1.CMD.SP` 2027-09-21T14:28:15Z, status 14:28:17Z | `scada_command_log` 14:28:15Z | session RAS-20656 14:24:39–14:32:01Z; WO-2027-32252 reported 14:39:15Z |
| P-3 setpoint 85 → 68 | `GW.UTL1.PUMP3.PRESS.SP` 2027-09-23T02:04:01Z | `ot_config_changes` 02:04:01Z (booster 02:08:00Z in both) | session RAS-20657 01:59:25–02:12:27Z |
| SUB-03 breaker | `GW.SUB3.BKR1.CMD.SP` 2027-09-24T19:43:46Z, status 19:43:48Z | `scada_command_log` 19:43:46Z | session RAS-20658; WO-2027-32253 19:52:46Z |
| Isolation | `GW.SCADA.EXT_ISOLATED.STS` and `GW.JMP.SERVER.COMMS.STS` 2027-10-12T12:00:00Z | P-3 restored 12:14:00Z in historian and `ot_config_changes` | WO-2027-OT-0881 "07:00 local" |

  All 14 external sessions have a matching Zeek connection (start 2 s earlier, same source address). All 181 Zeek day folders hold only timestamps of their own UTC day.
* **Outage curve.** Peak 72,000 at 2027-09-14T10:00Z; SUB-01 goes to 24,000 out at 07:12/07:15Z; +8,381 at 09-21T14:30Z; +6,754 at 09-24T19:45Z; 36,000 flat from 09-28 to 10-12T12:00Z; 3,247 at 10-19T19:45Z, **0 at 20:00Z (D+35)**. No missing 15-minute step.
* **Water plant.** P-2 flow 0 from D0 until D+38/39; plant flow median 28 MGD (D0–D+4) and 27.5 (D+9–D+28) against 63 before; zone pressures median 16–22 psi (D0–D+4), 33–39 (D+4–D+9), 32–36 (D+9–D+28), 43–47 (D+28–D+39) against 56–62 normal. Zone 4: 19.85 psi at 09-23T06:00Z, 15.19 after the SUB-03 event, 16.25 at 09-26T16:00Z, rising after 10-12, 58.8 at 10-23T14:00Z. Not "healthy" in either notice window.

Failures:
* **The hostile records are labelled in all but name (major).**
  * `scada_command_log.csv`, column `session_context`: 376 rows "console logon active", exactly 2 rows "no console logon on workstation; remote desktop session from GW-SYS-JMP-01" — the two breaker commands.
  * `remote_access_sessions.csv`: `auth_method` is "token" on 645 rows and "password only" on exactly the 14 hostile rows; `change_ticket` is empty on exactly those 14; `bytes_out` is a round multiple of 100,000 on exactly those 14; their ids are one contiguous block RAS-20646…20659 inserted out of sequence.
  * `ot_config_changes.csv`, `change_type`: every benign row "approved change"; the hostile rows "write outside change window (storm-preparation freeze in effect)", "remote write", "file replaced".
  * `settings_audits.csv` rows of 2027-10-02: "14 sessions, account GW-ENG-VELA, source networks in NL, RO, SG and DE; 11.4 hours total" and "alarm-suppression and setpoint changes fall inside the same remote sessions". `siem/rule_changes.csv` 2027-10-18: "created by svc_fieldops_ext 19 days before the first matching session". These hand over the conclusion of threads T8/T10/T18.
* **Telemetry loss (minor).** Canon: telemetry lost D0 to D+3. Data: quality-0 gaps of 4–14 h alternating with good data (P-3 setpoint: lost 09-14T09:30Z, back 23:10Z, lost 09-15T03:15Z, back 07:45Z, …); only 5–40% of D0–D+4 rows are bad.
* **Restoration too smooth (minor).** Customers-out falls by 17–22 every 15 minutes, day and night, for a week; 36,000 exactly for 14 days. At 36 h after a landfall on Mustang Island, Padre Island is 1,625 of 4,500 out and Flour Bluff 2,586 of 6,000 while inland Calallen is 9,500 of 9,500.
* **Audit trail gap (minor).** The SUB-02 overcurrent change 1200 → 2400 A at 2027-09-11T22:11:07Z is in the historian and `file_integrity.csv`, and its reversal on 10-19 is in `ot_config_changes.csv`, but the original write is not in `ot_config_changes.csv`.
* SIEM close notes are assigned at random: ADMIN_GROUP_CHANGE closed as "Password mistyped", OT_FILE_WRITE as "Known scanner", DEVICE_COMM_LOSS as "Approved removable media"; four notes with about 67,000 uses each.
* "Monthly breaker inspection" work orders on the same breaker two days running (GW-SUB02-CB-8, 11-04 and 11-05) and three times in December (GW-SUB03-CB-9).
* Source addresses of the intrusion are real routable ranges (185.220.101.x, 45.141.152.x, 104.21.88.43) and real-TLD domains (`meridiancontrols.net`, `cbpwa-vendor-support.com`) rather than documentation ranges and `.example`.

## 5. Weather and sensors — PASS

* **ASOS (7 stations).** Diurnal minimum 02–04 local, maximum 13–15 local at every station; dew point never above temperature; gust never below wind; RH 37–99%.
* **Storm peak.** KRAS (Port Aransas): 49.1 m/s (95 kt) gust 63.0 at 02:53Z, minimum pressure 947.1 hPa at 05:53–06:13Z, then silent 06:33Z → 09-19T16:53Z. KTFP 82 kt / 967.1 at 06:13Z then out to 09-17; KNGP 43 m/s, 959.7 at 07:13Z, out 32 h; KCRP 36.4 m/s, 968.5 at 09:33Z, out 6 h. Buoy 42020: 949.1 hPa at 10:50Z on 13 Sep, when the advisory centre is 4–7 nm away.
* **Surge.** Port Aransas gauge TG-8775237: residual 11.12 ft = **3.39 m** at 06:00Z (water level 3.84 m MLLW). Aransas Pass 3.03 m, Lexington 2.51 m before it fails. GAUGE-14 offline 2027-09-14T04:42Z → 09-19T14:00Z (canon D0–D+5).
* **Hydrocarbons.** Baseline 20 ppb. First excursion: WQ-02 Harbor Bridge 04:30Z, WQ-01 Industrial Canal 04:45Z (86 → 427 → 807 → 1,227 ppb by 05:30Z), WQ-05 Tule Lake 06:15Z; then WQ-06 North Beach 09-15T08:30Z, WQ-03 Nueces Bay 09-15T20:30Z (2,100 ppb on 09-18 at 16:30Z and 21:30Z), WQ-04 mid-bay 09-16T07:15Z (peak 408).
* **Air.** Hillcrest benzene 4.80 ppb at 09-16T14:00Z, 7.20 at 09-17T02:00Z, last value above 3 ppb 09-19T16:00Z; refinery-row TNMHC 12,400 ppbC at 09-16T16:00Z.

Notes (minor): all six sondes share the same baseline (20.2 ± 2.8 ppb) whether in the Industrial Canal or mid-bay. Buoy 42020 air temperature is 24.2 °C for more than 30 hours and its pressure is back to 1001.7 hPa while a 944 hPa centre is 44 nm away. Benzene jumps above 3 ppb at four sites in the same hour on 2027-12-22T20:00Z with no canon event.

## 6. Health — PASS

* **Summary = line list.** 90,893 visits; 13,806 facility/day/category cells and 57,701 area cells: **0 mismatches**; admitted counts 0 mismatches; `hospital_capacity.ED_Visits_24h` equals the line list on 1,050 of 1,050 rows. Visit_Date equals the local date of arrival on every row once DST is applied.
* **Waves.** All-hospital visits 542/day baseline → 855 / 976 / 1,020 on D+1…D+3. Injury 80 → 197–337 (D0–D+3). CO poisoning 0 → 21–25/day D+1…D+3. GI 11.3/day baseline → 29.0 on D+6…D+14 → 96 (D+16), 226 (D+17), 345–350 (D+18…D+22), 20 on D+28. D+18…D+22 GI cases come from ZIPs 78416, 78405, 78407, 78408; Spanish-preferring share 55% on D+15…D+17 against 24% baseline. Wastewater norovirus ratio 0.0015 (D+4) → 0.0066 (D+6) → 0.0243 (D+11). SRMC census 700 (140.0%) with 62 in the triage tent on 09-16, 540 on 09-22, 475 on 10-12; generator 06:17:26Z → 09-22T14:14:33Z, 195.05 h.

Deviations (minor): SRMC arrivals in the first 12 hours of D0 are 70–75 (canon 118). The citywide GI rise is +157% (canon +180%). Canon's own cluster figures do not add up (340 a day for five days is already 1,700 against a stated total of 1,820); the line list has about 2,700 excess GI visits D+15…D+28.

## 7. Alerts and public voice — PARTIAL

Passes:
* `eas_broadcasts.csv` (42 rows): every non-test alert is at its canon time (watch 09-11T15:00Z; Zone A 09-12T11:00Z EN / 13:47Z ES; warning 17:00Z / 17:08Z; A-B-C 09-13T12:00Z / 12:15Z; shelter C–E 18:00Z / 09-14T01:52Z; shelter in place 05:45Z / 05:50Z; citywide boil 09-18T12:00Z / 12:15Z until 10-23T14:00Z; lifts 10-23T14:00Z and 10-26T16:00Z bilingual). **Districts 3/4: EN 2027-09-26T22:30Z, ES 2027-09-27T11:03Z = 12 h 33 min**; `translation_jobs.csv` agrees (delivered 04:45Z, aired 11:03Z).
* Forbidden strings in 114,775 posts, 180 statements, 42 alerts, 1,936 broadcast rows and 73,457 CAD narratives: **0** for Halcyon Drift, KESTREL, GridWater, GW-ENG-VELA, ClearPath, Barge 44, Valero, Citgo, Flint Hills, Caller-Times, KIII, KRIS, Spohn, Driscoll, Auriga, Pier 9. Gated names in post text before their day: 0 for Pelican Ridge, Corrin Bay, Vantorra, Quellmar, Brightwake, Brannoch, Marrick, Kalvora, Ostrel.
* Foreknowledge scan (26 rules: spill, boil water, Districts 3/4, blast, second device, GPS, hack, parasite, account takeover, …): 0 early posts on 24 of them; the 11 early "Individual Assistance" hits are the state's request for it on 2027-10-09, which is canon; the curfew rule fails (below).

Failures:
* **Author notes inside delivered statements (blocker, three records).** `press_releases/statements_2027-08.jsonl` PUB-009: "The country is never named in this scenario's coverage; refer to 'a foreign government' or 'an overseas power'." PUB-014: "(scenario value: about half)". `statements_2028-01.jsonl` PUB-100: "(the scenario ends about four months after landfall)".
* **Curfew known before it exists (minor).** 34 posts "Curfew at dark. Streets are empty. Eerie." between 2027-09-12T22:29Z and 09-14; the curfew starts D+1 (alert 2027-09-15T14:00Z).
* **Outage bot contradicts the outage map (minor).** Posts "Nueces County, TX: N customers without power (CBPWA outage map)": 398 of 856 inside the map's span differ by more than 2% from `outage_map.csv`; 2027-09-14T08:07Z bot 36,000, map 52,626 (the bot ramps linearly and has no SUB-01 step).
* PUB-024 (D0) lists a "Rendal Terminals" spokesperson; the name is gated to D+1.
* The crude-export terminal's account posts "Open regular hours today. Come see us." and "Thank you Downtown for another great week."
* The ferry bot keeps posting "Port Aransas ferry wait: 5 min" on 2027-10-29 while every segment of the channel is closed.

## 8. Money — PASS

* **Registration.** 51,356 applications, none before 2027-11-13T00:01:00Z; 47,820 between 13 Nov and 12 Dec (canon 48,000).
* **Takeovers.** Exactly **410** accounts with a direct-deposit change from ASN 64512, all `login_ip_seen_before = N`, 2027-11-15T19:53Z → 11-23T21:19Z (D+62–D+70), to three accounts (****1073, ****5333, ****3176); 410 "restored after identity verification" rows; $3.86 million reissued. Six applications from the same network share two devices, two addresses (one is the shell companies' 4520 Agnes St Suite 210) and the same three accounts. Prepaid-card purchases 2027-11-19 → 12-04, $2.07 million.
* **Contracts.** NC-EM-2027-0071 Vantorra, $14,200,000, sole source, 2027-09-24 (D+10). N6883627C0075 Quellmar, $2,100,000, 2027-09-26 (canon: awarded D+12, public D+20 — the brief's "D+20" is the public day). Both vendors registered 2027-08-05, same address, same bank account. Vantorra billed 60,969 tons against 26,332 surveyed (2.32×).
* **Claims.** 5,581 claims: loss date min 2027-09-14, 0 before landfall day, 0 filed before loss, 0 paid before filing. Ring: 230 policies of holder PH-100001 written at 3.4× assessed value with RUSH appraisals, 198 claims from 2027-09-17, two contractors, reused photographs on 24%.

Notes (minor): 158 applications are stamped before 06:00Z on 13 Nov, i.e. on the evening of D+59 local. Oil-spill claims: 4,204 in total but only 3,425 fall in canon's D+60–D+89 window (618 earlier, from 2027-09-26). See area 10 for the two status values.

## 9. Cross-stream identity — PASS

* About 60 id columns checked against the registries: **0 unknown ids** for MMSI (AIS, radar, cameras, traffic log, arrivals, manifests, port orders), terminals and berths, sensors, stations, facilities, CAD units and nature codes, SCADA tags (331), areas, hosts (SIEM, endpoint, audit), suppliers, insurers, adjusters, drone operators, SAR assets, personas. AVL units: 0 unknown. ADS-B: 0 unknown.
* One MMSI ↔ one name everywhere; FAC-SRMC-001 is the same hospital in ED visits, capacity, CAD transport and fuel deliveries.
* Leftovers: 0 occurrences of FAC-CCMC, Auriga, Pier 9, GridWater, PHANTOM in any delivered file; "7c1234" occurs only inside one random Zeek connection uid; no 1821024000-based time found (ADS-B, Zeek and AVL all on the right clock).

Notes (minor): `outage_map.feeder_id` values (GW-SUB01-CB-2 …) are not in `infrastructure_assets.json`, which the catalog names as their registry. ASN notation differs by stream: "ASN 11427", "AS-209144", "64512", 198765, and "ASN-SYN-64512" / "ASN-SYN-64496" in `vessel_cargo_control_remote_sessions.csv` — the last is an internal-id form that `restricted_terms.json` bans. Canon text still says SUP-0388 / SUP-0390 for the two shell companies; registries and streams use VND-0001 / VND-0002.

## 10. Answer leakage — PARTIAL

* **Headers.** 111 CSV families: no column named for attack, fraud, bot, truth, label, scenario or thread. `phase` appears only as the survey phase in two aerial-survey files.
* **Thread ids and day notation.** No "T8"-style id (the 2,971 "T14" hits are ICD-10 codes) and no "D+12"-style notation in any stream.
* **Values that single out the answer** (all found by counting distinct values):
  * the four utility items in area 4;
  * `payments/aid_applications.csv` status "held, suspicious-activity flag SA-2027-TX-4471" on exactly the 94 ring applications;
  * `payments/insurance_claims.csv` status "under review, special investigations unit" on 86 claims, all 86 on ring policies;
  * "scenario" wording in PUB-009, PUB-014, PUB-100 (area 7);
  * `06_data_streams/cad_units.json` carries an `event` block with `"d0_date"`.

## 11. Twenty random expected observations

Drawn with `random.seed(20271109)`, one per stream (`a11_sample.json`).

| # | Event / stream | Found | Evidence |
|---|---|---|---|
| 1 | EVT-0101 ed_visits, baseline about 520/day | yes | 542/day D-30…D-8 |
| 2 | EVT-2007 news, designation and claims | yes | Gulfwater Maritime Report 2027-09-21T15:15 "Coast Guard designates owners…" |
| 3 | EVT-2202 insurance_claims, ring claims from D+3 | yes | 230 policies, 198 claims from 09-17, contractors VND-0003/0004, 24% reused photos |
| 4 | EVT-1105 outage_map, SUB-02 circuits listed as storm | yes | 402 rows cause STORM, all three feeders fully out 09-21T14:30Z → 09-23 |
| 5 | EVT-2006 water_quality, Nueces Bay 2.1 mg/L | yes | WQ-03 2,100.0 ppb at 2027-09-18T16:30Z |
| 6 | EVT-1208 port_conditions, partial reopening | yes | MSIB 27-051 effective 2027-10-14T16:00Z |
| 7 | EVT-1102 satellite, 08:30Z D0 pass | yes | NOAA42-SAR-20270914T083000Z-CCBAY, 5 m, two hulls, 2.1–3.4 m inundation |
| 8 | EVT-2004 air_quality, Hillcrest benzene | yes | 4.80 / 7.20 ppb at the stated hours |
| 9 | EVT-0316 vessel_ot_logs | yes | commands from station RMT-GW, session BRW-S-27129 03:52:10–05:35:12Z; later logins "DENIED: remote access disabled"; 9,053 bbl lost across both ships |
| 10 | GW-EVT-105 host_audit_logs, 82 alarms added | yes | 82 ADD rows since D-5, 12 → 94 active, 7 change times |
| 11 | EVT-1602 hospital_capacity, generator | yes | lost 06:17:03Z, start 06:17:26Z |
| 12 | EVT-2106 eas_alerts, BWW-2027-0926-001 | yes | BWW, 22:30Z; CharCount_EN says 287, the headline is 281 characters |
| 13 | EVT-1407 census, 46.7% limited English | yes | S1601_C05 / S1601_C01 over the 9 district tracts = 46.7% |
| 14 | EVT-1707 avl, routes end near SUB-02/SUB-03 | yes | 23 no-find incidents within 600 m of the two substations |
| 15 | EVT-0202 storm_advisories | yes | first TS advisory 2027-09-04T09:00Z; 09-09 forecast ends at 27.8N 97.2W |
| 16 | EVT-0301 weather, minima around 06:00Z at KNGP, KCRP, Port Aransas | partly | Port Aransas 05:53–06:13Z; KNGP 07:13Z; KCRP 09:33Z (consistent with the track, not with "around 06:00Z") |
| 17 | GW-EVT-001 zeek_logs, lookalike domain | yes | dns.log 2027-08-30 13:23:02Z, 10.14.22.47 → update-cdn.meridiancontrols.net; protection disabled 13:21:44Z; lure 13:14:09Z |
| 18 | EVT-1702 adsb, CG-6033 | yes | airborne 06:22:05Z from NGP, hover from about 06:45Z near 27.672,-97.298 |
| 19 | EVT-0503 aid_applications, six linked applications | yes | six applications from ASN 64512, two devices, three shared deposit accounts |
| 20 | EVT-0402 port_surveillance, uncorrelated contact | yes | track NE-001301, 377 plots 02:04:59–15:58:59Z |

---

## Ranked defects

| Rank | Severity | Defect | Where | Suggested fix |
|---|---|---|---|---|
| 1 | blocker | Author notes in public statements ("this scenario's coverage", "scenario value", "the scenario ends…") | `press_releases` PUB-009, PUB-014, PUB-100 (and their source in `02_public_record/public_record.json`) | Delete the three clauses at source and regenerate; add "scenario" to `restricted_terms.json` |
| 2 | major | Hostile utility records separable by one `uniq -c`: `session_context`, `auth_method`, empty ticket, round byte counts, contiguous session ids, `change_type` | `network_logs/audit/scada_command_log.csv`, `remote_access_sessions.csv`, `ot_config_changes.csv` | Drop `session_context` (the absence of a console logon is already inferable from the logon stream) or give benign rows the same variety; add benign password-only and ticket-less sessions; draw session ids and byte counts from the same generator as the rest; record what the device logs ("write", source host), not a judgement |
| 3 | major | Logs that state the conclusion | `network_logs/audit/settings_audits.csv` (two "evidence export" rows), `siem/rule_changes.csv` (2027-10-18 row) | Reduce to what such a record holds (export id, requester, file count); move the findings to the answer key |
| 4 | major | Storm-era incident types and narratives in the pre-storm baseline and in December (598 of 7,162 baseline incidents; 191 curfew violations before the curfew) | `911/cad_incidents_*.csv` | Make the nature-code and narrative mix depend on the day: no curfew, shelter, "since storm", roof or boat narratives before their triggering event, and a decay afterwards |
| 5 | major | Status values that mark exactly the fraud set | `payments/aid_applications.csv` (94 rows), `payments/insurance_claims.csv` (86 rows) | Either remove them or dilute them: add false positives and leave part of the ring unflagged, dated when the real review would have happened |
| 6 | minor | Curfew mentioned in 34 posts before D+1 | `social_media/*.jsonl` | Gate the template on 2027-09-15T14:00Z |
| 7 | minor | Public outage bot disagrees with `outage_map.csv` (398 of 856 posts; 36,000 vs 52,626 at 08:07Z D0) | `social_media/` outage bot | Generate the bot from the map, rounded |
| 8 | minor | False rescue calls start 14:07Z, canon decision says 19:00Z | `911/cad_incidents_2027-09.csv` | Shift the nine D+7 calls by five hours |
| 9 | minor | Call counts, ten-digit-line counts and restoration curve are noise-free series | `911/`, `cbecc_daily_call_volume.csv`, `outage_map.csv` | Add weekday effect and noise to calls while keeping canon anchor days; restore customers in feeder-sized steps, mostly in daylight; make coastal feeders the worst hit |
| 10 | minor | Telemetry is only intermittently lost D0–D+3 | `telemetry/historian_*` | Either extend the bad-quality runs or relax the canon sentence |
| 11 | minor | SUB-02 relay write missing from the configuration audit that records its reversal | `network_logs/audit/ot_config_changes.csv` | Add the 2027-09-11T22:11:07Z row, or drop the reversal row and leave both to file integrity |
| 12 | minor | "ASN-SYN-…" internal id form; five ASN notations | `telemetry/vessel_cargo_control_remote_sessions.csv` and others | One notation ("AS64512") everywhere |
| 13 | minor | Real routable addresses and real-TLD domains for attacker infrastructure | `network_logs/**` | Use documentation ranges and `.example` |
| 14 | minor | PUB-024 names Rendal Terminals on D0 (gate D+1) | `press_releases/statements_2027-09.jsonl` | Move the speaker to the D+1 statement or lower the gate to D0 |
| 15 | minor | Health figures off canon: SRMC first 12 h 70–75 vs 118; GI +157% vs +180%; canon cluster total inconsistent with its own peak | `public_health/ed_visits_*`, canon | Raise D0 SRMC arrivals; fix canon total |
| 16 | minor | Spill claims spread from 2027-09-26, only 3,425 of 4,204 in canon's D+60–D+89 window; 158 aid applications before local midnight of D+60 | `payments/` | Align window or canon wording; open registration at 06:00Z |
| 17 | minor | Too-perfect geometry: landings within 1 m of centreline, vehicles on centreline with zero scatter and parked in the road, tug "not under command" fixed for 3.5 h, instant speed changes | `adsb/`, `avl/`, `ais/` | Add metre-scale noise, park units at station coordinates, ramp speeds |
| 18 | minor | Small oddities: ADS-B starts 12:25Z on 15 Aug; `feeder_id` not in its registry; Halcyon Drift `deep_draft: false`; tankers load through Yankee; random SIEM close notes; repeated "monthly" inspections; terminal's chatty social account; ferry-wait posts during the blast closure; CharCount 287 vs 281; shift-log "CORPUS RETAINED FOR TRAINING"; `cad_units.json` `d0_date`; identical sonde baselines; canon text still cites SUP-0388/0390 | various | Tidy individually |

## Scripts

`common.py`, `mygeo.py` (own point-in-polygon), `a01_ais_closure.py`, `a01b_ais_speed.py`, `a01c_ais_events.py`, `a01d_tankers.py`, `a01e_ais_land.py`, `a01f_ais_land_indep.py`, `a01g_ais_offchannel.py`, `a01h_arrivals.py`, `a01i_inner.py`, `a01j_radar.py`, `a02_adsb.py`, `a02b_adsb_tfr.py`, `a02c_adsb_flights.py`, `a03_911.py`, `a03b_avl.py`, `a03c_avl_bridge.py`, `a03d_avl_cross.py`, `a03e_avl_roads.py`, `a03f_resp.py`, `a04_events.sh`, `a04b_outage.py`, `a04c_wtp.py`, `a05_weather.py`, `a05b_env.py`, `a05c_aq.py`, `a06_health.py`, `a06b_health.py`, `a07_public_voice.py`, `a07b_foreknowledge.py`, `a08_money.py`, `a08b_money.py`, `a09_ids.py`, `a10_headers.py`, `a10_scan.py` (too slow on this mount; replaced by fixed-string grep, patterns listed in the report sections 9 and 10), `a11_expected.py`, `a11b_expected.py`, `a11c_expected.py`, `a11_sample.json`. Several scripts read `/tmp/adsb.pkl` and `/tmp/cad.pkl`, which `a02_adsb.py` and `a03_911.py` write first.
