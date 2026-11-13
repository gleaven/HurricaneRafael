# Pass 1 (blind) notes: what each cheap trick returned

Elapsed analyst effort is given in "commands" (one script run each).

| # | Trick (script) | Result |
|---|---|---|
| 1 | value counts of every auth column (p1_valuecounts.py auth) | nothing rare; ASN 64496/64499/64512 present in all orgs as background |
| 2 | pairwise crosstabs on remote sign-ons (p1_auth_pairs.py) | no pair isolates hostile rows; documentation ranges = ASN 64496/64499/64512 |
| 3 | documentation-range sign-ons (p1_docrange.py) | 2,014 rows, 137 addresses, 204 accounts, all months: decoys present |
| 4 | mail burst domains (p1_mail_rare.py) | aid-help-portal.example 840 (city) + 360 (nascc), 15-18 Sep, among 3 benign bulk domains; all bulk counts are exact multiples of 10 |
| 5 | bulk campaigns (p1_campaigns.py) | lure wave has 89/87 distinct senders, every benign bulk mailing has exactly 1 |
| 6 | vendor gateway firewall, long sessions by source /24 (p1_brw_dmz.py) | 61 sessions >= 300 s: 49 from 198.51.100.x (vendor), 12 from 203.0.113.41/.44/.87, night hours, first 2027-08-13T02:33Z, last two end 2027-09-14T05:35Z. STORY 1 reached at command 6 |
| 7 | /24s with many accounts, daily new-device counts (p1_auth_hostile.py) | nothing |
| 8 | accounts in the click report -> later sign-ons (p1_clickers.py) | each of the 10 has one `password`/`new device` sign-on from 203.0.113.24-.74, 0.9 to 8.5 h after click. STORY 2 reached at command 8 (genuine analysis) |
| 9 | last-octet histogram of documentation ranges (p1_lowrange.py, p1_docrange_all.py) | background uses 203.0.113.120-249 only; `203.0.113.x, x<100` returns exactly the 10 hostile sign-ons in auth, the 12 long gateway sessions, 683 air-station firewall rows (Aug scan), 223,605 aid-portal rows and 680 logistics rows. One address filter, no false positives in auth |
| 10 | portal value counts (p1_portal_vc.py) | `client_network = ASN 64512` or `user_agent_family = python-requests`: Aug 10-13 scan of both portals and the Nov 15-23 credential stuffing (220,053 failed, 410 successes, 410 deposit changes; plus 800 failed logins inside the August probe). STORY 3 reached with the first command on the portal log |
| 11 | per-address account creation (p1_portal_ips.py, p1_farm.py) | 198.51.100.44: 94 accounts in three bursts from 2027-11-13T06:00:00Z. STORY 4, genuine analysis |
| 12 | rare web/DNS hosts (p1_web_rare.py) | aid-help-portal.example 10 rows (the clickers); certificates.marine-certification-notices.example 1 row (m.okoye 2027-08-12T15:02:07Z) |
