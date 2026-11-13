# Independent audit 4: partner organisation IT logs and portal access logs

Reviewer: independent second review, 2026-11-12. Nothing outside this folder was modified.

**Not fit to hand out yet.** The partner logs are much improved (14 of the 24 earlier items are fixed outright), but the two portal logs, which were not reviewed before, still give every hostile record away with one value count, the fix for the hostile address range only moved the boundary from a /24 to a /25, and one cross-stream contradiction with canon is new (hospital administration wings active while the hospital has no commercial power).

Scope: 294 partner files (805,611 rows), 14 portal files (406,504 rows), 6 extract tables, the registries, schemas, catalogue and guide, and the delivered streams they must agree with.

How to reproduce: `python3 <script>` from this folder. `common.py` builds a pickle cache under `./_scratch/cache4` on first use (about 10 s). Every script runs in under 60 s. Outputs of the longer ones are saved as `out_*.txt`. `PASS1_NOTES.md` lists the blind tricks in the order they were run.

## Pass 1: how fast each story fell out (data, registries, schemas and guide only)

| Story | Reached at | Filter | Kind |
|---|---|---|---|
| Aid-portal probing, credential stuffing, 410 takeovers, 6 planted applications | first value count on the portal log | `client_network = ASN 64512` (or `user_agent_family = python-requests`) | trivial filter on an artefact: **blocker** |
| Logistics-system probing | same command | same | **blocker** |
| Ten stolen sign-ons (city 7, air station 3) | command 8 by following the click report; command 9 by a last-octet histogram | `src_ip` in 203.0.113.0-99 | the join is genuine analysis; the address filter is an artefact: **blocker** |
| Lure wave (1,200 messages) | command 4 | new sender domain with 840 + 360 messages in four days, among three benign bulk domains | genuine analysis, acceptable |
| Vendor lure and click | command 12 | one uncategorised web host seen once; also handed over by `mail_url_clicks_brightwake.csv` | acceptable |
| Vendor gateway misuse (12 long sessions, two across the valve window) | command 6 | sessions of 300 s or more at `BRW-FW-DMZ-01` whose source is not the vendor's /24 | genuine analysis, acceptable; also caught by the address filter above |
| 94 applications from one address | command 11 | accounts created per client address | genuine analysis, acceptable |

## Defects

### Blockers

**1. In both portal logs one network label and two user-agent values occur only on hostile records.** (`p1_portal_vc.py`, `p3_verify_numbers.py`)
- `aid_portal_access_*.csv`: `client_network = ASN 64512` on 223,605 rows, all hostile: 2,720 probe rows (2027-08-10T05:01:01Z to 08-13T04:58:53Z, 800 of them failed logins), 220,053 failed logins, 410 successful logins and 410 `profile_updated: direct deposit` rows (2027-11-15 to 11-23), and the 6 + 6 rows of the planted applications (203.0.113.21 and .22). `ASN 64512` + `login_success` returns exactly the 410 taken-over accounts; `ASN 64512` + `account_created` returns exactly the six planted identities.
- `user_agent_family` `python-requests` (222,686 rows) and `curl` (907 rows) occur on no other row.
- `base_logistics_access_*.csv`: `ASN 64512` 680 rows, `python-requests` 453, `curl` 227, all the August probe.
- Status 404 (568 and 116 rows) and the paths `/admin`, `/owa`, `/login.aspx`, `/api/v1/session`, `/.well-known/security.txt`, `/account/recover`, `/help/contact` (and `/status` on the logistics system) occur only on the probe. Six of these return 200, so they are real pages that no ordinary visitor opened in six months.
- In the partner logs the builder gave the same label a background (1,311 sign-ons, 10 hostile). The portal logs label the background part of 203.0.113.0/24 as `ASN 64506`, `64508`, `64509` instead, so the label is still a pure marker there. `payments/aid_applications.csv` carries the same marker (`source_asn = 64512`: 416 rows = 410 + 6).
- `_PROJECT_RULES.md` line 24 forbids this ("no column, label, note or value that occurs only on hostile, fraudulent or coordinated records"). A stuffing run of 220,000 attempts will always be visible by volume; the defect is that the label also isolates the 410 successes and the six applications with no analysis.

