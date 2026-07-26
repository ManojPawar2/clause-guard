"""Run every planted scenario through the full pipeline to warm the LLM disk
cache (and as an end-to-end smoke test). The demo video is recorded only after
this reports all scenarios green.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "detect"))
from pipeline import review_draft  # noqa: E402


def main():
    drafts = sorted((ROOT / "data" / "planted").glob("*.txt"))
    if not drafts:
        print("no planted drafts in data/planted/")
        return
    for p in drafts:
        t0 = time.time()
        print(f"=== {p.stem}")
        out = review_draft(p.read_text(encoding="utf-8"),
                           progress=lambda m: print("   ", m, flush=True))
        print(f"    clauses={out['n_clauses']} pairs={out['n_pairs']} "
              f"conflicts={len(out['conflicts'])} ({time.time()-t0:.0f}s)")
        for c in out["conflicts"]:
            print(f"    CONFLICT vs {c['meta'].get('gr_code','?')}: {c['reason'][:100]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
