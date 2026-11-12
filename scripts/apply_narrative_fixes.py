"""Apply the narrative fixes recorded in scripts/narrative_fixes/*.py (idempotent).

Each patch module defines any of:
  STORIES = {story_id: {"headline": str, "dek": str, "time_local": "HH:MM", "section": str,
                        "public_facts": [...], "arcs": [...], "body": {index: paragraph}, "body_all": [paragraphs],
                        "replace": [(old, new), ...]}}                     # replace runs over headline, dek and body
  FACTS   = {fact_id: {"statement": str, "day": int, "time_local": str|None, "replace": [(old, new), ...]}}
  EVENTS  = {event_id: {"day": int, "replace": [(old, new), ...]}}        # replace runs over every string in the event
  FILES   = [(relative_path, old, new), ...]                              # plain text replacement in any narrative file
  SWEEPS  = [(scope, regex, replacement), ...]                            # scope: "stories", "facts", "events" or "public" (stories + facts);
                                                                          # the regex must not match its own replacement
After the patches, any story that cites a public fact timed on the same day is moved to at least 20 minutes after it.
Fact and event ids are looked up in the base scenario and in scenarios/gridwater.
A replacement whose old text is absent is fine when the new text is already there; otherwise it is reported.

    python3 scripts/apply_narrative_fixes.py [--check]
"""
import glob, importlib.util, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = "--check" in sys.argv
problems = []


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def jsave(p, obj, indent=1):
    if CHECK:
        return
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent)
        fh.write("\n")


def rep_text(text, pairs, where):
    for old, new in pairs:
        if new and new in text:
            pass
        elif old in text:
            text = text.replace(old, new)
        else:
            problems.append(f"{where}: text not found: {old[:70]!r}")
    return text


def walk_replace(obj, pairs, where, hit):
    if isinstance(obj, str):
        out = obj
        for old, new in pairs:
            if new and new in out:
                hit.add(old)
            elif old in out:
                out = out.replace(old, new); hit.add(old)
        return out
    if isinstance(obj, list):
        return [walk_replace(x, pairs, where, hit) for x in obj]
    if isinstance(obj, dict):
        return {k: walk_replace(v, pairs, where, hit) for k, v in obj.items()}
    return obj


