# AB_EVAL_ztc — ZTC 라우터 구현체 A/B 평가표 (초안)

- Status: **v0.2 (2026-09-25) — §6 U1–U9 유저 결정 반영(전부 추천안).** 실제 A/B 는 Phase 2(라우터가 advisory `additionalContext` 를 주입할 수 있는 단계) 이후에 시작한다(유저 결정). v0.1 초안 → v0.2 변경은 §6 결정표만(판정 규칙 본문은 U8·U9 반영 문장 추가).
- 작성: Claude Code (Opus 5.5) 서브에이전트 @ richardkim-macpro-macbookpro. 이 문서는 사전 등록(pre-registration)용이다. 측정 시작 후 판정 규칙·가중치를 바꾸면 버전을 올리고 사유를 적는다(`EVAL_PROTOCOL_ztc.md:3` 과 같은 규칙).
- 상위: `docs/PLAN_ZTC_topology_optimization.md` v0.3 §2.2·§5.4·§6, `docs/harness/EVAL_PROTOCOL_ztc.md`, `docs/harness/HOOK_CONTRACT_ztc.md`. 비교 방식 선례: `docs/evidence/ztc-phase1-merge-20260924/comparison.md`.

## 0. 쉬운 말로
같은 요리 주문서를 똑같은 두 주방에 동시에 넣는다. 한 주방(A)에는 접수원(라우터)이 쪽지로 조언을 건네고, 다른 주방(B)에는 접수원이 없다. 요리가 끝나면 맛(결과), 든 재료비(토큰), 걸린 시간, 사고 여부(안전)를 같은 채점표로 적는다. 다만 요리사(LLM)는 같은 주문서로도 매번 조금씩 다르게 요리하므로 **한 번 비교는 일화**다. 여러 번 짝지어 비교해야 "효과"라고 말할 수 있다.

## 1. 목적과 가설
- **"효과"의 정의:** 같은 지시문으로 시작해 루프 종결까지 간 한 루프에서, 구현체 적용(A)이 미적용(B)보다 **결과를 나쁘게 하지 않으면서(비열등)** 총비용·반복 실패·유저 개입을 줄이는 것. 속도만 빨라지고 결과가 나빠지면 효과가 아니다.
- **1차 가설 (사전 명시, 실행 전 고정):** H1 — A 의 루프당 총비용(토큰 4종 가중, K7 정의 `PLAN_ZTC_topology_optimization.md:71`)이 B 보다 **15% 이상 낮고**(K7 목표 −15%, 같은 줄), 결과 범주(완료·요구사항·게이트·유저 수용)는 B 대비 열등하지 않으며, 안전 항목 위반 0건.
- **2차 가설 (탐색적):** H2 같은 에러 반복 수 A < B, H3 유저 개입 수 A ≤ B, H4 벽시계 시간 A ≤ B. 2차 가설은 판정에 쓰지 않고 방향성만 보고한다.
- **Phase 2 이전에는 효과를 잴 수 없다.** Phase 1 은 shadow 전용이라 훅 stdout 이 항상 정확히 `{}` 다(`HOOK_CONTRACT_ztc.md:78-79`). 에이전트에 전달되는 정보가 0 이므로 행동 차이는 구조상 0 이고, A/B 로 측정 가능한 것은 **오버헤드**(Bash 호출당 전체 지연 약 27–31 ms, `comparison.md:12-15`)와 **안전 불변식 유지**뿐이다. Phase 1 에서 A/B 를 돌리면 결과 차이는 전부 LLM 비결정성 잡음이다 — 이 점 때문에 Phase 1 실행은 아래 §4 의 A/A 보정 용도로만 가치가 있다.

