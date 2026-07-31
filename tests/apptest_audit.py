"""FR-15 verification via streamlit.testing.v1.AppTest.

Two successive reviews with an edit between them must leave the audit trail
with 2 records, the second carrying a non-empty unified diff — and the app
must raise 0 exceptions. Conflict analysis is allowed to degrade (no Ollama /
no API needed): the trail records the run either way, which is the point.

Run:  python tests/apptest_audit.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src" / "audit"))
from trail import TRAIL_FILE, load_runs  # noqa: E402

from streamlit.testing.v1 import AppTest  # noqa: E402

DRAFT_V1 = """GOVERNMENT OF MAHARASHTRA
Higher and Technical Education Department
Government Resolution No.: TST-2026/C.R.1/TE-4
Date: 1 August, 2026

1. The fee reimbursement shall be 50% of tuition fees for EBC students.
"""
DRAFT_V2 = DRAFT_V1.replace("50%", "100%")


def run_review(draft_text: str):
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"),
                           default_timeout=900)
    at.run()
    assert not at.exception, f"exceptions on load: {[e.value for e in at.exception]}"
    at.text_area[0].set_value(draft_text)
    at.button[0].click()
    at.run()
    assert not at.exception, f"exceptions on review: {[e.value for e in at.exception]}"
    return at


def main():
    backup = None
    if TRAIL_FILE.exists():
        backup = TRAIL_FILE.read_bytes()
        TRAIL_FILE.unlink()
    try:
        run_review(DRAFT_V1)
        run_review(DRAFT_V2)
        runs = load_runs()
        assert len(runs) == 2, f"expected 2 trail records, got {len(runs)}"
        assert runs[0]["human_edit"] is None
        edit = runs[1]["human_edit"]
        assert edit and edit["diff"], "second record must carry a non-empty diff"
        assert "50%" in edit["diff"] and "100%" in edit["diff"], edit["diff"]
        assert runs[1]["deterministic"].get("compliance_pct") is not None
        print("APPTEST OK — 2 records, second has the 50%->100% diff, 0 exceptions")
    finally:
        TRAIL_FILE.unlink(missing_ok=True)   # leave a clean trail for the user
        if backup is not None:
            TRAIL_FILE.write_bytes(backup)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
