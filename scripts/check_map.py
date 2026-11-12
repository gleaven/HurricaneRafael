"""Check the map viewer's data the way the viewer uses it.

    python3 scripts/check_map.py                 sample days, writes snapshots, exit 1 on any failure
    python3 scripts/check_map.py --days=-2,0,44  chosen days (UTC day index from landfall day)
    python3 scripts/check_map.py --all --resume  every day, in pieces under the shell time limit
    python3 scripts/check_map.py --paths --all --resume   vehicle paths between the 15-minute steps (see below)

For each day chunk in 09_shared_state_timeline/viewer/map_data/ this decodes the tracks exactly
as map_view.html does (delta-decoded parts, linear interpolation by time between kept
vertices) and, at every 15-minute step:
  * every vessel position must be in water (scripts/geo.py, exact polygons);
  * every vehicle that is moving at that instant must be within 35 m of a road centreline;
  * every aircraft on the ground inside the local window must be at an airfield or helipad.
--paths looks between the 15-minute steps: every moving vehicle segment is sampled every 40 m and
each sample must be within 35 m of a street, and no segment may be a jump (more than 150 m
covered at over 50 m/s, about 110 mph).

A day already checked is checked again by itself when its chunk has been rebuilt since.
It also checks that each chunk parses, that ids resolve in index.js, and draws a snapshot of
each sampled day at 18:00Z over the real land, channels and roads into viewer/_snapshots/.
"""
import glob
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import geo  # noqa: E402

VIEW = os.path.join(ROOT, "09_shared_state_timeline", "viewer")
DATA = os.path.join(VIEW, "map_data")
SNAP = os.path.join(VIEW, "_snapshots")
SAMPLE = [-30, -10, -2, 0, 1, 2, 5, 12, 30, 38, 44, 45, 58, 60, 90, 119]
DAY = 86400


def read_js(path):
    """Payload of a map_data script file (the JSON after the second assignment)."""
    s = open(path, encoding="utf-8").read()
    a = s.index("=", s.index(";") + 1)
    b = s.rindex(";window.RAFAEL_MAP.onDay") if ";window.RAFAEL_MAP.onDay" in s[-80:] else s.rindex(";")
    return json.loads(s[a + 1:b])


def day_file(d):
    return os.path.join(DATA, f"day_{'m' if d < 0 else 'p'}{abs(d):03d}.js")


def decode(flat, width):
    """Delta-coded flat list -> array (n, width) of absolute values (as the viewer does)."""
    a = np.array(flat, dtype=np.int64).reshape(-1, width)
    return np.cumsum(a, axis=0)


