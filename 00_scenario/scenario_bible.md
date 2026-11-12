# Hurricane Rafael Scenario Bible

Nov 7, 2026 · @Andrew Meinecke

## Synopsis and ground rules

Hurricane Rafael, a Category 3 storm, makes landfall on Mustang Island near Port Aransas, Texas, on D0, and its eye crosses Corpus Christi Bay. Over 180 days (D-60 to D+119) it cascades through the city's only water treatment plant, the Port of Corpus Christi, NAS Corpus Christi and Corpus Christi Army Depot, hospitals and supply chains. Underneath run five hidden threads, all sponsored by an unnamed foreign state: a sanctioned tanker going dark offshore, a contract and benefits fraud ring, a cyber and influence campaign, a cyberattack that opens the cargo valves of two tankers moored in port so the incoming surge spreads the oil, and a covert military attack on the port meant to delay a US Army deployment. Civilian, DoD and IC lanes each see part of the picture; only the joined data shows the whole.

**Ground rules**

- **Real:** places, counties, military installations, ports, infrastructure and government agencies.
- **Fictional:** people, companies, ship and aircraft identities (names, MMSI, tail numbers), the storm, and the foreign sponsor (STATE-X, never named). Check fictional names against real business and vessel registries before release.
- **Misconduct only by fictional actors:** real agencies, installations and infrastructure only suffer storm damage or are targeted; wrongdoing belongs only to fictional companies, people and STATE-X.
- **Scenario values:** counts, rates, dollar amounts and damage figures are scenario values, not real statistics. Calibrate baselines (911 volume, ER visits, vessel traffic, population) to real public data at generation.
- **One truth:** every dataset is rendered from the master scenario events list (MSEL) below. Lane storylines are views of it, never written separately.
- **Relative time:** D0 = landfall at 06:00Z. Map to calendar dates only at generation, with one constant offset for every source.
- **Registry IDs only:** every synthetic ID comes from the cast table and carries a SYN prefix. Generators look IDs up and never create them.
- **Answer key stays hidden:** every generated record carries a `truth_event_id`; it is stripped from released data and kept only in the answer key.
- **Unclassified exercise:** IC activity is modeled as open-source style analysis.

## Setting

