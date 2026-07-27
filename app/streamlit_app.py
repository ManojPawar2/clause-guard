"""MAHA-GR-ALIGN — Streamlit demo app.

Tabs: Conflicts | References | Scorecard | Glossary | About.
Degrades gracefully: each analysis that is unavailable (no index yet, no API
keys yet) explains itself instead of crashing the app.
"""
import json
import os
import re
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
for sub in ("llm", "index", "ingest", "detect", "reftrack", "compliance"):
    sys.path.append(str(ROOT / "src" / sub))

from clients import GEMINI_MODEL, GROQ_MODEL, LLM_MODE, OLLAMA_MODEL  # noqa: E402

st.set_page_config(page_title="ClauseGuard", page_icon="📜", layout="wide")

MURIL_ON = (os.environ.get("USE_MURIL", "1") != "0"
            and (ROOT / "model" / "muril_gr_conflict_fp16" / "config.json").exists())
MODE_BADGE = (f"🖥️ local · Ollama {OLLAMA_MODEL}" if LLM_MODE == "ollama"
              else f"☁️ cloud · {GROQ_MODEL.split('-versatile')[0]} + {GEMINI_MODEL}")

st.markdown(
    f"""
    <div style="padding:0.9rem 1.3rem;border-radius:14px;
         background:linear-gradient(100deg,#152452 0%,#1c3a6e 55%,#1d5f6b 100%);
         border:1px solid #2b3a55">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
      <div>
        <h2 style="margin:0;color:#fff">📜 ClauseGuard</h2>
        <p style="margin:.15rem 0 0;color:#c9d6ea">Conflict-aware Government Resolution drafting —
        detection · references · compliance · bilingual</p>
      </div>
      <div style="text-align:right">
        <span style="background:#0e1a30;border:1px solid #33507e;border-radius:999px;
              padding:.3rem .8rem;color:#9fc0ff;font-size:.85rem">{MODE_BADGE}</span><br>
        <span style="background:#0e1a30;border:1px solid #2f5e46;border-radius:999px;
              padding:.3rem .8rem;color:#8fd0a0;font-size:.85rem;display:inline-block;margin-top:.35rem">
              {'🧠 MuRIL screening ON · 130 ms/pair' if MURIL_ON else 'MuRIL screening off — LLM verifies all pairs'}</span>
      </div>
    </div></div>
    """,
    unsafe_allow_html=True,
)

SCENARIOS = {
    "1_fee_conflict_draft": ("Scenario A — fee-reimbursement conflict",
                             "50% draft vs an in-force 100% GR: the planted contradiction"),
    "2_stale_reference_draft": ("Scenario B — outdated reference",
                                "cites a 2022 GR that has newer same-subject successors"),
    "3_broken_format_draft": ("Scenario C1 — broken format",
                              "missing Read block, bad date format → low scorecard"),
    "3_broken_format_FIXED": ("Scenario C2 — format fixed",
                              "same draft repaired → watch the score jump"),
}


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
    st.subheader("📚 Corpus")
    if corpus:
        n_clauses = sum(len(r.get("clauses", [])) for r in corpus)
        c1, c2 = st.columns(2)
        c1.metric("Real GRs", f"{len(corpus):,}")
        c2.metric("Clauses", f"{n_clauses:,}")
        depts = {}
        for r in corpus:
            depts[r.get("department") or "?"] = depts.get(r.get("department") or "?", 0) + 1
        with st.expander("Departments"):
            for k, v in sorted(depts.items(), key=lambda x: -x[1])[:8]:
                st.caption(f"{k.split('(')[0][:34]} — **{v}**")
    else:
        st.warning("corpus.jsonl not built yet")

    st.subheader("🎬 Demo scenarios")
    planted = sorted((ROOT / "data" / "planted").glob("*.txt"))
    labels = {"—": "— none —"}
    labels.update({p.stem: SCENARIOS.get(p.stem, (p.stem, ""))[0] for p in planted})
    choice = st.selectbox("Load a planted draft", list(labels), format_func=labels.get)
    if choice != "—" and choice in SCENARIOS:
        st.caption(SCENARIOS[choice][1])

    with st.expander("⚙️ Advanced"):
        # default matches the pipeline / warm-cache default so demo runs stay cached
        top_k = st.slider("Candidates per clause", 2, 8, 6)

