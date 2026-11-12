"""Satellite scene catalogue (05_other_sources/satellite/*.json), STAC 1.0.0 items.

    python3 scripts/streams/gen_satellite.py

Run after the AIS stream is generated: vessel counts in the scene summaries are taken from the AIS
files on disk (what a detection algorithm would find and an analyst would correlate), except where
the canon timeline itself states what a scene shows. Imagery is not produced; each item is the
metadata and detection summary of one acquisition. See scripts/streams/README.md.
"""
import csv
import glob
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *            # noqa: F401,F403

SAR_BOX = [-97.95, 27.35, -96.55, 28.35]
EO_BOX = [-97.75, 27.50, -96.85, 28.15]
INFRA = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"] if a.get("latitude") is not None}
TERM = reg("terminal_registry")
BERTH = next(b for b in TERM["berths"] if b["berth_id"] == "TERM-01-B07")
INNER = ("CESWG_CC_08", "CESWG_CC_09", "CESWG_CC_10", "CESWG_CC_11", "CESWG_CC_12", "CESWG_CC_13", "CESWG_CC_14", "CESWG_CC_15")


def sun(t, lat=27.8, lon=-97.4):
    """Solar elevation and azimuth (degrees) at an epoch; simple almanac formula."""
    d = (t - 946728000) / 86400.0                      # days since 2000-01-01 12:00 UTC
    g = math.radians((357.529 + 0.98560028 * d) % 360)
    q = (280.459 + 0.98564736 * d) % 360
    L = math.radians((q + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)) % 360)
    e = math.radians(23.439 - 0.00000036 * d)
    ra = math.atan2(math.cos(e) * math.sin(L), math.cos(L))
    dec = math.asin(math.sin(e) * math.sin(L))
    gmst = (18.697374558 + 24.06570982441908 * d) % 24
    ha = math.radians((gmst * 15 + lon) % 360) - ra
    la = math.radians(lat)
    el = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha), math.tan(dec) * math.cos(la) - math.sin(la) * math.cos(ha))
    return round(math.degrees(el), 1), round((math.degrees(az) + 360) % 360, 1)


# ---------------------------------------------------------------- AIS picture at a scene time
class Ais:
    def __init__(self):
        self.ok = False
        files = sorted(glob.glob(os.path.join(ROOT, "05_other_sources", "ais", "*.csv")))
        T, M, LA, LO, SOG, LEN = [], [], [], [], [], []
        mm = {}
        for fp in files:
            try:
                with open(fp, encoding="utf-8", errors="replace") as fh:
                    rd = csv.DictReader(fh)
                    if not rd.fieldnames or "MMSI" not in rd.fieldnames or "BaseDateTime" not in rd.fieldnames:
                        continue
                    for r in rd:
                        try:
                            T.append(ts(r["BaseDateTime"])); M.append(mm.setdefault(r["MMSI"], len(mm)))
                            LA.append(float(r["LAT"])); LO.append(float(r["LON"])); SOG.append(float(r.get("SOG") or 0)); LEN.append(float(r.get("Length") or 0))
                        except (ValueError, KeyError):
                            continue
            except OSError:
                continue
        if T:
            self.T, self.M, self.LA, self.LO, self.SOG, self.LEN = (np.array(x) for x in (T, M, LA, LO, SOG, LEN))
            self.ok = True
            self.t0, self.t1 = int(self.T.min()), int(self.T.max())

    def picture(self, t, G):
        """Hull counts a wide-area scene would show: at the offshore anchorage, alongside in the
        Inner Harbor, and under way in the ship channel (vessels of 40 m or more)."""
        if not self.ok or t < self.t0 - 1800 or t > self.t1 + 1800:
            return None
        m = np.abs(self.T - t) <= 3600
        if not m.any():
            return {"offshore_anchorage": 0, "inner_harbor_alongside": 0, "ship_channel_under_way": 0}
        idx = np.where(m)[0]
        best = {}
        for i in idx:
            k = int(self.M[i])
            if k not in best or abs(self.T[i] - t) < abs(self.T[best[k]] - t):
                best[k] = i
        anc = inner = move = 0
        for i in best.values():
            if self.LEN[i] < 40:
                continue
            la, lo = float(self.LA[i]), float(self.LO[i])
            if G.anchorages.contains(la, lo):
                anc += 1
            else:
                rid = G.channel_at(la, lo, 150)
                if rid and rid.startswith(INNER) and self.SOG[i] < 0.5:
                    inner += 1
                elif rid and self.SOG[i] >= 2.0:
                    move += 1
        return {"offshore_anchorage": anc, "inner_harbor_alongside": inner, "ship_channel_under_way": move}


