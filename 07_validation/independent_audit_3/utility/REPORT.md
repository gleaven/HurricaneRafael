# Independent audit 3: utility IT and security logs

Scope: `05_other_sources/network_logs/` (siem, zeek, audit, firewall, proxy, dhcp, pcap, windows, endpoint, triage), the registry `06_data_streams/gw_host_registry.json` and the participant-facing guides. Nothing outside this folder was written. `portal/` was not reviewed (it belongs to the aid-fraud and air-station threads, not to the utility intrusion). Pass 3 joins on endpoint telemetry, Windows sessions and web-filter users were run on September 2027 only; packet captures on four days.

How to reproduce: run `./build_cache.sh` once (concatenates Zeek, firewall, proxy and DHCP into `/tmp`), then `python3 checks.py <name>`; `python3 checks.py list` shows the 25 named checks. The `p1_*`, `p2_*`, `p3_*` scripts are the pass-specific scans and joins.

## Pass 1 summary (blind: data, registry and guide only)

The first hostile records surfaced after about two minutes (a count of `close_note` in the SIEM files). Within roughly 25 minutes of counting values, with no real analysis, I had the whole chain: lure mail 2027-08-30T13:14Z to `dgonzalez`, execution on GW-WS-IT-04 at 13:21, download from `update-cdn.meridiancontrols.net` at 13:23, service `vstelemetry.exe` at 13:24, 167 beacons to 104.21.88.43, the whitelist and the exception rule, the 14 remote sessions as GW-ENG-VELA, the historian reads, the relay and setpoint changes, the 82 suppressed alarms, the two breaker commands, detection on 2027-10-02 and clean-up on 2027-10-12. Almost every step was reachable by one `sort | uniq -c` or a one-column filter. Defects 1 to 6 list the filters.

## Defects

### Blockers

**1. Hostile flows are complete while everything else on the same hosts is a 1-in-200 sample, so plain counting ranks the command channel first.**
The most frequent (internal host, internet address) pair in six months of `conn.log` is 10.14.22.47 -> 104.21.88.43 with 168 flows; the next pairs are OCSP lookups at 93 to 101. GW-WS-IT-04 has 917 internet flows in total (fleet median 793), so 18 % of its outbound flows go to one address. The stated rule ("everything involving a host that has an alert or a remote session is complete") is not what the data does: IT-04's background is sampled like any other host, only its hostile flows are complete.
Repro: `python3 checks.py top_pair`

**2. One TLS cipher suite is used only by the command channel.**
`ssl.log`: `TLS_AES_256_GCM_SHA384` occurs on 168 rows, all 10.14.22.47 -> 104.21.88.43 (167 `update-cdn.vantagesec-telemetry.net`, 1 `update-cdn.meridiancontrols.net`). The other 57,005 rows use two other suites. The same marker is in the packet captures: ServerHello cipher 0x1302 appears only on those flows (4 days checked).
Repro: `python3 checks.py ssl_cipher`; `python3 p3_pcap_check.py 2027-08-30 2027-10-02`

**3. Hand-placed flows carry whole-second timestamps, integral durations and round byte counts.**
`awk '$1 ~ /\.000000$/'` over `conn.log` returns 81 of 557,106 rows: all 14 inbound sessions from the 185.220.101.x / 45.141.152.x / 198.51.x addresses, the 14 gateway-to-historian flows, the three RDP hops, both breaker-command flows (10.72.2.12 -> 10.72.1.30:4000, same source port 49800 and same 880/640 bytes on both days), the staging flow 10.14.22.47 -> 10.72.4.20:445 (exactly 4,100,000 / 1,900,000,000 bytes, 2710.5 s), the 22:11Z write to GW-SRV-OT-01, the 13:23Z lookup, and the 45 DNP3/Modbus flows behind the gateway rows of `ot_config_changes.csv`. 80 of the 81 have a duration ending in `00000`. No background row has this form.
The audit table and the network also disagree only for the hostile sessions: for all 869 US remote sessions `bytes_in` equals Zeek `orig_bytes`; for the 14 hostile ones it never does (RAS-20268: 2,222,514 vs 2,175,800) and the Zeek value is a multiple of 100 in 14 of 14 cases (6 of 869 otherwise). Zeek duration is session duration + 2.000 s for the hostile sessions and + 2.2 to 2.9 s for the others.
Repro: `python3 checks.py zeek_ts_round ras_bytes`; `python3 p2_story_crosscheck.py`

