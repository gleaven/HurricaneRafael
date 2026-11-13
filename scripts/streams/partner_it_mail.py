"""Mail gateway logs of the partner organisations.

Every organisation has its own correspondents (several hundred outside domains with a long tail, people who write
again and again), its own subjects (by sector, by season), internal mail between registry mailboxes, replies,
outgoing mail, bulk mailings, junk that the gateway quarantines or rejects. The few messages canon fixes are
written by the same emit() as everything else.
"""
import numpy as np

import partner_it_model as P
from common import D0_EPOCH, local_dt, local_ts, rng, ts

DAY = P.DAY
hsh, hint, h01 = P.hsh, P.hint, P.h01

A_WORDS = ["gulf", "coastal", "bayside", "lonestar", "southtex", "harbor", "mesa", "brazos", "nueces", "padre", "laguna", "redfish", "mustang", "aransas", "bluewave",
           "tidewater", "sabal", "oleander", "pelican", "heron", "anchor", "keel", "delta", "alamo", "rio", "frontera", "prairie", "hilltop", "summit", "pioneer", "liberty",
           "unity", "apex", "vertex", "nova", "orbit", "zenith", "cobalt", "granite", "cedar", "mesquite", "liveoak", "cypress", "magnolia", "bluebonnet", "kingfisher",
           "saltgrass", "driftwood", "seawall", "baypoint", "shoreline", "ingleside", "portland", "calallen", "flourbluff", "rockport", "kleberg", "sanpat", "tejano", "caliche"]
B_WORDS = {
    "generic": ["supply", "services", "consulting", "logistics", "solutions", "group", "partners", "associates", "systems", "tech", "office", "print", "staffing", "legal", "cpa",
                "insurance", "bank", "creditunion", "realty", "construction", "electric", "plumbing", "hvac", "fleet", "rentals", "catering", "uniforms", "signs", "media", "events",
                "telecom", "security", "janitorial", "landscaping", "paving", "surveying", "architects", "engineers", "auto", "tires"],
    "gov": ["isd", "utilities", "housing", "transit", "appraisal", "cog", "mud", "college", "library-foundation", "chamber", "rotary", "nonprofit", "foodbank", "redevelopment",
            "drainage", "airport", "conventions", "parks-foundation", "animal-care", "workforce"],
    "health": ["medsupply", "pharma", "radiology", "labs", "homehealth", "ems", "clinic", "physicians", "healthplan", "dialysis", "rehab", "oncology", "anesthesia", "nurse-staffing",
               "biomed", "surgical", "pathology", "hospice", "imaging", "cardiology", "pediatrics", "orthopedics"],
    "maritime": ["marine", "shipping", "towing", "pilots", "stevedores", "terminals", "ship-agency", "bunkers", "chandlers", "offshore", "dredging", "surveyors", "customs-brokers",
                 "freight", "pipeline", "refining", "tankers", "drydock", "barge", "crane-services", "rail", "trucking"],
    "navy": ["aviation-services", "avionics", "training-systems", "base-housing", "aero-parts", "flight-support", "simulation", "range-services", "contract-logistics", "depot-repair",
             "ground-support", "fuel-services"],
    "eng": ["automation", "controls", "instrumentation", "valves", "pumps", "shipyard", "electronics", "calibration", "hydraulics", "tank-gauging", "class-surveys", "loading-systems",
            "firmware", "components", "cabling", "panels"],
}
COMMON = ["officesuite-mail", "docsign-flow", "cloudstorage-sync", "hrcloud-payroll", "benefits-portal", "training-lms", "helpdesk-tickets", "packagetracker", "meetroom-video",
          "fleetfuel-cards", "partsdepot-supply", "airline-bookings", "hotel-reservations", "bank-online", "insurance-claims", "newswire-national", "cellcarrier-account",
          "partner-mail", "retail-orders", "utilitybilling-pay", "txstate-agencies", "federal-notices", "surveys-online", "webinar-invites", "jobboard-alerts"]
