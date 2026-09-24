"""Stage 5 - Peer groups + CX pillar construction.

Recomputes adaptive peer groups locally (lib/peer.py: 10mi -> city -> state
-> global segment, focal business always excluded) so that the per-aspect
peer prior used for shrinkage is a genuine leave-one-out calculation, not
just a reused aggregate. Low-evidence businesses shrink toward their peer
prior (informed by stage 3's Q1 finding that rating variance is noisy at low
review volume); the resulting sentiment is percentile-ranked to build the
CX pillar.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, ASPECTS, require, log, percentile_rank, shrink_to_prior
from lib.peer import assign_peer_groups

EVIDENCE_HIGH_MIN_MENTIONS = 30
EVIDENCE_MEDIUM_MIN_MENTIONS = 5


def build_peer_groups(biz: pd.DataFrame) -> pd.DataFrame:
    log("Assigning adaptive peer groups (10mi -> city -> state -> global segment)...")
    peer_groups = assign_peer_groups(biz[["BUSINESS_ID", "CITY", "STATE", "QSR_SEGMENT", "LATITUDE", "LONGITUDE", "IS_OPEN"]])
    tier_counts = peer_groups["PEER_TIER"].value_counts()
    log(f"Peer tier assignment: {tier_counts.to_dict()}")
    peer_groups.to_csv(OUTPUT_DIR / "QSR_PEER_GROUPS.csv",
                        index=False, columns=["BUSINESS_ID", "PEER_TIER", "PEER_GROUP_SIZE"])
    return peer_groups


def leave_one_out_prior(aspect_df: pd.DataFrame, peer_groups: pd.DataFrame, aspect: str) -> pd.Series:
    """Volume-weighted mean sentiment among each business's own peer list."""
    sub = aspect_df[aspect_df["ASPECT"] == aspect].set_index("BUSINESS_ID")
    sent = sub["RECENCY_WEIGHTED_SENTIMENT"]
    weight = sub["N_MENTIONS"]

    priors = {}
    for row in peer_groups.itertuples(index=False):
        peers = row.PEER_IDS
        if not peers:
            priors[row.BUSINESS_ID] = np.nan
            continue
        peer_sent = sent.reindex(peers).dropna()
        if peer_sent.empty:
            priors[row.BUSINESS_ID] = np.nan
            continue
        peer_weight = weight.reindex(peer_sent.index).fillna(1.0)
        priors[row.BUSINESS_ID] = float(np.average(peer_sent, weights=peer_weight))
    return pd.Series(priors, name="PEER_PRIOR")


def main():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    aspect_path = OUTPUT_DIR / "QSR_ASPECT_BUSINESS_SUMMARY.csv"
    require(aspect_path.exists(), f"Missing {aspect_path} -- run stage 4 first")
    aspect_df = pd.read_csv(aspect_path)

    peer_groups = build_peer_groups(biz)

    segment_map = biz.set_index("BUSINESS_ID")["QSR_SEGMENT"]
    state_map = biz.set_index("BUSINESS_ID")["STATE"]

    aspect_scores = []
    for aspect in ASPECTS:
        log(f"Scoring CX aspect: {aspect}")
        prior = leave_one_out_prior(aspect_df, peer_groups, aspect)
        sub = aspect_df[aspect_df["ASPECT"] == aspect].set_index("BUSINESS_ID").reindex(biz["BUSINESS_ID"])
        sub["PEER_PRIOR"] = prior.reindex(sub.index)
        # Fall back to segment-level prior for any business whose own peer list
        # produced no usable prior (tiny/global-only groups) -- visible, not silent.
        seg_prior = aspect_df[aspect_df["ASPECT"] == aspect].assign(
            SEG=lambda d: d["BUSINESS_ID"].map(segment_map)
        ).groupby("SEG")["RECENCY_WEIGHTED_SENTIMENT"].mean()
        sub["PRIOR_FALLBACK_USED"] = sub["PEER_PRIOR"].isna()
        fallback_mask = sub["PEER_PRIOR"].isna()
        if fallback_mask.any():
            fill_values = sub.loc[fallback_mask].index.map(segment_map).map(seg_prior).astype(float).values
            sub.loc[fallback_mask, "PEER_PRIOR"] = fill_values

        raw_mean = sub["RAW_MEAN_SENTIMENT"].fillna(sub["PEER_PRIOR"])
        n_eff = sub["N_MENTIONS"].fillna(0)
        shrunk = shrink_to_prior(raw_mean, n_eff, sub["PEER_PRIOR"].fillna(0), prior_strength=10.0)
        absolute_score = 50 * (shrunk + 1)

        # Percentile against same segment+state population as a practical
        # approximation of "against this business's own peer list" (exact
        # per-business percentile against individualized peer sets isn't
        # vectorizable cleanly; segment+state is the same reference frame
        # TIER_2/3 already falls back to).
        group_key = sub.index.map(segment_map).astype(str) + "|" + sub.index.map(state_map).astype(str)
        pct = absolute_score.groupby(group_key).transform(percentile_rank)

        out = pd.DataFrame({
            "BUSINESS_ID": sub.index,
            "ASPECT": aspect,
            "N_MENTIONS": n_eff.values,
            "RAW_SENTIMENT": sub["RAW_MEAN_SENTIMENT"].values,
            "PEER_PRIOR": sub["PEER_PRIOR"].values,
            "PRIOR_FALLBACK_USED": sub["PRIOR_FALLBACK_USED"].values,
            "SHRUNK_SENTIMENT": shrunk.values,
            "ABSOLUTE_SCORE_0_100": absolute_score.values,
            "PEER_PERCENTILE": pct.values,
        })
        aspect_scores.append(out)

    aspect_scores_df = pd.concat(aspect_scores, ignore_index=True)
    aspect_scores_df.to_csv(OUTPUT_DIR / "QSR_CX_ASPECT_SCORES.csv", index=False)

    # CX pillar = equal-weight mean of the aspect peer-percentiles (7 aspects
    # as of the Order Accuracy addition -- see ASPECTS in lib/common.py).
    cx_pillar = aspect_scores_df.groupby("BUSINESS_ID")["PEER_PERCENTILE"].mean().rename("PILLAR_CX")
    total_mentions = aspect_scores_df.groupby("BUSINESS_ID")["N_MENTIONS"].sum().rename("TOTAL_ASPECT_MENTIONS")

    evidence = pd.cut(
        total_mentions, bins=[-1, EVIDENCE_MEDIUM_MIN_MENTIONS - 1, EVIDENCE_HIGH_MIN_MENTIONS - 1, np.inf],
        labels=["Low", "Medium", "High"],
    ).rename("CX_EVIDENCE_CONFIDENCE")

    cx_out = pd.concat([cx_pillar, total_mentions, evidence], axis=1).reset_index()
    cx_out = cx_out.rename(columns={"index": "BUSINESS_ID"})
    cx_out.to_csv(OUTPUT_DIR / "QSR_CX_PILLAR.csv", index=False)

    log(f"CX evidence confidence distribution: {cx_out['CX_EVIDENCE_CONFIDENCE'].value_counts().to_dict()}")
    log("Stage 5 complete.")


if __name__ == "__main__":
    main()
