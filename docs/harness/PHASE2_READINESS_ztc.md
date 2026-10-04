# PHASE2_READINESS_ztc — Phase 2(2026-10-09~) 시작 전 준비 상태 점검

- 작성: 2026-10-04, Claude Code (Opus 5.5) @ richardkim-macpro (youtube-ext-atom 세션, 유저 AUQ 결정 "N ∥ P4 → Z"의 Z).
- 성격: **읽기 전용 점검 결과.** 코드·설정·launchd·`~/Pi` 사본은 바꾸지 않았다. 아래 "결정 필요"는 유저 몫이다.
- 기준 문서: `docs/PLAN_ZTC_topology_optimization.md` §Phase 1·§Phase 2, `docs/harness/EVAL_PROTOCOL_ztc.md`, `docs/harness/AB_EVAL_ztc.md` v0.2(`~/Pi` 사본과 바이트 동일, 2026-10-04 diff).
- 원자료: `~/.pi-router/telemetry/*.jsonl`(저장소 밖). 이 문서에는 개수·날짜만 싣는다.

## 0. 한 줄 요약
Phase 2 의 첫 항목(2.1 advisory opt-in)은 **K4 오처방률 ≤ 10%** 를 진입 조건으로 하는데, gold 가 0건이라 K4·K3 를 잴 수 없다. shadow 수집도 09-28 이후 멈춰 있고 10-02 첫 집계는 하지 않았다.
그래서 10-09 에는 **gold 없이 되는 일(수집 재개·10-02 집계 보충·U5 `arm` 필드·2.5 K7 집계 스크립트·2.3 L3 mock)** 부터 시작하는 것이 맞다 `[추정: 계획 문서 순서에서 도출]`.

## 1. 사실 (2026-10-04 19:4x KST 확인)

| # | 항목 | 상태 | 근거 |
|---|---|---|---|
| F1 | shadow 훅 수집 | `hook_events` 731건 — 날짜별 09-24 18 · 09-25 647 · 09-28 66. **09-28 21:24 이후 0건** `[확인됨]` | `hook_events.jsonl` 마지막 ts, `router_events.jsonl` 720건 같은 시각 |
| F2 | 멈춘 원인 | 고장이 아니다. router-client 훅은 **`~/Pi` 프로젝트 설정에만** 등록돼 있고(`~/Pi/.claude/settings.json:119·132·145`), `~/Pi` 에서 Claude Code 가 Bash 를 쓴 마지막 시각이 09-28 21:24 다(Pi 트랜스크립트 Bash 호출 시각과 일치). 개발이 이 저장소로 옮겨 왔고, 이 저장소에는 `.claude/` 가 없다 `[확인됨]` | 트랜스크립트 집계, `ls .claude` |
| F3 | 데몬 | 정상 — `health_status.json` status ok, daemon ready(10-04 19:44) `[확인됨]` | healthcheck 2,219건 |
| F4 | 10-02 K1/K2 첫 집계 | **하지 않음.** `learning/metrics/` 최신 파일이 09-24(`bench_20260924.json`·`shadow_k1_20260924.json`) `[확인됨]` | `EVAL_PROTOCOL_ztc.md:14` 가 요구 |
| F5 | gold·K3 | `gold_stats.json` rows 0, `gold_file_present: false`, K3 "기준선 미확보 (gold 부재)" `[확인됨]` | Phase 1.6 "gold 100건"은 미달 |
| F6 | 훅 결과 분포 | ok 711 · timeout 9 · absent 7 · disabled 4 `[확인됨]` | `hook_events.outcome` |
| F7 | 평가 편입 게이트 | `config/ab_gate.json` enabled(09-25 유저 지시로 전역). 질의 115 · 답 apply 15 · skip 19 · same_loop 65 · not_loop 14 `[확인됨]` | `ab_gate.jsonl` 506줄 |
| F8 | 편입 후보의 적격성 | AB_EVAL §2.2 적격 = **Pi 저장소 안에서 로컬 파일·로컬 테스트로 끝나는 루프**. 원격 노드(SSH·TeamViewer)·NV 저장소·공유 외부 서비스를 건드리면 부적격. apply 15건 중 상당수는 다른 저장소(youtube-ext-atom 등)·원격 노드 루프다 — 예: 이 점검을 낳은 루프(gate `31e6d883e2d8`)도 NVG SSH 디스패치를 포함해 부적격 `[추정: 건별 대조 안 함]` | §2.2, U6 "혼합 6블록" |
| F9 | A/A 보정 | U2 가 승인한 Phase 1 A/A 2쌍(루프 4개) — 실행 증거 없음 `[확인됨: docs/evidence 에 A/A 0건]` | `docs/evidence/` 는 phase1·merge·plan-review 4개뿐 |
| F10 | U5 텔레메트리 필드 | `session`(session_id sha256 12자)은 이미 있음(`scripts/hooks/router_client.py:70`). **`arm`(`PI_AB_ARM`) 없음**, `CLIENT_VERSION = "ztc-phase1-0.1"`(`:42`) `[확인됨]` | grep |
| F12 | 분리 때 빠진 경로 | `scripts/bench/`(hook_bench·gold_tool)와 `learning/metrics/` 가 `docs/MIGRATION_PATHS.txt` 에 없어 Pi 에만 있었다. `METRICS_DIR` 은 이 저장소를 가리킴 → 2026-10-04 보충 이관(D4) `[확인됨]` | README "분리 방식" |
| F13 | 원자료 보존 | 텔레메트리 14일 자동 삭제(`EVAL_PROTOCOL_ztc.md` §0) — 09-24·25 원자료는 10-08~09 에 사라진다. D2 집계는 그 전에 해야 함 `[확인됨]` | `telemetry.prune()` |
| F11 | 실행 기준 전환 | 아직 `~/Pi` 가 live(launchd 2개·훅 3곳). 전환은 "첫 집계 뒤 별도 유저 승인"(README) — 첫 집계(F4)가 없어 조건 미충족 `[확인됨]` | README "정본과 실행 기준" |

