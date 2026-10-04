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
│   ├─ db/           SQLite 마이그레이션
│   ├─ api/          FastAPI (대시보드용, 조회 위주)
│   ├─ notify/       텔레그램
│   └─ scheduler.py
└─ tests/
```

- 의존 방향: `strategies` → `indicators`, `marketdata` 의 캔들 모델·가격 표기만. `strategies` 는 `brokers`·`ledger`·`api` 를 import 하지 않는다
- 브로커는 `typing.Protocol` 로 정의, 실거래 어댑터와 `MockBroker` 가 같은 프로토콜을 구현
- 경계 데이터(API 응답, 설정, 대시보드 응답)는 pydantic 모델. 금액 필드는 `Decimal`
- 설정은 pydantic-settings 로 로드, 누락·검증 실패 시 dry-run 으로 떨어진다

## DB (SQLite)

- 테이블은 `STRICT` — 선언과 다른 타입이 들어오면 거부. 복합 자연키 시계열은 `WITHOUT ROWID`
- **금액·수량은 최소 단위 정수** (`orbit.units.to_units`). 원화는 원, 코인 수량은 10^8. 자릿수를 넘는 값은 반올림하지 않고 거부. TEXT·REAL 로 숫자 저장 금지
- 예외: 백테스트 같은 **분석 산출물**은 원 미만 금액을 원 단위로, 비율을 ppm 정수로 반올림 저장 (`round_to_units`). 장부·주문에는 쓰지 않음
- 시각은 epoch 초 정수 (UTC)
- 스키마 변경은 `orbit/db/migrations.py` 의 `MIGRATIONS` 뒤에 추가만. 적용된 항목 수정·삭제 금지. 버전은 `PRAGMA user_version`
- 테이블을 지우고 새로 만드는 마이그레이션은 다시 받을 수 있는 캐시(시세)에만. 장부·주문 테이블은 데이터 보존 마이그레이션만
- 조회는 컬럼명을 명시 (`SELECT *` 금지)

## 스타일

- 타입 힌트 필수 (공개 함수)
- 예외를 삼키지 않는다. 돈 경로의 예상 못 한 예외 → 정지 + 알림
- `print` 대신 구조화 로깅 (시크릿 마스킹 필터 통과)
