# PLAN — Pi 토폴로지 ZTC 고도화 · 추측 실행 체계 구축 (실행 계획 v0.3)

- Status: **DRAFT v0.3 — 계약 정정안 승인·반영; 나머지 계획 결정은 미결**. 구현·등록 승인을 뜻하지 않는다.
- 작성: Claude Code (Fable 5.1) @ richardkim-macpro-macbookpro. v0.1 2026-09-23 → v0.2 2026-09-24 → v0.3 2026-09-24 (Codex Luna, 승인된 계약 정정만 반영)
- 발주: 유저 지시문 (원문: `learning/user-prompts/2026-09-23_Wed/04_ztc-topology-plan-request.md`); v0.2 는 유저 지시 "다른 에이전트 관점 검토 후 개선" (`learning/user-prompts/2026-09-24_Thu/03_review-then-astra-handoff.md`)
- 검토 원문(증거): `docs/evidence/ztc-plan-review-20260924/codex-review.md` (Codex, 읽기 전용 샌드박스), `docs/evidence/ztc-plan-review-20260924/claude-reviewer.md` (Claude 독립 리뷰어, 분산·보안·비용 관점)
- 참조: `docs/PROJECT_BRIEF.md`, `ai_guidelines.md`, `docs/AGENT_COUNCIL_PROTOCOL.md`, `engines/hybrid_router/`, `scripts/decision-gate-interceptor.py`, NV `docs/harness/PLAN_C2_worker_loop_20260922.md`, NV `docs/harness/NORTH_STAR.md`

---

## 0. 쉬운 말로 (ai_guidelines §8 자동 발동)

식당 주방 입구에 "늘 나오는 주문은 셰프(LLM) 안 부르고 바로 내보내는 접수원"(라우터) 을 세웠다고 했는데, 두 명의 외부 감사가 와서 본 결과는 이렇다. 첫째, 그 접수원은 **아직 출근 명부에 없다** — 어떤 에이전트의 훅에도 연결돼 있지 않아 실제로는 아무 주문도 받은 적이 없다. 둘째, 명찰의 "18ms" 뿐 아니라 벽에 걸린 "800배 빠름·99.8% 절감" 포스터도 전부 인쇄물이다. 셋째, 우리가 "훈련된 접수원(진짜 Laya 모델)" 을 데려오려던 비용(수 GB)은 지금 이 가게 규모(처방 4종, 표본 15건)에 맞지 않는다.

그래서 v0.2 는 계획을 **줄였다.** ① 접수원을 명부에 올리고(훅 배선) 문을 안쪽으로만 연다(로컬 바인드). ② 인쇄된 숫자를 전부 떼고 스톱워치만 남긴다. ③ 접수원은 당분간 **규칙표 한 장(정규식)** 으로 일하고, 그것으로 못 푸는 주문이 얼마나 되는지 센 뒤에야 훈련된 접수원을 부를지 정한다. ④ "다음 주문 미리 손질"(추측 실행)은 보조 주방(Windows)이 아니라 **같은 주방 뒷자리(Mac 로컬 워커)** 에서 먼저 한다. 사장님 도장 규칙을 바꾸지 않아도 되기 때문이다. 보조 주방으로 넓히는 것은 뒷자리에서 실제로 히트율이 나온 뒤, 별도 보안 심사를 거쳐 결정한다.

---

## 1. 현황 실측 · 코드 진실표 (2026-09-23 실측 + 2026-09-24 검토 검증)

