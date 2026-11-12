# Writer guide: Hurricane Rafael news feed

You are writing fictional local and national news coverage for a synthetic-data exercise. The coverage spans scenario days -60 to +119, where day 0 is landfall of Hurricane Rafael on Mustang Island near Port Aransas, Texas. Your batch covers only the days you are assigned.

## Read first (project root = this folder's parent)

1. `00_scenario/scenario_bible.md`: the full ground truth, for context only. Most of it is secret.
2. `02_public_record/public_record.json`: the only facts news may report, each with the day it becomes public.
3. `02_public_record/restricted_terms.json`: names and patterns that must not appear, or only appear from a given day.
4. `01_characters/characters.json`: every person who may appear, with their voice, knowledge timeline and arc beats.
5. `01_characters/outlets.json`: seven fictional outlets with staff, sections and style.
6. `03_news/arcs.json`: storylines used for tagging.
7. `03_news/coverage_targets.json`: how many stories each day needs.
8. `03_news/story_schema.json`: the exact JSON shape.

Run `python3 scripts/dates.py <start> <end>` to get the calendar date, weekday and time zone for each day.

## Hard rules

- **Public only.** Every material fact must come from a public_record fact whose `day` is on or before the story's day, and the story must list those PUB ids in `tags.public_facts`. Never report something before it is public, and never reveal anything in `never_public`.
- **No leaks.** Never use the dark tanker, the fuel barge, KESTREL, the foreign state's identity, internal IDs or day notation (D+12, D0) in headline, dek or body. Use dates ("Tuesday", "Sept. 14") or relative wording ("two weeks after landfall").
- **Never name a country** for the overseas power: say "a foreign government" or "an overseas power".
- **People.** Quote only public-facing characters from `characters.json`, in their voice, and only about what they would know by that day. Never name or quote real elected officials or agency heads; say "county officials" or quote the fictional spokesperson. Do not invent new named people. If you truly need one, use an unnamed description ("a nurse who asked not to be named").
- **Bylines.** Use only that outlet's staff, and follow the outlet's style and word range. Every article is 250-450 words, in at least 3 paragraphs.
- **Allegations.** Use the public record's careful wording ("records show", "the company denies", "charges are allegations"). Do not accuse anyone beyond what the public record states.
- **Real and fictional.** Places, agencies, bases, the port and infrastructure are real. Companies, outlets and people are fictional. Numbers are scenario values from the public record.
- **Color is allowed, invention is not.** You may add harmless local color: weather, a high school game, a fish fry, a line at a store, what a street looks like. You may not invent new incidents, causes, numbers, arrests, statements by real officials, or anything touching the hidden threads.

## Making it a rich world

- Mix outlets and story types: breaking, update, feature, explainer, profile, analysis, fact-check, brief, opinion. Opinion pieces are by an outlet's staff, clearly labeled, and still only use public facts.
- On quiet days, build the world: profile recurring residents (Rosa Elizondo, Huy Nguyen, Bill Hargrove, Pastor Gloria Whitfield, Leticia Ramos), port and base life, preparedness, and the economy, so later stories pay off.
- Follow characters' `arc_beats` and keep their details consistent (ages, jobs, neighborhoods).
- Thread stories together: use the same arcs, refer back to earlier coverage ("as the Ledger reported Monday"), and set `tags.follows_up` to the earlier story id when one story directly follows another in your batch.
- Vary angles across outlets on big days: the TV site is fast and practical, public radio explains, the trade press is technical, the wire is national, the base weekly speaks to families.

## Output

1. Write `03_news/stories/batch-<X>.json` as `{"batch": "<X>", "day_range": [start, end], "stories": [...]}`, sorted by day and time. Story ids follow `NWS-M045-01` (day -45) or `NWS-P012-02` (day 12), numbered per day starting at 01.
2. Write `03_news/character_updates/batch-<X>.json` as `{"batch": "<X>", "updates": [{"character_id", "day", "story_id", "note"}]}`, one note per meaningful appearance: what they said or did, and any new detail (for example "Rosa's youngest is 6").
3. Build the JSON with a Python script that uses `json.dump(..., ensure_ascii=False, indent=2)`, so quotes and accents are escaped correctly. Keep your script in /tmp, not in the project folder.
4. Run `python3 scripts/validate.py 03_news/stories/batch-<X>.json` from the project root. Fix every ERROR and keep WARNs few, then rerun until there are 0 errors.
5. Do not edit shared files (characters, public record, arcs, scripts). If you find a conflict or a missing fact you need, describe it in your final report instead.
