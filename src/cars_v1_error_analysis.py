from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "data" / "validation" / "unseen_01"
A = VAL / "analysis"
P = VAL / "processed"
OUT = ROOT / "data" / "analysis"
OUT.mkdir(parents=True, exist_ok=True)

cars = pd.read_csv(A / "cars_v1_account_scores.csv")
net = pd.read_csv(A / "network_account_metrics.csv")
edges = pd.read_csv(A / "network_edges.csv")
sync = pd.read_csv(A / "behavior_pair_sync.csv")
feat = pd.read_csv(P / "account_features_v1.csv")

targets = ["SYN_U011", "SYN_U012", "SYN_U028", "SYN_U029"]

lookup = {}
for _, r in sync.iterrows():
    lookup[tuple(sorted((str(r.user_a), str(r.user_b))))] = float(r.sync_score)

rows = []
for uid in targets:
    c = cars[cars.user_id == uid].iloc[0].to_dict()
    ndf = net[net.user_id == uid]
    fdf = feat[feat.user_id == uid]
    if not ndf.empty:
        c.update({k:v for k,v in ndf.iloc[0].to_dict().items() if k not in c})
    if not fdf.empty:
        c.update({k:v for k,v in fdf.iloc[0].to_dict().items() if k not in c})

    rel = edges[(edges.sender_id.astype(str)==uid) | (edges.receiver_id.astype(str)==uid)].copy()
    out = rel[rel.sender_id.astype(str)==uid]
    inc = rel[rel.receiver_id.astype(str)==uid]

    out_total = float(out.total_gold.sum()) if len(out) else 0.0
    in_total = float(inc.total_gold.sum()) if len(inc) else 0.0
    largest_out = float(out.total_gold.max()) if len(out) else 0.0
    largest_in = float(inc.total_gold.max()) if len(inc) else 0.0

    ps = []
    for _, r in rel.iterrows():
        a, b = str(r.sender_id), str(r.receiver_id)
        partner = b if a == uid else a
        ps.append(lookup.get(tuple(sorted((uid, partner))), 0.0))

    c.update({
        "out_partner_count": int(out.receiver_id.nunique()) if len(out) else 0,
        "in_partner_count": int(inc.sender_id.nunique()) if len(inc) else 0,
        "out_total_gold": out_total,
        "in_total_gold": in_total,
        "out_top_share": largest_out/out_total if out_total else 0.0,
        "in_top_share": largest_in/in_total if in_total else 0.0,
        "mean_partner_sync": float(np.mean(ps)) if ps else 0.0,
        "max_partner_sync": float(np.max(ps)) if ps else 0.0,
    })
    rows.append(c)

detail = pd.DataFrame(rows)

cols = [
    "user_id","ground_truth_type","cars_score","cars_rank",
    "graph_flow_score","motif_component","sync_funnel_score",
    "economic_score","repetition_score","p2p_volume","volume_confidence",
    "tx_partner_sync","gold_in","gold_out","unique_senders","unique_receivers",
    "in_hhi","out_hhi","flow_balance","betweenness",
    "farm_role_score","mule_role_score","hub_role_score",
    "out_partner_count","in_partner_count","out_total_gold","in_total_gold",
    "out_top_share","in_top_share","mean_partner_sync","max_partner_sync",
    "action_entropy","event_count"
]
cols = [c for c in cols if c in detail.columns]
detail = detail[cols]

metrics = ["graph_flow_score","motif_component","sync_funnel_score","economic_score","repetition_score","cars_score"]
pct_rows = []
for uid in detail.user_id:
    r = detail[detail.user_id==uid].iloc[0]
    for m in metrics:
        if m in cars.columns:
            pct_rows.append({
                "user_id":uid,
                "metric":m,
                "value":float(r[m]),
                "percentile_all_accounts":float((cars[m] <= float(r[m])).mean()*100)
            })
pct = pd.DataFrame(pct_rows)

detail.to_csv(OUT / "cars_v1_error_detail.csv", index=False, encoding="utf-8-sig")
pct.to_csv(OUT / "cars_v1_error_percentiles.csv", index=False, encoding="utf-8-sig")

print("\n" + "="*90)
print("GHOST FARM | CARS V1 ERROR ANALYSIS")
print("="*90)
print(detail.round(3).to_string(index=False))

print("\n[Percentile]")
print(pct.pivot(index="user_id", columns="metric", values="percentile_all_accounts").round(1).to_string())

for uid in targets:
    rel = edges[(edges.sender_id.astype(str)==uid) | (edges.receiver_id.astype(str)==uid)].copy()
    if rel.empty:
        continue
    rel["direction"] = np.where(rel.sender_id.astype(str)==uid, "OUT", "IN")
    rel["partner"] = np.where(rel.sender_id.astype(str)==uid, rel.receiver_id, rel.sender_id)
    print(f"\n[{uid} TOP 거래]")
    print(rel.sort_values("total_gold", ascending=False)[["direction","partner","tx_count","total_gold"]].head(10).to_string(index=False))

print("\n생성:")
print(OUT / "cars_v1_error_detail.csv")
print(OUT / "cars_v1_error_percentiles.csv")
print("="*90)
