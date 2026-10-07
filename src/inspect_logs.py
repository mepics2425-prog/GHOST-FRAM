from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "aetheria-all.json"
OUT_DIR = PROJECT_ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_div(a, b):
    a = pd.Series(a, dtype="float64")
    b = pd.Series(b, dtype="float64")
    return np.where(b != 0, a / b, 0.0)


def load_snapshot():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"\n분석 원본을 찾을 수 없습니다.\n"
            f"다음 위치에 JSON 파일을 넣어주세요:\n{RAW_PATH}\n"
        )

    with RAW_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    events = pd.DataFrame(data.get("events", []))
    tx = pd.DataFrame(data.get("transactions", []))
    sessions = pd.DataFrame(data.get("sessions", []))
    ground_truth = pd.DataFrame(data.get("ground_truth", []))
    users = pd.DataFrame(data.get("users", []))
    characters = pd.DataFrame(data.get("characters", []))

    return data, events, tx, sessions, ground_truth, users, characters


def normalize(events, tx, sessions):
    if not events.empty:
        events["timestamp"] = pd.to_datetime(
            events["timestamp"], utc=True, errors="coerce"
        )
        for col in ["quantity", "gold_delta", "x", "y"]:
            if col in events.columns:
                events[col] = pd.to_numeric(events[col], errors="coerce").fillna(0)

    if not tx.empty:
        tx["timestamp"] = pd.to_datetime(
            tx["timestamp"], utc=True, errors="coerce"
        )
        for col in ["gold_amount", "quantity", "market_price", "trade_price"]:
            if col in tx.columns:
                tx[col] = pd.to_numeric(tx[col], errors="coerce").fillna(0)

    if not sessions.empty:
        sessions["login_at"] = pd.to_datetime(
            sessions["login_at"], utc=True, errors="coerce"
        )
        sessions["logout_at"] = pd.to_datetime(
            sessions["logout_at"], utc=True, errors="coerce"
        )
        sessions["play_time"] = pd.to_numeric(
            sessions["play_time"], errors="coerce"
        ).fillna(0)

    return events, tx, sessions


def build_event_features(events):
    if events.empty:
        return pd.DataFrame()

    event_counts = (
        events.groupby(["user_id", "action_type"])
        .size()
        .unstack(fill_value=0)
        .add_prefix("event_")
    )

    base = events.groupby("user_id").agg(
        event_count=("event_id", "count"),
        action_diversity=("action_type", "nunique"),
        map_diversity=("map_id", lambda x: x.dropna().nunique()),
        active_first=("timestamp", "min"),
        active_last=("timestamp", "max"),
        positive_gold_delta=("gold_delta", lambda x: x[x > 0].sum()),
        negative_gold_delta=("gold_delta", lambda x: -x[x < 0].sum()),
    )

    base["active_minutes"] = (
        (base["active_last"] - base["active_first"]).dt.total_seconds() / 60
    ).fillna(0)

    # 행동 엔트로피: 한 행동만 반복할수록 낮고, 다양한 행동을 섞을수록 높음
    action_entropy = {}
    for user_id, group in events.groupby("user_id"):
        p = group["action_type"].value_counts(normalize=True)
        action_entropy[user_id] = float(-(p * np.log2(p)).sum())

    base["action_entropy"] = pd.Series(action_entropy)
    base = base.join(event_counts, how="left")

    return base


def build_session_features(sessions):
    if sessions.empty:
        return pd.DataFrame()

    result = sessions.groupby("user_id").agg(
        session_count=("session_id", "count"),
        total_play_time_sec=("play_time", "sum"),
        avg_play_time_sec=("play_time", "mean"),
        max_play_time_sec=("play_time", "max"),
        device_group_count=("device_group", "nunique"),
        ip_group_count=("ip_group", "nunique"),
        first_login=("login_at", "min"),
        last_login=("login_at", "max"),
    )

    return result


