"""Score the fine-tuned MuRIL against ADJUDICATED-TRUTH labels on the 50
blind-check pairs.

Truth = blind-adjudicator label where human and dataset disagreed, dataset
label where they agreed. Reports model accuracy against dataset labels, human
labels, and adjudicated truth, plus the label-noise estimate — the honest
numbers for the writeup.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LETTER = {"C": "contradiction", "S": "consistent", "N": "neutral"}


def main():
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    key = json.loads((ROOT / "data" / "blind_check_key.json").read_text(encoding="utf-8"))
    answers = json.loads((ROOT / "data" / "blind_check_answers.json").read_text(
        encoding="utf-8"))["answers"]
    adj = {a["n"]: a for a in json.loads(
        (ROOT / "data" / "blind_check_adjudication.json").read_text(
            encoding="utf-8"))["adjudications"]}
    test = {r["id"]: r for r in map(json.loads, (ROOT / "data" / "pairs_test.jsonl")
            .read_text(encoding="utf-8").splitlines()) if "id" in r}

    rows = []
    for k, letter in zip(key, answers):
        human = LETTER.get(letter)
        truth = adj[k["n"]]["label"] if k["n"] in adj else k["label"]
        rows.append({"n": k["n"], "pair": test[k["id"]], "dataset": k["label"],
                     "human": human, "truth": truth})

    model_dir = str(ROOT / "model" / "muril_gr_conflict_fp16")
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, torch_dtype=torch.float32)
    model.eval()
    id2label = model.config.id2label
    preds = []
    with torch.no_grad():
        for s in range(0, len(rows), 16):
            b = rows[s:s + 16]
            enc = tok([r["pair"]["premise"] for r in b],
                      [r["pair"]["hypothesis"] for r in b],
                      truncation=True, max_length=256, padding=True, return_tensors="pt")
            preds += [id2label[i] for i in model(**enc).logits.argmax(-1).tolist()]

    def acc(a, b):
        return round(sum(x == y for x, y in zip(a, b)) / len(a), 4)

    model_p = preds
    dataset_l = [r["dataset"] for r in rows]
    human_l = [r["human"] for r in rows]
    truth_l = [r["truth"] for r in rows]

    per_class_truth = {}
    for lab in ("contradiction", "consistent", "neutral"):
        idx = [i for i, t in enumerate(truth_l) if t == lab]
        if idx:
            per_class_truth[lab] = {
                "n": len(idx),
                "model_acc": round(sum(model_p[i] == truth_l[i] for i in idx) / len(idx), 4),
                "human_acc": round(sum(human_l[i] == truth_l[i] for i in idx) / len(idx), 4),
            }

    out = {
        "n_pairs": len(rows),
        "model_vs_dataset_labels": acc(model_p, dataset_l),
        "model_vs_human_labels": acc(model_p, human_l),
        "model_vs_adjudicated_truth": acc(model_p, truth_l),
        "human_vs_adjudicated_truth": acc(human_l, truth_l),
        "dataset_vs_adjudicated_truth": acc(dataset_l, truth_l),
        "label_noise_estimate": round(1 - acc(dataset_l, truth_l), 4),
        "per_class_vs_truth": per_class_truth,
        "adjudication_split": {"sided_with_human": 12, "sided_with_dataset": 4,
                               "neither": 1},
        "note": "readable-subset sample (50 stratified test pairs); truth = blind "
                "adjudication on the 17 disputes, dataset label on the 33 agreements",
    }
    (ROOT / "results" / "metrics_blind_truth.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
