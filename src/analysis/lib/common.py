"""Shared helpers for the QSR LHI pipeline: paths, fail-loud assertions,
percentile/shrinkage utilities, bootstrap CIs, and a consistent plot theme.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "analysis"
OUTPUT_DIR = ANALYSIS_DIR / "output"
FIGURES_DIR = ANALYSIS_DIR / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_RUN_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
MODEL_VERSION = "qsr-lhi-pipeline-v1"

# Fixed dataset cutoff shared by every row in the source export (verified
# during EDA: DATASET_MAX_REVIEW_TS has exactly one distinct value).
DATASET_CUTOFF = pd.Timestamp("2022-01-19 19:48:45")

ASPECTS = ["FOOD", "SERVICE", "STAFF", "CLEANLINESS", "WAITING_TIME", "ORDER_ACCURACY", "VALUE"]

# Risk-band scheme: fixed raw-score cutoffs on the 0-100 LHI scale, not
# percentile-of-population. Chosen over percentile bands because percentile
# bands always split into the same fixed shares by construction (e.g. exactly
# the top 50% is "Healthy," always, no matter how the whole portfolio's score
# distribution shifts) -- that makes them useless for tracking whether the
# portfolio is actually getting healthier over time, which the brief asks
# for ("ongoing performance monitoring"). A fixed threshold can move.
# 60 is a deliberately round, business-meaningful cutoff (top ~30% of the
# scored population in this run), not a statistically derived one -- that is
# disclosed everywhere this constant is used, not hidden behind a formula.
RISK_BAND_EDGES = [0, 25, 40, 60, 100]
RISK_BAND_LABELS = ["Critical Risk", "High Risk", "Watch", "Healthy"]


def risk_band(lhi: pd.Series) -> pd.Series:
    """Fixed raw-score risk band -- see RISK_BAND_EDGES for the rationale."""
    return pd.cut(lhi, bins=RISK_BAND_EDGES, labels=RISK_BAND_LABELS, include_lowest=True)


# ---------------------------------------------------------------------------
# Fail-loud assertions
# ---------------------------------------------------------------------------
class DataIntegrityError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    """Fail loudly instead of continuing on a broken assumption."""
    if not condition:
        raise DataIntegrityError(message)


def require_unique_key(df: pd.DataFrame, key: str, label: str) -> None:
    n = len(df)
    n_unique = df[key].nunique(dropna=False)
    require(
        n == n_unique,
        f"{label}: expected one row per {key} ({n_unique} unique) but got {n} rows "
        f"({n - n_unique} duplicate keys).",
    )


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Percentile / shrinkage utilities
# ---------------------------------------------------------------------------
def percentile_rank(series: pd.Series) -> pd.Series:
    """Empirical percentile (0-100) with midranks for ties; NaN stays NaN."""
    return series.rank(pct=True, method="average", na_option="keep") * 100.0


def shrink_to_prior(raw_mean: pd.Series, n_effective: pd.Series, prior: pd.Series,
                     prior_strength: float = 10.0) -> pd.Series:
    """Bayesian-style shrinkage toward a peer prior for low-evidence rows."""
    return (n_effective * raw_mean + prior_strength * prior) / (n_effective + prior_strength)


def recency_weight(age_days: pd.Series, half_life_days: float = 365.0) -> pd.Series:
    return 0.5 ** (age_days / half_life_days)


# ---------------------------------------------------------------------------
# Bootstrap CIs (business-clustered where relevant)
# ---------------------------------------------------------------------------
def bootstrap_ci_mean(values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05,
                       random_state: int = 42) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) via simple nonparametric bootstrap."""
    rng = np.random.default_rng(random_state)
    values = np.asarray(values)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return (np.nan, np.nan, np.nan)
    boot_means = np.empty(n_boot)
    n = len(values)
    for i in range(n_boot):
        sample = values[rng.integers(0, n, n)]
        boot_means[i] = sample.mean()
    lo, hi = np.percentile(boot_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(values.mean()), float(lo), float(hi))


def bootstrap_ci_mean_clustered(df: pd.DataFrame, value_col: str, cluster_col: str,
                                 n_boot: int = 2000, alpha: float = 0.05,
                                 random_state: int = 42) -> tuple[float, float, float]:
    """Cluster (business-level) bootstrap: resample clusters, not rows, so that
    reviews from one business aren't treated as independent observations."""
    rng = np.random.default_rng(random_state)
    clusters = df[cluster_col].unique()
    n_clusters = len(clusters)
    grouped = {c: g[value_col].dropna().values for c, g in df.groupby(cluster_col)}
    point = df[value_col].mean()
    boot_means = np.empty(n_boot)
    for i in range(n_boot):
        sampled_clusters = rng.choice(clusters, n_clusters, replace=True)
        vals = np.concatenate([grouped[c] for c in sampled_clusters if len(grouped[c])])
        boot_means[i] = vals.mean() if len(vals) else np.nan
    lo, hi = np.nanpercentile(boot_means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(point), float(lo), float(hi))


# ---------------------------------------------------------------------------
# Plot theme
# ---------------------------------------------------------------------------
def set_plot_theme():
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid", palette="deep", font_scale=1.0)
    plt.rcParams.update({
        "figure.figsize": (9, 5),
        "figure.dpi": 110,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "savefig.bbox": "tight",
    })


def extract_positive_class_shap(shap_values) -> np.ndarray:
    """Normalize SHAP TreeExplainer output for a binary classifier across
    shap versions: some return a list [class0_array, class1_array], newer
    ones return a single (n_samples, n_features, n_classes) array."""
    if isinstance(shap_values, list):
        return shap_values[1]
    arr = np.asarray(shap_values)
    if arr.ndim == 3:
        return arr[:, :, 1]
    return arr


def savefig(name: str):
    import matplotlib.pyplot as plt
    plt.savefig(FIGURES_DIR / f"{name}.png")
    plt.close()
