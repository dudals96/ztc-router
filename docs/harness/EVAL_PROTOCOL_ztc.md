# EVAL_PROTOCOL_ztc — gold 셋·KPI·벤치 평가 규약 (ZTC Phase 1)

- Status: **DRAFT (트랙 A: Opus 5.5 초안)** — G0 승인 대상. 수치 목표는 사전 지정이며 측정 후 바꾸지 않는다(바꾸면 버전을 올리고 사유를 적는다).
- 작성: Claude Code (Opus 5.5) @ richardkim-macpro-macbookpro, 2026-09-24
- 상위: `docs/PLAN_ZTC_topology_optimization.md` v0.3 §2, `docs/harness/HOOK_CONTRACT_ztc.md`

## 0. 원자료와 집계의 위치
| 종류 | 위치 | git |
|---|---|---|
| 원자료(텔레메트리·벤치 원자료·gold·원장) | `$PI_ROUTER_HOME` (기본 `~/.pi-router/`; 트랙 A 초안은 `~/.pi-router/opus55/`) — `telemetry/*.jsonl`, `gold/`, `signatures.sqlite` | 추적 안 함 |
| 일별 집계 | `learning/metrics/*.json` | 추적. **원자료·명령문·경로 금지** |
- 원자료 보존: 30일 롤링(텔레메트리), gold 는 유저 삭제 시까지. 디렉터리 권한 0700, 파일 0600.
- git 추적 폴더에 들어간 파일은 다음 커밋에 포함되고 pull 로 다른 노드에 전파된다(자동 push 는 아님). 그래서 원자료를 두지 않는다.
- 이 위치는 유저 결정 ④ — G0 에서 확정.

## 1. gold 스키마
### 1.1 마스킹 규칙 (스키마보다 먼저 고정)
훅 클라이언트 마스킹(`HOOK_CONTRACT_ztc.md` §3)을 통과한 문자열만 gold 후보가 된다. gold 저장 시 한 번 더 같은 마스커를 적용한다(멱등). 검증기는 마스킹 뒤에도 남은 비밀 패턴이 있으면 행을 거부한다.

### 1.2 행 스키마 (`gold/v1.jsonl`, 한 줄 한 사례)
| 필드 | 형 | 필수 | 설명 |
|---|---|---|---|
| `id` | string | ✓ | `g-<8hex>` |
| `schema` | string | ✓ | `ztc-gold/1` |
| `group` | object | ✓ | `{session: <sha256 앞 12>, signature: <정규화 시그니처 해시>, project: "pi"}` — 분할 단위 |
| `event` | string | ✓ | `PreToolUse` / `PostToolUse` |
| `tool` | string | ✓ | 예 `Bash` |
| `program` | string | ✓ | 명령 첫 토큰 |
| `text` | string | ✓ | 마스킹된 오류 본문, ≤ 500자 |
| `exit_code` | int\|null | ✓ | 없으면 null |
| `label` | string | ✓ | 클래스 (`syntax_compile`/`dependency_missing`/`lint_formatting`/`permission_auth`/`other`/`abstain`) |
| `label_source` | string | ✓ | `user` / `agent-draft` — `agent-draft` 는 유저 검수 전 평가에 쓰지 않는다 |
| `split` | string | ✓ | `tune` / `holdout` — 그룹 단위로 배정, 사후 이동 금지 |
| `created_at` | string | ✓ | ISO-8601 |
| `attribution` | object | ✓ | `{head: <commit>, worktree_sha256: <판정 대상 파일 해시 묶음>}` (A12) |

### 1.3 그룹 분할
- 분할 단위는 **세션**. 같은 세션의 사례는 모두 같은 split. 같은 정규화 시그니처가 두 split 에 동시에 있으면 holdout 쪽을 버린다(누수 방지).
- 비율: tune 70% / holdout 30% (세션 수 기준). holdout 은 평가 전 봉인(파일 sha256 을 `learning/metrics/gold_stats.json` 에 기록)하고 규칙 조정에 쓰지 않는다.
- 평가 중 원장 write-through 동결.
- 클래스별 holdout ≥ 20건이 안 되면 그 클래스는 "표본 부족" 으로 보고하고 정확도를 주장하지 않는다.

