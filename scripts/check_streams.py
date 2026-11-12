"""Check every delivered data stream against the canon timeline and the registries.

    python scripts/check_streams.py            full report; exit 1 on any failure
    python scripts/check_streams.py --only=ais,adsb

For each delivered stream in 06_data_streams/stream_catalog.json this verifies
  1. files exist and are not empty
  2. the time span covers the catalogue's required span
  3. every entity id used exists in its registry
  4. every expected observation for the stream (canon_timeline.json -> expected_observations)
     is actually present, by running that observation's probe
  5. hygiene: no answer-revealing columns, no never-public terms in public-voice streams,
     no "GridWater", no real company or station names

Stream families describe themselves in scripts/streams/probes_<family>.py:

    STREAMS = {
      "ais": {
        "time_range": lambda: (min_epoch, max_epoch),        # of the data on disk
        "ids": lambda: {"367001230", ...},                   # entity ids used in the data
        "registry_ids": lambda: {...},                       # ids that are allowed
        "public_voice": False,                               # True for posts, alerts, narratives
        "text": lambda: iterable_of_strings,                 # only needed when public_voice
        "columns": lambda: ["MMSI", ...],                    # header names, for the hygiene scan
      }, ...
    }
    PROBES = {
      ("EVT-0313", "vessel_ot_logs"): lambda: (True, "valve open commands 04:00:12Z-05:29:40Z on both tankers"),
      ...
    }

A probe must read the files on disk (not the generator's memory) and return (ok, detail).
Writes 07_validation/reports/stream_check.json.
"""
import glob
import importlib
import json
import os
import re
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "streams"))

BANNED_COLUMNS = re.compile(r"attack|malicious|truth|phase_label|is_fake|is_fraud|ground_truth|thread|label_|_label$|anomaly_flag|compromised", re.I)
BANNED_EVERYWHERE = [r"GridWater", r"Flint Hills", r"Valero", r"Citgo", r"NuStar", r"Buckeye", r"Caller[- ]?Times", r"\bKIII\b", r"\bKRIS\b",
                     r"CHRISTUS", r"Spohn", r"Driscoll", r"State Farm", r"Auriga Meridian", r"Pier 9\b"]


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def ts(iso):
    import datetime as dt
    s = iso.replace("Z", "+00:00")
    if len(s) == 16:
        s += "+00:00"
    return dt.datetime.fromisoformat(s).timestamp()


