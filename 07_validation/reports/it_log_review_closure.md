# IT and security logs: closure of the two independent reviews

Two rounds of independent review were run on the IT and security logs on 2026-11-12. Each round had two
reviewers who had not built the logs and who worked blind first (data, registries, schemas and the data guide
only), then against the ground truth.

| Review | Scope | Report | Blocking | Major | Minor |
|---|---|---|---|---|---|
| Audit 3, utility | utility network and host logs (not the portal logs) | `07_validation/independent_audit_3/utility/REPORT.md` | 9 | 14 | 5 |
| Audit 3, partners | partner organisations' IT logs and the extract tables | `07_validation/independent_audit_3/partners/REPORT.md` (condensed copy) | 4 | 10 | 10 |
| Audit 4, utility | the same logs after the fixes | `07_validation/independent_audit_4/utility/REPORT.md` | 3 | 13 | 5 |
| Audit 4, partners | partner logs after the fixes, plus both portal logs for the first time | `07_validation/independent_audit_4/partners/REPORT.md` | 2 | 8 | 9 |

How to read the tables below.

- **Status** is the final state on the files that were locked after the last gate run: *fixed*, *partly*, *not fixed*,
  *documented* (a design decision that was written down instead of changed) or *kept by decision*.
- **Evidence** names who measured it. "audit 4" means the second-round reviewer re-tested the item with their own
  checks. "fix round 2" means the people who fixed the second review's findings measured it with that reviewer's
  scripts or with checks re-implemented from them (`recheck_g2.py` in the partners folder); no independent reviewer
  has re-tested those. The gates named are `scripts/check_itsec_raw.py` (86 invariants) and `scripts/check_streams.py`.
- A short third blind check of the final files is recorded separately; it is not a full review.

Totals: of the 52 items of audit 3, the second-round reviewers found 31 fixed, 16 partly fixed and 5 not fixed
(all five kept by decision). Of the 40 items of audit 4, fix round 2 reports 27 fixed, 8 partly, 4 not fixed and
1 documented.

## Audit 3, utility (28 items)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Periodic outbound connection ranks first among host and address pairs | fixed | audit 4: 32nd of 44,228 pairs |
| 2 | A cipher suite used only by that connection | fixed | audit 4: suite on 47,890 rows |
| 3 | Whole-second times, integral durations, round byte counts on hand-placed flows | fixed | audit 4: conn.log clean; residue (session seconds, batch seconds, fixed gaps) fixed in round 2, see audit 4 item 4 |
| 4 | Alert notes, priorities and dispositions isolate the story; exception rule applied only to story alerts | fixed | audit 4 |
| 5 | Audit tables and alerts agree only where the story is | fixed | audit 4: historian, file integrity and VPN joins complete; residue fixed in round 2, see audit 4 items 2 and 7 |
| 6 | Lure mail unique in the mail log | fixed | audit 4: subject and domain ordinary; attachment shape fixed in round 2, see audit 4 item 1 |
| 7 | Background records under the engineer's account during his leave | fixed | audit 4: none |
| 8 | Three suppression batches outside any session | fixed | audit 4: 7 of 7 inside sessions |
| 9 | Background crossing the boundary during isolation; changes during the freeze | fixed | audit 4 |
| 10 | Sampling rule untrue as stated | fixed | audit 4: stated in guide and schema, classes behave as stated |
| 11 | Web-filter DNS rows not aligned with dns.log | fixed | audit 4: 66,091 of 66,091 within 1 s |
| 12 | Impossible constants in the Zeek logs | fixed | audit 4 for DNS, S0 rows, ssl coverage, protocol mix; byte sizes and record types fixed in round 2, see audit 4 items 10 and 11 |
| 13 | Windows Security internals (duplicate logons, failures outnumbering successes, empty subjects, key order) | partly | audit 4: duplicates, subjects and key order fixed; what remains is audit 4 item 19 |
| 14 | Storm behaviour (midnight step, people-driven alerts rising, logons during power loss) | fixed | audit 4 |
| 15 | No public holidays; nights like days | fixed | audit 4 |
| 16 | Operational tables filled at random | fixed | audit 4 for operators and device fit; command sequence fixed in round 2, see audit 4 item 8 |
| 17 | Registry statements untrue | fixed | audit 4; flags recomputed again after the last regeneration (62 hosts, 2 service accounts, 0 users flagged) |
| 18 | Triage listings with dates after the collection | fixed | audit 4: 0 of 6,999 |
| 19 | Endpoint telemetry too narrow | fixed | audit 4 |
| 20 | Story steps without supporting records | fixed | audit 4. Still unexplained in the data: how the contractor account came to be usable before the lure |
| 21 | Participant guide incomplete and partly untrue | fixed | audit 4 partly; the listed sentences corrected in round 2 (audit 4 item 15); both worked examples re-verified on the final files |
| 22 | Post-incident records hand over the conclusion | documented | Data guide and game-master guide state that records from 2027-10-02T14:33Z include the utility's response; a staged release cut before then is the harder exercise |
| 23 | Volume problems (VPN devices, analysts, flagged addresses, internal senders) | fixed | audit 4 |
| 24 | Real names and address space | partly | Product-named hosts and the firewall vendor renamed; USB models and the hypervisor name invented in round 2. Kept: carrier network numbers, one anonymiser range, agency and plant names |
| 25 | Mixed address conventions, flows to reserved addresses | fixed | audit 4: 0 endpoints in reserved ranges |
| 26 | Source country selects exactly the 14 sessions | fixed | fix round 2: non-US sessions 14 → 25 (11 by travelling staff) |
| 27 | Small format points | partly | Hash shortening documented; firewall bytes are IP bytes; header overhead now varies. Session ids are contiguous by design |
| 28 | Internal code name | fixed | audit 4: absent everywhere |

