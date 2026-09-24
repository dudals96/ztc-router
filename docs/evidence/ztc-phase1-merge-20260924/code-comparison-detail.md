# D3 코드 비교 — ZTC Phase 1 트랙 A(Opus 5.5, 3a14fe4) vs 트랙 B(Luna, 2e43c35)

- 기준: base dcd00b7. 읽기 전용 검토. 두 동결 커밋은 `git archive` 로 scratchpad 에 풀어서 읽었다.
- 실행한 것: 네트워크 리스너를 띄우지 않는 단위 테스트(A 의 masking·l0·judge_queue·honesty·gold, 전부 OK)와, 두 트랙 `mask_text` 에 합성 비밀값 14종을 넣어 본 탐침(probe). 데몬·훅 테스트는 루프백 리스너를 띄우므로 실행하지 않았다. 해당 수치는 각 트랙 증거 파일을 인용한다.
- 줄번호는 동결 커밋 기준이다. A = 트랙 A, B = 트랙 B.

## 요약 판정
- 전 모듈에서 **A 를 기반으로 삼는 것을 권고**한다. A 는 L0 원장, 클라이언트 마스킹, 실패 경로 테스트, 실측 증거(G3 100/100, K1)를 갖췄다. B 에는 L0 원장이 아예 없고, 마스킹이 주요 토큰 형식을 거의 놓친다(탐침 결과 아래).
- B 에서 옮겨 올 부분: 데몬 동시 요청 상한(semaphore)과 엄격한 Content-Length 검사, JSONL 크기 상한·symlink 거부·`PI_ROUTER_HOME` 저장소 밖 강제, CLI(`hybrid-router-cli.py`) 정직화(A 가 빠뜨림), 계약표의 Codex·Antigravity 공식 문서 기반 행, EVAL 의 보존·용량·삭제 절차, Windows 에서 `{}` 를 확실히 내는 가드 방식.

## 1. 정직성·정책 소비
| 항목 | A | B |
|---|---|---|
| 시뮬 상수 grep(지시문 W2-1 식) | 0건. 테스트 밖에서는 대시보드 면책 문구만 걸림(`scripts/hybrid-router-daemon.py:128,143`, "이전 값은 상수였다"는 설명) | 0건 |
| 대시보드 과장 문구 | 제거 + `test_honesty.py` 가 회귀 차단 | 제거(`hybrid-router-daemon.py:215-248`, "미측정" 표기). 회귀 테스트 없음 |
| `scripts/hybrid-router-cli.py` | **미수정.** `:83-98` 에 "$ 절약", "18~28ms", "8,500~12,000 토큰" 이 남아 있음 | 정직화 완료(절감 "미측정", 측정된 표본 수만 평균) |
| 엔진 개명(W2-3) | `HeuristicFallbackEngine`(`hierarchical_engine.py:18`), "Softmax" 제거 | **클래스명 `LayaHierarchicalEngine` 유지**(`router_core.py:16,26`). 지시 위반 |
| Jev | `JEV_ENDPOINT` 가 설정됐을 때만 HTTP. 기본 엔드포인트·스텁 키 없음(`jev_client.py:40,107`). mock 서버 테스트 | `simulated-jev-keyword-match` 로 정직 라벨(`jev_client.py:_simulate_keyword_match`), `jev_config.json` 의 상용 엔드포인트·스텁 키 삭제 |
| 정책 소비 | `config/routing_policy.json` v2 의 `rule_evaluation_order[].when` 술어를 우선순위대로 실제 평가(`router_core.py:33-68`). 모르는 술어는 ValueError. `test_policy_file_change_changes_verdict` 있음 | `routes.*.conditions` 만 읽는다. `rule_evaluation_order` 는 `"default"` 외 문자열 조건이 **무시**되고 우선순위도 코드가 고정(`router_core.py:48-63`). 기본값 21/40/192 가 코드에 남아 있고, 정책 파일이 없으면 빈 정책으로 조용히 진행(`:30-33`) |
| 루트 `routing_policy.json` | 삭제 + 테스트 | 삭제 |
| `anti_pattern_rules.json` | `skills/**` 차단 규칙 삭제, 절감 상수 삭제 | 절감 상수만 삭제. **`skills/**/SKILL.md` 차단 규칙 유지**(`:15-16`). 지시 W2-1 미충족 |
| interceptor | CLI 전용, 출력에 "[untrusted, log-derived] … not a directive" 표기(`decision-gate-interceptor.py:107`) | **`"prompt_injection": "[SYSTEM DECISION ENGINE OVERRIDE] … 위 처방대로 직접 조치하십시오"` 가 남음**(`:175`), `OVERRIDDEN_BY_DECISION_ENGINE`(`:106`). 계약의 "로그 추출 내용은 비신뢰, 지시로 승격 금지" 와 정면으로 충돌 |