def build_transaction_features(tx):
    if tx.empty:
        return pd.DataFrame(), pd.DataFrame()

    # SYSTEM_SHOP이 낀 상점 거래와 P2P 거래를 분리
    p2p = tx[
        tx["sender_id"].fillna("").ne("SYSTEM_SHOP")
        & tx["receiver_id"].fillna("").ne("SYSTEM_SHOP")
    ].copy()

    send = p2p.groupby("sender_id").agg(
        tx_sent_count=("transaction_id", "count"),
        gold_sent=("gold_amount", "sum"),
        unique_receivers=("receiver_id", "nunique"),
    )

    recv = p2p.groupby("receiver_id").agg(
        tx_received_count=("transaction_id", "count"),
        gold_received=("gold_amount", "sum"),
        unique_senders=("sender_id", "nunique"),
    )

    # 특정 상대에게 송금이 얼마나 몰리는지
    sent_by_receiver = (
        p2p.groupby(["sender_id", "receiver_id"])["gold_amount"]
        .sum()
        .reset_index()
    )

    concentration_rows = []
    for sender, group in sent_by_receiver.groupby("sender_id"):
        total = group["gold_amount"].sum()
        max_to_one = group["gold_amount"].max() if len(group) else 0
        concentration_rows.append(
            {
                "user_id": sender,
                "max_receiver_share": max_to_one / total if total > 0 else 0,
                "largest_receiver_gold": max_to_one,
            }
        )

    concentration = (
        pd.DataFrame(concentration_rows).set_index("user_id")
        if concentration_rows
        else pd.DataFrame()
    )

    # 거래소 가격 괴리율
    market = tx[
        (tx["transaction_type"] == "market_trade")
        & (tx["market_price"] > 0)
    ].copy()

    if not market.empty:
        market["price_deviation"] = (
            (market["trade_price"] - market["market_price"]).abs()
            / market["market_price"]
        )
        market["trade_to_market_ratio"] = (
            market["trade_price"] / market["market_price"]
        )

        price_send = market.groupby("sender_id").agg(
            market_trade_count=("transaction_id", "count"),
            avg_price_deviation=("price_deviation", "mean"),
            max_price_deviation=("price_deviation", "max"),
            suspicious_price_trade_count=(
                "price_deviation",
                lambda x: int((x >= 0.50).sum()),
            ),
        )
    else:
        price_send = pd.DataFrame()

    ids = sorted(
        set(p2p["sender_id"].dropna())
        | set(p2p["receiver_id"].dropna())
        | set(tx["sender_id"].dropna())
        | set(tx["receiver_id"].dropna())
    )

    features = pd.DataFrame(index=ids)
    features.index.name = "user_id"
    for frame in [send, recv, concentration, price_send]:
        if not frame.empty:
            features = features.join(frame, how="left")

    numeric_cols = features.select_dtypes(include="number").columns
    features[numeric_cols] = features[numeric_cols].fillna(0)

    features["net_gold_flow"] = (
        features.get("gold_received", 0) - features.get("gold_sent", 0)
    )

    if "max_receiver_share" not in features:
        features["max_receiver_share"] = 0.0

    # 비정상 가격 거래 원본도 별도 저장
    if not market.empty:
        suspicious = market[market["price_deviation"] >= 0.50].copy()
        suspicious = suspicious.sort_values(
            "price_deviation", ascending=False
        )
    else:
        suspicious = market

    return features, suspicious


