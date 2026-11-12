"""Independent narrative audit 2026-11-10, major and minor defects D16-D54."""

STORIES = {
    # D17: canon is Fort Hood; the hospital's request went to DSHS and the National Disaster Medical System (PUB-161)
    "NWS-P002-08": {
        "headline": "Shoreline Regional at 140 percent capacity; second hospital full; state and federal medical teams requested",
        "dek": "Both major Corpus Christi area hospitals have reached or exceeded capacity two days after Hurricane Rafael, with storm surge trauma patients overwhelming emergency departments and officials requesting state and federal medical support.",
        "replace": [("The hospital has formally requested a National Guard medical team through the Texas Division of Emergency Management, citing", "The hospital has formally requested mutual aid support from the Texas Department of State Health Services and FEMA's National Disaster Medical System, citing"),
                    ("The National Guard deployment request was confirmed by TDEM, which said a Texas Army National Guard medical support team was being mobilized from Fort Cavazos and was expected to arrive within 24 to 36 hours.",
                     "The request was confirmed by the state health department, which said a medical support team was being mobilized and was expected to arrive within 24 to 36 hours.")],
    },
    # D18: quote GW-PUB-002 as issued
    "NWS-P014-04": {
        "dek": "The Coastal Bend Power and Water Authority has publicly acknowledged for the first time that failures at two substations are extending the recovery, and says the final 32,000 customers should be restored within 7 to 10 days.",
        "replace": [("Crews are on-site at two facilities to investigate protective relay conditions that are inconsistent with the mechanical damage caused by the storm. We are working to understand the full scope of these conditions and restore service as quickly and safely as possible.\"",
                     "Crews are on-site at two facilities to investigate protective relay conditions exacerbated by storm debris. We expect the final 32,000 affected customers in those areas to be restored within 7 to 10 days.\""),
                    ("The statement does not explain what specifically about the protective relay conditions is inconsistent with storm damage, nor does it describe what the crews found when they arrived.",
                     "The statement does not explain how debris affected the relays, nor does it describe what the crews found when they arrived."),
                    ("No new estimated restoration date has been given.", "The 7-to-10-day estimate is the first the authority has given for those customers.")],
    },
    # D19: PUB-181 gives no number, place or timing
    "NWS-P015-04": {
        "dek": "A joint FAA and CBP statement confirms that multiple incidents of unauthorized unmanned aircraft operations in the Corpus Christi area in the days before Hurricane Rafael are now under federal investigation.",
        "replace": [("confirming that two previously uncharacterized unmanned aircraft system sorties detected near Corpus Christi utility infrastructure in the period leading up to Hurricane Rafael are now under active federal investigation. The flights, which occurred between September 4 and September 11 — ten days to three days before Rafael's landfall — were retroactively identified during a systematic review of UAS tracking data conducted after the storm.",
                     "confirming that investigators have identified multiple incidents of unauthorized unmanned aircraft system operations in the Corpus Christi area in the period leading up to Hurricane Rafael. The agencies did not say how many flights were involved, where they took place or when; they asked anyone with information about drone activity in the area between September 4 and September 12 to contact the FBI."),
                    ("says the two sorties were identified during a counter-UAS assessment launched in connection with the security review that followed the storm period. \"During a systematic review of UAS track data for the pre-storm period, two sorties were identified that did not conform to expected recreational or commercial patterns,\" the statement reads. \"Both sorties are now under investigation by appropriate federal authorities. We are not in a position to characterize the nature or origin of the flights at this time.\"",
                     "says the aircraft operated without required FAA authorizations and were detected through a combination of radar and electronic sensor records. \"Due to the ongoing nature of the investigation, no additional details about the number, location, or timing of the incidents can be released at this time,\" the statement reads."),
                    ("Federal authorities have not publicly linked the drone sorties to any other aspect", "Federal authorities have not publicly linked the drone flights to any other aspect")],
    },
    # D20: PUB-213 names no firm and counts more than 300 complaints; the firm's name is public from D+90
    "NWS-P015-05": {
        "time_local": "16:00",
        "headline": "Texas DPS, AG's Office Warn of Storm Contractor Fraud After More Than 300 Complaints",
        "dek": "Unlicensed restoration contractors are charging Rafael survivors three to five times standard market rates for water extraction and mold remediation, according to Texas law enforcement, which is pursuing arrest warrants and civil investigative demands.",
        "replace": [("issued an urgent statewide warning Wednesday naming an unlicensed restoration contractor after receiving more than 128 complaints from Hurricane Rafael survivors who say the company charged between three and five times",
                     "issued an urgent statewide warning Wednesday after receiving more than 300 complaints from Hurricane Rafael survivors who say water damage contractors charged between three and five times"),
                    ("The company, identified as FastDry Coastal, holds no license with the Texas State Board of Plumbing Examiners or the Texas Department of Licensing and Regulation, officials said.",
                     "Many of the operators hold no license with the Texas State Board of Plumbing Examiners or the Texas Department of Licensing and Regulation, officials said. The warning does not name any company."),
                    ("\"FastDry Coastal has been named in 128 consumer complaints received since September 21,\"", "\"We have received more than 300 consumer complaints since the storm,\""),
                    ("to entities believed to be operating under the FastDry Coastal name", "to several entities named in the complaints"),
                    ("has obtained evidence that FastDry Coastal sales representatives have been approaching hurricane survivors at FEMA distribution sites and outside shelter facilities", "has obtained evidence that sales representatives have been approaching hurricane survivors at water distribution sites and outside shelter facilities"),
                    ("Investigators report that FastDry Coastal has used multiple telephone numbers", "Investigators report that one operation has used multiple telephone numbers")],
    },
    # D21: the operation name is not public until D+90
    "NWS-P030-08": {
        "headline": "Texas insurance commissioner launches Rafael fraud task force, coordinates with FBI and DPS",
        "dek": "Texas Department of Insurance Commissioner Rosa Vásquez activated the Insurance Fraud Task Force Thursday, citing coordinated claim fraud patterns that state and federal investigators are examining together.",
        "replace": [("that the FBI and Texas Department of Public Safety are jointly investigating under the name Operation Sandbar.", "that the FBI and Texas Department of Public Safety are jointly investigating."),
                    ("coordinating with FBI and Texas DPS on a coordinated fraud scheme investigation designated Operation Sandbar,\"", "coordinating with FBI and Texas DPS on a coordinated fraud scheme investigation,\""),
                    ("The agency did not describe the scope of Operation Sandbar or how many suspects", "The agency did not describe the scope of the investigation or how many suspects"),
                    ("The FBI and DPS did not comment Thursday on Operation Sandbar.", "The FBI and DPS did not comment Thursday.")],
    },
    # D22: pre-storm drone activity has been public since D+15; PUB-182 is a detection network, not interdiction
    "NWS-P032-05": {
        "dek": "The Port of Corpus Christi Authority and Coastal Bend Power and Water Authority announced a joint counter-drone detection program Saturday, acting on the federal finding, made public two weeks ago, of unauthorized drone activity in the area before Hurricane Rafael's landfall.",
        "replace": [("following retroactive identification of unauthorized drone activity in the pre-storm period. The announcement marks the first public disclosure that aerial surveillance of the facilities may have occurred before Hurricane Rafael made landfall on September 14.",
                     "following the federal finding, made public Sept. 29, of unauthorized drone activity in the area before the storm. It is the first step either agency has announced in response."),
                    ("They said the counter-UAS systems now deployed include detection, tracking, and — where legally permissible — interdiction capabilities.",
                     "They said the program will deploy a radio-frequency detection and direction-finding network at sites across the port and utility corridor, supplied by Sentinel Airspace Inc. and expected to be operational within 90 days."),
                    ("The joint program's reference to interdiction capabilities \"where legally permissible\" suggests coordination with federal partners who hold that authority. The agencies said the program was developed with guidance from the Department of Homeland Security, the FAA, and local law enforcement, but did not name which federal entity would hold legal authority for any active countermeasure.",
                     "The joint program is limited to detection: it can locate a drone and its operator but cannot bring an aircraft down. The agencies said the network will be operated in coordination with the FAA and CBP Air and Marine Operations."),
                    ("The FAA issued a temporary flight restriction over the port and CBPWA utility facilities in September; it is not clear whether that restriction is related to the counter-UAS program.",
                     "The FAA's temporary flight restriction over the area in September was the hurricane restriction and is unrelated to the new program.")],
    },
    # D23: on D+21 the news is the joint FEMA/CBPWA statement (PUB-205); the response team and declaration amendment are D+28 news
    "NWS-P021-05": {
        "time_local": "14:30",
        "headline": "FEMA, Corpus Christi Utility Say Outages Were Prolonged by Deliberate Interference With Control Systems",
        "dek": "In a joint statement, the federal disaster field office and the Coastal Bend Power and Water Authority say storm damage caused the initial blackouts but that interference with utility control systems kept some districts dark longer.",
        "body_all": [
            "CORPUS CHRISTI, Texas (Continental Wire) — The power outages that followed Hurricane Rafael lasted longer in parts of Corpus Christi than storm damage alone would have caused because of deliberate interference with utility control systems, the Federal Emergency Management Agency's Joint Field Office and the Coastal Bend Power and Water Authority said Tuesday in a joint statement. The statement came two hours after the FBI and the Cybersecurity and Infrastructure Security Agency announced a joint investigation into anomalous activity in industrial control systems at a coastal Texas electric utility.",
            "The statement draws a line between the storm and what came after. Wind and surge damage to the authority's transmission and distribution network caused the initial outages, it says; a technical review of the utility's operational data by federal investigators then determined that \"the duration of outages in certain districts was extended by deliberate interference with utility control systems beyond what storm damage alone would have caused.\" It does not say who was responsible, how the systems were reached or which districts were affected, and it says the investigation is continuing.",
            "\"Federal disaster response has not had to account for something like this alongside a major hurricane,\" said Continental Wire Service national security correspondent Noah Pemberton, who has covered domestic security for more than a decade. \"The immediate questions are practical ones: what it means for the customers still waiting for power, and what it means for the people who sat in the dark longer than the storm required.\"",
            "The authority said it has put enhanced security measures in place on its control systems and is working with federal partners to prevent further incidents. Power has been restored to most customers, the statement says; restoration in parts of northwest and central Corpus Christi is continuing while relay inspection and repair are completed. It says no decision has been made on whether residents who experienced prolonged outages will be eligible for additional disaster assistance.",
            "Both agencies asked anyone with information relevant to the investigation to contact the FBI's Corpus Christi Resident Agency. National Security Council spokesperson Adrian Wells confirmed Tuesday that the NSC is monitoring the situation and that the President has been briefed. The Senate Homeland Security and Governmental Affairs Committee and the House Energy and Commerce Committee indicated they intend to seek briefings on the federal response.",
        ],
    },
    # D24: deliberate interference has been official since D+21; the documents add the pre-storm timing
    "NWS-P045-10": {
        "replace": [("without electricity for more than 35 days following Hurricane Rafael", "without electricity for as long as 35 days following Hurricane Rafael"),
                    ("it would represent the first specific evidence that the manipulation of CBPWA's systems was deliberate and pre-planned rather than opportunistic — and that it was in place before the storm arrived. That framing would significantly alter the public narrative around the extended outages, which CBPWA and local officials characterized during the first weeks of recovery primarily as storm-damage restoration.",
                     "what it would add to the record is timing. Federal officials and CBPWA said on Oct. 5 that the outages were prolonged by deliberate interference with control systems; the documents indicate the changes were in place before the storm arrived, which would mean the interference was planned ahead of the hurricane rather than improvised after it.")],
    },
    # D25: PUB-146 (vote 4-1, RFP, 30 minutes); the county and its contractor handle translation (PUB-144)
    "NWS-P045-09": {
        "time_local": "16:30",
        "replace": [("KNCB broadcast the alert in Spanish based on its own translation before receiving official Spanish-language guidance, she testified, because the official translation did not reach the station until more than 12 hours after the English original. \"We made the decision to translate and broadcast because we could not wait,\" Fuentes-Vega told the court. \"The question for this commission is: why were we making that decision at all?\"",
                     "The official Spanish-language notice did not reach the station until 6:03 the next morning, she testified, 12 hours and 33 minutes after the English alert, and KNCB could not put an official notice on the air that it had not been sent. \"For twelve hours our hosts were telling callers we had nothing official in Spanish,\" Fuentes-Vega told the court. \"The question for this commission is: why were we in that position at all?\""),
                    ("Commissioners heard testimony from the Corpus Christi city emergency management office, which said the delay was attributable to translation workflow limitations and acknowledged it would evaluate its procedures.",
                     "Commissioners heard testimony from the Nueces County Office of Emergency Management, which said the delay was attributable to reduced staffing at its translation contractor and acknowledged it would evaluate its procedures."),
                    ("introduced a motion directing county staff to develop a simultaneous multilingual alert protocol within 60 days. The motion passed unanimously.",
                     "introduced a motion directing the Office of Emergency Management to issue a new request for proposals for language access services that requires every life-safety alert to be released in other languages within 30 minutes of the English text. The motion passed 4–1.")],
    },
    # D26: the lift notices carry no investigation line; the 1,820 total is first published on D+60
    "NWS-P042-04": {
        "replace": [("\"Water pressure across all Zone 4 test points has been confirmed above 40 psi.", "\"Water pressure at all test points in the two districts has been confirmed above 40 psi."),
                    (" The notice adds: \"The department notes that the federal investigation into the pressure anomalies that led to this advisory remains ongoing.\"", " Officials added at a briefing that their own review of the pressure drops that led to the notice is not finished."),
                    ("The caveat about the ongoing investigation is unusual in a boil-water lift notice, which typically signals a clean administrative close. City water officials said Tuesday that they are lifting the advisory because current water quality and pressure metrics meet all state and federal standards for safe use — but that the federal investigation into the unauthorized SCADA access and associated pressure irregularities is a separate process that the city is not in a position to close. That investigation, being conducted by the FBI, CISA, and other federal partners, remains open with no public timeline.",
                     "The caveat is unusual at the lifting of a boil-water notice, which typically signals a clean administrative close. City water officials said Tuesday that they are lifting the notice because current water quality and pressure meet all state and federal standards for safe use — but that some of the pressure readings recorded in late September are not fully explained by the storm damage found so far, and that the review of those records continues. They declined to say more."),
                    ("resulted in 1,820 documented cases. Dr. Reyes said the case count has plateaued and that the outbreak is considered resolved.", "sent hundreds of people to hospital. Dr. Reyes said new cases have stopped and that the outbreak is considered resolved; a final count has not been published.")],
    },
    "NWS-P042-05": {
        "replace": [("en todos los puntos de prueba de la Zona 4", "en todos los puntos de prueba de los dos distritos"),
                    ("El aviso también indica que la investigación federal sobre las anomalías de presión que llevaron al aviso original sigue en curso.", "Funcionarios dijeron que continúa la revisión de las caídas de presión que llevaron al aviso original."),
                    ("afectó a 1,820 personas según el informe preliminar del Departamento de Salud del Estado de Texas del 7 de octubre.", "envió a cientos de personas al hospital; el informe preliminar del Departamento de Salud del Estado de Texas del 7 de octubre confirmó que la causa fue agua contaminada. Todavía no se ha publicado una cifra final.")],
    },
    # D27: FBI Houston Division everywhere
    "NWS-P003-08": {"replace": [("the FBI San Antonio Division", "the FBI Houston Division")]},
    # D31 / D44
    "NWS-P003-07": {
        "time_local": "10:30",
        "headline": "911 center releases dispatch logs: 1,100 rescue calls on landfall day",
        "replace": [("representing the most concentrated single-day rescue dispatch load in the agency's history", "a rescue dispatch load that the center said was exceeded only by Thursday's")],
    },
    # D32: one version of the aerial program (PUB-113): Sept. 12 to Oct. 29, public downsampled imagery on OpenData
    "NWS-P045-07": {
        "time_local": "14:30",
        "headline": "FEMA closes out aerial damage survey of Corpus Christi metro after 6.2 million image tiles",
        "dek": "FEMA Region 6 announced Friday that its aerial assessment program for Hurricane Rafael has concluded, with 183 square kilometers of the Corpus Christi metropolitan area photographed and catalogued — and part of the imagery now open to the public.",
        "replace": [("confirming that 100 percent of the Corpus Christi metropolitan area has been covered by post-storm aerial imaging. The program, which ran for 45 days beginning the morning after Rafael's landfall, generated imagery of the full city,",
                     "which generated more than 6.2 million georeferenced image tiles covering 183 square kilometers of the Corpus Christi metropolitan area. The program, which ran from a pre-storm baseline on Sept. 12 through Oct. 29, generated imagery of the city"),
                    ("\"FEMA Region 6 has completed the Hurricane Rafael Aerial Assessment Program. One hundred percent of the Corpus Christi metropolitan area has been covered,\" the agency said in a statement. \"Imagery has been archived with the National Geospatial-Intelligence Agency for long-term infrastructure resilience research.\" FEMA said the archive will be available to researchers, planners, and infrastructure agencies under applicable data-sharing agreements, and that some imagery will be accessible to local governments for recovery planning purposes.",
                     "\"This imagery archive is a resource that will support not just today's recovery, but future preparedness for the entire Texas Gulf Coast,\" FEMA Federal Coordinating Officer Dennis Park said in a statement. FEMA said downsampled imagery from the first two survey phases is available from Friday through its OpenData portal for researchers, local governments and community organizations, and that requests for full-resolution imagery go through its regional geospatial office."),
                    ("The NGA archive commitment is an indication that federal planners view Rafael", "The decision to keep and publish the archive is an indication that federal planners view Rafael"),
                    ("were used in the 45-day program or what the total cost was. A spokeswoman said the program used both manned and uncrewed platforms and that the data quality met all NGA archival standards.",
                     "were used in the program or what the total cost was. A spokeswoman said the program used federal, state and contracted aircraft, both manned and uncrewed.")],
    },
    # D35: one spill, the Inner Harbor release of Sept. 14
    "NWS-P002-10": {
        "replace": [("or the confirmed discharge in the ship channel", "or the oil released in the Inner Harbor during the storm"),
                    ("\"We want to be very clear: tap water in the service area is currently safe to drink,\" Gallegos said. \"We are not issuing a boil water notice. We are activating additional treatment steps as a precaution while we determine the extent and source of the raw water contamination.\"",
                     "\"We want to be very clear: treated water leaving the plant meets the standards for hydrocarbons,\" Gallegos said. \"This detection does not change the conservation request already in place because of low pressure. We are activating additional treatment steps as a precaution while we determine the extent and source of the raw water contamination.\""),
                    ("are connected to the ship channel oil discharge confirmed by the Coast Guard earlier Thursday", "are connected to the Inner Harbor oil spill of Sept. 14")],
    },
    "NWS-P002-11": {
        "dek": "TCEQ and EPA have issued a health advisory for areas within two miles of the Corpus Christi ship channel after the air quality index rose to 134, driven by hydrocarbon vapors from the Inner Harbor oil spill.",
        "replace": [("driven by hydrocarbon vapors from the oil discharge confirmed in Corpus Christi Bay earlier in the day", "driven by hydrocarbon vapors from the oil spilled in the Inner Harbor on Sept. 14 and since carried into the bays"),
                    ("readings at some fixed monitoring points near the La Quinta Channel briefly exceeded 150 AQI", "readings at some fixed monitoring points in the Hillcrest area briefly exceeded 150 AQI")],
    },
    # D39: canon official and fictional terminals
    "NWS-M002-08": {
        "replace": [("had been working cargo at the La Quinta Terminal Complex and the bulk facilities along the Inner Harbor", "had been working cargo at the La Quinta Channel berths and the bulk facilities along the Inner Harbor"),
                    ("Port of Corpus Christi Authority chief of operations Rolando Espinosa confirmed", "Port of Corpus Christi Authority Director of Operations Julio Sandoval-Reeves confirmed"),
                    ("Petroleum product loading operations at the Taft Docks were halted", "Petroleum product loading operations at the Inner Harbor oil docks were halted"),
                    ("which handles LNG exports from the Ingleside facilities, was placed on reduced operations", "which handles LNG and bulk cargo on the north side of the bay, was placed on reduced operations")],
    },
    # D46
    "NWS-P040-01": {"replace": [("On the first Sunday in five weeks that Corpus Christi didn't have to boil its tap water,", "On the first Sunday in five weeks that most of Corpus Christi didn't have to boil its tap water,")]},
    "NWS-P041-02": {"replace": [("The city lifted its boil-water notice Saturday after 35 days.", "The city lifted its citywide boil-water notice Saturday after 35 days; Districts 3 and 4 remain under their separate notice.")]},
    # D43 / D54
    "NWS-P013-03": {
        "replace": [("from the city's public information office until 6:00 a.m. CDT on September 27", "until 6:03 a.m. CDT on September 27"),
                    (" KNCB aired emergency public service announcements throughout the evening based on the English-language notice, but the news director emphasized that an unofficial translation is not the same as an authorized government advisory.",
                     " KNCB could not put an official notice on the air that it had not been sent, the news director said, and an unofficial translation is not the same as an authorized government advisory."),
                    ("The delay traces in part to how the city processes multilingual emergency communications. Corpus Christi uses a language access system that routes official advisories first through English-language channels. Translation and re-broadcasting in Spanish and other languages occurs in a secondary processing step that, according to city communications protocols, can add up to twelve hours under normal workloads. City spokeswoman Delia Sandoval acknowledged the gap Monday but said the system \"performed within its defined parameters\" — a response that advocates say reveals the inadequacy of those parameters.",
                     "The delay traces to how multilingual emergency communications are handled. Official notices go out first in English; translation into Spanish and other languages is done by a county contractor, Nueces County Language Access Services, in a second step. Nueces County Office of Emergency Management spokesperson Cassandra Trejo-Morales confirmed the delay Monday and attributed it to reduced staffing at the contractor. \"We are reviewing what happened and what can be done differently,\" she said — a response that advocates say does not answer why a life-safety notice could wait overnight."),
                    ("have written to the city demanding an immediate review of its emergency language access protocols", "have written to the county demanding an immediate review of its emergency language access protocols"),
                    ("The city has not indicated whether it will conduct a formal after-action review", "The county has not indicated whether it will conduct a formal after-action review")],
    },
    # D30: PUB-132 and PUB-204 as issued
    "NWS-P012-05": {
        "time_local": "19:30",
        "headline": "County Opens NuecesInfoLine as Water Safety Calls Flood 911",
        "dek": "A mounting wave of water-safety inquiries after Sunday's boil-water notice has prompted the 911 center to open the NuecesInfoLine and urge residents to reserve 911 for genuine emergencies.",
        "body": {
            0: "The Coastal Bend Emergency Communications Center opened a new non-emergency information line, the NuecesInfoLine, Sunday evening to handle a mounting wave of calls about water safety, as the center reported a sharp increase in 911 contacts from residents seeking guidance rather than emergency assistance after the boil-water notice for Districts 3 and 4. The surge placed measurable stress on the 911 center's available lines during peak hours.",
            2: "The NuecesInfoLine, reached at 361-826-INFO, is staffed 24 hours a day with operators briefed on the boil-water notices, water distribution sites and when service is expected to be restored; callers can press 2 for Spanish. \"911 is for life-threatening emergencies only,\" CBECC Director Patricia Escamilla-Voss said. \"Please use that number and keep 911 available for people whose lives are in danger.\" City spokeswoman Delia Sandoval said water distribution sites are open at the Tuloso-Midway High School gym, the Woodlawn Community Center and Cefe Valenzuela Park.",
            3: "CBECC staffing levels, which were stretched thin during Rafael's initial days when call volume hit record highs, are still supported by mutual-aid dispatchers from San Patricio and Bee counties, who have been in place since landfall. Vasquez-Okafor said the center's own capacity has stabilized even as the informational demand from the public remains high.",
        },
        "replace": [("climbed significantly from September 20 through today", "climbed sharply after the alert went out at 5:30 p.m."),
                    ("\"We want people to know that 311 and NuecesInfoLine are there for information questions,\"", "\"We want people to know that the NuecesInfoLine is there for information questions,\"")],
    },
    "NWS-P012-07": {
        "replace": [("reached millions of devices across the region Sunday evening", "reached phones, televisions and radios across the region Sunday evening"),
                    ("The Emergency Alert System broadcast read: \"THE COASTAL BEND POWER AND WATER AUTHORITY HAS ISSUED A BOIL WATER NOTICE FOR DISTRICTS 3 AND 4 EFFECTIVE IMMEDIATELY. ALL RESIDENTS AND BUSINESSES IN THE ZONE 4 DISTRIBUTION AREA MUST BOIL WATER FOR AT LEAST ONE MINUTE BEFORE DRINKING OR COOKING. THIS NOTICE IS IN EFFECT UNTIL FURTHER NOTICE.\"",
                     "The Emergency Alert System broadcast read in part: \"THE COASTAL BEND POWER AND WATER AUTHORITY HAS ISSUED A BOIL WATER NOTICE FOR DISTRICTS 3 AND 4 OF THE CORPUS CHRISTI WATER DISTRIBUTION SYSTEM. THIS NOTICE AFFECTS APPROXIMATELY 48,000 RESIDENTS. DUE TO LOW WATER PRESSURE AND DISTRIBUTION SYSTEM DISRUPTIONS, ALL TAP WATER MUST BE BOILED BEFORE USE FOR DRINKING, COOKING, MAKING ICE, OR BRUSHING TEETH.\""),
                    ("generating a flood of calls to 311 and NuecesInfoLine that pushed both systems to capacity within minutes of broadcast", "generating a flood of calls to 311 and 911 within minutes of broadcast"),
                    ("generating a flood of calls to city information lines", "generating a flood of calls to 311 and 911"),
                    ("businesses within Zone 4 must comply", "businesses within the two districts must comply"),
                    ("confirms the Zone 4 system is safe", "confirms the system in the two districts is safe"),
                    ("Residents with questions can reach NuecesInfoLine at 311 or (361) 826-2489.", "Residents with questions can call 311; the county said a dedicated information line would open later Sunday evening.")],
    },
    "NWS-P000-13": {"replace": [("just after 12:30 a.m. Tuesday", "at 12:45 a.m. Tuesday"),
                                ("The alert, broadcast in both English and Spanish, instructed", "The alert, in English with a short Spanish summary, instructed")]},
    "NWS-P015-03": {"replace": [("between September 23 and September 28", "between September 23 and September 26"),
                                ("shows \"breaker positions inconsistent with expected post-storm failure modes\"", "— Harbor View and Crosstown — shows \"breaker positions inconsistent with expected post-storm failure modes\""),
                                ("imagery of two substations — identified by transmission corridor designation rather than by name — ", "imagery of two substations ")]},
    "NWS-P035-04": {"replace": [("the authority said in an early-morning statement", "the authority said in a statement Tuesday afternoon")]},
    "NWS-P028-04": {"replace": [("a relatively new federal posture under the Biden-era Infrastructure Investment and Jobs Act, which expanded", "a relatively new federal posture under the Infrastructure Investment and Jobs Act, which expanded")]},
    "NWS-P029-05": {"replace": [("serving more than 300,000 people", "serving roughly 500,000 people")]},
    "NWS-P000-12": {"replace": [("South Texas Blood Bank", "Nueces Bay Blood Services")]},
    "NWS-P045-60": {"replace": [("más de 55,000 llamadas", "más de 56,000 llamadas")]},
    # D45: on the morning of D+1 the figure is a rate, not a day total
    "NWS-P001-10": {"replace": [("Las llamadas al 9-1-1 llegaron a cerca de 2,900 en un día, casi diez veces lo normal,", "Las llamadas al 9-1-1 están llegando a un ritmo de cerca de 2,900 al día, casi diez veces lo normal,"),
                                ("and 911 calls peaked near 2,900 a day, most from", "and 911 calls are running at a rate near 2,900 a day, most from")]},
    "NWS-P001-02": {"replace": [("the Corpus Christi–Nueces County 911 center was taking calls", "the Coastal Bend Emergency Communications Center was taking calls")]},
}