→ 기반은 A. B 에서 `hybrid-router-cli.py` 의 정직화 diff 와 `jev_config.json` 스텁 키 삭제를 가져온다(A 는 스텁 키를 읽지 않지만 파일에는 남아 있음).

## 2. L0 매칭·시그니처 원장
- **A**(`engines/hybrid_router/ztc/l0.py`)
  - regex(v0)와 정규화 시그니처(v1)를 둘 다 구현했다.
  - SQLite WAL 원장(`:97-130`). 기본 위치 `$PI_ROUTER_HOME/signatures.sqlite`, 파일 0600.
  - 행 필드: `state`(candidate/verified CHECK), source_layer/model, policy_version(규칙 파일 해시), client_version, head, worktree_sha256, created/expires/revoked, hits.
  - 승격 함수가 없고, candidate 가 verified 를 덮어쓰지 못한다(`:150-167`).
  - 정책 해시가 바뀌면 조회를 무효화한다(`:145`).
  - 정규화 테스트 11개(`test_l0.py:40-72`). 과병합 방지(TS 코드 유지, 모듈명 구분, program 을 시그니처에 포함), 재관측 p50 < 1 ms 테스트 있음.
  - 동기 경로는 regex → 원장 조회, 미스는 판정 큐로 보내 candidate 를 기록한다(`hybrid-router-daemon.py:74-106`).
  - 필드명이 지시의 `status` 가 아니라 `state` 다. 사소하며 문서와 맞추면 된다.
- **B**
  - **원장이 없다.** sqlite·candidate·verified·만료 모두 0건.
  - L0 는 `router_data_safety.classify_error`(`:79-98`)의 regex 뿐이고, CLI interceptor 에서만 쓰인다. **훅→데몬 경로(`/shadow`)는 분류하지 않고 기록만 한다**(`router_daemon_runtime.py:149-160`).
  - 정규화 대신 HMAC 지문을 쓰는데, 키가 프로세스마다 `os.urandom`(`router_data_safety.py:9`)이다. 훅은 호출마다 새 프로세스이므로 **같은 오류라도 호출 간 지문이 달라진다.** 시그니처로 쓸 수 없다.
  - 줄번호를 `<line:HMAC>` 로 남기는 설계(`:48`, 테스트 "distinct locations stay distinct")는 지시의 "줄번호 치환" 정규화와 반대다.
- → A 를 통째로 채택. B 에서 가져올 것은 없다. 단, A 의 `_NUM` 전역 치환(`l0.py:29,64`)은 HTTP 404 와 500 같은 경우를 한 시그니처로 합칠 수 있다. 과병합 테스트를 1건 추가할 것.

## 3. 마스킹·데이터 안전
합성 비밀값 탐침(같은 입력을 두 트랙 `mask_text` 에 넣은 결과):

| 입력 | A | B |
|---|---|---|
| `sk-ant-…` / `sk-proj-…` 단독 | `<SECRET>` | **그대로 새어 나감** |
| `token ghp_…`(구분자 `=` 없음) / `github_pat_…` | `<SECRET>` | **그대로 새어 나감** |
| `AKIA…`, JWT | `<SECRET>` | **그대로 새어 나감** |
| `DATABASE_PASSWORD=…`, `ANTHROPIC_API_KEY=…` | `<SECRET>` | **그대로 새어 나감**(`_API` 앞에 단어 경계 `\b` 가 없어 패턴 미적중) |
| URL 자격 `user:pw@` | `<SECRET>@` | **pw 가 남음** |
| `Bearer …`, 64-hex | 마스킹됨 | 마스킹됨 |
| 절대경로 | `~/…` 또는 `<ABS>/basename`(상대화) | `<path:HMAC>`. 정보는 없어지지만 상대경로가 아님 |

