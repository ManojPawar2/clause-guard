# ClauseGuard — submission

**VJTI AI Hackathon 2026 · "Shaping Digital Governance" · Problem 1 (MAHA-GR-ALIGN)**

- **GitHub**: `<repo URL>`
- **Demo video**: `<YouTube unlisted URL>`

## Pitch (one paragraph)

ClauseGuard reviews a draft Government Resolution against 776 real Maharashtra GRs
(11,817 clauses, built from the Internet Archive while the live portal was down) and
flags the clause-level conflicts a drafting officer would otherwise miss. Retrieval
narrows thousands of clauses to ~30 candidates; a fine-tuned MuRIL cross-encoder
(238M, 130 ms/pair on CPU — no API, no rate limits) screens them to a handful; an LLM
then only *extracts* the competing values ("50 टक्के" vs "100 टक्के") and deterministic
code makes the conflict call — every flag ships with an auditable reason. The same app
links and currency-checks every citation, scores Manual-of-Office-Procedure compliance
(0%→100% live), and bundles a Marathi↔English legal glossary. It runs fully offline on
a laptop GPU.

## What makes it defensible

- **Real corpus, real mess**: the portal's PDFs carry legacy-font glyph corruption; we
  score it, filter it, and repair demo-critical documents under a digit audit that
  guarantees every numeral survives verbatim.
- **Measured evaluation, not marketing**: fine-tuned macro-F1 0.9134 (0.8957 on the
  leak-free subset) vs a protocol-matched TF-IDF baseline (0.7754), zero-shot
  Llama-70B (0.6521) and the model's own 8B teacher (0.499).
- **We audited our own labels**: a 50-pair human blind check + independent blind
  adjudication of every disagreement measured ~26% label noise in the synthetic
  contradiction/consistent labels — so we also report accuracy against adjudicated
  truth (~0.70), triangulated by a validated cross-family relabeler (0.6975 on 287
  pairs). The label-noise finding, provenance chain, and all raw artifacts are
  versioned in the repo.

## Run it

See `README.md` — quickstart uses the shipped corpus: `pip install -r requirements.txt`,
add keys to `.env` (or `LLM_MODE=ollama` for fully-local), `python src/index/build_index.py`,
`streamlit run app/streamlit_app.py`.

Evaluation: `EVAL_TABLE.md` · dataset provenance: `DATASET_CARD.md` · license: MIT.
