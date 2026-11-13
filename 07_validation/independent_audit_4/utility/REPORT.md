# Independent audit 4: utility IT and security logs

Scope: `05_other_sources/network_logs/` (siem, zeek, audit, firewall, proxy, dhcp, pcap, windows, endpoint, triage), `06_data_streams/gw_host_registry.json`, `stream_catalog.json`, `schemas/`, `11_hackathon/DATA_GUIDE.md`. `portal/` and the six partner extracts in `audit/` were not reviewed. Nothing outside this folder was written; no data, script or document was changed.

Coverage: every check ran over the whole span (2027-07-16 to 2028-01-12) except the endpoint-to-sensor join and process-tree checks (September 2027 only) and the "alert names someone at work" check (November 2027 only). All 181 capture files were parsed.

Reproduce: `./run_all.sh` (builds caches in `/tmp/c`, then runs every script; each step stays under 170 s). Script names are given per defect. `out_*.txt` are saved outputs.

## Pass 1 (blind: data, registry, schemas, guide only)

About ten minutes of wall-clock time from the first command to the whole chain. What each cheap trick returned, in the order tried:

| # | Trick | Returned | Kind |
|---|---|---|---|
| 1 | value counts, `audit/remote_access_sessions.csv` | `src_country` DE 9, NL 3, RO 1, SG 1: 14 sessions, all `GW-ENG-VELA`, all `password only`, no ticket, 185.220.101.x / 45.141.152.x / 198.51.47.19 / 198.51.48.203; seven of them 219 to 948 MB out (benign maximum 3.7 MB). Gives gateway host, account and outside addresses at the first command (about 1 minute) | genuine analysis, zero noise |
| 2 | value counts, `ot_config_changes.csv`, `alarm_suppression_audit.csv`, `scada_command_log.csv` | five no-ticket changes by that account during the freeze; 82 suppressions in seven bursts; two remote-desktop BREAKER OPEN with empty operator inside the sessions. Gives the control-network actions (about 3 minutes) | genuine analysis |
| 3 | value counts, `file_integrity.csv` | one path that is not an 8-hex file name; one `diff_summary` used once | **generator artefact** (defect 2) |
| 4 | value counts, `settings_audits.csv`, `change_management.csv`, `rule_changes.csv` | "Security incident SI-2027-CC-001", two MISMATCH rows naming the account, "evidence export 2027-09-07 to 2027-10-02", exception rule "removed" | in-world response records (defect 12) |
| 5 | value counts, SIEM (`priority`, `closed_by`, rule by month) | the one HIGH `ALARM_SUPPRESSION_CHANGE`, the one alert closed by the CISO | canon alerts |
| 6 | conn.log: flows to the gateway, integral durations, round bytes, whole-second times | nothing that separates the hostile flows (0 of 14 whole-second, byte counts equal the session table for 892 of 892) | sound |
| 7 | session duration modulo 60 | 11 of the 14 hostile durations are whole minutes + 22 s | **generator artefact** (defect 4) |
| 8 | triage: names present on one host only | GW-WS-IT-04: `FEMA-PREP-GUIDANCE-2027.pdf.exe`, `vstelemetry.exe`, service "Vantage Telemetry Update Service", eight `histarchive_*.arc`. Gives the first compromised host (about 7 minutes); five other hosts carry decoy one-off services | genuine analysis (design question, defect 12) |
| 9 | endpoint telemetry grep on those names; top destination per host | 167 connections to 104.21.88.43, `update-cdn.vantagesec-telemetry.net` (about 8 minutes). The command pair is one of 13 single-host periodic destinations | genuine analysis |
| 10 | value counts, boundary firewall | `src_zone = corp-users-admin`: one row, 10.14.22.47 to 10.72.4.20:445, 1.96 GB | genuine, zero noise |
| 11 | value counts, Windows Security | `service = gw-ws-it-04$` once in 46,419 ticket events | **generator artefact** (defect 3) |
| 12 | value counts and name shapes, mail gateway | one attachment name of 17,586 breaks the `word_NNNNN.ext` pattern: the lure | **generator artefact** (defect 1) |
| 13 | JSON key order, separators, id shapes, millisecond zeros, cipher suites, ClientHello fingerprints, SNI seen once, rare ports, rare `history`, x509 issuers | nothing that separates hostile rows | sound |

