# SOURCES — road centerlines (Corpus Christi area)

Fetched 2026-11-09. Every coordinate in the `roads_*.geojson` / `rail_port_corridor.geojson` files was returned by the server named below and transcribed digit-for-digit; nothing was estimated, interpolated or invented.

## Source

US Census Bureau **TIGERweb** ArcGIS REST service, `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer` — layer 2 Primary Roads, layer 6 Secondary Roads, layer 8 Local Roads, layer 9 Railroads. Public domain (US Government work).

## How it was fetched

- Only channel available: the `web_fetch` tool (`f=json`). The shell has no network. Responses were copied by hand (by the main agent and 8 sub-agents) into the part files under `_parts/`, then merged by `_parts/roads_build.py` and checked by `_parts/roads_verify.py`.
- Common parameters: `inSR=4326&outSR=4326&geometryPrecision=5&maxAllowableOffset=5e-5`.
- **Simplification:** `maxAllowableOffset=5e-5` degrees (about 5 m) applied server-side, coordinates rounded server-side to 5 decimals (about 1 m). Trailing zeros are stripped by the server. No further simplification was applied locally.
- Features are returned **whole**, not clipped to the query box, so files extend beyond their nominal boxes (e.g. I-37 runs to lat 28.15, SH 35 to 28.30, FM 624/FM 665 to lon -97.875).
- A TIGERweb feature is a whole named road, not a block-by-block edge. Cross streets meet a road at interior points that are often **not vertices** (and the 5 m simplification removes some). A router must node the network at geometric crossings, not only at endpoints.
- The web_fetch URL limit is about 250 characters and behaved erratically for `like '%25S...'` patterns; for the arterial name queries the geometry request carries `outFields=OID` only and NAME/MTFCC/RTTYP come from a paired attribute request (`returnGeometry=false`) joined on OID. A recorded arterial URL that is rejected for length returns the same features with the first letter of the pattern dropped (verified for `'%25taples+St'`).

## Output files

| File | Features | Vertices | Content |
|---|---|---|---|
| `roads_arterial.geojson` | 152 | 918 | Named arterial streets fetched by NAME from Local Roads layer 8 |
| `roads_local_calallen.geojson` | 124 | 522 | Every Local Roads (layer 8) feature intersecting the calallen box |
| `roads_local_downtown.geojson` | 151 | 463 | Every Local Roads (layer 8) feature intersecting the downtown box |
| `roads_local_flour_bluff.geojson` | 209 | 661 | Every Local Roads (layer 8) feature intersecting the flour_bluff box |
| `roads_local_hillcrest.geojson` | 87 | 308 | Every Local Roads (layer 8) feature intersecting the hillcrest box |
| `roads_local_interchange_ramps.geojson` | 71 | 225 | Ramps (layer 8, MTFCC S1630) at the SH358/SH44, I-37/SH358 and SH358/SH286 interchanges |
| `roads_local_molina.geojson` | 139 | 484 | Every Local Roads (layer 8) feature intersecting the molina box |
| `roads_local_north_beach.geojson` | 86 | 274 | Every Local Roads (layer 8) feature intersecting the north_beach box |
| `roads_local_port_aransas.geojson` | 198 | 640 | Every Local Roads (layer 8) feature intersecting the port_aransas box |
| `roads_major.geojson` | 362 | 3048 | Primary (layer 2) and Secondary (layer 6) roads intersecting lon -97.75..-96.95, lat 27.55..28.10; plus FM routes fetched by name from Local Roads layer 8 (source_layer=8) |
| `rail_port_corridor.geojson` | 61 | 308 | Railroads (layer 9) intersecting lon -97.55..-97.38, lat 27.78..27.86 (port corridor). NOT a road layer; class=rail |

