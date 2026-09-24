"""Stage 7 - Feature lineage + leakage/circularity gate.

Runs BEFORE any predictive modelling. Classifies every candidate feature by
source, whether it's time-dependent (recency/momentum-style), whether it's
derived from review text, whether it's used in the LHI itself (circularity
risk), and whether it's judged safe to feed a model that predicts IS_OPEN.
This generalizes the manually-verified leakage finding (92.7% of closed
businesses have zero reviews in the trailing 12 months vs 12.8% of open
ones) into a documented policy rather than an ad hoc exclusion list.

No real independent "location health" outcome exists in this dataset (no
sales, no dated closures, no audits) -- IS_OPEN with the leaky features
removed is the strongest defensible proxy available, and it is used in
stage 8 as one evidence source among several, not as ground truth.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, log

# Column-name patterns that flag a feature as time-dependent / recency-driven.
TIME_DEPENDENT_PATTERNS = [
    r"LAST_12M", r"PRIOR_12M", r"TREND", r"LAST_TS$", r"FIRST_TS$", r"CREATED_AT",
    r"^DATASET_MAX", r"^LAST_", r"^FIRST_",
]
REVIEW_DERIVED_PATTERNS = [
    r"REVIEW", r"CHECKIN", r"TIP", r"SENTIMENT", r"ASPECT",
]
# LHI component columns (already-aggregated pillar inputs) — using these to
# "predict" IS_OPEN and then claiming that validates the LHI would be
# circular scoring: the target and the predictor would share the same
# underlying construction.
LHI_COMPONENT_PATTERNS = [
    r"^STAR_GAP", r"^PEER_RATING_PERCENTILE", r"^REVIEW_VOLUME_INDEX",
    r"^LOCAL_QSR_", r"^BENCHMARK_TIER",
]

NON_FEATURE_COLS = {
    "BUSINESS_ID", "BUSINESS_NAME", "ADDRESS", "CITY", "STATE", "POSTAL_CODE",
    "CATEGORIES", "QSR_CATEGORY_MATCHES", "ATTRIBUTES_RAW", "HOURS_RAW", "QSR_SEGMENT",
    "IS_OPEN",
}


def classify_column(col: str) -> dict:
    time_dep = any(re.search(p, col) for p in TIME_DEPENDENT_PATTERNS)
    review_derived = any(re.search(p, col) for p in REVIEW_DERIVED_PATTERNS)
    lhi_component = any(re.search(p, col) for p in LHI_COMPONENT_PATTERNS)

    if time_dep:
        reason = "Name pattern indicates a rolling/recency window or a first/last activity timestamp -- " \
                 "closed businesses trivially go to zero/stale on these, verified empirically for REVIEWS_LAST_12M."
        safe = False
    elif lhi_component:
        reason = "Directly feeds an LHI pillar -- using it to \"predict\" IS_OPEN and then citing that as " \
                 "validation of the LHI would be circular."
        safe = False
    else:
        reason = "Static/structural attribute or a whole-history aggregate (not a recency window); " \
                 "not excluded by the time-dependency or circularity rules."
        safe = True

    return {
        "FEATURE": col,
        "TIME_DEPENDENT": time_dep,
        "DERIVED_FROM_REVIEWS": review_derived,
        "LHI_COMPONENT": lhi_component,
        "RULE_SAFE_FOR_TARGET": safe,
        "REASONING": reason,
    }


def main():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    numeric_cols = [c for c in biz.select_dtypes(include=[np.number]).columns if c not in NON_FEATURE_COLS]

    lineage_rows = [classify_column(c) for c in numeric_cols]
    lineage = pd.DataFrame(lineage_rows)

    # Empirical leakage scan: correlation with IS_OPEN for every candidate.
    corrs = {}
    for c in numeric_cols:
        s = biz[c]
        if s.notna().sum() > 10 and s.nunique() > 1:
            corrs[c] = s.corr(biz["IS_OPEN"])
    corr_series = pd.Series(corrs, name="CORR_WITH_IS_OPEN")
    lineage = lineage.merge(corr_series.rename_axis("FEATURE").reset_index(), on="FEATURE", how="left")

    EMPIRICAL_LEAK_THRESHOLD = 0.30
    lineage["EMPIRICAL_LEAK_FLAG"] = lineage["CORR_WITH_IS_OPEN"].abs() > EMPIRICAL_LEAK_THRESHOLD
    lineage["FINAL_SAFE_FOR_TARGET"] = lineage["RULE_SAFE_FOR_TARGET"] & ~lineage["EMPIRICAL_LEAK_FLAG"].fillna(False)

    # Anything with a strong empirical correlation but that the name-pattern
    # rules missed gets caught here too (belt and braces) and is reported,
    # not silently dropped.
    rule_missed = lineage[(lineage["EMPIRICAL_LEAK_FLAG"]) & (lineage["RULE_SAFE_FOR_TARGET"])]
    if len(rule_missed):
        log(f"Empirical scan caught {len(rule_missed)} leak(s) the naming rules missed: "
            f"{rule_missed['FEATURE'].tolist()}")

    lineage = lineage.sort_values("CORR_WITH_IS_OPEN", key=lambda s: s.abs(), ascending=False)
    out = OUTPUT_DIR / "QSR_FEATURE_LINEAGE.csv"
    lineage.to_csv(out, index=False)

    safe_features = lineage.loc[lineage["FINAL_SAFE_FOR_TARGET"], "FEATURE"].tolist()
    unsafe_features = lineage.loc[~lineage["FINAL_SAFE_FOR_TARGET"], "FEATURE"].tolist()
    log(f"Feature lineage: {len(safe_features)} safe-for-target, {len(unsafe_features)} excluded "
        f"(time-dependent, LHI-component, or empirically leaky). Wrote {out}")

    # Target/leakage documentation artefact.
    doc = pd.DataFrame([
        {"CHECK": "target_availability", "FINDING":
            "No sales, dated-closure, or audit outcome exists in the Yelp dataset. IS_OPEN is the only "
            "candidate for a supervised target, and it is a cross-sectional point-in-time flag, not a "
            "closure history."},
        {"CHECK": "target_leakage", "FINDING":
            f"{unsafe_features.__len__()} of {len(numeric_cols)} candidate features are excluded before "
            "modelling on time-dependency, LHI-component, or empirical-correlation grounds; see "
            "QSR_FEATURE_LINEAGE.csv for the full reasoning per feature."},
        {"CHECK": "circular_scoring", "FINDING":
            "LHI pillar-component columns (peer star gap, peer rating percentile, local benchmark fields) "
            "are excluded from the target-prediction feature set for the same reason: using them to predict "
            "IS_OPEN and then citing that as validation of the LHI would be circular."},
        {"CHECK": "proxy_construction", "FINDING":
            "The strongest defensible proxy is IS_OPEN with the excluded features removed -- explicitly an "
            "imperfect proxy for \"location health,\" not ground truth. Its predictive value (stage 8) is "
            "treated as one piece of evidence about whether the retained features carry real signal, not as "
            "proof the LHI is correct."},
    ])
    doc.to_csv(OUTPUT_DIR / "QSR_LEAKAGE_AUDIT.csv", index=False)

    log("Stage 7 complete.")


if __name__ == "__main__":
    main()
