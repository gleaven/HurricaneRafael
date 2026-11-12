"""Port conditions, arrivals and cargo manifests from the finished port simulation."""
import csv
import zlib

from common import iso, local_ts, out_path, rng, ts, local_iso
from maritime_base import DAY, H, PORT_NAMES
from maritime_core import (BLAST, INNER_E_PERMITS, REOPEN1, REOPEN2, RESTRICTION_LIFTED, T0, T_END, XRAY, YANKEE, ZULU, ais_name)

SEGMENTS = [("SEG-ENT", "Sea bar and jetty channels (sea buoy to Harbor Island)"), ("SEG-BAY", "Bay reaches (Harbor Island to Harbor Bridge)"),
            ("SEG-LAQ", "La Quinta Channel"), ("SEG-INNER-E", "Inner Harbor: Harbor Bridge to the west limit of the Main Turning Basin"),
            ("SEG-INNER-W", "Inner Harbor: Industrial Canal to Viola Turning Basin"), ("SEG-GIWW", "Gulf Intracoastal Waterway in the Captain of the Port zone"),
            ("SEG-ANCH", "Aransas Pass offshore anchorage")]
AGENTS = ["Gulf Coast Marine Agency", "Coastal Bend Ship Agency", "Aransas Maritime Agents", "Lone Star Vessel Agency"]
COND_HEADER = ["order_id", "issued_utc", "effective_utc", "authority", "order_type", "port_condition", "segment_id", "segment_name", "status",
               "vessel_mmsi", "terminal_id", "text"]
ARR_HEADER = ["arrival_id", "vessel_name", "mmsi", "imo_number", "call_sign", "flag_state", "vessel_type", "port_of_arrival", "terminal", "terminal_id",
              "berth_id", "anchorage_position_id", "draft_arrival_m", "port_of_departure", "next_port", "noa_submitted_datetime", "eta_datetime",
              "eta_revised_datetime", "ata_anchorage_datetime", "ata_datetime", "atd_datetime", "voyage_number", "agent", "noa_status", "hold_log",
              "shift_berth_id", "shift_datetime"]
MAN_HEADER = ["manifest_id", "bl_id", "bl_type", "mode", "direction", "arrival_id", "mmsi", "vessel_name", "carrier", "cargo_description",
              "hs_commodity_code", "quantity", "unit_of_measure", "cargo_weight_kg", "shipper_name", "supplier_id", "consignee_name", "consignee_id",
              "port_of_lading", "port_of_discharge", "booking_date", "planned_arrival_date", "arrival_date", "release_date", "hazmat_flag",
              "un_number", "container_numbers"]


def z(t):
    return iso(t) if t is not None else ""


def day(t):
    """Calendar date at the port (local time)."""
    return local_iso(t)[:10] if t is not None else ""


