"""Walk every step of every answer key and confirm the records it points to exist on disk.

    python3 scripts/check_answer_keys.py [--only=T8,T9]

Each step names an expected observation (event id + stream). The step passes when that
observation's probe (scripts/streams/probes_*.py, the same ones check_streams.py uses) finds the
records in the delivered files. The raw-log records listed under a step ("also_in") are checked the same way.
Each thread is checked in its own process, because the probes of the raw logs read several hundred MB. Also checks that every thread has a key, a question, a conclusion,
at least three steps and at least two different streams, and that the step's files exist.
Writes 07_validation/reports/answer_key_check.json.
"""
import glob
import importlib
import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "streams"))


def main():
    only = set()
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = set(a.split("=", 1)[1].split(","))
    ak = json.load(open(os.path.join(ROOT, "06_answer_key", "answer_key.json"), encoding="utf-8"))
    threads = json.load(open(os.path.join(ROOT, "00_scenario", "threads.json"), encoding="utf-8"))
    rp = os.path.join(ROOT, "07_validation", "reports", "answer_key_check.json")
    todo = [t["thread_id"] for t in threads if not only or t["thread_id"] in only]
    if "--child" not in sys.argv and len(todo) > 1:        # one process per thread; each merges its result into the report
        import subprocess
        if os.path.exists(rp):                              # forget earlier results for the threads about to be checked
            if only:
                prev = json.load(open(rp))
                prev["threads"] = [r for r in prev.get("threads", []) if r["thread"] not in todo]
                prev["problems"] = [x for x in prev.get("problems", []) if x.split(":")[0].split(" ")[0] not in todo]
                json.dump(prev, open(rp, "w"), indent=1)
            else:
                os.remove(rp)
        for tid in todo:
            subprocess.call([sys.executable, os.path.abspath(__file__), f"--only={tid}", "--child"])
        rep = json.load(open(rp)) if os.path.exists(rp) else {"problems": ["no report written"], "threads": []}
        mine = [r for r in rep["threads"] if r["thread"] in todo]
        probs = [x for x in rep["problems"] if x.split(":")[0].split(" ")[0] in todo]
        missing = [t for t in todo if t not in {r["thread"] for r in mine}]
        probs += [f"{t}: the check for this thread did not finish" for t in missing]
        print(f"\n{'PASS' if not probs else 'FAILED'}: {len(probs)} problem(s); {sum(r['verified'] for r in mine)}/{sum(r['steps'] for r in mine)} steps verified in {len(mine)} threads; "
              f"{sum(r.get('raw_verified', 0) for r in mine)}/{sum(r.get('raw_records', 0) for r in mine)} raw-log records under them verified")
        sys.exit(1 if probs else 0)
    probes = {}
    for fp in sorted(glob.glob(os.path.join(HERE, "streams", "probes_*.py"))):
        mod = importlib.import_module(os.path.basename(fp)[:-3])
        probes.update(getattr(mod, "PROBES", {}))
    keyed = {t["thread_id"]: t for t in ak["threads"]}
    problems, report, cache = [], [], {}
    for th in threads:
        tid = th["thread_id"]
        if only and tid not in only:
            continue
        k = keyed.get(tid)
        if not k:
            problems.append(f"{tid}: no answer key")
            continue
        if not k.get("question") or not k.get("conclusion") or len(k["steps"]) < 3 or len(k["streams"]) < 2:
            problems.append(f"{tid}: key needs a question, a conclusion, at least 3 steps and 2 streams")
        ok_n = raw_n = raw_ok = 0

        def verify(key, files, label):
            if files and not glob.glob(os.path.join(ROOT, files), recursive=True):
                problems.append(f"{tid} {label}: no files match {files}")
            p = probes.get(key)
            if p is None:
                problems.append(f"{tid} {label}: no probe for {key}")
                return False
            if key not in cache:
                try:
                    cache[key] = p()
                except Exception:
                    cache[key] = (False, "probe raised: " + traceback.format_exc(limit=1).strip().splitlines()[-1])
            ok, detail = cache[key]
            if not ok:
                problems.append(f"{tid} {label} {key}: {detail}")
            return bool(ok)

        for s in k["steps"]:
            ok_n += verify((s["observation"]["event_id"], s["observation"]["stream"]), s.get("files"), f"step {s['n']}")
            for a in s.get("also_in", []):
                raw_n += 1
                raw_ok += verify((s["observation"]["event_id"], a["stream"]), a.get("files"), f"step {s['n']} raw log")
        report.append({"thread": tid, "steps": len(k["steps"]), "verified": ok_n, "raw_records": raw_n, "raw_verified": raw_ok, "streams": k["streams"], "difficulty": k["difficulty"]})
        print(f"{'ok  ' if ok_n == len(k['steps']) and raw_ok == raw_n else 'FAIL'} {tid:<4} {ok_n}/{len(k['steps'])} steps verified across {len(k['streams'])} streams"
              + (f", {raw_ok}/{raw_n} raw-log records" if raw_n else "") + f"  ({k['difficulty']})")
    for p in problems[:40]:
        print("   -", p)
    if only and os.path.exists(rp):          # partial run: merge into the last report so the file always covers every thread checked
        prev = json.load(open(rp))
        ran = {r["thread"] for r in report}
        report_all = [r for r in prev.get("threads", []) if r["thread"] not in ran] + report
        problems_all = [x for x in prev.get("problems", []) if x.split(":")[0].split(" ")[0] not in ran] + problems
    else:
        report_all, problems_all = report, problems
    report_all.sort(key=lambda r: int(r["thread"][1:]))
    json.dump({"problems": problems_all, "threads": report_all, "steps_verified": sum(r["verified"] for r in report_all), "steps": sum(r["steps"] for r in report_all),
               "raw_records_verified": sum(r.get("raw_verified", 0) for r in report_all), "raw_records": sum(r.get("raw_records", 0) for r in report_all)}, open(rp, "w"), indent=1)
    print(f"\n{'PASS' if not problems else 'FAILED'}: {len(problems)} problem(s); {sum(r['verified'] for r in report)}/{sum(r['steps'] for r in report)} steps verified in {len(report)} threads")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
