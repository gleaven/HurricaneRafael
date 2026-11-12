# Answer key

Internal only: never ship this folder with released data.

`answer_key.json` is built by `scripts/build_answer_keys.py`. For each thread T1-T22 it gives:

- `question`: what a team is trying to answer
- `steps`: the chain of observations to join, in time order. Each step names the event and stream, the files, the time window, what to look for, the entity ids involved and how to join to the next step
- `key_joins`: the joins that crack the thread
- `conclusion` and `difficulty`

Every step refers to an expected observation in `00_scenario/canon_timeline.json`, and `scripts/check_answer_keys.py` confirms that each one is present in the delivered files. `paths` keeps the older one-line form of each key. The internal knowledge graph (`04_knowledge_graph/internal`) carries the same structure as `AnswerKeyPath -HAS_STEP-> Observation -EVIDENCED_BY-> DataStream`.
