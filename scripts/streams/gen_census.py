"""Census tract tables (stream: census), aligned with 06_data_streams/areas.json.

    python3 scripts/streams/gen_census.py

Writes
  05_other_sources/census/acs_nueces_tracts.csv   ACS-style 5-year estimates, one row per tract
  05_other_sources/census/nueces_tract_index.csv  tract index: names, area ids, evacuation zone, water district

The tract table is synthetic ACS-style data: geography ids follow the Census GEOID pattern for
Nueces County (48355), but the values are invented for the exercise and are not Census Bureau
estimates. Population, income, poverty and Hispanic-origin values are taken from areas.json
(which was built from the first version of this table), so the two always agree. This generator
adds the columns the equity and language-access comparisons need (households with no vehicle,
residents who speak English less than very well) and each tract's water district.
"""
import csv
import os

from common import ROOT, reg, rng, write_csv, retire

OLD = os.path.join(ROOT, "_versions", "streams_pre_regen_20261109", "05_other_sources", "census", "acs_nueces_tracts.csv")
CUR = os.path.join(ROOT, "05_other_sources", "census", "acs_nueces_tracts.csv")

# Share of residents (5 years and over) in Water Districts 3 and 4 who speak English less than
# very well (canon: about 46.7 percent).
LEP_D3_D4 = 0.467
PAD = 0.0025


def water_district(area, districts):
    """Primary water district of a tract: the district whose box holds the tract's reference
    point. Districts 3 and 4 are tested first because their notice area is what canon defines."""
    if not area.get("reference_point"):
        return ""
    lat, lon = area["reference_point"]["latitude"], area["reference_point"]["longitude"]
    order = sorted(districts, key=lambda d: 0 if d["area_id"] in ("AREA-WD-3", "AREA-WD-4") else 1)
    for d in order:
        b = d["bbox"]
        if b[0] - PAD <= lon <= b[2] + PAD and b[1] - PAD <= lat <= b[3] + PAD:
            return d["area_id"]
    return ""


def main():
    areas = reg("areas")["areas"]
    tracts = sorted((a for a in areas if a["area_type"] == "census_tract"), key=lambda a: a["tract"])
    districts = [a for a in areas if a["area_type"] == "water_district"]

    # the first table's remaining ACS columns are carried over unchanged
    if not os.path.exists(OLD):
        retire(["05_other_sources/census/acs_nueces_tracts.csv", "05_other_sources/census/nueces_tract_index.csv"])
    with open(OLD, encoding="utf-8", newline="") as fh:
        old = {r["TRACT"]: r for r in csv.DictReader(fh)}

    wd = {t["tract"]: water_district(t, districts) for t in tracts}
    rows, lep_raw = [], {}
    for t in tracts:
        r = rng("census", t["tract"])
        pop = t["population"]
        hisp = t["hispanic_or_latino"] / pop
        inc = t["median_household_income"]
        low = max(0.0, min(1.0, (60000 - inc) / 32000))          # 0 rich .. 1 poor
        lep_raw[t["tract"]] = max(0.03, 0.55 * hisp * (0.45 + 0.75 * low) + r.normal(0, 0.012))
    # scale the Districts 3 and 4 tracts so that their pooled share is the canon figure
    d34 = [t for t in tracts if wd[t["tract"]] in ("AREA-WD-3", "AREA-WD-4")]
    pop5 = {t["tract"]: int(round(t["population"] * 0.93)) for t in tracts}
    cur = sum(lep_raw[t["tract"]] * pop5[t["tract"]] for t in d34) / sum(pop5[t["tract"]] for t in d34)
    for t in d34:
        lep_raw[t["tract"]] = min(0.72, lep_raw[t["tract"]] * LEP_D3_D4 / cur)
    # second pass: clipping can leave the pooled share a little low
    for _ in range(4):
        cur = sum(lep_raw[t["tract"]] * pop5[t["tract"]] for t in d34) / sum(pop5[t["tract"]] for t in d34)
        for t in d34:
            lep_raw[t["tract"]] = min(0.72, lep_raw[t["tract"]] * LEP_D3_D4 / cur)

    header = ["GEOID", "NAME", "STATE", "COUNTY", "TRACT", "B01003_001E", "B01002_001E", "B19013_001E", "B17001_002E",
              "B03003_003E", "B08301_001E", "B25077_001E", "B25003_002E", "B25003_003E", "B15003_022E", "B27001_001E",
              "B25002_003E", "B01003_001EA", "POP_DENSITY", "PREF_EVAC_ZONE",
              "B08201_001E", "B08201_002E", "S1601_C01_001E", "S1601_C05_001E"]
    for t in tracts:
        o = old[t["tract"]]
        r = rng("census-hh", t["tract"])
        pop, inc = t["population"], t["median_household_income"]
        low = max(0.0, min(1.0, (60000 - inc) / 32000))
        households = int(o["B25003_002E"]) + int(o["B25003_003E"])
        if households < pop / 4.2:                                # first table under-counted occupied units
            households = int(round(pop / (2.55 + 0.5 * low)))
        no_vehicle = int(round(households * max(0.02, 0.035 + 0.21 * low ** 1.5 + r.normal(0, 0.008))))
        lep = int(round(lep_raw[t["tract"]] * pop5[t["tract"]]))
        rows.append([o["GEOID"], o["NAME"], o["STATE"], o["COUNTY"], t["tract"], pop, o["B01002_001E"], int(inc),
                     t["persons_below_poverty"], t["hispanic_or_latino"], o["B08301_001E"], o["B25077_001E"],
                     o["B25003_002E"], o["B25003_003E"], o["B15003_022E"], o["B27001_001E"], o["B25002_003E"],
                     o["B01003_001EA"], o["POP_DENSITY"], t["evacuation_zone"],
                     households, no_vehicle, pop5[t["tract"]], lep])
    n1 = write_csv("05_other_sources/census/acs_nueces_tracts.csv", header, rows)

    notes = {"A": "Highest coastal surge risk; mandatory evacuation zone A", "B": "Low-lying coastal area; mandatory evacuation zone B",
             "C": "Below 10 feet of elevation or mobile homes; mandatory evacuation zone C", "D": "Minimal surge risk; inland or rural zone D"}
    idx = [[t["tract"], t["geoid"], t["area_id"], t["neighbourhood_name"], t["evacuation_zone"], "AREA-EVAC-" + t["evacuation_zone"],
            wd[t["tract"]], t["population"],
            round(t["reference_point"]["latitude"], 5) if t.get("reference_point") else "",
            round(t["reference_point"]["longitude"], 5) if t.get("reference_point") else "",
            notes[t["evacuation_zone"]]] for t in tracts]
    n2 = write_csv("05_other_sources/census/nueces_tract_index.csv",
                   ["TRACT", "GEOID", "AREA_ID", "NEIGHBORHOOD_NAME", "EVAC_ZONE", "EVAC_ZONE_AREA_ID", "WATER_DISTRICT_AREA_ID",
                    "POP_EST", "REF_LATITUDE", "REF_LONGITUDE", "NOTES"], idx)
    d34pop = sum(pop5[t["tract"]] for t in d34)
    d34lep = sum(int(round(lep_raw[t["tract"]] * pop5[t["tract"]])) for t in d34)
    print(f"census: {n1} tracts, index {n2} rows; Districts 3 and 4: {len(d34)} tracts, "
          f"{sum(t['population'] for t in d34):,} residents, LEP share {d34lep / d34pop:.3f}")


if __name__ == "__main__":
    main()