| 항목 | 문서·코드가 주장하는 값 | 검증 결과 | 근거 |
|---|---|---|---|
| 인터셉터 훅 배선 | PreToolUse/PostToolUse 훅으로 가동 | **어떤 에이전트에도 미배선.** 등록된 PreToolUse 는 `py c:/Pi/scripts/tier2-gate-hook.py` 뿐(Windows 경로, Mac 에서 미실행). 인터셉터는 argparse CLI 이며 stdin JSON 훅 프로토콜이 아님 | `.claude/settings.json:98-133`, `.codex/hooks.json`, `scripts/decision-gate-interceptor.py:211-217` |
| Laya 추론 엔진 | ModernBERT/mmBERT 단일 forward pass, 로짓 기반 확신도 게이팅 | **키워드 휴리스틱.** 순수 연산 0.003 ms. `latency_ms` 는 `min(elapsed+18.5, 34.2)`(`:168`), 폴백 `+12.0`(`:197`). 확신도로 분기하는 코드 없음 | `hierarchical_engine.py:35-64,168,197` |
| 라우팅 정책 파일 | `config/routing_policy.json` 이 규칙 정본 | 라우터는 루트 `routing_policy.json` 을 읽지만 **한 번도 사용하지 않음**(규칙은 `:49-55` 하드코딩). `config/` 사본은 바이트 동일한 죽은 파일 | `router_core.py:24,26,49-55`, `cmp` IDENTICAL |
| 라우터 파이프라인 지연 | ≤ 38.5 ms | `min(total, 38.5)` 상한 캡 | `router_core.py:74` |
| 인터셉터 지연 | 18 ms | `+18.0`(`:120`), `+18.2`(`:174`) 상수. CLI 왕복 실측 57.7 ms p50(Python 기동 17.4 + import 35) — 단, 훅 미배선이라 **기준선 자격 없음** | `decision-gate-interceptor.py:120,174`, 09-23 스크래치 실측 |
| Jev 게이트웨이 | 상용 API + 서킷 브레이커 | **HTTP 호출 없음.** `time.sleep(0.045)` 후 키워드 점수, `confidence: 0.98` 상수. 브레이커 테스트는 `force_fail=True` 자기 주입 | `jev_client.py:14,127,143` |
| 대시보드 문구 | "18ms 추론", "800배+", "99.8% 시간·100% 토큰 절감" | 하드코딩 문자열 | `hybrid-router-daemon.py:227,232,256` |
| 데몬 노출 | 로컬 서비스 | `0.0.0.0:9876` 무인증, `/health` 는 항상 `ready`, `/telemetry` 가 개입 로그의 명령 문자열을 네트워크에 노출, 단일 스레드 | `hybrid-router-daemon.py:71-84,86-120,369` |
| 데몬 가동(Mac) | 상시 | 09-23 기준 미가동·launchd 미등록. i7 UTR 의 "active" 는 다른 노드·시점 | `pgrep`, `~/Library/LaunchAgents` |
| 절감 토큰 155,500 | 누적 실적 | 이벤트 15건 × 설정 상수(8,500/12,000) | `anti_pattern_rules.json:24,69` |
| 기존 테스트 8/8 | 품질 보증 | `latency_ms <= 40` 과 시뮬 Jev 판정을 단언 → 상수 제거 시 깨짐. "통과 유지" = 시뮬 유지 | `tests/test_hybrid_router.py:34,41,48,59` |
| 실제 Laya 패키지 | sub-40 ms | 33 ms 는 **T4 GPU** 값. CPU 193–464 ms. MPS 는 fp32 강제·공개 수치 없음. `Router(preload=True)` 는 체크포인트 3개 전부 상주(≈4.7 GB fp32) | `engines/laya/README.md:27,137,167`, `laya/agent.py:225-226` |
| C2 큐 확장 난이도 | schemaVersion 2 추가 | 계약이 fixture 프로젝트·`node === hostname`·`wait/write/fail`·`budgetUsd 0` 로 잠김. 어댑터는 codex 프로파일 2종. **Mac↔Windows 큐 전송 계층 없음**(SQLite 노드 로컬). 워커는 단일 비행·15 s 틱 | NV `job-contract.cjs:13-17`, `agent-adapter.cjs:4-7`, `execution-store.cjs`, `worker.cjs` |
| Prompt Cache | 히트율 95.8% | 사실. 단 cache_creation 10.7M 은 **정상 대화 증분·TTL 만료**가 본체. "프리픽스 드리프트" 귀속은 v0.1 의 모델 오류 | transcript usage 집계 |
| 일일 비용 상한 $2 | 가드레일 | 측정 코드 없음. 설정 숫자 | `config/agent_limits.json` |
| 안티패턴 규칙 | 스킬 남발 차단 | `skills/**/SKILL.md` 쓰기 차단 → ai_guidelines §2 스킬 활용·하네스 스킬 작성과 충돌 | `anti_pattern_rules.json:15-16` |

**카운슬 이견 기록:** 09-24 UTR(eb20336, Antigravity @ i7) 은 "ZTC 100% 준수: 로짓 기반 확신도 게이팅·forward-pass 분류 확인" 으로 기록했다. 현재 저장소 스냅샷과 검토자료는 이 문구를 배포된 라우팅의 증거로 뒷받침하지 않는다. 정확한 해시와 정정 제안은 별도 기록에 묶었으며, 유저 판정은 미결이다(§10-7).

---

## 2. North Star · KPI (v0.3 재정의)

### 2.1 North Star 4분류
| 산출물 | 분류 |
|---|---|
| 훅 배선 + L0 무토큰 판정, 로컬 프리페치 히트 | **팔다리** |
| 정직화 리팩터, 벤치 규약, gold 셋 | 배관 |
| 데몬 로컬 바인드, shadow 모드, 마스킹, 취소·TTL | 안전 |
| HUD·대시보드 | 조종간 보조 (문구 정직화 후) |

배관·안전만 쌓인 턴은 그렇게 보고한다.