- 적용 위치
  - A: 클라이언트(`router_client.py:57-81`)가 보내는 것은 program 첫 토큰, 마스킹한 cwd, stderr 500자뿐이다. 데몬이 다시 마스킹하고(`daemon.py:78`), 원문은 디스크에 두지 않는다(원장에는 해시만).
  - B: 클라이언트가 **`tool_response` 전체의 JSON(=성공한 명령의 stdout 포함) 1,200자와 명령 전문**을 보낸다(`shadow_hook_client.py:40-43,54`). 데몬은 그것을 `interventions.jsonl` 에 영구 기록한다(`router_daemon_runtime.py:156`). 위 표의 누락 패턴과 겹치면 `cat .env`, `gh auth token` 같은 출력이 디스크에 남는다.
- 절단
  - A 는 마스킹한 뒤 500자로 자른다.
  - B 는 1,200자로 먼저 자른 뒤 마스킹한다(`router_data_safety.py:43`). 지시는 500자다.
- B 에만 있는 장점
  - `append_bounded_jsonl`(`:101-121`): 레코드 8KB·파일 5MB 상한, O_NOFOLLOW, symlink 거부, 저장소 내부 경로 거부.
  - `resolve_router_home` 이 저장소 밖을 강제한다.
  - A 의 `telemetry.append` 는 크기 상한이 없다. `private_dir` 는 `PI_ROUTER_HOME` 이 가리키는 기존 디렉터리를 무조건 chmod 0700 한다(`paths.py:42`).
- → A 를 기반으로. B 의 상한·symlink·저장소 밖 강제를 `ztc/telemetry.py`·`paths.py` 에 접목한다. A 의 경로 정규식이 `https://` 를 `https:<ABS>` 로 뭉개는 과마스킹은 이번 병합에서는 정리 대상이다(보안상 해는 없음).

## 4. 데몬 하드닝
| 항목 | A | B |
|---|---|---|
| 바인드 | `BIND_HOST="127.0.0.1"` 상수(`paths.py:15`). 환경변수 없음. lsof 증거 `w2_04` | `ROUTER_HOST="127.0.0.1"`(`daemon.py:28`). 환경변수 없음 |
| 64KB→413 | 있음(`daemon.py:177`). 음수 Content-Length 는 통과하고 `rfile.read(-1)` 이 2초 타임아웃까지 대기(경미) | 있음. `isdecimal` 로 엄격 검사, 본문 길이 불일치도 400(`:92-105`) |
| 동시성 | ThreadingHTTPServer, **스레드 상한 없음**, 핸들러 소켓 타임아웃 2s(`:151`). 느린 클라이언트 비직렬화 테스트 있음 | ThreadingHTTPServer + 동시 요청 4개 semaphore, 초과 시 503(`:393-420`). **핸들러 타임아웃 없음** → 느린 연결 4개면 영구 503(아래 버그 B-5) |
| 큐 | `JudgeQueue`: 상한 64, 같은 키 합치기, TTL 30s, cancel, shutdown join(`judge_queue.py`). 실제 판정(휴리스틱→candidate)을 수행 | `ShadowEventQueue`: 상한 64, `(requestId,event)` 중복 제거, `/cancel` 엔드포인트, 드롭 계수. 판정 없이 로그 기록만 함 |
| 자식 프로세스 회수 | 자식 프로세스를 만들지 않는다고 명시 | 같음. 테스트 이름에 "without children" |
| /health | 원장 `SELECT 1` + 워커 생존 여부 → 200 또는 503 | 라우터 존재 + 워커 생존 + 쓰기 오류 0 → 200 또는 503 |
| /telemetry | 카운터·p50/p95/p99·큐·원장 수만 반환. 명령·cwd·경로 0 | 허용 목록 키만 반환. masked_fields 는 제외 |
| 요청 ID | X-Request-Id 를 되돌려 주거나 새로 생성 | tool_use_id 를 requestId 로 사용 |
| 자동 비활성 | 클라이언트 측: 최근 50회 중 20% 초과 실패 시 `disabled` 표지, 수동 복귀(`router_client.py:130-145`). G3 에서 실제 발동 확인 | **없음**(지시 W2-6 미충족) |
- → A 를 기반으로. B 에서 semaphore 동시 상한(`BoundedThreadingHTTPServer`), Content-Length 엄격 검사, `/cancel` 엔드포인트를 접목한다. 핸들러 타임아웃은 A 의 것을 유지한다.

