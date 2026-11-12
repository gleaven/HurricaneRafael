# What participants do not receive

Written by `scripts/build_delivery.py`. Internal: for the game master.

| Withheld | Why |
|---|---|
| `00_scenario/` | the hidden timeline, event list, storyline definitions and canon decisions |
| `01_characters/` | character sheets, including people who are not public |
| `02_public_record/` | the public record with its links to hidden events (teams get the dated statements in data/press_releases/) |
| `03_news/ and 08_release/` | story sources and the full story file: news reaches teams through the newsroom only, on the clock |
| `04_knowledge_graph/` | both graph views: the internal one holds the answers, the public one holds every story at once |
| `06_answer_key/` | the answer keys |
| `06_data_streams/_internal/` | internal notes on entities and old-id maps |
| `06_data_streams/stream_catalog.json` | lists which storylines rely on each stream; a copy without those fields ships as schemas/stream_catalogue.json |
| `06_data_streams/schemas/00_schema_index.json` | superseded by schemas/stream_catalogue.json |
| `07_validation/` | audit reports, findings and check results |
| `09_shared_state_timeline/` | the map viewer and state timeline: they include the game master's truth layers |
| `10_news_sites/` | the newsroom server is run by the game master; teams use it over the network |
| `11_hackathon/GAME_MASTER_GUIDE.md` | for the game master |
| `99_reference/geo/_parts, _cache, position_rules*` | working files of the geography build and the validator's rule list |
| `_thread_designs/, scenarios/, _versions/` | design files, the layered scenario definitions and old snapshots |
| `scripts/` | generators, probes and checks |
| stream `news` | stories are released by the newsroom on the exercise clock (web pages, RSS, API), not as a file |

## Removed from the schema files before they ship

- `01_ais_schema.json`: notes, scenario_notes, verified
- `02_911_cad_schema.json`: generator_reference, location_rule, verified
- `03_scada_telemetry_schema.json`: generator, verified
- `04_social_media_schema.json`: generator, verified
- `05_weather_schema.json`: generator_reference, verified
- `06_adsb_schema.json`: generator, scenario_notes, verified
- `07_env_sensors_schema.json`: generator_reference, verified
- `08_satellite_schema.json`: generator, scenario_notes, verified
- `09_drone_video_schema.json`: generator, scenario_notes, verified
- `10_network_logs_schema.json`: generator
- `11_maintenance_schema.json`: generator, verified
- `12_supply_chain_schema.json`: scenario_notes, verified
- `13_payments_schema.json`: generator, notes, verified
- `14_infrastructure_schema.json`: generator_reference, location_rule, verified
- `15_census_schema.json`: generator, verified
- `16_public_health_schema.json`: Generator_Hours_Cumulative, generator_reference, verified
- `17_drone_detections_schema.json`: entity_catalog, generator, scenario_notes
- `avl_schema.json`: generator_reference, location_rule
- `broadcast_logs_schema.json`: generator_reference
- `eas_alerts_schema.json`: generator_reference
- `fuel_deliveries_schema.json`: generator, verified
- `outage_map_schema.json`: generator, verified
- `port_surveillance_schema.json`: scenario_notes, verified
- `public_record_schema.json`: generator_reference
- `sar_missions_schema.json`: generator_reference
- `shelters_schema.json`: generator_reference
- `vessel_ot_logs_schema.json`: generator, verified

## Staged release

`--until YYYY-MM-DD` cuts row-oriented files on their main time column. Tables that are updated after a record is opened (work orders, port calls, dispatch records, claims, contracts) ship whole once opened; tables with no time column ship whole. See the docstring of `scripts/build_delivery.py`.
