# GHOST FARM Architecture

## 1. 목적

GHOST FARM은 합성 MMORPG 환경 **Aetheria : Moonberry Village**에서 생성되는 행동·세션·거래 로그를 이용해  
개별 계정 이상치가 아니라 **조직 단위의 재화 유통 구조**를 탐지하는 프로젝트입니다.

핵심 탐지 대상은 다음과 같습니다.

```text
Farm → Relay(Mule) → Hub
```

단일 계정의 활동량이나 거래량만 보는 것이 아니라  
**다수 계정 간 관계, 재화 집중도, relay 구조, multi-hop flow**를 함께 평가합니다.

---

## 2. 전체 시스템 구조

```text
┌────────────────────────────────────┐
│ Aetheria : Moonberry Village       │
│ Browser MMORPG Simulator           │
│                                    │
│ - Player                           │
│ - Normal / Hardcore / Guild        │
│ - Bot / Farm / Mule / Hub          │
└─────────────────┬──────────────────┘
                  │
                  ▼
┌────────────────────────────────────┐
│ Raw Telemetry Export               │
│                                    │
│ events                             │
│ transactions                       │
│ sessions                           │
│ users                              │
│ ground_truth (evaluation only)     │
└─────────────────┬──────────────────┘
                  │
                  ▼
┌────────────────────────────────────┐
│ Feature Engineering                │
│                                    │
│ Account Features                   │
│ Transaction Features               │
│ Graph Features                     │
│ Behavior Synchronization Features  │
└───────────────┬────────────────────┘
                │
       ┌────────┴─────────┐
       ▼                  ▼
┌───────────────┐  ┌──────────────────────┐
│ Baseline      │  │ Structural Analysis  │
│ Isolation     │  │                      │
│ Forest        │  │ Graph / Sync / Flow  │
└───────┬───────┘  └──────────┬───────────┘
        │                      │
        └──────────┬───────────┘
                   ▼
        ┌──────────────────────┐
        │ CARS V2              │
        │ Account + Chain Risk │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Red-Team Analysis    │
        │                      │
        │ - Mule Split         │
        │ - Normal Mix         │
        │ - Micro TX           │
        │ - Time Jitter        │
        │ - Behavior Noise     │
        │ - Composite          │
        └──────────┬───────────┘
                   │
                   ▼
        ┌───────────────────────────────┐
        │ CARS V3                      │
        │ Organization Flow Detector   │
        │                               │
        │ Source → Relay → Collector   │
        │ Relay Set                    │
        │ Organization Support         │
        │ Hub Branch                   │
        └──────────┬────────────────────┘
                   │
                   ▼
        ┌───────────────────────────────┐
        │ Evaluation                    │
        │                               │
        │ DEV                           │
        │ Held-out unseen snapshot      │
        │ Red-Team robustness           │
        └───────────────────────────────┘
```

---

## 3. 데이터 생성 계층

Aetheria는 탐지 실험을 위한 합성 MMORPG 로그 생성기입니다.

합성 계정 구성:

| 역할 | 수 | 목적 |
|---|---:|---|
| Normal | 10 | 일반 사용자 |
| Hardcore | 4 | 높은 활동량·거래량을 가진 정상 사용자 |
| Guild | 6 | 높은 행동 동기화를 가진 정상 협동 사용자 |
| Bot | 3 | 반복 행동 기반 자동화 계정 |
| Farm | 10 | 재화 생산 후 Relay로 전달 |
| Mule | 2 | Farm 재화를 모아 Hub로 전달 |
| Hub | 1 | 최종 재화 집결 |

이 설계는 단순한 정상/비정상 이분법보다  
**False Positive challenge와 조직 구조 탐지**를 테스트하기 위해 구성되었습니다.

---

## 4. 로그 계층

### Events

행동 단위 로그:

```text
event_id
timestamp
user_id
character_id
session_id
action_type
map_id
x
y
target_user_id
item_id
quantity
gold_delta
metadata
```

### Transactions

재화 이동 로그:

```text
transaction_id
timestamp
sender_id
receiver_id
gold_amount
item_id
quantity
market_price
trade_price
transaction_type
metadata
```

### Sessions

접속 및 플레이 로그:

```text
session_id
user_id
character_id
login_at
logout_at
play_time
device_group
ip_group
synthetic
```

---

## 5. Feature Engineering

### Account-level

- event count
- action diversity
- map diversity
- action entropy
- play time
- outgoing/incoming gold
- unique senders/receivers
- receiver concentration
- outflow ratio
- price deviation

### Graph-level

- weighted in/out flow
- in/out degree
- HHI
- flow balance
- betweenness
- PageRank
- sender/receiver concentration

