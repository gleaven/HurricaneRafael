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