def position(parts, t):
    """(lat, lon, moving, extra) at second t of the day, or None if no part covers t."""
    for p in parts:
        if p[0, 0] <= t <= p[-1, 0]:
            i = int(np.searchsorted(p[:, 0], t, side="right")) - 1
            if i >= len(p) - 1:
                return p[-1, 1] / 1e5, p[-1, 2] / 1e5, False, p[-1]
            a, b = p[i], p[i + 1]
            f = (t - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
            moving = abs(b[1] - a[1]) + abs(b[2] - a[2]) > 2
            return (a[1] + (b[1] - a[1]) * f) / 1e5, (a[2] + (b[2] - a[2]) * f) / 1e5, moving, a + (b - a) * f
    return None


class State:
    def __init__(self):
        self.G = geo.Geo()
        self.index = read_js(os.path.join(DATA, "index.js"))
        self.pads = np.array([(l["lat"], l["lon"]) for l in self.G.find(["helipad", "hospital", "airport"])])


def check_day(S, d, snapshot=True):
    G = S.G
    res = {"day": d, "vessel_positions": 0, "vessel_on_land": 0, "vehicle_positions": 0, "vehicle_moving": 0, "vehicle_off_road": 0,
           "aircraft_ground": 0, "aircraft_ground_bad": 0, "unknown_ids": 0, "examples": []}
    day = read_js(day_file(d))
    V = {k: [decode(p, 3) for p in v] for k, v in day["v"].items()}
    C = {k: [decode(p, 3) for p in v] for k, v in day["c"].items()}
    A = {k: [decode(p, 4) for p in v] for k, v in day["a"].items()}
    res["unknown_ids"] = sum(1 for k in V if k not in S.index["vessels"]) + sum(1 for k in A if k not in S.index["aircraft"]) + sum(1 for k in C if k not in S.index["units"])
    vl, vo, vid = [], [], []
    cl, co, cid = [], [], []
    for step in range(96):
        t = step * 900
        for k, parts in V.items():
            p = position(parts, t)
            if p:
                vl.append(p[0]); vo.append(p[1]); vid.append((k, t))
        for k, parts in C.items():
            p = position(parts, t)
            if p:
                res["vehicle_positions"] += 1
                if p[2]:
                    cl.append(p[0]); co.append(p[1]); cid.append((k, t))
        for k, parts in A.items():
            p = position(parts, t)
            if p and p[3][3] < 0 and G.in_box(p[0], p[1]):
                res["aircraft_ground"] += 1
                dr, _ = G.runway_distance_m(p[0], p[1])
                pad = float(np.hypot((S.pads[:, 0] - p[0]) * geo.M_PER_DEG_LAT, (S.pads[:, 1] - p[1]) * geo.M_PER_DEG_LON).min())
                if dr > 500 and pad > 300:
                    res["aircraft_ground_bad"] += 1
                    res["examples"].append(f"aircraft {k} on ground {dr:.0f} m from a runway at {p[0]:.5f},{p[1]:.5f} t={t}")
    res["vessel_positions"] = len(vl)
    if vl:
        land = G.is_land_many(np.array(vl), np.array(vo))
        res["vessel_on_land"] = int(land.sum())
        for i in np.where(land)[0][:5]:
            res["examples"].append(f"vessel {vid[i][0]} on land at {vl[i]:.5f},{vo[i]:.5f} t={vid[i][1]}")
    res["vehicle_moving"] = len(cl)
    if cl:
        dist = G.roads.distance_many(np.array(cl), np.array(co))
        bad = dist > 35
        res["vehicle_off_road"] = int(bad.sum())
        for i in np.where(bad)[0][:5]:
            res["examples"].append(f"vehicle {cid[i][0]} {dist[i]:.0f} m from a road at {cl[i]:.5f},{co[i]:.5f} t={cid[i][1]}")
    if snapshot:
        draw(S, d, V, C, A, day)
    return res


def paths_day(S, d):
    """Vehicle paths as drawn between kept vertices: distance to a street along the way, and jumps."""
    day = read_js(day_file(d))
    res = {"day": d, "segments": 0, "samples": 0, "off_road": 0, "jumps": 0, "examples": []}
    la, lo, who = [], [], []
    for k, parts in day["c"].items():
        for flat in parts:
            p = decode(flat, 3).astype(float)
            if len(p) < 2:
                continue
            dist = np.hypot((p[1:, 1] - p[:-1, 1]) / 1e5 * geo.M_PER_DEG_LAT, (p[1:, 2] - p[:-1, 2]) / 1e5 * geo.M_PER_DEG_LON)
            dt_ = p[1:, 0] - p[:-1, 0]
            mv = dist > 3
            res["segments"] += int(mv.sum())
            jump = mv & (dist > 150) & (dist > 50 * np.maximum(dt_, 0))
            res["jumps"] += int(jump.sum())
            for i in np.where(jump)[0][:2]:
                res["examples"].append(f"vehicle {k} covers {dist[i]:.0f} m in {dt_[i]:.0f} s at t={p[i, 0]:.0f}")
            idx = np.where(mv)[0]
            if not len(idx):
                continue
            n = np.maximum(1, (dist[idx] / 40).astype(int))
            rep = np.repeat(idx, n)
            off = np.concatenate([np.arange(c) for c in n])
            f = (off + 0.5) / np.repeat(n, n)
            la.append((p[rep, 1] + (p[rep + 1, 1] - p[rep, 1]) * f) / 1e5)
            lo.append((p[rep, 2] + (p[rep + 1, 2] - p[rep, 2]) * f) / 1e5)
            who += [k] * len(rep)
    if la:
        la = np.concatenate(la); lo = np.concatenate(lo)
        dd = S.G.roads.distance_many(la, lo)
        bad = dd > 35
        res["samples"] = int(len(la)); res["off_road"] = int(bad.sum()); res["max_m"] = float(dd.max())
        for i in np.where(bad)[0][:4]:
            res["examples"].append(f"vehicle {who[i]} path {dd[i]:.0f} m from a street at {la[i]:.5f},{lo[i]:.5f}")
    return res


def main_paths(days, resume, budget):
    prog_path = os.path.join(VIEW, "_build_cache", "check_map.paths.progress.json")
    done = json.load(open(prog_path)) if resume and os.path.exists(prog_path) else {}
    S = State()
    t0 = time.time()
    for d in days:
        m = int(os.path.getmtime(day_file(d)))
        if str(d) in done and done[str(d)].get("mtime") == m:
            continue
        done.pop(str(d), None)
        if time.time() - t0 > budget:
            break
        done[str(d)] = dict(paths_day(S, d), mtime=m)
        if resume:
            json.dump(done, open(prog_path, "w"))
    left = [d for d in days if str(d) not in done]
    if left:
        print(f"INCOMPLETE: {len(left)} days still to check (run again with --resume)")
        sys.exit(2)
    tot = {k: sum(done[str(d)][k] for d in days) for k in ("segments", "samples", "off_road", "jumps")}
    for d in days:
        for e in done[str(d)]["examples"][:3]:
            print(f"   day {d:+4d}: {e}")
    worst = max((done[str(d)].get("max_m", 0) for d in days), default=0)
    fails = tot["off_road"] + tot["jumps"]
    print(f"{'PASS' if not fails else 'FAILED'} (paths): {len(days)} days; {tot['segments']:,} moving vehicle segments, {tot['samples']:,} samples along them, "
          f"{tot['off_road']} more than 35 m from a street (farthest {worst:.0f} m); {tot['jumps']} jumps")
    if resume and os.path.exists(prog_path):
        os.remove(prog_path)
    sys.exit(1 if fails else 0)


def draw(S, d, V, C, A, day):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    G = S.G
    os.makedirs(SNAP, exist_ok=True)
    t = 18 * 3600
    fig, axs = plt.subplots(1, 2, figsize=(22, 10))
    for ax, box in zip(axs, [(-97.66, 27.55, -96.82, 28.08), (-97.54, 27.74, -97.33, 27.87)]):
        ax.set_facecolor("#bcd9ea")
        for it in G.land.items:
            b = it["bbox"]
            if b[2] < box[0] or b[0] > box[2] or b[3] < box[1] or b[1] > box[3]:
                continue
            ax.fill(it["xy"][:, 0], it["xy"][:, 1], fc="#e9e3cf", ec="#9a9", lw=0.2)
        for it in G.water_override.items:
            ax.fill(it["xy"][:, 0], it["xy"][:, 1], fc="#bcd9ea")
        for it in G.channels.items:
            ax.fill(it["xy"][:, 0], it["xy"][:, 1], fc="#7fb2e0", alpha=0.6)
        for _, cls, pts in G.roads.features:
            a = np.array(pts)
            ax.plot(a[:, 1], a[:, 0], c="#b9a", lw=0.3 if cls == "local" else 0.5)
        # the whole day's tracks, faint, then the position at 18:00Z
        for parts, col in ((V, "#c0392b"), (C, "#1e8449"), (A, "#6c3483")):
            for k, pp in parts.items():
                for p in pp:
                    ax.plot(p[:, 2] / 1e5, p[:, 1] / 1e5, c=col, lw=0.4, alpha=0.5)
        for parts, col, mk, lab in ((V, "#c0392b", "^", "vessels"), (C, "#1e8449", "s", "vehicles"), (A, "#6c3483", "P", "aircraft")):
            xs, ys = [], []
            for k, pp in parts.items():
                p = position(pp, t)
                if p:
                    xs.append(p[1]); ys.append(p[0])
            ax.plot(xs, ys, mk, c=col, ms=5, mec="k", mew=0.4, label=f"{lab} ({len(xs)})", ls="")
        inc = [r for r in day["i"] if r[0] <= t <= r[1]]
        ax.plot([r[3] / 1e5 for r in inc], [r[2] / 1e5 for r in inc], ".", c="#e67e22", ms=3, label=f"open incidents ({len(inc)})")
        ax.set_xlim(box[0], box[2]); ax.set_ylim(box[1], box[3]); ax.set_aspect(1 / 0.885)
        ax.legend(loc="lower left", fontsize=8)
    fig.suptitle(f"Map data, UTC day {d:+d} from landfall day, positions at 18:00Z (tracks for the whole day)")
    fig.savefig(os.path.join(SNAP, f"day_{'m' if d < 0 else 'p'}{abs(d):03d}.png"), dpi=70, bbox_inches="tight")
    plt.close(fig)


def main():
    days = SAMPLE
    for a in sys.argv[1:]:
        if a.startswith("--days="):
            days = [int(x) for x in a.split("=", 1)[1].split(",")]
    every = "--all" in sys.argv
    resume = "--resume" in sys.argv
    budget = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--budget=")), 130.0)
    if every:
        days = sorted(int(os.path.basename(f)[5:8]) * (-1 if os.path.basename(f)[4] == "m" else 1) for f in glob.glob(os.path.join(DATA, "day_*.js")))
    if "--paths" in sys.argv:
        return main_paths(days, resume, budget)
    prog_path = os.path.join(VIEW, "_build_cache", "check_map.progress.json")
    done = json.load(open(prog_path)) if resume and os.path.exists(prog_path) else {}
    S = State()
    t0 = time.time()
    for d in days:
        m = int(os.path.getmtime(day_file(d)))
        if str(d) in done and done[str(d)].get("mtime") == m:
            continue
        done.pop(str(d), None)
        if time.time() - t0 > budget:
            break
        done[str(d)] = dict(check_day(S, d, snapshot=(d in SAMPLE)), mtime=m)
        if resume:
            json.dump(done, open(prog_path, "w"))
    tot = {k: 0 for k in ("vessel_positions", "vessel_on_land", "vehicle_positions", "vehicle_moving", "vehicle_off_road", "aircraft_ground", "aircraft_ground_bad", "unknown_ids")}
    for d in days:
        r = done.get(str(d))
        if not r:
            continue
        bad = r["vessel_on_land"] + r["vehicle_off_road"] + r["aircraft_ground_bad"] + r["unknown_ids"]
        print(f"{'ok  ' if not bad else 'FAIL'} day {d:+4d}  vessels {r['vessel_positions']:>5} on land {r['vessel_on_land']}   vehicles {r['vehicle_positions']:>5} moving {r['vehicle_moving']:>4} "
              f"off road {r['vehicle_off_road']}   aircraft on ground {r['aircraft_ground']:>3} bad {r['aircraft_ground_bad']}   unknown ids {r['unknown_ids']}")
        for e in r["examples"][:4]:
            print("       ", e)
        for k in tot:
            tot[k] += r[k]
    left = [d for d in days if str(d) not in done]
    fails = tot["vessel_on_land"] + tot["vehicle_off_road"] + tot["aircraft_ground_bad"] + tot["unknown_ids"]
    if left:
        print(f"\nINCOMPLETE: {len(left)} days still to check (run again with --resume)")
        sys.exit(2)
    print(f"\n{'PASS' if not fails else 'FAILED'}: {len(days)} days; {tot['vessel_positions']:,} vessel positions, {tot['vessel_on_land']} on land; "
          f"{tot['vehicle_moving']:,} moving-vehicle positions, {tot['vehicle_off_road']} off road; {tot['aircraft_ground']:,} aircraft-on-ground positions, "
          f"{tot['aircraft_ground_bad']} away from an airfield; {tot['unknown_ids']} ids not in index.js")
    if resume and os.path.exists(prog_path):
        os.remove(prog_path)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
