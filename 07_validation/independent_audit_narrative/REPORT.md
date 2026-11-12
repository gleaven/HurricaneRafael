# Independent narrative audit - canon decisions

Auditor run of 2026-11-10. Nothing outside this folder was changed.

## Method and coverage

- Read first: `00_scenario/canon_decisions.md`, `canon_timeline.json` (all topic blocks), all 177 public facts in full, restricted_terms, quantity_rules, all 182 MSEL event descriptions (first 300-1,400 characters each), the character list.
- Read in full: story batches I, J, K, L and P (79 stories; the later-thread tie-in stories) except three Gulfwater items in batch J (NWS-P012-04, P016-03, P020-03) that I only scanned. These batches hold almost every defect.
- Batches A-H, M, N, O (578 stories) were NOT read end to end. They were checked by sentence extraction per topic (spill, barrels/gallons, AIS, drones, boil-water, port movement, FEMA registration, 911, rescues, deaths, outage, dollars, structures, curfew, sessions, districts, names, weekdays, event dates). A contradiction phrased without any of those keywords could have been missed there.
- Thread designs and answer keys: pattern searches only (removed names, old numbers, dates), not read in full.
- `08_release/news_stories_public.json`: 657 stories, same ids, headline and body identical to the batches (compared by script), so every story defect below is also in the release copy.
- Scripts in this folder: `common.py`, `s01_restricted.py`, `s02_numbers.py`, `s03_times.py`, `s04_dates.py`, `defects_data.py`, `build_report.py`.

## Verdict by area

| # | Area | Verdict |
|---|---|---|
| 1 | Oil spill | **PARTIAL** |
| 2 | Dark vessel / AIS | **PASS** |
| 3 | Drones | **PARTIAL** |
| 4 | Boil-water notices | **FAIL** |
| 5 | Port and channel | **PASS** |
| 6 | Numbers | **FAIL** |
| 7 | Federal aid | **FAIL** |
| 8 | Published times | **FAIL** |
| 9 | Names | **FAIL** |
| 10 | MSEL and thread designs | **PARTIAL** |
| 11 | Storyline continuity | **FAIL** |

### 1. Oil spill - PARTIAL

The canon spill holds everywhere I looked: every 'barrels' statement in the 657 stories is 'about 9,000' (script s02/barrel scan, 100+ sentences, first on D+1), always the two named tankers at the Rendal Terminals berth / Inner Harbor, 'as the storm arrived'. No story, fact or event names another vessel, another volume, gallons for the release (142,000 gallons is recovered oil-water mix, PUB-194), a second spill, an anchorage spill or a pier attack; 'Auriga', 'Meridian Star/Marine', 'Costana', 'Pier 9' occur nowhere in stories, public record, MSEL, threads, designs, characters or answer keys. EVT-1205 explicitly rules out a third vessel.
Defects: NWS-P002-10/-11 describe 'the oil discharge confirmed in Corpus Christi Bay earlier in the day' with readings 'near the La Quinta Channel' (reads as a different discharge and place); PUB-190 ('water supply remains uninterrupted') and PUB-195 ('within all regulatory parameters for 52 consecutive days') contradict the water-plant storyline (D35). PUB-193's '$4.2 million' fund ceiling and PUB-099's '4,200 claims' are easy to confuse but not contradictory.

### 2. Dark vessel / AIS - PASS

No story before D+38 mentions an AIS anomaly, spoofing, a dark or unidentified vessel (only generic AIS explainers on D-60..D-24). 'Halcyon Drift' and 'Barge 44' never appear in public text; 'Pelican Ridge' first appears D+38. The restricted-term and pair rules re-run clean (three allowlisted pair hits checked by reading: NWS-P091-01, P107-01, P116-01 are fine).
Note (D53): the drone thread keeps a support vessel 'Narwhal Dream' with its own front company (Nereid Maritime Holdings) in the MSEL, T19 design, answer key and canon_timeline. It is never public, but it is a second suspicious vessel next to the 'only' one in decision 2.

### 3. Drones - PARTIAL

Base corpus is consistent: lights over the air station from D+2, NAS statement D+6, FBI D+9, 'no new sightings' D+11 (NWS-P011-01), nothing later, no port/pier drone around D+30, pre-storm flights first public D+15/D+16. 
Defects: NWS-P015-04 says 'two ... sorties' and gives dates although PUB-181 withholds number and timing and canon has five (D19); NWS-P032-05 (D+32) calls the pre-storm flights 'the first public disclosure' 17 days after they were disclosed and says the detection network is 'now deployed' with interdiction (D22). PUB-181 asks for tips for 'September 4 and September 12' while the decision says D-10 to D-3 (Sept. 4 to 11), and the first sortie is 23:30 on Sept. 3 local.

### 4. Boil-water notices - FAIL

Base corpus (batches A-H, M, N, O): citywide notice Sept. 18 to Oct. 23, '35 days' / 'five weeks' (NWS-P039-01, P041-02, P043-01, P047-05, P085-02, P087-02, P090-04, P091-01, P107-01, P110-01/-50/-60, P119-01, P119-60) - all correct for the citywide notice. Districts 3/4: Sept. 26 5:30 p.m., 6:03 a.m., lifted Oct. 26, '30 days' (NWS-P042-04/-05, GW-PUB-007) - correct. No story says 'Zone 1/2' or a D+30 lift.
Failures: NWS-P012-06 says the rest of the city 'is unaffected and meets all ... safety standards' and calls the notice the most significant since 2008, eight days into the citywide notice (D07); NWS-P040-04 puts the Districts 3/4 notice 'in its 40th day' on D+40 (D08); PUB-134 on D+45 speaks of the notice as still running (D16); 'Zone 4' appears in GW-PUB-001, GW-PUB-007 and 20 story sentences (NWS-P012-06, P012-07, P018-02, P023-04, P036-04, P040-04, P042-04, P042-05) (D42); NWS-P042-04/-05 put a cyber-investigation line into the lift notice (D26); NWS-P029-05 'safe for boiled use in Districts 3 and 4' ignores the citywide notice; NWS-P040-01/P041-02 forget Districts 3/4 are still boiling (D46). District geography, population wording, boil time (1 vs 2 minutes), phone numbers and distribution sites differ between PUB-143, PUB-204, PUB-132 and the stories; KNCB receipt time is 05:58 / 06:00 / 06:03 (D43).

