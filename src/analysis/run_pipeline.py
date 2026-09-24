"""Orchestrates the full QSR LHI pipeline, stages 1-13, in order.

Each stage is a standalone script that can also be run independently; this
just chains them and stops (loudly) on the first failure. Re-run safe: every
stage recomputes and overwrites its own output files.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

STAGES = [
    "01_data_quality_audit.py",
    "02_extract_qsr_reviews.py",
    "03_eda_deep_dive.py",
    "04_aspect_sentiment.py",
    "05_peer_cx_scoring.py",
    "06_momentum_trajectory.py",
    "07_feature_lineage_and_leakage_audit.py",
    "08_ml_modelling.py",
    "09_lhi_versions.py",
    "10_robustness_sensitivity.py",
    "11_explainability_and_drivers.py",
    "12_fallback_confidence_priority.py",
    "13_final_export.py",
]


def main():
    here = Path(__file__).resolve().parent
    py = sys.executable
    t0 = time.time()
    for stage in STAGES:
        print(f"\n{'=' * 70}\nRunning {stage}\n{'=' * 70}", flush=True)
        t_stage = time.time()
        result = subprocess.run([py, str(here / stage)], cwd=here)
        if result.returncode != 0:
            print(f"\nPIPELINE STOPPED: {stage} failed (exit code {result.returncode}).", file=sys.stderr)
            sys.exit(result.returncode)
        print(f"{stage} finished in {time.time() - t_stage:.0f}s", flush=True)
    print(f"\nPipeline complete in {time.time() - t0:.0f}s. Final output: analysis/output/QSR_FINAL_LHI_DATA.csv")


if __name__ == "__main__":
    main()
