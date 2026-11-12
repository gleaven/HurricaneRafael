# SOURCES — navigation channels, centerlines, anchorage, fairways

Fetch date: **2026-11-09** (all queries). Fetched through the `web_fetch` tool (sandbox shell has no network).
All coordinates are WGS84 lon/lat exactly as returned by the servers (5 decimals, `geometryPrecision=5`). No coordinate was invented, estimated, moved or interpolated. Only two kinds of processing were applied: ring order reversed to GeoJSON (RFC 7946) winding, and Esri multi-ring polygons split into MultiPolygon where the server returned several outer rings.

Files (in this folder):

| File | Content | Features |
|---|---|---|
| `channels_usace.geojson` | USACE channel reach polygons (toe-to-toe channel footprint) | 37 |
| `channel_lines_usace.geojson` | USACE channel centerlines | 35 |
| `anchorages_fairways_noaa.geojson` | NOAA ENC anchorage + fairway polygons (simplified ~50 m) | 20 |
| `_parts/` | part files as fetched (`reach_p*.json`, `line_p*.json`, `noaa_p*.json`, `reach_attributes.json`, `reach_server_shape_stats.json`), raw saved server responses (`raw_server_responses/`), build/verify scripts (`scripts/`), check plot (`channels_check.png`) | |

---

## Source 1 — USACE National Channel Framework (authoritative)

`NCF = https://services7.arcgis.com/n1YM8pTrFmm7L4hs/ArcGIS/rest/services/National_Channel_Framework/FeatureServer`

Layers: 0 ChannelLine, 1 ChannelArea, 2 ChannelReach, 3 ChannelQuarter. SR 4326. Copyright text on the layer: "US Army Corps of Engineers Mobile District Operations Division Spatial Data Branch". Source dataset recorded on every feature: `NCF_CESWG_DIS_TEXAS_SOUTH_20261020.ZIP` (GIWW reach 20: `..._TEXAS_SOUTH_CENTRAL_20261020.ZIP`), uploaded 2026-10-20, Galveston District (CESWG), original projection NAD83 State Plane Texas South (ft).

Search box used for discovery: lon −97.60…−96.90, lat 27.55…28.10 (`BOX = geometry=-97.6,27.55,-96.9,28.1`).

### Layer 2 — ChannelReach polygons → `channels_usace.geojson`

Counts (server `returnCountOnly`) vs written:

| Query | Server count | Written |
|---|---|---|
| `NCF/2/query?where=channelreachidpk+like+'CESWG_CC_%25'&returnCountOnly=true&f=pjson` | 16 | 16 |
| `NCF/2/query?where=1%3D1&BOX&inSR=4326&returnCountOnly=true&f=pjson` | 37 | 37 |

All 16 Corpus Christi reaches are inside the box, so the file holds 37 reaches in 7 projects:

| Project (`sdsfeaturename`) | Reaches | Mile span summed |
|---|---|---|
| CORPUS CHRISTI (`CESWG_CC_*`) | 16 | main channel mile 0 → 36.39 (15 reaches, contiguous) + barge lane `CC_6A` mile 17–27 (two shelves either side of reach 06) |
| LA QUINTA (`CESWG_LA_*`) incl. La Quinta Extension | 3 | 0 → 7.11 |
| GULF INTRACOASTAL WATERWAY (`CESWG_GI_*`): 20, 21, 22, 23 (main route mile 511.9 → 565.12) and 21a/21b (Lydia Ann alternate, 0 → 11.8) | 6 | 65.02 |
| ARANSAS_PASS (`CESWG_AP_*`) incl. Conn Brown Harbor | 4 | 7.09 |
| RINCON_CANAL (`CESWG_RC_*`) | 4 | 4.18 |
| CHANNEL_TO_PORT_ARANSAS (`CESWG_AR_*`) | 3 | 0.52 |
| JEWEL_FULTON (`CESWG_JF_*`) | 1 | 0.87 |

Sum of all reach mile spans: 131.18 mi (121.18 without the overlapping barge lane).

Attribute queries (no geometry):
- `NCF/2/query?where=1%3D1&BOX&inSR=4326&outFields=channelreachidpk,sdsfeaturedescription&returnGeometry=false&f=json`
- `NCF/2/query?where=channelreachidpk+like+'CESWG_CC_%25'&outFields=channelreachidpk,sdsfeaturedescription&returnGeometry=false&f=json`
- `NCF/2/query?BOX&inSR=4326&outFields=channelreachidpk,channelareaidfk,sdsfeaturename&returnGeometry=false&f=json`
- `NCF/2/query?BOX&inSR=4326&outFields=channelreachidpk,mileagestart,mileageend&returnGeometry=false&f=json`
- `NCF/2/query?BOX&inSR=4326&outFields=channelreachidpk,depthmaintained,widthfrom,widthto&returnGeometry=false&f=json`
- `NCF/2/query?BOX&inSR=4326&outFields=channelreachidpk,Shape__Area,Shape__Length&returnGeometry=false&f=json` (checksum)

