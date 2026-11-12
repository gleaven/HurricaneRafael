# Second independent audit of the data streams

Auditor: independent agent, 2026-11-11. Scope: re-check of the first audit's defects (A), the streams it did not cover (B), cross-stream consistency at 16 canon moments (C), answer leakage and realism (D).
All checks are my own code in this folder (`a_*.py`, `b_*.py`, `c_*.py`, `c2_*.py`, `canon_dump.py`, `common.py`; raw outputs in `out/`). Nothing from `scripts/streams/probes_*.py` or `scripts/check_streams.py` was used; `scripts/geo.py` was used only for land and road tests. No file outside this folder was changed.

Limits, so no PASS is read wider than it is: 911, AVL, SAR, shelter and damage files were judged on logic and content, not coordinates. Satellite hull counts were not recomputed from AIS. News stories were not read. The ADS-B extract used for SAR is September only. Canon puts the generator failure on D+40 (2027-10-24) and makes it public on D+41; the brief's "D+41" is the public day. Canon puts the jetty blast at 06:10Z.

## Verdicts

| # | Item | Verdict |
|---|---|---|
| A1 | Author notes in public statements | PASS |
| A2 | Values that single out hostile rows in utility logs | PARTIAL (old tells gone, new ones found) |
| A3 | Post-discovery records that state the conclusion | PASS (minor residue) |
| A4 | Storm narratives in pre-storm 911 calls | PASS |
| A5 | Aid / claims flags that mark exactly the ring | PASS (one residual case id) |
| A6 | Posts that mention things too early | PARTIAL |
| A7 | Outage bot vs outage map | PASS |
| A8 | Noise-free series (911, outage) | PASS for those two; other regular series listed in D |
| B1 | Authorised drone telemetry | PASS (minor) |
| B2 | Drone detections and sighting reports | PARTIAL: timing and geometry PASS, leakage FAIL |
| B3 | Search and rescue | PARTIAL: canon totals exact, aircraft do not match ADS-B |
| B4 | Shelters | PARTIAL |
| B5 | Damage assessment | PARTIAL |
| B6 | Aid portal and base logistics logs | PASS (minor) |
| B7 | SIEM volumes | PASS against expected observations (minor) |
| B8 | Network sensor (Zeek) logs | FAIL |
| B9 | Satellite items | PASS (minor) |
| B10 | Fuel deliveries and base status reports | PARTIAL |
| B11 | Wastewater | PASS |
| B12 | Contracts | PASS on amounts and dates; fuel invoices contradict fuel deliveries (see B10) |
| C | 16 canon moments across streams | 6 fully consistent, 10 with at least one stream that contradicts or stays silent |
| D | Leakage and realism | PARTIAL: no give-away headers or thread ids; several value and id tells |

---

## A. Re-check of the first audit's defects

**A1 Author notes — PASS.** `press_releases/*.jsonl`: 0 hits for scenario / placeholder / fictional / hackathon / answer key. PUB-009, PUB-014, PUB-100 now read "A foreign government announces…", "…about half.", "Four months after Rafael: …". The one "synthetic" hit is "synthetic aperture radar". PUB-024 no longer names Rendal Terminals.

**A2 Utility logs — PARTIAL.**
Fixed: `session_context` is gone; `remote_access_sessions.csv` now has 150 benign password-only and 185 benign ticket-less sessions beside the 14 hostile ones, no round byte counts, ids monotonic in time with no gaps; `ot_config_changes.change_type` has 26 "remote write", 15 "file replaced", 13 "local panel".
Still separable with one count:

| File | Tell | Rows it returns |
|---|---|---|
| `historian_access.csv` | `query_type` = "bulk read" (1,266 others are "trend") | exactly the 14 hostile sessions |
| same | session numbers of those rows step by 37 (00441, 00515, 00552, 00589 … 00922) | same 14 |
| same | `tag_groups` in a notation of its own, e.g. "relay_config(all 5 substations)" | hostile only |
| `file_integrity.csv` | `diff_summary` filled on 1 of 161 rows ("overcurrent_trip_threshold 1200A -> 2400A for relays R-02A…") | the hostile write |
| `endpoint_protection.csv` | 1 `REALTIME_PROTECTION_DISABLED` in 7,190 rows (698 "ENABLED" with nothing else ever disabled), `detail` "setting changed locally; no alert generated", the only row not `initiated_by` system | the initial access, 2027-08-30T13:21:44Z |
| `scada_command_log.csv` | `device` GW-SUB02-CB-7 and GW-SUB03-CB-12 occur once each, the other nine devices 32–49 times; `origin` remote desktop with empty `operator` is 2 of 42 | the two breaker commands |
| `alarm_suppression_audit.csv` | `changed_by` GW-ENG-VELA = 82 rows = all hostile ADDs; the 12 benign ADDs are by "operator shift supervisor" at exactly 14:00:00Z every third day | all hostile |
| `ot_config_changes.csv` | `new_value` "last_modified 2027-09-11T22:11:26Z (17:11 local)", the only value with a local-time gloss | the hostile file write |
| `remote_access_sessions.csv` | `target_hosts` holding more than one host (";") | 5 rows, all hostile |
| `vessel_cargo_control_remote_sessions.csv` | the 15 hostile sessions are ids 27177–27238 (one benign id in that range; benign ids otherwise 27003–27176 and 27241–27247); all hostile logins 18–23 h local, all benign 9–15 h; `duration_s` a multiple of 60 on 9 of 15 hostile and 1 of 60 benign; login second "00" on 8 of 15 against 6 of 60 | the hostile block |

Also still open from audit 1: the SUB-02 relay write of 2027-09-11T22:11:07Z is absent from `ot_config_changes.csv` (only its reversal on 10-19 is there); SIEM close notes are still random (DEVICE_COMM_LOSS closed as "Password mistyped" 1,579 times).

