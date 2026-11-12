"""Run every check and report PASS/FAIL against the acceptance criteria in 07_validation/ACCEPTANCE.md.
Usage: python scripts/check_acceptance.py  -> 07_validation/reports/acceptance.json; exit 1 if any criterion fails"""
import sys, os, re, json, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, path, save, public_exclusions

def run(script):
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), script)], capture_output=True, text=True)
    return r.returncode, r.stdout

def main():
    res = {}
    rc, out = run("validate.py")
    rep = load("07_validation/reports/validation_report.json")
    res["1_validator_zero_errors"] = {"pass": rep["summary"]["errors"] == 0, "detail": rep["summary"]}
    rc, out = run("check_canon.py")
    res["2_canon_zero_violations"] = {"pass": rc == 0, "detail": out.strip().splitlines()[0]}
    rc, out = run("check_facts.py")
    res["3_numbers_dates_traced"] = {"pass": rc == 0, "detail": out.strip().splitlines()[0]}
    open_high, total = [], 0
    for f in glob.glob(path("07_validation", "findings", "*.json")):
        for x in load(os.path.relpath(f, path()))["findings"]:
            total += 1
            if x["severity"] == "high" and x["status"] not in ("applied", "superseded", "resolved_by_rewrite", "rejected"):
                open_high.append((os.path.basename(f), x["id"], x["status"]))
    res["4_no_open_high_findings"] = {"pass": not open_high, "detail": {"findings_total": total, "open_high": open_high}}
    p2 = glob.glob(path("07_validation", "findings", "review2-*.json"))
    p2_high = [x["id"] for f in p2 for x in load(os.path.relpath(f, path()))["findings"] if x["severity"] == "high" and x["status"] not in ("applied", "rejected")]
    res["5_second_review_no_high"] = {"pass": bool(p2) and not p2_high, "detail": {"files": [os.path.basename(f) for f in p2], "open_high": p2_high}}
    terms = load("02_public_record/restricted_terms.json")["terms"]
    never = [t["pattern"] for t in terms if t["public_from_day"] is None and not t["pattern"].startswith("\\bD")
             and not t["pattern"].startswith("\\bEVT") and not t["pattern"].startswith("BANK-SYN")]
    never += [r"\bEVT-\d", r"BANK-SYN|ASN-SYN|SOC-ACC|MMSI-SYN|UEI-SYN|PIID-SYN|ICAO-SYN|NSN-SYN|SYN-PER|\bDEV-0|\bJAM-0|UAS-SYN|\bVSL-0|\bSUP-0|\bORG-09|\bEQP-\d|\bTANK-0|\bHOST-|ACT-KES|ACT-SOF|truth_event"] + [re.escape(p) for p in sorted(public_exclusions()[1])]
    blobs = {"release": open(path("08_release", "news_stories_public.json"), encoding="utf-8").read(),
             "rss": open(path("03_news", "rss", "all.xml"), encoding="utf-8").read(),
             "public_graph": open(path("04_knowledge_graph", "public", "graph.json"), encoding="utf-8").read()}
    # Registry ids (VSL-, EQP-, ...) are participant-facing reference ids since the registries were rebuilt, so the
    # internal-id pattern applies to news text only; the public graph is still checked for every never-public term and phrase.
    id_pattern = next(p for p in never if p.startswith("BANK-SYN"))
    graph_pattern = r"BANK-SYN|SOC-ACC|MMSI-SYN|UEI-SYN|PIID-SYN|ICAO-SYN|NSN-SYN|SYN-PER|UAS-SYN|ACT-KES|ACT-SOF|truth_event"
    leaks = {k: [p for p in never if re.search(graph_pattern if (k == "public_graph" and p == id_pattern) else p, v, re.I)] for k, v in blobs.items()}
    leaks = {k: v for k, v in leaks.items() if v}
    res["6_public_outputs_leak_free"] = {"pass": not leaks, "detail": leaks}
    rc, out = run("check_integrity.py")
    res["8_integrity"] = {"pass": rc == 0, "detail": out.strip().splitlines()[0] if out.strip() else ""}
    rc, out = run("check_world_state.py")
    res["9_world_state"] = {"pass": rc == 0, "detail": out.strip().splitlines()[0] if out.strip() else ""}
    rc, out = run("check_scenarios.py")
    res["10_scenarios"] = {"pass": rc == 0, "detail": out.strip().splitlines()[0] if out.strip() else ""}
    lock = path("07_validation", "manifest.lock.json")
    if os.path.exists(lock):
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "snapshot.py"), "--verify"], capture_output=True, text=True)
        res["7_locked_files_unchanged"] = {"pass": r.returncode == 0, "detail": r.stdout.strip()[:400]}
    else:
        res["7_locked_files_unchanged"] = {"pass": False, "detail": "not locked yet"}
    overall = all(v["pass"] for v in res.values())
    save("07_validation/reports/acceptance.json", {"overall_pass": overall, "criteria": res})
    for k, v in res.items():
        print(f"{'PASS' if v['pass'] else 'FAIL'}  {k}")
    print("OVERALL:", "PASS" if overall else "FAIL")
    return 0 if overall else 1

if __name__ == "__main__":
    sys.exit(main())
