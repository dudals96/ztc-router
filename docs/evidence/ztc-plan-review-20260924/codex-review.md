<!-- 원본: codex exec --sandbox read-only --ephemeral, 2026-09-24, Mac richardkim-macpro-macbookpro. 파일 수정 없음. 계획 v0.1 (커밋 74ec602) 대상. -->

# Codex 카운슬 검토 — ZTC 토폴로지 최적화 계획 v0.1

**판정: 현재 초안의 Phase 1 착수 승인은 보류하는 편이 타당합니다.** 시뮬레이션 수치를 실측으로 바꾸려는 방향은 맞지만, 현재 구현과 계획의 전제가 다르고, 안전한 실행 순서와 검증 기준을 먼저 바로잡아야 합니다. 코드를 읽어 대조했으며, 실행·성능 측정은 하지 않았습니다.

## 1. 계획의 주장과 코드가 어긋나는 점

- **현재 구현은 실제 Laya 모델이나 신뢰도 기반 라우터가 아닙니다.** `hierarchical_engine.py`는 키워드 규칙 점수를 정규화하고(`:35-64`), 경과 시간에 `18.5ms`를 더한 뒤 `34.2ms`로 제한합니다(`:146-176`). `router_core.py`도 `confidence` 임계치로 다음 단계에 넘기지 않고 카테고리 수 등으로 라우트를 고릅니다(`:36-55`). 따라서 “Laya forward pass·logit 기반 판정·confidence gating”이라는 UTR의 100% 구현 주장은 코드로 뒷받침되지 않습니다(`docs/UNIFIED_TURN_REPORT.md:11-18`).
- **계획도 가짜 지연을 인지하지만 실제 모델의 준비 상태를 과대 전제합니다.** 코드에서 가중치 로드나 모델 추론 호출은 확인되지 않고, 모델이라고 부르는 엔진은 규칙 기반입니다(`engines/hybrid_router/hierarchical_routing/hierarchical_engine.py:35-64,146-176`). 계획의 “실제 Laya” 설치·추론은 아직 검증할 미래 작업입니다(`docs/PLAN_ZTC_topology_optimization.md:29,163`).
- **라우팅 정책 파일은 현재 코드 경로에 연결돼 있지 않습니다.** 설정은 `config/routing_policy.json`에 있지만(`config/routing_policy.json:1-6`), 라우터 기본 경로는 저장소 루트의 `routing_policy.json`입니다. 더구나 `evaluate_route()`는 정책 내용 대신 하드코딩된 조건을 씁니다(`engines/hybrid_router/router_core.py:22-34,36-55`). 계획에서 임계값을 설정 파일로 옮기기 전에 이 경로와 실제 소비 여부부터 해결해야 합니다.
- **인터셉터의 실제 실패 경로는 계획의 30ms fail-open과 다릅니다.** 데몬 요청 타임아웃은 1.5초이고, 실패하면 Python 내 로컬 폴백으로 넘어갑니다(`scripts/decision-gate-interceptor.py:45-62`). PostToolUse는 연속 실패 임계값이나 오류 시그니처를 확인하지 않고 모든 비정상 종료를 분류합니다(`:160-179`). 계획의 경량 셸 클라이언트와 30ms 상한은 새 설계이지 현재 동작이 아닙니다(`docs/PLAN_ZTC_topology_optimization.md:98,161`).
- **인터셉터 설정의 도구 제한·처방이 코드에서 안전하게 적용되지 않습니다.** 설정에는 `target_tools`와 오류 패턴이 있지만(`config/anti_pattern_rules.json:10-30,31-67`), 구현은 `tool_name` 및 패턴 검증 없이 경로 일치나 `exit_code != 0`으로 동작합니다(`scripts/decision-gate-interceptor.py:98-158,160-179`). 분류 결과만으로 파일 생성을 차단하고, 누락 의존성 설치나 포맷 파일 변경을 지시할 수 있습니다(`config/anti_pattern_rules.json:41-56`; `scripts/decision-gate-interceptor.py:143-155,199-205`).
- **Jev도 현재 실 HTTP 호출이 아니라 시뮬레이션입니다.** `_execute_jev_call()`은 45ms 대기 후 로컬 점수로 응답합니다(`engines/hybrid_router/gateway/jev_client.py:101-147`). 계획이 Phase 2에서 실 HTTP 경로를 만들겠다고 구분한 점은 맞지만, 현재의 “API 라우팅·서킷 브레이커”를 운영 실적으로 간주하면 안 됩니다.
- **실측 근거는 재현 가능한 저장 증거가 아닙니다.** 훅 57.7ms p50은 7회 스크래치패드 측정이고 원자료는 비보존입니다(`docs/PLAN_ZTC_topology_optimization.md:18-36,241`). 11개 세션의 캐시율은 로그 집계 주장이고, cache_creation 원인을 지침 변경 등으로 귀속한 근거는 제시되지 않았습니다(`:30,142-146`). 또한 계획의 Phase 1.6은 Laya 추론 “1회”로 p50 목표를 판정하려 하므로 측정 기준과 맞지 않습니다(`:56-59,163`).
- **데몬 가동 여부는 노드·시점별로 분리해야 합니다.** 계획은 Mac에서 미가동이라고 쓰지만(`docs/PLAN_ZTC_topology_optimization.md:27`), UTR은 i7 세션 복구에서 9876 데몬이 활성이라고 보고합니다(`docs/UNIFIED_TURN_REPORT.md:4,17`). 대상 노드와 확인 시점이 달라 직접 모순이라고 단정할 수는 없습니다. 노드별 상태 증거 없이는 현재 가동 여부를 확정할 수 없습니다.

