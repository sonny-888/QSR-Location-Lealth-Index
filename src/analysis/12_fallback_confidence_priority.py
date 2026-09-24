"""Stage 12 - Fallback hierarchy + composite confidence score.

Four-level fallback, visible at every level (no silent imputation with
arbitrary values):
  1. Full LHI            - all four pillars have real evidence
  2. Reduced LHI          - Momentum pillar missing (insufficient trajectory
                            evidence per stage 6's minimum-review-count rule);
                            LHI recomputed on the remaining three pillars with
                            re-normalized weights
  3. Peer-adjusted estimate - CX evidence is Low AND Momentum is missing;
                            LHI leans on Peer + Engagement only
  4. Insufficient Data    - fewer than 5 total loaded reviews (the existing
                            pipeline's own minimum-volume cutoff); score is
                            still computed but flagged unreliable, not hidden

LHI_CONFIDENCE is a broader composite than stage 11's CX-only evidence flag:
review volume, aspect coverage, momentum-evidence availability, peer-tier
quality, and business-attribute completeness, each contributing a 0-1
sub-score, averaged and banded to Low/Medium/High.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, log, percentile_rank

PEER_TIER_QUALITY = {
    "TIER_1_LOCAL_10MI": 1.0, "TIER_2_CITY_SEGMENT": 0.7,
    "TIER_3_STATE_SEGMENT": 0.4, "TIER_4_GLOBAL_SEGMENT": 0.2,
}
MIN_REVIEWS_FOR_ANY_SCORE = 5


def fallback_level(row) -> str:
    if row["LOADED_REVIEW_COUNT"] < MIN_REVIEWS_FOR_ANY_SCORE:
        return "4_Insufficient_Data"
    if row["CX_EVIDENCE_CONFIDENCE"] == "Low" and pd.isna(row["PILLAR_MOMENTUM"]):
        return "3_Peer_Adjusted_Estimate"
    if pd.isna(row["PILLAR_MOMENTUM"]):
        return "2_Reduced_LHI"
    return "1_Full_LHI"


def recompute_for_fallback(df: pd.DataFrame) -> pd.Series:
    """Re-derive the reported LHI at each fallback level using only the
    pillars that level trusts, re-normalizing weights rather than silently
    zero-filling a missing pillar."""
    w0 = {"PEER": 0.30, "ENGAGEMENT": 0.25, "MOMENTUM": 0.25, "CX": 0.20}
    out = df["LHI_FINAL"].copy()

    reduced_mask = df["FALLBACK_LEVEL"] == "2_Reduced_LHI"
    remaining = {"PEER": w0["PEER"], "ENGAGEMENT": w0["ENGAGEMENT"], "CX": w0["CX"]}
    total = sum(remaining.values())
    remaining = {k: v / total for k, v in remaining.items()}
    out.loc[reduced_mask] = (
        remaining["PEER"] * df.loc[reduced_mask, "PILLAR_PEER"] +
        remaining["ENGAGEMENT"] * df.loc[reduced_mask, "PILLAR_ENGAGEMENT"] +
        remaining["CX"] * df.loc[reduced_mask, "PILLAR_CX"]
    )

    peer_adj_mask = df["FALLBACK_LEVEL"] == "3_Peer_Adjusted_Estimate"
    out.loc[peer_adj_mask] = (
        0.6 * df.loc[peer_adj_mask, "PILLAR_PEER"] + 0.4 * df.loc[peer_adj_mask, "PILLAR_ENGAGEMENT"]
    )

    return out


def composite_confidence(df: pd.DataFrame, aspect_summary: pd.DataFrame) -> pd.DataFrame:
    coverage = aspect_summary.groupby("BUSINESS_ID")["ASPECT_COVERAGE_PCT"].mean().rename("MEAN_ASPECT_COVERAGE")
    df = df.merge(coverage, on="BUSINESS_ID", how="left")

    review_volume_score = percentile_rank(df["LOADED_REVIEW_COUNT"]) / 100
    aspect_coverage_score = (df["MEAN_ASPECT_COVERAGE"].fillna(0) / 100).clip(0, 1)
    momentum_evidence_score = (df["RATING_TRAJECTORY"] != "Insufficient Evidence").astype(float)
    peer_tier_score = df["PEER_TIER"].map(PEER_TIER_QUALITY).fillna(0.2)
    completeness_score = 1 - df[["PILLAR_PEER", "PILLAR_ENGAGEMENT", "PILLAR_MOMENTUM", "PILLAR_CX"]].isna().mean(axis=1)

    composite = (review_volume_score + aspect_coverage_score + momentum_evidence_score +
                 peer_tier_score + completeness_score) / 5 * 100

    band = pd.cut(composite, bins=[-1, 40, 70, 101], labels=["Low", "Medium", "High"])
    df["DATA_QUALITY_SCORE"] = composite.round(1)
    df["LHI_CONFIDENCE"] = band
    return df


def main():
    drivers = pd.read_csv(OUTPUT_DIR / "QSR_DRIVERS.csv")
    peer_groups = pd.read_csv(OUTPUT_DIR / "QSR_PEER_GROUPS.csv")
    aspect_summary = pd.read_csv(OUTPUT_DIR / "QSR_ASPECT_BUSINESS_SUMMARY.csv")
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", usecols=["BUSINESS_ID", "LOADED_REVIEW_COUNT"])

    df = drivers.merge(biz, on="BUSINESS_ID", how="left").merge(
        peer_groups[["BUSINESS_ID", "PEER_TIER", "PEER_GROUP_SIZE"]], on="BUSINESS_ID", how="left"
    )

    df["FALLBACK_LEVEL"] = df.apply(fallback_level, axis=1)
    df["LHI_REPORTED"] = recompute_for_fallback(df)
    df = composite_confidence(df, aspect_summary)

    log(f"Fallback level distribution: {df['FALLBACK_LEVEL'].value_counts().to_dict()}")
    log(f"LHI confidence distribution: {df['LHI_CONFIDENCE'].value_counts().to_dict()}")

    df.to_csv(OUTPUT_DIR / "QSR_FALLBACK_CONFIDENCE.csv", index=False)
    log("Stage 12 complete.")


if __name__ == "__main__":
    main()