### 2.2 KPI
| # | KPI | 기준선 | 목표 | 측정 정의 |
|---|---|---|---|---|
| K0 | shadow 계약 적합률 | 미측정(미배선) | G3 승인 실측 후 보고; 목표 임계값은 기준선 확인 뒤 별도 결정 | 정상·중립 응답·권한 비개입을 모두 만족한 관측 / 대상 hook 이벤트. 해결률·정확도와 별도 지표 |
| K1 | 훅 왕복 지연 **p50 / p95 / p99 / 타임아웃률 / 중립 폴백률** | 미측정(훅 미배선) → 승인된 Phase 1.1 첫 측정이 기준선 | L0 내부 RPC 목표 p50 ≤ 5 ms, p99 ≤ 30 ms는 잠정값. 전체 hook 지연 목표는 기준선 뒤 결정 | 전체 프로세스 지연과 내부 RPC 지연을 분리하고 cold/warm·동시성·요청 유형을 기록. 30 ms는 하네스 timeout이 아니며 수치는 측정 전 성과가 아님 |
| K2 | 실제 무토큰 종결율 = 첫 비교 재시도 성공 건수 / **승인 개입 뒤 비교 재시도 건수** | 미측정 | 표본과 기준선 확정 뒤 제안 | shadow에서는 아무 문제도 해결하지 않으므로 **N/A**. 첫 관측과 재관측을 분리하고 평가 중 write-through를 금지 |
| K3 | 판정 정확도 (gold 대비) **+ 95% CI** | 미측정 | 그룹 분리 holdout 결과와 CI 보고; 표본수만으로 비열등성 승인 불가 | 세션·시그니처 연결 그룹 단위 조정/최종 holdout 분리. n=300/1,000의 정밀도 한계는 `docs/harness/EVAL_PROTOCOL_ztc.md` 참조 |
| K4 | 최초 해결 뒤 같은 오류 재발률 | 미측정 | 해당 개입 단계가 별도 승인된 뒤 사전 정의된 관측창으로 측정 | **shadow에서는 N/A**. 최초 비교 재시도에 성공한 승인 개입 뒤 다음 3회 비교 가능한 호출 또는 24시간 중 먼저 끝나는 창에서 같은 시그니처 재발을 측정한다. 창이 끝난 사례만 분모에 넣고 관측 불완료 수를 별도 보고 |
| K5 | 프리페치 히트율 / 히트 시 도구 실행 시간 | 없음 | 히트율 ≥ 30%(로컬 워커), 히트 시 실행 시간 = 캐시 읽기 시간 | PreToolUse `updatedInput` 으로 명령을 캐시 결과 읽기로 치환한 건수 / 대상 명령 호출 건수. treeDigest 일치 시만 |
| K6 | 프리페치 낭비율 | 없음 | ≤ 30% | 취소·미사용 작업 / 발행 작업 |
| K7 | **세션당 순 output_tokens · 비용(전후 비교)** | 최근 11세션 output 3.06M tokens | 동종 작업 기준 −15% | transcript usage 집계 스크립트. 유일하게 돈이 걸린 지표. HUD 의 상수 절감치는 폐기 |

삭제: v0.1 K4(캐시 미스 ≤ 2%, 모델 오류), K7($2/일, 미터 없음).

---

## 3. 범위 · 저장소 경계

| 트랙 | 정본 저장소 |
|---|---|
| Track 1 전부, Track 2 **로컬 워커**, Track 3 | Pi |
| Track 2 **Windows 확장**(C2 계약 v2·어댑터·프로파일·전송 계층·템플릿 서명) | NV — Phase 3 이후, 별도 계획서 + 별도 보안 검토 + 3중 좌표 검증 |

Pi 훅이 NV 런타임(`~/.nv-fleet-execution`) 을 읽는 결합은 **Phase 1~2 에서 만들지 않는다.** 로컬 워커는 Pi 자체 원장(`PI_ROUTER_HOME`, 통합 기본값 `~/.pi-router`)을 쓴다. Luna 초안은 승인된 병렬 작업 경로인 `~/.pi-router/luna/`를 쓴다. 원자료는 `learning/` 등 저장소 추적 경로에 두지 않으며 데이터 절차는 `docs/harness/EVAL_PROTOCOL_ztc.md`를 따른다.

---

## 4. 목표 아키텍처 (v0.3)

```
tool call ─► agent-specific hook client ─► router daemon (127.0.0.1 / unix socket 0600)
                │  내부 RPC 예산 30 ms (전체 지연과 별도)  │
                │  L0  정규식 + 정규화 시그니처 원장     ─┘  hit/miss → shadow 기록만
                │  agent의 기본 권한 흐름 유지; 판정·처방 미주입
                ▼
   background judge (데몬 워커 스레드)            ─►  L3 LLM/Jev (스키마 강제, 재시도 1회)  ─► 원장 write-through
                                                      (L1 임베딩·L2 Laya 는 §10-5 게이트 통과 시에만 삽입)
```

