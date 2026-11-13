# Stream generators: the contract

Every delivered data stream is produced by a generator in this folder, from the same truth.
Nothing in `05_other_sources/` is edited by hand.

## Inputs (read only)

| What | Where |
|---|---|
| What happened and when | `00_scenario/canon_timeline.json` (incl. `expected_observations`), `00_scenario/canon_decisions.md` |
| Entities and ids | `06_data_streams/*.json` registries; internal notes and old-id maps in `06_data_streams/_internal/` |
| Stream definitions | `06_data_streams/stream_catalog.json` (path glob, columns, span, cadence), schemas in `06_data_streams/schemas/` |
| Geography | `scripts/geo.py` over `99_reference/geo/` |
| Helpers | `scripts/streams/common.py` (clock, loaders, seeded rng, storm wind/surge, writers, `retire`) |

## Rules

1. **Deterministic.** Use `common.rng(stream_id, ...)`; no wall-clock time, no unseeded randomness. Re-running produces identical files.
2. **Clock.** D0 epoch is `common.D0_EPOCH` (1820880000). Cover at least `SPAN_START`..`SPAN_END` unless the catalogue says otherwise. Write timestamps in the format the stream's standard uses; say UTC or local in the schema.
3. **Canon first.** Every event in `expected_observations` for your streams must be findable in the data at the stated time with the stated entity ids and values. Background activity must never contradict canon (no ship moving in a closed channel, no flight inside the flight restriction, no plant "healthy" while canon says it is down, no alert that canon does not have).
4. **Registry ids only.** Every entity id in a stream exists in its registry. If you need an entity that does not exist, add nothing to another fork's registry: list it in your report.
5. **Geography.** Every coordinate comes from the registries or `geo.py`: vessels routed with `G.nav.route` / `G.water.route`, vehicles with `G.roads.route`, incident and structure locations from `G.roads.random_point(..., setback_m=…)` checked with `G.is_land`. `python3 scripts/check_geo.py --only=<your source>` must report zero violations. Rules for new position sources go in `99_reference/geo/position_rules.d/<family>.json` (same format as `position_rules.json`); do not edit the main rules file.
6. **No answers in the data.** No columns, labels, notes or file names that reveal which records are hostile, fraudulent or coordinated (`AttackSig`, `phase_label`, "malicious", thread ids, D-notation). Hostile activity must look like the real thing would look in that system, surrounded by enough ordinary activity that it has to be found.
7. **Public voice.** Posts, alerts, press text and dispatch narratives never contain never-public terms and contain date-gated terms only from their public day (`02_public_record/restricted_terms.json`). "GridWater" never appears; the utility is Coastal Bend Power and Water Authority (CBPWA). No real company, hospital-system, newspaper or TV-station names.
8. **Physically plausible.** Night is cooler than day; sensors fail in a Category 3 landfall and come back; ships take time to sail; people sleep.
9. **Size.** Keep each file under about 60 MB and each stream under about 150 MB; split by month or by entity. No `_consolidated` duplicates.
10. **Retire old files.** Before writing, move the superseded files of your streams with `common.retire([...])` so stale data cannot be mistaken for current data. Leave other families' files alone.
11. **Do not edit** the canon timeline, MSEL, public record, news, registries, `stream_catalog.json`, `geo.py`, `check_geo.py`, `check_streams.py` or `common.py`. If one of them is wrong or missing something, work around it and say so in your report (catalogue changes go in `06_data_streams/_internal/catalog_changes_<family>.json`).

## What each family delivers

- `scripts/streams/gen_<family>.py` (one or more), runnable as `python3 scripts/streams/gen_<family>.py`, printing row counts.
- `scripts/streams/probes_<family>.py` exporting `STREAMS` and `PROBES` exactly as described at the top of `scripts/check_streams.py`: one probe per expected observation of your streams, each reading the files on disk and returning `(ok, detail)`. A probe that cannot honestly pass must fail; do not weaken it.
- Updated schema files for your streams.
- `python3 scripts/check_streams.py --only=<your streams>` and the geo check for your sources both passing.

## Ground family (911, AVL, SAR, shelters, damage, alerts, broadcast, press releases)

Run order: `gen_ground.py`, then `gen_ground_public.py` (the shelter census reads the bus trips and the
rescue deliveries the first one writes). Where a single call may not run longer than a minute, use
`python3 scripts/streams/gen_ground.py --resume` repeatedly until it prints `DONE` (exit code 3 means
more to do; state is kept under `$GROUND_CKPT`, default `/tmp/ground_ckpt`).

