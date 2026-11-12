"""Define, check and (optionally) copy the package that hackathon participants receive.

    python3 scripts/build_delivery.py                      write 11_hackathon/delivery_manifest.json and EXCLUDED.md
    python3 scripts/build_delivery.py --resume --budget=140   same, in pieces (hashing and scanning 1 GB takes a few minutes)
    python3 scripts/build_delivery.py --copy <dir>         also copy the package to <dir>
    python3 scripts/build_delivery.py --copy <dir> --until 2027-09-20
                                                           staged release: only rows time-stamped before that date (UTC)
    python3 scripts/build_delivery.py --streams ais,cad_911 ...   restrict to some streams (for testing)

What ships
    data/        every delivered stream in 06_data_streams/stream_catalog.json (the files under 05_other_sources/)
    registries/  the participant-facing registries in 06_data_streams/*.json (never _internal/), with build
                 provenance removed (copies are written to 11_hackathon/package_extras/registries/)
    schemas/     the schema files with generator and scenario notes removed, and a stream catalogue
                 without the fields that say which storylines rely on which stream
    reference/   real-world geography from 99_reference/geo (GeoJSON and the SOURCES files)
    docs/        11_hackathon/PLAYER_BRIEF.md, DATA_GUIDE.md and DATA_TABLES.md (the last is written by this
                 script from the files themselves: counts, time spans and columns of every data file)

What never ships is listed, with reasons, in 11_hackathon/EXCLUDED.md (written by this script).
News reaches teams only through the newsroom (web pages, RSS, API), which releases stories on the
exercise clock; the story files themselves are not in the package.

Checks (the run fails, exit 1, if any of these finds something)
    * internal ids or notes anywhere in the package: event ids, "MSEL", "answer key", "ground truth",
      storyline ("thread") fields, paths into _internal/ or the generators, the internal code name
    * scenario-day notation (D+12 and the like) anywhere
    * answer-revealing column names in any CSV header
    * never-public terms from 02_public_record/restricted_terms.json in public-voice files
      (posts, statements, alerts, broadcast logs, dispatch narratives, reports) and in docs and schemas
    * date-gated terms in official statements, alerts and broadcast logs before their public day (row by row);
      the same in posts, dispatch narratives, reports and scene descriptions is listed for review in
      11_hackathon/delivery_warnings.json instead (a company's own account or the people spreading a
      link may legitimately use a name before the news does)

Staged release (--until) and its limits
    Row-oriented files are cut on their main time column (table below; UTC, or the file's local clock
    where the column is local). Zeek logs are cut by day folder, satellite scenes by scene time, the
    advisory file by advisory time. Tables with no time column (sensor lists, registries, census,
    geography) ship whole. Records that keep being updated after they are opened (work orders, port
    calls, dispatch records with clearance times, claims, contracts) ship whole once their opening
    time is before the cut, so they can show a later status: cut after the period you want to hide,
    or release those tables later.
"""
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "11_hackathon")
EXTRAS = os.path.join(OUT, "package_extras")
CACHE = os.path.join(OUT, "_cache", "delivery_scan.json")
D0 = dt.date(2027, 9, 14)

REGISTRIES = ["vessels", "terminal_registry", "aircraft_registry", "drone_operators", "facility_registry", "infrastructure_assets",
              "sensor_registry", "cad_units", "areas", "gw_host_registry", "scada_tags", "personas", "organizations", "entity_registry"]
DOCS = ["PLAYER_BRIEF.md", "DATA_GUIDE.md"]
NOT_SHIPPED_STREAMS = {"news": "stories are released by the newsroom on the exercise clock (web pages, RSS, API), not as a file"}

EXCLUDED = [
    ("00_scenario/", "the hidden timeline, event list, storyline definitions and canon decisions"),
    ("01_characters/", "character sheets, including people who are not public"),
    ("02_public_record/", "the public record with its links to hidden events (teams get the dated statements in data/press_releases/)"),
    ("03_news/ and 08_release/", "story sources and the full story file: news reaches teams through the newsroom only, on the clock"),
    ("04_knowledge_graph/", "both graph views: the internal one holds the answers, the public one holds every story at once"),
    ("06_answer_key/", "the answer keys"),
    ("06_data_streams/_internal/", "internal notes on entities and old-id maps"),
    ("06_data_streams/stream_catalog.json", "lists which storylines rely on each stream; a copy without those fields ships as schemas/stream_catalogue.json"),
    ("06_data_streams/schemas/00_schema_index.json", "superseded by schemas/stream_catalogue.json"),
    ("07_validation/", "audit reports, findings and check results"),
    ("09_shared_state_timeline/", "the map viewer and state timeline: they include the game master's truth layers"),
    ("10_news_sites/", "the newsroom server is run by the game master; teams use it over the network"),
    ("11_hackathon/GAME_MASTER_GUIDE.md", "for the game master"),
    ("99_reference/geo/_parts, _cache, position_rules*", "working files of the geography build and the validator's rule list"),
    ("_thread_designs/, scenarios/, _versions/", "design files, the layered scenario definitions and old snapshots"),
    ("scripts/", "generators, probes and checks"),
]