Properties on every feature: `name` (TIGER NAME, may be null), `mtfcc`, `rttyp` (I/U/S/M/C/O or null), `class` (primary | secondary | arterial | local; `rail` in the rail file), `source_oid` (TIGER OID), `source_layer` (2/6/8/9). A road can appear in more than one file (an arterial that crosses a neighbourhood box is in both); de-duplicate on `source_oid` when loading several files. Unique totals across all road files: 1,503 features, 7,074 vertices, about 2,394 km (plus rail 61 features, 308 vertices).

Class rules: layer 2 → `primary`; layer 6 → `secondary`; FM routes fetched by name from layer 8 (TIGER files them as S1400 local roads, RTTYP O) are placed in `roads_major.geojson` as `secondary` with `source_layer` 8; streets fetched by name → `arterial`; everything from a neighbourhood box and the interchange ramps → `local`.

## Queries: server count vs written

### A. Major roads

| Part file(s) | Query URL | Server | Written |
|---|---|---|---|
| `roads_major_L2_all.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/2/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC,RTTYP&geometryPrecision=5&maxAllowableOffset=5e-5&f=json` | 47 | 47 |
| `roads_major_L6_U.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&where=RTTYP%3D'U'&f=json` | 39 | 39 |
| `roads_major_L6_S_p01.json`, `roads_major_L6_S_p02.json`, `roads_major_L6_S_p03.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&where=RTTYP%3D'S'&f=json` | 119 | 119 |
| `roads_major_L6_M_p01.json`, `roads_major_L6_M_p02.json`, `roads_major_L6_M_p03.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&where=RTTYP%3D'M'&f=json` | 118 | 118 |
| `roads_major_L6_C.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&where=RTTYP%3D'C'&f=json` | 3 | 3 |
| `roads_major_L6_O.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&where=RTTYP%3D'O'&f=json` | 8 | 8 |
| `roads_major_L6_I.json` | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/6/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&where=RTTYP%3D'I'&f=json` | 3 | 3 |

Layer 6 total in box (count query without `where`): 290 = 39+119+118+3+8+3; written 290. Count queries: same URLs with `returnCountOnly=true`.

FM routes from layer 8 (`roads_majorfill_FM_L8.json`): attribute list `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.75,27.55,-96.95,28.1&inSR=4326&where=NAME+like+'FM+%25'&outFields=OID,NAME,MTFCC,RTTYP&returnGeometry=false&f=json` (77 FM-named features in the box); geometry `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.8,27.5,-97,28.1&inSR=4326&outSR=4326&outFields=OID&geometryPrecision=5&maxAllowableOffset=5e-5&where=<W>&f=json` with `<W>` = `NAME+in('FM+43','FM+2444')`, `NAME+like+'FM+1069%25'`, `NAME+in('FM+893','FM+70')`, `NAME+like+'FM+27%25'`, `NAME+like+'FM+76%25'`, `NAME+like+'FM+18%25'`. Server returned 24 features, written 23. Not written: OID 110489577189 (matched `'FM 18%'` only in the slightly wider geometry box, lies west of lon -97.79, its NAME was not in the attribute list — left out rather than guess a name). FM 624 (OID 1106068777930) and FM 665 (OID 1102217726841) were returned whole by the Calallen/Molina box queries and are copied into `roads_major.geojson` from those parts.

### B. Named arterials (layer 8)

Two requests per street (attribute + geometry). Box `-97.7,27.5,-97,28.1` unless a town box is shown in the URL.

| Street | Geometry query (`where` / box) | Written feats | Vertices | NAMEs returned |
|---|---|---|---|---|
| Agnes St | `NAME+like+'%25Agnes+St'` / `-97.7,27.5,-97,28.1` | 9 | 59 | Agnes St |
| Airline Rd | `NAME+like+'%25Airline+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 7 | Airline Rd |
| Alameda St | `NAME+like+'%25Alameda+St'` / `-97.7,27.5,-97,28.1` | 6 | 30 | N Alameda St, S Alameda St |
| Ayers St | `NAME+like+'%25Ayers+St'` / `-97.7,27.5,-97,28.1` | 7 | 22 | Ayers St |
| Everhart Rd | `NAME+like+'%25Everhart+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 6 | Everhart Rd |
| Gollihar Rd | `NAME+like+'%25Gollihar+Rd'` / `-97.7,27.5,-97,28.1` | 2 | 13 | Gollihar Rd |
| Greenwood Dr | `NAME+like+'%25Greenwood+Dr'` / `-97.7,27.5,-97,28.1` | 1 | 23 | Greenwood Dr |
| Holly Rd | `NAME+like+'%25Holly+Rd'` / `-97.7,27.5,-97,28.1` | 4 | 30 | Holly Rd |
| Kostoryz Rd | `NAME+like+'%25Kostoryz+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 4 | Kostoryz Rd |
| Leopard St | `NAME+like+'%25Leopard+St'` / `-97.7,27.5,-97,28.1` | 7 | 31 | Leopard St |
| McArdle Rd | `NAME+like+'%25McArdle+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 7 | McArdle Rd |
| Morgan Ave | `NAME+like+'%25Morgan+Ave'` / `-97.7,27.5,-97,28.1` | 1 | 7 | Morgan Ave |
| Navigation Blvd | `NAME+like+'%25Navigation+Blvd'` / `-97.7,27.5,-97,28.1` | 3 | 45 | Navigation Blvd, S Navigation Blvd |
| Ocean Dr | `NAME+like+'%25Ocean+Dr'` / `-97.7,27.5,-97,28.1` | 7 | 60 | Ocean Dr |
| Old Brownsville Rd | `NAME+like+'%25Brownsville+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 17 | Old Brownsville Rd |
| Port Ave | `NAME+like+'%25Port+Ave'` / `-97.7,27.5,-97,28.1` | 6 | 26 | N Port Ave, Port Ave, S Port Ave |
| Rodd Field Rd | `NAME+like+'%25Rodd+Field+Rd'` / `-97.7,27.5,-97,28.1` | 2 | 6 | Rodd Field Rd |
| Santa Fe St | `NAME+like+'%25Santa+Fe+St'` / `-97.7,27.5,-97,28.1` | 2 | 11 | Santa Fe St |
| Saratoga Blvd | `NAME+like+'%25Saratoga+Blvd'` / `-97.7,27.5,-97,28.1` | 1 | 2 | Saratoga Blvd |
| Shoreline Blvd | `NAME+like+'%25Shoreline+Blvd'` / `-97.7,27.5,-97,28.1` | 10 | 37 | N Shoreline Blvd, S Shoreline Blvd |
| Staples St | `NAME+like+'%25Staples+St'` / `-97.7,27.5,-97,28.1` | 7 | 35 | N Staples St, S Staples St, Staples St |
| Up River Rd | `NAME+like+'%25Up+River+Rd'` / `-97.7,27.5,-97,28.1` | 11 | 79 | Up River Rd |
| Weber Rd | `NAME+like+'%25Weber+Rd'` / `-97.7,27.5,-97,28.1` | 4 | 17 | Weber Rd |
| Yorktown Blvd | `NAME+like+'%25Yorktown+Blvd'` / `-97.7,27.5,-97,28.1` | 2 | 22 | Yorktown Blvd |
| Access Rd 1A | `NAME+like+'%25Access%25'` / `-97.1,27.8,-97.03,27.86` | 1 | 2 | Beach Access Rd 1a |
| Alister St | `NAME+like+'%25Alister+St'` / `-97.1,27.8,-97.03,27.86` | 2 | 5 | N Alister St, S Alister St |
| Avenue G | `NAME+like+'%25Ave+G'` / `-97.1,27.8,-97.03,27.86` | 1 | 2 | E Ave G |
| Broadway St | `NAME+like+'%25roadway+St'` / `-97.1,27.98,-97.02,28.08` | 2 | 10 | Broadway St |
| Buddy Lawrence Dr | `NAME+like+'%25Lawrence+Dr'` / `-97.7,27.5,-97,28.1` | 1 | 8 | Buddy Lawrence Dr |
| Burleson St | `NAME+like+'%25Burleson+St'` / `-97.7,27.5,-97,28.1` | 3 | 11 | Burleson St |
| Callicoatte Rd | `NAME+like+'%25Callicoatte+Rd'` / `-97.7,27.5,-97,28.1` | 2 | 6 | Callicoatte Rd |
| Commercial St | `NAME+like+'%25mercial+St'` / `-97.2,27.87,-97.12,27.94` | 1 | 4 | N Commercial St |
| Cotter Ave | `NAME+like+'%25Cotter+Ave'` / `-97.1,27.8,-97.03,27.86` | 4 | 26 | Cotter Ave, E Cotter Ave, W Cotter Ave |
| Ennis Joslin Rd | `NAME+like+'%25Joslin+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 24 | Ennis Joslin Rd |
| Flour Bluff Dr | `NAME+like+'%25Flour+Bluff+Dr'` / `-97.7,27.5,-97,28.1` | 1 | 7 | Flour Bluff Dr |
| Laguna Shores Rd | `NAME+like+'%25Shores+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 22 | Laguna Shores Rd |
| Lexington Blvd | `NAME+like+'%25Lexington+Blvd'` / `-97.7,27.5,-97,28.1` | 6 | 17 | Lexington Blvd, N Lexington Blvd |
| Main St | `NAME+like+'%25Main+St'` / `-97.25,27.85,-97.18,27.9` | 7 | 45 | Main St, N Main St, S Main St, W Main St |
| McKinzie Rd | `NAME+like+'%25McKinzie+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 7 | McKinzie Rd |
| Moore Ave | `NAME+like+'%25Moore+Ave'` / `-97.36,27.85,-97.29,27.91` | 4 | 37 | Moore Ave |
| Nile Dr | `NAME+like+'%25Nile+Dr'` / `-97.7,27.5,-97,28.1` | 1 | 4 | Nile Dr |
| Nueces Bay Blvd | `NAME+like+'%25Nueces+Bay+Blvd'` / `-97.7,27.5,-97,28.1` | 1 | 3 | Nueces Bay Blvd |
| Surfside Blvd | `NAME+like+'%25Surfside+Blvd'` / `-97.7,27.5,-97,28.1` | 6 | 34 | Surfside Blvd, W Surfside Blvd |
| Timon Blvd | `NAME+like+'%25Timon+Blvd'` / `-97.7,27.5,-97,28.1` | 1 | 11 | Timon Blvd |
| Violet Rd | `NAME+like+'%25Violet+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 8 | Violet Rd |
| Waldron Rd | `NAME+like+'%25Waldron+Rd'` / `-97.7,27.5,-97,28.1` | 1 | 3 | Waldron Rd |
| Wheeler Ave | `NAME+like+'%25heeler+Ave'` / `-97.2,27.87,-97.12,27.94` | 4 | 11 | E Wheeler Ave, W Wheeler Ave |
| Wildcat Dr | `NAME+like+'%25ildcat+Dr'` / `-97.36,27.85,-97.29,27.91` | 2 | 15 | Wildcat Dr |

