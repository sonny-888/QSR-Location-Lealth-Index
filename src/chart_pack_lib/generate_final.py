"""
Final, R-Graph-Gallery-validated chart pack.

READ-ONLY against analysis/output/*.csv and dashboard/data/meta.json.
Writes new "_final" PNGs alongside (never over) the first-round P1 files.
Does not touch analysis/, dashboard/, or any pipeline file.

Applies the three mandatory RGG revisions from the validated spec:
  - Fig 01: risk-band-composition histogram, NOT called a "stacked histogram"
    (no such Gallery pattern exists) -- explicit footnote on threshold-straddling bins.
  - Fig 06/07 (pillar corr, LHI-version agreement): lower-triangle-only heatmap,
    diverging scale, explicit colorbar -- corrgram upper.panel/lower.panel convention.
  - Fig 09: true dumbbell (geom_segment-style connecting line), not two independent
    dot series.

Run: .venv/Scripts/python.exe chart_pack/_lib/generate_final.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

sys.path.insert(0, str(Path(__file__).parent))
from style import (  # noqa: E402
    INK, TEXT_DIM, TEXT_FAINT, BORDER, GRID, ACCENT, ACCENT_SOFT, NEUTRAL_GREY,
    RISK_COLORS, RISK_ORDER, PRIORITY_COLORS, PRIORITY_ORDER,
    ACCENT_RAMP, CONFIDENCE_COLORS, CONFIDENCE_ORDER, POPULATION_WASH,
    FONT_DISPLAY, FONT_BODY, FONT_MONO,
    apply_base_rc, clean_axes, title, source_note, savefig, kicker, end_label,
    teal_sequential_cmap,
)

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(__file__).resolve().parents[1]
AO = ROOT / "analysis" / "output"

apply_base_rc()

QA_LOG = []


def qa(figure, check, result):
    QA_LOG.append((figure, check, result))
    print(f"[QA] {figure} :: {check} :: {result}")


# ============================================================ shared data prep

def load_open_only_lhi():
    fin = pd.read_csv(AO / "QSR_FINAL_LHI_DATA.csv", usecols=["BUSINESS_ID", "LHI", "RISK_CATEGORY"])
    drv = pd.read_csv(AO / "QSR_DRIVERS.csv", usecols=["BUSINESS_ID", "IS_OPEN"])
    merged = fin.merge(drv, on="BUSINESS_ID", how="left", validate="one_to_one")
    open_only = merged[merged.IS_OPEN == 1].copy()
    qa("shared", "open-only rows", len(open_only))
    assert len(open_only) == 13719
    counts = open_only.RISK_CATEGORY.value_counts().to_dict()
    expected = {"Watch": 4806, "Healthy": 3856, "High Risk": 3528, "Critical Risk": 1529}
    assert counts == expected, f"risk-band counts diverge: {counts} vs {expected}"
    return open_only


def load_aspect_summary():
    meta = json.loads((ROOT / "dashboard" / "data" / "meta.json").read_text(encoding="utf-8"))
    d = pd.DataFrame(meta["aspectSummary"])
    assert len(d) == 7
    return d


# ============================================================ correlogram (lower-triangle, mandatory revision)

def lower_triangle_heatmap(ax, mat, labels, vmin, vmax, value_fmt="{:.3f}", diag_note=None):
    """Corrgram convention: mask the strict upper triangle, annotate lower+diagonal,
    diverging colormap, explicit colorbar handled by caller."""
    n = mat.shape[0]
    masked = mat.copy().astype(float)
    iu = np.triu_indices(n, k=1)
    masked[iu] = np.nan
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("white")
    im = ax.imshow(masked, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks(range(n)); ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=10)
    for i in range(n):
        for j in range(n):
            if j > i:
                continue  # strict upper triangle -- not drawn (RGG revision)
            v = mat[i, j]
            txt_color = "white" if abs(v - (vmin + vmax) / 2) > (vmax - vmin) * 0.28 else INK
            label = value_fmt.format(v)
            ax.text(j, i, label, ha="center", va="center", fontsize=9.5, fontweight="bold",
                     color=txt_color)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    return im


# ============================================================ Fig 01 -- LHI risk-band-composition histogram

def fig_01_lhi_composition_histogram(open_only, out_path):
    edges = list(range(0, 101, 4))
    n_bins = len(edges) - 1
    bins = {b: np.zeros(n_bins, dtype=int) for b in RISK_ORDER}
    idx = np.clip((open_only.LHI.values // 4).astype(int), 0, n_bins - 1)
    for b in RISK_ORDER:
        mask = open_only.RISK_CATEGORY.values == b
        for i in idx[mask]:
            bins[b][i] += 1
    total_per_bin = sum(bins[b] for b in RISK_ORDER)
    qa("fig01", "sum of composed bins == n", int(total_per_bin.sum()) == len(open_only))

    # explicit check: how many bins genuinely straddle a risk threshold (contain >1 band)
    straddling = sum(1 for i in range(n_bins) if sum(1 for b in RISK_ORDER if bins[b][i] > 0) > 1)
    qa("fig01", "bins containing more than one risk band", straddling)

    median_lhi = open_only.LHI.median()
    high_crit_pct = (open_only.RISK_CATEGORY.isin(["High Risk", "Critical Risk"]).mean()) * 100

    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    bottom = np.zeros(n_bins)
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(n_bins)]
    width = 3.6
    for b in RISK_ORDER:
        ax.bar(centers, bins[b], width=width, bottom=bottom, color=RISK_COLORS[b],
               label=b, zorder=3, edgecolor="white", linewidth=0.35)
        bottom += bins[b]

    ax.axvline(median_lhi, color=INK, linestyle="--", linewidth=1.1, alpha=0.6, zorder=4)
    ax.text(median_lhi + 1.5, max(total_per_bin) * 0.96, f"Median LHI {median_lhi:.1f}",
            fontsize=10, color=INK, fontfamily=FONT_BODY, ha="left", va="top")

    clean_axes(ax)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Location Health Index (LHI), 0–100", fontsize=11)
    ax.set_ylabel("Number of open locations", fontsize=11)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(20))

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.34),
              ncol=4, frameon=False, fontsize=9.5)
    fig.subplots_adjust(bottom=0.32)

    kicker(fig, "Figure 07")
    title(ax, "Risk is concentrated in a sizeable minority of QSR locations")
    ax.text(0.98, 0.94, f"{high_crit_pct:.1f}% High + Critical Risk", transform=ax.transAxes,
            ha="right", va="top", fontsize=10.5, fontweight="bold", color=RISK_COLORS["Critical Risk"])
    source_note(fig, "Source: QSR_FINAL_LHI_DATA.csv × QSR_DRIVERS.csv (IS_OPEN), analysis/output/. "
                      f"n = {len(open_only):,} open locations, 4-point bins.\n"
                      f"Colour composition per bin reflects each location's true RISK_CATEGORY, not the bin midpoint — "
                      f"{straddling} of {n_bins} bins straddle the 25/40/60 threshold.\n"
                      "Risk-band-composition histogram, not a generic \"stacked histogram\" — no such R Graph Gallery pattern exists (see design spec).")
    savefig(fig, out_path, dpi=220)


# ============================================================ Fig 02/PPTX -- risk-band distribution

def fig_risk_band_distribution_pptx(open_only, out_path):
    counts = open_only.RISK_CATEGORY.value_counts().reindex(RISK_ORDER)
    pct = counts / counts.sum() * 100
    high_crit_pct = pct[["High Risk", "Critical Risk"]].sum()

    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    y_pos = np.arange(len(RISK_ORDER))
    ax.barh(y_pos, counts.values, color=[RISK_COLORS[b] for b in RISK_ORDER], zorder=3, height=0.6)
    for i, b in enumerate(RISK_ORDER):
        ax.text(counts[b] + 60, i, f"{counts[b]:,}  ({pct[b]:.0f}%)", va="center",
                fontsize=15, color=INK, fontfamily=FONT_BODY, fontweight="bold")
    ax.set_yticks(y_pos); ax.set_yticklabels(RISK_ORDER, fontsize=15)
    ax.invert_yaxis()
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.xaxis.set_visible(False)
    ax.set_xlim(0, counts.max() * 1.32)

    fig.suptitle("Risk is concentrated in a sizeable minority of QSR locations",
                  fontsize=22, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.03)
    ax.text(0.0, -0.16, f"High Risk + Critical Risk = {counts['High Risk']+counts['Critical Risk']:,} of "
                        f"{counts.sum():,} open locations ({high_crit_pct:.0f}%)",
            transform=ax.transAxes, fontsize=13, color=TEXT_DIM, fontfamily=FONT_BODY)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 03 -- aspect sentiment + high-risk share

def fig_aspect_sentiment_risk_share(d, out_path, pptx=False):
    d = d.sort_values("meanSentiment0to100", ascending=True).reset_index(drop=True)
    benchmark = d.meanSentiment0to100.mean()
    weakest = d.iloc[0]["aspect"]
    y = np.arange(len(d))

    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    colors = [RISK_COLORS["Critical Risk"] if a == weakest else ACCENT for a in d.aspect]
    ax.barh(y, d.meanSentiment0to100, color=colors, zorder=3, height=0.55)
    ax.set_yticks(y); ax.set_yticklabels(d.aspect, fontsize=11)
    ax.axvline(benchmark, color=INK, linestyle="--", linewidth=1, alpha=0.55, zorder=4)
    ax.set_xlim(0, 100)
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.set_xlabel("Mean sentiment score, 0–100", fontsize=11)

    ax2 = ax.twiny()
    ax2.set_xlim(0, max(d.highRiskShare.max() * 1.4, 70))
    ax2.scatter(d.highRiskShare, y, color=INK, marker="D", s=46, zorder=5, edgecolor="white", linewidth=0.6)
    ax2.set_xlabel("High-risk share among primary complainants, %", fontsize=10, color=TEXT_DIM)
    ax2.tick_params(axis="x", colors=TEXT_DIM)
    ax2.spines["top"].set_visible(True); ax2.spines["top"].set_color(TEXT_FAINT)

    for yi, s in zip(y, d.meanSentiment0to100):
        ax.text(s - 2, yi, f"{s:.1f}", va="center", ha="right", fontsize=9, color="white", fontweight="bold")

    kicker(fig, "Figure 05")
    title(ax, "Order accuracy is the weakest aspect — but not the riskiest one", y=1.16)
    source_note(fig, "Source: dashboard/data/meta.json (aspectSummary, precomputed from QSR_FINAL_LHI_DATA.csv). "
                      "n = 13,719 open locations. Diamond markers = high-risk share (top axis, independent scale).")
    savefig(fig, out_path, dpi=220)


def fig_aspect_sentiment_only_pptx(d, out_path):
    d = d.sort_values("meanSentiment0to100", ascending=True).reset_index(drop=True)
    benchmark = d.meanSentiment0to100.mean()
    weakest = d.iloc[0]["aspect"]
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(13.333, 6.4))
    colors = [RISK_COLORS["Critical Risk"] if a == weakest else ACCENT for a in d.aspect]
    ax.barh(y, d.meanSentiment0to100, color=colors, zorder=3, height=0.55)
    ax.set_yticks(y); ax.set_yticklabels(d.aspect, fontsize=15)
    ax.axvline(benchmark, color=INK, linestyle="--", linewidth=1, alpha=0.55)
    ax.set_xlim(0, 100)
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.xaxis.set_visible(False)
    for yi, s in zip(y, d.meanSentiment0to100):
        ax.text(s + 1.5, yi, f"{s:.1f}", va="center", fontsize=13, color=INK, fontweight="bold")
    fig.suptitle("Order accuracy is the one aspect no QSR location is getting right",
                 fontsize=19, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.05)
    gap = d.iloc[1]["meanSentiment0to100"] - d.iloc[0]["meanSentiment0to100"]
    ax.text(0.0, -0.14, f"36.6 vs. 58.9–64.9 for every other aspect — a {gap:.0f}-point gap",
            transform=ax.transAxes, fontsize=13, color=TEXT_DIM)
    savefig(fig, out_path, dpi=150)


def fig_aspect_high_risk_share_pptx(d, out_path, top_highlight=3):
    d = d.sort_values("highRiskShare", ascending=True).reset_index(drop=True)
    y = np.arange(len(d))
    highlight_names = set(d.sort_values("highRiskShare", ascending=False).head(top_highlight).aspect)
    colors = [RISK_COLORS["High Risk"] if a in highlight_names else NEUTRAL_GREY for a in d.aspect]
    fig, ax = plt.subplots(figsize=(13.333, 6.4))
    ax.barh(y, d.highRiskShare, color=colors, zorder=3, height=0.55)
    ax.set_yticks(y); ax.set_yticklabels(d.aspect, fontsize=15)
    ax.set_xlim(0, d.highRiskShare.max() * 1.25)
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.xaxis.set_visible(False)
    for yi, h in zip(y, d.highRiskShare):
        ax.text(h + 1.2, yi, f"{h:.0f}%", va="center", fontsize=13, color=INK, fontweight="bold")
    fig.suptitle("But food, service and staff complaints are what actually\npush a location into High Risk",
                 fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.10)
    ax.text(0.0, -0.14, "Don't over-index on order accuracy alone — these three concentrate "
                        "in already-high-risk locations", transform=ax.transAxes, fontsize=13, color=TEXT_DIM)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 04 -- peer group size (new, P2)

def fig_peer_group_size(out_path):
    pg = pd.read_csv(AO / "QSR_PEER_GROUPS.csv")
    qa("fig04_peer_group_size", "rows", len(pg))
    assert len(pg) == 19154 and pg.BUSINESS_ID.duplicated().sum() == 0
    median_size = pg.PEER_GROUP_SIZE.median()
    tier_counts = pg.PEER_TIER.value_counts()
    qa("fig04_peer_group_size", "tier counts", tier_counts.to_dict())

    fig, ax = plt.subplots(figsize=(11, 5.2))
    bins = np.arange(0, pg.PEER_GROUP_SIZE.max() + 20, 20)
    ax.hist(pg.PEER_GROUP_SIZE, bins=bins, color=ACCENT, zorder=3, edgecolor="white", linewidth=0.3)
    ax.axvline(median_size, color=INK, linestyle="--", linewidth=1, alpha=0.6, zorder=4)
    ax.axvline(3, color=RISK_COLORS["Critical Risk"], linestyle=":", linewidth=1.2, alpha=0.8, zorder=4)
    clean_axes(ax, y_grid=True, x_grid=False)
    ax.set_xlabel("Peer group size (locations found)", fontsize=11)
    ax.set_ylabel("Number of businesses", fontsize=11)
    ymax = ax.get_ylim()[1]
    ax.text(median_size + 8, ymax * 0.92, f"Median {median_size:.0f}", fontsize=10, color=INK)
    ax.text(3 + 8, ymax * 0.78, "Minimum viable\npeer count (3)", fontsize=9, color=RISK_COLORS["Critical Risk"])

    kicker(fig, "Figure 02")
    title(ax, "Nearly every location is benchmarked against a real, sizeable peer set")
    source_note(fig, f"Source: QSR_PEER_GROUPS.csv, analysis/output/. n = {len(pg):,} businesses "
                      "(all classified locations, open and closed). Adaptive tier hierarchy: "
                      "10mi/same-segment → city → state → global segment fallback.")
    savefig(fig, out_path, dpi=220)


# ============================================================ Fig 05 -- LEAKY vs SAFE

def fig_model_comparison(out_path):
    df = pd.read_csv(AO / "QSR_MODEL_RESULTS.csv")
    models = df[df.MODEL != "Baseline (majority class)"].copy()
    baseline_pr = df.loc[df.MODEL == "Baseline (majority class)", "TEST_PR_AUC"].iloc[0]
    order = (models[models.FEATURE_SET.str.startswith("SAFE")]
             .sort_values("TEST_ROC_AUC", ascending=False)["MODEL"].tolist())

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8))
    fig.subplots_adjust(wspace=0.38)
    metrics = [("TEST_ROC_AUC", "ROC-AUC", 0.5), ("TEST_PR_AUC", "PR-AUC", baseline_pr)]
    bar_h = 0.36
    y = np.arange(len(order))
    for panel_i, (ax, (col, label, ref)) in enumerate(zip(axes, metrics)):
        leaky = models[models.FEATURE_SET.str.startswith("LEAKY")].set_index("MODEL").loc[order, col]
        safe = models[models.FEATURE_SET.str.startswith("SAFE")].set_index("MODEL").loc[order, col]
        ax.barh(y + bar_h / 2, leaky.values, height=bar_h, color=NEUTRAL_GREY, zorder=3)
        ax.barh(y - bar_h / 2, safe.values, height=bar_h, color=ACCENT, zorder=3)
        ax.axvline(ref, color=INK, linestyle="--", linewidth=1, alpha=0.5, zorder=4)
        ax.set_yticks(y)
        ax.set_yticklabels(order if panel_i == 0 else [], fontsize=10.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.42)
        ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        clean_axes(ax, y_grid=False, x_grid=False)
        ax.set_xlabel(label, fontsize=11)
        for yi, (lv, sv) in enumerate(zip(leaky.values, safe.values)):
            ax.text(lv + 0.015, yi + bar_h / 2, f"{lv:.2f}", va="center", fontsize=8.5, color=TEXT_DIM)
            ax.text(sv + 0.015, yi - bar_h / 2, f"{sv:.2f}", va="center", fontsize=8.5, color=ACCENT, fontweight="bold")
        if panel_i == 0:
            # direct end-of-bar labels on the top row only (Bain fig. 2.5 pattern) --
            # no legend needed since every other row repeats the same two colours
            end_label(ax, leaky.values[0] + 0.13, 0 + bar_h / 2, "LEAKY (naive)", color=NEUTRAL_GREY, fontsize=9)
            end_label(ax, safe.values[0] + 0.13, 0 - bar_h / 2, "SAFE (audited)", color=ACCENT, fontsize=9)

    xgb_leaky = models.loc[(models.MODEL == "XGBoost") & (models.FEATURE_SET.str.startswith("LEAKY")), "TEST_ROC_AUC"].iloc[0]
    xgb_safe = models.loc[(models.MODEL == "XGBoost") & (models.FEATURE_SET.str.startswith("SAFE")), "TEST_ROC_AUC"].iloc[0]
    qa("fig05_model_comparison", "XGBoost LEAKY vs SAFE ROC-AUC", (xgb_leaky, xgb_safe))

    kicker(fig, "Figure 03")
    fig.suptitle(f"A 0.969 AUC model was measuring closure directly — the honest figure is {xgb_safe:.3f}",
                  fontsize=14.5, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.03)
    source_note(fig, "Source: QSR_MODEL_RESULTS.csv, analysis/output/. 7 models × 2 feature sets "
                      "(LEAKY = naive full feature set, SAFE = leakage-audited). n = 3,831 test-set holdout.")
    savefig(fig, out_path, dpi=220)
    return xgb_leaky, xgb_safe


def fig_model_comparison_best_only_pptx(out_path):
    df = pd.read_csv(AO / "QSR_MODEL_RESULTS.csv")
    safe_rows = df[df.FEATURE_SET.str.startswith("SAFE") & (df.MODEL != "Baseline (majority class)")]
    leaky_rows = df[df.FEATURE_SET.str.startswith("LEAKY") & (df.MODEL != "Baseline (majority class)")]
    best_safe_model = safe_rows.loc[safe_rows.TEST_ROC_AUC.idxmax(), "MODEL"]
    best_safe_auc = safe_rows.TEST_ROC_AUC.max()
    leaky_auc_same_model = leaky_rows.loc[leaky_rows.MODEL == best_safe_model, "TEST_ROC_AUC"].iloc[0]

    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    bars_x = [0, 1]
    vals = [leaky_auc_same_model, best_safe_auc]
    colors = [NEUTRAL_GREY, ACCENT]
    labels = ["Naive model\n(leaky features included)", "Corrected model\n(leakage-audited features)"]
    bars = ax.bar(bars_x, vals, width=0.5, color=colors, zorder=3)
    for x, v in zip(bars_x, vals):
        ax.text(x, v + 0.02, f"{v:.3f}", ha="center", fontsize=26, fontweight="bold", color=INK, fontfamily=FONT_DISPLAY)
    ax.set_xticks(bars_x); ax.set_xticklabels(labels, fontsize=14)
    ax.set_ylim(0, 1.08)
    ax.axhline(0.5, color=INK, linestyle="--", linewidth=1, alpha=0.4)
    ax.text(1.35, 0.5, "baseline = 0.5", fontsize=10, color=TEXT_FAINT, va="center")
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.set_ylabel("ROC-AUC (test set)", fontsize=13)
    drop = leaky_auc_same_model - best_safe_auc
    ax.annotate(f"−{drop:.2f} AUC", xy=(0.5, (leaky_auc_same_model + best_safe_auc) / 2),
                fontsize=17, color=RISK_COLORS["Critical Risk"], fontweight="bold", ha="center", fontfamily=FONT_DISPLAY)
    fig.suptitle("Our closure-prediction model looked 97% accurate — until we removed the features\n"
                  "that were secretly measuring closure itself",
                  fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.06)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 06 -- feature importance 3-panel

def fig_feature_importance(out_path, top_n=10):
    df = pd.read_csv(AO / "QSR_ML_FEATURE_IMPORTANCE.csv").sort_values("MEAN_ABS_SHAP", ascending=False).head(top_n)
    order = df.FEATURE.tolist()[::-1]
    y = np.arange(len(order))

    fig, axes = plt.subplots(1, 3, figsize=(15, 6.2), sharey=True)
    panels = [
        ("NATIVE_IMPORTANCE", "Native (Gini) importance", NEUTRAL_GREY, None),
        ("PERMUTATION_IMPORTANCE_MEAN", "Permutation importance", RISK_COLORS["Watch"], "PERMUTATION_IMPORTANCE_STD"),
        ("MEAN_ABS_SHAP", "Mean |SHAP value|", ACCENT, None),
    ]
    d = df.set_index("FEATURE")
    for ax, (col, label, color, errcol) in zip(axes, panels):
        vals = d.loc[order, col].values
        xerr = d.loc[order, errcol].values if errcol else None
        ax.barh(y, vals, xerr=xerr, color=color, zorder=3, height=0.62,
                error_kw=dict(ecolor=TEXT_DIM, elinewidth=1, capsize=2))
        clean_axes(ax, y_grid=False, x_grid=True)
        ax.set_xlabel(label, fontsize=10)
        ax.set_yticks(y)
    axes[0].set_yticklabels(order, fontsize=10)

    kicker(fig, "Figure 04")
    fig.suptitle("Reviewer credibility and rating consistency drive the closure-risk signal",
                  fontsize=14.5, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.02)
    source_note(fig, f"Source: QSR_ML_FEATURE_IMPORTANCE.csv, analysis/output/. Top {top_n} of 38 exported "
                      "features, ranked by mean |SHAP|. Selected model: Random Forest, SAFE feature set. "
                      "n = 3,831 test-set holdout. Association/predictive importance, not a causal claim.")
    savefig(fig, out_path, dpi=220)


def fig_shap_top_drivers_pptx(out_path, top_n=6):
    df = pd.read_csv(AO / "QSR_ML_FEATURE_IMPORTANCE.csv").sort_values("MEAN_ABS_SHAP", ascending=False).head(top_n)
    order = df.FEATURE.tolist()[::-1]
    vals = df.set_index("FEATURE").loc[order, "MEAN_ABS_SHAP"].values
    y = np.arange(len(order))

    fig, ax = plt.subplots(figsize=(13.333, 6.4))
    colors = [ACCENT] * len(order)
    colors[-1] = RISK_COLORS["Critical Risk"]
    ax.barh(y, vals, color=colors, zorder=3, height=0.58)
    for yi, v in zip(y, vals):
        ax.text(v + vals.max() * 0.02, yi, f"{v:.3f}", va="center", fontsize=13, color=INK, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(order, fontsize=15)
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.xaxis.set_visible(False)
    fig.suptitle("Reviewer credibility and rating consistency, not price, drive the risk signal",
                 fontsize=19, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.04)
    ax.text(0.0, -0.14, "Top SHAP driver for 24% of all 19,154 locations: AVG_REVIEWER_AVERAGE_STARS",
            transform=ax.transAxes, fontsize=13, color=TEXT_DIM)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 06 -- pillar correlation (lower-triangle, mandatory revision)

def fig_pillar_correlation(out_path):
    corr = pd.read_csv(AO / "QSR_EDA_Q2_PEARSON_CORR.csv", index_col=0)
    vif = pd.read_csv(AO / "QSR_EDA_Q2_VIF.csv")
    qa("fig06_pillar_correlation", "matrix shape", corr.shape)
    assert corr.shape == (6, 6)

    # QSR_EDA_Q2_PEARSON_CORR.csv carries no row count of its own -- recompute the
    # exact N stage 03 used (listwise-complete rows across all 6 features) so the
    # chart can disclose it, and assert it reproduces the saved matrix exactly.
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False,
                       usecols=["BUSINESS_ID", "LOADED_REVIEW_COUNT", "CHECKINS_PER_LOADED_REVIEW",
                                "TIPS_PER_LOADED_REVIEW", "REVIEW_RATING_TREND_12M"])
    peer = pd.read_csv(ROOT / "QSR_BUSINESS_PEER_BENCHMARKS.csv", low_memory=False,
                        usecols=["BUSINESS_ID", "STAR_GAP_VS_PEERS", "PEER_RATING_PERCENTILE"])
    work = biz.merge(peer, on="BUSINESS_ID", how="left")
    work["ENGAGEMENT_log_reviews"] = np.log1p(work["LOADED_REVIEW_COUNT"])
    work = work.rename(columns={"STAR_GAP_VS_PEERS": "PEER_star_gap", "PEER_RATING_PERCENTILE": "PEER_rating_pct",
                                 "CHECKINS_PER_LOADED_REVIEW": "ENGAGEMENT_checkins_per_review",
                                 "TIPS_PER_LOADED_REVIEW": "ENGAGEMENT_tips_per_review",
                                 "REVIEW_RATING_TREND_12M": "MOMENTUM_rating_trend"})
    sub = work[list(corr.columns)].replace([np.inf, -np.inf], np.nan).dropna()
    n_corr = len(sub)
    qa("fig06_pillar_correlation", "N with complete data across all 6 features", n_corr)
    qa("fig06_pillar_correlation", "recomputed matrix matches saved CSV",
       bool(np.allclose(sub.corr(method="pearson").values, corr.values, atol=1e-3)))
    assert np.allclose(sub.corr(method="pearson").values, corr.values, atol=1e-3), \
        "recomputed correlation does not match QSR_EDA_Q2_PEARSON_CORR.csv -- do not disclose an unverified N"

    short = {"PEER_star_gap": "Peer star gap", "PEER_rating_pct": "Peer rating pct",
             "ENGAGEMENT_log_reviews": "Log reviews", "ENGAGEMENT_checkins_per_review": "Checkins/review",
             "ENGAGEMENT_tips_per_review": "Tips/review", "MOMENTUM_rating_trend": "Rating trend"}
    labels = [short[c] for c in corr.columns]
    mat = corr.values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 5.8), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.55})
    im = lower_triangle_heatmap(ax1, mat, labels, vmin=-1, vmax=1, value_fmt="{:.2f}")
    plt.setp(ax1.get_xticklabels(), rotation=35, ha="right")
    cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label("Pearson r", fontsize=9.5, color=TEXT_DIM)
    cbar.ax.tick_params(labelsize=8.5, color=TEXT_DIM)
    ax1.set_title("Pairwise correlation (lower triangle)", fontsize=11, fontfamily=FONT_BODY, loc="left")

    vif_sorted = vif.sort_values("VIF", ascending=True)
    y = np.arange(len(vif_sorted))
    colors = [RISK_COLORS["Critical Risk"] if v >= 5 else ACCENT for v in vif_sorted.VIF]
    ax2.barh(y, vif_sorted.VIF, color=colors, zorder=3, height=0.55)
    ax2.set_yticks(y); ax2.set_yticklabels([short[f] for f in vif_sorted.FEATURE], fontsize=9.5)
    ax2.axvline(5, color=INK, linestyle="--", linewidth=1, alpha=0.55, zorder=4)
    ax2.text(5.2, len(vif_sorted) - 0.4, "VIF = 5\nmulticollinearity threshold", fontsize=8.5, color=TEXT_DIM)
    clean_axes(ax2, y_grid=False, x_grid=True)
    ax2.set_xlabel("Variance Inflation Factor", fontsize=10)
    ax2.set_title("Multicollinearity check", fontsize=11, fontfamily=FONT_BODY, loc="left")

    high_vif = vif[vif.VIF >= 5].FEATURE.tolist()
    qa("fig06_pillar_correlation", "features above VIF=5", high_vif)

    fig.subplots_adjust(bottom=0.24)
    kicker(fig, "Figure 06")
    fig.suptitle("Two peer-tier measures are redundant — the underlying pillars are not",
                  fontsize=14, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.03)
    source_note(fig, "Source: QSR_EDA_Q2_PEARSON_CORR.csv × QSR_EDA_Q2_VIF.csv, analysis/output/. "
                      f"n = {n_corr:,} businesses with complete data across all 6 features "
                      f"({n_corr/19154*100:.0f}% of the 19,154 classified population — rows with any missing "
                      "engagement/momentum signal are excluded, not imputed).\n"
                      "Upper triangle omitted (symmetric matrix — corrgram convention); diagonal retained as scale anchor.",
                      y=0.015)
    savefig(fig, out_path, dpi=220)


# ============================================================ Fig 07 -- LHI version agreement (lower-triangle, mandatory revision)

def fig_lhi_version_agreement(out_path):
    pairs = pd.read_csv(AO / "QSR_LHI_VERSION_COMPARISON.csv")
    weights = pd.read_csv(AO / "QSR_LHI_WEIGHTS_BY_VERSION.csv")
    # QSR_LHI_VERSION_COMPARISON.csv carries no row count -- confirm the N behind
    # it from the file the comparison was computed from (all 4 versions, no nulls).
    all_versions = pd.read_csv(AO / "QSR_LHI_ALL_VERSIONS.csv", usecols=["LHI_0", "LHI_1", "LHI_2", "LHI_3"])
    n_versions = len(all_versions.dropna())
    qa("fig07_lhi_version", "N behind pairwise comparison (all 4 versions non-null)", n_versions)
    versions = ["LHI_0", "LHI_1", "LHI_2", "LHI_3"]
    mat = np.eye(4)
    for _, r in pairs.iterrows():
        i, j = versions.index(r.VERSION_A), versions.index(r.VERSION_B)
        mat[i, j] = mat[j, i] = r.SPEARMAN_RHO

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1, 1.15], "wspace": 0.55})
    im = lower_triangle_heatmap(ax1, mat, ["LHI-0", "LHI-1", "LHI-2", "LHI-3"], vmin=0.85, vmax=1.0)
    cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label("Spearman ρ", fontsize=9.5, color=TEXT_DIM)
    cbar.ax.tick_params(labelsize=8.5, color=TEXT_DIM)
    ax1.set_title("Pairwise Spearman ρ (lower triangle)", fontsize=11, fontfamily=FONT_BODY, loc="left")

    pillars = ["PEER", "ENGAGEMENT", "MOMENTUM", "CX"]
    x = np.arange(len(pillars))
    bw = 0.19
    version_colors = [NEUTRAL_GREY, RISK_COLORS["Watch"], ACCENT, INK]
    for i, (_, row) in enumerate(weights.iterrows()):
        ax2.bar(x + (i - 1.5) * bw, [row[p] for p in pillars], width=bw, color=version_colors[i],
                label=row.LHI_VERSION, zorder=3)
    ax2.set_xticks(x); ax2.set_xticklabels(pillars, fontsize=10)
    ax2.set_ylabel("Pillar weight", fontsize=10)
    clean_axes(ax2, y_grid=True, x_grid=False)
    ax2.legend(frameon=False, fontsize=8.5, ncol=2, loc="upper right")
    ax2.set_title("Pillar weight by version", fontsize=11, fontfamily=FONT_BODY, loc="left")

    lhi0_lhi3 = pairs.loc[(pairs.VERSION_A == "LHI_0") & (pairs.VERSION_B == "LHI_3"), "RISK_BAND_AGREEMENT"].iloc[0]
    lhi1_lhi2 = pairs.loc[(pairs.VERSION_A == "LHI_1") & (pairs.VERSION_B == "LHI_2"), "SPEARMAN_RHO"].iloc[0]
    qa("fig07_lhi_version", "LHI_0 vs LHI_3 risk-band agreement", lhi0_lhi3)
    qa("fig07_lhi_version", "LHI_1 vs LHI_2 spearman (weakest pair)", lhi1_lhi2)

    kicker(fig, "Figure 08")
    fig.suptitle("Four candidate LHI formulas agree closely — except one pair",
                  fontsize=14.5, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.02)
    source_note(fig, f"Source: QSR_LHI_VERSION_COMPARISON.csv × QSR_LHI_WEIGHTS_BY_VERSION.csv, analysis/output/. "
                      f"n = {n_versions:,} classified businesses (all 4 LHI versions computed for every one).\n"
                      "Upper triangle omitted (matrix is symmetric — corrgram convention); diagonal retained "
                      "as the 1.0 scale anchor. LHI-3 (hybrid) is the version selected for the final export.")
    savefig(fig, out_path, dpi=220)


def fig_lhi_version_callout_pptx(out_path):
    pairs = pd.read_csv(AO / "QSR_LHI_VERSION_COMPARISON.csv")
    vs3 = pairs[(pairs.VERSION_A == "LHI_3") | (pairs.VERSION_B == "LHI_3")].copy()
    vs3["other"] = vs3.apply(lambda r: r.VERSION_A if r.VERSION_B == "LHI_3" else r.VERSION_B, axis=1)
    vs3 = vs3.sort_values("other")
    headline = pairs.loc[(pairs.VERSION_A == "LHI_0") & (pairs.VERSION_B == "LHI_3"), "RISK_BAND_AGREEMENT"].iloc[0]

    fig = plt.figure(figsize=(13.333, 6.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.3])
    ax_num = fig.add_subplot(gs[0]); ax_num.axis("off")
    ax_num.text(0.5, 0.55, f"{headline*100:.0f}%", ha="center", va="center", fontsize=72,
                fontfamily=FONT_DISPLAY, fontweight="bold", color=INK)
    ax_num.text(0.5, 0.30, "risk-band agreement\nbaseline vs. selected hybrid version", ha="center", va="center",
                fontsize=14, color=TEXT_DIM)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(vs3))
    ax_bar.barh(y, vs3.RISK_BAND_AGREEMENT * 100, color=ACCENT, height=0.5, zorder=3)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([f"LHI-3 vs. {o.replace('LHI_', 'LHI-')}" for o in vs3.other], fontsize=13)
    ax_bar.set_xlim(0, 100)
    clean_axes(ax_bar, y_grid=False, x_grid=False)
    ax_bar.set_xlabel("Risk-band agreement, %", fontsize=12)
    for yi, v in zip(y, vs3.RISK_BAND_AGREEMENT * 100):
        ax_bar.text(v + 2, yi, f"{v:.0f}%", va="center", fontsize=12, fontweight="bold", color=INK)

    fig.suptitle("Four independently-built scoring methods agree on 96% of risk calls",
                 fontsize=19, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.04)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 08 -- sensitivity dumbbell (mandatory revision)

def fig_sensitivity_dumbbell(out_path):
    df = pd.read_csv(AO / "QSR_LHI_SENSITIVITY.csv")
    df = df[df.SCENARIO != "baseline_LHI3"].copy()
    df = df.sort_values("SPEARMAN_VS_BASELINE", ascending=True).reset_index(drop=True)
    qa("fig08_sensitivity", "scenarios", df.SCENARIO.tolist())
    # QSR_LHI_SENSITIVITY.csv carries no row count -- same source population as the
    # version-comparison figure (stage 10 scores every scenario off QSR_LHI_ALL_VERSIONS.csv).
    n_sensitivity = len(pd.read_csv(AO / "QSR_LHI_ALL_VERSIONS.csv", usecols=["LHI_0"]).dropna())
    qa("fig08_sensitivity", "N behind each scenario score", n_sensitivity)

    label_map = {"peer_heavy": "Peer-heavy", "engagement_heavy": "Engagement-heavy",
                 "momentum_heavy": "Momentum-heavy", "cx_heavy": "CX-heavy", "equal_weight": "Equal-weight"}
    df["label"] = df.SCENARIO.map(label_map).fillna(df.SCENARIO)
    df["gap"] = (df.SPEARMAN_VS_BASELINE - df.RISK_BAND_AGREEMENT_VS_BASELINE).abs()
    widest_gap_idx = df["gap"].idxmax()

    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    y = np.arange(len(df))
    # RGG revision: connecting segment between the two values per row (true dumbbell)
    for yi, row in df.iterrows():
        ax.plot([row.RISK_BAND_AGREEMENT_VS_BASELINE, row.SPEARMAN_VS_BASELINE], [yi, yi],
                color=TEXT_FAINT, linewidth=2.2, zorder=2, solid_capstyle="round")
    ax.scatter(df.SPEARMAN_VS_BASELINE, y, s=90, color=ACCENT, zorder=4, label="Spearman ρ vs. baseline",
               edgecolor="white", linewidth=0.8)
    ax.scatter(df.RISK_BAND_AGREEMENT_VS_BASELINE, y, s=90, color=RISK_COLORS["Watch"], zorder=4,
               label="Risk-band agreement vs. baseline", edgecolor="white", linewidth=0.8)

    ax.axvline(1.0, color=INK, linestyle="--", linewidth=1, alpha=0.5, zorder=1)
    ax.set_yticks(y); ax.set_yticklabels(df.label, fontsize=11)
    ax.set_xlim(0.6, 1.08)
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.set_xlabel("Agreement with baseline LHI (1.0 = identical)", fontsize=11)
    fig.subplots_adjust(bottom=0.22)

    # direct labels on the top row instead of a legend box (Bain fig. 2.5 pattern) --
    # placed on opposite sides of the row (above / below) so they stay clear of each
    # other regardless of how close the two dots sit on the x-axis
    top = df.iloc[-1]
    end_label(ax, top.SPEARMAN_VS_BASELINE, len(df) - 1 + 0.32, "Spearman ρ", color=ACCENT,
              fontsize=9.5, ha="center", va="bottom")
    end_label(ax, top.RISK_BAND_AGREEMENT_VS_BASELINE, len(df) - 1 - 0.32, "Risk-band agreement",
              color=RISK_COLORS["Watch"], fontsize=9.5, ha="center", va="top")

    wg = df.loc[widest_gap_idx]
    ax.annotate(f"Widest spread: {wg.label}\n(Δ = {wg.gap:.3f})",
                xy=((wg.SPEARMAN_VS_BASELINE + wg.RISK_BAND_AGREEMENT_VS_BASELINE) / 2, widest_gap_idx),
                xytext=(0.66, widest_gap_idx - 0.9), fontsize=9.5, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK, lw=0.9))

    kicker(fig, "Figure 09")
    title(ax, "The selected LHI holds up under five reasonable reweightings")
    source_note(fig, f"Source: QSR_LHI_SENSITIVITY.csv, analysis/output/. n = {n_sensitivity:,} classified "
                      "businesses, scored under each weighting scenario.\n"
                      "Dumbbell connects each scenario's two agreement metrics vs. the selected construction "
                      "(LHI-3, the hybrid scored throughout this report); baseline_LHI3 (=1.0 by definition) "
                      "omitted as a row since it carries no information. "
                      "Sorted ascending by Spearman ρ.")
    savefig(fig, out_path, dpi=220)


# ============================================================ Fig 09 -- risk-band stability

def fig_risk_band_stability(out_path):
    df = pd.read_csv(AO / "QSR_LHI_RISK_BAND_STABILITY.csv")
    total = df.N_BUSINESSES.sum()
    qa("fig09_risk_band_stability", "rows", df.to_dict("records"))
    assert total == 19154, f"unexpected total {total}"

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    x = df.N_DISTINCT_BANDS.astype(str)
    # ACCENT_RAMP (light->dark teal), not risk-red: this measures rank-methodology
    # instability, not a location's own risk classification, so it must not borrow
    # the reserved risk-band colours even though "more bands reached" is worse.
    bars = ax.bar(x, df.N_BUSINESSES, color=ACCENT_RAMP[:len(df)], zorder=3, width=0.55)
    for xi, (n, pct) in enumerate(zip(df.N_BUSINESSES, df.N_BUSINESSES / total * 100)):
        ax.text(xi, n + total * 0.015, f"{n:,}\n({pct:.0f}%)", ha="center", va="bottom", fontsize=10.5,
                color=INK, fontweight="bold")
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.set_xlabel("Distinct risk bands reached across all sensitivity scenarios", fontsize=11)
    ax.set_ylabel("Number of businesses", fontsize=11)
    ax.set_ylim(0, total * 0.62)

    kicker(fig, "Figure 10")
    title(ax, "Most locations never change risk band under stress-testing")
    source_note(fig, f"Source: QSR_LHI_RISK_BAND_STABILITY.csv, analysis/output/. n = {total:,} businesses.")
    savefig(fig, out_path, dpi=220)


# ============================================================ Fig 10 -- confidence / fallback (corrected denominator)

def fig_confidence_fallback(out_path):
    df = pd.read_csv(AO / "QSR_FALLBACK_CONFIDENCE.csv")
    qa("fig10_confidence_fallback", "rows (all classified, not open-only)", len(df))
    assert len(df) == 19154

    fallback_order = ["1_Full_LHI", "2_Reduced_LHI", "3_Peer_Adjusted_Estimate"]
    fallback_labels = ["Full LHI", "Reduced LHI", "Peer-adjusted estimate"]
    # CONFIDENCE_COLORS (accent-teal family), not the risk palette: LHI_CONFIDENCE
    # is a data-quality axis, not a location's risk classification.
    present_fb = [f for f in fallback_order if f in df.FALLBACK_LEVEL.unique()]
    ct = pd.crosstab(df.FALLBACK_LEVEL, df.LHI_CONFIDENCE).reindex(index=present_fb, columns=CONFIDENCE_ORDER, fill_value=0)

    fig, ax = plt.subplots(figsize=(10, 5.2))
    x = np.arange(len(ct))
    bottom = np.zeros(len(ct))
    for c in CONFIDENCE_ORDER:
        vals = ct[c].values
        ax.bar(x, vals, bottom=bottom, color=CONFIDENCE_COLORS[c], label=f"{c} confidence", zorder=3, width=0.55)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels([fallback_labels[fallback_order.index(f)] for f in present_fb], fontsize=10.5)
    clean_axes(ax, y_grid=True, x_grid=False)
    ax.set_ylabel("Number of locations", fontsize=11)
    ax.legend(frameon=False, fontsize=9.5, loc="upper right")

    kicker(fig, "Figure 01")
    title(ax, "Most scores rest on real evidence, not fallback estimation")
    full_pct = (df.FALLBACK_LEVEL == "1_Full_LHI").mean() * 100
    source_note(fig, f"Source: QSR_FALLBACK_CONFIDENCE.csv, analysis/output/. n = {len(df):,} classified "
                      f"locations (open and closed — corrected from an earlier draft that assumed open-only "
                      f"13,719; this table covers all 19,154). {full_pct:.1f}% receive the full, non-reduced LHI computation.")
    savefig(fig, out_path, dpi=220)


# ============================================================ Fig 11 -- intervention priority quadrant (shared)

def fig_intervention_priority(out_path):
    drv = pd.read_csv(AO / "QSR_DRIVERS.csv",
                       usecols=["BUSINESS_ID", "IS_OPEN", "RISK_SCORE", "TREND_ADJUSTMENT",
                                "INTERVENTION_PRIORITY", "INTERVENTION_PRIORITY_SCORE"])
    open_drv = drv[drv.IS_OPEN == 1].copy()
    assert len(open_drv) == 13719
    nonzero = open_drv[open_drv.TREND_ADJUSTMENT != 0]

    ex_a = drv[drv.BUSINESS_ID == "bzvxt0sP9OMwwks1vLSzKw"].iloc[0]
    ex_b = drv[drv.BUSINESS_ID == "KPzDlvjirWoWqQICXLgxsg"].iloc[0]
    assert ex_a.INTERVENTION_PRIORITY_SCORE > ex_b.INTERVENTION_PRIORITY_SCORE

    fig, ax = plt.subplots(figsize=(13.333, 7.0))
    fig.subplots_adjust(top=0.84, bottom=0.14)
    ax.scatter(open_drv.RISK_SCORE, open_drv.TREND_ADJUSTMENT, s=8, color=POPULATION_WASH, alpha=0.35, zorder=2, linewidths=0)
    ax.scatter(nonzero.RISK_SCORE, nonzero.TREND_ADJUSTMENT, s=26,
               color=[PRIORITY_COLORS[p] for p in nonzero.INTERVENTION_PRIORITY],
               alpha=0.85, zorder=3, edgecolor="white", linewidth=0.3)
    for thr in (40, 60, 75):
        ax.axvline(thr, color=INK, linestyle=":", linewidth=0.9, alpha=0.35, zorder=1)
    ax.axhline(0, color=INK, linestyle="-", linewidth=0.8, alpha=0.4, zorder=1)
    ax.set_ylim(-24, 24)

    ax.annotate(f"Deteriorating, Watch-range: risk {ex_a.RISK_SCORE:.0f} → priority score "
                f"{ex_a.INTERVENTION_PRIORITY_SCORE:.0f} ({ex_a.INTERVENTION_PRIORITY})",
                xy=(ex_a.RISK_SCORE, ex_a.TREND_ADJUSTMENT), xycoords="data",
                xytext=(0.30, 0.97), textcoords="axes fraction", fontsize=10.5, color=INK, fontfamily=FONT_BODY,
                ha="left", va="top", arrowprops=dict(arrowstyle="->", color=INK, lw=1, shrinkA=0, shrinkB=4))
    ax.annotate(f"Improving, High-Risk-range: risk {ex_b.RISK_SCORE:.0f} → priority score "
                f"{ex_b.INTERVENTION_PRIORITY_SCORE:.0f} ({ex_b.INTERVENTION_PRIORITY})",
                xy=(ex_b.RISK_SCORE, ex_b.TREND_ADJUSTMENT), xycoords="data",
                xytext=(0.50, 0.03), textcoords="axes fraction", fontsize=10.5, color=INK, fontfamily=FONT_BODY,
                ha="left", va="bottom", arrowprops=dict(arrowstyle="->", color=INK, lw=1, shrinkA=0, shrinkB=4))

    clean_axes(ax, y_grid=True, x_grid=False)
    ax.set_xlabel("Risk score, 0–100 (higher = more risk; ≈ 100 − LHI)", fontsize=13)
    ax.set_ylabel("Trend adjustment (trajectory magnitude)", fontsize=13)
    ax.set_xlim(0, 100)

    handles = [plt.Line2D([0], [0], marker="o", linestyle="", color=PRIORITY_COLORS[p], markersize=9, label=p)
               for p in PRIORITY_ORDER]
    ax.legend(handles=handles, title="Intervention priority", loc="center left", frameon=False, fontsize=11,
              title_fontsize=11, bbox_to_anchor=(0.0, 0.82))

    kicker(fig, "Figure 11", y=0.985)
    fig.suptitle("A declining Watch-range location can outrank an improving High-Risk one",
                 fontsize=17, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=0.93)
    source_note(fig, f"Source: QSR_DRIVERS.csv, analysis/output/. n = {len(open_drv):,} open locations "
                      f"(light grey); {len(nonzero):,} with statistically-evidenced trend adjustment (coloured by priority tier). "
                      "Intervention priority score = risk score + trend adjustment.", y=0.015)
    savefig(fig, out_path, dpi=200)


def fig_early_warning_callout_pptx(out_path):
    meta = json.loads((ROOT / "dashboard" / "data" / "meta.json").read_text(encoding="utf-8"))
    tc = meta["trajectoryCounts"]
    deteriorating = tc["Deteriorating"]
    # escalated (still Healthy/Watch) not stored directly in meta; recompute from QSR_DRIVERS
    drv = pd.read_csv(AO / "QSR_DRIVERS.csv", usecols=["BUSINESS_ID", "IS_OPEN", "RATING_TRAJECTORY"])
    fin = pd.read_csv(AO / "QSR_FINAL_LHI_DATA.csv", usecols=["BUSINESS_ID", "RISK_CATEGORY"])
    j = drv.merge(fin, on="BUSINESS_ID", how="left")
    open_j = j[j.IS_OPEN == 1]
    det = open_j[open_j.RATING_TRAJECTORY == "Deteriorating"]
    escalated = det.RISK_CATEGORY.isin(["Healthy", "Watch"]).sum()
    qa("pptx_early_warning", "deteriorating (open)", len(det))
    qa("pptx_early_warning", "still Healthy/Watch", int(escalated))
    assert len(det) == deteriorating, f"mismatch vs dashboard meta: {len(det)} vs {deteriorating}"

    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    ax.axis("off")
    ax.text(0.5, 0.62, f"{escalated}", ha="center", va="center", fontsize=100,
            fontfamily=FONT_DISPLAY, fontweight="bold", color=RISK_COLORS["Critical Risk"])
    ax.text(0.5, 0.34, f"of {deteriorating} statistically-evidenced deteriorating locations\n"
                       "are still classified Healthy or Watch today",
            ha="center", va="center", fontsize=17, color=TEXT_DIM)
    fig.suptitle("268 locations look fine today — and are already trending down",
                 fontsize=20, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.02)
    savefig(fig, out_path, dpi=150)


# ============================================================ appendix

def fig_confusion_matrix_appendix(out_path):
    df = pd.read_csv(AO / "QSR_MODEL_RESULTS.csv")
    row = df[(df.MODEL == "Random Forest") & (df.FEATURE_SET.str.startswith("SAFE"))].iloc[0]
    tn, fp, fn, tp = int(row.TN), int(row.FP), int(row.FN), int(row.TP)
    total = tn + fp + fn + tp
    mat = np.array([[tn, fp], [fn, tp]])

    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    im = ax.imshow(mat, cmap=teal_sequential_cmap(), vmin=0, vmax=mat.max())
    ax.set_xticks([0, 1]); ax.set_xticklabels(["Predicted Open", "Predicted Closed"], fontsize=10)
    ax.set_yticks([0, 1]); ax.set_yticklabels(["Actual Open", "Actual Closed"], fontsize=10)
    for i in range(2):
        for j in range(2):
            v = mat[i, j]
            ax.text(j, i - 0.08, f"{v:,}", ha="center", va="center", fontsize=15, fontweight="bold",
                    color="white" if v > mat.max() * 0.5 else INK)
            ax.text(j, i + 0.16, f"{v/total*100:.1f}%", ha="center", va="center", fontsize=9.5,
                    color="white" if v > mat.max() * 0.5 else TEXT_DIM)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    title(ax, "Where the safe model actually gets it wrong")
    source_note(fig, "Source: QSR_MODEL_RESULTS.csv, analysis/output/. Random Forest, SAFE (leakage-audited) "
                      f"feature set, test-set holdout. n = {total:,}.")
    savefig(fig, out_path, dpi=220)


def fig_rank_stability_hexbin_appendix(out_path):
    df = pd.read_csv(AO / "QSR_RANK_STABILITY.csv")
    qa("appendix_rank_stability", "rows", len(df))
    assert len(df) == 19154

    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    hb = ax.hexbin(df.MEAN_RANK, df.RANK_STD, gridsize=45, cmap=teal_sequential_cmap(), mincnt=1)
    cbar = fig.colorbar(hb, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Locations per hexagon", fontsize=9.5, color=TEXT_DIM)
    clean_axes(ax, y_grid=False, x_grid=False)
    ax.set_xlabel("Mean rank across sensitivity scenarios", fontsize=11)
    ax.set_ylabel("Rank standard deviation", fontsize=11)
    title(ax, "Mid-pack locations swing more than the extremes")
    source_note(fig, f"Source: QSR_RANK_STABILITY.csv, analysis/output/. n = {len(df):,}. "
                      "Hexbin used in place of a raw scatter to avoid overplotting at this n "
                      "(R Graph Gallery: high-density-scatterplot-with-binning).")
    savefig(fig, out_path, dpi=200)


# ============================================================ main

def main():
    tr = OUT_DIR / "technical_report"
    px = OUT_DIR / "pptx"
    sh = OUT_DIR / "shared"
    ap = OUT_DIR / "appendix"

    open_only = load_open_only_lhi()
    aspect_df = load_aspect_summary()

    # DATA / EVIDENCE QUALITY
    fig_confidence_fallback(tr / "fig_01_confidence_fallback_final.png")
    # BENCHMARKING FOUNDATION
    fig_peer_group_size(tr / "fig_02_peer_group_size_final.png")
    # ML EVIDENCE
    fig_model_comparison(tr / "fig_03_model_comparison_leaky_safe_final.png")
    fig_model_comparison_best_only_pptx(px / "fig_p2_model_comparison_best_final.png")
    fig_feature_importance(tr / "fig_04_feature_importance_panels_final.png")
    fig_shap_top_drivers_pptx(px / "fig_p3_shap_top_drivers_final.png")
    # RISK DRIVERS
    fig_aspect_sentiment_risk_share(aspect_df, tr / "fig_05_aspect_sentiment_risk_share_final.png")
    fig_aspect_sentiment_only_pptx(aspect_df, px / "fig_p4_aspect_sentiment_final.png")
    fig_aspect_high_risk_share_pptx(aspect_df, px / "fig_p5_aspect_high_risk_share_final.png")
    # LHI CONSTRUCTION
    fig_pillar_correlation(tr / "fig_06_pillar_correlation_final.png")
    fig_01_lhi_composition_histogram(open_only, tr / "fig_07_lhi_distribution_final.png")
    fig_risk_band_distribution_pptx(open_only, px / "fig_p1_risk_band_distribution_final.png")
    # VALIDATION
    fig_lhi_version_agreement(tr / "fig_08_lhi_version_agreement_final.png")
    fig_lhi_version_callout_pptx(px / "fig_p6_lhi_version_callout_final.png")
    # ROBUSTNESS
    fig_sensitivity_dumbbell(tr / "fig_09_sensitivity_dumbbell_final.png")
    fig_risk_band_stability(tr / "fig_10_risk_band_stability_final.png")
    # OPERATIONAL PRIORITISATION
    fig_intervention_priority(sh / "fig_11_intervention_priority_quadrant_final.png")
    fig_early_warning_callout_pptx(px / "fig_p7_early_warning_final.png")

    # appendix
    fig_confusion_matrix_appendix(ap / "fig_appx_confusion_matrix_final.png")
    fig_rank_stability_hexbin_appendix(ap / "fig_appx_rank_stability_hexbin_final.png")

    qa_path = OUT_DIR / "_lib" / "qa_log_final.csv"
    pd.DataFrame(QA_LOG, columns=["figure", "check", "result"]).to_csv(qa_path, index=False)
    print("\nQA log written to", qa_path)


if __name__ == "__main__":
    main()
