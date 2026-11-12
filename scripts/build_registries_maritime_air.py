"""Build the maritime and aviation registries from real geography.

Writes (all under 06_data_streams/):
  vessels.json, terminal_registry.json, aircraft_registry.json, drone_operators.json
  _internal/vessels_truth.json, _internal/terminal_registry_truth.json,
  _internal/aircraft_registry_truth.json, _internal/drone_operators_truth.json

The four top-level files are reference data a participant may be given: they carry no scenario
truth. Everything internal (roles, hidden links, thread ids, and the map from every old id,
name, MMSI or ICAO address to the new record) is in _internal/.

Every coordinate is taken from, or derived with scripts/geo.py from, the real data in
99_reference/geo/ (USACE reaches, NOAA land areas and anchorages, landmark points). The basis of
each position is recorded next to it. Deterministic: same inputs, same output.

Usage: python3 scripts/build_registries_maritime_air.py
"""
import hashlib
import json
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402

ROOT = geo.ROOT
OUT = os.path.join(ROOT, "06_data_streams")
INT = os.path.join(OUT, "_internal")
GENERATED = "2026-11-09"
G = geo.Geo(build_roads=False)
R5 = lambda x: round(float(x), 5)


def rng_for(key):
    return random.Random(int(hashlib.sha1(key.encode()).hexdigest()[:12], 16))


# ======================================================================================
# geometry helpers
# ======================================================================================
def reach_point(lat, lon, min_depth=0.0):
    """Nearest point on the edge of a USACE reach maintained to >= min_depth.
    Returns (metres, (lat, lon), reach_id, bearing of that edge 0-180)."""
    px, py = lon * geo.M_PER_DEG_LON, lat * geo.M_PER_DEG_LAT
    ax, ay, bx, by = G._ce
    d, cx, cy = geo._seg_dist(px, py, ax, ay, bx, by)
    ok = np.array([(G.channel_props[r].get("depth_ft") or 0) >= min_depth for r in G._ce_id])
    d = np.where(ok, d, 1e12)
    i = int(np.argmin(d))
    brg = math.degrees(math.atan2(bx[i] - ax[i], by[i] - ay[i])) % 180.0
    return float(d[i]), (float(cy[i] / geo.M_PER_DEG_LAT), float(cx[i] / geo.M_PER_DEG_LON)), G._ce_id[i], brg


def dock(code, idx=0, name_has=None):
    """Real dock landmark by its USACE dock code (99_reference/geo/landmarks.geojson)."""
    hits = [l for l in G.landmarks if code in str(l.get("source_id", ""))]
    if name_has:
        hits = [l for l in hits if name_has.lower() in l["name"].lower()]
    if not hits:
        raise SystemExit(f"dock {code} not found in landmarks")
    return hits[idx]


def alongside(lat, lon, min_depth, off=35.0, max_to_reach=140.0, min_clear=25.0):
    """Position of a vessel lying alongside the dock at (lat, lon): walk from the dock point
    toward the nearest reach of the required depth, take the first water plus `off` metres, keep
    it within max_to_reach of the reach, and make sure there is water around it."""
    inside = G.channel_at(lat, lon, 0, min_depth)
    d, p, rid, brg = reach_point(lat, lon, min_depth)
    if inside:
        return {"lat": lat, "lon": lon, "reach": inside, "heading": brg, "to_reach": 0.0, "from_dock": 0.0}
    n = max(1, int(d / 2.5))
    first = None
    for k in range(n + 1):
        la, lo = lat + (p[0] - lat) * k / n, lon + (p[1] - lon) * k / n
        if not G.is_land(la, lo):
            first = k * d / n
            break
    if first is None:
        raise SystemExit(f"no water between dock {lat},{lon} and reach {rid}")
    t = min(first + off, d)
    if d - t > max_to_reach:
        t = d - max_to_reach
    while t < d:
        la, lo = lat + (p[0] - lat) * t / d, lon + (p[1] - lon) * t / d
        if not G.is_land(la, lo) and G.land_clearance_m(la, lo) >= min_clear:
            break
        t += 5.0
    t = min(t, d)
    la, lo = lat + (p[0] - lat) * t / d, lon + (p[1] - lon) * t / d
    if G.is_land(la, lo):
        raise SystemExit(f"alongside position on land for dock {lat},{lon}")
    return {"lat": la, "lon": lo, "reach": rid, "heading": brg, "to_reach": d - t, "from_dock": t}


def nearest_water(lat, lon, min_clear=25.0, max_r=220.0, taken=(), sep=22.0, toward=None):
    """Nearest water point with min_clear metres of water around it (25 m raster), at least
    `sep` metres from points already taken."""
    r0, c0 = G.px(lat, lon)
    k = int(max_r / geo.RASTER_M) + 1
    best = None
    for r in range(max(r0 - k, 0), min(r0 + k + 1, G.ny)):
        for c in range(max(c0 - k, 0), min(c0 + k + 1, G.nx)):
            if G.dist_land[r, c] < min_clear:
                continue
            la, lo = G.px_to_ll(r, c)
            dd = geo.dist_m((lat, lon), (la, lo))
            if dd > max_r or G.is_land(la, lo):
                continue
            if any(geo.dist_m((la, lo), t) < sep for t in taken):
                continue
            if toward is not None:
                dd += 0.3 * geo.dist_m((la, lo), toward)
            if best is None or dd < best[0]:
                best = (dd, la, lo)
    return None if best is None else (best[1], best[2])


BAY = (27.77, -97.25)


def water_reachable(p):
    return route_clearance(p) is not None


def route_clearance(p):
    """Largest land clearance (m) at which G.water.route finds a clean water path from p to the open bay."""
    for cl in (150.0, 100.0, 60.0, 40.0):
        r = G.water.route(p, BAY, cl)
        if r is not None and G.path_land_hits(r) == 0 and geo.dist_m(p, r[0]) <= 450:
            return cl
    return None


# ======================================================================================
# identifiers
# ======================================================================================
FLAGS = {  # code: (flag name, MMSI MID, call-sign maker)
    "MH": ("Marshall Islands", "538", lambda r: "V7" + cs(r, "LLD")),
    "PA": ("Panama", "352", lambda r: "3E" + cs(r, "LLD")),
    "LR": ("Liberia", "636", lambda r: "D5" + cs(r, "LLD")),
    "BS": ("Bahamas", "311", lambda r: "C6" + cs(r, "LLD")),
    "MT": ("Malta", "248", lambda r: "9H" + cs(r, "LLD")),
    "GR": ("Greece", "240", lambda r: "SV" + cs(r, "LLD")),
    "SG": ("Singapore", "563", lambda r: "9V" + cs(r, "LLD")),
    "HK": ("Hong Kong", "477", lambda r: "VR" + cs(r, "LLD")),
    "NO": ("Norway", "257", lambda r: "LA" + cs(r, "LLD")),
    "CY": ("Cyprus", "209", lambda r: "5B" + cs(r, "LLD")),
    "PW": ("Palau", "511", lambda r: "T8" + cs(r, "LLD")),
    "AG": ("Antigua and Barbuda", "305", lambda r: "V2" + cs(r, "LLD")),
    "US": ("United States", "367", lambda r: "W" + cs(r, "LLDDDD")),
    "USG": ("United States", "369", lambda r: "N" + cs(r, "LLL")),
}


def cs(r, pat):
    out = ""
    for ch in pat:
        out += r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") if ch == "L" else str(r.randrange(2, 10))
    return out


def imo_number(r):
    six = [9] + [r.randrange(2, 9)] + [r.randrange(0, 10) for _ in range(4)]
    chk = sum(d * w for d, w in zip(six, (7, 6, 5, 4, 3, 2))) % 10
    return "IMO" + "".join(map(str, six)) + str(chk)


def imo_valid(s):
    d = [int(c) for c in s[3:]]
    return len(d) == 7 and sum(a * w for a, w in zip(d[:6], (7, 6, 5, 4, 3, 2))) % 10 == d[6]


USED_MMSI, USED_IMO, USED_CS = set(), set(), set()
KEEP_MMSI = {"MT Kalvora Star": "538847203", "MT Ostrel Bay": "352091748", "MV Gulf Provider": "308441927",
             "FV Pelican Ridge": "338724891", "Corrin Bay": "338190847"}   # canon ships keep the MMSIs already in use


def ident(name, flag, want_imo):
    r = rng_for("vessel:" + name)
    mid = FLAGS[flag][1]
    m = KEEP_MMSI.get(name)
    while not m or m in USED_MMSI:
        m = mid + "".join(str(r.randrange(0, 10)) for _ in range(6))
    USED_MMSI.add(m)
    imo = None
    if want_imo:
        imo = imo_number(r)
        while imo in USED_IMO:
            imo = imo_number(r)
        USED_IMO.add(imo)
    c = FLAGS[flag][2](r)
    while c in USED_CS:
        c = FLAGS[flag][2](r)
    USED_CS.add(c)
    return m, imo, c