Server vs written: batch 1 (24 streets) 97/97; batch 2 (24 streets) 57 returned / 55 written — the two not written are "Daniel Moore Ave" in Portland (OIDs 1102219718850, 1102219718851), a different street matched by `'%Moore Ave'`. Full URLs are stored in each `_parts/roads_art*_{attr,geom}.json`.

Notes: `Avenue G` exists as "E Ave G"; `Access Rd 1A` as "Beach Access Rd 1a"; only "N Commercial St" exists in Aransas Pass in layer 8 (the rest of Commercial St is in layer 6). Lexington Blvd returned six features: three near the NAS gate (about -97.268, 27.69) and three "N Lexington Blvd" pieces near -97.47, 27.79 — all kept. Same-named streets in other towns inside the wide box were kept (e.g. Ocean Dr / Port Ave / Holly Rd in Rockport, Ayers St in Aransas Pass); they show up as small isolated pieces in the connectivity check. Central Leopard St, Saratoga Blvd (SH 357), Rodd Field Rd, Agnes St, Ayers St and Holly Rd pieces that TIGER classes as secondary are in `roads_major.geojson` (layer 6), not in the arterial file.

### C. Neighbourhood grids (layer 8, every feature intersecting the box)

Template: `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=<box>&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC,RTTYP&geometryPrecision=5&maxAllowableOffset=5e-5&f=json`

