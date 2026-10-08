# Aetheria 로그 스키마

Aetheria는 게임 플레이 중 Event, Transaction, Session 로그를 생성합니다.

Ground Truth는 전체 JSON에 별도 저장되며, 탐지 Feature 계산에는 사용하지 않고 평가 단계에서만 사용합니다.

---

## 1. Event

주요 필드:

| 필드 | 설명 |
|---|---|
| `event_id` | 이벤트 식별자 |
| `timestamp` | 이벤트 발생 시각 |
| `user_id` | 사용자 계정 |
| `character_id` | 캐릭터 식별자 |
| `session_id` | 플레이 세션 |
| `action_type` | 행동 유형 |
| `map_id` | 맵 |
| `x`, `y` | 위치 |
| `target_user_id` | 대상 사용자 |
| `item_id` | 관련 아이템 |
| `quantity` | 수량 |
| `gold_delta` | 골드 변화 |
| `metadata` | 행동별 추가 정보 |

대표 `action_type` 예시:

```text
move
rest
attack
damaged
combat_start
monster_kill
monster_respawn
item_drop
gather_start
gather_success
gather_cancel
quest_start
quest_complete
market_list
market_buy
market_sell
trade_gold
login
logout
visit
```

---

## 2. Transaction

| 필드 | 설명 |
|---|---|
| `transaction_id` | 거래 식별자 |
| `timestamp` | 거래 시각 |
| `sender_id` | 송신 계정 |
| `receiver_id` | 수신 계정 |
| `gold_amount` | 이동 골드 |
| `item_id` | 아이템 |
| `quantity` | 수량 |
| `market_price` | 기준 시장 가격 |
| `trade_price` | 실제 거래 가격 |
| `transaction_type` | 거래 유형 |
| `metadata` | 추가 정보 |

조직형 탐지에서는 주로 다음을 사용합니다.

- 계정별 총 유입/유출 골드
- Unique sender / receiver
- Receiver concentration
- HHI
- Flow balance
- P2P volume
- Multi-hop transaction path
- Source → Relay → Hub 수렴 구조

---

## 3. Session

| 필드 | 설명 |
|---|---|
| `session_id` | 세션 식별자 |
| `user_id` | 사용자 |
| `character_id` | 캐릭터 |
| `login_at` | 로그인 |
| `logout_at` | 로그아웃 |
| `play_time` | 플레이 시간 |
| `device_group` | 합성 디바이스 그룹 |
| `ip_group` | 합성 네트워크 그룹 |
| `synthetic` | 합성 계정 여부 |

---

## 4. 전체 JSON Snapshot

전체 Export에는 다음 구조가 포함됩니다.

```text
schema_version
exported_at
world_time
clock_scale
events
transactions
sessions
users
ground_truth
characters
retention
```

`retention`에는 로그 최대 보존량 및 삭제 수가 기록될 수 있습니다.

---

## 5. Ground Truth 사용 원칙

`ground_truth`는 다음 용도로만 사용합니다.

- Precision / Recall / F1 계산
- False Positive 분석
- False Negative 분석
- 역할별 탐지율 평가

다음에는 사용하지 않습니다.

- Isolation Forest 학습 Feature
- CARS V2/V3 점수 계산
- Graph Risk 계산
- Behavior Sync 계산
- Organization Path Score 계산

즉 탐지기는 계정의 실제 합성 역할을 모른 상태에서 점수를 계산합니다.

---

## 6. Feature 예시

### Account-level

```text
event_count
action_diversity
map_diversity
active_time
action_entropy
gold_sent
gold_received
unique_senders
unique_receivers
max_receiver_share
price_deviation
outflow_ratio
```

### Graph-level

```text
in_degree
out_degree
weighted_gold_in
weighted_gold_out
in_hhi
out_hhi
flow_balance
betweenness
pagerank
```

### Synchronization

```text
login_sync
action_profile_cosine
temporal_action_cosine
map_timeline_cosine
```

### Organization-level

```text
relay_set_share
relay_in_share
downstream_hub_affinity
source_component
relay_component
hub_component
organization_support
organization_path_score
```