# ======================================================================================
# 1. terminals, berths, slips, anchorage
# ======================================================================================
def build_terminals():
    berths, terminals, truth = [], [], {}

    def add_berth(bid, tid, lm, need_ft, max_loa, max_draft, cargo, btype="berth", off=35.0, min_clear=25.0, label=None):
        a = alongside(lm["lat"], lm["lon"], need_ft, off=off, min_clear=min_clear)
        d40 = G.channel_distance_m(a["lat"], a["lon"], 40)
        b = {"berth_id": bid, "terminal_id": tid, "berth_name": label or bid, "berth_type": btype,
             "latitude": R5(a["lat"]), "longitude": R5(a["lon"]), "heading_deg": round(a["heading"], 0),
             "max_loa_m": max_loa, "max_draft_m": max_draft, "min_channel_depth_ft": need_ft,
             "cargo_types": cargo, "reach_id": a["reach"],
             "reach_depth_ft": G.channel_props[a["reach"]].get("depth_ft"),
             "distance_to_reach_m": round(a["to_reach"]), "distance_to_40ft_channel_m": round(d40) if d40 < 1e6 else None,
             "reference_dock": str(lm.get("source_id", "")).split(";")[0].strip(),
             "position_basis": f"alongside the real dock point, {round(a['from_dock'])} m toward the channel (scripts/geo.py)"}
        berths.append(b)
        return b

    def term(tid, name, operator, kind, reach_area, items, **kw):
        t = {"terminal_id": tid, "terminal_name": name, "operator": operator, "terminal_type": kind, "waterway": reach_area}
        t.update(kw)
        ids = []
        for it in items:
            b = add_berth(*it[:7], **(it[7] if len(it) > 7 else {}))
            ids.append(b["berth_id"])
        t["berth_ids"] = ids
        lat = sum(b["latitude"] for b in berths if b["berth_id"] in ids) / len(ids)
        lon = sum(b["longitude"] for b in berths if b["berth_id"] in ids) / len(ids)
        t["latitude"], t["longitude"] = R5(lat), R5(lon)
        t["position_note"] = "mean of berth positions (in the water alongside the docks)"
        terminals.append(t)
        return t

    CR = ["crude oil"]
    # ---------------- Inner Harbor (USACE reaches CC_08 to CC_15, maintained 54 ft)
    term("TERM-01", "Rendal Terminals", "Rendal Terminals LLC", "Crude oil export", "Inner Harbor, Main Turning Basin (north bank)",
         [("TERM-01-B07", "TERM-01", dock("60770-174"), 45, 260, 15.2, CR, {"label": "Berth 7"}),
          ("TERM-01-B08", "TERM-01", dock("60770-175"), 45, 260, 15.2, CR, {"label": "Berth 8"})])
    term("TERM-02", "Chemical Basin Fuel Dock", "Port of Corpus Christi", "Fuel storage and barge dock",
         "Inner Harbor, Chemical Turning Basin (south bank)",
         [("TERM-02-B01", "TERM-02", dock("60770-792"), 12, 120, 4.0, ["diesel", "jet fuel", "gasoline"], {"label": "Barge Dock 1"})])
    term("TERM-04", "Tule Lake Crude Terminal", "Sandhollow Midstream Partners", "Crude oil export", "Inner Harbor, Tule Lake Turning Basin",
         [("TERM-04-B01", "TERM-04", dock("60770-266"), 45, 280, 15.8, CR, {"label": "Dock 1"}),
          ("TERM-04-B02", "TERM-04", dock("60770-720"), 45, 260, 15.2, CR, {"label": "Dock 2", "off": 45})])
    term("TERM-05", "Viola Liquids Hub", "Caracara Terminal Services", "Crude oil and condensate export", "Inner Harbor, Viola Channel and Turning Basin",
         [("TERM-05-B01", "TERM-05", dock("60770-710"), 45, 260, 15.2, CR + ["condensate"], {"label": "Dock 1"}),
          ("TERM-05-B02", "TERM-05", dock("60770-704"), 45, 250, 14.9, CR, {"label": "Dock 2"}),
          ("TERM-05-B03", "TERM-05", dock("60770-705"), 45, 250, 14.9, CR, {"label": "Dock 3"})])
    term("TERM-06", "Avery Point Products Terminal", "Marlowe Petroleum Logistics", "Refined products", "Inner Harbor, Avery Point Turning Basin",
         [("TERM-06-B01", "TERM-06", dock("60770-794"), 40, 200, 12.2, ["gasoline", "diesel", "jet fuel"], {"label": "Dock 1", "off": 45}),
          ("TERM-06-B02", "TERM-06", dock("60770-793"), 40, 200, 12.2, ["gasoline", "diesel"], {"label": "Dock 2"})])
    term("TERM-07", "Port of Corpus Christi Public Cargo Docks", "Port of Corpus Christi Authority", "General cargo, project cargo, military outload",
         "Inner Harbor, Main Turning Basin",
         [("TERM-07-B01", "TERM-07", dock("60770-821"), 40, 230, 11.5, ["general cargo", "ro-ro", "military cargo"], {"label": "Cargo Dock A"}),
          ("TERM-07-B02", "TERM-07", dock("60770-168"), 40, 200, 11.0, ["general cargo", "containers"], {"label": "Cargo Dock B"}),
          ("TERM-07-B03", "TERM-07", dock("60770-169"), 40, 200, 11.0, ["general cargo", "steel"], {"label": "Cargo Dock C", "off": 50}),
          ("TERM-07-B04", "TERM-07", dock("60770-820"), 40, 230, 11.5, ["general cargo", "wind components"], {"label": "Cargo Dock D"})])
    term("TERM-11", "Port of Corpus Christi Bulk Terminal", "Port of Corpus Christi Authority", "Dry bulk", "Inner Harbor, Tule Lake Channel",
         [("TERM-11-B01", "TERM-11", dock("60770-233"), 40, 230, 12.8, ["petroleum coke", "ores", "aggregates"], {"label": "Bulk Dock 1", "off": 50}),
          ("TERM-11-B02", "TERM-11", dock("60770-235"), 40, 230, 12.8, ["petroleum coke", "barite"], {"label": "Bulk Dock 2"})])
    term("TERM-12", "Nueces Grain Elevator", "Coastal Plains Grain Cooperative", "Grain export", "Inner Harbor, Industrial Canal",
         [("TERM-12-B01", "TERM-12", dock("60770-195"), 40, 230, 12.5, ["sorghum", "wheat", "corn"], {"label": "Elevator Wharf"})])
    term("TERM-13", "Harbor Point Refining East Docks", "Harbor Point Refining Company", "Refinery crude intake and products",
         "Inner Harbor, Industrial Canal and Main Turning Basin (south bank)",
         [("TERM-13-B01", "TERM-13", dock("60770-811"), 45, 250, 14.9, CR + ["gasoline"], {"label": "Tanker Dock 1"}),
          ("TERM-13-B02", "TERM-13", dock("60770-807"), 45, 250, 14.9, CR + ["diesel"], {"label": "Tanker Dock 2"})])
    term("TERM-14", "Cabeza Creek Refining Tule Lake Docks", "Cabeza Creek Refining LP", "Refinery crude intake, products and LPG",
         "Inner Harbor, Tule Lake Channel",
         [("TERM-14-B01", "TERM-14", dock("60770-738"), 45, 250, 14.9, CR + ["gasoline", "diesel"], {"label": "Dock 2", "off": 55}),
          ("TERM-14-B02", "TERM-14", dock("60770-733"), 40, 190, 11.0, ["LPG", "propane"], {"label": "LPG Dock"})])
    term("TERM-15", "Tres Bahias Refining Industrial Canal Docks", "Tres Bahias Refining and Chemicals", "Refinery crude intake and products",
         "Inner Harbor, Industrial Canal",
         [("TERM-15-B01", "TERM-15", dock("60770-803"), 45, 250, 14.9, CR, {"label": "Dock 1"}),
          ("TERM-15-B02", "TERM-15", dock("60770-815"), 40, 200, 12.2, ["gasoline", "diesel", "asphalt"], {"label": "Dock 8"})])
    term("TERM-16", "Viola Chemical Dock", "Calallen Polymers LLC", "Chemicals", "Inner Harbor, Viola Channel",
         [("TERM-16-B01", "TERM-16", dock("60770-702"), 40, 190, 11.3, ["ethylene glycol", "caustic soda", "styrene"], {"label": "Chemical Dock"})])
    term("TERM-17", "Inner Harbor Crude Export Terminal", "Padre Midstream Export LLC", "Crude oil export", "Inner Harbor, Main Turning Basin",
         [("TERM-17-B01", "TERM-17", dock("60770-182"), 45, 280, 15.8, CR, {"label": "Dock 15"}),
          ("TERM-17-B02", "TERM-17", dock("60770-172"), 45, 280, 15.8, CR, {"label": "Dock 16"}),
          ("TERM-17-B03", "TERM-17", dock("60770-814"), 45, 260, 15.2, CR, {"label": "Dock 12"})])
    term("TERM-18", "Tule Lake Export Docks", "Llano Crude Logistics", "Crude oil export", "Inner Harbor, Tule Lake Channel",
         [("TERM-18-B01", "TERM-18", dock("60770-764"), 45, 260, 15.2, CR, {"label": "Dock 1", "off": 45}),
          ("TERM-18-B02", "TERM-18", dock("60770-755"), 45, 260, 15.2, CR, {"label": "Dock 2"}),
          ("TERM-18-B03", "TERM-18", dock("60770-766"), 45, 250, 14.9, CR, {"label": "Dock 6"}),
          ("TERM-18-B04", "TERM-18", dock("60770-231"), 40, 200, 12.2, ["condensate", "naphtha"], {"label": "Liquid Bulk Dock 3"})])
    term("TERM-19", "Chemical Basin Barge Fleet", "Brasada Inland Marine", "Barge dock and fleeting", "Inner Harbor, Chemical Turning Basin (north bank)",
         [("TERM-19-B01", "TERM-19", dock("60770-205"), 12, 90, 3.6, ["tank barges"], {"label": "Barge Dock", "btype": "barge_berth", "off": 20}),
          ("TERM-19-B02", "TERM-19", dock("60770-227"), 12, 90, 3.6, ["tank barges"], {"label": "Fleeting Area", "btype": "barge_berth", "off": 20})])
    term("TERM-20", "Nueces Bay Shipyard and Drydock", "Nueces Bay Shipyard and Drydock Inc.", "Ship repair", "Inner Harbor, Chemical Turning Basin (north bank)",
         [("TERM-20-B01", "TERM-20", dock("60770-214"), 12, 110, 5.5, ["repair"], {"label": "Repair Berth", "btype": "repair_berth", "off": 25})])
    term("TERM-21", "Laguna Towing Tug Base", "Laguna Towing and Salvage Inc.", "Harbor tug moorings", "Inner Harbor, Main Turning Basin (north bank)",
         [("TERM-21-B01", "TERM-21", dock("60770-180"), 12, 45, 5.5, ["tug mooring"], {"label": "Tug Mooring 1", "btype": "lay_berth", "off": 20}),
          ("TERM-21-B02", "TERM-21", dock("60770-736"), 12, 45, 5.5, ["tug mooring"], {"label": "Tug Mooring 2", "btype": "lay_berth", "off": 20})])
    term("TERM-22", "Coast Guard Cutter Moorings, Corpus Christi", "U.S. Coast Guard", "Government moorings", "Inner Harbor, Main Turning Basin (north bank)",
         [("TERM-22-B01", "TERM-22", dock("60770-186"), 12, 85, 4.5, ["government vessel"], {"label": "Cutter Mooring", "btype": "lay_berth", "off": 22})])
    term("TERM-24", "Gulf Shield Response Base", "Gulf Shield Response LLC", "Oil spill response base", "Inner Harbor, Tule Lake Channel (south bank)",
         [("TERM-24-B01", "TERM-24", dock("60770-771"), 12, 70, 4.5, ["response vessel"], {"label": "Response Dock", "btype": "lay_berth", "off": 20})])
    term("TERM-25", "Coastal Bend Harbor Services Tug Base", "Coastal Bend Harbor Services", "Harbor tug moorings", "Inner Harbor, Tule Lake Turning Basin",
         [("TERM-25-B01", "TERM-25", dock("60770-267"), 12, 45, 5.5, ["tug mooring"], {"label": "Tug Mooring", "btype": "lay_berth", "off": 20})])
    # ---------------- La Quinta Channel (USACE reaches LA_01 to LA_03, maintained 47 ft)
    term("TERM-03", "La Quinta LNG Terminal", "Baypoint LNG Partners", "LNG export", "La Quinta Channel extension",
         [("TERM-03-B01", "TERM-03", dock("60770-087"), 40, 300, 12.5, ["LNG"], {"label": "LNG Jetty 1"})])
    term("TERM-09", "La Quinta Bulk Liquids Terminal", "Gregory Point Terminals", "Chemicals and bulk liquids", "La Quinta Channel extension",
         [("TERM-09-B01", "TERM-09", dock("60770-092"), 40, 200, 12.0, ["monoethylene glycol", "methanol"], {"label": "Dock 1"})])
    term("TERM-10", "La Quinta Dry Bulk Dock", "Portland Reduction Works", "Dry bulk (iron ore, briquettes)", "La Quinta Channel extension",
         [("TERM-10-B01", "TERM-10", dock("60770-088"), 40, 230, 12.8, ["iron ore pellets", "hot briquetted iron"], {"label": "Bulk Dock"})])
    # ---------------- Harbor Island and Aransas Pass (shallow-draft)
    term("TERM-23", "Harbor Island Marine Base", "Harbor Island Marine Services", "Offshore supply base", "Aransas Channel at Harbor Island (16 ft)",
         [("TERM-23-B01", "TERM-23", dock("60750-992"), 12, 80, 4.6, ["offshore supply"], {"label": "Supply Dock 1", "btype": "lay_berth", "off": 15}),
          ("TERM-23-B02", "TERM-23", dock("60750-987"), 12, 80, 4.6, ["offshore supply"], {"label": "Supply Dock 2", "btype": "lay_berth", "off": 20})])
    term("TERM-26", "Redfish Bay Barge Fleeting", "Brasada Inland Marine", "Barge fleeting on the Intracoastal Waterway", "Gulf Intracoastal Waterway, Redfish Bay",
         [("TERM-26-B01", "TERM-26", dock("66535-103"), 12, 90, 3.6, ["tank barges", "hopper barges"], {"label": "Fleet", "btype": "barge_berth", "off": 25, "min_clear": 25})])

    # ---------------- small-craft harbours and slips
    slips, harbours = [], []

    def harbour(hid, name, place, basis, pts, min_clear=25.0, prefix=None, kind="slip", max_r=160.0, names=None):
        taken, out = [], []
        for i, (lat, lon) in enumerate(pts):
            w = (lat, lon) if (not G.is_land(lat, lon) and G.land_clearance_m(lat, lon) >= min_clear
                               and all(geo.dist_m((lat, lon), t) >= 20 for t in taken)) else \
                nearest_water(lat, lon, min_clear=min_clear, max_r=max_r, taken=taken)
            if w is None:
                continue
            cl = route_clearance(w)
            if cl is None:      # enclosed water with no route to the bay at raster resolution: not usable
                taken.append(w)
                continue
            taken.append(w)
            sid = f"SLIP-{prefix or hid[4:]}-{len(out) + 1:02d}"
            s = {"slip_id": sid, "harbour_id": hid, "slip_name": (names[i] if names else f"{name} slip {len(out) + 1}"),
                 "slip_type": kind, "latitude": R5(w[0]), "longitude": R5(w[1]),
                 "land_clearance_m": round(G.land_clearance_m(*w)), "water_route_clearance_m": cl, "position_basis": basis}
            out.append(s)
            slips.append(s)
        if not out:
            return out
        harbours.append({"harbour_id": hid, "harbour_name": name, "place": place, "slip_ids": [s["slip_id"] for s in out],
                         "water_route_clearance_m": min(s["water_route_clearance_m"] for s in out),
                         "latitude": R5(sum(s["latitude"] for s in out) / len(out)),
                         "longitude": R5(sum(s["longitude"] for s in out) / len(out))})
        return out

    def lm_pts(codes):
        out = []
        for c in codes:
            for l in G.landmarks:
                if c in str(l.get("source_id", "")):
                    out.append((l["lat"], l["lon"]))
        return out

    # Conn Brown Harbor, Aransas Pass: real shrimp-dock points, moved to the nearest water in the harbour
    cbh = lm_pts(["66532-100", "66532-280", "66532-250", "66532-289", "66532-290", "66531-922"])
    harbour("HBR-CBH", "Conn Brown Harbor", "Aransas Pass", "nearest water to a real Conn Brown Harbor dock point (USACE Master Docks)",
            cbh + cbh[:4], prefix="CBH")
    # Port Aransas municipal harbour: grid inside the USACE harbour basin polygons
    pah = []
    for it in G.channels.items:
        if it["props"]["reach_id"] in ("CESWG_AR_02_TRB_2", "CESWG_AR_03_ABN_3"):
            b = it["bbox"]
            la = b[1]
            while la <= b[3]:
                lo = b[0]
                while lo <= b[2]:
                    if it["path"].contains_point((lo, la)) and not G.is_land(la, lo):
                        pah.append((la, lo))
                    lo += 0.00035
                la += 0.00030
    pah = pah[::2][:14]
    harbour("HBR-PAH", "Port Aransas Municipal Harbor", "Port Aransas", "inside the USACE Port Aransas harbour basin polygon", pah, min_clear=0.0, prefix="PAH")
    cg = next(l for l in G.landmarks if l["category"] == "coast_guard")
    harbour("HBR-CGS", "Coast Guard Station Port Aransas", "Port Aransas", "nearest water to the charted Coast Guard station point (NOAA ENC)",
            [(cg["lat"], cg["lon"])] * 6, min_clear=0.0, prefix="CGS", kind="government_mooring", max_r=260.0)
    pil = dock("66534-905")
    harbour("HBR-PIL", "Aransas Pass Bar Pilots Station", "Port Aransas", "nearest water to the real pilot station dock point (USACE Master Docks)",
            [(pil["lat"], pil["lon"])] * 3, prefix="PIL", kind="pilot_boat_berth", max_r=260.0)
    ut = dock("66534-005")
    harbour("HBR-UTM", "Marine Science Institute Boat Basin", "Port Aransas", "nearest water to the real boat-basin point (USACE Master Docks)",
            [(ut["lat"], ut["lon"])] * 2, prefix="UTM", kind="research_berth", max_r=260.0)
    f1, f2 = dock("66534-900"), dock("66534-901")
    harbour("HBR-FRY", "Port Aransas Ferry Landings", "Port Aransas / Harbor Island",
            "nearest water to the real ferry landing points (USACE Master Docks)",
            [(f1["lat"], f1["lon"])] * 4 + [(f2["lat"], f2["lon"])] * 4, prefix="FRY", kind="ferry_slip", max_r=260.0,
            names=[f"Mustang Island landing, slip {i}" for i in (1, 2, 3, 4)] + [f"Harbor Island landing, slip {i}" for i in (1, 2, 3, 4)])
    rk = next(l for l in G.landmarks if l["name"].startswith("ROCKPORT HARBOR MOORINGS"))
    harbour("HBR-RKP", "Rockport Harbor", "Rockport", "nearest water to the real Rockport Harbor moorings point (USACE Master Docks)",
            [(rk["lat"], rk["lon"])] * 8, prefix="RKP", max_r=200.0)
    sg = dock("60770-079")
    harbour("HBR-ING", "Ingleside Marina", "Ingleside (Jewel Fulton Canal)",
            "water beside the Jewel Fulton Canal (USACE reach JF_01), nearest to a real dock point at its head",
            [(sg["lat"], sg["lon"])] * 10, prefix="ING", max_r=320.0, names=[f"Ingleside Marina Berth {i}" for i in range(1, 11)])
    # Corpus Christi municipal marina: the basin behind the breakwater is in the NOAA land data (T-heads);
    # no dock point is published, so slips are water cells 25-60 m from the T-head land.
    ccm = []
    for la in np.arange(27.7920, 27.7985, 0.00035):
        for lo in np.arange(-97.3905, -97.3872, 0.00035):
            if not G.is_land(la, lo) and 50 <= G.land_clearance_m(la, lo) <= 90:
                ccm.append((float(la), float(lo)))
    ccm = [p for p in ccm if water_reachable(p)][::2][:10]
    if ccm:
        harbour("HBR-CCM", "Corpus Christi Municipal Marina", "Corpus Christi bayfront",
                "water 50-90 m from the T-head piers shown in the NOAA land data; no published dock point", ccm, min_clear=50.0, prefix="CCM")
    fu = next(l for l in G.landmarks if "Rockport/Fulton shore" in l["name"])
    harbour("HBR-FUL", "Fulton Harbor", "Fulton", "nearest water to the charted small-craft facility point (NOAA ENC)",
            [(fu["lat"], fu["lon"])] * 4, prefix="FUL", max_r=200.0)

    # ---------------- offshore: sea buoy, pilot boarding, anchorage positions, sea gates
    cl = [f for f in geo._load("channel_lines_usace.geojson") if f["properties"]["line_id"].startswith("CESWG_CC_01")][0]
    pts = [(c[1], c[0]) for c in next(geo._lines(cl["geometry"]))]
    sea, inner = (pts[0], pts[1]) if pts[0][1] > pts[-1][1] else (pts[-1], pts[-2])
    axis = geo.bearing(inner, sea)

    def project(p, brg, nm):
        d = nm * 1852.0
        return (p[0] + d * math.cos(math.radians(brg)) / geo.M_PER_DEG_LAT,
                p[1] + d * math.sin(math.radians(brg)) / (111320.0 * math.cos(math.radians(p[0]))))

    pb = project(sea, axis, 2.0)
    assert not G.is_land(*pb)
    pilot_boarding = {"position_id": "PILOT-BOARDING", "name": "Aransas Pass pilot boarding area", "latitude": R5(pb[0]), "longitude": R5(pb[1]),
                      "radius_nm": 1.0, "inside_noaa_fairway": bool(G.fairways.contains(*pb)),
                      "position_basis": "2.0 nm seaward of the seaward end of the USACE sea bar channel centerline, on the channel axis; "
                                        "no pilot boarding place is published in the NOAA ENC layers that were fetched"}
    sea_buoy = {"position_id": "SEA-BUOY", "name": "Aransas Pass sea buoy (seaward end of the sea bar channel)",
                "latitude": R5(sea[0]), "longitude": R5(sea[1]), "channel_axis_deg": round(axis, 1),
                "position_basis": "seaward end of the USACE Corpus Christi sea bar channel centerline"}
    cand = []
    for la in np.arange(27.70, 27.90, 0.0180):
        for lo in np.arange(-97.00, -96.66, 0.0200):
            la, lo = float(la), float(lo)
            if not G.anchorages.contains(la, lo) or G.fairways.contains(la, lo) or G.is_land(la, lo):
                continue
            if G.channel_at(la, lo, 600):
                continue
            # keep half a nautical mile inside the anchorage boundary and clear of the fairways
            if not all(G.anchorages.contains(*project((la, lo), b, 0.4)) and not G.fairways.contains(*project((la, lo), b, 0.4))
                       for b in (0, 90, 180, 270)):
                continue
            d = geo.gc_nm((la, lo), sea)
            if 1.5 <= d <= 16:
                cand.append((d, la, lo))
    cand.sort()
    anch = []
    for i, (d, la, lo) in enumerate(cand[:30]):
        it = G.anchorages.which(la, lo)
        anch.append({"position_id": f"ANCH-{i + 1:02d}", "name": f"Aransas Pass anchorage, position {i + 1}",
                     "latitude": R5(la), "longitude": R5(lo), "swing_radius_m": 450, "distance_to_sea_buoy_nm": round(d, 1),
                     "anchorage_area": it["props"].get("name") or "Fairway anchorage (33 CFR 166.200)",
                     "position_basis": "grid point inside the NOAA ENC anchorage polygon, outside the charted fairways"})
    far = project(sea, axis, 25.0)
    gates_raw = [
        ("GATE-OFFING", "Aransas Pass offing, 25 nm seaward on the channel axis", far, []),
        ("GATE-GALVESTON", "Off Galveston Bay entrance", (29.10, -94.40), ["Houston", "Texas City", "Galveston", "Freeport"]),
        ("GATE-SABINE", "Off Sabine Pass", (29.40, -93.75), ["Port Arthur", "Beaumont", "Lake Charles"]),
        ("GATE-SWPASS", "Off Southwest Pass, Mississippi River", (28.75, -89.60), ["New Orleans", "Baton Rouge", "Mobile"]),
        ("GATE-CAPE-SAN-BLAS", "Northeast Gulf, off Cape San Blas", (29.40, -85.70), ["Panama City", "Port St. Joe"]),
        ("GATE-TAMPA", "Off Tampa Bay entrance", (27.55, -83.20), ["Tampa"]),
        ("GATE-FLORIDA-STRAITS", "Straits of Florida, west entrance", (24.00, -82.90), ["Rotterdam", "Milford Haven", "Algeciras", "US East Coast"]),
        ("GATE-YUCATAN", "Yucatan Channel", (21.80, -85.80), ["Panama Canal", "Ulsan", "Ningbo", "Sikka", "Santos", "Cartagena"]),
        ("GATE-TAMPICO", "Off Tampico and Altamira", (22.30, -97.45), ["Tampico", "Altamira"]),
        ("GATE-VERACRUZ", "Off Veracruz and Tuxpan", (19.40, -95.85), ["Veracruz", "Tuxpan"]),
        ("GATE-COATZACOALCOS", "Off Coatzacoalcos and Pajaritos", (18.40, -94.40), ["Coatzacoalcos", "Pajaritos", "Dos Bocas"]),
        ("GATE-BROWNSVILLE", "Off Brazos Santiago Pass", (26.07, -96.95), ["Brownsville", "Port Isabel"]),
    ]
    gates = []
    for gid, name, p, ports in gates_raw:
        assert not G.is_land(*p), gid
        clear = G.segment_clear(far, p, 1500.0) if gid != "GATE-OFFING" else G.segment_clear(pb, far, 500.0)
        assert clear, f"leg to {gid} crosses land"
        gates.append({"gate_id": gid, "name": name, "latitude": R5(p[0]), "longitude": R5(p[1]), "ports_beyond": ports,
                      "distance_from_sea_buoy_nm": round(geo.gc_nm(sea, p)),
                      "route_from_port": ["SEA-BUOY", "PILOT-BOARDING", "GATE-OFFING"] + ([gid] if gid != "GATE-OFFING" else []),
                      "position_basis": "open-water waypoint, not a charted feature; the straight leg from GATE-OFFING was checked "
                                        "clear of land with scripts/geo.py (coarse Gulf coastline, about 1.6 km)"})

    reg = {
        "metadata": {"dataset": "Port and harbour registry, Corpus Christi area", "schema_version": "2.0", "generated": GENERATED,
                     "generated_by": "scripts/build_registries_maritime_air.py",
                     "geography": "Positions are derived from real geometry in 99_reference/geo (USACE National Channel Framework reaches, "
                                  "NOAA ENC land areas and anchorages, USACE Master Docks points). Terminal and operator names are fictional "
                                  "names placed on real dock sites; the Port of Corpus Christi Authority and government agencies are real.",
                     "routing": "Deep-draft ships reach their berths along the channel centerlines (scripts/geo.py nav graph). Small craft leave a "
                                "slip with geo.water.route using a land clearance no larger than the slip's water_route_clearance_m.",
                     "joins": "berth_id and slip_id are used by vessels.json (home_berth_id, usual_berths) and by supply/vessel_arrivals.csv "
                              "(terminal_id, berth_id).",
                     "counts": {}},
        "port_overview": {"port_name": "Port of Corpus Christi", "channel": "Corpus Christi Ship Channel (USACE project CESWG_CC), sea bar to Viola Turning Basin, 36.4 statute miles",
                          "maintained_depth_ft": {"sea_bar_and_jetty": "54-56", "bay_reaches_and_inner_harbor": 54, "la_quinta_channel": 47,
                                                  "intracoastal_waterway": "12-14", "aransas_channel_and_conn_brown_harbor": 16},
                          "harbor_bridge": {"latitude": R5([l for l in G.landmarks if l["name"].startswith("Harbor Bridge")][0]["lat"]),
                                            "longitude": R5([l for l in G.landmarks if l["name"].startswith("Harbor Bridge")][0]["lon"]),
                                            "note": "US 181 crossing at the entrance to the Inner Harbor (National Bridge Inventory point)"},
                          "captain_of_the_port": "U.S. Coast Guard Sector Corpus Christi", "pilots": "Aransas Pass Bar Pilots (fictional name)"},
        "terminals": terminals, "berths": berths, "harbours": harbours, "slips": slips,
        "anchorage_areas": [{"area_id": "TERM-08", "name": "Aransas Pass offshore anchorage", "authority": "33 CFR 166.200 fairway anchorages",
                             "geometry_source": "99_reference/geo/anchorages_fairways_noaa.geojson (NOAA ENC Direct)",
                             "position_ids": [a["position_id"] for a in anch]}],
        "anchorage_positions": anch, "pilot_boarding": pilot_boarding, "sea_buoy": sea_buoy, "sea_gates": gates,
        "ferry_route": {"name": "Port Aransas ferry (State Highway 361)", "operator": "Texas Department of Transportation",
                        "landings": ["Mustang Island landing", "Harbor Island landing"], "slip_ids": [s["slip_id"] for s in slips if s["harbour_id"] == "HBR-FRY"],
                        "crossing_m": round(geo.dist_m((f1["lat"], f1["lon"]), (f2["lat"], f2["lon"])))},
    }
    reg["metadata"]["counts"] = {"terminals": len(terminals), "berths": len(berths), "harbours": len(harbours), "slips": len(slips),
                                 "anchorage_positions": len(anch), "sea_gates": len(gates)}
    truth = {
        "_about": "Internal. Scenario roles of terminals and positions. Never give this file to participants.",
        "truth": {
            "TERM-01": {"role": "Berths 7 and 8 hold MT Kalvora Star (VSL-0041) and MT Ostrel Bay (VSL-0042) from D-3. Cargo valves are opened "
                                "remotely 04:00Z-05:30Z on D0; about 9,000 barrels spill here. Pre-storm drone sorties 4 and 5 (D-5, D-4) image this berth.",
                        "threads": ["T6", "T12", "T19", "T20"], "events": ["EVT-0209", "EVT-0210", "EVT-0313", "EVT-1203", "EVT-1904", "EVT-1905"]},
            "TERM-02": {"role": "Quellmar (SUP-0390) terminal. Barge 44 (BRG-0044) delivers 380 m3 of transferred fuel here on D+32; the GPS "
                                "interference transmitter JAM-01 sits in a parked vehicle in the industrial area beside it, D+38 to D+43.",
                        "threads": ["T2", "T3", "T7"], "events": ["EVT-0312", "EVT-0404", "EVT-0412"]},
            "TERM-07": {"role": "MV Gulf Provider (VSL-0012) unloads 40 relief containers here on D+33; the Fort Hood aviation brigade loads the "
                                "sealift ship (VSL-0019) here D+59 to D+64.", "events": ["EVT-0401", "EVT-0409"]},
            "TERM-20": {"role": "Tug Corrin Bay (VSL-0077) is repaired here after the D+44 blast (placement chosen in the registry pass; canon only says the tug was damaged)."},
            "HBR-ING": {"role": "Motor yacht Narwhal Dream lies at 'Ingleside Marina Berth 7' (SLIP-ING-07) from D-12 to D-8 as the launch point "
                                "for the pre-storm drone sorties.", "threads": ["T19"], "events": ["EVT-1901", "EVT-1902", "EVT-1903", "EVT-1906"]},
            "TERM-08": {"role": "Halcyon Drift (VSL-0031) loiters here from D-45; the 14-vessel Yankee queue holds here D-2 to D-1; storm-riding ships "
                                "wait here D+3 to D+30; the AIS gap, the Pelican Ridge identity spoof and the transfer to Barge 44 happen here on D+30/31.",
                        "threads": ["T2", "T7", "T12"]},
            "PILOT-BOARDING": {"role": "DEV-01 and DEV-02 are laid about 2 nm off the entrance channel at 04:20Z on D+31 (EVT-0411); DEV-01 detonates "
                                       "beside Corrin Bay near the jetties at 06:10Z on D+44."},
        },
        "id_migration": {
            "terminals": {
                "TERM-01": {"new": "TERM-01", "note": "same name; moved from a made-up downtown point to real Inner Harbor docks"},
                "TERM-02": {"new": "TERM-02", "note": "same name; real dock site"},
                "TERM-03": {"new": "TERM-03", "note": "renamed La Quinta LNG Terminal (was 'CC LNG')"},
                "TERM-04": {"new": "TERM-04", "note": "real refiner name removed; now the fictional Tule Lake Crude Terminal"},
                "TERM-05": {"new": "TERM-05", "note": "real company name removed; now the fictional Viola Liquids Hub"},
                "TERM-06": {"new": "TERM-06", "note": "renamed Avery Point Products Terminal (was 'Maxus Energy Terminal')"},
                "TERM-07": {"new": "TERM-07", "note": "berths TERM-07-B01..B03 keep their ids; B04 added"},
                "TERM-08": {"new": "TERM-08", "note": "now an anchorage area with ANCH-nn positions inside the real NOAA anchorage"},
                "TERM-09": {"new": None, "note": "'Aransas Pass Entrance Channel Jetties' was not a terminal; use sea_buoy / pilot_boarding. The id TERM-09 is reused for La Quinta Bulk Liquids Terminal."},
                "TERM-10": {"new": None, "note": "'NAS Corpus Christi Fuel Farm' is not a marine terminal; it belongs in the infrastructure registry. The id TERM-10 is reused for La Quinta Dry Bulk Dock."},
                "La Quinta Channel Berth 23": {"new": "TERM-07-B01", "note": "old Gulf Provider note; canon berths it at the Port of Corpus Christi on D+33"},
                "Ingleside Marina Berth 7": {"new": "SLIP-ING-07"},
                "Pier 9": {"new": None, "note": "removed from canon"}},
        },
    }
    return reg, truth