`sar_plan.py` exposes `SORTIES`, the one rescue sortie schedule shared with the aircraft tracks
(data in `sar_plan_data.json`, written by `gen_ground.py`). `verify_ground_geo.py` runs the official
position rules on every ground source file by file; repeat until it prints `COMPLETE - PASS`.

## IT and security family (SIEM, network sensor, audit tables, portals, raw logs, partner organisations)

The raw logs are derived from the logs that were already delivered, so that every log describes the same
activity. Run order (each step reads the files the earlier steps wrote; shell calls are limited to about
three minutes here, so the long ones resume):

    python3 scripts/streams/gen_itsec.py siem                 # alerts (itsec_siem.py; who and where come from itsec_shared.py)
    python3 scripts/streams/gen_itsec.py zeek:2027-07         # sensor logs one month at a time, zeek:2027-07 ... zeek:2028-01 (itsec_zeek.py, itsec_zeek_extra.py);
                                                              #   several months fit in one call: gen_itsec.py zeek:2027-07 zeek:2027-08
    python3 scripts/streams/gen_itsec.py audit                # audit tables (itsec_audit.py), including the gateway and VPN session tables and the mail behind mail alerts
    python3 scripts/streams/gen_itsec.py portal               # aid portal and base logistics access logs (itsec_portal.py)
    python3 scripts/streams/gen_itsec_net.py --all --fresh --budget=120    # firewall, web filter, DHCP, packet capture (57 parts)
    python3 scripts/streams/gen_itsec_net.py --all --resume --budget=120   # repeat until DONE
    python3 scripts/streams/gen_itsec_host.py --all --budget=130           # Windows events, endpoint telemetry, triage last; add --resume and repeat until DONE
    python3 scripts/streams/gen_itsec_net.py dhcp             # once more: the lease log reads the host family's power and reboot model
    python3 scripts/streams/gen_partner_it.py --all --resume  # partner registry, seven organisations and the six extract tables in network_logs/audit/

Anything that changes the alerts, the Zeek logs or the audit tables means re-running everything below it.

Dependencies on other families: `gen_itsec.py portal` mirrors `payments/aid_applications.csv` (written by
`gen_finance.py`) into the aid-portal log, and `gen_partner_it.py` reads the tanker remote-session table
(`gen_ot_vessel.py`), the portal logs, and the alert, port, hospital and base-status streams. So after a change to
`gen_ot_vessel.py` or `gen_finance.py`, re-run `gen_itsec.py portal` and then `gen_partner_it.py --all`.

- `netmap.py` is the one address-to-network table for outside addresses: the portal logs, the aid applications, the
  tanker remote-session table, the partner sign-on logs and their extracts all take addresses and `ASN <number>`
  labels from it, so the same address carries the same network number everywhere. (The utility's own remote-session
  and VPN tables still label networks themselves.)

- `itsec_shared.py` is the shared model: who is at work when (`workday`, `interactive_sessions`, `sessions_at`,
  `user_on`), readers for the delivered Zeek, alert and audit files, zones, and the column lists of the raw logs.
  Logons, DHCP leases, web-filter user names and process owners all come from it.
- `gen_itsec.py` holds the model the writers share: gateway sessions, employee VPN sessions (people, their home
  addresses and devices), historian sessions, suppression changes, file writes, setting changes, SCADA commands,
  installed browsers. Alerts, flows, audit rows, leases and logons about one of these are all written from the one record.
- Sampling convention for the utility: traffic that people cause is a 1-in-200 sample, the same sample in every
  log; sessions, alerts, scheduled machine traffic, mail transfers and everything behind an alert or an audit
  record are complete. The partner organisations state theirs per log (sign-ons complete; web and DNS about
  1 in 40; mail about 1 in 25).
- Story records are drawn through the same functions, vocabularies and distributions as background records. The
  probe files include neutrality checks that fail if a value on a story record is rare elsewhere.
- The raw logs carry observable records only: no payloads, no file contents, no executable samples, no command
  lines beyond a program path and an opened document. Triage collections hold inert text placeholders whose
  SHA-256 is the hash the logs record.
- Checks: the story records are probed through `scripts/check_streams.py` (keys `(event id, stream)` in
  `probes_itsec.py`, `probes_itsec_net.py`, `probes_itsec_host.py`, `probes_partner_it.py`); the invariants that tie
  the raw logs to the delivered logs (every crossing flow has its firewall record, every alert its raw events,
  every extract row is in the partner logs, and so on) run through `python3 scripts/check_itsec_raw.py --resume`.
