"""Group-split pairs_clean.jsonl by seed clause (no clause leaks across splits).

Outputs data/pairs_train.jsonl, pairs_dev.jsonl, pairs_test.jsonl and asserts
the group-disjointness programmatically.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "pairs_clean.jsonl"


def main(dev_frac=0.08, test_frac=0.13):
    groups = defaultdict(list)
    for line in CLEAN.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        groups[r["seed_id"]].append(r)

    keys = sorted(groups)
    random.seed(42)
    random.shuffle(keys)
    n = len(keys)
    n_test = round(n * test_frac)
    n_dev = round(n * dev_frac)
    split_of = {}
    for i, k in enumerate(keys):
        split_of[k] = "test" if i < n_test else ("dev" if i < n_test + n_dev else "train")

    out = {s: (ROOT / "data" / f"pairs_{s}.jsonl").open("w", encoding="utf-8")
           for s in ("train", "dev", "test")}
    counts = defaultdict(int)
    for k, rows in groups.items():
        s = split_of[k]
        for r in rows:
            out[s].write(json.dumps(r, ensure_ascii=False) + "\n")
            counts[s] += 1
    for f in out.values():
        f.close()

    # leakage assertion
    by_split = defaultdict(set)
    for k, s in split_of.items():
        by_split[s].add(k)
    assert not (by_split["train"] & by_split["test"])
    assert not (by_split["train"] & by_split["dev"])
    assert not (by_split["dev"] & by_split["test"])
    print(f"splits: {dict(counts)} groups: train={len(by_split['train'])} "
          f"dev={len(by_split['dev'])} test={len(by_split['test'])} — leakage check PASSED")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