## 5. 훅 클라이언트·settings 배선
| 항목 | A | B |
|---|---|---|
| `{}` 불변식을 강제하는 곳 | sh 래퍼(`router-client.sh:6-15`): python stdout·stderr 를 /dev/null 로 보내고 `printf '{}'; exit 0`. settings 가드에 `\|\| printf '{}'` | python 이 `finally` 에서 `{}` 를 씀(`shadow_hook_client.py:115`). 여기에 settings 의 `node -e` 래퍼가 자식 stdout 을 버리고 `{}` 를 씀(`settings.json:111,123`) |
| 호출당 프로세스 | 하네스 셸 → sh → python3 -S(2개) | node → python3(2개). node 기동 비용이 더 큼 |
| 시간 예산 | 30ms 데드라인. connect·recv 마다 남은 시간 적용(`router_client.py:84-127`). 하네스 timeout 1s(실측 max 84ms 근거) | 30ms(`:13,81-94`). node spawnSync 750ms, 하네스 timeout 2s. **근거 수치 없음** |
| 텔레메트리·K1 | 클라이언트 outcome, rpc_ms, client_ms 1행씩. G3 실측 K1: 내부 RPC p50 1.75 / p99 4.21 ms, 하네스 p50 54 / p99 70 ms(`g3_01`, `g3_02`) | **기록 없음.** RPC 시간을 계산하고 버림. K1 없음, 벤치 스크립트 없음 |
| 파일 없음 가드 | `[ -x … ] && … \|\| printf '{}'`. python3 가 없으면 `cat` 으로 stdin 을 비움 | 파일이 없으면 python 이 오류 → node 가 `{}` |
| Windows 무해성 | cmd 셸에서 실행되면 `[`·`printf` 가 없어 **stdout 이 비고 non-blocking error 가 매 호출 발생**(실기 미확인) | `process.platform!=='darwin'` 이면 곧바로 `{}`. node 만 있으면 깨끗함 → **B 방식이 우수** |
| 등록 이벤트 | PreToolUse·PostToolUse(Bash). **실측: 실패한 Bash 에는 PostToolUse 가 발화하지 않음**(`g3_01` §2) → L0 입력 0 | Pre(`PowerShell\|Bash`)·Post. PostToolUseFailure 파싱 코드는 있으나 미등록. 같은 공백 |
| G3 실기 검증 | 100/100, transcript 240건 전부 `{}`·exit 0·주입 0, 데몬 kill·SIGSTOP·자동 비활성 실발동 | **실기 증거 없음.** 등록 커밋에 본문이 없고, 계약표는 "Runtime verification: not performed" 로 남아 있음 |
- → A 의 클라이언트를 기반으로. settings 가드는 B 의 node-플랫폼 분기 발상을 접목해 Windows 소음을 없애는 것을 검토한다(단 node 한 번 기동 비용을 실측한 뒤에). PostToolUseFailure 등록은 별도 승인 항목으로 올린다.