### 5. Port and channel - PASS

Scanned every sentence about the channel, ships, loading and exports on D+1..D+29 and D+44..D+57 for movement or reopening: none. X-Ray/Yankee/Zulu on D-3/D-2/D-1, partial reopening Oct. 14, blast 'around 1 a.m.' Oct. 28 (first story 03:20), second device Nov. 5, reopening Nov. 11 '14-day closure' are consistent in stories, facts and MSEL; date-keyword script s04 found no wrong date. Loadings restart D+32 and halt again D+44/46, consistent with PUB-073. No story moves the two tankers.
Small: NWS-M002-08 gives the port a second 'chief of operations' and real terminal names (D39).

### 6. Numbers - FAIL

Table of what is stated (stories and facts), by day:
- 911: D0 08:00 'about seven times normal' (PUB-130); D0 08:30 '1,840 calls in 24 hours' (NWS-P000-10 - impossible at that hour, D14); D+1 'about 2,900 a day, nearly ten times normal' (PUB-026 and 20+ stories; reported at 07:00 on D+1, D45); D+3 2,900 Wed / 2,109 rescue requests Thu / 1,100 landfall day / 7,300 in three days (PUB-131, NWS-P003-07 - superlative clash, D31); D+29 380 a day, 44,200 in four weeks (PUB-133) vs 'baseline ~310' (NWS-P029-04); D+45 'more than 56,000' (PUB-134) vs 'más de 55,000' (NWS-P045-60).
- False calls: 11 (PUB-174) vs 23 at utility sites (NWS-P010-06) vs 23 'non-existent shelters' (NWS-P029-04, P032-04, P038-04, P045-08) (D12).
- Rescues: 486 total / 341 by air / 180 hoists at D+1 15:00 (PUB-170); '47 rooftop rescues' D+1 16:00 (NWS-P001-08); 702 D+2; 1,427 D+5; final 341 hoist / 1,041 surface / 45 (PUB-173) vs '47 hoist' (NWS-P005-06, P007-05) (D10).
- Deaths: 12 at D+1 09:00 (PUB-203); 23 on D+2 (NWS-P002-09, P005-06, P007-05); 'Two fatalities were recovered' (PUB-172). No base-corpus story gives a toll.
- Outage: 'more than 72,000' D+1; 'final 32,000' D+14 (GW-PUB-002; NWS-P014-04 drops it and reverses the quote, D18); 'final 3,200' D+35. Hidden curve 36,000 at D+28 > 32,000 at D+14 (accepted open item).
- Flood area 43 sq mi, sheen 33 sq mi: consistent.
- Damage: 4,200-5,800 structures (PUB-111) vs '14,200 structures', '340 destroyed', '$2.1 to $2.4 billion' (NWS-P004-08, D11). Insured losses $2.1 billion / 187,000 claims at D+30: consistent (NWS-P030-07, P030-08, P119-03); '$3.8B / 142,000 claims' survives in the T22 design (D37).
- Illness: 'more than 600' D+18 (PUB-162) vs '148' on D+18 and D+21 (D13); '1,820' printed on D+23 and D+42, before the D+60 report; hospital total 4,217 (PUB-164) vs '4,847' (NWS-P060-04, D09).
- Bilingual lag 12 h 33 min vs '24-hour' (NWS-P060-04, P119-03, T16 design).
- Shelters: no counts stated anywhere.

### 7. Federal aid - FAIL

PUB-141, PUB-142, PUB-212, PUB-103, PUB-104, PUB-105, PUB-081 and the base corpus are consistent (information line only; approved Nov. 10; registration Saturday Nov. 13). 
Failures: NWS-P057-03 ('Survivors Can Register Beginning Today') and NWS-P057-04 (recovery centres open, residents 'can apply') on D+57, contradicted the same day by NWS-P057-02 and NWS-P057-05 (D01, D02); NWS-P025-04 has 'registered applicants' on D+25 (D03); NWS-P090-06 has 94 FEMA applications filed 'between Rafael's landfall and Day 50' (D04); four stories say a '43-day' wait (it is 57). PUB-205 (D+21) offers 'additional disaster assistance' to residents (D51).

### 8. Published times - FAIL

Mechanical check (s03): no story cites a fact from a later day or an earlier time on the same day; eight stories carry exactly the fact's minute (D44). Restricted terms: clean.
Reading finds what the tags hide: NWS-P000-10 reports the landfall-day 911 total at 08:30 (D14); NWS-P001-10/-02 report the D+1 peak at 07:00/08:30 on D+1 (D45); NWS-P023-04 prints the final 1,820 on D+23 and cites a 'Thursday afternoon' release at 11:30 (D13); NWS-P030-08 and NWS-P040-04 name 'Operation Sandbar' on D+30/D+40 (public D+90, D21); NWS-P015-05 names FastDry Coastal on D+15 (public D+90, D20); NWS-P010-06 prints the hidden 23-call campaign on D+10 (D12); NWS-P012-07 (18:10) cites the NuecesInfoLine created at 19:00 (D30); NWS-P021-04 says 7:00 a.m. for a noon statement (D34); NWS-P045-09 reports the vote at the minute the hearing starts (D25). Harborline, Gulfwater, Sabal and Anchor & Rotor publish during the hours canon says they are off line (D28). Day-count notation ('Day 28') in five stories (D52).

