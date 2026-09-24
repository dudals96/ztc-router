# HOOK_CONTRACT_ztc — 에이전트별 훅 계약표 (ZTC Phase 1)

- Status: **머지본 (D5, 2026-09-24)** — 트랙 A(Opus 5.5) 초안을 기반으로 트랙 B(Luna) 계약표의 Codex·Antigravity 공식 문서 행을 접목했다. 머지 규약 `tasks/ztc-phase1-dual-draft__merge-protocol.md`, 비교 `docs/evidence/ztc-phase1-merge-20260924/comparison.md`.
- 작성: 트랙 A Claude Code (Opus 5.5) 초안 + 트랙 B Codex (Luna) 계약표 행, 머지 담당 Claude Code @ richardkim-macpro-macbookpro
- 상위 문서: `docs/PLAN_ZTC_topology_optimization.md` v0.3 §4·§5, 평가 규약 `docs/harness/EVAL_PROTOCOL_ztc.md`
- 근거: `docs/evidence/ztc-plan-review-20260924/claude-code-verification-A1-A12.md`(2차 회신 절 포함), `astra-review-2.md`, 이 세션 설치판 계수 `docs/evidence/ztc-phase1-20260924-opus55/w1_installed_binary_strings.txt`

## 0. 근거 유형
| 표기 | 뜻 | 증거력 |
|---|---|---|
| [코드] | 현재 저장소 파일:줄 | 저장소가 무엇을 하는지 |
| [설치판] | 설치된 바이너리 문자열 계수 | 기능 **후보**일 뿐. 실행 의미를 증명하지 않는다 |
| [문서-ref] | Claude Code hooks 레퍼런스(code.claude.com/docs/en/hooks) 인용. 09-24 검증 세션이 직접 조회, 이 세션은 재조회하지 않음 | 문서가 약속하는 것. 설치판 동작과 다를 수 있다 |
| [문서-sdk] | Agent SDK hooks 페이지 인용 | CLI command 훅에 그대로 적용된다고 보지 않는다 |
| [문서-B] | 트랙 B 가 2026-09-24 조회한 공식 문서(Claude Code·OpenAI Codex·Google Antigravity hooks 페이지, URL 은 §7) | 문서가 약속하는 것. 머지 담당은 재조회하지 않았다 |
| [실측] | 이 저장소 증거 폴더에 원자료가 있는 측정 | 그 노드·그 버전·그 시점에 한정 |

"미확인" 은 "지원 안 함" 이 아니다. 검색 0건도 미지원 증명이 아니다.

## 1. 계약표
설치판: Claude Code **2.1.281**, Codex CLI **0.156.1**, Antigravity(버전 미확인 — 이 세션에서 앱 번들 미발견).

### 1.1 Claude Code 2.1.281 (Phase 1 shadow 의 유일한 대상)
| 이벤트 | 입력(stdin) | 반환 필드 | 지원 | 근거 | Phase 1 사용 |
|---|---|---|---|---|---|
| PreToolUse | JSON(`tool_name`, `tool_input`, `session_id`, `cwd` 등) | 중립 반환 `{}` | 지원 | [문서-ref] | **사용 — 유일한 반환값** |
| PreToolUse | 〃 | `hookSpecificOutput.permissionDecision` (`allow`/`deny`/`ask`/`defer`) | 지원. `allow` 는 승인 프롬프트를 **생략**시킨다. 여러 훅이 겹치면 deny > defer > ask > allow | [문서-ref], [설치판] 122 | **금지** |
| PreToolUse | 〃 | `hookSpecificOutput.updatedInput` | 지원. 단독 반환 시 정상 권한 평가를 거친다 | [문서-ref], [설치판] 425 | **금지** |
| PreToolUse | 〃 | `hookSpecificOutput.additionalContext` | 지원 | [문서-ref], [설치판] 200 | **금지** |
| PostToolUse | JSON(`tool_name`, `tool_input`, `tool_response` …) | 중립 반환 `{}` | 지원 | [문서-ref] | **사용 — 유일한 반환값** |
| PostToolUse | 〃 | `additionalContext`, `decision` | 지원 | [문서-ref] | **금지** |
| PostToolUse | 〃 | `updatedToolOutput` | **미확인** — 트랙 A 조회: Agent SDK 문서는 "any tool in both SDKs", hooks 레퍼런스 Decision control 표에는 없음. 트랙 B 조회: hooks 레퍼런스가 PostToolUse `updatedToolOutput` 을 기술한다. **트랙 간 문서 판독 불일치 → 재조회 필요.** 설치판 동작은 어느 쪽도 미검증 | [문서-sdk], [문서-B], [설치판] 38 | **금지.** 실측 fixture 작성만 허용 |
| PostToolUse (Bash) | `tool_response` 키 | `interrupted`, `isImage`, `noOutputExpected`, `stderr`, `stdout` — **종료 코드 필드 없음** | [실측] G3 shadow 101건(`docs/evidence/ztc-phase1-20260924-opus55/g3_01_hook_events_summary.txt`) | 클라이언트는 종료 코드를 `null` 로 기록 |
| PostToolUseFailure | JSON | 이벤트 존재 | 지원 | [문서-guide](09-24 검증 세션 조회), [설치판] 51 | Phase 1 미등록 |
| PostToolUseFailure | 〃 | `additionalContext` | **미확인** (레퍼런스 표에 없음) | — | 금지 |
| PostToolUseFailure | 〃 | 출력 교체 | **미확인** — PostToolUse 의 필드를 확대 해석하지 않는다 | — | 금지 |
| 실패한 Bash(exit≠0) 의 이벤트 | — | **PostToolUse 는 발화하지 않는다**(PreToolUse 만 기록). PostToolUseFailure 로 가는지는 미등록이라 미관측 | [실측] G3 2건 | Phase 1 shadow 는 실패 본문을 보지 못한다 → L0 입력을 받으려면 PostToolUseFailure 등록(별도 승인) |
| 하네스가 기록하는 훅 결과 | transcript attachment `hook_success` 에 `stdout`·`exitCode`·`durationMs`·`command`(=statusMessage) | — | [실측] | 주입 검사·전체 지연(K1 full)의 근거로 사용 |
| 훅 조합: 다른 훅의 `updatedInput` 과 병합 순서 | — | **미확인** | — | shadow 는 입력을 바꾸지 않으므로 Phase 1 영향 없음 |