Geometry queries, one per id prefix `X` (transcribed by hand into `_parts/reach_p01..p16.json`):
`NCF/2/query?where=channelreachidpk+like+'X%25'&outFields=channelreachidpk&geometryPrecision=5&f=json`
with X = `CESWG_CC_01` … `CESWG_CC_15` (15 queries), `CESWG_CC_6A`, `CESWG_LA_01`, `CESWG_LA_02`, `CESWG_LA_03`, `CESWG_RC_0` (4 features), `CESWG_AR_0` (3), `CESWG_JF_0` (1), `CESWG_AP_01`, `CESWG_AP_02`, `CESWG_AP_03`, `CESWG_AP_04`, `CESWG_GI_1A`, `CESWG_GI_1B`, `CESWG_GI_20`, `CESWG_GI_21`, `CESWG_GI_22`, `CESWG_GI_23`. Total 37 features returned, 37 written.

Machine verification queries (responses too large for the tool, so they were saved to disk untouched by the model, then parsed by script; copies in `_parts/raw_server_responses/`):
- `NCF/2/query?BOX&outFields=*&geometryPrecision=5&f=json`
- `NCF/2/query?BOX&outFields=*&geometryPrecision=5&orderByFields=OBJECTID+DESC&f=json`
- `NCF/2/query?BOX&outFields=*&geometryPrecision=5&orderByFields=channelreachidpk&f=json`

Each saved response is truncated by the tool at ~63 k characters, but the three orderings together contain every one of the 37 features complete. Result: **37/37 hand-transcribed reach geometries and 37/37 attribute rows are identical, digit for digit, to the machine-saved server output.**

Properties written: `reach_id, area_id, description, project, mile_start, mile_end, depth_ft` (= `depthmaintained`), `width_from_ft, width_to_ft`, plus `depth_authorized_ft, reported_length_mi, reach_type, source, source_objectid, source_dataset`.

Things to know about this layer:
- Sea Bar Channel (`CC_01`) starts at lon −96.9628 / lat 27.7940 (mile 0) with 56 ft maintained depth; the rest of the main channel is 54 ft. The server holds no reach seaward of that point.
- `CESWG_CC_6A_LQB_6` (barge lane, 12 ft) is a MultiPolygon: two separate strips north and south of reach 06. It is not part of the deep-draft channel.
- Reaches are channel-bottom (toe) extents. Berths, docks and slips outside the federal channel are not included.
- GIWW reach 20 runs north to lat 28.13 and reach 23 south to lat 27.476 (outside the discovery box but returned whole, kept whole).

### Layer 0 — ChannelLine → `channel_lines_usace.geojson`

Layer fields checked with `NCF/0?f=pjson`. `channellinetype` has three values in this area (`NCF/0/query?BOX&inSR=4326&outFields=channellinetype&returnDistinctValues=true&returnGeometry=false&f=json`):
- **CenterLine** — channel centerline, one (sometimes two) per channel area, id = `channellineidpk` = area id. **Collected.**
- **StationLine** — cross-channel station tick lines (49 for the Corpus Christi Inner Harbor areas 08–15; `stationlinevalue` is null). Not collected.
- **ToeLine** — channel toe (edge) lines; same information as the reach polygon outlines. Not collected.

| Query | Server count | Written |
|---|---|---|
| `NCF/0/query?BOX&inSR=4326&returnCountOnly=true&f=json` (all line types) | 663 | — |
| `NCF/0/query?where=channelareaidfk+like+'CESWG_CC_%25'&returnCountOnly=true&f=json` (these are the StationLines) | 49 | 0 (not collected) |
| `NCF/0/query?where=channellinetype+like+'%25enter%25'&BOX&inSR=4326&returnCountOnly=true&f=json` (CenterLines) | 35 | 35 |

