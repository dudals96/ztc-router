# PLAN — Pi 토폴로지 ZTC 고도화 · 분산 추측 실행 체계 구축 (실행 계획 초안 v0.1)

- Status: **DRAFT v0.1 — 유저 승인 대기** (§9 의 결정 항목이 확정되기 전에는 Phase 1 착수만 가능)
- 작성: Claude Code (Fable 5.1) @ richardkim-macpro-macbookpro, 2026-09-23
- 발주: 유저 지시문 "Pi 토폴로지 생산성 극대화 및 ZTC 기반 분산 라우터 고도화 프로젝트 실행 계획 수립 요청" (원문: `learning/user-prompts/2026-09-23_Wed/04_ztc-topology-plan-request.md`)
- 참조: `docs/PROJECT_BRIEF.md`, `ai_guidelines.md`, `docs/AGENT_COUNCIL_PROTOCOL.md`, `engines/hybrid_router/`, `scripts/decision-gate-interceptor.py`, NV `docs/harness/PLAN_C2_worker_loop_20260922.md`, NV `docs/harness/NORTH_STAR.md`

---

## 0. 쉬운 말로 (ai_guidelines §8 자동 발동)

식당 주방에 비유하면 지금 상황은 이렇다. 손님(코딩 에이전트)이 주문할 때마다 셰프(LLM)가 처음부터 생각해서 요리하면 느리고 비싸다. 그래서 주방 입구에 **주문 접수원(Laya 라우터)** 을 세워 "이건 늘 나오는 메뉴니까 셰프 부르지 말고 바로 내보내" 라고 판단하게 만들었다. 그런데 지금 접수원은 진짜 훈련된 접수원이 아니라 **메뉴판 키워드를 눈으로 훑는 아르바이트생**이고, "18ms 만에 판단했다" 는 명찰은 실제 시간이 아니라 명찰에 미리 인쇄된 숫자다. 이 계획의 첫 단계는 스톱워치로 실제 시간을 재는 것이다.

두 번째 단계는 접수원을 **4단 계단**으로 바꾸는 것이다. ① 똑같은 주문은 장부를 보고 0초에 처리, ② 비슷한 주문은 냄새(임베딩)로 5ms 안에, ③ 애매하면 훈련된 접수원(진짜 Laya 모델) 이 30ms 안에, ④ 그래도 모르면 셰프. 세 번째 단계는 **손님이 다음에 뭘 시킬지 미리 예측해서 보조 주방(Windows 노드)에 재료 손질을 시켜 두는 것**(추측 실행)이다. 단, 이 집 규칙상 보조 주방은 사장님 도장이 찍힌 주문서 없이는 칼을 들 수 없다. 그래서 "도장 한 번으로 허용되는 손질 목록" 을 먼저 정해야 한다.

---

## 1. 현황 실측 — 계획의 출발점 (2026-09-23, 이 세션에서 비파괴 실측)

계획의 KPI 는 **문서에 적힌 숫자가 아니라 실측값**을 기준선으로 삼는다. 이번 세션에서 확인한 사실:

