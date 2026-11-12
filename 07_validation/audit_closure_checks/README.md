# Checks behind `07_validation/reports/audit_closure.md`

Run from the project root, for example `python3 07_validation/audit_closure_checks/p2.py`. Each script only reads
the files on disk and prints counts; none of them reads the answer key or a generator.

| Script | What it counts |
|---|---|
| `p1.py` | network sensor logs (names, addresses, services, connection states, DNS/flow pairing); drone detection numbering, signatures and sighting reports |
| `p2.py` | utility audit logs (historian access, file integrity, endpoint protection, SCADA commands, alarm suppression, configuration changes, remote sessions, vessel sessions); isolation window; alert close notes |
| `p4.py` | rescue log against aircraft tracks; shelters against rescue deliveries and bus trips; damage assessment; survey flights |
| `p5.py`, `p6.py`, `p7.py` | fuel ledger and invoices; base status and perimeter sensors; outage map; pump pressure; hospital arrivals after the tug blast; satellite passes |
| `p8.py` | aid portal, aid applications against bank credits, flags, dispatch phrases and first dates of incident types, contracts |
| `p9.py` | ship position scatter and aircraft integrity values in the interference window |
| `p10.py`, `p11.py` | first-audit items: author notes, statuses, network notation, outage bot against the outage map, call series, sessions against flows |
| `n1.py` | narrative audit: for each defect, which quoted fragments are still in the named stories, facts or events (writes `07_validation/reports/narrative_fragments.json`) |