## 2. KPI v0.3 정의
| # | KPI | 정의 | Phase 1 목표/상태 |
|---|---|---|---|
| K1 | 훅 지연 | 두 층을 따로 잰다: **전체 지연**(하네스가 프로세스를 띄워 stdout 을 받을 때까지 — 클라이언트 쪽에서는 프로세스 시작~종료로 근사) / **내부 RPC 지연**(소켓 연결~응답 수신). 각각 cold·warm × p50/p95/p99, 타임아웃률(내부 예산 30 ms 초과 비율), 중립 반환률(=100% 가 shadow 정상) | 첫 값 기록. 목표: 내부 RPC p99 ≤ 30 ms, 타임아웃률 < 1%. 전체 지연은 목표 없이 보고(프로세스 기동이 지배) |
| K2 | 무토큰 분류율 | L0 가 확정 판정한 건수 / 실패한 도구 호출(exit≠0) 건수. **최초 관측 시그니처와 재관측을 분리**. 분류율 ≠ 해결률 | shadow 기록으로 첫 값 |
| K3 | shadow 처방 적합률 (gold 대비) | holdout 에서 L0 판정 = 유저 라벨 비율 + 95% CI(Wilson). 기권은 오답이 아니라 별도 칸 | gold 부재 시 "기준선 미확보" |
| K4 | 오처방률 | 주입된 처방 후 결과를 채택/해결/재발/포기/회귀 5분류. **shadow 에서는 주입이 0 이므로 N/A** (0% 아님) | N/A |
| K5 | 프리페치 히트율 | Phase 2 | 범위 밖 |
| K6 | 프리페치 낭비율 | Phase 2 | 범위 밖 |
| K7 | 세션당 총비용 | input + cache_write + cache_read + output + L3 + retry 토큰·비용, 성공률, 완료시간을 함께 | Phase 2 (집계 스크립트) |

### 2.1 해결의 정의 (A11)
- **해결** = 같은 목표 검사(같은 프로그램·같은 정규화 대상)가 이후 exit 0 으로 성공한 것이 관측됨.
- 재발 없음만으로는 해결이 아니다. **포기**(같은 목표를 다시 시도하지 않고 세션 종료) 와 **관측 종료**(세션이 끝나 판단 불가) 는 따로 센다.
- 순효과에는 CPU·메모리·취소 낭비와 원문 재조회 비용을 포함한다.

### 2.2 비열등 검정 (A3, K3 의 Phase 2 비교에 적용)
사전 지정:
- 비교: L0 v1 vs 휴리스틱(현 `HeuristicFallbackEngine`), 같은 holdout 사례에 대한 **paired** 판정.
- 비열등 마진 Δ = 3%p (L0 정확도 − 휴리스틱 정확도 > −3%p 이면 비열등).
- 통계: paired 차이의 95% CI (discordant 쌍 b, c 기반 — Newcombe 방식 또는 부트스트랩, 세션 클러스터 부트스트랩으로 세션 내 상관 반영). McNemar 이름만으로 대체하지 않는다.
- 검정력: 사전 계획 단계에서 파일럿 discordance 비율 p_d 를 tune 셋으로 추정하고, 단측 α=0.025·검정력 80% 로 필요 쌍 수 n ≈ (z_α+z_β)² · p_d / Δ² 을 산정해 기록. n 이 holdout 보다 크면 비열등을 주장하지 않는다.
- 단일 오류율 상한(오류 0건 단측 95% 상한 1−0.05^(1/n), n=90 → 3.27%, n=300 → 0.99%)은 참고값이며 비열등 증명이 아니다.
- 조정용(tune)과 최종 holdout 분리, holdout 은 한 번만 연다.

## 3. 벤치 규약
| 축 | 값 |
|---|---|
| 상태 | cold(데몬 기동 직후 첫 호출, 파이썬 바이트코드 캐시는 유지) / warm(동일 데몬 N번째 호출) |
| 동시성 | 1 / 3 |
| 반복 | 조건당 ≥ 200회(cold 는 조건당 ≥ 30회 데몬 재기동). **1회 측정으로 p50 을 주장하지 않는다** |
| 통계 | p50 / p95 / p99 / max, 타임아웃률, 중립 반환률 |
| 층 | 전체(프로세스 기동 포함) vs 내부 RPC 를 **분리** 기록 |
| 환경 기록 | 노드, OS, Python 버전, 커밋, 작업트리 sha256, 동시 실행 중인 다른 벤치 없음(병렬 초안 규약: 동시 벤치 금지) |
| 원자료 | `$PI_ROUTER_HOME/telemetry/bench_<YYYYMMDD>.jsonl` |
| 집계 | `learning/metrics/bench_<YYYYMMDD>.json` — 반드시 `"prior_values_note": "이전 값(18 ms·34.2 ms·38.5 ms 등)은 코드 상수로 만든 시뮬 값이며 측정이 아니다"` 포함 |
| 트랙 초안 수치 | 잠정값. 머지 단계에서 같은 조건으로 순차 재측정한 값만 비교에 쓴다 |

## 4. 정직성 규칙
- 문서 인용을 [실측] 으로 표기하지 않는다.
- 추정치는 필드명에 `_estimate` 를 붙이고 합계에 섞지 않는다.
- 측정 못 한 값은 빈칸이 아니라 `null` + 사유.
