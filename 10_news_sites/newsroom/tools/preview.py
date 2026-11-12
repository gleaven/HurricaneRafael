"""Render outlet pages at fixed scenario times into _preview/ without running the server.

    python tools/preview.py ledger harborline6        (or no args for every outlet)

Writes _preview/<slug>/<moment>-<view>.html. Uses the live templates and the real gating
logic, and never touches the game master's saved clock.
"""
import os, sys, re
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import server
from nr import common as C

MOMENTS = [("d-30", -30, "12:00"), ("d0-landfall", 0, "03:00"), ("d12-night", 12, "22:00"),
           ("d44-blast", 44, "09:00"), ("d119-end", 119, "18:00")]

def main(slugs):
    server.DEV = True
    corpus = server.Corpus()
    clock = server.Clock(corpus, reset=True, persist=False)
    slugs = slugs or [o["slug"] for o in corpus.outlets]
    import build_data
    for slug in slugs:
        out = os.path.join(HERE, "_preview", slug)
        os.makedirs(out, exist_ok=True)
        for name, day, hm in MOMENTS:
            clock.now = build_data.local_to_epoch(day, hm)
            vis = clock.visible_list(slug)
            pages = [("home", f"/{slug}/", {})]
            o = corpus.outlet[slug]
            if o["sections"]:
                pages.append(("section", f"/{slug}/section/{o['sections'][0]['slug']}/", {}))
            if vis:
                pages.append(("article", vis[-1]["url"], {}))
            pages.append(("archive", f"/{slug}/archive/", {"q": ["water"]}))
            pages.append(("notfound", f"/{slug}/no/such/page", {}))
            for view, path, q in pages:
                status, html = server.render_outlet(slug, path, q, clock)
                fn = os.path.join(out, f"{name}-{view}.html")
                open(fn, "w", encoding="utf-8").write(html)
                leaks = re.findall(r"NWS-[MP]\d{3}|\bD[+-]\d+\b", html)
                flag = f"  LEAK {sorted(set(leaks))[:5]}" if leaks else ""
                print(f"{slug:<13} {name:<12} {view:<9} {status}  {len(html)//1024:>3}KB{flag}")

if __name__ == "__main__":
    main(sys.argv[1:])
