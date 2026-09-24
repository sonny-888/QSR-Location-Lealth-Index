"""
Content model for the animated executive PPTX (Phase: Final Animated PPTX).

Every number here is copied verbatim from the already-released, frozen chart-pack
PNGs and their generating functions in generate_final.py (fig_risk_band_distribution_pptx,
fig_model_comparison_best_only_pptx, fig_shap_top_drivers_pptx, fig_aspect_sentiment_only_pptx,
fig_aspect_high_risk_share_pptx, fig_lhi_version_callout_pptx, fig_early_warning_callout_pptx)
and from analysis/output/*.csv as cited in each source note below. Nothing here is invented.

Slide order matches the user's explicit instruction:
P1 risk-band distribution -> P2 LEAKY/SAFE -> P3 SHAP drivers -> P4 aspect sentiment ->
P5 high-risk share -> P6 LHI version comparison -> P7 early warning -> Fig 11 intervention priority.
"""

INK = "141F28"
TEXT_DIM = "57626D"
TEXT_FAINT = "8B93A0"
BORDER = "DCD9D2"
ACCENT = "2E6B78"
ACCENT_SOFT = "E6EEF0"
NEUTRAL_GREY = "9AA2AD"
WHITE = "FFFFFF"
RISK_COLORS = {
    "Healthy": "2E7D5B",
    "Watch": "BF8B2E",
    "High Risk": "C1652E",
    "Critical Risk": "AB3A2E",
}

FONT_DISPLAY = "Cambria"
FONT_BODY = "Calibri"

SLIDE_W_IN = 13.333
SLIDE_H_IN = 7.5

# ---------------------------------------------------------------------------
# SLIDE 1 -- Risk-band distribution
# ---------------------------------------------------------------------------
SLIDE_1 = dict(
    key="risk_band_distribution",
    kicker="PORTFOLIO RISK  ·  01 / 08",
    title="Risk is concentrated in a sizeable minority of QSR locations",
    bars=[
        ("Healthy", 3856, 28, RISK_COLORS["Healthy"]),
        ("Watch", 4806, 35, RISK_COLORS["Watch"]),
        ("High Risk", 3528, 26, RISK_COLORS["High Risk"]),
        ("Critical Risk", 1529, 11, RISK_COLORS["Critical Risk"]),
    ],
    key_number="37%",
    key_number_label="High Risk + Critical Risk",
    callout="High Risk + Critical Risk = 5,057 of 13,719 open locations (37%)",
    source="Source: QSR_FINAL_LHI_DATA.csv, analysis/output/. n = 13,719 open locations.",
    build="Morph — bars grow from zero in neutral grey, then recolour to risk bands; High + Critical nudge forward and the 37% callout fades in.",
    transition="morph",
)

# ---------------------------------------------------------------------------
# SLIDE 2 -- LEAKY vs SAFE model comparison
# ---------------------------------------------------------------------------
SLIDE_2 = dict(
    key="model_comparison",
    kicker="MODEL INTEGRITY  ·  02 / 08",
    title="Our closure-prediction model looked 97% accurate — until we removed the "
          "features that were secretly measuring closure itself",
    bars=[
        ("Naive model\n(leaky features included)", 0.969, NEUTRAL_GREY),
        ("Corrected model\n(leakage-audited features)", 0.832, ACCENT),
    ],
    baseline=0.5,
    baseline_label="baseline = 0.5",
    drop_label="−0.14 AUC",
    source="Source: QSR_MODEL_RESULTS.csv, analysis/output/. Best SAFE model (XGBoost) vs. the same "
           "architecture on the naive LEAKY feature set. n = 3,831 test-set holdout.",
    build="Wipe + Morph — naive bar grows first and holds, then the corrected bar grows beside it; a bracket draws the −0.14 AUC gap, caption fades in.",
    transition="morph",
)

# ---------------------------------------------------------------------------
# SLIDE 3 -- SHAP / model drivers
# ---------------------------------------------------------------------------
SLIDE_3 = dict(
    key="shap_drivers",
    kicker="RISK DRIVERS  ·  03 / 08",
    title="Reviewer credibility and rating consistency, not price, drive the risk signal",
    bars=[
        ("TIPS_PER_LOADED_REVIEW", 0.034, ACCENT),
        ("CHECKIN_ACTIVE_MONTHS", 0.034, ACCENT),
        ("PRICE_RANGE", 0.039, ACCENT),
        ("REVIEW_STAR_STDDEV", 0.040, ACCENT),
        ("AVG_REVIEWER_AVERAGE_STARS", 0.044, ACCENT),
        ("DAYS_WITH_HOURS", 0.044, RISK_COLORS["Critical Risk"]),
    ],
    caption="Top SHAP driver for 24% of all 19,154 locations: AVG_REVIEWER_AVERAGE_STARS",
    source="Source: QSR_ML_FEATURE_IMPORTANCE.csv, analysis/output/. Mean |SHAP| value, Random Forest, "
           "SAFE feature set. Top 6 of 38 exported features. n = 3,831 test-set holdout.",
    build="Sequential Wipe — bars reveal strongest to weakest, top bar highlights, caption fades in beneath.",
    transition="fade",
)

