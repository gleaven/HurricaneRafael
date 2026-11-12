"""Headless pictures of what the map viewer shows at chosen moments.

    python3 scripts/render_map_frames.py             draw missing frames (stops before --budget=140 s; repeat until COMPLETE)
    python3 scripts/render_map_frames.py --force     redraw everything
    python3 scripts/render_map_frames.py --moments=3,4

Nobody can screenshot the browser page in the build environment, so this draws the same data
(09_shared_state_timeline/viewer/map_data: index.js and the per-day chunks), with the same
interpolation by time between kept vertices that map_view.html uses, over the real land,
channels and streets from 99_reference/geo. Symbols are simplified; positions are not.

Each frame also carries its own audit: how many vessels are on land, how many moving vehicles
are more than 35 m from a street, how many aircraft on the ground are away from an airfield.
Those three numbers must be zero; the script exits 1 if any frame has a non-zero count.

Frames go to 09_shared_state_timeline/viewer/_snapshots/frames/<moment>_<zoom>.png and a summary
to frames.json in the same folder.
"""
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import geo  # noqa: E402
import check_map as cm  # noqa: E402

OUT = os.path.join(cm.VIEW, "_snapshots", "frames")
D0 = 1820880000
DAY = 86400
# (label, UTC day index from landfall day, HH:MM UTC)
MOMENTS = [("D-2 12:00Z", -2, "12:00"), ("D0 03:00Z", 0, "03:00"), ("D0 15:00Z", 0, "15:00"), ("D+1 18:00Z", 1, "18:00"), ("D+12 23:00Z", 12, "23:00"),
           ("D+30 15:00Z", 30, "15:00"), ("D+44 06:10Z", 44, "06:10"), ("D+58 15:00Z", 58, "15:00"), ("D+90 15:00Z", 90, "15:00")]
ZOOMS = [("region", (-97.72, 27.50, -96.72, 28.10)), ("bay", (-97.56, 27.62, -97.00, 27.92)), ("harbor", (-97.47, 27.765, -97.355, 27.835))]
VCOL = {"tanker": "#c0392b", "lng": "#e74c3c", "bulk": "#a04000", "cargo": "#d35400", "roro": "#d35400", "tug": "#f1c40f", "barge": "#b7950b", "pilot": "#f39c12",
        "ferry": "#16a085", "coast_guard": "#ecf0f1", "navy": "#7f8c8d", "fishing": "#2e86c1", "charter": "#5dade2", "recreational": "#85c1e9"}
UCOL = {"engine": "#e74c3c", "ladder": "#e74c3c", "medic": "#2ecc71", "ambulance": "#2ecc71", "patrol": "#3498db", "bus": "#f39c12", "rescue": "#e67e22"}


def utc_offset(t):
    return -5 if t < 1825570800 else -6


def state_at(parts, sec):
    """(lat, lon, moving, heading_deg, extra) by the viewer's rule, or None."""
    p = cm.position(parts, sec)
    if p is None:
        return None
    hd, spd = None, 0.0
    for part in parts:
        if part[0, 0] <= sec <= part[-1, 0]:
            i = int(np.searchsorted(part[:, 0], sec, side="right")) - 1
            i = min(max(i, 0), len(part) - 2) if len(part) > 1 else 0
            if len(part) > 1:
                a, b = part[i], part[i + 1]
                if abs(b[1] - a[1]) + abs(b[2] - a[2]) > 2:
                    hd = math.degrees(math.atan2((b[2] - a[2]) * 0.885, (b[1] - a[1]))) % 360
                    m = math.hypot((b[1] - a[1]) * 1.11, (b[2] - a[2]) * 0.98)
                    spd = m / max(1.0, float(b[0] - a[0]))
            break
    return p[0], p[1], p[2], hd, p[3], spd


def trail(parts, sec, back):
    """Polyline of the last `back` seconds of track ending at sec."""
    for part in parts:
        if part[0, 0] <= sec <= part[-1, 0]:
            t = part[:, 0]
            i0 = max(0, int(np.searchsorted(t, sec - back, side="left")) - 1)
            i1 = int(np.searchsorted(t, sec, side="right"))
            seg = part[i0:i1]
            p = cm.position([part], sec)
            xs = list(seg[:, 2] / 1e5) + [p[1]]
            ys = list(seg[:, 1] / 1e5) + [p[0]]
            return xs, ys
    return [], []