**4. SIEM dispositions and notes isolate the story alerts, and the exception rule contradicts itself.**
- `close_note`: 27 notes are used 679 to 51,485 times each; seven notes are used 1 to 39 times and every one is a story alert (`WL-NET-0117` 39, `exception rule MAINT-EXCEPT-0892` 13, `Storm preparation` 3, `Restoration work, nuisance alarms` 2, three used once).
- `priority`: 458,969 alerts are INFO, LOW or MEDIUM; the 6 HIGH and the 1 ANOMALY_HIGH are all story alerts.
- `rule_id = SE3-OT-1104 and disposition = AUTO_ACK` gives exactly 13 hostile historian sessions; `SE3-NET-9941 and AUTO_ACK` gives exactly 39 beacons.
- MAINT-EXCEPT-0892 reads "auto-acknowledge SE3-OT-1104 when source is GW-SYS-JMP-01" and was active 2027-08-19 to 2027-10-18. In that window 440 such alerts came from GW-SYS-JMP-01; 13 were auto-acknowledged (the hostile ones) and 426 were handled by analysts. The rule as written would have acknowledged all of them.
Repro: `python3 checks.py exception_scope`

**5. The audit tables and the SIEM agree only where the story is: a join returns the answer, and the background contradicts itself.**
- Historian: 4,952 `HISTORIAN_BULK_QUERY` alerts; 14 match a row of `historian_access.csv` on account + tags + duration, and they are the 14 hostile sessions. Of the 1,326 rows of `historian_access.csv`, 14 have a Zeek flow from the client to the historian at the start time, the same 14. 150 of 170 benign remote sessions that list GW-SRV-HIST-01 as target have no historian row at all.
- Hostile historian sessions have round durations (12 of 14 are whole minutes, six are exactly 1500 s; 19 of 1,312 otherwise) and eight `tag_groups` values that occur once each and nowhere else (e.g. `relay_config(all 5 substations)`).
- Alarm suppression: `alarm_suppression_audit.csv` has 176 rows, 164 of them the story (82 ADD by GW-ENG-VELA, 82 REMOVE under SI-2027-CC-001). The 12 background rows are a fixed three-day rota that ends 2027-08-04; there is no background row afterwards and no background REMOVE ever. The SIEM has 1,653 `ALARM_SUPPRESSION_CHANGE` alerts; 7 have an audit row. Background alerts report `suppressed_alarm_count` 11 to 15 in every month, including 2027-09-09 to 2027-10-12 when the audit table holds 18 to 94 (`SE3-OT-3301-20270923T0400Z` says 94; `SE3-OT-3301-20270923T0400Z-2`, 22 seconds later, says 14). Story alarm points are named `ALM-30nn (label)`, background ones `ALM-21nn`.
- File integrity: 160 of 161 rows of `file_integrity.csv` have seconds `:00`; the other row is the hostile write (`2027-09-11T22:11:07Z`, `relayconfigs\sub02\rtu_config_draft.xml`). The table (161 rows, random hex file names) and the 2,589 `OT_FILE_WRITE` alerts (`projects\woNNNN\notes.docx`) describe disjoint sets of files; 20 alerts fall near a table row.
- Windows 5145: 2,750 events on GW-SRV-OT-01, all `WriteData`; the only `ReadData` events in the data set are the 8 hostile reads on GW-SRV-HIST-DMZ.
Repro: `python3 checks.py hist_join supp_counts fim_seconds win_counts`; `python3 p3_alert_vs_audit.py`

**6. The lure mail is the only row of its kind in 61,872.**
`mail_gateway_cbpwa.csv` has 24 subjects; 23 occur 1,983 to 4,676 times, "FEMA hurricane preparedness guidance for utilities" once. Its sender domain is the only one of 1,030 used once and its attachment is the only `.exe`. The gateway quarantined 20,496 attachments for their type (`.img`, `.htm`, `.xlsm`) and delivered `FEMA-PREP-GUIDANCE-2027.pdf.exe` as `clean`.
Repro: `python3 checks.py mail_unique`