- **동기/비동기 분리(핵심 수정):** 훅 안에서 응답하는 것은 L0 뿐이다. L2(≥33 ms GPU 최선)·L3(200 ms+) 는 훅 예산과 양립하지 않으므로 백그라운드에서 판정해 원장에 적재하고, 같은 시그니처의 **다음** 발생부터 L0 히트가 된다.
- **shadow 모드 우선:** Phase 1 의 훅은 판정을 기록만 하고 에이전트에 아무것도 주입하지 않는다. shadow에서 측정하는 것은 K0 계약 적합과 K1 지연뿐이며 실제 해결·재발 K2/K4는 N/A다. 이후 `additionalContext`, `deny`, `updatedInput` 등 개입은 각 별도 승인과 실제 결과 관측을 거친다.
- **중립 계약:** 문서상 중립 응답이 정의된 Claude Code/Codex command hook은 stdout `{}`와 exit 0으로 정상 권한 흐름에 결정을 남기지 않는다. 에이전트·이벤트마다 timeout/exit 효과가 다르므로 `docs/harness/HOOK_CONTRACT_ztc.md`와 G1 fixture 결과를 따라야 한다. Antigravity `PreToolUse`는 현재 문서상 `decision` 필수라 이 중립 계약의 대상으로 삼지 않는다.
- **결과 교체 정정:** "PostToolUse 결과 교체는 불가능"이라는 v0.2의 일반화는 철회한다. 현재 공식 문서는 Claude Code와 Codex의 일부 PostToolUse 출력 변경 기능을 기술한다. 설치 바이너리에서 동작은 재현하지 않았고 Phase 1은 어떤 교체 필드도 사용하지 않는다.
- **L1/L2 삽입 게이트(§10-5):** gold 셋에서 L0 가 못 푸는 비율이 20% 를 넘고, 그 케이스가 K7 에 유의미한 토큰을 쓰고 있을 때만 L1(ONNX 소형 인코더) → L2(Laya) 순으로 검토. Laya 는 로컬 MPS 조건에서 반복 100회 p50·상주 메모리를 재는 계획서와 함께 별도 승인.

---

## 5. 트랙별 설계 (v0.3)

### Track 1 — 라우터·인터셉터 정직화와 L0
1. **훅 배선(Phase 1.1):** Claude Code와 Codex는 각자의 stdin JSON 이벤트/출력 계약을 적용하며 같은 JSON schema로 간주하지 않는다. 이벤트별 문서 요약은 `docs/harness/HOOK_CONTRACT_ztc.md`; 설치판 동작 fixture를 통과한 한 에이전트만 추후 G3에서 별도 승인 요청한다. Antigravity `PreToolUse`는 문서상 decision 필수라 `{}` 중립 응답을 쓸 수 없어 범위에서 제외한다. 공유 `.claude/settings.json`은 등록 승인을 받은 뒤에만 수정한다.
2. **데몬 안전화(Phase 1.2):** `127.0.0.1` 또는 unix socket 0600 만 바인드, `/telemetry` 에서 명령 문자열 제거, `/health` 가 원장·워커 스레드 상태를 실제로 검사, 요청 크기 상한 64 KB, ThreadingHTTPServer, 요청 ID.
3. **정직화(Phase 1.3):** 상수 `+18.5/34.2/38.5/18.0/18.2/12.0` 제거, 대시보드 문구 3곳 제거, 루트 `routing_policy.json` 삭제 후 `evaluate_route` 가 `config/routing_policy.json` 을 실제로 읽게, 엔진 클래스 `HeuristicFallbackEngine` 개명, `skills/**` 차단 규칙 제거, 시뮬 단언 테스트를 실측 기반으로 교체, 라우터 이벤트를 `learning/interventions.jsonl` 에서 `learning/metrics/router_events.jsonl` 로 분리(유저 개입 통계 오염 방지).
4. **L0 v0(Phase 1.4):** 이미 존재하는 `error_signatures.patterns` 정규식을 코드가 실제로 사용하게 한다(현재 `:178` 은 미사용). L0 v1 은 정규화(경로·줄번호·해시 치환) 시그니처 원장 `~/.pi-router/signatures.sqlite`. 새 의존성 0.
5. **벤치 규약(Phase 1.5):** cold/warm × 동시성 1/3 × p50/p95/p99. `learning/metrics/bench_<date>.jsonl`에는 비식별 집계만 두고 이벤트 단위 원자료는 승인된 경우에만 `PI_ROUTER_HOME/raw/`에 제한 보존한다. 1회 측정으로 p50 을 주장하지 않음.
6. **gold 셋(Phase 1.6):** 스키마에 **마스킹 규칙**(절대경로→상대, 64-hex·토큰 패턴 삭제, 본문 500자 절단) 을 먼저 고정. 동의·검수를 거친 마스킹 골드는 `PI_ROUTER_HOME/gold/`, 원자료는 승인된 경우에만 `PI_ROUTER_HOME/raw/`에 둔다. 저장소에는 비식별 집계만 둔다. tuning/final holdout은 세션·시그니처 연결 그룹으로 분리하며 표본수만으로 비열등성을 주장하지 않는다.
7. **파레토 튜닝(Phase 2):** RouteLLM 방법론만 차용(자체 gold 로 L0 임계·L3 호출율 곡선). 자동 적용 없음, 제안 → 유저 승인 → 커밋.
8. **L3 구조화 출력(Phase 2):** Jev 실 HTTP 경로 + mock 서버 테스트 + JSON 스키마 검증 + 재시도 1회 상한. Outlines/Guidance 는 로컬 생성 모델 도입 시(§10-5 이후) 평가.

