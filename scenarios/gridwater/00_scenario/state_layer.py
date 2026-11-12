"""State layer for scenario gridwater (Operation DRIFTGLASS).

Called by scripts/build_world_state.py via build(api, scenario).

Variables added (all prefixed gw_):
  State (categorical):
    gw_sub01_status    — Riverside Switching Station (GW-FAC-SUB-01)
    gw_sub02_status    — Harbor View Substation (GW-FAC-SUB-02)
    gw_sub03_status    — Crosstown Substation (GW-FAC-SUB-03)
    gw_sub04_status    — Southside Substation (GW-FAC-SUB-04)
    gw_pump_p3_status  — FAC-UTL-01 Pump P-3 (O.N. Stevens)
    gw_scada_isolated  — GW-SYS-SCADA-01 network isolation flag

  Numeric (hourly):
    gw_grid_outage_customers  — customers without power, Corpus Christi
    gw_zone4_pressure_psi     — Zone 4 distribution pressure (psi)
    gw_alarm_suppressed_count — count of active alarm suppressions in SCADA

Events added (GW-EVT-*) are loaded from msel.json and merged by build_world_state.py.
This file only registers state variables.

Design note: values here represent OBSERVABLE telemetry — what a SCADA historian,
outage-management system or water-pressure sensor would record.  They do NOT encode
attack technique; they encode the effect that technique produced.
"""

from math import floor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _storm_outage_customers(H, t, api):
    """Approximate genuine storm-related outage customer count from the
    gw_grid_outage_customers variable is built BELOW.  Here we just need
    a helper for the baseline storm curve so we can add the adversary-caused
    increment on top.

    Storm curve (customers without power, Corpus Christi city):
      D-1 to D0+0h : ~0 (pre-storm normal)
      D0+6h (landfall +0h): 0 → 72,000 ramp over 4 hours
      D0+10h : 72,000 peak storm outage
      D0+10h → D+7 : linear restoration from 72,000 → 48,000 (normal restoration pace)
      D+7 : adversary re-trips SUB-02 → jumps +8,400
      D+10 : adversary re-trips SUB-03 → jumps +6,800
      D+10 → D+28 : slow restoration (manual ops + adversary interference) → 36,000
      D+28 (SCADA isolation, manual restore begins) → D+35 → 3,200 → 0
    """
    # D0 = hour 0 in the shared timeline; t is hours from D0
    if t < 0:
        return 0.0

    # Storm ramp: 0 to 72,000 over hours 6-10
    if t < 6:
        return 0.0
    if t <= 10:
        return (t - 6) / 4.0 * 72_000
    # Storm restoration: 72,000 → 48,000 over D0+10h to D+7 (10h → 168h)
    if t <= 168:
        base = 72_000 - (t - 10) / (168 - 10) * (72_000 - 48_000)
        return base

    # D+7: adversary re-trips SUB-02 at H(7, 9, 30) ≈ t=177.5
    # D+10: adversary re-trips SUB-03 at H(10, 14, 45) ≈ t=254.75
    # Until SUB-02 trip:
    if t < 177.5:
        base = 48_000
        return base

    # After SUB-02 trip, before SUB-03 trip: 48,000 + 8,400 spike, then slow restore
    if t < 254.75:
        # Slow restore from 56,400 at a rate of ~300/day (storm progress very slow)
        hours_since_sub02 = t - 177.5
        base = 56_400 - hours_since_sub02 / 24 * 300
        return max(base, 50_000)

    # After SUB-03 trip: 50,000 + 6,800 = 56,800
    if t < 672:  # D+28
        hours_since_sub03 = t - 254.75
        base = 56_800 - hours_since_sub03 / 24 * 500
        return max(base, 36_000)

    # D+28 to D+35: manual ops restore 36,000 → 3,200
    if t <= 840:
        base = 36_000 - (t - 672) / (840 - 672) * (36_000 - 3_200)
        return max(base, 3_200)

    # D+35 to D+36: final burst 3,200 → 0
    if t <= 864:
        base = 3_200 - (t - 840) / 24 * 3_200
        return max(base, 0)

    return 0.0