| 항목 | 문서·코드가 주장하는 값 | 실측/확인 결과 | 근거 |
|---|---|---|---|
| Laya 추론 엔진 | ModernBERT/mmBERT 단일 forward pass, 18.5 ms | **키워드 휴리스틱 시뮬레이션**. 순수 연산 **0.003 ms**. `latency_ms` 는 `min(elapsed+18.5, 34.2)` 상수 | `engines/hybrid_router/hierarchical_routing/hierarchical_engine.py:180` |
| 라우터 파이프라인 지연 | ≤ 38.5 ms | `min(total, 38.5)` 로 **상한 캡 처리**된 값 | `engines/hybrid_router/router_core.py:73` |
| 인터셉터 훅 왕복 | 18 ms | **57.7 ms p50**(데몬 다운·로컬 폴백 경로). 내역: Python 기동 17.4 ms + 표준 import 35 ms + 나머지 | 스크래치패드 실측 7회 중앙값 |
| 데몬(9876) | 상시 가동 | **현재 미가동**, launchd 미등록 | `pgrep -fl hybrid-router` 없음, `~/Library/LaunchAgents` 에 항목 없음 |
| 절감 토큰 | 155,500 tokens 누적 | 이벤트 15건 × 설정 상수(8,500 / 12,000). **측정값 아님** | `config/anti_pattern_rules.json` `tokens_saved_estimate` |
| 실제 Laya 패키지 | `engines/laya/` 클론(Apache-2.0) | 요구 Python ≥ 3.10, torch 2.14, transformers 5.x. 현 기본 python3 = 3.14, **torch 미설치**. python3.11 존재 | `engines/laya/README.md`, `which python3` |
| Prompt Cache 히트율 | 목표 "최대 90% 절감" | 최근 11개 Claude Code 세션 합산 **cache_read 95.8%** (cache_creation 10.7M / cache_read 246.7M / 비캐시 입력 42K tokens) | `~/.claude/projects/-Users-richardkim-macpro-Pi/*.jsonl` usage 필드 집계 |
| Tailnet 4노드 | 도달 가능 | 4노드 모두 tailscale status 표기. RTT 는 09-22 UTR 기준 16.8~24.7 ms | `Tailscale status` |
| M5 메모리 | — | 16 GB 통합 메모리 (Laya 상주 ~1.5 GB 여유 있음) | `sysctl hw.memsize` |
| C2 큐 계약 | — | `job-contract.cjs` 는 fixture 프로젝트·`wait/write/fail` 연산만 허용(schemaVersion 1). **모든 작업은 유저 ed25519 서명(암호구절 TTY) 필수** | NV `scripts/fleet/job-contract.cjs`, PLAN_C2 §1 |
| Windows 노드 워커 | — | i7: WSL2 + node24 + `/srv/nv-worker` 준비, **스케줄러 미등록**. Site1: RAM 여유 0.62 GB. NVG: 16 GB, Kepler GPU | 메모리 `i7-d1-wsl2-worker-state`, 09-22 UTR |

**결론:** 지시문의 "인터셉터 18 ms → 5 ms" 는 출발점 숫자가 실측이 아니므로, Phase 1 에서 기준선을 다시 세운 뒤 목표를 절대값으로 재확정한다. 현재 병목은 **모델 추론이 아니라 훅 프로세스 기동(Python 스폰 + import)** 이다. 이 사실이 Track 1 설계의 방향을 결정한다.

---

## 2. North Star · 핵심 KPI

### 2.1 North Star 정렬
NV `NORTH_STAR.md` 의 4분류로 이 프로젝트의 산출물을 미리 분류한다. **배관·안전만 쌓이는 턴은 그렇게 보고한다.**

| 산출물 | 분류 | 이유 |
|---|---|---|
| L0/L1 무토큰 판정 레이어, 추측 실행 히트 | **팔다리(effector)** | 에이전트 대기 없이 배가 움직인다 |
| RouteLLM 임계치 튜닝, 프리픽스 지문 | 배관(plumbing) | 비용·지연을 줄이지만 조종간이 늘진 않는다 |
| 구조화 출력 강제, 예측 실패 취소, Fallback | 안전(guardrail) | 되돌릴 수 없는 낭비를 막는다 |
| 대시보드 HUD | 조종간(cockpit) 보조 | 유저가 어디서든 절감 상태를 본다 |

### 2.2 KPI (모두 실측 정의 포함)

| # | KPI | 기준선 (실측) | Phase 1 목표 | Phase 3 목표 | 측정 방법 |
|---|---|---|---|---|---|
| K1 | 훅 왕복 지연 p50 (PreToolUse/PostToolUse 진입→응답) | **57.7 ms** (폴백 경로) | ≤ 20 ms (데몬 상시 + 경량 클라이언트) | **≤ 5 ms** (L0 히트 시), ≤ 35 ms (L2 Laya) | `scripts/bench/hook_roundtrip.py` 100회 중앙값, 결과 `learning/metrics/hook_latency.jsonl` |
| K2 | 무토큰 종결율 (L0+L1 에서 끝난 비율) | 미측정 | 측정 파이프라인 가동 | ≥ 60% (반복 에러·린트 패턴) | 라우터 텔레메트리 `layer_resolved` 필드 집계 |
| K3 | 판정 품질 손실 (gold 대비 정확도 차) | 미측정 (gold 셋 없음) | gold 셋 ≥ 300건 확보 | **< 1.0%p** (Track 1-2 조건) | `engines/hybrid_router/eval/` holdout 정확도 |
| K4 | 턴당 입력 토큰 중 캐시 미스 비율 (`input + cache_creation` / 총 입력) | **4.2%** (11세션 합산) | 세션별 cache_creation 원인 분류 | 세션 첫 턴 제외 **≤ 2%**, 프리픽스 드리프트 0건/주 | 세션 transcript usage 집계 스크립트 |
| K5 | 추측 실행 히트율 / 체감 대기 | 없음 | — | 히트율 ≥ 40%, 히트 시 도구 대기 **0초**(결과 즉시 반환) | C2 결과 원장 `execution_results` + 라우터 `prefetch_hit` 로그 |
| K6 | 추측 실행 낭비율 (취소·미사용 작업 비율) | 없음 | — | ≤ 30%, Windows 노드 CPU 유휴 시간에만 | 워커 `worker.stdout.log` + 큐 상태 |
| K7 | 일일 비용 상한 준수 | $2.0/일 (`config/agent_limits.json`) | 변경 없음 | 변경 없음 | 기존 가드레일 |

