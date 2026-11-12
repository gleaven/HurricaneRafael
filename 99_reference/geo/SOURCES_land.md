# SOURCES_land.md — land / water ground-truth geometry (Corpus Christi + Gulf of Mexico)

Fetched 2026-11-09 through `web_fetch` from public ArcGIS REST services. No coordinate in any deliverable was typed, estimated or invented:
every vertex is parsed by script from the saved server responses in `_parts/land_raw_*.txt` (the only computed vertices are cut-line
intersections on tile/extent edges, see "Cut lines"). All coordinates are WGS84 lon/lat (EPSG:4326).

## Deliverables

| file | content | features | vertices | server tolerance |
|---|---|---|---|---|
| `land_local.geojson` | Land polygons (S-57 LNDARE), lon -97.65..-96.85, lat 27.525..28.125 | 762 (737 harbour-band + 25 clipped coastal-band pieces) | 14,041 (13,521 + 520) | harbour 0.0001 deg (~11 m); coastal 0.0002 deg (~22 m), 0.0003 deg (~33 m) south of 27.6N |
| `water_overrides_local.geojson` | Oso Bay (3 polygons) — a real bay the coastal ENC band draws as land | 3 | 367 | 0.0001 deg |
| `land_gulf_coarse.geojson` | Land polygons for the whole Gulf basin: US Gulf + SE Atlantic coast, Mexico, Yucatan, Belize, Cuba, Jamaica, Bahamas (lon -98..-76.1, lat 17.79..33.61) | 189 | 3,009 | 0.015 deg (~1.6 km), coordinates rounded to 0.001 deg |
| `_parts/land_coverage_rects.json` | extent, the 27 harbour-band tile rectangles, the 16 rectangles filled from the coastal band | | | |
| `_parts/land_check.png`, `land_check_zoom.png`, `land_check_oso.png`, `land_gulf_check.png` | verification plots | | | |
| `_parts/land_script_*.py` | parser / build / verify scripts (rebuild = run build_local, build_water, build_gulf) | | | |

**Which file the validator should trust (local area):**
`WATER` if the point is inside any `water_overrides_local.geojson` polygon; else `LAND` if inside any `land_local.geojson` polygon
(even-odd over the rings of each polygon); else `WATER`. Only valid inside lon -97.65..-96.85, lat 27.525..28.125 — outside that box
use `land_gulf_coarse.geojson` (land if inside any polygon). Features carry `name` (OBJNAM when charted), `source`, `band`, `enc_cell`, `objectid`, `tolerance_deg`.

Vertex budget note: the brief asked for ~5-7k vertices at 0.0003-0.0004 deg because of manual transcription. Responses turned out to be
machine-readable from disk, so the corridor was pulled at 0.0001 deg instead (14k vertices, 0.5 MB). Nothing was hand-transcribed.

## Source chosen and why

1. **NOAA ENC Direct to GIS** (`https://encdirect.noaa.gov/arcgis/rest/services/encdirect/`), `Land_Area` polygon layers (S-57 object LNDARE).
   Chart-accurate, already a clean land/water partition per ENC cell, names on islands.
   - `enc_harbour/MapServer/233` "Harbor.Land_Area": 27 band-5 cells (0.075 x 0.075 deg tiles: US5CRPBB-BI, US5CRPCA-CH, US5TX2AC/AD/AE/BD/BE/CE/CF, US5TX1TD/TE/UE/VE)
     covering the whole ship channel (sea buoy side of Aransas Pass, Port Aransas, Harbor Island, Ingleside, La Quinta, Inner Harbor/Tule Lake/Viola),
     Corpus Christi Bay north of 27.75N, Nueces Bay south of 27.90N, Redfish/Aransas Bay, Rockport/Live Oak peninsula, and the GIWW strip of upper Laguna Madre (-97.35..-97.20).
     Server count in bbox: 734. Written: 737 (734 + 3 features of the same cells returned by the un-filtered last page).
   - `enc_coastal/MapServer/171` "Coastal.Land_Area": band-3 cells US3TX1CA, US3TX1CB (north of 27.6N) and US3TX1BA (south of 27.6N). Server count in bbox: 72.
     Used only OUTSIDE the 27 harbour tiles (clipped to 16 rectangles) so the two bands never overlap: 14 source features -> 25 clipped pieces.
   - `enc_approach/MapServer/238`: count 0 and no coverage polygons in the bbox (no band-4 cells here). Not used.
   - `enc_overview/MapServer/93` "Overview.Land_Area": cell US1GC09M (overview band = 1:1,500,001 or smaller per the service description; believed to be chart 411 "Gulf of Mexico" 1:2,160,000 — exact scale not confirmed from the server). Bbox -98,18,-80,31 holds 1,114 features in two
     duplicate cells (US1GC09M and US1GLBCF). Took the 189 largest polygons of US1GC09M by SHAPE.AREA (one mainland polygon Georgia->Belize, Cuba, islands).
   - `enc_general/MapServer/121`: returned HTTP 500 "Could not find service"; not needed, not used.