# ---------------------------------------------------------------------------------- checks
INTERNAL = re.compile(rb"GW-EVT-\d|\bEVT-\d{3,4}\b|\bMSEL\b|answer[ _]key|ground[ _]truth|truth_event|canon_timeline|_internal/|scripts/streams|probes_[a-z]|"
                      rb"\"threads?\"\s*:|\bKESTREL\b|STATE-X|GridWater|\bCHR-\d{3}\b|\bARC-[A-Z]{3}")
# placeholder-style ids from the scenario design: never in public-voice text, docs or schemas (a registry may carry one as a part number)
DESIGN_IDS = re.compile(rb"BANK-SYN|ASN-SYN|SOC-ACC|MMSI-SYN|UEI-SYN|PIID-SYN|ICAO-SYN|NSN-SYN|SYN-PER")
DAY_NOTATION = re.compile(rb"(?<![A-Za-z0-9_\-/.])D[+-]\d{1,3}(?![0-9A-Za-z_\-])|truth_event_id")
BANNED_COLUMNS = re.compile(r"attack|malicious|truth|phase_label|is_fake|is_fraud|ground_truth|thread|label_|_label$|anomaly_flag|compromised", re.I)
OFFICIAL_VOICE = re.compile(r"^data/(press_releases/|public_health/eas_broadcasts|broadcast/)")
PUBLIC_VOICE = re.compile(r"^data/(social_media/|press_releases/|public_health/eas_broadcasts|broadcast/|911/|sar/|shelters/|satellite/|drone_detections/sighting_reports)|^docs/|^schemas/")


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def restricted():
    never, gated = [], []
    for t in load("02_public_record/restricted_terms.json")["terms"]:
        p = t["pattern"]
        if t["public_from_day"] is None:
            if p.startswith(("\\bEVT", "BANK-SYN", "\\bD[")):
                continue                                   # covered by INTERNAL / DAY_NOTATION, minus ids that are public by design
            never.append(p)
        else:
            gated.append((p, t["public_from_day"]))
    return never, gated


# ---------------------------------------------------------------------------------- time columns
TIME_COLUMNS = ["time_utc", "timestamp_utc", "Timestamp", "timestamp", "BaseDateTime", "ObsDateTime", "time_position", "IssuedAt_UTC", "issued_utc",
                "delivered_utc", "air_time_utc", "received_utc", "launch_utc", "event_utc", "login_utc", "start_utc", "takeoff_utc", "survey_time_utc",
                "source_received_utc", "lookup_utc", "returned_utc", "reported_utc", "call_received_dttm", "Arrive_Date_Time",
                "call_time_local", "pickup_local", "opened_local", "Report_Date", "report_date", "date_local", "date_utc", "Date_GMT", "sample_date",
                "ASMT_DATE", "survey_date", "invoice_date", "award_date", "action_date", "filing_date", "transaction_date", "filed_date", "loss_date",
                "reported_date", "noa_submitted_datetime", "booking_date", "activation_date", "registration_date", "issued_local", "created_at"]
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def norm_time(v):
    """Sortable 'YYYY-MM-DDTHH:MM:SS' from the formats used in the streams, or None."""
    v = str(v).strip()
    if not v:
        return None
    if re.fullmatch(r"\d{9,11}(\.\d+)?", v):
        return dt.datetime.fromtimestamp(float(v), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?))?", v)
    if m:
        t = m.group(2) or "00:00:00"
        return f"{m.group(1)}T{t if len(t) == 8 else t + ':00'}"
    m = re.match(r"\w{3} (\w{3}) (\d{2}) (\d{2}:\d{2}:\d{2}) \+0000 (\d{4})", v)      # Twitter created_at
    if m:
        return f"{m.group(4)}-{MONTHS[m.group(1)]:02d}-{m.group(2)}T{m.group(3)}"
    return None


def time_col(header):
    for c in TIME_COLUMNS:
        if c in header:
            return c
    return None


