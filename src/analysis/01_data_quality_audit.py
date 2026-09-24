"""Stage 1 - Data quality audit.

Verifies grain, referential integrity, range validity, duplication, and
cardinality across every source table before anything downstream trusts them.
Mirrors the discipline of the existing Snowflake QSR_BUSINESS_FILTER_AUDIT /
validation SQL, but re-run locally and independently against the exported
CSVs, on the theory that a clean-looking table can still be wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, require, require_unique_key, log

pd.set_option("display.width", 160)


def load_sources():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    peer = pd.read_csv(ROOT / "QSR_BUSINESS_PEER_BENCHMARKS.csv", low_memory=False)
    review_m = pd.read_csv(ROOT / "REVIEW_QSR_METRICS.csv", low_memory=False)
    checkin_m = pd.read_csv(ROOT / "CHECKIN_QSR_METRICS.csv", low_memory=False)
    tip_m = pd.read_csv(ROOT / "TIPS_QSR_METRICS.csv", low_memory=False)
    return biz, peer, review_m, checkin_m, tip_m


def grain_and_referential_checks(biz, peer, review_m, checkin_m, tip_m) -> list[dict]:
    findings = []

    require_unique_key(biz, "BUSINESS_ID", "QSR_BUSINESS_ANALYSIS_READY")
    require_unique_key(peer, "BUSINESS_ID", "QSR_BUSINESS_PEER_BENCHMARKS")
    require_unique_key(review_m, "BUSINESS_ID", "REVIEW_QSR_METRICS")
    require_unique_key(checkin_m, "BUSINESS_ID", "CHECKIN_QSR_METRICS")
    require_unique_key(tip_m, "BUSINESS_ID", "TIPS_QSR_METRICS")

    biz_ids = set(biz["BUSINESS_ID"])
    peer_match = peer["BUSINESS_ID"].isin(biz_ids).mean()
    require(peer_match == 1.0, f"Peer benchmark table does not fully match business population: {peer_match:.4%}")

    findings.append({"CHECK": "business_grain_unique", "RESULT": "PASS", "DETAIL": f"{len(biz)} unique BUSINESS_ID"})
    findings.append({"CHECK": "peer_referential_integrity", "RESULT": "PASS", "DETAIL": f"{peer_match:.4%} match rate"})

    for name, tbl in [("review_metrics", review_m), ("checkin_metrics", checkin_m), ("tips_metrics", tip_m)]:
        match_rate = tbl["BUSINESS_ID"].isin(biz_ids).mean()
        coverage = tbl["BUSINESS_ID"].isin(biz_ids).sum() / len(biz)
        findings.append({
            "CHECK": f"{name}_referential_integrity", "RESULT": "PASS" if match_rate == 1.0 else "WARN",
            "DETAIL": f"{match_rate:.4%} of {name} rows map to a known business; covers {coverage:.2%} of the QSR population",
        })

    return findings


def range_checks(biz: pd.DataFrame) -> list[dict]:
    findings = []

    bad_stars = ~biz["BUSINESS_STARS"].between(1, 5)
    findings.append({"CHECK": "stars_in_range_1_5", "RESULT": "PASS" if bad_stars.sum() == 0 else "FAIL",
                      "DETAIL": f"{bad_stars.sum()} rows outside [1,5]"})

    bad_open = ~biz["IS_OPEN"].isin([0, 1])
    findings.append({"CHECK": "is_open_binary", "RESULT": "PASS" if bad_open.sum() == 0 else "FAIL",
                      "DETAIL": f"{bad_open.sum()} rows outside {{0,1}}"})

    bad_lat = ~biz["LATITUDE"].between(-90, 90)
    bad_lon = ~biz["LONGITUDE"].between(-180, 180)
    findings.append({"CHECK": "valid_lat_long", "RESULT": "PASS" if (bad_lat.sum() + bad_lon.sum()) == 0 else "FAIL",
                      "DETAIL": f"{bad_lat.sum()} bad lat, {bad_lon.sum()} bad lon"})

    negative_count_cols = [c for c in biz.columns if "COUNT" in c and biz[c].dtype != object]
    neg_hits = {c: int((biz[c] < 0).sum()) for c in negative_count_cols if (biz[c] < 0).any()}
    findings.append({"CHECK": "no_negative_counts", "RESULT": "PASS" if not neg_hits else "FAIL",
                      "DETAIL": str(neg_hits) if neg_hits else "none found"})

    # Epoch-zero sentinel timestamps: 1970-01-01 as a null-that-wasn't-nulled.
    ts_cols = [c for c in biz.columns if c.endswith("_TS")]
    epoch_hits = {}
    for c in ts_cols:
        parsed = pd.to_datetime(biz[c], errors="coerce")
        n_epoch = int((parsed == pd.Timestamp("1970-01-01")).sum())
        if n_epoch:
            epoch_hits[c] = n_epoch
    findings.append({"CHECK": "no_epoch_zero_timestamps", "RESULT": "PASS" if not epoch_hits else "WARN",
                      "DETAIL": str(epoch_hits) if epoch_hits else "none found"})

    return findings


def duplicate_and_cardinality_checks(biz: pd.DataFrame) -> list[dict]:
    findings = []

    exact_dupe_rows = int(biz.duplicated(subset=[c for c in biz.columns if c != "BUSINESS_ID"]).sum())
    findings.append({"CHECK": "exact_duplicate_rows_excl_id", "RESULT": "PASS" if exact_dupe_rows == 0 else "WARN",
                      "DETAIL": f"{exact_dupe_rows} rows identical apart from BUSINESS_ID"})

    dupe_name_addr = int(biz.duplicated(subset=["BUSINESS_NAME", "ADDRESS", "CITY", "STATE"]).sum())
    findings.append({"CHECK": "duplicate_name_address", "RESULT": "PASS" if dupe_name_addr == 0 else "WARN",
                      "DETAIL": f"{dupe_name_addr} rows share name+address+city+state with another row"})

    card = biz.nunique(dropna=False).sort_values()
    single_valued = card[card == 1].index.tolist()
    findings.append({"CHECK": "single_valued_columns", "RESULT": "INFO",
                      "DETAIL": f"{len(single_valued)} columns have only one distinct value: {single_valued}"})

    return findings


def missingness_profile(biz: pd.DataFrame) -> pd.DataFrame:
    miss = biz.isna().mean().sort_values(ascending=False) * 100
    return miss.rename("PCT_MISSING").reset_index().rename(columns={"index": "COLUMN"})


def main():
    log("Loading source tables...")
    biz, peer, review_m, checkin_m, tip_m = load_sources()

    findings = []
    findings += grain_and_referential_checks(biz, peer, review_m, checkin_m, tip_m)
    findings += range_checks(biz)
    findings += duplicate_and_cardinality_checks(biz)

    findings_df = pd.DataFrame(findings)
    miss_df = missingness_profile(biz)

    out = OUTPUT_DIR / "QSR_DATA_QUALITY.csv"
    findings_df.to_csv(out, index=False)
    miss_df.to_csv(OUTPUT_DIR / "QSR_MISSINGNESS_PROFILE.csv", index=False)

    n_fail = (findings_df["RESULT"] == "FAIL").sum()
    log(f"Wrote {out} ({len(findings_df)} checks, {n_fail} FAIL)")
    if n_fail:
        print(findings_df[findings_df["RESULT"] == "FAIL"].to_string(index=False))
    require(n_fail == 0, f"{n_fail} data-quality checks FAILED — see {out}")

    log("Stage 1 complete.")


if __name__ == "__main__":
    main()
