<!-- Claude Code (Fable 5.1) @ richardkim-macpro-macbookpro, 2026-09-24 16:05 KST. 아스트라 인계(docs/session-handoffs/2026-09-24-1506) A1~A12 독립 재검증. 읽기 전용. 로컬 미커밋(인계·유저 지시로 commit/push 금지). -->

# A1~A12 재검증 판정표 + 놓친 관점

설치판: Claude Code 2.1.281 (`@anthropic-ai/claude-code/bin/claude.exe`), Codex 0.156.1, Antigravity(app.asar 4.4 MB). 근거 유형: [코드]=현재 저장소 파일:줄, [설치판]=바이너리 문자열 grep 건수, [문서]=공식 문서 인용(서브에이전트 조회, 실측 아님), [실측]=이 세션 transcript.

| ID | 판정 | 근거·보완 |
|---|---|---|
| A1 L0 미해결 20% 는 탐색 신호 | 채택 | 도입 조건을 "빈도×토큰비용 가중 unresolved" 로 재정의하고, 규칙 확장 대안을 먼저 시도한 뒤 증분 효과·오판정·메모리 손익표를 첨부해야 도입. ≥/> 는 ≥ 로 통일 |
| A2 shadow 에서 K4 측정 불가 | 채택 | 주입 0 이면 "주입 후 재발" 은 정의상 0 건. Phase 1 exit 의 K4 를 "shadow 처방 적합률(gold 대비)" 로 바꾸고, 실 K4 는 additionalContext 단계에서 채택/해결/재발/포기/회귀 5분류로 측정 |
| A3 300→3%p, 1000→1%p 는 충분조건 아님 | 채택 | 공식 검산: 오류 0건 단측 95% 상한 1−0.05^(1/n): n=90 → 3.27%, n=300 → 0.99% (일치). 이는 단일 오류율 상한이지 paired 비열등성이 아님. holdout 30% 면 평가 n=90. 설계: 시그니처/세션 그룹 분할, discordance 기반 표본 산정(McNemar), 평가 중 write-through 동결 |
| A4 fail-open ≠ explicit allow | 채택 + 추가 | [문서] 중립 반환은 `{}`; `permissionDecision: allow` 는 승인 프롬프트 생략; `updatedInput` 만 반환하면 정상 권한 평가를 거침; deny > defer > ask > allow. **[문서] 훅 타임아웃 시 PreToolUse 는 도구가 "훅 미응답" 실패 결과를 받음 — 타임아웃은 fail-open 이 아니라 도구 실패.** 타임아웃 단위는 초(기본 600 s). 따라서 30 ms 예산은 클라이언트 내부에서 자체 강제해야 하며 하네스 timeout 은 안전망(≥5 s)으로만 |
| A5 에이전트별 훅 계약 | 채택 | [설치판] Claude 2.1.281 바이너리: updatedToolOutput 14, PostToolUseFailure 20, permissionDecision 37, updatedInput 117, additionalContext 50, PermissionRequest 92. Codex 0.156.1 바이너리(`codex-darwin-arm64/vendor/.../codex`): PreToolUse 38, PostToolUse 36, hooks.json 7, hookSpecificOutput 7 → 지원 문자열 존재, 의미는 미검증. Antigravity: app.asar·`~/.antigravity-ide` js 에 PreToolUse 0 → **미확인**(지원 근거 없음) |
| A6 updatedToolOutput | 채택 | [설치판] 문자열 14건 + [문서] "any tool in both SDKs". 선행 검토 2건의 "tool_result 대체 불가" 단정은 **틀렸다**(v0.2 §9 P2 행 정정 필요). 단 사후 교체는 실행 비용을 줄이지 않으므로 시간 절감 메커니즘은 여전히 updatedInput. 추가: 실패 로그를 정규화 진단으로 교체하면 입력 토큰 절감이 결정적으로 측정 가능(놓친 관점 M5) |
| A7 write-tree 만으로 동등성 부족 | 부분채택 | [코드] Pi `tsconfig` 에 incremental/composite 없음 → .tsbuildinfo 쓰기 우려는 현재 미적용. 임시 index 방식은 `GIT_INDEX_FILE=<tmp> git add -A && git write-tree` 로 tracked+untracked 포함·ignored 제외가 정의됨. 키에 toolchain 지문(node·tsc 버전, lockfile 해시)과 `git diff` 비교 기준(HEAD/index/ref)을 포함해야 함 |
| A8 같은 UID ≠ 무부작용·사전승인 | 채택 | 대안: write-tree 오브젝트로 `~/.pi-router/snap/<digest>` 스냅샷 worktree 를 만들어 실행(활성 체크아웃과 경합 0, 읽기 전용). 네트워크 차단 수단은 macOS 에서 미확정(제안) |
| A9 cat cache; exit 는 원 명령과 비동등 | 채택 | 저장 스펙: stdout/stderr 분리, exit/signal, truncation 플래그, 인코딩, cwd/env 지문, tmp+rename 원자 발행, sha 검증, 경로 확인(realpath ⊂ ~/.pi-router). [문서] updatedInput 은 정상 권한 평가를 거치므로 치환된 `cat` 도 규칙 적용됨. 투명성: additionalContext 로 "prefetch 결과 반환됨" 을 함께 주입 |
| A10 L3 → L0 즉시 승격은 오류 증폭 | 채택 | 원장에 candidate/verified 상태, 출처(layer·모델·정책 버전), 만료·폐기·기권. 승격 조건: 같은 시그니처에서 처방 후 재발 0 이 N=3 회 관측되거나 명시 확인 이벤트 |
| A11 K2/K5/K7 는 순효과 미보장 | 채택 | 총비용(input+cache_write+cache_read+output+L3+retry), 해결률(같은 클래스 에러가 세션 내 재발하지 않음), 완료시간을 동시 보고. K5 분모·낭비 CPU 시간 가중 |
| A12 카운슬 판정은 코드·revision 귀속 | 채택 | [코드] `engines/hybrid_router` 전체에 torch/logit/from_pretrained/onnx 0건. `hierarchical_engine.py:60-62` 주석 "Softmax normalization" 이나 실제는 v/총합 나눗셈. 판정 문구는 "커밋 2de6bd8 기준 Mac 체크아웃의 실행 경로" 로 한정. UTR 정정은 제안만(§10-7) |

