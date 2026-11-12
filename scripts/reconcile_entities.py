"""Tie the scenario's internal entity list (00_scenario/entities.json) and placeholder places to
the registries: each entity gets "registry_ids" (the registry records it corresponds to) and
"threads" (the threads whose events involve it). Idempotent.

    python3 scripts/reconcile_entities.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "06_data_streams")


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ents = load("00_scenario/entities.json")
    msel = load("00_scenario/msel.json")
    reg_text = {}
    for f in os.listdir(REG):
        if f.endswith(".json") and f != "stream_catalog.json":
            reg_text[f] = open(os.path.join(REG, f), encoding="utf-8").read()

    def exists(i):
        return any(f'"{i}"' in t for t in reg_text.values())

    org_map = load("06_data_streams/_internal/organizations_truth.json")["id_migration"]["scenario_entities"]
    pt = load("06_data_streams/_internal/personas_truth.json")
    pid_handle = {p["persona_id"]: p["handle"] for p in load("06_data_streams/personas.json")["personas"]}
    net = pt["networks"]["base_40"]["persona_ids"]
    manual = {
        "HOST-PORTAL-01": ["EXT-AIDPORTAL-01"], "HOST-DOD-LOG-02": ["EXT-NASLOG-02"], "HOST-911-01": ["EXT-CAD-01"], "HOST-VSL-01": ["EXT-KALVORA-CCS", "EXT-OSTREL-CCS", "EXT-BRW-RMT-01"],
        "EQP-1101 to 1104": ["EQP-1101", "EQP-1102", "EQP-1103", "EQP-1104"], "SOC-ACC-5001 to 5040": ["acct:" + pid_handle[p] for p in net if p in pid_handle],
        "BANK-SYN-71, 72, 73": ["ACCT-40134"], "SUP-0102": ["ORG-1118", "VND-0006"],
    }
    fallback_threads = {"ACT-KES": ["T4", "T6", "T8", "T15"], "ACT-SOF": ["T7", "T19"], "UAS-SYN-01 to 06": ["T7", "T19"], "DEV-01, DEV-02": ["T7"], "JAM-01": ["T7"],
                        "SYN-PER-700001 to 700006": ["T3"], "SOC-ACC-5001 to 5040": ["T4", "T15"], "BANK-SYN-71, 72, 73": ["T3", "T4"], "DOM-SYN-01": ["T4", "T15"],
                        "HOST-PORTAL-01": ["T4"], "HOST-DOD-LOG-02": ["T4"], "HOST-911-01": ["T4"], "HOST-VSL-01": ["T6"]}
    n = 0
    for e in ents:
        eid = e["id"]
        ids = manual.get(eid)
        if ids is None:
            if eid in org_map:
                ids = [org_map[eid].split(" ")[0]]
            elif exists(eid):
                ids = [eid]
            else:
                ids = []
        ids = [i for i in ids if i.startswith("acct:") or exists(i)]
        toks = [eid] if re.fullmatch(r"[A-Z0-9-]+", eid) else re.findall(r"[A-Z]+-[A-Z]*-?\d+", eid)
        prefix = re.match(r"[A-Z-]+", eid).group(0)
        rx = re.compile("|".join(re.escape(t) for t in toks) if toks else re.escape(eid))
        name_rx = re.compile(re.escape(e["name"]), re.I) if len(e["name"]) >= 8 else None
        th = set()
        for ev in msel:
            s = json.dumps(ev, ensure_ascii=False)
            if rx.search(s) or (name_rx and name_rx.search(s)) or any(i in s for i in ids if len(i) > 6 and not i.startswith("acct:")):
                th |= set(ev["threads"])
        th = sorted(th | set(fallback_threads.get(eid, [])), key=lambda t: int(t[1:]))
        if e.get("registry_ids") != ids or e.get("threads") != th:
            e["registry_ids"], e["threads"] = ids, th
            n += 1
    with open(os.path.join(ROOT, "00_scenario", "entities.json"), "w", encoding="utf-8") as fh:
        json.dump(ents, fh, ensure_ascii=False, indent=2)
    places = load("00_scenario/places.json")
    m = 0
    want = {"WQ-01 to WQ-06": ["WQ-01", "WQ-02", "WQ-03", "WQ-04", "WQ-05", "WQ-06"], "GAUGE-12": ["GAUGE-12"], "GAUGE-14": ["GAUGE-14"]}
    for p in places:
        if p["place_id"] in want and p.get("registry_ids") != want[p["place_id"]]:
            p["registry_ids"] = want[p["place_id"]]
            m += 1
    if m:
        with open(os.path.join(ROOT, "00_scenario", "places.json"), "w", encoding="utf-8") as fh:
            json.dump(places, fh, ensure_ascii=False, indent=2)
    none = [e["id"] for e in ents if not e["registry_ids"]]
    print(f"entities reconciled: {len(ents)} ({n} updated); without a registry record (internal actors and objects): {none}; places linked: {m}")


if __name__ == "__main__":
    main()
