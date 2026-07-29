"""Bilingual terminology check against the controlled glossary (SRS FR-8 / FR-9).

Deterministic and LLM-free — same contract as `scorecard.py`, so it is demo-safe
and can never be knocked out by an API quota.

Two kinds of flag:

* **variant** — the draft uses a non-approved form of a term that IS in the
  glossary (`अपंग` for `दिव्यांग`, `Govt. Resolution` for `Government Resolution`,
  `लेखाशिर्ष` for `लेखाशीर्ष`). The approved form is suggested (FR-9).
* **language-mix** — a predominantly-Marathi GR uses the English term (or a
  predominantly-English draft uses the Marathi one) where an approved
  counterpart exists and is itself absent from the document.

Language-mix is deliberately restricted to MULTI-WORD terms: single-word
entries ("Mantralaya", "MahaDBT", "Governor", "College") are proper nouns or
words that appear legitimately in either language, and flagging them produces
noise rather than a drafting correction.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GLOSSARY_FILE = ROOT / "data" / "glossary.json"

# Reuse the Devanagari tokeniser the corpus-quality scorer already uses.
sys.path.append(str(ROOT / "src" / "ingest"))
from quality import DEV_WORD  # noqa: E402

LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
CONTEXT = 55


def load_glossary(path=None) -> list:
    return json.loads(Path(path or GLOSSARY_FILE).read_text(encoding="utf-8"))


def primary_language(text: str) -> str:
    """'mr' or 'en' — whichever script carries the document."""
    return "mr" if len(DEV_WORD.findall(text)) >= len(LATIN_WORD.findall(text)) else "en"


def _surface_forms(en: str) -> list:
    """'Grant / Subsidy' -> ['Grant', 'Subsidy']; 'Minority (community)' -> ['Minority']."""
    base = re.sub(r"\([^)]*\)", " ", en or "")
    return [p.strip() for p in base.split("/") if p.strip()]


def _find(text: str, term: str):
    """Locate `term` in `text`. Latin terms match on word boundaries, Devanagari
    on substring (Devanagari has no \\b, and Marathi inflects by suffixing)."""
    if not term:
        return None
    if LATIN_WORD.search(term):
        m = re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text, re.IGNORECASE)
    else:
        m = re.search(re.escape(term), text)
    return m


def _context(text: str, m) -> str:
    s = text[max(0, m.start() - CONTEXT): m.end() + CONTEXT]
    return re.sub(r"\s+", " ", s).strip()


def check_terminology(draft_text: str, glossary=None) -> dict:
    """Return {primary_lang, n_flags, flags[]} for a draft GR."""
    gloss = glossary if glossary is not None else load_glossary()
    lang = primary_language(draft_text)
    flags, seen = [], set()

    for entry in gloss:
        mr, en = entry.get("mr", ""), entry.get("en", "")

        # FR-9: a non-approved variant is in use -> suggest the standard term.
        for variant in entry.get("variants", []):
            m = _find(draft_text, variant)
            if m and (key := ("variant", variant.lower())) not in seen:
                seen.add(key)
                flags.append({
                    "kind": "variant",
                    "found": draft_text[m.start():m.end()],
                    "approved_mr": mr,
                    "approved_en": en,
                    "note": entry.get("note", ""),
                    "context": _context(draft_text, m),
                })

        # FR-8: wrong-language term where the approved counterpart is absent.
        wrong, approved = (_surface_forms(en), mr) if lang == "mr" else ([mr], en)
        for form in wrong:
            if len(form.split()) < 2:      # single words are too noisy — see docstring
                continue
            m = _find(draft_text, form)
            if not m or _find(draft_text, approved):
                continue
            if (key := ("language-mix", form.lower())) in seen:
                continue
            seen.add(key)
            flags.append({
                "kind": "language-mix",
                "found": draft_text[m.start():m.end()],
                "approved_mr": mr,
                "approved_en": en,
                "note": entry.get("note", ""),
                "context": _context(draft_text, m),
            })

    return {"primary_lang": lang, "n_flags": len(flags), "flags": flags}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    text = src.read_text(encoding="utf-8") if src else (
        "Proposal for a Govt. Resolution covering handicapped students."
    )
    res = check_terminology(text)
    print(f"language={res['primary_lang']}  flags={res['n_flags']}")
    for f in res["flags"]:
        arrow = f["approved_mr"] if res["primary_lang"] == "mr" else f["approved_en"]
        print(f"  [{f['kind']}] '{f['found']}' -> use '{arrow}'")
        print(f"      …{f['context']}…")