def time_indices(header):
    """Indices of every known time column in a header, in priority order (a row uses the first one it has a value in)."""
    return [header.index(c) for c in TIME_COLUMNS if c in header]


def row_time(idx, row):
    for i in idx:
        if i < len(row):
            t = norm_time(row[i])
            if t:
                return t
    return None


def obj_time(o):
    return norm_time(o.get("lookup_utc") or o.get("returned_utc") or o.get("created_at") or o.get("issued_local") or "")


def day_of(tnorm):
    return (dt.date.fromisoformat(tnorm[:10]) - D0).days


# ---------------------------------------------------------------------------------- package definition
def schema_clean(obj, removed):
    """Drop generator/scenario notes from a schema; record what was removed."""
    DROP = {"generator", "generator_reference", "scenario_notes", "probes", "verified", "research_status", "entity_catalogs_built", "checks", "check"}
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in DROP or re.search(r"generator_|scenario|internal|probe|canon|truth|thread", k, re.I) and k not in ("generator_last_test_date",):
                removed.append(k)
                continue
            if isinstance(v, str) and (INTERNAL.search(v.encode()) or DAY_NOTATION.search(v.encode()) or re.search(r"scripts/|00_scenario|check_geo|check_streams", v)):
                removed.append(k)
                continue
            out[k] = schema_clean(v, removed)
        return out
    if isinstance(obj, list):
        return [schema_clean(x, removed) for x in obj if not (isinstance(x, str) and (INTERNAL.search(x.encode()) or re.search(r"scripts/|00_scenario", x)))]
    return obj


def participant_catalogue():
    cat = load("06_data_streams/stream_catalog.json")
    out = {"about": "Data streams in this package. Times are UTC unless a column name says local; local time is US Central "
                    "(UTC-5 until 2027-11-07 07:00Z, UTC-6 after). Paths are relative to the package root.",
           "streams": []}
    for s in cat["streams"]:
        if not s.get("delivered") or s["stream_id"] in NOT_SHIPPED_STREAMS:
            continue
        extra = s.get("additional_files") or []
        out["streams"].append({
            "stream_id": s["stream_id"], "name": s["name"],
            "path": s["path_glob"].replace("05_other_sources/", "data/"),
            "more_files": [(a if isinstance(a, str) else a.get("path") or a.get("path_glob") or "").replace("05_other_sources/", "data/") for a in extra],
            "format": s.get("format"), "key_columns": s.get("key_columns"),
            "ids_join_to": [os.path.basename(r) for r in (s.get("ids_from_registry") or []) if r.startswith("06_data_streams/")],
            "cadence": s.get("cadence") if not DAY_NOTATION.search(str(s.get("cadence")).encode()) else None,
        })
    return out


def package_paths(text):
    """Rewrite project paths to package paths."""
    return (text.replace("05_other_sources/", "data/").replace("06_data_streams/schemas/", "schemas/").replace("06_data_streams/", "registries/")
            .replace("99_reference/geo/", "reference/geo/"))


def readme_clean(text):
    """A stream folder's README without its 'how it is produced' section or any line that points at project scripts."""
    out, skip = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            skip = bool(re.search(r"how it is produced|generat|validation|checks?$", line, re.I))
        if skip or re.search(r"scripts/|check_geo|check_streams|probes?_|generator|deterministic", line):
            continue
        out.append(line)
    return package_paths("\n".join(out).rstrip() + "\n")


def write_extras():
    os.makedirs(os.path.join(EXTRAS, "schemas"), exist_ok=True)
    notes = []
    open(os.path.join(EXTRAS, "schemas", "stream_catalogue.json"), "w", encoding="utf-8").write(
        package_paths(json.dumps(participant_catalogue(), indent=1, ensure_ascii=False)))
    for fp in sorted(glob.glob(os.path.join(ROOT, "05_other_sources", "*", "README.md"))):
        rel = os.path.relpath(fp, os.path.join(ROOT, "05_other_sources"))
        dst = os.path.join(EXTRAS, "readmes", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "w", encoding="utf-8").write(readme_clean(open(fp, encoding="utf-8").read()))
    # registries: the same content, without build provenance (which script made the file, project paths)
    os.makedirs(os.path.join(EXTRAS, "registries"), exist_ok=True)

    def strip_provenance(o):
        if isinstance(o, dict):
            return {k: strip_provenance(v) for k, v in o.items() if k not in ("generated_by", "generator", "generated")}
        if isinstance(o, list):
            return [strip_provenance(x) for x in o]
        if isinstance(o, str):
            return re.sub(r"\s*\(scripts/geo\.py[^)]*\)", "", o).replace("with scripts/geo.py", "against the geography reference").replace("scripts/geo.py", "the geography reference")
        return o

    for r in REGISTRIES:
        d = strip_provenance(load(f"06_data_streams/{r}.json"))
        open(os.path.join(EXTRAS, "registries", r + ".json"), "w", encoding="utf-8").write(package_paths(json.dumps(d, indent=1, ensure_ascii=False)))
    for fp in sorted(glob.glob(os.path.join(ROOT, "06_data_streams", "schemas", "*.json"))):
        name = os.path.basename(fp)
        if name == "00_schema_index.json":
            continue
        removed = []
        clean = schema_clean(json.load(open(fp, encoding="utf-8")), removed)
        open(os.path.join(EXTRAS, "schemas", name), "w", encoding="utf-8").write(package_paths(json.dumps(clean, indent=1, ensure_ascii=False)))
        if removed:
            notes.append((name, sorted(set(removed))))
    return notes