## Defects

### Blockers (answer by one trivial filter on a generator artefact)

**1. The lure is the only mail whose attachment name is not machine-shaped.**
`audit/mail_gateway_cbpwa.csv`: 17,586 messages carry an attachment; 17,585 names match `^[a-z]+_\d+\.[a-z0-9]+$` (`roster_80625.pdf`, `minutes_69453.vbs`); the one that does not is `2027-08-30T13:14:09Z, preparedness@cbpwa-vendor-support.com -> dgonzalez@cbpwa.example, FEMA-PREP-GUIDANCE-2027.zip`. Subject and sender domain no longer isolate it (10,855 one-off subjects, 766 one-off domains).
Repro: `p1_more_tricks.py` (line "MAIL attachments").

**2. The hostile file write is the only row of `file_integrity.csv` with a human file name, and its text and hashes are hand-made.**
520 rows; 519 file names are 8 hex digits (`\\gw-srv-ot-01\relayconfigs\sub05\de522cc6.xlsx`); row 169 is `\\gw-srv-ot-01\relayconfigs\sub02\rtu_config_draft.xml`. Its `diff_summary` ("overcurrent_trip_threshold 1200A -> 2400A for relays R-02A, R-02B, R-02C") occurs once; the other eleven texts occur 14 to 20 times each (the same "time dial 2.5 -> 2.0 for relay R-01C" 19 times, also on `.xml` files in `projects`). Its hashes `d7e1a0f3c2b18429 -> a3f8c2d1e9b04517` are patterned by hand. No file is touched twice in six months (520 distinct paths; 390 MODIFIED with no earlier row).
Repro: `p2_item5_joins.py` ("path name shapes"), `p1_valcounts.py audit/file_integrity.csv`.

**3. One Kerberos service name occurs once and names the first compromised host.**
`windows/security_2027-08.jsonl`: `{"time_utc":"2027-08-30T12:03:59.308Z","host":"GW-SRV-DC-02","event_id":4769,"user":"dgonzalez","src_ip":"10.14.22.47","service":"gw-ws-it-04$"}`. It is the only ticket for a workstation account among 46,419 event-4769 rows (178 service names). A count of `service` hands over host, user and day, 70 minutes before the lure arrives. Every other interactive logon in the data set lacks this ticket.
Repro: `p1_windows_report.py` (`v:4769:service ... rare`).

### Major

**4. Residual timing artefacts on the hostile records.**
- `remote_access_sessions.csv`: 11 of the 14 hostile `duration_s` values are whole minutes + 22 s (5422, 6622, 1522, 7222, 7822, 922, 802, 622, 442, 382, 1282); 15 of 878 other sessions have that residue. 12 of 14 end in the digit 2 (10 % otherwise).
- `alarm_suppression_audit.csv`: five of the seven hostile batches start at second `:07` (03:12:07, 04:47:07, 22:15:07, 08:36:07, 02:10:07); 0 of 25 other ADD rows do.
- Each of the seven batches follows a remote-desktop logon on GW-SYS-SCADA-01 by exactly 5 s (logon 03:12:02, batch 03:12:07; ... 02:10:02 / 02:10:07): 6 to 22 suppressions entered five seconds after logon, seven times out of seven.
- `endpoint`: 23 `HistTrend.exe` starts on GW-SYS-JMP-01 fall on a whole second (`.000Z`), 5 of them hostile; 73 of about 115,000 process starts elsewhere do.
Repro: `p1_ras_tricks.py`, `p1_more_tricks.py`, `p2_canon_checks.py` (f).

**5. SIEM alerts, web-filter blocks, mail quarantines, USB and Defender events collapse for five working days after 2027-10-12T08:00Z although the offices are full.**
Hourly alerts on 10-12: 119, 88, 97, 94, 85, 96, 107, 107, then 3, 2, 8, 15. Daily: 2,424 (10-11), 958, 228, 263, ..., 2,349 (10-20). Every rule family falls, including corporate ones: `POLICY_BLOCKED_SITE` 788 (Mon 10-11), then 126, 75, 102, 79; `MAIL_ATTACHMENT_QUARANTINED` 73 then 30, 5, 5, 7; `USB_STORAGE_MOUNTED` 30 then 7, 3, 1, 2. In the same days office interactive logons are 111, 108, 112, 110 (median 110) and sampled allowed web rows 1,334, 1,297, 1,303, 1,305 (normal). Because blocked web rows, quarantined mail and USB events are generated one-to-one from alerts, the "complete" raw logs show staff at work who stop hitting the block list. Isolating the control network cannot cause this. The drop also starts four hours before the isolation (first `EMERG-OT-ISOLATION` deny 12:06:59Z, gateway powered off 12:07:57Z); `expected_observations` says 08:00Z, the canon event says 12:00Z (07:00 CDT).
Repro: `p3_oct12_drop.py` (rule by day 10-09 to 10-21, web filter, logons, mail), `p3_storm_siem.py`.

