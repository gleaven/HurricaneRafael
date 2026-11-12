"""Run the whole pipeline in order. Usage: python scripts/build_all.py"""
import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
steps = ["build_world_state.py", "check_world_state.py", "build_state_viewer.py", "validate.py", "merge_character_updates.py", "link_stories.py", "build_expected_observations.py", "reconcile_entities.py", "build_answer_keys.py", "build_graph.py", "build_graph_viewer.py", "build_rss.py", "build_release.py", "check_integrity.py", "check_scenarios.py"]
for s in steps:
    print(f"\n=== {s} ===", flush=True)
    r = subprocess.run([sys.executable, os.path.join(here, s)])
    if r.returncode != 0 and s == "validate.py":
        print("validation errors: fix them before release (continuing build for review)")
