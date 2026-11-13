"""Re-measurement of the 19 defects of audit 4 (partners and portal) after the G2 fixes.
python3 recheck_g2.py <1|2|3|4|5|6|7|8|9|10|minor>"""
import sys, os, glob, json, collections
import pandas as pd, numpy as np
sys.path.insert(0, "./scripts/streams")
import netmap as N
ROOT = "."
C = "./_scratch/cache_g2"
ORGS = ['city', 'nascc', 'brw', 'port', 'srmc', 'bcmc', 'county']
def load(kind, orgs=ORGS):
    out = []
    for o in orgs:
        p = f"{C}/{o}_{kind}.pkl"
        if not os.path.exists(p):
            d = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in sorted(glob.glob(f"{ROOT}/05_other_sources/partner_it/{o}/{kind}_*.csv"))], ignore_index=True)
            d["org"] = o; d.to_pickle(p)
        out.append(pd.read_pickle(p))
    return pd.concat(out, ignore_index=True)
def portal(name):
    p = f"{C}/portal_{name}.pkl"
    if not os.path.exists(p):
        pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in sorted(glob.glob(f"{ROOT}/05_other_sources/network_logs/portal/{name}_*.csv"))], ignore_index=True).to_pickle(p)
    return pd.read_pickle(p)
def T(d, c="time_utc"): return pd.to_datetime(d[c], format="%Y-%m-%dT%H:%M:%SZ", utc=True)
STORY = N.STORY_SET
w = sys.argv[1]
if w == "1":
    for name in ("aid_portal_access", "base_logistics_access"):
        d = portal(name); st = d.client_ip.isin(STORY)
        print(name, len(d), "story rows", int(st.sum()))
        for col in ("client_network", "user_agent_family", "status", "path", "event", "method"):
            a, s = d[col].value_counts(), d[st][col].value_counts()
            print("  ", col, "values occurring only on story rows:", [(k, int(v)) for k, v in s.items() if v == a[k]])
        for ev in ("login_success", "account_created", "login_failed", "page_view"):
            x = d[(d.client_network == "ASN 64512") & (d.event == ev)]
            print(f"   ASN 64512 + {ev}: {len(x)} rows, {int(x.client_ip.isin(STORY).sum())} story")
        for ua in ("python-requests", "curl"):
            x = d[d.user_agent_family == ua]; print(f"   {ua}: {len(x)} rows, {int(x.client_ip.isin(STORY).sum())} story; outside the two story windows: {int((~x.client_ip.isin(STORY)).sum())}")
        x = d[d.status == "404"]; print("   404:", len(x), "story", int(x.client_ip.isin(STORY).sum()))
    a = pd.read_csv(f"{ROOT}/05_other_sources/payments/aid_applications.csv", dtype=str, keep_default_na=False)
    x = a[a.source_asn == "64512"]; print("aid_applications source_asn 64512:", len(x), "story", int(x.source_ip.isin(STORY).sum()), x.record_type.value_counts().to_dict())
