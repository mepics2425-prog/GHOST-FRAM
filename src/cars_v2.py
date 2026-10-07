from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
ANALYSIS = ROOT / "data" / "analysis"
ANALYSIS.mkdir(parents=True, exist_ok=True)

ACCOUNT_PATH = PROCESSED / "account_features_v1.csv"
NETWORK_PATH = ANALYSIS / "network_account_metrics.csv"
EDGE_PATH = ANALYSIS / "network_edges.csv"
MOTIF_PATH = ANALYSIS / "ghost_motif_candidates_v1.csv"
SYNC_PATH = ANALYSIS / "behavior_pair_sync.csv"

ABUSE = {"farm", "mule", "hub"}
LEGIT = {"normal", "hardcore", "guild"}

# V2 weights: unseen_01 오류 분석을 반영한 개발 버전
W_FARM = 0.28
W_MULE = 0.27
W_HUB = 0.20
W_CHAIN = 0.15
W_ECON = 0.07
W_REPEAT = 0.03

VOL_SCALE = 200.0


def req(p: Path):
    if not p.exists():
        raise FileNotFoundError(f"필수 파일 없음: {p}")


def num(s, idx=None):
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce").fillna(0.0)
    if idx is None:
        return 0.0
    return pd.Series(float(s), index=idx)


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def build_sync_lookup(sync: pd.DataFrame):
    d = {}
    for _, r in sync.iterrows():
        a, b = str(r["user_a"]), str(r["user_b"])
        d[tuple(sorted((a, b)))] = float(r["sync_score"])
    return d


def best_partner_sync(uid: str, edges: pd.DataFrame, sync_lookup: dict):
    rel = edges[
        (edges["sender_id"].astype(str) == uid)
        | (edges["receiver_id"].astype(str) == uid)
    ]
    if rel.empty:
        return 0.0, 0.0

    vals, weights = [], []
    for _, r in rel.iterrows():
        a = str(r["sender_id"])
        b = str(r["receiver_id"])
        partner = b if a == uid else a
        sc = sync_lookup.get(tuple(sorted((uid, partner))), 0.0)
        vals.append(sc)
        weights.append(max(float(r.get("total_gold", 0) or 0), 0.0))

    weighted = float(np.average(vals, weights=weights)) if sum(weights) > 0 else float(np.mean(vals))
    return weighted, max(vals) if vals else 0.0


def edge_stats(uid: str, edges: pd.DataFrame):
    out = edges[edges["sender_id"].astype(str) == uid].copy()
    inc = edges[edges["receiver_id"].astype(str) == uid].copy()

    gold_out = float(out["total_gold"].sum()) if len(out) else 0.0
    gold_in = float(inc["total_gold"].sum()) if len(inc) else 0.0

    max_out = float(out["total_gold"].max()) if len(out) else 0.0
    max_in = float(inc["total_gold"].max()) if len(inc) else 0.0

    return {
        "edge_gold_out": gold_out,
        "edge_gold_in": gold_in,
        "out_partner_count_v2": int(out["receiver_id"].nunique()) if len(out) else 0,
        "in_partner_count_v2": int(inc["sender_id"].nunique()) if len(inc) else 0,
        "primary_out_share": max_out / gold_out if gold_out > 0 else 0.0,
        "primary_in_share": max_in / gold_in if gold_in > 0 else 0.0,
    }


