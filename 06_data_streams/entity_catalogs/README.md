# entity_catalogs (retired)

This folder used to hold second copies of eight registries. The copies had drifted apart from
the files one level up, so they were removed on 2026-11-09.

- The registries now live only in `06_data_streams/` (for example `06_data_streams/vessels.json`).
- The old copies are kept for reference in `_versions/entity_catalogs_20261109/`.
- `06_data_streams/schemas/00_schema_index.json` lists each stream and the registry it joins to.
- `06_data_streams/_internal/` holds internal notes and id migration maps and is never delivered.