**2. Every hostile address sits in 203.0.113.17 to .87 (plus one refused gateway attempt from .112) and the background was drawn only from .120 upwards.** (`p1_lowrange.py`, `p1_docrange_all.py`, `p2_items_1_4.py`, `p3_mail_fw.py`, `p3_verify_numbers.py`)
- `src_ip` last octet below 100 in 203.0.113.0/24, partner sign-on logs: 10 rows of 280,750, exactly the ten hostile sign-ons (city `auth_2027-09.csv` 2027-09-16T01:17:27Z `ef77646`, 14:52:10Z `e39dab0`, 09-17T00:56:22Z `3afab2b`, 03:22:54Z `1c53c5a`, 07:07:30Z `ff7a022`, 16:38:30Z `8f8d8c3`, 21:02:05Z `6332995`; air station 09-16T14:21:39Z `c903854`, 18:27:31Z `79c129e`, 09-18T02:56:41Z `64d29c0`). Background 203.0.113.x sign-ons: 1,301 rows, lowest last octet 122.
- Same filter on firewalls: city 7 rows (the seven inbound sign-on sessions); vendor 15 rows (the lure delivery from 203.0.113.22 at 2027-08-12T14:41:07Z and the 14 gateway sessions from .41, .44, .87); air station 1,054 rows, of which 680 are the August probe, 360 the lure deliveries and 3 the webmail sign-ons (11 are portal background). Port, county and both hospitals: 0 rows.
- The 360 air-station lure deliveries and the vendor lure are the only inbound SMTP sessions from any documentation range in the seven firewalls.
- This is item 1 of the previous review with the boundary moved. The three-value conjunction the builder disclosed (`ASN 64512` + `password` + `new device`) returns 12 rows in the partner logs (10 hostile) and exactly the 10 hostile rows in `account_logons_city_airstation.csv`.

### Major

**3. The vendor's addresses still collide with the fraud ring's address and with portal background.** (`p2_items_1_4.py`, `p2_item8b.py`, `p2_items_15_20.py`, `p3_registry_addr_as_clients.py`)
- Registry: vendor DMZ subnet 198.51.100.0/28; mail gateway .5, VPN .6. Firewall: outbound sessions leave from .7 (8,759) and from .10 to .59, each used 225 to 230 times, except .44, which is never used. The one hole in the pool is the address of the 94 fraudulent applications (426 aid-portal rows). A participant who lists the pool is pointed at the vendor.
- The aid-portal log has 75 page views from 198.51.100.7 (the vendor's main outbound address), 76 from 198.51.100.3 (inside the vendor's /28) and 60 from 198.51.100.187 (a vendor VPN exit); the logistics log has 3, 3 and 2. The vendor's own logs have no session to either system.
- 192.0.2.150 is the city's hosted mail gateway (`CITY-MX-02`, `EXT-CITY-MAIL`); the aid-portal log has 15 page views from it with phone and desktop browsers.

**4. `ASN <number>` is not a function of the address, within a log or across streams.** (`p3_asn_map.py`, `p3_portal_realism.py`, `p3_verify_numbers.py`)
- 192.0.2.x is `ASN 64499` in partner sign-ons, `64497`/`64498` in the portal logs, `64496` in aid applications. 198.51.100.x is `64496` in partner sign-ons, `64496`/`64497` in vessel sessions, `64500`/`64501`/`64502`/`64505` in the portal logs. 203.0.113.122-248 is `64512` in partner sign-ons, `64506`/`64508`/`64509` in the portal logs.
- Inside the aid-portal log 423 client addresses carry more than one label; all 88 background documentation-range addresses carry two or three (198.51.100.111 is `ASN 64501`, `64502` and `64505`).
- Ordinary carriers: `ASN 7018` is 24/67/72/76/99.x in partner sign-ons and 100.x in the portal logs. Three spellings are in use (`ASN 7018`, `AS-7018`, bare `7018`).

**5. Ordinary portal clients come from 100.64.0.0/10.** 170,027 aid-portal rows (98% of ordinary traffic) and 1,054 logistics rows have client addresses 100.64.x to 100.127.x. That is carrier shared address space; a public web server never sees it as a source. (`p1_portal_addr.py`)

**6. Portal user agents are drawn per row, not per client.** Registration and application, minutes apart from one address, use the same `user_agent_family` in 21.7% of 30,568 accounts; independent draws predict 21.7%. Of 21,920 addresses with four or more rows, 154 have one user agent and 18,720 have three or more. Example: `ACC-3EBFE7C55E` registers with Edge/Windows at 2027-11-14T18:34:37Z and applies with Safari/iOS at 18:49:36Z. Device-based analysis is impossible and the 94-application address looks like every household. (`p3_portal_realism.py`, `p1_portal_ips.py`)