### Track 2 — 추측 실행: 로컬 워커 기본, Windows 는 조건부
1. **로컬 프리페치 워커(Phase 2, Pi):** 데몬 내 워커 스레드가 예측 규칙표(`config/prefetch_rules.json`, 10개)로 다음 명령을 **같은 cwd·더티 트리에서** 실행. treeDigest 는 `git write-tree`(임시 인덱스) 오브젝트 ID 기반(파일 바이트 해시 아님 → CRLF 무관). 결과는 `~/.pi-router/prefetch/<digest>.out`, TTL 120 s, 동시 1, 출력 상한 1 MB, `cancelToken` 으로 후속 도구열이 어긋나면 취소.
2. **히트 반환 메커니즘(Phase 2, 별도 게이트):** tool 결과 반환·입력 변경은 에이전트/버전/이벤트별 문서 및 설치판 시험으로 먼저 확인한다. Claude Code/Codex 문서에는 관련 변경 필드가 있으나, 현재 설치판의 실동작·권한 상호작용을 검증하지 않았다. 문서만으로 "체감 0초"나 K5 성과를 주장하지 않으며, 어떤 변경 필드도 Phase 1에 사용하지 않는다. 검증된 agent contract와 별도 사용자 승인이 없으면 K5는 N/A다.
3. **명령 클래스 v1:** `git_diff_stat`, `tsc_noemit` 두 개만. `eslint`·`test_subset` 은 저장소 코드 실행이므로 로컬 워커에서도 K4·K6 실측 후 추가.
4. **Windows 확장(Phase 3 이후, NV, 조건부):** 로컬 히트율 ≥ 30% 가 실측되고, 두 검토가 명시한 최소 안전 범위(고정 argv, 워커 소유 도구 바이너리, `sourceCommit` 은 서명 base 의 후손이며 origin 보호 ref 존재, 네트워크 차단 `unshare -n`, 시간당·동시·출력 상한, 취소 목록, 템플릿 digest 필드 목록) 를 담은 **별도 보안 검토서**가 통과한 뒤에만. Mac↔Windows 큐 전송 계층은 신규 설계 항목이며 공수는 v0.1 추정의 3배 이상으로 재산정.
5. **이기종 역할표:** M5 = 데몬·L0·로컬 워커·L3 게이트웨이. i7 = Windows 확장 1호 후보(WSL2). NVG = 2호 후보. Site1 = 제외.

### Track 3 — 캐시·프리픽스 (축소)
- v0.1 의 "프리픽스 드리프트가 cache_creation 의 원인" 은 철회한다. cache_creation 은 대화 증분·TTL 만료가 본체다.
- 남기는 것: ① 직접 API 호출 경로(L3)에서 고정 시스템 프롬프트에 `cache_control` 브레이크포인트, ② 지침 파일 변경 빈도 모니터(`scripts/prefix-fingerprint.py`, 비용 아닌 **거버넌스** 지표로 격하), ③ K7 세션당 토큰·비용 집계 스크립트.
- 삭제: Handoff Bus "델타만 전송"(프로바이더 간 캐시 무관), 일 1회 묶음 반영 규칙 제안(근거 상실).

---

## 6. 단계별 마일스톤 · WBS (v0.3)

### Phase 1 — 배선·정직화·L0 (2026-09-25 ~ 2026-10-08) · Pi
| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 1.1 훅 배선(shadow) | `scripts/hooks/router-client.sh` + 에이전트·버전·이벤트별 계약 시험 및 파일 존재 가드 | G3 승인 후 대상 하나에서만 시험. 정상 권한 흐름 보존·중립 출력·무주입 확인; 계약 시험 전 배선 금지 |
| 1.2 데몬 안전화 | 로컬 바인드, telemetry 정화, readiness, 크기 상한, 스레딩 | `lsof` 로 0.0.0.0 미노출 확인, 동시 3 요청 직렬화 없음 |
| 1.3 정직화 | 상수·문구·죽은 설정·차단 규칙 제거, 테스트 교체, 이벤트 로그 분리 | `grep` 으로 상수 0건, 테스트 통과(실측 단언), `config/` 정책이 실제 소비됨을 테스트로 고정 |
| 1.4 L0 v0→v1 | 기존 정규식 사용 → 시그니처 원장 | 재관측 히트 p50 < 1 ms, 정규화 테스트 10케이스 |
| 1.5 벤치 규약·첫 기준선 | `scripts/bench/`, `learning/metrics/bench_<date>.jsonl` | K1 4지표 첫 값 |
| 1.6 gold 수집·휴리스틱 기준선 | 승인 후 `PI_ROUTER_HOME/gold/`(로컬), 집계는 `learning/metrics/gold_stats.json` | 데이터 승인·마스킹·유저 검수 및 연결 그룹 분할 후 CI와 한계 보고. n=100은 탐색용이며 최종 holdout·비열등성 증거가 아님 |
| 1.7 데몬 LaunchAgent | 템플릿만 작성 | 등록은 1.2 완료 후 별도 승인(§10-2) |