default_text = ""
if choice != "—":
    default_text = (ROOT / "data" / "planted" / f"{choice}.txt").read_text(encoding="utf-8")

draft = st.text_area("Paste / edit the draft GR under review:", value=default_text,
                     height=240, placeholder="Paste a draft Government Resolution here…")

run = st.button("🔍 Review draft", type="primary", use_container_width=True,
                disabled=not draft.strip())

t_conf, t_refs, t_score, t_gloss, t_about = st.tabs(
    ["⚠️ Conflicts", "🔗 References", "✅ Scorecard", "📖 Glossary", "ℹ️ About"]
)

if run and draft.strip():
    # Scorecard (always available, deterministic)
    from scorecard import score
    if "score" in st.session_state:  # keep the previous run for the before/after delta
        st.session_state["score_prev"] = st.session_state["score"]
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


def value_chips(reason: str):
    """Render the two extracted values from a code-built reason as compare chips."""
    vals = re.findall(r"'([^']+)'", reason or "")
    if len(vals) < 2:
        return
    st.markdown(
        f"""<div style="display:flex;gap:.8rem;align-items:center;margin:.4rem 0 .6rem">
        <span style="background:#3a1520;border:1px solid #8a3a4a;border-radius:10px;
              padding:.45rem 1rem;font-size:1.15rem;color:#ff9fb0">draft&nbsp;·&nbsp;<b>{vals[0]}</b></span>
        <span style="color:#93a1b8;font-size:1.3rem">vs</span>
        <span style="background:#12301f;border:1px solid #2f5e46;border-radius:10px;
              padding:.45rem 1rem;font-size:1.15rem;color:#8fd0a0">in&nbsp;force&nbsp;·&nbsp;<b>{vals[1]}</b></span>
        </div>""",
        unsafe_allow_html=True,
    )


with t_conf:
    r = st.session_state.get("review")
    if not r:
        st.info("Paste a draft (or pick a scenario in the sidebar) and press **Review draft**.")
    elif "error" in r:
        st.error(f"Conflict analysis unavailable: {r['error']}")
        st.caption("Needs the Chroma index (`python src/index/build_index.py`) and "
                   "API keys in `.env` (or `LLM_MODE=ollama`).")
    else:
        # the funnel: thousands of clauses -> candidates -> model flags -> verified
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Draft clauses", r["n_clauses"],
                  help="Numbered clauses extracted from the draft (boilerplate filtered)")
        f2.metric("Candidate pairs", r["n_pairs"],
                  help="Semantically-nearest corpus clauses per draft clause "
                       "(e5-small → Chroma, near-duplicate suppressed)")
        if r.get("n_muril_flagged") is not None:
            f3.metric("MuRIL flags", r["n_muril_flagged"],
                      delta=f"-{r['n_pairs'] - r['n_muril_flagged']} screened out",
                      delta_color="off",
                      help="Fine-tuned 238M cross-encoder, ~130 ms/pair on CPU")
        else:
            f3.metric("MuRIL flags", "off")
        f4.metric("Verified conflicts", len(r["conflicts"]),
                  help="LLM extracts the competing values; code makes the call")

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
                st.markdown(f"#### 🔴 Conflict with GR `{m.get('gr_code','?')}`")
                value_chips(c["reason"])
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Draft clause**")
                    st.warning(c["draft"])
                with col2:
                    st.markdown(f"**Existing GR** — {m.get('department','?')}  \n"
                                f"№ `{m.get('gr_number','?')}` · {m.get('date','?')}")
                    st.info(c["candidate"])
                st.markdown(f"**Why it conflicts:** {c['reason']}")
                with st.expander("📝 Drafting-officer explanation"):
                    st.markdown(c["explanation"])

