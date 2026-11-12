# Scenario layer: gridwater (Coastal Bend utility cyberattack)

**Status:** design. Scaffolded, with no events, facts or state yet.

A layer on the Rafael base world. It shares Rafael's places, calendar (D0 = Sept. 14, 2027), characters and shared state timeline, and adds threads T8 to T10 with its own events, public facts, assets, state variables and detection streams. Every ID it adds carries the `GW` prefix: `GW-EVT-*`, `GW-PUB-*`, `GW-*` assets, and `gw_*` state variables.

**Purpose:** an educational blue-team detection hackathon. Teams must separate real storm damage from a deliberate intrusion on the electric grid and the water system, and correlate the two. The scenario is modeled at the level of observable effects and detection data only, with no attack technique.

| Path | Holds |
| --- | --- |
| `00_scenario/config.json` | Calendar, time zone, public exclusions |
| `00_scenario/threads.json` | T8 Grid intrusion, T9 Water SCADA manipulation, T10 Hiding in the storm |
| `00_scenario/msel.json` | Ground-truth events (`GW-EVT-*`) |
| `00_scenario/assets.json` | Fictional assets on realistic topology (`GW-*`) |
| `00_scenario/state_layer.py` | Adds `gw_*` variables to the shared state timeline |
| `02_public_record/public_record.json` | Public facts (`GW-PUB-*`) |
| `05_streams/` | Detection telemetry |
| `06_answer_key/` | Join paths that prove each thread |