**삭제:** v0.1 1.6(실 Laya 설치). **Exit:** 오프라인 fixture 통과. G3 shadow가 별도 승인된 경우 K0/K1을 측정하고, 승인·검수된 gold가 있을 때만 K3를 보고한다. shadow의 K2/K4는 N/A이며, 개입 없이 이를 실적으로 보고하지 않는다. 시뮬 상수 0 여부를 확인하고 에이전트 개입은 0으로 유지한다. "배관·안전 위주 Phase" 로 보고.

### Phase 2 — 로컬 프리페치·L3·튜닝 (2026-10-09 ~ 2026-10-29) · Pi
| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 2.1 개입 opt-in | shadow → `additionalContext` → 클래스별 `deny`/`updatedInput` | K4 오처방률 ≤ 10% 인 클래스만 opt-in |
| 2.2 로컬 프리페치 워커 | 규칙표 10개, write-tree digest, TTL·취소, `updatedInput` 히트 반환 | K5·K6 첫 실측, 취소 시나리오 5개 |
| 2.3 L3 실 HTTP + 스키마 | mock 서버 테스트, 재시도 1회 | 스키마 위반 주입 시 재시도 ≤ 1, 폴백 allow |
| 2.4 gold 300건 + 파레토 제안 | `learning/metrics/pareto_<date>.json` | τ 제안 1세트, CI 명시 |
| 2.5 K7 집계 | 세션당 토큰·비용 스크립트 | 전후 비교 첫 표 |
| 2.6 L1/L2 게이트 판정 | §10-5 근거 자료 | 유저 결정 |

### Phase 3 — 조건부 확장 (2026-10-30 ~) · NV 주도, 조건부
| WBS | 조건 |
|---|---|
| 3.1 Windows 프리페치 보안 검토서 | 2.2 히트율 ≥ 30% |
| 3.2 C2 계약 v2·어댑터·전송 계층·템플릿 서명 설계 | 3.1 통과 + 유저 승인 |
| 3.3 i7 WSL2 워커·연동 테스트 | 3.2 |
| 3.4 L1/L2 도입 | §10-5 |

---

## 7. 리스크 · 롤백 (v0.2)
| # | 리스크 | 완화 | 롤백 |
|---|---|---|---|
| R1 | 훅이 도구 호출을 느리게 함 | 하드 타임아웃 30 ms → allow, K1 p99·타임아웃률 회귀 테스트 | settings 훅 1항목 제거 |
| R2 | 오처방 주입으로 에이전트가 더 돎 | shadow → additionalContext → 개입 순서, K4 게이트 | 클래스별 opt-in 해제 |
| R3 | 데몬이 같은 UID 프로세스에 열려 있음 | 소켓 0600, 요청 크기·속도 상한, 원장 항목에 생산 레이어·시각 기록 | 데몬 정지 |
| R4 | 프리페치가 부작용 있는 명령 실행 | 클래스 2개 고정 argv, 읽기 전용, 출력 상한 | `prefetch_rules.json enabled:false` |
| R5 | treeDigest 미스로 히트율 저조 | write-tree 기반, 더티 트리 지원(로컬이라 가능) | Track 2 축소 |
| R6 | gold 셋 민감정보 유출 | 마스킹 스키마 선행, 원자료 저장소 밖 | 파일 삭제·재생성 |
| R7 | 정직화로 대시보드 수치 급락 | 기준선 문서에 "이전 값 시뮬" 명기 | 되돌리지 않음 |
| R8 | 공급망(향후 L1/L2) | 해시 핀·오프라인 미러 없이는 설치 승인 요청 안 함 | — |
| R9 | 다중 에이전트 동시 훅 | ThreadingHTTPServer, 원장 SQLite WAL | — |
| R10 | NV 좌표 위반 | Phase 3 전까지 NV 산출물 0 | — |
| R11 | Windows 확장 시 템플릿 서명이 권한 확대가 됨 | 별도 보안 검토서 + 최소 범위 + 취소 목록 | 템플릿 폐기(유저) |

---

