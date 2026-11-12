import json,re
C='closed'; P='partly'; O='open'
A1=[
("A1-01","blocker",C,"Author notes removed from the three statements at source; press releases regenerated.","`02_public_record/public_record.json`, `press_releases/`","`p10.py`: 0 author-note hits in 180 statements and 0 in the public record"),
("A1-02","major",C,"Tells removed in the first round (session context column, round byte counts, contiguous ids); the rest closed with D2-03.","`network_logs/audit/`","see D2-03"),
("A1-03","major",C,"Export and rule-change rows reduced to what such a record holds.","`settings_audits.csv`, `siem/rule_changes.csv`","`p2.py`: export rows carry no counts; rule change reads \"removed (AUDIT-EXC-2027-10)\""),
("A1-04","major",C,"Incident types and narratives depend on the day.","`911/cad_incidents_*.csv`","`p8.py`: first curfew violation 2027-09-16 00:42 local, first water rescue and roof collapse on landfall day, shelter requests from 09-11; 73,647 incidents"),
("A1-05","major",C,"Fraud-marking statuses diluted with ordinary holds and reviews.","`payments/aid_applications.csv`, `insurance_claims.csv`","`p8.py`: 128 different hold-flag numbers; the ring's flag is on 38 rows at 38 different times; 69 claims under special-investigations review"),
("A1-06","minor",C,"Curfew template gated on the curfew.","`social_media/`","`p6.py`: 0 curfew posts before 2027-09-15T14:00Z in 117,021 posts"),
("A1-07","minor",C,"Outage bot generated from the outage map.","`social_media/TXOutageCount.jsonl`","`p11.py`: 861 posts with a customer count, 0 differ from `outage_map.csv` by more than 3%"),
("A1-08","minor",C,"False rescue calls on Sept. 21 start after 19:00Z.","`911/cad_incidents_2027-09.csv`","stream probe for EVT-1303 (`check_streams.py --only=cad_911`, passes) requires the calls between 19:00Z and 23:00Z; not re-measured by an independent filter because the 23 calls are no longer isolable with one (32 unfounded prepaid calls in the window)"),
("A1-09","minor",C,"Weekday effect and noise in call series; restoration in feeder-sized steps.","`911/reports/`, `telemetry/outage_map.csv`","`p11.py`: daily 911 calls 16 to 29 Aug range 275 to 344 with no smooth trend"),
("A1-10","minor",C,"Canon wording relaxed to what the data shows (decision 23g): telemetry drops out intermittently.","`00_scenario/canon_timeline.json`, `canon_decisions.md`","historian files for Sept. 14 to 17: 2% to 10% of samples not good quality; canon sentence now says so"),
("A1-11","minor",C,"The relay write is in the configuration audit.","`network_logs/audit/ot_config_changes.csv`","`p2.py`: row 2027-09-11T22:11:48Z, GW-SYS-RTU-02, relays R-02A/B/C"),
("A1-12","minor",P,"Internal \"ASN-SYN\" form removed. Two notations remain, one per system: the utility's gateway and alert queue write `AS-n` (canon quotes it), portals and logon logs write `ASN n`.","`network_logs/`, `telemetry/`, `payments/`","`p10.py`: notations found: `ASN n`, `AS-n`, plain number column; 0 files with ASN-SYN"),
("A1-13","minor",P,"Decided the other way after D2-01: every outside host, ordinary or hostile, shares one invented name and address space. Addresses are in routable ranges and names end in real top-level domains; the catalogue and data guide say they are invented.","`network_logs/zeek/`, `stream_catalog.json`, `DATA_GUIDE.md`","`p1.py`: 318 outside responders; name endings com/net/org/example mixed"),
("A1-14","minor",C,"The terminal operator is not named on landfall day.","`press_releases/statements_2027-09.jsonl`","`p10.py`: PUB-024 does not contain the name"),
("A1-15","minor",C,"Hospital arrivals and illness curve match canon.","`public_health/ed_visits_*`","118 arrivals at FAC-SRMC-001 by 18:00 local on landfall day; `check_streams.py` health group 34/34"),
("A1-16","minor",C,"Aid registration opens at 06:00Z; canon no longer gives a window for spill claims.","`payments/`, canon","`p8.py`: 0 applications before 2027-11-13T06:00Z; 4,204 spill claims, canon EVT-0508 \"about 4,200\""),
("A1-17","minor",P,"Vehicles: scatter, parking off the road, routes on streets (map check: 0 unmatched gaps). Aircraft touchdown scatter, the tug's fixed position and speed ramps were not re-measured in this pass.","`avl/`, `adsb/`, `ais/`","`check_geo.py` vehicle rule (parent gate); KALVORA STAR moored scatter about 1.2 m (`p9.py`)"),
("A1-18","minor",P,"Fixed and verified: `d0_date` removed, shift-log line removed, character count equals headline length (287), canon cites VND-0001/VND-0002. Still as found: VSL-0031 `deep_draft` false, first aircraft fix 12:25Z on 15 Aug, 4 ferry-wait posts during the blast closure. Not re-checked: tanker pilot station, repeated monthly inspections, the terminal's social account, sonde baselines.","various","`p10.py`"),
]
A2=[
("D2-01","blocker",C,"Ordinary and hostile outside hosts share name and address space; routine RDP and field-protocol flows added; every session on the remote-access gateway now has its flow (this pass: flows are written from the session log), and every remote-desktop command lies inside a gateway session.","`scripts/streams/gen_itsec.py`; `network_logs/zeek/`, `audit/`","`p1.py`: rdp 1,698, dnp3 4,455, modbus 1,061 flows; session/flow join 843 of 843 (829 ordinary, 14 hostile); 50 of 50 remote-desktop commands inside a session that lists the workstation"),
("D2-02","major",C,"Tracks and reports numbered in time order; dispositions and signatures shared with ordinary records.","`drone_detections/`","`p1.py`: 0 sequence inversions; 68 reports, ids in time order, 7 before 15 Sept.; each signature string on 100+ rows"),
("D2-03","major",C,"Bulk reads, diff summaries, protection toggles and breaker commands given ordinary company (earlier round). This pass: ordinary sessions touch several hosts, the server leaves the operator blank on some ordinary remote-desktop commands, the engineer account and others make ordinary suppression changes (some without a ticket), the local-time gloss is gone.","`scripts/streams/gen_itsec.py`; `network_logs/audit/*.csv`","`p2.py`: bulk read 108 of 1,326; diff summary 38 of 161; 34 protection-disabled rows; multi-host sessions 107 of 843; blank operator 11 of 50; ticket-less suppression adds by two accounts; 0 rows with a local-time gloss"),
("D2-04","major",C,"Rescue log and aircraft tracks come from one sortie plan.","`sar/`, `adsb/`","`p4.py`: 341 of 341 helicopter rescues have a fix of the airframe within 600 m at on-scene time; 29 of 29 launches match; sortie lengths 19 to 149 min. Note: 13 sorties carry 15 to 23 people (several pickups and landings per sortie)"),
("D2-05","major",C,"Ordinary generators honour the isolation window. This pass: historian sessions in the window come from engineering workstations inside the control network.","`scripts/streams/gen_itsec.py`; `audit/historian_access.csv`","`p2.py`: 0 commands, 0 historian sessions, 0 alerts and 0 flows involving the gateway host or the laboratory workstation between 10-12T12:00Z and 10-19T20:00Z"),
("D2-06","major",C,"DNS log written from the DNS flows; service follows port; connection states vary.","`network_logs/zeek/`","`p1.py`: 107,777 of 107,777 dns uids are in conn.log; 0 service/port mismatches; 7 connection states"),
("D2-07","major",C,"One delivery ledger shared by the fuel file and the invoices; dates aligned.","`supply/fuel_deliveries.csv`, `payments/contracts_*.csv`","`p5.py`: supplier VND-0002: 24 deliveries, 291,229 gal, tickets QF-2100 to QF-2109, 17 Oct to 22 Nov; 10 invoices for 291,229 gal, all naming a ledger ticket; failure dated Oct. 24 everywhere"),
("D2-08","major",C,"Census arrivals built from bus trips and rescue deliveries; capacity and opening times respected.","`shelters/`, `sar/`","`p4.py`, `p5.py`: 0 rows over capacity; census arrivals equal intake sums on 173 of 173 rows; 0 intake rows before opening; 578 of 578 rescue deliveries to shelters appear as intake references"),
("D2-09","major",C,"Daylight hours for field work; level derived from depth and foundation; barrier island worst hit; attributes constrained by occupancy.","`infrastructure/damage_assessment.csv`","`p4.py`: field verification 07 to 18 h, inspections 08 to 17 h; 0 of 485 non-elevated structures with 5 ft or more rated minor or lower; 78373 80% major or destroyed against 63% in 78402; manufactured homes all single-storey, none over 2,000 sq ft; 0 shared addresses"),
("D2-10","minor",C,"Template gated on the storm.","`social_media/`","`p6.py`: 0 pre-landfall posts with after-the-storm wording in 117,021"),
("D2-11","minor",C,"Closed by decision, no data change (decision 23f): the interference is observable in aircraft data only. A ship moored about 2 km away showing no effect is a simplification.","`00_scenario/canon_timeline.json`, `canon_decisions.md`","`p9.py`: aircraft integrity value falls from 7.95 to 5.0-5.8 on Oct. 22 to 27; moored-ship scatter unchanged at 1.0 to 1.5 m"),
("D2-12","minor",C,"Pressure holds until the setpoint write.","`telemetry/historian_WTP_202709.csv`","`p7.py`: 83.7 psi at 01:55Z, setpoint 85 to 68 at 02:04:01Z, 67.3 psi at 02:05:37Z"),
("D2-13","minor",C,"The pre-dawn pass is thermal.","`drone_video/logs/flight_log.csv`, `infrastructure/utility_site_survey.csv`","`p4.py`: six flights 10:03Z to 11:45Z with a long-wave infrared payload; no visible-band survey row before 12:20Z"),
("D2-14","minor",C,"Two arrivals after the blast. This pass: moved to the hospital the dispatch record names (decision 23h).","`scripts/streams/gen_health.py`; `public_health/ed_visits_FAC-BCMC-002.csv`","`p7.py`: arrivals 07:44:40Z and 07:52:15Z by ambulance at FAC-BCMC-002; dispatch incident 41-2027-000332 transports two patients there"),
("D2-15","minor",C,"The two passes are marked as tasked; other passes are off the fixed cycle too; text reworded.","`satellite/`","`p7.py`, `p11.py`: 8 pass times besides the two cycle times; scene text \"Tasked night acquisition ... the only AIS transmission at that position reports a 24 m fishing vessel\""),
("D2-16","minor",C,"Registration opens at local midnight; counts and sizes vary; ordinary logins and failures added.","`network_logs/portal/`","`p8.py`: first account 2027-11-13T06:00:00Z; 223,768 failed logins of 783 sizes; 4,289 failures against existing accounts; base system has failures too"),
("D2-17","minor",C,"No bus arrives before a shelter opens.","`shelters/evacuation_bus_trips.csv`","`p4.py`: 0 of 196"),
("D2-18","minor",C,"Short outage near the air station on Oct. 24; storm ramp starts in the evening before landfall.","`telemetry/outage_map.csv`","`p5.py`: AREA-NBH-FLOURBLUFF, feeder GW-SUB05-CB-18, cause equipment, on Oct. 24; customers out from 22:30Z on Sept. 13"),
("D2-19","minor",C,"Bank credits generated from the disbursements.","`payments/aid_applications.csv`, `financial_transactions.csv`","`p8.py`: 416 disbursements and 416 credits, $3,900,000.01 in both"),
("D2-20","minor",C,"Flag shared with outsiders; phrase used in real calls; count dropped.","`payments/`, `911/`, `audit/settings_audits.csv`","`p8.py`: phrase in 760 narratives, 65 unfounded; export row has no count"),
("D2-21","minor",C,"Dates aligned; pre-storm reports added; text chosen by hour.","`maintenance/base_status_reports.csv`, `drone_detections/`","`p7.py`: perimeter sensors offline in base status Sept. 14 to 25, in the sensor log until Sept. 26 16:00-19:00Z; 7 reports before Sept. 15; no after-sunset wording in daytime"),
("D2-22","minor",C,"Relay write present; close notes follow the rule; canon sentence corrected (decision 23c).","`audit/ot_config_changes.csv`, `siem/`, canon","`p2.py`: 0 communications-loss alerts closed with a password note; canon says 73,785 over six UTC days"),
("D2-23","minor",C,"Jitter added.","several","`p2.py`, `p4.py`, `p8.py`, `p11.py`: removals 82 with irregular gaps; sortie lengths vary; depot readiness steps 1 to 7; survey launches irregular; 7 to 19 maximum heights per drone model; 155 frame gaps in October telemetry"),
("D2-24","minor",C,"Ceilings raised by contract modifications; the water-question call type is created on the evening of Sept. 26 by canon (EVT-1305); stream READMEs ship without production notes; the nine streams without files are marked not delivered.","`payments/contracts_actions.csv`, `scripts/build_delivery.py`, `stream_catalog.json`","`p8.py`: each of the four awards has not-to-exceed modifications above the invoiced total; `check_catalog.py` PASS"),
]
N={o['id']:o for o in json.load(open('07_validation/reports/narrative_fragments.json'))}
D=json.load(open('07_validation/independent_audit_narrative/defects.json',encoding='utf-8'))
dec=open('00_scenario/canon_decisions.md',encoding='utf-8').read(); dec=dec[dec.index('## Decisions 2026-11-11'):]
mp={}
for n,title in re.findall(r'\n(\d+)\. \*\*([^*]+)\*\*',dec):
    for d in re.findall(r'D\d\d',title): mp[d]=n
