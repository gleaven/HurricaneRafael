# Independent audit 3: partner organisation IT logs

(Saved from the reviewer's hand-back on 2026-11-12; the reviewer could not write the file itself. The findings describe the logs as they stood BEFORE the fixes of the same day; the status of each item afterwards is in `CHANGELOG.md` and in the fix report summarised at the end of this file.)

**Not ready for release: each of the three intrusions can be found with a single value count, and a fourth blocker is a false lead that contradicts canon.**

Scope: 294 files, 759,060 rows across seven organisations, plus the registry, the guide, the schemas and the delivered streams they must agree with. Run `python3 build_cache.py` first (about 60 s); every other script runs as `python3 <script>` from this folder, each under 170 s.

## How fast the hostile activity fell out (pass 1: data, registry and guide only)

| Step | Filter | Result |
|---|---|---|
| First command on the auth logs | value counts of `src_network` | `ASN 64512`: 7 rows (city), 3 rows (air station). These are the ten hostile sign-ons. |
| Second look at the registry | hosts whose address is outside their site subnet | exactly ten workstations, `-WS-900` to `-906` (city) and `-900` to `-902` (air station): the ten link-click victims, each with its single user. |
| First command on the mail logs | value counts of `sender_domain` or `subject` | the 1,200 lure messages and the single vendor lure. |
| First look at the vendor firewall | `src_ip` starts `203.0.113.` on `BRW-FW-DMZ-01` | 15 rows: the sessions from the third network, including the two spanning the valve-opening window. |

Four value-count commands, no joins.

## Defects

### Blockers

**1. One address range and one network label occur only on hostile records.**
`src_ip` beginning `203.0.113.` (and `src_network = ASN 64512` in auth) returns only hostile records, and all of them.
- Auth: 10 of 257,545 rows (city `auth_2027-09.csv` lines 5002, 5095, 5099, 5252, 5285, 5294, 5418; air station lines 2680, 2721, 2739).
- Firewall: 705 rows (city 7 inbound sessions; air station 680 logistics-portal sessions 2027-08-10 to 08-13 and 3 webmail sessions; vendor 15 sessions at `BRW-FW-DMZ-01`, of which `firewall_2027-09.csv` lines 986 and 987 are the two valve-window sessions).
- Every other outside source is routable-looking; the only documentation-range sources are the vendor's own block and these.
- `_PROJECT_RULES.md` forbids exactly this ("no value that occurs only on hostile records").
- Reproduce: `p1_auth_asn.py`, `p1_aid.py`.

**2. The registry names the ten link-click victims.**
Ten workstations in `partner_it_registry.json` break both the naming sequence and the address plan (`CC-EOC-WS-900`, `CC-PSB-WS-901`, `CC-WTR-WS-902`, `CC-EOC-WS-903`, `CC-PSB-WS-904`, `CC-WTR-WS-905`, `CC-EOC-WS-906`, `NASCC-OPS-WS-900` to `-902`). Site subnets are /24s and no other workstation is outside its own. Their `users` are exactly the ten accounts with hostile sign-ons.
- Reproduce: `p3_registry.py`, `p1_clickhosts.py`.

**3. Lure mail is separable by a formatting artefact.**
- `message_id` ends `@mail>` on all 66,606 ordinary messages in all seven organisations; the only exceptions are the 1,200 lures, the vendor lure, 20 Coast Guard notices and 6 translation deliveries.
- All benign outside mail everywhere comes from one domain, `partner-mail.example` (39,893 rows). At the vendor the lure is the only row in six months from any other domain.
- There are ten background subjects, uniformly distributed, plus the lure subject.
- Reproduce: `p1_mail_filters.py`, `p1_rare.py mail`.

**4. The registry assigns the domestic fraud ring's address to the vendor.**
- The registry gives Brightwake 198.51.100.0/24, with office pool 198.51.100.10 to .59.
- `aid_portal_access_2027-11.csv` and `-12.csv` have 424 rows from 198.51.100.44: canon's 94 fraudulent applications by the separate domestic ring.
- The vendor's own firewall shows 153 office sessions leaving from 198.51.100.44, three of them to the aid portal.
- The same /24 carries three network labels across streams.
- Reproduce: `p2_addrcollide.py`, `p2_final.py`.

### Major

**5. The older extracts are visible as seams.** Sign-on labels `ASN 64503`, `64496`, `64510` exist only from 2027-09-12 to 09-21; no `spam` verdict inside any extract window against 1.7 to 2.2% outside. `p2_extracts.py`.

**6. Seven of the ten clicking mailboxes never received a lure**, and an eighth received its only lure after the click. `p2_wave.py`, `p1_clickhosts.py`.

**7. Firewall destinations disagree with DNS answers for 41% of web sessions** (39,437 of 95,551), including 7 of the 10 click sessions. `p3_joins2.py`.

**8. Partner logs and the portal logs disagree in the reverse direction.** All seven organisations visit `portal.disasteraid.example` (510 sampled web rows) but the aid portal's own log has no request from their public blocks; the air-station firewall has 1,138 completed sessions to the logistics system from ordinary outside addresses that the logistics log does not show. `p2_portal.py`, `p2_nascc.py`.

**9. Mail logs do not join to the registry and do not behave like mail.** Internal senders are not registry accounts (21,670 of 21,670); outside senders almost never repeat; three organisations have no outbound mail; vendor mail reaches 8 of 55 mailboxes; "Storm readiness checklist" is as frequent in July and December as in September. `p3_registry.py`, `p3_template.py`.

**10. One template, seven names.** Browser mix, session-end reasons, denied inbound per day, endpoint vocabulary, attachment and spam rates, sites visited and server layout are the same within a point or two across all seven organisations. `p3_template.py`, `p1_rare.py firewall`.

**11. Remote sign-ons ignore the calendar and the storm** (city 182.6 per weekday, 177.8 per weekend day, 191 on landfall day, 197 on Christmas Day). `p3_daily.py`.

**12. Workstation sessions are mechanically regular** (5th percentile of session length 8.2 h; logons only 05:00-09:59 or 17:00-19:59; every failed logon followed by success within three minutes; every denied inbound attempt from a different source). `p3_sessions.py`, `p3_misc2.py`.

**13. The vendor address plan collides with itself** (office and server subnets both 10.80.1.0/24; five addresses assigned twice). `p3_registry.py`.

**14. Guide and catalogue statements that are untrue or that steer** (sampling stated for the whole family although sign-ons are complete; the DNS caching statement; "mail gateways are hosted"; the list of what is "complete" and the sentence naming the vendor gateway's legitimate address pools; catalogue pointing at a guide section that did not exist). `p3_joins.py`, `p2_final.py`.

### Minor

**15.** Three remote-maintenance sessions are port 80 on the vendor edge firewall but port 443 on the gateway firewall. **16.** Address conventions are mixed (routable space for six organisations, documentation ranges for everything carried over). **17.** Real operating-system, browser and carrier-ASN names; many site names under real top-level domains. **18.** Firewall logs TCP only with 14 destination ports; web status 200 or 403 only; web bytes equal firewall bytes; failed gateway attempts all last exactly 3.0 s. **19.** VPN pool addresses appear only in the 20 vendor remote-maintenance sessions; hospital VPN sessions last 15 to 17 s. **20.** Each vendor workstation leaves from about 49 of the 50 office-pool addresses. **21.** Edge firewalls and resolvers keep working in buildings that are dark for four days. **22.** Port gate offices fall silent two days before Port Condition Zulu; the port's own notice arrives from the Coast Guard sender. **23.** The alert origination service is contacted only at real alerts. **24.** Catalogue `required_span` starts 05:00Z; data starts 00:00Z.

## Checked and found sound

- Structure: no malformed rows, no exact duplicates, all rows time-ordered and in the right month file.
- Registry joins: 0 unknown hosts, firewalls, resolvers, client addresses, web users, auth accounts or mail recipients, apart from the documented vendor VPN pool and item 9; no overlap between organisations' ranges.
- Extract containment: all mail and sign-on extract rows appear unchanged.
- Lure wave: 840 + 360 = 1,200 messages, 2027-09-15 13:05Z to 09-18 01:58Z; each of the ten clicks has a DNS lookup, a web row and a firewall session; the ten hostile sign-ons come 2.6 to 8.5 hours after the click.
- Vendor: lure 14:41:07Z, click 15:02:07Z; all 74 remote-session rows have a gateway-firewall session; the 15 third-network sessions have no counterpart inside the vendor's network; valve-window sessions 03:52 to 05:35Z against canon 04:00 to 05:30Z; access disabled 2027-09-22T15:00Z.
- Alerts and translation, port orders and gate activity, hospital power and load (unlocks correlate with emergency visits at 0.91), air-station staffing and outages all agree with the other delivered streams.
- Internal consistency: every allowed web row has one firewall session and a DNS lookup; 99.6 to 100% of user web requests fall inside that user's logon session; no account on two hosts at once; daylight-saving change handled.

## Judgement

The cross-stream work is careful, and almost everything canon requires is present and correctly timed. But the three intrusions these logs exist to hide each fall to one value count, and the fourth blocker is a false lead. Beyond that, the background is one generator run seven times, and the older extracts show as seams. Fix items 1 to 4 first, then 5 to 9, then decide how much of 10 to 12 to vary per organisation.

---

## After the fixes (2026-11-12, from the fix report; to be confirmed by the second review)

Items 1, 2, 5 to 13, 15 and 18 to 23 fixed in the generator (`partner_it_model.py`, `gen_partner_it.py`, `partner_it_mail.py`); item 3 fixed with one residue (the wave's sender domain is still the second most frequent outside sender at the city, beside other bulk mailings); item 4: the vendor's plan no longer lists a pool and the generator never emits 198.51.100.44, but the vendor and the fraud ring's address remain in the same /24 because other delivered streams and canon fix both; items 14 and 24 fixed in the guide, schemas and catalogue; items 16 and 17 kept by decision (mixed ranges are documented; operating-system and browser names are ordinary environment detail; carrier ASN numbers are shared with other streams). One conjunction still isolates the ten sign-ons in the extract table: `ASN 64512` + `password` + `new device`; each value alone is shared with ordinary rows. Probes: `scripts/streams/probes_partner_it.py`, 41 of 41 pass.
