# MAHA-GR-ALIGN

AI-assisted Government Resolution (GR) drafting for Maharashtra — VJTI AI Hackathon 2026
("Shaping Digital Governance", Problem 1).

Reviews a draft GR against a corpus of real Maharashtra GRs and provides:

1. **Cross-departmental conflict detection** — retrieval narrows candidate clause pairs,
   an LLM (and optionally a fine-tuned MuRIL cross-encoder) screens them, and flagged
   conflicts get a drafting-officer-grade explanation citing the conflicting GRs.
2. **Reference tracking** — extracts cited GR numbers/codes, links them to the corpus,
   flags stale (superseded) references, suggests successors.
3. **Template compliance** — deterministic scorecard against Manual of Office Procedure
   conventions (header, Read block, preamble, numbered clauses, signature formula, code).
4. **Bilingual terminology** — Marathi ↔ English legal/administrative glossary.

## Corpus note

The live portal gr.maharashtra.gov.in returned 503 throughout the hackathon window
(Jul 26–28, 2026). The corpus was therefore built from the **Wayback Machine's archive
of the same portal** (≥20,000 archived English GR PDFs enumerated via the CDX API) —
real GRs, archival copies. See `src/ingest/download_wayback.py`.

## Run

```
pip install -r requirements.txt
copy .env.example .env   # add GEMINI_API_KEY, GROQ_API_KEY
python src/ingest/download_wayback.py bulk --codes <dept-codes> --max 600
python src/ingest/parse_pdfs.py corpus
python src/index/build_index.py
streamlit run app/streamlit_app.py
```

(Build log and evaluation results are added as the project progresses.)
