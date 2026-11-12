"""Build RSS 2.0 feeds: 03_news/rss/<outlet-slug>.xml per outlet and all.xml combined.
Public fields only (no internal ids or tags).  Dates come from config d0_date.
Usage: python scripts/build_rss.py"""
import sys, os, re, datetime
from xml.sax.saxutils import escape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import context, load_all_stories, path
from dates import date_for_day, tz_for_date, utc_offset_hours

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70]

def pubdate(day, hhmm):
    d = date_for_day(day)
    h, m = map(int, hhmm.split(":"))
    off = utc_offset_hours(d)
    dt = datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=datetime.timezone(datetime.timedelta(hours=off)))
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z"), dt

def item_xml(s, ctx):
    o = ctx["outlets"][s["outlet_id"]]
    pd, dt = pubdate(s["day"], s["time_local"])
    link = f'{o["site_url"]}/{dt.strftime("%Y/%m/%d")}/{slug(s["headline"])}'
    authors = ", ".join(ctx["characters"][b]["name"] for b in s["byline"])
    cats = [s["section"]] + [ctx["arcs"][a]["name"] for a in s["tags"].get("arcs", []) if a in ctx["arcs"]]
    html = "".join(f"<p>{escape(p)}</p>" for p in s["body"])
    out = ["    <item>",
           f"      <title>{escape(s['headline'])}</title>",
           f"      <link>{escape(link)}</link>",
           f"      <guid isPermaLink=\"false\">{escape(o['site_url'])}/id/{s['story_id']}</guid>",
           f"      <pubDate>{pd}</pubDate>",
           f"      <dc:creator>{escape(authors)}</dc:creator>",
           f"      <source url=\"{escape(o['feed_url'])}\">{escape(o['name'])}</source>"]
    out += [f"      <category>{escape(c)}</category>" for c in cats]
    out += [f"      <description>{escape(s['dek'])}</description>",
            f"      <content:encoded><![CDATA[{html}]]></content:encoded>",
            "    </item>"]
    return "\n".join(out), dt

def channel(title, link, desc, items):
    head = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">',
            "  <channel>", f"    <title>{escape(title)}</title>", f"    <link>{escape(link)}</link>",
            f"    <description>{escape(desc)}</description>", "    <language>en-us</language>"]
    return "\n".join(head + [x for x, _ in items] + ["  </channel>", "</rss>", ""])

def main():
    ctx = context()
    stories = load_all_stories()
    os.makedirs(path("03_news", "rss"), exist_ok=True)
    built = [(item_xml(s, ctx), s) for s in stories]
    built.sort(key=lambda t: t[0][1], reverse=True)
    allitems = [x for x, _ in built]
    with open(path("03_news", "rss", "all.xml"), "w", encoding="utf-8") as f:
        f.write(channel("Hurricane Rafael coverage (all outlets)", "https://coastal-bend-news.example",
                        "Combined fictional news feed for the Hurricane Rafael synthetic scenario.", allitems))
    for oid, o in ctx["outlets"].items():
        items = [x for x, s in built if s["outlet_id"] == oid]
        with open(path("03_news", "rss", f"{slug(o['name'])}.xml"), "w", encoding="utf-8") as f:
            f.write(channel(o["name"], o["site_url"], o["type"] + " (fictional)", items))
        print(f"{o['name']}: {len(items)} items")
    print(f"all.xml: {len(allitems)} items")

if __name__ == "__main__":
    main()
