"""Local snapshots and the file lock (works with or without git).
  python scripts/snapshot.py "label"   -> _versions/<UTC timestamp>-<label>.zip plus manifest, and a CHANGELOG entry
  python scripts/snapshot.py --verify  -> compare current files with 07_validation/manifest.lock.json
  python scripts/snapshot.py --lock    -> write 07_validation/manifest.lock.json (SHA-256 of every data file)"""
import sys, os, hashlib, zipfile, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

SKIP_DIRS = {"_versions", "__pycache__", "_build_cache", "_cache", "_test", "state", ".git", "cache"}
LOCK = os.path.join(ROOT, "07_validation", "manifest.lock.json")

def files():
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in fs:
            if f.endswith(".pkl"):
                continue
            full = os.path.join(d, f)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if rel == "07_validation/manifest.lock.json":
                continue
            yield rel, full

def sha(full):
    h = hashlib.sha256()
    with open(full, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

VOLATILE = ("07_validation/reports/", "CHANGELOG.md")

def manifest():
    """Hashes of data files. Logs and reports rewritten on every run are excluded."""
    return {rel: sha(full) for rel, full in sorted(files()) if not rel.startswith(VOLATILE)}

def snapshot(label):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(os.path.join(ROOT, "_versions"), exist_ok=True)
    name = f"{ts}-{label.replace(' ', '_')}.zip"
    man = manifest()
    with zipfile.ZipFile(os.path.join(ROOT, "_versions", name), "w", zipfile.ZIP_DEFLATED) as z:
        for rel, full in files():
            z.write(full, rel)
        z.writestr("MANIFEST.json", json.dumps(man, indent=1))
    with open(os.path.join(ROOT, "CHANGELOG.md"), "a", encoding="utf-8") as f:
        f.write(f"- {ts}: snapshot `{name}` ({len(man)} files) - {label}\n")
    print(f"snapshot {name}: {len(man)} files")

def lock():
    man = manifest()
    with open(LOCK, "w", encoding="utf-8") as f:
        json.dump({"locked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "files": man}, f, indent=1)
    print(f"locked {len(man)} files")

def verify():
    if not os.path.exists(LOCK):
        print("no lock file"); return 1
    want = json.load(open(LOCK, encoding="utf-8"))["files"]; have = manifest()
    changed = [k for k in want if k in have and have[k] != want[k]]
    missing = [k for k in want if k not in have]; added = [k for k in have if k not in want]
    print(json.dumps({"changed": changed, "missing": missing, "added": added}, indent=1))
    return 1 if (changed or missing) else 0

if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--verify": sys.exit(verify())
    elif a and a[0] == "--lock": lock()
    else: snapshot(a[0] if a else "manual")
