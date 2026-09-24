<!-- 원본: Claude Code 서브에이전트(독립 리뷰어, 분산시스템·보안·비용 관점), 2026-09-24, Mac richardkim-macpro-macbookpro. 읽기 전용, 파일 수정 없음. 계획 v0.1 (커밋 74ec602) 대상. 본문은 에이전트 출력 원문이며 유저 발언이 아니다. -->

# PLAN_ZTC_topology_optimization.md — 독립 검토 (분산시스템·보안·비용 관점)

검토 대상: `/Users/richardkim-macpro/Pi/docs/PLAN_ZTC_topology_optimization.md` (v0.1). 파일은 일절 수정하지 않았고 상태 변경 명령도 실행하지 않았다.

## 1. 전제 검증 — 코드와 어긋나거나 미검증인 주장

| # | 계획의 주장 | 실제 | 근거 |
|---|---|---|---|
| P1 | "훅 왕복 57.7 ms p50" 를 K1 기준선으로 | **인터셉터는 어떤 에이전트 훅에도 등록돼 있지 않다.** 실제 등록된 PreToolUse 훅은 `py c:/Pi/scripts/tier2-gate-hook.py` 뿐이며 Windows 경로라 Mac 에서는 실행조차 안 된다. 57.7 ms 는 아무도 호출하지 않는 CLI 를 스크래치패드에서 잰 값 | `.claude/settings.json` hooks, `.codex/hooks.json:4-13`; `scripts/decision-gate-interceptor.py:211-217` (argparse CLI, stdin JSON 훅 프로토콜 아님) |
| P2 | "히트 시 결과를 `tool_result` 로 즉시 반환" (§5 2-1, K5) | Claude Code 훅 모델에서 PostToolUse 는 도구 출력을 **대체할 수 없다.** PreToolUse 는 deny/updatedInput 만 가능. 인터셉터 반환값 `{"permission":"intercepted"}` 는 어느 에이전트의 훅 스키마도 아니다. Track 2 의 "대기 0초" 는 현 훅 API 로 구현 불가 | `decision-gate-interceptor.py:143-156, 199-208` |
| P3 | `hierarchical_engine.py:180` 의 `min(elapsed+18.5, 34.2)` | 실제 위치는 `:168`. `:180` 은 `fallback_resolve` docstring. 그 함수에도 `+12.0` 상수(`:197`)가 있는데 계획 1.2 의 제거 목록에 없다. 인터셉터 `+18.0`(`:120`)·`+18.2`(`:174`), 대시보드 하드코딩 "18ms"(`hybrid-router-daemon.py:227`) "800배+"(`:232`) "99.8%"(`:256`) 도 누락 | 위 각 줄 |
| P4 | `router_core.py:73` 캡 | `:74`. 더 중요한 것: 라우터는 `/Users/richardkim-macpro/Pi/routing_policy.json`(루트) 를 읽고(`:24`), 읽은 정책을 **한 번도 쓰지 않는다** — 규칙은 `:49-55` 하드코딩. `config/routing_policy.json` 은 루트 사본과 바이트 동일한 죽은 파일. 계획 1-2 의 "`config/routing_policy.json` `thresholds` 블록에 제안" 은 아무것도 읽지 않는 파일에 쓰는 것 | `router_core.py:24,30-34,49-55` |
| P5 | L3 "Jev API / LLM 200 ms+", 2.4 "실 HTTP 경로 + 스키마 검증" | Jev 클라이언트에 HTTP 호출이 **없다**. `time.sleep(0.045)` 후 키워드 점수. `urlopen` 은 import 만 되고 미사용, `confidence: 0.98` 상수. 서킷 브레이커 테스트는 `force_fail=True` 자기 주입뿐 | `gateway/jev_client.py:14,34,98-99,127,143` |
| P6 | Laya "≤ 40 ms p50 on MPS", "상주 ~1.5 GB" | README 의 33 ms 는 **T4 GPU**. CPU 는 193–464 ms, 코드 경고도 "200-500 ms". MPS 는 fp32 강제(`agent.py:225-226`)이고 공개 수치 없음. 계획 2.2 의 `Router(preload=True)` 는 **세 체크포인트 전부 상주**(421M+322M+421M, fp32 ≈ 4.7 GB) | `engines/laya/README.md:27,167`; `laya/agent.py:247`; `laya/router.py:140` |
| P7 | C2 v2 는 "`job-contract.cjs` schemaVersion 2 제안" 정도의 확장 | 현 계약은 `projectId ∈ fixture-*`(`:13`), **`node === os.hostname()`**(`:14`, 즉 작업은 실행 노드에서만 생성 가능), `operation ∈ wait/write/fail`(`:16`), `budgetUsd===0`(`:17`). 실행 어댑터는 **codex 프로파일 2종만**(`agent-adapter.cjs:4-7`), 슈퍼바이저는 그 executable 을 spawn. `tsc`/`eslint` 를 돌리려면 계약·어댑터·프로파일·verifyOutput 전부 신규. 큐는 노드 로컬 SQLite(`execution-store.cjs:38`), 결과는 0600 + uid 검사(`job-queue.cjs:40,73`) — **Mac↔i7 를 잇는 큐 전송 계층이 존재하지 않는다.** `transport.cjs:8-22` 는 동기 ssh 로 node 소스를 eval 하는 것이지 큐가 아니다 | 위 각 줄 |
| P8 | R2 "동시 프리페치 ≤ 2" | 워커는 설계상 단일 비행·순차(`worker.cjs:2,17`), 틱 간격 최소 1 s·기본 15 s(`:51`, PLAN_C2 §6). "초당 단위" 프리페치와 구조적으로 안 맞음 | |
| P9 | "기존 8/8 테스트 통과" 유지 | 테스트가 `latency_ms <= 40` 을 단언(`tests/test_hybrid_router.py:34,41,48`)하고 시뮬 Jev 판정을 단언(`:59`). 상수를 빼거나 실 Laya 를 넣는 순간 깨지므로 "통과 유지" 는 시뮬레이션 유지와 동치 | |
| P10 | K7 "$2.0/일 기존 가드레일" | 일일 비용을 재는 코드가 저장소에 없다(`scripts/` grep 0건). `agent_limits.json` 의 숫자일 뿐 | `config/agent_limits.json` |