## Audit 3, partners (24 items)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | One address range and one network label only on hostile records | fixed | Label: audit 4. Range: fix round 2, hostile addresses scattered over the /24; sign-ons with last octet below 100 are 7 hostile of 623 |
| 2 | Registry names the ten link-click victims | fixed | audit 4 |
| 3 | Lure mail separable by formatting | fixed | audit 4; sender-count residue fixed in round 2 (five ordinary mailings with 66 to 89 senders) |
| 4 | Registry assigns the fraud ring's address to the vendor | fixed | fix round 2: vendor moved to 192.0.2.64/26; no vendor address in 198.51.100.0/24 |
| 5 | Older extracts visible as seams | fixed | audit 4: extracts are row subsets of the partner logs |
| 6 | Clicking mailboxes never received the message | fixed | audit 4: 10 of 10 received it first |
| 7 | Firewall destinations disagree with DNS answers | fixed | audit 4: 0 of 73,802 |
| 8 | Partner logs and portal logs disagree | fixed | audit 4 |
| 9 | Mail does not join to the registry or behave like mail | fixed | audit 4 |
| 10 | One template, seven names | partly | Products, addresses, policies, browser and failure mixes differ; hospitals differ from each other (round 2). Office session shapes are still one model |
| 11 | Remote sign-ons ignore calendar and storm | fixed | audit 4 |
| 12 | Workstation sessions mechanically regular | fixed | audit 4 partly; round 2: failures followed by success 70 to 85 %, no empty clock hours |
| 13 | Vendor address plan collides with itself | fixed | audit 4 |
| 14 | Guide and catalogue statements untrue or steering | fixed | audit 4 partly; the listed statements corrected in round 2 |
| 15 | Port 80 against 443 on remote-maintenance sessions | fixed | audit 4 |
| 16 | Mixed routable and documentation ranges | kept by decision | The guide says so; clients no longer come from carrier shared space |
| 17 | Real names (operating systems, browsers, carrier numbers, top-level domains) | kept by decision | Operating-system and browser names are environment detail; carrier numbers remain |
| 18 | TCP only, two statuses, equal byte counts, fixed 3.0 s | fixed | audit 4; byte ratio no longer constant (round 2) |
| 19 | VPN pool unused; 15 s hospital VPN sessions | fixed | audit 4 |
| 20 | A vendor workstation leaves from many pool addresses | kept by decision | Documented as a rotating pool; the vendor now has 16 office egress addresses |
| 21 | Edge devices working in buildings without power | fixed | audit 4 for city, air station, port; hospitals fixed in round 2 (0 rows in the generator period) |
| 22 | Port gate stops two days early; sender of the port's own notice | fixed | audit 4 |
| 23 | Alert service contacted only at real alerts | fixed | audit 4 |
| 24 | Catalogue span | fixed | audit 4 for the partner streams; portal entry corrected in round 2 |

## Audit 4, utility (21 items)

