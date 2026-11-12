#!/bin/bash
# Area 4: every record of the five canon OT events in every stream, straight grep on the raw files.
cd "$(dirname "$0")/../../05_other_sources"
ev() { # label, iso-minute regexes, epoch lo, epoch hi
  echo "================ $1"
  grep -n -E "$2" telemetry/historian_*.csv network_logs/audit/*.csv network_logs/siem/rule_changes.csv maintenance/work_orders.csv 2>/dev/null | grep -v -E "POLICY_|\.PV,|DEFINITIONS|mail_gateway|account_logons|endpoint_protection.*(SCAN|UPDATED)" | cut -c1-420
  echo "--- SIEM (non-INFO)"; grep -h -E "$2" network_logs/siem/siem_alerts_$3.csv | grep -v -E ",INFO,|,LOW," | cut -c1-380 | head -12
  echo "--- zeek notice"; awk -F'\t' -v a=$5 -v b=$6 '$1>=a && $1<=b' network_logs/zeek/$4/notice.log | cut -c1-380 | head -10
}
ev "relay threshold 2027-09-11 ~17:04Z" "2027-09-11T17:0[2-7]" 2027-09 2027-09-11 1820682120 1820682420
ev "SUB-02 breaker 2027-09-21 ~14:28Z" "2027-09-21T14:(2[6-9]|3[0-2])" 2027-09 2027-09-21 1821536760 1821537120
ev "SUB-03 breaker 2027-09-24 ~19:43Z" "2027-09-24T19:4[1-7]" 2027-09 2027-09-24 1821814860 1821815220
ev "P-3 setpoint 2027-09-23 ~02:04Z" "2027-09-23T02:0[2-9]" 2027-09 2027-09-23 1821664920 1821665400
ev "isolation 2027-10-12 12:00Z" "2027-10-12T(11:5[89]|12:0[0-3])" 2027-10 2027-10-12 1823342280 1823342580
