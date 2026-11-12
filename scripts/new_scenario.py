"""Scaffold a new scenario (or layer) folder and register it.
  python scripts/new_scenario.py <id> --name "Name" --prefix GW [--base-world rafael] [--threads T8,T9] [--d0 2027-09-14]
Creates scenarios/<id>/ with empty, schema-shaped files. Never overwrites existing files."""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, path

FILES = {
    "00_scenario/config.json": lambda a: {"scenario": a.name, "d0_date": a.d0, "local_timezone": a.tz, "day_range": [-60, 119],
        "public_exclusions": {"places": [], "leak_phrases": []}},
    "00_scenario/threads.json": lambda a: [{"thread_id": t, "name": "TBD", "truth": "TBD", "lanes": []} for t in a.threads],
    "00_scenario/msel.json": lambda a: [],
    "00_scenario/assets.json": lambda a: {"note": "Scenario-specific assets. Fictional IDs carry the scenario prefix.", "assets": []},
    "02_public_record/public_record.json": lambda a: {"facts": [], "never_public": []},
    "06_answer_key/answer_key.json": lambda a: {"paths": []},
    "07_validation/allowlist.json": lambda a: {"entries": []},
}
STATE_LAYER = '''"""State layer for scenario {id}. Called by scripts/build_world_state.py.
api: state(id, [(t, value)], **meta), number(id, hourly_list, **meta), H(day, hh, mm), keyframes, noise, clamp, C (palette), value(var_id, t).
Variable ids must start with "{pfx}_". Leave build() empty until the scenario is designed."""

def build(api, scenario):
    pass
'''

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("id"); ap.add_argument("--name", required=True); ap.add_argument("--prefix", required=True)
    ap.add_argument("--base-world"); ap.add_argument("--threads", default=""); ap.add_argument("--d0", default="2027-09-14"); ap.add_argument("--tz", default="America/Chicago")
    a = ap.parse_args(); a.threads = [t for t in a.threads.split(",") if t]
    root = os.path.join("scenarios", a.id); made = []
    for rel, fn in FILES.items():
        full = path(root, rel)
        if not os.path.exists(full):
            save(os.path.join(root, rel), fn(a)); made.append(rel)
    for d in ("05_streams", "03_news"):
        os.makedirs(path(root, d), exist_ok=True)
    sl = path(root, "00_scenario", "state_layer.py")
    if not os.path.exists(sl):
        open(sl, "w", encoding="utf-8").write(STATE_LAYER.format(id=a.id, pfx=a.prefix.lower())); made.append("00_scenario/state_layer.py")
    reg = load("scenarios/registry.json")
    if not any(s["id"] == a.id for s in reg["scenarios"]):
        reg["scenarios"].append({"id": a.id, "name": a.name, "kind": "layer" if a.base_world else "base_world", "root": root.replace(os.sep, "/"),
            "id_prefix": a.prefix, "d0_date": a.d0, "base_world": a.base_world, "threads": a.threads, "status": "design", "thread_colors": {},
            "threads_file": "00_scenario/threads.json", "config_file": "00_scenario/config.json"})
        save("scenarios/registry.json", reg); made.append("registry entry")
    print(f"scenario {a.id}: created {made or 'nothing (already scaffolded)'}")

if __name__ == "__main__":
    main()
