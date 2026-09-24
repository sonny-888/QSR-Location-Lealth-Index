"""Stage 8 - ML modelling: importance evidence, not LHI weights.

Trains the same model family on two feature sets -- LEAKY (every numeric
feature, including the time-dependent/circular ones stage 7 flags) and SAFE
(stage 7's leakage-audited feature set) -- so the leakage effect is a
documented before/after comparison, not an assertion. The SAFE-set result is
the one used as importance evidence for stage 9; SHAP/permutation importance
here answers "which variables predict IS_OPEN," which is a different
question from "how much should this variable count toward location health"
(that synthesis happens explicitly in stage 9, not here).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (roc_auc_score, average_precision_score, precision_score, recall_score,
                              f1_score, accuracy_score, confusion_matrix, brier_score_loss)
from sklearn.inspection import permutation_importance

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import ROOT, OUTPUT_DIR, require, log, extract_positive_class_shap

warnings.filterwarnings("ignore")
RANDOM_STATE = 42

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False
import shap


def build_models(scale_pos_weight: float):
    models = {
        "Baseline (majority class)": DummyClassifier(strategy="most_frequent"),
        "Logistic Regression (L2)": LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0),
        "Logistic Regression (L1)": LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0,
                                                         penalty="l1", solver="liblinear"),
        "Decision Tree": DecisionTreeClassifier(max_depth=6, min_samples_leaf=30, class_weight="balanced",
                                                  random_state=RANDOM_STATE),
        "Random Forest": RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=10,
                                                  class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                                                           random_state=RANDOM_STATE),
    }
    if HAS_XGB:
        models["XGBoost"] = xgb.XGBClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05, scale_pos_weight=scale_pos_weight,
            eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=-1,
        )
    if HAS_LGBM:
        models["LightGBM"] = lgb.LGBMClassifier(
            n_estimators=300, max_depth=4, learning_rate=0.05, class_weight="balanced",
            random_state=RANDOM_STATE, n_jobs=-1, verbosity=-1,
        )
    return models


NEEDS_SCALING = {"Logistic Regression (L2)", "Logistic Regression (L1)"}


def evaluate(model, name, X_train, X_test, y_train, y_test, needs_scaling: bool):
    steps = [("impute", SimpleImputer(strategy="median"))]
    if needs_scaling:
        steps.append(("scale", StandardScaler()))
    steps.append(("model", model))
    pipe = Pipeline(steps)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    cv_auc = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="roc_auc", n_jobs=-1)

    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = pipe.predict(X_test)

    tn, fp, fn, tp = confusion_matrix(y_test, pred).ravel()
    return {
        "MODEL": name,
        "CV_ROC_AUC_MEAN": round(cv_auc.mean(), 4),
        "CV_ROC_AUC_STD": round(cv_auc.std(), 4),
        "TEST_ROC_AUC": round(roc_auc_score(y_test, proba), 4),
        "TEST_PR_AUC": round(average_precision_score(y_test, proba), 4),
        "TEST_ACCURACY": round(accuracy_score(y_test, pred), 4),
        "TEST_PRECISION": round(precision_score(y_test, pred), 4),
        "TEST_RECALL": round(recall_score(y_test, pred), 4),
        "TEST_F1": round(f1_score(y_test, pred), 4),
        "TEST_BRIER_SCORE": round(brier_score_loss(y_test, proba), 4),
        "TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp),
    }, pipe


def run_feature_set(biz: pd.DataFrame, features: list[str], label: str):
    X = biz[features]
    y = biz["IS_OPEN"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE)
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    results = []
    fitted = {}
    for name, model in build_models(scale_pos_weight).items():
        needs_scaling = name in NEEDS_SCALING
        try:
            metrics, pipe = evaluate(model, name, X_train, X_test, y_train, y_test, needs_scaling)
        except Exception as e:
            log(f"  [{label}] {name} failed: {e}")
            continue
        metrics["FEATURE_SET"] = label
        results.append(metrics)
        fitted[name] = pipe
        log(f"  [{label}] {name}: ROC-AUC={metrics['TEST_ROC_AUC']}, Recall={metrics['TEST_RECALL']}")

    return pd.DataFrame(results), fitted, (X_train, X_test, y_train, y_test)


def feature_importance_and_shap(fitted_models: dict, X_train, X_test, y_test, features: list[str]):
    best_name = "Random Forest" if "Random Forest" in fitted_models else list(fitted_models)[-1]
    pipe = fitted_models[best_name]
    model = pipe.named_steps["model"]
    imputer = pipe.named_steps["impute"]
    X_test_imputed = pd.DataFrame(imputer.transform(X_test), columns=features, index=X_test.index)

    rows = []
    if hasattr(model, "feature_importances_"):
        for f, imp in zip(features, model.feature_importances_):
            rows.append({"FEATURE": f, "NATIVE_IMPORTANCE": imp})
    imp_df = pd.DataFrame(rows) if rows else pd.DataFrame({"FEATURE": features})

    perm = permutation_importance(pipe, X_test, y_test, n_repeats=8, random_state=RANDOM_STATE, n_jobs=-1,
                                   scoring="roc_auc")
    perm_df = pd.DataFrame({"FEATURE": features, "PERMUTATION_IMPORTANCE_MEAN": perm.importances_mean,
                             "PERMUTATION_IMPORTANCE_STD": perm.importances_std})
    imp_df = imp_df.merge(perm_df, on="FEATURE", how="outer")

    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test_imputed.sample(min(2000, len(X_test_imputed)), random_state=RANDOM_STATE))
        sv = extract_positive_class_shap(shap_values)
        mean_abs_shap = np.abs(sv).mean(axis=0)
        shap_df = pd.DataFrame({"FEATURE": features, "MEAN_ABS_SHAP": mean_abs_shap})
        imp_df = imp_df.merge(shap_df, on="FEATURE", how="outer")
    except Exception as e:
        log(f"SHAP computation skipped: {e}")

    imp_df = imp_df.sort_values("PERMUTATION_IMPORTANCE_MEAN", ascending=False)
    imp_df.to_csv(OUTPUT_DIR / "QSR_ML_FEATURE_IMPORTANCE.csv", index=False)
    log(f"Feature importance (from {best_name}) written to QSR_ML_FEATURE_IMPORTANCE.csv")
    return best_name, imp_df


def main():
    biz = pd.read_csv(ROOT / "QSR_BUSINESS_ANALYSIS_READY.csv", low_memory=False)
    lineage = pd.read_csv(OUTPUT_DIR / "QSR_FEATURE_LINEAGE.csv")
    require(len(lineage) > 0, "Run stage 7 first (feature lineage/leakage audit)")

    safe_features = lineage.loc[lineage["FINAL_SAFE_FOR_TARGET"], "FEATURE"].tolist()
    leaky_features = lineage["FEATURE"].tolist()

    log(f"LEAKY feature set: {len(leaky_features)} features (includes recency/momentum)")
    log(f"SAFE feature set: {len(safe_features)} features (leakage-audited)")

    leaky_results, _, _ = run_feature_set(biz, leaky_features, "LEAKY (naive full feature set)")
    safe_results, safe_fitted, (X_train, X_test, y_train, y_test) = run_feature_set(biz, safe_features, "SAFE (leakage-audited)")

    all_results = pd.concat([leaky_results, safe_results], ignore_index=True)
    all_results.to_csv(OUTPUT_DIR / "QSR_MODEL_RESULTS.csv", index=False)

    leaky_best_auc = leaky_results["TEST_ROC_AUC"].max()
    safe_best_auc = safe_results["TEST_ROC_AUC"].max()
    log(f"Best ROC-AUC: LEAKY={leaky_best_auc:.3f} vs SAFE={safe_best_auc:.3f} "
        f"(drop of {leaky_best_auc - safe_best_auc:.3f})")

    best_name, imp_df = feature_importance_and_shap(safe_fitted, X_train, X_test, y_test, safe_features)

    summary = pd.DataFrame([{
        "LEAKY_BEST_MODEL_AUC": leaky_best_auc, "SAFE_BEST_MODEL_AUC": safe_best_auc,
        "AUC_DROP": leaky_best_auc - safe_best_auc, "SELECTED_MODEL_FOR_SHAP": best_name,
        "NOTE": "SAFE-set performance is assessed on its own terms, not required to be low -- "
                "if it genuinely predicts IS_OPEN without leaky features, that is a real finding.",
    }])
    summary.to_csv(OUTPUT_DIR / "QSR_LEAKAGE_MODEL_COMPARISON.csv", index=False)

    log("Stage 8 complete.")


if __name__ == "__main__":
    main()
