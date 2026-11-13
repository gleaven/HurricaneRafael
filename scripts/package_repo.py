"""Copy the current, working parts of the project to a clean folder that can be pushed to a git host.

  python scripts/package_repo.py <target folder>              copy (repeat until it prints COMPLETE)
  python scripts/package_repo.py <target folder> --budget=120 stop after about 120 s and resume next time
  python scripts/package_repo.py <target folder> --scan       only scan the target for local paths and secrets

What it leaves out: local history archives (_versions), rebuildable caches, the newsroom's run state
(saved clock and signing secret), map test renders, working notes and two superseded viewer pages.
What it changes: absolute paths of the machine the data was built on are replaced with relative ones
in the few helper scripts and reports that recorded them. Data streams are copied byte for byte.

After a COMPLETE run, in the target folder:
  python scripts/snapshot.py --lock        (the copy has fewer files than the master, so it needs its own lock)
  python scripts/check_acceptance.py
"""
import os, re, sys, time, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

SKIP_DIRS = {"_versions", "__pycache__", "_cache", "_build_cache", "_test", "_preview", "_snapshots",
             "_delivery", "_scratch", ".git", ".vscode", ".idea", "cache"}
SKIP_PATHS = {"10_news_sites/newsroom/state"}                  # saved clock and signing secret
SKIP_FILES = {"memory_update.md", "viewer.html", "rafael-graph.html"}   # root only: working notes, superseded pages
SKIP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
BYTE_FOR_BYTE = ("05_other_sources/", "09_shared_state_timeline/viewer/map_data/")
TEXT_EXT = {".py", ".md", ".json", ".txt", ".html", ".js", ".css", ".bat", ".sh", ".csv", ".cypher",
            ".geojson", ".jsonl", ".xml", ".graphml", ".yml", ".yaml", ".cfg", ".log"}
MAX_SCRUB_BYTES = 30 * 1024 * 1024
LOCK_REL = "07_validation/manifest.lock.json"

# Local paths recorded by one-off helper scripts and reports. Order matters: longest first.
_WIN = r"C:[\\/]+Users[\\/]+[^\\/\"'\s]+[\\/]+OneDrive[^\\/\"']*[\\/]+Documents[\\/]+Synthetic Data"
SCRUB = [
    (re.compile(rb"/sessions/[a-z0-9-]+/mnt/(?:Synthetic Data/)?News Stories"), b"."),
    (re.compile(rb"/sessions/[a-z0-9-]+/mnt/Synthetic Data"), b".."),
    (re.compile(rb"/sessions/[a-z0-9-]+/mnt/outputs"), b"./_scratch"),
    (re.compile(rb"/sessions/[a-z0-9-]+/mnt/\.claude/projects/[^\s\"']*?tool-results"), b"./_scratch/fetch"),
    (re.compile(rb"/sessions/[a-z0-9-]+/mnt/uploads"), b"./_scratch/uploads"),
    (re.compile(rb"/sessions/[a-z0-9-]+"), b"./_scratch"),
    (re.compile((_WIN + r"[\\/]+News Stories").encode()), b"."),
    (re.compile(_WIN.encode()), b".."),
    # only the build machine's own working folders: the data and the generators contain fictional
    # C:\\Users\\<name> paths of the scenario's hosts, which must stay as they are
    (re.compile(rb"C:[\\/]+Users[\\/]+[^\\/\"'\s]+[\\/]+AppData[\\/]+Local[\\/]+(?:Claude[-]Data|Temp[\\/]+claude)[^\"'\s]*"), b"./_scratch"),
]
# Anything matching these in the finished copy is a failure.
FORBIDDEN = [re.compile(p) for p in (rb"/sessions/[a-z0-9]+-[a-z0-9]+-[a-z0-9]+", rb"OneDrive[ ]- ", rb"Claude[-]Data",
                                     rb"local-agent-mode[-]sessions", rb"AppData[\\/]+Local[\\/]+Temp[\\/]+claude",
                                     rb"[A-Za-z0-9._-]+@nvidia\.com")]


def wanted():
    for d, dirs, fs in os.walk(ROOT):
        rel_d = os.path.relpath(d, ROOT).replace(os.sep, "/")
        rel_d = "" if rel_d == "." else rel_d + "/"
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and (rel_d + x) not in SKIP_PATHS)
        for f in sorted(fs):
            if f in SKIP_NAMES or f.endswith((".pyc", ".pkl")) or f.startswith("~$"):
                continue
            if rel_d == "" and f in SKIP_FILES:
                continue
            if rel_d + f == LOCK_REL:        # the copy has its own lock (see the docstring)
                continue
            yield rel_d + f, os.path.join(d, f)


