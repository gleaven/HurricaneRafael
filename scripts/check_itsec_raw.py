"""Gate for the raw IT and security logs: run the invariant probes of the three families.

    python3 scripts/check_itsec_raw.py                    start from scratch; stops after the time budget
    python3 scripts/check_itsec_raw.py --resume           continue; repeat until it prints PASS or FAILED
    python3 scripts/check_itsec_raw.py --budget=110       seconds before it stops and asks to be resumed (default 110)
    python3 scripts/check_itsec_raw.py --only=net,host    families: net, host, partner

The story-specific probes (keyed by MSEL event id) are run by scripts/check_streams.py. This gate runs
everything else those probe files define: the invariants that tie the raw logs to the logs they are
derived from, measured over every day and every file.

  net      scripts/streams/probes_itsec_net.py      firewall, web filter, DHCP, packet capture against Zeek and the SIEM
  host     scripts/streams/probes_itsec_host.py     Windows events, endpoint telemetry, triage against alerts, audit tables, Zeek
  partner  scripts/streams/probes_partner_it.py     partner organisations against the delivered extracts and public streams

A probe reads the files on disk and returns (ok, detail). Results are kept in
07_validation/reports/itsec_raw_check.json so that a run cut off by the time limit can be resumed.
Exit code: 0 PASS, 1 FAILED, 3 more to do.
"""
import importlib
import json
import os
import re
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "streams"))
REPORT = os.path.join(ROOT, "07_validation", "reports", "itsec_raw_check.json")
FAMILIES = [("net", "probes_itsec_net"), ("host", "probes_itsec_host"), ("partner", "probes_partner_it")]
CANON_ID = re.compile(r"^(GW-)?EVT-\d+$")


def load():
    return json.load(open(REPORT, encoding="utf-8")).get("results", {}) if os.path.exists(REPORT) else {}


def save(done, complete):
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    fails = [k for k, v in done.items() if not v["ok"]]
    json.dump({"complete": complete, "failures": len(fails), "results": done}, open(REPORT, "w", encoding="utf-8"), indent=1)


def child(fam, budget):
    """Run the remaining invariant probes of one family (its own process: the families read several hundred MB each)."""
    modname = dict(FAMILIES)[fam]
    mod = importlib.import_module(modname)
    done, t0, pending = load(), time.time(), 0
    for ev, sid in [k for k in mod.PROBES if not CANON_ID.match(k[0])]:
        name = f"{fam}|{sid}|{ev}"
        if name in done:
            continue
        if time.time() - t0 > budget:
            pending += 1
            continue
        t1 = time.time()
        try:
            ok, detail = mod.PROBES[(ev, sid)]()
        except Exception:
            ok, detail = False, "probe raised: " + traceback.format_exc(limit=2).strip().splitlines()[-1]
        done[name] = {"ok": bool(ok), "detail": str(detail)[:600], "seconds": round(time.time() - t1, 1)}
        save(done, False)
        print(f"{'ok  ' if ok else 'FAIL'} {fam:<8}{sid:<26}{ev:<26}{str(detail)[:230]}")
        sys.stdout.flush()
    return 3 if pending else 0


def main():
    budget = next((float(a.split("=", 1)[1]) for a in sys.argv[1:] if a.startswith("--budget=")), 110.0)
    only = next((set(a.split("=", 1)[1].split(",")) for a in sys.argv[1:] if a.startswith("--only=")), None)
    fam = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--family=")), None)
    if fam:
        return child(fam, budget)
    if "--resume" not in sys.argv and os.path.exists(REPORT):
        os.remove(REPORT)
    import subprocess
    t0, more = time.time(), False
    for f, _ in FAMILIES:
        if only and f not in only:
            continue
        left = budget - (time.time() - t0)
        if left < 5:
            more = True
            continue
        rc = subprocess.call([sys.executable, os.path.abspath(__file__), f"--family={f}", f"--budget={left:.0f}"])
        if rc == 3:
            more = True
        elif rc != 0:
            done = load()
            done[f"{f}|(process)|(process)"] = {"ok": False, "detail": f"the probe process for this family ended with code {rc}", "seconds": 0}
            save(done, False)
    done = load()
    fails = [k for k, v in done.items() if not v["ok"]]
    if more:
        print(f"\nPARTIAL: {len(done)} invariant probes run ({len(fails)} failed). Run again with --resume.")
        return 3
    save(done, True)
    for k in fails:
        print("FAILED", k, "-", done[k]["detail"][:300])
    print(f"\n{'PASS' if not fails else 'FAILED'}: {len(fails)} problem(s) in {len(done)} invariant probes of the raw IT and security logs")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
