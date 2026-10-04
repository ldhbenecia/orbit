# Python 컨벤션 (`engine/`)

## 도구

- 패키지·가상환경: `uv` (`uv sync`, `uv run`). `pip install` 직접 사용 금지
- Python 3.13
- 린트·포맷: `ruff` (`ruff check --fix`, `ruff format`)
- 타입: `mypy --strict` 대상은 전체 (`strict = true`). 돈이 지나가는 `ledger`·`risk`·`brokers` 에서 `Any`·`type: ignore` 금지
- 테스트: `pytest`. 돈 경로는 단위 테스트 필수 (→ [money-safety](money-safety.md))

## 구조

```
engine/
├─ src/orbit/
│   ├─ strategies/   전략 순수 함수 (I/O 금지)
│   ├─ indicators/   지표 계산 (pandas)
│   ├─ backtest/     백테스터 · 성과 지표
│   ├─ brokers/      거래소 어댑터 (공통 Broker 프로토콜 + upbit / toss / mock)
│   ├─ ledger/       가상 장부
│   ├─ risk/         리스크 가드 · 하드 리밋 · 킬 스위치
│   ├─ marketdata/   시세(캔들) 수집 · 저장
│   ├─ api/          FastAPI (대시보드용, 조회 위주)
│   ├─ notify/       텔레그램
│   └─ scheduler.py
└─ tests/
```

- 의존 방향: `strategies` → `indicators` 만. `strategies` 는 `brokers`·`ledger`·`api` 를 import 하지 않는다
- 브로커는 `typing.Protocol` 로 정의, 실거래 어댑터와 `MockBroker` 가 같은 프로토콜을 구현
- 경계 데이터(API 응답, 설정, 대시보드 응답)는 pydantic 모델. 금액 필드는 `Decimal`
- 설정은 pydantic-settings 로 로드, 누락·검증 실패 시 dry-run 으로 떨어진다

## 스타일

- 타입 힌트 필수 (공개 함수)
- 예외를 삼키지 않는다. 돈 경로의 예상 못 한 예외 → 정지 + 알림
- `print` 대신 구조화 로깅 (시크릿 마스킹 필터 통과)