**7. Activity under GW-ENG-VELA during his leave that is not part of the story.**
Leave is 2027-09-06T22:00Z to 2027-09-22T06:00Z (generator; "an engineer who is on leave" in the expected observations). In that window the SIEM has 13 `HISTORIAN_BULK_QUERY` and 5 `OT_FILE_WRITE` alerts for GW-ENG-VELA from GW-WS-ENG-03 (e.g. `2027-09-13T08:28:37Z ... projects\wo4100\notes.docx`, 03:28 local), and Windows Security has the 5 matching network logons and writes on GW-SRV-OT-01 from 10.72.1.43. No interactive logon on GW-WS-ENG-03 stands behind any of them. There are also 13 `VPN_NEW_LOCATION` alerts for `rvela`. The "account used while its owner is away" signal, the intended honest route, is polluted by background noise, and the catalogue's statement that alerts "name someone who is at work on the machine they are logged on to" is false for these rows.
Repro: `python3 p2_vela_leave.py`

**8. Three of the seven alarm-suppression changes have no session behind them.**
`alarm_suppression_audit.csv` attributes batches at 2027-09-13T04:41Z (9 points), 2027-09-16T08:22Z (14) and 2027-09-19T05:37Z (12) to GW-ENG-VELA from GW-SYS-JMP-01, and the SIEM raises the alerts. There is no row in `remote_access_sessions.csv`, no logon on the gateway and no firewall or Zeek flow at those times; the 14 sessions cover only the other four batches (09-09, 09-11, 09-21, 09-23). Canon gives 14 sessions and 7 changes; as the logs stand the two cannot both hold.
Repro: `python3 p2_vela_leave.py`; `python3 checks.py supp_counts`

**9. Historian sessions cross the IT/OT boundary during the isolation window; changes continue during the change freeze.**
- Isolation runs 2027-10-12T12:00Z to 2027-10-19T18:00Z. The boundary firewall shows 0 allowed sessions and 704 `EMERG-OT-ISOLATION` denies (685 of them historian replication) and there are 0 remote sessions, which is right. But `historian_access.csv` has 20 sessions in the window from GW-SRV-OMS-01 (corporate data centre) and GW-SRV-HIST-DMZ into GW-SRV-HIST-01, e.g. `HIST-20271012-01077`.
- `CHG-FREEZE-27-09` (2027-09-10T21:00Z, "all OT configuration changes suspended until further notice", status ACTIVE, never lifted) is followed by 14 ticketed background changes in `ot_config_changes.csv` before the isolation and by 27 "Approved change" records in `change_management.csv`. Canon relies on the freeze to make the 09-11 changes unauthorised.
Repro: `python3 checks.py isolation freeze`

### Major

**10. The sampling rule is stated in a form that cannot be true, and logs mix complete and sampled rows without saying so.**
"Everything involving a host that has an alert" covers 240 of 329 hosts, including all 162 workstations (each has `POLICY_BLOCKED_SITE` alerts), yet workstations have a median of 2,312 non-scan flows in 181 days. In the web-filter log the 108,663 blocked rows and the 69,966 DNS rows are complete (they equal the alert counts) and the 135,522 allowed rows are the sample, so the raw blocked share is 44 %. The 28,885 employee VPN sessions are complete. None of this is in the guides.
Repro: `python3 checks.py top_pair`; `python3 p3_net_join.py`

**11. Web-filter DNS rows do not line up with `dns.log`.**
Of 69,966 `scheme = dns` rows, 1,688 have a `dns.log` row for the same client and name within 2 s; 59,404 are off by up to 300 s either way (median -10.6 s) and 8,874 have no row at all. The guide says client and second match and that the clocks agree to the second.
Repro: `python3 checks.py proxy_dns_offset`

