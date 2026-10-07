from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "aetheria-all.json"
OUT_DIR = PROJECT_ROOT / "data" / "analysis"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PREFIX = "SYSTEM_"


def minmax(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    lo, hi = s.min(), s.max()
    if hi == lo:
        return pd.Series(0.0, index=s.index)
    return (s - lo) / (hi - lo)


def load_data():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"\n분석 원본을 찾을 수 없습니다:\n{RAW_PATH}\n"
            "data/raw/aetheria-all.json 파일을 확인해 주세요.\n"
        )

    with RAW_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    tx = pd.DataFrame(data.get("transactions", []))
    gt = pd.DataFrame(data.get("ground_truth", []))

    if tx.empty:
        raise ValueError("transactions가 비어 있습니다.")

    tx["timestamp"] = pd.to_datetime(tx["timestamp"], utc=True, errors="coerce")
    for col in ["gold_amount", "market_price", "trade_price", "quantity"]:
        if col in tx.columns:
            tx[col] = pd.to_numeric(tx[col], errors="coerce").fillna(0.0)

    p2p = tx[
        ~tx["sender_id"].fillna("").astype(str).str.startswith(SYSTEM_PREFIX)
        & ~tx["receiver_id"].fillna("").astype(str).str.startswith(SYSTEM_PREFIX)
        & tx["sender_id"].notna()
        & tx["receiver_id"].notna()
    ].copy()

    return data, tx, p2p, gt


def build_edge_table(p2p: pd.DataFrame) -> pd.DataFrame:
    edge = (
        p2p.groupby(["sender_id", "receiver_id"], as_index=False)
        .agg(
            tx_count=("transaction_id", "count"),
            total_gold=("gold_amount", "sum"),
            first_tx=("timestamp", "min"),
            last_tx=("timestamp", "max"),
        )
    )
    return edge