## 2. 빠진 고려사항

- **원장 일관성(Mac 정본 ↔ Windows 미러):** 동기 방향·충돌 규칙·미러가 정본에 역주입될 수 있는지가 없다. L0 원장은 write-through(§5 1-1)로 **판정을 에이전트 컨텍스트에 주입하는 저장소**(`decision-gate-interceptor.py:205` 는 문자 그대로 `prompt_injection`)다. 미러→정본 방향이 한 번이라도 열리면 Windows 노드 침해 = Mac 에이전트 조종.
- **treeDigest 경합:** i7 는 커밋된 트리만 가진다. 에러 루프는 **더티 트리**에서 일어나므로 `sourceCommit` 바인딩 프리페치는 목표 시나리오에서 거의 항상 미스. 미커밋 diff 를 보내면 워커 트리를 써야 해 readonly 프로파일과 모순. 또 Windows autocrlf 로 파일 바이트가 달라 파일 해시 기반 treeDigest 는 노드 간 불일치가 기본값 — git 오브젝트 ID 기반이어야 한다.
- **훅 보안:** unix socket 은 같은 UID 의 모든 프로세스(npm postinstall, IDE 확장)가 접속 가능. 현 데몬은 `0.0.0.0:9876` 무인증(`hybrid-router-daemon.py:369`), `/telemetry` 가 `interventions.jsonl` 의 명령 문자열을 네트워크에 노출(`:92-120`). 계획은 소켓 추가만 말하고 0.0.0.0 폐쇄·소켓 0600·요청 발신자 검증·원장 항목의 생산 레이어 서명을 말하지 않는다.
- **동시성:** `HTTPServer` 단일 스레드(`:369`), 공유 `router_instance`(`:34,327`). Antigravity+Claude Code+Codex 가 Bash 마다 훅을 치면 직렬화되고, Jev 45 ms sleep 하나가 전원을 막는다. 인터셉터 타임아웃 1.5 s(`:58`)는 데몬이 "느리게 살아있을 때" 최악 경로. 그리고 **훅 30 ms 하드 타임아웃(§4, R4) 과 L2 ≥33 ms(GPU 최선)·L3 200 ms 는 양립 불가** — L2/L3 는 동기 훅 안에서 절대 응답 못 한다. 계획은 이를 비동기 사전판정으로 풀지 않았다.
- **데몬 중도 사망:** LaunchAgent 재기동 시 시작 핑 3노드 × 최대 1.5 s(`:50-56`) 동안 훅은 전부 `allow` 폴백. 세션 중 데몬 재시작이 판정 공백을 만드는데 K1 은 p50 만 보므로 이를 못 잡는다.
- **공급망:** `pip install laya` = torch·transformers·HF hub, 락파일·해시 핀 없음(`engines/laya/pyproject.toml` dependencies 는 하한만). 첫 호출 시 `snapshot_download` 로 네트워크에서 체크포인트 수신(`laya/agent.py:126-137`). L1 의 ONNX 런타임+모델은 별도 두 번째 공급망. 어느 쪽도 승인 항목에 "핀·해시·오프라인 미러" 가 없다.
- **관측·테스트:** 훅 타임아웃률·오판정률·주입된 처방을 에이전트가 실제로 따랐는지 추적 없음. L3 실 HTTP 는 mock 없이 테스트 불가. 시뮬 Jev 를 단언하는 테스트(P9) 교체 계획 없음.
- **Windows/WSL2:** 공유 `.claude/settings.json` 에 `router-client.sh`(bash+curl unix socket) 를 넣으면 Windows 노드에서 깨진다(메모리 "공유 settings 훅은 파일 존재 가드 필수" 와 같은 함정의 재발). WSL2 `/srv` 트리와 Windows 체크아웃의 줄끝·경로 이중성 미언급.
- **비용 회계:** 4.7 GB 상주 메모리·i7 CPU·개발 시간 대비 절감의 실측치가 0. 현재 근거 이벤트는 15건(`learning/interventions.jsonl` 563행 중), 그 절감치는 설정 상수(`anti_pattern_rules.json:24,69`). $2/일 상한이면 절감 상한도 $2/일이다.
- **gold 셋 데이터 유출:** `~/.claude/projects/*/*.jsonl` 에는 파일 내용·비밀값이 섞인다. 300건을 `engines/hybrid_router/eval/gold/` 로 저장소에 넣으면 private 라도 4노드 push 대상이 된다. 마스킹 규칙 없음.
- **인터셉터의 자기모순:** `skills/**/SKILL.md` 쓰기를 차단(`anti_pattern_rules.json:15-16`) — ai_guidelines §2 의 스킬 활용 규칙·하네스 자체 스킬 작성과 충돌. 배선되는 순간 정상 작업을 막는다.
- **Track 3 캐시 모델 오류:** Claude Code 에서 매 호출의 새 턴 내용(도구 결과 등)은 **정상적으로** `cache_creation` 이다. 10.7M 은 "프리픽스 드리프트" 가 아니라 대화 증분 + 5분 TTL 만료가 대부분이다. 지문은 API 캐시에 아무 영향이 없고, Antigravity/Codex 는 다른 프로바이더 캐시라 "델타만 전송" 은 무의미.

