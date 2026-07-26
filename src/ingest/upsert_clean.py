"""Incrementally LLM-clean specific GRs and upsert them into corpus.jsonl + Chroma.

Used for targeted repair of high-value documents before the full-corpus cleanup
pass runs (the full pass writes corpus_clean.jsonl; this edits corpus.jsonl in
place so partial cleaning never shadows the rest of the corpus).

Usage: python src/ingest/upsert_clean.py 202407191857335408 [more codes ...]
       python src/ingest/upsert_clean.py --top-retrieved 50   (clean the N most
       scholarship-relevant docs by keyword count)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "ingest"))
sys.path.append(str(ROOT / "src" / "llm"))
sys.path.append(str(ROOT / "src" / "index"))

from clean_corpus import clean_one  # noqa: E402

CORPUS = ROOT / "data" / "corpus.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--top-retrieved", type=int, default=0)
    ap.add_argument("--max-chars", type=int, default=9000)
    args = ap.parse_args()

    recs = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines()]
    by_code = {r["gr_code"]: r for r in recs}

    targets = list(args.codes)
    if args.top_retrieved:
        KEYS = ["शिष्यवृत्ती", "शुल्क", "प्रतिपूर्ती", "विद्यार्थ", "EWS", "EBC", "OBC",
                "SEBC", "stipend", "scholarship", "fee"]
        scored = []
        for r in recs:
            if r.get("cleaned"):
                continue
            blob = (r.get("subject") or "") + " " + " ".join(r["clauses"])[:4000]
            scored.append((sum(blob.count(k) for k in KEYS), r["gr_code"]))
        scored.sort(reverse=True)
        targets += [c for s, c in scored[: args.top_retrieved] if s > 0]

    targets = [c for c in dict.fromkeys(targets) if c in by_code
               and not by_code[c].get("cleaned")]
    print(f"cleaning {len(targets)} GRs", flush=True)

    from build_index import client, model, COLLECTION
    col = client().get_collection(COLLECTION)
    m = model()

    n_ok = 0
    for code in targets:
        try:
            cleaned = clean_one(by_code[code], args.max_chars)
        except Exception as e:
            print(f"  FAIL {code}: {str(e)[:120]}", flush=True)
            continue
        by_code[code] = cleaned
        # replace this GR's clauses in the index
        old_ids = [f"{code}:{i}" for i in range(120)]
        try:
            col.delete(ids=old_ids)
        except Exception:
            pass
        clauses = cleaned["clauses"][:60]
        if clauses:
            embs = m.encode([f"passage: {c}" for c in clauses], normalize_embeddings=True)
            col.add(
                ids=[f"{code}:{i}" for i in range(len(clauses))],
                documents=clauses,
                metadatas=[{
                    "gr_code": code,
                    "department": cleaned.get("department") or "?",
                    "date": cleaned.get("date") or "?",
                    "subject": (cleaned.get("subject") or "?")[:200],
                    "gr_number": cleaned.get("gr_number") or "?",
                } for _ in clauses],
                embeddings=embs.tolist(),
            )
        n_ok += 1
        print(f"  OK {code}: {len(clauses)} clauses re-indexed "
              f"(digits_ok={cleaned.get('digit_audit_ok')}, "
              f"readability={cleaned.get('readability_after')})", flush=True)

    # rewrite corpus.jsonl with the cleaned records merged in
    with CORPUS.open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(by_code[r["gr_code"]], ensure_ascii=False) + "\n")
    print(f"DONE: {n_ok}/{len(targets)} cleaned and upserted", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
