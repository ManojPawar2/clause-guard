"""Rule-based template-compliance scorecard for a draft GR.

Deterministic (zero LLM calls) so it is demo-safe. Returns per-rule pass/fail
with weights; the Streamlit app renders it as a live checklist.
"""
import re
from pathlib import Path

import yaml

RULES_FILE = Path(__file__).parent / "rules.yaml"


def load_rules():
    data = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    return data["rules"]


def score(draft_text: str) -> dict:
    rules = load_rules()
    results = []
    got = total = 0
    for r in rules:
        rx = re.compile(r["regex"], re.IGNORECASE | re.MULTILINE)
        passed = bool(rx.search(draft_text))
        w = int(r.get("weight", 1))
        total += w
        if passed:
            got += w
        results.append({
            "id": r["id"],
            "desc": r["desc"],
            "passed": passed,
            "weight": w,
        })
    return {
        "score": got,
        "max_score": total,
        "pct": round(100 * got / total) if total else 0,
        "checks": results,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    demo = "Government of Maharashtra\nHigher and Technical Education Department\n"
    s = score(demo)
    print(f"{s['score']}/{s['max_score']} ({s['pct']}%)")
    for c in s["checks"]:
        print(("PASS " if c["passed"] else "FAIL ") + c["desc"])