# ======================================================================================
# 2. vessels
# ======================================================================================
VENDORS = ["Brightwake Marine Systems", "Halvard Cargo Controls", "Tessaly Marine Automation", "Nordkapp Systems"]
CRUDE_OUT = ["Rotterdam", "Milford Haven", "Algeciras", "Ulsan", "Ningbo", "Sikka", "Singapore", "Trieste"]
CRUDE_IN = ["Houston lightering area", "Galveston offshore", "Rotterdam", "Freeport (Bahamas)", "Algeciras", "Panama Canal"]

# name, flag, class, type code, loa, beam, max draft, ballast draft, operator, type text, usual terminals, gate, last ports, next ports, pattern
SHIPS = []


def ship(vid, name, flag, klass, code, loa, beam, draft, ballast, operator, text, terminals, gates, last, nxt, pattern, **kw):
    SHIPS.append(dict(vessel_id=vid, vessel_name=name, flag=flag, klass=klass, code=code, loa=loa, beam=beam, draft=draft, ballast=ballast,
                      operator=operator, text=text, terminals=terminals, gates=gates, last=last, nxt=nxt, pattern=pattern, **kw))


def fleet():
    EXPORT = ["TERM-01", "TERM-04", "TERM-05", "TERM-17", "TERM-18"]
    REFINERY = ["TERM-13", "TERM-14", "TERM-15"]
    afra = lambda i: (243 + i % 7, 42 + i % 3, 14.2 + (i % 5) * 0.15, 7.6 + (i % 4) * 0.2)
    suez = lambda i: (272 + i % 4, 48, 15.6 + (i % 3) * 0.1, 8.4)
    # ---- canon tankers
    ship("VSL-0041", "MT Kalvora Star", "MH", "tanker", 80, 243, 42, 14.2, 7.8, "Kalvora Maritime Holdings Ltd.", "Crude oil tanker (Aframax)",
         ["TERM-01"], ["GATE-FLORIDA-STRAITS"], ["Freeport (Bahamas)"], ["Rotterdam"],
         "Crude export voyages Corpus Christi to northwest Europe, about every 40 days", vendor=VENDORS[0])
    ship("VSL-0042", "MT Ostrel Bay", "PA", "tanker", 80, 248, 44, 14.5, 7.9, "Ostrel Tankers S.A.", "Crude oil tanker (Aframax)",
         ["TERM-01"], ["GATE-YUCATAN"], ["Panama Canal"], ["Ulsan"],
         "Crude export voyages Corpus Christi to east Asia via Panama, about every 70 days", vendor=VENDORS[0])
    crude = [("MT Valdris Sun", "LR", "S", "Valdris Shipping Corp."), ("MT Brazos Star", "MH", "A", "Brazos Tanker Corp."),
             ("MT Orinda Bay", "PA", "A", "Orinda Maritime S.A."), ("MT Halcyon Aegis", "MT", "S", "Aegis Marine Ltd."),
             ("MT Narvik Pioneer", "NO", "A", "Nordic Pioneer Tankers AS"), ("MT Corpus Prince", "MH", "A", "Prince Maritime Holdings Ltd."),
             ("MT Lone Star Carrier", "MH", "A", "Lone Star Tankers LLC"), ("MT Storm Rider", "MT", "S", "Meltemi Tankers Ltd."),
             ("MT Ingleside Pride", "LR", "A", "Redfish Maritime Inc."), ("MT Nueces Sunrise", "PA", "A", "Sunrise Tanker Holdings S.A."),
             ("MT Permian Sun", "LR", "S", "Permian Sun Shipping Ltd."), ("MT Gulf Knight", "GR", "A", "Kyklades Tankers S.A."),
             ("MT Maverick Bay", "PA", "A", "Maverick Bay Navigation S.A."), ("MT Chinook Spirit", "MH", "A", "Chinook Spirit Shipping LLC"),
             ("MT Gulf Titan", "SG", "A", "Straits Titan Pte. Ltd."), ("MT Refugio Bay", "LR", "A", "Refugio Bay Tankers Ltd."),
             ("MT Bayou Spirit", "BS", "A", "Bayou Spirit Shipping Ltd."), ("MT Santos Provider", "PA", "A", "Santos Provider S.A."),
             ("MT La Quinta Express", "MT", "S", "Quinta Express Ltd."), ("MT Harbor Bay", "HK", "A", "Harbor Bay Shipping (HK) Ltd."),
             ("MT Gulf Coast Pioneer", "LR", "S", "Coast Pioneer Tankers Inc."), ("MT Aldebaran Trader", "CY", "A", "Aldebaran Shipmanagement Ltd.")]
    for i, (name, flag, size, op) in enumerate(crude):
        loa, beam, dr, bal = suez(i) if size == "S" else afra(i)
        terms = [EXPORT[i % len(EXPORT)], EXPORT[(i + 2) % len(EXPORT)]] if i % 5 else [REFINERY[i % 3], EXPORT[i % len(EXPORT)]]
        if size == "S":          # only the 280 m berths take a Suezmax
            terms = ["TERM-17", "TERM-04"]
        gate = "GATE-YUCATAN" if i % 3 == 0 else "GATE-FLORIDA-STRAITS"
        ship(f"VSL-{101 + i:04d}", name, flag, "tanker", 80, loa, beam, round(dr, 1), bal, op,
             f"Crude oil tanker ({'Suezmax' if size == 'S' else 'Aframax'})", terms, [gate],
             [CRUDE_IN[i % len(CRUDE_IN)]], [CRUDE_OUT[i % len(CRUDE_OUT)]],
             f"Arrives in ballast, waits at the offshore anchorage for a berth, loads crude for {CRUDE_OUT[i % len(CRUDE_OUT)]}; a call about every {34 + (i * 7) % 30} days",
             vendor=VENDORS[(i * 3 + 1) % 4] if i not in (3, 8, 13, 17) else VENDORS[0])
    prod = [("MT Sennar Gulf", "GR", "Sennar Petroleum Carriers S.A.", ["TERM-06", "TERM-15"], "GATE-TAMPICO", "Tuxpan", "Tampico"),
            ("MT Gulf Chemist", "PA", "Gulf Chemical Carriers S.A.", ["TERM-16", "TERM-09"], "GATE-GALVESTON", "Houston", "Altamira"),
            ("MT Aransas Spirit", "LR", "Aransas Shipping Corp.", ["TERM-06", "TERM-13"], "GATE-TAMPA", "Tampa", "Tampa"),
            ("MT Rockport Trader", "MH", "Rockport Trader Shipping LLC", ["TERM-06", "TERM-14"], "GATE-VERACRUZ", "Veracruz", "Tuxpan"),
            ("MT Tarpon Reach", "SG", "Tarpon Reach Pte. Ltd.", ["TERM-18", "TERM-06"], "GATE-COATZACOALCOS", "Pajaritos", "Dos Bocas"),
            ("MT Laguna Verde", "MT", "Laguna Verde Shipping Ltd.", ["TERM-16", "TERM-09"], "GATE-SWPASS", "New Orleans", "Cartagena"),
            ("MT Copano Mist", "MH", "Copano Mist Tankers LLC", ["TERM-14", "TERM-15"], "GATE-BROWNSVILLE", "Brownsville", "Tampico")]
    for i, (name, flag, op, terms, gate, last, nxt) in enumerate(prod):
        ship(f"VSL-{171 + i:04d}", name, flag, "tanker", 80, 179 + i % 5, 29 + i % 4, round(10.8 + (i % 4) * 0.2, 1), 6.4, op,
             "Product / chemical tanker (MR)", terms, [gate], [last], [nxt],
             f"Products and chemicals between Corpus Christi and {nxt}; a call every {12 + i * 2} to {18 + i * 2} days", vendor=VENDORS[(i + 2) % 4])
    lng = [("MT Pacific Prism", "MH", "Pacific Gas Transport Ltd.", "Incheon"), ("MT Galveston Star", "MT", "Star Gas Maritime Ltd.", "Rotterdam"),
           ("MT Ingleside Star", "BS", "Ingleside Star LNG Ltd.", "Zeebrugge"), ("MT Lone Star Aurora", "NO", "Aurora LNG Carriers AS", "Swinoujscie"),
           ("MT Coastal Bend Energy", "SG", "Bendline Gas Carriers Pte. Ltd.", "Tokyo Bay")]
    for i, (name, flag, op, dest) in enumerate(lng):
        ship(f"VSL-{151 + i:04d}", name, flag, "lng", 84, 290 + i % 6, 46, round(11.8 + (i % 3) * 0.2, 1), 9.6, op, "LNG carrier (174,000 m3)",
             ["TERM-03"], ["GATE-FLORIDA-STRAITS" if i % 2 else "GATE-YUCATAN"], ["Panama Canal" if i % 2 == 0 else "Gibraltar"], [dest],
             f"Loads LNG at La Quinta for {dest}; a call about every {45 + i * 6} days", vendor=VENDORS[(i + 1) % 4])
    bulk = [("MV Nueces Trader", "PA", "Nueces Bulk Carriers S.A.", ["TERM-12"], "sorghum", "Veracruz"),
            ("MV Sable Horizon", "LR", "Sable Bulk Shipping Ltd.", ["TERM-11"], "petroleum coke", "Sikka"),
            ("MV Capehorn Eagle", "MH", "Capehorn Bulk Carriers Ltd.", ["TERM-10"], "iron ore pellets", "Santos"),
            ("MV Gulf Petcoke", "BS", "Gulf Bulk Navigation Ltd.", ["TERM-11"], "petroleum coke", "Altamira"),
            ("MV Diamond Bulk", "LR", "Diamond Bulk Maritime Inc.", ["TERM-11", "TERM-10"], "barite", "Tampico"),
            ("MV Corpus Grain", "BS", "Corpus Grain Shipping Ltd.", ["TERM-12"], "wheat", "Coatzacoalcos"),
            ("MV Rio Hondo", "PA", "Rio Hondo Navegacion S.A.", ["TERM-10", "TERM-11"], "hot briquetted iron", "Mobile")]
    for i, (name, flag, op, terms, cargo, dest) in enumerate(bulk):
        ship(f"VSL-{201 + i:04d}", name, flag, "bulk", 70, 190 + (i * 7) % 36, 32, round(11.6 + (i % 5) * 0.3, 1), 6.2, op,
             "Bulk carrier (Supramax / Panamax)", terms, ["GATE-YUCATAN" if i % 2 else "GATE-TAMPICO"], [dest], [dest],
             f"Dry bulk ({cargo}); a call about every {25 + i * 4} days")
    ship("VSL-0012", "MV Gulf Provider", "BS", "cargo", 70, 182, 28, 10.2, 6.5, "Cayo Largo Shipping Ltd.", "General cargo ship (multipurpose)",
         ["TERM-07"], ["GATE-TAMPA"], ["Tampa"], ["Houston"],
         "General and project cargo between Tampa, Corpus Christi and Houston; a call every 14 to 18 days")
    cargo = [("MV Adriatic Carrier", "MT", "Adriatic Carrier Lines Ltd.", 172, 9.8, "GATE-FLORIDA-STRAITS", "Koper", "wind components"),
             ("MV Pacific Trader", "HK", "Pacific Trader Shipping (HK) Ltd.", 155, 8.4, "GATE-YUCATAN", "Manzanillo", "steel pipe"),
             ("MV Coastal Endeavor", "AG", "Endeavor Coastal Shipping Ltd.", 138, 7.6, "GATE-TAMPICO", "Altamira", "steel and general cargo"),
             ("MV San Antonio Bay", "BS", "San Antonio Bay Shipping Ltd.", 160, 9.2, "GATE-GALVESTON", "Houston", "project cargo"),
             ("MV Coastal Express", "AG", "Coastal Express Lines Ltd.", 132, 7.2, "GATE-SWPASS", "New Orleans", "bagged cargo"),
             ("MV Gulf Rebuilder", "US", "Bluewater Jones Act Carriers LLC", 168, 9.4, "GATE-GALVESTON", "Houston", "building materials"),
             ("MV Galveston Relief", "US", "Bluewater Jones Act Carriers LLC", 150, 8.6, "GATE-GALVESTON", "Galveston", "relief supplies"),
             ("MV Port Royal", "LR", "Port Royal Container Line Inc.", 185, 10.4, "GATE-YUCATAN", "Cartagena", "containers")]
    for i, (name, flag, op, loa, dr, gate, last, cg) in enumerate(cargo):
        ship(f"VSL-{231 + i:04d}", name, flag, "cargo", 70, loa, 22 + int(loa / 14), dr, round(dr * 0.62, 1), op, "General cargo / multipurpose ship",
             ["TERM-07"], [gate], [last], [last], f"{cg.capitalize()} through the public cargo docks; a call about every {16 + i * 3} days")
    ship("VSL-0019", "MV Cape Sandoval", "US", "roro", 70, 208, 31, 9.6, 7.4, "U.S. Maritime Administration (operated under contract)",
         "Roll-on/roll-off sealift ship", ["TERM-07"], ["GATE-FLORIDA-STRAITS"], ["Beaumont"], ["(not announced)"],
         "Government sealift ship; calls only for military cargo movements", imo=True)
    ship("VSL-0251", "MV Roosevelt Island", "BS", "roro", 70, 199, 32, 9.1, 7.2, "Islandway Car Carriers Ltd.", "Vehicle carrier",
         ["TERM-07"], ["GATE-VERACRUZ"], ["Veracruz"], ["Veracruz"], "Vehicles and rolling cargo; a call about every 30 days")
    for i, (name, op) in enumerate([("MV Deepwater Scout", "Harbor Island Marine Services"), ("MV Gulf Surveyor", "Harbor Island Marine Services"),
                                    ("MV Nueces Bay Supply", "Harbor Island Marine Services")]):
        ship(f"VSL-{261 + i:04d}", name, "US", "offshore_supply", 79, 62 + i * 4, 14, 4.4, 3.6, op, "Offshore supply vessel",
             ["TERM-23"], ["GATE-OFFING"], ["offshore platforms"], ["offshore platforms"],
             "Runs between Harbor Island and offshore platforms, two or three round trips a week", home=f"TERM-23-B0{1 + i % 2}")
    # ---- tugs
    ship("VSL-0077", "Corrin Bay", "US", "tug", 52, 30, 11, 4.9, 4.9, "Laguna Towing and Salvage Inc.", "Harbor tug (azimuth stern drive)",
         [], [], [], [], "Ship-assist tug; escorts deep-draft ships between the jetties and the Inner Harbor", home="TERM-21-B01")
    for i, (name, op, home) in enumerate([("Laguna Queen", "Laguna Towing and Salvage Inc.", "TERM-21-B01"), ("Rockport Mariner", "Laguna Towing and Salvage Inc.", "TERM-21-B02"),
                                          ("Laguna Chief", "Laguna Towing and Salvage Inc.", "TERM-21-B02"), ("Laguna Spirit", "Laguna Towing and Salvage Inc.", "TERM-21-B01"),
                                          ("Mesquite Bay", "Coastal Bend Harbor Services", "TERM-25-B01"), ("Baffin Bay", "Coastal Bend Harbor Services", "TERM-25-B01"),
                                          ("Copano", "Coastal Bend Harbor Services", "TERM-25-B01")]):
        ship(f"VSL-{271 + i:04d}", name, "US", "tug", 52, 28 + i % 5, 10 + i % 2, round(4.4 + (i % 4) * 0.2, 1), 4.4, op, "Harbor tug",
             [], [], [], [], "Ship-assist tug working the ship channel and the Inner Harbor docks", home=home)
    for i, name in enumerate(["Leona Grace", "Sabine Runner", "Trinity Belle", "Matagorda Star"]):
        ship(f"VSL-{291 + i:04d}", name, "US", "tug", 31, 24 + i, 9, 2.9, 2.9, "Brasada Inland Marine" if i < 3 else "Coastal Bend Bunkering LLC",
             "Inland towboat (pushboat)", ["TERM-19", "TERM-26", "TERM-02"], ["GATE-GALVESTON"], ["Houston"], ["Brownsville"],
             "Pushes tank barges along the Intracoastal Waterway between Houston, Corpus Christi and Brownsville" if i < 3 else
             "Pushes bunker and fuel barges between the Inner Harbor docks and the Intracoastal Waterway", home="TERM-19-B02" if i != 2 else "TERM-26-B01", kind_note="towboat")
    for i, n in enumerate([41, 42, 44, 47]):
        ship(f"BRG-{n:04d}", f"Barge {n}", "US", "barge", 90, 61, 11, 2.8, 0.6, "Coastal Bend Bunkering LLC", "Tank barge (10,000 barrel class)",
             ["TERM-02", "TERM-19"], [], [], [], "Fuel and bunker deliveries around the Inner Harbor and the bay, pushed by a towboat",
             home="TERM-19-B01", unmanned=True, ais=(n in (42, 44)))
    for i, name in enumerate(["Aransas Pilot I", "Aransas Pilot II", "Aransas Pilot III"]):
        ship(f"VSL-{301 + i:04d}", name, "US", "pilot", 50, 17, 5, 1.5, 1.5, "Aransas Pass Bar Pilots", "Pilot boat",
             [], [], [], [], "Runs between the pilot station at Port Aransas and the boarding area off the sea buoy for every ship movement",
             home=f"SLIP-PIL-0{i + 1}")
    for i, name in enumerate(["Redfish Runner", "Lydia Ann Light", "Harbor Island", "Mustang Dunes", "Tarpon Flats", "San Jose"]):
        ship(f"VSL-{311 + i:04d}", name, "US", "ferry", 60, 49 if i < 3 else 30, 16 if i < 3 else 12, 2.0, 2.0, "Texas Department of Transportation",
             "Vehicle ferry (%d cars)" % (28 if i < 3 else 20), [], [], [], [],
             "Crosses the ship channel between Harbor Island and Port Aransas around the clock; more boats in service on summer weekends",
             home=f"SLIP-FRY-0{i + 1}")
    uscg = [("USCGC Resolute Bay", 64, 10, 3.3, "Medium endurance cutter (210 ft)", "TERM-22-B01", "Offshore patrol of the western Gulf; in port about one week in four"),
            ("USCGC Padre Light", 47, 8, 2.9, "Fast response cutter (154 ft)", "TERM-22-B01", "Coastal patrol and search and rescue between Port O'Connor and Brownsville"),
            ("USCGC Cormorant Point", 27, 6, 1.8, "Coastal patrol boat (87 ft)", "SLIP-CGS-01", "Patrols the bays, the ship channel and the offshore anchorage"),
            ("USCGC Live Oak", 53, 11, 2.5, "Coastal buoy tender (175 ft)", "TERM-22-B01", "Services buoys and beacons along the ship channel and the Intracoastal Waterway"),
            ("CG 45712", 14, 4, 1.0, "Response boat, medium (45 ft)", "SLIP-CGS-02", "Search and rescue and security patrols from Station Port Aransas"),
            ("CG 45718", 14, 4, 1.0, "Response boat, medium (45 ft)", "SLIP-CGS-03", "Search and rescue and security patrols from Station Port Aransas"),
            ("CG 45731", 14, 4, 1.0, "Response boat, medium (45 ft)", "SLIP-CGS-04", "Search and rescue and security patrols from Station Port Aransas"),
            ("CG 29158", 9, 3, 0.8, "Response boat, small (29 ft)", "SLIP-CGS-05", "Harbor and channel patrols, safety zones"),
            ("CG 26204", 8, 3, 0.9, "Aids-to-navigation boat (26 ft)", "SLIP-CGS-06", "Maintains lights and daybeacons in the bays")]
    for i, (name, loa, beam, dr, text, home, pat) in enumerate(uscg):
        ship(f"VSL-{321 + i:04d}", name, "USG", "coast_guard", 55 if i != 3 else 53, loa, beam, dr, dr, "U.S. Coast Guard", text, [], [], [], [], pat, home=home)
    navy = [("USNS Muskogee Bend", 80, 18, 5.5, "Towing, salvage and rescue ship", None, "Based outside the area; deploys for salvage and diving support"),
            ("NAVY EOD 11M-1", 11, 3, 0.7, "Explosive ordnance disposal craft (11 m)", "SLIP-CGS-05", "Based outside the area; deploys with a Navy explosive ordnance disposal detachment"),
            ("NAVY EOD 11M-2", 11, 3, 0.7, "Explosive ordnance disposal craft (11 m)", "SLIP-CGS-06", "Based outside the area; deploys with a Navy explosive ordnance disposal detachment"),
            ("NAVY MCM USV-07", 12, 3, 0.8, "Mine countermeasures unmanned surface vessel", "SLIP-CGS-04", "Based outside the area; deploys with a Navy mine countermeasures team")]
    for i, (name, loa, beam, dr, text, home, pat) in enumerate(navy):
        ship(f"VSL-{341 + i:04d}", name, "USG", "navy", 35, loa, beam, dr, dr, "U.S. Navy", text, [], ["GATE-SWPASS"] if i == 0 else [], [], [], pat,
             home=home, visiting=True, home_port="Joint Expeditionary Base Little Creek, Virginia" if i else "Norfolk, Virginia")
    spill = [("Responder Aransas", 64, 14, 4.2, "Oil spill response vessel"), ("GS Skimmer 11", 12, 4, 0.9, "Oil skimming vessel"),
             ("GS Skimmer 12", 12, 4, 0.9, "Oil skimming vessel"), ("GS Skimmer 14", 12, 4, 0.9, "Oil skimming vessel"),
             ("GS Boom Tender 3", 10, 3, 0.7, "Boom-handling workboat")]
    for i, (name, loa, beam, dr, text) in enumerate(spill):
        ship(f"VSL-{351 + i:04d}", name, "US", "spill_response", 54, loa, beam, dr, dr, "Gulf Shield Response LLC", text, [], [], [], [],
             "On standby at the response base; drills monthly in the Inner Harbor and Nueces Bay", home="TERM-24-B01")
    ship("VSL-0361", "Dredge Baffin", "US", "dredge", 33, 70, 15, 2.6, 2.6, "Brazoria Dredging Company", "Cutter suction dredge",
         [], [], [], [], "Maintenance dredging of the ship channel bay reaches under an Army Corps of Engineers contract; moves a few hundred metres a day",
         home=None, home_port="works on site in the bay reaches of the ship channel")
    ship("VSL-0362", "SV Tejas Sounder", "USG", "survey", 90, 17, 5, 1.2, 1.2, "U.S. Army Corps of Engineers, Galveston District", "Hydrographic survey boat",
         [], [], [], [], "Channel condition surveys of the ship channel and the Intracoastal Waterway", home="SLIP-PAH-01")
    ship("VSL-0461", "RV Espiritu Santo", "US", "research", 90, 23, 7, 1.9, 1.9, "University Marine Science Institute, Port Aransas", "Coastal research vessel",
         [], [], [], [], "Day trips in the bays and to stations within 30 nm of the pass, two or three times a week", home="SLIP-UTM-01")
    shrimp = ["Miss Thuy", "Lady Carolyn", "Capt. Elroy", "Gulf Wind II", "Mary Louise", "Sea Hunter", "Kim Anh"]
    for i, name in enumerate(shrimp):
        ship(f"VSL-{401 + i:04d}", "FV " + name, "US", "fishing", 30, 19 + i % 6, 6, 1.9 + (i % 3) * 0.2, 1.9, "Owner-operated", "Shrimp trawler",
             [], [], [], [], "Bay and Gulf shrimping out of Conn Brown Harbor; trips of one to five days in season", home=f"SLIP-CBH-{i + 1:02d}", klass_b=True)
    for i, name in enumerate(["Copano Queen", "Lamar Star", "Fulton Pride"]):
        ship(f"VSL-{411 + i:04d}", "FV " + name, "US", "fishing", 30, 15 + i * 2, 5, 1.6, 1.6, "Owner-operated", "Bay shrimp and oyster boat",
             [], [], [], [], "Works Aransas and Copano bays out of Rockport; day trips", home=f"SLIP-RKP-0{i + 1}", klass_b=True)
    ship("VSL-0457", "FV Pelican Ridge", "US", "fishing", 30, 24, 7, 2.1, 2.1, "Pelican Ridge Fisheries LLC", "Shrimp trawler",
         [], ["GATE-CAPE-SAN-BLAS"], [], [], "Gulf shrimp trawler; works the northeastern Gulf from Panama City, Florida, on trips of two to three weeks",
         home=None, home_port="Panama City, Florida", klass_b=False)
    for i, name in enumerate(["Jetty Runner", "Blue Marlin II", "Island Time", "Tarpon Ghost", "Sandollar"]):
        ship(f"VSL-{431 + i:04d}", name, "US", "charter", 37, 11 + i * 2, 4, 1.1, 1.1, "Owner-operated", "Charter fishing boat",
             [], [], [], [], "Half-day and full-day offshore and bay charters from Port Aransas", home=f"SLIP-PAH-{i + 2:02d}", klass_b=True)
    for i, (name, text, pat) in enumerate([("Island Dolphin", "Tour boat (49 passengers)", "Dolphin and sunset tours in the Lydia Ann Channel, several trips a day in season"),
                                           ("St. Jo Shuttle", "Passenger launch", "Shuttle between Port Aransas and San Jose Island, hourly in daylight")]):
        ship(f"VSL-{471 + i:04d}", name, "US", "passenger", 60, 16 - i * 4, 5, 1.0, 1.0, "Port Aransas Excursions LLC", text, [], [], [], [], pat,
             home=f"SLIP-PAH-{i + 8:02d}", klass_b=True)
    ship("VSL-0481", "Narwhal Dream", "MH", "recreational", 37, 26, 6, 1.7, 1.7, "Nereid Maritime Holdings LLC", "Motor yacht",
         [], ["GATE-FLORIDA-STRAITS"], [], [], "Visiting yacht", home=None, home_port="Bikini (registry)", klass_b=False, visiting=True)
    for i, (name, text, home, pat) in enumerate([("Second Wind", "Sailing yacht (38 ft)", "SLIP-CCM-01", "Weekend sailing on Corpus Christi Bay"),
                                                 ("Mistral", "Sailing yacht (42 ft)", "SLIP-CCM-02", "Wednesday-night races and weekend sailing on Corpus Christi Bay"),
                                                 ("Reel Tide", "Sportfishing boat (45 ft)", "SLIP-RKP-04", "Offshore fishing trips from Rockport, mostly weekends"),
                                                 ("Sea Breeze IV", "Motor yacht (52 ft)", "SLIP-PAH-10", "Occasional trips along the coast")]):
        ship(f"VSL-{482 + i:04d}", name, "US", "recreational", 36 if "Sailing" in text else 37, 12 + i, 4, 1.6, 1.6, "Private owner", text, [], [], [], [], pat,
             home=home, klass_b=True)
    for i, (name, op, text, home, pat) in enumerate([
            ("TPWD Marine 1207", "Texas Parks and Wildlife Department", "Game warden patrol boat", "SLIP-RKP-05", "Fisheries enforcement patrols in the bays"),
            ("Port Police 2", "Port of Corpus Christi Authority Police", "Harbor patrol boat", "TERM-22-B01", "Security patrols of the Inner Harbor and La Quinta"),
            ("CCFD Marine 1", "Corpus Christi Fire Department", "Fireboat", "SLIP-CCM-03", "Marine firefighting and rescue on the bayfront and in the Inner Harbor")]):
        ship(f"VSL-{491 + i:04d}", name, "USG" if i == 0 else "US", "public_safety", 55 if i < 2 else 51, 10 + i, 3, 0.8, 0.8, op, text, [], [], [], [], pat,
             home=home, klass_b=True)
    # dark vessel: registry entry is neutral
    ship("VSL-0031", "MV Halcyon Drift", "PW", "tanker", 80, 176, 30, 8.8, 5.9, "Seren Ocean Navigation Ltd.", "Product tanker",
         [], ["GATE-YUCATAN"], ["(none filed)"], ["(none filed)"], "No regular trade to this port on record", vendor=None)


