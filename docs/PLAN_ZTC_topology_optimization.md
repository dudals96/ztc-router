# PLAN — Pi 토폴로지 ZTC 고도화 · 추측 실행 체계 구축 (실행 계획 v0.3)

- Status: **v0.3 머지본 (D5, 2026-09-24)** — 아스트라 2차 검토·A1~A12·M1~M6 반영. v0.3 문서 세트는 두 트랙 G0 에서 유저 승인. 트랙 A(Opus 5.5) 초안을 기반으로 삼았고, 트랙 B(Luna) 초안의 계약표 행·K0·보존 절차는 `docs/harness/` 두 문서에 접목했다. 비교와 머지안: `docs/evidence/ztc-phase1-merge-20260924/comparison.md`. main 반영(D6)은 유저 승인 대기.
- 작성: Claude Code (Fable 5.1) @ richardkim-macpro-macbookpro. v0.1 2026-09-23 → v0.2 2026-09-24 → v0.3 2026-09-24 Claude Code (Opus 5.5, worktree `~/Pi-wt/ztc-opus55`)
- v0.3 신규 정본 문서: 훅 계약표 `docs/harness/HOOK_CONTRACT_ztc.md`, 평가 규약 `docs/harness/EVAL_PROTOCOL_ztc.md`. 이 계획과 두 문서가 다르면 두 문서가 세부 정본이다.
- v0.3 추가 근거: `docs/evidence/ztc-plan-review-20260924/astra-review-2.md`, `claude-code-verification-A1-A12.md`(2차 회신 절)
- 발주: 유저 지시문 (원문: `learning/user-prompts/2026-09-23_Wed/04_ztc-topology-plan-request.md`); v0.2 는 유저 지시 "다른 에이전트 관점 검토 후 개선" (`learning/user-prompts/2026-09-24_Thu/03_review-then-astra-handoff.md`)
- 검토 원문(증거): `docs/evidence/ztc-plan-review-20260924/codex-review.md` (Codex, 읽기 전용 샌드박스), `docs/evidence/ztc-plan-review-20260924/claude-reviewer.md` (Claude 독립 리뷰어, 분산·보안·비용 관점)
- 참조: `docs/PROJECT_BRIEF.md`, `ai_guidelines.md`, `docs/AGENT_COUNCIL_PROTOCOL.md`, `engines/hybrid_router/`, `scripts/decision-gate-interceptor.py`, NV `docs/harness/PLAN_C2_worker_loop_20260922.md`, NV `docs/harness/NORTH_STAR.md`

---

## 0. 쉬운 말로 (ai_guidelines §8 자동 발동)

식당 주방 입구에 "늘 나오는 주문은 셰프(LLM) 안 부르고 바로 내보내는 접수원"(라우터) 을 세웠다고 했는데, 두 명의 외부 감사가 와서 본 결과는 이렇다. 첫째, 그 접수원은 **아직 출근 명부에 없다** — 어떤 에이전트의 훅에도 연결돼 있지 않아 실제로는 아무 주문도 받은 적이 없다. 둘째, 명찰의 "18ms" 뿐 아니라 벽에 걸린 "800배 빠름·99.8% 절감" 포스터도 전부 인쇄물이다. 셋째, 우리가 "훈련된 접수원(진짜 Laya 모델)" 을 데려오려던 비용(수 GB)은 지금 이 가게 규모(처방 4종, 표본 15건)에 맞지 않는다.

그래서 v0.2 는 계획을 **줄였다.** ① 접수원을 명부에 올리고(훅 배선) 문을 안쪽으로만 연다(로컬 바인드). ② 인쇄된 숫자를 전부 떼고 스톱워치만 남긴다. ③ 접수원은 당분간 **규칙표 한 장(정규식)** 으로 일하고, 그것으로 못 푸는 주문이 얼마나 되는지 센 뒤에야 훈련된 접수원을 부를지 정한다. ④ "다음 주문 미리 손질"(추측 실행)은 보조 주방(Windows)이 아니라 **같은 주방 뒷자리(Mac 로컬 워커)** 에서 먼저 한다. 사장님 도장 규칙을 바꾸지 않아도 되기 때문이다. 보조 주방으로 넓히는 것은 뒷자리에서 실제로 히트율이 나온 뒤, 별도 보안 심사를 거쳐 결정한다.

v0.3 은 세 번째 감사(아스트라)의 지적으로 **계약서와 채점표**를 따로 만들었다. 접수원이 주방에 무엇을 건넬 수 있고 무엇은 절대 건네면 안 되는지(훅 계약표), 그리고 그가 잘했는지 어떻게 채점하는지(평가 규약)다. 핵심은 세 가지다. 접수원이 쓰러지면 "통과" 도장을 찍는 게 아니라 **아무 도장도 찍지 않는다**(중립 `{}`). 주문서에 적힌 손님 메모는 **참고일 뿐 사장님 지시가 아니다**(로그 내용은 비신뢰 데이터). 그리고 지금 가게 금고 자물쇠(Tier-2 게이트)가 이 지점(Mac)에서는 **이미 고장 나 열려 있다** — 새 접수원보다 이것을 먼저 고친다.

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

