"""Local CPU inference for the fine-tuned MuRIL: verifies Colab metrics locally
and measures ms/pair (the measured basis of the latency/cost claim).

Usage: python src/finetune/eval_local_latency.py [model_dir]
Default model dir: model/muril_gr_conflict_fp16 (unzipped from Colab).
"""
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
TEST = ROOT / "data" / "pairs_test.jsonl"
RESULTS = ROOT / "results"


def main():
    model_dir = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "model" / "muril_gr_conflict_fp16")
    tok = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, torch_dtype=torch.float32)  # fp16 weights upcast for CPU
    model.eval()

    rows = [json.loads(l) for l in TEST.read_text(encoding="utf-8").splitlines()]
    id2label = model.config.id2label
    preds, y = [], []
    B = 16
    t0 = time.perf_counter()
    with torch.no_grad():
        for s in range(0, len(rows), B):
            batch = rows[s:s + B]
            enc = tok([r["premise"] for r in batch], [r["hypothesis"] for r in batch],
                      truncation=True, max_length=256, padding=True, return_tensors="pt")
            out = model(**enc).logits.argmax(-1).tolist()
            preds += [id2label[i] for i in out]
            y += [r["label"] for r in batch]
    dt = time.perf_counter() - t0

    from sklearn.metrics import classification_report, f1_score
    m = {
        "macro_f1_local": round(f1_score(y, preds, average="macro"), 4),
        "n_pairs": len(rows),
        "total_seconds": round(dt, 2),
        "ms_per_pair": round(1000 * dt / len(rows), 1),
        "pairs_per_second": round(len(rows) / dt, 1),
        "report": classification_report(y, preds, output_dict=True, zero_division=0),
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "metrics_local_cpu.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("macro_f1_local", "ms_per_pair", "pairs_per_second")},
                     indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