def build_vessels(reg):
    fleet()
    berth_ids = {b["berth_id"] for b in reg["berths"]} | {s["slip_id"] for s in reg["slips"]}
    out = []
    for s in SHIPS:
        r = rng_for("attrs:" + s["vessel_name"])
        k = s["klass"]
        want_imo = k in ("tanker", "lng", "bulk", "cargo", "roro", "offshore_supply") or s.get("imo") or (k in ("spill_response", "navy") and s["loa"] >= 60) \
            or s["vessel_name"] in ("USCGC Resolute Bay",)
        has_ais = s.get("ais", True)
        mmsi, imo, call = ident(s["vessel_name"], s["flag"], want_imo)
        if not has_ais:
            USED_MMSI.discard(mmsi)
            mmsi, call = None, None
        if k == "barge" and has_ais:
            call = None
        cls_ais = None if not has_ais else ("B" if (s.get("klass_b") or k == "barge" or (k in ("coast_guard", "navy", "public_safety", "survey") and s["loa"] < 20)) else "A")
        home = s.get("home")
        if home and home not in berth_ids:
            raise SystemExit(f"{s['vessel_name']}: home {home} not in terminal registry")
        deep = s["draft"] >= 9.0 and k not in ("navy",) and s["vessel_id"] != "VSL-0031"
        gt = int(s["loa"] * s["beam"] * (6.0 if k in ("tanker", "lng", "bulk") else 3.2) * (1.0 if s["loa"] > 100 else 0.12))
        rec = {"vessel_id": s["vessel_id"], "mmsi": mmsi, "imo": imo, "call_sign": call, "vessel_name": s["vessel_name"],
               "class": "tug" if k == "tug" else k, "sub_class": s.get("kind_note") or s["text"], "ais_type_code": s["code"],
               "vessel_type_desc": s["text"], "flag": FLAGS[s["flag"]][0], "flag_code": "US" if s["flag"] == "USG" else s["flag"],
               "operator": s["operator"], "length_m": s["loa"], "beam_m": s["beam"], "draft_m": s["draft"], "draft_ballast_m": s["ballast"],
               "deep_draft": bool(deep), "gross_tonnage": gt, "year_built": 2004 + r.randrange(0, 20),
               "transceiver_class": cls_ais, "home_berth_id": home,
               "home_port": s.get("home_port") or (None if home is None and k in ("tanker", "lng", "bulk", "cargo", "roro") else
                                                   ("Corpus Christi area" if home else None)),
               "usual_berths": s["terminals"], "sea_gates": s["gates"], "usual_previous_ports": s["last"], "usual_next_ports": s["nxt"],
               "typical_pattern": s["pattern"]}
        if rec["home_port"] is None and k in ("tanker", "lng", "bulk", "cargo", "roro"):
            rec["home_port"] = "foreign-going; no local home berth"
        if "vendor" in s and k in ("tanker", "lng"):
            rec["cargo_control_system_vendor"] = s["vendor"]
        if s.get("unmanned"):
            rec["unmanned"] = True
        if s.get("visiting"):
            rec["visiting"] = True
        out.append(rec)
    out.sort(key=lambda v: v["vessel_id"])
    by_class = {}
    for v in out:
        by_class[v["class"]] = by_class.get(v["class"], 0) + 1
    reg_v = {"metadata": {"dataset": "Vessel registry, Corpus Christi area", "schema_version": "2.0", "generated": GENERATED,
                          "generated_by": "scripts/build_registries_maritime_air.py",
                          "description": "Vessels that appear in the AIS, port-call and incident data. Vessel, owner and operator names are fictional; "
                                         "government agencies are real. MMSI prefixes match the flag. IMO numbers carry valid check digits but are not real ships.",
                          "joins": "mmsi joins AIS (MMSI) and supply/vessel_arrivals.csv (mmsi); home_berth_id and usual_berths join terminal_registry.json "
                                   "(berths[].berth_id, slips[].slip_id, terminals[].terminal_id); sea_gates joins terminal_registry.json sea_gates[].gate_id.",
                          "fields": {"deep_draft": "true when the vessel needs the dredged 40 ft+ ship channel inside the port",
                                     "draft_m": "maximum (laden) draft; draft_ballast_m is the light draft",
                                     "transceiver_class": "A, B, or null when the hull carries no AIS transponder"},
                          "counts": {"vessels": len(out), "by_class": dict(sorted(by_class.items()))}},
             "vessels": out}
    return reg_v


