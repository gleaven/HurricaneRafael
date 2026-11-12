# Acceptance criteria

The dataset is accepted only when `python scripts/check_acceptance.py` reports PASS on all of these:

1. **Validator:** zero errors across all stories. This covers public-record timing, leak terms, IDs, bylines, word counts and daily coverage.
2. **Canon:** zero violations of character fixed facts (`01_characters/canon.json`).
3. **Numbers and dates:** every material number traced to `02_public_record/quantity_rules.json` on or after its public day; every weekday-date pair correct. Reviewed exceptions sit in `07_validation/allowlist.json`, each with a reason.
4. **Review findings:** no open high-severity finding in any `07_validation/findings/*.json`.
5. **Second review:** an independent second review pass (`review2-*.json`) exists, with no open high-severity findings.
6. **Public outputs:** the release JSON, RSS and public graph contain none of the never-public terms.
7. **Lock:** the files match `07_validation/manifest.lock.json`. Any later change needs a new review and lock.
8. **Integrity:** every public fact is reported at least once; each fact cited by a story is actually in its text (reviewed exceptions allowlisted); no one is quoted before their knowledge timeline starts; follow-up links point backward; the RSS, release and graph match the story set; wire stories carry the standard dateline (`check_integrity.py`).
9. **World state:** the shared state timeline passes all consistency checks against the ground-truth events and the public record (`check_world_state.py`).
10. **Scenarios:** the registry is valid; each layer's events, facts, assets and state variables carry its prefix; no thread or ID collides across scenarios (`check_scenarios.py`).

## Data-stream gates (added 2026-11-09)

The narrative checks above cover the news corpus. The delivered data streams, registries, geography and answer keys are accepted only when each of these also reports PASS. They are separate commands because the stream files are large; each can be run in pieces.

11. **Streams match the timeline:** `python scripts/check_streams.py` (or in groups with `--only=stream_a,stream_b`). Every delivered stream in `06_data_streams/stream_catalog.json` exists, covers its required span, uses only registry ids, has no answer-revealing columns or never-public terms, and every expected observation in `00_scenario/canon_timeline.json` (357) is found on disk by its probe.
12. **Entities:** `python scripts/check_entities.py`. Every id in every stream column listed in the script exists in a registry; registry ids are unique; every registry entry is used by a stream or marked `reference_only` with a reason; no real company or station names and no "GridWater" in registries, schemas or stream files.
13. **Geography:** `python scripts/check_geo.py --resume` repeated until it prints `COMPLETE - PASS`. Every position in every stream and registry satisfies its rule in `99_reference/geo/position_rules.json` and `position_rules.d/` (vessels in water and, if deep-draft, in the dredged channels or anchorages; fixed assets on land or in water as declared; incident locations on streets; vehicles on roads; aircraft on the ground only at airfields and helipads).
14. **Answer keys:** `python scripts/check_answer_keys.py` (or `--only=T8,T9`). Every thread T1-T22 has a key with a question, a conclusion and at least three steps across two streams, and every step's records exist on disk.
15. **Thread completeness:** `python scripts/check_thread_completeness.py`. Every thread has a beginning, an escalation, a discovery and a resolution, public facts, stories, at least one delivered stream with evidence and a verified answer key (`07_validation/reports/thread_completeness.md`).

## Consistency gates (added 2026-11-11)

16. **Canon decisions:** `python scripts/check_canon_decisions.py --strict`. No story, public fact, newsroom text, registry or public-voice stream file contradicts `00_scenario/canon_decisions.md`: banned and retired names, date-gated terms before their public day, events inside their windows, weekdays, and every tracked figure by day (`07_validation/canon_rules.json`, `07_validation/reports/narrative_figures.json`). Zero violations.
17. **Map:** `python scripts/build_map.py --resume` until `COMPLETE`, then `python scripts/check_map.py --all --resume` until every day is checked. No vessel on land, no moving vehicle off a street, on every day of the span.
18. **Catalogue:** `python scripts/check_catalog.py`. Every delivered stream's files exist, every column the catalogue names is in the files, every file in `05_other_sources/` belongs to a catalogued stream, and every column on disk is described in a schema.
19. **Delivery package:** `python scripts/build_delivery.py --resume` until it prints `PASS`. No internal ids or notes, no scenario-day notation, no answer-revealing columns, no never-public or early date-gated terms in public-voice files. Early mentions outside official statements are listed for review in `11_hackathon/delivery_warnings.json`.

The closure state of every audit defect is in `07_validation/reports/audit_closure.md`; the counting scripts behind it are in `07_validation/audit_closure_checks/`.

Order after any change to canon or registries: `apply_integration_fixes.py` and `apply_catalog_and_people.py` (idempotent) → re-run the affected generators in `scripts/streams/` → `apply_registry_additions.py --mark` (after `check_entities.py --usage`) → `apply_narrative_fixes.py` (idempotent) → `build_all.py` → gates 11-19 → newsroom `build_data.py` and `tools/verify_gating.py`.
