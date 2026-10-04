# GOLD100_SCHEDULE_ztc — gold 100건 라벨링 일정 (초안, 10-05 → 10-09)

- 작성: 2026-10-04, Claude Code (Opus 5.5) 서브에이전트 @ richardkim-macpro. `PHASE2_READINESS_ztc.md` D4("Phase 2 첫 주에 유저 검수 일정") 의 후속.
- 성격: **초안 + 읽기 전용 점검.** 코드·설정·`$PI_ROUTER_HOME` 은 바꾸지 않았다. 후보 수는 원자료를 메모리에서 세기만 했다(파일 쓰기 0). `[제안]` 은 에이전트 제안, **HITL** 은 유저 결정 필요.
- 기준 문서: `docs/PLAN_ZTC_topology_optimization.md`(이하 PLAN), `docs/harness/EVAL_PROTOCOL_ztc.md`(이하 EVAL), `engines/hybrid_router/ztc/gold.py`, `scripts/bench/gold_tool.py`.
- 이 문서에는 개수·날짜·클래스 이름만 싣는다. 오류 본문·명령문·대화 원문·계정·세션 ID 는 싣지 않는다.

## 0. 한 줄 요약
gold 1건 = **마스킹된 Bash 실패 본문 1개에 유저가 붙인 오류 클래스 1개**다. gold 100건이 직접 풀어 주는 것은 **K3 첫 값(Phase 1.6 exit)** 과 **2.4(gold 300) 착수**이고, **K4 는 gold 로 잴 수 없다**(K4 는 실제 주입 뒤의 결과 분류). 실패 본문은 텔레메트리에 저장되지 않으므로 후보는 **트랜스크립트에서 뽑아야** 하며, 그 풀은 09-24 이후 **146건**이다. 하루 20–25건, 하루 15–20분이면 10-09 에 100건이 된다 `[제안]`.

## 1. gold 100 이 무엇이고 무엇이 기다리나

### 1.1 gold 행의 정의
| 항목 | 내용 | 근거 |
|---|---|---|
| 대상 | 실패한 도구 호출(Bash)의 **마스킹된 오류 본문**(≤ 500자) + 이벤트·프로그램 첫 토큰·exit code | EVAL:34-49, `gold.py:30-31` |
| 라벨 | 6클래스 `syntax_compile`·`dependency_missing`·`lint_formatting`·`permission_auth`·`other`·`abstain` | `gold.py:20`, EVAL:45. 앞 4개가 L0 규칙 클래스(`config/anti_pattern_rules.json:29·38·47·55`) |
| 라벨 주체 | `label_source` = `user` 만 평가에 쓴다. `agent-draft` 는 유저 검수 전 평가 제외 | EVAL:46, `gold.py:47·103` |
| 분할 | 세션 단위 tune 70% / holdout 30%, 사후 이동 금지. 같은 시그니처가 두 split 에 있으면 holdout 쪽을 버림. holdout 은 봉인(sha256) 후 한 번만 연다 | EVAL:51-55·81, `gold.py:81-87·104` |
| 저장 | `$PI_ROUTER_HOME/gold/v1.jsonl`(저장소 밖, 0700/0600). 저장소에는 `learning/metrics/gold_stats.json` 집계만 | EVAL:10-13, `gold_tool.py:4-5·24` |
| 마스킹 | 검증기가 비밀 패턴·절대경로·재마스킹 시 바뀌는 문자열이 있는 행을 거부 | `gold.py:57-64`, EVAL:32 |
| 보존 | gold 원자료는 **Phase 2 종료까지**, 종결 때 삭제 여부 재질의 | EVAL:13 |
| 지금 | rows 0, `gold_file_present: false`, `~/.pi-router/gold/` 폴더 없음 `[확인됨]` | `learning/metrics/gold_stats.json`, `PHASE2_READINESS_ztc.md:20` |