## 3. 반대 의견

- **4단 사다리는 과설계다.** 판정의 실체는 처방 문자열 4개 중 하나 고르기(`anti_pattern_rules.json:39,48,56,65`) 이고, 클래스 7개, 데이터 15건. 이미 `error_signatures.patterns` 정규식(`:33-64`)이 있는데 코드가 안 쓸 뿐(`interceptor.py:178`). 정규식 L0 + (필요 시) L3 두 단이면 충분하다. L1 임베딩은 7클래스 문제에 런타임 하나를 더 얹는 것.
- **실 Laya 는 지금 값어치가 없다.** 3~4 GB 의존 + 4.7 GB 상주 + 검증 안 된 MPS 지연을 들여 얻는 것이 "보정된 확신도" 인데, 확신도를 걸어 갈라질 분기가 아직 없다. 휴리스틱이 0.003 ms 인 것은 장점이 아니라 **문제가 그만큼 작다는 증거**다. Phase 1.6 은 삭제하고 gold 셋에서 L0 가 못 푸는 케이스 비율이 나온 뒤 재논의.
- **Windows 추측 실행은 C2 서명 예외를 정당화하지 못한다.** P7·treeDigest 문제로 히트율이 구조적으로 낮고, 전송 계층·어댑터·프로파일을 새로 써야 한다. Mac 로컬 백그라운드 워커는 더티 트리 접근·전송 0·서명 불필요(에이전트와 같은 신뢰 경계). §9-1 의 "허용 안 하면 축소" 가 아니라 **로컬 워커가 기본**이어야 하고, Windows 는 로컬 히트율이 실측된 뒤의 선택지.
- **순서 재배치:** (1) 실제 훅 배선 → (2) 정직화·죽은 설정 제거 → (3) L0 정규식 → (4) 로컬 워커 → 그 뒤에야 L1/L2/Windows. 현 Phase 1 은 (1) 없이 벤치부터 하므로 기준선 자체가 허구다.
- **NV 결합:** Mac 훅이 NV 의 `~/.nv-fleet-execution` SQLite 를 읽는 구조는 두 저장소의 런타임 결합이며, NV 내용해시 게이트 때문에 계약 한 줄 바꿀 때마다 매니페스트 재고정이 따른다. Phase 2.5 공수는 과소평가.

