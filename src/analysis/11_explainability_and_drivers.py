"""Stage 11 - Explainability, drivers, and intervention priority.

Health, trajectory, confidence, and intervention priority are kept as four
separate concepts, never collapsed into one number. The final LHI version is
selected here from LHI-0..3 using an explicit, checkable rule (highest mean
pairwise Spearman correlation with the other three candidates -- i.e. the
version closest to the "consensus" ranking across business-rule, statistical,
and ML-informed evidence), not assumed to be LHI-3 in advance, and the check
result is logged either way.

Intervention priority is a function of health AND trajectory magnitude AND
confidence together, so e.g. a high-scoring but rapidly deteriorating
location can outrank a lower-scoring but recovering one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import shap

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, log, extract_positive_class_shap

CONFIDENCE_MULTIPLIER = {"High": 1.0, "Medium": 0.6, "Low": 0.3}


def select_final_version(lhi_all: pd.DataFrame, version_comp: pd.DataFrame) -> str:
    versions = ["LHI_0", "LHI_1", "LHI_2", "LHI_3"]
    mean_corr = {}
    for v in versions:
        rows = version_comp[(version_comp["VERSION_A"] == v) | (version_comp["VERSION_B"] == v)]
        mean_corr[v] = rows["SPEARMAN_RHO"].mean()
    selected = max(mean_corr, key=mean_corr.get)
    log(f"Final LHI version selection (highest mean pairwise Spearman with the other candidates): "
        f"{mean_corr} -> selected {selected}")
    return selected


def compute_shap_drivers(lineage: pd.DataFrame, biz: pd.DataFrame) -> pd.DataFrame:
    safe_features = lineage.loc[lineage["FINAL_SAFE_FOR_TARGET"], "FEATURE"].tolist()
    X = biz[safe_features]
    y = biz["IS_OPEN"]

    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(n_estimators=200, max_depth=8, min_samples_leaf=10,
                                           class_weight="balanced", random_state=42, n_jobs=-1)),
    ])
    pipe.fit(X, y)
    X_imputed = pd.DataFrame(pipe.named_steps["impute"].transform(X), columns=safe_features, index=X.index)

    explainer = shap.TreeExplainer(pipe.named_steps["model"])
    shap_values = explainer.shap_values(X_imputed)
    sv = extract_positive_class_shap(shap_values)

    shap_df = pd.DataFrame(sv, columns=safe_features, index=biz["BUSINESS_ID"])
    top3 = pd.DataFrame(index=shap_df.index)
    abs_shap = shap_df.abs()
    for rank in range(3):
        top3[f"SHAP_TOP_DRIVER_{rank + 1}"] = abs_shap.apply(
            lambda row: row.nlargest(rank + 1).index[-1] if row.notna().any() else None, axis=1
        )
    return top3.reset_index()


def top_negative_theme_evidence(cx_aspect: pd.DataFrame, review_aspect: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Picks the weakest aspect per business, preferring aspects the business
    has its own review evidence for. Without this guard, a rare-but-uniformly-
    negative aspect wins "worst aspect" for most businesses via pure
    peer-prior shrinkage rather than their own reviews -- checked directly
    while validating Order Accuracy (mentioned in only ~0.48 reviews/business
    on average, but virtually always negative when mentioned): 74% of the
    businesses where it came out "worst" had zero Order Accuracy mentions of
    their own. Preferring evidenced aspects fixes this for every aspect, not
    just Order Accuracy -- an aspect still wins legitimately whenever a
    business has real negative evidence for it.
    """
    has_evidence = cx_aspect["N_MENTIONS"] > 0
    evidenced = cx_aspect[has_evidence]
    evidenced_weakest = evidenced.loc[evidenced.groupby("BUSINESS_ID")["PEER_PERCENTILE"].idxmin()]

    # Businesses with zero mentions in every aspect have no evidenced
    # candidate at all -- fall back to the pure peer-prior percentile only
    # for those, since there's genuinely no other basis to pick from.
    no_evidence_ids = set(cx_aspect["BUSINESS_ID"]) - set(evidenced_weakest["BUSINESS_ID"])
    fallback = cx_aspect[cx_aspect["BUSINESS_ID"].isin(no_evidence_ids)]
    fallback_weakest = (fallback.loc[fallback.groupby("BUSINESS_ID")["PEER_PERCENTILE"].idxmin()]
                         if len(fallback) else fallback)

    weakest = pd.concat([evidenced_weakest, fallback_weakest], ignore_index=True)[
        ["BUSINESS_ID", "ASPECT", "PEER_PERCENTILE"]
    ].rename(columns={"ASPECT": "TOP_NEGATIVE_ASPECT", "PEER_PERCENTILE": "TOP_NEGATIVE_ASPECT_PERCENTILE"})

    ra = review_aspect.merge(reviews[["REVIEW_ID", "REVIEW_TEXT"]], on="REVIEW_ID", how="left")
    ra_neg = ra[ra["SENTIMENT"] < -0.3].sort_values("REVIEW_TS", ascending=False)

    # Restrict to only the (business, aspect) pairs actually needed, then take
    # the top-3 most recent per pair in one vectorized groupby (a per-business
    # Python-loop filter here is O(n_businesses * n_negative_rows) and far too
    # slow at this scale).
    pair_keys = pd.MultiIndex.from_frame(weakest[["BUSINESS_ID", "TOP_NEGATIVE_ASPECT"]].rename(
        columns={"TOP_NEGATIVE_ASPECT": "ASPECT"}))
    ra_neg = ra_neg[ra_neg.set_index(["BUSINESS_ID", "ASPECT"]).index.isin(pair_keys)]
    top_snippets = ra_neg.groupby(["BUSINESS_ID", "ASPECT"], as_index=False).head(3)

    evidence = top_snippets[["BUSINESS_ID", "ASPECT", "SENTIMENT", "REVIEW_TS", "REVIEW_TEXT"]].copy()
    evidence["SENTIMENT"] = evidence["SENTIMENT"].round(3)
    evidence["REVIEW_SNIPPET"] = evidence["REVIEW_TEXT"].fillna("").str.slice(0, 280)
    evidence = evidence.drop(columns=["REVIEW_TEXT"])
    return weakest[["BUSINESS_ID", "TOP_NEGATIVE_ASPECT", "TOP_NEGATIVE_ASPECT_PERCENTILE"]], evidence