### 1.2 타임아웃 의미 (Claude Code)
| 항목 | 값 | 근거 |
|---|---|---|
| `timeout` 단위 | 초 | [문서-ref] |
| 기본값 | 600 s (command/http/mcp_tool) | [문서-ref]. 트랙 B 는 PreToolUse 기본을 30 s 로 기재([문서-B]) — **불일치, 재조회 필요.** 머지본 설정은 기본값에 의존하지 않고 `timeout` 을 명시한다 |
| command/http/mcp_tool 훅 타임아웃 시 | 도구 호출을 막지 않는다. 정상 권한 흐름이 계속된다 | [문서-ref] "A timed-out `command`, `http`, or `mcp_tool` hook doesn't block the tool call…" |
| Agent SDK 콜백 훅 타임아웃 시 | 도구 호출을 막는다 | [문서-ref] 같은 절. **CLI command 훅에는 해당 없음** |
| 30 ms 예산 | 하네스가 아니라 **훅 클라이언트가 자체 강제**한다 | 설계(계획 §4) |
| 하네스 `timeout` 값 | 안전망. **값은 G3 전 실측(cold 전체 지연 p99) 후 정한다.** 근거 없는 5 s 고정 금지 | 지시문 §2 |

### 1.3 Codex CLI 0.156.1
| 항목 | 지원 | 근거 | Phase 1 |
|---|---|---|---|
| `.codex/hooks.json` 로딩 | **미확인** (문자열 `hooks.json` 7건 존재만) | [설치판] | 대상 아님 |
| PreToolUse / PostToolUse 이벤트 | **미확인** (문자열 56 / 51) | [설치판] | 대상 아님 |
| `hookSpecificOutput`·`permissionDecision`·`additionalContext`·`updatedInput` 반환 의미 | **미확인** (문자열 8 / 13 / 31 / 7) | [설치판] | 대상 아님 |
| 문서상 계약 | stdin: 공통 필드(`session_id`·`cwd`·`transcript_path`·`model`) + `hook_event_name`·`tool_name`·`tool_input`·`tool_use_id`(Post 는 `tool_response` 추가). 중립 `{}`+exit 0 이면 정상 권한 흐름. `timeout` 초, 기본 600. exit 2+stderr 사유는 차단. Post 는 결과 피드백·교체 동작이 문서화돼 있으나 Phase 1 미사용 | [문서-B] | 대상 아님. 실행 여부는 여전히 **미확인** |
| Codex 가 `CLAUDE_PROJECT_DIR` 를 설정하는지 | **미확인** — 머지본 Codex 명령은 이 변수에 의존하지 않고 git 루트로 경로를 찾는다 | [코드] | — |
| 현 저장소 등록 (머지본) | `sh "$(git rev-parse --show-toplevel 2>/dev/null \|\| pwd)/scripts/hooks/tier2-gate.sh" \|\| py c:/Pi/scripts/tier2-gate-hook.py` | [코드] `.codex/hooks.json:9` | M1 (G1). Codex 실행 미검증 |