### 1.2 gold 를 기다리는 게이트
| 게이트 | 조건 | gold 100 으로 풀리나 | 근거 |
|---|---|---|---|
| **K3** shadow 처방 적합률 | holdout 에서 L0 판정 = 유저 라벨 비율 + Wilson 95% CI, 기권 별칸 | **풀린다(첫 값).** 단 holdout ≈ 30건 → CI 폭 약 ±17%p(예: 15/30 → 0.33–0.67), 클래스별 holdout ≥ 20건은 **어느 클래스도 못 채움** → 전 클래스 "표본 부족" | PLAN:67, EVAL:55·63, `gold.py:22·128-134` |
| K3 비열등(L0 vs 휴리스틱, 마진 3%p) | discordant 쌍 기반 검정력 사전 산정 | **안 풀린다.** n 이 holdout 보다 크면 주장 금지 규칙 | EVAL:74-81 |
| Phase 1.6 exit | gold 100건 + 휴리스틱 실측 정확도 | 풀린다 | PLAN:160·164 |
| **K4** 오처방률 ≤ 10% | 주입된 처방 뒤 채택/해결/재발/포기/회귀 5분류 | **안 풀린다.** shadow 에서는 주입 0 → N/A. gold 는 주입 결과가 아니다 | PLAN:68, EVAL:64, `shadow_aggregate.py:101` |
| **2.1** 개입 opt-in | "K4 ≤ 10% 인 클래스만" + S2 인증 설계 | gold 만으로는 **안 풀린다.** K4 를 재려면 먼저 주입해야 하는 순환이 있다 → §1.3 | PLAN:103·169, `PHASE2_READINESS_ztc.md:34` |
| 2.4 gold 300 + 파레토 | gold 100 선행 | 착수 가능해진다 | PLAN:172, `PHASE2_READINESS_ztc.md:37` |
| L1/L2 삽입 게이트 | gold 에서 L0 미해결 ≥ 20% | 첫 추정치(표본 부족 표기) | PLAN:107 |

### 1.3 2.1 의 순환을 푸는 방법 `[제안]` — **HITL H4**
- K4 는 주입이 있어야 분모가 생긴다. 그래서 2.1 첫 단계(shadow → `additionalContext`)의 **진입** 조건을 gold 기반 대리 지표로 두고, K4 는 **유지** 조건(주입 뒤 실측, 넘으면 클래스 opt-in 해제 — PLAN R2 완화책)으로 쓰는 안.
- 대리 지표 후보: 클래스 X 에 대해 "holdout 에서 L0 가 X 라고 판정한 행 중 유저 라벨이 X 가 아닌 비율"(L0 정밀도의 보수). 이 값 ≤ 10% 이고 그 클래스 판정 건수 ≥ 20 일 때만 그 클래스를 `additionalContext` 대상으로.
- 정직한 한계: gold 100 에서는 클래스별 20건을 못 채우므로 이 대리 지표로도 **10-09 에 opt-in 가능한 클래스는 0개일 가능성이 높다**. 2.1 실주입은 gold 300(2.4) 쪽에서 열린다고 보는 것이 맞다 `[추정]`.

## 2. 후보 풀 (2026-10-04 21:2x KST, 메모리에서 셈)

### 2.1 사실
| # | 출처 | 값 | 근거 |
|---|---|---|---|
| P1 | shadow 텔레메트리 실패 이벤트 | `PostToolUseFailure` **17건**(09-24 1 · 09-25 11 · 09-28 3 · 10-04 2). L0 확정 2건 | `router_events.jsonl` `source`∈miss/l0_ledger/l0_regex |
| P2 | 텔레메트리에 **오류 본문이 없다** | 데몬은 마스킹한 본문으로 판정만 하고, `router_events` 에는 program·exit_code·source·error_class·signature 만 남긴다 → **텔레메트리는 gold 의 `text` 출처가 될 수 없다** `[확인됨]` | `scripts/hybrid-router-daemon.py:82·113-118`, `scripts/hooks/router_client.py:113` |
| P3 | 전환 뒤 수집 속도 | 10-04 20:55–21:26(31분) Bash 144회 · 실패 2건(ztc-phase2-0.1, 세션 4개) | `hook_events.jsonl` |
| P4 | Claude Code 트랜스크립트 Bash 실패 | 09-24 이후 `is_error` 178건 = **"Exit code N" 실패 146** · 차단/거부 13 · 기타 19. 세션 46개, 프로젝트 5개(최다 한 곳 127건 — 쏠림), 서브에이전트 63건 | `~/.claude/projects/*/*.jsonl` 125개 파일 |
| P5 | 일별(P4 전체) | 09-24 15 · 09-25 15 · 09-26 2 · 09-27 36 · 09-28 9 · 09-29 6 · 09-30 3 · 10-01 25 · 10-02 39 · 10-03 10 · 10-04 18 | 같음 |
| P6 | Codex 세션 | 09-24 이후 파일 198개 — **실패 건수는 세지 않음**(형식 다름) | `~/.codex/sessions/2026/` |

