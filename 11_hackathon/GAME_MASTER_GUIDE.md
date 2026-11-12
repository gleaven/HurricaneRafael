# Game master guide

**Internal. Do not give this file to participants.** It points at the answers.

Paths are relative to the project folder (`News Stories`). Commands need Python 3.8 or newer and nothing else, except where noted.

## 1. What you hand out

| To participants | Where it comes from |
|---|---|
| The data package: `data/`, `registries/`, `schemas/`, `reference/`, `docs/` | `python scripts/build_delivery.py --copy <folder>` |
| The newsroom address | the newsroom server's start-up window |
| `docs/PLAYER_BRIEF.md`, `docs/DATA_GUIDE.md`, `docs/DATA_TABLES.md` | inside the package |

Everything else stays with you. `11_hackathon/EXCLUDED.md` lists what is withheld and why, and `11_hackathon/delivery_manifest.json` lists every file that ships, with its size and SHA-256.

## 2. Build the package

```
python scripts/build_delivery.py --resume --budget=140      repeat until it prints PASS (hashing and scanning about 1 GB)
python scripts/build_delivery.py --copy D:\rafael_package    copy the whole period
python scripts/build_delivery.py --copy D:\stage1 --until 2027-09-20    only rows time-stamped before 20 Sept (UTC)
```

The builder refuses to produce a package (exit 1, with the file and the offending text) if anything internal would ship: event ids, storyline fields, answer-revealing column names, scenario-day notation, never-public names in posts, statements, alerts or narratives, or a date-gated name in an official statement before its public day.

`11_hackathon/delivery_warnings.json` lists date-gated names that appear early in posts, reports or scene descriptions. Read it once. At the time of writing these are: the accounts that spread the lookalike aid link use its address from the day they start, the terminal operator's own account and one satellite scene name the terminal before the spill makes it news. All are things the public could see at the time; none needs removing.

### All at once, or in stages

- **All at once** is simplest and suits a one-day event. Teams get the full four months and the news catches up with them on the clock.
- **Staged** suits a multi-day event. Run `--copy` with `--until` for each stage into a new folder and hand out the folders in turn. Each folder is complete up to its date, so later folders replace earlier ones.

