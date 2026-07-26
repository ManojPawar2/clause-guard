"""Driver: bulk-download all three target departments with parallel workers.
Run detached; progress goes to stdout (redirect to data/bulk_log.txt).
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from download_wayback import ROOT, load_listing, run  # noqa: E402

PLAN = [("08", 400), ("22", 244), ("21", 356)]

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rows = [r for r in load_listing() if r[1] >= 2019]
    print(f"listing: {len(rows)} usable rows", flush=True)
    for code, cap in PLAN:
        targets = [r for r in rows if r[2] == code][:cap]
        print(f"=== dept {code}: {len(targets)} targets", flush=True)
        run(targets, ROOT / "data" / "raw_pdfs", f"bulk-{code}", workers=4)
    print("ALL DONE", flush=True)