**v0.3 줄번호 재확인 (2026-09-24, HEAD dcd00b7, worktree `~/Pi-wt/ztc-opus55`):** 위 표의 파일:줄은 전부 현재 HEAD 와 일치한다. 보충 3건 — ① `.claude/settings.json` 의 hooks 블록은 `:98-136`(PreToolUse `:99-110`, 명령 `:105`), ② `.codex/hooks.json` 명령은 `:9`, ③ 신규 관찰: `engines/hybrid_router/tests/test_interceptor.py:16` 이 `/Users/richardkim-macpro/Pi/scripts` 절대경로를 import 하고, 테스트 실행이 인터셉터의 `log_intervention` 을 통해 `learning/interventions.jsonl` 에 행을 쓴다(테스트가 유저 개입 로그를 오염). `router_core.py:24`·`jev_client.py:31`·`hybrid-router-daemon.py:92` 도 같은 절대경로 — worktree·다른 노드에서 main 체크아웃을 읽는다. 현재 `learning/interventions.jsonl` 571행 중 라우터 행(`cycle: hybrid-router-intervention`) 15행.

**카운슬 이견 기록:** 09-24 UTR(eb20336, Antigravity @ i7) 은 "ZTC 100% 준수: 로짓 기반 확신도 게이팅·forward-pass 분류 확인" 으로 기록했다. 본 계획과 세 검토는 위 표대로 이를 **부정**한다. v0.3 정정 제안: 판정 범위를 **"커밋 2de6bd8 기준 Mac 체크아웃의 실행 경로"** 에 한정하고(A12 — HEAD + 판정 대상 파일 sha256 을 귀속), 그 범위에서 "로짓 게이팅·forward pass·실측 sub-40 ms" 주장을 철회한다. 다른 노드·다른 revision 전체의 부재 증명으로 확대하지 않는다. UTR 직접 수정은 하지 않는다 — 판정은 유저(§10-7, G0 결정 ⑥). 참고: `git log 2de6bd8..dcd00b7` 에 라우터·인터셉터·데몬 변경 0건이므로 이 판정은 HEAD dcd00b7 에도 그대로 적용된다.

---

## 2. North Star · KPI (v0.2 재정의)

### 2.1 North Star 4분류
| 산출물 | 분류 |
|---|---|
| 훅 배선 + L0 무토큰 판정, 로컬 프리페치 히트 | **팔다리** |
| 정직화 리팩터, 벤치 규약, gold 셋 | 배관 |
| 데몬 로컬 바인드, shadow 모드, 마스킹, 취소·TTL | 안전 |
| HUD·대시보드 | 조종간 보조 (문구 정직화 후) |

배관·안전만 쌓인 턴은 그렇게 보고한다.

### 2.2 KPI (v0.3 — 세부 정의·통계 절차의 정본은 `docs/harness/EVAL_PROTOCOL_ztc.md` §2)
| # | KPI | 기준선 | 목표 | 측정 정의 |
|---|---|---|---|---|
| K1 | 훅 지연 **p50 / p95 / p99 / 타임아웃률 / 중립 반환률** — **전체 지연(프로세스 기동 포함)과 내부 RPC 지연을 분리** | 미측정(훅 미배선) → W3 shadow 가 첫 값 | 내부 RPC p99 ≤ 30 ms, 타임아웃률 < 1%. 전체 지연은 보고만 | 원자료 `$PI_ROUTER_HOME/telemetry/hook_events.jsonl`(저장소 밖, M3), 집계만 `learning/metrics/`. cold/warm 구분 |
| K2 | 무토큰 분류율 = L0 확정 판정 건수 / **실패한 도구 호출(exit≠0) 건수** | 미측정 | ≥ 50% (반복 에러·린트) | 분모 고정. "최초 관측 시그니처" 와 "재관측" 분리. **분류율 ≠ 해결률**(A11) |
| K3 | **shadow 처방 적합률 (gold 대비) + 95% CI** — Phase 1 exit 지표(A2) | gold 확보 후(Phase 1.6, G3 이후) | Phase 2 비교: L0 v1 vs 휴리스틱 **paired 비열등**, 마진 3%p. 검정력·discordance·세션 그룹 분할·tune/holdout 분리를 **사전 지정**(A3). 표본 수 규칙(300→3%p, 1000→1%p)은 철회 | holdout 30%(세션 단위), 유저 검수, 클래스별 ≥ 20건 미만이면 "표본 부족" |
| K4 | **오처방률** = 주입된 처방 후 채택/해결/재발/포기/회귀 5분류 | **shadow 에서는 N/A**(주입 0 → 분모 없음. "0%" 아님, A2) | ≤ 10% (additionalContext 단계부터) | 해결 = 목표 검사 성공 확인. 포기·관측 종료는 별도 집계(A11) |
| K5 | 프리페치 히트율 / 히트 시 도구 실행 시간 | 없음 | 히트율 ≥ 30%(로컬 워커) | Phase 2. 순대기시간 절감과 동일시하지 않는다(A11) |
| K6 | 프리페치 낭비율 | 없음 | ≤ 30% | 취소·미사용 작업 / 발행 작업, CPU 시간 가중 |
| K7 | **세션당 총비용(전후 비교)** — input + cache_write + cache_read + output + L3 + retry, 성공률·완료시간 동시 보고(A11) | 최근 11세션 output 3.06M tokens(output 만) | 동종 작업 기준 −15% | transcript usage 집계 스크립트. HUD 의 상수 절감치는 폐기 |

