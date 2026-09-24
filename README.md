# QSR Location Health Index

A digital-health scorecard for quick-service restaurant (QSR) locations, built from the
[Yelp Open Dataset](https://business.yelp.com/data/resources/open-dataset/). Scores 19,154
locations across four pillars (peer standing, engagement, momentum, and customer experience),
flags at-risk outlets, and explains *why* each score is what it is.

This started as a team employer project for **VP Analytics**, delivered as part of the
LSE Data Analytics Career Accelerator. My own focus within the team was the exploratory
analysis, the NLP-based aspect-level sentiment model, building the Location Health Index
scoring system, and the interactive HTML operator's dashboard — the pieces in this repo
reflect that work.

## What it does

- **Scores every location 0–100** on four pillars, built from three independent methods
  (business judgement, statistics, and model-driven feature importance) blended into one
  final construction, then stress-tested against five deliberately different alternative
  weightings.
- **Reads customer reviews for seven operational aspects** (food, service, staff,
  cleanliness, wait time, order accuracy, value) using a transparent, rule-based sentiment
  model — chosen over a black-box model specifically so every scoring decision can be
  inspected and challenged.
- **Separates health from direction**: a location's current score, its recent trend, and
  the confidence behind that trend are reported as three distinct fields, not collapsed
  into one number.
- **Validates its own modelling honestly**: an early version of the underlying classifier
  looked 97% accurate at predicting open-vs-closed status, until a leakage audit showed it
  was just detecting review recency, not health. The corrected, leakage-audited model
  (0.832 ROC-AUC) is the one this project actually trusts — see the technical report for
  the full audit.

## Repository structure

```
report/         Full technical report (approach, model design, assumptions, limitations)
notebook/       End-to-end analysis notebook (EDA, NLP, scoring, validation)
presentation/   Executive presentation deck
dashboard/      Self-contained interactive HTML dashboard + its build scripts
figures/        Final chart assets used in the report and deck
src/            Pipeline source: analysis/ (13-stage scoring pipeline) and
                chart_pack_lib/ (chart + deck generation scripts)
requirements.txt
```

## Running it

The dashboard (`dashboard/QSR_Location_Health_Dashboard.html`) is fully self-contained —
open it directly in a browser, no server required.

The analysis pipeline (`src/analysis/`) was built against Snowflake-exported CSVs and runs
as thirteen independent, re-runnable stages (`01_data_quality_audit.py` through
`13_final_export.py`). Install dependencies with:

```bash
pip install -r requirements.txt
```

Raw data (the Yelp Open Dataset export) isn't included in this repo due to size — the
pipeline expects the same CSV exports described in the technical report's data section.

## Key numbers

| | |
|---|---|
| Locations scored | 19,154 (13,719 open) |
| Reviews analysed | 1.16M |
| Leakage-audited model accuracy | 0.832 ROC-AUC |
| Rank stability across 5 alternative weightings | ≥ 0.95 Spearman correlation |

## Notes

- This was a team project; the report and presentation carry the full team's authorship.
  This repository is my own record of the parts I built and led.
- No claim in the report describes current operating conditions — the underlying data is
  a historical snapshot through 19 January 2022.
