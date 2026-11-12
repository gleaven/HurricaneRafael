# SOURCES — full local street network (Corpus Christi area)

Fetched 2026-11-10. Every coordinate in `roads_local_all.geojson` was returned by the server named below and written by script from the saved server responses; nothing was typed by hand, estimated, interpolated or invented.

## Source

US Census Bureau **TIGERweb** ArcGIS REST service, `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8` — layer 8 **Local Roads** (layer description: "Local roads; January 1, 2026"). Public domain (US Government work). Same source and layer as the seven neighbourhood files of the first pass (`SOURCES_roads.md`).

## Area

Every layer-8 feature intersecting lon -97.70 .. -96.98, lat 27.55 .. 28.08 (Corpus Christi, Flour Bluff, Padre Island, Calallen/Annaville, Robstown, Portland, Gregory, Ingleside, Aransas Pass, Port Aransas, Rockport/Fulton). Features are returned **whole**, not clipped, so 1.4% of the vertices lie outside the box (overall extent lon -97.87520 .. -96.97183, lat 27.49218 .. 28.23861).

## Method

- Channel: the `web_fetch` tool only (the shell has no network). A response larger than about 50,000 characters is saved by the harness to a file and cut at about 67,300 characters of body. Each page was requested large enough to be saved; `_parts/streets_ingest.py` parses each saved file, keeps only the features that are complete before the cut (a feature is kept only if its closing brace is followed by `,` or `]`), and stores them in `_parts/streets_page_<offset>.json` together with the request URL. `_parts/streets_build.py` merges the pages into the GeoJSON.
- Paging: one query for the whole box, paged with `resultOffset` in the server's default order (no `orderByFields`; the URL limit of the tool, about 250 characters, left no room for it). Position in the server order = `resultOffset` + position in the page. Pages were requested with deliberate overlap; in every overlap the same position gave the same OID (0 mismatches over 38 pages), so the order is stable. The last page (`resultOffset=12441`) was placed so that the response was above the save threshold and below the cut; it ends with the closing `]` of the feature array (`complete_response: true`).
- Page URL (only `<N>` changes):

  `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.7,27.55,-96.98,28.08&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=3e-5&resultOffset=<N>&f=json`

- Count URL: `.../MapServer/8/query?geometry=<xmin>,<ymin>,<xmax>,<ymax>&inSR=4326&returnCountOnly=true&f=json`
- **Simplification:** `maxAllowableOffset=3e-5` degrees (about 3 m) and `geometryPrecision=5` (about 1 m), both applied by the server. No local simplification, rounding or snapping. Against the first-pass files (5e-5 simplification) the same OIDs deviate by at most 6.1 m.
- Fetch count: 38 feature pages used + 1 trial page (`resultOffset=12600`, came back inline and was not used for data; its last feature equals the last feature of the final page) + 1 whole-box count + 30 tile counts + 2 metadata requests (layer description, distinct MTFCC values).

## Output

`roads_local_all.geojson` — 3.3 MB, one file (no split needed).

| | |
|---|---|
| Features (LineString, one per TIGER feature; no multi-part features occurred) | 12,786 |
| Unique `source_oid` | 12,786 |
| Vertices | 49,778 |
| Length | 7,523.6 km |
| Named / unnamed (`name` null) | 8,966 / 3,820 |

Properties: `name` (TIGER NAME, may be null), `mtfcc`, `class`, `source_oid` (TIGER OID, same key as in the first-pass files), `source_layer` (8). `rttyp` was not fetched.

| class | MTFCC | Meaning | Features | Vertices | km |
|---|---|---|---|---|---|
| local | S1400 | Local neighbourhood road, rural road, city street | 11294 | 43456 | 6891.6 |
| local | S1630 | Ramp | 597 | 2259 | 154.2 |
| local | S1640 | Service drive | 98 | 704 | 167.5 |
| local | S1730 | Alley | 8 | 20 | 1.5 |
| local | S1740 | Private road | 581 | 2455 | 272.7 |
| local | S1780 | Parking-lot road | 143 | 528 | 21.2 |
| other | S1750 | Internal US Census Bureau use | 14 | 55 | 2.9 |
| track | S1500 | Vehicular trail (4WD) | 2 | 6 | 0.8 |
| walk | S1710 | Walkway / pedestrian trail | 49 | 295 | 11.2 |