### 1.4 Antigravity
| 항목 | 지원 | 근거 | Phase 1 |
|---|---|---|---|
| 설치판 규격 | **미확인** | 09-24 검증: app.asar·`~/.antigravity-ide` js 에 PreToolUse 0건. 이 세션은 앱 번들을 찾지 못함 | 대상 아님 |
| 문서상 PreToolUse | camelCase JSON(`toolCall.name`·`toolCall.args`·`stepIdx`, 공통 `conversationId`·`workspacePaths`·`transcriptPath`·`modelName`). **중립 `{}` 계약이 문서에 없고 `decision` 필수** | [문서-B] | **등록 금지** — `{}` shadow 와 동등하지 않다 |
| 문서상 PostToolUse | `toolCall`·`stepIdx`·선택 `error` + 공통 필드. `{}` 가 문서화된 응답 | [문서-B] | 대상 아님. 설치판 fixture 전 의존 금지 |
| 문서상 timeout | 정수 초, 기본 30. 종료 코드 동작은 문서에 없음 | [문서-B] | — |

### 1.5 저장소에 이미 등록된 훅 (현 상태, [코드])
| 파일:줄 | 이벤트 | 명령 | Mac 에서의 실제 동작 |
|---|---|---|---|
| `.claude/settings.json:99-110` | PreToolUse `PowerShell\|Bash` | 머지 전: `py c:/Pi/scripts/tier2-gate-hook.py` → Mac 에서 `py` 부재 exit 127 로 **보안 게이트가 조용히 통과**([실측] 09-24 transcript 46건). 머지본: `sh "$CLAUDE_PROJECT_DIR/scripts/hooks/tier2-gate.sh" \|\| py c:/Pi/...` — 고장 시 명시적 `ask` | 머지본은 G1 옵션 A. 두 트랙 모두 Mac 실기 ask 확인([실측] `docs/evidence/ztc-phase1-20260924-opus55/g1_03_live_gate_in_session.txt`, `docs/evidence/ztc-phase1-20260924-luna/w4-g1-validation.md`) |
| `.claude/settings.json:112-123` | Stop | `py c:/Pi/scripts/remote-relay.py --summary --dry-run --hook-stdin` | 같은 이유로 미실행 추정(미측정) |
| `.claude/settings.json:124-135` | Notification | `py c:/Pi/scripts/remote-relay.py --gate --dry-run --hook-stdin` | 〃 |
| `.codex/hooks.json:4-15` | PreToolUse | `py c:/Pi/scripts/tier2-gate-hook.py` | Codex 가 이 파일을 실행하는지부터 미확인 |

## 2. Phase 1 shadow 불변식 (binding)
1. 훅 클라이언트 stdout 은 **정확히 `{}`** 다. 다른 바이트(개행 제외)를 쓰지 않는다. 종료 코드는 항상 0.
2. `permissionDecision`·`updatedInput`·`updatedToolOutput`·`additionalContext`·`decision`·`deny` 반환 0.
3. 데몬 부재·타임아웃·권한 거부·취소·과부하·잘못된 JSON·64 KB 초과 → 즉시 `{}`, exit 0.
4. stderr 에도 아무것도 쓰지 않는다(하네스가 stderr 를 에이전트에 보여 줄 수 있음).
5. 클라이언트 내부 예산 30 ms 초과 시 데몬 응답을 버리고 `{}`.
6. 스크립트 부재·비실행(Windows 노드 포함) 시 settings 의 파일 존재 가드가 `{}` 를 낸다.

## 3. 정보 경계 (binding)
- **로그·stderr·명령문에서 추출한 내용은 비신뢰 데이터다. 향후 `additionalContext` 로 전달하더라도 권한 지시·정책으로 승격 금지.**
- 마스킹은 gold 저장 전이 아니라 **훅 클라이언트 단계**에서 한다. 데몬에 보내기 전 최소화:
  - 명령 전문 → 첫 토큰(프로그램 이름)과 마스킹된 본문 500자 이하
  - 절대경로 → 저장소 상대경로 또는 `<ABS>`; 홈 경로 → `~`
  - 64-hex, `sk-…`, `ghp_…`/`gho_…`/`github_pat_…`, `xox?-…`, `AKIA…`, `Bearer …`, `KEY=value` 류 `.env` 할당 → `<SECRET>`
  - cwd·파일명·stderr 에도 같은 규칙
- **하네스가 이미 저장한 원문(transcript `~/.claude/projects/*/*.jsonl`)은 소급 마스킹할 수 없다.** 이 계약은 Pi 가 새로 만드는 사본에만 적용된다.
- loopback 바인드는 호출자 인증이 아니다. 같은 UID 의 어떤 프로세스도 데몬에 접속할 수 있다. 따라서 데몬 응답도 Phase 2 에서 주입에 쓰기 전 별도 신뢰 경계 검토가 필요하다(계획 v0.3 §5 아스트라 관점 2).