## 2. 실험 설계 조건
### 2.1 동일 조건 체크리스트 (양 arm 시작 직전 확인, 증거 폴더 `conditions.md` 에 기록)
| # | 조건 | 확인 방법 | A | B |
|---|---|---|---|---|
| C1 | 같은 분기 커밋 | 각 worktree 에서 `git rev-parse HEAD` 가 같은 값 | | |
| C2 | 같은 모델·effort | 세션 시작 배너 + transcript 첫 assistant 메시지의 `model` 필드 | | |
| C3 | 지시문 바이트 동일 | 지시문 파일 1개를 두 창에 붙이고 `shasum -a 256` 값 기록(창에 치기 전 파일 해시) | | |
| C4 | 시작 시각 차 ≤ 60 s | transcript 첫 user 메시지 `timestamp` 차이 | | |
| C5 | 권한 모드 동일 | 시작 명령의 permission mode 플래그, `.claude/settings.local.json` 해시 | | |
| C6 | MCP 세트 동일 | 세션 안 `/mcp` 목록 캡처(서버 이름만) | | |
| C7 | 네트워크 동일 | 같은 Mac, 같은 회선. VPN·Tailscale 상태 기록 | | |
| C8 | Claude Code 버전 동일 | `claude --version` (한 바이너리이므로 자동 동일) | | |
| C9 | 부트스트랩 동일 | 양 arm 모두 같은 방식으로 `CLAUDE.md` 부트스트랩을 수행하거나 생략(§6 미결 U3) | | |
| C10 | Tier-2 게이트 동일 | 양 worktree 의 `.claude/settings.json:111-122` Tier-2 항목이 같은지 diff | | |

### 2.2 격리 규칙
- **worktree·브랜치:** `~/Pi-wt/ab-<date>-<slug>-A`, `…-B`, 브랜치 `ab/<date>-<slug>-{A,B}`, 같은 커밋에서 분기. **push 금지**(원격 없음, 지시문에 명시). 훅 명령은 `$CLAUDE_PROJECT_DIR` 기준이므로(`.claude/settings.json:116,127`) 각 arm 은 자기 worktree 의 스크립트를 쓴다.
- **질의 게이트 차단:** 두 worktree 루트에 미추적 파일 `.pi-ab-arm`(내용 `A`/`B`)을 두거나 `PI_AB_ARM` 을 지정해 A/B 질의 게이트(`scripts/hooks/ab-prompt-gate.sh`, UserPromptSubmit)가 arm 세션 안에서는 묻지 않게 한다. 게이트의 질의·답은 `$PI_ROUTER_HOME/telemetry/ab_gate.jsonl` 에 gate_id 로 남으며(지시문 원문은 저장 안 함), `apply` 로 답한 gate_id 가 A/B 후보 목록이다. 게이트는 2026-09-25 부터 Claude Code·Codex 전역 등록이며 작업 루프 지시문에만 묻는다(유저가 `ZTC 평가 중지`로 멈춤, DECISION_20260925 §3).
- **라우터 원자료 분리:** A 는 `PI_ROUTER_HOME=~/.pi-router-ab/<date>-<slug>-A`, `PI_ROUTER_PORT=<main 9876 과 다른 포트>` 로 전용 데몬 1개. 두 값은 환경변수로 받는다(`engines/hybrid_router/ztc/paths.py:19,24`). B 도 빈 전용 `PI_ROUTER_HOME` 을 지정해 두고, 종료 후 **비어 있어야 정상**(비어 있지 않으면 오염 기록). main 의 상시 shadow 데몬(9876)은 어느 arm 도 쓰지 않는다.
- **Tier-2 로그:** 게이트 로그는 worktree 별 `learning/remote-approvals/tier2-gate-log.jsonl` 에 쌓인다(`scripts/tier2-gate-hook.py:54-56`, REPO = 스크립트 위치 기준). arm 간 섞이지 않는다.
- **대상 적격성:** 루프가 원격 노드(SSH·TeamViewer 착탄), NV 저장소, launchd·LaunchAgent, 공유 외부 서비스(Discord 봇·GitHub PR·원격 API 쓰기)를 건드리면 **부적격**. 두 arm 이 같은 외부 상태를 바꾸면 서로 오염되고 되돌릴 수 없다. 적격 = Pi 저장소 안에서 로컬 파일·로컬 테스트로 끝나는 루프.
- **공유 로컬 자원:** `~/.claude/` 메모리·전역 설정은 두 arm 이 공유한다. 루프가 메모리 파일을 쓰면 다른 arm 에 새어 들어갈 수 있으므로, 지시문에 "메모리 쓰기 금지"를 넣거나 부적격 처리(§6 U4).

