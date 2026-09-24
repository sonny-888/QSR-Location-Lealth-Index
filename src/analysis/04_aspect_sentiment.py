"""Stage 4 - Aspect-based sentiment analysis (ABSA).

Transparent heuristic layer (keyword taxonomy + VADER, see lib/absa.py), not
a contextual model -- explicitly disclosed as a limitation, not hidden.
Produces:
  - qsr_review_aspect.parquet: one row per (review, aspect) with sentiment
    and recency weight
  - QSR_ASPECT_BUSINESS_SUMMARY.csv: per-business, per-aspect mean sentiment,
    mention count, negative-mention rate, and aspect coverage (% of that
    business's reviews carrying evidence for the aspect) -- coverage feeds
    the confidence score in stage 12 directly.
Validation is convergent-validity only (aspect sentiment vs star rating,
business-clustered bootstrap CI, monotonicity) plus a small spot-check audit
-- labeled as a lightweight audit, not a multi-annotator gold standard.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import OUTPUT_DIR, DATASET_CUTOFF, ASPECTS, recency_weight, log, require, set_plot_theme, savefig, bootstrap_ci_mean_clustered
from lib.absa import score_review

REPORT_EVERY = 100_000


def score_all_reviews(reviews: pd.DataFrame) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for i, r in enumerate(reviews.itertuples(index=False)):
        for hit in score_review(r.REVIEW_TEXT):
            rows.append((r.REVIEW_ID, r.BUSINESS_ID, r.STARS, r.REVIEW_TS, hit["ASPECT"], hit["SENTIMENT"], hit["N_SENTENCES"]))
        if (i + 1) % REPORT_EVERY == 0:
            log(f"...scored {i + 1:,}/{len(reviews):,} reviews in {time.time() - t0:.0f}s")
    log(f"Finished scoring {len(reviews):,} reviews in {time.time() - t0:.0f}s -> {len(rows):,} review-aspect rows")
    return pd.DataFrame(rows, columns=["REVIEW_ID", "BUSINESS_ID", "STARS", "REVIEW_TS", "ASPECT", "SENTIMENT", "N_SENTENCES"])


def business_aspect_summary(review_aspect: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    ra = review_aspect.copy()
    ra["REVIEW_TS"] = pd.to_datetime(ra["REVIEW_TS"], errors="coerce")
    ra["AGE_DAYS"] = (DATASET_CUTOFF - ra["REVIEW_TS"]).dt.days.clip(lower=0)
    ra["RECENCY_WEIGHT"] = recency_weight(ra["AGE_DAYS"])
    ra["IS_NEGATIVE"] = ra["SENTIMENT"] < -0.05

    total_reviews_per_biz = reviews.groupby("BUSINESS_ID").size().rename("TOTAL_REVIEWS")

    summaries = []
    for aspect in ASPECTS:
        sub = ra[ra["ASPECT"] == aspect]
        g = sub.groupby("BUSINESS_ID").apply(
            lambda x: pd.Series({
                "N_MENTIONS": len(x),
                "RAW_MEAN_SENTIMENT": x["SENTIMENT"].mean(),
                "RECENCY_WEIGHTED_SENTIMENT": np.average(x["SENTIMENT"], weights=x["RECENCY_WEIGHT"]) if len(x) else np.nan,
                "NEGATIVE_MENTION_RATE": x["IS_NEGATIVE"].mean(),
            }), include_groups=False
        ).reset_index()
        g["ASPECT"] = aspect
        summaries.append(g)

    out = pd.concat(summaries, ignore_index=True)
    out = out.merge(total_reviews_per_biz, on="BUSINESS_ID", how="right")
    out["ASPECT"] = out["ASPECT"].fillna("__NONE__")
    out["N_MENTIONS"] = out["N_MENTIONS"].fillna(0)
    out["ASPECT_COVERAGE_PCT"] = (out["N_MENTIONS"] / out["TOTAL_REVIEWS"] * 100).round(2)
    return out[out["ASPECT"] != "__NONE__"]


def convergent_validity(review_aspect: pd.DataFrame):
    set_plot_theme()
    import matplotlib.pyplot as plt

    rows = []
    fig, ax = plt.subplots(figsize=(9, 5))
    for aspect in ASPECTS:
        sub = review_aspect[review_aspect["ASPECT"] == aspect]
        if len(sub) < 30:
            continue
        rho, p = stats.spearmanr(sub["STARS"], sub["SENTIMENT"])
        point, lo, hi = bootstrap_ci_mean_clustered(sub.assign(_val=sub["SENTIMENT"]), "_val", "BUSINESS_ID", n_boot=500)
        by_star = sub.groupby("STARS")["SENTIMENT"].mean()
        monotonic = by_star.is_monotonic_increasing
        rows.append({"ASPECT": aspect, "N": len(sub), "SPEARMAN_RHO": round(rho, 4), "P_VALUE": p,
                      "MONOTONIC_VS_STARS": monotonic, "CLUSTER_BOOTSTRAP_MEAN": round(point, 4),
                      "CI_LOW": round(lo, 4), "CI_HIGH": round(hi, 4)})
        ax.plot(by_star.index, by_star.values, marker="o", label=aspect)

    ax.set_xlabel("Yelp review star rating"); ax.set_ylabel("Mean aspect sentiment (-1 to +1)")
    ax.set_title("Aspect sentiment vs star rating (convergent validity, stars excluded from scoring)")
    ax.legend(fontsize=8)
    savefig("absa_convergent_validity")

    val_df = pd.DataFrame(rows)
    val_df.to_csv(OUTPUT_DIR / "QSR_ABSA_CONVERGENT_VALIDITY.csv", index=False)
    log(f"Convergent validity: {val_df[['ASPECT','SPEARMAN_RHO','MONOTONIC_VS_STARS']].to_string(index=False)}")
    return val_df


def spot_check_sample(reviews: pd.DataFrame, review_aspect: pd.DataFrame, n=180, seed=42):
    """Random review sample paired with its predicted aspects/sentiment, for
    a lightweight human audit -- explicitly not a multi-annotator gold set."""
    sample_ids = reviews["REVIEW_ID"].sample(min(n, len(reviews)), random_state=seed)
    sample_reviews = reviews[reviews["REVIEW_ID"].isin(sample_ids)][["REVIEW_ID", "STARS", "REVIEW_TEXT"]]
    sample_aspects = review_aspect[review_aspect["REVIEW_ID"].isin(sample_ids)]
    merged = sample_reviews.merge(
        sample_aspects.groupby("REVIEW_ID").apply(
            lambda x: "; ".join(f"{a}:{s:.2f}" for a, s in zip(x["ASPECT"], x["SENTIMENT"])), include_groups=False
        ).rename("PREDICTED_ASPECTS").reset_index(),
        on="REVIEW_ID", how="left",
    )
    merged["PREDICTED_ASPECTS"] = merged["PREDICTED_ASPECTS"].fillna("(no aspect matched)")
    merged.to_csv(OUTPUT_DIR / "QSR_ABSA_SPOT_CHECK_SAMPLE.csv", index=False)
    log(f"Wrote {len(merged)}-review spot-check sample to QSR_ABSA_SPOT_CHECK_SAMPLE.csv for manual audit")
    return merged


def main():
    reviews_path = OUTPUT_DIR / "qsr_reviews_detail.parquet"
    require(reviews_path.exists(), f"Missing {reviews_path} -- run stage 2 first")
    reviews = pd.read_parquet(reviews_path)
    reviews = reviews[reviews["REVIEW_TEXT"].notna() & (reviews["REVIEW_TEXT"].str.len() > 0)]
    log(f"Loaded {len(reviews):,} reviews with text")

    review_aspect = score_all_reviews(reviews)
    review_aspect.to_parquet(OUTPUT_DIR / "qsr_review_aspect.parquet", index=False)

    coverage_pct = review_aspect["REVIEW_ID"].nunique() / len(reviews) * 100
    log(f"Aspect coverage: {coverage_pct:.2f}% of reviews carry at least one aspect mention")

    summary = business_aspect_summary(review_aspect, reviews)
    summary.to_csv(OUTPUT_DIR / "QSR_ASPECT_BUSINESS_SUMMARY.csv", index=False)

    convergent_validity(review_aspect)
    spot_check_sample(reviews, review_aspect)

    log("Stage 4 complete.")


if __name__ == "__main__":
    main()
