"""Assemble and run the port simulation."""
import os
import sys
import time

_H = os.path.dirname(os.path.abspath(__file__))
if not sys.path or sys.path[0] != _H:
    sys.path.insert(0, _H)

import maritime_base as mb          # noqa: E402
import maritime_local as ml         # noqa: E402
import maritime_ships as ms         # noqa: E402
from maritime_core import T_END, T_WARM, Stay  # noqa: E402,F401
H = 3600.0


class PortSim(ms.ShipsMixin, ms.ShipLoopMixin, ml.LocalMixin, mb.PortBase):
    def run(self):
        steps = [("ocean-going traffic", self.run_ships), ("dark tanker", self.script_halcyon), ("Pelican Ridge", self.script_pelican),
                 ("yacht at Ingleside", self.script_narwhal), ("fuel barge", self.script_tow44), ("tug at the jetties", self.script_blast),
                 ("channel search", self.script_search), ("spill response", self.run_response), ("ferries", self.run_ferries),
                 ("bunker barges", self.run_bunker_barges), ("cutters", self.run_cutters), ("patrols", self.run_patrols),
                 ("survey, dredge, research", self.run_survey_dredge_research), ("supply boats and tows", self.run_osv_and_tows),
                 ("fishing and leisure", self.run_fishing_and_leisure)]
        for name, fn in steps:
            t = time.time()
            fn()
            self.save_paths()
            self.log(f"  {name}: {time.time() - t:.1f}s")
        self.finish()
        return self

    def finish(self):
        V = self.vessels
        class_a_home = ["tug", "pilot", "coast_guard", "spill_response", "survey", "research", "offshore_supply", "public_safety", "barge"]
        for v in V.values():
            if v.id.startswith("SPOOF") or v.id in ("VSL-0361",):
                continue
            if v.cls == "ferry" or v.rec.get("home_berth_id") is None and v.id not in self.home:
                continue
            if v.id in ("VSL-0342", "VSL-0343", "VSL-0344", "VSL-0077"):
                if v.id == "VSL-0077":
                    self.fill_home(v, ais_moored=True, t_stop=self.escort_plan["t_start"] - 1800)
                continue
            if v.mmsi is None:
                continue
            if v.cls in class_a_home or v.tc == "A":
                self.fill_home(v, ais_moored=True)
            else:
                self.fill_home(v, ais_moored=False)
        for v in V.values():
            v.finalize()
        self.setup_sensors()

    def setup_sensors(self):
        """Port radar buoys, fixed cameras and the vessel traffic log (positions from real geometry)."""
        import maritime_geom as mg
        from maritime_core import ts
        GM = self.GM
        ne = GM.water_point_near((27.8190, -96.9990), 300.0, 800.0)
        sw = GM.water_point_near((27.8200, -97.2600), 400.0, 1200.0)
        if self.G.channel_at(ne[0], ne[1], 60) or self.G.channel_at(sw[0], sw[1], 60):
            raise ValueError("radar buoy inside a channel")
        S = [dict(sensor_id="RADAR-BUOY-NE", sensor_type="radar buoy", name="Buoy-NE, entrance channel off the Port Aransas jetties",
                  latitude=round(ne[0], 5), longitude=round(ne[1], 5), range_nm=9.5),
             dict(sensor_id="RADAR-BUOY-SW", sensor_type="radar buoy", name="Buoy-SW, bay reach of the ship channel",
                  latitude=round(sw[0], 5), longitude=round(sw[1], 5), range_nm=7.0)]
        cams = [("CAM-01", "Rendal Terminals berths 7 and 8", ["TERM-01-B07", "TERM-01-B08"], "TERM-01-B07"),
                ("CAM-02", "Public cargo docks", ["TERM-07-B01", "TERM-07-B02", "TERM-07-B03", "TERM-07-B04"], "TERM-07-B01"),
                ("CAM-03", "Main Turning Basin, south bank", ["TERM-17-B01", "TERM-17-B02", "TERM-17-B03", "TERM-13-B02", "TERM-15-B02"], "TERM-17-B02"),
                ("CAM-04", "Harbor Bridge, channel entrance to the Inner Harbor", [], None),
                ("CAM-05", "Industrial Canal", ["TERM-13-B01", "TERM-15-B01", "TERM-12-B01"], "TERM-13-B01"),
                ("CAM-06", "Avery Point Turning Basin", ["TERM-06-B01", "TERM-06-B02"], "TERM-06-B01"),
                ("CAM-07", "Chemical Turning Basin", ["TERM-02-B01", "TERM-19-B01", "TERM-19-B02", "TERM-20-B01"], "TERM-02-B01"),
                ("CAM-08", "Tule Lake Channel", ["TERM-18-B01", "TERM-18-B02", "TERM-18-B03", "TERM-18-B04", "TERM-11-B01", "TERM-11-B02"], "TERM-18-B01"),
                ("CAM-09", "Tule Lake Turning Basin", ["TERM-04-B01", "TERM-04-B02", "TERM-14-B01", "TERM-14-B02", "TERM-05-B01"], "TERM-04-B02"),
                ("CAM-10", "Viola Turning Basin", ["TERM-05-B02", "TERM-05-B03", "TERM-16-B01"], "TERM-05-B02"),
                ("CAM-11", "La Quinta LNG berth", ["TERM-03-B01"], "TERM-03-B01"),
                ("CAM-12", "La Quinta bulk docks", ["TERM-09-B01", "TERM-10-B01"], "TERM-10-B01"),
                ("CAM-13", "Port Aransas jetties, channel entrance", [], None),
                ("CAM-14", "Harbor Island", ["TERM-23-B01", "TERM-23-B02"], "TERM-23-B01")]
        fixed = {"CAM-04": (27.81194, -97.39565), "CAM-13": (27.8347, -97.0462)}
        for cid, name, berths, ref in cams:
            base = self.bpos(ref) if ref else fixed[cid]
            p = GM.land_point_near(base, 500.0)
            if p is None:
                raise ValueError(f"no shore position for {cid}")
            S.append(dict(sensor_id=cid, sensor_type="fixed camera", name=name, latitude=round(p[0], 5), longitude=round(p[1], 5), range_nm="",
                          berths=berths))
        S.append(dict(sensor_id="VTS-CC", sensor_type="vessel traffic log", name="Port of Corpus Christi vessel traffic service", latitude="", longitude="", range_nm=""))
        self.sensors = S
        storm_off = ts("2027-09-14T02:30Z")
        self.sensor_windows = {"RADAR-BUOY-NE": [(T_WARM, ts("2027-09-14T05:10Z")), (ts("2027-09-16T19:30Z"), 4e9)],
                               "RADAR-BUOY-SW": [(T_WARM, ts("2027-09-15T11:00Z")), (ts("2027-10-02T15:00Z"), 4e9)]}
        back = {"CAM-01": "2027-09-15T14:10Z", "CAM-02": "2027-09-17T13:20Z", "CAM-03": "2027-09-17T14:05Z", "CAM-04": "2027-09-17T15:40Z",
                "CAM-11": "2027-09-17T17:10Z", "CAM-12": "2027-09-17T17:35Z", "CAM-13": "2027-09-17T18:50Z", "CAM-14": "2027-09-17T19:30Z",
                "CAM-05": "2027-10-29T14:10Z", "CAM-06": "2027-10-29T15:00Z", "CAM-07": "2027-10-29T15:45Z", "CAM-08": "2027-10-29T17:20Z",
                "CAM-09": "2027-10-29T18:30Z", "CAM-10": "2027-10-29T20:15Z"}
        for cid, when in back.items():
            self.sensor_windows[cid] = [(T_WARM, storm_off), (ts(when), 4e9)]
        self.buoy_sw_live_lost = ts("2027-09-14T03:38Z")
        self.buoy_sw_buffer_recovered = ts("2027-09-15T16:20Z")

    def dump(self, fp):
        import pickle
        gm, g, wp = self.GM, self.G, getattr(self, "_wp", None)
        self.GM = self.G = None
        try:
            with open(fp, "wb") as fh:
                pickle.dump(self, fh, protocol=4)
        finally:
            self.GM, self.G = gm, g

    @staticmethod
    def load(fp):
        import pickle
        import maritime_geom as mg
        with open(fp, "rb") as fh:
            sim = pickle.load(fh)
        sim.GM = mg.Geom()
        sim.G = sim.GM.G
        return sim


if __name__ == "__main__":
    PortSim().run()