### 2.3 B 에서 구현체를 끄는 방법
- B worktree 의 `.claude/settings.json` 에서 router-client 항목 3개(PreToolUse `:127`, PostToolUse `:140`, PostToolUseFailure `:153`)를 **미커밋 수정으로 삭제**한 뒤 세션을 시작한다. 이것이 `HOOK_CONTRACT_ztc.md:120` 의 공식 원복 절차와 같다. Tier-2 항목은 그대로 둔다(안전 게이트는 구현체가 아님).
- 대안 비교: `router-client.sh` 실행 비트 제거는 파일 존재 가드(`[ -x … ] || printf '{}'`)의 셸 기동이 남아 "완전 미적용"이 아니다. 데몬만 끄는 방법은 클라이언트가 여전히 약 26 ms 를 쓰므로(`comparison.md:16`) 부적합. `disableAllHooks` 는 Tier-2 까지 꺼지므로 금지.
- 확인: B transcript 에 router-client 명령의 `hook_success` attachment 가 0건(`HOOK_CONTRACT_ztc.md:38`), B 의 `PI_ROUTER_HOME` 이 비어 있음.

### 2.4 두 arm 동시 실행의 경합과 기록
- **CPU·메모리:** 같은 Mac 에서 두 세션 + A 데몬이 돈다. 시작·종료 시 `uptime`(load average)과 `vm_stat` 한 줄을 `conditions.md` 에 남긴다. 루프가 테스트·빌드를 돌리면 동시 실행이 벽시계 시간을 서로 늘린다 → 벽시계 지표는 **경합 보정 없음**을 명기.
- **API 한도:** 같은 계정이므로 요청 한도·과부하 오류를 나눠 쓴다. transcript 의 API 오류(429·overloaded·retry) 건수를 arm 별로 센다. 한쪽에만 3건 이상이면 그 쌍의 효율 지표에 "경합 오염" 표시.
- **프롬프트 캐시 교차:** 같은 계정·같은 시스템 프리픽스는 캐시가 공유될 수 있다. 먼저 시작한 arm 이 cache_creation 을, 나중 arm 이 cache_read 를 가져갈 수 있으므로 C4(시작 차 ≤ 60 s)를 지키고, **토큰 4종을 분리 보고**하며 총비용은 4종 가중합으로 비교한다.
- **순서 효과:** 여러 쌍을 돌릴 때 어느 창을 먼저 시작하는지 쌍마다 번갈아(동전 던지기 결과 기록) 배정한다.

### 2.5 텔레메트리 arm 태깅
- `hook_events.jsonl` 레코드 키: ts, client_version, request_id, outcome, event, tool, program, exit_code, response_keys, rpc_ms, client_ms, **session·arm**(U5, `ztc-phase2-0.1` 부터 — 2026-10-04 `PHASE2_READINESS_ztc.md` D6. `ztc-phase1-0.1` 레코드에는 없다). **arm 태깅의 1차 근거는 그대로 전용 `PI_ROUTER_HOME` 경로**이고(집계 시 경로 이름 `…-A` 가 arm 라벨), `arm` 필드는 교차 확인용이다.
- 보조 교차 확인: `ts` 가 A 세션의 첫·마지막 메시지 시각 안에 있는지, `client_version` 이 실험 당시 값인지(정본 `ztc-phase2-0.1`, `scripts/hooks/router_client.py:42` — live 는 전환 전까지 `ztc-phase1-0.1`), `arm` 필드가 경로 라벨과 같은지.
- `router_events.jsonl`(ts, kind, request_id, event, program, exit_code, source, error_class, signature, queued, handle_ms)은 `request_id` 로 hook_events 와 이어 붙인다. 명령 원문은 어디에도 복사하지 않는다.

## 3. 평가표
가중치는 범주 합 100(안전은 가중치 대신 **거부권**). 값이 없으면 빈칸이 아니라 `null` + 사유(`EVAL_PROTOCOL_ztc.md:98`). 추정치는 `_estimate` 표기, 합계에 섞지 않음(`:97`).

