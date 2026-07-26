"""Download archived GR PDFs from the Wayback Machine.

The live portal (gr.maharashtra.gov.in) is down (503), so we pull PDFs from
web.archive.org using a pre-enumerated CDX listing (data/cdx_english.txt,
lines of "<original-url> <wayback-timestamp>").

Modes:
  sample --per-code N --codes 01,19,...   download N most-recent PDFs per trailing
                                          2-digit code into data/raw_pdfs/sample/
  bulk   --codes 07,19 --max N            download up to N most-recent PDFs whose
                                          filename ends with one of the codes into
                                          data/raw_pdfs/

Resumable: existing non-empty files are skipped. Rate-limited (~1 req / 1.2 s),
with exponential backoff on 429/5xx.
"""
import argparse
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CDX_FILE = ROOT / "data" / "cdx_english.txt"
UA = "MAHA-GR-ALIGN hackathon corpus builder (contact: student project)"
FNAME_RE = re.compile(r"English/((20\d{6})\d{8}(\d{2}))\.pdf$")


def load_listing():
    """Return list of (code, year, dept2, url, ts), newest GR-date first."""
    rows = []
    for line in CDX_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        url, ts = parts
        m = FNAME_RE.search(url)
        if not m:
            continue  # skip odd/legacy filenames (short codes etc.)
        code, ymd, dept2 = m.group(1), m.group(2), m.group(3)
        rows.append((code, int(ymd[:4]), dept2, url, ts))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


def fetch(url, ts, dest, session, max_tries=4):
    wb = f"https://web.archive.org/web/{ts}id_/{url}"
    delay = 3.0
    for attempt in range(1, max_tries + 1):
        try:
            r = session.get(wb, timeout=60)
            if r.status_code == 200 and r.content[:5] == b"%PDF-":
                dest.write_bytes(r.content)
                return "ok"
            if r.status_code in (404, 403):
                return f"gone({r.status_code})"
            # 429/5xx or non-PDF body: back off and retry
        except requests.RequestException as e:
            if attempt == max_tries:
                return f"err({type(e).__name__})"
        time.sleep(delay)
        delay *= 2
    return "failed"


def run(targets, out_dir, label, workers=1):
    out_dir.mkdir(parents=True, exist_ok=True)
    ok = skip = bad = 0
    t0 = time.time()

    todo = []
    for code, _year, _dept2, url, ts in targets:
        dest = out_dir / f"{code}.pdf"
        if dest.exists() and dest.stat().st_size > 1024:
            skip += 1
        else:
            todo.append((code, url, ts, dest))

    if workers <= 1:
        session = requests.Session()
        session.headers["User-Agent"] = UA
        for i, (code, url, ts, dest) in enumerate(todo, 1):
            status = fetch(url, ts, dest, session)
            if status == "ok":
                ok += 1
            else:
                bad += 1
                print(f"  MISS {code}: {status}", flush=True)
            if i % 25 == 0:
                el = time.time() - t0
                print(f"[{label}] {i}/{len(todo)} ok={ok} skip={skip} miss={bad} ({el:.0f}s)",
                      flush=True)
            time.sleep(1.2)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        local = threading.local()

        def worker(item):
            code, url, ts, dest = item
            if not hasattr(local, "s"):
                local.s = requests.Session()
                local.s.headers["User-Agent"] = UA
            time.sleep(0.15)
            return code, fetch(url, ts, dest, local.s, max_tries=3)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(worker, it) for it in todo]
            for i, fut in enumerate(as_completed(futs), 1):
                code, status = fut.result()
                if status == "ok":
                    ok += 1
                else:
                    bad += 1
                    print(f"  MISS {code}: {status}", flush=True)
                if i % 25 == 0:
                    el = time.time() - t0
                    rate = i / max(el, 1)
                    eta = (len(todo) - i) / max(rate, 0.01) / 60
                    print(f"[{label}] {i}/{len(todo)} ok={ok} skip={skip} miss={bad} "
                          f"({el:.0f}s, {rate:.1f}/s, eta {eta:.0f}m)", flush=True)
    print(f"[{label}] DONE ok={ok} skip={skip} miss={bad}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sample", "bulk"])
    ap.add_argument("--codes", default="", help="comma-separated trailing 2-digit codes")
    ap.add_argument("--per-code", type=int, default=2)
    ap.add_argument("--max", type=int, default=600)
    ap.add_argument("--min-year", type=int, default=2019)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    rows = [r for r in load_listing() if r[1] >= args.min_year]
    print(f"listing: {len(rows)} usable rows (>= {args.min_year})", flush=True)

    if args.mode == "sample":
        wanted = args.codes.split(",") if args.codes else None
        by_code = defaultdict(list)
        for r in rows:
            by_code[r[2]].append(r)
        targets = []
        for c, lst in sorted(by_code.items()):
            if wanted and c not in wanted:
                continue
            targets.extend(lst[: args.per_code])
        run(targets, ROOT / "data" / "raw_pdfs" / "sample", "sample")
    else:
        codes = set(args.codes.split(","))
        cand = [r for r in rows if r[2] in codes]
        # newest first, but keep some spread: take newest max*1.0
        targets = cand[: args.max]
        print(f"bulk: {len(cand)} candidates for codes {sorted(codes)}, downloading {len(targets)}", flush=True)
        run(targets, ROOT / "data" / "raw_pdfs", "bulk")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
