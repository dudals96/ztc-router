# ZTC Phase 1 이중 초안 · 머지 규약 (2026-09-24, 발주: Claude Code @ richardkim-macpro-macbookpro)

유저 결정(2026-09-24 원문 `learning/user-prompts/2026-09-24_Thu/11_dual-draft-merge.md`): 같은 의도를 서로 다른 코딩 에이전트가 각자 구현체 초안으로 작성하고, 각 초안의 장단점을 포용해 머지한다. 이 파일은 두 초안이 서로 부딪히지 않고, 나중에 공정하게 비교·병합되도록 하는 사전 조치다. 두 지시문(`tasks/claude-code-to-opus55__ztc-phase1-impl.md`, `tasks/codex-to-gpt6-luna__ztc-phase1-impl.md`) 머리의 "병렬 초안 모드" 블록이 이 파일을 참조한다.

## 1. 트랙 격리표 (binding)
| 항목 | 트랙 A: Opus 5.5 | 트랙 B: Luna (GPT-6) |
|---|---|---|
| 도구 | Claude Code CLI, `claude-opus-5-5` | Codex CLI 0.156.1, `gpt-6-luna` |
| worktree | `~/Pi-wt/ztc-opus55` | `~/Pi-wt/ztc-luna` |
| 브랜치 | `ztc/phase1-opus55` | `ztc/phase1-luna` |
| 분기점 | 이 파일을 담은 main 커밋 | 동일 |
| 원자료 루트 | `~/.pi-router/opus55/` | `~/.pi-router/luna/` |
| 데몬 포트 | 9877 | 9878 |
| 증거 폴더 | `docs/evidence/ztc-phase1-<YYYYMMDD>-opus55/` | `docs/evidence/ztc-phase1-<YYYYMMDD>-luna/` |
| council entry | `<date>_claude-code-opus55_ztc-phase1-<slug>.md` | `<date>_codex-luna_ztc-phase1-<slug>.md` |

- 포트 9876 과 `~/.pi-router/` 최상위는 머지본의 기본값으로 예약한다. 어느 트랙도 쓰지 않는다.
- 공통 인터페이스 두 가지만 고정한다. 나머지 설계는 각 트랙 자유다.
  1. 데몬 포트는 환경변수 `PI_ROUTER_PORT`(기본 9876), 원자료 루트는 `PI_ROUTER_HOME`(기본 `~/.pi-router`) 으로 받는다. 외부 바인드를 여는 환경변수는 두지 않는다.
  2. 전체 테스트는 저장소 루트에서 한 명령으로 돈다. 그 명령을 council entry 첫 절에 적는다.
- `main` 에 커밋·push 하지 않는다. 자기 브랜치에만 커밋한다. 자기 브랜치 push 는 각 정지점에서 유저가 지시할 때만.
- 상대 트랙의 브랜치·worktree·원자료를 초안 동결(§2 D2) 전까지 읽지 않는다. 독립성이 이 방식의 가치다.
- 훅 등록(G3)은 자기 worktree 의 `.claude/settings.json` 또는 `.codex/hooks.json` 에만 한다. main 체크아웃·사용자 전역 설정·다른 worktree 는 건드리지 않는다.
- 벤치는 동시에 돌리지 않는다. 같은 Mac 에서 CPU 를 다툰다. 각 트랙의 벤치 수치는 잠정값이며, 비교용 최종 수치는 머지 단계에서 같은 조건으로 순차 재측정한다.
- `session-recover.ps1` 은 worktree 에서 `-Pull` 없이 실행한다. 새 브랜치엔 upstream 이 없다. Handoff Bus 수신은 main 체크아웃 세션의 몫이다.
- `learning/interventions.jsonl`·`learning/user-prompts/` 는 양쪽이 추가만 한다. 머지 때 합집합으로 해소한다.

## 2. 단계
- **D1 초안 작성:** 각 트랙이 자기 지시문대로 진행한다. 정지점(G0~G3)은 트랙별로 유저에게 따로 묻는다. 한쪽 승인은 다른 쪽 승인이 아니다.
- **D2 동결:** 트랙이 "오프라인 구현 통과" 또는 도달 가능한 마지막 정지점에 닿으면 멈추고, 마지막 커밋 해시를 council entry 에 적는다. 유저 지시로 브랜치를 push 한다. 이후 그 브랜치는 머지 끝까지 수정하지 않는다.
- **D3 비교:** 두 브랜치가 모두 동결되면 머지 담당(유저 지정, 미지정 시 main 체크아웃의 Claude Code)이 §3 표로 비교한다. 결과는 `docs/evidence/ztc-phase1-merge-<YYYYMMDD>/comparison.md` 에 둔다.
- **D4 머지안 승인:** 모듈별로 "기반 초안 + 접목할 상대 부분"을 제시하고 AskUserQuestion 으로 승인받는다.
- **D5 통합:** `ztc/phase1-merged` 브랜치에서 승인안대로 합친다. 두 트랙의 테스트 합집합이 전부 통과해야 한다. 한쪽에만 있던 실패 경로·마스킹 테스트는 버리지 않는다.
- **D6 main 반영:** 유저 승인 후에만. 시행 중이던 트랙별 훅 등록은 원복을 확인한다.

## 3. 비교표 (D3, 항목마다 증거 경로를 단다)
| 축 | 보는 것 |
|---|---|
| 정직성 | 시뮬 상수·과장 문구 grep 0건, 이름만 바꾼 눈속임 여부 |
| 정책 소비 | `config/routing_policy.json` 변경이 판정을 바꾸는 테스트 |
| 안전 | 실패 경로(부재·타임아웃·거부·취소·과부하·잘못된 JSON·64KB 초과) 모두 stdout `{}`·exit 0, 외부 바인드 0 |
| 마스킹 | 합성 비밀 입력이 전송·로그·집계로 새지 않음 |
| L0 | 정규화 과병합 방지 테스트, 원장 스키마(candidate/verified·출처·만료), 조회 지연 |
| 성능 | 머지 단계 순차 재측정: 전체 vs 내부 RPC, cold/warm, 동시성 1/3, p50/p95/p99 |
| 계약 문서 | v0.3·계약표·평가 규약의 정확성, "미확인" 칸 정직성 |
| 변경 규모 | 파일 수·diff 줄 수·신규 의존성 0 |
| 테스트 | 빨강→초록 이력, 합집합 커버리지 |
| 운영 | 원복 절차, 자동 비활성·복귀 절차 |

## 4. 금지 (두 트랙 공통, 각 지시문의 금지와 합집합)
NV 쓰기, launchd 등록·해제, Tier-2 승인 파일, 유료 API, 외부 알림, INBOX(astra) 소비, UTR 덮어쓰기, `main` 직접 커밋, 상대 트랙 열람(D2 전), 동시 벤치.
