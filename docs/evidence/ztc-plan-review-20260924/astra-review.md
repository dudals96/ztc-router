# 아스트라 ZTC v0.2 검토 — 채팅 의견 편집 보존본

Date: 2026-09-24
Source: 현재 ChatGPT 아스트라/Codex 대화의 직전 검토 응답.
Provenance: 사용자 요청으로 인계용 편집·요약 보존. 원문 transcript 또는 새 검증 결과가 아니다.
Method: 지정 문서·코드 읽기 + 공식 웹 문서 조회. 코드 실행·벤치·시스템 변경 없음.

## 종합
방향 채택, v0.2 그대로 Phase1 착수 보류. 접수 직원이 조언만 기록하는 동안 조언의 실제 효과를 측정할 수 없고, 미리 만든 음식과 주문의 동등성 확인 없이 바꿔 내놓아서는 안 된다는 비유로 K4와 캐시 치환 문제를 설명했다.

## 요청된 네 쟁점
- L1/L2 게이트: 미해결20%+토큰 비용은 탐색 신호로 채택, 도입 충분조건으로는 부적절. 규칙 보완 대안과 증분효과·오판정·메모리·유지비 비교. 계획:97.
- Mac 우선: 전송/Windows 권한 확장 축소는 채택. 같은 dirty tree 직접 실행은 보류. 같은 UID라는 이유로 실행 승인이나 무부작용이 보장되지 않는다. 계획:114.
- K3: n300으로3%p/n1000으로1%p 보장은 거부. holdout30%이면 평가90/300. paired difference CI·기준 정확도·불일치율·검정력 필요. 프로젝트/세션/시그니처별 split과 평가 중 학습 동결. 계획:61.
- 훅 승격: shadow→조언은 채택, deny와 updatedInput은 별도 위험/검증 게이트. K4≤10% 하나로 승인 불가. 계획:95,145.

통계 설명: 독립 Bernoulli 표본의 오류0건에서 단측95% 오류율 상한은 1−0.05^(1/n). n90≈3.27%, n300≈0.99%. 이것은 paired 비열등성 증명과 다르며 필요한 표본 수를 대체하는 공식이 아니다.

## 추가 발견·보완 제안
1. K4는 주입 후 재발인데 shadow 주입은0: Phase1에서 실제 K4 측정 불가. 전문가 대비 적합률과 실개입의 채택/해결/재발/포기/회귀를 분리. 계획:62,140.
2. fail-open에서 명시적 permissionDecision allow는 중립 no-op와 다름. 최적화 실패 시 기존 승인 흐름을 유지하는 중립 반환 필요. 계획:96.
3. 에이전트 간 동일 hook 계약을 가정하지 말 것. PostToolUseFailure/취소/권한거부를 설치판별 대조. 계획:104.
4. 최신 Claude 공식 문서가 PostToolUse.updatedToolOutput을 설명하므로 두 선행 검토의 출력대체 불가 단정은 재검증 필요. 설치판 지원 확인 전 대체 가능으로 확정하지 않음. 사후 교체는 실행 비용을 없애지 않음.
5. write-tree는 현재 index 트리이며 임시 index 선언만으로 dirty/untracked/ignored·환경·도구 의존성이 결합되지 않음. Git 정규화 동일성은 실제 실행입력 동일성과 다름. git diff 비교 기준/HEAD/index, tsc incremental .tsbuildinfo 쓰기 포함 검토. 계획:114~116.
6. 캐시 대체는 stdout/stderr/종료·signal/절단·완료상태, immutable snapshot·atomic publication·취소 후 폐기·권한 보존을 증명해야 함.
7. L3 schema-valid 출력 즉시 L0 write-through는 오답을 반복 적용할 수 있음. candidate→verified 승격, policy/tool/source scope와 버전·expiry·폐기·기권 필요. 계획:90,107.
8. K2 분류율≠오류 해결률. K5 hit30%≠실제 순대기시간 절감. K7 output만 아니라 input/cache/L3/retry 총비용·성공률·완료시간 동시 측정. 계획:60~65.

## 카운슬 판정
현재 확인한 실행 경로에서 UTR:18의 로짓 게이팅·forward pass·실측 sub40ms 주장 거부, 계획§1 핵심 판정 채택.
- hierarchical_engine.py:35~64: keyword 고정 점수와 합 나눗셈. 주석 Softmax와 실제 연산 불일치.
- router_core.py:49~55: confidence 분기 없음.
- hierarchical_engine.py:168와 router_core.py:74: 상수 지연·상한 캡.
- jev_client.py:124~146: sleep·keyword·고정 confidence 시뮬레이션.
허용 가능한 설명은 외부 생성 토큰 없는 규칙 기반 시뮬레이터. 다른 노드/revision 전체나 ZTC 용어의 보편 정의를 단정한 것은 아님.

## Phase1 첫3작업 권고 (미실행)
1. 설치판별 hook/권한/실패 계약과 KPI/gold split·수집 전 privacy 규약 확정.
2. 오프라인 정직화·안전화: 상수·정책 경로, 로컬 통신/telemetry, bounded queue·timeout, 공유상태 동기화 fixture.
3. 유저 승인된 한 에이전트·한 노드 shadow: 성공뿐 아니라 실패/권한거부/취소/데몬부재/과부하에서 주입0·명령변경0·기존 승인 유지 검증, 기준선 측정.
이후 additionalContext는 제한 실험, deny는 false-denial과 보안 요구, updatedInput은 동등성과 권한 보존으로 각각 평가.

## 공식 자료 (조회 당시 내용, 설치판은 별도 검증)
- https://code.claude.com/docs/en/hooks : PreToolUse allow/updatedInput, PostToolUseFailure, PostToolUse updatedToolOutput.
- https://git-scm.com/docs/git-write-tree : current index 기반 tree object.
- https://www.typescriptlang.org/tsconfig/incremental.html : incremental .tsbuildinfo 저장.
