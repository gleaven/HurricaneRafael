# Rafael Scenario — Project Rules

## Standing Rule: Update the Status Doc
After every work session, update the living status doc:
https://claude.ai/artifact/3fFBTj158LaYQsnLJd4jvL

What to update:
- Check off completed items in **Remaining Work**
- Update asset counts in **Corpus Built**, **Data Streams**, **Thread Status**
- Note any new gaps or blockers discovered

## Security Constraints (never violate)
- Never mention in public stories: KESTREL, GW-ENG-VELA, ClearPath SecureReach, GW-SYS-JMP-01, GW-WS-IT-04
- Effects and detection data only — no exploit or OT attack procedures
- Real places, fictional people

## Standing Rules for the Data Layer (added 2026-11-10)
- **Canon first.** `00_scenario/canon_decisions.md` settles every conflict; `00_scenario/canon_timeline.json` is the machine-readable truth every stream is generated from. Where sources disagree, the base scenario (T1–T10) and the news corpus win.
- **Never edit `05_other_sources/` by hand.** Change canon or a registry, then re-run the generator in `scripts/streams/`. Generators are deterministic. The contract is in `scripts/streams/README.md`.
- **One id per thing.** Registries in `06_data_streams/` are the source of ids. Internal notes and old-id maps live in `06_data_streams/_internal/` and are never delivered.
- **Real geography.** Every position comes from the registries or `scripts/geo.py` (real channels, land, roads, airfields in `99_reference/geo/`). Ships stay in channels and water, vehicles on streets, fixed assets on land.
- **Logs first, map second.** The map viewer is built from the logs by `scripts/build_map.py`. It never has tracks of its own.
- **Raw IT logs are derived, not invented.** The firewall, web-filter, DHCP, packet-capture, Windows, endpoint, triage and partner logs are generated from the SIEM, Zeek and audit files on disk through `scripts/streams/itsec_shared.py`; regenerate them whenever those change (order in `scripts/streams/README.md`). Observable records only: no payloads, samples, exploit or attack procedure.
- **No answers in the data.** No column, label, note or value that occurs only on hostile, fraudulent or coordinated records. "GridWater" is an internal code name; the utility is Coastal Bend Power and Water Authority (CBPWA). No real company, hospital-system, newspaper or TV-station names.
- **Gates** (all must pass before a lock; full text in `07_validation/ACCEPTANCE.md`):
  - `python scripts/build_all.py` then `python scripts/check_acceptance.py` (ten narrative criteria)
  - `python scripts/check_streams.py --only=<streams>` (run by family; 398 of 398 observations)
  - `python scripts/check_entities.py`
  - `python scripts/check_geo.py --resume` repeated until it prints `COMPLETE - PASS`
  - `python scripts/check_answer_keys.py --only=<threads>` (run in groups)
  - `python scripts/check_itsec_raw.py --resume` until `PASS` (the raw IT and security logs agree with the logs they are derived from)
  - `python scripts/check_neutrality_utility.py` and `python scripts/check_neutrality_partner.py` until 0 findings (story records are not separable by generator artefacts)
  - `python scripts/check_thread_completeness.py`
  - `python scripts/check_canon_decisions.py --strict` (canon decisions hold in stories, facts, registries and public-voice streams; rules in `07_validation/canon_rules.json`)
  - `python scripts/check_catalog.py` (the stream catalogue and schemas describe the files on disk)
  - `python scripts/build_map.py --resume` until `COMPLETE`, then `python scripts/check_map.py --all --resume` until it reports every day checked
  - `python scripts/build_delivery.py --resume` until `PASS` (participant package manifest and leak scan)
  - `python 10_news_sites/newsroom/tools/verify_gating.py`
  - then `python scripts/snapshot.py --lock`
- Shell commands are cut off after about three minutes in this environment: long checks and builds have `--resume`.

## Current State (as of 2026-11-12)
- Narrative corpus: 681 stories, 177 facts, 182 MSEL events, 22 threads, 29 arcs, 8 outlets, 116 characters. Canon decisions of 2026-11-11 (23 entries in `00_scenario/canon_decisions.md`) hold in every layer: `check_canon_decisions.py --strict` 0 violations
- Audits: three independent audits of the earlier streams and the narrative, 96 defects. `07_validation/reports/audit_closure.md`: 92 closed, 4 partly closed, 0 open, each row checked against the files on disk; not confirmed by a further independent audit. The IT and security logs had two independent reviews of their own on 2026-11-12 (`independent_audit_3/`: 13 blocking, 24 major, 15 minor; `independent_audit_4/` after the fixes: 5 blocking, 21 major, 14 minor). Both sets were fixed; the second set was checked with that reviewer's scripts and a short third blind check. Item-by-item status: `07_validation/reports/it_log_review_closure.md`
- Geography: real USACE, NOAA and Census geometry; full street network (12,786 roads) and inland water layer; map road matching 0 unmatched gaps
- Registries: vessels (130), aircraft (64), facilities (45), response units (315), hosts (329), SCADA tags (331), social accounts (309), organisations (259), areas (148); partner IT registry (7 organisations, 496 hosts, 2,169 accounts). FAC-BLD-020 is Nueces Bay Blood Services (fictional)
- Data streams: 56 delivered streams, about 1.9 GB in 2,777 files, largest 36 MB (13 raw IT and security streams added 2026-11-12; SIEM, Zeek, audit and portal logs rebuilt with them and again after each of the two independent reviews; the tanker remote-session table and the aid applications' address columns regenerated with the shared address table `scripts/streams/netmap.py`); 398 of 398 expected observations present (run by family on 2026-11-12); 86 of 86 raw-log invariants (`check_itsec_raw.py`); catalogue and schemas match the files (`check_catalog.py`); entities 130 id columns against 14,535 registry ids
- Knowledge graph: 4,405 nodes, 27,092 edges internal; 3,360 and 21,146 public; 0 orphans
- Answer keys: 22 threads, 300 of 300 steps verified, and 60 of 60 raw-log records listed under them
- Hackathon materials: `11_hackathon/` (player brief, data guide, game-master guide, data tables, exclusion list). Delivery package: 2,860 files, 1,923 MB, leak scan passes, 43 early mentions of date-gated names listed for review
- Presentation layer: newsroom and map viewer built and checked by script; **still not seen in a real browser**
- Lock: re-lock after the final gate run of 2026-11-12 (`python scripts/snapshot.py --lock`); leave reviewers' caches under `07_validation/independent_audit_*/` (`cache/`, `*.pkl`) out of the lock and out of any repository copy

## Next Up
1. Run the full gate list above once more in one pass, then `python scripts/snapshot.py --lock`.
2. Open the newsroom and the map viewer in a browser; fix what looks wrong. Offline, the map uses its built-in fallback view (Leaflet could not be bundled).
3. Remaining items in `07_validation/reports/audit_closure.md` (four rows marked partly) and in the status doc's open list.