| Area | Requested box | Sub-boxes actually fetched | Server | Written (unique OID) |
|---|---|---|---|---|
| north_beach | `-97.395,27.815,-97.375,27.845` | `-97.395,27.815,-97.375,27.845` | 86 | 86 |
| hillcrest | `-97.425,27.8,-97.4,27.815` | `-97.425,27.8,-97.4,27.815` | 87 | 87 |
| molina | `-97.455,27.755,-97.43,27.775` | `-97.455,27.755,-97.43,27.775` | 139 | 139 |
| flour_bluff | `-97.32,27.655,-97.285,27.685` | `-97.32,27.67,-97.3025,27.685`; `-97.32,27.655,-97.3025,27.67`; `-97.3025,27.655,-97.285,27.67`; `-97.3025,27.67,-97.294,27.685`; `-97.294,27.67,-97.285,27.685` | 209 | 209 |
| calallen | `-97.64,27.855,-97.61,27.88` | `-97.64,27.855,-97.61,27.88` | 124 | 124 |
| port_aransas | `-97.085,27.82,-97.05,27.845` | `-97.085,27.8325,-97.0675,27.845`; `-97.085,27.82,-97.0675,27.8325`; `-97.0675,27.82,-97.05,27.8325`; `-97.0675,27.8325,-97.05,27.845` | 198 | 198 |
| downtown | `-97.405,27.785,-97.39,27.805` | `-97.405,27.785,-97.39,27.795`; `-97.405,27.795,-97.39,27.805` | 151 | 151 |