삭제: v0.1 K4(캐시 미스 ≤ 2%, 모델 오류), K7($2/일, 미터 없음). v0.3: K1 의 "allow-폴백률" → "중립 반환률"(A4 — 폴백은 `allow` 가 아니라 `{}`).

---

## 3. 범위 · 저장소 경계

| 트랙 | 정본 저장소 |
|---|---|
| Track 1 전부, Track 2 **로컬 워커**, Track 3 | Pi |
| Track 2 **Windows 확장**(C2 계약 v2·어댑터·프로파일·전송 계층·템플릿 서명) | NV — Phase 3 이후, 별도 계획서 + 별도 보안 검토 + 3중 좌표 검증 |

Pi 훅이 NV 런타임(`~/.nv-fleet-execution`) 을 읽는 결합은 **Phase 1~2 에서 만들지 않는다.** 로컬 워커는 Pi 자체 원장(`~/.pi-router/`)을 쓴다.

**원자료 위치(M3, 유저 결정 ④):** 텔레메트리·gold·원장 원자료는 저장소 밖 `$PI_ROUTER_HOME`(기본 `~/.pi-router/`, 디렉터리 0700·파일 0600). 저장소에는 일별 집계만 `learning/metrics/`. `learning/` 은 git 추적 폴더라 커밋되면 pull 로 다른 노드에 전파된다(자동 push 는 아님, M3 정정). 데몬 포트 `PI_ROUTER_PORT`(기본 9876), 루트 `PI_ROUTER_HOME` 은 환경변수로 받는다. 외부 바인드를 여는 환경변수는 두지 않는다.

---

## 4. 목표 아키텍처 (v0.2)

```
tool call ─► hook client (에이전트별 stdin/stdout 프로토콜, 파일 존재 가드) ─► router daemon (127.0.0.1 / unix socket 0600)
                │  동기 예산 30 ms                       │
                │  L0  정규식 + 정규화 시그니처 원장     ─┘  히트 → 판정/처방 (ZTC)
                │  미스 → 중립 {} (개입 없음) + 비동기 판정 요청 enqueue
                ▼
   background judge (데몬 워커 스레드)            ─►  L3 LLM/Jev (스키마 강제, 재시도 1회)  ─► 원장 write-through
                                                      (L1 임베딩·L2 Laya 는 §10-5 게이트 통과 시에만 삽입)
```

- **동기/비동기 분리(핵심 수정):** 훅 안에서 응답하는 것은 L0 뿐이다. L2(≥33 ms GPU 최선)·L3(200 ms+) 는 훅 예산과 양립하지 않으므로 백그라운드에서 판정해 원장에 적재하고, 같은 시그니처의 **다음** 발생부터 L0 히트가 된다.
- **shadow 모드 우선:** Phase 1 의 훅은 판정을 기록만 하고 에이전트에 아무것도 주입하지 않는다. 전환 게이트(아스트라 §7): shadow → `additionalContext` 는 적합률·지연 기준 충족과 데이터 취급 검증 후 승인. `deny` 와 `updatedInput` 은 **별도 트랙**으로 심사한다 — `deny` 는 오차단·회복, `updatedInput` 은 의미 동등성·원 권한 보존이 각각 필요하며 K4 하나로 승인하지 않는다.
- **폴백(v0.3 정정, A4):** 데몬 부재·타임아웃·오류 → **중립 반환 `{}`**. 명시적 `permissionDecision: "allow"` 는 승인 프롬프트를 생략시키므로 폴백으로 쓰지 않는다. 어떤 단이 죽어도 도구 호출은 막히지 않고 기존 권한 흐름이 그대로 돈다.
- **타임아웃(v0.3 정정, A4/M4):** 하네스 `timeout` 은 초 단위(기본 600 s). command/http/mcp_tool 훅이 하네스 타임아웃에 걸려도 도구 호출은 막히지 않고 정상 권한 흐름이 계속된다(SDK 콜백 훅만 차단). 따라서 30 ms 는 **클라이언트가 자체 강제**하는 내부 예산이고, 하네스 `timeout` 은 안전망이며 값은 실측(cold 전체 지연 p99) 후 정한다. 전체 지연(프로세스 기동·stdin 파싱 포함)과 내부 RPC 예산을 분리 측정한다.
- **계약의 정본:** 에이전트·이벤트·반환 필드별 지원 여부와 근거 유형은 `docs/harness/HOOK_CONTRACT_ztc.md`. 미확인 항목(`updatedToolOutput`, PostToolUseFailure 의 `additionalContext`, Codex·Antigravity 훅 실행)은 사용하지 않는다.
- **L1/L2 삽입 게이트(§10-5):** gold 셋에서 L0 가 못 푸는 비율이 20% 를 넘고, 그 케이스가 K7 에 유의미한 토큰을 쓰고 있을 때만 L1(ONNX 소형 인코더) → L2(Laya) 순으로 검토. Laya 는 로컬 MPS 조건에서 반복 100회 p50·상주 메모리를 재는 계획서와 함께 별도 승인.