Limits of a staged cut (also in the builder's help text): tables that keep being updated after a record is opened (work orders, port calls, dispatch records, claims, contracts) ship whole once the record's opening time is before the cut, so they can show a later status. Tables with no time column ship whole. `social_media/_account_lookup.jsonl` is an end-of-collection snapshot and only appears once the cut passes 12 January 2028. If a stage must hide a particular development, cut before it or hold those tables back.

Suggested stage boundaries, chosen to fall between developments rather than on them: 2027-09-12, 2027-09-20, 2027-10-10, 2027-10-27, 2027-11-13, 2027-12-15, then everything.

## 3. Run the newsroom

Full instructions: `10_news_sites/newsroom/README.md`.

| | Windows | Mac / Linux |
|---|---|---|
| This computer only | `10_news_sites/newsroom/start_newsroom.bat` | `./start_newsroom.sh` |
| Shared network | `start_newsroom_lan.bat` | `./start_newsroom.sh --lan` |

The window prints the participant address, the control page address and, on a network, the game-master passphrase.

- **Control page** (`/control`): the exercise clock. Play at a chosen speed, step, jump to the next story or to a milestone, hold an outlet, release a story early, rewind, reset. The clock survives a restart.
- **Corpus explorer** (`/explorer`): every story regardless of the clock, with filters, a day view across outlets and a storyline view.
- **Participants** use `/` (newsstand), `/feeds`, the RSS feeds and `/api/articles`. Nothing published after the clock reaches any of them.

Before the event, run `python 10_news_sites/newsroom/tools/verify_gating.py`. It starts a throwaway server, jumps through the whole timeline and fails if any future story, internal id or early name is reachable.

Keep the newsroom clock and the data stages in step: when you hand out a stage cut at a date, set the clock to that date.

## 4. Focus questions and when to release them

The answer key holds one question per storyline (`06_answer_key/answer_key.json`, field `question`). Release a question only once the public news has raised it. The dates below are the first day the public record carries each development; do not post a question earlier than its date, and word it no more specifically than the news does at that point.

| Earliest | Question | Storyline |
|---|---|---|
| any time | What does ordinary look like for this port, this utility, this city? (baseline work) | all |
| 2027-09-15 | What does the 911 record say about the storm, hour by hour? Who was rescued, where, and by whom? | T13, T17 |
| 2027-09-15 | Why did two moored tankers spill oil as the storm arrived? (cause "under investigation" from 14 Sept; possible remote access said publicly 20 Sept) | T6 |
| 2027-09-16 | Where did the oil go, and who breathed it? | T20 |
| 2027-09-16 | What are the lights residents filmed over the air station at night? | T7 |
| 2027-09-16 | Are the home-seizure and aid rumours organic? (false claims reported 16 Sept; coordination reported 30 Sept) | T15 |
| 2027-09-18 | How did a hurricane turn into weeks without safe tap water? | T1 |
| 2027-09-19 | Who is behind the emails imitating the aid portal? | T4 |
| 2027-09-27 | How late were the Spanish-language warnings, and did it matter? Did every alert reach every station? | T14, T21 |
| 2027-09-28 | Did every neighbourhood get the same help? | T5 |
| 2027-09-28 | Why did parts of the city lose power again after the storm? (utility statement on cascading failures 28 Sept; federal investigation public 5 Oct) | T8, T11 |
| 2027-10-02 | Why did Districts 3 and 4 lose water pressure two weeks after the storm? What pushed the hospitals past capacity twice? | T9, T16 |
| 2027-10-05 | What did the utility's security team see, and when could it have known? How did it stay hidden? | T18, T10 |
| 2027-10-14 | Which storm claims were never real? (fraud task force announced 14 Oct) | T22 |
| 2027-10-22 | Which vessel was really off Port Aransas on the night of 14–15 October? What did the port's own sensors see? | T2, T12 |
| 2027-10-23 | Where is the GPS interference coming from? | T7 |
| 2027-10-25 | Why did the air station's backup generator fail? Whose fuel was it? | T2 |
| 2027-10-28 | Was the channel blast an accident? | T7 |
| 2027-11-19 | Who took over the aid accounts, and where did the money go? | T4 |
| 2027-12-01 | Do the debris invoices match the debris? Are the debris contractor and the fuel supplier connected? | T3 |
| after 2027-09-29 | Who was flying drones near utility and dock sites before the storm? (federal statement on pre-storm flights 29 Sept) | T19 |

The storyline summaries are in `07_validation/reports/thread_completeness.md` (one row each: beginning, escalation, discovery, resolution, where it becomes public, which streams carry it) and `00_scenario/threads.json`. The full hidden timeline is `00_scenario/canon_timeline.json`; the rulings that settled conflicts between sources are in `00_scenario/canon_decisions.md`.

## 5. Scoring

`06_answer_key/answer_key.json` has, for each of the 22 storylines: the question, a difficulty (easy, medium, hard, expert), the streams involved, the key joins between them, the steps (each naming the records that carry it: stream, files, entity ids, time window), and the conclusion. `python scripts/check_answer_keys.py --only=T1,T2,T3,T4` (run in groups) confirms every step's records exist in the delivered files.

A workable rubric for one finding sheet (see the player brief for the sheet's shape):

| Points | For |
|---|---|
| 0–3 | **Claim** matches the storyline's conclusion (3 fully, 2 the right mechanism with a wrong detail, 1 the right place and time only) |
| 0–3 | **Evidence**: one point per independent stream with correct rows cited, up to three |
| 0–2 | **Chain**: the joins are the right ones (compare `key_joins`) and reproducible |
| 0–1 | **Alternatives**: the ordinary explanation was tested, not just dismissed |
| 0–1 | **Confidence** stated and proportionate |

Multiply by 1, 1.5, 2 or 3 for easy, medium, hard or expert. Credit a correct finding that is not in the key (a real pattern in the background data, well evidenced) as an easy storyline. Deduct for naming a person or organisation as responsible without records that carry it.

The storylines connect (`links_between_threads` in the answer key). A team that shows a connection between two of them, with rows, has done the hardest thing in the exercise; score it as an expert finding.

## 6. The map viewer

Open `09_shared_state_timeline/viewer/map_view.html` in a browser, with the `map_data/` folder beside it. It needs an internet connection for the map library and the satellite imagery; without imagery it falls back to a chart drawn from the reference geography.

It shows every logged vessel, aircraft and response vehicle on its recorded track, incidents, sensors with live readings, outages, alerts, the storm, and events, at 15-minute steps. The perspective switch matters: **Truth** shows hidden events and roles and is for you; **Public** and **Civilian** show only what those audiences could have known. Do not project the Truth view.

The viewer is for the game master and is not in the participant package.

## 7. Before the event: the gates

Run these and expect PASS from each. Long ones are written to be repeated until they finish.

```
python scripts/build_all.py                       narrative pipeline, expected observations, answer keys, graph, RSS, release
python scripts/check_acceptance.py                the ten narrative criteria and the file lock
python scripts/check_streams.py --only=<streams>  every stream against the timeline (run in groups; 357 observations in all)
python scripts/check_entities.py                  every id in every stream is in a registry
python scripts/check_geo.py --resume              repeat until "COMPLETE - PASS": every position against real geography
python scripts/check_answer_keys.py --only=T1,T2,T3,T4     in groups
python scripts/check_thread_completeness.py
python scripts/check_map.py                       the map's data: no vessel on land, no moving vehicle off a road
python 10_news_sites/newsroom/tools/verify_gating.py
python scripts/build_delivery.py --resume         the participant package and its leak checks
```

`07_validation/ACCEPTANCE.md` defines each gate. `07_validation/independent_audit/REPORT.md` is the outside audit of the data against the timeline.

## 8. After a change

Never edit a file under `05_other_sources/` by hand. Streams are produced by the generators in `scripts/streams/` from the canon timeline and the registries, and they are deterministic: the same inputs give the same files.

1. Change the source of truth: the timeline, public record or events (`00_scenario/`, `02_public_record/`), a registry (`06_data_streams/`), or a story batch (`03_news/stories/`).
2. Re-run the generators for the streams the change touches (`python scripts/streams/gen_<family>.py`; some run in parts).
3. `python scripts/build_all.py`, then the gates in section 7.
4. `python scripts/build_map.py --resume` until COMPLETE, then `python scripts/check_map.py`, if positions changed.
5. `python 10_news_sites/newsroom/build_data.py` (the server also rebuilds at start) and `verify_gating.py`, if stories changed.
6. `python scripts/build_delivery.py --resume`, and re-copy the package.
7. `python scripts/snapshot.py --lock` to record the new state; `check_acceptance.py` should then report PASS.

The exact order for canon and registry changes is at the end of `07_validation/ACCEPTANCE.md`.

## 9. On the day

- Start the newsroom, set the clock to the opening date, open the control page and the explorer.
- Hand out the package (or stage 1) and the newsroom address. Ask teams to read the player brief first.
- Advance the clock at a pace that leaves time to work: the two weeks around landfall deserve the most wall-clock time.
- Post focus questions as their dates pass (section 4).
- If a team reports something that looks like an answer file, or a way to read ahead, thank them and fix it; the builder and `verify_gating.py` should have prevented both.
- Collect finding sheets; score with section 5.
