"""Reference tracking: extract citations from a draft, link them to the corpus,
flag stale (superseded) references, and suggest related GRs to cite.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "ingest"))
from extract_metadata import extract_citations  # noqa: E402


def load_corpus(path=None):
    path = path or ROOT / "data" / "corpus.jsonl"
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            recs.append(json.loads(line))
    return recs


def _norm_ref(s: str) -> str:
    """Normalise a formal GR reference string for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"\b(government|resolution|circular|no|dated|dt)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def analyze_references(draft_text: str, corpus: list) -> dict:
    """Return citations found in the draft, matched corpus GRs, and stale flags."""
    cites = extract_citations(draft_text)
    by_code = {r["gr_code"]: r for r in corpus}
    by_grno = {}
    for r in corpus:
        if r.get("gr_number"):
            by_grno[_norm_ref(r["gr_number"])] = r

    linked, unknown = [], []
    for code in cites["cited_codes"]:
        if code in by_code:
            linked.append({"cited": code, "match": by_code[code], "via": "unique-code"})
        else:
            unknown.append(code)
    for ref in cites["cited_refs"]:
        n = _norm_ref(ref)
        hit = None
        for k, r in by_grno.items():
            if k and (k in n or n in k):
                hit = r
                break
        if hit:
            linked.append({"cited": ref, "match": hit, "via": "gr-number"})
        else:
            unknown.append(ref)

    # Stale check: a linked GR is 'superseded' if any LATER corpus GR cites it
    # AND contains supersession language near that citation (cheap heuristic:
    # later GR cites it and uses supersede/cancel/revise wording anywhere).
    stale = []
    superseders = {}
    for entry in linked:
        m = entry["match"]
        code = m["gr_code"]
        for r in corpus:
            if r["gr_code"] <= code:  # codes start with YYYYMMDD → sortable by date
                continue
            cited_here = code in r.get("cited_codes", [])
            if not cited_here and m.get("gr_number"):
                cited_here = any(
                    _norm_ref(m["gr_number"]) == _norm_ref(x) for x in r.get("cited_refs", [])
                )
            if cited_here:
                blob = " ".join(r.get("clauses", []))[:20000].lower()
                if re.search(r"supersed|cancel|repeal|in place of|revis|अधिक्रमित|रद्द", blob):
                    stale.append({"cited": entry["cited"], "superseded_by": r["gr_code"],
                                  "successor_subject": r.get("subject")})
                    superseders[code] = r["gr_code"]
                    break

    return {"linked": linked, "unknown": unknown, "stale": stale,
            "n_citations": len(cites["cited_codes"]) + len(cites["cited_refs"])}


def build_citation_graph(corpus: list) -> list:
    """Edges (citing_code -> cited_code) within the corpus, for the graph view."""
    codes = {r["gr_code"] for r in corpus}
    edges = []
    for r in corpus:
        for c in r.get("cited_codes", []):
            if c in codes and c != r["gr_code"]:
                edges.append((r["gr_code"], c))
    return edges