**A3 Conclusion records — PASS.** `settings_audits.csv` export rows now read "session log export SLE-2027-10-02 / 14 session records" and "2027-09-07 to 2027-10-02"; `rule_changes.csv` 2027-10-18 reads "removed (AUDIT-EXC-2027-10)". Residue: "14 session records" still hands over the count.

**A4 911 baseline — PASS.** 73,647 incidents. CURFEWVIO first on D+2 (0 before), WATERRESC / TRAPPEDVEH / ROOFCOLLAP / STORMDAMAG / URBANSAR first on D0, SHELTERREQ from D-3, EVACENFOR D-2…D0, WATERSAFE D+12…D+42. Daily counts now carry noise (D+13…D+18: 1414, 1280, 1227, 1061, 956, 948). False rescue calls: 9 on 2027-09-21 between 14:07 and 17:53 local (19:07–22:53Z), then 7 / 5 / 2 = 23; callback area codes are now mixed (361 ×8, 830 ×5, 956 ×3, 512 ×3, 210 ×2, 737 ×2). Residue: the phrase "PEOPLE (ARE) IN DANGER NOW" occurs 12 times in the whole CAD, all 12 on false calls.

**A5 Aid and claims flags — PASS.** `aid_applications.csv`: 1,712 "held, suspicious-activity flag" rows, 74 of them on ring applications. `insurance_claims.csv`: special-investigations status on 26 ring and 42 other claims. Residue: flag number SA-2027-TX-4471 is carried by ring applications only (74 of 74), all stamped 2027-11-16T16:14:02Z.

**A6 Early posts — PARTIAL.** 116,981 posts, 21 rules. Curfew first mentioned 2027-09-15T16:38:31Z (was 09-12). No early hit for boil water, Districts 3/4, spill, GPS, account takeover, Pelican Ridge, Vantorra, Quellmar, Corrin Bay; no internal ids. New: "If you waited more than a day for help after the storm, I want to hear from you." is posted 30 times before landfall by three reporter accounts, first on 2027-07-16T12:57Z (D-60).

**A7 Outage bot — PASS.** 860 bot posts inside the map's span, 0 differ from `outage_map.csv` by more than 2%.

**A8 Regular series — PASS for the two named.** Restoration now comes in steps (518 of 576 quarter-hours on 15–21 Sep unchanged; none between 03 and 05 h or after 19 h local); coastal feeders are 100% out at the peak.

---

## B. Streams not covered before