## 2. 빠진 고려사항

- **분산 일관성:** `sourceCommit`·`treeDigest`만으로 동시 변경, 서브모듈·무시 파일·심볼릭 링크, 워커 중복 실행, 임대 만료 후 늦은 결과, 취소와 완료의 경합을 처리하는 규칙이 부족합니다. SQLite 미러의 단일 정본, 복구·중복 제거, 재시도 및 결과의 원자적 공개도 정해야 합니다(`docs/PLAN_ZTC_topology_optimization.md:126-129,188-190`).
- **보안·서명 경계:** 명령 클래스 허용 목록은 `npm`/테스트/린터 플러그인이 실행하는 저장소 코드를 제한하지 않습니다. 파일 변경 탐지는 실행 이후 검사라 비밀 읽기나 네트워크 반출을 막지 못합니다. 격리된 임시 작업 트리, 비밀 없는 계정, OS 수준 읽기 전용·네트워크 차단이 필요합니다(`:126-129,203`).
- **비용과 데이터 취급:** 일 $2 상한은 에이전트·API 예산일 뿐, 3~4GB 패키지 설치·모델 다운로드·디스크·전력·CPU 경쟁·라벨링 인력 비용까지 설명하지 않습니다(`ai_guidelines.md:21-24`; `config/agent_limits.json:29-37`; `docs/PLAN_ZTC_topology_optimization.md:62,163,228`). Claude Code transcript로 gold 셋을 만들 때는 민감한 입력의 최소수집·비식별화·보존 기간도 필요합니다(`docs/PLAN_ZTC_topology_optimization.md:113`).
- **운영·관측성:** 데몬은 `0.0.0.0:9876`에 바인드하면서 인증이 없고, `/health`는 실제 준비 상태를 검사하지 않고 항상 `ready`를 반환합니다(`scripts/hybrid-router-daemon.py:71-84,346-370`). 단일 스레드 서버, 요청 크기 제한, 로그 억제도 확인됩니다(`:321-343`). 로컬 전용 바인딩, 요청 ID, p95/p99, 오류율·큐 적체·워커 상태, 로그 민감정보 제거 및 보존 정책이 필요합니다.
- **테스트 전략:** 현재 8개 테스트는 휴리스틱 출력과 시뮬레이션 경로를 주로 확인하며, 실제 엔진 지연·훅 타임아웃·HTTP 접근 통제·동시 요청·단절 후 복구는 검증하지 않습니다(`engines/hybrid_router/tests/test_interceptor.py:26-53`; `test_hybrid_router.py:29-75`). Phase 3의 몇 가지 데모만으로는 분산 중복·재생·경합을 덮기 어렵습니다(`docs/PLAN_ZTC_topology_optimization.md:186-190`).
- **미션 우선순위:** Pi의 현재 제품 초점은 Remote Vibe Hub와 원격 작업 제어입니다(`docs/PROJECT_BRIEF.md:4-18`). 계획은 라우팅 작업을 배관으로 분류하지만, 이 작업이 현재 초점보다 먼저인 이유와 기회비용은 설명하지 않습니다(`docs/PLAN_ZTC_topology_optimization.md:42-50`). 또한 Council은 파일 기반이며 보장된 메시지 버스가 없으므로, “Handoff Bus 연동”은 기존 기능이 아니라 별도 제안으로 명시해야 합니다(`docs/AGENT_COUNCIL_PROTOCOL.md:8-21`; 계획 `:142-146`).

## 3. 반대 의견 및 순서 조정