FACTS = {
    "PUB-026": {"statement": "911 call volume is running at a rate of about 2,900 calls a day, nearly ten times normal; most calls come from low-lying neighborhoods near the bay."},
    # D16
    "PUB-134": {"replace": [("The NuecesInfoLine will remain active through the duration of the boil water notice. CBECC thanks the residents of Districts 3 and 4 for their patience during the extended water advisory.",
                             "The NuecesInfoLine, opened during the boil-water notices, will close on Friday, November 5. CBECC thanks the residents of Districts 3 and 4 for their patience during the extended water notices.")]},
    # D29
    "PUB-170": {"replace": [("have conducted rescue operations continuously since 06:22 this morning, completing 180 hoist operations as of 15:00", "have conducted rescue operations continuously since 1:22 a.m. Tuesday, completing 180 hoist operations as of 3 p.m. Wednesday")]},
    # D40
    "PUB-171": {"replace": [("Corpus Christi Fire Department Dispatch Chief Elena Vasquez-Okafor", "Coastal Bend Emergency Communications Center Dispatch Chief Elena Vasquez-Okafor")]},
    "PUB-172": {"replace": [("CCFD Dispatch Chief Elena Vasquez-Okafor", "Coastal Bend Emergency Communications Center Dispatch Chief Elena Vasquez-Okafor"),
                            ("Two fatalities were recovered, both occupants of a submerged vehicle on Violet Road.", "Search teams recovered two bodies during the operation, both occupants of a submerged vehicle on Violet Road; the county's confirmed storm death toll stands at 23.")]},
    # D27
    "PUB-210": {"replace": [("The Federal Bureau of Investigation San Antonio Division", "The Federal Bureau of Investigation Houston Division")]},
    # D41
    "PUB-200": {"replace": [("LANDFALL NEAR CORPUS CHRISTI TEXAS", "LANDFALL NEAR PORT ARANSAS TEXAS"),
                            ("STORM SURGE OF 9 TO 13 FEET", "STORM SURGE OF 9 TO 12 FEET"),
                            ("RESIDENTS IN EVACUATION ZONES A THROUGH D SHOULD PREPARE TO EVACUATE.", "EVACUATION ZONE A IS UNDER A MANDATORY EVACUATION ORDER. RESIDENTS IN ZONES B AND C SHOULD PREPARE TO EVACUATE."),
                            ("EVACUATE zones A-D or shelter.", "Zone A EVACUATE; B-C prepare.")]},
    # D35
    "PUB-190": {"replace": [("reports that treated drinking water quality is not affected and water supply remains uninterrupted", "reports that treated drinking water continues to meet the standards for hydrocarbons; the low system pressure reported since the storm is unrelated to this detection")]},
    "PUB-195": {"replace": [("The O.N. Stevens Water Treatment Plant water quality has remained within all regulatory parameters for 52 consecutive days.", "Raw-water intake readings at the O.N. Stevens Water Treatment Plant have remained below the hydrocarbon alert threshold for 52 consecutive days.")]},
    # D42: no "Zone 4" in public text; one boundary; one site list; one boil time (two minutes)
    "PUB-143": {"replace": [("(generally bounded by Leopard Street to the north, Highway 286 to the east, Agnes Street to the south, and Staples Street to the west)", "(ZIP codes 78401, 78405, 78407, 78408, 78416 and 78417)"),
                            ("bring water to a rolling boil for at least one full minute before use", "bring water to a rolling boil for two minutes before use")]},
    "PUB-204": {"replace": [("BRING WATER TO A ROLLING BOIL FOR AT LEAST ONE MINUTE BEFORE USE.", "BRING WATER TO A ROLLING BOIL FOR TWO MINUTES BEFORE USE.")]},
    "GW-PUB-001": {"replace": [("Low water pressure in the Zone 4 distribution system", "Low water pressure in the distribution system serving the two districts"),
                               ("rolling boil for one minute before drinking or cooking", "rolling boil for two minutes before drinking or cooking")]},
    "GW-PUB-007": {"replace": [("Water pressure across all Zone 4 test points", "Water pressure at all test points in the two districts")]},
    "PUB-132": {"replace": [("Water distribution sites are open at Cunningham Middle School, Brownie's Corner Community Center, and Calallen High School;", "Water distribution sites are open at the Tuloso-Midway High School gym, the Woodlawn Community Center, and Cefe Valenzuela Park;")]},
    # D47
    "PUB-161": {"replace": [("the South Texas Blood and Tissue Center is accepting donations at their Ayers Street location", "the Nueces Bay Blood Services is accepting donations at its Ayers Street location")]},
    # D48
    "PUB-206": {"replace": [("LA AUTORIDAD DE AGUA Y ENERGIA DE LA COSTA DEL GOLFO", "LA AUTORIDAD DE ENERGIA Y AGUA DEL COASTAL BEND")]},
    # D49
    "PUB-164": {"replace": [("treated 4,217 hurricane-related patients over the 30-day response period", "treated 4,217 hurricane-related patients over that period")]},
    # D51
    "PUB-205": {"replace": [("Residents in Districts 1 through 5 who experienced prolonged outages may be eligible for additional disaster assistance.", "No decision has been made on whether residents who experienced prolonged outages will be eligible for additional disaster assistance.")]},
    # D32
    "PUB-113": {"replace": [("Over 45 days beginning September 12 and concluding October 29", "From a pre-storm baseline on September 12 through October 29")]},
}