## 2. Phase 2 WBS 별 준비

| WBS | 선행 조건 | 지금 | 10-09 착수 가능? |
|---|---|---|---|
| 2.1 개입 opt-in(shadow → additionalContext → deny/updatedInput) | K4 ≤ 10% 인 클래스(gold 필요), S2 호출자 인증 설계(PLAN §5.4 S2) | gold 0, S2 미설계 | **설계만**(S2 인증·opt-in 스위치 구조). 실제 주입은 K4 뒤 |
| 2.2 로컬 프리페치 워커 | 규칙표 10개, S1 `updatedInput` 병합 순서 실측 | 미착수 | 가능(규칙표·취소 시나리오부터) |
| 2.3 L3 실 HTTP + 스키마 | mock 서버 | 미착수 | 가능(mock 우선, 신규 유료 호출 0) |
| 2.4 gold 300 + 파레토 | gold 100(Phase 1.6) | 0 | **불가** — gold 라벨링 일정이 먼저 |
| 2.5 K7 집계 | 세션 토큰 원자료(트랜스크립트) | 미착수(AB_EVAL E2 도 이것을 기다림) | 가능 — A/A·A/B 모두의 1차 지표(E2) 선행 |
| 2.6 L1/L2 게이트 판정 | §10-5 근거 | — | Phase 2 끝 |
| (AB) A/A 2쌍 | U5 `arm` 필드, 적격 루프 지시문 6블록 고정(U6), 포트 9877 데몬(U7) | `arm` 없음, 블록 미고정 | `arm` 추가 뒤 가능 |

## 3. 결정 필요 (유저)

