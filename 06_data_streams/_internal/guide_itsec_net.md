# Utility network logs: firewall, web filter, address leases, packet capture

Guide text for `11_hackathon/DATA_GUIDE.md` (participant-safe). Four streams that record the same network
activity as the Zeek logs, each as the device that produced it saw it. All belong to the utility (Coastal Bend
Power and Water Authority); hosts and users join to `gw_host_registry.json`.

| Stream | What it is | Files | Time column | How it joins |
|---|---|---|---|---|
| Firewall session logs | Session and drop log of the internet edge firewall (`GW-FW-EDGE-01`) and the IT/OT boundary firewall (`GW-OT-FW-01`) | `network_logs/firewall/fw_<DEVICE>_<YYYY-MM>.csv` | `time_utc` = session end; start is `time_utc - duration_s` | `src_ip`, `src_port`, `dst_ip`, `dst_port`, `proto` = the 5-tuple of a row in Zeek `conn.log`; `src_ip` / `dst_ip` → host `ip`; `src_zone` / `dst_zone` → `network_zones` |
| Web and DNS filter logs | Access log of the transparent web and DNS filter (`GW-SRV-PROXY-01`) | `network_logs/proxy/web_proxy_<YYYY-MM>.csv` | `time_utc` = request time | `client_ip` → host `ip`; `user` → `users.username`; `host` = `server_name` in `ssl.log`, `host` in `http.log` or `query` in `dns.log` |
| Address lease logs | DHCP lease audit log of the user networks and the employee VPN address pool | `network_logs/dhcp/dhcp_leases_<YYYY-MM>.csv` | `time_utc` | `hostname` → host `hostname` (company machines); `ip`, `mac`; `scope` → `network_zones` |
| Perimeter packet capture | The opening packets of every flow through the internet edge, captured on the inside interface | `network_logs/pcap/perimeter_<YYYY-MM-DD>.pcap` | packet timestamp | 5-tuple = `conn.log`; the first packet has the `conn.log` `ts` |

Things to know:

- **What is sampled and what is complete.** These logs follow the Zeek logs. Traffic that people cause
  (browsing, opening applications and files) is a 1-in-200 sample. Traffic that machines produce on a schedule
  (agents, licence and update checks, time synchronisation), sessions through the remote-access gateway and the
  employee VPN, and the flows behind an alert or an audit record are recorded in full. Mail transfers follow the
  mail gateway log. So do not compute volumes from the sampled part without scaling, and do
  not read the number of rows a host has as a measure of how busy it was. Per log:
  - firewall: one record for every Zeek flow that crosses the device (so it inherits the rule above); dropped
    inbound internet traffic is a sample;
  - web filter: allowed requests follow the Zeek flows; blocked requests and DNS-filter rows are complete;
  - address leases: complete for the user networks; the VPN pool has one lease per VPN connection in Zeek, and
    those connections are complete;
  - packet capture: every Zeek flow that crosses the edge.
- **Two firewalls.** The edge firewall sits between the utility and the internet. The boundary firewall has
  three legs: the corporate side, the IT/OT DMZ (`ot-dmz`) and the control network (all other `ot-*` zones).
  A flow from the internet to a DMZ host passes both and is in both logs. Flows that stay inside the corporate
  network or inside the control network pass neither.
- **Addresses.** Firewall and capture show the internal addresses. Outbound sessions leave from one of four
  public addresses (`nat_src_ip`, 12.186.44.66 to .69). The utility's public block is 12.186.44.64/28:
  .65 firewall, .70 mail gateway, .71 website, .72 customer portal, .73 external DNS, .74 file transfer,
  .75 employee VPN, .76 OT remote-access gateway. Dropped inbound packets show the public address they were sent to.
- **Firewall rows.** `action` is `allow` or `deny`. `proto` is tcp, udp or icmp. An allowed session has the
  duration of its `conn.log` row; `bytes_sent` and `bytes_recv` count whole IP packets, headers included, so
  they equal `orig_ip_bytes` and `resp_ip_bytes` in `conn.log` and are a little larger than the payload bytes
  there and in the web filter log. `app` is `incomplete` when a TCP handshake never finished. Denies with rule
  `DEFAULT-DENY-INBOUND` are unsolicited internet traffic and have no `conn.log` row. While the control network
  is cut off from the rest, the boundary firewall passes nothing and logs what was refused.
- **Web filter rows.** The filter is transparent, so addresses are unchanged. For HTTPS it records the server
  name only (`method` CONNECT, `url_path` `-`). A `blocked` request never left the network, so there is no flow
  for it. `scheme` `dns` rows are lookups of names the filter has no category for; each carries the client,
  the name and the second of that lookup in `dns.log`. Other lookups are not logged. Byte counts are payload
  bytes, as in `conn.log`.
- **The `user` column.** A name means that person was logged on to the client and the request was made in
  their session (a browser, an application they run). Requests made by the operating system, by services and
  by agents carry `-`, whether or not somebody is logged on, and so do requests from servers and all DNS rows.
- **Leases.** Machines have reserved addresses, so a host's address never changes. Desktops renew every four
  days while they run and ask again each time they start; laptops ask when they are docked. A machine that is
  switched off logs nothing. Each employee VPN session gets a pool address (`scope` `corp-vpn`) for its
  duration. The VPN device is a company laptop (its registry `hostname`) or a home computer, whose name
  (`DESKTOP-…`, `LAPTOP-…`) and `mac` are not in the registry but stay the same from session to session.
- **Packet capture.** The capture keeps only the opening of each flow: for TCP the handshake and the first
  application message (the TLS ClientHello with the server name, the HTTP request, the mail server's greeting);
  for UDP the request and its answer (DNS and time synchronisation). Nothing after that is kept, so payload
  sizes in the capture are smaller than the flow's byte counts. Files open in tcpdump, Wireshark, tshark or Zeek.
- **Clocks.** Firewall `time_utc` is the session end. A web filter row carries the second in which the request
  was made: the start of the flow, or the following second when a plain-HTTP request falls just after a second
  boundary. The capture agrees with `conn.log` to the microsecond.

- **Employee VPN sessions.** `network_logs/audit/employee_vpn_sessions.csv` has one row per session: account, the
  address it came from, the device and the pool address. The lease log has the same pool address and device for
  the same seconds, and the sensor has one connection from that outside address to the VPN concentrator.