def build_graph(edge: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    for row in edge.itertuples(index=False):
        G.add_edge(
            row.sender_id,
            row.receiver_id,
            total_gold=float(row.total_gold),
            tx_count=int(row.tx_count),
        )
    return G


def concentration_metrics(p2p: pd.DataFrame, all_nodes: list[str]) -> pd.DataFrame:
    rows = []
    for user_id in all_nodes:
        outgoing = p2p[p2p["sender_id"] == user_id]
        incoming = p2p[p2p["receiver_id"] == user_id]

        out_total = float(outgoing["gold_amount"].sum())
        in_total = float(incoming["gold_amount"].sum())

        if out_total > 0:
            out_by_receiver = outgoing.groupby("receiver_id")["gold_amount"].sum()
            out_shares = out_by_receiver / out_total
            out_hhi = float((out_shares ** 2).sum())
            max_receiver_share = float(out_shares.max())
        else:
            out_hhi = 0.0
            max_receiver_share = 0.0

        if in_total > 0:
            in_by_sender = incoming.groupby("sender_id")["gold_amount"].sum()
            in_shares = in_by_sender / in_total
            in_hhi = float((in_shares ** 2).sum())
            max_sender_share = float(in_shares.max())
        else:
            in_hhi = 0.0
            max_sender_share = 0.0

        total_flow = out_total + in_total
        outflow_ratio = out_total / total_flow if total_flow > 0 else 0.0

        # Mule은 받은 금액과 보낸 금액이 비슷할수록 relay 성격이 강함
        if max(out_total, in_total) > 0:
            flow_balance = min(out_total, in_total) / max(out_total, in_total)
        else:
            flow_balance = 0.0

        rows.append(
            {
                "user_id": user_id,
                "gold_in": in_total,
                "gold_out": out_total,
                "unique_senders": int(incoming["sender_id"].nunique()),
                "unique_receivers": int(outgoing["receiver_id"].nunique()),
                "in_hhi": in_hhi,
                "out_hhi": out_hhi,
                "max_sender_share": max_sender_share,
                "max_receiver_share": max_receiver_share,
                "outflow_ratio": outflow_ratio,
                "flow_balance": flow_balance,
            }
        )

    return pd.DataFrame(rows).set_index("user_id")


def graph_metrics(G: nx.DiGraph, p2p: pd.DataFrame) -> pd.DataFrame:
    all_nodes = sorted(G.nodes())
    base = concentration_metrics(p2p, all_nodes)

    # edge weight가 클수록 가까운 관계가 되도록 inverse-weight distance 사용
    H = G.copy()
    for u, v, d in H.edges(data=True):
        d["distance"] = 1.0 / max(float(d.get("total_gold", 0.0)), 1.0)

    between = nx.betweenness_centrality(H, weight="distance", normalized=True)
    pagerank = nx.pagerank(G, weight="total_gold")

    base["in_degree"] = pd.Series(dict(G.in_degree()), dtype=float)
    base["out_degree"] = pd.Series(dict(G.out_degree()), dtype=float)
    base["weighted_in_gold"] = pd.Series(
        dict(G.in_degree(weight="total_gold")), dtype=float
    )
    base["weighted_out_gold"] = pd.Series(
        dict(G.out_degree(weight="total_gold")), dtype=float
    )
    base["betweenness"] = pd.Series(between, dtype=float)
    base["pagerank"] = pd.Series(pagerank, dtype=float)
    base = base.fillna(0.0)

    # Ground Truth를 전혀 사용하지 않는 role score
    in_gold_n = minmax(base["weighted_in_gold"])
    out_gold_n = minmax(base["weighted_out_gold"])
    senders_n = minmax(base["unique_senders"])
    receivers_n = minmax(base["unique_receivers"])
    between_n = minmax(base["betweenness"])

    # Farm 후보: 재화가 특정 수신자에게 몰리고, 전체 흐름 중 유출 비중이 높음
    base["farm_role_score"] = (
        0.40 * base["out_hhi"]
        + 0.30 * base["outflow_ratio"]
        + 0.20 * out_gold_n
        + 0.10 * (1.0 - receivers_n)
    ) * 100

    # Mule 후보: 여러 송신자에게 받고, 다시 특정 수신자로 넘기며, 브리지 역할
    base["mule_role_score"] = (
        0.30 * senders_n
        + 0.20 * base["out_hhi"]
        + 0.25 * base["flow_balance"]
        + 0.25 * between_n
    ) * 100

    # Hub 후보: 큰 금액을 받고 여러 계정에서 유입되며 거의 재유출하지 않음
    base["hub_role_score"] = (
        0.45 * in_gold_n
        + 0.30 * senders_n
        + 0.25 * (1.0 - base["outflow_ratio"])
    ) * 100

    base["graph_risk_score"] = base[
        ["farm_role_score", "mule_role_score", "hub_role_score"]
    ].max(axis=1)

    return base.reset_index()


def temporal_gap_minutes(
    p2p: pd.DataFrame,
    src: str,
    mid: str,
    dst: str,
) -> float | None:
    incoming = p2p[
        (p2p["sender_id"] == src)
        & (p2p["receiver_id"] == mid)
    ]["timestamp"].dropna().sort_values()

    outgoing = p2p[
        (p2p["sender_id"] == mid)
        & (p2p["receiver_id"] == dst)
    ]["timestamp"].dropna().sort_values()

    if incoming.empty or outgoing.empty:
        return None

    best = None
    for t_in in incoming:
        later = outgoing[outgoing >= t_in]
        if later.empty:
            continue
        gap = (later.iloc[0] - t_in).total_seconds() / 60.0
        if best is None or gap < best:
            best = gap

    return best


def detect_two_hop_funnels(
    edge: pd.DataFrame,
    p2p: pd.DataFrame,
    metrics: pd.DataFrame,
) -> pd.DataFrame:
    metric = metrics.set_index("user_id")
    edge_lookup = edge.set_index(["sender_id", "receiver_id"])

    max_edge_gold = max(float(edge["total_gold"].max()), 1.0)
    rows = []

    for mid in metric.index:
        incoming_sources = edge.loc[
            edge["receiver_id"] == mid, "sender_id"
        ].tolist()
        outgoing_targets = edge.loc[
            edge["sender_id"] == mid, "receiver_id"
        ].tolist()

        if not incoming_sources or not outgoing_targets:
            continue

        for src in incoming_sources:
            for dst in outgoing_targets:
                if src == dst or src == mid or dst == mid:
                    continue

                in_edge_gold = float(
                    edge_lookup.loc[(src, mid), "total_gold"]
                )
                out_edge_gold = float(
                    edge_lookup.loc[(mid, dst), "total_gold"]
                )

                src_out_hhi = float(metric.loc[src, "out_hhi"]) if src in metric.index else 0.0
                mid_mule = float(metric.loc[mid, "mule_role_score"]) / 100.0
                dst_hub = float(metric.loc[dst, "hub_role_score"]) / 100.0 if dst in metric.index else 0.0

                edge_strength = min(in_edge_gold, out_edge_gold) / max_edge_gold

                lag_min = temporal_gap_minutes(p2p, src, mid, dst)
                if lag_min is None:
                    temporal_score = 0.0
                else:
                    # 60분 이내 relay가 강한 증거가 되도록 지수 감쇠
                    temporal_score = float(np.exp(-max(lag_min, 0.0) / 60.0))

                motif_score = (
                    0.25 * src_out_hhi
                    + 0.25 * mid_mule
                    + 0.20 * dst_hub
                    + 0.15 * edge_strength
                    + 0.15 * temporal_score
                ) * 100

                rows.append(
                    {
                        "source": src,
                        "middle": mid,
                        "destination": dst,
                        "source_to_middle_gold": in_edge_gold,
                        "middle_to_destination_gold": out_edge_gold,
                        "relay_gap_minutes": lag_min,
                        "temporal_score": temporal_score,
                        "motif_score": motif_score,
                    }
                )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).sort_values(
        "motif_score", ascending=False
    ).reset_index(drop=True)


