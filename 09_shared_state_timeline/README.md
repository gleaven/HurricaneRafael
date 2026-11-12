# Shared state timeline

The hour-by-hour world state of the Hurricane Rafael scenario. Every synthetic data generator (ship tracks, aircraft tracks, sensors, telemetry, 911, payments, logs, imagery, social media) reads its facts from here instead of deciding them itself. It is built from `00_scenario/msel.json` (ground truth) and `02_public_record/public_record.json` (public timing), and checked against both.

## Contents

| File | What it holds |
| --- | --- |
| `data/variables.json` | Catalog of 61 variables (33 state, 28 numeric). Each has its group, unit, visibility (`public`, `internal` or `hidden` truth), lanes (C/D/I), threads (T1-T7), source events and facts, and an `assumption` flag when values go beyond the event list. |
| `data/segments.json` | State variables as `[start_t, end_t, value, note]` intervals covering the whole range with no gaps. |
| `data/series_hourly.json` / `.csv` | Numeric variables, one value per hour (4,320 hours). |
| `data/events.json` | All 64 ground-truth events and 109 public facts, timed to the hour. |
| `data/storm_track.json` | Rafael's 6-hourly position and intensity (landfall Mustang Island, 06:00Z Sept. 14, 2027). |
| `data/state_daily.csv` | Every variable at 18:00Z (about 1 p.m. local) each day, for quick lookup. |
| `viewer/shared_state_timeline.html` | Offline interactive viewer (open in any browser). |
| `viewer/template.html` | Viewer source; `scripts/build_state_viewer.py` embeds the data. |

**Time:** `t` is hours from D0 00:00Z, so landfall is t = 6. Local time is UTC-5 (CDT) until Nov. 7, 2027 07:00Z (t = 1303), then UTC-6 (CST).

## Scripts (run from the project root)

- `python scripts/build_world_state.py`: rebuilds the data (deterministic, fixed seed).
- `python scripts/check_world_state.py`: runs 140 consistency checks against the event list and public facts. These cover storm timing and intensity, port conditions, the 14 ships, the boil-water dates, 9,000 barrels, 40 relief flights, devices, readiness and the FEMA dates. They also confirm the public-knowledge rows never run ahead of the public facts.
- `python scripts/build_state_viewer.py`: rebuilds the viewer.
- `python scripts/state_at.py <day> <hourZ> [--var id]` and `--changes id`: look up the state from the command line. Generators can import `value_at(var_id, t)`.

## The viewer

Its design follows published research on timeline visualization:

- **Faceted linear timeline:** one row per variable on a shared chronological axis, grouped into collapsible facets. This follows the Brehmer et al. timeline design space ([paper](https://aviz.fr/~bbach/timelines/Brehmer2016timelines.pdf)) and LifeLines-style records ([Plaisant et al.](https://www.cs.umd.edu/~ben/papers/Plaisant1996LifeLines.pdf)), with durations as bars and point events as markers.
- **Overview plus detail:** a full 180-day strip with a draggable window above a zoomable detail view, plus cue-based highlighting by storyline thread ([Cockburn, Karlson and Bederson](https://www.microsoft.com/en-us/research/wp-content/uploads/2008/01/cockburn-ComputingSurveys09.pdf)).
- **Horizon charts:** numeric rows draw as two-band horizon charts, which keep readable value comparisons at small heights ([Heer, Kong and Agrawala](https://idl.uw.edu/papers/horizon)). An area-chart toggle is included.
- **Simplified start:** some groups start collapsed and the view opens on the storm approach, to limit initial complexity as EventFlow research recommends ([HCIL](https://hcil.umd.edu/?p=890)).
- **Linked views:** a playhead drives a "state at this moment" panel, nearby events and a storm-track map with a local status inset.
- **Views:**
  - **Truth:** everything, with hidden truth hatched.
  - **Public:** only what the public could know.
  - **Civilian, DoD, IC:** what each lane can observe.

**Controls:**
- **Move the playhead:** `←` `→` by hour, `Shift` + arrow by day, `PgUp` `PgDn` by week.
- **Play:** `Space`.
- **Zoom:** `Ctrl`/`⌘` + wheel, or `+` `-`.
- **Pan:** drag the view, or `Shift` + wheel.
- **Other:** click to move the playhead, click an event marker for details, click a group header to collapse it.

## Assumptions

Variables flagged `A` include values the event list does not specify:
- power-feed restoration times;
- pump capacity;
- outage percentages;
- shelter counts;
- rain and river shapes;
- export activity index;
- the fuel drawdown;
- Halcyon Drift leaving the area after day 33.

Change them in `scripts/build_world_state.py`, then rebuild, recheck and re-lock.
