"""Build the knowledge graph in two views:
  04_knowledge_graph/internal/  everything, including ground truth (events, threads, entities, hidden characters)
  04_knowledge_graph/public/    only what a member of the public could know (no EVT/thread/entity/hidden nodes)
Each view has graph.json (node-link), nodes.csv, edges.csv, graph.graphml.  Neo4j: see neo4j_import.cypher.
Usage: python scripts/build_graph.py   (run link_stories.py first)"""
import sys, os, csv, json
from xml.sax.saxutils import escape
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import context, load_all_stories, load, path, public_exclusions
import graph_entities

INTERNAL_TYPES = {"Event", "Thread", "Entity"} | graph_entities.INTERNAL_NODE_TYPES
INTERNAL_PLACES = public_exclusions()[0]
PUBLIC_PROPS = {"Place": ["kind"], "Character": ["kind", "role", "org"], "Story": ["day", "time_local", "outlet", "section", "story_type", "dek", "topics"],
                "PublicFact": ["day", "statement"], "Arc": ["description"], "Outlet": ["kind", "url"]}
PUBLIC_PROPS.update(graph_entities.PUBLIC_PROPS)

def build():
    ctx = context()
    stories = load_all_stories()
    idx = load("03_news/story_index.json")["stories"]
    threads = load("00_scenario/threads.json")
    nodes, edges = {}, []
    def node(nid, ntype, label, internal=False, **props):
        nodes[nid] = {"id": nid, "type": ntype, "label": label, "internal": internal, **props}
    def edge(src, rel, dst, internal=False, **props):
        if src in nodes and dst in nodes:
            edges.append({"source": src, "rel": rel, "target": dst, "internal": internal, **props})
    for o in ctx["outlets"].values():
        node(o["outlet_id"], "Outlet", o["name"], kind=o["type"], url=o["site_url"])
    for p in ctx["places"].values():
        node(p["place_id"], "Place", p["name"], internal=p["place_id"] in INTERNAL_PLACES, kind=p["type"], role=p["role"])
    for a in ctx["arcs"].values():
        node(a["arc_id"], "Arc", a["name"], description=a["description"])
    for t in threads:
        node(t["thread_id"], "Thread", t["name"], internal=True, truth=t["truth"])
    for e in ctx["entities"].values():
        node(e["id"], "Entity", e["name"], internal=True, keys=e["type_and_keys"], role=e["role"])
    for e in ctx["msel"].values():
        node(e["event_id"], "Event", e["description"][:80], internal=True, day=e["day"], description=e["description"])
    for f in ctx["facts"].values():
        node(f["id"], "PublicFact", f["statement"][:80], day=f["day"], statement=f["statement"])
    for c in ctx["characters"].values():
        node(c["id"], "Character", c["name"], internal=not c["public_facing"], kind=c["kind"], role=c["role"],
             org=c["affiliation"].get("org"), appearances=len(c.get("context_log", [])))
    for s in stories:
        node(s["story_id"], "Story", s["headline"], day=s["day"], time_local=s["time_local"],
             outlet=s["outlet_id"], section=s["section"], story_type=s["tags"].get("story_type"),
             dek=s["dek"], topics=s["tags"].get("topics", []))
    for name in {"FAC-HOS-xx", "WW-xx"}:
        node(name, "Place", name, kind="placeholder")
    # character edges
    for c in ctx["characters"].values():
        org = c["affiliation"].get("org_id")
        if org:
            edge(c["id"], "AFFILIATED_WITH", org, internal=not c["public_facing"])
        for p in c["home_place_ids"]:
            edge(c["id"], "BASED_AT", p)
        for a in c["arcs"]:
            edge(c["id"], "APPEARS_IN_ARC", a)
        for r in c["relationships"]:
            hidden = "hidden" in r["relation"].lower()
            edge(c["id"], "RELATES_TO", r["with"], internal=hidden or not c["public_facing"], relation=r["relation"])
    # facts, events, threads
    for f in ctx["facts"].values():
        for a in f["arcs"]:
            edge(f["id"], "IN_ARC", a)
        for s in f["sources"]:
            edge(f["id"], "SOURCED_FROM", s)
        for p in f["places"]:
            edge(f["id"], "ABOUT_PLACE", p)
        for e in f["events"]:
            edge(f["id"], "REVEALS_EVENT", e, internal=True)
    for e in ctx["msel"].values():
        for t in e["threads"]:
            edge(e["event_id"], "PART_OF_THREAD", t, internal=True)
        for p in e["place_ids"]:
            edge(e["event_id"], "AT_PLACE", p, internal=True)
    for a in ctx["arcs"].values():
        for t in a["threads"]:
            edge(a["arc_id"], "SURFACES_THREAD", t, internal=True)
    # story edges
    for s in stories:
        sid, t = s["story_id"], s["tags"]
        edge(sid, "PUBLISHED_BY", s["outlet_id"])
        for b in s["byline"]:
            edge(sid, "WRITTEN_BY", b)
        for c in t.get("characters_quoted", []):
            edge(sid, "QUOTES", c)
        for c in t.get("characters_mentioned", []):
            edge(sid, "MENTIONS", c)
        for a in t.get("arcs", []):
            edge(sid, "IN_ARC", a)
        for f in t.get("public_facts", []):
            edge(sid, "CITES_FACT", f)
        for p in t.get("places", []):
            edge(sid, "ABOUT_PLACE", p)
        for e in s.get("internal", {}).get("truth_events", []):
            edge(sid, "DEPICTS_EVENT", e, internal=True)
        if t.get("follows_up"):
            edge(sid, "FOLLOWS_UP", t["follows_up"])
        info = idx.get(sid, {})
        for arc, nxt in info.get("next_in_arc", {}).items():
            edge(sid, "NEXT_IN_ARC", nxt, arc=arc)
        for r in info.get("related", []):
            if r["story_id"] > sid:
                edge(sid, "RELATED_TO", r["story_id"], score=r["score"])
    # registries, data streams, observations and answer keys (scripts/graph_entities.py)
    graph_entities.extend(nodes, edges, node, edge, ctx, stories)
    # drop placeholder nodes that nothing points to
    deg = {}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1; deg[e["target"]] = deg.get(e["target"], 0) + 1
    for nid in [n for n in nodes if not deg.get(n) and nodes[n].get("kind") == "placeholder"]:
        del nodes[nid]
    return nodes, edges

