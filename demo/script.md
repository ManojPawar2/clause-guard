# Demo video script (~3.5–4 min)

> Record with Xbox Game Bar (Win+G) against a WARM LLM cache. Trim in Clipchamp.
> Do a 2-minute test clip first. Max 2 full takes; take 2 ships.

| t | Beat | On screen | Voiceover (draft) |
|---|------|-----------|-------------------|
| 0:00–0:20 | Problem | Screenshot of a real GR + the portal's 503 page | "Maharashtra issues thousands of Government Resolutions. Nothing checks a new draft against what's already in force — conflicting amounts, stale references, broken formats slip through. ClauseGuard fixes that." |
| 0:20–0:50 | Architecture | One slide: corpus → e5 retrieval → LLM/classifier screen → explain; scorecard; citations | "We indexed real GRs from the Higher & Technical Education, School Education and Social Justice departments — pulled from the Internet Archive because the live portal was down all weekend. Clause-level multilingual retrieval narrows candidates; a screening layer flags conflicts; an LLM explains only what's flagged." |
| 0:50–2:10 | **Scenario A — fee-reimbursement conflict** | Load planted HTE draft → Review → funnel caption (11,817 clauses → ~30 candidates → MuRIL flags ~3 → verified conflicts) → red conflict card, side-by-side clauses, explanation | "This draft sets fee reimbursement at 50%. The system searches eleven thousand clauses, the fine-tuned classifier narrows thirty candidates to three in milliseconds, and the verifier confirms one real conflict: the existing Higher & Technical Education GR of July 2024 mandates 100% reimbursement for the same students. The reason is built from extracted values — fifty per cent versus one hundred per cent — fully auditable, not a black-box opinion." |
| 2:10–2:50 | **Scenario B — outdated reference** | References tab: citation linked (1/1), yellow **Currency check** warning listing 2 newer same-subject GRs | "The draft funds a 2022 scheme by citing the original GR. The tracker links the citation and warns: two newer GRs exist on the same subject — verify the cited one is still operative. A currency check on every citation, automatically." |
| 2:50–3:30 | **Scenario C — compliance + terminology** | Broken draft: report header shows **0%** compliance and **3** terminology flags → load the fixed draft: **100%** and **0** flags | "The scorecard runs thirteen Manual-of-Office-Procedure checks — including the financial sanction block and the budget head. The broken draft scores zero and trips three terminology flags. Load the corrected version: one hundred per cent, no flags." |
| 3:30–3:45 | Terminology beat | Glossary tab on the BROKEN draft — the three red→green correction chips | "Every term is checked against a controlled bilingual glossary. 'Govt. Resolution' should be 'Government Resolution'; 'handicapped' should be 'Person with disability' — the term Government policy actually mandates. It suggests the approved form, not just a warning." |
| 3:40–4:00 | Eval + close | Eval table screenshot (fine-tuned vs zero-shot) + repo link | "A fine-tuned MuRIL classifier screens clause pairs at milliseconds per pair — benchmarked against zero-shot LLMs on a held-out set. Code, dataset and eval are in the repo." |

## Recording checklist
- [ ] `.env` has `LLM_MODE=ollama` (fully local — quota can't ruin a take) and `ollama serve` is up
- [ ] `streamlit run app/streamlit_app.py` fresh; sidebar shows corpus stats
- [ ] Cache warmed: `python src/detect/warm_cache.py` reports all scenarios green
- [ ] Architecture slide for the 0:20 beat: open `demo/architecture_slide.html` in a browser tab, F11 fullscreen
- [ ] Browser zoom 110–125%, hide bookmarks bar
- [ ] Mic test clip watched back
- [ ] All planted drafts load from the sidebar selector
