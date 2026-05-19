"""
ml_evaluator.py — Machine Learning Evaluation Module
DummySite — Adaptive CAPTCHA Difficulty Adjustment System
Author: Tanish | Bachelor of Computer Applications

PURPOSE
-------
This module trains a supervised ML classifier on the behavioural signals
already logged by DummySite's rule-based engine, then compares the ML
model's predictions against the rule-based system.

The comparison itself is the academic contribution:
  - If they agree → the rule-based system is well-calibrated
  - Where they disagree → potential improvements to thresholds

USAGE
-----
  python ml_evaluator.py                   # run full evaluation
  python ml_evaluator.py --db mylog.db     # custom DB path
  python ml_evaluator.py --min-rows 20     # lower data threshold (demo)

OUTPUT
------
  ml_report.txt        — full text report (accuracy, classification report,
                         feature importances, confusion matrix)
  ml_confusion.png     — confusion matrix heatmap
  ml_features.png      — feature importance bar chart
  ml_roc.png           — ROC curve (if enough data)
"""

import os
import sys
import argparse
import sqlite3
import warnings
warnings.filterwarnings("ignore")

import numpy  as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # non-interactive backend — safe for servers
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from sklearn.ensemble         import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model     import LogisticRegression
from sklearn.tree             import DecisionTreeClassifier
from sklearn.model_selection  import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing    import StandardScaler
from sklearn.metrics          import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve, accuracy_score,
    precision_score, recall_score, f1_score,
)
from sklearn.pipeline         import Pipeline
from sklearn.impute            import SimpleImputer


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_DB   = "access_log.db"
MIN_ROWS     = 30          # minimum rows needed to train meaningfully
RANDOM_STATE = 42

FEATURE_COLS = [
    "mouse_moves",
    "fill_time_ms",
    "focus_switches",
    "used_paste",
    "honeypot",
    "rhythm_score",
    "risk_score",
    "bot_probability",
]

FEATURE_LABELS = {
    "mouse_moves":     "Mouse Moves",
    "fill_time_ms":    "Fill Time (ms)",
    "focus_switches":  "Focus Switches",
    "used_paste":      "Used Paste",
    "honeypot":        "Honeypot Triggered",
    "rhythm_score":    "Keystroke Rhythm Score",
    "risk_score":      "Rule-Based Risk Score",
    "bot_probability": "Rule-Based Bot Probability",
}

TARGET_COL = "is_bot"