---

## 5. 트랙별 설계 (v0.2)

### Track 1 — 라우터·인터셉터 정직화와 L0
1. **훅 배선(Phase 1.1, v0.3 정정):** Phase 1 은 **Claude Code 1 에이전트·Mac 1 노드**만. 훅 클라이언트는 stdin JSON 을 읽고 stdout 에 **`{}` 만** 쓴다(shadow 불변식 — `HOOK_CONTRACT_ztc.md` §2). Codex(`.codex/hooks.json`) 는 문자열 존재만 확인돼 실행 의미 미검증, Antigravity 는 훅 지원 미확인 → 둘 다 Phase 1 대상 아님. 공유 `.claude/settings.json` 에는 파일 존재·실행 가드(`[ -x … ] && … \|\| echo '{}'`)로 Windows 노드에서 무해화.
2. **데몬 안전화(Phase 1.2):** `127.0.0.1` 또는 unix socket 0600 만 바인드(외부 바인드 환경변수 없음), `/telemetry` 에서 명령 문자열·cwd·경로 제거, `/health` 가 원장·워커 스레드 상태를 실제로 검사, 요청 크기 상한 64 KB(초과 413), ThreadingHTTPServer, 요청 ID, bounded 비동기 판정 큐(상한·중복 합치기·취소 전파·자식 프로세스 회수), 자동 비활성·복귀 절차(§5.4).
3. **정직화(Phase 1.3):** 상수 `+18.5/34.2/38.5/18.0/18.2/12.0`·Jev `sleep(0.045)`·`confidence 0.98` 제거, 대시보드 문구 3곳 제거, 루트 `routing_policy.json` 삭제 후 `evaluate_route` 가 `config/routing_policy.json` 을 실제로 읽게, 엔진 클래스 `HeuristicFallbackEngine` 개명(실제와 다른 "Softmax" 주석 제거), `skills/**` 차단 규칙 제거, 절감 토큰 상수(8,500/12,000) 제거 또는 "추정치" 라벨, 시뮬 단언 테스트를 실측 기반으로 교체, 라우터 이벤트를 `learning/interventions.jsonl` 에서 **`$PI_ROUTER_HOME/telemetry/router_events.jsonl`** 로 분리(집계만 `learning/metrics/`), 하드코딩 절대경로 `/Users/richardkim-macpro/Pi/…` 를 저장소 상대 경로로.
4. **L0 v0→v1(Phase 1.4, v0.3 A10):** 이미 존재하는 `error_signatures.patterns` 정규식을 코드가 실제로 사용하게 한다(현재 `:178` 은 미사용). L0 v1 은 정규화(경로·줄번호·해시 치환) 시그니처 원장 `$PI_ROUTER_HOME/signatures.sqlite`(WAL). 원장 항목: signature, **상태 candidate/verified**, 출처(layer·모델·정책 버전·훅 클라이언트 버전), 생성·만료·폐기 시각, 판정 귀속(HEAD + 판정 대상 파일 sha256, A12). **자동 승격 로직 없음** — v0.2 검증 문서의 "재발 0 이 N=3" 승격 조건은 삭제. candidate → verified 는 성공 재실행 + 독립 평가 + 적용 범위 명시 + 오판정 시 폐기 조건을 갖춘 별도 승인 절차(Phase 2 설계). 새 의존성 0.
5. **벤치 규약(Phase 1.5):** cold/warm × 동시성 1/3 × p50/p95/p99, 전체 vs 내부 RPC 분리, 원자료 `$PI_ROUTER_HOME/telemetry/bench_<date>.jsonl`, 집계 `learning/metrics/bench_<date>.json`, 1회 측정으로 p50 을 주장하지 않음. 세부는 `EVAL_PROTOCOL_ztc.md` §3.
6. **gold 셋(Phase 1.6, G3 이후):** 스키마에 **마스킹 규칙**을 먼저 고정하되, 마스킹 자체는 **훅 클라이언트 단계**에서 한다(M6 — 데몬에 보내기 전 명령 전문·cwd·파일명·stderr 최소화: 절대경로→상대, 64-hex·토큰 패턴 삭제, 본문 500자 절단). 하네스가 이미 저장한 원문(transcript)은 소급 마스킹 불가 — 명기. 원자료는 저장소 밖 `$PI_ROUTER_HOME/gold/`, 저장소에는 집계 통계만. 세션 그룹 분할·tune/holdout 봉인은 `EVAL_PROTOCOL_ztc.md` §1.
7. **파레토 튜닝(Phase 2):** RouteLLM 방법론만 차용(자체 gold 로 L0 임계·L3 호출율 곡선). 자동 적용 없음, 제안 → 유저 승인 → 커밋.
8. **L3 구조화 출력(Phase 2):** Jev 실 HTTP 경로 + mock 서버 테스트 + JSON 스키마 검증 + 재시도 1회 상한. Outlines/Guidance 는 로컬 생성 모델 도입 시(§10-5 이후) 평가.