- **현재 인터셉터의 차단·처방 동작을 바로 켜지 마십시오.** 어떤 분류 결과든 사용자의 도구 실행에 영향을 줄 수 있고, 현재는 실제 오류 시그니처 확인조차 없습니다. 먼저 관측 전용(shadow)으로 판정과 실제 결과를 비교한 뒤 제한된 경로에서 opt-in 해야 합니다(`scripts/decision-gate-interceptor.py:160-207`).
- **인증 없는 데몬을 상시 등록하지 마십시오.** LaunchAgent 등록은 보안 경계와 준비 상태 검증 이후로 미루고, 먼저 UNIX 소켓 또는 loopback 전용 바인딩·인증·입력 크기 제한·정직한 readiness를 확정해야 합니다(`scripts/hybrid-router-daemon.py:71-84,321-370`; 계획 `:160,218`).
- **Laya 설치를 먼저 승인하지 마십시오.** 계획은 1회 추론으로 p50을 보려 하면서 수 GB 설치를 요구합니다. 모델·라이선스·체크포인트·호환성·반복 지연·메모리 측정을 정한 후, 설치 가치가 확인될 때 별도 판단하는 편이 낫습니다(`docs/PLAN_ZTC_topology_optimization.md:163,228`).
- **순서는 계약·측정 정의 → 정책·측정 정직화 → gold/holdout 평가 → shadow 검증 → 로컬 데몬 안전화 → 제한적 인터셉션 → 분산 프리페치가 적절합니다.** 현재 WBS는 데몬 상시화·훅·L0를 gold 셋 확정과 모델 타당성 전에 배치합니다(`docs/PLAN_ZTC_topology_optimization.md:154-166`).
- **계획 내부의 골드셋 기준도 일치시켜야 합니다.** K3는 Phase 1에 300건을 요구하지만 WBS 1.7은 100건을 요구하고 Phase 2에서야 300건을 둡니다(`docs/PLAN_ZTC_topology_optimization.md:58,164,174`).

## 4. Phase 1에서 우선 바꿀 구체 개선 — 5개

1. **P0 — 런타임 사실과 정책 경로를 먼저 바로잡기.** 가짜 지연·신뢰도 표기를 없애고 측정값을 그대로 노출하며, 실제 정책 파일 경로와 사용 여부를 테스트로 고정합니다. 허위 KPI와 설정이 무시되는 문제를 동시에 막습니다(`engines/hybrid_router/hierarchical_routing/hierarchical_engine.py:60-64,166-176`; `router_core.py:22-34,49-75`).
2. **P0 — 인터셉터를 shadow-only로 제한하고 데몬 노출을 닫기.** tool/error allowlist를 실제 검증에 연결하고, 위험 처방은 승인 없이 실행 지시로 반환하지 않습니다. 상시화 전에 loopback/UNIX 소켓과 readiness를 갖춥니다(`scripts/decision-gate-interceptor.py:98-158,160-207`; `scripts/hybrid-router-daemon.py:71-84,368-370`).
3. **P1 — 재현 가능한 벤치 규약을 확정하기.** cold/warm, Python 기동 포함 여부, 동시성, p50/p95/p99, 환경·명령·원자료 보존을 정하고, 1회 추론을 p50 판정으로 쓰지 않습니다(`docs/PLAN_ZTC_topology_optimization.md:56-59,158-163,241`).
4. **P1 — gold 셋과 판정 기준을 실제 라우팅 도입 전에 고정하기.** 클래스별 표본·holdout·유저 라벨 검수·오분류 비용을 정의하고, 100/300건 기준 충돌을 해소합니다(`docs/PLAN_ZTC_topology_optimization.md:58,113-115,164,174,206`).
5. **P1 — 텔레메트리와 비용 원장을 사용자 개입 기록에서 분리하기.** 코드가 고정 추정치를 실제 절감처럼 합산하는 경로를 멈추고, 실측 지연·추정 절감·API 비용을 별도 필드로 기록하며 민감정보를 제거합니다(`scripts/decision-gate-interceptor.py:64-78,81-94`; `scripts/hybrid-router-daemon.py:91-120`; `config/anti_pattern_rules.json:23-24,68-69`; 계획 `:64,217`).

## 5. §9-1 추측 실행 템플릿 서명 모델 — 독립 평가

**방향은 UX 개선으로 이해되지만, 현재 제안만으로는 승인할 수 없습니다.** 매 작업마다 서명하기 어려운 문제를 템플릿으로 풀고, 키와 암호구절을 사용자에게 남기는 점은 합리적입니다. 그러나 C2의 작업별 서명에서 7일짜리 위임 권한으로 바뀌므로, 이것은 단순 형식 변경이 아니라 권한 범위 확대입니다(`docs/PLAN_ZTC_topology_optimization.md:33,126-129,226`).

서명 템플릿에는 정규화된 불변 스키마와 버전·키 ID·대상 저장소/워커·만료·폐기·재생 방지 nonce가 필요합니다. 개별 파생 작업도 신뢰된 스케줄러의 서명을 받아야 하고, `sourceCommit`·`treeDigest`뿐 아니라 정확한 argv/인자 제한·도구체인 버전·자원 상한에 결합해야 합니다. 저장소 코드 실행을 고려해 비밀 없는 격리 환경과 OS 수준 네트워크 차단을 먼저 갖춰야 합니다. 파일 변경 감지와 명령 클래스만으로는 충분하지 않습니다(`docs/PLAN_ZTC_topology_optimization.md:126-129,203`; `scripts/hybrid-router-daemon.py:321-336,368-370`).

**권고:** §9-1은 Phase 1 승인 항목에서 빼고, 로컬 격리·재생 방지·취소/복구·실패 주입 검증을 통과한 뒤 별도의 보안 검토와 사용자 승인 대상으로 다시 올리십시오(`docs/PLAN_ZTC_topology_optimization.md:176,186-193,226`).

요청에 따라 계획 검토만 했으며 파일은 수정하지 않았습니다.