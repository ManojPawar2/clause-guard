"""Parse downloaded GR PDFs into structured records.

Modes:
  headers --dir data/raw_pdfs/sample     print filename-code vs parsed department
                                         (used to verify the trailing-code=dept hypothesis)
  corpus  [--dir data/raw_pdfs]          build data/corpus.jsonl from all PDFs in dir
"""
import argparse
import json
import sys
from pathlib import Path

import pdfplumber

sys.path.append(str(Path(__file__).parent))
from chunk_clauses import chunk  # noqa: E402
from extract_metadata import extract_citations, parse_header  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def read_pdf(path: Path, max_pages: int = 30):
    """Return (first_page_text, full_text) or (None, None) on failure."""
    try:
        with pdfplumber.open(path) as pdf:
            pages = []
            for pg in pdf.pages[:max_pages]:
                pages.append(pg.extract_text() or "")
            return (pages[0] if pages else ""), "\n".join(pages)
    except Exception as e:
        print(f"  PARSE-FAIL {path.name}: {type(e).__name__}: {e}", flush=True)
        return None, None


def cmd_headers(dir_: Path):
    rows = []
    for p in sorted(dir_.glob("*.pdf")):
        first, _ = read_pdf(p, max_pages=1)
        if first is None:
            rows.append((p.stem[-2:], p.stem, "UNREADABLE", ""))
            continue
        h = parse_header(first)
        rows.append((p.stem[-2:], p.stem, h["department"] or "?", (h["subject"] or "")[:60]))
    rows.sort()
    for code, stem, dept, subj in rows:
        print(f"{code} | {stem} | {dept} | {subj}")


def cmd_corpus(dir_: Path, out: Path):
    n_ok = n_thin = n_fail = 0
    with out.open("w", encoding="utf-8") as f:
        for p in sorted(dir_.glob("*.pdf")):
            first, full = read_pdf(p)
            if first is None:
                n_fail += 1
                continue
            if len((full or "").strip()) < 400:  # likely scanned/empty
                n_thin += 1
                continue
            h = parse_header(first)
            cites = extract_citations(full)
            clauses = chunk(full)
            rec = {
                "id": p.stem,
                "gr_code": p.stem,
                "department": h["department"],
                "gr_number": h["gr_number"],
                "date": h["date"],
                "subject": h["subject"],
                "n_chars": len(full),
                "clauses": clauses,
                **cites,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += 1
    print(f"corpus: ok={n_ok} thin/scanned={n_thin} fail={n_fail} -> {out}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["headers", "corpus"])
    ap.add_argument("--dir", default=str(ROOT / "data" / "raw_pdfs"))
    ap.add_argument("--out", default=str(ROOT / "data" / "corpus.jsonl"))
    a = ap.parse_args()
    if a.mode == "headers":
        cmd_headers(Path(a.dir))
    else:
        cmd_corpus(Path(a.dir), Path(a.out))
