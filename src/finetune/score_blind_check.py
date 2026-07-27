"""Score the human blind check against the dataset labels.

Reads data/blind_check_answers.json (human C/S/N/? letters, in pair order) and
data/blind_check_key.json (dataset labels for the same 50 pairs), writes
results/metrics_blind_check.json with overall + per-label agreement and the
full disagreement list.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LETTER = {"C": "contradiction", "S": "consistent", "N": "neutral"}


def main():
    key = json.loads((ROOT / "data" / "blind_check_key.json").read_text(encoding="utf-8"))
    ans = json.loads((ROOT / "data" / "blind_check_answers.json").read_text(encoding="utf-8"))
    letters = ans["answers"]
    assert len(letters) == len(key), f"{len(letters)} answers vs {len(key)} key entries"

    judged, agree = 0, 0
    per_label = {}
    disagreements = []
    unjudgeable = 0
    for k, letter in zip(key, letters):
        if letter == "?":
            unjudgeable += 1
            continue
        human = LETTER[letter]
        judged += 1
        d = per_label.setdefault(k["label"], {"n": 0, "agree": 0})
        d["n"] += 1
        if human == k["label"]:
            agree += 1
            d["agree"] += 1
        else:
            disagreements.append({"n": k["n"], "dataset_label": k["label"],
                                  "human_label": human, "generator": k["generator"],
                                  "min_readability": k["min_readability"]})

    out = {
        "n_pairs": len(key), "n_judged": judged, "n_unjudgeable": unjudgeable,
        "agreement": round(agree / judged, 4) if judged else None,
        "per_label": {lab: {"n": d["n"], "agreement": round(d["agree"] / d["n"], 4)}
                      for lab, d in per_label.items()},
        "disagreements": disagreements,
        "protocol": "50 stratified test pairs from the readable subset "
                    "(make_blind_check.py); human blind to labels; '?' counted "
                    "separately, never guessed",
    }
    (ROOT / "results" / "metrics_blind_check.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