def main():
    data, events, tx, sessions, gt, users, characters = load_snapshot()
    events, tx, sessions = normalize(events, tx, sessions)

    print("\n" + "=" * 68)
    print(" GHOST FARM | AETHERIA LOG INSPECTION")
    print("=" * 68)
    print(f"Export 시각       : {data.get('exported_at')}")
    print(f"World 시각        : {data.get('world_time')}")
    print(f"Clock scale       : {data.get('clock_scale')}")
    print(f"Events            : {len(events):,}")
    print(f"Transactions      : {len(tx):,}")
    print(f"Sessions          : {len(sessions):,}")
    print(f"Ground truth      : {len(gt):,}")
    print(f"Real users        : {len(users):,}")
    print(f"Real characters   : {len(characters):,}")

    if not gt.empty:
        print("\n[Ground Truth 유형 분포 — 모델 입력에는 사용하지 않음]")
        print(gt["user_type"].value_counts().to_string())

    if not events.empty:
        print("\n[행동 유형 TOP 20]")
        print(events["action_type"].value_counts().head(20).to_string())

    event_f = build_event_features(events)
    session_f = build_session_features(sessions)
    tx_f, suspicious_tx = build_transaction_features(tx)

    # 모든 관측 계정을 합침
    observed_ids = set()
    for df, col in [
        (events, "user_id"),
        (sessions, "user_id"),
        (tx, "sender_id"),
        (tx, "receiver_id"),
    ]:
        if not df.empty and col in df:
            observed_ids.update(df[col].dropna().astype(str))

    observed_ids.discard("SYSTEM_SHOP")

    features = pd.DataFrame(index=sorted(observed_ids))
    features.index.name = "user_id"

    for frame in [event_f, session_f, tx_f]:
        if not frame.empty:
            features = features.join(frame, how="left")

    # Ground truth는 평가용 컬럼으로만 마지막에 붙인다.
    if not gt.empty:
        gt_cols = gt[["user_id", "user_type", "device_group", "ip_group"]].copy()
        gt_cols = gt_cols.rename(columns={"user_type": "ground_truth_type"})
        features = features.reset_index().merge(
            gt_cols, on="user_id", how="left"
        ).set_index("user_id")
    else:
        features["ground_truth_type"] = np.nan

    # 결측치 처리
    numeric_cols = features.select_dtypes(include="number").columns
    features[numeric_cols] = features[numeric_cols].fillna(0)

    # 분석 편의를 위한 비율형 특징
    if {"gold_sent", "gold_received"}.issubset(features.columns):
        denom = features["gold_sent"] + features["gold_received"]
        features["outflow_ratio"] = safe_div(features["gold_sent"], denom)

    # 저장
    features.to_csv(
        OUT_DIR / "account_features_v1.csv",
        encoding="utf-8-sig"
    )

    if not events.empty:
        events["action_type"].value_counts().rename_axis(
            "action_type"
        ).reset_index(name="count").to_csv(
            OUT_DIR / "action_type_counts.csv",
            index=False,
            encoding="utf-8-sig",
        )

    if not suspicious_tx.empty:
        suspicious_tx.to_csv(
            OUT_DIR / "suspicious_price_transactions.csv",
            index=False,
            encoding="utf-8-sig",
        )

    # 흐름 확인용 P2P edge 집계
    if not tx.empty:
        p2p_edges = tx[
            tx["sender_id"].fillna("").ne("SYSTEM_SHOP")
            & tx["receiver_id"].fillna("").ne("SYSTEM_SHOP")
        ].groupby(["sender_id", "receiver_id"]).agg(
            tx_count=("transaction_id", "count"),
            total_gold=("gold_amount", "sum"),
        ).reset_index().sort_values(
            ["total_gold", "tx_count"], ascending=False
        )

        p2p_edges.to_csv(
            OUT_DIR / "transaction_edges.csv",
            index=False,
            encoding="utf-8-sig",
        )

    print("\n[출력 파일]")
    print(f"- {OUT_DIR / 'account_features_v1.csv'}")
    print(f"- {OUT_DIR / 'action_type_counts.csv'}")
    print(f"- {OUT_DIR / 'transaction_edges.csv'}")
    print(f"- {OUT_DIR / 'suspicious_price_transactions.csv'}")

    # ground truth를 보지 않고 거래 특성만으로 상위 후보를 참고 출력
    score_cols = [
        c for c in [
            "gold_received",
            "gold_sent",
            "max_receiver_share",
            "suspicious_price_trade_count",
            "unique_senders",
        ] if c in features.columns
    ]

    if score_cols:
        preview = features.copy()
        # 단순 preview용 정규화. 최종 CARS가 아님.
        temp = pd.DataFrame(index=preview.index)
        for col in score_cols:
            s = pd.to_numeric(preview[col], errors="coerce").fillna(0)
            if s.max() > s.min():
                temp[col] = (s - s.min()) / (s.max() - s.min())
            else:
                temp[col] = 0.0
        preview["inspection_priority_v0"] = temp.mean(axis=1)
        show_cols = score_cols + ["inspection_priority_v0"]
        if "ground_truth_type" in preview.columns:
            show_cols += ["ground_truth_type"]

        print("\n[거래 특징 기준 조사 우선순위 TOP 10]")
        print(
            preview.sort_values(
                "inspection_priority_v0", ascending=False
            )[show_cols].head(10).round(3).to_string()
        )

    print("\n※ ground_truth_type은 검증용 정답이며 탐지 Feature에는 사용하지 않습니다.")
    print("※ inspection_priority_v0는 CARS가 아니라 데이터 점검용 임시 우선순위입니다.")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