elif w == "2":
    au = load("auth"); fw = load("firewall")
    x = au[au.src_ip.str.startswith("203.0.113.")]; lo = x[x.src_ip.str.split(".").str[3].astype(int) < 100]
    print("sign-on rows from 203.0.113.x:", len(x), "story", int(x.src_ip.isin(STORY).sum()), "| last octet < 100:", len(lo), "story", int(lo.src_ip.isin(STORY).sum()))
    so = sorted({int(i.split(".")[3]) for i in STORY}); print("story octets min/max", so[0], so[-1], "| background octets used:", len(set(x[~x.src_ip.isin(STORY)].src_ip)), "min", x[~x.src_ip.isin(STORY)].src_ip.str.split(".").str[3].astype(int).min(), "max", x[~x.src_ip.isin(STORY)].src_ip.str.split(".").str[3].astype(int).max())
    best = None
    oc = x.src_ip.str.split(".").str[3].astype(int); hs = x.src_ip.isin(STORY)
    for lo_ in range(0, 256, 8):
        for hi_ in range(lo_ + 8, 257, 8):
            m = (oc >= lo_) & (oc < hi_)
            if hs[m].sum() >= 8:
                pur = hs[m].sum() / m.sum()
                if best is None or pur > best[0]: best = (pur, lo_, hi_, int(hs[m].sum()), int(m.sum()))
    print("best contiguous octet window holding >= 8 of the 10 story sign-ons: purity %.3f [%d,%d) story %d of %d rows" % best)
    f = fw[fw.src_ip.str.startswith("203.0.113.")]
    for o in ORGS:
        y = f[f.org == o]; print("  firewall", o, "rows from 203.0.113.x:", len(y), "story", int(y.src_ip.isin(STORY).sum()))
    smtp = fw[(fw.dst_port == "25") & (fw.src_ip.str.match(r"^(203\.0\.113|198\.51\.100|192\.0\.2)\."))]
    print("inbound SMTP sessions from documentation ranges:", len(smtp), "story", int(smtp.src_ip.isin(STORY).sum()), smtp.org.value_counts().to_dict())
    conj = au[(au.src_network == "ASN 64512") & (au.auth_method == "password") & (au.device == "new device")]
    print("partner logs ASN 64512 + password + new device:", len(conj), "story", int(conj.src_ip.isin(STORY).sum()))
    e = pd.read_csv(f"{ROOT}/05_other_sources/network_logs/audit/account_logons_city_airstation.csv", dtype=str, keep_default_na=False)
    c2 = e[(e.src_network == "ASN 64512") & (e.auth_method == "password") & (e.device == "new device")]
    print("extract same conjunction:", len(c2), "story", int(c2.src_ip.isin(STORY).sum()))
elif w == "3":
    r = json.load(open(f"{ROOT}/06_data_streams/partner_it_registry.json"))
    b = [o for o in r["organisations"] if o["org_id"] == "BRW"][0]; print("vendor plan:", b["address_plan"])
    fw = load("firewall", ["brw"]); nat = fw[fw.nat_src_ip != ""].nat_src_ip.value_counts()
    print("vendor egress addresses used:", len(nat), "min uses", int(nat.min()), "max", int(nat.max()), "| any 198.51.100.x in vendor logs:", int(fw.apply(lambda x: "198.51.100." in (x.src_ip + x.dst_ip + x.nat_src_ip), axis=1).sum()))
    pool = sorted(nat.index, key=lambda i: int(i.split(".")[3])); print("  pool:", pool[0], "..", pool[-1], "holes:", [i for i in N.VENDOR_OFFICE + N.VENDOR_VPN if i not in set(nat.index)])
    regips = set()
    for o in r["organisations"]:
        for h in o["hosts"]:
            if not h["ip"].startswith("10."): regips.add(h["ip"])
        for k, v in o["address_plan"].items():
            pass
    import ipaddress
    blocks = [ipaddress.ip_network(o["address_plan"]["public_block"]) for o in r["organisations"] if "public_block" in o["address_plan"]]
    for name in ("aid_portal_access", "base_logistics_access"):
        d = portal(name); ips = d[d.client_network != "base network"].client_ip.unique()
        hit = [i for i in ips if i in regips or any(ipaddress.ip_address(i) in b_ for b_ in blocks)]
        print(name, "distinct outside clients", len(ips), "| clients that are a partner registry address or inside a partner public block:", len(hit), hit[:5])
    print("198.51.100.44 rows in aid portal:", int((portal("aid_portal_access").client_ip == "198.51.100.44").sum()))
