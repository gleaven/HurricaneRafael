"""Health streams: emergency department line list, hospital capacity, syndromic summary, wastewater.

    python3 scripts/streams/gen_health.py              all
    python3 scripts/streams/gen_health.py wastewater   one (ed | wastewater)   (ed writes line list, capacity and summary)

Visits are built from components that follow 00_scenario/canon_timeline.json (health, power):
an ordinary baseline, the storm trauma wave, complaints near the oiled shorelines, the citywide
stomach-illness wave, the Districts 3 and 4 cluster, and the slower recovery of the low-income
surge-zone tracts. Counts canon states exactly are met exactly. Deterministic.
"""
import datetime as dt
import glob
import math
import os
import sys
from collections import defaultdict

import numpy as np

from common import (D0_EPOCH, SPAN_END, SPAN_START, ROOT, day_of, internal, iso, local_dt, local_ts, reg, retire, rng,
                    write_csv)

FIRST_DAY, LAST_DAY = -30, 119
D0_DATE = dt.date(2027, 9, 14)


def ddate(d):
    return D0_DATE + dt.timedelta(days=d)


# ---------------------------------------------------------------------------------------
# reference tables
# ---------------------------------------------------------------------------------------
TRACT_ZIP = {"480101": "78402", "480201": "78401", "480301": "78401", "480401": "78407", "480501": "78408", "480601": "78373",
             "480701": "78373", "480801": "78418", "480901": "78418", "481001": "78410", "481101": "78404", "481201": "78405",
             "481301": "78407", "481401": "78405", "481501": "78404", "481601": "78408", "481701": "78416", "481801": "78411",
             "481901": "78418", "482001": "78418", "482101": "78412", "482201": "78415", "482301": "78412", "482401": "78406",
             "482501": "78410", "482601": "78410", "482701": "78380", "482801": "78410", "482901": "78380", "483001": "78380",
             "483101": "78415", "483201": "78411", "483301": "78412", "483401": "78416", "483501": "78413", "483601": "78415",
             "483701": "78410", "483801": "78409", "483901": "78414", "484001": "78413", "484101": "78418", "484201": "78380",
             "484301": "78380", "484401": "78380", "484501": "78410", "484601": "78380", "484701": "78415", "484801": "78380",
             "484901": "78409", "485001": "78410", "485101": "78417", "485201": "78415", "485301": "78418", "485401": "78418",
             "485501": "78414", "485601": "78418"}
OUT_ZIPS = {"78374": (27.8876, -97.3240, 20500), "78362": (27.8700, -97.2100, 10300), "78336": (27.9072, -97.1566, 9200),
            "78382": (28.0300, -97.0600, 12000), "78359": (27.9220, -97.2900, 2000)}       # San Patricio / Aransas counties
D34_ZIPS = {"78405", "78416", "78417", "78401", "78407", "78408"}
SHORELINE_TRACTS = {"480101", "480201", "480301", "480401", "480501", "481301"}
SHORELINE_ZIPS = {"78374"}
IRRITANT_TRACTS = {"481301": 5, "480401": 3, "480501": 3, "480101": 2, "481601": 2, "480201": 1}
OUT_SHARE = {"SRMC": 0.06, "BCMC": 0.04, "LPMC": 0.02, "SCMH": 0.02, "FPCH": 0.03, "GCCH": 0.10, "ABCH": 0.86}
REACH_KM = {"SRMC": 12.0, "BCMC": 8.0, "LPMC": 6.0, "SCMH": 5.5, "FPCH": 6.0, "GCCH": 16.0, "ABCH": 9.0}
SURGE_SHARE = {"SRMC": 0.46, "BCMC": 0.26, "LPMC": 0.09, "GCCH": 0.06, "FPCH": 0.05, "SCMH": 0.05, "ABCH": 0.03}
HOUR_W = np.array([1.6, 1.3, 1.1, 1.0, 1.0, 1.2, 1.8, 2.8, 3.9, 4.8, 5.4, 5.7, 5.7, 5.6, 5.5, 5.5, 5.6, 5.8, 5.9, 5.7, 5.0, 4.1, 3.1, 2.3])

MIX = {"INJURY": .17, "RESP": .11, "CARD": .09, "ABD": .09, "MSK": .09, "NEURO": .065, "FEVER": .05, "GU": .05, "MH": .045,
       "SKIN": .035, "ENT": .035, "OB": .028, "GI": .019, "MEDS": .010, "HEAT": .008, "RENAL": .006, "IRRITANT": .002,
       "CO": .0004}
MIX["OTHER"] = 1.0 - sum(MIX.values())
PEDS_MIX = {"FEVER": .22, "RESP": .20, "INJURY": .19, "ENT": .09, "ABD": .07, "SKIN": .05, "GI": .019, "NEURO": .03, "MH": .03,
            "IRRITANT": .002, "HEAT": .006, "CO": .0004}
PEDS_MIX["OTHER"] = 1.0 - sum(PEDS_MIX.values())