**12. Zeek logs: constants and combinations that a sensor cannot produce.**
- All 177,743 DNS flows have duration 0.004000 s, 44 bytes out, 92 bytes in and 4 packets each way, whatever the query name.
- All 76,878 `S0` rows have `resp_pkts` 4 and duration 0.000000.
- 108,037 of 165,210 `conn.log` rows with `service ssl` have no `ssl.log` row.
- 10,480 `ssl.log` rows pair `TLSv12` with the TLS 1.3 suite `TLS_AES_128_GCM_SHA256`; 2,090 of them are `resumed T` and still list a certificate chain.
- 29,875 of 43,055 flows with more than 1 MB received have fewer than a quarter as many originator packets as responder packets (e.g. 4 against 2,965).
- Six months contain 24 protocol/port/service combinations and 8 `history` strings: no NTP, SMTP, SSH service or ICMP, no UDP other than client-to-DC DNS, no resolver traffic from the DCs to the internet, although the mail gateway logged 61,872 messages. `http.log` has 8 user agents and status codes 200/301/302 only. 534 of 559 notices have `msg` `-`.
- 869 rows are `OTH` with history `Aa` but full byte counts and `service ssl`.
Repro: `python3 checks.py conn_constants ssl_missing ssl_cipher`; `python3 p1_zeek_conn.py`

**13. Windows Security log internals.**
- 1,845 logon ids have two to nine 4624 events on the same host within a second (3,923 surplus events), each followed by as many 4634, e.g. GW-WS-IT-105 `0xc7321e1` at 2027-09-01T11:09:54.040, .369 and .777Z.
- 99,695 failed logons (4625) against 54,584 successful ones; 92,280 failures are type 7 (unlock); 4625 comes from 183 hosts although lock/unlock is forwarded from 37.
- 418 of 805 group-membership events (4728/4732/4756) have an empty subject user; the rest are made by ordinary staff from 93 different workstations.
- Exactly one 4771 per lockout (2,644 and 2,644); every 4672 carries the same three privileges.
- 8,853 of the 4624 events have `logon_id` before `logon_type` in the JSON, exactly the number of `LOGON_OUTSIDE_HOURS` alerts: key order marks which logons were generated from an alert.
Repro: `python3 checks.py dup_logons win_counts`; `python3 p1_win_scan.py security`

**14. The storm does not behave like a storm.**
- SIEM hourly counts step at UTC midnight and are flat within each day: 269 to 759 at 2027-09-14T00:00Z (19:00 local, six hours before the outage begins), 63 to 212 at 2027-09-12T00:00Z. `UPS_ON_BATTERY` on 09-14 is 49 in hour 00 and 47 in hour 12.
- Alerts driven by people rise with it. Landfall day against 09-08: `POLICY_BLOCKED_SITE` 1,098 against 611, `LOGON_OUTSIDE_HOURS` 411 against 42, `PUP_DETECTED` 62 against 20, `USB_STORAGE_MOUNTED` 77 against 33, `ADMIN_GROUP_CHANGE` 21 against 4. Office staff have 403 interactive logons on 09-14 (weekday median about 137) while 137 office hosts log an unexpected shutdown that day and allowed web rows fall from about 950 to 392.
- 14 hosts have a DHCP renewal, and one a web-filter row, within 20 minutes before the boot that follows their power loss (GW-LT-FLD-92: five renewals between 05:10 and 08:05Z, boot at 08:22Z).
Repro: `python3 checks.py storm_hourly`; `python3 p3_calendar.py`; `python3 p3_power_gap.py`

**15. No public holidays, and nights look like days.**
Labor Day (Mon 2027-09-06) has 118 office logons and 958 web rows, Thanksgiving 113 and 958, the Friday after 151 and 891, Fri 12-24 157 and 949, Fri 12-31 118 and 965; an ordinary weekday has about 137 and 950. On weekdays 67 % of office logons fall in 06:00 to 07:59 local; the other hours are flat, with 00:00 to 05:59 (258 to 325 per hour of day) busier than 09:00 to 16:59 (184 to 264).
Repro: `python3 p3_calendar.py`