elif w == "4":
    m = collections.defaultdict(set)
    for kind, ipc, nc in (("auth", "src_ip", "src_network"),):
        d = load(kind); d = d[d[nc].str.startswith("ASN")]
        for ip, n in zip(d[ipc], d[nc]): m[ip].add(n)
    for name in ("aid_portal_access", "base_logistics_access"):
        d = portal(name); d = d[d.client_network.str.startswith("ASN")]
        for ip, n in zip(d.client_ip, d.client_network): m[ip].add(n)
    a = pd.read_csv(f"{ROOT}/05_other_sources/payments/aid_applications.csv", dtype=str, keep_default_na=False); a = a[a.source_ip != ""]
    for ip, n in zip(a.source_ip, a.source_asn): m[ip].add("ASN " + n)
    v = pd.read_csv(f"{ROOT}/05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv", dtype=str, keep_default_na=False)
    for ip, n in zip(v.src_ip, v.src_asn): m[ip].add(n)
    for f in ("account_logons_city_airstation",):
        e = pd.read_csv(f"{ROOT}/05_other_sources/network_logs/audit/{f}.csv", dtype=str, keep_default_na=False)
        for ip, n in zip(e.src_ip, e.src_network): m[ip].add(n)
    multi = {ip: s for ip, s in m.items() if len(s) > 1}
    print("addresses with a network label, all streams:", len(m), "| with more than one label:", len(multi), list(multi.items())[:5])
    by = collections.defaultdict(set)
    for ip, s in m.items(): by[".".join(ip.split(".")[:3]) if ip.split(".")[0] in ("192", "198", "203") else ip.split(".")[0]].update(s)
    print({k: sorted(v) for k, v in by.items() if k in ("192.0.2", "198.51.100", "203.0.113")})
    print("spellings:", collections.Counter(n.split(" ")[0] if " " in n else "?" for s in m.values() for n in s))
elif w == "5":
    for name in ("aid_portal_access", "base_logistics_access"):
        d = portal(name); print(name, "rows from 100.64.0.0/10:", int(d.client_ip.str.match(r"^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.").sum()))
elif w == "6":
    d = portal("aid_portal_access")
    reg_ = d[d.event == "account_created"].set_index("account_ref"); app = d[d.event == "application_submitted"].set_index("account_ref")
    j = reg_.join(app, lsuffix="_r", rsuffix="_a", how="inner"); j = j[j.client_ip_r == j.client_ip_a]
    print("accounts registering and applying from one address:", len(j), "same user agent: %.1f%%" % (100 * (j.user_agent_family_r == j.user_agent_family_a).mean()))
    hum = d[~d.user_agent_family.isin(["python-requests", "curl", "Go-http-client", "zgrab", "okhttp", "Java-http-client", "crawler", "uptime-monitor"])]
    g = hum.groupby("client_ip").user_agent_family.agg(["size", "nunique"]); g4 = g[g["size"] >= 4]
    print("addresses with >= 4 rows:", len(g4), "one user agent:", int((g4["nunique"] == 1).sum()), "two:", int((g4["nunique"] == 2).sum()), "three or more:", int((g4["nunique"] >= 3).sum()))
elif w == "7":
    d = portal("aid_portal_access"); d["t"] = T(d); OPEN = pd.Timestamp("2027-11-13T06:00:00Z")
    hum = d[~d.client_ip.isin(STORY)]
    b, a = hum[hum.t < OPEN].client_network.value_counts(normalize=True), hum[hum.t >= OPEN].client_network.value_counts(normalize=True)
    print("network share before / after registration opens:"); 
    for n in a.index[:12]: print("   ", n, "%.3f" % b.get(n, 0), "%.3f" % a[n])
    print("networks seen only after opening:", [n for n in a.index if n not in b.index], "| only before:", [n for n in b.index if n not in a.index])
    info = hum[(hum.event == "page_view") & hum.path.isin(["/", "/disasters/current", "/help/eligibility", "/help/documents", "/es/ayuda", "/help/contact"])]
    day = info.groupby((info.t - pd.Timedelta(hours=5)).dt.date).size()
    for a_, b_ in (("2027-08-02", "2027-08-08"), ("2027-09-08", "2027-09-13"), ("2027-09-14", "2027-09-14"), ("2027-09-15", "2027-09-21"), ("2027-09-28", "2027-10-04"), ("2027-10-19", "2027-10-25"), ("2027-11-06", "2027-11-12"), ("2027-11-13", "2027-11-19"), ("2027-12-20", "2027-12-26")):
        s = day[(day.index >= pd.Timestamp(a_).date()) & (day.index <= pd.Timestamp(b_).date())]; print("   info views/day", a_, "to", b_, "mean %.0f" % s.mean())
    wk = info[(info.t < pd.Timestamp("2027-09-01", tz="UTC"))]; dd_ = (wk.t - pd.Timedelta(hours=5)).dt.normalize(); c = wk.groupby(dd_).size(); print("   Jul-Aug info views per weekday day %.0f, per weekend day %.0f" % (c[c.index.weekday < 5].mean(), c[c.index.weekday >= 5].mean()))
    print("   page shares:", (info.path.value_counts(normalize=True) * 100).round(1).to_dict())
    ls = hum[hum.event == "login_success"]; h = ((ls.t - pd.Timedelta(hours=6)).dt.hour.value_counts(normalize=True).sort_index() * 100).round(1)
    print("   login_success share by local hour: min %.1f max %.1f" % (h.min(), h.max()), h.to_dict())
