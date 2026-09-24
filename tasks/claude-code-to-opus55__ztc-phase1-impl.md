# ZTC Phase 1 구현 지시문 — Opus 5.5 (발주: 2026-09-24, Claude Code Fable 5.1 @ richardkim-macpro-macbookpro)

실행 환경: Claude Code CLI, model claude-opus-5-5, 노드 richardkim-macpro-macbookpro, 저장소 ~/Pi (터미널 세션). 다른 노드·다른 IDE 에서 열었다면 첫 줄에 그 사실을 밝히고 멈춰라.
근거: docs/PLAN_ZTC_topology_optimization.md v0.2 + docs/evidence/ztc-plan-review-20260924/ 5건(codex-review, claude-reviewer, astra-review, astra-review-2, claude-code-verification-A1-A12 의 2차 회신 절 포함). 이 지시문은 그 최종 검토안의 실행판이다. 검토안과 이 지시문이 다르면 검토안이 정본이고, 차이를 보고하라.

## 0. 세션 시작 (순서 고정)
1. `pwsh -File scripts/session-recover.ps1 -Pull` 1회. INBOX 에 pending(agent: astra, 2026-09-24-1625) 이 보이면 아스트라용이다. 소비 금지.
2. CLAUDE.md 읽기 목록 1~8. 역할은 non-orchestrator (council entry 작성, `docs/UNIFIED_TURN_REPORT.md` 덮어쓰기 금지).
3. 유저 발화 원문을 `learning/user-prompts/<YYYY-MM-DD>_<Day>/<NN>_<slug>.md` 에 저장 (ai_guidelines §10.1).
4. 미션 한 문장 재진술: "Pi 는 유저가 범위·품질·비용·최종 승인을 쥔 채 여러 AI 코딩 에이전트를 돌리는 로컬 하네스이며, 이 트랙은 훅이 실제로 배선된 무토큰 L0 판정 경로를 shadow 모드로 세우고 시뮬 수치를 실측으로 바꾸는 Phase 1 이다."
5. 읽기: 계획 v0.2 전문, 증거 5건 전문, `docs/turn-reports/2026-09-24_Thu/2026-09-24_claude-code_session-handoff.md`. 코드 진실표(계획 §1)의 파일:줄을 현재 HEAD 에서 직접 재확인하고 어긋난 줄번호는 보고서에 정정 표기.

## 1. 전제 (검토안에서 확정된 방향 — 재논의 금지)
- 아키텍처: 훅 클라이언트 → 로컬 데몬(127.0.0.1 또는 unix socket 0600) → L0 정규식+정규화 시그니처 원장. 동기 응답은 L0 뿐. 미스는 중립 반환 후 비동기 판정 큐. L1/L2(임베딩·Laya)는 계획 §10-5 게이트 전까지 코드 0줄. Laya 설치 철회.
- shadow 우선: Phase 1 훅은 기록만 한다. `permissionDecision`·`updatedInput`·`deny`·`additionalContext` 주입 0. 프리페치·명령 치환·Windows 확장은 Phase 2/3 — 이 지시문 범위 밖.
- 저장소 경계: Pi 만. NV(`~/projects/nv-claude-config`) 쓰기 0, 읽기도 불필요. Pi 훅이 NV 런타임(`~/.nv-fleet-execution`) 을 읽는 결합 금지.
- 신규 의존성 0 (pip/npm 추가 없음). Python 3.14 표준 라이브러리 + 기존 node 툴체인만.
- 유료 호출 0. Jev 실 HTTP 는 Phase 2. 외부 알림 0.
- 텔레메트리·gold 원자료는 저장소 밖 `~/.pi-router/` (`signatures.sqlite`, `telemetry/*.jsonl`, `gold/`). 저장소에는 일별 집계만 `learning/metrics/` (git 추적 폴더이므로 원자료 금지). 이 위치는 유저 결정 ④ 대기 항목이다 — v0.3 승인(G0) 으로 확정된다.