> "토큰 절감율" 은 단독 KPI 로 두지 않는다. 절감치는 반사실(LLM 이 안 돌았다면 썼을 토큰)이라 직접 측정이 불가능하므로, **K2(무토큰 종결율) × 에러 루프 1회당 실측 평균 토큰**(Claude Code transcript 에서 에러→수정까지의 output_tokens 를 사후 집계)으로 파생 지표만 보고한다. HUD 의 상수 기반 절감치는 "추정" 라벨을 붙인다.

---

## 3. 범위 · 저장소 경계 (NV 좌표 규약 적용)

| 트랙 | 정본 저장소 | 이유 |
|---|---|---|
| Track 1 (라우터·인터셉터·평가 파이프라인) | **Pi** (`~/Pi`, `engines/hybrid_router/`, `scripts/`) | Pi 자체 개발 |
| Track 2-1 C2 큐 스펙 확장·프로파일·Windows 워커 | **NV** (`~/projects/nv-claude-config`, `scripts/fleet/`, `docs/harness/`) | 하네스 정본. CLAUDE.md ⚓ 규약: Pi 에서 하네스 산출물 작업 금지, 3중 검증 후 착수 |
| Track 2-1 예측기(라우터 측 next-action 예측) | Pi | 라우터 기능 |
| Track 2-2 이기종 역할표 | NV `docs/harness/FLEET.md` 갱신 + Pi `config/routing_policy.json` `nodes` 반영 | 로스터는 NV, 정책 미러는 Pi |
| Track 3 프리픽스 지문 | Pi (`scripts/prefix-fingerprint.py`), 규약 반영은 NV `AGENT_BASE_MD_SYNC` 트랙 | 지침 파일 동기화 트랙과 연동 |

이 계획서 자체는 Pi 문서다. NV 측 산출물이 생기는 Phase 2 부터는 NV 에 `docs/harness/PLAN_C2_prefetch_ext_<date>.md` 를 별도로 두고 이 문서는 링크만 유지한다.

---

## 4. 목표 아키텍처 — 4단 판정 사다리 (Decision Ladder)

```
tool call ──► hook client (bash/curl, no Python spawn) ──► router daemon (상시, unix socket + :9876)
                                                             │
     L0  signature hash lookup  (정규화된 에러 시그니처 → 판정)      ~0.05 ms   ZTC
     L1  embedding kNN          (Semantic Router 패턴, ONNX 소형 인코더) ~2-5 ms  ZTC
     L2  Laya typed decision    (실제 mmBERT 체크포인트, MPS)          ~30 ms   ZTC
     L3  Jev API / LLM          (스키마 제약 출력, 서킷 브레이커)      200 ms+  토큰 발생
                                                             │
                                             confidence < τ_L ⇒ 다음 단으로 에스컬레이션
```

- **ZTC 정의(이 계획에서의 운용 정의):** 텍스트 생성 없이 로짓/유사도 분포만으로 확신도를 얻고 그 확신도가 임계치 이상이면 단락 결정한다. L0~L2 는 토큰을 생성하지 않는다.
- **에스컬레이션 규칙:** 각 단은 `(decision, confidence, layer)` 를 반환. `confidence < τ_layer` 면 다음 단. τ 는 Track 1-2 의 튜닝 대상이며 초기값은 L0=exact match 만, L1=0.85 cosine, L2=Laya 보정 후 확률 0.80.
- **폴백 순서(하향 안전):** L3 실패(서킷 OPEN) → L2 → 기존 휴리스틱(현 `LayaHierarchicalEngine`, 이름을 `HeuristicFallbackEngine` 으로 개명) → `allow`(개입 없음). **어떤 단이 죽어도 도구 호출 자체는 막히지 않는다.**
- **훅 클라이언트:** Python 스폰이 K1 의 지배 항이므로 훅 진입점을 `scripts/hooks/router-client.sh`(bash + `curl --unix-socket`, 타임아웃 30 ms) 로 교체. 데몬이 없으면 즉시 `allow` 를 반환하고 `learning/metrics/hook_latency.jsonl` 에 `daemon_down` 을 남긴다.

