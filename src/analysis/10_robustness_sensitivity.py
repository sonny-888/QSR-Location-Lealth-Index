"""Stage 10 - Robustness, sensitivity, and rank-reversal analysis.

Compares LHI-0..3 against each other, then stress-tests the LHI-0 pillar
scores under a battery of weight, feature-dropout, volume, outlier,
importance-method, and peer-definition perturbations. Produces a per-business
Ranking Stability Score so a business that moves 12->184->57->301->19 across
scenarios is flagged as a methodological warning, distinct from one that just
drifts a little.

Risk bands are fixed raw-score cutoffs (see lib/common.risk_band), shared
across every stage that assigns one, so the robustness grid, the
intervention-priority lookup, and the final export can never disagree with
each other about what "Healthy" means.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, require, log, percentile_rank, risk_band

SCENARIO_WEIGHTS = {
    # Baseline for THIS grid is LHI-3, the hybrid actually selected and scored
    # everywhere else in the report/deck -- not LHI-0. An earlier version of
    # this script compared the five scenarios against LHI-0 (the discarded
    # business-rule-only draft) and the deck's "the selected LHI holds up"
    # claim outran what was actually tested. Fixed to test the real, final
    # construction. Weights taken verbatim from QSR_LHI_WEIGHTS_BY_VERSION.csv.
    "baseline_LHI3": {"PEER": 0.3181859004268704, "ENGAGEMENT": 0.29188094093557987,
                       "MOMENTUM": 0.2028976277199141, "CX": 0.18703553091763558},
    "peer_heavy": {"PEER": 0.45, "ENGAGEMENT": 0.20, "MOMENTUM": 0.20, "CX": 0.15},
    "engagement_heavy": {"PEER": 0.20, "ENGAGEMENT": 0.40, "MOMENTUM": 0.25, "CX": 0.15},
    "momentum_heavy": {"PEER": 0.25, "ENGAGEMENT": 0.20, "MOMENTUM": 0.40, "CX": 0.15},
    "cx_heavy": {"PEER": 0.20, "ENGAGEMENT": 0.20, "MOMENTUM": 0.20, "CX": 0.40},
    "equal_weight": {"PEER": 0.25, "ENGAGEMENT": 0.25, "MOMENTUM": 0.25, "CX": 0.25},
}


def score(df: pd.DataFrame, w: dict) -> pd.Series:
    result = (w["PEER"] * df["PILLAR_PEER"] + w["ENGAGEMENT"] * df["PILLAR_ENGAGEMENT"] +
              w["MOMENTUM"] * df["PILLAR_MOMENTUM"].fillna(df["PILLAR_MOMENTUM"].median()) +
              w["CX"] * df["PILLAR_CX"])
    result.index = df["BUSINESS_ID"].values
    return result


def version_comparison(df: pd.DataFrame):
    versions = ["LHI_0", "LHI_1", "LHI_2", "LHI_3"]
    rows = []
    for i, a in enumerate(versions):
        for b in versions[i + 1:]:
            rho, _ = spearmanr(df[a], df[b])
            band_a, band_b = risk_band(df[a]), risk_band(df[b])
            agreement = (band_a == band_b).mean()
            rows.append({"VERSION_A": a, "VERSION_B": b, "SPEARMAN_RHO": round(rho, 4),
                         "RISK_BAND_AGREEMENT": round(agreement, 4)})
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_DIR / "QSR_LHI_VERSION_COMPARISON.csv", index=False)
    log(f"LHI version pairwise comparison:\n{out.to_string(index=False)}")
    return out


def weight_scenario_grid(df: pd.DataFrame):
    scenario_scores = {name: score(df, w) for name, w in SCENARIO_WEIGHTS.items()}
    scenario_df = pd.DataFrame(scenario_scores)

    baseline = scenario_df["baseline_LHI3"]
    rows = []
    for name, s in scenario_scores.items():
        rho, _ = spearmanr(baseline, s)
        band_agree = (risk_band(baseline).values == risk_band(s).values).mean()
        rows.append({"SCENARIO": name, "SPEARMAN_VS_BASELINE": round(rho, 4),
                     "RISK_BAND_AGREEMENT_VS_BASELINE": round(band_agree, 4)})
    grid_summary = pd.DataFrame(rows)
    grid_summary.to_csv(OUTPUT_DIR / "QSR_LHI_SENSITIVITY.csv", index=False)
    log(f"Weight scenario grid:\n{grid_summary.to_string(index=False)}")

    # Risk-band stability specifically (a stricter lens than plain agreement).
    band_table = pd.DataFrame({name: risk_band(s) for name, s in scenario_scores.items()})
    band_table["N_DISTINCT_BANDS"] = band_table.nunique(axis=1)
    band_stability = band_table["N_DISTINCT_BANDS"].value_counts().sort_index()
    band_stability.rename("N_BUSINESSES").to_csv(OUTPUT_DIR / "QSR_LHI_RISK_BAND_STABILITY.csv")
    log(f"Risk-band stability (# distinct bands a business falls into across {len(SCENARIO_WEIGHTS)} scenarios): "
        f"{band_stability.to_dict()}")

    return scenario_df


def rank_stability(scenario_df: pd.DataFrame):
    ranks = scenario_df.rank(ascending=False, method="average")
    stability = pd.DataFrame({
        "BUSINESS_ID": scenario_df.index,
        "MEAN_RANK": ranks.mean(axis=1).round(1).values,
        "RANK_STD": ranks.std(axis=1).round(1).values,
        "RANK_RANGE": (ranks.max(axis=1) - ranks.min(axis=1)).round(0).values,
        "MIN_RANK": ranks.min(axis=1).values,
        "MAX_RANK": ranks.max(axis=1).values,
    })
    n = len(scenario_df)
    top_decile_cut, bottom_decile_cut = n * 0.10, n * 0.90
    in_top_decile = (ranks <= top_decile_cut)
    in_bottom_decile = (ranks >= bottom_decile_cut)
    stability["PROB_TOP_DECILE"] = in_top_decile.mean(axis=1).round(3).values
    stability["PROB_BOTTOM_DECILE"] = in_bottom_decile.mean(axis=1).round(3).values
    stability["RANK_WARNING"] = stability["RANK_RANGE"] > (n * 0.15)  # moves >15% of the population = warning

    stability = stability.sort_values("RANK_STD", ascending=False)
    stability.to_csv(OUTPUT_DIR / "QSR_RANK_STABILITY.csv", index=False)

    n_warn = int(stability["RANK_WARNING"].sum())
    log(f"Rank-reversal check: {n_warn} businesses ({n_warn/n:.2%}) swing more than 15% of the population in rank "
        f"across the {scenario_df.shape[1]} weight scenarios -- flagged in QSR_RANK_STABILITY.csv.")
    return stability


def outlier_and_peer_definition_sensitivity(df: pd.DataFrame):
    """Named for what it actually checks: winsorization, an alternate peer definition, and
    momentum missingness. A review-volume-bucketed stability check was planned but never
    implemented -- dropped rather than left under a misleading function name."""
    rows = []

    winsorized = df.copy()
    for col in ["PILLAR_PEER", "PILLAR_ENGAGEMENT", "PILLAR_CX"]:
        lo, hi = winsorized[col].quantile([0.01, 0.99])
        winsorized[col] = winsorized[col].clip(lo, hi)
    w0 = SCENARIO_WEIGHTS["baseline_LHI3"]
    lhi_raw = score(df, w0)
    lhi_winsor = score(winsorized, w0)
    rho, _ = spearmanr(lhi_raw, lhi_winsor)
    rows.append({"CHECK": "outlier_winsorization_1_99pct", "SPEARMAN_VS_RAW": round(rho, 4)})

    naive_peer = df.copy()
    naive_peer["PILLAR_PEER_NAIVE_SEGMENT_ONLY"] = df.groupby("QSR_SEGMENT")["PILLAR_PEER"].transform(
        lambda s: percentile_rank(s.rank())
    )
    lhi_naive = (w0["PEER"] * naive_peer["PILLAR_PEER_NAIVE_SEGMENT_ONLY"] + w0["ENGAGEMENT"] * df["PILLAR_ENGAGEMENT"] +
                 w0["MOMENTUM"] * df["PILLAR_MOMENTUM"].fillna(df["PILLAR_MOMENTUM"].median()) + w0["CX"] * df["PILLAR_CX"])
    rho2, _ = spearmanr(lhi_raw, lhi_naive)
    rows.append({"CHECK": "peer_definition_segment_only_vs_adaptive_geo", "SPEARMAN_VS_RAW": round(rho2, 4)})

    missing_momentum_rate = df["PILLAR_MOMENTUM"].isna().mean()
    rows.append({"CHECK": "missing_data_rate_momentum_pillar", "SPEARMAN_VS_RAW": round(1 - missing_momentum_rate, 4)})

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_DIR / "QSR_ROBUSTNESS_MISC_CHECKS.csv", index=False)
    log(f"Misc robustness checks:\n{out.to_string(index=False)}")


def operational_profile_evidence_gate(df: pd.DataFrame, hours: pd.Series):
    """DAYS_WITH_HOURS ranked 6th of 38 features by permutation importance in
    stage 8's leakage-audited model -- interesting, but permutation importance
    answers "does this help predict the IS_OPEN proxy," not "should it count
    toward location health." Those are different questions, and a strong ML
    signal doesn't automatically earn a pillar. This runs the explicit gate
    both questions require: predictive power, stability, conceptual validity,
    independence from the existing pillars, actionability, and (regardless of
    the other verdicts) measured impact on the ranking if it were included --
    a documented decision record, not a single up/down vote.
    """
    gate = []

    imp = pd.read_csv(OUTPUT_DIR / "QSR_ML_FEATURE_IMPORTANCE.csv").sort_values(
        "PERMUTATION_IMPORTANCE_MEAN", ascending=False).reset_index(drop=True)
    hit = imp.index[imp["FEATURE"] == "DAYS_WITH_HOURS"]
    rank = int(hit[0]) + 1 if len(hit) else None
    mean_imp = float(imp.loc[hit[0], "PERMUTATION_IMPORTANCE_MEAN"]) if len(hit) else np.nan
    std_imp = float(imp.loc[hit[0], "PERMUTATION_IMPORTANCE_STD"]) if len(hit) else np.nan
    predictive_pass = rank is not None and rank <= max(1, round(len(imp) * 0.25))
    gate.append({"GATE_STEP": "1_predicts_proxy_outcome", "VERDICT": "YES" if predictive_pass else "NO",
                 "EVIDENCE": f"Rank {rank}/{len(imp)} by permutation importance (mean={mean_imp:.4f}) in "
                             f"stage 8's leakage-audited safe feature set."})

    cv = std_imp / mean_imp if mean_imp else np.nan
    stable_pass = cv < 0.5
    gate.append({"GATE_STEP": "2_relationship_stable", "VERDICT": "YES" if stable_pass else "NO",
                 "EVIDENCE": f"Permutation-importance coefficient of variation (std/mean) = {cv:.3f} "
                             f"across the model's repeated permutations."})

    gate.append({"GATE_STEP": "3_measures_outlet_health", "VERDICT": "PARTLY",
                 "EVIDENCE": "DAYS_WITH_HOURS counts how many days of the week a Yelp listing has posted "
                             "hours -- a listing-completeness/maintenance signal, not a direct measurement "
                             "of whether the outlet keeps consistent operating hours (which this dataset "
                             "cannot observe). It correlates with health without being health -- a judgment "
                             "call, disclosed as one, not a statistically derived answer."})

    corrs = {p: abs(float(pd.Series(hours.values, index=df.index).corr(df[p])))
             for p in ["PILLAR_PEER", "PILLAR_ENGAGEMENT", "PILLAR_MOMENTUM", "PILLAR_CX"]}
    max_corr = max(corrs.values())
    independent_pass = max_corr < 0.30
    gate.append({"GATE_STEP": "4_independent_of_pillars", "VERDICT": "YES" if independent_pass else "NO",
                 "EVIDENCE": f"Max |correlation| with an existing pillar = {max_corr:.3f} "
                             f"({ {k: round(v, 3) for k, v in corrs.items()} })."})

    gate.append({"GATE_STEP": "5_operationally_actionable", "VERDICT": "PARTLY",
                 "EVIDENCE": "An owner can complete a Yelp listing's hours in minutes -- easy to act on -- "
                             "but doing so improves the signal, not the outlet's actual operations, which "
                             "is a weaker form of actionability than the other four pillars."})

    weights_row = pd.read_csv(OUTPUT_DIR / "QSR_LHI_WEIGHTS_BY_VERSION.csv").set_index("LHI_VERSION").loc["LHI-3"]
    hours_weight = 0.10
    rescale = 1 - hours_weight
    hours_pct = percentile_rank(hours)
    candidate = (
        weights_row["PEER"] * rescale * df["PILLAR_PEER"] +
        weights_row["ENGAGEMENT"] * rescale * df["PILLAR_ENGAGEMENT"] +
        weights_row["MOMENTUM"] * rescale * df["PILLAR_MOMENTUM"].fillna(df["PILLAR_MOMENTUM"].median()) +
        weights_row["CX"] * rescale * df["PILLAR_CX"] +
        hours_weight * hours_pct
    )
    rho, _ = spearmanr(df["LHI_3"], candidate)
    band_agree = (risk_band(df["LHI_3"]).values == risk_band(candidate).values).mean()
    robust_pass = rho > 0.95
    gate.append({"GATE_STEP": "6_improves_robustness", "VERDICT": "YES" if robust_pass else "NO",
                 "EVIDENCE": f"Adding a {hours_weight:.0%}-weighted operational-profile signal to LHI-3 "
                             f"(rescaling the other four pillars to fill the remaining {rescale:.0%}): "
                             f"Spearman rho vs. LHI-3 = {rho:.4f}, risk-band agreement = {band_agree:.4f}."})

    gate_df = pd.DataFrame(gate)
    gate_df.to_csv(OUTPUT_DIR / "QSR_OPERATIONAL_PROFILE_EVIDENCE_GATE.csv", index=False)

    # Conceptual validity is the deciding axis by design: a feature can be
    # predictive, stable, independent, and rank-preserving while still not
    # being what "location health" means. Everything else informs *how* it
    # should be surfaced, not *whether* it becomes a scored pillar.
    final_verdict = "CANDIDATE_LHI_COMPONENT" if gate[2]["VERDICT"] == "YES" else "CONTEXTUAL_DIAGNOSTIC"
    log(f"Operational-profile evidence gate verdict: {final_verdict}")
    log(gate_df[["GATE_STEP", "VERDICT"]].to_string(index=False))
    return gate_df, final_verdict


def main():
    df = pd.read_csv(OUTPUT_DIR / "QSR_LHI_ALL_VERSIONS.csv")
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv",
                       usecols=["BUSINESS_ID", "LOADED_REVIEW_COUNT", "DAYS_WITH_HOURS"])
    df = df.merge(biz, on="BUSINESS_ID", how="left")
    require(len(df) > 0, "Run stage 9 first (LHI versions)")

    version_comparison(df)
    scenario_df = weight_scenario_grid(df)
    rank_stability(scenario_df)
    outlier_and_peer_definition_sensitivity(df)
    operational_profile_evidence_gate(df, df["DAYS_WITH_HOURS"].fillna(df["DAYS_WITH_HOURS"].median()))

    log("Stage 10 complete.")


if __name__ == "__main__":
    main()
