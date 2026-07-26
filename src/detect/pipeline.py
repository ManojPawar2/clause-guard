"""Conflict-detection pipeline: retrieve -> screen (Groq, batched) -> explain (Gemini).

Conflict definition is deliberately NARROW (per plan): numeric/amount changes,
date/deadline changes, eligibility reversals, authority/procedure changes,
scope changes. Subtle legal interpretation is out of scope.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "llm"))
sys.path.append(str(ROOT / "src" / "index"))
sys.path.append(str(ROOT / "src" / "ingest"))

from clients import llm, llm_with_fallback, LLMError  # noqa: E402
from build_index import retrieve  # noqa: E402
from chunk_clauses import chunk  # noqa: E402

# e5-small cosine distances compress to ~[0.10, 0.25] on this index: related
# clauses measure <=0.16, off-topic >=0.18 (calibrated live). 0.18 is the cut.
MAX_COSINE_DISTANCE = 0.18

# Boilerplate present in every GR (availability line, signature formula,
# distribution list, digital-signature note). These retrieve each other across
# unrelated GRs and produce junk "conflicts" — never screen them.
BOILERPLATE_RE = re.compile(
    r"maharashtra\.gov\.in|सांके\s*तांक|संके\s*तस्थळ|digitally sign|साक्षां\s*कित"
    r"|by order and in the name|राज्यपालांच्या आदेशानुसार"
    r"|^\s*(?:प्रत|प्रति|copy to)\s*[:,\-]|unique code",
    re.IGNORECASE,
)


def is_boilerplate(clause: str) -> bool:
    return bool(BOILERPLATE_RE.search(clause))

SCREEN_PROMPT = """You are screening clauses of a DRAFT Maharashtra Government Resolution (GR) against clauses from EXISTING GRs for conflicts.

A CONFLICT means the two clauses cannot both be in force for the same beneficiaries/institutions, specifically:
- different numeric amounts/percentages/limits for the same benefit or fee
- different dates/deadlines/durations for the same scheme or process
- eligibility reversal (one includes a group/condition the other excludes)
- different sanctioning authority or procedure for the same action
- different coverage/scope (districts, categories, institution types) for the same scheme

NOT a conflict: paraphrase, one elaborating the other, different schemes/subjects entirely, or clauses about unrelated matters (label these consistent or neutral).

For each numbered pair below, output a JSON object: {{"results": [{{"pair": <n>, "label": "conflict"|"consistent"|"neutral", "reason": "<one sentence>"}}]}}
Output ONLY the JSON.

{pairs}"""

# The screener sometimes states an exclusion rule in its own reason and then
# flags anyway ("introduces a new benefit not covered by..."). Catch the
# self-reported exclusions in code and downgrade without wasting a verify call.
SELF_EXCLUDED_REASON_RE = re.compile(
    r"new benefit|not covered|not present in|not mentioned in|introduces a new"
    r"|different URL|unique code|file number",
    re.IGNORECASE,
)

# Extraction beats judgment for small models: instead of asking "is this a
# contradiction?", ask for each clause's value for the shared benefit and
# compare the values in code.
VERIFY_PROMPT = """Two clauses from Maharashtra Government Resolutions were flagged as possibly conflicting. Extract facts — do not judge.

CLAUSE 1 (draft): {draft}

CLAUSE 2 (existing): {existing}

