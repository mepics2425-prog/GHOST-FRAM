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

# 이번 프로젝트의 1차 핵심 타깃:
# 조직형 작업장 구조를 이루는 FARM / MULE / HUB
ORGANIZED_TYPES = {"farm", "mule", "hub"}


def load_features() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(
            f"\n입력 파일을 찾을 수 없습니다:\n{INPUT_PATH}\n"
            "먼저 src/inspect_logs.py를 실행해 주세요.\n"
        )

    df = pd.read_csv(INPUT_PATH)

    if "user_id" not in df.columns:
        raise ValueError("account_features_v1.csv에 user_id 컬럼이 없습니다.")

    return df


def choose_numeric_features(df: pd.DataFrame) -> list[str]:
    """
    모델에 넣어도 되는 수치형 컬럼만 선택.
    Ground Truth, ID, 날짜/시간은 제외한다.
    """
    exclude = {
        "ground_truth_type",
        "device_group",
        "ip_group",
        "user_id",
        "active_first",
        "active_last",
        "first_login",
        "last_login",
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    feature_cols = [c for c in numeric_cols if c not in exclude]

    # 값이 전부 같은 컬럼은 정보가 없으므로 제거
    feature_cols = [
        c for c in feature_cols
        if df[c].nunique(dropna=True) > 1
    ]

    return feature_cols


def prepare_matrix(df: pd.DataFrame, feature_cols: list[str]):
    X = df[feature_cols].copy()
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    return X, X_scaled


def normalize_to_100(values: pd.Series) -> pd.Series:
    v = pd.to_numeric(values, errors="coerce").fillna(0.0)
    lo, hi = v.min(), v.max()

    if hi == lo:
        return pd.Series(0.0, index=v.index)

    return (v - lo) / (hi - lo) * 100.0


def evaluate_top_k(df: pd.DataFrame) -> dict:
    """
    모델 학습에는 Ground Truth를 사용하지 않는다.
    평가 단계에서만 실제 조직형 어뷰징 계정 수만큼 Top-K를 잡아
    Precision / Recall / F1을 확인한다.
    """
    labeled = df[df["ground_truth_type"].notna()].copy()

    if labeled.empty:
        return {
            "target_count": 0,
            "top_k": 0,
            "precision_at_k": np.nan,
            "recall_at_k": np.nan,
            "f1_at_k": np.nan,
            "tn": np.nan,
            "fp": np.nan,
            "fn": np.nan,
            "tp": np.nan,
        }

    labeled["y_true"] = labeled["ground_truth_type"].isin(ORGANIZED_TYPES).astype(int)
    target_count = int(labeled["y_true"].sum())

    if target_count == 0:
        return {
            "target_count": 0,
            "top_k": 0,
            "precision_at_k": np.nan,
            "recall_at_k": np.nan,
            "f1_at_k": np.nan,
            "tn": np.nan,
            "fp": np.nan,
            "fn": np.nan,
            "tp": np.nan,
        }

    labeled = labeled.sort_values("baseline_risk_score", ascending=False)
    labeled["y_pred_topk"] = 0
    labeled.iloc[:target_count, labeled.columns.get_loc("y_pred_topk")] = 1

    p = precision_score(labeled["y_true"], labeled["y_pred_topk"], zero_division=0)
    r = recall_score(labeled["y_true"], labeled["y_pred_topk"], zero_division=0)
    f1 = f1_score(labeled["y_true"], labeled["y_pred_topk"], zero_division=0)

    tn, fp, fn, tp = confusion_matrix(
        labeled["y_true"],
        labeled["y_pred_topk"],
        labels=[0, 1]
    ).ravel()

    return {
        "target_count": target_count,
        "top_k": target_count,
        "precision_at_k": p,
        "recall_at_k": r,
        "f1_at_k": f1,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def create_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    labeled = df[df["ground_truth_type"].notna()].copy()

    if labeled.empty:
        return pd.DataFrame()

    numeric_candidates = [
        "event_count",
        "action_diversity",
        "map_diversity",
        "active_minutes",
        "action_entropy",
        "session_count",
        "total_play_time_sec",
        "gold_sent",
        "gold_received",
        "unique_receivers",
        "unique_senders",
        "max_receiver_share",
        "avg_price_deviation",
        "suspicious_price_trade_count",
        "outflow_ratio",
        "baseline_risk_score",
    ]
    cols = [c for c in numeric_candidates if c in labeled.columns]

    summary = (
        labeled.groupby("ground_truth_type")[cols]
        .mean(numeric_only=True)
        .round(3)
    )

    summary.insert(
        0,
        "account_count",
        labeled.groupby("ground_truth_type").size()
    )

    return summary


def save_charts(df: pd.DataFrame):
    labeled = df[df["ground_truth_type"].notna()].copy()

    if labeled.empty:
        return

    # 1) 유형별 Baseline Risk 분포
    type_order = [
        t for t in
        ["normal", "hardcore", "guild", "bot", "farm", "mule", "hub"]
        if t in labeled["ground_truth_type"].unique()
    ]

    data = [
        labeled.loc[
            labeled["ground_truth_type"] == t,
            "baseline_risk_score"
        ].values
        for t in type_order
    ]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot(data, tick_labels=type_order)
    ax.set_title("Isolation Forest Baseline Risk by Ground Truth Type")
    ax.set_ylabel("Risk Score (0-100)")
    ax.set_xlabel("Ground Truth Type")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "baseline_risk_by_type.png", dpi=160)
    plt.close(fig)

    # 2) 위험도 상위 계정
    top = df.sort_values("baseline_risk_score", ascending=False).head(15).copy()
    top = top.sort_values("baseline_risk_score", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top["user_id"], top["baseline_risk_score"])
    ax.set_title("Top 15 Accounts by Isolation Forest Baseline Risk")
    ax.set_xlabel("Risk Score (0-100)")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "baseline_top15_accounts.png", dpi=160)
    plt.close(fig)