elif w == "8":
    d = portal("aid_portal_access"); hum = d[~d.client_ip.isin(STORY)]
    print("register: GET", int(((hum.path == "/account/register") & (hum.method == "GET")).sum()), "POST", int(((hum.path == "/account/register") & (hum.method == "POST")).sum()), "| GET /applications", int(((hum.path == "/applications") & (hum.method == "GET")).sum()), "GET /applications/new", int((hum.path == "/applications/new").sum()))
    r = hum[hum.event == "account_created"].assign(t=lambda x: T(x)).set_index("account_ref").t; a = hum[hum.event == "application_submitted"].assign(t=lambda x: T(x)).set_index("account_ref").t
    dt = (a - r.reindex(a.index)).dt.total_seconds().dropna(); print("register->apply seconds percentiles 5/25/50/75/95/99:", [int(x) for x in np.percentile(dt, [5, 25, 50, 75, 95, 99])], "accounts created without an application:", int((~r.index.isin(a.index)).sum()))
    ls = hum[hum.event == "login_success"].groupby("account_ref").size(); allacc = set(a.index)
    print("applicants who never sign in again: %.0f%%; sign-ins per returning applicant 50/90/max: %s" % (100 * (1 - len(set(ls.index) & allacc) / len(allacc)), [int(np.percentile(ls, 50)), int(np.percentile(ls, 90)), int(ls.max())]))
    st = hum[hum.path == "/status"].groupby("account_ref").size(); print("status views per account with any: 50/90/max", [int(np.percentile(st, 50)), int(np.percentile(st, 90)), int(st.max())])
    print("ordinary status codes:", hum.status.value_counts().to_dict())
    hum2 = hum.assign(b=hum.bytes.astype(int)); print("median bytes by path:", hum2[hum2.status == "200"].groupby("path").b.median().sort_values().astype(int).to_dict())
    s = d[d.client_ip.isin(STORY) & (d.event == "login_failed")]; print("story failed logins:", len(s), "with an account id:", int((s.account_ref != "").sum()), "distinct ids", s[s.account_ref != ""].account_ref.nunique(), "that exist:", len(set(s.account_ref) & set(r.index)))
    print("exact duplicate rows aid:", int(d.duplicated().sum()))
    L = portal("base_logistics_access"); L["t"] = T(L); inn = L[L.client_network == "base network"]
    hrs = ((inn.t - pd.Timedelta(hours=5)).dt.hour.value_counts(normalize=True).sort_index() * 100).round(1); print("logistics inside rows:", len(inn), "share 08-16 local: %.0f%%, 00-05: %.1f%%" % (hrs[8:17].sum(), hrs[0:6].sum()))
    dd = inn.groupby((inn.t - pd.Timedelta(hours=5)).dt.date).size(); wdm = pd.Series(dd.values, index=pd.to_datetime(dd.index)); print("logistics per weekday %.0f, weekend day %.0f, Thanksgiving %d" % (wdm[wdm.index.weekday < 5].mean(), wdm[wdm.index.weekday >= 5].mean(), int(wdm.get(pd.Timestamp("2027-11-25"), 0))))
    ac = inn[inn.account_ref != ""].groupby("account_ref").client_ip.nunique(); print("accounts", len(ac), "addresses per account 50/90/max", [int(np.percentile(ac, 50)), int(np.percentile(ac, 90)), int(ac.max())])
    regacc = {a_["account"] for o in json.load(open(f"{ROOT}/06_data_streams/partner_it_registry.json"))["organisations"] if o["org_id"] == "NASCC" for a_ in o["accounts"]}
    print("logistics accounts not in the air station registry:", len(set(ac.index) - regacc))
    f = inn[inn.event == "login_failed"].sort_values("t"); s_ = inn[inn.event == "login_success"]
    ok = 0
    sk = s_.groupby("account_ref").t.apply(list).to_dict()
    for a_, t_ in zip(f.account_ref, f.t):
        ok += any(0 < (x - t_).total_seconds() <= 120 for x in sk.get(a_, []))
    print("logistics failed logins:", len(f), "followed by success within two minutes:", ok); print("exact duplicate rows logistics:", int(L.duplicated().sum()))