→ 쓸 수 있는 풀은 **P4 의 146건 + 하루 약 10–40건 신규**. 100건 목표에는 충분하지만 여유는 작다(중복 시그니처·마스킹 탈락·`abstain` 으로 줄어든다).
→ 다시 세는 방법(읽기 전용): 트랜스크립트의 `tool_use(name=Bash)` id 와 짝인 `tool_result.is_error=true` 를 날짜·프로젝트별로 센다. 본문은 출력하지 않는다.

### 2.2 표본 규칙 `[제안]`
| 규칙 | 내용 | 이유 |
|---|---|---|
| 포함 | Bash `tool_result.is_error` 이고 본문이 "Exit code N"(N≠0) 으로 시작 | gold 대상 = 실제 실행 실패 |
| 제외 | 하네스·훅·권한 거부(유저 거절, Tier-2 deny), 타임아웃, 마스킹 뒤 검증 실패 행, 빈 본문 | 도구 실패가 아니거나 저장 불가 |
| 층화 | 프로젝트 × 프로그램 첫 토큰 버킷 × exit code × 주/서브에이전트. 각 층에서 비례 추출하되 **한 프로젝트 ≤ 50%** | P4 의 한 프로젝트 쏠림(127/178) |
| 상한 | **세션당 ≤ 4건, 같은 시그니처 ≤ 2건** | 한 세션·한 오류 반복이 지표를 지배하지 않게 |
| 분할 | 라벨 **전에** 세션 해시로 결정적 배정(tune 70 / holdout 30). 시그니처가 tune 에도 있으면 holdout 행 제거 | EVAL:52-53, 사후 이동 금지 |
| 여유 | 120건 추출 → 100건 라벨(`abstain`·탈락 대비) | `abstain` 은 K3 평가 제외(`gold.py:103`) |
| 문서 | 이 문서·집계·커밋에는 개수만. 프로젝트는 폴더 마지막 이름만(계정이 든 slug 전체 금지) | EVAL:11 |

## 3. 일정 (10-05 월 → 10-09 금·한글날)
라벨은 **유저**, 추출·층화·tune 초벌(pre-fill)·검증·집계는 **에이전트** `[제안]`. 1건 소요 추정: holdout 블라인드 ≈ 40초, tune 초벌 확인 ≈ 20초 `[추정]`.

| 날짜 | 에이전트 | 유저 라벨(누적) | 유저 시간 | 비고 |
|---|---|---|---|---|
| 10-05 월 | H1–H3 결정 받기 → 추출 도구 작성·시험(합성 데이터) → 120건 추출·분할·검증 | tune 15 (15) — 라벨 기준 맞추기, 애매한 건 기준표(§4.2)에 메모 | 15분 | 저녁 1회. 기준표 확정 |
| 10-06 화 | 전날분 `gold_tool.py validate` | holdout 15 + tune 10 (40) | 20분 | holdout 은 초벌 없이 |
| 10-07 수 | validate, 클래스 분포 중간 보고(개수만) | holdout 15 + tune 10 (65) | 20분 | holdout 30 완료 → **봉인 대기** |
| 10-08 목 | validate. 09-24 텔레메트리 만료 시작(§5 R1) | tune 25 (90) | 10분 | |
| 10-09 금 | validate → holdout 봉인 → `gold_tool.py stats` → K3 첫 값 | tune 10 (100) | 5분 | Phase 2 시작일 |
| 합계 | | **100** | **약 70분** | |