## 놓친 관점 (세 검토 모두 미언급, 이 세션 확인)
- **M1 Tier-2 게이트 훅이 Mac 에서 무력화.** [실측] 이 세션 transcript 에 `hook_non_blocking_error` PreToolUse:Bash 46건, `/bin/sh: py: command not found`, exit 127, 13 ms. 공유 settings 의 `py c:/Pi/...` 경로가 Mac 에서 매 Bash 마다 실패하고 조용히 통과된다. 보안 게이트가 이미 fail-open 상태이며, `.codex/hooks.json` 도 동일 경로. 새 훅 이전에 이것부터 고쳐야 한다(파일 존재 가드 + OS 분기).
- **M2 pre-commit 품질 게이트 우회.** [코드] 저장소 루트 `.codegraph` 심링크(→ `~/.omo/codegraph/...`, `.git/info/exclude` 로만 제외) 를 `biome check .` 가 스캔해 실패 → Mac 커밋이 상습적으로 `--no-verify`. Phase 1 의 "테스트·린트 게이트" 는 이 노드에서 실효 없음. `biome.json` includes 에 `!.codegraph` 1줄 추가가 필요(설정 변경 → 승인).
- **M3 텔레메트리 위치.** [코드] `learning/` 은 git 추적 818 파일. 계획의 `learning/metrics/hook_latency.jsonl` 은 매 도구 호출마다 1행이 4노드로 push 된다. 원자료는 `~/.pi-router/`, 저장소에는 일별 집계만.
- **M4 하네스 타임아웃 의미.** [문서] 단위 초·기본 600 s, 타임아웃 = 도구 실패. 계획 §4/R1 의 "30 ms 하드 타임아웃 → allow" 는 하네스가 아니라 클라이언트 스크립트가 구현해야 성립.
- **M5 updatedToolOutput 은 토큰 레버.** 장문 실패 출력을 정규화 진단 + 원문 파일 경로로 교체하면 입력 토큰 절감이 모델 없이 결정적으로 측정된다. ZTC 의 가장 싼 첫 성과 후보인데 세 검토 모두 "사후 교체는 시간을 못 줄인다" 까지만 말했다.
- **M6 훅 stdin 에 명령 전문.** 비밀값이 섞인 명령이 데몬·텔레메트리로 흐른다. 마스킹은 gold 저장 전이 아니라 훅 클라이언트 단계에서.

## Phase 1 첫 3작업 (권고, 미실행)
1. 계약·규약 문서화: 에이전트별 훅 계약표(위 [설치판] 근거 첨부), 중립 반환 `{}`, 클라이언트 내부 30 ms, 마스킹 위치, K4 → shadow 적합률, gold 그룹 분할. 코드 변경 0.
2. 오프라인 정직화·안전화 + M1/M2/M3 수정: 상수·정책 경로·로컬 바인드·bounded queue, Tier-2 훅 OS 가드, `biome.json` `.codegraph` 제외, 텔레메트리 경로.
3. 1 에이전트·1 노드 shadow: 성공뿐 아니라 데몬 부재·타임아웃·권한 거부·취소·과부하에서 주입 0·명령 변경 0·기존 승인 유지를 테스트로 증명한 뒤 기준선 측정.

---
## 2차 회신 (2026-09-24 17:10 KST) — 아스트라 `astra-review-2.md` 에 대한 항목별 동의/반박/미확인