def pillar_drivers(df: pd.DataFrame) -> pd.DataFrame:
    pillars = ["PILLAR_PEER", "PILLAR_ENGAGEMENT", "PILLAR_MOMENTUM", "PILLAR_CX"]
    z = df[pillars] - 50  # pillars are percentiles; 50 is the peer-neutral point
    top_pos = z.idxmax(axis=1)
    top_neg = z.idxmin(axis=1)
    return pd.DataFrame({
        "BUSINESS_ID": df["BUSINESS_ID"],
        "TOP_POSITIVE_DRIVER": top_pos.str.replace("PILLAR_", ""),
        "TOP_NEGATIVE_DRIVER": top_neg.str.replace("PILLAR_", ""),
    })


# Priority = f(current health band, trajectory) -- directly encodes the
# "LHI 75 declining can outrank LHI 65 improving" principle as an explicit,
# inspectable lookup rather than an additive score where health's 0-100
# range would otherwise always swamp a capped trend adjustment. Matches the
# worked example table: e.g. Healthy+Deteriorating -> Medium (a deterioration
# warning, elevated above a stagnant/improving healthy business, but not
# automatically as urgent as a location that is already unhealthy).
PRIORITY_LOOKUP = {
    ("Healthy", "Improving"): "Low", ("Healthy", "Stable"): "Low",
    ("Healthy", "Deteriorating"): "Medium", ("Healthy", "Insufficient Evidence"): "Low",
    ("Watch", "Improving"): "Low", ("Watch", "Stable"): "Medium",
    ("Watch", "Deteriorating"): "High", ("Watch", "Insufficient Evidence"): "Medium",
    ("High Risk", "Improving"): "Medium", ("High Risk", "Stable"): "High",
    ("High Risk", "Deteriorating"): "Critical", ("High Risk", "Insufficient Evidence"): "High",
    ("Critical Risk", "Improving"): "High", ("Critical Risk", "Stable"): "Critical",
    ("Critical Risk", "Deteriorating"): "Critical", ("Critical Risk", "Insufficient Evidence"): "Critical",
}
PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]


