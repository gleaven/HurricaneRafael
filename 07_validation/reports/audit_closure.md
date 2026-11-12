# Audit closure table

Written 2026-11-11 at the end of the final consistency sweep. One row per defect of the three independent audits:
the first stream audit (`07_validation/independent_audit/REPORT.md`, 18 ranked defects, ids A1-01 to A1-18 here),
the second stream audit (`07_validation/independent_audit_2/defects.json`, 24) and the narrative audit
(`07_validation/independent_audit_narrative/defects.json`, 54).

Every row was checked against the files on disk in this pass, not against the reports of the work that fixed it.
The counting scripts are in `07_validation/audit_closure_checks/` (run from the project root).

**Totals: 96 defects: 92 closed, 4 partly closed, 0 open.**

What "partly" means here: the main fault is fixed and verified, and a named remainder is still as the auditor found it
or was not measured again. Those remainders are listed in the row. Nothing in this table has been confirmed by a third
independent audit.

Fixed during this pass because the check showed the earlier fix was incomplete: D2-01 (sessions without flows,
remote-desktop commands outside sessions), D2-03 (four remaining tells), D2-05 (historian sessions in the isolation
window), D2-14 (hospital did not match the dispatch record), D02, D04, D07, D10, D38, D47 (narrative residues).
Closed by a canon decision instead of a data change: A1-10, D2-11, part of D2-24 (see `00_scenario/canon_decisions.md`, entry 23).

## First stream audit

| Id | Severity | Status | What was done | Where | How verified now |
|---|---|---|---|---|---|
| A1-01 | blocker | closed | Author notes removed from the three statements at source; press releases regenerated. | `02_public_record/public_record.json`, `press_releases/` | `p10.py`: 0 author-note hits in 180 statements and 0 in the public record |
| A1-02 | major | closed | Tells removed in the first round (session context column, round byte counts, contiguous ids); the rest closed with D2-03. | `network_logs/audit/` | see D2-03 |
| A1-03 | major | closed | Export and rule-change rows reduced to what such a record holds. | `settings_audits.csv`, `siem/rule_changes.csv` | `p2.py`: export rows carry no counts; rule change reads "removed (AUDIT-EXC-2027-10)" |
| A1-04 | major | closed | Incident types and narratives depend on the day. | `911/cad_incidents_*.csv` | `p8.py`: first curfew violation 2027-09-16 00:42 local, first water rescue and roof collapse on landfall day, shelter requests from 09-11; 73,647 incidents |
| A1-05 | major | closed | Fraud-marking statuses diluted with ordinary holds and reviews. | `payments/aid_applications.csv`, `insurance_claims.csv` | `p8.py`: 128 different hold-flag numbers; the ring's flag is on 38 rows at 38 different times; 69 claims under special-investigations review |
| A1-06 | minor | closed | Curfew template gated on the curfew. | `social_media/` | `p6.py`: 0 curfew posts before 2027-09-15T14:00Z in 117,021 posts |
| A1-07 | minor | closed | Outage bot generated from the outage map. | `social_media/TXOutageCount.jsonl` | `p11.py`: 861 posts with a customer count, 0 differ from `outage_map.csv` by more than 3% |
| A1-08 | minor | closed | False rescue calls on Sept. 21 start after 19:00Z. | `911/cad_incidents_2027-09.csv` | stream probe for EVT-1303 (`check_streams.py --only=cad_911`, passes) requires the calls between 19:00Z and 23:00Z; not re-measured by an independent filter because the 23 calls are no longer isolable with one (32 unfounded prepaid calls in the window) |
| A1-09 | minor | closed | Weekday effect and noise in call series; restoration in feeder-sized steps. | `911/reports/`, `telemetry/outage_map.csv` | `p11.py`: daily 911 calls 16 to 29 Aug range 275 to 344 with no smooth trend |
| A1-10 | minor | closed | Canon wording relaxed to what the data shows (decision 23g): telemetry drops out intermittently. | `00_scenario/canon_timeline.json`, `canon_decisions.md` | historian files for Sept. 14 to 17: 2% to 10% of samples not good quality; canon sentence now says so |
| A1-11 | minor | closed | The relay write is in the configuration audit. | `network_logs/audit/ot_config_changes.csv` | `p2.py`: row 2027-09-11T22:11:48Z, GW-SYS-RTU-02, relays R-02A/B/C |
| A1-12 | minor | partly | Internal "ASN-SYN" form removed. Two notations remain, one per system: the utility's gateway and alert queue write `AS-n` (canon quotes it), portals and logon logs write `ASN n`. | `network_logs/`, `telemetry/`, `payments/` | `p10.py`: notations found: `ASN n`, `AS-n`, plain number column; 0 files with ASN-SYN |
| A1-13 | minor | partly | Decided the other way after D2-01: every outside host, ordinary or hostile, shares one invented name and address space. Addresses are in routable ranges and names end in real top-level domains; the catalogue and data guide say they are invented. | `network_logs/zeek/`, `stream_catalog.json`, `DATA_GUIDE.md` | `p1.py`: 318 outside responders; name endings com/net/org/example mixed |
| A1-14 | minor | closed | The terminal operator is not named on landfall day. | `press_releases/statements_2027-09.jsonl` | `p10.py`: PUB-024 does not contain the name |
| A1-15 | minor | closed | Hospital arrivals and illness curve match canon. | `public_health/ed_visits_*` | 118 arrivals at FAC-SRMC-001 by 18:00 local on landfall day; `check_streams.py` health group 34/34 |
| A1-16 | minor | closed | Aid registration opens at 06:00Z; canon no longer gives a window for spill claims. | `payments/`, canon | `p8.py`: 0 applications before 2027-11-13T06:00Z; 4,204 spill claims, canon EVT-0508 "about 4,200" |
| A1-17 | minor | partly | Vehicles: scatter, parking off the road, routes on streets (map check: 0 unmatched gaps). Aircraft touchdown scatter, the tug's fixed position and speed ramps were not re-measured in this pass. | `avl/`, `adsb/`, `ais/` | `check_geo.py` vehicle rule (parent gate); KALVORA STAR moored scatter about 1.2 m (`p9.py`) |
| A1-18 | minor | partly | Fixed and verified: `d0_date` removed, shift-log line removed, character count equals headline length (287), canon cites VND-0001/VND-0002. Still as found: VSL-0031 `deep_draft` false, first aircraft fix 12:25Z on 15 Aug, 4 ferry-wait posts during the blast closure. Not re-checked: tanker pilot station, repeated monthly inspections, the terminal's social account, sonde baselines. | various | `p10.py` |