근거 유형 추가: [문서-ref]=hooks 레퍼런스(code.claude.com/docs/en/hooks) 직접 조회, [문서-guide]=hooks-guide 직접 조회, [문서-sdk]=Agent SDK hooks 페이지(서브에이전트 인용).

| 항목 | 판정 | 근거·정정 |
|---|---|---|
| A2 "0%" → N/A | 동의 | 분모 부재. V:10 문구 정정 대상 |
| A3 절차 보완 | 동의 | 사전 지정 항목(마진·검정력·discordance·세션 상관·조정/holdout 분리) 채택 |
| **A4 타임아웃** | **동의 — 내 V:12 가 틀렸다** | [문서-ref] Timeouts: "A timed-out `command`, `http`, or `mcp_tool` hook doesn't block the tool call. The call continues through the normal permission flow… An Agent SDK callback hook that exceeds its timeout blocks the tool call." 내가 인용한 "도구 실패" 문장은 SDK 콜백 훅 조항이었다. 기본값 600 s(command/http/mcp_tool), 단위 초. ≥5 s 안전값은 철회 |
| A5 additionalContext | 부분 동의 | [문서-ref] Decision control 표: PreToolUse(permissionDecision·additionalContext·updatedInput), PostToolUse(additionalContext), UserPromptSubmit(additionalContext). "PostToolUse 전용" 은 내 오류. PostToolUseFailure 의 additionalContext 는 레퍼런스 표에 없음 → **미확인**(아스트라 주장도 미확인 처리) |
| **A6 updatedToolOutput** | 미확인으로 하향 | [문서-sdk] "any tool in both SDKs" 는 Agent SDK 페이지. [문서-ref] hooks.md Decision control 표에는 updatedToolOutput 없음. [설치판] 문자열 14건. 결론: CLI 2.1.281 에서 command 훅이 출력을 교체할 수 있는지는 **문서 간 불일치, 실측 필요**. PostToolUseFailure 확대 해석 금지 동의. [문서-guide] PostToolUseFailure 이벤트 존재는 확인 |
| A7 채택 상향 | 동의 | "활성 index 보호" 와 "무부작용" 분리. Pi 외 저장소·ignored 의존성·생성물 포함 |
| A8 해결 표현 거부 | 동의 | worktree 는 경합 완화일 뿐 격리가 아님. 격리 수단은 미확정으로 표기 |
| A9 승인 의미 | 동의 | 치환 명령의 권한 통과 ≠ 원 작업 승인. 원 명령 정체성·캐시 생성 주체·입력 일치를 같이 검증 |
| A10 자동 승격 기준 거부 | 동의 | N=3·단일 확인 이벤트 철회. 성공 재실행 + 독립 평가 + 폐기 조건 |
| A11 해결 정의 | 동의 | 목표 검사 성공 확인, 포기·관측 종료 별도 집계 |
| A12 revision | 동의 | HEAD + 작업트리 파일 sha256 을 귀속. 이 세션 판정 시 라우터 디렉터리는 미커밋 변경 0 이었음(git status) |
| M1 | 동의 | 보안 게이트는 중립 반환이 아니라 별도 고장 정책. Codex 측 실제 실행 여부는 미확인 |
| M2 단일 원인 결론 보류 | 부분 반박 | [실측] 이 세션에서 `biome check .` 를 읽기 전용 재실행: `.omo/codegraph/.../daemon.sock internalError`, `source.json format`, "Found 1 error" — 현재 실패 원인은 `.codegraph` 단일. "상습" 은 git log(e448b57·f92c4f7 메시지, 이 세션 커밋 3건 `--no-verify`)에 근거. 수정 후 전체 게이트 재검증 요구에는 동의 |
| M3 자동 전파 정정 | 동의 | "git 추적 → 다음 커밋에 포함 → pull 시 전파" 로 정정. 자동 push 아님 |
| M4 | 동의 | A4 정정 적용. 전체 지연과 내부 RPC 예산 분리 측정 |
| M5 보류 | 동의 | A6 미확인이 선행. 원문 접근·보존·해시·재조회 설계 없이는 제안 단계 |
| M6 경계 확대 | 동의 | cwd·파일명·stderr·보관 경로 포함. 하네스 기저장 원문은 소급 불가 |
| §5 추가 관점 6건 | 동의 | 훅 조합(deny>defer>ask>allow 는 [문서-guide] 529 확인, updatedInput 병합은 미확인), 로컬 신뢰 경계, 시간차 무효화, 과부하·자식 프로세스 회수, 로그 내용은 비신뢰 데이터(additionalContext 를 정책으로 승격 금지), 자동 비활성 조건·복귀 절차 |

정정 요약: 내 판정표에서 틀린 것 2곳(A4 타임아웃, A5 "PostToolUse 전용"), 하향 1곳(A6 → 미확인), 반박 1곳(M2 원인은 실측으로 단일 확인). 나머지 동의.