**6. Ticket references in the audit tables are mostly dangling.**
`remote_access_sessions.csv` and `alarm_suppression_audit.csv` cite 385 distinct `CHG-27-nnnn` tickets; 121 exist in `change_management.csv` (196 CHG records, stated complete). Of the 199 citations of existing tickets, 37 predate the ticket (RAS session 2027-07-19 cites CHG-27-1119, opened 2027-09-02) and 23 are more than 30 days later; CHG-27-1079 ("configuration file 05_active.cfg, GW-SYS-RTU-05") is cited by three unrelated sessions in December. 251 `WO-4nnnn` references match nothing in `maintenance/work_orders.csv` (ids there are `WO-2027-nnnnn`). In `remote_access_sessions.csv` 306 of 398 CHG citations (77 %) point at no record, so canon's "no work order exists" test also fails for most ordinary ticketed sessions. (`ot_config_changes.csv` is clean: 118 of 118 tickets exist, owner matches in 112 of 114.)
Repro: `p2_tickets.py`.

**7. Windows shows 296 file writes on GW-SRV-OT-01 that the "complete" file-integrity table and the SIEM do not have, two of them in the hostile session.**
816 event-5145 `WriteData` on the six monitored shares; 520 have a `file_integrity.csv` row and alert, 296 do not (239 by workstation machine accounts such as `GW-WS-ENG-05$`, 57 by people, 12 on `relayconfigs`). In the 22:11Z session `GW-ENG-VELA` writes `projects\sub01\1ee21d24.xlsx` (22:11:03) and `projects\sub03\c81f600a.xlsx` (22:11:07) besides `relayconfigs\sub02\rtu_config_draft.xml`; only the last is in the integrity table. Canon describes one file.
Repro: `p3_fim_5145.py`.

**8. `scada_command_log.csv` is state-blind and ignores the storm.**
29 of 75 breaker commands repeat the state the same device is already in (21 OPEN after OPEN, 8 CLOSE after CLOSE); 18 of 39 pump commands likewise. GW-SUB02-CB-7, opened by the adversary on 09-21, is opened again on 11-18 with no close between. 404 commands in 181 days (2.2 a day); landfall day has 4, the following days 1, 2, 1, 1, 2, 1; no command touches a SUB-01 device between 09-14 and 09-19 although SUB-01 trips at 07:12Z.
Repro: `p3_misc.py` (first lines), `p3_fim_5145.py` (last lines).

**9. Analyst closure notes are drawn at random.**
"Storm damage" closes 1,682 alerts in July and 3,111 in December; `AGENT_OFFLINE` is closed as "Approved removable media" 20,886 times and "Benign software" 24,368 times; `DNS_UNCATEGORISED_DOMAIN` as "Switch maintenance" 10,972 and "User travelling" 10,953; session-anomaly alerts as "Communications path down" (10) and "Storm damage" (10, one of them on 2027-07-22). Storm mode says "dismiss LOW and MEDIUM alerts from 44 device-availability and OT maintenance rule families": the data has 24 rule ids in all, 16 are dismissed, 798 dismissed alerts are INFO, and the dismissed set includes `DNS_UNCATEGORISED_DOMAIN` (954), `USB_STORAGE_MOUNTED` (66), `PUP_DETECTED` (51), `VPN_NEW_LOCATION` (13).
Repro: `p3_storm_siem.py`, `p2_canon_checks.py` (q).