No box had to be shrunk. Downtown: 25 of its 151 features had already been transcribed for the Hillcrest box and are taken from those parts (OID list of the full downtown box: `_parts/roads_loc_downtown_oids.json`).

Interchange ramps (`roads_ramps_L8.json`, layer 8 `where=MTFCC='S1630'`, RTTYP null for all — checked with `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.476,27.733,-97.42,27.808&inSR=4326&where=MTFCC%3D'S1630'+and+RTTYP+is+not+null&outFields=OID,NAME,RTTYP&returnGeometry=false&f=json`):

| Interchange | URL | Server | Written |
|---|---|---|---|
| SH358_SH44 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.476,27.777,-97.464,27.787&inSR=4326&outSR=4326&outFields=OID,NAME&geometryPrecision=5&maxAllowableOffset=5e-5&where=MTFCC%3D'S1630'&f=json` | 24 | 24 |
| I37_SH358 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.476,27.798,-97.462,27.808&inSR=4326&outSR=4326&outFields=OID,NAME&geometryPrecision=5&maxAllowableOffset=5e-5&where=MTFCC%3D'S1630'&f=json` | 10 | 10 |
| SH358_SH286 | `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/8/query?geometry=-97.436,27.733,-97.42,27.746&inSR=4326&outSR=4326&outFields=OID,NAME&geometryPrecision=5&maxAllowableOffset=5e-5&where=MTFCC%3D'S1630'&f=json` | 37 | 37 |

### D. Railroads (layer 9, port corridor)