def _zone4_pressure(t):
    """Zone 4 distribution pressure (psi).
      Pre-storm nominal: 60 psi
      D0 to D+9: drops to 40 psi due to power disruption at FAC-UTL-01 (T1 event)
      D+9: adversary lowers P-3 setpoint → drops to ~25 psi over 8h
      D+10: SUB-03 trip cuts P-4 → drops to 14 psi over 2h
      D+10 to D+28: stays at 14–17 psi (no intervention; alarm suppressed)
      D+28: setpoint restored, P-4 feeder restored → rises to 32 psi over 2h, then 40 psi by D+30
      D+42: certified at 41+ psi
    """
    if t < 0:
        return 60.0
    # D0 to D+9: storm damage to FAC-UTL-01 power drops pressure
    if t <= 216:  # D+9
        base = 60 - (t / 216) * 20   # 60 → 40
        return max(base, 40.0)
    # D+9 to D+9+8h: setpoint manipulation drives pressure down
    if t <= 224:
        base = 40 - (t - 216) / 8 * 15   # 40 → 25
        return max(base, 25.0)
    # D+10 (254.75) SUB-03 cuts P-4 feeder → drops to 14
    if t <= 254.75:
        return 25.0
    if t <= 258:
        base = 25 - (t - 254.75) / 3.25 * 11  # 25 → 14
        return max(base, 14.0)
    # D+10 to D+28: stagnant at 14–17 (slow tank drain adds minor fluctuation)
    if t <= 672:
        import math
        return 14.0 + 1.5 * (1 + math.sin(t * 0.07))  # 14–17 oscillation
    # D+28: setpoint restored, rises
    if t <= 680:
        base = 14 + (t - 672) / 8 * 18  # → 32
        return min(base, 32.0)
    if t <= 720:
        base = 32 + (t - 680) / 40 * 8  # → 40
        return min(base, 40.0)
    # D+42: certified 41+ psi; approach 41 smoothly
    if t <= 1008:
        return 40.0 + (t - 720) / (1008 - 720) * 1.5
    return 41.5