def vessels_truth(reg_v):
    by_name = {v["vessel_name"]: v for v in reg_v["vessels"]}
    vid = lambda n: by_name[n]["vessel_id"]
    queue = ["MV Gulf Provider", "MV Halcyon Drift", "MT Valdris Sun", "MT Brazos Star", "MT Orinda Bay", "MT Halcyon Aegis", "MT Narvik Pioneer",
             "MT Corpus Prince", "MT Pacific Prism", "MT Galveston Star", "MV Sable Horizon", "MV Capehorn Eagle", "MT Aransas Spirit", "MT Storm Rider"]
    truth = {
        "VSL-0041": {"role": "Laden tanker at TERM-01 Berth 7 from D-3; cargo valves opened remotely 04:00Z-05:30Z D0 (with VSL-0042, about 9,000 bbl). "
                             "Never leaves the berth during the scenario (Captain of the Port order from D+6; departure not set in canon).",
                     "threads": ["T6", "T12", "T20"], "events": ["EVT-0209", "EVT-0210", "EVT-0313", "EVT-1203", "EVT-1207"], "public_name_from_day": 1},
        "VSL-0042": {"role": "Second laden tanker at TERM-01 Berth 8; same attack.", "threads": ["T6", "T12", "T20"],
                     "events": ["EVT-0209", "EVT-0210", "EVT-0313", "EVT-1203", "EVT-1207"], "public_name_from_day": 1},
        "VSL-0012": {"role": "Relief ship with 40 containers booked D-5; held offshore from D-2; rides out the storm at sea; waits at the anchorage D+3 to "
                             "D+33; berths at TERM-07 on D+33.", "threads": ["T1", "T5"], "events": ["EVT-0204", "EVT-0207", "EVT-0401"]},
        "VSL-0019": {"role": "Sealift ship for the Fort Hood aviation brigade; outload postponed D-3, restart planned D+45, loads and sails D+59 to D+64. "
                             "The name 'MV Cape Sandoval' is new in this registry; the Army never names the ship publicly.",
                     "threads": ["T7"], "events": ["EVT-0207", "EVT-0409"], "public_name": "never (described only as a sealift ship)"},
        "VSL-0031": {"role": "Sanctioned tanker serving STATE-X. Loiters at the offshore anchorage from D-45 under its true MMSI; in the Yankee queue; "
                             "puts to sea at Zulu and returns D+3; AIS silent 02:00Z-16:00Z on D+30/31 while it broadcasts FV Pelican Ridge's MMSI, lays "
                             "DEV-01 and DEV-02 about 2 nm off the entrance channel (04:20Z) and transfers 380 m3 of fuel to Barge 44 (09:30Z).",
                     "threads": ["T2", "T7", "T12"], "events": ["EVT-0104", "EVT-0207", "EVT-0402", "EVT-0403", "EVT-0411", "EVT-1201", "EVT-1203"],
                     "public_name": "never", "ais_rule": "no AIS gap before D+30 21:00 local; never enters the port; files no notice of arrival"},
        "VSL-0457": {"role": "Real fishing vessel, about 600 nm away in the northeastern Gulf on D+30/31, whose MMSI is broadcast by VSL-0031 off Port Aransas. "
                             "Home port Panama City, Florida (set in this registry so the 600 nm figure holds: Port Aransas to Cape San Blas is about 590-625 nm).",
                     "threads": ["T2"], "events": ["EVT-0402"], "public_name_from_day": 38},
        "BRG-0044": {"role": "Receives 380 m3 of fuel from VSL-0031 alongside at the anchorage (radar: two hulls, one with no AIS match) at 09:30Z D+31 and "
                             "delivers it up the ship channel to TERM-02 (SUP-0390, Quellmar) on D+32.", "threads": ["T2", "T3"],
                     "events": ["EVT-0403", "EVT-0404"], "public_name": "never", "pushed_by": vid("Matagorda Star")},
        vid("Matagorda Star"): {"role": "Towboat that pushes Barge 44 on D+31/32 (pairing chosen in the registry pass; canon names only the barge)."},
        "VSL-0077": {"role": "Harbor tug damaged when DEV-01 detonates beside it near the Port Aransas jetties at 06:10Z D+44; two crew injured "
                             "(master Ray Dupree, deckhand Eddie Fontenot). Repaired at TERM-20 afterwards.",
                     "threads": ["T7"], "events": ["EVT-0413"], "public_name_from_day": 44},
        "VSL-0481": {"role": "Front-company yacht (Nereid Maritime Holdings LLC) used as the launch point for the pre-storm drone sorties; at Ingleside Marina "
                             "Berth 7 (SLIP-ING-07) D-12 to D-8, AIS last seen 2027-09-07T00:14Z, then dark.", "threads": ["T19"],
                     "events": ["EVT-1901", "EVT-1902", "EVT-1903", "EVT-1906"], "public_name": "never"},
        vid("MT Halcyon Aegis"): {"role": "Ordinary Suezmax with a similar name to VSL-0031; a deliberate distractor."},
    }
    for n in ("NAVY EOD 11M-1", "NAVY EOD 11M-2", "NAVY MCM USV-07", "USNS Muskogee Bend"):
        truth[vid(n)] = {"role": "Navy channel search after the jetty blast, D+46 to D+58 (EOD and mine countermeasures); the salvage ship supports the "
                                 "spill response from about D+3 (Navy salvage equipment requested D+1).", "events": ["EVT-0315", "EVT-0414"]}
    brightwake = [v["vessel_id"] for v in reg_v["vessels"] if v.get("cargo_control_system_vendor") == "Brightwake Marine Systems"]
    sets = {"yankee_queue_14": {"what": "The 14 inbound vessels holding at the offshore anchorage under Port Condition Yankee (D-2 to D-1 18:00 local)",
                                "vessels": [vid(n) for n in queue], "sources": ["EVT-0207", "PUB-107"],
                                "note": "Canon names only Gulf Provider and Halcyon Drift; the other twelve are chosen here."},
            "brightwake_fleet": {"what": "Tankers whose cargo-control systems are maintained by Brightwake Marine Systems (credentials misused; public D+8)",
                                 "vessels": brightwake, "note": "Only VSL-0041 and VSL-0042 were attacked."},
            "storm_riders": {"what": "Ships that put to sea at Zulu and return to the anchorage on D+3", "vessels": [vid(n) for n in queue]},
            "spill_response": {"what": "Vessels working the Inner Harbor spill from D+2", "vessels": [v["vessel_id"] for v in reg_v["vessels"] if v["class"] == "spill_response"]}}
    # ---- migration from every old identifier
    mig = {"by_old_vessel_id": {}, "by_old_mmsi": {}, "by_old_name": {}, "by_scenario_entity": {}}
    old = json.load(open(os.path.join(ROOT, "_versions", "pre_registry_20261109", "vessels.json"), encoding="utf-8"))["vessels"] \
        if os.path.exists(os.path.join(ROOT, "_versions", "pre_registry_20261109", "vessels.json")) else []
    alias = {"Kalvora Star": "MT Kalvora Star", "Ostrel Bay": "MT Ostrel Bay", "CCPILOT-1": "Aransas Pilot I", "CCPILOT-2": "Aransas Pilot II",
             "USCGC Dependable": "USCGC Resolute Bay", "USCGC Capelin": "USCGC Cormorant Point", "USCGC Elm Buoy Tender": "USCGC Live Oak",
             "MV Army Corps Pioneer": "SV Tejas Sounder", "Marine Spill Response I": "Responder Aransas", "Marine Spill Response II": "GS Skimmer 11",
             "Bayou Spirit": "MT Bayou Spirit", "Santos Provider": "MT Santos Provider", "Adriatic Carrier": "MV Adriatic Carrier",
             "Pacific Trader": "MV Pacific Trader", "Coastal Endeavor": "MV Coastal Endeavor", "Gulf Meridian": "MT Aldebaran Trader",
             "MT Lone Star LNG": "MT Lone Star Aurora", "MT Corpus LNG I": "MT Coastal Bend Energy", "MV Rio Bulk Carrier": "MV Rio Hondo",
             "MT Refugio Bay Trader": "MT Refugio Bay", "MT Harbor Bay Crude": "MT Harbor Bay", "MV Roosevelt Island": "MV Roosevelt Island",
             "MT Rio Grande Tanker": "MT Aldebaran Trader", "MT La Quinta Crude": "MT La Quinta Express", "MT South Padre Crude": "MT Maverick Bay",
             "MT Lone Star Crude 2": "MT Lone Star Carrier", "MT Lone Star Suezmax": "MT Storm Rider", "MT Corpus Christi Star": "MT Corpus Prince",
             "MT Nueces Bay Tanker": "MT Copano Mist", "MT South Texas Product": "MT Tarpon Reach", "MT Galveston Product": "MT Rockport Trader",
             "MT CC Chemical I": "MT Gulf Chemist", "MT CC Chemical II": "MT Laguna Verde", "MT Nueces Chemical": "MT Laguna Verde",
             "MV Corpus Bay Freighter": "MV San Antonio Bay", "MV Aransas Pass Cargo": "MV Coastal Express", "MV Houston Supply": "MV Gulf Rebuilder",
             "MV Lone Star Container": "MV Port Royal", "MV Corpus Containers I": "MV Port Royal", "MV Gulf Ferry Express": "MV Roosevelt Island",
             "MV Narvik Pioneer FEMA2": "MV Galveston Relief", "Sealift ro-ro ship (synthetic name)": "MV Cape Sandoval",
             "Tug Corrin Bay": "Corrin Bay", "Barge 44": "Barge 44"}
    src = json.load(open(os.path.join(INT, "_old_identifiers.json"), encoding="utf-8"))
    for name, mm in src["names_mmsi"]:
        if not name:
            continue
        new = by_name.get(name) or by_name.get(alias.get(name, ""))
        entry = {"new_vessel_id": new["vessel_id"] if new else None, "new_name": new["vessel_name"] if new else None, "new_mmsi": new["mmsi"] if new else None}
        if new and new["vessel_name"] != name:
            entry["note"] = "old name retired; mapped to the nearest equivalent in the new fleet" if name not in ("Kalvora Star", "Ostrel Bay") else "prefix restored"
        if not new:
            entry["note"] = "no equivalent in the new fleet"
        mig["by_old_name"].setdefault(name, entry)
        if mm:
            mig["by_old_mmsi"].setdefault(mm, dict(entry, old_name=name))
    for ovid, name in src["old_vessel_ids"]:
        new = by_name.get(name) or by_name.get(alias.get(name, ""))
        mig["by_old_vessel_id"][ovid] = {"new_vessel_id": new["vessel_id"] if new else None, "old_name": name}
    ent = {"VSL-0012": "VSL-0012", "VSL-0019": "VSL-0019", "VSL-0031": "VSL-0031", "VSL-0457": "VSL-0457", "BRG-0044": "BRG-0044",
           "VSL-0041": "VSL-0041", "VSL-0042": "VSL-0042", "VSL-0077": "VSL-0077"}
    keys = {"VSL-0012": "MMSI-SYN-0101", "VSL-0019": "MMSI-SYN-0119", "VSL-0031": "MMSI-SYN-0131 / IMO-SYN-9031", "VSL-0457": "MMSI-SYN-0457",
            "BRG-0044": "MMSI-SYN-0444", "VSL-0041": "MMSI-SYN-0141", "VSL-0042": "MMSI-SYN-0142", "VSL-0077": "MMSI-SYN-0177"}
    regv = {v["vessel_id"]: v for v in reg_v["vessels"]}
    for e, n in ent.items():
        mig["by_scenario_entity"][e] = {"new_vessel_id": n, "placeholder_key": keys[e], "mmsi": regv[n]["mmsi"], "imo": regv[n]["imo"],
                                        "note": "00_scenario/entities.json keeps the same id; replace the MMSI-SYN placeholder with this MMSI"}
    mig["notes"] = ["Old vessels.json used VSL-001..VSL-028; the scenario files used four-digit ids for the same ships. The four-digit scenario ids win.",
                    "MV Halcyon Drift: old MMSI 416002317 (Taiwan prefix) replaced by a Palau-prefixed MMSI; old type 'general cargo' corrected to tanker (canon: sanctioned tanker).",
                    "FV Pelican Ridge: old registry based it at Port Aransas, which contradicts canon (it reports from 600 nm away); now Panama City, Florida.",
                    "The canon ships keep the MMSIs already in use (Kalvora Star, Ostrel Bay, Gulf Provider, Pelican Ridge, Corrin Bay). "
                    "Every other vessel has a newly generated MMSI with the right prefix for its flag; US commercial craft use 367, US government 369."]
    return {"_about": "Internal. Scenario roles of vessels, scenario sets, and the map from every old identifier. Never give this file to participants.",
            "truth": truth, "scenario_sets": sets, "id_migration": mig}


