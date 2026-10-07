from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics.pairwise import cosine_similarity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "aetheria-all.json"
OUT_DIR = PROJECT_ROOT / "data" / "analysis"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

BIN_MINUTES = 10

# Ground Truth를 보고 최적화한 값이 아니라,
# 해석 가능한 초기 가중치다. 이후 CARS ablation에서 검증한다.
W_LOGIN = 0.05
W_ACTION_PROFILE = 0.25
W_TEMPORAL_ACTION = 0.55
W_MAP_TIMELINE = 0.15

MEANINGFUL_ACTIONS = [
    "move",
    "rest",
    "attack",
    "combat_start",
    "quest_start",
    "quest_complete",
    "trade_gold",
    "monster_kill",
    "gather_start",
    "gather_success",
    "market_sell",
    "market_list",
    "market_buy",
    "visit",
    "item_drop",
]


def load_snapshot():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"\n원본 JSON을 찾을 수 없습니다:\n{RAW_PATH}\n"
        )

    with RAW_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    events = pd.DataFrame(data.get("events", []))
    sessions = pd.DataFrame(data.get("sessions", []))
    gt = pd.DataFrame(data.get("ground_truth", []))

    if events.empty:
        raise ValueError("events가 비어 있습니다.")

    events["timestamp"] = pd.to_datetime(
        events["timestamp"], utc=True, errors="coerce"
    )

    if not sessions.empty:
        sessions["login_at"] = pd.to_datetime(
            sessions["login_at"], utc=True, errors="coerce"
        )

    return events, sessions, gt


def build_matrix(
    events: pd.DataFrame,
    account_ids: list[str],
    value_col: str,
    values: list[str],
) -> pd.DataFrame:
    """
    계정 x (시간창, 행동/맵) 형태의 벡터를 만든다.
    모든 계정이 동일한 시간축/컬럼을 갖게 한다.
    """
    work = events[
        events["user_id"].isin(account_ids)
        & events[value_col].isin(values)
    ].copy()

    work["time_bin"] = work["timestamp"].dt.floor(f"{BIN_MINUTES}min")

    if work.empty:
        return pd.DataFrame(index=account_ids)

    time_bins = pd.date_range(
        work["time_bin"].min(),
        work["time_bin"].max(),
        freq=f"{BIN_MINUTES}min",
    )

    full_index = pd.MultiIndex.from_product(
        [account_ids, time_bins, values],
        names=["user_id", "time_bin", value_col],
    )

    counts = (
        work.groupby(["user_id", "time_bin", value_col])
        .size()
        .reindex(full_index, fill_value=0)
        .rename("count")
        .reset_index()
    )

    matrix = counts.pivot_table(
        index="user_id",
        columns=["time_bin", value_col],
        values="count",
        fill_value=0,
    )

    return matrix.reindex(account_ids, fill_value=0)