**16. Operational tables are filled at random.**
- `scada_command_log.csv`: 148 operators issue 401 commands; 107 of them have no control-network account. Customer Service issues 26 commands, Finance 24, HR 10 (`2027-07-28T18:55:11Z`, HR Generalist `dzamora`, BREAKER OPEN GW-SUB03-CB-9). Commands do not fit devices (CAP BANK SWITCH and TAP RAISE on circuit breakers).
- `ot_config_changes.csv`: relay time dials on the water-plant DCS, pump discharge setpoints on substation RTUs, an LTC band on a booster station (11 device/parameter pairs, 16 rows).
- `historian_access.csv`: the three service accounts are spread evenly over three client hosts (50 to 69 each), so `svc_oms` connects from the SCADA server and `svc_scada_hist` from the outage-management server; the registry gives each account its own hosts.
- For the record: the two hostile breaker commands have an empty `operator`, but so do 9 of the other 48 remote-desktop commands, so that field is not a giveaway.
Repro: `python3 checks.py scada_ops freeze hist_join`

**17. The registry says things about the logs that are not true.**
- `reference_only`, reason "staff account with no remote session or alert in the logs": all 133 such users are named in SIEM alerts.
- `reference_only` hosts "with no alert, session or audit record": GW-WS-OPS-02 (329 alerts; the console used for both breaker commands; one of the 14 triaged hosts), GW-WS-OPS-03, GW-WS-OPS-04, GW-WTP-HMI-01, GW-VPN-EMP-01.
- `svc_fieldops_ext` is marked "service account with no audited session": it has 23 remote sessions and 27 historian sessions and is the author of MAINT-EXCEPT-0892. `svc_oms`, `svc_hist_repl` and `svc_scada_hist` have 164 to 183 historian sessions each.
- `metadata.public_address_block` is 203.0.113.16/28; the firewall, the captures and the guide use 12.186.44.64/28. `counts.equipment` is 72; there are 74.
- The registry's vendor systems (`support.meridiancontrols.example` 192.0.2.210, `telemetry.vantagesec.example` 192.0.2.220) never appear in any log; legitimate vendor traffic goes to `www.meridiancontrols.com` and `static.vantage-security.com`. A participant who wants to compare the lookalike names with the registry has nothing to compare.
Repro: `python3 checks.py registry_flags names`

**18. Triage file listings contain files dated after the collection.**
101 rows in 10 of 14 `file_listing.csv` have a creation or modification time later than `collected_utc`, up to 2028-06-07, five months after the data set ends (GW-SRV-OT-01 24 of 36 rows, GW-WS-OPS-04 22 of 104, GW-WS-IT-33 20 of 83; GW-WS-IT-04 `CcmExec.exe` modified 2027-12-12 in a collection taken 2027-10-12).
Repro: `python3 checks.py triage_future`

**19. Endpoint telemetry.**
- 5,097 USB insertions use 5,097 different device serial numbers.
- 106,237 process starts use 32 images and DNS lookups come from 4 images; two of each are the malware. The lure binary (1 start) and the implant (3) are among the four rarest images. A rare binary is a fair finding, but there is not one benign one-off executable in six months.
- `http.log` and the web filter show Chrome and Firefox user agents; no `chrome.exe` or `firefox.exe` ever starts. `invagent.exe` makes 31,537 connections, never starts and is in no installed-software list. `OUTLOOK.EXE` and `msedge.exe` start exactly 17,334 times each.
Repro: `python3 checks.py usb_serials`; `python3 p1_endpoint_scan.py report`

**20. Story steps without supporting records.**
- MAINT-EXCEPT-0892 is created 2027-08-19T11:34:20Z by `svc_fieldops_ext`, 11 days before the first recorded access (2027-08-30). No log shows that account logged on anywhere at that time (that day it has a service logon at 08:33Z and a remote session at 20:55Z) nor any connection to the SIEM server. Nothing in the data explains how the adversary held the account before the lure.
- The 1.9 GB pulled to GW-WS-IT-04 on 2027-09-08 leaves no file in the endpoint telemetry or in the triage file listing (largest file 6.8 MB) and never leaves the host (beacons carry about 300 bytes).
- GW-WS-IT-04 keeps producing endpoint telemetry and DHCP renewals through December (424 events in November) after being triaged; there is no reimage or shutdown record.
Repro: `grep svc_fieldops_ext windows/security_2027-08.jsonl | grep 2027-08-19`; `sort -t, -k2 -n triage/GW-WS-IT-04/file_listing.csv | tail -1`

