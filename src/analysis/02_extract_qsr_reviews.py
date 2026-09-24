"""Stage 2 - Extract QSR-relevant reviews from the 11GB REVIEWS_CLEANED.csv.

REVIEWS_CLEANED.csv holds the full Yelp review corpus (all businesses, not
just QSR) and carries a RAW_JSON column with pretty-printed, multi-line JSON,
so naive line-counting tools (wc -l) miscount rows. We stream it in chunks
with pandas' real CSV parser (which handles embedded newlines inside quoted
fields correctly), keep only rows whose BUSINESS_ID is in the QSR population,
drop the columns we don't need (RAW_JSON, RAW_RECORD_HASH, JSON_VALUE_TYPE),
and write a much smaller parquet file everything downstream reads instead.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, require, log

KEEP_COLS = ["REVIEW_ID", "USER_ID", "BUSINESS_ID", "STARS", "USEFUL_VOTES",
             "FUNNY_VOTES", "COOL_VOTES", "REVIEW_TEXT", "REVIEW_TS", "IS_VALID_RECORD"]

CHUNKSIZE = 200_000


def main():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", usecols=["BUSINESS_ID"])
    qsr_ids = set(biz["BUSINESS_ID"])
    log(f"QSR population: {len(qsr_ids)} business IDs")

    src = ROOT / "REVIEWS_CLEANED.csv"
    require(src.exists(), f"Missing source file: {src}")

    t0 = time.time()
    chunks = []
    n_scanned = 0
    reader = pd.read_csv(src, usecols=KEEP_COLS, chunksize=CHUNKSIZE, low_memory=False)
    for i, chunk in enumerate(reader):
        n_scanned += len(chunk)
        matched = chunk[chunk["BUSINESS_ID"].isin(qsr_ids)]
        if len(matched):
            chunks.append(matched)
        if (i + 1) % 25 == 0:
            elapsed = time.time() - t0
            log(f"...scanned {n_scanned:,} rows in {elapsed:.0f}s, "
                f"kept {sum(len(c) for c in chunks):,} so far")

    log(f"Finished scanning {n_scanned:,} rows in {time.time() - t0:.0f}s")
    df = pd.concat(chunks, ignore_index=True)
    log(f"Matched {len(df):,} QSR-relevant review rows")

    n_invalid = int((df["IS_VALID_RECORD"] == False).sum())  # noqa: E712
    df = df[df["IS_VALID_RECORD"] != False]  # noqa: E712
    log(f"Dropped {n_invalid} rows flagged IS_VALID_RECORD=False")

    dup_mask = df.duplicated(subset=["REVIEW_TEXT", "BUSINESS_ID"], keep="first") & df["REVIEW_TEXT"].notna()
    df["IS_EXACT_TEXT_DUPLICATE"] = dup_mask
    log(f"Flagged {int(dup_mask.sum())} exact-duplicate review-text rows (kept, flagged not dropped)")

    dup_review_id = int(df.duplicated(subset=["REVIEW_ID"]).sum())
    require(dup_review_id == 0, f"REVIEW_ID is not unique after extraction: {dup_review_id} duplicates")

    match_rate = df["BUSINESS_ID"].nunique() / len(qsr_ids)
    log(f"{df['BUSINESS_ID'].nunique()} / {len(qsr_ids)} QSR businesses ({match_rate:.2%}) have at least one review")

    out = OUTPUT_DIR / "qsr_reviews_detail.parquet"
    df.to_parquet(out, index=False)
    log(f"Wrote {out} ({len(df):,} rows, {out.stat().st_size / 1e6:.1f} MB)")
    log("Stage 2 complete.")


if __name__ == "__main__":
    main()