Other queries:
- `NCF/0/query?where=channelareaidfk+like+'CESWG_CC_%25'&outFields=channellinetype,channelareaidfk,stationlinevalue&returnGeometry=false&f=json`
- `NCF/0/query?where=channellinetype+like+'Cen%25'&BOX&outFields=*&returnGeometry=false&resultRecordCount=2&f=json`
- `NCF/0/query?where=channellinetype+like+'C%25'&BOX&outFields=channellineidpk&returnGeometry=false&f=json`
- Geometry, per prefix X: `NCF/0/query?where=channellineidpk+like+'X%25'+and+channellinetype<'D'&outFields=channellineidpk&geometryPrecision=5&f=json` with X = `CESWG_CC_0`, `CESWG_CC_1`, `CESWG_LA_0`, `CESWG_RC_0`, `CESWG_A` (also returned two Anahuac lines at lon −94.7, discarded as outside the area), `CESWG_JF`, `CESWG_GI_1A`, `CESWG_GI_1B`, `CESWG_GI_20`, `CESWG_GI_21`, `CESWG_GI_22`, `CESWG_GI_23`.
- `NCF/0/query?where=channellinetype<'D'&BOX&outFields=*&geometryPrecision=5&f=json`
- Machine verification (full precision, saved to disk, copies in `_parts/raw_server_responses/`): `NCF/0/query?where=channellinetype<'D'&BOX&outFields=*&orderByFields=OBJECTID&f=json` and the same with `orderByFields=OBJECTID+DESC`. Result: **35/35 transcribed centerlines equal the server geometry rounded to 5 decimals.**

Centerline inventory (35): Corpus Christi 14 (areas 01–09, 12 ×2, 13, 14, 15), GIWW 6, Aransas Pass 4, Rincon 4, La Quinta 3, Port Aransas 3, Jewel Fulton 1.

