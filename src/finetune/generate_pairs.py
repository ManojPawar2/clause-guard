"""Generate the synthetic NLI pair dataset (contradiction / consistent / neutral)
grounded in real corpus clauses.

Anti-artifact measures (per plan):
- 50% of contradictions must be PARAPHRASED (low lexical overlap), 50% minimal-edit;
  consistent/neutral classes mirror that overlap spread so surface overlap cannot
  predict the label.
- Neutral pairs: half are hard negatives (same scheme vocabulary, unrelated obligations).
- Premise/hypothesis order randomized; dedup downstream in validate_dataset.py.

Runs unattended, resumable: appends to data/pairs_raw.jsonl after every response.
Rate limits respected by the client's backoff + a fixed inter-call sleep.
"""
import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "src" / "llm"))
from clients import llm, LLMError  # noqa: E402

OUT = ROOT / "data" / "pairs_raw.jsonl"

GEN_PROMPT = """You are creating a training dataset for detecting conflicts between clauses of Maharashtra Government Resolutions (GRs).

Below is a REAL seed clause from a GR. Generate {n} labeled clause PAIRS as JSON.

SEED CLAUSE (id {seed_id}):
{seed}

Produce this exact JSON shape:
{{"pairs": [{{"premise": "...", "hypothesis": "...", "label": "contradiction"|"consistent"|"neutral", "conflict_type": "amount"|"date"|"eligibility"|"authority"|"scope"|"none", "lang": "{lang}"}}]}}

Rules:
- premise = the seed clause (possibly lightly cleaned), or a close variant of it.
- For CONTRADICTION pairs ({n_contra} of them): hypothesis contradicts the premise on exactly ONE of: numeric amount/percentage ("amount"), date/deadline/duration ("date"), eligibility criterion reversed ("eligibility"), sanctioning authority/procedure ("authority"), coverage/scope ("scope"). Vary which one. IMPORTANT: for about half of these, fully REPHRASE the hypothesis (different sentence structure and synonyms) so it does not lexically mirror the premise; for the other half make a minimal edit.
- For CONSISTENT pairs ({n_cons} of them): hypothesis is a faithful paraphrase, a subset restatement, or a consistent elaboration — at least one must be a heavy paraphrase with low word overlap.
- For NEUTRAL pairs ({n_neut} of them): hypothesis is about a DIFFERENT scheme/topic with no logical relation; at least one must reuse similar government vocabulary (hard negative) while remaining unrelated.
- Language: write both premise and hypothesis in {lang_full}.
- Keep every clause between 25 and 90 words, realistic GR drafting style.
Output ONLY the JSON."""


def load_seed_clauses(min_len=120, max_len=900):
    corpus = ROOT / "data" / "corpus.jsonl"
    seeds = []
    with open(corpus, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            for i, c in enumerate(r["clauses"]):
                if min_len <= len(c) <= max_len:
                    seeds.append({"seed_id": f"{r['gr_code']}:{i}", "text": c,
                                  "gr_code": r["gr_code"]})
    return seeds


def already_done():
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["seed_id"])
            except Exception:
                pass
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-pairs", type=int, default=3600)
    ap.add_argument("--per-seed", type=int, default=9)
    ap.add_argument("--provider", default="gemini", choices=["gemini", "groq"])
    ap.add_argument("--mr-frac", type=float, default=0.35,
                    help="fraction of seeds generated in Marathi")
    ap.add_argument("--sleep", type=float, default=6.5)
    args = ap.parse_args()

    seeds = load_seed_clauses()
    random.seed(42)
    random.shuffle(seeds)
    done = already_done()
    print(f"{len(seeds)} seed clauses, {len(done)} already generated", flush=True)

    n_written = sum(1 for _ in OUT.open(encoding="utf-8")) if OUT.exists() else 0
    total_pairs = n_written * 0  # informational only; recount below
    total_pairs = 0
    if OUT.exists():
        for line in OUT.open(encoding="utf-8"):
            try:
                total_pairs += len(json.loads(line)["pairs"])
            except Exception:
                pass

    n_contra = max(3, round(args.per_seed * 0.35))
    n_cons = max(3, round(args.per_seed * 0.35))
    n_neut = args.per_seed - n_contra - n_cons

    with OUT.open("a", encoding="utf-8") as out:
        for s in seeds:
            if total_pairs >= args.target_pairs:
                break
            if s["seed_id"] in done:
                continue
            lang = "mr" if random.random() < args.mr_frac else "en"
            lang_full = "Marathi (Devanagari)" if lang == "mr" else "English"
            prompt = GEN_PROMPT.format(n=args.per_seed, n_contra=n_contra,
                                       n_cons=n_cons, n_neut=n_neut,
                                       seed=s["text"][:1200], seed_id=s["seed_id"],
                                       lang=lang, lang_full=lang_full)
            try:
                raw = llm(prompt, provider=args.provider, temperature=0.7,
                          max_tokens=4096, json_mode=True, use_cache=False)
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                data = json.loads(m.group(0) if m else raw)
                pairs = [p for p in data.get("pairs", [])
                         if p.get("premise") and p.get("hypothesis")
                         and p.get("label") in ("contradiction", "consistent", "neutral")]
                if pairs:
                    out.write(json.dumps({"seed_id": s["seed_id"],
                                          "gr_code": s["gr_code"],
                                          "generator": args.provider,
                                          "pairs": pairs}, ensure_ascii=False) + "\n")
                    out.flush()
                    total_pairs += len(pairs)
                    print(f"{s['seed_id']}: +{len(pairs)} (total {total_pairs})", flush=True)
            except (LLMError, json.JSONDecodeError, ValueError) as e:
                print(f"{s['seed_id']}: SKIP ({str(e)[:120]})", flush=True)
            time.sleep(args.sleep)
    print(f"DONE: {total_pairs} pairs in {OUT}", flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