def attach_ground_truth(df: pd.DataFrame, gt: pd.DataFrame, id_col="user_id"):
    if gt.empty or "user_id" not in gt.columns or "user_type" not in gt.columns:
        return df

    mapping = gt.set_index("user_id")["user_type"]
    result = df.copy()

    if id_col == "user_id":
        result["ground_truth_type"] = result[id_col].map(mapping)
    return result


def save_graph_figure(G: nx.DiGraph, metrics: pd.DataFrame):
    if G.number_of_nodes() == 0:
        return

    # 레이아웃만 지정하고 색은 직접 지정하지 않는다.
    pos = nx.spring_layout(G, seed=42, weight="total_gold")

    widths = []
    max_gold = max(
        [d.get("total_gold", 0.0) for _, _, d in G.edges(data=True)] or [1.0]
    )
    for _, _, d in G.edges(data=True):
        widths.append(0.5 + 4.0 * d.get("total_gold", 0.0) / max_gold)

    fig, ax = plt.subplots(figsize=(12, 9))
    nx.draw_networkx_nodes(G, pos, node_size=650, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7, ax=ax)
    nx.draw_networkx_edges(
        G,
        pos,
        width=widths,
        arrows=True,
        arrowsize=12,
        alpha=0.55,
        ax=ax,
    )
    ax.set_title("Aetheria P2P Gold Transaction Network")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "transaction_network.png", dpi=170)
    plt.close(fig)


def role_hit_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    """
    평가용 Ground Truth가 붙은 경우에만 Top-N 역할 랭킹의 적중 여부를 요약.
    N은 실제 역할 계정 수를 사용하지만 점수 계산에는 Ground Truth를 쓰지 않는다.
    """
    if "ground_truth_type" not in metrics.columns:
        return pd.DataFrame()

    role_cfg = [
        ("farm", "farm_role_score"),
        ("mule", "mule_role_score"),
        ("hub", "hub_role_score"),
    ]

    rows = []
    for role, score_col in role_cfg:
        n = int((metrics["ground_truth_type"] == role).sum())
        if n == 0:
            continue

        top = metrics.nlargest(n, score_col)
        hits = int((top["ground_truth_type"] == role).sum())
        rows.append(
            {
                "role": role,
                "top_n": n,
                "hits": hits,
                "precision_at_n": hits / n,
                "recall_at_n": hits / n,
            }
        )

    return pd.DataFrame(rows)


