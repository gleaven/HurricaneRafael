// Neo4j import: copy nodes.csv and edges.csv from internal/ or public/ into Neo4j's import folder.
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