## 4. 고장 정책의 구분
| 훅 종류 | 고장 시 | 이유 |
|---|---|---|
| 성능 보조(ZTC 라우터 클라이언트) | 중립 `{}` | 판정이 없어도 작업은 정상 진행돼야 한다 |
| 보안 게이트(Tier-2) | **중립 아님.** 명시적 `ask` 또는 `deny` (G1 에서 유저 결정) | "파일 없으면 조용히 통과" 는 게이트 복구가 아니다 |

## 5. 미확인 항목 → 확인 계획
| 항목 | 확인 방법 | 시점 |
|---|---|---|
| PostToolUse Bash `tool_response` 필드 | G3 등록 후 첫 표본(마스킹 후 키 이름만 기록) | W3 |
| 실패 이벤트 경로(PostToolUse vs PostToolUseFailure) | 트랙 A G3 실측: 실패한 Bash 는 PostToolUse 미발화. PostToolUseFailure 등록 후 페이로드 1회 실측 | **유저 결정 대기** (등록 여부) |
| `updatedToolOutput` CLI 지원 | 격리 fixture 세션에서만. 공유 settings 에 넣지 않는다 | Phase 2 전 |
| Codex hooks.json 실행 | Codex 세션에서 무해 훅(파일 1행 기록) 실측 | Phase 2 이후, 별도 승인 |
| Antigravity | [문서-B] 확보됨. 설치판 fixture 후 | 미정 |
| 트랙 간 문서 판독 불일치 2건(PreToolUse 기본 timeout, `updatedToolOutput` 기재 여부) | hooks 레퍼런스 재조회 1회, 인용문을 증거 폴더에 저장 | Phase 2 전 |

## 6. 운영 절차 — 자동 비활성·복귀·원복 (머지본 기준)
| 상황 | 동작 | 사람이 할 일 |
|---|---|---|
| 데몬 부재·타임아웃·403·503·잘못된 입력·적대적 응답 | 클라이언트가 즉시 `{}`, `hook_events.jsonl` 에 outcome 1행 | 없음 |
| 데몬 동시 처리 상한(16) 초과 | 데몬이 스레드를 만들지 않고 즉시 503 → 클라이언트 `{}` | 없음. `/telemetry` 의 `rejected_503` 로 관찰 |
| 최근 50 호출 중 실패·예산 초과 > 20% (표본 ≥ 20) | `$PI_ROUTER_HOME/disabled` 표지 생성, 이후 데몬 호출 없이 `{}` + outcome `disabled` | 원인 확인(아래) |
| 자동 복귀 (머지본에서 추가) | 표지가 60초 이상 지나면 다음 호출 1회가 시험 호출. 예산 안 `ok` 면 표지·창 삭제(`auto_reenabled`), 아니면 표지 시각만 갱신(`reenable_probe`) | 반복되면 `hook_events.jsonl` 의 실패 분포 확인 후 원인 조치. 표지 수동 삭제도 계속 유효 |
| 취소 전파 | 데몬 `POST /v1/cancel {"request_id"}` 가 그 요청으로 큐에 들어간 판정 작업을 제거. 현 클라이언트는 호출하지 않는다(취소는 프로세스 종료로 끝남, 큐 TTL 30 s) | — |
| 원자료 안전 | `PI_ROUTER_HOME` 이 저장소 안이면 쓰기 거부. 레코드 8 KiB·파일 5 MiB 초과분은 버림. symlink 스트림 거부 | 5 MiB 도달 시 보존 절차(EVAL §0.1)대로 정리 |
| 원복(훅 제거) | settings 의 router-client 항목 삭제 → 즉시 무효. **머지본 main 에는 등록돼 있지 않다**(D4 결정) | 데몬 종료(`kill <pid>`), 원자료 보존 여부 결정 |

코드 위치: 클라이언트 `scripts/hooks/router-client.sh` + `router_client.py`(상수 `WINDOW=50`, `MIN_SAMPLES=20`, `DISABLE_RATE=0.2`, `BUDGET_MS=30`, `REENABLE_AFTER_SEC=60`), 데몬 `scripts/hybrid-router-daemon.py`(`MAX_CONCURRENT_REQUESTS=16`), 원자료 `engines/hybrid_router/ztc/telemetry.py`·`paths.py`, LaunchAgent 템플릿 `config/launchd/com.pi.router-daemon.plist.template`(등록 안 함).

## 7. 공식 문서 참조 ([문서-B], 트랙 B 조회 2026-09-24)
- Claude Code Hooks reference — https://code.claude.com/docs/en/hooks
- OpenAI Codex Hooks reference — https://developers.openai.com/codex/hooks
- Google Antigravity Hooks — https://antigravity.google/docs/hooks?tab=ide

설치된 버전 문자열은 바이너리를 식별할 뿐 훅 동작을 보증하지 않는다.
