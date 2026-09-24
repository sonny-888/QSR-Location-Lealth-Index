"""Adaptive peer-group construction: local 10-mile radius -> city -> state ->
global segment fallback, with the focal business always excluded from its own
peer set (leave-one-out). Recomputed locally (grid-accelerated haversine)
rather than reusing only the aggregate Snowflake peer stats, because building
per-aspect CX priors needs the actual peer *membership*, not just summary
percentiles.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_MI = 3958.8
LOCAL_RADIUS_MI = 10.0
MIN_LOCAL_PEERS = 3


def _haversine_mi(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def build_local_peer_index(open_biz: pd.DataFrame, cell_deg: float = 0.2) -> dict:
    """Grid-bucket open businesses by (segment, lat_cell, lon_cell) so that
    10-mile neighbor search only compares nearby candidates instead of all
    pairs. Returns {(segment, lat_cell, lon_cell): sub-dataframe}."""
    df = open_biz.copy()
    df["_lat_cell"] = (df["LATITUDE"] / cell_deg).round().astype(int)
    df["_lon_cell"] = (df["LONGITUDE"] / cell_deg).round().astype(int)
    index = {}
    for key, g in df.groupby(["QSR_SEGMENT", "_lat_cell", "_lon_cell"]):
        index[key] = g
    return index, cell_deg


def local_peers_within_10mi(business_id, lat, lon, segment, index, cell_deg) -> list:
    lat_cell = int(round(lat / cell_deg))
    lon_cell = int(round(lon / cell_deg))
    candidates = []
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            key = (segment, lat_cell + dlat, lon_cell + dlon)
            if key in index:
                candidates.append(index[key])
    if not candidates:
        return []
    cand = pd.concat(candidates, ignore_index=True)
    cand = cand[cand["BUSINESS_ID"] != business_id]
    if cand.empty:
        return []
    dist = _haversine_mi(lat, lon, cand["LATITUDE"].values, cand["LONGITUDE"].values)
    return cand.loc[dist <= LOCAL_RADIUS_MI, "BUSINESS_ID"].tolist()


def assign_peer_groups(business_df: pd.DataFrame) -> pd.DataFrame:
    """For every business (open or closed), find its peer group of OPEN,
    same-segment businesses using: local 10mi (>=3 peers) -> city -> state ->
    global segment. Returns a DataFrame with BUSINESS_ID, PEER_TIER,
    PEER_GROUP_SIZE, and PEER_IDS (list) with the focal business excluded.
    """
    open_biz = business_df[business_df["IS_OPEN"] == 1].copy()
    index, cell_deg = build_local_peer_index(open_biz)

    by_city_segment = {k: g["BUSINESS_ID"].tolist() for k, g in
                        open_biz.groupby(["CITY", "STATE", "QSR_SEGMENT"])}
    by_state_segment = {k: g["BUSINESS_ID"].tolist() for k, g in
                         open_biz.groupby(["STATE", "QSR_SEGMENT"])}
    by_segment = {k: g["BUSINESS_ID"].tolist() for k, g in
                  open_biz.groupby("QSR_SEGMENT")}

    rows = []
    for r in business_df.itertuples(index=False):
        bid = r.BUSINESS_ID
        local = []
        if pd.notna(r.LATITUDE) and pd.notna(r.LONGITUDE):
            local = local_peers_within_10mi(bid, r.LATITUDE, r.LONGITUDE, r.QSR_SEGMENT, index, cell_deg)
        if len(local) >= MIN_LOCAL_PEERS:
            tier, peers = "TIER_1_LOCAL_10MI", local
        else:
            city_peers = [p for p in by_city_segment.get((r.CITY, r.STATE, r.QSR_SEGMENT), []) if p != bid]
            if len(city_peers) >= MIN_LOCAL_PEERS:
                tier, peers = "TIER_2_CITY_SEGMENT", city_peers
            else:
                state_peers = [p for p in by_state_segment.get((r.STATE, r.QSR_SEGMENT), []) if p != bid]
                if len(state_peers) >= MIN_LOCAL_PEERS:
                    tier, peers = "TIER_3_STATE_SEGMENT", state_peers
                else:
                    tier, peers = "TIER_4_GLOBAL_SEGMENT", [p for p in by_segment.get(r.QSR_SEGMENT, []) if p != bid]
        rows.append((bid, tier, len(peers), peers))

    return pd.DataFrame(rows, columns=["BUSINESS_ID", "PEER_TIER", "PEER_GROUP_SIZE", "PEER_IDS"])