| # | 질문 | 추천안 | 근거 |
|---|---|---|---|
| D1 | shadow 수집을 어떻게 재개하나 | router-client 훅을 **전역 Claude Code 설정**(파일 존재 가드 그대로)으로 옮기거나, 최소한 이 저장소에도 프로젝트 훅을 둔다. 전역이면 cwd 마스킹이 이미 있으므로 다른 저장소 작업도 shadow 표본이 된다 | F1·F2 — Pi 에서 작업이 없으면 표본이 영영 0. 전역 등록은 live 설정 변경이라 승인 게이트 |
| D2 | 10-02 첫 집계를 지금 있는 731건으로 할지 | **한다**, 단 "수집 3일분(09-24·25·28), 7일 창 미충족"을 정직하게 표기 | F4. 전환(F11)의 조건이 "첫 집계"라 이것이 막힌 고리 |
| D3 | 실행 기준 전환(`~/Pi` → 이 저장소) 시점 | D2 집계 직후, D1 과 **한 번에**(훅 경로를 바꿀 때 전역 등록도 같이) | 훅·launchd 경로를 두 번 건드리지 않음 |
| D4 | gold 100건 라벨링 | Phase 2 첫 주에 유저 검수 일정을 잡는다. 그 전까지 2.1 은 설계만 | F5. K3·K4·2.4 가 모두 gold 를 기다림 |
| D5 | 편입 게이트의 범위 | 게이트는 계속 묻되, **답이 apply 여도 §2.2 적격 검사를 한 줄 덧붙여** 후보 원장에 적격/부적격을 같이 남긴다(코드 변경, 별도 승인) | F7·F8 — 지금 apply 후보 대부분이 실험에 못 쓰임 |
| D6 | U5 `arm` 필드와 CLIENT_VERSION 올림 | 2.x 첫 커밋으로 넣는다(`ztc-phase2-0.1`) | F10, A/A 선행 |

## 3.1 유저 결정 (2026-10-04 AUQ) 과 집행
- D1 전역 훅 추가 · D2 지금 731건으로 집계 · D3 D2 뒤 D1 과 한 번에 전환 · D4·D5·D6 ztc-router 정본에만(live 반영은 전환 때).
- **D4 집행** `b00cf22`: `scripts/bench/`·`learning/metrics/` 보충 이관(F12).
- **D2 집행:** `scripts/bench/shadow_aggregate.py`(개수·분위수만, 프로그램명·서명 미출력, 합성 시험 3건) → `learning/metrics/shadow_k1k2_20261004.json`.

| 지표 | 값 | 목표 | 판정 |
|---|---|---|---|
| 수집 | 731건, 데이터 있는 날 3일(09-24 18 · 09-25 647 · 09-28 66) | 7일 창(09-25~10-02) | **창 미충족** |
| K1 내부 RPC (ok 711) | p50 2.41 · p95 5.90 · p99 16.99 · max 25.48 ms | p99 ≤ 30 ms | 충족 |
| K1 클라이언트(인터프리터 기동 제외) | p50 2.55 · p95 6.05 · p99 17.12 ms | 보고만 | — |
| K1 타임아웃률 | 9/731 = 1.23% | < 1% | **미달** — 09-24 의도적 SIGSTOP 시험분(그날 6건, `shadow_k1_20260924.json` timeout_note)이 섞임 `[추정: 원자료에 시험 표지 없음]`. 그것을 빼면 3/725 ≈ 0.41% |
| K2 무토큰 분류율 | L0 확정 1 / 실패 Bash 15 = 6.7%(첫 관측 0 · 원장 재관측 1, syntax_compile) | ≥ 50% | **미달** — 표본 15건 |
| K3 | 기준선 미확보 (gold 부재) | — | — |
| 전체 지연(하네스 durationMs) | 텔레메트리에 없음 — 측정 안 함 | 보고만 | — |

## 4. 이 점검이 하지 않은 것
- apply 15건의 건별 적격 판정(F8 은 표본 1건 + 규칙으로 추정).
- `~/Pi` 사본과 이 저장소의 코드 차이 대조(AB_EVAL 문서만 대조).
- 텔레메트리 내용 열람(개수·날짜·outcome 만 셈).