CC = {
    "GI": ["vomiting and diarrhea x2 days", "n/v/d since last night", "diarrhea, abd cramps", "vomiting, unable to keep fluids down",
           "watery diarrhea x3d, weak", "nausea vomiting", "dehydration, diarrhea", "stomach bug per pt", "abd cramping, loose stools",
           "vomiting x6 today", "diarrhea x4 days, dizzy when standing", "n/v, family members also sick"],
    "GI_ES": ["diarrea y vomito x2 dias", "vomito y diarrea, debil", "dolor de estomago y diarrea", "diarrea, no tolera liquidos",
              "vomito desde anoche", "diarrea x3 dias, mareo"],
    "RESP": ["sob", "cough x3d", "asthma exacerbation", "wheezing", "copd flare", "difficulty breathing", "cough, congestion",
             "chest tightness, cough", "sob, out of inhaler", "cough, wheeze x2d"],
    "SKIN": ["rash both arms", "skin irritation hands and forearms", "cellulitis L leg", "itching, rash", "wound infection foot",
             "blisters hands", "rash legs after wading", "red itchy skin, was at shoreline", "infected cut R shin"],
    "IRRITANT": ["burning eyes and throat, strong odor at home", "headache, nausea, petroleum smell outside",
                 "eye irritation, chemical smell in neighborhood", "throat irritation x1d, odor from channel",
                 "dizzy, fumes in neighborhood", "headache and cough, oil smell since yesterday", "nausea, odor complaint, lives near port"],
    "INJURY": ["fall, wrist pain", "mvc, neck pain", "laceration finger", "ankle sprain", "head injury, fall", "back pain after lifting",
               "dog bite hand", "fall at home, hip pain", "foot injury", "assault, facial pain"],
    "INJ_CRUSH": ["crush injury leg, debris", "crush injury arm, wall collapse", "pinned under fallen tree, leg"],
    "INJ_DROWN": ["near drowning, pulled from flood water", "submersion, flood water, coughing"],
    "INJ_LAC": ["laceration forearm, sheet metal", "puncture wound foot, nail", "chainsaw laceration thigh", "laceration scalp, glass",
                "laceration hand clearing debris", "puncture wound, stepped on nail in flood water"],
    "INJ_FX": ["fall from ladder, wrist deformity", "fall from roof, hip pain", "ankle deformity, slipped on debris",
               "arm deformity, struck by door in wind", "rib pain after fall"],
    "INJ_STORM": ["struck by debris, shoulder", "eye injury, flying debris", "burn hand, generator", "electrical shock, downed line",
                  "back injury moving debris", "head injury, struck by branch", "foot wound, wading in flood water",
                  "smoke inhalation, candle fire", "mvc, traffic signals out"],
    "CO": ["headache, nausea, generator running indoors", "found confused, generator in garage", "dizziness, family of 4, generator on porch",
           "headache and vomiting, charcoal grill indoors"],
    "HEAT": ["heat exhaustion, no power at home", "dizzy, dehydrated, working outside", "syncope, heat", "cramps, weakness, no ac x3d"],
    "RENAL": ["missed dialysis x2", "dialysis pt, sob, missed treatment", "fluid overload, dialysis center closed", "weakness, missed dialysis"],
    "CARD": ["chest pain", "palpitations", "chest pressure, diaphoretic", "htn, headache", "chf exacerbation, leg swelling", "chest pain x2h"],
    "NEURO": ["headache", "dizziness", "stroke symptoms, facial droop", "seizure", "syncope", "numbness L arm"],
    "ABD": ["abdominal pain", "rlq pain", "flank pain", "epigastric pain", "abd pain x2d"],
    "MSK": ["back pain", "knee pain", "shoulder pain", "neck pain", "hip pain"],
    "FEVER": ["fever x2d", "fever, body aches", "flu like symptoms", "fever, sore throat", "fever, cough"],
    "MH": ["anxiety", "suicidal ideation", "panic attack", "insomnia, stress", "alcohol intoxication", "depression, lost home"],
    "GU": ["dysuria", "uti symptoms", "kidney stone pain", "urinary retention"],
    "OB": ["pregnant, cramping", "vaginal bleeding, 10 wks", "pregnant, decreased fetal movement"],
    "ENT": ["ear pain", "sore throat", "dental pain", "eye redness"],
    "MEDS": ["needs medication refill, pharmacy closed", "out of insulin", "oxygen concentrator, no power", "lost medications in flood",
             "needs bp meds refill"],
    "OTHER": ["weakness", "allergic reaction", "wound check", "suture removal", "generalized weakness", "abnormal labs", "leg swelling"],
}
DX = {
    "GI": ["A09", "K52.9", "R11.2", "R19.7", "E86.0"], "RESP": ["J45.901", "J44.1", "J06.9", "R06.02", "J18.9"],
    "SKIN": ["L03.115", "L23.9", "R21", "L08.9"], "IRRITANT": ["J68.9", "R51.9", "H57.8", "R11.0", "J39.2"],
    "INJURY": ["S61.419A", "S52.501A", "S93.401A", "S06.0X0A", "T14.90XA"], "INJ_CRUSH": ["S87.80XA", "S77.10XA", "S47.9XXA"],
    "INJ_DROWN": ["T75.1XXA"], "INJ_LAC": ["S51.819A", "S91.339A", "S71.119A", "S01.01XA"], "INJ_FX": ["S52.501A", "S72.009A", "S82.899A", "S22.39XA"],
    "INJ_STORM": ["T14.90XA", "S05.00XA", "T23.009A", "T75.4XXA", "S39.012A", "S09.90XA"], "CO": ["T58.11XA"], "HEAT": ["T67.5XXA", "T67.1XXA", "E86.0"],
    "RENAL": ["N18.6", "Z91.15", "E87.70"], "CARD": ["R07.9", "I10", "I50.9", "R00.2"], "NEURO": ["R51.9", "R42", "I63.9", "G40.909", "R55"],
    "ABD": ["R10.9", "R10.31", "N23", "K35.80"], "MSK": ["M54.50", "M25.561", "M25.511"], "FEVER": ["R50.9", "J11.1", "J02.9"],
    "MH": ["F41.9", "R45.851", "F10.129", "F43.0"], "GU": ["N39.0", "N20.0", "R33.9"], "OB": ["O20.0", "O26.899"],
    "ENT": ["H66.90", "K08.89", "H10.9", "J02.9"], "MEDS": ["Z76.0"], "OTHER": ["R53.1", "T78.40XA", "Z48.02", "R60.0"],
}
ADMIT = {"CARD": .28, "NEURO": .20, "RESP": .16, "GI": .10, "RENAL": .60, "CO": .30, "HEAT": .12, "INJURY": .08, "INJ_CRUSH": .90,
         "INJ_DROWN": .85, "INJ_LAC": .10, "INJ_FX": .45, "INJ_STORM": .22, "ABD": .12, "FEVER": .06, "MH": .12, "SKIN": .08}
HEADER = ["Visit_ID", "Facility_ID", "Facility_Name", "Patient_Class", "Visit_Date", "Arrive_Date_Time", "Arrival_Mode",
          "Triage_Acuity_ESI", "Chief_Complaint_Text", "CC_Category", "Age", "Age_Group", "Sex", "Race_Ethnicity",
          "Preferred_Language", "Patient_ZIP", "Patient_Tract", "Onset_Date", "Disposition", "Discharge_Diagnosis_ICD10",
          "Facility_County"]
SYN_HEADER = ["Report_Date", "Facility_ID", "Area_ID", "CC_Category", "Visit_Count", "Admitted_Count"]
CAT_OF = {"INJ_CRUSH": "INJURY", "INJ_DROWN": "INJURY", "INJ_LAC": "INJURY", "INJ_FX": "INJURY", "INJ_STORM": "INJURY"}