def build_chain_features(df: pd.DataFrame, motif: pd.DataFrame):
    """
    V2 Ghost Chain:
    source -> middle -> destination 각각의 구조 순도를 이용.
    Ground Truth는 사용하지 않음.
    """
    m = df.set_index("user_id")

    rows = []
    for uid in df["user_id"].astype(str):
        best_source = 0.0
        best_middle = 0.0
        best_dest = 0.0

        related = motif[
            (motif["source"].astype(str) == uid)
            | (motif["middle"].astype(str) == uid)
            | (motif["destination"].astype(str) == uid)
        ]

        for _, r in related.iterrows():
            s = str(r["source"])
            mid = str(r["middle"])
            dst = str(r["destination"])

            if s not in m.index or mid not in m.index or dst not in m.index:
                continue

            motif01 = clamp01(float(r.get("motif_score", 0) or 0) / 100.0)
            temporal01 = clamp01(float(r.get("temporal_score", 0) or 0))

            source_share = clamp01(float(m.loc[s, "primary_out_share"]))
            relay_purity = clamp01(float(m.loc[mid, "mule_purity"]))
            sink_purity = clamp01(float(m.loc[dst, "hub_purity"]))

            # 경로가 실제 funnel일수록 높음.
            chain = (
                0.30 * motif01
                + 0.15 * temporal01
                + 0.20 * source_share
                + 0.20 * relay_purity
                + 0.15 * sink_purity
            ) * 100.0

            if uid == s:
                best_source = max(best_source, chain)
            if uid == mid:
                best_middle = max(best_middle, chain)
            if uid == dst:
                best_dest = max(best_dest, chain)

        rows.append({
            "user_id": uid,
            "source_chain_score": best_source,
            "middle_chain_score": best_middle,
            "destination_chain_score": best_dest,
            "ghost_chain_score": max(best_source, best_middle, best_dest),
        })

    return pd.DataFrame(rows)


