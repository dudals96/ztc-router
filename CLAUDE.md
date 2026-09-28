# ztc-router — 에이전트 안내

작업 전 `README.md` 의 "정본과 실행 기준" 표를 읽는다.

- 이 저장소가 ZTC 구현의 개발 정본이다. 단, 전환 승인 전까지 live 실행은 `~/Pi` 사본이 맡는다. `~/Pi` 쪽 ZTC 파일은 고치지 않는다.
- launchd·전역 훅 경로 변경, 데몬 재시작, Pi 쪽 사본 삭제는 유저 승인 없이 하지 않는다.
- 변경 후 `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s engines/hybrid_router/tests` 가 통과해야 한다.
- 턴 기록은 Pi 규약대로 Pi `docs/turn-reports/` 에 남긴다(이 저장소에 별도 보고서 파일을 만들지 않는다).