### Track 2 — 추측 실행: 로컬 워커 기본, Windows 는 조건부
1. **로컬 프리페치 워커(Phase 2, Pi):** 데몬 내 워커 스레드가 예측 규칙표(`config/prefetch_rules.json`, 10개)로 다음 명령을 **같은 cwd·더티 트리에서** 실행. treeDigest 는 `git write-tree`(임시 인덱스) 오브젝트 ID 기반(파일 바이트 해시 아님 → CRLF 무관). 결과는 `~/.pi-router/prefetch/<digest>.out`, TTL 120 s, 동시 1, 출력 상한 1 MB, `cancelToken` 으로 후속 도구열이 어긋나면 취소. **v0.3(A8):** 같은 UID 실행은 무부작용·사전승인을 뜻하지 않고, 별도 worktree 는 경합 완화일 뿐 격리가 아니다(원 저장소·홈·자격증명·네트워크 접근 가능). 실제 쓰기 제한·외부 경로 접근 통제·공유 캐시·프로세스 종료 정책을 정하기 전에는 운영 투입하지 않는다. macOS 네트워크 차단 수단은 미확정.
2. **히트 반환 메커니즘(Phase 2, v0.3 정정):** v0.2 의 "PostToolUse 는 tool_result 를 대체할 수 없다" 는 단정은 **철회**한다 — `updatedToolOutput` 은 Agent SDK 문서에 있고 hooks 레퍼런스 표에는 없어 CLI command 훅 지원이 **미확인**이다(`HOOK_CONTRACT_ztc.md` §1.1). 어느 쪽이든 사후 교체는 실행 비용을 없애지 않으므로 시간 절감 후보는 PreToolUse `updatedInput` 치환이다. 단 치환은 원 명령과 비동등하다(A9): stdout/stderr 분리·exit/signal·절단 플래그·인코딩·cwd/env 지문·원자적 발행을 보존하고, 치환 명령이 권한 평가를 통과해도 **원 작업 승인이 증명되지 않으므로** 원 명령 정체성·승인 맥락·캐시 생성 주체·현재 입력 일치를 함께 검증한다. treeDigest(A7: toolchain 지문·비교 기준 포함, "활성 index 보호" ≠ "무부작용")·argv·cwd 가 모두 일치할 때만. K5 의 분자.
3. **명령 클래스 v1:** `git_diff_stat`, `tsc_noemit` 두 개만. `eslint`·`test_subset` 은 저장소 코드 실행이므로 로컬 워커에서도 K4·K6 실측 후 추가.
4. **Windows 확장(Phase 3 이후, NV, 조건부):** 로컬 히트율 ≥ 30% 가 실측되고, 두 검토가 명시한 최소 안전 범위(고정 argv, 워커 소유 도구 바이너리, `sourceCommit` 은 서명 base 의 후손이며 origin 보호 ref 존재, 네트워크 차단 `unshare -n`, 시간당·동시·출력 상한, 취소 목록, 템플릿 digest 필드 목록) 를 담은 **별도 보안 검토서**가 통과한 뒤에만. Mac↔Windows 큐 전송 계층은 신규 설계 항목이며 공수는 v0.1 추정의 3배 이상으로 재산정.
5. **이기종 역할표:** M5 = 데몬·L0·로컬 워커·L3 게이트웨이. i7 = Windows 확장 1호 후보(WSL2). NVG = 2호 후보. Site1 = 제외.

