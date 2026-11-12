"""Embed the shared state timeline data into the offline viewer.
Usage: python scripts/build_state_viewer.py -> 09_shared_state_timeline/viewer/shared_state_timeline.html"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, path, all_threads

D = "09_shared_state_timeline/data/"
data = {"variables": load(D + "variables.json"), "segments": load(D + "segments.json"), "series": load(D + "series_hourly.json"),
        "events": load(D + "events.json"), "track": load(D + "storm_track.json")}
used = {t for v in data["variables"]["variables"] for t in v.get("threads", [])} | {t for e in data["events"] for t in e.get("threads", [])}
TH = all_threads()
data["threads"] = {k: [TH[k]["name"], TH[k]["color"]] for k in sorted(used, key=lambda x: int(x[1:])) if k in TH}
tpl = open(path("09_shared_state_timeline", "viewer", "template.html"), encoding="utf-8").read()
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
html = tpl.replace("/*__DATA__*/null", blob)
out = path("09_shared_state_timeline", "viewer", "shared_state_timeline.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"viewer written: {os.path.relpath(out, path())} ({len(html)/1e6:.2f} MB)")
