"""KNCB 1480 AM Coastal Bend Radio: Spanish-language AM station. Spanish first, English second.
Radio red and gold on warm white; Nunito Sans throughout."""
import datetime as dt

from nr import common as C
from nr.common import esc

FONTS = "https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700;800&display=swap"

CSS = """
:root{--red:#c0392b;--red-d:#922b21;--red-l:#e74c3c;--gold:#f39c12;--gold-l:#f8c94a;--bg:#fff9f0;--white:#fff;
--text:#1a1a1a;--muted:#6f7a7b;--border:#f0d4a0;--green:#27ae60;--green-d:#1e8449;--amber:#b9770e;--shadow:0 2px 8px rgba(0,0,0,.08)}
body{margin:0;font-family:'Nunito Sans',system-ui,-apple-system,'Segoe UI',sans-serif;background:var(--bg);color:var(--text);font-size:16px;line-height:1.6}
a{color:var(--red);text-decoration:none}a:hover{color:var(--red-d);text-decoration:underline}
p{margin:0 0 12px}h1,h2,h3,h4{margin:0}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.en{display:block;font-weight:400;opacity:.85;font-size:.86em}
.banner{color:#fff;padding-block:10px;font-weight:700;font-size:.92rem;line-height:1.45}
.banner .in{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:8px}
.banner.ok{background:var(--green);text-align:center}
.banner.red{background:var(--red-d)}
.banner.amber{background:var(--amber)}
.alert-row{display:flex;gap:10px;align-items:flex-start}
.alert-tag{background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.35);font-size:.68rem;font-weight:800;letter-spacing:.08em;padding:2px 7px;border-radius:3px;white-space:nowrap;margin-top:2px}
.alert-row .en{font-size:.8rem}
.hdr{background:var(--red);position:relative;overflow:hidden}
.hdr::before,.hdr::after{content:'';position:absolute;border-radius:50%;border:2px solid rgba(255,255,255,.09)}
.hdr::before{width:300px;height:300px;right:-60px;top:-110px}.hdr::after{width:200px;height:200px;right:20px;top:-55px}
.hdr .in{max-width:1100px;margin:0 auto;min-height:96px;display:flex;align-items:center;justify-content:space-between;gap:18px;position:relative;z-index:1;padding-block:12px}
.brand{min-width:0}
.brand a{color:#fff;text-decoration:none}
.call{font-size:2.6rem;font-weight:800;line-height:1;letter-spacing:.01em}
.call small{font-size:1.1rem;font-weight:800;color:var(--gold-l);margin-left:6px}
.stn{font-size:.95rem;color:rgba(255,255,255,.9);font-weight:700;letter-spacing:.06em}
.since{font-size:.74rem;color:rgba(255,255,255,.75);font-style:italic}
.hdr-right{text-align:right;color:#fff;display:flex;flex-direction:column;align-items:flex-end;gap:6px}
.hdr-date{font-size:.82rem;font-weight:700}
.hdr-date .en{font-size:.74rem}
.wave{display:flex;align-items:center;gap:5px;height:30px}
.wave span{display:inline-block;width:4px;border-radius:2px;background:rgba(255,255,255,.4);animation:wb 1.2s ease-in-out infinite}
.wave span:nth-child(1){height:12px}.wave span:nth-child(2){height:22px;animation-delay:.15s}.wave span:nth-child(3){height:30px;animation-delay:.3s}
.wave span:nth-child(4){height:22px;animation-delay:.45s}.wave span:nth-child(5){height:14px;animation-delay:.6s}.wave span:nth-child(6){height:26px;animation-delay:.75s}
.wave.off span{animation:none;opacity:.35;height:4px}
@keyframes wb{0%,100%{transform:scaleY(.5);opacity:.5}50%{transform:scaleY(1);opacity:1}}
nav.nv{background:var(--red-d);border-bottom:3px solid var(--gold)}
nav.nv .in{max-width:1100px;margin:0 auto;display:flex;flex-wrap:wrap}
nav.nv a{display:block;color:rgba(255,255,255,.88);font-size:.84rem;font-weight:800;padding:9px 13px;text-decoration:none;line-height:1.2}
nav.nv a .en{font-size:.68rem;opacity:.7;font-weight:400}
nav.nv a:hover,nav.nv a.on{background:rgba(0,0,0,.18);color:var(--gold-l)}
.live{max-width:1100px;margin:20px auto 0;box-sizing:border-box}
.live-in{background:var(--white);border:2px solid var(--border);border-left:5px solid var(--red);padding:18px 22px;display:flex;align-items:center;gap:20px;box-shadow:var(--shadow)}
.play{width:64px;height:64px;background:var(--red);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;animation:pp 2s infinite}
.play::after{content:'';border-left:22px solid #fff;border-top:13px solid transparent;border-bottom:13px solid transparent;margin-left:5px}
.play.off{background:#9aa3a4;animation:none}
@keyframes pp{0%{box-shadow:0 0 0 0 rgba(192,57,43,.5)}70%{box-shadow:0 0 0 16px rgba(192,57,43,0)}100%{box-shadow:0 0 0 0 rgba(192,57,43,0)}}
.live-info{min-width:0}
.live-info h3{font-size:1.1rem;font-weight:800;color:var(--red);margin-bottom:2px}
.live-info h3 .en{display:inline;font-size:.8rem;color:var(--muted);font-weight:600}
.badge{display:inline-block;background:var(--red);color:#fff;font-size:.7rem;font-weight:800;padding:3px 8px;border-radius:3px;letter-spacing:.06em;animation:bl 1.5s step-end infinite;margin-right:8px;vertical-align:middle}
.badge.off{background:#5d6566;animation:none}
@keyframes bl{0%,100%{opacity:1}50%{opacity:.45}}
.prog{font-size:.86rem;margin-top:4px}
.prog strong{color:var(--text)}
.note{font-size:.8rem;color:var(--muted);margin-top:4px}
.main{max-width:1100px;margin:0 auto;padding-block:22px 28px;display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:24px;box-sizing:border-box}
.col{min-width:0}
.h-sec{font-size:1.05rem;font-weight:800;color:var(--red);border-bottom:3px solid var(--gold);padding-bottom:6px;margin:6px 0 14px}
.h-sec .en{display:inline;font-size:.8rem;color:var(--muted);font-weight:600;margin-left:6px}
.feat{background:var(--white);border:1px solid var(--border);border-top:5px solid var(--red);padding:22px;box-shadow:var(--shadow);margin-bottom:24px}
.kicker{display:inline-block;background:var(--gold);color:#3a2500;font-size:.7rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:3px 9px;border-radius:3px;margin-bottom:10px}
.kicker.red{background:var(--red);color:#fff}
.kicker a{color:inherit}
.feat h2{font-size:1.6rem;line-height:1.2;font-weight:800;color:var(--text);text-wrap:balance}
.feat h2 a{color:inherit}
.hl-en{font-size:1rem;color:var(--muted);font-weight:600;margin-top:6px;line-height:1.35}
.dek{font-size:1rem;color:#333;margin:12px 0}
.meta{font-size:.78rem;color:var(--muted)}
.meta .sec{font-weight:800;color:var(--red);text-transform:uppercase;letter-spacing:.04em;font-size:.7rem}
.more{font-weight:800;font-size:.85rem}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.card{background:var(--white);border:1px solid var(--border);border-radius:6px;padding:16px;box-shadow:var(--shadow);min-width:0}
.card h3{font-size:1.02rem;font-weight:800;line-height:1.3}
.card h3 a{color:var(--text)}
.card .hl-en{font-size:.84rem;margin-top:4px}
.card p{font-size:.86rem;color:#444;margin:8px 0}
.side{display:flex;flex-direction:column;gap:18px;min-width:0}
.box{background:var(--white);border:1px solid var(--border);border-radius:6px;padding:16px;box-shadow:var(--shadow)}
.box h4{font-size:.92rem;font-weight:800;color:var(--red);margin-bottom:10px}
.box h4 .en{display:inline;font-size:.75rem;color:var(--muted);font-weight:600;margin-left:4px}
.box.green{border-left:5px solid var(--green)}
.box.green h4{color:var(--green-d)}
.box ul{list-style:none;margin:0;padding:0}
.box li{padding:8px 0;border-bottom:1px dashed var(--border);font-size:.86rem;line-height:1.4}
.box li:last-child{border-bottom:0}
.alert-item{padding:8px 0;border-bottom:1px dashed var(--border);font-size:.86rem}
.alert-item:last-child{border-bottom:0}
.alert-item .lvl{font-size:.66rem;font-weight:800;letter-spacing:.08em;color:#fff;background:var(--red);padding:1px 6px;border-radius:3px}
.alert-item .lvl.amber{background:var(--amber)}
.secs a{display:flex;justify-content:space-between;gap:8px;padding:7px 0;border-bottom:1px dashed var(--border);color:var(--text);font-weight:700;font-size:.88rem}
.secs a .en{display:inline;font-size:.74rem;color:var(--muted);font-weight:400;margin-left:4px}
.secs a .n{color:var(--red);font-weight:800}
.listen p{font-size:.86rem;margin-bottom:6px}
.story{background:var(--white);border:1px solid var(--border);border-top:5px solid var(--red);padding:26px;box-shadow:var(--shadow)}
.story h1{font-size:1.9rem;line-height:1.18;font-weight:800;text-wrap:balance}
.story .hl-en{font-size:1.1rem}
.story .body p{font-size:1.02rem;line-height:1.72;margin-bottom:14px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 4px;align-items:center}
.tags .lbl{font-size:.74rem;font-weight:800;color:var(--muted)}
.tag{background:#fdebd0;color:#7a4a00;font-size:.74rem;font-weight:700;padding:3px 9px;border-radius:999px}
.pager{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:18px;border-top:2px solid var(--border);padding-top:12px;font-size:.88rem}
.pager a{max-width:48%;color:var(--text);font-weight:700}
.pager small{display:block;font-size:.7rem;font-weight:800;color:var(--red);letter-spacing:.04em}
.list{list-style:none;margin:0;padding:0}
.list li{background:var(--white);border:1px solid var(--border);border-left:4px solid var(--red);border-radius:4px;padding:12px 14px;margin-bottom:10px}
.list li h3{font-size:1rem;font-weight:800;line-height:1.3}
.list li h3 a{color:var(--text)}
.list li .hl-en{font-size:.82rem;margin-top:2px}
.list li p{font-size:.85rem;color:#444;margin:6px 0 0}
.search{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.search input{flex:1;min-width:0;padding:10px 12px;border:2px solid var(--border);border-radius:6px;font:inherit;background:#fff}
.search button{background:var(--red);color:#fff;border:0;border-radius:6px;padding:10px 16px;font:800 .86rem 'Nunito Sans',sans-serif;cursor:pointer}
.filter{font-size:.86rem;color:var(--muted);margin-bottom:12px}
.filter a{font-weight:800;margin-left:8px}
.dayhead{font-size:.95rem;font-weight:800;color:var(--red-d);margin:18px 0 8px;text-transform:capitalize}
.days{display:flex;flex-wrap:wrap;gap:6px}
.days a{font-size:.76rem;font-weight:700;background:#fdebd0;color:#7a4a00;padding:3px 8px;border-radius:999px}
.days a.on{background:var(--red);color:#fff}
.empty{background:var(--white);border:2px dashed var(--border);border-radius:8px;padding:26px;text-align:center;color:var(--muted)}
.empty strong{display:block;color:var(--text);font-size:1.05rem;margin-bottom:4px}
footer{background:var(--red);color:rgba(255,255,255,.88);padding-block:20px;text-align:center;font-size:.82rem;line-height:1.8}
footer a{color:var(--gold-l)}
@media (max-width:880px){.main{grid-template-columns:minmax(0,1fr)}}
@media (max-width:600px){.cards{grid-template-columns:minmax(0,1fr)}.call{font-size:2rem}.hdr-right{display:none}
.live-in{padding:14px;gap:14px}.play{width:52px;height:52px}.feat,.story{padding:18px}.feat h2{font-size:1.32rem}.story h1{font-size:1.45rem}
nav.nv a{padding:8px 9px;font-size:.8rem}.pager a{max-width:100%}}
"""

