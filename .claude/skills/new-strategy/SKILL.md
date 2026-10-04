---
name: new-strategy
description: orbit 에 새 매매 전략 추가 — 지식 문서 확인, 순수 함수 구현, 미래 데이터·경계 테스트, 백테스트 등록까지
---

# 전략 추가

## 인자

$ARGUMENTS — 전략 이름 또는 설명 (예: `이동평균 필터 120일`, `변동성 돌파 k=0.5`)

## 절차

1. **이해부터** — [docs/knowledge/strategies.md](../../../docs/knowledge/strategies.md) 에서 해당 전략의 근거 수준·알려진 약점을 찾는다. 없으면 추가한다. 사용자에게 학습 모드 형식(무엇 → 왜 → 어떤 때 깨지는지)으로 세 줄 설명
2. **정책 확인** — [docs/policy/investment-policy.md](../../../docs/policy/investment-policy.md) 의 허용 자산·금지 행위와 충돌하면 멈추고 묻는다
3. **인터페이스 확정** — 입력 캔들 주기, 파라미터와 기본값, 판단 형태(목표 포지션/주문 의도), 근거 문구 형식을 사용자에게 짧게 제시
4. **테스트 먼저** — `engine/tests/strategies/test_<name>.py`
   - 손으로 계산 가능한 작은 캔들로 매수/보유/매도 판단
   - **미래 데이터 테스트**: t 이후 캔들을 바꿔도 t 시점 판단이 같아야 함
   - 데이터 부족 구간(지표 계산 불가)에서 판단 = 아무것도 안 함
   - 근거 문구가 비어 있지 않음
5. **구현** — `engine/orbit/strategies/<name>.py` 순수 함수. I/O·`now()`·랜덤 금지, 금액 결정 금지 (→ [strategy-rules](../../rules/strategy-rules.md))
6. **백테스트 등록** — 전략 레지스트리에 추가, 기준선(단순 보유·적립식)과 함께 돌려지는지 확인
7. **검증** — `uv run pytest`, `uv run ruff check`, `uv run mypy` 결과를 그대로 보고
8. **다음** — 결과 해석은 `backtest-review` 스킬로. 용어가 새로 나왔으면 glossary 갱신
