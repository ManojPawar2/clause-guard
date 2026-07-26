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
copy .env.example .env                       # add GEMINI_API_KEY, GROQ_API_KEY
python src/llm/clients.py                    # smoke-test both providers

python src/ingest/bulk_download_all.py       # ~1,000 archival PDFs (HTE=08, SJ=22, SchoolEd=21)
python src/ingest/parse_pdfs.py corpus --min-quality 0.10
python src/ingest/clean_corpus.py            # LLM repair of legacy-font garble (digit-audited)
python src/index/build_index.py              # e5-small -> Chroma

python src/detect/warm_cache.py              # run planted scenarios end-to-end (warms cache)
streamlit run app/streamlit_app.py
```

Fine-tune track: `src/finetune/generate_pairs.py` → `validate_dataset.py` → `split_dataset.py`
→ `notebooks/finetune_muril_colab.ipynb` (Colab T4) → `eval_zeroshot.py` + `eval_local_latency.py`.
Results land in `EVAL_TABLE.md` / `DATASET_CARD.md`.

## The corpus-garble story (worth reading)

Most Maharashtra GR PDFs are text-based but typeset in legacy Devanagari fonts with
broken ToUnicode CMaps — text extracts *garbled* (e.g. `निर्णय` → `दनणचय`), differently
per font family. We (1) score every document's extraction quality against a common-word
list (`src/ingest/quality.py`), (2) keep the best-extracting documents, (3) repair
residual corruption with an LLM pass whose **digit audit** guarantees every numeral
survives verbatim (`src/ingest/clean_corpus.py`) — amounts and dates are the substance
of conflict detection and must never be "fixed" by the repair step.

(Build log and evaluation results are added as the project progresses.)