def package_files(streams_filter):
    """[(package_path, source_path, kind, stream_id)]"""
    cat = load("06_data_streams/stream_catalog.json")
    items, seen = [], set()
    for s in cat["streams"]:
        sid = s["stream_id"]
        if not s.get("delivered") or sid in NOT_SHIPPED_STREAMS or (streams_filter and sid not in streams_filter):
            continue
        pats = [s["path_glob"]] + [(a if isinstance(a, str) else a.get("path") or a.get("path_glob") or "") for a in (s.get("additional_files") or [])]
        for pat in pats:
            if not pat.startswith("05_other_sources/"):
                continue
            for fp in sorted(glob.glob(os.path.join(ROOT, pat), recursive=True)):
                rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
                if os.path.isfile(fp) and rel not in seen and "/_consolidated/" not in rel:
                    seen.add(rel)
                    items.append(("data/" + rel[len("05_other_sources/"):], rel, "stream", sid))
    # every other file in a delivered stream's folder that the catalogue did not name (READMEs, lookup tables)
    for folder in sorted({os.path.dirname(i[1]) for i in items}):
        for fp in sorted(glob.glob(os.path.join(ROOT, folder, "*"))):
            rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
            if os.path.isfile(fp) and rel not in seen and not streams_filter:
                seen.add(rel)
                src = rel
                if os.path.basename(rel) == "README.md":       # ship the copy without production notes
                    src = os.path.relpath(os.path.join(EXTRAS, "readmes", rel[len("05_other_sources/"):]), ROOT).replace(os.sep, "/")
                items.append(("data/" + rel[len("05_other_sources/"):], src, "stream-extra", ""))
    if streams_filter:
        return items
    for r in REGISTRIES:
        items.append((f"registries/{r}.json", f"11_hackathon/package_extras/registries/{r}.json", "registry", ""))
    for fp in sorted(glob.glob(os.path.join(EXTRAS, "schemas", "*.json"))):
        items.append(("schemas/" + os.path.basename(fp), os.path.relpath(fp, ROOT).replace(os.sep, "/"), "schema", ""))
    for fp in sorted(glob.glob(os.path.join(ROOT, "99_reference", "geo", "*.geojson")) + glob.glob(os.path.join(ROOT, "99_reference", "geo", "SOURCES_*.md"))):
        items.append(("reference/geo/" + os.path.basename(fp), os.path.relpath(fp, ROOT).replace(os.sep, "/"), "reference", ""))
    for d in DOCS:
        if os.path.exists(os.path.join(OUT, d)):
            items.append(("docs/" + d, "11_hackathon/" + d, "doc", ""))
    return items


# ---------------------------------------------------------------------------------- scanning
def scan_file(pkg, src, never_rx, gated):
    """Problems found in one file (list of strings)."""
    full = os.path.join(ROOT, src)
    with open(full, "rb") as fh:
        data = fh.read()
    probs = []
    m = INTERNAL.search(data)
    if m:
        probs.append(f"internal id or note: {m.group(0).decode('utf-8', 'replace')!r}")
    m = DAY_NOTATION.search(data)
    if m:
        probs.append(f"scenario-day notation: {m.group(0).decode()!r} near {data[max(0, m.start() - 40):m.end() + 20].decode('utf-8', 'replace')!r}")
    if src.endswith(".csv"):
        header = data[:data.find(b"\n")].decode("utf-8", "replace").strip().split(",")
        bad = [c for c in header if BANNED_COLUMNS.search(c)]
        if bad:
            probs.append(f"answer-revealing column names: {bad}")
    if PUBLIC_VOICE.search(pkg):
        m = DESIGN_IDS.search(data)
        if m:
            probs.append(f"design placeholder id in public-voice file: {m.group(0).decode()!r}")
        m = never_rx.search(data)
        if m:
            probs.append(f"never-public term in public-voice file: {m.group(0).decode('utf-8', 'replace')!r}")
        if pkg.startswith("data/"):
            for pat, day in gated:
                rx = re.compile(pat.encode(), re.I)
                if rx.search(data):
                    early = first_early(full, rx, day)
                    if early:
                        tag = "" if OFFICIAL_VOICE.search(pkg) else "WARNING "
                        probs.append(f"{tag}date-gated term /{pat}/ before its public day ({day}): {early}")
    return probs