**10. Byte counts below what the protocol needs.**
26,326 of 162,410 full (non-resumed) TLS handshakes in `ssl.log` have fewer than 1,200 response bytes in `conn.log`; 867 of them are TLS 1.2 rows that list a certificate chain. The beacons (318 out, 212 in, TLS 1.3, not resumed; canon values) are in this class, as is the benign agent traffic. Transfers carry no overhead at all: the 13:23Z download is 1,884,012 response bytes for a 1,884,012-byte file; the staging flow is 1,902,447,611 response bytes for eight files that sum to 1,902,447,611. Every TCP packet in `conn.log` has exactly 40 bytes of header (422,374 flows) while the captures show 52-byte SYNs.
Repro: `p3_net_join2.py` (last line), `p1_conn_artifacts.py`, `p2_triage_logons.py`.

**11. `dns.log` is not a resolver log.**
210,064 rows: all `qtype` A, all `AA=F RD=T RA=T`, one answer each, no CNAME, no PTR/SRV/AAAA, and not one query for a `cbpwa.example` name although clients connect to `mail.cbpwa.example` and `gw-srv-patch-01.corp.cbpwa.example` thousands of times. Uncategorised names are spread evenly over seven TLDs (6,503 to 6,670 each). 97 `HTTP::Unusual_User_Agent` notices are all on port 443, where the user agent is not visible; all 110 `DNS::External_Name` notices say "pointing to a local host" for a public address. `conn.log` has ten `history` strings in 669,452 rows; `http.log` status codes are 200, 301, 302 only.
Repro: `p1_more_tricks.py`, `p1_conn_profile.py`, `p3_net_join2.py`.

**12. Post-incident records still hand over the conclusion (design decision, unchanged from audit 3 item 22).**
`change_management.csv` "Security incident, SI-2027-CC-001, opened by CISO after session-behaviour anomaly"; `settings_audits.csv` "evidence export ... 2027-09-07 to 2027-10-02" and "2027-09-11T22:11:26Z by GW-ENG-VELA ... MISMATCH"; 85 REMOVE rows and four restore rows citing the incident; `rule_changes.csv` "removed (AUDIT-EXC-2027-10)"; event 4725 disabling `svc_fieldops_ext` on the gateway; the only non-patch shutdown in six months (gateway, 2027-10-12T12:07:57Z); 14 triage folders with case `SI-2027-CC-001`, of which GW-WS-IT-04 lists the lure and the implant. The guide says only that the triage was "collected in October 2027". Either state that the response is part of the delivery, or cut the delivery before 2027-10-02T14:33Z.
Repro: `p1_valcounts.py`, `p1_triage.py`.

**13. One-column filters with no benign neighbour (not artefacts, but no analysis needed).**
- `src_country != US`: 14 of 892, all hostile (no employee or vendor ever connects from abroad).
- boundary firewall `src_zone = corp-users-admin`: 1 of 23,952 rows, the 1.96 GB staging flow.
- endpoint `file_create` sorted by `size`: the eight largest files in six months are the eight staged archives (168 to 295 MB; ninth is 48 MB).
- historian sessions from the gateway whose account differs from the gateway session's account: 14 of 168, all hostile.
- `alarm_point` labels "(SUB-0n relay trip)": 12 rows, all the hostile 17:09Z batch and its reversal; alarm ids are simply numbered in order of suppression (ALM-2101 to ALM-2207 strictly increasing over 107 ADD rows).
- `ot_config_changes.parameter` values "P-3 discharge pressure setpoint (psi)" and "relays R-02A/B/C overcurrent trip (A)": 2 rows each, hostile change and its reversal.
Repro: `p1_ras_tricks.py`, `p1_csv_profile.py`, `p1_more_tricks.py`, `p2_item16_ops.py`.

**14. Remote-access byte direction is inverted for ordinary sessions.**
For 845 of 878 benign sessions the client sends more than it receives (median 4.1 MB in, 0.64 MB out) on a gateway that forwards screens to the client. Only the hostile sessions (11 of 14) and 33 others have `bytes_out > bytes_in`.
Repro: `p1_ras_tricks.py`.

