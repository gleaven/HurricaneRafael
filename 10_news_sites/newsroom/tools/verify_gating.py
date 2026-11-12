"""End-to-end leak check for the newsroom. Run before an exercise.

    python tools/verify_gating.py

Starts a throwaway server (it does not touch config.json or the saved clock), jumps the clock
to every milestone plus extra checkpoints, crawls every public surface (newsstand, feeds page,
outlet home/section/archive/search pages, recent article pages, RSS, JSON API) and fails if
anything published after the clock, any scenario-internal id or D-notation, or any restricted
term before its public day shows up. Also checks direct access to future URLs, outlet holds
and game-master sign-in from another address.
"""
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
PORT = 8095
BASE = f"http://127.0.0.1:{PORT}"
PASS = "verify-only-passphrase"
fails = []


def get(url, opener=None):
    try:
        r = (opener or urllib.request).open(url, timeout=20) if opener else urllib.request.urlopen(url, timeout=20)
        return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def post(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def fail(msg):
    fails.append(msg)
    print("  FAIL", msg)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return None if ip.startswith("127.") else ip
    except Exception:
        return None


def main():
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py"), "--port", str(PORT), "--no-save",
                             "--lan", "--passphrase", PASS], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/api/clock", timeout=2)
                break
            except Exception:
                time.sleep(0.5)
        run()
    finally:
        proc.terminate()
        try:
            err = proc.communicate(timeout=5)[1].decode("utf-8", "replace")
        except Exception:
            err = ""
        if "Traceback" in err:
            fail("server printed a traceback:\n" + err[-2000:])
    print(f"\n{'PASS' if not fails else 'FAILED'}: {len(fails)} problem(s)")
    sys.exit(1 if fails else 0)


def run():
    terms = json.load(open(os.path.join(ROOT, "02_public_record", "restricted_terms.json"), encoding="utf-8"))["terms"]
    state = json.loads(get(BASE + "/api/gm/state")[1])
    outlets = [o["slug"] for o in state["outlets"]]
    checkpoints = [(m["label"], m["ts"]) for m in state["milestones"]]
    span = state["end"] - state["start"]
    checkpoints += [(f"checkpoint {i}", state["start"] + span * i / 9) for i in range(1, 9)]
    checkpoints.append(("end", state["end"]))
    checkpoints.sort(key=lambda x: x[1])

    for label, ts in checkpoints:
        post("/api/gm/action", {"action": "set", "ts": ts})
        allr = json.loads(get(BASE + "/api/gm/articles")[1])
        day = None
        st = json.loads(get(BASE + "/api/gm/state")[1])
        m = re.match(r"D([+-])(\d+)", st["d"])
        day = int(m.group(2)) * (1 if m.group(1) == "+" else -1)
        hidden = [a for a in allr["articles"] if not a["visible"]]
        shown = [a for a in allr["articles"] if a["visible"]]

        pages = ["/", "/feeds", "/rss/all.xml", "/api/articles?limit=500", "/api/outlets", "/api/clock?outlet=_all"]
        for s in outlets:
            pages += [f"/{s}/", f"/{s}/archive/", f"/{s}/archive/?q=the", f"/{s}/rss.xml",
                      f"/api/articles?outlet={s}&limit=500"]
            outlet_state = next(o for o in st["outlets"] if o["slug"] == s)
            pages += [f"/{s}/section/{sec}/" for sec in section_slugs(s)]
            recent = [a for a in shown if a["outlet"] == s][-6:]
            pages += [a["url"] for a in recent]
            if outlet_state["visible"] == 0 and recent:
                fail(f"{label}: {s} state says 0 visible but explorer shows visible stories")
        text = []
        for p in pages:
            code, body = get(BASE + p)
            if code >= 500:
                fail(f"{label}: {p} returned {code}")
            text.append(body)
        blob = "\n".join(text)

        for a in hidden:
            for needle in (a["pid"], a["url"]):
                if needle in blob:
                    fail(f"{label}: future story leaked ({needle}) {a['headline'][:60]}")
                    break
        if re.search(r"NWS-[MP]\d{3}", blob):
            fail(f"{label}: scenario story id appears on a public surface")
        dn = re.findall(r"(?<![A-Za-z0-9])D[+-]\d{1,3}(?![0-9])", blob)
        if dn:
            fail(f"{label}: D-notation on a public surface {sorted(set(dn))[:5]}")
        for t in terms:
            if (t["public_from_day"] is None or day < t["public_from_day"]) and re.search(t["pattern"], blob, re.I):
                fail(f"{label} (day {day}): restricted term /{t['pattern']}/ appears before day {t['public_from_day']}")
        for a in hidden[:3]:
            if get(BASE + a["url"])[0] != 404:
                fail(f"{label}: future article URL did not return 404: {a['url']}")
            if get(BASE + "/api/articles/" + a["pid"])[0] != 404:
                fail(f"{label}: future article API did not return 404")
        print(f"  ok  {st['d']:<16} {len(shown):>3} published  {len(pages):>3} pages  {label}")

    # holds
    post("/api/gm/action", {"action": "milestone", "index": 3})
    before = next(o for o in post("/api/gm/action", {"action": "hold", "outlet": "kncb", "on": True})["outlets"] if o["slug"] == "kncb")["visible"]
    after = next(o for o in post("/api/gm/action", {"action": "step", "seconds": 86400 * 20})["outlets"] if o["slug"] == "kncb")["visible"]
    if after != before:
        fail(f"hold: KNCB advanced from {before} to {after} while held")
    k = json.loads(get(BASE + "/api/articles?outlet=kncb&limit=500")[1])["total"]
    if k != before:
        fail(f"hold: KNCB API shows {k} stories while held at {before}")
    released = next(o for o in post("/api/gm/action", {"action": "hold", "outlet": "kncb", "on": False})["outlets"] if o["slug"] == "kncb")["visible"]
    print(f"  ok  hold: KNCB stayed at {before} while held, {released} after release")
    if released <= before:
        fail("hold: releasing KNCB did not publish the held stories")

    # game master sign-in from another address
    ip = lan_ip()
    if not ip:
        print("  --  no LAN address; skipped remote sign-in check")
        return
    rb = f"http://{ip}:{PORT}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    plain = urllib.request.build_opener(NoRedirect)
    for p in ("/control", "/explorer"):
        code = get(rb + p, plain)[0]
        if code not in (302, 303):
            fail(f"remote {p} returned {code} without sign-in (expected redirect)")
    if get(rb + "/api/gm/state", plain)[0] != 401:
        fail("remote GM API reachable without sign-in")
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(rb + "/gm/login", data=urllib.parse.urlencode({"passphrase": PASS, "next": "/control"}).encode(), timeout=20)
    if get(rb + "/api/gm/state", op)[0] != 200:
        fail("remote sign-in with the right passphrase did not grant access")
    print(f"  ok  remote sign-in enforced from {ip}")


def section_slugs(slug):
    outlets = json.load(open(os.path.join(HERE, "data", "outlets.json"), encoding="utf-8"))
    return [s["slug"] for o in outlets if o["slug"] == slug for s in o["sections"]]


if __name__ == "__main__":
    main()
