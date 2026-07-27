# Demo video script (~3.5–4 min)

> Record with Xbox Game Bar (Win+G) against a WARM LLM cache. Trim in Clipchamp.
> Do a 2-minute test clip first. Max 2 full takes; take 2 ships.

| t | Beat | On screen | Voiceover (draft) |
|---|------|-----------|-------------------|
| 0:00–0:20 | Problem | Screenshot of a real GR + the portal's 503 page | "Maharashtra issues thousands of Government Resolutions. Nothing checks a new draft against what's already in force — conflicting amounts, stale references, broken formats slip through. MAHA-GR-ALIGN fixes that." |
| 0:20–0:50 | Architecture | One slide: corpus → e5 retrieval → LLM/classifier screen → explain; scorecard; citations | "We indexed real GRs from the Higher & Technical Education, School Education and Social Justice departments — pulled from the Internet Archive because the live portal was down all weekend. Clause-level multilingual retrieval narrows candidates; a screening layer flags conflicts; an LLM explains only what's flagged." |
| 0:50–2:10 | **Scenario A — fee-reimbursement conflict** | Load planted HTE draft → Review → funnel caption (11,817 clauses → ~30 candidates → MuRIL flags ~3 → verified conflicts) → red conflict card, side-by-side clauses, explanation | "This draft sets fee reimbursement at 50% and makes students pay upfront. The system searches eleven thousand clauses, the fine-tuned classifier narrows them in milliseconds, and it finds the existing Higher & Technical Education GR of July 2024: 100% reimbursement, and students must NOT be made to pay at admission. Both contradictions — amount and procedure — flagged with an auditable reason." |
| 2:10–2:50 | **Scenario B — outdated reference** | References tab: citation linked (1/1), yellow **Currency check** warning listing 2 newer same-subject GRs | "The draft funds a 2022 scheme by citing the original GR. The tracker links the citation and warns: two newer GRs exist on the same subject — verify the cited one is still operative. A currency check on every citation, automatically." |
| 2:50–3:30 | **Scenario C — compliance scorecard** | Broken draft scores low → fixed draft rescores high | "The template scorecard checks the Manual of Office Procedure format — watch the score jump when the missing Read block and date format are fixed." |
| 3:30–3:40 | Glossary beat | Glossary tab, filter a term | "Bilingual legal terminology, built in." |
| 3:40–4:00 | Eval + close | Eval table screenshot (fine-tuned vs zero-shot) + repo link | "A fine-tuned MuRIL classifier screens clause pairs at milliseconds per pair — benchmarked against zero-shot LLMs on a held-out set. Code, dataset and eval are in the repo." |

## Recording checklist
- [ ] `streamlit run app/streamlit_app.py` fresh; sidebar shows corpus stats
- [ ] Cache warmed: each scenario reviewed at least once before recording
- [ ] Browser zoom 110–125%, hide bookmarks bar
- [ ] Mic test clip watched back
- [ ] All three planted drafts load from the sidebar selector
