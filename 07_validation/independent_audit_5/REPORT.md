# Independent blind audit 5: can the hidden activity be found by a cheap trick?

Reviewer had no access to the answer key, scenario, scripts or earlier audits. Only the permitted inputs were read
(`05_other_sources/network_logs/`, `partner_it/`, `payments/aid_applications.csv`,
`telemetry/vessel_cargo_control_remote_sessions.csv`, the two registries, `schemas/` listing, `DATA_GUIDE.md`).
Nothing outside this folder was written. "Hostile" below is my judgement from the data, not a confirmed label.

**Verdict: not fixed.** Six trivial, artefact-type filters still isolate hostile records with 100 % precision
(section A). The most serious are the hostname-label artefact for the utility implant (one filter returns the whole
command-and-control trace in four log types) and the photo-name artefact in the aid applications. Elsewhere the
blending is good: most rare values I pulled had benign company (section C).

Scripts: `prof.py` (CSV / Zeek value and shape profiler), `profj.py` (JSON Lines profiler by event type),
`zeekprof.py`, `checks.py` (reproduces every count in sections A and B; output in `cache/checks_out.json`).

## (a) Story elements reached

Four stories were reached: S1 utility intrusion (phish, implant on `GW-WS-IT-04`, remote sessions as `GW-ENG-VELA`,
OT changes); S2 Brightwake vendor account used against two tankers; S3 `aid-help-portal.example` phish against city
and air station followed by account takeovers; S4 aid-portal fraud (two application rings, 410 deposit redirects).

| # | Story element | Exact filter | Rows | Believed hostile | Class |
|---|---|---|---|---|---|
| A1 | S1 implant and dropper C2 traffic | first DNS label of an outside name contains `-` (only `update-cdn.vantagesec-telemetry.net`, `update-cdn.meridiancontrols.net`): `proxy/web_proxy_*` `host` | 168 | 168 | **artefact = defect** |
| A1 | same | Zeek `ssl.log` `server_name`, same test | 168 | 168 | **defect** |
| A1 | same | Zeek `dns.log` `query`, same test | 50 | 50 | **defect** |
| A1 | same | endpoint `dns_query` `query`, same test | 50 | 50 | **defect** |
| A2 | S4 application ring A | `'CC-DAM' in damage_photo_hashes` (all other 124,302 photo tokens are 16 hex characters) | 94 | 94 | **defect** |
| A3 | S3 phish clicks | partner `web_*` / `dns_*`: `host.count('.') == 1` (every other host in all seven organisations has three labels) | city 7 + 7, air station 3 + 3 | all | **defect** |
| A4 | S1 phishing mail | `mail_gateway_cbpwa.csv`: subject (digits normalised) that occurs once; 173 templates, exactly one singleton, "FEMA hurricane preparedness guidance for utilities" | 1 | 1 | **defect** |
| A5 | S1 hostile config change | `ot_config_changes.csv`: `parameter == 'configuration file rtu04_active.cfg'` (the other 35 file rows use `04_active.cfg`, `wtr3_active.cfg` forms) | 1 | 1 | **defect** |
| A5 | S1 hostile relay change | `change_type == 'file replaced'` and parameter is not a configuration file | 1 | 1 | **defect** |
| A6 | S2 and S3 clicks | open `mail_url_clicks_brightwake.csv` and `mail_url_clicks_city_airstation.csv`: the tables contain no benign click at all | 1 + 10 | 11 | **defect** (table holds only story rows) |
| G1 | S1 phishing mail | `'cbpwa' in sender_domain`, not own domain, `verdict == 'clean'` (five other look-alike domains, 9,302 rows, all rejected) | 1 | 1 | genuine |
| G2 | S1 dropper | endpoint `image` ends `.pdf.exe` | 6 | 6 | genuine (double extension); no benign double-extension company |
| G3 | S1 implant service | Windows 7045 / endpoint `service_install` whose image is not `<brand>svc.exe` and not a fleet agent | 5 | 1 | genuine; 4 decoys beacon the same way |
| G4 | S1 remote sessions | `remote_access_sessions.csv`: `src_country != 'US'` | 25 | 14 | genuine (11 benign abroad with token and ticket) |
| G4 | same | `auth_method == 'password only'`, no ticket, outside address | 49 | 14 | genuine |
| G5 | S1 OT changes | `ot_config_changes.csv`: empty `change_ticket` | 23 | 5 | genuine |
| G6 | S1 alarm suppression | `alarm_suppression_audit.csv`: `changed_by == 'GW-ENG-VELA'` (95 ticketless rows in total) | 82 | 82 (not each checked against a session) | genuine |
| G7 | S1 SIEM exception | `rule_changes.csv`: `changed_by == 'svc_fieldops_ext'` (4 other vendor-account rows) | 1 | 1 | genuine |
| G8 | S1 historian theft | `historian_access.csv` bulk reads by `GW-SYS-JMP-01\svc_fieldops_ext` falling inside VELA's foreign sessions (needs a join) | 23 bulk reads by the account | at least 7 seen | genuine |
| G9 | S2 vendor sessions | `vessel_cargo_control_remote_sessions.csv`: `src_asn == 'ASN 64512'` | 15 | 15 | genuine (new network, night, no ticket), but zero benign company in this file |
| G10 | S3 campaign | partner mail `sender_domain == 'aid-help-portal.example'` (bulk company: `benefits-portal` 1,455, `training-lms` 788) | 840 city, 360 air station | all | genuine |
| G11 | S3 takeovers | clickers' first sign-on from 203.0.113.0/24, new device, password only (city: 243 new-device successes on that network) | 7 city, 3 air station | 10 | genuine (needs the click join) |
| G12 | S4 ring A | `source_ip == '198.51.100.44'` (3 devices) | 94 | 94 | genuine |
| G13 | S4 redirects | `account_change`, `source_asn == '64512'`, direct deposit | 423 | 410 | genuine; 3 destination accounts, 9 devices |
| G14 | S4 stuffing | portal `login_failed` with `python-requests` | 224,999 | nearly all | genuine |

