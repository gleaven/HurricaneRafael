"""Entity layer of the knowledge graph (called from build_graph.py).

Adds the registries, the data streams, the expected observations and the answer keys to the
story/fact/event graph, and links them:

  nodes   Organization, Vessel, Aircraft, Facility, Asset, Equipment, Host, UserAccount,
          ScadaTagGroup, Sensor, SocialAccount, ResponseUnit, Station, Area, Terminal, Berth,
          DataStream, Registry, Observation*, AnswerKeyPath*, OldId*          (* internal view only)
  edges   LISTED_IN (entity -> Registry), RECORDS (DataStream -> Registry),
          OPERATED_BY / OWNED_BY / PART_OF / SERVES / BASED_AT / LOCATED_AT / WITHIN,
          EMPLOYED_BY (Character -> Organization), INVOLVES (Event -> entity),
          MENTIONS_ENTITY (Story / PublicFact -> entity, by canon name),
          OBSERVED_IN (Event -> DataStream), HAS_OBSERVATION (Event -> Observation),
          EVIDENCED_BY (Observation -> DataStream), ABOUT_ENTITY (Observation -> entity),
          SOLVES (AnswerKeyPath -> Thread), HAS_STEP (AnswerKeyPath -> Observation),
          USES_STREAM (AnswerKeyPath -> DataStream), SAME_AS (scenario Entity / OldId -> registry node)

Anything that only the internal view may show is created with internal=True: never-public
entities (matched against restricted_terms.json), observations, answer keys, old-id aliases and
every edge that touches them or an Event.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "06_data_streams")

INTERNAL_NODE_TYPES = {"Observation", "AnswerKeyPath", "OldId"}
PUBLIC_PROPS = {
    "Organization": ["kind", "jurisdiction", "public_role"], "Vessel": ["mmsi", "kind", "flag", "deep_draft"], "Aircraft": ["icao24", "kind", "home_base"],
    "Facility": ["kind", "latitude", "longitude"], "Asset": ["kind", "latitude", "longitude"], "Equipment": ["kind"], "Host": ["kind", "zone", "ip"],
    "UserAccount": ["kind", "department"], "ScadaTagGroup": ["tags", "site"], "Sensor": ["kind", "latitude", "longitude"], "SocialAccount": ["kind", "language"],
    "ResponseUnit": ["kind", "agency"], "Station": ["agency", "latitude", "longitude"], "Area": ["kind"], "Terminal": ["kind", "latitude", "longitude"],
    "Berth": ["kind", "latitude", "longitude"], "DataStream": ["path", "format", "delivered", "cadence"], "Registry": ["file", "count"],
}


def load(name):
    with open(os.path.join(REG, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"\(.*?\)", "", s or "")).strip().lower()


def extend(nodes, edges, node, edge, ctx, stories):
    terms = json.load(open(os.path.join(ROOT, "02_public_record", "restricted_terms.json"), encoding="utf-8"))["terms"]
    # names that are never public (single-name patterns only; the id-format patterns in the list are for news text)
    never = [re.compile(t["pattern"], re.I) for t in terms if t["public_from_day"] is None and "|" not in t["pattern"] and "\\b" not in t["pattern"]]
    try:        # identifiers that appear only in raw logs (project rule): keep them out of the public view too
        rid = json.load(open(os.path.join(REG, "_internal", "gw_host_registry_truth.json"), encoding="utf-8"))["restricted_identifiers"]["ids"]
        never += [re.compile(re.escape(x), re.I) for x in rid] + [re.compile(r"ClearPath", re.I)]
    except (OSError, KeyError):
        pass

    def hidden(*texts):
        s = " ".join(str(t) for t in texts if t)
        return any(r.search(s) for r in never)

    names = {}          # canon name (lower) -> node id, for text matching
    idtok = {}          # exact id token -> node id, for event text

    def reg_node(nid, ntype, label, registry, internal=False, **props):
        if nid in nodes:
            if nodes[nid]["type"] == "Entity":  # the scenario's own record of the same thing: it becomes the registry node (truth props stay internal-only)
                nodes[nid].update(type=ntype, label=label, internal=internal, **props)
            edge(nid, "LISTED_IN", "registry:" + registry, internal=nodes[nid]["internal"])
            idtok[nid] = nid
            return nid
        node(nid, ntype, label, internal=internal, **props)
        edge(nid, "LISTED_IN", "registry:" + registry, internal=internal)
        idtok[nid] = nid
        return nid

    def name_of(nid, *ns):
        for n in ns:
            n = (n or "").strip()
            if len(n) >= 6 and not n.isdigit():
                names.setdefault(n.lower(), nid)

    def registry(key, file, count, label):
        node("registry:" + key, "Registry", label, file=file, count=count)

    # ---------------------------------------------------------------- organisations
    O = load("organizations")
    registry("organizations", "06_data_streams/organizations.json", len(O["organizations"]), "Organisations")
    org_by_name = {}
    for o in O["organizations"]:
        h = hidden(o["name"])
        reg_node(o["org_id"], "Organization", o["name"], "organizations", internal=h, kind=o.get("type"), jurisdiction=o.get("jurisdiction"), public_role=o.get("public_role"))
        org_by_name[norm(o["name"])] = o["org_id"]
        name_of(o["org_id"], o["name"])
        if o.get("abbr") and len(o["abbr"]) >= 4 and o["abbr"].isupper():
            names.setdefault(o["abbr"].lower(), o["org_id"])
            org_by_name[o["abbr"].lower()] = o["org_id"]
    for o in O["organizations"]:
        par = o.get("parent")
        pid = par if par in nodes else org_by_name.get(norm(o.get("parent_name") or ""))
        if pid and pid != o["org_id"]:
            edge(o["org_id"], "PART_OF", pid, internal=nodes[o["org_id"]]["internal"] or nodes[pid]["internal"])

    def org_edge(nid, rel, org_name):
        oid = org_by_name.get(norm(org_name))
        if not oid and org_name:
            for part in re.split(r"\s*/\s*|,\s*| and ", org_name):
                oid = org_by_name.get(norm(part))
                if oid:
                    break
        if oid and nid in nodes:
            edge(nid, rel, oid, internal=nodes[nid]["internal"] or nodes[oid]["internal"])
            return True
        return False

    # ---------------------------------------------------------------- areas
    A = load("areas")["areas"]
    registry("areas", "06_data_streams/areas.json", len(A), "Areas (districts, zones, neighbourhoods, tracts)")
    area_boxes = []
    for a in A:
        reg_node(a["area_id"], "Area", a["name"], "areas", kind=a.get("area_type"))
        if a.get("area_type") not in ("census_tract", "zip", "patrol_beat"):
            name_of(a["area_id"], a["name"])
        if a.get("bbox") and a.get("area_type") in ("neighbourhood", "community", "city", "census_tract"):
            b = a["bbox"]
            area_boxes.append(((b[2] - b[0]) * (b[3] - b[1]), b, a["area_id"]))
    for a in A:
        for w in a.get("within", []) or []:
            if w in nodes and w != a["area_id"]:
                edge(a["area_id"], "WITHIN", w)
    area_boxes.sort()

    def locate(nid, lat, lon):
        if lat is None or lon is None:
            return
        for _, b, aid in area_boxes:
            if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]:
                edge(nid, "LOCATED_AT", aid, internal=nodes[nid]["internal"])
                return

    # ---------------------------------------------------------------- port
    T = load("terminal_registry")
    registry("terminals", "06_data_streams/terminal_registry.json", len(T["terminals"]) + len(T["berths"]), "Terminals, berths, harbours and anchorage")
    for t in T["terminals"]:
        reg_node(t["terminal_id"], "Terminal", t["terminal_name"], "terminals", kind=t.get("terminal_type"), latitude=t.get("latitude"), longitude=t.get("longitude"))
        name_of(t["terminal_id"], t["terminal_name"], t["terminal_name"].split(" — ")[0])
        org_edge(t["terminal_id"], "OPERATED_BY", t.get("operator"))
        locate(t["terminal_id"], t.get("latitude"), t.get("longitude"))
    for b in T["berths"]:
        reg_node(b["berth_id"], "Berth", f"{b.get('berth_name') or b['berth_id']} ({b['terminal_id']})", "terminals", kind=b.get("berth_type") or "berth", latitude=b.get("latitude"), longitude=b.get("longitude"))
        edge(b["berth_id"], "PART_OF", b["terminal_id"])
    for hb in T.get("harbours", []):
        reg_node(hb["harbour_id"], "Terminal", hb.get("name") or hb["harbour_id"], "terminals", kind="small-craft harbour", latitude=hb.get("latitude"), longitude=hb.get("longitude"))
        name_of(hb["harbour_id"], hb.get("name"))
        locate(hb["harbour_id"], hb.get("latitude"), hb.get("longitude"))
    slip_harbour = {s["slip_id"]: s["harbour_id"] for s in T.get("slips", [])}
    for p in T.get("anchorage_positions", []):
        reg_node(p["position_id"], "Berth", p.get("name") or p["position_id"], "terminals", kind="anchorage position", latitude=p.get("latitude"), longitude=p.get("longitude"))
        if "TERM-08" in nodes:
            edge(p["position_id"], "PART_OF", "TERM-08")

    # ---------------------------------------------------------------- vessels, aircraft
    V = load("vessels")["vessels"]
    registry("vessels", "06_data_streams/vessels.json", len(V), "Vessels")
    for v in V:
        h = hidden(v["vessel_name"])
        reg_node(v["vessel_id"], "Vessel", v["vessel_name"], "vessels", internal=h, mmsi=v.get("mmsi"), kind=v.get("class"), flag=v.get("flag"), deep_draft=v.get("deep_draft"))
        name_of(v["vessel_id"], v["vessel_name"], re.sub(r"^(MT|MV|FV|RV|USCGC|Tug|M/V)\s+", "", v["vessel_name"]))
        if v.get("mmsi"):
            idtok[str(v["mmsi"])] = v["vessel_id"]
        org_edge(v["vessel_id"], "OPERATED_BY", v.get("operator"))
        hb = v.get("home_berth_id")
        tgt = hb if hb in nodes else slip_harbour.get(hb)
        if tgt:
            edge(v["vessel_id"], "BASED_AT", tgt, internal=nodes[v["vessel_id"]]["internal"])
    AC = load("aircraft_registry")
    registry("aircraft", "06_data_streams/aircraft_registry.json", len(AC["aircraft"]), "Aircraft and airfields")
    for f in AC["airfields"]:
        fid = "airfield:" + f["airfield_id"]
        node(fid, "Facility", f["name"], kind="airfield", latitude=f.get("latitude"), longitude=f.get("longitude"))
        edge(fid, "LISTED_IN", "registry:aircraft")
        name_of(fid, f["name"].split(" (")[0])
        locate(fid, f.get("latitude"), f.get("longitude"))
    for a in AC["aircraft"]:
        reg_node(a["aircraft_id"], "Aircraft", f"{a.get('callsign_voice') or a.get('callsign')} ({a.get('model')})", "aircraft", icao24=a.get("icao24"), kind=a.get("role"), home_base=a.get("home_base"))
        idtok[str(a.get("icao24"))] = a["aircraft_id"]
        for cs in (a.get("callsign"), a.get("callsign_voice"), a.get("registration")):
            if cs and len(cs) >= 5:
                idtok[cs] = a["aircraft_id"]
        org_edge(a["aircraft_id"], "OPERATED_BY", a.get("operator"))
        if "airfield:" + str(a.get("home_base")) in nodes:
            edge(a["aircraft_id"], "BASED_AT", "airfield:" + a["home_base"])

    # ---------------------------------------------------------------- facilities, infrastructure, sensors
    F = load("facility_registry")
    registry("facilities", "06_data_streams/facility_registry.json", len(F["facilities"]) + len(F.get("out_of_area", [])), "Facilities")
    for f in F["facilities"] + F.get("out_of_area", []):
        reg_node(f["facility_id"], "Facility", f["facility_name"], "facilities", kind=f.get("facility_type"), latitude=f.get("latitude"), longitude=f.get("longitude"))
        name_of(f["facility_id"], f["facility_name"])
        org_edge(f["facility_id"], "OPERATED_BY", f.get("operator") or f.get("owner") or f.get("system"))
        locate(f["facility_id"], f.get("latitude"), f.get("longitude"))
    I = load("infrastructure_assets")
    registry("infrastructure", "06_data_streams/infrastructure_assets.json", len(I["assets"]) + len(I.get("remote_assets", [])), "Infrastructure assets and equipment")
    for a in I["assets"] + I.get("remote_assets", []):
        reg_node(a["asset_id"], "Asset", a["name"], "infrastructure", kind=a.get("asset_type"), latitude=a.get("latitude"), longitude=a.get("longitude"))
        name_of(a["asset_id"], a["name"], *(a.get("aliases") or []))
        for al in a.get("aliases") or []:
            idtok[al] = a["asset_id"]
        org_edge(a["asset_id"], "OPERATED_BY", a.get("operator"))
        locate(a["asset_id"], a.get("latitude"), a.get("longitude"))
    for a in I["assets"] + I.get("remote_assets", []):
        for s in a.get("serves") or []:
            sid = s if isinstance(s, str) else (s.get("area_id") or s.get("asset_id") or s.get("facility_id"))
            if sid in nodes:
                edge(a["asset_id"], "SERVES", sid)
        for eq in (a.get("equipment") if isinstance(a.get("equipment"), list) else []):
            if not isinstance(eq, dict):
                continue
            eid = eq.get("equipment_id") or eq.get("asset_id")
            if eid:
                reg_node(eid, "Equipment", eq.get("name") or eq.get("label") or eid, "infrastructure", kind=eq.get("type") or eq.get("equipment_type"))
                edge(eid, "PART_OF", a["asset_id"])
    S = load("sensor_registry")
    n_s = sum(len(v) for v in S.values() if isinstance(v, list))
    registry("sensors", "06_data_streams/sensor_registry.json", n_s, "Sensors and observation stations")
    for key, lst in S.items():
        if not isinstance(lst, list):
            continue
        for s in lst:
            sid = s.get("sensor_id") or s.get("site_id")
            reg_node(sid, "Sensor", s.get("sensor_name") or s.get("name") or s.get("site_name") or sid, "sensors", kind=key, latitude=s.get("latitude"), longitude=s.get("longitude"))
            org_edge(sid, "OPERATED_BY", s.get("operator") or s.get("owner") or s.get("owner_agency"))
            locate(sid, s.get("latitude"), s.get("longitude"))
            if s.get("asset_id") in nodes and s.get("asset_id") != sid:
                edge(sid, "PART_OF", s["asset_id"])

    # ---------------------------------------------------------------- response units
    C = load("cad_units")
    registry("cad_units", "06_data_streams/cad_units.json", len(C["units"]) + len(C["stations"]), "Response units and stations")
    for s in C["stations"]:
        reg_node(s["station_id"], "Station", s["name"], "cad_units", agency=s.get("agency"), latitude=s.get("latitude"), longitude=s.get("longitude"))
        locate(s["station_id"], s.get("latitude"), s.get("longitude"))
        org_edge(s["station_id"], "OPERATED_BY", (C["agencies"].get(s.get("agency")) or {}).get("name"))
    for u in C["units"]:
        reg_node(u["unit_id"], "ResponseUnit", u.get("description") or u["unit_id"], "cad_units", kind=u.get("type"), agency=u.get("agency"))
        if u.get("home_station") in nodes:
            edge(u["unit_id"], "BASED_AT", u["home_station"])
        org_edge(u["unit_id"], "OPERATED_BY", (C["agencies"].get(u.get("agency")) or {}).get("name"))

    # ---------------------------------------------------------------- utility network
    H = load("gw_host_registry")
    registry("hosts", "06_data_streams/gw_host_registry.json", len(H["hosts"]) + len(H["users"]), "Utility hosts, accounts and field equipment")
    for h in H["hosts"]:
        hid = hidden(h["hostname"], h.get("role"))
        reg_node(h["hostname"], "Host", h["hostname"], "hosts", internal=hid, kind=h.get("device_type"), zone=h.get("zone"), ip=h.get("ip"))
        if h.get("ip"):
            idtok[h["ip"]] = h["hostname"]
        if h.get("site_id") in nodes:
            edge(h["hostname"], "LOCATED_AT", h["site_id"], internal=hid)
    for e in H["external_systems"]:
        reg_node(e["system_id"], "Host", e["name"], "hosts", kind="external system", ip=e.get("ip"))
        org_edge(e["system_id"], "OPERATED_BY", e.get("operator"))
    for e in H["equipment"]:
        reg_node(e["equipment_id"], "Equipment", f"{e.get('label') or e['equipment_id']} ({e.get('type')})", "hosts", kind=e.get("type"))
        if e.get("site_id") in nodes:
            edge(e["equipment_id"], "PART_OF", e["site_id"])
        if e.get("served_by") in nodes:
            edge(e["equipment_id"], "MONITORED_BY", e["served_by"], internal=nodes[e["served_by"]]["internal"])
    cb = org_by_name.get("coastal bend power and water authority") or org_by_name.get("cbpwa")
    for u in H["users"]:
        hid = hidden(u.get("ot_account"), u["username"])
        uid = "user:" + u["username"]
        node(uid, "UserAccount", u["username"], internal=hid, kind=u.get("account_type"), department=u.get("department"))
        edge(uid, "LISTED_IN", "registry:hosts", internal=hid)
        idtok[u["username"]] = uid
        if u.get("ot_account"):
            idtok[u["ot_account"]] = uid
        if cb:
            edge(uid, "EMPLOYED_BY", cb, internal=hid)
        for hn in u.get("normal_hosts") or []:
            if hn in nodes:
                edge(uid, "USES_HOST", hn, internal=hid or nodes[hn]["internal"])
    for s in H["service_accounts"]:
        uid = "user:" + s["account"]
        node(uid, "UserAccount", s["account"], kind="service", department=s.get("owner_team"))
        edge(uid, "LISTED_IN", "registry:hosts")
        idtok[s["account"]] = uid
    TG = load("scada_tags")
    registry("scada_tags", "06_data_streams/scada_tags.json", len(TG["tags"]), "SCADA tags")
    groups = {}
    for t in TG["tags"]:
        groups.setdefault((t.get("site_id"), t.get("equipment_id")), []).append(t["tagname"])
    for (site, eq), tags in groups.items():
        gid = f"tags:{eq or site}"
        hid = hidden(eq, site)
        node(gid, "ScadaTagGroup", f"{len(tags)} tags on {eq or site}", internal=hid, tags=len(tags), site=site, tagnames=tags)
        edge(gid, "LISTED_IN", "registry:scada_tags", internal=hid)
        for t in tags:
            idtok[t] = gid
        tgt = eq if eq in nodes else (site if site in nodes else None)
        if tgt:
            edge(gid, "MEASURES", tgt)

    # ---------------------------------------------------------------- social accounts, payments entities
    P = load("personas")["personas"]
    registry("personas", "06_data_streams/personas.json", len(P), "Social accounts")
    for p in P:
        hid = hidden(p["handle"])
        sid = "acct:" + p["handle"]
        node(sid, "SocialAccount", p["handle"], internal=hid, kind=p.get("account_type"), language=p.get("language"))
        edge(sid, "LISTED_IN", "registry:personas", internal=hid)
        names.setdefault(p["handle"].lower(), sid)
        idtok[p["persona_id"]] = sid
        if p.get("home_area_id") in nodes:
            edge(sid, "LOCATED_AT", p["home_area_id"], internal=hid)
        org_edge(sid, "OPERATED_BY", p.get("display_name"))
    ER = load("entity_registry")
    registry("entity_registry", "06_data_streams/entity_registry.json", len(ER["vendors"]) + len(ER["accounts"]), "Vendors, contracts, insurers and accounts")
    for v in ER["vendors"]:
        if v.get("org_id") in nodes:
            edge(v["org_id"], "LISTED_IN", "registry:entity_registry", vendor_id=v["vendor_id"], internal=nodes[v["org_id"]]["internal"])
            idtok[v["vendor_id"]] = v["org_id"]
    for k in ("insurers", "brokers", "appraisers", "adjusting_firms"):
        for v in ER.get(k, []):
            if v.get("org_id") in nodes:
                idtok[v.get(next(x for x in v if x.endswith("_id")))] = v["org_id"]

    # ---------------------------------------------------------------- characters -> organisations
    for c in ctx["characters"].values():
        oid = org_by_name.get(norm(c["affiliation"].get("org")))
        if oid:
            edge(c["id"], "EMPLOYED_BY", oid, internal=(not c["public_facing"]) or nodes[oid]["internal"])
    for o in ctx["outlets"].values():
        oid = org_by_name.get(norm(o["name"]))
        if oid:
            edge(o["outlet_id"], "SAME_AS", oid)

    # ---------------------------------------------------------------- data streams, observations
    cat = json.load(open(os.path.join(REG, "stream_catalog.json"), encoding="utf-8"))["streams"]
    reg_key = {"vessels.json": "vessels", "terminal_registry.json": "terminals", "aircraft_registry.json": "aircraft", "drone_operators.json": "aircraft", "facility_registry.json": "facilities",
               "infrastructure_assets.json": "infrastructure", "sensor_registry.json": "sensors", "cad_units.json": "cad_units", "gw_host_registry.json": "hosts", "scada_tags.json": "scada_tags",
               "personas.json": "personas", "organizations.json": "organizations", "entity_registry.json": "entity_registry", "areas.json": "areas"}
    for s in cat:
        sid = "stream:" + s["stream_id"]
        node(sid, "DataStream", s.get("name") or s["stream_id"], path=s.get("path_glob"), format=s.get("format"), delivered=s.get("delivered"), cadence=s.get("cadence"))
        linked = False
        for r in s.get("ids_from_registry") or []:
            k = reg_key.get(os.path.basename(r.split(" ")[0]))
            if k:
                edge(sid, "RECORDS", "registry:" + k)
                linked = True
        if not linked:
            edge(sid, "RECORDS", "registry:areas" if s["stream_id"] in ("census",) else "registry:organizations", basis="issuing bodies and places named in the records")
    # matcher for names and ids in text
    name_keys = sorted(names, key=len, reverse=True)
    name_rx = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(k) for k in name_keys) + r")(?![A-Za-z0-9])", re.I) if name_keys else None
    id_keys = sorted((k for k in idtok if k and len(str(k)) >= 5), key=len, reverse=True)
    id_rx = re.compile(r"(?<![A-Za-z0-9.-])(" + "|".join(re.escape(str(k)) for k in id_keys) + r")(?![A-Za-z0-9])")

    def mentioned(text, with_ids):
        out = set()
        if name_rx:
            for m in name_rx.finditer(text):
                out.add(names[m.group(1).lower()])
        if with_ids:
            for m in id_rx.finditer(text):
                out.add(idtok[m.group(1)])
        return out

    obs = json.load(open(os.path.join(ROOT, "00_scenario", "canon_timeline.json"), encoding="utf-8"))["expected_observations"]["items"]
    seen = {}
    for o in obs:
        base = f"obs:{o['event_id']}:{o['stream']}"
        seen[base] = seen.get(base, 0) + 1
        oid = base if seen[base] == 1 else f"{base}:{seen[base]}"
        node(oid, "Observation", o["what"][:90], internal=True, what=o["what"], start_utc=o["start_utc"], end_utc=o["end_utc"], day=o["day"])
        edge(o["event_id"], "HAS_OBSERVATION", oid, internal=True)
        edge(oid, "EVIDENCED_BY", "stream:" + o["stream"], internal=True, start_utc=o["start_utc"], end_utc=o["end_utc"])
        for nid in mentioned(o["what"], True):
            edge(oid, "ABOUT_ENTITY", nid, internal=True)
    done = set()
    for e in ctx["msel"].values():
        for o in e.get("observed_in", []):
            k = (e["event_id"], o["stream"])
            if k not in done and "stream:" + o["stream"] in nodes:
                done.add(k)
                edge(e["event_id"], "OBSERVED_IN", "stream:" + o["stream"], internal=True)
        text = " ".join([e["description"]] + [x for x in (e.get("detection_artifacts") or []) if isinstance(x, str)] + [o["what"] for o in e.get("observed_in", [])])
        for nid in mentioned(text, True):
            edge(e["event_id"], "INVOLVES", nid, internal=True)
        for p in e.get("place_ids", []):
            if p in nodes and nodes[p]["type"] not in ("Place",):
                edge(e["event_id"], "INVOLVES", p, internal=True)

    # ---------------------------------------------------------------- stories and facts mention entities
    for s in stories:
        text = " ".join([s["headline"], s["dek"]] + s["body"])
        for nid in mentioned(text, False):
            edge(s["story_id"], "MENTIONS_ENTITY", nid, internal=nodes[nid]["internal"])
    for f in ctx["facts"].values():
        for nid in mentioned(f["statement"], False):
            edge(f["id"], "MENTIONS_ENTITY", nid, internal=nodes[nid]["internal"])

    # ---------------------------------------------------------------- scenario entities and old ids -> registry nodes
    for ent in ctx["entities"].values():
        for rid in ent.get("registry_ids") or []:
            if rid in nodes and rid != ent["id"]:
                edge(ent["id"], "SAME_AS", rid, internal=True)
        for t in ent.get("threads") or []:
            if t in nodes:
                edge(ent["id"], "INVOLVED_IN", t, internal=True)
    for p in ctx["places"].values():
        for rid in p.get("registry_ids") or []:
            if rid in nodes and rid != p["place_id"]:
                edge(p["place_id"], "SAME_AS", rid, internal=p["place_id"] in INTERNAL_PLACES_HINT)
    import glob as _g
    for fp in sorted(_g.glob(os.path.join(REG, "_internal", "*_truth.json"))):
        im = json.load(open(fp, encoding="utf-8")).get("id_migration")
        pairs = []

        def walk(x):
            if isinstance(x, dict):
                if isinstance(x.get("old"), str) and isinstance(x.get("new"), (str, list)):
                    for nw in (x["new"] if isinstance(x["new"], list) else [x["new"]]):
                        pairs.append((x["old"], nw))
                for k, v in x.items():
                    if isinstance(v, str):
                        pairs.append((k, v))
                    elif isinstance(v, dict) and isinstance(v.get("new") or v.get("new_vessel_id"), str):
                        pairs.append((k, v.get("new") or v.get("new_vessel_id")))
                    else:
                        walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(im)
        for old, new in pairs:
            new_id = new.split(" ")[0] if isinstance(new, str) else None
            tgt = new_id if new_id in nodes else idtok.get(new_id) or ("user:" + new_id[5:] if new_id and new_id.startswith("user:") and "user:" + new_id[5:] in nodes else None)
            if isinstance(tgt, str) and tgt in nodes and old != tgt and len(old) < 60:
                oid = "old:" + old
                if oid not in nodes:
                    node(oid, "OldId", old, internal=True, source=os.path.basename(fp))
                edge(oid, "SAME_AS", tgt, internal=True)

    # ---------------------------------------------------------------- answer keys
    ak = json.load(open(os.path.join(ROOT, "06_answer_key", "answer_key.json"), encoding="utf-8"))
    for k in ak.get("threads", []):
        kid = "key:" + k["thread_id"]
        node(kid, "AnswerKeyPath", k["question"], internal=True, difficulty=k["difficulty"], conclusion=k["conclusion"], key_joins=k["key_joins"])
        edge(kid, "SOLVES", k["thread_id"], internal=True)
        for s in k["steps"]:
            oid = f"obs:{s['observation']['event_id']}:{s['observation']['stream']}"
            if oid in nodes:
                edge(kid, "HAS_STEP", oid, internal=True, n=s["n"], join_to_next=s.get("join_to_next"))
        for st in k["streams"]:
            edge(kid, "USES_STREAM", "stream:" + st, internal=True)


INTERNAL_PLACES_HINT = set()