**15. Guide statements that the data does not support.**
- "Alerts about ... alarm-suppression changes ... each correspond to one row of an audit table": 32 of 71 `SE3-OT-3301` alerts are daily "periodic re-evaluation" rows (09:44Z, 2027-09-12 to 10-12) with no audit row.
- "... out-of-hours remote-desktop logons each correspond to one row of an audit table": the 480 `LOGON_OUTSIDE_HOURS` alerts match Windows 4624 type 10 events (480 of 480), not an audit table; none of the 14 foreign logons on the gateway raises one.
- "`user` is ... `-` for requests made by the operating system, services and agents": 7,342 blocked requests to games, gambling, dating and peer-to-peer sites have `-` (GW-WS-IT-04: three to `www.heartline-dating.org`).
- "Audit logs ... Complete": see defects 6 and 7. "the mail transfer of every message in the mail gateway table": 89 inbound rows have no SMTP flow within 6 s; 426 inbound SMTP flows have no row.
- "One `allow` row for every sensor flow that crosses the device": 2,192 flows from the DMZ mail gateway 172.20.5.10 to 10.14.10.30:25 are in no firewall log.
- "Network, security ... records start ... on 2027-07-16": `endpoint_protection.csv` and `mail_gateway_cbpwa.csv` start 2027-07-15, `change_management.csv` 2027-07-12.
- "Addresses and names outside the utility are invented": see defect 20.
- Section 8, in a worked example about an ordinary DNS lookup: "operator commands in `scada_command_log.csv` carry `origin` ... and remote-desktop commands name the `origin_host` they came through". Out of place there; it points at the field that separates the two hostile breaker commands.
Repro: `p2_item5_joins.py`, `p3_misc.py`, `p3_net_join.py`, `p3_smtp.py`.

