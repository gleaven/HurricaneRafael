"""Re-embed the current knowledge graph (public and internal views) in 04_knowledge_graph/viewer.html
and give every node type a colour. Run after build_graph.py.

    python3 scripts/build_graph_viewer.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KG = os.path.join(ROOT, "04_knowledge_graph")
COLORS = {"Story": "#4ea1ff", "Character": "#f5a623", "Place": "#3ddc97", "Arc": "#b48cff", "Outlet": "#ff6b81", "PublicFact": "#f2d84b", "Event": "#ff8a4c", "Entity": "#59d6e6",
          "Thread": "#e05bd0", "Organization": "#c9a227", "Vessel": "#2bb3c0", "Aircraft": "#8fd3ff", "Facility": "#6fcf97", "Asset": "#d98880", "Equipment": "#b9770e", "Host": "#7f8c8d",
          "UserAccount": "#95a5a6", "ScadaTagGroup": "#566573", "Sensor": "#48c9b0", "SocialAccount": "#f1948a", "ResponseUnit": "#eb984e", "Station": "#dc7633", "Area": "#82e0aa",
          "Terminal": "#5dade2", "Berth": "#85c1e9", "DataStream": "#f7dc6f", "Registry": "#d7dbdd", "Observation": "#ff5e7e", "AnswerKeyPath": "#ffffff", "OldId": "#4d5656"}
KEEP = ("id", "type", "label", "internal", "day", "kind", "outlet", "section", "statement", "description", "what", "question", "conclusion", "difficulty", "mmsi", "icao24", "path")


def slim(view):
    g = json.load(open(os.path.join(KG, view, "graph.json"), encoding="utf-8"))
    nodes = [{k: (v[:400] if isinstance(v, str) else v) for k, v in n.items() if k in KEEP and v is not None} for n in g["nodes"]]
    links = [{"source": e["source"], "target": e["target"], "rel": e["rel"], "internal": e.get("internal", False)} for e in g["links"]]
    return {"nodes": nodes, "links": links}


def main():
    p = os.path.join(KG, "viewer.html")
    lines = open(p, encoding="utf-8").read().split("\n")
    data = {"public": slim("public"), "internal": slim("internal")}
    done = [False, False]
    for i, l in enumerate(lines):
        if l.startswith("const DATA="):
            lines[i] = "const DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";"
            done[0] = True
        elif l.startswith("const COLORS="):
            rest = l[l.index("}") + 1:]
            lines[i] = "const COLORS=" + json.dumps(COLORS) + rest
            done[1] = True
        elif "const COLORS={" in l and not done[1]:
            lines[i] = re.sub(r"const COLORS=\{[^}]*\}", "const COLORS=" + json.dumps(COLORS), l)
            done[1] = True
    assert all(done), f"viewer structure not recognised: {done}"
    open(p, "w", encoding="utf-8").write("\n".join(lines))
    print(f"viewer: public {len(data['public']['nodes'])} nodes / {len(data['public']['links'])} links, internal {len(data['internal']['nodes'])} / {len(data['internal']['links'])}; {os.path.getsize(p) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