---

## 5. 트랙별 설계

### Track 1 — ZTC 라우터 고도화 · 오픈소스 접목

**1-1. Semantic Router 패턴 (L0 + L1)** — 단기
- L0: 에러/린트 출력 정규화(경로·줄번호·해시·따옴표 내용 → 플레이스홀더) → SHA-256 앞 16자 시그니처 → `learning/router/signatures.sqlite` (판정·확신·최근 히트 시각·TTL). 히트 시 판정을 그대로 반환. 새 시그니처는 상위 단의 판정으로 채워진다(write-through).
- L1: aurelio `semantic-router` 의 `Route`/`RouteLayer` 구조를 차용하되 의존성은 최소화. 인코더는 ONNX 소형 다국어 모델(`multilingual-e5-small` 급, CPU, int8) 1개를 데몬에 상주. 각 Tier-1 도메인·Tier-2 클래스에 발화 예시 20~50개를 `engines/hybrid_router/semantic/routes.json` 에 둔다. 코사인 ≥ τ_L1 면 종결.
- 검증: `engines/hybrid_router/tests/test_ladder.py` — 동일 에러 2회 호출 시 두 번째는 L0, 서로 다른 경로의 같은 TS 에러는 L0 히트(정규화 검증), L1 임계치 미만은 L2 로 넘어감.

**1-2. RouteLLM 파레토 임계치 자동 튜닝** — 중기
- RouteLLM(lm-sys) 의 라우터 모델 자체(Chatbot Arena 선호 데이터 학습)는 이 도메인과 맞지 않으므로 **방법론만** 채택: "강한 모델 호출 비율 대비 품질" 곡선을 그리고, 품질 손실 허용치 안에서 호출 비율을 최소화하는 τ 를 고른다.
- 데이터: 현 `learning/interventions.jsonl` 의 라우터 이벤트는 **15건**(syntax 12, dependency 2, general 1)으로 튜닝 불가. gold 셋은 Claude Code transcript(`~/.claude/projects/*/*.jsonl`)에서 `tool_result` 에러 → 다음 에이전트 행동을 추출해 반자동 라벨링(에이전트 1차 라벨 + 유저 샘플 검수 10%). 목표 ≥ 300건, 클래스별 ≥ 20건.
- 산출: `engines/hybrid_router/eval/pareto.py` 가 (τ_L1, τ_L2) 격자에 대해 정확도·L3 호출율·p50 지연을 표로 내고, 품질 손실 < 1%p 조건의 최소 L3 호출율 조합을 `config/routing_policy.json` 의 `thresholds` 블록에 **제안**한다. 자동 적용은 하지 않는다(유저 승인 후 커밋).
- 고정 규칙(`tokens <= 192`, `categories > 20`)은 유지하되, Laya 실제 컨텍스트 한도(mmBERT 1024 토큰)와 선택지 예산 20개를 상수가 아닌 정책 파일 값으로 옮긴다.

**1-3. 구조화 출력 방어 (L3)**
- 로컬 HF 모델 경로에서만 Outlines/Guidance 가 적용된다. 현 구성에는 로컬 생성형 모델이 없으므로 **Phase 2 에서는 API 측 스키마 강제**를 우선한다: Jev 는 타입드 결정(choice/score) 자체가 구조화 출력이고, Claude/기타 LLM 에스컬레이션은 tool-use/JSON 스키마 강제 + 1회 재시도 상한으로 재시도 토큰을 막는다.
- 재시도 예산: 파싱 실패 시 1회만 재시도, 그래도 실패면 L2 판정으로 폴백하고 `schema_violation` 텔레메트리를 남긴다.
- Outlines 는 Phase 3 에서 로컬 소형 생성 모델(예: Qwen 계열 1~3B, MPS)을 L2.5 로 도입할지 결정할 때 함께 평가한다. **이번 계획 범위에서는 선택 사항.**

### Track 2 — 이기종 분산 연산 · 추측성 사전 실행