def scrubbable(rel, size):
    return (not rel.startswith(BYTE_FOR_BYTE) and size <= MAX_SCRUB_BYTES
            and os.path.splitext(rel)[1].lower() in TEXT_EXT)


def scrub(data):
    n = 0
    for rx, rep in SCRUB:
        data, k = rx.subn(rep, data)
        n += k
    return data, n


def copy(target, budget):
    t0 = time.time()
    copied = skipped = scrubbed = 0
    total = 0
    keep = set()
    for rel, src in wanted():
        if budget and time.time() - t0 > budget:
            print(f"PARTIAL: copied {copied}, already there {skipped}. Run again to continue.")
            return 3
        dst = os.path.join(target, rel)
        keep.add(rel)
        st = os.stat(src)
        total += st.st_size
        if scrubbable(rel, st.st_size):
            with open(src, "rb") as fh:
                data = fh.read()
            new, n = scrub(data)
            scrubbed += 1 if n else 0
            if os.path.exists(dst):
                with open(dst, "rb") as fh:
                    if fh.read() == new:
                        skipped += 1
                        continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as fh:
                fh.write(new)
            copied += 1
        else:
            if os.path.exists(dst):
                dt = os.stat(dst)
                if dt.st_size == st.st_size and int(dt.st_mtime) >= int(st.st_mtime):
                    skipped += 1
                    continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            os.utime(dst, (st.st_atime, st.st_mtime))
            copied += 1
    # remove anything in the target that is no longer part of the package (git's own folder is kept)
    removed = 0
    for d, dirs, fs in os.walk(target):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in fs:
            rel = os.path.relpath(os.path.join(d, f), target).replace(os.sep, "/")
            if rel not in keep and rel != LOCK_REL:
                os.remove(os.path.join(d, f))
                removed += 1
    for d, dirs, fs in os.walk(target, topdown=False):           # drop folders left empty
        if ".git" not in d.split(os.sep) and not os.listdir(d):
            os.rmdir(d)
    print(f"COMPLETE: {len(keep)} files, {total / 1e6:.0f} MB; copied {copied}, unchanged {skipped}, "
          f"removed {removed}; local paths rewritten in {scrubbed} file(s)")
    return 0


def scan(target, budget):
    """Fail if a local path, an e-mail address or the newsroom secret is in the target."""
    t0 = time.time()
    state = os.path.join(target, "_scan_state.txt")          # resume marker, removed on completion
    done = set(open(state).read().split("\n")) if os.path.exists(state) else set()
    bad, biggest = [], (0, "")
    for d, dirs, fs in os.walk(target):
        dirs[:] = sorted(x for x in dirs if x != ".git")
        for f in sorted(fs):
            full = os.path.join(d, f)
            rel = os.path.relpath(full, target).replace(os.sep, "/")
            if rel == "_scan_state.txt":
                continue
            size = os.path.getsize(full)
            biggest = max(biggest, (size, rel))
            if f == "secret.key" or "/state/" in "/" + rel and "newsroom" in rel:
                bad.append((rel, "newsroom run state"))
            if rel in done:
                continue
            with open(full, "rb") as fh:
                tail = b""
                while True:
                    chunk = fh.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    buf = tail + chunk
                    for rx in FORBIDDEN:
                        m = rx.search(buf)
                        if m:
                            bad.append((rel, m.group(0)[:60].decode("utf-8", "replace")))
                    tail = chunk[-200:]
            done.add(rel)
            if budget and time.time() - t0 > budget:
                with open(state, "w") as fh:
                    fh.write("\n".join(sorted(done)))
                for rel, what in bad:
                    print(f"  FOUND {what!r} in {rel}")
                print(f"SCAN PARTIAL: {len(done)} files scanned, {len(bad)} finding(s) so far. Run again to continue.")
                return 3
    if os.path.exists(state):
        os.remove(state)
    for rel, what in sorted(set(bad)):
        print(f"  FOUND {what!r} in {rel}")
    print(f"largest file: {biggest[1]} ({biggest[0] / 1e6:.1f} MB)")
    if biggest[0] > 95e6:
        print("  WARNING: over 95 MB; most git hosts refuse files over 100 MB")
    print(f"SCAN {'FAIL' if bad else 'PASS'}: {len(done)} files, {len(set(bad))} finding(s)")
    return 1 if bad else 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    target = os.path.abspath(args[0])
    if os.path.commonpath([target, ROOT]) == ROOT:
        print("The target must be outside the project folder.")
        return 2
    budget = next((float(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--budget=")), 0)
    os.makedirs(target, exist_ok=True)
    if "--scan" in sys.argv:
        return scan(target, budget)
    return copy(target, budget)


if __name__ == "__main__":
    sys.exit(main())