### Behavior Synchronization

- LoginSync
- ActionProfileCosine
- TemporalActionCosine
- MapTimelineCosine

중요한 관찰:

> Guild 계정의 Sync가 Farm보다 높게 나타날 수 있다.

따라서 Sync는 단독 이상 신호가 아니라  
**재화 Funnel이 존재할 때 구조적 보조 신호**로 사용합니다.

---

## 6. Baseline

Baseline은 account-level feature에 **Isolation Forest**를 적용합니다.

장점:

- Ground Truth 없이 비지도 방식으로 사용 가능
- 빠르게 기준 성능 확보 가능

한계:

- Hardcore 정상 계정을 위험 계정으로 오탐
- Farm은 개별 행동만 보면 정상과 유사
- 조직 구조를 직접 표현하지 못함

---

## 7. CARS V2

CARS V2는 계정 단위 신호와 거래 구조를 결합합니다.

주요 요소:

```text
Farm Purity
Mule Purity
Hub Purity
Ghost Chain
Economic Anomaly
Repetition
Structural Sync Interaction
```

V2는 Baseline보다 크게 개선되었지만 Red-Team에서 다음 약점이 확인되었습니다.

- Mule Split
- Normal Mix
- Composite
- Hub False Negative

---

## 8. CARS V3

V3는 핵심 질문을 바꿉니다.

```text
이 계정이 이상한가?
        ↓
이 계정들이 하나의 조직으로 움직이는가?
```

### 8.1 Relay Set

V2는 single primary receiver에 상대적으로 의존했습니다.

V3는 다음처럼 여러 Relay로 분산되더라도:

```text
Farm A → Mule 1
Farm A → Mule 2
Farm A → Mule 3
```

전체 Relay 집합으로 전달된 비율을 평가합니다.

---

### 8.2 Organization Path

핵심 구조:

```text
Source → Relay → Collector
```

각 계정의 risk뿐 아니라  
**upstream/downstream 관계를 통한 organization support**를 계산합니다.

---

### 8.3 Hub Branch

Hub는 이벤트 수가 적어 기존 합산 점수에서 과소평가될 수 있습니다.

V3는 Collector/Hub 평가 branch를 별도로 유지하여:

- 높은 incoming concentration
- upstream relay support
- 낮은 outgoing
- 조직 전체 flow 수렴

을 독립적으로 평가합니다.

---

## 9. 평가 구조

### Development

- calibration snapshot
- unseen_01
- unseen_02
- V2 Red-Team

이 데이터는 error analysis와 V3 설계에 영향을 주었기 때문에  
최종 held-out 성능으로 취급하지 않습니다.

### Held-out

V3 설계 이후 새로 생성한:

```text
unseen_03
```

에서 코드 수정 없이 검증했습니다.

### Red-Team

`unseen_03` 기반으로 다음 6종 공격을 적용했습니다.

```text
time_jitter
mule_split
micro_tx
normal_mix
behavior_noise
composite
```

---

## 10. 최종 결과

### unseen_03

| 모델 | Precision@K | Recall@K | F1@K |
|---|---:|---:|---:|
| Isolation Forest | 0.538 | 0.538 | 0.538 |
| CARS V2 | 0.923 | 0.923 | 0.923 |
| CARS V3 | **1.000** | **1.000** | **1.000** |

CARS V3:

```text
TP = 13
FP = 0
FN = 0
TN = 20
```

Role Detection:

```text
Farm = 10 / 10
Mule = 2 / 2
Hub  = 1 / 1
```

---

## 11. 설계 원칙

### Ground Truth Isolation

Ground Truth는 다음에 사용하지 않습니다.

- feature engineering
- Isolation Forest training
- CARS V2/V3 scoring
- graph scoring
- Sync scoring

다음 평가 단계에서만 사용합니다.

- Precision
- Recall
- F1
- FP/FN analysis

### No Auto-ban

CARS 점수는 자동 제재보다는:

```text
Detection
   ↓
Investigation Queue
   ↓
Counter-Evidence Review
   ↓
Human Decision
```

형태의 운영 구조를 가정합니다.

---

## 12. 한계

- synthetic data 기반
- simulator distribution 안에서의 held-out
- predefined red-team attack families
- `@K` 평가 방식 사용
- 실제 운영 threshold calibration 미적용
- real-world device/payment/social graph 미포함

따라서 실제 서비스 성능을 100%로 주장하지 않습니다.

---

## 13. 프로젝트 핵심 문장

> **개별 계정에는 이상이 없었다. 그런데 여러 계정을 함께 보자, 돈은 한 곳으로 흐르고 있었다.**
