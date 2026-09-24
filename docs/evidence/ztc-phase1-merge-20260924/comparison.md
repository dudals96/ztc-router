# ZTC Phase 1 이중 초안 비교 (D3) — 2026-09-24

머지 담당: Claude Code @ richardkim-macpro-macbookpro (main 체크아웃, 유저 미지정 시 기본값). 규약: `tasks/ztc-phase1-dual-draft__merge-protocol.md` §2 D3·§3.
대상: 트랙 A Opus 5.5 `ztc/phase1-opus55` 구현 동결 3a14fe4 · 트랙 B Luna `ztc/phase1-luna` 구현 동결 2e43c35. 분기점 dcd00b7.
모듈별 file:line 근거 전문: `code-comparison-detail.md` (읽기 전용 서브에이전트, 머지 담당이 핵심 6건 재확인). 측정 원자료: `hook_bench_same_condition.{py,json}`.

## 1. 같은 조건 재측정 (머지 담당 실행, 순차)
각 동결 커밋의 `.claude/settings.json` 에 등록된 shadow 훅 명령을 그대로 실행. 호출마다 고유 tool_use_id, HOME 은 임시 폴더.

| 구간 (ms, 전체 벽시계) | A p50 / p95 / p99 | B p50 / p95 / p99 |
|---|---|---|
| Pre, 동시성 1, n=200 | 27.6 / 28.7 / 31.2 | 51.7 / 53.8 / 55.7 |
| Pre, 동시성 3, n=201 | 31.0 / 33.3 / 37.4 | 56.3 / 59.5 / 66.2 |
| Post, 동시성 1, n=200 | 27.6 / 28.8 / 30.9 | 52.3 / 54.3 / 60.5 |
| Post, 동시성 3, n=201 | 31.4 / 32.7 / 34.4 | 56.2 / 58.0 / 70.5 |
| 데몬 부재, n=50 | 25.9 / 27.6 / 43.7 | 52.5 / 54.9 / 56.7 |
| `{}` 외 출력 | 0 | 0 |

- A 내부 RPC(클라이언트 기록, ok 822건): p50 1.40 / p99 2.08 ms.
- B 가 느린 원인: 호출마다 node → python 두 번의 프로세스 기동.
- 1차 측정 무효: 부재 구간을 먼저 돌리자 A 클라이언트가 자동 비활성(20/20 실패)되고 데몬 복귀 후에도 풀리지 않았다. A 의 결함으로 기록한다.

## 2. 같은 조건 비밀값 탐침 (합성 입력)
- A: `sk-` 합성 키·절대경로 모두 원자료에 남지 않음(해시만).
- B: 절대경로는 HMAC 치환되나 `sk-…` 합성 키가 `~/.pi-router/luna/interventions.jsonl` 에 원문 저장됨. 패턴에 `sk-`·단독 `ghp_`·`github_pat_`·AKIA·JWT 없음(`scripts/router_data_safety.py:14-20`). 성공 명령 stdout 1,200자도 기록(`scripts/shadow_hook_client.py:40-43`).

## 3. 테스트 (동결 스냅샷 재실행)
- A: `python3 -m unittest discover -s engines/hybrid_router/tests -p 'test_*.py'` 102 OK + Tier-2 26/26.
- B: hybrid_router 10 · interceptor 7 · shadow_hook 11 OK + Tier-2 26/26.

## 4. 판정 요약 (§3 비교표 축)
| 축 | 우세 | 근거 한 줄 |
|---|---|---|
| 정직성 | A (CLI 파일만 B) | B 는 `LayaHierarchicalEngine` 명·주입 문구 "[SYSTEM DECISION ENGINE OVERRIDE]"(interceptor:175) 잔존. A 는 `hybrid-router-cli.py:92-98` 과장 문구 미처리 |
| 정책 소비 | A | B 는 규칙 조건 변경이 판정에 반영 안 됨, 정책 파일 부재 시 조용히 기본값 |
| 안전(실패 경로) | 동률, 세부 B 접목 | 둘 다 `{}` 불변. B 의 동시 상한 503·엄격 Content-Length·O_NOFOLLOW 가 A 에 없음 |
| 마스킹 | A | §2 |
| L0 | A | B 는 원장 없음 |
| 성능 | A | §1 |
| 계약 문서 | A (B 행 일부 접목) | B 는 `updatedToolOutput` "문서화됨", timeout 30s 서술 — 지시문·A 와 충돌 |
| 테스트 | A | 102 vs 28(+26) |
| 운영 | A, 복귀 결함 수정 필요 | B 는 자동 비활성 없음 |

## 5. 비용 사실
B 의 shadow 실측은 Claude CLI 유료 호출 약 $0.68(자기 보고)을 썼다. 두 지시문 모두 "유료 호출 0" 이었다. A 의 실측 비용은 기록 없음.

## 6. 머지안 (D4 승인 대상)
기반: 트랙 A 3a14fe4. 통합 브랜치 `ztc/phase1-merged`. 두 트랙 테스트 합집합 통과가 조건.

| 모듈 | 기반 | B 에서 접목 | 머지 중 A 수정 |
|---|---|---|---|
| 정직화·정책 | A | `hybrid-router-cli.py` 정직화 | — |
| L0 원장 | A | — | `_NUM` 전역 치환이 HTTP 상태코드를 합치지 않게, 종료 코드 없는 PostToolUse 는 판정 큐 제외 |
| 마스킹·원자료 | A | JSONL 크기 상한·O_NOFOLLOW·symlink 거부·저장소 밖 강제 | `private_dir` 는 자기가 만든 폴더만 chmod |
| 데몬 | A | 동시 상한 semaphore(초과 503)·엄격 Content-Length·`/cancel` | 음수 Content-Length 거부, 스레드 상한, 핸들러 timeout, telemetry 크기 상한 |
| 훅 클라이언트·settings | A | 비 darwin 즉시 `{}` 가드, "래퍼는 항상 `{}`" 불변식 | 자동 비활성 후 health 확인으로 자동 복귀 |
| Tier-2 | A(sh 래퍼) | — (B 는 Windows 에 node 의존) | Codex 명령 cwd 상대경로 fail-open 수정 |
| 테스트 | 합집합 | B shadow_hook fixture 11 | — |
| 문서 | A | 계약표 Codex·Antigravity 공식 문서 행, K0 지표, EVAL 보존·삭제 절차("미구현" 라벨) | — |

main 제외: 양 트랙 shadow 등록·포트 9877/9878·`~/.pi-router/<track>` 고정값, `CLIENT_VERSION "opus55-0.1"`, A 가 커밋한 tier2 로그 6행, 잠정 metrics 파일(§1 재측정값으로 교체).