elif w == "9":
    cap = pd.read_csv(f"{ROOT}/05_other_sources/public_health/hospital_capacity.csv", dtype=str, keep_default_na=False)
    r = {o["org_id"]: o for o in json.load(open(f"{ROOT}/06_data_streams/partner_it_registry.json"))["organisations"]}
    for org in ("srmc", "bcmc"):
        o = r[org.upper()]; fac = o["facility_id"]; c = cap[cap.Facility_ID == fac]
        lost = c[c.Commercial_Power_Lost_UTC != ""].Commercial_Power_Lost_UTC.iloc[0]; back = c[c.Commercial_Power_Restored_UTC != ""].Commercial_Power_Restored_UTC.iloc[0]
        adm = {h["host_id"] for h in o["hosts"] if h["site_id"] == "ADM"}; admip = {h["ip"] for h in o["hosts"] if h["site_id"] == "ADM"}
        au, we, ep = load("auth", [org]), load("web", [org]), load("endpoint_alerts", [org])
        a = au[au.host.isin(adm) & (au.time_utc >= lost) & (au.time_utc < back)]; w_ = we[we.client_ip.isin(admip) & (we.time_utc >= lost) & (we.time_utc < back)]; e = ep[ep.host.isin(adm) & (ep.time_utc >= lost) & (ep.time_utc < back)]
        print(org, "window", lost, back, "| administration wing rows inside: auth", len(a), "web", len(w_), "endpoint", len(e))
    au = load("auth", ["nascc"]); o = r["NASCC"]; adm = {h["host_id"] for h in o["hosts"] if h["site_id"] == "ADM"}
    x = au[au.host.isin(adm) & (au.event_id == "4624")]; print("air station administration building logons by date:", {d_: int((x.time_utc.str[:10] == d_).sum()) for d_ in ("2027-09-08", "2027-09-09", "2027-09-10", "2027-09-11", "2027-09-12", "2027-09-13", "2027-09-15", "2027-09-21")})
