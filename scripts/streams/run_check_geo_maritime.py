"""Run scripts/check_geo.py's own checker over the maritime position sources in resumable pieces.

    python3 scripts/streams/run_check_geo_maritime.py --budget 45     work for about 45 s; run again to continue
    python3 scripts/streams/run_check_geo_maritime.py --report        print the combined result
    python3 scripts/streams/run_check_geo_maritime.py --fresh         discard earlier results
    python3 scripts/streams/run_check_geo_maritime.py --redo 2        discard and rebuild one source only (0 AIS, 1 satellite AIS, 2 radar)

Why this exists: `python3 scripts/check_geo.py --only=AIS` is the authority, but on the full AIS
stream (about 1.2 million reports) it needs roughly 40 minutes of CPU, because every pair of
consecutive reports is tested for land between them. This runner feeds exactly the same Checker
class and rules the same rows, cut into pieces: each vessel's track is split into runs of a few
thousand reports that overlap by one report, so every consecutive pair is tested exactly once.
Nothing is sampled or skipped. Results for finished pieces are kept in /tmp/maritime_geo_check/.
"""
import csv
import glob
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
WORK = "/tmp/maritime_geo_check"
CHUNK = 2500
SOURCES = [
    dict(name="AIS vessel positions", glob="05_other_sources/ais/*.csv", lat="LAT", lon="LON", rule="vessel", id="MMSI", time="BaseDateTime", draft_m="Draft"),
    dict(name="AIS satellite feed", glob="05_other_sources/ais/satellite/*.csv", lat="LAT", lon="LON", rule="vessel", id="MMSI", time="BaseDateTime", draft_m="Draft"),
    dict(name="Port radar contacts", glob="05_other_sources/port_surveillance/radar_tracks_*.csv", lat="latitude", lon="longitude", rule="vessel", id="track_id", time="time_utc"),
]


def build_shards(only=None, index=None):
    os.makedirs(WORK, exist_ok=True)
    index = [j for j in (index or []) if only is not None and j["source"] not in only]
    for si, src in enumerate(SOURCES):
        if only is not None and si not in only:
            continue
        tracks, header = {}, None
        for fp in sorted(glob.glob(os.path.join(ROOT, src["glob"]))):
            with open(fp, encoding="utf-8", newline="") as fh:
                r = csv.reader(fh)
                header = next(r)
                ii, it = header.index(src["id"]), header.index(src["time"])
                for row in r:
                    tracks.setdefault(row[ii], []).append(row)
        pieces = []
        for vid in sorted(tracks):
            rows = tracks[vid]
            rows.sort(key=lambda x: x[it])
            i = 0
            while i < len(rows) - 1 or (i == 0 and len(rows) == 1):
                pieces.append(rows[i:i + CHUNK + 1])
                i += CHUNK
                if len(rows) == 1:
                    break
        # pack pieces into shard files of about CHUNK * 2 rows
        shard, n, k = [], 0, 0
        def flush():
            nonlocal shard, n, k
            if not shard:
                return
            fp = os.path.join(WORK, f"s{si}_{k:04d}.csv")
            with open(fp, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(header + ["_piece"])
                for pi, piece in shard:
                    for row in piece:
                        w.writerow(row + [pi])
            index.append(dict(source=si, file=fp, rows=n))
            shard, n = [], 0
            k += 1
        for pi, piece in enumerate(pieces):
            shard.append((pi, piece)); n += len(piece)
            if n >= CHUNK * 2:
                flush()
        flush()
    json.dump(index, open(os.path.join(WORK, "index.json"), "w"))
    return index


_checker = None


def work(job):
    global _checker
    sys.path.insert(0, SCRIPTS)
    import check_geo
    if _checker is None:
        _checker = check_geo.Checker()
    src = dict(SOURCES[job["source"]])
    src["glob"] = job["file"]
    # each piece is one vessel-run: make the track id unique per piece so pairs never straddle pieces
    src_id = src["id"]
    tmp = job["file"] + ".run.csv"
    with open(job["file"], encoding="utf-8", newline="") as fh, open(tmp, "w", encoding="utf-8", newline="") as out:
        r = csv.reader(fh); w = csv.writer(out)
        header = next(r)
        ii = header.index(src_id)
        w.writerow(header)
        for row in r:
            row = list(row)
            row[ii] = row[ii] + "#" + row[-1]
            w.writerow(row)
    src["glob"] = tmp
    _checker.results = []
    t = time.time()
    o = _checker.run(src)
    os.remove(tmp)
    res = dict(file=job["file"], source=job["source"], rows=o["rows"], violations=o["violations"], by_kind=o["by_kind"], examples=o["examples"], seconds=round(time.time() - t, 1))
    json.dump(res, open(job["file"] + ".json", "w"))
    return res


def report(index):
    tot = {}
    done = 0
    secs = 0.0
    for job in index:
        fp = job["file"] + ".json"
        if not os.path.exists(fp):
            continue
        done += 1
        r = json.load(open(fp))
        s = tot.setdefault(r["source"], dict(rows=0, violations=0, by_kind={}, examples=[]))
        s["rows"] += r["rows"]; s["violations"] += r["violations"]
        secs += r["seconds"]
        for k, v in r["by_kind"].items():
            s["by_kind"][k] = s["by_kind"].get(k, 0) + v
        s["examples"] += r["examples"][:3]
    print(f"pieces checked: {done} of {len(index)}   checker time so far: {secs / 60:.1f} min")
    for si, src in enumerate(SOURCES):
        s = tot.get(si)
        if not s:
            continue
        print(f"{'ok  ' if not s['violations'] else 'FAIL'} {src['name']:<24} rows checked {s['rows']:>8} (overlap rows counted twice)  violations {s['violations']}")
        for k, v in s["by_kind"].items():
            print(f"       {v:>6}  {k}")
        for e in s["examples"][:8]:
            print("         e.g.", e)
    return done == len(index), sum(s["violations"] for s in tot.values())


def main():
    args = sys.argv[1:]
    budget = float(args[args.index("--budget") + 1]) if "--budget" in args else 1e9
    t0 = time.time()
    if "--fresh" in args and os.path.isdir(WORK):
        for f in os.listdir(WORK):
            os.remove(os.path.join(WORK, f))
    ix = os.path.join(WORK, "index.json")
    index = json.load(open(ix)) if os.path.exists(ix) else build_shards()
    if "--redo" in args:                 # e.g. --redo 2 after regenerating only the radar tables
        si = int(args[args.index("--redo") + 1])
        for f in os.listdir(WORK):
            if f.startswith(f"s{si}_"):
                os.remove(os.path.join(WORK, f))
        index = build_shards(only=[si], index=index)
    if "--report" not in args:
        todo = [j for j in index if not os.path.exists(j["file"] + ".json")]
        if todo:
            with mp.Pool(int(args[args.index("--procs") + 1]) if "--procs" in args else 2) as pool:
                for res in pool.imap_unordered(work, todo):
                    if time.time() - t0 > budget:
                        pool.terminate()
                        break
    complete, viol = report(index)
    print("COMPLETE" if complete else "INCOMPLETE: run again to continue", "-", "PASS" if (complete and not viol) else f"{viol} violation(s) so far")
    return 0 if (complete and not viol) else 1


if __name__ == "__main__":
    sys.exit(main())
