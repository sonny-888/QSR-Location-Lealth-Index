"""Stage 9 - Build LHI-0..3 candidates.

ML = importance evidence, Statistics = structure evidence, Business logic =
meaning evidence, Robustness = stability evidence (checked in stage 10).
Final weights for LHI-3 come from a documented synthesis of these, not a
direct copy of any single source -- and feature importance is explicitly
NOT treated as a normative weight (stage 8's importance answers "what
predicts IS_OPEN," not "how much should this count toward health").

LHI-0..3 are candidates. None is labelled "recommended" here; stage 10
supplies the robustness/stability evidence the final selection is argued
from (done in stage 11).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, require, log, percentile_rank

BASELINE_WEIGHTS = {"PEER": 0.30, "ENGAGEMENT": 0.25, "MOMENTUM": 0.25, "CX": 0.20}

# Domain mapping of stage 8's SAFE feature set to a pillar, for ML-informed
# weight evidence. Momentum has NO representation here -- virtually every
# momentum/recency-style feature was excluded in stage 7 as unsafe for the
# IS_OPEN target, so there is no ML importance evidence for Momentum at all.
# This is a structural gap, disclosed explicitly rather than papered over.
FEATURE_PILLAR_MAP = {
    "BUSINESS_STARS": "PEER", "AVG_REVIEW_STARS": "PEER", "AVG_REVIEWER_AVERAGE_STARS": "PEER",
    "BUSINESS_VS_LOADED_STAR_GAP": "PEER", "REVIEW_STAR_STDDEV": "PEER",
    "LOADED_REVIEW_COUNT": "ENGAGEMENT", "BUSINESS_REVIEW_COUNT": "ENGAGEMENT",
    "UNIQUE_REVIEW_COUNT": "ENGAGEMENT", "UNIQUE_REVIEWERS": "ENGAGEMENT",
    "CHECKINS_PER_LOADED_REVIEW": "ENGAGEMENT", "TIPS_PER_LOADED_REVIEW": "ENGAGEMENT",
    "CHECKIN_COUNT": "ENGAGEMENT", "UNIQUE_CHECKIN_COUNT": "ENGAGEMENT", "CHECKIN_ACTIVE_MONTHS": "ENGAGEMENT",
    "TIP_COUNT": "ENGAGEMENT", "UNIQUE_TIPPERS": "ENGAGEMENT", "TIPS_WITH_TEXT": "ENGAGEMENT",
    "TIP_COMPLIMENT_COUNT": "ENGAGEMENT", "TOTAL_USEFUL_VOTES": "ENGAGEMENT", "TOTAL_FUNNY_VOTES": "ENGAGEMENT",
    "TOTAL_COOL_VOTES": "ENGAGEMENT", "REVIEWS_WITH_MATCHED_USER": "ENGAGEMENT",
    "USER_MATCH_RATE_PERCENT": "ENGAGEMENT", "AVG_REVIEWER_LIFETIME_REVIEW_COUNT": "ENGAGEMENT",
    "LOADED_REVIEW_COVERAGE_PERCENT": "ENGAGEMENT", "REVIEW_TEXT_COVERAGE_PERCENT": "ENGAGEMENT",
    "NEGATIVE_REVIEW_PERCENT": "CX", "POSITIVE_REVIEW_PERCENT": "CX",
}


def build_pillar_components(biz: pd.DataFrame, peer: pd.DataFrame, trajectory: pd.DataFrame, cx: pd.DataFrame) -> pd.DataFrame:
    df = biz[["BUSINESS_ID", "QSR_SEGMENT", "IS_OPEN", "LOADED_REVIEW_COUNT",
              "CHECKINS_PER_LOADED_REVIEW", "TIPS_PER_LOADED_REVIEW"]].merge(
        peer[["BUSINESS_ID", "STAR_GAP_VS_PEERS", "PEER_RATING_PERCENTILE"]], on="BUSINESS_ID", how="left"
    ).merge(trajectory[["BUSINESS_ID", "RATING_DELTA", "VOLUME_MOMENTUM_LOG", "RATING_TRAJECTORY"]],
            on="BUSINESS_ID", how="left"
    ).merge(cx[["BUSINESS_ID", "PILLAR_CX", "CX_EVIDENCE_CONFIDENCE"]], on="BUSINESS_ID", how="left")

    # Peer pillar: 0.6 * star-gap percentile + 0.4 * peer rating percentile
    # (production formula both existing docs agree on, kept as the LHI-0
    # baseline construction; alternative constructions are stress-tested in
    # stage 10, not assumed correct here).
    df["_star_gap_pct"] = percentile_rank(df["STAR_GAP_VS_PEERS"])
    df["PILLAR_PEER"] = 0.6 * df["_star_gap_pct"] + 0.4 * df["PEER_RATING_PERCENTILE"]

    # Engagement pillar: 0.5 * log volume + 0.25 * checkin ratio + 0.25 * tip ratio.
    # A NaN here means the source pipeline recorded zero check-ins/tips ever
    # (NULL, not 0, in the Snowflake export) -- genuinely "no activity of
    # this kind," not missing evidence, so it's filled with 0 before ranking
    # rather than propagated as NaN (which would otherwise silently NaN out
    # every LHI version for ~12% of businesses).
    df["_log_vol_pct"] = percentile_rank(np.log1p(df["LOADED_REVIEW_COUNT"]))
    df["_checkin_pct"] = percentile_rank(df["CHECKINS_PER_LOADED_REVIEW"].fillna(0).clip(upper=20))
    df["_tip_pct"] = percentile_rank(df["TIPS_PER_LOADED_REVIEW"].fillna(0).clip(upper=5))
    df["PILLAR_ENGAGEMENT"] = 0.5 * df["_log_vol_pct"] + 0.25 * df["_checkin_pct"] + 0.25 * df["_tip_pct"]

    # Momentum pillar: our own bootstrap-evidenced rating delta (stage 6),
    # not the pipeline's original black-box precomputed trend field, plus
    # volume-growth momentum. Businesses with "Insufficient Evidence" get a
    # NaN pillar score here -- handled explicitly by the fallback hierarchy
    # in stage 12, not silently zero-filled.
    df["_rating_delta_pct"] = percentile_rank(df["RATING_DELTA"])
    df["_volume_momentum_pct"] = percentile_rank(df["VOLUME_MOMENTUM_LOG"])
    df["PILLAR_MOMENTUM"] = 0.6 * df["_rating_delta_pct"] + 0.4 * df["_volume_momentum_pct"]

    df["PILLAR_CX"] = df["PILLAR_CX"]

    return df


def lhi0_business_rule(df: pd.DataFrame) -> pd.Series:
    w = BASELINE_WEIGHTS
    return (w["PEER"] * df["PILLAR_PEER"] + w["ENGAGEMENT"] * df["PILLAR_ENGAGEMENT"] +
            w["MOMENTUM"] * df["PILLAR_MOMENTUM"].fillna(df["PILLAR_MOMENTUM"].median()) +
            w["CX"] * df["PILLAR_CX"])


def statistical_weights(df: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """LHI-1: weights from pillar independence/variance structure (PCA first-
    component loadings + a "uniqueness" signal from average pairwise
    correlation). Because every pillar is already percentile-transformed to
    a comparable 0-100 scale before this step, their raw variances are
    approximately equal by construction -- so a pure variance-based weighting
    is expected to land close to equal weights; that's a real, reportable
    finding, not a bug, and it's why LHI-1 leans on correlation structure
    (uniqueness) as well as PCA, not variance alone.
    """
    pillars = ["PILLAR_PEER", "PILLAR_ENGAGEMENT", "PILLAR_MOMENTUM", "PILLAR_CX"]
    sub = df[pillars].dropna()

    corr = sub.corr()
    avg_abs_corr = (corr.abs().sum(axis=1) - 1) / (len(pillars) - 1)
    uniqueness = (1 - avg_abs_corr)
    uniqueness_w = (uniqueness / uniqueness.sum()).to_dict()

    pca = PCA(n_components=1)
    pca.fit((sub - sub.mean()) / sub.std())
    loadings = np.abs(pca.components_[0])
    pca_w = dict(zip(pillars, loadings / loadings.sum()))

    blended = {p: (uniqueness_w[p] + pca_w[p]) / 2 for p in pillars}
    total = sum(blended.values())
    blended = {p: v / total for p, v in blended.items()}

    detail = pd.DataFrame({
        "PILLAR": pillars,
        "AVG_ABS_CORR_WITH_OTHERS": [round(avg_abs_corr[p], 4) for p in pillars],
        "UNIQUENESS_WEIGHT": [round(uniqueness_w[p], 4) for p in pillars],
        "PCA_FIRST_COMPONENT_WEIGHT": [round(pca_w[p], 4) for p in pillars],
        "LHI1_BLENDED_WEIGHT": [round(blended[p], 4) for p in pillars],
    })
    return {p.replace("PILLAR_", ""): blended[p] for p in pillars}, detail


def ml_informed_weights() -> tuple[dict, str]:
    imp_path = OUTPUT_DIR / "QSR_ML_FEATURE_IMPORTANCE.csv"
    require(imp_path.exists(), "Run stage 8 first (ML modelling)")
    imp = pd.read_csv(imp_path)
    imp["PILLAR"] = imp["FEATURE"].map(FEATURE_PILLAR_MAP)
    mapped = imp.dropna(subset=["PILLAR"])
    agg = mapped.groupby("PILLAR")["PERMUTATION_IMPORTANCE_MEAN"].sum().clip(lower=0)

    note = ("No SAFE-set feature maps to MOMENTUM -- every momentum/recency-style feature was excluded in stage 7 "
            "as unsafe for the IS_OPEN target itself, so there is no ML importance evidence for Momentum's weight. "
            "LHI-2's Momentum weight falls back to the LHI-0 baseline value (0.25) rather than being fabricated.")

    weights = {}
    if agg.sum() > 0:
        for pillar in ["PEER", "ENGAGEMENT", "CX"]:
            weights[pillar] = agg.get(pillar, 0) / agg.sum() * (1 - BASELINE_WEIGHTS["MOMENTUM"])
    weights["MOMENTUM"] = BASELINE_WEIGHTS["MOMENTUM"]
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}
    return weights, note


def hybrid_weights(w0: dict, w1: dict, w2: dict) -> dict:
    """LHI-3: average of business-rule, statistical, and ML-informed weights
    where all three exist; for Momentum (no ML evidence), average only the
    business-rule and statistical weights. A documented synthesis rule, not
    a formula-only average dressed up as objective."""
    hybrid = {}
    for pillar in ["PEER", "ENGAGEMENT", "CX"]:
        hybrid[pillar] = np.mean([w0[pillar], w1[pillar], w2[pillar]])
    hybrid["MOMENTUM"] = np.mean([w0["MOMENTUM"], w1["MOMENTUM"]])
    total = sum(hybrid.values())
    return {k: v / total for k, v in hybrid.items()}


def score_lhi(df: pd.DataFrame, weights: dict) -> pd.Series:
    return (weights["PEER"] * df["PILLAR_PEER"] + weights["ENGAGEMENT"] * df["PILLAR_ENGAGEMENT"] +
            weights["MOMENTUM"] * df["PILLAR_MOMENTUM"].fillna(df["PILLAR_MOMENTUM"].median()) +
            weights["CX"] * df["PILLAR_CX"])


def main():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    peer = pd.read_csv(ROOT / "QSR_BUSINESS_PEER_BENCHMARKS.csv", low_memory=False)
    trajectory = pd.read_csv(OUTPUT_DIR / "QSR_TRAJECTORY_FINAL.csv")
    cx = pd.read_csv(OUTPUT_DIR / "QSR_CX_PILLAR.csv")

    df = build_pillar_components(biz, peer, trajectory, cx)

    w0 = BASELINE_WEIGHTS
    w1, w1_detail = statistical_weights(df)
    w2, w2_note = ml_informed_weights()
    w3 = hybrid_weights(w0, w1, w2)

    log(f"LHI-0 (business rule): {w0}")
    log(f"LHI-1 (statistical):   { {k: round(v,3) for k,v in w1.items()} }")
    log(f"LHI-2 (ML-informed):   { {k: round(v,3) for k,v in w2.items()} } -- {w2_note}")
    log(f"LHI-3 (hybrid candidate): { {k: round(v,3) for k,v in w3.items()} }")

    df["LHI_0"] = score_lhi(df, w0)
    df["LHI_1"] = score_lhi(df, w1)
    df["LHI_2"] = score_lhi(df, w2)
    df["LHI_3"] = score_lhi(df, w3)

    weights_table = pd.DataFrame([
        {"LHI_VERSION": "LHI-0", "TYPE": "Business-rule baseline", **w0},
        {"LHI_VERSION": "LHI-1", "TYPE": "Statistical (PCA + uniqueness)", **w1},
        {"LHI_VERSION": "LHI-2", "TYPE": "ML-informed (permutation importance)", **w2},
        {"LHI_VERSION": "LHI-3", "TYPE": "Hybrid candidate", **w3},
    ])
    weights_table.to_csv(OUTPUT_DIR / "QSR_LHI_WEIGHTS_BY_VERSION.csv", index=False)
    w1_detail.to_csv(OUTPUT_DIR / "QSR_LHI1_STATISTICAL_EVIDENCE.csv", index=False)
    pd.DataFrame([{"NOTE": w2_note}]).to_csv(OUTPUT_DIR / "QSR_LHI2_ML_EVIDENCE_NOTE.csv", index=False)

    out_cols = ["BUSINESS_ID", "QSR_SEGMENT", "IS_OPEN", "PILLAR_PEER", "PILLAR_ENGAGEMENT",
                "PILLAR_MOMENTUM", "PILLAR_CX", "LHI_0", "LHI_1", "LHI_2", "LHI_3", "CX_EVIDENCE_CONFIDENCE"]
    df[out_cols].to_csv(OUTPUT_DIR / "QSR_LHI_ALL_VERSIONS.csv", index=False)

    log(f"LHI version means: " + ", ".join(f"LHI_{i}={df[f'LHI_{i}'].mean():.1f}" for i in range(4)))
    log("Stage 9 complete.")


if __name__ == "__main__":
    main()
