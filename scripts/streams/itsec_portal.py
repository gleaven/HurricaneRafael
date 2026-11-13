"""Access logs of the disaster-aid applicant portal and the base logistics system (stream portal_access_logs).
Called through gen_itsec.py (`gen_itsec.py portal`).

What the two logs are built from
  * payments/aid_applications.csv: every web application, account change and sign-in recorded there appears here
    at the same second, from the same address, with the network number the shared address table (netmap) gives it.
  * The air station's people and working days (partner_it_model.sessions): the logistics system is used from the
    base's own workstations, by the base's own accounts, while they are at work.
  * netmap: one address-to-network table for every stream.
Everything else is ordinary traffic of a public web site: people reading information pages, starting and
abandoning registrations, coming back to check a status; search-engine crawlers, an availability monitor,
and the scanners and scripts that probe every internet-facing login page every day.

Every record, whoever caused it, is written through the same helpers (visit, form, sign_in, scan), so the
same paths, status codes, user agents and sizes occur across the whole span.
"""
import csv
import glob
import os

import netmap
from gen_itsec import DAY, NET, SPAN_START, hsh, z
from common import D0_EPOCH, ROOT, SPAN_END, UTC, dt, local_dt, local_ts, np, reg, rng, ts, write_csv

PORTAL_COLS = ["time_utc", "system", "client_ip", "client_network", "method", "path", "status", "event", "account_ref", "user_agent_family", "bytes"]
UA = ["Chrome/Windows", "Safari/iOS", "Chrome/Android", "Edge/Windows", "Firefox/Windows", "Safari/macOS", "Samsung/Android"]
UA_P = [0.24, 0.31, 0.22, 0.08, 0.03, 0.07, 0.05]
UA_MOBILE = ["Safari/iOS", "Chrome/Android", "Samsung/Android"]
SCRIPT_UA = [("python-requests", 30), ("curl", 16), ("Go-http-client", 18), ("zgrab", 9), ("okhttp", 7), ("Java-http-client", 6), ("crawler", 14)]
AID, NASLOG = "EXT-AIDPORTAL-01", "EXT-NASLOG-02"
# page -> typical response size in bytes (compressed HTML); errors and redirects are small
SIZE = {"/": 18400, "/disasters/current": 27100, "/help/eligibility": 21300, "/help/documents": 16800, "/es/ayuda": 19900, "/help/contact": 9400,
        "/login": 6100, "/status": 11800, "/account/register": 14200, "/account/recover": 5600, "/account/profile": 9900, "/applications": 12600,
        "/applications/new": 23800, "/robots.txt": 310, "/sitemap.xml": 2900, "/.well-known/security.txt": 420, "/logout": 0,
        "/orders": 15200, "/orders/new": 11700, "/fuel/requests": 13900, "/inventory": 31500, "/reports/daily": 22400, "/contact": 7300,
        "/suppliers": 12800, "/help": 8600}
INFO = [("/", 30), ("/disasters/current", 22), ("/help/eligibility", 17), ("/help/documents", 11), ("/es/ayuda", 10), ("/help/contact", 6), ("/login", 2.5), ("/status", 1.5)]
TYPOS = ["/help/elegibility", "/apply", "/espanol", "/disaster", "/help/faq", "/register", "/es", "/contact-us", "/favicon.ico", "/apple-touch-icon.png"]
# what scanners ask for. A path that exists answers as it does for anyone else.
SCAN = ["/admin", "/owa", "/login.aspx", "/wp-login.php", "/.env", "/.git/config", "/phpmyadmin/", "/api/v1/session", "/.well-known/security.txt", "/robots.txt",
        "/server-status", "/cgi-bin/", "/actuator/health", "/account/recover", "/help/contact", "/login", "/account/register", "/status", "/xmlrpc.php", "/config.json",
        "/account/profile", "/applications", "/orders"]
EXISTS = {AID: {"/", "/disasters/current", "/help/eligibility", "/help/documents", "/es/ayuda", "/help/contact", "/login", "/account/register", "/account/recover",
                "/robots.txt", "/sitemap.xml", "/.well-known/security.txt"},
          NASLOG: {"/", "/login", "/contact", "/suppliers", "/robots.txt", "/help", "/.well-known/security.txt"}}