GLOSS = {"Emergencias": "Emergencies", "Local": "Local", "Comunidad": "Community", "Salud": "Health"}
LEVEL_ES = {"emergency": ("EMERGENCIA", "red"), "warning": ("ADVERTENCIA", "red"),
            "watch": ("VIGILANCIA", "amber"), "advisory": ("AVISO", "amber")}
ES_SHORT_MONTHS = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sept.", "oct.", "nov.", "dic."]


def split_hl(h):
    if " / " in h:
        es_, en_ = h.split(" / ", 1)
        return es_.strip(), en_.strip()
    return h, ""


def program(ctx):
    h = C.local(ctx["now"]).hour
    if 5 <= h < 10: return "Despierta Coastal Bend"
    if 10 <= h < 14: return "Noticias al Mediodía"
    if 14 <= h < 19: return "La Tarde con KNCB"
    if 19 <= h < 24: return "Noche Informativa"
    return "Madrugada KNCB"


def headline_block(a, tag="h3", link=True):
    es_, en_ = split_hl(a["headline"])
    t = f'<a href="{a["url"]}">{esc(es_)}</a>' if link else esc(es_)
    en = f'<div class="hl-en" lang="en">{esc(en_)}</div>' if en_ else ""
    return f"<{tag}>{t}</{tag}>{en}"