def item(sid, t, platform, instrument, gsd, bbox, title, desc, cloud=None, extra=None, sar=False, off_nadir=None, links=None):
    w, s, e, n = bbox
    el, az = sun(t, (s + n) / 2, (w + e) / 2)
    props = {"datetime": iso(t), "title": title, "description": desc, "platform": platform, "instruments": [instrument],
             "constellation": platform.rsplit("-", 1)[0] if "-" in platform else platform, "gsd": gsd,
             "view:off_nadir": off_nadir if off_nadir is not None else round(3 + (t % 1700) / 100.0, 1),
             "view:sun_azimuth": az, "view:sun_elevation": el, "proj:epsg": 32614}
    if sar:
        props["sar:instrument_mode"] = "stripmap" if gsd <= 5 else "wide swath"
        props["sar:frequency_band"] = "X"
        props["sar:polarizations"] = ["VV", "VH"]
    else:
        props["eo:cloud_cover"] = cloud
    if extra:
        props.update(extra)
    ext = ["https://stac-extensions.github.io/view/v1.0.0/schema.json", "https://stac-extensions.github.io/projection/v1.1.0/schema.json"]
    ext.append("https://stac-extensions.github.io/sar/v1.0.0/schema.json" if sar else "https://stac-extensions.github.io/eo/v1.0.0/schema.json")
    return {"type": "Feature", "stac_version": "1.0.0", "stac_extensions": ext, "id": sid, "collection": "coastal-bend-scenes",
            "geometry": {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}, "bbox": [w, s, e, n],
            "links": [{"rel": "collection", "href": "catalog.json", "type": "application/json"}, {"rel": "self", "href": f"{sid}.json", "type": "application/geo+json"}],
            "assets": {"data": {"href": f"s3://coastal-bend-scenes/{sid}/{'sigma0_vv.tif' if sar else 'visual.tif'}", "type": "image/tiff; application=geotiff", "roles": ["data"]},
                       "thumbnail": {"href": f"s3://coastal-bend-scenes/{sid}/thumb.jpg", "type": "image/jpeg", "roles": ["thumbnail"]}},
            "properties": props}


def box_around(lat, lon, km=1.2):
    dy = km / 110.95
    dx = km / (111.32 * math.cos(math.radians(lat)))
    return [round(lon - dx, 4), round(lat - dy, 4), round(lon + dx, 4), round(lat + dy, 4)]


