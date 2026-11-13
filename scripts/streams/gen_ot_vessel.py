"""Tanker cargo-control logs and the vendor remote-session log (stream vessel_ot_logs).

    python3 scripts/streams/gen_ot_vessel.py

Writes
  05_other_sources/telemetry/vessel_cargo_control_kalvora_star.csv
  05_other_sources/telemetry/vessel_cargo_control_ostrel_bay.csv
      the ships' own cargo-control event logs: console logins, commands, valve feedback, alarms,
      tank gauging, remote-gateway attach/detach, survey entries
  05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv
      the vendor's remote-maintenance gateway log for all the tankers it serves

Canon: valves on both tankers' cargo manifolds open at 04:00Z on D0 with alarms inhibited, a vendor
remote session active throughout, crews close them by 05:30Z, about 9,000 barrels lost in total; the
vendor disables its remote access on D+8. Logs say what happened, never why.
"""
import re
import numpy as np

import netmap
from common import SPAN_END, iso, reg, rng, ts, write_csv
from ot_model import DAY, T, ev_sec

START = ts("2027-07-16T05:00Z")
COLS = ["timestamp_utc", "mmsi", "vessel_name", "record_type", "station", "operator", "tag", "value", "unit", "text"]
SESS_COLS = ["session_id", "gateway", "vendor_account", "src_ip", "src_asn", "target_system", "vessel_mmsi", "vessel_name", "login_utc", "logout_utc",
             "duration_s", "access_level", "ticket_ref", "result", "bytes_out"]
GATEWAY = "rmt-gw.brightwake.example"
# network numbers come from the one address table every stream shares (netmap): the vendor's office and VPN egress
# sit beside its gateway at one provider; the third network is the one other streams also show
ASN_OFFICE = ASN_VPN = netmap.label(netmap.VENDOR_OFFICE[0])
ASN_ODD = netmap.label(netmap.story_ip(41))
REVOKED = ts("2027-09-22T15:00Z")                 # D+8: vendor disables remote access
TANKS = [f"{n}{s}" for n in range(1, 7) for s in ("P", "S")]
TANK_BBL = 61500.0                                # capacity of one cargo tank at 98 percent
TANK_DEPTH = 20.8

SHIPS = {
    "kalvora_star": {"vid": "VSL-0041", "system": "EXT-KALVORA-CCS", "loaded": 702400.0, "arrive": ts("2027-09-11T14:30Z"),
                     "load": (ts("2027-09-11T17:10Z"), ts("2027-09-12T15:40Z")), "disch": (ts("2027-08-02T05:00Z"), ts("2027-08-03T14:00Z")),
                     "disport": "Rotterdam", "lost": 5200.0, "lost_tanks": ["3P", "3S", "4P", "4S"], "valves": ["MV-P2", "MV-P3"],
                     "closed": ts("2027-09-14T05:29Z") + 40, "noticed": ts("2027-09-14T05:14Z") + 20},
    "ostrel_bay": {"vid": "VSL-0042", "system": "EXT-OSTREL-CCS", "loaded": 688100.0, "arrive": ts("2027-09-11T09:10Z"),
                   "load": (ts("2027-09-11T11:30Z"), ts("2027-09-12T12:50Z")), "disch": (ts("2027-07-24T22:00Z"), ts("2027-07-26T09:00Z")),
                   "disport": "Ulsan", "lost": 3800.0, "lost_tanks": ["2P", "2S", "5P", "5S"], "valves": ["MV-S1", "MV-S2"],
                   "closed": ts("2027-09-14T05:26Z") + 50, "noticed": ts("2027-09-14T05:11Z") + 5},
}
ODD_ACCOUNT = "bw-eng-07"
ODD_SESSIONS = {  # read-only look-arounds before the storm: (vessel key, start, seconds)
    "kalvora_star": [(ts("2027-08-26T03:12Z"), 2460), (ts("2027-09-01T02:40Z"), 3120), (ts("2027-09-07T04:05Z"), 1980), (ts("2027-09-12T23:48Z"), 2760)],
    "ostrel_bay": [(ts("2027-08-27T02:55Z"), 2220), (ts("2027-09-02T03:31Z"), 2880), (ts("2027-09-08T03:02Z"), 1740), (ts("2027-09-13T00:41Z"), 2520)],
}
EVENT_SESSION = (ts("2027-09-14T03:52Z") + 10, ts("2027-09-14T05:35Z") + 12)