## 6. Tier-2 게이트 Mac 수정
| 항목 | A | B |
|---|---|---|
| settings 명령 | `sh "$CLAUDE_PROJECT_DIR/scripts/hooks/tier2-gate.sh" \|\| py c:/Pi/…`(`settings.json:105`) | 약 400자짜리 `node -e` 인라인 → `tier2-gate-dispatch.cjs` → `/bin/sh tier2-gate-macos.sh` → python3(`settings.json:105`) |
| 고장 → ask | 인터프리터 없음, 게이트 없음, 비정상 종료 → ask(`tier2-gate.sh:14-20`). 테스트 9개(`test_tier2_gate_wrapper.py`) | 디스패처 없음, 스크립트·python 없음, 비정상 종료 → ask. 잘못된 stdin 은 darwin 에서만 ask(`tier2-gate-hook.py:219`). **커밋된 전용 테스트 없음**(증거 문서의 수동 시뮬레이션뿐) |
| REPO 경로 | `Path(__file__).parent.parent`(`tier2-gate-hook.py:54`) | 같은 방식(`:51`). 충돌은 사소함 |
| 로그 위치 | 저장소 `learning/remote-approvals/tier2-gate-log.jsonl`. **A 는 트랙 실행 로그 6행을 커밋**(worktree scratchpad 경로·명령 전문 포함) | 같은 위치. 커밋된 행 없음 |
| Windows | Git Bash 면 `py`, sh 가 없으면 `\|\| py` 폴백. py 도 없으면 fail-open(기존과 동일) | node 필수. win32 는 `py c:/Pi/…` 를 그대로 실행하고, 오류면 exit 1(fail-open) |
| Codex | `sh scripts/hooks/tier2-gate.sh`(cwd 상대). cwd 가 하위 디렉터리면 Mac 에서 `py` 127 → **fail-open** | **`CLAUDE_PROJECT_DIR` 에 의존**(`.codex/hooks.json:9`). Codex 가 이 변수를 설정하지 않으면 **모든 OS 에서 모든 Bash 가 ask**(Windows Codex 회귀) |
| 환경변수 우회 | 없음 | `TIER2_GATE_SCRIPT`·`TIER2_GATE_PYTHON` 으로 게이트 교체 가능(`tier2-gate-macos.sh:8-9`). 보안 게이트에 주입 지점이 생김 |
- → A 를 기반으로(짧고, 테스트가 있고, G1 실기 ask 6건 증거가 있음). Codex 명령은 두 트랙 모두 미검증이다. A 의 cwd 상대 경로는 `git rev-parse --show-toplevel` 기반으로 보강하는 편이 낫다. A 가 커밋한 tier2 로그 6행은 main 에 넣지 않는다.

## 7. 테스트
- **A: 102개**(unittest 93 + tier2 래퍼 9). 실행 명령 1개: `python3 -m unittest discover -s engines/hybrid_router/tests -p 'test_*.py'`.
  - 빨강→초록 증거: fc79718 위에서 38개 실패·오류(`w2_01`) → 93 OK(`w2_02`). tier2 는 9개 실패 → 통과(커밋 5fdcde0 본문).
  - 실패 경로 fixture(`test_hook_client.py`): 부재, 타임아웃, 권한 거부(403 + 쓰기 불가 홈), 취소(SIGTERM), 과부하(503), 자동 비활성, 잘못된 JSON, 64KB 초과, python 부재, 동시 호출. 7종 전부 + α.
- **B: 28개**(`test_shadow_hook.py` 11, `test_hybrid_router.py` 10, `test_interceptor.py` 7) + 기존 `tests/test_tier2_gate_hook.py` 26(미변경).
  - 부재, 타임아웃, 잘못된 입력·응답, 64KB(입력·HTTP), cancel·dedup·overload·shutdown 을 다룬다.
  - **권한 거부와 클라이언트 취소(SIGTERM) 경로가 없다.**
  - 빨강→초록 기록 없음(커밋 8개 모두 본문 없음. 지시 §6 "본문에 검증 명령과 결과" 위반).
  - `npm test` 99는 기존 jest 스위트다.
- → 합집합 방침. B 의 `test_queue_deduplicates_cancels_overload…`, `/cancel` 스키마, 응답 과대(>4KB) 테스트, `append_bounded_jsonl` 저장소 경로 거부 테스트를 A 구조로 이식한다. 단 B 의 masking·지문 단언은 A 설계와 반대이므로 버린다.

## 8. 문서
| 항목 | A | B |
|---|---|---|
| v0.3 계획 | A1~A12·M1~M6·아스트라 §5 6건 반영, §5.4 운영 안전(S1~S6), 원장 candidate/verified | K0(계약 적합률)을 새로 둠, K2/K4 shadow N/A, Antigravity PreToolUse 는 `decision` 필수라 제외. **원장·데몬 안전·자동 비활성 절은 얇음** |
| HOOK_CONTRACT | 근거 유형 태그([코드]/[설치판]/[문서-ref]/[실측]), 미확인 칸 명시, 실측 행(tool_response 키, 실패 Bash 는 PostToolUse 미발화) | 3개 에이전트 × 이벤트 표를 공식 문서 URL 로 작성. **"Runtime verification: not performed / No hook settings were changed" 가 2e43c35 의 등록 사실과 모순(낡음)** |
| EVAL | 벤치 규약·gold 스키마·그룹 분할. 구현(`hook_bench.py`, `gold.py`)과 일치 | 보존 7일, 256MiB/4,096건, 삭제 절차 → **코드는 5MB 상한뿐, 7일 만료·건수 상한 미구현**(문서만 있음) |
| council entry | **없음**(지시 W4. 트랙 entry 미작성) | 있으나 G0 시점에 멈춰 있음. 동결 해시·구현·G3 기록 없음 |