Class rules: `local` = drivable (S1400, S1640, S1730, S1740 as requested; S1630 ramps and S1780 parking-lot roads were also in the layer and are tagged `local` because they are drivable — ramps follow the convention of `roads_local_interchange_ramps.geojson`; filter on `mtfcc` if the router should not use them). `track` = S1500. `walk` = S1710 (no S1720 stairways, S1820 or S1830 exist in the box). `other` = S1750 (14 features, 2.9 km; Census-internal class, not a confirmed public street — exclude from routing).

Overlap with the first pass: all 152 arterial features, all 1,065 features of the eight `roads_local_<area>.geojson` files and 24 of the 25 layer-8 FM routes in `roads_major.geojson` are in this file again under the same `source_oid` (de-duplicate on `source_oid` when loading several files; keep the arterial/secondary class from the earlier file). The one FM route not in this file is FM 70, OID 1104470259717, which lies west of this box (lon -97.88 .. -97.74).

## Server count vs written

Whole box: server `returnCountOnly` = **12,786**; fetched unique OIDs = **12,786**; written = **12,786**.

Per tile (6 x 5 tiles of 0.12 deg x 0.106 deg; "written" = features of the file whose geometry intersects the tile, computed by `_parts/streets_verify.py`; a feature that crosses tiles is counted in each, so the tile sum 13,420 exceeds 12,786):

| Tile (col_row) | Box xmin,ymin,xmax,ymax | Server | Written | |
|---|---|---|---|---|
| 0_0 | -97.7,27.55,-97.58,27.656 | 204 | 204 | equal |
| 1_0 | -97.58,27.55,-97.46,27.656 | 107 | 107 | equal |
| 2_0 | -97.46,27.55,-97.34,27.656 | 433 | 433 | equal |
| 3_0 | -97.34,27.55,-97.22,27.656 | 673 | 673 | equal |
| 4_0 | -97.22,27.55,-97.1,27.656 | 64 | 64 | equal |
| 5_0 | -97.1,27.55,-96.98,27.656 | 0 | 0 | equal |
| 0_1 | -97.7,27.656,-97.58,27.762 | 102 | 102 | equal |
| 1_1 | -97.58,27.656,-97.46,27.762 | 347 | 347 | equal |
| 2_1 | -97.46,27.656,-97.34,27.762 | 3057 | 3057 | equal |
| 3_1 | -97.34,27.656,-97.22,27.762 | 670 | 670 | equal |
| 4_1 | -97.22,27.656,-97.1,27.762 | 55 | 55 | equal |
| 5_1 | -97.1,27.656,-96.98,27.762 | 0 | 0 | equal |
| 0_2 | -97.7,27.762,-97.58,27.868 | 849 | 849 | equal |
| 1_2 | -97.58,27.762,-97.46,27.868 | 800 | 800 | equal |
| 2_2 | -97.46,27.762,-97.34,27.868 | 1233 | 1233 | equal |
| 3_2 | -97.34,27.762,-97.22,27.868 | 59 | 59 | equal |
| 4_2 | -97.22,27.762,-97.1,27.868 | 152 | 152 | equal |
| 5_2 | -97.1,27.762,-96.98,27.868 | 279 | 279 | equal |
| 0_3 | -97.7,27.868,-97.58,27.974 | 415 | 415 | equal |
| 1_3 | -97.58,27.868,-97.46,27.974 | 111 | 111 | equal |
| 2_3 | -97.46,27.868,-97.34,27.974 | 185 | 186 | diff +1 (see note) |
| 3_3 | -97.34,27.868,-97.22,27.974 | 569 | 569 | equal |
| 4_3 | -97.22,27.868,-97.1,27.974 | 805 | 805 | equal |
| 5_3 | -97.1,27.868,-96.98,27.974 | 60 | 60 | equal |
| 0_4 | -97.7,27.974,-97.58,28.08 | 109 | 109 | equal |
| 1_4 | -97.58,27.974,-97.46,28.08 | 526 | 526 | equal |
| 2_4 | -97.46,27.974,-97.34,28.08 | 266 | 266 | equal |
| 3_4 | -97.34,27.974,-97.22,28.08 | 139 | 139 | equal |
| 4_4 | -97.22,27.974,-97.1,28.08 | 165 | 165 | equal |
| 5_4 | -97.1,27.974,-96.98,28.08 | 986 | 986 | equal |

