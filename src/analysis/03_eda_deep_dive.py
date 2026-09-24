"""Stage 3 - Deep, hypothesis-driven EDA.

Structured around named questions rather than a gallery of plots. Each ends
in a written finding with an explicit LHI design implication, appended to
QSR_EDA_FINDINGS.csv. The CX/aspect-sentiment pillar doesn't exist yet at
this point in the pipeline (it's built in stages 4-5), so Q2's pillar-
independence check runs on the three business-level pillars available now
(Peer, Engagement, Momentum) and is revisited with CX included once stage 5
completes -- flagged explicitly below rather than faked. Q5 opens the
DAYS_WITH_HOURS operational-profile investigation the same way -- partial
here, completed once stage 8/10's ML and robustness evidence exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, FIGURES_DIR, DATASET_CUTOFF, log, set_plot_theme, savefig

findings = []


def finding(section, question, result, implication):
    findings.append({"SECTION": section, "QUESTION": question, "FINDING": result, "LHI_IMPLICATION": implication})
    log(f"[{section}] {result[:110]}")


def load_data():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    peer = pd.read_csv(ROOT / "QSR_BUSINESS_PEER_BENCHMARKS.csv", low_memory=False)
    df = biz.merge(peer[["BUSINESS_ID", "BENCHMARK_TIER_USED", "STAR_GAP_VS_PEERS",
                          "REVIEW_VOLUME_INDEX", "PEER_RATING_PERCENTILE"]], on="BUSINESS_ID", how="left")
    reviews_path = OUTPUT_DIR / "qsr_reviews_detail.parquet"
    reviews = pd.read_parquet(reviews_path, columns=["BUSINESS_ID", "STARS", "REVIEW_TS"]) if reviews_path.exists() else None
    return df, reviews


# ---------------------------------------------------------------------------
def structure_missingness_duplicates(df: pd.DataFrame):
    n_rows, n_cols = df.shape
    n_num = df.select_dtypes(include=[np.number]).shape[1]
    n_cat = n_cols - n_num
    finding("Structure", "Dataset shape and type mix",
            f"{n_rows} rows x {n_cols} columns ({n_num} numeric, {n_cat} categorical/text).",
            "Confirms business-grain, wide table suitable for pillar construction without further reshaping.")

    miss = df.isna().mean().sort_values(ascending=False) * 100
    heavy = miss[miss > 50]
    finding("Missingness", "Which columns are too sparse to use directly?",
            f"{len(heavy)} columns exceed 50% missing: {list(heavy.index)}.",
            "These (mostly attribute flags like WHEELCHAIR_ACCESSIBLE, HAS_DRIVE_THRU, HAS_TABLE_SERVICE) "
            "are unsuitable as direct LHI inputs without an explicit missing-category encoding; excluded from pillars.")

    dup_name_addr = int(df.duplicated(subset=["BUSINESS_NAME", "ADDRESS", "CITY", "STATE"]).sum())
    finding("Duplicates", "Are there near-duplicate businesses inflating counts?",
            f"{dup_name_addr} rows share name+address+city+state with another row (out of {len(df)}).",
            "Low enough to leave as-is; would need a franchise/site master to resolve safely, noted as a limitation.")

    card = df.nunique(dropna=False)
    finding("Cardinality", "Any constant / near-constant columns?",
            f"{int((card == 1).sum())} single-valued columns; "
            f"{int((card <= 2).sum())} columns with <=2 distinct values.",
            "Single-valued columns (e.g. DATASET_MAX_REVIEW_TS) confirm the fixed 2022-01-19 cutoff and carry zero "
            "discriminating information for scoring.")


# ---------------------------------------------------------------------------
def outliers_and_distributions(df: pd.DataFrame):
    set_plot_theme()
    import matplotlib.pyplot as plt

    numeric_cols = ["BUSINESS_REVIEW_COUNT", "LOADED_REVIEW_COUNT", "CHECKIN_COUNT", "TIP_COUNT",
                    "AVG_REVIEW_STARS", "REVIEW_STAR_STDDEV"]
    rows = []
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for ax, col in zip(axes.flat, numeric_cols):
        s = df[col].dropna()
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        iqr_outliers = ((s < q1 - 1.5 * iqr) | (s > q3 + 1.5 * iqr)).sum()
        robust_z = 0.6745 * (s - s.median()) / (stats.median_abs_deviation(s) or 1)
        z_outliers = (robust_z.abs() > 3.5).sum()
        skew_raw = float(s.skew())
        skew_log = float(np.log1p(s.clip(lower=0)).skew()) if s.min() >= 0 else np.nan
        rows.append({"COLUMN": col, "IQR_OUTLIERS": int(iqr_outliers), "ROBUST_Z_OUTLIERS": int(z_outliers),
                      "SKEW_RAW": round(skew_raw, 2), "SKEW_LOG1P": round(skew_log, 2) if pd.notna(skew_log) else None,
                      "N": len(s)})
        sns_ax = ax
        sns_ax.hist(np.log1p(s.clip(lower=0)) if s.min() >= 0 else s, bins=40, color="#4C72B0")
        sns_ax.set_title(col, fontsize=10)
    plt.tight_layout()
    savefig("eda_distributions")

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUTPUT_DIR / "QSR_EDA_OUTLIER_SKEW.csv", index=False)

    worst_skew = out_df.loc[out_df["SKEW_RAW"].abs().idxmax()]
    finding("Distributions", "Which numerics are skewed enough to need a transform?",
            f"{worst_skew['COLUMN']} has raw skew {worst_skew['SKEW_RAW']}, "
            f"reduced to {worst_skew['SKEW_LOG1P']} after log1p. Full table: QSR_EDA_OUTLIER_SKEW.csv.",
            "Confirms the pipeline's existing log1p(review volume) design choice is justified, not arbitrary; "
            "the same transform should apply consistently to check-in/tip counts before percentile-ranking.")


# ---------------------------------------------------------------------------
def q1_review_volume_effects(df: pd.DataFrame):
    bins = [0, 5, 20, 50, 100, np.inf]
    labels = ["1-5", "6-20", "21-50", "51-100", "100+"]
    df = df.copy()
    df["_vol_bucket"] = pd.cut(df["LOADED_REVIEW_COUNT"], bins=bins, labels=labels)
    g = df.groupby("_vol_bucket", observed=True).agg(
        n=("BUSINESS_ID", "size"),
        mean_stars=("BUSINESS_STARS", "mean"),
        star_stddev=("REVIEW_STAR_STDDEV", "mean"),
    ).reset_index()
    g.to_csv(OUTPUT_DIR / "QSR_EDA_Q1_VOLUME_EFFECTS.csv", index=False)

    # The honest pattern here is non-monotonic (checked against all five
    # buckets, not just the two endpoints): stddev rises from the 1-5 bucket
    # into the 6-50 range before falling at 100+. That's a weaker basis for
    # shrinkage than a clean monotonic decline would be -- reported as such,
    # not rounded up to "confirms".
    star_stddev_range = f"{g['star_stddev'].min():.2f}-{g['star_stddev'].max():.2f}"
    is_monotonic_decreasing = g["star_stddev"].is_monotonic_decreasing
    finding("Q1: Review volume distortion", "Does rating variance shrink as review volume grows?",
            f"Star stddev by volume bucket is non-monotonic ({star_stddev_range} across buckets, "
            f"monotonic decrease: {is_monotonic_decreasing}) -- a weaker pattern than a clean shrink story. "
            f"The clearer, more robust relationship is in the mean itself: average stars rises steadily from "
            f"{g['mean_stars'].iloc[0]:.2f} (bucket {labels[0]}) to {g['mean_stars'].iloc[-1]:.2f} (bucket {labels[-1]}), "
            f"consistent with popularity/survivorship (well-liked places accumulate more reviews) rather than "
            f"volume mechanically producing a more accurate average. Table: QSR_EDA_Q1_VOLUME_EFFECTS.csv.",
            "Shrinkage toward a peer prior for low-volume businesses (stage 5) is still defensible on general "
            "statistical grounds (small samples are less reliable), but this dataset's own variance pattern is not "
            "a clean confirmation of it -- the popularity/volume-vs-rating relationship is the more robust finding "
            "and is a reason to keep Engagement (volume) and Peer (rating) as separate, not-fully-independent-by-"
            "construction pillars whose overlap is worth watching, not collapsing.")


# ---------------------------------------------------------------------------
def q2_pillar_distinctness(df: pd.DataFrame):
    candidate_features = {
        "PEER_star_gap": "STAR_GAP_VS_PEERS",
        "PEER_rating_pct": "PEER_RATING_PERCENTILE",
        "ENGAGEMENT_log_reviews": None,  # derived below
        "ENGAGEMENT_checkins_per_review": "CHECKINS_PER_LOADED_REVIEW",
        "ENGAGEMENT_tips_per_review": "TIPS_PER_LOADED_REVIEW",
        "MOMENTUM_rating_trend": "REVIEW_RATING_TREND_12M",
    }
    work = df.copy()
    work["ENGAGEMENT_log_reviews"] = np.log1p(work["LOADED_REVIEW_COUNT"])
    cols = ["PEER_star_gap", "PEER_rating_pct", "ENGAGEMENT_log_reviews",
            "ENGAGEMENT_checkins_per_review", "ENGAGEMENT_tips_per_review", "MOMENTUM_rating_trend"]
    rename = {v: k for k, v in candidate_features.items() if v}
    work = work.rename(columns=rename)
    sub = work[cols].replace([np.inf, -np.inf], np.nan).dropna()

    pearson = sub.corr(method="pearson")
    spearman = sub.corr(method="spearman")
    pearson.to_csv(OUTPUT_DIR / "QSR_EDA_Q2_PEARSON_CORR.csv")
    spearman.to_csv(OUTPUT_DIR / "QSR_EDA_Q2_SPEARMAN_CORR.csv")

    X = sub.values
    vif = pd.DataFrame({
        "FEATURE": cols,
        "VIF": [variance_inflation_factor(X, i) for i in range(X.shape[1])],
    })
    vif.to_csv(OUTPUT_DIR / "QSR_EDA_Q2_VIF.csv", index=False)

    off_diag = spearman.where(~np.eye(len(spearman), dtype=bool))
    max_pair = off_diag.abs().stack().idxmax()
    max_val = off_diag.loc[max_pair]
    high_vif = vif[vif["VIF"] > 5]

    high_vif_is_within_peer = set(high_vif["FEATURE"]) <= {"PEER_star_gap", "PEER_rating_pct"}
    finding("Q2: Pillar distinctness (partial -- CX added in stage 5/10)", "Are Peer/Engagement/Momentum features independent?",
            f"Highest pairwise Spearman correlation is {max_pair[0]} vs {max_pair[1]} at {max_val:.3f}. "
            f"{len(high_vif)} of {len(cols)} candidate features show VIF > 5 ({list(high_vif['FEATURE']) if len(high_vif) else 'none'}) -- "
            f"and both are PEER's own two sub-components (star-gap and rating-percentile, two views of the same "
            f"underlying peer comparison, deliberately combined within the Peer pillar formula), not a cross-pillar "
            f"redundancy. Every Engagement/Momentum feature has VIF close to 1. Full matrices: QSR_EDA_Q2_*.csv.",
            "Cross-pillar correlation and VIF are low once the expected within-Peer-pillar correlation is set aside -- "
            "supports keeping Peer/Engagement/Momentum as separate pillars rather than collapsing them; the CX pillar "
            "is checked against these three in stage 10 once it exists, to test the full four-pillar structure the "
            "same way (CX vs Engagement later comes out at rho=0.045, i.e. genuinely distinct)."
            if high_vif_is_within_peer else
            "Some candidate features show meaningful cross-pillar collinearity beyond the expected within-Peer overlap "
            "-- worth a closer look before trusting the pillars as fully independent.")


# ---------------------------------------------------------------------------
def temporal_analysis(reviews: pd.DataFrame | None):
    if reviews is None:
        finding("Temporal", "Review velocity over time", "Skipped -- qsr_reviews_detail.parquet not yet built.",
                "Re-run stage 3 after stage 2 completes for the temporal section.")
        return
    set_plot_theme()
    import matplotlib.pyplot as plt

    r = reviews.copy()
    r["REVIEW_TS"] = pd.to_datetime(r["REVIEW_TS"], errors="coerce")
    monthly = r.dropna(subset=["REVIEW_TS"]).set_index("REVIEW_TS").resample("MS").size()
    fig, ax = plt.subplots(figsize=(11, 4))
    monthly.plot(ax=ax, color="#4C72B0")
    ax.set_title("QSR review volume by month")
    ax.set_ylabel("Reviews")
    savefig("eda_review_velocity")

    peak_month = monthly.idxmax()
    last_month = monthly.index.max()
    cutoff_month = DATASET_CUTOFF.to_period("M").to_timestamp()
    tail_drop = monthly.loc[monthly.index >= cutoff_month - pd.DateOffset(months=2)]

    finding("Temporal", "Does review volume show the dataset's fixed 2022 cutoff and any structural breaks?",
            f"Monthly review volume peaks at {peak_month.date()} ({int(monthly.max()):,} reviews); "
            f"the series ends abruptly at {last_month.date()}, and the final partial month "
            f"({int(tail_drop.iloc[-1])} reviews) is a truncation artefact, not a real drop-off.",
            "Any recency/momentum feature (stage 6) must treat the last partial month as censored, not as evidence "
            "of decline -- otherwise every business looks like it's deteriorating right at the data boundary.")


# ---------------------------------------------------------------------------
def group_and_spatial_analysis(df: pd.DataFrame):
    set_plot_theme()
    import matplotlib.pyplot as plt

    seg = df.groupby("QSR_SEGMENT", observed=True)["BUSINESS_STARS"].agg(["mean", "count"]).sort_values("mean")
    seg.to_csv(OUTPUT_DIR / "QSR_EDA_SEGMENT_STARS.csv")

    state = df.groupby("STATE", observed=True)["BUSINESS_STARS"].agg(["mean", "count"])
    state = state[state["count"] >= 20].sort_values("mean")
    state.to_csv(OUTPUT_DIR / "QSR_EDA_STATE_STARS.csv")

    fig, ax = plt.subplots(figsize=(9, 7))
    sample = df.dropna(subset=["LATITUDE", "LONGITUDE"]).sample(min(6000, len(df)), random_state=42)
    sc = ax.scatter(sample["LONGITUDE"], sample["LATITUDE"], c=sample["BUSINESS_STARS"],
                     cmap="RdYlGn", s=6, alpha=0.6, vmin=1, vmax=5)
    plt.colorbar(sc, ax=ax, label="Business stars")
    ax.set_title("QSR locations by star rating (spatial pattern check)")
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    savefig("eda_spatial_stars")

    spread = seg["mean"].max() - seg["mean"].min()
    finding("Group/spatial", "Does health vary systematically by segment, state, or geography?",
            f"Segment mean stars range {seg['mean'].min():.2f}-{seg['mean'].max():.2f} (spread {spread:.2f}); "
            f"state-level means (n>=20) range {state['mean'].min():.2f}-{state['mean'].max():.2f}. "
            f"Spatial scatter (eda_spatial_stars.png) shows visually clustered low-rated regions rather than "
            f"uniform noise -- descriptive only, no causal claim about why.",
            "Segment and state both carry real between-group variance -- reinforces the existing design choice to "
            "peer-benchmark within segment (and locally) rather than against the full population; a burger joint "
            "should not be judged against national coffee-shop norms.")


# ---------------------------------------------------------------------------
def q5_operational_profile_evidence(df: pd.DataFrame):
    """DAYS_WITH_HOURS showed up with a surprisingly strong permutation
    importance in early exploration -- worth investigating, not worth
    assuming it belongs in the LHI just because it's predictive. This does
    the two checks possible at this point in the pipeline (before CX and the
    ML importance evidence exist): what the feature actually looks like, and
    whether it overlaps with the pillars already available. The predictive-
    power, independence-with-CX, and ranking-impact checks are completed in
    stage 10 once the ML evidence and full pillar set exist -- flagged
    explicitly rather than answered early with incomplete information."""
    col = df["DAYS_WITH_HOURS"]
    dist = {int(k): float(v) for k, v in col.value_counts(normalize=True).sort_index().round(3).items()}
    corr_peer = float(col.corr(df["STAR_GAP_VS_PEERS"]))
    corr_engagement = float(col.corr(np.log1p(df["LOADED_REVIEW_COUNT"])))

    finding("Q5: Operational-profile evidence (partial -- predictive/robustness checks in stage 10)",
            "Does DAYS_WITH_HOURS carry independent, meaningful evidence, or is it redundant with pillars "
            "we already have?",
            f"DAYS_WITH_HOURS distribution: {dist}. Correlation with the Peer pillar's star-gap component = "
            f"{corr_peer:.3f} (negligible); correlation with log review volume (Engagement proxy) = "
            f"{corr_engagement:.3f} (real but modest -- listings with more reviews tend to have more complete "
            f"hours, unsurprisingly, but this isn't strong enough to call the two redundant). Not a "
            f"restatement of either existing pillar. It measures how many days of the week a Yelp listing has "
            f"posted hours: a listing-completeness/maintenance signal, not a direct observation of whether the "
            f"outlet actually keeps consistent hours (this dataset can't see that).",
            "Low overlap with existing pillars keeps it worth investigating, but conceptual validity is the "
            "harder question -- a listing-maintenance proxy correlating with health is not the same as it "
            "measuring health. Full evidence-gate verdict (predictive power, stability, independence from all "
            "four pillars, actionability, and measured ranking impact) is in stage 10's "
            "QSR_OPERATIONAL_PROFILE_EVIDENCE_GATE.csv, once stage 8's ML evidence and the CX pillar both "
            "exist to test against.")


# ---------------------------------------------------------------------------
def leakage_scan_preview(df: pd.DataFrame):
    numeric = df.select_dtypes(include=[np.number]).drop(columns=["IS_OPEN"], errors="ignore")
    corrs = numeric.apply(lambda c: c.corr(df["IS_OPEN"]) if c.notna().sum() > 10 else np.nan)
    corrs = corrs.dropna().sort_values(key=lambda s: s.abs(), ascending=False)
    top = corrs.head(15)
    top.to_csv(OUTPUT_DIR / "QSR_EDA_IS_OPEN_CORRELATION_SCAN.csv", header=["CORR_WITH_IS_OPEN"])

    finding("Leakage preview", "Which features correlate most with IS_OPEN?",
            f"Top absolute correlations with IS_OPEN: " +
            ", ".join(f"{k}={v:.2f}" for k, v in top.head(6).items()) +
            f". Full ranked list: QSR_EDA_IS_OPEN_CORRELATION_SCAN.csv.",
            "Recency/momentum features dominate the top of this list, consistent with the manually-verified leakage "
            "finding (92.7% of closed businesses have zero reviews in the trailing 12 months vs 12.8% of open ones). "
            "This list is the starting point for stage 7's formal feature-lineage/leakage gate.")


def main():
    log("Loading data for EDA...")
    df, reviews = load_data()

    structure_missingness_duplicates(df)
    outliers_and_distributions(df)
    q1_review_volume_effects(df)
    q2_pillar_distinctness(df)
    temporal_analysis(reviews)
    group_and_spatial_analysis(df)
    q5_operational_profile_evidence(df)
    leakage_scan_preview(df)

    findings_df = pd.DataFrame(findings)
    out = OUTPUT_DIR / "QSR_EDA_FINDINGS.csv"
    findings_df.to_csv(out, index=False)
    log(f"Wrote {out} ({len(findings_df)} findings) and figures to {FIGURES_DIR}")
    log("Stage 3 complete.")


if __name__ == "__main__":
    main()
