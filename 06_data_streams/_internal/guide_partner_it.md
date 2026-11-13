# Partner organisation IT logs: text for the data guide and notes for the game master

Generator: `scripts/streams/gen_partner_it.py` (model in `partner_it_model.py`, mail in `partner_it_mail.py`, probes in `probes_partner_it.py`).
Registry: `06_data_streams/partner_it_registry.json`.

## Participant-facing text (for DATA_GUIDE.md)

| Stream | What it imitates | Files | Time column | Ids and joins | Notes |
|---|---|---|---|---|---|
| Partner firewall logs | Edge firewall session log | `partner_it/<org>/firewall_<YYYY-MM>.csv` | `time_utc` (**end** of the session; start = `time_utc` − `duration_s`) | `device` → host; internal `src_ip` → host `ip` in `partner_it_registry.json` | Outbound sessions carry the public address they left from in `nat_src_ip`. TCP, UDP and ICMP. Byte counts include packet headers. |
| Partner web gateway logs | Web filtering log | `partner_it/<org>/web_<YYYY-MM>.csv` | `time_utc` | `client_ip` → host; `user` → account | Encrypted sites appear as `CONNECT` with no path. `user` is `-` when the machine itself made the request. Byte counts are payload only. |
| Partner DNS logs | Resolver query log | `partner_it/<org>/dns_<YYYY-MM>.csv` | `time_utc` | `client_ip` → host; `resolver` → host | A client that asked for the same name and record type in the previous five minutes uses its cached answer and is not logged again. `answer` is the address the client then connects to. |
| Partner sign-on logs | Workstation logons and logoffs; single sign-on, webmail and VPN sign-ons | `partner_it/<org>/auth_<YYYY-MM>.csv` | `time_utc` | `host` → host; `account` → account | `event_id` 4624 / 4634 / 4625 on workstations; `sso-login`, `webmail-login`, `vpn-login` on the remote services. A workstation that loses power, or is simply left on, writes no logoff. |
| Partner mail gateway logs | Mail gateway message log | `partner_it/<org>/mail_<YYYY-MM>.csv` | `time_utc` | `gateway` → host; own-domain addresses → account mailbox | Inbound, internal and outbound mail with the gateway's verdict and action. |
| Partner endpoint protection events | Endpoint protection console | `partner_it/<org>/endpoint_alerts_<YYYY-MM>.csv` | `time_utc` | `host` → host; `initiated_by` → account or `system` | Three different products are in use across the organisations; version strings and detection names differ accordingly. |

`<org>` is one of `city` (City of Corpus Christi), `nascc` (Naval Air Station Corpus Christi, unclassified administrative network), `brw` (Brightwake Marine Systems, Houston), `port` (Port of Corpus Christi Authority), `srmc` (Shoreline Regional Medical Center), `bcmc` (Bay City Medical Center), `county` (Nueces County). All seven cover 2027-07-16T00:00Z to the end of 2028-01-12 UTC.

- **These are seven separate networks.** Each has its own address plan, rule and zone names, web policy, products and working habits. A value that is ordinary in one folder may not exist in another.
- **What is complete and what is a sample.** Workstation logons and logoffs and remote sign-ons are complete for the hosts and accounts in the registry. Web, DNS and endpoint records are a sample of ordinary activity (about 1 in 40); mail is a sample (about 1 in 25, bulk mailings more completely). Firewall sessions that carried a remote sign-on or a logged mail message are all present; other firewall sessions are a sample. Do not compute traffic volumes from the sampled logs without scaling.
- The registry lists the hosts that are modelled, not every device an organisation owns. An account without a workstation in the registry can still receive mail and sign on remotely.
- Where a mail gateway stands in the organisation's own network, the mail it exchanges with outside servers also appears as sessions in the firewall log. The city's gateway is a hosted service, so its mail does not cross the city's firewall.
- Internal traffic (for example base clients using the base logistics system) does not cross an edge firewall or the web gateway and is not in these logs.
- Outside names and addresses are invented. `src_network` gives the network of an outside address as `ASN <number>`; the labels come from one table (`scripts/streams/netmap.py`), so the same address carries the same number in every stream that records one.
- People are pseudonymous ids; the vendor's staff are invented names.
- Four tables in `network_logs/audit/` are cut from these logs, row for row: `mail_gateway_city.csv`, `mail_gateway_airstation.csv` and `account_logons_city_airstation.csv` (2027-09-12 to 09-21) and `mail_gateway_brightwake.csv` (2027-07-16 to 08-24). The two `mail_url_clicks_*.csv` tables are the mail gateways' own reports of every link in delivered mail that a recipient followed in the same windows, with the client address as the gateway saw it. A link followed at a workstation is also in that organisation's web, DNS and firewall logs; a link followed on a phone or at home shows an outside address and never crossed that network.

## What follows canon or another delivered stream (game master; not for participants)