29 of 30 tiles are exactly equal. Tile 2_3 gives 186 locally against 185 on the server: two features (Poseidon Dr OID 11039093978678, Great Oak Dr OID 1107292850949) have an end vertex that the server's 5-decimal rounding put exactly on the tile edge lon -97.34000, so the local test counts as touching one feature that the server (using unrounded geometry) places just outside. No feature is missing or extra in the file: the whole-box counts are equal. With the tile grown/shrunk by 6 m the server count lies inside the local band for all 30 tiles. Two tiles are empty (open Gulf).

## Pages

| Part file | resultOffset | Complete features kept | Response ended |
|---|---|---|---|
| `streets_page_00000.json` | 0 | 382 | cut by the tool; tail re-fetched by the next page |
| `streets_page_00382.json` | 382 | 372 | cut by the tool; tail re-fetched by the next page |
| `streets_page_00700.json` | 700 | 386 | cut by the tool; tail re-fetched by the next page |
| `streets_page_01020.json` | 1020 | 363 | cut by the tool; tail re-fetched by the next page |
| `streets_page_01340.json` | 1340 | 372 | cut by the tool; tail re-fetched by the next page |
| `streets_page_01660.json` | 1660 | 391 | cut by the tool; tail re-fetched by the next page |
| `streets_page_01980.json` | 1980 | 359 | cut by the tool; tail re-fetched by the next page |
| `streets_page_02339.json` | 2339 | 370 | cut by the tool; tail re-fetched by the next page |
| `streets_page_02669.json` | 2669 | 352 | cut by the tool; tail re-fetched by the next page |
| `streets_page_02999.json` | 2999 | 371 | cut by the tool; tail re-fetched by the next page |
| `streets_page_03329.json` | 3329 | 383 | cut by the tool; tail re-fetched by the next page |
| `streets_page_03659.json` | 3659 | 385 | cut by the tool; tail re-fetched by the next page |
| `streets_page_03989.json` | 3989 | 373 | cut by the tool; tail re-fetched by the next page |
| `streets_page_04319.json` | 4319 | 381 | cut by the tool; tail re-fetched by the next page |
| `streets_page_04649.json` | 4649 | 384 | cut by the tool; tail re-fetched by the next page |
| `streets_page_05033.json` | 5033 | 378 | cut by the tool; tail re-fetched by the next page |
| `streets_page_05373.json` | 5373 | 384 | cut by the tool; tail re-fetched by the next page |
| `streets_page_05713.json` | 5713 | 378 | cut by the tool; tail re-fetched by the next page |
| `streets_page_06053.json` | 6053 | 367 | cut by the tool; tail re-fetched by the next page |
| `streets_page_06393.json` | 6393 | 364 | cut by the tool; tail re-fetched by the next page |
| `streets_page_06733.json` | 6733 | 379 | cut by the tool; tail re-fetched by the next page |
| `streets_page_07073.json` | 7073 | 357 | cut by the tool; tail re-fetched by the next page |
| `streets_page_07413.json` | 7413 | 385 | cut by the tool; tail re-fetched by the next page |
| `streets_page_07753.json` | 7753 | 371 | cut by the tool; tail re-fetched by the next page |
| `streets_page_08093.json` | 8093 | 357 | cut by the tool; tail re-fetched by the next page |
| `streets_page_08450.json` | 8450 | 374 | cut by the tool; tail re-fetched by the next page |
| `streets_page_08790.json` | 8790 | 374 | cut by the tool; tail re-fetched by the next page |
| `streets_page_09130.json` | 9130 | 380 | cut by the tool; tail re-fetched by the next page |
| `streets_page_09470.json` | 9470 | 389 | cut by the tool; tail re-fetched by the next page |
| `streets_page_09810.json` | 9810 | 375 | cut by the tool; tail re-fetched by the next page |
| `streets_page_10150.json` | 10150 | 379 | cut by the tool; tail re-fetched by the next page |
| `streets_page_10490.json` | 10490 | 379 | cut by the tool; tail re-fetched by the next page |
| `streets_page_10830.json` | 10830 | 379 | cut by the tool; tail re-fetched by the next page |
| `streets_page_11170.json` | 11170 | 381 | cut by the tool; tail re-fetched by the next page |
| `streets_page_11510.json` | 11510 | 371 | cut by the tool; tail re-fetched by the next page |
| `streets_page_11850.json` | 11850 | 388 | cut by the tool; tail re-fetched by the next page |
| `streets_page_12190.json` | 12190 | 370 | cut by the tool; tail re-fetched by the next page |
| `streets_page_12441.json` | 12441 | 345 | complete (closing bracket present) |

