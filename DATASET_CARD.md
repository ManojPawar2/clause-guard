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

## Distributions (filled by validate_dataset.py output)
- Pairs: _TBD_ · labels: _TBD_ · languages: _TBD_ · generators: _TBD_
- Mean lexical overlap (Jaccard) by class: _TBD_
- TF-IDF + LogReg probe macro-F1 (lexical-artifact check): _TBD_ (threshold 0.75)

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