def main():
    df = load_features()
    feature_cols = choose_numeric_features(df)

    if not feature_cols:
        raise ValueError("Isolation Forest에 사용할 수치형 Feature가 없습니다.")

    X_raw, X_scaled = prepare_matrix(df, feature_cols)

    # Unsupervised baseline:
    # Ground Truth를 학습에 사용하지 않고 account feature만 사용
    model = IsolationForest(
        n_estimators=500,
        contamination="auto",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    # decision_function 값이 낮을수록 더 이상함.
    # 보기 편하도록 방향을 뒤집어 Risk 0~100으로 변환.
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

    # 평가용 라벨
    df["is_organized_abuse"] = (
        df["ground_truth_type"].isin(ORGANIZED_TYPES)
        if "ground_truth_type" in df.columns
        else False
    )

    metrics = evaluate_top_k(df)
    summary = create_type_summary(df)

    # 저장
    scores_path = OUT_DIR / "baseline_account_scores.csv"
    metrics_path = OUT_DIR / "baseline_metrics.csv"
    summary_path = OUT_DIR / "account_type_summary.csv"
    features_path = OUT_DIR / "baseline_feature_list.txt"

    df.sort_values("baseline_risk_score", ascending=False).to_csv(
        scores_path,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame([metrics]).to_csv(
        metrics_path,
        index=False,
        encoding="utf-8-sig",
    )

    if not summary.empty:
        summary.to_csv(summary_path, encoding="utf-8-sig")

    features_path.write_text(
        "\n".join(feature_cols),
        encoding="utf-8"
    )

    save_charts(df)

    print("\n" + "=" * 76)
    print(" GHOST FARM | EDA + ISOLATION FOREST BASELINE")
    print("=" * 76)
    print(f"Accounts                : {len(df):,}")
    print(f"Features used           : {len(feature_cols):,}")
    print("Ground Truth in training: NO")
    print("Baseline model          : Isolation Forest")
    print("Target for evaluation   : FARM + MULE + HUB")

    print("\n[Baseline 평가 — Ground Truth는 평가에만 사용]")
    if metrics["top_k"]:
        print(f"Organized abuse 계정 수 : {metrics['target_count']}")
        print(f"Precision@K             : {metrics['precision_at_k']:.3f}")
        print(f"Recall@K                : {metrics['recall_at_k']:.3f}")
        print(f"F1@K                    : {metrics['f1_at_k']:.3f}")
        print(
            "Confusion Matrix         : "
            f"TN={metrics['tn']} / FP={metrics['fp']} / "
            f"FN={metrics['fn']} / TP={metrics['tp']}"
        )
    else:
        print("평가 가능한 Ground Truth가 없습니다.")

    show_cols = [
        "user_id",
        "ground_truth_type",
        "baseline_risk_score",
        "baseline_rank",
    ]

    optional = [
        "event_count",
        "action_entropy",
        "gold_sent",
        "gold_received",
        "max_receiver_share",
        "suspicious_price_trade_count",
    ]
    show_cols += [c for c in optional if c in df.columns]

    print("\n[Baseline 위험도 TOP 15]")
    print(
        df.sort_values("baseline_risk_score", ascending=False)[show_cols]
        .head(15)
        .to_string(index=False)
    )

    if "ground_truth_type" in df.columns:
        fp = df[
            (~df["ground_truth_type"].isin(ORGANIZED_TYPES))
            & df["ground_truth_type"].notna()
        ].sort_values("baseline_risk_score", ascending=False).head(5)

        print("\n[Baseline이 의심한 정상/비조직형 계정 TOP 5 — 오탐 후보]")
        print(
            fp[show_cols]
            .to_string(index=False)
        )

    if not summary.empty:
        print("\n[유형별 평균 특징 요약]")
        print(summary.to_string())

    print("\n[생성 파일]")
    print(f"- {scores_path}")
    print(f"- {metrics_path}")
    print(f"- {summary_path}")
    print(f"- {features_path}")
    print(f"- {FIG_DIR / 'baseline_risk_by_type.png'}")
    print(f"- {FIG_DIR / 'baseline_top15_accounts.png'}")

    print("\n해석 포인트:")
    print("1) 이 Baseline은 계정 하나의 Feature만 보고 이상도를 계산합니다.")
    print("2) normal/hardcore/guild가 상위에 끼면 그 자체가 실패 사례입니다.")
    print("3) 다음 단계에서 계정 간 동기화와 거래 Graph를 추가해 이 오탐을 줄입니다.")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