**21. Participant guide.**
`11_hackathon/DATA_GUIDE.md` does not describe the firewall, web-filter, DHCP, capture, Windows, endpoint or triage streams (they exist only in `_internal/guide_itsec_*.md`), and its Zeek row lists `conn, dns, ssl, notice` although `http`, `files` and `x509` are delivered. Untrue statements, as shown above: "clocks agree to the second" (defect 11); "`user` is whoever was logged on" (812 September rows have `-` while a session is open); the sampling paragraph (defect 10). I found no sentence in the guides that points at what is hostile.
Repro: `grep -n -i -E "firewall|proxy|dhcp|pcap|endpoint|triage" 11_hackathon/DATA_GUIDE.md`

**22. Post-incident records hand over the conclusion (design decision to confirm).**
`ls triage/*/placeholders` names the first compromised host and both binaries; every `collection.json` carries case `SI-2027-CC-001`; `rule_changes.csv` (7 rows) says the exception rule was "removed (AUDIT-EXC-2027-10)"; `change_management.csv` has a "Security incident" row; the 82 REMOVE rows and four restore rows cite the incident number. If teams receive the full span, the hunt reduces to reading these. If that is intended, say so in the guide; if not, cut the delivery before 2027-10-02.

**23. Other volume and behaviour problems.**
- VPN pool: 13,414 sessions without a hostname use 13,414 different MAC addresses, a new personal device every time, for 177 staff. All 66,975 MAC addresses in the lease log start `02:`.
- The three analysts each close alerts on all 182 days and in all 24 hours of the day; nobody has a day off or a shift.
- 5,951 background `FLAGGED_IP_OUTBOUND` alerts name 5,951 different addresses, each once; the only address seen twice or more is the command address (44 times).
- Mail: all 8,343 internal senders are hex strings (`435a6b@cbpwa.example`) while recipients are registry usernames; the three verdicts are each a third of the log (20,943 / 20,496 / 20,433).
Repro: `python3 checks.py dhcp_vpn siem_analysts exception_scope mail_unique`

### Minor

**24. Real-world names and address space.** 185.220.101.0/24 with AS-60729 is a well-known real anonymiser range; AS-7018, AS-22773, AS-20057 and AS-11427 are real carriers; 104.21.88.0/24 and 12.186.44.64/28 are real allocations. "Bastille Networks" (firewall vendor in the registry) is a real company. `svc_maximo`, `maximo_assetnum`, `GW-SRV-MAXIMO-01`, `svc_sccm`, `svc_wsus` name real products. USB models "Ultra Fit", "Store-n-Go" and "Extreme" are real product names. `dns.log` has 44,259 invented names on real top-level domains (some are certainly registered, e.g. `hotel-reservations.com`) against 6 under `.example`; the mail log has 1,028 sender domains outside `.example`. Repro: `python3 checks.py names`

**25. Mixed address conventions.** Vendor remote sessions come from 192.0.2.223 (documentation range, AS-64499) while employees and the adversary use routable addresses. 31 flows go to 127.x.x.x, 10 to 100.64/10 and one each to 192.168/16 and 172.16/12 as if these were internet hosts. Repro: `python3 checks.py reserved_ips`

**26. Source country is a zero-noise filter.** `src_country != US` returns exactly the 14 hostile sessions; no employee connects from abroad in 869 sessions. A fair analytic, but with 100 % precision. Repro: `python3 checks.py ras_bytes`

**27. Small format points.** `file_integrity.csv` labels 16-hex-digit values `sha256=`. Remote-session ids are contiguous (20001 to 20883). Triage lists Edge 127 while the user agents say 139. Two triage services (on GW-WS-IT-33 and GW-WS-OPS-04) have no 7045. Firewall byte counts equal Zeek payload bytes on all 188,273 rows, though a firewall counts packet bytes. Every TCP packet in `conn.log` has exactly 40 bytes of header.

**28. Code name.** "GridWater" and "KESTREL" do not occur in the logs, the registry or the guides. The initials survive in the host prefix `GW-` and in the file name `gw_host_registry.json`. Repro: `python3 checks.py names`

## Checked and found sound

