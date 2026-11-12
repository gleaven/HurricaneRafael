"""The port simulation behind the maritime streams (AIS, port surveillance, port conditions,
arrivals, cargo manifests).

One schedule for every vessel in 06_data_streams/vessels.json from D-30 to D+119, built from
  - the canon port timeline (00_scenario/canon_timeline.json: port, spill, dark_vessel,
    channel_attack, relief), encoded as the clock constants in maritime_core.py
  - the registries (vessels, berths, slips, anchorage positions, sea gates)
  - real geography through scripts/geo.py (maritime_geom.py verifies every path)

    sim = PortSim(); sim.run()
    sim.vessels[...] .itin     itineraries (Stay / Move)
    sim.calls                  port calls (for arrivals and manifests)
    sim.transits               pilot-order ship movements (for the traffic log, tugs, pilots)

Ordinary traffic comes from simple agents (ships cycle between sea and berth, waiting at the
anchorage when berths or the channel are not available). Canon events are scripted on top and
the agents are constrained so they can never contradict them.
"""
import math
import re

import numpy as np

import geo
import maritime_geom as mg
from common import internal, iso, reg, rng, ts
from maritime_core import *  # noqa: F401,F403
from maritime_core import (BLACKOUT_FROM, BLAST, BOARD, DARK_END, DARK_START, INNER_E_PERMITS, KN, LAST_IN_PRESTORM,
                           LAST_OUT_PRESTORM, LON_BRIDGE, LON_FERRY, LON_JETTY, OFFING, REOPEN1, REOPEN2, RETURN_D3_A,
                           RETURN_D3_B, SEA, T0, T_END, T_WARM, XRAY, YANKEE, ZULU, Move, Stay, Vessel, follow, make_move)

H = 3600.0
DAY = 86400.0

PORT_NAMES = {  # last/next port -> UN/LOCODE-style code used in AIS destinations and arrivals
    "Rotterdam": "NLRTM", "Milford Haven": "GBMLF", "Algeciras": "ESALG", "Panama Canal": "PAPCN", "Ulsan": "KRUSN",
    "Ningbo": "CNNGB", "Sikka": "INSIK", "Santos": "BRSSZ", "Cartagena": "COCAR", "Houston": "USHOU", "Galveston": "USGLS",
    "Tampa": "USTPA", "Tampico": "MXTAM", "Altamira": "MXATM", "Veracruz": "MXVER", "Tuxpan": "MXTUX", "New Orleans": "USMSY",
    "Brownsville": "USBRO", "Koper": "SIKOP", "Manzanillo": "MXZLO", "Incheon": "KRINC", "Zeebrugge": "BEZEE",
    "Swinoujscie": "PLSWI", "Tokyo Bay": "JPTYO", "Gibraltar": "GIGIB", "Mobile": "USMOB", "Coatzacoalcos": "MXCOA",
    "Pajaritos": "MXPAJ", "Dos Bocas": "MXDBT", "Beaumont": "USBPT", "Freeport (Bahamas)": "BSFPO",
    "Houston lightering area": "USGOM", "Galveston offshore": "USGOM"}


class Call:
    """One port call: what the arrivals file records."""
    seq = 18000

    def __init__(self, v, eta, last_port, next_port, cargo, direction):
        Call.seq += int(v.rs.integers(3, 17))
        self.id = f"NOA-2027-CC-{Call.seq}"
        self.v, self.eta, self.last_port, self.next_port = v, eta, last_port, next_port
        self.cargo, self.direction = cargo, direction
        self.noa_time = eta - 96 * H - float(v.rs.uniform(0, 30 * H))
        self.eta_revised = None
        self.ata_anch = self.anch = None
        self.atd_anch = None
        self.ata = self.atd = self.atd_port = None
        self.berth = None
        self.status = "SUBMITTED"
        self.hold = []            # (time, text)
        self.draft_arr = None
        self.shift = None         # (time, berth) later shift inside the port


