from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

ACCOUNT_PATH = PROCESSED_DIR / "account_features_v1.csv"
NETWORK_PATH = ANALYSIS_DIR / "network_account_metrics.csv"
EDGE_PATH = ANALYSIS_DIR / "network_edges.csv"
MOTIF_PATH = ANALYSIS_DIR / "ghost_motif_candidates_v1.csv"
SYNC_PAIR_PATH = ANALYSIS_DIR / "behavior_pair_sync.csv"

# ---------------------------------------------------------
# CARS V1
# Ground Truth는 아래 점수 계산에 사용하지 않는다.
# 마지막 ranking 평가 단계에서만 사용한다.
# ---------------------------------------------------------

W_GRAPH = 0.35
W_MOTIF = 0.30
W_SYNC_FUNNEL = 0.20
W_ECONOMIC = 0.10
W_REPETITION = 0.05

VOLUME_SCALE_GOLD = 200.0

ORGANIZED_TYPES = {"farm", "mule", "hub"}
LEGIT_TYPES = {"normal", "hardcore", "guild"}


def require_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(
            f"\n필수 파일이 없습니다:\n{path}\n"
            "이전 분석 단계를 먼저 실행해 주세요.\n"
        )


def load_inputs():
    for p in [
        ACCOUNT_PATH,
        NETWORK_PATH,
        EDGE_PATH,
        MOTIF_PATH,
        SYNC_PAIR_PATH,
    ]:
        require_file(p)

    account = pd.read_csv(ACCOUNT_PATH)
    network = pd.read_csv(NETWORK_PATH)
    edges = pd.read_csv(EDGE_PATH)
    motif = pd.read_csv(MOTIF_PATH)
    sync_pair = pd.read_csv(SYNC_PAIR_PATH)

    return account, network, edges, motif, sync_pair


def safe_numeric(series, default=0.0):
    return pd.to_numeric(series, errors="coerce").fillna(default)


def build_pair_sync_lookup(sync_pair: pd.DataFrame) -> dict:
    lookup = {}

    for _, r in sync_pair.iterrows():
        a = str(r["user_a"])
        b = str(r["user_b"])
        key = tuple(sorted((a, b)))
        lookup[key] = float(r["sync_score"])

    return lookup


def build_tx_partner_sync(
    user_ids: list[str],
    edges: pd.DataFrame,
    sync_pair: pd.DataFrame,
) -> pd.DataFrame:
    """
    계정의 '실제 거래 상대'와 행동이 얼마나 동기화되어 있는지 계산.

    Guild 구성원끼리 행동 Sync가 높더라도
    재화 Funnel 거래가 없다면 이 항목은 크게 올라가지 않는다.
    """
    lookup = build_pair_sync_lookup(sync_pair)

    rows = []

    for uid in user_ids:
        rel = edges[
            (edges["sender_id"].astype(str) == uid)
            | (edges["receiver_id"].astype(str) == uid)
        ].copy()

        if rel.empty:
            rows.append({
                "user_id": uid,
                "tx_partner_sync": 0.0,
                "max_tx_partner_sync": 0.0,
                "tx_partner_count": 0,
            })
            continue

        scores = []
        weights = []

        for _, r in rel.iterrows():
            sender = str(r["sender_id"])
            receiver = str(r["receiver_id"])
            partner = receiver if sender == uid else sender

            sync_score = lookup.get(
                tuple(sorted((uid, partner))),
                0.0,
            )

            gold = float(r.get("total_gold", 0) or 0)

            scores.append(sync_score)
            weights.append(max(gold, 0.0))

        if sum(weights) > 0:
            weighted_sync = float(np.average(scores, weights=weights))
        else:
            weighted_sync = float(np.mean(scores)) if scores else 0.0

        rows.append({
            "user_id": uid,
            "tx_partner_sync": weighted_sync,
            "max_tx_partner_sync": max(scores) if scores else 0.0,
            "tx_partner_count": len(scores),
        })

    return pd.DataFrame(rows)