# ---------------------------------------------------------------------------
# SLIDE 4 -- Aspect sentiment
# ---------------------------------------------------------------------------
SLIDE_4 = dict(
    key="aspect_sentiment",
    kicker="CUSTOMER EXPERIENCE  ·  04 / 08",
    title="Order accuracy is the one aspect no QSR location is getting right",
    bars=[
        ("Service", 64.3, ACCENT),
        ("Staff", 63.8, ACCENT),
        ("Value", 63.6, ACCENT),
        ("Food", 63.6, ACCENT),
        ("Cleanliness", 59.5, ACCENT),
        ("Waiting Time", 58.9, ACCENT),
        ("Order Accuracy", 36.6, RISK_COLORS["Critical Risk"]),
    ],
    caption="36.6 vs. 58.9–64.9 for every other aspect — a 22-point gap",
    source="Source: dashboard/data/meta.json (aspectSummary, precomputed from QSR_FINAL_LHI_DATA.csv). "
           "n = 13,719 open locations. Mean sentiment score, 0–100 scale.",
    build="Morph — all seven bars grow together in neutral grey, six recolour to accent teal, Order Accuracy recolours to red a beat later; gap bracket and caption follow.",
    transition="morph",
)

# ---------------------------------------------------------------------------
# SLIDE 5 -- High-risk share
# ---------------------------------------------------------------------------
SLIDE_5 = dict(
    key="high_risk_share",
    kicker="CUSTOMER EXPERIENCE  ·  05 / 08",
    title="But food, service and staff complaints are what actually push a location into High Risk",
    bars=[
        ("Food", 58, RISK_COLORS["High Risk"]),
        ("Service", 54, RISK_COLORS["High Risk"]),
        ("Staff", 43, RISK_COLORS["High Risk"]),
        ("Waiting Time", 39, NEUTRAL_GREY),
        ("Value", 24, NEUTRAL_GREY),
        ("Order Accuracy", 23, NEUTRAL_GREY),
        ("Cleanliness", 22, NEUTRAL_GREY),
    ],
    caption="Don't over-index on order accuracy alone — these three concentrate in already-high-risk locations",
    source="Source: dashboard/data/meta.json (aspectSummary, highRiskShare). n = 13,719 open locations.",
    build="Fade in from Slide 4 (deliberately not a Morph — different metric, same 7 aspects), bars Wipe in grey, Food/Service/Staff recolour to orange, caption fades in.",
    transition="fade",
)

# ---------------------------------------------------------------------------
# SLIDE 6 -- LHI version comparison
# ---------------------------------------------------------------------------
SLIDE_6 = dict(
    key="lhi_version_agreement",
    kicker="METHODOLOGY ROBUSTNESS  ·  06 / 08",
    title="Four independently-built scoring methods agree on 96% of risk calls",
    big_number="96%",
    big_number_sub="risk-band agreement\nbaseline vs. selected hybrid version",
    bars=[
        ("LHI-3 vs. LHI-0", 96, ACCENT),
        ("LHI-3 vs. LHI-1", 84, ACCENT),
        ("LHI-3 vs. LHI-2", 82, ACCENT),
    ],
    source="Source: QSR_LHI_VERSION_COMPARISON.csv, analysis/output/. Risk-band agreement between the "
           "selected hybrid version (LHI-3) and each alternative construction.",
    build="Wipe — 96% headline fades in, then the three comparison bars wipe in top to bottom.",
    transition="fade",
)

# ---------------------------------------------------------------------------
# SLIDE 7 -- Early warning
# ---------------------------------------------------------------------------
SLIDE_7 = dict(
    key="early_warning",
    kicker="EARLY WARNING  ·  07 / 08",
    title="268 locations look fine today — and are already trending down",
    big_number="268",
    big_number_color=RISK_COLORS["Critical Risk"],
    big_number_sub="of 347 statistically-evidenced deteriorating locations\nare still classified Healthy or Watch today",
    source="Source: QSR_DRIVERS.csv, QSR_FINAL_LHI_DATA.csv, dashboard/data/meta.json (trajectoryCounts). "
           "n = 347 open locations with a statistically-evidenced deteriorating trajectory (bootstrap CI, "
           "stage 06); this is a validated 2-point recent-vs-prior comparison, not a multi-point trend line.",
    build="Fade — title fades in, big number grows/fades in, subtitle fades in beneath.",
    transition="fade",
)

# ---------------------------------------------------------------------------
# Fig 11 -- Intervention priority (hybrid: frozen chart-pack image + native overlay)
# ---------------------------------------------------------------------------
SLIDE_8 = dict(
    key="intervention_priority",
    kicker="ACTION PRIORITY  ·  08 / 08",
    image_path="chart_pack/shared/fig_11_intervention_priority_quadrant_final.png",
    image_w_px=2482,
    image_h_px=1475,
    caption_native="The recommendation engine looks at where a location is heading, not just where it sits today.",
    source="Chart reproduced unmodified from the released technical-report chart pack (fig_11). "
           "Source: QSR_DRIVERS.csv, analysis/output/. n = 13,719 open locations; 499 with statistically-evidenced trend adjustment.",
    build="Fade — the released chart fades in as a single static image (frozen, not regenerated); a native spotlight outline Wipes onto each of the two annotated examples already labelled on the chart; a closing takeaway line fades in.",
    transition="fade",
)

SLIDES = [SLIDE_1, SLIDE_2, SLIDE_3, SLIDE_4, SLIDE_5, SLIDE_6, SLIDE_7, SLIDE_8]