**7. The aid-portal log changes generator when registration opens, and its background is flat.** (`p3_portal_realism.py`, `p1_portal_vc.py`)
- `ASN 20115`, `ASN 7922` and `ASN 64500` have 0 rows before 2027-11-13 and about 12% of traffic each afterwards; eight small networks (`64497` to `64509`) never register or log in.
- Information-page traffic is a step: 52 to 65 rows a day until 2027-09-13, 357 on landfall day (72,000 customers without power), then 314 to 373 a day for 60 days with no decay, no weekday effect (60.3 against 58.4 before the storm) and no rise when individual assistance is approved on 11-10.
- The seven information pages each take 14.0 to 14.6% of views, the home page no more than any other.
- `login_success` is flat across the clock (4.0 to 4.4% in every local hour) while applications follow a daytime curve.

**8. Portal sessions are mechanical.** (`p3_portal_realism.py`, `p1_farm.py`, `p3_logistics_realism.py`)
- 30,052 ordinary `POST /account/register` and 0 `GET`; 0 `GET /applications`; 4,163 `GET /login` against 44,017 `POST`.
- Every account submits exactly one application 80 to 1,499 s after registering (uniform). 38,983 of 40,486 ordinary logins are followed by exactly one `/status` view 3 to 199 s later; failed-then-successful logins are 8 to 89 s apart.
- The stuffing run logs 215,724 distinct well-formed `ACC-` ids, of which 327 exist (30,058 accounts exist). The August probe logs attempted user names (`fema`, `support`, `mgarcia61`). A portal cannot give an account id to a login for an account that does not exist.
- `bytes` is 900 to 42,000 for every page and event alike; ordinary traffic has only status 200, 201 and 401 in 173,327 rows.
- Logistics log: base-network use is flat across the clock (3.9 to 4.6% per hour), 42.1 rows on weekdays and 43.1 at weekends, 44 on Thanksgiving and 50 on New Year's Day; every one of an account's 28 to 61 rows comes from a different address; a failed login is never retried (next row 42 minutes to 19 days later); browsers other than the crawler fetch `/robots.txt` 146 times. The 180 `nas-<hex>` accounts join to nothing.

**9. Hospital administration wings are active while the hospitals have no commercial power.** (`p2_hospital_power.py`)
- `hospital_capacity.csv`: Shoreline on generator 2027-09-14T06:17:03Z to 09-22T14:14:33Z, Bay City 09-14T06:31:40Z to 09-22T15:42:10Z. Registry: site `ADM` has `backup_power: false` at both. Canon expects "no events from the administrative wings while they have no power".
- Shoreline `ADM` inside the window: 93 workstation logon rows (09-16: 3, 09-17: 22, 09-20: 30, 09-21: 30, 09-22: 8), 46 web rows, 47 endpoint events on seven days (12 `DEFINITIONS_UPDATED`, 14 `SCAN_COMPLETED`). Bay City `ADM`: 80 logon rows, 31 web rows, 31 endpoint events.
- City Hall, the library, the air-station administration building and the port offices are correctly silent for their outages.

**10. Residual single-template behaviour.** (`p2_items_9_13.py`, `p2_items_11_12.py`, `p3_verify_numbers.py`)
- The two hospitals have identical session-length percentiles (0.7, 2.1, 3.9, 6.5, 11.2 h) and hour profiles within 0.6 points.
- Across all seven: endpoint event mix within 3 points over three "products"; denied-port mix within 1 point; failed workstation logons 3.8 to 5.0%; failed remote sign-ons 5.1 to 5.8%; new-device share 5.4 to 7.0%; remote sign-on hour profile within about 1 point.
- All 10,170 failed workstation logons are followed by a success on the same host within an hour (68 to 73% within three minutes).
- City, vendor, county and port have no workstation logons at all in local hours 04, 16 and 19 (0 to 3 of 5,700 to 18,000).
- Firewall `bytes_recv` is web `bytes_in` times 1.03 (5th percentile and median both 1.03).

### Minor

**11.** Bulk mailings have round counts: 860, 840, 780, 620, 540, 390, 370, 360, 330, 260, 230, 210, 200, 180, 170, 160, 150, 120, 110, 60. The lure wave is the only bulk mailing with many sender addresses (89 and 87 `assistance-NN@`; benign bulk has 1 to 6). (`p1_campaigns.py`, `p2_items_3_6.py`)

**12.** The five vendor macOS hosts browse as `Chrome/Windows`, `Firefox/Windows` and `Edge/Windows` (1,433 rows) and log Windows event ids. (`p3_misc.py`)

**13.** 149 of 745 site names are under `.com`, `.net` or `.org` (`api.bank-online-secure.com`, `api.nueces-county-tx.org`); any may be registered. (`p3_misc.py`)