def intervention_priority(df: pd.DataFrame) -> pd.DataFrame:
    from lib.common import risk_band
    health_band = risk_band(df["LHI_FINAL"])
    trajectory = df["RATING_TRAJECTORY"].fillna("Insufficient Evidence")

    priority_band = pd.Series(
        [PRIORITY_LOOKUP.get((h, t), "Medium") for h, t in zip(health_band, trajectory)],
        index=df.index,
    )

    # A Low-confidence trajectory signal shouldn't drive urgent action on its
    # own -- downgrade one level (never below Low) when evidence is thin.
    low_conf = df["CX_EVIDENCE_CONFIDENCE"] == "Low"
    downgraded = priority_band.map(lambda p: PRIORITY_ORDER[max(0, PRIORITY_ORDER.index(p) - 1)])
    priority_band = priority_band.where(~low_conf, downgraded)

    risk_score = 100 - df["LHI_FINAL"]
    mult = df["CX_EVIDENCE_CONFIDENCE"].map(CONFIDENCE_MULTIPLIER).fillna(0.3)
    trend_adjustment = np.where(
        df["RATING_TRAJECTORY"] == "Deteriorating", np.minimum(20, df["RATING_DELTA"].abs() * 15),
        np.where(df["RATING_TRAJECTORY"] == "Improving", -np.minimum(15, df["RATING_DELTA"].abs() * 12), 0.0),
    )
    priority_score = risk_score + trend_adjustment * mult  # for sorting within a priority band, not the band itself

    return pd.DataFrame({
        "BUSINESS_ID": df["BUSINESS_ID"], "RISK_SCORE": risk_score.round(1),
        "TREND_ADJUSTMENT": trend_adjustment.round(1), "INTERVENTION_PRIORITY_SCORE": priority_score.round(1),
        "INTERVENTION_PRIORITY": priority_band,
    })