def write_port_conditions(sim):
    CG = "USCG Captain of the Port, Sector Corpus Christi"
    PA = "Port of Corpus Christi Authority"
    rows = []

    def order(oid, issued, eff, auth, typ, cond, seg_status, text, mmsi="", term=""):
        if seg_status is None:
            rows.append([oid, z(issued), z(eff), auth, typ, cond, "", "", "", mmsi, term, text])
        else:
            for sid, name in SEGMENTS:
                if sid in seg_status:
                    rows.append([oid, z(issued), z(eff), auth, typ, cond, sid, name, seg_status[sid], mmsi, term, text])
    allseg = lambda st: {sid: st for sid, _ in SEGMENTS}
    k = sim.vessels["VSL-0041"]; o = sim.vessels["VSL-0042"]
    order("MSIB 27-031", ts("2027-07-30T15:00Z"), ts("2027-08-01T05:00Z"), CG, "CHANNEL STATUS", "SEASONAL ALERT (hurricane season)", allseg("OPEN"),
          "Normal operations. All segments open to all traffic.")
    order("MSIB 27-034", ts("2027-08-18T14:00Z"), ts("2027-08-20T12:00Z"), CG, "NOTICE", "SEASONAL ALERT (hurricane season)", None,
          "Maintenance dredging in the barge lane beside the bay reach of the ship channel. Dredge monitors VHF 13. No restriction on deep-draft traffic.")
    order("MSIB 27-041", XRAY - 40 * 60, XRAY, CG, "PORT CONDITION", "X-RAY", allseg("OPEN"),
          "Port Condition X-Ray: gale-force winds possible within 48 hours. Port open. Ocean-going vessels over 500 gross tons make plans to depart or request permission to remain. Cargo operations to wind down.")
    for v, bid in ((k, "TERM-01-B07"), (o, "TERM-01-B08")):
        order("COTP LTR 27-2026", ts("2027-09-11T18:20Z"), ts("2027-09-11T18:20Z"), CG, "VESSEL ORDER", "X-RAY", None,
              f"Request approved: {ais_name(v.name)} may remain moored at {bid} through Port Condition Zulu under the terminal's heavy-weather mooring plan.",
              mmsi=str(v.mmsi), term="TERM-01")
    order("MSIB 27-042", YANKEE - 45 * 60, YANKEE, CG, "PORT CONDITION", "YANKEE",
          {"SEG-ENT": "CLOSED TO INBOUND", "SEG-BAY": "CLOSED TO INBOUND", "SEG-LAQ": "CLOSED TO INBOUND", "SEG-INNER-E": "CLOSED TO INBOUND",
           "SEG-INNER-W": "CLOSED TO INBOUND", "SEG-GIWW": "CLOSED TO INBOUND", "SEG-ANCH": "OPEN"},
          "Port Condition Yankee: gale-force winds expected within 24 hours. Port closed to inbound traffic. Inbound vessels hold at the offshore anchorage. Vessels in port depart or complete mooring arrangements.")
    order("COTP ORDER 27-2027", ZULU - 50 * 60, ZULU, CG, "PORT CONDITION", "ZULU", allseg("CLOSED"),
          "Port Condition Zulu effective 1700Z 13 SEP: ship channel closed to all traffic. Vessels at the offshore anchorage directed to sea, to be clear by 2300Z. Order served on the agents of every vessel in or approaching the port.")
    order("PCCA STORM LOG", ts("2027-09-14T02:40Z"), ts("2027-09-14T02:40Z"), PA, "NOTICE", "ZULU", None,
          "Channel clear of traffic. Inner Harbor cameras dark on loss of shore power.")
    order("COTP ORDER 27-2028", ts("2027-09-14T14:40Z"), ts("2027-09-14T15:00Z"), CG, "SAFETY ZONE", "ZULU",
          {"SEG-INNER-E": "CLOSED", "SEG-INNER-W": "CLOSED"},
          "Safety zone: all waters of the Inner Harbor. Entry prohibited except response vessels authorised by the Captain of the Port. Oil reported on the water at an Inner Harbor terminal. The ship channel remains closed.")
    order("MSIB 27-044", ts("2027-09-15T17:30Z"), ts("2027-09-15T18:00Z"), CG, "CHANNEL STATUS", "RECOVERY", allseg("CLOSED"),
          "Ship channel remains closed pending surveys of depths and aids to navigation and containment of the Inner Harbor spill. Survey, aids-to-navigation and response vessels only.")
    for v, bid in ((k, "TERM-01-B07"), (o, "TERM-01-B08")):
        order("COTP ORDER 27-2029", ts("2027-09-19T08:00Z"), ts("2027-09-19T08:00Z"), CG, "VESSEL ORDER", "RECOVERY", None,
              f"Captain of the Port order: {ais_name(v.name)} to remain at {bid} until released. Inspection completed.", mmsi=str(v.mmsi), term="TERM-01")
    order("MSIB 27-046", ts("2027-09-23T20:00Z"), local_ts(10, "06:00"), CG, "NOTICE", "RECOVERY", {"SEG-ENT": "CLOSED"},
          "State ferry crossings between Harbor Island and Port Aransas authorised, daylight and evening service. The ship channel remains closed to all other traffic.")
    order("MSIB 27-047", ts("2027-09-27T19:00Z"), ts("2027-09-28T12:00Z"), CG, "CHANNEL STATUS", "RECOVERY", {"SEG-GIWW": "OPEN NORTH OF THE SHIP CHANNEL"},
          "Gulf Intracoastal Waterway open to tows north of the ship channel crossing. Tows may not enter or cross the ship channel.")
    order("MSIB 27-051", ts("2027-10-14T14:30Z"), REOPEN1, CG, "CHANNEL STATUS", "SEASONAL ALERT (hurricane season)",
          {"SEG-ENT": "OPEN", "SEG-BAY": "OPEN", "SEG-LAQ": "OPEN", "SEG-INNER-E": "RESTRICTED", "SEG-INNER-W": "CLOSED TO DEEP-DRAFT", "SEG-GIWW": "OPEN", "SEG-ANCH": "OPEN"},
          "Partial reopening: outer and bay reaches cleared for deep-draft traffic. Inner channel restricted for vessel decontamination: deep-draft vessels enter the Main Turning Basin only under a Captain of the Port permit, from 1400Z 15 OCT, and are decontaminated before departure; no deep-draft traffic west of the Main Turning Basin. Backlog at the anchorage worked by priority.")
    order("MSIB 27-056", ts("2027-10-27T21:00Z"), RESTRICTION_LIFTED, CG, "CHANNEL STATUS", "SEASONAL ALERT (hurricane season)",
          {"SEG-INNER-E": "OPEN", "SEG-INNER-W": "OPEN"}, "Spill cleanup moves to monitoring. Inner-channel restrictions lifted.")
    order("COTP ORDER 27-2031", BLAST + 15 * 60, BLAST + 15 * 60, CG, "CHANNEL STATUS", "SEASONAL ALERT (hurricane season)", allseg("CLOSED"),
          "Explosion reported beside a harbor tug near the Port Aransas jetties. Ship channel closed to all traffic until further notice. Safety zone: all waters between the jetties. Vessels at berth remain at berth; inbound vessels hold at the offshore anchorage.")
    order("MSIB 27-058", ts("2027-10-30T16:00Z"), ts("2027-10-30T16:00Z"), CG, "SECURITY ZONE", "SEASONAL ALERT (hurricane season)", {"SEG-ENT": "CLOSED"},
          "Channel remains closed. Navy explosive ordnance disposal and mine countermeasures teams and Coast Guard vessels are searching the entrance channel. Security zone: entrance channel and approaches; no entry.")
    order("MSIB 27-060", ts("2027-11-05T22:00Z"), ts("2027-11-05T22:00Z"), CG, "NOTICE", "SEASONAL ALERT (hurricane season)", None,
          "A second object was located near the entrance channel and rendered safe. The sweep continues. Channel remains closed.")
    order("MSIB 27-062", REOPEN2 - 2 * H, REOPEN2, CG, "CHANNEL STATUS", "SEASONAL ALERT (hurricane season)", allseg("OPEN"),
          "Full sweep of the ship channel completed. Channel open to all traffic. Vessels at berth depart first; anchorage backlog berths in order of priority.")
    for v, nb in ((k, "TERM-13-B01"), (o, "TERM-15-B01")):
        order("COTP LTR 27-2034", ts("2027-11-14T20:00Z"), ts("2027-11-15T14:00Z"), CG, "VESSEL ORDER", "SEASONAL ALERT (hurricane season)", None,
              f"{ais_name(v.name)} authorised to shift under tow assistance from TERM-01 to lay berth {nb} on 15 NOV. Vessel remains under Captain of the Port control.",
              mmsi=str(v.mmsi), term=nb[:7])
    order("MSIB 27-071", ts("2027-11-30T15:00Z"), ts("2027-12-01T06:00Z"), CG, "PORT CONDITION", "NORMAL", allseg("OPEN"),
          "End of hurricane season. Normal operations.")
    rows.sort(key=lambda r: (r[2], r[0], r[6]))
    with open(out_path("05_other_sources/supply/port_conditions.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COND_HEADER)
        w.writerows(rows)
    return len(rows)


def agent_for(v):
    return AGENTS[zlib.crc32((v.rec.get("operator") or v.name).encode()) % len(AGENTS)]


def port_code(name):
    return PORT_NAMES.get(name, name)


def write_arrivals(sim):
    rows = []
    calls = [c for c in sim.calls if (c.ata_anch or c.ata or c.eta) >= T0 - 4 * DAY or (c.ata and (c.atd is None or c.atd >= T0))]
    for c in calls:
        v = c.v
        r = v.rec
        hold = list(c.hold)
        if c.ata_anch and c.ata_anch < YANKEE < (c.atd_anch or 1e18) and c.status != "CANCELLED":
            hold.append((YANKEE, "Port Condition Yankee: port closed to inbound; holding at anchorage"))
        if c.ata_anch and c.ata_anch < BLAST < (c.atd_anch or 1e18) or (c.ata_anch and BLAST <= c.ata_anch < REOPEN2):
            hold.append((max(BLAST + 20 * 60, c.ata_anch), "ship channel closed; holding at anchorage"))
        if c.ata and c.ata < BLAST and (c.atd is None or c.atd > REOPEN2) and v.id not in ("VSL-0041", "VSL-0042"):
            hold.append((BLAST + 20 * 60, "ship channel closed; remaining at berth"))
        hold.sort()
        status = c.status
        if status == "DEPARTED" and c.atd is not None and c.atd > T_END:
            status = "IN PORT"
        term = sim.berths[c.berth]["terminal_id"] if c.berth else ""
        tname = sim.terminals[term]["terminal_name"] if term else ""
        eta_rev = ""
        if hold and c.ata:
            eta_rev = z(c.ata - (c.ata % 3600))
        yr = iso(c.eta)[:4]
        voy = f"{yr}-{''.join(w[0] for w in ais_name(v.name).split())[:3]}-{zlib.crc32(c.id.encode()) % 900 + 100}"
        rows.append([c.id, ais_name(v.name), str(v.mmsi), r.get("imo") or "", r.get("call_sign") or "", r.get("flag") or "", r.get("sub_class") or v.cls,
                     "USCRP", tname, term, c.berth or "", c.anch or "", f"{c.draft_arr:.1f}" if c.draft_arr else "", port_code(c.last_port), port_code(c.next_port),
                     z(c.noa_time), z(c.eta), eta_rev, z(c.ata_anch), z(c.ata), z(c.atd if (c.atd and c.atd <= T_END) else None), voy, agent_for(v), status,
                     " | ".join(f"{z(t)} {txt}" for t, txt in hold), (c.shift[1] if c.shift else ""), z(c.shift[0]) if c.shift else ""])
    # the sealift call that was postponed before the storm
    sl = sim.vessels["VSL-0019"]
    r = sl.rec
    rows.append(["NOA-2027-CC-18207", ais_name(sl.name), str(sl.mmsi), r.get("imo") or "", r.get("call_sign") or "", r.get("flag") or "", r.get("sub_class") or "",
                 "USCRP", sim.terminals["TERM-07"]["terminal_name"], "TERM-07", "TERM-07-B01", "", "7.4", "USBPT", "", z(ts("2027-09-06T15:00Z")),
                 z(ts("2027-09-15T14:00Z")), "", "", "", "", "2027-CS-311", agent_for(sl), "CANCELLED",
                 f"{z(XRAY + 9 * H)} port call postponed: Port Condition X-Ray", "", ""])
    rows.sort(key=lambda x: (x[16], x[0]))
    with open(out_path("05_other_sources/supply/vessel_arrivals.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(ARR_HEADER)
        w.writerows(rows)
    return len(rows)


def write_manifests(sim):
    rs = rng("manifests")
    rows = []
    n = [0]

    def add(mode, direction, call, v, carrier, desc, hs, qty, uom, kg, shipper, sup, cons, cons_id, pol, pod, booked, planned, arrived, released,
            haz="N", un="", cont="", bl_type="Master"):
        n[0] += 1
        mid = f"MAN-{27 if (arrived or planned or booked or 0) < ts('2028-01-01T00:00Z') else 28}-{n[0]:06d}"
        pre = "".join(w[0] for w in ais_name(v.name).split())[:3] if v else {"AIR": "AWB", "ROAD": "TRK"}.get(mode, "BL")
        bl = f"{'BL' if mode == 'SEA' else 'AWB' if mode == 'AIR' else 'PRO'}-{pre}-{iso(planned or arrived or booked)[:4]}-{zlib.crc32(mid.encode()) % 9000 + 1000}"
        rows.append([mid, bl, bl_type, mode, direction, call.id if call else "", str(v.mmsi) if v else "", ais_name(v.name) if v else "", carrier, desc, hs,
                     qty, uom, int(kg) if kg else "", shipper, sup, cons, cons_id, pol, pod, day(booked), day(planned), day(arrived), day(released), haz, un, cont])
    relief_done = False
    for c in sorted(sim.calls, key=lambda c: (c.ata or 1e18, c.id)):
        if c.ata is None or (c.atd or 1e18) < T0:
            continue
        v = c.v
        term = sim.terminals[sim.berths[c.berth]["terminal_id"]]
        op = term["operator"]
        tp = v.rec.get("typical_pattern", "")
        kind = c.cargo
        lastp, nextp = c.last_port, c.next_port
        booked = c.noa_time - float(rs.uniform(3, 12)) * DAY
        rel = c.atd if (c.atd and c.atd <= T_END) else None
        carrier = v.rec.get("operator") or ""
        if v.id in ("VSL-0041", "VSL-0042"):
            qty = 720000 if v.id == "VSL-0041" else 735000
            add("SEA", "EXPORT", c, v, carrier, "CRUDE PETROLEUM OIL", "2709.00", qty, "BBL", qty * 136, op, "", "TO ORDER", "", "Corpus Christi, TX", nextp,
                booked, c.eta, c.ata, None, "Y", "UN1267")
            continue
        if v.id == "VSL-0019":
            for desc, uom, kg in (("ROTARY-WING AIRCRAFT, SHRINK-WRAPPED, ARMY AVIATION BRIGADE", "LOT", 1650000), ("GROUND SUPPORT EQUIPMENT AND WHEELED VEHICLES", "LOT", 2380000),
                                  ("CONTAINERISED UNIT EQUIPMENT", "LOT", 910000)):
                add("SEA", "EXPORT", c, v, carrier, desc, "8802.12" if "AIRCRAFT" in desc else "8705.90", 1, uom, kg, "U.S. Army, Fort Hood (aviation brigade)", "",
                    "U.S. Army (destination not announced)", "", "Corpus Christi, TX", "(not announced)", ts("2027-10-20T15:00Z"), ts("2027-10-29T13:00Z"), c.ata, c.atd)
            continue
        if kind == "crude":
            qty = int(round((1000000 if v.draft_max >= 15.5 else 700000) * float(rs.uniform(0.96, 1.02)), -3))
            add("SEA", "EXPORT", c, v, carrier, "CRUDE PETROLEUM OIL", "2709.00", qty, "BBL", qty * 136, op, "", "TO ORDER", "", "Corpus Christi, TX", nextp, booked, c.eta, c.ata, rel, "Y", "UN1267")
        elif kind == "lng":
            qty = int(round(float(rs.uniform(160000, 172000)), -2))
            add("SEA", "EXPORT", c, v, carrier, "LIQUEFIED NATURAL GAS", "2711.11", qty, "M3", qty * 450, op, "", "TO ORDER", "", "Corpus Christi, TX", nextp, booked, c.eta, c.ata, rel, "Y", "UN1972")
        elif kind == "product":
            cargo = term.get("terminal_type", "")
            desc = ["GASOLINE, UNLEADED", "DIESEL FUEL, ULTRA-LOW SULFUR", "JET FUEL", "NAPHTHA"][int(rs.integers(0, 4))]
            qty = int(round(float(rs.uniform(240000, 320000)), -3))
            add("SEA", c.direction, c, v, carrier, desc, "2710.12" if "GASOLINE" in desc or "NAPHTHA" in desc else "2710.19", qty, "BBL", qty * 125,
                op if c.direction == "EXPORT" else carrier, "", op if c.direction == "IMPORT" else "TO ORDER", "",
                lastp if c.direction == "IMPORT" else "Corpus Christi, TX", "Corpus Christi, TX" if c.direction == "IMPORT" else nextp, booked, c.eta, c.ata, rel, "Y", "UN1203")
        elif kind == "bulk":
            com = tp[tp.find("(") + 1:tp.find(")")].upper() if "(" in tp else "DRY BULK"
            qty = int(round(float(rs.uniform(34000, 58000)), -2))
            add("SEA", c.direction, c, v, carrier, com, "2713.11" if "COKE" in com else "1007.90" if "SORGHUM" in com else "1001.99" if "WHEAT" in com else "2601.12", qty, "MT",
                qty * 1000, op if c.direction == "EXPORT" else carrier, "", op if c.direction == "IMPORT" else "TO ORDER", "",
                lastp if c.direction == "IMPORT" else "Corpus Christi, TX", "Corpus Christi, TX" if c.direction == "IMPORT" else nextp, booked, c.eta, c.ata, rel)
        else:
            com = tp.split(" through")[0].split(";")[0].upper()[:60] if tp else "GENERAL CARGO"
            if v.id == "VSL-0012":
                com = "GENERAL AND PROJECT CARGO"
            qty = int(round(float(rs.uniform(4000, 16000)), -2))
            add("SEA", "IMPORT", c, v, carrier, com, "7304.19" if "PIPE" in com or "STEEL" in com else "8502.31" if "WIND" in com else "9999.00", qty, "MT", qty * 1000,
                carrier, "", op, "", lastp, "Corpus Christi, TX", booked, c.eta, c.ata, rel)
        if v.id == "VSL-0012" and c.ata and c.ata > REOPEN1 and not relief_done:
            relief_done = True
            # the 40 relief containers booked five days before landfall, landed on the first call after the reopening
            ids = [f"CLGU{4410000 + int(x):07d}" for x in sorted(rs.choice(89000, 40, replace=False))]
            parts = [("BOTTLED WATER, PALLETISED", 12), ("SHELF-STABLE MEALS", 9), ("TARPAULINS, PLYWOOD AND ROOFING KITS", 8), ("PORTABLE GENERATORS AND FUEL CANS", 6),
                     ("HYGIENE AND CLEANING KITS", 5)]
            i = 0
            for desc, k in parts:
                add("SEA", "IMPORT", c, v, carrier, "RELIEF SUPPLIES: " + desc, "9999.00", k, "CONTAINER (40 FT)", k * 21500, "Gulf Relief Logistics (Tampa consolidation)", "",
                    "Gulf Relief Logistics", "VND-0006", "Tampa, FL", "Corpus Christi, TX", ts("2027-09-09T14:00Z"), ts("2027-09-12T11:00Z"), c.ata,
                    c.ata + float(rs.uniform(14, 40)) * H, cont=" ".join(ids[i:i + k]), bl_type="House")
                i += k
    # pump parts for the water plant: ordered D+2 with a nine-day quote, shipped from out of state, delivered D+36
    add("ROAD", "DOMESTIC", None, None, "Common carrier (less-than-truckload)", "PUMP REBUILD PARTS: IMPELLER, SHAFT SLEEVE, MECHANICAL SEAL, BEARING SET", "8413.91", 1, "SHIPMENT",
        860, "Delta Pumps & Controls (out-of-state distribution center)", "VND-0005", "City of Corpus Christi Water Department, O.N. Stevens Water Treatment Plant", "",
        "Tulsa, OK", "Corpus Christi, TX", local_ts(2, "15:30"), local_ts(11, "12:00"), local_ts(36, "10:40"), local_ts(36, "10:40"))
    # air relief into NAS Corpus Christi, D+34 to D+43: 26 military airlift flights and 14 civil charters
    cargo = ["BOTTLED WATER AND WATER PURIFICATION UNITS", "SHELF-STABLE MEALS", "PORTABLE GENERATORS", "MEDICAL SUPPLIES AND PHARMACEUTICALS", "TARPAULINS AND SHELTER KITS",
             "COTS, BLANKETS AND HYGIENE KITS", "INFANT AND ELDER CARE SUPPLIES", "CHAINSAWS, PUMPS AND CLEANUP EQUIPMENT"]
    cons = [("FEMA Region 6, Joint Field Office", ""), ("Texas Division of Emergency Management", ""), ("Gulf Relief Logistics", "VND-0006")]
    flights = ["Military airlift (C-17)"] * 26 + ["Civil charter"] * 14
    order = rs.permutation(40)
    days = sorted(int(x) for x in rs.integers(34, 44, 40))
    for i, d in zip(order, days):
        fl = flights[i]
        cn = cons[int(rs.integers(0, 2))] if fl.startswith("Military") else cons[int(rs.integers(1, 3))]
        t = local_ts(d, "06:00") + float(rs.uniform(0, 15)) * H
        kg = float(rs.uniform(52000, 74000)) if fl.startswith("Military") else float(rs.uniform(14000, 38000))
        add("AIR", "DOMESTIC", None, None, fl, "RELIEF SUPPLIES: " + cargo[int(rs.integers(0, len(cargo)))], "9999.00", int(rs.integers(14, 19)) if fl.startswith("Military") else int(rs.integers(6, 15)),
            "PALLET", kg, "Federal Emergency Management Agency" if fl.startswith("Military") else "Gulf Relief Logistics (donated goods)", "", cn[0], cn[1],
            ["Joint Base San Antonio, TX", "Dobbins ARB, GA", "Fort Worth, TX", "Memphis, TN", "Atlanta, GA", "Dallas, TX"][int(rs.integers(0, 6))], "NAS Corpus Christi (NGP), TX",
            t - float(rs.uniform(1.5, 4)) * DAY, t, t, t + float(rs.uniform(2, 20)) * H)
    rows.sort(key=lambda r: (r[22] or r[21] or r[20], r[0]))
    with open(out_path("05_other_sources/supply/cargo_manifest.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(MAN_HEADER)
        w.writerows(rows)
    return len(rows)
