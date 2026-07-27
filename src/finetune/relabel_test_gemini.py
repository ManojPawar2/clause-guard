"""Clean the test-set labels with a cross-family relabeler (Gemini).

Phase 1 — VALIDATE: Gemini judges the 50 blind-check pairs; agreement vs the
adjudicated-truth labels must be >= 0.80 or the script aborts (a relabeler
worse than that would add noise, not remove it).

Phase 2 — RELABEL: Gemini judges the 446 ollama-generated test pairs (the
deterministic numswap/truncation/mined pairs keep their construction-correct
labels). Writes data/test_labels_cleaned.json.

Phase 3 — SCORE: fine-tuned MuRIL macro-F1 against the cleaned labels
(Gemini-unjudged pairs excluded, count reported). Writes
results/metrics_cleaned_test.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "finetune"))
from eval_zeroshot import judge  # noqa: E402

LETTER = {"C": "contradiction", "S": "consistent", "N": "neutral"}
VALIDATION_GATE = 0.80


def load_rows():
    return [json.loads(l) for l in (ROOT / "data" / "pairs_test.jsonl")
            .read_text(encoding="utf-8").splitlines()]


def truth_pairs():
    key = json.loads((ROOT / "data" / "blind_check_key.json").read_text(encoding="utf-8"))
    adj = {a["n"]: a["label"] for a in json.loads(
        (ROOT / "data" / "blind_check_adjudication.json").read_text(
            encoding="utf-8"))["adjudications"]}
    test = {r["id"]: r for r in load_rows() if "id" in r}
    pairs, truth = [], []
    for k in key:
        pairs.append(test[k["id"]])
        truth.append(adj.get(k["n"], k["label"]))
    return pairs, truth


def main():
    # Phase 1: validate the relabeler
    pairs, truth = truth_pairs()
    print("=== phase 1: validating Gemini vs adjudicated truth (50 pairs)", flush=True)
    preds = judge("gemini", pairs, sleep=6.5)
    judged = [(p, t) for p, t in zip(preds, truth) if p]
    agree = sum(p == t for p, t in judged) / max(1, len(judged))
    print(f"validation: agreement {agree:.4f} on {len(judged)}/50 judged", flush=True)
    if agree < VALIDATION_GATE or len(judged) < 40:
        print(f"ABORT: below gate ({VALIDATION_GATE}) or too few judged", flush=True)
        return

    # Phase 2: relabel the LLM-generated test pairs
    rows = load_rows()
    llm_rows = [r for r in rows if r.get("generator", "").startswith("ollama")]
    print(f"=== phase 2: relabeling {len(llm_rows)} ollama-generated test pairs", flush=True)
    relabels = judge("gemini", llm_rows, sleep=6.5)
    relabel_by_id = {r["id"]: p for r, p in zip(llm_rows, relabels) if p}
    cleaned = {}
    for r in rows:
        if r.get("generator", "").startswith("ollama"):
            if r["id"] in relabel_by_id:
                cleaned[r["id"]] = relabel_by_id[r["id"]]
        else:
            cleaned[r["id"]] = r["label"]  # construction-correct classes
    (ROOT / "data" / "test_labels_cleaned.json").write_text(
        json.dumps(cleaned, indent=1), encoding="utf-8")
    changed = sum(1 for r in rows if r["id"] in cleaned and cleaned[r["id"]] != r["label"])
    print(f"cleaned labels: {len(cleaned)}/{len(rows)} pairs, {changed} changed", flush=True)

    # Phase 3: score MuRIL against cleaned labels
    print("=== phase 3: scoring MuRIL vs cleaned labels", flush=True)
    import torch
    from sklearn.metrics import classification_report, f1_score
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    model_dir = str(ROOT / "model" / "muril_gr_conflict_fp16")
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, torch_dtype=torch.float32)
    model.eval()
    id2label = model.config.id2label
    scored = [r for r in rows if r["id"] in cleaned]
    mpreds = []
    with torch.no_grad():
        for s in range(0, len(scored), 16):
            b = scored[s:s + 16]
            enc = tok([r["premise"] for r in b], [r["hypothesis"] for r in b],
                      truncation=True, max_length=256, padding=True, return_tensors="pt")
            mpreds += [id2label[i] for i in model(**enc).logits.argmax(-1).tolist()]
    y = [cleaned[r["id"]] for r in scored]
    y_orig = [r["label"] for r in scored]
    out = {
        "relabeler_validation_agreement": round(agree, 4),
        "n_scored": len(scored), "n_test": len(rows),
        "n_labels_changed": changed,
        "macro_f1_vs_cleaned": round(f1_score(y, mpreds, average="macro"), 4),
        "macro_f1_vs_original_same_subset": round(
            f1_score(y_orig, mpreds, average="macro"), 4),
        "original_vs_cleaned_agreement": round(
            sum(a == b for a, b in zip(y, y_orig)) / len(y), 4),
        "report_vs_cleaned": classification_report(y, mpreds, output_dict=True,
                                                   zero_division=0),
        "protocol": "cleaned = Gemini relabels for ollama-generated pairs "
                    "(relabeler validated vs blind-adjudicated truth), "
                    "construction labels for numswap/truncation/mined pairs",
    }
    (ROOT / "results" / "metrics_cleaned_test.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("relabeler_validation_agreement",
                                          "macro_f1_vs_cleaned",
                                          "macro_f1_vs_original_same_subset",
                                          "n_labels_changed")}, indent=2), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