NEEDS_LOGIN = {AID: {"/status", "/applications", "/applications/new", "/account/profile"}, NASLOG: {"/orders", "/orders/new", "/fuel/requests", "/inventory", "/reports/daily"}}
FORBIDDEN = {"/.env", "/.git/config", "/server-status", "/config.json"}
LOGIN_POSTS = {"/login", "/api/v1/session", "/login.aspx"}
LOCAL_HOURS = np.array([0.16, 0.09, 0.06, 0.05, 0.05, 0.09, 0.22, 0.45, 0.7, 0.88, 1.0, 1.0, 0.96, 0.92, 0.9, 0.9, 0.92, 0.96, 1.0, 1.06, 1.02, 0.84, 0.55, 0.3])
WORK_HOURS = np.array([0.02, 0.01, 0.01, 0.01, 0.02, 0.05, 0.2, 0.6, 1.0, 1.0, 1.0, 0.9, 0.7, 0.9, 1.0, 1.0, 0.8, 0.45, 0.2, 0.1, 0.08, 0.06, 0.04, 0.03])


def _pick(pairs, x):
    return netmap.pick(pairs, x)


def _h(*k):
    return int(hsh(*k, n=12), 16)


def device_ua(dev):
    """The browser of a device: a device keeps it."""
    return UA[int(np.searchsorted(np.cumsum(UA_P), (_h("ua", dev) % 10 ** 6) / 10.0 ** 6))] if dev else UA[0]


def story_ua(ip):
    """The client a given outside address presents itself as: sign-in tools copy an ordinary browser's name, one per address."""
    k = (_h("ua-addr", ip) % 10 ** 6) / 10.0 ** 6
    return _pick([("Chrome/Windows", 34), ("Safari/iOS", 30), ("Chrome/Android", 24), ("Edge/Windows", 12)], k)       # such tools ship a short list of common names


def interest(d):
    """How many people look at the aid portal's information pages on local day d, relative to an ordinary summer day."""
    if d < -5:
        f = 1.0
    elif d < 0:
        f = [1.3, 1.7, 2.4, 3.3, 4.1][d + 5]           # the forecast firms up
    elif d == 0:
        f = 2.2                                         # landfall: most of the area has no power
    elif d < 4:
        f = [4.6, 6.4, 7.6][d - 1]
    else:
        f = 1.0 + 6.8 * np.exp(-(d - 3) / 13.0)
    if 52 <= d < 60:
        f += 0.5 * (d - 51)                             # registration is announced
    elif 60 <= d < 90:
        f += 5.5 * np.exp(-(d - 60) / 16.0) + 1.2       # registration period
    elif d >= 90:
        f += 0.9 * np.exp(-(d - 90) / 10.0)
    wd = local_dt(local_ts(d, "12:00")).weekday()
    return f * (1.0, 1.04, 1.0, 0.98, 0.93, 0.74, 0.68)[wd]


