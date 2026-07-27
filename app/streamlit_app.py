"""MAHA-GR-ALIGN — Streamlit demo app.

Tabs: Review Draft | References | Scorecard | Glossary | About.
Degrades gracefully: each analysis that is unavailable (no index yet, no API
keys yet) explains itself instead of crashing the app.
"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
for sub in ("llm", "index", "ingest", "detect", "reftrack", "compliance"):
    sys.path.append(str(ROOT / "src" / sub))

st.set_page_config(page_title="MAHA-GR-ALIGN", page_icon="📜", layout="wide")

st.markdown(
    """
    <div style="padding:0.6rem 1rem;border-radius:12px;
         background:linear-gradient(90deg,#1a2980,#26d0ce);color:white">
    <h2 style="margin:0">📜 MAHA-GR-ALIGN</h2>
    <p style="margin:0">AI-assisted Government Resolution drafting — conflict detection ·
    reference tracking · template compliance · bilingual terminology</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def _corpus_file():
    # prefer the LLM-cleaned corpus when it exists
    for name in ("corpus_clean.jsonl", "corpus.jsonl"):
        p = ROOT / "data" / name
        if p.exists():
            return p
    return None


@st.cache_data
def load_corpus_cached(path_str, mtime):
    # mtime participates in the cache key so a rebuilt corpus refreshes the app
    return [json.loads(l) for l in Path(path_str).read_text(encoding="utf-8").splitlines()
            if l.strip()]


@st.cache_data
def load_glossary():
    return json.loads((ROOT / "data" / "glossary.json").read_text(encoding="utf-8"))


_cf = _corpus_file()
corpus = load_corpus_cached(str(_cf), _cf.stat().st_mtime) if _cf else []

# ---------- sidebar ----------
with st.sidebar:
    st.subheader("Corpus")
    if corpus:
        depts = {}
        for r in corpus:
            depts[r.get("department") or "?"] = depts.get(r.get("department") or "?", 0) + 1
        st.metric("GRs indexed", len(corpus))
        st.caption(" · ".join(f"{k.split('(')[0][:28]}: {v}" for k, v in
                              sorted(depts.items(), key=lambda x: -x[1])[:6]))
    else:
        st.warning("corpus.jsonl not built yet")

    st.subheader("Load a demo draft")
    planted = sorted((ROOT / "data" / "planted").glob("*.txt"))
    choice = st.selectbox("Planted scenario", ["—"] + [p.stem for p in planted])
    top_k = st.slider("Candidates per clause", 2, 8, 4)

default_text = ""
if choice != "—":
    default_text = (ROOT / "data" / "planted" / f"{choice}.txt").read_text(encoding="utf-8")

draft = st.text_area("Paste / edit the draft GR under review:", value=default_text,
                     height=260, placeholder="Paste a draft Government Resolution here…")

run = st.button("🔍 Review draft", type="primary", disabled=not draft.strip())

t_conf, t_refs, t_score, t_gloss, t_about = st.tabs(
    ["⚠️ Conflicts", "🔗 References", "✅ Scorecard", "📖 Glossary", "ℹ️ About"]
)

if run and draft.strip():
    # Scorecard (always available, deterministic)
    from scorecard import score
    st.session_state["score"] = score(draft)

    # References (needs corpus)
    if corpus:
        from citations import analyze_references
        st.session_state["refs"] = analyze_references(draft, corpus)

    # Conflicts (needs index + LLM keys)
    try:
        with st.spinner("Loading retrieval model (first run takes ~30 s)…"):
            from pipeline import review_draft
        prog = st.progress(0.0, text="analysing…")
        msgs = {"n": 0}

        def cb(msg):
            msgs["n"] += 1
            prog.progress(min(0.95, msgs["n"] / 40), text=msg)

        st.session_state["review"] = review_draft(draft, top_k=top_k, progress=cb)
        prog.progress(1.0, text="done")
    except Exception as e:
        st.session_state["review"] = {"error": str(e)}

with t_conf:
    r = st.session_state.get("review")
    if not r:
        st.info("Paste a draft and press **Review draft**.")
    elif "error" in r:
        st.error(f"Conflict analysis unavailable: {r['error']}")
        st.caption("Needs the Chroma index (`python src/index/build_index.py`) and "
                   "API keys in `.env`.")
    else:
        cap = f"{r['n_clauses']} draft clauses → {r['n_pairs']} candidate pairs"
        if r.get("n_muril_flagged") is not None:
            cap += (f" → fine-tuned MuRIL flagged {r['n_muril_flagged']} "
                    f"→ LLM-verified")
        st.caption(cap)
        n_err = sum(1 for v in r.get("verdicts", []) if v.get("label") == "error")
        if n_err:
            st.error(f"{n_err} of {len(r.get('verdicts', []))} pair verifications "
                     f"failed (LLM errors) — results are incomplete.")
        if not r["conflicts"]:
            if n_err:
                st.warning("No conflicts confirmed, but verification was incomplete — "
                           "not a clean pass.")
            else:
                st.success("No conflicts flagged against the indexed corpus.")
        for c in r["conflicts"]:
            m = c["meta"]
            with st.container(border=True):
                st.markdown(f"### 🔴 Conflict with GR `{m.get('gr_code','?')}`")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Draft clause**")
                    st.warning(c["draft"])
                with col2:
                    st.markdown(f"**Existing GR** — {m.get('department','?')}  \n"
                                f"№ `{m.get('gr_number','?')}` · {m.get('date','?')}")
                    st.info(c["candidate"])
                st.markdown(f"**Why it conflicts:** {c['reason']}")
                st.markdown(c["explanation"])

with t_refs:
    refs = st.session_state.get("refs")
    if not refs:
        st.info("Run a review (corpus must be built) to analyse the draft's references.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Citations found", refs["n_citations"])
        c2.metric("Linked to corpus", len(refs["linked"]))
        c3.metric("Stale / superseded", len(refs["stale"]))
        for s in refs["stale"]:
            st.error(f"⚠️ Cites **{s['cited']}** which appears superseded by "
                     f"`{s['superseded_by']}` — {s.get('successor_subject','')}")
        for a in refs.get("newer_related", []):
            newest = a["newer"][0]
            st.warning(
                f"🕐 **Currency check:** cites a GR dated **{a['cited_date']}** — "
                f"{len(a['newer'])} newer GR(s) exist on the same subject "
                f"(latest `{newest['gr_code']}`, {newest['date']}). "
                f"Verify the cited GR is still the operative one."
            )
        if refs["linked"]:
            st.markdown("**Linked references**")
            for l in refs["linked"]:
                m = l["match"]
                st.markdown(f"- `{l['cited'][:70]}` → **{m.get('department','?')}**, "
                            f"{m.get('date','?')} — {(m.get('subject') or '')[:90]}")
        if refs["unknown"]:
            with st.expander(f"Unmatched citations ({len(refs['unknown'])})"):
                for u in refs["unknown"]:
                    st.markdown(f"- `{u[:90]}`")

with t_score:
    s = st.session_state.get("score")
    if not s:
        st.info("Run a review to score the draft against the Manual of Office Procedure template.")
    else:
        st.metric("Template compliance", f"{s['score']}/{s['max_score']}",
                  f"{s['pct']}%")
        st.progress(s["pct"] / 100)
        for c in s["checks"]:
            icon = "✅" if c["passed"] else "❌"
            st.markdown(f"{icon} {c['desc']}  *(weight {c['weight']})*")

with t_gloss:
    q = st.text_input("Filter terms (Marathi or English)")
    rows = load_glossary()
    if q:
        rows = [g for g in rows if q.lower() in g["en"].lower() or q in g["mr"]]
    st.caption(f"{len(rows)} terms")
    for g in rows:
        note = f" — *{g['note']}*" if g.get("note") else ""
        st.markdown(f"**{g['mr']}** · {g['en']}{note}")

with t_about:
    st.markdown(
        """
**MAHA-GR-ALIGN** reviews a draft Maharashtra Government Resolution against a corpus of
real GRs (archival copies via the Wayback Machine — the live portal returned 503 during
the hackathon window).

**Pipeline**: clause chunking → multilingual retrieval (e5-small → Chroma) →
LLM screening of candidate pairs (Groq, batched) → detailed conflict explanations
(Gemini) → deterministic template scorecard → citation linking & supersession flags.

Built for VJTI AI Hackathon 2026 · Problem 1 · "Shaping Digital Governance".
        """
    )
