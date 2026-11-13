#!/bin/bash
# Builds the header-less concatenations used by the audit scripts (in /tmp; ~230 MB). Run first.
L="./05_other_sources/network_logs"
for t in conn dns ssl http files x509 notice; do cat "$L"/zeek/*/$t.log | grep -v '^#' > /tmp/z_$t.tsv; done
cat "$L"/firewall/*.csv | grep -v '^time_utc' > /tmp/fw.csv
cat "$L"/proxy/*.csv | grep -v '^time_utc' > /tmp/px.csv
cat "$L"/dhcp/*.csv | grep -v '^time_utc' > /tmp/dhcp.csv
wc -l /tmp/z_*.tsv /tmp/fw.csv /tmp/px.csv /tmp/dhcp.csv