def main():
    only = set()
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    cat = load("06_data_streams/stream_catalog.json")["streams"]
    canon = load("00_scenario/canon_timeline.json")
    expected = canon["expected_observations"]["items"]
    terms = load("02_public_record/restricted_terms.json")["terms"]
    never = [t["pattern"] for t in terms if t["public_from_day"] is None]

    streams, probes, load_errors = {}, {}, []
    for fp in sorted(glob.glob(os.path.join(HERE, "streams", "probes_*.py"))):
        name = os.path.basename(fp)[:-3]
        try:
            mod = importlib.import_module(name)
            streams.update(getattr(mod, "STREAMS", {}))
            probes.update(getattr(mod, "PROBES", {}))
        except Exception:
            load_errors.append((name, traceback.format_exc(limit=2)))

    report, failures = [], 0
    for s in cat:
        sid = s["stream_id"]
        if not s.get("delivered") or (only and sid not in only):
            continue
        if sid in ("news", "census"):
            pass
        r = {"stream": sid, "problems": [], "observations": {"expected": 0, "present": 0, "missing": [], "no_probe": []}}
        files = [f for f in glob.glob(os.path.join(ROOT, s["path_glob"]), recursive=True) if os.path.getsize(f) > 0] if s.get("path_glob") else []
        r["files"] = len(files)
        r["mb"] = round(sum(os.path.getsize(f) for f in files) / 1e6, 1)
        if not files:
            r["problems"].append("no files on disk")
        d = streams.get(sid)
        if d is None:
            if sid not in ("news",):
                r["problems"].append("no description in scripts/streams/probes_*.py (span, ids and hygiene not checked)")
        else:
            try:
                span = s.get("required_span") or {}
                if span.get("start_utc") and d.get("time_range"):
                    lo, hi = d["time_range"]()
                    r["span"] = [lo, hi]
                    if lo > ts(span["start_utc"]) + 86400:
                        r["problems"].append(f"starts {(lo - ts(span['start_utc'])) / 86400:.1f} days after the required start")
                    if hi < ts(span["end_utc"]) - 86400:
                        r["problems"].append(f"ends {(ts(span['end_utc']) - hi) / 86400:.1f} days before the required end")
                if d.get("ids") and d.get("registry_ids"):
                    unknown = sorted(str(x) for x in set(d["ids"]()) - set(d["registry_ids"]()))
                    if unknown:
                        r["problems"].append(f"{len(unknown)} ids not in the registry, e.g. {unknown[:5]}")
                if d.get("columns"):
                    bad = [c for c in d["columns"]() if BANNED_COLUMNS.search(c)]
                    if bad:
                        r["problems"].append(f"answer-revealing columns: {bad}")
                if d.get("text"):
                    pats = BANNED_EVERYWHERE + (never if d.get("public_voice") else [])
                    rx = re.compile("|".join(f"(?:{p})" for p in pats), re.I)
                    hits = {}
                    for line in d["text"]():
                        for m in rx.finditer(line):
                            hits[m.group(0)] = hits.get(m.group(0), 0) + 1
                    if hits:
                        r["problems"].append(f"banned or never-public terms in text: {dict(sorted(hits.items(), key=lambda x: -x[1])[:8])}")
            except Exception:
                r["problems"].append("description raised: " + traceback.format_exc(limit=1).strip().splitlines()[-1])
        for e in expected:
            if e["stream"] != sid:
                continue
            r["observations"]["expected"] += 1
            p = probes.get((e["event_id"], sid))
            if p is None:
                r["observations"]["no_probe"].append(e["event_id"])
                continue
            try:
                ok, detail = p()
            except Exception:
                ok, detail = False, "probe raised: " + traceback.format_exc(limit=1).strip().splitlines()[-1]
            if ok:
                r["observations"]["present"] += 1
            else:
                r["observations"]["missing"].append({"event": e["event_id"], "what": e["what"][:160], "detail": detail})
        bad = len(r["problems"]) + len(r["observations"]["missing"]) + len(r["observations"]["no_probe"])
        failures += bad
        report.append(r)
        o = r["observations"]
        print(f"{'ok  ' if not bad else 'FAIL'} {sid:<24} files {r['files']:>4} {r['mb']:>7.1f} MB  observations {o['present']}/{o['expected']}"
              + (f"  missing {len(o['missing'])}" if o["missing"] else "") + (f"  unprobed {len(o['no_probe'])}" if o["no_probe"] else ""))
        for p in r["problems"]:
            print(f"       - {p}")
        for m in o["missing"][:6]:
            print(f"       - {m['event']}: {m['detail']}  (expected: {m['what']})")
        if o["no_probe"]:
            print(f"       - no probe for: {', '.join(o['no_probe'][:12])}")
    for name, err in load_errors:
        failures += 1
        print(f"FAIL could not load {name}: {err.strip().splitlines()[-1]}")
    os.makedirs(os.path.join(ROOT, "07_validation", "reports"), exist_ok=True)
    json.dump({"failures": failures, "streams": report}, open(os.path.join(ROOT, "07_validation", "reports", "stream_check.json"), "w"), indent=1)
    tot = sum(r["observations"]["expected"] for r in report); got = sum(r["observations"]["present"] for r in report)
    print(f"\n{'PASS' if not failures else 'FAILED'}: {failures} problem(s); expected observations present {got}/{tot}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