### 9. Names - FAIL

Real names in participant text: 'AEP Texas' (NWS-P001-09, D05), 'South Texas Blood and Tissue Center' (PUB-161, D47), 'La Quinta Terminal Complex' (NWS-M002-08), 'Biden-era' (NWS-P028-04); 00_scenario/assets.json also carries 'AEP Texas' (internal). 'GridWater' is absent from stories and the public record. 'Fort Cavazos' once (NWS-P002-08) against 97 'Fort Hood' (D17). Wrong utility name 'Corpus Christi Bay Port and Water Authority' (NWS-P119-03, D06). FBI division: San Antonio in PUB-210 and NWS-P003-08, Houston everywhere else (D27). Two port operations chiefs (D39). Elena Vasquez-Okafor works for the fire department in the facts and for the 911 centre in characters.json and two stories (D40). Organisation name variants for the 911 centre, the health district, the water utility and CBPWA's Spanish name (D48). Disaster number: DR-4890 still in msel.json and the T22 design. Weekday/date pairs: all 'Weekday, Month DD' strings in stories and facts check out against the 2027 calendar; relative weekdays also plausible.

### 10. MSEL and thread designs - PARTIAL

No orphan of the second spill, the pier attack or the D+30 drone loiter remains in msel.json, threads.json, the 12 designs or the answer keys; scenarios/gridwater/00_scenario/msel.json is empty ('[]').
Contradictions that remain: two overlapping false-call campaigns (EVT-1303/1304, 23 calls; EVT-1707, 11 calls) against one public fact (D12); EVT-1403 tells Zones C-E to shelter in place six hours after Zone C was ordered out, and mentions a D-1 curfew (D36); zone schemes A-C / A-D / C-E; EVT-1410 calls D+30 'the first simultaneous bilingual public alert' although PUB-201, PUB-202 carry Spanish text and the T21 design says the D-1 order was bilingual; T22 design keeps '$3.8B' and DR-4890 (D37); T16 design keeps the '24-hour' lag (D38); PUB-113 vs EVT-1108 (D32); PUB-200 vs canon forecast (D41); smaller day and id mismatches (D50).

### 11. Storyline continuity - FAIL

Things that un-happen or happen twice for a reader: Rafael is a hurricane on D-6 and a 70-mph tropical storm again on D-3 (D15); FEMA registration opens on D+57 in two stories and on D+60 in all others (D01-D02); the FEMA cyber team and declaration amendment are announced on D+21 and again as new on D+28 (D23); deliberate interference is official on D+21 and an 'exclusive' revelation on D+45 (D24); pre-storm drones are disclosed on D+15 and 'for the first time' on D+32 (D22); rescues end 'Thursday' yet the count doubles by Sunday, and helicopters first fly Wednesday in one outlet and Tuesday 1:22 a.m. in the record (D10); the false-shelter posts move from before landfall to after it (D33); KNCB both did and did not warn listeners on the night of Sept. 26 (D25); the 911 false calls have three descriptions (D12).
The original storylines (spill, port, channel attack, contracts, aid fraud, influence posts, fishing closures, brigade move) read consistently across outlets from D-60 to D+119.

## Decisions not covered by a numbered area

- Evacuation (Zone A D-2 06:00; Zones B/C 07:00 D-1): stories and PUB-021/PUB-201 agree. Conflicts are PUB-200 'zones A through D' and EVT-1403 'Zones C-E' (D36, D41).
- Insured losses $2.1 billion: consistent in public text; '$3.8B' only in the T22 design (D37); NWS-P004-08 invents a '$2.1 to $2.4 billion' damage figure on D+4 (D11).
- Outage peak 72,000: consistent ('more than 72,000', PUB-203, NWS-P001-09).
- Tankers held at the berth to D+62: no story moves them; not mentioned in news after D+16 apart from recaps.
- Five water districts: 'Districts 1 through 5' in PUB-203, PUB-205; EVT-1103 says 'districts 1 through 6' (D50).
- Remote sessions 7 / 14: not in public text; MSEL gives the window as both 'D-7 to D+16' and 'D-7 to D+18' (D50).
- Curfew D+1 to D+21: only PUB-203 mentions it; no story does (the story written from PUB-203, NWS-P001-09, omits it); EVT-1403 has a 22:00 curfew on D-1 (D36).

## Ranked defect list

### Blocker

**D01** (area 7) - NWS-P057-03  
File: `03_news/stories/batch-L.json`  
Text: headline 'Survivors Can Register Beginning Today'; 'opens registration immediately'; '43 days after Rafael made landfall'; 'nearly six weeks'; 'Day 28'; 'since Day 2'  
Fix: Rewrite to PUB-105: approved Wed Nov. 10 (57 days / eight weeks after landfall); 'registration opens Saturday, Nov. 13'; recovery centers open Saturday; replace 'Day 28'/'Day 2' with dates. Same-day stories NWS-P057-02 and NWS-P057-05 already say Saturday.

**D02** (area 7) - NWS-P057-04  
File: `03_news/stories/batch-L.json`  
Text: 'Six Weeks On'; 'one of FEMA's three new Disaster Recovery Centers was opening its doors for the first time' (Wed D+57); 'Eligible residents can apply at DisasterAssistance.gov'; 'the 43-day interval'; 'until Day 28'; MLK Drive centre later called 'the Ayers Street center'  
Fix: Retitle 'Eight weeks on'; people queue for information, registration opens Saturday Nov. 13; '57-day interval'; remove Day-N notation; one centre address.