PEERS = {"CITY": "cctexas.example", "NASCC": "nascc.navy.example", "BRW": "brightwake-marine.example", "PORT": "portofcc.example", "SRMC": "shorelineregional.example",
         "BCMC": "baycitymedical.example", "COUNTY": "nuecesco.example"}
OTHER_LOCAL = ["cbpwa.example", "uscg-sector-cc.example", "nclas-language.example", "cbecc.example"]
ROLE = ["info", "billing", "noreply", "notifications", "support", "sales", "orders", "accounts", "admin", "office", "dispatch", "scheduling", "service", "ap", "ar", "hr"]
LAST = ["garcia", "martinez", "rodriguez", "hernandez", "lopez", "gonzalez", "perez", "sanchez", "ramirez", "flores", "smith", "johnson", "williams", "brown", "jones", "miller",
        "davis", "wilson", "anderson", "taylor", "thomas", "moore", "jackson", "white", "harris", "clark", "lewis", "walker", "young", "allen", "king", "wright", "scott", "nguyen",
        "tran", "pham", "patel", "kim", "cantu", "salinas", "trevino", "guerra", "villarreal", "pena", "longoria", "benavides", "ochoa", "zamora", "becker", "schultz"]

# subject templates: {n} number, {w} week ending date, {m} month name, {p} project or topic word
T_GENERIC = ["Invoice {n}", "PO {n} confirmation", "Quote {n}", "Meeting notes - {p}", "Agenda: {p}", "{p} schedule w/e {w}", "Timesheet reminder", "Delivery notice {n}",
             "Ticket #{n} updated", "Your order {n} has shipped", "Statement for {m}", "Contract renewal - {p}", "Updated contact list", "Minutes {w}", "Training: {p}",
             "Password expiry notice", "Voicemail from {n}", "Scanned document {n}", "Out of office", "Lunch?", "Parking lot resurfacing", "{m} newsletter", "Webinar: {p}",
             "Expense report {n}", "Purchase request {n}", "Reminder: {p}", "Question about {p}", "Call back request", "Vendor registration update", "W-9 request"]
T_SECTOR = {
    "gov": ["Permit application {n}", "Council agenda item {n}", "Public information request {n}", "Work order {n}", "Bid tabulation {p}", "Inspection scheduled {w}",
            "Grant report - {p}", "Citizen request {n}", "Road closure notice {w}", "Budget amendment {n}", "Docket {n}", "Tax statement inquiry {n}", "Jury summons question"],
    "navy": ["Plan of the week {w}", "Supply requisition {n}", "Duty roster {w}", "Training requirement: {p}", "Facility work request {n}", "Fuel order {n}", "Gate access list {w}",
             "Flight schedule {w}", "Safety stand-down notes", "Housing office notice", "Watchbill change {w}"],
    "eng": ["Service ticket BW-{n}", "RE: commissioning report {p}", "Class survey documents {n}", "Spare parts quotation {n}", "Firmware release notes {n}", "Site visit {w}",
            "Loading computer certificate {n}", "Drawing revision {n}", "FAT protocol {p}", "Warranty claim {n}", "Remote support request {n}"],
    "maritime": ["Vessel schedule update {w}", "Berth request {n}", "Gate transaction report {w}", "Tariff invoice {n}", "Notice of arrival {n}", "Line handling order {n}",
                 "Dock maintenance {w}", "Cargo manifest {n}", "Pilot order {n}", "Security plan review {p}", "Dredging survey {w}"],
    "health": ["Shift swap request {w}", "Lab interface downtime {w}", "Credentialing packet {n}", "Supply backorder {n}", "On-call schedule {w}", "Policy update: {p}",
               "Bed management huddle {w}", "Pharmacy formulary change {n}", "Equipment service report {n}", "Referral {n}", "Transcription {n}", "CME session: {p}"],
}
T_STORM = ["Storm readiness checklist", "Situation report #{n}", "Facility status after Rafael", "Damage assessment form {n}", "Employee check-in", "Office closure notice",
           "Generator fuel request {n}", "Debris pickup schedule", "Temporary work location", "Insurance adjuster visit {w}", "Road access update", "Supply request {n}",
           "Staffing during recovery", "Water service update"]