class Scene:
    def __init__(self):
        self.S = cm.State()
        self.G = self.S.G
        self.idx = self.S.index
        G = self.G
        self.coarse = [it["xy"] for it in G.land_coarse.items if len(it["xy"]) >= 4]
        self.land = [it["xy"] for it in G.land.items]
        self.water = [it["xy"] for it in G.water_override.items]
        self.chan = [it["xy"] for it in G.channels.items]
        self.anch = [it["xy"] for it in G.anchorages.items]
        self.roads = {"major": [], "local": []}
        for _, cls, pts in G.roads.features:
            a = np.array(pts)[:, ::-1]
            self.roads["local" if cls == "local" else "major"].append(a)

    def base(self, ax, box, zoom):
        from matplotlib.collections import LineCollection, PolyCollection
        ax.set_facecolor("#9ec9e2")

        def inbox(xy):
            return not (xy[:, 0].max() < box[0] or xy[:, 0].min() > box[2] or xy[:, 1].max() < box[1] or xy[:, 1].min() > box[3])
        bx = geo.BOX   # lon0, lat0, lon1, lat1 of the detailed window; outside it only the coarse coast exists
        ax.add_collection(PolyCollection([p for p in self.coarse if inbox(p)], facecolors="#e3dcc6", edgecolors="none", zorder=0.5))
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1], facecolor="#9ec9e2", edgecolor="none", zorder=0.8))
        ax.add_collection(PolyCollection([p for p in self.land if inbox(p)], facecolors="#ece6d2", edgecolors="#9aa58f", linewidths=0.2, zorder=1))
        ax.add_collection(PolyCollection([p for p in self.water if inbox(p)], facecolors="#9ec9e2", edgecolors="none", zorder=2))
        ax.add_collection(PolyCollection([p for p in self.chan if inbox(p)], facecolors="#4f8fc4", edgecolors="none", alpha=0.75, zorder=3))
        for a in self.anch:
            ax.plot(a[:, 0], a[:, 1], c="#8e44ad", lw=0.6, ls="--", zorder=3)
        if zoom != "region":
            ax.add_collection(LineCollection([r for r in self.roads["local"] if inbox(r)], colors="#b8b0a0", linewidths=0.35 if zoom == "bay" else 0.7, zorder=4))
        ax.add_collection(LineCollection([r for r in self.roads["major"] if inbox(r)], colors="#8d7b68", linewidths=0.6 if zoom == "region" else 1.1, zorder=5))
        ax.set_xlim(box[0], box[2]); ax.set_ylim(box[1], box[3]); ax.set_aspect(1 / 0.885)
        ax.tick_params(labelsize=6)

    def frame(self, mi, label, day_i, hhmm):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        G, idx = self.G, self.idx
        h, m = map(int, hhmm.split(":"))
        sec = h * 3600 + m * 60
        T = D0 + day_i * DAY + sec
        day = cm.read_js(cm.day_file(day_i))
        V = {k: [cm.decode(p, 3) for p in v] for k, v in day["v"].items()}
        C = {k: [cm.decode(p, 3) for p in v] for k, v in day["c"].items()}
        A = {k: [cm.decode(p, 4) for p in v] for k, v in day["a"].items()}
        ves = {k: state_at(p, sec) for k, p in V.items()}
        veh = {k: state_at(p, sec) for k, p in C.items()}
        air = {k: state_at(p, sec) for k, p in A.items()}
        ves = {k: v for k, v in ves.items() if v}; veh = {k: v for k, v in veh.items() if v}; air = {k: v for k, v in air.items() if v}
        # audit of this instant
        audit = {"vessels": len(ves), "vessels_on_land": 0, "vehicles": len(veh), "vehicles_moving": 0, "vehicles_off_street": 0,
                 "aircraft": len(air), "aircraft_airborne": 0, "aircraft_ground_bad": 0}
        if ves:
            la = np.array([v[0] for v in ves.values()]); lo = np.array([v[1] for v in ves.values()])
            audit["vessels_on_land"] = int(G.is_land_many(la, lo).sum())
        mv = [(k, v) for k, v in veh.items() if v[2]]              # the checker's strict rule: any change of position
        audit["vehicles_moving"] = sum(1 for v in veh.values() if v[5] >= 1.0)   # shown as moving: 1 m/s or more
        audit["vehicles_checked"] = len(mv)
        if mv:
            d = G.roads.distance_many(np.array([v[0] for _, v in mv]), np.array([v[1] for _, v in mv]))
            audit["vehicles_off_street"] = int((d > 35).sum())
        for k, v in air.items():
            if v[4][3] < 0:
                if G.in_box(v[0], v[1]):
                    dr, _ = G.runway_distance_m(v[0], v[1])
                    pad = float(np.hypot((self.S.pads[:, 0] - v[0]) * geo.M_PER_DEG_LAT, (self.S.pads[:, 1] - v[1]) * geo.M_PER_DEG_LON).min())
                    if dr > 500 and pad > 300:
                        audit["aircraft_ground_bad"] += 1
            else:
                audit["aircraft_airborne"] += 1
        inc = [r for r in day.get("i", []) if r[0] <= sec <= r[1]]
        drones = []
        for f in day.get("d", []):
            p = cm.decode(f["p"], 4)
            s = cm.position([p], sec)
            if s:
                drones.append(s)
        radar = []
        for f in day.get("r", []):
            for part in f["p"]:
                p = cm.decode(part, 3)
                s = cm.position([p], sec)
                if s:
                    radar.append(s)
        dets = []
        for f in day.get("x", []):
            p = cm.decode(f["p"], 4)
            s = cm.position([p], sec) if len(p) > 1 else ((p[0, 1] / 1e5, p[0, 2] / 1e5) if abs(p[0, 0] - sec) <= 60 else None)
            if s:
                dets.append((s[0], s[1]))
        events = [e for e in idx.get("events", []) if "la" in e and abs(e["t"] - T) <= 12 * 3600]
        out_total = 0
        for area, slots in (day.get("o") or {}).items():
            if slots:
                v = slots[min(len(slots) - 1, 23, sec // 3600)]   # hourly slots, as in map_view.html
                out_total += (v[0] if isinstance(v, list) else v) or 0
        storm = None
        tr = idx.get("storm_track") or []
        hh = (T - D0) / 3600.0
        for a, b in zip(tr, tr[1:]):
            if a[0] <= hh <= b[0]:
                f = (hh - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
                storm = (a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f)
        loc = dt.datetime.fromtimestamp(T, dt.timezone(dt.timedelta(hours=utc_offset(T))))
        files = []
        for zname, box in ZOOMS:
            fig, ax = plt.subplots(figsize=(13, 8.6))
            self.base(ax, box, zname)
            ms = {"region": 5, "bay": 7, "harbor": 10}[zname]
            # trails
            for k, v in ves.items():
                xs, ys = trail(V[k], sec, 1800)
                ax.plot(xs, ys, c=VCOL.get(idx["vessels"].get(k, {}).get("c"), "#555"), lw=0.9, alpha=0.7, zorder=6)
            for k, v in veh.items():
                if v[5] >= 1.0:
                    xs, ys = trail(C[k], sec, 300)
                    ax.plot(xs, ys, c=UCOL.get(idx["units"].get(k, {}).get("k"), "#444"), lw=1.0, alpha=0.8, zorder=6)
            for k, v in air.items():
                if v[4][3] >= 0:
                    xs, ys = trail(A[k], sec, 600)
                    ax.plot(xs, ys, c="#6c3483", lw=0.8, alpha=0.6, zorder=6)
            # symbols
            if inc:
                ax.plot([r[3] / 1e5 for r in inc], [r[2] / 1e5 for r in inc], ".", c="#e67e22", ms=ms * 0.45, zorder=7, label=f"open incidents ({len(inc)})")
            for k, v in ves.items():
                col = VCOL.get(idx["vessels"].get(k, {}).get("c"), "#555")
                ax.plot(v[1], v[0], marker=(3, 0, -(v[3] or 0)), c=col, ms=ms * (1.3 if v[5] >= 0.5 else 0.9), mec="k", mew=0.4, zorder=9, ls="")
            for k, v in veh.items():
                col = UCOL.get(idx["units"].get(k, {}).get("k"), "#95a5a6")
                ax.plot(v[1], v[0], "s", c=col, ms=ms * (0.75 if v[5] >= 1.0 else 0.45), mec="k", mew=0.3, zorder=8)
            for k, v in air.items():
                heli = idx["aircraft"].get(k, {}).get("k") == "heli"
                up = v[4][3] >= 0
                ax.plot(v[1], v[0], "X" if heli else "P", c="#6c3483" if up else "#bb8fce", ms=ms * (1.1 if up else 0.6), mec="k", mew=0.3, zorder=10)
            if drones:
                ax.plot([d[1] for d in drones], [d[0] for d in drones], "x", c="#00bcd4", ms=ms * 0.8, mew=1.2, zorder=10, label=f"authorised drones ({len(drones)})")
            if radar:
                ax.plot([d[1] for d in radar], [d[0] for d in radar], "o", mfc="none", mec="#111", ms=ms * 0.8, mew=0.6, zorder=8, label=f"radar contacts ({len(radar)})")
            if dets:
                ax.plot([d[1] for d in dets], [d[0] for d in dets], "+", c="#c2185b", ms=ms * 0.9, mew=1.0, zorder=10, label=f"sensor detections in the air ({len(dets)})")
            if events:
                ax.plot([e["lo"] for e in events], [e["la"] for e in events], "*", c="#f4d03f", mec="#7d6608", ms=ms * 1.3, mew=0.5, zorder=11, label=f"events within 12 h ({len(events)})")
            if storm and storm[2] >= 34:
                th = np.linspace(0, 2 * np.pi, 80)
                for r_nm, st in ((18, "-"), (60, "--")):
                    ax.plot(storm[1] + r_nm / 60 / 0.885 * np.cos(th), storm[0] + r_nm / 60 * np.sin(th), c="#1b2631", lw=1.0, ls=st, zorder=12)
                ax.plot(storm[1], storm[0], "o", c="#1b2631", ms=6, zorder=12, label=f"Rafael centre, {storm[2]:.0f} kt (rings 18 and 60 nm)")
            n_mv = sum(1 for v in ves.values() if v[5] >= 0.5)
            ax.plot([], [], marker=(3, 0, 0), c="#c0392b", ls="", label=f"vessels ({len(ves)}; {n_mv} under way)")
            ax.plot([], [], "s", c="#2ecc71", ls="", label=f"vehicles ({len(veh)}; {audit['vehicles_moving']} moving)")
            ax.plot([], [], "P", c="#6c3483", ls="", label=f"aircraft ({len(air)}; {audit['aircraft_airborne']} airborne)")
            ax.legend(loc="lower right", fontsize=7, framealpha=0.9)
            ax.set_title(f"{label}  |  {loc:%a %d %b %Y %H:%M} local  |  customers without power: {out_total:,}  |  audit: vessels on land {audit['vessels_on_land']}, "
                         f"moving vehicles off street {audit['vehicles_off_street']}, aircraft on ground away from airfield {audit['aircraft_ground_bad']}", fontsize=8)
            fn = f"{mi:02d}_{label.split('Z')[0].replace(' ', '_').replace(':', '').replace('+', 'p').replace('-', 'm')}_{zname}.png"
            fig.savefig(os.path.join(OUT, fn), dpi=95, bbox_inches="tight")
            plt.close(fig)
            files.append(fn)
        return dict(audit, label=label, incidents=len(inc), drones=len(drones), detections=len(dets), radar=len(radar), events=len(events), customers_out=out_total, files=files)


def main():
    force = "--force" in sys.argv
    budget = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--budget=")), 140.0)
    only = next(([int(x) for x in a.split("=")[1].split(",")] for a in sys.argv if a.startswith("--moments=")), None)
    os.makedirs(OUT, exist_ok=True)
    sp = os.path.join(OUT, "frames.json")
    summary = json.load(open(sp)) if os.path.exists(sp) and not force else {}
    t0 = time.time()
    sc = None
    for mi, (label, d, hm) in enumerate(MOMENTS):
        if only is not None and mi not in only:
            continue
        key = str(mi)
        src_m = os.path.getmtime(cm.day_file(d))
        if not force and key in summary and summary[key].get("data_mtime") == int(src_m) and all(os.path.exists(os.path.join(OUT, f)) for f in summary[key]["files"]):
            continue
        if time.time() - t0 > budget:
            print("INCOMPLETE: run again")
            sys.exit(2)
        if sc is None:
            sc = Scene()
        r = sc.frame(mi, label, d, hm)
        r["data_mtime"] = int(src_m)
        summary[key] = r
        json.dump(summary, open(sp, "w"), indent=1)
        print(f"{label:<12} vessels {r['vessels']:>3} (on land {r['vessels_on_land']})  vehicles {r['vehicles']:>3} moving {r['vehicles_moving']:>3} (of {r['vehicles_checked']} checked, off street {r['vehicles_off_street']})  "
              f"aircraft {r['aircraft']:>2} airborne {r['aircraft_airborne']:>2} (bad ground {r['aircraft_ground_bad']})  incidents {r['incidents']:>4}  drones {r['drones']}  radar {r['radar']}  "
              f"events {r['events']}  out {r['customers_out']:,}", flush=True)
    bad = sum(v["vessels_on_land"] + v["vehicles_off_street"] + v["aircraft_ground_bad"] for v in summary.values())
    print(f"COMPLETE: {len(summary)} moments x {len(ZOOMS)} zooms; audit failures {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