- Firewall against Zeek: all 188,273 allowed firewall rows match a `conn.log` row on 5-tuple, end time (within 1.5 s), bytes and duration; all 185,323 boundary crossings are in the right firewall log, internet-to-DMZ flows in both. (`p3_net_join.py`)
- Web filter against Zeek, HTTP and HTTPS: all 135,522 allowed rows have their flow with equal byte counts; 51,727 of 51,727 server names match where `ssl.log` has the row; 108,635 of 108,663 blocked rows have no flow. (`p3_net_join.py`)
- Endpoint against Zeek, September: 57,958 `network_connect` events and 57,958 TCP flows from Windows hosts match one to one within 0.5 s; 30,463 `dns_query` events all match `dns.log`. All PIDs are multiples of 4. 53,440 of 53,577 user-owned events lie inside a logon session of that user on that host; the 137 others belong to sessions opened in August. (`p3_endpoint_join.py 2027-09`)
- Packet captures, four days: valid classic pcap, time-ordered, IP and TCP checksums correct, handshake then ClientHello with the right server name; 2,833 of 2,842 edge flows have their SYN at exactly the `conn.log` timestamp, and the 9 others are mid-stream `OTH` rows (verified for 08-30). (`p3_pcap_check.py`)
- Web-filter user against Windows sessions, September: 46,687 rows name a user with an open session on that host; 276 do not (sessions opened before the month). (`p3_win_sessions.py 2027-09`)
- Windows: `record_id` strictly increasing per host and channel (75,295 September events, 0 violations); files time-ordered; Defender 1116 events 5,220 = 4,936 `PUP_DETECTED` alerts + 284 table rows; 4740 events 2,644 = lockout alerts; group changes 805 = alerts; USB events 5,097 = alerts.
- SIEM: no duplicate alert id, no alert closed before it was raised, `daily_summary.csv` equals the alert files on all 181 days.
- Canon figures: 14 sessions; durations sum to 41,348 s (11.49 h); first seven sessions 4.100 GB out; 11,847 tags over the 14 historian sessions; daily alert counts 4,812 / 7,341 / 18,340 / 16,207 / 14,884 / 12,201 / 6,633; 2,312 alerts and 11.3 % on 2027-10-19; suppression 12 to 94 in seven changes; first beacon 2027-08-31T03:17:12Z (318 / 212 bytes in Zeek, firewall and web filter), last 2027-10-12T10:04:37Z; relay, file and setpoint changes at the canon times and values; remote-desktop logon on GW-WS-OPS-02 95 s before the 09-21 breaker command; the named alert ids exist with the stated dispositions.
- The 2027-08-30 chain on GW-WS-IT-04 is consistent to the second across mail gateway, endpoint telemetry, Defender, System log, Zeek, web filter and capture.
- Remote sessions: every target of every session (1,037 targets) has a flow from the gateway during the session; every external session has its flow on both firewalls and its logon on the gateway.
- Isolation window: 0 allowed boundary sessions, 0 remote sessions, 704 denies, first allowed session 2027-10-19T18:02Z.
- Triage: all 112 table hashes and row counts in `collection.json` are right; placeholder hashes equal the hashes in the logs; every `logon_history.csv` row is in Windows Security; 33 of 35 services installed in the span have their 7045.
- Registry: 329 hosts, no duplicate address, every address inside its zone.

## Judgement

The plumbing is good: firewall, web filter, endpoint telemetry and captures agree with Zeek to the row, and the canon numbers are all there. The data set is still not fit for the exercise, for two reasons. First, the hostile records were written by a different code path from the background and it shows everywhere: whole-second timestamps, round byte counts, a private cipher suite, unique notes, subjects and tag groups, complete flows in a sampled sea. A participant needs no analysis; counting values finds every stage in minutes. Second, the background is thin or random exactly where the story lives (alarm suppression, historian access, file integrity, SCADA commands, the change freeze, the absent engineer), so those tables either contain only the answer or contradict it.

What to do: draw story rows through the same functions as background rows (timestamps, sizes, ciphers, note vocabulary); give the audit tables a real background that agrees with the SIEM; remove the leave and isolation violations and the three orphan suppression batches; correct the registry flags and the guide. Then rerun `checks.py`: each blocker check should return either nothing or a crowd.
