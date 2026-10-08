from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "data" / "analysis"
ANALYSIS.mkdir(parents=True, exist_ok=True)

V2_PATH = ANALYSIS / "cars_v2_account_scores.csv"
EDGE_PATH = ANALYSIS / "network_edges.csv"
NET_PATH = ANALYSIS / "network_account_metrics.csv"

ABUSE = {"farm", "mule", "hub"}
LEGIT = {"normal", "hardcore", "guild"}
VOL_SCALE = 200.0


def req(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"필수 파일 없음: {path}")


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def safe_num(s, index=None):
    if isinstance(s, pd.Series):
        return pd.to_numeric(s, errors="coerce").fillna(0.0)
    if index is None:
        return 0.0
    return pd.Series(float(s), index=index)


def build_edge_maps(edges: pd.DataFrame):
    e = edges.copy()
    e["sender_id"] = e["sender_id"].astype(str)
    e["receiver_id"] = e["receiver_id"].astype(str)
    e["total_gold"] = pd.to_numeric(e["total_gold"], errors="coerce").fillna(0.0)

    out_map: dict[str, pd.DataFrame] = {}
    in_map: dict[str, pd.DataFrame] = {}
    for uid, g in e.groupby("sender_id"):
        out_map[str(uid)] = g.copy()
    for uid, g in e.groupby("receiver_id"):
        in_map[str(uid)] = g.copy()
    return e, out_map, in_map


def weighted_partner_affinity(uid: str, out_map, score_lookup: dict[str, float]) -> float:
    g = out_map.get(uid)
    if g is None or g.empty:
        return 0.0
    weights = g["total_gold"].to_numpy(float)
    vals = np.array([score_lookup.get(str(x), 0.0) for x in g["receiver_id"]], dtype=float)
    if weights.sum() <= 0:
        return float(vals.mean()) if len(vals) else 0.0
    return float(np.average(vals, weights=weights))


def weighted_sender_affinity(uid: str, in_map, score_lookup: dict[str, float]) -> float:
    g = in_map.get(uid)
    if g is None or g.empty:
        return 0.0
    weights = g["total_gold"].to_numpy(float)
    vals = np.array([score_lookup.get(str(x), 0.0) for x in g["sender_id"]], dtype=float)
    if weights.sum() <= 0:
        return float(vals.mean()) if len(vals) else 0.0
    return float(np.average(vals, weights=weights))


def soft_sender_breadth(uid: str, in_map, score_lookup: dict[str, float], scale: float = 1.5) -> float:
    g = in_map.get(uid)
    if g is None or g.empty:
        return 0.0
    unique = g.groupby("sender_id", as_index=False)["total_gold"].sum()
    mass = sum(score_lookup.get(str(s), 0.0) for s in unique["sender_id"])
    return float(1.0 - math.exp(-mass / scale)) if mass > 0 else 0.0


def source_share_to_relay_set(uid: str, out_map, relay_lookup: dict[str, float]) -> float:
    """Outgoing gold share weighted by *all* relay-like receivers, not a single primary receiver."""
    return weighted_partner_affinity(uid, out_map, relay_lookup)


def enumerate_org_paths(df: pd.DataFrame, edges: pd.DataFrame):
    idx = df.set_index("user_id")
    out_groups = {str(k): g.copy() for k, g in edges.groupby("sender_id")}
    edge_lookup = {(str(r.sender_id), str(r.receiver_id)): float(r.total_gold) for r in edges.itertuples()}

    rows = []
    for middle, g_in in edges.groupby("receiver_id"):
        middle = str(middle)
        if middle not in idx.index or middle not in out_groups:
            continue
        g_out = out_groups[middle]
        if g_out.empty:
            continue

        middle_relay = float(idx.loc[middle, "relay_component_v3"]) / 100.0
        if middle_relay <= 0:
            continue

        mid_gold_out = float(g_out["total_gold"].sum())
        if mid_gold_out <= 0:
            continue

        for rin in g_in.itertuples():
            source = str(rin.sender_id)
            if source not in idx.index:
                continue
            src_gold_out = float(idx.loc[source, "edge_gold_out_v3"])
            if src_gold_out <= 0:
                continue
            src_edge_share = float(rin.total_gold) / src_gold_out
            src_score = float(idx.loc[source, "source_component_v3"]) / 100.0

            for rout in g_out.itertuples():
                dest = str(rout.receiver_id)
                if dest not in idx.index or dest == source:
                    continue
                dst_hub = float(idx.loc[dest, "hub_component_v3"]) / 100.0
                dst_share = float(rout.total_gold) / mid_gold_out

                # Geometric-style path strength: every stage must contribute.
                terms = [
                    max(src_score, 1e-9),
                    max(middle_relay, 1e-9),
                    max(dst_hub, 1e-9),
                    max(clamp01(src_edge_share), 1e-9),
                    max(clamp01(dst_share), 1e-9),
                ]
                geom = float(np.prod(terms) ** (1.0 / len(terms)))
                path_score = 100.0 * geom

                rows.append({
                    "source": source,
                    "middle": middle,
                    "destination": dest,
                    "source_to_middle_gold": float(rin.total_gold),
                    "middle_to_destination_gold": float(rout.total_gold),
                    "source_edge_share": src_edge_share,
                    "middle_out_share": dst_share,
                    "source_component_v3": 100.0 * src_score,
                    "relay_component_v3": 100.0 * middle_relay,
                    "hub_component_v3": 100.0 * dst_hub,
                    "organization_path_score": path_score,
                })

    if not rows:
        return pd.DataFrame(columns=[
            "source", "middle", "destination", "source_to_middle_gold",
            "middle_to_destination_gold", "source_edge_share", "middle_out_share",
            "source_component_v3", "relay_component_v3", "hub_component_v3",
            "organization_path_score"
        ])
    return pd.DataFrame(rows).sort_values("organization_path_score", ascending=False)