**2-1. Speculative Prefetch Worker**
- **예측기(Pi):** 라우터가 PostToolUse 에서 `(tool, exit_code, error_class, cwd, 최근 N 도구열)` 을 보고 다음 액션 후보를 낸다. 초기에는 규칙표(예: `tsc` 실패 → `npx tsc --noEmit` 재실행 + `eslint` ; `git commit` 직전 → `git diff --stat`; 테스트 실패 → 해당 테스트 파일만 재실행)로 시작하고, L1 인코더로 도구열 유사도 기반 예측을 Phase 3 에 추가.
- **큐 확장(NV):** `job-contract.cjs` schemaVersion **2** 제안 — `operation: "prefetch"`, `commandClass ∈ {git_diff, tsc_noemit, eslint, ast_parse, test_subset, sqlite_mirror}`, `sourceCommit`·`treeDigest` 바인딩, `ttlMs`(기본 120 s), `cancelToken`. 결과는 기존 `execution_results` + `results/<job>.jsonl` 원장 재사용.
- **승인 모델(핵심 결정, §9-1):** C2 는 작업마다 유저 서명이 필요하다. 추측 실행은 초당 단위로 작업이 생기므로 작업별 서명은 불가능하다. 제안: **"프리페치 템플릿 서명"** — 유저가 `commandClass` 허용 목록·대상 저장소·노드·유효기간(예: 7일)을 담은 템플릿 하나에 서명하고, 개별 프리페치 작업은 템플릿 digest + sourceCommit 에 바인딩된 파생 작업으로 큐에 들어간다. 워커는 템플릿 서명 검증 + 파생 작업이 템플릿 허용 범위 안인지 검증. 읽기 전용 프로파일 `prefetch-readonly-v1`(파일 변경 시 `WRITE_ATTEMPT_DETECTED`, 네트워크 금지, cwd 밖 읽기 금지) 만 허용.
- **결과 반환:** 에이전트가 실제로 같은 명령을 호출하면 훅 클라이언트가 `(commandClass, sourceCommit, treeDigest)` 로 원장을 조회해 히트 시 결과를 `tool_result` 로 즉시 반환. treeDigest 불일치(작업 트리가 그 사이 바뀜) 면 미스 처리하고 정상 실행.
- **Windows 측 워커:** i7 WSL2(`/srv/nv-worker`, node24) 를 1호 프리페치 워커로. `fleet worker loop` 를 WSL2 systemd `--user` unit 으로 등록(작업 스케줄러 Store 별칭 함정 회피, 메모리 `windows-task-scheduler-store-alias-pwsh`). NVG 는 2호, Site1 은 RAM 0.62 GB 여유로 **제외**.

**2-2. 이기종 역할 분담표**

| 노드 | 자원 | 역할 | 제외 사항 |
|---|---|---|---|
| richardkim-macpro-macbookpro (M5, 16 GB) | MPS | L1/L2 추론, Jev 게이트웨이, 라우터 데몬, 오케스트레이션, 시그니처 원장 정본 | 장시간 CPU 바운드 정적 검사(프리페치로 오프로드) |
| richardkim-i7 (6C/12T, 16 GB, WSL2) | CPU | 프리페치 1호: tsc/eslint/AST/test_subset, SQLite 원장 미러 | 모델 추론, C: 10 GB 구속 → 산출물은 `/srv` 에만 |
| nv-gigabyte (16 GB, Kepler) | CPU | 프리페치 2호(대기), 시그니처 원장 미러 | GPU 추론(Kepler 미지원) |
| desktop-1q6j3e6 (8 GB, 0.62 GB 여유) | — | 관측·백업 전용 | 프리페치 전면 제외 |

### Track 3 — 프리픽스 캐싱 · 상태 지문

- 실측 히트율 95.8% 는 이미 API 캐시가 잘 작동함을 뜻한다. 남은 문제는 **cache_creation(10.7M tokens)** 즉 "새로 쓴 프리픽스" 이며 원인은 ① 세션 첫 턴(불가피) ② 지침 파일 변경으로 인한 전 노드 프리픽스 무효화 ③ 프리픽스 앞쪽에 섞이는 가변 내용(날짜·git 상태 등).
- **프리픽스 지문:** `scripts/prefix-fingerprint.py` 가 `CLAUDE.md`, `ai_guidelines.md`, `docs/PROJECT_BRIEF.md`, `AGENTS.md`, 메모리 `MEMORY.md` 의 SHA-256 을 계산해 `learning/metrics/prefix_fingerprint.jsonl` 에 (노드, 시각, 지문) 을 남긴다. 지문이 하루 2회 이상 바뀌면 "프리픽스 드리프트" 경고를 세션 복구 브리핑에 표출.
- **핸드오프 연동:** Handoff Bus 핸드오프 문서에 `prefix_fingerprint` 필드를 넣어, 수신 세션이 같은 지문이면 지침 재전송 없이 델타만 받는다(Antigravity ↔ Claude Code ↔ Codex).
- **API 직접 호출 경로(Jev/LLM 에스컬레이션):** 고정 시스템 프롬프트에 `cache_control` 브레이크포인트를 명시하고 가변 내용은 그 뒤에 둔다.
- 지침 파일 편집은 **하루 1회 묶음 반영**을 권고 규칙으로 제안(§9-4).