def build_action_profile(
    events: pd.DataFrame,
    account_ids: list[str],
) -> pd.DataFrame:
    work = events[
        events["user_id"].isin(account_ids)
        & events["action_type"].isin(MEANINGFUL_ACTIONS)
    ]

    matrix = (
        work.groupby(["user_id", "action_type"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=account_ids, columns=MEANINGFUL_ACTIONS, fill_value=0)
    )
    return matrix


def cosine_matrix(matrix: pd.DataFrame) -> np.ndarray:
    if matrix.shape[1] == 0:
        return np.zeros((len(matrix), len(matrix)))

    return cosine_similarity(matrix.to_numpy(dtype=float))


def first_login_map(
    events: pd.DataFrame,
    sessions: pd.DataFrame,
    account_ids: list[str],
) -> dict[str, pd.Timestamp]:
    result = {}

    if not sessions.empty and {"user_id", "login_at"}.issubset(sessions.columns):
        s = (
            sessions[sessions["user_id"].isin(account_ids)]
            .groupby("user_id")["login_at"]
            .min()
        )
        result.update(s.to_dict())

    # session이 없는 계정은 첫 이벤트 시각으로 보완
    first_event = (
        events[events["user_id"].isin(account_ids)]
        .groupby("user_id")["timestamp"]
        .min()
    )

    for uid in account_ids:
        if uid not in result or pd.isna(result[uid]):
            result[uid] = first_event.get(uid, pd.NaT)

    return result


def login_sync_score(a, b, tau_minutes=30.0):
    if pd.isna(a) or pd.isna(b):
        return 0.0, np.nan

    delta_min = abs((a - b).total_seconds()) / 60.0
    score = float(np.exp(-delta_min / tau_minutes))
    return score, delta_min


def main():
    events, sessions, gt = load_snapshot()

    # 실제 플레이어 + synthetic 계정. 시스템 엔티티 제외.
    account_ids = sorted(
        uid for uid in events["user_id"].dropna().astype(str).unique()
        if not uid.startswith("SYSTEM_")
    )

    gt_map = {}
    if not gt.empty and {"user_id", "user_type"}.issubset(gt.columns):
        gt_map = dict(zip(gt["user_id"], gt["user_type"]))

    action_profile = build_action_profile(events, account_ids)

    temporal_action = build_matrix(
        events=events,
        account_ids=account_ids,
        value_col="action_type",
        values=MEANINGFUL_ACTIONS,
    )

    map_values = sorted(
        events.loc[
            events["user_id"].isin(account_ids),
            "map_id"
        ].dropna().astype(str).unique()
    )

    map_timeline = build_matrix(
        events=events.dropna(subset=["map_id"]),
        account_ids=account_ids,
        value_col="map_id",
        values=map_values,
    )

    profile_sim = cosine_matrix(action_profile)
    temporal_sim = cosine_matrix(temporal_action)
    map_sim = cosine_matrix(map_timeline)

    login_map = first_login_map(events, sessions, account_ids)

    rows = []

    for i, uid_a in enumerate(account_ids):
        for j in range(i + 1, len(account_ids)):
            uid_b = account_ids[j]

            login_sync, login_delta = login_sync_score(
                login_map.get(uid_a),
                login_map.get(uid_b),
            )

            action_profile_score = float(profile_sim[i, j])
            temporal_action_score = float(temporal_sim[i, j])
            map_timeline_score = float(map_sim[i, j])

            sync_01 = (
                W_LOGIN * login_sync
                + W_ACTION_PROFILE * action_profile_score
                + W_TEMPORAL_ACTION * temporal_action_score
                + W_MAP_TIMELINE * map_timeline_score
            )

            rows.append({
                "user_a": uid_a,
                "user_b": uid_b,
                "login_delta_minutes": login_delta,
                "login_sync": login_sync,
                "action_profile_cosine": action_profile_score,
                "temporal_action_cosine": temporal_action_score,
                "map_timeline_cosine": map_timeline_score,
                "sync_score": sync_01 * 100.0,
                "user_a_gt": gt_map.get(uid_a),
                "user_b_gt": gt_map.get(uid_b),
            })

    pair_df = pd.DataFrame(rows).sort_values(
        "sync_score", ascending=False
    )

    account_rows = []

    for uid in account_ids:
        rel = pair_df[
            (pair_df["user_a"] == uid)
            | (pair_df["user_b"] == uid)
        ].copy()

        rel = rel.sort_values("sync_score", ascending=False)

        top3 = rel.head(3)
        top5 = rel.head(5)

        if len(rel):
            best_row = rel.iloc[0]
            best_partner = (
                best_row["user_b"]
                if best_row["user_a"] == uid
                else best_row["user_a"]
            )
        else:
            best_partner = None

        account_rows.append({
            "user_id": uid,
            "ground_truth_type": gt_map.get(uid),
            "max_sync_score": rel["sync_score"].max() if len(rel) else 0.0,
            "top3_mean_sync": top3["sync_score"].mean() if len(top3) else 0.0,
            "top5_mean_sync": top5["sync_score"].mean() if len(top5) else 0.0,
            "mean_sync_all": rel["sync_score"].mean() if len(rel) else 0.0,
            "best_sync_partner": best_partner,
        })

    account_df = pd.DataFrame(account_rows).sort_values(
        "top3_mean_sync", ascending=False
    )

    # Ground Truth는 여기서부터 해석/평가에만 사용
    same_type = pair_df[
        pair_df["user_a_gt"].notna()
        & pair_df["user_b_gt"].notna()
        & (pair_df["user_a_gt"] == pair_df["user_b_gt"])
    ].copy()

    if not same_type.empty:
        type_summary = (
            same_type.groupby("user_a_gt")["sync_score"]
            .agg(["count", "mean", "median", "max", "min"])
            .rename_axis("ground_truth_type")
            .sort_values("mean", ascending=False)
            .round(3)
        )
    else:
        type_summary = pd.DataFrame()

    pair_path = OUT_DIR / "behavior_pair_sync.csv"
    account_path = OUT_DIR / "behavior_account_sync.csv"
    summary_path = OUT_DIR / "behavior_sync_type_summary.csv"

    pair_df.to_csv(pair_path, index=False, encoding="utf-8-sig")
    account_df.to_csv(account_path, index=False, encoding="utf-8-sig")
    type_summary.to_csv(summary_path, encoding="utf-8-sig")

    # 유형별 계정 Top-3 평균 Sync 시각화
    chart_df = account_df[account_df["ground_truth_type"].notna()].copy()

    if not chart_df.empty:
        order = [
            t for t in
            ["normal", "hardcore", "guild", "bot", "farm", "mule", "hub"]
            if t in chart_df["ground_truth_type"].unique()
        ]

        data = [
            chart_df.loc[
                chart_df["ground_truth_type"] == t,
                "top3_mean_sync"
            ].values
            for t in order
        ]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.boxplot(data, tick_labels=order)
        ax.set_title("Behavior Synchronization by Account Type")
        ax.set_ylabel("Top-3 Mean Sync Score (0-100)")
        ax.set_xlabel("Ground Truth Type")
        fig.tight_layout()
        fig.savefig(
            FIG_DIR / "behavior_sync_by_type.png",
            dpi=160
        )
        plt.close(fig)

    print("\n" + "=" * 92)
    print(" GHOST FARM | BEHAVIOR SYNCHRONIZATION ANALYSIS V1")
    print("=" * 92)
    print(f"Accounts                  : {len(account_ids)}")
    print(f"Account pairs             : {len(pair_df)}")
    print(f"Time bin                  : {BIN_MINUTES} minutes")
    print("Ground Truth in score     : NO")
    print("")
    print("SyncScore =")
    print(
        f"  {W_LOGIN:.2f} * LoginSync"
        f" + {W_ACTION_PROFILE:.2f} * ActionProfileCosine"
        f" + {W_TEMPORAL_ACTION:.2f} * TemporalActionCosine"
        f" + {W_MAP_TIMELINE:.2f} * MapTimelineCosine"
    )

    print("\n[계정 Sync TOP 15]")
    print(
        account_df[
            [
                "user_id",
                "ground_truth_type",
                "top3_mean_sync",
                "max_sync_score",
                "best_sync_partner",
            ]
        ]
        .head(15)
        .round(3)
        .to_string(index=False)
    )

    print("\n[동일 유형 계정쌍 Sync 평균 — Ground Truth는 해석에만 사용]")
    if type_summary.empty:
        print("Ground Truth 없음")
    else:
        print(type_summary.to_string())

    print("\n[Pair Sync TOP 15]")
    print(
        pair_df[
            [
                "user_a",
                "user_b",
                "sync_score",
                "login_delta_minutes",
                "action_profile_cosine",
                "temporal_action_cosine",
                "map_timeline_cosine",
                "user_a_gt",
                "user_b_gt",
            ]
        ]
        .head(15)
        .round(3)
        .to_string(index=False)
    )

    print("\n[생성 파일]")
    print(f"- {pair_path}")
    print(f"- {account_path}")
    print(f"- {summary_path}")
    print(f"- {FIG_DIR / 'behavior_sync_by_type.png'}")

    print("\n해석 포인트:")
    print("1) SyncScore는 Ground Truth를 사용하지 않고 행동/시간/맵 로그만으로 계산합니다.")
    print("2) Guild의 Sync가 높게 나와도 실패가 아닙니다. 실제 정상 협동 플레이도 동기화될 수 있습니다.")
    print("3) 따라서 Sync 하나로 제재하면 안 되고, Graph/Economy와 결합해야 합니다.")
    print("4) 다음 단계 CARS에서 '높은 Sync + 재화 Funnel' 조합을 조직형 어뷰징 근거로 사용합니다.")
    print("=" * 92 + "\n")


if __name__ == "__main__":
    main()
