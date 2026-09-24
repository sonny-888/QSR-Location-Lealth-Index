"""
Content model for the final 14-slide executive presentation (visual refinement pass).

Every number, title, and claim here is copied or directly paraphrased from either:
  (a) the released chart-pack PNGs (chart_pack/technical_report/, pptx/, shared/), or
  (b) QSR_LHI_Technical_Report.html (the written methodology report).
Nothing is invented, no analytical content changed from the prior version -- only
headlines, text volume, grouping, and visual hierarchy were revised per the visual
refinement brief. No chart is recreated -- every chart slide embeds the actual
released PNG, unmodified.
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

SLIDES = [
    dict(
        key="title",
        kind="title",
        kicker="AGENCY 5  -  VP ANALYTICS EMPLOYER PROJECT",
        title="The QSR Location Health Index",
        subtitle="A defensible, evidence-tested digital-health scorecard for quick-service "
                  "restaurant operators -- built to be challenged, not just believed.",
        stats=[
            ("19,154", "QSR locations scored"),
            ("13,719", "currently open"),
            ("0.83", "ROC-AUC, leakage-audited (not the inflated 0.97)"),
            ("4", "competing index designs compared"),
        ],
        footer="Prepared for VP Analytics leadership  -  LSE Data Analytics Career Accelerator  -  "
               "Source: Yelp Open Dataset, historical through 19 Jan 2022",
    ),
    dict(
        key="context",
        kind="questions",
        kicker="BUSINESS CONTEXT  -  01",
        title="A useful scorecard must answer four operational questions",
        list_items=[
            ("Which outlets are at risk?", "A portfolio-wide view of location health, identifying "
                                            "which outlets are stable, vulnerable, or require attention."),
            ("What is driving the risk?", "Pillar attribution and customer-voice evidence, not just "
                                           "a number."),
            ("How do they compare to peers?", "Health only means something in the context of "
                                               "nearby competition."),
            ("What should be prioritised first?", "Health and trajectory combined -- not just the "
                                                    "lowest-scoring location."),
        ],
        footer="Audience: VP Analytics leadership. Source: QSR_LHI_Technical_Report_Agency5_v5.pdf, Section 02 (The Business Problem and Assignment).",
    ),
    dict(
        key="process",
        kind="process4",
        kicker="PROJECT DEVELOPMENT PROCESS  -  02",
        title="A four-phase pipeline, each phase asserting its own evidence before the next begins",
        phases=[
            ("1", "Understand the data", ["Data QA", "Review extraction", "Deep EDA"]),
            ("2", "Build the evidence", ["Aspect sentiment", "Peer / CX scoring", "Trajectory"]),
            ("3", "Construct and validate", ["Leakage gate", "ML modelling", "4 LHI candidates", "Robustness grid"]),
            ("4", "Operationalise", ["Explainability", "Confidence / fallback", "Final export"]),
        ],
        body="Fail loudly, not silently -- a misleading 96.9%-accurate model was caught at the "
             "leakage gate (Slide 05) before it could shape the index.",
        footer="Source: QSR_LHI_Technical_Report_Agency5_v5.pdf, Section 03 (Analytical Design). Thirteen "
               "independently re-runnable stages, grouped here into four phases.",
    ),
    dict(
        key="eda",
        kind="eda_hero",
        kicker="EDA AND PORTFOLIO UNDERSTANDING  -  03",
        title="Nearly every location is benchmarked against a real, local peer set",
        images=["chart_pack/technical_report/fig_02_peer_group_size_final.png"],
        stats=[
            ("119", "median peer group size"),
            ("315", "locations with fewer than 10 peers"),
        ],
        body="A thin peer group means a noisier benchmark -- peer-tier quality feeds directly "
             "into each location's confidence score, so a weak comparison is disclosed, not hidden.",
        footer="Source: QSR_PEER_GROUPS.csv, analysis/output/. n = 19,154 businesses (all classified "
               "locations, open and closed).",
    ),
    dict(
        key="model_integrity",
        kind="hero_secondary",
        kicker="WHY MODELLING WAS NECESSARY  -  04",
        title="Leakage inflated model performance; the corrected model provides a "
              "more credible signal",
        hero_image="chart_pack/pptx/fig_p2_model_comparison_best_final.png",
        hero_stats=[("0.969", "naive"), ("0.832", "corrected")],
        secondary_image="chart_pack/pptx/fig_p3_shap_top_drivers_final.png",
        secondary_label="Supporting evidence -- what the corrected model actually finds",
        takeaway="Every number in this deck is checked against this standard -- evidence first, "
                 "nothing assumed correct because it was the obvious first guess.",
        footer="Source: QSR_MODEL_RESULTS.csv, QSR_ML_FEATURE_IMPORTANCE.csv, analysis/output/. "
               "n = 3,831 test-set holdout.",
    ),
    dict(
        key="cx",
        kind="chart",
        kicker="CUSTOMER-EXPERIENCE INSIGHTS  -  05",
        title="Order accuracy is the weakest aspect -- but not the riskiest one",
        images=["chart_pack/technical_report/fig_05_aspect_sentiment_risk_share_final.png"],
        body="Bars rank sentiment; diamonds mark which aspects actually predict High or Critical "
             "Risk -- the two do not point to the same aspect.",
        footer="Source: dashboard/data/meta.json (aspectSummary). n = 13,719 open locations.",
    ),
    dict(
        key="outlet_compare",
        kind="outlet_compare",
        kicker="MEET TWO REAL LOCATIONS  -  06",
        title="The same four pillars, two very different stories",
        cards=[
            dict(
                label="STRUGGLING",
                accent="C1652E",
                name="Bryn and Dane's",
                place="Horsham, PA  ·  17 local/state peers",
                lhi="36.6",
                risk_line="High Risk\nCritical priority",
                trend="Deteriorating -2.3  (1.6★ recent vs. 3.9★ prior)",
                peer="10.7th percentile vs. peers  ·  -0.62★ vs. peer median",
                pillars=[("Peer", 20), ("Engagement", 76), ("Momentum", 4), ("Cust. Exp.", 39)],
                note="Strong engagement (76) wasn't enough on its own -- peer standing and "
                     "momentum both collapsed.",
            ),
            dict(
                label="HEALTHY",
                accent="2E7D5B",
                name="In-N-Out Burger",
                place="Tucson, AZ  ·  173 local peers",
                lhi="85.3",
                risk_line="Healthy\nLow priority",
                trend="Improving +1.0  (4.75★ recent vs. 3.79★ prior)",
                peer="79.9th percentile vs. peers  ·  +1.21★ vs. peer median",
                pillars=[("Peer", 87), ("Engagement", 94), ("Momentum", 64), ("Cust. Exp.", 93)],
                note="Consistently strong across all four pillars -- healthy here means no weak "
                     "link, not one standout number.",
            ),
        ],
        body="Every one of the 19,154 scored locations gets a card like this -- not just a "
             "number, but the specific pillars and evidence behind it, so an operator knows "
             "exactly what to fix first.",
        footer="Source: QSR_FINAL_LHI_DATA.csv, analysis/output/. Two real, individually "
               "identifiable locations shown as a worked example of the scoring logic.",
    ),
    dict(
        key="weights",
        kind="weights",
        kicker="HOW THE WEIGHTS WERE CHOSEN  -  07",
        title="Every weight is a business judgement -- tested, not just assumed",
        pillars=[
            ("Peer Standing", "31.8%", "Health only means something next to comparable local "
                                        "competition, so this counts for the most."),
            ("Engagement", "29.2%", "Reviews, check-ins, and tips show a location people are "
                                     "actually visiting and talking about."),
            ("Momentum", "20.3%", "Direction of travel -- a good-looking score that is quietly "
                                   "getting worse is exactly what this is meant to catch."),
            ("Cust. Experience", "18.7%", "The specific, fixable drivers -- food, service, "
                                           "cleanliness -- weighted lowest because review-level "
                                           "signal is noisier."),
        ],
        body="These weights blend business judgement with statistical and model-based evidence "
             "-- none of it is precision science. The next slide shows the ranking barely moves "
             "even under five deliberately extreme alternative weightings.",
        footer="Source: QSR_LHI_Technical_Report_Agency5_v5.pdf, Section 06 (Building the LHI). "
               "LHI-3, the hybrid construction, is the version scored throughout this deck.",
    ),
    dict(
        key="lhi_construction",
        kind="chart",
        kicker="LHI CONSTRUCTION AND VALIDATION  -  08",
        title="Location rankings remain broadly stable across alternative LHI constructions",
        show_title=True,
        images=["chart_pack/technical_report/fig_09_sensitivity_dumbbell_final.png"],
        body="Across five deliberately extreme reweightings, agreement with LHI-3 -- the version "
             "actually scored throughout this deck -- never drops below 0.95.",
        footer="Source: QSR_LHI_SENSITIVITY.csv, analysis/output/. n = 19,154 classified businesses, "
               "scored under each weighting scenario, tested against LHI-3.",
    ),
    dict(
        key="prioritisation",
        kind="priority",
        kicker="OPERATIONAL PRIORITISATION  -  09",
        title="A declining Watch-range location can outrank an improving High-Risk one",
        logic=["Health band", "Trajectory", "Confidence"],
        logic_result="Intervention priority",
        images=["chart_pack/shared/fig_11_intervention_priority_quadrant_final.png"],
        body="Priority is an explicit lookup table across these three fields, not health plus a "
             "trend nudge added arithmetically -- confidence acts as a damper, so a low-evidence "
             "signal never drives urgent action alone.",
        footer="Source: QSR_DRIVERS.csv, analysis/output/. n = 13,719 open locations; 499 with "
               "statistically-evidenced trend adjustment.",
    ),
    dict(
        key="recommendations",
        kind="themes",
        kicker="RECOMMENDATIONS  -  10",
        title="Three moves before this framework drives automated action",
        themes=[
            ("Strengthen the evidence", [
                "Get a real outcome variable -- dated closures, sales trend, or pilot audit scores.",
                "Re-run sentiment validation against a multi-annotator gold set.",
            ]),
            ("Govern the framework", [
                "Ship the priority lookup table as a governed artifact operators can read.",
                "Version every threshold-based shortlist -- 38.4% of locations move rank under "
                "reasonable alternative weights.",
            ]),
            ("Deploy responsibly", [
                "Pilot with analyst-in-the-loop review before wiring the priority queue into an "
                "automated workflow.",
            ]),
        ],
        footer="Source: QSR_LHI_Technical_Report_Agency5_v5.pdf, Section 12 (Recommendations).",
    ),
    dict(
        key="limitations",
        kind="themes",
        kicker="LIMITATIONS  -  11",
        title="What this framework can't yet claim",
        themes=[
            ("No ground truth yet", [
                "No sales figures, confirmed closures, or audit outcomes exist in this dataset "
                "to check the score against.",
                "The data is a historical snapshot through January 2022, not a live feed of "
                "current conditions.",
            ]),
            ("Simplifications we made", [
                "Review sentiment is read by a transparent, rule-based system, not a "
                "deep-learning model -- it can miss sarcasm.",
                "Which businesses count as \"QSR\" was set by an automated rule, not manually "
                "checked one by one.",
            ]),
            ("Not yet in scope", [
                "No roll-up across multi-location franchise ownership -- every location is "
                "scored on its own.",
                "A single location's exact rank can shift under different reasonable weightings; "
                "the overall picture does not.",
            ]),
        ],
        footer="Source: QSR_LHI_Technical_Report_Agency5_v5.pdf, Section 11 (Limitations and Assumptions).",
    ),
    dict(
        key="conclusion",
        kind="conclusion3",
        kicker="CONCLUSION  -  12",
        title="268 locations look fine today -- and are already trending down",
        images=["chart_pack/pptx/fig_p7_early_warning_final.png"],
        takeaways=[
            "One defensible score for 19,154 locations, tested against three alternatives.",
            "Direction, evidence strength, and priority -- what a score alone cannot show.",
            "For VP Analytics: a ranked, evidence-backed shortlist operators can act on today.",
            "The practical value is what this framework refuses to claim, as much as what it finds.",
        ],
        footer="Source: QSR_DRIVERS.csv, QSR_FINAL_LHI_DATA.csv, dashboard/data/meta.json "
               "(trajectoryCounts). n = 347 open, statistically-evidenced deteriorating locations.",
    ),
    dict(
        key="thankyou",
        kind="closing",
        title="Thank you",
        subtitle="Questions and discussion",
        footer="Agency 5  -  LSE Data Analytics Career Accelerator  -  QSR Location Health Index",
    ),
]