def meta(ctx, a, section=True):
    sec = f'<span class="sec">{esc(a["section"])}</span> · ' if section else ""
    by = f'Por {esc(C.byline(a, " y "))} · ' if a["authors"] else ""
    return f'<div class="meta">{sec}{by}{C.ago_span(ctx, a)}</div>'


def frame(ctx, title, inner, active=""):
    o = ctx["outlet"]
    st = ctx["status"]
    alerts = st["alerts"]
    if alerts:
        worst = "red" if any(a["level"] in ("emergency", "warning") for a in alerts) else "amber"
        rows = "".join(
            f'<div class="alert-row"><span class="alert-tag">{LEVEL_ES.get(a["level"], ("AVISO", "amber"))[0]}</span>'
            f'<span>{esc(a["text"])}<span class="en" lang="en">{esc(a["text_en"])}</span></span></div>' for a in alerts)
        banner = f'<div class="banner {worst} gut" role="alert"><div class="in">{rows}</div></div>'
    else:
        banner = ('<div class="banner ok gut"><div class="in">Sin alertas activas en este momento'
                  '<span class="en" lang="en">No active alerts right now</span></div></div>')

    off = (st.get("broadcast") or {}).get("status") == "off-air"
    nav = [f'<a href="{C.url_home(ctx)}"{" class=on" if active == "home" else ""}>Inicio<span class="en">Home</span></a>']
    for s in o["sections"]:
        on = ' class="on"' if active == s["slug"] else ""
        nav.append(f'<a href="{C.url_section(ctx, s["slug"])}"{on}>{esc(s["name"])}<span class="en">{esc(GLOSS.get(s["name"], s["name"]))}</span></a>')
    nav.append(f'<a href="{C.url_archive(ctx)}"{" class=on" if active == "archive" else ""}>Archivo<span class="en">Archive</span></a>')

    return (C.head(ctx, title, FONTS, CSS) +
            '<div id="nr-root">' + banner +
            '<header class="hdr gut"><div class="in"><div class="brand">'
            f'<a href="{C.url_home(ctx)}"><div class="call">KNCB<small>1480 AM</small></div>'
            '<div class="stn">COASTAL BEND RADIO</div></a>'
            '<div class="since">La voz de la comunidad · The community\'s voice</div></div>'
            f'<div class="hdr-right"><div class="wave{" off" if off else ""}" aria-hidden="true">' + "<span></span>" * 6 + '</div>'
            f'<div class="hdr-date">{C.clock_span(ctx, "date-es")} · {C.clock_span(ctx, "time-es")}'
            f'<span class="en" lang="en">{C.clock_span(ctx, "date-long")}</span></div></div>'
            '</div></header>'
            f'<nav class="nv gut" aria-label="Secciones"><div class="in">{"".join(nav)}</div></nav>'
            f'{inner}'
            '<footer class="gut">KNCB 1480 AM · Coastal Bend Radio · Corpus Christi, Texas<br>'
            'Noticias en español para el Coastal Bend · Spanish-language news for the Coastal Bend<br>'
            f'<a href="{C.url_rss(ctx)}">RSS</a> · Todo el contenido es ficticio · All content is fictional</footer>'
            '</div>' + C.foot(ctx))


