# ClauseGuard

AI-assisted Government Resolution (GR) drafting for Maharashtra — VJTI AI Hackathon 2026
("Shaping Digital Governance", Problem 1: MAHA-GR-ALIGN).

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
of the same portal** (≥20,000 archived **Marathi** GR PDFs enumerated via the CDX API —
the portal folder is labeled "English" but that reflects the portal UI language, not
the documents) — real GRs, archival copies. See `src/ingest/download_wayback.py`.

## Quickstart (uses the shipped corpus — minutes, not hours)

The parsed corpus (`data/corpus.jsonl`, 776 GRs) ships in the repo; you only need to
embed it and run the app:

```
pip install -r requirements.txt
cp .env.example .env        # Windows: copy — add GEMINI_API_KEY + GROQ_API_KEY,
                            # or uncomment LLM_MODE=ollama for a keyless local run
python src/llm/clients.py   # smoke-test the active provider(s)
python src/index/build_index.py              # e5-small -> Chroma (~10 min CPU)
streamlit run app/streamlit_app.py
```

## Rebuild the corpus from scratch (optional — several hours + LLM quota)

```
python src/ingest/bulk_download_all.py       # ~1,000 archival PDFs (HTE=08, SJ=22, SchoolEd=21)
python src/ingest/parse_pdfs.py corpus --min-quality 0.10
python src/index/build_index.py
python src/ingest/upsert_clean.py --top-retrieved 25   # targeted LLM repair, digit-audited
python src/detect/warm_cache.py              # planted scenarios end-to-end (warms the LLM cache)
```

Fine-tune track: `src/finetune/generate_pairs.py` → `validate_dataset.py` → `split_dataset.py`
→ `notebooks/finetune_muril_colab.ipynb` (Colab T4) → `eval_zeroshot.py` + `eval_local_latency.py`.
Results land in `EVAL_TABLE.md` / `DATASET_CARD.md`.

## The corpus-garble story (worth reading)

Most Maharashtra GR PDFs are text-based but typeset in legacy Devanagari fonts with
broken ToUnicode CMaps — text extracts *garbled* (e.g. `निर्णय` → `दनणचय`), differently
per font family. We (1) score every document's extraction quality against a common-word
list (`src/ingest/quality.py`), (2) keep the best-extracting documents, (3) repair
demo-visible documents with an LLM pass whose **digit audit** guarantees every numeral
survives verbatim (`src/ingest/upsert_clean.py`) — amounts and dates are the substance
of conflict detection and must never be "fixed" by the repair step.

**Validated next step (not run within the hackathon window)**: the glyphs *render*
correctly — only the extraction mapping is broken — so rendering pages to images and
OCR-ing them recovers clean text and would upgrade the whole corpus at the root.

Evaluation: `EVAL_TABLE.md` · dataset provenance and limitations: `DATASET_CARD.md`.

## License

MIT — see `LICENSE`.