### 3.1 결과 (35)
| ID | 항목 | 정의 | 측정 방법/출처 | 단위 | 우세 규칙 | 가중 | A | B |
|---|---|---|---|---|---|---|---|---|
| R1 | 완료 여부 | 유저가 루프 종결을 선언했고, 종결 시점에 지시문의 산출물이 worktree 에 존재 | 유저 종결 선언 시각 + `git -C <wt> log`/`status` | 예/아니오 | 예 > 아니오 | 10 | | |
| R2 | 요구사항 충족 | 지시문에서 사전 추출한 요구사항 체크리스트(실행 전 고정) 중 충족 항목 비율 | 평가자가 diff·산출물 대조, 항목별 근거 file:line | % | 높을수록 | 12 | | |
| R3 | 테스트/게이트 통과 | 종결 시점에 지시문이 요구한 테스트·린트 명령 전부 exit 0 | 평가자가 각 worktree 에서 같은 명령 재실행(예: `python3 -m unittest discover -s engines/hybrid_router/tests -p 'test_*.py'`) | 통과/전체 | 높을수록 | 8 | | |
| R4 | 유저 수용 | 유저가 결과를 main 에 받을지 판정(블라인드: 평가자가 arm 라벨을 X/Y 로 가려 제시) | 유저 판정 기록 | 수용/조건부/거부 | 수용 > 조건부 > 거부 | 5 | | |

### 3.2 효율 (30)
| ID | 항목 | 정의 | 측정 방법/출처 | 단위 | 우세 규칙 | 가중 | A | B |
|---|---|---|---|---|---|---|---|---|
| E1 | 토큰 4종 | input / cache_creation_input / cache_read_input / output 합계를 **따로** | transcript `~/.claude/projects/<slug>/<session>.jsonl` 각 assistant 메시지 `usage` 합산. 서브에이전트 transcript 포함. 같은 `message.id` 중복 행은 1회만 | tokens ×4 | 보고용(판정은 E2) | 0 | | |
| E2 | 추정 비용 | E1 4종 × 실험 당일 공식 단가(모델별). 단가·출처 URL 을 증거에 기록. **1차 지표** | 집계 스크립트(K7 스크립트는 Phase 2.5 산출물, `PLAN:173` — 아직 없음) | USD_estimate | 낮을수록 | 10 | | |
| E3 | 벽시계 시간 | 첫 user 메시지 ts → 유저 종결 선언 ts. 유저 대기 시간은 따로(E3b) | transcript `timestamp` | 분 | 낮을수록 | 5 | | |
| E4 | 도구 호출 수 | `tool_use` 블록 수(도구별 분해) | transcript | 건 | 낮을수록 | 3 | | |
| E5 | 실패 도구 호출 수 | `tool_result.is_error = true` 건수(Bash 는 exit≠0 포함) | transcript (양 arm 대칭 출처). A 는 `hook_events` 의 PostToolUseFailure 건수와 대조 | 건 | 낮을수록 | 4 | | |
| E6 | 같은 에러 반복 수 | 같은 정규화 시그니처가 2회째 이후 나온 횟수 | 양 arm 실패 본문에 **사후** `ztc.l0.signature()`(`engines/hybrid_router/ztc/l0.py:84`)를 같은 규칙판으로 적용. A 의 실시간 원장은 쓰지 않음(대칭성) | 건 | 낮을수록 | 5 | | |
| E7 | 유저 개입 수 | 종결 전 유저의 redirect·clarify·approve·reject·pause 메시지 수(지시문 제외) | transcript user 메시지 수동 분류, `ai_guidelines.md:59` 분류 체계 | 건 | 낮을수록 | 3 | | |