def main():
    G = geo_handle(build_roads=True)
    ais = Ais()
    r = rng("satellite")
    items = []

    def cloud_for(t):
        d = (t - LANDFALL) / 86400.0
        if -1.6 < d < -0.6:
            return 88
        if -0.6 <= d < 0.9:
            return 100
        if 0.9 <= d < 1.6:
            return 72
        if 1.6 <= d < 2.6:
            return 28
        if -2.6 < d <= -1.6:
            return 41
        rr = rng("satellite-cloud", int(t // 86400))
        return int(min(95, max(0, rr.gamma(1.6, 14))))

    def vessels(t):
        p = ais.picture(t, G)
        return p

    SMALL = ["in Corpus Christi Bay off Ingleside", "near the jetties at the harbour entrance", "about 5 nautical miles offshore of Mustang Island",
             "in the Intracoastal Waterway near Aransas Pass", "about 3 nautical miles off the entrance channel", "in Redfish Bay", "off Port Aransas",
             "in Nueces Bay", "about 8 nautical miles offshore, east of the anchorage"]

    def small_hulls(tt, p, rate=0.34):
        """Boats too small to have to carry AIS show up on radar scenes all the time: returns (vessels dict, sentence)."""
        rs = rng("satellite-small", int(tt))
        d = day_of(tt)
        if rs.random() >= (rate if not -1 <= d <= 6 else 0.08):
            return p, ""
        n = 1 + int(rs.random() < 0.3)
        where = [str(x) for x in rs.choice(SMALL, size=n, replace=False)]
        p = dict(p or {})
        p["uncorrelated"] = [{"description": f"small hull {w}", "length_m": int(rs.integers(8, 32)), "ais_match": False} for w in where]
        return p, (f" {'One small hull' if n == 1 else 'Two small hulls'} with no AIS correlation ({'; '.join(where)}); below the size that must carry AIS.")

    def summary(p):
        if p is None:
            return ""
        return (f" Vessel detections (hulls of 40 m or more): {p['offshore_anchorage']} at the offshore anchorage, "
                f"{p['inner_harbor_alongside']} alongside in the Inner Harbor, {p['ship_channel_under_way']} under way in the ship channel.")

    # ---- canon scenes (what the timeline says these acquisitions show)
    canon_t = set()

    def add(it, canon=False):
        items.append(it)
        if canon:
            canon_t.add(it["properties"]["datetime"][:13])

    # D-2 radar pass: the queue at the anchorage (EVT-0207) and four reference frames (EVT-0208)
    t = ts("2027-09-12T12:14Z")
    frames = [("NUECES", [-97.75, 27.55, -96.60, 27.95], "Nueces County, the port and the offshore anchorage"), ("SANPATRICIO", [-97.80, 27.82, -97.05, 28.20], "San Patricio County"),
              ("ARANSAS", [-97.25, 27.82, -96.70, 28.32], "Aransas County"), ("KLEBERG", [-98.00, 27.20, -97.20, 27.62], "Kleberg County")]
    for i, (nm, bb, what) in enumerate(frames):
        d = {"offshore_anchorage": 14} if nm == "NUECES" else None
        desc = f"Pre-storm radar reference scene, {what}. Calm-water reference for later flood and change mapping."
        ex = {}
        if nm == "NUECES":
            desc += " A queue of ships is holding at the offshore anchorage east of Port Aransas: 14 hulls detected."
            ex = {"detections": {"vessels": {"offshore_anchorage": 14}}}
        add(item(f"HALYARD-SAR-20270912T1214{14 + i * 9:02d}Z-{nm}", t + i * 9, "Halyard-SAR-2", "X-band SAR", 10, bb, f"Pre-storm radar reference, {what}", desc, sar=True, extra=ex), True)
    # D-2 very-high-resolution baseline of utility yards and the port (EVT-1101)
    vhr = [("GW-FAC-SUB-01", "14:09"), ("GW-FAC-SUB-02", "14:17"), ("GW-FAC-SUB-03", "14:31"), ("GW-FAC-SUB-04", "14:36"), ("GW-FAC-SUB-05", "14:40"), ("GW-FAC-UTL-01", "14:12")]
    for aid, hh in vhr:
        a = INFRA[aid]
        tt = ts(f"2027-09-12T{hh}Z")
        obs = []
        desc = f"Pre-storm baseline image of {a['name']} for the regional pre-event package (archive entry NAS-BL-20270912-UTL). Yard dry, no visible damage."
        if aid == "GW-FAC-SUB-02":
            obs = [{"asset_id": aid, "feature": "main feeder breakers B2-A, B2-B, B2-C", "state": "closed"}]
            desc += " All three main feeder breakers are in the closed position. Look angle 32 degrees from north."
        elif aid == "GW-FAC-SUB-03":
            obs = [{"asset_id": aid, "feature": "main feeder breakers B3-A, B3-B, B3-C", "state": "closed"}]
            desc += " All three main feeder breakers are in the closed position."
        elif aid.startswith("GW-FAC-SUB"):
            n_ = aid[-1]
            obs = [{"asset_id": aid, "feature": f"main feeder breakers B{n_}-A, B{n_}-B, B{n_}-C", "state": "closed"}]
            desc += " Breaker contacts in the normal closed position."
        add(item(f"VANTAGE-VHR-20270912T{hh.replace(':', '')}00Z-{aid}", tt, "Vantage-VHR-3", "panchromatic and multispectral imager", 0.15, box_around(a["latitude"], a["longitude"], 0.9),
                 f"Pre-storm baseline, {a['name']}", desc, cloud=int(r.uniform(18, 40)), off_nadir=32.0 if aid == "GW-FAC-SUB-02" else round(float(r.uniform(12, 30)), 1),
                 extra={"observations": obs, "processing:level": "orthorectified, HD-resampled to 15 cm", "archive_entry": "NAS-BL-20270912-UTL"}), True)
    tt = ts("2027-09-12T14:44Z")
    add(item("VANTAGE-VHR-20270912T144400Z-PORT-DOCKS", tt, "Vantage-VHR-3", "panchromatic and multispectral imager", 0.15, [-97.455, 27.806, -97.392, 27.828],
             "Pre-storm baseline, Port of Corpus Christi Inner Harbor docks", "Pre-storm baseline image of the Inner Harbor docks for the regional pre-event package (archive entry NAS-BL-20270912-UTL). "
             "Two tankers alongside at the crude oil berth on the north bank of the Main Turning Basin.", cloud=31, off_nadir=24.5,
             extra={"processing:level": "orthorectified, HD-resampled to 15 cm", "archive_entry": "NAS-BL-20270912-UTL", "detections": {"vessels": {"main_turning_basin_crude_berth": 2}}}), True)
    # landfall night and day
    add(item("HALYARD-SAR-20270914T002214Z-COAST", ts("2027-09-14T00:22Z"), "Halyard-SAR-1", "X-band SAR", 10, SAR_BOX, "Radar pass ahead of landfall",
             "Outer rain bands over the coast; sea surface very rough, which limits small-target detection. The offshore anchorage is empty.", sar=True,
             extra={"detections": {"vessels": {"offshore_anchorage": 0}}}), True)
    add(item("NOAA42-SAR-20270914T083000Z-CCBAY", ts("2027-09-14T08:30Z"), "NOAA42 airborne SAR", "side-looking airborne radar (WP-3D)", 5, [-97.62, 27.60, -97.10, 27.95],
             "Airborne radar pass over Corpus Christi Bay and the ship channel after landfall",
             "Airborne radar pass NOAA42-20270914-0830Z, about 2,400 square km centred on Corpus Christi Bay at 5 m resolution, two and a half hours after landfall. "
             "Two large hulls alongside at the crude oil berth on the north bank of the Main Turning Basin in the Inner Harbor; no vessel under way anywhere in the ship channel. "
             "Storm-surge inundation of 2.1 to 3.4 m across the coastal industrial zone. Low-backscatter (oil-on-water) signature in the Inner Harbor around the berth, trailing east toward the bay.",
             sar=True, extra={"detections": {"vessels": {"main_turning_basin_crude_berth": 2, "ship_channel_under_way": 0, "offshore_anchorage": 0},
                                             "inundation_depth_m": [2.1, 3.4], "oil_on_water": {"present": True, "where": "Inner Harbor around the Main Turning Basin crude oil berth, trailing east"}},
                              "sar:frequency_band": "C"}), True)
    add(item("HALYARD-SAR-20270914T121630Z-COAST", ts("2027-09-14T12:16Z"), "Halyard-SAR-2", "X-band SAR", 10, SAR_BOX, "Radar pass on landfall day, bays and coast",
             "Radar pass over the bays six hours after landfall. Widespread standing water on low-lying coastal land (extent mapped from the next pass). "
             "Low-backscatter slick in the Inner Harbor and at the harbour entrance. No vessels at the offshore anchorage; two large hulls at the crude oil berth on the north bank of the Main Turning Basin.", sar=True,
             extra={"detections": {"vessels": {"main_turning_basin_crude_berth": 2, "offshore_anchorage": 0}, "oil_on_water": {"present": True, "where": "Inner Harbor and harbour entrance"}}}), True)
    add(item("MERIDIAN-EO-20270914T164800Z-COAST", ts("2027-09-14T16:48Z"), "Meridian-EO-2", "multispectral imager", 3, EO_BOX, "Optical pass on landfall day",
             "Scene fully obscured by cloud.", cloud=100), True)
    add(item("HALYARD-SAR-20270915T121400Z-FLOOD", ts("2027-09-15T12:14Z"), "Halyard-SAR-1", "X-band SAR", 10, SAR_BOX, "Radar flood-extent scene",
             "Flood extent mapped against the pre-storm reference scenes: about 112 square km inundated across Nueces, San Patricio and Aransas counties. "
             "Slick extends from the Inner Harbor into the western bay.", sar=True,
             extra={"detections": {"flood_extent_km2": 112, "oil_on_water": {"present": True, "where": "Inner Harbor into western Corpus Christi Bay"}}}), True)
    add(item("MERIDIAN-EO-20270915T164500Z-COAST", ts("2027-09-15T16:45Z"), "Meridian-EO-1", "multispectral imager", 3, EO_BOX, "First optical pass after the storm",
             "Mostly cloud-covered. Gaps over Mustang Island and the southern bay show overwash and standing water.", cloud=72), True)
    add(item("HALYARD-SAR-20270916T002000Z-BAYS", ts("2027-09-16T00:20Z"), "Halyard-SAR-2", "X-band SAR", 10, SAR_BOX, "Radar pass over the bays",
             "The slick has been carried out of the ship channel into Nueces Bay and Corpus Christi Bay.", sar=True,
             extra={"detections": {"oil_on_water": {"present": True, "where": "Nueces Bay and western Corpus Christi Bay"}}}), True)
    add(item("MERIDIAN-EO-20270916T164800Z-BAYS", ts("2027-09-16T16:48Z"), "Meridian-EO-2", "multispectral imager", 3, EO_BOX, "Optical scene of the bays",
             "Sheen across Nueces Bay and the western half of Corpus Christi Bay, about 85 square km of bay water, marsh and shoreline, with oil on the North Beach shoreline.",
             cloud=28, extra={"detections": {"oil_on_water": {"present": True, "area_km2": 85, "where": "Nueces Bay and the western half of Corpus Christi Bay; North Beach shoreline oiled"}}}), True)
    # D+31 night radar passes (EVT-0411, EVT-0403)
    add(item("CORVUS-SAR-20271015T042000Z-APPROACH", ts("2027-10-15T04:20Z"), "Corvus-SAR-4", "X-band SAR", 3, [-97.20, 27.62, -96.72, 27.98], "Night radar pass, Aransas Pass approaches",
             "Tasked night acquisition of the approaches (harbour reopening watch). One hull about 180 m long lies about 2 nautical miles off the entrance channel; "
             "no AIS message matches a vessel of that size. The only AIS transmission at that position reports a 24 m fishing vessel.", sar=True,
             extra={"tasking": "port security, harbour reopening watch",
                    "detections": {"vessels": {"uncorrelated": [{"description": "hull about 180 m long, about 2 nautical miles off the entrance channel", "length_m": 180, "ais_match": False}]}}}), True)
    add(item("CORVUS-SAR-20271015T093000Z-ANCHORAGE", ts("2027-10-15T09:30Z"), "Corvus-SAR-2", "X-band SAR", 3, [-97.20, 27.62, -96.72, 27.98], "Night radar pass, offshore anchorage",
             "Tasked night acquisition of the anchorage (harbour reopening watch). Two hulls lying side by side at the anchorage; one has no AIS match.", sar=True,
             extra={"tasking": "port security, harbour reopening watch",
                    "detections": {"vessels": {"uncorrelated": [{"description": "hull alongside another vessel at the offshore anchorage", "ais_match": False}]}}}), True)
    # archive receipt (EVT-1108)
    rec = item("ARCHIVE-RECEIPT-NGA-2027-10-29-FEMA-CC", ts("2027-10-29T18:00Z"), "aerial survey archive", "archive transfer record", 0.03, EO_BOX,
               "Archive receipt NGA-2027-10-29-FEMA-CC",
               "Receipt for the full-resolution (3 cm per pixel) aerial survey archive of the Corpus Christi area, 12 September to 29 October 2027, transferred by FEMA Region 6 for long-term storage; "
               "6.2 million georeferenced tiles. Public release FEMA-OD-2027-CC-AERIAL carries the Phase 1 and Phase 2 optical imagery at 30 cm per pixel. "
               "Chain-of-custody note: includes thermal tile set FEMA-TIR-0925-UTL and the accompanying analysis report (breaker finding at two substations, flagged for engineering follow-up).",
               cloud=0, extra={"archive": {"receipt_id": "NGA-2027-10-29-FEMA-CC", "tiles": 6200000, "native_gsd_m": 0.03, "public_gsd_m": 0.30, "public_release": "FEMA-OD-2027-CC-AERIAL",
                                           "referenced_reports": ["FEMA-TIR-0925-UTL"]}})
    del rec["properties"]["view:sun_azimuth"], rec["properties"]["view:sun_elevation"], rec["properties"]["view:off_nadir"]
    add(rec, True)

    # ---- routine acquisitions across the span
    t = SPAN_START + 12 * 3600 + 14 * 60                       # Halyard, every 4 days, alternating dawn and dusk passes
    k = 0
    while t < SPAN_END:
        tt = t if k % 2 == 0 else t + 12 * 3600 + 6 * 60
        if iso(tt)[:13] not in canon_t and not (ts("2027-09-12T00:00Z") <= tt <= ts("2027-09-16T12:00Z")):
            p = vessels(tt)
            d = day_of(tt)
            desc = "Routine wide-swath radar acquisition." + summary(p)
            p, more = small_hulls(tt, p, 0.2)
            desc += more
            ex = {"detections": {"vessels": p}} if p else {}
            if 2 < d <= 20:
                desc += " Oil sheen still present in parts of Nueces Bay and along the western bay shore." if d < 20 else " The main slick is no longer visible as a continuous feature."
            add(item(f"HALYARD-SAR-{iso(tt)[:19].replace('-', '').replace(':', '')}Z-COAST", tt, f"Halyard-SAR-{1 + k % 2}", "X-band SAR", 10, SAR_BOX, "Routine radar acquisition", desc, sar=True, extra=ex))
        t += 4 * 86400
        k += 1
    t = SPAN_START + 16 * 3600 + 44 * 60                       # Meridian optical, every 3 days
    k = 0
    while t < SPAN_END:
        tt = t + int(rng("satellite-eo", k).uniform(-240, 420))
        if iso(tt)[:10] not in ("2027-09-14", "2027-09-15", "2027-09-16"):
            c = cloud_for(tt)
            d = day_of(tt)
            p = vessels(tt) if c < 60 else None
            desc = "Routine multispectral acquisition." + (summary(p) if p else (" Vessel detection not attempted (cloud)." if c >= 60 else ""))
            if 2 < d <= 20 and c < 70:
                desc += " Sheen visible in Nueces Bay and along the western shore of Corpus Christi Bay; boom lines visible at the harbour entrance."
            if 3 <= d <= 30 and c < 70:
                desc += " Blue roof tarps and debris piles visible across the coastal neighbourhoods."
            add(item(f"MERIDIAN-EO-{iso(tt)[:19].replace('-', '').replace(':', '')}Z-COAST", tt, f"Meridian-EO-{1 + k % 2}", "multispectral imager", 3, EO_BOX, "Routine optical acquisition", desc,
                     cloud=c, extra={"detections": {"vessels": p}} if p else None))
        t += 3 * 86400
        k += 1
    t = SPAN_START + 3 * 86400 + 4 * 3600 + 18 * 60            # Corvus night radar, every 6 days, two satellites
    k = 0
    while t < SPAN_END:
        tt = t if k % 2 == 0 else t + 5 * 3600 + 11 * 60
        if iso(tt)[:10] != "2027-10-15" and not (ts("2027-09-13T00:00Z") <= tt <= ts("2027-09-15T12:00Z")):
            p = vessels(tt)
            desc = "Routine night acquisition of the approaches and anchorage." + summary(p)
            p, more = small_hulls(tt, p)
            desc += more
            add(item(f"CORVUS-SAR-{iso(tt)[:19].replace('-', '').replace(':', '')}Z-APPROACH", tt, f"Corvus-SAR-{2 + 2 * (k % 2)}", "X-band SAR", 3, [-97.20, 27.62, -96.72, 27.98],
                     "Night radar pass, approaches and anchorage", desc, sar=True, extra={"detections": {"vessels": p}} if p else None))
        t += 6 * 86400
        k += 1
    # tasked night passes outside the six-day cycle: spill response, the harbour reopening week, the days after the jetty explosion
    tasked = [("2027-09-19T04:31Z", 4, "spill response"), ("2027-09-22T09:12Z", 2, "spill response"), ("2027-09-27T04:07Z", 4, "spill response"),
              ("2027-10-13T04:26Z", 4, "port security, harbour reopening watch"), ("2027-10-14T09:41Z", 2, "port security, harbour reopening watch"),
              ("2027-10-16T04:13Z", 4, "port security, harbour reopening watch"), ("2027-10-18T09:22Z", 2, "port security, harbour reopening watch"),
              ("2027-10-28T09:36Z", 2, "port security"), ("2027-10-29T04:24Z", 4, "port security"), ("2027-10-31T09:18Z", 2, "port security"),
              ("2027-11-03T04:35Z", 4, "port security"), ("2027-11-10T09:27Z", 2, "port security, harbour reopening watch")]
    for when, sat, why in tasked:
        tt = ts(when)
        p = vessels(tt)
        desc = f"Tasked night acquisition of the approaches and anchorage ({why.split(', ')[-1]})." + summary(p)
        p, more = small_hulls(tt, p, 0.45)
        desc += more
        ex = {"tasking": why}
        if p:
            ex["detections"] = {"vessels": p}
        add(item(f"CORVUS-SAR-{iso(tt)[:19].replace('-', '').replace(':', '')}Z-APPROACH", tt, f"Corvus-SAR-{sat}", "X-band SAR", 3, [-97.20, 27.62, -96.72, 27.98],
                 "Night radar pass, approaches and anchorage", desc, sar=True, extra=ex))
    # ---- debris staging sites (EVT-0505): very-high-resolution scenes every two weeks from late September
    sites = {"DEBRIS-CAL": (27.8440, -97.6050), "DEBRIS-FB": (27.6640, -97.3040), "DEBRIS-PTL": (27.8890, -97.3120), "DEBRIS-RKP": (28.0380, -97.0680), "DEBRIS-WEST": (27.7760, -97.4820)}
    for dstr in ("2027-09-30", "2027-10-14", "2027-10-28", "2027-11-11", "2027-11-22"):
        for j, (nm, (la, lo)) in enumerate(sites.items()):
            d_, sla, slo, rn, cls = G.roads.nearest(la, lo)
            tt = ts(f"{dstr}T16:{31 + j * 3:02d}Z")
            add(item(f"VANTAGE-VHR-{dstr.replace('-', '')}T16{31 + j * 3:02d}00Z-{nm}", tt, "Vantage-VHR-2", "panchromatic and multispectral imager", 0.3, box_around(sla, slo, 0.8),
                     f"Debris staging site {nm.split('-')[1]}", f"Debris staging site beside {rn or 'the access road'}. Pile outlines and haul-truck queue are resolved; suitable for pile-footprint and volume measurement.",
                     cloud=int(rng("satellite-debris", dstr, nm).uniform(0, 25)), extra={"tasking": "county debris monitoring"}))

    tt = ts("2028-01-11T16:46Z")                                # four months on
    c = cloud_for(tt)
    p = vessels(tt) if c < 60 else None
    add(item("MERIDIAN-EO-20280111T164600Z-COAST", tt, "Meridian-EO-1", "multispectral imager", 3, EO_BOX, "Routine optical acquisition",
             "Routine multispectral acquisition." + (summary(p) if p else ""), cloud=c, extra={"detections": {"vessels": p}} if p else None))
    items.sort(key=lambda it: it["properties"]["datetime"])
    out_dir = os.path.join(ROOT, "05_other_sources", "satellite")
    legacy = [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(out_dir, "RAFAEL-*.json"))]      # superseded hand-built scenes
    if legacy:
        retire(legacy + ["05_other_sources/satellite/catalog.json"])
    for p in glob.glob(os.path.join(out_dir, "*.json")):                                                # this generator's own earlier output
        os.remove(p)
    for it in items:
        with open(out_path(f"05_other_sources/satellite/{it['id']}.json"), "w", encoding="utf-8") as fh:
            json.dump(it, fh, indent=1)
    cat = {"type": "Collection", "stac_version": "1.0.0", "id": "coastal-bend-scenes", "description": "Satellite and airborne scene metadata over the Corpus Christi area, with detection summaries. Imagery is not included.",
           "license": "proprietary", "extent": {"spatial": {"bbox": [SAR_BOX]}, "temporal": {"interval": [[items[0]["properties"]["datetime"], items[-1]["properties"]["datetime"]]]}},
           "links": [{"rel": "item", "href": f"{it['id']}.json", "type": "application/geo+json"} for it in items]}
    with open(out_path("05_other_sources/satellite/catalog.json"), "w", encoding="utf-8") as fh:
        json.dump(cat, fh, indent=1)
    print(f"satellite: {len(items)} items; AIS used for vessel counts: {'yes, ' + iso(ais.t0) + ' to ' + iso(ais.t1) if ais.ok else 'no'}")


if __name__ == "__main__":
    main()