T_HOLIDAY = ["Holiday schedule", "Year-end closing deadlines", "Holiday luncheon", "Office closed {w}", "Toy drive"]
T_SPAM = ["You have a pending delivery", "Invoice overdue - final notice", "Account verification required", "Claim your reward today", "Mailbox quota exceeded", "Re: your application",
          "Limited time offer", "Payment receipt {n}", "New fax received", "Urgent: document shared with you", "Lower your rates now", "Your subscription is expiring", "Meet singles near you",
          "Congratulations, you were selected", "Remote job offer"]
TOPICS = ["Q3 review", "safety", "budget", "fleet", "IT refresh", "audit", "onboarding", "phones", "inventory", "compliance", "roof repair", "open house", "wellness", "records",
          "payroll", "procurement", "HVAC", "badge access", "radio system", "website", "leases", "uniforms", "insurance", "retirement"]
ATT_EXT = [("pdf", 0.52), ("docx", 0.16), ("xlsx", 0.15), ("jpg", 0.08), ("zip", 0.03), ("pptx", 0.03), ("csv", 0.03)]
CAMPAIGNS = {  # (first local day, days, messages, sender domain word, local part, subject)
    "CITY": [(-43, 4, 780, "training-lms", "noreply", "Assigned: cybersecurity awareness course"), (34, 5, 860, "benefits-portal", "enrollment", "Open enrollment is now open"),
             (41, 3, 540, "benefits-portal", "enrollment", "Reminder: open enrollment closes Friday"),
             (1, 3, 620, None, "hr", "Employee check-in: reply with your status"), (72, 3, 150, "surveys-online", "survey", "Employee engagement survey")],
    "NASCC": [(-36, 3, 370, "training-lms", "noreply", "Annual training requirement due"), (-6, 2, 390, None, "quarterdeck", "Hurricane condition update - all hands"),
              (55, 4, 330, "federal-notices", "benefits", "Federal benefits open season")],
    "BRW": [(41, 4, 60, "benefits-portal", "enrollment", "Open enrollment is now open")],
    "PORT": [(-30, 3, 110, "training-lms", "noreply", "Annual security awareness refresher"), (2, 3, 140, None, "hr", "Employee check-in"), (48, 4, 120, "benefits-portal", "enrollment", "Open enrollment")],
    "SRMC": [(20, 5, 230, None, "nursing.admin", "Flu vaccination clinic schedule"), (-48, 4, 210, "training-lms", "noreply", "Mandatory competency modules assigned"),
             (1, 2, 260, None, "hr", "Staff recall and status roster"), (60, 4, 180, "benefits-portal", "enrollment", "Benefits enrollment reminder")],
    "BCMC": [(23, 4, 150, None, "hr", "Flu shot clinic sign-up"), (-20, 3, 120, "training-lms", "noreply", "Annual compliance training"), (2, 2, 170, None, "hr", "Staff status roll call")],
    "COUNTY": [(-25, 3, 150, "training-lms", "noreply", "Cybersecurity training assigned"), (1, 3, 200, None, "hr", "Employee accountability check"), (40, 4, 160, "benefits-portal", "enrollment", "Open enrollment period")],
}
W_HOUR = np.array([1, 1, 1, 1, 1, 2, 4, 8, 12, 13, 13, 12, 10, 12, 13, 12, 10, 6, 4, 3, 2, 2, 1, 1], float)
W_HOUR_BULK = np.array([2, 2, 2, 2, 2, 3, 4, 5, 6, 6, 6, 6, 5, 5, 5, 5, 5, 4, 4, 3, 3, 3, 2, 2], float)