### 3.1 10-09 판정 `[제안]` — **HITL H6**
gold 개수는 **Phase 2 시작일을 바꾸지 않는다** — 100건이어도 K4 는 안 열리고(§1.2), 10-09 첫 착수 항목은 원래 gold 없이 되는 일이다(`PHASE2_READINESS_ztc.md:10`).

| 10-09 상태 | 결정 |
|---|---|
| ≥ 100 (holdout ≥ 30) | Phase 1.6 exit 기록, K3 첫 값(전 클래스 "표본 부족" 표기), 2.4 gold 300 착수. 2.1 은 설계(+H4 대리 지표 산출) |
| 60–99 | Phase 2 예정대로 시작. K3 는 "잠정(n=k)" 로만 기록, 2.4 착수 보류, 라벨 하루 20건으로 계속 → 10-12 전후 100 |
| < 60 또는 holdout < 30 | Phase 2 예정대로 시작, K3 "기준선 미확보" 유지, 2.1 설계만. 일정 재수립 |
| 공통 | **2.1 실주입(K4 게이트 없이 `additionalContext`)은 어느 경우에도 10-09 에 켜지 않는다** (PLAN:103 전환 게이트) |

## 4. 도구와 절차

### 4.1 있는 것 / 없는 것
| 도구 | 상태 | 근거 |
|---|---|---|
| 스키마 검증·집계 `ztc/gold.py` | 있음(합성 시험 `tests/test_gold.py`) | `gold.py:28-138` |
| `scripts/bench/gold_tool.py validate`·`stats` | 있음. **행을 만들지 않는다**("labelling is a user review step") | `gold_tool.py:2-5` |
| 후보 추출기(트랜스크립트 → 마스킹 후보) | **없음** | — |
| 라벨 입력 CLI | **없음** | — |

### 4.2 최소 도구안 `[제안]` (작성하지 않음 — **HITL H2**)
`scripts/bench/gold_draft.py` 하나, 하위 명령 2개. 쓰기는 `$PI_ROUTER_HOME/gold/` 에만(0700/0600, 저장소 안 경로 거부 — `ztc.paths` 재사용).
1. `extract --since 2026-09-24 --n 120 --seed <고정>`: 트랜스크립트에서 §2.2 규칙대로 뽑아 `gold/candidates.jsonl` 에 저장. 행마다 `mask_text`(클라이언트와 같은 마스커, cwd 마스킹) → 500자 절단 → `gold.validate_row` 통과분만. `group.session` = 세션 ID sha256 앞 12, `group.signature` = `l0.signature()`, `group.project` = 폴더 마지막 이름, `attribution` = `l0.attribution()`, `split` = 세션 해시 결정적 배정. **tune 행에만** `draft_label`(L0 regex, 없으면 비움) 을 붙인다.
2. `label [--split holdout|tune]`: 한 건씩 마스킹 본문·프로그램 첫 토큰·exit code 만 보여 주고 숫자키 1–6 으로 라벨, `s` 건너뜀, `q` 저장 후 종료. 저장 시 `label_source: "user"`, `created_at`, `v1.jsonl` 에 추가. holdout 은 초벌을 **보여 주지 않는다**.
- 시험: 합성 트랜스크립트 픽스처만 사용(실데이터 금지), `gold_tool.py validate` 0 errors 확인.
- 왜 holdout 블라인드인가: K3 는 "L0 = 유저 라벨" 비율이므로 L0 초벌을 보고 고르면 K3 가 부풀고(앵커링), 휴리스틱 초벌이면 paired 비교가 기운다(EVAL:76).
- 초벌을 LLM 으로 만들지 않는 이유: 마스킹 본문이 새 트랜스크립트에 복사된다. 로컬 regex 초벌이면 복사 0.

### 4.3 라벨 기준표 초안 `[제안]` (10-05 보정)
| 키 | 클래스 | 이럴 때 |
|---|---|---|
| 1 | `syntax_compile` | 구문·타입·컴파일 오류(파서·컴파일러가 거부) |
| 2 | `dependency_missing` | 모듈·패키지·명령·파일이 없어서 실패 |
| 3 | `lint_formatting` | 린터·포매터·스타일 검사 실패 |
| 4 | `permission_auth` | OS 권한·인증·토큰·접근 거부(하네스의 도구 거절은 §2.2 에서 이미 제외) |
| 5 | `other` | 위 넷이 아닌 실패(테스트 실패, 네트워크, 로직 오류 등) |
| 6 | `abstain` | 본문만으로 판단 불가 — K3 평가에서 빠짐 |