### 3.3 구현체 고유 (15, A 만 측정 — B 는 N/A 가 정상)
| ID | 항목 | 정의 | 측정 방법/출처 | 단위 | 우세 규칙 | 가중 | A | B |
|---|---|---|---|---|---|---|---|---|
| Z1 | K1 훅 지연 | 전체(`client_ms`)·내부 RPC(`rpc_ms`) 각각 p50/p95/p99 | A `PI_ROUTER_HOME/telemetry/hook_events.jsonl`, `ztc.telemetry.percentile()`. 전체 지연 교차: transcript `hook_success.durationMs` | ms | 내부 RPC p99 ≤ 30 ms 충족(`PLAN:65`) | 3 | | N/A |
| Z2 | 타임아웃률 | 내부 예산 30 ms 초과 비율(`router_client.py:43`) | hook_events `outcome` | % | < 1% | 2 | | N/A |
| Z3 | 중립 반환률 | `{}` 반환 비율. Phase 2 에서는 주입이 아닌 호출의 비율 | transcript `hook_success.stdout` | % | 보고용 | 1 | | N/A |
| Z4 | 주입 건수 | `additionalContext` 를 실제로 낸 호출 수 | transcript `hook_success.stdout` 에 `additionalContext` 키가 있는 attachment 수(`HOOK_CONTRACT:38`) | 건 | 보고용 | 1 | | N/A |
| Z5 | K4 5분류 | 주입마다 채택/해결/재발/포기/회귀 중 하나. 해결 = 같은 목표 검사가 이후 exit 0(`EVAL:68-71`). 관측 종료는 별칸 | 평가자가 주입 직후 도구열을 읽고 분류 | 건×5 | 오처방률(재발+회귀+포기)/주입 ≤ 10%(`PLAN:68`) | 6 | | N/A |
| Z6 | 자동 비활성 발생 | `disabled` 표지 생성·복귀 횟수(`HOOK_CONTRACT:116-117`) | hook_events `outcome=disabled`, `auto_disabled` | 건 | 0 이 우세 | 2 | | N/A |

### 3.4 안전 (거부권 — 하나라도 A 쪽 위반이면 판정 "채택 불가")
| ID | 항목 | 정의 | 측정 방법/출처 | 단위 | 규칙 | A | B |
|---|---|---|---|---|---|---|---|
| S1 | Tier-2 흐름 불변 | Tier-2 게이트가 양 arm 에서 같은 명령에 같은 판정(ask/deny/통과)을 냈고, 라우터가 `permissionDecision` 을 한 번도 내지 않음(`PLAN:133`, `HOOK_CONTRACT:79`) | worktree 별 `tier2-gate-log.jsonl` + transcript `hook_success.stdout` 에 `permissionDecision` 0건 | 위반 건 | 0 | | |
| S2 | 비밀값 원자료 잔존 | A `PI_ROUTER_HOME` 원자료에 마스킹 안 된 비밀 패턴 | `ztc.masking.contains_unmasked_secret()`(`masking.py:81`)로 전 레코드 검사, 결과 건수만 기록 | 건 | 0 | | |
| S3 | 오처방으로 인한 우회 | 주입 문구를 따른 결과 테스트 삭제·skip·`--no-verify`·게이트 비활성·권한 확대가 생김. 주입 내용은 비신뢰 데이터(`HOOK_CONTRACT:86`) | 주입 뒤 도구열·diff 검토 | 건 | 0 | | |
| S4 | 격리 위반 | push·원격 노드 접촉·NV 저장소 쓰기·공유 메모리 쓰기·B 의 `PI_ROUTER_HOME` 비어 있지 않음 | transcript 도구열, `git -C <wt> reflog`, 디렉터리 확인 | 건 | 0 (위반 시 그 쌍 무효) | | |

### 3.5 품질 (20)
| ID | 항목 | 정의 | 측정 방법/출처 | 단위 | 우세 규칙 | 가중 | A | B |
|---|---|---|---|---|---|---|---|---|
| Q1 | diff 리뷰 결함 수 | 분기 커밋 대비 최종 diff 를 **arm 라벨을 가린** 독립 리뷰어(별도 세션)가 검토, 심각도 상/중/하 | `git -C <wt> diff <base>..HEAD` + 미커밋분, 리뷰 원문을 증거 폴더에 | 건(상×3+중×2+하×1) | 낮을수록 | 12 | | |
| Q2 | 되돌림 수 | 루프 안에서 자기 변경을 되돌린 횟수(revert·같은 hunk 재작성·`git checkout -- <file>`) | transcript 도구열 + `git reflog` | 건 | 낮을수록 | 8 | | |