with t_refs:
    refs = st.session_state.get("refs")
    if not refs:
        st.info("Run a review (corpus must be built) to analyse the draft's references.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Citations found", refs["n_citations"],
                  help="Formal GR references + 18-digit unique codes in the draft "
                       "(the draft's own header/footer are excluded)")
        c2.metric("Linked to corpus", len(refs["linked"]))
        c3.metric("Currency warnings", len(refs.get("newer_related", [])),
                  help="Cited GRs with newer same-subject GRs in force")
        c4.metric("Explicit supersessions", len(refs["stale"]))
        for s in refs["stale"]:
            st.error(f"⚠️ Cites **{s['cited']}** which appears superseded by "
                     f"`{s['superseded_by']}` — {s.get('successor_subject','')}")
        for a in refs.get("newer_related", []):
            newest = a["newer"][0]
            with st.container(border=True):
                st.markdown(f"🕐 **Currency check** — the draft cites a GR dated "
                            f"**{a['cited_date']}**, but {len(a['newer'])} newer GR(s) "
                            f"exist on the same subject. Verify it is still operative.")
                for nr in a["newer"]:
                    st.caption(f"↳ `{nr['gr_code']}` · {nr['date']} — {nr['subject']}")
        if refs["linked"]:
            st.markdown("**Linked references**")
            for l in refs["linked"]:
                m = l["match"]
                with st.container(border=True):
                    lc1, lc2 = st.columns([2, 3])
                    lc1.markdown(f"`{l['cited'][:60]}`  \n*via {l['via']}*")
                    lc2.markdown(f"**{m.get('department','?')}** · {m.get('date','?')}  \n"
                                 f"{(m.get('subject') or '')[:110]}")
        if refs["unknown"]:
            with st.expander(f"Unmatched citations ({len(refs['unknown'])})"):
                for u in refs["unknown"]:
                    st.markdown(f"- `{u[:90]}`")

with t_score:
    s = st.session_state.get("score")
    if not s:
        st.info("Run a review to score the draft against the Manual of Office Procedure template.")
    else:
        prev = st.session_state.get("score_prev")
        delta = (f"{s['pct'] - prev['pct']:+d}% vs previous draft"
                 if prev and prev["pct"] != s["pct"] else None)
        st.metric("Template compliance", f"{s['pct']}%", delta,
                  help=f"{s['score']}/{s['max_score']} weighted points — "
                       "11 deterministic Manual-of-Office-Procedure checks")
        st.progress(s["pct"] / 100)
        fails = [c for c in s["checks"] if not c["passed"]]
        passes = [c for c in s["checks"] if c["passed"]]
        if fails:
            st.markdown("**Fix these:**")
            for c in fails:
                st.markdown(f"❌ {c['desc']}  *(weight {c['weight']})*")
        else:
            st.success("Every template check passes.")
        with st.expander(f"✅ Passing checks ({len(passes)})"):
            for c in passes:
                st.markdown(f"✅ {c['desc']}  *(weight {c['weight']})*")

with t_gloss:
    q = st.text_input("🔎 Filter terms (Marathi or English)")
    rows = load_glossary()
    if q:
        rows = [g for g in rows if q.lower() in g["en"].lower() or q in g["mr"]]
    st.caption(f"{len(rows)} terms")
    cols = st.columns(2)
    for i, g in enumerate(rows):
        note = f" — *{g['note']}*" if g.get("note") else ""
        cols[i % 2].markdown(f"**{g['mr']}** · {g['en']}{note}")

with t_about:
    slide = ROOT / "demo" / "architecture_slide.html"
    if slide.exists():
        components.html(slide.read_text(encoding="utf-8"), height=560, scrolling=False)
    st.markdown(
        """
**ClauseGuard** (Problem 1: MAHA-GR-ALIGN) reviews a draft Maharashtra Government Resolution against a corpus of
real GRs (archival copies via the Wayback Machine — the live portal returned 503 during
the hackathon window).

**Honest evaluation**: fine-tuned macro-F1 0.9134 (0.8957 on the leak-free subset) vs a
protocol-matched lexical baseline (0.7754) and zero-shot Llama-70B (0.6521). We also
blind-checked our own labels (~26% noise found in the synthetic C/S classes) and report
accuracy against adjudicated truth — see `EVAL_TABLE.md` and `DATASET_CARD.md`.

Built for VJTI AI Hackathon 2026 · Problem 1 · "Shaping Digital Governance" · MIT license.
        """
    )