**14.** Guide, schema and catalogue statements:
- Guide: the two `mail_url_clicks_*` tables are said to be the same rows as in `partner_it/`. No partner log has such rows. The vendor click row gives `client_ip` 198.51.100.10 (the outbound address); the web row gives 10.80.1.56. The city and air-station click rows give inside addresses.
- Catalogue `portal_access_logs`: "aggregated per minute during floods" (the log has 220,053 single failed-login rows), "account hash", and `required_span` from 05:00Z while data starts 00:26Z.
- Guide: "serves information pages only until registration opens", yet `/login` and `/status` take 14% of views each before then.
- Guide: the sentence telling participants to treat documentation ranges "like any other outside address" singles out the ranges that hold all hostile infrastructure.
- Partner schemas carry `"generator": "scripts/streams/gen_partner_it.py"` and `"verified": true`.

**15.** Small gaps against "all present": 2 of 6,679 air-station inbound messages and 1 of 2,284 outbound have no SMTP session; 3 remote sign-ons (one each at Shoreline, Bay City, county) have no firewall session. (`p3_mail_fw.py`, `p2_item8b.py`)

**16.** The vendor's and Bay City's second resolver is the edge firewall (`10.80.8.1`, 896 answers; `10.112.1.1`, 466). (`p3_misc.py`)

**17.** Every gateway firewall session is the vessel-session duration plus 1 s (74 of 74). (`p2_items_15_20.py`)

**18.** 46 exact duplicate rows in the aid-portal log; 1 in the county firewall log. (`p3_struct_hostile.py`)

**19.** Air-station administration building: 22 logons on evacuation day 2027-09-10 and 12 on 09-13, against canon's "near zero from the evacuation". (`p2_item21_sites.py`)

## The 24 items of audit 3

| # | Item | Verdict | Numbers |
|---|---|---|---|
| 1 | Range and label only on hostile records | **Partly** | Label fixed in partner logs (1,311 sign-ons, 10 hostile). Range moved to a /25: last octet below 100 returns 10 of 10 hostile sign-ons, 0 others. Portal logs: label still hostile-only (defects 1, 2) |
| 2 | Registry names the ten victims | Fixed | 0 hosts outside their site subnet; no numbering outliers; the ten click hosts are ordinary shared consoles with 4 to 6 users |
| 3 | Lure separable by formatting | Fixed, residue | Six message-id shapes, all shared; 4,022 sender domains. Residue: 89/87 senders on the wave; lure SMTP from 203.0.113.17-.22 |
| 4 | Fraud ring's address assigned to the vendor | **Partly** | No pool in the registry, 0 vendor rows from .44. But pool .10-.59 has exactly one unused address (.44); /28 and .7 collide with portal background (defect 3) |
| 5 | Extract seams | Fixed | 1,189 / 2,314 / 859 / 973 extract rows all found unchanged; label mix inside and outside the window within 2 points; spam present inside windows |
| 6 | Clickers never received a lure | Fixed | 10 of 10 received one before the click |
| 7 | Firewall destination against DNS answer | Fixed | 0 of 73,802 allowed web rows lack a prior lookup or a session to the answer |
| 8 | Partner and portal logs disagree | Fixed | 0 partner rows to the aid portal; 1,862 of 1,862 outside logistics rows have a firewall session; the 1,063 other sessions carry at most 619 B out |
| 9 | Mail does not join or behave | Fixed | Internal and outbound senders 100% registry; outbound 886 to 5,338 per organisation; storm subjects only in September and October |
| 10 | One template, seven names | **Partly** | Browser mix, categories, rule and policy names differ; defect 10 remains |
| 11 | Remote sign-ons ignore calendar | Fixed | City 138.0 weekday, 69.6 weekend, 37 landfall day, 47 Christmas Day |
| 12 | Workstation sessions regular | **Partly** | 5th percentile 2.1 to 2.9 h; denied sources repeat (990 of 3,113 at the city). Still 100% of failures followed by success; empty clock hours |
| 13 | Vendor plan collides with itself | Fixed | 0 duplicate addresses, 0 overlapping subnets |
| 14 | Guide and catalogue statements | **Partly** | Sampling and DNS caching statements now true (largest lookup-to-request gap 275 s); defect 14 remains |
| 15 | Port 80 against 443 | Fixed | 59 of 59 edge sessions to the gateway on 443 |
| 16 | Mixed address conventions | Not fixed (by decision) | Worse in the portal logs (defect 5) |
| 17 | Real names and top-level domains | Not fixed (by decision) | Defect 13 |
| 18 | TCP only, two statuses, equal bytes, 3.0 s | Fixed, residue | 3 protocols, 35 ports, 11 statuses; failed sign-on sessions 1.0 to 5.8 s; constant 1.03 byte ratio |
| 19 | VPN pool and 15 s hospital VPN | Fixed | 87 to 147 VPN-zone rows per organisation; hospital VPN median 759 and 865 s |
| 20 | Vendor workstation uses 49 pool addresses | Not fixed (documented as rotating) | 75th percentile 46 addresses per workstation, maximum 49 |
| 21 | Dark buildings keep working | **Partly** | Fixed at city, air station and port; not at the hospitals (defect 9) |
| 22 | Port gate and Coast Guard sender | Fixed | Gate 4, 4, 6 logons on 09-11 to 09-13, 0 from 09-14 to 09-17; 17 of 17 Coast Guard orders and bulletins mailed 0.8 to 6.0 min after issue (two letters addressed to vessels are not mailed) |
| 23 | Alert service only at alerts | Fixed | 84 of 98 requests are not near an alert; 11 of 11 city and county alerts have a request 3 to 24 s before issue |
| 24 | Catalogue span | Fixed for partner streams | `portal_access_logs` still starts 05:00Z |