Things to know:
- There is **no centerline** for `CC_10` (Avery Point Turning Basin), `CC_11` (Chemical Turning Basin) or `CC_6A` (barge lane). The second `CESWG_CC_12_TLC` line runs east from the Tule Lake Channel through the Chemical Turning Basin and ends at −97.43112, 27.82195; the `CC_09` line ends at −97.43193, 27.82032. That leaves a real ~200 m break in the centerline across the Avery Point turning basin (the reach polygons are continuous there).
- Corpus Christi centerlines total 58.4 km = 36.26 statute miles, matching the 36.39 mi reach mileage.
- `CESWG_AP_04_CBH` on the server has three paths, one of which is a stray ~1 m segment at −97.02634, 28.0033 (in Aransas Bay, 14 km from Conn Brown Harbor). It is a source artefact; it is omitted from the GeoJSON (noted in that feature's `note` property) and kept in `_parts/line_p04.json`.
- Some lines carry repeated consecutive vertices exactly as served; they were not removed.
- Line direction is as served and is not consistent (some run seaward, some landward).

---

## Source 2 — NOAA ENC Direct to GIS → `anchorages_fairways_noaa.geojson`

`ENC = https://encdirect.noaa.gov/arcgis/rest/services/encdirect`
Services: `enc_coastal` (1:150,001–1:600,000), `enc_approach`, `enc_harbour`. "Not intended for navigation purpose" (service description). The server intermittently answers `{"error":{"code":500,"message":"...Could not find service..."}}` for a layer that works seconds later; failed calls were repeated with a slightly different box.

Layer lists read from `ENC/enc_approach/MapServer?f=pjson`, `ENC/enc_coastal/MapServer?f=pjson`, `ENC/enc_harbour/MapServer?f=pjson`.

All geometry was requested with `maxAllowableOffset=0.0005&geometryPrecision=5` (server-side simplification, about 50 m). Query box `B1 = geometry=-97.3,27.5,-96.5,28.1&inSR=4326` (also −97.31 as retry), offshore box `B2 = geometry=-97.045,27.6,-96.5,28.0&inSR=4326`.

| Layer | Query | Server count | Written |
|---|---|---|---|
| Coastal Anchorage_Area (132) | `ENC/enc_coastal/MapServer/132/query?where=1%3D1&B1&returnCountOnly=true&f=json` | 1 | 1 — "Aransas Pass Anchorage Area", 33 CFR 166.200, cell US3TX1CB |
| Coastal Fairway_area (150) | `.../enc_coastal/MapServer/150/query?...B1...` | 8 | 8 — incl. "Aransas Pass Channel" fairway and "East-West Gulf of America Fairway" |
| Harbour Anchorage_Area (186) | `.../enc_harbour/MapServer/186/query?...B1...` | 4 | 4 — "Fairway anchorage, 33 CFR 166.200" (pieces clipped at ENC cell edges) |
| Harbour Fairway_area (208) | `.../enc_harbour/MapServer/208/query?...B2...` | 8 | 7 (1 excluded, see below) |
| Harbour Fairway_area (208), whole box B1 | count only | 87 | not collected (in-bay fairway pieces; USACE reaches cover them) |
| Harbour Dredged_Area (228) | count only, B1 / B2 | 211 / 22 | **0 — not collected** |
| Approach Fairway_area (213) | count, B1 | 0 (layer has 922 features nationally) | 0 |
| Approach Dredged_Area (233) | count, B1 | 0 | 0 |
| Approach Anchorage_Area (191) | count, B1 | server error on every attempt (3) | 0 |
| Coastal Dredged_Area (167) | count, B1 | 0 | 0 |
| Pilot boarding place: Approach point (61), Approach area (188), Coastal point (47), Coastal area (130), Harbour point (57), Harbour area (183) | count, B1 | **0 in all six** (Harbour point layer has 62 features nationally, none here) | 0 |
| Coastal Anchorage_Area_point (53) | count, B1 | 0 | 0 |

Geometry queries:
- `ENC/enc_coastal/MapServer/132/query?where=1%3D1&B1&outSR=4326&outFields=*&maxAllowableOffset=0.0005&geometryPrecision=5&f=json`
- `ENC/enc_coastal/MapServer/150/query?where=1%3D1&B1&outSR=4326&outFields=OBJECTID,OBJNAM,DSNM&maxAllowableOffset=0.0005&geometryPrecision=5&f=json`
- `ENC/enc_harbour/MapServer/186/query?where=1%3D1&geometry=-97.31,27.5,-96.5,28.1&inSR=4326&outSR=4326&outFields=OBJECTID,OBJNAM,DSNM,INFORM&maxAllowableOffset=0.0005&geometryPrecision=5&f=json`
- `ENC/enc_harbour/MapServer/208/query?where=1%3D1&geometry=-97.045,27.6,-96.5,28.01&inSR=4326&outSR=4326&outFields=OBJECTID,OBJNAM,DSNM&maxAllowableOffset=0.0005&geometryPrecision=5&f=json`

Properties written: `kind` (anchorage | fairway), `name` (ENC OBJNAM, often null), `source_layer`, `source_objectid`, `enc_cell`, `simplified_deg`, and `inform/sorind/sordat` where fetched.

Things to know:
- These 20 polygons were transcribed by hand from small inline responses and were **not** machine-verified against a saved copy (unlike the USACE data). They pass ring-closure and plot checks; total 146 vertices.
- Fairway and anchorage features are returned whole when they intersect the box, so several extend far outside the local area (to lat 26.4 and lon −96.0). They were not clipped.
- The coastal-band anchorage is one polygon; the harbour-band anchorage is the same regulated area at larger scale, cut into four pieces at ENC cell boundaries (straight edges at lon −96.975 / −96.9 and lat 27.825 / 27.75 are cell edges, not regulatory limits). Use one band or the other, not both.
- Excluded from the GeoJSON, kept in `_parts/noaa_p03.json`: harbour fairway OBJECTID 44184 "Gulf Intracoastal Waterway" — the 50 m simplification collapses this ~38 m wide channel into a self-touching sliver.

---

## Could NOT get / gaps

1. **Pilot boarding place** — no feature in any ENC Direct band (approach, coastal, harbour; point and area layers) inside the box. Not written. Nothing was substituted.
2. **Approach-band anchorage** (`enc_approach` layer 191) — server error on every attempt; the approach band returned 0 for every other layer queried here, so it probably has no data for this area.
3. **NOAA dredged areas** — present at harbour scale (211 in the box) but not collected; `kind = dredged` does not occur in the file. The USACE reach polygons are the dredged-channel footprint.
4. **In-bay ENC harbour fairway pieces** (79 of 87) not collected.
5. **USACE StationLine and ToeLine** features (628 of 663 lines in the box) not collected.
6. **USACE layers 1 (ChannelArea) and 3 (ChannelQuarter)** not collected.
7. No USACE reach exists seaward of Sea Bar Channel mile 0, and none for private berths/slips.
8. A reach named "Channel to Rockport/Fulton" or "Channel to Port Ingleside" does not exist in the box under those names; the box query returned exactly the 7 projects listed above.

## Verification performed (scripts in `_parts/scripts/`)

- Every file parses; 0 unclosed rings; 0 wrong ring orientations.
- USACE reaches and centerlines: all vertices inside lon −98…−96.5 / lat 27…28.5. NOAA: 29 of 146 vertices outside that window (whole offshore fairways, see above).
- Feature counts equal server counts (tables above).
- Consecutive Corpus Christi reaches ordered by `mile_start`: all 14 joins have gap 0.0 m and matching mile values (mile 0 → 36.39). Branch joins (La Quinta, Jewel Fulton, Rincon, Aransas Pass, Port Aransas, GIWW) are 0–28 m (boundary to boundary) from the reach they leave; the GIWW 21/22 junction lies inside reach 05, 54 m from its edge.
- Polygon area and perimeter computed from the transcription agree with the server `Shape__Area` / `Shape__Length` within rounding (perimeter within 0.35 %).
- Plot: `_parts/channels_check.png` — one continuous channel from the Gulf through the jetties and Port Aransas, across the bay to the Inner Harbor (Viola Turning Basin), La Quinta branching north, GIWW crossing at lon −97.19.
