import pandas as pd
import numpy as np
from pathlib import Path

SEED = 42
N_USERS = 1000

np.random.seed(SEED)

# 프로젝트 루트/data 경로
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 사용자 유형
user_types = (
    ["normal"] * 750 +
    ["hardcore"] * 80 +
    ["guild"] * 70 +
    ["bot"] * 40 +
    ["farm"] * 50 +
    ["mule"] * 8 +
    ["hub"] * 2
)

np.random.shuffle(user_types)

users = pd.DataFrame({
    "user_id": [f"U{i:05d}" for i in range(1, N_USERS + 1)],
    "user_type": user_types
})

# 가입일
base_date = pd.Timestamp("2026-01-01")

users["join_date"] = [
    base_date + pd.Timedelta(days=int(day))
    for day in np.random.randint(0, 250, N_USERS)
]

# 유형별 레벨 범위
level_ranges = {
    "normal": (15, 70),
    "hardcore": (55, 100),
    "guild": (35, 90),
    "bot": (25, 80),
    "farm": (30, 75),
    "mule": (10, 45),
    "hub": (5, 30)
}

users["level"] = [
    np.random.randint(
        level_ranges[user_type][0],
        level_ranges[user_type][1] + 1
    )
    for user_type in users["user_type"]
]

# 저장
output_path = DATA_DIR / "users.csv"

users.to_csv(
    output_path,
    index=False,
    encoding="utf-8-sig"
)

print("\n===== GHOST FARM USER GENERATOR =====")
print(f"총 계정 수 : {len(users):,}")
print(f"저장 위치  : {output_path}")

print("\n[사용자 유형]")
print(users["user_type"].value_counts())

print("\n[샘플]")
print(users.head(10))