**D03** (area 7) - NWS-P025-04  
File: `03_news/stories/batch-K.json`  
Text: 'the number of registered applicants has outpaced inspection capacity'; 'homeowners navigating simultaneous insurance, FEMA and Small Business Administration applications' (D+25)  
Fix: No FEMA registration exists before D+60. Replace with: joint FEMA-state damage assessment teams are behind; households cannot apply yet (state asked for Individual Assistance this week, PUB-104).

**D04** (area 7) - NWS-P090-05 / NWS-P090-06 / NWS-P090-07  
File: `03_news/stories/batch-L.json`  
Text: 'the 43-day delay in FEMA IA approval' (x3); P090-06: '94 fraudulent FEMA Individual Assistance applications ... between Rafael's landfall and Day 50'; 'FBI Houston Division' (PUB-210: San Antonio Division); '128 fraudulent water-damage claims'; 'indictment' vs complaint  
Fix: '57-day wait'; applications filed 'in the first days after registration opened Nov. 13' (EVT-2206); drop 'Day 50'; one FBI division (see D27).

**D05** (area 9) - NWS-P001-09  
File: `03_news/stories/batch-I.json`  
Text: 'AEP Texas crews are staged outside the affected areas'; outage figure sourced to 'the state utility reporting network'  
Fix: Real utility name, and not the scenario utility. Replace with 'Coastal Bend Power and Water Authority crews'; source 72,000 to CBPWA as in PUB-203. Story also omits the 12 deaths and the curfew that PUB-203 carries.

**D06** (area 9) - NWS-P119-03  
File: `03_news/stories/batch-L.json`  
Text: 'The Corpus Christi Bay Port and Water Authority has implemented ...'; 'The 24-hour gap in bilingual emergency alerts'; 'Operation Sandbar brought 14 convictions and $4.7 million in restitution' (29 days after the arrests); utility cyberattack described by federal authorities as 'the work of a sophisticated threat actor with possible foreign-state ties'; 'a Calallen homeowner' on Lipan Street in District 3  
Fix: 'Coastal Bend Power and Water Authority'; 'the 12-hour gap'; '14 arrests; the case is pending'; delete the foreign-state line (public attribution on D+112 covers only the tankers and channel devices, PUB-097; utility attribution is never public); fix place.

**D07** (area 4) - NWS-P012-06  
File: `03_news/stories/batch-J.json`  
Text: 'The city confirmed that water outside Zone 4 — including Districts 1, 2, and 5 — is unaffected and meets all state and federal safety standards'; 'the most significant water quality action in the city since Hurricane Dolly in 2008'; 'Zone 4 distribution system' (x4); districts described as 'portions of Calallen, Violet'  
Fix: Citywide notice has been in force since Sept. 18 (D+4). Replace with 'the rest of the city remains under the citywide notice issued Sept. 18; the new notice adds a separate low-pressure warning for Districts 3 and 4'. Delete 'Zone 4'. Use the PUB-143 boundary.

**D08** (area 4) - NWS-P040-04  
File: `03_news/stories/batch-K.json`  
Text: 'For families in Districts 3 and 4 ... the boil-water notice remained in its 40th day' (D+40); 'Operation Sandbar — the FBI and TDI joint fraud investigation announced Oct. 14'; 'Zone 4'  
Fix: Districts 3/4 notice began Sept. 26: 'its 28th day'; add that the citywide notice was lifted Saturday. Remove the Sandbar name (not public until D+90; EVT-2204).

**D09** (area 6) - NWS-P060-04  
File: `03_news/stories/batch-L.json`  
Text: '4,847 patient encounters'; 'four-month internal review'; 'between landfall and Day 60'; '1,820 ... between Day 15 and Day 32'; 'documented 24-hour delay in bilingual alert distribution'; 'approximately 24 hours after English-language outlets'; 'Day 5'  
Fix: PUB-164: 4,217 patients, Sept. 11 to Oct. 14; cluster Sept. 29 to Oct. 12; delay 12 hours 33 minutes; remove Day-N notation; 'two-month review'.

**D10** (area 6) - NWS-P001-08 / NWS-P005-06 / NWS-P007-05  
File: `03_news/stories/batch-I.json`  
Text: 'more than 47 rooftop rescues since first light Wednesday'; 'We were wheels-up at first light' Wednesday; '47 specifically documented hoist rescues'; '47 helicopter hoist rescue missions'; 'last confirmed living survivor rescue occurred at approximately 2200 Thursday'; 'wind conditions prevented helicopter operations' for 48 hours; 'ISR-CC-2027-0921'; 'submitted to the Seventh District'; 'through stand-down September 18'; 'Day 4 of operations'  
Fix: PUB-170/173 and canon: first launch 1:22 a.m. Tuesday; 180 hoists and 341 rescued by air by 3 p.m. Wednesday; final 341 by helicopter, 1,041 by surface, 45 contacts; total grows 702 (Thu 6 p.m.) to 1,427 (Sun 5 p.m.) so rescues continued after Thursday; report ISR-2027-CC-004 to District 8; stand-down Sept. 19.

**D11** (area 6) - NWS-P004-08  
File: `03_news/stories/batch-I.json`  
Text: '$2.1 to $2.4 billion in damage to Nueces County; 14,200 structures severely impacted'; '340 destroyed'; survey by 'NOAA National Geodetic Survey aircraft' lidar  
Fix: PUB-111: 4,200 to 5,800 structures with major or severe damage, from eight contracted unmanned aircraft; no dollar total (canon: $2.1 billion insured losses at D+30 is the only total). Remove the dollar range and 14,200/340.

