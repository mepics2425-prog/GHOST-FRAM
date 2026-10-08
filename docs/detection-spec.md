# GHOST FARM Detection Specification

## 1. 문서 목적

이 문서는 GHOST FARM의 탐지 파이프라인에서  
각 데이터가 어떤 Feature로 변환되고, CARS V3가 어떤 논리로 조직형 어뷰징을 탐지하는지 정의합니다.

---

## 2. 탐지 대상

Primary Target:

```text
Farm → Mule → Hub
```

탐지 단위는 단일 계정이 아니라  
**조직형 재화 유통 구조**입니다.

평가 시 organized abuse positive는:

```text
Farm
Mule
Hub
```

로 구성합니다.

Bot은 반복 행동 이상 유형이지만  
organized abuse 평가는 별도 범주로 취급합니다.

---

## 3. 입력 데이터

### Event

필수 주요 필드:

```text
timestamp
user_id
session_id
action_type
map_id
x
y
target_user_id
gold_delta
```

### Transaction

핵심 필드:

```text
timestamp
sender_id
receiver_id
gold_amount
market_price
trade_price
transaction_type
```

### Session

핵심 필드:

```text
user_id
login_at
logout_at
play_time
device_group
ip_group
```

---

## 4. Account Features

대표 Feature:

| Feature | 의미 |
|---|---|
| `event_count` | 총 행동량 |
| `action_diversity` | 행동 종류 다양성 |
| `map_diversity` | 활동 맵 다양성 |
| `action_entropy` | 행동 분포 불확실성 |
| `gold_sent` | 총 송금 골드 |
| `gold_received` | 총 수신 골드 |
| `unique_senders` | 송금자 수 |
| `unique_receivers` | 수신자 수 |
| `max_receiver_share` | 가장 큰 수신처 집중도 |
| `outflow_ratio` | 전체 흐름 중 송금 비율 |
| `price_deviation` | 시장 가격 대비 거래 가격 이상도 |

---

## 5. Graph Features

거래 그래프:

```text
Node = Account
Edge = Gold / Item Transaction
Weight = Flow Volume
```

대표 Feature:

| Feature | 의미 |
|---|---|
| weighted_in | 총 유입 |
| weighted_out | 총 유출 |
| in_degree | 송금자 수 |
| out_degree | 수신자 수 |
| in_hhi | 유입 집중도 |
| out_hhi | 유출 집중도 |
| flow_balance | 유입 대비 유출 균형 |
| betweenness | 중계 역할 가능성 |
| pagerank | 네트워크 영향도 |

---

## 6. Behavior Synchronization

SyncScore는 다음 요소를 결합합니다.

```text
LoginSync
ActionProfileCosine
TemporalActionCosine
MapTimelineCosine
```

기존 가중 구조:

```text
0.05 * LoginSync
+ 0.25 * ActionProfileCosine
+ 0.55 * TemporalActionCosine
+ 0.15 * MapTimelineCosine
```

중요:

```text
High Sync != Abuse
```

Guild 정상 유저가 높은 Sync를 보일 수 있으므로  
Sync는 독립 판정 규칙이 아니라 구조적 Funnel과 결합합니다.

---

## 7. CARS V2 Specification

V2 주요 구성:

```text
Farm Purity
Mule Purity
Hub Purity
Ghost Chain
Economic
Repetition
Sync Funnel
```

### Farm Purity

주요 관점:

- outbound volume
- primary receiver share
- outflow ratio
- 거래량 신뢰도

### Mule Purity

주요 관점:

- inbound breadth
- primary receiver concentration
- flow-through
- outgoing partner penalty

### Hub Purity

주요 관점:

- incoming concentration
- 높은 수신량
- 낮은 outgoing

---

## 8. V2 Failure Modes

### Hardcore False Positive

특징:

- 높은 거래량
- 많은 상대
- balanced flow
- 낮은 outbound concentration

따라서 높은 활동량/거래량만으로는 abuse가 아닙니다.

### Farm False Negative

특징:

- 정상 거래 noise
- receiver 다양화
- 하지만 relay 방향성이 남아 있음

### Hub False Negative

Hub는 낮은 행동량으로 인해  
account score aggregation에서 과소평가될 수 있습니다.

### Mule Split

공격자가 송금을 여러 mule로 분산하면:

```text
Primary Receiver Share ↓
```

V2 위험 점수가 약해집니다.

---