# ======================================================================================
# 3. aircraft
# ======================================================================================
OUT_OF_AREA = {  # fetched 2026-11-09 from USDOT NTAD Aviation Facilities (FAA NASR), airport reference points
    "NFW": ("Fort Worth NAS JRB (Carswell Field)", 32.7691861, -97.4415347), "SAT": ("San Antonio International", 29.5339583, -98.4690569),
    "EFD": ("Ellington (Houston)", 29.6073333, -95.1587500), "HOU": ("William P. Hobby (Houston)", 29.6457998, -95.2772316),
    "SKF": ("Kelly Field (San Antonio)", 29.3842333, -98.5811167), "GRK": ("Robert Gray Army Airfield (Fort Hood)", 31.0672500, -97.8289167),
    "ALI": ("Alice International", 27.7408889, -98.0269444), "AUS": ("Austin-Bergstrom International", 30.1945272, -97.6698761),
    "CHS": ("Charleston AFB / International", 32.8986389, -80.0405278), "IAH": ("George Bush Intercontinental (Houston)", 29.9844353, -95.3414425),
    "LAL": ("Lakeland Linder International", 27.9876389, -82.0190000), "VCT": ("Victoria Regional", 28.8542055, -96.9187317),
    "BRO": ("Brownsville / South Padre Island International", 25.9061389, -97.4260000), "DAL": ("Dallas Love Field", 32.8459447, -96.8508767),
    "DFW": ("Dallas-Fort Worth International", 32.8972331, -97.0376947), "MFE": ("McAllen International", 26.1758333, -98.2386111),
    "MSY": ("Louis Armstrong New Orleans International", 29.9932722, -90.2590275)}


