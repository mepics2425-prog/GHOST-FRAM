# Aetheria : Moonberry Village

GHOST FARM · 게임 이상탐지 분석가 포트폴리오용 **플레이 가능한 Canvas RPG + 합성 행동/거래 로그 생성기**.

작은 토끼 캐릭터로 마을과 숲, 동굴을 탐험하며 채집·전투·퀘스트·판매·거래를 진행합니다. 36명의 합성 주민도 실제로 이동하고 자원을 사용하며 거래합니다. 분석의 핵심 질문은 “개별 계정이 정상처럼 보여도 행동 동기화와 재화 흐름을 함께 보면 조직 구조가 드러나는가?”입니다.

![게임 화면](docs/game.png)

## 실행

**설치 없이:** `index.html`을 Chrome 또는 Edge에서 엽니다. 모든 JS/CSS는 로컬 상대 경로이며 외부 이미지, 폰트, 라이브러리 의존성이 없습니다. 브라우저에 따라 `file://` 저장 정책이 다를 수 있어 아래 방법을 권장합니다.

**권장:** Node.js가 있으면 프로젝트 폴더에서 실행합니다.

```sh
node server.cjs
```

브라우저에서 `http://127.0.0.1:4173`을 엽니다. `npm start`도 같습니다. 서버는 localhost 전용입니다. Windows에서는 `start-game.cmd`를 사용할 수 있습니다.

1. 이메일 / 8자 이상 비밀번호로 회원가입하거나 게스트로 입장합니다.
2. 캐릭터 이름을 입력해 생성한 뒤 **모험 시작**을 누릅니다. 계정당 최대 8개 슬롯입니다.
3. **WASD / 방향키** 이동, **Shift** 대시, **E** 가까운 대상과 상호작용, **Space** 공격.
4. 마을 왼쪽의 **모모**에게 퀘스트 3개를 수락합니다.
5. 숲에서 딸기 6개와 별결정 2개를 채집하고 동굴에서 슬라임 3마리를 처치합니다.
6. **포포**에게 별결정을 판매하고 모모에게 보상을 받습니다. 호수에서는 서서 쉬면 HP가 회복됩니다.
7. **루나**에게 매물을 등록/취소/구매합니다. 움직이는 주민을 클릭하면 골드를 전송할 수 있습니다.
8. 운영자 모드에서 유형과 실제 거래 그래프를 확인하고 CSV/JSON을 내려받습니다.

자동 저장은 5초 간격, 거래·캐릭터 생성 등 주요 변경 시 즉시 수행합니다. 새로고침하면 로그인 상태와 선택 캐릭터, 골드·HP·EXP·인벤토리·퀘스트·월드 상태를 복구합니다. 페이지가 닫힌 동안 게임 시간은 진행하지 않습니다.

## 구현 범위

| 영역 | 실제 동작 |
|---|---|
| Authentication | Local 회원가입/로그인/오류 처리, 게스트, 세션 복구, Supabase REST 어댑터 |
| Character | users/characters 분리, 다중 캐릭터 생성·선택·저장 |
| Game Engine | 5개 연결 지역, 이동·대시, idle/walk/gather/attack/damaged 애니메이션 |
| Gathering | 실제 오브젝트 근접 채집, 1.1초 진행, 이동 취소, 수량/EXP, 18초 재생성 |
| Combat | 이동하는 슬라임 HP/피격/사망/15초 재생성, 플레이어 피해, 골드/EXP/젤 보상 |
| Quests | 딸기 6개 전달, 수락 후 슬라임 3회 처치, 수락 후 별결정 2개 판매, 보상 중복 방지 |
| Inventory / Shop | 4종 아이템, 실제 수량, 시세의 80%로 판매, 25 G 회복 |
| Economy / Transaction | 시세 변동, 등록 에스크로·취소·구매, 잔액 검증, 주민 간 골드 전송 |
| NPC Behavior | 36명, 7개 숨겨진 유형, 접속/종료 일정, 이동·채집·사냥·휴식·퀘스트·거래 |
| Organization | 10 Farm → 2 Mule → 1 Hub 실제 골드 이동, 30,000 G 기준 토큰의 500 G 지정 판매 |
| Event Logger | 실시간 JS 배열, 이벤트/거래/플레이 세션 기록, CSV 3종/전체 JSON 다운로드 |
| Operator Tools | ground truth 전용 목록·계정 상세·거래 금액 비례 방향 그래프 |

**20개 MVP 항목은 Local Demo Mode에서 구현 및 검증했습니다.** 상점과 거래소는 주민에게 가까이 다가가서 열고, 사용자 송금은 선택한 주민에게 보낼 수 있습니다. NPC의 사냥/채집도 월드 오브젝트를 소비하므로 플레이어와 경쟁할 수 있습니다.

## 코드 구조

```text
index.html              로그인 / 선택 / 플레이 / 운영자 UI
css/game.css            반응형 파스텔 UI
js/config.js            Supabase 공개 설정
js/store.js             상태 모델, localStorage, 지역/아이템 정의
js/auth.js              Local PBKDF2 인증 / Guest / Supabase REST 어댑터
js/game.js              게임 루프, 이동, 채집, 전투, 퀘스트
js/render.js            Canvas로 직접 그린 월드·토끼·오브젝트·슬라임
js/npc.js               합성 주민 스케줄과 행동, 조직 송금
js/economy.js           재화 변경, 거래 검증, 에스크로, 시장
js/logger.js            이벤트 / 거래 / 세션 / CSV·JSON
js/operator.js          ground-truth inspection과 그래프
js/app.js               화면·입력·NPC 대화·상점·UI 연결
server.cjs              의존성 없는 로컬 정적 서버
tests/integrity.cjs     Node 무결성 및 12시간 시뮬레이션 테스트
tests/browser.cjs       선택 설치형 실제 브라우저 E2E
docs/                   스키마, 유형, 검증 보고서, 스크린샷
data/sample/            실제 엔진 및 브라우저에서 생성한 샘플
```