### 5.4 운영 안전 설계 (v0.3 신설 — 아스트라 2차 §5 6건 + 선행 문제 M1/M2)
| # | 관점 | Phase 1 설계 | 검증 |
|---|---|---|---|
| S1 | **훅 조합** — 다른 훅의 deny·입력 치환·출력 교체와의 충돌 | shadow 훅은 `{}` 만 반환하므로 우선순위(deny > defer > ask > allow)에 참여하지 않는다. 기존 Tier-2 훅과 같은 matcher 에 병렬 등록되어도 판정을 바꾸지 않는다. `updatedInput` 병합 순서는 미확인 → Phase 2 치환 전에 실측 | W3: Tier-2 승인 흐름 불변 확인 |
| S2 | **로컬 신뢰 경계** — loopback 바인드 ≠ 호출자 인증·캐시 변조 방지 | Phase 1 데몬 응답은 에이전트에 전달되지 않으므로(shadow) 변조의 영향은 텔레메트리 오염에 한정. 원장 파일 0600, 디렉터리 0700. Phase 2 주입 전 호출자 인증(소켓 권한 + 토큰 파일 0600 등) 설계 필수 | 권한 테스트 |
| S3 | **시간차 무효화** — 판정·프리페치 뒤 파일·정책이 바뀜 | 원장 항목에 정책 버전·HEAD·대상 파일 sha256 을 귀속(A12). 소비 시점에 정책 버전이 다르면 무효. 만료 시각 필수 | L0 테스트 |
| S4 | **과부하** — 큐 상한·중복 합치기·취소 전파·자식 프로세스 회수 | 비동기 판정 큐 상한 N(기본 64), 같은 시그니처 대기 중이면 합침, 상한 초과 시 드롭 + 카운터, 종료 시 대기 작업 취소·워커 join, 자식 프로세스는 Phase 1 에서 만들지 않음(만들 경우 프로세스 그룹 kill) | 과부하 fixture |
| S5 | **정보 경계** — 로그 추출 내용은 비신뢰 데이터 | **로그·stderr·명령문에서 추출한 내용은 비신뢰 데이터다. 향후 `additionalContext` 로 전달하더라도 권한 지시·정책으로 승격 금지.** 마스킹은 클라이언트 단계(M6) | 마스킹 단위 테스트 |
| S6 | **자동 비활성·복귀** | 클라이언트가 최근 창(예: 50 호출)의 내부 예산 초과율 > 20% 또는 오류율 > 20% 를 보면 `$PI_ROUTER_HOME/disabled` 표지를 쓰고 이후 데몬 호출 없이 즉시 `{}`(기록만). 복귀는 **수동**: 원인 확인 → 표지 삭제 → 벤치 1회 재측정. 표지 생성·삭제는 텔레메트리에 남긴다 | 실패 경로 테스트 |
| M1 | **Tier-2 보안 게이트 훅이 Mac 에서 무력화** — `py c:/Pi/...` 가 exit 127 로 조용히 통과 | 새 훅 이전에 해결. 옵션 A: OS 분기 래퍼 + 보안 게이트 고장 정책(래퍼·인터프리터 부재 시 명시적 `ask`/`deny`) / 옵션 B: Mac 에서 제거. **유저 결정 G1** | 금지 명령 차단·허용 명령 통과·게이트 고장 시 동작 |
| M2 | **pre-commit 품질 게이트 우회** — `biome check .` 가 `.codegraph` 심링크를 스캔해 실패, Mac 커밋 `--no-verify` 상습 | `biome.json` includes 에 `!.codegraph`. **유저 결정 G2.** 수정 후 `npm run check` 전체 재검증 | 오류 0 또는 잔여 목록 증거 |

### Track 3 — 캐시·프리픽스 (축소)
- v0.1 의 "프리픽스 드리프트가 cache_creation 의 원인" 은 철회한다. cache_creation 은 대화 증분·TTL 만료가 본체다.
- 남기는 것: ① 직접 API 호출 경로(L3)에서 고정 시스템 프롬프트에 `cache_control` 브레이크포인트, ② 지침 파일 변경 빈도 모니터(`scripts/prefix-fingerprint.py`, 비용 아닌 **거버넌스** 지표로 격하), ③ K7 세션당 토큰·비용 집계 스크립트.
- 삭제: Handoff Bus "델타만 전송"(프로바이더 간 캐시 무관), 일 1회 묶음 반영 규칙 제안(근거 상실).

---

## 6. 단계별 마일스톤 · WBS (v0.2)

### Phase 1 — 배선·정직화·L0 (2026-09-25 ~ 2026-10-08) · Pi
| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 1.0 계약·규약 (v0.3) | 본 문서 v0.3, `docs/harness/HOOK_CONTRACT_ztc.md`, `docs/harness/EVAL_PROTOCOL_ztc.md` | G0 승인 |
| 1.1 훅 배선(shadow) | `scripts/hooks/router-client.sh` + Claude Code 훅 클라이언트(마스킹 포함), 파일 존재 가드 | 실패 경로 7종(데몬 부재·타임아웃·권한 거부·취소·과부하·잘못된 JSON·64 KB 초과) 에서 stdout `{}`·exit 0 (등록 전 fixture) → G3 후 Mac 에서 Bash 호출 100회 중 훅 기록 100건, 주입 0, Tier-2 흐름 불변. Windows 노드 settings 무해는 가드 코드 리뷰로 대체("실기 미확인") |
| 1.2 데몬 안전화 | 로컬 바인드, telemetry 정화, readiness, 크기 상한, 스레딩, bounded 큐, 자동 비활성 | `lsof` 로 0.0.0.0 미노출, 동시 3 요청 직렬화 없음(벤치), 64 KB 초과 413 |
| 1.3 정직화 | 상수·문구·죽은 설정·차단 규칙 제거, 테스트 교체, 이벤트 로그 분리 | `grep` 으로 상수 0건, 테스트 통과(실측 단언), `config/` 정책 변경이 판정을 바꾸는 테스트 |
| 1.4 L0 v0→v1 | 기존 정규식 사용 → 시그니처 원장(candidate/verified, 출처, 만료) | 재관측 히트 p50 < 1 ms(원장 조회만), 정규화 테스트 10케이스 |
| 1.5 벤치 규약·첫 기준선 | `scripts/bench/hook_bench.py`, 원자료 `$PI_ROUTER_HOME/telemetry/`, 집계 `learning/metrics/bench_<date>.json` | K1 첫 값(전체 vs 내부 RPC, cold/warm) |
| 1.6 gold 도구 → gold 100건 + 휴리스틱 실측 정확도 | 스키마 검증기·집계기(Phase 1), 원자료 `$PI_ROUTER_HOME/gold/v1.jsonl` 은 G3 이후 유저 검수 | 마스킹 검증 통과, K3 기준선(부재 시 "기준선 미확보") |
| 1.7 데몬 LaunchAgent | 템플릿만 작성 | 등록은 별도 승인(§10-2, G4 — 이번 Phase 밖) |
| 1.8 선행 결함 | M1 Tier-2 훅(G1), M2 biome `.codegraph`(G2) | 각 게이트의 테스트·재검증 증거 |