## Verification (`_parts/streets_verify.py`, output in `_parts/streets_verify_output.txt`, plot `_parts/streets_check.png`)

- Coordinates: all with at most 5 decimals; 98.6% of vertices inside the request box, the rest belong to whole features that leave it. Longest single segment 14.2 km (straight rural county road).
- First-pass files found again (by `source_oid`, and geometry within 10 m both ways): calallen 124/124, downtown 151/151, flour_bluff 209/209, hillcrest 87/87, interchange_ramps 71/71, molina 139/139, north_beach 86/86, port_aransas 198/198, arterial 152/152 — 100% of features and segments; worst deviation 6.1 m.
- Connectivity of `roads_major` + `roads_arterial` + `roads_local_all` (13,124 unique features, 8,988 km):
  - endpoints snapped to any other line within 12 m: largest component **98.58%** of length (105 components);
  - the same plus noding at geometric crossings: largest component **99.57%** of length (24 components; 58 features / 38.5 km outside).
  - Drivable classes only: 98.57% / 99.56%.
- Plot checked by eye: full street grids of Corpus Christi, Flour Bluff, Padre Island, Calallen/Annaville, Robstown, Portland, Gregory, Ingleside, Aransas Pass, Port Aransas and Rockport/Fulton plus the rural county-road grid.

Pieces not in the largest component after noding (largest first):

| km | Features | Centre lon, lat | Entirely inside box |
|---|---|---|---|
| 13.6 | 9 | -97.603, 27.559 | no (leaves the box; its connection is outside) |
| 6.4 | 3 | -97.312, 28.081 | no (leaves the box; its connection is outside) |
| 5.0 | 17 | -96.983, 27.950 | no (leaves the box; its connection is outside) |
| 2.1 | 1 | -97.508, 27.549 | no (leaves the box; its connection is outside) |
| 1.8 | 2 | -97.180, 27.971 | yes |
| 1.7 | 1 | -97.520, 27.548 | no (leaves the box; its connection is outside) |
| 1.2 | 1 | -97.379, 28.080 | no (leaves the box; its connection is outside) |
| 1.1 | 3 | -97.432, 27.649 | yes |
| 1.1 | 1 | -97.559, 27.809 | yes |
| 1.1 | 1 | -97.702, 27.652 | no (leaves the box; its connection is outside) |
| 1.0 | 1 | -97.690, 27.549 | no (leaves the box; its connection is outside) |
| 0.6 | 1 | -97.534, 28.025 | yes |
| ... | 11 smaller pieces, 1.7 km in total | | |

The piece near lon -96.98, lat 27.95 is on San Jose Island (no road link to the mainland in reality). Pieces at the south and north edges are roads whose junctions lie outside the box.

## Notes for the router

- A TIGERweb feature is a whole named road, not a block-by-block edge. Cross streets meet it at interior points that are often **not vertices**. Node the network at geometric crossings and snap dangling endpoints (12 m is enough for 99.6% connectivity); endpoint snapping alone gives 98.6%.
- Noding at crossings also joins roads at grade-separated crossings (a local street passing under a freeway). The data carries no level information; use the S1630 ramps to get on and off the primary roads if that matters.
- Port Aransas is in the largest component (linked along Mustang Island by SH 361 from `roads_major.geojson`). Whether the ferry crossing to Harbor Island is represented as a road feature was not checked.

## Missing / limits

- Nothing known to be missing inside the box: the server count and the written count are equal, as a whole and per tile (one edge-rounding difference explained above).
- Not included: roads entirely outside the box (e.g. FM 70 west of -97.74; Bayside/Refugio County north of 28.08; Kingsville/Kleberg County south of 27.55; Sinton centre is inside).
- Primary and secondary roads (layers 2 and 6) are not in this file; they are in `roads_major.geojson` (first pass, 5e-5 simplification).
- `rttyp` not fetched; block-level address ranges are not part of this layer.
- TIGER vintage is January 1, 2026; private and unnamed features (S1740, null names) are as TIGER has them.

## Files

- `roads_local_all.geojson`
- `_parts/streets_ingest.py`, `_parts/streets_build.py`, `_parts/streets_verify.py`
- `_parts/streets_page_00000.json` ... `_parts/streets_page_12441.json` (38 parsed server pages, each with its URL), `_parts/streets_progress.json`
- `_parts/streets_tile_counts.json` (server counts), `_parts/streets_tile_check.json`, `_parts/streets_verify_output.txt`, `_parts/streets_check.png`
