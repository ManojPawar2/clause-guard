"""Citation-extraction recall — SRS acceptance criterion 1 (>= 80% of cited references).

Scored against a HAND-ANNOTATED ground truth (`data/citation_ground_truth.json`),
never against `corpus.jsonl`'s own `cited_codes` / `cited_refs`: those fields are
the output of the very function under test, so scoring on them would be circular
and would report ~100% for free.

Two populations are reported separately because they behave completely
differently, and only one of them is what the product actually receives:

* **clean drafts** — what a desk officer types, pastes or uploads into the app.
* **archived GRs** — first-page text of real portal PDFs, carrying the legacy-font
  glyph corruption documented in README. The anchor words the reference patterns
  key on (`शासन निर्णय`) extract corrupted and font-specifically, which is why the
  garble-tolerant digit-anchored fallback in `extract_metadata.py` exists.

Run: python src/reftrack/eval_citation_recall.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "ingest"))
from extract_metadata import extract_citations  # noqa: E402

GT_FILE = ROOT / "data" / "citation_ground_truth.json"
OUT_FILE = ROOT / "results" / "metrics_citation_recall.json"
READ_START = re.compile(r"(वाचा|Read)\s*[:\-]")
# Section headings start a line. Matching them mid-line truncates the block at
# the first citation (every 'शासन आदेश क्र...' entry contains 'आदेश') and would
# under-report recall — so these are line-anchored.
READ_END = re.compile(
    r"^\s*(प्रस्तावना|प्रसतावना|प्रस्ताविा|Preamble|शासन\s*निर्णय|Government\s+Resolution"
    r"|आदेश|ज्ञापन|ज्ञापन|शुध्दीपत्रक|शुद्धीपत्रक|शासन\s*शुध्दीपत्रक)\s*[:\-]?\s*$",
    re.MULTILINE,
)


def read_block(text: str) -> str:
    """The preamble reference block — the unit AC-1 is stated over."""
    m = READ_START.search(text)
    if not m:
        return ""
    rest = text[m.start() + 10:]
    e = READ_END.search(rest)
    return text[m.start(): m.start() + 10 + (e.start() if e else 800)]


def recovered(sig, extracted: dict) -> bool:
    """A citation counts as recovered when one extracted string carries all of
    its digit tokens (digits survive the font garble verbatim)."""
    if not sig:
        return False
    for s in list(extracted["cited_refs"]) + list(extracted["cited_codes"]):
        flat = re.sub(r"\s+", "", s)
        if all(tok in flat for tok in sig):
            return True
    return False


def score(docs, get_text):
    rows, hit, tot, unidentifiable = [], 0, 0, 0
    for d in docs:
        text = get_text(d)
        block = read_block(text) if text else ""
        ext = extract_citations(block) if block else {"cited_refs": [], "cited_codes": []}
        found = [c for c in d["citations"] if recovered(c["signature"], ext)]
        unidentifiable += sum(1 for c in d["citations"] if not c["signature"])
        hit += len(found)
        tot += len(d["citations"])
        rows.append({
            "id": d.get("gr_code") or d["id"],
            "expected": len(d["citations"]),
            "recovered": len(found),
            "letters_excluded": d.get("n_letters", 0),
            "missed": [c["label"] for c in d["citations"] if c not in found],
        })
    return {"n_docs": len(docs), "n_expected": tot, "n_recovered": hit,
            "recall": round(hit / tot, 4) if tot else None,
            "n_without_file_number": unidentifiable, "per_doc": rows}


def main():
    gt = json.loads(GT_FILE.read_text(encoding="utf-8"))

    def draft_text(d):
        p = ROOT / "data" / "planted" / f"{d['id']}.txt"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    # The 12 sampled Read blocks ship with the repo so this eval reproduces
    # without data/raw_pdfs/ (which is gitignored); PDFs are the fallback.
    cache = ROOT / "data" / "citation_eval_readblocks.json"
    blocks = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}

    def gr_text(d):
        if d["gr_code"] in blocks:
            return blocks[d["gr_code"]]
        p = ROOT / "data" / "raw_pdfs" / f"{d['gr_code']}.pdf"
        if not p.exists():
            return ""
        import pdfplumber
        with pdfplumber.open(p) as pdf:
            return pdf.pages[0].extract_text() or ""

    drafts = score([d for d in gt["clean_drafts"] if d["citations"]], draft_text)
    archived = score(gt["archived_grs"], gr_text)

    out = {
        "acceptance_criterion": "SRS AC-1 — extract >= 80% of cited references from a GR preamble",
        "ground_truth": "data/citation_ground_truth.json (hand-annotated, single annotator)",
        "not_scored_against": "corpus.jsonl cited_codes/cited_refs — produced by the function "
                             "under test, so scoring on them would be circular",
        "clean_drafts": drafts,
        "archived_grs": archived,
    }
    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    for name, r in (("clean drafts (the app's real input)", drafts),
                    ("archived GRs (legacy-font garble)", archived)):
        verdict = "PASS" if (r["recall"] or 0) >= 0.80 else "BELOW AC-1 TARGET"
        print(f"{name:38} recall {r['recall']:.2%}  "
              f"({r['n_recovered']}/{r['n_expected']} over {r['n_docs']} docs)  {verdict}")
        if r["n_without_file_number"]:
            print(f"{'':38} of which {r['n_without_file_number']} cite no file number at all")
    print(f"\n-> {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