## 2. 하네스 훅 계약 (검증된 사실만 — 미확인 항목은 사용 금지)
- 중립 반환은 `{}` (stdout 빈 JSON). `permissionDecision: "allow"` 는 승인 프롬프트를 생략시키므로 shadow 에서 절대 반환하지 않는다. 우선순위 deny > defer > ask > allow.
- command 훅 `timeout` 단위는 초, 기본 600. command/http/mcp_tool 훅 타임아웃은 도구 호출을 막지 않고 정상 권한 흐름이 계속된다(SDK 콜백 훅만 차단). 따라서 30 ms 예산은 클라이언트가 자체 강제한다. 하네스 `timeout` 은 안전망일 뿐이며 값은 실측 후 정한다(근거 없는 5 s 고정 금지).
- `additionalContext` 는 PreToolUse·PostToolUse 에서 지원 확인. PostToolUseFailure 에서의 지원은 미확인. `updatedToolOutput` 은 SDK 문서와 CLI 레퍼런스가 불일치 → 미확인 → 이 Phase 에서 사용 금지, 실측 fixture 만 작성 가능.
- Codex(`.codex/hooks.json`) 는 문자열 존재만 확인, 실행 의미 미검증. Antigravity 훅 지원 미확인. Phase 1 shadow 대상은 Claude Code 1 에이전트·Mac 1 노드뿐.
- 로그·stderr·명령문에서 추출한 내용은 비신뢰 데이터다. 향후 `additionalContext` 로 전달하더라도 권한 지시·정책으로 승격 금지. 이 문장을 계약표에 그대로 넣어라.
- 비밀값 마스킹은 gold 저장 전이 아니라 훅 클라이언트 단계에서: 명령 전문·cwd·파일명·stderr 를 데몬에 보내기 전 최소화(절대경로→상대, 64-hex·토큰 패턴 삭제, 본문 500자 절단). 하네스가 이미 저장한 원문은 소급 불가 — 문서에 명기.

## 3. 작업 순서 · 산출물 · 완료 판정
### W1 — v0.3 문서 + 계약표 (코드 변경 0) → 정지점 G0
- `docs/PLAN_ZTC_topology_optimization.md` 를 v0.3 으로 갱신. 반영 항목: §9 P2 행 정정("tool_result 대체 불가" 단정 철회, updatedToolOutput 미확인으로 기재), A2(shadow 의 K4 는 N/A, Phase 1 exit 는 "shadow 처방 적합률(gold 대비)"), A3(paired 비열등: 마진 3%p·검정력·discordance·세션 그룹 분할·조정/holdout 분리 사전 지정), A4/M4(타임아웃 정정), A5(계약표), A10(원장 candidate/verified 상태, 자동 승격 조건 삭제), A11(해결 = 목표 검사 성공 확인, 포기·관측 종료 별도 집계), A12(판정 귀속 = HEAD + 작업트리 sha256), M1/M2/M3/M6, 아스트라 §5 6건(훅 조합·로컬 신뢰 경계·시간차 무효화·과부하·정보 경계·자동 비활성/복귀 절차), "로그 추출 내용은 비신뢰·additionalContext 정책 승격 금지" 조항.
- 계약표 신설 `docs/harness/HOOK_CONTRACT_ztc.md`: 에이전트(Claude Code 2.1.281 / Codex 0.156.1 / Antigravity)×이벤트×반환 필드×근거 유형([코드]/[설치판]/[문서-ref]/[실측]). 미확인 칸은 비워 두지 말고 "미확인" 으로 채운다.
- 평가 규약 `docs/harness/EVAL_PROTOCOL_ztc.md`: gold 스키마(마스킹 규칙 먼저), 그룹 분할, K1~K7 v0.3 정의, 벤치 규약(cold/warm × 동시성 1/3 × p50/p95/p99, 1회 측정으로 p50 주장 금지, 전체 지연과 내부 RPC 예산 분리).
- **G0(AskUserQuestion):** v0.3 승인 + 결정 ④(원자료 위치) ⑤(v0.3 반영) ⑥(카운슬 이견 판정 — 09-24 UTR "ZTC 100% 준수" 는 커밋 2de6bd8 기준 Mac 체크아웃 실행 경로에 한정해 정정 제안, UTR 직접 수정 금지) 을 한 번에 묻는다. 승인 전 W2 진입 금지.