def main():
    lhi_all = pd.read_csv(OUTPUT_DIR / "QSR_LHI_ALL_VERSIONS.csv")
    version_comp = pd.read_csv(OUTPUT_DIR / "QSR_LHI_VERSION_COMPARISON.csv")
    trajectory = pd.read_csv(OUTPUT_DIR / "QSR_TRAJECTORY_FINAL.csv")
    lineage = pd.read_csv(OUTPUT_DIR / "QSR_FEATURE_LINEAGE.csv")
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    cx_aspect = pd.read_csv(OUTPUT_DIR / "QSR_CX_ASPECT_SCORES.csv")
    review_aspect = pd.read_parquet(OUTPUT_DIR / "qsr_review_aspect.parquet")
    reviews = pd.read_parquet(OUTPUT_DIR / "qsr_reviews_detail.parquet", columns=["REVIEW_ID", "REVIEW_TEXT"])

    selected_version = select_final_version(lhi_all, version_comp)
    lhi_all["LHI_FINAL"] = lhi_all[selected_version]
    lhi_all["LHI_VERSION_SELECTED"] = selected_version

    traj_cols = ["BUSINESS_ID", "RATING_DELTA", "RATING_TRAJECTORY", "TOP_DETERIORATING_ASPECT",
                 "RECENCY_WEIGHTED_STARS", "RECENCY_VS_RAW_GAP", "RECENT_MEAN_STARS", "PRIOR_MEAN_STARS",
                 "SPIKE_DETECTED", "SPIKE_STATUS", "SPIKE_RATE_DELTA", "SPIKE_30D_FLAG", "SPIKE_90D_FLAG"]
    df = lhi_all.merge(trajectory[traj_cols], on="BUSINESS_ID", how="left")
    df = df.merge(biz[["BUSINESS_ID", "DAYS_WITH_HOURS"]], on="BUSINESS_ID", how="left")

    log("Computing SHAP drivers (fresh RandomForest fit on the leakage-safe feature set)...")
    shap_drivers = compute_shap_drivers(lineage, biz)

    weakest, evidence = top_negative_theme_evidence(cx_aspect, review_aspect, reviews)
    evidence.to_csv(OUTPUT_DIR / "QSR_ROOT_CAUSE_EVIDENCE.csv", index=False)

    pdrivers = pillar_drivers(df)
    df = df.merge(pdrivers, on="BUSINESS_ID", how="left").merge(weakest, on="BUSINESS_ID", how="left")

    priority = intervention_priority(df)
    df = df.merge(priority, on="BUSINESS_ID", how="left").merge(shap_drivers, on="BUSINESS_ID", how="left")

    # Emerging issue: deliberately kept separate from INTERVENTION_PRIORITY,
    # not folded into it -- a spike is a *recent* signal the 12-month
    # trajectory structurally can't see, and collapsing it into the priority
    # score would hide exactly the "stable annual average, bad last month"
    # case it exists to catch. Surfaced as its own field instead.
    df["EMERGING_ISSUE"] = np.where(
        df["SPIKE_DETECTED"].fillna(False) & df["TOP_DETERIORATING_ASPECT"].notna(),
        df["TOP_DETERIORATING_ASPECT"].astype(str) + " spike",
        np.where(df["SPIKE_DETECTED"].fillna(False), "Recent negative-review spike", None),
    )

    # Operational profile: a contextual/diagnostic field, not a scored pillar
    # -- see stage 10's QSR_OPERATIONAL_PROFILE_EVIDENCE_GATE.csv for why
    # (DAYS_WITH_HOURS measures listing completeness, not observed operating
    # consistency, so it informs the read but doesn't move the LHI).
    df["OPERATIONAL_PROFILE_DAYS_WITH_HOURS"] = df["DAYS_WITH_HOURS"]

    df.to_csv(OUTPUT_DIR / "QSR_DRIVERS.csv", index=False)

    # A healthy-but-deteriorating location should be escalated above an
    # equally healthy stable/improving one (a "deterioration warning," not
    # necessarily the same urgency as a location that's already unhealthy --
    # per the worked example: 85 LHI + declining = warning, not automatically
    # "high priority" outright).
    declining_high_lhi = df[(df["LHI_FINAL"] >= 70) & (df["RATING_TRAJECTORY"] == "Deteriorating")]
    stable_high_lhi = df[(df["LHI_FINAL"] >= 70) & (df["RATING_TRAJECTORY"].isin(["Stable", "Improving"]))]
    order = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    declining_escalated = declining_high_lhi["INTERVENTION_PRIORITY"].map(order).mean()
    stable_baseline = stable_high_lhi["INTERVENTION_PRIORITY"].map(order).mean()
    log(f"Sanity check: {len(declining_high_lhi)} healthy-but-declining businesses (LHI>=70, Deteriorating) "
        f"average priority tier {declining_escalated:.2f} vs {stable_baseline:.2f} for equally healthy "
        f"stable/improving businesses ({len(stable_high_lhi)}) -- escalated as intended "
        f"{'(pass)' if declining_escalated > stable_baseline else '(FAIL: no escalation detected)'}.")

    log(f"Intervention priority distribution: {df['INTERVENTION_PRIORITY'].value_counts().to_dict()}")
    log("Stage 11 complete.")


if __name__ == "__main__":
    main()
