# Hurricane Rafael: project guide

**Status (2026-11-12):** thirteen raw IT and security streams were added (the utility's firewall, web filter, DHCP, packet capture, Windows event, endpoint and triage logs, and the IT logs of seven partner organisations), and the SIEM, Zeek, audit and portal logs were rebuilt with them. Two independent reviews of these logs followed (`07_validation/independent_audit_3/`, `independent_audit_4/`); the findings of both were fixed, the second set checked with that reviewer's own scripts, and the item-by-item status is in `07_validation/reports/it_log_review_closure.md`. Every stream, entity, catalogue, answer-key, raw-log, map and delivery gate passes on the final files; the files are re-locked after the last check. The map viewer has been seen rendered in its offline view; its satellite view and the live newsroom pages have had little hands-on browser testing. This is the detailed working reference; the overview is the `README.md` at the repository root.

A fictional six-month scenario (scenario days -60 to +119; landfall is day 0, 2027-09-14) set in the real Texas Coastal Bend. It produces a news corpus, 56 linked synthetic data streams, a knowledge graph and answer keys for a hackathon in which teams build tools to work out what happened. **The files in this folder are the master copy.**

## Where things are

| Folder | What's in it | Who reads it |
| --- | --- | --- |
| `00_scenario/` | Ground truth. `canon_decisions.md` (how every conflict was settled), `canon_timeline.json` (machine-readable truth, including the 398 `expected_observations`), `msel.json` (182 events, each with structured `observed_in`), `threads.json`, `places.json`, `entities.json`, `config.json` (calendar anchor), `scenario_bible.md` | Generators and controllers only |
| `01_characters/` | `characters.json` (116 characters with knowledge timelines), `canon.json`, `outlets.json` (8 fictional outlets) | Writers |
| `02_public_record/` | `public_record.json` (177 dated public facts: the only things news may say), `restricted_terms.json` (leak guard), `quantity_rules.json` | Writers, validator |
| `03_news/` | `stories/batch-*.json` (681 articles), `arcs.json` (29 storylines), `story_index.json`, `rss/`, `WRITER_GUIDE.md`, `story_schema.json`, `coverage_targets.json` | Everyone |
| `04_knowledge_graph/` | `internal/` and `public/` views as `graph.json`, `nodes.csv`, `edges.csv`, `graph.graphml`; `neo4j_import.cypher`; `viewer.html` | Analysts |
| `05_other_sources/` | The 56 delivered data streams (about 1.9 GB). See `05_other_sources/README.md`. Never edited by hand | Participants |
| `06_data_streams/` | Registries (the source of every entity id), `stream_catalog.json` (path, columns, span, cadence of every stream; internal because it names threads), `schemas/`, `_internal/` (truth notes and old-id maps; never delivered) | Generators; registries and schemas also go to participants |
| `06_answer_key/` | `answer_key.json`: for each of the 22 threads, the chain of observations a team must join | Controllers only |
| `07_validation/` | `ACCEPTANCE.md`, `reports/` (latest check results), `independent_audit/`, `independent_audit_2/`, `independent_audit_narrative/`, `reports/audit_closure.md`, `audit_closure_checks/`, `findings/`, `allowlist.json`, `manifest.lock.json` | QA |
| `08_release/` | `news_stories_public.json`: public fields only | Participants |
| `09_shared_state_timeline/` | Hour-by-hour world state, storm track and advisories, the timeline viewer, and the map viewer (`viewer/map_view.html` with `viewer/map_data/`) | Controllers |
| `10_news_sites/newsroom/` | Local server for the eight outlet sites with a game-master clock. The eight loose `10_news_sites/*.html` pages are superseded mock-ups | Controllers, participants |
| `99_reference/geo/` | Real geometry: USACE channel reaches and centerlines, NOAA land areas and anchorages, Census roads, landmark points, with `SOURCES_*.md` and `position_rules.json` | Generators, checks |
| `scripts/` | The pipeline, the generators (`scripts/streams/`) and the checks | Builders |
| `scenarios/` | Scenario registry and the `gridwater` layer (threads T8 to T10, T18) | Builders |
| `_versions/` | Snapshots, and the superseded streams from before the rebuild | Archive |

## How the data layer works

1. **Canon.** `00_scenario/canon_decisions.md` and `00_scenario/canon_timeline.json` say what happened and when. Where older material disagreed, the base scenario and the news corpus won.
2. **Registries.** `06_data_streams/*.json` define every vessel, aircraft, facility, unit, host, tag, sensor, account, organisation and area once, on real sites.
3. **Geography.** `scripts/geo.py` loads `99_reference/geo/` and answers: is this point on land, which channel reach is it in, what is the channel route between two berths, the water route for a small boat, the street route for a vehicle.
4. **Generators.** `scripts/streams/gen_<family>.py` write the streams from 1 to 3. They are deterministic. The contract they follow is `scripts/streams/README.md`. Each family also has `probes_<family>.py`, which finds every expected observation in the files on disk.
5. **Map.** `scripts/build_map.py` builds the map viewer's data from the logs. The map never has tracks of its own.

To change a stream: change canon or a registry, re-run the affected generator, re-run the checks. Do not edit `05_other_sources/` by hand.

### Generators

```
python scripts/streams/gen_maritime.py --budget 140      # repeat until done (AIS, port surveillance, conditions, arrivals, manifests)
python scripts/streams/gen_aviation.py                   # ADS-B
python scripts/streams/gen_drones.py                     # drone telemetry and detections
python scripts/streams/gen_satellite.py                  # run again whenever AIS changes
python scripts/streams/gen_ground.py                     # 911, vehicle locations, SAR, shelters, damage
python scripts/streams/gen_ground_public.py              # alerts, broadcast logs, public statements
python scripts/streams/gen_ot_scada.py e1                # one part at a time: e1 e2 w1 w2 sys
python scripts/streams/gen_ot_records.py                 # outage map, work orders, base status, fuel
python scripts/streams/gen_ot_vessel.py                  # tanker cargo-control logs (vendor addresses from netmap.py)
python scripts/streams/gen_itsec.py siem                 # one part at a time, in this order: siem, zeek:<month> for each month, audit, portal
                                                         #   portal mirrors payments/aid_applications.csv: run gen_finance.py before it when applications change
python scripts/streams/gen_itsec_net.py --all --resume   # firewall, web filter, DHCP, packet capture (start with --fresh; repeat until DONE)
python scripts/streams/gen_itsec_host.py --all --resume  # Windows events, endpoint telemetry, triage (repeat until DONE)
python scripts/streams/gen_itsec_net.py dhcp             # again, after the host logs
python scripts/streams/gen_partner_it.py --all --resume  # partner registry, seven organisations, six extract tables (reads the tanker remote-session table and the portal logs)
python scripts/streams/gen_environment.py                # weather, gauges, water and air quality
python scripts/streams/gen_health.py                     # emergency visits, capacity, syndromic, wastewater
python scripts/streams/gen_finance.py                    # claims, aid, contracts, transactions (applicant addresses from netmap.py; then gen_itsec.py portal and gen_partner_it.py again)
python scripts/streams/gen_census.py
python scripts/streams/gen_social.py                     # last: its bot accounts read sensor files
```

Shell commands are cut off after about three minutes in the build environment, so the long generators and checks work in pieces and resume.

The raw IT and security logs (`gen_itsec_net.py`, `gen_itsec_host.py`, `gen_partner_it.py`) are derived from the SIEM, Zeek and audit files on disk, so they must be re-run whenever those change. The family's run order, shared model (`itsec_shared.py`) and sampling convention are in `scripts/streams/README.md`.

## Checks

Run from this folder with Python 3.8 or newer.

```
python scripts/build_all.py                              # narrative pipeline, expected observations, answer keys, graph, RSS, release
python scripts/check_acceptance.py                       # the ten narrative criteria
python scripts/check_streams.py --only=ais,port_surveillance,port_conditions,port_arrivals,cargo_manifests
                                                         # every expected observation is in the data; run one family at a time
python scripts/check_entities.py                         # every id in every stream is in a registry
python scripts/check_geo.py --resume                     # repeat until it prints "COMPLETE - PASS"
python scripts/check_answer_keys.py --only=T1,T2,T3,T4   # every answer-key step, and every raw-log record listed under it, exists on disk; run in groups
python scripts/check_itsec_raw.py --resume               # repeat until PASS: the raw IT and security logs agree with the logs they are derived from
python scripts/check_thread_completeness.py              # every thread complete end to end
python scripts/check_canon_decisions.py --strict         # canon decisions hold in stories, facts, registries and public-voice streams
python scripts/check_catalog.py                          # catalogue and schemas describe the files on disk
python scripts/build_map.py --resume                     # repeat until COMPLETE
python scripts/check_map.py --all --resume               # every day: no vessel on land, no moving vehicle off a road
python scripts/build_delivery.py --resume                # participant package manifest and leak scan; repeat until PASS
python 10_news_sites/newsroom/tools/verify_gating.py     # no future story reachable through the newsroom
python scripts/snapshot.py --lock                        # re-lock after a reviewed change
```

What the long ones check:

- **`check_geo.py`** reads `99_reference/geo/position_rules.json` (and `position_rules.d/`). Vessels are never on land; deep-draft vessels stay in channels maintained to 40 ft, anchorages or the open Gulf; consecutive fixes never have land between them; incident locations are on land near a street; vehicles are within 30 m of a road; aircraft are on the ground only at airfields and helipads; fixed assets are on land (sondes and buoys in water).
- **`check_streams.py`** checks each delivered stream in `06_data_streams/stream_catalog.json` for files, time span, registry ids, answer-revealing columns, banned names, and its expected observations.
- **`check_itsec_raw.py`** runs the 86 invariant probes of the raw IT and security logs: every flow that crosses a firewall has its session record and its captured packets, every web flow its filter record, every alert its raw events, every remote session its logon, every row of the partner extracts is in the partner logs, and no host, address or account is outside the registries.

Latest results are in `07_validation/reports/` (`geo_check.json`, `stream_check.json`, `entity_check.json`, `answer_key_check.json`, `thread_completeness.md`, `acceptance.json`). An independent audit of the regenerated streams is in `07_validation/independent_audit/REPORT.md`.

## Viewers

- **Newsroom:** `10_news_sites/newsroom/`. Double-click `start_newsroom.bat` (this computer only) or `start_newsroom_lan.bat` (shared network), or run `python server.py [--lan]`. The window prints the addresses: the newsstand for participants, `/control` for the game master's clock, `/explorer` for the whole corpus. Details in `10_news_sites/newsroom/README.md`. After the news corpus changes, `python 10_news_sites/newsroom/build_data.py` (the server also rebuilds at start).
- **Map:** open `09_shared_state_timeline/viewer/map_view.html`. It needs the `map_data/` folder beside it and an internet connection for the map library and satellite tiles (an offline chart basemap is built in). Rebuild with `python scripts/build_map.py --resume` after any stream with positions changes; the build cache in `viewer/_build_cache/` does not notice changed inputs, so delete the affected cache files first.
- **Knowledge graph:** `04_knowledge_graph/viewer.html`.
- **Timeline:** `09_shared_state_timeline/viewer/shared_state_timeline.html`.

## Narrative pipeline

`python scripts/build_all.py` runs, in order: `build_world_state.py`, `check_world_state.py`, `build_state_viewer.py`, `validate.py`, `merge_character_updates.py`, `link_stories.py`, `build_expected_observations.py`, `reconcile_entities.py`, `build_answer_keys.py`, `build_graph.py`, `build_graph_viewer.py`, `build_rss.py`, `build_release.py`, `check_integrity.py`, `check_scenarios.py`.

Other tools:

- `python scripts/kg_query.py character CHR-040 --before 60`: what a character has said and done before a day.
- `python scripts/kg_query.py arc ARC-SPILL`: a storyline in order.
- `python scripts/kg_query.py story NWS-P044-01`: a story's neighbours.
- `python scripts/kg_query.py day 44`: everything published on a day, plus facts going public that day.
- `python scripts/dates.py 0 10`: calendar dates and time zones for scenario days.

## Knowledge graph

- **Node types:** Story, Outlet, Character, Arc, PublicFact, Place, plus the registry entities (Organization, Vessel, Aircraft, Facility, Asset, Equipment, Host, UserAccount, ScadaTagGroup, Sensor, SocialAccount, ResponseUnit, Station, Area, Terminal, Berth, Registry) and DataStream. The internal view adds Event, Thread, Entity, Observation, AnswerKeyPath and OldId.
- **Edges added in the rebuild:** `INVOLVES` (event to entity), `MENTIONS_ENTITY` (story or fact to entity), `OPERATED_BY`, `OWNED_BY`, `PART_OF`, `SERVES`, `LOCATED_AT`, `WITHIN`, `OBSERVED_IN`, `EVIDENCED_BY`, `RECORDS`, `LISTED_IN`, `HAS_STEP`, `SOLVES`, `SAME_AS` (internal only).
- Every node has at least one edge. The public view drops every ground-truth node, edge and property and the never-public entities, so it can be shared.

## Scenarios

`scenarios/registry.json` lists every scenario.

- **rafael:** the base world. Its files stay at the project root.
- **Layers:** a layer (currently `gridwater`) lives under `scenarios/<id>/`. It shares the base world's places, calendar, characters and state timeline, and prefixes every id it adds (`GW-EVT-*`, `GW-PUB-*`, `GW-*` assets, `gw_*` state variables).

Tools: `python scripts/new_scenario.py <id> --name "..." --prefix XX` scaffolds a scenario; `check_scenarios.py` (criterion 10) validates the registry, prefixes and id collisions.

## Quality gates for the news corpus

| Gate | File | Script |
| --- | --- | --- |
| Public timing, leaks, ids, bylines, word counts, daily coverage | `02_public_record/public_record.json`, `restricted_terms.json` | `validate.py` |
| Character fixed facts | `01_characters/canon.json` | `check_canon.py` |
| Numbers and weekday-date pairs traced to the record and calendar | `02_public_record/quantity_rules.json` | `check_facts.py` |
| Reviewed exceptions, each with a reason | `07_validation/allowlist.json` | (read by the checks) |
| Review findings as exact-text fixes | `07_validation/findings/*.json` | `apply_fixes.py` |
| Integrity: every public fact reported, citations match text, knowledge timing | `07_validation/reports/integrity_report.json` | `check_integrity.py` |
| Acceptance criteria | `07_validation/ACCEPTANCE.md` | `check_acceptance.py` |
| Lock and changelog | `07_validation/manifest.lock.json`, `CHANGELOG.md` | `snapshot.py` (`--lock`, `--verify`) |

Any change after a lock fails criterion 7 until it is reviewed and re-locked. `snapshot.py "label"` also writes a zip of the whole folder to `_versions/`; with the streams the corpus is about 1.5 GB, so no zip was taken after the rebuild.

## Rules that keep it consistent

- **One truth:** everything derives from the event list and the canon timeline; news may only use public-record facts on or after their day; streams contain every expected observation and nothing that contradicts canon.
- **Real places, fictional people:** places, agencies, bases, channels, streets and airfields are real; people, companies, outlets, hospitals, vessels, aircraft, the storm and the foreign sponsor are fictional. Real elected officials and agency heads are never named or quoted. The real names in `99_reference/geo/landmarks.geojson` are reference data only.
- **Registry ids only:** a new entity goes into its registry first.
- **No answers in the data:** no column, label or value that marks hostile, fraudulent or coordinated records. The utility is Coastal Bend Power and Water Authority; "GridWater" is an internal code name.
- **Calendar:** D0 is 2027-09-14 local; the epoch of 2027-09-14T00:00Z is 1820880000; landfall is 06:00Z.

## Adding or changing news content

1. **Plan:** add or edit public facts (with a `day`) and any new characters.
2. **Write:** generate stories into a batch file, following `03_news/WRITER_GUIDE.md`.
3. **Build:** run `python scripts/build_all.py` and fix every validation error, then the newsroom build and `verify_gating.py`.

## Known limits

- The map viewer has been seen rendered only in its offline fallback view (Leaflet could not be bundled); its satellite view and the live newsroom pages have had little hands-on browser testing.
- About 180 remote lake and pond polygons were not cross-checked against wetlands data, and about 12 km of roads at Copano Bay and Egery Flats read as water.
- Three independent audits found 96 defects. `07_validation/reports/audit_closure.md` records 92 closed and 4 partly closed, each checked against the files, but no further independent audit has confirmed the fixes. The four partly closed rows: two network-number notations (one per system), outside network addresses in routable ranges (invented, and documented as such), aircraft touchdown scatter and speed ramps not measured again, and a short list of small oddities.
- The GPS interference of Oct. 22 to 27 is visible in aircraft data only; ship, vehicle and drone positions carry no added error (canon decision 23f).
- 43 early mentions of date-gated names in posts and dispatch narratives are listed for review in `11_hackathon/delivery_warnings.json`.
- The raw IT and security logs carry observable records only: no payloads, no file contents, no executable samples, no exploit or attack procedure. Packet captures stop after the first packets of a flow; triage collections hold inert text placeholders. They support detection, correlation and triage exercises, not malware analysis.
- The raw IT and security logs were added on 2026-11-12 and reviewed twice by independent reviewers. The first review found 13 blocking defects (mostly hostile records that a single value count could isolate), the second, after the fixes, 5. Both sets were fixed; the second set was checked with that reviewer's own scripts and by a short third blind check, not by a full third review. Status of every item: `07_validation/reports/it_log_review_closure.md`.
- Addresses and names outside the organisations are invented. Where they look routable they necessarily fall in address space that belongs to someone in the real world; no real host is meant. Some carried-over streams use documentation ranges instead.
- Known weaknesses of the IT and security logs: user-driven traffic is a thin 1-in-200 sample; there are no Linux, network-device or controller logs; Windows events are a forwarded subset; lock and unlock events come from two zones only; file hashes in the audit tables are shortened to 16 hexadecimal characters; the password-guessing run on the aid portal is found with one filter because of its sheer volume; the story's first workstation is a quiet shared desk; the utility's own response is in the data from 2027-10-02T14:33Z (a staged release cut before then is the harder exercise); the partner organisations' office networks share one behavioural model; the utility's remote-session and VPN tables do not use the address-to-network table the portal, payment, tanker and partner logs share; DNS has no CNAME chains; Windows shutdowns are almost all patch restarts.
- Writers added well-known real details that should be checked before external release, such as the Texas 2-1-1 evacuation registry, the JFK Causeway and Highway 361, and Hurricane Harvey references.
