"""Fetch ClauseGuard's heavy runtime artifacts when they are absent.

Free app hosts can't carry a 475 MB fine-tuned model or a 112 MB vector index
inside a git repo, so they live on the Hugging Face Hub (public — no token
needed to download) and stream in on the host's first boot:

  model    samay-rajput/clauseguard-muril  -> model/muril_gr_conflict_fp16/
  dataset  samay-rajput/clauseguard-index  -> chroma_db/ + cache/llm/

The dataset also carries the warmed LLM disk cache, so the four demo
scenarios run without spending any provider quota on the deployed host.
A local dev checkout already has everything on disk -> instant no-op.
"""
import os
from pathlib import Path

# hub progress bars use tqdm's class-level lock from worker threads, which
# newer tqdm releases dropped ("type object 'tqdm' has no attribute '_lock'")
# - and a Streamlit script run has no terminal to draw on anyway.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

ROOT = Path(__file__).resolve().parents[2]

MODEL_REPO = "samay-rajput/clauseguard-muril"
DATA_REPO = "samay-rajput/clauseguard-index"

_CHECKS = {
    "muril model": (ROOT / "model" / "muril_gr_conflict_fp16" / "model.safetensors"),
    "vector index": (ROOT / "chroma_db" / "chroma.sqlite3"),
}


def artifacts_missing() -> list:
    """Names of artifacts not present on this host."""
    return [name for name, marker in _CHECKS.items() if not marker.exists()]


def ensure_artifacts() -> list:
    """Download whatever is missing; returns the names fetched. No-op when
    everything is already on disk (the local-dev case)."""
    missing = artifacts_missing()
    if not missing:
        return []
    from huggingface_hub import snapshot_download

    if "muril model" in missing:
        snapshot_download(MODEL_REPO,
                          local_dir=ROOT / "model" / "muril_gr_conflict_fp16")
    if "vector index" in missing:
        snapshot_download(DATA_REPO, repo_type="dataset", local_dir=ROOT,
                          allow_patterns=["chroma_db/**", "cache/llm/**"])
    return missing


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    missing = artifacts_missing()
    print("missing:", missing or "nothing — all artifacts on disk")
    if missing:
        print("fetched:", ensure_artifacts())
