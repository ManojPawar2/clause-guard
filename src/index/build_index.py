"""Build the Chroma retrieval index over corpus clauses.

Embeddings: intfloat/multilingual-e5-small (CPU-fast, multilingual).
E5 convention: documents are embedded with "passage: " prefix, queries with
"query: " (handled in retrieve()).
"""
import json
import sys
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
DB_DIR = str(ROOT / "chroma_db")
MODEL_NAME = "intfloat/multilingual-e5-small"
COLLECTION = "gr_clauses"

_model = None


def model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def client():
    return chromadb.PersistentClient(path=DB_DIR)


def default_corpus_path():
    for name in ("corpus_clean.jsonl", "corpus.jsonl"):
        p = ROOT / "data" / name
        if p.exists():
            return p
    return ROOT / "data" / "corpus.jsonl"


def build(corpus_path=None, max_clauses_per_gr=60):
    corpus_path = corpus_path or default_corpus_path()
    cl = client()
    try:
        cl.delete_collection(COLLECTION)
    except Exception:
        pass
    col = cl.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    ids, docs, metas = [], [], []
    with open(corpus_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            for i, clause in enumerate(r["clauses"][:max_clauses_per_gr]):
                ids.append(f"{r['gr_code']}:{i}")
                docs.append(clause)
                metas.append({
                    "gr_code": r["gr_code"],
                    "department": r.get("department") or "?",
                    "date": r.get("date") or "?",
                    "subject": (r.get("subject") or "?")[:200],
                    "gr_number": r.get("gr_number") or "?",
                })
    print(f"embedding {len(docs)} clauses...", flush=True)
    m = model()
    B = 128
    for s in range(0, len(docs), B):
        embs = m.encode([f"passage: {d}" for d in docs[s:s + B]],
                        normalize_embeddings=True, show_progress_bar=False)
        col.add(ids=ids[s:s + B], documents=docs[s:s + B],
                metadatas=metas[s:s + B], embeddings=embs.tolist())
        if (s // B) % 5 == 0:
            print(f"  {s + len(embs)}/{len(docs)}", flush=True)
    print(f"index built: {col.count()} clauses -> {DB_DIR}", flush=True)


def retrieve(query_text: str, k=5, exclude_gr=None):
    col = client().get_collection(COLLECTION)
    emb = model().encode([f"query: {query_text}"], normalize_embeddings=True)
    res = col.query(query_embeddings=emb.tolist(), n_results=min(k + 5, 25))
    out = []
    for i in range(len(res["ids"][0])):
        meta = res["metadatas"][0][i]
        if exclude_gr and meta["gr_code"] == exclude_gr:
            continue
        out.append({
            "clause": res["documents"][0][i],
            "distance": res["distances"][0][i],
            **meta,
        })
        if len(out) >= k:
            break
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