## Second stream audit

| Id | Severity | Status | What was done | Where | How verified now |
|---|---|---|---|---|---|
| D2-01 | blocker | closed | Ordinary and hostile outside hosts share name and address space; routine RDP and field-protocol flows added; every session on the remote-access gateway now has its flow (this pass: flows are written from the session log), and every remote-desktop command lies inside a gateway session. | `scripts/streams/gen_itsec.py`; `network_logs/zeek/`, `audit/` | `p1.py`: rdp 1,698, dnp3 4,455, modbus 1,061 flows; session/flow join 843 of 843 (829 ordinary, 14 hostile); 50 of 50 remote-desktop commands inside a session that lists the workstation |
| D2-02 | major | closed | Tracks and reports numbered in time order; dispositions and signatures shared with ordinary records. | `drone_detections/` | `p1.py`: 0 sequence inversions; 68 reports, ids in time order, 7 before 15 Sept.; each signature string on 100+ rows |
| D2-03 | major | closed | Bulk reads, diff summaries, protection toggles and breaker commands given ordinary company (earlier round). This pass: ordinary sessions touch several hosts, the server leaves the operator blank on some ordinary remote-desktop commands, the engineer account and others make ordinary suppression changes (some without a ticket), the local-time gloss is gone. | `scripts/streams/gen_itsec.py`; `network_logs/audit/*.csv` | `p2.py`: bulk read 108 of 1,326; diff summary 38 of 161; 34 protection-disabled rows; multi-host sessions 107 of 843; blank operator 11 of 50; ticket-less suppression adds by two accounts; 0 rows with a local-time gloss |
| D2-04 | major | closed | Rescue log and aircraft tracks come from one sortie plan. | `sar/`, `adsb/` | `p4.py`: 341 of 341 helicopter rescues have a fix of the airframe within 600 m at on-scene time; 29 of 29 launches match; sortie lengths 19 to 149 min. Note: 13 sorties carry 15 to 23 people (several pickups and landings per sortie) |
| D2-05 | major | closed | Ordinary generators honour the isolation window. This pass: historian sessions in the window come from engineering workstations inside the control network. | `scripts/streams/gen_itsec.py`; `audit/historian_access.csv` | `p2.py`: 0 commands, 0 historian sessions, 0 alerts and 0 flows involving the gateway host or the laboratory workstation between 10-12T12:00Z and 10-19T20:00Z |
| D2-06 | major | closed | DNS log written from the DNS flows; service follows port; connection states vary. | `network_logs/zeek/` | `p1.py`: 107,777 of 107,777 dns uids are in conn.log; 0 service/port mismatches; 7 connection states |
| D2-07 | major | closed | One delivery ledger shared by the fuel file and the invoices; dates aligned. | `supply/fuel_deliveries.csv`, `payments/contracts_*.csv` | `p5.py`: supplier VND-0002: 24 deliveries, 291,229 gal, tickets QF-2100 to QF-2109, 17 Oct to 22 Nov; 10 invoices for 291,229 gal, all naming a ledger ticket; failure dated Oct. 24 everywhere |
| D2-08 | major | closed | Census arrivals built from bus trips and rescue deliveries; capacity and opening times respected. | `shelters/`, `sar/` | `p4.py`, `p5.py`: 0 rows over capacity; census arrivals equal intake sums on 173 of 173 rows; 0 intake rows before opening; 578 of 578 rescue deliveries to shelters appear as intake references |
| D2-09 | major | closed | Daylight hours for field work; level derived from depth and foundation; barrier island worst hit; attributes constrained by occupancy. | `infrastructure/damage_assessment.csv` | `p4.py`: field verification 07 to 18 h, inspections 08 to 17 h; 0 of 485 non-elevated structures with 5 ft or more rated minor or lower; 78373 80% major or destroyed against 63% in 78402; manufactured homes all single-storey, none over 2,000 sq ft; 0 shared addresses |
| D2-10 | minor | closed | Template gated on the storm. | `social_media/` | `p6.py`: 0 pre-landfall posts with after-the-storm wording in 117,021 |
| D2-11 | minor | closed | Closed by decision, no data change (decision 23f): the interference is observable in aircraft data only. A ship moored about 2 km away showing no effect is a simplification. | `00_scenario/canon_timeline.json`, `canon_decisions.md` | `p9.py`: aircraft integrity value falls from 7.95 to 5.0-5.8 on Oct. 22 to 27; moored-ship scatter unchanged at 1.0 to 1.5 m |
| D2-12 | minor | closed | Pressure holds until the setpoint write. | `telemetry/historian_WTP_202709.csv` | `p7.py`: 83.7 psi at 01:55Z, setpoint 85 to 68 at 02:04:01Z, 67.3 psi at 02:05:37Z |
| D2-13 | minor | closed | The pre-dawn pass is thermal. | `drone_video/logs/flight_log.csv`, `infrastructure/utility_site_survey.csv` | `p4.py`: six flights 10:03Z to 11:45Z with a long-wave infrared payload; no visible-band survey row before 12:20Z |
| D2-14 | minor | closed | Two arrivals after the blast. This pass: moved to the hospital the dispatch record names (decision 23h). | `scripts/streams/gen_health.py`; `public_health/ed_visits_FAC-BCMC-002.csv` | `p7.py`: arrivals 07:44:40Z and 07:52:15Z by ambulance at FAC-BCMC-002; dispatch incident 41-2027-000332 transports two patients there |
| D2-15 | minor | closed | The two passes are marked as tasked; other passes are off the fixed cycle too; text reworded. | `satellite/` | `p7.py`, `p11.py`: 8 pass times besides the two cycle times; scene text "Tasked night acquisition ... the only AIS transmission at that position reports a 24 m fishing vessel" |
| D2-16 | minor | closed | Registration opens at local midnight; counts and sizes vary; ordinary logins and failures added. | `network_logs/portal/` | `p8.py`: first account 2027-11-13T06:00:00Z; 223,768 failed logins of 783 sizes; 4,289 failures against existing accounts; base system has failures too |
| D2-17 | minor | closed | No bus arrives before a shelter opens. | `shelters/evacuation_bus_trips.csv` | `p4.py`: 0 of 196 |
| D2-18 | minor | closed | Short outage near the air station on Oct. 24; storm ramp starts in the evening before landfall. | `telemetry/outage_map.csv` | `p5.py`: AREA-NBH-FLOURBLUFF, feeder GW-SUB05-CB-18, cause equipment, on Oct. 24; customers out from 22:30Z on Sept. 13 |
| D2-19 | minor | closed | Bank credits generated from the disbursements. | `payments/aid_applications.csv`, `financial_transactions.csv` | `p8.py`: 416 disbursements and 416 credits, $3,900,000.01 in both |
| D2-20 | minor | closed | Flag shared with outsiders; phrase used in real calls; count dropped. | `payments/`, `911/`, `audit/settings_audits.csv` | `p8.py`: phrase in 760 narratives, 65 unfounded; export row has no count |
| D2-21 | minor | closed | Dates aligned; pre-storm reports added; text chosen by hour. | `maintenance/base_status_reports.csv`, `drone_detections/` | `p7.py`: perimeter sensors offline in base status Sept. 14 to 25, in the sensor log until Sept. 26 16:00-19:00Z; 7 reports before Sept. 15; no after-sunset wording in daytime |
| D2-22 | minor | closed | Relay write present; close notes follow the rule; canon sentence corrected (decision 23c). | `audit/ot_config_changes.csv`, `siem/`, canon | `p2.py`: 0 communications-loss alerts closed with a password note; canon says 73,785 over six UTC days |
| D2-23 | minor | closed | Jitter added. | several | `p2.py`, `p4.py`, `p8.py`, `p11.py`: removals 82 with irregular gaps; sortie lengths vary; depot readiness steps 1 to 7; survey launches irregular; 7 to 19 maximum heights per drone model; 155 frame gaps in October telemetry |
| D2-24 | minor | closed | Ceilings raised by contract modifications; the water-question call type is created on the evening of Sept. 26 by canon (EVT-1305); stream READMEs ship without production notes; the nine streams without files are marked not delivered. | `payments/contracts_actions.csv`, `scripts/build_delivery.py`, `stream_catalog.json` | `p8.py`: each of the four awards has not-to-exceed modifications above the invoiced total; `check_catalog.py` PASS |