def first_early(full, rx, day):
    """First row that carries the term with a time stamp before the term's public day, or None."""
    if full.endswith(".jsonl"):
        with open(full, encoding="utf-8") as fh:
            for line in fh:
                if rx.search(line.encode()):
                    o = json.loads(line)
                    t = obj_time(o)
                    if t and day_of(t) < day - 1:          # one day of slack for UTC vs local dates
                        return f"{t} {line[:120]!r}"
    elif full.endswith(".csv"):
        with open(full, encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            header = next(rd, [])
            idx = time_indices(header)
            if not idx:
                return None
            for row in rd:
                if rx.search(",".join(row).encode()):
                    t = row_time(idx, row)
                    if t and day_of(t) < day - 1:
                        return f"{t} {','.join(row)[:120]!r}"
    elif full.endswith(".json"):
        o = json.load(open(full, encoding="utf-8"))
        t = norm_time(((o.get("properties") or {}).get("datetime")) or "") if isinstance(o, dict) else None
        if t and day_of(t) < day - 1:
            return f"{t} {os.path.basename(full)}"
    return None


def file_facts(src, data):
    """Columns, row count and first/last time stamp of one data file (for DATA_TABLES.md)."""
    f = {}
    try:
        if src.endswith(".csv"):
            lines = data.split(b"\n")
            header = next(csv.reader([lines[0].decode("utf-8", "replace").lstrip("\ufeff")]))
            rows = [l for l in (lines[1], lines[-1] if lines[-1].strip() else lines[-2]) if l.strip()] if len(lines) > 2 else []
            f = {"cols": header, "rows": max(0, data.count(b"\n") - (1 if data.endswith(b"\n") else 0))}
            tc, idx = time_col(header), time_indices(header)
            if tc and rows:
                vals = [next(csv.reader([r.decode("utf-8", "replace")])) for r in rows]
                ts_ = [t for t in (row_time(idx, v) for v in vals) if t]
                f.update(tcol=tc, t0=min(ts_) if ts_ else None, t1=max(ts_) if ts_ else None)
        elif src.endswith(".jsonl"):
            lines = [l for l in data.split(b"\n") if l.strip()]
            f = {"rows": len(lines)}
            if lines:
                a, b = json.loads(lines[0]), json.loads(lines[-1])
                f["cols"] = list(a.keys())
                f.update(tcol=next((k for k in ("lookup_utc", "returned_utc", "created_at", "issued_local") if k in a), None), t0=obj_time(a), t1=obj_time(b))
        elif src.endswith(".log"):
            lines = data.split(b"\n")
            cols = next((l.decode().split("\t")[1:] for l in lines if l.startswith(b"#fields")), [])
            day = os.path.basename(os.path.dirname(src))
            f = {"cols": cols, "rows": sum(1 for l in lines if l and not l.startswith(b"#")), "tcol": "ts", "t0": day + "T00:00:00", "t1": day + "T23:59:59"}
        elif src.endswith(".json"):
            o = json.loads(data)
            if isinstance(o, dict):
                f = {"cols": list(o.keys())}
                t = norm_time(((o.get("properties") or {}).get("datetime")) or "") if isinstance(o.get("properties"), dict) else None
                if t:
                    f.update(tcol="properties.datetime", t0=t, t1=t, rows=1)
                if isinstance(o.get("advisories"), list) and o["advisories"]:
                    ts_ = sorted(t for t in (norm_time(a.get("issued_utc") or "") for a in o["advisories"]) if t)
                    f.update(tcol="advisories[].issued_utc", rows=len(o["advisories"]), t0=ts_[0] if ts_ else None, t1=ts_[-1] if ts_ else None)
    except Exception as e:                                  # facts are documentation; never block the package on them
        f["error"] = str(e)[:80]
    return f


def group_name(pkg):
    """Collapse per-month / per-entity file names into one pattern for the tables."""
    d, base = os.path.split(pkg)
    if "/zeek/" in pkg:
        return "data/network_logs/zeek/<YYYY-MM-DD>/" + base
    if d.endswith("social_media") and not base.startswith("_"):
        return d + "/<account or group>.jsonl"
    if d == "data/satellite" and base != "catalog.json":
        return d + "/<scene id>.json"
    if d.endswith("avl"):
        return d + "/avl_<YYYY-MM>_<agency>.csv"
    b = re.sub(r"\d{4}-\d{2}|(?<=_)\d{6}(?=[._])", "<month>", base)
    b = re.sub(r"^(aqs_air_quality|water_quality|gauge|ed_visits)_[A-Za-z0-9\-]+\.csv$", r"\1_<id>.csv", b)
    b = re.sub(r"^[A-Z0-9]+(_ASOS)?_observations\.csv$", r"<station>\1_observations.csv", b)
    return d + "/" + b


def write_data_tables(manifest, facts):
    cat = load("06_data_streams/stream_catalog.json")
    names = {s["stream_id"]: s["name"] for s in cat["streams"]}
    by_stream = {}
    for m in manifest:
        if m["kind"] == "stream":
            by_stream.setdefault(m["stream"], {}).setdefault(group_name(m["path"]), []).append(m)
    out = ["# Data tables", "", "Every data file in the package: where it is, how much there is, its time span and its columns.",
           "Written by the package builder from the files themselves, so it matches what you received.", "",
           "Times are UTC unless the column name says local. `<month>` in a file name means one file per calendar month.", ""]
    for s in cat["streams"]:
        sid = s["stream_id"]
        if sid not in by_stream:
            continue
        out += [f"## {names[sid]} (`{sid}`)", "", "| Files | Count | Size | Records | Time column | First | Last |", "|---|---|---|---|---|---|---|"]
        cols_seen = []
        for pat, ms in by_stream[sid].items():
            fs = [facts.get(m["source"], {}) for m in ms]
            rows = sum(f.get("rows") or 0 for f in fs)
            t0s = sorted(f["t0"] for f in fs if f.get("t0")); t1s = sorted(f["t1"] for f in fs if f.get("t1"))
            tcol = next((f.get("tcol") for f in fs if f.get("tcol")), "")
            size = sum(m["bytes"] for m in ms) / 1e6
            out.append(f"| `{pat}` | {len(ms)} | {size:.1f} MB | {rows:,} | {('`' + tcol + '`') if tcol else 'none (static table)'} | "
                       f"{t0s[0].replace('T', ' ')[:16] if t0s else ''} | {t1s[-1].replace('T', ' ')[:16] if t1s else ''} |")
            cols = next((f.get("cols") for f in fs if f.get("cols")), None)
            if cols:
                cols_seen.append((pat, cols))
        out.append("")
        for pat, cols in cols_seen:
            out.append(f"`{os.path.basename(pat)}` columns: " + ", ".join(f"`{c}`" for c in cols))
            out.append("")
    open(os.path.join(OUT, "DATA_TABLES.md"), "w", encoding="utf-8").write("\n".join(out))


def sha256(full):
    h = hashlib.sha256()
    with open(full, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------------- copying
def copy_until(src_full, dst_full, until):
    """Copy one file, keeping only rows before `until` ('YYYY-MM-DDT00:00:00'). Returns a note for the manifest."""
    name = os.path.basename(src_full)
    if until is not None and src_full.endswith(".log") and os.path.basename(os.path.dirname(src_full)) >= until[:10]:
        return None                                        # Zeek day folder on or after the cut
    os.makedirs(os.path.dirname(dst_full), exist_ok=True)
    if until is None:
        shutil.copyfile(src_full, dst_full)
        return "complete"
    if src_full.endswith(".csv"):
        with open(src_full, encoding="utf-8", errors="replace", newline="") as fh:
            rd = csv.reader(fh)
            header = next(rd, None)
            tc = time_col(header or [])
            if not tc:
                shutil.copyfile(src_full, dst_full)
                return "no time column: complete"
            idx, kept = time_indices(header), 0
            with open(dst_full, "w", encoding="utf-8", newline="") as out:
                w = csv.writer(out)
                w.writerow(header)
                for row in rd:
                    t = row_time(idx, row)
                    if t is None or t < until:
                        w.writerow(row); kept += 1
        return f"rows before {until[:10]} on {tc}: {kept}"
    if src_full.endswith(".jsonl"):
        kept = 0
        with open(src_full, encoding="utf-8") as fh, open(dst_full, "w", encoding="utf-8") as out:
            for line in fh:
                o = json.loads(line)
                t = obj_time(o)
                if t is None or t < until:
                    out.write(line); kept += 1
        return f"records before {until[:10]}: {kept}"
    if src_full.endswith(".log"):                          # Zeek: one folder per UTC day
        day = os.path.basename(os.path.dirname(src_full))
        if day < until[:10]:
            shutil.copyfile(src_full, dst_full)
            return "day folder before the cut"
        return None
    if src_full.endswith(".json"):
        o = json.load(open(src_full, encoding="utf-8"))
        if name == "nhc_advisories.json":
            for key, tk in (("advisories", "issued_utc"), ("best_track", "time_utc")):
                if isinstance(o.get(key), list):
                    o[key] = [a for a in o[key] if (norm_time(a.get(tk) or a.get("valid_utc") or a.get("time") or "") or "") < until]
            o["count"] = len(o.get("advisories", []))
            json.dump(o, open(dst_full, "w", encoding="utf-8"), indent=1)
            return f"advisories before {until[:10]}: {o['count']}"
        if name == "catalog.json" and isinstance(o.get("links"), list):
            keep = []
            for l in o["links"]:
                item = os.path.join(os.path.dirname(src_full), os.path.basename(l.get("href", "")))
                if l.get("rel") != "item" or not os.path.exists(item):
                    keep.append(l)
                else:
                    t = norm_time((json.load(open(item, encoding="utf-8")).get("properties") or {}).get("datetime") or "")
                    if t is None or t < until:
                        keep.append(l)
            o["links"] = keep
            json.dump(o, open(dst_full, "w", encoding="utf-8"), indent=1)
            return "links to scenes before the cut"
        t = norm_time(((o.get("properties") or {}).get("datetime")) or "") if isinstance(o, dict) else None
        if t is None or t < until:
            shutil.copyfile(src_full, dst_full)
            return "scene before the cut" if t else "complete"
        return None
    shutil.copyfile(src_full, dst_full)
    return "complete"


# ---------------------------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    def opt(name):
        for i, a in enumerate(args):
            if a == name and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(name + "="):
                return a.split("=", 1)[1]
        return None
    copy_dir, until = opt("--copy"), opt("--until")
    streams_filter = set(opt("--streams").split(",")) if opt("--streams") else None
    budget = float(opt("--budget") or 1e9)
    resume = "--resume" in args
    if until:
        dt.date.fromisoformat(until)
        until = until + "T00:00:00"
    t0 = time.time()

    schema_notes = write_extras()
    items = package_files(streams_filter)
    never, gated = restricted()
    never_rx = re.compile(("|".join(f"(?:{p})" for p in never)).encode(), re.I)

    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    cache = json.load(open(CACHE)) if resume and os.path.exists(CACHE) else {}
    problems, warnings, manifest, pending, dirty, facts = [], [], [], 0, 0, {}
    for pkg, src, kind, sid in items:
        full = os.path.join(ROOT, src)
        st = os.stat(full)
        key = f"v3|{src}|{st.st_size}|{int(st.st_mtime)}"
        c = None if src.startswith("11_hackathon/") else cache.get(key)     # derived files and docs are small: always re-read
        if c is None:
            if time.time() - t0 > budget and not src.startswith("11_hackathon/"):
                pending += 1
                continue
            c = {"sha256": sha256(full), "problems": scan_file(pkg, src, never_rx, gated)}
            if kind == "stream":
                with open(full, "rb") as fh:
                    c["facts"] = file_facts(src, fh.read())
            if src.startswith("11_hackathon/"):
                pass
            else:
                cache[key] = c
                dirty += 1
            if resume and dirty % 100 == 0:
                json.dump(cache, open(CACHE, "w"))
        manifest.append({"path": pkg, "source": src, "kind": kind, "stream": sid, "bytes": st.st_size, "sha256": c["sha256"]})
        facts[src] = c.get("facts", {})
        problems += [f"{pkg}: {p}" for p in c["problems"] if not p.startswith("WARNING ")]
        warnings += [f"{pkg}: {p[8:]}" for p in c["problems"] if p.startswith("WARNING ")]
    if resume and dirty:
        json.dump(cache, open(CACHE, "w"))
    if pending:
        print(f"INCOMPLETE: {pending} of {len(items)} files still to hash and scan (run again with --resume)")
        sys.exit(2)

    total = sum(m["bytes"] for m in manifest)
    if not streams_filter:
        write_data_tables(manifest, facts)
        if not any(m["path"] == "docs/DATA_TABLES.md" for m in manifest):
            fp = os.path.join(OUT, "DATA_TABLES.md")
            manifest.append({"path": "docs/DATA_TABLES.md", "source": "11_hackathon/DATA_TABLES.md", "kind": "doc", "stream": "",
                             "bytes": os.path.getsize(fp), "sha256": sha256(fp)})
            problems += [f"docs/DATA_TABLES.md: {p}" for p in scan_file("docs/DATA_TABLES.md", "11_hackathon/DATA_TABLES.md", never_rx, gated)]
            total += os.path.getsize(fp)
        json.dump({"about": "Files a participant receives. Paths are relative to the package root; 'source' is where each file lives in the project.",
                   "files": len(manifest), "bytes": total, "by_kind": {k: sum(1 for m in manifest if m["kind"] == k) for k in sorted({m["kind"] for m in manifest})},
                   "manifest": manifest}, open(os.path.join(OUT, "delivery_manifest.json"), "w", encoding="utf-8"), indent=1)
        with open(os.path.join(OUT, "EXCLUDED.md"), "w", encoding="utf-8") as fh:
            fh.write("# What participants do not receive\n\nWritten by `scripts/build_delivery.py`. Internal: for the game master.\n\n| Withheld | Why |\n|---|---|\n")
            for path, why in EXCLUDED:
                fh.write(f"| `{path}` | {why} |\n")
            for sid, why in NOT_SHIPPED_STREAMS.items():
                fh.write(f"| stream `{sid}` | {why} |\n")
            fh.write("\n## Removed from the schema files before they ship\n\n")
            for name, keys in schema_notes:
                fh.write(f"- `{name}`: {', '.join(keys)}\n")
            fh.write("\n## Staged release\n\n`--until YYYY-MM-DD` cuts row-oriented files on their main time column. Tables that are updated after "
                     "a record is opened (work orders, port calls, dispatch records, claims, contracts) ship whole once opened; tables with no time "
                     "column ship whole. See the docstring of `scripts/build_delivery.py`.\n")

    if not streams_filter:
        json.dump({"about": "Date-gated names found in posts, dispatch narratives, reports or scene descriptions before the day the news first reports "
                            "them. Official statements, alerts and broadcast logs are checked strictly (a hit there fails the run). Elsewhere a hit is "
                            "often legitimate (a company's own account, the people spreading a link, a berth named on a chart), so it is listed here "
                            "for the game master to review rather than blocked.", "count": len(warnings), "warnings": warnings},
                  open(os.path.join(OUT, "delivery_warnings.json"), "w", encoding="utf-8"), indent=1)
    print(f"package: {len(manifest)} files, {total / 1e6:.0f} MB" + (f" (streams: {','.join(sorted(streams_filter))})" if streams_filter else ""))
    for k in sorted({m["kind"] for m in manifest}):
        print(f"  {k:<13} {sum(1 for m in manifest if m['kind'] == k):>5} files  {sum(m['bytes'] for m in manifest if m['kind'] == k) / 1e6:>8.1f} MB")
    if problems:
        print(f"\nFAILED: {len(problems)} problem(s): nothing should ship until these are fixed")
        for p in problems[:40]:
            print("  -", p[:300])
        sys.exit(1)
    if warnings:
        print(f"review: {len(warnings)} early mention(s) of date-gated names outside official statements (11_hackathon/delivery_warnings.json)")
    print("checks: no internal ids or notes, no scenario-day notation, no answer-revealing columns, no never-public or early gated terms in public-voice files")

    if copy_dir:
        copied, out_manifest = 0, []
        if not streams_filter:
            items = items + [("docs/DATA_TABLES.md", "11_hackathon/DATA_TABLES.md", "doc", "")]
        for pkg, src, kind, sid in items:
            dst = os.path.join(copy_dir, pkg)
            note = copy_until(os.path.join(ROOT, src), dst, until if kind in ("stream", "stream-extra") else None)
            if note is None:
                continue
            copied += 1
            out_manifest.append({"path": pkg, "kind": kind, "stream": sid, "bytes": os.path.getsize(dst), "sha256": sha256(dst), "content": note})
        json.dump({"cut": until[:10] if until else None, "files": len(out_manifest), "manifest": out_manifest},
                  open(os.path.join(copy_dir, "MANIFEST.json"), "w", encoding="utf-8"), indent=1)
        print(f"copied {copied} files to {copy_dir}" + (f" (rows before {until[:10]})" if until else ""))
    print("PASS")


if __name__ == "__main__":
    main()
