"""Stage 6 - Momentum / trajectory, separate from current health.

Recent-vs-prior window comparison (12 months each, relative to the dataset's
fixed cutoff 2022-01-19 -- appropriate for "as of the last available data"
framing on open businesses; stage 3's EDA flagged the final partial month as
a truncation artefact, handled by anchoring windows at the cutoff rather than
using the ragged last month alone). Every direction flag is backed by a
bootstrap CI on the recent-vs-prior delta, not a raw sign check. Businesses
without enough reviews in both windows get an explicit "Insufficient
Evidence" flag rather than a fabricated trend -- feeds stage 12's fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import OUTPUT_DIR, DATASET_CUTOFF, recency_weight, require, log

MIN_REVIEWS_PER_WINDOW = 5
MIN_ASPECT_MENTIONS_PER_WINDOW = 3
N_BOOT = 1000
RNG = np.random.default_rng(42)

RECENT_START = DATASET_CUTOFF - pd.Timedelta(days=365)
PRIOR_START = DATASET_CUTOFF - pd.Timedelta(days=730)

# Negative-spike detection: a location can be flat on the 12-month trajectory
# above while still absorbing a sharp recent cluster of bad reviews -- the
# annual window structurally cannot see that. 1-2 stars = "negative" (the
# standard Yelp low-rating convention). Baseline is the 12 months immediately
# preceding each recent window (non-overlapping), so every comparison is
# windowed-recent vs a stable prior norm, not two different-length periods.
# SPIKE_MAGNITUDE_MIN is a practical-significance floor on top of the CI --
# a statistically real but 1-point-percentage shift isn't an operational
# "spike"; both a significant CI *and* a real-sized shift are required.
NEGATIVE_STAR_MAX = 2
SPIKE_PRIMARY_WINDOW_DAYS = 60
SPIKE_SENSITIVITY_WINDOWS_DAYS = [30, 90]
SPIKE_MIN_REVIEWS = 5
SPIKE_MAGNITUDE_MIN = 0.10


def two_sample_bootstrap_delta(recent: np.ndarray, prior: np.ndarray, n_boot=N_BOOT):
    if len(recent) < 2 or len(prior) < 2:
        return (np.nan, np.nan, np.nan)
    point = recent.mean() - prior.mean()
    boot = np.empty(n_boot)
    for i in range(n_boot):
        r = recent[RNG.integers(0, len(recent), len(recent))]
        p = prior[RNG.integers(0, len(prior), len(prior))]
        boot[i] = r.mean() - p.mean()
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return (float(point), float(lo), float(hi))


def classify_direction(ci_low, ci_high):
    if np.isnan(ci_low):
        return "Insufficient Evidence"
    if ci_low > 0:
        return "Improving"
    if ci_high < 0:
        return "Deteriorating"
    return "Stable"


def rating_trajectory(reviews: pd.DataFrame) -> pd.DataFrame:
    r = reviews.copy()
    r["REVIEW_TS"] = pd.to_datetime(r["REVIEW_TS"], errors="coerce")
    rows = []
    for bid, g in r.groupby("BUSINESS_ID"):
        recent = g.loc[g["REVIEW_TS"] > RECENT_START, "STARS"].dropna().values
        prior = g.loc[(g["REVIEW_TS"] > PRIOR_START) & (g["REVIEW_TS"] <= RECENT_START), "STARS"].dropna().values
        if len(recent) < MIN_REVIEWS_PER_WINDOW or len(prior) < MIN_REVIEWS_PER_WINDOW:
            rows.append((bid, len(recent), len(prior), np.nan, np.nan, np.nan, "Insufficient Evidence",
                         np.nan, np.nan))
            continue
        delta, lo, hi = two_sample_bootstrap_delta(recent, prior)
        rows.append((bid, len(recent), len(prior), delta, lo, hi, classify_direction(lo, hi),
                     float(recent.mean()), float(prior.mean())))
    return pd.DataFrame(rows, columns=["BUSINESS_ID", "RECENT_REVIEW_COUNT", "PRIOR_REVIEW_COUNT",
                                        "RATING_DELTA", "RATING_DELTA_CI_LOW", "RATING_DELTA_CI_HIGH",
                                        "RATING_TRAJECTORY", "RECENT_MEAN_STARS", "PRIOR_MEAN_STARS"])


def aspect_trajectory(review_aspect: pd.DataFrame) -> pd.DataFrame:
    ra = review_aspect.copy()
    ra["REVIEW_TS"] = pd.to_datetime(ra["REVIEW_TS"], errors="coerce")
    rows = []
    for (bid, aspect), g in ra.groupby(["BUSINESS_ID", "ASPECT"]):
        recent = g.loc[g["REVIEW_TS"] > RECENT_START, "SENTIMENT"].dropna().values
        prior = g.loc[(g["REVIEW_TS"] > PRIOR_START) & (g["REVIEW_TS"] <= RECENT_START), "SENTIMENT"].dropna().values
        if len(recent) < MIN_ASPECT_MENTIONS_PER_WINDOW or len(prior) < MIN_ASPECT_MENTIONS_PER_WINDOW:
            rows.append((bid, aspect, len(recent), len(prior), np.nan, np.nan, np.nan, "Insufficient Evidence"))
            continue
        delta, lo, hi = two_sample_bootstrap_delta(recent, prior, n_boot=500)
        rows.append((bid, aspect, len(recent), len(prior), delta, lo, hi, classify_direction(lo, hi)))
    return pd.DataFrame(rows, columns=["BUSINESS_ID", "ASPECT", "RECENT_MENTIONS", "PRIOR_MENTIONS",
                                        "ASPECT_SENTIMENT_DELTA", "CI_LOW", "CI_HIGH", "ASPECT_TRAJECTORY"])


def recency_weighted_rating(reviews: pd.DataFrame) -> pd.DataFrame:
    """Business-level recency-weighted average star rating (365-day half-
    life, same decay used for aspect sentiment) -- a continuous complement to
    the windowed RATING_TRAJECTORY above: it answers "what does this
    business's rating look like once older reviews count for less," not
    "did the average shift between two fixed windows."
    """
    r = reviews.copy()
    r["REVIEW_TS"] = pd.to_datetime(r["REVIEW_TS"], errors="coerce")
    r["AGE_DAYS"] = (DATASET_CUTOFF - r["REVIEW_TS"]).dt.days.clip(lower=0)
    r["W"] = recency_weight(r["AGE_DAYS"])

    def _agg(x):
        return pd.Series({
            "RECENCY_WEIGHTED_STARS": np.average(x["STARS"], weights=x["W"]) if len(x) else np.nan,
            "RAW_AVG_STARS": x["STARS"].mean(),
        })

    g = r.groupby("BUSINESS_ID").apply(_agg, include_groups=False).reset_index()
    g["RECENCY_VS_RAW_GAP"] = g["RECENCY_WEIGHTED_STARS"] - g["RAW_AVG_STARS"]
    return g


def negative_spike_detector(reviews: pd.DataFrame) -> pd.DataFrame:
    """Recent-vs-baseline negative-review-rate shift at 60 days (primary,
    bootstrap-CI-backed), cross-checked at 30 and 90 days (point-estimate
    only, for consistency -- not bootstrapped, to keep this a single pass
    over the review data rather than three)."""
    r = reviews.copy()
    r["REVIEW_TS"] = pd.to_datetime(r["REVIEW_TS"], errors="coerce")
    r["IS_NEGATIVE"] = (r["STARS"] <= NEGATIVE_STAR_MAX).astype(float)

    windows = [SPIKE_PRIMARY_WINDOW_DAYS] + SPIKE_SENSITIVITY_WINDOWS_DAYS

    rows = []
    for bid, g in r.groupby("BUSINESS_ID"):
        row = {"BUSINESS_ID": bid}
        for days in windows:
            recent_start = DATASET_CUTOFF - pd.Timedelta(days=days)
            baseline_end = recent_start
            baseline_start = baseline_end - pd.Timedelta(days=365)
            recent = g.loc[g["REVIEW_TS"] > recent_start, "IS_NEGATIVE"].dropna().values
            baseline = g.loc[(g["REVIEW_TS"] > baseline_start) & (g["REVIEW_TS"] <= baseline_end),
                              "IS_NEGATIVE"].dropna().values
            enough = len(recent) >= SPIKE_MIN_REVIEWS and len(baseline) >= SPIKE_MIN_REVIEWS

            if days == SPIKE_PRIMARY_WINDOW_DAYS:
                if not enough:
                    row.update({"SPIKE_RECENT_N": len(recent), "SPIKE_BASELINE_N": len(baseline),
                                "SPIKE_RECENT_NEGATIVE_RATE": np.nan, "SPIKE_BASELINE_NEGATIVE_RATE": np.nan,
                                "SPIKE_RATE_DELTA": np.nan, "SPIKE_DELTA_CI_LOW": np.nan,
                                "SPIKE_DELTA_CI_HIGH": np.nan, "SPIKE_DETECTED": False})
                    continue
                delta, lo, hi = two_sample_bootstrap_delta(recent, baseline, n_boot=500)
                row.update({
                    "SPIKE_RECENT_N": len(recent), "SPIKE_BASELINE_N": len(baseline),
                    "SPIKE_RECENT_NEGATIVE_RATE": float(recent.mean()),
                    "SPIKE_BASELINE_NEGATIVE_RATE": float(baseline.mean()),
                    "SPIKE_RATE_DELTA": delta, "SPIKE_DELTA_CI_LOW": lo, "SPIKE_DELTA_CI_HIGH": hi,
                    "SPIKE_DETECTED": bool(lo > 0 and delta >= SPIKE_MAGNITUDE_MIN),
                })
            else:
                prefix = f"SPIKE_{days}D"
                if not enough:
                    row[f"{prefix}_DELTA"] = np.nan
                    row[f"{prefix}_FLAG"] = False
                    continue
                delta = float(recent.mean() - baseline.mean())
                row[f"{prefix}_DELTA"] = delta
                row[f"{prefix}_FLAG"] = bool(delta >= SPIKE_MAGNITUDE_MIN)
        rows.append(row)

    out = pd.DataFrame(rows)
    out["SPIKE_STATUS"] = np.select(
        [out["SPIKE_DETECTED"], out["SPIKE_RATE_DELTA"] > 0, out["SPIKE_RATE_DELTA"].isna()],
        ["Spike Detected", "Elevated (not significant)", "Insufficient Evidence"],
        default="No Spike",
    )
    return out


def main():
    reviews_path = OUTPUT_DIR / "qsr_reviews_detail.parquet"
    aspect_path = OUTPUT_DIR / "qsr_review_aspect.parquet"
    require(reviews_path.exists(), f"Missing {reviews_path} -- run stage 2 first")
    require(aspect_path.exists(), f"Missing {aspect_path} -- run stage 4 first")

    reviews = pd.read_parquet(reviews_path, columns=["BUSINESS_ID", "STARS", "REVIEW_TS"])
    review_aspect = pd.read_parquet(aspect_path)

    log("Computing rating trajectory (recent vs prior 12-month windows)...")
    rating_traj = rating_trajectory(reviews)
    rating_traj.to_csv(OUTPUT_DIR / "QSR_RATING_TRAJECTORY.csv", index=False)
    log(f"Rating trajectory distribution: {rating_traj['RATING_TRAJECTORY'].value_counts().to_dict()}")

    log("Computing aspect-sentiment trajectory...")
    aspect_traj = aspect_trajectory(review_aspect)
    aspect_traj.to_csv(OUTPUT_DIR / "QSR_ASPECT_TRAJECTORY.csv", index=False)
    oa_traj = aspect_traj[aspect_traj["ASPECT"] == "ORDER_ACCURACY"]
    log(f"Order Accuracy trajectory (recent-vs-prior movement, n={len(oa_traj)}): "
        f"{oa_traj['ASPECT_TRAJECTORY'].value_counts().to_dict()}")

    log("Computing recency-weighted star rating...")
    recency_stars = recency_weighted_rating(reviews)
    recency_stars.to_csv(OUTPUT_DIR / "QSR_RECENCY_WEIGHTED_RATING.csv", index=False)

    log(f"Detecting negative-review spikes ({SPIKE_PRIMARY_WINDOW_DAYS}-day primary window, "
        f"{SPIKE_SENSITIVITY_WINDOWS_DAYS}-day sensitivity checks)...")
    spikes = negative_spike_detector(reviews)
    spikes.to_csv(OUTPUT_DIR / "QSR_NEGATIVE_SPIKE.csv", index=False)
    log(f"Spike status distribution: {spikes['SPIKE_STATUS'].value_counts().to_dict()}")

    # Volume momentum -- magnitude context only, not used to set direction.
    rating_traj["VOLUME_MOMENTUM_LOG"] = (
        np.log1p(rating_traj["RECENT_REVIEW_COUNT"]) - np.log1p(rating_traj["PRIOR_REVIEW_COUNT"])
    )

    # Business-level composite direction: rating trajectory is the primary
    # signal (available for virtually every business with any recent
    # activity); aspect trajectories feed "reason for change" in stage 11,
    # not the direction flag itself, to avoid double-counting the same
    # underlying review text twice.
    worst_aspect = (
        aspect_traj[aspect_traj["ASPECT_TRAJECTORY"] == "Deteriorating"]
        .sort_values("ASPECT_SENTIMENT_DELTA")
        .groupby("BUSINESS_ID")
        .first()[["ASPECT", "ASPECT_SENTIMENT_DELTA"]]
        .rename(columns={"ASPECT": "TOP_DETERIORATING_ASPECT", "ASPECT_SENTIMENT_DELTA": "TOP_DETERIORATING_DELTA"})
    )

    out = rating_traj.merge(worst_aspect, on="BUSINESS_ID", how="left")
    out = out.merge(recency_stars[["BUSINESS_ID", "RECENCY_WEIGHTED_STARS", "RECENCY_VS_RAW_GAP"]],
                     on="BUSINESS_ID", how="left")
    spike_cols = ["BUSINESS_ID", "SPIKE_DETECTED", "SPIKE_STATUS",
                  "SPIKE_RECENT_NEGATIVE_RATE", "SPIKE_BASELINE_NEGATIVE_RATE", "SPIKE_RATE_DELTA",
                  "SPIKE_30D_FLAG", "SPIKE_90D_FLAG"]
    out = out.merge(spikes[spike_cols], on="BUSINESS_ID", how="left")
    out.to_csv(OUTPUT_DIR / "QSR_TRAJECTORY_FINAL.csv", index=False)

    log("Stage 6 complete.")


if __name__ == "__main__":
    main()