**삭제:** v0.1 1.6(실 Laya 설치). **Exit(v0.3):** 시뮬 상수 0(grep 증거), 정책 파일 실제 소비 테스트, 데몬 로컬 바인드 lsof 증거, 실패 경로 7종 `{}` 테스트, shadow 100/100 기록·주입 0, K1 첫 값, K3 = **shadow 처방 적합률**(gold 부재 시 "기준선 미확보"로 정직 기재), **K4 = N/A**, v0.3·계약표·평가 규약 커밋, G0~G3 승인 기록. "배관·안전 위주 Phase" 로 보고.

### Phase 2 — 로컬 프리페치·L3·튜닝 (2026-10-09 ~ 2026-10-29) · Pi
| WBS | 산출물 | 완료 판정 |
|---|---|---|
| 2.1 개입 opt-in | shadow → `additionalContext` → 클래스별 `deny`/`updatedInput` | K4 오처방률 ≤ 10% 인 클래스만 opt-in |
| 2.2 로컬 프리페치 워커 | 규칙표 10개, write-tree digest, TTL·취소, `updatedInput` 히트 반환 | K5·K6 첫 실측, 취소 시나리오 5개 |
| 2.3 L3 실 HTTP + 스키마 | mock 서버 테스트, 재시도 1회 | 스키마 위반 주입 시 재시도 ≤ 1, 폴백 중립 `{}` |
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
| R1 | 훅이 도구 호출을 느리게 함 | 클라이언트 내부 예산 30 ms 초과 → 중립 `{}`, 자동 비활성 표지(§5.4 S6), K1 p99·타임아웃률 회귀 테스트. 프로세스 기동 비용은 예산 밖이므로 전체 지연을 따로 보고 | settings 훅 1항목 제거 |
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

## 9. 검토 반영 기록 (v0.1 → v0.2)

| 출처 | 지적 | 판정 | 반영 |
|---|---|---|---|
| Claude P1 | 훅 미배선, 57.7 ms 는 기준선 아님 | 수용 | §1, K1 재정의, Phase 1.1 |
| Claude P2 | tool_result 대체 불가 | ~~수용~~ **v0.3 정정: 단정 철회** — `updatedToolOutput` 은 CLI 2.1.281 command 훅 지원 **미확인**(SDK 문서 有·레퍼런스 표 無). 시간 절감 후보는 여전히 `updatedInput` | §5 T2-2, `HOOK_CONTRACT_ztc.md` §1.1 |
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

