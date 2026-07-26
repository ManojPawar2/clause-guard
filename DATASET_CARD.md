# Dataset card — GR clause-conflict pairs (synthetic labels, real clause grounding)

> Status: skeleton — distributions and results are filled in by the pipeline once
> generation completes. Numbers in this card are written by scripts, not by hand.

## What this is
A 3-class NLI-style dataset (contradiction / consistent / neutral) of clause pairs for
detecting conflicts between Maharashtra Government Resolutions. Every pair is grounded
in a **real seed clause** from the project corpus (archival GR PDFs); the counterpart
clause and the label are **LLM-generated** (Gemini Flash / Groq Llama; generator recorded
per pair in the `generator` field).

## Generation
- Prompt: see `src/finetune/generate_pairs.py` (`GEN_PROMPT`) — verbatim, versioned in git.
- Contradiction types (tagged per pair): amount · date · eligibility · authority · scope.
- Anti-artifact rules: ~half of contradictions fully rephrased (low lexical overlap);
  consistent/neutral classes mirror the overlap spread; hard-negative neutrals reuse
  scheme vocabulary; premise/hypothesis order randomized post-hoc.
- Dedup: exact pair-text match (validate_dataset.py).
- Split: **grouped by seed clause** (no clause appears in two splits; asserted
  programmatically in `split_dataset.py`, seed 42).

## Distributions (from validate_dataset.py, final overnight build 2026-07-27)
- **Pairs: 4,490** (after exact-dedup) → split 3,633 train / 294 dev / 563 test (grouped by seed clause, leakage asserted)
- Labels: contradiction 1,796 · consistent 1,364 · neutral 1,330
- Languages: mr-en cross-lingual 3,290 · mr 886 · en 314
- Generators: ollama:llama3.1 3,604 · augment-numswap 350 · mined-neutral 218 · augment-truncation 297 · mined-neutral-hard 21
- Mean lexical overlap (Jaccard) by class: contradiction 0.211 · consistent 0.167 · neutral 0.015
- **TF-IDF + LogReg probe macro-F1: 0.788** (threshold 0.75 — exceeded). Interpretation: with the
  dominant cross-lingual construction, the residual signal is LLM English vocabulary style per label,
  inherent to single-generator data. The probe is therefore reported as the lexical-baseline row of
  the eval table; the fine-tuned model's margin above it (+0.13) is the semantic-learning evidence.
  A human blind-check of 50 stratified test pairs is reported alongside (see EVAL_TABLE.md).

## Known limitations (read this before trusting the numbers)
1. **All labels are LLM-generated.** A human spot-check of a random subset is reported
   where available; there was no legal-expert review.
2. **Shared provenance**: the zero-shot judge models are from the same model families
   that generated the data. Mitigation: per-generator F1 breakdown is reported
   (each judge's score on the *other* model's pairs is the cleaner cell).
3. The underlying corpus text passed through legacy-font extraction repair
   (`src/ingest/clean_corpus.py`); digits were audited to survive verbatim, but
   residual script noise may remain in some seed clauses.
4. Marathi pairs are machine-generated Marathi; register may differ from drafted GR prose.
5. Source clauses come from public government documents (archival copies).