1. same_scheme: Do BOTH clauses govern the SAME specific scheme/benefit for the SAME beneficiary group? (A different scholarship, a different stipend scheme, a different year's one-time sanction, or a merely similar topic = false.)
2. benefit: In 3-8 words, what shared benefit/rule do they both address (empty string if none)?
3. value1: What amount/percentage/date/authority/condition does CLAUSE 1 state or presuppose for that benefit? Quote it briefly (e.g. "50 टक्के", "Rs. 2,000", "31 March 2025"). Empty string if none.
4. value2: Same for CLAUSE 2 (e.g. "100 टक्के"). A value counts even if presupposed ("students entitled to 100% reimbursement" -> "100 टक्के"). Empty string if none.

Output ONLY JSON: {{"same_scheme": true|false, "benefit": "...", "value1": "...", "value2": "..."}}"""


def _values_conflict(v1: str, v2: str) -> bool:
    """Compare extracted values in code: different digit-content = conflict."""
    d1 = re.findall(r"[0-9०-९]+(?:[.,][0-9०-९]+)?", v1 or "")
    d2 = re.findall(r"[0-9०-९]+(?:[.,][0-9०-९]+)?", v2 or "")
    tr = str.maketrans("०१२३४५६७८९", "0123456789")
    n1 = {x.translate(tr).replace(",", "") for x in d1}
    n2 = {x.translate(tr).replace(",", "") for x in d2}
    if n1 and n2:
        return n1 != n2
    # non-numeric values (authority/procedure): require textual disagreement
    a, b = (v1 or "").strip().lower(), (v2 or "").strip().lower()
    return bool(a and b and a != b and a not in b and b not in a)

EXPLAIN_PROMPT = """A draft Maharashtra Government Resolution contains a clause that conflicts with an existing GR. Explain the conflict precisely for a government drafting officer.

DRAFT CLAUSE:
{draft}

EXISTING GR CLAUSE (from {gr_label}):
{existing}

Screening reason: {reason}

Write 3-5 sentences: (1) state the specific contradiction (quote the conflicting values/terms), (2) name the existing GR it conflicts with, (3) recommend what the drafter should do (align the value, explicitly supersede the old GR, or narrow the scope). Be concrete and cite the GR identifiers given."""


def screen_pairs(pairs, batch_size=5, provider="groq"):
    """pairs: list of dicts {draft, candidate, meta}. Returns verdicts aligned to input."""
    verdicts = [None] * len(pairs)
    for s in range(0, len(pairs), batch_size):
        batch = pairs[s:s + batch_size]
        listing = []
        for i, p in enumerate(batch, 1):
            listing.append(
                f"PAIR {i}\nDRAFT: {p['draft'][:700]}\nEXISTING ({p['meta'].get('gr_code','?')}): "
                f"{p['candidate'][:700]}\n"
            )
        prompt = SCREEN_PROMPT.format(pairs="\n".join(listing))
        try:
            raw = llm_with_fallback(prompt, preferred=provider, temperature=0.0,
                                    max_tokens=2048, json_mode=True)
            data = json.loads(_json_slice(raw))
            for item in data.get("results", []):
                idx = s + int(item.get("pair", 0)) - 1
                if s <= idx < s + len(batch):  # in-batch only; stray ids dropped
                    lab = str(item.get("label", "neutral")).lower()
                    if lab not in ("conflict", "consistent", "neutral"):
                        lab = "neutral"
                    verdicts[idx] = {"label": lab, "reason": item.get("reason", "")}
        except (LLMError, json.JSONDecodeError, ValueError) as e:
            for i in range(s, min(s + batch_size, len(pairs))):
                verdicts[i] = {"label": "error", "reason": f"screening failed: {e}"}
    for i, v in enumerate(verdicts):
        if v is None:
            verdicts[i] = {"label": "neutral", "reason": "no verdict returned"}
    return verdicts


def _json_slice(text):
    """Tolerate markdown fences / stray prose around the JSON object."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return m.group(0) if m else text


def explain_conflict(draft, existing, meta, reason):
    gn = meta.get("gr_number")
    gr_id = gn if gn and gn != "?" else meta.get("gr_code", "?")
    label = f"{meta.get('department','?')} GR {gr_id} dated {meta.get('date','?')}"
    prompt = EXPLAIN_PROMPT.format(draft=draft[:900], existing=existing[:900],
                                   gr_label=label, reason=reason)
    return llm_with_fallback(prompt, preferred="gemini", temperature=0.2, max_tokens=1024)


def review_draft(draft_text: str, top_k=6, max_draft_clauses=25, progress=None):
    """Full pipeline for the app. Returns dict with clauses, pairs, verdicts, conflicts."""
    clauses = chunk(draft_text)[:max_draft_clauses]
    pairs = []
    for ci, cl in enumerate(clauses):
        if is_boilerplate(cl):
            continue
        if progress:
            progress(f"retrieving candidates for clause {ci + 1}/{len(clauses)}")
        for cand in retrieve(cl, k=top_k):
            if cand["distance"] > MAX_COSINE_DISTANCE:
                continue
            if is_boilerplate(cand["clause"]):
                continue
            pairs.append({"draft": cl, "draft_idx": ci,
                          "candidate": cand["clause"], "meta": cand})
    # One reliable stage instead of two flaky ones: extraction-verify EVERY pair.
    # (Batched judgment screening proved unstable on the local 8B — verdicts
    # flipped with batch composition. Fact extraction is stable; the conflict
    # decision itself is made in code by comparing the extracted values.)
    verdicts = []
    conflicts = []
    for i, p in enumerate(pairs):
        if progress:
            progress(f"extracting values for pair {i + 1}/{len(pairs)}")
        v = {"label": "neutral", "reason": ""}
        try:
            raw = llm_with_fallback(
                VERIFY_PROMPT.format(draft=p["draft"][:700], existing=p["candidate"][:700]),
                temperature=0.0, max_tokens=512, json_mode=True)
            chk = json.loads(_json_slice(raw))
            if chk.get("same_scheme") and _values_conflict(
                    chk.get("value1", ""), chk.get("value2", "")):
                v = {"label": "conflict",
                     "reason": f"For {chk.get('benefit') or 'the same benefit'}, "
                               f"the draft specifies '{chk.get('value1')}' but the "
                               f"existing GR specifies '{chk.get('value2')}'."}
        except (LLMError, json.JSONDecodeError, ValueError) as e:
            v = {"label": "error", "reason": f"verification failed: {e}"}
        verdicts.append(v)
        if v["label"] == "conflict":
            if progress:
                progress("explaining flagged conflict")
            expl = explain_conflict(p["draft"], p["candidate"], p["meta"], v["reason"])
            conflicts.append({**p, "reason": v["reason"], "explanation": expl})
    return {"n_clauses": len(clauses), "clauses": clauses, "n_pairs": len(pairs),
            "verdicts": verdicts, "pairs": pairs, "conflicts": conflicts}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    t = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else \
        "1. The fee reimbursement shall be 50% of tuition fees for EBC students."
    out = review_draft(t)
    print(f"clauses={out['n_clauses']} pairs={out['n_pairs']} conflicts={len(out['conflicts'])}")
    for c in out["conflicts"]:
        print("-", c["reason"])