def main():
    data, tx, p2p, gt = load_data()

    edge = build_edge_table(p2p)
    G = build_graph(edge)
    metrics = graph_metrics(G, p2p)
    metrics = attach_ground_truth(metrics, gt)

    funnels = detect_two_hop_funnels(edge, p2p, metrics)

    # funnel path의 Ground Truth는 검증 표시만 추가
    if not gt.empty and not funnels.empty:
        gt_map = gt.set_index("user_id")["user_type"]
        funnels["source_gt"] = funnels["source"].map(gt_map)
        funnels["middle_gt"] = funnels["middle"].map(gt_map)
        funnels["destination_gt"] = funnels["destination"].map(gt_map)

    role_eval = role_hit_summary(metrics)

    edge_path = OUT_DIR / "network_edges.csv"
    metrics_path = OUT_DIR / "network_account_metrics.csv"
    funnels_path = OUT_DIR / "ghost_motif_candidates_v1.csv"
    eval_path = OUT_DIR / "network_role_evaluation.csv"

    edge.to_csv(edge_path, index=False, encoding="utf-8-sig")
    metrics.sort_values(
        "graph_risk_score", ascending=False
    ).to_csv(metrics_path, index=False, encoding="utf-8-sig")
    funnels.to_csv(funnels_path, index=False, encoding="utf-8-sig")
    role_eval.to_csv(eval_path, index=False, encoding="utf-8-sig")

    save_graph_figure(G, metrics)

    print("\n" + "=" * 88)
    print(" GHOST FARM | TRANSACTION NETWORK + GHOST MOTIF V1")
    print("=" * 88)
    print(f"All transactions      : {len(tx):,}")
    print(f"P2P transactions      : {len(p2p):,}")
    print(f"Graph nodes           : {G.number_of_nodes():,}")
    print(f"Graph edges           : {G.number_of_edges():,}")
    print("Ground Truth in score : NO")

    display_cols = [
        "user_id",
        "ground_truth_type",
        "gold_in",
        "gold_out",
        "unique_senders",
        "unique_receivers",
        "out_hhi",
        "flow_balance",
        "betweenness",
        "farm_role_score",
        "mule_role_score",
        "hub_role_score",
        "graph_risk_score",
    ]
    display_cols = [c for c in display_cols if c in metrics.columns]

    print("\n[Graph Risk TOP 15]")
    print(
        metrics.sort_values("graph_risk_score", ascending=False)[display_cols]
        .head(15)
        .round(3)
        .to_string(index=False)
    )

    for role, score_col in [
        ("FARM 후보", "farm_role_score"),
        ("MULE 후보", "mule_role_score"),
        ("HUB 후보", "hub_role_score"),
    ]:
        print(f"\n[{role} TOP 10]")
        cols = ["user_id", score_col]
        if "ground_truth_type" in metrics.columns:
            cols.append("ground_truth_type")
        print(
            metrics.sort_values(score_col, ascending=False)[cols]
            .head(10)
            .round(3)
            .to_string(index=False)
        )

    print("\n[Ghost Motif 2-hop 후보 TOP 15]")
    if funnels.empty:
        print("탐지된 2-hop funnel이 없습니다.")
    else:
        print(
            funnels.head(15)
            .round(3)
            .to_string(index=False)
        )

    if not role_eval.empty:
        print("\n[역할 랭킹 평가 — Ground Truth는 평가에만 사용]")
        print(role_eval.round(3).to_string(index=False))

    print("\n[생성 파일]")
    print(f"- {edge_path}")
    print(f"- {metrics_path}")
    print(f"- {funnels_path}")
    print(f"- {eval_path}")
    print(f"- {FIG_DIR / 'transaction_network.png'}")

    print("\n해석 포인트:")
    print("1) Farm/Mule/Hub 역할 점수는 Ground Truth 없이 그래프 구조만으로 계산합니다.")
    print("2) Ground Truth는 마지막 ranking 평가 및 화면 표시 용도로만 붙입니다.")
    print("3) Ghost Motif V1은 Source → Middle → Destination 2-hop relay 구조를 찾습니다.")
    print("4) 다음 단계에서 행동 동기화 점수와 결합하면 CARS의 Graph/Sync 축이 완성됩니다.")
    print("=" * 88 + "\n")


if __name__ == "__main__":
    main()