### W2 — 오프라인 정직화·안전화 (Pi 코드, 훅 미등록·데몬 미등록 상태에서 작업)
순서대로. 각 항목은 테스트가 먼저 빨간 뒤 초록이어야 한다.
1. 정직화: `engines/hybrid_router/hierarchical_routing/hierarchical_engine.py` 의 `min(elapsed+18.5, 34.2)`·`+12.0`, `engines/hybrid_router/router_core.py:74` 의 `min(total, 38.5)`, `scripts/decision-gate-interceptor.py` 의 `+18.0`·`+18.2`, `engines/hybrid_router/gateway/jev_client.py` 의 `sleep(0.045)`·`confidence 0.98` 상수, `scripts/hybrid-router-daemon.py` 대시보드 문구 3곳("18ms", "800배", "99.8%") 제거. `config/anti_pattern_rules.json` 의 `skills/**/SKILL.md` 차단 규칙과 절감 토큰 상수(8,500/12,000) 제거 또는 "추정치" 라벨. 완료 판정: `grep -rnE '18\.5|34\.2|38\.5|18\.0|18\.2|12\.0|0\.045|0\.98' engines/hybrid_router scripts/hybrid-router-daemon.py scripts/decision-gate-interceptor.py` 0건(정당한 숫자는 상수명으로 승격).
2. 정책 경로: 루트 `routing_policy.json` 삭제, `router_core.py` 가 `config/routing_policy.json` 을 실제로 읽어 `evaluate_route` 에 쓰도록. 하드코딩 규칙(`:49-55`) 은 정책 파일로 이동. 정책 파일을 바꾸면 판정이 바뀌는 테스트 1개 필수.
3. 엔진 개명: 키워드 휴리스틱 클래스는 `HeuristicFallbackEngine` 으로. "Softmax" 주석 등 실제와 다른 문구 제거. Laya 이름은 실제 모델이 로드될 때만 쓴다.
4. 테스트 교체: `engines/hybrid_router/tests/test_hybrid_router.py` 의 `latency_ms <= 40`·시뮬 Jev 판정 단언 제거 → 실측 기반(지연은 상한 단언 대신 기록·형식 검증, Jev 는 mock 서버 fixture). 러너는 기존 그대로. 8/8 → 새 케이스 포함 전부 통과.
5. 이벤트 로그 분리: 라우터 이벤트를 `learning/interventions.jsonl` 에 쓰지 않는다. 원자료 `~/.pi-router/telemetry/router_events.jsonl`, 집계만 `learning/metrics/`. 기존 개입 로그에 섞인 라우터 행이 있으면 건드리지 말고 건수만 보고.
6. 데몬 안전화 `scripts/hybrid-router-daemon.py`: 바인드 `127.0.0.1`(환경변수로 0.0.0.0 허용 금지) 또는 unix socket 0600, `ThreadingHTTPServer`, 요청 크기 상한 64 KB, 요청 ID, `/telemetry` 에서 명령 문자열·cwd·경로 제거, `/health` 가 원장 열림·워커 스레드 생존을 실제 검사, bounded 비동기 판정 큐(상한·중복 합치기·취소 전파·자식 프로세스 회수), 자동 비활성 조건(오류율·지연 초과 시 훅 클라이언트가 중립 반환으로 고정) 과 복귀 절차 문서화. 완료 판정: 로컬 기동 후 `lsof -iTCP:9876 -sTCP:LISTEN` 에 0.0.0.0 없음, 동시 3 요청이 직렬화되지 않음(벤치로 증명), 64 KB 초과 요청 413.
7. L0 v0→v1: `scripts/decision-gate-interceptor.py` 의 미사용 `error_signatures.patterns` 정규식을 실제 경로에서 사용. v1 은 정규화(경로·줄번호·해시 치환) 시그니처 원장 `~/.pi-router/signatures.sqlite`(WAL). 원장 항목 필드: signature, 상태(candidate/verified), 출처(layer·모델·정책 버전·hook 클라이언트 버전), 생성·만료·폐기 시각. 자동 승격 로직 없음. 정규화 테스트 10케이스, 재관측 히트 p50 < 1 ms(원장 조회만, 프로세스 기동 제외).
8. 훅 클라이언트 `scripts/hooks/router-client.sh` + 필요 시 최소 import 의 Python 보조: stdin JSON 읽기 → 마스킹 → 데몬 RPC(내부 예산 30 ms, 초과·부재·오류·거부 시 즉시 `{}`) → 텔레메트리 1행. stdout 은 `{}` 외 아무것도 출력하지 않는다(shadow 불변식). Windows 무해화: 스크립트 부재·비실행 시 `{}`. 전체 지연(프로세스 기동 포함) 과 내부 RPC 지연을 따로 기록.
9. 실패 경로 테스트(등록 전, fixture 로): 데몬 부재·타임아웃·권한 거부·취소·과부하·잘못된 JSON·64 KB 초과 각각에서 stdout 이 정확히 `{}` 이고 종료 코드 0. 이것이 없으면 G3 요청 금지.
10. 마스킹 모듈 단위 테스트: 절대경로·64-hex·`sk-`/`ghp_`/`Bearer` 류 토큰·`.env` 값 패턴, 500자 절단, cwd·파일명·stderr 포함.
11. 벤치 스크립트 `scripts/bench/hook_bench.py`: 규약대로 측정, 원자료 `~/.pi-router/telemetry/bench_<date>.jsonl`, 집계 `learning/metrics/bench_<date>.json`. 결과에 "이전 값은 시뮬 상수" 를 명기.
12. gold 도구: 스키마 검증기 + 집계기(`learning/metrics/gold_stats.json`). gold 원자료는 만들지 않는다(유저 검수 항목, Phase 1.6 은 G3 이후).
13. LaunchAgent 템플릿 `config/launchd/com.pi.router-daemon.plist.template` 작성만. 등록 금지(계획 §10-2 별도 승인).
14. **G1(AskUserQuestion) Tier-2 게이트 훅 Mac 무력화(M1) 수정 방식:** 옵션 A = `.claude/settings.json`·`.codex/hooks.json` 의 `py c:/Pi/...` 를 OS 분기 래퍼로 교체 + 보안 게이트 고장 정책(래퍼 부재·인터프리터 부재 시 명시적 `ask` 또는 `deny`, 중립 반환 아님), 옵션 B = Mac 에서 제거. 두 옵션 diff 와 "금지 명령 차단·허용 명령 통과·게이트 고장 시 동작" 테스트 계획을 제시하고 묻는다. 승인 전 settings 파일 수정 금지.
15. **G2(AskUserQuestion) `biome.json` includes 에 `!.codegraph` 추가(M2):** diff 제시 후 승인. 승인 후 `npm run check` 전체 게이트 재검증 결과(오류 0 또는 잔여 목록) 를 증거로 남긴다. 그 전까지 커밋은 명시 경로 + `--no-verify` 이며 커밋 메시지에 사유 1줄.