def live_box(ctx):
    bc = ctx["status"].get("broadcast") or {}
    if bc.get("status") == "off-air":
        return ('<div class="live gut"><div class="live-in"><div class="play off" aria-hidden="true"></div><div class="live-info">'
                '<h3><span class="badge off">FUERA DEL AIRE</span>Señal interrumpida <span class="en">Off the air</span></h3>'
                f'<div class="note">{esc(bc.get("note", ""))}</div>'
                '<div class="note" lang="en">Our transmitter is down. Web updates continue here.</div></div></div></div>')
    return ('<div class="live gut"><div class="live-in"><div class="play" role="img" aria-label="Escuchar en vivo"></div><div class="live-info">'
            '<h3><span class="badge">EN VIVO</span>Escúchanos en vivo <span class="en">Listen live</span></h3>'
            f'<div class="prog">Ahora: <strong>{esc(program(ctx))}</strong> · {C.clock_span(ctx, "time-es")}</div>'
            '<div class="note">KNCB 1480 AM · Corpus Christi, TX · <span lang="en">On the air in Spanish and English</span></div>'
            '</div></div></div>')


def sidebar(ctx, extra=""):
    o = ctx["outlet"]
    alerts = ctx["status"]["alerts"]
    if alerts:
        items = "".join(
            f'<div class="alert-item"><span class="lvl {LEVEL_ES.get(a["level"], ("", "amber"))[1]}">{LEVEL_ES.get(a["level"], ("AVISO", ""))[0]}</span> '
            f'{esc(a["text"])}<div class="meta">Desde {esc(C.fmt_date_es(a["since"]).split(", ", 1)[1])}, {esc(C.fmt_time_es(a["since"]))}</div></div>'
            for a in alerts)
        alert_box = f'<div class="box"><h4>Alertas activas<span class="en">Active alerts</span></h4>{items}</div>'
    else:
        alert_box = ('<div class="box green"><h4>Alertas<span class="en">Alerts</span></h4>'
                     '<p style="margin:0;font-size:.88rem">No hay alertas activas. Le avisaremos aquí y al aire.'
                     '<span class="en" lang="en">No active alerts. We will post them here and on the air.</span></p></div>')
    counts = {}
    for a in ctx["articles"]:
        counts[a["section"]] = counts.get(a["section"], 0) + 1
    secs = "".join(f'<a href="{C.url_section(ctx, s["slug"])}"><span>{esc(s["name"])}<span class="en">{esc(GLOSS.get(s["name"], ""))}</span></span>'
                   f'<span class="n">{counts.get(s["name"], 0)}</span></a>' for s in o["sections"])
    secs += f'<a href="{C.url_archive(ctx)}"><span>Buscar en el archivo<span class="en">Search the archive</span></span><span class="n">→</span></a>'
    return (f'<aside class="side">{alert_box}{extra}'
            f'<div class="box secs"><h4>Secciones<span class="en">Sections</span></h4>{secs}</div>'
            '<div class="box green listen"><h4>Cómo escucharnos<span class="en">How to listen</span></h4>'
            '<p>Sintonice 1480 AM en cualquier radio. Un radio de baterías o de manivela funciona aunque se vaya la luz.</p>'
            '<p class="en" lang="en" style="font-size:.8rem">Tune to 1480 AM on any radio. A battery or hand-crank radio works even when the power is out.</p></div>'
            '</aside>')


