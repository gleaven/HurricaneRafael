"""Independent narrative audit 2026-11-10, blockers D01-D15 (07_validation/independent_audit_narrative)."""

STORIES = {
    # D01: Individual Assistance approved D+57 (Wed Nov. 10); registration opens D+60 (Sat Nov. 13)
    "NWS-P057-03": {
        "headline": "FEMA Grants Individual Assistance to Storm-Battered Counties; Registration Opens Saturday",
        "dek": "Federal aid authorization unlocks rental assistance, home repair grants, and personal property replacement for residents of Nueces, San Patricio, and Aransas counties — 57 days after Rafael made landfall.",
        "body": {
            0: "FEMA has approved Individual Assistance for Nueces, San Patricio, and Aransas counties, the agency announced Wednesday, authorizing direct financial aid for eligible Hurricane Rafael survivors eight weeks after the storm struck. The approval, long awaited by tens of thousands of displaced and damaged households, does not open the application line at once: registration begins Saturday, Nov. 13, through FEMA's disaster hotline, its online portal and local recovery centers.",
            1: "Beginning Saturday, eligible residents can apply by calling 1-800-621-FEMA or visiting DisasterAssistance.gov. The approved programs include rental assistance for displaced households, grants for essential home repairs, and personal property replacement funds for lost or destroyed belongings. FEMA said it will open three Disaster Recovery Centers in Corpus Christi the same morning: at the Oveal Williams Senior Center at 1414 Martin Luther King Drive, a facility at 5301 Ayers Street, and Memorial Coliseum Annex at 902 N. Shoreline Blvd. All three sites will operate Monday through Saturday, 8 a.m. to 6 p.m. Residents will not need an appointment.",
            2: "The 57-day interval between landfall and approval is longer than is typical for major hurricane declarations. FEMA officials attributed the delay partly to the pace of household damage assessments: access limits around the oil spill zone, flooded roads and the extended power outage — parts of Corpus Christi's grid remained impaired into mid-October — hampered field teams' ability to reach and assess damaged properties, particularly in Districts 3 and 4. The state formally asked for Individual Assistance on Oct. 9. 'The prolonged outage created verification challenges we do not normally encounter to this degree,' said FEMA Region 6 external affairs officer Rachel Ostrander. 'Our teams could not safely or accurately assess many properties without stable utilities in those neighborhoods.'",
        },
        "replace": [("since Day 2 of the storm", "since the second day after the storm"),
                    ("FEMA urges all eligible survivors to apply as soon as possible to preserve eligibility.", "FEMA urges all eligible survivors to apply as soon as registration opens Saturday."),
                    ("'Don't wait.'", "'Don't wait once the line opens.'")],
    },
    # D02
    "NWS-P057-04": {
        "headline": "Eight Weeks On, Federal Aid Is Approved — But For Many Corpus Christi Families, the Wait Already Cost Them",
        "dek": "FEMA's Individual Assistance approval brings relief to hurricane survivors Wednesday, but advocates say the 57-day gap has left lasting financial damage — particularly for renters and Spanish-speaking households who had the fewest safety nets.",
        "body": {
            0: "By 8 a.m. Wednesday, a line had already formed outside the Oveal Williams Senior Center on Martin Luther King Drive, where FEMA plans to open one of its three Disaster Recovery Centers on Saturday. Word had spread that federal help was finally coming, and people came to ask when. Many of those waiting had been displaced from Districts 3 and 4, the neighborhoods hardest hit by Hurricane Rafael's storm surge and by the power outages that followed. Some carried folders stuffed with photographs, utility bills, and lease agreements — documents they had been told to gather weeks ago, in anticipation of the federal aid that was approved Wednesday.",
            1: "FEMA's approval of Individual Assistance for Nueces, San Patricio, and Aransas counties unlocks rental assistance, home repair grants, and personal property replacement for eligible storm survivors. Registration opens Saturday, Nov. 13, at DisasterAssistance.gov, by phone at 1-800-621-FEMA and at the recovery centers. But for many families, the 57-day interval between Rafael's landfall and the approval has already meant missed rent payments, maxed credit cards, and decisions to move in with relatives across the state — or to leave altogether.",
        },
        "replace": [("But you can't hold on for six weeks when", "But you can't hold on for eight weeks when"),
                    ("did not reach 80 percent restoration until Day 28.", "did not reach 80 percent restoration until mid-October."),
                    ("The FEMA declaration does not remediate the gap, but advocates say the opening of three local recovery centers", "The approval does not remediate the gap, but advocates say the three local recovery centers opening Saturday"),
                    ("She said she planned to visit the Ayers Street center first thing Thursday morning.", "She said she planned to be at the center on Martin Luther King Drive when it opens Saturday morning.")],
    },
    # D03: no FEMA household registration before D+60
    "NWS-P025-04": {
        "body": {
            1: "FEMA and state teams are carrying out joint damage assessments in Corpus Christi, but officials acknowledged this week that the work has fallen behind the scale of the damage. Households cannot yet apply for federal aid: the disaster declaration so far covers debris removal and emergency work, and the state has now formally asked FEMA to add Individual Assistance. Texas Department of Insurance data shows that claims filings from the Coastal Bend are arriving at a rate consistent with what actuaries are projecting as the second-largest coastal storm insurance event in Texas history since Hurricane Harvey in 2017.",
            3: "The delay creates compounding problems for homeowners navigating insurance claims while they wait to learn whether federal household aid will be approved. Residents say they are receiving conflicting guidance about which paperwork to gather first, and advocates at the city's recovery assistance hubs say the documentation requirements have overwhelmed elderly residents and those without reliable internet access.",
        },
    },
    # D04
    "NWS-P090-05": {"replace": [("the 43-day delay in FEMA IA approval", "the 57-day wait for FEMA Individual Assistance"),
                                ("said a Calallen-area resident who said", "said a Westside resident who said")]},
    "NWS-P090-06": {"replace": [("187 fraudulent insurance claims between Rafael's landfall and Day 50.", "187 fraudulent insurance claims in the weeks after the storm; the aid applications were filed in the first days after registration opened Nov. 13."),
                                ("where the FEMA Individual Assistance approval was delayed 43 days and genuine need was highest", "where FEMA Individual Assistance was not approved until 57 days after landfall and genuine need was highest")]},
    "NWS-P090-07": {"replace": [("the 43-day wait for FEMA Individual Assistance", "the 57-day wait for FEMA Individual Assistance")]},
    # D05: the utility is CBPWA; add the deaths and curfew PUB-203 carries; D44 timing
    "NWS-P001-09": {
        "time_local": "09:20",
        "replace": [("according to data from the state utility reporting network", "according to the Coastal Bend Power and Water Authority"),
                    ("AEP Texas crews are staged outside the affected areas and will begin damage assessment and restoration work as soon as access conditions allow, expected to take several hours more in areas where water has not yet fully receded.",
                     "Authority crews are staged outside the affected areas and will begin damage assessment and restoration work as soon as access conditions allow. Nueces County Emergency Management has confirmed twelve deaths as of 9 a.m. and cautions the number may rise. A dusk-to-dawn curfew is in effect inside the Corpus Christi city limits.")],
    },
    # D06
    "NWS-P119-03": {
        "replace": [("As of this week, 97 percent of homes in the affected area have had power restored.", "Power has been back on for every customer since Oct. 19."),
                    ("Corpus Christi Bay has been declared clean; of the 340 oiled birds", "Part of the bay's fishing grounds reopened last week after testing; of the 340 oiled birds"),
                    ("The 24-hour gap in bilingual emergency alerts", "The 12-hour gap in bilingual emergency alerts"),
                    ("Nueces County adopted a simultaneous multilingual alert protocol in November, requiring all public emergency notices to be transmitted concurrently in English, Spanish, and Vietnamese.",
                     "Nueces County commissioners voted in October to require that Spanish-language versions of emergency notices be released within 30 minutes of the English text."),
                    ("Operation Sandbar brought 14 convictions and $4.7 million in restitution ordered in the disaster-fraud case that targeted Districts 3 and 4.",
                     "Operation Sandbar brought 14 arrests in December in the disaster-fraud case that targeted Districts 3 and 4; the case is pending in federal court."),
                    ("publicly acknowledged in the weeks after the storm, with federal authorities describing it as the work of a sophisticated threat actor with possible foreign-state ties — remains open.",
                     "publicly acknowledged in the weeks after the storm — remains open, and no attribution for it has been made public."),
                    ("The Corpus Christi Bay Port and Water Authority has implemented", "The Coastal Bend Power and Water Authority has implemented"),
                    ("a Calallen homeowner who declined to give her name", "a homeowner who declined to give her name")],
    },
    # D07: the citywide notice has been in force since Sept. 18; no "Zone 4" in public text
    "NWS-P012-06": {
        "dek": "Approximately 48,000 Corpus Christi residents in Districts 3 and 4 are under a new boil water notice, effective immediately, after the utility reported low pressure in the two districts; the citywide notice issued Sept. 18 also remains in force.",
        "body": {
            0: "The Coastal Bend Power and Water Authority and the City of Corpus Christi issued an emergency boil water notice for water Districts 3 and 4 effective immediately at 5:30 p.m. Sunday, instructing approximately 48,000 residents and all businesses in the two districts to boil tap water before using it for drinking, cooking, making ice, or brushing teeth. The notice comes on top of the citywide boil-water notice in force since Sept. 18 and is the most significant water quality action in the city since Hurricane Dolly in 2008.",
            1: "Water Services Director James Thornton said the notice was issued as a precautionary measure after low system pressure was recorded in the two districts, which he attributed to hurricane damage to distribution and pumping infrastructure. \"We identified storm-related damage to treatment and pumping infrastructure that may have caused pressure fluctuations in these districts,\" Thornton said. \"Until we can verify that distribution integrity has been maintained throughout, the boil water notice protects public health.\" He said engineers are on-site conducting assessments and that the department is working as quickly and safely as possible.",
            2: "Districts 3 and 4 take in downtown, Hillcrest and the Northside, and the Westside neighborhoods including Molina, in ZIP codes 78401, 78405, 78407, 78408, 78416 and 78417. The rest of the city remains under the citywide notice issued Sept. 18; the new notice adds a separate low-pressure warning for the two districts and will be lifted on its own schedule. Restaurants and food service businesses within the two districts must comply immediately: they must use pre-boiled water or obtain bottled water from approved suppliers, and many are expected to close temporarily.",
            3: "Under state rules, the boil water notice triggers required testing protocols. The utility must collect water samples from multiple points in the affected distribution system and receive laboratory results confirming that bacteria counts are within safe limits before the notice can be lifted. Thornton declined to estimate how long that process might take, citing the ongoing complexity of post-storm infrastructure assessments. Residents in Districts 3 and 4 who cannot boil water due to lack of power or other circumstances may obtain bottled water at distribution sites at the Tuloso-Midway High School gym, the Woodlawn Community Center and Cefe Valenzuela Park.",
        },
    },
    # D08: Districts 3/4 notice began Sept. 26 (28th day on Oct. 24); operation name not public until D+90
    "NWS-P040-04": {
        "replace": [("noting that Operation Sandbar — the FBI and TDI joint fraud investigation announced Oct. 14 — is ongoing.", "noting that the joint fraud investigation by the FBI, the Department of Public Safety and the Texas Department of Insurance announced Oct. 14 is ongoing."),
                    ("the AG's advisory arrived on a day when the boil-water notice remained in its 40th day. City officials offered no updated timeline Sunday for lifting the advisory, saying only that testing and pressure normalization in Zone 4 is continuing.",
                     "the AG's advisory arrived on the 28th day of their separate boil-water notice, a day after the citywide notice was lifted. City officials offered no updated timeline Sunday for lifting it, saying only that testing and pressure normalization in the two districts is continuing.")],
    },
    # D09: PUB-164 figures
    "NWS-P060-04": {
        "dek": "A joint after-action analysis from Shoreline Regional and Bay City Medical centers documents 4,217 hurricane-related patients, a preventable 12-hour bilingual notification gap, and systemic failures that amplified suffering among the region's most vulnerable residents.",
        "replace": [("the product of a four-month internal review, traces nearly 5,000 patient encounters directly to the storm", "the product of a two-month internal review, traces more than 4,200 patients directly to the storm"),
                    ("The two hospitals recorded 4,847 total Rafael-related patient encounters between landfall and Day 60. Among those, 1,820 confirmed gastroenteritis cases were documented between Day 15 and Day 32",
                     "The two hospitals treated 4,217 hurricane-related patients between Sept. 11 and Oct. 14. Among those, 1,820 patients were treated for Cryptosporidium and Giardia infection between Sept. 29 and Oct. 12"),
                    ("the documented 24-hour delay in bilingual alert distribution by area emergency broadcasters in the first hours after the boil-water notice was issued", "the documented delay of more than 12 hours before the Spanish-language version of the boil-water notice was distributed"),
                    ("until approximately 24 hours after English-language outlets were notified", "until more than 12 hours after English-language outlets were notified"),
                    ("a near-catastrophic hospital generator diesel shortage on Day 5", "a near-catastrophic hospital generator diesel shortage five days after landfall"),
                    ("on the afternoon of Day 5", "that afternoon")],
    },
    # D10: hoist and rescue counts follow PUB-170/173; first launch 1:22 a.m. Tuesday
    "NWS-P001-08": {
        "time_local": "16:00",
        "headline": "Coast Guard Jayhawks fly 180 hoists over Flour Bluff and North Beach as thermal imaging cuts through debris field",
        "dek": "HH-60 Jayhawk helicopter crews from Air Station Corpus Christi have completed 180 hoist operations since launching early Tuesday, with thermal imaging cameras credited for locating survivors hidden beneath debris in flooded neighborhoods.",
        "replace": [("have conducted more than 47 rooftop rescues in Flour Bluff and surrounding low-lying neighborhoods since first light Wednesday, working in improving but still challenging conditions",
                     "have completed 180 hoist operations in Flour Bluff, North Beach and surrounding low-lying neighborhoods since launching at 1:22 a.m. Tuesday, working in improving but still challenging conditions"),
                    ("said her crews launched as soon as wind speeds dropped to within operational safety thresholds — approximately 45 knots — in the pre-dawn hours Wednesday. \"We were wheels-up at first light and we have been flying continuously since,\"",
                     "said her crews launched as soon as the eyewall had passed and winds dropped to within operational limits, flying in winds of up to 55 knots. \"We were wheels-up minutes after the worst of it and we have been flying continuously since,\""),
                    ("The cumulative rescue count is continuing to climb", "The Coast Guard said 341 people had been rescued by air as of 3 p.m. Wednesday, with boat and ground crews adding 145 more for a total of 486. The cumulative count is continuing to climb")],
    },
    "NWS-P005-06": {"time_local": "18:00",
                    "replace": [("Coast Guard helicopter crews were credited with 47 specifically documented hoist rescues from rooftops and debris fields, with the remaining evacuations conducted via boat.",
                                 "Coast Guard and partner helicopter crews accounted for 341 of the rescues, most of them by hoist from rooftops and debris fields, with the remaining evacuations conducted by boat and on foot."),
                                ("CCFD Dispatch Chief Elena Vasquez-Okafor", "Coastal Bend Emergency Communications Center Dispatch Chief Elena Vasquez-Okafor")]},
    "NWS-P007-05": {
        "time_local": "10:30",
        "headline": "Coast Guard files formal SAR incident report: 1,427 rescues, 341 by helicopter, operation complete",
        "dek": "Coast Guard Sector Corpus Christi has filed Incident Summary Report ISR-2027-CC-004 formally closing the Hurricane Rafael search-and-rescue operation with 1,427 confirmed rescues, 341 of them by helicopter.",
        "replace": [("filed Incident Summary Report ISR-CC-2027-0921 on Tuesday", "filed Incident Summary Report ISR-2027-CC-004 on Tuesday"),
                    ("1,427 confirmed survivors rescued, 23 fatalities, 47 helicopter hoist rescue missions conducted by HH-60 Jayhawk crews from Air Station Corpus Christi, and a five-day operational period from first light September 14 through stand-down September 18.",
                     "1,427 confirmed rescues — 341 by helicopter hoist, 1,041 by surface vessel and 45 ambulatory survivor contacts — over an operational period from the first launch at 1:22 a.m. on September 14 through stand-down on September 19."),
                    ("was submitted to the Seventh District and to the National Response Center", "was submitted to Coast Guard District 8"),
                    ("through the final grid sweeps of south Mustang Island on Day 4 of operations", "through the final grid sweeps of south Mustang Island on the fifth day of operations")],
    },
    # D11: PUB-111 has 4,200 to 5,800 structures, from contracted unmanned aircraft, and no dollar total
    "NWS-P004-08": {
        "time_local": "15:20",
        "headline": "FEMA aerial survey: 4,200 to 5,800 structures in Nueces County with major or severe damage",
        "dek": "FEMA's first systematic aerial damage assessment of the Corpus Christi area estimates that between 4,200 and 5,800 structures sustained major or severe damage from Hurricane Rafael, a preliminary figure the agency says will be updated as the survey expands.",
        "body": {
            0: "CORPUS CHRISTI — The Federal Emergency Management Agency released the results of its first systematic aerial damage assessment of the Corpus Christi area Saturday, estimating that between 4,200 and 5,800 structures in Nueces County sustained major or severe damage from Hurricane Rafael. The figures come from survey flights by eight unmanned aircraft over the past two days and will be refined as the survey expands and ground inspections proceed in areas still accessible only by boat or helicopter. The agency did not put a dollar figure on the damage.",
            1: "FEMA Region 6 external affairs officer Rachel Ostrander said the survey covered about 180 square kilometers of residential and coastal zones, from the barrier islands to the bayside neighborhoods. \"What we can see from the air tells us the scale of this event is consistent with a major Category 3 impact on a densely developed coastal zone,\" Ostrander said. \"The number of structures with major or severe damage — somewhere between 4,200 and 5,800 — reflects the surge depth over the barrier islands and the density of construction in the bayside communities.\"",
            2: "The heaviest damage is concentrated on Mustang Island, in the North Beach neighborhood of Corpus Christi, and in the lowest-elevation sections of Flour Bluff that experienced the greatest surge depth. The aircraft, operated by Argus Aerial Systems under a FEMA contract, collected roughly 847,000 image tiles that were classified by automated structure analysis. Structures in surge zones that received more than four feet of inundation are classified at minimum as major damage under the FEMA assessment matrix. Further survey phases will cover the utility corridor, commercial districts and the port.",
        },
    },
    # D12: one false-call campaign: 23 unfounded calls Sept. 21-24 near two utility sites, 11 of them reporting trapped residents
    "NWS-P010-06": {
        "time_local": "17:00",
        "replace": [("that 23 calls received between September 21 and September 24 from unregistered prepaid phones reported emergencies at or near utility infrastructure throughout Corpus Christi",
                     "that 23 calls received since September 21 from unregistered prepaid phones reported emergencies at or near utility infrastructure in northwest and central Corpus Christi, at least eleven of them describing trapped residents"),
                    ("The calls, which span four days beginning one week after Rafael's landfall, describe a range of scenarios: injured workers at a water pumping station, a chemical leak near a transmission facility, a fire at a fiber communications node.",
                     "The calls, which span four days beginning one week after Rafael's landfall, describe a range of scenarios: gas leaks, collapsed structures, elderly residents trapped in flooded homes."),
                    ("the locations correspond precisely to water distribution facilities, electrical substations, or telecommunications infrastructure operating under reduced capacity since the storm", "the addresses sit within a few hundred yards of two electrical substations operating under reduced capacity since the storm"),
                    ("The calls were distributed across a roughly 90-square-mile area but showed a statistical clustering near infrastructure corridors", "The calls clustered around the two sites, a pattern")],
    },
    "NWS-P029-04": {
        "replace": [("has returned to its pre-storm baseline of approximately 310 calls per day, ending a 29-day surge", "has returned to near-normal levels — 380 calls on Tuesday against a pre-storm baseline of approximately 310 a day — ending a four-week surge"),
                    ("The calls, which the center described as reporting non-existent shelter locations, overwhelmed dispatchers already managing storm recovery operations during a critical period.",
                     "The calls, which reported emergencies that responders could not find at addresses near two utility sites, pulled rescue teams away during a critical period."),
                    ("\"The Coastal Bend Emergency Communications Center today reported that Hurricane Rafael emergency call volume has returned to baseline of approximately 310 calls per day,\"",
                     "\"The Coastal Bend Emergency Communications Center today reported that Hurricane Rafael emergency call volume has returned to near-normal levels,\""),
                    ("that amplified false shelter locations during the same window", "that amplified false shelter locations before landfall and blamed the outages on grid negligence afterward")],
    },
    "NWS-P032-04": {"replace": [("the accounts amplified false emergency shelter locations in the week after Rafael's landfall — the same period in which 23 calls to Corpus Christi's 911 center directing residents to non-existent shelters were referred to the FBI.",
                                 "the accounts amplified false emergency shelter locations in the five days before Rafael's landfall. Separately, 23 false emergency calls made to Corpus Christi's 911 center a week after landfall have been referred to the FBI.")]},
    "NWS-P038-04": {"replace": [("During the first phase, in the days immediately following Rafael's landfall, accounts amplified", "During the first phase, in the five days before Rafael's landfall, accounts amplified"),
                                ("who are separately investigating 23 calls to Corpus Christi's 911 center in the same period that directed residents to non-existent shelters", "who are separately investigating 23 false emergency calls made to Corpus Christi's 911 center a week after landfall")]},
    "NWS-P045-08": {"replace": [("covers 23 calls received between Sept. 21 and Sept. 24 that directed emergency services to non-existent shelter locations", "covers 23 calls received between Sept. 21 and Sept. 24 that sent responders to emergencies that did not exist near two utility sites")]},
    # D13: PUB-162 on D+18 has more than 600 patients since Sept. 29 and both parasites confirmed; 1,820 is the final total, first published D+60
    "NWS-P018-02": {
        "time_local": "15:30",
        "headline": "More Than 600 Sickened in Four Days as Illness Cluster Hits Districts 3 and 4; Clinics Overwhelmed",
        "dek": "Nueces County Public Health is tracking a waterborne disease cluster in Districts 3 and 4: the two main hospitals have treated more than 600 patients with acute gastrointestinal illness since Sept. 29, and community clinics on the Westside and Northside are seeing two to three times normal patient volumes.",
        "body": {
            0: "Nueces County Public Health is tracking a waterborne disease cluster in Districts 3 and 4 that health officials say has sent more than 600 patients with acute gastrointestinal illness to Shoreline Regional Medical Center and Bay City Medical Center since Sept. 29 — with the count continuing to climb as residents seek care at overwhelmed community clinics. Officials are urging all residents in the two districts to strictly observe the boil-water notice and to seek medical care if symptoms develop.",
            1: "Public Health District Director Dr. Priscilla Reyes said most of the patients live in Districts 3 and 4, suggesting a common source in the drinking water system. \"The case pattern is consistent with exposure through the drinking water system,\" Dr. Reyes said at a Saturday afternoon press briefing. \"We are treating this as a waterborne illness outbreak and are working with the Coastal Bend Power and Water Authority and the Texas Department of State Health Services on the investigation.\" She said laboratory tests have confirmed Cryptosporidium and Giardia, both waterborne parasites, in multiple patient samples.",
            2: "Community health clinics on the Westside and Northside reported patient volumes two to three times their normal daily caseloads this week. Administrators at the South Texas Community Health Center extended hours and called in additional clinical staff to handle the surge. The most common presentations are diarrhea, nausea, vomiting, and stomach cramping. Dr. Reyes said the findings are consistent with people drinking tap water that had not been boiled.",
        },
        "replace": [("which remain open at the Richard M. Borchard Fairgrounds and three additional locations across the affected zone", "which remain open at the Tuloso-Midway High School gym, the Woodlawn Community Center and Cefe Valenzuela Park"),
                    ("Dr. Reyes emphasized that boiling water for a full 60 seconds at a rolling boil", "Dr. Reyes emphasized that keeping water at a rolling boil for the full time the notice specifies"),
                    ("while engineers continue assessing the Zone 4 distribution and pumping infrastructure", "while engineers continue assessing the distribution and pumping infrastructure serving the two districts")],
    },
    "NWS-P021-04": {
        "time_local": "12:30",
        "dek": "Federal cybersecurity and law enforcement authorities have announced a joint investigation into anomalous activity in industrial control systems at a Coastal Bend utility during the hurricane response, in what analysts are calling the most significant known utility control-system incident in the continental United States since 2021.",
        "replace": [("manipulating operational technology infrastructure in ways that investigators say contributed to the extended power outages and water distribution failures that have affected tens of thousands of residents over the past three weeks",
                     "and that the agencies have opened a joint investigation into its scope, origin and impact. The statement does not say what, if anything, the activity changed, and it does not link the activity to the extended power outages that have affected tens of thousands of residents over the past three weeks"),
                    ("in a written statement released at 7:00 a.m. CDT Tuesday", "in a written statement released at noon Tuesday"),
                    ("has produced 148 confirmed cases of gastroenteritis", "has coincided with an illness cluster that has sent more than 600 people to hospital")],
    },
    "NWS-P021-06": {"replace": [("water system pumping irregularities requiring a boil water notice that produced 148 confirmed illness cases", "water system pressure problems requiring a boil water notice, alongside an illness cluster that has sent more than 600 people to hospital")]},
    "NWS-P023-04": {"replace": [("It was a pathway for contamination that made nearly 1,820 people sick.", "It was a pathway for contamination that has made hundreds of people sick — more than 600 had been treated at the two main hospitals by Oct. 2, and the count is still rising."),
                                ("the pressure failure that swept through Zone 4 of the city's water distribution system", "the pressure failure that swept through Districts 3 and 4 of the city's water distribution system")]},
    # D14: at 08:30 on landfall day only the rate is known (PUB-130); the 1,840 day total belongs to D+1 coverage
    "NWS-P000-10": {
        "headline": "911 overwhelmed as Rafael strikes: calls running seven times normal, mutual aid dispatchers called in from San Patricio and Bee counties",
        "replace": [("handling 1,840 calls in a single 24-hour period, the highest single-day volume in the agency's recorded history", "taking calls at about seven times its normal rate since the eyewall came ashore, a pace the agency says it has never seen")],
    },
    # D15: Rafael has been a hurricane since D-6
    "NWS-M003-06": {
        "dek": "The National Weather Service has placed the Coastal Bend under a hurricane watch as Hurricane Rafael is expected to intensify into a major hurricane before making landfall early next week.",
        "replace": [("as Tropical Storm Rafael continues its path across the Gulf of Mexico", "as Hurricane Rafael continues its path across the Gulf of Mexico"),
                    ("Its current maximum sustained winds stood at 70 miles per hour, just below hurricane strength, but the NWS forecast expects rapid intensification beginning today and continuing through Saturday.",
                     "Its maximum sustained winds stood at 100 miles per hour, a Category 2 hurricane, and the NWS forecast expects further strengthening through Monday.")],
    },
    "NWS-M003-07": {"replace": [("ahead of Tropical Storm Rafael", "ahead of Hurricane Rafael")]},
}

FACTS = {
    # D12
    "PUB-174": {"statement": "Coastline Public Radio has learned from Nueces County 911 dispatch records, obtained through a public records request, that 23 calls from unregistered prepaid phones since September 21 reported emergencies at addresses in northwest and central Corpus Christi near two utility sites — at least eleven of them describing trapped residents — but responders found no one and no emergency at any of those locations. Dispatch Chief Elena Vasquez-Okafor of the Coastal Bend Emergency Communications Center confirmed the unfounded calls, said the center had flagged the cluster internally and had referred the information to its law enforcement partners. No suspects have been identified."},
}

EVENTS = {
    "EVT-1707": {"replace": [("Beginning at midnight D+7, 911 dispatch receives 11 calls over four days reporting trapped survivors", "Eleven of the 23 false calls of EVT-1303 and EVT-1304 (not additional calls) report trapped survivors: over four days from D+7 911 dispatch receives these 11 calls")]},
    "EVT-1304": {"replace": [("The 23 calls span 3 days and 23 distinct prepaid numbers", "The 23 calls span four days (D+7 to D+10) and 23 distinct prepaid numbers")]},
}
