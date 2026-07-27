"""Protocol-matched lexical baseline: TF-IDF + LogReg fit on pairs_train,
scored on pairs_test — the SAME held-out set every other eval-table row uses.

(validate_dataset.py's 0.788 probe is a random-split dataset AUDIT over all
pairs — a different, easier protocol; it stays in the dataset card as the
artifact gate, not in the eval table.)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    p = ROOT / "data" / f"pairs_{name}.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]


def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report, f1_score

    tr, te = load("train"), load("test")
    to_x = lambda rows: [r["premise"] + " || " + r["hypothesis"] for r in rows]  # noqa: E731
    vec = TfidfVectorizer(max_features=50000, ngram_range=(1, 2), sublinear_tf=True)
    xtr = vec.fit_transform(to_x(tr))
    xte = vec.transform(to_x(te))
    clf = LogisticRegression(max_iter=2000).fit(xtr, [r["label"] for r in tr])
    pred = clf.predict(xte)
    y = [r["label"] for r in te]

    out = {
        "macro_f1": round(f1_score(y, pred, average="macro"), 4),
        "n_train": len(tr), "n_test": len(y),
        "protocol": "fit on pairs_train, scored on pairs_test (protocol-matched "
                    "with all other eval-table rows)",
        "config": "TfidfVectorizer(max_features=50000, ngram_range=(1,2), "
                  "sublinear_tf=True) + LogisticRegression(max_iter=2000)",
        "report": classification_report(y, pred, output_dict=True, zero_division=0),
    }
    (ROOT / "results" / "metrics_tfidf_baseline.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(f"tfidf baseline (train->test): macro-F1 {out['macro_f1']} on {len(y)} pairs")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