| # | Sev. | Item | Status | Evidence |
|---|---|---|---|---|
| 1 | blocker | Lure attachment name the only one off-pattern | fixed | fix round 2: nine name shapes, 14,106 of 17,669 names off the old pattern |
| 2 | blocker | Hostile file write the only named file | fixed | fix round 2: 151 named files, 541 edits, up to 13 per file, one code path |
| 3 | blocker | Workstation service ticket seen once | fixed | fix round 2: 28 occurrences for that host (neighbours 30 to 31) |
| 4 | major | Timing regularities on story records | fixed | fix round 2; the process-start millisecond fix was not re-measured |
| 5 | major | All alert families collapse after the control network is cut off | fixed | fix round 2: corporate alerts continue; control-network rules silent from the isolation time. MSEL wording for GW-EVT-107 changed to match; daily totals for D+28 to D+34 no longer forced |
| 6 | major | Tickets that point at no record | fixed | fix round 2: 513 citations, 0 before the ticket; 166 of 166 work orders found |
| 7 | major | File writes with no file-integrity row | fixed | fix round 2: 541 of 541; gate `check_itsec_raw.py` |
| 8 | major | SCADA command log inconsistent | fixed | fix round 2: 0 commands repeating a state |
| 9 | major | Closure notes at random; storm-mode rule text | fixed | fix round 2 |
| 10 | major | Byte counts below protocol minimum; transfer equals file size | fixed | fix round 2: 0 of 136,231 handshakes under 1,200 bytes |
| 11 | major | dns.log has A records only; notices inconsistent | partly | AAAA, PTR, SRV and internal names added; no CNAME chains or multi-answer rows |
| 12 | major | Response records hand over the conclusion | documented | Guide and game-master guide; staged release recommended for the harder exercise |
| 13 | major | Zero-noise one-column filters | partly | Travelling-staff sessions, administration-wing readers, large benign files, shared labels and parameters added. One story alert still carries a detail field no other alert has |
| 14 | major | Byte direction inverted on remote sessions | fixed | fix round 2: 0 of 880 |
| 15 | major | Guide statements the data does not support | fixed | fix round 2; residue: large inbound mails start more than 6 s before their log row. Worked examples re-verified on the final files |
| 16 | major | Canon wording against the logs | fixed | fix round 2: wording aligned (D+18, 11.4 h, 94 to 95 s) |
| 17 | minor | Capture fingerprints | partly | SYN options and windows vary by host; ClientHello fingerprints unchanged |
| 18 | minor | Triage details | partly | Collection times off the grid; gateway software list and product-name mismatch not done |
| 19 | minor | Windows minors | not fixed | Patch-only shutdowns, no January reboots, 214 lock events outside a session |
| 20 | minor | Real names | partly | USB models and hypervisor invented; address ranges, carrier numbers and agency names kept |
| 21 | minor | Other | partly | MAC prefixes from vendor blocks; no approved change during the freeze; restore row and analyst ids not done. Four setting changes fall on a whole minute, one of them hostile |

## Audit 4, partners and portals (19 items)

