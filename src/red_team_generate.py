from __future__ import annotations

import argparse
import copy
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SEED = 20261007
ABUSE_TYPES = {"farm", "mule", "hub"}
SAFE_TYPES = {"normal", "hardcore", "guild"}


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def gt_map(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    gt = data.get("ground_truth", [])
    if isinstance(gt, dict):
        for k, v in gt.items():
            if isinstance(v, dict):
                out[str(k)] = str(v.get("user_type") or v.get("type") or v.get("ground_truth_type") or "")
            else:
                out[str(k)] = str(v)
        return out

    for row in gt:
        if not isinstance(row, dict):
            continue
        uid = row.get("user_id") or row.get("id")
        typ = row.get("user_type") or row.get("type") or row.get("ground_truth_type")
        if uid and typ:
            out[str(uid)] = str(typ)
    return out


def tx_is_p2p(tx: dict[str, Any]) -> bool:
    return bool(tx.get("sender_id") and tx.get("receiver_id") and float(tx.get("gold_amount") or 0) > 0)


def suspicious_tx(tx: dict[str, Any], gtm: dict[str, str]) -> bool:
    s = gtm.get(str(tx.get("sender_id")), "")
    r = gtm.get(str(tx.get("receiver_id")), "")
    return s in ABUSE_TYPES or r in ABUSE_TYPES


def clone_tx(tx: dict[str, Any], suffix: str, timestamp: str | None = None, amount: float | None = None) -> dict[str, Any]:
    out = copy.deepcopy(tx)
    tid = str(out.get("transaction_id") or f"RT_{random.randrange(10**12)}")
    out["transaction_id"] = f"{tid}_{suffix}"
    if timestamp is not None:
        out["timestamp"] = timestamp
    if amount is not None:
        out["gold_amount"] = round(float(amount), 3)
    meta = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
    meta = copy.deepcopy(meta)
    meta["red_team_generated"] = True
    meta["red_team_variant"] = suffix
    out["metadata"] = meta
    return out


def scenario_time_jitter(base: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    d = copy.deepcopy(base)
    gtm = gt_map(d)
    changed = 0
    for tx in d.get("transactions", []):
        if tx_is_p2p(tx) and suspicious_tx(tx, gtm) and tx.get("timestamp"):
            tx["timestamp"] = fmt_ts(parse_ts(tx["timestamp"]) + timedelta(minutes=rng.uniform(-90, 90)))
            changed += 1
    d.setdefault("red_team", {})["time_jitter"] = {"changed_transactions": changed, "max_abs_minutes": 90}
    return d


def scenario_mule_split(base: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    d = copy.deepcopy(base)
    gtm = gt_map(d)
    mules = sorted([u for u, t in gtm.items() if t == "mule"])
    changed = 0
    if len(mules) >= 2:
        for tx in d.get("transactions", []):
            s = str(tx.get("sender_id"))
            r = str(tx.get("receiver_id"))
            if gtm.get(s) == "farm" and gtm.get(r) == "mule" and rng.random() < 0.65:
                alternatives = [m for m in mules if m != r]
                if alternatives:
                    tx["receiver_id"] = rng.choice(alternatives)
                    changed += 1
    d.setdefault("red_team", {})["mule_split"] = {"rerouted_farm_transfers": changed, "mules": mules}
    return d


def scenario_micro_tx(base: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    d = copy.deepcopy(base)
    gtm = gt_map(d)
    new_txs = []
    split_originals = 0
    for tx in d.get("transactions", []):
        s = str(tx.get("sender_id"))
        r = str(tx.get("receiver_id"))
        amt = float(tx.get("gold_amount") or 0)
        chain = (
            (gtm.get(s) == "farm" and gtm.get(r) == "mule")
            or (gtm.get(s) == "mule" and gtm.get(r) == "hub")
        )
        if chain and amt >= 80 and tx.get("timestamp"):
            n = rng.randint(3, 6)
            weights = [rng.random() + 0.3 for _ in range(n)]
            total = sum(weights)
            parts = [amt * w / total for w in weights]
            t0 = parse_ts(tx["timestamp"])
            for i, part in enumerate(parts, 1):
                new_txs.append(clone_tx(
                    tx,
                    f"micro{i}",
                    timestamp=fmt_ts(t0 + timedelta(minutes=rng.uniform(0, 35))),
                    amount=part,
                ))
            split_originals += 1
        else:
            new_txs.append(tx)
    d["transactions"] = new_txs
    d.setdefault("red_team", {})["micro_tx"] = {
        "split_original_transactions": split_originals,
        "result_transactions": len(new_txs),
    }
    return d


def scenario_normal_mix(base: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    d = copy.deepcopy(base)
    gtm = gt_map(d)
    normals = [u for u, t in gtm.items() if t in SAFE_TYPES]
    abusers = [u for u, t in gtm.items() if t in {"farm", "mule"}]
    txs = d.get("transactions", [])
    p2p_times = [parse_ts(t["timestamp"]) for t in txs if tx_is_p2p(t) and t.get("timestamp")]
    if p2p_times:
        lo, hi = min(p2p_times), max(p2p_times)
    else:
        now = datetime.now(timezone.utc)
        lo, hi = now, now + timedelta(hours=1)

    template = next((t for t in txs if tx_is_p2p(t)), None)
    injected = 0
    if template and normals and abusers:
        for uid in abusers:
            for j in range(rng.randint(2, 4)):
                other = rng.choice(normals)
                sender, receiver = (uid, other) if rng.random() < 0.55 else (other, uid)
                t = copy.deepcopy(template)
                t["transaction_id"] = f"RT_MIX_{uid}_{j}_{rng.randrange(10**8)}"
                t["sender_id"] = sender
                t["receiver_id"] = receiver
                t["gold_amount"] = rng.randint(8, 75)
                span = max((hi - lo).total_seconds(), 1)
                t["timestamp"] = fmt_ts(lo + timedelta(seconds=rng.uniform(0, span)))
                t["transaction_type"] = "trade_gold"
                t["item_id"] = None
                t["quantity"] = 0
                t["market_price"] = 0
                t["trade_price"] = 0
                meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
                meta = copy.deepcopy(meta)
                meta["red_team_generated"] = True
                meta["red_team_variant"] = "normal_mix"
                t["metadata"] = meta
                txs.append(t)
                injected += 1

    d.setdefault("red_team", {})["normal_mix"] = {"injected_transactions": injected}
    return d


def scenario_behavior_noise(base: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    d = copy.deepcopy(base)
    gtm = gt_map(d)
    changed = 0
    for ev in d.get("events", []):
        uid = str(ev.get("user_id"))
        if gtm.get(uid) in ABUSE_TYPES and rng.random() < 0.30:
            if ev.get("timestamp"):
                ev["timestamp"] = fmt_ts(parse_ts(ev["timestamp"]) + timedelta(minutes=rng.uniform(-25, 25)))
            if isinstance(ev.get("x"), (int, float)):
                ev["x"] = round(float(ev["x"]) + rng.uniform(-3.0, 3.0), 3)
            if isinstance(ev.get("y"), (int, float)):
                ev["y"] = round(float(ev["y"]) + rng.uniform(-3.0, 3.0), 3)
            changed += 1
    d.setdefault("red_team", {})["behavior_noise"] = {
        "changed_events": changed,
        "fraction_target": 0.30,
        "max_abs_minutes": 25,
    }
    return d


def scenario_composite(base: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    d = scenario_time_jitter(base, rng)
    d = scenario_mule_split(d, rng)
    d = scenario_micro_tx(d, rng)
    d = scenario_normal_mix(d, rng)
    d = scenario_behavior_noise(d, rng)
    d.setdefault("red_team", {})["composite"] = True
    return d


SCENARIOS = {
    "time_jitter": scenario_time_jitter,
    "mule_split": scenario_mule_split,
    "micro_tx": scenario_micro_tx,
    "normal_mix": scenario_normal_mix,
    "behavior_noise": scenario_behavior_noise,
    "composite": scenario_composite,
}


def main():
    p = argparse.ArgumentParser(description="Generate GHOST FARM Red-Team snapshots")
    p.add_argument("--input", required=True)
    p.add_argument("--outdir", default="data/redteam")
    p.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args()

    src = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    with src.open("r", encoding="utf-8") as f:
        base = json.load(f)

    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    manifest = {
        "source": str(src),
        "seed": args.seed,
        "note": "Ground truth is allowed only to construct attacks. Detector scoring must remain ground-truth-free.",
        "files": [],
    }

    for i, name in enumerate(selected):
        rng = random.Random(args.seed + i * 1009)
        attacked = SCENARIOS[name](base, rng)
        attacked.setdefault("red_team", {})["scenario"] = name
        attacked["red_team"]["source_file"] = src.name
        attacked["red_team"]["seed"] = args.seed + i * 1009
        dst = outdir / f"aetheria-redteam-{name}.json"
        with dst.open("w", encoding="utf-8") as f:
            json.dump(attacked, f, ensure_ascii=False, indent=2)
        manifest["files"].append({
            "scenario": name,
            "path": str(dst),
            "events": len(attacked.get("events", [])),
            "transactions": len(attacked.get("transactions", [])),
            "sessions": len(attacked.get("sessions", [])),
            "details": attacked.get("red_team", {}),
        })
        print(f"[OK] {name:15s} -> {dst}")

    manifest_path = outdir / "redteam_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nManifest -> {manifest_path}")


if __name__ == "__main__":
    main()