EVENTS = {
    # D36
    "EVT-1403": {"replace": [("shelter-in-place guidance for Zones C–E residents who have not evacuated", "shelter-in-place guidance for residents of Zones D and E and for anyone in Zones A to C who has not been able to leave"),
                             (" and omits the curfew time of 22:00 CDT", "")]},
    # D40
    "EVT-1701": {"replace": [("CCFD SAR coordinator Dispatch Chief Elena Vasquez-Okafor", "Coastal Bend Emergency Communications Center Dispatch Chief Elena Vasquez-Okafor, the county's SAR coordinator,")]},
    # D50
    "EVT-1103": {"replace": [("districts 1 through 6", "districts 1 through 5")]},
    "EVT-1602": {"replace": [("as the McKinley Substation (T8 target) fails", "as the McKinley Substation (GW-FAC-DSS-01, the distribution substation feeding the hospital; storm damage, not one of the five manipulated transmission substations) fails")]},
    "GW-EVT-011": {"replace": [("across the D-7 to D+16 window", "across the D-7 to D+18 window")]},
    # D43: the notice reaches KNCB at 06:03 and is aired at once
    "EVT-2106": {"replace": [("is not delivered to KNCB until 05:58 local the next morning; KNCB airs it at 06:03 local on D+13", "is not delivered to KNCB until 06:03 local the next morning; KNCB airs it at once, at 06:03 local on D+13"),
                             ("translation received from the county at 05:58 local", "translation received from the county at 06:03 local")]},
    "EVT-1407": {"replace": [("KNCB receives the boil-water notice text via email from OEM at 06:00 CDT D+13 and airs it at 06:03 CDT", "KNCB receives the boil-water notice text from OEM at 06:03 CDT D+13 and airs it at once")]},
    # D32
    "EVT-1108": {"replace": [("completes the 180-day assessment commitment", "completes the assessment programme (September 12 to October 29)")]},
    # D37
    "EVT-2205": {"replace": [("DR-4890", "DR-4821")]},
}

FILES = [
    # D27, D37, D38: design leftovers
    ("_thread_designs/t22_fraud_design.json", "San Antonio Division", "Houston Division"),
    ("_thread_designs/t22_fraud_design.json", "DR-4890", "DR-4821"),
    ("_thread_designs/t22_fraud_design.json", "142,000 claims filed, $3.8B in insured losses", "about 187,000 claims filed, $2.1 billion in insured losses"),
    ("_thread_designs/t16_hospital_design.json", "consistent with 24-hour behavioral lag from notification delay", "consistent with the behavioral lag from the 12-hour 33-minute notification delay"),
    ("_thread_designs/t16_hospital_design.json", "explained by the 24-hour notification lag", "explained by the 12-hour 33-minute notification lag"),
    ("_thread_designs/t11_aerial_design.json", "districts 1 through 6", "districts 1 through 5"),
]