class PortBase:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.GM = mg.Geom()
        self.G = self.GM.G
        V = reg("vessels")["vessels"]
        self.vessels = {r["vessel_id"]: Vessel(r) for r in V}
        T = reg("terminal_registry")
        self.T = T
        self.berths = {b["berth_id"]: b for b in T["berths"]}
        self.slips = {s["slip_id"]: s for s in T["slips"]}
        self.anch = {a["position_id"]: (a["latitude"], a["longitude"]) for a in T["anchorage_positions"]}
        self.gates = {g["gate_id"]: (g["latitude"], g["longitude"]) for g in T["sea_gates"]}
        self.terminals = {t["terminal_id"]: t for t in T["terminals"]}
        truth = internal("vessels")
        self.sets = truth["scenario_sets"]
        self.calls, self.transits, self.notes = [], [], []
        self.berth_busy = {b: [] for b in self.berths}          # list of (t0, t1, vessel id)
        self.anch_busy = {a: [] for a in self.anch}
        self.free_at = {}                                        # service craft availability
        self.ship_passes = []                                    # (time at ferry crossing, vessel id)
        self.home = {}
        self._paths = {}
        self._paths_n0 = 0
        self.load_paths()
        for b in self.berths.values():
            r = b.get("reach_id", "")
            b["zone"] = ("laq" if r.startswith("CESWG_LA") else "inner_e" if r.startswith("CESWG_CC_08") else
                         "inner_w" if r.startswith("CESWG_CC") else "other")

    # ------------------------------------------------------------------ verified-path cache on disk
    # Building and verifying a path against the land and channel polygons is the slow part of the
    # simulation. Paths depend only on the geometry files and the registries, so they are kept in
    # scripts/streams/_cache/ and reused; delete the folder to rebuild everything from scratch.
    def _cache_file(self):
        import hashlib
        import os
        sig = hashlib.sha1()
        for rel in ("land_local.geojson", "water_overrides_local.geojson", "channels_usace.geojson", "channel_lines_usace.geojson",
                    "anchorages_fairways_noaa.geojson", "landmarks.geojson"):
            fp = os.path.join(geo.GEO_DIR, rel)
            sig.update(f"{rel}:{os.path.getsize(fp)}".encode())
        for rel in ("terminal_registry.json", "vessels.json"):
            fp = os.path.join(geo.ROOT, "06_data_streams", rel)
            sig.update(f"{rel}:{os.path.getsize(fp)}".encode())
        here = os.path.dirname(os.path.abspath(__file__))
        for rel in ("maritime_geom.py",):
            sig.update(open(os.path.join(here, rel), "rb").read())
        d = os.path.join(here, "_cache")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"maritime_paths_{sig.hexdigest()[:10]}.pkl")

    def load_paths(self):
        import os
        import pickle
        fp = self._cache_file()
        if os.path.exists(fp):
            try:
                with open(fp, "rb") as fh:
                    data = pickle.load(fh)
                for k, (pts, head, tail, nofix) in data.items():
                    P = mg.Path(pts)
                    P.head, P.tail, P.nofix = head, tail, nofix
                    self._paths[k] = P
            except Exception:
                self._paths = {}
        self._paths_n0 = len(self._paths)

    def save_paths(self):
        import os
        import pickle
        if len(self._paths) == self._paths_n0:
            return
        data = {k: (p.pts, p.head, p.tail, p.nofix) for k, p in self._paths.items() if isinstance(p, mg.Path)}
        fp = self._cache_file()
        tmp = fp + ".tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(data, fh, protocol=4)
        os.replace(tmp, fp)
        self._paths_n0 = len(self._paths)

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ------------------------------------------------------------------ geometry shortcuts
    def bpos(self, bid):
        b = self.berths[bid]
        return (b["latitude"], b["longitude"])

    def spos(self, sid):
        s = self.slips[sid]
        return (s["latitude"], s["longitude"])

    def place_pos(self, pid):
        if pid in self.berths:
            return self.bpos(pid)
        if pid in self.slips:
            return self.spos(pid)
        return self.anch[pid]

    def ship_path(self, bid):
        """Sea buoy -> berth along the channel centerlines (deep-verified where the berth is deep)."""
        key = ("ship", bid)
        if key not in self._paths:
            b = self.berths[bid]
            deep = b["min_channel_depth_ft"] >= 40
            self._paths[key] = self.GM.nav_path(SEA, self.bpos(bid), 40 if deep else 0, deep=deep, end_at=self.bpos(bid))
        return self._paths[key]

    def lane(self, bid, inbound, deep=True):
        """Keep to starboard in the bay reaches: inbound and outbound ships use opposite sides."""
        key = ("lane", bid, inbound)
        if key not in self._paths:
            self._paths[key] = self.GM.offset(self.ship_path(bid), 38.0 if inbound else -38.0, deep=deep)
        return self._paths[key]

    def offset_path(self, key, path, d_m):
        k = ("offs",) + tuple(key) + (d_m,)
        if k not in self._paths:
            self._paths[k] = self.GM.offset(path, d_m)
        return self._paths[k]

    def open_path(self, a, b, deep=False, seg=12000.0):
        key = ("open", round(a[0], 5), round(a[1], 5), round(b[0], 5), round(b[1], 5), deep)
        if key not in self._paths:
            self._paths[key] = self.GM.open_leg(a, b, deep=deep, max_seg_m=seg)
        return self._paths[key]

    def gate_path(self, gate):
        """OFFING -> sea gate (the vessel leaves coverage at the gate)."""
        key = ("gate", gate)
        if key not in self._paths:
            self._paths[key] = self.open_path(OFFING, self.gates[gate], seg=14000.0)
        return self._paths[key]

    def water(self, a, b, clearance=150.0, key=None):
        k = ("w",) + (key if key is not None else (round(a[0], 5), round(a[1], 5), round(b[0], 5), round(b[1], 5)))
        if k not in self._paths:
            try:
                self._paths[k] = self.GM.water_path(a, b, clearance)
            except ValueError:
                # Corpus Christi marina: only the gap beside slip 1 is short enough to pass between reports
                via = self.spos("SLIP-CCM-01")
                if geo.dist_m(a, via) < 500:
                    self._paths[k] = mg.join(self.GM.water_path(a, via, 40.0), self.GM.water_path(via, b, clearance))
                elif geo.dist_m(b, via) < 500:
                    self._paths[k] = mg.join(self.GM.water_path(a, via, clearance), self.GM.water_path(via, b, 40.0))
                else:
                    raise
        return self._paths[k]

    def nav(self, a, b, draft_ft=0.0, start_at=None, end_at=None, key=None):
        k = ("n",) + (key if key is not None else (round(a[0], 5), round(a[1], 5), round(b[0], 5), round(b[1], 5), draft_ft,
                                                    start_at is not None, end_at is not None))
        if k not in self._paths:
            self._paths[k] = self.GM.nav_path(a, b, draft_ft, deep=False, start_at=start_at, end_at=end_at)
        return self._paths[k]

    # ------------------------------------------------------------------ speeds
    @staticmethod
    def channel_speed(lat, lon):
        """Typical deep-draft speed (kn) by position along the ship channel."""
        if lon > -96.9636:
            return 9.0
        if lon > -97.030:
            return 10.5                       # sea bar
        if lon > -97.078:
            return 8.5                        # jetties, inner basin, ferry crossing
        if lon > -97.355:
            if lat > 27.835 and lon < -97.215:
                return 6.5 if lat > 27.865 else 8.0     # La Quinta channel
            return 11.0                       # bay reaches
        if lon > -97.3957:
            return 7.0                        # approach to the Harbor Bridge
        return 4.8                            # Inner Harbor

    def ship_vfun(self, path, factor=1.0):
        L, head, tail = path.length, path.head, path.tail

        def f(lat, lon, s):
            if s < head + 40 or s > L - tail - 40:
                return 1.3
            if s < head + 500 or s > L - tail - 500:
                return 3.0
            return self.channel_speed(lat, lon) * factor
        return f

    # ------------------------------------------------------------------ occupancy
    @staticmethod
    def free(busy, t0, t1):
        return all(t1 <= a or t0 >= b for a, b, _ in busy)

    def home_position(self, v):
        """Where a locally based vessel lies when not working. Vessels sharing a mooring are
        spread along the dock face when the neighbouring spot is also good water."""
        if v.id in self.home:
            return self.home[v.id]
        hid = v.rec.get("home_berth_id")
        if not hid:
            return None
        base = self.place_pos(hid)
        hdg = self.berths[hid].get("heading_deg", 0.0) if hid in self.berths else float(v.rs.uniform(0, 360))
        used = [h[0] for k, h in self.home.items() if h[2] == hid]
        pos = base
        if used and hid in self.berths:
            for k in range(1, 8):
                for sign in (1, -1):
                    cand = mg.dest_point(base, hdg + (0 if sign > 0 else 180), 36.0 * ((k + 1) // 2) * 1.0)
                    if all(geo.dist_m(cand, u) > 25 for u in used) and self.GM.point_ok(cand) and \
                            self.G.channel_at(cand[0], cand[1], 120) and self.GM.clear(base, cand, 3.0):
                        pos = cand
                        break
                if pos is not base:
                    break
        self.home[v.id] = (pos, hdg, hid)
        return self.home[v.id]