The scenario covers the real Texas Coastal Bend: Nueces, San Patricio, Aransas and Kleberg counties. Equity comparisons use real census tracts selected by rule at generation, so no named neighborhood is pre-labeled. H3 cells are assigned once and reused by every source. Sources: [Port of Corpus Christi military role](https://portofcc.com/port-of-corpus-christi-and-u-s-army-partner-in-military-readiness-operations/), [O.N. Stevens power feed](https://www.corpuschristitx.gov/news/posts/city-responding-to-temporary-loss-of-power-at-o-n-stevens-water-treatment-plant/), [NAS Corpus Christi](https://www.cnic.navy.mil/CorpusChristi), [Harvey evacuations](https://www.defensenews.com/news/your-military/2017/08/24/navy-bases-in-texas-evacuate-jets-personnel-ahead-of-hurricane/), [Corpus Christi Army Depot during Harvey](https://www.army.mil/article/192898/corpus_christi_army_depot_prepares_for_tropical_storm_harvey), [DLA Distribution Corpus Christi](https://www.dla.mil/About-DLA/News/News-Article-View/Article/1324368/dla-distribution-corpus-christi-texas-bounces-back-from-hurricane-harvey/).

| Place ID | Name | Type | Role in the scenario |
| --- | --- | --- | --- |
| PLC-001 | Nueces County (FIPS 48355) | County | Corpus Christi; main impact area |
| PLC-002 | San Patricio County (FIPS 48409) | County | Portland, Ingleside, Aransas Pass |
| PLC-003 | Aransas County (FIPS 48007) | County | Rockport; heavy surge |
| PLC-004 | Kleberg County (FIPS 48273) | County | Kingsville |
| PLC-010 | Low-income surge-zone tracts | Census tracts | Bottom income quartile inside the surge or flood zone, highest share of households without a vehicle (ACS, selected at generation) |
| PLC-011 | High-income tracts | Census tracts | Top income quartile in Nueces County (ACS, selected at generation) |
| LF-01 | Mustang Island near Port Aransas | Landfall point | Eye crosses Corpus Christi Bay |
| PORT-07 | Port of Corpus Christi | Deep-water port | Largest US crude export gateway; strategic military seaport since 1997 |
| ANC-OFF | Offshore anchorage east of Port Aransas | Anchorage | Vessel queue while the ship channel is closed |
| FAC-DOD-01 | Naval Air Station Corpus Christi | Navy installation | Hosts the Army depot; backup generator EQP-2201 |
| FAC-DOD-02 | Corpus Christi Army Depot | Army depot on NAS Corpus Christi | Primary DoD rotary-wing depot maintenance |
| FAC-DOD-03 | Naval Air Station Kingsville | Navy installation | Jet training; aircraft evacuate |
| FAC-DOD-04 | NAS Joint Reserve Base Fort Worth | Navy installation | Evacuation destination for aircraft |
| FAC-DOD-05 | DLA Distribution Corpus Christi | Defense Logistics Agency site | Parts warehouse supporting the depot |
| FAC-DOD-06 | Fort Hood | Army installation | Aviation brigade scheduled to deploy through PORT-07 |
| FAC-UTL-01 | O.N. Stevens Water Treatment Plant (Calallen) | Water utility | City's sole treatment plant; pumps P-1 to P-4 are scenario IDs |
| FAC-UTL-02 | Transmission lines feeding O.N. Stevens | Power | Primary and backup feeds; both fail at D0 |
| FAC-INF-01 | US 181 Harbor Bridge and Nueces Bay Causeway | Bridges | Close in high winds; cut Portland and North Beach off from downtown |
| FAC-HOS-xx | Nueces County hospital emergency departments | Hospitals | Real facilities chosen at generation; operators not named |
| WW-xx | Corpus Christi wastewater treatment plants | Health sampling | Sampling sites chosen at generation |
| GAUGE-12 | Nueces River gauge at Calallen | Environmental sensor | Upstream river level |
| GAUGE-14 | NOAA tide gauge on Corpus Christi Bay | Environmental sensor | Surge level; station chosen at generation |
| PSAP-01 | Corpus Christi–Nueces County 911 center | Emergency communications | Dispatch system HOST-911-01 |
| TANK-0390 | Quellmar fuel terminal | Private fuel storage (fictional company) | Inner Harbor industrial area |
| STATE-X | Unnamed foreign state | Sponsor | Behind the hidden network; never named |
| TERM-01 | Crude terminal on the Inner Harbor ship channel | Oil terminal (fictional operator, Rendal Terminals) | Where the two attacked tankers stay moored through the storm |
| FAC-USCG-01 | US Coast Guard Sector Corpus Christi | Coast Guard unit | Leads the federal spill response in a Unified Command with the Texas General Land Office |
| WQ-01 to WQ-06 | Water-quality sondes in the ship channel, Nueces Bay and Corpus Christi Bay | Environmental sensors (scenario IDs) | Hydrocarbon and dissolved-oxygen readings |
| ENT-01 | Aransas Pass entrance channel and jetties at Port Aransas | Channel entrance | Gulf entrance to the Corpus Christi Ship Channel; mined at D+31 |

## Cast and entity registry

These are the synthetic keys every generator draws from; places in the Setting table are real, everything here is fictional. Lanes: C = civilian, D = DoD, I = IC. Network names use the reserved `.example` domain and a private-range ASN so nothing resolves to a real system.

| ID | Type and keys | Name | Role in the story | Lanes |
| --- | --- | --- | --- | --- |
| VSL-0012 | Vessel; MMSI-SYN-0101 | MV Gulf Provider | Relief cargo ship carrying 40 containers | C, D |
| VSL-0019 | Vessel; MMSI-SYN-0119 | Sealift ro-ro ship (synthetic name) | Carries the Fort Hood aviation brigade outload | D |
| VSL-0031 | Vessel; MMSI-SYN-0131, IMO-SYN-9031 | MV Halcyon Drift | Sanctioned tanker serving STATE-X; spoofs MMSI-SYN-0457 | I, then C, D |
| VSL-0457 | Vessel; MMSI-SYN-0457 | FV Pelican Ridge | Fishing vessel 600 nm away whose identity is spoofed | I |
| BRG-0044 | Barge; MMSI-SYN-0444 | Barge 44 | Receives the transferred fuel | I, D |
| ACF-0201 | Aircraft: C-17; ICAO-SYN-AE0201, callsign SYN41 | Military airlift | 26 relief sorties into NAS Corpus Christi | D |
| ACF-0301 | Aircraft; ICAO-SYN-A00301 | Civil relief charter | 14 relief flights | C |
| EQP-1101 to 1104 | Pumps; NSN-SYN-4320-0001 | O.N. Stevens pumps P-1 to P-4 (scenario IDs) | P-2 fails and P-3 overheats at D0 | C |
| EQP-2201 | Generator; NSN-SYN-6115-0001 | NAS Corpus Christi backup generator | Fails on contaminated fuel at D+40 | D |
| SUP-0102 | Supplier; UEI-SYN-0102 | Gulf Relief Logistics | Legitimate freight forwarder | C |
| SUP-0219 | Supplier; UEI-SYN-0219 | Delta Pumps & Controls | Legitimate pump-parts supplier; quoted 9-day lead time, actual 34 | C, D |
| SUP-0388 | Supplier; UEI-SYN-0388 | Vantorra Restoration LLC | Shell company; debris contract PIID-SYN-0071 | C, I |
| SUP-0390 | Supplier; UEI-SYN-0390 | Quellmar Fuel Partners | Shell company; NAS fuel contract PIID-SYN-0075 | C, D, I |
| ORG-0901 | Company | Brannoch Maritime Holdings | Operates Halcyon Drift for STATE-X; hidden owner of SUP-0388 and SUP-0390 | I |
| ACT-KES | Threat actor; ASN-SYN-64512 | KESTREL | STATE-X-linked cyber and influence group | C, D, I |
| SYN-PER-700001 to 700006 | Synthetic identities | Fraud ring claimants | Six fake benefit claimants | C, I |
| SOC-ACC-5001 to 5040 | Social accounts | Coordinated network | 40 inauthentic accounts | C, I |
| BANK-SYN-71, 72, 73 | Bank accounts | Receiving accounts | 71 and 72 shared with SUP-0388 and SUP-0390 | C, I |
| HOST-PORTAL-01 | Network host | Disaster-aid benefits portal (scenario system) | Credential-stuffing target | C |
| HOST-DOD-LOG-02 | Network host | NAS Corpus Christi logistics system (scenario system) | Phishing target | D |
| HOST-911-01 | Network host | 911 dispatch system (scenario system) | Phishing target | C |
| DOM-SYN-01 | Domain; aid-help-portal.example | Lure domain | Used in phishing and disinformation links | C, D, I |
| VSL-0041 | Vessel: crude tanker; MMSI-SYN-0141 | MT Kalvora Star | Laden tanker moored at TERM-01; cargo valves opened remotely at D0 | C, D, I |
| VSL-0042 | Vessel: crude tanker; MMSI-SYN-0142 | MT Ostrel Bay | Second laden tanker at TERM-01; same attack | C, D, I |
| SUP-0455 | Supplier; UEI-SYN-0455 | Brightwake Marine Systems | Legitimate remote-maintenance vendor for tanker cargo systems; victim whose credentials are stolen | C, I |
| ORG-0950 | Company | Rendal Terminals | Operator of TERM-01; victim | C |
| HOST-VSL-01 | Network host | Tanker cargo-control networks (scenario system) | Reached through the vendor's remote-maintenance access | C, I |
| ACT-SOF | Threat actor | STATE-X special operations unit | Runs the drone overflights, device laying and GPS interference | D, I |
| UAS-SYN-01 to 06 | Unidentified drones | Overflight drones | Scout NAS Corpus Christi and the depot on six nights, D+1 to D+10 | D, I |
| DEV-01, DEV-02 | Seabed explosive devices | Channel devices | Laid from Halcyon Drift at D+31; DEV-01 detonates at D+44, DEV-02 cleared at D+52 | C, D, I |
| VSL-0077 | Vessel: harbor tug; MMSI-SYN-0177 | Tug Corrin Bay | Damaged by DEV-01 at the jetties; 2 crew injured | C, D |
| JAM-01 | Interference source | GPS interference transmitter | Operated near TANK-0390 from D+38 to D+43 | D, I, C |

## Hidden truths

Seven threads run under the scenario. T2, T3, T4, T6 and T7 are one STATE-X network: Brannoch Maritime Holdings (ORG-0901) ties the tanker to the shell vendors, bank accounts BANK-SYN-71 and 72 tie the vendors to the cyber campaign, the tanker attack reuses KESTREL's infrastructure, and the military thread uses Halcyon Drift's dark window and the Quellmar terminal.

| Thread | What really happens | Lanes | Phases |
| --- | --- | --- | --- |
| T1 Storm cascade | Surge floods the Coastal Bend; both power feeds to O.N. Stevens fail; plant pumps fail; a citywide boil-water notice drives GI illness; pump parts arrive 25 days late; NAS and depot operations pause. Natural, no adversary. | C, D | 2–5 |
| T2 Dark vessel | MV Halcyon Drift goes dark at the offshore anchorage, spoofs FV Pelican Ridge's MMSI, and transfers 380 m³ of fuel to Barge 44. The fuel is sold through SUP-0390 to NAS Corpus Christi and fouls the station's backup generator. | I, D, C | 1, 4, 5 |
| T3 Fraud ring | SUP-0388 and SUP-0390 share an address, a bank account and a hidden owner (ORG-0901). They win sole-source contracts, overbill debris removal, and receive diverted benefit payments. | C, I, D | 1, 3–6 |
| T4 KESTREL campaign | Reconnaissance at D-35, phishing at D+1 to D+3, then credential stuffing at D+62 to D+70 that diverts benefit payments to BANK-SYN-71, 72 and 73. Its disinformation network links to the same lure domain. | C, D, I | 1, 3, 5, 6 |
| T5 Equity gap | Low-income surge-zone tracts receive aid dollars at half their share of residents, and their median 911 response time is 2.1× that of high-income tracts. Emerges from the storm and access, not from an adversary. | C | 3–6 |
| T6 Tanker cyberattack | KESTREL steals a remote-maintenance vendor's credentials, reaches the cargo systems of two laden tankers moored at TERM-01, and two hours before landfall opens their cargo valves and silences alarms. About 9,000 barrels spill, and the surge spreads the oil across 85 km² of bay and shoreline. | C, D, I | 1–6 |
| T7 Opportunistic military attack | STATE-X exploits the storm to delay the Fort Hood brigade's deployment through the strategic seaport. Drones scout NAS Corpus Christi while its sensors are down; Halcyon Drift's dark window covers laying two seabed explosive devices off the entrance channel; GPS interference from the Inner Harbor disrupts relief flights; one device detonates beside a tug at D+44, closing the channel for 14 days as STATE-X moves militarily abroad. | D, I, C | 1, 3–6 |

## Phase narratives

Six 30-day phases match the six months of the scenario grid. Each phase's injects are listed in the MSEL by ID prefix (EVT-01xx for phase 1, and so on).

### Phase 1: Baseline (D-60 to D-31)

The Coastal Bend runs normally, with about 310 911 calls and 520 ER visits a day in Nueces County. Pump P-2 at O.N. Stevens creeps up in vibration and its work order is deferred. MV Halcyon Drift loiters offshore among the crude-export tankers under its true identity, two new vendors register at the same Corpus Christi address, and KESTREL scans the aid portal and NAS Corpus Christi's logistics system. KESTREL also steals remote-access credentials from Brightwake Marine Systems, a vendor that maintains tanker cargo systems, and STATE-X announces naval exercises abroad.

### Phase 2: Signals (D-30 to D-1)

The seasonal outlook calls for an active season. Rafael forms in the northwestern Caribbean at D-10, crosses the Yucatan into the Gulf, and the forecast cone covers the Coastal Bend by D-5. The Nueces River rises at Calallen and 40 relief containers are booked. NAS Corpus Christi and NAS Kingsville fly their aircraft to NAS JRB Fort Worth, and the Army depot secures helicopters in hangars. The Coast Guard sets Port Condition X-Ray at D-3, postponing a Fort Hood aviation brigade outload; the port closes to inbound ships at D-2 (Yankee) with 14 vessels queued offshore, and to all traffic at D-1 (Zulu). KESTREL quietly uses the vendor's access to reach two laden tankers, MT Kalvora Star and MT Ostrel Bay, which stay moored at an Inner Harbor terminal through the storm.

### Phase 3: Landfall (D0 to D+29)

Two hours before landfall, commands sent through the vendor's access open the two tankers' cargo valves and silence their alarms; about 9,000 barrels of crude spill before crews close the valves. Rafael makes landfall on Mustang Island at 06:00Z on D0 as a Category 3 storm, pushing a 3.4 m surge into Corpus Christi and Nueces bays that carries the oil across 85 km² of bay and shoreline. Both power feeds to O.N. Stevens fail three hours later, taking down pumps P-2 and P-3; a citywide boil-water notice follows at D+4. 911 calls peak at 2,900 a day, 61% from low-income surge-zone tracts; the Harbor Bridge and Nueces Bay Causeway close, and depot hangars take roof damage and water intrusion. KESTREL phishes city and NAS staff, a disinformation network spreads rumors, and both shell vendors win sole-source contracts. Unidentified drones fly over NAS Corpus Christi and the depot on six nights while storm-damaged perimeter sensors are down.

### Phase 4: Response (D+30 to D+59)

The ship channel partly reopens at D+30, but the anchorage backlog delays MV Gulf Provider and spill cleanup restricts the inner channel until D+44. Halcyon Drift goes dark for 14 hours at D+31, drops two seabed explosive devices off the entrance channel, and transfers fuel to Barge 44, and that fuel reaches NAS Corpus Christi through SUP-0390. Forty relief flights land, pump parts finally arrive at D+36, and the station's backup generator fails on contaminated fuel at D+40. GPS interference from the Inner Harbor disrupts the last relief flights. At D+44, as the outload is about to resume, one device detonates beside a harbor tug at the Port Aransas jetties; the channel closes for mine clearance until D+58, STATE-X moves militarily abroad at D+46, and the Fort Hood outload finally sails from D+59.

### Phase 5: Recovery (D+60 to D+89)

FEMA approves Individual Assistance on D+57 after delayed damage assessments; registration opens D+60 and takes 48,000 claims in 30 days. KESTREL credential stuffing takes over 410 portal accounts; with six synthetic identities, the ring diverts $3.9M into three bank accounts, two shared with the shell vendors. SUP-0388 bills 2.3× the debris tonnage that imagery supports, and a second disinformation wave claims contractors are stealing aid. Oil spill damage claims from fishers and shoreline owners reach 4,200.

### Phase 6: Review (D+90 to D+119)

The civilian review finds low-income surge-zone tracts received aid dollars at half their share of residents. The DoD after-action review traces NAS Corpus Christi readiness falling from 92% to 61% and recovering to 85% by D+110. The IC assessment ties KESTREL, the disinformation network and the shell vendors' bank accounts to Halcyon Drift's operator, Brannoch Maritime Holdings, acting for STATE-X. It also attributes the tanker attack and the channel mining to STATE-X, both timed to the storm to spread damage and delay the US deployment. The DoD review adds force-protection gaps: six nights of undetected drone overflights and a channel mined without detection.

## Lane storylines

Each lane sees a filtered view of the same MSEL. No lane can close T2, T3 or T4 alone: the case needs the IC's ship and radar evidence, DoD's fuel-fault maintenance note, and civilian vendor and payment records.

### Civilian agencies

**Story:** prepare for the storm, absorb the 911 surge, manage the water crisis and the tanker spill under Unified Command, move relief supplies, pay claims, then review fraud and equity.

**Sees:** weather, river gauges, water-quality sondes, oil-slick imagery, 911, ER and wastewater data, pump telemetry and maintenance, supply delays, contracts and payments, census, maps, social media rumors.

**Blind spots:** has no view of the AIS gap or radar detection; sees the fraud only as payment anomalies until D+70; doesn't know SUP-0390's fuel went to NAS Corpus Christi.

### DoD

**Story:** set the readiness baseline, evacuate aircraft, recover from depot storm damage and phishing, fly relief, support the spill response, lose the base generator, clear the mined channel, re-launch the delayed deployment, then run the after-action review.

**Sees:** base telemetry and maintenance, aircraft and sealift tracks, drone video, base network logs, its own fuel contract and supply records.

**Blind spots:** has no view of benefits fraud; treats SUP-0390 as a bad fuel vendor, not part of a network; misses the drone overflights while perimeter sensors are down; can't tie the mines to Halcyon Drift's dark window until the IC shares it.

### Intelligence community

**Story:** build pattern of life on Halcyon Drift, detect KESTREL reconnaissance, track phishing and disinformation during landfall, catch the dark-vessel transfer, trace the tanker intrusion to the stolen vendor credentials, connect the dark-vessel window to the mining, link the credential stuffing, then attribute the network to Brannoch Maritime Holdings.

**Sees:** ship and aircraft tracks, optical and radar imagery, social media and news, network intrusion indicators.

**Blind spots:** needs civilian payment and vendor records and DoD maintenance records to prove the fuel and money trail.

## Master scenario events list

The 64 injects below are the ground truth, in time order; every generated record traces to one of them through `truth_event_id`. Lanes: C = civilian, D = DoD, I = IC.

| ID | Time | Place | What happens | Thread | Lanes | Observed in |
| --- | --- | --- | --- | --- | --- | --- |
| EVT-0101 | D-60 | PLC-001 | Baseline: about 310 911 calls and 520 ER visits a day | T1 | C | 911, public health, census |
| EVT-0102 | D-55 | FAC-UTL-01 | Pump P-2 (EQP-1102) at O.N. Stevens trends up in vibration; work order deferred | T1 | C | Telemetry, maintenance |
| EVT-0103 | D-50 | FAC-DOD-01 | NAS Corpus Christi readiness 92%; backup generator EQP-2201 healthy on its regular fuel supplier | T2 | D | Telemetry, maintenance, payments |
| EVT-0104 | D-45 | Gulf, 40 nm offshore | Halcyon Drift (VSL-0031) loiters among crude-export tankers under its true MMSI | T2 | I | Ship tracks, satellite |
| EVT-0105 | D-40 | PLC-001 | SUP-0388 and SUP-0390 register with the same Corpus Christi address and bank account BANK-SYN-71 | T3 | C | Payments (vendor registry) |
| EVT-0108 | D-40 | Abroad | STATE-X announces naval and special-operations exercises far from the Gulf | T7 | I, D | News |
| EVT-0106 | D-35 | HOST-PORTAL-01, HOST-DOD-LOG-02 | KESTREL scans the aid portal and NAS logistics system from ASN-SYN-64512 | T4 | C, D, I | Network logs |
| EVT-0107 | D-33 | SUP-0455 | KESTREL phishes Brightwake Marine Systems from ASN-SYN-64512 and steals its remote-access credentials for tanker cargo systems | T6 | I | Network logs |
| EVT-0201 | D-21 | Gulf | Seasonal outlook: above-normal storm activity | T1 | C, D | Weather |
| EVT-0209 | D-20 | HOST-VSL-01 | KESTREL uses the vendor credentials to reach the cargo-control networks of MT Kalvora Star and MT Ostrel Bay; sessions look like routine maintenance | T6 | None at the time; I in hindsight | Network logs |
| EVT-0202 | D-10 | Gulf | Tropical Storm Rafael forms; forecast cone covers the Coastal Bend by D-5 | T1 | C, D, I | Weather, news |
| EVT-0203 | D-7 | GAUGE-12 | Tropical moisture ahead of Rafael and a stalled front: Nueces River rising at Calallen; soil moisture at 85th percentile | T1 | C | Environmental sensors |
| EVT-0204 | D-5 | PORT-07 | 40 relief containers booked on MV Gulf Provider through SUP-0102 | T1 | C | Supply, payments |
| EVT-0205 | D-4 | FAC-DOD-01, FAC-DOD-03 | NAS Corpus Christi and NAS Kingsville fly aircraft to NAS JRB Fort Worth (FAC-DOD-04) | T1 | D | Aircraft tracks, maintenance |
| EVT-0206 | D-4 | FAC-DOD-02 | Corpus Christi Army Depot halts work and secures helicopters and components in hangars | T1 | D | Maintenance, supply |
| EVT-0207 | D-3 to D-1 | PORT-07, ANC-OFF | Coast Guard sets Port Condition X-Ray (D-3, port open; brigade outload postponed), Yankee (D-2, closed to inbound; 14 vessels queue offshore, including Gulf Provider and Halcyon Drift; exports halt) and Zulu (D-1, closed to all; anchored ships put to sea) | T1, T2 | C, D, I | Ship tracks, satellite, supply |
| EVT-0210 | D-3 to D-1 | TERM-01 | Laden tankers Kalvora Star (VSL-0041) and Ostrel Bay (VSL-0042) get Coast Guard approval to stay moored at the Inner Harbor terminal through Zulu, with skeleton crews | T6 | C, I | Ship tracks, supply |
| EVT-0208 | D-2 | PLC-001 to 004 | Pre-storm radar reference images acquired | T1 | C, I | Satellite |
| EVT-0313 | D0 04:00Z | TERM-01, HOST-VSL-01 | Commands through the vendor session open both tankers' cargo valves and silence alarms; crews close the valves by 05:30Z after about 9,000 barrels spill | T6 | C, D, I | Network logs, telemetry, maintenance |
| EVT-0301 | D0 06:00Z | LF-01 | Rafael makes landfall on Mustang Island: Category 3, 3.4 m surge into Corpus Christi and Nueces bays | T1 | C, D, I | Weather, satellite, news |
| EVT-0302 | D0 09:00Z | FAC-UTL-02, FAC-UTL-01 | Both power feeds to O.N. Stevens fail; pump P-2 fails and P-3 overheats | T1 | C | Telemetry, maintenance, maps |
| EVT-0314 | D0 to D+2 | PORT-07, PLC-001, PLC-002 | Surge and wind push the oil out the ship channel into Nueces and Corpus Christi bays, covering 85 km² of water, marsh and shoreline; hydrocarbon readings spike at WQ-01 to WQ-06 | T6 | C, D, I | Environmental sensors, satellite, drone video, news |
| EVT-0303 | D0 to D+2 | PLC-010 | 911 calls peak at 2,900 a day, 61% from low-income surge-zone tracts | T1, T5 | C | 911 |
| EVT-0304 | D+1 | FAC-INF-01 | Harbor Bridge and Nueces Bay Causeway closed; Portland and North Beach cut off from downtown | T1, T5 | C, D | Maps, drone video, 911 |
| EVT-0305 | D+1 | PLC-001 to 003 | Radar flood extent: 112 km² inundated | T1 | C, I | Satellite |
| EVT-0315 | D+1 | FAC-USCG-01 | Coast Guard Sector Corpus Christi and the Texas General Land Office stand up Unified Command; on-water response waits for winds to drop; Navy salvage support requested | T6 | C, D | News, payments |
| EVT-0306 | D+1 to D+3 | HOST-911-01, HOST-DOD-LOG-02 | KESTREL phishing: 1,200 aid-portal lures linking aid-help-portal.example; 7 city and 3 NAS credentials stolen | T4 | C, D, I | Network logs |
| EVT-0318 | D+1 to D+10 | FAC-DOD-01, FAC-DOD-02 | Unidentified drones (UAS-SYN-01 to 06) overfly NAS Corpus Christi and the depot on six nights while storm-damaged perimeter sensors are down; residents post videos of the lights | T7 | I, D | Social media, maintenance |
| EVT-0307 | D+2 | FAC-DOD-02 | Drone survey: depot hangar roof damage and water intrusion | T1 | D | Drone video, maintenance |
| EVT-0308 | D+2 | FAC-UTL-01 | Pump parts ordered from SUP-0219 (quoted 9 days); its local warehouse is flooded, so parts ship from out of state | T1 | C | Supply, payments |
| EVT-0316 | D+2 to D+5 | HOST-VSL-01 | Cyber responders find the valve commands came through the vendor's remote session, not crew consoles; the vendor's credentials are revoked | T6 | C, I | Network logs, maintenance |
| EVT-0309 | D+2 to D+20 | Online | 40 accounts (SOC-ACC-5001 to 5040) post 18,000 rumors ("military seizing homes", "aid only for wealthy neighborhoods", "refinery negligence caused the spill") linking the lure domain | T4 | C, D, I | Social media, news |
| EVT-0317 | D+3 to D+21 | Shoreline tracts in PLC-001 and PLC-002 | Respiratory and skin complaints at ERs serving shoreline tracts +60%; fishing and shellfish harvesting closed in Nueces and Corpus Christi bays | T6 | C | Public health, news |
| EVT-0310 | D+4 to D+14 | PLC-001, WW-xx | Citywide boil-water notice at D+4; wastewater norovirus rises at D+5; GI ER visits +180% from D+6 to D+14 | T1 | C | Public health |
| EVT-0311 | D+10 | PLC-001 | Debris contract PIID-SYN-0071 ($14.2M, sole-source) awarded to SUP-0388 | T3 | C | Payments |
| EVT-0312 | D+12 | FAC-DOD-01 | Emergency generator fuel contract PIID-SYN-0075 ($2.1M) awarded to SUP-0390 after the regular supplier's terminal floods | T2, T3 | D | Payments, supply |
| EVT-0401 | D+30 | PORT-07, ANC-OFF | Ship channel partly reopens; Gulf Provider's berth delayed by the anchorage backlog until D+33 | T1 | C, D | Ship tracks, supply |
| EVT-0410 | D+30 to D+44 | PORT-07 | Shoreline cleanup continues; the inner ship channel stays restricted for vessel decontamination until D+44 | T6 | C, D | Ship tracks, drone video, payments |
| EVT-0402 | D+31 02:00–16:00Z | ANC-OFF | Halcyon Drift's AIS goes silent for 14 h; a vessel broadcasting MMSI-SYN-0457 appears at the anchorage while the real Pelican Ridge reports 600 nm away | T2 | I | Ship tracks |
| EVT-0411 | D+31 04:20Z | ENT-01 | Radar pass shows an unidentified hull loitering 2 nm off the entrance channel for 40 minutes during Halcyon Drift's AIS gap: DEV-01 and DEV-02 are laid | T7, T2 | I | Satellite |
| EVT-0403 | D+31 09:30Z | ANC-OFF | Radar shows two hulls side by side, one with no AIS match: fuel transfer to Barge 44 | T2 | I | Satellite |
| EVT-0404 | D+32 | TANK-0390 | Barge 44 delivers 380 m³ of fuel up the ship channel to SUP-0390; deliveries to NAS Corpus Christi invoiced from D+33 | T2, T3 | C, D, I | Ship tracks, supply, payments |
| EVT-0405 | D+34 to D+43 | FAC-DOD-01 | 26 military C-17 (ACF-0201) and 14 civil charter (ACF-0301) relief flights into NAS Corpus Christi | T1 | C, D | Aircraft tracks, supply |
| EVT-0406 | D+36 to D+39 | FAC-UTL-01 | Pump parts arrive at D+36 (34 days, 25 late); P-2 restored at D+38; boil-water notice lifted at D+39 | T1 | C | Supply, maintenance, telemetry |
| EVT-0412 | D+38 to D+43 | Near TANK-0390 | GPS interference from JAM-01 near the Quellmar terminal; relief and NAS aircraft report GPS anomalies within 60 km and ADS-B navigation-integrity values drop | T7, T3 | D, I, C | Aircraft tracks |
| EVT-0407 | D+40 | FAC-DOD-01 | Generator EQP-2201 fails; technician note cites injector fouling from water-contaminated fuel, lot traced to SUP-0390; readiness drops to 61% | T2 | D | Telemetry, maintenance |
| EVT-0413 | D+44 06:10Z | ENT-01 | DEV-01 detonates beside the harbor tug Corrin Bay (VSL-0077) at the jetties; tug damaged, 2 crew injured | T7 | C, D, I | Ship tracks, news, social media |
| EVT-0414 | D+44 to D+58 | ENT-01, PORT-07 | Coast Guard closes the channel; Navy explosive ordnance disposal and mine countermeasures teams search it and recover DEV-02 at D+52; channel reopens at D+58; crude exports halted 14 days | T7 | C, D, I | Ship tracks, maintenance, supply, payments |
| EVT-0408 | D+45 | PLC-010 | ER visits back near baseline except low-income surge-zone tracts (+40%) | T1, T5 | C | Public health |
| EVT-0415 | D+46 | Abroad | STATE-X begins military operations abroad while the brigade's equipment sits at the port | T7 | I, D | News |
| EVT-0409 | D+59 to D+64 | PORT-07, FAC-DOD-06 | Fort Hood aviation brigade outload sails on sealift ship VSL-0019, 14 days after its planned D+45 restart; depot back at full work with parts from DLA Distribution Corpus Christi (FAC-DOD-05) | T7, T1 | D | Ship tracks, supply, maintenance |
| EVT-0501 | D+57 to D+89 | PLC-001 to 004 | FEMA Individual Assistance approved D+57 after delayed damage assessments; registration opens D+60; 48,000 claims filed | T5 | C | Payments |
| EVT-0508 | D+60 to D+89 | PLC-001 to 003 | 4,200 oil spill damage claims from fishers and shoreline owners | T6 | C | Payments |
| EVT-0502 | D+62 to D+70 | HOST-PORTAL-01 | KESTREL credential stuffing from ASN-SYN-64512: 220,000 attempts, 410 account takeovers, direct-deposit details changed | T4 | C, I | Network logs, payments |
| EVT-0503 | D+64 to D+80 | BANK-SYN-71, 72, 73 | 410 hijacked accounts plus 6 synthetic identities route $3.9M to three accounts; 71 and 72 are shared with SUP-0388 and SUP-0390 | T3, T4 | C, I | Payments |
| EVT-0504 | D+66 to D+80 | Out of area | Prepaid card purchases from diverted funds cluster more than 300 km from Corpus Christi | T3 | C | Payments |
| EVT-0505 | D+70 | PLC-002, PLC-003 | SUP-0388 bills 2.3× the debris tonnage that drone and satellite estimates support | T3 | C | Payments, drone video, satellite |
| EVT-0506 | D+72 | FAC-DOD-01 | Generator overhaul parts ordered from SUP-0219; Navy contracting flags SUP-0390 for fuel quality | T2, T3 | D | Maintenance, supply, payments |
| EVT-0507 | D+75 to D+85 | Online | Second disinformation wave from the same 40 accounts: "contractors are stealing aid" (partly true) | T4 | C, I | Social media, news |
| EVT-0601 | D+90 | PLC-010, PLC-011 | Equity review: low-income surge-zone tracts received aid dollars at half their share of residents; median 911 response 2.1× high-income tracts | T5 | C | Census, payments, 911, maps |
| EVT-0602 | D+95 | FAC-DOD-01, FAC-DOD-02 | After-action review: NAS Corpus Christi readiness fell from 92% to 61%, back to 85% by D+110; force-protection gaps from undetected drone overflights and channel mining | T2, T7 | D | Telemetry, maintenance, supply |
| EVT-0603 | D+100 | All | IC assessment ties KESTREL, the disinformation network, BANK-SYN-71 and 72, the tanker intrusion and the channel mining to ORG-0901 and STATE-X; shared with C and D | T2, T3, T4, T6, T7 | I | All |
| EVT-0605 | D+105 | PORT-07 | Coast Guard and CISA issue a maritime cyber advisory on vendor remote access to vessel cargo systems | T6 | C, D, I | News |
| EVT-0604 | D+110 | FAC-UTL-02, FAC-INF-01 | Recovery plan: harden the O.N. Stevens power feeds and review bridge wind-closure procedures | T1 | C, D | Maps |

## Answer key

Each hidden truth is proven by one join path across sources. Run each path as a query against the generated data before release; if it doesn't return the listed evidence, regenerate.

| Thread | Join path (source: key) | Proving evidence |
| --- | --- | --- |
| T1 Storm cascade | Weather: storm track at D0 → environmental sensors: GAUGE-12, GAUGE-14 → satellite: flood extent by H3 cell → maps: FAC-UTL-02 power feeds → telemetry and maintenance: EQP-1102, EQP-1103 by serial → supply: SUP-0219 order → public health: WW-xx and FAC-HOS-xx by place and time | Pumps fail 3 h after the power feeds; GI ER visits spike a day after the wastewater rise; parts arrive 25 days late |
| T2 Dark vessel | Ship tracks: VSL-0031 gap at ANC-OFF at D+31, MMSI-SYN-0457 at the anchorage while VSL-0457 is 600 nm away → satellite: unmatched hull in the same H3 cell at D+31 09:30Z → ship tracks: BRG-0044 up the ship channel to TANK-0390 → supply: 380 m³ receipt under UEI-SYN-0390 → payments: PIID-SYN-0075 invoices → maintenance: EQP-2201 note with fuel lot ID | Same place and time window across AIS and radar; the fuel lot in NAS maintenance matches the SUP-0390 receipt |
| T3 Fraud ring | Vendor registry: UEI-SYN-0388 and 0390 share an address and BANK-SYN-71 → payments: PIID-SYN-0071 and 0075 → drone and satellite: debris estimate vs invoiced tonnage → payments: benefit deposits to BANK-SYN-71 and 72 → ownership: ORG-0901 | Same bank accounts receive vendor payments and diverted benefits; billing at 2.3× the imaged debris |
| T4 KESTREL | Network logs: ASN-SYN-64512 scans at D-35 → phishing through aid-help-portal.example at D+1 to D+3 → social media: SOC-ACC-5001 to 5040 posts linking the same domain → network logs: credential stuffing from the same ASN at D+62 to D+70 → payments: changed deposit details to BANK-SYN-71, 72, 73 | One ASN and one domain appear in NAS logs, city logs and social posts |
| T5 Equity gap | Census: PLC-010 vs PLC-011 income and vehicle access → 911: response time by H3 cell → maps: Harbor Bridge and causeway closures → payments: aid dollars by tract | Aid dollars at half the residents' share; 911 response 2.1× high-income tracts |
| T6 Tanker cyberattack | Network logs: SUP-0455 vendor phished from ASN-SYN-64512 at D-33 → vendor remote sessions on HOST-VSL-01 at D-20 and D0 04:00Z → telemetry: cargo tank levels fall on VSL-0041 and VSL-0042 at D0 04:00Z → environmental sensors: hydrocarbon spikes at WQ-01 to WQ-06 → satellite: oil slick extent by H3 cell → public health: respiratory and skin ER visits by shoreline tract → payments: spill damage claims | Valve commands came from the vendor's session, not crew consoles, when the vendor had no open work order; the session source matches KESTREL's ASN |
| T7 Opportunistic military attack | Social media: geotagged drone-light posts near FAC-DOD-01 at D+1 to D+10 → maintenance: perimeter-sensor repair orders showing sensors down those nights → satellite: hull 2 nm off ENT-01 at D+31 04:20Z, inside VSL-0031's AIS gap → aircraft tracks: ADS-B navigation-integrity drop centered near TANK-0390 at D+38 to D+43 → ship tracks and news: VSL-0077's AIS stops at the jetties at D+44 06:10Z → maintenance: EOD report on DEV-02 recovered at D+52 → news: STATE-X operations abroad from D+46 | The device positions lie on the only track Halcyon Drift could have sailed during its gap; the interference centroid sits at the Quellmar terminal; the detonation lands on the eve of the planned outload restart |

**Links between threads:** T2 and T3 join on UEI-SYN-0390 and ORG-0901; T3 and T4 join on BANK-SYN-71 and 72. T4 and T6 join on ASN-SYN-64512. T7 joins T2 through VSL-0031's AIS gap and T3 through TANK-0390, where the GPS interference centers.

## Rendering rules

Each source is generated as background data plus the scenario signal, then degraded on purpose so analysts must work for the joins. Every record keeps its place, time and registry IDs; degradation never removes the keys an answer-key path depends on.

| Source | Baseline volume | Scenario signal | Deliberate degradation |
| --- | --- | --- | --- |
| Satellite imagery | 1 optical pass a day; radar every 6 days, plus tasked passes at D-2, D+1, D+31 | Flood extent at D+1; oil slick from D+1 to D+20; hull off the entrance channel at D+31 04:20Z and unmatched hull at 09:30Z; debris from D+10 to D+70 | Clouds block optical from D-2 to D+3; ±30 m geolocation error |
| Drone video | Weekly base inspections | Depot flood at D+2; debris surveys from D+10 to D+70 | Partial coverage; 5% of frames missing GPS tags |
| Ship tracks (AIS) | About 120 vessels a day in the area | Queue at D-3; Halcyon gap and spoof at D+31; Barge 44 at D+32; tug AIS stops at D+44; 14-day channel closure | 2–5% random message loss; coverage gaps from D0 to D+2 |
| Aircraft tracks (ADS-B) | About 60 flights a day | Evacuation at D-4; 40 relief flights from D+34 to D+43; navigation-integrity drop near the Inner Harbor from D+38 to D+43 | Military aircraft broadcast only 50% of the time |
| Environmental sensors | 15-minute readings from 2 river gauges, 20 air-quality sensors and 6 water-quality sondes | River rises from D-7 and peaks at D+1; hydrocarbon spikes at WQ-01 to WQ-06 from D0 | GAUGE-14 offline from D0 to D+5 (flooded) |
| Equipment telemetry | 1-minute readings from 5 assets | P-2 and P-3 at D0; tanker cargo levels drop at D0 04:00Z; EQP-2201 at D+40 | Data lost during the outage from D0 to D+3 |
| Maintenance records | About 15 work orders a week | Pump and generator work orders with technician notes; perimeter-sensor repairs; tanker cargo-system inspections; EOD and mine-clearance reports | Typos in free text; 10% of records missing serials (never EQP-2201 at D+40) |
| Supply and inventory | Daily stock for about 200 SKUs | Relief containers; pump parts 25 days late; 380 m³ fuel receipt | Receipts logged 1–3 days late |
| Network security logs | About 2 million events a day | Scans at D-35; vendor phishing at D-33; vendor sessions on tanker networks at D-20 and D0; phishing D+1 to D+3; credential stuffing D+62 to D+70 | Retention gaps; NAT hides some source IPs, but not ASN-SYN-64512 |
| Emergency 911 calls | About 310 a day | Peak of 2,900 a day, 61% from low-income surge-zone tracts | Location error up to 500 m; 8% duplicate calls |
| Payments and claims | About 1,500 transactions a day | Contracts; 48,000 claims; $3.9M diverted; 4,200 spill claims; 14-day crude-export halt | 1–5 day posting delays; vendor name variants |
| Weather and climate | Hourly grids | Rafael's track from D-10 to D+2 | None: use real or modeled grids as the physical driver |
| Infrastructure maps | Static layers | Bridge closure at D+1; substation status | Status layer updated 1–3 days late |
| Census demographics | Static by tract | Low-income surge-zone tracts vs high-income tracts (ACS) | None: reference data |
| News and social media | About 5,000 posts a day | 18,000 rumor posts from D+2 to D+20; drone-light posts near NAS from D+1 to D+10; tug blast at D+44; second wave D+75 to D+85 | Bot and real posts mixed; 30% without geotags |
| Public health | Daily ER counts by hospital; wastewater twice a week | GI visits +180%; respiratory and skin complaints +60% in shoreline tracts from D+3 to D+21; low-income surge-zone tracts +40% at D+45 | 1–2 day reporting lag; counts under 11 suppressed |