**D12** (area 6) - NWS-P010-06, NWS-P029-04, NWS-P032-04, NWS-P038-04, NWS-P045-08; PUB-174; EVT-1303/1304 vs EVT-1707  
File: `03_news/stories/batch-J.json; batch-K.json; 02_public_record/public_record.json; 00_scenario/msel.json`  
Text: P010-06: '23 calls received between September 21 and September 24 from unregistered prepaid phones ... at or near utility infrastructure'; P029-04/P045-08: '23 calls ... reporting non-existent shelter locations'; P032-04/P038-04: '23 calls to Corpus Christi's 911 center directing residents to non-existent shelters'; PUB-174: 'at least eleven calls ... reported trapped residents ... No further investigation has been announced'  
Fix: Three public versions of one event, and two overlapping hidden events (23 calls, EVT-1303/1304; 11 calls, EVT-1707) in the same window at the same substations. Decide one: e.g. 23 false calls in total of which 11 were dispatched no-find rescues. Stories on D+10 may say only what PUB-174 says; drop 'non-existent shelters' (that is the 211 calls about Zavala Elementary on the day before landfall, PUB-152); 'referred to the FBI' needs a public fact (none exists; PUB-133/134 do not say it).

**D13** (area 6) - NWS-P018-02, NWS-P021-04, NWS-P021-06, NWS-P023-04  
File: `03_news/stories/batch-J.json; batch-K.json`  
Text: P018-02: '148 confirmed cases of acute gastroenteritis in the six days'; 'has not yet identified the specific pathogen'; 'bacterial gastroenteritis ... E. coli'. P021-04/06: '148 confirmed cases' on D+21. P023-04 (D+23): 'made nearly 1,820 people sick'; 'released ... Thursday afternoon' in a story timed 11:30  
Fix: PUB-162 (same day, 30 minutes earlier): more than 600 patients since Sept. 29; Cryptosporidium and Giardia confirmed. 1,820 is the final total first published D+60 (PUB-164) - on D+23 write 'more than 600 by Oct. 2 and rising'.

**D14** (area 8) - NWS-P000-10  
File: `03_news/stories/batch-I.json`  
Text: headline '1,840 calls in 24 hours'; 'handling 1,840 calls in a single 24-hour period, the highest single-day volume in the agency's recorded history' - published 08:30 on landfall day, 7.5 hours after landfall  
Fix: PUB-130 (08:00): 'about seven times normal call volume'. Move the 1,840 day total to a D+1 story.

**D15** (area 11) - NWS-M003-06 / NWS-M003-07  
File: `03_news/stories/batch-I.json`  
Text: 'as Tropical Storm Rafael is expected to intensify'; 'maximum sustained winds stood at 70 miles per hour, just below hurricane strength' (D-3); 'rapid intensification beginning today and continuing through Saturday' (today is Saturday); KNCB: 'ahead of Tropical Storm Rafael'  
Fix: Rafael has been a hurricane since D-6 (PUB-017). 'Hurricane Rafael, forecast to strengthen to a major hurricane'; give a hurricane-strength wind; 'through Monday'.

### Major

**D16** (area 4) - PUB-134  
File: `02_public_record/public_record.json`  
Text: 'The NuecesInfoLine will remain active through the duration of the boil water notice. CBECC thanks the residents of Districts 3 and 4 for their patience during the extended water advisory.' (D+45)  
Fix: Both notices were lifted (D+39, D+42). 'The NuecesInfoLine, opened during the boil-water notices, will close on <date>.'

**D17** (area 9) - NWS-P002-08  
File: `03_news/stories/batch-I.json`  
Text: 'a Texas Army National Guard medical support team was being mobilized from Fort Cavazos'  
Fix: 'Fort Hood' (97 other uses). Also PUB-161 says the request went to DSHS and the National Disaster Medical System, not the National Guard.

**D18** (area 6) - NWS-P014-04  
File: `03_news/stories/batch-J.json`  
Text: 'investigate protective relay conditions that are inconsistent with the mechanical damage caused by the storm'; 'No new estimated restoration date has been given'; headline 'Recovery Stalls'  
Fix: GW-PUB-002 says the opposite: 'protective relay conditions exacerbated by storm debris' and 'the final 32,000 affected customers ... restored within 7 to 10 days'. Quote the fact; add 32,000.

**D19** (area 3) - NWS-P015-04  
File: `03_news/stories/batch-J.json`  
Text: 'two previously uncharacterized unmanned aircraft system sorties'; 'both sorties'; 'between September 4 and September 11'  
Fix: PUB-181 withholds number, place and timing ('multiple incidents'); canon has five sorties. Replace 'two sorties' with 'multiple incidents' and drop the dates (the tip window Sept. 4 to 12 may be given).

**D20** (area 8) - NWS-P015-05  
File: `03_news/stories/batch-J.json`  
Text: headline 'Name FastDry Coastal ... 128 Complaints Filed'; 'more than 128 complaints'  
Fix: PUB-213 names no firm and says 'more than 300 complaints' (KNCB the same day, NWS-P015-60, says 300). FastDry Coastal first becomes public on D+90 (PUB-210). Remove the name or add a public fact.

**D21** (area 8) - NWS-P030-08  
File: `03_news/stories/batch-K.json`  
Text: 'jointly investigating under the name Operation Sandbar'; 'The FBI and DPS did not comment Thursday on Operation Sandbar'  
Fix: EVT-2204: 'The operation name is classified; it will not be made public until D+90.' PUB-214 has no name. Delete the name on D+30 and D+40.

**D22** (area 3) - NWS-P032-05  
File: `03_news/stories/batch-K.json`  
Text: 'disclosing for the first time that retroactive analysis identified unauthorized drone activity'; 'the first public disclosure that aerial surveillance of the facilities may have occurred'; 'systems now deployed include detection, tracking, and ... interdiction'; 'The FAA issued a temporary flight restriction over the port and CBPWA utility facilities in September'  
Fix: Public since D+15 (PUB-181, NWS-P015-04, NWS-P016-40). PUB-182: RF-sensing network by Sentinel Airspace, operational within 90 days, no interdiction; the TFR was the storm TFR (30 nm).