## (b) Artefact-type separators, including uncertain ones

- A1 to A6 above.
- `aid_applications.csv`: `deposit_routing_number in (990000037, 990000125)` returns 6 applications, 410 account
  changes and 416 disbursements, all hostile; the nine ordinary routing numbers have 5,581 to 5,821 applications
  each. A mule bank is plausible, but two values with no benign user is a one-line filter. Borderline.
- Aid portal: `user_agent_family == 'python-requests'` with `login_success` returns 410 rows, all takeovers (same
  for `profile_updated: direct deposit`). Real tooling behaves so, but no benign script ever signs in. Borderline.
- `remote_access_sessions.csv`: `bytes_in % 100 == 0` holds for 9 of the 14 hostile sessions and 39 of 891 others
  (13 of 14 against 249 of 891 for `% 10`). Weak alone, but shows those rows were generated differently.
- `siem/rule_changes.csv`: 5 of 63 rows have whole-minute timestamps (about 1 expected). They are the hand-written
  ones: `WL-NET-0117` (the whitelist that covers the implant's address 104.21.88.43), `MAINT-EXCEPT-0893`, the storm
  deactivation and two response rows. The first alert on that address was closed at the same second, 14:22:00.
- SIEM: `rule_id == 'SE3-OT-3301' and priority == 'HIGH'` returns 1 row; its detail key
  `change_count_since_2027-09-09` is unique in 468,452 alerts and names the day the hostile changes began.
- Windows 4624: `domain == 'GW-SYS-JMP-01'` returns 22 rows, all `svc_fieldops_ext` (the other vendor accounts log
  on with `CBPWA-OT`). I could not tell which of the 22 are hostile.
- Windows 4625: 5 of 45,140 rows carry an extra `process` key (`consent.exe`, `acantu`, `GW-WS-OPS-03`,
  2027-11-10). Hostility unknown; it is the only key-order difference found in the JSON logs.
- Vessel sessions: `BRW-S-27083` has `bytes_out` 48211, identical to `size_bytes` of the Brightwake phishing mail.
- Vessel sessions and registry: the two targeted tankers are the only ones named `EXT-<NAME>-CCS` (16 rows, 11
  hostile); the other 13 vessels are `CCS-<mmsi>`.
- OT firewall: `dst_zone == 'ot-sub-02'` returns 1 row, the hostile write of 2027-09-11T22:11:47Z. Probably a real
  property (nobody else reaches that RTU through the jump host).
- ASN 64512 / 203.0.113.0/24 is the hostile source in S2, S3 and S4 and the phish sender network in the Brightwake
  click report. Benign users share it (1,763 city sign-ons, 82 Brightwake VPN rows), so it is a pivot, not a filter.

## (c) Low-count values checked that had benign company

- Remote access: `src_country` DE 9, MX 5, CA 4, NL 3, GB 2, RO 1, SG 1: MX, CA and GB (11 rows) are staff with
  token and ticket. `password only` 162 rows, 148 benign. Empty ticket 273 rows.
- SIEM: `ANOMALY_HIGH` 8 and `ANOMALY_MEDIUM` 12, all but one benign users; close note "Storm prep relay
  adjustment per ops supervisor note" 7 rows, 1 hostile; `MAINT-EXCEPT-0892` auto-acknowledgements 28; whitelist
  auto-acknowledgements 1,154 across 8 whitelists (`WL-NET-0117` 105). No rule has a rare detail template except
  the one row above; whole-minute alert times match expectation in all 24 rules.
- Endpoint protection: "disabled by management task" 21 rows by `svc_edr` / `svc_ecm` on 20 hosts; 40 local
  disables by 36 users. SCADA commands: `automation` 20 rows spread over six months.
- File integrity: `CREATED` 13 (monthly reports); `GW-ENG-VELA` 16 rows, 1 hostile; no-diff rows 403.
- Service installs: 68 service names under 30 rows; one-off services on 5 hosts (1 hostile). Triage: 6 of 14 hosts
  have a service found on no other host. Beacon timing of the implant (6 h) matches four decoys.
- Endpoint: installers run from `Temp1_*.zip` 9 distinct, 8 benign; unsigned or rare signers 14 with 3 or fewer rows.
- Mail: 756 single-message sender domains at the utility; 239 inbound `.zip`; partner subjects seen twice or less:
  57 to 109 per organisation ("Wire request", "Updated bank details" are rejected spam).
- Partner sign-ons: no value under 30 rows separates anything; ASN by device by method tables are smooth in all
  seven. Partner web: single-client hosts 8 (Brightwake, 1 hostile) and 7 to 12 elsewhere. Partner firewall rare
  ports (3306, 6379, 2323, 9200 and so on, 8 to 28 rows) are inbound scan noise. Endpoint alerts: nothing.
- Base logistics portal: 126 accounts, one address each; no outside sign-in succeeds; 230 night sign-ins spread over
  all months. No separator and no story element found.
- Aid applications: 51 devices with 20 or more applications are recovery-centre kiosks; 8,232 deposit accounts used
  twice; 624 "restored" rows cover 214 accounts that were never redirected; all-letter ids occur by chance.
- Zeek: `conn.log` categorical fields have no value under 30 rows; 7 whole-second timestamps, all ordinary flows;
  TLS version and cipher of the implant are common values; `x509`, `files`, `notice` nothing. Edge firewall: no
  value under 30 rows. DHCP: `NACK` 24, `EXPIRE` 1.
- Registry: host, user and service-account naming is regular; one hyphenated surname; no address reuse found.

## (d) Not covered

- Packet captures (`pcap/`) were not opened.
- Per-flow numeric artefacts (bytes, durations, ports, id sequences) in Zeek, both firewalls, the web filter and the
  partner logs were not tested beyond whole-second timestamps; `uid`, `record_id` and `logon_id` sequences were not.
- Windows Security was profiled by event id only; 4624 / 4769 / 5145 rows of hostile sessions were not compared
  field by field with benign ones. Endpoint `command_line`, `file_create` paths and `answers` were not reviewed.
- Employee VPN sessions and the `VPN_NEW_LOCATION` / `LOGON_OUTSIDE_HOURS` alerts were only value-profiled; if a
  story lives there I did not reach it. Same for county, port and both hospitals: nothing found, not proven absent.
- Partner DNS and firewall were profiled for rare values and shapes only. Schemas and `stream_catalog.json` were
  not read for leaks. Triage `file_listing.csv` and placeholders were not reviewed.
- The hostile counts in G6 and G8 are estimates; I did not match each row to a session.