두 트랙이 충돌하는 문서 주장:
1. **Claude Code PreToolUse 기본 timeout**
   - B 계약표: "event default documented as 30 seconds".
   - A 와 지시문 §2: command 훅 기본 600s.
   - 판정: A 쪽이 검증 세션 인용과 지시문에 일치한다. B 는 재확인이 필요하며, 병합본은 A 값에 "B 문서 재조회 필요" 주석을 단다.
2. **`updatedToolOutput`**
   - B: "공식 문서가 기술한다". 사실상 지원으로 서술한다.
   - A: SDK 문서에는 있고 CLI 레퍼런스 표에는 없어 **미확인**.
   - 판정: 지시문과 검토안이 "미확인" 을 요구하므로 A 가 맞다.
3. **실패 이벤트 경로**
   - A 만 실측했다(실패한 Bash 는 PostToolUse 없음).
   - B 계약표에는 이 행이 없다.
   - 판정: A 를 채택한다.

B 에서 가져올 것: 계약표의 Codex·Antigravity 공식 문서 행(URL·필드명), K0 지표 정의, EVAL 의 보존·삭제 절차. 단 "미구현" 라벨을 달거나 구현과 함께 넣는다.

## 9. 변경 규모·의존성·main 반입 금지 항목
- 규모
  - A: 59 파일, +3,648/−1,058. 증거·메트릭·테스트가 약 절반.
  - B: 34 파일, +1,988/−575.
  - 신규 pip/npm 의존성: 두 트랙 모두 0. B 는 node 내장 모듈만 쓴다.
- **main 반입 금지(두 트랙 공통으로 제거·치환):**
  - A `.claude/settings.json:116,129` — `PI_ROUTER_PORT=9877 PI_ROUTER_HOME="$HOME/.pi-router/opus55"`, 그리고 shadow 훅 등록 자체(D6 원복 규칙)
  - A `router_client.py:40` — `CLIENT_VERSION = "opus55-0.1"`(이름 정리)
  - A `learning/remote-approvals/tier2-gate-log.jsonl` — 트랙 실행 6행(scratchpad 경로와 명령 전문 포함)
  - A `docs/evidence/ztc-phase1-20260924-opus55/`, `learning/metrics/*_20260924.json` — 잠정 수치. 머지 단계에서 순차 재측정한 값으로 교체하거나, 증거로만 보존
  - B `.claude/settings.json:111,123` — `PI_ROUTER_PORT:'9878'`, `'.pi-router','luna'`, 그리고 shadow 등록
  - B **`scripts/router_data_safety.py:31` — 코드 기본값이 `~/.pi-router/luna`**(공통 인터페이스 "기본 `~/.pi-router`" 위반)
  - B 계획 문서 §3 의 "Luna 초안은 `~/.pi-router/luna/` 사용" 문구