## 4. 판정 규칙 (사전 등록)
1. **무효 쌍:** S4 위반, C1–C10 불일치, 한 arm 만 경합 오염(§2.4) → 그 쌍은 집계에서 뺀다(사유 기록, 다시 돌림).
2. **거부권:** S1–S3 중 A 위반이 1건이라도 있으면 쌍 수와 무관하게 "채택 불가". B 위반은 기록만.
3. **쌍 판정(쌍마다):** ① 결과 비열등 = R1 에서 A 가 B 보다 나쁘지 않고, R2 차이(A−B) ≥ −10%p, R3 에서 A 가 B 보다 나쁘지 않음. ② 1차 지표 = E2 비율 A/B. ③ 쌍 결과 = "A 우세"(① 충족 + E2 비율 ≤ 0.85), "B 우세"(① 불충족 또는 E2 비율 ≥ 1.15), 그 외 "무승부".
4. **가중 점수(보조):** 항목별 우세 arm 에 가중치를 주고 동률은 반분. 판정 근거로 쓰지 않고 요약용으로만 보고.
5. **정직한 통계:**
   - LLM 은 같은 지시문·같은 모델에서도 도구 순서·토큰이 달라진다. **한 쌍(n=1)은 일화**이며 "효과 입증"을 말할 수 없다.
   - 쌍별 부호 검정 기준: 무승부를 뺀 쌍이 전부 한 방향이어도 5쌍이면 양측 p = 0.0625, **6쌍 이상이 모두 같은 방향**이어야 p < 0.05. 연속 지표(E2 비율)는 쌍별 로그비의 Wilcoxon 부호순위 검정 + 부트스트랩 95% CI 를 함께 보고(6쌍 전부 같은 방향이면 양측 p ≈ 0.031).
   - 따라서 어떤 주장이든 **최소 6쌍, 권장 8–10쌍**. 한 과제 반복보다 **서로 다른 적격 루프 여러 개**에 쌍을 배치(paired design, 과제가 블록)해야 일반화 가능. 같은 과제 반복은 과제 내 잡음 추정용.
   - **A/A 보정:** 본 실험 전 또는 Phase 1 기간에 두 arm 모두 구현체 미적용으로 2–3쌍을 돌려, 같은 조건에서 E2·E3·E5 가 얼마나 흔들리는지(쌍별 비율 범위)를 잰다. A/B 에서 관측한 차이가 A/A 범위 안이면 "잡음과 구별 불가"로 보고한다. Phase 1 shadow 로 돌린 A/B 는 사실상 A/A + 오버헤드 측정이다(§1).
   - 보고 문구: n < 6 이면 **"방향성 관찰 (n=k, 통계적 주장 없음)"**, n ≥ 6 이고 검정 통과 시에만 "효과 관측 (n=k, p=…, CI …)". "효과 입증"은 쓰지 않는다. 여러 2차 지표를 동시에 보면 우연히 하나는 좋게 나오므로 2차 가설은 판정에 쓰지 않는다.
6. **최종 판정 문구 후보:** "채택 지지" (거부권 0 + 검정 통과 + A 우세), "해 없음/방향성 A" , "해 없음/방향성 B", "채택 불가"(거부권 또는 B 우세 유의).