---

## 6. 단계별 마일스톤 · WBS

일정은 KST 기준, 각 Phase 는 유저 승인 게이트로 끝난다. 착수 조건이 충족되지 않으면 그 Phase 는 시작하지 않는다.

### Phase 1 — 준비·검증 (2026-09-24 ~ 2026-09-30) · 저장소: Pi

| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 1.1 기준선 벤치 | `scripts/bench/hook_roundtrip.py`, `scripts/bench/router_bench.py`, 결과 `learning/metrics/baseline_20260924.json` | 훅 왕복 100회·엔진 1,000회 실측치가 파일로 존재, 시뮬레이션 상수 제거 전/후 비교표 |
| 1.2 정직화 리팩터 | `hierarchical_engine.py` 의 `+18.5`/`34.2`/`38.5` 상수 제거, `HeuristicFallbackEngine` 개명, HUD 절감치에 `estimate` 라벨 | 기존 8/8 테스트 통과 + 지연 상수 관련 assert 를 실측 기반으로 교체 |
| 1.3 데몬 상시화 | `scripts/hybrid-router-daemon.py` unix socket 추가, LaunchAgent 템플릿 `scripts/launchd/com.pi.hybrid-router.plist` | 템플릿 lint 통과. **등록은 시스템 상태 변경 → 유저 승인(§9-2)** |
| 1.4 훅 클라이언트 | `scripts/hooks/router-client.sh` | 데몬 다운 시 30 ms 내 `allow`, 데몬 업 시 p50 ≤ 20 ms |
| 1.5 L0 시그니처 원장 | `engines/hybrid_router/ladder/l0_signature.py`, `learning/router/signatures.sqlite` | 정규화 테스트 10케이스, 2회차 히트 p50 < 1 ms |
| 1.6 실제 Laya 기동 검증 | `python3.11 -m venv .venv-laya`, `pip install laya`, MPS 에서 mmBERT 1회 추론 | 실측 지연(목표 ≤ 40 ms p50 on MPS) 과 상주 메모리를 baseline 파일에 기록. 설치는 `npm install` 과 같은 급의 환경 변경 → 승인(§9-3) |
| 1.7 gold 셋 1차 | `engines/hybrid_router/eval/gold/v1.jsonl` ≥ 100건 | 라벨 스키마 고정, 유저 검수 샘플 10건 |

**Exit:** K1 기준선 확정, 시뮬레이션 상수 0, L0 동작, 실제 Laya 실측 1건. UTR 에 "배관 위주 Phase" 로 정직 보고.

### Phase 2 — 통합·라우팅 고도화 (2026-10-01 ~ 2026-10-14) · 저장소: Pi + NV

| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 2.1 L1 임베딩 단 | `ladder/l1_semantic.py`, `semantic/routes.json`, ONNX 인코더 상주 | p50 ≤ 5 ms(인코더 워밍 후), routes 커버리지 Tier-2 전 클래스 |
| 2.2 L2 실제 Laya 편입 | `ladder/l2_laya.py` (라우터 `Router(preload=True)`), 휴리스틱은 폴백으로 강등 | gold 셋 정확도 ≥ 휴리스틱 + 10%p, p50 ≤ 40 ms |
| 2.3 파레토 평가 파이프라인 | `eval/pareto.py`, `eval/report_<date>.md` 금지 → 결과는 `learning/metrics/pareto_<date>.json` + UTR 표 | gold ≥ 300건, τ 제안 1세트 |
| 2.4 L3 스키마 강제 | `gateway/jev_client.py` 실 HTTP 경로 + JSON 스키마 검증 + 재시도 1회 상한 | 스키마 위반 주입 테스트에서 재시도 ≤ 1, 폴백 L2 |
| 2.5 C2 큐 스펙 v2 (NV) | NV `docs/harness/PLAN_C2_prefetch_ext_<date>.md`, `job-contract.cjs` v2, `prefetch-readonly-v1` 프로파일, 템플릿 서명 검증 | NV 테스트 90/90 + 신규 ≥ 8, 원격 존재 확인(`git ls-tree origin/sync/...`) |
| 2.6 예측기 규칙표 | `engines/hybrid_router/prefetch/predictor.py` + `config/prefetch_rules.json` | 규칙 10개, 단위 테스트 |
| 2.7 프리픽스 지문 | `scripts/prefix-fingerprint.py`, 세션 복구 브리핑에 드리프트 경고 | 4노드 지문 일치 확인 1회 |