note={
 'D02':'this pass: one address for the recovery centre (Martin Luther King Drive)',
 'D04':'this pass: "indictment" replaced by "criminal complaint" (PUB-210) and the unsupported count of 128 claims removed; "FBI Houston Division" and the 94 applications are canon',
 'D07':'this pass: the "most significant ... since 2008" clause removed',
 'D08':'the remaining phrase now reads "on the 28th day of their separate boil-water notice"',
 'D10':'this pass: NWS-P005-06 no longer says helicopters could not fly or that rescues ended Thursday',
 'D12':'"23 calls" is canon',
 'D13':'remaining words are neutral ("released", "Thursday afternoon"); the counts are gone',
 'D18':'headline keeps "recovery stalls"; the body now quotes the utility statement and the 32,000 customers',
 'D24':'headline keeps "Exclusive" and now says the changes predate the storm',
 'D26':'the Oct. 7 report is still cited, without a total',
 'D29':'"55 knots" kept; the start time is 1:22 a.m. Tuesday',
 'D31':'superlative for 1,100 removed; the 2,109 figure is canon',
 'D32':'183 square kilometres and the public imagery are canon',
 'D37':'the old number appears only in a canon note that names it as retired',
 'D38':'this pass: the same sentence in the MSEL corrected',
 'D40':'"Dispatch Chief" of the communications center is canon',
 'D42':'"two minutes" is canon',
 'D47':'this pass: the replacement name was itself real; now Nueces Bay Blood Services everywhere (decision 23a)',
 'D48':'the remaining name is the canon one',
 'D49':'dates kept; "30-day" removed',
 'D50':'"to D+18" is the corrected window',
 'D54':'both stories now say "roughly 500,000"',
 'D44':'enforced on every run by `apply_narrative_fixes.py` (0 story times moved)',
 'D53':'kept as canon and never public; rule B21 added',
 'D28':'no story says a station stayed on the air inside its window',
}
rows=[]
for x in D:
    o=N[x['id']]; left=len(o['still_present'])
    how=f"`n1.py`: {o['n_fragments']-left} of {o['n_fragments']} quoted fragments gone" if o['n_fragments'] else "`apply_narrative_fixes.py`: 0 problems"
    if left: how+=f"; {left} left and reviewed"
    what=("canon decision 2026-11-11 no. "+mp[x['id']]) if x['id'] in mp else "narrative fix scripts p01 to p03"
    if x['id'] in note: what+="; "+note[x['id']]
    rows.append((x['id'],x['severity'],C,what,(x.get('item_id') or '')[:90],how+"; `check_canon_decisions.py --strict` PASS"))
