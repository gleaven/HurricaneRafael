import csv, os, sys, json, collections, datetime as dt
ROOT="."
SRC=ROOT+"/05_other_sources"
D0=dt.datetime(2027,9,14,tzinfo=dt.timezone.utc)
def rows(path):
    with open(path if path.startswith('/') else SRC+'/'+path, newline='', encoding='utf-8', errors='replace') as f:
        yield from csv.DictReader(f)
def load(path): return list(rows(path))
def ts(s):
    s=s.strip().replace(' ','T')
    if s.endswith('Z'): s=s[:-1]+'+00:00'
    d=dt.datetime.fromisoformat(s)
    if d.tzinfo is None: d=d.replace(tzinfo=dt.timezone.utc)
    return d
def local(d):
    off=-5 if d<dt.datetime(2027,11,7,7,tzinfo=dt.timezone.utc) else -6
    return d+dt.timedelta(hours=off)
def dday(d): return (local(d).date()-dt.date(2027,9,14)).days
def cnt(rs,col): return collections.Counter(r[col] for r in rs)
