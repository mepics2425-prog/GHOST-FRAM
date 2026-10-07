from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from sklearn.preprocessing import RobustScaler


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "account_features_v1.csv"
OUT_DIR = PROJECT_ROOT / "data" / "analysis"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

GENERAL_ANOMALY_TYPES = {"bot", "farm", "mule", "hub"}
ORGANIZED_ABUSE_TYPES = {"farm", "mule", "hub"}
LEGIT_TYPES = {"normal", "hardcore", "guild"}


def load_features() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"\n입력 파일을 찾을 수 없습니다:\n{INPUT_PATH}\n"
            "먼저 src/inspect_logs.py를 실행해 주세요.\n"
        )

    df = pd.read_csv(INPUT_PATH)

    if "user_id" not in df.columns:
        raise ValueError("account_features_v1.csv에 user_id 컬럼이 없습니다.")

    # 시스템 엔티티는 플레이어 계정이 아니므로 모델 대상에서 제외
    df = df[~df["user_id"].astype(str).str.startswith("SYSTEM_")].copy()

    return df


def choose_numeric_features(df: pd.DataFrame) -> list[str]:
    exclude = {
        "ground_truth_type",
        "device_group",
        "ip_group",
        "user_id",
        "active_first",
        "active_last",
        "first_login",
        "last_login",
        "is_organized_abuse",
        "is_general_anomaly",
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [c for c in numeric_cols if c not in exclude]

    # 값이 전부 같은 컬럼은 정보가 없으므로 제외
    feature_cols = [
        c for c in feature_cols
        if df[c].nunique(dropna=True) > 1
    ]

    return feature_cols


def normalize_to_100(values: pd.Series) -> pd.Series:
    v = pd.to_numeric(values, errors="coerce").fillna(0.0)
    lo, hi = v.min(), v.max()
    if hi == lo:
        return pd.Series(0.0, index=v.index)
    return (v - lo) / (hi - lo) * 100.0


def evaluate_top_k(
    df: pd.DataFrame,
    benchmark_name: str,
    positive_types: set[str],
    negative_types: set[str],
) -> dict:
    """
    Ground Truth는 평가에만 사용한다.
    모델이 이상점수만 산출한 뒤, 평가셋의 실제 positive 수와 같은 K를 사용해
    Precision@K / Recall@K / F1@K를 계산한다.
    """
    labeled = df[
        df["ground_truth_type"].isin(positive_types | negative_types)
    ].copy()

    labeled["y_true"] = (
        labeled["ground_truth_type"].isin(positive_types).astype(int)
    )

    k = int(labeled["y_true"].sum())
    labeled = labeled.sort_values("baseline_risk_score", ascending=False)
    labeled["y_pred_topk"] = 0

    if k > 0:
        labeled.iloc[:k, labeled.columns.get_loc("y_pred_topk")] = 1

    precision = precision_score(
        labeled["y_true"], labeled["y_pred_topk"], zero_division=0
    )
    recall = recall_score(
        labeled["y_true"], labeled["y_pred_topk"], zero_division=0
    )
    f1 = f1_score(
        labeled["y_true"], labeled["y_pred_topk"], zero_division=0
    )

    tn, fp, fn, tp = confusion_matrix(
        labeled["y_true"],
        labeled["y_pred_topk"],
        labels=[0, 1],
    ).ravel()

    return {
        "benchmark": benchmark_name,
        "positive_types": ",".join(sorted(positive_types)),
        "negative_types": ",".join(sorted(negative_types)),
        "eval_accounts": len(labeled),
        "positive_accounts": k,
        "top_k": k,
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f1_at_k": f1,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def false_positive_table(
    df: pd.DataFrame,
    positive_types: set[str],
    negative_types: set[str],
) -> pd.DataFrame:
    labeled = df[
        df["ground_truth_type"].isin(positive_types | negative_types)
    ].copy()

    k = int(labeled["ground_truth_type"].isin(positive_types).sum())
    ranked = labeled.sort_values("baseline_risk_score", ascending=False).copy()
    ranked["predicted_positive"] = False
    ranked.iloc[:k, ranked.columns.get_loc("predicted_positive")] = True

    fp = ranked[
        ranked["predicted_positive"]
        & ranked["ground_truth_type"].isin(negative_types)
    ].copy()

    cols = [
        "user_id",
        "ground_truth_type",
        "baseline_risk_score",
        "event_count",
        "action_entropy",
        "gold_sent",
        "gold_received",
        "max_receiver_share",
    ]
    cols = [c for c in cols if c in fp.columns]
    return fp[cols]


def save_charts(df: pd.DataFrame):
    labeled = df[df["ground_truth_type"].notna()].copy()
    if labeled.empty:
        return

    type_order = [
        t for t in
        ["normal", "hardcore", "guild", "bot", "farm", "mule", "hub"]
        if t in labeled["ground_truth_type"].unique()
    ]

    chart_data = [
        labeled.loc[
            labeled["ground_truth_type"] == t,
            "baseline_risk_score"
        ].values
        for t in type_order
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(chart_data, tick_labels=type_order)
    ax.set_title("Isolation Forest Risk by Account Type")
    ax.set_ylabel("Risk Score (0-100)")
    ax.set_xlabel("Ground Truth Type")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "baseline_v2_risk_by_type.png", dpi=160)
    plt.close(fig)


def main():
    df = load_features()

    feature_cols = choose_numeric_features(df)
    if not feature_cols:
        raise ValueError("Isolation Forest에 사용할 수치형 Feature가 없습니다.")

    X = (
        df[feature_cols]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=500,
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    raw_anomaly = -model.decision_function(X_scaled)
    df["baseline_anomaly_raw"] = raw_anomaly
    df["baseline_risk_score"] = normalize_to_100(
        pd.Series(raw_anomaly, index=df.index)
    ).round(3)
    df["baseline_rank"] = (
        df["baseline_risk_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    # 평가지표 1: 모든 비정상 행위 탐지
    general_metrics = evaluate_top_k(
        df,
        benchmark_name="general_anomaly",
        positive_types=GENERAL_ANOMALY_TYPES,
        negative_types=LEGIT_TYPES,
    )

    # 평가지표 2: 조직형 작업장만 탐지
    # BOT은 정상도 조직형 작업장도 아니므로 이 평가에서 제외
    organized_metrics = evaluate_top_k(
        df,
        benchmark_name="organized_abuse",
        positive_types=ORGANIZED_ABUSE_TYPES,
        negative_types=LEGIT_TYPES,
    )

    metrics = pd.DataFrame([general_metrics, organized_metrics])

    general_fp = false_positive_table(
        df,
        positive_types=GENERAL_ANOMALY_TYPES,
        negative_types=LEGIT_TYPES,
    )

    organized_fp = false_positive_table(
        df,
        positive_types=ORGANIZED_ABUSE_TYPES,
        negative_types=LEGIT_TYPES,
    )

    scores_path = OUT_DIR / "baseline_v2_account_scores.csv"
    metrics_path = OUT_DIR / "baseline_v2_metrics.csv"
    general_fp_path = OUT_DIR / "baseline_v2_general_false_positives.csv"
    organized_fp_path = OUT_DIR / "baseline_v2_organized_false_positives.csv"
    features_path = OUT_DIR / "baseline_v2_feature_list.txt"

    df.sort_values("baseline_risk_score", ascending=False).to_csv(
        scores_path,
        index=False,
        encoding="utf-8-sig",
    )
    metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")
    general_fp.to_csv(general_fp_path, index=False, encoding="utf-8-sig")
    organized_fp.to_csv(
        organized_fp_path, index=False, encoding="utf-8-sig"
    )
    features_path.write_text("\n".join(feature_cols), encoding="utf-8")

    save_charts(df)

    print("\n" + "=" * 82)
    print(" GHOST FARM | ISOLATION FOREST BASELINE V2")
    print("=" * 82)
    print(f"Player-like accounts     : {len(df)}")
    print(f"Features used            : {len(feature_cols)}")
    print("SYSTEM_* excluded        : YES")
    print("Ground Truth in training : NO")

    for row in [general_metrics, organized_metrics]:
        print("\n[" + row["benchmark"] + "]")
        print(f"Positive types           : {row['positive_types']}")
        print(f"Negative types           : {row['negative_types']}")
        print(f"Evaluation accounts      : {row['eval_accounts']}")
        print(f"Positive accounts        : {row['positive_accounts']}")
        print(f"Precision@K              : {row['precision_at_k']:.3f}")
        print(f"Recall@K                 : {row['recall_at_k']:.3f}")
        print(f"F1@K                     : {row['f1_at_k']:.3f}")
        print(
            "Confusion Matrix          : "
            f"TN={row['tn']} / FP={row['fp']} / "
            f"FN={row['fn']} / TP={row['tp']}"
        )

    show_cols = [
        "user_id",
        "ground_truth_type",
        "baseline_risk_score",
        "baseline_rank",
        "event_count",
        "action_entropy",
        "gold_sent",
        "gold_received",
        "max_receiver_share",
    ]
    show_cols = [c for c in show_cols if c in df.columns]

    print("\n[위험도 TOP 15]")
    print(
        df.sort_values("baseline_risk_score", ascending=False)[show_cols]
        .head(15)
        .to_string(index=False)
    )

    print("\n[조직형 작업장 평가의 실제 오탐 계정]")
    if organized_fp.empty:
        print("없음")
    else:
        print(organized_fp.to_string(index=False))

    print("\n[생성 파일]")
    print(f"- {scores_path}")
    print(f"- {metrics_path}")
    print(f"- {general_fp_path}")
    print(f"- {organized_fp_path}")
    print(f"- {features_path}")
    print(f"- {FIG_DIR / 'baseline_v2_risk_by_type.png'}")

    print("\n※ BOT은 general_anomaly에서는 양성입니다.")
    print("※ BOT은 organized_abuse 평가에서는 제외됩니다.")
    print("※ normal / hardcore / guild만 정상 음성군으로 사용합니다.")
    print("=" * 82 + "\n")


if __name__ == "__main__":
    main()