## 9. CARS V3 Specification

V3 핵심 구성:

```text
Account Risk
+
Organization Support
+
Relay Set Share
+
Source → Relay → Collector Path
+
Independent Hub Branch
```

---

## 10. Relay Set Logic

단일 receiver 집중도 대신  
의심 Relay 집합 전체로 흘러간 비율을 계산합니다.

개념:

```text
relay_set_share
=
gold_sent_to_relays
/
total_gold_sent
```

예:

```text
Mule 1 = 35%
Mule 2 = 30%
Mule 3 = 25%
Other  = 10%
```

Single receiver share:

```text
0.35
```

Relay Set Share:

```text
0.90
```

따라서 Mule Split 회피에 더 강합니다.

---

## 11. Source Component

Source/Farm 관점에서 평가:

- relay_set_share
- outbound ratio
- suspicious downstream support
- transaction volume confidence
- downstream convergence

높은 Source Score는:

> 재화를 생산하고 조직 relay 방향으로 지속적으로 전달하는 계정

을 의미합니다.

---

## 12. Relay Component

Relay/Mule 관점에서 평가:

- upstream sender breadth
- flow-through
- downstream concentration
- collector affinity
- incoming → outgoing path support

Relay는:

```text
Many Sources
    ↓
Relay
    ↓
Few Collectors
```

형태를 보입니다.

---

## 13. Collector Component

Hub/Collector 관점:

- incoming volume
- incoming concentration
- relay upstream support
- low outgoing
- organization path convergence

V3는 Hub 점수를 별도 branch로 유지합니다.

---

## 14. Organization Support

조직 구조는 개별 점수가 아닌  
연결된 계정의 상호 지지로 계산합니다.

개념:

```text
Source Support
   ↓
Relay Support
   ↓
Collector Support
```

즉:

```text
High-risk Source
+
Valid Relay
+
Valid Collector
```

가 연결될수록 organization evidence가 강화됩니다.

---

## 15. Counter-Evidence

운영에서는 위험 신호와 함께 정상 근거도 검토해야 합니다.

예:

### Hardcore 정상 근거

- 거래 상대가 넓게 분산
- 양방향 거래
- 다양한 행동
- 다양한 맵
- 특정 collector 수렴 없음

### Guild 정상 근거

- 높은 Sync
- 협동 행동
- 그러나 funnel flow 없음

따라서 CARS는:

```text
High Activity
High Sync
High Volume
```

만으로 자동 제재하지 않습니다.

---

## 16. Evaluation Protocol

### Development Set

```text
calibration
unseen_01
unseen_02
V2 red-team
```

V3 설계에 영향을 준 데이터입니다.

### Held-out

```text
unseen_03
```

V3 freeze 이후 새로 생성해 평가했습니다.

### Red-Team

6종:

```text
time_jitter
mule_split
micro_tx
normal_mix
behavior_noise
composite
```

---

## 17. Metrics

현재 주요 평가 지표:

```text
Precision@K
Recall@K
F1@K
```

여기서 K는 organized abuse positive 수와 동일하게 설정한 연구용 ranking 평가입니다.

주의:

실제 운영 환경에서는 다음이 추가로 필요합니다.

- fixed threshold
- threshold calibration
- PR-AUC
- precision at review budget
- alert volume
- detection latency

---

## 18. Current Result

### unseen_03

```text
Precision@K = 1.000
Recall@K    = 1.000
F1@K        = 1.000
```

### Confusion Matrix

```text
TP = 13
FP = 0
FN = 0
TN = 20
```

### Role Coverage

```text
Farm = 10 / 10
Mule = 2 / 2
Hub  = 1 / 1
```

---

## 19. Operational Decision Flow

권장 운영 흐름:

```text
Raw Telemetry
    ↓
Feature Pipeline
    ↓
CARS V3
    ↓
Risk Ranking
    ↓
Organization Evidence
    ↓
Counter-Evidence Review
    ↓
Investigation Queue
    ↓
Human Decision
```

CARS는 자동 Ban 엔진보다  
**investigation prioritization system**으로 사용하는 것이 안전합니다.

---

## 20. Limitations

- synthetic data
- simulator distribution dependency
- predefined attack families
- small population
- current `@K` evaluation
- no production threshold
- no real payment/social/device graph
- no external game telemetry

따라서 현재 결과는  
**정의된 synthetic threat model 안에서의 기술 검증 결과**로 해석합니다.