### 9.1 v0.2 → v0.3 반영 기록 (아스트라 2차 `astra-review-2.md` + 검증 문서 2차 회신)
| 항목 | 판정 | 반영 위치 |
|---|---|---|
| A1 L0 미해결 ≥20% 는 탐색 신호 | 채택 | §10-5 문구: 도입 충분조건 아님, 규칙 보완 대비 순비용·지연·오판정 증분으로 결정 |
| A2 shadow 의 K4 | 채택 | K4 = N/A, Phase 1 exit 는 "shadow 처방 적합률(gold 대비)" (§2.2, §6) |
| A3 paired 비열등 | 채택 | 마진 3%p·검정력·discordance·세션 그룹 분할·tune/holdout 분리 사전 지정. 표본 수 규칙 철회 (§2.2, EVAL §2.2) |
| A4 / M4 타임아웃 | 채택 — 검증 문서 V:12 "타임아웃=도구 실패" 는 SDK 콜백 조항 오인이었음 | command 훅 타임아웃은 비차단, 30 ms 는 클라이언트 자체 강제, 하네스 timeout 값은 실측 후. ≥5 s 안전값 철회 (§4) |
| A5 계약표 | 채택 | `docs/harness/HOOK_CONTRACT_ztc.md` 신설. "additionalContext 는 PostToolUse 전용" 오류 정정(PreToolUse 도 지원), PostToolUseFailure 는 미확인 |
| A6 updatedToolOutput | 미확인으로 하향 | §9 P2 행, §5 T2-2. Phase 1 사용 금지, fixture 만 |
| A7 write-tree 동등성 | 채택 상향 | §5 T2-2: toolchain 지문·비교 기준, "활성 index 보호" ≠ "무부작용" |
| A8 같은 UID·worktree 격리 | 채택 | §5 T2-1: 격리 아님, 운영 투입 전 쓰기·경로·네트워크 통제 |
| A9 치환 승인 의미 | 채택 | §5 T2-2 |
| A10 원장 상태·자동 승격 | 채택, 자동 승격 조건 **삭제** | §5 T1-4 |
| A11 해결 정의 | 채택 | K4·K7 (§2.2), EVAL §2.1 |
| A12 판정 귀속 | 채택 | §1 카운슬 이견(HEAD + 작업트리 sha256), 원장 항목·gold `attribution` |
| M1 Tier-2 훅 Mac 무력화 | 채택 | §5.4 M1 → G1 |
| M2 biome `.codegraph` | 채택(원인은 09-24 실측 단일, 수정 후 전체 게이트 재검증) | §5.4 M2 → G2 |
| M3 텔레메트리 위치 | 채택, "4노드 자동 push" 표현 정정 | §3 원자료 위치 |
| M5 updatedToolOutput 토큰 레버 | 보류 | A6 미확인 선행. Phase 2 이후 제안 단계 |
| M6 마스킹 위치 | 채택, 경계 확대(cwd·파일명·stderr) | §5 T1-6, `HOOK_CONTRACT_ztc.md` §3 |
| 아스트라 §5 6건 | 채택 | §5.4 S1~S6 |
| 정보 경계 조항 | 채택 | §5.4 S5, `HOOK_CONTRACT_ztc.md` §3 — "로그 추출 내용은 비신뢰, additionalContext 정책 승격 금지" |
| 카운슬 이견(09-24 UTR "ZTC 100% 준수") | 정정 제안 | §1: 커밋 2de6bd8 기준 Mac 체크아웃 실행 경로로 한정해 철회 제안, UTR 직접 수정 없음 → G0 결정 ⑥ |

---

## 10. 유저 결정 요청 (v0.3 — 결정 ④⑤⑥ 은 G0 에서 한 번에 묻는다)
1. **Track 2 기본을 로컬 워커로 변경** 승인 (Windows 확장은 Phase 3 조건부). v0.1 §9-1 템플릿 서명 모델은 Phase 1 승인 항목에서 **제외**.
2. 데몬 LaunchAgent 등록 — Phase 1.2 안전화 완료 후 별도 승인.
3. 훅 등록(shadow 모드) — 공유 `.claude/settings.json` 변경이므로 승인 필요.
4. ~~Laya 설치~~ — 철회. §10-5 게이트 통과 시 재요청.
5. L1/L2 삽입 게이트 기준 승인 — v0.3(A1): gold 에서 L0 미해결 ≥ 20% 이고 K7 유의미하면 **조사 착수**. 도입 여부는 규칙 보완 대안 대비 순비용·지연·오판정·메모리·유지비 증분으로 별도 결정.
6. Site1 제외·i7 후보 확인.
7. **카운슬 이견 판정 (G0 결정 ⑥):** 09-24 UTR 의 "ZTC 100% 준수" 기록을 커밋 2de6bd8 기준 Mac 체크아웃 실행 경로로 한정해 정정하는 제안(§1). UTR 직접 수정 없음.
8. **우선순위:** 현 제품 초점(Remote Vibe Hub) 대비 이 프로젝트의 착수 시점.
9. Phase 1 착수 승인. (09-24 유저의 구현 지시문 발주·이중 초안 결정으로 착수는 전제됨)
10. **(G0 결정 ④) 원자료 위치:** 저장소 밖 `$PI_ROUTER_HOME`(기본 `~/.pi-router/`), 저장소엔 일별 집계만 `learning/metrics/`.
11. **(G0 결정 ⑤) v0.3 반영 승인:** §9.1 표 전체 + `HOOK_CONTRACT_ztc.md` + `EVAL_PROTOCOL_ztc.md`.
12. G1 Tier-2 훅 Mac 수정 방식, G2 biome `.codegraph` 제외, G3 shadow 훅 등록 — 각 정지점에서 개별 질문.

---

## 11. 참조
- 검토 원문: `docs/evidence/ztc-plan-review-20260924/`
- 상위 결정: NV `DECISION_orchestrator_loop.md`, `NORTH_STAR.md`, `DECISION_i7_reinstatement_20260922.md`
- C2: NV `PLAN_C2_worker_loop_20260922.md`, `scripts/fleet/{job-contract,job-queue,worker,approval-keys,agent-adapter}.cjs`
- 현 구현: `engines/hybrid_router/`, `scripts/decision-gate-interceptor.py`, `scripts/hybrid-router-daemon.py`, `config/routing_policy.json`, `config/anti_pattern_rules.json`
- 오픈소스(방법론 차용): Laya(`engines/laya/`, Apache-2.0), aurelio-labs semantic-router, lm-sys RouteLLM, dottxt-ai Outlines, microsoft guidance — 의존성 추가는 해시 핀과 함께 별도 승인
- v0.1 전문: git `74ec602:docs/PLAN_ZTC_topology_optimization.md`