def _name(g, sector):
    a = A_WORDS[int(g.integers(len(A_WORDS)))]
    b = B_WORDS[sector][int(g.integers(len(B_WORDS[sector])))]
    return f"{a}{'-' if g.random() < 0.45 else ''}{b}.example"


def mid(dom, *key):
    """A message id in the style of the sending system (the style is a property of the sender's domain)."""
    style = hint("midstyle", dom) % 5
    x = hsh("mid", dom, *key, n=40)
    if dom in (P.LURE_DOM, P.BRW_LURE_DOM):
        return None
    if style == 0:
        return f"<{x[:16 + 4 * (hint('midlen', dom) % 3)]}@{dom}>"
    if style == 1:
        return f"<{int(x[:10], 16) % 10 ** 14:014d}.{x[10:18]}@mail.{dom}>"
    if style == 2:
        return f"<{x[:8]}-{x[8:12]}-{x[12:16]}-{x[16:20]}-{x[20:32]}@{dom}>"
    if style == 3:
        return f"<{x[:20].upper()}@mx.{dom}>"
    return f"<{x[:12]}${x[12:20]}${x[20:28]}@{dom.split('.')[0]}>"


class World:
    def __init__(self, org):
        self.org, o = org, P.ORGS[org]
        g = rng("partner_it", "mailworld", org)
        self.dom = o["domain"]
        self.boxes = P.mailboxes(org)
        self.staff = [a["mailbox"] for a in P.registry()[org]["accounts"] if a["kind"] == "staff"]
        w = g.gamma(0.7, 1.0, len(self.staff)) + 0.05                      # some people write and receive far more than others
        self.staff_cum = np.cumsum(w / w.sum())
        names, kinds = [], []
        for c in COMMON:
            names.append(c + ".example")
            kinds.append("common")
        if org != "BRW":
            for k, d in PEERS.items():
                if k != org and (k != "BRW" or org == "PORT"):
                    names.append(d)
                    kinds.append("peer:" + k)
            names += OTHER_LOCAL
            kinds += ["local"] * len(OTHER_LOCAL)
        seen = set(names)
        sectors = o["sector"]
        while len(names) < o["domains"]:
            sec = sectors[0] if g.random() < 0.55 else sectors[int(g.integers(len(sectors)))]
            n = _name(g, sec)
            if n not in seen:
                seen.add(n)
                names.append(n)
                kinds.append(sec)
        order = g.permutation(len(names))
        wt = np.zeros(len(names))
        for rank, i in enumerate(order):
            wt[i] = 1.0 / (rank + 4) ** 1.08 * (2.2 if kinds[i].startswith("peer") or kinds[i] in (sectors[0], "local") else 1.0)
        self.names, self.kinds, self.dom_cum = names, kinds, np.cumsum(wt / wt.sum())
        self.senders = {}
        self.recent = []                                                   # earlier messages someone may still answer

    def staff_box(self, g):
        return self.staff[min(len(self.staff) - 1, int(np.searchsorted(self.staff_cum, g.random())))]

    def correspondent(self, g):
        """(address, domain) of an outside correspondent; the same people keep writing."""
        i = min(len(self.names) - 1, int(np.searchsorted(self.dom_cum, g.random())))
        dom, kind = self.names[i], self.kinds[i]
        if kind.startswith("peer:"):
            mbs = P.mailboxes(kind[5:])
            return mbs[hint("peerbox", self.org, dom, int(g.integers(0, 14))) % len(mbs)], dom
        if dom not in self.senders:
            k = 1 + hint("nsend", dom) % 9
            role = kind == "common" or hint("role", dom) % 4 == 0
            self.senders[dom] = [(ROLE[hint("rl", dom, j) % len(ROLE)] if role and j < 3 else
                                  f"{chr(97 + hint('fi', dom, j) % 26)}.{LAST[hint('ln', dom, j) % len(LAST)]}") + "@" + dom for j in range(k)]
        s = self.senders[dom]
        return s[min(len(s) - 1, int(g.gamma(1.0, 1.2)))], dom

    def subject(self, g, d, t):
        o = P.ORGS[self.org]
        sec = o["sector"][0]
        l = local_dt(t)
        r = g.random()
        if self.org in P.STORM_AFFECTED and -5 <= d <= 34 and r < (0.34 if 0 <= d <= 12 else 0.12):
            tpl = T_STORM[int(g.integers(len(T_STORM)))]
        elif (l.month, l.day) >= (11, 15) and r < 0.07 or (l.month == 1 and l.day <= 5 and r < 0.04):
            tpl = T_HOLIDAY[int(g.integers(len(T_HOLIDAY)))]
        elif r < 0.5:
            lst = T_SECTOR[sec]
            tpl = lst[min(len(lst) - 1, int(g.gamma(1.4, len(lst) / 3.2)))]
        else:
            tpl = T_GENERIC[min(len(T_GENERIC) - 1, int(g.gamma(1.4, len(T_GENERIC) / 3.0)))]
        wk = (l + __import__("datetime").timedelta(days=(4 - l.weekday()) % 7))
        s = tpl.format(n=int(g.integers(1000, 99999)), w=f"{wk.month}/{wk.day}", m=l.strftime("%B"), p=TOPICS[int(g.integers(len(TOPICS)))])
        if g.random() < 0.08:
            s = "FW: " + s
        return s

    def attachment(self, g, subj, p=0.2):
        if g.random() >= p:
            return ""
        ext = P.pick(ATT_EXT, g.random())
        stem = "".join(c if c.isalnum() else "_" for c in subj.replace("RE: ", "").replace("FW: ", ""))[:24].strip("_") or "document"
        return f"{stem}{'_' + str(int(g.integers(1, 9))) if g.random() < 0.2 else ''}.{ext}"