def attach_org_support(df: pd.DataFrame, paths: pd.DataFrame) -> pd.DataFrame:
    support = {uid: 0.0 for uid in df["user_id"].astype(str)}
    if not paths.empty:
        for r in paths.itertuples():
            score = float(r.organization_path_score)
            support[str(r.source)] = max(support.get(str(r.source), 0.0), score)
            support[str(r.middle)] = max(support.get(str(r.middle), 0.0), score)
            support[str(r.destination)] = max(support.get(str(r.destination), 0.0), score)
    out = df.copy()
    out["organization_support_v3"] = out["user_id"].astype(str).map(support).fillna(0.0)
    return out


def evaluate(df: pd.DataFrame):
    e = df[df["ground_truth_type"].isin(ABUSE | LEGIT)].copy()
    e["y_true"] = e["ground_truth_type"].isin(ABUSE).astype(int)
    k = int(e["y_true"].sum())
    e = e.sort_values("cars_v3_score", ascending=False).reset_index(drop=True)
    e["y_pred"] = 0
    if k:
        e.loc[:k-1, "y_pred"] = 1

    tp = int(((e.y_true == 1) & (e.y_pred == 1)).sum())
    fp = int(((e.y_true == 0) & (e.y_pred == 1)).sum())
    fn = int(((e.y_true == 1) & (e.y_pred == 0)).sum())
    tn = int(((e.y_true == 0) & (e.y_pred == 0)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return e, {
        "eval_accounts": len(e),
        "positive_accounts": k,
        "precision_at_k": p,
        "recall_at_k": r,
        "f1_at_k": f1,
        "tn": tn, "fp": fp, "fn": fn, "tp": tp,
    }


def main():
    for p in [V2_PATH, EDGE_PATH, NET_PATH]:
        req(p)

    v2 = pd.read_csv(V2_PATH)
    net = pd.read_csv(NET_PATH).drop(columns=["ground_truth_type"], errors="ignore")
    edges = pd.read_csv(EDGE_PATH)
    edges, out_map, in_map = build_edge_maps(edges)

    # V2 score file is the frozen account-level detector. V3 adds organization structure.
    df = v2.merge(net, on="user_id", how="left", suffixes=("", "_net"))
    df["user_id"] = df["user_id"].astype(str)

    # Basic graph quantities from the current snapshot.
    gold_out = edges.groupby("sender_id")["total_gold"].sum().to_dict()
    gold_in = edges.groupby("receiver_id")["total_gold"].sum().to_dict()
    out_cnt = edges.groupby("sender_id")["receiver_id"].nunique().to_dict()
    in_cnt = edges.groupby("receiver_id")["sender_id"].nunique().to_dict()

    df["edge_gold_out_v3"] = df["user_id"].map(gold_out).fillna(0.0)
    df["edge_gold_in_v3"] = df["user_id"].map(gold_in).fillna(0.0)
    df["out_partner_count_v3"] = df["user_id"].map(out_cnt).fillna(0).astype(int)
    df["in_partner_count_v3"] = df["user_id"].map(in_cnt).fillna(0).astype(int)

    total = df["edge_gold_out_v3"] + df["edge_gold_in_v3"]
    df["volume_confidence_v3"] = 1 - np.exp(-total / VOL_SCALE)
    df["incoming_ratio_v3"] = (df["edge_gold_in_v3"] / total.replace(0, np.nan)).fillna(0.0)
    df["outgoing_ratio_v3"] = (df["edge_gold_out_v3"] / total.replace(0, np.nan)).fillna(0.0)
    df["in_breadth_v3"] = 1 - np.exp(-df["in_partner_count_v3"] / 3.0)
    df["out_breadth_v3"] = 1 - np.exp(-df["out_partner_count_v3"] / 3.0)

    # Existing network metrics are still useful, but they are only graph-derived.
    flow_balance = safe_num(df.get("flow_balance", pd.Series(0.0, index=df.index))).clip(0, 1)
    out_hhi = safe_num(df.get("out_hhi", pd.Series(0.0, index=df.index))).clip(0, 1)
    out_concentration = np.sqrt(out_hhi)

    # STEP 1 — Collector seed: receives much more than it sends and has multiple senders.
    df["hub_seed_v3"] = (
        df["incoming_ratio_v3"]
        * df["in_breadth_v3"]
        * df["volume_confidence_v3"]
    ).clip(0, 1)
    hub_seed_lookup = dict(zip(df["user_id"], df["hub_seed_v3"]))

    # STEP 2 — Relay seed: receives from several accounts and forwards value toward collector-like nodes.
    downstream_hub_seed = []
    for uid in df["user_id"]:
        downstream_hub_seed.append(weighted_partner_affinity(uid, out_map, hub_seed_lookup))
    df["downstream_hub_affinity_seed_v3"] = downstream_hub_seed

    relay_seed = (
        df["in_breadth_v3"]
        * flow_balance
        * df["volume_confidence_v3"]
        * (0.30 * out_concentration + 0.70 * df["downstream_hub_affinity_seed_v3"])
    ).clip(0, 1)
    df["relay_seed_v3"] = relay_seed
    relay_seed_lookup = dict(zip(df["user_id"], df["relay_seed_v3"]))

    # STEP 3 — Refine collector evidence using incoming money from relay-like accounts.
    relay_in_share = []
    relay_sender_breadth = []
    for uid in df["user_id"]:
        relay_in_share.append(weighted_sender_affinity(uid, in_map, relay_seed_lookup))
        relay_sender_breadth.append(soft_sender_breadth(uid, in_map, relay_seed_lookup))
    df["relay_in_share_v3"] = relay_in_share
    df["relay_sender_breadth_v3"] = relay_sender_breadth

    hub_score = (
        df["incoming_ratio_v3"]
        * df["volume_confidence_v3"]
        * (
            0.25 * df["in_breadth_v3"]
            + 0.50 * df["relay_in_share_v3"]
            + 0.25 * df["relay_sender_breadth_v3"]
        )
    ).clip(0, 1)
    df["hub_component_v3"] = 100.0 * hub_score
    hub_lookup = dict(zip(df["user_id"], hub_score))

    # STEP 4 — Recompute relay score against the refined collector evidence.
    downstream_hub = []
    for uid in df["user_id"]:
        downstream_hub.append(weighted_partner_affinity(uid, out_map, hub_lookup))
    df["downstream_hub_affinity_v3"] = downstream_hub

    relay_score = (
        df["in_breadth_v3"]
        * flow_balance
        * df["volume_confidence_v3"]
        * (0.20 * out_concentration + 0.80 * df["downstream_hub_affinity_v3"])
    ).clip(0, 1)
    df["relay_component_v3"] = 100.0 * relay_score
    relay_lookup = dict(zip(df["user_id"], relay_score))

    # STEP 5 — Source/Farm: fraction of outgoing value aimed at the whole relay set.
    relay_set_share = []
    for uid in df["user_id"]:
        relay_set_share.append(source_share_to_relay_set(uid, out_map, relay_lookup))
    df["relay_set_share_v3"] = relay_set_share

    source_score = (
        df["relay_set_share_v3"]
        * (
            0.45
            + 0.30 * df["outgoing_ratio_v3"]
            + 0.25 * df["volume_confidence_v3"]
        )
    ).clip(0, 1)
    df["source_component_v3"] = 100.0 * source_score

    # STEP 6 — Explicit organization paths: Source -> Relay -> Collector.
    paths = enumerate_org_paths(df, edges)
    df = attach_org_support(df, paths)

    # STEP 7 — Role-preserving final risk. A strong Hub should not be diluted by low Farm/Mule scores.
    v2_score = safe_num(df["cars_v2_score"]).clip(0, 100)
    org = safe_num(df["organization_support_v3"]).clip(0, 100)
    source = safe_num(df["source_component_v3"]).clip(0, 100)
    relay = safe_num(df["relay_component_v3"]).clip(0, 100)
    hub = safe_num(df["hub_component_v3"]).clip(0, 100)

    account_branch = 0.70 * v2_score + 0.30 * org
    source_branch = 0.80 * source + 0.20 * org
    relay_branch = 0.80 * relay + 0.20 * org
    hub_branch = 0.88 * hub + 0.12 * org

    df["cars_v3_score"] = np.maximum.reduce([
        account_branch.to_numpy(),
        source_branch.to_numpy(),
        relay_branch.to_numpy(),
        hub_branch.to_numpy(),
    ])
    df["cars_v3_score"] = np.clip(df["cars_v3_score"], 0, 100).round(3)
    df["cars_v3_rank"] = df["cars_v3_score"].rank(method="first", ascending=False).astype(int)

    ev, metrics = evaluate(df)
    fp = ev[(ev.y_pred == 1) & ev.ground_truth_type.isin(LEGIT)]
    fn = ev[(ev.y_pred == 0) & ev.ground_truth_type.isin(ABUSE)]

    score_cols = [
        "user_id", "ground_truth_type", "cars_v2_score", "cars_v3_score", "cars_v3_rank",
        "source_component_v3", "relay_component_v3", "hub_component_v3",
        "organization_support_v3", "relay_set_share_v3", "relay_in_share_v3",
        "downstream_hub_affinity_v3", "incoming_ratio_v3", "outgoing_ratio_v3",
        "in_partner_count_v3", "out_partner_count_v3", "volume_confidence_v3",
    ]

    df.sort_values("cars_v3_score", ascending=False)[score_cols].to_csv(
        ANALYSIS / "cars_v3_account_scores.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([metrics]).to_csv(
        ANALYSIS / "cars_v3_metrics.csv", index=False, encoding="utf-8-sig"
    )
    fp[score_cols].to_csv(
        ANALYSIS / "cars_v3_false_positives.csv", index=False, encoding="utf-8-sig"
    )
    fn[score_cols].to_csv(
        ANALYSIS / "cars_v3_false_negatives.csv", index=False, encoding="utf-8-sig"
    )
    paths.to_csv(
        ANALYSIS / "cars_v3_organization_paths.csv", index=False, encoding="utf-8-sig"
    )

    print("\n" + "=" * 104)
    print("GHOST FARM | CARS V3 — ORGANIZATION FLOW DETECTOR")
    print("=" * 104)
    print("Ground Truth in score : NO")
    print("개발 근거             : CARS V2 red-team 실패 분석 (mule_split / composite / persistent hub FN)")
    print("\n[V3 핵심 변경]")
    print("1) Primary receiver 1명 대신 Relay 집합 전체로 흐른 재화 비율을 계산")
    print("2) Source -> Relay -> Collector 구조를 graph message passing 방식으로 전파")
    print("3) Hub/Collector 역할 점수는 다른 역할 점수에 희석되지 않도록 별도 branch 유지")
    print("4) V2 account risk는 보존하고 Organization support를 추가")

    print("\n[조직형 작업장 평가]")
    print(f"Evaluation accounts : {metrics['eval_accounts']}")
    print(f"Positive accounts   : {metrics['positive_accounts']}")
    print(f"Precision@K         : {metrics['precision_at_k']:.3f}")
    print(f"Recall@K            : {metrics['recall_at_k']:.3f}")
    print(f"F1@K                : {metrics['f1_at_k']:.3f}")
    print(f"Confusion Matrix    : TN={metrics['tn']} / FP={metrics['fp']} / FN={metrics['fn']} / TP={metrics['tp']}")

    print("\n[CARS V3 TOP 20]")
    print(df.sort_values("cars_v3_score", ascending=False)[score_cols].head(20).round(3).to_string(index=False))

    print("\n[Organization Path TOP 15]")
    if paths.empty:
        print("없음")
    else:
        print(paths.head(15).round(3).to_string(index=False))

    print("\n[False Positive]")
    print("없음" if fp.empty else fp[["user_id", "ground_truth_type", "cars_v3_score"]].to_string(index=False))
    print("\n[False Negative]")
    print("없음" if fn.empty else fn[["user_id", "ground_truth_type", "cars_v3_score"]].to_string(index=False))

    print("\n[생성 파일]")
    for name in [
        "cars_v3_account_scores.csv", "cars_v3_metrics.csv",
        "cars_v3_false_positives.csv", "cars_v3_false_negatives.csv",
        "cars_v3_organization_paths.csv",
    ]:
        print(ANALYSIS / name)

    print("\n주의: V3는 V2 red-team 결과를 보고 개발한 버전입니다.")
    print("따라서 기존 red-team/unseen_02 성능은 개발 성능이며, 최종 일반화 평가는 새로운 unseen_03에서 코드 수정 없이 수행해야 합니다.")
    print("=" * 104 + "\n")


if __name__ == "__main__":
    main()