## Checked and found sound

- Structure: 805,611 partner rows, all time-ordered, in the right month file, no bad timestamps; 1 duplicate.
- Registry joins: 0 unknown hosts, accounts, mailboxes, resolvers, firewalls or inside addresses in any log, apart from the documented VPN pools; every workstation logon is by a listed user of that host.
- Web, DNS and firewall: 73,802 allowed web rows each have one lookup and one firewall session; as many outbound web sessions as web rows in every organisation.
- Mail and firewall: 23,615 of 23,617 inbound and 8,339 of 8,340 outbound messages at the six organisations with their own gateway have an SMTP session.
- Vendor story against canon and `vessel_cargo_control_remote_sessions.csv`: lure 14:41:07Z, click 15:02:07Z by `m.okoye`; 74 of 74 vessel sessions have a gateway firewall session; the 15 third-network rows have no vendor-side session and all 59 others do; valve-window sessions 03:52:10Z to 05:35:12Z and 03:53:45Z to 05:35:52Z (canon 04:00 to 05:30Z); access disabled 2027-09-22T15:00:00Z; no session of 300 s or more afterwards.
- Phishing against canon: 840 + 360 = 1,200 messages, 2027-09-15T13:06:38Z to 09-18T01:56:21Z; ten clicks each with lookup, web row and firewall session; ten sign-ons 0.9 to 7.9 h after the click, each with an inbound session whose bytes and duration are unremarkable.
- Portal against canon and `aid_applications.csv`: probe 08-10T05:01Z to 08-13T04:59Z on both systems from the same 64 addresses, no successful login; 220,053 failed logins and 410 successes 11-15 to 11-23; 94 applications from 198.51.100.44 in bursts of 31, 29 and 34; 30,058 web applications match the applications file on account, second, address and label; all 1,909 web account changes match; 47,820 applications between D+60 and D+89 (canon about 48,000). Absent as required: no outside `login_success` on the logistics system; no account events before 2027-11-13T06:00:00Z.
- Other streams: air-station outage 09-14 to 09-16 matches `base_status_reports.csv`; clinical unlocks correlate with `ED_Visits_24h` at 0.87 at both hospitals; Coast Guard orders, alert transmissions and the port gate agree with `port_conditions.csv` and `eas_broadcasts.csv`.
- No hostile activity at the port, the county or either hospital. No real company, product or person names found in hosts, domains, subjects, attachments, rule names or detections.

## Judgement

Not fit to hand to teams yet. Change first, in this order:

1. Portal logs: give `ASN 64512`, script user agents, 404s and the probe paths an ordinary background (monitoring checks, other scanners, ordinary visitors to `/help/contact` and `/account/recover`), or drop the network label from the portal logs and the applications file.
2. Draw background documentation-range traffic across the whole of 203.0.113.0/24, including inbound SMTP, so no last-octet cut separates hostile addresses.
3. Move the vendor out of 198.51.100.0/24 or move the fraud address; in any case fill the hole at .44 and stop using vendor and city-gateway addresses as portal visitors.
4. Keep hospital administration wings silent for the whole generator period, or change the registry and canon.
5. Portal realism: one user agent per client, routable client addresses, one label per address and one address-to-label table for all streams, form GETs, a clock and calendar for logins and for the logistics system.

Items 10 to 19 can follow. The partner logs' joins, calendar behaviour and agreement with canon are now in good shape; the remaining exposure is concentrated in the portal logs and in the address plan.