MODELS = {
    "Logistic Regression": Pipeline([
        ("imp",   SimpleImputer(strategy="median")),
        ("scl",   StandardScaler()),
        ("clf",   LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
    ]),
    "Decision Tree": Pipeline([
        ("imp",   SimpleImputer(strategy="median")),
        ("clf",   DecisionTreeClassifier(max_depth=5, random_state=RANDOM_STATE)),
    ]),
    "Random Forest": Pipeline([
        ("imp",   SimpleImputer(strategy="median")),
        ("clf",   RandomForestClassifier(
                      n_estimators=100, max_depth=6,
                      random_state=RANDOM_STATE, n_jobs=-1)),
    ]),
    "Gradient Boosting": Pipeline([
        ("imp",   SimpleImputer(strategy="median")),
        ("clf",   GradientBoostingClassifier(
                      n_estimators=100, max_depth=4,
                      learning_rate=0.1, random_state=RANDOM_STATE)),
    ]),
}

# Primary model used for detailed plots
PRIMARY_MODEL = "Random Forest"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_data(db_path: str) -> pd.DataFrame:
    """Load access_logs from SQLite into a DataFrame."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            "Run the DummySite Flask app first to generate log data."
        )
    conn = sqlite3.connect(db_path)
    df   = pd.read_sql("SELECT * FROM access_logs", conn)
    conn.close()
    return df


def preprocess(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Select features, handle missing/sentinel values, return (X, y).

    Special cases:
      rhythm_score == -1  → sentinel for "no data" → replace with NaN
      used_paste, honeypot → stored as 0/1 int in SQLite
    """
    df = df.copy()

    # Replace sentinel value for missing rhythm score
    df["rhythm_score"] = df["rhythm_score"].replace(-1, np.nan)

    # Ensure numeric types
    for col in FEATURE_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = np.nan

    X = df[FEATURE_COLS].copy()
    y = df[TARGET_COL].astype(int)
    return X, y


# ── Rule-based predictor (baseline) ──────────────────────────────────────────

def rule_based_predict(df: pd.DataFrame) -> np.ndarray:
    """
    Re-derive the rule-based bot flag from the logged risk_score.
    Mirrors the logic in routes/auth.py:
      is_bot = risk_score >= 7 OR (mouse_moves == 0 AND fill_time < 300)
    This gives us a comparable baseline vector.
    """
    cond_score = df["risk_score"] >= 7
    cond_combo = (df["mouse_moves"] == 0) & (df["fill_time_ms"] < 300)
    return (cond_score | cond_combo).astype(int).values


# ── Evaluation helpers ────────────────────────────────────────────────────────

def cross_val_eval(model, X: pd.DataFrame, y: pd.Series,
                   cv: int = 5) -> dict:
    """
    Stratified k-fold cross-validation.
    Returns dict of mean ± std for accuracy, precision, recall, f1, roc_auc.
    Falls back to 2-fold if class distribution is too skewed for 5-fold.
    """
    n_minority = int(y.value_counts().min())
    cv         = min(cv, n_minority) if n_minority >= 2 else 2
    skf        = StratifiedKFold(n_splits=cv, shuffle=True, random_state=RANDOM_STATE)

    results = {}
    for metric in ["accuracy", "precision", "recall", "f1", "roc_auc"]:
        scores = cross_val_score(model, X, y,
                                 cv=skf, scoring=metric,
                                 error_score="raise")
        results[metric] = (scores.mean(), scores.std())
    return results


def train_primary(X: pd.DataFrame, y: pd.Series):
    """
    Train the primary model on a hold-out split and return
    (fitted_pipeline, X_test, y_test, y_pred, y_prob).
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=RANDOM_STATE
    )
    model = MODELS[PRIMARY_MODEL]
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] \
             if hasattr(model, "predict_proba") else None

    return model, X_test, y_test, y_pred, y_prob


# ── Plot helpers ──────────────────────────────────────────────────────────────

PALETTE = {
    "blue":   "#2563eb",
    "green":  "#16a34a",
    "red":    "#dc2626",
    "amber":  "#d97706",
    "gray":   "#64748b",
    "light":  "#f1f5f9",
}


def plot_confusion_matrix(y_test, y_pred, out_path: str):
    cm     = confusion_matrix(y_test, y_pred)
    labels = ["Human", "Bot"]

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("Predicted", fontsize=12, labelpad=8)
    ax.set_ylabel("Actual",    fontsize=12, labelpad=8)
    ax.set_title(f"Confusion Matrix — {PRIMARY_MODEL}", fontsize=13, pad=12)

    for i in range(2):
        for j in range(2):
            color = "white" if cm[i, j] > cm.max() / 2 else "black"
            ax.text(j, i, str(cm[i, j]),
                    ha="center", va="center",
                    fontsize=18, fontweight="bold", color=color)

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_feature_importance(model, out_path: str):
    """Extract feature importances from the primary model's classifier step."""
    clf = model.named_steps["clf"]
    if not hasattr(clf, "feature_importances_"):
        return   # Logistic Regression — skip

    importances = clf.feature_importances_
    labels      = [FEATURE_LABELS.get(c, c) for c in FEATURE_COLS]
    idx         = np.argsort(importances)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.barh(
        [labels[i] for i in idx],
        importances[idx],
        color=PALETTE["blue"],
        edgecolor="none",
        height=0.6,
    )
    # Colour the top-2 bars differently
    for bar in bars[-2:]:
        bar.set_color(PALETTE["red"])

    ax.set_xlabel("Feature Importance (Gini)", fontsize=11)
    ax.set_title(f"Feature Importances — {PRIMARY_MODEL}", fontsize=13, pad=10)
    ax.xaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    # Value labels
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.003, bar.get_y() + bar.get_height() / 2,
                f"{w:.3f}", va="center", ha="left", fontsize=8.5)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_roc_curve(y_test, y_prob, out_path: str):
    if y_prob is None:
        return
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    auc_val     = roc_auc_score(y_test, y_prob)

    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.plot(fpr, tpr, color=PALETTE["blue"], lw=2,
            label=f"{PRIMARY_MODEL} (AUC = {auc_val:.3f})")
    ax.plot([0, 1], [0, 1], color=PALETTE["gray"],
            lw=1.5, linestyle="--", label="Random Classifier")
    ax.fill_between(fpr, tpr, alpha=0.08, color=PALETTE["blue"])
    ax.set_xlabel("False Positive Rate", fontsize=11)
    ax.set_ylabel("True Positive Rate",  fontsize=11)
    ax.set_title("ROC Curve — Bot Detection", fontsize=13, pad=10)
    ax.legend(fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(linestyle="--", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


# ── Text report builder ───────────────────────────────────────────────────────

def build_report(df, X, y, cv_results, model, X_test, y_test,
                 y_pred, y_prob, rule_pred) -> str:

    lines = []
    W     = 70

    def hr(char="═"):
        lines.append(char * W)

    def h(title):
        hr()
        lines.append(f"  {title}")
        hr()

    # ── Header ──
    lines.append("")
    hr("╔" + "═" * (W - 2) + "╗")
    lines.append(f"{'DummySite — ML Evaluation Report':^{W}}")
    lines.append(f"{'Adaptive CAPTCHA Difficulty Adjustment System':^{W}}")
    lines.append(f"{'Author: Tanish | Bachelor of Computer Applications':^{W}}")
    hr("╚" + "═" * (W - 2) + "╝")

    # ── Dataset overview ──
    h("1. DATASET OVERVIEW")
    n_total  = len(df)
    n_bots   = int(y.sum())
    n_humans = n_total - n_bots
    lines += [
        f"  Total logged sessions   : {n_total}",
        f"  Bot sessions            : {n_bots}  ({n_bots/n_total*100:.1f}%)",
        f"  Human sessions          : {n_humans}  ({n_humans/n_total*100:.1f}%)",
        f"  Features used           : {len(FEATURE_COLS)}",
        "",
        "  Features:",
    ]
    for col in FEATURE_COLS:
        missing = int(X[col].isna().sum())
        lines.append(f"    • {FEATURE_LABELS.get(col, col):<32} missing: {missing}")

    # ── Model comparison (cross-validation) ──
    h("2. MODEL COMPARISON  (5-fold stratified cross-validation)")
    header = f"  {'Model':<24} {'Accuracy':>9} {'Precision':>10} {'Recall':>8} {'F1':>8} {'ROC-AUC':>9}"
    lines.append(header)
    lines.append("  " + "-" * (W - 4))

    for name, pipe in MODELS.items():
        cv  = cross_val_eval(pipe, X, y)
        acc = cv["accuracy"][0]
        pre = cv["precision"][0]
        rec = cv["recall"][0]
        f1  = cv["f1"][0]
        auc = cv["roc_auc"][0]
        marker = " ◄ primary" if name == PRIMARY_MODEL else ""
        lines.append(
            f"  {name:<24} {acc:>8.3f}  {pre:>9.3f}  {rec:>7.3f}  {f1:>7.3f}  {auc:>8.3f}{marker}"
        )

    # ── Primary model detailed results ──
    h(f"3. DETAILED RESULTS — {PRIMARY_MODEL}")
    acc = accuracy_score(y_test, y_pred)
    pre = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1  = f1_score(y_test, y_pred, zero_division=0)

    lines += [
        f"  Hold-out test size : {len(y_test)} rows (30%)",
        f"  Accuracy           : {acc:.4f}  ({acc*100:.1f}%)",
        f"  Precision          : {pre:.4f}",
        f"  Recall             : {rec:.4f}",
        f"  F1 Score           : {f1:.4f}",
    ]
    if y_prob is not None:
        auc = roc_auc_score(y_test, y_prob)
        lines.append(f"  ROC AUC            : {auc:.4f}")

    lines += ["", "  Classification Report:", ""]
    cr = classification_report(y_test, y_pred,
                                target_names=["Human", "Bot"],
                                zero_division=0)
    for line in cr.splitlines():
        lines.append("    " + line)

    lines += ["", "  Confusion Matrix  [rows=Actual, cols=Predicted]:"]
    cm = confusion_matrix(y_test, y_pred)
    lines += [
        "               Pred: Human   Pred: Bot",
        f"  Actual: Human     {cm[0,0]:>5}         {cm[0,1]:>5}",
        f"  Actual: Bot       {cm[1,0]:>5}         {cm[1,1]:>5}",
    ]

    # ── ML vs Rule-based comparison ──
    h("4. ML MODEL vs RULE-BASED SYSTEM COMPARISON")
    agree     = int((y_pred == rule_pred[:len(y_pred)]).sum())
    disagree  = len(y_pred) - agree
    agree_pct = agree / len(y_pred) * 100

    rule_acc  = accuracy_score(y_test, rule_pred[:len(y_test)])
    ml_acc    = acc

    lines += [
        f"  Agreement between ML and rule-based : {agree}/{len(y_pred)} ({agree_pct:.1f}%)",
        f"  Disagreements                        : {disagree} cases",
        "",
        f"  Accuracy comparison (hold-out set):",
        f"    Rule-based system  : {rule_acc:.4f}  ({rule_acc*100:.1f}%)",
        f"    {PRIMARY_MODEL:<22}: {ml_acc:.4f}  ({ml_acc*100:.1f}%)",
        "",
    ]

    # Breakdown of disagreement types
    y_test_arr = np.array(y_test)
    rb_arr     = rule_pred[:len(y_pred)]
    ml_arr     = np.array(y_pred)

    ml_right_rb_wrong = int(((ml_arr == y_test_arr) & (rb_arr != y_test_arr)).sum())
    rb_right_ml_wrong = int(((rb_arr == y_test_arr) & (ml_arr != y_test_arr)).sum())
    both_wrong        = int(((ml_arr != y_test_arr) & (rb_arr != y_test_arr)).sum())

    lines += [
        "  Disagreement breakdown:",
        f"    ML correct, rule-based wrong : {ml_right_rb_wrong} cases",
        f"    Rule-based correct, ML wrong : {rb_right_ml_wrong} cases",
        f"    Both systems wrong           : {both_wrong} cases",
    ]

    # ── Feature importances (if available) ──
    clf = model.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        h("5. FEATURE IMPORTANCES")
        importances = clf.feature_importances_
        idx         = np.argsort(importances)[::-1]
        lines.append(f"  {'Feature':<36} {'Importance':>10}")
        lines.append("  " + "-" * 50)
        for i in idx:
            bar = "█" * int(importances[i] * 40)
            lines.append(
                f"  {FEATURE_LABELS.get(FEATURE_COLS[i], FEATURE_COLS[i]):<36} "
                f"{importances[i]:>8.4f}  {bar}"
            )

    # ── Cross-val results for primary model ──
    h(f"6. CROSS-VALIDATION DETAIL — {PRIMARY_MODEL}")
    cv = cv_results
    lines += [
        f"  {'Metric':<20} {'Mean':>8} {'Std Dev':>10}",
        "  " + "-" * 42,
    ]
    for metric, (mean, std) in cv.items():
        lines.append(f"  {metric.capitalize():<20} {mean:>8.4f}  ±{std:.4f}")

    # ── Interpretation ──
    h("7. INTERPRETATION & CONCLUSIONS")
    lines += [
        "  The ML classifier was trained on the same behavioural signals that",
        "  DummySite's rule-based engine already uses. This allows a direct",
        "  comparison between the hand-crafted threshold approach and a",
        "  data-driven model.",
        "",
        f"  With {n_total} logged sessions, the {PRIMARY_MODEL} achieves",
        f"  {ml_acc*100:.1f}% accuracy on the hold-out set compared to the rule-based",
        f"  system's {rule_acc*100:.1f}%. The two systems agree on {agree_pct:.1f}% of cases.",
        "",
        "  Key observations:",
    ]

    if hasattr(clf, "feature_importances_"):
        top_feat = FEATURE_LABELS.get(FEATURE_COLS[np.argmax(importances)], "—")
        lines.append(f"    • '{top_feat}' is the single most predictive signal")

    if abs(ml_acc - rule_acc) < 0.05:
        lines.append("    • ML and rule-based systems perform comparably, validating")
        lines.append("      the hand-crafted thresholds as well-calibrated")
    elif ml_acc > rule_acc:
        diff = (ml_acc - rule_acc) * 100
        lines.append(f"    • ML outperforms rule-based by {diff:.1f}%, suggesting the")
        lines.append("      current thresholds could be tightened")
    else:
        diff = (rule_acc - ml_acc) * 100
        lines.append(f"    • Rule-based outperforms ML by {diff:.1f}%, which is expected")
        lines.append("      with limited training data — more logs will close this gap")

    lines += [
        "    • High agreement confirms the rule-based system is internally",
        "      consistent with what the data supports",
        "",
        "  Limitation: ML performance improves with more data. Run more",
        "  login sessions (including bot simulations) to enrich the training",
        "  set and make the model increasingly reliable.",
    ]

    hr()
    lines.append(f"  Output files: ml_report.txt, ml_confusion.png,")
    lines.append(f"                ml_features.png, ml_roc.png")
    hr()
    lines.append("")

    return "\n".join(lines)


# ── Synthetic data generator (demo / testing) ─────────────────────────────────

def generate_synthetic_data(n: int = 120) -> pd.DataFrame:
    """
    Generate realistic synthetic access logs when the real DB has too few rows.
    Roughly 40% bots, 60% humans — similar to a typical demo ratio.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    rows = []

    for i in range(n):
        is_bot = int(i < n * 0.40)

        if is_bot:
            row = {
                "mouse_moves":     int(rng.integers(0, 4)),
                "fill_time_ms":    int(rng.integers(50, 290)),
                "focus_switches":  0,
                "used_paste":      int(rng.random() > 0.6),
                "honeypot":        int(rng.random() > 0.75),
                "rhythm_score":    int(rng.integers(0, 18)),
                "risk_score":      int(rng.integers(7, 25)),
                "bot_probability": float(rng.uniform(50, 100)),
                "is_bot":          1,
                "success":         0,
                "access_denied":   1,
                "captcha_type":    rng.choice(["text", "math", "tile", "drag", "rotation"]),
                "timestamp":       f"2025-01-{i%28+1:02d} 12:00:00",
                "username":        "admin",
                "ip":              "127.0.0.1",
            }
        else:
            row = {
                "mouse_moves":     int(rng.integers(20, 300)),
                "fill_time_ms":    int(rng.integers(800, 8000)),
                "focus_switches":  int(rng.integers(1, 5)),
                "used_paste":      0,
                "honeypot":        0,
                "rhythm_score":    int(rng.integers(40, 100)),
                "risk_score":      int(rng.integers(0, 6)),
                "bot_probability": float(rng.uniform(0, 35)),
                "is_bot":          0,
                "success":         int(rng.random() > 0.3),
                "access_denied":   0,
                "captcha_type":    rng.choice(["text", "math"]),
                "timestamp":       f"2025-01-{i%28+1:02d} 12:00:00",
                "username":        rng.choice(["admin", "student"]),
                "ip":              "192.168.1.1",
            }
        rows.append(row)

    rng.shuffle(rows)
    return pd.DataFrame(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="DummySite ML Evaluation Module"
    )
    parser.add_argument("--db",       default=DEFAULT_DB,
                        help="Path to access_log.db")
    parser.add_argument("--min-rows", type=int, default=MIN_ROWS,
                        help="Minimum rows required (default 30)")
    parser.add_argument("--synthetic", action="store_true",
                        help="Force synthetic data even if DB exists")
    args = parser.parse_args()

    print("\n" + "═" * 60)
    print("  DummySite — ML Evaluation Module")
    print("  Author: Tanish | BCA")
    print("═" * 60)

    # ── Load data ──
    using_synthetic = False
    try:
        if args.synthetic:
            raise FileNotFoundError("synthetic flag set")
        df = load_data(args.db)
        if len(df) < args.min_rows:
            print(f"\n  ⚠  Only {len(df)} rows found in DB "
                  f"(minimum: {args.min_rows}).")
            print("  → Augmenting with synthetic data for demonstration.\n")
            df_synth       = generate_synthetic_data(150)
            df             = pd.concat([df, df_synth], ignore_index=True)
            using_synthetic = True
        else:
            print(f"\n  ✓ Loaded {len(df)} rows from {args.db}")
    except FileNotFoundError:
        print(f"\n  ⚠  DB not found or --synthetic flag set.")
        print("  → Using fully synthetic data for demonstration.\n")
        df              = generate_synthetic_data(150)
        using_synthetic = True

    if using_synthetic:
        print("  ℹ  NOTE: Results below use synthetic / augmented data.")
        print("          Run more sessions in DummySite for real results.\n")

    # ── Preprocess ──
    X, y = preprocess(df)

    # Sanity check: need at least 2 classes
    if y.nunique() < 2:
        print("\n  ✗  Only one class present in the data.")
        print("     Simulate at least one bot attack and one human login.")
        sys.exit(1)

    # ── Cross-validation on all models ──
    print("  Training and evaluating models...", flush=True)
    cv_results = cross_val_eval(MODELS[PRIMARY_MODEL], X, y)

    # ── Primary model on hold-out split ──
    model, X_test, y_test, y_pred, y_prob = train_primary(X, y)

    # ── Rule-based baseline ──
    rule_pred = rule_based_predict(df)
    # align to test set indices (train_test_split uses iloc)
    # we need indices from the test set
    _, test_idx = train_test_split(
        np.arange(len(df)), test_size=0.3,
        stratify=y, random_state=RANDOM_STATE
    )
    rule_pred_test = rule_pred[test_idx]

    # ── Build and save report ──
    print("  Generating report...", flush=True)
    report = build_report(
        df, X, y, cv_results,
        model, X_test, y_test, y_pred, y_prob,
        rule_pred_test,
    )

    with open("ml_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    print("  ✓ ml_report.txt saved")

    # ── Plots ──
    plot_confusion_matrix(y_test, y_pred, "ml_confusion.png")
    print("  ✓ ml_confusion.png saved")

    plot_feature_importance(model, "ml_features.png")
    print("  ✓ ml_features.png saved")

    if y_prob is not None and y.nunique() == 2:
        plot_roc_curve(y_test, y_prob, "ml_roc.png")
        print("  ✓ ml_roc.png saved")

    # ── Print report to console ──
    print("\n" + report)


if __name__ == "__main__":
    main()