def table(R):
    out=["| Id | Severity | Status | What was done | Where | How verified now |","|---|---|---|---|---|---|"]
    for r in R: out.append("| "+" | ".join(str(c).replace("|","/") for c in r)+" |")
    return "\n".join(out)
allr=A1+A2+rows
cnt={k:sum(1 for r in allr if r[2]==k) for k in (C,P,O)}
md=f"""# Audit closure table

Written 2026-11-11 at the end of the final consistency sweep. One row per defect of the three independent audits:
the first stream audit (`07_validation/independent_audit/REPORT.md`, 18 ranked defects, ids A1-01 to A1-18 here),
the second stream audit (`07_validation/independent_audit_2/defects.json`, 24) and the narrative audit
(`07_validation/independent_audit_narrative/defects.json`, 54).

Every row was checked against the files on disk in this pass, not against the reports of the work that fixed it.
The counting scripts are in `07_validation/audit_closure_checks/` (run from the project root).

**Totals: {len(allr)} defects: {cnt[C]} closed, {cnt[P]} partly closed, {cnt[O]} open.**

What "partly" means here: the main fault is fixed and verified, and a named remainder is still as the auditor found it
or was not measured again. Those remainders are listed in the row. Nothing in this table has been confirmed by a third
independent audit.

Fixed during this pass because the check showed the earlier fix was incomplete: D2-01 (sessions without flows,
remote-desktop commands outside sessions), D2-03 (four remaining tells), D2-05 (historian sessions in the isolation
window), D2-14 (hospital did not match the dispatch record), D02, D04, D07, D10, D38, D47 (narrative residues).
Closed by a canon decision instead of a data change: A1-10, D2-11, part of D2-24 (see `00_scenario/canon_decisions.md`, entry 23).

## First stream audit

{table(A1)}

## Second stream audit

{table(A2)}

## Narrative audit

Method: `n1.py` takes the fragments each defect quotes and looks for them in the stories, facts and events the defect
names. Fragments that are still present were read one by one; they are the canon wording the auditor quoted for
contrast, or neutral words. `scripts/check_canon_decisions.py --strict` (rules in `07_validation/canon_rules.json`)
passes with 0 violations over 681 stories, 177 facts and the public-voice stream files.

{table(rows)}
"""
open('07_validation/reports/audit_closure.md','w',encoding='utf-8').write(md)
print(cnt,len(allr))