def gen_portal():
    """Set PORTAL_SPLIT=1 where a single command may not run longer than a minute: the first call computes the rows and
    keeps them in a scratch file, the second call writes the CSV files."""
    import pickle
    scratch = os.path.join(os.environ.get("TMPDIR", "/tmp"), "portal_access_rows.pkl")
    P = f"{NET}/portal"
    if os.environ.get("PORTAL_SPLIT") and os.path.exists(scratch):
        with open(scratch, "rb") as fh:
            files, n_partner = pickle.load(fh)
        if _write_portal(P, files, n_partner, scratch + ".done"):
            os.remove(scratch)
            os.remove(scratch + ".done")
        return
    import partner_it_model as PM
    nas_dark = PM.nas_power()[1]                        # the evening the air station's backup generator failed (base status reports)
    g = rng("portal_access", "v4")
    files = {}
    ext = {e["system_id"]: e for e in reg("gw_host_registry")["external_systems"]}
    apps_csv = os.path.join(ROOT, "05_other_sources/payments/aid_applications.csv")
    with open(apps_csv, encoding="utf-8", newline="") as fh:
        apps = [r for r in csv.DictReader(fh) if r["record_type"] in ("application", "account_change")]
    OPEN_T = min(ts(r["submitted_utc"]) for r in apps if r["submitted_utc"]) - 60
    lab = netmap.label

    def size(path, status):
        if status in (301, 302, 304):
            return 0 if status == 304 else int(g.integers(180, 260))
        if status == 404:
            return int(g.integers(470, 590))
        if status in (401, 403, 422, 503):
            return int(g.integers(430, 720))
        if status == 201:
            return int(g.integers(520, 980))
        base = SIZE.get(path) or SIZE.get("/" + path.split("/")[1], 5200)
        return int(base * g.uniform(0.94, 1.07)) if base else 0

    def add(t, system, ip, method, path, status, event, acct="", ua="", nbytes=None):
        if system == NASLOG and nas_dark[0] <= t < nas_dark[1] and not ip.startswith("10."):
            return                                      # the base's server room is without power that evening
        if not (SPAN_START <= t < SPAN_END):
            return
        mon = dt.datetime.fromtimestamp(t, UTC).strftime("%Y-%m")
        files.setdefault((system, mon), []).append([int(t), system, ip, lab(ip) or "base network", method, path, status, event, acct, ua,
                                                    size(path, status) if nbytes is None else nbytes])

    def get(t, system, ip, ua, path, acct="", signed_in=False):
        """One GET of a page by anybody: what the site answers depends only on the page and on whether the client is signed in."""
        if system == AID and OPEN_T <= t < OPEN_T + 3 * DAY and g.random() < 0.012:      # the first days of registration: the site is overloaded now and then
            add(t, system, ip, "GET", path, 503, "page_view", acct, ua)
            t += int(g.integers(4, 30))
        if path in NEEDS_LOGIN[system] and not signed_in:
            add(t, system, ip, "GET", path, 302, "page_view", "", ua)
        elif path in EXISTS[system] or path in NEEDS_LOGIN[system] or path == "/logout":
            add(t, system, ip, "GET", path, 302 if path == "/logout" else 200, "page_view", acct, ua)
        elif path in FORBIDDEN:
            add(t, system, ip, "GET", path, 403, "page_view", "", ua)
        else:
            add(t, system, ip, "GET", path, 404, "page_view", "", ua)
        return t

    def sign_in(t, system, ip, ua, acct, ok=True, form=True):
        """GET the form, POST it. `acct` is the account the name resolved to ("" when the name is unknown)."""
        if form:
            get(t - int(g.integers(4, 70)), system, ip, ua, "/login")
        add(t, system, ip, "POST", "/login", 200 if ok else 401, "login_success" if ok else "login_failed", acct, ua)

    # ---------------------------------------------------------------- people reading the aid portal
    def household(k, d):
        ip, _ = netmap.home(("hh", k), epoch=(d + _h("hhp", k) % 31) // 31)
        ndev = 1 + _h("hhn", k) % 3
        return ip, device_ua(f"hh{k}-{int(g.integers(ndev))}")

    def browse(t, ip, ua, n, opened):
        seen = set()
        for i in range(n):
            p = _pick(INFO, g.random())
            if opened and g.random() < 0.1:
                p = "/account/register"                 # looks at the form; most do not send it in this visit
            if g.random() < 0.012:
                p = TYPOS[int(g.integers(len(TYPOS)))]
            if p in seen and p in EXISTS[AID] and g.random() < 0.5:
                add(t, AID, ip, "GET", p, 304, "page_view", "", ua)
            else:
                get(t, AID, ip, ua, p)
            seen.add(p)
            t += int(g.gamma(1.6, 38)) + 3
        return t

    first_d, last_d = int((SPAN_START - D0_EPOCH) // DAY) - 1, int((SPAN_END - D0_EPOCH) // DAY)
    cum_local = np.cumsum(LOCAL_HOURS / LOCAL_HOURS.sum())
    cum_work = np.cumsum(WORK_HOURS / WORK_HOURS.sum())

    def local_time(d, cum):
        hr = int(np.searchsorted(cum, g.random()))
        return local_ts(d, f"{min(hr, 23):02d}:00") + int(g.integers(0, 3600))

    for d in range(first_d, last_d + 1):
        for _ in range(int(g.poisson(21 * interest(d)))):
            t = local_time(d, cum_local)
            k = int(g.integers(0, 2600)) if g.random() < 0.3 else int(g.integers(2600, 90000))      # some households come back often
            ip, ua = household(k, d)
            if g.random() < 0.18:                       # on a phone, away from home
                ip, ua = netmap.mobile(("hhm", k, d // 3))[0], device_ua(f"hh{k}-m")
            browse(t, ip, ua, 1 + int(g.geometric(0.42)) if g.random() < 0.9 else 1, t >= OPEN_T)

    # ---------------------------------------------------------------- applicants (mirrors payments/aid_applications.csv)
    def other_device(acct):
        return netmap.mobile(("acct-phone", acct))[0], UA_MOBILE[_h("mua", acct) % 3]

    accounts = []                                       # (time created, account id), for the sign-in runs below
    for r in apps:
        ip, acct, dev = r["source_ip"], r["account_id"], r["device_id"]
        if r["record_type"] == "application" and r["channel"] == "web":
            t = ts(r["submitted_utc"])
            ua = device_ua(dev)
            story = ip in netmap.STORY_SET
            fill = int(min(g.lognormal(6.55, 0.75), 30 * DAY)) + 180        # registering to submitting: usually a quarter of an hour, sometimes days
            if g.random() < 0.1:
                fill += int(g.integers(1, 9)) * DAY
            t_reg = max(OPEN_T + int(g.integers(5, 900)), t - fill)
            if t_reg >= t - 120:
                t_reg = t - int(g.integers(150, 600))
            accounts.append((t_reg, acct))
            if g.random() < 0.55 and not story:        # read about the programme first
                tb = t_reg - int(g.gamma(1.4, 2.2 * DAY)) - 300
                browse(tb, ip, ua, 1 + int(g.geometric(0.5)), tb >= OPEN_T)
            get(t_reg - int(g.gamma(2.0, 95)) - 35, AID, ip, ua, "/account/register")
            if g.random() < 0.07:                       # a field left out the first time
                add(t_reg - int(g.integers(12, 80)), AID, ip, "POST", "/account/register", 422, "validation_error", "", ua)
            add(t_reg, AID, ip, "POST", "/account/register", 201, "account_created", acct, ua)
            same_sitting = t - t_reg < 3 * 3600
            if not same_sitting:                        # came back another time to finish
                sign_in(t - int(g.gamma(2.0, 240)) - 120, AID, ip, ua, acct)
            get(t - int(g.gamma(2.0, 170)) - 45, AID, ip, ua, "/applications/new", acct, True)
            if g.random() < 0.3:
                get(t - int(g.integers(30, 600)), AID, ip, ua, "/help/documents", acct, True)
            add(t, AID, ip, "POST", "/applications", 201, "application_submitted", acct, ua)
            for j in range(min(3, len([p for p in r["damage_photo_hashes"].split(";") if p]))):
                if g.random() < 0.45:
                    add(t + 20 + j * int(g.integers(15, 90)) + int(g.integers(0, 15)), AID, ip, "POST", "/applications/documents", 201, "document_uploaded", acct, ua)
            if story:
                continue
            nret = 0 if g.random() < 0.34 else int(g.geometric(0.42))
            tb = t
            for _ in range(min(nret, 9)):               # people come back to check their status, some many times, some never
                tb += int(g.gamma(1.3, 4.5 * DAY)) + 3600
                tb = local_time(int((tb - D0_EPOCH - 5 * 3600) // DAY), cum_local)
                if tb >= SPAN_END or tb <= t + 600:
                    continue
                cip, cua = (ip, ua) if g.random() < 0.8 else other_device(acct)
                r_ = g.random()
                if r_ < 0.09:                           # wrong password, then right
                    sign_in(tb - int(g.integers(8, 90)), AID, cip, cua, acct, ok=False)
                    sign_in(tb, AID, cip, cua, acct, form=False)
                elif r_ < 0.115:                        # wrong password, gives up or asks for a reset
                    sign_in(tb, AID, cip, cua, acct, ok=False)
                    if g.random() < 0.6:
                        get(tb + int(g.integers(10, 90)), AID, cip, cua, "/account/recover")
                        add(tb + int(g.integers(95, 240)), AID, cip, "POST", "/account/recover", 200, "password_reset_requested", "", cua)
                    continue
                elif r_ < 0.13:                         # mistyped e-mail address: the name matches no account
                    sign_in(tb - int(g.integers(10, 60)), AID, cip, cua, "", ok=False)
                    sign_in(tb, AID, cip, cua, acct, form=False)
                else:
                    sign_in(tb, AID, cip, cua, acct)
                tv = tb + int(g.integers(3, 40))
                for _k in range(int(g.geometric(0.62))):
                    get(tv, AID, cip, cua, str(g.choice(["/status", "/status", "/status", "/applications", "/status", "/account/profile"])), acct, True)
                    tv += int(g.gamma(1.5, 45)) + 4
                if g.random() < 0.2:
                    get(tv, AID, cip, cua, "/logout", acct, True)
        elif r["record_type"] == "account_change" and r["login_utc"] and ip:
            tl, tc = ts(r["login_utc"]), ts(r["changed_utc"])
            story = ip in netmap.STORY_SET
            ua = story_ua(ip) if story else device_ua(dev)
            if story:                                   # a few wrong guesses against the same account before the one that works
                for _ in range(int(g.integers(0, 5))):
                    gip = netmap.STORY_POOL[int(g.integers(64))]
                    sign_in(tl - int(g.integers(20, 6 * 3600)), AID, gip, story_ua(gip), acct, ok=False, form=False)
            elif g.random() < 0.06:
                sign_in(tl - int(g.integers(8, 60)), AID, ip, ua, acct, ok=False)
            sign_in(tl, AID, ip, ua, acct, form=not story)
            if tc - tl > 8:
                get(tl + int(g.integers(2, max(3, min(60, tc - tl - 2)))), AID, ip, ua, "/account/profile", acct, True)
            add(tc, AID, ip, "POST", "/account/" + r["field_changed"].split(" restored")[0].replace(" ", "-"), 200, "profile_updated: " + r["field_changed"], acct, ua)
    # people who open an account and never apply
    n_extra = int(0.08 * len(accounts))
    for i in range(n_extra):
        d = int(g.integers(60, 100))
        t = local_time(d, cum_local)
        if t < OPEN_T + 600:
            continue
        ip, ua = household(100000 + i, d)
        acct = "ACC-" + hsh("extra-acct", i, n=10).upper()
        get(t - int(g.gamma(2.0, 95)) - 35, AID, ip, ua, "/account/register")
        add(t, AID, ip, "POST", "/account/register", 201, "account_created", acct, ua)
        accounts.append((t, acct))
        if g.random() < 0.5:
            get(t + int(g.integers(20, 400)), AID, ip, ua, "/applications/new", acct, True)
    accounts.sort()

    # ---------------------------------------------------------------- crawlers, monitors, scanners and scripts (both systems, whole span)
    def scan(t, system, ip, ua, paths, names):
        """A run of requests from one client. Unknown names on a login form fail; everything else answers as it would for anybody."""
        for p in paths:
            if p in LOGIN_POSTS and names:
                st = 401 if (p == "/login" or p == "/api/v1/session" or p == "/login.aspx") else 404
                add(t, system, ip, "POST", p, st, "login_failed", "", ua)
            else:
                get(t, system, ip, ua, p)
            t += int(g.gamma(1.2, 2.5)) + (1 if g.random() < 0.7 else int(g.integers(5, 400)))
        return t

    monitors = [netmap.hosted(("monitor", i))[0] for i in range(2)]
    NSRC = 4200
    CHEAP_UA = [("python-requests", 44), ("curl", 40), ("Go-http-client", 8), ("okhttp", 4), ("zgrab", 4)]
    for d in range(first_d, last_d + 1):
        t0 = D0_EPOCH + d * DAY
        for k in range(48):                             # an availability monitor asks for the front page every half hour
            add(t0 + k * 1800 + 11 + (d * 7 + k * 3) % 23, AID, monitors[k % 2], "GET", "/", 200, "page_view", "", "uptime-monitor")
        for system, lam in ((AID, 72.0), (NASLOG, 40.0)):
            for _ in range(int(g.poisson(lam))):
                t = t0 + int(g.integers(0, DAY))
                src = int(g.integers(0, 90)) if g.random() < 0.45 else int(g.integers(90, NSRC))        # a few sources come back every week
                ip = netmap.hosted(("scanner", src))[0]
                ua = _pick(SCRIPT_UA, (_h("sua", src) % 10 ** 6) / 10.0 ** 6)
                if _h("sprov", src) % 100 < 45:         # much of this noise comes from the cheapest hosting providers
                    ip = netmap.addr_in(64512, _h("s64512", src))
                    ua = _pick(CHEAP_UA, (_h("sua2", src) % 10 ** 6) / 10.0 ** 6)
                kind = _h("skind", src) % 100
                if ua == "crawler" or kind < 12:        # search engines and link checkers
                    pages = ["/robots.txt"] + [str(x) for x in g.choice(sorted(EXISTS[system] - {"/robots.txt"}), int(g.integers(1, 6)), replace=False)]
                    if g.random() < 0.3:
                        pages.append("/sitemap.xml")
                    scan(t, system, ip, ua if ua == "crawler" else "crawler", pages, False)
                elif kind < 70:                         # path scanners
                    n = int(min(len(SCAN), g.geometric(0.13)))
                    scan(t, system, ip, ua, [str(x) for x in g.choice(SCAN, n, replace=False)], g.random() < 0.5)
                else:                                   # login guessing with common names
                    n = int(g.geometric(0.07))
                    scan(t, system, ip, ua, [str(g.choice(["/login", "/login", "/login", "/api/v1/session", "/login.aspx"])) for _ in range(min(n, 120))], True)

    # ---------------------------------------------------------------- 10-13 August: both login pages worked over from one small network
    a0, a1 = ts("2027-08-10T05:00Z"), ts("2027-08-13T05:00Z")
    paths = ["/login", "/account/recover", "/account/register", "/api/v1/session", "/admin", "/login.aspx", "/owa", "/status", "/.well-known/security.txt", "/help/contact"]
    for i in range(3400):
        t = a0 + int(g.integers(0, a1 - a0))
        sysid = AID if i % 5 else NASLOG
        p = paths[int(g.integers(len(paths)))]
        ip = netmap.STORY_POOL[int(g.integers(64))]
        scan(t, sysid, ip, "python-requests" if i % 3 else "curl", [p], True)

    # ---------------------------------------------------------------- 15-24 November: automated sign-in attempts in bursts, about 220,000 failures
    b0, b1 = ts("2027-11-15T06:00Z"), ts("2027-11-24T06:00Z")
    nb = int(g.integers(55, 75))
    bursts = np.sort(g.integers(b0, b1 - 3 * 3600, nb))
    per = g.multinomial(int(g.integers(218200, 221400)), g.dirichlet(np.full(nb, 1.6)))
    ipw = g.dirichlet(np.full(64, 0.9))
    acc_t = np.array([a for a, _ in accounts])
    for bt, n in zip(bursts, per):
        tt = bt + np.sort(g.integers(0, int(g.integers(1500, 4 * 3600)), n))
        ips = g.choice(64, n, p=ipw)
        known = g.random(n) < 0.045                     # most names on such lists match no account here
        pickn = g.random(n)
        for t, ipn, kn, pk in zip(tt, ips, known, pickn):
            acct = ""
            if kn:
                hi = int(np.searchsorted(acc_t, t))
                if hi:
                    acct = accounts[int(pk * hi)][1]
            sip = netmap.STORY_POOL[int(ipn)]
            add(int(t), AID, sip, "POST", "/login", 401, "login_failed", acct, story_ua(sip))

    # ---------------------------------------------------------------- the base logistics system
    # the base's own people, from their own workstations, while they are at work
    use = {"SUP": 0.8, "OPS": 0.3, "PWD": 0.3, "ADM": 0.1}
    nas = PM.registry()["NASCC"]
    host_ua = {h["host_id"]: _pick([("Edge/Windows", 88), ("Chrome/Windows", 10), ("Firefox/Windows", 2)], (_h("nasua", h["host_id"]) % 1000) / 1000.0) for h in nas["hosts"]}
    for s in PM.sessions("NASCC"):
        gs = rng("portal_access", "naslog", s["host"], int(s["a"]))
        if s["b"] - s["a"] < 1500 or gs.random() > use.get(s["site"], 0.1):
            continue
        ua = host_ua[s["host"]]
        for _ in range(1 + int(gs.poisson(0.7))):
            t = int(s["a"] + 240 + gs.random() * (s["b"] - s["a"] - 900))
            if nas_dark[0] - 600 <= t < nas_dark[1]:
                continue
            if not 6 <= local_dt(t).hour < 21 and gs.random() < 0.8:
                continue                                # little ordering is done at night, even by the duty office
            get(t - int(gs.integers(3, 40)), NASLOG, s["ip"], ua, "/login")
            if gs.random() < 0.04:
                add(t - int(gs.integers(6, 45)), NASLOG, s["ip"], "POST", "/login", 401, "login_failed", s["user"], ua)
                if gs.random() < 0.15:
                    continue                            # gives up, rings the help desk
            add(t, NASLOG, s["ip"], "POST", "/login", 200, "login_success", s["user"], ua)
            tv = t + int(gs.integers(2, 25))
            for _k in range(int(gs.geometric(0.3))):
                p = str(gs.choice(["/orders", "/fuel/requests", "/inventory", "/reports/daily", "/orders", "/inventory"]))
                get(tv, NASLOG, s["ip"], ua, p, s["user"], True)
                if p in ("/orders", "/fuel/requests") and gs.random() < 0.22:
                    tv += int(gs.gamma(2.0, 80)) + 20
                    add(tv, NASLOG, s["ip"], "POST", p, 201, "request_submitted", s["user"], ua)
                tv += int(gs.gamma(1.5, 70)) + 5
                if tv > s["b"] - 60:
                    break
            if gs.random() < 0.35:
                get(tv, NASLOG, s["ip"], ua, "/logout", s["user"], True)
    # its public pages: suppliers in business hours, families, the curious
    for d in range(first_d, last_d + 1):
        wd = local_dt(local_ts(d, "12:00")).weekday()
        for _ in range(int(g.poisson(3.1 if wd < 5 else 1.2))):
            t = local_time(d, cum_work if g.random() < 0.7 else cum_local)
            k = int(g.integers(0, 160)) if g.random() < 0.55 else int(g.integers(160, 20000))            # regular suppliers come back
            ip, ua = household(200000 + k, d)
            for _k in range(int(g.geometric(0.5))):
                get(t, NASLOG, ip, ua, str(g.choice(["/", "/suppliers", "/contact", "/help", "/login", "/suppliers"])))
                t += int(g.gamma(1.5, 30)) + 3

    # ---------------------------------------------------------------- visits the partner organisations' own firewalls recorded
    n_partner = 0
    for p in sorted(glob.glob(os.path.join(ROOT, "05_other_sources/partner_it/*/firewall_*.csv"))):
        with open(p, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("dst_ip") == ext[AID]["ip"] and r.get("action") == "allow" and r.get("dst_port") in ("443", "80"):
                    t = ts(r["time_utc"][:16] + "Z") + int(r["time_utc"][17:19]) - int(float(r.get("duration_s") or 0))
                    k = int(hsh("pv", p, r["time_utc"], r["src_ip"], n=6), 16)
                    get(t, AID, r.get("nat_src_ip") or r["src_ip"], UA[[0, 3, 4][k % 3]], INFO[k % 6][0])
                    n_partner += 1

    if os.environ.get("PORTAL_SPLIT"):
        with open(scratch, "wb") as fh:
            pickle.dump((files, n_partner), fh)
        print("portal_access_logs: rows computed; run the same command again to write the files")
        return
    _write_portal(P, files, n_partner)


def _write_portal(P, files, n_partner, done_file=None):
    """Write the monthly files in time order, no two identical rows. With done_file the work can be cut off and
    taken up again: files already written in this round are skipped. Returns True when everything is written."""
    done = set(open(done_file).read().split("\n")) if done_file and os.path.exists(done_file) else set()
    if not done:
        for old in glob.glob(os.path.join(ROOT, P, "*.csv")):
            os.remove(old)
    total = 0
    for (system, mon), rows in sorted(files.items()):
        name = "aid_portal_access" if system == AID else "base_logistics_access"
        if f"{name}_{mon}" in done:
            continue
        rows.sort(key=lambda r: (r[0], r[2], r[5]))
        seen = set()
        for r in rows:
            k = tuple(r[:9])
            while k in seen:
                r[0] += 1
                k = tuple(r[:9])
            seen.add(k)
        rows.sort(key=lambda r: r[0])
        for r in rows:
            r[0] = z(r[0])
        est = sum(len(",".join(map(str, r))) + 2 for r in rows)
        parts = max(1, -(-est // 38_000_000))              # a month too large for one file is written in parts, in time order
        step = -(-len(rows) // parts)
        for k in range(parts):
            suffix = "" if parts == 1 else f"_{k + 1:02d}"
            total += write_csv(f"{P}/{name}_{mon}{suffix}.csv", PORTAL_COLS, rows[k * step:(k + 1) * step])
        if done_file:
            with open(done_file, "a") as fh:
                fh.write(f"{name}_{mon}\n")
    print(f"portal_access_logs: {sum(len(v) for v in files.values()):,} rows in {len(files)} months and systems ({n_partner} visits mirrored from partner firewall logs)")
    return True
