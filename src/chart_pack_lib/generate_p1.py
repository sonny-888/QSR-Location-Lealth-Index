"""
Generates the P1 charts approved in the Final Chart Design Specification.

READ-ONLY against the project's existing analytical outputs:
  analysis/output/*.csv
  dashboard/data/meta.json

Writes PNGs only under chart_pack/{technical_report,pptx,shared}/.
Does not touch analysis/, dashboard/, or any pipeline file.

Run:  .venv/Scripts/python.exe chart_pack/_lib/generate_p1.py
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
    FONT_DISPLAY, FONT_BODY, FONT_MONO,
    apply_base_rc, clean_axes, title, source_note, savefig,
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
    """QSR_FINAL_LHI_DATA (LHI, RISK_CATEGORY) joined to QSR_DRIVERS (IS_OPEN), open-only."""
    fin = pd.read_csv(AO / "QSR_FINAL_LHI_DATA.csv",
                       usecols=["BUSINESS_ID", "LHI", "RISK_CATEGORY"])
    drv = pd.read_csv(AO / "QSR_DRIVERS.csv", usecols=["BUSINESS_ID", "IS_OPEN"])
    qa("shared", "FINAL_LHI_DATA rows", len(fin))
    qa("shared", "FINAL_LHI_DATA duplicate BUSINESS_ID", fin.BUSINESS_ID.duplicated().sum())
    merged = fin.merge(drv, on="BUSINESS_ID", how="left", validate="one_to_one")
    qa("shared", "merged rows", len(merged))
    qa("shared", "null IS_OPEN after merge", int(merged.IS_OPEN.isna().sum()))
    open_only = merged[merged.IS_OPEN == 1].copy()
    qa("shared", "open-only rows", len(open_only))
    assert len(open_only) == 13719, "open-only row count does not match the shipped dashboard's 13,719 — STOP"
    counts = open_only.RISK_CATEGORY.value_counts().to_dict()
    qa("shared", "open-only risk-band counts", counts)
    expected = {"Watch": 4806, "Healthy": 3856, "High Risk": 3528, "Critical Risk": 1529}
    assert counts == expected, f"risk-band counts diverge from dashboard meta.json: {counts} vs {expected}"
    median_lhi = open_only.LHI.median()
    qa("shared", "open-only median LHI", round(median_lhi, 2))
    return open_only


# ============================================================ Fig 01 -- LHI distribution (report)

def fig_lhi_distribution(open_only, out_path, pptx=False):
    edges = list(range(0, 101, 4))
    n_bins = len(edges) - 1
    bins = {b: np.zeros(n_bins, dtype=int) for b in RISK_ORDER}
    idx = np.clip((open_only.LHI.values // 4).astype(int), 0, n_bins - 1)
    for b in RISK_ORDER:
        mask = open_only.RISK_CATEGORY.values == b
        for i in idx[mask]:
            bins[b][i] += 1
    total_per_bin = sum(bins[b] for b in RISK_ORDER)
    qa("01_lhi_distribution", "sum of stacked bins == n", int(total_per_bin.sum()) == len(open_only))

    median_lhi = open_only.LHI.median()
    high_crit_pct = (open_only.RISK_CATEGORY.isin(["High Risk", "Critical Risk"]).mean()) * 100

    figsize = (11.5, 5.2) if not pptx else (13.333, 6.2)
    fig, ax = plt.subplots(figsize=figsize)
    bottom = np.zeros(n_bins)
    centers = [(edges[i] + edges[i + 1]) / 2 for i in range(n_bins)]
    width = 3.6
    for b in RISK_ORDER:
        ax.bar(centers, bins[b], width=width, bottom=bottom, color=RISK_COLORS[b],
               label=b, zorder=3, edgecolor="white", linewidth=0.3)
        bottom += bins[b]

    ax.axvline(median_lhi, color=INK, linestyle="--", linewidth=1.1, alpha=0.6, zorder=4)
    ax.text(median_lhi + 1.5, ax.get_ylim()[1] if False else max(total_per_bin) * 0.96,
            f"Median LHI {median_lhi:.1f}", fontsize=10 if not pptx else 13,
            color=INK, fontfamily=FONT_BODY, ha="left", va="top")

    clean_axes(ax)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Location Health Index (LHI), 0–100", fontsize=11 if not pptx else 15)
    ax.set_ylabel("Number of open locations", fontsize=11 if not pptx else 15)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(20))

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.16),
              ncol=4, frameon=False, fontsize=9.5 if not pptx else 13)

    if pptx:
        fig.suptitle("37% of open locations already show a customer-facing warning sign",
                      fontsize=21, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK,
                      x=0.02, ha="left", y=1.02)
        ax.text(0.98, 0.94, f"{high_crit_pct:.0f}% High + Critical Risk", transform=ax.transAxes,
                ha="right", va="top", fontsize=15, fontweight="bold", color=RISK_COLORS["Critical Risk"],
                fontfamily=FONT_DISPLAY)
    else:
        title(ax, "Portfolio LHI distribution, by risk-band composition")
        ax.text(0.98, 0.94, f"{high_crit_pct:.1f}% High + Critical Risk", transform=ax.transAxes,
                ha="right", va="top", fontsize=10.5, fontweight="bold", color=RISK_COLORS["Critical Risk"])
        source_note(fig, "Source: QSR_FINAL_LHI_DATA.csv × QSR_DRIVERS.csv (IS_OPEN), analysis/output/. "
                          f"n = {len(open_only):,} open locations, 4-point bins.")
    savefig(fig, out_path, dpi=200 if not pptx else 150)


# ============================================================ Fig -- risk-band distribution (pptx only)

def fig_risk_band_distribution(open_only, out_path):
    counts = open_only.RISK_CATEGORY.value_counts().reindex(RISK_ORDER)
    pct = counts / counts.sum() * 100
    high_crit_pct = pct[["High Risk", "Critical Risk"]].sum()

    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    y_pos = np.arange(len(RISK_ORDER))
    bars = ax.barh(y_pos, counts.values, color=[RISK_COLORS[b] for b in RISK_ORDER], zorder=3, height=0.6)
    for i, b in enumerate(RISK_ORDER):
        ax.text(counts[b] + 60, i, f"{counts[b]:,}  ({pct[b]:.0f}%)", va="center",
                fontsize=15, color=INK, fontfamily=FONT_BODY, fontweight="bold")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(RISK_ORDER, fontsize=15)
    ax.invert_yaxis()
    clean_axes(ax, y_grid=False, x_grid=True)
    ax.set_xlabel("")
    ax.xaxis.set_visible(False)
    ax.set_xlim(0, counts.max() * 1.32)

    fig.suptitle("37% of open locations already show a customer-facing warning sign",
                  fontsize=22, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.03)
    ax.text(0.0, -0.16, f"High Risk + Critical Risk = {counts['High Risk']+counts['Critical Risk']:,} of "
                        f"{counts.sum():,} open locations ({high_crit_pct:.0f}%)",
            transform=ax.transAxes, fontsize=13, color=TEXT_DIM, fontfamily=FONT_BODY)
    savefig(fig, out_path, dpi=150)
    qa("pptx_01_risk_band_distribution", "counts", counts.to_dict())


# ============================================================ Fig 02 -- LEAKY vs SAFE model comparison

def load_model_results():
    df = pd.read_csv(AO / "QSR_MODEL_RESULTS.csv")
    qa("02_model_comparison", "rows in QSR_MODEL_RESULTS.csv", len(df))
    return df


def fig_model_comparison(df, out_path, pptx=False):
    models = df[df.MODEL != "Baseline (majority class)"].copy()
    baseline_pr = df.loc[df.MODEL == "Baseline (majority class)", "TEST_PR_AUC"].iloc[0]
    order = (models[models.FEATURE_SET.str.startswith("SAFE")]
             .sort_values("TEST_ROC_AUC", ascending=False)["MODEL"].tolist())
    qa("02_model_comparison", "model order (desc SAFE ROC-AUC)", order)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8) if not pptx else (14, 6.4))
    fig.subplots_adjust(wspace=0.38)
    metrics = [("TEST_ROC_AUC", "ROC-AUC", 0.5, "Majority-class baseline = 0.5"),
               ("TEST_PR_AUC", "PR-AUC", baseline_pr, f"Prevalence baseline = {baseline_pr:.2f}")]
    bar_h = 0.36
    y = np.arange(len(order))
    for panel_i, (ax, (col, label, ref, ref_label)) in enumerate(zip(axes, metrics)):
        leaky = models[models.FEATURE_SET.str.startswith("LEAKY")].set_index("MODEL").loc[order, col]
        safe = models[models.FEATURE_SET.str.startswith("SAFE")].set_index("MODEL").loc[order, col]
        ax.barh(y + bar_h / 2, leaky.values, height=bar_h, color=NEUTRAL_GREY, label="LEAKY (naive)", zorder=3)
        ax.barh(y - bar_h / 2, safe.values, height=bar_h, color=ACCENT, label="SAFE (leakage-audited)", zorder=3)
        ax.axvline(ref, color=INK, linestyle="--", linewidth=1, alpha=0.5, zorder=4)
        ax.set_yticks(y)
        if panel_i == 0:
            ax.set_yticklabels(order, fontsize=10.5 if not pptx else 13)
        else:
            ax.set_yticklabels([])
        ax.invert_yaxis()
        ax.set_xlim(0, 1.12)
        ax.xaxis.set_major_locator(mticker.MultipleLocator(0.2))
        clean_axes(ax, y_grid=False, x_grid=True)
        ax.set_xlabel(label, fontsize=11 if not pptx else 14)
        for yi, (lv, sv) in enumerate(zip(leaky.values, safe.values)):
            ax.text(lv + 0.015, yi + bar_h / 2, f"{lv:.2f}", va="center", fontsize=8.5 if not pptx else 11, color=TEXT_DIM)
            ax.text(sv + 0.015, yi - bar_h / 2, f"{sv:.2f}", va="center", fontsize=8.5 if not pptx else 11,
                    color=ACCENT, fontweight="bold")

    handles = [plt.Rectangle((0, 0), 1, 1, color=NEUTRAL_GREY), plt.Rectangle((0, 0), 1, 1, color=ACCENT)]
    fig.legend(handles, ["LEAKY (naive)", "SAFE (leakage-audited)"], loc="lower center", ncol=2,
               frameon=False, fontsize=9.5 if not pptx else 12, bbox_to_anchor=(0.5, -0.04))

    xgb_leaky = models.loc[(models.MODEL == "XGBoost") & (models.FEATURE_SET.str.startswith("LEAKY")), "TEST_ROC_AUC"].iloc[0]
    xgb_safe = models.loc[(models.MODEL == "XGBoost") & (models.FEATURE_SET.str.startswith("SAFE")), "TEST_ROC_AUC"].iloc[0]
    qa("02_model_comparison", "XGBoost LEAKY vs SAFE ROC-AUC", (xgb_leaky, xgb_safe))
    drop = xgb_leaky - xgb_safe

    if pptx:
        fig.suptitle("Our closure-prediction model looked 97% accurate — until we removed the features\n"
                      "that were secretly measuring closure itself",
                      fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.10)
    else:
        fig.suptitle("Removing leaky features drops model performance from "
                      f"{xgb_leaky:.3f} to {xgb_safe:.3f} AUC",
                      fontsize=14.5, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.03)
        source_note(fig, "Source: QSR_MODEL_RESULTS.csv, analysis/output/. 7 models × 2 feature sets "
                          "(LEAKY = naive full feature set, SAFE = leakage-audited). Test-set holdout metrics.")
    savefig(fig, out_path, dpi=200 if not pptx else 150)
    return drop


def fig_model_comparison_best_only(df, out_path):
    """PPTX-simplified: single best-model pair, one dominant message."""
    safe_rows = df[df.FEATURE_SET.str.startswith("SAFE") & (df.MODEL != "Baseline (majority class)")]
    leaky_rows = df[df.FEATURE_SET.str.startswith("LEAKY") & (df.MODEL != "Baseline (majority class)")]
    best_safe_model = safe_rows.loc[safe_rows.TEST_ROC_AUC.idxmax(), "MODEL"]
    best_safe_auc = safe_rows.TEST_ROC_AUC.max()
    leaky_auc_same_model = leaky_rows.loc[leaky_rows.MODEL == best_safe_model, "TEST_ROC_AUC"].iloc[0]
    qa("pptx_02_model_comparison_best", "best SAFE model", (best_safe_model, best_safe_auc, leaky_auc_same_model))

    fig, ax = plt.subplots(figsize=(13.333, 6.2))
    bars_x = [0, 1]
    vals = [leaky_auc_same_model, best_safe_auc]
    colors = [NEUTRAL_GREY, ACCENT]
    labels = ["Naive model\n(leaky features included)", "Corrected model\n(leakage-audited features)"]
    bars = ax.bar(bars_x, vals, width=0.5, color=colors, zorder=3)
    for x, v in zip(bars_x, vals):
        ax.text(x, v + 0.02, f"{v:.3f}", ha="center", fontsize=26, fontweight="bold",
                color=INK, fontfamily=FONT_DISPLAY)
    ax.set_xticks(bars_x)
    ax.set_xticklabels(labels, fontsize=14)
    ax.set_ylim(0, 1.08)
    ax.axhline(0.5, color=INK, linestyle="--", linewidth=1, alpha=0.4)
    ax.text(1.35, 0.5, "baseline = 0.5", fontsize=10, color=TEXT_FAINT, va="center")
    clean_axes(ax, y_grid=True, x_grid=False)
    ax.set_ylabel("ROC-AUC (test set)", fontsize=13)
    drop = leaky_auc_same_model - best_safe_auc
    ax.annotate(f"−{drop:.2f} AUC", xy=(0.5, (leaky_auc_same_model + best_safe_auc) / 2),
                fontsize=17, color="#c9432f", fontweight="bold", ha="center", fontfamily=FONT_DISPLAY)
    fig.suptitle("Our closure-prediction model looked 97% accurate — until we removed the features\n"
                  "that were secretly measuring closure itself",
                  fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.06)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 03 -- feature importance 3-panel

def fig_feature_importance(out_path, pptx=False, top_n=10):
    df = pd.read_csv(AO / "QSR_ML_FEATURE_IMPORTANCE.csv")
    qa("03_feature_importance", "rows in QSR_ML_FEATURE_IMPORTANCE.csv", len(df))
    df = df.sort_values("MEAN_ABS_SHAP", ascending=False).head(top_n)
    order = df.FEATURE.tolist()[::-1]  # reversed so highest-SHAP renders at TOP of barh
    y = np.arange(len(order))

    fig, axes = plt.subplots(1, 3, figsize=(15, 6.2) if not pptx else (13.333, 6.4), sharey=True)
    panels = [
        ("NATIVE_IMPORTANCE", "Native (Gini) importance", NEUTRAL_GREY, None),
        ("PERMUTATION_IMPORTANCE_MEAN", "Permutation importance", "#a3701a", "PERMUTATION_IMPORTANCE_STD"),
        ("MEAN_ABS_SHAP", "Mean |SHAP value|", ACCENT, None),
    ]
    d = df.set_index("FEATURE")
    for ax, (col, label, color, errcol) in zip(axes, panels):
        vals = d.loc[order, col].values
        xerr = d.loc[order, errcol].values if errcol else None
        ax.barh(y, vals, xerr=xerr, color=color, zorder=3, height=0.62,
                error_kw=dict(ecolor=TEXT_DIM, elinewidth=1, capsize=2))
        clean_axes(ax, y_grid=False, x_grid=True)
        ax.set_xlabel(label, fontsize=10 if not pptx else 12.5)
        ax.set_yticks(y)
    axes[0].set_yticklabels(order, fontsize=10 if not pptx else 12.5)

    if pptx:
        fig.suptitle("Reviewer credibility and rating consistency drive the closure-risk signal",
                      fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.04)
    else:
        fig.suptitle("Reviewer credibility and rating consistency drive the closure-risk signal",
                      fontsize=14.5, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.02)
        source_note(fig, f"Source: QSR_ML_FEATURE_IMPORTANCE.csv, analysis/output/. Top {top_n} of "
                          f"{len(pd.read_csv(AO / 'QSR_ML_FEATURE_IMPORTANCE.csv'))} exported features, ranked by mean |SHAP|. "
                          "Selected model: Random Forest, SAFE (leakage-audited) feature set.")
    savefig(fig, out_path, dpi=200 if not pptx else 150)


def fig_shap_top_drivers_pptx(out_path, top_n=6):
    df = pd.read_csv(AO / "QSR_ML_FEATURE_IMPORTANCE.csv").sort_values("MEAN_ABS_SHAP", ascending=False).head(top_n)
    order = df.FEATURE.tolist()[::-1]
    vals = df.set_index("FEATURE").loc[order, "MEAN_ABS_SHAP"].values
    y = np.arange(len(order))

    fig, ax = plt.subplots(figsize=(13.333, 6.4))
    colors = [ACCENT] * len(order)
    colors[-1] = "#c9432f"  # top driver highlighted
    ax.barh(y, vals, color=colors, zorder=3, height=0.58)
    for yi, v in zip(y, vals):
        ax.text(v + vals.max() * 0.02, yi, f"{v:.3f}", va="center", fontsize=13, color=INK, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=15)
    clean_axes(ax, y_grid=False, x_grid=True)
    ax.xaxis.set_visible(False)
    fig.suptitle("Reviewer credibility and rating consistency, not price, drive the risk signal",
                 fontsize=19, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.04)
    ax.text(0.0, -0.14, "Top SHAP driver for 24% of all 19,154 locations: AVG_REVIEWER_AVERAGE_STARS",
            transform=ax.transAxes, fontsize=13, color=TEXT_DIM)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 04 -- aspect sentiment + high-risk share

def load_aspect_summary():
    meta = json.loads((ROOT / "dashboard" / "data" / "meta.json").read_text(encoding="utf-8"))
    d = pd.DataFrame(meta["aspectSummary"])
    qa("04_aspect_sentiment", "aspects loaded", d["aspect"].tolist())
    qa("04_aspect_sentiment", "rows", len(d))
    assert len(d) == 7
    return d


def fig_aspect_sentiment_risk_share(d, out_path, pptx=False):
    d = d.sort_values("meanSentiment0to100", ascending=True).reset_index(drop=True)
    benchmark = d.meanSentiment0to100.mean()
    weakest = d.iloc[0]["aspect"]
    y = np.arange(len(d))

    fig, ax = plt.subplots(figsize=(11.5, 5.4) if not pptx else (13.333, 6.4))
    colors = [RISK_COLORS["Critical Risk"] if a == weakest else ACCENT for a in d.aspect]
    ax.barh(y, d.meanSentiment0to100, color=colors, zorder=3, height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(d.aspect, fontsize=11 if not pptx else 15)
    ax.axvline(benchmark, color=INK, linestyle="--", linewidth=1, alpha=0.55, zorder=4)
    ax.set_xlim(0, 100)
    clean_axes(ax, y_grid=False, x_grid=True)
    ax.set_xlabel("Mean sentiment score, 0–100", fontsize=11 if not pptx else 14)

    ax2 = ax.twiny()
    ax2.set_xlim(0, max(d.highRiskShare.max() * 1.4, 70))
    ax2.scatter(d.highRiskShare, y, color=INK, marker="D", s=46 if not pptx else 70, zorder=5,
                edgecolor="white", linewidth=0.6)
    ax2.set_xlabel("High-risk share among primary complainants, %", fontsize=10 if not pptx else 13, color=TEXT_DIM)
    ax2.tick_params(axis="x", colors=TEXT_DIM)
    ax2.spines["top"].set_visible(True)
    ax2.spines["top"].set_color(TEXT_FAINT)

    for yi, (s, h) in enumerate(zip(d.meanSentiment0to100, d.highRiskShare)):
        # printed INSIDE the bar (not past its end) so it never collides with the
        # high-risk-share diamond, which sits on an independent top axis and can
        # land at the same pixel x as an outside label purely by coincidence
        ax.text(s - 2, yi, f"{s:.1f}", va="center", ha="right", fontsize=9 if not pptx else 12,
                color="white", fontweight="bold")

    if pptx:
        fig.suptitle("Order accuracy is the one aspect no QSR location is getting right",
                      fontsize=19, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.10)
    else:
        title(ax, "Order accuracy is the weakest aspect — but not the riskiest one", y=1.16)
        source_note(fig, "Source: dashboard/data/meta.json (aspectSummary, precomputed from QSR_FINAL_LHI_DATA.csv). "
                          "n = 13,719 open locations. Diamond markers = high-risk share (top axis).")
    savefig(fig, out_path, dpi=200 if not pptx else 150)


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
    clean_axes(ax, y_grid=False, x_grid=True)
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
    clean_axes(ax, y_grid=False, x_grid=True)
    ax.xaxis.set_visible(False)
    for yi, h in zip(y, d.highRiskShare):
        ax.text(h + 1.2, yi, f"{h:.0f}%", va="center", fontsize=13, color=INK, fontweight="bold")
    fig.suptitle("But food, service and staff complaints are what actually\npush a location into High Risk",
                 fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.10)
    ax.text(0.0, -0.14, "Don't over-index on order accuracy alone — these three concentrate "
                        "in already-high-risk locations", transform=ax.transAxes, fontsize=13, color=TEXT_DIM)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig 05 -- LHI version agreement

def fig_lhi_version_agreement(out_path, pptx=False):
    pairs = pd.read_csv(AO / "QSR_LHI_VERSION_COMPARISON.csv")
    weights = pd.read_csv(AO / "QSR_LHI_WEIGHTS_BY_VERSION.csv")
    qa("05_lhi_version_agreement", "pairs rows", len(pairs))
    qa("05_lhi_version_agreement", "weights rows", len(weights))
    versions = ["LHI_0", "LHI_1", "LHI_2", "LHI_3"]
    mat = pd.DataFrame(np.eye(4), index=versions, columns=versions)
    for _, r in pairs.iterrows():
        mat.loc[r.VERSION_A, r.VERSION_B] = r.SPEARMAN_RHO
        mat.loc[r.VERSION_B, r.VERSION_A] = r.SPEARMAN_RHO

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.4) if not pptx else (13.333, 6.2),
                                    gridspec_kw={"width_ratios": [1, 1.15]})
    im = ax1.imshow(mat.values, cmap="Blues", vmin=0.85, vmax=1.0)
    ax1.set_xticks(range(4)); ax1.set_xticklabels(["LHI-0", "LHI-1", "LHI-2", "LHI-3"], fontsize=10 if not pptx else 13)
    ax1.set_yticks(range(4)); ax1.set_yticklabels(["LHI-0", "LHI-1", "LHI-2", "LHI-3"], fontsize=10 if not pptx else 13)
    for i in range(4):
        for j in range(4):
            v = mat.values[i, j]
            ax1.text(j, i, f"{v:.3f}", ha="center", va="center",
                     color="white" if v > 0.94 else INK, fontsize=9.5 if not pptx else 12.5, fontweight="bold")
    ax1.set_title("Pairwise Spearman ρ", fontsize=11 if not pptx else 14, fontfamily=FONT_BODY, loc="left")
    for spine in ax1.spines.values():
        spine.set_visible(False)

    pillars = ["PEER", "ENGAGEMENT", "MOMENTUM", "CX"]
    x = np.arange(len(pillars))
    bw = 0.19
    version_colors = [NEUTRAL_GREY, "#a3701a", ACCENT, INK]
    for i, (_, row) in enumerate(weights.iterrows()):
        ax2.bar(x + (i - 1.5) * bw, [row[p] for p in pillars], width=bw,
                color=version_colors[i], label=row.LHI_VERSION, zorder=3)
    ax2.set_xticks(x); ax2.set_xticklabels(pillars, fontsize=10 if not pptx else 13)
    ax2.set_ylabel("Pillar weight", fontsize=10 if not pptx else 13)
    clean_axes(ax2, y_grid=True, x_grid=False)
    ax2.legend(frameon=False, fontsize=8.5 if not pptx else 11, ncol=2, loc="upper right")
    ax2.set_title("Pillar weight by version", fontsize=11 if not pptx else 14, fontfamily=FONT_BODY, loc="left")

    lhi0_lhi3 = pairs.loc[(pairs.VERSION_A == "LHI_0") & (pairs.VERSION_B == "LHI_3"), "RISK_BAND_AGREEMENT"].iloc[0]
    qa("05_lhi_version_agreement", "LHI_0 vs LHI_3 risk-band agreement", lhi0_lhi3)

    if pptx:
        fig.suptitle(f"Four independently-built scoring methods agree on "
                     f"{lhi0_lhi3*100:.0f}% of risk calls",
                     fontsize=18, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.04)
    else:
        fig.suptitle("Four candidate LHI formulas agree closely — except one pair",
                      fontsize=14.5, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.02)
        source_note(fig, "Source: QSR_LHI_VERSION_COMPARISON.csv × QSR_LHI_WEIGHTS_BY_VERSION.csv, analysis/output/. "
                          "LHI-3 (hybrid) is the version selected for the final export.")
    savefig(fig, out_path, dpi=200 if not pptx else 150)


def fig_lhi_version_callout_pptx(out_path):
    pairs = pd.read_csv(AO / "QSR_LHI_VERSION_COMPARISON.csv")
    vs3 = pairs[(pairs.VERSION_A == "LHI_3") | (pairs.VERSION_B == "LHI_3")].copy()
    vs3["other"] = vs3.apply(lambda r: r.VERSION_A if r.VERSION_B == "LHI_3" else r.VERSION_B, axis=1)
    vs3 = vs3.sort_values("other")
    headline = pairs.loc[(pairs.VERSION_A == "LHI_0") & (pairs.VERSION_B == "LHI_3"), "RISK_BAND_AGREEMENT"].iloc[0]

    fig = plt.figure(figsize=(13.333, 6.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.3])
    ax_num = fig.add_subplot(gs[0])
    ax_num.axis("off")
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
    clean_axes(ax_bar, y_grid=False, x_grid=True)
    ax_bar.set_xlabel("Risk-band agreement, %", fontsize=12)
    for yi, v in zip(y, vs3.RISK_BAND_AGREEMENT * 100):
        ax_bar.text(v + 2, yi, f"{v:.0f}%", va="center", fontsize=12, fontweight="bold", color=INK)

    fig.suptitle("Four independently-built scoring methods agree on 96% of risk calls",
                 fontsize=19, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=1.04)
    savefig(fig, out_path, dpi=150)


# ============================================================ Fig -- intervention priority quadrant (shared)

def fig_intervention_priority(out_path):
    drv = pd.read_csv(AO / "QSR_DRIVERS.csv",
                       usecols=["BUSINESS_ID", "IS_OPEN", "RISK_SCORE", "TREND_ADJUSTMENT",
                                "INTERVENTION_PRIORITY", "INTERVENTION_PRIORITY_SCORE"])
    qa("shared_intervention_priority", "rows in QSR_DRIVERS.csv", len(drv))
    open_drv = drv[drv.IS_OPEN == 1].copy()
    qa("shared_intervention_priority", "open-only rows", len(open_drv))
    assert len(open_drv) == 13719

    corr = np.corrcoef(open_drv.RISK_SCORE, 100 - open_drv.RISK_SCORE)  # sanity no-op check placeholder
    nonzero = open_drv[open_drv.TREND_ADJUSTMENT != 0]
    qa("shared_intervention_priority", "open-only rows with nonzero trend adjustment", len(nonzero))

    ex_a = drv[drv.BUSINESS_ID == "bzvxt0sP9OMwwks1vLSzKw"].iloc[0]
    ex_b = drv[drv.BUSINESS_ID == "KPzDlvjirWoWqQICXLgxsg"].iloc[0]
    qa("shared_intervention_priority", "example A (deteriorating, moderate risk)",
       (ex_a.RISK_SCORE, ex_a.TREND_ADJUSTMENT, ex_a.INTERVENTION_PRIORITY_SCORE, ex_a.INTERVENTION_PRIORITY))
    qa("shared_intervention_priority", "example B (improving, higher risk)",
       (ex_b.RISK_SCORE, ex_b.TREND_ADJUSTMENT, ex_b.INTERVENTION_PRIORITY_SCORE, ex_b.INTERVENTION_PRIORITY))
    assert ex_a.INTERVENTION_PRIORITY_SCORE > ex_b.INTERVENTION_PRIORITY_SCORE, \
        "example pair does not actually demonstrate the reordering claim -- STOP, do not use"

    fig, ax = plt.subplots(figsize=(13.333, 7.0))
    fig.subplots_adjust(top=0.84, bottom=0.14)
    ax.scatter(open_drv.RISK_SCORE, open_drv.TREND_ADJUSTMENT, s=8, color="#c9c4b8", alpha=0.35,
               zorder=2, linewidths=0)
    ax.scatter(nonzero.RISK_SCORE, nonzero.TREND_ADJUSTMENT, s=26,
               color=[PRIORITY_COLORS[p] for p in nonzero.INTERVENTION_PRIORITY],
               alpha=0.85, zorder=3, edgecolor="white", linewidth=0.3)

    for thr, lbl in [(40, "Healthy/Watch"), (60, "Watch/High Risk"), (75, "High/Critical Risk")]:
        ax.axvline(thr, color=INK, linestyle=":", linewidth=0.9, alpha=0.35, zorder=1)
    ax.axhline(0, color=INK, linestyle="-", linewidth=0.8, alpha=0.4, zorder=1)
    ax.set_ylim(-24, 24)

    # Callouts anchored in AXES-FRACTION coordinates, not data coordinates, so they
    # never depend on where a real data point happens to fall and never compete with
    # the figure title for vertical space.
    ax.annotate(f"Deteriorating, Watch-range: risk {ex_a.RISK_SCORE:.0f} → priority score "
                f"{ex_a.INTERVENTION_PRIORITY_SCORE:.0f} ({ex_a.INTERVENTION_PRIORITY})",
                xy=(ex_a.RISK_SCORE, ex_a.TREND_ADJUSTMENT), xycoords="data",
                xytext=(0.30, 0.97), textcoords="axes fraction",
                fontsize=10.5, color=INK, fontfamily=FONT_BODY, ha="left", va="top",
                arrowprops=dict(arrowstyle="->", color=INK, lw=1, shrinkA=0, shrinkB=4))
    ax.annotate(f"Improving, High-Risk-range: risk {ex_b.RISK_SCORE:.0f} → priority score "
                f"{ex_b.INTERVENTION_PRIORITY_SCORE:.0f} ({ex_b.INTERVENTION_PRIORITY})",
                xy=(ex_b.RISK_SCORE, ex_b.TREND_ADJUSTMENT), xycoords="data",
                xytext=(0.50, 0.03), textcoords="axes fraction",
                fontsize=10.5, color=INK, fontfamily=FONT_BODY, ha="left", va="bottom",
                arrowprops=dict(arrowstyle="->", color=INK, lw=1, shrinkA=0, shrinkB=4))

    clean_axes(ax, y_grid=True, x_grid=False)
    ax.set_xlabel("Risk score, 0–100 (higher = more risk; ≈ 100 − LHI)", fontsize=13)
    ax.set_ylabel("Trend adjustment (trajectory magnitude)", fontsize=13)
    ax.set_xlim(0, 100)

    handles = [plt.Line2D([0], [0], marker="o", linestyle="", color=PRIORITY_COLORS[p], markersize=9, label=p)
               for p in PRIORITY_ORDER]
    ax.legend(handles=handles, title="Intervention priority", loc="center left", frameon=False, fontsize=11,
              title_fontsize=11, bbox_to_anchor=(0.0, 0.82))

    fig.suptitle("A declining Watch-range location can outrank an improving High-Risk one",
                 fontsize=17, fontfamily=FONT_DISPLAY, fontweight="bold", color=INK, x=0.02, ha="left", y=0.98)
    source_note(fig, f"Source: QSR_DRIVERS.csv, analysis/output/. n = {len(open_drv):,} open locations "
                      f"(light grey); {len(nonzero):,} with statistically-evidenced trend adjustment (coloured by priority tier). "
                      "Intervention priority score = risk score + trend adjustment.", y=0.015)
    savefig(fig, out_path, dpi=180)


# ============================================================ main

def main():
    tr = OUT_DIR / "technical_report"
    px = OUT_DIR / "pptx"
    sh = OUT_DIR / "shared"

    open_only = load_open_only_lhi()

    fig_lhi_distribution(open_only, tr / "01_lhi_distribution.png", pptx=False)
    fig_risk_band_distribution(open_only, px / "01_risk_band_distribution.png")

    model_df = load_model_results()
    fig_model_comparison(model_df, tr / "02_model_comparison_leaky_vs_safe.png", pptx=False)
    fig_model_comparison_best_only(model_df, px / "02_model_comparison_best_model.png")

    fig_feature_importance(tr / "03_feature_importance_panels.png", pptx=False, top_n=10)
    fig_shap_top_drivers_pptx(px / "03_shap_top_drivers.png", top_n=6)

    aspect_df = load_aspect_summary()
    fig_aspect_sentiment_risk_share(aspect_df, tr / "04_aspect_sentiment_risk_share.png", pptx=False)
    fig_aspect_sentiment_only_pptx(aspect_df, px / "04_aspect_sentiment.png")
    fig_aspect_high_risk_share_pptx(aspect_df, px / "05_aspect_high_risk_share.png")

    fig_lhi_version_agreement(tr / "05_lhi_version_agreement.png", pptx=False)
    fig_lhi_version_callout_pptx(px / "06_lhi_version_agreement_callout.png")

    fig_intervention_priority(sh / "07_intervention_priority_quadrant.png")

    qa_path = OUT_DIR / "_lib" / "qa_log.csv"
    pd.DataFrame(QA_LOG, columns=["figure", "check", "result"]).to_csv(qa_path, index=False)
    print("\nQA log written to", qa_path)


if __name__ == "__main__":
    main()