class World:
    def __init__(self):
        fac = [f for f in reg("facility_registry")["facilities"] if f["facility_type_code"] == "HOSP-ED"]
        self.fac = {f["facility_name_abbrev"]: f for f in fac}
        areas = reg("areas")["areas"]
        self.tracts = {a["tract"]: a for a in areas if a["area_type"] == "census_tract"}
        self.plc010 = set(t.split("-")[-1] for t in internal("areas")["truth"]["PLC-010"]["members"])
        codes = sorted(self.tracts)
        self.homes = [("T", c) for c in codes] + [("Z", z) for z in sorted(OUT_ZIPS)]
        pop = np.array([self.tracts[c]["population"] for c in codes] + [OUT_ZIPS[z][2] for z in sorted(OUT_ZIPS)], float)
        self.pop = pop
        self.n_in = len(codes)
        self.home_zip = [TRACT_ZIP[c] for c in codes] + sorted(OUT_ZIPS)
        self.hisp = np.array([self.tracts[c]["hispanic_or_latino"] / self.tracts[c]["population"] for c in codes] + [0.42, 0.38, 0.45, 0.28, 0.6])
        self.zone = [self.tracts[c].get("evacuation_zone", "D") for c in codes] + ["A"] * len(OUT_ZIPS)
        zref = {a["zip"]: a["reference_point"] for a in areas if a["area_type"] == "zip" and a.get("reference_point")}

        def ref(c):                                   # rural tracts have no point of their own: use their ZIP's
            return self.tracts[c].get("reference_point") or zref.get(TRACT_ZIP[c]) or {"latitude": 27.74, "longitude": -97.62}
        lat = np.array([ref(c)["latitude"] for c in codes] + [OUT_ZIPS[z][0] for z in sorted(OUT_ZIPS)])
        lon = np.array([ref(c)["longitude"] for c in codes] + [OUT_ZIPS[z][1] for z in sorted(OUT_ZIPS)])
        self.pf = {}
        for ab, f in self.fac.items():
            d = np.hypot((lat - f["latitude"]) * 111.0, (lon - f["longitude"]) * 98.0)
            w = pop * np.exp(-d / REACH_KM[ab])
            w_in, w_out = w[:self.n_in].copy(), w[self.n_in:].copy()
            w_in *= (1 - OUT_SHARE[ab]) / w_in.sum()
            w_out *= OUT_SHARE[ab] / w_out.sum()
            self.pf[ab] = np.concatenate([w_in, w_out])
        self.idx = {h: i for i, h in enumerate(self.homes)}
        base = {ab: f["ed_baseline_visits_per_day"] for ab, f in self.fac.items()}
        self.base = base
        # expected baseline visits a day by home (all facilities)
        self.home_rate = sum(base[ab] * self.pf[ab] for ab in base)
        self.is_d34 = np.array([z in D34_ZIPS for z in self.home_zip])
        self.is_shore = np.array([(k == "T" and c in SHORELINE_TRACTS) or (k == "Z" and c in SHORELINE_ZIPS) for k, c in self.homes])
        self.is_plc010 = np.array([k == "T" and c in self.plc010 for k, c in self.homes])
        zw = {"A": 3.0, "B": 2.0, "C": 1.0, "D": 0.6}
        self.surge_w = np.array([zw.get(z, 0.6) for z in self.zone]) * (1 + 0.3 * self.is_plc010)


W = None


def world():
    global W
    if W is None:
        W = World()
    return W


# ---------------------------------------------------------------------------------------
# visit construction
# ---------------------------------------------------------------------------------------
def pick_home(w, ab, g, mask=None, weights=None):
    p = w.pf[ab].copy()
    if weights is not None:
        p = p * weights
    if mask is not None:
        p = p * mask
    if p.sum() <= 0:
        p = w.pf[ab].copy()
    return int(g.choice(len(p), p=p / p.sum()))


def age_for(cat, ab, g, cluster=False):
    if ab == "GCCH":
        return int(min(17, abs(g.gamma(1.6, 3.6))))
    if cluster:
        r = g.random()
        return int(g.integers(0, 12)) if r < 0.24 else (int(g.integers(65, 94)) if r < 0.60 else int(g.integers(18, 65)))
    if cat in ("CARD", "RENAL"):
        return int(min(96, max(22, g.normal(63, 14))))
    if cat in ("FEVER", "ENT"):
        return int(min(90, abs(g.gamma(1.4, 14))))
    if cat == "OB":
        return int(g.integers(17, 42))
    if cat in ("INJURY", "MH", "HEAT", "CO") or cat.startswith("INJ_"):
        return int(min(92, max(2, g.gamma(3.2, 12))))
    return int(min(97, max(0, g.gamma(2.6, 16))))


def age_group(a):
    return "0-4" if a < 5 else "5-17" if a < 18 else "18-44" if a < 45 else "45-64" if a < 65 else "65+"


def make_visit(w, g, ab, day, cat, hour=None, home=None, lang_es=None, admit_p=None, esi=None, mode=None, dx=None,
               cluster=False, forced_disp=None):
    """Return a dict for one visit. cat may be a storm-injury subtype (INJ_*)."""
    h = int(g.choice(24, p=HOUR_W / HOUR_W.sum())) if hour is None else hour
    t = local_ts(day, f"{h:02d}:{int(g.integers(0, 60)):02d}") + int(g.integers(0, 60))
    hi = pick_home(w, ab, g) if home is None else home
    kind, code = w.homes[hi]
    hisp = g.random() < w.hisp[hi]
    p_es = (0.42 * w.hisp[hi]) if lang_es is None else lang_es
    spanish = g.random() < p_es
    if spanish:
        hisp = True
    race = "Hispanic" if hisp else str(g.choice(["Non-Hispanic White", "Non-Hispanic Black", "Asian", "Other"], p=[0.72, 0.18, 0.05, 0.05]))
    a = age_for(cat, ab, g, cluster)
    pool = CC[cat]
    if cat == "GI" and spanish and g.random() < 0.6:
        pool = CC["GI_ES"]
    text = str(pool[int(g.integers(0, len(pool)))])
    pub_cat = CAT_OF.get(cat, cat)
    ap = ADMIT.get(cat, 0.07) if admit_p is None else admit_p
    if a >= 70 and admit_p is None:
        ap = min(0.9, ap * 1.7)
    r = g.random()
    disp = forced_disp or ("Admitted" if r < ap else "Transferred" if r < ap + 0.02 else "Left without being seen" if r < ap + 0.045 else "Discharged")
    if esi is None:
        esi = 2 if disp == "Admitted" and g.random() < 0.55 else int(g.choice([2, 3, 4, 5], p=[0.08, 0.44, 0.36, 0.12]))
    if mode is None:
        mode = "EMS" if (esi <= 2 and g.random() < 0.55) or g.random() < 0.09 else "Walk-in"
    diag = dx or str(DX[cat][int(g.integers(0, len(DX[cat])))])
    onset_back = int(g.choice([0, 1, 2, 3], p=[0.45, 0.33, 0.15, 0.07])) if pub_cat in ("GI", "RESP", "FEVER", "SKIN", "IRRITANT") else 0
    return {"t": t, "ab": ab, "day": day, "cat": pub_cat, "text": text, "age": a, "sex": "F" if g.random() < 0.52 else "M",
            "race": race, "lang": "Spanish" if spanish else "English", "zip": w.home_zip[hi], "tract": code if kind == "T" else "",
            "mode": mode, "esi": esi, "disp": disp, "dx": diag, "onset": ddate(day - onset_back).isoformat(), "home": hi}


