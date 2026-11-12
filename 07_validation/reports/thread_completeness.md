# Thread completeness

Built by `scripts/check_thread_completeness.py`. A thread is complete when the event list has a beginning, an escalation, a discovery and a resolution; the public record and the news pick it up where it becomes public; at least one delivered data stream carries evidence; and its answer key is verified on disk.

| Thread | Events (days) | Begin / escalate / discover / resolve | Public facts (first day) | Stories (days) | Data streams with evidence | Observations | Answer key | Gaps |
|---|---|---|---|---|---|---|---|---|
| T1 Storm cascade | 34 (-60 to 110) | 11 / 12 / 44 / 17 | 36 (-21) | 520 (-60 to 119) | 24: adsb, ais, avl, base_status_reports, cad_911, cargo_manifests… | 79 | 16 steps verified | none |
| T2 Dark vessel | 18 (-50 to 100) | 6 / 6 / 22 / 9 | 15 (-60) | 259 (-60 to 119) | 11: ais, base_status_reports, broadcast_logs, contracts, fuel_deliveries, insurance_claims… | 38 | 16 steps verified | none |
| T3 Fraud ring | 11 (-40 to 100) | 3 / 5 / 14 / 5 | 9 (10) | 175 (3 to 119) | 10: adsb, aid_applications, ais, contracts, drone_detections, drone_telemetry… | 18 | 16 steps verified | none |
| T4 KESTREL campaign | 7 (-35 to 100) | 2 / 3 / 12 / 4 | 10 (2) | 120 (2 to 119) | 5: aid_applications, financial_transactions, host_audit_logs, portal_access_logs, social_media | 10 | 8 steps verified | none |
| T5 Equity gap | 12 (-7 to 90) | 4 / 4 / 10 / 4 | 5 (1) | 210 (-45 to 119) | 9: aid_applications, avl, cad_911, census, drone_telemetry, ed_visits… | 20 | 16 steps verified | none |
| T6 Tanker cyberattack | 24 (-33 to 105) | 8 / 8 / 32 / 17 | 20 (-2) | 275 (-3 to 119) | 15: adsb, air_quality, ais, drone_detections, drone_telemetry, ed_visits… | 47 | 16 steps verified | none |
| T7 Opportunistic military attack | 11 (-40 to 100) | 3 / 5 / 24 / 6 | 18 (-40) | 342 (-60 to 119) | 11: adsb, ais, base_status_reports, cad_911, cargo_manifests, drone_detections… | 25 | 16 steps verified | none |
| T11 Aerial damage assessment corridor | 8 (-2 to 45) | 2 / 4 / 8 / 4 | 4 (0) | 13 (0 to 45) | 5: adsb, damage_assessment, drone_telemetry, outage_map, satellite | 16 | 14 steps verified | none |
| T12 Dark vessel and port surveillance | 11 (-7 to 31) | 3 / 5 / 13 / 2 | 6 (-1) | 103 (-55 to 119) | 5: ais, port_conditions, port_surveillance, satellite, vessel_ot_logs | 23 | 16 steps verified | none |
| T13 911 dispatch corpus | 9 (0 to 45) | 3 / 3 / 11 / 4 | 6 (0) | 17 (0 to 45) | 4: avl, cad_911, eas_alerts, sar_missions | 15 | 14 steps verified | none |
| T14 Bilingual Emergency Communications | 12 (-5 to 45) | 4 / 4 / 20 / 8 | 9 (-3) | 29 (-3 to 119) | 6: broadcast_logs, census, eas_alerts, ed_visits, shelters, syndromic | 27 | 16 steps verified | none |
| T15 Social Media Influence Operation | 9 (-7 to 38) | 3 / 3 / 10 / 6 | 4 (21) | 34 (2 to 83) | 2: shelters, social_media | 13 | 9 steps verified | none |
| T16 Hospital Surge and Clinical Triage | 10 (-2 to 60) | 3 / 4 / 12 / 5 | 5 (0) | 48 (0 to 119) | 6: ed_visits, fuel_deliveries, hospital_capacity, outage_map, scada_historian, syndromic | 20 | 16 steps verified | none |
| T17 Search and rescue operations | 8 (-1 to 7) | 2 / 4 / 11 / 4 | 5 (1) | 16 (1 to 10) | 5: adsb, avl, cad_911, drone_telemetry, sar_missions | 15 | 14 steps verified | none |
| T19 Drone and counter-UAV surveillance | 8 (-10 to 30) | 2 / 4 / 10 / 4 | 4 (-2) | 23 (-2 to 109) | 2: ais, drone_detections | 11 | 8 steps verified | none |
| T20 Environmental sensors and spill tracking | 9 (0 to 60) | 3 / 3 / 13 / 6 | 6 (2) | 91 (0 to 119) | 6: adsb, air_quality, scada_historian, syndromic, vessel_ot_logs, water_quality | 15 | 10 steps verified | none |
| T21 Broadcast and emergency alert corpus | 8 (-5 to 42) | 2 / 4 / 14 / 4 | 7 (-2) | 19 (-2 to 105) | 2: broadcast_logs, eas_alerts | 14 | 13 steps verified | none |
| T22 Insurance and disaster fraud | 7 (-30 to 90) | 2 / 3 / 8 / 2 | 5 (3) | 16 (3 to 104) | 3: aid_applications, broadcast_logs, insurance_claims | 9 | 4 steps verified | none |
| T8 Grid intrusion | 31 (-15 to 35) | 10 / 11 / 32 / 16 | 10 (14) | 27 (10 to 105) | 14: cad_911, damage_assessment, drone_detections, drone_telemetry, fuel_deliveries, hospital_capacity… | 57 | 16 steps verified | none |
| T9 Water SCADA manipulation | 18 (-3 to 42) | 6 / 6 / 29 / 10 | 13 (2) | 100 (0 to 111) | 13: broadcast_logs, cad_911, census, damage_assessment, eas_alerts, ed_visits… | 35 | 16 steps verified | none |
| T10 Hiding in the storm | 17 (-15 to 30) | 5 / 7 / 16 / 9 | 5 (21) | 25 (14 to 105) | 7: host_audit_logs, outage_map, scada_historian, siem_alerts, social_media, work_orders… | 28 | 16 steps verified | none |
| T18 Utility SOC / SIEM telemetry | 8 (-14 to 35) | 2 / 4 / 11 / 5 | 4 (20) | 24 (14 to 105) | 4: host_audit_logs, siem_alerts, work_orders, zeek_logs | 14 | 14 steps verified | none |

## Events that no delivered stream can show

- EVT-0603: A classified assessment; it is in no delivered stream. Each link it draws can be rebuilt from the streams named on the events it ties together.
- EVT-1306: An internal audit and briefing. The 23 false calls it lists are in cad_911 (EVT-1303, EVT-1304, EVT-1707); the referral becomes public on D+29.
- EVT-1507: A law-enforcement records request. The account behaviour it concerns is in social_media.
- EVT-2005: A trajectory-modelling product inside the response team. Its projection (heaviest oiling along Nueces Bay) is borne out by water_quality and satellite at D+4 (EVT-2006).

## Gaps that need new story content

- none