**D23** (area 11) - NWS-P021-05  
File: `03_news/stories/batch-J.json`  
Text: 'FEMA said Tuesday it is deploying a Cyber Rapid Response Team'; 'declaration supplement is expected within 48 hours' (D+21); cites PUB-205 but does not report it; quotes its own correspondent as an expert  
Fix: The team and the amendment are the D+28 news (GW-PUB-005; NWS-P028-04/-05 report them as new). Rewrite onto PUB-205 (joint FEMA/CBPWA statement: outages extended by deliberate interference).

**D24** (area 11) - NWS-P045-10 / GW-PUB-104  
File: `03_news/stories/batch-K.json; 02_public_record/public_record.json`  
Text: 'EXCLUSIVE'; 'would represent the first specific evidence that the manipulation ... was deliberate'; 'would significantly alter the public narrative'  
Fix: PUB-205 (D+21) already states officially that outages were extended by 'deliberate interference with utility control systems'. The new element is only the pre-storm timestamp: say so.

**D25** (area 6) - NWS-P045-09  
File: `03_news/stories/batch-K.json`  
Text: 'The motion passed unanimously'; 'develop a simultaneous multilingual alert protocol within 60 days'; 'KNCB broadcast the alert in Spanish based on its own translation before receiving official Spanish-language guidance'; 'the Corpus Christi city emergency management office'; timed 14:00, the minute the testimony starts  
Fix: PUB-146: vote 4-1 to issue an RFP requiring release within 30 minutes; county OEM and its contractor are responsible (PUB-144). KNCB airing its own translation that evening contradicts PUB-144 and NWS-P021-80 ('For twelve hours, the people who listen to us were filling glasses from the tap'); also in NWS-P013-03. Time the story after the hearing.

**D26** (area 4) - NWS-P042-04 / NWS-P042-05  
File: `03_news/stories/batch-K.json`  
Text: quoted notice: 'the federal investigation into the pressure anomalies that led to this advisory remains ongoing'; 'federal investigation into the unauthorized SCADA access and associated pressure irregularities'; '1,820 ... según el informe preliminar ... del 7 de octubre'  
Fix: PUB-206 and GW-PUB-007 carry no such line (GW-PUB-007 note: 'No mention of cyber cause'). Delete; it publicly ties the water notice to the intrusion. 1,820 comes from the D+60 hospital report, not the Oct. 7 DSHS report - on D+42 no public total exists.

**D27** (area 9) - PUB-210; NWS-P003-08  
File: `02_public_record/public_record.json; 03_news/stories/batch-I.json`  
Text: 'The Federal Bureau of Investigation San Antonio Division'  
Fix: Corpus elsewhere uses FBI Houston Division (20+ stories, CHR-033, CHR-146; NWS-P090-05/06 say Houston on the same event). Pick Houston; change PUB-210, NWS-P003-08, t22 design.

**D28** (area 8) - NWS-P000-01; also NWS-P000-03, NWS-P000-10, NWS-P001-01 (OUT-02); NWS-P000-06 (OUT-04); NWS-P000-07, NWS-P001-50 (OUT-05); NWS-P001-08, NWS-P001-07 (OUT-07)  
File: `03_news/stories/batch-C.json; canon broadcast`  
Text: 'Harborline 6 is staying on the air and on this page through the night.' (01:40 D0)  
Fix: canon_timeline broadcast: Harborline 6 off air 01:00 D0 to 08:52 D+1; OUT-04 back D+1 11:30, OUT-05 D+1 23:10, OUT-07 D+2 01:00 local (EVT-2105). Either state that web publishing continued, or move the stories. Remove 'staying on the air'.

**D29** (area 6) - PUB-170  
File: `02_public_record/public_record.json`  
Text: 'conducted rescue operations continuously since 06:22 this morning' (statement dated Wednesday 15:00); 'wind speeds up to 55 knots'  
Fix: 06:22 is UTC on landfall day = 1:22 a.m. Tuesday. 'continuously since 1:22 a.m. Tuesday'.

**D30** (area 6) - NWS-P012-05 / NWS-P012-07  
File: `03_news/stories/batch-J.json`  
Text: 'the last of those mutual-aid staff departed over the weekend'; NuecesInfoLine '311 or (361) 826-2489'; P012-07 (18:10) describes calls to NuecesInfoLine before it was set up at 19:00; EAS text quoted with 'ZONE 4 DISTRIBUTION AREA'; 'reached millions of devices'  
Fix: PUB-133: mutual aid scales back from Oct. 14. PUB-132: NuecesInfoLine 361-826-INFO, 'newly established' at 19:00, announced by Director Escamilla-Voss. Quote PUB-204 verbatim.

**D31** (area 6) - NWS-P003-07  
File: `03_news/stories/batch-I.json`  
Text: headline 'highest single-event total in agency history'; 'the most concentrated single-day rescue dispatch load in the agency's history' (1,100) - same story: 'Thursday brought a record 2,109 rescue requests'  
Fix: Drop the superlative for 1,100.

**D32** (area 10) - NWS-P045-07 / PUB-113 / EVT-1108  
File: `03_news/stories/batch-K.json; 02_public_record/public_record.json; 00_scenario/msel.json`  
Text: story: 'archived with the National Geospatial-Intelligence Agency'; 'ran for 45 days beginning the morning after Rafael's landfall'; '100 percent'. Fact: 'Over 45 days beginning September 12 and concluding October 29' (47 days); 'publicly available through the FEMA OpenData portal'; '183 square kilometers'. Event: 'completes the 180-day assessment commitment'  
Fix: One version: Sept. 12 to Oct. 29 (47 days); public downsampled imagery on OpenData; fix '180-day'.