def volume_factor(ab, d):
    f = {-3: 0.94, -2: 0.84, -1: 0.62, 1: 0.85, 2: 0.90, 3: 0.95}.get(d, 1.0)
    if ab == "ABCH":
        f = {-1: 0.3, 0: 0.1, 1: 0.3, 2: 0.5, 3: 0.8}.get(d, f)
    wd = ddate(d).weekday()
    f *= {0: 1.05, 5: 0.98, 6: 0.99}.get(wd, 1.0)
    if d >= 78:
        f *= 1.04 + 0.04 * min(1.0, (d - 78) / 30.0)
    return f


def cat_mult(cat, d):
    if cat == "HEAT":
        return 1.6 if d < -14 else 1.2 if d < 17 else 0.6 if d < 48 else 0.1
    if cat in ("FEVER", "RESP") and d >= 78:
        return 1.3 + 0.3 * min(1.0, (d - 78) / 30.0)
    if cat == "GI":
        return {5: 1.5, 14: 2.3, 15: 1.9, 16: 1.6, 17: 1.4, 18: 1.25, 19: 1.15, 20: 1.1}.get(d, 2.8 if 6 <= d <= 13 else 1.0)
    return 1.0


SURGE_TOTAL = {1: 430, 2: 520, 3: 450, 4: 360, 5: 290, 6: 230, 7: 170, 8: 110, 9: 70, 10: 45, 11: 30, 12: 20, 13: 12, 14: 6}
SURGE_CATS = [("INJ_LAC", .18), ("INJ_FX", .10), ("INJ_CRUSH", .02), ("INJ_DROWN", .01), ("INJ_STORM", .15), ("CO", .05),
              ("HEAT", .07), ("RENAL", .06), ("CARD", .09), ("RESP", .04), ("MH", .06), ("MEDS", .10), ("SKIN", .015), ("OTHER", .045)]
GI_TARGET = {"SRMC": {16: 59, 17: 140, 18: 216, 19: 219, 20: 218, 21: 220, 22: 217, 23: 176, 24: 136, 25: 94, 26: 63, 27: 38, 28: 12, 29: 9, 30: 6},
             "BCMC": {16: 33, 17: 78, 18: 121, 19: 123, 20: 122, 21: 124, 22: 120, 23: 99, 24: 76, 25: 52, 26: 34, 27: 20, 28: 6, 29: 5, 30: 3}}
GI_HALF = {"SRMC": {14: (5, 6), 15: (8, 9)}, "BCMC": {14: (2, 3), 15: (5, 5)}}       # (before noon, from noon) local
GI_HALF_D34 = {"SRMC": {(14, 1): 4, (15, 0): 6}, "BCMC": {(14, 1): 2, (15, 0): 4}}    # how many of those live in Districts 3-4
IRRITANT_EXTRA = {2: 9, 3: 14, 4: 11, 5: 7, 6: 3, 7: 1}


def cluster_visit(w, g, ab, d, hour=None, force_d34=None):
    in_d34 = (g.random() < 0.943) if force_d34 is None else force_d34
    mask = w.is_d34 if in_d34 else ~w.is_d34
    hi = pick_home(w, ab, g, mask=mask.astype(float), weights=(w.pop / w.pf[ab].clip(1e-9)) if in_d34 else None)
    es = 0.68 if d <= 16 else 0.50 if d == 17 else 0.36
    dx = None
    if d >= 18:
        r = g.random()
        dx = "A07.2" if r < 0.38 else ("A07.1" if r < 0.50 else None)
    return make_visit(w, g, ab, d, "GI", hour=hour, home=hi, lang_es=es, admit_p=0.665, dx=dx, cluster=True,
                      mode=("EMS" if g.random() < 0.18 else "Walk-in"))


