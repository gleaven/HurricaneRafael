"""Ground emergency streams that do not depend on the dispatch simulation:

  05_other_sources/public_health/eas_broadcasts.csv   public alerts with separate English/Spanish release times
  05_other_sources/broadcast/*.csv                    station status, programme log, alert relay, translation jobs, call-ins
  05_other_sources/press_releases/*.jsonl             the public record as dated statements and notices
  05_other_sources/shelters/*.csv                     shelter registry, daily census, 211 shelter calls
  05_other_sources/infrastructure/*.csv               structure damage assessments, utility site surveys
  05_other_sources/infrastructure/aerial_survey/      aerial collection index

    python3 scripts/streams/gen_ground_public.py

Truth: 00_scenario/canon_timeline.json (alerts, broadcast, closures) and its expected observations,
02_public_record/public_record.json (public fields only). Positions: scripts/geo.py via ground_lib.
"""
import collections
import re

from ground_lib import *  # noqa: F401,F403

H = 3600
DAY = 86400


def Z(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return D0_EPOCH + day * DAY + h * H + m * 60


def when(obj):
    """Epoch of a canon time object ({"utc": ...}) or None."""
    return ts(obj["utc"]) if obj and obj.get("utc") else None


# ======================================================================================
# alerts
# ======================================================================================
def build_alerts():
    al = {a["id"]: a for a in canon()["alerts"]["items"]}
    rows = []

    def add(aid, cap, code, typ, issued, en, es, expires, channels, wea, wea_en, wea_es, area, area_ids, h_en, h_es, source, prio):
        rows.append({"AlertID": aid, "CAPmsgID": cap, "EventCode": code, "AlertType": typ, "IssuedAt_UTC": iso(issued),
                     "ReleasedAt_EN": iso(en) if en else "", "ReleasedAt_ES": iso(es) if es else "",
                     "ExpiresAt_UTC": iso(expires) if expires else "", "BroadcastChannel": channels, "WEA_Sent": "Y" if wea else "N",
                     "WEA_Sent_EN": iso(wea_en) if wea_en else "", "WEA_Sent_ES": iso(wea_es) if wea_es else "",
                     "GeographicArea": area, "AreaIDs": area_ids, "Headline_EN": h_en, "Headline_ES": h_es, "AlertSource": source,
                     "Priority": prio, "CharCount_EN": len(h_en), "_t": issued})

    nueces = "Nueces County TX"
    # routine tests across the whole span: one required weekly test a week on a varying day, a monthly test on the
    # first Wednesday (not while the response is at its height), and the county IPAWS test on D-5 (EVT-2101)
    wrg = rng("ground", "rwt")
    week_start = -30
    while week_start <= 119:
        if week_start == -30:
            d, hm = -30, "10:10"
        elif week_start + 6 >= 119:
            d, hm = 119, "09:00"
        else:
            d, hm = week_start + int(wrg.integers(0, 7)), f"{int(wrg.integers(8, 17)):02d}:{int(wrg.integers(0, 6)) * 10:02d}"
        if not (-2 <= d <= 5):
            t = local_ts(d, hm)
            l = local_dt(t)
            add(f"RWT-{l:%Y-%m%d}-001", f"CCDMA-{l:%Y-%m-%d}-RWT-001", "RWT", "RequiredWeeklyTest", t, t, t, t + 900, "EAS-TV,EAS-Radio", False, None, None,
                "Corpus Christi DMA", "PLC-001", "REQUIRED WEEKLY TEST of the Emergency Alert System", "PRUEBA SEMANAL REQUERIDA del Sistema de Alerta de Emergencia",
                "CC-DMA-LP1", "TEST")
        week_start += 7
    for d in range(-30, 120):
        l = local_dt(local_ts(d, "12:00"))
        if l.weekday() == 2 and l.day <= 7 and not (0 <= d <= 21):
            t = local_ts(d, "10:20")
            add(f"RMT-{l:%Y-%m%d}-001", f"TXSECC-{l:%Y-%m-%d}-RMT-001", "RMT", "RequiredMonthlyTest", t, t, t, t + 3600, "EAS-TV,EAS-Radio", False, None, None,
                "State of Texas", "PLC-001", "REQUIRED MONTHLY TEST of the Emergency Alert System", "PRUEBA MENSUAL REQUERIDA del Sistema de Alerta de Emergencia",
                "TX-SECC", "TEST")
    t = local_ts(-5, "09:00")
    add("IPAWS-TX-2027-0909-001", "NCOEM-2027-09-09-RWT-001", "RWT", "RequiredWeeklyTest", t, t, t, t + 900, "EAS-TV,EAS-Radio,IPAWS",
        False, None, None, "Corpus Christi DMA", "PLC-001", "IPAWS TEST - Nueces County Office of Emergency Management - this is only a test",
        "PRUEBA DE IPAWS - Oficina de Manejo de Emergencias del Condado de Nueces - esto es solo una prueba", "NCOEM", "TEST")
    # hurricane watch (no time of day in the sources: issued 10:00 local on D-3)
    t = local_ts(-3, "10:00")
    add("HUA-2027-0911-001", "NWS-CRP-2027-09-11-HUA-001", "HU.A", "HurricaneWatch", t, t, t + 300, when(al["hurricane-watch"]["end"]),
        "EAS-TV,EAS-Radio,NWS-Website", False, None, None, "Coastal Bend: Nueces, San Patricio, Aransas, Kleberg counties TX", "PLC-001;PLC-002;PLC-003;PLC-004",
        "HURRICANE WATCH for the Coastal Bend. Hurricane Rafael could bring hurricane conditions within 48 hours.",
        "VIGILANCIA DE HURACAN para el Coastal Bend. El huracan Rafael podria traer condiciones de huracan en 48 horas.", "NWS-CRP", "SEVERE")
    a = al["evacuation-zone-a"]
    en, es = when(a["release_en"]), when(a["release_es"])
    add("EVI-2027-0912-001", "NCOEM-2027-09-12-EVAC-A-001", "EVI", "MandatoryEvacuationOrder", en, en, es, when(al["evacuation-zone-abc"]["end"]),
        "EAS-TV,EAS-Radio,IPAWS-WEA,BendReady-SMS", True, en + 240, es + 180, "Nueces County Evacuation Zone A", "AREA-EVAC-A",
        "MANDATORY EVACUATION ORDER - Zone A (barrier islands and low-lying surge areas). Leave now. County buses for residents without transportation: call 2-1-1.",
        "ORDEN DE EVACUACION OBLIGATORIA - Zona A (islas de barrera y areas bajas). Salga ahora. Autobuses del condado para residentes sin transporte: llame al 2-1-1.",
        "NCOEM", "EXTREME")
    a = al["hurricane-warning"]
    en, es = when(a["release_en"]), when(a["release_es"])
    hw = ("HURRICANE WARNING for Nueces County. Hurricane Rafael, a major hurricane, is expected to make landfall near Port Aransas around 1 AM CDT Tuesday, "
          "September 14 with life-threatening storm surge and destructive winds. Complete preparations now and follow evacuation orders from local officials. NWS Corpus Christi.")
    add("HUW-2027-0912-001", "NWS-CRP-2027-09-12-HUW-001", "HU.W", "HurricaneWarning", en, en, es, when(a["end"]), "EAS-TV,EAS-Radio,IPAWS-WEA,NWS-Website", True, en + 240, None,
        "TX-355 Nueces County", "PLC-001", hw,
        "ADVERTENCIA DE HURACAN para el Condado de Nueces. Se espera que el huracan Rafael toque tierra cerca de Port Aransas alrededor de la 1 AM del martes 14 de septiembre. Termine sus preparativos ahora.",
        "NWS-CRP", "EXTREME")
    assert rows[-1]["CharCount_EN"] == 312, rows[-1]["CharCount_EN"]     # the count canon states is the real length
    a = al["evacuation-zone-abc"]
    en, es = when(a["release_en"]), when(a["release_es"])
    add("EVI-2027-0913-001", "NCOEM-2027-09-13-EVAC-ABC-001", "EVI", "MandatoryEvacuationOrder", en, en, es, when(a["end"]), "EAS-TV,EAS-Radio,IPAWS-WEA,BendReady-SMS", True,
        en + 240, en + 240, "Nueces County Evacuation Zones A, B and C", "AREA-EVAC-A;AREA-EVAC-B;AREA-EVAC-C",
        "EVACUATION ORDER Nueces County Zones A B C. LEAVE NOW. Hurricane Rafael Cat 3 arrives 9/14. Take medications, documents, pets. Emergency.Alert.gov",
        "ORDEN DE EVACUACION Condado de Nueces Zonas A B C. SALGA AHORA. El huracan Rafael categoria 3 llega el 14 de septiembre. Lleve medicinas, documentos, mascotas.",
        "NCOEM", "EXTREME")
    a = al["shelter-zones-c-e"]
    en, es = when(a["release_en"]), when(a["release_es"])
    add("SPW-2027-0913-001", "CCOEM-2027-09-13-SIP-CE-001", "SPW", "ShelterInPlaceGuidance", en, en, es, when(al["shelter-in-place"]["end"]), "IPAWS-WEA,BendReady-SMS,City-Website", True,
        en, es, "Corpus Christi Evacuation Zones C, D and E", "AREA-EVAC-C;AREA-EVAC-D;AREA-EVAC-E",
        "City of Corpus Christi: residents of Zones C, D and E who have not left should shelter in place from 8 PM. Stay off the roads. Shelter list: call 2-1-1.",
        "Ciudad de Corpus Christi: los residentes de las Zonas C, D y E que no hayan salido deben refugiarse en casa desde las 8 PM. No salga a las calles. Albergues: llame al 2-1-1.",
        "CCOEM", "SEVERE")
    a = al["shelter-in-place"]
    en, es = when(a["release_en"]), when(a["release_es"])
    add("SPW-2027-0914-001", "NCOEM-2027-09-14-SIP-001", "SPW", "ShelterInPlaceWarning", en, en, es, when(a["end"]), "EAS-TV,EAS-Radio,IPAWS-WEA", True, en + 60, None,
        "Nueces County - all zones", "PLC-001", "SHELTER IN PLACE. Hurricane Rafael is making landfall. Do not go outside. Life-threatening conditions. Refugiese ahora.",
        "REFUGIESE DONDE ESTA. El huracan Rafael esta tocando tierra. No salga. Condiciones que amenazan la vida.", "NCOEM", "EXTREME")
    t = local_ts(1, "09:00")
    add("CEM-2027-0915-001", "CCOEM-2027-09-15-CURFEW-001", "CEM", "CurfewNotice", t, t, None, None, "EAS-Radio,City-Website", False, None, None, "City of Corpus Christi", "AREA-CITY-CORPUSCHRISTI",
        "CURFEW in effect dusk to dawn inside Corpus Christi city limits until further notice.", "", "CCOEM", "MODERATE")
    a = al["air-quality-advisory"]
    en = when(a["release_en"])
    add("AQA-2027-0916-001", "TCEQ-2027-09-16-AQ-001", "CEM", "AirQualityHealthAdvisory", en, en, None, None, "EAS-Radio,Agency-Website", False, None, None,
        "Within 3 km of the Corpus Christi Ship Channel", "AREA-NBH-INNERHARBOR;AREA-NBH-HILLCREST;AREA-NBH-NORTHBEACH",
        "AIR QUALITY HEALTH ADVISORY within 3 km of the ship channel. Benzene measured at 4.8 ppb at Hillcrest. Sensitive groups stay indoors and avoid oiled shorelines.", "",
        "TCEQ / Corpus Christi-Nueces County Public Health District", "MODERATE")
    a = al["boil-water-citywide"]
    en, es = when(a["release_en"]), when(a["release_es"])
    add("BWN-2027-0918-001", "CCWATER-2027-09-18-BWN-001", "CEM", "BoilWaterNotice", en, en, es, when(a["end"]), "EAS-TV,EAS-Radio,IPAWS-WEA,BendReady-SMS,City-Website", True, en + 300, es + 300,
        "City of Corpus Christi - all water customers", "AREA-CITY-CORPUSCHRISTI",
        "BOIL WATER NOTICE for all Corpus Christi water customers. Bring water to a rolling boil for two minutes before drinking or cooking. Water distribution sites are open.",
        "AVISO DE HERVIR EL AGUA para todos los clientes de agua de Corpus Christi. Hierva el agua durante dos minutos antes de beberla o cocinar. Hay sitios de distribucion de agua abiertos.",
        "Corpus Christi Water Department", "SEVERE")
    t = local_ts(4, "15:00")
    add("ADR-2027-0918-001", "FEMA-DR-4821-TX-001", "ADR", "DisasterDeclarationNotice", t, t, None, None, "EAS-Radio,Agency-Website", False, None, None,
        "Nueces, San Patricio and Aransas counties TX", "PLC-001;PLC-002;PLC-003",
        "MAJOR DISASTER DECLARATION DR-4821-TX for Nueces, San Patricio and Aransas counties covers debris removal and emergency protective measures.", "", "FEMA Region 6", "MODERATE")
    a = al["fishing-shellfish-closure"]
    en = when(a["release_en"])
    add("CEM-2027-0918-002", "TPWD-DSHS-2027-09-18-CLOSURE-001", "CEM", "FishingAndShellfishClosure", en, en, None, None, "EAS-Radio,Agency-Website", False, None, None,
        "Nueces Bay and Corpus Christi Bay", "PLC-001;PLC-002", "FISHING AND SHELLFISH HARVESTING CLOSED in Nueces and Corpus Christi bays because of the oil spill until further notice.", "",
        "TPWD / DSHS", "MODERATE")
    a = al["boil-water-d3-d4"]
    en, es = when(a["release_en"]), when(a["release_es"])
    bw = ("BOIL WATER NOTICE for Water Districts 3 and 4 of the Corpus Christi water system, around 48,000 residents. Low water pressure in both districts. "
          "Bring all water to a rolling boil for two minutes before drinking, cooking or brushing teeth. CBPWA and the City Water Department. Call 3-1-1.")
    add("BWW-2027-0926-001", "CCWATER-2027-09-26-BWN-D34-001", "BWW", "BoilWaterNotice", en, en, es, when(a["end"]), "CoastAlert,EAS-TV,EAS-Radio,IPAWS-WEA", True, en + 120, None,
        "Corpus Christi Water Districts 3 and 4", "AREA-WD-3;AREA-WD-4", bw,
        "AVISO DE HERVIR EL AGUA para los Distritos de Agua 3 y 4 de Corpus Christi, unos 48,000 residentes. Hierva toda el agua durante dos minutos antes de beberla, cocinar o cepillarse los dientes.",
        "Corpus Christi Water Department / CBPWA", "SEVERE")
    assert rows[-1]["CharCount_EN"] == 287, rows[-1]["CharCount_EN"]
    t = when(a["detail"]["weekly_update_first_simultaneous_bilingual"])
    add("BWU-2027-1014-001", "CCWATER-2027-10-14-BWU-001", "CEM", "BoilWaterStatusUpdate", t, t, t, None, "CoastAlert,EAS-Radio,City-Website", False, None, None,
        "City of Corpus Christi; Water Districts 3 and 4", "AREA-CITY-CORPUSCHRISTI;AREA-WD-3;AREA-WD-4",
        "BOIL WATER STATUS UPDATE: both boil water notices remain in effect. Continue to boil water for two minutes. Next update in one week.",
        "ACTUALIZACION DEL AVISO DE HERVIR EL AGUA: ambos avisos siguen vigentes. Siga hirviendo el agua durante dos minutos. Proxima actualizacion en una semana.",
        "Corpus Christi Water Department", "MODERATE")
    t = when(al["boil-water-citywide"]["end"])
    add("BWA-2027-1023-001", "CCWATER-2027-10-23-BWL-001", "BWA", "BoilWaterNoticeLifted", t, t, t, None, "CoastAlert,EAS-TV,EAS-Radio,City-Website", False, None, None,
        "City of Corpus Christi except Water Districts 3 and 4", "AREA-CITY-CORPUSCHRISTI",
        "BOIL WATER NOTICE LIFTED for Corpus Christi after pump repairs and testing. The notice remains in effect for Water Districts 3 and 4.",
        "SE LEVANTA EL AVISO DE HERVIR EL AGUA en Corpus Christi tras la reparacion de bombas y pruebas. El aviso sigue vigente en los Distritos de Agua 3 y 4.",
        "Corpus Christi Water Department", "MODERATE")
    t = when(a["end"])
    add("BWA-2027-1026-001", "CCWATER-2027-10-26-BWL-D34-001", "BWA", "BoilWaterNoticeLifted", t, t, t, None, "CoastAlert,EAS-TV,EAS-Radio,IPAWS", False, None, None,
        "Corpus Christi Water Districts 3 and 4", "AREA-WD-3;AREA-WD-4",
        "BOIL WATER NOTICE LIFTED for Water Districts 3 and 4. Pressure at all test points in both districts is confirmed above 40 psi and bacteriological samples have passed.",
        "SE LEVANTA EL AVISO DE HERVIR EL AGUA para los Distritos de Agua 3 y 4. La presion en todos los puntos de prueba de ambos distritos supera 40 psi y las muestras bacteriologicas pasaron.",
        "Corpus Christi Water Department / CBPWA", "MODERATE")
    rows.sort(key=lambda r: r["_t"])
    return rows


ALERT_HEADER = ["AlertID", "CAPmsgID", "EventCode", "AlertType", "IssuedAt_UTC", "ReleasedAt_EN", "ReleasedAt_ES", "ExpiresAt_UTC", "BroadcastChannel", "WEA_Sent",
                "WEA_Sent_EN", "WEA_Sent_ES", "GeographicArea", "AreaIDs", "Headline_EN", "Headline_ES", "AlertSource", "Priority", "CharCount_EN"]


# ======================================================================================
# broadcast logs
# ======================================================================================
STATION = {"OUT-02": ("Harborline 6 News", "TV"), "OUT-03": ("Coastline Public Radio", "FM"), "OUT-08": ("KNCB Coastal Bend Radio", "AM"),
           "OUT-01": ("The Bayside Ledger", "WEB"), "OUT-04": ("Gulfwater Maritime Report", "WEB"), "OUT-05": ("Sabal Energy Wire", "WEB"),
           "OUT-06": ("Continental Wire Service", "WIRE"), "OUT-07": ("Anchor & Rotor Weekly", "WEB")}
RELAY = ["OUT-01", "OUT-02", "OUT-03", "OUT-04", "OUT-05", "OUT-07", "OUT-08"]      # the seven outlets in the Corpus Christi market


def build_broadcast(alerts):
    b = canon()["broadcast"]
    rg = rng("ground", "broadcast")
    prog, status, relay, jobs, calls = [], [], [], [], []

    def P(t, sid, item, lang, desc, alert="", dur=None, platform=None):
        prog.append([iso(t), sid, STATION[sid][0], platform or STATION[sid][1], item, lang, alert, dur if dur is not None else "", desc])

    def S(t, sid, st, note):
        status.append([iso(t), sid, STATION[sid][0], st, note])

    # --- station status (canon broadcast.outlets_on_air)
    kn = next(o for o in b["outlets_on_air"] if "OUT-08" in o["outlet"])
    h6 = next(o for o in b["outlets_on_air"] if "OUT-02" in o["outlet"])
    cp = next(o for o in b["outlets_on_air"] if "OUT-03" in o["outlet"])
    ef0, ef1 = when(kn["emergency_format"]["start"]), when(kn["emergency_format"]["end"])
    S(ef0, "OUT-08", "EMERGENCY FORMAT", "24-hour emergency format begins; regular programming suspended")
    S(when(kn["off_air"]["start"]), "OUT-08", "OFF AIR", "transmitter lost power; web updates continue")
    S(when(kn["off_air"]["end"]), "OUT-08", "ON AIR", "transmitter restored; emergency format continues")
    S(local_ts(30, "00:00"), "OUT-08", "EMERGENCY FORMAT 18 HOURS", "emergency format 06:00-24:00; music programming overnight")
    S(ef1, "OUT-08", "NORMAL FORMAT", "return to normal format after 48 days of emergency format")
    S(Z(-2, "17:06"), "OUT-02", "EMERGENCY FORMAT", "continuous hurricane coverage from the anchor desk")
    S(when(h6["off_air"]["start"]), "OUT-02", "OFF AIR", "main transmitter and studio lost power; web updates continue")
    S(when(h6["off_air"]["end"]), "OUT-02", "ON AIR", "transmitter restored; broadcasting from backup studio")
    S(Z(-2, "17:03"), "OUT-03", "SPECIAL COVERAGE", "regular programming interrupted for hurricane coverage")
    S(when(cp["on_generator"]["start"]), "OUT-03", "ON AIR - GENERATOR", "continuous coverage on 2.2 kW generator")
    S(when(cp["on_generator"]["end"]), "OUT-03", "ON AIR", "utility power restored at transmitter")
    S(Z(0, "06:30"), "OUT-03", "ON AIR - GENERATOR", "no other Corpus Christi broadcast signal monitored on the air")
    S(Z(0, "09:00"), "OUT-03", "ON AIR - GENERATOR", "eyewall passed; still the only local broadcast signal monitored")
    for sid, t in (("OUT-04", Z(1, "16:30")), ("OUT-05", Z(2, "04:10")), ("OUT-07", Z(2, "06:00"))):
        S(Z(0, "06:10") + int(rg.integers(0, 1500)), sid, "OFFLINE", "newsroom systems down")
        S(t, sid, "ONLINE", "publishing restored")
    S(Z(2, "06:00"), "OUT-07", "MARKET STATUS", "all Corpus Christi market outlets back in service")

    # --- alert relay log: when each market outlet received each alert (lag after the origination)
    for a in alerts:
        t = ts(a["IssuedAt_UTC"])
        for sid in RELAY:
            down = (sid == "OUT-02" and when(h6["off_air"]["start"]) <= t < when(h6["off_air"]["end"])) or \
                   (sid == "OUT-08" and when(kn["off_air"]["start"]) <= t < when(kn["off_air"]["end"]))
            lag = round(float(rg.uniform(0.4, 1.9)), 1)
            relay.append([a["AlertID"], sid, STATION[sid][0], "" if down else iso(t + int(lag)), "" if down else lag, "NOT RECEIVED - OFF AIR" if down else "RECEIVED"])
        lag = 4.1 if a["AlertID"] == "IPAWS-TX-2027-0909-001" else round(float(rg.uniform(3.8, 4.4)) if -5 <= day_of(t) <= 0 else float(rg.uniform(0.5, 1.6)), 1)
        relay.append([a["AlertID"], "WKCB-AM", "WKCB-AM relay station", iso(t + int(lag)), lag, "RELAYED - LAG ANOMALY" if a["AlertID"] == "IPAWS-TX-2027-0909-001" else "RELAYED"])

    # --- translation jobs (county contractor NCLAS: two-hour turnaround for life-safety alerts)
    al = {x["id"]: x for x in canon()["alerts"]["items"]}
    jobs.append(["2027-09-09-STANDBY-001", "", "NCLAS", iso(Z(-5, "14:00")), "", "", 2, "STANDBY", "24-hour standby placed; two-hour turnaround for life-safety alerts; no provision for simultaneous release"])
    a = al["evacuation-zone-a"]
    jobs.append(["2027-09-12-EVAC-001", "EVI-2027-0912-001", "NCLAS", iso(when(a["release_en"])), iso(when(a["translation_delivered_es"])), iso(when(a["release_es"])), 2, "DELIVERED",
                 "Zone A evacuation order; read on KNCB at 08:47 local"])
    a = al["shelter-zones-c-e"]
    jobs.append(["2027-09-13-SIP-001", "SPW-2027-0913-001", "NCLAS", iso(when(a["release_en"])), iso(when(a["release_es"]) - 26 * 60), iso(when(a["release_es"])), 2, "DELIVERED LATE", "shelter guidance Zones C to E"])
    a = al["boil-water-citywide"]
    jobs.append(["2027-09-18-BWN-001", "BWN-2027-0918-001", "CITY STAFF", iso(when(a["release_en"]) - 1500), iso(when(a["release_en"]) - 300), iso(when(a["release_es"])), 2, "DELIVERED", "citywide boil water notice"])
    a = al["boil-water-d3-d4"]
    jobs.append(["2027-09-26-BWN-001", "BWW-2027-0926-001", "NCLAS", iso(local_ts(12, "17:35")), iso(when(a["detail"]["translation_ready"])), iso(when(a["release_es"])), 2, "DELIVERED LATE",
                 f"Districts 3 and 4 boil water notice; sent to KNCB {local_iso(when(a['detail']['sent_to_kncb']))[11:16]} local next morning"])
    for aid, d, hm in (("BWU-2027-1014-001", 30, "09:00"), ("BWA-2027-1023-001", 39, "09:00"), ("BWA-2027-1026-001", 42, "11:00")):
        t = local_ts(d, hm)
        jobs.append([f"{local_dt(t):%Y-%m-%d}-BW-001", aid, "NCLAS", iso(t - 5 * H), iso(t - 3 * H - 600), iso(t), 2, "DELIVERED", "held for simultaneous release in English and Spanish"])

    # --- programme log: alert read-outs
    for a in alerts:
        if a["EventCode"] in ("RWT", "RMT"):
            continue
        en = ts(a["ReleasedAt_EN"]); es = ts(a["ReleasedAt_ES"]) if a["ReleasedAt_ES"] else None
        for sid in ("OUT-02", "OUT-03"):
            off = sid == "OUT-02" and when(h6["off_air"]["start"]) <= en < when(h6["off_air"]["end"])
            if not off:
                P(en + int(rg.integers(60, 400)), sid, "ALERT READ", "EN", a["AlertType"], a["AlertID"], int(rg.integers(40, 110)))
        if es is not None:
            off = when(kn["off_air"]["start"]) <= es < when(kn["off_air"]["end"])
            P(es, "OUT-08", "ALERT READ", "ES", a["AlertType"], a["AlertID"], int(rg.integers(50, 130)), platform="WEB STREAM" if off else None)

    # --- canon programme items
    P(Z(-5, "14:00"), "OUT-08", "COORDINATION CALL", "ES/EN", "Emergency coordination call with Nueces County Office of Emergency Management; translation contractor on standby", dur=1500, platform="OFF AIR - INTERNAL")
    P(ef0, "OUT-08", "FORMAT CHANGE", "ES", "Emergency format announcement: regular programming suspended; official information in Spanish around the clock", dur=120)
    P(Z(-2, "17:06"), "OUT-02", "FORMAT CHANGE", "EN", "Emergency format activated after the hurricane warning; anchor desk continuous coverage", "HUW-2027-0912-001", 0)
    P(Z(-2, "17:03"), "OUT-03", "PROGRAM INTERRUPTION", "EN", "Regular programming interrupted for the hurricane warning", "HUW-2027-0912-001", 0)
    P(Z(-2, "17:08"), "OUT-08", "BILINGUAL COVERAGE", "ES/EN", "Bilingual continuous coverage of the hurricane warning begins", "HUW-2027-0912-001", 0)
    loop0 = Z(-1, "12:15")
    P(loop0, "OUT-08", "LOOP START", "ES/EN", "Bilingual evacuation loop activated: routes, shelters, bus pick-up through 2-1-1", "EVI-2027-0913-001", 0)
    stop = LANDFALL
    for k in range(24):
        t = loop0 + int((stop - loop0 - 600) * k / 23)
        P(t + 30, "OUT-08", "EVACUATION LOOP", "ES/EN", f"Evacuation and shelter information loop, play {k + 1}", "EVI-2027-0913-001", 420)
    P(local_ts(-1, "13:45"), "OUT-08", "SHELTER INFORMATION", "ES", "Lectura de albergues: 'Los residentes de la Zona D deben ir al Colegio Collier en Leopard Street'", "", 45)
    P(local_ts(-1, "20:52"), "OUT-08", "SHELTER INFORMATION", "ES", "Lectura de albergues oficiales del condado: Zona D, Richard King High School, 5225 Gollihar Rd", "SPW-2027-0913-001", 60)
    P(when(cp["on_generator"]["start"]), "OUT-03", "CONTINUOUS COVERAGE", "EN", "Continuous landfall coverage on generator power", "", 9 * H)
    P(Z(0, "08:30"), "OUT-08", "SIGN-OFF", "ES", "Ultima transmision antes de perder energia en el transmisor", "", 60)
    P(local_ts(0, "10:00"), "OUT-08", "ADVISORY", "ES", "Aviso: la linea de informacion de FEMA atiende solo en ingles por ahora", "", 90, platform="WEB STREAM")
    P(when(h6["first_post_storm_broadcast"]), "OUT-02", "NEWSCAST", "EN", "First post-landfall anchor broadcast from the backup studio: damage, casualties, shelters, curfew (read pace about 158 words a minute)", "", 47 * 60)
    P(local_ts(8, "10:00"), "OUT-08", "LIVE ANNOUNCEMENT", "ES", "Regular programming interrupted to carry live the announcement that the FEMA information line now answers in Spanish", "", 420)
    P(local_ts(13, "06:03"), "OUT-08", "ALERT READ", "ES", "First reading of the boil water notice for Districts 3 and 4; translation received from the county at 05:58", "BWW-2027-0926-001", 150)
    P(local_ts(13, "07:15"), "OUT-08", "HOST REMARKS", "ES", "'Recibimos el aviso oficial esta manana temprano de la ciudad. Se que muchos de ustedes estan preguntando: por que no lo supimos antes? Es una pregunta que tambien tenemos nosotros.'", "BWW-2027-0926-001", 75)
    P(local_ts(13, "12:10"), "OUT-02", "FIELD INTERVIEWS", "EN/ES", "Field interviews at a District 3 water distribution site: 7 of 9 residents interviewed said they first heard of the notice the next morning", "BWW-2027-0926-001", 180)
    P(Z(21, "19:00"), "OUT-02", "LIVE PRESS CONFERENCE", "EN", "Live press conference coverage. Anchor intro: 'authorities say the outages that left tens of thousands without power for more than two weeks were prolonged by what officials are calling, quote, deliberate interference with utility systems'", "", 47 * 60)
    P(Z(21, "19:55"), "OUT-08", "DOCUMENT READ", "ES/EN", "LULAC complaint TX-DEM-2027-LEP-0012 to the Texas Division of Emergency Management read in full", "", 780)
    P(local_ts(30, "00:00"), "OUT-08", "FORMAT CHANGE", "ES", "Emergency format scaled back to 18 hours a day; music programming restored overnight", "", 60)
    P(Z(42, "16:00"), "OUT-08", "ALERT READ", "ES", "Spanish all-clear for Districts 3 and 4 aired at the same time as the English alert, under the county rule requiring simultaneous Spanish and English release", "BWA-2027-1026-001", 120)
    P(Z(42, "22:00"), "OUT-02", "NEWS PACKAGE", "EN", "'Boil water ban ends - 30 days later' package, 3 min 42 sec; recalls the Spanish-language delay when the notice began", "BWA-2027-1026-001", 222)
    P(ef1, "OUT-08", "FORMAT CHANGE", "ES", "Return to normal format at 06:00; emergency format lasted 48 days", "", 60)
    P(Z(90, "19:00"), "OUT-02", "LIVE PRESS CONFERENCE", "EN", "FBI and state investigators announce disaster-fraud arrests; carried live", "", 34 * 60)
    P(Z(90, "19:00"), "OUT-03", "LIVE PRESS CONFERENCE", "EN", "FBI and state investigators announce disaster-fraud arrests; carried live", "", 34 * 60)
    P(Z(90, "19:40"), "OUT-06", "WIRE DISTRIBUTION", "EN", "Press conference report distributed nationally", "", "", platform="WIRE")
    # --- routine items, D-5 to D+45
    for d in range(-5, 46):
        for hm in ("05:00", "12:00", "17:00", "18:00", "22:00"):
            t = local_ts(d, hm)
            if not (when(h6["off_air"]["start"]) <= t < when(h6["off_air"]["end"])):
                P(t, "OUT-02", "NEWSCAST", "EN", "Scheduled newscast", "", 1800 if hm != "22:00" else 2100)
        for hm in ("06:00", "12:00", "16:00"):
            P(local_ts(d, hm), "OUT-03", "NEWS PROGRAM", "EN", "Scheduled news program", "", 3600)
        if ef0 <= local_ts(d, "12:00") < ef1 + DAY:
            hours = range(24) if d < 30 else range(6, 24)
            for hh in hours:
                t = local_ts(d, f"{hh:02d}:00")
                if ef0 <= t < ef1 and not (when(kn["off_air"]["start"]) <= t < when(kn["off_air"]["end"])):
                    P(t, "OUT-08", "EMERGENCY UPDATE", "ES/EN", "Hourly emergency information block", "", 600)
    # --- call-ins to KNCB on D+2 (47 calls, mean 2.3 minutes, code-switching in 31)
    durs = rg.normal(138, 45, 47).clip(40, 320)
    durs = durs * (138 * 47 / durs.sum())
    flags = ["Y"] * 31 + ["N"] * 16
    flags = [flags[i] for i in rg.permutation(47)]
    topics = ["agua y hielo", "familiar desaparecido", "electricidad", "albergue", "ayuda de FEMA", "medicinas", "transporte", "escuelas"]
    for k in range(47):
        t = Z(2, "16:00") + int(2 * H * (k + rg.random()) / 47)
        calls.append([iso(t), "OUT-08", f"KNCB-CALL-0916-{k + 1:03d}", int(round(durs[k])), "ES", flags[k],
                      "agency names; street addresses; official document names" if flags[k] == "Y" else "", topics[int(rg.integers(len(topics)))]])
    prog.sort(); status.sort(); calls.sort()
    return prog, status, relay, jobs, calls


# ======================================================================================
# public record export
# ======================================================================================
def build_public_record():
    pr = load_json("02_public_record/public_record.json")
    chars = load_json("01_characters/characters.json")
    chars = {c["id"]: c for c in (chars.get("characters", chars) if isinstance(chars, dict) else chars)}
    places = load_json("00_scenario/places.json")
    places = {p["place_id"]: p["name"] for p in (places if isinstance(places, list) else places.get("places", []))}
    terms = load_json("02_public_record/restricted_terms.json")["terms"]
    never_ids = {"TANK-0390", "STATE-X", "GW-WS-IT-04", "GW-SYS-JMP-01"}
    # earliest same-day story citing each fact, so a statement is never dated after its coverage
    first_story = {}
    import glob as _g
    for fp in sorted(_g.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
        for s in json.load(open(fp, encoding="utf-8"))["stories"]:
            for f in s.get("tags", {}).get("public_facts", []):
                key = (f, s["day"])
                if key not in first_story or s["time_local"] < first_story[key]:
                    first_story[key] = s["time_local"]
    out, skipped = [], []
    for f in pr["facts"]:
        day = f["day"]
        text = f["statement"]
        bad = [t["pattern"] for t in terms if re.search(t["pattern"], text, re.I) and (t["public_from_day"] is None or day < t["public_from_day"])]
        if bad:
            skipped.append((f["id"], bad))
            continue
        if f.get("time_local"):
            hm = f["time_local"]
        else:
            rg = rng("ground", "pubtime", f["id"])
            hm = f"{int(rg.integers(8, 15)):02d}:{int(rg.integers(0, 4)) * 15:02d}"
            fs = first_story.get((f["id"], day))
            if fs and fs <= hm:
                h, m = map(int, fs.split(":"))
                tot = max(5, h * 60 + m - int(rg.integers(35, 95)))
                hm = f"{tot // 60:02d}:{tot % 60:02d}"
        t = local_ts(day, hm)
        issuer = f.get("source")
        speakers = []
        for cid in f.get("sources", []):
            c = chars.get(cid)
            if c and c.get("public_facing", True):
                org = (c["affiliation"].get("org") or "").replace(" (fictional)", "")
                who = " ".join([c["name"], c.get("role") or "", org])
                if any(re.search(t["pattern"], who, re.I) and (t["public_from_day"] is None or day < t["public_from_day"]) for t in terms):
                    continue                  # a speaker whose name or employer is not public yet is not listed
                speakers.append({"name": c["name"], "role": c.get("role") or "", "organization": org})
        if not issuer:
            orgs = [s["organization"] for s in speakers if s["organization"]]
            issuer = orgs[0] if orgs else (speakers[0]["name"] if speakers else "Public notice")
        issuer = re.sub(r"\s*[/(]?\s*\bOUT-\d+\)?\s*", " ", issuer).strip()
        ftype = f.get("type") or ("media_report" if any(k in issuer for k in ("Ledger", "Harborline", "Radio", "Wire", "Report", "Weekly")) else "official_statement")
        pls = [places[p] for p in f.get("places", []) if p in places and p not in never_ids]
        l = local_dt(t)
        out.append({"id": f["id"], "issued_local": l.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":" + l.strftime("%z")[-2:], "date_local": l.strftime("%Y-%m-%d"),
                    "time_local": hm, "issuer": issuer, "type": ftype, "text": text, "speakers": speakers, "places": pls, "_t": t})
    # notices that canon events describe but the fact list does not carry as separate statements
    extra = [
        ("NOTICE-NCOEM-2027-0912-01", local_ts(-2, "14:40"), "Nueces County Office of Emergency Management", "official_notice",
         "CORRECTION FROM NUECES COUNTY EMERGENCY MANAGEMENT: Posts circulating online name schools that are not county shelters. The only official shelters are the ones listed in the county evacuation order and at 2-1-1. "
         "Zavala Elementary is not an evacuation shelter. US-77 is open. Check the county shelter list before you travel.", ["Nueces County (FIPS 48355)"]),
        ("NOTICE-TDEM-2027-1005-01", Z(21, "19:00"), "Texas Division of Emergency Management", "interim_report",
         "TDEM interim after-action snapshot on public communications during Hurricane Rafael: 'Communication timelines in Spanish showed variation from English baseline. Recommend review of NCLAS contract performance.'",
         ["Nueces County (FIPS 48355)"]),
        ("NOTICE-LULAC-2027-1005-01", Z(21, "19:20"), "League of United Latin American Citizens (LULAC)", "complaint_filing",
         "Complaint TX-DEM-2027-LEP-0012 filed with the Texas Division of Emergency Management alleges violations of Texas LEP Plan Section 4.2 (simultaneous multi-language release for life-safety alerts) "
         "and Title VI, 42 U.S.C. 2000d, in the release of emergency alerts during Hurricane Rafael.", ["Nueces County (FIPS 48355)"]),
    ]
    for pid, t, issuer, typ, text, pls in extra:
        l = local_dt(t)
        out.append({"id": pid, "issued_local": l.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":" + l.strftime("%z")[-2:], "date_local": l.strftime("%Y-%m-%d"),
                    "time_local": l.strftime("%H:%M"), "issuer": issuer, "type": typ, "text": text, "speakers": [], "places": pls, "_t": t})
    out.sort(key=lambda r: (r["_t"], r["id"]))
    return out, skipped


# ======================================================================================
# shelters
# ======================================================================================
INTAKE_HEADER = ["arrival_local", "facility_id", "facility_name", "persons", "arrival_mode", "reference"]


def build_shelters():
    """Registry, daily census, intake log and 2-1-1 calls. The census is the sum of what arrived:
    evacuation buses (shelters/evacuation_bus_trips.csv), people who came on their own, and
    rescued persons delivered by boat, high-water vehicle or bus from the air station
    (the rescue log, through scripts/streams/_sar_shelter_flow.json). Run gen_ground.py first."""
    fac = {f["facility_id"]: f for f in reg("facility_registry")["facilities"]}
    rg = rng("ground", "shelters")
    flows = json.load(open(os.path.join(HERE, "_sar_shelter_flow.json"), encoding="utf-8"))["flows"]
    import csv as _csv
    with open(out_path("05_other_sources/shelters/evacuation_bus_trips.csv"), encoding="utf-8") as fh:
        bus = list(_csv.DictReader(fh))
    lt = lambda s_: int(dt.datetime.fromisoformat(s_).replace(tzinfo=UTC).timestamp()) + 5 * 3600       # CDT wall clock to epoch
    regrows, census, intake = [], [], []
    for fid, (od, ot, cd, peak) in SHELTER_PLAN.items():
        f = fac[fid]
        sh = f.get("shelter") or {}
        cap = sh.get("capacity") or 300
        name = f["facility_name"]
        zones = "/".join(sh.get("serves_evacuation_zones") or [])
        regrows.append([fid, name, f["address"], cap, local_iso(local_ts(od, ot))[:16], local_iso(local_ts(cd, "12:00"))[:16], zones or "post-landfall",
                        "Y" if sh.get("pets") else "N", "Y" if sh.get("medical_station") else "N", "Nueces County / American Red Cross"])
        t_open = local_ts(od, ot)
        # rescued persons: arrivals by day, and how many of them are still there each night
        sar_in = collections.defaultdict(list)
        stock = collections.Counter()
        for t, ffid, n, mode, ref, stay in flows:
            if ffid != fid:
                continue
            sar_in[day_of(t)].append((t, n, mode, ref))
        for t, ffid, n, mode, ref, stay in flows:
            if ffid == fid and stay:
                for d in range(day_of(t), day_of(t) + stay):
                    stock[d] += n
        nas = json.load(open(os.path.join(HERE, "_sar_shelter_flow.json"), encoding="utf-8")).get("onward", {}).get(fid, {})
        for d, n in nas.items():
            stock[int(d)] += n
        bus_in = collections.defaultdict(list)
        for r in bus:
            if r["facility_id"] == fid:
                t = lt(r["arrival_local"])
                bus_in[day_of(t)].append((t, int(r["passengers"]), "EVACUATION BUS", r["unit_id"]))
        prev = 0
        for d in range(od, cd + 1):
            base = shelter_base(fid, cap, d)
            occ = 0 if d == cd else base + stock[d]
            rows_d = list(bus_in[d]) + list(sar_in[d])
            got = sum(x[1] for x in rows_d)
            # people who came on their own: enough to reach the evening count, plus a little turnover
            base_prev = shelter_base(fid, cap, d - 1) if d > od else 0
            churn = int(rg.integers(0, max(2, base // 40 + 1))) if d < cd else 0
            own = max(0, base - base_prev - sum(x[1] for x in bus_in[d])) + churn
            lo = max(t_open, local_ts(d, "06:30")) if d == od else local_ts(d, "06:30")
            hi = local_ts(d, "22:30")
            if d == 0:
                lo = local_ts(0, "09:30")           # nobody travels during the landfall hours
            while own > 0 and d < cd:
                k = int(min(own, rg.choice([1, 1, 2, 2, 3, 4, 5, 6])))
                u = rg.beta(1.3, 2.2) if d < 0 else rg.beta(1.6, 1.6)
                rows_d.append((int(lo + (hi - lo) * u), k, "PRIVATE VEHICLE" if rg.random() < 0.82 else "WALK-IN", ""))
                own -= k; got += k
            arrivals = got
            departures = prev + arrivals - occ
            if departures < 0:                      # more room was used than arrived: the difference came on their own late in the day
                rows_d.append((int(local_ts(d, "21:00") + rg.uniform(0, 5000)), -departures, "PRIVATE VEHICLE", ""))
                arrivals -= departures; departures = 0
            for t, n, mode, ref in rows_d:
                intake.append([t, fid, name, n, mode, ref])
            es = round(float({"FAC-SHLT-027": 0.68, "FAC-SHLT-026": 0.52, "FAC-SHLT-007": 0.57, "FAC-SHLT-028": 0.74, "FAC-SHLT-006": 0.44, "FAC-SHLT-029": 0.41}[fid]
                             + rg.uniform(-0.04, 0.04)) * 100)
            staff = max(1, int(round(occ / 55))) if occ else 0
            biling = 0 if not occ else max(0 if d <= 2 else 1, int(round(staff * (0.12 if d <= 12 else 0.3))))
            census.append([(local_dt(local_ts(d, "12:00"))).strftime("%Y-%m-%d"), fid, name, cap, occ, arrivals, departures, es, 100 - es - (2 if occ else 0) if occ else 0,
                           staff, biling, "OPEN" if d < cd else "CLOSED"])
            assert occ <= cap, (fid, d, occ, cap)
            prev = occ
    regrows.sort(key=lambda r: (r[4], r[0])); census.sort()
    intake.sort()
    intake = [[local_iso(r[0])] + r[1:] for r in intake]
    # 2-1-1 shelter calls, D-3 to D+3
    calls = []
    zones = ["A", "B", "C", "D", "E"]
    topics = ["TRANSPORTATION TO SHELTER", "PETS AT SHELTER", "MEDICAL NEEDS AT SHELTER", "SHELTER CAPACITY", "WHICH SHELTER FOR MY ZONE", "ACCESSIBILITY", "WHAT TO BRING"]
    n = 0
    for d in range(-3, 4):
        count = {-3: 60, -2: 190, -1: 240, 0: 70, 1: 110, 2: 90, 3: 60}[d]
        for k in range(count):
            t = local_ts(d, "06:00") + int(rg.uniform(0, 16.5) * H)
            z = zones[int(rg.choice(5, p=[.34, .28, .2, .13, .05]))]
            topic = topics[int(rg.integers(len(topics)))]
            if d == -1 and local_ts(-1, "14:00") <= t < local_ts(-1, "20:00") and z == "D" and topic == "WHICH SHELTER FOR MY ZONE":
                topic = "TRANSPORTATION TO SHELTER"
            ref = {"A": "FAC-SHLT-007", "B": "FAC-SHLT-027", "C": "FAC-SHLT-028", "D": "FAC-SHLT-026", "E": ""}[z]
            calls.append([t, z, topic, "ES" if rg.random() < 0.38 else "EN", ref, ""])
    for k in range(14):
        t = local_ts(-1, "14:05") + int((6 * H - 600) * (k + rg.random()) / 14)
        calls.append([t, "D", "SHELTER LOCATION CLARIFICATION", "ES", "FAC-SHLT-026", "CALLER HEARD ZONE D SHELTER NAMED AS COLLIER ON RADIO; ADVISED RICHARD KING HIGH SCHOOL"])
    calls.sort()
    crow = []
    for t, z, topic, lang, ref, note in calls:
        n += 1
        crow.append([local_iso(t)[:10], local_iso(t), f"211-{local_dt(t):%m%d}-{n:05d}", z, topic, lang, ref, note])
    return regrows, census, crow, intake


# ======================================================================================
# damage assessment
# ======================================================================================
LV = ["DST", "MAJ", "MIN", "AFF", "NVD"]
FFH = {"Slab": 0.5, "Pier and beam": 2.5, "Elevated": 9.0}      # first floor above grade, ft
LANDFALL_PT = (27.834, -97.061)                                 # Port Aransas


def flood_level(depth, found, occ):
    """Damage level from the high-water mark above grade and the height of the first floor."""
    inside = depth - FFH[found]
    if occ == "RES-MH":                      # manufactured homes: water over the floor is a loss
        return "DST" if inside >= 2.0 else "MAJ" if inside >= 0.0 else "AFF" if depth > 0.2 else "NVD"
    if inside >= 6.5:
        return "DST"
    if inside >= 1.5:
        return "MAJ"
    if inside > 0.0:
        return "MIN"
    return "AFF" if depth > 0.2 else "NVD"


def wind_level(roof):
    return "DST" if roof >= 80 else "MAJ" if roof >= 40 else "MIN" if roof >= 15 else "AFF" if roof >= 3 else "NVD"


def work_time(rg, d0, d1, h0, h1, sunday=0.15):
    """A local working-hours timestamp between scenario days d0 and d1 (few Sundays)."""
    while True:
        d = int(rg.integers(d0, d1 + 1))
        if local_dt(local_ts(d, "12:00")).weekday() == 6 and rg.random() > sunday:
            continue
        return local_ts(d, "00:00") + int(rg.triangular(h0, (h0 + h1) / 2 - 0.5, h1) * H)


def build_damage():
    g = Ground()
    rg = rng("ground", "damage")
    areas = [a for a in reg("areas")["areas"] if a["area_type"] == "census_tract" and a.get("bbox") and a.get("reference_point")]
    zips = [a for a in reg("areas")["areas"] if a["area_type"] == "zip"]
    zw = {"A": 3.0, "B": 2.0, "C": 0.8, "D": 0.3}
    w = np.array([a["population"] * zw[a["evacuation_zone"]] for a in areas], float)
    n_per = np.floor(w / w.sum() * 12000).astype(int)
    n_per[0] += 12000 - n_per.sum()
    spill_zone = {"Hillcrest", "Port/Channel N", "Port/Channel S", "North Beach", "Rincon Point"}
    barrier = {"Mustang Island N", "East Flats"}
    open_coast = {"North Beach", "Rincon Point", "Flour Bluff Shore", "Padre Island NW"}
    surge_mean = {"A": 4.3, "B": 2.1, "C": 0.8, "D": 0.4}        # ft above grade where water reached
    p_wet = {"A": 0.92, "B": 0.72, "C": 0.30, "D": 0.05}
    structs, seen = [], set()
    for a, n in zip(areas, n_per):
        if n <= 0:
            continue
        locs = g.sample_locations(a["bbox"], int(n), rng("ground", "structures", a["tract"]), setback=(14.0, 30.0))
        rp = (a["reference_point"]["latitude"], a["reference_point"]["longitude"])
        z = min(zips, key=lambda q: geo.dist_m(rp, (q["reference_point"]["latitude"], q["reference_point"]["longitude"])))["zip"]
        name = a["neighbourhood_name"]
        zone = a["evacuation_zone"]
        city = "Port Aransas" if name in barrier else "Robstown" if name.startswith("Robstown") else "Corpus Christi"
        km = geo.dist_m(rp, LANDFALL_PT) / 1000.0
        wind_mean = 6.0 + 50.0 * math.exp(-km / 24.0)            # mean roof loss, percent
        for p in locs:
            while (p["street"], p["number"]) in seen:            # one structure per street number
                p = dict(p, number=p["number"] + 2)
            seen.add((p["street"], p["number"]))
            typ = "Residential" if rg.random() < 0.86 else ("Commercial" if rg.random() < 0.8 else "Public")
            if typ == "Residential":
                occ = ["RES-SFD", "RES-MF", "RES-MH"][int(rg.choice(3, p=[.68, .21, .11]))]
            else:
                occ = "COM" if typ == "Commercial" else "GOV"
            coastal = zone == "A"
            if occ == "RES-SFD":
                stories = 1 if rg.random() < 0.76 else 2
                sqft = int(np.clip(rg.lognormal(7.42, 0.33) * (1.35 if stories == 2 else 1.0), 760, 5200))
                found = ["Slab", "Pier and beam", "Elevated"][int(rg.choice(3, p=[.50, .22, .28] if coastal else [.66, .30, .04]))]
                year = int(rg.integers(1948, 2025))
            elif occ == "RES-MF":
                stories = int(rg.choice([1, 2, 3], p=[.15, .6, .25]))
                sqft = int(rg.integers(3200, 9000) * stories)
                found = "Elevated" if coastal and rg.random() < 0.15 else "Slab"
                year = int(rg.integers(1958, 2025))
            elif occ == "RES-MH":
                stories = 1
                sqft = int(rg.integers(620, 1090)) if rg.random() < 0.6 else int(rg.integers(1100, 1820))
                found = ["Pier and beam", "Slab", "Elevated"][int(rg.choice(3, p=[.86, .06, .08]))]
                year = int(rg.integers(1972, 2024))
            else:
                stories = 1 if rg.random() < 0.72 else 2
                sqft = int(np.clip(rg.lognormal(8.7, 0.8), 1400, 90000))
                found = "Slab" if rg.random() < 0.93 else "Pier and beam"
                year = int(rg.integers(1950, 2025))
            if found == "Elevated" and stories == 1 and occ == "RES-SFD" and rg.random() < 0.3:
                stories = 2
            # hazard at the structure
            expo = 1.75 if name in barrier else 1.2 if name in open_coast else 1.0
            depth = 0.0
            if rg.random() < min(0.99, p_wet[zone] * (1.08 if expo > 1 else 1.0)):
                depth = float(min(14.0, rg.gamma(3.2, surge_mean[zone] * expo / 3.2)))
            m = wind_mean * (1.7 if occ == "RES-MH" else 1.0) * (1.25 if year < 1980 else 0.78 if year >= 2002 else 1.0) / 100.0
            m = min(0.9, m)
            roof = float(100 * rg.beta(1.9 * m / (1 - m) if m < 0.5 else 1.9, 1.9 if m < 0.5 else 1.9 * (1 - m) / m))
            depth = round(depth, 1)
            roof = int(round(roof))
            fl, wl = flood_level(depth, found, occ), wind_level(roof)
            true = fl if LV.index(fl) <= LV.index(wl) else wl
            # what a classifier sees from above: the roof, debris fields and collapse; not the water line inside
            seen_score = roof + rg.normal(0, 5.0)
            if fl == "DST":
                seen_score = max(seen_score, rg.uniform(62, 100) if rg.random() < 0.72 else rg.uniform(30, 62))
            elif fl == "MAJ":
                seen_score += rg.uniform(0, 26) if rg.random() < 0.5 else 0.0      # debris line, contents at the kerb
            structs.append({"loc": p, "tract": a["tract"], "name": name, "zone": zone, "zip": z, "city": city, "typ": typ, "occ": occ, "year": year,
                            "sqft": sqft, "stories": stories, "found": found, "depth": depth, "roof": roof, "true": true, "score": float(seen_score)})
    # the automated classifier flags exactly 2,100 major and 390 destroyed (EVT-1104): the 390 and 2,100 highest scores
    order = sorted(range(len(structs)), key=lambda i: -structs[i]["score"])
    for rank, i in enumerate(order):
        sc = structs[i]["score"]
        structs[i]["ai"] = "DST" if rank < 390 else "MAJ" if rank < 2490 else "MIN" if sc >= 15 else "AFF" if (sc >= 4 or structs[i]["depth"] > 0.5) else "NVD"
    cut = (structs[order[389]]["score"], structs[order[2489]]["score"])
    tc = collections.Counter(s["true"] for s in structs)
    print(f"  damage: true levels {dict(tc)}; classifier cut scores destroyed {cut[0]:.0f}, major {cut[1]:.0f}")
    assert 4200 <= tc["DST"] + tc["MAJ"] <= 5800, tc
    rows = []
    for i, s in enumerate(structs):
        sid = f"CC-{100001 + i}"
        p = s["loc"]
        base = [sid, s["typ"], f"{address(p).title()}, {s['city']} TX {s['zip']}", s["city"], s["zip"], s["tract"], f"{p['lat']:.6f}", f"{p['lon']:.6f}"]
        attrs = [s["occ"], s["year"], s["sqft"], s["stories"], s["found"]]
        ai_roof = int(np.clip(round(s["score"]), 0, 100))

        def add(level, atype, t, assessor, depth, roof, note=""):
            rows.append(base + [level, atype, local_iso(t)[:16], assessor] + attrs + [depth, roof, note, "DR-4821-TX"])

        if rg.random() < 0.12 and s["zone"] in ("A", "B"):       # fire crews' windshield survey once crews are released: daylight, from the street
            d = int(rg.choice([0, 1, 2], p=[.2, .4, .4]))
            t = local_ts(d, "00:00") + int(rg.uniform(13.0 if d == 0 else 7.2, 19.3) * H)
            coarse = "MAJ" if s["true"] in ("DST", "MAJ") else ("MIN" if s["true"] in ("MIN", "AFF") else "NVD")
            add(coarse, "RS", t, "Corpus Christi Fire Department", "", "", "windshield survey")
        # automated classification: imagery flown in daylight on D+3..D+5, classified one to five hours after the flight lands
        d = int(rg.integers(3, 6))
        t_ai = local_ts(d, "00:00") + int((rg.uniform(8.0, 18.4) + rg.uniform(1.0, 5.0)) * H)
        add(s["ai"], "AI", t_ai, "FEMA aerial survey contractor (Argus Aerial Systems)", "", ai_roof if s["ai"] != "NVD" else 0, "automated classification of aerial imagery")
        hot = s["true"] in ("DST", "MAJ", "MIN") or s["ai"] in ("DST", "MAJ", "MIN")
        if rg.random() < (0.55 if hot else 0.3):
            slow = s["name"] in spill_zone
            d0, d1 = (20, 41) if slow else ((6, 30) if s["zone"] in ("A", "B") else (6, 22))
            t = work_time(rg, d0, d1, 7.5, 18.2)
            add(s["true"], "FV", t, "Joint FEMA / State / County assessment team", s["depth"], s["roof"], "access delayed: spill-zone restrictions" if slow else "")
            s["fv"] = True
        if s["typ"] == "Residential" and s["true"] in ("DST", "MAJ", "MIN") and rg.random() < (0.55 if s.get("fv") else 0.42):
            t = work_time(rg, 61, 119, 8.0, 17.6, sunday=0.03)
            add(s["true"], "HI", t, "FEMA housing inspection", s["depth"], s["roof"], "Individual Assistance inspection")
    rows.sort(key=lambda r: (r[10], r[0]))
    # utility site surveys (Phase 1 D+3..D+5 optical in daylight, Phase 2 D+8 pre-dawn thermal, thermal corridor pass D+11, water plant D+15)
    assets = reg("infrastructure_assets")["assets"]
    sites = [a for a in assets if a.get("latitude") is not None and any(k in str(a.get("asset_type", "")).lower() for k in ("substation", "plant", "pump", "lift", "wastewater", "switch"))][:23]
    byid = {a["asset_id"]: a for a in assets}
    wtp = next((a for a in assets if "O.N. Stevens" in str(a.get("name", ""))), None)
    # Phase 2 tile sets as flown (drone flight log); the plan below is the fallback when that log is not on disk
    p2 = {"GW-FAC-SUB-01": ("FEMA-UAV-0922-UTL-01", "2027-09-22T10:08:00Z", 1210), "GW-FAC-SUB-02": ("FEMA-UAV-0922-UTL-02", "2027-09-22T10:34:00Z", 1247),
          "GW-FAC-SUB-03": ("FEMA-UAV-0922-UTL-03", "2027-09-22T11:02:00Z", 1180), "GW-FAC-SUB-04": ("FEMA-UAV-0922-UTL-04", "2027-09-22T11:26:00Z", 1105),
          "GW-FAC-SUB-05": ("FEMA-UAV-0922-UTL-05", "2027-09-22T11:50:00Z", 1090)}
    if wtp:
        p2[wtp["asset_id"]] = ("FEMA-UAV-0922-UTL-06", "2027-09-22T11:10:00Z", 2100)
    p2_end = "2027-09-22T12:04:00Z"
    fl_path = out_path("05_other_sources/drone_video/logs/flight_log.csv")
    if os.path.exists(fl_path):
        import csv as _csv
        with open(fl_path, encoding="utf-8") as fh:
            flown = {r["tile_set_id"]: r for r in _csv.DictReader(fh) if r.get("tile_set_id", "").startswith("FEMA-UAV-0922-UTL-")}
        for k, (ts_id, t0, n) in list(p2.items()):
            if ts_id in flown:
                p2[k] = (ts_id, flown[ts_id]["acquisition_start_utc"], int(flown[ts_id]["tiles"]))
        if flown:
            p2_end = max(r["acquisition_end_utc"] for r in flown.values())
    srows = []
    obs = ["NO VISIBLE DAMAGE", "FENCE DOWN ONE SIDE", "DEBRIS IN YARD", "STANDING WATER IN YARD", "ROOF PANEL MISSING ON CONTROL HOUSE", "ACCESS ROAD WASHED OUT"]
    for a in sites:
        t = local_ts(int(rg.integers(3, 6)), "00:00") + int(rg.uniform(8.2, 18.3) * H)
        srows.append([a["asset_id"], a.get("name", ""), a["latitude"], a["longitude"], iso(t), "PHASE 1 RAPID", "RGB", "", int(rg.integers(8, 40)),
                      "FLOODED" if rg.random() < 0.3 else "DRY", obs[int(rg.integers(len(obs)))], ""])
        is_sub = "substation" in str(a.get("asset_type", "")).lower()
        if a["asset_id"] in p2 and a["asset_id"] != "GW-FAC-SUB-02":
            ts_id, t0, n = p2[a["asset_id"]]
            srows.append([a["asset_id"], a.get("name", ""), a["latitude"], a["longitude"], t0, "PHASE 2 UTILITY", "LWIR 12 cm", ts_id, n,
                          "RECEDED" if rg.random() < 0.5 else "DRY", obs[int(rg.integers(3))], "ALL FEEDER BAYS CARRYING LOAD" if is_sub else ""])
        if is_sub or a is wtp:
            t3 = Z(11, "09:15") + int(rg.uniform(0.05, 1.5) * H)
            srows.append([a["asset_id"], a.get("name", ""), a["latitude"], a["longitude"], iso(t3), "THERMAL PASS", "TIR", "FEMA-AER-2027-0925-TIR", int(rg.integers(10, 30)), "DRY", "", ""])
    sub2 = byid.get("GW-FAC-SUB-02")
    if sub2:
        ts_id, t0, n = p2["GW-FAC-SUB-02"]
        srows.append(["GW-FAC-SUB-02", sub2.get("name", ""), sub2["latitude"], sub2["longitude"], t0, "PHASE 2 UTILITY", "LWIR 12 cm", ts_id, n, "RECEDED",
                      "NO VISIBLE STORM DAMAGE TO FEEDER BAYS", "FEEDER BREAKER B2-A CONTACTS OPEN, BAY AT AMBIENT TEMPERATURE"])
    if wtp:
        srows.append([wtp["asset_id"], wtp.get("name", ""), wtp["latitude"], wtp["longitude"], iso(Z(15, "13:00")), "PHASE 2 WATER PLANT", "RGB 3 cm + multispectral", "FEMA-AER-2027-0929-WTP", 2100, "DRY",
                      "PUMP STATION C ROOF: ABOUT 40 SQ M OF ROOFING MISSING", "SETTLING TANK FILL ANALYSIS (SPECTRAL REFLECTANCE): ABOUT 60 PCT OF NORMAL THROUGHPUT"])
    srows.sort(key=lambda r: (r[4], r[0]))
    p2_start = min(v[1] for v in p2.values())
    coll = [
        ["FEMA-AER-2027-0912-BASE", iso(Z(-2, "14:00")), iso(Z(-2, "16:00")), "PRE-EVENT BASELINE", "RGB", 847, "about 94 percent of metro utility infrastructure", "utility sites, port, air station perimeter"],
        ["FEMA-AER-2027-0917-P1", iso(local_ts(3, "07:00")), iso(local_ts(5, "18:30")), "PHASE 1 RAPID DAMAGE", "RGB", 412000, "all evacuation zones", "structures; classifier output 2,100 major and 390 destroyed"],
        ["FEMA-AER-2027-0922-P2", p2_start, p2_end, "PHASE 2 UTILITY", "LWIR 12 cm, flown before sunrise", sum(v[2] for v in p2.values()), f"{len(p2)} utility infrastructure sites", "substations and the water treatment plant"],
        ["FEMA-AER-2027-0925-TIR", iso(Z(11, "09:15")), iso(Z(11, "11:15")), "THERMAL INFRARED PASS", "TIR", 1900, "utility corridor", "substations and feeders"],
        ["FEMA-AER-2027-0929-WTP", iso(Z(15, "13:00")), iso(Z(15, "15:00")), "PHASE 2 WATER PLANT", "RGB 3 cm + multispectral", 2100, "O.N. Stevens Water Treatment Plant", "settling tanks, pump stations"],
        ["FEMA-OD-2027-CC-AERIAL", iso(Z(-2, "14:00")), iso(Z(45, "17:00")), "PROGRAM COMPLETE - OPEN DATA RELEASE", "RGB 30 cm public resolution", 6200000, "full program, pre-event baseline through completion", "public release"],
    ]
    return rows, srows, coll


DAMAGE_HEADER = ["structure_id", "structure_type", "address", "city", "zip", "census_tract", "LATITUDE", "LONGITUDE", "DMG_LEVEL", "ASMT_TYPE", "ASMT_DATE", "ASSESSOR",
                 "OCCUPANCY", "YEAR_BUILT", "SQ_FT", "STORIES", "FOUNDATION", "FLOOD_DEPTH_FT", "ROOF_DAMAGE_PCT", "ACCESS_NOTE", "INCIDENT_NUMBER"]


def main():
    # retire the pre-regeneration files only (recognised by their old columns), never this generator's own output
    for rel, old_col in (("05_other_sources/infrastructure/damage_assessment.csv", "COMMENTS"), ("05_other_sources/public_health/eas_broadcasts.csv", "NoteOnDelay")):
        fp = os.path.join(ROOT, rel)
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as fh:
                if old_col in fh.readline().strip().split(","):
                    retire([rel])
    alerts = build_alerts()
    n = write_csv("05_other_sources/public_health/eas_broadcasts.csv", ALERT_HEADER, ([a[k] for k in ALERT_HEADER] for a in alerts))
    print(f"eas_alerts: {n} rows ({sum(1 for a in alerts if a['EventCode'] not in ('RWT', 'RMT'))} alerts, rest required tests)")
    prog, status, relay, jobs, calls = build_broadcast(alerts)
    write_csv("05_other_sources/broadcast/station_program_log.csv", ["air_time_utc", "station_id", "station_name", "platform", "item", "language", "alert_id", "duration_sec", "description"], prog)
    write_csv("05_other_sources/broadcast/station_status_log.csv", ["air_time_utc", "station_id", "station_name", "status", "note"], status)
    write_csv("05_other_sources/broadcast/alert_relay_log.csv", ["alert_id", "station_id", "station_name", "received_utc", "relay_lag_sec", "result"], relay)
    write_csv("05_other_sources/broadcast/translation_jobs.csv", ["job_id", "alert_id", "translator", "source_received_utc", "translation_delivered_utc", "first_aired_utc", "service_level_hours", "status", "note"], jobs)
    write_csv("05_other_sources/broadcast/call_in_log.csv", ["air_time_utc", "station_id", "call_id", "duration_sec", "primary_language", "code_switching", "english_insertions", "topic"], calls)
    print(f"broadcast_logs: programme {len(prog)}, status {len(status)}, relay {len(relay)}, translation jobs {len(jobs)}, call-ins {len(calls)}")
    recs, skipped = build_public_record()
    by_month = collections.defaultdict(list)
    for r in recs:
        by_month[r["date_local"][:7]].append({k: v for k, v in r.items() if not k.startswith("_")})
    import glob as _g
    for f in _g.glob(out_path("05_other_sources/press_releases/x").replace("x", "*.jsonl")):
        os.remove(f)
    for mth, rows in sorted(by_month.items()):
        write_jsonl(f"05_other_sources/press_releases/statements_{mth}.jsonl", rows)
    print(f"public_record: {len(recs)} statements in {len(by_month)} files; withheld {len(skipped)} {skipped[:3]}")
    regrows, census, crow, intake = build_shelters()
    write_csv("05_other_sources/shelters/shelter_intake_log.csv", INTAKE_HEADER, intake)
    write_csv("05_other_sources/shelters/shelter_registry.csv", ["facility_id", "facility_name", "address", "capacity", "opened_local", "closed_local", "evacuation_zones_served", "pets", "medical_station", "operator"], regrows)
    write_csv("05_other_sources/shelters/shelter_daily_census.csv", ["date_local", "facility_id", "facility_name", "capacity", "occupancy", "new_arrivals", "departures", "spanish_speaking_pct", "english_speaking_pct", "staff_on_duty", "bilingual_staff_on_duty", "status"], census)
    write_csv("05_other_sources/shelters/shelter_211_calls.csv", ["date_local", "call_time_local", "call_id", "caller_evacuation_zone", "topic", "language", "referred_facility_id", "note"], crow)
    print(f"shelters: registry {len(regrows)}, census {len(census)}, intake rows {len(intake)}, 2-1-1 calls {len(crow)}")
    rows, srows, coll = build_damage()
    write_csv("05_other_sources/infrastructure/damage_assessment.csv", DAMAGE_HEADER, rows)
    write_csv("05_other_sources/infrastructure/utility_site_survey.csv", ["asset_id", "asset_name", "LATITUDE", "LONGITUDE", "survey_time_utc", "phase", "sensor", "tile_set_id", "tiles", "yard_flood_status", "visible_condition", "equipment_observation"], srows)
    write_csv("05_other_sources/infrastructure/aerial_survey/collection_index.csv", ["collection_id", "start_utc", "end_utc", "phase", "sensor", "tiles", "coverage", "targets"], coll)
    print(f"damage_assessment: {len(rows)} assessment rows, {len(srows)} utility site surveys, {len(coll)} collections")


if __name__ == "__main__":
    main()