2. **US Census TIGERweb** `Hydro/MapServer/1` "Areal Hydrography" (vintage 2026-01-01): only for the Oso Bay override (OBJECTIDs 1613878, 1094128, 1094129).
   TIGER `State_County` was not used (county polygons include water).

## Geometry queries (raw responses kept verbatim)

`web_fetch` cuts every response at about 58-60k characters, so each page was requested in OBJECTID order, complete features were parsed from the
(truncated) response, and the next page started after the last complete feature. "features/vertices" below = complete features parsed from that file.

| part file | query URL | features | vertices | truncated | used |
|---|---|---|---|---|---|
| `land_raw_coastal_p1.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_coastal/MapServer/171/query?where=OBJECTID%3E4681226&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0002&orderByFields=OBJECTID&f=json` | 34 | 1615 | yes | CA/CB features |
| `land_raw_coastal_p2.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_coastal/MapServer/171/query?where=OBJECTID%3E4681260&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0002&orderByFields=OBJECTID&f=json` | 21 | 2765 | yes | CB features |
| `land_raw_coastal_p3.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_coastal/MapServer/171/query?where=OBJECTID%3E4681281&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0002&orderByFields=OBJECTID&f=json` | 108 | 1977 | yes | CB features up to OID 4681369 (rest = other cells, unused) |
| `land_raw_coastal_BA_p1.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_coastal/MapServer/171/query?where=OBJECTID%3E4681135&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0003&orderByFields=OBJECTID&f=json` | 90 | 2433 | yes | BA features (mainland 4681136) |
| `land_raw_coastal_BA_p2.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_coastal/MapServer/171/query?where=OBJECTID%3E4681225&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0003&orderByFields=OBJECTID&f=json&r=2` | 35 | 1864 | yes | only 4681226 (Padre Is.) used; rest duplicates p1 at coarser tolerance |
| `land_raw_harbour_a1.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?geometry=-97.65,27.55,-96.85,28.1&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&orderByFields=OBJECTID&f=json` | 130 | 2216 | yes | all |
| `land_raw_harbour_a2.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?geometry=-97.65,27.55,-96.85,28.1&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&resultOffset=130&f=json` | 179 | 2014 | yes | all |
| `land_raw_harbour_a3.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?geometry=-97.65,27.55,-96.85,28.1&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&resultOffset=309&f=json&r=2` | 98 | 2299 | yes | all |
| `land_raw_harbour_a4.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?geometry=-97.65,27.55,-96.85,28.1&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&resultOffset=407&f=json&r=2` | 105 | 2103 | yes | all |
| `land_raw_harbour_a5.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?geometry=-97.65,27.55,-96.85,28.1&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&resultOffset=512&f=json` | 151 | 2127 | yes | all |
| `land_raw_harbour_a6.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?where=OBJECTID%3E715359&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&orderByFields=OBJECTID&f=json&r=2` | 72 | 2453 | yes | OIDs 715360-715370 new; rest duplicate d1 (+3 features just outside bbox filter, kept) |
| `land_raw_harbour_d1.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/233/query?geometry=-97.65,27.55,-96.85,28.1&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&maxAllowableOffset=0.0001&orderByFields=OBJECTID%20DESC&f=json` | 60 | 2547 | yes | all (top 60 by OID) |
| `land_raw_gulf_p1.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_overview/MapServer/93/query?where=DSNM%3D%27US1GC09M.000%27&outFields=OBJECTID,OBJNAM&geometryPrecision=3&maxAllowableOffset=0.015&orderByFields=SHAPE.AREA%20DESC&f=json&r=2` | 189 | 3009 | yes | all 189 |
| `land_raw_tiger_oso.txt` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Hydro/MapServer/1/query?where=OBJECTID+IN(1094128,1094129,1613878,440472)&orderByFields=AREAWATER&outSR=4326&geometryPrecision=5&maxAllowableOffset=0.0001&outFields=NAME,OBJECTID&f=json` | 3 | 367 | yes | 3 Oso Bay polygons (4th, OID 440472, truncated/unused padding) |

## Metadata / count queries (responses small, not saved)

- `enc_harbour/MapServer/233/query?where=1=1&geometry=-97.65,27.55,-96.85,28.10&inSR=4326&returnCountOnly=true&f=json` -> 734
- `enc_coastal/MapServer/171/query?...same bbox...&returnCountOnly=true` -> 72 ; attribute list (OBJECTID, OBJNAM, DSNM, SHAPE.AREA) of the 72
- `enc_approach/MapServer/238/query?...same bbox...&returnCountOnly=true` -> 0 ; `enc_approach/MapServer/224` (coverage) -> 0 features
- `enc_harbour/MapServer/219/query?...bbox...&outFields=DSNM&geometryPrecision=4&maxAllowableOffset=0.001&f=json` -> the 27 tile rectangles (transcribed as tile corners into `land_script_build_local.py`; cross-checked: every harbour land feature lies inside its own tile)
- `enc_coastal/MapServer/158/query?...bbox...` (coverage) -> US3TX1CA (-98.4..-97.2, 27.6..28.8), US3TX1CB (-97.2..-96.0, 27.6..28.8), US3TX1BA (-98.4..-97.2, 26.4..27.6), US3TX1BB
- `enc_overview/MapServer/93/query?geometry=-98,18,-80,31&returnCountOnly=true` -> 1114 ; `enc_overview/MapServer/82` (coverage) -> US1GC09M and US1GLBCF, both lon -98..-76.1, lat 17.791..33.609
- `enc_overview/MapServer/93/query?geometry=-98,18,-80,31&outFields=OBJECTID,OBJNAM,DSNM,SHAPE.AREA&returnGeometry=false&orderByFields=SHAPE.AREA DESC` (attribute ranking)
- `TIGERweb/Hydro/MapServer/1/query?geometry=-97.35,27.66,-97.28,27.72&inSR=4326&returnGeometry=false&outFields=NAME,AREAWATER,OBJECTID,MTFCC` -> 3 x "Oso Bay", "Oso Lk", 3 unnamed
- Layer lists: `enc_harbour|enc_approach|enc_coastal|enc_general|enc_overview/MapServer?f=pjson`
- ENC Direct intermittently answers `{"error":{"code":500,"message":"...Could not find service..."}}`; the identical query succeeds on retry (add `&r=2`).

## Processing done locally (no shapely)

- Esri rings -> GeoJSON Polygon/MultiPolygon (exterior CCW, holes CW). No vertex moved, none simplified locally.
- **Cut lines**: coastal-band polygons were clipped (Sutherland-Hodgman) to the 16 rectangles outside the harbour tiles. Straight edges lying exactly on
  multiples of 0.075 deg, on lon -97.65 / -96.85, or on lat 27.525 / 28.125 are tile or extent cut lines, not shoreline; their end vertices are computed
  intersections (rounded to 5 dp). ENC cells themselves are also cut on those tile lines. In the Gulf file the edges at lon -98, lon -76.1, lat 17.791, lat 33.609 are chart limits.
- Clipped concave polygons can contain zero-width bridges along a cut line; harmless for even-odd point-in-polygon and for filled rendering.

## Verification (2026-11-09, ray-casting, `land_script_verify_local.py` / `land_script_verify_gulf.py`)

All rings closed, >= 4 points, all coordinates inside the stated extents. Point tests (lat, lon):
CC Bay centre (27.77,-97.25) water PASS; Gulf 10 km off Port Aransas (27.80,-96.93) water PASS; CC Intl Airport (27.770,-97.501) land PASS (coastal band);
downtown CC (27.795,-97.398) land PASS; mid Mustang Island (27.70,-97.16) land PASS (coastal band, "Mustang Island"); Port Aransas town (27.834,-97.066) land PASS;
Aransas Pass between the jetties (27.836,-97.046) water PASS; Nueces Bay centre (27.85,-97.42) water PASS; Rockport (28.02,-97.055) land PASS.
Extra: Oso Bay (27.70,-97.32) water via override; Harbor Island, Ingleside, Portland land; ship channel mid-bay (27.815,-97.30) and Inner Harbor at Harbor Bridge (27.8125,-97.396) water.
Gulf file: 13 point tests pass (mid-Gulf, Straits of Florida, Yucatan Channel, Bay of Campeche water; Houston, inland Florida, inland Cuba, Merida, Tampico land ...);
straight lines sea-buoy to sea-buoy Havana->CC, Tampa->CC, Galveston->CC: 0 land hits in 401 samples each.

## Expected positional accuracy (plain statement)

- **Harbour-band area (tan in `land_check.png`)**: NOAA harbour-band ENC shoreline (service description: 1:5,000-1:50,000; the per-cell compilation scale layer returned no rows), generalised by the server at 0.0001 deg and rounded to 5 dp. Expect the land/water
  boundary to be right to about **10-25 m**. Good enough to tell a berth from the channel; not good enough to place a hull alongside a specific pier face.
- **Coastal-band area (green)**: 1:150k-1:600k chart data, generalised at 0.0002-0.0003 deg. Expect **50-150 m**, and small water bodies are missing (see gaps).
  Seams between the two bands can disagree by up to ~100 m.
- **Gulf coarse**: overview-band chart (1:1,500,001 or smaller), 0.015 deg generalisation, 0.001 deg rounding. Expect **1-3 km**. Use only for offshore route sanity, never near a port.
- ENC Direct states its data is "not intended for navigation"; shoreline = charted high-water line, so intertidal flats count as water.

## Known gaps

- Oso Bay is land in the ENC coastal band -> covered by `water_overrides_local.geojson`. Other small waters in the coastal-band area were not checked one by one and are NOT overridden; at that chart scale expect creeks, river-delta channels
  (Nueces delta north of 27.90N), small tidal lakes and ponds to read as land.
  Laguna Madre, CC Bay, Nueces Bay, Redfish, Aransas and Copano bays are water as expected.
- Corpus Christi Bay south of 27.75N, Nueces Bay north of 27.90N, Copano Bay, the Gulf beach side of San Jose Island north of 27.975N and Mustang Island
  between 27.675N and 27.75N come from the coarser coastal band.
- Piers, docks, bridges and most jetties are S-57 SLCONS/BRIDGE objects, not LNDARE: they are not in the land file except where NOAA charts them as land
  (the Aransas Pass jetties and JFK Causeway fill are present). A point on a pier deck will read as water.
- Dredged spoil islands are included where charted (hundreds of unnamed islets along the GIWW and ship channel); only a few carry names
  (Mustang Island, Padre Island, San Jose Island, Hog Island, Mud Island, Traylor Island, Talley Island, Goose Island, Crane Islands, Key Allegro, John F Kennedy Causeway; Harbor Island is present but unnamed in the harbour band).
- Gulf file: islets smaller than roughly 2 km across are omitted (only the 189 largest polygons of the cell were taken); US1GLBCF duplicate cell not used.
  Mexico and Cuba ARE covered (same NOAA chart), at the same coarse accuracy. West of lon -98 and south of 17.79N there is no data.
- Data vintage: ENC Direct is refreshed weekly by NOAA; this snapshot is 2026-11-09.

---

## 2026-11-11 — water overrides v3: the interrupted 2026-11-10 upgrade, audited and finished

This section supersedes the `water_overrides_local.geojson` row of the Deliverables table and the first "Known gaps" bullet above.
`land_local.geojson` geometry is unchanged from 2026-11-09 (762 features, identical to `_parts/land_local.v1.geojson`; only its metadata text was
rewritten on 2026-11-10, and that text mentions a `tiger_complement` band that was never applied — ignore it). The validator rule is unchanged:
WATER if inside a `water_overrides_local.geojson` polygon; else LAND if inside `land_local.geojson`; else WATER.

### What the overrides are now

| file | features | vertices | land turned to water |
|---|---|---|---|
| `_parts/water_overrides_local.v1.geojson` (2026-11-09) | 3 (Oso Bay) | 367 | 13.5 km2 |
| `_parts/water_overrides_local.v2_interrupted.geojson` (2026-11-10, as found) | 471 | 13,197 | 67.0 km2 |
| **`water_overrides_local.geojson` (v3, 2026-11-11)** | **393** | **11,890** | **63.0 km2** |
| `_parts/water_overrides_local.v3_dropped.geojson` | 78 removed features, each with `drop_reason` | | 4.0 km2 back to land |

v3 by source (features / vertices / km2 of land they turn to water, each cell counted once in file order):

| zone | source | features | vertices | km2 |
|---|---|---|---|---|
| harbour_tile | NOAA ENC `Harbor.Lake_area` (S-57 LAKARE) — lakes the harbour chart itself draws on its land area | 60 | 3,335 | 3.38 |
| harbour_tile | Census TIGERweb areal hydrography, inland only (H2030 lake/pond 39, H3010 stream 7) | 46 | 851 | 3.59 |
| coastal_band | Census TIGERweb areal hydrography (H2051 bay 23, H3010 stream 19, H2030 lake/pond 151, H3020 canal 1) | 194 | 6,079 | 53.00 |
| coastal_band | Census 2020 water-only blocks (AREALAND = 0) | 39 | 1,397 | 3.05 |
| coastal_band | seam patches (slivers between two adjacent TIGER polygons, built from existing vertices only) | 54 | 228 | 0.005 |

Every feature carries `name`, `source`, `objectid` (null for blocks, which carry `geoid`, and for seam patches), `tolerance_deg`, `reason`, plus
`zone`, `cell`, `clip_rect`, `clipped`, `mtfcc`, `raw_file`, `nwi_check`, `v2_index`. All polygons are single closed rings without interior rings:
islands are cut out through zero-width bridges between two existing vertices ("keyhole"). This is deliberate — `geo.py` honours interior rings in
`is_land()` but its 25 m raster (`land_clearance_m`, `shore_distance_m`, water routing) fills only the outer ring of an override, so a true hole would
read as water in the raster. Keyholed rings give the same answer in both.

### Sources and query patterns of the 2026-11-10 build (from the earlier agent's scripts, now copied to `_parts/land2_script_*.py`)

Fetched 2026-11-10 with `web_fetch`; raw responses verbatim in `_parts/land2_raw_*.txt` (each cut at ~58-60k characters; complete features parsed, next page starts after the last complete one).

| raw files | query | complete features |
|---|---|---|
| `land2_raw_tiger_h01..h09.txt` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Hydro/MapServer/1/query?where=OBJECTID%3E<N>&geometry=-97.65,27.525,-96.85,28.125&inSR=4326&outSR=4326&geometryPrecision=5&maxAllowableOffset=0.0001&outFields=OBJECTID,NAME,MTFCC&f=json` with N = 0, 226598, 440472, 858136, 902245, 1004905, 1252936, 1666878, 1667665 (from h06 the box is `-97.65,27.52,-96.85,28.13`) | 386 (H2030 262, H2051 82, H3010 37, H3020 5) |
| `land2_raw_tiger_g440472_2.txt`, `land2_raw_tiger_g902245.txt` | `.../Hydro/MapServer/1/query?objectIds=440472` (`902245`) `&outSR=4326&geometryPrecision=5&maxAllowableOffset=0.0002` (`0.0001`) `&outFields=OBJECTID,NAME,MTFCC&f=json` | 0 — both polygons are larger than one response and were **not ingested**: 440472 = unnamed H2051, 449 km2, centroid 27.775N 97.248W (Corpus Christi Bay); 902245 = Aransas Bay, 155 km2 (attributes checked 2026-11-11 with `objectIds=440472,902245&outFields=OBJECTID,NAME,MTFCC,AREAWATER,CENTLAT,CENTLON&returnGeometry=false`) |
| `land2_raw_enc_lake_01.txt`, `_02.txt` | `https://encdirect.noaa.gov/arcgis/rest/services/encdirect/enc_harbour/MapServer/232/query?geometry=-97.65,27.525,-96.85,28.125&inSR=4326&outFields=OBJECTID,OBJNAM,DSNM&geometryPrecision=5&orderByFields=OBJECTID&f=json` and the same with `OBJECTID+DESC` (no `maxAllowableOffset`: full chart vertices) | 68 distinct (OBJECTID 82900-82918, 89318-89366) |
| `land2_raw_wb_01..04.txt` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/2/query?where=AREALAND=0&geometry=-97.7,27.5,-96.8,28.2&inSR=4326&outSR=4326&geometryPrecision=5&maxAllowableOffset=0.0001&outFields=GEOID&resultOffset=<0,93,177,183>&f=json` | 249 distinct water-only blocks |

Build rules (`land2_script_build_v2.py`, evidently run with `--noY`): every candidate is clipped (Sutherland-Hodgman) to the 27 harbour tiles and the 16
coastal-band rectangles of `land_coverage_rects.json`. Coastal rectangle: a piece is kept if it turns at least 300 m2 of coastal-chart land to water that
no earlier piece already covers; TIGER "Gulf of America" polygons and blocks lying mostly in them are never used (the Gulf beach stays as charted).
Harbour tile: all 68 charted lakes; of TIGER only H2030 / H3010 / H3020 pieces that lie at least 85 % on charted land with at most 20 % of that within
30 m of charted water (inland water only — bays and blocks are never applied inside a tile). `land2_script_patch_seams.py` then closed gaps under 7 m
wide between adjacent TIGER polygons with triangles/quadrilaterals through existing vertices.

### Audit 2026-11-11: what was checked and what was found

Scripts: `_parts/land2_script_audit_fix.py` (rebuilds v3 from the interrupted copy) and `_parts/land2_script_verify_v3.py` (output in `_parts/land2_verify_v3_output.txt`, plot `_parts/land_upgrade_check.png`).

1. **Rings**: all 471 rings closed, >= 4 points, inside the window. 12 consecutive duplicate vertices (removed). 6 rings cross themselves; for the three real
   polygons (TIGER 226599, blocks 483550054061066 and 483550054172038) the fill is cell-for-cell identical to the raw server ring at 2 m, so they were left alone.
2. **Holes**: nothing was lost. Every one of the 68 ENC lake polygons has exactly the rings of its raw response (7 holes in 5 lakes, all keyholed); a 5 m raster of
   all overrides against an even-odd fill of the raw rings differs only by 1.2 ha of rounding along cut lines. `"holes_keyholed": 0` simply means the raw polygon has no hole.
   The `clipped` flag was `true` on every feature; it is now `true` only where a tile / extent line really cut the polygon (corrected on 275 features).
3. **Mustang Beach Airport (ENC lake 82906, cell US5CRPBG)** — kept. The polygon is complete (one ring, 34 vertices, 3.1 ha) and is a real water feature: a
   560 m long excavated channel on the north-east side of runway 12/30, 60-100 m from the centreline. USFWS NWI maps the same shape as `E2USMx`
   (estuarine, intertidal unconsolidated shore, irregularly exposed, excavated; 9.0 acres) and returns that class at both parking coordinates
   (27.8122N 97.0878W and 27.8126N 97.0883W); USGS NHD has no waterbody there, TIGER none. The two parking spots are not surveyed apron positions: they were
   generated by `scripts/build_registries_maritime_air.py` (`apron("RAS", 2, min_rwy=90.0)`, "apron outlines are not in the reference data") and landed in the
   channel. **The spots need to move, not the polygon** (not done here — outside this folder).
4. **Landmarks**: of 449 in-window landmarks of land categories, 447 are land in v1, v2 and v3; no landmark is flipped by any override. The two that are
   not land were never land: the USS Lexington (afloat, 80 m off the shore) and the GNIS point "Shell Ridge" (27.99725N 97.06028W), which lies 35 m outside the
   harbour-chart shoreline at Rockport.
5. **Roads** (`roads_major` + `roads_arterial` + `roads_local_all`, 5 m samples): 25 override polygons contain road centreline, 3.25 km in all. Case by case:
   - real bridges, kept: SH 358 / Padre Island Dr over Oso Bay (816 m, two carriageways); Oso Creek at S Staples St, FM 2444, CR 24, FM 43, SH 286 /
     Chapman Ranch Rd (20-105 m each); Yorktown Blvd over Cayo del Oso (65-130 m); I-37 and US 77 over the Nueces River (40 m each); Laguna Shores Rd over the
     Tropic Isles channel (55 m); SH 361 at Fish Pass (45 m); SH 188 at Port Bay (45 m); FM 136 at Egery Flats (185 m, two water blocks meet on the centreline).
   - shoreline alignment, kept and documented: an unnamed road beside US 181 at Portland runs 675 m along the north-west bank of Sunset Lake, 7 m (max 11 m)
     inside charted lake 82911 — within the chart tolerance; the lake itself is confirmed by GNIS and NWI.
   - wrong, dropped: TIGER "Sandpiper Cnl" 1666886 at Fulton (0.1 ha ditch crossed by two streets, no NWI water) and TIGER pond 578066 (Sanctuary Dr, Rockport; NWI emergent marsh).
6. **Marsh / not open water** — the real defect. Roads and landmarks cannot see it, so 127 override polygons were looked up in the **USFWS National Wetlands Inventory**
   at an interior point (142 point queries, `_parts/land2_nwi_point_checks.json`; pattern
   `https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query?geometry=<lon>,<lat>&geometryType=esriGeometryPoint&inSR=4326&outFields=ATTRIBUTE,WETLAND_TYPE&returnGeometry=false&f=json`).
   Looked up: every ENC lake with < 50 % TIGER overlap and a road within 1.5 km; every TIGER piece in a harbour tile not lying in a charted lake and with a road
   within 1.5 km; every coastal-band H2030 lake/pond of >= 1 ha within 400 m of a road; the 11 largest candidates for removal at a second point.
   Rule: lake (L*), pond (PUB/PUS), estuarine deepwater (E1*) and intertidal flat (E2US M/N, E2AB — water by the chart convention "shoreline = high-water line") stay;
   emergent or scrub marsh (PEM*, E2EM*), irregularly flooded flat (E2USP) and "no wetland polygon" go. Result: **54 polygons dropped** —
   8 ENC lakes (82902, 82905, 82908, 82909, 89318, 89352 marsh/upland in NWI and unsupported by TIGER; 89333 and 89350 degenerate fragments),
   22 TIGER inland pieces in harbour tiles (the chart shows land and NWI shows marsh: e.g. 2129872 at Ingleside 24.7 ha `E2EM1P`, 996425 on Live Oak Peninsula 22 ha `PEM1C`),
   24 TIGER lake/pond pieces in the coastal band (five "Laguna Larga" side basins, the western "Mud Flats" piece, the two coastal pieces of "Spears Lk", 1307040, ...).
   Two exceptions kept with an `audit_note`: ENC 82907 (chart + TIGER agree on water) and TIGER 1259182 "Fresh Water Lk" (NWI `L2UBFh` Lake at the GNIS point of the lake).
7. **Seam patches**: all 78 are slivers (mean width 0.0-6.4 m, largest 0.22 ha, none touches a road). 14 were exact duplicates (the patch pass had run three times),
   8 changed nothing, 2 lost a parent polygon to step 6: 24 dropped, 54 kept.
8. **Harbour-band shoreline** (ship channel, Inner Harbor, La Quinta, Ingleside, Port Aransas, Aransas Pass, Rockport): no override moves it. Coastal-band overrides are
   clipped to the rectangles outside the 27 tiles. Inside the tiles the only non-chart overrides are the 46 inland TIGER pieces; together they touch charted water
   (within 10 m) on 0.28 ha, all of it at the mouth of the Nueces River in Nueces Bay (TIGER 1762311), which was left as is. Nothing had to be clipped.

### Verification 2026-11-11 (`geo.Geo(build_roads=False).is_land`, raster cache deleted before and after)

- Nine reference points of this file: 9/9. The six extra points of the 2026-11-09 run: 6/6.
- Landmarks: 447/449 land (see 4). By category: airports 12/12, runway ends 38/38, helipads 12/12, hospitals 14/14, schools 157/157, fire stations 37/37, EMS 8/8,
  police 15/15, communities 103/104, venues 17/18, wastewater 16/16, refineries 7/7.
- 58 additional points with a known answer (`_parts/land2_checkpoints.json`: 32 GNIS water names and 12 GNIS landforms fetched 2026-11-11; plus NBI bridge points,
  CO-OPS gauges, a USACE GIWW centreline vertex and six road-centreline water crossings): **52 pass**. Changed from land to water by the overrides and now correct:
  Sunset Lake, Fresh Water Lake, Spears Lake, Salt Lake, Rincon Bayou, Oso Municipal Golf Course Lake (TIGER "Oso Lk" 1094130, NWI `PUBHh` — the one golf-course pond a source charts),
  the Nueces River at I-37, Oso Creek at S Staples St, Fish Pass at SH 361. Still correct: Oso Bay, Ward Island (TAMU-CC), Encinal Peninsula, the turning basins, La Quinta Channel, JFK Causeway, Harbor Bridge.
  The six misses, none caused by an override (all read the same in v1): GNIS "Egery Flats" (on land 55 m from water), GNIS "Calallen Reservoir" (25 m from the river polygon),
  CO-OPS 8775792 Packery Channel (4-decimal position, 25 m from water), NBI point of the northbound Nueces Bay Causeway (on Indian Point, 55 m from water),
  and GNIS "Little Shamrock Cove" / "Shamrock Island", whose GNIS coordinates sit 250-330 m off the harbour-chart outline of Shamrock Island (harbour band, not touched).
- Road centreline in "water": **v1 53.42 km of 8,351 km = 0.640 %; v2 55.72 km = 0.667 %; v3 55.62 km = 0.666 %.** 52.47 km of that has no land polygon at all
  (same in all versions); overrides account for 0.95 km (v1), 3.25 km (v2), 3.15 km (v3) — see 5. Runs of 100 m or more make up 52.7 km. The long ones:
  Nueces Bay Causeway (US 181 / SH 35, 2 x 2.43 km — the file carries the same road under three names, so it counts three times), Harbor Bridge (2 x 0.43 km),
  JFK Causeway / Park Road 22 bridges (1.3 km in six runs), Copano Bay causeway SH 35 (1.5 km inside the window) — real bridges. Not bridges: Egery Island Rd across Egery Flats (2.6 km),
  FM 136 there (0.9 km), Rattlesnake Point Rd (1.4 km), Copano Ridge Rd (1.4 km), FM 1781 (1.3 km), Ridge Harbor Dr (0.7 km) and four unnamed roads of 0.9-1.3 km
  (28.062N 97.187W, 27.987N 97.183W, 27.731N 97.165W, 28.046N 97.164W): real ground that the coastal-band chart leaves out (next section).
- `geo.py` raster agrees with the exact test on 99.44 % of 200,000 random points (25 m cells); land fraction of the window 0.5532 (v1), 0.5438 (v2), 0.5446 (v3).

### Expected accuracy by sub-area now

- **Harbour-band tiles** (ship channel corridor, Inner Harbor, CC Bay north of 27.75N, Nueces Bay south of 27.90N, La Quinta, Ingleside, Port Aransas, Aransas Pass,
  Redfish / Aransas Bay, Rockport, GIWW strip of the upper Laguna Madre): shoreline unchanged, **10-25 m**. Inland lakes and ponds inside those tiles are now present:
  charted lakes at chart accuracy, TIGER ponds at about **10-30 m**.
- **Coastal-band areas where an override now draws the shore** — Oso Bay / Cayo del Oso / Oso Creek, the Corpus Christi Bay shore from 27.75N down to the Naval Air Station,
  the Laguna Madre shore of Flour Bluff, the Nueces River above the delta, Port Bay, Swan Lake, the Copano Bay shore: water side at TIGER accuracy, about **10-50 m**.
- **Rest of the coastal band**: still **50-150 m**.

### What remains approximate

- **Overrides can only remove land.** Where the coastal-band chart omits real land, it still reads as water: the south shore of Copano Bay between 97.125W and 97.05W north of 28.05N
  (FM 1781, Copano Ridge Rd, Ridge Harbor Dr), Rattlesnake Point, the Egery Flats crossing, parts of the bay side of Mustang Island south of 27.75N — about 12 km of road centreline.
  Fixing that needs new land geometry in `land_local.geojson` (the abandoned `tiger_complement` idea), not overrides.
- **Not checked against NWI** (kept as fetched): 124 coastal-band TIGER lake/pond pieces that are small or more than 400 m from any road, 13 TIGER pieces and 46 charted lakes
  in harbour tiles that are remote (San Jose Island, Nueces delta) or confirmed by a second source, all 23 bay pieces, 19 stream pieces and 39 water blocks. Some of the remote
  lake/pond pieces are probably marsh or seasonal flats. `nwi_check` is null on them.
- The NWI lookup is one interior point per polygon (two or three for the eleven largest removals); a polygon that is part pond, part marsh is kept or dropped whole.
- Intertidal flats (NWI `E2US`) count as water, as in the chart: Sunset Lake, the flats behind Port Bay and at Ingleside (82914) can be dry ground at low water.
- Corpus Christi Bay (TIGER 440472) and Aransas Bay (902245) were never ingested; in the coastal band their shoreline is corrected only where a water-only census block covers it.
- Embankment causeways narrower than about 20 m between two water polygons read as water (FM 136 at Egery Flats); piers, docks and bridge decks read as water as before.
- The road along Sunset Lake (5) and the two Mustang Beach parking spots (3) are known "in water" positions that are data-side issues, not layer errors.
