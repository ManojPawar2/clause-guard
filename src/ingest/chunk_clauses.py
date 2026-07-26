"""Split GR body text into clause-level chunks for embedding + conflict screening."""
import re

# GR bodies are organised as numbered operative clauses ("1.", "2)", "(iii)", "अ)"),
# section headings (Read/Preamble/Government Resolution), and paragraphs.
CLAUSE_START = re.compile(r"^\s*(?:\(?\d{1,2}[.)]|\(?[ivxIVX]{1,4}\)|\(?[a-hA-H][.)])\s+")
SECTION_RE = re.compile(
    r"^\s*(Read|Reference|Preamble|Government\s+Resolution|Resolution|Order)\s*[:\-]",
    re.IGNORECASE,
)
MIN_CHARS = 80
MAX_CHARS = 1200


def chunk(text: str) -> list[str]:
    """Return clause-ish chunks: numbered clauses kept whole, long paras split."""
    lines = text.splitlines()
    blocks, cur = [], []

    def flush():
        if cur:
            b = re.sub(r"\s+", " ", " ".join(cur)).strip()
            if len(b) >= MIN_CHARS:
                blocks.append(b)
            cur.clear()

    for ln in lines:
        if CLAUSE_START.match(ln) or SECTION_RE.match(ln) or not ln.strip():
            flush()
        if ln.strip():
            cur.append(ln.strip())
    flush()

    # split oversized blocks on sentence boundaries
    out = []
    for b in blocks:
        while len(b) > MAX_CHARS:
            cut = b.rfind(". ", 0, MAX_CHARS)
            if cut < MIN_CHARS:
                cut = MAX_CHARS
            out.append(b[: cut + 1].strip())
            b = b[cut + 1 :].strip()
        if len(b) >= MIN_CHARS:
            out.append(b)
    return out