def card(ctx, a):
    return (f'<div class="card" data-article-id="{a["pid"]}">{headline_block(a)}'
            f'<p>{esc(C.excerpt(a, 26))}</p>{meta(ctx, a)}</div>')


def list_item(ctx, a):
    return (f'<li data-article-id="{a["pid"]}">{headline_block(a)}{meta(ctx, a)}'
            f'<p>{esc(C.excerpt(a, 30))}</p></li>')


def render(view, ctx, **kw):
    o = ctx["outlet"]
    name = "KNCB 1480 AM Coastal Bend Radio"

    if view == "home":
        arts = ctx["articles"]
        if not arts:
            body = ('<div class="empty"><strong>Todavía no hay noticias publicadas.</strong>'
                    'Escuche 1480 AM para la información más reciente.<span class="en" lang="en">No stories published yet. '
                    'Tune to 1480 AM for the latest.</span></div>')
            inner = live_box(ctx) + f'<div class="main gut"><div class="col">{body}</div>{sidebar(ctx)}</div>'
            return frame(ctx, f"{name} | Inicio", inner, "home")
        urgent = [a for a in C.recent(ctx, 24) if C.is_breaking(a) or a["section"] == "Emergencias"]
        lead = urgent[0] if urgent else arts[0]
        rest = [a for a in arts if a["pid"] != lead["pid"]][:10]
        kick_cls = "red" if lead in urgent else ""
        sec = next((s for s in o["sections"] if s["name"] == lead["section"]), None)
        kick = (f'<a href="{C.url_section(ctx, sec["slug"])}">{esc(lead["section"])}</a>' if sec else esc(lead["section"]))
        if kick_cls:
            kick = "Última hora · " + kick
        paras = "".join(f"<p>{esc(p)}</p>" for p in lead["body"][:2])
        by = f'Por {esc(C.byline(lead, " y "))} · ' if lead["authors"] else ""
        feat = (f'<article class="feat" data-article-id="{lead["pid"]}"><span class="kicker {kick_cls}">{kick}</span>'
                f'{headline_block(lead, "h2")}<p class="dek">{esc(lead["summary"])}</p>'
                f'<div class="meta" style="margin-bottom:12px">{by}{esc(C.pub_label(lead, "es"))}</div>{paras}'
                f'<a class="more" href="{lead["url"]}">Leer más · <span lang="en">Read more</span> →</a></article>')
        more = ""
        if rest:
            more = ('<h2 class="h-sec">Últimas noticias<span class="en">Latest news</span></h2><div class="cards">'
                    + "".join(card(ctx, a) for a in rest) + '</div>')
        inner = live_box(ctx) + f'<div class="main gut"><div class="col">{feat}{more}</div>{sidebar(ctx)}</div>'
        return frame(ctx, f"{name} | Inicio", inner, "home")

    if view == "section":
        sec, items = kw["section"], kw["items"]
        gl = GLOSS.get(sec["name"], "")
        body = ("<ul class='list'>" + "".join(list_item(ctx, a) for a in items) + "</ul>") if items else \
            ('<div class="empty"><strong>Aún no hay noticias en esta sección.</strong>'
             '<span class="en" lang="en">No stories in this section yet.</span></div>')
        inner = (f'<div class="main gut"><div class="col"><h2 class="h-sec">{esc(sec["name"])}<span class="en">{esc(gl)}</span></h2>'
                 f'{body}</div>{sidebar(ctx)}</div>')
        return frame(ctx, f'{sec["name"]} | {name}', inner, sec["slug"])

    if view == "article":
        a = kw["article"]
        sec = next((s for s in o["sections"] if s["name"] == a["section"]), None)
        kick = f'<a href="{C.url_section(ctx, sec["slug"])}">{esc(a["section"])}</a>' if sec else esc(a["section"])
        tags = "".join(f'<span class="tag">{esc(s)}</span>' for s in a["storylines"])
        tags = f'<div class="tags"><span class="lbl">Temas · Topics:</span>{tags}</div>' if tags else ""
        by = f'Por {esc(C.byline(a, " y "))} · ' if a["authors"] else ""
        nw, ol = kw.get("newer"), kw.get("older")
        pager = ""
        if nw or ol:
            left = (f'<a href="{ol["url"]}" data-article-id="{ol["pid"]}" data-nr-nobadge><small>← Anterior · Older</small>'
                    f'{esc(split_hl(ol["headline"])[0])}</a>') if ol else "<span></span>"
            right = (f'<a href="{nw["url"]}" data-article-id="{nw["pid"]}" data-nr-nobadge style="text-align:right">'
                     f'<small>Más reciente · Newer →</small>{esc(split_hl(nw["headline"])[0])}</a>') if nw else "<span></span>"
            pager = f'<nav class="pager" aria-label="Más noticias">{left}{right}</nav>'
        rel = kw.get("related") or []
        rel_box = ""
        if rel:
            items = "".join(f'<li data-article-id="{r["pid"]}"><a href="{r["url"]}">{esc(split_hl(r["headline"])[0])}</a>'
                            f'<div class="meta">{esc(r["outlet_name"])} · {C.ago_span(ctx, r)}</div></li>' for r in rel)
            rel_box = f'<div class="box"><h4>Cobertura relacionada<span class="en">Related coverage</span></h4><ul>{items}</ul></div>'
        story = (f'<article class="story" data-article-id="{a["pid"]}"><span class="kicker">{kick}</span>'
                 f'{headline_block(a, "h1", link=False)}<p class="dek">{esc(a["summary"])}</p>'
                 f'<div class="meta">{by}{esc(C.pub_label(a, "es"))}</div>'
                 f'<div class="body" style="margin-top:16px">{C.paras(a["body"])}</div>{tags}{pager}</article>')
        inner = f'<div class="main gut"><div class="col">{story}</div>{sidebar(ctx, rel_box)}</div>'
        return frame(ctx, f'{split_hl(a["headline"])[0]} | KNCB 1480 AM', inner, sec["slug"] if sec else "")

    if view == "archive":
        q, date, results, days = kw.get("q", ""), kw.get("date"), kw.get("results", []), kw.get("days", [])
        form = (f'<form class="search" action="{C.url_archive(ctx)}" role="search">'
                f'<input name="q" value="{esc(q)}" placeholder="Buscar noticias · Search stories" aria-label="Buscar · Search">'
                + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "")
                + '<button type="submit">Buscar</button></form>')
        n = len(results)
        filt = []
        if q:
            filt.append(f'con “{esc(q)}”')
        if date:
            try:
                d = dt.date.fromisoformat(date)
                filt.append(f'del {d.day} de {C.ES_MONTHS[d.month - 1]} de {d.year}')
            except ValueError:
                filt.append(esc(date))
        label = f'{n} {"noticia" if n == 1 else "noticias"}'
        filter_html = (f'<div class="filter">{label} {" ".join(filt)}<a href="{C.url_archive(ctx)}">Borrar · Clear</a></div>'
                       if filt else f'<div class="filter">{label} en el archivo · <span lang="en">{n} in the archive</span></div>')
        groups = C.group_by_day(results)
        if groups:
            body = "".join(f'<h3 class="dayhead">{esc(C.fmt_date_es(items[0]["ts"]))}</h3><ul class="list">'
                           + "".join(list_item(ctx, a) for a in items) + "</ul>" for _, items in groups)
        else:
            body = ('<div class="empty"><strong>No encontramos noticias.</strong>Pruebe otra palabra o borre el filtro.'
                    '<span class="en" lang="en">No stories found. Try another word or clear the filter.</span></div>')
        day_links = "".join(
            f'<a href="{C.url_archive(ctx, date=d)}"{" class=on" if d == date else ""}>'
            f'{int(d[8:10])} {ES_SHORT_MONTHS[int(d[5:7]) - 1]} ({k})</a>' for d, k in days)
        day_box = (f'<div class="box"><h4>Por día<span class="en">By day</span></h4><div class="days">{day_links}</div></div>'
                   if day_links else "")
        inner = (f'<div class="main gut"><div class="col"><h2 class="h-sec">Archivo<span class="en">Archive</span></h2>'
                 f'{form}{filter_html}{body}</div>{sidebar(ctx, day_box)}</div>')
        return frame(ctx, f"Archivo | {name}", inner, "archive")

    inner = ('<div class="main gut"><div class="col"><div class="empty"><strong>Esta página no está disponible.</strong>'
             'Puede que el enlace esté mal o que la noticia ya no esté publicada.'
             '<span class="en" lang="en">This page is not available. The link may be wrong or the story is not published.</span><br>'
             f'<a class="more" href="{C.url_home(ctx)}">Inicio · Home</a> · <a class="more" href="{C.url_archive(ctx)}">Archivo · Archive</a>'
             f'</div></div>{sidebar(ctx)}</div>')
    return frame(ctx, f"Página no encontrada | {name}", inner)