def build_visits():
    w = world()
    visits = []
    for d in range(FIRST_DAY, LAST_DAY + 1):
        for ab in w.fac:
            g = rng("ed_visits", ab, d)
            base = w.base[ab]
            mix = PEDS_MIX if ab == "GCCH" else MIX
            # ---------------- the landfall day at the two surge hospitals
            if d == 0 and ab == "SRMC":
                visits += srmc_landfall_day(w, g)
                continue
            n_exp = base * volume_factor(ab, d) * (0.5 if d == 0 else 1.0)
            for cat, share in mix.items():
                if cat == "GI" and ab in GI_TARGET and (d in GI_TARGET[ab] or d in GI_HALF[ab]):
                    continue
                lam = n_exp * share * cat_mult(cat, d)
                for _ in range(int(g.poisson(lam))):
                    visits.append(make_visit(w, g, ab, d, cat))
            # ---------------- GI at the two hospitals while canon gives numbers
            if ab in GI_TARGET:
                if d in GI_HALF[ab]:
                    for half, n in enumerate(GI_HALF[ab][d]):
                        n34 = GI_HALF_D34[ab].get((d, half))
                        for k in range(n):
                            hour = int(g.integers(0, 12)) + 12 * half
                            if n34 is not None:
                                visits.append(cluster_visit(w, g, ab, d, hour=hour, force_d34=(k < n34)))
                            elif d == 15 and g.random() < 0.8:
                                visits.append(cluster_visit(w, g, ab, d, hour=hour))
                            else:
                                visits.append(make_visit(w, g, ab, d, "GI", hour=hour))
                elif d in GI_TARGET[ab]:
                    target = GI_TARGET[ab][d]
                    ordinary = min(target, int(round(base * 0.019 * cat_mult("GI", d))))
                    for _ in range(ordinary):
                        visits.append(make_visit(w, g, ab, d, "GI"))
                    for _ in range(target - ordinary):
                        visits.append(cluster_visit(w, g, ab, d))
            # ---------------- storm trauma wave
            if d == 0:
                n = {"BCMC": 46, "LPMC": 12, "GCCH": 6, "FPCH": 7, "SCMH": 7, "ABCH": 1}[ab]
                for _ in range(n):
                    cat = str(g.choice([c for c, _ in SURGE_CATS[:5]], p=np.array([s for _, s in SURGE_CATS[:5]]) / sum(s for _, s in SURGE_CATS[:5])))
                    hi = pick_home(w, ab, g, weights=w.surge_w)
                    visits.append(make_visit(w, g, ab, d, cat, home=hi, hour=int(g.integers(5, 24))))
            elif d in SURGE_TOTAL:
                n = int(g.poisson(SURGE_TOTAL[d] * SURGE_SHARE[ab]))
                cats = [(c, s) for c, s in SURGE_CATS if not (c == "INJ_DROWN" and d > 2) and not (c == "CO" and d > 8) and not (c == "SKIN" and d < 4)]
                p = np.array([s for _, s in cats]); p /= p.sum()
                for _ in range(n):
                    cat = cats[int(g.choice(len(cats), p=p))][0]
                    hi = pick_home(w, ab, g, weights=w.surge_w)
                    visits.append(make_visit(w, g, ab, d, cat, home=hi))
        # ---------------- components drawn by home area, then sent to a hospital
        g = rng("ed_visits", "areas", d)
        send = lambda hi: str(g.choice(list(w.fac), p=np.array([w.base[a] * w.pf[a][hi] for a in w.fac]) / sum(w.base[a] * w.pf[a][hi] for a in w.fac)))
        # complaints near the oiled shorelines: +60% respiratory and skin, D+3 to D+21
        if 3 <= d <= 25:
            ramp = 1.0 if d <= 21 else (26 - d) / 5.0
            for hi in np.where(w.is_shore)[0]:
                lam = 0.52 * ramp * w.home_rate[hi] * (MIX["RESP"] + MIX["SKIN"])
                for _ in range(int(g.poisson(lam))):
                    cat = "RESP" if g.random() < 0.7 else "SKIN"
                    visits.append(make_visit(w, g, send(hi), d, cat, home=int(hi)))
        # odour, eye and throat irritation downwind of the channel
        if d in IRRITANT_EXTRA:
            keys = list(IRRITANT_TRACTS)
            p = np.array([IRRITANT_TRACTS[k] for k in keys], float); p /= p.sum()
            for _ in range(IRRITANT_EXTRA[d]):
                hi = w.idx[("T", keys[int(g.choice(len(keys), p=p))])]
                visits.append(make_visit(w, g, send(hi), d, "IRRITANT", home=hi, hour=int(g.integers(9 if d == 2 else 6, 24)), admit_p=0.03))
        # slower recovery in the low-income surge-zone tracts
        if 8 <= d <= 85:
            lvl = 0.4 if d <= 50 else 0.4 * (85 - d) / 35.0
            cats = ["CARD", "MH", "INJURY", "MEDS", "ABD", "OTHER", "NEURO", "MSK", "GU", "FEVER"]
            for hi in np.where(w.is_plc010)[0]:
                for _ in range(int(g.poisson(lvl * w.home_rate[hi]))):
                    visits.append(make_visit(w, g, send(hi), d, cats[int(g.integers(0, len(cats)))], home=int(hi)))
    # two tug crew hurt in the explosion at the jetties (06:10Z on 28 Oct) are landed at the Port Aransas harbor and go by ambulance
    # to the hospital the dispatch record names (911 incident of 06:46Z, transported to FAC-BCMC-002, units clear 08:10Z)
    gt = rng("ed_visits", "tug-crew")
    for k, (when, text, dx, esi, disp, age) in enumerate([("2027-10-28T07:44:40Z", "burns face and forearms, explosion on tug", "T20.20XA", 2, "Admitted", 41),
                                                          ("2027-10-28T07:52:15Z", "ear pain, lacerations arm, thrown against rail, explosion on boat", "S09.21XA", 3, "Discharged", 29)]):
        v = make_visit(w, gt, "BCMC", 44, "INJ_STORM", hour=1, esi=esi, mode="EMS", dx=dx, forced_disp=disp, lang_es=0.0)
        v.update({"t": tsz(when), "text": text, "age": age, "sex": "M"})
        visits.append(v)
    # ambulance arrivals on the landfall day as dispatch recorded them: 44 to SRMC (all before 18:00), 28 to BCMC
    for v in visits:
        if v["day"] == 0 and v["ab"] == "SRMC" and local_dt(v["t"]).hour >= 18:
            v["mode"] = "Walk-in"
    bc = sorted([v for v in visits if v["day"] == 0 and v["ab"] == "BCMC"], key=lambda v: (v["esi"], v["t"]))
    for k, v in enumerate(bc):
        v["mode"] = "EMS" if k < 28 else "Walk-in"
    return visits