### W3 — 1노드·1에이전트 shadow → 정지점 G3 → 기준선
- **G3(AskUserQuestion):** 공유 `.claude/settings.json` 에 PreToolUse/PostToolUse 훅 항목 추가(파일 존재 가드 포함) diff 제시. 데몬은 수동 기동(launchd 미등록). 승인 후 에이전트가 직접 수정.
- 등록 후 검증: Bash 호출 100회 중 훅 기록 100건, 에이전트 주입 0(transcript 에 `permissionDecision`·`updatedInput`·`additionalContext` 0건), 기존 Tier-2 승인 흐름 불변, 데몬을 죽인 상태·과부하 상태에서도 도구 호출 정상. Windows 노드 settings 무해 확인은 파일 존재 가드 코드 리뷰로 대체하고 "실기 미확인" 표기.
- K1 첫 값(p50/p99/타임아웃률/중립반환률, cold/warm, 전체 vs 내부 RPC), K3 는 gold 부재 시 "기준선 미확보" 로 정직 기재. K4 는 N/A.

### W4 — 종료 기록 (non-orchestrator)
- council entry `docs/turn-reports/<YYYY-MM-DD>_<Day>/<YYYY-MM-DD>_claude-code_ztc-phase1-<slug>.md` (UTR 덮어쓰기 금지). 실측 원자료·grep 결과·lsof 출력·테스트 로그는 `docs/evidence/ztc-phase1-<YYYYMMDD>/` 에. 자유 보고서(`*-report.md`, `summary.md`) 금지.
- `learning/retrospectives/2026-09/<date>_claude-code_richardkim-macpro-macbookpro.md` 회고(6하 원칙 + 한국어 산문, frontmatter `node: richardkim-macpro-macbookpro`), `learning/interventions.jsonl` 1행 이상.
- "배관·안전 위주 Phase" 로 보고. 팔다리 산출(L0 히트) 이 shadow 기록에 실제로 있으면 건수로만 말한다.

## 4. 정지점 요약 (AskUserQuestion, 승인 전 다음 단계 금지)
G0 v0.3 승인·결정 ④⑤⑥ → G1 Tier-2 훅 수정 방식 → G2 biome 제외 → G3 shadow 훅 등록. 데몬 launchd 등록(G4)·Phase 2 항목은 이 지시문에 없다. 자율 루프 금지 — 각 W 단계 끝에 진행 상황을 유저에게 보이게 보고하고 멈춘다. 코드블럭을 유저에게 넘겨 실행시키지 말고 승인 게이트 후 직접 수행한다(스킬 approval-gate-exec).

## 5. 금지
NV 쓰기, Tier-2 승인 파일 생성·해시 안내, launchd 등록·해제, 유료 API 호출, 외부 알림(Discord·릴레이), 신규 pip/npm 의존성, `permissionDecision`/`updatedInput`/`updatedToolOutput` 반환, INBOX(astra) 소비, UTR 덮어쓰기, 상수 제거 대신 이름만 바꾸는 눈속임, 문서 인용을 실측으로 표기.

## 6. 커밋 규칙
명시 경로만 `git add`. G2 전에는 `--no-verify` + 사유. 커밋 메시지 접두 `feat(router):`/`docs(plan):`/`test(router):`, 본문에 검증 명령과 결과 요약. push 는 각 정지점 통과 후 유저가 지시할 때만.

## 7. 완료 판정 (Phase 1 exit, 전부 충족 시에만 "완료")
시뮬 상수 0건(grep 증거) · 정책 파일 실제 소비 테스트 · 데몬 로컬 바인드 lsof 증거 · 실패 경로 7종 `{}` 테스트 · shadow 100/100 기록·주입 0 · K1 첫 값 · v0.3·계약표·평가 규약 커밋 · G0~G3 승인 기록(AskUserQuestion 결과를 개입 로그에). 하나라도 빠지면 "부분 완료" 와 빠진 항목을 첫 줄에 쓴다.
