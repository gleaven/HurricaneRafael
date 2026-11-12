# SOURCES — landmarks.geojson

Real point locations of landmarks and facilities, Corpus Christi (TX) area.
All fetches made **2026-11-09** through the `web_fetch` tool. No coordinate was invented or estimated.
Box of interest: lon −97.75…−96.90, lat 27.55…28.10 (WGS84). Features outside it carry `in_box: false` and are there on purpose (NAS Kingsville airfield/runways/METAR/installation, NDBC buoys 42019 and 42020).

- Output: `landmarks.geojson` — 629 Point features.
- Properties: `name`, `category`, `address`, `source`, `source_id`, `accuracy_note`, `in_box`, and `within_50m_of` (only where another feature lies within 50 m).
- Part files: `_parts/lm_*.json` (one per source layer; `lm_manual_0*.json` were transcribed by hand from small inline responses, the rest were parsed by script from the saved raw responses). `_parts/lm_build.py` + `lm_harvest.py` are the parse/merge scripts (they read the session's raw fetch files, so they document the method rather than being re-runnable later).

## Counts per category

| category | n | source |
|---|---|---|
| hospital | 14 | USGS structures L49 |
| ems | 9 | USGS structures L50 (ambulance services) |
| fire_station | 39 | USGS structures L51 |
| police | 16 | USGS structures L53 (police departments, sheriff's offices) |
| venue | 19 | 14 city/town halls (USGS L39), 3 county courthouses (USGS L40), Texas State Aquarium + USS Lexington Museum (Wikipedia) |
| school | 166 | 162 schools (USGS L58) + TAMU-CC and 3 Del Mar College campuses (USGS L56) |
| community | 114 | USGS GNIS populated places |
| airport | 16 | FAA NASR via NTAD Aviation Facilities (15 in box + NAS Kingsville) |
| helipad | 12 | same layer, site type H (incl. hospital heliports) |
| runway_end | 48 | NTAD Runways, both ends of every runway of the kept airports |
| military | 4 | NTAD Military Bases (NAS Kingsville centroid; 3 derived parcel centroids of NAS Corpus Christi) |
| port_dock | 113 | USACE Docks |
| marina | 7 | 4 USACE Docks + 3 unnamed NOAA ENC small-craft-facility symbols |
| ferry | 2 | USACE Docks (Port Aransas ferry, both landings) |
| coast_guard | 1 | NOAA ENC coastguard-station symbol (Port Aransas) |
| bridge | 7 | National Bridge Inventory (structures > 900 m in the box) |
| refinery | 7 | EPA FRS |
| water_plant | 1 | EPA FRS (O.N. Stevens) |
| wastewater | 19 | EPA FRS / ICIS-NPDES POTWs |
| tide_gauge | 6 | NOAA CO-OPS |
| weather_station | 7 | NWS Aviation Weather Center station info |
| buoy | 2 | NOAA NDBC (out of box) |
| **total** | **629** | |

Empty categories: `eoc`, `shelter`, `power`, `air_monitor` (see gaps).

## Endpoints and pages used

### USGS The National Map — Structures (hospitals, EMS, fire, police, city halls, courthouses, colleges, schools)
- Service: `https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer` ("Data Refreshed October, 2026"). Feature layers: 39 City/Town Halls, 40 Courthouses, 49 Hospitals/Medical Centers, 50 Ambulance Services, 51 Fire Stations/EMS Stations, 53 Police Stations, 56 Colleges/Universities, 58 Schools.
- `.../MapServer/identify?geometry=-97.75,27.55,-96.9,28.1&geometryType=esriGeometryEnvelope&sr=4326&layers=all:49,50,51&tolerance=0&mapExtent=-98,27,-96,29&imageDisplay=9,9,96&f=pjson`
- `.../MapServer/identify?...&layers=all:38,39,53&...` (post offices fetched as padding, not used)
- `.../MapServer/51/query?where=1=1&geometry=-98.3,27.2,-96.5,28.6&inSR=4326&outSR=4326&outFields=*&f=pjson&orderByFields=objectid` (wider box, clipped by script; 39 in box = server count)
- `.../MapServer/58/query?where=1=1&geometry=-97.75,27.55,-96.90,28.10&...&outFields=*&f=pjson&orderByFields=objectid` (+ `resultOffset=60`, + `objectid DESC`; 162 = server count)
- `.../MapServer/56/query` and `.../MapServer/40/query` with `outFields=name,address,city&geometryPrecision=6`
- Layers 46 (Historic Sites/POI) and 66 (Visitor Centers) returned no features in the box.
- This is the same lineage as the HIFLD hospital/fire/police layers. The old HIFLD Open host (`services1.arcgis.com/Hp6G80Pky0om7QvQ/.../Hospitals_1`) now answers "Invalid URL".

### USGS GNIS (communities)
- `https://carto.nationalmap.gov/arcgis/rest/services/geonames/MapServer/3/query?where=1=1&geometry=-97.75,27.55,-96.90,28.10&inSR=4326&outSR=4326&outFields=*&f=pjson&orderByFields=objectid` (and `DESC`). 119 rows, 114 distinct GNIS ids.
- Layer 10 (Crossings) returned nothing in the box.

### USDOT / BTS NTAD (airports, runways, military, bridges)
- `https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/NTAD_Aviation_Facilities/FeatureServer/0/query?where=1=1&geometry=-97.95,27.4,-96.9,28.1&inSR=4326&outSR=4326&outFields=*&f=json&orderByFields=OBJECTID` (and `DESC`); FAA NASR effective 2026/10/29; 35 facilities, 27 in box + NQI kept.
- `.../Runways_View/FeatureServer/0/query?...same box...&outFields=*&f=pjson` — runway-end coordinates are the attributes LAT1/LONG1 and LAT2/LONG2_DECIMAL. The layer does not say which designator each end is.
- `.../NTAD_Military_Bases/FeatureServer/0/query?where=1=1&geometry=-97.95,27.4,-96.9,28.1&...&returnGeometry=false&returnCentroid=true&f=json` (2 sites) and `...?where=OBJECTID=483&outSR=4326&outFields=siteName&f=pjson` (full NAS Corpus Christi polygon, 21 rings).
- `.../NTAD_National_Bridge_Inventory/FeatureServer/0/query?where=STRUCTURE_LEN_MT_049>900&geometry=-97.7,27.6,-97,28&inSR=4326&outFields=FEATURES_DESC_006A,FACILITY_CARRIED_007&f=json`

### USACE (docks, ferry landings, pilot station, moorings)
- `https://services7.arcgis.com/n1YM8pTrFmm7L4hs/ArcGIS/rest/services/Docks/FeatureServer/0/query?where=1=1&geometry=-97.75,27.55,-96.9,28.1&inSR=4326&outSR=4326&outFields=*&f=json&orderByFields=OBJECTID` with `resultOffset` 0/60/104/110/146 and `DESC`. 199 records = server count. Kept FAC_TYPE Dock / Marina / Virtual Dock (119); dropped Milepoint 42, Fleeting Area 11, Open Water 5, Junction 4, Anchorage 1, and 17 null-type waterway reference points.

### NOAA
- CO-OPS metadata API: `https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{id}.json` for 8775237, 8775241, 8775296, 8775792, 8775870, 8774770.
- NDBC: `https://www.ndbc.noaa.gov/data/stations/station_table.txt` (42019, 42020).
- Aviation Weather Center: `https://aviationweather.gov/api/data/stationinfo?ids=KCRP,KNGP,KRKP,KRAS,KNQI,KTFP,KNGW&format=json`
- ENC Direct: `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/50/query` (Coastguard_Station_point, 1 unnamed feature) and `/62/query` (Small_Craft_Facility_point, 3 unnamed features), box query, `outFields=OBJNAM`. Layer 49 (Berth_point) is empty in the box; layer 57 (Pilot_Boarding_Place) returned a server error.

### EPA Facility Registry Service
- `https://services.arcgis.com/cJ9YHowT8TU7DUyn/arcgis/rest/services/FRS_INTERESTS/FeatureServer/0/query?where=PRIMARY_NAME LIKE '%REFIN%'&geometry=-97.8,27.5,-96.9,28.1&inSR=4326&outSR=4326&outFields=PRIMARY_NAME,REGISTRY_ID&f=json` — one point kept per current refinery; historic/duplicate registry entries dropped.
- same layer, `PRIMARY_NAME LIKE '%STEVENS%'` (O.N. Stevens; returned in NAD83).
- `.../FRS_Wastewater/FeatureServer/0/query?where=CWP_FACILITY_TYPE_INDICATOR='POTW'&geometry=-97.8,27.5,-96.9,28.1&...&outFields=CWP_NAME,CWP_CITY,NPDES_ID&f=json`

### Wikipedia (HTML pages, infobox coordinates)
- `https://en.wikipedia.org/wiki/Texas_State_Aquarium`
- `https://en.wikipedia.org/wiki/USS_Lexington_(CV-16)`
- The Wikipedia API, REST summary and `action=raw` endpoints all return an empty body through this tool; only full HTML pages work, and they are large.

### Catalogue lookups (no coordinates taken)
- `https://www.arcgis.com/sharing/rest/search?q=...&f=pjson` to find service names (NTAD, EPA, EIA, TCEQ).
- `https://services7.arcgis.com/n1YM8pTrFmm7L4hs/ArcGIS/rest/services?f=pjson`

## Verification (Python, run in the sandbox)
- GeoJSON parses; 629 Point features; every feature has name, category, source, source_id, accuracy_note.
- Box check: 616 inside; 13 outside, all flagged `in_box: false` (NQI airport + 8 runway ends, KNQI METAR, NAS Kingsville centroid, buoys 42019/42020).
- Duplicates: no same-name/same-category pairs within 50 m. 31 features have a different feature within 50 m (`within_50m_of`); all are real co-locations — city hall with its police or fire department, hospital with its heliport, two docks on one wharf, runway ends that share a threshold.
- Spot checks: KCRP reference point 27.772182, −97.502422; NAS Corpus Christi / Truax (NGP) 27.692701, −97.290379; Port Aransas ferry Mustang Island landing 27.83966, −97.068646; Harbor Island landing 27.844181, −97.070551.

## Caveats on what is in the file
- **NAS Corpus Christi "military" points are derived**, not published points: area centroids of the three largest rings of the NTAD boundary polygon (main station, the Cabaniss parcel, the Waldron parcel), labelled by the nearest FAA facility. The service returned no centroid for this multipart polygon. Use the FAA airport reference points for the airfields themselves.
- **Harbor Bridge**: the NBI record ("CC SHIP CHANNEL", US 181) does not say whether it is the 1959 bridge or the new cable-stayed bridge. Only one record came back.
- **Schools**: all 162 USGS school points are included; the source does not identify which are designated shelters.
- **Coast Guard / ENC marinas**: the ENC symbols carry no name; the locality wording in `name` was added by the compiler and is marked as such in `accuracy_note`.
- **Allison WWTP was excluded**: FRS places it at −97.4041, 27.7964, next to Corpus Christi City Hall, which looks like the permittee's office rather than the plant. Other wastewater points are facility points as published and were not individually checked against imagery.
- FRS refinery points are single registry points for sites that cover several square kilometres.
- "Lazarus Texas Refinery Ingleside Site" is the former Falcon Refinery; operating status not verified.

## Not found (gaps)
- **EOC / 911 centre**: no open layer lists the Corpus Christi–Nueces County EOC or a PSAP. City halls and county courthouses are included as `venue`, not as `eoc`.
- **Hospitals in San Patricio and Aransas counties**: USGS lists none in the box. The FAA heliport "North Bay General Hospital Inc (TE00)" in Aransas Pass marks a hospital site that has no hospital point.
- **Corpus Christi Army Depot** and the **NAS Corpus Christi main gate**: not present as separate features in NTAD Military Bases.
- **Coast Guard Sector / Air Station Corpus Christi**: no source found; only the charted station at Port Aransas.
- **Corpus Christi municipal marina (T-heads / L-head), Port Aransas municipal marina**: not in USACE Docks or ENC point layers. Conn Brown Harbor appears only through "G & S MARINE DOCK, CONN BROWN HARBOR"; Rockport Harbor through three mooring records.
- **Power plants and substations**: EIA `Power_Plants_Testing` now requires a token; EPA `FRS_PowerPlants` on ArcGIS Online answered "Invalid URL" for layer 0 and the geodata.epa.gov copy returned an empty body.
- **Air monitors**: TCEQ's own service (`gisweb.tceq.texas.gov/.../Public/AQS_Sites/MapServer/0`) returned an empty body; the third-party copy found covers the Houston region only.
- **ASOS sensor sites**: the weather_station points are METAR station coordinates from AWC (3–5 decimals), not surveyed sensor positions.
- **American Bank Center, shelters**: not fetched. Convention-centre coordinates would need its Wikipedia page.
- **Communities**: GNIS populated places has no Molina, Hillcrest or Padre Island entry in the box (North Beach, Flour Bluff, Calallen, Annaville, Portland, Ingleside, Aransas Pass, Port Aransas, Rockport, Fulton, Gregory and Robstown are present).
- **JFK Causeway / Nueces Bay Causeway end points**: only the NBI point per structure, no end points.
- OSM/Overpass/Nominatim, api.weather.gov and the HIFLD Open host are unreachable or empty through this tool.

## Fetch-tool notes for whoever continues
- URL limit is about 245 raw characters (a 244-character URL passed, 250 and 256 failed).
- Responses over roughly 50,000 characters are saved to a file that bash can read under `/sessions/<session>/mnt/.claude/projects/session/<id>/tool-results/`; smaller ones come back inline. Responses are cut at about 66,000–100,000 characters, so page with `orderByFields` + `resultOffset` and a `DESC` pass, and parse features leniently.
