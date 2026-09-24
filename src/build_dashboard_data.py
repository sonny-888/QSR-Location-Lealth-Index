"""Prepares compact, columnar JSON data files for the QSR LHI dashboard.

Row-of-objects JSON with verbose keys repeated per-record blew the artifact
size budget (11.7MB for locations alone, mostly key-name repetition). This
version uses a columnar layout (one array per field, key paid once) plus
small-integer codes for every categorical field (legend in meta.json), which
cuts the same data down by roughly 5x.

Open locations only, matching the reference dashboard's scope. Writes:
  dashboard/data/locations.json  - columnar per-location data + codebooks
  dashboard/data/evidence.json   - columnar ABSA snippets, non-Healthy only
  dashboard/data/meta.json       - precomputed KPIs / histogram / summaries
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "dashboard" / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ASPECT_COLS = ["FOOD_SENTIMENT", "SERVICE_SENTIMENT", "STAFF_SENTIMENT",
               "CLEANLINESS_SENTIMENT", "WAITING_TIME_SENTIMENT", "ORDER_ACCURACY_SENTIMENT", "VALUE_SENTIMENT"]
ASPECT_KEYS = ["FOOD", "SERVICE", "STAFF", "CLEANLINESS", "WAITING_TIME", "ORDER_ACCURACY", "VALUE"]
ASPECT_LABELS = ["Food", "Service", "Staff", "Cleanliness", "Waiting Time", "Order Accuracy", "Value"]
ASPECT_LETTERS = "FSTCWOV"

RISK_LEGEND = ["Critical Risk", "High Risk", "Watch", "Healthy"]
PRIORITY_LEGEND = ["Critical", "High", "Medium", "Low"]
CONFIDENCE_LEGEND = ["Low", "Medium", "High"]
TRAJECTORY_LEGEND = ["Deteriorating", "Stable", "Improving", "Insufficient Evidence"]
DRIVER_LEGEND = ["PEER", "ENGAGEMENT", "MOMENTUM", "CX"]
SEGMENT_EMOJI = {
    "Pizza": "\U0001F355", "Burger": "\U0001F354", "Sandwich": "\U0001F96A",
    "Fast Food & Other": "\U0001F35F", "Chicken": "\U0001F357", "Coffee & Beverage": "☕",
    "Dessert": "\U0001F370", "Bakery & Breakfast": "\U0001F950",
}


def code_index(series: pd.Series, legend: list[str] | None = None):
    if legend is None:
        legend = sorted(series.dropna().unique().tolist())
    idx = {v: i for i, v in enumerate(legend)}
    codes = series.map(idx)
    return codes, legend


def to_int(series, scale=1, na=-999):
    return [int(round(v * scale)) if pd.notna(v) else na for v in series]


def main():
    final = pd.read_csv(ROOT / "analysis/output/QSR_FINAL_LHI_DATA.csv")
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False,
                       usecols=["BUSINESS_ID", "LATITUDE", "LONGITUDE", "QSR_SEGMENT", "IS_OPEN",
                                "BUSINESS_STARS", "LOADED_REVIEW_COUNT"])
    evidence = pd.read_csv(ROOT / "analysis/output/QSR_ROOT_CAUSE_EVIDENCE.csv")
    weights = pd.read_csv(ROOT / "analysis/output/QSR_LHI_WEIGHTS_BY_VERSION.csv")
    cx_scores = pd.read_csv(ROOT / "analysis/output/QSR_CX_ASPECT_SCORES.csv",
                             usecols=["BUSINESS_ID", "ASPECT", "PEER_PERCENTILE"])
    peer_pct_pivot = cx_scores.pivot_table(index="BUSINESS_ID", columns="ASPECT", values="PEER_PERCENTILE")
    peer_pct_pivot = peer_pct_pivot.add_prefix("PEERPCT_").reset_index()

    df = final.merge(biz, on="BUSINESS_ID", how="left")
    df = df[df["IS_OPEN"] == 1].copy()
    df = df.dropna(subset=["LATITUDE", "LONGITUDE"]).reset_index(drop=True)
    df = df.merge(peer_pct_pivot, on="BUSINESS_ID", how="left")
    print(f"{len(df)} open locations with coordinates")

    seg_codes, seg_legend = code_index(df["QSR_SEGMENT"])
    tier_codes, tier_legend = code_index(df["PEER_TIER"])
    fallback_codes, fallback_legend = code_index(df["FALLBACK_LEVEL"])
    risk_codes, _ = code_index(df["RISK_CATEGORY"], RISK_LEGEND)
    priority_codes, _ = code_index(df["INTERVENTION_PRIORITY"], PRIORITY_LEGEND)
    confidence_codes, _ = code_index(df["LHI_CONFIDENCE"], CONFIDENCE_LEGEND)
    trajectory_codes, _ = code_index(df["TRAJECTORY"].fillna("Insufficient Evidence"), TRAJECTORY_LEGEND)
    top_pos_codes, _ = code_index(df["TOP_POSITIVE_DRIVER"], DRIVER_LEGEND)
    top_neg_codes, _ = code_index(df["TOP_NEGATIVE_DRIVER"], DRIVER_LEGEND)
    top_neg_aspect_codes, _ = code_index(df["TOP_NEGATIVE_ASPECT"], ASPECT_KEYS)

    # EMERGING_ISSUE is null for all but ~21 locations (stage 6's spike detector) --
    # code_index leaves those as NaN (not in the legend), so fill to -1 (== "none").
    ei_codes, ei_legend = code_index(df["EMERGING_ISSUE"])
    ei_codes = ei_codes.fillna(-1).astype(int)

    aspects_cols = {label: to_int(df[col], scale=10, na=-999)
                     for col, label in zip(ASPECT_COLS, ASPECT_LETTERS)}
    aspects_peerpct_cols = {label: to_int(df.get("PEERPCT_" + key, pd.Series([None] * len(df))), scale=1, na=-999)
                             for key, label in zip(ASPECT_KEYS, ASPECT_LETTERS)}

    locations = {
        "n": len(df),
        "codebooks": {
            "segment": seg_legend, "segmentEmoji": [SEGMENT_EMOJI.get(s, "\U0001F37D") for s in seg_legend],
            "peerTier": tier_legend, "fallback": fallback_legend,
            "risk": RISK_LEGEND, "priority": PRIORITY_LEGEND, "confidence": CONFIDENCE_LEGEND,
            "trajectory": TRAJECTORY_LEGEND, "driver": DRIVER_LEGEND, "aspect": ASPECT_LABELS,
            "emergingIssue": ei_legend,
        },
        "id": df["BUSINESS_ID"].tolist(),
        "nm": df["BUSINESS_NAME"].tolist(),
        "ct": df["CITY"].tolist(),
        "st": df["STATE"].tolist(),
        "sg": seg_codes.tolist(),
        "lat": to_int(df["LATITUDE"], scale=100),
        "lon": to_int(df["LONGITUDE"], scale=100),
        "str": to_int(df["BUSINESS_STARS"], scale=10),
        "rv": to_int(df["LOADED_REVIEW_COUNT"], scale=1),
        "lhi": to_int(df["LHI"], scale=10),
        "rsk": risk_codes.tolist(),
        "pri": priority_codes.tolist(),
        "cnf": confidence_codes.tolist(),
        "dq": to_int(df["DATA_QUALITY_SCORE"], scale=1),
        "fb": fallback_codes.tolist(),
        "trj": trajectory_codes.tolist(),
        "tm": to_int(df["TRAJECTORY_MAGNITUDE"], scale=100),
        "pp": to_int(df["PILLAR_PERFORMANCE"], scale=10),
        "eg": to_int(df["PILLAR_ENGAGEMENT"], scale=10),
        "mo": to_int(df["PILLAR_MOMENTUM"], scale=10),
        "cx": to_int(df["PILLAR_CX"], scale=10),
        "tpos": top_pos_codes.tolist(),
        "tneg": top_neg_codes.tolist(),
        "tna": top_neg_aspect_codes.tolist(),
        "aF": aspects_cols["F"], "aS": aspects_cols["S"], "aT": aspects_cols["T"],
        "aC": aspects_cols["C"], "aW": aspects_cols["W"], "aO": aspects_cols["O"], "aV": aspects_cols["V"],
        "pF": aspects_peerpct_cols["F"], "pS": aspects_peerpct_cols["S"], "pT": aspects_peerpct_cols["T"],
        "pC": aspects_peerpct_cols["C"], "pW": aspects_peerpct_cols["W"], "pO": aspects_peerpct_cols["O"],
        "pV": aspects_peerpct_cols["V"],
        "ppct": to_int(df["PEER_RATING_PERCENTILE"], scale=1),
        "sgap": to_int(df["STAR_GAP_TO_PEERS"], scale=100),
        "pt": tier_codes.tolist(),
        "pgs": to_int(df["PEER_GROUP_SIZE"], scale=1),
        "rr": to_int(df["RECENT_REVIEW_COUNT"], scale=1),
        "pr": to_int(df["PRIOR_REVIEW_COUNT"], scale=1),
        "ei": ei_codes.tolist(),
        "opdh": to_int(df["OPERATIONAL_PROFILE_DAYS_WITH_HOURS"], scale=1),
        "rms": to_int(df["RECENT_MEAN_STARS"], scale=10),
        "pms": to_int(df["PRIOR_MEAN_STARS"], scale=10),
    }
    for k in list(locations.keys()):
        v = locations[k]
        if isinstance(v, list) and v and hasattr(v[0], "item"):
            locations[k] = [x.item() if hasattr(x, "item") else x for x in v]

    loc_path = OUT_DIR / "locations.json"
    loc_path.write_text(json.dumps(locations, separators=(",", ":")), encoding="utf-8")
    print(f"locations.json: {len(df)} records, {loc_path.stat().st_size / 1e6:.2f} MB")

    # ---- Evidence: non-Healthy businesses only, 1 most-recent snippet each ----
    non_healthy_ids = set(df.loc[df["RISK_CATEGORY"] != "Healthy", "BUSINESS_ID"])
    ev = evidence[evidence["BUSINESS_ID"].isin(non_healthy_ids)].copy()
    ev = ev.sort_values("REVIEW_TS", ascending=False).groupby("BUSINESS_ID").head(1)
    ev["ASPECT_CODE"] = ev["ASPECT"].map({k: i for i, k in enumerate(ASPECT_KEYS)}).fillna(-1).astype(int)

    evidence_out = {
        "bid": ev["BUSINESS_ID"].tolist(),
        "asp": ev["ASPECT_CODE"].tolist(),
        "sent": to_int(ev["SENTIMENT"], scale=100),
        "txt": [(t or "")[:200] for t in ev["REVIEW_SNIPPET"]],
    }
    ev_path = OUT_DIR / "evidence.json"
    ev_path.write_text(json.dumps(evidence_out, separators=(",", ":")), encoding="utf-8")
    print(f"evidence.json: {len(ev)} businesses, {ev_path.stat().st_size / 1e6:.2f} MB")

    # ---- Meta: precomputed KPIs / histogram / segment mix / aspect summary ----
    n = len(df)
    risk_counts = df["RISK_CATEGORY"].value_counts().reindex(RISK_LEGEND, fill_value=0).to_dict()
    traj_counts = df["TRAJECTORY"].fillna("Insufficient Evidence").value_counts().reindex(TRAJECTORY_LEGEND, fill_value=0).to_dict()
    hist_edges = list(range(0, 101, 4))
    hist_counts, _ = np.histogram(df["LHI"].dropna(), bins=hist_edges)
    seg_counts = df["QSR_SEGMENT"].value_counts().to_dict()

    aspect_summary = []
    for col, key, label in zip(ASPECT_COLS, ASPECT_KEYS, ASPECT_LABELS):
        vals = df[col].dropna()
        is_primary = df["TOP_NEGATIVE_ASPECT"] == key
        n_primary = int(is_primary.sum())
        aspect_summary.append({
            "aspect": label,
            "meanSentiment0to100": round(float(vals.mean()), 1) if len(vals) else None,
            "primaryComplaintCount": n_primary,
            "highRiskShare": round(float((df.loc[is_primary, "RISK_CATEGORY"]
                                    .isin(["Critical Risk", "High Risk"])).mean() * 100), 0) if n_primary else 0,
        })

    meta = {
        "generatedFrom": "QSR_FINAL_LHI_DATA.csv",
        "nOpen": n,
        "avgLhi": round(float(df["LHI"].mean()), 1),
        "medianLhi": round(float(df["LHI"].median()), 1),
        "avgStars": round(float(df["BUSINESS_STARS"].mean()), 2),
        "medianStars": round(float(df["BUSINESS_STARS"].median()), 2),
        "totalReviewsInView": int(df["LOADED_REVIEW_COUNT"].sum()),
        "riskCounts": risk_counts,
        "trajectoryCounts": traj_counts,
        "histogram": {"edges": hist_edges, "counts": [int(c) for c in hist_counts]},
        "segmentCounts": seg_counts,
        "aspectSummary": aspect_summary,
        "states": sorted(df["STATE"].dropna().unique().tolist()),
        "segments": sorted(df["QSR_SEGMENT"].dropna().unique().tolist()),
        "latRange": [round(float(df["LATITUDE"].min()), 2), round(float(df["LATITUDE"].max()), 2)],
        "lonRange": [round(float(df["LONGITUDE"].min()), 2), round(float(df["LONGITUDE"].max()), 2)],
        "lhiVersion": df["LHI_VERSION"].mode().iloc[0] if len(df) else None,
        "lhiVersionLabel": (weights.set_index("LHI_VERSION")
                             .loc[df["LHI_VERSION"].mode().iloc[0].replace("_", "-"), "TYPE"]) if len(df) else None,
        "lhi3Weights": {
            "Peer Performance": round(float(weights.loc[weights["LHI_VERSION"] == "LHI-3", "PEER"].iloc[0]), 4),
            "Engagement": round(float(weights.loc[weights["LHI_VERSION"] == "LHI-3", "ENGAGEMENT"].iloc[0]), 4),
            "Momentum": round(float(weights.loc[weights["LHI_VERSION"] == "LHI-3", "MOMENTUM"].iloc[0]), 4),
            "Customer Experience": round(float(weights.loc[weights["LHI_VERSION"] == "LHI-3", "CX"].iloc[0]), 4),
        },
        "pipelineRunDate": final["PIPELINE_RUN_DATE"].iloc[0] if "PIPELINE_RUN_DATE" in final.columns else None,
    }
    (OUT_DIR / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    print(f"meta.json: {(OUT_DIR / 'meta.json').stat().st_size / 1e3:.1f} KB")
    total = loc_path.stat().st_size + ev_path.stat().st_size + (OUT_DIR / "meta.json").stat().st_size
    print(f"TOTAL data payload: {total / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
