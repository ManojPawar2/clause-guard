"""Audit trail of AI suggestions and human edits (SRS FR-15).

Append-only JSONL at data/audit_trail.jsonl. Every **Review draft** click
appends one record carrying three things:

* the draft itself (sha256 + full text),
* every AI suggestion offered on that run — verified conflicts (with the
  code-built reason and suggested fix), citation warnings, terminology
  corrections — plus the deterministic results (compliance %, funnel counts),
* the **human edits**: a unified diff of this draft against the previously
  recorded one. The app hands us the text-area contents on every run, so the
  diff between consecutive submissions IS what the officer changed.

Deterministic and LLM-free, same contract as scorecard.py. The trail is a
local file only (NFR-2: drafts never leave the machine) and is gitignored —
it is runtime data and contains draft text.
"""
import csv
import difflib
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIL_FILE = ROOT / "data" / "audit_trail.jsonl"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _suggested_fix(reason: str, gr_code) -> str:
    """Same two-value construction the app shows on the conflict card (FR-14)."""
    vals = re.findall(r"'([^']+)'", reason or "")
    if len(vals) < 2:
        return ""
    return (f"align the draft to '{vals[1]}', or keep '{vals[0]}' and add an "
            f"explicit clause superseding GR {gr_code} for this benefit")


def _unified_diff(prev: str, cur: str) -> dict:
    lines = list(difflib.unified_diff(
        prev.splitlines(), cur.splitlines(),
        fromfile="previous_draft", tofile="this_draft", lineterm=""))
    return {
        "diff": "\n".join(lines),
        "lines_added": sum(1 for l in lines[2:] if l.startswith("+")),
        "lines_removed": sum(1 for l in lines[2:] if l.startswith("-")),
    }


def build_record(draft: str, score=None, terms=None, refs=None, review=None,
                 prev_draft=None, source="review") -> dict:
    """One trail record. All analysis arguments are the session results as the
    app already holds them; any of them may be None (that stage was skipped)."""
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "draft_sha256": _sha(draft),
        "draft_chars": len(draft),
        "draft": draft,
        "ai_suggestions": {"conflicts": [], "citation_warnings": [],
                           "terminology": []},
        "deterministic": {},
        "human_edit": None,
    }

    if prev_draft is not None and prev_draft != draft:
        rec["human_edit"] = {"prev_sha256": _sha(prev_draft),
                             **_unified_diff(prev_draft, draft)}

    if score:
        rec["deterministic"]["compliance_pct"] = score.get("pct")
        rec["deterministic"]["failed_checks"] = [
            c["id"] for c in score.get("checks", []) if not c["passed"]]

    if review and "error" not in review:
        rec["deterministic"]["funnel"] = {
            "n_clauses": review.get("n_clauses"),
            "n_pairs": review.get("n_pairs"),
            "n_muril_flagged": review.get("n_muril_flagged"),
            "n_conflicts": len(review.get("conflicts", [])),
        }
        for c in review.get("conflicts", []):
            gr = c.get("meta", {}).get("gr_code", "?")
            rec["ai_suggestions"]["conflicts"].append({
                "gr_code": gr,
                "reason": c.get("reason"),
                "suggested_fix": _suggested_fix(c.get("reason"), gr),
                "explanation": c.get("explanation"),
            })

    if refs:
        for s in refs.get("stale", []):
            rec["ai_suggestions"]["citation_warnings"].append(
                {"kind": "superseded", "cited": s.get("cited"),
                 "superseded_by": s.get("superseded_by")})
        for a in refs.get("newer_related", []):
            rec["ai_suggestions"]["citation_warnings"].append(
                {"kind": "currency", "cited_date": a.get("cited_date"),
                 "n_newer": len(a.get("newer", []))})

    if terms:
        for f in terms.get("flags", []):
            rec["ai_suggestions"]["terminology"].append(
                {"kind": f.get("kind"), "found": f.get("found"),
                 "approved_mr": f.get("approved_mr"),
                 "approved_en": f.get("approved_en")})

    return rec


def load_runs(path=None) -> list:
    """All records, oldest first. Tolerates a torn final line (crash mid-append)."""
    p = Path(path or TRAIL_FILE)
    if not p.exists():
        return []
    runs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return runs


def append_run(draft: str, score=None, terms=None, refs=None, review=None,
               path=None, source="review") -> dict:
    """Build a record diffed against the last recorded draft and append it."""
    p = Path(path or TRAIL_FILE)
    runs = load_runs(p)
    prev = runs[-1]["draft"] if runs else None
    rec = build_record(draft, score=score, terms=terms, refs=refs,
                       review=review, prev_draft=prev, source=source)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def to_csv(runs: list) -> str:
    """Flat per-run summary (the full detail stays in the JSONL)."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["ts", "source", "draft_sha256", "draft_chars", "compliance_pct",
                "n_conflicts", "n_citation_warnings", "n_terminology_flags",
                "edit_lines_added", "edit_lines_removed"])
    for r in runs:
        s, e = r.get("ai_suggestions", {}), r.get("human_edit") or {}
        w.writerow([r.get("ts"), r.get("source"), r.get("draft_sha256"),
                    r.get("draft_chars"),
                    r.get("deterministic", {}).get("compliance_pct"),
                    len(s.get("conflicts", [])),
                    len(s.get("citation_warnings", [])),
                    len(s.get("terminology", [])),
                    e.get("lines_added"), e.get("lines_removed")])
    return out.getvalue()


if __name__ == "__main__":
    # Self-test: append two runs with an edit between them to a scratch trail,
    # read back, and confirm the second record carries a non-empty diff.
    import sys
    import tempfile
    sys.stdout.reconfigure(encoding="utf-8")
    scratch = Path(tempfile.mkdtemp()) / "trail_selftest.jsonl"
    d1 = "Government of Maharashtra\n1. The stipend shall be Rs. 1,000.\n"
    d2 = "Government of Maharashtra\n1. The stipend shall be Rs. 2,000.\n"
    fake_score = {"pct": 40, "checks": [{"id": "read_block", "passed": False}]}
    fake_review = {"n_clauses": 1, "n_pairs": 3, "n_muril_flagged": 1,
                   "conflicts": [{"meta": {"gr_code": "202207131204391408"},
                                  "reason": "draft says '50 %' vs existing '100 %'",
                                  "explanation": "…"}]}
    append_run(d1, score=fake_score, path=scratch)
    append_run(d2, score=fake_score, review=fake_review, path=scratch)
    runs = load_runs(scratch)
    assert len(runs) == 2, f"expected 2 records, got {len(runs)}"
    assert runs[0]["human_edit"] is None
    edit = runs[1]["human_edit"]
    assert edit and "-1. The stipend shall be Rs. 1,000." in edit["diff"]
    assert edit["lines_added"] == 1 and edit["lines_removed"] == 1
    fix = runs[1]["ai_suggestions"]["conflicts"][0]["suggested_fix"]
    assert "'100 %'" in fix, fix
    assert to_csv(runs).count("\n") == 3
    print(f"trail self-test OK — 2 records round-tripped via {scratch}")