**Exit:** 4단 사다리 로컬 완결, τ 제안서 유저 검토, C2 v2 스펙 유저 승인.

### Phase 3 — 분산 추측 실행 검증 (2026-10-15 ~ 2026-10-31) · 저장소: NV 주도

| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 3.1 프리페치 템플릿 서명 1호 | 유저 TTY 서명(에이전트는 키·암호구절 미접근) | `fleet approve show` 로 템플릿 확인 |
| 3.2 i7 WSL2 워커 등록 | systemd `--user` unit, `fleet worker loop` | 틱 로그 `found=0` 확인, 리스 pid 일치 |
| 3.3 Mac ↔ i7 실시간 연동 | Mac 라우터 → 큐 enqueue → i7 실행 → 원장 → Mac 훅 히트 | 왕복 실측: enqueue→결과 도착 시간, 히트 시 tool_result 즉시 반환 데모 3케이스 |
| 3.4 취소·TTL | `cancelToken` 전파, TTL 만료 정리, treeDigest 미스 처리 | 예측 실패 시나리오 5개 통과, 낭비율 K6 측정 |
| 3.5 단절 폴백 | Tailnet 단절 주입(워커 정지·방화벽) 시 Mac 측 무영향 | 훅 p50 변화 없음, 큐에 stale→unknown 만 남음 |
| 3.6 NVG 2호 확장(선택) | 동일 절차 | 유저 결정 |

**Exit:** K5·K6 실측, ORCH 루프 통합 보고, 스킬 등록은 보류(DECISION_orchestrator_loop §3).

---

## 7. 리스크 분석 · 롤백

| # | 리스크 | 영향 | 완화 | 롤백 |
|---|---|---|---|---|
| R1 | Tailnet 지터·Windows 노드 단절 | 프리페치 결과 미도착 | 훅은 원장 조회만 하고 결과 대기를 **절대 하지 않는다**(미스 = 정상 실행). 워커 heartbeat 60 s 초과 시 stale→unknown(기존 C2 규칙) | 프리페치 비활성 플래그 `config/prefetch_rules.json` `enabled:false` 1줄 |
| R2 | 예측 실패로 인한 Windows 노드 부하 | CPU·디스크 낭비, i7 C: 10 GB 압박 | 동시 프리페치 ≤ 2, TTL 120 s, `cancelToken` 으로 후속 도구열이 예측과 어긋나면 즉시 취소, 산출물은 `/srv` 한정·크기 상한 1 MB | 워커 unit 정지(`systemctl --user stop`) |
| R3 | 추측 실행이 부작용 있는 명령을 실행 | 비가역 변경 | `prefetch-readonly-v1` 만 허용, `commandClass` 화이트리스트, 파일 변경 감지 시 실패 처리(기존 codex-readonly-v1 방식 재사용) | 템플릿 서명 폐기(유저) |
| R4 | 훅 지연이 오히려 증가 | 모든 도구 호출이 느려짐 | 훅 클라이언트 하드 타임아웃 30 ms → `allow`; K1 회귀 테스트를 CI 에 | 훅 등록 해제(settings hooks 1항목) |
| R5 | 실제 Laya 가 M5 에서 목표 지연 미달 | L2 무의미 | Phase 1.6 에서 먼저 실측 후 결정; 미달 시 L2 를 배치 모드/비동기 사전 판정으로 전환 | L2 비활성, L1→L3 직결 |
| R6 | gold 셋 라벨 편향(에이전트 자기 라벨) | τ 튜닝이 품질 손실을 못 잡음 | 유저 검수 10% + 클래스별 최소 20건, holdout 분리 | τ 를 초기값으로 되돌림 |
| R7 | 상수 제거로 대시보드 숫자가 "나빠 보임" | 보고 혼선 | 기준선 문서에 "이전 값은 시뮬레이션" 명기, HUD 에 estimate 라벨 | 없음(정직화는 되돌리지 않음) |
| R8 | 지침 파일 잦은 편집으로 캐시 무효화 | 비용 증가 | 지문 드리프트 경고, 일 1회 묶음 반영 | 없음 |
| R9 | NV 좌표 위반(Pi 에서 하네스 산출물 작성) | 정본 분열 | Phase 2.5/3 착수 전 3중 검증 절차를 체크리스트로 | 잘못 놓인 파일은 NV 로 이전 후 Pi 에서 삭제 |