**D33** (area 11) - NWS-P032-04 / NWS-P038-04  
File: `03_news/stories/batch-K.json`  
Text: 'amplified false emergency shelter locations in the week after Rafael's landfall'; 'in the days immediately following Rafael's landfall'  
Fix: PUB-152 and EVT-1502/1504: false shelter posts ran from five days before landfall and stopped at landfall (the Zavala Elementary 211 calls are on the day before landfall).

**D34** (area 8) - NWS-P021-04  
File: `03_news/stories/batch-J.json`  
Text: 'in a written statement released at 7:00 a.m. CDT Tuesday'; 'contributed to the extended power outages and water distribution failures'; '148 confirmed cases'  
Fix: PUB-150 / GW-PUB-003 are timed 12:00; PUB-150 speaks only of 'anomalous activity' at 'a coastal electric utility'. Water effects are not public.

**D35** (area 1) - NWS-P002-10 / NWS-P002-11 / PUB-190 / PUB-195  
File: `03_news/stories/batch-I.json; 02_public_record/public_record.json`  
Text: P002-11: 'the oil discharge confirmed in Corpus Christi Bay earlier in the day'; 'fixed monitoring points near the La Quinta Channel'; P002-10: 'ship channel oil discharge confirmed by the Coast Guard earlier Thursday'; 'We are not issuing a boil water notice ... tap water ... is currently safe'. PUB-190: 'water supply remains uninterrupted'. PUB-195: plant 'within all regulatory parameters for 52 consecutive days'  
Fix: Reads as a separate discharge first confirmed on D+2 in the bay; name it 'the Inner Harbor spill of Sept. 14'. La Quinta Channel is across the bay from the Inner Harbor: use Hillcrest (CC-AQ-02, PUB-191). PUB-190 contradicts PUB-025 (low pressure citywide). 52 days before D+60 is D+8, inside the citywide boil-water notice (to D+39): say 'raw-water intake below the hydrocarbon alert threshold for 52 days'.

**D36** (area 10) - EVT-1403 / alerts.shelter-zones-c-e  
File: `00_scenario/msel.json; 00_scenario/canon_timeline.json`  
Text: 'shelter-in-place guidance for Zones C–E' at 13:00 D-1; 'omits the curfew time of 22:00 CDT'  
Fix: Zone C has been under mandatory evacuation since 07:00 that day (PUB-201). Evacuation order uses Zones A-C; PUB-200 says 'ZONES A THROUGH D'; this event has Zones C-E. Curfew starts D+1 (canon). Make it 'guidance for residents outside Zones A-C' and drop the curfew.

**D37** (area 10) - t22 news hook; EVT-22xx  
File: `_thread_designs/t22_fraud_design.json; 00_scenario/msel.json`  
Text: 'Sabal Energy Wire: industry surge report shows 142,000 claims filed, $3.8B in insured losses'; 'fema_disaster_declaration_DR-4890-TX'; msel.json 'DR-4890'  
Fix: Canon: $2.1 billion, about 187,000 claims; DR-4821-TX.

**D38** (area 10) - T16 analysis text  
File: `_thread_designs/t16_hospital_design.json`  
Text: 'consistent with 24-hour behavioral lag from notification delay'; 'explained by the 24-hour notification lag'  
Fix: 12 hours 33 minutes.

**D39** (area 9) - NWS-M002-08  
File: `03_news/stories/batch-I.json`  
Text: 'Port of Corpus Christi Authority chief of operations Rolando Espinosa'; 'La Quinta Terminal Complex'; 'Taft Docks'; 'LNG exports from the Ingleside facilities'  
Fix: PUB-120/123 name Julio Sandoval-Reeves as Director of Operations. Real terminal names; use Rendal Terminals / 'Inner Harbor terminals'.

**D40** (area 9) - CHR-109 Elena Vasquez-Okafor  
File: `01_characters/characters.json; 02_public_record/public_record.json`  
Text: characters: 'Dispatch chief', Coastal Bend Emergency Communications Center; PUB-171/172: 'Corpus Christi Fire Department Dispatch Chief' / 'CCFD Dispatch Chief'; EVT-1701 'CCFD SAR coordinator'; NWS-P010-06, NWS-P012-05 speak for CBECC  
Fix: One employer. CBECC already has Director Patricia Escamilla-Voss.

**D41** (area 10) - PUB-200  
File: `02_public_record/public_record.json`  
Text: 'STORM SURGE OF 9 TO 13 FEET'; 'RESIDENTS IN EVACUATION ZONES A THROUGH D SHOULD PREPARE TO EVACUATE'; 'LANDFALL NEAR CORPUS CHRISTI'  
Fix: Canon forecast 9 to 12 feet (PUB-102, PUB-022; NWS-M002-11 already says 12); zones A to C; near Port Aransas. Also at noon D-2 Zone A is already under a mandatory order.

### Minor

**D42** (area 4) - GW-PUB-001, GW-PUB-007, PUB-143, PUB-204, PUB-132  
File: `02_public_record/public_record.json; scenarios`  
Text: 'Zone 4 distribution system' / 'all Zone 4 test points'; PUB-143 boundary 'Leopard Street to the north, Highway 286 to the east, Agnes Street to the south, and Staples Street to the west' vs PUB-204 ZIPs 78401, 78405, 78407, 78408, 78416, 78417; stories place the districts in Calallen/Violet; three different lists of water distribution sites; boil 'two minutes' (PUB-039) vs 'one minute'  
Fix: Remove 'Zone 4' from public text; one boundary, one site list, one boil time.

