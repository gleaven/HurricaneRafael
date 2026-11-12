"""Generate the maritime stream family: AIS, port surveillance, port conditions, arrivals, cargo manifests.

    python3 scripts/streams/gen_maritime.py                 everything, in one go
    python3 scripts/streams/gen_maritime.py --budget 40     work for about 40 s, then stop; run again to continue
    python3 scripts/streams/gen_maritime.py --fresh         forget saved progress (and with --no-cache, saved paths too)

Stages: sim -> ais (one file per month, shore and satellite feeds) -> surveillance -> tables -> docs.
Progress between stages is kept in scripts/streams/_cache/ so a run that is cut short resumes where
it stopped; the output is identical however many runs it takes. See scripts/streams/README.md for
the contract and 05_other_sources/ais/README.md for what the files contain.
"""
import json
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if not sys.path or sys.path[0] != HERE:
    sys.path.insert(0, HERE)

from common import ROOT, retire  # noqa: E402

CACHE = os.path.join(HERE, "_cache")
SIM_PKL = os.path.join(CACHE, "maritime_sim.pkl")
PROGRESS = os.path.join(CACHE, "maritime_progress.json")
OLD = ["05_other_sources/ais/ais_positions.csv"]
# These two keep their file names, so they are retired only while they are still the pre-regeneration
# files (recognised by their header) and only if no retired copy exists yet: a re-run must never move
# this generator's own output over the retired originals.
OLD_SAME_NAME = {"05_other_sources/supply/vessel_arrivals.csv": "noa_submitted_datetime", "05_other_sources/supply/cargo_manifest.csv": "manifest_id"}


def superseded():
    out = list(OLD)
    for rel, new_col in OLD_SAME_NAME.items():
        fp = os.path.join(ROOT, rel)
        if not os.path.exists(fp) or os.path.exists(os.path.join(ROOT, "_versions", "streams_pre_regen_20261109", rel)):
            continue
        with open(fp, encoding="utf-8") as fh:
            if new_col not in fh.readline().split(","):
                out.append(rel)
    return out


def main():
    args = sys.argv[1:]
    budget = float(args[args.index("--budget") + 1]) if "--budget" in args else 1e9
    t_start = time.time()
    os.makedirs(CACHE, exist_ok=True)
    if "--no-cache" in args:
        for f in os.listdir(CACHE):
            if f.startswith("maritime_paths_"):
                os.remove(os.path.join(CACHE, f))
    if "--fresh" in args:
        for f in (SIM_PKL, PROGRESS):
            if os.path.exists(f):
                os.remove(f)
    prog = json.load(open(PROGRESS)) if os.path.exists(PROGRESS) else {"done": [], "counts": {}}

    def left():
        return budget - (time.time() - t_start)

    def mark(stage, counts=None):
        prog["done"].append(stage)
        if counts is not None:
            prog["counts"][stage] = counts
        json.dump(prog, open(PROGRESS, "w"), indent=1)

    import maritime_port as mp
    sim = None
    if "sim" not in prog["done"] or not os.path.exists(SIM_PKL):
        print("simulating the port (D-30 to D+119) ...", flush=True)
        sim = mp.PortSim(verbose="--quiet" not in args)
        try:
            sim.run()
        finally:
            sim.save_paths()
        sim.dump(SIM_PKL)
        prog = {"done": [], "counts": {}}
        moved = retire(superseded())
        mark("sim", {"calls": len(sim.calls), "movements": len(sim.transits), "retired_old_files": moved})
        if left() < 12:
            return finish(prog, False)
    if sim is None:
        sim = mp.PortSim.load(SIM_PKL)

    import maritime_out as mo
    import maritime_tables as mt
    aw = None
    for ym, a, b in mo.MONTHS:
        st = f"ais:{ym}"
        if st in prog["done"]:
            continue
        if left() < 25:
            return finish(prog, False)
        aw = aw or mo.AisWriter(sim)
        n = aw.write_month(ym, a, b)
        print(f"  AIS {ym}: {n['T']} shore-station reports, {n['S']} satellite reports", flush=True)
        mark(st, n)
    if "radar" not in prog["done"]:
        if left() < 30:
            return finish(prog, False)
        sv = mo.Surveillance(sim)
        n = sv.write_radar()
        print(f"  radar tracks: {sum(n.values())} rows", flush=True)
        mark("radar", n)
    if "cameras" not in prog["done"]:
        if left() < 20:
            return finish(prog, False)
        sv = mo.Surveillance(sim)
        ne, nv = sv.write_cameras_and_vts()
        ns = sv.write_status_and_sensors()
        print(f"  camera events: {ne}; traffic log: {nv}; sensor status: {ns}", flush=True)
        mark("cameras", {"camera_events": ne, "traffic_log": nv, "sensor_status": ns})
    if "tables" not in prog["done"]:
        n = {"port_conditions": mt.write_port_conditions(sim), "vessel_arrivals": mt.write_arrivals(sim), "cargo_manifest": mt.write_manifests(sim)}
        print(f"  port conditions: {n['port_conditions']}; arrivals: {n['vessel_arrivals']}; manifests: {n['cargo_manifest']}", flush=True)
        mark("tables", n)
    if "docs" not in prog["done"]:
        import maritime_docs as md
        md.write_all(sim, prog)
        mark("docs")
    return finish(prog, True)


def finish(prog, complete):
    if complete:
        print("maritime streams complete:", json.dumps(prog["counts"]))
    else:
        print("stopped at the time budget after:", ", ".join(prog["done"]) or "(nothing)", "- run again to continue")
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(main())
