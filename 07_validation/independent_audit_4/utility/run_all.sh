#!/bin/bash
# Reproduce independent audit 4 (utility logs). Run from anywhere; each step stays under ~170 s.
# Caches go to /tmp/c (not part of the deliverable). Nothing outside this folder and /tmp is written.
set -e
A="$(cd "$(dirname "$0")" && pwd)"
cd "$A/../../../05_other_sources/network_logs"
mkdir -p /tmp/c
for l in conn dns ssl http files x509 notice; do python3 "$A/cache_zeek.py" $l 2027-07 2027-08 2027-09 2027-10 2027-11 2027-12 2028-01; done
python3 "$A/cache_csv.py" siem fw_edge fw_ot proxy dhcp
python3 "$A/cache_win.py"
python3 "$A/p1_siem_profile.py" "$A/cache_siem.pkl" > "$A/out_siem_profile.txt"
# Pass 1 (blind value counts and artefact filters)
python3 "$A/p1_valcounts.py" audit/remote_access_sessions.csv audit/ot_config_changes.csv audit/scada_command_log.csv audit/alarm_suppression_audit.csv audit/historian_access.csv audit/file_integrity.csv audit/change_management.csv audit/settings_audits.csv > "$A/out_audit_valcounts.txt"
python3 "$A/p1_ras_tricks.py"; python3 "$A/p1_conn_profile.py" | cut -c1-3000; python3 "$A/p1_conn_jmp.py" | cut -c1-2500; python3 "$A/p1_conn_artifacts.py" | cut -c1-1500
python3 "$A/p1_ssl_profile.py" > "$A/out_ssl_profile.txt"; (cd triage && python3 "$A/p1_triage.py" > "$A/out_triage.txt")
for m in 2027-07 2027-08 2027-09 2027-10 2027-11 2027-12 2028-01; do python3 "$A/p1_endpoint_profile.py" $m; for c in security system defender; do python3 "$A/p1_windows_profile.py" $c $m; done; done
python3 "$A/p1_endpoint_report.py" > "$A/out_endpoint_profile.txt"; python3 "$A/p1_windows_report.py" > "$A/out_windows_profile.txt"
python3 "$A/p1_csv_profile.py" 'firewall/fw_GW-OT-FW-01_*.csv' time_utc,src_port,bytes_sent,bytes_recv,duration_s > "$A/out_fw_ot_profile.txt"
python3 "$A/p1_csv_profile.py" 'firewall/fw_GW-FW-EDGE-01_*.csv' time_utc,src_port,bytes_sent,bytes_recv,duration_s > "$A/out_fw_edge_profile.txt"
python3 "$A/p1_csv_profile.py" 'proxy/web_proxy_*.csv' time_utc,bytes_out,bytes_in > "$A/out_proxy_profile.txt"
python3 "$A/p1_it04_flows.py" | cut -c1-300; python3 "$A/p1_more_tricks.py" | cut -c1-1200
# Pass 2 (ground truth, re-test of the 28 earlier items)
python3 "$A/p2_items_1_3.py"; python3 "$A/p2_items_4_5.py" | cut -c1-1500; python3 "$A/p2_item5_joins.py"; python3 "$A/p2_items_6_9.py"; python3 "$A/p2_tickets.py"
python3 "$A/p2_item16_ops.py"; python3 "$A/p2_items_17_19.py" || true; python3 "$A/p2_triage_logons.py"; python3 "$A/p2_items_25_27.py"; python3 "$A/p2_canon_checks.py" > "$A/out_canon_checks.txt"
# Pass 3 (realism and cross-log consistency)
python3 "$A/p3_net_join.py"; python3 "$A/p3_net_join2.py"; python3 "$A/p3_windows.py"; python3 "$A/p3_storm_siem.py" | cut -c1-1500
python3 "$A/p3_endpoint.py" 2027-09; python3 "$A/p3_dhcp_vpn.py"; python3 "$A/p3_pcap.py" 2027 2028 > "$A/out_pcap_files.txt"; python3 "$A/p3_pcap_report.py"
python3 "$A/p3_oct12_drop.py"; python3 "$A/p3_fim_5145.py"; python3 "$A/p3_misc.py" > "$A/out_misc.txt"; python3 "$A/p3_sampling.py"; python3 "$A/p3_smtp.py"
