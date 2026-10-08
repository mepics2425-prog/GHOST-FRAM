# 합성 사용자 유형

Aetheria에는 실제 플레이어 외에 36명의 합성 주민이 존재합니다.

합성 주민의 역할은 모델에 직접 입력되지 않으며 Ground Truth 평가에만 사용됩니다.

---

## 유형 분포

| 유형 | 계정 수 |
|---|---:|
| Normal | 10 |
| Hardcore | 4 |
| Guild | 6 |
| Bot | 3 |
| Farm | 10 |
| Mule | 2 |
| Hub | 1 |
| 합계 | 36 |

---

## Normal

일반적인 변동성을 가진 정상 계정입니다.

특징:

- 여러 행동 수행
- 불규칙한 접속
- 거래 상대 다양
- 특정 계정으로 지속적인 재화 수렴 없음

---

## Hardcore

활동량이 매우 높은 정상 사용자입니다.

특징:

- 긴 플레이 시간
- 높은 Event volume
- 높은 거래량
- 다수 사용자와 양방향 거래

이 유형은 중요한 False Positive challenge입니다.

단순히:

```text
거래량이 많다
활동량이 많다
여러 명과 거래한다
```

만으로 위험 판정을 하면 Hardcore 계정을 작업장으로 오탐할 수 있습니다.

---

## Guild

정상 협동 플레이 그룹입니다.

특징:

- 로그인 시간 유사
- 행동 패턴 유사
- 같은 지역에서 활동
- 높은 행동 동기화

실험에서 Guild의 평균 Sync가 Farm보다 더 높게 나타나는 경우가 반복되었습니다.

따라서:

> 높은 Sync = 작업장

이라는 규칙은 사용할 수 없습니다.

CARS에서는 Sync를 독립 위험 신호로 사용하지 않고 재화 Funnel과 결합합니다.

---

## Bot

반복 행동 계정입니다.

특징:

- 낮은 행동 다양성
- 반복 주기
- 유사한 행동 패턴

Bot은 일반 이상탐지 평가에서는 양성이지만,  
Farm/Mule/Hub를 대상으로 하는 organized abuse 평가에서는 별도로 분리합니다.

---

## Farm

재화를 생산해 Relay로 보내는 계정입니다.

설계 의도:

- 개별 행동은 정상 사용자와 유사
- 채집/전투/퀘스트 등 다양한 행동 수행
- 단순 Isolation Forest에서는 정상처럼 보일 수 있음
- 재화 흐름을 보면 Relay 방향성이 드러남

V2에서는 Primary Receiver Share를 사용했으나 Mule Split 공격에서 약점이 드러났습니다.

V3에서는 단일 Receiver가 아니라 Relay Set 전체로 이동한 재화 비율을 평가합니다.

---

## Mule

다수 Farm의 재화를 받아 최종 Hub로 중계하는 계정입니다.

정상 Hardcore 거래와 구분하기 위해 중요한 요소:

- 여러 Source에서 유입
- 최종적으로 소수 Collector 방향으로 유출
- 높은 Flow-through
- Downstream Hub affinity

Hardcore 계정은 거래량은 많지만 보통 유출 상대가 넓게 분산됩니다.

---

## Hub

조직의 최종 재화 집결 계정입니다.

특징:

- 높은 Incoming Gold
- 낮은 Outgoing
- 플레이 행동은 상대적으로 적을 수 있음
- 여러 Relay에서 자금 수신

V2에서는 다른 계정 점수와 합산되면서 반복적으로 False Negative가 발생했습니다.

V3에서는 Hub/Collector branch를 별도로 유지해 이 문제를 보완했습니다.

---

## 조직 구조

```text
Farm × 10
   ↓
Mule × 2
   ↓
Hub × 1
```

실제 탐지 문제는 특정 역할 하나를 맞히는 것보다:

> 여러 계정의 재화가 Relay를 거쳐 동일 Collector로 수렴하는가?

를 찾는 것입니다.
