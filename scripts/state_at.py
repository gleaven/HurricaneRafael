"""Look up the shared world state.
  python scripts/state_at.py 0 6              every variable at day 0, 06:00Z (landfall)
  python scripts/state_at.py 44 --var channel_status --var vessels_at_anchorage
  python scripts/state_at.py --changes channel_status    every change of one state variable
Generators import value_at(var_id, t) from here (t = hours from D0 00:00Z)."""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load

D = "09_shared_state_timeline/data/"
_V = load(D + "variables.json"); _S = load(D + "segments.json"); _N = load(D + "series_hourly.json")
VARS = {v["id"]: v for v in _V["variables"]}

def value_at(vid, t):
    if vid in _N["series"]:
        a = _N["series"][vid]; return a[max(0, min(len(a) - 1, int(round(t)) - _N["t0"]))]
    for s, e, val, _ in _S[vid]:
        if s <= t < e: return val
    return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("day", nargs="?", type=int); ap.add_argument("hour", nargs="?", type=int, default=18)
    ap.add_argument("--var", action="append"); ap.add_argument("--changes"); a = ap.parse_args()
    if a.changes:
        fmt = lambda t: f"D{t//24:+d} {t%24:02d}:00Z".replace("D+0 ", "D0 ")
        for s, e, val, _ in _S[a.changes]: print(f"{fmt(s):>14} -> {fmt(e):>14}  {val}")
        return
    t = a.day * 24 + a.hour; print(f"state at day {a.day:+d} {a.hour:02d}:00Z (t={t})")
    for vid in (a.var or VARS):
        v = VARS[vid]; print(f"  [{v['group']}] {v['label']}: {value_at(vid, t)} {v.get('unit','') if v['kind']=='number' else ''}  ({v['visibility']})")

if __name__ == "__main__":
    main()
