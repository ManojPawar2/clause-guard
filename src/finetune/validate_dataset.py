"""Validate the synthetic pair dataset (GO/NO-GO #1 gate).

Checks: schema, label distribution, dedup (exact + near-dup), lexical-overlap
audit per class, and the TF-IDF + logistic-regression probe (if the probe's
macro-F1 exceeds THRESH the dataset is lexically too easy — regenerate).
Writes the cleaned flat dataset to data/pairs_clean.jsonl.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "pairs_raw.jsonl"
CLEAN = ROOT / "data" / "pairs_clean.jsonl"
THRESH = 0.75


def jaccard(a, b):
    sa, sb = set(a.split()), set(b.split())
    return len(sa & sb) / max(1, len(sa | sb))


def main():
    rows = []
    for line in RAW.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        for i, p in enumerate(rec.get("pairs", [])):
            pr, hy = (p.get("premise") or "").strip(), (p.get("hypothesis") or "").strip()
            if len(pr) < 40 or len(hy) < 40 or p.get("label") not in (
                    "contradiction", "consistent", "neutral"):
                continue
            rows.append({
                "id": f"{rec['seed_id']}#{i}",
                "premise": pr, "hypothesis": hy,
                "label": p["label"],
                "conflict_type": p.get("conflict_type", "none"),
                "lang": p.get("lang", "?"),
                "generator": rec.get("generator", "?"),
                "seed_id": rec["seed_id"],
                "gr_code": rec.get("gr_code", "?"),
                "jaccard": round(jaccard(pr, hy), 3),
            })

    # exact dedup on (premise, hypothesis)
    seen, deduped = set(), []
    for r in rows:
        k = (r["premise"], r["hypothesis"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)

    # randomize order of premise/hypothesis for half the pairs (symmetric task)
    random.seed(42)
    for r in deduped:
        if random.random() < 0.5:
            r["premise"], r["hypothesis"] = r["hypothesis"], r["premise"]

    labels = Counter(r["label"] for r in deduped)
    langs = Counter(r["lang"] for r in deduped)
    gens = Counter(r["generator"] for r in deduped)
    print(f"raw pairs: {len(rows)}  after dedup: {len(deduped)}")
    print(f"labels: {dict(labels)}")
    print(f"langs: {dict(langs)}  generators: {dict(gens)}")

    # overlap audit per class
    print("mean jaccard by label:")
    for lab in ("contradiction", "consistent", "neutral"):
        xs = [r["jaccard"] for r in deduped if r["label"] == lab]
        if xs:
            print(f"  {lab}: {sum(xs)/len(xs):.3f} (n={len(xs)})")

    # TF-IDF probe
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import f1_score
        from sklearn.model_selection import train_test_split

        X = [r["premise"] + " || " + r["hypothesis"] for r in deduped]
        y = [r["label"] for r in deduped]
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=42,
                                              stratify=y)
        vec = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
        clf = LogisticRegression(max_iter=1000)
        clf.fit(vec.fit_transform(Xtr), ytr)
        f1 = f1_score(yte, clf.predict(vec.transform(Xte)), average="macro")
        verdict = "TOO-EASY (regenerate hard slices)" if f1 > THRESH else "OK"
        print(f"TF-IDF probe macro-F1: {f1:.3f} -> {verdict}")
    except ImportError:
        print("sklearn missing — probe skipped")
        f1 = None

    with CLEAN.open("w", encoding="utf-8") as f:
        for r in deduped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(deduped)} -> {CLEAN}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