## 데이터 분석 시 주의

운영자 그래프는 **ground-truth inspection**입니다. CARS나 다른 이상탐지 모델을 실행한 결과가 아닙니다. 일반 플레이 UI에는 `user_type`이 표시되지 않습니다. 이벤트/거래 CSV에도 유형 라벨이 없습니다. JSON의 `ground_truth`를 평가용 정답으로 별도 보관하세요.

세계 시간 배속은 1× / 60× / 360×입니다. 이벤트 timestamp와 세션 play_time은 **세계 시간**, 이동·채집 진행·공격 쿨다운·재생성은 **실시간**입니다. 배속 변경은 이벤트에 기록됩니다. 브라우저 탭이 숨겨지면 프레임이 제한될 수 있어 연속 장기 수집에는 활성 탭을 사용하세요. 로그인 노이즈 1~5분은 세계 시간 기준입니다. 기본 60×에서 약 1~5초 뒤 Farm이 접속합니다.

로컬 로그는 최대 이벤트 12,000 / 거래 6,000 / 세션 3,000행의 순환 버퍼입니다. 더 작은 브라우저 저장 한도에서는 오래된 로그를 먼저 줄여 캐릭터 상태를 저장합니다. 삭제 수는 `retention.dropped`와 운영자 패널에서 확인할 수 있습니다. 장기 수집 전/중간에 Export하세요. 순환 후 전체 과거 거래/세션을 재구성하려면 이전 Export도 필요합니다.

`SYSTEM_SHOP`은 무한 재화 원천/소각 계정입니다. 사냥·퀘스트 보상도 게임 내 발행 재화입니다. 사용자 간 송금과 거래소 구매는 두 사용자 간 잔액 합계를 보존합니다. 초기 NPC 보유 자산과 토큰은 명시적인 시드 자산입니다. 이 데이터는 합성이며 실제 위메이드 서비스의 계정·IP·행동을 나타내지 않습니다.

자세한 내용: [로그 스키마](docs/log-schema.md), [합성 유형](docs/synthetic-users.md), [검증 보고서](docs/verification.md).

## Supabase 연결

기본값은 빈 설정으로 Local Demo Mode입니다. `js/config.js`에 `supabaseUrl`과 **공개 anon key**를 지정하면 `/auth/v1/signup`, `/auth/v1/token?grant_type=password`, `/auth/v1/user` REST 어댑터를 사용합니다. 메일 인증이 필요하면 가입 후 메일 확인 안내를 표시합니다. 만료된 access token은 재로그인을 요청합니다.

**현재 제공된 인증 정보가 없어 실제 Supabase 서버 연결은 검증하지 않았습니다.** Supabase 모드도 캐릭터/월드/로그는 이 브라우저에 저장합니다. 서버 DB 동기화, refresh token 자동 갱신, RLS, 운영자 권한은 다음 단계입니다. Local 계정 비밀번호는 PBKDF2-SHA256(120,000회) 해시와 salt를 저장하지만 로컬 데모 인증이며, 실서비스 권한 경계가 아닙니다. 공개키 외에 서비스 역할 키를 넣지 마세요.

## 테스트

의존성 없는 데이터 테스트:

```sh
node tests/integrity.cjs
node tests/integrity.cjs --sample
```

브라우저 테스트는 별도 개발 환경에서 Playwright를 설치한 뒤 로컬 서버를 실행하고 수행합니다.

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/browser.cjs
node tests/regression.cjs
```

`PLAYWRIGHT_PATH`로 설치 경로, `BROWSER_CDP_URL`로 테스트 전용 Chromium 연결을 지정할 수도 있습니다. 테스트는 별도 브라우저 context를 사용하며 실사용 계정에 접근하지 않습니다. 서버에 API/DB 호출이 없는 Local Mode는 UI → 엔진 → 상태/로그 → localStorage → 재로드까지 검증합니다.

## 아직 구현하지 않은 기능과 다음 순서

1. Python의 1,000계정 이상 오프라인 생성기와 시드/기간별 재현 가능한 실험 데이터셋.
2. 행동 엔트로피·주기성 baseline, 동기화/공유 환경/재화 그래프 feature 추출, Hardcore/Guild false-positive 평가.
3. CARS 또는 그래프 기반 조직 이상탐지 모델, train/test 기간 분리 및 정답 누출 방지.
4. Supabase의 서버 저장·RLS·운영자 권한·자동 토큰 갱신, 장기 로그의 DB/IndexedDB 보관.
5. 충돌/길찾기, 카메라 확대·추적, 모바일 터치 조작, 장비/낚시/파티 전투 확장.

현재는 브라우저 내부의 가상 다중 사용자 세계입니다. 네트워크 멀티플레이, 실서비스 보안, 장애 복구 서버는 포함하지 않습니다. 나무/집/물은 장식 지형이고 맵 경계 외 지형 충돌은 아직 없습니다.