`https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/9/query?geometry=-97.55,27.78,-97.38,27.86&inSR=4326&outSR=4326&outFields=OID,NAME,MTFCC&geometryPrecision=5&maxAllowableOffset=5e-5&f=json` — server 61, written 61 (`rail_L9_port.json` → `rail_port_corridor.geojson`). Not a road layer; keep it out of road snapping.

## Verification (run 2026-11-09, `_parts/roads_verify.py`, plot `_parts/roads_check.png`)

- All files parse; all coordinates within lon -97.904..-96.946, lat 27.558..28.298 (whole features extend past the query boxes).
- Unique vertices / length by class: primary 47 feats, 789 vertices, 397 km; secondary 313 feats, 2,162 vertices, 1,200 km; arterial 152 feats, 918 vertices, 352 km; local 991 feats, 3,205 vertices, 445 km.
- Connectivity (features joined when their geometries pass within about 15 m anywhere along their length — not endpoint-only, because features are whole roads): major+arterial = 514 features, largest component 503 features = 99.4 % of length. Isolated pieces: FM 893 stub (2.0 km, near 27.955,-97.425), FM 70 west piece (5.5 km, 27.576,-97.720), N Alameda St (0.65 km, joins via downtown locals), Burleson St and N Shoreline Blvd on North Beach (join via North Beach locals), Callicoatte Rd stub (0.15 km), Wildcat Dr piece in Portland (0.8 km), and same-named streets in other towns: Ayers St (Aransas Pass), Holly Rd / Ocean Dr / Port Ave (Rockport). All road files together: 1,503 features, largest component 99.4 %.
- Spot checks (the test points were approximate): I-37 at Port Ave (27.797,-97.415) → 4 m from N Port Ave; SH 358 at Staples (27.7075,-97.3745) → 218 m from SH 358 (in the data S Staples St crosses the two SH 358 carriageways at 27.7076,-97.3700, i.e. the test point has the right latitude but sits about 440 m west of the crossing); JFK Causeway (27.635,-97.245) → 207 m from State Park Road 22 (the causeway feature ends at 27.63887,-97.24605 and continues as PR 22).
- Transcription checks: 48 features (293 vertices) were transcribed independently by two different agents from different responses — zero differences. Staples St (7 features, 35 vertices) was re-fetched afterwards and matches the part file digit-for-digit. Long-segment and spike scans found only legitimate geometry (straight rural stretches; turnaround loops). A full byte-for-byte diff against the server is not possible because responses never reach the disk.

## Skipped / limitations

- **Ramps and connectors** (TIGER MTFCC S1630, in layer 8) were fetched only for three interchanges (SH 358/SH 44, I-37/SH 358, SH 358/SH 286) and inside the seven neighbourhood boxes. The city box holds 525 ramp features; the rest were skipped for budget. Elsewhere freeway mainlines and cross streets simply cross each other without a connecting ramp.
- **Local streets** outside the seven boxes are not included (only the named arterials and the major roads).
- **Alias features kept:** TIGER carries the same alignment under several names/OIDs (SH 35 / US 181, Crosstown Fwy / SH 286, I-69E / US 77, SH 358 / S Padre Island Dr, PR 22 / JFK Cswy, Cotter Ave / E Cotter Ave ...). All were kept, so geometry is duplicated under different `source_oid`s; length totals above count them all.
- Layer 6 feature "I- -35 N" (OID 11015482079854, Rockport) is a TIGER naming glitch for Hwy 35 N; kept as returned.
- Other FM routes in the box (FM 630, 631, 136, 2046, 2986, 3036, 3089, 1781, 1944, 1945, 2165, 2292, 2512, 3239, 3284, 3354, 3386, 3512, 1694, 892, 1074, 1257, 2826, 22, 24, 796) were listed but their layer-8 geometry was not fetched, except where layer 6 already carries them.
- OSM / Overpass / Nominatim are unreachable from this environment and were not used.

