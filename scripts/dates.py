"""Print calendar dates for scenario days.  Usage: python scripts/dates.py [start_day] [end_day]"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load

def date_for_day(day):
    d0 = datetime.date.fromisoformat(load("00_scenario/config.json")["d0_date"])
    return d0 + datetime.timedelta(days=day)

def tz_for_date(d):
    """Zone label for local noon on date d, from the scenario's local_timezone (IANA name)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(load("00_scenario/config.json").get("local_timezone", "America/Chicago"))
    dt = datetime.datetime(d.year, d.month, d.day, 12, tzinfo=tz)
    off = int(dt.utcoffset().total_seconds() // 3600)
    return f"{dt.tzname()} (UTC{off:+d})"

def utc_offset_hours(d):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(load("00_scenario/config.json").get("local_timezone", "America/Chicago"))
    return int(datetime.datetime(d.year, d.month, d.day, 12, tzinfo=tz).utcoffset().total_seconds() // 3600)

if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else -60
    b = int(sys.argv[2]) if len(sys.argv) > 2 else a
    for day in range(a, b + 1):
        d = date_for_day(day)
        print(f"day {day:+4d}  {d.isoformat()}  {d.strftime('%A')}  {tz_for_date(d)}")