def mta_of(dom, t):
    """Address of the outside mail server a domain's mail comes from or goes to."""
    if dom in (P.LURE_DOM, P.BRW_LURE_DOM):
        import netmap
        return netmap.story_ip(17 + hint("mta", dom, int(t // 7200)) % 6)
    return P.stable_ip("mta", dom)


def gen(org):
    """[(epoch, row, peer)] for the organisation's mail gateway. row has the twelve delivered columns with time_utc
    left empty; peer is the outside mail server's address for mail that crosses the internet, or None."""
    o = P.ORGS[org]
    W = World(org)
    gw, dom = o["mx"][0], W.dom
    out = []

    def emit(t, direction, sender, sdom, rcpt, subj, att, size, verdict="clean", action="delivered", m=None):
        peer_dom = sdom if direction == "inbound" else (rcpt.split("@")[1] if direction == "outbound" else None)
        peer = None
        if peer_dom:
            peer = mta_of(peer_dom, t)
        out.append((t, [None, gw, direction, sender, sdom, rcpt, subj, att, int(size), verdict, action, m or mid(sdom, t, rcpt, subj)], peer))

    d_first, d_last = int((P.SPAN_A - D0_EPOCH) // DAY), int((P.SPAN_B - 1 - D0_EPOCH) // DAY)
    mix = o["mail_mix"]
    for d in range(d_first, d_last + 1):
        t0 = D0_EPOCH + d * DAY
        g = rng("partner_it", "mail", org, d)
        dl = P.lday(t0 + 43200)
        f = 0.22 + 0.78 * P.day_factor(org, dl)
        if org in P.STORM_AFFECTED:
            f *= {-1: 0.8, 0: 0.3, 1: 0.4, 2: 0.5, 3: 0.6, 4: 0.75, 5: 0.8}.get(dl, 1.0)
        off = int(-local_dt(t0 + 43200).utcoffset().total_seconds() // 3600)
        n = int(g.poisson(o["mail_per_day"] * f))
        hw = np.roll(W_HOUR, off)
        times = np.sort(t0 + g.choice(24, n, p=hw / hw.sum()) * 3600 + g.integers(0, 3600, n))
        for t in times:
            t = int(t)
            r = g.random()
            if W.recent and r < 0.24:                                       # an answer to an earlier message
                i = int(g.integers(max(0, len(W.recent) - 400), len(W.recent)))
                t1, dirn, snd, sd, rc, sj = W.recent[i]
                if 240 < t - t1 < 3 * DAY and rc.endswith("@" + dom):
                    sj2 = sj if sj.startswith("RE: ") else "RE: " + sj
                    nd = "internal" if dirn == "internal" else "outbound"
                    emit(t, nd, rc, dom, snd, sj2, W.attachment(g, sj2, 0.08), g.gamma(2, 16000) + 2500)
                    W.recent.append((t, nd, rc, dom, snd, sj2))
                    continue
            r = g.random()
            if r < mix[0]:                                                  # from outside
                junk = g.random()
                if junk < o["spam"]:
                    sd = f"{A_WORDS[int(g.integers(len(A_WORDS)))]}{hsh('sp', t, org, n=4)}-{B_WORDS['generic'][int(g.integers(40))]}.example"
                    sj = T_SPAM[int(g.integers(len(T_SPAM)))].format(n=int(g.integers(1000, 99999)))
                    emit(t, "inbound", f"{ROLE[int(g.integers(len(ROLE)))]}@{sd}", sd, W.staff_box(g), sj, "", g.gamma(2, 5000) + 1500, "spam", "quarantined")
                elif junk < o["spam"] + 0.006:
                    sd = f"{A_WORDS[int(g.integers(len(A_WORDS)))]}{hsh('bl', t, org, n=4)}.example"
                    k = int(g.integers(4))
                    emit(t, "inbound", f"{ROLE[int(g.integers(len(ROLE)))]}@{sd}", sd, W.staff_box(g), ["Scanned document", "Payment advice", "Voicemail", "Delivery label"][k],
                         ["scan_{}.html", "payment_{}.iso", "voicemail_{}.htm", "label_{}.xlsm"][k].format(int(g.integers(1000, 99999))), g.gamma(2, 60000) + 4000,
                         "blocked attachment type", "quarantined")
                elif junk < o["spam"] + 0.011:
                    sd = W.names[int(g.integers(len(W.names)))]
                    emit(t, "inbound", f"{ROLE[int(g.integers(len(ROLE)))]}@{sd}", sd, W.staff_box(g), ["Payroll update needed", "Wire request", "Quick favor", "Updated bank details"][int(g.integers(4))],
                         "", g.gamma(2, 4000) + 1500, "sender failed authentication", "rejected")
                else:
                    if g.random() < 0.055:                                  # someone who writes once and never again
                        sec = o["sector"][int(g.integers(len(o["sector"])))]
                        sd = _name(g, sec)
                        snd = f"{chr(97 + int(g.integers(26)))}.{LAST[int(g.integers(len(LAST)))]}@{sd}"
                    else:
                        snd, sd = W.correspondent(g)
                    sj = W.subject(g, dl, t)
                    rc = W.staff_box(g) if g.random() < 0.93 else W.boxes[int(g.integers(len(W.boxes)))]
                    emit(t, "inbound", snd, sd, rc, sj, W.attachment(g, sj, 0.24), g.gamma(2, 38000) + 2500)
                    W.recent.append((t, "inbound", snd, sd, rc, sj))
            elif r < mix[0] + mix[1]:                                       # between colleagues
                snd, rc = W.staff_box(g), W.staff_box(g)
                if snd != rc:
                    sj = W.subject(g, dl, t)
                    emit(t, "internal", snd, dom, rc, sj, W.attachment(g, sj, 0.17), g.gamma(2, 30000) + 2000)
                    W.recent.append((t, "internal", snd, dom, rc, sj))
            else:                                                           # to outside
                rc, _ = W.correspondent(g)
                snd = W.staff_box(g)
                sj = W.subject(g, dl, t)
                emit(t, "outbound", snd, dom, rc, sj, W.attachment(g, sj, 0.22), g.gamma(2, 36000) + 2500)
    # ---- bulk mailings (training assignments, benefits, all-staff notices)
    for d0, days, n, word, local, sj in CAMPAIGNS.get(org, []):
        g = rng("partner_it", "campaign", org, d0, sj)
        if word is None:
            snd, sd, dirn = f"{local}@{dom}", dom, "internal"
        else:
            sd = word + ".example"
            snd, dirn = f"{local}@{sd}", "inbound"
        t_a = local_ts(d0, "06:00") + int(g.integers(0, 4 * 3600))
        n = int(n * g.uniform(0.9, 1.08)) + int(g.integers(0, 9))        # mailing lists are never round numbers
        many = word in ("training-lms", "surveys-online", "federal-notices", "benefits-portal")     # bulk-mail platforms rotate numbered sender addresses
        for i in range(n):
            t = t_a + int(min(g.exponential(days * DAY / 3.2), days * DAY))
            emit(t, dirn, f"{local}-{int(g.integers(10, 99))}@{sd}" if many else snd, sd, W.boxes[int(g.integers(len(W.boxes)))], sj, "", g.integers(14000, 42000))
    # ---- records other delivered streams and canon fix
    for t, snd, rc, size, m in P.wave(org):
        emit(t, "inbound", snd, P.LURE_DOM, rc, P.LURE_SUBJECT, "", size, m=m)
    if org == "BRW":
        emit(P.BRW_LURE_T, "inbound", "class-renewals@" + P.BRW_LURE_DOM, P.BRW_LURE_DOM, "remote.support@" + dom, "Remote access certificate renewal required", "", 48211,
             m="<" + hsh("bw") + "@" + P.BRW_LURE_DOM + ">")
    if org == "COUNTY":                                    # translation requests and deliveries (delivered broadcast/translation_jobs.csv)
        for r in P.read_csv("broadcast/translation_jobs.csv"):
            if r["translator"] != "NCLAS":
                continue
            g = rng("partner_it", "tr", r["job_id"])
            box = "eoc.pio@" + dom
            emit(ts(r["source_received_utc"]) - int(g.integers(15, 90)), "outbound", box, dom, "requests@nclas-language.example", f"Translation request {r['job_id']}",
                 "" if not r["alert_id"] else "alert_text_en.pdf", g.integers(18000, 90000))
            if r["translation_delivered_utc"]:
                emit(ts(r["translation_delivered_utc"]) + int(g.integers(0, 40)), "inbound", "delivery@nclas-language.example", "nclas-language.example", box,
                     f"Translation delivered {r['job_id']}", "alert_text_es.pdf", g.integers(18000, 90000))
    if org == "PORT":                                      # port orders as they reached the operations mailbox (delivered supply/port_conditions.csv)
        seen = set()
        for r in P.read_csv("supply/port_conditions.csv"):
            key = (r["order_id"], r["issued_utc"])
            if key in seen or not r["issued_utc"]:
                continue
            seen.add(key)
            g = rng("partner_it", "msib", *key)
            t = ts(r["issued_utc"]) + int(g.integers(40, 420))
            sj, att = f"{r['order_id']}: {r['order_type'].lower()}", f"{r['order_id'].replace(' ', '_')}.pdf"
            if r["authority"].startswith("Port of Corpus Christi"):          # the port's own notice goes out from the operations mailbox
                emit(t, "internal", "port.operations@" + dom, dom, W.staff_box(g), sj, att, g.integers(60000, 240000))
            else:
                emit(t, "inbound", "notices@uscg-sector-cc.example", "uscg-sector-cc.example", "port.operations@" + dom, sj, att, g.integers(60000, 240000))
    out.sort(key=lambda x: x[0])
    return out