def srmc_landfall_day(w, g):
    """Canon: 118 patients by 18:00 local on D0 (4 crush, 2 near-drowning, 11 laceration/wound, 8 fracture,
    19 other storm-related, 74 not storm-related), 37 admitted, 44 arrivals by ambulance, 6 major trauma."""
    plan = [("INJ_CRUSH", 4), ("INJ_DROWN", 2), ("INJ_LAC", 11), ("INJ_FX", 8), ("INJ_STORM", 19)]
    out = []
    hours_w = np.array([2, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 9, 9, 8, 8, 8, 8, 8], float)
    for cat, n in plan:
        for _ in range(n):
            hi = pick_home(w, "SRMC", g, weights=w.surge_w)
            out.append(make_visit(w, g, "SRMC", 0, cat, home=hi, hour=int(g.choice(18, p=hours_w / hours_w.sum())), forced_disp="Discharged", mode="Walk-in", esi=3))
    cats = [c for c in MIX if c not in ("IRRITANT", "CO", "GI")]
    p = np.array([MIX[c] for c in cats]); p /= p.sum()
    for _ in range(74):
        out.append(make_visit(w, g, "SRMC", 0, cats[int(g.choice(len(cats), p=p))], hour=int(g.choice(18, p=hours_w / hours_w.sum())), forced_disp="Discharged", mode="Walk-in", esi=int(g.choice([3, 4, 5], p=[0.5, 0.38, 0.12]))))
    # exactly 37 admissions, 44 ambulance arrivals, 6 major trauma among the storm injuries
    order = sorted(range(len(out)), key=lambda i: (0 if out[i]["text"].startswith(("crush", "pinned", "near drowning", "submersion")) else 1 if i < 44 else 2, i))
    for k, i in enumerate(order[:37]):
        out[i]["disp"] = "Admitted"
        out[i]["esi"] = 1 if k < 6 else 2
    for i in order[:44]:
        out[i]["mode"] = "EMS"
    # the evening
    for _ in range(54):
        if g.random() < 0.6:
            c = SURGE_CATS[int(g.choice(5, p=np.array([s for _, s in SURGE_CATS[:5]]) / sum(s for _, s in SURGE_CATS[:5])))][0]
            out.append(make_visit(w, g, "SRMC", 0, c, home=pick_home(w, "SRMC", g, weights=w.surge_w), hour=int(g.integers(18, 24))))
        else:
            out.append(make_visit(w, g, "SRMC", 0, cats[int(g.choice(len(cats), p=p))], hour=int(g.integers(18, 24))))
    return out


# ---------------------------------------------------------------------------------------
# hospital capacity
# ---------------------------------------------------------------------------------------
CENSUS = {
    "SRMC": {-3: 462, -2: 452, -1: 441, 0: 512, 1: 618, 2: 700, 3: 692, 4: 668, 5: 640, 6: 612, 7: 578, 8: 540, 9: 531, 10: 524,
             11: 519, 12: 514, 13: 510, 14: 506, 15: 509, 16: 528, 17: 556, 18: 580, 19: 592, 20: 598, 21: 596, 22: 590, 23: 572,
             24: 551, 25: 530, 26: 514, 27: 503, 28: 475, 29: 468, 30: 462},
    "BCMC": {-3: 244, -2: 236, -1: 228, 0: 283, 1: 310, 2: 331, 3: 327, 4: 318, 5: 312, 6: 306, 7: 302, 8: 298, 9: 292, 10: 287,
             11: 284, 12: 283, 13: 281, 14: 280, 15: 281, 16: 288, 17: 297, 18: 305, 19: 309, 20: 311, 21: 310, 22: 307, 23: 299,
             24: 288, 25: 277, 26: 268, 27: 259, 28: 249, 29: 247, 30: 246},
}
CAP_HEADER = ["Report_Date", "Facility_ID", "Facility_Name", "Census_Time_Local", "Licensed_Beds", "Staffed_Beds_Available",
              "Inpatient_Census", "Pct_Licensed_Occupancy", "Census_Target", "ICU_Beds", "ICU_Occupied", "ED_Beds", "ED_Visits_24h",
              "ED_Boarding", "Hallway_Patients", "Triage_Tent_Patients", "Elective_Procedures_Postponed", "Ventilators_Total",
              "Ventilators_In_Use", "Diversion_Status", "Staffing_Level", "Mutual_Aid", "Power_Source", "Commercial_Power_Lost_UTC",
              "Generator_Start_UTC", "Commercial_Power_Restored_UTC", "Generator_Hours_Cumulative", "Generator_Test",
              "Diesel_Tank_A_gal", "Diesel_Tank_B_gal", "Diesel_On_Hand_gal", "Burn_Rate_gph", "Fuel_Hours_Remaining",
              "Est_Runtime_Days_At_Storm_Load", "Fuel_Delivered_gal"]
# generator windows (UTC): lost, generator start, restored
POWER = {"SRMC": ("2027-09-14T06:17:03Z", "2027-09-14T06:17:26Z", "2027-09-22T14:14:33Z"),
         "BCMC": ("2027-09-14T06:31:40Z", "2027-09-14T06:32:02Z", "2027-09-22T15:42:10Z"),
         "LPMC": ("2027-09-14T06:44:12Z", "2027-09-14T06:44:51Z", "2027-09-18T19:05:00Z"),
         "GCCH": ("2027-09-14T06:52:30Z", "2027-09-14T06:52:49Z", "2027-09-17T21:30:00Z"),
         "SCMH": ("2027-09-14T07:05:18Z", "2027-09-14T07:05:55Z", "2027-09-19T16:20:00Z"),
         "FPCH": ("2027-09-14T08:10:44Z", "2027-09-14T08:11:20Z", "2027-09-16T23:45:00Z"),
         "ABCH": ("2027-09-14T05:38:09Z", "2027-09-14T05:38:41Z", "2027-09-23T18:10:00Z")}
SRMC_RATES = [110.0, 135.0, 158.0, 174.0, 180.0]      # gal/h between noon reports, D0 start .. D+4 noon