def build_aircraft():
    airfields, parking = [], []

    def local(lid):
        l = next(x for x in G.find("airport") if f"({lid}" in x["name"] or f"/{lid}" in x["name"] or f"({lid}/" in x["name"])
        key = next((k for k in G.runways if lid in k.split("(")[-1]), None)
        rws = [{"runway": n, "end_1": [R5(a[0]), R5(a[1])], "end_2": [R5(b[0]), R5(b[1])], "length_m": round(geo.dist_m(a, b))}
               for n, a, b in G.runways.get(key, [])]
        return l, rws

    names = {"CRP": "Corpus Christi International Airport", "NGP": "NAS Corpus Christi (Truax Field)", "NGW": "Cabaniss Field (Navy outlying field)",
             "NWL": "Waldron Field (Navy outlying field)", "RAS": "Mustang Beach Airport, Port Aransas", "RKP": "Aransas County Airport, Rockport",
             "TFP": "Ingleside Regional (McCampbell-Porter)", "NQI": "NAS Kingsville"}

    def apron(lid, n, anchor=None, spacing=45.0, min_rwy=170.0, label="apron", skip=0):
        """Parking positions near the airfield reference point: on land, at least min_rwy metres from
        every runway centreline, laid out in rows. Apron outlines are not in the reference data."""
        l, rws = local(lid)
        a0 = anchor or (l["lat"], l["lon"])
        cands = []
        for dy in range(-16, 17):
            for dx in range(-16, 17):
                la = a0[0] + dy * spacing / geo.M_PER_DEG_LAT
                lo = a0[1] + dx * spacing / geo.M_PER_DEG_LON
                if G.in_box(la, lo) and G.is_land(la, lo) is False:
                    continue
                dr, apt = G.runway_distance_m(la, lo)
                # 450 m keeps a parked aircraft inside the 500 m ground rule of check_geo ("aircraft_ground")
                if dr < min_rwy or dr > 450 or (G.in_box(la, lo) and G.shore_distance_m(la, lo) < 40):
                    continue
                cands.append((geo.dist_m(a0, (la, lo)), la, lo, dr))
        cands.sort()
        out = []
        if not cands:           # no runway geometry for this field: fall back to the reference point
            return [f"PARK-{lid}-01"] * n
        for i, (d, la, lo, dr) in enumerate(cands[skip:skip + n]):
            pid = f"PARK-{lid}-{label[:1].upper()}{i + 1:02d}"
            p = {"position_id": pid, "airfield_id": lid, "kind": label, "latitude": R5(la), "longitude": R5(lo),
                 "distance_to_runway_centreline_m": round(dr),
                 "position_basis": "on land, 170-450 m from the nearest runway centreline, nearest to the airfield's reference point or main "
                                   "base area; apron outlines are not in the reference data, so this is an approximate ramp position"}
            parking.append(p)
            out.append(pid)
        return out

    def pad(pid, lm, kind):
        p = {"position_id": pid, "airfield_id": None, "kind": kind, "latitude": R5(lm["lat"]), "longitude": R5(lm["lon"]),
             "reference": str(lm.get("source_id", "")).split(";")[0].strip(),
             "position_basis": "published heliport reference point (FAA NASR via USDOT NTAD)"}
        parking.append(p)
        return pid

    nas_anchor = next((l["lat"], l["lon"]) for l in G.find("military") if "Naval Air Station Corpus Christi" in l["name"] and abs(l["lon"] + 97.279) < 0.01)
    spots = {}
    for lid in ("CRP", "NGP", "NGW", "NWL", "RAS", "RKP", "TFP", "NQI"):
        l, rws = local(lid)
        airfields.append({"airfield_id": lid, "icao": "K" + lid, "name": names[lid], "latitude": R5(l["lat"]), "longitude": R5(l["lon"]),
                          "runways": rws, "in_local_area": bool(G.in_box(l["lat"], l["lon"])),
                          "coordinate_source": "FAA NASR airport reference point and runway ends via USDOT NTAD (99_reference/geo/landmarks.geojson)"})
    spots["CRP-CG"] = apron("CRP", 6, label="government ramp")
    spots["CRP-GA"] = apron("CRP", 16, label="apron", skip=6)
    spots["NGP-NAVY"] = apron("NGP", 16, anchor=nas_anchor, label="military ramp")
    spots["NGP-TRANSIENT"] = apron("NGP", 10, anchor=nas_anchor, label="transient ramp", skip=16)
    spots["NQI"] = apron("NQI", 6, label="military ramp")
    spots["RAS"] = apron("RAS", 2, label="apron", min_rwy=90.0)
    spots["RKP"] = apron("RKP", 2, label="apron", min_rwy=120.0)
    spots["TFP"] = apron("TFP", 2, label="apron", min_rwy=120.0)
    for lid, (nm, la, lo) in OUT_OF_AREA.items():
        airfields.append({"airfield_id": lid, "icao": "K" + lid, "name": nm, "latitude": R5(la), "longitude": R5(lo), "runways": [],
                          "in_local_area": False,
                          "coordinate_source": "FAA NASR airport reference point via USDOT NTAD Aviation Facilities, fetched 2026-11-09 (outside the local map window)"})
        parking.append({"position_id": f"PARK-{lid}-01", "airfield_id": lid, "kind": "out-of-area base", "latitude": R5(la), "longitude": R5(lo),
                        "position_basis": "airport reference point (out of the local window; no ramp position derived)"})
    hp = {l["name"]: l for l in G.find("helipad")}
    pad_halo = pad("PARK-HELI-TX10", next(v for k, v in hp.items() if "TX10" in k), "heliport")
    pad_dps = pad("PARK-HELI-3TX0", next(v for k, v in hp.items() if "3TX0" in k), "heliport")
    pad_south = pad("PARK-HELI-1XA3", next(v for k, v in hp.items() if "1XA3" in k), "hospital helipad")
    for k, v in hp.items():
        code = k.split("(")[-1].strip(")")
        if code not in ("TX10", "3TX0", "1XA3") and G.in_box(v["lat"], v["lon"]):
            pad(f"PARK-HELI-{code}", v, "hospital helipad" if any(w in k for w in ("Hospital", "Medical", "Spohn", "D.F.C.H", "Meml")) else "heliport")

    used_hex = set()

    def hexa(key, mil):
        r = rng_for("icao:" + key)
        while True:
            h = ("ae" + "%04x" % r.randrange(0x0800, 0xf000)) if mil else ("a" + "%05x" % r.randrange(0x08000, 0xdffff))
            if h not in used_hex:
                used_hex.add(h)
                return h

    ac = []

    def add(aid, reg_, callsign, tdes, model, operator, role, base, park, kt, alt, cat, mil=False, n_ops=None, **kw):
        a = {"aircraft_id": aid, "icao24": hexa(aid, mil), "registration": reg_, "callsign": callsign, "type_designator": tdes, "model": model,
             "operator": operator, "role": role, "home_base": base, "parking_position_id": park, "cruise_speed_kt": kt, "cruise_altitude_ft": alt,
             "adsb_emitter_category": cat, "origin_country": "United States", "military": mil}
        a.update(kw)
        ac.append(a)

    cgp = spots["CRP-CG"]
    for i, (tail, cs_) in enumerate([("6033", "C6033"), ("6041", "C6041"), ("6017", "C6017"), ("6028", "C6028")]):
        add(f"ACF-USCG-{i + 1:03d}", "CG-" + tail, cs_, "H60", "MH-60T Jayhawk", "U.S. Coast Guard Air Station Corpus Christi", "Search and rescue", "CRP", cgp[i], 125, 1500, 8, True)
    for i, tail in enumerate(["2306", "2311"]):
        add(f"ACF-USCG-{i + 5:03d}", "CG-" + tail, "C" + tail, "CN35", "HC-144B Ocean Sentry", "U.S. Coast Guard Air Station Corpus Christi", "Maritime patrol and search", "CRP", cgp[4 + i], 215, 8000, 3, True)
    nv = spots["NGP-NAVY"]
    add("ACF-CBP-001", "CBP-104", "CAMCC-04", "Q9", "MQ-9 Predator B (maritime variant, unmanned)", "U.S. Customs and Border Protection, Air and Marine Operations Corpus Christi",
        "Maritime patrol (unmanned)", "NGP", nv[0], 170, 19000, 14, True, unmanned=True)
    add("ACF-CBP-002", "N3941A", "CAMCC-11", "AS50", "Airbus AS350 B3", "U.S. Customs and Border Protection, Air and Marine Operations Corpus Christi",
        "Law enforcement, search and rescue support", "NGP", nv[1], 115, 1200, 8)
    add("ACF-CBP-003", "N802MR", "CAMCC-21", "DH8B", "DHC-8 maritime patrol aircraft", "U.S. Customs and Border Protection, Air and Marine Operations Corpus Christi",
        "Maritime patrol", "NGP", nv[2], 230, 10000, 3)
    add("ACF-DPS-001", "N110TX", "DPS110", "AS50", "Airbus AS350 B3", "Texas Department of Public Safety, Aircraft Operations Division", "Law enforcement, hoist rescue", None, pad_dps, 115, 1200, 8)
    add("ACF-DPS-002", "N201TX", "DPS201", "PC12", "Pilatus PC-12 Spectre", "Texas Department of Public Safety, Aircraft Operations Division", "Surveillance and transport", "CRP", spots["CRP-GA"][0], 260, 14000, 1)
    for i in range(3):
        add(f"ACF-TXNG-{i + 1:03d}", f"88-2601{3 + i}", f"GUNSMOKE0{i + 1}", "H60", "UH-60L Black Hawk", "Texas Army National Guard, 1-149th Aviation Battalion",
            "Reconnaissance and rescue support", "AUS", "PARK-AUS-01", 130, 1500, 8, True)
    add("ACF-ARMY-001", "13-74005", "RIDGELINE01", "H47", "CH-47F Chinook", "U.S. Army, combat aviation brigade (Fort Hood)", "Heavy lift", "GRK", "PARK-GRK-01", 140, 2000, 8, True)
    for i in range(8):
        add(f"ACF-NAVY-{i + 1:03d}", f"1669{10 + i * 3:02d}", f"MARLIN{11 + i}", "TEX2", "T-6B Texan II", "U.S. Navy, Training Air Wing Four", "Primary flight training", "NGP", nv[3 + i], 200, 8000, 1, True)
    for i in range(4):
        add(f"ACF-NAVY-{i + 9:03d}", f"1615{20 + i * 4:02d}", f"PELICAN{21 + i}", "BE9L", "T-44C Pegasus", "U.S. Navy, Training Air Wing Four", "Multi-engine flight training", "NGP", nv[11 + i], 210, 9000, 2, True)
    for i in range(6):
        add(f"ACF-NAVY-{i + 13:03d}", f"1656{30 + i * 2:02d}", f"JAVELINA{31 + i}", "T45", "T-45C Goshawk", "U.S. Navy, Training Air Wing Two", "Jet flight training", "NQI", spots["NQI"][i], 350, 15000, 6, True)
    tr = spots["NGP-TRANSIENT"]
    add("ACF-NAVY-019", "167841", "NAVYHK21", "H60", "MH-60S Seahawk (airborne mine countermeasures fit)", "U.S. Navy, helicopter sea combat squadron detachment",
        "Mine countermeasures support (deployed)", "NGP", tr[0], 120, 500, 8, True, visiting=True)
    add("ACF-ARMY-002", "13-72221", "CCAD31", "H60", "UH-60M Black Hawk", "Corpus Christi Army Depot", "Maintenance test flight", "NGP", nv[15], 120, 1500, 8, True)
    add("ACF-ARMY-003", "14-03044", "CCAD44", "H64", "AH-64E Apache", "Corpus Christi Army Depot", "Maintenance test flight", "NGP", tr[1], 120, 1500, 8, True)
    add("ACF-NOAA-001", "NOAA 42", "NOAA42", "P3", "WP-3D Orion", "NOAA Aircraft Operations Center", "Hurricane reconnaissance", "LAL", "PARK-LAL-01", 300, 10000, 4)
    add("ACF-FEMA-001", "N350FM", "FEMA01", "B350", "Beechcraft King Air 350", "Federal Emergency Management Agency (contract aircraft)", "Aerial assessment and staff transport", "SAT", "PARK-SAT-01", 280, 20000, 2)
    add("ACF-CAP-001", "N4216C", "CAP4216", "C182", "Cessna 182T", "Civil Air Patrol, Texas Wing", "Damage photography", "CRP", spots["CRP-GA"][1], 135, 3000, 1)
    add("ACF-CAP-002", "N4227C", "CAP4227", "C182", "Cessna 182T", "Civil Air Patrol, Texas Wing", "Damage photography", "VCT", "PARK-VCT-01", 135, 3000, 1)
    add("ACF-MED-001", "N429BF", "AIRMED1", "B429", "Bell 429", "Bayfront AirMed", "Air ambulance", None, pad_halo, 140, 1500, 8)
    add("ACF-MED-002", "N135BF", "AIRMED2", "EC35", "Airbus H135", "Bayfront AirMed", "Air ambulance", None, pad_south, 130, 1500, 8)
    add("ACF-NEWS-001", "N606HL", "SKY6", "B06", "Bell 206L-4 LongRanger", "Harborline 6 News", "News gathering", "CRP", spots["CRP-GA"][2], 105, 1500, 8)
    add("ACF-SURVEY-001", "N208CB", "CBAS208", "C208", "Cessna 208B Grand Caravan (thermal sensor)", "Coastal Bend Aerial Services", "Aerial survey", "CRP", spots["CRP-GA"][3], 160, 2500, 1)
    add("ACF-SURVEY-002", "N424SV", "EAGLE424", "C206", "Cessna 206 Stationair", "South Texas Aerial Surveys", "Aerial survey and pipeline patrol", "CRP", spots["CRP-GA"][4], 130, 1500, 1)
    for i in range(5):
        add(f"ACF-{201 + i:04d}", f"0{i + 3}-{8190 + i * 7}", f"SYN{41 + i}", "C17", "C-17A Globemaster III", "U.S. Air Force, Air Mobility Command", "Strategic airlift",
            "CHS" if i < 3 else "SKF", "PARK-CHS-01" if i < 3 else "PARK-SKF-01", 430, 31000, 5, True)
    for i, (reg_, cs_, td, model, op, base) in enumerate([("N781GX", "GCX301", "B734", "Boeing 737-400F", "Gulf Charter Express", "HOU"),
                                                          ("N757GX", "GCX302", "B752", "Boeing 757-200F", "Gulf Charter Express", "DFW"),
                                                          ("N372BZ", "BZA303", "AT72", "ATR 72-600F", "Brazos Air Cargo", "SAT")]):
        add(f"ACF-{301 + i:04d}", reg_, cs_, td, model, op, "Civil cargo charter", base, f"PARK-{base}-01", 280 if td == "AT72" else 440, 24000 if td == "AT72" else 34000, 3 if td == "AT72" else 4)
    for i, (reg_, cs_, td, model, op, base) in enumerate([("N175CP", "CPA2231", "E75L", "Embraer 175", "Coastal Plains Airways", "DFW"),
                                                          ("N176CP", "CPA2245", "E75L", "Embraer 175", "Coastal Plains Airways", "IAH"),
                                                          ("N177CP", "CPA2262", "E75L", "Embraer 175", "Coastal Plains Airways", "DFW"),
                                                          ("N702LM", "LMA614", "CRJ7", "Bombardier CRJ700", "Lone Mesa Air", "HOU"),
                                                          ("N705LM", "LMA628", "CRJ7", "Bombardier CRJ700", "Lone Mesa Air", "DAL")]):
        add(f"ACF-AIR-{i + 1:03d}", reg_, cs_, td, model, op, "Scheduled passenger service to Corpus Christi International", base, f"PARK-{base}-01", 430, 33000, 3, scheduled=True, serves="CRP")
    ga = [("N7312K", "C172", "Cessna 172S", "Bayfront Flying Club", "Flight training and rental", "CRP", spots["CRP-GA"][5], 115, 3000),
          ("N58PA", "P28A", "Piper Archer", "Private owner", "Personal flying", "RAS", spots["RAS"][0], 120, 3500),
          ("N922SR", "SR22", "Cirrus SR22", "Private owner", "Personal and business flying", "RKP", spots["RKP"][0], 170, 7000),
          ("N36BN", "BE36", "Beechcraft Bonanza A36", "Private owner", "Personal flying", "TFP", spots["TFP"][0], 165, 6000),
          ("N200KC", "BE20", "Beechcraft King Air 200", "Kleberg Ranch Aviation LLC", "Corporate transport", "CRP", spots["CRP-GA"][6], 260, 21000),
          ("N8841Q", "C172", "Cessna 172N", "Private owner", "Personal flying", "RAS", spots["RAS"][1], 110, 3000)]
    for i, (reg_, td, model, op, role, base, park, kt, alt) in enumerate(ga):
        add(f"ACF-GA-{i + 1:03d}", reg_, reg_, td, model, op, role, base, park, kt, alt, 1 if td != "BE20" else 2)
    by_role = {}
    for a in ac:
        k = a["operator"].split(",")[0]
        by_role[k] = by_role.get(k, 0) + 1
    reg = {"metadata": {"dataset": "Aircraft registry, Corpus Christi area", "schema_version": "2.0", "generated": GENERATED,
                        "generated_by": "scripts/build_registries_maritime_air.py",
                        "description": "Aircraft that appear in the ADS-B data. Civil operators, registrations and call signs are fictional; government "
                                       "agencies and military units are real organisations with invented tail numbers. ICAO 24-bit addresses are in the "
                                       "United States civil (a.....) or military (ae....) ranges and are not derived from the registrations.",
                        "joins": "icao24 joins ADS-B (icao24); home_base joins airfields[].airfield_id; parking_position_id joins parking_positions[].position_id.",
                        "note_on_unmanned": "Only aircraft that carry a transponder are listed. Small unmanned aircraft are in drone_operators.json.",
                        "counts": {"aircraft": len(ac), "airfields": len(airfields), "parking_positions": len(parking)}},
           "aircraft": ac, "airfields": airfields, "parking_positions": parking}
    truth = {
        "_about": "Internal. Scenario roles of aircraft and the map from every old identifier. Never give this file to participants.",
        "truth": {
            "ACF-USCG-001": {"role": "CG-6033: pre-positioned at NAS Corpus Christi 19:15Z D-1; launches 06:22Z D0, first hoist 06:51Z at Flour Bluff; returns to routine tasking D+3.",
                             "events": ["EVT-1701", "EVT-1702", "EVT-1703", "EVT-1705"], "threads": ["T17"]},
            "ACF-USCG-002": {"role": "CG-6041: pre-positioned with CG-6033; on standby from D+3.", "events": ["EVT-1701", "EVT-1703", "EVT-1705"], "threads": ["T17"]},
            "ACF-CBP-001": {"role": "CAMCC-04: electronic support measures detect the drone data link during sortie 2 at 06:47Z on D-9 (bearing toward Ingleside Marina).",
                            "events": ["EVT-1902", "EVT-1906"], "threads": ["T19"]},
            "ACF-NOAA-001": {"role": "NOAA42: synthetic aperture radar pass at 08:30Z D0, first image of the slick; the only manned non-rescue flight inside the TFR window.",
                             "events": ["EVT-1102"], "threads": ["T11", "T20"]},
            "ACF-TXNG-001..003": {"role": "Three UH-60 reconnaissance sorties from Austin-Bergstrom at 16:00Z D+1; sortie S02 films GW-FAC-SUB-02.", "events": ["EVT-1103"], "threads": ["T11"]},
            "ACF-SURVEY-001": {"role": "Coastal Bend Aerial Services Cessna 208B: thermal pass over the substation corridor at dawn on D+11.", "events": ["EVT-1106"], "threads": ["T11"]},
            "ACF-0201..0205": {"role": "26 C-17 relief sorties into NAS Corpus Christi D+34 to D+43 (entity ACF-0201); GPS interference from JAM-01 lowers "
                                       "their NIC/NACp values D+38 to D+43.", "events": ["EVT-0405", "EVT-0412"], "threads": ["T1", "T7"]},
            "ACF-0301..0303": {"role": "14 civil charter relief flights into NAS Corpus Christi D+34 to D+43 (entity ACF-0301).", "events": ["EVT-0405"]},
            "ACF-NAVY-001..018": {"role": "Training aircraft fly to NAS JRB Fort Worth (NFW) on D-4 and begin returning D+6.", "events": ["EVT-0205"], "public_from_day": -4},
            "ACF-NAVY-019": {"role": "Mine countermeasures helicopter for the channel search D+46 to D+58 (added in the registry pass; canon says only 'mine countermeasures teams')."},
            "airspace": {"rule": "TFR from 05:01Z D-2. No manned flight in the local area from then until after landfall except NOAA42 (08:30Z D0) and Coast Guard "
                                 "rescue helicopters from 06:22Z D0. Covert drones never appear in ADS-B."}},
        "id_migration": {
            "by_old_icao24": {"ae0a01": "ACF-USCG-001", "ae0a02": "ACF-USCG-002", "ae0a03": "ACF-USCG-005", "ae1b01": "ACF-TXNG-001", "ae1b02": "ACF-TXNG-002",
                              "a4d001": "ACF-FEMA-001", "ae0201": "ACF-0201", "ae0202": "ACF-0202", "ae0203": "ACF-0203", "a00301": "ACF-0301", "a00302": "ACF-0303",
                              "a3c001": "ACF-NEWS-001", "a3c002": None, "a66001": "ACF-NEWS-001", "7c1234": None, "ae2a01": None, "ae2a02": "ACF-NAVY-013",
                              "ae3c01": "ACF-ARMY-002", "ae3c02": None, "ae4d01": "ACF-ARMY-001", "a44001": "ACF-DPS-001", "a44002": None, "a55001": "ACF-MED-001",
                              "a55002": "ACF-MED-002", "a77001": "ACF-SURVEY-002", "a88001": None},
            "by_old_callsign": {"CGNR6540": "ACF-USCG-001", "CGNR6541": "ACF-USCG-002", "CGAS2306": "ACF-USCG-005", "GUNSMOKE01": "ACF-TXNG-001", "GNSMOKE1": "ACF-TXNG-001",
                                "GUNSMOKE02": "ACF-TXNG-002", "GNSMOKE2": "ACF-TXNG-002", "FEMA01": "ACF-FEMA-001", "SYN41": "ACF-0201", "RCH441": "ACF-0202",
                                "RCH801": "ACF-0203", "CLIPPER01": "ACF-0301", "SKW7730": "ACF-0303", "KIII1": "ACF-NEWS-001", "KIII7": "ACF-NEWS-001", "KRIS1": None,
                                "NAV851": None, "NAV097": "ACF-NAVY-013", "CCAD31": "ACF-ARMY-002", "WARLORD01": None, "RIDGELINE01": "ACF-ARMY-001",
                                "TXDPS44": "ACF-DPS-001", "TXDPS302": None, "LIFESTAR1": "ACF-MED-001", "LIFESTAR2": "ACF-MED-002", "EAGLE424": "ACF-SURVEY-002", "AERO221": None},
            "by_scenario_entity": {"ACF-0201": {"new": "ACF-0201", "icao24_placeholder": "ICAO-SYN-AE0201", "note": "use the icao24 in aircraft_registry.json; callsign SYN41 kept"},
                                   "ACF-0301": {"new": "ACF-0301", "icao24_placeholder": "ICAO-SYN-A00301"}},
            "notes": ["CG-6540/CG-6541 were the old Jayhawk tails; canon names CG-6033 and CG-6041 (EVT-1701).",
                      "GUNSMOKE01/02 were mislabelled 'DoD ISR' in the map viewer; they are Texas Army National Guard UH-60s from Austin-Bergstrom (EVT-1103).",
                      "The two real TV station helicopters (KIII, KRIS) are replaced by one Harborline 6 News helicopter.",
                      "7c1234 was a hostile drone with an ICAO address; hostile drones have no address and are not in this registry.",
                      "Real operator names removed: SkyWest, LifeStar. Airframes with no successor map to null."]}}
    return reg, truth