| # | Sev. | Item | Status | Evidence |
|---|---|---|---|---|
| 1 | blocker | Portal labels, user agents, 404s and paths only on hostile rows | fixed | fix round 2: no value of network, user agent, status, path, event or method occurs only on story rows. Remaining by volume: failed sign-ins from the one provider are 99.9 % the guessing run (the storyline's 220,000 attempts) |
| 2 | blocker | Hostile addresses in one octet range | fixed | fix round 2: 66 addresses scattered over the /24; the three-value conjunction returns 10 hostile of 22 in the extract |
| 3 | major | Vendor addresses collide with the fraud ring and portal background | fixed | fix round 2: vendor at 192.0.2.64/26; 0 portal visitors from any partner address |
| 4 | major | Network label not a function of the address | partly (fixed for the portal, payment, tanker and partner streams) | fix round 2: 61,582 addresses, 0 with two labels. The utility's remote-session and VPN tables still label networks themselves |
| 5 | major | Portal clients from carrier shared space | fixed | fix round 2: 0 rows |
| 6 | major | User agent drawn per row | fixed | fix round 2 |
| 7 | major | Portal generator changes at opening; flat background | fixed | fix round 2. A bump of about 2,500 information views a day remains in the week before registration opens |
| 8 | major | Mechanical portal sessions | fixed | fix round 2 |
| 9 | major | Hospital administration wings active without power | fixed | fix round 2: 0 rows; gate `check_itsec_raw.py` (PARTNER-POWER) |
| 10 | major | Single-template residue | partly | Hospitals differ; failure rates vary; office session shapes are one model |
| 11 | minor | Round bulk counts; wave's sender count unique | fixed | fix round 2 |
| 12 | minor | macOS hosts behave as Windows | fixed | fix round 2 |
| 13 | minor | Site names under real top-level domains | not fixed | Kept by earlier decision |
| 14 | minor | Guide, schema and catalogue statements | fixed | fix round 2 |
| 15 | minor | A few messages and sign-ons without a firewall session | not fixed | Not re-measured; generator unchanged there |
| 16 | minor | Second resolver is the edge firewall | not fixed | Left as a plausible small-office setup |
| 17 | minor | Gateway session always the vessel duration plus 1 s | fixed | fix round 2 |
| 18 | minor | Duplicate rows | fixed | fix round 2: 0 |
| 19 | minor | Air-station administration active after evacuation | fixed | fix round 2 |

## Third review: blind check (audit 5, 2026-11-12) and the neutrality scanners

A third reviewer was given only the data, the registries, the schemas and the data guide, and asked one question:
can the hidden activity still be found by a cheap trick? Report: `07_validation/independent_audit_5/REPORT.md`.
It reached four stories and classified 14 routes as genuine signals and 6 as generator artefacts.

| # | Artefact found | Status | Evidence |
|---|---|---|---|
| A1 | The two hostile outside names were the only ones with a hyphen in the first label | fixed | 53,679 web-filter rows now have one; scanner clean |
| A2 | Photo tokens of a different shape on the 94 applications from one address | fixed | all 124,583 tokens are 16 hex characters; reuse shows as repeated hashes |
| A3 | The clicked host was the only two-label host in the partner web and DNS logs | fixed | 213 and 112 ordinary rows of that shape at the two organisations |
| A4 | The lure's subject was the only one-off template in the utility's mail | fixed | many one-off agency subjects; scanner clean |
| A5 | Two configuration-change rows worded unlike their neighbours | fixed | wording and change type shared with ordinary rows |
| A6 | The click tables held only the story's clicks | fixed | 172 and 68 rows, 10 and 1 of them the story's |
| b | Borderline separators (routing numbers, scripted sign-ins, round byte counts, whole-minute rule changes, one HIGH alert with a unique detail key, tanker naming, a value reused between two tables, a firewall zone singleton, an extra key on five rows) | fixed | see the two scanner reports |

Because each review found narrower artefacts than the one before, the reviewers' method was then automated.
`scripts/check_neutrality_utility.py` (26 logs) and `scripts/check_neutrality_partner.py` (53 tables) know which
records belong to the stories and test every column for anything that separates them from ordinary records:
exact values alone and in pairs and triples, string shapes and templates, round numbers and equal values, whole
seconds and minutes, fixed time offsets, JSON key order, structural singletons and registry patterns. A finding
must be fixed in the generator unless it is a real property of the activity, in which case it is named in a short
allow-list inside the script with its reason (15 entries for the utility, 17 for the partner data). Before the
last round the utility scanner reported 85 findings in 14 logs and the partner scanner 31; both now report 0.

What this does and does not establish: the fixes for the third review were verified by the two scanners and by the
checks above, not by a fourth blind review. The scanners do not open the packet captures, and they can only test
the kinds of feature they were written for. The allow-lists are judgement calls and are the first place to look
if a team finds the stories faster than intended.

## Gate results on the final files (2026-11-12)

| Gate | Result |
|---|---|
| `check_streams.py`, all IT, partner and portal streams, tanker logs, aid applications, SCADA historian | PASS; expected observations 25/25, 12/12, 12/12, 17/17, 25/25 by group |
| `check_itsec_raw.py` | PASS: 0 problems in 86 invariant probes |
| `check_neutrality_utility.py`, `check_neutrality_partner.py` | PASS: 0 findings in 26 logs and 53 tables |
| `check_entities.py` | PASS: 130 id columns against 14,535 registry ids |
| `check_catalog.py` | PASS |
| `check_answer_keys.py`, 22 threads | 300 of 300 steps, 60 of 60 raw-log records |
| `check_thread_completeness.py` | PASS: 0 blocking gaps |
| `check_canon_decisions.py --strict` | PASS (one known wording item for review) |
| `build_delivery.py` | PASS: 2,860 files, 1,923 MB, 43 early mentions listed for review |

The reviewers' working caches (`cache/` folders and `*.pkl` files under `07_validation/independent_audit_*/`) can
be rebuilt with the scripts beside them and are not part of the project record.