**D43** (area 4) - EVT-2106, EVT-1407, PUB-144, NWS-P013-03, NWS-P021-80  
File: `00_scenario/msel.json; 02_public_record/public_record.json; 03_news/stories/`  
Text: KNCB receives the Spanish notice at '05:58' (EVT-2106), '06:00 ... via email' (EVT-1407), '6:00 a.m.' (P013-03), '6:03' by fax (P021-80, PUB-144)  
Fix: Canon: reaches KNCB 06:03. Align events and P013-03.

**D44** (area 8) - NWS-P001-09, NWS-P003-07, NWS-P004-08, NWS-P007-05, NWS-P016-40, NWS-P028-05, NWS-P045-60, NWS-P045-09  
File: `03_news/stories/`  
Text: story time_local equals the cited fact's time_local (zero lag)  
Fix: Shift each story at least 15 minutes after the fact.

**D45** (area 8) - PUB-026; NWS-P001-10 (07:00), NWS-P001-02 (08:30)  
File: `02_public_record/public_record.json; 03_news/stories/`  
Text: '911 calls peaked near 2,900 a day' reported the morning of D+1  
Fix: 2,900 is the D+1 full-day total (PUB-131). Date PUB-026 to D+2, or phrase as a rate ('running near ten times normal').

**D46** (area 4) - NWS-P040-01 / NWS-P041-02  
File: `03_news/stories/batch-E.json`  
Text: 'the first Sunday in five weeks that Corpus Christi didn't have to boil its tap water'; 'The city lifted its boil-water notice Saturday after 35 days'  
Fix: Add 'except Districts 3 and 4, still under their separate notice' (lifted D+42).

**D47** (area 9) - PUB-161 / NWS-P000-12  
File: `02_public_record/public_record.json; 03_news/stories/`  
Text: 'South Texas Blood and Tissue Center ... Ayers Street' (a real organisation) vs 'South Texas Blood Bank'  
Fix: One fictional name.

**D48** (area 9) - organisation name variants  
File: `03_news/stories/; 02_public_record/public_record.json`  
Text: 911 centre: 'Coastal Bend Emergency Communications Center' vs 'Corpus Christi–Nueces County 911 center' (NWS-P001-02, NWS-P090-01, NWS-P099-01); health: 'Corpus Christi-Nueces County Public Health District' / 'Nueces County Public Health' / 'Nueces County Health District'; water: 'city water utility' / 'Water Department' / 'Water Services' / 'Public Works Department' / CBPWA; Spanish: 'Autoridad de Energía y Agua del Coastal Bend' vs 'AUTORIDAD DE AGUA Y ENERGIA DE LA COSTA DEL GOLFO' (PUB-206)  
Fix: One name each.

**D49** (area 6) - PUB-164, PUB-172, NWS-P045-60, NWS-P029-04  
File: `02_public_record/public_record.json; 03_news/stories/`  
Text: PUB-164 'September 11 through October 14 ... 30-day response period' (33 days); PUB-172 'Two fatalities were recovered' beside 12 (PUB-203) and 23 deaths; P045-60 'más de 55,000 llamadas' (fact: more than 56,000); P029-04 'returned to its pre-storm baseline of approximately 310' (fact: 380)  
Fix: Align.

**D50** (area 10) - EVT-1103, EVT-1602/1605, EVT-1304, EVT-1509, EVT-1907, EVT-1608, GW-EVT-011  
File: `00_scenario/msel.json`  
Text: 'districts 1 through 6' (five districts); 'McKinley Substation (T8 target)' with no GW id and a 06:17Z failure against SUB-01 at 07:12Z; 'The 23 calls span 3 days' (D+7 to D+10); EVT-1509 D+38 vs PUB-153 D+40; EVT-1907 D+14 vs PUB-181 D+15; EVT-1608 D+22 vs PUB-163 D+23; '14 sessions D-7 to D+16' vs 'D-7 to D+18'  
Fix: Align days and ids.

**D51** (area 7) - PUB-205  
File: `02_public_record/public_record.json`  
Text: 'Residents in Districts 1 through 5 who experienced prolonged outages may be eligible for additional disaster assistance.' (D+21)  
Fix: No household programme exists until D+57; delete or say 'if Individual Assistance is approved'. Repeated in NWS-P021-07.

**D52** (area 8) - NWS-P057-03, NWS-P057-04, NWS-P060-04, NWS-P090-06, NWS-P007-05  
File: `03_news/stories/`  
Text: 'Day 28', 'Day 2', 'Day 5', 'Day 60', 'Day 50', 'Day 4 of operations'  
Fix: Scenario day counts in public text; use dates.

**D53** (area 2) - EVT-1901..1905 support vessel  
File: `00_scenario/msel.json; _thread_designs/t19_drone_design.json`  
Text: 'Narwhal Dream' (front company Nereid Maritime Holdings), Ingleside Marina, D-12 to D-7  
Fix: A second suspicious vessel and a second front company beside Halcyon Drift / Brannoch. Never public and accepted in canon_timeline, but decision 2 says there is one; confirm or fold into Brannoch.

**D54** (area 9) - NWS-P013-03, NWS-P000-13, NWS-P015-03, NWS-P035-04, NWS-P028-04, NWS-P029-05  
File: `03_news/stories/batch-J.json; batch-K.json`  
Text: P013-03 city 'language access system ... performed within its defined parameters' (PUB-144: county contractor, reduced staffing); P000-13 'just after 12:30 a.m.' (PUB-202: 12:45) and 'broadcast in both English and Spanish' (PUB-146 claims a 7 h 52 min lag); P015-03 'between September 23 and September 28' and substations unnamed (PUB-112: Sept. 23 to 26, Harbor View and Crosstown); P035-04 'early-morning statement' (15:00); P028-04 'Biden-era'; P029-05 'serving more than 300,000 people' vs P002-10 'roughly 500,000'  
Fix: Align with the facts.