---

## 8. 가드레일 준수 계획

- **4중 게이트(ai_guidelines §1~§4):** Slop 금지 → 시뮬레이션 상수를 실측으로 교체하는 것이 첫 작업. 테스트·린트 → 모든 신규 모듈에 unittest, biome pre-commit 유지. 비용 → 일 $2.0 상한 유지, L3 호출은 파레토 평가 결과로만 확대. 회의 프로토콜 → Phase 종료마다 UTR 갱신, 비오케스트레이터 턴은 council entry.
- **NV 좌표 규약:** Track 2 큐·워커·프로파일은 NV 에서만. 매 NV 작업 시작 시 `Set-Location`/`git rev-parse --show-toplevel`/`git remote get-url origin` 3중 검증을 결과에 명기. 완료 판정은 원격 존재 확인.
- **비파괴 검증:** 벤치·평가는 스크래치패드 또는 `learning/metrics/` 에만 기록. `learning/interventions.jsonl` 에는 라우터 이벤트를 더 이상 섞지 않고 `learning/metrics/router_events.jsonl` 로 분리(§7 유저 개입 로그의 통계 오염 방지 — 현재 559행 중 15행이 라우터 이벤트).
- **유저 승인 게이트:** 시스템 상태 변경(LaunchAgent 등록, venv·pip 설치, WSL2 unit 등록, 훅 등록), C2 계약 변경, τ 정책 반영, 템플릿 서명은 모두 AskUserQuestion 승인 후 에이전트가 직접 수행(스킬 `approval-gate-exec`). 서명 키·암호구절은 유저만.
- **가시적 정지점:** 각 Phase 끝에서 멈춘다. 다단계 자율 루프로 Phase 를 연속 실행하지 않는다(메모리 `no-blackbox-agent-loops`).
- **자유 보고서 파일 금지:** 평가 결과는 `learning/metrics/*.json` 과 UTR 표로만. `*-report.md` 생성 없음.

---

## 9. 유저 결정 요청 (Requires User Approval)

1. **프리페치 승인 모델** — "템플릿 1회 서명 + 파생 작업 자동 큐잉" 을 C2 의 예외로 허용할지. 허용하지 않으면 Track 2-1 은 Mac 로컬 백그라운드 워커(서명 불필요, 같은 노드) 로 축소된다.
2. **라우터 데몬 LaunchAgent 등록**(`com.pi.hybrid-router`) — Phase 1.3.
3. **Python 3.11 venv + `pip install laya`(torch 2.14 포함, 약 3~4 GB)** — Phase 1.6.
4. **지침 파일 일 1회 묶음 반영 규칙**을 ai_guidelines 에 추가할지 — Track 3.
5. **Site1 프리페치 제외·i7 1호 지정** 확인.
6. 이 계획서의 Phase 1 착수 승인.

---

## 10. 참조

- 상위 결정: NV `docs/harness/DECISION_orchestrator_loop.md`, `NORTH_STAR.md`, `DECISION_i7_reinstatement_20260922.md`
- C2 원장·서명: NV `docs/harness/PLAN_C2_worker_loop_20260922.md`, `scripts/fleet/{job-contract,job-queue,worker,approval-keys}.cjs`
- 현 구현: `engines/hybrid_router/`, `scripts/decision-gate-interceptor.py`, `scripts/hybrid-router-daemon.py`, `config/routing_policy.json`, `config/anti_pattern_rules.json`
- 오픈소스: Laya(`engines/laya/`, convaiinnovations, Apache-2.0), aurelio-labs semantic-router, lm-sys RouteLLM, dottxt-ai Outlines, microsoft guidance — 모두 방법론·구조 차용 대상이며 의존성 추가는 Phase 별 승인 항목에 포함
- 이 세션 실측 원자료: 스크래치패드(비보존). Phase 1.1 에서 저장소 내 재측정으로 대체