### B1 Authorised drone telemetry — PASS
444 flights in telemetry, 445 in `flight_log.csv` (the extra one is the crewed thermal sortie CBAS-TIR-0925, which is in ADS-B as N208CB 09:19:25–11:33:30Z, passing 115–243 m from SUB-01/02/03). 14 operators, all in the registry. Every flight has an authorisation that covers its time, place and height; 0 launches off land; 0 landings more than 200 m from launch. No flight from D-4 to D0; first after landfall 2027-09-15T11:47Z; every flight D+1…D+10 is under a Special Governmental Interest waiver. Canon days hold: SAR thermal D+1…D+5, grid survey D+3 (8 aircraft, 1,433 km; canon about 1,440), depot hangars D+2, utility yards D+8, completion D+45. Envelopes: multirotors at most 13.3 m/s and 111 m; fixed wing 29.5 m/s, 122.5 m, 110 min.
Minor: optical surveys fly in darkness (FEMA-UAV-0922-UTL-01…03 take off 10:03–10:56Z = 05:03–05:56 local with a "42 MP nadir mapping camera, visible"; sunrise is about 12:17Z; canon's 10:30Z is the root). Every flight of a model tops out at the same height (Matrice 30T: 45.4 m on 30 of 46). 0 missing frames in 444 flights. Eight survey aircraft launch at exact 20-second intervals from 12:02:00Z. Three landing fixes are in water by `geo.is_land` (FLT-DRN-OP-005-20270917-03, -014-20271015-01, -006-20271019-01).

### B2 Drone detections — PARTIAL
Timing and geometry PASS:
* Pre-storm sorties are where canon puts them. Sortie 2: ESM contact 2027-09-05T06:47:00–06:47:02Z, 902.4 MHz, bearing 306.7° from the aircraft at 27.7492,-97.0794; ADS-B has the aircraft 1.8 km from there 21 s later, and 306.6° is the bearing to Ingleside Marina, where *Narwhal Dream* reports by AIS from 09-02T21:07Z to 09-07T00:14:00Z. Sortie 3: R-22 inbound 04:07:46–04:14:18Z, R-18 over SUB-01 04:14:58–04:32:10Z (128 m from the site), R-22 outbound 04:32:50–04:39:22Z. Sorties 4 and 5: R-22 2027-09-09T04:58:00–05:16:12Z and 09-11T04:45:00–05:07:08Z, 9–21 m from the berth, RCS 0.012–0.015 m² (alert threshold 0.05), alert false. Radar range, bearing and position agree to 1 m.
* Air-station perimeter sensors offline 2027-09-14T06:00Z → 09-26T16–20Z; 0 tracks D0…D+11. Portable detector: two bursts, 2027-09-22T03:41:10Z and 09-24T04:12:35Z. Sighting reports near the base on six nights (D+1, 2, 4, 5, 7, 9: 4, 4, 3, 6, 4, 6 reports), every bearing within 60° of the base. Nothing hostile after D+11. All 395 "uas" tracks carry a Remote ID and an authorisation.

Leakage FAIL:
* **Track ids.** Hostile tracks hold the lowest sequence numbers: R22-270906-00001, R22-270906-00002, R22-270909-00003, R22-270911-00004, R18-270906-00001, R14-270906-00001, R14-270906-00002, while R-22's first August track is 00005. The hostile ESM contact is CAMCC04-270905-00976, the highest of 976 numbers, among 00131–00148.
* **Report ids.** `sighting_reports.csv` SR-…-0001 to 0027 are exactly the 27 hostile-night reports; benign reports are 0028 and up (SR-270915-0028 at 13:04Z precedes SR-270915-0001 at 02:50Z the next day).
* **Dispositions.** "logged; no sensor confirmation" (17) and "logged; forwarded to investigators" (10) occur only on those 27.
* **Signatures.** `rf_signature` "analog-style video downlink burst" (2), "frequency-hopping burst, data link" (1) and "frequency-hopping, 2.4 GHz control link" (1) occur only on hostile rows; on ESM-CAMCC04 the class "unknown emitter" is on 2 of 977 rows.

Minor: no sighting report at all before 2027-09-15; "bright light low in the western sky after sunset" is logged at 13:04:40Z (08:04 local); four unresolved "drone over the debris site" reports on D+22, 25, 39, 66; base status has the sensors "degraded" 09-15…09-24 and "operational" from 09-25 while the sensor log has them offline 09-14…09-26.

### B3 Search and rescue — PARTIAL
Canon totals are exact: 486 by 2027-09-15T20:00Z (341 by air, 180 hoists), 702 by 09-16T23:00Z, 1,427 by 09-19T22:00Z; 341 helicopter / 1,041 surface / 45 ambulatory; first launch 06:22:00Z, first rescue 06:51:00Z; CG-6033 7 sorties and CG-6041 6 on D+1; 22 task-force deployments on D+2 and 847 rescued over D+1 and D+2; 87 civilian boats from D+3; no helicopter rescue after 2027-09-17T08:00Z; 11 no-find rows SAR-27-01428…01438 (first on scene 19:31:27Z on D+7); all 1,438 incident numbers exist in CAD.
Failures:
* **Helicopters do not fly their sorties in ADS-B (major).** Of 341 helicopter rescues, 1 has an ADS-B fix of that airframe within 600 m at the on-scene time, 138 are farther away, 202 have no fix within 3 minutes. Of 29 sorties, 3 launches and 2 recoveries match within 2 minutes; 4 have no airborne fix at all. Example: SARM-27-0014, 0016, 0018 (CG-6033, 2027-09-15T05:20–11:02Z, 54 rescues) while ADS-B has CG-6033 on the ground from 02:24:33Z to 11:05:05Z. Between 06:22Z on D0 and 02:24Z ADS-B shows 24 airborne intervals for CG-6033; the log has 5 sorties.
* Sorties are mechanical: 13 of 29 carry exactly 18 survivors (an H-60 cabin takes about 6); every D+1 sortie lasts exactly 102 minutes and launches at :20 of every second hour.

### B4 Shelters — PARTIAL
Sensible: five shelters open 2027-09-12 08:00 local, two hours after the Zone A order; a sixth on 09-15; total occupancy 1,133 → 4,055 (D0) → 4,532 (D+2) → 2,400 (D+10) → 78 (11-14) → closed 11-15; peaks at 91–99.8% of capacity, never over; no rows before opening or after closing; 14 Zone D "Collier" clarification calls 14:00–20:00 local on D-1; Zavala is not in the registry.
Failures: SAR missions deliver 612 people to West Oso High School (capacity 500) on 09-15…09-19, 274 of them on 09-16, when its census shows 4 new arrivals and occupancy falling 499 → 484; King High School receives 239 by SAR while its census shows 104 arrivals over the same days. 33 SAR deliveries reach the Flour Bluff gym on 09-14, before it opens (09-15 12:00). 29 evacuation buses arrive before 08:00 on 09-12 (for example 07:30:15 at West Oso).

### B5 Damage assessment — PARTIAL
Consistent: 12,000 structures; aerial classification 2,100 major and 390 destroyed (canon); windshield surveys D0…D+2, aerial D+3…D+5, field verification from D+6, housing inspections from 2027-11-14 (after registration opens); field level never below the aerial level; mean flood depth and roof loss rise with level (none 0 ft / 0% … destroyed 6.6 ft / 73%); worst ZIPs are North Beach and downtown (78402: 45% major or destroyed, 6.1 ft), inland Robstown 13%, 0.3 ft.
Failures: assessment times are uniform over 24 hours for every type (field verification 245 at 00 h, 202 at 01 h, 206 at 10 h; housing inspections alike; aerial imagery 371–454 an hour through the night). 1,266 of 3,139 non-elevated structures with 5 ft or more of water are rated MIN or lower (CC-100959: slab, 6.3 ft, MIN). Port Aransas, at landfall with a 3.4 m surge, has 140 structures, 34% major or destroyed, 4.5 ft: less than downtown. Manufactured homes: 593 with two storeys, 1,350 of 2,567 over 2,000 sq ft. 303 addresses are shared by two or three structures. `utility_site_survey.csv`: "RGB" surveys at 09:00:03Z, 10:09Z, 10:30:00Z (04:00–05:30 local); the SUB-02 row is the only one on a round second and precedes its own tile-set acquisition (10:34–10:51Z).

### B6 Portal logs — PASS
* Probing 2027-08-10T05:00:08Z → 08-13T04:59:27Z (10–12 Aug local): 2,720 requests on the aid portal and 680 on the base logistics system from 64 addresses of ASN 64512; 810 and 185 failed logins, 0 successes; nothing from that network between 13 Aug and 12 Nov.
* Registration: 30,058 web accounts created = 30,058 web applications in `aid_applications.csv`, source address equal on all.
* Stuffing: 220,000 failed logins 2027-11-15…11-24 (20,236 / 17,625 / 24,194 / 48,138 / 38,828 / 9,398 / 13,677 / 19,494 / 27,946 / 464 per day), 410 successes on 410 accounts, 410 direct-deposit changes; all 410 match `aid_applications.csv` on account, login time, address and change time, and no portal success is missing there. First: login 2027-11-15T19:37:18Z, change 19:53:38Z, ACC-2D376DE4C0.

Minor: 9 accounts are created on 2027-11-12 between 23:42:24Z and 23:59Z, before the opening. The failed-login count is exactly 220,000, every failure is 512 bytes, the 64 addresses carry 3,540–3,557 failures each, 0 of the 220,000 targeted account ids exist, and no taken account has a prior failure. Benign use is thin: 31,025 page views for 30,058 registrations; 1,504 benign logins in two months, exactly one per profile change; seven browser families at 11,657–11,972 each. In the base logistics log every benign row is `login_success` whatever the path. Probe account ids are literally "guess-3252e3".

### B7 SIEM — PASS
461,537 alerts; `daily_summary.csv` equals the rows on all 181 days. Volumes equal the expected observation: 4,812 / 7,341 / 18,340 / 16,207 / 14,884 / 12,201 / 6,633 for D-2…D+4; 2,312 on D+35; hourly rate falls from about 100 to about 9 at 08:00Z on 2027-10-12; last beacon alert 10:04:37Z. Canon alerts present with the stated fields (0831T0317Z, 0907T0244Z, 0911T2211Z, 0923T0400Z, 1002T1433Z). All hosts are in the registry.
Minor: canon's "74,120 alerts in 60 hours (5.1× baseline)" matches nothing (best 60 hours = 41,593; D-2…D+3 = 73,785; 5.1 × baseline would be about 27,900). The 10-12 drop hits mail and web-policy alerts as hard as OT ones and recovers as a straight line (235, 598, 922, 1,257, 1,588, 1,927, 2,312). `open_ml_anomaly_alerts` is 0 on every day. 31 alerts have `src_host` GW-SYS-JMP-01 while the jump host is offline (C11).

### B8 Network sensor logs — FAIL
Consistent: 307,420 connections, each in its own day folder; all 55,444 `ssl.log` rows join `conn.log` on uid, addresses, ports and time; 0 internal addresses missing from `gw_host_registry.json`; 14 of 14 hostile sessions present with matching start and duration; historian → GW-WS-IT-04 over 445 on 2027-09-08T23:58:14Z, 1.9 GB; beacon 168 flows 2027-08-30T13:23:03Z → 10-12T10:04:37Z; 0 flows to or from the jump host in the isolation window and 0 IT → OT-DMZ flows between 2027-10-11T22:53Z and 10-20T01:33Z.
Failures:
* **Three one-line filters return the intrusion and nothing else (blocker).** (1) `ssl.log` server names: 55,276 end in `.example`, 168 in `.net`, all 168 the beacon; in `dns.log` the only names not ending `.example` are the two lookalike domains (56 queries). (2) In `conn.log` every address outside 10/8, 172.20/16, 100.64/10 and 198.18/15 is hostile: 104.21.88.43 (168 flows) and eight source addresses (14 flows). (3) `service` rdp, modbus, dnp3 and port 4000 occur 9 times in six months, each one a hostile action: 09-11 17:04:17 dnp3, 17:09:18 rdp, 22:11:22 dnp3; 09-21 14:26:40 rdp, 14:28:13 port 4000; 09-23 02:03:56 and 02:07:55 modbus; 09-24 19:42:11 rdp, 19:43:44 port 4000. The README says background flows are sampled 1 in 200; the hostile ones are complete, so "not sampled" is itself the label. None of the 354 benign external remote sessions and none of the 42 benign remote-desktop commands has a flow.
* `dns.log` and `conn.log` do not describe the same lookups: 0 of 107,931 DNS uids exist in `conn.log` (which has 61,522 DNS connections); 6 share a 4-tuple.
* Service and port are paired at random for directory traffic: "krb" on 389, 135 and 445, "ldap" on 88, 135 and 445, "smb" on 88, 135 and 389 (about 2,700 rows each, some 50,000 in all).
* Every connection has `conn_state` SF.
* During the isolation the laboratory workstation GW-WTP-LAB-01 (10.72.30.50, zone ot-wtp) makes 72 flows out of the OT network: 25 to the internet on 443, 20 DNS and 27 other to corporate servers.

### B9 Satellite — PASS
159 items, id = file name, bbox = geometry. Canon scenes present: 14 hulls at the anchorage 2027-09-12T12:14Z; baseline images of the five substations, the plant and the docks 14:09–14:44Z with breakers closed; airborne radar 2027-09-14T08:30Z (two hulls, 2.1–3.4 m inundation); 112 km² flood 09-15T12:14Z; 85 km² sheen 09-16T16:48Z; "small hull about 2 nautical miles off the entrance channel" 2027-10-15T04:20Z; "two hulls side by side, one with no AIS match" 09:30Z; debris sites about every two weeks; archive receipt 10-29. Cloud 100% on D0, 72% on D+1.
Minor: the two 10-15 scenes are the only passes off the fixed 6-day 04:18 / 09:29 cycle and the only ones with an `uncorrelated` block or the suffix ANCHORAGE, yet both are described as "Routine". At 04:20Z radar holds one uncorrelated contact, 180 m long (NE-001301 at 27.7779,-96.9292), and AIS has "PELICAN RIDGE" transmitting from there, so "small hull" and "no AIS correlation" fit neither stream. Six ids differ from `datetime` by seconds.

### B10 Fuel deliveries and base status — PARTIAL
Consistent: the regular supplier's last delivery to the air station is 2027-09-07; contract N6883627C0075 awarded 09-26, first delivery under it 09-28; 380 m³ from barge BRG-0044 into the supplier's tank 2027-10-16T19:25Z (lot QF-27289-B, no certificate of analysis), that lot into generator tank EQP-2201 on 10-17, 19, 21, 23; generator fails 10-24 (readiness 89 → 61, work order NASCC-PW-27-2800 at 19:31Z, tank dipped at 2.0% from 10-26, refilled 12-18, "operational (overhauled)" 12-20); aircraft 0 from 09-10, returning 09-20; depot halted 09-10, roof damage 09-16, full production 10-31; hospital tank A empty 2027-09-19T16:30Z, tank B 23.1%, federal delivery 21:45Z.
Failures:
* **Invoices and deliveries disagree (major).** `contracts_invoices.csv`: ten invoices, 291,000 gallons, $1.69 million, tickets QF-2100…2109, service dates 10-17 … 11-22. `fuel_deliveries.csv`: nine deliveries from that supplier, 17,467 gallons, tickets FT-50412…50463, 09-28 … 10-23; from 10-26 the station is supplied federally "while the emergency contract is under review", a month before the deficiency report (11-26) and the suspension (11-28). No ticket number joins. Canon has no fuel over-billing.
* Contract action 2027-10-15: "Deliveries to begin when the ship channel reopens to fuel barges", after deliveries on 09-28, 10-05 and 10-12.
* Failure date: base report and work order say 10-24; the contract action says "generator failure on Oct. 25"; the station's post of 2027-10-25T20:00Z says "today".
* No stream shows the "commercial power interruption": the only outage in `outage_map.csv` on 10-24 is 110 customers in Tuloso (feeder GW-SUB01-CB-4) from 10-23T22:45Z to 10-24T01:30Z; nothing near the air station and nothing at the time of the work order (19:31Z).

Minor: depot readiness climbs about 2 points a day for five weeks; the generator tank loses 4.4% every two days on weekly 30-minute tests.

### B11 Wastewater — PASS
488 samples, five plants, two targets. Norovirus GII 25,000–73,000 gc/L up to D+4 (44,000), 126,000–130,000 on D+6, 377,000–527,000 on D+9…D+11, under 65,000 again by D+27. Canon: signal from D+5.

### B12 Contracts — PASS
NC-EM-2027-0071, $14,200,000, sole source, 2027-09-24; N6883627C0075, $2,100,000, 2027-09-26; both vendors registered 2027-08-05 at 4520 Agnes St Suite 210 with ACCT-40134. Billed 60,969 tons against 26,227–26,436 surveyed = 2.32×; five other haulers 0.94–1.01×. Payment hold 12-03, inspector-general review 12-07, searches 12-27 match D+80, D+84, D+104.
Minor: four ordinary awards are invoiced at 1.5–3.4 times their value (PA-ER-2027-2934: $737,646 on $220,400).

---

## C. Cross-stream consistency at 16 moments

✓ reacts as it should · ✗ contradicts, or is silent where it should react · – no reaction expected. Times UTC.

| # | Moment | Streams and timestamps |
|---|---|---|
| 1 | Reconnaissance sortie 3, 2027-09-06T04:15 | ✓ detections: R-22 04:07:46 in, R-18 04:14:58–04:32:10, R-22 out until 04:39:22 · ✓ authorisations: none · ✓ AIS *Narwhal Dream* at the Ingleside berth until 09-07T00:14:00 · ✓ ESM bearing the night before points at the marina · – sighting reports: none |
| 2 | Cargo valves open, 2027-09-14T04:00 | ✓ cargo-control: alarms inhibited 03:57:40, valves commanded 03:59:23–03:59:57 from station RMT-GW · ✓ vendor sessions 03:52:10–05:35:12 and 03:53:45–05:35:52, ASN 64512 · ✓ sondes WQ-02 04:30, WQ-01 04:45, WQ-05 06:15 · ✓ cameras dark since 02:40 · ✓ airborne radar 08:30 · ✓ statement 13:30, first post 14:31:42 |
| 3 | Landfall 06:00 and SUB-01 trip 07:12 | ✓ KRAS minimum 946.8 hPa at 06:13; gauge 12.59 ft at 06:00 · ✓ alert 05:45 / 05:50 · ✓ hospital on generator 06:17:03 · ✓ historian: breaker 07:12:26, bus 0 V 07:12:27 · ✓ outage 16,686 → 42,500 at 07:15 · ✓ ADS-B first airborne 06:22:05; SAR launch 06:22:00 · ✗ outage map has 0 customers out until 06:15, two hours into hurricane-force wind at Port Aransas (canon's own curve starts at 06:00) |
| 4 | Rescue day D+1, 2027-09-15 | ✓ SAR 480 rescues, 486 cumulative at 20:00 · ✓ CAD 2,900 calls · ✓ 20 authorised drone flights, SAR thermal among them · ✗ ADS-B: CG-6033 on the ground 02:24–11:05 while the log flies three sorties · ✗ shelters the next day: 274 SAR deliveries to West Oso against 4 census arrivals |
| 5 | Citywide boil-water notice, 2027-09-18T12:00 | ✓ alert 12:00 EN / 12:15 ES · ✓ translation 11:35 → 11:55 → 12:15 · ✓ first post 12:00:35 · ✗ 911: code WATERSAFE is not used until 09-26, then 390 calls in six hours for the district notice |
| 6 | SUB-02 breaker, 2027-09-21T14:28:15 | ✓ command log 14:28:15 · ✓ historian command 14:28:15, status 14:28:17 · ✓ outage +8,400 at 14:30, cause STORM · ✓ work order 14:39:15 · ✓ session 14:24:39–14:32:01 · ✓ historian access 14:24:58 · ✓ suppression +10 at 14:25:15 · ✓ SIEM 14:24:57 and 14:25:19 · ✓ Zeek 14:24:37, 14:24:58, 14:26:40, 14:28:13 |
| 7 | False rescue calls from 2027-09-21T19:07 | ✓ CAD: nine unfounded calls 19:07–22:53 near SUB-02 and SUB-03 · ✓ SAR: five no-find rows, on scene 19:31:27–22:59:01 · ✓ task-force team attached to the 19:26 and 21:10 calls |
| 8 | P-3 setpoint, 2027-09-23T02:04:01 | ✓ configuration audit 02:04:01 and 02:08:00 · ✓ historian setpoint 02:04:01 · ✓ Zeek modbus 02:03:56 and 02:07:55 · ✓ session 01:59:25–02:12:27 · ✓ Zone 4 29.4 psi → 20.4 by 05:30 · ✓ SIEM open alert 04:00:11 (94 suppressed) · ✗ pump discharge pressure is already 68.2 psi at 22:30 the evening before (74.6 at 18:15) and moves 1 psi at the write, while flow drops 1,660 → 584 in one sample |
| 9 | SUB-03 breaker, 2027-09-24T19:43:46 | ✓ command log 19:43:46 · ✓ outage +6,800 at 19:45 · ✓ work order 19:52:46 · ✓ Zeek 19:42:11 and 19:43:44 |
| 10 | Districts 3/4 notice, 2027-09-26T22:30 | ✓ field report 15:44, work order 17:20 "alarm did not annunciate" · ✓ Zone 4 15.6–16.6 psi all day · ✓ alert 22:30:00 EN · ✓ relays 22:30:00–22:30:01 · ✓ English reads 22:32:21 and 22:35:33 · ✓ posts 22:30:06 · ✓ 911 WATERSAFE from 23:05:00 · ✓ translation in 22:35, out 04:45, KNCB 11:03:00 |
| 11 | Control systems isolated, 2027-10-12T12:00 | ✓ historian flags 12:00:00 · ✓ work order (cut at 07:00 local) · ✓ setpoints restored at local panels 12:14 and 12:26 · ✓ no remote session until 10-20T13:44:10 · ✓ Zeek: no jump-host flows · ✓ SIEM −90% from 08:00, last beacon 10:04:37 · ✓ outage 36,000 → 0 at 10-19T20:00 · ✗ `scada_command_log`: 3 commands "remote desktop" from the jump host (10-14 10:26:35, 10-18 02:36:14 and 14:08:14) · ✗ `historian_access`: 4 sessions from it (10-13 … 10-16) · ✗ SIEM: 31 alerts with it as source · ✗ Zeek: 72 flows from the plant laboratory workstation |
| 12 | Dark vessel and devices, 2027-10-15 | ✓ partial reopening effective 10-14T16:00 · ✓ radar NE-001301 uncorrelated 02:04:59–15:58:59, 180 m · ✓ AIS "PELICAN RIDGE" 02:04:50–15:54:51, out to 27.779,-96.927 by 04:49 and back · ✓ traffic log: BARGE 44 out past the jetties 07:48:05, in 14:12:54 · ✓ fuel receipt 10-16T19:25 · ✓ satellite 04:20 and 09:30 · ✗ satellite wording (B9) |
| 13 | GPS interference, 2027-10-22…27 | ✓ ADS-B mean NIC 7.95 → 5.0–5.8, back to 7.8 on 10-28 · ✓ first post 2027-10-23T16:00:25 · ✗ AIS: the tanker moored about 2 km from the transmitter keeps its 2–4 m scatter · ✗ AVL road offsets unchanged (median 1.5 against 1.7 m) · ✗ 20 drone flights in the window, no effect · ✗ `gps_integrity_reports` has no file |
| 14 | Generator failure, 2027-10-24 | ✓ base status 61% · ✓ work order 19:31 · ✓ tank 2.0% from 10-26 · ✓ fouled lot delivered 10-17…23 · ✓ posts 10-25 · ✗ outage map: no interruption near the station or at that hour (only 110 customers in Tuloso until 01:30) · ✗ contract action and the station's post date it 25 Oct |
| 15 | Jetty blast, 2027-10-28T06:10 | ✓ AIS: tug outbound at 9.4 kn at 06:00:14, stopped from 06:13:13 · ✓ camera passage 05:55:40 · ✓ 911: first call 06:11:35, 11 explosion calls by 06:36:25 · ✓ AVL PA-1 at 06:13:11 · ✓ posts 06:14:27 · ✓ channel closed 06:25:00 · ✓ ADS-B C6017 overhead 06:44:15 · ✗ ED line lists: none of the 9 injury arrivals 06:00–12:00 is a blast, burn or marine injury, and there is no 911 transport, for "two crew injured" |
| 16 | First account takeover, 2027-11-15T19:37:18 | ✓ portal login 19:37:18, deposit change 19:53:38 · ✓ aid file: same account, times, address · ✓ first victim post 2027-11-17T14:50:45 · ✓ bank credits 2027-11-19T12:11:06 → 12-02 · ✗ 416 credits totalling exactly $3,900,000.00 against 424 disbursements of $3,949,083 to the same three accounts in the aid file |

Nine catalogued streams have no file (`path_glob` null): gps_integrity_reports, eod_dive_logs, calls_311, traffic_counts, grid_operator_logs, investigative_files, threat_intelligence, hospital_internal_records, spill_response_logs.

---

## D. Leakage and realism

* **Headers.** No column named for attack, hostile, fraud, bot, truth, label, scenario or thread. `phase` is the survey phase. `open_ml_anomaly_alerts` is always 0.
* **Values.** 0 hits for "D+12"-style notation, thread ids, EVT- or PUB- ids, UAS-SYN, ASN-SYN, JAM-01, DEV-01/02, KESTREL, GridWater, ClearPath, "scenario", "hackathon" in the streams of this audit. "Phantom" is a drone model. `05_other_sources/README.md` states the data is synthetic; `port_surveillance/README.md` names its generator script.
* **Values and id patterns unique to canon rows.** Zeek (B8), drone detections and sighting reports (B2), utility audit logs and tanker sessions (A2), aid flag SA-2027-TX-4471 (A5), false-call phrase (A4), "guess-" ids (B6), off-cycle satellite passes (B9).
* **Too regular.** SAR sorties (102 minutes, 18 survivors); 82 alarm-suppression removals at 20-second steps from 12:30:00Z on 10-12; benign suppression changes every third day at 14:00:00Z; depot readiness +2 a day; SIEM recovery ramp; exactly 220,000 failed logins of 512 bytes; exactly $3,900,000.00 diverted; survey aircraft launched 20 seconds apart; one maximum height per drone model; patrol aircraft on every second day; every Zeek state SF.
* **Impossible or implausible.** Helicopter rescues with the aircraft on the ground; 612 people delivered to a 500-place shelter that logs 4 arrivals; optical surveys and field inspections at night; 6 ft of water in a slab house rated minor; a pressure effect four hours before its cause; jump-host activity while it is powered off; invoices for fuel after the supplier stopped delivering.
* **Units.** No unit error found (drone heights in metres are within limits stated in feet; radar ranges in metres; RCS in m²; gauge in feet MLLW with residual 11.12 ft = 3.39 m).

---

## Ranked defects

| Rank | Id | Severity | Defect | Where | Suggested fix |
|---|---|---|---|---|---|
| 1 | D2-01 | blocker | Three one-line filters (name not ending `.example`; address outside the reserved ranges; service rdp / modbus / dnp3 / port 4000) return exactly the intrusion; hostile flows are the only unsampled ones | `network_logs/zeek/*/conn.log`, `ssl.log`, `dns.log` | Give benign traffic the same name and address space as the attacker's (mixed TLDs and ordinary public ranges, or put the attacker in `.example` and 198.18/15); add routine OT-protocol and RDP flows; keep or sample hostile and benign flows by one rule and emit flows for benign remote sessions |
| 2 | D2-02 | major | Hostile drone records identifiable by id and label: lowest track numbers, report ids 0001–0027, two dispositions, three RF signatures, "unknown emitter" | `drone_detections/detections_*.csv`, `sighting_reports.csv` | Number tracks and reports in time order after merging; give benign unresolved reports the same dispositions; reuse the signature strings on some benign emitters |
| 3 | D2-03 | major | Remaining single-value tells in utility and tanker logs (table in A2) | `network_logs/audit/historian_access.csv`, `file_integrity.csv`, `endpoint_protection.csv`, `scada_command_log.csv`, `alarm_suppression_audit.csv`, `ot_config_changes.csv`, `remote_access_sessions.csv`, `telemetry/vessel_cargo_control_remote_sessions.csv` | Add benign bulk reads, diff summaries, disable/enable pairs, multi-target sessions and named-operator commands on those breakers; drop the narrator texts; draw ids, seconds and durations from one generator; let the engineer account also make ordinary suppression changes |
| 4 | D2-04 | major | SAR helicopter sorties are not flown in ADS-B (1 of 341 rescues matches; aircraft on the ground during three sorties); 18 survivors and 102 minutes per sortie | `sar/sar_missions.csv`, `sar_asset_log.csv` against `adsb/adsb_2027-09.csv` | Regenerate the log from the ADS-B airborne intervals (or the tracks from the log); cap survivors per sortie near 6; vary sortie length |
| 5 | D2-05 | major | Jump host used while offline: 3 SCADA commands, 4 historian sessions, 31 SIEM alerts; plus 72 flows out of the OT network from a laboratory workstation, 2027-10-12T12:00Z–10-19T20:00Z | `scada_command_log.csv`, `historian_access.csv`, `siem_alerts_2027-10.csv`, `zeek/2027-10-1*/conn.log` | Make every benign generator honour the isolation window; move the workstation to an IT zone or silence it |
| 6 | D2-06 | major | Network sensor logs not self-consistent: DNS rows share no uid with connections, service and port paired at random for directory traffic, every state SF | `network_logs/zeek/**` | Write `dns.log` from the DNS connections; set service by port; add S0 / REJ / RSTO states |
| 7 | D2-07 | major | Fuel invoices (291,000 gal, 10-17…11-22) contradict deliveries (17,467 gal, 09-28…10-23); federal supply "under review" a month before the review; notice to proceed after three deliveries; failure dated both 24 and 25 Oct | `payments/contracts_invoices.csv`, `contracts_actions.csv`, `supply/fuel_deliveries.csv`, station post of 2027-10-25T20:00Z | One delivery ledger feeding both files with shared ticket numbers; decide whether over-billing is intended and put it in canon; align the dates |
| 8 | D2-08 | major | SAR deliveries missing from the shelter census (612 into a 500-place shelter that logs 4 arrivals); 33 deliveries to a shelter not yet open | `shelters/shelter_daily_census.csv` against `sar/sar_missions.csv` | Build census arrivals from bus trips plus SAR deliveries; respect capacity and opening times |
| 9 | D2-09 | major | Damage file logic: times uniform over 24 h; 1,266 flooded slab houses rated minor or less; landfall town less damaged than downtown; two-storey manufactured homes | `infrastructure/damage_assessment.csv`, `utility_site_survey.csv` | Daylight hours for field and optical work; derive level from depth, foundation and roof loss; raise Port Aransas exposure; constrain attributes by occupancy type |
| 10 | D2-10 | minor | 30 "after the storm" posts before landfall, from 2027-07-16 | `social_media/RubenCastaneda_.jsonl`, `GrantOkaforCC.jsonl`, `KeishaMonroeH6.jsonl` | Gate the template on D+1 |
| 11 | D2-11 | minor | GPS interference shows only in ADS-B; AIS, AVL and drone positions unaffected; `gps_integrity_reports` not delivered | `ais/`, `avl/`, `drone_video/` | Add position scatter and integrity loss inside the radius, or state in canon that only aviation receivers were affected |
| 12 | D2-12 | minor | Pump discharge pressure at its post-attack value four hours before the write | `telemetry/historian_WTP_202709.csv` | Hold about 85 psi until 02:04:01Z, then step |
| 13 | D2-13 | minor | Optical surveys before sunrise (flights 10:03–10:56Z, site surveys from 09:00Z) | `drone_video/logs/flight_log.csv`, `infrastructure/utility_site_survey.csv`, canon | Move the D+8 pass after 12:30Z or make it thermal |
| 14 | D2-14 | minor | Blast casualties in no health or dispatch stream | `public_health/ed_visits_*.csv`, `911/cad_incidents_2027-10.csv` | Add two arrivals (helicopter or EMS) after 06:44Z |
| 15 | D2-15 | minor | Satellite 10-15 scenes off-cycle yet "Routine"; "small hull / no AIS" against a 180 m radar contact with a (false) AIS identity | `satellite/CORVUS-SAR-20271015T042000Z-APPROACH.json`, `…T093000Z-ANCHORAGE.json` | Put them on the cycle or mark them as tasked; reword |
| 16 | D2-16 | minor | Portal realism: 9 accounts before opening; exactly 220,000 failures of 512 bytes spread evenly over 64 addresses; no failure against a real account; almost no benign logins; uniform browser mix; "guess-" ids; every benign base-portal row "login_success" | `network_logs/portal/*.csv` | Open at 00:00 local on 13 Nov; jitter counts and sizes; add benign logins and failures |
| 17 | D2-17 | minor | 29 evacuation buses arrive before the shelters open | `shelters/evacuation_bus_trips.csv` | Shift first pickups or open earlier |
| 18 | D2-18 | minor | No outage in the map near the air station for the 10-24 "commercial power interruption" (only 110 customers in Tuloso until 01:30Z); 0 customers out until 06:15Z on landfall night | `telemetry/outage_map.csv`, canon | Add a short Flour Bluff outage on 10-24; start the storm ramp with the first hurricane-force gusts |
| 19 | D2-19 | minor | Aid disbursements to the three accounts (424, $3,949,083) differ from bank credits (416, exactly $3,900,000.00) | `payments/aid_applications.csv`, `financial_transactions.csv` | Generate the credits from the disbursements |
| 20 | D2-20 | minor | Residual case-id and phrase tells: SA-2027-TX-4471 on ring only; "IN DANGER NOW" on false calls only; "14 session records" | `payments/aid_applications.csv`, `911/cad_incidents_2027-09.csv`, `network_logs/audit/settings_audits.csv` | Split the ring over two or three case numbers shared with outsiders; reuse the phrase in real calls; drop the count |
| 21 | D2-21 | minor | Sensor outage dates differ between base status (09-15…09-24) and sensor log (09-14…09-26); no sighting reports before D+1; "after sunset" at 08:04 local; four unresolved drone reports after D+11 | `maintenance/base_status_reports.csv`, `drone_detections/*` | Align dates; add pre-storm benign reports; choose text by hour |
| 22 | D2-22 | minor | Still open from audit 1: SUB-02 relay write absent from the configuration audit; random SIEM close notes. Canon's "74,120 in 60 hours (5.1×)" matches no window | `ot_config_changes.csv`, `siem_alerts_*.csv`, `canon_timeline.json` | As audit 1; correct the canon sentence |
| 23 | D2-23 | minor | Mechanical series (list in D) | various | Add jitter |
| 24 | D2-24 | minor | Four ordinary awards invoiced at 1.5–3.4× their value; WATERSAFE code unused for the citywide notice; a delivered README names a generator script; nine catalogued streams have no file | `payments/contracts_*.csv`, `911/`, `port_surveillance/README.md`, `stream_catalog.json` | Tidy individually |

Machine-readable list: `defects.json`.

## Scripts

`common.py`, `canon_dump.py`; A: `a_distinct.py`, `a_ras.py`, `a_vcc.py`, `a_911.py`, `a_aid.py`, `a_ins.py`, `a_outage_bot.py`, `a_posts.py`; B: `b_drone_tel.py`…`b_drone_tel4.py`, `b_det.py`…`b_det7.py`, `b_sar.py`, `b_sar_adsb.py`, `b_sar_adsb2.py`, `b_shelter.py`, `b_dmg.py`, `b_portal.py`…`b_portal3.py`, `b_siem.py`…`b_siem3.py`, `b_zeek.py`…`b_zeek4.py`, `b_sat.py`, `b_base.py`, `b_ww.py`, `b_contracts.py`, `b_utl.py`; C: `c_moments1.py`…`c_moments3.py`, `c2_a.py`, `c2_b.py`, `c2_c.py` (stops at moment 14 on a column name; `c2_d.py` is the corrected remainder). Outputs are in `out/`.
Several scripts read pickles in `/tmp` written by the first script of their family (`a_911.py`, `a_aid.py`, `b_drone_tel.py`, `b_portal.py`, `b_zeek.py`); `b_sar_adsb*.py` read `/tmp/sar_adsb.csv`, made with `grep -E "^(ae5d83|ae1118|a1b783|aa0d79|ac8a3c)," adsb/adsb_2027-09.csv`. Scripts dated 10 Nov come from the interrupted first attempt; I re-ran every one of them on the current files on 11 Nov and report only those outputs. A few figures (fuel totals by supplier, the Zeek service and address lists, the ED and outage look-ups for moments 14 and 15, the patrol-aircraft check for sortie 2) came from one-off commands whose logic is described in the text.
