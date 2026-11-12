"""Check that the stream catalogue and the schema files describe what is on disk.

    python3 scripts/check_catalog.py

1. Every delivered stream's path_glob (and additional_files globs) in 06_data_streams/stream_catalog.json matches files.
2. Every column named in a stream's key_columns exists in those files.
3. Every file under 05_other_sources is covered by some catalogue glob (README files excepted).
4. Every column that exists in a delivered file is mentioned in the schema file for its folder (so new columns
   cannot ship undocumented), and every field a schema lists under "fields" exists on disk.
Exit 1 on any problem. Writes 07_validation/reports/catalog_check.json.
"""
import csv, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def header(fp):
    try:
        if fp.endswith(".csv"):
            with open(fp, encoding="utf-8", errors="replace", newline="") as fh:
                return next(csv.reader(fh), [])
        if fp.endswith(".log"):
            for line in open(fp, encoding="utf-8"):
                if line.startswith("#fields"):
                    return line.rstrip("\n").split("\t")[1:]
            return []
        if fp.endswith(".jsonl"):
            with open(fp, encoding="utf-8") as fh:
                obj = json.loads(fh.readline() or "{}")
        elif fp.endswith(".json") or fp.endswith(".geojson"):
            obj = json.load(open(fp, encoding="utf-8"))
        else:
            return []
        keys = set()

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    keys.add(k); walk(v)
            elif isinstance(x, list) and x:
                walk(x[0])
        walk(obj)
        return sorted(keys)
    except Exception:
        return []


def names(item):
    """Column names in a key_columns entry such as 'submitted_utc, changed_utc (UTC)' or 'user.screen_name'."""
    out = []
    for part in re.split(r"[,;/]| and ", str(item)):
        part = re.sub(r"\(.*?\)", "", part).strip()
        if part and re.fullmatch(r"[A-Za-z0-9_.:\-]+", part):
            out.append(part.split(".")[-1])
    return out


def main():
    cat = json.load(open("06_data_streams/stream_catalog.json", encoding="utf-8"))
    problems, matched = [], set()
    by_folder = {}
    for s in cat["streams"]:
        if not s.get("delivered"):
            continue
        globs = [s["path_glob"]] + [a["path_glob"] for a in s.get("additional_files", []) if a.get("path_glob")]
        main_files = []
        for g in globs:
            m = [f.replace("\\", "/") for f in glob.glob(g, recursive=True)]
            if not m:
                problems.append(f"{s['stream_id']}: glob matches no file: {g}")
            matched |= set(m)
            if g == s["path_glob"]:
                main_files = m
        hdr = set()
        for f in sorted(main_files)[:60]:
            hdr |= set(header(f))
        for k, v in (s.get("key_columns") or {}).items():
            for item in (v if isinstance(v, list) else [v]):
                for n in names(item or ""):
                    if hdr and n not in hdr:
                        problems.append(f"{s['stream_id']}: key column '{n}' ({k}) is not in the files")
    for d, _, fs in os.walk("05_other_sources"):
        for f in fs:
            p = os.path.join(d, f).replace("\\", "/")
            if p not in matched and not f.lower().startswith("readme"):
                problems.append(f"file not covered by any catalogue entry: {p}")
            if f.endswith((".csv", ".log", ".jsonl")):
                by_folder.setdefault(d.replace("\\", "/"), {})
    # schemas: a folder may be described by several schema files, so columns are checked against all of them together
    folder_text, folder_schemas, schema_fields = {}, {}, {}
    for sf in sorted(glob.glob("06_data_streams/schemas/*.json")):
        if sf.endswith("00_schema_index.json"):
            continue
        text = open(sf, encoding="utf-8").read()
        sch = json.loads(text)
        folders = sch.get("folder") or []
        folders = folders if isinstance(folders, list) else [folders]
        if not folders and "network" in sf:
            folders = ["05_other_sources/network_logs"]
        for fo in folders:
            fo = fo.rstrip("/")
            if os.path.splitext(fo)[1]:
                fo = os.path.dirname(fo)
            if not fo.startswith("05_other_sources"):
                fo = "05_other_sources/" + fo
            folder_text[fo] = folder_text.get(fo, "") + text
            folder_schemas.setdefault(fo, []).append(os.path.basename(sf))
        fields = sch.get("fields")
        listed = list(fields.keys()) if isinstance(fields, dict) else [(x.get("name") or x.get("field")) if isinstance(x, dict) else None for x in (fields or [])]
        schema_fields[sf] = ([str(x).split(" ")[0] for x in listed if x], folders)
    folder_cols = {}
    for fo in folder_text:
        seen, cols, base = set(), set(), set()
        for f in sorted(glob.glob(fo + "/**/*", recursive=True)):
            if not f.endswith((".csv", ".log", ".jsonl")) or os.path.basename(f).startswith("_"):
                continue
            base.add(os.path.basename(f))
            key = re.sub(r"\d{4}-?\d{2}(-\d{2})?", "", f)
            if key in seen:
                continue
            seen.add(key)
            cols |= set(header(f))
        folder_cols[fo] = (cols, base)
        missing_doc = sorted(c for c in cols if c and c not in folder_text[fo])
        if missing_doc:
            problems.append(f"{fo} ({', '.join(folder_schemas[fo])}): columns on disk not described in any schema: {missing_doc[:30]}")
    for sf, (listed, folders) in schema_fields.items():
        cols, base = set(), set()
        for fo in folders:
            fo = fo.rstrip("/")
            fo = fo if fo.startswith("05_other_sources") else "05_other_sources/" + fo
            c, b = folder_cols.get(fo, (set(), set()))
            cols |= c; base |= b
        gone = sorted(x for x in listed if re.fullmatch(r"[A-Za-z0-9_.]+", x) and cols and x not in cols and x.split(".")[-1] not in cols
                      and not x.endswith("_object") and not any(x in b for b in base))
        if gone:
            problems.append(f"{os.path.basename(sf)}: schema fields not on disk: {gone[:25]}")
    os.makedirs("07_validation/reports", exist_ok=True)
    json.dump({"problems": problems}, open("07_validation/reports/catalog_check.json", "w"), indent=1)
    for p in problems:
        print("  -", p[:420])
    print(f"\n{'PASS' if not problems else 'FAILED'}: {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