def evaluate(df: pd.DataFrame):
    e = df[df["ground_truth_type"].isin(ABUSE | LEGIT)].copy()
    e["y_true"] = e["ground_truth_type"].isin(ABUSE).astype(int)
    k = int(e["y_true"].sum())

    e = e.sort_values("cars_v2_score", ascending=False)
    e["y_pred"] = 0
    if k:
        e.iloc[:k, e.columns.get_loc("y_pred")] = 1

    tp = int(((e.y_true == 1) & (e.y_pred == 1)).sum())
    fp = int(((e.y_true == 0) & (e.y_pred == 1)).sum())
    fn = int(((e.y_true == 1) & (e.y_pred == 0)).sum())
    tn = int(((e.y_true == 0) & (e.y_pred == 0)).sum())

    p = tp / (tp + fp) if tp + fp else 0
    r = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * p * r / (p + r) if p + r else 0

    return e, {
        "eval_accounts": len(e),
        "positive_accounts": k,
        "precision_at_k": p,
        "recall_at_k": r,
        "f1_at_k": f1,
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def main():
    for p in [ACCOUNT_PATH, NETWORK_PATH, EDGE_PATH, MOTIF_PATH, SYNC_PATH]:
        req(p)

    acc = pd.read_csv(ACCOUNT_PATH)
    net = pd.read_csv(NETWORK_PATH).drop(columns=["ground_truth_type"], errors="ignore")
    edges = pd.read_csv(EDGE_PATH)
    motif = pd.read_csv(MOTIF_PATH)
    sync = pd.read_csv(SYNC_PATH)

    acc = acc[~acc["user_id"].astype(str).str.startswith("SYSTEM_")].copy()
    df = acc.merge(net, on="user_id", how="left", suffixes=("", "_network"))

    # 1) 거래 관계 통계
    edge_rows = [dict(user_id=uid, **edge_stats(uid, edges)) for uid in df["user_id"].astype(str)]
    df = df.merge(pd.DataFrame(edge_rows), on="user_id", how="left")

    df["edge_gold_out"] = num(df["edge_gold_out"])
    df["edge_gold_in"] = num(df["edge_gold_in"])
    df["primary_out_share"] = num(df["primary_out_share"])
    df["primary_in_share"] = num(df["primary_in_share"])

    total_volume = df["edge_gold_out"] + df["edge_gold_in"]
    df["volume_confidence_v2"] = 1 - np.exp(-total_volume / VOL_SCALE)

    # 2) Farm purity
    # 핵심: '몇 명에게 보냈나'보다 '주 수신처로 얼마가 몰렸나'를 직접 반영.
    outflow01 = df["edge_gold_out"] / (df["edge_gold_out"] + df["edge_gold_in"]).replace(0, np.nan)
    outflow01 = outflow01.fillna(0.0)

    df["farm_purity"] = (
        0.55 * df["primary_out_share"]
        + 0.30 * outflow01
        + 0.15 * df["volume_confidence_v2"]
    ).clip(0, 1)

    # 3) Mule purity
    # Mule: 여러 명에게 받고, 받은 재화를 소수 수신처로 넘기며, in/out이 균형.
    in_breadth = 1 - np.exp(-num(df["in_partner_count_v2"]) / 3.0)
    receiver_concentration = df["primary_out_share"]
    flow_balance = num(df.get("flow_balance", pd.Series(0, index=df.index))).clip(0, 1)

    # 다수 수신처로 퍼뜨리는 계정은 relay purity 감점.
    out_partner_penalty = 1 / np.sqrt(np.maximum(num(df["out_partner_count_v2"]), 1))

    df["mule_purity"] = (
        in_breadth
        * receiver_concentration
        * flow_balance
        * out_partner_penalty
    ).clip(0, 1)

    # 4) Hub purity
    incoming_ratio = df["edge_gold_in"] / (df["edge_gold_in"] + df["edge_gold_out"]).replace(0, np.nan)
    incoming_ratio = incoming_ratio.fillna(0.0)
    sender_breadth = 1 - np.exp(-num(df["in_partner_count_v2"]) / 2.0)

    df["hub_purity"] = (
        incoming_ratio
        * sender_breadth
        * df["volume_confidence_v2"]
    ).clip(0, 1)

    # 5) Sync는 실제 거래 상대와의 sync만 사용
    lookup = build_sync_lookup(sync)
    sync_rows = []
    for uid in df["user_id"].astype(str):
        mean_sync, max_sync = best_partner_sync(uid, edges, lookup)
        sync_rows.append({
            "user_id": uid,
            "tx_partner_sync_v2": mean_sync,
            "max_tx_partner_sync_v2": max_sync,
        })
    df = df.merge(pd.DataFrame(sync_rows), on="user_id", how="left")

    # 6) 구조 점수
    df["farm_component_v2"] = 100 * df["farm_purity"]
    df["mule_component_v2"] = 100 * df["mule_purity"]
    df["hub_component_v2"] = 100 * df["hub_purity"]

    chain = build_chain_features(df, motif)
    df = df.merge(chain, on="user_id", how="left")

    role_max = df[["farm_purity", "mule_purity", "hub_purity"]].max(axis=1)
    df["sync_interaction_v2"] = (
        num(df["tx_partner_sync_v2"])
        * role_max
        * df["volume_confidence_v2"]
    )

    # Economic
    price_dev = num(df.get("max_price_deviation", pd.Series(0, index=df.index))).clip(0, 1)
    df["economic_v2"] = np.maximum(
        100 * price_dev,
        100 * df["primary_out_share"] * df["volume_confidence_v2"] * 0.70
    )

    # Repetition
    entropy = num(df["action_entropy"])
    df["repetition_v2"] = (1 - entropy.rank(pct=True)) * 100

    # 역할 특화 CARS:
    # Farm/Mule/Hub 중 가장 강한 조직 역할을 structural score로 사용.
    role_component = np.maximum.reduce([
        df["farm_component_v2"].to_numpy(),
        df["mule_component_v2"].to_numpy(),
        df["hub_component_v2"].to_numpy()
    ])

    df["role_component_v2"] = role_component

    df["cars_v2_score"] = (
        W_FARM * df["farm_component_v2"]
        + W_MULE * df["mule_component_v2"]
        + W_HUB * df["hub_component_v2"]
        + W_CHAIN * df["ghost_chain_score"]
        + W_ECON * df["economic_v2"]
        + W_REPEAT * df["repetition_v2"]
    )

    # Sync는 standalone 가중합이 아니라, 조직 역할이 이미 있을 때만 작은 보정으로 추가
    df["cars_v2_score"] += 0.10 * df["sync_interaction_v2"]

    df["cars_v2_score"] = df["cars_v2_score"].round(3)
    df["cars_v2_rank"] = df["cars_v2_score"].rank(method="first", ascending=False).astype(int)

    ev, metrics = evaluate(df)

    fp = ev[(ev.y_pred == 1) & ev.ground_truth_type.isin(LEGIT)]
    fn = ev[(ev.y_pred == 0) & ev.ground_truth_type.isin(ABUSE)]

    score_cols = [
        "user_id","ground_truth_type","cars_v2_score","cars_v2_rank",
        "farm_component_v2","mule_component_v2","hub_component_v2",
        "ghost_chain_score","sync_interaction_v2","economic_v2","repetition_v2",
        "primary_out_share","out_partner_count_v2","in_partner_count_v2",
        "volume_confidence_v2"
    ]

    df.sort_values("cars_v2_score", ascending=False)[score_cols].to_csv(
        ANALYSIS / "cars_v2_account_scores.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([metrics]).to_csv(
        ANALYSIS / "cars_v2_metrics.csv", index=False, encoding="utf-8-sig"
    )
    fp[score_cols].to_csv(
        ANALYSIS / "cars_v2_false_positives.csv", index=False, encoding="utf-8-sig"
    )
    fn[score_cols].to_csv(
        ANALYSIS / "cars_v2_false_negatives.csv", index=False, encoding="utf-8-sig"
    )

    print("\n" + "="*100)
    print("GHOST FARM | CARS V2 — RELATIONSHIP PURITY MODEL")
    print("="*100)
    print("Ground Truth in score : NO")
    print("개발 근거             : unseen_01 FP/FN 오류 분석")
    print("\n[V2 핵심 변경]")
    print("1) Mule = 다수 유입 × 단일/소수 유출 × 높은 flow balance")
    print("2) Farm = primary receiver share를 직접 반영")
    print("3) Ghost Chain = Source/Middle/Destination 구조 순도를 같이 평가")
    print("4) Sync = 단독 위험 신호가 아니라 구조적 Funnel이 있을 때만 상호작용")

    print("\n[조직형 작업장 평가]")
    print(f"Evaluation accounts : {metrics['eval_accounts']}")
    print(f"Positive accounts   : {metrics['positive_accounts']}")
    print(f"Precision@K         : {metrics['precision_at_k']:.3f}")
    print(f"Recall@K            : {metrics['recall_at_k']:.3f}")
    print(f"F1@K                : {metrics['f1_at_k']:.3f}")
    print(f"Confusion Matrix    : TN={metrics['tn']} / FP={metrics['fp']} / FN={metrics['fn']} / TP={metrics['tp']}")

    print("\n[CARS V2 TOP 20]")
    print(df.sort_values("cars_v2_score", ascending=False)[score_cols].head(20).round(3).to_string(index=False))

    print("\n[False Positive]")
    print("없음" if fp.empty else fp[["user_id","ground_truth_type","cars_v2_score"]].to_string(index=False))

    print("\n[False Negative]")
    print("없음" if fn.empty else fn[["user_id","ground_truth_type","cars_v2_score"]].to_string(index=False))

    print("\n[생성 파일]")
    print(ANALYSIS / "cars_v2_account_scores.csv")
    print(ANALYSIS / "cars_v2_metrics.csv")
    print(ANALYSIS / "cars_v2_false_positives.csv")
    print(ANALYSIS / "cars_v2_false_negatives.csv")

    print("\n주의: unseen_01은 이제 V2 개발 데이터입니다.")
    print("V2 성능 확정은 새로운 unseen_02에서 코드 수정 없이 검증해야 합니다.")
    print("="*100 + "\n")


if __name__ == "__main__":
    main()