def tsz(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def srmc_fuel(d):
    """(tank A, tank B, burn rate now, delivered since last report) at 12:00 local on day d; canon D-2, D+5."""
    if d < 0:
        return 12000.0, 11850.0, 0.0, 0
    noon = lambda k: local_ts(k, "12:00")
    start = tsz(POWER["SRMC"][1])
    cum, t = 0.0, start
    for k in range(0, min(d, 4) + 1):
        cum += SRMC_RATES[k] * (noon(k) - t) / 3600.0
        t = noon(k)
    if d <= 4:
        a = max(0.0, 12000.0 * (1 - cum / 21024.0))
        return a, 23850.0 - cum - a, [122, 146, 166, 178, 182][d], 0
    if d == 5:
        return 0.0, 2730.0, 192.0, 0
    b = 2730.0 - 192.0 * 9.0 + 8000.0                      # delivery at 21:00 local on D+5 fills tank B to 10,730
    if d == 6:
        return 0.0, b - 192.0 * 15.0, 192.0, 8000
    if d == 7:                                              # second delivery, 6,000 gal, that morning
        return 0.0, b - 192.0 * 15.0 - 190.0 * 24.0 + 6000.0, 188.0, 6000
    end = tsz(POWER["SRMC"][2]) + 270
    left = b - 192.0 * 15.0 - 190.0 * 24.0 + 6000.0 - 188.0 * (end - noon(7)) / 3600.0
    if d == 8:
        return 0.0, left, 0.0, 0
    if d == 9:
        return 0.0, left, 0.0, 0
    if d in (10, 11):
        return 9000.0, left, 0.0, 9000 if d == 10 else 0
    return 12000.0, 11800.0, 0.0, (12000 - 9000) + int(11800 - left) if d == 12 else 0


def gen_capacity(visits_by):
    w = world()
    rows = []
    for d in range(FIRST_DAY, LAST_DAY + 1):
        for ab, f in w.fac.items():
            g = rng("hospital_capacity", ab, d)
            lic = f["licensed_beds"]
            base_occ = {"SRMC": 0.91, "BCMC": 0.875, "LPMC": 0.83, "SCMH": 0.80, "FPCH": 0.78, "GCCH": 0.82, "ABCH": 0.62}[ab]
            wd = ddate(d).weekday()
            if ab in CENSUS and d in CENSUS[ab]:
                census = CENSUS[ab][d]
            else:
                bump = 0.0
                if ab not in CENSUS and 0 <= d <= 20:
                    bump = 0.16 * math.exp(-((d - 2.5) / 5.0) ** 2) + 0.04 * math.exp(-((d - 19) / 4.0) ** 2)
                if ab == "ABCH" and -1 <= d <= 3:
                    bump = -0.45                           # evacuated ahead of landfall
                census = int(round(lic * (base_occ + bump + (-0.02 if wd >= 5 else 0.0)) + g.normal(0, lic * 0.012)))
                if ab == "SRMC" and d > 30:
                    census = min(census, 472)
            pct = round(100.0 * census / lic, 1)
            icu = f["icu_beds"]
            icu_occ = int(round(icu * min(1.25, 0.72 * census / (lic * base_occ)) + g.normal(0, 0.6)))
            hall = tent = 0
            over = census - lic
            if ab == "SRMC":
                tent = {1: 40, 2: 62, 3: 55, 4: 38, 5: 20, 6: 8}.get(d, 0)
                if over > 0:
                    hall = int(round(0.445 * over))
                if d == 2:
                    icu_occ, hall = 48, 89
            elif over > 0:
                hall = int(round(0.5 * over))
            ed_vis = visits_by.get((ab, d), 0)
            boarding = int(max(0, round(0.07 * ed_vis * max(0.2, census / lic - 0.6) * 3 + g.normal(0, 1.0))))
            if ab == "BCMC" and d == 2:
                boarding = 44
            elective = 0
            if ab == "SRMC":
                elective = {-2: 47, -1: 52}.get(d, (58 if wd < 5 else 0) if 0 <= d <= 28 else 0)
            elif -2 <= d <= 21:
                elective = int(round(lic * 0.09)) if wd < 5 else 0
            vent = f.get("ventilators") or 4
            vent_use = int(min(vent + 4, round(vent * 0.4 * census / (lic * base_occ) + g.normal(0, 0.6))))
            div = "OPEN"
            if ab == "SRMC" and 1 <= d <= 8:
                div = "INTERNAL EMERGENCY - SURGE"
            if ab == "BCMC" and 2 <= d <= 6:
                div = "DIVERT NON-CRITICAL"
            if ab == "ABCH" and -1 <= d <= 3:
                div = "EVACUATED - ED ONLY"
            staffing = "NORMAL" if census <= lic else ("STRAINED" if census <= lic * 1.1 else "CRITICAL")
            aid = ""
            if ab == "SRMC":
                aid = {2: "GETAC mutual aid requested 11:30; federal medical task force and supplemental nursing staff requested",
                       3: "Federal medical task force en route; road assessment pending", 4: "Federal medical task force en route",
                       5: "Priority 1 fuel request filed with county emergency fuel depot", 6: "Federal Medical Task Force 9 on site",
                       7: "Federal Medical Task Force 9 on site", 8: "Federal Medical Task Force 9 standing down"}.get(d, "")
            if ab == "BCMC" and d == 2:
                aid = "Non-critical ambulances redirected to Robstown and Kingsville"
            # ---------------- power and fuel
            lost, gstart, rest = (tsz(x) for x in POWER[ab])
            noon = local_ts(d, "12:00")
            src = "GENERATOR" if gstart <= noon < rest else "COMMERCIAL"
            d_lost, d_rest = day_of(lost), day_of(rest)
            gen_h = 0.0 if noon < gstart else (min(noon, rest + 270) - gstart) / 3600.0
            if ab == "SRMC":
                gen_h *= 195.05 / ((rest + 270 - gstart) / 3600.0)     # run-hours meter: 195 h 03 m in total (canon)
            cap_gal = f["backup_power"]["diesel_storage_gal"]
            ta = tb = ""
            burn = hours_left = deliv = ""
            test = "PASS" if d == -2 else ("PASS" if (wd == 0 and src == "COMMERCIAL") else "")
            est = ""
            if ab == "SRMC":
                a, b, r, dl = srmc_fuel(d)
                ta, tb, on_hand = int(round(a)), int(round(b)), a + b
                if src == "GENERATOR":
                    burn, hours_left = r, round(on_hand / r, 1)
                deliv = dl or ""
                est = 9.2 if d <= -1 else ""
            else:
                rate = cap_gal / (24.0 * {"BCMC": 4.2, "LPMC": 4.5, "GCCH": 5.0, "SCMH": 4.4, "FPCH": 5.0, "ABCH": 3.8}[ab])
                on = cap_gal * 0.97
                dl = 0
                if noon >= gstart:
                    t0 = gstart
                    k = d_lost
                    while k <= d:
                        tk = min(local_ts(k, "12:00"), rest)
                        if tk > t0:
                            on -= rate * (tk - t0) / 3600.0
                            t0 = tk
                        dl = 0
                        if on < rate * 30 and k < d + 1 and local_ts(k, "12:00") < rest + 3 * 86400:
                            dl = int(round((cap_gal * 0.92 - on) / 100.0) * 100)
                            on += dl
                        k += 1
                    if noon > rest + 4 * 86400:
                        on = cap_gal * 0.97
                        dl = 0
                on_hand = max(0.0, on)
                ta = int(round(on_hand))
                if src == "GENERATOR":
                    burn, hours_left = round(rate, 1), round(on_hand / rate, 1)
                deliv = dl or ""
            rows.append([ddate(d).isoformat(), f["facility_id"], f["facility_name"], "07:00" if not (ab == "SRMC" and d == 8) else "12:00",
                         lic, (487 if ab == "SRMC" and d == -2 else int(round(lic * (0.97 if census <= lic else 1.0)))), census, pct,
                         (440 if ab == "SRMC" and -3 <= d <= -1 else ""), icu, max(0, icu_occ), f["ed_beds"], ed_vis, boarding, hall, tent,
                         elective, vent, max(0, vent_use), div, staffing, aid, src,
                         iso(lost) if d == d_lost else "", iso(gstart) if d == d_lost else "", iso(rest) if d == d_rest else "",
                         round(gen_h, 2) if gen_h else "", test, ta, tb, int(round(on_hand)), burn, hours_left, est, deliv])
    return write_csv("05_other_sources/public_health/hospital_capacity.csv", CAP_HEADER, rows)


# ---------------------------------------------------------------------------------------
# wastewater
# ---------------------------------------------------------------------------------------
WW_HEADER = ["sample_id", "sample_date", "sewershed_id", "site_name", "sample_type", "target", "concentration_gc_per_L",
             "pmmov_gc_per_L", "normalized_ratio", "flow_MGD", "lab_qc", "report_date"]
WW_FLOW = {"WW-01": 6.5, "WW-02": 13.0, "WW-03": 7.0, "WW-04": 2.6, "WW-05": 1.4}
WW_RESUME = {"WW-01": 8, "WW-02": 4, "WW-03": 4, "WW-04": 6, "WW-05": 10}       # first sample day after landfall
NORO = [(-30, 1.0), (4, 1.2), (5, 2.2), (6, 4.0), (9, 9.0), (11, 12.0), (13, 10.0), (16, 6.0), (20, 3.0), (23, 1.8), (27, 1.1),
        (60, 1.0), (85, 1.5), (105, 2.6), (119, 3.0)]


def gen_wastewater():
    from gen_environment import supersede
    supersede(["05_other_sources/public_health/wastewater_surveillance.csv"], [WW_HEADER])
    sites = reg("sensor_registry")["wastewater_sampling_sites"]
    rows = []
    for s in sites:
        sid = s["asset_id"]
        g = rng("wastewater", sid)
        seq = 0
        for d in range(FIRST_DAY - 3, LAST_DAY + 1):      # the programme was already running before the span starts
            wd = ddate(d).weekday()
            days = (0, 3, 5) if sid in ("WW-01", "WW-02") else (0, 3)
            if wd not in days:
                continue
            if -1 <= d < WW_RESUME[sid]:
                continue                                  # plants flooded or without power; sampling suspended
            if g.random() < 0.03 and FIRST_DAY + 7 < d < LAST_DAY - 7:
                continue                                  # a missed pick-up now and then
            seq += 1
            rain_flow = 1.0 + (1.6 * math.exp(-max(0, d - 2) / 6.0) if d >= 0 else (0.25 if -7 <= d <= -3 else 0.0))
            flow = WW_FLOW[sid] * rain_flow * (1 + g.normal(0, 0.05))
            pmmov = 3.2e7 * math.exp(g.normal(0, 0.25)) / rain_flow ** 0.5
            mult = float(np.interp(d, [k for k, _ in NORO], [v for _, v in NORO]))
            noro = 4.2e4 * mult * math.exp(g.normal(0, 0.28)) / rain_flow ** 0.3
            cov = 9.0e4 * (1.0 + 1.2 * max(0.0, (d - 70) / 49.0)) * math.exp(g.normal(0, 0.35)) / rain_flow ** 0.3
            for target, conc in (("Norovirus GII", noro), ("SARS-CoV-2", cov)):
                rows.append([f"{sid}-{ddate(d).strftime('%y%m%d')}-{'N' if target.startswith('N') else 'S'}", ddate(d).isoformat(), sid,
                             s["sensor_name"], "24-hour flow-weighted composite", target, int(round(conc, -2)), int(round(pmmov, -4)),
                             round(conc / pmmov, 6), round(flow, 2), "pass", ddate(d + 2 + (1 if wd == 5 else 0)).isoformat()])
    return write_csv("05_other_sources/public_health/wastewater_surveillance.csv", WW_HEADER, rows)


# ---------------------------------------------------------------------------------------
def gen_ed():
    w = world()
    old = [os.path.relpath(p, ROOT) for pat in ("05_other_sources/public_health/ed_visits_*.csv", "05_other_sources/public_health/_consolidated/*",
                                                "05_other_sources/public_health/hospital_capacity.csv", "05_other_sources/public_health/syndrome_summary.csv")
           for p in glob.glob(os.path.join(ROOT, pat))]
    from gen_environment import supersede
    supersede(old, [HEADER, CAP_HEADER, SYN_HEADER])
    visits = build_visits()
    visits.sort(key=lambda v: (v["ab"], v["t"]))
    by_fac = defaultdict(list)
    for v in visits:
        by_fac[v["ab"]].append(v)
    counts = defaultdict(int)
    syn = defaultdict(lambda: [0, 0])
    totals = {}
    for ab, vs in by_fac.items():
        f = w.fac[ab]
        seq = defaultdict(int)
        rows = []
        for v in vs:
            date = ddate(v["day"])
            seq[v["day"]] += 1
            counts[(ab, v["day"])] += 1
            key = (date.isoformat(), f["facility_id"], "AREA-ZIP-" + v["zip"], v["cat"])
            syn[key][0] += 1
            syn[key][1] += v["disp"] == "Admitted"
            rows.append([f"{ab}-{date.strftime('%y%m%d')}-{seq[v['day']]:04d}", f["facility_id"], f["facility_name"], "E", date.isoformat(),
                         iso(v["t"]), v["mode"], v["esi"], v["text"], v["cat"], v["age"], age_group(v["age"]), v["sex"], v["race"],
                         v["lang"], v["zip"], v["tract"], v["onset"], v["disp"], v["dx"], f["county"]])
        totals[ab] = write_csv(f"05_other_sources/public_health/ed_visits_{f['facility_id']}.csv", HEADER, rows)
    srows = [[k[0], k[1], k[2], k[3], v[0], v[1]] for k, v in sorted(syn.items())]
    totals["syndromic"] = write_csv("05_other_sources/public_health/syndrome_summary.csv", SYN_HEADER, srows)
    totals["capacity"] = gen_capacity(counts)
    return totals


if __name__ == "__main__":
    which = sys.argv[1:] or ["ed", "wastewater"]
    if "ed" in which:
        for k, v in gen_ed().items():
            print(f"ed {k}: {v} rows")
    if "wastewater" in which:
        print("wastewater:", gen_wastewater(), "rows")