**16. Canon and expected-observation wording against the logs.**
- "All 14 out-of-hours sessions" (GW-EVT-011): sessions 11 and 13 start Tue 09:24 and Fri 14:40 local, inside the account owner's Mon-Fri 07:00-17:30; two more are on Saturdays at 12:00 and 09:32.
- "14 sessions ... D-7 to D+16" (canon event at D+18): the fourteenth session is on D+18 (2027-10-02T14:32:44Z), as canon's own "session 14 of 14" says.
- "total session time 11.4 hours": the 14 durations sum to 41,348 s = 11.49 h.
- "Remote-interactive logon on GW-WS-OPS-02 ... about 95 s before the breaker-open command" (twice): 78 s on 09-21, 101 s on 09-24.
- Ticket on a domain controller for the 23:58Z replica logon: event 4769 is on GW-SRV-OTDC-02 with `src_ip` 10.14.22.47, but no flow from 10.14.22.47 to 10.72.1.6 exists in `conn.log` or the boundary firewall (the workstation's only flow into 10.72.0.0/16 is the port-445 one).
- The alert flood begins 2027-09-11T14:00Z, about 60 hours before landfall (`LINK_DOWN` 243 on 09-11, 1,115 on 09-12; `UPS_ON_BATTERY` 220 on 09-12), as the canon daily totals for D-2 and D-1 require.
Repro: `p2_canon_checks.py`, `p3_storm_siem.py`.

### Minor

**17. Packet captures have one TCP stack and two TLS clients.** All 245,128 SYNs (Windows clients, Linux servers, outside mail servers, outside remote users) carry the same options (`mss 1460, nop, wscale 8, nop, nop, sackOK`) and window 64240. 165,929 ClientHellos have two fingerprints: one for every internal client (browsers, agents, the implant: 143,921) and one for every outside client (22,008). Repro: `p3_pcap_report.py`.

**18. Triage details.** GW-SYS-JMP-01 `installed_software.csv` lists two products while its services, autoruns and execution history show five more (Remote Access Gateway, Meridian Historian client, RelaySet, Asset Inventory, Defender). The registry calls the gateway product "ClearPath SecureReach 2.1"; the host shows `ragw.exe` signed "Remote Access Gateway Software Inc". `epagent.exe` has hash `c0f9df2b...` in execution history (last run 2027-08-19) and `bb6f04a9...` in autoruns (first seen 2027-08-20) with no run of the new binary. All 14 `collected_utc` values end in a multiple of 5 s. Repro: `p1_triage.py`.

**19. Windows residue.** 45,809 failed logons against 78,823 successful ones; every 4672 carries the same three privileges; 1,116 of 1,117 event-1074 rows are `TrustedInstaller.exe` restarts (no user ever restarts or shuts down a machine); January 2028 has no 1074/6005/6006 at all (104 to 280 in the other full months); 214 of 44,912 lock/unlock events lie outside their logon session. Repro: `p1_windows_report.py`, `p3_windows.py`, `p3_misc.py`.

**20. Real names and address space.** 185.220.101.0/24 with AS-60729 is a real, well-known anonymiser range; AS-7018, AS-22773, AS-20057 and AS-11427 are real carriers; 104.21.88.0/24, 45.141.152.0/24 and 12.186.44.64/28 are real allocations. ERCOT (registry roles, `change_management.csv` 5 times, `settings_audits.csv`), FEMA (registry operator, lure name), "O.N. Stevens Water Treatment Plant" and "Texana" (real Corpus Christi facility and water source; the guide says the data uses fictional names on real sites), `maximo_assetnum` (4 equipment rows), "VMware ESXi 7.0", USB models "Store-n-Go", "Ultra Fit", "Extreme". Repro: `grep` on the registry; `p3_endpoint.py`.

**21. Smaller realism points.** All 366 MAC addresses in the lease log start `02:` and no two share an OUI. 6 VPN sessions overlap a desk session of the same user. `ot_config_changes.csv` row 2027-10-12T12:14:00Z is `change_type` "local panel" with `source_host` GW-WTP-HMI-01. Three "Approved change" tickets are opened during the freeze (10-23, 10-25). Analysts `aclark` and `bflores` close 101,296 alerts but have no `analyst_id` in the registry. 10,995 of 11,079 rejected (spoofed-sender) messages have an SMTP flow smaller than the logged message size. Zeek `uid`s are `C` + 17 hex digits. Repro: `p3_dhcp_vpn.py`, `p2_item16_ops.py`, `p3_smtp.py`.

## The 28 items of audit 3, re-tested

| # | Audit 3 item | Verdict | My numbers |
|---|---|---|---|
| 1 | Hostile flows complete in a sampled sea; command pair ranks first | fixed | pair is 32nd of 44,228 internal-to-internet pairs, 13th among workstation pairs; 8 workstations have a top destination no other host uses; 13 server names are single-host with 20+ flows; decoys beacon at 5 to 12 h like the implant (6.1 h) |
| 2 | Cipher suite unique to the command channel | fixed | `TLS_AES_128_GCM_SHA256` on 47,890 rows; ClientHello fingerprint shared with 143,921 hellos |
| 3 | Whole-second times, integral durations, round bytes on hand-placed flows | partly | conn.log clean (4 whole-second rows of 669,452, none hostile; session bytes equal Zeek for 892 of 892; lead and lag in the same range). Residue in audit and host logs: defect 4 |
| 4 | SIEM notes, priorities and the exception rule isolate story alerts | fixed | rarest notes: MAINT-EXCEPT-0892 on 28 alerts (all 30 gateway-sourced historian alerts in the rule's window are auto-acknowledged or storm-dismissed), WL-NET-0117 on 103 (39 beacons); 2,014 HIGH; 3,752 ESCALATED. New: notes are random (defect 9) |
| 5 | Audit tables and SIEM agree only where the story is | partly | historian 117 of 117 alerts match a row, 948 of 948 sessions have a flow, 0 round durations, 0 one-off tag groups; file integrity 520 of 520; VPN 263 of 263; suppression counts agree (0 mismatches). Left: file name (defect 2), 296 unlogged writes (defect 7), 32 periodic suppression alerts without a row |
| 6 | Lure mail unique | partly | subject 1 of 10,855 one-offs, domain 1 of 766 one-offs, 279 clean inbound zips; attachment-name shape still unique (defect 1) |
| 7 | Background activity under GW-ENG-VELA during leave | fixed | leave window: 0 historian, 0 VPN, 0 desk logons, 0 web rows for the owner; everything naming the account is the story (11 sessions, 3 changes, 62 suppressions, 1 file write) plus 8 inbound-mail alerts |
| 8 | Three suppression batches with no session | fixed | 7 batches, each inside a hostile session, each with a logon and flow to GW-SYS-SCADA-01 |
| 9 | Historian sessions cross the boundary during isolation; changes during the freeze | fixed | isolation: 36 historian sessions, all from control-network clients; 0 allowed boundary rows; 1,039 denies; first allow 2027-10-19T18:02:17Z. Freeze: 16 emergency, 4 incident, 5 hostile changes; thaw record 2027-10-25 |
| 10 | Sampling rule cannot be true as stated | fixed | guide and schema now state the classes; periodic traffic is regular, alert-backed rows are complete. Exceptions in defect 15 |
| 11 | Web-filter DNS rows do not line up with dns.log | fixed | 66,091 of 66,091 within 1 s |
| 12 | Zeek constants and impossible combinations | partly | fixed: DNS flows vary, S0 rows have 1 to 3 packets and no reply, every established TLS flow has its ssl.log row, no TLS 1.2/1.3 mix, NTP/SMTP/SSH/ICMP present, 576 notices all with text. Left: defects 10 and 11 |
| 13 | Windows Security internals | partly | 0 duplicate 4624 per logon id (78,823 ids); 627 group changes all by 11 IT Infrastructure accounts; 5,122 pre-auth failures for 1,276 lockouts; uniform key order. Left: defect 19 |
| 14 | Storm does not behave like a storm | fixed | hourly counts rise smoothly; people-driven alerts fall (`POLICY_BLOCKED_SITE` 397 and 402 on Mon 09-13 and Tue 09-14 against about 740 on ordinary weekdays); office logons 46 on landfall day; 137 unexpected shutdowns, 0 lease renewals in the 20 minutes before the boots. Left: SCADA commands (defect 8) |
| 15 | No holidays; nights like days | fixed | Labor Day 12 office logons, Thanksgiving 12, day after 11, 12-24 9, 12-31 10 (weekday median 110, weekend 12); 00:00 to 04:59 local holds 22 of 14,218 logons |
| 16 | Operational tables filled at random | partly | 28 operators, all with control-network accounts; every command fits its device type; service accounts on their own hosts; 45 of 45 remote-desktop commands inside a gateway session that lists the console. Left: defect 8 |
| 17 | Registry statements untrue | fixed | 62 reference-only hosts, none in an alert, session or audit row; counts 329/177/22/74/25/10 correct; public block 12.186.44.64/28 |
| 18 | Triage files dated after collection | fixed | 0 of 6,999 time fields later than `collected_utc` |
| 19 | Endpoint telemetry (USB serials, image variety) | fixed | September: 287 serials on 653 insertions; 254 process images; chrome 993, firefox present |
| 20 | Story steps without records | fixed | exception rule: gateway session RAS-20187 (2027-08-19T11:31:12Z, token, target GW-SRV-SIEM-OT) and its flow exist; archives are in endpoint telemetry and triage with equal sizes and hashes; GW-WS-IT-04 is silent after 2027-10-12T10:04:37Z. Still unexplained in the data: how the contractor account was usable 11 days before the lure |
| 21 | Guide omits streams and misstates | partly | all streams described; three worked network joins verified to the digit. Left: defect 15 |
| 22 | Post-incident records hand over the conclusion | not fixed | defect 12 |
| 23 | Other volume problems (VPN MACs, analysts, flagged addresses, mail) | fixed | 227 VPN devices with one MAC each; analysts work 90 to 116 days in day or night shifts; 96 flagged addresses, each 10+ alerts; all 14,230 internal senders are registry users |
| 24 | Real-world names and address space | partly | "Bastille Networks" and the product-named hosts and accounts are gone; rest in defect 20 |
| 25 | Mixed address conventions | fixed | 0 conn or firewall endpoints in loopback, CGNAT, RFC 1918 (outside the plan) or documentation ranges; vendor sessions from 69.48.219.x and 66.193.54.x |
| 26 | Source country is a zero-noise filter | not fixed | still exactly the 14 hostile sessions (defect 13) |
| 27 | Small format points | partly | hash shortening documented; session ids have 132 gaps; firewall bytes equal Zeek IP bytes on 320,129 of 320,129 rows; 0 triage services without 7045; browser versions agree. Left: 40-byte TCP header constant |
| 28 | Code name | fixed | "GridWater" and "KESTREL" absent from logs, registry, schemas and guides |

## Checked and found sound

- Firewall against Zeek: 297,216 edge and 22,913 boundary allow rows each match a conn.log flow on 5-tuple, end time (within 1.5 s), duration and IP byte counts; every boundary-crossing flow has its row; 0 edge deny rows have a flow; zone labels agree with the registry on every row.
- Web filter against Zeek: 36,447 HTTP rows match host and URI in http.log; 162,364 HTTPS rows match the server name in ssl.log; the 3,830 others are refused or unanswered flows (502/504) and half-open rows; 104,288 blocked rows have no flow; all 196,772 outbound web flows have a web-filter row.
- Zeek internals: every dns, ssl and http row has its conn row; every certificate fingerprint in ssl.log is in x509.log; every http file id is in files.log; no payload above 1,460 bytes per packet.
- Packet captures, all 181 files: valid classic pcap, 1,077,115 packets in time order, 0 bad IP, TCP or UDP checksums, 0 length errors; 296,787 flow openings, each with its first packet at the conn.log timestamp; 165,412 ClientHello server names equal ssl.log (517 others are half-open flows with no ssl.log row).
- Endpoint against Zeek (September): 52,934 `network_connect` events all have their flow within 1 s; 21,138 `dns_query` events all have their dns.log row; the 5,997 Windows-host flows without an event are all browser TLS, as the guide says; 44,750 user-owned events all lie inside a session of that user on that host; all PIDs are multiples of 4.
- Windows: record ids strictly increasing per host; 0 logoffs without logon; 0 logoffs before logon; 1,120 logons from VPN pool addresses all inside a VPN session of that user with that address; lock/unlock only from the administration wing and the control network, always alternating.
- VPN and leases: 2,647 sessions, each with ASSIGN at login and RELEASE at logout, its gateway flow and equal byte counts; no pool address in two sessions at once.
- Triage: all table hashes, row counts and placeholder hashes correct; every logon in Windows Security within each 45-day window is in `logon_history.csv` and the reverse; the gateway's history lists the 14 foreign logons; GW-WS-IT-04 file hashes, sizes and times equal the endpoint telemetry.
- Canon: lure 13:14:09Z; protection off 13:21:44Z (Defender 5001 and `endpoint_protection.csv`); lookalike lookup and 1.88 MB download 13:23:03Z; service 13:24:21Z; first beacon 2027-08-31T03:17:12Z (318 / 212 bytes, 4.2 s, TLS 1.3) in Zeek, firewall, web filter, capture, endpoint and SIEM (`SE3-NET-9941-20270831T0317Z`, closed 14:22Z by SOC-AN-02 with the canon note); last beacon 2027-10-12T10:04:37Z; 14 sessions, first seven 4.100 GB out; historian cluster `HIST-20270907-00441` to `HIST-20271002-00917`, 11,847 tags; relay, file and setpoint changes at canon times and values with a DNP3 or Modbus flow 4 to 6 s before each; suppression 12 to 94 in seven changes; breaker commands 14:28:15Z and 19:43:46Z with console logon and command flow; daily alert counts 4,812 / 7,341 / 18,340 / 16,207 / 14,884 / 12,201 / 6,633 and 2,312 with 11.3 % on 10-19; `daily_summary.csv` equals the alert files on 181 of 181 days; the seven named alert ids exist with the stated dispositions.
- No leak in registry, schemas, catalogue or guide: no hostile address, name, file or account except the owner's legitimate `ot_account`.

## Judgement

Much better than at audit 3: the network plumbing is exact across six log types, the hostile flows are drawn like the background, the leave, isolation and freeze contradictions are gone, and 17 of the 28 earlier items are fully fixed (9 partly, 2 not, both design choices). It is not yet fit to hand out, for three reasons.

1. Three one-line filters on generator artefacts still give the entry point and the key hostile write (defects 1 to 3). Each is a small fix: name the lure attachment and the relay file like their neighbours (or give the neighbours real names), give repeated edits to the same files, and emit the workstation ticket for every interactive logon or for none.
2. The week of 2027-10-12 is broken in every "complete" log (defect 5). Thin only the control-network rule families after the isolation at 12:00Z and leave corporate alerts, web blocks, mail and endpoint events alone.
3. The tables a team would use to argue "unauthorised" do not hold up for ordinary activity: dangling tickets (6), unlogged writes (7), a command log with impossible sequences and no storm (8), random closure notes (9).

Before release also: remove the 22 s, `:07` and 5 s regularities (4); decide and document whether response records are in scope (12); add benign neighbours to the zero-noise filters, at least foreign-travel sessions and large benign files (13); correct the guide sentences in defect 15 and move the SCADA-command hint out of the DNS example. Defects 10, 11 and 14 and the minor items can follow; they cost realism, not the exercise.
