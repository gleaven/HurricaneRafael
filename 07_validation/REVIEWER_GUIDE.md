# Reviewer guide (hardening pass)

You review fictional news stories for a synthetic-data exercise. Do not edit story files. Write findings only.

## Files
- Stories: `03_news/stories/batch-A.json` to `batch-H.json` (393 stories; fields: story_id, day, time_local, outlet_id, byline, headline, dek, body (list of paragraphs), tags).
- Ground rules: `03_news/WRITER_GUIDE.md`.
- Public facts with the day each becomes public: `02_public_record/public_record.json` (also its `never_public` list).
- Characters: `01_characters/characters.json` (voice, knowledge timeline, context_log).
- Canon: `01_characters/canon.json` (fixed facts and timelines for 43 recurring characters; story text must agree).
- Storylines: `03_news/arcs.json`. Calendar: `python3 scripts/dates.py <day>` (day 0 = Tue Sept. 14, 2027, landfall).
- Tools: `python3 scripts/kg_query.py arc <ARC-ID>`, `python3 scripts/kg_query.py character <CHR-ID>`.

## What to check
1. **Continuity:** events, numbers, names, titles, sequences and character details agree across every story you read, and with the canon. Watch for a later story contradicting an earlier one.
2. **Public-only:** nothing appears before its public day. Nothing implies a hidden link early: no spill cause before day 6; no link between the two contractors, or between the account takeovers and the contractors, before day 114; nothing tying the GPS transmitter, fuel terminal, spoofed vessel or blast together beyond "separately investigating" or "declined to comment on any link". No foreign country is ever named. Nothing in `never_public` appears.
3. **People:** quotes come only from public-facing characters, and only about what they would know by that day. No real elected officials or agency heads are named or quoted.
4. **Plausibility:** agency roles and procedures are realistic; sequences make sense; nothing reads as copy-pasted between stories (identical sentences or quotes in different stories).
5. **Outlet style:** each story matches its outlet's style in `01_characters/outlets.json`.

## Output
Write `07_validation/findings/<your file>.json`:
```
{"source": "<your id>", "scope": "<what you reviewed>", "stories_read": <int>,
 "findings": [
  {"id": "<PREFIX>-001", "severity": "high|medium|low", "story_id": "NWS-...", "field": "headline|dek|body",
   "old": "exact substring currently in that field", "new": "replacement", "reason": "short", "status": "proposed"}
 ]}
```
- **Severity:** high means a contradiction, leak or error a careful reader would notice; medium means a detail mismatch or weak plausibility; low is a nit.
- **`old` must occur exactly once** in that field (body counts across all paragraphs). Verify every `old` with Python before writing. Keep fixes minimal and in the story's voice; keep word count about the same.
- **Bigger problems:** if a problem needs more than a phrase or sentence swap, add a finding with `"field": "story"`, `"old": ""`, `"new": "<what the rewrite must do>"` and `"status": "needs_rewrite"`.
- Work through your whole scope; don't sample. Use Python to load and filter stories, then read every story in your scope in full.

Final report (short): stories read, findings by severity, and anything systemic.

## Rewrite agents: extra formats
- Whole-story replacement: `{"id", "severity", "story_id", "field": "story", "replacement": {<full story object, same story_id and day>}, "reason", "status": "proposed"}`
- New story: `{"id", "severity", "story_id": "<new id>", "field": "new_story", "replacement": {<full story object>}, "reason", "status": "proposed"}`. Use the next free sequence number for that day, and keep the day within `03_news/coverage_targets.json` limits.
- Before writing your findings, simulate: `cp -r "." /tmp/sim_<id>`, put your findings file in `/tmp/sim_<id>/07_validation/findings/`, then run `python3 scripts/apply_fixes.py <file>`, `python3 scripts/validate.py`, `python3 scripts/check_canon.py` and `python3 scripts/check_facts.py` inside `/tmp/sim_<id>`. Fix your proposals until all four report 0 errors or violations and every proposal shows `applied`. Then write the final findings file (statuses reset to `proposed`) to the real project. Never edit story files in the real project.
