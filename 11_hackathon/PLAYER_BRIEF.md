# Player brief: Hurricane Rafael

## The setting

It is late summer 2027 on the Texas Coastal Bend. Corpus Christi is a working port city: one of the country's busiest crude oil export channels, a naval air station, an Army helicopter depot, a public utility that runs both power and water, and about a third of a million people living between the bay and the barrier islands.

A hurricane named Rafael is on its way. It comes ashore near Port Aransas in the early hours of Tuesday, 14 September 2027. Everything in this exercise is measured from that day: the weeks of ordinary life before it, the landfall, and about four months of response, recovery and investigation after it.

You are analysts. Your team supports the people running the response and, later, the people trying to work out what happened and why. You have what such a team would have: sensor feeds, logs, registries, public alerts, official statements, social media, and the local news.

The places are real. The people, companies, vessels, agencies' staff, news outlets and events are fictional.

## What you are asked to do

Build tools that find and explain what happened, using the data.

That is deliberately open. Good work in this exercise looks like one or more of these:

- **Timelines.** Reconstruct the sequence of events in a place, a system or an organisation from records that were never meant to be read together.
- **Anomalies.** Separate what is ordinary for this city from what is not. The weeks before landfall are there so you can learn what ordinary looks like.
- **Links across sources.** Follow one thing, a vessel, a vehicle, a neighbourhood, an account, a piece of equipment, across feeds that describe it in different ways.
- **Explanations.** When something goes wrong, say what the evidence supports about the cause, what it rules out, and what it cannot tell you.
- **Who was served.** Compare how the response reached different neighbourhoods and language communities, using the records and the census tables together.
- **Decision support.** Summaries, maps, alerts or question-answering that a duty officer, an investigator or a reporter could use under time pressure.

The game master will post focus questions as the exercise clock advances. You are also free to follow anything in the data that looks worth explaining. A storm does plenty of damage on its own; part of the work is telling storm damage from everything else.

## What you receive

- **The data package.** See `DATA_GUIDE.md` for every stream and how they join, and `DATA_TABLES.md` for exact file names, time spans and columns. The game master decides whether you receive the whole period at once or in stages.
- **The news.** Eight local, trade and national outlets publish on the exercise clock through the newsroom web server. You can read the sites, subscribe to RSS, or pull stories from the API. A story appears when it is published in the exercise, not before.
- **Reference geography.** Real channels, shoreline, roads and landmark points for the area, so that positions can be put in context.

## Rules of engagement

1. **Use what you are given.** The package, the newsroom and anything you build from them. Do not go looking for the exercise's design files; if you are handed something that looks like an answer sheet, tell the game master.
2. **The news is on a clock.** Take stories from the newsroom as they are released. Do not try to read ahead by guessing addresses or probing the server; it will not work, and it is against the spirit of the exercise.
3. **Poll gently.** No more than one request every 15 seconds per tool against the newsroom.
4. **Evidence first.** A finding with no rows behind it is an opinion. Cite the records.
5. **Treat names as you would in real work.** Naming a person or a company as responsible for something is a serious claim. Make it only when the records carry it, and say how sure you are.
6. **Data stays in the exercise.** The dataset is for this event and for learning. Do not present it elsewhere as real.
7. **Any tools, any models.** Bring what you like. Say what you used, and be ready to show that a result can be reproduced from the files.

## How to report a finding

One finding per sheet, in this shape:

| Part | What goes in it |
|---|---|
| **Claim** | One or two sentences. What happened, where, when, involving what. |
| **Evidence** | The rows that support it. For each: file, the record's id or key, the time stamp, and the value that matters. Enough that someone else can open the file and find the same row. |
| **Chain** | How the rows connect: which id joins which file to which, and what each step adds. |
| **Alternatives** | The ordinary explanation you considered (storm damage, sensor failure, clerical error, coincidence) and why the evidence does or does not fit it. |
| **Confidence** | High, medium or low, and what would change your mind. |
| **So what** | Who needs to know, and what they could do with it. |

Times in findings should be UTC, with the local time alongside where it helps a reader.

## What "done" looks like

There is no single finish line. A strong submission has:

- a tool or method that someone else could run again on the same files and get the same answer;
- several findings in the shape above, each resting on at least two independent sources;
- at least one finding that needed a join across different kinds of data (for example a position feed with a log, or a public statement with a sensor);
- an honest account of what the method misses or gets wrong;
- a short demonstration aimed at a person who has to act on it, not at another engineer.

Judges will ask "show me the rows" and "what else could explain this". Prepare for both.

## A note on ethics

This is a training exercise built for education. The storm, the people and the events are invented; the geography is real so that the problems feel real. Some of the material is about hardship: people waiting for help, illness, damaged homes. Some of it may point to wrongdoing. Treat it with the care you would give the real thing, because the skills carry over, and so do the habits.
