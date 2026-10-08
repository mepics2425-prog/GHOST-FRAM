# GHOST FARM 검증 보고서

이 문서는 GHOST FARM 탐지 모델의 개발 및 검증 흐름을 정리합니다.

중요한 원칙:

> Ground Truth는 탐지 점수 계산에 사용하지 않고 평가에만 사용한다.

---

## 1. Baseline

Account-level Feature에 Isolation Forest를 적용했습니다.

`unseen_03` organized abuse 기준:

```text
Precision@K = 0.538
Recall@K    = 0.538
F1@K        = 0.538
```

문제:

- Hardcore 정상 사용자가 높은 위험도로 오탐됨
- Farm은 개별 행동만 보면 정상과 유사
- 조직 구조를 직접 표현하지 못함

---

## 2. CARS V1

초기 CARS는 다음 신호를 결합했습니다.

- Graph Flow
- Ghost Motif
- Sync Funnel
- Economic
- Repetition

초기 calibration snapshot에서는 높은 성능이 나왔지만,  
같은 설계 과정에서 사용한 데이터이므로 일반화 성능으로 해석하지 않았습니다.

첫 unseen 검증:

```text
unseen_01
CARS V1 F1@K = 0.846
```

False Positive:

```text
Hardcore × 2
```

False Negative:

```text
Farm × 2
```

---

## 3. V1 오류 분석

Hardcore False Positive 특징:

- 높은 P2P 거래량
- 높은 Flow Balance
- 다수 Sender/Receiver
- 그러나 특정 Receiver 집중도는 낮음

Farm False Negative 특징:

- 여러 정상 거래를 섞음
- Receiver 수 증가
- 하지만 주된 Relay로 보내는 비율은 여전히 높음

이 분석을 바탕으로 CARS V2를 설계했습니다.

---

## 4. CARS V2

V2 핵심:

- Farm purity
- Mule purity
- Hub purity
- Ghost Chain
- Volume confidence
- 구조적 Sync interaction

`unseen_02` held-out:

```text
Precision@K = 0.923
Recall@K    = 0.923
F1@K        = 0.923

TP = 12
FP = 1
FN = 1
TN = 19
```

---

## 5. V2 Red-Team

6개 회피 시나리오:

1. Time jitter
2. Mule split
3. Micro transaction
4. Normal mix
5. Behavior noise
6. Composite

결과:

| 공격 | V2 F1@K |
|---|---:|
| Time jitter | 0.923 |
| Mule split | 0.769 |
| Micro transaction | 0.923 |
| Normal mix | 0.846 |
| Behavior noise | 0.923 |
| Composite | 0.692 |

해석:

- 시간 랜덤화에는 강함
- 소액 분할에는 강함
- 행동 노이즈에는 강함
- Relay 분산에 취약
- 복합 회피에서 Baseline 대비 우위가 크게 감소
- Hub가 반복적으로 False Negative

---

## 6. CARS V3 설계

V3는 Account Risk에서 Organization Flow 중심으로 확장했습니다.

### 6.1 Relay Set

Primary Receiver 1명이 아니라  
의심 Relay 집합 전체에 전달한 재화 비율을 계산합니다.

예:

```text
Mule 1 = 35%
Mule 2 = 32%
Mule 3 = 25%
Normal = 8%
```

Primary Receiver만 보면 35%지만  
Relay Set 전체로 보면 92%입니다.

---

### 6.2 Organization Path

```text
Source → Relay → Collector
```

구조를 직접 평가합니다.

주요 구성:

```text
source_component
relay_component
hub_component
organization_support
organization_path_score
```

---

### 6.3 Hub Branch

Hub는 행동량이 적어 일반 계정 점수에서 약해질 수 있습니다.

따라서 Hub/Collector 위험도를 독립 branch로 유지합니다.

---

## 7. V3 개발 데이터 결과

V2 Composite Red-Team:

```text
F1@K = 0.692
```

V3 적용 후:

```text
F1@K = 0.923
```

하지만 이 데이터는 V3 설계에 사용되었으므로 개발 성능입니다.

---

## 8. unseen_03 Held-out

V3 설계 이후 새로 생성한 snapshot에서 코드 수정 없이 검증했습니다.

데이터:

```text
Events       = 13,820
Transactions = 1,002
Sessions     = 448
```

결과:

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

Role detection:

```text
Farm = 10 / 10
Mule = 2 / 2
Hub  = 1 / 1
```

---

## 9. V3 Red-Team

`unseen_03` 기반으로 동일 6종 공격군을 새로 생성했습니다.

| 공격 | V3 F1@K | V2 F1@K | Baseline |
|---|---:|---:|---:|
| Time jitter | 1.000 | 0.923 | 0.538 |
| Mule split | 1.000 | 0.846 | 0.538 |
| Micro transaction | 1.000 | 0.923 | 0.538 |
| Normal mix | 1.000 | 0.923 | 0.538 |
| Behavior noise | 1.000 | 0.923 | 0.538 |
| Composite | 1.000 | 0.846 | 0.538 |

모든 공격:

```text
TP = 13
FP = 0
FN = 0
TN = 20
```

---

## 10. 결과 해석 시 주의

다음 표현은 피해야 합니다.

```text
실제 게임 작업장을 100% 탐지한다.
모든 공격을 완벽하게 막는다.
```

권장 표현:

> 신규 synthetic held-out snapshot에서 CARS V3가 Precision@K, Recall@K, F1@K 1.000을 기록했고, 동일 snapshot 기반 6종 정의된 회피 시나리오에서도 F1@K 1.000을 유지했다.

이유:

- 실제 서비스 데이터가 아니라 합성 데이터
- 공격군은 이미 정의된 threat model
- 새로운 공격 전략에 대한 일반화는 별도 검증 필요
- 데이터 생성 정책과 실제 서비스 행동 분포는 다를 수 있음

---

## 11. 프로젝트에서 확인한 핵심 교훈

### 교훈 1

단일 계정 이상점수는 조직형 Farm을 놓칠 수 있다.

### 교훈 2

행동 동기화가 높다고 작업장은 아니다.

Guild는 Farm보다 Sync가 높을 수 있다.

### 교훈 3

Hardcore 사용자는 거래량 때문에 작업장처럼 보일 수 있다.

Counter-evidence가 필요하다.

### 교훈 4

공격자는 단일 Rule을 회피할 수 있다.

Mule split은 Primary Receiver 기반 구조를 약화시킨다.

### 교훈 5

조직 탐지는 Account Risk보다 Organization Flow가 중요하다.

최종 탐지 질문은:

> 이 계정 하나가 이상한가?

가 아니라:

> 이 계정들이 하나의 재화 유통 조직으로 움직이는가?

이다.