def build_role_aware_motif(
    df: pd.DataFrame,
    motif: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ghost Motif 참여 점수.

    Source일 때 Farm role,
    Middle일 때 Mule role,
    Destination일 때 Hub role과 결합한다.

    단순 2-hop 경로가 존재한다는 이유만으로 높은 점수를 주지 않는다.
    """
    role_lookup = df.set_index("user_id")[
        ["farm_role_score", "mule_role_score", "hub_role_score"]
    ].to_dict("index")

    rows = []

    for uid in df["user_id"]:
        candidates = []

        for _, r in motif.iterrows():
            motif_score = float(r.get("motif_score", 0) or 0)

            if str(r.get("source")) == uid:
                role = role_lookup.get(uid, {}).get("farm_role_score", 0) or 0
                candidates.append({
                    "role": "source",
                    "middle": r.get("middle"),
                    "destination": r.get("destination"),
                    "raw_motif_score": motif_score,
                    "role_score": float(role),
                    "role_aware_score": motif_score * float(role) / 100.0,
                })

            if str(r.get("middle")) == uid:
                role = role_lookup.get(uid, {}).get("mule_role_score", 0) or 0
                candidates.append({
                    "role": "middle",
                    "middle": uid,
                    "destination": r.get("destination"),
                    "raw_motif_score": motif_score,
                    "role_score": float(role),
                    "role_aware_score": motif_score * float(role) / 100.0,
                })

            if str(r.get("destination")) == uid:
                role = role_lookup.get(uid, {}).get("hub_role_score", 0) or 0
                candidates.append({
                    "role": "destination",
                    "middle": r.get("middle"),
                    "destination": uid,
                    "raw_motif_score": motif_score,
                    "role_score": float(role),
                    "role_aware_score": motif_score * float(role) / 100.0,
                })

        if candidates:
            best = max(
                candidates,
                key=lambda x: x["role_aware_score"],
            )
            rows.append({
                "user_id": uid,
                "motif_role_aware_raw": best["role_aware_score"],
                "best_motif_role": best["role"],
                "best_motif_middle": best["middle"],
                "best_motif_destination": best["destination"],
            })
        else:
            rows.append({
                "user_id": uid,
                "motif_role_aware_raw": 0.0,
                "best_motif_role": None,
                "best_motif_middle": None,
                "best_motif_destination": None,
            })

    return pd.DataFrame(rows)


def build_repetition_score(df: pd.DataFrame) -> pd.Series:
    """
    Action entropy가 낮을수록 반복성이 높다고 본다.
    절대 임계값이 아니라 현재 관측 계정 내 percentile을 사용.
    """
    entropy = safe_numeric(df["action_entropy"])

    if entropy.nunique() <= 1:
        return pd.Series(0.0, index=df.index)

    percentile = entropy.rank(pct=True)
    return (1.0 - percentile) * 100.0


def evaluate_organized_abuse(df: pd.DataFrame) -> dict:
    eval_df = df[
        df["ground_truth_type"].isin(
            ORGANIZED_TYPES | LEGIT_TYPES
        )
    ].copy()

    eval_df["y_true"] = (
        eval_df["ground_truth_type"].isin(ORGANIZED_TYPES)
    ).astype(int)

    k = int(eval_df["y_true"].sum())

    ranked = eval_df.sort_values(
        "cars_score",
        ascending=False,
    ).copy()

    ranked["y_pred"] = 0
    if k > 0:
        ranked.iloc[:k, ranked.columns.get_loc("y_pred")] = 1

    tp = int(((ranked["y_true"] == 1) & (ranked["y_pred"] == 1)).sum())
    fp = int(((ranked["y_true"] == 0) & (ranked["y_pred"] == 1)).sum())
    fn = int(((ranked["y_true"] == 1) & (ranked["y_pred"] == 0)).sum())
    tn = int(((ranked["y_true"] == 0) & (ranked["y_pred"] == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )

    return {
        "eval_accounts": len(eval_df),
        "positive_accounts": k,
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f1_at_k": f1,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def main():
    account, network, edges, motif, sync_pair = load_inputs()

    # 평가용 Ground Truth는 account 파일에서만 보존한다.
    # 네트워크 파일 안의 ground_truth_type은 계산 전 제거한다.
    network = network.drop(
        columns=["ground_truth_type"],
        errors="ignore",
    )

    # 시스템 엔티티 제외
    account = account[
        ~account["user_id"].astype(str).str.startswith("SYSTEM_")
    ].copy()

    # 실사용자/ synthetic 사용자 모두 score는 계산한다.
    df = account.merge(
        network,
        on="user_id",
        how="left",
        suffixes=("", "_network"),
    )

    # Network에 참여하지 않은 계정은 0 처리
    net_numeric = [
        "gold_in",
        "gold_out",
        "unique_senders",
        "unique_receivers",
        "in_hhi",
        "out_hhi",
        "max_sender_share",
        "max_receiver_share_network",
        "outflow_ratio_network",
        "flow_balance",
        "in_degree",
        "out_degree",
        "weighted_in_gold",
        "weighted_out_gold",
        "betweenness",
        "pagerank",
        "farm_role_score",
        "mule_role_score",
        "hub_role_score",
        "graph_risk_score",
    ]

    for col in net_numeric:
        if col in df.columns:
            df[col] = safe_numeric(df[col])

    # ---------------------------------------------------------
    # 1) 거래량 신뢰도
    #
    # 7G 한 번 송금해서 HHI=1인 Guild와
    # 300~800G를 집중 송금하는 Farm을 같은 강도로 보지 않는다.
    #
    # confidence = 1 - exp(-volume / 200)
    # ---------------------------------------------------------
    df["p2p_volume"] = (
        safe_numeric(df.get("gold_in", pd.Series(0, index=df.index)))
        + safe_numeric(df.get("gold_out", pd.Series(0, index=df.index)))
    )

    df["volume_confidence"] = (
        1.0 - np.exp(-df["p2p_volume"] / VOLUME_SCALE_GOLD)
    )

    # ---------------------------------------------------------
    # 2) Graph Flow
    # ---------------------------------------------------------
    df["role_graph_raw"] = df[
        ["farm_role_score", "mule_role_score", "hub_role_score"]
    ].max(axis=1)

    # 거래가 거의 없는 계정은 graph score를 완전히 0으로 죽이지 않고
    # 최소 35%만 남기되, 실제 volume이 쌓일수록 신뢰도를 올린다.
    df["graph_flow_score"] = (
        df["role_graph_raw"]
        * (0.35 + 0.65 * df["volume_confidence"])
    )

    # ---------------------------------------------------------
    # 3) Ghost Motif
    # ---------------------------------------------------------
    motif_df = build_role_aware_motif(df, motif)
    df = df.merge(motif_df, on="user_id", how="left")

    df["motif_role_aware_raw"] = safe_numeric(
        df["motif_role_aware_raw"]
    )

    df["motif_component"] = (
        df["motif_role_aware_raw"]
        * (0.50 + 0.50 * df["volume_confidence"])
    )

    # ---------------------------------------------------------
    # 4) Sync × Funnel
    #
    # 전체 Sync를 그냥 더하지 않는다.
    # 실제 거래 상대와의 행동 동기화 × Graph Role × 거래량 신뢰도
    # ---------------------------------------------------------
    tx_sync = build_tx_partner_sync(
        df["user_id"].astype(str).tolist(),
        edges,
        sync_pair,
    )
    df = df.merge(tx_sync, on="user_id", how="left")

    for col in [
        "tx_partner_sync",
        "max_tx_partner_sync",
        "tx_partner_count",
    ]:
        df[col] = safe_numeric(df[col])

    df["sync_funnel_score"] = (
        df["tx_partner_sync"]
        * (df["role_graph_raw"] / 100.0)
        * df["volume_confidence"]
    )

    # ---------------------------------------------------------
    # 5) Economic anomaly
    # ---------------------------------------------------------
    max_price_dev = safe_numeric(
        df.get(
            "max_price_deviation",
            pd.Series(0, index=df.index),
        )
    ).clip(0, 1)

    concentration = safe_numeric(
        df.get(
            "max_receiver_share",
            pd.Series(0, index=df.index),
        )
    ).clip(0, 1)

    concentration_adjusted = (
        concentration
        * df["volume_confidence"]
        * 100.0
    )

    df["economic_score"] = np.maximum(
        max_price_dev * 100.0,
        concentration_adjusted * 0.70,
    )

    # ---------------------------------------------------------
    # 6) Repetition
    # ---------------------------------------------------------
    df["repetition_score"] = build_repetition_score(df)

    # ---------------------------------------------------------
    # 7) CARS
    #
    # 초기 가설 가중치.
    # 이 snapshot의 Ground Truth를 score 계산에 사용하지 않는다.
    #
    # 다만 이 데이터 자체는 synthetic calibration snapshot이므로
    # 이 결과를 일반화 성능으로 주장하면 안 된다.
    # ---------------------------------------------------------
    df["cars_score"] = (
        W_GRAPH * df["graph_flow_score"]
        + W_MOTIF * df["motif_component"]
        + W_SYNC_FUNNEL * df["sync_funnel_score"]
        + W_ECONOMIC * df["economic_score"]
        + W_REPETITION * df["repetition_score"]
    ).round(3)

    df["cars_rank"] = (
        df["cars_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    # Explainable evidence bundle
    def main_reason(r):
        comps = {
            "GraphFlow": r["graph_flow_score"],
            "GhostMotif": r["motif_component"],
            "SyncFunnel": r["sync_funnel_score"],
            "Economic": r["economic_score"],
            "Repetition": r["repetition_score"],
        }
        return max(comps, key=comps.get)

    df["primary_evidence"] = df.apply(main_reason, axis=1)

    # Ground Truth는 여기서 처음 평가에 사용
    metrics = evaluate_organized_abuse(df)

    ranked = df.sort_values(
        "cars_score",
        ascending=False,
    ).copy()

    eval_df = ranked[
        ranked["ground_truth_type"].isin(
            ORGANIZED_TYPES | LEGIT_TYPES
        )
    ].copy()

    k = metrics["positive_accounts"]
    eval_df["predicted_topk"] = False

    if k > 0:
        eval_df.iloc[
            :k,
            eval_df.columns.get_loc("predicted_topk")
        ] = True

    false_positive = eval_df[
        eval_df["predicted_topk"]
        & eval_df["ground_truth_type"].isin(LEGIT_TYPES)
    ].copy()

    false_negative = eval_df[
        ~eval_df["predicted_topk"]
        & eval_df["ground_truth_type"].isin(ORGANIZED_TYPES)
    ].copy()

    # Save
    score_path = ANALYSIS_DIR / "cars_v1_account_scores.csv"
    metric_path = ANALYSIS_DIR / "cars_v1_metrics.csv"
    fp_path = ANALYSIS_DIR / "cars_v1_false_positives.csv"
    fn_path = ANALYSIS_DIR / "cars_v1_false_negatives.csv"

    output_cols = [
        "user_id",
        "ground_truth_type",
        "cars_score",
        "cars_rank",
        "primary_evidence",
        "graph_flow_score",
        "motif_component",
        "sync_funnel_score",
        "economic_score",
        "repetition_score",
        "volume_confidence",
        "p2p_volume",
        "tx_partner_sync",
        "best_motif_role",
        "best_motif_middle",
        "best_motif_destination",
    ]

    ranked[output_cols].to_csv(
        score_path,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame([metrics]).to_csv(
        metric_path,
        index=False,
        encoding="utf-8-sig",
    )

    false_positive[output_cols].to_csv(
        fp_path,
        index=False,
        encoding="utf-8-sig",
    )

    false_negative[output_cols].to_csv(
        fn_path,
        index=False,
        encoding="utf-8-sig",
    )

    # Console
    print("\n" + "=" * 100)
    print(" GHOST FARM | CARS V1 — COORDINATED ABUSE RISK SCORE")
    print("=" * 100)
    print("Ground Truth in score     : NO")
    print("Target                    : FARM + MULE + HUB")
    print("")
    print("CARS =")
    print(f"  {W_GRAPH:.2f} * GraphFlow")
    print(f"+ {W_MOTIF:.2f} * GhostMotif")
    print(f"+ {W_SYNC_FUNNEL:.2f} * SyncFunnel")
    print(f"+ {W_ECONOMIC:.2f} * Economic")
    print(f"+ {W_REPETITION:.2f} * Repetition")
    print("")
    print(
        "VolumeConfidence = "
        f"1 - exp(-P2P_Gold / {VOLUME_SCALE_GOLD:.0f})"
    )
    print("")
    print(
        "SyncFunnel = "
        "TransactionPartnerSync × GraphRole × VolumeConfidence"
    )

    print("\n[CARS 조직형 작업장 평가 — Ground Truth는 평가에만 사용]")
    print(f"Evaluation accounts       : {metrics['eval_accounts']}")
    print(f"Positive accounts         : {metrics['positive_accounts']}")
    print(f"Precision@K               : {metrics['precision_at_k']:.3f}")
    print(f"Recall@K                  : {metrics['recall_at_k']:.3f}")
    print(f"F1@K                      : {metrics['f1_at_k']:.3f}")
    print(
        "Confusion Matrix          : "
        f"TN={metrics['tn']} / "
        f"FP={metrics['fp']} / "
        f"FN={metrics['fn']} / "
        f"TP={metrics['tp']}"
    )

    print("\n[CARS 위험도 TOP 20]")
    show = [
        "user_id",
        "ground_truth_type",
        "cars_score",
        "graph_flow_score",
        "motif_component",
        "sync_funnel_score",
        "economic_score",
        "repetition_score",
        "primary_evidence",
    ]
    print(
        ranked[show]
        .head(20)
        .round(3)
        .to_string(index=False)
    )

    print("\n[False Positive]")
    if false_positive.empty:
        print("없음")
    else:
        print(
            false_positive[
                ["user_id", "ground_truth_type", "cars_score"]
            ].to_string(index=False)
        )

    print("\n[False Negative]")
    if false_negative.empty:
        print("없음")
    else:
        print(
            false_negative[
                ["user_id", "ground_truth_type", "cars_score"]
            ].to_string(index=False)
        )

    print("\n[생성 파일]")
    print(f"- {score_path}")
    print(f"- {metric_path}")
    print(f"- {fp_path}")
    print(f"- {fn_path}")

    print("\n주의:")
    print("1) 현재 결과는 동일 synthetic snapshot에서의 calibration 결과입니다.")
    print("2) 높은 성능이 나오더라도 일반화 성능으로 주장하면 안 됩니다.")
    print("3) 다음 단계에서 새로운 seed / 회피 시나리오 / unseen snapshot으로 재검증해야 합니다.")
    print("4) 특히 Guild의 높은 Sync를 막기 위해 Sync를 단독 사용하지 않고 Funnel과 상호작용시켰습니다.")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()