elif w == "10":
    au = load("auth"); au["t"] = T(au)
    for org in ORGS:
        a = au[au.org == org]; ws = a[a.event_id.isin(["4624", "4625", "4634", "login", "login-failed", "logout"]) & (a.logon_type.isin(["2", "console"]))]
        on = ws[ws.event_id.isin(["4624", "login"])].sort_values("t"); off = ws[ws.event_id.isin(["4634", "logout"])]
        m = on.merge(off, on=["host", "account"], suffixes=("", "_o")); m = m[m.t_o > m.t]; m = m.sort_values("t_o").groupby(["host", "account", "t"]).first().reset_index()
        ln = (m.t_o - m.t).dt.total_seconds() / 3600
        f = ws[ws.event_id.isin(["4625", "login-failed"])]
        ok = on.groupby(["host", "account"]).t.apply(lambda s: s.values).to_dict()
        fol = sum(any(0 <= (x - np.datetime64(t_.tz_convert(None))) / np.timedelta64(1, "s") <= 3600 for x in ok.get((h, a_), [])) for h, a_, t_ in zip(f.host, f.account, f.t))
        rem = a[a.logon_type == "remote"]; hr = (rem.t - pd.Timedelta(hours=5)).dt.hour.value_counts(normalize=True).sort_index()
        lh = (on.t - pd.Timedelta(hours=5)).dt.hour.value_counts().reindex(range(24), fill_value=0)
        print(org, "session h pct 5/25/50/75/95: %s | ws fail share %.1f%% followed by success within 1 h %.0f%% | remote fail %.1f%% | remote share 02h %.1f 12h %.1f 19h %.1f | empty logon hours %s" % (
            [round(float(x), 1) for x in np.percentile(ln, [5, 25, 50, 75, 95])], 100 * len(f) / max(1, len(f) + len(on)), 100 * fol / max(1, len(f)),
            100 * (rem.result == "FAILED").mean(), 100 * hr.get(2, 0), 100 * hr.get(12, 0), 100 * hr.get(19, 0), [h for h in range(24) if lh[h] == 0]))
    ep = load("endpoint_alerts"); print((ep.groupby("org").event.value_counts(normalize=True).unstack().fillna(0) * 100).round(0).astype(int).to_string())
    fw = load("firewall"); dn = fw[fw.action == "deny"]; top = dn.dst_port.value_counts().index[:6]
    print((dn.groupby("org").dst_port.value_counts(normalize=True).unstack().fillna(0)[top] * 100).round(0).astype(int).to_string())
    we = load("web"); we = we[(we.action == "allowed")]; we["k"] = we.org + "|" + we.client_ip + "|" + we.time_utc
    f2 = fw[(fw.action == "allow") & fw.dst_port.isin(["443", "80"])].copy(); f2["st"] = (T(f2) - pd.to_timedelta(f2.duration_s.astype(float).round(), unit="s")).dt.strftime("%Y-%m-%dT%H:%M:%SZ"); f2["k"] = f2.org + "|" + f2.src_ip + "|" + f2.st
    j = we.drop_duplicates("k").merge(f2.drop_duplicates("k"), on="k"); ratio = j.bytes_recv.astype(float) / j.bytes_in.astype(float).clip(lower=1); ratio = ratio[j.bytes_in.astype(float) > 20000]
    print("firewall bytes_recv / web bytes_in for larger flows: pct 5/50/95", [round(float(x), 3) for x in np.percentile(ratio, [5, 50, 95])], "n", len(ratio))
elif w == "minor":
    ma = load("mail"); ma["t"] = T(ma)
    inb = ma[ma.direction == "inbound"]; g = inb.groupby(["org", "sender_domain", "subject"]).agg(n=("sender", "size"), senders=("sender", "nunique")).reset_index(); big = g[g.n >= 100].sort_values("n", ascending=False)
    print(big.head(14).to_string(index=False)); print("bulk mailings with a count that is a multiple of 10:", int((big.n % 10 == 0).sum()), "of", len(big))
    r = {o["org_id"]: o for o in json.load(open(f"{ROOT}/06_data_streams/partner_it_registry.json"))["organisations"]}
    mac = {h["ip"]: h["host_id"] for h in r["BRW"]["hosts"] if h["os"].startswith("macOS")}; we = load("web", ["brw"]); x = we[we.client_ip.isin(mac)]
    print("vendor macOS hosts", len(mac), "web rows", len(x), x.user_agent_family.value_counts().to_dict()); au = load("auth", ["brw"]); print("  their auth event ids:", au[au.host.isin(set(mac.values()))].event_id.value_counts().to_dict())
    for f in sorted(glob.glob(f"{ROOT}/06_data_streams/schemas/partner_*_schema.json")):
        s = open(f).read(); print(os.path.basename(f), "generator path:", "scripts/" in s, "verified flag:", '"verified"' in s)
    v = pd.read_csv(f"{ROOT}/05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv", dtype=str, keep_default_na=False); fw = load("firewall", ["brw"]); dz = fw[fw.device == "BRW-FW-DMZ-01"]
    ds = collections.Counter()
    for _, s in v[v.result == "SUCCESS"].iterrows():
        m = dz[(dz.src_ip == s.src_ip)]; m = m[(m.duration_s.astype(float) - float(s.duration_s)).abs() < 12]
        if len(m): ds[round(float(m.duration_s.iloc[0]) - float(s.duration_s))] += 1
    print("gateway firewall session minus vessel session seconds:", dict(sorted(ds.items())))
    for k in ("firewall", "web", "dns", "auth", "mail", "endpoint_alerts"):
        d = load(k); print(k, "exact duplicate rows:", int(d.duplicated().sum()))
    print("aid portal duplicates:", int(portal("aid_portal_access").duplicated().sum()))