def _alarm_suppression_count(t):
    """Count of SCADA alarm suppressions active.
    0 normally → 5 added on D-3 (relay trip alarms + Zone 4 pressure alarm)
    → 5 until D+28 when SCADA is isolated and rebuilt → 0.
    """
    if t < -72:   # D-3 = -72 hours
        return 0
    if t < 672:   # D+28
        return 5
    return 0


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build(api, scenario):
    H = api["H"]      # H(day, hh, mm) → t in hours
    C = api["C"]      # semantic palette: "ok","warn","severe","hidden","info","watch","none","calm", etc.
    # Thread colors from scenario registry (fall back to semantic keys)
    TC = scenario.get("thread_colors", {})
    T8_COLOR  = TC.get("T8", C["watch"])    # amber — grid intrusion
    T9_COLOR  = TC.get("T9", C["restore"])  # teal — water SCADA
    T10_COLOR = TC.get("T10", C["hidden"])  # purple — hiding in storm

    # ---- Substation status variables (categorical) -------------------------

    api["state"]("gw_sub01_status",
        [
            (H(-60, 0, 0), "online"),
            (H(0, 7, 12), "tripped"),        # D0 07:12Z — relay undervoltage (modified threshold)
            (H(1, 12, 0), "online"),          # D+1: restoration after storm-sag clears
            # remains online through the scenario (not retargeted after D0)
        ],
        label="GW-FAC-SUB-01 (Riverside)",
        states={"online": "#3f8f6b", "tripped": "#c8402f"},
        group="Water & power",
        color=T8_COLOR,
        unit="status",
        thread="T8",
        note="Adversary-modified relay (0.94 pu trip threshold vs 0.88 pu nominal) caused premature trip at D0. Restored D+1."
    )

    api["state"]("gw_sub02_status",
        [
            (H(-60, 0, 0), "online"),
            (H(0, 6, 0), "degraded"),         # D0 landfall — partial storm damage
            (H(6, 18, 0), "online"),           # D+6: partially restored
            (H(7, 9, 30), "tripped"),          # D+7: adversary sends OPEN command remotely
            (H(35, 20, 14), "online"),         # D+35: manual relay reset, fully restored
        ],
        label="GW-FAC-SUB-02 (Harbor View)",
        states={"online": "#3f8f6b", "degraded": "#e07a1f", "tripped": "#c8402f"},
        group="Water & power",
        color=T8_COLOR,
        unit="status",
        thread="T8",
        note="Adversary remote breaker-open at D+7 during restoration. Re-energized D+35 after relay audit."
    )

    api["state"]("gw_sub03_status",
        [
            (H(-60, 0, 0), "online"),
            (H(0, 6, 0), "degraded"),
            (H(5, 10, 0), "online"),           # D+5: restored
            (H(10, 19, 45), "tripped"),        # D+10: adversary OPEN command
            (H(35, 20, 14), "online"),         # D+35: restored with SUB-02
        ],
        label="GW-FAC-SUB-03 (Crosstown)",
        states={"online": "#3f8f6b", "degraded": "#e07a1f", "tripped": "#c8402f"},
        group="Water & power",
        color=T8_COLOR,
        unit="status",
        thread="T8",
        note="Second adversary remote OPEN at D+10; also cut backup feeder to FAC-UTL-01 pump room."
    )

    api["state"]("gw_sub04_status",
        [
            (H(-60, 0, 0), "online"),
            (H(0, 6, 0), "degraded"),
            (H(8, 14, 0), "online"),           # D+8: restored
            # Relay file was written on D-3 but not configured to trip
        ],
        label="GW-FAC-SUB-04 (Southside)",
        states={"online": "#3f8f6b", "degraded": "#e07a1f"},
        group="Water & power",
        color=T8_COLOR,
        unit="status",
        thread="T8",
        note="Relay config file modified D-3 (unauthorized write detected D+16), but substation was not commanded to trip."
    )

    api["state"]("gw_pump_p3_status",
        [
            (H(-60, 0, 0), "normal"),
            (H(0, 6, 0), "reduced"),           # D0: storm causes partial power reduction
            (H(1, 18, 0), "normal"),           # D+1: power restored
            (H(9, 2, 4), "setpoint_lowered"),  # D+9 02:04Z: adversary lowers setpoint
            (H(28, 12, 14), "normal"),         # D+28 12:14Z: setpoint manually restored
        ],
        label="FAC-UTL-01 Pump P-3",
        states={"normal": "#3f8f6b", "reduced": "#e07a1f", "setpoint_lowered": "#c8402f"},
        group="Water & power",
        color=T9_COLOR,
        unit="status",
        thread="T9",
        note="Setpoint lowered from 85 to 68 psi by adversary at D+9; alarm suppression masked the effect for 3 days."
    )

    api["state"]("gw_scada_isolated",
        [
            (H(-60, 0, 0), "connected"),
            (H(28, 12, 0), "isolated"),        # D+28 12:00Z: CBPWA isolates SCADA on CISA guidance
            (H(35, 18, 0), "restored"),        # D+35: clean SCADA rebuilt and reconnected
        ],
        label="GW-SYS-SCADA-01 network status",
        states={"connected": "#3f8f6b", "isolated": "#c8402f", "restored": "#2a9d8f"},
        group="Cyber & information",
        color=C["calm"],
        unit="status",
        thread="T8",
        note="Isolation ended adversary access; also ended remote ERCOT visibility for 7 days."
    )

    # ---- Numeric variables (hourly) ----------------------------------------

    # Build grid outage customer count as hourly list from D-60 to D+119
    T_RANGE = range(-60 * 24, 120 * 24)   # hours: -1440 to 2880
    outage_vals = []
    for t in T_RANGE:
        v = _storm_outage_customers(H, t, api)
        outage_vals.append(round(v))

    api["number"]("gw_grid_outage_customers",
        outage_vals,
        t0=H(-60, 0, 0),
        label="Corpus Christi customers without power",
        group="Water & power",
        unit="customers",
        color=T8_COLOR,
        thread="T8",
        note="Combines genuine storm outage with adversary-caused increments (D+7 +8,400; D+10 +6,800). Normal storm-only restoration curve would have reached ~5,000 by D+21; adversary interference held it at 36,000."
    )

    # Zone 4 water pressure
    pressure_vals = []
    for t in T_RANGE:
        v = _zone4_pressure(t)
        pressure_vals.append(round(v, 1))

    api["number"]("gw_zone4_pressure_psi",
        pressure_vals,
        t0=H(-60, 0, 0),
        label="Zone 4 water distribution pressure",
        group="Water & power",
        unit="psi",
        color=T9_COLOR,
        thread="T9",
        note="Drops to 14 psi by D+10; regulatory threshold is 20 psi; boil water notice issued D+12. Remains below 20 psi until D+28 SCADA restoration."
    )

    # Active SCADA alarm suppressions
    suppress_vals = []
    for t in T_RANGE:
        suppress_vals.append(_alarm_suppression_count(t))

    api["number"]("gw_alarm_suppressed_count",
        suppress_vals,
        t0=H(-60, 0, 0),
        label="Active SCADA alarm suppressions",
        group="Cyber & information",
        unit="count",
        color=T10_COLOR,
        thread="T10",
        note="5 suppressions added D-3 17:09Z (same session as relay modifications). Masks relay trip alarms and Zone 4 low-pressure alarm until D+28 SCADA rebuild."
    )