def z(t):
    return iso(int(t))


def ship_log(key, spec, vessel):
    g = rng("vessel_ot", key)
    mmsi, name = vessel["mmsi"], vessel["vessel_name"]
    rows = []

    def add(t, rtype, station, operator, tag="", value="", unit="", text=""):
        rows.append([z(t), mmsi, name, rtype, station, operator, tag, value, unit, text])

    # ---------------- volume in each tank over time (barrels)
    d0, d1 = spec["disch"]
    l0, l1 = spec["load"]
    vo, vc = T["valves_open"], spec["closed"]
    rob = 180.0                                               # remaining on board per tank after discharge
    per_tank = spec["loaded"] / 12.0

    def volume(tank, t):
        k = TANKS.index(tank)
        stagger = (k % 6) * 0.03
        if t < d0:
            return per_tank * 0.997
        if t < d1:
            f = min(1.0, max(0.0, ((t - d0) / (d1 - d0) - stagger) / (1 - 0.18)))
            return per_tank * 0.997 * (1 - f) + rob * f
        if t < l0:
            return rob
        if t < l1:
            f = min(1.0, max(0.0, ((t - l0) / (l1 - l0) - stagger) / (1 - 0.18)))
            return rob + (per_tank - rob) * f
        v = per_tank
        if tank in spec["lost_tanks"]:
            share = spec["lost"] / len(spec["lost_tanks"])
            f = min(1.0, max(0.0, (t - vo - 45) / (vc - vo - 45)))
            v -= share * f
        return v

    def gauge(t, note=""):
        for tank in TANKS:
            v = volume(tank, t)
            wobble = float(g.normal(0, 2.5)) if v > 1000 else float(abs(g.normal(0, 0.6)))
            lvl = max(0.02, (v + wobble) / TANK_BBL * TANK_DEPTH * 0.98)
            add(t, "LEVEL", "TANK-GAUGING", "", f"COT-{tank}", f"{lvl:.3f}", "m", f"{v + wobble:,.0f} bbl".replace(",", ""))

    # tank gauging cadence: 5 min during cargo operations and the night of D0, hourly alongside, 6-hourly otherwise
    fast = [(d0 - 3600, d1 + 3600), (l0 - 3600, l1 + 3600), (ts("2027-09-14T03:30Z"), ts("2027-09-14T06:30Z"))]
    hourly = [(spec["arrive"], ts("2027-09-21T00:00Z"))]
    t = START
    while t < SPAN_END:
        if any(a <= t < b for a, b in fast):
            step = 300
        elif any(a <= t < b for a, b in hourly):
            step = 3600
        else:
            step = 6 * 3600
        gauge(t)
        t += step
        if step > 300:
            for a, _b in fast:
                if t - step < a < t:
                    t = a
    # ---------------- cargo operations (discharge at the previous port, loading at Corpus Christi)
    for (a, b, what, port) in ((d0, d1, "DISCHARGE", spec["disport"]), (l0, l1, "LOADING", "Corpus Christi, Rendal Terminals")):
        add(a - 2700, "LOGIN", "CCR-1", "C/O", text="console login")
        add(a - 1500, "EVENT", "CCR-1", "C/O", "CARGO-OPS", what + " START", "", f"pre-transfer checks complete; {port}")
        for i, tank in enumerate(TANKS):
            add(a - 900 + i * 40, "CMD", "CCR-1", "C/O", f"DROP-VALVE-{tank}", "OPEN", "", "")
            add(a - 880 + i * 40, "STATE", "VALVE-CTRL", "", f"DROP-VALVE-{tank}", "OPEN", "", "position feedback")
        for mv in spec["valves"]:
            add(a - 300, "CMD", "CCR-1", "C/O", mv, "OPEN", "", "manifold connected to shore arm")
            add(a - 272, "STATE", "VALVE-CTRL", "", mv, "OPEN", "", "position feedback")
        tt = a + 4 * 3600
        while tt < b:
            add(tt, "LOGIN", "CCR-1", str(g.choice(["2/O", "3/O", "C/O"])), text="watch change")
            tt += 4 * 3600
        for mv in spec["valves"]:
            add(b + 240, "CMD", "CCR-1", "C/O", mv, "CLOSE", "", "")
            add(b + 262, "STATE", "VALVE-CTRL", "", mv, "CLOSED", "", "position feedback")
        for i, tank in enumerate(TANKS):
            add(b + 600 + i * 35, "CMD", "CCR-1", "C/O", f"DROP-VALVE-{tank}", "CLOSE", "", "")
            add(b + 621 + i * 35, "STATE", "VALVE-CTRL", "", f"DROP-VALVE-{tank}", "CLOSED", "", "position feedback")
        add(b + 1500, "EVENT", "CCR-1", "C/O", "CARGO-OPS", what + " COMPLETE", "", "")
        add(b + 5400, "LOGOUT", "CCR-1", "C/O", text="console logout")
    add(l1 + 3 * 3600, "SURVEY", "CCR-1", "C/O", "CARGO-FIGURES", f"{spec['loaded']:.0f}", "bbl", "ship's figures after loading, agreed with shore and surveyor")
    add(ts("2027-09-12T20:00Z"), "EVENT", "CCR-1", "C/O", "HEAVY-WEATHER", "SECURED", "", "manifold valves closed and locked, cargo system secured for heavy weather; vessel remaining alongside")
    # ---------------- ordinary system chatter
    tt = START + int(g.integers(3600, 2 * DAY))
    while tt < SPAN_END:
        kind = int(g.integers(0, 4))
        if kind == 0:
            add(tt, "ALARM", "ALARM-PANEL", "", "IG-PRESS-LOW", "RAISED", "", "inert gas main pressure low")
            add(tt + int(g.integers(200, 1500)), "ALARM", "ALARM-PANEL", "", "IG-PRESS-LOW", "CLEARED", "", "")
        elif kind == 1:
            add(tt, "LOGIN", "CCR-1", str(g.choice(["C/O", "2/O", "PUMPMAN"])), text="console login")
            add(tt + int(g.integers(600, 5400)), "LOGOUT", "CCR-1", "", text="console logout")
        elif kind == 2:
            add(tt, "EVENT", "CCR-2", "PUMPMAN", "SELF-TEST", "PASS", "", "weekly alarm and trip test")
        else:
            add(tt, "ALARM", "ALARM-PANEL", "", f"COT-{g.choice(TANKS)}-PRESS-HIGH", "RAISED", "", "tank pressure high, vented")
            add(tt + int(g.integers(120, 900)), "ALARM", "ALARM-PANEL", "", "TANK-PRESS-HIGH", "CLEARED", "", "")
        tt += int(g.integers(DAY, 4 * DAY))
    # ---------------- remote gateway on the ship side
    return rows, add, volume