def main():
    mods = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "scripts", "narrative_fixes", "*.py"))):
        spec = importlib.util.spec_from_file_location(os.path.basename(fp)[:-3], fp)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); mods.append(m)
    S, F, E, FILES = {}, {}, {}, []
    for m in mods:
        for k, v in getattr(m, "STORIES", {}).items():
            S.setdefault(k, []).append(v)
        for k, v in getattr(m, "FACTS", {}).items():
            F.setdefault(k, []).append(v)
        for k, v in getattr(m, "EVENTS", {}).items():
            E.setdefault(k, []).append(v)
        FILES += getattr(m, "FILES", [])
    # stories
    seen = set()
    for fp in sorted(glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
        b = jload(fp); changed = False
        for s in b["stories"]:
            for p in S.get(s["story_id"], []):
                seen.add(s["story_id"]); before = json.dumps(s, sort_keys=True)
                for k in ("headline", "dek", "time_local", "section"):
                    if k in p:
                        s[k] = p[k]
                if "public_facts" in p:
                    s["tags"]["public_facts"] = p["public_facts"]
                if "arcs" in p:
                    s["tags"]["arcs"] = p["arcs"]
                if "body_all" in p:
                    s["body"] = list(p["body_all"])
                for i, para in p.get("body", {}).items():
                    i = int(i)
                    if i < len(s["body"]):
                        s["body"][i] = para
                    elif i == len(s["body"]):
                        s["body"].append(para)
                    else:
                        problems.append(f"{s['story_id']}: no paragraph {i}")
                if p.get("replace"):
                    blob = "\x1e".join([s["headline"], s["dek"]] + s["body"])
                    blob = rep_text(blob, p["replace"], s["story_id"])
                    parts = blob.split("\x1e")
                    s["headline"], s["dek"], s["body"] = parts[0], parts[1], parts[2:]
                changed |= json.dumps(s, sort_keys=True) != before
        if changed:
            jsave(fp, b)
    for k in S:
        if k not in seen:
            problems.append(f"story {k} not found")
    # facts
    for rel in ("02_public_record/public_record.json", "scenarios/gridwater/02_public_record/public_record.json"):
        fp = os.path.join(ROOT, rel)
        if not os.path.exists(fp):
            continue
        d = jload(fp); changed = False
        for f in d.get("facts", []):
            for p in F.get(f["id"], []):
                seen.add(f["id"]); before = json.dumps(f, sort_keys=True)
                for k in ("statement", "day", "time_local", "source"):
                    if k in p:
                        f[k] = p[k]
                if p.get("replace"):
                    f["statement"] = rep_text(f["statement"], p["replace"], f["id"])
                changed |= json.dumps(f, sort_keys=True) != before
        if changed:
            jsave(fp, d)
    for k in F:
        if k not in seen:
            problems.append(f"fact {k} not found")
    # events
    for rel in ("00_scenario/msel.json", "scenarios/gridwater/00_scenario/msel.json"):
        fp = os.path.join(ROOT, rel)
        if not os.path.exists(fp):
            continue
        d = jload(fp); ev = d if isinstance(d, list) else d.get("events", [])
        changed = False
        for i, e in enumerate(ev):
            for p in E.get(e["event_id"], []):
                seen.add(e["event_id"]); before = json.dumps(e, sort_keys=True)
                for k in ("day", "time_utc", "time_label"):
                    if k in p:
                        e[k] = p[k]
                if p.get("replace"):
                    hit = set()
                    new = walk_replace(e, p["replace"], e["event_id"], hit)
                    blob = json.dumps(new, ensure_ascii=False)
                    for old, nw in p["replace"]:
                        if old not in hit and nw not in blob and json.dumps(nw, ensure_ascii=False)[1:-1] not in blob:
                            problems.append(f"{e['event_id']}: text not found: {old[:70]!r}")
                    ev[i] = e = new
                changed |= json.dumps(e, sort_keys=True) != before
        if changed:
            jsave(fp, d)
    for k in E:
        if k not in seen:
            problems.append(f"event {k} not found")
    # plain files
    for rel, old, new in FILES:
        fp = os.path.join(ROOT, rel)
        t = open(fp, encoding="utf-8").read()
        if new and new in t and old in new:
            pass
        elif old in t:
            if not CHECK:
                open(fp, "w", encoding="utf-8").write(t.replace(old, new))
        elif new not in t:
            problems.append(f"{rel}: text not found: {old[:70]!r}")
    # design copies: thread designs and the timeline quote public facts and events; carry the same replacements there
    pairs = []
    for src in (F, E):
        for plist in src.values():
            for p in plist:
                pairs += [(o, n) for o, n in p.get("replace", []) if len(o) >= 25]
    for m in mods:
        pairs += [(o, n) for sc, o, n in getattr(m, "DESIGN_PAIRS", [])]
    ncopy = 0
    for fp in sorted(glob.glob(os.path.join(ROOT, "_thread_designs", "*.json"))) + [os.path.join(ROOT, "00_scenario", "canon_timeline.json"), os.path.join(ROOT, "00_scenario", "threads.json")]:
        txt = open(fp, encoding="utf-8").read(); new = txt
        for o, n in pairs:
            for oo, nn in ((o, n), (json.dumps(o, ensure_ascii=False)[1:-1], json.dumps(n, ensure_ascii=False)[1:-1])):
                if oo in new and not (nn and nn in new):
                    new = new.replace(oo, nn); ncopy += 1
        if new != txt and not CHECK:
            json.loads(new)
            open(fp, "w", encoding="utf-8").write(new)
    print(f"design copies: {ncopy} replacement(s)")
    # structured edits
    for m in mods:
        fn = getattr(m, "apply", None)
        if fn:
            problems.extend(fn(ROOT, CHECK) or [])
    # sweeps
    import re
    SW = []
    for m in mods:
        SW += getattr(m, "SWEEPS", [])
    nsw = 0

    def sweep(text, scopes):
        nonlocal nsw
        for scope, pat, rep in SW:
            if scope in scopes:
                text, k = re.subn(pat, rep, text)
                nsw += k
        return text

    def sweep_obj(o, scopes):
        if isinstance(o, str):
            return sweep(o, scopes)
        if isinstance(o, list):
            return [sweep_obj(x, scopes) for x in o]
        if isinstance(o, dict):
            return {k: sweep_obj(v, scopes) for k, v in o.items()}
        return o

    fact_time = {}
    for rel in ("02_public_record/public_record.json", "scenarios/gridwater/02_public_record/public_record.json"):
        fp = os.path.join(ROOT, rel)
        d = jload(fp); before = json.dumps(d, sort_keys=True)
        for f in d.get("facts", []):
            f["statement"] = sweep(f["statement"], ("facts", "public"))
            if f.get("time_local"):
                fact_time[f["id"]] = (f["day"], f["time_local"])
        if json.dumps(d, sort_keys=True) != before:
            jsave(fp, d)
    for rel in ("00_scenario/msel.json", "scenarios/gridwater/00_scenario/msel.json"):
        fp = os.path.join(ROOT, rel)
        d = jload(fp); new = sweep_obj(d, ("events",))
        if json.dumps(new, sort_keys=True) != json.dumps(d, sort_keys=True):
            jsave(fp, new)
    moved = 0
    for fp in sorted(glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
        b = jload(fp); before = json.dumps(b, sort_keys=True)
        for s in b["stories"]:
            s["headline"] = sweep(s["headline"], ("stories", "public"))
            s["dek"] = sweep(s["dek"], ("stories", "public"))
            s["body"] = [sweep(x, ("stories", "public")) for x in s["body"]]
            need = 0
            for pf in s["tags"].get("public_facts", []):
                if pf in fact_time and fact_time[pf][0] == s["day"]:
                    h, mi = fact_time[pf][1].split(":")[:2]
                    need = max(need, int(h) * 60 + int(mi) + 20)
            h, mi = s["time_local"].split(":")[:2]
            if need and int(h) * 60 + int(mi) < need - 10 and need < 24 * 60:
                s["time_local"] = f"{need // 60:02d}:{need % 60:02d}"; moved += 1
        if json.dumps(b, sort_keys=True) != before:
            jsave(fp, b)
    print(f"sweeps: {len(SW)} patterns, {nsw} replacement(s); {moved} story time(s) moved after the fact they cite")
    print(f"narrative fixes: {len(S)} stories, {len(F)} facts, {len(E)} events, {len(FILES)} file edits; {len(problems)} problem(s)")
    for p in problems:
        print("  -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
