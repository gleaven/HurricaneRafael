# Coastal Bend Newsroom — game master guide

Eight fictional news sites for the Hurricane Rafael exercise, released story by story on a
scenario clock that you control. Nothing ahead of the clock ever reaches a browser, an RSS
reader or the API, so participants cannot read ahead by viewing page source.

## Requirements

Python 3.8 or newer. Nothing else to install. The folder must stay inside the
`News Stories` corpus so the server can rebuild its data at start; if you copy only the
`newsroom` folder elsewhere, it runs from the cached files in `data/`.

## Start it

| Where | Windows | Mac / Linux |
|---|---|---|
| This computer only | double-click `start_newsroom.bat` | `./start_newsroom.sh` |
| Shared network | double-click `start_newsroom_lan.bat` | `./start_newsroom.sh --lan` |

Or run `python server.py` / `python server.py --lan` yourself. Other options:
`--port 8090`, `--passphrase "your phrase"`, `--reset` (start the clock over).

The window prints the addresses to use:

- **Control page** `http://localhost:8080/control` (you)
- **Corpus explorer** `http://localhost:8080/explorer` (you)
- **Newsstand** `http://localhost:8080/` (everyone)
- With `--lan`, the address participants type, such as `http://10.0.0.25:8080/`

Leave the window open while the exercise runs. Ctrl+C stops the server.

**Windows firewall:** the first `--lan` start may ask whether Python can use the network.
Allow it on private networks, or participants won't be able to connect.

## Passphrase

- On the computer running the server, /control and /explorer open without a passphrase.
- From any other computer they ask for one. With `--lan`, the server makes one up the first
  time (for example `pelican-jetty-417`), prints it in the window and saves it in `config.json`.
- Set your own with `--passphrase`, or edit `gm_passphrase` in `config.json` and restart.
- To require it even on this computer, set `"local_gm_without_passphrase": false`.

## What participants use

- **Newsstand** (`/`): the eight outlets, how many stories each has published and the latest
  headline. Each site has a home page, sections, full articles and a searchable archive.
- **Data feeds** (`/feeds`): instructions for team tools. JSON at `/api/articles` and
  `/api/outlets`; RSS at `/<outlet>/rss.xml` and `/rss/all.xml`. Teams are asked to poll no
  faster than every 15 seconds.

Open pages update on their own: new stories slide in with a NEW badge and a toast, dates tick
forward, and alert banners, port status and on-air status change with the clock.

## Control page

- **Clock:** scenario time in D-notation (D0 = landfall day) and local time. Only you see
  D-notation; participants see ordinary dates.
- **Play / Pause** with speeds of 1 min, 10 min, 1 hour, 6 hours or 1 day per second.
- **Step** −1 h, +15 min, +1 h, +6 h, +1 day, and **Next story** (jumps to the next publish
  time). Each outlet card also has its own **Next story**.
- **Timeline:** stories per day (filled bars are published) with milestone marks. Drag and
  release to move the clock.
- **Milestones:** click to jump to just before a key moment (warning, landfall, boil-water
  notices, the jetty blast, the attribution).
- **Up next:** the next stories in order, with **Release now** to publish one early.
- **Hold** an outlet to freeze it; its stories queue up and all appear when you **Resume**.
- **Pause automatically when a breaking story drops** stops play at each breaking story.
- **Release log:** everything that was published, when and why.
- **Reset** asks once more, then returns to the scenario start and clears holds and early releases.

Keyboard: `Space` play/pause · `→` +1 h · `Shift`+`→` +1 day · `←` −1 h · `N` next story.

Going backward is allowed: pages roll back and stories after the clock disappear again.

## Corpus explorer

Every article regardless of the clock. Filter by outlet, type, storyline, words, day range
and published/upcoming. Views: **List** (sortable), **Day** (each outlet side by side) and
**Storyline** (one thread across outlets). The reader shows the full text, internal ids,
people, places, topics and related stories; **Set clock to this story** moves the exercise
there. **Download filtered JSON** saves what you're looking at.

## The clock persists

The clock, holds, early releases and log are saved in `state/clock.json`. Restarting the
server resumes where you left off. Use `--reset` or the Reset button to start over.

## Before the exercise

Run `python tools/verify_gating.py`. It starts a throwaway server (your saved clock and
config are untouched), jumps to every milestone, crawls every public page, feed and API
response, and fails if anything ahead of the clock, any internal id or D-notation, or any
restricted name before its public day shows up. It also checks holds and the passphrase.

## After the corpus changes

The server rebuilds its data from `08_release/news_stories_public.json` every time it starts.
To rebuild without restarting the exercise, run `python build_data.py`, then restart.
The build refuses any story that names something before the public record allows it
(`02_public_record/restricted_terms.json`) and prints what it held back.

## Folder

```
server.py          the server (clock, sites, feeds, game-master API)
build_data.py      compiles data/ from the corpus
nr/outlets/        one template per outlet
nr/portal.py       newsstand, feeds and not-found pages
static/            live updates, control page, explorer
tools/preview.py   renders outlet pages at fixed times for template work
tools/verify_gating.py  end-to-end leak check (run before an exercise)
data/  state/      generated: compiled articles, saved clock
```