## Narrative audit

Method: `n1.py` takes the fragments each defect quotes and looks for them in the stories, facts and events the defect
names. Fragments that are still present were read one by one; they are the canon wording the auditor quoted for
contrast, or neutral words. `scripts/check_canon_decisions.py --strict` (rules in `07_validation/canon_rules.json`)
passes with 0 violations over 681 stories, 177 facts and the public-voice stream files.

| Id | Severity | Status | What was done | Where | How verified now |
|---|---|---|---|---|---|
| D01 | blocker | closed | canon decision 2026-11-11 no. 1 | NWS-P057-03 | `n1.py`: 6 of 6 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D02 | blocker | closed | canon decision 2026-11-11 no. 1; this pass: one address for the recovery centre (Martin Luther King Drive) | NWS-P057-04 | `n1.py`: 6 of 6 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D03 | blocker | closed | canon decision 2026-11-11 no. 1 | NWS-P025-04 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D04 | blocker | closed | canon decision 2026-11-11 no. 2; this pass: "indictment" replaced by "criminal complaint" (PUB-210) and the unsupported count of 128 claims removed; "FBI Houston Division" and the 94 applications are canon | NWS-P090-05 / NWS-P090-06 / NWS-P090-07 | `n1.py`: 4 of 6 quoted fragments gone; 2 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D05 | blocker | closed | canon decision 2026-11-11 no. 3 | NWS-P001-09 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D06 | blocker | closed | canon decision 2026-11-11 no. 10 | NWS-P119-03 | `n1.py`: 5 of 5 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D07 | blocker | closed | canon decision 2026-11-11 no. 4; this pass: the "most significant ... since 2008" clause removed | NWS-P012-06 | `n1.py`: 4 of 4 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D08 | blocker | closed | canon decision 2026-11-11 no. 4; the remaining phrase now reads "on the 28th day of their separate boil-water notice" | NWS-P040-04 | `n1.py`: 3 of 4 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D09 | blocker | closed | canon decision 2026-11-11 no. 5 | NWS-P060-04 | `n1.py`: 6 of 6 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D10 | blocker | closed | canon decision 2026-11-11 no. 6; this pass: NWS-P005-06 no longer says helicopters could not fly or that rescues ended Thursday | NWS-P001-08 / NWS-P005-06 / NWS-P007-05 | `n1.py`: 10 of 10 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D11 | blocker | closed | canon decision 2026-11-11 no. 7 | NWS-P004-08 | `n1.py`: 3 of 3 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D12 | blocker | closed | canon decision 2026-11-11 no. 8; "23 calls" is canon | NWS-P010-06, NWS-P029-04, NWS-P032-04, NWS-P038-04, NWS-P045-08; PUB-174; EVT-1303/1304 vs | `n1.py`: 6 of 8 quoted fragments gone; 2 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D13 | blocker | closed | canon decision 2026-11-11 no. 5; remaining words are neutral ("released", "Thursday afternoon"); the counts are gone | NWS-P018-02, NWS-P021-04, NWS-P021-06, NWS-P023-04 | `n1.py`: 6 of 8 quoted fragments gone; 2 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D14 | blocker | closed | canon decision 2026-11-11 no. 9 | NWS-P000-10 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D15 | blocker | closed | canon decision 2026-11-11 no. 2 | NWS-M003-06 / NWS-M003-07 | `n1.py`: 4 of 4 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D16 | major | closed | canon decision 2026-11-11 no. 4 | PUB-134 | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D17 | major | closed | canon decision 2026-11-11 no. 16 | NWS-P002-08 | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D18 | major | closed | canon decision 2026-11-11 no. 12; headline keeps "recovery stalls"; the body now quotes the utility statement and the 32,000 customers | NWS-P014-04 | `n1.py`: 2 of 3 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D19 | major | closed | canon decision 2026-11-11 no. 11 | NWS-P015-04 | `n1.py`: 3 of 3 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D20 | major | closed | canon decision 2026-11-11 no. 10 | NWS-P015-05 | `n1.py`: 3 of 3 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D21 | major | closed | canon decision 2026-11-11 no. 10 | NWS-P030-08 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D22 | major | closed | canon decision 2026-11-11 no. 11 | NWS-P032-05 | `n1.py`: 5 of 5 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D23 | major | closed | canon decision 2026-11-11 no. 12 | NWS-P021-05 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D24 | major | closed | canon decision 2026-11-11 no. 12; headline keeps "Exclusive" and now says the changes predate the storm | NWS-P045-10 / GW-PUB-104 | `n1.py`: 3 of 4 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D25 | major | closed | canon decision 2026-11-11 no. 13 | NWS-P045-09 | `n1.py`: 4 of 4 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D26 | major | closed | canon decision 2026-11-11 no. 4; the Oct. 7 report is still cited, without a total | NWS-P042-04 / NWS-P042-05 | `n1.py`: 3 of 4 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D27 | major | closed | canon decision 2026-11-11 no. 16 | PUB-210; NWS-P003-08 | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D28 | major | closed | canon decision 2026-11-11 no. 17; no story says a station stayed on the air inside its window | NWS-P000-01; also NWS-P000-03, NWS-P000-10, NWS-P001-01 (OUT-02); NWS-P000-06 (OUT-04); NW | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D29 | major | closed | canon decision 2026-11-11 no. 6; "55 knots" kept; the start time is 1:22 a.m. Tuesday | PUB-170 | `n1.py`: 1 of 2 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D30 | major | closed | narrative fix scripts p01 to p03 | NWS-P012-05 / NWS-P012-07 | `n1.py`: 4 of 4 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D31 | major | closed | canon decision 2026-11-11 no. 9; superlative for 1,100 removed; the 2,109 figure is canon | NWS-P003-07 | `n1.py`: 2 of 3 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D32 | major | closed | canon decision 2026-11-11 no. 7; 183 square kilometres and the public imagery are canon | NWS-P045-07 / PUB-113 / EVT-1108 | `n1.py`: 5 of 7 quoted fragments gone; 2 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D33 | major | closed | narrative fix scripts p01 to p03 | NWS-P032-04 / NWS-P038-04 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D34 | major | closed | narrative fix scripts p01 to p03 | NWS-P021-04 | `n1.py`: 3 of 3 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D35 | major | closed | canon decision 2026-11-11 no. 14 | NWS-P002-10 / NWS-P002-11 / PUB-190 / PUB-195 | `n1.py`: 8 of 8 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D36 | major | closed | canon decision 2026-11-11 no. 15 | EVT-1403 / alerts.shelter-zones-c-e | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D37 | major | closed | canon decision 2026-11-11 no. 19; the old number appears only in a canon note that names it as retired | t22 news hook; EVT-22xx | `n1.py`: 2 of 3 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D38 | major | closed | canon decision 2026-11-11 no. 19; this pass: the same sentence in the MSEL corrected | T16 analysis text | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D39 | major | closed | canon decision 2026-11-11 no. 16 | NWS-M002-08 | `n1.py`: 4 of 4 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D40 | major | closed | canon decision 2026-11-11 no. 6; "Dispatch Chief" of the communications center is canon | CHR-109 Elena Vasquez-Okafor | `n1.py`: 3 of 4 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D41 | major | closed | canon decision 2026-11-11 no. 15 | PUB-200 | `n1.py`: 3 of 3 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D42 | minor | closed | canon decision 2026-11-11 no. 4; "two minutes" is canon | GW-PUB-001, GW-PUB-007, PUB-143, PUB-204, PUB-132 | `n1.py`: 4 of 5 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D43 | minor | closed | canon decision 2026-11-11 no. 13 | EVT-2106, EVT-1407, PUB-144, NWS-P013-03, NWS-P021-80 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D44 | minor | closed | canon decision 2026-11-11 no. 18; enforced on every run by `apply_narrative_fixes.py` (0 story times moved) | NWS-P001-09, NWS-P003-07, NWS-P004-08, NWS-P007-05, NWS-P016-40, NWS-P028-05, NWS-P045-60, | `apply_narrative_fixes.py`: 0 problems; `check_canon_decisions.py --strict` PASS |
| D45 | minor | closed | canon decision 2026-11-11 no. 9 | PUB-026; NWS-P001-10 (07:00), NWS-P001-02 (08:30) | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D46 | minor | closed | canon decision 2026-11-11 no. 4 | NWS-P040-01 / NWS-P041-02 | `n1.py`: 2 of 2 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D47 | minor | closed | canon decision 2026-11-11 no. 16; this pass: the replacement name was itself real; now Nueces Bay Blood Services everywhere (decision 23a) | PUB-161 / NWS-P000-12 | `n1.py`: 2 of 3 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D48 | minor | closed | canon decision 2026-11-11 no. 16; the remaining name is the canon one | organisation name variants | `n1.py`: 10 of 11 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D49 | minor | closed | canon decision 2026-11-11 no. 9; dates kept; "30-day" removed | PUB-164, PUB-172, NWS-P045-60, NWS-P029-04 | `n1.py`: 4 of 5 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D50 | minor | closed | canon decision 2026-11-11 no. 19; "to D+18" is the corrected window | EVT-1103, EVT-1602/1605, EVT-1304, EVT-1509, EVT-1907, EVT-1608, GW-EVT-011 | `n1.py`: 4 of 5 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
| D51 | minor | closed | narrative fix scripts p01 to p03 | PUB-205 | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D52 | minor | closed | canon decision 2026-11-11 no. 19 | NWS-P057-03, NWS-P057-04, NWS-P060-04, NWS-P090-06, NWS-P007-05 | `n1.py`: 4 of 4 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D53 | minor | closed | canon decision 2026-11-11 no. 11; kept as canon and never public; rule B21 added | EVT-1901..1905 support vessel | `n1.py`: 1 of 1 quoted fragments gone; `check_canon_decisions.py --strict` PASS |
| D54 | minor | closed | canon decision 2026-11-11 no. 13; both stories now say "roughly 500,000" | NWS-P013-03, NWS-P000-13, NWS-P015-03, NWS-P035-04, NWS-P028-04, NWS-P029-05 | `n1.py`: 8 of 9 quoted fragments gone; 1 left and reviewed; `check_canon_decisions.py --strict` PASS |