## 5. 위험
| # | 위험 | 영향 | 대응 |
|---|---|---|---|
| R1 | 텔레메트리 14일 자동 삭제 — 09-24·25 레코드가 10-08~09 에 사라짐 | gold `text` 와는 무관(본문은 텔레메트리에 없음, P2). 영향은 K1/K2 재집계·gold 행과 `request_id` 대조 불가 | K1/K2 는 10-04 집계로 이미 남김(`shadow_k1k2_20261004.json`). 대조가 필요하면 10-07 까지 개수만 뽑아 둔다 | 
| R2 | 트랜스크립트 보존 기한 | `~/.claude/settings.json` 에 `cleanupPeriodDays` 없음 → 기본값(30일)이면 09-24분이 10-24 전후 삭제 `[추정: 기본값]` | 10-05 추출로 후보를 `gold/` 에 고정 |
| R3 | 개인정보 — 오류 본문에 경로·호스트·토큰·대화 조각 | 저장소·문서 유출 | 원자료는 `gold/` 에만, 저장소에는 개수만. 검증기 거부 규칙(`gold.py:57-64`). 이 문서·커밋·보고에 본문 인용 금지. 마스킹은 소급 불가한 transcript 원문에서 새로 하는 것이므로 **추출 직후 validate 0 errors** 를 매일 확인 |
| R4 | 쏠림 — 한 프로젝트 127/178 | K3 가 한 작업 스타일을 대표 | §2.2 상한(프로젝트 ≤ 50%, 세션 ≤ 4) |
| R5 | holdout 30 · 클래스별 < 20 | K3 CI 넓음, 클래스 주장 불가 | 보고 문구에 n·CI·"표본 부족" 고정. 클래스 주장은 2.4(300) 뒤 |
| R6 | 라벨러 1인 | 일관성 검증 없음(카파 불가) | 10-09 에 tune 10건 재라벨(블라인드)로 자기 일치율만 보고 `[제안]` |
| R7 | live 저장소 | `gold_draft.py` 커밋·`gold/` 생성은 live 환경 변경 | 도구 커밋·폴더 생성 각각 승인(H1·H2) |

## 6. 결정 필요 (HITL)
| # | 질문 | 추천안 |
|---|---|---|
| H1 | gold 후보 출처를 트랜스크립트(Claude, +Codex?)로 하고 `~/.pi-router/gold/` 를 만들어도 되나 | Claude 트랜스크립트만, 폴더 생성 승인. Codex 는 2.4 에서 |
| H2 | `gold_draft.py`(extract·label) 를 이 저장소에 작성·커밋해도 되나 | 작성 → 합성 시험 → 커밋(push 는 별도) |
| H3 | 표본 규칙(§2.2: 제외 대상·층화·세션 ≤ 4·시그니처 ≤ 2·120 추출) | 그대로 |
| H4 | 2.1 진입을 gold 대리 지표(클래스별 L0 오판정 ≤ 10%, n ≥ 20)로 두고 K4 는 유지 조건으로 바꿀지 — PLAN 2.1 문구 변경 | 채택하되 PLAN 버전 올림. 10-09 에는 산출만 |
| H5 | 초벌 정책: holdout 블라인드, tune 만 L0 regex 초벌, LLM 초벌 없음 | 그대로 |
| H6 | 10-09 에 100 미만일 때 처리(§3.1) | Phase 2 예정대로 시작, 2.1 실주입 없음, 라벨 계속 |
| H7 | 라벨 시간대·분량(하루 15–20분, 5일 약 70분) | 그대로, 저녁 1회 |

## 7. 이 문서가 하지 않은 것
- 오류 본문 출력·인용(P4 의 종류는 메모리에서 첫 줄 형식·키워드로만 나눠 셈), 클래스 분포 추정.
- Codex 세션의 실패 건수 집계.
- 도구 작성·`gold/` 생성·커밋.