# ======================================================================================
# 4. drone operators
# ======================================================================================
def build_drones(aircraft_reg):
    def site(sid, name, cat=None, contains=None, near=None):
        if near:
            d, l = G.nearest_landmark(near[0], near[1], cat)
        else:
            l = next(x for x in G.find(cat, contains))
        assert G.is_land(l["lat"], l["lon"]) or not G.in_box(l["lat"], l["lon"]), (sid, l["name"])
        return {"site_id": sid, "site_name": name, "latitude": R5(l["lat"]), "longitude": R5(l["lon"]), "landmark_category": l["category"],
                "position_basis": "real landmark point (99_reference/geo/landmarks.geojson: %s)" % str(l.get("source", ""))[:40].strip()}

    crp = next(a for a in aircraft_reg["airfields"] if a["airfield_id"] == "CRP")
    comm = {c["name"]: c for c in G.find("community")}

    def comm_pt(name):
        k = next(k for k in comm if name.lower() in k.lower())
        return (comm[k]["lat"], comm[k]["lon"])

    sites = [
        {"site_id": "UAS-SITE-CRP", "site_name": "Corpus Christi International Airport, general aviation ramp",
         "latitude": next(p for p in aircraft_reg["parking_positions"] if p["position_id"] == "PARK-CRP-A12")["latitude"],
         "longitude": next(p for p in aircraft_reg["parking_positions"] if p["position_id"] == "PARK-CRP-A12")["longitude"],
         "landmark_category": "airport", "position_basis": "aircraft_registry.json parking position PARK-CRP-A12"},
        site("UAS-SITE-FB", "Flour Bluff fire station", "fire_station", near=comm_pt("Flour Bluff")),
        site("UAS-SITE-NB", "Fire station nearest North Beach", "fire_station", near=(27.826, -97.389)),
        site("UAS-SITE-CAL", "Fire station nearest Calallen", "fire_station", near=comm_pt("Calallen")),
        site("UAS-SITE-PA", "Port Aransas fire station", "fire_station", near=(27.834, -97.066)),
        site("UAS-SITE-DT", "Downtown fire station", "fire_station", near=(27.795, -97.398)),
        site("UAS-SITE-PTL", "Fire station nearest Portland", "fire_station", near=comm_pt("Portland")),
        site("UAS-SITE-ING", "Fire station nearest Ingleside", "fire_station", near=comm_pt("Ingleside")),
        site("UAS-SITE-RKP", "Fire station nearest Rockport", "fire_station", near=comm_pt("Rockport")),
        site("UAS-SITE-WTP", "O.N. Stevens Water Treatment Plant", "water_plant"),
        site("UAS-SITE-PD", "Police station nearest downtown", "police", near=(27.795, -97.398)),
    ]
    ops = [
        ("DRN-OP-001", "Argus Aerial Systems", "Contractor (FEMA damage survey)", "Part 107 with FEMA mission waiver", ["Nueces County", "San Patricio County", "Aransas County"],
         [("Argus Mk-7 fixed-wing survey aircraft", 8, "GRID01-GRID08")], ["UAS-SITE-CRP", "UAS-SITE-CAL", "UAS-SITE-FB"]),
        ("DRN-OP-002", "Texas Department of Transportation, Corpus Christi District", "State agency (bridge and road inspection)", "Public aircraft COA",
         ["State highways and bridges in the district"], [("Autel EVO II Pro", 2, "TXDOT-1, TXDOT-2")], ["UAS-SITE-NB", "UAS-SITE-PTL", "UAS-SITE-PA"]),
        ("DRN-OP-003", "Corpus Christi Fire Department, Technical Services", "Local government (search and rescue)", "Public aircraft COA",
         ["City of Corpus Christi"], [("DJI Mavic 3 Enterprise", 3, "CCFD-UAS-1 to 3")], ["UAS-SITE-DT", "UAS-SITE-FB", "UAS-SITE-NB"]),
        ("DRN-OP-004", "Harborline 6 News", "News media", "Part 107", ["Corpus Christi metro area outside flight restrictions"],
         [("DJI Mini 4 Pro", 1, "HL6-DRONE")], ["UAS-SITE-DT"]),
        ("DRN-OP-005", "Meridian Aerial Systems", "Contractor (search and rescue thermal imaging)", "Part 107 with emergency authorisation",
         ["Nueces County"], [("FLIR-equipped multirotor", 2, "MAS-1, MAS-2")], ["UAS-SITE-CRP", "UAS-SITE-FB"]),
        ("DRN-OP-006", "Coastal Bend Power and Water Authority, Asset Inspection", "Utility", "Part 107",
         ["CBPWA substations, lines and the water treatment plant"], [("DJI Matrice 30T", 2, "CBPWA-UAS-1, CBPWA-UAS-2")], ["UAS-SITE-WTP", "UAS-SITE-CAL"]),
        ("DRN-OP-007", "The Bayside Ledger, Visual Journalism", "News media", "Part 107", ["Corpus Christi metro area outside flight restrictions"],
         [("DJI Mini 3 Pro", 1, "BL-DRONE")], ["UAS-SITE-DT"]),
        ("DRN-OP-008", "Port of Corpus Christi Authority Police", "Local government (port security)", "Public aircraft COA",
         ["Inner Harbor, La Quinta and port property"], [("Skydio X10", 2, "PORT-UAS-1, PORT-UAS-2")], ["UAS-SITE-PD"]),
        ("DRN-OP-009", "Texas Parks and Wildlife Department", "State agency (wildlife and shoreline survey)", "Public aircraft COA",
         ["Nueces Bay, Corpus Christi Bay and Redfish Bay shorelines"], [("DJI Matrice 350 RTK", 1, "TPWD-UAS-1")], ["UAS-SITE-PTL", "UAS-SITE-ING"]),
        ("DRN-OP-010", "NOAA Office of Response and Restoration", "Federal agency (oil spill mapping)", "Public aircraft COA",
         ["Ship channel and adjacent bay waters"], [("WingtraOne Gen II", 1, "NOAA-UAS-1")], ["UAS-SITE-NB", "UAS-SITE-PTL"]),
        ("DRN-OP-011", "U.S. Coast Guard Sector Corpus Christi", "Federal agency (spill response and boom inspection)", "Public aircraft COA",
         ["Ship channel and coastal waters"], [("Skydio X2D", 2, "CG-UAS-1, CG-UAS-2")], ["UAS-SITE-NB", "UAS-SITE-PA"]),
        ("DRN-OP-012", "Texas A&M University-Corpus Christi, coastal research program", "University", "Part 107",
         ["Nueces Bay, Corpus Christi Bay and Oso Bay marshes"], [("DJI Phantom 4 Multispectral", 2, "TAMUCC-UAS-1, TAMUCC-UAS-2")], ["UAS-SITE-PTL", "UAS-SITE-FB"]),
        ("DRN-OP-013", "Nueces County Sheriff's Office", "Local government (search and rescue)", "Public aircraft COA",
         ["Nueces County outside city limits"], [("DJI Mavic 3 Thermal", 2, "NCSO-UAS-1, NCSO-UAS-2")], ["UAS-SITE-CAL", "UAS-SITE-PA"]),
        ("DRN-OP-014", "Lone Palm Claims Imaging", "Contractor (insurance damage surveys)", "Part 107",
         ["Residential areas by appointment"], [("DJI Mavic 3 Enterprise", 3, "LPCI-1 to 3")], ["UAS-SITE-FB", "UAS-SITE-PA", "UAS-SITE-RKP"]),
    ]
    out = []
    n_air = 0
    for oid, org, kind, auth, zones, fleet_, st in ops:
        frames = []
        for model, n, tags in fleet_:
            for i in range(n):
                n_air += 1
                frames.append({"airframe_id": f"{oid}-A{i + 1:02d}", "model": model, "faa_registration": "FA3" + hashlib.sha1(f"{oid}{model}{i}".encode()).hexdigest()[:7].upper(),
                               "remote_id": True})
        out.append({"operator_id": oid, "org_name": org, "org_type": kind, "authorization_type": auth, "authorized_zones": zones,
                    "airframes": frames, "callsigns": fleet_[0][2], "launch_site_ids": st})
    reg = {"metadata": {"dataset": "Small unmanned aircraft operators, Corpus Christi area", "schema_version": "2.0", "generated": GENERATED,
                        "generated_by": "scripts/build_registries_maritime_air.py",
                        "description": "Authorised operators of small unmanned aircraft, their airframes and the places they launch from. Company "
                                       "names are fictional; agencies and the university are real organisations.",
                        "joins": "operator_id joins drone_video/*.csv (operator_id); launch_site_ids joins launch_sites[].site_id.",
                        "flight_restriction": "TFR-2027-CC-0441 took effect at 00:01 local on 2027-09-12: no unmanned flights within 30 nm of Corpus Christi "
                                              "International Airport up to 3,000 ft above ground without an emergency authorisation.",
                        "unregistered_aircraft": "Unauthorised or unidentified unmanned aircraft have no record here; reports of them are in the incident and sensor data.",
                        "counts": {"operators": len(out), "airframes": n_air, "launch_sites": len(sites)}},
           "authorized_operators": out, "launch_sites": sites}
    truth = {
        "_about": "Internal. Hostile unmanned aircraft and scenario roles of the authorised operators. Never give this file to participants.",
        "hostile_uas": [
            {"ids": ["UAS-RECON-01"], "what": "Pre-storm reconnaissance drone flown from the yacht Narwhal Dream (VSL-0481) at Ingleside Marina Berth 7 (SLIP-ING-07): "
                                               "sorties 1-3 over GW-FAC-SUB-01 (D-11 04:30Z, D-9 06:47Z, D-9/8 04:15Z), sorties 4-5 over the Rendal berth TERM-01 "
                                               "(D-5 05:00Z, D-4/3 04:45Z). 400-600 ft above ground, 900 MHz burst data link, 2.4 GHz command link.",
             "detected_by": ["CBP aircraft CAMCC-04 (ACF-CBP-001) electronic support measures", "Coast Guard radar buoys R-18 and R-22 raw archives (below alert threshold)"],
             "events": ["EVT-1901", "EVT-1902", "EVT-1903", "EVT-1904", "EVT-1905", "EVT-1906"], "threads": ["T19"], "public_from_day": 15,
             "note": "Sorties 4 and 5 take place after the yacht's AIS goes dark on D-8; canon gives no launch point for them."},
            {"ids": ["UAS-SYN-01", "UAS-SYN-02", "UAS-SYN-03", "UAS-SYN-04", "UAS-SYN-05", "UAS-SYN-06"],
             "what": "Night overflights of NAS Corpus Christi and the Army depot on six nights between D+1 and D+10 while perimeter sensors are down; operated by STATE-X special forces.",
             "events": ["EVT-0318"], "threads": ["T7"], "public": "residents' videos D+2; NAS statement D+6; FBI D+9; no sightings after D+11"}],
        "rules": ["Hostile drones have no operator record, no FAA registration, no Remote ID and no ICAO address; they never appear in ADS-B or in drone_video.",
                  "No drone activity of any kind after D+11. The old D+30 port loiter (UNIDENTIFIED-D30, UNKNOWN-001) is removed."],
        "truth": {"DRN-OP-001": {"role": "Argus Mk-7 swarm GRID01-GRID08: Phase 1 survey from D+3, Phase 2 utility yards D+8 (images the open breakers at SUB-02 and SUB-03), complete D+45.",
                                 "events": ["EVT-1104", "EVT-1105"], "threads": ["T11"]},
                  "DRN-OP-005": {"role": "Two FLIR multirotors pre-staged at Corpus Christi International on D-1; SAR thermal imaging D+1 to D+5.", "events": ["EVT-1701", "EVT-1703", "EVT-1706"], "threads": ["T17"]}},
        "id_migration": {"by_old_operator_id": {
            "DRN-OP-001": {"new": "DRN-OP-001", "note": "was 'FEMA Region VI UAS Team'; canon operator is the FEMA contractor Argus Aerial Systems (PUB-111)"},
            "DRN-OP-002": {"new": "DRN-OP-002"}, "DRN-OP-003": {"new": "DRN-OP-003"},
            "DRN-OP-004": {"new": None, "note": "registry listed Texas National Guard small drones; drone_video files used DRN-OP-004 for the real station KIII, now Harborline 6 News (new DRN-OP-004)"},
            "DRN-OP-005": {"new": "DRN-OP-011", "note": "Coast Guard UAS support"}, "DRN-OP-006": {"new": "DRN-OP-012", "note": "university program"},
            "DRN-OP-007": {"new": "DRN-OP-007"}, "DRN-OP-008": {"new": None, "note": "real outlet name (Texas Tribune) removed"},
            "DRN-OP-009": {"new": "DRN-OP-009"}, "DRN-OP-010": {"new": "DRN-OP-010"},
            "DRN-OP-UNK": {"new": None, "note": "hostile; see hostile_uas"}, "UNKNOWN-001": {"new": None, "note": "D+30 loiter removed from canon"}},
            "by_old_flight_prefix": {"FLT-KIII-": "DRN-OP-004 (Harborline 6 News)", "FLT-FEMA-": "DRN-OP-001", "FLT-CCFD-": "DRN-OP-003", "FLT-TXDOT-": "DRN-OP-002", "FLT-UNKNOWN-": None}}}
    return reg, truth


# ======================================================================================
def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    print(f"  wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} KB)")


def snapshot_old():
    """Keep the pre-rebuild registries once, and collect every old identifier for the migration map."""
    import csv
    import glob
    import re
    import shutil
    bak = os.path.join(ROOT, "_versions", "pre_registry_20261109")
    os.makedirs(bak, exist_ok=True)
    for n in ("vessels.json", "terminal_registry.json", "aircraft_registry.json", "drone_operators.json"):
        if not os.path.exists(os.path.join(bak, n)):
            shutil.copy2(os.path.join(OUT, n), os.path.join(bak, n))
    cache = os.path.join(INT, "_old_identifiers.json")
    if os.path.exists(cache):
        return
    names, ids = [], []
    for v in json.load(open(os.path.join(bak, "vessels.json"), encoding="utf-8"))["vessels"]:
        names.append((v["vessel_name"], v["mmsi"]))
        ids.append((v["vessel_id"], v["vessel_name"]))
    fp = os.path.join(ROOT, "05_other_sources", "ais", "ais_positions.csv")
    if os.path.exists(fp):
        seen = set()
        for r in csv.DictReader(open(fp, encoding="utf-8")):
            if r["MMSI"] not in seen:
                seen.add(r["MMSI"])
                names.append((r["VesselName"], r["MMSI"]))
    fp = os.path.join(ROOT, "05_other_sources", "supply", "vessel_arrivals.csv")
    if os.path.exists(fp):
        for r in csv.DictReader(open(fp, encoding="utf-8")):
            names.append((r["vessel_name"], r["mmsi"]))
    fp = os.path.join(ROOT, "09_shared_state_timeline", "viewer", "map_view.html")
    if os.path.exists(fp):
        m = re.search(r"var VMETA=(\{.*?\});", open(fp, encoding="utf-8").read(), re.S)
        if m:
            for k, v in json.loads(m.group(1)).items():
                names.append((v.get("name"), k))
    names.append(("Sealift ro-ro ship (synthetic name)", None))
    names.append(("Barge 44", None))
    names.append(("Tug Corrin Bay", None))
    uniq = []
    for n in names:
        if n not in uniq:
            uniq.append(n)
    os.makedirs(INT, exist_ok=True)
    json.dump({"names_mmsi": uniq, "old_vessel_ids": ids}, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    snapshot_old()
    print("terminals, berths, slips, anchorage ...")
    treg, ttruth = build_terminals()
    print("vessels ...")
    vreg = build_vessels(treg)
    vtruth = vessels_truth(vreg)
    print("aircraft ...")
    areg, atruth = build_aircraft()
    print("drone operators ...")
    dreg, dtruth = build_drones(areg)
    dump(os.path.join(OUT, "terminal_registry.json"), treg)
    dump(os.path.join(OUT, "vessels.json"), vreg)
    dump(os.path.join(OUT, "aircraft_registry.json"), areg)
    dump(os.path.join(OUT, "drone_operators.json"), dreg)
    dump(os.path.join(INT, "terminal_registry_truth.json"), ttruth)
    dump(os.path.join(INT, "vessels_truth.json"), vtruth)
    dump(os.path.join(INT, "aircraft_registry_truth.json"), atruth)
    dump(os.path.join(INT, "drone_operators_truth.json"), dtruth)
    print("counts:", treg["metadata"]["counts"], vreg["metadata"]["counts"], areg["metadata"]["counts"], dreg["metadata"]["counts"])


if __name__ == "__main__":
    main()