## 5. 기록 절차 (유저가 두 arm 종결을 선언한 뒤)
1. **정지 확인:** 두 창 모두 추가 입력 없이 멈춰 있음을 확인하고, 유저 종결 선언 시각을 arm 별로 기록. A 데몬을 멈추고 종료 확인(`EVAL_PROTOCOL_ztc.md:27` ①).
2. **증거 폴더:** `docs/evidence/ab-<YYYYMMDD>-<slug>/` 생성. `conditions.md`(§2.1 표·경합 기록), `directive.sha256`, `table.md`(본 §3 표 채움), `stats.json`, `review_X.md`/`review_Y.md`(블라인드 리뷰 원문), `arm_key.md`(X/Y↔A/B 대응, 리뷰 후 공개). 원자료·명령 원문·transcript 사본은 넣지 않는다(`EVAL_PROTOCOL_ztc.md:11`).
3. **transcript 식별:** 각 worktree 경로의 slug 로 `~/.claude/projects/<slug>/` 에서 세션 파일과 서브에이전트 파일을 찾는다. 세션 ID·파일 sha256 만 증거에 기록.
4. **텔레메트리 필터:** A 는 `~/.pi-router-ab/<date>-<slug>-A/telemetry/*.jsonl` 전체, ts 가 A 세션 시간창 안인 행만. B 는 전용 폴더가 비어 있는지 확인(S4).
5. **계산:** 집계 스크립트(스크래치 폴더에서 실행, 저장소에 넣으려면 별도 승인)로 E1–E7, Z1–Z6 을 산출. 같은 스크립트를 두 arm 에 그대로 적용한다. 결과는 숫자만 `stats.json` 에.
6. **평가자 수동 항목:** R2 체크리스트 대조, R3 재실행, Z5 분류, S1–S3 검토, Q2 계수. 각 판정에 근거(transcript 메시지 uuid 또는 file:line).
7. **블라인드 리뷰:** Q1 은 arm 라벨을 X/Y 로 바꾼 diff 두 개를 새 세션 리뷰어에게 준다. R4 유저 수용도 같은 X/Y 로 묻는다.
8. **표 채우기·판정:** §3 A/B 칸을 채우고 §4 규칙 1→6 순서로 적용. 누적 쌍 표(쌍 번호·과제·쌍 결과·E2 비율)를 갱신하고 n 에 맞는 보고 문구를 고른다.
9. **보고:** council entry `docs/turn-reports/<date>_claude-code_ab-<slug>.md` 에 요약, 오케스트레이터면 UTR 갱신(`CLAUDE.md` 종료 규칙). worktree·브랜치는 유저 결정 전 지우지 않는다.

## 6. 유저 결정 (2026-09-25, 전부 추천안 채택 — `learning/user-prompts/2026-09-25_Fri/07_ab-eval-u1-u9-deck-skill.md`)
| # | 결정 | 확정 내용 |
|---|---|---|
| U1 | 1차 지표 | **E2(추정 비용)** 유지. 이 계정은 구독 결제(`~/.claude.json` billingType)라 E2 는 실지출이 아니라 API 환산 비교값이다 — 사용 한도 소모의 대리 지표로 쓴다 |
| U2 | 쌍 수·예산 | **단계 승인.** 지금(Phase 1) A/A 2쌍 = 루프 4개만 승인. 본실험 6쌍은 Phase 2 뒤 A/A 결과를 보고 다시 승인. 참고 규모: 중간 세션 1개 ≈ cache read 8–13M · cache 생성 0.3–0.4M · output 0.1–0.2M 토큰(09-23~25 Pi 세션 실측). `config/agent_limits.json` 의 일 $2 한도는 API 과금 기준이라 적용 대상 아님 |
| U3 | 부트스트랩 | 양 arm 모두 `session-recover.ps1` 을 **`-Pull` 없이** 읽기 전용으로 실행, 핸드오프 `-Consume`·push 금지(지시문에 명시). C9 는 이 방식으로 확인 |
| U4 | 공유 메모리 | 지시문에 `~/.claude/projects/.../memory/` **쓰기 금지** 명시, 쓰면 그 쌍 무효(S4) |
| U5 | 텔레메트리 필드 | Phase 2 클라이언트에 `arm`(`PI_AB_ARM` 값)·`session_id` 해시 필드 추가. 경로 태깅(§2.5)은 교차 확인용으로 유지 |
| U6 | 적격 루프 | **혼합 6블록:** `C:\Pi` 하드코딩 PS 스크립트 이식화 3 + `engines/hybrid_router` 테스트 보강 3. 블록별 지시문·R2 체크리스트는 착수 전에 파일로 고정하고 해시 기록(C3) |
| U7 | 데몬·포트 | A 전용 데몬 **포트 9877**(2026-09-25 LISTEN 없음 확인), 승인 게이트 거쳐 수동 기동, LaunchAgent 미사용 |
| U8 | 블라인드 | Q1 **블라인드 필수**. R4 는 유저가 arm 을 알고 있으면 **가중 0(보고용)** 으로 내린다(가중 점수는 §4-4 대로 요약용이라 판정에 영향 없음) |
| U9 | 비열등 마진 | R2 −10%p·E2 ±15% 는 **잠정**. A/A 보정에서 쌍별 E2 비율이 ±15% 밖으로 흔들리면, 본실험 전에 E2 문턱을 A/A 관측 최대 편차로 올리고 버전을 올린다(사전 등록 규칙, 본실험 시작 후에는 바꾸지 않음) |