def write_view(nodes, edges, view):
    out = path("04_knowledge_graph", view)
    os.makedirs(out, exist_ok=True)
    if view == "public":
        nodes = {k: v for k, v in nodes.items() if not v["internal"] and v["type"] not in INTERNAL_TYPES}
        edges = [e for e in edges if not e["internal"] and e["source"] in nodes and e["target"] in nodes]
        nodes = {k: {**{kk: v[kk] for kk in ("id", "type", "label", "internal")},
                     **{p: v[p] for p in PUBLIC_PROPS.get(v["type"], []) if p in v}} for k, v in nodes.items()}
    with open(os.path.join(out, "graph.json"), "w", encoding="utf-8") as f:
        json.dump({"directed": True, "view": view, "nodes": list(nodes.values()), "links": edges}, f, ensure_ascii=False, indent=1)
    nkeys = ["id", "type", "label", "internal", "day"]
    with open(os.path.join(out, "nodes.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(nkeys + ["props_json"])
        for n in nodes.values():
            w.writerow([n.get(k, "") for k in nkeys] + [json.dumps({k: v for k, v in n.items() if k not in nkeys}, ensure_ascii=False)])
    with open(os.path.join(out, "edges.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["source", "rel", "target", "props_json"])
        for e in edges:
            w.writerow([e["source"], e["rel"], e["target"], json.dumps({k: v for k, v in e.items() if k not in ("source", "rel", "target")}, ensure_ascii=False)])
    with open(os.path.join(out, "graph.graphml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n')
        f.write('<key id="type" for="node" attr.name="type" attr.type="string"/>\n<key id="label" for="node" attr.name="label" attr.type="string"/>\n')
        f.write('<key id="day" for="node" attr.name="day" attr.type="int"/>\n<key id="rel" for="edge" attr.name="rel" attr.type="string"/>\n')
        f.write('<graph edgedefault="directed">\n')
        for n in nodes.values():
            day = f'<data key="day">{n["day"]}</data>' if isinstance(n.get("day"), int) else ""
            f.write(f'<node id="{escape(n["id"])}"><data key="type">{n["type"]}</data><data key="label">{escape(str(n["label"]))}</data>{day}</node>\n')
        for i, e in enumerate(edges):
            f.write(f'<edge id="e{i}" source="{escape(e["source"])}" target="{escape(e["target"])}"><data key="rel">{e["rel"]}</data></edge>\n')
        f.write("</graph>\n</graphml>\n")
    counts = {}
    for n in nodes.values():
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    deg, rels = {}, {}
    for e in edges:
        deg[e["source"]] = deg.get(e["source"], 0) + 1; deg[e["target"]] = deg.get(e["target"], 0) + 1
        rels[e["rel"]] = rels.get(e["rel"], 0) + 1
    orphans = [n["id"] for n in nodes.values() if not deg.get(n["id"])]
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"view": view, "nodes": len(nodes), "edges": len(edges), "nodes_by_type": counts, "edges_by_type": dict(sorted(rels.items(), key=lambda x: -x[1])),
                   "orphans": orphans}, f, indent=1)
    print(f"  {view}: orphans {len(orphans)} {orphans[:8]}")
    return len(nodes), len(edges), counts

CYPHER = """// Neo4j import: copy nodes.csv and edges.csv from internal/ or public/ into Neo4j's import folder.
LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row
CALL apoc.create.node([row.type], apoc.map.merge({id: row.id, label: row.label, internal: row.internal = 'True'},
     apoc.convert.fromJsonMap(row.props_json))) YIELD node RETURN count(node);
CREATE INDEX node_id IF NOT EXISTS FOR (n:Story) ON (n.id);
LOAD CSV WITH HEADERS FROM 'file:///edges.csv' AS row
MATCH (a {id: row.source}), (b {id: row.target})
CALL apoc.create.relationship(a, row.rel, apoc.convert.fromJsonMap(row.props_json), b) YIELD rel RETURN count(rel);
// Node labels: Story, PublicFact, Character, Outlet, Place, Arc, Organization, Vessel, Aircraft, Facility, Asset, Equipment, Host,
//   UserAccount, ScadaTagGroup, Sensor, SocialAccount, ResponseUnit, Station, Area, Terminal, Berth, DataStream, Registry;
//   internal view also: Event, Thread, Entity, Observation, AnswerKeyPath, OldId.
// Example: everything the graph knows about one vessel
// MATCH (v:Vessel {id:'VSL-0041'})-[r]-(x) RETURN type(r), labels(x), x.label LIMIT 50;
// Example (internal): the answer key for a thread, step by step
// MATCH (k:AnswerKeyPath)-[:SOLVES]->(:Thread {id:'T8'}), (k)-[s:HAS_STEP]->(o:Observation)-[:EVIDENCED_BY]->(d:DataStream) RETURN s.n, d.id, o.what ORDER BY s.n;
// Example: a character's storyline in order
// MATCH (s:Story)-[:QUOTES]->(c:Character {id:'CHR-040'}) RETURN s.day, s.label ORDER BY s.day;
"""

def main():
    nodes, edges = build()
    for view in ("internal", "public"):
        n, e, counts = write_view(dict(nodes), list(edges), view)
        print(f"{view}: {n} nodes, {e} edges, {counts}")
    with open(path("04_knowledge_graph", "neo4j_import.cypher"), "w", encoding="utf-8") as f:
        f.write(CYPHER)

if __name__ == "__main__":
    main()
