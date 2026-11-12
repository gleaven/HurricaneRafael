"""One row per thread: is the story complete in every layer?

For each thread T1-T22 this checks that it has a beginning, an escalation, a discovery and a
resolution in the event list, that the public record and the news pick it up where it becomes
public, that at least one delivered stream carries evidence for it, and that its answer key is
verified. Writes 07_validation/reports/thread_completeness.md and .json.

    python3 scripts/check_thread_completeness.py        (exit 1 if a thread has a blocking gap)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCOVERY = re.compile(r"notic|detect|discover|find|found|flag|investigat|confirm|report|identif|audit|review|alert|trace|attribut|testif|announce|assess|ties|advisory|declar|designat|releas|warn|says|statement", re.I)
RESOLUTION = re.compile(r"restor|reopen|lift|clos|resum|repair|reset|remov|arrest|charg|convict|attribut|after-action|report|complet|return|isolat|approved|plan|hardening|repaid|review|advisory|assessment|designat|contained|claims|ties|sweep|search", re.I)


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    threads = load("00_scenario/threads.json")
    msel = load("00_scenario/msel.json")
    facts = load("02_public_record/public_record.json")["facts"]
    arcs = load("03_news/arcs.json")["arcs"]
    tl = load("00_scenario/canon_timeline.json")["expected_observations"]
    cat = {s["stream_id"]: s for s in load("06_data_streams/stream_catalog.json")["streams"]}
    ak = {t["thread_id"]: t for t in load("06_answer_key/answer_key.json").get("threads", [])}
    akc = {}
    p = os.path.join(ROOT, "07_validation", "reports", "answer_key_check.json")
    if os.path.exists(p):
        akc = {r["thread"]: r for r in json.load(open(p))["threads"]}
    stories = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
        stories += json.load(open(fp, encoding="utf-8"))["stories"]
    ev_by_id = {e["event_id"]: e for e in msel}
    rows, blocking = [], 0
    for th in threads:
        tid = th["thread_id"]
        evs = sorted([e for e in msel if tid in e["threads"]], key=lambda e: e["day"])
        days = [e["day"] for e in evs]
        span = (days[0], days[-1])
        k = max(1, len(evs) // 3)                      # thirds by order of events (threads are unevenly spaced in time by design)
        begin, mid, late = evs[:k], evs[k:len(evs) - k], evs[len(evs) - k:]
        ids = {e["event_id"] for e in evs}
        tfacts = [f for f in facts if tid in (f.get("threads") or []) or ids & set(f.get("events") or [])]
        disc = [e for e in evs[1:] if DISCOVERY.search(e["description"])] + [f for f in tfacts if f["day"] > span[0]]
        res = [e for e in late if RESOLUTION.search(e["description"])] + [f for f in tfacts if f["day"] >= late[0]["day"] and RESOLUTION.search(f["statement"])]
        arc_ids = {a["arc_id"] for a in arcs if tid in (a.get("threads") or [])}
        tstories = [s for s in stories if ids & set(s.get("internal", {}).get("truth_events", [])) or arc_ids & set(s["tags"].get("arcs", []))]
        obs = [o for o in tl["items"] if tid in o["threads"]]
        streams = sorted({o["stream"] for o in obs if cat[o["stream"]].get("delivered")})
        data_streams = [s for s in streams if s not in ("news", "public_record")]
        hidden = [h["event_id"] for h in tl["not_observable"] if tid in h["threads"]]
        key = akc.get(tid)
        gaps, need_story = [], []
        if not begin or len(evs) < 4:
            gaps.append("fewer than four events")
        if not mid:
            gaps.append("no escalation between the first and last events")
        if not disc:
            gaps.append("no discovery event")
        if not res:
            gaps.append("no resolution event")
        if not tfacts:
            gaps.append("no public fact")
        if len(tstories) < 10:
            need_story.append(f"thin coverage: {len(tstories)} stories")
        if tfacts and tstories:
            last_fact, last_story = max(f["day"] for f in tfacts), max(s["day"] for s in tstories)
            if last_story < min(span[1], last_fact) - 14:
                need_story.append(f"coverage stops at day {last_story}, {min(span[1], last_fact) - last_story} days before the thread's last public development")
        if not data_streams:
            gaps.append("no delivered data stream carries evidence")
        if tid not in ak:
            gaps.append("no answer key")
        elif key and key["verified"] != key["steps"]:
            gaps.append(f"answer key: {key['steps'] - key['verified']} step(s) not verified")
        elif not key:
            gaps.append("answer key not yet checked (run check_answer_keys.py)")
        blocking += len(gaps)
        rows.append({"thread": tid, "name": th["name"], "events": len(evs), "days": list(span), "stages": {"beginning": len(begin), "escalation": len(mid), "discovery": len(disc), "resolution": len(res)},
                     "public_facts": len(tfacts), "first_public_day": min([f["day"] for f in tfacts], default=None), "stories": len(tstories), "story_days": [min([s["day"] for s in tstories], default=None), max([s["day"] for s in tstories], default=None)],
                     "data_streams": data_streams, "observations": len(obs), "not_observable_events": hidden, "answer_key_steps": key["steps"] if key else None, "gaps": gaps, "needs_story_content": need_story})
    out = os.path.join(ROOT, "07_validation", "reports")
    json.dump({"blocking_gaps": blocking, "threads": rows}, open(os.path.join(out, "thread_completeness.json"), "w"), indent=1)
    L = ["# Thread completeness", "", "Built by `scripts/check_thread_completeness.py`. A thread is complete when the event list has a beginning, an escalation, a discovery and a resolution; "
         "the public record and the news pick it up where it becomes public; at least one delivered data stream carries evidence; and its answer key is verified on disk.", "",
         "| Thread | Events (days) | Begin / escalate / discover / resolve | Public facts (first day) | Stories (days) | Data streams with evidence | Observations | Answer key | Gaps |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        st = r["stages"]
        g = "; ".join(r["gaps"] + [f"needs story content: {x}" for x in r["needs_story_content"]]) or "none"
        L.append(f"| {r['thread']} {r['name']} | {r['events']} ({r['days'][0]} to {r['days'][1]}) | {st['beginning']} / {st['escalation']} / {st['discovery']} / {st['resolution']} | {r['public_facts']} ({r['first_public_day']}) | "
                 f"{r['stories']} ({r['story_days'][0]} to {r['story_days'][1]}) | {len(r['data_streams'])}: {', '.join(r['data_streams'][:6])}{'…' if len(r['data_streams']) > 6 else ''} | {r['observations']} | "
                 f"{str(r['answer_key_steps']) + ' steps verified' if r['answer_key_steps'] else 'not checked'} | {g} |")
    hid = sorted({e for r in rows for e in r["not_observable_events"]})
    L += ["", "## Events that no delivered stream can show", ""] + [f"- {e}: {next((h.get('reason') for h in tl['not_observable'] if h['event_id'] == e), '')}" for e in hid]
    L += ["", "## Gaps that need new story content", ""] + ([f"- {r['thread']} {r['name']}: {'; '.join(r['needs_story_content'])}" for r in rows if r["needs_story_content"]] or ["- none"])
    open(os.path.join(out, "thread_completeness.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    for r in rows:
        print(f"{'ok  ' if not r['gaps'] else 'GAP '} {r['thread']:<4} events {r['events']:>2}  facts {r['public_facts']:>2}  stories {r['stories']:>3}  streams {len(r['data_streams']):>2}  obs {r['observations']:>2}"
              + (f"  gaps: {'; '.join(r['gaps'])}" if r["gaps"] else "") + (f"  story: {'; '.join(r['needs_story_content'])}" if r["needs_story_content"] else ""))
    print(f"\n{'PASS' if not blocking else 'FAILED'}: {blocking} blocking gap(s) in {len(rows)} threads")
    sys.exit(1 if blocking else 0)


if __name__ == "__main__":
    main()
