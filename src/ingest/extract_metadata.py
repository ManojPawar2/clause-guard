"""Header/metadata extraction from English Maharashtra GR first-page text."""
import re

DEPT_RE = re.compile(
    r"^\s*([A-Z][A-Za-z,&.'\- ]*?Department)\s*[,.]?\s*$", re.MULTILINE
)
GRNO_RE = re.compile(
    r"(?:Government\s+(?:Resolution|Circular|Order)|Corrigendum|Resolution)"
    r"\s*No\.?\s*[:\-]?\s*([^\n]{4,90})",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"Date[d]?\s*[:\-. ]*\s*(\d{1,2}\s*(?:st|nd|rd|th)?\s+[A-Za-z]+[,.]?\s+\d{4})",
    re.IGNORECASE,
)
DATE_NUM_RE = re.compile(r"Date[d]?\s*[:\-. ]*\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})", re.IGNORECASE)
# 18-digit unique GR codes (used for citation linking + supersession checks)
UNIQUE_CODE_RE = re.compile(r"\b(20\d{16})\b")
# Formal GR reference strings cited in "Read"/body, e.g.
#   "Government Resolution No. NGC-2024/C.R.100/TE-4, dated 14th August 2024"
REF_RE = re.compile(
    r"((?:Government\s+(?:Resolution|Circular)|G\.R\.)\s*No\.?[^\n,]{0,80}"
    r"(?:,?\s*(?:dated|dt\.?)\s*[^\n,;)]{4,30})?)",
    re.IGNORECASE,
)
# Marathi form: "शासन निर्णय क्र.शिष्यवृ-2024/प्र.क्र.105/तासशि-4, दि.08.07.2024"
# (क्रमांक/क्र + a slash-separated file number, optional दि./दिनांक date tail)
REF_MR_RE = re.compile(
    r"((?:शासन\s*(?:निर्णय|परिपत्रक)|परिपत्रक|निर्णय)\s*"
    r"(?:क्रमांक|क्र)\.?\s*[:\-ः]?\s*[^\s,][^\n,]{4,70}"
    r"(?:,?\s*(?:दि|दिनांक)\.?\s*[^\n,;)]{4,25})?)"
)


def parse_header(text: str) -> dict:
    """Best-effort metadata from first-page text of an English GR."""
    dept = None
    m = DEPT_RE.search(text)
    if m:
        dept = re.sub(r"\s+", " ", m.group(1)).strip()

    grno = None
    m = GRNO_RE.search(text)
    if m:
        grno = m.group(1).strip().rstrip(",.")

    date = None
    m = DATE_RE.search(text) or DATE_NUM_RE.search(text)
    if m:
        date = re.sub(r"\s+", " ", m.group(1)).strip()

    # Subject: everything before "Government of Maharashtra" is usually the
    # subject block; fall back to an explicit "Subject:" line.
    subject = None
    gom = re.search(r"Government\s+of\s+Maharashtra", text, re.IGNORECASE)
    if gom and gom.start() > 10:
        block = text[: gom.start()].strip()
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if lines:
            subject = re.sub(r"\s+", " ", " ".join(lines[:4]))[:300]
    if not subject:
        m = re.search(r"Sub(?:ject)?\s*[:\-]\s*([^\n]+(?:\n[^\n]+)?)", text, re.IGNORECASE)
        if m:
            subject = re.sub(r"\s+", " ", m.group(1)).strip()[:300]

    return {"department": dept, "gr_number": grno, "date": date, "subject": subject}


# Garble-tolerant fallback. Archived GR PDFs use legacy Devanagari fonts with
# broken ToUnicode CMaps, so the anchor words the patterns above rely on extract
# corrupted and font-specifically (निर्णय -> मनणणय / वनणणय / शनणणय / रिणणय ...).
# Digits and punctuation survive that corruption intact — the same property the
# corpus repair step's digit audit is built on — so this pattern keys on the
# STRUCTURE of a Maharashtra GR file number instead of on any word:
#   <prefix>-<year> / प्र.क्र.<serial> / <section>   e.g. "उमाशा-2020/प्र.क्र.13/एसएम-4"
# `प्र` survives nearly every font (प्र.क्र., प्र.ि., प्र.क्र), so it anchors the
# middle segment while the surrounding tokens are allowed to be arbitrary garble.
REF_MR_GARBLED_RE = re.compile(
    r"([^\s,;:]{0,25}[०-९0-9]{4}\s*/\s*प्र[^\s/]{0,6}\s*[०-९0-9]{1,4}\s*/\s*[^\s,;:\n]{1,20}"
    r"(?:\s*,?\s*[^\s]{0,4}\.?\s*[०-९0-9]{1,2}[./][०-९0-9]{1,2}[./][०-९0-9]{2,4})?)"
)


def extract_citations(text: str) -> dict:
    codes = sorted(set(UNIQUE_CODE_RE.findall(text)))
    refs, spans = [], []
    # Word-anchored patterns first; the garbled fallback only fills the gaps it
    # leaves, and never re-reports a fragment of a citation already captured.
    for rx in (REF_RE, REF_MR_RE, REF_MR_GARBLED_RE):
        for m in rx.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in spans):
                continue
            r = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",.")
            if len(r) > 15 and r not in refs:
                refs.append(r)
                spans.append((m.start(), m.end()))
    return {"cited_codes": codes, "cited_refs": refs[:40]}
