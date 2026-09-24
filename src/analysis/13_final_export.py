"""Stage 13 - Final export.

Assembles the analytical dataset a dashboard (Phase 2) would consume.
Raw review text stays in qsr_reviews_detail.parquet / QSR_ROOT_CAUSE_EVIDENCE
and is never joined into this table.

Two disclosed simplifications, stated here rather than silently:
  - LHI_CHANGE is a proxy from the rating-trajectory star delta, not a
    re-computed prior-period LHI (that would require rebuilding the whole
    pillar pipeline on a historical snapshot, out of scope for this pass).
  - TOP_NEGATIVE_THEME is reported at aspect granularity (e.g. "Waiting
    Time"), not fine-grained phrase mining ("long queues," "slow orders");
    QSR_ROOT_CAUSE_EVIDENCE.csv carries the raw snippets for manual reading.

EMERGING_ISSUE and OPERATIONAL_PROFILE_DAYS_WITH_HOURS are new: EMERGING_ISSUE
is the recent-negative-spike flag (stage 6), reported separately from
TRAJECTORY on purpose -- it answers a different question ("did something
break in the last 60 days") than the 12-month trend does, and folding the two
together would hide exactly the case it exists to catch.
OPERATIONAL_PROFILE_DAYS_WITH_HOURS is exported as context, not scored into
LHI -- stage 10's evidence gate found it predictive of the IS_OPEN proxy but
conceptually a listing-completeness signal, not a direct measurement of
outlet health (see QSR_OPERATIONAL_PROFILE_EVIDENCE_GATE.csv).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, MODEL_VERSION, PIPELINE_RUN_DATE, require, log, risk_band


def main():
    fb = pd.read_csv(OUTPUT_DIR / "QSR_FALLBACK_CONFIDENCE.csv")
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    peer_bench = pd.read_csv(ROOT / "QSR_BUSINESS_PEER_BENCHMARKS.csv",
                              usecols=["BUSINESS_ID", "STAR_GAP_VS_PEERS", "PEER_RATING_PERCENTILE"])
    cx_aspect = pd.read_csv(OUTPUT_DIR / "QSR_CX_ASPECT_SCORES.csv")
    cx_pillar = pd.read_csv(OUTPUT_DIR / "QSR_CX_PILLAR.csv", usecols=["BUSINESS_ID", "TOTAL_ASPECT_MENTIONS"])
    trajectory = pd.read_csv(OUTPUT_DIR / "QSR_TRAJECTORY_FINAL.csv")

    aspect_pivot = cx_aspect.pivot_table(index="BUSINESS_ID", columns="ASPECT",
                                          values="ABSOLUTE_SCORE_0_100").reset_index()
    aspect_pivot = aspect_pivot.rename(columns={a: f"{a}_SENTIMENT" for a in aspect_pivot.columns if a != "BUSINESS_ID"})

    df = fb.merge(biz[["BUSINESS_ID", "BUSINESS_NAME", "CITY", "STATE"]], on="BUSINESS_ID", how="left") \
           .merge(peer_bench, on="BUSINESS_ID", how="left") \
           .merge(aspect_pivot, on="BUSINESS_ID", how="left") \
           .merge(trajectory[["BUSINESS_ID", "RECENT_REVIEW_COUNT", "PRIOR_REVIEW_COUNT"]], on="BUSINESS_ID", how="left") \
           .merge(cx_pillar, on="BUSINESS_ID", how="left")

    df["RISK_CATEGORY"] = risk_band(df["LHI_REPORTED"])
    df["LHI_CHANGE"] = df["RATING_DELTA"]
    df["TOP_NEGATIVE_THEME"] = df["TOP_NEGATIVE_ASPECT"]
    df["ABSA_EVIDENCE_COUNT"] = df["TOTAL_ASPECT_MENTIONS"]
    df["MODEL_VERSION"] = MODEL_VERSION
    df["PIPELINE_RUN_DATE"] = PIPELINE_RUN_DATE
    df["LHI"] = df["LHI_REPORTED"]
    df["LHI_VERSION"] = df["LHI_VERSION_SELECTED"]
    df["PILLAR_PERFORMANCE"] = df["PILLAR_PEER"]
    df["TRAJECTORY"] = df["RATING_TRAJECTORY"]
    df["TRAJECTORY_MAGNITUDE"] = df["RATING_DELTA"]

    final_cols = [
        "BUSINESS_ID", "BUSINESS_NAME", "CITY", "STATE",
        "PEER_TIER", "PEER_GROUP_SIZE",
        "LHI", "LHI_VERSION",
        "PILLAR_CX", "PILLAR_ENGAGEMENT", "PILLAR_PERFORMANCE", "PILLAR_MOMENTUM",
        "LHI_CHANGE", "TRAJECTORY", "TRAJECTORY_MAGNITUDE",
        "RISK_CATEGORY", "INTERVENTION_PRIORITY",
        "LHI_CONFIDENCE", "DATA_QUALITY_SCORE", "FALLBACK_LEVEL",
        "TOP_POSITIVE_DRIVER", "TOP_NEGATIVE_DRIVER",
        "TOP_NEGATIVE_ASPECT", "TOP_NEGATIVE_THEME",
        "FOOD_SENTIMENT", "SERVICE_SENTIMENT", "STAFF_SENTIMENT",
        "CLEANLINESS_SENTIMENT", "WAITING_TIME_SENTIMENT", "ORDER_ACCURACY_SENTIMENT", "VALUE_SENTIMENT",
        "PEER_RATING_PERCENTILE", "STAR_GAP_VS_PEERS",
        "RECENCY_WEIGHTED_STARS", "RECENT_MEAN_STARS", "PRIOR_MEAN_STARS", "EMERGING_ISSUE",
        "OPERATIONAL_PROFILE_DAYS_WITH_HOURS",
        "SHAP_TOP_DRIVER_1", "SHAP_TOP_DRIVER_2", "SHAP_TOP_DRIVER_3",
        "ABSA_EVIDENCE_COUNT", "RECENT_REVIEW_COUNT", "PRIOR_REVIEW_COUNT",
        "MODEL_VERSION", "PIPELINE_RUN_DATE",
    ]
    missing = [c for c in final_cols if c not in df.columns]
    require(not missing, f"Final export missing expected columns: {missing}")

    out = df[final_cols].rename(columns={"STAR_GAP_VS_PEERS": "STAR_GAP_TO_PEERS"})
    out.to_csv(OUTPUT_DIR / "QSR_FINAL_LHI_DATA.csv", index=False)

    log(f"Final export: {len(out)} rows x {len(out.columns)} columns -> QSR_FINAL_LHI_DATA.csv")
    log(f"Risk category distribution: {out['RISK_CATEGORY'].value_counts().to_dict()}")
    log(f"Intervention priority distribution: {out['INTERVENTION_PRIORITY'].value_counts().to_dict()}")

    check = out[(out["LHI"] >= 70) & (out["TRAJECTORY"] == "Deteriorating")]
    log(f"Verification: {len(check)} businesses with LHI>=70 but Deteriorating trajectory retained "
        f"in the export with their real intervention priority (not silently marked healthy).")

    log("Stage 13 complete. Pipeline finished.")


if __name__ == "__main__":
    main()