## (a) 버그·위험
| # | 심각도 | 위치 | 시나리오 |
|---|---|---|---|
| B-1 | **높음** | `router_data_safety.py:14-20` | `sk-ant-`·`sk-proj-`·`ghp_`·`github_pat_`·AKIA·JWT·`*_API_KEY=`·`*_PASSWORD=`·URL 비밀번호가 마스킹되지 않음(탐침 확인). 지시 W2-10 이 명시한 `sk-`/`ghp_` 누락 |
| B-2 | **높음** | `shadow_hook_client.py:40-43` + `router_daemon_runtime.py:156` | 성공한 Bash 의 stdout(최대 1,200자)과 명령 전문을 모든 호출마다 `~/.pi-router/luna/interventions.jsonl` 에 영구 기록. B-1 과 겹치면 `cat .env` 결과가 평문으로 남음 |
| B-3 | 중 | `.codex/hooks.json:9` | Codex 는 `CLAUDE_PROJECT_DIR` 가 없으면 → 모든 Bash 에 ask. Windows Codex 노드 게이트 동작이 바뀜(미검증인데 커밋됨) |
| B-4 | 중 | `decision-gate-interceptor.py:175` | "SYSTEM DECISION ENGINE OVERRIDE … 직접 조치하십시오" 주입 문구. 이후 훅에 연결되면 로그 유래 텍스트가 지시로 승격됨 |
| B-5 | 중 | `hybrid-router-daemon.py:99`(핸들러 timeout 없음) + semaphore 4 | 같은 UID 프로세스가 Content-Length 만 보내고 멈추기를 4번 하면 영구 503 → shadow 기록 전부 유실(`{}` 는 유지) |
| B-6 | 중 | `router_data_safety.py:9` | 프로세스별 난수 HMAC 키 → 훅 호출 간 지문을 조인할 수 없음. 중복 제거·시그니처 불가, "fingerprint" 필드가 분석에 무의미 |
| B-7 | 중 | `router_core.py:48-63` | `rule_evaluation_order` 의 조건·우선순위를 편집해도 판정이 바뀌지 않음(`default` 제외). 정책 소비가 부분적. 정책 파일이 없으면 기본값으로 조용히 진행 |
| B-8 | 낮음 | `tier2-gate-macos.sh:8-9` | 환경변수로 보안 게이트 스크립트·인터프리터를 교체할 수 있음 |
| B-9 | 낮음 | 계약표 머리말, council entry | 등록 후에도 "변경·검증 없음" 이라고 기재 → 기록과 사실 불일치 |
| A-1 | 중 | `scripts/hybrid-router-cli.py:83-98` | 정직화 누락: "$ 절약·18~28ms·8,500~12,000 토큰" 출력이 남아 있음(W2-1 의 정신 위반, grep 식에는 안 걸림) |
| A-2 | 중 | 설계(`g3_01` §2) | 실패한 Bash 는 PostToolUse 가 없어 L0·원장에 실패 본문이 0건. 대신 성공 명령의 stderr(진행 메시지 등)가 판정 큐로 가서 원장에 'unclassified' candidate 가 쌓임 → 원장 오염. 병합 시 `exit_code is None and event=="PostToolUse"` 면 큐에 넣지 않도록 권고 |
| A-3 | 중 | `router_client.py:130-145` | 데몬을 켜기 전에 훅이 등록돼 있으면 20회 absent 로 자동 비활성 → 데몬을 켠 뒤에도 수동 삭제 전까지 계속 disabled. 절차는 문서화됐으나 운영 함정 |
| A-4 | 낮음~중 | `settings.json:116,129` | Windows cmd 셸에서 `[`·`printf` 가 없어 stdout 이 비고 매 호출 hook error 가 발생(무해하나 소음). 실기 미확인 |
| A-5 | 낮음 | `.codex/hooks.json:9` | cwd 상대 `sh scripts/…` → 하위 디렉터리 cwd 이고 Mac 이면 `py` 127 로 fail-open |
| A-6 | 낮음 | `hybrid-router-daemon.py` 스레드 상한 없음, `:173` 음수 Content-Length, `telemetry.py` 크기 상한 없음, `paths.py:42` 가 임의 `PI_ROUTER_HOME` 을 chmod 0700 | 로컬 자원 고갈·오설정 시 홈 디렉터리 권한 변경 가능 |
| A-7 | 낮음 | `l0.py:29,64` `_NUM` 전역 치환 | HTTP 404 와 500, `exit 1` 과 `exit 137` 같은 경우가 한 시그니처로 합쳐짐 |
| A-8 | 낮음 | `anti_pattern_rules.json:7-8` | `laya_daemon_url`, `intervention_log_path: learning/interventions.jsonl` 등 쓰지 않는 낡은 키가 남음(B 는 경로 갱신) |