## 4. §9-1 템플릿 서명 모델 독립 평가

- **현 보장:** 승인은 `jobId + planDigest` 에 정확 바인딩(`execution-approval.cjs:22-25`), planDigest 는 요청 전 필드 해시(`job-contract.cjs:6-8`). 템플릿 모델은 이 F1 "정확 바인딩" 을 **폐기**하고 "범위 바인딩" 으로 바꾸는 것이다.
- **공격면:** 파생 작업을 만드는 주체는 에이전트다. 에이전트(또는 에이전트를 조종한 프롬프트 주입)가 고를 수 있는 것: `sourceCommit`(자기가 만든 임의 커밋), cwd, 인자, 대상 파일. `eslint` 설정은 JS 실행, `test_subset` 은 테스트 코드 실행 — **읽기 전용 샌드박스 안에서도 임의 코드 실행**이고 네트워크가 열려 있으면 i7 의 읽을 수 있는 모든 것(ssh 키·.env) 이 유출 경로. `tsc` 도 트리의 `typescript` 바이너리를 쓰면 같다. "파일 변경 감지 시 실패" 는 사후 탐지이지 방지가 아니다.
- **에이전트 남용 시나리오:** 악성 커밋 push → 그 SHA 로 파생 작업 → 워커가 실행 → 결과 원장에 유출 데이터 기록 → Mac 훅이 "히트" 로 읽어 컨텍스트에 주입. 템플릿 서명 1회로 7일간 무인 반복.
- **최소 안전 범위:** v1 은 `git_diff_stat` 과 `tsc_noemit` 만. argv 는 템플릿에 **고정 문자열**로, 에이전트 입력은 정규식 화이트리스트 파일 목록뿐. 도구 바이너리는 워커가 소유한 고정 경로(트리의 node_modules 금지). `sourceCommit` 은 임의 SHA 가 아니라 **서명 시점 base 의 후손이며 origin 보호 ref 에 존재**할 것. 네트워크 차단(WSL2 는 `unshare -n` 또는 방화벽 규칙을 프로파일이 검증). 시간당 작업 수·동시 1·출력 상한·TTL 상한. **취소 목록**(만료 전 폐기) 을 워커가 매 틱 확인.
- **템플릿 digest 에 반드시 포함:** schemaVersion, templateId, issuer, projectId + 원격 URL, node, 허용 commandClass 별 정확 argv, 도구 바이너리 경로+해시, sourceCommit 허용 규칙(base SHA), 프로파일 이름+프로파일 코드 digest, 최대 동시/시간당/총 작업 수, 작업 TTL 상한, 출력 바이트 상한, expiresAt(≤7 d), 파생 작업 바인딩 규칙 자체. 파생 작업은 `templateDigest + 자기 digest` 를 지니고 워커가 "작업 ⊂ 템플릿" 을 재계산해야 한다.
- **결론:** 허용하더라도 Phase 3 이후, 위 범위로만. Phase 1~2 에서는 로컬 워커로 대체하는 것이 안전하고 빠르다.