## 8. 가드레일 준수 계획
- 4중 게이트: Slop 금지 → 정직화가 첫 작업. 테스트·린트 → 실측 단언 테스트, biome. 비용 → 신규 유료 호출 0(Phase 1), L3 는 Phase 2 mock 우선. 회의 → Phase 종료마다 UTR/council entry.
- NV 좌표: Phase 1~2 는 Pi 만. Phase 3 착수 시 3중 검증 명기.
- 비파괴: 벤치·평가는 `learning/metrics/`·`~/.pi-router/` 에만. 개입 로그 오염 방지.
- 승인 게이트: 훅 등록·데몬 등록·설정 변경·τ 반영·Windows 확장은 AskUserQuestion 후 에이전트 직접 수행. 키·암호구절은 유저만.
- 가시적 정지점: Phase 단위. 자율 루프 금지.
- 자유 보고서 금지: 검토 원문은 `docs/evidence/` 에, 결과는 metrics JSON + UTR 표.

---

## 9. 검토 반영 기록

### 9.1 v0.1 → v0.2

| 출처 | 지적 | 판정 | 반영 |
|---|---|---|---|
| Claude P1 | 훅 미배선, 57.7 ms 는 기준선 아님 | 수용 | §1, K1 재정의, Phase 1.1 |
| Claude P2 | PostToolUse output replacement 미지원(일반 주장) | v0.2 작성 시 수용, v0.3에서 보완 | 에이전트·버전·이벤트별 계약으로 세분화; 현재 공식 문서와 설치판 재현 여부를 분리 |
| Claude P3, Codex 1 | 누락 상수·문구 | 수용 | Phase 1.3 목록 확장 |
| Claude P4, Codex 1 | 정책 파일 미사용·중복 | 수용 | Phase 1.3 |
| Claude P5, Codex 1 | Jev HTTP 없음 | 수용 | §1, Phase 2.3 mock 우선 |
| Claude P6 | Laya 수치 T4, preload 4.7 GB | 수용 | 1.6 삭제, §10-5 게이트 |
| Claude P7/P8, Codex 5 | C2 확장 공수 과소·전송 계층 없음·서명 모델 위험 | 수용 | Track 2 로컬 기본, Windows Phase 3 조건부 + 보안 검토서 |
| Claude P9 | 테스트가 시뮬 고정 | 수용 | Phase 1.3 |
| Claude P10 | $2/일 미터 없음 | 수용 | K7 교체 |
| Claude §2 캐시 모델 | cache_creation 은 대화 증분 | 수용 | Track 3 축소, v0.1 K4 삭제 |
| Claude §3 4단 과설계 | L0+L3 로 충분 | **부분 수용** | L1/L2 를 삭제하지 않고 §10-5 게이트 뒤로 |
| Claude §3 순서 | 배선 → 정직화 → L0 → 로컬 워커 | 수용 | Phase 1 WBS 재배열 |
| Codex 2 gold 유출·마스킹 | | 수용 | Phase 1.6 |
| Codex 3 shadow 우선·무인증 데몬 등록 금지·Laya 설치 보류 | | 수용 | §4, Phase 1.2/1.7, 1.6 삭제 |
| Codex 3 gold 100/300 불일치 | | 수용 | K3·1.6·2.4 일치 |
| Codex 2 미션 우선순위(RVH 대비 기회비용) | | **유저 판단** | §10-8 |
| Codex 2 Handoff Bus 연동은 기존 기능 아님 | | 수용 | Track 3 에서 삭제 |
| Claude 훅 30 ms vs L2/L3 양립 불가 | | 수용 | §4 동기/비동기 분리 |
| Claude `skills/**` 차단 자기모순 | | 수용 | Phase 1.3 |
| Claude K2 허영 지표 | | 수용 | 분모 고정·최초/재관측 분리 |
| Claude K3 통계 | | 수용 | 비열등 마진 3%p, CI 명시 |

### 9.2 v0.2 → v0.3 — 승인된 계약·평가 정정