## (b) 머지 충돌 핫스팟(두 트랙 모두 크게 수정)
- `scripts/hybrid-router-daemon.py`: 둘 다 전면 재작성. A 로 가고 B 의 semaphore 만 손으로 이식
- `.claude/settings.json`, `.codex/hooks.json`: Tier-2 명령과 shadow 블록이 정면 충돌
- `engines/hybrid_router/router_core.py`, `hierarchical_engine.py`, `gateway/jev_client.py`: 클래스명(Laya 대 HeuristicFallback)과 정책 스키마가 다름
- `config/routing_policy.json`: 스키마 비호환(`when` 술어 대 `conditions`). A 스키마 채택
- `config/anti_pattern_rules.json`, `scripts/decision-gate-interceptor.py`
- `engines/hybrid_router/tests/test_hybrid_router.py`, `test_interceptor.py`
- `docs/PLAN_ZTC_topology_optimization.md`, `docs/harness/HOOK_CONTRACT_ztc.md`·`EVAL_PROTOCOL_ztc.md`(둘 다 새로 만든 파일이라 add/add 충돌)
- `scripts/tier2-gate-hook.py`: REPO 줄. 의도가 같아 쉽게 해소
- `learning/interventions.jsonl`, `learning/user-prompts/`: 합집합. `biome.json`: 두 트랙 변경이 동일

## (c) 머지안
| 모듈 | 기반 | 접목(상대 트랙에서) | 이유 |
|---|---|---|---|
| 1 정직성·정책 | A | B `hybrid-router-cli.py` 정직화, B `jev_config.json` 스텁 키·상용 엔드포인트 삭제, B `anti_pattern_rules.json` 설명문 일부 | A 는 정책 술어를 실제로 평가하고, 개명·skills 규칙 삭제·비신뢰 라벨까지 완료. B 는 개명 누락, SKILL.md 차단 유지, 주입 문구 잔존 |
| 2 L0·원장 | A | 없음(+과병합 테스트 1건 추가, `state`/`status` 명칭 정렬) | B 에는 원장·정규화가 없음 |
| 3 마스킹·데이터 | A | B `append_bounded_jsonl` 의 상한·O_NOFOLLOW·symlink 거부, `resolve_router_home` 저장소 밖 강제(기본값 `~/.pi-router` 로 교정) | B 마스킹은 핵심 토큰을 놓치고 stdout 을 저장함 |
| 4 데몬 | A | B `BoundedThreadingHTTPServer`(semaphore→503), Content-Length `isdecimal`·길이 불일치 400, `/cancel` | A 는 원장·판정 큐·/health 실검사. B 의 동시 상한이 A 의 빈틈을 메움 |
| 5 훅 클라이언트·settings | A | B 의 "비 darwin 이면 곧바로 `{}`" 가드 방식(Windows 소음 제거, node 비용 실측 후 결정). PostToolUseFailure 등록은 별도 승인 | A 는 G3 실측 100/100·K1·자동 비활성이 있음. B 는 텔레메트리·K1 없음 |
| 6 Tier-2 | A | Codex 경로는 두 방식 모두 버리고 저장소 루트 해석 방식으로 새로 작성(미검증 표기). B 의 darwin 잘못된 stdin→ask 는 A 래퍼가 이미 크래시 시 ask 로 덮음 | A 는 짧고 테스트 9개와 G1 실기 증거가 있음. B 는 node 3단계, 환경변수 우회, Codex 회귀 |
| 7 테스트 | A | B 의 큐 dedup·cancel·overload·shutdown, 응답 과대, 로그 저장소 경로 거부 테스트 이식 | 합집합 규칙(§2 D5). 실패 경로 커버리지는 A 가 우위 |
| 8 문서 | A | B 계약표의 Codex·Antigravity 공식 문서 행, K0 지표, EVAL 보존·삭제 절차(미구현 라벨). timeout 30s·`updatedToolOutput` 서술은 **채택하지 않음** | A 는 근거 유형 태그, 실측 행, 미확인 정직성이 있음 |
| 9 운영·반입 | — | 트랙별 포트·홈·shadow 등록·tier2 로그 6행·`opus55`/`luna` 문자열 제거, 벤치 순차 재측정 후 metrics 교체 | 규약 §1·D6 |

잔여 확인 사항: B 계약표 "PreToolUse 기본 30s" 의 출처 재조회, Codex 가 `CLAUDE_PROJECT_DIR` 를 설정하는지와 hooks.json 을 실제로 실행하는지, 실패한 Bash 의 PostToolUseFailure 페이로드(등록 승인 뒤 실측).
