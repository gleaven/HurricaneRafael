# Utility host logs: Windows event logs, endpoint telemetry, triage collections

Guide text for `11_hackathon/DATA_GUIDE.md` (participant-safe). Three streams recorded on the Windows hosts of
the utility (Coastal Bend Power and Water Authority). They describe the same activity as the SIEM alerts, the
Zeek logs and the audit tables, as each host saw it. Hosts and accounts join to `gw_host_registry.json`.

| Stream | What it is | Files | Time column | How it joins |
|---|---|---|---|---|
| Windows event logs | Security, System and Defender channels forwarded from 236 Windows hosts | `network_logs/windows/security_<YYYY-MM>[_NN].jsonl`, `system_<YYYY-MM>.jsonl`, `defender_<YYYY-MM>.jsonl` | `time_utc` (milliseconds) | `host` → `hosts[].hostname`; `user`, `target_user` → `users[].username`, `users[].ot_account`, `service_accounts[].account` (machine accounts are `<hostname>$`); `src_ip` → `hosts[].ip` and Zeek `id.orig_h`; `logon_id` pairs a logon (4624) with its logoff (4634) |
| Endpoint telemetry | Events from the endpoint agent: process starts, network connections, DNS lookups, file creation, registry values, service and task registration, removable devices | `network_logs/endpoint/endpoint_<YYYY-MM>.jsonl` | `time_utc` (milliseconds) | `host`, `user` as above; `src_ip`, `src_port`, `dst_ip`, `dst_port` → Zeek `conn.log`; `query` → Zeek `dns.log`; `pid` + `image` link an event to its `process_start`; `sha256` → triage listings |
| Host triage collections | What the utility's security team collected from fourteen hosts in October 2027: file listing, autoruns, services, scheduled tasks, execution history, logon history, installed software, network configuration | `network_logs/triage/<HOST>/*.csv`, `collection.json`, `placeholders/` | `collected_utc` in `collection.json`; `*_utc` columns | folder name → `hosts[].hostname`; `sha256` → endpoint telemetry; `logon_history.csv` → Windows Security events |

## Reading the Windows event logs

JSON Lines, one event per line. Every line starts with `time_utc`, `host`, `channel`, `provider`, `event_id`,
`record_id`, `level`; the remaining keys depend on the event (see `schemas/windows_event_logs_schema.json`).

- **Event ids collected.** Security: 4624, 4625, 4634, 4647, 4672, 4722, 4725, 4728, 4732, 4740, 4756, 4768,
  4769, 4771, 4800, 4801, 5140, 5145. System: 1074, 6005, 6006, 6008, 7036, 7045. Defender: 1001, 1116, 1117,
  2000, 5000, 5001. Nothing else is forwarded, so `record_id` rises with gaps.
- **What is complete and what is a sample.** Interactive logons and logoffs are complete. So is everything a
  SIEM alert or an audit-table row refers to: for example the failed logons behind a `FAILED_LOGON_BURST`
  alert, the logon on the remote-access gateway for every row of `audit/remote_access_sessions.csv`, the
  Defender event for every row of `audit/endpoint_protection.csv`, the share write for every row of
  `audit/file_integrity.csv`. Network logons (type 3), share access (5140, 5145) and Kerberos tickets follow
  the flows in the Zeek logs: a file-sharing flow to a Windows server opens a network logon there, a share and
  one or more files; an authenticated application session opens a network logon. The Zeek logs hold a
  1-in-200 sample of user-driven traffic, so these events are a sample too: do not compute volumes from them
  without scaling.
- **Lock and unlock** (4800/4801) are forwarded only from the control network and the administration wing.
- **Failed logons.** `sub_status` says why: `0xC000006A` wrong password, `0xC0000071` password expired,
  `0xC0000070` not allowed from this workstation, `0xC000006F` outside permitted hours, `0xC0000234` account
  locked. Wrong passwords entered on phones, webmail or the VPN are counted by the directory but are not
  recorded as 4625 on a workstation, so a lockout (4740) can have fewer 4625 before it than the lockout policy
  requires. Each failed attempt at a workstation also leaves a failed pre-authentication (4771) on a domain
  controller.
- **Accounts.** People use their directory account (`CBPWA\<username>`) on office machines and their control
  network account (`CBPWA-OT\GW-...`) inside the control network. `logon_type` 2 is at the keyboard, 3 over the
  network, 5 a service, 10 remote desktop, 11 a laptop using cached credentials.
- **Power.** A host that is off writes nothing. A planned restart shows 1074 and 6006, then 6005; a loss of
  power shows only 6005 followed by 6008 when the host comes back.

## Reading the endpoint telemetry

JSON Lines. Every line starts with `time_utc`, `host`, `event_type`, `user`, `pid`, `image`.

- The agent records process starts, not exits. A process is identified by `host` + `pid` + `image` from its
  `process_start` until the next start of the machine.
- A TCP or UDP row of Zeek `conn.log` that starts at a Windows host has one `network_connect` with the same
  addresses and ports within half a second, and a Zeek `dns.log` row one `dns_query`, with one exception made
  to bound the volume: for ordinary web browsing (connections and lookups for the categorised public sites of
  the Zeek sample) the agent's records keep every second one. Everything else the sensor logged from a Windows
  host is there. ICMP is not recorded. Because the Zeek background is itself a sample, so is this.
- Programs that run as a service are started when the machine starts. A process that was already running when
  the logs begin (2027-07-15) has no `process_start` until the machine next restarts.
- Removable drives are identified by `device_serial`; a drive keeps its serial wherever it is plugged in.
- `signer` is empty for files that are not signed. In-house tools under `C:\Tools\` are unsigned.
- `command_line` holds the program path and, for office programs and installers, the file that was opened.
- Events owned by a person always lie between that account's logon (4624) and logoff (4634) on that host in
  the Windows Security log.

## Reading the triage collections

One folder per collected host. `collection.json` says when the collection was taken and lists each table with
its row count and SHA-256. The tables agree with the event logs of the same host: a service in `services.csv`
has its registration (System 7045) at `installed_utc`; a file in `file_listing.csv` that the agent saw being
written has the same `sha256` and creation time in the endpoint telemetry; `logon_history.csv` is the 45 days
of logon events before the collection.

The collector copies every unsigned executable it finds outside the Windows folders, on every host: in-house
utilities, vendor tools, downloaded programs. In this data set each copy is replaced by an inert text
placeholder under `placeholders/`: the placeholder's own SHA-256 is the hash the logs record for the file, so
hashes can be followed across the logs and the collections without any executable content being present. No
time in a collection is later than the collection itself.

## Limits

- No process exit, image load or raw file-read events; no PowerShell, Sysmon or application logs.
- Event text is reduced to the fields listed in the schemas; it is not the full Windows event XML.
- Linux servers, network devices and controllers are not in these three streams.