## 5. Phase 1 즉시 개선 (우선순위순, 5개)

1. **진짜 훅을 먼저 배선하고 그 위에서 K1 을 재라.** 에이전트별 stdin/stdout 훅 프로토콜에 맞춘 클라이언트, 공유 settings 에는 `[ -f ] &&` 가드. 동시에 데몬 바인드를 `127.0.0.1`/소켓 0600 으로 바꾸고 `/telemetry` 를 로컬 전용으로. (P1·보안 동시 해결)
2. **§4 를 "동기 L0 / 비동기 그 외" 로 고쳐 써라.** 훅 예산 30 ms 안에서는 L0(정규식/시그니처) 만 응답하고, L2/L3 는 백그라운드에서 판정해 L0 원장에 write-through 하는 구조를 명시. 현재 문서의 사다리는 자기모순.
3. **1.6(실 Laya 설치) 삭제, 1.5 를 `error_signatures.patterns` 재사용으로 축소.** 이미 있는 정규식을 코드가 읽게 하는 것이 L0 v0 이다. 새 의존성 0.
4. **죽은 설정·상수를 한 번에 정리.** 루트 `routing_policy.json` 삭제 후 `evaluate_route` 가 `config/` 를 실제로 읽게, `+18.5/34.2/38.5/18.0/18.2/12.0` 과 대시보드 문자열 제거, 시뮬 단언 테스트(P9) 를 실측 기반으로 교체, `skills/**` 차단 규칙 제거.
5. **Track 2 를 "Mac 로컬 워커 + 더티 트리 지원" 으로 재정의.** treeDigest 는 `git write-tree`(임시 인덱스) 기반, Windows 는 로컬 히트율 실측 후 결정. 병행해 gold 셋 마스킹 규칙(경로·토큰·본문 절단) 을 스키마에 먼저 넣는다.

## 6. KPI 비판

| KPI | 판정 | 이유 |
|---|---|---|
| K1 훅 p50 | 지금은 **측정 불가** | 훅이 없다(P1). 배선 후에도 p50 은 1.5 s 타임아웃 꼬리를 숨긴다 — p99·타임아웃률·`allow` 폴백률을 추가해야 의미 |
| K2 무토큰 종결율 ≥60% | **허영 지표** | 분모 미정의(전체 호출? 실패 호출?). write-through 뒤 반복 에러는 자동 L0 히트라 숫자가 저절로 오른다. "종결" 뒤에도 에이전트는 주입 문구를 읽고 추론하므로 토큰이 0 이 아니다 |
| K3 <1.0%p | **통계적으로 무의미** | 300건이면 95% CI 가 ±3~5%p. 자기 라벨(R6) 편향까지 겹침. 수천 건 없이는 1%p 를 판별 못 함 |
| K4 캐시 미스 ≤2% | **모델 오류** | cache_creation 은 대화 증분·TTL 만료가 본체(§2). 지문과 무관하고 2% 는 구조적으로 도달 불가 |
| K5 히트율 ≥40%, 대기 0초 | **구현 불가 전제** | tool_result 대체가 훅 API 에 없음(P2). "0초" 는 실제 명령이 여전히 실행되므로 정의 불명 |
| K6 낭비율 ≤30% | 측정 가능하나 K5 종속 | |
| K7 $2/일 | **KPI 아님** | 미터가 없다(P10). 설정 상수 |

**빠진 진짜 KPI:** 세션당 순 output_tokens/비용 전후 비교(유일하게 돈이 걸린 지표), 오처방률(주입된 처방이 틀려 에이전트를 더 돌게 한 비율), 훅 타임아웃 → `allow` 폴백률.

---
요약: 계획은 자기 코드의 "정직화" 를 첫 과제로 잡은 점만 맞다. 그 외 기준선(훅 없음)·L3(HTTP 없음)·Laya 수치(GPU 값)·C2 확장 공수(계약·어댑터·전송 전부 신규)·tool_result 반환(훅 API 불가)·캐시 진단(모델 오류) 이 전부 검증 없이 쌓여 있어, Phase 1 을 위 5개로 축소하지 않으면 Phase 2 이후는 존재하지 않는 기반 위에 세워진다.
