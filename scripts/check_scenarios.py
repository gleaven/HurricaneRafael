"""Check the scenario registry and every layer's namespacing.
  - ids, prefixes and roots unique and present; layers point to an existing base world
  - thread ids unique across scenarios and match each scenario's threads file
  - layer event ids GW-EVT-*, fact ids GW-PUB-*, asset ids GW-*, state variables gw_*
  - no event or fact id collides across scenarios; scaffold files present
Usage: python scripts/check_scenarios.py -> 07_validation/reports/scenarios_report.json; exit 1 on failure"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, load_registry, sroot, sload

REQUIRED = ["00_scenario/config.json", "00_scenario/threads.json", "00_scenario/msel.json", "02_public_record/public_record.json"]
res = []
def check(name, ok, detail=""): res.append({"check": name, "pass": bool(ok), "detail": detail})
reg = load_registry(); ids = [s["id"] for s in reg]
check("scenario ids unique", len(ids) == len(set(ids)), str(ids))
pfx = [s["id_prefix"] for s in reg if s.get("kind") == "layer"]
check("layer prefixes non-empty and unique", all(pfx) and len(pfx) == len(set(pfx)), str(pfx))
seen_threads, seen_events, seen_facts = {}, {}, {}
for s in reg:
    sid, root = s["id"], sroot(s["id"])
    check(f"{sid}: root exists", os.path.isdir(root), root)
    for rel in REQUIRED:
        check(f"{sid}: has {rel}", os.path.exists(os.path.join(root, rel)))
    if s.get("kind") == "layer":
        base = next((b for b in reg if b["id"] == s.get("base_world")), None)
        check(f"{sid}: base world exists and is a base_world", base is not None and base.get("kind") == "base_world", str(s.get("base_world")))
    try: th = sload(sid, s.get("threads_file", "00_scenario/threads.json"))
    except FileNotFoundError: th = []
    tids = [t["thread_id"] for t in th]
    check(f"{sid}: threads file matches registry", sorted(tids) == sorted(s.get("threads", [])), f"{tids} vs {s.get('threads')}")
    for t in tids:
        check(f"thread {t} unique across scenarios", t not in seen_threads, f"also in {seen_threads.get(t)}"); seen_threads[t] = sid
    msel = sload(sid, "00_scenario/msel.json") if os.path.exists(os.path.join(root, "00_scenario/msel.json")) else []
    facts = sload(sid, "02_public_record/public_record.json").get("facts", []) if os.path.exists(os.path.join(root, "02_public_record/public_record.json")) else []
    for e in msel:
        if s.get("kind") == "layer": check(f"{sid}: event {e['event_id']} prefixed", e["event_id"].startswith(s["id_prefix"] + "-EVT-"))
        check(f"event id {e['event_id']} unique across scenarios", e["event_id"] not in seen_events, str(seen_events.get(e["event_id"]))); seen_events[e["event_id"]] = sid
        for t in e.get("threads", []): check(f"{sid}: event {e['event_id']} thread {t} belongs to scenario", t in tids)
    for f in facts:
        if s.get("kind") == "layer": check(f"{sid}: fact {f['id']} prefixed", f["id"].startswith(s["id_prefix"] + "-PUB-"))
        check(f"fact id {f['id']} unique across scenarios", f["id"] not in seen_facts, str(seen_facts.get(f["id"]))); seen_facts[f["id"]] = sid
    if s.get("kind") == "layer" and os.path.exists(os.path.join(root, "00_scenario/assets.json")):
        for a in sload(sid, "00_scenario/assets.json").get("assets", []):
            check(f"{sid}: asset {a.get('id')} prefixed", str(a.get("id", "")).startswith(s["id_prefix"] + "-"))
vars_ = load("09_shared_state_timeline/data/variables.json")["variables"]
for v in vars_:
    sc = v.get("scenario")
    if sc:
        p = next(s["id_prefix"] for s in reg if s["id"] == sc).lower() + "_"
        check(f"state variable {v['id']} prefixed {p}", v["id"].startswith(p))
fails = [r for r in res if not r["pass"]]
save("07_validation/reports/scenarios_report.json", {"checks": len(res), "failed": fails, "results": res})
print(f"scenarios: {len(reg)} registered, {len(res)} checks, {len(fails)} failed")
for r in fails: print("  FAIL", r["check"], r["detail"])
sys.exit(1 if fails else 0)