| 근거/지적 | v0.3 반영 | 경계 |
|---|---|---|
| Claude Code 공식 훅 문서가 `PostToolUse`의 `updatedToolOutput`을 문서화하며, Codex도 사후 hook 결과 처리 동작을 문서화한다. | v0.2의 “PostToolUse는 결과를 대체할 수 없다”는 보편 단정을 철회했다. 이벤트·에이전트별 차이와 미검증 상태를 `HOOK_CONTRACT_ztc.md`에 고정했다. | 설치 바이너리의 결과 변경 동작은 재현 전까지 미확인. Phase 1에서 출력 변경을 사용하지 않는다. |
| 설치판 문서·버전·이벤트별 입력/출력/timeout/exit 계약을 구분할 필요 | Claude Code 2.1.281과 Codex CLI 0.156.1의 로컬 버전을 확인하고, 각 공식 문서와 Antigravity 문서의 이벤트 표를 분리했다. | 런타임 fixture, settings 등록, timeout 실패 주입은 실행하지 않았다. |
| Shadow 적합성과 문제 해결 결과는 서로 다른 측정 대상 | K0 계약 적합과 K2/K4의 실제 해결·재발 성과를 분리했다. shadow의 K2/K4는 N/A다. | 개입·해결 성과는 승인된 별도 단계 전 측정 불가. |
| Gold 무작위 이벤트 분할은 세션·동일 시그니처 누출을 허용 | 세션과 정규화 시그니처의 연결 그룹 전체를 한 partition에 두고 tuning/최종 holdout을 분리하도록 평가 규약을 정했다. | 그룹 연결로 holdout이 커지거나 클래스가 빠지면 그대로 보고하고 그룹을 쪼개지 않는다. |
| 평가 중 write-through는 holdout 오염 가능 | 후보·원장 스냅샷을 읽기 전용으로 고정하고 평가 중 자동 적재·갱신을 금지한다. | 평가 결과 반영은 종료 후 새 버전의 별도 승인 대상으로 한다. |
| 표본 수를 품질 보장으로 오해할 위험 | n=300/1,000의 이상적 단순표본 95% 오차 폭과 군집·희귀 사건 한계를 `EVAL_PROTOCOL_ztc.md`에 명시했다. | 해당 표본수만으로 3%p 비열등성 또는 1%p 정밀도를 보장하지 않는다. |
| 원자료 저장·보존 정책이 불완전 | 최소 수집, 7일 원자료 보존, 256 MiB/4,096건 제한, POSIX 권한, 논리 삭제 절차를 문서화했다. | 이번 작업은 데이터 수집·삭제를 실행하지 않았으며, Windows ACL은 미정이다. |
| UTR의 “ZTC 100% 준수” 이견은 출처 귀속이 약함 | 관련 UTR·소스·검토 파일의 SHA-256과 현재 HEAD를 `docs/evidence/ztc-phase1-20260924-luna/council-correction-proposal.md`에 귀속했다. | 정정안은 제안 기록일 뿐 사용자 판정이 아니다. UTR은 수정하지 않았다. |

문서 변경과 승인 범위의 정확한 기록은 `docs/evidence/ztc-phase1-20260924-luna/g0-approval-audit.md`를 따른다.

---

## 10. 유저 결정 요청 (v0.3; 미결 항목 유지)
1. **Track 2 기본을 로컬 워커로 변경** 승인 (Windows 확장은 Phase 3 조건부). v0.1 §9-1 템플릿 서명 모델은 Phase 1 승인 항목에서 **제외**.
2. 데몬 LaunchAgent 등록 — Phase 1.2 안전화 완료 후 별도 승인.
3. 훅 등록(shadow 모드) — 공유 `.claude/settings.json` 변경이므로 승인 필요.
4. ~~Laya 설치~~ — 철회. §10-5 게이트 통과 시 재요청.
5. L1/L2 삽입 게이트 기준(gold 에서 L0 미해결 ≥ 20% 이고 K7 유의미) 승인.
6. Site1 제외·i7 후보 확인.
7. **카운슬 이견 판정:** 09-24 UTR 의 "ZTC 100% 준수" 기록 vs 본 계획 §1 진실표.
8. **우선순위:** 현 제품 초점(Remote Vibe Hub) 대비 이 프로젝트의 착수 시점.
9. Phase 1 작업 착수는 사용자 지시로 승인됨. 이는 구현의 G0–G3 경계·설정 등록·서비스 설치를 면제하지 않는다.
10. v0.3 계약 정정 세트는 2026-09-24 사용자 선택 “1번만 진행”에 따라 승인되어 이 문서와 두 하네스 규약에 반영됨. 이 결정은 §10-1~8의 별도 계획 결정 상태를 바꾸거나 UTR 이견의 사용자 판정을 대신하지 않는다.

---

## 11. 참조
- v0.3 hook 계약: `docs/harness/HOOK_CONTRACT_ztc.md`
- v0.3 평가·데이터 정책: `docs/harness/EVAL_PROTOCOL_ztc.md`
- UTR 정정 제안(사용자 판정 미결): `docs/evidence/ztc-phase1-20260924-luna/council-correction-proposal.md`
- 검토 원문: `docs/evidence/ztc-plan-review-20260924/`
- 상위 결정: NV `DECISION_orchestrator_loop.md`, `NORTH_STAR.md`, `DECISION_i7_reinstatement_20260922.md`
- C2: NV `PLAN_C2_worker_loop_20260922.md`, `scripts/fleet/{job-contract,job-queue,worker,approval-keys,agent-adapter}.cjs`
- 현 구현: `engines/hybrid_router/`, `scripts/decision-gate-interceptor.py`, `scripts/hybrid-router-daemon.py`, `config/routing_policy.json`, `config/anti_pattern_rules.json`
- 오픈소스(방법론 차용): Laya(`engines/laya/`, Apache-2.0), aurelio-labs semantic-router, lm-sys RouteLLM, dottxt-ai Outlines, microsoft guidance — 의존성 추가는 해시 핀과 함께 별도 승인
- v0.1 전문: git `74ec602:docs/PLAN_ZTC_topology_optimization.md`