def main():
    vessels = {v["vessel_id"]: v for v in reg("vessels")["vessels"]}
    g = rng("vessel_ot", "sessions")
    gx = rng("vessel_ot", "sessions-everyday")          # everyday untidiness: call-outs without a ticket, mistyped passwords, portal-only logins
    sessions = []
    sid = [27000]

    def session(account, ip, asn, system, v, a, dur, level, ticket, result="SUCCESS", nbytes=None):
        tok = f"@{len(sessions)}@"                          # numbered in login order once every session exists
        b = a + dur
        sessions.append([tok, GATEWAY, account, ip, asn, system, v["mmsi"] if v else "", v["vessel_name"] if v else "", z(a),
                         z(b) if result == "SUCCESS" else "", int(dur) if result == "SUCCESS" else 0, level, ticket, result,
                         int(nbytes if nbytes is not None else (dur * g.uniform(900, 4200) if result == "SUCCESS" else 0))])
        return tok

    office_ip = lambda: netmap.VENDOR_OFFICE[int(g.integers(20, 60)) % len(netmap.VENDOR_OFFICE)]     # the vendor's office egress pool
    vpn_ip = lambda: netmap.VENDOR_VPN[int(g.integers(130, 180)) % len(netmap.VENDOR_VPN)]             # its staff VPN egress pool
    odd_ip = lambda: netmap.story_ip(int(g.choice([41, 44, 87, 112])))

    # the vendor's customers: the two canon tankers and a dozen others
    customers = ["VSL-0041", "VSL-0042", "VSL-0101", "VSL-0102", "VSL-0104", "VSL-0106", "VSL-0109", "VSL-0112", "VSL-0114", "VSL-0116", "VSL-0118",
                 "VSL-0121", "VSL-0171", "VSL-0174"]
    systems = {"VSL-0041": "EXT-KALVORA-CCS", "VSL-0042": "EXT-OSTREL-CCS"}

    def system_of(vid, v):
        """Name of a ship's cargo-control network on the vendor's portal: one scheme for every customer."""
        if vid in systems:
            return systems[vid]
        w = v["vessel_name"].split()[1:]
        return "EXT-" + (w[-1] if w[0] == "Gulf" else w[0]).upper() + "-CCS"
    legit_by_ship = {"VSL-0041": [], "VSL-0042": []}
    tick = 3100
    for vid in customers:
        v = vessels[vid]
        t = START + int(g.integers(1, 20)) * DAY
        while t < REVOKED - 3600:
            ld = ts(iso(t)[:10] + "T14:00Z") + int(g.integers(0, 7 * 3600))            # Houston business hours
            if ((ld // DAY) + 4) % 7 in (0, 6):
                ld += 2 * DAY
            callout = gx.random() < 0.2                    # the ship rings the duty engineer at night: from home, over the VPN
            if callout:
                ld = ts(iso(t)[:10] + "T23:10Z") + int(gx.integers(0, 12 * 3600))
            if ld < REVOKED - 5400 and not (ts("2027-09-12T12:00Z") < ld < ts("2027-09-16T12:00Z")):
                tick += int(g.integers(1, 9))
                dur = int(g.integers(1500, 5400))
                acct = f"bw-eng-{int(g.integers(1, 10)):02d}"
                level = str(g.choice(["read-only", "read-only", "maintenance"]))
                use_vpn = g.random() < 0.3 or callout
                src_ip, src_asn = (vpn_ip(), ASN_VPN) if use_vpn else (office_ip(), ASN_OFFICE)
                go = rng("vessel_ot", "travelling", vid, int(ld))
                if not callout and go.random() < 0.19:      # the engineer is at a customer's office or on the road: phone hotspot, straight to the portal
                    src_ip = netmap.mobile(("brw-travel", acct, int(ld) // (3 * DAY)))[0]
                    src_asn = netmap.label(src_ip)
                ticket = f"BW-MT-27-{tick}" if gx.random() > 0.22 else ""          # ship called the duty engineer; ticket never raised
                if gx.random() < 0.12:
                    session(acct, src_ip, src_asn, "", None, ld - int(gx.integers(40, 400)), 0, "", "", result="FAILED: bad password")
                s_id = session(acct, src_ip, src_asn, system_of(vid, v), v, ld, dur, level, ticket)
                if vid in legit_by_ship:
                    legit_by_ship[vid].append((ld, dur, acct, level, ticket or "none", s_id))
            t += int(g.integers(16, 40)) * DAY
    # engineers also sign in to the portal without attaching to a ship (schedules, documentation, password changes)
    t = START + 2 * DAY
    while t < REVOKED - DAY:
        ld = ts(iso(t)[:10] + "T13:30Z") + int(gx.integers(0, 9 * 3600))
        if ((ld // DAY) + 4) % 7 not in (0, 6):
            acct = f"bw-eng-{int(gx.integers(1, 10)):02d}"
            use_vpn = gx.random() < 0.35
            if gx.random() < 0.1:
                session(acct, vpn_ip() if use_vpn else office_ip(), ASN_VPN if use_vpn else ASN_OFFICE, "", None, ld - int(gx.integers(30, 300)), 0, "", "", result="FAILED: bad password")
            session(acct, vpn_ip() if use_vpn else office_ip(), ASN_VPN if use_vpn else ASN_OFFICE, "", None, ld, int(gx.integers(120, 2400)), "portal", "")
        t += int(gx.integers(1, 5)) * DAY
    # the odd address: first portal login (no ship), then read-only sessions with no ticket, then the night of D0
    first = ts("2027-08-13T02:37Z") + ev_sec("EVT-0107")
    session(ODD_ACCOUNT, netmap.story_ip(41), ASN_ODD, "", None, first - 190, 0, "", "", result="FAILED: bad password")
    session(ODD_ACCOUNT, netmap.story_ip(41), ASN_ODD, "", None, first, 372, "portal", "", nbytes=50873)
    session(ODD_ACCOUNT, netmap.story_ip(44), ASN_ODD, "", None, ts("2027-08-17T03:20Z") + 31, 1140, "portal", "", nbytes=912455)
    odd_by_ship = {}
    for key, spec in SHIPS.items():
        v = vessels[spec["vid"]]
        odd_by_ship[key] = []
        for a, dur in ODD_SESSIONS[key]:
            jo = rng("vessel_ot", "odd", key, a)
            a, dur = a + int(jo.integers(4, 57)), dur + int(jo.integers(-28, 29))
            s_id = session(ODD_ACCOUNT, odd_ip(), ASN_ODD, spec["system"], v, a, dur, "read-only", "")
            odd_by_ship[key].append((a, dur, s_id))
        a, b = EVENT_SESSION
        off = 0 if key == "kalvora_star" else 95
        s_id = session(ODD_ACCOUNT, netmap.story_ip(87), ASN_ODD, spec["system"], v, a + off, b - a - off + (0 if key == "kalvora_star" else 40), "maintenance", "")
        odd_by_ship[key].append((a + off, b - a - off + (0 if key == "kalvora_star" else 40), s_id))
    # after the vendor disables remote access: every attempt is refused
    session("svc-admin", netmap.VENDOR_OFFICE[0], ASN_OFFICE, "", None, REVOKED, 0, "", "BW-SEC-27-0044", result="ALL REMOTE ACCESS DISABLED BY VENDOR")
    for t_try, acct, ip, asn in ((ts("2027-09-22T23:14Z") + 8, ODD_ACCOUNT, netmap.story_ip(112), ASN_ODD), (ts("2027-09-24T02:51Z") + 40, ODD_ACCOUNT, netmap.story_ip(44), ASN_ODD),
                                 (ts("2027-09-23T15:20Z"), "bw-eng-03", office_ip(), ASN_OFFICE), (ts("2027-09-27T16:05Z"), "bw-eng-05", office_ip(), ASN_OFFICE),
                                 (ts("2027-10-11T14:40Z"), "bw-eng-02", office_ip(), ASN_OFFICE), (ts("2027-11-18T15:10Z"), "bw-eng-08", office_ip(), ASN_OFFICE)):
        session(acct, ip, asn, "", None, t_try, 0, "", "", result="DENIED: remote access disabled")
    sessions.sort(key=lambda r: r[8])
    sid_final = {}
    for r in sessions:
        sid[0] += int(g.integers(1, 7))
        sid_final[r[0]] = f"BRW-S-{sid[0]}"
        r[0] = sid_final[r[0]]
    untok = lambda x: re.sub(r"@\d+@", lambda m: sid_final[m.group(0)], x) if isinstance(x, str) and "@" in x else x
    n_s = write_csv("05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv", SESS_COLS, sessions)

    total = n_s
    for key, spec in SHIPS.items():
        v = vessels[spec["vid"]]
        rows, add, volume = ship_log(key, spec, v)
        # ship-side record of every remote session
        for a, dur, acct, level, ticket, s_id in legit_by_ship[spec["vid"]]:
            add(a + 6, "REMOTE", "RMT-GW", acct, "SESSION", "ATTACH", "", f"{s_id}; {level}; ticket {ticket}")
            add(a + dur, "REMOTE", "RMT-GW", acct, "SESSION", "DETACH", "", s_id)
        for a, dur, s_id in odd_by_ship[key][:-1]:
            add(a + 6, "REMOTE", "RMT-GW", ODD_ACCOUNT, "SESSION", "ATTACH", "", f"{s_id}; read-only; ticket none")
            add(a + dur, "REMOTE", "RMT-GW", ODD_ACCOUNT, "SESSION", "DETACH", "", s_id)
        a, dur, s_id = odd_by_ship[key][-1]
        vo = T["valves_open"] + (0 if key == "kalvora_star" else 7)
        add(a + 6, "REMOTE", "RMT-GW", ODD_ACCOUNT, "SESSION", "ATTACH", "", f"{s_id}; maintenance; ticket none")
        add(vo - 163, "ALARM", "RMT-GW", ODD_ACCOUNT, "COT-LEVEL-HH-GROUP", "INHIBIT ON", "", "high-high level alarms inhibited")
        add(vo - 141, "ALARM", "RMT-GW", ODD_ACCOUNT, "VALVE-POSITION-GROUP", "INHIBIT ON", "", "valve position discrepancy alarms inhibited")
        for i, tank in enumerate(spec["lost_tanks"]):
            add(vo - 60 + i * 9, "CMD", "RMT-GW", ODD_ACCOUNT, f"DROP-VALVE-{tank}", "OPEN", "", "")
            add(vo - 41 + i * 9, "STATE", "VALVE-CTRL", "", f"DROP-VALVE-{tank}", "OPEN", "", "position feedback")
        for i, mv in enumerate(spec["valves"]):
            add(vo + i * 11, "CMD", "RMT-GW", ODD_ACCOUNT, mv, "OPEN", "", "")
            add(vo + 24 + i * 11, "STATE", "VALVE-CTRL", "", mv, "OPEN", "", "position feedback")
        nt = spec["noticed"]
        add(nt, "LOGIN", "CCR-1", "C/O", text="console login")
        add(nt + 95, "EVENT", "CCR-1", "C/O", "CARGO-OPS", "UNPLANNED FLOW", "", "manifold valves indicating open; no cargo operation in progress; deck watch reports oil on the water")
        vc = spec["closed"]
        for i, mv in enumerate(spec["valves"]):
            add(vc - 310 + i * 70, "CMD", "CCR-1", "C/O", mv, "CLOSE", "", "")
            add(vc - 284 + i * 70, "STATE", "VALVE-CTRL", "", mv, "CLOSED", "", "position feedback")
        for i, tank in enumerate(spec["lost_tanks"]):
            add(vc - 150 + i * 30, "CMD", "CCR-1", "C/O", f"DROP-VALVE-{tank}", "CLOSE", "", "")
            add(vc - 120 + i * 30, "STATE", "VALVE-CTRL", "", f"DROP-VALVE-{tank}", "CLOSED", "", "position feedback")
        add(vc + 95, "ALARM", "CCR-1", "C/O", "COT-LEVEL-HH-GROUP", "INHIBIT OFF", "", "inhibit reset at console")
        add(vc + 118, "ALARM", "CCR-1", "C/O", "VALVE-POSITION-GROUP", "INHIBIT OFF", "", "inhibit reset at console")
        add(vc + 121, "ALARM", "ALARM-PANEL", "", "VALVE-POSITION-DISCREPANCY", "RAISED", "", "valves moved without console command")
        add(vc + 600, "ALARM", "ALARM-PANEL", "", "VALVE-POSITION-DISCREPANCY", "ACKNOWLEDGED", "", "")
        add(a + dur, "REMOTE", "RMT-GW", ODD_ACCOUNT, "SESSION", "DETACH", "", s_id)
        add(vc + 2400, "EVENT", "CCR-1", "C/O", "REMOTE-GATEWAY", "DISCONNECTED", "", "remote maintenance gateway network cable removed by master's order")
        # cargo survey with the Coast Guard attending, morning of D+5
        st = ts("2027-09-19T08:10Z") + (0 if key == "kalvora_star" else 1500)
        final = sum(volume(tk, st) for tk in ["1P", "1S", "2P", "2S", "3P", "3S", "4P", "4S", "5P", "5S", "6P", "6S"])
        add(st, "SURVEY", "CCR-1", "C/O", "CARGO-FIGURES", f"{final:.0f}", "bbl", "tank survey with Coast Guard boarding team and cargo surveyor attending")
        add(st + 1500, "SURVEY", "CCR-1", "C/O", "CARGO-SHORTFALL", f"{spec['loaded'] - final:.0f}", "bbl", "shortfall against the figures agreed after loading")
        add(st + 2100, "SURVEY", "CCR-1", "C/O", "VALVE-RECORD", "REVIEWED", "", "manifold valves read open from 04:00Z to about 05:30Z on 14 Sep; no console or deck-log entry ordering them open; "
            "level and valve-position alarms inhibited from shortly before 04:00Z until reset at the console after 05:30Z")
        add(st + 2700, "EVENT", "CCR-1", "C/O", "PORT-STATE", "HELD AT BERTH", "", "vessel held at berth by the Coast Guard pending investigation")
        rows.sort(key=lambda r: (r[0], r[3]))
        rows = [[untok(x) for x in r] for r in rows]
        total += write_csv(f"05_other_sources/telemetry/vessel_cargo_control_{key}.csv", COLS, rows)
    print(f"vessel_ot_logs: {total:,} rows in 3 files ({n_s} remote sessions)")


if __name__ == "__main__":
    main()
