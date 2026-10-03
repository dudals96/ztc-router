# ztc-router — Pi ZTC 라우터 구현체

Pi 토폴로지 ZTC(하이브리드 라우터 + 훅 클라이언트 + 평가 게이트) 구현체를 Pi 저장소에서 분리한 개발 저장소다. 2026-09-28 유저 지시로 분리했다.

## 정본과 실행 기준 (전환 전까지 유효)

| 구분 | 위치 | 비고 |
|---|---|---|
| 개발 정본 | 이 저장소 (`~/projects/ztc-router`, `dudals96/ztc-router`) | 코드·계획·평가 문서의 새 변경은 여기서만 한다 |
| 실행 기준 (live) | `~/Pi` 의 같은 경로 사본 | launchd `com.pi.router-daemon`·`com.pi.router-healthcheck`, Pi 프로젝트 훅 `router-client.sh`, 전역 Claude Code·Codex 훅 `ab-prompt-gate.sh` 가 `~/Pi` 를 가리킨다 |
| 런타임 데이터 | `~/.pi-router` | 저장소 밖. 이관 대상 아님 |

- 10-02 shadow 첫 집계가 끝날 때까지 실행 기준은 `~/Pi` 에 둔다. 7일 수집 창을 끊지 않기 위해서다.
- 그동안 `~/Pi` 쪽 ZTC 파일은 고치지 않는다. 여기서 고친 내용을 live 에 반영해야 하면 전환을 앞당기는 별도 승인을 받는다.
  - 예외 기록(2026-10-03, 유저 AUQ 승인): 평가 게이트가 세션 간 메시지·서브에이전트 보고에 묻지 않게 한 수정을 `~/Pi`(`6d2f7a3`)와 여기(`6c8fe2e`)에 같이 넣었다. 10-02 집계 창은 지난 뒤다.
- 전환(launchd 2개·훅 3곳 경로 변경, 데몬 재시작)과 Pi 쪽 사본 정리는 첫 집계 뒤 별도 유저 승인으로 한다.

## 구성

- `engines/hybrid_router/` — 라우터 코어, `ztc/`(L0 정규식·마스킹·텔레메트리·gold·judge 큐), 계층 라우팅, 테스트
- `scripts/` — 데몬 `hybrid-router-daemon.py`, CLI, 헬스체크, `decision-gate-interceptor.py`
- `scripts/hooks/` — 라우터 훅 클라이언트, A/B 평가 편입 게이트
- `config/` — `anti_pattern_rules.json`(L0 규칙), `routing_policy.json`, `jev_config.json`, `ab_gate.json`, launchd 템플릿
- `docs/PLAN_ZTC_topology_optimization.md` — 실행 계획
- `docs/harness/` — 훅 계약표·평가 규약·A/B 평가 절차 (세부 정본)
- `docs/evidence/ztc-*` — Phase 1 검증·머지·계획 검토 증거
- `tasks/` — Phase 1 이중 초안 위임·머지 규약

디렉터리 배치는 Pi 와 같게 유지했다. 테스트와 스크립트가 저장소 루트 기준 상대 경로(`scripts/`, `config/`)를 쓰기 때문이다.

## 테스트

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s engines/hybrid_router/tests
```

분리 시점 결과: 148개 통과. Pi 에서는 157개였고, 빠진 9개는 `test_tier2_gate_wrapper.py` 다.

## Pi 에 남긴 것

- Tier-2 보안 게이트(`scripts/tier2-gate-hook.py`, `scripts/hooks/tier2-gate.sh`)와 그 테스트: Pi 의 `.claude/settings.json`·`.codex/hooks.json` 을 검사하는 Pi 고유 게이트다.
- 턴 기록(`docs/turn-reports/`), 유저 원문(`learning/user-prompts/`), 세션 인계 문서: Pi 의 작업 이력 기록이다.
- 발표 덱 등 claude.ai Artifact: 저장소 밖.

## 분리 방식

Pi `main` @ `a3ed310` 을 로컬 복제한 뒤 `git filter-repo --paths-from-file` 로 위 경로의 커밋 이력만 남겼다(38커밋). 분리 직후 모든 파일의 blob 해시가 Pi `a3ed310` 과 같음을 확인했다. 원 커밋 해시는 바뀌었으므로 Pi 쪽 증거 문서가 가리키는 해시는 Pi 저장소에서 찾는다. 사용한 경로 목록은 `docs/MIGRATION_PATHS.txt`.