| Behaviour in the logs | Source |
|---|---|
| County and city alerting workstations are logged on and send to the origination service 3 to 25 s before each alert's issue time; a second transmission at the Spanish wireless-alert time when it differs. The same service is also contacted for a weekly proficiency check and occasional console sign-ins, which transmit nothing | `public_health/eas_broadcasts.csv` (`AlertSource` NCOEM → county; CCOEM and Corpus Christi Water Department → city), canon `alerts` |
| County mailbox `eoc.pio` sends each translation request and receives each delivery at the logged times | `broadcast/translation_jobs.csv` (translator NCLAS) |
| Port operations mailbox receives each Coast Guard order within ten minutes of issue and sends the port's own storm-log notice; gate offices work until Port Condition Zulu is set (2027-09-13T16:10Z) and follow the channel windows afterwards (0 from landfall to D+3, about a quarter of normal to D+30, then 0.6, 0.35 during the D+44 to D+58 closure, normal from D+58) | `supply/port_conditions.csv`, canon `port.channel_windows` |
| Hospitals: commercial power lost, generator start and restoration times; clinical workstations are back nine minutes after the generator starts; clinical workstation unlocks follow emergency-department visits | `public_health/hospital_capacity.csv`, canon `power.hospital_power`, `health` |
| Air station: staffing drops with the aircraft evacuation (D-4) and recovers from D+6; non-critical buildings dark while the backup generator carries critical loads; everything, including the edge, dark during the commercial power interruption on the day the generator fails (2027-10-24) | `maintenance/base_status_reports.csv`, canon `military_aviation`, `power.nas_generator` |
| Air station: every outside request in the base logistics log has an inbound firewall session to the system's public address; no other session to that address gets past the handshake | `network_logs/portal/base_logistics_access_*.csv` (run `gen_itsec.py portal` first) |
| City and air station: 840 + 360 aid-themed messages between 2027-09-15T13:00Z and 09-18T02:00Z; seven city and three air-station recipients click the link from their own registered workstations some minutes to hours after receiving it (DNS query, web request, firewall session); each click is followed 0.5 to 9 hours later by a successful password-only sign-on on a new device from 203.0.113.17-80 (`ASN 64512`). Ordinary staff also sign on from that provider (other addresses in 203.0.113.120-250), with a password only, and on new devices; the ten are found by what precedes them and by the network being new to the account | canon EVT-0306; `partner_it_model.wave`, `story_clicks`, `story_signons` |
| Vendor: certificate-renewal message to the shared support mailbox at 2027-08-12T14:41:07Z, clicked at 15:02:07Z from the duty engineer's workstation (leaving through the office egress pool); every session in the vessel remote-session log at the gateway firewall; office sessions also as an outbound session from that engineer's workstation leaving from the logged address, VPN sessions preceded by that engineer's VPN sign-on; sessions from the third network have no counterpart inside the vendor's network | canon EVT-0107, EVT-0209; `telemetry/vessel_cargo_control_remote_sessions.csv`, canon `spill`, `investigation_and_attribution` (D+8) |
| None of the seven organisations visits the aid portal; the aid portal's own access log is complete and shows no such request | `network_logs/portal/aid_portal_access_*.csv` |

## Generated detail that canon does not state

These were needed to make the logs behave; change them in `partner_it_model.py` if canon later says otherwise.

- Site power windows other than the hospitals and the air station: City Hall 2027-09-14T06:48Z to 09-18T15:20Z, Public Works Service Center to 09-20T16:00Z, libraries to 09-23T18:00Z; County Courthouse 09-14T06:55Z to 09-18T17:05Z, Public Health District to 09-16T14:00Z; port administration building and gate offices 09-14T06:41Z to 09-18T20:00Z. Emergency operations centres, public safety, the water department offices, port security, the harbormaster office and every server room are on backup power (`backup_power` in the registry's site list).
- Office closures: City Hall, the courthouse and the port administration building close at noon on D-1 and reopen on D+6 (Monday 2027-09-20) at about 70% staffing until D+13; remote sign-ons fall on landfall day and run above normal while the buildings are closed.
- Emergency operations centres are staffed round the clock from D-3 (city) and D-5 (county, the day the translation standby was placed) to D+35.
- Air station storm outage starts 2027-09-14T06:35Z and ends at 09:40 local on the day after the last "carrying load" status report; the 2027-10-24 interruption is 18:52Z to 23:47Z.
- Hospital administration wings are without power for the first 48 hours on generator.
- Which engineer holds which remote-maintenance account (`BRW_ENG` in the model), and that the duty engineer for the shared mailbox on 2027-08-12 was the holder of `bw-eng-07`.
- Address plans, host names, products, rule names, the alert origination service name `origination.alertgateway.example`, bulk mailings (training assignments, benefits enrolment, all-staff notices), access providers and their address space. The vendor's published services, office egress pool and staff VPN egress pool are one block next to its remote-maintenance gateway (see the registry's address plan); the vessel remote-session log shows the same addresses.

## Commands

    python3 scripts/streams/gen_partner_it.py --all --resume      # registry, seven organisations, extract tables; about 80 s (repeat if it prints "more to do")
    python3 scripts/streams/gen_partner_it.py CITY [2027-09]      # one organisation; then: gen_partner_it.py extracts
    python3 scripts/streams/probes_partner_it.py                  # 41 probes
